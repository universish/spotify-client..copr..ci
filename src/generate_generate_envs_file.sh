#!/usr/bin/env bash
set -euo pipefail
output=${1:?Output directory required}
mkdir -p "$output"
cat > "$output/generate_envs_file.sh" <<'SCRIPT'
#!/bin/bash
set -euo pipefail
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/spotify"
mkdir -p "$config_dir"
umask 077
# noclobber preserves a configuration another launcher may have just created.
if [[ ! -e "$config_dir/spotify.env" ]]; then
    (set -o noclobber; cat > "$config_dir/spotify.env" <<'CONFIG'
# One KEY=value assignment per line; shell code is never evaluated.
#WAYLAND_DISPLAY=
#SPOTIFY_GPU_MODE=auto
CONFIG
    ) || [[ -f "$config_dir/spotify.env" ]]
fi
SCRIPT
chmod 0755 "$output/generate_envs_file.sh"
