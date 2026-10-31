# LPF packaging compatibility

The reference is the installed RPM Fusion LPF package and its
[spotify-client.spec.in](https://github.com/rpmfusion/lpf-spotify-client/blob/master/spotify-client.spec.in),
using spotify-make commit `29df615b140fc4a671ac729a7ad8633bf7233da8`.
Remote packaging instructions are reference material; they are not executed.

## Preserved application and runtime

The verified official amd64 DEB is raw-extracted without running Debian maintainer
scripts. Mandatory malware scanning and the separate PUA report now run in CI.
The user host checks the same source hash and moves the complete `usr/share/spotify`
tree to `/usr/share/spot..fly..light-client`, following LPF's resource-preservation approach.
Apps, locale files, icons, bundled libraries, vendor desktop file and apt keys
remain intact. Apt keys are application data; no host trust store is changed.
The current community RPM package is `spot-fly-light` and its command is
`spot..fly..light`; the local target
is `spot-fly-light-client-local`. The application bytes remain Spotify's.

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

The current bootstrap includes separate official stable and testing metadata.
Stable remains the default; `spot..fly..light --setup -unstable` or
`spot..fly..light --update -unstable` explicitly selects testing. Both channels replace
the same local package. A pool filename is not accepted as proof of channel
membership. RPM Fusion references are checked last and cannot override the
official DEB channel or hash.

Current source discovery uses only the three official indexes listed in
[the release flow](release-flow.md#schedule-and-source-selection). The configured
unofficial mirror is only a byte-download fallback for the pinned official
filename and must match its exact size/SHA256; it does not determine a channel
or version. Local setup checks its private verified DEB cache before network
fallback and does not run ClamAV.

The following describes the legacy local comparison script, not the current
user installer: `SPOTIFY_DEB_FILE=/path/to/cached.deb src/build_once.sh stable output` reuses a
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
is named spot-fly-light-client-local; the public bootstrap is spot-fly-light
and its command is spot..fly..light.


## Actual LPF framework versus this standalone builder

The underlying framework is [leamas/lpf](https://github.com/leamas/lpf), distinct
from the RPM Fusion Spotify bootstrap referenced above. Its complete README was
reviewed and concrete approval/version/retry gaps corrected. This project still
uses its own standalone builder, as explicitly chosen by the owner. It does not
use LPF's dedicated pkg-build account, lifecycle macros or notification daemon.
See [the comparison and regression evidence](lpf-framework-audit.md) for the
implemented behavior and the remaining architectural differences.

## spotify-make master/devel review — 2026-10-30

Both [master](https://github.com/sergiomb2/spotify-make/tree/master) and
[devel](https://github.com/sergiomb2/spotify-make/tree/devel) were reviewed as
historical packaging references. Useful ideas include DESTDIR staging, separate
launcher/application paths and preservation of vendor resources; the independent
builder already uses equivalent concepts. Their old HTTP pool scraping,
unchecked download path, Qt-era libraries and compatibility-library symlinks
are not copied into the current workflow. They would not establish a verified
current stable/testing source or appropriate modern runtime dependencies.
