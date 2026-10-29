import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap_client', ROOT / 'bootstrap/spotify.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class BootstrapTests(unittest.TestCase):
    def record(self, contents=b'fixture'):
        return dict(Package='spotify-client', Architecture='amd64', RPMVersion='1.2.3',
                    Filename='pool/non-free/s/spotify-client/spotify-client_1.2.3_amd64.deb',
                    SHA256=hashlib.sha256(contents).hexdigest(), Size=len(contents))

    def test_terms_review_does_not_download_or_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'eula.txt').write_text('Terms fixture')
            with patch.object(client, 'HERE', path), patch.object(client.shutil, 'which', return_value=None), patch.object(client, 'download') as download:
                with self.assertRaisesRegex(SystemExit, 'accept-spotify-terms'):
                    client.setup(['--setup'])
                download.assert_not_called()

    def test_root_cannot_run_download_or_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'eula.txt').write_text('Terms fixture')
            with patch.object(client, 'HERE', path), patch.object(os, 'geteuid', return_value=0), patch.object(client, 'download') as download:
                with self.assertRaisesRegex(SystemExit, 'regular user'):
                    client.setup(['--setup', '--accept-spotify-terms'])
                download.assert_not_called()

    def test_tampered_cached_deb_stops_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            cached, output = Path(tmp) / 'cached.deb', Path(tmp) / 'download.deb'
            cached.write_bytes(b'tampered')
            with patch.dict(os.environ, SPOTIFY_DEB_FILE=str(cached)), patch.object(client, 'urlopen') as network:
                with self.assertRaisesRegex(ValueError, 'mismatch'):
                    client.download(self.record(), output)
                network.assert_not_called()
                self.assertFalse(output.exists())

    def test_metadata_cannot_redirect_to_untrusted_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.json'
            record = self.record()
            record['Filename'] = 'https://untrusted.invalid/payload.deb'
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                client.metadata(path)

    def test_local_spec_keeps_integrity_and_runtime_dependencies(self):
        text = client.target_spec('1.2.3', 4, '2.39')
        self.assertIn('Name: spotify-client-local', text)
        self.assertIn('Release: 4', text)
        self.assertIn('Requires: spotify', text)
        self.assertIn('Requires: glibc >= 2.39', text)
        self.assertIn('sha256sum --quiet -c .vendor-files.sha256', text)
        self.assertNotIn('%post\n', text)


    def test_gui_decline_removes_only_our_local_target_and_clears_consent(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'eula.txt').write_text('Terms fixture')
            (path / 'consent.json').write_text('{}')
            calls = [SimpleNamespace(returncode=1), SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
            with patch.object(client, 'HERE', path), patch.object(client, 'state_dir', return_value=path), patch.dict(os.environ, DISPLAY=':test'), patch.object(client.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), patch.object(client.subprocess, 'run', side_effect=calls) as run:
                with self.assertRaisesRegex(SystemExit, 'Consent declined'):
                    client.consent([])
                self.assertEqual(run.call_args_list[-1].args[0], ['pkexec', '/usr/bin/rpm', '-e', 'spotify-client-local'])
                self.assertFalse((path / 'consent.json').exists())

    def test_failed_removal_does_not_keep_a_prior_acceptance(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'consent.json').write_text('{}')
            with patch.object(client, 'state_dir', return_value=path), patch.object(client.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name), patch.object(client.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]):
                with self.assertRaisesRegex(SystemExit, 'will not launch'):
                    client.revoke_local_client()
                self.assertFalse((path / 'consent.json').exists())
