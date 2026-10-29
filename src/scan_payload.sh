#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
# Update an isolated signature database, then scan the complete extracted payload.
set -euo pipefail

mode=both
case ${1:-} in
    --update) mode=update; targets=() ;;
    --scan) mode=scan; shift; targets=("$@"); [[ ${#targets[@]} -gt 0 ]] ;;
    *) targets=("${1:?Usage: scan_payload.sh [--update | --scan PATH... | PATH]}") ;;
esac
database=${CLAMAV_DATABASE_DIR:-${TMPDIR:-/tmp}/spotify-clamav-${UID}}
report_dir=${SCAN_REPORT_DIR:-${TMPDIR:-/tmp}/spotify-scan-reports-${UID}}
mkdir -p "$database" "$report_dir"
database=$(realpath "$database")
report_dir=$(realpath "$report_dir")
config=$(mktemp)
trap 'rm -f "$config"' EXIT
cat > "$config" <<CONFIG
DatabaseDirectory $database
DatabaseOwner $(id -un)
DatabaseMirror database.clamav.net
DNSDatabaseInfo current.cvd.clamav.net
ConnectTimeout 30
ReceiveTimeout 300
CONFIG

if [[ "$mode" != scan ]]; then
    echo 'Updating ClamAV signatures (an update failure stops packaging)...'
    freshclam --config-file="$config" 2>&1 | tee "$report_dir/freshclam.log"
fi
[[ "$mode" != update ]] || exit 0
echo 'Scanning DEB, extracted files, embedded archives and ELF executables for malware...'
# Spotify's main ELF exceeds ClamAV's default file size limit.
# Treat exhausted limits as detections instead of silently accepting skipped data.
scan_options=(--database="$database" --recursive --infected
    --scan-elf=yes --scan-archive=yes --heuristic-alerts=yes
    --alert-encrypted=yes --alert-broken=yes
    --max-filesize=2000M --max-scansize=2000M --alert-exceeds-max=yes
    --follow-dir-symlinks=0 --follow-file-symlinks=0)
# Do not leave an earlier attempt's advisory result beside a failed malware pass.
: > "$report_dir/clamscan-pua.log"
printf '%s\n' '{"disposition":"not_run","detections":[]}' > "$report_dir/pua-status.json"
: > "$report_dir/clamscan.log"
clamscan "${scan_options[@]}" --detect-pua=no --log="$report_dir/clamscan.log" "${targets[@]}"

# PUA signatures are less curated and may match legitimate JavaScript obfuscation.
# Keep this report separate; only PUA detections may be advisory. Every scanner
# error, malware/heuristic detection and exhausted scan limit still stops the build.
echo 'Scanning separately for potentially unwanted applications (PUA report)...'
: > "$report_dir/clamscan-pua.log"
if clamscan "${scan_options[@]}" --detect-pua=yes --log="$report_dir/clamscan-pua.log" "${targets[@]}"; then
    pua_status=0
else
    pua_status=$?
fi
python3 - "$report_dir" "$pua_status" <<'PUA_REPORT'
import json
import re
import sys
from pathlib import Path

directory, status = Path(sys.argv[1]), int(sys.argv[2])
lines = (directory / "clamscan-pua.log").read_text(errors="replace").splitlines()
detections = [line for line in lines if line.endswith(" FOUND")]
pua_only = bool(detections) and all(re.search(r": PUA[.][^\s]+ FOUND$", line) for line in detections)
allowed = (status == 0 and not detections) or (status == 1 and pua_only)
disposition = ("advisory" if detections else "clean") if allowed else "blocked"
(directory / "pua-status.json").write_text(json.dumps({
    "scanner_exit_code": status, "disposition": disposition, "detections": detections
}, indent=2) + "\n")
if not allowed:
    raise SystemExit("PUA pass failed or reported a non-PUA detection; stopping packaging")
if detections:
    print("PUA warning recorded separately; mandatory malware scan passed. See clamscan-pua.log.")
PUA_REPORT
