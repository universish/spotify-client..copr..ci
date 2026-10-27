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
