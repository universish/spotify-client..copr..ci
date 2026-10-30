import importlib.util
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

INDEX = b"Package: spotify-client\nArchitecture: amd64\nVersion: 1:1.2.3\nFilename: pool/non-free/s/spotify-client/spotify-client_1.2.3_amd64.deb\nSize: 123\nSHA256: " + b"a" * 64 + b"\n"


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.audit = mock.patch.object(sources, "check_rpmfusion", return_value=[])
        self.audit.start()
        self.addCleanup(self.audit.stop)

    def test_download_spotify_is_checked_first(self):
        with mock.patch.object(sources.request, "urlopen", return_value=io.BytesIO(INDEX)) as fetch:
            result = sources.fetch_package("stable")
        self.assertTrue(fetch.call_args.args[0].startswith("https://download.spotify.com/debian/dists/"))
        self.assertEqual(result["RepositoryURL"], "https://download.spotify.com/debian")

    def test_missing_primary_index_falls_back_to_working_package_index(self):
        failure = HTTPError("https://download.spotify.com/debian/dists/stable/", 404, "missing", {}, io.BytesIO())
        with mock.patch.object(sources.request, "urlopen", side_effect=[failure, io.BytesIO(INDEX)]) as fetch:
            result = sources.fetch_package("stable")
        self.assertEqual(fetch.call_count, 2)
        self.assertTrue(fetch.call_args.args[0].endswith("/dists/stable/non-free/binary-amd64/Packages"))
        self.assertEqual(result["RepositoryURL"], "https://repository.spotify.com")

    def test_unusable_official_sources_fail_instead_of_claiming_unchanged(self):
        with mock.patch.object(sources.request, "urlopen", side_effect=URLError("offline")):
            with self.assertRaises(RuntimeError):
                sources.fetch_package("stable")

    def test_unstable_uses_official_testing_index(self):
        with mock.patch.object(sources.request, "urlopen", return_value=io.BytesIO(INDEX)) as fetch:
            result = sources.fetch_package("unstable")
        self.assertIn("/dists/testing/", fetch.call_args.args[0])
        self.assertEqual(result["Channel"], "unstable")
        self.assertEqual(result["Distribution"], "testing")

    def test_default_channel_is_stable(self):
        with mock.patch.object(sources.request, "urlopen", return_value=io.BytesIO(INDEX)):
            self.assertEqual(sources.fetch_package()["Channel"], "stable")

    def test_unknown_channel_does_not_touch_network(self):
        with mock.patch.object(sources.request, "urlopen") as fetch:
            with self.assertRaises(ValueError):
                sources.fetch_package("pool")
        fetch.assert_not_called()

    def test_integrity_metadata_is_required_before_a_record_can_be_used(self):
        for text in (INDEX.replace(b"Size: 123\n", b""), INDEX.replace(b"pool/non-free/s/spotify-client/", b"../../")):
            with self.subTest(text=text):
                with mock.patch.object(sources.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(text)):
                    with self.assertRaises(RuntimeError):
                        sources.fetch_package()

    def test_rpmfusion_is_checked_after_official_discovery(self):
        events = []
        def official(*args, **kwargs):
            events.append("official")
            return io.BytesIO(INDEX)
        def audit():
            events.append("rpmfusion")
            return [{"repository": "fedora-44-updates", "packages": [{"version": "99.0"}]}]
        with mock.patch.object(sources.request, "urlopen", side_effect=official), mock.patch.object(sources, "check_rpmfusion", side_effect=audit):
            record = sources.fetch_package()
        self.assertEqual(events, ["official", "rpmfusion"])
        self.assertEqual(record["RPMVersion"], "1.2.3")
        self.assertEqual(record["Channel"], "stable")

    def test_rpmfusion_candidate_cannot_replace_missing_official_checksum(self):
        with mock.patch.object(sources.request, "urlopen", side_effect=URLError("offline")), mock.patch.object(sources, "check_rpmfusion", return_value=[{"packages": [{"version": "99"}]}]) as audit:
            with self.assertRaisesRegex(RuntimeError, "cannot establish the DEB channel/checksum"):
                sources.fetch_package()
        audit.assert_called_once()


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
