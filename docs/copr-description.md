# Spot..Light — community local installer for Spotify

Independent community project. Not affiliated with, approved by or supported by
Spotify, Fedora or Red Hat. The historical COPR identifier is
`universish/Spotify..Client`; the RPM package is `spot-fly-light` and the
primary terminal command is `spot..fly..light`; `spot-fly-light` is an
equivalent command alias. RPM names cannot contain `..`, so the package name
uses hyphens. The installer Version is its packaging date in Stockholm
(`yy.mm.dd`), with a separate same-day Release counter. Its DNF description
lists the distinct stable and testing client versions it can install.

This repository distributes only a freely licensed, payload-free bootstrap.
It does not contain the Spotify executable, application archive or logo.
After your approval, Spot..Light downloads the official amd64 DEB on your own
computer, checks its size and SHA256 against the CI-scanned source record
and builds a private local RPM. ClamAV runs only in the GitHub Actions VM;
it is not installed or run on your computer. Administrator authorization is requested for the
final installation. Debian installation scripts are not executed.

Downloading, hash verification, extraction, local RPM compression and dependency
resolution can each take time. The installer shows stage completion percentages,
elapsed-time heartbeats, download bytes/percentage/speed/ETA, hash progress and
live RPM build output. Stage percentages measure completed operations, not time
remaining. Timings are written to `setup-progress.log` next to the local build
log. Verified DEBs are kept in a private hash-keyed cache and checked again
before reuse, avoiding another network download. The cache and resulting
client RPM are for personal local use, not redistribution. `--install` retries
a previously built, verified pending RPM without downloading or rebuilding it.

The purpose is to preserve the original application resources, provide explicit
source/channel selection and improve graphics compatibility without publicly
hosting repackaged proprietary client binaries. It uses an independent local
builder inspired by LPF's architecture; it is not the LPF framework.

## Read before installing

Spotify and bundled third-party software keep their own ownership and terms.
The MIT license for the new community helpers does not license Spotify or grant
redistribution permission. Read [Spotify's current terms for your country](https://www.spotify.com/legal/end-user-agreement/),
the [installation notice](https://github.com/universish/spotify-client..copr..ci/blob/main/bootstrap/NOTICE.txt)
and [disclaimer](https://github.com/universish/spotify-client..copr..ci/blob/main/bootstrap/DISCLAIMER.txt).
Do not share or upload the locally generated client RPM.

Consent does not waive mandatory rights or transfer the maintainer's obligations
to you. COPR hosting does not transfer those obligations to Fedora or Red Hat.
Scans and hashes reduce certain risks; they do not prove absolute safety or grant
legal permission. A PUA-only finding is reported separately; ordinary malware,
scanner errors or exceeded limits in CI stop delivery to COPR.

Declining stops download, build and launch. If this project's local target is
already installed, its removal is requested through system authorization. If
authorization fails, the package can remain installed, but this launcher refuses
to run it. Another vendor's LPF/Spotify installation is not silently removed.

## Supported installations

x86_64 only, with distribution and library versions compatible with the selected
official DEB. ARM and 32-bit systems are not supported. A successful bootstrap
build does not establish compatibility of the proprietary client with an old
runtime. Dependencies are not bypassed.

The following commands are for Fedora with DNF and the COPR plugin. Review an
existing LPF/Spotify installation before switching; do not assume the packages
can coexist. Before downloading, the installer identifies conflicting packages.
Only a previous local target verified as this project's own package is eligible
for replacement; unrelated vendor packages are not silently removed.
Review the proposed package transaction before accepting it.
If `dnf copr` is unavailable, install the matching COPR plugin for
your Fedora/DNF version first.

## Add the repository and install stable

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

Run setup as your normal user, without sudo. Review and accept the displayed
terms if you wish to proceed. The bootstrap is `spot-fly-light`; the client it
builds locally is `spot-fly-light-client-local`.

## Install testing instead

```sh
spot..fly..light --setup -unstable
```

`-unstable` belongs to the Spot..Light command, not to `dnf`. There is no separate
`spot-fly-light-unstable` package or second executable. Stable is the default; testing is
selected only by an explicit option. Both replace the same local client RPM, so
there is no simultaneous stable/testing installation.

## Launch and diagnose

```sh
spot..fly..light
spot..fly..light --debug
spot..fly..light --safe-mode
spot..fly..light --status
```

## Inspect versions and help

```sh
dnf info spot-fly-light
spot..fly..light --client-versions
spot..fly..light -cl.ver
spot..fly..light --help
spot..fly..light -h
spot-fly-light --help
spot-fly-light -h
```

The version commands report both client versions in the installed bootstrap's
catalog, without downloading or installing them. Help explains normal launch,
setup, update, testing selection, status, debug and safe mode. Both command
names accept the same options.

## Refresh repository metadata

```sh
sudo dnf makecache --refresh
```

This refreshes package metadata; it does not rebuild or reinstall the client.

## Update/upgrade the bootstrap and stable client

```sh
sudo dnf upgrade --refresh spot-fly-light
spot..fly..light --update
```

DNF upgrades the free bootstrap. Spot..Light separately verifies the source hash,
builds and requests installation of the selected client. Omitting `-unstable` selects
stable, including when switching back from testing. That switch can install an
older vendor version.

## Update/upgrade to testing

```sh
sudo dnf upgrade --refresh spot-fly-light
spot..fly..light --update -unstable
```

For a fresh local verified download/build of the selected stable version, use
`spot..fly..light --rebuild`; for testing, use `spot..fly..light --rebuild -unstable`.
`spot..fly..light --install` retries a verified pending local RPM without repeating
the download and build; add `-unstable` for a pending testing build.

## Remove the client

```sh
sudo dnf remove spot-fly-light-client-local
```

## Remove both packages

```sh
sudo dnf remove spot-fly-light-client-local spot-fly-light
```

These commands do not erase local build/download caches or vendor preferences.
Review those separately if you also want to delete personal data.

## Disable or remove the repository

```sh
sudo dnf copr disable universish/Spotify..Client
```

Disabling the repository leaves installed packages in place. With DNF5, remove
its repository configuration entirely using:

```sh
sudo dnf copr remove universish/Spotify..Client
```

## Sources, licensing and build policy

Source and change history:
[universish/spotify-client..copr..ci](https://github.com/universish/spotify-client..copr..ci).
Fork origin:
[zicstardust/spotify-rpm-packager](https://github.com/zicstardust/spotify-rpm-packager).
New independently authored helpers: MIT, within the scope of the repository's
[licensing notice](https://github.com/universish/spotify-client..copr..ci/blob/main/LICENSE).
Inherited files without a verified compatible grant are excluded from the
distributed bootstrap source archive.

Official metadata/download sources are tried in order: `download.spotify.com/debian`,
`repository.spotify.com`, then `repository-origin.spotify.com`. The unofficial
`deb.rug.nl/ppa/mirror/repository.spotify.com` is a final byte-download fallback
only; the pinned official filename, size and SHA256 must match. It cannot select
a channel or version, and source discovery stops if all official indexes fail.

The automated workflow checks official Spotify metadata before RPM Fusion's
Fedora 44/Rawhide packaging references. GitHub Releases may contain only the
verified free installer RPM/SRPM and `SHA256SUMS`; the official Spotify DEB and
private client RPM are excluded. COPR receives only the free bootstrap SRPM;
the proprietary client is built on
the end user's computer. The community helper uses no Nginx, Docker Hub or GHCR and adds no usage
telemetry. This statement does not describe the vendor client’s network behavior.
