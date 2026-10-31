import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_bootstrap', REPO / 'tools/build_bootstrap.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def record(channel, version='1.2.3'):
    digest = 'a' * 64
    return {'Package': 'spotify-client', 'Architecture': 'amd64', 'RPMVersion': version,
            'Filename': f'pool/non-free/s/spotify-client/spotify-client_{version}_amd64.deb',
            'SHA256': digest, 'Size': 123, 'Channel': channel,
            'ScanAttestation': {'SHA256': digest, 'Malware': 'clean', 'PUA': 'advisory', 'Scanner': 'ClamAV',
                'RunURL': 'https://github.com/universish/spotify-client..copr..ci/actions/runs/123',
                'ScannedAt': '2026-10-30T00:00:00+00:00', 'DatabaseVersion': 'ClamAV 1.4/123/date'}}


class BootstrapArchiveTests(unittest.TestCase):
    def test_contains_both_scanned_records_and_only_free_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = root / 'source.json'
            metadata.write_text(json.dumps({'stable': record('stable'), 'unstable': record('unstable', '2.0')}))
            inspected = []
            def observe(args, **kwargs):
                spec_path = Path(args[-1])
                text = spec_path.read_text()
                self.assertIn('Name: spot-fly-light\n', text)
                self.assertIn('Obsoletes: sonicradle\n', text)
                self.assertIn('Provides: sonicradle = 1.2.3-5%{?dist}\n', text)
                self.assertEqual([line for line in text.splitlines() if line.startswith('Obsoletes:')], ['Obsoletes: sonicradle'])
                self.assertNotIn('/usr/bin/clamscan', text)
                self.assertNotIn('/usr/bin/freshclam', text)
                archive_path = spec_path.parent.parent / 'SOURCES/bootstrap.tar.gz'
                with tarfile.open(archive_path) as archive:
                    files = {member.name for member in archive.getmembers() if member.isfile()}
                    self.assertEqual(files, {'bootstrap/' + name for name in ('spot..fly..light.py', 'spot..fly..light-gpu.sh',
                        'eula.txt', 'DISCLAIMER.txt', 'COPYRIGHT', 'MIT-new-contributions.txt', 'source.json')})
                    records = json.load(archive.extractfile('bootstrap/source.json'))
                    self.assertEqual(set(records), {'stable', 'unstable'})
                    self.assertEqual(records['stable']['PackagingRelease'], 5)
                    self.assertEqual(records['unstable']['PackagingRelease'], 1)
                    self.assertEqual(records['unstable']['ScanAttestation']['PUA'], 'advisory')
                inspected.append(True)
            with mock.patch.object(builder.subprocess, 'run', side_effect=observe): builder.build(metadata, root / 'out', 5)
            self.assertTrue(inspected)

    def test_missing_or_mismatched_scan_blocks_source_rpm(self):
        for change in ('missing', 'mismatched'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                item = record('stable')
                if change == 'missing': del item['ScanAttestation']
                else: item['ScanAttestation']['SHA256'] = 'b' * 64
                metadata = root / 'source.json'
                metadata.write_text(json.dumps(item))
                with mock.patch.object(builder.subprocess, 'run') as run:
                    with self.assertRaises(ValueError): builder.build(metadata, root / 'out', 1)
                run.assert_not_called()


if __name__ == '__main__': unittest.main()
