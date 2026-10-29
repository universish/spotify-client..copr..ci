#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 universish
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
manifest=licenses/evidence/2026-10-30-SHA256SUMS
stamp=licenses/evidence/timestamps/2026-10-30
sha256sum -c "$manifest"
openssl ts -verify -data "$manifest" -in "$stamp/manifest.tsr" \
    -CAfile "$stamp/cacert.pem" -untrusted "$stamp/tsa.crt"
openssl ts -verify -queryfile "$stamp/manifest.tsq" -in "$stamp/manifest.tsr" \
    -CAfile "$stamp/cacert.pem" -untrusted "$stamp/tsa.crt"
