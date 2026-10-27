import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("spotify_sources", Path(__file__).resolve().parents[1] / "src/parser_debian_control_file.py")
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)

INDEX = b"Package: spotify-client\nArchitecture: amd64\nVersion: 1:1.2.3\nSHA256: " + b"a" * 64 + b"\n"


class SourceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
