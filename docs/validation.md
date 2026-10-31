> Historical validation record. Dates, former package names, scans and public
> releases below describe the implementation that existed at that time. They
> are not current install instructions or evidence that a later naming transition
> has been published. Current behavior is documented in `release-flow.md`; ClamAV now
> runs in Actions only. New remote results should be appended after verification.

# Validation evidence — 2026-10-27

The official stable `spotify-client_1.2.95.453.g0eeebbed_amd64.deb` was downloaded
and its 171,638,972-byte size and SHA256 verified against Spotify's repository:

`256e2eb1ec96fbc0c51afab247298e4e6eabfabbafafd4617584f44cca2fb31f`

Freshclam updated daily to 28166, main to 63 and bytecode to 339. The extracted
payload and Debian control files were scanned with ClamAV 1.4.6: 117 files,
552.41 MB scanned, zero infected files. No Debian maintainer scripts were run.
The raw updater/scanner reports are in the local `output/scan-reports` directory.

The scanned source tarball was rebuilt locally with packaging revision 2 and produced:

* `spotify-1.2.95.453.g0eeebbed-2.src.rpm`
* `spotify-1.2.95.453.g0eeebbed-2.x86_64.rpm`

RPM queries confirm `Name: spotify`, architecture `x86_64`, no distribution tag,
the vendor's `glibc >= 2.39` requirement, and automatically generated ELF library
and symbol requirements. Private bundled library provides are filtered. The
launcher, native executable and shared libraries are owned by root with mode
0755. There is no post-install script making application data world writable.
The package digest verification returned `digests OK`; the RPM is not signed.

All 12 regression tests pass. Bash syntax, workflow YAML and embedded workflow
shell syntax checks pass, as does `git diff --check`. Tests cover native exit
codes and argument boundaries, XDG paths with spaces, private debug logs, literal
environment assignments, package index boundaries and failed ClamAV gates.

This local build used Fedora 44. The independent Ubuntu GitHub Actions run
40564866938 also completed successfully: signature update, extraction/scan,
source RPM, binary RPM, validation artifacts and stable GitHub publication.
Packaging revision 3 adds the refreshed COPR matrix and x86_64_v2 eligibility;
its source preparation, scan and binary build passed in run 40565535788:
117 files scanned, zero infected files, and both revision-3 RPM artifacts written.
The same amd64 binary is used on v2 targets.
Graphical login, audio playback and clean dependency transactions on every listed
distribution have not been confirmed. COPR remote publication was not performed.
No private Spotify Developer credentials were read or added.


## LPF compatibility and bootstrap work (2026-10-29)

The original LPF DEB 1.3.4.258.gc60b10b0946a was verified against official
metadata. Mandatory ClamAV scan passed; PUA.Win.Trojan.Xored-1 was separately
retained as advisory. The reference SRPM and x86_64 RPM built locally. Both
RPM %check and a subsequent extraction/hash-manifest check preserved every
listed vendor file. No application was installed or launched by those checks.

A payload-free bootstrap SRPM and binary RPM also built locally. Its RPM file
list contains only the public launcher, source metadata, Python/shell helpers,
and legal notices. The standalone bootstrap's local-target path subsequently completed with the
same verified LPF DEB: ClamAV main 63, daily 28168, bytecode 339, normal malware
scan clean and PUA-only advisory. spotify-client-local-1.3.4.258.gc60b10b0946a-1
x86_64 RPM was produced and rpm -K returned digests OK. That test used the
pre-install implementation and did not install the target on this computer.

64 regression tests passed, including terms refusal, root-build refusal,
wrong-cache rejection, untrusted metadata rejection, GUI cancellation, scoped
local-target removal, and clearing prior consent on removal failure. GUI
behavior is simulated by subprocess fixtures; a physical desktop consent dialog
and privileged package-manager installation have not been exercised. These
checks do not establish clean install/playback on every target distribution. Validation logs remain under output/.

