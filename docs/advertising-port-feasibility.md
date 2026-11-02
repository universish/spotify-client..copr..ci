# Requested fixed-port separation: feasibility and delivery plan

Status: requested feature recorded; no selective Spotify port mapping is
implemented, verified or included in an RPM. This document does not substitute
a general proxy or status API for the requested advertising-only separation.

The owner subsequently asked to examine server IPs instead. See the
[read-only IP investigation](spotify-ip-investigation-2026-11-02.md).
Port remapping remains unimplemented; the IP research is not a proven substitute.

## Requested outcome

Before local Spotify packaging, provide stable, documented ports for advertising
traffic so an end user can optionally block those ports while ordinary music
playback continues. Automate preparation and verification in GitHub Actions.
The owner also requires Spotify-terms compliance and believes that making the
ports available without applying a block is compliant. That belief is recorded
as a requirement to verify, not as an established technical or legal fact.

## What is verified

| Port or mechanism | Meaning | Consequence for this request |
| --- | --- | --- |
| Remote service port | The endpoint on which a remote service accepts a connection | Repackaging cannot make Spotify's remote server listen on an arbitrary new port. A matching remote listener or a forwarding mechanism is needed. |
| Local client/source port | The local endpoint of a connection | Choosing its number does not identify whether the connection carries advertising, music or multiple resources. |
| Fixed local proxy/listener port | A locally controlled forwarding endpoint | A proxy can have a stable local port, but a selective advertising port first requires a reliable classifier or a supported separate upstream channel. Routing all Spotify traffic through it does not meet the music-preservation requirement when that port is blocked. |
| Spotify Connect ZeroConf port | A documented local device-discovery/login service | It is not evidence of an advertising channel and must not be relabeled as one. |

