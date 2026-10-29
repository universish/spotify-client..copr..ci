import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class CachedDebTests(unittest.TestCase):
    def download_cached(self, good):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = root / "lpf.deb"
            cached.write_bytes(b"cached-deb-fixture")
            metadata = {"Package": "spotify-client", "Architecture": "amd64", "RPMVersion": "1.2.3",
                        "Filename": "pool/non-free/s/spotify-client/spotify-client_1.2.3_amd64.deb",
                        "SHA256": hashlib.sha256(cached.read_bytes()).hexdigest() if good else "0" * 64,
                        "Size": cached.stat().st_size}
            (root / "spotify-client.stable.json").write_text(json.dumps(metadata))
            output = root / "downloads"
            result = subprocess.run(["bash", str(REPO / "src/download_spotify.sh"), "stable", "1.2.3"],
                                    env=dict(os.environ, SOURCE="deb", SPOTIFY_METADATA_DIR=str(root),
                                             SPOTIFY_DOWNLOAD_DIR=str(output), SPOTIFY_DEB_FILE=str(cached)),
                                    capture_output=True, text=True)
            if good:
                self.assertEqual((output / "spotify-client_1.2.3_amd64.deb").read_bytes(), cached.read_bytes())
            else:
                self.assertEqual(list(output.iterdir()), [])
            return result

    def test_lpf_cache_is_verified_without_network_download(self):
        result = self.download_cached(True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified cached DEB", result.stdout)

    def test_wrong_cached_checksum_stops_before_extraction(self):
        result = self.download_cached(False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum/size mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
