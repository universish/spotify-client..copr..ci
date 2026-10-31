#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Payload-free community bootstrap. Spotify is built only on the user's host."""
import hashlib
from http.client import HTTPException
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
BASES = ('https://download.spotify.com/debian', 'https://repository.spotify.com',
         'https://repository-origin.spotify.com',
         'https://deb.rug.nl/ppa/mirror/repository.spotify.com')
CURRENT_CHANNEL = 'stable'


def byte_progress(label, completed, total, started):
    elapsed = max(time.monotonic() - started, 0.001)
    speed = completed / elapsed
    percent = min(completed / total * 100, 100) if total else 100
    eta = f'{max(total - completed, 0) / speed:.0f}s' if speed else 'pending'
    print(f'{label}: {percent:.1f}% | {completed / 1048576:.1f}/{total / 1048576:.1f} MiB'
          f' | {speed / 1048576:.2f} MiB/s | elapsed {elapsed:.0f}s | ETA {eta}', flush=True)


@contextmanager
def phase(label, output, *, step=None, total=7):
    started = time.monotonic()
    stopped = threading.Event()
    guard = threading.Lock()
    prefix = f'[Step {step}/{total}] ' if step is not None else ''
    def report(message):
        with guard:
            print(message, flush=True)
            with (output / 'setup-progress.log').open('a') as log:
                log.write(datetime.now(timezone.utc).isoformat() + ' ' + message + '\n')
    def heartbeat():
        while not stopped.wait(5):
            report(prefix + label + f': still running, elapsed {time.monotonic() - started:.0f}s.')
    start_percent = f' ({(step - 1) / total * 100:.0f}% of steps complete)' if step else ''
    report(prefix + label + '...' + start_percent)
    watcher = threading.Thread(target=heartbeat, daemon=True)
    watcher.start()
    try:
        yield
    except BaseException:
        stopped.set(); watcher.join()
        report(prefix + f'{label}: stopped after {time.monotonic() - started:.1f}s.')
        raise
    else:
        stopped.set(); watcher.join()
        finish_percent = f' ({step / total * 100:.0f}% of steps complete)' if step else ''
        report(prefix + f'{label}: completed in {time.monotonic() - started:.1f}s.' + finish_percent)


def run_logged(args, path, env):
    with path.open('w') as log, subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                text=True, bufsize=1, env=env) as process:
        for line in process.stdout:
            print('rpm> ' + line, end='', flush=True)
            log.write(line); log.flush()
        if process.wait():
            raise subprocess.CalledProcessError(process.returncode, args)


def channel_option(args):
    return 'unstable' if any(arg in ('-unstable', '--unstable') for arg in args) else 'stable'


def active_channel():
    path = Path('/usr/share/spot..fly..light-client/.spot..fly..light-source.json')
    try:
        channel = json.loads(path.read_text())['Channel']
        if channel not in ('stable', 'unstable'):
            raise ValueError('Invalid installed channel')
        return channel
    except FileNotFoundError:
        return 'stable'


def validate_scan(record):
    scan = record.get('ScanAttestation', {})
    if (scan.get('SHA256') != record['SHA256'] or scan.get('Malware') != 'clean'
            or scan.get('PUA') not in ('clean', 'advisory')
            or scan.get('Scanner') != 'ClamAV'
            or not re.fullmatch(r'https://github[.]com/universish/spotify-client[.][.]copr[.][.]ci/actions/runs/[0-9]+', scan.get('RunURL', ''))
            or not scan.get('ScannedAt') or not scan.get('DatabaseVersion')):
        raise ValueError('Missing or mismatched successful CI scan evidence; refusing to build')


def state_dir():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'spot..fly..light-bootstrap'


def consent_digest():
    return hashlib.sha256((HERE / 'eula.txt').read_bytes()).hexdigest()


def approval_subject():
    record = metadata(HERE / 'source.json')
    release = str(record.get('PackagingRelease', 1))
    if not re.fullmatch('[1-9][0-9]*', release):
        raise ValueError('Invalid bootstrap packaging release')
    return {'version': record['RPMVersion'], 'release': release, 'deb_sha256': record['SHA256'], 'channel': record.get('Channel', 'stable')}


def installed_source():
    try:
        return json.loads(Path('/usr/share/spot..fly..light-client/.spot..fly..light-source.json').read_text())
    except (OSError, ValueError):
        return {}


