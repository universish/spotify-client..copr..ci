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

The zicstardust/spotify-client project currently uses direct SRPM upload
(`source_type: upload`). This is the same technical mechanism supported here;
its presence is not evidence of a documented license exception. On 2026-10-27,
universish/Spotify..Client had the requested chroots enabled but no package source
entry yet. No project settings or remote builds were changed during preparation.

## Direct SRPM upload

Build and inspect the artifact first:

```sh
src/build_once.sh stable output
rpm -qpi output/spotify-*.src.rpm
```

After resolving the hosting constraint, configure `copr-cli` with your own
credentials from https://copr.fedorainfracloud.org/api/ (never commit them).
Submit only compatible, enabled targets, for example:

```sh
copr-cli build --chroot fedora-44-x86_64 universish/Spotify..Client output/spotify-*.src.rpm
```

The `Build scanned SRPM for COPR` GitHub workflow always builds the scanned SRPM
and saves it with the scan logs. Its submission input defaults to false. If you
choose to submit through that workflow, set the repository secret `COPR_CONFIG`
to the complete copr-cli configuration. It intersects the candidate target list
with the project's currently enabled chroots and waits for the remote result.

## SCM build option

Use Git URL `https://github.com/universish/spotify-client..copr..ci.git`, branch
`main`, repository root as subdirectory, and SRPM build method `make srpm`.
`.copr/Makefile` installs source-build tools and invokes the same mandatory scan
pipeline. Outgoing network is required during SRPM generation for Spotify and
ClamAV. Binary RPM rebuilds use the prepared tarball and need no internet access.
ClamAV CDN restrictions/rate limits are build failures, never a reason to skip
the signature update. CLAMAV_DATABASE_DIR can select a persistent local signature
directory to avoid unnecessary full downloads.

## GitHub secret and running the workflow

1. Log in at https://copr.fedorainfracloud.org/api/ and copy the complete generated configuration.
2. Open https://github.com/universish/spotify-client..copr..ci/settings/secrets/actions
3. Choose New repository secret, name it `COPR_CONFIG`, and paste the complete configuration as its value.
4. Open Actions → Build scanned SRPM for COPR → Run workflow. Enable `submit_to_copr` to submit.

The value has this shape (use your real generated values, not these placeholders):

```ini
[copr-cli]
login = YOUR_GENERATED_LOGIN
username = universish
token = YOUR_GENERATED_TOKEN
copr_url = https://copr.fedorainfracloud.org
```

The API page states tokens expire after 180 days. Replace the repository secret
when you renew the token. Do not put the token in workflow YAML or tracked files.
For local copr-cli use, save that same configuration in `~/.config/copr` with
permissions 0600. The workflow uses a temporary private file and removes it on exit.
No additional API key is needed for public project/chroot inspection.

## Current requested distributions and architectures

The updated user-requested list is in `packaging/targets.json`; all aarch64 entries
have been removed. GitHub Releases still produces only stable x86_64 RPMs. COPR
also permits the requested x86_64_v2 targets. Run `python3 tools/targets.py`.

* `candidate`: x86_64 or x86_64_v2 target with a plausible current runtime. A clean
  mock build, dependency transaction and graphical login/playback test are still
  needed before claiming support. Fedora 43 is included alongside 44/45/ELN/rawhide.
* `unavailable`: i386/i686. The official stable i386 index still contains legacy
  1.0.72.117.g6bd7cc73-35, while amd64 is 1.2.95.453.g0eeebbed. The current stable
  pipeline cannot produce a corresponding 32-bit binary and does not relabel the
  64-bit executable or silently substitute that old release.
* `incompatible`: the release's glibc ABI predates the current DEB's requirement
  of 2.39: EL7/EL8/EL9, Mageia 8/9 and openEuler 20.03/22.03/24.03. Package
  dependencies are not bypassed and no replacement system glibc is bundled.
* `unconfigured`: custom-1 needs an actual repository/buildroot definition.

The x86_64_v2 package uses the upstream amd64 binary; it is not a source rebuild
optimized for v2. Availability of EOL targets (especially CentOS Stream 8) and
vendor subscription repositories must be checked separately. Public COPR metadata
is used to intersect candidates with currently enabled project chroots at submission.

Upstream metadata:
https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages
https://repository.spotify.com/dists/stable/non-free/binary-i386/Packages
