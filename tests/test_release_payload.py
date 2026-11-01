import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_payload',ROOT/'tools/verify_release_payload.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
RUN='https://github.com/universish/spotify-client..copr..ci/actions/runs/123'


def catalog():
    records={}
    for channel,version in [('stable','1.2.3'),('unstable','2.0')]:
        records[channel]={'Package':'spotify-client','Architecture':'amd64','Channel':channel,
            'RPMVersion':version,'PackagingRelease':9,'SHA256':'a'*64,'Size':100,
            'Filename':f'pool/non-free/s/spotify-client/spotify-client_{version}_amd64.deb',
            'ScanAttestation':{'SHA256':'a'*64,'Malware':'clean','PUA':'advisory','Scanner':'ClamAV',
                'RunURL':RUN,'ScannedAt':'2026-10-31T00:00:00+00:00','DatabaseVersion':'ClamAV 1.5/test'}}
    records['Bootstrap']={'Version':'26.10.31','Release':1,'PackagedAt':'2026-10-31T03:00:00+00:00','Timezone':'Europe/Stockholm'}
    return records


def source_archive(records=None,extra=None):
    records=records or catalog()
    profile=gate.release_profile(records)
    files={name:path.read_bytes() for name,path in gate.source_files(profile).items()}
    files['source.json']=json.dumps(records).encode()
    files.update(extra or {})
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w:gz') as archive:
        for name,contents in files.items():
            member=tarfile.TarInfo('bootstrap/'+name);member.size=len(contents)
            archive.addfile(member,io.BytesIO(contents))
    return data.getvalue()


def binary_files(records=None):
    records=records or catalog();profile=gate.release_profile(records);prefix=profile['share'].lstrip('/')+'/'
    sources=gate.source_files(profile)
    files={prefix+name:path.read_bytes() for name,path in sources.items() if name not in gate.DESKTOP_FILES.values()}
    if profile['Kind']=='current':
        files.update({target:gate.SOURCES[name].read_bytes() for target,name in gate.DESKTOP_FILES.items()})
    files[prefix+'source.json']=json.dumps(records).encode()
    for name in ('COPYRIGHT','DISCLAIMER.txt','eula.txt'):
        files['usr/share/doc/'+profile['Name']+'/'+name]=gate.SOURCES[name].read_bytes()
    files['usr/share/licenses/'+profile['Name']+'/MIT-new-contributions.txt']=gate.SOURCES['MIT-new-contributions.txt'].read_bytes()
    wrapper=('#!/bin/bash\nexec /usr/bin/python3 '+profile['share']+'/spot..fly..light.py "$@"\n').encode()
    files['usr/bin/'+profile['command']]=wrapper
    files['usr/bin/'+profile['alias']]=wrapper
    return files


