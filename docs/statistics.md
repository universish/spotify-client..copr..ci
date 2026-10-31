# Download and usage statistics

The owner originally supplied a Spotify Developer dashboard URL. That dashboard
counts activity for applications using Spotify's APIs/SDKs; repackaging the
native desktop application does not make it use this project's Client ID.
Spot..Light adds no OAuth flow, API traffic or usage telemetry.

[Spotify application concepts](https://developer.spotify.com/documentation/web-api/concepts/apps)
explain the developer-app identity. No developer API or VirusTotal credential is
needed by the current package workflow. COPR submission uses `COPR_CONFIG`.

`tools/download_stats.py` reports GitHub RPM release-asset `download_count`
values and can render a saved JSON snapshot. Under the current policy, newly
published RPM assets may contain only the free installer, so their counters
measure installer downloads, not Spotify client downloads or active use.
The revised release workflow awaits verification. Removing historical assets
or releases removes their live counters. The tool must not be presented as a
client-usage or combined GitHub/COPR measurement.

COPR's repository-download figures are separate. Downloads can include repeats,
metadata or files fetched without an installation; they are not unique users,
installs or active listeners. No combined total is invented. Active usage would
require a separate, informed telemetry design; this project does not implement
one.
