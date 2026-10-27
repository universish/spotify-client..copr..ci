#!/usr/bin/env bash
set -euo pipefail
srpm=${1:?Usage: tools/build_target.sh SRPM CHROOT OUTPUT_DIRECTORY}
chroot=${2:?Chroot required}
output=${3:?Output directory required}
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! python3 "$repo/tools/targets.py" --candidates | grep -Fxq -- "$chroot"; then
    echo "Unsupported or incompatible chroot: $chroot (see packaging/targets.json)" >&2
    exit 2
fi
[[ -f "/etc/mock/$chroot.cfg" ]] || { echo "Mock configuration not installed: $chroot" >&2; exit 2; }
mkdir -p "$output"
mock -r "$chroot" --resultdir "$(realpath "$output")" --rebuild "$(realpath "$srpm")"
