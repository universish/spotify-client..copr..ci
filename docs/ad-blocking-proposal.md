# Requested advertising-filter extension

Status: proposed scope; no advertising filter is currently implemented or enabled.

The owner requested automatic inclusion of an up-to-date advertising filter in
the local Spotify packaging flow, while retaining music playback. This request
has a direct conflict with the earlier requirement to comply strictly with
Spotify's terms. Spotify's [User Guidelines, prohibited activity 10](https://www.spotify.com/us/legal/user-guidelines/)
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
