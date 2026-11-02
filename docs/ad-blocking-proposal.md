# Extension API scope and advertising-blocking decision

Status: built-in advertising filtering declined by the owner. The requested
external-blocker API and advertising-specific port-separation proposals remain
unimplemented and subject to their documented permission/feasibility gates.

The subsequent fixed-port request and Actions automation plan are recorded in
[the port-separation feasibility report](advertising-port-feasibility.md).

## Owner decision — 2 November 2026

The owner chose to preserve compliance with Spotify's terms and not include
advertising blocking. The former filtering implementation proposal, proposed
`--ad-filter` controls and automatic rule-update work are withdrawn from the
implementation scope. The previous proposal remains available in Git history.
Existing helper/client packaging, scans and releases are unchanged.

The owner subsequently requested an API through which separately installed
advertising blockers could connect, without bundling a blocker in Spot..Light.
That request is recorded below; it is not treated as established permission to
implement a terms-compliant advertising-blocking integration.

## Requested advertising-blocker API: permission gate

Spotify's [User Guidelines, prohibited activity 10](https://www.spotify.com/tr-tr/legal/user-guidelines/)
cover blocking advertisements and creating or distributing tools intended for
that purpose. Our assessment is that an interface deliberately designed to
connect advertising blockers may fall within that restriction even when the
blocking code is distributed separately. Separation into another process,
package or plugin does not itself establish compliance. This is an interpretation
of the published restriction, not a claim that Spotify has issued a specific
ruling about this proposed API or that all advertising blocking is unlawful.

Before including an advertising-specific integration in implementation scope,
obtain a verifiable permission basis that covers both the interface and its
intended third-party integrations, such as Spotify's written authorization.
Record its scope and applicable conditions. A disclaimer, external distribution
or user opt-in alone is not substituted for that basis. Do not advertise such an
API as compliant while this requirement remains unmet.

No advertising interception hooks, request-cancellation interfaces, filter
callbacks, DNS/hosts changes, injected libraries, blocker discovery/installers or
automatic rule-update workflows will be added under the selected strict
compliance requirement without resolving this permission gate.

## Separate candidate: general local status API

A general-purpose API for helper metadata and installation status can be designed
separately. It is an alternative proposal, not an implementation of the requested
advertising-blocker connection and not an advertising-filtering workaround.
Its proposed requirements are:

1. A versioned, opt-in local interface, disabled by default. Consider structured
   CLI output before adding a daemon. If a persistent connection is needed, use
   a Unix-domain socket in a validated private user runtime directory with
   owner-only access; do not open a TCP port or expose it on the network.
2. Read-only operations such as helper identity, pinned stable/testing versions,
   source-verification summary and installation readiness. Reuse the existing
   CLI's data and behavior. Return bounded, schema-validated JSON and explicit
   API-version/error responses.
3. No Spotify passwords, tokens, cookies, playback URLs, network traffic, audio,
   listening/track data, advertising classification/signals or COPR/GitHub
   credentials. Status responses must not expose private paths, process
   environments, raw consent files, private logs or unrelated user data.
4. No arbitrary command execution, elevated package-manager operations, dynamic
   plugin loading/registration, rule loading, callbacks, library injection,
   launcher/environment mutation, DNS/proxy configuration or interception,
   modification, cancellation or replacement of Spotify requests. Even a
   read-only stream of Spotify request URLs or advertising events is excluded.
5. Tests for opt-in/disabled behavior, Unix-socket ownership and permissions,
   bounded requests/responses, absence of sensitive fields, current/archive
   isolation and clean shutdown/removal. Document that read access does not
   grant a way to control Spotify's advertising or traffic.
6. If this separate alternative is selected for implementation, keep its exact
   free files/dependencies in the existing public-payload allowlists and normal
   CI verification. It must not weaken vendor-file integrity checks or require
   publishing proprietary Spotify content.

This document updates the plan only. No API socket, HTTP service, CLI API option
or advertising-blocker adapter currently exists in the package. Existing
Spotify-specific behavior must not be described as globally or conclusively
terms-compliant merely because this particular feature is omitted.