def installed_current(minimum_release=None):
    subject = approval_subject()
    installed = installed_source()
    if installed.get('Channel') != subject.get('channel', 'stable') or installed.get('SHA256') != subject['deb_sha256']:
        return False
    result = subprocess.run(['rpm', '-q', '--qf', '%{VERSION}\\n%{RELEASE}\\n', 'spot-fly-light-client-local'], capture_output=True, text=True)
    fields = result.stdout.splitlines()
    if result.returncode or len(fields) != 2 or fields[0] != subject['version']:
        return False
    revision = re.fullmatch(r'([1-9][0-9]*)(?:[.].*)?', fields[1])
    required = max(int(subject['release']), int(minimum_release or 1))
    return bool(revision and int(revision[1]) >= required)


def pending_install():
    try:
        subject = approval_subject()
        folder = state_dir() / subject['version']
        record = json.loads((folder / 'pending-install.json').read_text())
        if record['package'] != subject:
            return None
        match = re.fullmatch(re.escape('spot-fly-light-client-local-' + subject['version']) + r'-([1-9][0-9]*)[.]x86_64[.]rpm', record['filename'])
        if not match or int(match[1]) < int(subject['release']):
            return None
        path = folder / record['filename']
        if path.is_symlink():
            return None
        verify(path, record)
        result = subprocess.run(['rpm', '-qp', '--qf', '%{NAME}\\n%{VERSION}\\n%{RELEASE}\\n', str(path)], capture_output=True, text=True)
        if result.returncode or result.stdout.splitlines() != ['spot-fly-light-client-local', subject['version'], match[1]]:
            return None
        return path, int(match[1])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remember_pending(path):
    with path.open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    record = {'package': approval_subject(), 'filename': path.name,
              'SHA256': digest.hexdigest(), 'Size': path.stat().st_size}
    destination = path.parent / 'pending-install.json'
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(record, stream)
    os.replace(temporary, destination)


def package_state():
    if not has_consent():
        return 'approve-wait'
    pending = pending_install()
    if pending and not installed_current(pending[1]):
        return 'install-wait'
    return 'OK' if installed_current() else 'build-wait'


def revoke_local_client():
    # Never remove the user's existing LPF/vendor package or the RPM transaction's
    # bootstrap. Only this project's separately named local target is eligible.
    (state_dir() / 'consent.json').unlink(missing_ok=True)
    installed = subprocess.run(['rpm', '-q', 'spot-fly-light-client-local'], capture_output=True).returncode == 0
    if installed:
        if not shutil.which('pkexec'):
            raise SystemExit('Consent declined. Client will not launch. Administrator removal required: sudo rpm -e spot-fly-light-client-local')
        result = subprocess.run(['pkexec', shutil.which('rpm'), '-e', 'spot-fly-light-client-local'])
        if result.returncode:
            raise SystemExit('Consent declined. Client will not launch. Removal was not authorized or failed; run sudo rpm -e spot-fly-light-client-local.')


def consent(args):
    notice = (HERE / 'eula.txt').read_text()
    print(notice, flush=True)
    accepted = '--accept-spotify-terms' in args
    if not accepted and shutil.which('zenity') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        print('Waiting for consent in the legal notice window...', flush=True)
        result = subprocess.run(['zenity', '--text-info', '--title=Spot..Light: legal notice and local installation consent',
                                 '--filename=' + str(HERE / 'eula.txt'), '--width=760', '--height=600',
                                 '--ok-label=Accept', '--cancel-label=Decline',
                                 '--checkbox=I have read this notice and the applicable Spotify terms; I request local installation.'],
                                env=dict(os.environ, LC_ALL='C.UTF-8', LANGUAGE='en'))
        accepted = result.returncode == 0
        if result.returncode == 1:
            revoke_local_client()
            raise SystemExit('Consent declined; download, build and launch cancelled.')
        if not accepted:
            raise SystemExit('Consent dialog failed; no rejection or package removal inferred. Retry spot..fly..light --setup.')
    if not accepted:
        raise SystemExit('Review the official terms, then run: spot..fly..light --setup --accept-spotify-terms')
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / 'consent.json'
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        json.dump({'notice_sha256': consent_digest(), 'package': approval_subject()}, stream)


