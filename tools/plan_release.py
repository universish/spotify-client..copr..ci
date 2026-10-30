#!/usr/bin/env python3
"""Pin both upstream channels and reserve a COPR-only bootstrap packaging revision."""
import argparse
import configparser
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib import error, parse, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from parser_debian_control_file import fetch_package

REPOSITORY = 'universish/spotify-client..copr..ci'
PROJECT_QUERY = parse.urlencode({'ownername': 'universish', 'projectname': 'Spotify..Client'})


class GitHub:
    def __init__(self, repository, token):
        self.base = f'https://api.github.com/repos/{repository}'
        self.headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'sonicradle-release-planner'}
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
            if record['ref'].startswith('refs/tags/sonicradle-v') and record.get('object', {}).get('type') == 'tag':
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
    match = re.fullmatch(rf'(?:sonicradle-)?v{re.escape(version)}-([1-9][0-9]*)', tag)
    return int(match[1]) if match else None


def revision_from_rpm(version, name):
    match = re.fullmatch(rf'(?:spotify|sonicradle)-{re.escape(version)}-([1-9][0-9]*)(?:[.][A-Za-z0-9_+~.-]+)?[.](?:x86_64|x86_64_v2|src)[.]rpm', name)
    return int(match[1]) if match else None


def revision_from_copr(version, build):
    source = build.get('source_package') or {}
    if source.get('name') not in ('spotify', 'sonicradle'):
        return None
    match = re.fullmatch(rf'{re.escape(version)}-([1-9][0-9]*)(?:[.][A-Za-z0-9_+~.-]+)?', source.get('version', '').split(':', 1)[-1])
    return int(match[1]) if match else None


def source_signature(channels):
    # URLs and mirrors can change without changing the actual pinned upstream bytes.
    fields = ('RPMVersion', 'Version', 'SHA256', 'Size', 'Filename')
    pinned = {channel: {field: str(record.get(field, '')) for field in fields}
              for channel, record in channels.items()}
    return hashlib.sha256(json.dumps(pinned, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def plan(version, releases, refs, builds, manual=False, signature=None):
    if not re.fullmatch(r'[A-Za-z0-9.+~]+', version):
        raise ValueError('Invalid upstream version')
    numbers, delivered, matching = [], False, set()
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
            if signature and ref.get('reservation', {}).get('signature') == signature:
                matching.add(number)
    for build in builds:
        number = revision_from_copr(version, build)
        if number:
            numbers.append(number)
            if build.get('state') == 'succeeded' and (signature is None or number in matching):
                delivered = True
    if delivered and not manual:
        return {'needed': False, 'version': version,
                'reason': 'Pinned stable and unstable DEBs unchanged; stopping before download, scanning and packaging.'}
    number = max(numbers, default=0) + 1
    return {'needed': True, 'version': version, 'release': number, 'tag': f'sonicradle-v{version}-{number}',
            'reason': 'Manual repackaging requested.' if manual else 'New channel metadata detected.'}


def channel_release(channel, version, refs, stable_release):
    if channel == 'stable':
        return stable_release
    numbers = []
    for ref in refs:
        old = ref.get('reservation', {}).get('channels', {}).get(channel, {})
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
        tag = f'sonicradle-v{version}-{number}'
        payload = dict(reservation or {})
        payload['release'] = number
        if 'channels' in payload:
            payload['channels']['stable']['release'] = number
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
    version = channels['stable']['RPMVersion']
    signature = source_signature(channels)
    github = GitHub(repository, os.environ.get('GH_TOKEN', ''))
    refs = github.reservations()
    result = plan(version, [], refs, copr_builds(), args.event == 'workflow_dispatch', signature)
    if result['needed']:
        pins = {channel: {'version': record['RPMVersion'],
                          'release': channel_release(channel, record['RPMVersion'], refs, result['release'])}
                for channel, record in channels.items()}
        if not args.dry_run:
            if not os.environ.get('GH_TOKEN'):
                raise ValueError('GH_TOKEN is required to reserve a packaging number')
            require_copr_config(os.environ.get('COPR_CONFIG', ''))
            result['release'], result['tag'] = reserve(github, version, result['release'], os.environ.get('GITHUB_SHA', ''),
                                                       {'schema': 1, 'signature': signature, 'channels': pins})
        pins['stable']['release'] = result['release']
        for channel, record in channels.items():
            record.update(Channel=channel, PackagingRelease=pins[channel]['release'])
        directory = Path(os.environ.get('SONICRADLE_METADATA_DIR', os.environ.get('SPOTIFY_METADATA_DIR', 'metadata')))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'source.json').write_text(json.dumps(channels, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as stream:
            for key in ('needed', 'version', 'release', 'tag'):
                if key in result:
                    value = str(result[key]).lower() if isinstance(result[key], bool) else result[key]
                    stream.write(f'{key}={value}\n')
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(f"{result['reason']} Stable upstream version: `{version}`.\n")
            if result['needed']:
                stream.write(f"Reserved bootstrap: `{version}-{result['release']}`; metadata tag `{result['tag']}`. No GitHub Release is created.\n")


if __name__ == '__main__':
    main()