class ReleasePayloadTests(unittest.TestCase):
    def setUp(self):
        patched=mock.patch.object(gate, 'validate_auth', return_value=None)
        patched.start();self.addCleanup(patched.stop)

    def test_only_reviewed_helpers_and_current_scanned_catalog_are_accepted(self):
        records=gate.check_source(source_archive(),'26.10.31',1,RUN)
        gate.check_binary(binary_files(records),records)

    def test_standard_versioned_documentation_directories_are_accepted(self):
        for doc_versioned in (False, True):
            for license_versioned in (False, True):
                files=binary_files()
                for prefix,versioned in [('usr/share/doc/',doc_versioned),('usr/share/licenses/',license_versioned)]:
                    if versioned:
                        for name in list(files):
                            if name.startswith(prefix+'spot-fly-light/'):
                                files[name.replace(prefix+'spot-fly-light/',prefix+'spot-fly-light-26.10.31/',1)]=files.pop(name)
                self.assertEqual(len(files),20)
                gate.check_binary(files,catalog())

    def test_versioned_documentation_never_allows_foreign_versions_duplicates_or_changed_bytes(self):
        for failure in ('foreign-version','duplicate','changed-notice','changed-license'):
            files=binary_files()
            for name in list(files):
                if name.startswith(('usr/share/doc/spot-fly-light/','usr/share/licenses/spot-fly-light/')):
                    replacement=name.replace('/spot-fly-light/','/spot-fly-light-26.10.31/',1)
                    files[replacement]=files.pop(name)
            if failure=='foreign-version':
                files={name.replace('/spot-fly-light-26.10.31/','/spot-fly-light-26.11.01/'):data for name,data in files.items()}
            elif failure=='duplicate':
                files['usr/share/doc/spot-fly-light/eula.txt']=gate.SOURCES['eula.txt'].read_bytes()
            elif failure=='changed-notice':
                files['usr/share/doc/spot-fly-light-26.10.31/eula.txt']+=b'changed'
            else:
                files['usr/share/licenses/spot-fly-light-26.10.31/MIT-new-contributions.txt']+=b'changed'
            with self.subTest(failure=failure),self.assertRaises(ValueError):
                gate.check_binary(files,catalog())

    def test_deb_or_proprietary_resource_inside_source_blocks_publication(self):
        for name in ('spotify.deb','Apps/login.spa','spotify','icons/spotify.png'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Unexpected file'):
                gate.check_source(source_archive(extra={name:b'vendor payload'}),'26.10.31',1,RUN)

    def test_replaced_helper_bytes_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'differs from the reviewed'):
            gate.check_source(source_archive(extra={'spot..fly..light.py':b'changed bytes'}),'26.10.31',1,RUN)

    def test_foreign_or_failed_scan_cannot_authorize_a_release(self):
        for field,value in [('RunURL',RUN+'9'),('Malware','infected')]:
            records=catalog();records['unstable']['ScanAttestation'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                gate.check_source(source_archive(records),'26.10.31',1,RUN)

    def test_application_file_in_binary_blocks_publication(self):
        files=binary_files();files['usr/share/spotify/spotify']=b'vendor binary'
        with self.assertRaisesRegex(ValueError,'Unexpected file'):
            gate.check_binary(files,catalog())

    def test_standard_rpm_shebang_normalization_keeps_reviewed_script_body(self):
        files=binary_files();name='usr/share/spot..fly..light-bootstrap/spot..fly..light-gpu.sh'
        files[name]=files[name].replace(b'#!/bin/bash\n',b'#!/usr/bin/bash\n',1)
        gate.check_binary(files,catalog())
        files[name]+=b'changed body'
        with self.assertRaisesRegex(ValueError,'differs from the reviewed'):
            gate.check_binary(files,catalog())

    def test_source_and_binary_catalogs_must_match(self):
        files=binary_files();changed=copy.deepcopy(catalog());changed['stable']['PackagingRelease']=10
        with self.assertRaisesRegex(ValueError,'catalogs differ'):
            gate.check_binary(files,changed)

    def test_source_catalog_cannot_hide_vendor_attachments_in_record_or_scan_fields(self):
        for location in ('record', 'scan', 'authentication', 'description'):
            records=catalog()
            if location=='record':
                records['stable']['UnknownBlob']='embedded proprietary payload'
            elif location=='scan':
                records['stable']['ScanAttestation']['Payload']='embedded proprietary payload'
            elif location=='authentication':
                records['stable']['Authentication']={'Schema':1,'Payload':'embedded proprietary payload'}
            else:
                records['stable']['Description']='a'*8193
            with self.subTest(location=location),self.assertRaisesRegex(ValueError,'catalog metadata'):
                gate.check_source(source_archive(records),'26.10.31',1,RUN)

    def test_source_catalog_cannot_hide_attachments_inside_bootstrap_or_pairing(self):
        for location in ('bootstrap', 'pairing', 'original'):
            records=catalog()
            if location=='bootstrap':
                records['Bootstrap']['Payload']='embedded proprietary payload'
            elif location=='pairing':
                records['Bootstrap']['Pairing']={'Selection':'manual','Payload':'embedded proprietary payload'}
            else:
                records['Bootstrap']['OriginalBootstrap']={'Version':'26.10.31','Release':1,
                    'PackagedAt':'2026-10-31T03:00:00+00:00','Payload':'embedded proprietary payload'}
            with self.subTest(location=location),self.assertRaisesRegex(ValueError,'catalog metadata'):
                gate.check_source(source_archive(records),'26.10.31',1,RUN)

    def test_documented_historical_provenance_is_retained_by_the_bounded_schema(self):
        history=json.loads((ROOT/'data/spotify-history.json').read_text())
        for record in history['records']:
            with self.subTest(record=record.get('Id')):
                gate._record_schema(record,'historical fixture')


class AuthenticationGateTests(unittest.TestCase):
    def test_missing_authentication_cannot_be_published(self):
        with self.assertRaisesRegex(ValueError,'Authenticated source evidence'):
            gate.check_source(source_archive(),'26.10.31',1,RUN)


class ArchivePayloadTests(unittest.TestCase):
    def records(self):
        records=catalog()
        for channel,version in [('stable','1.2.63.394'),('unstable','1.2.86.502')]:
            records[channel]['RPMVersion']=version
            records[channel]['Filename']=f'pool/non-free/s/spotify-client/spotify-client_{version}_amd64.deb'
        records['Bootstrap'].update(Kind='archive',Name='spot-fly-light-st1.2.63.394-unst1.2.86.502',Version='0',Release='2')
        return records

    def test_archive_has_only_isolated_paths_and_no_desktop_autostart(self):
        records=self.records()
        with mock.patch.object(gate,'validate_auth',return_value=None):
            checked=gate.check_source(source_archive(records),'0','2',RUN)
        files=binary_files(checked);gate.check_binary(files,checked)
        self.assertEqual(len(files),16)
        self.assertTrue(all('onboarding' not in name for name in files))
        self.assertFalse(any(name.startswith(('etc/xdg/','usr/lib/systemd/')) for name in files))
        self.assertNotIn('usr/bin/spot..fly..light',files)
        self.assertNotIn('usr/bin/spot-fly-light',files)
        files['usr/bin/spot-fly-light']=b'current path overwrite'
        with self.assertRaisesRegex(ValueError,'Unexpected file'):
            gate.check_binary(files,records)

    def test_archive_release_notes_expose_versions_authentication_and_archive_status(self):
        records=self.records();notes=gate.render_release_notes(records,RUN)
        for expected in ('ARCHIVE','1.2.63.394','1.2.86.502','publisher release unknown','first helper identity: unknown','--setup -unstable'):
            self.assertIn(expected,notes)

    def test_repository_timestamp_is_never_presented_as_a_publisher_release_date(self):
        records=self.records()
        records['stable']['Authentication']={'ReleaseDate':'2025-08-04T14:00:05+00:00','Type':'distribution-openpgp'}
        records['stable']['ReleaseDate']='2025-08-04T14:00:05+00:00'
        notes=gate.render_release_notes(records,RUN)
        self.assertIn('publisher release unknown, repository metadata 2025-08-04T14:00:05+00:00',notes)
        self.assertNotIn('Packaged/uploaded now',notes)
