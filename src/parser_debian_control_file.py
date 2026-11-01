#!/usr/bin/env python3
"""Read Spotify's package index; retain the exact record for checksum validation."""
import json
import gzip
import hashlib
from http.client import HTTPException
import io
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import error, request
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

# Keep one reviewed registry for metadata authorities and byte transports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_auth
from release_identity import parse_debian_version

REPOSITORIES = tuple(s['base_url'] for s in source_auth.spotify_sources())
DOWNLOAD_BASES = source_auth.download_bases()
CHANNELS = {"stable": "stable", "unstable": "testing", "testing": "testing"}
RPMFUSION = "https://download1.rpmfusion.org/nonfree/fedora/"
# Fedora's testing repository is not Spotify's testing channel. These checks are
# observations only: a bootstrap RPM version cannot establish a DEB's channel or
# its SHA256. A candidate must still be verified by an official package index.
RPMFUSION_PATHS = (
    ("fedora-44-release", "releases/44/Everything/x86_64/os/"),
    ("fedora-44-updates", "updates/44/x86_64/"),
    ("fedora-44-updates-testing", "updates/testing/44/x86_64/"),
    ("fedora-rawhide", "development/rawhide/Everything/x86_64/os/"),
)


def _read_url(url, limit, timeout=15):
    with request.urlopen(url, timeout=timeout) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Metadata exceeds size limit")
    return data


def _rpmfusion_check(item):
    name, path = item
    base = RPMFUSION + path
    result = {"repository": name, "url": base, "status": "unavailable", "packages": []}
    try:
        repomd = ET.fromstring(_read_url(base + "repodata/repomd.xml", 1024 * 1024))
        ns = {"r": "http://linux.duke.edu/metadata/repo"}
        primary = repomd.find("r:data[@type='primary']", ns)
        if primary is None:
            raise ValueError("No primary metadata")
        location, checksum = primary.find("r:location", ns), primary.find("r:checksum", ns)
        if location is None or checksum is None or checksum.get("type") != "sha256":
            raise ValueError("No SHA256 primary metadata")
        href = location.get("href", "")
        if not href.startswith("repodata/") or ".." in href.split("/"):
            raise ValueError("Unexpected primary metadata path")
        url = urljoin(base, href)
        if urlsplit(url).netloc != urlsplit(RPMFUSION).netloc:
            raise ValueError("Unexpected primary metadata origin")
        data = _read_url(url, 32 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != checksum.text:
            raise ValueError("Primary metadata checksum mismatch")
        if href.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as source:
                data = source.read(128 * 1024 * 1024 + 1)
        if len(data) > 128 * 1024 * 1024:
            raise ValueError("Uncompressed primary metadata exceeds limit")
        common = "{http://linux.duke.edu/metadata/common}"
        for _, element in ET.iterparse(io.BytesIO(data), events=("end",)):
            if element.tag != common + "package":
                continue
            package = element.findtext(common + "name")
            if package == "lpf-spotify-client":
                version = element.find(common + "version")
                if version is not None:
                    result["packages"].append({"name": package, "version": version.get("ver"),
                                               "release": version.get("rel"),
                                               "architecture": element.findtext(common + "arch")})
            element.clear()
        result["status"] = "ok"
    except (error.URLError, TimeoutError, ValueError, ET.ParseError, OSError, HTTPException) as exc:
        result["error"] = type(exc).__name__
    return result


def check_rpmfusion():
    """Check all requested Fedora repositories, after official DEB discovery.

    This never downloads a client RPM or confuses Fedora repository stability
    with the Spotify release channel. HTTPS metadata integrity is checked; no
    assertion of an RPM GPG signature is made.
    """
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_rpmfusion_check, RPMFUSION_PATHS))
    for result in results:
        versions = ", ".join(p["version"] for p in result["packages"]) or "no candidate"
        print(f"Last-priority RPM Fusion check: {result['repository']}: {result['status']} ({versions})", file=sys.stderr)
    return results


def parse_packages(text):
    return source_auth.parse_control_records(text)


class RequestedVersionNotFound(RuntimeError):
    """The requested version has no authenticated record in this channel."""


class AmbiguousVersionError(ValueError):
    """A short version identifies more than one authenticated source."""


def matches_requested_version(version, requested):
    parsed = parse_debian_version(version)
    return requested in (parsed['raw'], parsed['upstream'], parsed['numeric'], parsed['rpm_version'])


