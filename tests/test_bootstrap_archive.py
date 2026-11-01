import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
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


def identity(release=5):
    return {'Version': '26.10.31', 'Release': release, 'Timezone': 'Europe/Stockholm',
            'PackagedAt': '2026-10-31T05:00:00+01:00'}


class BootstrapArchiveTests(unittest.TestCase):
    def setUp(self):
        self.auth = mock.patch.object(builder, 'validate_auth', return_value=None)
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def test_contains_both_scanned_records_and_only_free_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = root / 'source.json'
            metadata.write_text(json.dumps({'stable': dict(record('stable'), PackagingRelease=9),
                'unstable': dict(record('unstable', '2.0'), PackagingRelease=3), 'Bootstrap': identity()}))
            inspected = []
            def observe(args, **kwargs):
                spec_path = Path(args[-1])
                text = spec_path.read_text()
                self.assertIn('Name: spot-fly-light\n', text)
                self.assertIn('Obsoletes: sonicradle\n', text)
                self.assertIn('Version: 26.10.31\n', text)
                self.assertIn('Provides: sonicradle = 26.10.31-5%{?dist}\n', text)
                self.assertIn('Spotify stable client: 1.2.3-9.', text)
                self.assertIn('Spotify unstable client: 2.0-3.', text)
                self.assertIn('/usr/bin/spot-fly-light\n', text)
                self.assertIn('/etc/xdg/autostart/spot-fly-light-onboarding.desktop\n', text)
                self.assertIn('/usr/lib/systemd/user/spot-fly-light-onboarding.service\n', text)
                self.assertIn('desktop-file-validate %{buildroot}/etc/xdg/autostart/', text)
                scriptlet = text.split('%posttrans\n', 1)[1].split('%files\n', 1)[0]
                self.assertIn('command -v loginctl', scriptlet)
                self.assertIn('--property=Type', scriptlet)
                self.assertIn('--property=Remote', scriptlet)
                self.assertIn('--property=Active', scriptlet)
                self.assertIn('--user --machine="$user@.host"', scriptlet)
                self.assertIn('--no-block start spot-fly-light-onboarding.service', scriptlet)
                self.assertIn('exit 0', scriptlet)
                self.assertNotIn('zenity', scriptlet)
                self.assertNotIn('python3', scriptlet)
                self.assertEqual([line for line in text.splitlines() if line.startswith('Obsoletes:')], ['Obsoletes: sonicradle'])
                self.assertNotIn('/usr/bin/clamscan', text)
                self.assertNotIn('/usr/bin/freshclam', text)
                archive_path = spec_path.parent.parent / 'SOURCES/bootstrap.tar.gz'
                with tarfile.open(archive_path) as archive:
                    files = {member.name for member in archive.getmembers() if member.isfile()}
                    self.assertEqual(files, {'bootstrap/' + name for name in ('spot..fly..light.py', 'spot..fly..light-gpu.sh',
                        'eula.txt', 'DISCLAIMER.txt', 'COPYRIGHT', 'MIT-new-contributions.txt', 'source.json',
                        'release_identity.py', 'fontconfig_runtime.py', 'source_auth.py', 'source-registry.json',
                        'onboarding.py', 'spot-fly-light-onboarding.desktop', 'spot-fly-light-onboarding.service')})
                    records = json.load(archive.extractfile('bootstrap/source.json'))
                    self.assertEqual(set(records), {'stable', 'unstable', 'Bootstrap'})
                    self.assertEqual(records['Bootstrap'], dict(identity(), Name='spot-fly-light', Kind='current'))
                    self.assertEqual(records['stable']['PackagingRelease'], 9)
                    self.assertEqual(records['unstable']['PackagingRelease'], 3)
                    self.assertEqual(records['unstable']['ScanAttestation']['PUA'], 'advisory')
                    for name in ('eula.txt', 'DISCLAIMER.txt'):
                        notice = archive.extractfile('bootstrap/' + name).read().decode()
                        self.assertNotIn('sonicradle', notice.lower())
                        self.assertNotIn('HUKUKİ BİLDİRİMİ', notice)
                        self.assertIn('Spot..Light', notice)
                inspected.append(True)
            with mock.patch.object(builder.subprocess, 'run', side_effect=observe): builder.build(metadata, root / 'out', 5)
            self.assertTrue(inspected)

    def test_invalid_or_mismatched_packaging_identity_blocks_build(self):
        for changes in ({'Version': '1.2.3'}, {'Timezone': 'Europe/Istanbul'}, {'Release': 6},
                        {'PackagedAt': '2026-10-31T05:00:00'}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'source.json'
                path.write_text(json.dumps({'stable': record('stable'), 'Bootstrap': dict(identity(), **changes)}))
                with mock.patch.object(builder.subprocess, 'run') as run:
                    with self.assertRaises(ValueError): builder.build(path, Path(tmp) / 'out', 5)
                run.assert_not_called()
        with mock.patch.dict('os.environ', {'SPOT_FLY_LIGHT_VERSION': '26.11.01'}):
            with self.assertRaises(ValueError): builder.bootstrap_identity({'Bootstrap': identity()}, 5)

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


@unittest.skipUnless(all(shutil.which(name) for name in ('rpmbuild', 'rpm', 'rpm2cpio', 'desktop-file-validate')),
                     'RPM build tools are unavailable')
class ActualFreeRPMBuildTests(unittest.TestCase):
    def test_current_and_archive_rpms_pass_the_actual_binary_payload_gate(self):
        """Exercise distro RPM doc layouts and script normalization, with no DEB."""
        gate_spec = importlib.util.spec_from_file_location('integration_release_gate', REPO / 'tools/verify_release_payload.py')
        gate = importlib.util.module_from_spec(gate_spec); gate_spec.loader.exec_module(gate)
        for kind in ('current', 'archive'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); output = root / 'out'; top = root / 'rebuild'; top.mkdir()
                (top / 'tmp').mkdir()
                records = {'stable': record('stable', '1.2.63.394'),
                           'unstable': record('unstable', '1.2.86.502'), 'Bootstrap': identity(3)}
                version, release, name = '26.10.31', '3', 'spot-fly-light'
                if kind == 'archive':
                    name = 'spot-fly-light-st1.2.63.394-unst1.2.86.502'; release = '3.2'
                    records['Bootstrap'].update(Kind='archive', Name=name, Release=release,
                        PackagedAt='2026-11-01T18:00:00+01:00', OriginalBootstrap=identity(3))
                metadata = root / 'catalog.json'; metadata.write_text(json.dumps(records))
                # These are deliberately synthetic source/scan fixtures. This
                # integration verifies RPM bytes and identity only; the separate
                # authentication tests must establish cryptographic acceptance.
                with mock.patch.object(builder, 'validate_auth', return_value=None):
                    builder.build(metadata, output, release)
                source = output / f'{name}-{version}-{release}.src.rpm'
                result = subprocess.run(['rpmbuild', '--rebuild', '--nodeps', '--define', f'_topdir {top}',
                    '--define', f'_tmppath {top / "tmp"}', '--define', 'dist %{nil}', str(source)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                binary = next((top / 'RPMS').rglob('*.x86_64.rpm'))
                shutil.copy2(binary, output / binary.name)
                (output / 'SHA256SUMS').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()
                    + '  ' + path.name + '\n' for path in sorted(output.glob('*.rpm'))))
                with mock.patch.object(gate, 'validate_auth', return_value=None):
                    gate.verify(output, version, release,
                        'https://github.com/universish/spotify-client..copr..ci/actions/runs/123', name)
                files = gate.rpm_payload(output / binary.name)
                self.assertNotIn('usr/bin/spotify', files)
                self.assertFalse(any(path.endswith('.deb') for path in files))
                if kind == 'archive':
                    self.assertFalse(any('onboarding' in path for path in files))
                    self.assertNotIn('usr/bin/spot..fly..light', files)


if __name__ == '__main__': unittest.main()
