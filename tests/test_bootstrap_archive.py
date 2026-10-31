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


def identity(release=5):
    return {'Version': '26.10.31', 'Release': release, 'Timezone': 'Europe/Stockholm',
            'PackagedAt': '2026-10-31T05:00:00+01:00'}


class BootstrapArchiveTests(unittest.TestCase):
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
                        'onboarding.py', 'spot-fly-light-onboarding.desktop', 'spot-fly-light-onboarding.service')})
                    records = json.load(archive.extractfile('bootstrap/source.json'))
                    self.assertEqual(set(records), {'stable', 'unstable', 'Bootstrap'})
                    self.assertEqual(records['Bootstrap'], identity())
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


if __name__ == '__main__': unittest.main()
