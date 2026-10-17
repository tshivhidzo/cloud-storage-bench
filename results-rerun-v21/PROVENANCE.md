# Provenance of the v2.1 (October 2026) campaign data

Each provider folder is the content of the archive packed on that provider's
first client host at the end of its campaign, with one change: credential
identifiers were removed (see below). The original archives are not published
because they contain those identifiers; their SHA-256 digests, as recorded on
the hosts and confirmed after copying to the laptop, are:

| Archive (host-side) | SHA-256 |
|---|---|
| rerun_aws.tgz | 1e611d759269f02cca394ae06655c026d068d881dab991891aef45b70cba20f1 |
| rerun_azure.tgz | 18fc3d269117d50a2cb0228f1f1f74ee37f10dac27aca812fa76a2234b40f8b5 |
| rerun_gcp.tgz | aa974988e6003f8451ea1e9158c64a76240b03fe379f62a5999dd62dce8dfe3b |
| rerun_huawei.tgz | bf0659f7c4aadd593df15e154f5ac10b6625575e916005ec932a3c236ff54c5b |
| rerun_alibaba.tgz | e463cacd871534d66edf91d9014df9ca53cebca26ad0c1d4999637a82762f0f7 |
| rerun_azure_mc2.tgz (deviation D5) | 98c4fe6ec36858989b7ce91fc8a58589d90646cdf00ceef3516b9ec1d9f724c1 |

`azure/sweep/netbaseline_azure_600s.json` was copied separately from the Azure
host (SHA-256 c818a12019a89604df694e0d9e41f1bf5d0571ef8d7132d4b9d624e6ec51717d).

## Redaction

elbencho writes its full command line into each result CSV. For object runs
on the S3-compatible clouds that command line contains the access-key
identifier and, on AWS, a temporary session token (the secret key is masked by
elbencho itself). In every `*.elbencho.csv` file the values following
`"--s3key"`, `"--s3secret"` and `"--s3sessiontoken"` were replaced with
`REDACTED` (186 values in 75 files). No other byte was changed. The run
manifests already carried masked command lines (`'***'`) and were not altered.
All campaign credentials were deleted after teardown.

The redaction does not affect any measured value: `sweep/analyze_v21.py` and
`sweep/make_v21_paper.py` run on this redacted tree reproduce `v21-output/` and
`paper-v21/` byte for byte (see VERIFICATION_GUIDE_V21.md).

## Layout

`<provider>/results-rerun-v21-<provider>/run_manifest.jsonl` (every attempt),
`.../raw/` (per run: elbencho or runner CSV, stdout log, per-core mpstat),
`.../netbaseline_<provider>.json` (30-second iperf3 runs),
`<provider>/sweep/netbaseline_<provider>_600s.json` (600-second iperf3 run),
`<provider>/rerun_<provider>_s*.log` (orchestrator logs; Alibaba also
`_fb.log`), `<provider>/status_<provider>_final.txt`.
`azure-mc2/` holds the supplementary Azure two-host test (deviation D5) with
the processor records of both hosts.
