#!/usr/bin/env bash
# Submit the scanned SRPM, preserving the planned RPM release exactly.
set -euo pipefail
source_rpm=${1:?Usage: submit_copr.sh SOURCE_RPM OUTPUT_DIRECTORY}
output=${2:-output}
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
: "${COPR_CONFIG:?COPR_CONFIG repository secret is required for automatic submission}"
: "${SONICRADLE_VERSION:?Expected bootstrap version is required}"
: "${SONICRADLE_RELEASE:?Reserved packaging number is required}"
[[ $(rpm -qp --qf '%{NAME} %{VERSION}-%{RELEASE}' "$source_rpm") == "sonicradle $SONICRADLE_VERSION-$SONICRADLE_RELEASE" ]]
mkdir -p "$output"
work=$(mktemp -d "${TMPDIR:-/tmp}/sonicradle-copr.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
umask 077
printf '%s\n' "$COPR_CONFIG" > "$work/copr.conf"
# Resolve the current project configuration, never resurrect removed chroots.
python3 "$repo/tools/targets.py" --candidates --live > "$work/targets"
mapfile -t targets < "$work/targets"
[[ ${#targets[@]} -gt 0 ]] || { echo 'No enabled compatible COPR targets remain' >&2; exit 2; }
cp "$work/targets" "$output/copr-targets.txt"
args=()
for target in "${targets[@]}"; do args+=(--chroot "$target"); done
copr-cli --config "$work/copr.conf" build "${args[@]}" \
    universish/Spotify..Client "$source_rpm" 2>&1 | tee "$output/copr-submit.log"
