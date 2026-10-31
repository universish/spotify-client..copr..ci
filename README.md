# Spot..Light Local RPM Installer — universish

> The next installer includes date-based versioning, channel selection, English
> notices, verified migration and detailed progress. Publication awaits
> verification; the completed release below remains historical evidence.

The project name is **Spot..Light**, its RPM package is **`spot-fly-light`**,
and its terminal command is **`spot..fly..light`**. **`spot-fly-light`** is an
equivalent command alias. RPM package names cannot contain `..`, so the package
uses hyphens while the primary command keeps the chosen spelling.

> **31 October 2026:** Bootstrap `spot-fly-light-1.2.95.453.g0eeebbed-8`
> built successfully for all 17 targets in [COPR build 11233588](https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/build/11233588/).
> [Actions run 41151337784](https://github.com/universish/spotify-client..copr..ci/actions/runs/41151337784)
> records the CI scans and delivery. The bootstrap contains both stable and
> testing source records in the same installer.

**Please read before downloading and installing:** The COPR RPM is a small community-maintained
installer. It does not include the Spotify app, logo, or proprietary binaries.
The Spotify client is downloaded from the official DEB on **your own computer** after your approval,
verified against the CI-scanned source hash, and packaged as a local RPM. This is not a project supported
or endorsed by Spotify.

[Current legal notice and terms](bootstrap/NOTICE.txt), [disclaimer](bootstrap/DISCLAIMER.txt),
[license scope](LICENSE), and [copyright/attributions](COPYRIGHT) must be read before downloading.
You must comply with Spotify’s [terms applicable to your country](https://www.spotify.com/legal/end-user-agreement/).
Approval does not transfer all legal liability to the user; it does not waive mandatory rights
or eliminate the maintainer’s own obligations. These documents do not grant permission to
redistribute Spotify RPMs. Do not share the local client RPM.

## Installation and Acceptance

The freely licensed installer RPM is distributed through COPR and GitHub Releases.
GitHub release assets contain only the payload-free installer RPM/SRPM and
`SHA256SUMS`. The Spotify DEB and locally built client RPM are never published
there. COPR provides repository-managed updates; GitHub provides direct downloads.

To install the installer published via COPR:

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

In a graphical session, a Zenity window opens displaying the legal text and a checkbox.
If you agree, the DEB file is downloaded and verified against the CI-scanned source hash; the local `spot-fly-light-client-local`
RPM is built. The package manager then opens with system privileges.
Administrator privileges are used only for the final installation/uninstallation process.

If you decline, the download, build, and execution will stop. If our `spot-fly-light-client-local`
package is already installed, system authorization is requested for its removal.
If authorization is not granted or the removal fails, it is not assumed to have been automatically deleted;
this launcher will again refuse to run. Existing LPF/vendor packages are not automatically
removed. You can remove the small installer RPM separately using your package manager.

The installer RPM itself does not accept Spotify terms or download the client
in a DNF/RPM scriptlet. **Confirmation for the actual Spotify client comes in
the user session.** If the terms of service change, confirmation will be
requested again. The confirmation record is user-specific. A user without a graphical session can
run `spot..fly..light --setup --accept-spotify-terms` explicitly after reviewing the text.

```sh
spot..fly..light
spot..fly..light --debug
spot..fly..light --safe-mode
spot..fly..light --gpu-mode=native
```

## Versions and command help

The installer has its own date-based version. DNF's package description lists
both pinned Spotify client versions; it does not label the installer with
Spotify's stable version. To inspect the repository package or the catalog
already installed on your computer:

```sh
dnf info spot-fly-light
spot..fly..light --client-versions
spot..fly..light -cl.ver
spot..fly..light --help
spot..fly..light -h
spot-fly-light --help
spot-fly-light -h
```

`--client-versions` and `-cl.ver` read the installed installer's catalog. They
show what this installer can build, without downloading or installing a client.
Update `spot-fly-light` through DNF to receive a newer catalog.

| Command | Purpose |
| --- | --- |
| `spot..fly..light` | Launch the installed client selection. |
| `spot..fly..light --setup` | Review terms, build and request installation of the pinned stable client. |
| `spot..fly..light --setup -unstable` | Perform setup for the pinned testing client. |
| `-unstable` (with setup/update/install/rebuild) | Select testing for that operation; a standalone launch option does not switch clients. |
| `spot..fly..light --update` | Build/install the stable client offered by the installed bootstrap. |
| `spot..fly..light --update -unstable` | Build/install the testing client offered by the installed bootstrap. |
| `spot..fly..light --debug` | Launch with graphics diagnostics. |
| `spot..fly..light --safe-mode` | Launch with the software-rendering fallback. |
| `spot..fly..light --status` | Report approval, build and installation readiness. |
| `spot..fly..light --client-versions` or `-cl.ver` | List both pinned client versions. |
| `spot..fly..light --help` or `-h` | Explain command options and usage. |

The `spot-fly-light` alias accepts the same options.

## Local Client Build

1. GitHub Actions verifies the official amd64 DEB and updates ClamAV signatures.
2. The DEB and extracted content are scanned; malware, errors and exceeded limits stop COPR delivery.
3. A separate PUA pass reports PUA-only matches without treating them as confirmed malware.
4. The payload-free bootstrap records the source SHA256 and CI scan result, not the application.
5. On your computer, the same DEB is downloaded, its size/hash checked and its contents extracted
   without running Debian scripts. ClamAV is neither installed nor run on your computer.
6. As in the LPF local-build model, the application tree is kept intact under `/usr/share/spot..fly..light-client/`.
   The RPM `%check` phase re-verifies the SHA256 values of the original files.
7. A local RPM is created, and installation with system privileges is requested.

Local verification/build records are under `${XDG_STATE_HOME:-$HOME/.local/state}/spot..fly..light-bootstrap/<version>/`.
ClamAV scan reports are retained in Actions instead.

The download, size/SHA256 verification, extraction, local RPM compression and
package-manager dependency resolution can each take time. Stage messages show
completed-step counts, a completion percentage and elapsed time. Steps have
different durations, so the stage percentage does not predict remaining time.
Downloads report transferred bytes, percentage, speed and estimated remaining
time. Hash checks report progress, RPM build output is streamed live and
periodic elapsed-time messages remain visible during longer operations.
Verified official DEBs are retained privately under
`${XDG_STATE_HOME:-$HOME/.local/state}/spot..fly..light-bootstrap/downloads/<sha256>.deb`.
Each reuse verifies the full size and SHA256 again; an invalid cache is discarded.
This personal cache is not a redistribution channel. The local build uses an
uncompressed intermediate tar archive before final RPM compression. Build details and stage timings are retained in the local state
directory. `setup-progress.log` records setup stages; `rpm-build.log` contains
the RPM build output. No local antivirus scan is performed.
Scanning does not guarantee the absence of all unknown threats. Approval, local download and packaging
are performed as the requesting user; the installer’s RPM scriptlets do not download or run Spotify.

The NVIDIA desktop GL profile tracks active LPF settings; PRIME is applied
on supported hybrid GPUs. NVIDIA variables are not added to AMD/Intel/Nouveau. In the event of an early graphics
error, there is limited ANGLE/software fallback. Ozone/DPI is not forced.
User `spot..fly..light/flags.conf` and `spot..fly..light/environment.conf` files are preserved; the environment file
is not executed as shell code. [GPU details](docs/gpu-launcher.md).

## Automation

The build pipeline now produces only **installer RPMs/SRPMs that do not contain proprietary content**.
It checks both official channels daily at 12:00 and 17:00 Stockholm time; if
both pinned source records are unchanged from a successful delivery, it skips
the build. Manual triggering also repackages unchanged sources.
The installer version is the packaging date in `Europe/Stockholm`, formatted
`yy.mm.dd` (for example, `26.10.31`). Its RPM Release starts at `1` for that
date and increases for another packaging attempt on the same date. Spotify
client versions are separate; each channel starts its local packaging counter
at `1` for a new upstream version. An unchanged scheduled check does not
publish a new installer merely because the date changed.
The official stable/testing DEBs and their extracted contents are scanned in Actions.
After successful COPR delivery, the workflow may publish only the verified free
installer RPM/SRPM and `SHA256SUMS` in GitHub Releases. Temporary runner DEBs,
extracted application trees and RPM files are then removed; GitHub manages
teardown of the hosted VM. No proprietary client is uploaded.

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

The default is stable x86_64; explicit `-unstable` selects testing. There is no ARM/32-bit version.
The difference between LPF source 1.3.4 and the official stable 1.2.95 is explained [in the LPF documentation](docs/lpf-compatibility.md);
testing is not automatically selected. RPM Fusion Fedora 44/Rawhide references
are checked last and cannot override the official DEB channel/hash.

The `COPR_CONFIG` secret setting and active distribution selection are [in the COPR documentation](docs/copr.md).
Main uses the payload-free bootstrap model. The previously verified
`1.2.95.453.g0eeebbed-4` publication and its authorized cleanup are historical.
The current policy allows only free installer RPM/SRPM releases, with the
Spotify download and private local client build kept separate. Cleanup and COPR
results are recorded separately in the
[validation log](docs/validation.md). Nginx, Docker Hub and GHCR are not used. The community helper adds no usage
telemetry; this statement does not describe the vendor client’s own network behavior.
Deleting GitHub assets removes their download counters; COPR downloads also do
not measure active users.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Package construction requires both channel records and valid Actions scan evidence;
the sequence is documented in [the release flow](docs/release-flow.md) and workflow.
The build source archive is created using an explicit allowlist;
producers with unclear licenses from the old fork and Spotify data are not included in this archive.
`src/build_once.sh` preserves the old direct client build solely for local comparisons;
the COPR/GitHub build release does not use this script.


## Installer state and retry

```sh
spot..fly..light --status
spot..fly..light --install
spot..fly..light --rebuild
```

`--status` reports approval/build/install readiness. `--install` retries a
previously built RPM after checking its hash and package identity; it does not
repeat the DEB download. `--rebuild` requests a fresh local verification/build; it does not run ClamAV on the user host. New source
versions or bootstrap revisions need renewed approval.

This standalone installer does not use the actual LPF framework; see the
[LPF comparison](docs/lpf-framework-audit.md) for account, lifecycle and
notification differences.

## Spot..Light: stable / testing channel operations

```sh
spot..fly..light --setup
spot..fly..light --setup -unstable
sudo dnf upgrade --refresh spot-fly-light
spot..fly..light --update
spot..fly..light --update -unstable
sudo dnf remove spot-fly-light-client-local spot-fly-light
sudo dnf copr disable universish/Spotify..Client
```

`-unstable` is a Spot..Light option, not a DNF option or a second package name.
Setup/update without it selects stable, including a switch from testing back to
stable; that can install an older vendor version. Both channels replace the
same local target, so there is one installed client. Launching `spot..fly..light` runs
the installed selection. Run setup/update without sudo. If an LPF/vendor client
is already installed, review migration first rather than assuming coexistence.

Read the English [project history and operating guide](docs/project-history-and-operation.md),
[paste-ready COPR description](docs/copr-description.md) and
[current legal/naming review](docs/legal-review-2026-10-30.md). COPR hosting
does not transfer responsibility to Fedora. The root notice/license files in
the original timestamp manifest remain historical evidence; active installation
notices are in `bootstrap/NOTICE.txt` and `bootstrap/DISCLAIMER.txt`.

## Existing installations and migration

Before downloading or building, the installer checks for conflicting client
packages. Only a previous local target verified as this project's own package
is eligible for automatic replacement within the normal package-manager
transaction. An unrelated LPF or other vendor package requires explicit
migration review. Read the proposed transaction before accepting it.

Current settings use `~/.config/spot..fly..light/flags.conf` and
`~/.config/spot..fly..light/environment.conf`. When a new configuration file is
absent, the corresponding file in this project's previous configuration
directory is read without moving or deleting it. Recognized previous GPU/debug
settings remain fallback values; current settings take precedence. Consent is
not migrated. Same-version local packaging counters also consider this
project's own previous cache and installed local target.
