# Stable version checks, malware gates and packaging numbers

## Schedule

The reference location is Spotify AB in Stockholm, Sweden, listed by Spotify at
https://investors.spotify.com/resources/default.aspx . The workflow uses
`timezone: Europe/Stockholm` and `cron: 0 12,17 * * *`: every day at local noon
and 17:00. Stockholm daylight saving is handled by GitHub's IANA timezone support:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule
GitHub may delay scheduled jobs during busy periods; these times are scheduler
requests, not a real-time delivery guarantee.

Only `schedule` and `workflow_dispatch` trigger publication. Code pushes still
run the separate validation workflow. A scheduled run reads the official stable
amd64 Packages index (download.spotify.com/debian first, repository.spotify.com
as the official fallback) and compares its upstream version with completed stable
GitHub releases and successful COPR uploads. If unchanged, it exits after metadata
checks; no DEB download, signature update, scan, RPM build or COPR submission runs.
A manual Run workflow always requests packaging of the current official stable
version, with or without a version change.

## Counter and concurrency

The visible RPM identity is `<upstream-version>-<packaging-number>`. For example:

* `1.2.95...-3` → manual rebuild → `1.2.95...-4`.
* New upstream `1.2.96...` → `1.2.96...-1`.

The planner reads all release pages, matching Git tags and paginated COPR build
history for that exact upstream version. Numbers for another upstream version
are ignored. Existing distribution suffixes are recognized. The highest existing
or reserved number plus one is used; numbers are never derived from run count,
lexical sorting or a fixed spec constant.

Before downloading/scanning, an atomic GitHub reference creation reserves
`refs/tags/v<version>-<number>` at the workflow commit. An existing reference is
never updated. A reservation collision advances to the next free number. Other
API errors stop the workflow. The shared concurrency group serializes scheduled
and manual executions. The reserved number becomes RPM `Release:` and the
source RPM is checked again immediately before COPR upload.

A failed or cancelled attempt leaves its reserved tag. It may produce a gap,
but its number is never reused: a partially successful COPR upload cannot collide
with a later attempt. Rerun the full workflow to get a new number. Rerunning only
a failed COPR/publish job intentionally retains its original source artifact and
number. Keep release tags even when deleting failed workflow runs.

## Scan and delivery gates

The source check first requests
`https://download.spotify.com/debian/dists/stable/non-free/binary-amd64/Packages`,
then falls back to
`https://repository.spotify.com/dists/stable/non-free/binary-amd64/Packages`.
The primary currently returns 404 while the fallback index works; directory
listing status is never used as an availability test. The public signing key
URL under download.spotify.com/debian is a key resource, not a Packages index.
No APT source or trusted-key files on the build host are modified.

The selected official HTTPS metadata supplies the filename, size and SHA256. That exact
record is pinned between jobs. After verification, freshclam updates isolated
official signatures. The DEB is then raw-extracted without running maintainer
scripts. The original DEB, unpacked files, control scripts, ELF binaries, supported
nested archives and optional additional codec libraries are scanned. PUA and
heuristic detection are enabled; encrypted content, broken executable alerts,
scan errors and exhausted limits block packaging.

ClamAV can detect known malware and backdoor signatures; a clean result is not
proof that every unknown or deliberately hidden threat is absent. No external
sample upload, private token or paid malware service is used.

Only a clean scan allows RPM/SRPM creation. COPR upload uses the current project
configuration and only compatible candidate targets; removed chroots are never
restored by the workflow. Submission waits for COPR. GitHub publication depends
on successful COPR completion. A failed scan/build/upload leaves evidence in
workflow artifacts and does not expose a new complete GitHub release.
