import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.error import HTTPError

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plan_release', REPO / 'tools/plan_release.py')
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


def build(version, number, state='succeeded', name='spot-fly-light'):
    return {'source_package': {'name': name, 'version': f'{version}-{number}'}, 'state': state}


def ref(version, number, signature='pinned'):
    return {'ref': f'refs/tags/spot-fly-light-v{version}-{number}', 'reservation': {'signature': signature}}


class PlanningTests(unittest.TestCase):
    def test_identical_channels_successfully_delivered_stop_schedule(self):
        result = planner.plan('1.2.3', [], [ref('1.2.3', 3)], [build('1.2.3', 3)], signature='pinned')
        self.assertFalse(result['needed'])
        self.assertNotIn('release', result)

    def test_manual_increments_same_pinned_version(self):
        result = planner.plan('1.2.3', [], [ref('1.2.3', 3)], [build('1.2.3', 3)], manual=True, signature='pinned')
        self.assertEqual((result['needed'], result['release'], result['tag']), (True, 4, 'spot-fly-light-v1.2.3-4'))

    def test_unstable_change_rebuilds_same_stable_version(self):
        result = planner.plan('1.2.3', [], [ref('1.2.3', 3)], [build('1.2.3', 3)], signature='changed-unstable')
        self.assertEqual(result['release'], 4)

    def test_new_stable_version_resets_to_one(self):
        result = planner.plan('1.2.4', [], [ref('1.2.3', 100)], [build('1.2.3', 101)], signature='new')
        self.assertEqual(result['release'], 1)

    def test_copr_history_and_legacy_tags_continue_counter(self):
        result = planner.plan('1.2.3', [], [{'ref': 'refs/tags/v1.2.3-4'}], [build('1.2.3', 9, name='spotify')], manual=True)
        self.assertEqual(result['release'], 10)

    def test_old_sonicradle_success_does_not_skip_new_package_delivery(self):
        old = {'ref': 'refs/tags/sonicradle-v1.2.3-6', 'reservation': {'signature': 'pinned'}}
        result = planner.plan('1.2.3', [], [old], [build('1.2.3', 6, name='sonicradle')], signature='pinned')
        self.assertTrue(result['needed'])
        self.assertEqual((result['release'], result['tag']), (7, 'spot-fly-light-v1.2.3-7'))

    def test_only_spot_fly_light_copr_success_can_fulfill_current_reservation(self):
        result = planner.plan('1.2.3', [], [ref('1.2.3', 7)], [build('1.2.3', 7, name='sonicradle')], signature='pinned')
        self.assertTrue(result['needed'])
        self.assertEqual(result['release'], 8)

    def test_testing_revision_continues_from_delivered_sonicradle_catalog(self):
        old = {'ref': 'refs/tags/sonicradle-v1.2.3-6', 'reservation': {'channels': {
            'stable': {'version': '1.2.3', 'release': 6}, 'unstable': {'version': '2.0', 'release': 1}}}}
        self.assertEqual(planner.channel_release('unstable', '2.0', [old], 7,
                         [build('1.2.3', 6, name='sonicradle')]), 2)
        self.assertEqual(planner.channel_release('unstable', '2.0', [old], 7,
                         [build('1.2.3', 6, name='spotify')]), 1)

    def test_copr_success_without_matching_source_signature_does_not_skip(self):
        self.assertTrue(planner.plan('1.2.3', [], [], [build('1.2.3', 1)], signature='unknown')['needed'])

    def test_reserved_failed_attempt_is_never_reused(self):
        result = planner.plan('1.2.3', [], [ref('1.2.3', 4)], [build('1.2.3', 5, 'failed')], signature='pinned')
        self.assertEqual(result['release'], 6)

    def test_removed_release_assets_still_leave_counter_history(self):
        result = planner.plan('1.2.3', [{'tag_name': 'v1.2.3-4', 'assets': []}], [], [])
        self.assertEqual(result['release'], 5)

    def test_version_prefix_does_not_match_another_version(self):
        self.assertEqual(planner.plan('1.2.3', [], [ref('1.2.30', 50)], [])['release'], 1)

    def test_legacy_distribution_suffix_counted(self):
        self.assertEqual(planner.plan('1.2.3', [], [], [build('1.2.3', '8.el10')], manual=True)['release'], 9)
        self.assertEqual(planner.revision_from_rpm('1.2.3', 'spotify-1.2.3-12.fc44.x86_64.rpm'), 12)

    def test_rpm_name_and_git_tag_use_safe_prefix(self):
        self.assertEqual(planner.revision_from_rpm('1.2.3', 'spot-fly-light-1.2.3-7.fc44.x86_64.rpm'), 7)
        self.assertIsNone(planner.revision_from_rpm('1.2.3', 'spotXXflyYYlight-1.2.3-7.fc44.x86_64.rpm'))
        tag = planner.plan('1.2.3', [], [], [])['tag']
        self.assertEqual(tag, 'spot-fly-light-v1.2.3-1')
        subprocess.run(['git', 'check-ref-format', 'refs/tags/' + tag], check=True)

    def test_unrelated_copr_package_not_counted(self):
        self.assertEqual(planner.plan('1.2.3', [], [], [build('1.2.3', 8, name='other')])['release'], 1)

    def test_signature_ignores_volatile_mirror_checks_but_includes_both_debs(self):
        records = {'stable': {'RPMVersion': '1', 'SHA256': 'a'}, 'unstable': {'RPMVersion': '2', 'SHA256': 'b'}}
        signature = planner.source_signature(records)
        records['stable']['RPMFusionChecks'] = ['transient result']
        self.assertEqual(planner.source_signature(records), signature)
        records['unstable']['SHA256'] = 'c'
        self.assertNotEqual(planner.source_signature(records), signature)

    def test_unstable_counter_resets_on_new_upstream_version(self):
        refs = [dict(ref('1.2.3', 4), reservation={'channels': {'stable': {'version':'1.2.3','release':4}, 'unstable': {'version': '2.0', 'release': 9}}})]
        self.assertEqual(planner.channel_release('unstable', '2.0', refs, 5, [build('1.2.3',4)]), 10)
        self.assertEqual(planner.channel_release('unstable', '2.1', refs, 5, [build('1.2.3',4)]), 1)

    def test_failed_reservation_keeps_first_unstable_client_at_one(self):
        refs = [dict(ref('1.2.3', 4), reservation={'channels': {
            'stable': {'version':'1.2.3','release':4},
            'unstable': {'version':'2.0','release':1}}})]
        self.assertEqual(planner.channel_release('unstable','2.0',refs,5,[build('1.2.3',4,'failed')]),1)
        self.assertEqual(planner.channel_release('unstable','2.0',refs,5,[build('1.2.3',4)]),2)


