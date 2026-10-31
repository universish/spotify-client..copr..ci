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

REPOSITORIES = ("https://download.spotify.com/debian", "https://repository.spotify.com",
                "https://repository-origin.spotify.com")
# A community mirror can transport pinned bytes, but never supplies trusted
# version/channel/checksum metadata. Official source hashes remain mandatory.
DOWNLOAD_BASES = (*REPOSITORIES, "https://deb.rug.nl/ppa/mirror/repository.spotify.com")
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


def parse_packages(text: str):
    packages, current, last_key = [], {}, None
    for line in text.splitlines():
        if not line.strip() or (line.startswith("Package:") and current):
            if current:
                packages.append(current)
            current, last_key = {}, None
            if not line.strip():
                continue
        if line.startswith((" ", "\t")) and last_key:
            current[last_key] += "\n" + line.strip()
            continue
        key, value = line.split(":", 1)
        current[key] = value.strip()
        last_key = key
    if current:
        packages.append(current)
    return packages


class RequestedVersionNotFound(RuntimeError):
    """The requested version has no usable record in this official channel."""


class AmbiguousVersionError(ValueError):
    """A short version identifies more than one officially indexed source."""


def matches_requested_version(version, requested):
    if version == requested:
        return True
    return bool(re.fullmatch(r'[0-9]+(?:[.][0-9]+){3}', requested)
                and re.fullmatch(re.escape(requested) + r'[.]g[0-9a-fA-F]+', version))


def fetch_package(branch="stable", package="spotify-client", *, audit_rpmfusion=True, requested_version=None):
    if branch not in CHANNELS:
        raise ValueError("channel must be stable or unstable (testing)")
    distribution = CHANNELS[branch]
    channel = "stable" if distribution == "stable" else "unstable"
    selected = None
    for base in REPOSITORIES:
        url = f"{base}/dists/{distribution}/non-free/binary-amd64/Packages"
        try:
            with request.urlopen(url, timeout=30) as response:
                records = parse_packages(response.read().decode("utf-8"))
            candidates = [r for r in records if r.get("Package") == package and r.get("Architecture") == "amd64"]
            if requested_version is not None:
                candidates = [r for r in candidates if matches_requested_version(r.get('Version', '').split(':', 1)[-1], requested_version)]
                unique = {(r.get('Version'), r.get('SHA256'), r.get('Filename'), r.get('Size')): r for r in candidates}
                if len(unique) > 1:
                    versions = ', '.join(sorted({r['Version'] for r in unique.values()}))
                    raise AmbiguousVersionError('Requested version matches multiple sources or conflicting metadata in ' + channel + '; use an unambiguous full version and official source record: ' + versions)
                candidates = list(unique.values())
            record = next(iter(candidates), None)
            if record is None or record.get("Architecture") != "amd64":
                raise ValueError("No matching amd64 package record")
            version = record["Version"].split(":", 1)[-1]
            if not re.fullmatch(r"[A-Za-z0-9.+~]+", version):
                raise ValueError("Unsupported RPM version")
            if not re.fullmatch(r"[0-9a-f]{64}", record.get("SHA256", "")):
                raise ValueError("Missing or invalid SHA256")
            if not re.fullmatch(r"pool/non-free/s/spotify-client/[A-Za-z0-9_.+~-]+[.]deb", record.get("Filename", "")):
                raise ValueError("Unexpected upstream DEB path")
            if not record.get("Size", "").isdigit() or int(record["Size"]) <= 0:
                raise ValueError("Missing or invalid DEB size")
            record.update(RPMVersion=version, RepositoryURL=base, PackageIndexURL=url,
                          DownloadBaseURLs=list(DOWNLOAD_BASES), Channel=channel, Distribution=distribution)
            print(f"Spotify package metadata: {url}", file=sys.stderr)
            selected = record
            break
        except error.HTTPError as exc:
            print(f"Package index unavailable (HTTP {exc.code}): {url}", file=sys.stderr)
            exc.close()
        except AmbiguousVersionError:
            raise
        except (error.URLError, TimeoutError, ValueError, UnicodeError, OSError, HTTPException):
            print(f"Package index unavailable or invalid: {url}", file=sys.stderr)
    # Always last; a newer LPF bootstrap is useful evidence but not sufficient
    # authority to reclassify a Spotify testing DEB as stable or invent a hash.
    observations = check_rpmfusion() if audit_rpmfusion else []
    if selected is not None:
        selected["RPMFusionChecks"] = observations
        return selected
    if requested_version is not None:
        raise RequestedVersionNotFound('Requested Spotify version is not advertised in accessible official ' + channel + ' indexes: ' + requested_version)
    raise RuntimeError("No official Spotify package index is usable; RPM Fusion candidates cannot establish the DEB channel/checksum; stopping")


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
