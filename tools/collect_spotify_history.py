#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Collect bounded public metadata; never download or execute a Spotify DEB."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import csv
import bz2
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from http.client import HTTPException
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from release_identity import parse_debian_version

SPOTIFY_BASES = ('https://download.spotify.com/debian', 'https://repository.spotify.com',
                 'https://repository-origin.spotify.com')
RUG = 'https://deb.rug.nl/ppa/mirror/repository.spotify.com'
MINT = 'https://ftp.sh.cvut.cz/mint'
LITE = 'https://fosszone.csd.auth.gr/linuxlite'
BASELINE = {'ObservedOn': '2026-10-31', 'Stable': '1.2.95.453', 'Unstable': '1.3.4.258'}
LIMIT = 8 * 1024 * 1024
CACHE_DIR = None


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def captured_at(stamp):
    return datetime.strptime(stamp, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).isoformat()


def version_key(record):
    numeric = record.get('NumericVersion', '')
    values = tuple(map(int, numeric.split('.'))) if re.fullmatch(r'\d+(?:[.]\d+){3}', numeric) else (-1,)
    return values, record.get('Version', ''), record.get('Channel', ''), record.get('SHA256') or ''


def read_url(url, timeout=20, retries=1):
    cache_path = CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest() + '.json') if CACHE_DIR else None
    immutable = (url.startswith('https://web.archive.org/')
                 or bool(re.fullmatch(r'https://raw[.]githubusercontent[.]com/archlinux/aur/[0-9a-f]{40}/PKGBUILD', url)))
    if cache_path and immutable and cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached.get('URL') == url and cached.get('Status') == 'read':
            return bytes.fromhex(cached['BodyHex']), cached['Headers'], cached['FinalURL'], cached['TransportSHA256']
    last = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={'User-Agent': 'SpotLight-public-metadata-history/1', 'Accept-Encoding': 'identity'})
            with urlopen(request, timeout=timeout) as response:
                data = response.read(LIMIT + 1)
                headers = dict(response.headers)
                final_url = response.geturl()
            if len(data) > LIMIT:
                raise ValueError('Public metadata exceeds its size limit')
            transport_sha = hashlib.sha256(data).hexdigest()
            for _ in range(2):
                if data.startswith(b'BZh'):
                    decompressor = bz2.BZ2Decompressor()
                    data = decompressor.decompress(data, max_length=LIMIT + 1)
                    if not decompressor.eof:
                        raise ValueError('Expanded metadata exceeds its size limit')
                elif data.startswith(b'\x1f\x8b'):
                    with gzip.GzipFile(fileobj=io.BytesIO(data)) as archive:
                        data = archive.read(LIMIT + 1)
                else:
                    break
                if len(data) > LIMIT:
                    raise ValueError('Expanded metadata exceeds its size limit')
            if cache_path:
                cache_path.write_text(json.dumps({'URL': url, 'Status': 'read', 'FetchedAt': utc_now(),
                    'BodyHex': data.hex(), 'Headers': headers, 'FinalURL': final_url, 'TransportSHA256': transport_sha}) + '\n')
            return data, headers, final_url, transport_sha
        except (HTTPError, URLError, OSError, TimeoutError, HTTPException, ValueError) as exc:
            last = exc
            if isinstance(exc, HTTPError):
                exc.close()
                if exc.code not in (408, 429, 500, 502, 503, 504):
                    break
    if cache_path:
        cache_path.write_text(json.dumps({'URL': url, 'Status': 'unavailable', 'FetchedAt': utc_now(), 'Error': str(last)}) + '\n')
    raise RuntimeError(type(last).__name__ + ': ' + str(last)) from last


def package_records(text):
    current, last = {}, None
    for line in text.splitlines() + ['']:
        if not line.strip():
            if current:
                yield current
            current, last = {}, None
        elif line.startswith((' ', '\t')) and last:
            current[last] += '\n' + line.strip()
        elif ':' in line:
            last, value = line.split(':', 1)
            current[last] = value.strip()
    if current:
        yield current


def source_record(raw, channel, evidence, repository):
    if raw.get('Architecture') != 'amd64' or raw.get('Package') not in ('spotify-client', 'spotify-client-qt', 'spotify-client-0.9.17'):
        return None
    if (not re.fullmatch(r'[0-9a-f]{64}', raw.get('SHA256', ''))
            or not str(raw.get('Size', '')).isdigit() or int(raw['Size']) <= 0
            or not raw.get('Filename', '').startswith('pool/')):
        return None
    result = dict(raw)
    result.update(Version=raw['Version'], DebianVersion=raw['Version'], RawDebianVersion=raw['Version'],
                  Size=int(raw['Size']), Channel=channel, RepositoryURL=repository,
                  PackageIndexURL=evidence['URL'], FirstObservedAt=evidence['ObservedAt'],
                  PublishedAt=None, Evidence=[evidence], DownloadURLs=[],
                  DownloadBaseURLs=[*SPOTIFY_BASES, RUG],
                  Availability={'Status': 'not-checked', 'Checks': []})
    try:
        parsed = parse_debian_version(raw['Version'])
        numeric = tuple(map(int, parsed['numeric'].split('.')))
        result.update(RPMVersion=parsed['rpm_version'], NumericVersion=parsed['numeric'],
                      CommitHash=parsed['commit'], DebianRevision=parsed['revision'],
                      SupportedLayout=numeric >= (1, 0, 0, 0) and raw['Package'] == 'spotify-client')
        if not result['SupportedLayout']:
            result['UnsupportedReason'] = 'Legacy Qt/package layout is recorded for research, not offered by the Chromium builder'
    except ValueError:
        result.update(RPMVersion=None, NumericVersion=raw['Version'].split(':')[-1].split('.g')[0],
                      CommitHash='', SupportedLayout=False,
                      UnsupportedReason='Legacy version/layout needs a separate implementation')
    result['Id'] = hashlib.sha256((channel + '\0' + raw['Version'] + '\0' + raw['SHA256'] + '\0' + str(raw['Size'])).encode()).hexdigest()[:24]
    return result


