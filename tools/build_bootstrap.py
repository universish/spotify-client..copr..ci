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


def build(record_path, output, release):
    module_spec = importlib.util.spec_from_file_location('bootstrap', REPO / 'bootstrap/spotify.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    record = module.metadata(record_path)
    if not re.fullmatch('[1-9][0-9]*', str(release)):
        raise ValueError('Positive packaging release required')
    record['PackagingRelease'] = int(release)
    version = record['RPMVersion']
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='spotify-bootstrap-') as tmp:
        top = Path(tmp)
        for directory in ('BUILD', 'SOURCES', 'SPECS', 'RPMS', 'SRPMS'):
            (top / directory).mkdir()
        root = top / 'bootstrap'
        root.mkdir()
        # Explicit allowlist: never copy output/, DEBs, vendor icons, archives or app code.
        for source in ('bootstrap/spotify.py', 'src/scan_payload.sh', 'src/spotify-gpu.sh',
                       'eula.txt', 'DISCLAIMER.txt', 'COPYRIGHT', 'licenses/MIT-new-contributions.txt'):
            shutil.copy2(REPO / source, root / Path(source).name)
        (root / 'source.json').write_text(json.dumps(record, indent=2) + '\n')
        with tarfile.open(top / 'SOURCES/bootstrap.tar.gz', 'w:gz') as archive:
            archive.add(root, arcname='bootstrap')
        spec = top / 'SPECS/spotify.spec'
        spec.write_text(f'''%global debug_package %{{nil}}
Name: spotify
Version: {version}
Release: {release}%{{?dist}}
Summary: Community bootstrap for a local Spotify client build
License: MIT
URL: https://github.com/universish/spotify-client..copr..ci
ExclusiveArch: x86_64 x86_64_v2
Source0: bootstrap.tar.gz
BuildRequires: coreutils
Requires: bash
Requires: python3
Requires: coreutils
Requires: /usr/bin/rpmbuild
Requires: /usr/bin/dpkg-deb
Requires: /usr/bin/freshclam
Requires: /usr/bin/clamscan
Requires: /usr/bin/desktop-file-validate
Requires: tar
Requires: /usr/bin/zenity
Requires: /usr/bin/pkexec
%description
Contains only independently authored packaging helpers and source metadata.
No Spotify application, icons or proprietary archives are included. Run
spotify --setup to review the terms and explicitly request a local client build.
%prep
%setup -q -n bootstrap
%install
mkdir -p %{{buildroot}}/usr/share/spotify-bootstrap %{{buildroot}}/usr/bin
cp -a * %{{buildroot}}/usr/share/spotify-bootstrap/
printf '#!/bin/bash\\nexec /usr/bin/python3 /usr/share/spotify-bootstrap/spotify.py "$@"\\n' > %{{buildroot}}/usr/bin/spotify
chmod 0755 %{{buildroot}}/usr/bin/spotify
%files
%license MIT-new-contributions.txt
%doc eula.txt DISCLAIMER.txt COPYRIGHT
/usr/bin/spotify
/usr/share/spotify-bootstrap/
''')
        subprocess.run(['rpmbuild', '-bs', '--define', f'_topdir {top}', '--define', 'dist %{nil}', str(spec)], check=True)
        for rpm in (top / 'SRPMS').glob('*.rpm'):
            shutil.copy2(rpm, output / rpm.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata')
    parser.add_argument('output')
    parser.add_argument('--release', default=os.environ.get('SPOTIFY_RELEASE', '1'))
    args = parser.parse_args()
    build(args.metadata, args.output, args.release)
