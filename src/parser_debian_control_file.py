#!/usr/bin/env python3
"""Read Spotify's package index; retain the exact record for checksum validation."""
import json
import os
import re
import sys
from pathlib import Path
from urllib import request


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
    url = f"https://repository.spotify.com/dists/{branch}/non-free/binary-amd64/Packages"
    with request.urlopen(url, timeout=60) as response:
        records = parse_packages(response.read().decode("utf-8"))
    record = next((r for r in records if r.get("Package") == package), None)
    if record is None or record.get("Architecture") != "amd64":
        raise ValueError(f"No amd64 {package} record in {branch}")
    version = record["Version"].split(":", 1)[-1]
    if not re.fullmatch(r"[A-Za-z0-9.+~]+", version):
        raise ValueError(f"Unsupported RPM version: {version!r}")
    record["RPMVersion"] = version
    return record


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
