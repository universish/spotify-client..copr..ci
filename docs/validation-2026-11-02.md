# Packaging and runtime validation

## Local verification

- All 240 regression tests passed on Fedora 44. The suite builds real current
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

Local build products and solver logs are excluded from version control. Public
release verification must additionally pass on the Actions runner and COPR.
