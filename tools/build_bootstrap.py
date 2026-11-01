#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Create a source RPM containing only the community bootstrap and pinned metadata."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from release_identity import validate_identity, release_profile
PACKAGING_ZONE = 'Europe/Stockholm'
POSTTRANS = r'''if command -v loginctl >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1; then
  loginctl list-sessions --no-legend --no-pager 2>/dev/null | while read -r session uid user rest; do
    case "$uid" in ''|*[!0-9]*|0) continue ;; esac
    case "$session:$user" in *[!A-Za-z0-9_.:-]*) continue ;; esac
    case "$(loginctl show-session "$session" --property=Type --value 2>/dev/null)" in wayland|x11) ;; *) continue ;; esac
    [ "$(loginctl show-session "$session" --property=Remote --value 2>/dev/null)" = no ] || continue
    [ "$(loginctl show-session "$session" --property=Active --value 2>/dev/null)" = yes ] || continue
    timeout 2s systemctl --user --machine="$user@.host" --no-ask-password daemon-reload >/dev/null 2>&1 || :
    timeout 2s systemctl --user --machine="$user@.host" --no-ask-password --no-block start spot-fly-light-onboarding.service >/dev/null 2>&1 || :
  done
fi
exit 0'''


def bootstrap_identity(raw, release):
    """Keep helper identity separate from the pinned proprietary clients."""
    identity = dict(raw.get('Bootstrap', {}))
    if not identity:
        packaged = datetime.now(ZoneInfo(PACKAGING_ZONE))
        identity = {'Version': packaged.strftime('%y.%m.%d'), 'PackagedAt': packaged.isoformat(),
                    'Timezone': PACKAGING_ZONE, 'Release': str(release)}
    if str(identity.get('Release')) != str(release):
        raise ValueError('Reserved helper release does not match the packaging catalog')
    result = validate_identity(dict(raw, Bootstrap=identity))
    if os.environ.get('SPOT_FLY_LIGHT_VERSION', result['Version']) != result['Version']:
        raise ValueError('Reserved helper version does not match the packaging catalog')
    return result


def validate_auth(record):
    from source_auth import validate_record_authentication, replay_authentication
    validate_record_authentication(record, allow_legacy=False)
    replay_authentication(record)