Review-branch commit e1cb7e4 passed GitHub Validate packaging run 40917710557.
Publication was initially held pending approval. After explicit approval,
main fast-forwarded to 8d026e4 and the payload-free workflow was manually
started from the review branch through the authenticated GitHub UI. API dispatch
and Actions artifact deletion returned 403 with the available Git credential;
no credential permissions were expanded.

Actions run 40919031213 completed detect, build, COPR and publish successfully.
COPR build 11227671 reports succeeded for all 17 submitted compatible targets.
Public stable release v1.2.95.453.g0eeebbed-4 contains:

* spotify-1.2.95.453.g0eeebbed-4.src.rpm: 23,275 bytes.
* spotify-1.2.95.453.g0eeebbed-4.x86_64.rpm: 23,419 bytes.
* SHA256SUMS.

The uploaded COPR source RPM was independently downloaded and its source tarball
inspected: precisely eight allowlisted helper/notice/metadata files, no vendor
application tree or ELF payload. Content hashes are retained locally in
output/delivered-bootstrap-4/source-content-audit.json.

The four former direct-client release RPM/SRPM assets were removed, their tags
retained and release descriptions marked retired. With additional explicit
approval, package ZIP artifacts 12762506955 and 12763635337 were deleted through
the authenticated GitHub UI. Fresh API listings confirm only metadata,
validation logs and download statistics remain for both old runs. The public
bootstrap release and its current package artifacts were not removed.


## Sonicradle delivery verified — 2026-10-30

The source transition was committed and pushed to both main and the review
branch. Code at `afb993906520218489a2a20daa8627324586e024` passed 102 tests.
The earlier user-authored README and bilingual notice contributions remain in
Git history; the current notice preserves their wording with the necessary
name and scan-location corrections.

