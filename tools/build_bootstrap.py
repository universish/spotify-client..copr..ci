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
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
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
    """Keep the helper version separate from the pinned proprietary clients."""
    identity = dict(raw.get('Bootstrap', {}))
    if not identity:
        packaged = datetime.now(ZoneInfo(PACKAGING_ZONE))
        identity = {'Version': packaged.strftime('%y.%m.%d'), 'PackagedAt': packaged.isoformat(),
                    'Timezone': PACKAGING_ZONE, 'Release': int(release)}
    try:
        packaged = datetime.fromisoformat(identity['PackagedAt'])
        if packaged.utcoffset() is None or identity['Timezone'] != PACKAGING_ZONE:
            raise ValueError()
        if (identity['Version'] != packaged.astimezone(ZoneInfo(PACKAGING_ZONE)).strftime('%y.%m.%d')
                or not re.fullmatch(r'[0-9]{2}[.][0-9]{2}[.][0-9]{2}', identity['Version'])
                or identity['Release'] != int(release)):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError('Invalid Stockholm packaging date or helper release') from None
    if os.environ.get('SPOT_FLY_LIGHT_VERSION', identity['Version']) != identity['Version']:
        raise ValueError('Reserved helper version does not match the packaging catalog')
    return identity


def build(record_path, output, release, unstable_path=None):
    module_spec = importlib.util.spec_from_file_location('bootstrap', REPO / 'bootstrap/spot..fly..light.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    raw = json.loads(Path(record_path).read_text())
    if 'stable' in raw:
        channels = {channel: module.metadata(record_path, channel) for channel in ('stable', 'unstable')}
    else:
        channels = {'stable': module.metadata(record_path, 'stable')}
    if unstable_path:
        channels['unstable'] = module.metadata(unstable_path, 'unstable')
    record = channels['stable']
    if not re.fullmatch('[1-9][0-9]*', str(release)):
        raise ValueError('Positive packaging release required')
    identity = bootstrap_identity(raw, release)
    for channel, item in channels.items():
        module.validate_scan(item)
        item['Channel'] = channel
        item.setdefault('PackagingRelease', 1)
    version = identity['Version']
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='spot..fly..light-bootstrap-') as tmp:
        top = Path(tmp)
        for directory in ('BUILD', 'SOURCES', 'SPECS', 'RPMS', 'SRPMS'):
            (top / directory).mkdir()
        root = top / 'bootstrap'
        root.mkdir()
        # Explicit allowlist: never copy output/, DEBs, vendor icons, archives or app code.
        files = {
            'bootstrap/spot..fly..light.py': 'spot..fly..light.py',
            'bootstrap/onboarding.py': 'onboarding.py',
            'bootstrap/spot-fly-light-onboarding.desktop': 'spot-fly-light-onboarding.desktop',
            'bootstrap/spot-fly-light-onboarding.service': 'spot-fly-light-onboarding.service',
            'src/spotify-gpu.sh': 'spot..fly..light-gpu.sh',
            'bootstrap/NOTICE.txt': 'eula.txt',
            'bootstrap/DISCLAIMER.txt': 'DISCLAIMER.txt',
            'COPYRIGHT': 'COPYRIGHT',
            'licenses/MIT-new-contributions.txt': 'MIT-new-contributions.txt',
        }
        for source, destination in files.items():
            shutil.copy2(REPO / source, root / destination)
        (root / 'source.json').write_text(json.dumps(dict(channels, Bootstrap=identity), indent=2) + '\n')
        with tarfile.open(top / 'SOURCES/bootstrap.tar.gz', 'w:gz') as archive:
            archive.add(root, arcname='bootstrap')
        spec = top / 'SPECS/spot-fly-light.spec'
        spec.write_text(f'''%global debug_package %{{nil}}
Name: spot-fly-light
Version: {version}
Release: {release}%{{?dist}}
Summary: Spot..Light installer for Spotify stable and unstable
License: MIT
Obsoletes: sonicradle
Provides: sonicradle = {version}-{release}%{{?dist}}
URL: https://github.com/universish/spotify-client..copr..ci
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
Contains only independently authored packaging helpers and source metadata.
No Spotify application, icons or proprietary archives are included. Run
spot..fly..light --setup to review the terms and explicitly request a local client build.
Helper packaging date: {version} ({PACKAGING_ZONE}); packaging revision: {release}.
Spotify stable client: {channels['stable']['RPMVersion']}-{channels['stable']['PackagingRelease']}.
Spotify unstable client: {channels.get('unstable', {}).get('RPMVersion', 'not included')}{('-' + str(channels['unstable']['PackagingRelease'])) if 'unstable' in channels else ''}.
Use spot..fly..light --client-versions (or -cl.ver) to inspect the pinned catalog.
Use spot..fly..light --help for setup, updates and graphics troubleshooting.
%prep
%setup -q -n bootstrap
%install
mkdir -p %{{buildroot}}/usr/share/spot..fly..light-bootstrap %{{buildroot}}/usr/bin
cp -a *.py spot..fly..light-gpu.sh eula.txt DISCLAIMER.txt COPYRIGHT MIT-new-contributions.txt source.json %{{buildroot}}/usr/share/spot..fly..light-bootstrap/
mkdir -p %{{buildroot}}/etc/xdg/autostart %{{buildroot}}/usr/lib/systemd/user
install -m 0644 spot-fly-light-onboarding.desktop %{{buildroot}}/etc/xdg/autostart/spot-fly-light-onboarding.desktop
install -m 0644 spot-fly-light-onboarding.service %{{buildroot}}/usr/lib/systemd/user/spot-fly-light-onboarding.service
printf '#!/bin/bash\\nexec /usr/bin/python3 /usr/share/spot..fly..light-bootstrap/spot..fly..light.py "$@"\\n' > %{{buildroot}}/usr/bin/spot..fly..light
chmod 0755 %{{buildroot}}/usr/bin/spot..fly..light
cp -a %{{buildroot}}/usr/bin/spot..fly..light %{{buildroot}}/usr/bin/spot-fly-light
%check
desktop-file-validate %{{buildroot}}/etc/xdg/autostart/spot-fly-light-onboarding.desktop
%posttrans
{POSTTRANS}
%files
%license MIT-new-contributions.txt
%doc eula.txt DISCLAIMER.txt COPYRIGHT
/usr/bin/spot..fly..light
/usr/bin/spot-fly-light
/usr/share/spot..fly..light-bootstrap/
/etc/xdg/autostart/spot-fly-light-onboarding.desktop
/usr/lib/systemd/user/spot-fly-light-onboarding.service
''')
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
