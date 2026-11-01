import importlib.util
import base64
from datetime import datetime, timezone
from email.utils import format_datetime
import gzip
import hashlib
import io
from pathlib import Path
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("spotify_sources", Path(__file__).resolve().parents[1] / "src/parser_debian_control_file.py")
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)

INDEX = b"Package: spotify-client\nArchitecture: amd64\nVersion: 1:1.2.3.4.g123456789-1\nFilename: pool/non-free/s/spotify-client/spotify-client_1.2.3.4.g123456789-1_amd64.deb\nSize: 123\nSHA256: " + b"a" * 64 + b"\n"


def evidence(index=INDEX, repository='spotify-download', distribution='stable'):
    # Pure envelope fixture only. Real signatures and key policy are tested in test_source_auth.
    info = sources.source_auth.source(repository)
    path = info['distributions'][distribution]['index_path']
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    release = f"Suite: {distribution}\nDate: {format_datetime(stamp)}\nSHA256:\n {hashlib.sha256(index).hexdigest()} {len(index)} {path}\n".encode()
    return {'Schema': 1, 'Type': 'spotify-openpgp', 'Publisher': info['owner'],
            'RepositoryID': repository, 'Distribution': distribution, 'Fingerprint': info['fingerprint'],
            'ReleaseDate': stamp.isoformat(), 'ReleaseSHA256': hashlib.sha256(release).hexdigest(),
            'ValidUntil': None, 'IndexPath': path, 'IndexSHA256': hashlib.sha256(index).hexdigest(),
            'IndexSize': len(index), 'Evidence': {'Packages': base64.b64encode(index).decode(),
            'Release': base64.b64encode(release).decode(), 'Signature': base64.b64encode(b'unit fixture only').decode()}}


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.audit = mock.patch.object(sources, 'check_rpmfusion', return_value=[])
        self.audit.start()
        self.addCleanup(self.audit.stop)

    def test_download_spotify_is_checked_first_and_preserves_raw_version(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', return_value=(INDEX, evidence())) as fetch:
            result = sources.fetch_package('stable')
        self.assertEqual(fetch.call_args.args, ('spotify-download', 'stable'))
        self.assertEqual(result['RepositoryURL'], 'https://download.spotify.com/debian')
        self.assertEqual(result['Version'], '1:1.2.3.4.g123456789-1')
        self.assertEqual(result['DebianVersion'], result['Version'])
        self.assertEqual(result['RPMVersion'], '1.2.3.4.g123456789.deb1')
        self.assertEqual(result['NumericVersion'], '1.2.3.4')

    def test_missing_primary_source_uses_next_signed_source(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=[
                sources.source_auth.SourceUnavailable('offline'), (INDEX, evidence(repository='spotify-repository'))]) as fetch:
            result = sources.fetch_package()
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result['RepositoryURL'], 'https://repository.spotify.com')

    def test_origin_is_third_official_metadata_source(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=[
                sources.source_auth.SourceUnavailable('offline'), sources.source_auth.SourceUnavailable('offline'),
                (INDEX, evidence(repository='spotify-origin'))]) as fetch:
            result = sources.fetch_package()
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(result['DownloadBaseURLs'][-1], 'https://deb.rug.nl/ppa/mirror/repository.spotify.com')
        self.assertNotIn('https://ftp.sh.cvut.cz/mint', result['DownloadBaseURLs'])

    def test_community_mirror_never_supplies_metadata(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=sources.source_auth.SourceUnavailable('offline')) as fetch:
            with self.assertRaises(RuntimeError): sources.fetch_package()
        self.assertEqual(fetch.call_count, 3)
        self.assertTrue(all(c.args[0].startswith('spotify-') for c in fetch.call_args_list))

    def test_bad_signature_is_fatal_without_mirror_downgrade(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=sources.source_auth.AuthenticationError('bad signature')) as fetch:
            with self.assertRaises(sources.source_auth.AuthenticationError): sources.fetch_package()
        self.assertEqual(fetch.call_count, 1)

    def test_rollback_can_try_a_newer_official_transport(self):
        state = {'spotify-repository:stable': {'ReleaseDate': '2026-01-01T00:00:00+00:00'}}
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=[
                sources.source_auth.MetadataRollback('old mirror'), (INDEX, evidence(repository='spotify-repository'))]) as fetch:
            sources.fetch_package(accepted_state=state)
        self.assertEqual(fetch.call_args.kwargs['accepted_state'], state)

    def test_unstable_uses_testing_and_default_stable(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', return_value=(INDEX, evidence(distribution='testing'))) as fetch:
            result = sources.fetch_package('unstable')
        self.assertEqual(fetch.call_args.args, ('spotify-download', 'testing'))
        self.assertEqual(result['Channel'], 'unstable')
        with mock.patch.object(sources.source_auth, 'verify_repository', return_value=(INDEX, evidence())):
            self.assertEqual(sources.fetch_package()['Channel'], 'stable')

    def test_unknown_channel_never_fetches(self):
        with mock.patch.object(sources.source_auth, 'verify_repository') as fetch:
            with self.assertRaises(ValueError): sources.fetch_package('pool')
        fetch.assert_not_called()

    def test_missing_size_and_traversal_are_rejected(self):
        for data in (INDEX.replace(b'Size: 123\n', b''), INDEX.replace(b'pool/non-free/s/spotify-client/', b'../../')):
            with self.subTest(data=data), mock.patch.object(sources.source_auth, 'verify_repository', return_value=(data, evidence(data))):
                with self.assertRaises(sources.source_auth.AuthenticationError): sources.fetch_package()

    def test_short_and_full_requested_versions_match_epoch_revision(self):
        for requested in ('1.2.3.4', '1.2.3.4.g123456789', '1:1.2.3.4.g123456789-1'):
            self.assertTrue(sources.matches_requested_version('1:1.2.3.4.g123456789-1', requested))
        self.assertFalse(sources.matches_requested_version('1:1.2.3.4.g123456789-1', '1.2.3.5'))

    def test_ambiguous_requested_version_fails(self):
        data = INDEX + b'\n' + INDEX.replace(b'g123456789', b'g987654321')
        with mock.patch.object(sources.source_auth, 'verify_repository', return_value=(data, evidence(data))):
            with self.assertRaises(sources.AmbiguousVersionError): sources.fetch_package(requested_version='1.2.3.4')

    def test_rpmfusion_last_and_never_replaces_authority(self):
        events = []
        def official(*args, **kwargs):
            events.append('official'); return INDEX, evidence()
        def audit():
            events.append('rpmfusion'); return [{'packages': [{'version': '99'}]}]
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=official), mock.patch.object(sources, 'check_rpmfusion', side_effect=audit):
            result = sources.fetch_package()
        self.assertEqual(events, ['official', 'rpmfusion'])
        self.assertEqual(result['NumericVersion'], '1.2.3.4')

    def test_missing_official_sources_are_failure_not_unchanged(self):
        with mock.patch.object(sources.source_auth, 'verify_repository', side_effect=sources.source_auth.SourceUnavailable('offline')):
            with self.assertRaisesRegex(RuntimeError, 'cannot establish the DEB channel/checksum'): sources.fetch_package()

    def test_archive_capture_cannot_change_the_registered_original(self):
        expected = 'https://repository.spotify.com/dists/stable/InRelease'
        self.assertEqual(sources._snapshot_url('https://web.archive.org/web/20261031000000id_/' + expected, expected), {'web.archive.org'})
        for url in ('https://attacker.invalid/x', 'https://web.archive.org/web/20261031000000id_/https://attacker.invalid/x'):
            with self.assertRaises(sources.source_auth.AuthenticationError): sources._snapshot_url(url, expected)