[Actions run 41073185870](https://github.com/universish/spotify-client..copr..ci/actions/runs/41073185870)
completed successfully, including CI scanning, bootstrap construction, COPR
submission/wait and unconditional cleanup. It ran ClamAV 1.5.4 with database
28169. Both stable and testing passed the mandatory malware scan. PUA-only
warnings were recorded separately as advisory, consistent with the selected
policy. No ClamAV process or installation was used for the end-user build.

[COPR build 11231606](https://copr.fedorainfracloud.org/coprs/build/11231606/)
succeeded for the 17 selected enabled compatible targets. The submitted
`sonicradle-1.2.95.453.g0eeebbed-6.src.rpm` was downloaded from COPR and its
SHA256 matched the Actions `SHA256SUMS` entry exactly:
`916f520da2633acd6093c794bf31bf5990fea4c5466dbf7841af2208ff4024b1`.
Its source archive contained exactly seven allowlisted files: launcher, GPU
helper, two notices, copyright record, helper license and source catalog.
No application payload, vendor icon, DEB or local scan script was present.
The delivered launcher SHA256 matched the Git source exactly.

The Fedora 44 binary was downloaded through the repository primary metadata,
and both the metadata checksum and package checksum matched. `rpm -Kv`
validated its OpenPGP signatures and payload digests with key fingerprint
`f74d6e06914d8c3975cd0751d364643f98a68580`. The package was 25,049 bytes;
SHA256 `9f945436801b54cdad9d2f8b9711b772bb526dd42e977512bb46de8df3cdd920`.
Its file list contained only the community bootstrap, and its runtime
requirements contained neither freshclam nor clamscan. The binary's embedded
catalog matched the submitted source catalog exactly.

The catalog pinned stable `1.2.95.453.g0eeebbed`, revision 6, and testing
`1.3.4.258.gc60b10b0946a`, revision 1. The unused reservation 5 records a failed
CI attempt, so delivery uses 6 without rewriting a reserved tag. A failed
reservation does not consume testing's initial client revision.

Developer verification then used the delivered launcher's actual build body
for each channel, with the installation callback replaced by identity/hash
inspection. It did not create a user consent record, install either package,
launch vendor code or run a local antivirus scan. The official sources were
verified against the successful CI scan catalog before extraction. Both RPM
`%check` stages validated 114 original vendor-file hashes and private bundled
ELF libraries did not leak into global RPM provides:

| Channel | Local package | SHA256 |
| --- | --- | --- |
| stable | sonicradle-client-local-1.2.95.453.g0eeebbed-6.x86_64.rpm | 67574b0236bffe7ee69b72290bae7dd2affcf339ced0daa660dcbfaea3d81296 |
| testing | sonicradle-client-local-1.3.4.258.gc60b10b0946a-1.x86_64.rpm | d7e208515b4056ad0c6971089d53866d3549004f533acd602b2a530dc94f3455 |

These client RPMs remain private local verification output and were not
uploaded to COPR, Releases or Actions artifacts. No graphical launch or
end-user installation across the supported distributions is claimed here.

The retained Actions artifact `sonicradle-validation`, ID 12986083420, was
7,594 bytes. Its ZIP digest matched the API digest
`099cb85a81c3aef2db984bb5f51582ee34bcf6cddde24abecf089479ca6c3972`.
The ZIP contained 12 entries: scan reports, build/COPR logs, checksums, selected
targets and source metadata. There were no RPMs, DEBs or application archives.
Cleanup ran before artifact upload. The hosted job then completed;
[GitHub provisions a fresh VM per job for this runner type](https://docs.github.com/en/actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners).
Provider-level teardown/backup erasure is not independently audited by this
project.

A subsequent real-source scheduled planner dry run returned `needed: false`
after matching both upstream source identities to the successful COPR delivery;
it stopped before DEB downloading, scanning, building or submission. Manual
repackaging and channel revision behavior are covered by the planner tests.

The preserved license manifest still passed all 23 file digests and both
OpenSSL timestamp checks. The unused inherited logo SVG was removed from the
current source tree; Git history was not rewritten.

### Completed legacy-host cleanup

After explicit confirmation, the -2, -3 and -4 Release records were deleted.
All three REST DELETE operations returned 204; an authenticated follow-up
Releases list returned an empty list, and the web page displayed that there
were no releases. The old payload-free RPM artifact 12917461854 from run
40919031213 was deleted through the authenticated web interface; the success
notice was visible, the artifact endpoint returned 404, and the repository
artifact list no longer contained any RPM archives. New scan/report artifact
12986083420 remained available. Git tags and COPR packages were preserved.
The older proprietary release assets and two proprietary Actions ZIP artifacts
had already been removed, as recorded in the historical validation above.

This verifies repository-controlled Releases assets and Actions artifacts; it
does not claim erasure of other people’s downloads or provider backups. The
new workflow creates neither GitHub Releases nor RPM artifact archives.

## Spot..Light delivery verified — 2026-10-31

The selected display name is **Spot..Light**. The RPM package is
`spot-fly-light`; its terminal command is `spot..fly..light`. Actual RPM builds
reject consecutive dots in the package name, and Git rejects them in tag refs,
so RPM identities and internal `spot-fly-light-v...` reservation tags use
hyphens. Command, desktop and configuration paths retain the selected spelling.
The historical Sonicradle evidence above is preserved without renaming its
artifacts or changing its hashes. Frozen license/timestamp evidence is unchanged.

Source commit `1c2f582ce63ebd17a4f6ef6e7abf525a84b2b2fd` was pushed to
`main` and `codex/spotify-automation-gpu`. All **112 tests** passed locally and
in both branch validation runs (`41151273756` and `41151273500`).
[Actions run 41151337784](https://github.com/universish/spotify-client..copr..ci/actions/runs/41151337784),
job `124388328633`, completed successfully, including transient-package cleanup.
[COPR build 11233588](https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/build/11233588/)
succeeded on all 17 selected compatible enabled targets.

The bootstrap is `spot-fly-light-1.2.95.453.g0eeebbed-8`. The earlier scheduled
Sonicradle delivery had already consumed revision 7; its reservation was not
rewritten or reused. The included source catalog pins stable packaging revision
8 and testing revision 2. Normal ClamAV 1.5.4 scans found zero infected files
for both original DEBs and extracted trees. The separate PUA passes recorded
`PUA.Win.Trojan.Xored-1` in `Apps/login.spa` as advisory, following the owner's
chosen policy. Source hashes remain the same as the earlier verified DEBs.
Scanning took place only on the Actions VM; the local helper has no ClamAV
installation or scan step.

The original uploaded source RPM was downloaded from COPR:

* Size: 27,028 bytes.
* SHA256: `4f5d80e6ef1cd64c825ad858e2adf73830daa6e7dc445d2bedae99a405916154`.
* Its checksum matches the new Actions `SHA256SUMS` report.
* Its archive has exactly seven allowed free helper/notice/catalog files:
  `spot..fly..light.py`, `spot..fly..light-gpu.sh`, `eula.txt`,
  `DISCLAIMER.txt`, `COPYRIGHT`, `MIT-new-contributions.txt` and `source.json`.
* The launcher bytes match the published source commit. No Spotify application,
  DEB, vendor icon or proprietary application archive is present.

The real Fedora 44 repository metadata resolved the new binary RPM:
`spot-fly-light-1.2.95.453.g0eeebbed-8.fc44.x86_64.rpm`.
Its size is 25,695 bytes and SHA256 is
`f2d972bdb2bc6cfe2c21ebe10deef226cf1a97169c326f941ee7aa0311928363`.
`rpm -Kv` verified the header/payload digests and COPR OpenPGP signatures using
the already trusted key fingerprint
`f74d6e06914d8c3975cd0751d364643f98a68580`. No system key was imported.
The actual RPM contains `/usr/bin/spot..fly..light`, no ClamAV dependency and
no application payload. Its embedded source catalog matches the uploaded
source RPM and current scan run.

The retained report artifact is `spot..fly..light-validation`, ID
`13023053313`, 7,726 bytes, ZIP SHA256
`75082dd7f5ee6333bafeaac890e06d4d0b48af49b77d24e7ccbbc0704760b3ca`.
All twelve entries were inspected: scan logs, PUA reports, checksums, build/COPR
logs, target list and pinned source catalog only. It contains no RPM, DEB or
application archive. The report catalog matches the COPR source RPM.

A real post-delivery scheduled planner dry run returned `needed: false` for
the unchanged sources, stopping before download/scanning/build. GitHub's final
API audit at `2026-10-31T00:49:40Z` reported zero Releases and no RPM artifact
archives; the previously authorized legacy artifact deletion remains effective.

Migration checks cover old project processes, configuration fallback, legacy
GPU/debug environment keys and same-version private rebuild counters. RPM
replacement metadata covers only this project's former Sonicradle packages;
existing LPF/vendor packages are not silently obsoleted. Fresh consent is still
required for the new notice/source context.

### Private local client builds

Developer verification used the actual delivered helper's local packaging body
and genuine scan catalog from Actions run `41151337784`, with the final install
callback replaced by identity/digest inspection. No user consent record was
created; no package was installed, removed or launched. No ClamAV ran locally.
The stable DEB was downloaded and verified against the scan hash; testing used
the existing LPF DEB cache only after size/SHA256 verification. Both builds
preserved and checked all **114 original vendor files** in RPM `%check`, passed
RPM digest checks and excluded private bundled ELF library provides.

| Channel | Private RPM | Bytes | SHA256 |
| --- | --- | ---: | --- |
| stable | spot-fly-light-client-local-1.2.95.453.g0eeebbed-8.x86_64.rpm | 166599975 | 0508f8d4c1690382529575b0c93478c0c886db49bfb8ea6656f49db57d60124a |
| testing | spot-fly-light-client-local-1.3.4.258.gc60b10b0946a-2.x86_64.rpm | 173931817 | e151892fb5e4b79bf30901ecf1bd823db25f15c79c3b61efa822b870d4731f23 |

These private verification RPMs remain only in ignored local output. They were
not uploaded to GitHub, Actions artifacts or COPR. This packaging verification
does not claim an end-user installation or graphics runtime test on every GPU.
