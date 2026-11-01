#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Gate GitHub assets: only the payload-free community bootstrap may be published."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from release_identity import release_profile
SOURCES = {
    'spot..fly..light.py': ROOT / 'bootstrap/spot..fly..light.py',
    'spot..fly..light-gpu.sh': ROOT / 'src/spotify-gpu.sh',
    'eula.txt': ROOT / 'bootstrap/NOTICE.txt',
    'DISCLAIMER.txt': ROOT / 'bootstrap/DISCLAIMER.txt',
    'COPYRIGHT': ROOT / 'COPYRIGHT',
    'MIT-new-contributions.txt': ROOT / 'licenses/MIT-new-contributions.txt',
    'release_identity.py': ROOT / 'src/release_identity.py',
    'fontconfig_runtime.py': ROOT / 'src/fontconfig_runtime.py',
    'source_auth.py': ROOT / 'src/source_auth.py',
    'source-registry.json': ROOT / 'src/source-registry.json',
    'onboarding.py': ROOT / 'bootstrap/onboarding.py',
    'spot-fly-light-onboarding.desktop': ROOT / 'bootstrap/spot-fly-light-onboarding.desktop',
    'spot-fly-light-onboarding.service': ROOT / 'bootstrap/spot-fly-light-onboarding.service',
}
DESKTOP_FILES = {
    'etc/xdg/autostart/spot-fly-light-onboarding.desktop': 'spot-fly-light-onboarding.desktop',
    'usr/lib/systemd/user/spot-fly-light-onboarding.service': 'spot-fly-light-onboarding.service',
}
SHARE_NAMES = set(SOURCES) - set(DESKTOP_FILES.values())
LIMIT = 8 * 1024 * 1024

# source.json is an evidence document, not a general-purpose attachment format.
# Keep provenance explicitly rather than permitting arbitrary nested blobs under
# an otherwise valid, authenticated package record.
DEBIAN_FIELDS = set('Package Architecture Version Source Maintainer Priority Section Installed-Size '
                    'Depends Pre-Depends Recommends Suggests Enhances Breaks Conflicts Provides Replaces '
                    'Multi-Arch Essential Built-Using Homepage License Vendor Description Description-md5 '
                    'Filename Size MD5sum SHA1 SHA256 SHA512'.split())
RECORD_FIELDS = DEBIAN_FIELDS | set('DebianVersion RawDebianVersion RPMVersion NumericVersion CommitHash '
    'UpstreamVersion DebianEpoch DebianRevision Channel ChannelEvidence PackagingRelease RepositoryURL '
    'Distribution PackageIndexURL DownloadBaseURLs DownloadURLs RPMFusionChecks Authentication ScanAttestation '
    'Id PublishedAt ReleaseDate FirstObservedAt SupportedLayout UnsupportedReason Evidence SourceVariants '
    'Availability HistoricalProvenance DistributionProvenance OriginalFilename OriginalSHA256 SpotifySHA256'.split())
BOOTSTRAP_FIELDS = set('Kind Name Version Release PackagedAt Timezone Pairing OriginalBootstrap'.split())
PAIRING_FIELDS = set('Kind Selection RequestedVersion ResolvedRequestedVersion RequestedChannel OppositeVersion '
    'AnchorObservedAt AnchorPublishedAt Evidence Chronology ChannelAssignment'.split())
PROVENANCE_FIELDS = set('SourceID Distribution IndexPath PackageIndexURL CaptureTimestamp '
                        'InReleaseURL ReleaseURL ReleaseSignatureURL'.split())
OBSERVATION_FIELDS = set('Type URL RequestedURL ObservedAt Channel PublishedAt IndexModifiedAt '
                         'DocumentSHA256 TransportSHA256 Authentication'.split())
AUTH_FIELDS = set('Schema Type Publisher RepositoryID Distribution ReleaseDate ReleaseSHA256 ValidUntil '
    'IndexPath IndexSHA256 IndexSize Evidence Fingerprint SigningFingerprint SignatureCreated '
    'SignatureHashAlgorithm SigningKeyAlgorithm SigningKeyBits KeyExpires InReleaseURL ReleaseURL '
    'ReleaseSignatureURL PackageIndexURL Record'.split())
SCAN_FIELDS = set('SHA256 Malware PUA RunURL ScannedAt Scanner DatabaseVersion'.split())


def _object(value, allowed, label):
    if not isinstance(value, dict) or not set(value) <= allowed:
        raise ValueError('Unexpected catalog metadata fields: ' + label)
    return value


