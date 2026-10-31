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
spec = importlib.util.spec_from_file_location('bootstrap_client', ROOT / 'bootstrap/spot..fly..light.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(client, 'migration_preflight', return_value=None).start()
        patch.object(client, 'previous_named_target', return_value=None).start()

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
            with patch.dict(os.environ, SPOT_FLY_LIGHT_DEB_FILE=str(cached)), patch.object(client, 'urlopen') as network:
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
        self.assertIn('Name: spot-fly-light-client-local', text)
        self.assertIn('Release: 4', text)
        self.assertIn('Requires: spot-fly-light', text)
        self.assertNotIn('sonicradle', text)
        self.assertNotIn('Obsoletes: spotify', text)
        self.assertIn('__provides_exclude_from ^%{_datadir}/spot[.][.]fly[.][.]light-client/', text)
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
                self.assertEqual(run.call_args_list[-1].args[0], ['pkexec', '/usr/bin/rpm', '-e', 'spot-fly-light-client-local'])
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
        with patch.object(client, 'approval_subject', return_value=expected), patch.object(client, 'installed_source', return_value={'Channel':'stable', 'SHA256':'0'*64}):
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
            rpm=folder/'spot-fly-light-client-local-1.2.3-4.x86_64.rpm';rpm.write_bytes(b'fixture-rpm')
            subject={'version':'1.2.3','release':'4','deb_sha256':'1'*64}
            with patch.object(client,'state_dir',return_value=root), patch.object(client,'approval_subject',return_value=subject), patch.object(client.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='spot-fly-light-client-local\n1.2.3\n4\n')):
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
            with patch.object(os,'geteuid',return_value=1000), patch.object(client,'consent'), patch.object(client,'metadata',return_value={'RPMVersion':'1.2.3'}), patch.object(client,'validate_scan'), patch.object(client,'state_dir',return_value=root), patch.object(client.shutil,'which',return_value='/stub/tool'), patch.object(client,'pending_install',return_value=(pending,4)), patch.object(client,'installed_current',return_value=False), patch.object(client,'install_local') as install, patch.object(client,'download') as download, patch.object(client.subprocess,'run') as run:
                client.setup(['--install','--accept-spotify-terms'])
                install.assert_called_once_with(pending)
                download.assert_not_called()
                run.assert_not_called()

    def test_state_reports_waiting_install_for_newer_cached_local_revision(self):
        with patch.object(client,'has_consent',return_value=True), patch.object(client,'pending_install',return_value=(Path('/fixture.rpm'),5)), patch.object(client,'installed_current',return_value=False):
            self.assertEqual(client.package_state(),'install-wait')


