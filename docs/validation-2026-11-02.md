# Packaging and runtime validation

## Local verification

- All 242 regression tests passed on Fedora 44. The suite builds real current
  and archive helper SRPMs and binary RPMs and applies the strict public-payload
  gate. Test catalogs are synthetic fixtures and are never publication inputs.
- The frozen license evidence manifest and both RFC 3161 timestamp responses
  passed `tools/verify_license_evidence.sh`; those files were not changed.
- A copied installed RPM database was used for DNF solver checks with
  `--assumeno`, disabled system repositories, a local fixture repository and
  `tsflags=noscripts`. Its database SHA256 was unchanged afterwards. The host
  package database was never the transaction target.
- Both named and general upgrades selected only the current helper. An explicit
  archive install added a separate package without replacing the current helper.
  A private-client fixture with the verified previous package's exact EVR
  replaced that package; a mismatched EVR failed resolution. Client fixtures
  contain only synthetic MIT text, never Spotify application bytes.
- Native Fontconfig created genuine private caches, reused them on repeat
  execution and retained shared caches unchanged. Tests cover format 11/12
  headers, misleading format symlinks, optional broken includes and realpath
  deduplication. Pango rendered Turkish and CJK text using the private rules.
  This does not constitute an interactive Spotify/CEF rendering test.
- Ayatana's tray remains available. Its deprecation warning is an upstream
  Spotify ABI/API issue; it is not claimed to be eliminated.

Local build products and solver logs are excluded from version control.

## Current helper delivery

Commit `342958053f5b4b774823f343a3da2ba842715b4a` passed the then-current
240-test suite in Ubuntu [validation run 41357681934](https://github.com/universish/spotify-client..copr..ci/actions/runs/41357681934).
[Publication run 41357809613](https://github.com/universish/spotify-client..copr..ci/actions/runs/41357809613)
completed signed source selection, both mandatory malware scans, separate PUA
reporting, the strict pre-submission content gate, COPR, GitHub and cleanup.
[COPR build 11241791](https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/build/11241791/)
succeeded on all 17 submitted targets. The source RPM and actual Fedora 44
binary were downloaded afterwards; exact source/binary payload checks and signed
metadata replay passed without installing either package. The three
[GitHub assets](https://github.com/universish/spotify-client..copr..ci/releases/tag/spot-fly-light-v26.11.01-1)
were separately downloaded and their API digests, sizes, SHA256SUMS and full
publication gate passed.

| Delivered file | SHA256 |
| --- | --- |
| Source RPM (COPR upload and GitHub) | `6389aff7f43a28116b91618ab80812aa36c21b562d61c0b3d228d57b80922cb8` |
| GitHub Ubuntu-built x86_64 RPM | `39dc2119cd8eda03cbcfaf1eff96177d5307302d393179b4bd8e1fd911c6dd6d` |
| COPR Fedora 44 x86_64 RPM (`1.fc44`) | `a1d2a6f6d4b391346a193107862f9415d524be2c2a0f1db3c6fde62f20b5a894` |

The first archive attempt [41357892225](https://github.com/universish/spotify-client..copr..ci/actions/runs/41357892225)
stopped before reservation or download: a discovered archive Packages record
lacked a captured signed Release. The planner was corrected to retain a freshly
authenticated current-channel proof when all five immutable source fields match
the selected historical record exactly. A changed hash cannot borrow that proof;
two new regression tests cover this path. No authentication requirement was
relaxed, and that failed attempt published nothing.

## Archive delivery and independent verification

The corrected planner passed both Ubuntu validation runs
[41358539933](https://github.com/universish/spotify-client..copr..ci/actions/runs/41358539933)
and [41358540318](https://github.com/universish/spotify-client..copr..ci/actions/runs/41358540318).
[Archive publication 41358604583](https://github.com/universish/spotify-client..copr..ci/actions/runs/41358604583)
completed its 242 tests, signed source checks, both malware scans, separate PUA
reports, content gates, [COPR build 11241800](https://copr.fedorainfracloud.org/coprs/build/11241800),
GitHub publication and cleanup.

The [archive release](https://github.com/universish/spotify-client..copr..ci/releases/tag/spot-fly-light-st1.2.95.453-unst1.3.4.258-v26.10.31-1.1)
is marked prerelease and preserves the original `26.10.31-1` helper identity as
archive `26.10.31-1.1`. Its actual packaging timestamp is
`2026-11-01T23:48:43.748819+01:00`; it is not backdated to October 31.
The GitHub API still selects current `spot-fly-light-v26.11.01-1` as Latest.
Only two small free helper RPMs and SHA256SUMS are public archive assets.

| Archive asset | GitHub-reported SHA256 |
| --- | --- |
| SRPM | `4df1e1093887fbcd1481b10d046f9cf52b78d602afc8414969ad2ee4581ea03b` |
| x86_64 RPM | `46e6abba48b95656c808d931c5210452a5f85bbaa726a829a618dc74cb9a3f3c` |
| SHA256SUMS | `9fe72053c4411324d1ba2554ce53f6d0a7b7571edfd950dc1fda15cc8237cc94` |

The independent post-publication download was initially delayed because
automatic approval review was unavailable. It subsequently completed: the
actual COPR source/Fedora archive binary passed the exact payload gate and
signed metadata replay. The archive has precisely 16 allowlisted files, no
global `spotify` or current-helper command and no autostart/systemd files.
The three GitHub assets were independently downloaded, matched their API sizes
and SHA256 digests, and passed the full source/binary/SHA256SUMS gate. The COPR
source RPM hash also matches the GitHub SRPM above. The actual Fedora archive
binary (`1.1.fc44`) has SHA256
`c5b9e8993533840e02f592869cddd41b251282f5120a6d959124b21ec0627b06`.

A new local repository containing only copies of the two actual published
Fedora helper RPMs was checked against a read-only backup of the installed RPM
database. Named and ordinary upgrades selected the current helper only. Explicit
archive installation proposed one additional archive package with no removal or
replacement. Archive header/path isolation passed. All three DNF commands used
an explicit copied `--installroot`, disabled system repositories and plugins,
used only the local file repository, and stopped at `--assumeno` before any
transaction. The copied database SHA256 was unchanged:
`15cd5564b541858131c095acf9c3fa8a16c7f9f7f72addd0facabe9e90d8131f`.
Host packages and files were not transaction targets. Local evidence is under
ignored `output/delivered-dnf-verification-2026-11-02/`; these final solver
checks used real public free RPMs rather than the earlier synthetic fixtures.

A subsequent live read-only scheduled-plan check returned `needed: false`
before DEB download, scanning or reservation. The delivered current run's summary
was inspected in GitHub and contains the real stable and testing versions, with
no `1.2.3`/`2.0` fixture leakage. The delivered RPM's help and version aliases
produced identical outputs, and its RPM description lists both full source
versions and their client packaging revisions.
