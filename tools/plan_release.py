#!/usr/bin/env python3
"""Pin both channels and reserve a Stockholm-dated bootstrap packaging revision."""
import argparse
import configparser
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib import error, parse, request
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from parser_debian_control_file import fetch_package, RequestedVersionNotFound

REPOSITORY = 'universish/spotify-client..copr..ci'
PROJECT_QUERY = parse.urlencode({'ownername': 'universish', 'projectname': 'Spotify..Client'})
PACKAGING_ZONE = 'Europe/Stockholm'


def packaging_identity(now=None):
    if now is not None and now.utcoffset() is None:
        raise ValueError('Packaging time must include a timezone')
    packaged = (now or datetime.now(ZoneInfo(PACKAGING_ZONE))).astimezone(ZoneInfo(PACKAGING_ZONE))
    return {'Version': packaged.strftime('%y.%m.%d'), 'PackagedAt': packaged.isoformat(),
            'Timezone': PACKAGING_ZONE}


class GitHub:
    def __init__(self, repository, token):
        self.base = f'https://api.github.com/repos/{repository}'
        self.headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'spot..fly..light-release-planner'}
        if token:
            self.headers['Authorization'] = f'Bearer {token}'

    def call(self, path, data=None):
        headers = dict(self.headers)
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        with request.urlopen(request.Request(self.base + path, data=body, headers=headers), timeout=60) as response:
            return json.load(response)

    def reservations(self):
        records = self.call('/git/matching-refs/tags/')
        for record in records:
            if record['ref'].startswith(('refs/tags/spot-fly-light-v', 'refs/tags/spot-fly-light-st', 'refs/tags/sonicradle-v')) and record.get('object', {}).get('type') == 'tag':
                tag = self.call('/git/tags/' + record['object']['sha'])
                try:
                    record['reservation'] = json.loads(tag['message'])
                except (ValueError, KeyError):
                    pass
        return records


def copr_builds():
    records, offset = [], 0
    while True:
        url = f'https://copr.fedorainfracloud.org/api_3/build/list?{PROJECT_QUERY}&limit=100&offset={offset}'
        with request.urlopen(url, timeout=60) as response:
            batch = json.load(response)['items']
        records.extend(batch)
        if len(batch) < 100:
            return records
        offset += 100


def revision_from_tag(version, tag):
    match = re.fullmatch(rf'(?:(?:spot-fly-light|sonicradle)-)?v{re.escape(version)}-([1-9][0-9]*)', tag)
    return int(match[1]) if match else None


def revision_from_rpm(version, name):
    match = re.fullmatch(rf'(?:spotify|sonicradle|spot-fly-light)-{re.escape(version)}-([1-9][0-9]*)(?:[.][A-Za-z0-9_+~.-]+)?[.](?:x86_64|x86_64_v2|src)[.]rpm', name)
    return int(match[1]) if match else None


def revision_from_copr(version, build):
    source = build.get('source_package') or {}
    if source.get('name') not in ('spotify', 'sonicradle', 'spot-fly-light'):
        return None
    match = re.fullmatch(rf'{re.escape(version)}-([1-9][0-9]*)(?:[.][A-Za-z0-9_+~.-]+)?', source.get('version', '').split(':', 1)[-1])
    return int(match[1]) if match else None