class ChannelAndCIScanTests(unittest.TestCase):
    def setUp(self):
        self.previous_channel = client.CURRENT_CHANNEL
        client.CURRENT_CHANNEL = 'stable'

    def tearDown(self):
        client.CURRENT_CHANNEL = self.previous_channel

    def record(self, channel, version='1.2.3'):
        return dict(Package='spotify-client', Architecture='amd64', RPMVersion=version,
                    Channel=channel, Filename=f'pool/non-free/s/spotify-client/spotify-client_{version}_amd64.deb',
                    SHA256='a'*64, Size=10)

    def test_default_and_explicit_unstable_select_one_channel(self):
        self.assertEqual(client.channel_option(['--setup']), 'stable')
        self.assertEqual(client.channel_option(['--update']), 'stable')
        self.assertEqual(client.channel_option(['--setup', '-unstable']), 'unstable')
        self.assertEqual(client.channel_option(['--update', '-unstable']), 'unstable')

    def test_catalog_never_promotes_unstable_record_into_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.json'
            catalog={'stable':self.record('stable'), 'unstable':self.record('unstable','1.3.4')}
            path.write_text(json.dumps(catalog))
            self.assertEqual(client.metadata(path)['RPMVersion'], '1.2.3')
            self.assertEqual(client.metadata(path, 'unstable')['RPMVersion'], '1.3.4')
            catalog['stable']=catalog['unstable'];path.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(ValueError, 'requested channel'):
                client.metadata(path)

    def test_successful_scan_evidence_must_match_download_hash(self):
        record=self.record('stable')
        with self.assertRaisesRegex(ValueError, 'CI scan evidence'):
            client.validate_scan(record)
        record['ScanAttestation']={'SHA256':'a'*64, 'Malware':'clean','PUA':'advisory',
            'RunURL':'https://github.com/universish/spotify-client..copr..ci/actions/runs/123',
            'ScannedAt':'2026-10-30T00:00:00+00:00', 'Scanner':'ClamAV','DatabaseVersion':'ClamAV 1.4/123/Oct30'}
        client.validate_scan(record)
        for field,value in [('SHA256','b'*64),('Malware','infected'),('PUA','blocked'),('RunURL','https://untrusted.invalid/run')]:
            original=record['ScanAttestation'][field]
            record['ScanAttestation'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                client.validate_scan(record)
            record['ScanAttestation'][field]=original

    def test_channels_replace_one_identically_named_local_rpm(self):
        stable=client.target_spec('1.2.3',1,'2.39')
        unstable=client.target_spec('1.3.4',1,'2.39')
        for spec in (stable,unstable):
            self.assertIn('Name: spot-fly-light-client-local\n',spec)
            self.assertNotIn('Name: spot-fly-light-client-local-unstable',spec)
            self.assertNotIn('Provides: spotify-client',spec)

    def test_local_setup_contains_no_clamav_install_or_scan(self):
        import inspect
        source=inspect.getsource(client.setup)
        self.assertNotIn('freshclam',source)
        self.assertNotIn('clamscan',source)
        self.assertNotIn('scan_payload',source)
        self.assertIn('validate_scan(record)',source)


class LocalTransactionTests(unittest.TestCase):
    def test_downgrade_and_upgrade_use_native_rpm_ordering(self):
        from types import SimpleNamespace
        for comparison, expected in [('-1', 'downgrade'),('1','install'),('0','reinstall')]:
            results=[SimpleNamespace(stdout='spot-fly-light-client-local\n1.2.95-1\n'),
                     SimpleNamespace(returncode=0,stdout='1.3.4-1'),SimpleNamespace(stdout=comparison)]
            with self.subTest(comparison=comparison),patch.object(client.subprocess,'run',side_effect=results):
                self.assertEqual(client.transaction_action(Path('/client.rpm')),expected)

    def test_dnf_channel_downgrade_is_explicit(self):
        with patch.object(client,'previous_named_target',return_value=None),patch.object(client,'migration_preflight',return_value=None),patch.object(client,'ensure_client_closed'),patch.object(client,'transaction_action',return_value='downgrade'),patch.object(client.shutil,'which',side_effect=lambda tool:'/usr/bin/'+tool),patch.object(client.subprocess,'run') as run:
            client.install_local(Path('/client.rpm'))
            run.assert_called_once_with(['pkexec','/usr/bin/dnf','downgrade','-y','/client.rpm'],check=True)


class RunningAndPendingTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(client, 'migration_preflight', return_value=None).start()

    def test_current_cached_rpm_does_not_reinstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(os,'geteuid',return_value=1000),patch.object(client,'consent'),patch.object(client,'metadata',return_value={'RPMVersion':'1.2.3'}),patch.object(client,'validate_scan'),patch.object(client,'state_dir',return_value=root),patch.object(client.shutil,'which',return_value='/stub/tool'),patch.object(client,'pending_install',return_value=(root/'ready.rpm',4)),patch.object(client,'installed_current',return_value=True),patch.object(client,'install_local') as install,patch.object(client,'download') as download:
                client.setup(['--update'])
                install.assert_not_called()
                download.assert_not_called()

    def test_running_client_prevents_replacement(self):
        with patch.object(client.Path,'glob',return_value=[Path('/proc/123/exe')]),patch.object(client.os,'readlink',return_value='/usr/share/spot..fly..light-client/spotify (deleted)'):
            with self.assertRaisesRegex(SystemExit,'Close all'):
                client.ensure_client_closed()


class RenamedClientMigrationTests(unittest.TestCase):
    def test_running_old_project_client_also_blocks_replacement(self):
        with patch.object(client.Path,'glob',return_value=[Path('/proc/123/exe')]),patch.object(client.os,'readlink',return_value='/usr/share/sonicradle-client/spotify'):
            with self.assertRaisesRegex(SystemExit,'Close all'):
                client.ensure_client_closed()

    def test_new_target_replaces_only_our_previous_target(self):
        text=client.target_spec('1.2.3',7,'2.39',previous_release='1.2.3-6')
        self.assertIn('Name: spot-fly-light-client-local',text)
        self.assertIn('Obsoletes: sonicradle-client-local = 1.2.3-6',text)
        self.assertNotIn('Obsoletes: spotify-client',text)
        self.assertIn('Conflicts: spotify-client, spotify-client-local',text)


class RenameConfigurationAndReleaseTests(unittest.TestCase):
    def test_legacy_configuration_is_read_only_fallback_per_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            legacy=root/'sonicradle';legacy.mkdir()
            (legacy/'flags.conf').write_text('--legacy-flag\n')
            (legacy/'environment.conf').write_text('GPU_SETTING=legacy\n')
            current=root/'spot..fly..light';current.mkdir()
            (current/'flags.conf').write_text('--current-flag\n')
            with patch.dict(os.environ,XDG_CONFIG_HOME=tmp):
                self.assertEqual(client.user_configuration(),(['--current-flag'],['GPU_SETTING=legacy']))
            self.assertEqual((legacy/'flags.conf').read_text(),'--legacy-flag\n')
            self.assertFalse((current/'environment.conf').exists())

    def test_rename_preserves_same_version_rebuild_counter_and_new_version_resets(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);legacy=root/'sonicradle-bootstrap/1.2.3';legacy.mkdir(parents=True)
            (legacy/'sonicradle-client-local-1.2.3-12.x86_64.rpm').touch()
            output=root/'current';output.mkdir()
            installed=[SimpleNamespace(returncode=1,stdout=''),SimpleNamespace(returncode=0,stdout='1.2.3\n15.fc44\n'),SimpleNamespace(returncode=1,stdout='')]
            with patch.dict(os.environ,XDG_STATE_HOME=tmp),patch.object(client.subprocess,'run',side_effect=installed):
                self.assertEqual(client.next_release({'RPMVersion':'1.2.3','PackagingRelease':7},output),16)
            with patch.dict(os.environ,XDG_STATE_HOME=tmp),patch.object(client.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='1.2.3\n15.fc44\n')):
                self.assertEqual(client.next_release({'RPMVersion':'1.2.4','PackagingRelease':1},output),1)


