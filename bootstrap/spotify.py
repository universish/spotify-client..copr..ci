#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Payload-free community bootstrap. Spotify is built only on the user's host."""
import hashlib
import json
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
BASES = ('https://download.spotify.com/debian', 'https://repository.spotify.com')


def state_dir():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'spotify-bootstrap'


def consent_digest():
    return hashlib.sha256((HERE / 'eula.txt').read_bytes()).hexdigest()


def revoke_local_client():
    # Never remove the user's existing LPF/vendor package or the RPM transaction's
    # bootstrap. Only this project's separately named local target is eligible.
    (state_dir() / 'consent.json').unlink(missing_ok=True)
    installed = subprocess.run(['rpm', '-q', 'spotify-client-local'], capture_output=True).returncode == 0
    if installed:
        if not shutil.which('pkexec'):
            raise SystemExit('Consent declined. Client will not launch. Administrator removal required: sudo rpm -e spotify-client-local')
        result = subprocess.run(['pkexec', shutil.which('rpm'), '-e', 'spotify-client-local'])
        if result.returncode:
            raise SystemExit('Consent declined. Client will not launch. Removal was not authorized or failed; run sudo rpm -e spotify-client-local.')


def consent(args):
    notice = (HERE / 'eula.txt').read_text()
    print(notice, flush=True)
    accepted = '--accept-spotify-terms' in args
    if not accepted and shutil.which('zenity') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        result = subprocess.run(['zenity', '--text-info', '--title=Spotify: hukuki durum ve yerel kurulum onayı',
                                 '--filename=' + str(HERE / 'eula.txt'), '--width=760', '--height=600',
                                 '--checkbox=Bu bildirimi ve geçerli Spotify koşullarını okudum; yerel kurulumu istiyorum.'])
        accepted = result.returncode == 0
        if not accepted:
            revoke_local_client()
            raise SystemExit('Consent declined; download, build and launch cancelled.')
    if not accepted:
        raise SystemExit('Review the official terms, then run: spotify --setup --accept-spotify-terms')
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / 'consent.json'
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        json.dump({'notice_sha256': consent_digest()}, stream)


def has_consent():
    try:
        return json.loads((state_dir() / 'consent.json').read_text()).get('notice_sha256') == consent_digest()
    except (OSError, ValueError):
        return False


def install_local(path):
    if not shutil.which('pkexec'):
        raise SystemExit('Local RPM built. Install it after review with your package manager: ' + str(path))
    for tool, options in [('dnf', ['install', '-y']), ('zypper', ['install']), ('urpmi', [])]:
        manager = shutil.which(tool)
        if manager:
            subprocess.run(['pkexec', manager, *options, str(path)], check=True)
            return
    raise SystemExit('Local RPM built; install using your system package manager: ' + str(path))


def metadata(path):
    record = json.loads(Path(path).read_text())
    version = record['RPMVersion']
    if (record.get('Package') != 'spotify-client' or record.get('Architecture') != 'amd64'
            or not re.fullmatch(r'[A-Za-z0-9.+~]+', version)
            or record.get('Filename') != f'pool/non-free/s/spotify-client/spotify-client_{version}_amd64.deb'
            or not re.fullmatch(r'[0-9a-f]{64}', record.get('SHA256', ''))
            or int(record['Size']) <= 0):
        raise ValueError('Invalid pinned official amd64 metadata')
    return record


def verify(path, record):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if path.stat().st_size != int(record['Size']) or digest.hexdigest() != record['SHA256']:
        raise ValueError('DEB size/SHA256 mismatch; stopping before extraction')


def download(record, path):
    if os.environ.get('SPOTIFY_DEB_FILE'):
        cached = Path(os.environ['SPOTIFY_DEB_FILE'])
        verify(cached, record)
        shutil.copy2(cached, path)
        return
    errors = []
    for base in BASES:
        try:
            with urlopen(base + '/' + record['Filename'], timeout=60) as stream, path.open('wb') as output:
                shutil.copyfileobj(stream, output)
            verify(path, record)
            return
        except (OSError, ValueError) as exc:
            errors.append(type(exc).__name__)
            path.unlink(missing_ok=True)
    raise RuntimeError('Official downloads failed: ' + ', '.join(errors))


