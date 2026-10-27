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
python3 - "$metadata_dir/spotify-client.$branch.json" "$version" "$download_dir" <<'DOWNLOAD'
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib import request

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
fd, temporary = tempfile.mkstemp(prefix=".spotify-download-", dir=directory)
try:
    checksum, size = hashlib.sha256(), 0
    with os.fdopen(fd, "wb") as output:
        with request.urlopen("https://repository.spotify.com/" + filename, timeout=120) as response:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                checksum.update(chunk)
                size += len(chunk)
    if checksum.hexdigest() != digest or size != int(record["Size"]):
        raise SystemExit("DEB checksum/size mismatch; stopping before extraction")
    os.replace(temporary, destination)
    print(f"Verified {destination} (SHA256 {digest})")
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
DOWNLOAD
