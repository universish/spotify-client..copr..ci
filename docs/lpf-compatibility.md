# LPF packaging compatibility

The reference is the installed RPM Fusion LPF package and its
[spotify-client.spec.in](https://github.com/rpmfusion/lpf-spotify-client/blob/master/spotify-client.spec.in),
using spotify-make commit `29df615b140fc4a671ac729a7ad8633bf7233da8`.
Remote packaging instructions are reference material; they are not executed.

## Preserved application and runtime

The verified official amd64 DEB is raw-extracted without running Debian maintainer
scripts. After the mandatory malware scan and separate PUA report, its entire
`usr/share/spotify` tree is moved to `/usr/share/spotify-client`, as LPF does.
Apps, locale files, icons, bundled libraries, vendor desktop file and apt keys
remain intact. Apt keys are application data; no host trust store is changed.
The package and command names remain `spotify`.

All original regular files are hashed before generated launch helpers are added.
The RPM disables stripping and archive determinism rewriting; `%check` verifies
`.vendor-files.sha256` after buildroot processing. A changed vendor file stops
the build. The manifest is also retained with the scan reports. Official PNG
icons are copied to hicolor without removing the application originals.

The launcher places vendor libraries before optional codecs and inherited library
paths. It defaults LC_NUMERIC to an available en_US UTF-8 locale, with C.UTF-8 as
a fallback, and unsets LPF's two legacy desktop-session variables. Explicit user
locale settings remain effective. The spec requires dbus-launch and the locale
runtime through distribution-compatible dependencies.

The automatic NVIDIA profile uses the user's working desktop GL acceleration
settings on both Wayland and X11. Supported hybrid NVIDIA uses PRIME offload;
Intel/AMD/Nouveau do not receive NVIDIA variables. No accelerated profile forces
Wayland Ozone or a scale factor. Early failed NVIDIA GL initialization can retry
ANGLE, then software. User GPU flags take precedence. These changes preserve the
original UI resources but do not prove identical rendering on every GPU/display.

## Source version and cache

On 2026-10-28 the installed LPF package selects **1.3.4.258.gc60b10b0946a**.
That exact DEB appears in Spotify's
[testing index](https://repository-origin.spotify.com/dists/testing/non-free/binary-amd64/Packages),
whereas the [stable index](https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages)
advertises **1.2.95.453.g0eeebbed**. LPF's updater examines the official origin
pool rather than restricting itself to the stable index. This version difference
can explain UI differences; packaging layout alone does not change the vendor UI.

The automated release workflow retains the stable-only source policy. Matching
LPF's newer source selection requires a separate source-policy decision. The
local LPF reference build uses explicitly pinned metadata for comparison and
does not change the automated release channel.

`SPOTIFY_DEB_FILE=/path/to/cached.deb src/build_once.sh stable output` reuses a
cached LPF source only when its size and SHA256 match the selected metadata.
A mismatch stops before extraction; an existing cache never skips signature
updates or either scan. Without that variable the verified HTTPS download path
is used. `SPOTIFY_METADATA_FILE` can pin an already inspected official record
for a local reference build; it is not required for normal stable builds.

## Reference PUA result

The original LPF DEB has SHA256
`20f327441d11b202c82e65b69ec990ef631eb66605da15f41076c049acb718e4`.
Its `Apps/login.spa` and the installed LPF file are identical, SHA256
`4cbc5468d896037efa89080f2a504ab4f8d849ce1d1abd692ad07b026ca2470a`.

ClamAV 1.4.6 with main 63 / daily 28166 reports `PUA.Win.Trojan.Xored-1`
inside login.js. Static inspection of the signature shows a generic
`charcodeat(...)^` JavaScript XOR pattern. It is a possible false positive,
not evidence establishing malicious behavior or proving the whole app safe.
No application code was run or uploaded externally for this inspection.
[ClamAV documents](https://docs.clamav.net/faq/faq-pua.html) the higher false-positive
rate of PUA signatures and historical misleading malware-category labels.

Per the selected policy, PUA-only matches are retained as advisory evidence;
the mandatory malware scan remains blocking. Scanner errors, unexplained
detection exits, non-PUA findings and exhausted limits stop packaging in either
pass. The installed LPF package, user configuration and caches are not modified.

## Supplied reference specs and selected deployment model

The user supplied lpf-spotify-client.spec and spotify-client.spec.in on
2026-10-29. Both were inspected as reference data. The first declares the free
MIT bootstrap and LPF lifecycle macros; the second marks Spotify itself
non-redistributable and retains its original resources without stripping.

The selected deployment model now distributes only the independently authored
bootstrap helpers. It follows LPF's local-build architecture without requiring
LPF's Fedora-specific framework on every target distribution. It does not copy
the supplied specs into the distributed source package. The actual local target
is named spotify-client-local; the public bootstrap and command remain spotify.
