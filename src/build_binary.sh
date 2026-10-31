#!/usr/bin/env bash
# Rebuild the prepared, scanned source as a distribution-neutral x86_64 RPM.
set -euo pipefail
source_rpm=${1:?Usage: build_binary.sh SOURCE_RPM OUTPUT_DIRECTORY}
output=${2:-./output}
source_rpm=$(realpath "$source_rpm")
mkdir -p "$output"
output=$(realpath "$output")
work=$(mktemp -d "${TMPDIR:-/tmp}/spot..fly..light-rpm.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/tmp"
for command in bash tar gzip desktop-file-validate; do command -v "$command" >/dev/null; done
build_options=()
# Debian's package manager does not register its tools in the RPM database.
# This skips build-dependency lookup only; automatic runtime ELF requirements stay enabled.
if [[ -f /etc/debian_version ]]; then build_options+=(--nodeps); fi
rpmbuild --rebuild --target x86_64 "${build_options[@]}" \
    --define "_topdir $work" --define "_tmppath $work/tmp" \
    --define 'dist %{nil}' --define '_binary_payload w3.zstdio' \
    "$source_rpm" 2>&1 | tee "$output/rpm-build.log"
cp "$work"/RPMS/x86_64/spot-fly-light-*.x86_64.rpm "$output/"