def target_spec(version, release, glibc):
    if not re.fullmatch(r'[0-9]+(?:[.][0-9]+)*', glibc):
        raise ValueError('Missing official glibc requirement')
    return f'''%global debug_package %{{nil}}
%global __strip /bin/true
%global __brp_strip /bin/true
%global __brp_add_determinism /bin/true
%global __provides_exclude_from ^%{{_datadir}}/spotify-client/.*$
%global __requires_exclude ^(libcef|libEGL|libGLESv2|libvk_swiftshader|libvulkan)[.]so.*$
Name: spotify-client-local
Version: {version}
Release: {release}
Summary: Locally built proprietary Spotify client
License: LicenseRef-Spotify-Proprietary
URL: https://www.spotify.com/download/linux/
ExclusiveArch: x86_64 x86_64_v2
Source0: payload.tar.gz
BuildRequires: coreutils
BuildRequires: desktop-file-utils
Requires: spotify
Requires: glibc >= {glibc}
Requires: hicolor-icon-theme
Requires: /usr/bin/dbus-launch
Requires: /usr/bin/locale
Requires: (glibc-langpack-en or glibc-locale or locales-en)
Requires: libayatana-appindicator3.so.1()(64bit)
Provides: spotify-client = %{{version}}-%{{release}}
Conflicts: spotify-client
%description
Built on this computer from Spotify's verified DEB. Not for redistribution.
%prep
%setup -q -n payload
%install
mkdir -p %{{buildroot}}
cp -a usr %{{buildroot}}/
find %{{buildroot}}/usr/share/spotify-client -type d -exec chmod 0755 {{}} +
find %{{buildroot}}/usr/share/spotify-client -type f -exec chmod go-w {{}} +
find %{{buildroot}}/usr/share/spotify-client -name '*.so*' -type f -exec chmod 0755 {{}} +
desktop-file-validate %{{buildroot}}/usr/share/applications/spotify.desktop
%check
cd %{{buildroot}}/usr/share/spotify-client
sha256sum --quiet -c .vendor-files.sha256
%files
/usr/share/spotify-client/
/usr/share/applications/spotify.desktop
/usr/share/icons/hicolor/*/apps/spotify-client.png
'''


def setup(args):
    if os.geteuid() == 0:
        raise SystemExit('Run setup as your regular user; only the final RPM installation needs administrator rights.')
    consent(args)
    for command in ('dpkg-deb', 'freshclam', 'clamscan', 'rpmbuild', 'desktop-file-validate', 'tar'):
        if not shutil.which(command):
            raise SystemExit('Missing local build tool: ' + command)
    record = metadata(HERE / 'source.json')
    version = record['RPMVersion']
    state = state_dir()
    output = state / version
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A lock prevents overlapping local builds from reusing a packaging number.
    import fcntl
    with (state / 'build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existing = [int(m.group(1)) for p in output.glob('*.x86_64.rpm')
                    if (m := re.fullmatch(re.escape('spotify-client-local-' + version) + r'-([0-9]+)[.]x86_64[.]rpm', p.name))]
        release = max([int(record.get('PackagingRelease', 1)) - 1, *existing]) + 1
        with tempfile.TemporaryDirectory(prefix='spotify-local-') as tmp:
            work = Path(tmp)
            deb = work / 'spotify.deb'
            download(record, deb)
            # Update signatures before extraction, then scan raw data and control scripts.
            env = dict(os.environ, SCAN_REPORT_DIR=str(output / 'scan-reports'))
            subprocess.run(['bash', str(HERE / 'scan_payload.sh'), '--update'], env=env, check=True)
            root = work / 'raw'
            subprocess.run(['dpkg-deb', '--raw-extract', str(deb), str(root)], check=True)
            for field, expected in [('Package', 'spotify-client'), ('Architecture', 'amd64')]:
                actual = subprocess.check_output(['dpkg-deb', '-f', str(deb), field], text=True).strip()
                if actual != expected:
                    raise ValueError('Unexpected DEB ' + field)
            actual_version = subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Version'], text=True).strip().split(':')[-1]
            if actual_version != version:
                raise ValueError('Unexpected DEB version')
            subprocess.run(['bash', str(HERE / 'scan_payload.sh'), '--scan', str(root), str(deb)], env=env, check=True)
            payload = work / 'payload'
            app = payload / 'usr/share/spotify-client'
            app.parent.mkdir(parents=True)
            shutil.move(str(root / 'usr/share/spotify'), app)
            manifest = []
            for file in sorted(app.rglob('*')):
                if file.is_file() and not file.is_symlink():
                    with file.open('rb') as stream:
                        hasher = hashlib.sha256()
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            hasher.update(block)
                        digest = hasher.hexdigest()
                    manifest.append(digest + '  ./' + str(file.relative_to(app)))
            (app / '.vendor-files.sha256').write_text('\n'.join(manifest) + '\n')
            shutil.copy2(app / '.vendor-files.sha256', output / 'scan-reports/vendor-files.sha256')
            for icon in (app / 'icons').glob('spotify-linux-*.png'):
                size = icon.stem.removeprefix('spotify-linux-')
                if not size.isdigit():
                    continue
                dest = payload / f'usr/share/icons/hicolor/{size}x{size}/apps/spotify-client.png'
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(icon, dest)
            desktop = payload / 'usr/share/applications/spotify.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('[Desktop Entry]\nType=Application\nName=Spotify\nExec=spotify %U\nIcon=spotify-client\nTerminal=false\nCategories=Audio;Music;Player;AudioVideo;\nMimeType=x-scheme-handler/spotify;\nStartupWMClass=spotify\n')
            top = work / 'rpmbuild'
            for folder in ('SOURCES', 'SPECS', 'BUILD', 'RPMS', 'SRPMS'):
                (top / folder).mkdir(parents=True)
            subprocess.run(['tar', '-czf', str(top / 'SOURCES/payload.tar.gz'), '-C', str(work), 'payload'], check=True)
            spec = top / 'SPECS/client.spec'
            match = re.search(r'libc6\s*\(>=\s*([0-9.]+)\)', record.get('Depends', ''))
            if not match:
                raise ValueError('No official libc6 dependency')
            spec.write_text(target_spec(version, release, match.group(1)))
            options = ['--nodeps'] if Path('/etc/debian_version').exists() else []
            with (output / 'rpm-build.log').open('w') as log:
                subprocess.run(['rpmbuild', '-bb', *options, '--define', f'_topdir {top}', '--define', 'dist %{nil}', '--define', '_binary_payload w3.zstdio', str(spec)], stdout=log, stderr=subprocess.STDOUT, check=True)
            for rpm in (top / 'RPMS').rglob('*.rpm'):
                dest = output / rpm.name
                shutil.copy2(rpm, dest)
                print('Local RPM:', dest)
                print('Install after reviewing it: sudo dnf install ' + str(dest))
                install_local(dest)


