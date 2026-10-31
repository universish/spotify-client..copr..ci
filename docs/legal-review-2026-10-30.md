# Current legal scope and naming review — 2026-10-30

This document records the project's distribution decisions and the boundaries
of the available evidence. It does not assert that every jurisdiction or every
possible use has been cleared. No written Spotify redistribution or trademark
permission has been supplied to this project.

## Current names

The community bootstrap is `spot-fly-light`; its terminal command is
`spot..fly..light`. The locally
generated proprietary target is `spot-fly-light-client-local`. The original
application remains Spotify's application, with its original ownership and
embedded notices. The former community name was Sonicradle. Those published records remain
historical evidence; the current project name is Spot..Light.
The new name is a precaution against presenting the community
helper as an official product; it is not evidence of registered or globally
exclusive trademark rights in the word Spot..Light.

`spotify`, `spotify-client` or `spotify-client-local` as an identifier does not,
by itself, prove a legal violation. The relevant context includes product
presentation, likelihood of confusion, the applicable terms and the law of the
relevant jurisdiction. The old names are retained in historical evidence rather
than erased from the record. Current package examples use `spot-fly-light`; command examples use `spot..fly..light`.

The COPR identifier `universish/Spotify..Client` is retained as a historical,
descriptive repository identifier with a prominent unofficial-project notice.
There is no demonstrated need to create a replacement COPR project solely
because of that identifier. This is an engineering choice, not trademark
permission from Spotify or a guarantee against a complaint. A request from a
rights holder or a host-policy determination would need a separate response.

## Sources checked

* [Spotify terms applicable in Türkiye](https://www.spotify.com/tr-tr/legal/end-user-agreement/),
  displayed update date 26 August 2025: personal-use scope, retained ownership,
  redistribution restrictions and reserved brand rights.
* [Spotify US terms](https://www.spotify.com/us/legal/end-user-agreement/),
  displayed update date 4 September 2026: a regional reference only, not a
  substitute for a user's own applicable agreement.
* [Spotify developer design and naming guidance](https://developer.spotify.com/documentation/design#logo-and-naming-restrictions):
  guidance for registered applications and integrations. This project does not
  gain a desktop redistribution license by registering a Developer app.
* [COPR upload rules](https://docs.copr.fedorainfracloud.org/user_documentation.html#what-i-can-build-in-copr):
  an uploader must have the necessary rights and use material with an accepted
  license. Build-service availability does not replace that assessment.

These are live documents and may change. Use the official regional links when
reviewing current terms. This review paraphrases selected issues; it does not
reproduce Spotify's contract or purport to amend it.

## Distribution boundary

The public source RPM contains only independently authored free helpers,
source metadata, scan attestations and notices from an explicit allowlist.
The build path must not upload the DEB, extracted application, proprietary
icons or a client-containing source/binary RPM to COPR or GitHub.

The CI scanner may temporarily download the official DEB and unpack it on the
GitHub-hosted runner for hash-bound scanning. It must delete those temporary
copies on completion/failure. The bootstrap carries the selected source hash
and scan record, not the application. On the user's computer, the helper
downloads that exact source and verifies its hash before local packaging.
ClamAV is not installed or run on the end-user computer by this workflow.

Keeping a client's bytes unchanged, scanning them and showing a notice do not
create permission to publicly redistribute them. GitHub Release RPM publishing
is disabled under the current delivery policy. Source tags may remain as
packaging-number reservations without containing downloadable RPM assets.

The local-build architecture removes the previous public-client delivery path.
It is not a claim that every local repackaging/use is expressly approved by
Spotify. Users must still comply with the applicable terms and law. There is
no confirmed new violation established merely by the remaining descriptive
references, but there is also no basis for promising universal legal clearance.

## Responsibility and consent

Fedora, Red Hat and COPR do not take over the maintainer's responsibilities
because they provide infrastructure. A user checkbox likewise does not shift
all responsibility to the user or remove mandatory rights. The maintainer
remains responsible for the material they upload and representations they make;
the user remains responsible for their own use and compliance obligations.

The notice is a request for informed local installation. It is not Spotify's
agreement, a rights-holder permission letter, a waiver of non-excludable
liability or an indemnity binding third parties. The active texts are
[bootstrap/NOTICE.txt](../bootstrap/NOTICE.txt) and
[bootstrap/DISCLAIMER.txt](../bootstrap/DISCLAIMER.txt).

## License evidence and historical notices

[LICENSE](../LICENSE) scopes the grant for new contributions. Inherited files
are not automatically relicensed because the repository is public or forkable.
GitHub itself gives public-repository users a limited right to view and fork
through the service, under [Terms section D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#5-license-grant-to-other-users).
The absence of a general upstream license therefore does not by itself show
that this GitHub fork is unauthorized. That service-level permission is not a
blanket MIT grant or permission to distribute inherited files through COPR.
The distributed bootstrap excludes inherited generators with unresolved grants.
The archived RPM Fusion bootstrap license applies to its corresponding material,
not to Spotify or every file in this fork. The actual LPF framework has a
separate license and is not silently bundled into this standalone installer.

The original root `eula.txt`, `DISCLAIMER.txt`, `LICENSE.txt`, `LICENSE` and
`COPYRIGHT` are part of the preserved timestamp evidence. Historical package
names or local-scan descriptions in those snapshots are not the active runtime
instructions. The active notice updates those operational details while
preserving the limits on rights and responsibility. It does not change the
scope of any original license or Spotify agreement.

The FreeTSA response and hash manifest establish evidence about specified
bytes at the recorded time, subject to validation and trust in the time service.
They do not establish copyright ownership, grant a trademark license, prevent a
rights holder from disputing scope, or convert third-party notices into a
license for the proprietary application.

## Corrections made in the current documentation

* Neutral community package/command names replace product-brand command names.
* The unused inherited logo SVG was removed from the current source tree.
  Original vendor icons are obtained only with the local client download;
  this change does not rewrite historical Git objects or tags.
* The COPR description identifies both the unofficial status and payload-free
  scope, and gives separate bootstrap/client operations.
* Hosting on Fedora infrastructure is not described as a liability transfer.
* Current notices identify CI scanning and local hash verification separately.
* PUA reports and a clean malware scan are not represented as proof of safety.
* Historical timestamped files are preserved; current runtime instructions have
  separate paths rather than silently changing the signed evidence.
* The origin account is credited without accusing the upstream maintainer of
  illegality, malware or unproven causes of UI defects.

Live cleanup/build results are operational evidence and should be recorded in
the validation log after verification. A policy document alone is not proof
that every remote copy has been removed.
