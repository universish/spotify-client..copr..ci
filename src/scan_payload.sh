#!/usr/bin/env bash
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
echo 'Scanning DEB, extracted files, embedded archives and ELF executables for malware and potentially unwanted applications...'
# Spotify's main ELF exceeds ClamAV's default file size limit.
# Treat exhausted limits as detections instead of silently accepting skipped data.
clamscan --database="$database" --recursive --infected \
    --scan-elf=yes --scan-archive=yes --heuristic-alerts=yes --detect-pua=yes \
    --alert-encrypted=yes --alert-broken=yes \
    --max-filesize=2000M --max-scansize=2000M --alert-exceeds-max=yes \
    --follow-dir-symlinks=0 --follow-file-symlinks=0 \
    --log="$report_dir/clamscan.log" "${targets[@]}"
