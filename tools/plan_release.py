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
from parser_debian_control_file import fetch_package

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
            if record['ref'].startswith(('refs/tags/spot-fly-light-v', 'refs/tags/sonicradle-v')) and record.get('object', {}).get('type') == 'tag':
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


def reservation_identity(ref):
    """The tag identifies the helper build, independently of its client catalog."""
    match = re.fullmatch(r'refs/tags/(?:(spot-fly-light|sonicradle)-)?v(.+)-([1-9][0-9]*)', ref['ref'])
    return (match[1] or 'spotify', match[2], int(match[3])) if match else None


def delivered_reservation(ref, builds):
    identity = reservation_identity(ref)
    if not identity:
        return False
    package, version, release = identity
    return any(build.get('source_package', {}).get('name') == package
               and build.get('state') == 'succeeded'
               and revision_from_copr(version, build) == release for build in builds)


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
        # The date may have changed since the previous successful package. A
        # scheduled check still skips unchanged DEBs across date boundaries.
        if (ref['ref'].startswith('refs/tags/spot-fly-light-v') and signature
                and ref.get('reservation', {}).get('signature') == signature
                and delivered_reservation(ref, builds)):
            delivered = True
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


def channel_release(channel, version, refs, stable_release=None, builds=()):
    numbers = []
    for ref in refs:
        channels = ref.get('reservation', {}).get('channels', {})
        # A failed reservation never delivered this channel to COPR, so it does
        # not consume a local client revision (in particular the first -1).
        if not delivered_reservation(ref, builds):
            continue
        old = channels.get(channel, {})
        if old.get('version') == version and isinstance(old.get('release'), int):
            numbers.append(old['release'])
    return max(numbers, default=0) + 1


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', choices=('schedule', 'workflow_dispatch'), required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    repository = os.environ.get('GITHUB_REPOSITORY', REPOSITORY)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository')
    channels = {channel: fetch_package(channel) for channel in ('stable', 'unstable')}
    bootstrap = packaging_identity()
    version = bootstrap['Version']
    signature = source_signature(channels)
    github = GitHub(repository, os.environ.get('GH_TOKEN', ''))
    refs = github.reservations()
    builds = copr_builds()
    result = plan(version, [], refs, builds, args.event == 'workflow_dispatch', signature)
    if result['needed']:
        pins = {channel: {'version': record['RPMVersion'],
                          'release': channel_release(channel, record['RPMVersion'], refs, result['release'], builds)}
                for channel, record in channels.items()}
        if not args.dry_run:
            if not os.environ.get('GH_TOKEN'):
                raise ValueError('GH_TOKEN is required to reserve a packaging number')
            require_copr_config(os.environ.get('COPR_CONFIG', ''))
            result['release'], result['tag'] = reserve(github, version, result['release'], os.environ.get('GITHUB_SHA', ''),
                                                       {'schema': 2, 'signature': signature, 'channels': pins,
                                                        'bootstrap': dict(bootstrap, Release=result['release'])})
        bootstrap['Release'] = result['release']
        for channel, record in channels.items():
            record.update(Channel=channel, PackagingRelease=pins[channel]['release'])
        directory = Path(os.environ.get('SPOT_FLY_LIGHT_METADATA_DIR', 'metadata'))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'source.json').write_text(json.dumps(dict(channels, Bootstrap=bootstrap), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as stream:
            for key in ('needed', 'version', 'release', 'tag'):
                if key in result:
                    value = str(result[key]).lower() if isinstance(result[key], bool) else result[key]
                    stream.write(f'{key}={value}\n')
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(f"{result['reason']} Stable upstream version: `{channels['stable']['RPMVersion']}`; unstable: `{channels['unstable']['RPMVersion']}`.\n")
            if result['needed']:
                stream.write(f"Reserved bootstrap: `{version}-{result['release']}` ({PACKAGING_ZONE}); metadata tag `{result['tag']}`. Only the payload-free helper may be released.\n")


if __name__ == '__main__':
    main()