class RPMFusionTests(unittest.TestCase):
    def fixture(self, digest=None, href="repodata/primary.xml.gz"):
        data = gzip.compress(b'''<metadata xmlns="http://linux.duke.edu/metadata/common"><package type="rpm"><name>lpf-spotify-client</name><arch>x86_64</arch><version epoch="0" ver="1.3.4.258" rel="1.fc44"/></package><package type="rpm"><name>unrelated</name></package></metadata>''')
        checksum = digest or hashlib.sha256(data).hexdigest()
        index = f'<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><checksum type="sha256">{checksum}</checksum><location href="{href}"/></data></repomd>'.encode()
        return index, data

    def test_reads_bootstrap_version_without_fetching_any_rpm(self):
        index, primary = self.fixture()
        with mock.patch.object(sources.request, "urlopen", side_effect=[io.BytesIO(index), io.BytesIO(primary)]) as fetch:
            result = sources._rpmfusion_check(sources.RPMFUSION_PATHS[1])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["packages"], [{"name": "lpf-spotify-client", "version": "1.3.4.258", "release": "1.fc44", "architecture": "x86_64"}])
        self.assertTrue(all("repodata/" in call.args[0] for call in fetch.call_args_list))

    def test_altered_primary_metadata_is_rejected(self):
        index, primary = self.fixture(digest="0" * 64)
        with mock.patch.object(sources.request, "urlopen", side_effect=[io.BytesIO(index), io.BytesIO(primary)]):
            result = sources._rpmfusion_check(sources.RPMFUSION_PATHS[1])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["packages"], [])

    def test_external_or_traversal_primary_location_is_rejected(self):
        for href in ("https://attacker.invalid/primary.xml.gz", "repodata/../../primary.xml.gz"):
            index, _ = self.fixture(href=href)
            with mock.patch.object(sources.request, "urlopen", return_value=io.BytesIO(index)) as fetch:
                result = sources._rpmfusion_check(sources.RPMFUSION_PATHS[1])
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
