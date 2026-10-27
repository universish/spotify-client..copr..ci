# Download and usage statistics

Requested Developer dashboard:
https://developer.spotify.com/dashboard/4b833db4e6454636b2d2aea2852385d5

A Spotify Developer application identifies calls made through the Spotify Web API
or SDKs. Repackaging the official desktop executable does not make it use that
application's Client ID. The official executable uses Spotify's own login and
application identity. An RPM cannot register downloads or desktop usage in this
Developer dashboard by adding its URL or Client ID. No API feature was requested,
so this fork introduces no OAuth flow, secret, token or synthetic API traffic.

Reference: https://developer.spotify.com/documentation/web-api/concepts/apps

`tools/download_stats.py` uses GitHub's documented release asset `download_count`
and generates an HTML table/bar chart plus its input JSON snapshot. It follows
pagination so old release downloads are included. `GH_TOKEN` is optional for
public repositories and is sent only to api.github.com. `--input FILE` renders an
already saved releases JSON response without networking.

Reference: https://docs.github.com/en/rest/releases/assets

The counters count file downloads, including repeats and source RPMs. They are
not install counts or unique/active users. COPR downloads are counted separately
on the COPR project's release table; self-hosted repositories can use their web
server's access logs. The report links to COPR rather than inventing a combined
counter. GitHub download counters are lost when assets/releases are deleted or
replaced, so automatic removal of old releases has been removed from this fork.

Active usage would require a separately designed, consent-based telemetry system
or application changes. It cannot be inferred accurately from package downloads.
The packaged launcher sends no usage statistics.