def merge_record(records, incoming):
    previous = records.get(incoming['Id'])
    if previous is None:
        records[incoming['Id']] = incoming
        return
    seen = {(e['URL'], e['ObservedAt']) for e in previous['Evidence']}
    previous['Evidence'].extend(e for e in incoming['Evidence'] if (e['URL'], e['ObservedAt']) not in seen)
    previous['FirstObservedAt'] = min(e['ObservedAt'] for e in previous['Evidence'])
    previous.setdefault('SourceVariants', [])
    if incoming['Filename'] != previous['Filename'] or incoming.get('DistributionProvenance'):
        variant = {k: v for k, v in incoming.items() if k not in ('Evidence', 'Availability', 'SourceVariants')}
        if variant not in previous['SourceVariants']:
            previous['SourceVariants'].append(variant)


def index_document(url, channel, observed, repository, source_id, timeout, retries, capture=None):
    candidates = [url]
    if capture:
        # Wayback's catalog may retain :80 or a different original scheme than
        # its retrievable replay. These remain HTTPS archive requests, not an
        # insecure direct package transport. Preserve the actual replay URL.
        normalized = url.replace('spotify.com:80/', 'spotify.com/')
        candidates.extend([normalized, normalized.replace('id_/http://', 'id_/https://'),
                           normalized.replace('id_/https://', 'id_/http://')])
    errors = []
    for candidate in dict.fromkeys(candidates):
        try:
            data, headers, final_url, transport = read_url(candidate, timeout, retries if candidate == url else 0)
            break
        except RuntimeError as exc:
            errors.append(str(exc))
    else:
        raise RuntimeError('; '.join(dict.fromkeys(errors)))
    actual_capture = re.search(r'/web/(\d{14})(?:id_)?/', final_url)
    if actual_capture:
        observed = captured_at(actual_capture.group(1))
    evidence = {'Type': 'spotify-index-archive' if capture else 'spotify-index-live',
                'URL': final_url, 'RequestedURL': url, 'ObservedAt': observed,
                'Channel': channel, 'PublishedAt': None,
                'IndexModifiedAt': headers.get('x-archive-orig-last-modified', headers.get('Last-Modified')),
                'DocumentSHA256': hashlib.sha256(data).hexdigest(), 'TransportSHA256': transport,
                'Authentication': 'Not authenticated by this collector; CI must validate the signed bundle'}
    records = []
    for raw in package_records(data.decode('utf-8')):
        record = source_record(raw, channel, evidence, repository)
        if record:
            distribution = 'testing' if channel == 'unstable' else 'stable'
            record['HistoricalProvenance'] = {'SourceID': source_id, 'Distribution': distribution,
                'IndexPath': 'non-free/binary-amd64/Packages', 'PackageIndexURL': final_url}
            if capture:
                record['HistoricalProvenance']['CaptureTimestamp'] = actual_capture.group(1) if actual_capture else capture
            records.append(record)
    if not records:
        raise ValueError('No exact native amd64 Spotify package record in this document')
    return records, evidence


def cdx_url(target):
    return 'https://web.archive.org/cdx/search/cdx?' + urlencode({'url': target, 'output': 'json',
        'filter': 'statuscode:200', 'collapse': 'digest', 'fl': 'timestamp,original,digest', 'limit': 1000})


def cdx_records(target, timeout, retries):
    try:
        body = read_url(cdx_url(target), timeout, retries)[0]
    except RuntimeError:
        # Some archive frontends serve the ordinary documented query form
        # while refusing its percent-encoded equivalent. Both requests have
        # the same bounded parser and never relax HTTPS certificate checks.
        alternate = ('https://web.archive.org/cdx/search/cdx?url=' + target
                     + '&output=json&filter=statuscode:200&collapse=digest&fl=timestamp,original,digest')
        body = read_url(alternate, timeout, retries)[0]
    data = json.loads(body)
    if not data:
        return []
    if data[0] != ['timestamp', 'original', 'digest'] or len(data) > 1001:
        raise ValueError('Unexpected archive catalog schema/size')
    return data[1:]


