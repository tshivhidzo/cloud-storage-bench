# Cloud Storage Benchmark — Thesis Dataset and Harness (v1.0)

Companion archive for the MTech (IT) thesis:
**"Performance Evaluation of Object, Block and File Storage Systems"**
Tshivhidzo Makungo (author), Dr Boniface Kabaso (supervisor),
Cape Peninsula University of Technology, 2026.

## What this archive contains

- `scripts/` — benchmark harness: campaign orchestrator, provisioning
  (Terraform wrapper), workload runners (elbencho; Azure Blob SDK runner),
  parsers, consolidation, cost attribution, leak checks.
- `configs/` — workload/tool configuration and credential template
  (`credentials.env.example`; no real credentials anywhere in this archive).
- `terraform/` — infrastructure definitions per provider (state files and
  provider binaries excluded).
- `results-<provider>/` — per-provider campaign output: `all_runs.csv`,
  `run_manifest.jsonl` (every attempt, ok or failed), and `raw/` (untouched
  tool output per run: elbencho CSV, stdout log, mpstat telemetry).
- `results-merged/` — consolidated dataset (`all_runs.csv`, 225 designed
  cells; 210 populated, blanks are disclosed gaps, never imputed),
  completeness report, storage leak-check reports, `manifest.sha256`.
- `billing/DERIVATION_NOTES.md` — how billing-derived costs were computed.
  Raw provider billing exports are excluded (account identifiers); they are
  available from the author on reasonable request.

## Design summary

5 providers (AWS, Azure, GCP, Huawei Cloud, Alibaba Cloud) x 3 paradigms
(block, file, object) x 5 workload classes x 3 repetitions, randomised
order (seed 42), fixed 16-thread concurrency, 4 vCPU / 16 GB benchmark
hosts co-located with storage targets. Integrity rules: raw output is never
edited by the pipeline; failed runs produce no metrics; missing values stay
blank; SHA-256 digest per raw artefact; costs only from provider billing.

## Redaction notice

elbencho echoes its command line into its CSV output. S3 access key IDs
(key IDs only — never secret keys, which are not present in any artefact)
were redacted from 117 raw files after measurement (`***REDACTED***`), and
the affected credentials were rotated regardless. `manifest.sha256` in this
archive is computed over the published (redacted) artefacts. No measurement
values were altered. Original unredacted digests are retained by the author.

## Reproducing

See `README.md` (harness usage) and `QUICKSTART_WINDOWS.md`. Provision with
your own cloud accounts; see `configs/credentials.env.example`.

## Licence

Code: MIT (see LICENSE). Data (`results-*`): CC BY 4.0 (see DATA_LICENSE).
Cite as: Makungo, T. (2026). Cloud Storage Benchmark — Thesis Dataset and
Harness (v1.0) [Data set and software].

## Concurrency-scaling sweep (journal campaign, sweep-v1)

Added for the paper "Concurrency scaling of managed cloud storage" (CCPE):

- `sweep/` — sweep orchestrator, design, Azure Blob runner v2, analysis script.
- `results-sweep-<provider>/` — 72 runs per provider (5 providers x 3 paradigms
  x 2 workloads x concurrency 1/4/16/64 x 3 reps = 360 runs, complete grid),
  same artefact discipline as the thesis campaign.
- `sweep-analysis/` — fitted scaling exponents (beta, 95% CI, R^2, saturation,
  CPU-gate flags) and the pooled-model result.
- `JOURNAL_SWEEP_RUNBOOK.md` — execution runbook including the instrument
  lessons (Azure runner v2 correction; internal-vs-public endpoint).
- Azure object cells measured with the defective v1 runner are quarantined and
  NOT in this dataset; the correction is documented in the paper.
- The same redaction notice applies: S3 access key IDs (never secrets) were
  redacted from echoed command lines in raw artefacts; credentials rotated.

## Redaction and checksum note (audit v2)

In addition to S3 access-key IDs, AWS STS temporary session tokens echoed by
elbencho into raw command lines were redacted (long expired; redacted
regardless). Host-generated integrity manifests, computed over pre-redaction
originals, are preserved as manifest.sha256.original-unredacted for
provenance; each folder's manifest.sha256 is computed over the published
(redacted) artefacts and verifies cleanly. No measurement value was altered
by any redaction.
