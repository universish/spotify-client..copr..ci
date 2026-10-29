#!/usr/bin/env bash
set -euo pipefail
branch=${1:?Branch required}
version=${2:?Version required}
metadata_dir=${SPOTIFY_METADATA_DIR:-/tmp}
download_dir=${SPOTIFY_DOWNLOAD_DIR:-/tmp}
mkdir -p "$download_dir"
if [[ "${SOURCE:-deb}" != deb ]]; then
    echo 'This fork packages the official Debian source only; SOURCE must be deb.' >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 - "$metadata_dir/spotify-client.$branch.json" "$version" "$download_dir" "$script_dir" "${SPOTIFY_DEB_FILE:-}" <<'DOWNLOAD'
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib import error, request
sys.path.insert(0, sys.argv[4])
from parser_debian_control_file import REPOSITORIES

record = json.loads(Path(sys.argv[1]).read_text())
version, directory = sys.argv[2], Path(sys.argv[3])
if record.get("RPMVersion") != version or record.get("Architecture") != "amd64":
    raise SystemExit("Spotify metadata version/architecture mismatch; detect the version again")
filename, digest = record["Filename"], record["SHA256"]
if not re.fullmatch(r"pool/non-free/s/spotify-client/[A-Za-z0-9_.+~-]+[.]deb", filename):
    raise SystemExit("Unexpected upstream DEB path")
if not re.fullmatch(r"[0-9a-f]{64}", digest):
    raise SystemExit("Missing or invalid upstream SHA256")
destination = directory / f"spotify-client_{version}_amd64.deb"
if sys.argv[5]:
    # LPF can reuse a previously downloaded source; it still gets the same verification and scan.
    cached = Path(sys.argv[5])
    fd, temporary = tempfile.mkstemp(prefix=".spotify-cache-", dir=directory)
    try:
        checksum, size = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as output, cached.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
                checksum.update(chunk)
                size += len(chunk)
        if checksum.hexdigest() != digest or size != int(record["Size"]):
            raise SystemExit("Cached DEB checksum/size mismatch; stopping before extraction")
        os.replace(temporary, destination)
        print(f"Verified cached DEB {cached} (SHA256 {digest})")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    raise SystemExit(0)
for base in REPOSITORIES:
    fd, temporary = tempfile.mkstemp(prefix=".spotify-download-", dir=directory)
    try:
        checksum, size = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as output:
            try:
                response = request.urlopen(base + "/" + filename, timeout=120)
            except error.HTTPError as exc:
                print(f"DEB source unavailable (HTTP {exc.code}): {base}", file=sys.stderr)
                exc.close()
                continue
            except (error.URLError, TimeoutError):
                print(f"DEB source unavailable: {base}", file=sys.stderr)
                continue
            with response:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    checksum.update(chunk)
                    size += len(chunk)
        # A downloaded but altered file is rejected, not silently replaced by a mirror.
        if checksum.hexdigest() != digest or size != int(record["Size"]):
            raise SystemExit("DEB checksum/size mismatch; stopping before extraction")
        os.replace(temporary, destination)
        print(f"Verified {destination} from {base} (SHA256 {digest})")
        break
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
else:
    raise SystemExit("Neither official Spotify DEB download source is usable")
DOWNLOAD
