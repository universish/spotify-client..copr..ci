#!/usr/bin/env python3
"""Read Spotify's package index; retain the exact record for checksum validation."""
import json
import os
import re
import sys
from pathlib import Path
from urllib import error, request

REPOSITORIES = ("https://download.spotify.com/debian", "https://repository.spotify.com")


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


def fetch_package(branch, package="spotify-client"):
    if branch != "stable":
        raise ValueError("only the stable branch is packaged")
    for base in REPOSITORIES:
        url = f"{base}/dists/{branch}/non-free/binary-amd64/Packages"
        try:
            with request.urlopen(url, timeout=30) as response:
                records = parse_packages(response.read().decode("utf-8"))
            record = next((r for r in records if r.get("Package") == package), None)
            if record is None or record.get("Architecture") != "amd64":
                raise ValueError("No matching amd64 package record")
            version = record["Version"].split(":", 1)[-1]
            if not re.fullmatch(r"[A-Za-z0-9.+~]+", version):
                raise ValueError("Unsupported RPM version")
            if not re.fullmatch(r"[0-9a-f]{64}", record.get("SHA256", "")):
                raise ValueError("Missing or invalid SHA256")
            record.update(RPMVersion=version, RepositoryURL=base, PackageIndexURL=url,
                          DownloadBaseURLs=list(REPOSITORIES))
            print(f"Spotify package metadata: {url}", file=sys.stderr)
            return record
        except error.HTTPError as exc:
            print(f"Package index unavailable (HTTP {exc.code}): {url}", file=sys.stderr)
            exc.close()
        except (error.URLError, TimeoutError, ValueError, UnicodeError):
            print(f"Package index unavailable or invalid: {url}", file=sys.stderr)
    raise RuntimeError("Neither official Spotify package index is usable; stopping")


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