def has_consent():
    try:
        record = json.loads((state_dir() / 'consent.json').read_text())
        return isinstance(record, dict) and record.get('notice_sha256') == consent_digest() and record.get('package') == approval_subject()
    except (OSError, ValueError, KeyError):
        return False


def transaction_action(path):
    candidate = subprocess.run(['rpm', '-qp', '--qf', '%{NAME}\\n%{VERSION}-%{RELEASE}\\n', str(path)], capture_output=True, text=True, check=True).stdout.splitlines()
    if len(candidate) != 2 or candidate[0] != 'spot-fly-light-client-local':
        raise ValueError('Unexpected local RPM identity')
    installed = subprocess.run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', 'spot-fly-light-client-local'], capture_output=True, text=True)
    if installed.returncode:
        return 'install'
    previous, target = installed.stdout.strip(), candidate[1]
    if any(not re.fullmatch(r'[A-Za-z0-9.+~^-]+', value) for value in (previous, target)):
        raise ValueError('Invalid local RPM version')
    # Delegate RPM version ordering to RPM itself; string sorting gets e.g. 1.10 wrong.
    expression = '%{lua: print(rpm.vercmp(' + json.dumps(target) + ',' + json.dumps(previous) + '))}'
    compared = int(subprocess.run(['rpm', '--eval', expression], capture_output=True, text=True, check=True).stdout.strip())
    return 'downgrade' if compared < 0 else 'reinstall' if compared == 0 else 'install'


def ensure_client_closed():
    for process in Path('/proc').glob('[0-9]*/exe'):
        try:
            executable = os.readlink(process).removesuffix(' (deleted)')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if executable.startswith(('/usr/share/spot..fly..light-client/', '/usr/share/sonicradle-client/', '/usr/share/spotify-client/')):
            raise SystemExit('Close all Spot..Light client processes before replacing the installed client.')


def migration_preflight():
    vendor = subprocess.run(['rpm', '-q', 'spotify-client'], capture_output=True)
    if vendor.returncode == 0:
        raise SystemExit('An existing vendor client conflicts with this local package. Review and remove spotify-client with your package manager before setup; no download or rebuild was started.')
    legacy = subprocess.run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}\\n%{URL}\\n%{SUMMARY}\\n', 'spotify-client-local'], capture_output=True, text=True)
    if legacy.returncode:
        return None
    fields = legacy.stdout.splitlines()
    bootstrap = subprocess.run(['rpm', '-q', '--qf', '%{URL}', 'spotify'], capture_output=True, text=True)
    owner = subprocess.run(['rpm', '-qf', '--qf', '%{NAME}', '/usr/share/spotify-client/.vendor-files.sha256'], capture_output=True, text=True)
    if (len(fields) != 3 or not re.fullmatch(r'[A-Za-z0-9.+~^-]+', fields[0])
            or fields[1:] != ['https://www.spotify.com/download/linux/', 'Locally built proprietary Spotify client']
            or bootstrap.returncode or bootstrap.stdout.strip() != 'https://github.com/universish/spotify-client..copr..ci'
            or owner.returncode or owner.stdout.strip() != 'spotify-client-local'):
        raise SystemExit('An unrecognized spotify-client-local package is installed. Review its origin and resolve the conflict with your package manager before setup; no download or rebuild was started.')
    return fields[0]


def previous_named_target():
    previous = subprocess.run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}\\n%{URL}\\n%{SUMMARY}\\n', 'sonicradle-client-local'], capture_output=True, text=True)
    if previous.returncode:
        return None
    fields = previous.stdout.splitlines()
    owner = subprocess.run(['rpm', '-qf', '--qf', '%{NAME}', '/usr/share/sonicradle-client/.vendor-files.sha256'], capture_output=True, text=True)
    if (len(fields) != 3 or not re.fullmatch(r'[A-Za-z0-9.+~^-]+', fields[0])
            or fields[1:] != ['https://www.spotify.com/download/linux/', 'Locally built proprietary Spotify client']
            or owner.returncode or owner.stdout.strip() != 'sonicradle-client-local'):
        raise SystemExit('An unrecognized previous local package is installed. Review its origin and resolve the conflict before setup.')
    return fields[0]


