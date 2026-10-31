# COPR build setup

Project: https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/

The historical project identifier remains descriptive. The independent community
RPM package is `spot-fly-light` and its command is `spot..fly..light`;
the local client package is
`spot-fly-light-client-local`. This is not an official Spotify/Fedora/Red Hat project.
For the paste-ready Description/Installation text, use
[copr-description.md](copr-description.md).

## Hosting boundary

Only the payload-free community bootstrap SRPM is uploaded to COPR. Its explicit
source allowlist contains newly authored MIT helpers, metadata, CI scan records
and notices. It excludes the DEB, app tree, proprietary icons and inherited
generators without a verified compatible grant. The proprietary client RPM is
built privately on the user's computer and is never submitted by this workflow.

COPR hosting does not transfer the maintainer's responsibilities to Fedora.
The uploader must have rights to uploaded content and follow the
[COPR rules](https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr).
See [the current legal review](legal-review-2026-10-30.md).

## API configuration

1. Log in at https://copr.fedorainfracloud.org/api/ and copy the complete generated configuration.
2. Open https://github.com/universish/spotify-client..copr..ci/settings/secrets/actions
3. Choose New repository secret, name it `COPR_CONFIG`, and paste the complete configuration as its value.
4. Use the repository's packaging workflow and Run workflow for a manual rebuild.

```ini
[copr-cli]
login = YOUR_GENERATED_LOGIN
username = universish
token = YOUR_GENERATED_TOKEN
copr_url = https://copr.fedorainfracloud.org
```

Do not put the token into Git, an issue, a README or a chat. Renew it when its
COPR API expiration requires it. Local copr-cli can read the same configuration
from `~/.config/copr` with permissions 0600. CI uses a temporary private file,
removes it on exit and waits for the COPR result. No webhook is required: the
scheduled/manual workflow submits the free SRPM through the API.

No VirusTotal API key is required by this implementation. ClamAV runs in the
GitHub Actions VM only. It is neither installed nor run by the local bootstrap
on the user's computer. No proprietary sample is uploaded to VirusTotal.

## Submission, numbering and evidence

The workflow detects both official channels, reserves a packaging number, scans
the official DEBs in CI, builds/scans the free SRPM, uploads it directly to COPR
and waits for completion. It does not create GitHub Releases. See
[release-flow.md](release-flow.md) for the source signature, reservation tags,
numbering, scan record and cleanup rules.

`tools/submit_copr.sh` intersects compatible candidates with the project's live
enabled chroots. An API read failure or an empty compatible list stops
submission; it never restores targets removed by the owner. Selected targets,
submission logs and scan records are delivery evidence. Package/RPM artifacts
are not retained in GitHub Actions.

For a new packaging number, use the workflow. Rebuilding an old source in COPR
keeps that source RPM's identity. Source tags are retained as reservations;
removing a GitHub Release must not erase numbering history. Repeated packaging
of one upstream version increments Release; a new version starts at 1.

## Targets

The earlier target snapshot in `packaging/targets.json` excludes EL7/EL8,
custom-1, Mageia 8/cauldron, Fedora 43, openEuler 20.03/22.03, 32-bit and ARM.
Fedora 45 is included. Live enabled targets are checked again at submission.
A candidate architecture alone is not evidence of runtime compatibility.

Remaining older EL9, Mageia 9 and openEuler 24.03 runtimes were classified as
incompatible with the inspected DEB's glibc >= 2.39 requirement. Dependencies
are not suppressed. x86_64_v2 targets would consume the same official amd64 app,
not an application rebuilt from source for v2. A successful bootstrap build
cannot prove graphical login/audio playback on each target distribution.

Live project API:
https://copr.fedorainfracloud.org/api_3/project?ownername=universish&projectname=Spotify..Client
