#!/bin/bash
# Unprivileged runtime GPU selection; no hardware state is written into /usr.
set -euo pipefail
binary=${1:?Executable required}
requested=${2:?GPU mode required}
debug=${3:-0}
shift 3
count=${1:?Environment count required}; shift
[[ "$count" =~ ^[0-9]+$ && $# -ge $count ]] || exit 2
configured_env=("${@:1:count}"); shift "$count"
count=${1:?Flag count required}; shift
[[ "$count" =~ ^[0-9]+$ && $# -ge $count ]] || exit 2
configured_flags=("${@:1:count}"); shift "$count"
app_args=("$@")
case "$requested" in auto|native|mesa|nvidia|nvidia-desktop|software) ;; *) echo 'spotify: invalid GPU mode' >&2; exit 2 ;; esac

sysfs=${SPOTIFY_SYSFS_ROOT:-/sys}
session=${XDG_SESSION_TYPE:-}
[[ "$session" == wayland || "$session" == x11 ]] || session=$([[ -n ${WAYLAND_DISPLAY:-} ]] && echo wayland || echo x11)
nvidia=0
mesa=0
driver_version=unknown
for device in "$sysfs"/class/drm/card[0-9]*/device; do
    [[ -r "$device/vendor" && -L "$device/driver" ]] || continue
    read -r vendor < "$device/vendor" || continue
    driver=$(readlink "$device/driver")
    driver=${driver##*/}
    case "${vendor,,}:$driver" in
        0x10de:nvidia) nvidia=1 ;;
        0x8086:i915|0x8086:xe|0x1002:amdgpu|0x1002:radeon|0x10de:nouveau) mesa=1 ;;
    esac
done
if [[ -r "$sysfs/module/nvidia/version" ]]; then
    read -r driver_version < "$sysfs/module/nvidia/version" || driver_version=unknown
fi
driver_major=${driver_version%%.*}
[[ "$driver_major" =~ ^[0-9]+$ ]] || driver_major=0
hybrid=0
[[ "$nvidia" == 1 && "$mesa" == 1 ]] && hybrid=1

# A bounded optional probe detects actual GLX rendering, including software Mesa.
renderer=
if [[ "$requested" == auto && -n ${DISPLAY:-} ]] && command -v glxinfo >/dev/null 2>&1; then
    renderer=$(timeout 2s glxinfo -B 2>/dev/null || true)
fi
mode=$requested
if [[ "$mode" == auto ]]; then
    if [[ "${renderer,,}" == *llvmpipe* || "${renderer,,}" == *softpipe* ]]; then
        mode=software
    elif [[ "$nvidia" == 1 && ( "$hybrid" == 0 || "$driver_major" -ge 435 ) ]]; then
        mode=nvidia
        [[ "$session" != x11 ]] || mode=nvidia-desktop
    elif [[ "$mesa" == 1 ]]; then
        mode=mesa
    else
        mode=native
    fi
fi
# A driver merely installed/loaded on an Intel/AMD machine is not an active NVIDIA GPU.
if [[ "$mode" == nvidia* && "$nvidia" == 0 ]]; then mode=native; fi
manual_gpu=0
for flag in "${configured_flags[@]}" "${app_args[@]}"; do
    case "$flag" in --use-gl=*|--use-angle=*|--disable-gpu|--disable-gpu-compositing) manual_gpu=1 ;; esac
done
if [[ "$manual_gpu" == 1 && "$requested" == auto ]]; then mode=native; fi

work=$(mktemp -d "${TMPDIR:-/tmp}/spotify-gpu.XXXXXXXX")
child=
logger=
interrupted=0
cleanup() {
    [[ -z "$child" ]] || kill -TERM "$child" 2>/dev/null || true
    [[ -z "$logger" ]] || kill -TERM "$logger" 2>/dev/null || true
    rm -rf -- "$work"
}
forward_signal() {
    interrupted=$1
    [[ -z "$child" ]] || kill -"$2" "$child" 2>/dev/null || true
}
trap cleanup EXIT
trap 'forward_signal 130 INT' INT
trap 'forward_signal 143 TERM' TERM
mkfifo "$work/stderr"

gpu_error() {
    local line
    local pattern='display[.]cpp:1128|egl_not_initialized|requested gl implementation|failed to (create|initialize).*(gl|gpu|egl)|gpu process.*(crash|unusable)|angle.*(initializ.*fail|context.*fail)'
    while IFS= read -r line; do
        [[ "${line,,}" =~ $pattern ]] && return 0
    done < "$work/startup.log"
    return 1
}

