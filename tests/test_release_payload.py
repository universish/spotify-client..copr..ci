import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import unittest

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
    files={name:path.read_bytes() for name,path in gate.SOURCES.items()}
    files['source.json']=json.dumps(records or catalog()).encode()
    files.update(extra or {})
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w:gz') as archive:
        for name,contents in files.items():
            member=tarfile.TarInfo('bootstrap/'+name);member.size=len(contents)
            archive.addfile(member,io.BytesIO(contents))
    return data.getvalue()


def binary_files(records=None):
    records=records or catalog();prefix='usr/share/spot..fly..light-bootstrap/'
    files={prefix+name:gate.SOURCES[name].read_bytes() for name in gate.SHARE_NAMES}
    files.update({target:gate.SOURCES[name].read_bytes() for target,name in gate.DESKTOP_FILES.items()})
    files[prefix+'source.json']=json.dumps(records).encode()
    for name in ('COPYRIGHT','DISCLAIMER.txt','eula.txt'):
        files['usr/share/doc/spot-fly-light/'+name]=gate.SOURCES[name].read_bytes()
    files['usr/share/licenses/spot-fly-light/MIT-new-contributions.txt']=gate.SOURCES['MIT-new-contributions.txt'].read_bytes()
    files['usr/bin/spot..fly..light']=b'#!/bin/bash\nexec /usr/bin/python3 /usr/share/spot..fly..light-bootstrap/spot..fly..light.py "$@"\n'
    files['usr/bin/spot-fly-light']=files['usr/bin/spot..fly..light']
    return files


class ReleasePayloadTests(unittest.TestCase):
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
                self.assertEqual(len(files),16)
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
