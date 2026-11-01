import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import spotify_history as history

spec = importlib.util.spec_from_file_location('history_collector', ROOT / 'tools/collect_spotify_history.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def record(version, channel='stable', digest='a', identifier=None):
    return {'Id': identifier or channel + '-' + version, 'Package': 'spotify-client',
        'Architecture': 'amd64', 'Version': version, 'DebianVersion': version,
        'Filename': 'pool/non-free/s/spotify-client/spotify-client_' + version.split(':')[-1] + '_amd64.deb',
        'SHA256': digest * 64, 'Size': 321, 'Channel': channel,
        'PublishedAt': None, 'FirstObservedAt': '2025-01-01T00:00:00+00:00',
        'Evidence': [{'URL': 'https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages'}]}


class HistoricalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'catalog.json'
        self.stable = record('1:1.2.63.394.g126b0d89')
        self.unstable = record('1:1.2.86.502.g8cd7fb22', 'unstable', 'b')

    def catalog(self, records=None, pairs=None):
        self.path.write_text(json.dumps({'schema': 1, 'records': records or [self.stable, self.unstable],
            'reviewed_pairs': pairs or []}))

    def select(self, requested='1.2.63.394', channel='auto', opposite='1.2.86.502'):
        return history.select_historical_channels(requested, channel, opposite, self.path)

    def test_manual_pair_preserves_source_identity_and_does_not_invent_dates(self):
        self.catalog()
        sources, pairing = self.select()
        self.assertEqual(sources['stable']['Version'], '1:1.2.63.394.g126b0d89')
        self.assertEqual(sources['stable']['CommitHash'], '126b0d89')
        self.assertEqual(pairing['Selection'], 'manual')
        self.assertIsNone(pairing['AnchorPublishedAt'])
        self.assertEqual(pairing['Evidence'], [])

    def test_numeric_request_never_matches_version_prefix(self):
        self.catalog()
        with self.assertRaisesRegex(ValueError, 'No evidenced'):
            self.select('1.2.63.39')
        self.assertFalse(history.matches_version(self.stable['Version'], '1.2.63.39'))

    def test_epoch_debian_revision_and_variable_commit_are_preserved(self):
        revision = record('1:1.0.98.78.gb45d2a6b-10')
        self.catalog([revision, self.unstable])
        sources, _ = self.select('1.0.98.78.gb45d2a6b-10')
        self.assertEqual(sources['stable']['RPMVersion'], '1.0.98.78.gb45d2a6b.deb10')
        self.assertEqual(sources['stable']['DebianRevision'], '10')
        long_commit = record('1:1.3.4.258.gc60b10b0946a', 'unstable', 'b')
        self.assertEqual(history.source_record(long_commit)['CommitHash'], 'c60b10b0946a')

    def test_ambiguous_numeric_build_requires_full_version(self):
        second = record('1:1.2.63.394.gdeadbeef', digest='c')
        self.catalog([self.stable, second, self.unstable])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.select()
        sources, _ = self.select('1:1.2.63.394.g126b0d89')
        self.assertEqual(sources['stable']['SHA256'], 'a' * 64)

    def test_distro_channel_is_not_inferred_by_auto(self):
        unclassified = copy.deepcopy(self.stable)
        unclassified['Channel'] = 'unknown'
        self.catalog([unclassified, self.unstable])
        with self.assertRaisesRegex(ValueError, 'No evidenced'):
            self.select()
        sources, pairing = self.select(channel='stable')
        self.assertEqual(sources['stable']['ChannelEvidence'], 'manual')
        self.assertEqual(pairing['Selection'], 'manual')
        self.assertIn('ChannelAssignment', pairing)

    def test_capture_time_is_not_enough_for_automatic_counterpart(self):
        self.catalog()
        with self.assertRaisesRegex(ValueError, 'chronology is not proven'):
            self.select(opposite='')

    def test_reviewed_pair_requires_evidence_and_exact_source_ids(self):
        pair = {'reviewed': True, 'stable': self.stable['Id'], 'unstable': self.unstable['Id'],
            'Evidence': [{'URL': 'https://example.test/reviewed-observation'}],
            'AnchorObservedAt': '2025-02-01T00:00:00+00:00'}
        self.catalog(pairs=[pair])
        _, selected = self.select(opposite='')
        self.assertEqual(selected['Selection'], 'historical')
        self.assertEqual(selected['AnchorObservedAt'], pair['AnchorObservedAt'])
        self.assertIsNone(selected['AnchorPublishedAt'])
        pair['unstable'] = 'missing-id'
        self.catalog(pairs=[pair])
        with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
            self.select(opposite='')

    def test_catalog_never_reuses_past_scan_or_authentication_as_authority(self):
        self.stable.update(Authentication={'Verified': True}, ScanAttestation={'Clean': True})
        self.catalog()
        sources, _ = self.select()
        self.assertNotIn('Authentication', sources['stable'])
        self.assertNotIn('ScanAttestation', sources['stable'])

    def test_unsupported_legacy_layout_and_invalid_paths_are_rejected(self):
        legacy = record('1:0.8.2.637.g252b980.486-1')
        with self.assertRaisesRegex(ValueError, 'layout is not supported'):
            history.source_record(legacy)
        invalid = copy.deepcopy(self.stable)
        invalid['Filename'] = 'pool/../escape_amd64.deb'
        with self.assertRaisesRegex(ValueError, 'filename'):
            history.source_record(invalid)


class HistoricalCollectorTests(unittest.TestCase):
    def test_recipe_literal_filename_preserves_hash_but_does_not_invent_debian_epoch(self):
        recipe = '''pkgver='1.3.4.258'
epoch=1
_commit=gc60b10b0946a
source=("http://repository.spotify.com/pool/non-free/s/spotify-client/spotify-client_${pkgver}.${_commit}_amd64.deb")
# http://repository.spotify.com/dists/testing/Release
'''
        commit = {'commit': {'committer': {'date': '2026-10-01T00:00:00Z'}}}
        rows = collector.recipe_observations(recipe, 'https://example.test/PKGBUILD', commit, '2026-11-01T00:00:00Z')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['Version'], '1.3.4.258.gc60b10b0946a')
        self.assertEqual(rows[0]['CommitHash'], 'c60b10b0946a')
        self.assertIsNone(rows[0]['DebianEpoch'])
        self.assertIsNone(rows[0]['PublishedAt'])
        self.assertEqual(rows[0]['Channel'], 'unknown')
        self.assertEqual(rows[0]['RecipeConfiguredChannel'], 'unstable')

    def test_recipe_commands_and_unresolved_variables_are_never_executed(self):
        recipe = '''pkgver=$(touch /tmp/forbidden-history-recipe)
source=("http://repository.spotify.com/pool/non-free/s/spotify-client/spotify-client_${pkgver}_amd64.deb")
'''
        commit = {'commit': {'committer': {'date': '2026-10-01T00:00:00Z'}}}
        self.assertEqual(collector.recipe_observations(recipe, 'https://example.test', commit, 'now'), [])

    def test_control_continuations_and_package_architecture_filter(self):
        text = 'Package: spotify-client\nArchitecture: amd64\nVersion: 1:1.2.63.394.g126b0d89\nDescription: title\n body\n\nPackage: other\nArchitecture: i386\n'
        records = list(collector.package_records(text))
        self.assertEqual(records[0]['Description'], 'title\nbody')
        self.assertEqual(len(records), 2)
        self.assertIsNone(collector.source_record(records[1], 'stable', {}, 'https://repository.spotify.com'))

    def test_merging_observations_keeps_earliest_capture_separate_from_release(self):
        original = self.record('2026-01-02T00:00:00+00:00')
        older = self.record('2025-01-01T00:00:00+00:00')
        records = {}
        collector.merge_record(records, original)
        collector.merge_record(records, older)
        merged = records[original['Id']]
        self.assertEqual(merged['FirstObservedAt'], '2025-01-01T00:00:00+00:00')
        self.assertIsNone(merged['PublishedAt'])
        self.assertEqual(len(merged['Evidence']), 2)

    @staticmethod
    def record(observed):
        raw = record('1:1.2.63.394.g126b0d89')
        return collector.source_record(raw, 'stable', {'URL': 'https://example.test/' + observed,
            'ObservedAt': observed}, 'https://repository.spotify.com')


if __name__ == '__main__':
    unittest.main()