def launch(args):
    if not has_consent():
        consent(args)
    binary = Path('/usr/share/spotify-client/spotify')
    if not binary.is_file():
        raise SystemExit('Spotify is not built yet. Run spotify --setup to review the local-build instructions.')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'spotify'
    flags, assignments = [], []
    for name, collection in [('spotify-flags.conf', flags), ('spotify.env', assignments)]:
        path = config / name
        if path.is_file():
            collection.extend(line for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))
    env = os.environ.copy()
    for line in assignments:
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError('Invalid spotify.env assignment')
        env[key] = value
    env['LD_LIBRARY_PATH'] = str(binary.parent) + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    if 'LC_NUMERIC' not in env:
        try:
            locale.setlocale(locale.LC_NUMERIC, 'en_US.UTF-8')
            env['LC_NUMERIC'] = 'en_US.UTF-8'
        except locale.Error:
            env['LC_NUMERIC'] = 'C.UTF-8'
    for key in ('DESKTOP_SESSION', 'GNOME_DESKTOP_SESSION_ID'):
        env.pop(key, None)
    mode, debug, forwarded = env.get('SPOTIFY_GPU_MODE', 'auto'), env.get('SPOTIFY_DEBUG', '0'), []
    for arg in args:
        if arg == '--safe-mode': mode = 'software'
        elif arg.startswith('--gpu-mode='): mode = arg.split('=', 1)[1]
        elif arg == '--debug': debug = '1'
        elif arg == '--accept-spotify-terms': continue
        else: forwarded.append(arg)
    if debug in ('1', 'true'):
        flags.extend(['--enable-logging=stderr', '--v=1', '--show-console', '--debug-level=4'])
    os.execve('/bin/bash', ['bash', str(HERE / 'spotify-gpu.sh'), str(binary), mode, debug, '0', str(len(flags)), *flags, *forwarded], env)


if __name__ == '__main__':
    try:
        if '--setup' in sys.argv[1:]: setup(sys.argv[1:])
        elif '--help' in sys.argv[1:]: print('spotify [--setup --accept-spotify-terms] [--debug] [--safe-mode] [--gpu-mode=MODE] [URI]')
        else: launch(sys.argv[1:])
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit('spotify: ' + str(exc))
