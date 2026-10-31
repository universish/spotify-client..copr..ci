import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fallback_client',ROOT/'bootstrap/spot..fly..light.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


class DownloadFallbackTests(unittest.TestCase):
    def test_fourth_source_is_used_only_after_all_official_sources_fail(self):
        contents=b'original-source-bytes'
        record={'Filename':'pool/non-free/s/spotify-client/spotify-client_1.2.3_amd64.deb',
                'SHA256':hashlib.sha256(contents).hexdigest(),'Size':len(contents)}
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'source.deb'
            with patch.dict(os.environ,{},clear=True),patch.object(client,'urlopen',side_effect=[URLError('offline')]*3+[io.BytesIO(contents)]) as fetch:
                client.download(record,dest)
            self.assertEqual([c.args[0] for c in fetch.call_args_list],[base+'/'+record['Filename'] for base in (
                'https://download.spotify.com/debian','https://repository.spotify.com','https://repository-origin.spotify.com','https://deb.rug.nl/ppa/mirror/repository.spotify.com')])
            self.assertEqual(dest.read_bytes(),contents)

    def test_mirror_cannot_substitute_different_bytes_for_official_hash(self):
        record={'Filename':'pool/non-free/s/spotify-client/spotify-client_1.2.3_amd64.deb',
                'SHA256':hashlib.sha256(b'original').hexdigest(),'Size':len(b'original')}
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'source.deb'
            with patch.dict(os.environ,{},clear=True),patch.object(client,'urlopen',side_effect=[URLError('offline')]*3+[io.BytesIO(b'modified')]):
                with self.assertRaises(RuntimeError):client.download(record,dest)
            self.assertFalse(dest.exists())
