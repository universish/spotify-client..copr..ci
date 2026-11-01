#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Validated RPM identities and isolated paths for current and archive helpers."""
from datetime import datetime
import re
from zoneinfo import ZoneInfo

ZONE = 'Europe/Stockholm'
CURRENT_NAME = 'spot-fly-light'
NUMERIC = r'[0-9]+(?:[.][0-9]+){3}'


def parse_debian_version(raw):
    """Preserve vendor identity; map Debian revision into RPM's hyphen-free Version."""
    if not isinstance(raw, str):
        raise ValueError('Invalid Debian version')
    match = re.fullmatch(r'(?:(?P<epoch>[0-9]+):)?(?P<upstream>(?P<numeric>' + NUMERIC
        + r')(?:[.]g(?P<commit>[0-9a-fA-F]+)(?P<build_suffix>(?:[.][0-9]+)*))?)'
          r'(?:-(?P<revision>[A-Za-z0-9.+~]+))?', raw)
    if not match:
        raise ValueError('Unsupported Spotify Debian version: ' + raw)
    result = match.groupdict()
    result.update(raw=raw, epoch=result['epoch'] or '0', revision=result['revision'] or '',
                  commit=result['commit'] or '', build_suffix=result['build_suffix'] or '')
    # Epoch is retained independently. The historic revision belongs to the
    # source version, not the community RPM's separately incremented Release.
    result['rpm_version'] = result['upstream'] + ('.deb' + result['revision'] if result['revision'] else '')
    return result


def source_version(record):
    raw = record.get('DebianVersion', record.get('Version', record.get('RPMVersion', '')))
    if not record.get('DebianVersion') and not record.get('Version') and re.fullmatch(r'[A-Za-z0-9.+~]+', raw):
        return {'raw': raw, 'upstream': raw, 'numeric': raw.split('.g', 1)[0], 'commit': '',
                'build_suffix': '', 'epoch': '0', 'revision': '', 'rpm_version': raw}
    parsed = parse_debian_version(raw)
    if record.get('DebianVersion') and record.get('Version') and record['DebianVersion'] != record['Version']:
        raise ValueError('Conflicting full Debian versions')
    return parsed


def archive_name(catalog):
    stable, unstable = (source_version(catalog[channel])['numeric'] for channel in ('stable', 'unstable'))
    if not re.fullmatch(NUMERIC, stable) or not re.fullmatch(NUMERIC, unstable):
        raise ValueError('Archive identities require both four-part client versions')
    return 'spot-fly-light-st' + stable + '-unst' + unstable


def _date_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{2}[.][0-9]{2}[.][0-9]{2}', value):
        raise ValueError('Invalid helper date version')
    year, month, day = map(int, value.split('.'))
    datetime(2000 + year, month, day)
    return value


def _timestamp(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError('Packaging timestamp must include a timezone')
    return stamp.astimezone(ZoneInfo(ZONE))


def validate_identity(catalog):
    """Return a normalized Bootstrap identity without modifying the catalog."""
    original = catalog.get('Bootstrap')
    if not isinstance(original, dict):
        raise ValueError('Missing Bootstrap identity')
    identity = dict(original)
    kind = identity.get('Kind', 'current')
    if kind not in ('current', 'archive'):
        raise ValueError('Invalid helper kind')
    name = identity.get('Name', CURRENT_NAME)
    if identity.get('Timezone') != ZONE:
        raise ValueError('Invalid packaging timezone')
    try:
        packaged = _timestamp(identity['PackagedAt'])
        release = str(identity['Release'])
        if kind == 'current':
            if name != CURRENT_NAME or not re.fullmatch(r'[1-9][0-9]*', release):
                raise ValueError('Invalid current helper identity')
            if _date_version(identity['Version']) != packaged.strftime('%y.%m.%d'):
                raise ValueError('Current helper version must be its Stockholm packaging date')
            identity['Release'] = int(release)
        else:
            if name != archive_name(catalog):
                raise ValueError('Archive name does not match the two client versions')
            first = identity.get('OriginalBootstrap')
            if first is None:
                if identity['Version'] != '0' or not re.fullmatch(r'[1-9][0-9]*', release):
                    raise ValueError('An undated archive requires Version 0 and an integer Release')
            else:
                if not isinstance(first, dict):
                    raise ValueError('Invalid first helper identity')
                first_version = _date_version(first['Version'])
                first_release = str(first['Release'])
                if not re.fullmatch(r'[1-9][0-9]*', first_release):
                    raise ValueError('Invalid original daily slot')
                if first.get('PackagedAt') and _timestamp(first['PackagedAt']).strftime('%y.%m.%d') != first_version:
                    raise ValueError('Original helper date mismatch')
                if identity['Version'] != first_version or not re.fullmatch(re.escape(first_release) + r'[.][1-9][0-9]*', release):
                    raise ValueError('Archive must preserve the original date and daily slot')
            identity['Release'] = release
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Invalid helper packaging identity: ' + str(exc)) from None
    identity.update(Name=name, Kind=kind)
    return identity


def current_paths():
    return {'Name': CURRENT_NAME, 'Kind': 'current', 'share': '/usr/share/spot..fly..light-bootstrap',
            'command': 'spot..fly..light', 'alias': CURRENT_NAME, 'state': 'spot..fly..light-bootstrap',
            'config': 'spot..fly..light', 'client_name': 'spotify-client-via-spot-fly-light',
            'client_share': '/usr/share/spot..fly..light-client', 'desktop': 'spot..fly..light.desktop',
            'icon': 'spot..fly..light'}


def release_profile(catalog):
    identity = validate_identity(catalog)
    if identity['Kind'] == 'current':
        profile = current_paths()
    else:
        name = identity['Name']
        profile = {'Name': name, 'Kind': 'archive', 'share': '/usr/share/' + name + '-bootstrap',
                   'command': name, 'alias': name, 'state': name + '-bootstrap', 'config': name,
                   'client_name': 'spotify-client-via-' + name, 'client_share': '/usr/share/' + name + '-client',
                   'desktop': name + '.desktop', 'icon': name}
    profile.update(Version=identity['Version'], Release=str(identity['Release']), Bootstrap=identity)
    return profile