def collect_signed_bundles(catalog, args):
    """Associate actual archive signature captures, without trusting them.

    Nearby captures are only verification candidates. The source verifier must
    prove the detached signature and exact index digest before selecting bytes.
    """
    global CACHE_DIR
    evidence_dir = Path(args.evidence_dir); evidence_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR = evidence_dir / 'requests'; CACHE_DIR.mkdir(parents=True, exist_ok=True)
    captures = {}
    records = catalog['records']
    for source_id, base in [('spotify-repository', SPOTIFY_BASES[1]), ('spotify-origin', SPOTIFY_BASES[2])]:
        for distribution in ('stable', 'testing'):
            for part in ('InRelease', 'Release', 'Release.gpg'):
                target = base.removeprefix('https://') + '/dists/' + distribution + '/' + part
                try:
                    rows = cdx_records(target, args.timeout, args.retries)
                    captures[(source_id, distribution, part)] = rows
                    catalog['coverage'].append({'SourceURL': cdx_url(target), 'Kind': 'signed-metadata-catalog', 'Status': 'read', 'DistinctCapturedDocuments': len(rows)})
                    print('signed catalog: ' + target + ' (' + str(len(rows)) + ')', flush=True)
                except Exception as exc:
                    catalog['coverage'].append({'SourceURL': cdx_url(target), 'Kind': 'signed-metadata-catalog', 'Status': 'unavailable', 'Error': str(exc)})
                Path(args.catalog).write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    for record in records:
        provenance = record.get('HistoricalProvenance', {})
        stamp = provenance.get('CaptureTimestamp')
        if not stamp: continue
        anchor = datetime.strptime(stamp, '%Y%m%d%H%M%S')
        for part, field in [('InRelease', 'InReleaseURL'), ('Release', 'ReleaseURL'), ('Release.gpg', 'ReleaseSignatureURL')]:
            choices = captures.get((provenance.get('SourceID'), provenance.get('Distribution'), part), [])
            choices = sorted(choices, key=lambda row: abs((datetime.strptime(row[0], '%Y%m%d%H%M%S') - anchor).total_seconds()))
            if choices and abs((datetime.strptime(choices[0][0], '%Y%m%d%H%M%S') - anchor).total_seconds()) <= 5 * 86400:
                actual_stamp, original, _ = choices[0]
                provenance[field] = 'https://web.archive.org/web/' + actual_stamp + 'id_/' + original
    catalog['generated_at'] = utc_now()
    return catalog


