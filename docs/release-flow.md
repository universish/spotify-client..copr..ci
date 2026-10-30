# Version checks, CI scans and COPR delivery

## Schedule and source selection

The workflow requests checks daily at 12:00 and 17:00 in `Europe/Stockholm`.
GitHub manages daylight saving and may delay scheduled runs; this is not a
real-time delivery guarantee. Manual dispatch can repackage unchanged versions.
Code pushes run validation rather than publishing a package.

Official source metadata is checked first at `download.spotify.com/debian`,
then `repository.spotify.com`. Stable is the default channel; the explicit
`-unstable` client option selects Spotify's testing channel. RPM Fusion's
Fedora 44 release/updates/updates-testing and Rawhide packaging references are
checked last. They can identify newer LPF references but cannot override the
verified official DEB channel, filename, size or SHA256. Fedora stable does not
mean Spotify stable.

On 2026-10-30 the primary metadata URL returned 404, and the repository fallback
advertised stable `1.2.95.453.g0eeebbed` and testing
`1.3.4.258.gc60b10b0946a`. Directory-listing errors are not used as repository
availability checks. The signing-key URL supplied by the owner is not a package
index. No host APT sources or trust store is changed.

## Version identity and concurrency

The payload-free bootstrap is named `sonicradle`; it carries metadata for both
channels. Its RPM version follows the stable upstream version. The local target
is named `sonicradle-client-local` for both channels. A switch replaces that
single package instead of creating side-by-side stable/testing installs.

The planner compares the selected source signature with previously delivered
metadata. A scheduled check with an unchanged delivered signature stops before
build/scanning/COPR submission. A change to either channel requires a new
bootstrap so testing metadata does not become stale merely because stable has
not changed.

Packaging numbers increase for the same bootstrap version and start at 1 for a
new upstream version. Annotated, metadata-only reservation tags use
`sonicradle-v<stable-version>-<release>`. They are not GitHub Releases and do not
contain RPM downloads. An existing reservation is never rewritten; interrupted
attempts can leave numbering gaps. A shared concurrency group prevents parallel
scheduled/manual delivery from racing. COPR build history also informs the
counter and successful-delivery decision.

## Mandatory scan in GitHub Actions

The Actions VM downloads each selected official DEB, checks size and SHA256,
updates an isolated ClamAV database and raw-extracts the archive. Debian
maintainer scripts are not executed. The original DEB, extracted application
and control scripts are scanned with mandatory malware/heuristic signatures.
Malware findings, scan errors, encrypted/corrupt content and exhausted limits
stop delivery. A separate PUA pass permits only explicitly reported PUA-only
findings; a non-PUA result or scanner error in that pass remains blocking.

The bootstrap includes a CI scan record tied to each source SHA256, not the
DEB or extracted application. Scan records are statements produced by this
workflow, not a guarantee against unknown threats or a grant of legal rights.
The bootstrap archive is separately checked for its explicit free-helper allowlist; no vendor payload is included.

ClamAV is neither installed nor run on the user's computer by Sonicradle.
The user downloads the selected official DEB and verifies the same size/hash
before extraction and local RPM construction. A mismatched source is rejected;
the local builder cannot treat a different file as the previously scanned one.

## Delivery and cleanup

Only the payload-free bootstrap SRPM is uploaded directly to COPR. The workflow
waits for successful builds on the current compatible enabled targets. There is
no GitHub Release creation or RPM artifact publication. Metadata, scan logs and
attestation evidence can be retained as workflow artifacts; application payloads,
source/binary RPMs and extracted trees cannot.

An always-run cleanup removes temporary DEBs, unpacked application files, RPMs
and private COPR configuration on success or failure. GitHub manages teardown
of the hosted runner; a shell cleanup step cannot independently prove VM reset
or erase provider backups. The workflow does not claim to do so. COPR hosting
also does not transfer the uploader's obligations to Fedora.

## Local setup

`sonicradle --setup` selects stable; `sonicradle --setup -unstable` selects
testing. `sonicradle --update` returns to/currently selects stable, while
`sonicradle --update -unstable` selects testing regardless of the previously
installed channel. Launching `sonicradle` runs the installed choice. Source hash,
version, channel and packaging revision are bound to the approval/build context.

The original app tree and embedded notices are preserved. Local packaging uses
normal user privileges; system authorization is requested only for the final
package-manager installation/removal. Returning to stable can be a version
downgrade. No local result may be uploaded by the public delivery workflow.

References:

* [GitHub schedule syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
* [Spotify investor contact information](https://investors.spotify.com/resources/default.aspx)
* [COPR build and licensing rules](https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr)
