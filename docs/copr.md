# COPR build setup

Project: https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/

## Hosting constraint

Fedora COPR's published terms restrict uploaded material to accepted Fedora
licenses. Spotify's proprietary client is not FOSS. This fork's binary RPM and
SRPM contain Spotify's proprietary payload; the packaging script being open source
does not change the payload's license. Confirm any exception or permission with
the COPR maintainers before publishing it on Fedora infrastructure. A separate
RPM repository is an alternative, subject to Spotify's redistribution terms.

Reference: https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr

The zicstardust/spotify-client project uses direct SRPM upload (`source_type:
upload`). This workflow uses the same technical upload mechanism. Credentials
are consumed only inside GitHub Actions; no credential is stored in Git.

## GitHub secret and running the workflow

1. Log in at https://copr.fedorainfracloud.org/api/ and copy the complete generated configuration.
2. Open https://github.com/universish/spotify-client..copr..ci/settings/secrets/actions
3. Choose New repository secret, name it `COPR_CONFIG`, and paste the complete configuration as its value.
4. Open Actions → Stable Spotify RPMs and COPR → Run workflow. No force or submit checkbox is needed.

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
mandatory scanning, source/binary RPM builds, automatic COPR upload and stable
GitHub publication in that order. See [release-flow.md](release-flow.md).
`SPOTIFY_RELEASE` is carried unchanged into RPM `Release:` and its changelog.
The source RPM's version-release is checked before submission.

`tools/submit_copr.sh` intersects `tools/targets.py --candidates` with the project's
live enabled chroots. An API read failure or an empty compatible list stops
submission; it never falls back to stale/all targets. Upload logs and the exact
selected target list are saved in the workflow's COPR validation artifact.
Network is needed while preparing the SRPM for Spotify and ClamAV. Binary rebuilds
on COPR consume the prepared tarball and require no outbound build network.

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