def build(record_path, output, release, unstable_path=None):
    module_spec = importlib.util.spec_from_file_location('bootstrap', REPO / 'bootstrap/spot..fly..light.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    raw = json.loads(Path(record_path).read_text())
    channels = {channel: module.metadata(record_path, channel) for channel in ('stable', 'unstable')} if 'stable' in raw else {'stable': module.metadata(record_path, 'stable')}
    if unstable_path:
        channels['unstable'] = module.metadata(unstable_path, 'unstable')
    identity = bootstrap_identity(dict(raw, **channels), release)
    catalog = dict(channels, Bootstrap=identity)
    profile = release_profile(catalog)
    for channel, item in channels.items():
        module.validate_scan(item)
        validate_auth(item)
        item['Channel'] = channel
        item.setdefault('PackagingRelease', 1)
    version, name, release = profile['Version'], profile['Name'], profile['Release']
    current = profile['Kind'] == 'current'
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='spot..fly..light-bootstrap-') as tmp:
        top = Path(tmp)
        for directory in ('BUILD', 'SOURCES', 'SPECS', 'RPMS', 'SRPMS'):
            (top / directory).mkdir()
        root = top / 'bootstrap'
        root.mkdir()
        # Explicit allowlist: never copy vendor data, downloads or app code.
        files = {
            'bootstrap/spot..fly..light.py': 'spot..fly..light.py',
            'src/spotify-gpu.sh': 'spot..fly..light-gpu.sh',
            'src/release_identity.py': 'release_identity.py',
            'src/fontconfig_runtime.py': 'fontconfig_runtime.py',
            'src/source_auth.py': 'source_auth.py',
            'src/source-registry.json': 'source-registry.json',
            'bootstrap/NOTICE.txt': 'eula.txt', 'bootstrap/DISCLAIMER.txt': 'DISCLAIMER.txt',
            'COPYRIGHT': 'COPYRIGHT', 'licenses/MIT-new-contributions.txt': 'MIT-new-contributions.txt',
        }
        if current:
            files.update({'bootstrap/onboarding.py': 'onboarding.py',
                'bootstrap/spot-fly-light-onboarding.desktop': 'spot-fly-light-onboarding.desktop',
                'bootstrap/spot-fly-light-onboarding.service': 'spot-fly-light-onboarding.service'})
        for source, destination in files.items():
            shutil.copy2(REPO / source, root / destination)
        (root / 'source.json').write_text(json.dumps(catalog, indent=2) + '\n')
        with tarfile.open(top / 'SOURCES/bootstrap.tar.gz', 'w:gz') as archive:
            archive.add(root, arcname='bootstrap')
        compatibility = f'Obsoletes: sonicradle\nProvides: sonicradle = {version}-{release}%{{?dist}}\n' if current else ''
        share, command = profile['share'], profile['command']
        desktop_install = """mkdir -p %{buildroot}/etc/xdg/autostart %{buildroot}/usr/lib/systemd/user
install -m 0644 spot-fly-light-onboarding.desktop %{buildroot}/etc/xdg/autostart/spot-fly-light-onboarding.desktop
install -m 0644 spot-fly-light-onboarding.service %{buildroot}/usr/lib/systemd/user/spot-fly-light-onboarding.service
""" if current else ''
        aliases = f'cp -a %{{buildroot}}/usr/bin/{command} %{{buildroot}}/usr/bin/{profile["alias"]}\n' if profile['alias'] != command else ''
        desktop_checks = '%check\ndesktop-file-validate %{buildroot}/etc/xdg/autostart/spot-fly-light-onboarding.desktop\n' if current else ''
        scriptlets = '%posttrans\n' + POSTTRANS + '\n' if current else ''
        extra_files = '/etc/xdg/autostart/spot-fly-light-onboarding.desktop\n/usr/lib/systemd/user/spot-fly-light-onboarding.service\n' if current else ''
        if aliases:
            extra_files += '/usr/bin/' + profile['alias'] + '\n'
        summary = 'Spot..Light installer for Spotify stable and unstable' if current else 'ARCHIVE: isolated historical Spotify local installer'
        marker = 'CURRENT' if current else 'ARCHIVE: fixed historical pair; explicit setup only; no automatic current updates'
        spec = top / 'SPECS' / (name + '.spec')
        spec.write_text(f'''%global debug_package %{{nil}}
Name: {name}
Version: {version}
Release: {release}%{{?dist}}
Summary: {summary}
License: MIT
{compatibility}URL: https://github.com/universish/spotify-client..copr..ci
ExclusiveArch: x86_64 x86_64_v2
Source0: bootstrap.tar.gz
BuildRequires: coreutils
BuildRequires: /usr/bin/desktop-file-validate
Requires: bash
Requires: python3
Requires: coreutils
Requires: /usr/bin/rpmbuild
Requires: /usr/bin/dpkg-deb
Requires: /usr/bin/desktop-file-validate
Requires: tar
Requires: /usr/bin/zenity
Requires: /usr/bin/pkexec
%description
{marker}
Contains only independently authored helpers and authenticated scanned source metadata.
No Spotify application, icons or proprietary archives are included.
Run {command} --setup to review the terms and explicitly request a local build.
Helper identity: {name} {version}-{release}; packaged at {identity['PackagedAt']} ({PACKAGING_ZONE}).
Spotify stable client: {channels['stable'].get('DebianVersion', channels['stable'].get('Version', channels['stable']['RPMVersion']))}-{channels['stable']['PackagingRelease']}.
Spotify unstable client: {channels.get('unstable', {}).get('DebianVersion', channels.get('unstable', {}).get('Version', channels.get('unstable', {}).get('RPMVersion', 'not included')))}{('-' + str(channels['unstable']['PackagingRelease'])) if 'unstable' in channels else ''}.
Use {command} --client-versions (or -cl.ver) and --help to inspect this helper.
%prep
%setup -q -n bootstrap
%install
mkdir -p %{{buildroot}}{share} %{{buildroot}}/usr/bin
cp -a *.py *.json spot..fly..light-gpu.sh eula.txt DISCLAIMER.txt COPYRIGHT MIT-new-contributions.txt %{{buildroot}}{share}/
{desktop_install}printf '#!/bin/bash\nexec /usr/bin/python3 {share}/spot..fly..light.py "$@"\n' > %{{buildroot}}/usr/bin/{command}
chmod 0755 %{{buildroot}}/usr/bin/{command}
{aliases}{desktop_checks}{scriptlets}%files
%license MIT-new-contributions.txt
%doc eula.txt DISCLAIMER.txt COPYRIGHT
/usr/bin/{command}
{share}/
{extra_files}''')
        subprocess.run(['rpmbuild', '-bs', '--define', f'_topdir {top}', '--define', 'dist %{nil}', str(spec)], check=True)
        for rpm in (top / 'SRPMS').glob('*.rpm'):
            shutil.copy2(rpm, output / rpm.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata')
    parser.add_argument('output')
    parser.add_argument('--release', default=os.environ.get('SPOT_FLY_LIGHT_RELEASE', '1'))
    parser.add_argument('--unstable-metadata', help='Optional separately pinned unstable DEB record')
    args = parser.parse_args()
    build(args.metadata, args.output, args.release, args.unstable_metadata)
