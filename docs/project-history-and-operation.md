# Spot..Light: origin, purpose and operation

Spot..Light is an independent community installer and launcher for the official
Spotify Linux desktop application. It is maintained in
[universish/spotify-client..copr..ci](https://github.com/universish/spotify-client..copr..ci),
a fork of [zicstardust/spotify-rpm-packager](https://github.com/zicstardust/spotify-rpm-packager).
The historical repository and COPR identifiers have been retained for continuity;
the new public RPM package is `spot-fly-light` and its terminal command is
`spot..fly..light`. RPM names cannot contain `..`, so the package uses hyphens.

This project is not affiliated with, approved by or supported by Spotify. COPR
hosting does not make it an official Fedora or Red Hat package. The choice of a
new project name is not a claim of completed trademark clearance.

The next installer update adds an English-only notice, verified migration,
progress/timing output, private source caching, date-based installer versioning
and a desktop channel chooser. It also enables GitHub Releases containing only
free installer assets. These source changes await
verified publication; the completed delivery below is historical evidence.

The Spot..Light bootstrap `spot-fly-light-1.2.95.453.g0eeebbed-8` was delivered
on 31 October 2026 through [COPR build 11233588](https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/build/11233588/),
with all 17 targets successful. [Actions run 41151337784](https://github.com/universish/spotify-client..copr..ci/actions/runs/41151337784)
used [source commit 1c2f582](https://github.com/universish/spotify-client..copr..ci/commit/1c2f582ce63ebd17a4f6ef6e7abf525a84b2b2fd).
Its 112 tests passed; both official DEBs passed the normal malware scan, with
PUA-only findings reported separately. The Fedora 44 bootstrap RPM's signature
and digests were verified against the trusted COPR key. Its catalog selects
stable `1.2.95.453.g0eeebbed-8` or testing `1.3.4.258.gc60b10b0946a-2` for private
local packaging; neither client payload is included in the public bootstrap.

The preceding community bootstrap was delivered by COPR build 11231606 and
verified against its Actions provenance. Those package/scan records remain
historical evidence; neither that package nor the earlier `spotify` RPM
contains the new `spot..fly..light` command. The validation record keeps the
original artifact names and hashes unchanged.

## Why this fork changed

The owner wanted an RPM workflow that preserved the current vendor application's
appearance, adapted to graphics drivers, checked downloaded content and avoided
publicly redistributing proprietary client payloads. Earlier local comparisons
found that the stable and testing repositories supplied different vendor
versions. That distinction can explain differences in interface appearance;
changing the packaging layout cannot turn an older client into a newer one.

The changes below describe this fork's engineering decisions. They are not a
finding that the upstream maintainer violated the law, shipped malware or caused
every reported display problem.

* Direct public client RPM/SRPM delivery was replaced with a freely licensed,
  payload-free bootstrap. The real client is downloaded and packaged locally
  after the requesting user's approval. Malware scanning runs in Actions, not on the user host.
* Four former client RPM/SRPM release assets and their two corresponding Actions
  ZIP archives were removed during the earlier migration. The later authorized
  release-record cleanup remains historical evidence. The current delivery
  policy permits GitHub Releases only for the freely licensed, payload-free
  installer RPM/SRPM and checksums, never the proprietary client. Publication
  and cleanup must be verified from live service records.
* Nginx, Docker Hub and GHCR distribution are not part of the delivery path.
  The launcher adds no usage telemetry or Spotify Developer API traffic.
* The DEB's size and SHA256 are checked before extraction. Fresh ClamAV
  signatures and a mandatory malware scan in the GitHub Actions VM gate COPR delivery. A separate PUA
  report preserves PUA-only findings without treating them as confirmed malware.
* Debian maintainer scripts are not executed. The original application tree,
  resources and bundled third-party notices are preserved. A file manifest
  checks original vendor bytes during the local RPM build.
* A session-time graphics launcher detects drivers and display environment.
  It keeps NVIDIA variables away from Mesa systems, uses supported hybrid
  offload when available and offers bounded graphics fallback and diagnostics.
* The standalone builder follows the local-build idea used by LPF, but does not
  silently claim to be the actual LPF framework. It has its own consent, cache,
  retry and installation logic; it does not create LPF's dedicated build user.
* License scope, original attribution, upstream source links and timestamped
  provenance were documented. A timestamp establishes evidence about bytes;
  it does not grant rights to Spotify software.
* Stable and testing selection use one bootstrap, one command and one local
  target package. A channel switch replaces the installed target.

## What the two packages contain

| Package | Location | Contents |
| --- | --- | --- |
| `spot-fly-light` | COPR / GitHub Releases | Community launcher, local packaging helpers, source metadata and notices; no Spotify executable, logo or application archive |
| `spot-fly-light-client-local` | Built on the user's computer | The verified official application and local integration; subject to Spotify and bundled third-party terms |

Keep the generated client RPM private. The project's MIT grant for its new
helpers does not license the Spotify application or all inherited source files.
See [the current legal review](legal-review-2026-10-30.md), [LICENSE](../LICENSE),
[active installation notice](../bootstrap/NOTICE.txt) and
[active disclaimer](../bootstrap/DISCLAIMER.txt).

## Automated workflow

The scheduler requests checks at 12:00 and 17:00 in `Europe/Stockholm`.
GitHub scheduling can be delayed. Stable and testing are kept separate; a pool
filename alone does not establish a stable release.

The configured network source order is:

1. `https://download.spotify.com/debian` — official metadata and DEB source.
2. `https://repository.spotify.com` — official metadata and DEB source.
3. `https://repository-origin.spotify.com` — official metadata and DEB source.
4. `https://deb.rug.nl/ppa/mirror/repository.spotify.com` — an unofficial,
   byte-download fallback only, for the already pinned official filename.

Only the three official indexes determine channel, version, filename, size and
SHA256. Source discovery fails if all three official indexes are unavailable;
it does not trust a mirror's index or select an arbitrary mirror version. A
DEB fetched from the unofficial fallback must match the exact official size
and SHA256 before use. A valid private cache is checked first and avoids a
network download. RPM Fusion references remain the final advisory check and
cannot override official channel or source identity.


When the selected metadata has not changed, a scheduled run ends before
packaging or COPR submission. A manual workflow can repackage an unchanged
version. The installer uses the packaging date in `Europe/Stockholm` as its
`yy.mm.dd` Version, with a Release that starts at 1 and increases on the same
date. Its description lists the separate stable/testing Spotify versions.
Client packaging counters remain tied to each upstream version and reset to 1
when that upstream version changes. A date change alone does not make an
unchanged scheduled run publish. Reservation tags prevent concurrent or
interrupted attempts from reusing a number.

The CI runner temporarily downloads the selected official DEBs, verifies and
extracts them, updates ClamAV and scans the DEBs and unpacked content. A source-
hash-bound scan record is included in the bootstrap. It constructs the payload-free source RPM using an explicit free-helper
allowlist, submits only that RPM directly to COPR and waits
for the build result. The DEB and extracted application are never uploaded or
retained as Actions artifacts. After successful COPR delivery, GitHub Releases
may contain only the verified free installer RPM/SRPM and `SHA256SUMS`.
The Spotify DEB and locally built proprietary client remain separate and
are never release assets. Temporary packages and credentials are removed on
runner exit; GitHub manages
teardown of its hosted VM. Cleanup does not erase already published logs,
source history or other providers' retention systems.

## Installation on Fedora

These commands are for a supported x86_64 installation with no conflicting
Spotify/LPF package. If an existing installation works, review a migration
transaction first; the installer does not silently erase another vendor's
package or the user's configuration.

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install spot-fly-light
```

After the installer is installed or updated, an active graphical user session
is asked which pinned client to install: stable or unstable/testing, with both
version numbers shown. Continuing opens a terminal and runs
`spot..fly..light --setup` or `spot..fly..light --setup -unstable` for the selected
channel. The legal notice still requires your separate approval. Cancel closes
the chooser without downloading or building and dismisses it for that installer
version; the commands remain available manually.

The popup runs as the desktop user, not inside a privileged RPM scriptlet.
If no usable desktop session is available at installation, it is deferred until
the next graphical login. Each desktop user is prompted once per installer
Version-Release. For a terminal-only installation, use the setup commands below.

```sh
spot..fly..light --setup
```

Run setup as your normal desktop user. Review the displayed notice and Spotify's
terms applicable in your country. Acceptance allows the original DEB download,
verification against the CI scan record and local build. Only the final package-manager transaction
requests administrator authorization. Declining cancels the operation; removal
of an already installed local target also requires system authorization.

To choose testing for installation, use this instead of the last command:

```sh
spot..fly..light --setup -unstable
```

`-unstable` is an option of Spot..Light. It is not a DNF option, a second package
name or a separate executable. Both channels install `spot-fly-light-client-local`.
The vendor application retains its own name and ownership.

After setup, start the application with:

```sh
spot..fly..light
```

## Inspect available client versions and help

```sh
dnf info spot-fly-light
spot..fly..light --client-versions
spot..fly..light -cl.ver
spot..fly..light --help
spot..fly..light -h
spot-fly-light --help
spot-fly-light -h
```

Both command names accept the same options. The client-version commands read
the installed catalog; they do not claim to query a newer live Spotify release.
The help lists setup, channel selection, update, state, diagnostics, safe mode
and normal launch behavior. The installer Version belongs to this project and
uses its Stockholm packaging date; the listed client versions belong to Spotify.

## Refresh, update and switch channels

Refresh the repository metadata and update the bootstrap before asking it to
update the client:

```sh
sudo dnf makecache --refresh
sudo dnf upgrade --refresh spot-fly-light
spot..fly..light --update
```

Without `-unstable`, setup/update selects stable even if testing was installed.
Returning to stable can be a version downgrade. To install/update to testing:

```sh
spot..fly..light --update -unstable
```

The same target identity replaces the previous channel; stable and testing are
not installed side by side. Launching `spot..fly..light` runs the installed selection;
it does not silently switch channels at each launch. Neither setup nor an update
is permission to share the generated proprietary client RPM.

```sh
spot..fly..light --status
spot..fly..light --install
spot..fly..light --rebuild
spot..fly..light --debug
spot..fly..light --safe-mode
```

`--install` retries a verified pending RPM, and `--rebuild` requests a new local
verified download/build. It does not run ClamAV on the user host. Use the same explicit channel option when operating on testing.
Local verification/build records and cache files remain in the user's `${XDG_STATE_HOME:-$HOME/.local/state}/spot..fly..light-bootstrap/<version>/`
directory; CI scan logs are separate workflow evidence. Review relevant
records before deleting them.

## Existing installations and migration

Before downloading, the installer checks for conflicting client packages. A
previous local target is eligible for replacement only after it is identified
as this project's own package. Existing LPF or other vendor installations are
not silently removed. Review the DNF transaction before accepting migration;
stop and resolve an unrelated conflicting package explicitly.

The current configuration directory is `~/.config/spot..fly..light/`; its files
are `flags.conf` and `environment.conf`. Current environment overrides are
`SPOT_FLY_LIGHT_GPU_MODE` and `SPOT_FLY_LIGHT_DEBUG`. For each configuration
file, a previous project configuration file is read only when the current file
is absent. Existing files are not moved or deleted. Recognized earlier GPU/debug
settings remain fallback values, while current settings take precedence.
This does not migrate consent. A new local build also considers the project's
same-version earlier cache and installed local target when choosing its next
packaging revision. Vendor application data keeps its original identity.

## Installation duration and private cache

The installer reports completed-step counts, a stage completion percentage
and elapsed time. Step durations vary, so this percentage measures completion
of steps rather than predicting remaining time. Downloads report transferred
bytes, percentage, speed and estimated remaining time; hash checks report
progress. RPM build output streams live, and periodic elapsed-time messages
show that a longer operation is still running. Downloading the original DEB,
verification, extraction, final RPM compression and dependency resolution can
all take time; none is a local antivirus scan. Details are retained in
`setup-progress.log` and `rpm-build.log` in the version-specific local state
directory.

Verified DEBs are retained privately under
`${XDG_STATE_HOME:-$HOME/.local/state}/spot..fly..light-bootstrap/downloads/<sha256>.deb`.
Reusing a cached DEB requires a fresh size/SHA256 check. Invalid cached content
is discarded and downloaded again. The private cache is for personal local
builds, not redistribution. An uncompressed intermediate tar archive avoids
compressing the application tree twice before final RPM creation. `--install`
retries a verified pending RPM without repeating the DEB download or build.

## Removal and repository management

Remove just the generated client:

```sh
sudo dnf remove spot-fly-light-client-local
```

Remove both this project's packages:

```sh
sudo dnf remove spot-fly-light-client-local spot-fly-light
```

Disable future downloads from the COPR repository:

```sh
sudo dnf copr disable universish/Spotify..Client
```

Disabling a repository does not uninstall packages or erase a user's preferences.
On DNF5, `sudo dnf copr remove universish/Spotify..Client` also removes the
repository configuration file. Inspect the package-manager transaction before
accepting removal. Local build caches and vendor user data are separate from
installed RPM files and are not automatically deleted by these commands.

## Scope and limits

The goal is a transparent, inspectable packaging path for personal installation
of the original client, with explicit consent, reproducible source selection and
practical graphics compatibility. A scan cannot prove the absence of unknown
threats. Passing a COPR build does not establish playback on every GPU or every
enabled distribution. Vendor requirements are retained; old runtimes are not
made compatible by ignoring dependencies.

Hosting, notices and consent do not transfer all responsibility to Fedora or
users. Each participant retains their own obligations. This project grants no
additional Spotify license and makes no claim of Spotify endorsement.

The unused inherited `src/spotify-client.svg` was removed from the current source
tree during the naming review. The public bootstrap has no vendor icon. Local
client icons come from the original DEB and remain in the private client RPM.
Historical Git commits were not rewritten.