class LegacyGPUEnvironmentTests(unittest.TestCase):
    def test_legacy_gpu_settings_work_and_explicit_new_settings_win(self):
        with tempfile.TemporaryDirectory() as tmp:
            for current,expected in [(False,('nvidia','1')),(True,('software','0'))]:
                env={'LC_NUMERIC':'C','SONICRADLE_GPU_MODE':'nvidia','SONICRADLE_DEBUG':'1'}
                if current:
                    env.update(SPOT_FLY_LIGHT_GPU_MODE='software',SPOT_FLY_LIGHT_DEBUG='0')
                with self.subTest(current=current),patch.dict(os.environ,env,clear=True),patch.object(client,'active_channel',return_value='stable'),patch.object(client,'has_consent',return_value=True),patch.object(client,'installed_current',return_value=True),patch.object(client.Path,'is_file',return_value=True),patch.object(client,'user_configuration',return_value=([],[])),patch.object(client,'state_dir',return_value=Path(tmp)),patch.object(os,'execve') as execute:
                    client.launch([])
                    self.assertEqual(tuple(execute.call_args.args[1][3:5]),expected)


class OlderLocalPackageMigrationTests(unittest.TestCase):
    def replies(self, url='https://github.com/universish/spotify-client..copr..ci', owner='spotify-client-local'):
        from types import SimpleNamespace
        return [SimpleNamespace(returncode=1),
                SimpleNamespace(returncode=0,stdout='1.2.95-4\nhttps://www.spotify.com/download/linux/\nLocally built proprietary Spotify client\n'),
                SimpleNamespace(returncode=0,stdout=url),SimpleNamespace(returncode=0,stdout=owner)]

    def test_our_old_target_can_be_replaced_by_exact_installed_revision(self):
        with patch.object(client.subprocess,'run',side_effect=self.replies()):
            legacy=client.migration_preflight()
        spec=client.target_spec('1.2.95',9,'2.39',legacy)
        self.assertIn('Obsoletes: spotify-client-local = 1.2.95-4\n',spec)
        self.assertNotIn('Obsoletes: spotify-client\n',spec)
        self.assertNotIn('Obsoletes: spotify\n',spec)
        self.assertNotIn('Obsoletes: lpf-',spec)
        self.assertNotIn('Obsoletes: spotify-client-local',client.target_spec('1.2.95',9,'2.39'))

    def test_foreign_name_collision_is_never_replaced(self):
        for url,owner in [('https://example.org/another-project','spotify-client-local'),('https://github.com/universish/spotify-client..copr..ci','another-package')]:
            with self.subTest(url=url,owner=owner),patch.object(client.subprocess,'run',side_effect=self.replies(url,owner)):
                with self.assertRaisesRegex(SystemExit,'unrecognized'):
                    client.migration_preflight()

    def test_vendor_client_conflict_fails_before_download_or_build(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(os,'geteuid',return_value=1000),patch.object(client,'has_consent',return_value=True),patch.object(client,'metadata',return_value={'RPMVersion':'1.2.3'}),patch.object(client,'validate_scan'),patch.object(client,'state_dir',return_value=Path(tmp)),patch.object(client.shutil,'which',return_value='/stub/tool'),patch.object(client.subprocess,'run',return_value=SimpleNamespace(returncode=0)),patch.object(client,'download') as download:
                with self.assertRaisesRegex(SystemExit,'existing vendor client'):
                    client.setup(['--setup'])
                download.assert_not_called()

    def test_old_cached_rpm_explains_rebuild_instead_of_retrying_failed_install(self):
        from types import SimpleNamespace
        with patch.object(client,'previous_named_target',return_value=None),patch.object(client,'ensure_client_closed'),patch.object(client,'migration_preflight',return_value='1.2.95-4'),patch.object(client.subprocess,'run',return_value=SimpleNamespace(stdout='')) as run:
            with self.assertRaisesRegex(SystemExit,'predates the migration fix'):
                client.install_local(Path('/old.rpm'))
            self.assertEqual(run.call_count,1)

    def test_unsafe_release_cannot_inject_spec_metadata(self):
        with self.assertRaisesRegex(ValueError,'legacy package release'):
            client.target_spec('1.2.3',9,'2.39','4\nObsoletes: another-package')


class SetupProgressTests(unittest.TestCase):
    def test_completed_and_failed_phases_keep_elapsed_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            with patch.object(client.time,'monotonic',side_effect=[10,12.5]):
                with client.phase('Verifying source',output): pass
            with patch.object(client.time,'monotonic',side_effect=[20,21.5]):
                with self.assertRaises(ValueError):
                    with client.phase('Building RPM',output): raise ValueError('build failed')
            log=(output/'setup-progress.log').read_text()
            self.assertIn('Verifying source: completed in 2.5s.',log)
            self.assertIn('Building RPM: stopped after 1.5s.',log)


class PrivateDEBCacheTests(unittest.TestCase):
    def test_repeated_build_reuses_only_hash_verified_private_source(self):
        import io
        contents=b'official-deb-fixture'
        record={'SHA256':hashlib.sha256(contents).hexdigest(),'Size':len(contents),'Filename':'fixture.deb'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache'
            with patch.dict(os.environ,{},clear=True),patch.object(client,'urlopen',side_effect=lambda *a,**k:io.BytesIO(contents)) as network:
                client.download(record,root/'first.deb',cache)
                client.download(record,root/'second.deb',cache)
                self.assertEqual(network.call_count,1)
            self.assertEqual((root/'second.deb').read_bytes(),contents)
            self.assertEqual((cache/(record['SHA256']+'.deb')).stat().st_mode & 0o777,0o600)

    def test_tampered_private_cache_is_replaced_before_extraction(self):
        import io
        contents=b'official-deb-fixture'
        record={'SHA256':hashlib.sha256(contents).hexdigest(),'Size':len(contents),'Filename':'fixture.deb'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';cache.mkdir()
            cached=cache/(record['SHA256']+'.deb');cached.write_bytes(b'tampered')
            with patch.dict(os.environ,{},clear=True),patch.object(client,'urlopen',return_value=io.BytesIO(contents)) as network:
                client.download(record,root/'fresh.deb',cache)
                network.assert_called_once()
            self.assertEqual(cached.read_bytes(),contents)


class LiveFeedbackAndCommandTests(unittest.TestCase):
    def test_help_aliases_are_readonly_and_document_requested_commands(self):
        import contextlib, io
        for args in (['--help'], ['-h'], ['--setup', '-h']):
            with self.subTest(args=args), patch.object(client, 'setup') as setup, patch.object(client, 'launch') as launch:
                output=io.StringIO()
                with contextlib.redirect_stdout(output): client.main(args)
                setup.assert_not_called();launch.assert_not_called()
                for option in ('--setup -unstable','--update -unstable','--status','--debug','--safe-mode','--client-versions','-cl.ver','spot-fly-light','(no option)'):
                    self.assertIn(option,output.getvalue())

    def test_version_aliases_show_both_pinned_channels_without_consent_or_network(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            records={}
            for channel,version in [('stable','1.2.3'),('unstable','1.3.4')]:
                records[channel]=dict(Package='spotify-client',Architecture='amd64',Channel=channel,RPMVersion=version,
                    Filename=f'pool/non-free/s/spotify-client/spotify-client_{version}_amd64.deb',SHA256='a'*64,Size=10,PackagingRelease=7)
            records['Bootstrap']={'Version':'26.10.31','Release':2,'PackagedAt':'2026-10-31T12:00:00+01:00','Timezone':'Europe/Stockholm'}
            (root/'source.json').write_text(json.dumps(records))
            for option in ('--client-versions','-cl.ver'):
                with patch.object(client,'HERE',root),patch.object(client,'consent') as consent,patch.object(client,'download') as download:
                    output=io.StringIO()
                    with contextlib.redirect_stdout(output):client.main([option])
                    consent.assert_not_called();download.assert_not_called()
                    for text in ('26.10.31-2','Spotify stable: 1.2.3','Spotify unstable: 1.3.4','Europe/Stockholm'):
                        self.assertIn(text,output.getvalue())

    def test_live_child_output_is_also_preserved_and_failure_propagates(self):
        import contextlib, io, sys
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'build.log';output=io.StringIO()
            with contextlib.redirect_stdout(output):
                client.run_logged([sys.executable,'-c','print("actual rpm output", flush=True)'],log,dict(os.environ))
            self.assertEqual(log.read_text(),'actual rpm output\n')
            self.assertIn('rpm> actual rpm output',output.getvalue())
            with self.assertRaises(subprocess.CalledProcessError):
                client.run_logged([sys.executable,'-c','print("build failure"); raise SystemExit(7)'],log,dict(os.environ))
            self.assertIn('build failure',log.read_text())

    def test_progress_reports_measured_bytes_and_completed_stages(self):
        import contextlib, io
        output=io.StringIO()
        with contextlib.redirect_stdout(output),patch.object(client.time,'monotonic',return_value=12):
            client.byte_progress('Download',1048576,2097152,10)
        self.assertIn('50.0%',output.getvalue());self.assertIn('0.50 MiB/s',output.getvalue());self.assertIn('ETA 2s',output.getvalue())
        with tempfile.TemporaryDirectory() as tmp:
            with client.phase('Complete',Path(tmp),step=7,total=7):pass
            text=(Path(tmp)/'setup-progress.log').read_text()
            self.assertIn('86% of steps complete',text);self.assertIn('100% of steps complete',text)

    def test_private_cache_directory_is_preserved(self):
        import io
        data=b'original';record={'Filename':'fixture.deb','SHA256':hashlib.sha256(data).hexdigest(),'Size':len(data)}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';entry=cache/(record['SHA256']+'.deb');entry.mkdir(parents=True)
            (entry/'keep').write_text('user data')
            with patch.dict(os.environ,{},clear=True),patch.object(client,'urlopen',return_value=io.BytesIO(data)):
                client.download(record,root/'download.deb',cache)
            self.assertEqual((entry/'keep').read_text(),'user data')
            self.assertEqual((root/'download.deb').read_bytes(),data)
