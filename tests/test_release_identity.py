import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from release_identity import archive_name, parse_debian_version, release_profile, validate_identity


def archive_catalog():
    return {'stable': {'Version': '1:1.2.63.394.g126b0d89'},
            'unstable': {'Version': '1:1.2.86.502.g8cd7fb22'},
            'Bootstrap': {'Kind': 'archive', 'Name': 'spot-fly-light-st1.2.63.394-unst1.2.86.502',
                          'Version': '0', 'Release': '2', 'PackagedAt': '2026-11-01T18:00:00+01:00',
                          'Timezone': 'Europe/Stockholm'}}


class ReleaseIdentityTests(unittest.TestCase):
    def test_historic_debian_revisions_and_variable_commit_suffixes_preserve_raw_identity(self):
        for raw, expected in [('1:1.0.98.78.gb45d2a6b-10', '1.0.98.78.gb45d2a6b.deb10'),
                              ('1:1.1.84.716.gc5f8b819-2', '1.1.84.716.gc5f8b819.deb2'),
                              ('1:0.8.2.637.g252b980.486-1', '0.8.2.637.g252b980.486.deb1'),
                              ('1:0.9.1.55.gbdd3b79.203-1', '0.9.1.55.gbdd3b79.203.deb1')]:
            with self.subTest(raw=raw):
                parsed = parse_debian_version(raw)
                self.assertEqual(parsed['raw'], raw)
                self.assertEqual(parsed['rpm_version'], expected)
                self.assertEqual(parsed['epoch'], '1')
                self.assertNotIn('-', parsed['rpm_version'])

    def test_archive_name_omits_hashes_and_has_an_isolated_private_client(self):
        records = archive_catalog()
        profile = release_profile(records)
        name = 'spot-fly-light-st1.2.63.394-unst1.2.86.502'
        self.assertEqual(archive_name(records), name)
        self.assertEqual(profile['client_name'], 'spotify-client-via-' + name)
        self.assertEqual(profile['command'], name)
        self.assertEqual(profile['share'], '/usr/share/' + name + '-bootstrap')
        self.assertEqual(profile['state'], name + '-bootstrap')

    def test_archive_preserves_known_first_identity_but_records_real_packaging_time(self):
        records = archive_catalog()
        records['Bootstrap'].update(Version='26.10.31', Release='3.2',
            OriginalBootstrap={'Version': '26.10.31', 'Release': 3, 'PackagedAt': '2026-10-31T20:00:00+01:00'})
        identity = validate_identity(records)
        self.assertEqual(identity['Version'], '26.10.31')
        self.assertEqual(identity['Release'], '3.2')
        self.assertEqual(identity['PackagedAt'], '2026-11-01T18:00:00+01:00')
        for changes in ({'Release': '4.2'}, {'Version': '26.11.01'}, {'Name': 'spot-fly-light'},
                        {'OriginalBootstrap': None}):
            bad = copy.deepcopy(records); bad['Bootstrap'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_identity(bad)

    def test_undated_archive_and_current_date_identity_cannot_be_confused(self):
        records = archive_catalog()
        for changes in ({'Version': '26.11.01'}, {'Release': '2.1'}, {'Kind': 'current'},
                        {'Name': 'spot-fly-light-st1.2.63.394-unst1.2.86.502.gdeadbeef'}):
            bad = copy.deepcopy(records); bad['Bootstrap'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_identity(bad)
        records['Bootstrap'].update(Kind='current', Name='spot-fly-light', Version='26.11.01')
        current = release_profile(records)
        self.assertEqual(current['client_name'], 'spotify-client-via-spot-fly-light')
        self.assertEqual(current['Release'], '2')


if __name__ == '__main__':
    unittest.main()
