"""Real isolated-GPG fixtures for the repository signature/hash trust boundary."""
import base64
import copy
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import source_auth as auth
import parser_debian_control_file as upstream

INDEX = (b'Package: spotify-client\nArchitecture: amd64\nVersion: 1:1.2.86.502.g8cd7fb22-1\n'
         b'Filename: pool/non-free/s/spotify-client/spotify-client_1.2.86.502.g8cd7fb22-1_amd64.deb\n'
         b'Size: 123\nSHA256: ' + b'a' * 64 + b'\n')


@unittest.skipUnless(shutil.which('gpg'), 'GnuPG required for signature integration tests')
class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='spot-auth-tests-')
        cls.directory = Path(cls.tmp.name)
        cls.home = cls.directory / 'gpg'; cls.home.mkdir(mode=0o700)
        cls.command('--pinentry-mode', 'loopback', '--passphrase', '', '--quick-generate-key',
                    'Repository fixture <fixture@example.invalid>', 'rsa2048', 'sign', '0')
        listing = cls.command('--with-colons', '--list-keys').decode()
        cls.fingerprint = next(l.split(':')[9] for l in listing.splitlines() if l.startswith('fpr:'))
        cls.key = cls.command('--armor', '--export', cls.fingerprint)
        (cls.directory / 'key.asc').write_bytes(cls.key)
        base = {'owner': 'Fixture publisher', 'enabled': True, 'kind': 'spotify',
                'roles': ['metadata', 'bytes'], 'fingerprint': cls.fingerprint, 'key_file': 'key.asc',
                'distributions': {'stable': {'index_path': 'non-free/binary-amd64/Packages'},
                                  'testing': {'index_path': 'non-free/binary-amd64/Packages'}}}
        cls.sources = [dict(base, id='spotify-fixture', base_url='https://fixture.invalid'),
                       dict(base, id='spotify-mirror', base_url='https://mirror.invalid'),
                       dict(base, id='mint-fixture', kind='distribution', base_url='https://mint.invalid')]
        cls.registry = cls.directory / 'source-registry.json'
        cls.registry.write_text(json.dumps({'schema': 1, 'sources': cls.sources}))
        cls.stamp = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=1)
        cls.release = cls.release_document()
        cls.inline = cls.sign(cls.release)
        cls.signature = cls.sign(cls.release, detached=True)

    @classmethod
    def tearDownClass(cls):
        subprocess.run(['gpgconf', '--homedir', str(cls.home), '--kill', 'gpg-agent'], capture_output=True)
        cls.tmp.cleanup()

    @classmethod
    def command(cls, *args, data=None):
        result = subprocess.run(['gpg', '--batch', '--no-options', '--homedir', str(cls.home),
                                 '--yes', *args], input=data, capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr.decode())
        return result.stdout

    @classmethod
    def sign(cls, data, *, detached=False, digest='SHA256'):
        return cls.command('--armor', '--digest-algo', digest, '--local-user', cls.fingerprint,
                           '--output', '-', '--detach-sign' if detached else '--clearsign', data=data)

    @classmethod
    def release_document(cls, *, stamp=None, expiry=None, distribution='stable', index=INDEX):
        text = f'Suite: {distribution}\nDate: {format_datetime(stamp or cls.stamp)}\n'
        if expiry:
            text += 'Valid-Until: ' + format_datetime(expiry) + '\n'
        text += f'SHA256:\n {hashlib.sha256(index).hexdigest()} {len(index)} non-free/binary-amd64/Packages\n'
        return text.encode()

    def setUp(self):
        self.registry_patch = mock.patch.object(auth, 'REGISTRY_PATH', self.registry)
        self.registry_patch.start(); self.addCleanup(self.registry_patch.stop)

    def snapshot(self, **kwargs):
        return auth.verify_snapshot('spotify-fixture', 'stable', 'non-free/binary-amd64/Packages',
                                    kwargs.pop('packages', INDEX), **kwargs)

    def test_inline_and_detached_roundtrip_and_record_replay(self):
        for fields in ({'inrelease': self.inline}, {'release': self.release, 'signature': self.signature}):
            with self.subTest(fields=list(fields)):
                packages, evidence = self.snapshot(**fields)
                record = auth.bind_record(auth.parse_control_records(packages)[0], evidence)
                auth.validate_record_authentication(record)
                replayed, _ = auth.replay_authentication(record)
                self.assertEqual(replayed, INDEX)
                self.assertEqual(record['Authentication']['Fingerprint'], self.fingerprint)

    def test_tampered_inline_signature_and_wrong_full_pin_fail(self):
        for inline, fingerprint in ((self.inline.replace(b'Suite: stable', b'Suite: testing'), self.fingerprint),
                                    (self.inline, 'A' * 40)):
            with self.subTest(fingerprint=fingerprint):
                with self.assertRaises(auth.AuthenticationError):
                    auth.verify_signed_release(key_data=self.key, fingerprint=fingerprint, inrelease=inline)

    def test_hash_and_size_changes_fail_even_with_a_valid_signature(self):
        for data in (INDEX + b'\n', INDEX.replace(b'Size: 123', b'Size: 124')):
            with self.subTest(data=data):
                with self.assertRaisesRegex(auth.AuthenticationError, 'Packages size/SHA256'):
                    self.snapshot(inrelease=self.inline, packages=data)

    def test_weak_signature_hash_is_rejected(self):
        weak = self.sign(self.release, digest='SHA1')
        with self.assertRaises(auth.AuthenticationError): self.snapshot(inrelease=weak)

    def test_wrong_suite_future_date_and_expired_valid_until_fail(self):
        documents = [self.release_document(distribution='testing'),
                     self.release_document(stamp=datetime.now(timezone.utc) + timedelta(hours=1)),
                     self.release_document(expiry=datetime.now(timezone.utc) - timedelta(seconds=1))]
        for release in documents:
            with self.subTest(release=release):
                with self.assertRaises(auth.AuthenticationError): self.snapshot(inrelease=self.sign(release))

    def test_old_signed_date_without_valid_until_has_no_arbitrary_age_limit(self):
        release = self.release_document(stamp=self.stamp - timedelta(days=500))
        _, evidence = self.snapshot(inrelease=self.sign(release))
        self.assertIsNone(evidence['ValidUntil'])

    def test_cross_mirror_rollback_and_same_date_equivocation_rejected(self):
        accepted = {'spotify-mirror:stable': {'ReleaseDate': (self.stamp + timedelta(seconds=1)).isoformat(), 'ReleaseSHA256': 'a' * 64}}
        with self.assertRaises(auth.MetadataRollback): self.snapshot(inrelease=self.inline, accepted_state=accepted)
        accepted['spotify-mirror:stable']['ReleaseDate'] = self.stamp.isoformat()
        with self.assertRaises(auth.MetadataRollback): self.snapshot(inrelease=self.inline, accepted_state=accepted)
        # A different publisher does not set Spotify's high-water mark.
        accepted = {'mint-fixture:stable': {'ReleaseDate': (self.stamp + timedelta(days=1)).isoformat(), 'ReleaseSHA256': 'a' * 64}}
        self.snapshot(inrelease=self.inline, accepted_state=accepted)

    def test_invalid_signature_never_uses_detached_fallback(self):
        calls = []
        def fetch(url, limit):
            calls.append(url)
            return b'invalid inline signature'
        with self.assertRaises(auth.AuthenticationError):
            auth.verify_repository('spotify-fixture', 'stable', fetcher=fetch)
        self.assertEqual(calls, ['https://fixture.invalid/dists/stable/InRelease'])

    def test_absent_inrelease_uses_signed_detached_fallback(self):
        calls = []
        def fetch(url, limit):
            calls.append(url)
            if url.endswith('/InRelease'): raise HTTPError(url, 404, 'missing', {}, io.BytesIO())
            if url.endswith('/Release.gpg'): return self.signature
            if url.endswith('/Release'): return self.release
            return INDEX
        data, _ = auth.verify_repository('spotify-fixture', 'stable', fetcher=fetch)
        self.assertEqual(data, INDEX)
        self.assertEqual(len(calls), 4)

    def test_record_binding_channel_and_evidence_tampering_rejected(self):
        _, evidence = self.snapshot(inrelease=self.inline)
        original = auth.bind_record(auth.parse_control_records(INDEX)[0], evidence)
        variants = []
        for key, value in [('Version', '1:1.2.86.502.gdeadbeef-1'), ('Filename', 'pool/other.deb'),
                           ('Size', '124'), ('SHA256', 'b' * 64), ('Channel', 'unstable')]:
            changed = copy.deepcopy(original); changed[key] = value; variants.append(changed)
        changed = copy.deepcopy(original); changed['Authentication']['Evidence']['Packages'] = base64.b64encode(INDEX + b'\n').decode(); variants.append(changed)
        changed = copy.deepcopy(original); changed['Authentication'].pop('Evidence'); variants.append(changed)
        for changed in variants:
            with self.subTest(record=changed):
                with self.assertRaises(auth.AuthenticationError): auth.validate_record_authentication(changed)

    def test_signature_facts_are_replayed_not_just_envelope_hashes(self):
        _, evidence = self.snapshot(inrelease=self.inline)
        record = auth.bind_record(auth.parse_control_records(INDEX)[0], evidence)
        record['Authentication']['SigningFingerprint'] = 'A' * 40
        with self.assertRaises(auth.AuthenticationError): auth.replay_authentication(record)

    def test_expired_revoked_disabled_weak_and_future_keys_fail_policy(self):
        good = {'validity': '-', 'capabilities': 'scSC', 'created': int(self.stamp.timestamp()) - 20,
                'expires': 0, 'algorithm': 1, 'bits': 2048}
        for changes in ({'validity': 'r'}, {'validity': 'e'}, {'capabilities': 'scD'},
                        {'expires': int(self.stamp.timestamp()) - 1}, {'bits': 1024}, {'algorithm': 17},
                        {'created': int((self.stamp + timedelta(hours=1)).timestamp())}):
            with self.subTest(changes=changes):
                with self.assertRaises(auth.AuthenticationError): auth._valid_key(dict(good, **changes), datetime.now(timezone.utc))
        auth._valid_key(good, datetime.now(timezone.utc))

    def test_distribution_record_requires_its_actual_signed_filename(self):
        data, evidence = auth.verify_snapshot('mint-fixture', 'stable', 'non-free/binary-amd64/Packages',
                                              INDEX, inrelease=self.inline)
        record = dict(auth.parse_control_records(INDEX)[0], Channel='stable',
                      DistributionProvenance={'SourceID': 'mint-fixture', 'Distribution': 'stable',
                                              'IndexPath': 'non-free/binary-amd64/Packages'})
        with mock.patch.object(auth, 'verify_repository', return_value=(data, evidence)):
            checked = upstream.verify_distribution_record(record)
            self.assertEqual(checked['Authentication']['Type'], 'distribution-openpgp')
            self.assertEqual(checked['DownloadBaseURLs'], ['https://mint.invalid'])
            bad = dict(record, Filename='pool/guessed-spotify-path.deb')
            with self.assertRaises(auth.AuthenticationError): upstream.verify_distribution_record(bad)
            bad = dict(record, OriginalSHA256='b' * 64)
            with self.assertRaises(auth.AuthenticationError): upstream.verify_distribution_record(bad)

    def test_historical_actual_captured_signed_bundle_and_embedded_replay(self):
        record = dict(auth.parse_control_records(INDEX)[0], Channel='stable', HistoricalProvenance={
            'SourceID': 'spotify-fixture', 'Distribution': 'stable', 'IndexPath': 'non-free/binary-amd64/Packages',
            'PackageIndexURL': 'https://web.archive.org/web/20261031010000id_/http://fixture.invalid:80/dists/stable/non-free/binary-amd64/Packages',
            'InReleaseURL': 'https://web.archive.org/web/20261031020000id_/https://fixture.invalid/dists/stable/InRelease'})
        def fetch(url, **kwargs):
            return INDEX if url.endswith('/Packages') else self.inline
        with mock.patch.object(auth, 'read_url', side_effect=fetch):
            checked = upstream.verify_historical_record(record)
        self.assertEqual(checked['DebianVersion'], record['Version'])
        self.assertEqual(checked['RPMVersion'], '1.2.86.502.g8cd7fb22.deb1')
        upstream.verify_historical_record(checked)
        # An index timestamp is not a signed Release capture and cannot be invented.
        record['HistoricalProvenance'].pop('InReleaseURL')
        with mock.patch.object(auth, 'read_url', side_effect=fetch):
            with self.assertRaisesRegex(auth.AuthenticationError, 'actual captured signed Release'):
                upstream.verify_historical_record(record)

    def test_real_revocation_certificate_is_rejected(self):
        revoked_home = self.directory / 'revoked'; revoked_home.mkdir(mode=0o700, exist_ok=True)
        def command(*args, data=None):
            result = subprocess.run(['gpg', '--batch', '--no-options', '--homedir', str(revoked_home),
                                     *args], input=data, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return result.stdout
        command('--import', data=self.key)
        certificate = (self.home / 'openpgp-revocs.d' / (self.fingerprint + '.rev')).read_bytes()
        certificate = b'-----BEGIN PGP PUBLIC KEY BLOCK-----' + certificate.split(b':-----BEGIN PGP PUBLIC KEY BLOCK-----', 1)[1]
        command('--import', data=certificate)
        revoked = command('--armor', '--export', self.fingerprint)
        with self.assertRaises(auth.AuthenticationError):
            auth.verify_signed_release(key_data=revoked, fingerprint=self.fingerprint, inrelease=self.inline)

    def test_real_expired_key_cannot_authorize_an_old_valid_signature(self):
        expired_home = self.directory / 'expired'; expired_home.mkdir(mode=0o700, exist_ok=True)
        past = int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp())
        def command(*args, data=None):
            result = subprocess.run(['gpg', '--batch', '--no-options', '--homedir', str(expired_home),
                                     *args], input=data, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return result.stdout
        try:
            command('--faked-system-time', str(past), '--pinentry-mode', 'loopback', '--passphrase', '',
                    '--quick-generate-key', 'Expired fixture <expired@example.invalid>', 'rsa2048', 'sign', '1d')
            listing = command('--with-colons', '--list-keys').decode()
            fingerprint = next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
            signed = command('--faked-system-time', str(past + 3600), '--armor', '--digest-algo', 'SHA256',
                             '--output', '-', '--clearsign', data=self.release)
            key = command('--armor', '--export', fingerprint)
            with self.assertRaises(auth.AuthenticationError):
                auth.verify_signed_release(key_data=key, fingerprint=fingerprint, inrelease=signed)
        finally:
            subprocess.run(['gpgconf', '--homedir', str(expired_home), '--kill', 'gpg-agent'], capture_output=True)

    def test_no_host_key_import_or_trust_database_used(self):
        real = auth._gpg
        with mock.patch.object(auth, '_gpg', wraps=real) as calls:
            self.snapshot(inrelease=self.inline)
        for call in calls.call_args_list:
            self.assertNotIn('--import', call.args[0])
            self.assertNotIn('--trust-model', call.args[0])
            self.assertNotEqual(Path(call.args[1]), Path.home() / '.gnupg')

    def test_path_and_duplicate_record_rejection(self):
        for path in ('../x.deb', 'pool/./x.deb', 'pool/%2e%2e/x.deb', 'pool//x.deb', 'pool/x.deb\n', '/x.deb'):
            with self.subTest(path=path):
                with self.assertRaises(auth.AuthenticationError): auth.safe_relative(path)
        with self.assertRaises(auth.AuthenticationError): auth.parse_control_records('Package: a\nVersion: a\nVersion: b\n')
        with self.assertRaises(auth.AuthenticationError): auth.find_bound_record(INDEX + b'\n' + INDEX, auth.parse_control_records(INDEX)[0])


if __name__ == '__main__':
    unittest.main()
