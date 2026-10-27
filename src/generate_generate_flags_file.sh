#!/usr/bin/env bash
set -euo pipefail
output=${1:?Output directory required}
mkdir -p "$output"
cat > "$output/generate_flags_file.sh" <<'SCRIPT'
#!/bin/bash
set -euo pipefail
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/spotify"
mkdir -p "$config_dir"
umask 077
# noclobber preserves a configuration another launcher may have just created.
if [[ ! -e "$config_dir/spotify-flags.conf" ]]; then
    (set -o noclobber; cat > "$config_dir/spotify-flags.conf" <<'CONFIG'
# One argument per line. Lines beginning with # are comments.
#--ozone-platform=x11
#--disable-gpu
#--force-device-scale-factor=1.5
# Terminal diagnostics: spotify --debug
CONFIG
    ) || [[ -f "$config_dir/spotify-flags.conf" ]]
fi
SCRIPT
chmod 0755 "$output/generate_flags_file.sh"
