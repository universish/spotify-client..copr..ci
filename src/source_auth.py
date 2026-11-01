#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authenticate repository snapshots without changing the host's trust store."""
import base64
import binascii
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import gzip
import io
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from urllib import request, error
from urllib.parse import urlsplit, unquote

REGISTRY_PATH = Path(__file__).with_name('source-registry.json')
METADATA_LIMIT = 4 * 1024 * 1024
FUTURE_ALLOWANCE = timedelta(minutes=10)
STRONG_HASH_ALGORITHMS = {8, 9, 10}  # SHA256, SHA384, SHA512


class AuthenticationError(ValueError):
    """A source exists but its authenticated identity or integrity is invalid."""


class SourceUnavailable(RuntimeError):
    """A registered source could not supply its metadata."""


class MetadataRollback(AuthenticationError):
    """An otherwise authenticated snapshot is older than accepted evidence."""


def registry():
    data = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    if data.get('schema') != 1:
        raise AuthenticationError('Unsupported source registry')
    return data


def source(source_id):
    item = next((s for s in registry()['sources'] if s['id'] == source_id), None)
    if item is None or not item.get('enabled'):
        raise AuthenticationError('Unknown or disabled source: ' + str(source_id))
    return item


def spotify_sources():
    return [s for s in registry()['sources'] if s.get('enabled') and s['kind'] == 'spotify']


def download_bases():
    return tuple(s['base_url'].rstrip('/') for s in registry()['sources']
                 if s.get('enabled') and 'bytes' in s.get('roles', []))


def safe_relative(path):
    if (not isinstance(path, str) or not path or '\\' in path or '\x00' in path
            or urlsplit(path).scheme or urlsplit(path).query or urlsplit(path).fragment or path.startswith('/')
            or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or unquote(path) != path or any(p in ('', '.', '..') for p in path.split('/'))):
        raise AuthenticationError('Unsafe repository path')
    return path


def _approved_url(url, hosts):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username
            or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
        raise AuthenticationError('Unregistered metadata URL')
    return url


def read_url(url, limit=METADATA_LIMIT, timeout=30, *, hosts=None):
    hosts = set(hosts or [urlsplit(s['base_url']).hostname for s in registry()['sources'] if s.get('enabled')])
    _approved_url(url, hosts)
    class Redirect(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _approved_url(newurl, hosts)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    opener = request.build_opener(Redirect())
    with opener.open(url, timeout=timeout) as response:
        result = response.read(limit + 1)
        coding = response.headers.get('Content-Encoding', '').lower()
    if len(result) > limit:
        raise AuthenticationError('Repository metadata exceeds size limit')
    if coding not in ('', 'identity', 'gzip'):
        raise AuthenticationError('Unsupported repository metadata content encoding')
    if coding == 'gzip':
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(result)) as stream:
                result = stream.read(limit + 1)
        except (OSError, EOFError) as exc:
            raise AuthenticationError('Malformed compressed repository metadata') from exc
    if len(result) > limit:
        raise AuthenticationError('Repository metadata exceeds size limit')
    return result