def source_signature(channels):
    # URLs and mirrors can change without changing the actual pinned upstream bytes.
    fields = ('RPMVersion', 'Version', 'SHA256', 'Size', 'Filename')
    pinned = {channel: {field: str(channels[channel].get(field, '')) for field in fields}
              for channel in ('stable', 'unstable')}
    return hashlib.sha256(json.dumps(pinned, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def select_sources(requested='', requested_channel='auto', opposite_version='', accepted_state=None):
    """Resolve immutable current or historical pairs before creating any tag."""
    requested = requested.strip()
    if requested_channel not in ('auto', 'stable', 'unstable'):
        raise ValueError('Manual Spotify channel must be auto, stable or unstable')
    if requested and not re.fullmatch(r'(?:[0-9]+:)?[0-9]+(?:[.][0-9]+){3}(?:[.]g[0-9a-fA-F]+(?:[.][0-9]+)?)?(?:-[0-9A-Za-z.+~]+)?', requested):
        raise ValueError('Enter a full Spotify version or its four-part numeric form, for example 1.2.95.453.g0eeebbed or 1.2.95.453')
    if opposite_version and not requested:
        raise ValueError('opposite_version requires spotify_version')
    channels = {}
    for channel in ('stable', 'unstable'):
        try:
            options = {'accepted_state': accepted_state} if accepted_state else {}
            channels[channel] = fetch_package(channel, **options)
        except (RuntimeError, ValueError, error.URLError, OSError):
            if not requested:
                raise
            # Explicit archives remain usable when a current endpoint is down.
            # Their sources still require independent signed authentication below.
            print('Current ' + channel + ' discovery unavailable; checking the historical catalog for the explicit request.', file=sys.stderr)
    if not requested:
        return channels, {'Kind': 'current', 'Selection': 'latest-signed-channels'}
    matches = {}
    for channel in (('stable', 'unstable') if requested_channel == 'auto' else (requested_channel,)) if len(channels) == 2 else ():
        try:
            matches[channel] = fetch_package(channel, requested_version=requested, audit_rpmfusion=False)
        except RequestedVersionNotFound:
            continue
    if len(matches) != 1:
        if matches:
            choices = ', '.join(channel + ': ' + record['RPMVersion'] for channel, record in matches.items())
            raise ValueError('Version matches multiple channels; select spotify_channel explicitly: ' + choices)
    elif not opposite_version:
        channel, record = next(iter(matches.items()))
        if all(str(record.get(field, '')) == str(channels[channel].get(field, ''))
               for field in ('RPMVersion', 'Version', 'SHA256', 'Size', 'Filename')):
            print('Manual current source resolved: ' + requested + ' -> ' + channel + ' ' + record['RPMVersion'], file=sys.stderr)
            return channels, {'Kind': 'current', 'Selection': 'current-explicit-version', 'RequestedVersion': requested}
    from spotify_history import select_historical_channels
    import parser_debian_control_file as upstream
    historical, pairing = select_historical_channels(requested, requested_channel, opposite_version)
    authenticated = {}
    for channel, record in historical.items():
        current = channels.get(channel)
        if current and all(str(current.get(field, '')) == str(record.get(field, ''))
                           for field in ('RPMVersion', 'Version', 'SHA256', 'Size', 'Filename')):
            # A historical observation is a discovery hint. When the exact
            # bytes still appear in today's signed channel, retain that fresh
            # authentication instead of requiring a separate archive signature.
            authenticated[channel] = dict(record, **current)
        else:
            authenticated[channel] = upstream.verify_historical_record(record)
    historical = authenticated
    return historical, dict(pairing, Kind='archive')


def selected_channels(requested='', requested_channel='auto'):
    """Compatibility entry point; the planner also needs the pair selection evidence."""
    return select_sources(requested, requested_channel)[0]


def reservation_identity(ref):
    """The tag identifies the helper build, independently of its client catalog."""
    if ref['ref'].startswith('refs/tags/spot-fly-light-st'):
        info = ref.get('reservation', {}).get('bootstrap', {})
        name, version, release = info.get('Name', ''), info.get('Version', ''), str(info.get('Release', ''))
        if (re.fullmatch(r'spot-fly-light-st[0-9]+(?:[.][0-9]+){3}-unst[0-9]+(?:[.][0-9]+){3}', name)
                and re.fullmatch(r'(?:0|[0-9]{2}(?:[.][0-9]{2}){2})', version)
                and re.fullmatch(r'[1-9][0-9]*(?:[.][1-9][0-9]*)?', release)
                and ref['ref'] == f'refs/tags/{name}-v{version}-{release}'):
            return name, version, release
        return None
    match = re.fullmatch(r'refs/tags/(?:(spot-fly-light|sonicradle)-)?v(.+)-([1-9][0-9]*)', ref['ref'])
    return (match[1] or 'spotify', match[2], int(match[3])) if match else None


def delivered_reservation(ref, builds):
    identity = reservation_identity(ref)
    if not identity:
        return False
    package, version, release = identity
    if package.startswith('spot-fly-light-st'):
        return any(build.get('source_package', {}).get('name') == package
                   and build.get('state') == 'succeeded'
                   and re.fullmatch(re.escape(version + '-' + release) + r'(?:[.][A-Za-z][A-Za-z0-9_+~.-]*)?',
                                    str(build.get('source_package', {}).get('version', '')).split(':', 1)[-1])
                   for build in builds)
    return any(build.get('source_package', {}).get('name') == package
               and build.get('state') == 'succeeded'
               and revision_from_copr(version, build) == release for build in builds)


def reservation_order(ref):
    identity = reservation_identity(ref)
    if not identity:
        return ((), ())
    _, version, release = identity
    return (tuple(int(part) for part in re.findall(r'[0-9]+', version)),
            tuple(int(part) for part in str(release).split('.')))


def accepted_states(refs):
    """Recover the last authenticated current snapshot without consulting archives."""
    states = {}
    for ref in refs:
        if not ref['ref'].startswith('refs/tags/spot-fly-light-v'):
            continue
        for proof in ref.get('reservation', {}).get('source_authentication', {}).values():
            if not isinstance(proof, dict):
                continue
            try:
                timestamp = datetime.fromisoformat(proof['ReleaseDate'].replace('Z', '+00:00'))
                if timestamp.utcoffset() is None or not re.fullmatch(r'[0-9a-f]{64}', proof['ReleaseSHA256']):
                    continue
                key = proof['RepositoryID'] + ':' + proof['Distribution']
            except (KeyError, TypeError, ValueError):
                continue
            previous = states.get(key)
            if previous is None or timestamp > datetime.fromisoformat(previous['ReleaseDate'].replace('Z', '+00:00')):
                states[key] = {field: proof[field] for field in ('ReleaseDate', 'ReleaseSHA256')}
    return states


def canonical_version(record):
    return record.get('Version', record['RPMVersion'])


def archive_identity(channels, pairing, refs, builds, now=None):
    """Assign a different RPM name, never a newer current helper date."""
    from release_identity import archive_name, validate_identity
    name = archive_name(channels)
    signature = source_signature(channels)
    originals = [ref for ref in refs if ref['ref'].startswith('refs/tags/spot-fly-light-v')
                 and ref.get('reservation', {}).get('signature') == signature
                 and delivered_reservation(ref, builds)
                 and re.fullmatch(r'[0-9]{2}(?:[.][0-9]{2}){2}', ref.get('reservation', {}).get('bootstrap', {}).get('Version', ''))]
    original = min(originals, key=reservation_order).get('reservation', {}).get('bootstrap') if originals else None
    packaged = packaging_identity(now)
    identity = dict(packaged, Kind='archive', Name=name, Version=original['Version'] if original else '0',
                    Pairing=pairing)
    prefix = str(original['Release']) + '.' if original else ''
    if original:
        identity['OriginalBootstrap'] = {key: original[key] for key in ('Version', 'Release', 'PackagedAt')}
    numbers = []
    for ref in refs:
        previous = reservation_identity(ref)
        if previous and previous[:2] == (name, identity['Version']):
            candidate = str(previous[2])
            if candidate.startswith(prefix) and re.fullmatch(r'[1-9][0-9]*', candidate[len(prefix):]):
                numbers.append(int(candidate[len(prefix):]))
    for build in builds:
        source = build.get('source_package') or {}
        if source.get('name') != name:
            continue
        match = re.fullmatch(re.escape(identity['Version'] + '-' + prefix) + r'([1-9][0-9]*)(?:[.][A-Za-z][A-Za-z0-9_+~.-]*)?',
                             str(source.get('version', '')).split(':', 1)[-1])
        if match:
            numbers.append(int(match[1]))
    identity['Release'] = prefix + str(max(numbers, default=0) + 1)
    return validate_identity(dict(channels, Bootstrap=identity))


def reserve_archive(github, channels, identity, sha, reservation):
    """Archive counters are atomic and independent of date-based current tags."""
    from release_identity import validate_identity
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('GITHUB_SHA must be a full commit SHA')
    identity = validate_identity(dict(channels, Bootstrap=identity))
    for _ in range(20):
        tag = f"{identity['Name']}-v{identity['Version']}-{identity['Release']}"
        payload = dict(reservation, bootstrap=identity, release=identity['Release'])
        tag_object = github.call('/git/tags', {'tag': tag, 'message': json.dumps(payload, sort_keys=True),
                                             'object': sha, 'type': 'commit'})
        try:
            github.call('/git/refs', {'ref': f'refs/tags/{tag}', 'sha': tag_object['sha']})
            return identity, tag
        except error.HTTPError as exc:
            exc.close()
            if exc.code != 422:
                raise
            github.call('/git/ref/tags/' + parse.quote(tag, safe=''))
            components = str(identity['Release']).split('.')
            components[-1] = str(int(components[-1]) + 1)
            identity = dict(identity, Release='.'.join(components))
    raise RuntimeError('Could not reserve a unique archive revision after 20 collisions')


def plan(version, releases, refs, builds, manual=False, signature=None):
    if not re.fullmatch(r'[A-Za-z0-9.+~]+', version):
        raise ValueError('Invalid upstream version')
    numbers, delivered = [], False
    for release in releases:  # Count historic reservations even after their assets are removed.
        number = revision_from_tag(version, release.get('tag_name', ''))
        if number:
            numbers.append(number)
        numbers.extend(n for asset in release.get('assets', [])
                       if (n := revision_from_rpm(version, asset['name'])))
    for ref in refs:
        number = revision_from_tag(version, ref['ref'].removeprefix('refs/tags/'))
        if number:
            numbers.append(number)
    # Only the latest delivered current helper can satisfy the schedule. An
    # older matching pair or any archive must never mask a later channel change.
    current = [ref for ref in refs if ref['ref'].startswith('refs/tags/spot-fly-light-v')
               and delivered_reservation(ref, builds)]
    if current and signature:
        latest = max(current, key=reservation_order)
        delivered = latest.get('reservation', {}).get('signature') == signature
    for build in builds:
        number = revision_from_copr(version, build)
        if number:
            numbers.append(number)
            if (build.get('source_package', {}).get('name') == 'spot-fly-light'
                    and build.get('state') == 'succeeded'
                    and signature is None):
                delivered = True
    if delivered and not manual:
        return {'needed': False, 'version': version,
                'reason': 'Pinned stable and unstable DEBs unchanged; stopping before download, scanning and packaging.'}
    number = max(numbers, default=0) + 1
    return {'needed': True, 'version': version, 'release': number, 'tag': f'spot-fly-light-v{version}-{number}',
            'reason': 'Manual repackaging requested.' if manual else 'New channel metadata detected.'}


def channel_release(channel, version, refs, stable_release=None, builds=(), rpm_version=None):
    numbers = []
    for ref in refs:
        channels = ref.get('reservation', {}).get('channels', {})
        # A failed reservation never delivered this channel to COPR, so it does
        # not consume a local client revision (in particular the first -1).
        if not delivered_reservation(ref, builds):
            continue
        old = channels.get(channel, {})
        same = old.get('debian_version', old.get('version')) == version
        # Old reservations predate retaining Debian's epoch. Only those legacy
        # records use the old RPM-safe identity for continuity.
        if not old.get('debian_version'):
            same = same or old.get('version') == (rpm_version or version.split(':', 1)[-1])
        if same and type(old.get('release')) is int:
            numbers.append(old['release'])
    return max(numbers, default=0) + 1


def reservation_payload(channels, bootstrap, signature):
    proofs = {}
    for channel, record in channels.items():
        proof = record.get('Authentication')
        if isinstance(proof, dict):
            proofs[channel] = {key: proof[key] for key in ('Type', 'RepositoryID', 'Distribution', 'Fingerprint',
                'ReleaseDate', 'ReleaseSHA256', 'IndexSHA256', 'IndexSize') if key in proof}
    return {'schema': 3, 'signature': signature, 'bootstrap': bootstrap,
            'channels': {channel: {'version': record['RPMVersion'],
                'debian_version': canonical_version(record), 'release': record['PackagingRelease']}
                for channel, record in channels.items()}, 'source_authentication': proofs}


def require_copr_config(value):
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(value)
    except configparser.Error:
        raise ValueError('COPR_CONFIG is not a valid generated INI configuration') from None
    if not config.has_section('copr-cli') or any(not config.get('copr-cli', key, fallback='').strip() for key in ('login', 'username', 'token')):
        raise ValueError('COPR_CONFIG must contain the complete generated [copr-cli] configuration')
    if config.get('copr-cli', 'copr_url', fallback='').rstrip('/') != 'https://copr.fedorainfracloud.org':
        raise ValueError('COPR_CONFIG must point to https://copr.fedorainfracloud.org')


def reserve(github, version, number, sha, reservation=None):
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('GITHUB_SHA must be a full commit SHA')
    for _ in range(20):
        tag = f'spot-fly-light-v{version}-{number}'
        payload = dict(reservation or {})
        payload['release'] = number
        if 'bootstrap' in payload:
            payload['bootstrap'] = dict(payload['bootstrap'], Release=number)
        tag_object = github.call('/git/tags', {'tag': tag, 'message': json.dumps(payload, sort_keys=True),
                                             'object': sha, 'type': 'commit'})
        try:
            github.call('/git/refs', {'ref': f'refs/tags/{tag}', 'sha': tag_object['sha']})
            return number, tag
        except error.HTTPError as exc:
            exc.close()
            if exc.code != 422:
                raise
            github.call('/git/ref/tags/' + parse.quote(tag, safe=''))
            number += 1
    raise RuntimeError('Could not reserve a unique packaging number after 20 collisions')


def finalize(metadata_path, repository, dry_run=False):
    """Finalize real packaging time; archive identities never advance to today."""
    from release_identity import validate_identity
    path = Path(metadata_path)
    catalog = json.loads(path.read_text(encoding='utf-8'))
    old = catalog.get('Bootstrap', {})
    channels = {channel: catalog[channel] for channel in ('stable', 'unstable')}
    # Validate the helper separately from source shapes, which the scan/gate
    # validate. This also keeps test fixtures out of production summaries.
    identity = validate_identity(catalog)
    if any(type(record.get('PackagingRelease')) is not int or record['PackagingRelease'] < 1
           or not re.fullmatch(r'[A-Za-z0-9.+~]+', record.get('RPMVersion', ''))
           for record in channels.values()):
        raise ValueError('Finalization requires both pinned client revisions')
    packaged = packaging_identity()
    if identity['Kind'] == 'archive':
        bootstrap = dict(old, PackagedAt=packaged['PackagedAt'])
        result = {'needed': True, 'name': identity['Name'], 'kind': 'archive',
            'version': identity['Version'], 'release': identity['Release'],
            'tag': f"{identity['Name']}-v{identity['Version']}-{identity['Release']}",
            'reason': 'Confirmed actual packaging time while preserving the historical archive identity.'}
    else:
        bootstrap = dict(old, **packaged)
        version = packaged['Version']
        if version == old['Version']:
            result = {'needed': True, 'version': version, 'release': old['Release'],
                'tag': f"spot-fly-light-v{version}-{old['Release']}",
                'reason': 'Confirmed the Stockholm packaging date after upstream scanning.'}
        else:
            if not dry_run:
                if not os.environ.get('GH_TOKEN'):
                    raise ValueError('GH_TOKEN is required to reserve a packaging number')
                require_copr_config(os.environ.get('COPR_CONFIG', ''))
            signature = source_signature(channels)
            github = GitHub(repository, os.environ.get('GH_TOKEN', ''))
            result = plan(version, [], github.reservations(), copr_builds(), manual=True, signature=signature)
            if not dry_run:
                result['release'], result['tag'] = reserve(github, version, result['release'], os.environ.get('GITHUB_SHA', ''),
                    reservation_payload(channels, dict(bootstrap, Release=result['release']), signature))
            result['reason'] = 'Stockholm date changed during scanning; reserved the actual packaging date without changing client pins.'
        bootstrap['Release'] = result['release']
        result.update(name='spot-fly-light', kind='current')
    if not dry_run:
        catalog['Bootstrap'] = bootstrap
        path.write_text(json.dumps(catalog, indent=2) + '\n', encoding='utf-8')
    return result, channels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', choices=('schedule', 'workflow_dispatch'))
    parser.add_argument('--finalize', metavar='METADATA', help='Confirm the Stockholm packaging date after scanning')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if bool(args.event) == bool(args.finalize):
        parser.error('Specify exactly one of --event or --finalize')
    repository = os.environ.get('GITHUB_REPOSITORY', REPOSITORY)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository')
    if args.finalize:
        result, channels = finalize(args.finalize, repository, args.dry_run)
        version = result['version']
        report(result, channels, version)
        return
    requested = os.environ.get('SPOT_FLY_LIGHT_REQUESTED_VERSION', '').strip()
    opposite = os.environ.get('SPOT_FLY_LIGHT_OPPOSITE_VERSION', '').strip()
    if args.event != 'workflow_dispatch' and (requested or opposite):
        raise ValueError('Explicit Spotify versions are supported only for manual workflow dispatch')
    github = GitHub(repository, os.environ.get('GH_TOKEN', ''))
    refs = github.reservations()
    builds = copr_builds()
    channels, pairing = select_sources(requested,
        os.environ.get('SPOT_FLY_LIGHT_REQUESTED_CHANNEL', 'auto') or 'auto', opposite, accepted_states(refs))
    signature = source_signature(channels)
    if pairing.get('Kind') == 'archive':
        bootstrap = archive_identity(channels, pairing, refs, builds)
        result = {'needed': True, 'name': bootstrap['Name'], 'kind': 'archive',
            'version': bootstrap['Version'], 'release': bootstrap['Release'],
            'tag': f"{bootstrap['Name']}-v{bootstrap['Version']}-{bootstrap['Release']}",
            'reason': 'Explicit historical pair selected; publication cannot replace the current helper.'}
    else:
        bootstrap = packaging_identity()
        bootstrap['Pairing'] = pairing
        result = plan(bootstrap['Version'], [], refs, builds, args.event == 'workflow_dispatch', signature)
        result.update(name='spot-fly-light', kind='current')
        if result['needed']:
            bootstrap['Release'] = result['release']
    if result['needed']:
        for channel, record in channels.items():
            record.update(Channel=channel, PackagingRelease=channel_release(channel,
                canonical_version(record), refs, result['release'], builds, rpm_version=record['RPMVersion']))
        if not args.dry_run:
            if not os.environ.get('GH_TOKEN'):
                raise ValueError('GH_TOKEN is required to reserve a packaging number')
            require_copr_config(os.environ.get('COPR_CONFIG', ''))
            payload = reservation_payload(channels, bootstrap, signature)
            if pairing.get('Kind') == 'archive':
                bootstrap, result['tag'] = reserve_archive(github, channels, bootstrap,
                    os.environ.get('GITHUB_SHA', ''), payload)
                result['release'] = bootstrap['Release']
            else:
                result['release'], result['tag'] = reserve(github, bootstrap['Version'], result['release'],
                    os.environ.get('GITHUB_SHA', ''), payload)
                bootstrap['Release'] = result['release']
            directory = Path(os.environ.get('SPOT_FLY_LIGHT_METADATA_DIR', 'metadata'))
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'source.json').write_text(json.dumps(dict(channels, Bootstrap=bootstrap), indent=2) + '\n', encoding='utf-8')
    report(result, channels, result['version'])


def report(result, channels, version):
    print(json.dumps(result))
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as stream:
            for key in ('needed', 'version', 'release', 'tag', 'name', 'kind'):
                if key in result:
                    value = str(result[key]).lower() if isinstance(result[key], bool) else str(result[key])
                    if '\n' in value or '\r' in value:
                        raise ValueError('Unsafe workflow output')
                    stream.write(f'{key}={value}\n')
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(f"{result['reason']} Stable upstream version: `{channels['stable']['RPMVersion']}`; unstable: `{channels['unstable']['RPMVersion']}`.\n")
            if result['needed']:
                stream.write(f"Reserved {result.get('kind', 'current')} bootstrap: `{result.get('name', 'spot-fly-light')}-{version}-{result['release']}` ({PACKAGING_ZONE}); metadata tag `{result['tag']}`. Only the payload-free helper may be released.\n")


if __name__ == '__main__':
    main()
