# LPF framework comparison

Reference read in full: [leamas/lpf README](https://github.com/leamas/lpf/blob/master/README.md).

These are distinct sources:

| Source | Role in this repository |
| --- | --- |
| leamas/lpf | Actual Local Package Factory framework; design reference |
| rpmfusion/lpf-spotify-client | Spotify bootstrap/target specs; existing LPF license snapshot source |
| sergiomb2/spotify-make | Reference for preservation of Debian application resources |
| bootstrap/spot..fly..light.py | Our independently authored, standalone local builder |

The archived `licenses/LPF-bootstrap-LICENSE.txt` comes from the RPM Fusion
Spotify bootstrap, not the LPF engine. Its pinned source link is in LICENSE.txt.
The framework has its own [MIT license](https://github.com/leamas/lpf/blob/master/LICENSE),
including Alec Leamas's copyright notice. No framework code is imported by this
review; the timestamped records are preserved without replacing their contents.

## Findings corrected

The framework separates approval, build and installation and compares the
installed target with the bootstrap version. Our approval was only bound to
the notice text. It is now also bound to the selected DEB hash, version and
packaging revision. A new package cannot inherit an old package's approval.

The launcher now checks the installed spot-fly-light-client-local version and revision.
A missing/outdated target is reported instead of running it as the current
client. `spot..fly..light --status` exposes approve-wait, build-wait, install-wait or OK. These are a
small standalone status interface, not the framework's full state machine.

A dialog process error was previously treated as user rejection. Only the
documented cancel result now requests removal; other failures stop without
inferring consent/rejection or uninstalling a package. Explicit rejection retains
the removal behavior requested by this repository's owner.

## Remaining architectural differences

A completed local RPM is retained with its digest, size, package context and
RPM identity. `spot..fly..light --install` retries only that verified artifact; it never
starts an unapproved download/build. `spot..fly..light --setup` can also resume it;
`spot..fly..light --rebuild` explicitly requests a fresh verified local build. Missing, changed or
wrong-context cache files cannot be installed through this retry path.

The real framework uses a dedicated pkg-build account/group, its own installed
package layout, lifecycle macros, GUI and notifications. Our builder runs as the
requesting unprivileged user and uses system authorization only for installation
or removal. It does not provide the same account separation, full lifecycle,
LPF notification service or dedicated build account. The independent desktop
chooser now offers the two pinned channels once per installer version and opens
a terminal for setup, with legal consent still separate. It does not provide
LPF's GUI/state machinery. It should not be described
as the actual LPF framework or equivalent isolation.

Adopting that framework is a separate packaging/dependency transition across the
supported distributions. It must retain the project's scanner gates and wrapper,
and cannot silently change existing users' groups or privileged configuration.
On 2026-10-30 the owner explicitly chose to retain this standalone builder,
correct its gaps and document these differences. It must not silently install
the LPF framework or change system groups as part of these fixes.

The upstream README warns that its system tests can remove installed LPF
packages. Those tests were not run on this computer. Regression checks use
synthetic data and mocked privileged operations; the working LPF installation,
user configuration and previous signed evidence are preserved.

## Spot..Light update to the original comparison

The bootstrap package is `spot-fly-light`, its command is `spot..fly..light`,
and its local target is `spot-fly-light-client-local`.
Stable and testing share one local target. Setup/update defaults to stable;
`-unstable` explicitly selects testing. Original LPF package names above in
source references identify those upstream projects rather than the new command.

Scanning now happens exclusively in the GitHub Actions VM. The free bootstrap
carries the selected source hash and CI scan record. The user's computer
downloads and verifies the same DEB, then packages it locally; it neither
installs nor runs ClamAV. Earlier validation notes about local scanning record
the previous implementation, not the current host behavior.
