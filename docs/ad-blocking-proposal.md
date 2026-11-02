# Requested advertising-filter extension

Status: proposed scope; no advertising filter is currently implemented or enabled.

The owner requested automatic inclusion of an up-to-date advertising filter in
the local Spotify packaging flow, while retaining music playback. This request
has a direct conflict with the earlier requirement to comply strictly with
Spotify's terms. Spotify's [User Guidelines, prohibited activity 10](https://www.spotify.com/tr-tr/legal/user-guidelines/)
expressly cover blocking advertisements and distributing tools intended to do
so. The owner must resolve which instruction takes priority before this feature
can be implemented. This is a contractual compatibility issue, not a claim that
every form of ad blocking is criminal or unlawful.

## Research and acceptance criteria if the scope is authorized

1. Examine maintained upstream implementations at immutable commits, their
   licenses and compatibility with each pinned Spotify/CEF version. The
   [abba23 project](https://github.com/abba23/spotify-adblock) describes filtering
   CEF URL requests; that is different from DNS filtering and is a candidate for
   investigation, not a verified integration in this repository.
2. Do not claim that DNS filtering can distinguish advertising from music on a
   shared hostname. The [AdGuard DNS limitations](https://adguard-dns.io/kb/adguard-home/faq/)
   explain this domain-level limitation. A community list's label is not proof
   that a rule preserves Spotify playback. Do not block entire Spotify/CDN
   domains based on a name or a substring alone.
3. Keep filtering scoped to the launched application. Do not change the user's
   global DNS configuration, `/etc/hosts`, certificate trust or firewall during
   RPM installation. Specify activation, diagnostics, rollback and removal
   behavior before implementation; keep the original vendor files verifiable.
4. Automate source/list update discovery in Actions with provenance and pinned
   hashes. Treat a list update as a candidate change requiring compatibility
   checks, rather than executing a remotely fetched installer or silently
   replacing rules at client startup.
5. Gate each supported client pair on playback, seeking, track transitions,
   login, reconnecting and failure behavior, alongside verification of the
   advertising requests actually affected. Synthetic URL tests alone do not
   establish working audio playback or complete ad removal.
6. Publish only freely licensed helper/filter components and metadata. Preserve
   the existing source authentication, Actions-only malware scanning, isolated
   archive identities and no-proprietary-payload publication gate.

No promise that all advertising can be removed without affecting music is made
without version-specific runtime evidence. Existing publications contain no
ad-blocking addition and retain their previously verified contents.

## Proposed automated delivery sequence

These steps are design work only. Implementation depends on resolving the
instruction conflict above; no new runtime option below exists yet.

1. **Discover candidate updates.** At the existing 12:00/17:00 Stockholm checks,
   detect both Spotify channel changes and changes to explicitly registered
   filter/rule upstreams. A manual workflow can request a candidate rebuild.
   Preserve immutable upstream commits and authenticated release identities;
   a self-reported hash from an untrusted list is insufficient provenance.
2. **Validate candidate rules and licenses.** Pin permitted source owners and
   HTTPS origins, reject unexpected redirects, and limit downloads to 1 MiB and
   10,000 rules initially. Parse a documented data-only schema: no commands or
   scripts in a rule bundle. Reject malformed URL patterns, broad parent/CDN
   blocks, duplicate/conflicting entries, older accepted revisions and equal
   revisions with different hashes. Record license text, rule digest and update
   evidence. An intentional rollback selects a previously authenticated bundle
   explicitly rather than disabling the replay check.
3. **Bind compatibility before packaging.** Create one reviewed matrix row for
   each supported full DEB version and SHA256, CEF version/ABI, filter source
   commit/build identity and rule-bundle hash. Stable and unstable are evaluated
   independently. An untested combination, including an old archive, must not
   silently inherit a newer filter: leave filtering off and explain that the
   combination is unsupported. Do not claim ad removal for that combination.
4. **Build and scan in Actions.** Download and authenticate the DEB in the runner,
   extract it without executing maintainer scripts, and build any proposed free
   filter from its pinned source. Record dependencies, source/license inventory
   and build hashes. Keep vendor payload files unchanged and hash-verifiable.
   The existing mandatory malware gate still blocks delivery; PUA stays a
   separate report. No Spotify application bytes enter public artifacts.
5. **Test the same client with filtering off and on.** Use a consented test
   account and actual decoded audio in an isolated test environment. Cover at
   least ten track transitions, seeking, pause/resume, queue continuity and
   reconnecting for each matrix row. Proposed initial thresholds: output/audio
   time advances during playback, no new unexplained stall longer than five
   seconds, and seek/reconnect latency no more than two seconds worse than the
   unfiltered baseline. Calibrate these thresholds against recorded baseline
   runs; do not fabricate a pass when account, audio or network evidence is
   unavailable. Record the advertising requests actually blocked separately.
   Redact account identifiers, tokens, cookies and private URLs from logs.
6. **Promote a tested immutable bundle.** Update the helper's pinned catalog only
   when the exact client/filter/rule tuple passes. Reuse atomic release-counter
   reservation; describe the feature and tuple in release notes. Explicitly add
   each reviewed free component to the existing exact source/binary allowlists
   and content checks; do not add a broad library/archive exception. Keep archive
   commands, rules, libraries and state isolated from current installations.
7. **Activate and recover locally.** Proposed CLI controls are
   `--ad-filter=on|off|status`, with a clear user-visible activation decision.
   Write bundles atomically, retain a last-known-good authenticated bundle and
   provide an immediate off switch. If hook loading or ABI validation fails,
   launch without the filter and report that ad blocking is inactive. Do not
   retry by changing system trust, DNS or the vendor executable. Removal must
   remove only this project's filter/configuration and preserve unrelated DNS
   settings. Client startup must never execute a remote update script.

DNS-only filtering remains a limited candidate for independently demonstrated
dedicated ad hostnames. It cannot satisfy the full requirement when advertising
and playback share a hostname; a domain list alone is not an accepted replacement
for the per-client audio and request-filtering checks above.