while :; do
    automatic_flags=()
    launch_env=()
    automatic_env=()
    clear_env=()
    prime_requested=${__NV_PRIME_RENDER_OFFLOAD:-}
    for assignment in "${configured_env[@]}"; do
        # Software fallback must not inherit PRIME selections from spotify.env either.
        if [[ "$mode" == software && "$assignment" =~ ^(__NV_PRIME_RENDER_OFFLOAD|__GLX_VENDOR_LIBRARY_NAME|__VK_LAYER_NV_optimus)= ]]; then continue; fi
        launch_env+=("$assignment")
        [[ "$assignment" != __NV_PRIME_RENDER_OFFLOAD=* ]] || prime_requested=${assignment#*=}
    done
    case "$mode" in
        nvidia|nvidia-desktop|mesa)
            if [[ "$mode" == nvidia-desktop ]]; then
                automatic_flags+=(--use-gl=desktop)
            else
                automatic_flags+=(--use-gl=angle --use-angle=gl)
            fi
            automatic_flags+=(--enable-features=VaapiVideoDecodeLinuxGL,VaapiVideoEncoderLinuxGL --enable-zero-copy --enable-hardware-overlays)
            if [[ "$mode" == nvidia* ]]; then
                automatic_flags+=(--ignore-gpu-blocklist)
                if [[ "$hybrid" == 1 && "$driver_major" -ge 435 && "$prime_requested" != 0 ]]; then
                    automatic_env+=(__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia)
                fi
            fi
            [[ "$session" != wayland ]] || automatic_flags+=(--ozone-platform=wayland)
            ;;
        software)
            clear_env=(-u __NV_PRIME_RENDER_OFFLOAD -u __GLX_VENDOR_LIBRARY_NAME -u __VK_LAYER_NV_optimus)
            automatic_flags+=(--disable-gpu --disable-gpu-compositing)
            if [[ -n ${DISPLAY:-} ]]; then
                automatic_flags+=(--ozone-platform=x11)
            elif [[ "$session" == wayland ]]; then
                automatic_flags+=(--ozone-platform=wayland)
            fi
            ;;
    esac
    if [[ "$debug" == 1 || "$debug" == true ]]; then
        printf 'spotify: gpu-mode=%s session=%s nvidia-driver=%s hybrid=%s\n' "$mode" "$session" "$driver_version" "$hybrid" >&2
    fi
    : > "$work/startup.log"
    tee "$work/startup.log" < "$work/stderr" >&2 &
    logger=$!
    started=$SECONDS
    # Automatic arguments precede user arguments. Safe mode's disabling switches go last.
    if [[ "$mode" == software ]]; then
        safe_inputs=()
        for flag in "${configured_flags[@]}" "${app_args[@]}"; do
            case "$flag" in --use-gl=*|--use-angle=*|--enable-zero-copy|--enable-hardware-overlays|--ignore-gpu-blocklist) continue ;; esac
            safe_inputs+=("$flag")
        done
        env "${clear_env[@]}" "${launch_env[@]}" "$binary" "${safe_inputs[@]}" "${automatic_flags[@]}" 2> "$work/stderr" &
    else
        env "${automatic_env[@]}" "${launch_env[@]}" "$binary" "${automatic_flags[@]}" "${configured_flags[@]}" "${app_args[@]}" 2> "$work/stderr" &
    fi
    child=$!
    if wait "$child"; then status=0; else status=$?; fi
    if [[ "$interrupted" != 0 ]]; then
        wait "$child" 2>/dev/null || true
        status=$interrupted
    fi
    child=
    wait "$logger" || true
    logger=
    [[ "$interrupted" == 0 ]] || exit "$status"
    # Nonfatal warnings, user termination and late unrelated crashes never trigger a restart.
    if [[ "$requested" == auto && "$manual_gpu" == 0 && "$mode" != software && "$status" != 0 && "$status" != 130 && "$status" != 143 && $((SECONDS-started)) -le 20 ]] && gpu_error; then
        if [[ "$mode" == nvidia-desktop ]]; then mode=nvidia; else mode=software; fi
        printf 'spotify: early graphics initialization failure; retrying with %s mode\n' "$mode" >&2
        continue
    fi
    exit "$status"
done
