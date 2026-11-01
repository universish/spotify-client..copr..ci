import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('archive_planner', ROOT / 'tools/plan_release.py')
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


def channels():
    return {channel: {'Package': 'spotify-client', 'Architecture': 'amd64', 'Channel': channel,
        'Version': '1:' + version, 'RPMVersion': version, 'SHA256': digest * 64, 'Size': 123,
        'Filename': 'pool/non-free/s/spotify-client/spotify-client_' + version + '_amd64.deb',
        'PackagingRelease': 1}
        for channel, version, digest in [('stable', '1.2.63.394.g126b0d89', 'a'),
            ('unstable', '1.2.86.502.g8cd7fb22', 'b')]}


def reservation(identity, signature=None):
    prefix = identity.get('Name', 'spot-fly-light')
    return {'ref': f"refs/tags/{prefix}-v{identity['Version']}-{identity['Release']}",
        'reservation': {'bootstrap': identity, 'signature': signature}}


def build(identity, state='succeeded'):
    return {'source_package': {'name': identity.get('Name', 'spot-fly-light'),
        'version': f"{identity['Version']}-{identity['Release']}.fc44"}, 'state': state}


class ArchivePlanningTests(unittest.TestCase):
    def test_explicit_archive_pair_uses_fresh_signed_proof_for_exact_current_bytes(self):
        sources = channels()
        signed = {channel: dict(record, Authentication={'proof': channel}) for channel, record in sources.items()}
        def fetch(channel, **kwargs): return copy.deepcopy(signed[channel])
        for requested in ('1.2.63.394', '1:1.2.63.394.g126b0d89'):
            with self.subTest(requested=requested), mock.patch.object(planner, 'fetch_package', side_effect=fetch), \
                    mock.patch('spotify_history.select_historical_channels', return_value=(copy.deepcopy(sources), {'Selection': 'manual'})), \
                    mock.patch('parser_debian_control_file.verify_historical_record') as archived:
                result, pairing = planner.select_sources(requested, 'stable', '1.2.86.502')
            self.assertEqual(pairing['Kind'], 'archive')
            self.assertEqual(result['stable']['Authentication'], {'proof': 'stable'})
            self.assertEqual(result['unstable']['Authentication'], {'proof': 'unstable'})
            archived.assert_not_called()

    def test_changed_historical_hash_cannot_borrow_current_authentication(self):
        sources = channels(); historical = copy.deepcopy(sources)
        historical['stable']['SHA256'] = 'c' * 64
        def fetch(channel, **kwargs): return copy.deepcopy(sources[channel])
        with mock.patch.object(planner, 'fetch_package', side_effect=fetch), \
                mock.patch('spotify_history.select_historical_channels', return_value=(historical, {'Selection': 'manual'})), \
                mock.patch('parser_debian_control_file.verify_historical_record', side_effect=ValueError('No signed historical proof')) as archived:
            with self.assertRaisesRegex(ValueError, 'No signed historical proof'):
                planner.select_sources('1.2.63.394', 'stable', '1.2.86.502')
        archived.assert_called_once_with(historical['stable'])

    def test_old_pair_uses_version_zero_and_counts_failed_reservations(self):
        sources = channels()
        first = planner.archive_identity(sources, {'Selection': 'manual'}, [], [])
        self.assertEqual(first['Name'], 'spot-fly-light-st1.2.63.394-unst1.2.86.502')
        self.assertEqual((first['Version'], first['Release']), ('0', '1'))
        self.assertNotIn('.g', first['Name'])
        second = planner.archive_identity(sources, {}, [reservation(first)], [build(first, 'failed')])
        self.assertEqual(second['Release'], '2')
        self.assertEqual(sources['stable']['Version'], '1:1.2.63.394.g126b0d89')

    def test_original_helper_date_and_slot_are_preserved_when_archived(self):
        sources = channels()
        original = {'Version': '26.10.31', 'Release': 3, 'Timezone': 'Europe/Stockholm',
            'PackagedAt': '2026-10-31T14:00:00+01:00'}
        ref = reservation(original, planner.source_signature(sources))
        identity = planner.archive_identity(sources, {}, [ref], [build(original)])
        self.assertEqual((identity['Version'], identity['Release']), ('26.10.31', '3.1'))
        self.assertEqual(identity['OriginalBootstrap'], {'Version': '26.10.31', 'Release': 3,
            'PackagedAt': original['PackagedAt']})
        again = planner.archive_identity(sources, {}, [ref, reservation(identity)], [build(original), build(identity)])
        self.assertEqual(again['Release'], '3.2')

    def test_archive_atomic_collision_only_increments_its_last_counter(self):
        sources = channels()
        identity = planner.archive_identity(sources, {}, [], [])
        class API:
            def __init__(self): self.messages = []
            def call(self, path, data=None):
                if path == '/git/tags':
                    self.messages.append(json.loads(data['message']))
                    return {'sha': 'b' * 40}
                if data and data['ref'].endswith('-1'):
                    raise HTTPError('https://api.github.com', 422, 'exists', {}, io.BytesIO())
                return {}
        api = API()
        saved, tag = planner.reserve_archive(api, sources, identity, 'a' * 40,
            planner.reservation_payload(sources, identity, 'signature'))
        self.assertEqual(saved['Release'], '2')
        self.assertTrue(tag.endswith('-v0-2'))
        self.assertEqual(identity['Release'], '1')
        self.assertEqual(api.messages[0]['channels'], api.messages[1]['channels'])

    def test_archive_can_never_satisfy_or_renumber_current_schedule(self):
        archive = planner.archive_identity(channels(), {}, [], [])
        archive['Release'] = '100'
        result = planner.plan('26.11.01', [], [reservation(archive, 'same')], [build(archive)], signature='same')
        self.assertTrue(result['needed'])
        self.assertEqual(result['release'], 1)

    def test_previous_matching_current_pair_cannot_mask_later_delivered_pair(self):
        old = {'Version': '26.10.31', 'Release': 1}
        latest = {'Version': '26.11.01', 'Release': 1}
        refs = [reservation(old, 'same'), reservation(latest, 'different')]
        result = planner.plan('26.11.02', [], refs, [build(old), build(latest)], signature='same')
        self.assertTrue(result['needed'])

    def test_archive_finalization_keeps_identity_across_midnight(self):
        sources = channels()
        identity = planner.archive_identity(sources, {}, [], [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.json'
            path.write_text(json.dumps(dict(sources, Bootstrap=identity)))
            current = {'Version': '26.11.02', 'Timezone': 'Europe/Stockholm', 'PackagedAt': '2026-11-02T00:04:00+01:00'}
            with mock.patch.object(planner, 'packaging_identity', return_value=current), mock.patch.object(planner, 'GitHub') as api:
                result, updated = planner.finalize(path, 'owner/repo')
            saved = json.loads(path.read_text())
            self.assertEqual((saved['Bootstrap']['Version'], saved['Bootstrap']['Release']), ('0', '1'))
            self.assertEqual(saved['Bootstrap']['PackagedAt'], current['PackagedAt'])
            self.assertEqual(saved['stable'], sources['stable'])
            self.assertEqual(result['kind'], 'archive')
            api.assert_not_called()

    def test_raw_debian_epoch_is_part_of_new_client_counter_identity(self):
        helper = {'Version': '26.10.31', 'Release': 1}
        ref = reservation(helper)
        ref['reservation']['channels'] = {'stable': {'version': '1.2.63.394.g126b0d89',
            'debian_version': '1:1.2.63.394.g126b0d89', 'release': 4}}
        self.assertEqual(planner.channel_release('stable', '1:1.2.63.394.g126b0d89', [ref], builds=[build(helper)]), 5)
        self.assertEqual(planner.channel_release('stable', '2:1.2.63.394.g126b0d89', [ref], builds=[build(helper)]), 1)

    def test_rollback_highwater_ignores_archives_and_keeps_signed_dates(self):
        helper = {'Version': '26.10.31', 'Release': 1}
        ref = reservation(helper)
        proof = {'RepositoryID': 'spotify-repository', 'Distribution': 'stable',
            'ReleaseDate': '2026-08-12T13:00:02+00:00', 'ReleaseSHA256': 'a' * 64}
        ref['reservation']['source_authentication'] = {'stable': proof}
        archive = reservation(planner.archive_identity(channels(), {}, [], []))
        archive['reservation']['source_authentication'] = {'stable': dict(proof, ReleaseDate='2027-01-01T00:00:00+00:00')}
        self.assertEqual(planner.accepted_states([archive, ref]), {'spotify-repository:stable': {
            'ReleaseDate': proof['ReleaseDate'], 'ReleaseSHA256': proof['ReleaseSHA256']}})


if __name__ == '__main__':
    unittest.main()