def install_local(path):
    ensure_client_closed()
    legacy = migration_preflight()
    previous = previous_named_target()
    if legacy or previous:
        obsoletes = subprocess.run(['rpm', '-qp', '--obsoletes', str(path)], capture_output=True, text=True, check=True).stdout.splitlines()
        if ((legacy and 'spotify-client-local = ' + legacy not in obsoletes)
                or (previous and 'sonicradle-client-local = ' + previous not in obsoletes)):
            raise SystemExit('This cached RPM predates the migration fix. Upgrade spot-fly-light, then run spot..fly..light --rebuild. Your existing client and cached RPM have been preserved.')
    if not shutil.which('pkexec'):
        raise SystemExit('Local RPM built. Install it after review with your package manager: ' + str(path))
    action = transaction_action(path)
    for tool, options in [('dnf', [action, '-y']),
                          ('zypper', ['install', '--oldpackage', '--force']),
                          ('urpmi', ['--downgrade'] if action == 'downgrade' else ['--replacepkgs'] if action == 'reinstall' else [])]:
        manager = shutil.which(tool)
        if manager:
            try:
                subprocess.run(['pkexec', manager, *options, str(path)], check=True)
            except subprocess.CalledProcessError:
                channel = ' -unstable' if CURRENT_CHANNEL == 'unstable' else ''
                raise SystemExit('Package installation did not complete. The verified RPM is preserved at ' + str(path)
                                 + '. Resolve the package-manager error, then retry without downloading or rebuilding: spot..fly..light --install' + channel) from None
            return
    raise SystemExit('Local RPM built; install using your system package manager: ' + str(path))


def metadata(path, channel=None):
    record = json.loads(Path(path).read_text())
    channel = channel or CURRENT_CHANNEL
    if 'Package' not in record:
        if channel not in record:
            raise ValueError('This bootstrap has no scanned metadata for ' + channel)
        record = record[channel]
    if record.get('Channel', 'stable') != channel:
        raise ValueError('Pinned metadata does not match the requested channel')
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
    total, completed = path.stat().st_size, 0
    started = last_update = time.monotonic()
    byte_progress('Checking SHA256 of ' + path.name, 0, total, started)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            completed += len(block)
            now = time.monotonic()
            if now - last_update >= 1:
                byte_progress('Checking SHA256 of ' + path.name, completed, total, started)
                last_update = now
    byte_progress('Checking SHA256 of ' + path.name, completed, total, started)
    if path.stat().st_size != int(record['Size']) or digest.hexdigest() != record['SHA256']:
        raise ValueError('DEB size/SHA256 mismatch; stopping before extraction')


def download(record, path, cache=None):
    if os.environ.get('SPOT_FLY_LIGHT_DEB_FILE'):
        cached = Path(os.environ['SPOT_FLY_LIGHT_DEB_FILE'])
        print('Verifying the configured DEB cache against the official size and SHA256...', flush=True)
        verify(cached, record)
        shutil.copy2(cached, path)
        return
    cached = None
    if cache is not None:
        if not re.fullmatch(r'[0-9a-f]{64}', record['SHA256']):
            raise ValueError('Invalid DEB cache key')
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        cached = cache / (record['SHA256'] + '.deb')
        if cached.is_dir() and not cached.is_symlink():
            print('The private cache entry is a directory; preserving it and downloading without cache.', flush=True)
            cached = None
        if cached is not None and (cached.exists() or cached.is_symlink()):
            print('Checking the private DEB cache...', flush=True)
            try:
                if cached.is_symlink():
                    raise ValueError('Unexpected cache symlink')
                verify(cached, record)
            except (OSError, ValueError):
                cached.unlink(missing_ok=True)
                print('Cached DEB failed verification; downloading a fresh official copy.', flush=True)
            else:
                shutil.copy2(cached, path)
                print('Using the verified private DEB cache; no download needed.', flush=True)
                return
    errors = []
    for base in BASES:
        try:
            kind = 'official source' if base in BASES[:3] else 'community mirror (official hash required)'
            print('Downloading pinned DEB from ' + kind + ': ' + base, flush=True)
            with urlopen(base + '/' + record['Filename'], timeout=60) as stream, path.open('wb') as output:
                received = 0
                started = last_update = time.monotonic()
                byte_progress('Download', 0, int(record['Size']), started)
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    output.write(block)
                    received += len(block)
                    now = time.monotonic()
                    if now - last_update >= 1:
                        byte_progress('Download', received, int(record['Size']), started)
                        last_update = now
                byte_progress('Download', received, int(record['Size']), started)
            print('Verifying official DEB size and SHA256...', flush=True)
            verify(path, record)
            if cached is not None:
                staging = None
                try:
                    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as temporary:
                        staging = Path(temporary.name)
                    shutil.copyfile(path, staging)
                    os.replace(staging, cached)
                except OSError:
                    print('Could not retain the private DEB cache; continuing with the verified download.', flush=True)
                finally:
                    if staging is not None:
                        staging.unlink(missing_ok=True)
            return
        except (OSError, ValueError, HTTPException) as exc:
            errors.append(type(exc).__name__)
            path.unlink(missing_ok=True)
            print('Download or integrity check failed; trying the next configured source.', flush=True)
    raise RuntimeError('Configured DEB download sources failed: ' + ', '.join(errors))


