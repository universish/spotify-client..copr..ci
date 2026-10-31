#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Gate GitHub assets: only the payload-free community bootstrap may be published."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'spot..fly..light.py': ROOT / 'bootstrap/spot..fly..light.py',
    'spot..fly..light-gpu.sh': ROOT / 'src/spotify-gpu.sh',
    'eula.txt': ROOT / 'bootstrap/NOTICE.txt',
    'DISCLAIMER.txt': ROOT / 'bootstrap/DISCLAIMER.txt',
    'COPYRIGHT': ROOT / 'COPYRIGHT',
    'MIT-new-contributions.txt': ROOT / 'licenses/MIT-new-contributions.txt',
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


def check_source(data, version, release, run_url):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        members = [m for m in archive.getmembers() if not m.isdir()]
        expected = {'bootstrap/' + name for name in (*SOURCES, 'source.json')}
        if {m.name for m in members} != expected or len(members) != len(expected):
            raise ValueError('Unexpected file in bootstrap source archive')
        if any(not m.isfile() or m.size > LIMIT for m in members):
            raise ValueError('Unexpected source archive entry type or size')
        for name, source in SOURCES.items():
            if archive.extractfile('bootstrap/' + name).read() != source.read_bytes():
                raise ValueError('Source helper differs from the reviewed checkout: ' + name)
        catalog = json.load(archive.extractfile('bootstrap/source.json'))
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
            if record['ScanAttestation']['RunURL'] != run_url:
                raise ValueError('Source must have passed scanning in this Actions run')
    info = catalog['Bootstrap']
    if (info.get('Version') != version or info.get('Release') != release
            or info.get('Timezone') != 'Europe/Stockholm'):
        raise ValueError('Bootstrap catalog does not match the reserved release')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    packaged = datetime.fromisoformat(info['PackagedAt'])
    if packaged.tzinfo is None or packaged.astimezone(ZoneInfo('Europe/Stockholm')).strftime('%y.%m.%d') != version:
        raise ValueError('Bootstrap version must be its Stockholm packaging date')
    return catalog


def check_binary(files, catalog):
    prefix = 'usr/share/spot..fly..light-bootstrap/'
    version = catalog.get('Bootstrap', {}).get('Version', '')
    if not re.fullmatch(r'[0-9]{2}[.][0-9]{2}[.][0-9]{2}', version):
        raise ValueError('Invalid bootstrap catalog version')
    # Fedora uses name-only documentation directories; Debian RPM macros append
    # the package version. Accept only these two exact layouts, with no extra files.
    notices = ('COPYRIGHT', 'DISCLAIMER.txt', 'eula.txt')
    doc_prefix = next((f'usr/share/doc/{directory}/' for directory in ('spot-fly-light', f'spot-fly-light-{version}')
                       if all(f'usr/share/doc/{directory}/{name}' in files for name in notices)), None)
    license_path = next((f'usr/share/licenses/{directory}/MIT-new-contributions.txt'
                         for directory in ('spot-fly-light', f'spot-fly-light-{version}')
                         if f'usr/share/licenses/{directory}/MIT-new-contributions.txt' in files), None)
    if doc_prefix is None or license_path is None:
        raise ValueError('Unexpected file in bootstrap binary payload')
    expected = {prefix + name for name in (*SHARE_NAMES, 'source.json')}
    expected.update(DESKTOP_FILES)
    expected.update(doc_prefix + name for name in notices)
    expected.update((license_path, 'usr/bin/spot..fly..light', 'usr/bin/spot-fly-light'))
    if set(files) != expected:
        raise ValueError('Unexpected file in bootstrap binary payload')
    for name, source in SOURCES.items():
        target = next((path for path, entry in DESKTOP_FILES.items() if entry == name), prefix + name)
        reviewed = source.read_bytes()
        alternatives = {reviewed}
        if name == 'spot..fly..light-gpu.sh' and reviewed.startswith(b'#!/bin/bash\n'):
            # RPM's standard shebang normalization changes only this interpreter path.
            alternatives.add(reviewed.replace(b'#!/bin/bash\n', b'#!/usr/bin/bash\n', 1))
        if files[target] not in alternatives:
            raise ValueError('Binary helper differs from the reviewed checkout: ' + name)
    for name in notices:
        if files[doc_prefix + name] != SOURCES[name].read_bytes():
            raise ValueError('Mismatched packaged notice')
    if files[license_path] != SOURCES['MIT-new-contributions.txt'].read_bytes():
        raise ValueError('Mismatched packaged license')
    if json.loads(files[prefix + 'source.json']) != catalog:
        raise ValueError('Binary and source catalogs differ')
    launch = files['usr/bin/spot..fly..light']
    if launch not in (b'#!/bin/bash\nexec /usr/bin/python3 /usr/share/spot..fly..light-bootstrap/spot..fly..light.py "$@"\n',
                      b'#!/usr/bin/bash\nexec /usr/bin/python3 /usr/share/spot..fly..light-bootstrap/spot..fly..light.py "$@"\n'):
        raise ValueError('Unexpected bootstrap command')
    if files['usr/bin/spot-fly-light'] != launch:
        raise ValueError('Bootstrap command aliases differ')


def verify(output, version, release, run_url):
    if not re.fullmatch(r'[0-9]{2}[.][0-9]{2}[.][0-9]{2}', version) or release < 1:
        raise ValueError('Invalid version/release')
    expected = [output / f'spot-fly-light-{version}-{release}.{arch}.rpm' for arch in ('src', 'x86_64')]
    checksums = {}
    for path, arch in zip(expected, ('src', 'x86_64')):
        identity = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH} %{SOURCEPACKAGE}', str(path)], text=True)
        wanted = f'spot-fly-light {version}-{release} x86_64 ' + ('1' if arch == 'src' else '(none)')
        if identity != wanted:
            raise ValueError('Unexpected release RPM identity')
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    source = rpm_payload(expected[0])
    if set(source) != {'bootstrap.tar.gz', 'spot-fly-light.spec'}:
        raise ValueError('Unexpected source RPM contents')
    catalog = check_source(source['bootstrap.tar.gz'], version, release, run_url)
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
    (output / 'release-notes.md').write_text(
        'Spot..Light community installer and launcher.\n\n'
        'These RPM/SRPM assets contain only free community helpers, notices and scanned source metadata. '
        'Spotify is downloaded separately from its upstream repository after the requesting user approves local installation.\n\n'
        f"Pinned stable source: `{catalog['stable']['RPMVersion']}`. "
        f"Pinned testing source: `{catalog['unstable']['RPMVersion']}`.\n\n"
        'Install the bootstrap RPM using your package manager, then run `spot..fly..light --setup` as your normal user. '
        'Add `-unstable` to select testing. Read the displayed notice and the applicable Spotify terms.\n\n'
        f'[CI scan and delivery evidence]({run_url}).\n')
    print('Verified both payload-free bootstrap RPMs and SHA256SUMS for publication.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--release', required=True, type=int)
    parser.add_argument('--run-url', required=True)
    args = parser.parse_args()
    verify(args.output, args.version, args.release, args.run_url)
