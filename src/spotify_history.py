#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Resolve documented historical sources without inventing channel chronology.

The checked-in catalog is a discovery/evidence inventory, not an authentication
cache. Every selected source must pass fresh repository authentication in CI.
"""
import copy
import json
from pathlib import Path
import re

from release_identity import parse_debian_version

DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / 'data/spotify-history.json'


def load_catalog(path=None):
    catalog = json.loads(Path(path or DEFAULT_CATALOG).read_text(encoding='utf-8'))
    if catalog.get('schema') != 1 or not isinstance(catalog.get('records'), list):
        raise ValueError('Unsupported Spotify history catalog')
    return catalog


def matches_version(raw, requested):
    """A numeric request is exact, never an arbitrary prefix of another version."""
    parsed = parse_debian_version(raw)
    return requested in (raw, raw.split(':', 1)[-1], parsed['numeric'])


def source_record(record, channel=None):
    """Copy a catalog record into the shared, lossless source-record shape."""
    result = copy.deepcopy(record)
    raw = result.get('DebianVersion', result.get('Version', ''))
    parsed = parse_debian_version(raw)
    if result.get('Version', raw) != raw:
        raise ValueError('Conflicting full Debian versions in historical catalog')
    if (result.get('Package') != 'spotify-client' or result.get('Architecture') != 'amd64'
            or not re.fullmatch(r'[0-9a-f]{64}', result.get('SHA256', ''))
            or not isinstance(result.get('Size'), int) or result['Size'] <= 0):
        raise ValueError('Historical source lacks exact amd64 package size/hash evidence')
    filename = result.get('Filename', '')
    if (not filename.startswith('pool/') or filename.startswith('/')
            or '..' in Path(filename).parts or not filename.endswith('_amd64.deb')):
        raise ValueError('Invalid historical package filename')
    if result.get('SupportedLayout') is False or tuple(map(int, parsed['numeric'].split('.'))) < (1, 0, 0, 0):
        raise ValueError('Historical Qt/client layout is not supported by this local builder')
    if result.get('RPMVersion', parsed['rpm_version']) != parsed['rpm_version']:
        raise ValueError('Historical RPM version does not match the full Debian source')
    assigned = channel or result.get('Channel')
    if assigned not in ('stable', 'unstable'):
        raise ValueError('Historical source needs an explicit channel assignment')
    if result.get('Channel') not in (assigned, 'unknown'):
        raise ValueError('Historical source belongs to a different channel')
    result.update(Version=raw, DebianVersion=raw, RawDebianVersion=raw,
                  RPMVersion=parsed['rpm_version'], NumericVersion=parsed['numeric'],
                  CommitHash=parsed['commit'], DebianRevision=parsed['revision'],
                  Channel=assigned)
    if record.get('Channel') == 'unknown':
        result['ChannelEvidence'] = 'manual'
    result.pop('ScanAttestation', None)
    # Authentication evidence collected in the past must never authorize a new
    # build. The caller revalidates the signed repository before scanning bytes.
    result.pop('Authentication', None)
    return result


def _matching_records(catalog, requested, channel='auto'):
    requested = requested.strip()
    parse_debian_version(requested)
    if channel not in ('auto', 'stable', 'unstable'):
        raise ValueError('Historical channel must be auto, stable or unstable')
    matches = []
    for record in catalog['records']:
        if not isinstance(record, dict):
            raise ValueError('Invalid historical catalog record')
        raw = record.get('DebianVersion', record.get('Version', ''))
        try:
            matched = matches_version(raw, requested)
        except ValueError:
            continue
        if not matched:
            continue
        actual_channel = record.get('Channel', 'unknown')
        if channel == 'auto' and actual_channel not in ('stable', 'unstable'):
            continue
        if channel != 'auto' and actual_channel not in (channel, 'unknown'):
            continue
        matches.append(record)
    # Prefer documented channel membership over an unclassified distro copy.
    if channel != 'auto' and any(r.get('Channel') == channel for r in matches):
        matches = [r for r in matches if r.get('Channel') == channel]
    unique = {}
    for record in matches:
        key = (record.get('Channel'), record.get('Version'), record.get('SHA256'), record.get('Size'))
        unique.setdefault(key, record)
    return list(unique.values())


def _one(catalog, requested, channel):
    matches = _matching_records(catalog, requested, channel)
    if not matches:
        raise ValueError('No evidenced historical amd64 source matches ' + requested
                         + '; unavailable or unclassified versions cannot be guessed')
    if len(matches) != 1:
        choices = ', '.join(sorted(r.get('Channel', 'unknown') + ': ' + r['Version'] for r in matches))
        raise ValueError('Historical version is ambiguous; specify the full Debian version and channel: ' + choices)
    record = matches[0]
    selected_channel = record.get('Channel') if channel == 'auto' else channel
    return source_record(record, selected_channel), record


def select_historical_channels(requested, channel='auto', opposite_version='', catalog_path=None):
    """Return ``(two source records, pairing evidence)`` without network access.

    Automatic pairing requires an explicitly reviewed historical pair. Capture
    time, mirror mtime and package-maintainer commit dates are never substituted
    for a Spotify publication date. Otherwise the owner supplies the opposite
    version explicitly and the resulting catalog identifies that manual choice.
    """
    catalog = load_catalog(catalog_path)
    selected, original = _one(catalog, requested.strip(), channel)
    selected_channel = selected['Channel']
    other = 'unstable' if selected_channel == 'stable' else 'stable'
    pairs = [p for p in catalog.get('reviewed_pairs', [])
             if p.get('reviewed') is True and p.get(selected_channel) == original.get('Id')]
    pairing = {'Kind': 'archive', 'RequestedVersion': requested.strip(),
               'ResolvedRequestedVersion': selected['Version'],
               'RequestedChannel': selected_channel,
               'AnchorObservedAt': original.get('FirstObservedAt'),
               'AnchorPublishedAt': original.get('PublishedAt')}
    if opposite_version.strip():
        opposite, _ = _one(catalog, opposite_version.strip(), other)
        pairing.update(Selection='manual', OppositeVersion=opposite['Version'],
                       Evidence=[], Chronology='Manual counterpart; no publication-time claim')
    else:
        if len(pairs) != 1 or not pairs[0].get('Evidence'):
            raise ValueError('Historical counterpart chronology is not proven; specify opposite_version explicitly')
        pair = pairs[0]
        rows = [r for r in catalog['records'] if r.get('Id') == pair.get(other)]
        if len(rows) != 1:
            raise ValueError('Reviewed historical pair references a missing or ambiguous source')
        opposite = source_record(rows[0], other)
        pairing.update(Selection='historical', OppositeVersion=opposite['Version'],
                       Evidence=copy.deepcopy(pair['Evidence']),
                       AnchorObservedAt=pair.get('AnchorObservedAt', pairing['AnchorObservedAt']),
                       Chronology='Reviewed source-channel observation pair')
    if selected.get('ChannelEvidence') == 'manual' or opposite.get('ChannelEvidence') == 'manual':
        pairing['Selection'] = 'manual'
        pairing['ChannelAssignment'] = 'One or more channel labels were explicitly supplied by the owner'
    return {selected_channel: selected, other: opposite}, pairing


resolve_historical_pair = select_historical_channels
