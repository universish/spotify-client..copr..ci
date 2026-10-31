# Distribution and licensing decision

The current decision and checked legal sources are in
[legal-review-2026-10-30.md](legal-review-2026-10-30.md). The active runtime notice
and disclaimer are [bootstrap/NOTICE.txt](../bootstrap/NOTICE.txt) and
[bootstrap/DISCLAIMER.txt](../bootstrap/DISCLAIMER.txt). Root notice files remain
unchanged historical snapshots covered by the original timestamp evidence.

Spot..Light distributes a freely licensed, payload-free bootstrap through COPR.
The Spotify DEB is downloaded and scanned temporarily in GitHub Actions, and
its source hash/scan record is included in the bootstrap. The original app is
not included in the public SRPM/RPM. On the user's computer, that same DEB is
downloaded, hash-verified, unpacked and packaged locally after approval.
ClamAV is not installed or run on the user's computer.

The proprietary local target is `spot-fly-light-client-local`. It is not uploaded to
COPR/GitHub by this workflow. The local build follows the architectural idea of
LPF without using the actual LPF framework. LPF's own license or the RPM Fusion
bootstrap reference license does not license Spotify or every inherited file.
New helpers have the scoped MIT grant described by [LICENSE](../LICENSE).

The earlier direct-client release assets and two corresponding Actions ZIP
copies were removed during the prior migration. The current policy also stops
GitHub Release RPM publication and removes remaining release assets; live
cleanup/build evidence belongs in [validation.md](validation.md), not in a
blanket claim that a policy file proves external-state cleanup.

Preserving bytes, scanning, attribution, a timestamp and consent do not create
rights to redistribute Spotify. Hosting on COPR does not shift the maintainer's
responsibilities to Fedora or eliminate the user's own obligations. The current
neutral package names and prominent unofficial notice reduce confusion; no
claim is made that merely using a descriptive historical name establishes an
infringement or that a new name has undergone global trademark clearance.
