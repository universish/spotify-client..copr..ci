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
