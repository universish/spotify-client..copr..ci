#!/usr/bin/env bash
set -euo pipefail
output=${1:?Usage: generate_bin.sh OUTPUT_DIRECTORY BUILTIN_FFMPEG}
mkdir -p "$output"
cat > "$output/spotify" <<'LAUNCHER'
#!/bin/bash
set -euo pipefail
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/spotify"
data_dir=/usr/share/spotify
# SPOTIFY_DATA_DIR is useful for testing this launcher with a stub executable.
data_dir=${SPOTIFY_DATA_DIR:-$data_dir}

if [[ -d "$data_dir/ffmpeg" ]]; then
    export LD_LIBRARY_PATH="$data_dir/ffmpeg${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

debug=${SPOTIFY_DEBUG:-0}
log_file=
while (($#)); do
    case "$1" in
        --debug) debug=1; shift ;;
        --debug-log=*) debug=1; log_file=${1#*=}; shift ;;
        --help)
            printf '%s\n' 'Usage: spotify [--debug] [--debug-log=FILE] [Spotify options/URI]' \
                'SPOTIFY_DEBUG=1 enables terminal diagnostics.' \
                'Configuration: ${XDG_CONFIG_HOME:-$HOME/.config}/spotify/'
            exit 0 ;;
        --) shift; break ;;
        *) break ;;
    esac
done

mkdir -p "$config_dir"
[[ -f "$config_dir/spotify.env" ]] || "$data_dir/generate_envs_file.sh"
[[ -f "$config_dir/spotify-flags.conf" ]] || "$data_dir/generate_flags_file.sh"
flags=()
envs=()
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    flags+=("$line")
done < "$config_dir/spotify-flags.conf"
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    if [[ ! "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        printf 'spotify: invalid environment assignment in %s\n' "$config_dir/spotify.env" >&2
        exit 2
    fi
    envs+=("$line")
done < "$config_dir/spotify.env"

if [[ "$debug" == 1 || "$debug" == true ]]; then
    flags+=(--show-console --debug-level=4 --enable-logging=stderr --v=1)
    printf 'spotify: diagnostics enabled; configuration: %s\n' "$config_dir" >&2
fi
if [[ -n "$log_file" ]]; then
    umask 077
    mkdir -p "$(dirname "$log_file")"
    touch "$log_file"
    chmod 600 "$log_file"
    exec > >(tee -a "$log_file") 2> >(tee -a "$log_file" >&2)
fi
if [[ ! -x "$data_dir/spotify" ]]; then
    printf 'spotify: executable not found: %s/spotify\n' "$data_dir" >&2
    exit 127
fi
exec env "${envs[@]}" "$data_dir/spotify" "${flags[@]}" "$@"
LAUNCHER
chmod 0755 "$output/spotify"
