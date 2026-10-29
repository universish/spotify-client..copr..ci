# Distribution and licensing decision

Reviewed 2026-10-29. This records engineering decisions and unresolved permission
questions; it is not a legal opinion or a guarantee against legal claims. A
qualified lawyer can assess the intended distribution and any permission letter.

## What the reference actually distributes

RPM Fusion's [bootstrap spec](https://github.com/rpmfusion/lpf-spotify-client/blob/master/lpf-spotify-client.spec)
packages a target spec, helper sources and terms. Its description calls the
Spotify target non-redistributable. The installed target spec separately declares
`No modification permitted, non-redistributable`. LPF builds the target on the
user's computer. The reference's bootstrap license does not license Spotify.

The former direct-client source and binary RPMs both contained the proprietary
application. The replacement bootstrap RPMs contain only free helpers and notices.
An SRPM is not an exception merely because its extension says source. Scanning,
preserving original bytes, attribution, charging nothing, and an EULA disclaimer
do not create redistribution permission.

## Permission boundaries

The current [Spotify terms](https://www.spotify.com/tr-tr/legal/end-user-agreement/)
restrict redistribution and reserve ownership and brand rights. The
[COPR rules](https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr)
require rights to upload material and accepted Fedora licenses. A Spotify
permission and a COPR exception, if applicable, are separate matters.

No Spotify redistribution permission has been supplied. The owner selected the
payload-free bootstrap model on 2026-10-29. The release workflow therefore uses
`tools/build_bootstrap.py`, whose explicit source allowlist includes only newly
authored helpers, metadata and notices. The proprietary client is downloaded,
scanned and built locally after consent; it is never uploaded by that workflow.
No blanket guarantee of legal compliance is inferred from this architecture.

The inspected inherited Git tree has no general license file. The LPF license
cannot be pasted over it. `LICENSE` limits the grant for new contributions;
`COPYRIGHT` retains origin attribution. A combined bootstrap cannot be declared
fully MIT until every included inherited file has a compatible permission basis
or is independently replaced. The unrelated downloaded GPL text is not used to
relicense this repository.

## Current delivery scope

The owner explicitly approved migration and cleanup. Main now contains the
payload-free bootstrap workflow. Release
[v1.2.95.453.g0eeebbed-4](https://github.com/universish/spotify-client..copr..ci/releases/tag/v1.2.95.453.g0eeebbed-4)
was produced by successful Actions run 40919031213 and COPR build 11227671
(17 selected targets). The uploaded source RPM was downloaded and inspected:
its source archive contains exactly eight allowlisted helper/notice/metadata
files, with no proprietary application payload.

The four direct-client RPM/SRPM assets in the -2 and -3 releases were removed;
the tags remain reserved to protect numbering history. The two corresponding
old Actions package ZIP artifacts (12762506955 and 12763635337) were also removed
with explicit approval and their absence verified on 2026-10-30. Their logs,
metadata and statistics remain available. Inherited generators with unresolved
licensing remain outside the distributed bootstrap source archive.

`eula.txt` is a third-party terms notice with current official links, not a new
Spotify contract. Original vendor notices are kept within the app tree. The bootstrap shows the notice and consent checkbox before local download/build.
RPM installation scriptlets never download or run proprietary code. Rejection
cancels launch/build and requests removal only of spotify-client-local through
system authorization; failure to authorize removal is reported explicitly.
