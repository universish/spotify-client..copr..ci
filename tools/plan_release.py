#!/usr/bin/env python3
"""Check stable metadata and atomically reserve a per-version RPM release number."""
import argparse
import configparser
import json
import os
import re
import sys
from pathlib import Path
from urllib import error, parse, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from parser_debian_control_file import fetch_package

REPOSITORY = "universish/spotify-client..copr..ci"
PROJECT_QUERY = parse.urlencode({"ownername": "universish", "projectname": "Spotify..Client"})


class GitHub:
    def __init__(self, repository, token):
        self.base = f"https://api.github.com/repos/{repository}"
        self.headers = {"Accept": "application/vnd.github+json", "User-Agent": "spotify-rpm-release-planner"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def call(self, path, data=None):
        headers = dict(self.headers)
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        with request.urlopen(request.Request(self.base + path, data=body, headers=headers), timeout=60) as response:
            return json.load(response)

    def releases(self):
        records, page = [], 1
        while True:
            batch = self.call(f"/releases?per_page=100&page={page}")
            records.extend(batch)
            if len(batch) < 100:
                return records
            page += 1


def copr_builds():
    records, offset = [], 0
    while True:
        url = f"https://copr.fedorainfracloud.org/api_3/build/list?{PROJECT_QUERY}&limit=100&offset={offset}"
        with request.urlopen(url, timeout=60) as response:
            batch = json.load(response)["items"]
        records.extend(batch)
        if len(batch) < 100:
            return records
        offset += 100


def revision_from_tag(version, tag):
    match = re.fullmatch(rf"v{re.escape(version)}-([1-9][0-9]*)", tag)
    return int(match[1]) if match else None


def revision_from_rpm(version, name):
    match = re.fullmatch(rf"spotify-{re.escape(version)}-([1-9][0-9]*)(?:[.][A-Za-z0-9_+~.-]+)?[.](?:x86_64|x86_64_v2|src)[.]rpm", name)
    return int(match[1]) if match else None


def revision_from_copr(version, build):
    source = build.get("source_package") or {}
    if source.get("name") != "spotify":
        return None
    match = re.fullmatch(rf"{re.escape(version)}-([1-9][0-9]*)(?:[.][A-Za-z0-9_+~.-]+)?", source.get("version", "").split(":", 1)[-1])
    return int(match[1]) if match else None


def plan(version, releases, refs, builds, manual=False):
    if not re.fullmatch(r"[A-Za-z0-9.+~]+", version):
        raise ValueError("Invalid upstream version")
    numbers, published = [], False
    for release in releases:
        number = revision_from_tag(version, release.get("tag_name", ""))
        if number:
            numbers.append(number)
        assets = [asset["name"] for asset in release.get("assets", [])]
        numbers.extend(n for name in assets if (n := revision_from_rpm(version, name)))
        binaries = {revision_from_rpm(version, name) for name in assets if name.endswith(".x86_64.rpm")}
        sources = {revision_from_rpm(version, name) for name in assets if name.endswith(".src.rpm")}
        complete = bool((binaries & sources) - {None})
        if complete and not release.get("draft", False) and not release.get("prerelease", False):
            published = True
    for ref in refs:
        number = revision_from_tag(version, ref["ref"].removeprefix("refs/tags/"))
        if number:
            numbers.append(number)
    for build in builds:
        number = revision_from_copr(version, build)
        if number:
            numbers.append(number)
            if build.get("state") == "succeeded":
                published = True
    if published and not manual:
        return {"needed": False, "version": version, "reason": "Stable DEB version unchanged; stopping before download, scanning and packaging."}
    number = max(numbers, default=0) + 1
    return {"needed": True, "version": version, "release": number, "tag": f"v{version}-{number}",
            "reason": "Manual repackaging requested." if manual else "New stable DEB version detected."}


def require_copr_config(value):
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(value)
    except configparser.Error:
        raise ValueError("COPR_CONFIG is not a valid generated INI configuration") from None
    if not config.has_section("copr-cli") or any(not config.get("copr-cli", key, fallback="").strip() for key in ("login", "username", "token")):
        raise ValueError("COPR_CONFIG must contain the complete generated [copr-cli] configuration")
    if config.get("copr-cli", "copr_url", fallback="").rstrip("/") != "https://copr.fedorainfracloud.org":
        raise ValueError("COPR_CONFIG must point to https://copr.fedorainfracloud.org")


def reserve(github, version, number, sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("GITHUB_SHA must be a full commit SHA")
    for _ in range(20):
        tag = f"v{version}-{number}"
        try:
            github.call("/git/refs", {"ref": f"refs/tags/{tag}", "sha": sha})
            return number, tag
        except error.HTTPError as exc:
            exc.close()
            if exc.code != 422:
                raise
            # A 422 can also be a permission/validation error: only retry a real collision.
            github.call("/git/ref/tags/" + parse.quote(tag, safe=""))
            number += 1
    raise RuntimeError("Could not reserve a unique packaging number after 20 collisions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", choices=("schedule", "workflow_dispatch"), required=True)
    parser.add_argument("--dry-run", action="store_true", help="Preview the decision without reserving a tag or requiring secrets")
    args = parser.parse_args()
    repository = os.environ.get("GITHUB_REPOSITORY", REPOSITORY)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    record = fetch_package("stable")
    version = record["RPMVersion"]
    github = GitHub(repository, os.environ.get("GH_TOKEN", ""))
    refs = github.call("/git/matching-refs/tags/" + parse.quote(f"v{version}-", safe=""))
    result = plan(version, github.releases(), refs, copr_builds(), args.event == "workflow_dispatch")
    if result["needed"]:
        if not args.dry_run:
            if not os.environ.get("GH_TOKEN"):
                raise ValueError("GH_TOKEN is required to reserve a packaging number")
            require_copr_config(os.environ.get("COPR_CONFIG", ""))
            result["release"], result["tag"] = reserve(github, version, result["release"], os.environ.get("GITHUB_SHA", ""))
        directory = Path(os.environ.get("SPOTIFY_METADATA_DIR", "metadata"))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "spotify-client.stable.json").write_text(json.dumps(record), encoding="utf-8")
    print(json.dumps(result))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            for key in ("needed", "version", "release", "tag"):
                if key in result:
                    stream.write(f"{key}={str(result[key]).lower() if isinstance(result[key], bool) else result[key]}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(f"{result['reason']} Upstream version: `{version}`.\n")
            if result["needed"]:
                stream.write(f"Reserved RPM version-release: `{version}-{result['release']}`.\n")


if __name__ == "__main__":
    main()
