#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Mirror font rules into a private, source-specific Fontconfig configuration.

Every include is resolved before launch and every cache directive is replaced.
Neither the host's font files nor its shared caches are changed. The client
creates caches using its own Fontconfig implementation, including embedded CEF.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import uuid
import xml.etree.ElementTree as ET

MAX_FILES = 1024
MAX_BYTES = 8 * 1024 * 1024


def _home(env):
    return Path(env.get('HOME') or Path.home()).absolute()


def _xdg(env, name, default):
    value = Path(env.get(name) or default)
    if not value.is_absolute():
        raise ValueError(name + ' must be an absolute directory')
    return value


def _expand(value, env):
    if value == '~' or value.startswith('~/'):
        return str(_home(env)) + value[1:]
    return value


class Configuration:
    def __init__(self, env, source_config):
        self.env = env
        self.main = Path(source_config).absolute()
        self.sources = {}
        self.documents = {}
        self.stack = set()
        self.total = 0
        self.search = [Path(p) for p in env.get('FONTCONFIG_PATH', '').split(':') if p]
        self.search += [Path('/etc/fonts')]
        self.data = _xdg(env, 'XDG_DATA_HOME', _home(env) / '.local/share')
        self.config = _xdg(env, 'XDG_CONFIG_HOME', _home(env) / '.config')

    def path(self, value, prefix, owner, *, include=False):
        value = _expand(value.strip(), self.env)
        path = Path(value)
        if path.is_absolute():
            return path
        if prefix == 'relative':
            return owner.parent / path
        if prefix == 'xdg':
            return (self.config if include else self.data) / path
        if prefix not in ('default', 'cwd'):
            raise ValueError('Unsupported Fontconfig path prefix: ' + prefix)
        if include and prefix != 'cwd':
            return next((base / path for base in self.search if (base / path).exists()), self.search[0] / path)
        return Path.cwd() / path

    def load(self, path):
        path = path.absolute()
        canonical = path.resolve(strict=True)
        # Native Fontconfig deduplicates real filenames, including aliases
        # symlinked into multiple conf.d directories. Give them one snapshot.
        name = hashlib.sha256(str(canonical).encode()).hexdigest() + '.conf'
        if canonical in self.stack:
            # Fontconfig itself skips already-loaded includes. Omit a recursive
            # edge rather than reproducing an include loop in a new location.
            return None
        if name in self.documents:
            return name
        raw = path.read_bytes()
        self.total += len(raw)
        if len(self.sources) >= MAX_FILES or self.total > MAX_BYTES:
            raise ValueError('Fontconfig configuration exceeds the snapshot limit')
        if b'<!ENTITY' in raw:
            raise ValueError('Fontconfig entity declarations are not supported in a private snapshot')
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ValueError('Cannot parse Fontconfig configuration ' + str(path) + ': ' + str(exc)) from None
        if root.tag != 'fontconfig':
            raise ValueError('Unexpected Fontconfig document root: ' + str(path))
        self.sources[str(path)] = hashlib.sha256(raw).hexdigest()
        self.stack.add(canonical)
        try:
            for parent in list(root.iter()):
                for index, child in reversed(list(enumerate(list(parent)))):
                    if child.tag == 'cachedir':
                        parent.remove(child)
                    elif child.tag == 'include':
                        target = self.path(child.text or '', child.get('prefix', 'default'), path, include=True)
                        if not target.exists():
                            if child.get('ignore_missing', 'no') == 'yes':
                                parent.remove(child)
                                self.sources['missing:' + str(target)] = None
                                continue
                            raise ValueError('Required Fontconfig include is missing: ' + str(target))
                        files = sorted((p for p in target.iterdir() if re.fullmatch(r'[0-9].*[.]conf', p.name)), key=lambda p: p.name) if target.is_dir() else [target]
                        includes = []
                        for item in files:
                            if child.get('ignore_missing', 'no') == 'yes' and not item.exists():
                                # Optional conf.d directories commonly contain
                                # stale symlinks after a font package removal.
                                self.sources['missing:' + str(item)] = None
                                continue
                            mapped = self.load(item)
                            if mapped:
                                entry = ET.Element('include', {k: v for k, v in child.attrib.items() if k not in ('prefix', 'ignore_missing')})
                                entry.set('ignore_missing', 'no')
                                entry.text = '@PRIVATE_CONFIG@/' + mapped
                                includes.append(entry)
                        parent.remove(child)
                        for entry in reversed(includes):
                            parent.insert(index, entry)
                    elif child.tag in ('dir', 'remap-dir'):
                        child.text = str(self.path(child.text or '', child.get('prefix', 'default'), path))
                        child.attrib.pop('prefix', None)
                        if child.get('as-path', '').startswith('~'):
                            child.set('as-path', _expand(child.get('as-path'), self.env))
            self.documents[name] = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            return name
        finally:
            self.stack.remove(canonical)


