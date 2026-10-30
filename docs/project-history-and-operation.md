# Sonicradle: origin, purpose and operation

Sonicradle is an independent community installer and launcher for the official
Spotify Linux desktop application. It is maintained in
[universish/spotify-client..copr..ci](https://github.com/universish/spotify-client..copr..ci),
a fork of [zicstardust/spotify-rpm-packager](https://github.com/zicstardust/spotify-rpm-packager).
The historical repository and COPR identifiers have been retained for continuity;
the new public package and terminal command are `sonicradle`.

This project is not affiliated with, approved by or supported by Spotify. COPR
hosting does not make it an official Fedora or Red Hat package. The choice of a
new project name is not a claim of completed trademark clearance.

The current Sonicradle bootstrap was delivered by COPR build 11231606 and
verified against its Actions provenance. The validation record contains the
package, scan and legacy-host cleanup evidence. The earlier `spotify` RPM
does not contain the new `sonicradle` command.

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
  ZIP archives were removed during the earlier migration. The current delivery
  policy also removes remaining GitHub release assets and stops creating new
  GitHub Releases. Publication and cleanup must be verified from live service
  records; source tags alone are not RPM downloads.
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
| `sonicradle` | COPR | Community launcher, local packaging helpers, source metadata and notices; no Spotify executable, logo or application archive |
| `sonicradle-client-local` | Built on the user's computer | The verified official application and local integration; subject to Spotify and bundled third-party terms |

Keep the generated client RPM private. The project's MIT grant for its new
helpers does not license the Spotify application or all inherited source files.
See [the current legal review](legal-review-2026-10-30.md), [LICENSE](../LICENSE),
[active installation notice](../bootstrap/NOTICE.txt) and
[active disclaimer](../bootstrap/DISCLAIMER.txt).

## Automated workflow

The scheduler requests checks at 12:00 and 17:00 in `Europe/Stockholm`.
GitHub scheduling can be delayed. Official Spotify metadata is checked first:
`download.spotify.com/debian`, then `repository.spotify.com`. RPM Fusion's
Fedora 44 and Rawhide packaging metadata is a final reference/fallback check,
not a substitute primary publisher of the application. Stable and testing are
kept separate; a pool filename alone does not establish a stable release.

When the selected metadata has not changed, a scheduled run ends before
packaging or COPR submission. A manual workflow can repackage an unchanged
version. The RPM release number increases for repeated packaging of the same
upstream version, and starts at 1 for a new upstream version. Reservation tags
prevent concurrent or interrupted attempts from reusing a number.

The CI runner temporarily downloads the selected official DEBs, verifies and
extracts them, updates ClamAV and scans the DEBs and unpacked content. A source-
hash-bound scan record is included in the bootstrap. It constructs the payload-free source RPM using an explicit free-helper
allowlist, submits only that RPM directly to COPR and waits
for the build result. The DEB and extracted application are never uploaded or
retained as Actions artifacts. No RPM is published in GitHub Releases.
Temporary packages and credentials are removed on runner exit; GitHub manages
teardown of its hosted VM. Cleanup does not erase already published logs,
source history or other providers' retention systems.

## Installation on Fedora

These commands are for a supported x86_64 installation with no conflicting
Spotify/LPF package. If an existing installation works, review a migration
transaction first; the installer does not silently erase another vendor's
package or the user's configuration.

```sh
sudo dnf copr enable universish/Spotify..Client
sudo dnf install sonicradle
sonicradle --setup
```

Run setup as your normal desktop user. Review the displayed notice and Spotify's
terms applicable in your country. Acceptance allows the original DEB download,
verification against the CI scan record and local build. Only the final package-manager transaction
requests administrator authorization. Declining cancels the operation; removal
of an already installed local target also requires system authorization.

To choose testing for installation, use this instead of the last command:

```sh
sonicradle --setup -unstable
```

`-unstable` is an option of Sonicradle. It is not a DNF option, a second package
name or a separate executable. Both channels install `sonicradle-client-local`.
The vendor application retains its own name and ownership.

After setup, start the application with:

```sh
sonicradle
```

## Refresh, update and switch channels

Refresh the repository metadata and update the bootstrap before asking it to
update the client:

```sh
sudo dnf makecache --refresh
sudo dnf upgrade --refresh sonicradle
sonicradle --update
```

Without `-unstable`, setup/update selects stable even if testing was installed.
Returning to stable can be a version downgrade. To install/update to testing:

```sh
sonicradle --update -unstable
```

The same target identity replaces the previous channel; stable and testing are
not installed side by side. Launching `sonicradle` runs the installed selection;
it does not silently switch channels at each launch. Neither setup nor an update
is permission to share the generated proprietary client RPM.

```sh
sonicradle --status
sonicradle --install
sonicradle --rebuild
sonicradle --debug
sonicradle --safe-mode
```

`--install` retries a verified pending RPM, and `--rebuild` requests a new local
verified download/build. It does not run ClamAV on the user host. Use the same explicit channel option when operating on testing.
Local verification/build records and cache files remain in the user's `${XDG_STATE_HOME:-$HOME/.local/state}/sonicradle-bootstrap/<version>/`
directory; CI scan logs are separate workflow evidence. Review relevant
records before deleting them.

## Removal and repository management

Remove just the generated client:

```sh
sudo dnf remove sonicradle-client-local
```

Remove both this project's packages:

```sh
sudo dnf remove sonicradle-client-local sonicradle
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