def _gpg(args, home, *, data=None):
    env = dict(os.environ, GNUPGHOME=str(home), LC_ALL='C', LANGUAGE='en')
    result = subprocess.run(['gpg', '--batch', '--no-options', '--homedir', str(home),
                             '--no-auto-key-retrieve', '--auto-key-locate', 'clear',
                             *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env, timeout=30)
    return result


def _key_records(text):
    records, current = {}, None
    for line in text.splitlines():
        fields = line.split(':')
        if fields[0] in ('pub', 'sub'):
            current = {'type': fields[0], 'validity': fields[1], 'bits': int(fields[2]),
                       'algorithm': int(fields[3]), 'created': int(fields[5] or 0),
                       'expires': int(fields[6] or 0), 'capabilities': fields[11]}
        elif fields[0] == 'fpr' and current is not None:
            records[fields[9]] = current
            current = None
    return records


def _valid_key(key, now):
    if key['validity'] in ('r', 'e', 'd', 'i') or 'D' in key['capabilities']:
        raise AuthenticationError('Repository signing key is revoked, expired or disabled')
    timestamp = int(now.timestamp())
    if key['created'] > timestamp + int(FUTURE_ALLOWANCE.total_seconds()):
        raise AuthenticationError('Repository signing key is from the future')
    if key['expires'] and key['expires'] <= timestamp:
        raise AuthenticationError('Repository signing key has expired')
    if not ((key['algorithm'] in (1, 3) and key['bits'] >= 2048)
            or (key['algorithm'] == 22 and key['bits'] >= 255)):
        raise AuthenticationError('Repository signing key algorithm is not permitted')


def verify_signed_release(*, key_data, fingerprint, inrelease=None, release=None,
                          signature=None, now=None):
    """Return verified plaintext and signer facts; never trust gpg exit alone."""
    now = now or datetime.now(timezone.utc)
    if not re.fullmatch(r'[0-9A-F]{40,64}', fingerprint):
        raise AuthenticationError('A complete pinned key fingerprint is required')
    with tempfile.TemporaryDirectory(prefix='spot-light-auth-') as tmp:
        home = Path(tmp)
        key = home / 'key.asc'; key.write_bytes(key_data)
        shown = _gpg(['--with-colons', '--fixed-list-mode', '--show-keys', str(key)], home)
        if shown.returncode:
            raise AuthenticationError('Cannot read the repository public key')
        keys = _key_records(shown.stdout.decode('utf-8'))
        if fingerprint not in keys or keys[fingerprint]['type'] != 'pub':
            raise AuthenticationError('Repository public key fingerprint mismatch')
        _valid_key(keys[fingerprint], now)
        ring = home / 'trusted.gpg'
        if key_data.startswith(b'-----BEGIN PGP PUBLIC KEY BLOCK-----'):
            converted = _gpg(['--dearmor', '--output', str(ring), str(key)], home)
            if converted.returncode:
                raise AuthenticationError('Cannot prepare the isolated repository keyring')
        else:
            ring.write_bytes(key_data)
        plaintext = home / 'Release'
        options = ['--no-default-keyring', '--keyring', str(ring), '--no-auto-check-trustdb', '--status-fd', '1']
        if inrelease is not None:
            signed = home / 'InRelease'; signed.write_bytes(inrelease)
            checked = _gpg([*options, '--output', str(plaintext), '--decrypt', str(signed)], home)
        elif release is not None and signature is not None:
            plaintext.write_bytes(release)
            signed = home / 'Release.gpg'; signed.write_bytes(signature)
            checked = _gpg([*options, '--verify', str(signed), str(plaintext)], home)
        else:
            raise AuthenticationError('Signed repository metadata is required')
        statuses = [line.split()[1:] for line in checked.stdout.decode('utf-8', 'replace').splitlines()
                    if line.startswith('[GNUPG:] ')]
        bad = {'BADSIG', 'ERRSIG', 'NO_PUBKEY', 'EXPKEYSIG', 'REVKEYSIG', 'EXPSIG', 'KEYREVOKED', 'FAILURE', 'ERROR', 'NODATA'}
        valid = [item[1:] for item in statuses if item and item[0] == 'VALIDSIG']
        if checked.returncode or any(item and item[0] in bad for item in statuses) or len(valid) != 1:
            raise AuthenticationError('Repository OpenPGP signature did not pass strict verification')
        fields = valid[0]
        signer, primary = fields[0], fields[9] if len(fields) > 9 else fields[0]
        if primary != fingerprint or signer not in keys:
            raise AuthenticationError('Metadata was not signed by the pinned repository key')
        _valid_key(keys[signer], now)
        if int(fields[6]) not in (1, 3, 22) or int(fields[7]) not in STRONG_HASH_ALGORITHMS:
            raise AuthenticationError('Repository signature algorithm is not permitted')
        created, expires = int(fields[2]), int(fields[3])
        if created < keys[signer]['created'] or created > int((now + FUTURE_ALLOWANCE).timestamp()):
            raise AuthenticationError('Repository signature creation time is invalid')
        if expires and expires <= int(now.timestamp()):
            raise AuthenticationError('Repository signature has expired')
        return plaintext.read_bytes(), {'Fingerprint': fingerprint, 'SigningFingerprint': signer,
                'SignatureCreated': datetime.fromtimestamp(created, timezone.utc).isoformat(),
                'SignatureHashAlgorithm': int(fields[7]), 'SigningKeyAlgorithm': keys[signer]['algorithm'],
                'SigningKeyBits': keys[signer]['bits'],
                'KeyExpires': datetime.fromtimestamp(keys[signer]['expires'], timezone.utc).isoformat() if keys[signer]['expires'] else None}


def parse_release(data):
    fields, current = {}, None
    for line in data.decode('utf-8').splitlines():
        if line.startswith((' ', '\t')):
            if current is None:
                raise AuthenticationError('Malformed Release document')
            fields[current] += '\n' + line.strip()
        elif line:
            key, separator, value = line.partition(':')
            if not separator or key in fields:
                raise AuthenticationError('Malformed or duplicate Release field')
            fields[key] = value.strip(); current = key
    return fields


def _date(value):
    try:
        result = parsedate_to_datetime(value)
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise AuthenticationError('Missing or invalid repository date') from None


def _accepted_states(accepted, source_info, distribution):
    if not accepted:
        return []
    items = accepted.items() if isinstance(accepted, dict) else ((None, item) for item in accepted)
    results = []
    for key, item in items:
        if not isinstance(item, dict):
            continue
        repository_id = item.get('RepositoryID') or (str(key).rsplit(':', 1)[0] if key else '')
        suite = item.get('Distribution') or (str(key).rsplit(':', 1)[-1] if key else '')
        same = repository_id == source_info['id']
        if source_info['kind'] == 'spotify':
            same = repository_id in {s['id'] for s in spotify_sources()}
        if same and suite == distribution:
            results.append(item)
    return results


def verify_snapshot(source_id, distribution, index_path, packages, *, inrelease=None,
                    release=None, signature=None, accepted_state=None, now=None):
    info = source(source_id)
    if 'metadata' not in info.get('roles', []) or distribution not in info.get('distributions', {}):
        raise AuthenticationError('Repository is not an authority for this distribution')
    expected = info['distributions'][distribution]['index_path']
    if safe_relative(index_path) != expected:
        raise AuthenticationError('Unexpected repository package index')
    key_file = REGISTRY_PATH.parent / info['key_file']
    verified, signer = verify_signed_release(key_data=key_file.read_bytes(), fingerprint=info['fingerprint'],
        inrelease=inrelease, release=release, signature=signature, now=now)
    fields = parse_release(verified)
    if distribution not in (fields.get('Suite'), fields.get('Codename')):
        raise AuthenticationError('Signed repository distribution mismatch')
    current = now or datetime.now(timezone.utc)
    published = _date(fields.get('Date'))
    if published > current + FUTURE_ALLOWANCE:
        raise AuthenticationError('Repository Release date is in the future')
    expires = _date(fields['Valid-Until']) if fields.get('Valid-Until') else None
    if expires is not None and (expires <= current or expires < published):
        raise AuthenticationError('Repository Release has expired')
    checksums = {}
    for line in fields.get('SHA256', '').splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 3 or not re.fullmatch(r'[0-9a-fA-F]{64}', parts[0]) or not parts[1].isdigit():
            raise AuthenticationError('Invalid Release SHA256 entry')
        if parts[2] in checksums:
            raise AuthenticationError('Duplicate Release checksum path')
        checksums[parts[2]] = (parts[0].lower(), int(parts[1]))
    actual = (hashlib.sha256(packages).hexdigest(), len(packages))
    if checksums.get(index_path) != actual:
        raise AuthenticationError('Packages size/SHA256 does not match the signed Release')
    release_hash = hashlib.sha256(verified).hexdigest()
    for old in _accepted_states(accepted_state, info, distribution):
        try:
            previous = datetime.fromisoformat(old['ReleaseDate'])
            if previous.tzinfo is None:
                raise ValueError('Naive accepted timestamp')
            previous = previous.astimezone(timezone.utc)
        except (KeyError, ValueError, TypeError):
            raise AuthenticationError('Invalid previously accepted repository state') from None
        if published < previous:
            raise MetadataRollback('Repository metadata predates an accepted snapshot')
        if published == previous and old.get('ReleaseSHA256') != release_hash:
            raise MetadataRollback('Different signed repository contents reuse an accepted Release date')
    bundle = {'Packages': base64.b64encode(packages).decode('ascii')}
    if inrelease is not None:
        bundle['InRelease'] = base64.b64encode(inrelease).decode('ascii')
    else:
        bundle.update(Release=base64.b64encode(release).decode('ascii'), Signature=base64.b64encode(signature).decode('ascii'))
    evidence = {'Schema': 1, 'Type': 'spotify-openpgp' if info['kind'] == 'spotify' else 'distribution-openpgp',
                'Publisher': info['owner'], 'RepositoryID': source_id, 'Distribution': distribution,
                'ReleaseDate': published.isoformat(), 'ReleaseSHA256': release_hash,
                'ValidUntil': expires.isoformat() if expires else None, 'IndexPath': index_path,
                'IndexSHA256': actual[0], 'IndexSize': actual[1], 'Evidence': bundle, **signer}
    return packages, evidence


def verify_repository(source_id, distribution, *, accepted_state=None, fetcher=None, now=None):
    info = source(source_id)
    if distribution not in info.get('distributions', {}):
        raise AuthenticationError('Unknown repository distribution')
    fetcher = fetcher or read_url
    base = info['base_url'].rstrip('/') + '/dists/' + distribution + '/'
    inline = detached = release = None
    try:
        inline = fetcher(base + 'InRelease', METADATA_LIMIT)
    except error.HTTPError as exc:
        missing = exc.code in (404, 410)
        exc.close()
        if not missing:
            raise SourceUnavailable('Repository InRelease is unavailable') from exc
    except (error.URLError, TimeoutError, OSError):
        # This is a transport failure, not a failed signature. A separately
        # authenticated Release/Release.gpg remains an acceptable fallback.
        pass
    if inline is None:
        try:
            release = fetcher(base + 'Release', METADATA_LIMIT)
            detached = fetcher(base + 'Release.gpg', METADATA_LIMIT)
        except (error.URLError, TimeoutError, OSError) as exc:
            raise SourceUnavailable('Signed Release fallback is unavailable') from exc
    # Fail a bad signature before retrieving or parsing its package index.
    verify_signed_release(key_data=(REGISTRY_PATH.parent / info['key_file']).read_bytes(),
        fingerprint=info['fingerprint'], inrelease=inline, release=release, signature=detached, now=now)
    index_path = info['distributions'][distribution]['index_path']
    try:
        packages = fetcher(base + index_path, METADATA_LIMIT)
    except (error.URLError, TimeoutError, OSError) as exc:
        raise SourceUnavailable('Repository Packages is unavailable') from exc
    data, evidence = verify_snapshot(source_id, distribution, index_path, packages,
        inrelease=inline, release=release, signature=detached, accepted_state=accepted_state, now=now)
    evidence.update(InReleaseURL=base + 'InRelease', ReleaseURL=base + 'Release',
                    ReleaseSignatureURL=base + 'Release.gpg', PackageIndexURL=base + index_path)
    return data, evidence


def record_binding(record):
    try:
        if record.get('DebianVersion') and record.get('Version') and record['DebianVersion'] != record['Version']:
            raise ValueError('Conflicting Debian versions')
        result = {key: str(record.get('DebianVersion', record.get('Version', ''))) if key == 'DebianVersion'
                  else int(record[key]) if key == 'Size' else record[key]
                  for key in ('Package', 'Architecture', 'DebianVersion', 'Filename', 'Size', 'SHA256')}
        if (result['Package'] != 'spotify-client' or result['Architecture'] != 'amd64'
                or not result['DebianVersion'] or result['Size'] <= 0
                or not re.fullmatch(r'[0-9a-f]{64}', result['SHA256'])
                or not safe_relative(result['Filename']).endswith('.deb')):
            raise ValueError('Unsupported source identity')
        return result
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError('Invalid authenticated DEB identity: ' + str(exc)) from None


def bind_record(record, evidence):
    result = dict(record)
    result['DebianVersion'] = record.get('DebianVersion') or record.get('Version', '')
    result['Authentication'] = dict(evidence, Record=record_binding(result))
    validate_record_authentication(result)
    return result


def validate_record_authentication(record, *, allow_legacy=False):
    """Validate a packaged evidence envelope locally, without GPG or network."""
    auth = record.get('Authentication')
    if auth is None and allow_legacy:
        return
    if not isinstance(auth, dict) or auth.get('Schema') != 1:
        raise AuthenticationError('Authenticated source evidence is required')
    info = source(auth.get('RepositoryID'))
    expected_type = 'spotify-openpgp' if info['kind'] == 'spotify' else 'distribution-openpgp'
    if (auth.get('Type') != expected_type or auth.get('Fingerprint') != info.get('fingerprint')
            or auth.get('Publisher') != info['owner']):
        raise AuthenticationError('Source evidence publisher or fingerprint mismatch')
    if auth.get('Record') != record_binding(record):
        raise AuthenticationError('Source record differs from its authenticated binding')
    if auth.get('Distribution') not in info.get('distributions', {}) or auth.get('IndexPath') != info['distributions'][auth['Distribution']]['index_path']:
        raise AuthenticationError('Source evidence distribution mismatch')
    if info['kind'] == 'spotify' and record.get('Channel') is not None:
        if record['Channel'] != ('stable' if auth['Distribution'] == 'stable' else 'unstable'):
            raise AuthenticationError('Spotify channel differs from signed distribution')
    for key in ('ReleaseSHA256', 'IndexSHA256'):
        if not re.fullmatch(r'[0-9a-f]{64}', auth.get(key, '')):
            raise AuthenticationError('Source evidence digest is invalid')
    if type(auth.get('IndexSize')) is not int or not 0 < auth['IndexSize'] <= METADATA_LIMIT:
        raise AuthenticationError('Source evidence index size is invalid')
    try:
        published = datetime.fromisoformat(auth['ReleaseDate'])
        if published.tzinfo is None:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise AuthenticationError('Source evidence date is invalid') from None
    decoded = decode_evidence(auth)
    packages = decoded['Packages']
    if (len(packages) != auth['IndexSize']
            or hashlib.sha256(packages).hexdigest() != auth['IndexSHA256']):
        raise AuthenticationError('Embedded Packages differs from its verified digest')
    plaintext = cleartext_release(decoded['InRelease']) if 'InRelease' in decoded else decoded['Release']
    if hashlib.sha256(plaintext).hexdigest() != auth['ReleaseSHA256']:
        raise AuthenticationError('Embedded Release differs from its verified digest')
    fields = parse_release(plaintext)
    if auth['Distribution'] not in (fields.get('Suite'), fields.get('Codename')):
        raise AuthenticationError('Embedded Release has a different distribution')
    if _date(fields.get('Date')).isoformat() != auth['ReleaseDate']:
        raise AuthenticationError('Embedded Release has a different date')
    expected = [auth['IndexSHA256'], str(auth['IndexSize']), auth['IndexPath']]
    rows = [line.split() for line in fields.get('SHA256', '').splitlines() if line.strip()]
    if rows.count(expected) != 1:
        raise AuthenticationError('Embedded signed Release does not bind this package index')
    expiry = _date(fields['Valid-Until']).isoformat() if fields.get('Valid-Until') else None
    if auth.get('ValidUntil') != expiry:
        raise AuthenticationError('Embedded Release expiry differs from recorded evidence')
    find_bound_record(packages, record)


def decode_evidence(auth):
    bundle = auth.get('Evidence')
    if not isinstance(bundle, dict) or set(bundle) not in ({'Packages', 'InRelease'}, {'Packages', 'Release', 'Signature'}):
        raise AuthenticationError('Complete embedded signed repository evidence is required')
    try:
        if any(not isinstance(v, str) or len(v) > (METADATA_LIMIT + 2) // 3 * 4 for v in bundle.values()):
            raise ValueError('Evidence exceeds limit')
        decoded = {name: base64.b64decode(value, validate=True) for name, value in bundle.items()}
        if any(not value or len(value) > METADATA_LIMIT for value in decoded.values()):
            raise ValueError('Empty or oversized evidence')
        return decoded
    except (TypeError, ValueError, binascii.Error):
        raise AuthenticationError('Embedded signed repository evidence is invalid') from None


def cleartext_release(data):
    """Extract inline payload for local envelope checks; CI also verifies its signature."""
    text = data.replace(b'\r\n', b'\n')
    header, separator, rest = text.partition(b'\n\n')
    if not separator or not header.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\nHash: '):
        raise AuthenticationError('Malformed inline OpenPGP envelope')
    body, separator, trailer = rest.partition(b'-----BEGIN PGP SIGNATURE-----')
    if not separator or not trailer.rstrip().endswith(b'-----END PGP SIGNATURE-----'):
        raise AuthenticationError('Incomplete inline OpenPGP signature')
    return b''.join(line[2:] if line.startswith(b'- ') else line for line in body.splitlines(keepends=True))


def parse_control_records(data):
    text = data.decode('utf-8') if isinstance(data, bytes) else data
    records, current, previous = [], {}, None
    for line in text.splitlines():
        if not line.strip() or (line.startswith('Package:') and current):
            if current:
                records.append(current)
            current, previous = {}, None
            if not line.strip():
                continue
        if line.startswith((' ', '\t')):
            if previous is None:
                raise AuthenticationError('Malformed Debian control continuation')
            current[previous] += '\n' + line.strip()
            continue
        key, separator, value = line.partition(':')
        if not separator or not re.fullmatch(r'[A-Za-z0-9-]+', key) or key in current:
            raise AuthenticationError('Malformed or duplicate Debian control field')
        current[key], previous = value.strip(), key
    if current:
        records.append(current)
    return records


def find_bound_record(packages, record):
    binding = record_binding(record)
    matches = []
    for item in parse_control_records(packages):
        if item.get('Package') != binding['Package'] or item.get('Architecture') != binding['Architecture']:
            continue
        if item.get('Version') != binding['DebianVersion']:
            continue
        if record_binding(item) != binding:
            raise AuthenticationError('Signed index contains conflicting bytes for this Debian version')
        matches.append(item)
    if len(matches) != 1:
        raise AuthenticationError('The exact DEB record is absent or duplicated in the signed index')
    return matches[0]


def replay_authentication(record, *, accepted_state=None):
    """Revalidate embedded signed evidence before CI downloads historical bytes."""
    validate_record_authentication(record)
    auth = record['Authentication']
    decoded = decode_evidence(auth)
    data, verified = verify_snapshot(auth['RepositoryID'], auth['Distribution'], auth['IndexPath'],
        decoded.get('Packages', b''), inrelease=decoded.get('InRelease'), release=decoded.get('Release'),
        signature=decoded.get('Signature'), accepted_state=accepted_state)
    if any(verified[key] != auth[key] for key in ('ReleaseDate', 'ReleaseSHA256', 'IndexSHA256', 'IndexSize', 'Fingerprint',
        'SigningFingerprint', 'SignatureCreated', 'SignatureHashAlgorithm', 'SigningKeyAlgorithm',
        'SigningKeyBits', 'KeyExpires', 'ValidUntil')):
        raise AuthenticationError('Embedded source evidence differs from the recorded verification')
    return data, verified
