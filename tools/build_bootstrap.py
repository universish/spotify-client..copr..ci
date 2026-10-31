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

REPO = Path(__file__).resolve().parents[1]


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
    record['PackagingRelease'] = int(release)
    for channel, item in channels.items():
        module.validate_scan(item)
        item['Channel'] = channel
        item.setdefault('PackagingRelease', 1 if channel == 'unstable' else int(release))
    version = record['RPMVersion']
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
            'src/spotify-gpu.sh': 'spot..fly..light-gpu.sh',
            'bootstrap/NOTICE.txt': 'eula.txt',
            'bootstrap/DISCLAIMER.txt': 'DISCLAIMER.txt',
            'COPYRIGHT': 'COPYRIGHT',
            'licenses/MIT-new-contributions.txt': 'MIT-new-contributions.txt',
        }
        for source, destination in files.items():
            shutil.copy2(REPO / source, root / destination)
        (root / 'source.json').write_text(json.dumps(channels, indent=2) + '\n')
        with tarfile.open(top / 'SOURCES/bootstrap.tar.gz', 'w:gz') as archive:
            archive.add(root, arcname='bootstrap')
        spec = top / 'SPECS/spot-fly-light.spec'
        spec.write_text(f'''%global debug_package %{{nil}}
Name: spot-fly-light
Version: {version}
Release: {release}%{{?dist}}
Summary: Independent local client packaging helper
License: MIT
Obsoletes: sonicradle
Provides: sonicradle = {version}-{release}%{{?dist}}
URL: https://github.com/universish/spotify-client..copr..ci
ExclusiveArch: x86_64 x86_64_v2
Source0: bootstrap.tar.gz
BuildRequires: coreutils
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
%prep
%setup -q -n bootstrap
%install
mkdir -p %{{buildroot}}/usr/share/spot..fly..light-bootstrap %{{buildroot}}/usr/bin
cp -a * %{{buildroot}}/usr/share/spot..fly..light-bootstrap/
printf '#!/bin/bash\\nexec /usr/bin/python3 /usr/share/spot..fly..light-bootstrap/spot..fly..light.py "$@"\\n' > %{{buildroot}}/usr/bin/spot..fly..light
chmod 0755 %{{buildroot}}/usr/bin/spot..fly..light
%files
%license MIT-new-contributions.txt
%doc eula.txt DISCLAIMER.txt COPYRIGHT
/usr/bin/spot..fly..light
/usr/share/spot..fly..light-bootstrap/
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
