# Download and usage statistics

The owner originally supplied a Spotify Developer dashboard URL. That dashboard
counts activity for applications using Spotify's APIs/SDKs; repackaging the
native desktop application does not make it use this project's Client ID.
Spot..Light adds no OAuth flow, API traffic or usage telemetry.

[Spotify application concepts](https://developer.spotify.com/documentation/web-api/concepts/apps)
explain the developer-app identity. No developer API or VirusTotal credential is
needed by the current package workflow. COPR submission uses `COPR_CONFIG`.

`tools/download_stats.py` is a legacy report utility for GitHub release-asset
`download_count` values. It can render a saved JSON snapshot, but the current
policy does not publish new GitHub Release RPMs. Removing historical assets or
releases removes their live counters. The tool must not be presented as a
current client-usage or combined GitHub/COPR measurement.

COPR's repository-download figures are separate. Downloads can include repeats,
metadata or files fetched without an installation; they are not unique users,
installs or active listeners. No combined total is invented. Active usage would
require a separate, informed telemetry design; this project does not implement
one.
