# Version checks, CI scans and COPR delivery

## Schedule and source selection

The workflow requests checks daily at 12:00 and 17:00 in `Europe/Stockholm`.
GitHub manages daylight saving and may delay scheduled runs; this is not a
real-time delivery guarantee. Manual dispatch can repackage unchanged versions.
Code pushes run validation rather than publishing a package.

The configured network source order is:

1. `https://download.spotify.com/debian` — official metadata and DEB source.
2. `https://repository.spotify.com` — official metadata and DEB source.
3. `https://repository-origin.spotify.com` — official metadata and DEB source.
4. `https://deb.rug.nl/ppa/mirror/repository.spotify.com` — an unofficial,
   byte-download fallback only, for the already pinned official filename.

Only the three official indexes determine channel, version, filename, size and
SHA256. Source discovery fails if all three official indexes are unavailable;
it does not trust a mirror's index or select an arbitrary mirror version. A
DEB fetched from the unofficial fallback must match the exact official size
and SHA256 before use. A valid private cache is checked first and avoids a
network download. RPM Fusion references remain the final advisory check and
cannot override official channel or source identity.

Stable is the default channel; the explicit `-unstable` client option selects
Spotify's testing channel. RPM Fusion's Fedora 44 release/updates/updates-testing
and Rawhide packaging references are checked last. They can identify newer LPF
references but cannot override the verified official DEB channel, filename,
size or SHA256. Fedora stable does not mean Spotify stable.

On 2026-10-30 the primary metadata URL returned 404, and the repository fallback
advertised stable `1.2.95.453.g0eeebbed` and testing
`1.3.4.258.gc60b10b0946a`. Directory-listing errors are not used as repository
availability checks. The signing-key URL supplied by the owner is not a package
index. No host APT sources or trust store is changed.

## Version identity and concurrency

The payload-free bootstrap RPM is named `spot-fly-light`; it carries metadata for both
channels. Its RPM Version is the packaging date in `Europe/Stockholm`, formatted
`yy.mm.dd`; its Release counts packaging attempts on that date. The installer
RPM description and `--client-versions` / `-cl.ver` expose both pinned client
versions separately. The catalog records installer identity under `Bootstrap`
and keeps stable/unstable upstream metadata distinct. The local target is named
`spot-fly-light-client-local` for both channels. A switch replaces that single package instead of creating side-by-side stable/testing installs.

The planner compares the selected source signature with previously delivered
metadata. A scheduled check with an unchanged delivered signature stops before
build/scanning/COPR submission. A change to either channel requires a new
bootstrap so testing metadata does not become stale merely because stable has
not changed.

The installer Release increases for the same packaging date and starts at 1
for a new date. This does not force a scheduled publication when both upstream
channel records are unchanged. Annotated, metadata-only reservation tags use
`spot-fly-light-v<yy.mm.dd>-<release>`. A reservation tag does not by
itself contain a package download. After verified delivery it may identify a
GitHub Release containing only the free installer RPM/SRPM and checksums.
Git reference names cannot contain `..`, so this internal
tag prefix matches the normalized RPM name `spot-fly-light`; the terminal
command retains the spelling `spot..fly..light`.
Existing reservation tags from previous project names remain
historical numbering evidence and are not renamed or rewritten. An existing reservation is never rewritten; interrupted
attempts can leave numbering gaps. A shared concurrency group prevents parallel
scheduled/manual delivery from racing. COPR build history also informs the
counter and successful-delivery decision. Client packaging counters are separate
from the date-based installer Release: each upstream channel version starts at
`-1` and counts delivered catalogs for subsequent repackaging. A failed
reservation does not consume that client version's initial `-1`.

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

ClamAV is neither installed nor run on the user's computer by Spot..Light.
The user downloads the selected official DEB and verifies the same size/hash
before extraction and local RPM construction. A mismatched source is rejected;
the local builder cannot treat a different file as the previously scanned one.

## Delivery and cleanup

Only the payload-free bootstrap SRPM is uploaded directly to COPR. The workflow
waits for successful builds on the current compatible enabled targets. After
success, GitHub Releases may publish only the verified free installer RPM/SRPM
and `SHA256SUMS`. The Spotify DEB, extracted application and private local
client RPM must never be uploaded as release assets. Source/license metadata,
scan logs and attestation evidence can be retained as workflow artifacts;
application payloads, RPM archives and extracted trees are excluded from
those report artifacts. The revised release workflow awaits remote verification.

An always-run cleanup removes temporary DEBs, unpacked application files, RPMs
and private COPR configuration on success or failure. GitHub manages teardown
of the hosted runner; a shell cleanup step cannot independently prove VM reset
or erase provider backups. The workflow does not claim to do so. COPR hosting
also does not transfer the uploader's obligations to Fedora.

## Local setup

After the installer is installed or updated, an active graphical user session
is asked which pinned client to install: stable or unstable/testing, with both
version numbers shown. Continuing opens a terminal and runs
`spot..fly..light --setup` or `spot..fly..light --setup -unstable` for the selected
channel. The legal notice still requires your separate approval. Cancel closes
the chooser without downloading or building and dismisses it for that installer
version; the commands remain available manually.

The popup runs as the desktop user, not inside a privileged RPM scriptlet.
If no usable desktop session is available at installation, it is deferred until
the next graphical login. Each desktop user is prompted once per installer
Version-Release. For a terminal-only installation, use the setup commands below.

The host checks its private hash-keyed DEB cache before network fallback and
fully verifies size/SHA256 before every reuse. Progress output includes stage
completion counts/percentages, elapsed-time heartbeats, download percentage,
speed and estimated remaining time, hash progress and live RPM build output.
Stage percentages count completed operations; they are not a time estimate.
Local stage and RPM details remain in `setup-progress.log` and `rpm-build.log`.


`spot..fly..light --setup` selects stable; `spot..fly..light --setup -unstable` selects
testing. `spot..fly..light --update` returns to/currently selects stable, while
`spot..fly..light --update -unstable` selects testing regardless of the previously
installed channel. Launching `spot..fly..light` runs the installed choice. Source hash,
version, channel and packaging revision are bound to the approval/build context.

The original app tree and embedded notices are preserved. Local packaging uses
normal user privileges; system authorization is requested only for the final
package-manager installation/removal. Returning to stable can be a version
downgrade. No local result may be uploaded by the public delivery workflow.

References:

* [GitHub schedule syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule)
* [Spotify investor contact information](https://investors.spotify.com/resources/default.aspx)
* [COPR build and licensing rules](https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr)