def target_spec(version, release, glibc, legacy_release=None, previous_release=None):
    if not re.fullmatch(r'[0-9]+(?:[.][0-9]+)*', glibc):
        raise ValueError('Missing official glibc requirement')
    if legacy_release is not None and not re.fullmatch(r'[A-Za-z0-9.+~^-]+', legacy_release):
        raise ValueError('Invalid legacy package release')
    if previous_release is not None and not re.fullmatch(r'[A-Za-z0-9.+~^-]+', previous_release):
        raise ValueError('Invalid previous package release')
    migration = f'Obsoletes: spotify-client-local = {legacy_release}\n' if legacy_release else ''
    if previous_release:
        migration += f'Obsoletes: sonicradle-client-local = {previous_release}\n'
    return f'''%global debug_package %{{nil}}
%global __strip /bin/true
%global __brp_strip /bin/true
%global __brp_add_determinism /bin/true
%global __provides_exclude_from ^%{{_datadir}}/spot[.][.]fly[.][.]light-client/.*$
%global __requires_exclude ^(libcef|libEGL|libGLESv2|libvk_swiftshader|libvulkan)[.]so.*$
Name: spot-fly-light-client-local
Version: {version}
Release: {release}
Summary: Locally built proprietary Spotify client
License: LicenseRef-Spotify-Proprietary
URL: https://www.spotify.com/download/linux/
ExclusiveArch: x86_64 x86_64_v2
Source0: payload.tar
BuildRequires: coreutils
BuildRequires: desktop-file-utils
Requires: spot-fly-light
Requires: glibc >= {glibc}
Requires: hicolor-icon-theme
Requires: /usr/bin/dbus-launch
Requires: /usr/bin/locale
Requires: (glibc-langpack-en or glibc-locale or locales-en)
Requires: libayatana-appindicator3.so.1()(64bit)
Conflicts: spotify-client, spotify-client-local
{migration}%description
Built on this computer from Spotify's verified DEB. Not for redistribution.
%prep
%setup -q -n payload
%install
mkdir -p %{{buildroot}}
cp -a usr %{{buildroot}}/
find %{{buildroot}}/usr/share/spot..fly..light-client -type d -exec chmod 0755 {{}} +
find %{{buildroot}}/usr/share/spot..fly..light-client -type f -exec chmod go-w {{}} +
find %{{buildroot}}/usr/share/spot..fly..light-client -name '*.so*' -type f -exec chmod 0755 {{}} +
desktop-file-validate %{{buildroot}}/usr/share/applications/spot..fly..light.desktop
%check
cd %{{buildroot}}/usr/share/spot..fly..light-client
sha256sum --quiet -c .vendor-files.sha256
%files
/usr/share/spot..fly..light-client/
/usr/share/applications/spot..fly..light.desktop
/usr/share/icons/hicolor/*/apps/spot..fly..light.png
'''


def next_release(record, output):
    version = record['RPMVersion']
    # Preserve the counter across this project's rename, including private rebuilds.
    state_root = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    legacy = state_root / 'sonicradle-bootstrap' / version
    revisions = [int(record.get('PackagingRelease', 1)) - 1]
    for directory, name in ((output, 'spot-fly-light'), (legacy, 'sonicradle'),
                            (state_root / 'spotify-bootstrap' / version, 'spotify')):
        pattern = re.escape(name + '-client-local-' + version) + r'-([1-9][0-9]*)[.]x86_64[.]rpm'
        revisions.extend(int(match[1]) for path in directory.glob('*.x86_64.rpm')
                         if (match := re.fullmatch(pattern, path.name)))
    for name in ('spot-fly-light-client-local', 'sonicradle-client-local', 'spotify-client-local'):
        result = subprocess.run(['rpm', '-q', '--qf', '%{VERSION}\\n%{RELEASE}\\n', name], capture_output=True, text=True)
        fields = result.stdout.splitlines()
        if result.returncode == 0 and len(fields) == 2 and fields[0] == version:
            match = re.fullmatch(r'([1-9][0-9]*)(?:[.].*)?', fields[1])
            if match:
                revisions.append(int(match[1]))
    return max(revisions) + 1