def _normalize(record, evidence, *, channel=None, extra=None):
    result = dict(record)
    if extra:
        result.update(extra)
    parsed = parse_debian_version(result.get('DebianVersion', result.get('Version', '')))
    result.update(Version=parsed['raw'], DebianVersion=parsed['raw'], RPMVersion=parsed['rpm_version'],
                  NumericVersion=parsed['numeric'], CommitHash=parsed['commit'],
                  UpstreamVersion=parsed['upstream'], DebianEpoch=parsed['epoch'],
                  DebianRevision=parsed['revision'])
    info = source_auth.source(evidence['RepositoryID'])
    distribution = evidence['Distribution']
    if info['kind'] == 'spotify':
        expected_channel = 'stable' if distribution == 'stable' else 'unstable'
        if channel is not None and channel != expected_channel:
            raise source_auth.AuthenticationError('Spotify signature distribution disagrees with requested channel')
        channel = expected_channel
        bases = [s['base_url'] for s in source_auth.registry()['sources']
                 if s.get('enabled') and (s['kind'] == 'spotify' or s['id'] == 'rug-spotify-bytes')]
    else:
        # A distro signature authenticates bytes, never a Spotify release channel.
        # Channel membership must have been established separately by the history planner.
        channel = channel or result.get('Channel', 'unknown')
        bases = [info['base_url']]
    result.update(RepositoryURL=info['base_url'], Distribution=distribution, Channel=channel,
                  PackageIndexURL=evidence.get('PackageIndexURL', info['base_url'] + '/dists/' + distribution + '/' + evidence['IndexPath']),
                  DownloadBaseURLs=bases)
    source_auth.find_bound_record(source_auth.decode_evidence(evidence)['Packages'], result)
    return source_auth.bind_record(result, evidence)


def fetch_package(branch="stable", package="spotify-client", *, audit_rpmfusion=True,
                  requested_version=None, accepted_state=None):
    if branch not in CHANNELS:
        raise ValueError("channel must be stable or unstable (testing)")
    if package != 'spotify-client':
        raise ValueError('Only the Spotify amd64 client is supported')
    distribution = CHANNELS[branch]
    channel = "stable" if distribution == "stable" else "unstable"
    selected = None
    for info in source_auth.spotify_sources():
        try:
            data, evidence = source_auth.verify_repository(info['id'], distribution, accepted_state=accepted_state)
            candidates = [r for r in parse_packages(data)
                          if r.get('Package') == package and r.get('Architecture') == 'amd64']
            if requested_version is not None:
                candidates = [r for r in candidates if matches_requested_version(r.get('Version', ''), requested_version)]
            unique = {(r.get('Version'), r.get('SHA256'), r.get('Filename'), r.get('Size')): r for r in candidates}
            if len(unique) > 1:
                raise AmbiguousVersionError('Authenticated index has multiple matching Spotify versions or conflicting records; use the full Debian version')
            if not unique:
                continue
            selected = _normalize(next(iter(unique.values())), evidence, channel=channel)
            print('Authenticated Spotify metadata: ' + selected['PackageIndexURL'], file=sys.stderr)
            break
        except (source_auth.SourceUnavailable, source_auth.MetadataRollback) as exc:
            # An older mirror is not accepted; a later transport can still carry
            # the publisher's accepted or newer signed snapshot.
            print('Signed Spotify metadata unavailable: ' + info['id'] + ': ' + str(exc), file=sys.stderr)
        # AuthenticationError is intentionally fatal: a bad signature, suite,
        # hash or key must never downgrade to unsigned discovery or another trust path.
    observations = check_rpmfusion() if audit_rpmfusion else []
    if selected is not None:
        selected['RPMFusionChecks'] = observations
        return selected
    if requested_version is not None:
        raise RequestedVersionNotFound('Requested Spotify version is not advertised in accessible authenticated ' + channel + ' indexes: ' + requested_version)
    raise RuntimeError('No authenticated Spotify package index is usable; RPM Fusion candidates cannot establish the DEB channel/checksum; stopping')


def verify_distribution_record(record, *, accepted_state=None):
    provenance = record.get('DistributionProvenance')
    if not isinstance(provenance, dict):
        raise source_auth.AuthenticationError('Distribution provenance is required')
    info = source_auth.source(provenance.get('SourceID'))
    if info['kind'] != 'distribution':
        raise source_auth.AuthenticationError('Historical distribution source is not a registered distro authority')
    distribution = provenance.get('Distribution')
    if provenance.get('IndexPath') != info.get('distributions', {}).get(distribution, {}).get('index_path'):
        raise source_auth.AuthenticationError('Distribution index path is not registered')
    data, evidence = source_auth.verify_repository(info['id'], distribution, accepted_state=accepted_state)
    exact = source_auth.find_bound_record(data, record)
    for key in ('OriginalSHA256', 'SpotifySHA256'):
        if record.get(key) and record[key] != exact['SHA256']:
            raise source_auth.AuthenticationError('Distro bytes conflict with independently recorded Spotify SHA256')
    return _normalize(exact, evidence, channel=record.get('Channel'), extra=record)


