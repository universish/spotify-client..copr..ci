# License notices from the original Spotify DEB

Reference package: `spotify-client_1.3.4.258.gc60b10b0946a_amd64.deb` from the
installed LPF cache. This is an LPF/testing reference; the automated workflow
continues to follow the official stable channel. No DEB or application binary
is included here.

The entire cached DEB's SHA256 and size were checked against Spotify's official
[testing package index](https://repository-origin.spotify.com/dists/testing/non-free/binary-amd64/Packages).
`official-package-record.json` retains the selected official record;
`DEBIAN-control.txt` retains the original package metadata without executing it.

The original package's `License` field points to:
https://www.spotify.com/legal/end-user-agreement

No separate full Spotify proprietary license text was found among the
license/copyright/eula/doc entries of this exact package. The linked online
terms are maintained by Spotify and can change; this directory does not pretend
to be an authoritative copy of those terms.

`native-licenses.html` is a byte-for-byte copy of
`usr/share/spotify/Apps/native-licenses.html`. It contains licenses and notices
for bundled third-party components. Those grants apply to their respective
components; they do not license the whole Spotify client for redistribution.
`provenance.json` records the source DEB and embedded notice digests and the
license-related archive entries that were inspected. This documentation is
separate from the application resources preserved by the local RPM builder.