def _text(value, label, limit=4096, nullable=False):
    if nullable and value is None:
        return
    if (not isinstance(value, str) or len(value) > limit
            or any(ord(char) < 32 and char not in '\n\r\t' for char in value)):
        raise ValueError('Invalid or oversized catalog metadata: ' + label)


def _number(value, label, *, text=False):
    if type(value) is int and 0 <= value <= 2 ** 63 - 1:
        return
    if text and isinstance(value, str) and re.fullmatch(r'[0-9]{1,19}', value) and int(value) <= 2 ** 63 - 1:
        return
    raise ValueError('Invalid catalog metadata number: ' + label)


def _list(value, label, limit=64):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError('Invalid or oversized catalog metadata list: ' + label)
    return value


def _flat_text_object(value, allowed, label):
    for key, item in _object(value, allowed, label).items():
        _text(item, label + '.' + key, nullable=True)


def _observations(value, label):
    for item in _list(value, label):
        _flat_text_object(item, OBSERVATION_FIELDS, label)


def _authentication_schema(value, label):
    for key, item in _object(value, AUTH_FIELDS, label).items():
        field = label + '.' + key
        if key == 'Evidence':
            _object(item, {'Packages', 'InRelease', 'Release', 'Signature'}, field)
            # source_auth independently requires one exact complete bundle,
            # validates base64, hashes and membership, and replays OpenPGP.
            for name, encoded in item.items():
                _text(encoded, field + '.' + name, (LIMIT + 2) // 3 * 4)
        elif key == 'Record':
            _object(item, {'Package', 'Architecture', 'DebianVersion', 'Filename', 'Size', 'SHA256'}, field)
            for name, bound in item.items():
                _number(bound, field + '.' + name, text=True) if name == 'Size' else _text(bound, field + '.' + name)
        elif key in ('Schema', 'IndexSize', 'SignatureHashAlgorithm', 'SigningKeyAlgorithm', 'SigningKeyBits'):
            _number(item, field)
        else:
            _text(item, field, nullable=key in ('ValidUntil', 'KeyExpires'))


def _record_schema(record, label, depth=0):
    _object(record, RECORD_FIELDS, label)
    if depth > 2:
        raise ValueError('Catalog source variants are too deeply nested')
    plain = {key: value for key, value in record.items() if key != 'Authentication'}
    if len(json.dumps(plain, ensure_ascii=False).encode()) > 256 * 1024:
        raise ValueError('Oversized catalog metadata: ' + label)
    for key, item in record.items():
        field = label + '.' + key
        if key == 'Authentication':
            _authentication_schema(item, field)
        elif key == 'ScanAttestation':
            _flat_text_object(item, SCAN_FIELDS, field)
        elif key == 'Evidence':
            _observations(item, field)
        elif key == 'SourceVariants':
            for variant in _list(item, field, 8):
                _record_schema(variant, field, depth + 1)
        elif key in ('HistoricalProvenance', 'DistributionProvenance'):
            _flat_text_object(item, PROVENANCE_FIELDS, field)
        elif key in ('DownloadBaseURLs', 'DownloadURLs'):
            for url in _list(item, field, 32):
                _text(url, field)
        elif key == 'RPMFusionChecks':
            for check in _list(item, field, 16):
                _object(check, {'repository', 'url', 'status', 'packages', 'error'}, field)
                for name, value in check.items():
                    if name == 'packages':
                        for package in _list(value, field + '.packages', 32):
                            _flat_text_object(package, {'name', 'version', 'release', 'architecture'}, field + '.packages')
                    else:
                        _text(value, field + '.' + name)
        elif key == 'Availability':
            _object(item, {'Status', 'Checks'}, field)
            if 'Status' in item:
                _text(item['Status'], field + '.Status')
            for check in _list(item.get('Checks', []), field + '.Checks', 32):
                _object(check, {'URL', 'Status', 'Size', 'LastModified', 'CheckedAt', 'BytesHashVerified', 'Error'}, field + '.Checks')
                for name, value in check.items():
                    if name in ('Status', 'Size'):
                        _number(value, field + '.' + name, text=True)
                    elif name == 'BytesHashVerified':
                        if type(value) is not bool:
                            raise ValueError('Invalid catalog metadata boolean: ' + field)
                    else:
                        _text(value, field + '.' + name, nullable=True)
        elif key in ('Size', 'Installed-Size', 'PackagingRelease'):
            _number(item, field, text=key != 'PackagingRelease')
        elif key == 'SupportedLayout':
            if type(item) is not bool:
                raise ValueError('Invalid catalog metadata boolean: ' + field)
        else:
            _text(item, field, 8192 if key in ('Description', 'Depends', 'Recommends') else 4096,
                  nullable=key in ('PublishedAt', 'ReleaseDate', 'FirstObservedAt'))


def validate_catalog_schema(catalog):
    """Reject attachment-like data without dropping documented source evidence."""
    _object(catalog, {'stable', 'unstable', 'Bootstrap'}, 'catalog')
    for channel in ('stable', 'unstable'):
        if channel in catalog:
            _record_schema(catalog[channel], channel)
    bootstrap = _object(catalog.get('Bootstrap'), BOOTSTRAP_FIELDS, 'Bootstrap')
    if len(json.dumps(bootstrap, ensure_ascii=False).encode()) > 64 * 1024:
        raise ValueError('Oversized Bootstrap metadata')
    for key, item in bootstrap.items():
        if key == 'OriginalBootstrap':
            _object(item, {'Version', 'Release', 'PackagedAt', 'Timezone'}, 'OriginalBootstrap')
            for name, value in item.items():
                _number(value, name, text=True) if name == 'Release' else _text(value, name, 256)
        elif key == 'Pairing':
            _object(item, PAIRING_FIELDS, 'Pairing')
            for name, value in item.items():
                _observations(value, 'Pairing.Evidence') if name == 'Evidence' else _text(value, 'Pairing.' + name, nullable=True)
        elif key == 'Release':
            # Known first-helper archives use OriginalDailySlot.Rebuild.
            if not (type(item) is int and item > 0) and not (isinstance(item, str) and re.fullmatch(r'[1-9][0-9]*(?:[.][1-9][0-9]*)?', item)):
                raise ValueError('Invalid Bootstrap.Release')
        else:
            _text(item, 'Bootstrap.' + key, 256)


def rpm_payload(path):
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Unexpectedly large bootstrap RPM')
    with subprocess.Popen(['rpm2cpio', str(path)], stdout=subprocess.PIPE) as process:
        data = process.stdout.read(LIMIT + 1)
        if len(data) > LIMIT:
            process.kill()
            process.wait()
            raise ValueError('RPM payload exceeds the bootstrap limit')
        if process.wait():
            raise ValueError('Cannot decode RPM payload')
    files, links, offset = {}, {}, 0
    while True:
        header = data[offset:offset + 110]
        if len(header) != 110 or header[:6] not in (b'070701', b'070702'):
            raise ValueError('Invalid RPM cpio header')
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        offset += 110
        name = data[offset:offset + fields[11] - 1].decode()
        offset = (offset + fields[11] + 3) & ~3
        if name == 'TRAILER!!!':
            break
        size, mode = fields[6], fields[1]
        contents = data[offset:offset + size]
        if len(contents) != size:
            raise ValueError('Truncated RPM cpio data')
        offset = (offset + size + 3) & ~3
        name = name.removeprefix('./')
        if name in files or name.startswith('/') or '..' in Path(name).parts:
            raise ValueError('Unsafe or duplicate RPM payload path')
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Bootstrap payload must contain only regular files')
        files[name] = contents
        if fields[4] > 1:
            key = fields[0], fields[7], fields[8]
            links.setdefault(key, []).append(name)
    for group in links.values():
        contents = next((files[name] for name in group if files[name]), b'')
        for name in group:
            files[name] = contents
    return files


def source_files(profile):
    omitted = set() if profile['Kind'] == 'current' else {'onboarding.py', *DESKTOP_FILES.values()}
    return {name: path for name, path in SOURCES.items() if name not in omitted}


def validate_auth(record):
    from source_auth import validate_record_authentication, replay_authentication
    validate_record_authentication(record, allow_legacy=False)
    replay_authentication(record)


def check_source(data, version, release, run_url):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        members = []
        for count, member in enumerate(archive, 1):
            if count > 64 or member.size > LIMIT or member.size < 0:
                raise ValueError('Unexpected source archive entry count or size')
            if not member.isdir():
                if not member.isfile():
                    raise ValueError('Unexpected source archive entry type')
                members.append(member)
        if len([m for m in members if m.name == 'bootstrap/source.json']) != 1:
            raise ValueError('Missing or duplicate source catalog')
        catalog = json.load(archive.extractfile('bootstrap/source.json'))
        validate_catalog_schema(catalog)
        profile = release_profile(catalog)
        sources = source_files(profile)
        expected = {'bootstrap/' + name for name in (*sources, 'source.json')}
        if {m.name for m in members} != expected or len(members) != len(expected):
            raise ValueError('Unexpected file in bootstrap source archive')
        for name, source in sources.items():
            if archive.extractfile('bootstrap/' + name).read() != source.read_bytes():
                raise ValueError('Source helper differs from the reviewed checkout: ' + name)
    if set(catalog) != {'stable', 'unstable', 'Bootstrap'}:
        raise ValueError('Both source channels are required')
    spec = importlib.util.spec_from_file_location('release_bootstrap', SOURCES['spot..fly..light.py'])
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    with tempfile.TemporaryDirectory(prefix='spot-light-release-check-') as tmp:
        pinned = Path(tmp) / 'source.json'
        pinned.write_text(json.dumps(catalog))
        for channel in ('stable', 'unstable'):
            record = bootstrap.metadata(pinned, channel)
            bootstrap.validate_scan(record)
            validate_auth(record)
            if record['ScanAttestation']['RunURL'] != run_url:
                raise ValueError('Source must have passed scanning in this Actions run')
    if profile['Version'] != str(version) or profile['Release'] != str(release):
        raise ValueError('Bootstrap catalog does not match the reserved release')
    return catalog


def check_binary(files, catalog):
    profile = release_profile(catalog)
    sources = source_files(profile)
    prefix = profile['share'].lstrip('/') + '/'
    name, version = profile['Name'], profile['Version']
    notices = ('COPYRIGHT', 'DISCLAIMER.txt', 'eula.txt')
    doc_prefix = next((f'usr/share/doc/{directory}/' for directory in (name, f'{name}-{version}')
                       if all(f'usr/share/doc/{directory}/{entry}' in files for entry in notices)), None)
    license_path = next((f'usr/share/licenses/{directory}/MIT-new-contributions.txt'
                         for directory in (name, f'{name}-{version}')
                         if f'usr/share/licenses/{directory}/MIT-new-contributions.txt' in files), None)
    if doc_prefix is None or license_path is None:
        raise ValueError('Unexpected file in bootstrap binary payload')
    shared_names = set(sources) - set(DESKTOP_FILES.values())
    expected = {prefix + entry for entry in (*shared_names, 'source.json')}
    if profile['Kind'] == 'current':
        expected.update(DESKTOP_FILES)
    expected.update(doc_prefix + entry for entry in notices)
    expected.update((license_path, 'usr/bin/' + profile['command'], 'usr/bin/' + profile['alias']))
    if set(files) != expected:
        raise ValueError('Unexpected file in bootstrap binary payload; missing=' + str(sorted(expected - set(files))) + '; extra=' + str(sorted(set(files) - expected)))
    for entry, source in sources.items():
        target = next((path for path, item in DESKTOP_FILES.items() if item == entry), prefix + entry)
        reviewed = source.read_bytes()
        alternatives = {reviewed}
        if entry == 'spot..fly..light-gpu.sh' and reviewed.startswith(b'#!/bin/bash\n'):
            alternatives.add(reviewed.replace(b'#!/bin/bash\n', b'#!/usr/bin/bash\n', 1))
        if files[target] not in alternatives:
            raise ValueError('Binary helper differs from the reviewed checkout: ' + entry)
    for entry in notices:
        if files[doc_prefix + entry] != SOURCES[entry].read_bytes():
            raise ValueError('Mismatched packaged notice')
    if files[license_path] != SOURCES['MIT-new-contributions.txt'].read_bytes():
        raise ValueError('Mismatched packaged license')
    if json.loads(files[prefix + 'source.json']) != catalog:
        raise ValueError('Binary and source catalogs differ')
    launch = files['usr/bin/' + profile['command']]
    body = f'exec /usr/bin/python3 {profile["share"]}/spot..fly..light.py "$@"\n'.encode()
    if launch not in (b'#!/bin/bash\n' + body, b'#!/usr/bin/bash\n' + body):
        raise ValueError('Unexpected bootstrap command')
    if files['usr/bin/' + profile['alias']] != launch:
        raise ValueError('Bootstrap command aliases differ')


def render_release_notes(catalog, run_url):
    profile = release_profile(catalog)
    name, version, release = profile['Name'], profile['Version'], profile['Release']
    def verification(record):
        auth = record.get('Authentication', {})
        return str(auth.get('Type', auth.get('Publisher', 'legacy metadata + hash-bound CI scan')))
    rows = '\n'.join(f"| {channel} | `{catalog[channel].get('DebianVersion', catalog[channel].get('Version', catalog[channel]['RPMVersion']))}` | {verification(catalog[channel])} | `{profile['command']} --setup" + (' -unstable' if channel == 'unstable' else '') + '` |' for channel in ('stable', 'unstable'))
    dates = '; '.join(channel + ': publisher release ' + str(catalog[channel].get('PublishedAt') or 'unknown')
        + ', repository metadata ' + str(catalog[channel].get('Authentication', {}).get('ReleaseDate') or 'unknown')
        + ', first observed ' + str(catalog[channel].get('FirstObservedAt') or 'unknown') for channel in ('stable', 'unstable'))
    original = catalog['Bootstrap'].get('OriginalBootstrap')
    first = (f"{original['Version']}-{original['Release']}" if original else 'unknown / predates the first helper')
    return (
        f"# {'ARCHIVE — ' if profile['Kind'] == 'archive' else ''}Spot..Light {name} {version}-{release}\n\n"
        + f"Status: **{profile['Kind'].upper()}**. Packaging timestamp: {catalog['Bootstrap']['PackagedAt']}. GitHub records the actual publication timestamp separately.\n\n"
        + '| Spotify channel | Exact source version | Verification | Explicit setup command |\n| --- | --- | --- | --- |\n' + rows + '\n\n'
        + 'Source dates: ' + dates + '.\n\n'
        + ('Historical pair; first helper identity: ' + first + '. This isolated package does not replace or update the current helper.\n\n' if profile['Kind'] == 'archive' else '')
        + 'These RPM/SRPM assets contain only free helpers, notices and source metadata. Verification status is shown per channel above. Spotify is downloaded separately after explicit user approval.\n\n'
        + f'[CI scan and delivery evidence]({run_url}).\n')


def verify(output, version, release, run_url, name=None):
    candidates = list(output.glob('*.src.rpm'))
    if len(candidates) != 1:
        raise ValueError('Exactly one source RPM is required')
    actual_name = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}', str(candidates[0])], text=True)
    if name is not None and name != actual_name:
        raise ValueError('Requested and actual helper RPM names differ')
    name = actual_name
    if not re.fullmatch(r'spot-fly-light(?:-st[0-9]+(?:[.][0-9]+){3}-unst[0-9]+(?:[.][0-9]+){3})?', name):
        raise ValueError('Invalid helper name')
    expected = [output / f'{name}-{version}-{release}.{arch}.rpm' for arch in ('src', 'x86_64')]
    checksums = {}
    for path, arch in zip(expected, ('src', 'x86_64')):
        identity = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH} %{SOURCEPACKAGE}', str(path)], text=True)
        wanted = f'{name} {version}-{release} x86_64 ' + ('1' if arch == 'src' else '(none)')
        if identity != wanted:
            raise ValueError('Unexpected release RPM identity')
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    source = rpm_payload(expected[0])
    if set(source) != {'bootstrap.tar.gz', name + '.spec'}:
        raise ValueError('Unexpected source RPM contents')
    catalog = check_source(source['bootstrap.tar.gz'], version, release, run_url)
    if release_profile(catalog)['Name'] != name:
        raise ValueError('RPM and catalog helper names differ')
    check_binary(rpm_payload(expected[1]), catalog)
    requires = subprocess.check_output(['rpm', '-qp', '--requires', str(expected[1])], text=True)
    if re.search(r'clamav|clamscan|freshclam', requires, re.I):
        raise ValueError('End-user bootstrap must not require ClamAV')
    recorded = {}
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        key = Path(name.lstrip('*')).name
        if key in recorded:
            raise ValueError('Duplicate checksum entry')
        recorded[key] = digest
    if recorded != checksums:
        raise ValueError('Release checksums do not match the two bootstrap RPMs')
    (output / 'release-notes.md').write_text(render_release_notes(catalog, run_url))
    print('Verified both payload-free bootstrap RPMs and SHA256SUMS for publication.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--name', default=os.environ.get('SPOT_FLY_LIGHT_NAME'))
    parser.add_argument('--version', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--run-url', required=True)
    args = parser.parse_args()
    verify(args.output, args.version, args.release, args.run_url, args.name)
