# Sweep Protocol v2.1: amendment to the locked v2 protocol

Status: LOCKED upon commit to the public repository, before the first v2.1
run. SWEEP_PROTOCOL_V2.md is not edited; this file states every point where
the v2.1 rerun departs from it or adds to it. Where this file is silent, v2
governs. Reason for the amendment: the first-round peer review of the Future
Internet manuscript (October 2026) asked for a uniform replication plus five
additional measurements; the rerun is scoped to what can be executed and
analysed within the revision period.

## A. Scope (replaces v2 section 1, grid)

- Primary grid: 5 providers x 3 paradigms (block, file, object) x 1 workload
  class (balanced) x 4 concurrency levels (1, 4, 16, 64) x 3 repetitions =
  180 runs. The large-object class is not rerun; its v1 results are reported
  with their v1 caveats.
- Extension level: object storage only, concurrency 128, 3 repetitions per
  provider = 15 runs, included in the same seeded order as the primary grid.
  Block and file are not run at 128 threads (their targets are capped by the
  80 GB ceiling and the tier caps are already reached at lower levels).
- Seeded order and stages: the journal set the revision deadline at
  30 October 2026, so each provider's plan is split into two stages fixed
  before execution. Stage 1 is the object and block primary runs (24 per
  provider, 120 in total), the cells on which the paper's main findings rest.
  Stage 2 is everything else: file primary runs, the 128-thread level, the
  two-client runs and the AWS equivalence and reservoir runs. Each stage is
  shuffled separately with seed 43. Stage 2 starts on a provider only after
  that provider's stage 1, including retries, is complete.
- Stopping rule: no run starts after 20 October 2026, 23:59 SAST
  (21:59:59 UTC). Runs not started by then are reported as not executed, by
  stage and mode; they are not imputed, and their absence is not treated as
  a failure of the service.
- Hosts: unchanged from v2 (4 vCPU / 16 GB, same regions); nproc recorded.

## B. Dataset sizing (v2 section 2, extended)

- Every run: dataset = 20 GB x concurrency / 16 (1.25, 5, 20, 80 GB), as v2.
- 128-thread object runs: 160 GB. No cap applies to object storage; per-thread
  work stays at 1.25 GB at every level, so the design remains uniformly
  weak-scaled.

## C. Telemetry (replaces v2 section 6, first bullet)

- mpstat -P ALL at a 5-second cadence for the whole measured window, so every
  core's utilisation is archived (not only the all-CPU mean).
- Gates reported per run: mean all-CPU > 80% (as v2), and any single core
  > 95% busy (100 - %idle) for at least half of the measured window.
- Both gated sets are excluded in separate sensitivity refits; primary fits
  include all accepted runs.

## D. Network baseline (makes v2 section 6, second bullet, concrete)

- At campaign start on each provider, with the second client host (section E)
  as iperf3 server in the same subnet: iperf3, 4 parallel streams, 30 s, both
  directions, 3 repetitions. Archived as netbaseline_<provider>.json.
- The per-provider documented NIC limit is still recorded, but interpretation
  of client-side network ceilings uses the measured value.

## E. Multi-client configuration (new)

- A second client host, identical in type, is provisioned in the same subnet
  and security group as the first, for the four S3-compatible providers (aws,
  gcp, huawei, alibaba). Azure is excluded because its object runs use the SDK
  runner, which has no coordinated multi-host mode.
- Runs: object, balanced, two clients x 64 threads each (128 threads in
  total), coordinated by elbencho's distributed mode (service on both hosts,
  --hosts from the first), same per-thread dataset (1.25 GB, 160 GB total),
  3 repetitions per provider = 12 runs.
- Comparison of interest: one host at 128 threads (section A) against two
  hosts at 64 threads each. A difference attributes a limit to the client; no
  difference attributes it beyond the client.

## F. Azure runner equivalence on S3 (new)

- s3_equiv_runner.py is a line-for-line port of azure_blob_runner v2 (same
  process and thread structure, duration-driven phases, streaming reads,
  reservoir-sampled latencies), with the Azure SDK replaced by boto3. Its
  SHA-256 is recorded in every manifest record.
- On AWS (role credentials, internal regional endpoint), object balanced at
  1, 4, 16 and 64 threads, 3 repetitions = 12 runs, interleaved in the AWS
  plan with the elbencho object runs on the same bucket configuration.
- Reservoir sensitivity: at 16 and 64 threads, one run each with reservoir
  sizes 1,000, 10,000 (the v2 default) and 100,000 per thread = 6 runs.
- Comparison of interest: per-level throughput ratio and p99 ratio between
  the ported runner and elbencho; p99 at the three reservoir sizes.

## G. Endpoint, instrument and integrity guards (v2 section 4, enforced)

- Before any run: the Alibaba S3 endpoint must contain "-internal."; the plan
  refuses to start otherwise.
- Every manifest record carries the SHA-256 of the elbencho binary and of the
  runner script actually executed.
- Retry rule unchanged (at most two retries, no parameter change).
- Bucket hygiene: after every object run on AWS, Huawei and Alibaba the
  bucket is emptied in parallel over the S3 API (sweep/purge_s3.py) before
  Terraform destroys it, and before every Alibaba provision all csb-bench
  buckets are emptied. This is housekeeping between runs and touches no
  measurement. GCP is left to Terraform's force_destroy because its S3
  interface has no multi-object delete.

## H. Analysis (additions to v2 section 7, fixed before execution)

- Primary exponents: balanced workload, per provider x paradigm x operation,
  levels 1 to 64, exactly as v2.
- Extended object exponents: levels 1 to 128, reported alongside.
- Completion-bias bounds: failed attempts re-entered at the 10th percentile of
  accepted runs at the same level, at half the cell minimum, and at the c=1
  median; all three reported.
- Comparison with v1: per cell, v2.1 exponent minus v1 exponent with both
  intervals; no pooling of v1 and v2.1 runs in any fit.
- The pooled mixed-effects test is not part of the v2.1 primary analysis.

## I. Publication

- New tag sweep-v2.1 and a new Zenodo version under the same concept DOI.
- v1 data stay published and unchanged; nothing moves to quarantine because
  of the rerun.