HTTP and HTTPS default ports are service endpoints, not content-purpose labels.
[HTTP semantics, RFC 9110 section 4.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-4.2)
defines the HTTP/HTTPS schemes. [HTTP/2, RFC 9113 section 5](https://www.rfc-editor.org/rfc/rfc9113.html#section-5)
permits multiple exchanges in one connection. Receiving data on a client-initiated
connection does not imply an unsolicited incoming advertising-server connection;
see the [TCP specification](https://datatracker.ietf.org/doc/html/rfc9293#section-3.9.1.1).

Spotify's [playback troubleshooting](https://support.spotify.com/us/article/spotify-not-playing/)
warns against a firewall blocking Spotify. Its [Connect ZeroConf guide](https://developer.spotify.com/documentation/commercial-hardware/implementation/guides/zeroconf)
documents discovery/login services. The official material examined does not
establish a supported advertising-only port for the closed Linux desktop
client. This is a bounded research result, not a claim that every possible
Spotify document or implementation has been examined. Older community claims
about port 4070 are not treated as a current advertising-port specification.

The subsequent local investigation sampled only Spotify-owned remote-peer
socket metadata in user-reported ordinary playback, advertising and resumed
playback windows. It did not capture packet contents or request URLs. Peer
endpoints first seen in the advertising window remained observable after
ordinary playback resumed. This neither identifies their payloads nor proves
or disproves an advertising-only service role; connections can remain idle.
Detailed observations remain local and are not included in this report.

No validated traffic classifier resulted from those observations. In particular,
this report does not assert that Spotify advertisements and songs always share
a hostname, IP address or exact connection. The engineering conclusion is
narrower: a port number alone cannot establish the requested classification or
guarantee that future music playback will remain unaffected.

## Local protocol counterexample

An isolated loopback HTTPS test served synthetic `/music` and `/advertisement`
resources over one persistent HTTP/1.1 connection. Both returned HTTP 200 and
had the same client/server address-port tuple. Therefore a predicate using
only those ports could not choose one resource while permitting the other.
The server used an automatically allocated loopback port and a temporary test
certificate trusted only by the test client; all sockets were closed afterwards.
Spotify was not run. No firewall, DNS, trust-store or package changes occurred.

The local reproducible script and result are under ignored
`output/port-feasibility-check/`. This is a synthetic protocol counterexample,
not a Spotify compatibility test, runtime feature or advertising blocker.

## Required implementation gates

1. Establish a supported way to distinguish the relevant traffic before mapping
   it to ports. Identify the exact source and ownership of the classification
   evidence: vendor-provided transport separation or a validated application
   integration. A port number, hostname substring, old forum post or unverified
   CDN list is insufficient. Do not invent advertising-server endpoints.
2. Resolve the compliance basis for an intentionally advertising-specific
   routing interface. [Spotify User Guidelines, activity 10](https://www.spotify.com/tr-tr/legal/user-guidelines/)
   address tools intended to block advertising as well as blocking itself.
   Our assessment is that facilitating selective blocking through special
   ports may still fall within that restriction. It is not established that
   merely leaving the final firewall decision to the user removes the issue.
   Obtain a verifiable permission basis covering the proposed integration;
   do not represent this interpretation as a specific Spotify ruling or a
   general assertion that port configuration is unlawful.
3. Choose the actual forwarding architecture only after the separation evidence
   is available. Preserve remote service compatibility, TLS verification and
   the original vendor-file hashes. Address IPv4/IPv6, HTTP/1.1, HTTP/2, QUIC
   where applicable, connection reuse, reconnecting and endpoint changes.
   Do not silently change global firewall, DNS or certificate configuration.
4. Validate each complete DEB version/SHA256 and relevant client/backend version
   independently for stable and testing. Demonstrate advertising routed through
   the assigned port while music and required control traffic remain elsewhere.
   Then verify uninterrupted decoded audio, track transitions, seek and reconnect
   with the advertising route unavailable in a consented isolated test setup.
   A synthetic protocol test or successful RPM build cannot establish this.
   Compare an unmodified-client baseline, mapping with all routes available and
   mapping with the advertising route unavailable. Proposed initial coverage is
   at least 30 minutes and ten track transitions per variant, with no new
   unexplained stall over five seconds and seek/reconnect latency no more than
   two seconds above baseline. Calibrate thresholds before accepting results;
   missing account, classification or decoded-audio evidence is not a pass.
5. Specify local-port allocation, collision handling, owner-only access, opt-in
   activation, diagnostics, disable/rollback behavior and archive isolation.
   Do not claim the feature is active on untested combinations. Preserve a
   clear distinction between mapping, blocking and unsupported classification.

## Proposed Actions automation after the gates are met

1. Use the existing twice-daily Stockholm source check and manual dispatch.
   Also detect changes to the authenticated mapping/adapter source. Pin its
   immutable revision and digest; reject unsigned/untrusted or replayed updates.
2. Authenticate and scan the two original DEBs in Actions as today. Validate
   the routing evidence/schema and the exact client/adapter combination before
   preparing any local-client packaging instructions containing the feature.
3. Build only reviewed freely licensed routing components. Run the real-client
   separation/playback tests above with sensitive account and traffic data kept
   out of public logs. Record which client, adapter and mapping were tested.
4. Stop feature promotion if classification, playback or compliance evidence is
   missing or fails. Actions cannot create a remote Spotify listening port or
   turn a failed compatibility claim into a successful one. Existing installer
   builds are independent; do not label them as implementing this feature.
5. Only after acceptance, extend the exact helper source/binary schemas and
   payload allowlists for the reviewed free files. Reserve ordinary revisions
   atomically, preserve historical identities, document the actual behavior
   and publish no DEB, extracted Spotify client or private client RPM.

No routing adapter, fixed advertising port, classifier, firewall rule, new CLI
option or Actions mapping job is activated by this plan. The remaining gates
are external integration/permission and real runtime evidence, not a missing
RPM macro or a number that can safely be hardcoded during packaging.
