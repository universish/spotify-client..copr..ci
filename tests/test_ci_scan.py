import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scan_sources', REPO / 'tools/scan_sources.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)
RUN = 'https://github.com/owner/project/actions/runs/123'


class CIScanTests(unittest.TestCase):
    def execute(self, fail_channel=None, bootstrap=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        metadata = root / 'source.json'
        metadata.write_text(json.dumps({'untouched': True, **({'Bootstrap': bootstrap} if bootstrap else {})}))
        records = {channel: {'SHA256': channel + '-digest'} for channel in ('stable', 'unstable')}
        events, scanned_paths = [], []
        def download(record, path):
            events.append('download:' + record['SHA256'])
            path.write_bytes(b'deb')
        bootstrap = SimpleNamespace(metadata=lambda path, channel: dict(records[channel]), download=download,
                                    verify=lambda path, record: events.append('verify:' + record['SHA256']))
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
        def run(args, **kwargs):
            if args[0] == 'clamscan': return SimpleNamespace(stdout='ClamAV 1.4/12345/date\n')
            if '--update' in args: events.append('update')
            if args[0] == 'dpkg-deb': events.append('extract')
            if '--scan' in args:
                folder = Path(kwargs['env']['SCAN_REPORT_DIR'])
                events.append('scan:' + folder.name)
                scanned_paths.append(Path(args[-1]))
                if folder.name == fail_channel: raise subprocess.CalledProcessError(1, args)
                folder.mkdir(parents=True)
                (folder / 'pua-status.json').write_text(json.dumps({'disposition': 'advisory' if folder.name == 'unstable' else 'clean'}))
            return SimpleNamespace(stdout='')
        with mock.patch.object(scanner.importlib.util, 'spec_from_file_location', return_value=fake_spec), \
             mock.patch.object(scanner.importlib.util, 'module_from_spec', return_value=bootstrap), \
             mock.patch.object(scanner.subprocess, 'run', side_effect=run):
            if fail_channel:
                with self.assertRaises(subprocess.CalledProcessError): scanner.scan(metadata, root / 'reports', RUN)
            else:
                scanner.scan(metadata, root / 'reports', RUN)
        self.assertTrue(all(not path.exists() for path in scanned_paths))
        return json.loads(metadata.read_text()), events

    def test_both_debs_scanned_and_hash_bound_before_attestation(self):
        records, events = self.execute()
        self.assertEqual(events, ['update', 'download:stable-digest', 'verify:stable-digest', 'extract', 'scan:stable',
                                  'download:unstable-digest', 'verify:unstable-digest', 'extract', 'scan:unstable'])
        self.assertEqual(records['stable']['ScanAttestation']['SHA256'], 'stable-digest')
        self.assertEqual(records['unstable']['ScanAttestation']['PUA'], 'advisory')
        self.assertEqual(records['stable']['ScanAttestation']['RunURL'], RUN)
        self.assertEqual(records['stable']['ScanAttestation']['DatabaseVersion'], 'ClamAV 1.4/12345/date')

    def test_any_channel_scan_failure_does_not_write_partial_attestations(self):
        records, events = self.execute(fail_channel='unstable')
        self.assertEqual(records, {'untouched': True})

    def test_packaging_date_identity_survives_both_scans(self):
        identity={'Version':'26.10.31','Release':1,'Timezone':'Europe/Stockholm','PackagedAt':'2026-10-31T00:00:00+01:00'}
        records, events=self.execute(bootstrap=identity)
        self.assertEqual(records['Bootstrap'],identity)

    def test_unverifiable_run_url_rejected(self):
        with self.assertRaises(ValueError): scanner.scan('unused', 'unused', 'https://example.invalid/run')


class WorkflowContractTests(unittest.TestCase):
    def test_offline_copr_make_refuses_implicit_download_or_unscanned_input(self):
        result = subprocess.run(['make', '-f', '.copr/Makefile', 'srpm'], cwd=REPO,
                                env=dict(__import__('os').environ, SCANNED_METADATA='', SPOT_FLY_LIGHT_RELEASE=''),
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Use the GitHub Actions workflow', result.stderr)
        makefile = (REPO / '.copr/Makefile').read_text()
        self.assertNotIn('parser_debian_control_file.py', makefile)
        self.assertNotIn('clamav', makefile)
        self.assertNotIn('dnf ', makefile)

    def test_github_release_is_gated_and_artifacts_contain_reports_only(self):
        workflow = (REPO / '.github/workflows/spotify-rpm-releases.yml').read_text()
        copr = workflow.index('run: bash tools/submit_copr.sh')
        gate = workflow.index('python3 tools/verify_release_payload.py')
        draft = workflow.index('gh release create ')
        publish = workflow.index('gh release edit ')
        cleanup = workflow.index('      - name: Remove transient RPMs')
        self.assertLess(copr, gate)
        self.assertLess(gate, draft)
        self.assertLess(draft, publish)
        self.assertLess(publish, cleanup)
        release_step = workflow.split('      - name: Verify and publish only the payload-free bootstrap to GitHub Releases', 1)[1].split('      - name:', 1)[0]
        self.assertIn("if: steps.version.outputs.needed == 'true'", release_step)
        self.assertIn('GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}', release_step)
        self.assertIn('SPOT_FLY_LIGHT_TAG: ${{ steps.version.outputs.tag }}', release_step)
        self.assertIn('--verify-tag --draft', release_step)
        self.assertIn('gh release edit "$SPOT_FLY_LIGHT_TAG" --draft=false --latest', release_step)
        self.assertIn('--notes-file output/release-notes.md output/spot-fly-light-*.src.rpm output/spot-fly-light-*.x86_64.rpm output/SHA256SUMS', release_step)
        self.assertNotIn('output/*.rpm', release_step)
        self.assertNotIn('client-local', release_step)
        self.assertNotIn('download-artifact', workflow)
        artifact_paths = workflow.split('          path: |', 1)[1]
        self.assertNotIn('*.rpm', artifact_paths)
        self.assertIn('output/scan-reports/', artifact_paths)
        self.assertIn('if: always()', workflow)
        scan_step = workflow.split('      - name: Download, verify, extract and scan upstream DEBs in this runner', 1)[1].split('      - name:', 1)[0]
        self.assertIn('TMPDIR: /tmp', scan_step)
        self.assertIn('/tmp/spot..fly..light-ci-scan-* /tmp/spot..fly..light-freshclam.*', workflow)
        self.assertLess(workflow.index('tools/scan_sources.py'), workflow.index('tools/build_bootstrap.py'))


if __name__ == '__main__': unittest.main()