class VersionTable(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_cell = False; self.cell = ''; self.row = []; self.versions = []
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag == 'td': self.in_cell = True; self.cell = ''
    def handle_data(self, data):
        if self.in_cell: self.cell += data
    def handle_endtag(self, tag):
        if tag == 'td': self.in_cell = False; self.row.append(self.cell.strip())
        if tag == 'tr' and self.row and re.fullmatch(r'[0-9]+(?:[.][0-9]+){3}[.]g[0-9a-fA-F]+', self.row[0]):
            self.versions.append(self.row[0])


def collect_hints(catalog, observed, timeout, retries):
    hints = {(x['Version'], x['SourceURL']): x for x in catalog.get('discovery_hints', [])}
    sources = [('spotify-desktop-cef', 'https://www.spotify.com/nl/opensource/'),
               ('rpmfusion-lpf-changelog', 'https://raw.githubusercontent.com/rpmfusion/lpf-spotify-client/master/lpf-spotify-client.spec')]
    for kind, url in sources:
        try:
            data = read_url(url, timeout, retries)[0].decode()
            if kind == 'spotify-desktop-cef':
                table = VersionTable(); table.feed(data); versions = table.versions
            else:
                versions = re.findall(r'Update to ([0-9]+(?:[.][0-9]+){3}(?:[.]g[0-9a-fA-F]+)?)', data)
            for version in versions:
                hints[(version, url)] = {'Version': version, 'NumericVersion': version.split('.g')[0],
                    'SourceType': kind, 'SourceURL': url, 'ObservedAt': observed, 'PublishedAt': None,
                    'Channel': 'unknown', 'DebianPackageConfirmed': False,
                    'Note': 'Discovery only; desktop/packager records do not establish Debian channel, source hash or publication date'}
            catalog['coverage'].append({'SourceURL': url, 'Kind': kind, 'Status': 'read', 'VersionHints': len(set(versions))})
        except Exception as exc:
            catalog['coverage'].append({'SourceURL': url, 'Kind': kind, 'Status': 'unavailable', 'Error': str(exc)})
    for page in (1, 2, 3):
        url = 'https://api.github.com/repos/archlinux/aur/commits?' + urlencode({'sha': 'spotify', 'path': 'PKGBUILD', 'per_page': 100, 'page': page})
        try:
            commits = json.loads(read_url(url, timeout, retries)[0])
            if not isinstance(commits, list): raise ValueError('Unexpected public commit API response')
            for commit in commits:
                version = re.search(r'\b([0-9]+(?:[.][0-9]+){3})\b', commit['commit']['message'].splitlines()[0])
                if not version: continue
                source = 'https://github.com/archlinux/aur/commit/' + commit['sha']
                hints[(version[1], source)] = {'Version': version[1], 'NumericVersion': version[1],
                    'SourceType': 'aur-maintainer-commit', 'SourceURL': source, 'ObservedAt': observed,
                    'MaintainerCommittedAt': commit['commit']['committer']['date'], 'PublishedAt': None,
                    'Channel': 'unknown', 'DebianPackageConfirmed': False,
                    'Note': 'Maintainer commit date is not a Spotify publication date; per-commit source/hash needs separate validation'}
            catalog['coverage'].append({'SourceURL': url, 'Kind': 'aur-maintainer-commits', 'Status': 'read', 'Commits': len(commits)})
            if len(commits) < 100: break
        except Exception as exc:
            catalog['coverage'].append({'SourceURL': url, 'Kind': 'aur-maintainer-commits', 'Status': 'unavailable', 'Error': str(exc)})
            break
    catalog['discovery_hints'] = sorted(hints.values(), key=lambda x: (x['NumericVersion'], x['SourceURL']))


def collect_mint(catalog, records, observed, timeout, retries):
    url = MINT + '/dists/virginia/import/binary-amd64/Packages.gz'
    try:
        data, _, final, _ = read_url(url, timeout, retries)
        for raw in package_records(data.decode()):
            evidence = {'Type': 'distribution-index', 'URL': final, 'ObservedAt': observed,
                'Channel': 'unknown', 'PublishedAt': None,
                'DocumentSHA256': hashlib.sha256(data).hexdigest(),
                'Authentication': 'Fresh Mint signature/key checks required before packaging'}
            incoming = source_record(raw, 'unknown', evidence, MINT)
            if not incoming: continue
            incoming.update(Distribution='virginia', DistributionProvenance={'SourceID': 'mint-cvut',
                'Distribution': 'virginia', 'IndexPath': 'import/binary-amd64/Packages'},
                DownloadBaseURLs=[MINT], DownloadURLs=[MINT + '/' + incoming['Filename']])
            same = [r for r in records.values() if r['Version'] == incoming['Version']
                    and r['SHA256'] == incoming['SHA256'] and r['Size'] == incoming['Size']
                    and r['Channel'] in ('stable', 'unstable')]
            for original in same:
                # Use the currently signed distro transport while retaining the
                # independent historical Spotify channel/byte evidence.
                original.setdefault('OriginalFilename', original['Filename'])
                variant = {k: v for k, v in original.items() if k not in ('Evidence', 'SourceVariants', 'Availability')}
                if variant not in original.setdefault('SourceVariants', []):
                    original['SourceVariants'].append(variant)
                for key in ('Filename', 'RepositoryURL', 'PackageIndexURL', 'Distribution', 'DistributionProvenance', 'DownloadBaseURLs', 'DownloadURLs'):
                    original[key] = incoming[key]
                if evidence not in original['Evidence']:
                    original['Evidence'].append(evidence)
            if not same: merge_record(records, incoming)
        catalog['coverage'].append({'SourceURL': url, 'Kind': 'distribution-index', 'Status': 'read'})
    except Exception as exc:
        catalog['coverage'].append({'SourceURL': url, 'Kind': 'distribution-index', 'Status': 'unavailable', 'Error': str(exc)})


def recipe_observations(text, url, commit, observed):
    """Read literal recipe source URLs, never execute or source shell code.

    Arch's ``epoch`` is deliberately not treated as a Debian epoch. A recipe
    filename proves a packaging observation, not the contents of a Debian
    control file, a signed channel, publication date, or continued availability.
    """
    variables = {}
    for name, value in re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*?)\s*$', text, re.M):
        if value.startswith(('(', '$(')) or '`' in value:
            continue
        variables[name] = value.strip().strip('\"\'')
    def expand(value):
        for _ in range(4):
            previous = value
            value = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)',
                lambda match: variables.get(match.group(1) or match.group(2), match.group(0)), value)
            if value == previous: break
        return value
    result = []
    for candidate in re.findall(r'https?://[^\s\"\'<>]+[.]deb', text):
        package_url = expand(candidate)
        if '$' in package_url or '`' in package_url: continue
        path = urlsplit(package_url).path
        match = re.search(r'/spotify-client_([^/]+)_amd64[.]deb$', path)
        if not match: continue
        upstream = match.group(1)
        try: parsed = parse_debian_version(upstream)
        except ValueError: continue
        intended = 'unstable' if '/dists/testing/' in text else ('stable' if '/dists/stable/' in text else 'unknown')
        result.append({'Version': upstream, 'NumericVersion': parsed['numeric'],
            'CommitHash': parsed['commit'], 'Filename': path.lstrip('/'),
            'SourceURL': package_url, 'EvidenceURL': url,
            'EvidenceType': 'aur-debian-source-recipe', 'Channel': 'unknown',
            'RecipeConfiguredChannel': intended, 'DebianEpoch': None, 'DebianControlVersion': None,
            'SHA256': None, 'Size': None, 'PublishedAt': None,
            'MaintainerCommitAt': commit['commit']['committer']['date'],
            'ObservedAt': observed, 'Available': 'not-checked',
            'Note': 'Literal amd64 Debian filename in a primary recipe; not an authenticated Debian index or release-date proof'})
    return result


