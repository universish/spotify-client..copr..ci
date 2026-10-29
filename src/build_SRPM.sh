#!/usr/bin/env bash
set -euo pipefail
branch=${1:?Branch required}
version=${2:?Version required}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PATH="$script_dir:$PATH"
: "${BUILD_DIR:?BUILD_DIR is required}"
: "${SOURCES_DIR:=$BUILD_DIR/SOURCES}"
: "${BUILTIN_FFMPEG:=false}"
export SCAN_REPORT_DIR=${SCAN_REPORT_DIR:-${TMPDIR:-/tmp}/spotify-scan-reports-${UID}}
if [[ ! "$version" =~ ^[A-Za-z0-9.+~]+$ || ! "$branch" =~ ^stable$ ]]; then
    echo 'Invalid version or branch' >&2
    exit 2
fi
source_file="${SPOTIFY_DOWNLOAD_DIR:-/tmp}/spotify-client_${version}_amd64.deb"
work=$(mktemp -d "${TMPDIR:-/tmp}/spotify-build.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$BUILD_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cd "$work"
root="spotify-client-$version"
# Refresh signatures first, then extract and scan before changing the payload.
scan_payload.sh --update
# Extract control scripts for scanning too; never execute Debian maintainer scripts.
dpkg-deb --raw-extract "$source_file" "$root"
[[ $(dpkg-deb --field "$source_file" Architecture) == amd64 ]]
[[ $(dpkg-deb --field "$source_file" Package) == spotify-client ]]
deb_version=$(dpkg-deb --field "$source_file" Version)
[[ ${deb_version#*:} == "$version" ]]
minimum_glibc=$(dpkg-deb --field "$source_file" Depends | python3 -c \
    'import re,sys; m=re.search(r"libc6\s*\(>=\s*([0-9.]+)\)", sys.stdin.read()); sys.exit("Missing upstream libc6 requirement") if m is None else print(m[1])')

if [[ "$BUILTIN_FFMPEG" =~ ^(1|true|True|y|Y)$ ]]; then
    ffmpeg_version=7.1.5
    curl --fail --location --retry 3 \
        "https://github.com/zicstardust/spotify-ffmpeg-libs/releases/download/v${ffmpeg_version}/spotify-ffmpeg-${ffmpeg_version}-libs-linux-x86_64.tar.gz" \
        --output "$work/ffmpeg.tar.gz"
    mkdir -p "$root/usr/share/spotify/ffmpeg"
    tar -xzf "$work/ffmpeg.tar.gz" -C "$root/usr/share/spotify/ffmpeg"
fi

# No RPM/SRPM is produced unless signatures update and the extracted tree scans clean.
scan_payload.sh --scan "$root" "$source_file"
rm -rf -- "$root/DEBIAN"
# Match LPF's layout: preserve the complete vendor application tree under spotify-client.
app_dir="$root/usr/share/spotify-client"
[[ ! -e "$app_dir" ]]
mv "$root/usr/share/spotify" "$app_dir"
[[ -x "$app_dir/spotify" ]]
# Pin every vendor file before adding the packager's own launch helpers.
(cd "$app_dir"; find . -type f -print0 | sort -z | xargs -0 -r sha256sum) > "$work/vendor-files.sha256"
install -m0644 "$work/vendor-files.sha256" "$app_dir/.vendor-files.sha256"
cp "$work/vendor-files.sha256" "$SCAN_REPORT_DIR/vendor-files.sha256"
generate_desktopentry.sh "$root/usr/share/applications" "$version"
# Keep the fork's icon names to preserve desktop integration.
for size in 8 16 22 24 32 36 44 48 64 72 96 128 144 150 192 256 310 512 1024; do
    icon="$app_dir/icons/spotify-linux-$size.png"
    if [[ -f "$icon" ]]; then
        install -Dm0644 "$icon" "$root/usr/share/icons/hicolor/${size}x${size}/apps/spotify-client.png"
    fi
done
generate_man.sh "$root/usr/share/man/man1"
generate_appdata.sh "$root/usr/share/appdata" "$version"
# Debian's launcher is a symlink; remove it before writing the wrapper.
rm -f -- "$root/usr/bin/spotify"
generate_bin.sh "$root/usr/bin" "$BUILTIN_FFMPEG"
generate_generate_flags_file.sh "$app_dir"
generate_generate_envs_file.sh "$app_dir"
install -m0755 "$script_dir/spotify-gpu.sh" "$app_dir/spotify-gpu.sh"
# Only the /usr payload belongs in the resulting RPM.
mkdir package
mv "$root/usr" package/
rm -rf -- "$root"
mv package "$root"
tar -czf "$SOURCES_DIR/spotify-client-$version.tar.gz" "$root"
generate_spec.sh "$BUILD_DIR/SPECS/spotify.spec" "$version" "$minimum_glibc"
rpmbuild -bs --define "_topdir $BUILD_DIR" --define 'dist %{nil}' --define '_source_payload w3.gzdio' "$BUILD_DIR/SPECS/spotify.spec"
