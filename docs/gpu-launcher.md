The payload-free bootstrap uses `bootstrap/spot..fly..light.py` and the same GPU helper
installed under `/usr/share/spot..fly..light-bootstrap/spot..fly..light-gpu.sh`. The bootstrap generates its local target separately. GPU selection and bounded
fallback behavior are shared with the historical reference implementation.

# Adaptive GPU launcher and RPM integration

`/usr/bin/spot..fly..light` reads `~/.config/spot..fly..light/environment.conf` and
`~/.config/spot..fly..light/flags.conf` and delegates
to `/usr/share/spot..fly..light-bootstrap/spot..fly..light-gpu.sh`. Selection happens in the user's session
on every launch. Root installation scripts do not probe a display or write a
hardware-specific launcher, and no system-wide GPU configuration is changed.
If either current configuration file is absent, its matching file in this
project's previous configuration directory is read as a migration fallback.
The old files are not moved or deleted, and installation consent is not inherited.

## Detection and profiles

DRM card vendor IDs and bound driver symlinks under `/sys/class/drm` distinguish
Intel i915/xe, AMD amdgpu/radeon, NVIDIA proprietary and Nouveau. A loaded module
alone does not count as an active NVIDIA graphics device. NVIDIA's module version
is read when available; PRIME offload on hybrid systems requires a known driver
version >= 435. An optional `glxinfo -B` probe is bounded to two seconds. Mesa
llvmpipe/softpipe rendering selects software mode. The profile uses
`XDG_SESSION_TYPE`, with WAYLAND_DISPLAY as a fallback.

| Situation | Automatic policy |
| --- | --- |
| Intel/AMD/Nouveau | Mesa ANGLE/OpenGL flags; no NVIDIA environment injection |
| NVIDIA proprietary, X11 | Desktop GL flags; modern driver compatibility profile |
| NVIDIA proprietary, Wayland | Desktop GL matching the working LPF setup; Spotify selects its display backend |
| Supported hybrid NVIDIA | PRIME render offload and NVIDIA GLX vendor selection |
| Legacy hybrid NVIDIA driver | Preserve the Mesa/default route without unsupported PRIME offload |
| Software GL, explicit safe mode | Disable GPU acceleration; clear PRIME selections |
| Unknown hardware | Keep the application's native defaults |

The NVIDIA profile requests `VaapiVideoDecodeLinuxGL`,
`VaapiVideoEncoderLinuxGL`, zero-copy, overlays and the GPU blocklist override.
Mesa requests the shared acceleration features without NVIDIA-specific settings.
Accelerated profiles do not force Ozone or a device scale factor; Spotify retains
its native backend and DPI selection. Existing user flags can override that choice.
Actual video acceleration depends on the driver, codecs and Spotify/CEF build;
requesting these features does not install a VA-API driver or prove support.

Explicit user `--use-gl`, `--use-angle` or GPU-disable flags take precedence over
automatic selection. `SPOT_FLY_LIGHT_GPU_MODE` can be set in the process environment or
`~/.config/spot..fly..light/environment.conf`; a wrapper `--gpu-mode=` option has higher priority.

```sh
spot..fly..light --debug
spot..fly..light --safe-mode
spot..fly..light --gpu-mode=native
spot..fly..light --gpu-mode=nvidia-desktop --debug
```

Safe/native modes avoid the optional GL probe. Safe mode also removes inherited
PRIME choices and prefers XWayland when DISPLAY is available. Each launch uses a
private temporary stderr log, streams diagnostics to the terminal, and removes
its temporary files at exit. A requested `--debug-log=FILE` remains available for
persistent diagnostics with permissions 0600.

## Bounded fallback

Only an automatic profile that exits unsuccessfully within 20 seconds with a
recognized GL/ANGLE/EGL initialization failure is retried. Unsupported NVIDIA
desktop GL first retries ANGLE/OpenGL, then software rendering if that fails.
Other automatic profiles fall back directly to software. A software failure
ends the launcher, preserving the native exit code. There is no restart loop.
A warning followed by exit 0, explicit user GPU settings, SIGINT/SIGTERM or a late
unrelated failure does not cause a restart. Signals are forwarded to the app.
Persistent warnings in a still-running app can be handled with `--safe-mode`.

## RPM integration

The public bootstrap installs `/usr/bin/spot..fly..light` and the independent GPU
helper under `/usr/share/spot..fly..light-bootstrap/spot..fly..light-gpu.sh`. The locally
built target preserves the original executable at
`/usr/share/spot..fly..light-client/spotify`; that vendor filename does not become
an additional public terminal command. `bootstrap/spot..fly..light.py` generates the
local target spec and desktop integration.

The target requires desktop-file-utils and hicolor-icon-theme. Its desktop file
is validated at build time. Fedora's standard desktop/icon transaction triggers
handle install, upgrade and removal. No unconditional GPU probe runs in a root
installation script, and no hardware-specific system configuration is written.

The legacy `src/generate_bin.sh`/`src/generate_spec.sh` code is kept only for local
historical comparison; it is not the public COPR source generator. Launcher
tests simulate driver/session combinations and initialization failures. Actual
rendering/playback on every physical GPU remains a hardware QA task.

NVIDIA PRIME reference:
https://download.nvidia.com/XFree86/Linux-x86_64/555.58/README/primerenderoffload.html
Chromium GL backend reference:
https://chromium.googlesource.com/chromium/src/+/refs/tags/124.0.6367.208/ui/gl/gl_implementation.cc