def collect_recipes(catalog, args):
    global CACHE_DIR
    evidence_dir = Path(args.evidence_dir); evidence_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR = evidence_dir / 'requests'; CACHE_DIR.mkdir(parents=True, exist_ok=True)
    observed, commits = utc_now(), []
    for page in (1, 2, 3):
        url = 'https://api.github.com/repos/archlinux/aur/commits?' + urlencode({'sha': 'spotify', 'path': 'PKGBUILD', 'per_page': 100, 'page': page})
        try:
            rows = json.loads(read_url(url, args.timeout, args.retries)[0])
            if not isinstance(rows, list): raise ValueError('Unexpected public commit API response')
            commits.extend(rows)
            if len(rows) < 100: break
        except Exception as exc:
            catalog['coverage'].append({'SourceURL': url, 'Kind': 'aur-recipe-catalog', 'Status': 'unavailable', 'Error': str(exc)})
            break
    observations = {(r['Version'], r['EvidenceURL']): r for r in catalog.get('debian_observations', [])}
    def run(commit):
        url = 'https://raw.githubusercontent.com/archlinux/aur/' + commit['sha'] + '/PKGBUILD'
        try:
            text = read_url(url, args.timeout, args.retries)[0].decode()
            rows = recipe_observations(text, url, commit, observed)
            return rows, {'SourceURL': url, 'Kind': 'aur-debian-recipe', 'Status': 'read', 'DebianObservations': len(rows)}
        except Exception as exc:
            return [], {'SourceURL': url, 'Kind': 'aur-debian-recipe', 'Status': 'unavailable', 'Error': str(exc)}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for rows, coverage in pool.map(run, commits):
            for row in rows: observations[(row['Version'], row['EvidenceURL'])] = row
            catalog['coverage'].append(coverage)
            catalog['debian_observations'] = sorted(observations.values(), key=lambda r: (r['NumericVersion'], r['EvidenceURL']))
            Path(args.catalog).write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
            (evidence_dir / 'recipe-progress.json').write_text(json.dumps({'UpdatedAt': utc_now(), 'Observations': len(observations), 'LastResult': coverage}, indent=2) + '\n')
            print('recipe ' + coverage['Status'] + ': ' + coverage['SourceURL'], flush=True)
    catalog['generated_at'] = observed
    return catalog


def retry_failed(catalog, args):
    """Retry known missing metadata bodies without recrawling catalogs."""
    global CACHE_DIR
    observed = utc_now()
    evidence_dir = Path(args.evidence_dir); evidence_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR = evidence_dir / 'requests'; CACHE_DIR.mkdir(parents=True, exist_ok=True)
    records = {r['Id']: r for r in catalog['records']}
    missing = [c for c in catalog['coverage'] if c['Kind'] == 'package-index' and c['Status'] != 'read']
    missing.sort(key=lambda c: (not any(stamp in c['SourceURL'] for stamp in ('20260411220746', '20250817133028')),
                                c['SourceURL']))
    by_url = {c['SourceURL']: c for c in catalog['coverage'] if c['Kind'] == 'package-index'}
    def run(coverage):
        url = coverage['SourceURL']
        channel = 'unstable' if '/dists/testing/' in url else 'stable'
        capture_match = re.search(r'/web/(\d{14})id_/', url)
        capture = capture_match.group(1) if capture_match else None
        original = url.split('id_/', 1)[-1] if capture else url
        host = urlsplit(original).hostname
        source_id, base = {'download.spotify.com': ('spotify-download', SPOTIFY_BASES[0]),
            'repository.spotify.com': ('spotify-repository', SPOTIFY_BASES[1]),
            'repository-origin.spotify.com': ('spotify-origin', SPOTIFY_BASES[2])}[host]
        try:
            rows, evidence = index_document(url, channel, captured_at(capture) if capture else observed,
                base, source_id, args.timeout, args.retries, capture)
            return rows, {'SourceURL': url, 'Kind': 'package-index', 'Status': 'read', 'PackageRecords': len(rows)}, evidence
        except Exception as exc:
            return [], dict(coverage, Error=str(exc)), None
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for rows, coverage, evidence in pool.map(run, missing):
            by_url[coverage['SourceURL']] = coverage
            for record in rows: merge_record(records, record)
            if evidence:
                (evidence_dir / (hashlib.sha256(evidence['URL'].encode()).hexdigest() + '.json')).write_text(
                    json.dumps({'Evidence': evidence, 'Records': rows}, indent=2) + '\n')
            catalog['records'] = sorted(records.values(), key=lambda r: (r.get('NumericVersion', ''), r['Version'], r['Channel']))
            catalog['coverage'] = [c for c in catalog['coverage'] if c['Kind'] != 'package-index'] + list(by_url.values())
            Path(args.catalog).write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
            print('retry ' + coverage['Status'] + ': ' + coverage['SourceURL'], flush=True)
    collect_mint(catalog, records, observed, args.timeout, args.retries)
    add_known_transports(records)
    if not args.skip_availability: check_availability(records, observed, args.timeout)
    catalog['records'] = sorted(records.values(), key=lambda r: (r.get('NumericVersion', ''), r['Version'], r['Channel']))
    catalog['generated_at'] = observed
    return catalog


def add_known_transports(records):
    for record in records.values():
        version = record.get('NumericVersion')
        basename = Path(record.get('OriginalFilename', record['Filename'])).name
        if version == '1.2.74.477':
            record['DownloadURLs'].append('https://download.spotify.com/spotify-client_1.2.74.477_amd64.deb')
        if version in ('1.1.42.622', '1.2.18.999', '1.2.79.425', '1.2.86.502', '1.2.95.453'):
            record['DownloadURLs'].append(LITE + '/pool/main/s/spotify-client/' + basename)
        record['DownloadURLs'] = sorted(set(record['DownloadURLs']))


