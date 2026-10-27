# Adaptive GPU launcher and RPM integration

`/usr/bin/spotify` reads the user's existing environment/flags files and delegates
to `/usr/share/spotify/spotify-gpu.sh`. Selection happens in the user's session
on every launch. Root installation scripts do not probe a display or write a
hardware-specific launcher, and no system-wide GPU configuration is changed.

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
| NVIDIA proprietary, Wayland | ANGLE OpenGL plus Wayland Ozone |
| Supported hybrid NVIDIA | PRIME render offload and NVIDIA GLX vendor selection |
| Legacy hybrid NVIDIA driver | Preserve the Mesa/default route without unsupported PRIME offload |
| Software GL, explicit safe mode | Disable GPU acceleration; clear PRIME selections |
| Unknown hardware | Keep the application's native defaults |

The NVIDIA profile requests `VaapiVideoDecodeLinuxGL`,
`VaapiVideoEncoderLinuxGL`, zero-copy, overlays and the GPU blocklist override.
Mesa requests the shared acceleration features without NVIDIA-specific settings.
Actual video acceleration depends on the driver, codecs and Spotify/CEF build;
requesting these features does not install a VA-API driver or prove support.

Explicit user `--use-gl`, `--use-angle` or GPU-disable flags take precedence over
automatic selection. `SPOTIFY_GPU_MODE` can be set in the process environment or
spotify.env; a wrapper `--gpu-mode=` option has higher priority.

```sh
spotify --debug
spotify --safe-mode
spotify --gpu-mode=native
spotify --gpu-mode=nvidia-desktop --debug
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

## Spec integration

The generated spec includes this equivalent placement/validation contract:

```spec
BuildRequires: desktop-file-utils
Requires: desktop-file-utils
Requires: hicolor-icon-theme
Requires: coreutils

%install
# The prepared source tarball already includes the generated wrapper and helper.
cp -ar usr %{buildroot}/
chmod 0755 %{buildroot}%{_bindir}/spotify
chmod 0755 %{buildroot}%{_datadir}/spotify/spotify-gpu.sh
desktop-file-validate %{buildroot}%{_datadir}/applications/spotify.desktop

%files
%{_bindir}/spotify
%{_datadir}/spotify/
%{_datadir}/applications/spotify.desktop
%{_datadir}/icons/hicolor/*/apps/spotify-client.*
```

On Fedora, desktop-file-utils owns transfiletriggerin/postun for
`/usr/share/applications`, invoking update-desktop-database. The hicolor/GTK
packages supply the matching icon-cache transaction triggers. The installed
Fedora package scripts were checked with `rpm -q --filetriggers`. These standard
triggers cover install, upgrade and removal; duplicating them in Spotify's %post
is unnecessary. The package validates its desktop file during build and never
runs an unconditional cache command or GPU probe at install time.

Implementation: `src/generate_bin.sh`, `src/spotify-gpu.sh`, `src/generate_spec.sh`.
The tests simulate the driver/session combinations and initialization failures;
actual rendering/playback on every physical GPU remains a hardware QA task.

NVIDIA PRIME reference:
https://download.nvidia.com/XFree86/Linux-x86_64/555.58/README/primerenderoffload.html
Chromium GL backend reference:
https://chromium.googlesource.com/chromium/src/+/refs/tags/124.0.6367.208/ui/gl/gl_implementation.cc
