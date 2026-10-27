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

## Requested distributions and architectures

Current scope is stable x86_64 only. The historical requested list is in `packaging/targets.json`, including targets
which cannot work with the upstream binary. Run `python3 tools/targets.py`.

* `candidate`: x86_64 target with a plausible current runtime. A clean
  mock build, dependency transaction and graphical login/playback test are still
  needed before claiming support.
* `unsupported`: aarch64; Spotify does not publish an arm64 Linux DEB. Renaming
  an amd64 RPM or using a multi-architecture container cannot change its ISA.
* `incompatible`: the release's glibc ABI predates the current DEB's requirement
  of 2.39, including EL8/EL9, Mageia 9 and openEuler 24.03. No glibc replacement,
  dependency bypass or obsolete Spotify release is bundled to conceal this.
* `excluded`: x86_64_v2; the current scope produces x86_64 RPMs only.
* `unconfigured`: custom-1 needs an actual repository/buildroot definition.

EL10's x86_64_v2 chroots can run an x86_64 payload but do not turn it into an
optimized v2 build. Availability of EOL targets (especially CentOS Stream 8) and
vendor subscription repositories must be checked separately.

Upstream metadata: https://repository.spotify.com/dists/stable/Release and
https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages
