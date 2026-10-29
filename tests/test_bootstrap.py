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

    def test_dialog_failure_is_not_a_rejection_and_never_removes_package(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'eula.txt').write_text('Terms fixture')
            with patch.object(client, 'HERE', path), patch.dict(os.environ, DISPLAY=':test'), patch.object(client.shutil, 'which', return_value='/usr/bin/zenity'), patch.object(client.subprocess, 'run', return_value=SimpleNamespace(returncode=255)), patch.object(client, 'revoke_local_client') as remove:
                with self.assertRaisesRegex(SystemExit, 'dialog failed'):
                    client.consent([])
                remove.assert_not_called()

    def test_consent_is_bound_to_selected_version_and_packaging_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'eula.txt').write_text('Terms fixture')
            record = self.record()
            record['PackagingRelease'] = 4
            (path / 'source.json').write_text(json.dumps(record))
            with patch.object(client, 'HERE', path), patch.object(client, 'state_dir', return_value=path):
                client.consent(['--accept-spotify-terms'])
                self.assertTrue(client.has_consent())
                record['PackagingRelease'] = 5
                (path / 'source.json').write_text(json.dumps(record))
                self.assertFalse(client.has_consent())
                record['PackagingRelease'] = 4
                record['RPMVersion'] = '1.2.4'
                record['Filename'] = 'pool/non-free/s/spotify-client/spotify-client_1.2.4_amd64.deb'
                (path / 'source.json').write_text(json.dumps(record))
                self.assertFalse(client.has_consent())

    def test_old_notice_only_consent_does_not_authorize_new_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'eula.txt').write_text('Terms fixture')
            (path / 'source.json').write_text(json.dumps(self.record()))
            with patch.object(client, 'HERE', path), patch.object(client, 'state_dir', return_value=path):
                (path / 'consent.json').write_text(json.dumps({'notice_sha256':client.consent_digest()}))
                self.assertFalse(client.has_consent())

    def test_installed_client_requires_correct_version_and_at_least_bootstrap_revision(self):
        from types import SimpleNamespace
        expected = {'version':'1.2.3','release':'4','deb_sha256':'0'*64}
        with patch.object(client, 'approval_subject', return_value=expected):
            for version, release, result in [('1.2.2','9',False), ('1.2.3','3',False), ('1.2.3','4',True), ('1.2.3','5.fc44',True)]:
                with self.subTest(version=version,release=release), patch.object(client.subprocess, 'run', return_value=SimpleNamespace(returncode=0,stdout=version+'\n'+release+'\n')):
                    self.assertEqual(client.installed_current(),result)

    def test_outdated_client_is_never_launched(self):
        with patch.object(client,'has_consent',return_value=True), patch.object(client,'installed_current',return_value=False), patch.object(os,'execve') as execute:
            with self.assertRaisesRegex(SystemExit,'missing or outdated'):
                client.launch([])
            execute.assert_not_called()

    def test_invalid_consent_record_is_unapproved_not_a_launcher_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with patch.object(client,'state_dir',return_value=path):
                for contents in ('[]', 'null', '"wrong"', '{broken'):
                    with self.subTest(contents=contents):
                        (path/'consent.json').write_text(contents)
                        self.assertFalse(client.has_consent())

    def test_pending_rpm_is_bound_to_identity_hash_and_source_context(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/'1.2.3';folder.mkdir()
            rpm=folder/'spotify-client-local-1.2.3-4.x86_64.rpm';rpm.write_bytes(b'fixture-rpm')
            subject={'version':'1.2.3','release':'4','deb_sha256':'1'*64}
            with patch.object(client,'state_dir',return_value=root), patch.object(client,'approval_subject',return_value=subject), patch.object(client.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='spotify-client-local\n1.2.3\n4\n')):
                client.remember_pending(rpm)
                self.assertEqual(client.pending_install(),(rpm,4))
                rpm.write_bytes(b'changed-after-build')
                self.assertIsNone(client.pending_install())

    def test_pending_record_cannot_escape_version_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'1.2.3';folder.mkdir()
            subject={'version':'1.2.3','release':'4','deb_sha256':'1'*64}
            (folder/'pending-install.json').write_text(json.dumps({'package':subject,'filename':'../../outside.rpm','SHA256':'0'*64,'Size':1}))
            with patch.object(client,'state_dir',return_value=root), patch.object(client,'approval_subject',return_value=subject):
                self.assertIsNone(client.pending_install())

    def test_install_retry_does_not_repeat_download_scan_or_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pending=root/'ready.rpm'
            with patch.object(os,'geteuid',return_value=1000), patch.object(client,'consent'), patch.object(client,'metadata',return_value={'RPMVersion':'1.2.3'}), patch.object(client,'state_dir',return_value=root), patch.object(client.shutil,'which',return_value='/stub/tool'), patch.object(client,'pending_install',return_value=(pending,4)), patch.object(client,'install_local') as install, patch.object(client,'download') as download, patch.object(client.subprocess,'run') as run:
                client.setup(['--install','--accept-spotify-terms'])
                install.assert_called_once_with(pending)
                download.assert_not_called()
                run.assert_not_called()

    def test_state_reports_waiting_install_for_newer_cached_local_revision(self):
        with patch.object(client,'has_consent',return_value=True), patch.object(client,'pending_install',return_value=(Path('/fixture.rpm'),5)), patch.object(client,'installed_current',return_value=False):
            self.assertEqual(client.package_state(),'install-wait')
