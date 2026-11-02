# Spotify endpoint IP investigation — 2 November 2026

The owner requested a read-only investigation of server IPs rather than port
remapping. No blocking, routing, proxy, DNS or client configuration was changed.

## Observation scope

The public table below contains DNS candidates, not a user traffic capture.
Spotify-process peer checks are performed separately; detailed session timing,
process identifiers and peer observations remain in ignored local output.
No application was launched by this investigation and no packet capture was
started. A DNS answer does not establish that a particular client used it.

The following is a public DNS snapshot from the machine's configured resolver,
started at **2026-11-02 14:30:15 UTC / 17:30:15 Europe/Istanbul**. A, AAAA and
CNAME records were queried without forcing another resolver. Role hints come
from the cited community-client maintainer source, not a Spotify promise about
the closed Linux desktop client's behavior.

| Hostname | Observed IPv4 | Observed IPv6 | Source-backed role hint |
| --- | --- | --- | --- |
| `apresolve.spotify.com` | `35.186.224.24` | `2600:1901:1:7c5::` | Endpoint discovery. |
| `ap.spotify.com` | `104.199.65.9` | No AAAA answer observed | Access-point fallback. |
| `dealer.spotify.com` | `35.186.224.39` | `2600:1901:1:292::` | Dealer/control fallback. |
| `spclient.wg.spotify.com` | `35.186.224.24` | `2600:1901:1:7c5::` | Metadata and audio-storage API fallback. |
| `login5.spotify.com` | `35.186.224.24` | `2600:1901:1:7c5::` | Login endpoint. |
| `clienttoken.spotify.com` | `35.186.224.24` | `2600:1901:1:7c5::` | Client-token endpoint. |

Observed A/AAAA TTLs ranged from 26 to 220 seconds. `spclient.wg.spotify.com`,
`login5.spotify.com` and `clienttoken.spotify.com` shared the CNAME target
`edge-web.dual-gslb.spotify.com`. `ap.spotify.com` used
`ap.single-gslb.spotify.com`, and `dealer.spotify.com` used
`global-dealer-ssl.spotify.com`. These are time/resolver-specific answers, not
permanent IP assignments or an exhaustive Spotify endpoint inventory.

## Routing ownership

RIPEstat's routing lookup returned **AS396982** for all five distinct addresses;
its AS overview names **GOOGLE-CLOUD-PLATFORM — Google LLC**. The observed
announced prefixes were `35.186.0.0/16`, `104.199.64.0/23` and
`2600:1901::/32`. Those prefixes are routing information, not Spotify-specific
or advertising-only ranges and must not be repurposed as a blocking list.

Primary routing observations:

- [AS396982 overview](https://stat.ripe.net/data/as-overview/data.json?resource=AS396982)
- [35.186.224.24 route](https://stat.ripe.net/data/network-info/data.json?resource=35.186.224.24)
- [35.186.224.39 route](https://stat.ripe.net/data/network-info/data.json?resource=35.186.224.39)
- [104.199.65.9 route](https://stat.ripe.net/data/network-info/data.json?resource=104.199.65.9)

Network ownership/ASN describes routing administration, not the purpose of an
individual request; see [RFC 1930 section 3](https://www.rfc-editor.org/rfc/rfc1930.html#section-3).
No location, advertising ownership or tenant exclusivity is inferred from it.

## Endpoint role evidence and limits

- [librespot endpoint resolver](https://github.com/librespot-org/librespot/blob/dev/core/src/apresolve.rs)
  uses `apresolve.spotify.com` for accesspoint/dealer/spclient discovery and
  contains the three fallback names above.
- [librespot login implementation](https://github.com/librespot-org/librespot/blob/dev/core/src/login5.rs)
  names `login5.spotify.com`.
- [librespot spclient implementation](https://github.com/librespot-org/librespot/blob/dev/core/src/spclient.rs)
  names `clienttoken.spotify.com` and uses spclient for metadata and audio-storage
  lookup. This does not establish an advertising-only service.
- The [abba23 configuration](https://github.com/abba23/spotify-adblock/blob/main/config.toml)
  identifies advertising patterns using URL paths under spclient hosts. This is
  third-party discovery evidence, not proof those patterns are correct for the
  owner's current client, nor an IP-exclusive advertising guarantee. No rules
  from it were installed or copied into a runtime configuration.

These are community-maintainer sources, not official Spotify integration rights.
Mutable source links may change; the locally saved research snapshot identifies
what was inspected. Public DNS data alone do not establish that any sampled
address carries only advertising, or that blocking it preserves playback.

## Finding and next evidence

Four different service names currently share the same IPv4 and IPv6 answers.
An address-level block of those sampled endpoints can therefore affect several
service names, including login and client-token paths suggested by the source
evidence. That is a risk inference, not a claim that every native-client session
uses these exact addresses or would fail in the same way.

Spotify-process-only socket observations must remain separate from DNS
candidates and record their timestamp, transport and remote address. Do not
publish private local addresses, session activity, account data, tokens or
playback URLs. Normal-playback and user-reported advertising observations can
be compared locally, but a peer's IP and an advertising-time coincidence alone
are not sufficient to classify it ad-only. Both advertising and ordinary
playback need independent role evidence before claiming separation.

Local raw DNS/routing results and process/socket observations are under ignored
`output/spotify-ip-investigation/`. No IP blocklist, fixed-port mechanism or
Actions traffic-classification job has been implemented by this investigation.

## Completed local comparison

The three user-reported phases—ordinary playback, advertising and resumed
ordinary playback—were compared locally. Endpoints first observed in the
advertising-aligned sample were still observable after playback resumed. An
established socket does not establish that payload is being transferred, so
this result neither assigns music delivery to those endpoints nor establishes
an advertising-only role. The samples are brief and do not identify exact
advertisement boundaries.

This comparison did not produce a validated advertising-only IP classifier.
The [port-separation implementation gates](advertising-port-feasibility.md#required-implementation-gates)
therefore remain unmet. No rule, port assignment or Actions mapping job may be
represented as validated on the basis of this comparison. Raw peer sets,
session timestamps and process identifiers remain outside version control.
