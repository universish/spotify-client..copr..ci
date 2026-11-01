## Launch Spotify

After completing client setup and installation, start the Spotify GUI with:

```sh
spotify
```

The local client package is `spotify-client-via-spot-fly-light`. The `spotify`
command uses Spot..Light's consent checks and graphics configuration. Running
`spot..fly..light` without an option also launches the installed client.

## Command help

```sh
spot-fly-light --help
spot-fly-light -h
spot..fly..light --help
spot..fly..light -h
```

`--help` and `-h` are equivalent: they explain the available options without
starting Spotify, downloading a DEB or installing a package. `spot-fly-light`
and `spot..fly..light` accept the same helper options.

## Available client versions

```sh
spot..fly..light --client-versions
spot..fly..light -cl.ver
```

These equivalent commands show the installed helper's version and the exact
stable and unstable/testing Spotify versions it can install. They read the
helper's pinned catalog; they do not download or install a client. The package
description also lists both client versions:

```sh
dnf info spot-fly-light
```

## Common commands

| Command | Purpose |
| --- | --- |
| `spotify` | Launch the installed Spotify GUI. |
| `spot..fly..light` | Launch through the helper, using the installed channel. |
| `spot..fly..light --setup` | Review the notice, build and request installation of pinned stable. |
| `spot..fly..light --setup -unstable` | Set up the pinned unstable/testing client. |
| `spot..fly..light --update` | Build/install the stable client offered by this helper. |
| `spot..fly..light --update -unstable` | Build/install the unstable/testing client offered by this helper. |
| `spot..fly..light --debug` | Launch with detailed graphics and client diagnostics. |
| `spot..fly..light --safe-mode` | Launch using software rendering for graphics troubleshooting. |
| `spot..fly..light --status` | Show approval, build and installation readiness. |
| `spot..fly..light --install` | Retry installation of an already built, verified pending RPM. |
| `spot..fly..light --rebuild` | Build another local RPM of the selected pinned client. |
| `spot..fly..light --gpu-mode=MODE` | Choose a graphics profile: `auto`, `nvidia`, `mesa`, `software` or `native`. |
| `spot..fly..light --client-versions` or `spot..fly..light -cl.ver` | List both client versions this helper offers. |
| `spot-fly-light --help` or `spot-fly-light -h` | Explain options and usage. |

Run setup/update commands as your regular user, without `sudo`. Administrator
authorization is requested only for the package-manager transaction. `-unstable`
selects testing for setup, update, install or rebuild; it does not switch the
client merely by being added to a launch command.

`--update` uses the installed helper's pinned catalog. To obtain a newer catalog,
update the helper first:

```sh
sudo dnf upgrade spot-fly-light
```

Historical archive helpers have their own version-pair commands and fixed
catalogs. The common `spotify` command belongs to the current local client;
installing an archive helper does not replace it.
