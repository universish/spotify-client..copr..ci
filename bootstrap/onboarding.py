#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Offer the pinned channels in the desktop user's session, never as root."""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CLIENT = '/usr/bin/spot..fly..light'


def catalog(path=None):
    data = json.loads((path or HERE / 'source.json').read_text())
    bootstrap = data.get('Bootstrap', {})
    version, release = bootstrap.get('Version', ''), bootstrap.get('Release')
    if not re.fullmatch(r'[0-9]{2}[.][0-9]{2}[.][0-9]{2}', version) or not isinstance(release, int) or release < 1:
        raise ValueError('Missing installed bootstrap version information')
    for channel in ('stable', 'unstable'):
        if not re.fullmatch(r'[A-Za-z0-9.+~_-]+', data.get(channel, {}).get('RPMVersion', '')):
            raise ValueError('Missing pinned ' + channel + ' version')
    return data, f'{version}-{release}'


def state_directory():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'spot..fly..light-bootstrap'


def remember(path, identity, selection):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.onboarding-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump({'Bootstrap': identity, 'Selection': selection}, stream)
            stream.write('\n')
            stream.flush()
            os.fchmod(stream.fileno(), 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def setup_arguments(channel):
    if channel not in ('stable', 'unstable'):
        raise ValueError('Invalid channel selection')
    return [CLIENT, '--setup', *(['-unstable'] if channel == 'unstable' else [])]


def terminal_commands(command):
    # Each application receives an argv vector; no shell interprets catalog data.
    terminals = {
        'xdg-terminal-exec': ['--'],
        'ptyxis': ['--standalone', '--'],
        'gnome-terminal': ['--wait', '--'],
        'kgx': ['--'],
        'konsole': ['--separate', '-e'],
        'xfce4-terminal': ['--disable-server', '--execute'],
        'mate-terminal': ['--disable-factory', '--'],
        'xterm': ['-e'],
        'foot': ['--'],
        'alacritty': ['-e'],
        'kitty': ['--'],
    }
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    preferred = ('konsole',) if 'kde' in desktop else ('xfce4-terminal',) if 'xfce' in desktop else ()
    order = ['xdg-terminal-exec', *preferred, *terminals]
    seen = set()
    for name in order:
        if name in seen:
            continue
        seen.add(name)
        executable = shutil.which(name)
        if executable:
            yield [executable, *terminals[name], *command]


def open_terminal(channel):
    command = ['/usr/bin/python3', str(HERE / 'onboarding.py'), '--run-setup', channel]
    for arguments in terminal_commands(command):
        try:
            process = subprocess.Popen(arguments, start_new_session=True)
            try:
                status = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                return process
            if status == 0:
                return process
        except OSError:
            continue
    raise RuntimeError('No usable terminal was found. Run ' + ' '.join(setup_arguments(channel)) + ' in your terminal.')


def run_setup(channel):
    command = setup_arguments(channel)
    print('Spot..Light: running ' + ' '.join(command), flush=True)
    result = subprocess.run(command, check=False)
    print(f'\nSpot..Light setup exited with status {result.returncode}.', flush=True)
    try:
        input('Press Enter to close this terminal. ')
    except EOFError:
        pass
    return result.returncode


def offer():
    # No root-owned acceptance state, GUI authentication bypass or implicit build.
    if os.geteuid() == 0 or not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return 0
    zenity = shutil.which('zenity')
    if not zenity:
        return 0
    data, identity = catalog()
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    process = None
    with (directory / 'onboarding.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        marker = directory / 'onboarding.json'
        try:
            previous = json.loads(marker.read_text())
            if isinstance(previous, dict) and previous.get('Bootstrap') == identity:
                return 0
        except (FileNotFoundError, ValueError):
            pass
        result = subprocess.run([
            zenity, '--list', '--radiolist', '--title=Spot..Light: choose a client channel',
            '--text=Which Spotify client would you like to build and install?\nThe terminal will show the legal notice and every setup stage.',
            '--column=Choose', '--column=Channel', '--column=Spotify client version',
            '--print-column=2', '--ok-label=Open setup terminal', '--cancel-label=Not now',
            '--width=650', '--height=310',
            'TRUE', 'stable', data['stable']['RPMVersion'],
            'FALSE', 'unstable', data['unstable']['RPMVersion'],
        ], text=True, stdout=subprocess.PIPE, env=dict(os.environ, LC_ALL='C.UTF-8', LANGUAGE='en'), check=False)
        if result.returncode == 1:
            remember(marker, identity, 'dismissed')
            return 0
        if result.returncode != 0:
            # A missing/starting graphical session can try again at next login.
            return 0
        channel = result.stdout.strip()
        setup_arguments(channel)  # Validate the untrusted dialog output before spawning.
        try:
            process = open_terminal(channel)
        except RuntimeError as exc:
            subprocess.run([zenity, '--error', '--title=Spot..Light', '--text=' + str(exc)], check=False)
            return 1
        remember(marker, identity, channel)
    # Keep standalone terminal children alive in this user service's cgroup.
    # The chooser lock is released first; no setup or package-manager lock is held.
    if process is not None:
        process.wait()
    return 0


def main(args):
    if os.geteuid() == 0:
        return 0
    if len(args) == 2 and args[0] == '--run-setup':
        return run_setup(args[1])
    if args:
        raise ValueError('Unknown onboarding argument')
    return offer()


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('Spot..Light onboarding: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
