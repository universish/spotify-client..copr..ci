#!/usr/bin/env python3
"""Render GitHub RPM asset download counts. Counts are not active users."""
import argparse
import datetime
import html
import json
import os
import re
from pathlib import Path
from urllib import request


def fetch_releases(repository):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "spotify-rpm-download-report"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    releases = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}"
        with request.urlopen(request.Request(url, headers=headers), timeout=60) as response:
            batch = json.load(response)
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def render(releases, repository):
    rows = []
    for release in releases:
        for asset in release.get("assets", []):
            name = asset["name"]
            if name.endswith(".rpm"):
                rows.append((release["tag_name"], name, int(asset["download_count"])))
    maximum = max((r[2] for r in rows), default=1) or 1
    table = "".join(
        f"<tr><td>{html.escape(tag)}</td><td>{html.escape(name)}</td><td>{count:,}</td>"
        f'<td><div class="bar" style="width:{count / maximum * 100:.2f}%"></div></td></tr>'
        for tag, name, count in sorted(rows, key=lambda r: r[2], reverse=True)
    )
    if not rows:
        table = '<tr><td colspan="4">Henüz yayımlanmış RPM dosyası yok.</td></tr>'
    total = sum(r[2] for r in rows)
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    return f'''<!doctype html>
<html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spotify RPM indirmeleri</title>
<style>
body{{font:16px system-ui,sans-serif;background:#101714;color:#e7eee9;max-width:1100px;margin:48px auto;padding:0 24px}}
h1{{font-size:2rem}}.total{{font-size:3rem;color:#82e8ad;margin:16px 0}}a{{color:#82e8ad}}
table{{border-collapse:collapse;width:100%;margin-top:32px}}td,th{{text-align:left;padding:14px 10px;border-bottom:1px solid #34473c}}
td:last-child{{width:25%}}.bar{{height:12px;background:#82e8ad;min-width:0}}.muted{{color:#b0bdb4}}small{{overflow-wrap:anywhere}}
</style>
<h1>Spotify RPM indirmeleri</h1><p>{html.escape(repository)}</p>
<p class="total">{total:,}</p><p>GitHub Releases üzerinden toplam RPM dosyası indirmesi</p>
<p class="muted">Bu sayaç kurulum veya aktif kullanıcı sayısı değildir. Tekrarlanan indirmeler dahildir.
COPR ve özel depo indirmeleri ayrı sayılır. Uygulamadan kullanım verisi toplanmaz.</p>
<table><thead><tr><th>Sürüm</th><th>Dosya</th><th>İndirme</th><th>Grafik</th></tr></thead><tbody>{table}</tbody></table>
<p><a href="https://github.com/{repository}/releases">GitHub Releases</a> ·
<a href="https://copr.fedorainfracloud.org/coprs/universish/Spotify..Client/">COPR indirme sayaçları</a></p>
<small class="muted">Oluşturulma zamanı (UTC): {generated}. Silinen/değiştirilen yayın dosyalarının sayaçları korunamaz.</small></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="universish/spotify-client..copr..ci")
    parser.add_argument("--input", type=Path, help="Read a saved GitHub releases JSON response (offline)")
    parser.add_argument("--output", type=Path, default=Path("output/download-stats.html"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("repository must be OWNER/REPO")
    releases = json.loads(args.input.read_text()) if args.input else fetch_releases(args.repository)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(releases, args.repository), encoding="utf-8")
    args.output.with_suffix(".json").write_text(json.dumps(releases, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