def _private_directory(path):
    if path.is_symlink():
        raise ValueError('Private Fontconfig directory is a symbolic link')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('Private Fontconfig directory is not safely owned')


def _atomic(path, contents):
    if path.is_symlink():
        raise ValueError('Private Fontconfig file is a symbolic link')
    if path.is_file() and path.read_bytes() == contents:
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        out.write(contents)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_private_caches(cache, folder):
    rejected = []
    for path in cache.iterdir():
        match = re.search(r'[.]cache-([0-9]+)$', path.name)
        if not match:
            continue
        valid = False
        try:
            target = path.resolve(strict=True)
            if target.parent == cache and target.is_file():
                with target.open('rb') as source:
                    header = source.read(8)
                if len(header) == 8:
                    valid = any(struct.unpack(order + 'II', header) == (0xfc02fc04, int(match[1]))
                                for order in ('<', '>'))
        except (OSError, RuntimeError):
            pass
        if not valid:
            quarantine = folder / 'rejected-cache'
            _private_directory(quarantine)
            os.replace(path, quarantine / (path.name + '.' + uuid.uuid4().hex))
            rejected.append(path.name)
    return rejected


def prepare_fontconfig(env, record, profile, *, source_config=None, cache_root=None):
    """Return ``(child environment, diagnostics)`` without running a font tool."""
    child = dict(env)
    if child.get('FONTCONFIG_SYSROOT'):
        raise ValueError('A custom FONTCONFIG_SYSROOT needs a matching private Fontconfig profile')
    configured = source_config or child.get('FONTCONFIG_FILE') or '/etc/fonts/fonts.conf'
    path = Path(_expand(str(configured), child))
    if not path.is_absolute():
        directories = [Path(p) for p in child.get('FONTCONFIG_PATH', '').split(':') if p] + [Path('/etc/fonts')]
        path = next((base / path for base in directories if (base / path).is_file()), directories[0] / path)
    tree = Configuration(child, path)
    main = tree.load(path)
    source_hash = record.get('SHA256')
    if not isinstance(source_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', source_hash):
        raise ValueError('The installed client source hash is required for Fontconfig isolation')
    identity = {'schema': 1, 'helper': profile['Name'], 'channel': record.get('Channel', 'stable'),
                'source_sha256': source_hash, 'configuration': tree.sources,
                'documents': {name: hashlib.sha256(data).hexdigest() for name, data in tree.documents.items()}}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    base = (Path(cache_root) if cache_root is not None else _xdg(child, 'XDG_CACHE_HOME', _home(child) / '.cache') / profile['Name'] / 'fontconfig').absolute()
    _private_directory(base)
    folder = base / digest
    _private_directory(folder)
    config, cache = folder / 'config', folder / 'cache'
    _private_directory(config)
    _private_directory(cache)
    lock_path = folder / 'prepare.lock'
    if lock_path.is_symlink():
        raise ValueError('Private Fontconfig lock is a symbolic link')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rejected = _validate_private_caches(cache, folder)
        for name, data in tree.documents.items():
            root = ET.fromstring(data)
            for included in root.iter('include'):
                if included.text and included.text.startswith('@PRIVATE_CONFIG@/'):
                    included.text = str(config / included.text.removeprefix('@PRIVATE_CONFIG@/'))
            if name == main:
                entry = ET.SubElement(root, 'cachedir')
                entry.text = str(cache)
            _atomic(config / name, ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n')
        _atomic(folder / 'source.json', (json.dumps(identity, indent=2, sort_keys=True) + '\n').encode())
    child['FONTCONFIG_FILE'] = str(config / main)
    child['FONTCONFIG_PATH'] = str(config)
    # Never bypass Fontconfig's compatibility guard, even if inherited from an
    # old workaround. The client generates its own correctly formatted caches.
    child.pop('FONTCONFIG_NO_CHECK_CACHE_VERSION', None)
    info = {'Configuration': child['FONTCONFIG_FILE'], 'Cache': str(cache),
            'Identity': digest, 'SourceFiles': len(tree.sources), 'CacheWriter': 'client Fontconfig backend',
            'RejectedCacheEntries': rejected}
    return child, info
