#!/usr/bin/env bash
set -euo pipefail
output=${1:?Usage: generate_bin.sh OUTPUT_DIRECTORY BUILTIN_FFMPEG}
mkdir -p "$output"
cat > "$output/spotify" <<'LAUNCHER'
#!/bin/bash
set -euo pipefail
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/spotify"
data_dir=/usr/share/spotify-client
# SPOTIFY_DATA_DIR is useful for testing this launcher with a stub executable.
data_dir=${SPOTIFY_DATA_DIR:-$data_dir}

# LPF puts the vendor's own libraries first; optional codecs remain secondary.
library_path=$data_dir
if [[ -d "$data_dir/ffmpeg" ]]; then
    library_path+=":$data_dir/ffmpeg"
fi
export LD_LIBRARY_PATH="$library_path${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# LPF's numeric locale/session compatibility fixes, without deleting user caches.
if [[ -z ${LC_NUMERIC+x} ]]; then
    numeric_locale=C.UTF-8
    while IFS= read -r available_locale; do
        if [[ "${available_locale,,}" == en_us.utf8 || "${available_locale,,}" == en_us.utf-8 ]]; then
            numeric_locale=$available_locale
            break
        fi
    done < <(locale -a 2>/dev/null || true)
    export LC_NUMERIC=$numeric_locale
fi
unset DESKTOP_SESSION GNOME_DESKTOP_SESSION_ID

debug=${SPOTIFY_DEBUG:-0}
gpu_mode=${SPOTIFY_GPU_MODE:-auto}
gpu_cli=0
log_file=
while (($#)); do
    case "$1" in
        --debug) debug=1; shift ;;
        --debug-log=*) debug=1; log_file=${1#*=}; shift ;;
        --safe-mode) gpu_mode=software; gpu_cli=1; shift ;;
        --gpu-mode=*) gpu_mode=${1#*=}; gpu_cli=1; shift ;;
        --help)
            printf '%s\n' 'Usage: spotify [--debug] [--debug-log=FILE] [--safe-mode] [--gpu-mode=auto|native|mesa|nvidia|nvidia-desktop|software] [Spotify options/URI]' \
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
    if [[ "$line" == SPOTIFY_GPU_MODE=* && "$gpu_cli" == 0 && -z ${SPOTIFY_GPU_MODE+x} ]]; then gpu_mode=${line#*=}; fi
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
if [[ -r "$data_dir/spotify-gpu.sh" ]]; then
    exec /bin/bash "$data_dir/spotify-gpu.sh" "$data_dir/spotify" "$gpu_mode" "$debug" \
        "${#envs[@]}" "${envs[@]}" "${#flags[@]}" "${flags[@]}" "$@"
fi
exec env "${envs[@]}" "$data_dir/spotify" "${flags[@]}" "$@"
LAUNCHER
chmod 0755 "$output/spotify"
