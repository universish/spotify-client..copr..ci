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
Manual release/COPR dispatch was rejected by automatic approval review because
of the prior review-only instruction; explicit publication approval is pending.
Main's old direct-payload workflow was confirmed by a read-only GitHub file
fetch. This review branch alone does not disable that workflow or remove old
payload-containing releases.