class ReservationTests(unittest.TestCase):
    def test_collision_gets_next_number_and_preserves_source_manifest(self):
        class API:
            def __init__(self): self.calls = []
            def call(self, path, data=None):
                self.calls.append((path, data))
                if path == '/git/tags': return {'sha': 'b' * 40}
                if data and data['ref'].endswith('-4'):
                    raise HTTPError('https://api.github.com', 422, 'exists', {}, io.BytesIO())
                return {}
        api = API()
        result = planner.reserve(api, '1.2.3', 4, 'a' * 40, {'signature': 'pins'})
        self.assertEqual(result, (5, 'spot-fly-light-v1.2.3-5'))
        self.assertEqual([c[0] for c in api.calls], ['/git/tags', '/git/refs', '/git/ref/tags/spot-fly-light-v1.2.3-4', '/git/tags', '/git/refs'])
        self.assertEqual(api.calls[0][1]['object'], 'a' * 40)
        self.assertIn('"signature": "pins"', api.calls[0][1]['message'])

    def test_permission_failure_is_not_collision(self):
        class API:
            def call(self, path, data=None):
                raise HTTPError('https://api.github.com', 403, 'forbidden', {}, io.BytesIO())
        with self.assertRaises(HTTPError): planner.reserve(API(), '1.2.3', 1, 'a' * 40)

    def test_reads_legacy_and_current_annotated_reservations_without_rewriting(self):
        api = planner.GitHub('owner/repository', '')
        calls = []
        def call(path, data=None):
            self.assertIsNone(data)
            calls.append(path)
            if path == '/git/matching-refs/tags/':
                return [{'ref': 'refs/tags/' + name, 'object': {'type': 'tag', 'sha': sha}}
                        for name, sha in [('sonicradle-v1.2.3-6', 'old'), ('spot-fly-light-v1.2.3-7', 'new')]]
            return {'message': '{"channels":{"unstable":{"version":"2.0","release":1}}}'}
        api.call = call
        records = api.reservations()
        self.assertEqual(calls, ['/git/matching-refs/tags/', '/git/tags/old', '/git/tags/new'])
        self.assertEqual(records[0]['reservation']['channels']['unstable']['release'], 1)

    def test_secret_errors_do_not_echo_value(self):
        with self.assertRaises(ValueError) as raised:
            planner.require_copr_config('highly-private-malformed-secret')
        self.assertNotIn('highly-private', str(raised.exception))


class SpecReleaseTests(unittest.TestCase):
    def test_reserved_number_used_in_legacy_local_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'spotify.spec'
            subprocess.run(['bash', str(REPO / 'src/generate_spec.sh'), str(output), '1.2.3'],
                           env=dict(os.environ, BUILTIN_FFMPEG='false', SPOTIFY_RELEASE='7'), check=True)
            text = output.read_text()
            self.assertIn('Release:        7%{?dist}', text)
            self.assertIn('1.2.3-7\n', text)

    def test_invalid_release_rejected(self):
        for number in ('0', '-1', '1.2', '1\nName: injected'):
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'spotify.spec'
                result = subprocess.run(['bash', str(REPO / 'src/generate_spec.sh'), str(output), '1.2.3'],
                                        env=dict(os.environ, BUILTIN_FFMPEG='false', SPOTIFY_RELEASE=number), capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
