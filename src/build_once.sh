#!/usr/bin/env bash
# Build one scanned source RPM of the stable x86_64 client.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PATH="$script_dir:$PATH"
branch=${1:-stable}
output=${2:-./output}
mkdir -p "$output"
output=$(realpath "$output")
work=$(mktemp -d "${TMPDIR:-/tmp}/spotify-once.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
export BUILD_DIR="$work/rpmbuild"
export SOURCES_DIR="$BUILD_DIR/SOURCES"
export SPOTIFY_METADATA_DIR="$work/metadata"
export SPOTIFY_DOWNLOAD_DIR="$work/downloads"
export SCAN_REPORT_DIR="$output/scan-reports"
export SOURCE=deb
export BUILTIN_FFMPEG=${BUILTIN_FFMPEG:-false}
if [[ "$branch" != stable ]]; then
    echo 'Only stable Spotify releases are supported' >&2
    exit 2
fi
if [[ -n "${SPOTIFY_METADATA_FILE:-}" ]]; then
    mkdir -p "$SPOTIFY_METADATA_DIR"
    cp "$SPOTIFY_METADATA_FILE" "$SPOTIFY_METADATA_DIR/spotify-client.stable.json"
    python3 - "$SPOTIFY_METADATA_DIR" <<'METADATA'
import json
import re
import sys
from pathlib import Path
folder = Path(sys.argv[1])
record = json.loads((folder / "spotify-client.stable.json").read_text())
version = record["RPMVersion"]
if record.get("Package") != "spotify-client" or record.get("Architecture") != "amd64" or not re.fullmatch(r"[A-Za-z0-9.+~]+", version):
    raise SystemExit("Invalid pinned Spotify package metadata")
(folder / "spotify-client.stable.Version").write_text(version)
METADATA
else
    parser_debian_control_file.py "$branch" spotify-client Version
fi
version=$(cat "$SPOTIFY_METADATA_DIR/spotify-client.$branch.Version")
download_spotify.sh "$branch" "$version"
build_SRPM.sh "$branch" "$version"
cp "$BUILD_DIR"/SRPMS/spotify-*.src.rpm "$output/"
printf 'Source RPM and scan logs: %s\n' "$output"
