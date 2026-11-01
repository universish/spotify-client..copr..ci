# Source registry and historical provenance

The executable allowlist is `src/source-registry.json`. This document explains
the evidence behind its roles; adding a URL to a history table does not enable
that source. Application binaries are absent from the repository and helper
RPMs. A publishing build must authenticate source metadata again and then
validate and scan the downloaded DEB on the Actions runner.

| Source | Ownership evidence | Permitted role | Authority limit |
| --- | --- | --- | --- |
| `download.spotify.com/debian` | [Spotify Linux download instructions](https://www.spotify.com/us/download/linux/) | Preferred current signed metadata and exact DEB bytes | A directory response alone proves neither channel membership nor package authenticity. |
| `repository.spotify.com` | [Spotify Linux download instructions](https://www.spotify.com/us/download/linux/) | Current signed metadata and exact DEB bytes | A 403 on the repository root does not describe the status of its specific signed metadata URLs. |
| `repository-origin.spotify.com` | [Vendor repository](https://repository-origin.spotify.com/dists/) | Alternate vendor metadata and exact DEB bytes | Metadata must pass the same pinned Spotify signature checks. |
| `download.spotify.com` explicit root aliases | [Spotify employee's documented backup link](https://community.spotify.com/forum/en/discussion/comment/7325365) | Exact registered DEB transport aliases, including the documented 1.2.74.477 backup | Bytes only. This is not another current metadata/channel authority; filenames are not guessed for arbitrary versions. |
| University of Groningen | [University mirror directory](https://deb.rug.nl/ppa/mirror/repository.spotify.com/) | Transport for an already authenticated exact DEB | The mirror cannot choose the current version or assign a channel. |
| Linux Mint via Silicon Hill / CVUT | [Linux Mint mirror registry](https://www.linuxmint.com/mirrors.php), [mirror operator](https://ftp.sh.cvut.cz/) | Signed distribution metadata and historical DEB transport | This is an official **Linux Mint mirror**, not a Spotify-owned server. Mint authentication is identified separately from Spotify authentication. |
| Linux Lite Hematite | [Linux Lite repository](https://repo.linuxliteos.com/linuxlite/), [signed suite metadata](https://repo.linuxliteos.com/linuxlite/dists/hematite/InRelease) | Signed distribution metadata and exact historical DEB transport for the registered suite | The current verified index contains 1.2.95.453. A retained old file on an unregistered or differently signed mirror index does not gain this authority. |
| Linux Lite university mirror | [University mirror directory](https://fosszone.csd.auth.gr/linuxlite/pool/main/s/spotify-client/) | Enabled bytes-only transport for independently authenticated exact sources | A retained DEB filename or HEAD response is insufficient. It cannot select current versions or authenticate channel metadata. Old Galena metadata is not enabled under an unreviewed old key pin. |
| Internet Archive | [Archived vendor stable index catalog](https://web.archive.org/cdx/search/cdx?url=repository.spotify.com/dists/stable/non-free/binary-amd64/Packages&output=json&filter=statuscode:200&collapse=digest&fl=timestamp,original,digest), [testing index catalog](https://web.archive.org/cdx/search/cdx?url=repository.spotify.com/dists/testing/non-free/binary-amd64/Packages&output=json&filter=statuscode:200&collapse=digest&fl=timestamp,original,digest) | Discovery and transport of historical vendor metadata | Archive timestamps are observations. Actual signed vendor metadata, valid keys, and matching index digests are still required. |

The registry pins the Spotify fingerprint
`E1096BCBFF6D418796DE78515384CE82BA52C83A` and Linux Mint fingerprint
`302F0738F465C1535761F965A6616109451BBBF2`. Keys are supplied as payload-free
source-authentication material. Their current validity, signature validity,
expiration and revocation status are checked by the verifier; a successful
`gpgv` process alone does not establish the complete policy.

The registered Linux Lite Hematite primary key is
`CB38D02B85C9274CB13041B57F2B3FFE35099647`; its reviewed signing subkey is
`292C379F4AADCF2D4D5C7920B26492090E1E9344`. Galena's differently signed
metadata remains excluded: locating an old public key on a keyserver does not
independently establish that its full fingerprint is an authorized distribution
pin. The current signed keyring package does not contain that old key.

## Verification chain

1. Select a registered source and a permitted suite/index path. Reject arbitrary
   URLs, redirects to unregistered hosts, traversal, unsupported architectures,
   oversized metadata and ambiguous source identities.
2. Validate an actual `InRelease`, or actual `Release` plus `Release.gpg`, against
   the pinned permitted key. Historical archive captures use actual recorded
   signature URLs; the Packages capture timestamp is never substituted to
   fabricate an existing signature capture.
3. Verify the authenticated Release document's exact index byte length and
   digest. Locate the package's full raw Debian version, architecture, filename,
   size and digest in that index.
4. Download only that DEB identity, verify its full byte length and digest, and
   run the Actions malware scan. A successful HEAD is only a transport hint.
5. Preserve whether the authority was Spotify or a named distribution. If both
   independently authenticated sources identify the same version with
   contradictory bytes, stop rather than silently downgrade the authority.

For example, the current [Mint Virginia import index](https://ftp.sh.cvut.cz/mint/dists/virginia/import/binary-amd64/Packages.gz)
identifies `1:1.2.63.394.g126b0d89`, SHA256
`99c229f829ccb9c2a188be80d1241d2b8c8fd35f1e8d773438c0f612d68e940e`,
147984434 bytes. Its relative path is
`pool/import/s/spotify-client/spotify-client_1.2.63.394.g126b0d89_amd64.deb`.
This matches an independently observed historical Spotify stable record. Fresh
validation is still mandatory; this paragraph is not a trusted build cache.

## Version history is not release chronology

`data/spotify-history.json`, its CSV export, and
`docs/spotify-version-history.md` distinguish package-index records from
unclassified discovery hints. Full Debian epochs, revisions, commit hashes and
legacy build suffixes are preserved. The public archive helper name alone
uses four-component numbers, for example
`spot-fly-light-st1.2.63.394-unst1.2.86.502`.

An archive capture proves that a record was observed in a named index at that
capture. It does not establish the first public release time. Mirror mtimes,
Release metadata dates, package maintainer commits and Spotify's multi-platform
CEF table are also not substituted for an application release date. A version
can legitimately appear in both channel histories at different observations.

Automatic historical pairing requires a separately reviewed pair with cited
evidence in `reviewed_pairs`. When chronology cannot be established, the owner
must explicitly supply the other channel's version. A distribution-only record
with no independent Spotify channel evidence also needs an explicit channel
assignment. Both decisions remain labeled manual in release metadata.

The history collector reads bounded metadata only. Successful archived requests
and failed attempts are retained under ignored
`output/spotify-history-evidence/`; the checked-in catalog records coverage
failures. Rerunning can reuse already retrieved archive bodies and retry gaps.

## Candidates that do not establish an enabled fallback

The Spotify Open Source CEF table, LPF changelog and AUR commit history help find
versions, but a version string there does not prove a particular Debian
package's channel, checksum, availability or compatibility. They remain
discovery hints until stronger package metadata is available.

No exact `spotify-client` package was established in the official Debian or
Ubuntu package searches. Pardus/MX source candidates remain disabled until a
specific signed package record and pinned valid key can be verified. A
certificate hostname failure is not bypassed to retrieve a package. Genua and
other directory mirrors are not added as version authorities solely because a
filename exists.

Historical Qt/native package layouts are research entries only. The current
Chromium local builder rejects unsupported layouts instead of presenting an
unverified old application as a working installation option.
