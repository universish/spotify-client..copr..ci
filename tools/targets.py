#!/usr/bin/env python3
"""Report requested targets without pretending an x86 DEB is an ARM build."""
import argparse
import json
from pathlib import Path
from urllib import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", action="store_true", help="Print candidate chroots only")
    parser.add_argument("--live", action="store_true", help="Intersect candidates with currently enabled COPR chroots")
    args = parser.parse_args()
    data = json.loads((Path(__file__).resolve().parents[1] / "packaging/targets.json").read_text())
    enabled = None
    if args.live:
        with request.urlopen("https://copr.fedorainfracloud.org/api_3/project?ownername=universish&projectname=Spotify..Client", timeout=60) as response:
            enabled = set(json.load(response)["chroot_repos"])
    for target in data["targets"]:
        name, status = target["chroot"], target["status"]
        if enabled is not None and name not in enabled:
            status = "disabled"
        if args.candidates:
            if status == "candidate":
                print(name)
        else:
            print(f"{name:43} {status:13} {target['reason']}")


if __name__ == "__main__":
    main()