def check_availability(records, observed, timeout):
    checks = {}
    for record in records.values():
        for url in record.get('DownloadURLs', []): checks[url] = None
    def head(url):
        try:
            with urlopen(Request(url, method='HEAD', headers={'User-Agent': 'SpotLight-history-availability/1'}), timeout=timeout) as response:
                return {'URL': url, 'Status': response.status, 'Size': response.headers.get('Content-Length'),
                        'LastModified': response.headers.get('Last-Modified'), 'CheckedAt': observed,
                        'BytesHashVerified': False}
        except Exception as exc:
            return {'URL': url, 'Status': 'unavailable', 'Error': str(exc), 'CheckedAt': observed, 'BytesHashVerified': False}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for url, result in zip(checks, pool.map(head, checks)):
            checks[url] = result
    for record in records.values():
        rows = [checks[url] for url in record.get('DownloadURLs', [])]
        available = any(x.get('Status') == 200 and (x.get('Size') is None or int(x['Size']) == record['Size']) for x in rows)
        record['Availability'] = {'Status': 'head-available-hash-unverified' if available else 'not-confirmed', 'Checks': rows}


def render(catalog, json_path, csv_path=None, markdown_path=None):
    catalog['records'] = sorted(catalog['records'], key=version_key)
    catalog['debian_observations'] = sorted(catalog.get('debian_observations', []), key=lambda r: (version_key(r), r['EvidenceURL']))
    catalog['discovery_hints'] = sorted(catalog.get('discovery_hints', []), key=lambda r: (version_key(r), r['SourceURL']))
    coverage = {(row['Kind'], row['SourceURL']): row for row in catalog['coverage']}
    catalog['coverage'] = sorted(coverage.values(), key=lambda r: (r['Kind'], r['SourceURL']))
    json_path = Path(json_path)
    csv_path = Path(csv_path or json_path.with_suffix('.csv'))
    markdown_path = Path(markdown_path or ROOT / 'docs/spotify-version-history.md')
    for path in (json_path, csv_path, markdown_path): path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    fields = ('RecordType', 'NumericVersion', 'Version', 'DebianEpoch', 'DebianRevision', 'CommitHash', 'Channel', 'PublishedAt', 'FirstObservedAt',
              'SHA256', 'Size', 'Filename', 'SupportedLayout', 'Availability', 'EvidenceURLs')
    with csv_path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        rows = []
        for record in catalog['records']:
            row = {k: record.get(k, '') for k in fields}
            row['RecordType'] = 'package-index'
            try:
                row['DebianEpoch'] = parse_debian_version(record['Version'])['epoch']
            except ValueError:
                row['DebianEpoch'] = record['Version'].split(':', 1)[0] if ':' in record['Version'] else '0'
            row['Availability'] = record.get('Availability', {}).get('Status', 'not-checked')
            row['EvidenceURLs'] = ' | '.join(dict.fromkeys(e['URL'] for e in record.get('Evidence', [])))
            rows.append(row)
        for record in catalog.get('debian_observations', []):
            row = {k: record.get(k, '') for k in fields}
            row.update(RecordType='debian-source-recipe', Availability='not-confirmed', EvidenceURLs=record['EvidenceURL'])
            rows.append(row)
        writer.writerows(sorted(rows, key=lambda row: (version_key(row), row['RecordType'], row['EvidenceURLs'])))
    lines = ['# Spotify Debian version evidence inventory', '',
        'Generated from bounded public metadata reads at `' + catalog['generated_at'] + '`.', '',
        '**Coverage is incomplete.** This is an evidence inventory, not a claim that every Spotify release is known or installable. '
        'The collector never downloads application DEBs. CI must freshly authenticate metadata, verify actual DEB bytes and scan them before publication.', '',
        'Publisher release dates remain **unknown** unless an explicit publisher statement proves them. '
        'Archive capture times, index dates, mirror modification dates and maintainer commits are separate observations.', '',
        'The user-approved 31 October 2026 baseline is stable `1.2.95.453` and testing/unstable `1.3.4.258`. '
        'The earlier `1.2.86.502` example is a historical testing build, not the actual baseline stable build. '
        'Spotify names its unstable Debian distribution `testing`; the helper calls that channel `unstable`.', '',
        'The public historical helper name uses four numeric components. Raw Debian epochs/revisions and the full variable-length `.g` value are retained below and in the JSON/CSV.', '',
        '## Package-index records', '',
        f"{len(catalog['records'])} distinct package/channel/hash records; {len(catalog.get('discovery_hints', []))} unclassified discovery hints.", '',
        '| Numeric version | Full Debian version | Full commit | Channel evidence | Published | First observed (UTC) | SHA256 / bytes | Available | Source evidence |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for record in catalog['records']:
        urls = dict.fromkeys(e['URL'] for e in record.get('Evidence', []))
        links = ' '.join('[source ' + str(i + 1) + '](' + url + ')' for i, url in enumerate(urls))
        lines.append('| ' + ' | '.join(str(x).replace('|', '\\|') for x in (
            record.get('NumericVersion', '?'), '`' + record['Version'] + '`', record.get('CommitHash', '') or 'unknown',
            record['Channel'], record.get('PublishedAt') or 'unknown', record.get('FirstObservedAt') or 'unknown',
            '`' + record['SHA256'] + '` / ' + str(record['Size']), record.get('Availability', {}).get('Status', 'not-checked'), links)) + ' |')
    observations = catalog.get('debian_observations', [])
    lines += ['', '## Debian filename observations in primary packaging recipes', '',
        f"{len(observations)} recipe observations; {len(set(r['Version'] for r in observations))} distinct full amd64 filename versions. "
        'These are Debian source URL observations, not installable source records. Debian epoch/control revision, size and authenticated checksum may be unknown. '
        'A recipe-configured channel is a maintainer setting, not proof from a signed Spotify index. Commit timestamps are maintainer observations, not publisher dates.', '',
        '| Full filename version | Numeric version | Commit | Recipe channel setting | Debian epoch | Published | Maintainer commit (UTC) | Debian filename | Evidence |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in observations:
        lines.append('| `' + row['Version'] + '` | ' + row['NumericVersion'] + ' | ' + (row['CommitHash'] or 'unknown')
            + ' | ' + row['RecipeConfiguredChannel'] + ' | unknown | unknown | ' + row['MaintainerCommitAt']
            + ' | `' + row['Filename'] + '` | [recipe](' + row['EvidenceURL'] + ') |')
    lines += ['', '## Discovery hints without Debian channel/hash proof', '',
        'The Spotify CEF table includes desktop builds for multiple platforms. LPF/AUR records are packaging observations. '
        'These hints are not used as source-authentication authority or automatic channel assignments.', '',
        '| Version as observed | Source type | Channel | Publisher date | Evidence |', '| --- | --- | --- | --- | --- |']
    for hint in catalog.get('discovery_hints', []):
        lines.append('| `' + hint['Version'] + '` | ' + hint['SourceType'] + ' | unknown | unknown | [source](' + hint['SourceURL'] + ') |')
    lines += ['', '## Reviewed channel observation pairs', '',
        'These pairs describe the cited observation window. They do not turn capture timestamps into publisher release dates. '
        'Other counterparts require explicit owner selection when chronology is not evidenced.', '',
        '| Stable full source | Testing full source | Observation anchor | Evidence |', '| --- | --- | --- | --- |']
    by_id = {r['Id']: r for r in catalog['records']}
    for pair in catalog.get('reviewed_pairs', []):
        if not pair.get('reviewed'): continue
        lines.append('| `' + by_id[pair['stable']]['Version'] + '` | `' + by_id[pair['unstable']]['Version']
            + '` | ' + pair.get('AnchorObservedAt', 'unknown') + ' | '
            + ' '.join('[source ' + str(i + 1) + '](' + e['URL'] + ')' for i, e in enumerate(pair['Evidence'])) + ' |')
    lines += ['', '## Source coverage and gaps', '',
        'Failed fetches and sparse archive captures remain explicit. An unavailable historical counterpart must be supplied manually; numerical ordering does not establish publication chronology.', '',
        '| Source | Type | Result | Details |', '| --- | --- | --- | --- |']
    for coverage in catalog['coverage']:
        detail = coverage.get('Error', '') or ', '.join(str(k) + '=' + str(v) for k, v in coverage.items() if k not in ('SourceURL', 'Kind', 'Status'))
        lines.append('| [source](' + coverage['SourceURL'] + ') | ' + coverage['Kind'] + ' | ' + coverage['Status'] + ' | ' + detail.replace('|', '\\|').replace('\n', ' ') + ' |')
    lines += ['', 'Legacy Qt/native package layouts are recorded for research but rejected by the current Chromium local builder. '
        'HEAD availability does not prove a DEB checksum or current runtime compatibility. Historical signatures and key validity are rechecked by the publishing workflow.', '']
    lines += ['## Reproduce and retry', '',
        'Run `python3 tools/collect_spotify_history.py` to refresh bounded metadata, literal primary recipes and actual signed-metadata capture candidates. '
        'The collector never executes recipes or fetches application DEBs. Use `--retry-only` to retry recorded package-index gaps, '
        '`--recipes-only` for primary recipe metadata, `--signed-bundles-only` for actual signature capture catalogs, or `--render-only` to export existing data without network access. '
        'Ignored request caches and progress reports are kept under `output/spotify-history-evidence/`; successful archive bodies are reused. '
        'Adding signed capture URLs does not establish their validity until the source verifier matches the signed index digest and package record.', '']
    markdown_path.write_text('\n'.join(lines), encoding='utf-8')


def collect(args):
    global CACHE_DIR
    observed = utc_now()
    path = Path(args.catalog)
    catalog = json.loads(path.read_text()) if path.exists() else {'schema': 1, 'records': [], 'discovery_hints': [], 'reviewed_pairs': []}
    catalog.update(generated_at=observed, baseline=BASELINE, coverage=[])
    records = {r['Id']: r for r in catalog['records']}
    evidence_dir = Path(args.evidence_dir); evidence_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR = evidence_dir / 'requests'; CACHE_DIR.mkdir(parents=True, exist_ok=True)
    def checkpoint():
        catalog['records'] = sorted(records.values(), key=lambda r: (r.get('NumericVersion', ''), r['Version'], r['Channel'], r['SHA256']))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
        temporary.replace(path)
        (evidence_dir / 'progress.json').write_text(json.dumps({'UpdatedAt': utc_now(),
            'Records': len(records), 'Coverage': catalog['coverage']}, indent=2) + '\n')
    checkpoint()
    jobs, seen = [], set()
    source_ids = {'download.spotify.com': 'spotify-download', 'repository.spotify.com': 'spotify-repository', 'repository-origin.spotify.com': 'spotify-origin'}
    for base in SPOTIFY_BASES:
        source_id = source_ids[urlsplit(base).hostname]
        for channel, distribution in (('stable', 'stable'), ('unstable', 'testing')):
            url = base + f'/dists/{distribution}/non-free/binary-amd64/Packages'
            jobs.append((url, channel, observed, base, source_id, None))
            for suffix in ('', '.gz', '.bz2'):
                target = url.removeprefix('https://') + suffix
                try:
                    captures = cdx_records(target, args.timeout, args.retries)
                    catalog['coverage'].append({'SourceURL': cdx_url(target), 'Kind': 'archive-catalog', 'Status': 'read', 'DistinctCapturedDocuments': len(captures)})
                    print('catalog: ' + target + ' (' + str(len(captures)) + ' captured documents)', flush=True)
                    for stamp, original, digest in captures:
                        key = (channel, stamp, original)
                        if key in seen: continue
                        seen.add(key)
                        jobs.append((f'https://web.archive.org/web/{stamp}id_/{original}', channel, captured_at(stamp), base, source_id, stamp))
                except Exception as exc:
                    catalog['coverage'].append({'SourceURL': cdx_url(target), 'Kind': 'archive-catalog', 'Status': 'unavailable', 'Error': str(exc)})
                checkpoint()
    def run(job):
        url, channel, stamp, base, source_id, capture = job
        try:
            rows, evidence = index_document(url, channel, stamp, base, source_id, args.timeout, args.retries, capture)
            return rows, {'SourceURL': url, 'Kind': 'package-index', 'Status': 'read', 'PackageRecords': len(rows)}, evidence
        except Exception as exc:
            return [], {'SourceURL': url, 'Kind': 'package-index', 'Status': 'unavailable', 'Error': str(exc)}, None
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(run, job) for job in jobs]):
            rows, coverage, evidence = future.result()
            catalog['coverage'].append(coverage)
            for record in rows: merge_record(records, record)
            if evidence:
                digest = hashlib.sha256(evidence['URL'].encode()).hexdigest()
                (evidence_dir / (digest + '.json')).write_text(json.dumps({'Evidence': evidence, 'Records': rows}, indent=2) + '\n')
            print(coverage['Status'] + ': ' + coverage['SourceURL'], flush=True)
            checkpoint()
    collect_mint(catalog, records, observed, args.timeout, args.retries)
    add_known_transports(records)
    if not args.skip_availability: check_availability(records, observed, args.timeout)
    collect_hints(catalog, observed, args.timeout, args.retries)
    catalog['records'] = sorted(records.values(), key=lambda r: (r.get('NumericVersion', ''), r['Version'], r['Channel'], r['SHA256']))
    if not args.skip_recipes:
        collect_recipes(catalog, args)
    if not args.skip_signed_bundles:
        collect_signed_bundles(catalog, args)
    catalog['coverage'] = sorted(catalog['coverage'], key=lambda x: (x['Kind'], x['SourceURL']))
    render(catalog, path, args.csv, args.markdown)
    print(json.dumps({'records': len(catalog['records']), 'hints': len(catalog['discovery_hints']),
                      'unavailable_sources': sum(x['Status'] != 'read' for x in catalog['coverage'])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', default=str(ROOT / 'data/spotify-history.json'))
    parser.add_argument('--csv')
    parser.add_argument('--markdown')
    parser.add_argument('--evidence-dir', default=str(ROOT / 'output/spotify-history-evidence'))
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--retries', type=int, choices=(0, 1, 2), default=1)
    parser.add_argument('--skip-availability', action='store_true')
    parser.add_argument('--skip-recipes', action='store_true')
    parser.add_argument('--skip-signed-bundles', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    parser.add_argument('--recipes-only', action='store_true', help='Add bounded primary AUR recipe metadata to an existing catalog')
    parser.add_argument('--retry-only', action='store_true', help='Retry recorded metadata gaps without crawling archive catalogs again')
    parser.add_argument('--signed-bundles-only', action='store_true', help='Associate actual archived Release/signature captures; verification remains mandatory')
    args = parser.parse_args()
    if args.render_only:
        render(json.loads(Path(args.catalog).read_text()), args.catalog, args.csv, args.markdown)
    elif args.recipes_only:
        catalog = collect_recipes(json.loads(Path(args.catalog).read_text()), args)
        render(catalog, args.catalog, args.csv, args.markdown)
    elif args.retry_only:
        catalog = retry_failed(json.loads(Path(args.catalog).read_text()), args)
        render(catalog, args.catalog, args.csv, args.markdown)
    elif args.signed_bundles_only:
        catalog = collect_signed_bundles(json.loads(Path(args.catalog).read_text()), args)
        render(catalog, args.catalog, args.csv, args.markdown)
    else: collect(args)


if __name__ == '__main__':
    main()