def user_configuration():
    root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    flags, assignments = [], []
    for name, collection in [('flags.conf', flags), ('environment.conf', assignments)]:
        path = root / 'spot..fly..light' / name
        if not path.exists():
            path = root / 'sonicradle' / name
        if not path.exists():
            path = root / 'spotify' / name
        if path.is_file():
            collection.extend(line for line in path.read_text().splitlines()
                              if line.strip() and not line.lstrip().startswith('#'))
    return flags, assignments


def setup(args):
    if os.geteuid() == 0:
        raise SystemExit('Run setup as your regular user; only the final RPM installation needs administrator rights.')
    global CURRENT_CHANNEL
    CURRENT_CHANNEL = channel_option(args)
    if not has_consent():
        consent(args)
    for command in ('dpkg-deb', 'rpmbuild', 'desktop-file-validate', 'tar'):
        if not shutil.which(command):
            raise SystemExit('Missing local build tool: ' + command)
    record = metadata(HERE / 'source.json')
    validate_scan(record)
    version = record['RPMVersion']
    state = state_dir()
    output = state / version
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A lock prevents overlapping local builds from reusing a packaging number.
    import fcntl
    with (state / 'build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print('Checking for a verified pending local RPM...', flush=True)
        pending = pending_install()
        steps = 2 if pending and '--rebuild' not in args else 7
        with phase('Checking installed package compatibility', output, step=1, total=steps):
            legacy_release = migration_preflight()
            previous_release = previous_named_target()
        if '--rebuild' not in args and pending:
            if not installed_current(pending[1]):
                with phase('Installing the verified cached RPM', output, step=2, total=2):
                    install_local(pending[0])
            else:
                print(CURRENT_CHANNEL + ' client is already current. Setup is 100% complete; remaining steps are unnecessary.')
            return
        if '--install' in args:
            raise SystemExit('No verified pending RPM. Run spot..fly..light --setup to build it.')
        if '--rebuild' not in args and installed_current():
            print(CURRENT_CHANNEL + ' client is already current. Setup is 100% complete; remaining steps are unnecessary.')
            return
        ensure_client_closed()
        (output / 'pending-install.json').unlink(missing_ok=True)
        release = next_release(record, output)
        with tempfile.TemporaryDirectory(prefix='spot..fly..light-local-') as tmp:
            work = Path(tmp)
            deb = work / 'spotify.deb'
            print('ClamAV scanning was completed in GitHub Actions. Local setup only verifies and packages the source.', flush=True)
            with phase('Obtaining and verifying the official DEB', output, step=2):
                download(record, deb, cache=state / 'downloads')
            # CI scanned these exact bytes. Only integrity verification runs locally.
            with phase('Extracting and checking the DEB', output, step=3):
                root = work / 'raw'
                subprocess.run(['dpkg-deb', '--raw-extract', str(deb), str(root)], check=True)
                for field, expected in [('Package', 'spotify-client'), ('Architecture', 'amd64')]:
                    actual = subprocess.check_output(['dpkg-deb', '-f', str(deb), field], text=True).strip()
                    if actual != expected:
                        raise ValueError('Unexpected DEB ' + field)
                actual_version = subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Version'], text=True).strip().split(':')[-1]
                if actual_version != version:
                    raise ValueError('Unexpected DEB version')
            with phase('Preserving and hashing original application files', output, step=4):
                payload = work / 'payload'
                app = payload / 'usr/share/spot..fly..light-client'
                app.parent.mkdir(parents=True)
                shutil.move(str(root / 'usr/share/spotify'), app)
                manifest = []
                vendor_files = [file for file in sorted(app.rglob('*')) if file.is_file() and not file.is_symlink()]
                hash_started = last_hash_update = time.monotonic()
                for index, file in enumerate(vendor_files, 1):
                    if file.is_file() and not file.is_symlink():
                        with file.open('rb') as stream:
                            hasher = hashlib.sha256()
                            for block in iter(lambda: stream.read(1024 * 1024), b''):
                                hasher.update(block)
                            digest = hasher.hexdigest()
                        manifest.append(digest + '  ./' + str(file.relative_to(app)))
                    now = time.monotonic()
                    if now - last_hash_update >= 1 or index == len(vendor_files):
                        print(f'Hashing vendor files: {index}/{len(vendor_files)} ({index / len(vendor_files) * 100:.1f}%) | {file.relative_to(app)} | elapsed {now - hash_started:.1f}s', flush=True)
                        last_hash_update = now
                (app / '.vendor-files.sha256').write_text('\n'.join(manifest) + '\n')
                shutil.copy2(app / '.vendor-files.sha256', output / 'vendor-files.sha256')
                (app / '.spot..fly..light-source.json').write_text(json.dumps(record, indent=2) + '\n')
                for icon in (app / 'icons').glob('spotify-linux-*.png'):
                    size = icon.stem.removeprefix('spotify-linux-')
                    if not size.isdigit():
                        continue
                    dest = payload / f'usr/share/icons/hicolor/{size}x{size}/apps/spot..fly..light.png'
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(icon, dest)
                desktop = payload / 'usr/share/applications/spot..fly..light.desktop'
                desktop.parent.mkdir(parents=True)
                desktop.write_text('[Desktop Entry]\nType=Application\nName=Spotify via Spot..Light (unofficial)\nExec=spot..fly..light %U\nIcon=spot..fly..light\nTerminal=false\nCategories=Audio;Music;Player;AudioVideo;\nMimeType=x-scheme-handler/spotify;\nStartupWMClass=spotify\n')
            top = work / 'rpmbuild'
            for folder in ('SOURCES', 'SPECS', 'BUILD', 'RPMS', 'SRPMS', 'tmp'):
                (top / folder).mkdir(parents=True)
            with phase('Staging the local RPM source', output, step=5):
                # The final RPM uses zstd; avoid compressing this temporary tar twice.
                subprocess.run(['tar', '-cf', str(top / 'SOURCES/payload.tar'), '-C', str(work), 'payload'], check=True)
            spec = top / 'SPECS/client.spec'
            match = re.search(r'libc6\s*\(>=\s*([0-9.]+)\)', record.get('Depends', ''))
            if not match:
                raise ValueError('No official libc6 dependency')
            spec.write_text(target_spec(version, release, match.group(1), legacy_release, previous_release))
            options = ['--nodeps'] if Path('/etc/debian_version').exists() else []
            print('RPM build details: ' + str(output / 'rpm-build.log'), flush=True)
            with phase('Building and verifying the local RPM (no antivirus scan)', output, step=6):
                run_logged(['rpmbuild', '-bb', '--target', 'x86_64', *options, '--define', f'_topdir {top}', '--define', f'_tmppath {top / "tmp"}', '--define', 'dist %{nil}', '--define', '_binary_payload w3.zstdio', str(spec)],
                           output / 'rpm-build.log', dict(os.environ, LC_ALL='C.UTF-8', LANGUAGE='en'))
            for rpm in (top / 'RPMS').rglob('*.rpm'):
                dest = output / rpm.name
                shutil.copy2(rpm, dest)
                print('Local RPM:', dest)
                print('Install after reviewing it: sudo dnf install ' + str(dest))
                remember_pending(dest)
                with phase('Installing the local RPM through the package manager', output, step=7):
                    install_local(dest)


def launch(args):
    global CURRENT_CHANNEL
    if '-unstable' in args or '--unstable' in args:
        raise SystemExit('Select a channel with spot..fly..light --setup -unstable or spot..fly..light --update -unstable.')
    CURRENT_CHANNEL = active_channel()
    if not has_consent():
        consent(args)
    if not installed_current():
        raise SystemExit('The local client is missing or outdated. Run spot..fly..light --setup to approve, build and install the selected version.')
    binary = Path('/usr/share/spot..fly..light-client/spotify')
    if not binary.is_file():
        raise SystemExit('Spotify is not built yet. Run spot..fly..light --setup to review the local-build instructions.')
    flags, assignments = user_configuration()
    env = os.environ.copy()
    for line in assignments:
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError('Invalid environment.conf assignment')
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
    mode = env.get('SPOT_FLY_LIGHT_GPU_MODE', env.get('SONICRADLE_GPU_MODE', env.get('SPOTIFY_GPU_MODE', 'auto')))
    debug = env.get('SPOT_FLY_LIGHT_DEBUG', env.get('SONICRADLE_DEBUG', env.get('SPOTIFY_DEBUG', '0')))
    forwarded = []
    for arg in args:
        if arg == '--safe-mode': mode = 'software'
        elif arg.startswith('--gpu-mode='): mode = arg.split('=', 1)[1]
        elif arg == '--debug': debug = '1'
        elif arg == '--accept-spotify-terms': continue
        else: forwarded.append(arg)
    if debug in ('1', 'true'):
        flags.extend(['--enable-logging=stderr', '--v=1', '--show-console', '--debug-level=4'])
    import fcntl
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    launch_lock = (directory / 'build.lock').open('a')
    try:
        fcntl.flock(launch_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('A local client build or replacement is in progress; retry after it finishes.')
    os.set_inheritable(launch_lock.fileno(), True)
    try:
        os.execve('/bin/bash', ['bash', str(HERE / 'spot..fly..light-gpu.sh'), str(binary), mode, debug, '0', str(len(flags)), *flags, *forwarded], env)
    finally:
        launch_lock.close()


def client_versions():
    catalog = json.loads((HERE / 'source.json').read_text())
    info = catalog.get('Bootstrap', {})
    print('Spot..Light installer: ' + str(info.get('Version', 'legacy')) + '-' + str(info.get('Release', '?')))
    if info.get('PackagedAt'):
        print('Packaged at: ' + info['PackagedAt'] + ' (' + info.get('Timezone', 'Europe/Stockholm') + ')')
    for channel in ('stable', 'unstable'):
        record = metadata(HERE / 'source.json', channel)
        print(f"Spotify {channel}: {record['RPMVersion']} (local packaging revision {record.get('PackagingRelease', 1)})")
        print('  Install: spot..fly..light --setup' + (' -unstable' if channel == 'unstable' else ''))
    print('These are the scanned versions pinned by this installed helper. Update spot-fly-light to obtain newer source metadata.')


def help_text():
    return '''Spot..Light — independent local installer and launcher
Usage: spot..fly..light [OPTION] [URI]
Alias: spot-fly-light accepts the same options.

  (no option)                  Launch the installed client after checking consent and version.
  --setup                      Review the notice, build and install pinned Spotify stable.
  --setup -unstable            Build and install the pinned Spotify unstable/testing client.
  --update                     Install the stable version pinned by this installed helper.
  --update -unstable           Install the unstable version pinned by this installed helper.
  -unstable, --unstable        Select testing for setup/update/install/rebuild only.
  --client-versions, -cl.ver   Show installer date/version and both available Spotify versions.
  --status                     Show the installed channel and approval/build/install state.
  --debug                      Launch with detailed GPU/client logging in the terminal.
  --safe-mode                  Launch using software rendering for graphics troubleshooting.
  --gpu-mode=MODE             Select auto, nvidia, mesa or software rendering.
  --install                    Retry installing a verified cached RPM without rebuilding.
  --rebuild                    Build another local RPM of the selected pinned version.
  --accept-spotify-terms       Explicit command-line consent after reviewing the notice.
  --help, -h                   Show this help without downloading, installing or launching.

Examples:
  spot..fly..light --client-versions
  spot-fly-light --help
  spot..fly..light --setup
  spot..fly..light --setup -unstable
  spot..fly..light --update -unstable
  spot..fly..light --debug
  spot..fly..light --safe-mode

Setup runs as your regular user; the package manager asks for administrator
authorization only for installation. Antivirus scanning runs in GitHub Actions.
--update uses this helper's pinned catalog; update spot-fly-light with your package
manager first to obtain newly published Spotify source versions.'''


def main(args=None):
    global CURRENT_CHANNEL
    args = sys.argv[1:] if args is None else args
    if any(option in args for option in ('--help', '-h')):
        print(help_text())
    elif any(option in args for option in ('--client-versions', '-cl.ver')):
        client_versions()
    elif any(option in args for option in ('--setup', '--install', '--rebuild', '--update')):
        setup(args)
    elif '--status' in args:
        CURRENT_CHANNEL = active_channel()
        print(CURRENT_CHANNEL + ': ' + package_state())
    else:
        launch(args)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit('spot..fly..light: ' + str(exc))
