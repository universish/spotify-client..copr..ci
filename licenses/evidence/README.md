# License provenance and independent timestamps

Snapshot date: 2026-10-30 in Europe/Istanbul. UTC collection times are recorded
in the JSON files. The bundle covers the LPF license and source records, the
Spotify DEB metadata and embedded third-party notice, and the public FreeTSA
certificate files. No Spotify executable or secret is included.

## Verify

From the repository root:

```sh
bash tools/verify_license_evidence.sh
```

The verifier first checks every file against `2026-10-30-SHA256SUMS`, then uses
OpenSSL to verify the RFC 3161 response against both that exact manifest and
its saved request. SHA256 protects byte integrity; the response carries the
independent TSA's signed time and message imprint. Only the manifest digest,
request nonce and protocol metadata are submitted to https://freetsa.org/tsr.
Neither documents nor DEB files are uploaded to that service.

`timestamps/2026-10-30/` retains the request, response, TSA certificate, CA
certificate, decoded token and verification output. Certificate trust is
explicitly anchored in the retained FreeTSA CA, obtained over verified HTTPS;
that CA is not silently installed in the host trust store. The validation is
an integrity/signature check, not a complete long-term revocation assessment.

## What this supports and what it does not

The LPF file is also bound to an upstream commit permalink and a recomputed Git
blob hash checked against the GitHub contents API. The original upstream bytes,
including trailing newlines, are retained. HTTP Date/Last-Modified/ETag and Git
commit dates support provenance but are not independently signed trusted times.
The TSA token supplies the independent signed time for this collected bundle.
It does not prove that we collected it in 2013, nor establish authorship,
ownership, authority to grant a license, applicability to unrelated code, or
legal validity. It cannot guarantee that nobody can dispute the evidence.

FreeTSA is a free RFC 3161 service, used through the open-source OpenSSL client.
This project does not claim that this is a qualified electronic timestamp under
Turkish or EU law, notarization, or a court's determination. Legal weight depends
on the applicable law and facts. Keep the bundle together; before algorithms or
certificates become unsuitable, preserve relevant validation material and obtain
a renewal stamp over the original proof. Never replace this dated snapshot;
create a separately dated bundle for later changes.

Sources: https://freetsa.org/index_en.php and
https://docs.openssl.org/master/man1/openssl-ts/