def _snapshot_url(url, expected):
    if url == expected:
        return {urlsplit(expected).hostname}
    # A replay transport supplies only bytes. The pinned OpenPGP chain remains
    # authoritative, and each capture must name the exact registered original.
    match = re.fullmatch(r'https://web[.]archive[.]org/web/[0-9]{14}id_/(https?://.+)', str(url))
    original = urlsplit(match.group(1)) if match else None
    canonical = urlsplit(expected)
    if (original is None or original.scheme not in ('http', 'https')
            or original.hostname != canonical.hostname or original.path != canonical.path
            or original.username or original.password or original.query or original.fragment
            or original.port not in (None, 80 if original.scheme == 'http' else 443)):
        raise source_auth.AuthenticationError('Historical metadata URL is not an approved exact archive capture')
    return {'web.archive.org'}


def verify_historical_record(record, *, accepted_state=None):
    if record.get('Authentication') is not None:
        data, evidence = source_auth.replay_authentication(record, accepted_state=accepted_state)
        exact = source_auth.find_bound_record(data, record)
        return _normalize(exact, evidence, channel=record.get('Channel'), extra=record)
    if record.get('DistributionProvenance'):
        return verify_distribution_record(record, accepted_state=accepted_state)
    provenance = record.get('HistoricalProvenance')
    if not isinstance(provenance, dict):
        raise source_auth.AuthenticationError('Historical source has no revalidatable signed provenance')
    info = source_auth.source(provenance.get('SourceID'))
    distribution = provenance.get('Distribution')
    index_path = provenance.get('IndexPath')
    if (info['kind'] != 'spotify' or distribution not in info.get('distributions', {})
            or index_path != info['distributions'][distribution]['index_path']):
        raise source_auth.AuthenticationError('Historical Spotify authority/distribution/index is not registered')
    base = info['base_url'] + '/dists/' + distribution + '/'
    def fetch(field, path):
        url = provenance.get(field)
        hosts = _snapshot_url(url, base + path)
        return source_auth.read_url(url, hosts=hosts)
    packages = fetch('PackageIndexURL', index_path)
    # Some archive captures store a compressed Packages representation without
    # restoring the original Content-Encoding header. Bound decompression still
    # has to match the uncompressed Packages checksum in the signed Release.
    if packages.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(packages)) as stream:
            packages = stream.read(source_auth.METADATA_LIMIT + 1)
        if len(packages) > source_auth.METADATA_LIMIT:
            raise source_auth.AuthenticationError('Historical package index exceeds size limit')
    inline = release = signature = None
    if provenance.get('InReleaseURL'):
        inline = fetch('InReleaseURL', 'InRelease')
    elif provenance.get('ReleaseURL') and provenance.get('ReleaseSignatureURL'):
        release = fetch('ReleaseURL', 'Release')
        signature = fetch('ReleaseSignatureURL', 'Release.gpg')
    else:
        raise source_auth.AuthenticationError('Historical Packages lacks an actual captured signed Release')
    data, evidence = source_auth.verify_snapshot(info['id'], distribution, index_path, packages,
        inrelease=inline, release=release, signature=signature, accepted_state=accepted_state)
    evidence.update({key: provenance[key] for key in ('PackageIndexURL', 'InReleaseURL', 'ReleaseURL', 'ReleaseSignatureURL') if provenance.get(key)})
    exact = source_auth.find_bound_record(data, record)
    return _normalize(exact, evidence, channel=record.get('Channel'), extra=record)


def main():
    branch, package, field = sys.argv[1:]
    record = fetch_package(branch, package)
    directory = Path(os.environ.get("SPOTIFY_METADATA_DIR", "/tmp"))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{package}.{branch}.json").write_text(json.dumps(record), encoding="utf-8")
    value = record["RPMVersion"] if field == "Version" else record[field]
    (directory / f"{package}.{branch}.{field}").write_text(value, encoding="utf-8")
    print(value)


if __name__ == "__main__":
    main()
