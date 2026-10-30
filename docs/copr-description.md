# Sonicradle — community local installer for Spotify

Independent community project. Not affiliated with, approved by or supported by
Spotify, Fedora or Red Hat. The historical COPR identifier is
`universish/Spotify..Client`; the package and terminal command are `sonicradle`.

This repository distributes only a freely licensed, payload-free bootstrap.
It does not contain the Spotify executable, application archive or logo.
After your approval, Sonicradle downloads the official amd64 DEB on your own
computer, checks its size and SHA256 against the CI-scanned source record
and builds a private local RPM. ClamAV runs only in the GitHub Actions VM;
it is not installed or run on your computer. Administrator authorization is requested for the
final installation. Debian installation scripts are not executed.

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
can coexist. If `dnf copr` is unavailable, install the matching COPR plugin for
your Fedora/DNF version first.

## Add the repository and install stable

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install sonicradle
sonicradle --setup
```

Run setup as your normal user, without sudo. Review and accept the displayed
terms if you wish to proceed. The bootstrap is `sonicradle`; the client it
builds locally is `sonicradle-client-local`.

## Install testing instead

```sh
sonicradle --setup -unstable
```

`-unstable` belongs to the Sonicradle command, not to `dnf`. There is no separate
`sonicradle-unstable` package or executable. Stable is the default; testing is
selected only by an explicit option. Both replace the same local client RPM, so
there is no simultaneous stable/testing installation.

## Launch and diagnose

```sh
sonicradle
sonicradle --debug
sonicradle --safe-mode
sonicradle --status
```

## Refresh repository metadata

```sh
sudo dnf makecache --refresh
```

This refreshes package metadata; it does not rebuild or reinstall the client.

## Update/upgrade the bootstrap and stable client

```sh
sudo dnf upgrade --refresh sonicradle
sonicradle --update
```

DNF upgrades the free bootstrap. Sonicradle separately verifies the source hash,
builds and requests installation of the selected client. Omitting `-unstable` selects
stable, including when switching back from testing. That switch can install an
older vendor version.

## Update/upgrade to testing

```sh
sudo dnf upgrade --refresh sonicradle
sonicradle --update -unstable
```

For a fresh local verified download/build of the selected stable version, use
`sonicradle --rebuild`; for testing, use `sonicradle --rebuild -unstable`.
`sonicradle --install` retries a verified pending local RPM without repeating
the download and build; add `-unstable` for a pending testing build.

## Remove the client

```sh
sudo dnf remove sonicradle-client-local
```

## Remove both packages

```sh
sudo dnf remove sonicradle-client-local sonicradle
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

The automated workflow checks official Spotify metadata before RPM Fusion's
Fedora 44/Rawhide packaging references. No GitHub Release RPMs are published.
COPR receives only the free bootstrap SRPM; the proprietary client is built on
the end user's computer. No Nginx, Docker Hub, GHCR or usage telemetry is used.
