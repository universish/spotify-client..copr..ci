#!/usr/bin/env bash
set -euo pipefail
output=${1:?Output directory required}
version=${2:?Spotify version required}
mkdir -p "$output"
cat > "$output/spotify.appdata.xml" <<APPDATA
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>spotify.desktop</id>
  <launchable type="desktop-id">spotify.desktop</launchable>
  <name>Spotify</name>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>LicenseRef-proprietary</project_license>
  <url type="homepage">https://www.spotify.com/</url>
  <url type="help">https://community.spotify.com/t5/Desktop-Linux/bd-p/desktop_linux</url>
  <summary>Music and podcasts</summary>
  <description>
    <p>Listen to music and podcasts with Spotify's official Linux desktop client.</p>
  </description>
  <releases><release version="${version}" date="$(date +%Y-%m-%d)"/></releases>
</component>
APPDATA
