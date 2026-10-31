#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
"""Scan pinned DEBs in the CI runner; retain reports and hash-bound attestations only."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]


def scan(metadata_path, report_dir, run_url):
    if not re.fullmatch(r'https://github[.]com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+', run_url):
        raise ValueError('A GitHub Actions run URL is required for scan provenance')
    spec = importlib.util.spec_from_file_location('spot_fly_light_ci', REPO / 'bootstrap/spot..fly..light.py')
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    catalog = json.loads(Path(metadata_path).read_text())
    records = {channel: bootstrap.metadata(metadata_path, channel) for channel in ('stable', 'unstable')}
    report_dir = Path(report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    # Private CI temp data is removed on success, a detection, any subprocess error,
    # and Python exceptions. The workflow also has an always() cleanup step.
    with tempfile.TemporaryDirectory(prefix='spot..fly..light-ci-scan-') as temporary:
        work = Path(temporary)
        env = dict(os.environ, CLAMAV_DATABASE_DIR=str(work / 'database'),
                   SCAN_REPORT_DIR=str(report_dir / 'database'))
        subprocess.run([str(REPO / 'src/scan_payload.sh'), '--update'], env=env, check=True)
        database_version = subprocess.run(['clamscan', '--database=' + env['CLAMAV_DATABASE_DIR'], '--version'],
                                          env=env, check=True, capture_output=True, text=True).stdout.strip()
        if not database_version:
            raise ValueError('ClamAV database version is missing')
        for channel, record in records.items():
            channel_work = work / channel
            channel_work.mkdir()
            deb = channel_work / 'client.deb'
            # Download helper checks the exact size and SHA256 before extraction.
            bootstrap.download(record, deb)
            bootstrap.verify(deb, record)
            raw = channel_work / 'raw'
            subprocess.run(['dpkg-deb', '--raw-extract', str(deb), str(raw)], check=True)
            env['SCAN_REPORT_DIR'] = str(report_dir / channel)
            subprocess.run([str(REPO / 'src/scan_payload.sh'), '--scan', str(deb), str(raw)], env=env, check=True)
            pua = json.loads((Path(env['SCAN_REPORT_DIR']) / 'pua-status.json').read_text())
            if pua.get('disposition') not in ('clean', 'advisory'):
                raise ValueError('PUA scan status is not acceptable')
            record['ScanAttestation'] = {
                'SHA256': record['SHA256'], 'Malware': 'clean', 'PUA': pua['disposition'],
                'RunURL': run_url, 'ScannedAt': datetime.now(timezone.utc).isoformat(),
                'Scanner': 'ClamAV', 'DatabaseVersion': database_version,
            }
    # Publish no partial/new attestations if either channel was blocked.
    if 'Bootstrap' in catalog:
        records['Bootstrap'] = catalog['Bootstrap']
    Path(metadata_path).write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata')
    parser.add_argument('reports')
    parser.add_argument('--run-url', default='https://github.com/' + os.environ.get('GITHUB_REPOSITORY', '') + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', ''))
    args = parser.parse_args()
    scan(args.metadata, args.reports, args.run_url)
