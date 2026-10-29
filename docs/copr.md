# COPR build setup

Project: https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/

## Hosting constraint

The release workflow now uploads a **payload-free community bootstrap** SRPM.
`tools/build_bootstrap.py` uses an explicit allowlist of new MIT helpers, pinned
source metadata and notices. Spotify binaries, icons, application archives and
inherited generators with unresolved licensing are not included.

The separately built `spotify-client-local` RPM is proprietary, remains on the
user's computer, and must not be submitted to COPR or GitHub by this workflow.
The standalone legacy `src/build_once.sh` path is retained for local comparisons;
it is no longer the workflow's COPR source producer.

Reference: https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr
Legal analysis: [legal-distribution.md](legal-distribution.md).

## GitHub secret and running the workflow

1. Log in at https://copr.fedorainfracloud.org/api/ and copy the complete generated configuration.
2. Open https://github.com/universish/spotify-client..copr..ci/settings/secrets/actions
3. Choose New repository secret, name it `COPR_CONFIG`, and paste the complete configuration as its value.
4. Open Actions → Stable Spotify bootstrap RPMs and COPR → Run workflow. No force or submit checkbox is needed.

```ini
[copr-cli]
login = YOUR_GENERATED_LOGIN
username = universish
token = YOUR_GENERATED_TOKEN
copr_url = https://copr.fedorainfracloud.org
```

The API page states tokens expire after 180 days. Renew the repository secret
when needed. Local copr-cli can use the same generated configuration in
`~/.config/copr` with permissions 0600. Workflow submission uses a temporary
private configuration file, removes it on exit, and waits for the COPR result.
A missing/invalid `COPR_CONFIG` stops a required build before reserving a number
or downloading the DEB; unchanged scheduled checks need no COPR secret.

## Submission and release numbering

`spotify-rpm-releases.yml` performs version detection, number reservation,
bootstrap source construction/scanning, source/binary RPM builds, automatic COPR upload and stable
GitHub publication in that order. See [release-flow.md](release-flow.md).
`SPOTIFY_RELEASE` is carried unchanged into RPM `Release:` and its changelog.
The source RPM's version-release is checked before submission.

`tools/submit_copr.sh` intersects `tools/targets.py --candidates` with the project's
live enabled chroots. An API read failure or an empty compatible list stops
submission; it never falls back to stale/all targets. Upload logs and the exact
selected target list are saved in the workflow's COPR validation artifact.
Metadata checks contact Spotify; bootstrap-source scanning updates ClamAV.
COPR binary rebuilds consume only free bootstrap sources and need no outbound
build network. The proprietary DEB is downloaded/scanned on the user host.

For a new packaging number, use the GitHub workflow. Rebuilding an old uploaded
source directly in COPR keeps that source RPM's number. The optional SCM Makefile
therefore requires an explicit `SPOTIFY_RELEASE`; it does not share the Actions
counter. Local builds default to release 1 unless explicitly overridden.

## Current target configuration

The live project list was refreshed after the user's removals on 2026-10-28.
`packaging/targets.json` now contains 25 enabled targets: 17 candidates and 8
incompatible runtimes. Removed EL7/EL8, custom-1, Mageia 8/cauldron, Fedora 43,
openEuler 20.03/22.03, 32-bit and ARM entries are absent. Fedora 45 is enabled.

* `candidate`: x86_64 or x86_64_v2 targets with a plausible runtime. A successful
  COPR build does not itself prove graphical login and playback work.
* `incompatible`: remaining EL9, Mageia 9 and openEuler 24.03 runtimes predate
  the current DEB's glibc >= 2.39 requirement. Dependencies are never suppressed.

The x86_64_v2 package contains the same official amd64 binary; it is not optimized
from source for v2. Github Releases continues to publish x86_64 binaries only.

Sources:
https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages
https://copr.fedorainfracloud.org/api_3/project?ownername=universish&projectname=Spotify..Client
