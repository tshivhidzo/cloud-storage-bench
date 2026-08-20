# Sweep Protocol v2 (locked)

Status: LOCKED upon commit to the public repository. Any deviation during
execution is recorded in the run manifest and disclosed; the protocol file
itself is never edited after the first run starts. This protocol governs the
rerun proposed in response to the pre-submission audit of the v1 sweep, whose
executed conditions mixed pre- and post-correction instrument states.

## 1. Design

- Grid: 5 providers (aws, azure, gcp, huawei, alibaba) x 3 paradigms (block,
  file, object) x 2 workload classes (balanced, largeobj) x 4 concurrency
  levels (1, 4, 16, 64) x 3 repetitions = 360 runs, seeded order (seed 43).
- Hosts: 4 vCPU / 16 GB, one per provider, same regions as v1 (comparability
  with the thesis dataset and sweep v1); `nproc` verified at host start.

## 2. Dataset sizing (uniform weak scaling, no cap distortion)

- BOTH workload classes use a 20 GB base at 16 threads.
- Every run's dataset = 20 GB x concurrency / 16 = 1.25, 5, 20, 80 GB.
- The 80 GB c64 dataset equals the operational ceiling exactly: per-thread
  work (1.25 GB/thread) is constant at every level. No cell is capped.
- Object runs: object size fixed per class (64 KiB balanced, 16 MiB
  largeobj); object count derives from the dataset size.

## 3. Phase rules

- balanced: write pass then read pass, equal volume, phase-sequential.
- largeobj: unmeasured preparation write, then measured sequential read.
- Block/file phases: `--timelimit 600` on EVERY run without exception.
  KNOWN SEMANTICS (discovered in v1): elbencho ends the whole benchmark when
  a phase hits the limit, so a write phase that caps out produces a
  write-only measurement. This is accepted and recorded: the parser stores
  phases_present per run, and balanced fits are per-operation, so write-only
  runs contribute to write fits without contaminating read fits.
- Object runs: never time-limited; `--duration 2400` uniformly (subprocess
  window 2700 s), chosen from v1 experience so no provider needs retries at a
  different duration than another.

## 4. Instruments (versions pinned, hashes recorded)

- elbencho 3.1-1 (static build), all block/file runs and all S3-compatible
  object runs. SHA-256 of the installed binary recorded in every manifest
  record at run start.
- Azure Blob: azure_blob_runner v2.3 (process pool <= 16 workers, thread
  fan-out, socket timeouts, streaming reads, reservoir-sampled latencies,
  per-phase csv rows). SHA-256 of the deployed script recorded in every
  manifest record.
- Endpoints: internal/VPC endpoints ONLY for object storage on huawei
  (obs...myhuaweicloud.com over VPC), alibaba (oss-<region>-internal), aws
  (regional S3 endpoint from within VPC), gcp (storage.googleapis.com via
  Private Google Access). The endpoint string is part of the archived
  command line of every object run; a preflight asserts the alibaba endpoint
  contains "-internal." and refuses to start otherwise.

## 5. Execution and retry rule

- Runs execute in seeded order within one tmux session per provider host.
- A failed run (tool error, timeout, provisioning failure) is retried at
  most TWICE, always under this same protocol; a cell that fails three times
  is reported as a disclosed blank. No parameter may be changed for a retry.
- Every attempt (success or failure) is appended to run_manifest.jsonl with
  full command line (credentials masked), timestamps, and instrument hashes.
  Attempt counts are reported in the paper, not only final coverage.
- Alibaba: automated OSS purge (dynamic bucket discovery, streaming delete)
  before every provision; purge failures never fail a run.
- Azure: orphaned-runner reaper before every object run.

## 6. Telemetry and gates

- mpstat 5-second cadence for the full measurement window per run; mean CPU
  > 80% flags the run CPU-bound. Gated runs are included in primary fits and
  excluded in a sensitivity refit; both are reported.
- Host NIC baseline: iperf3 (or provider equivalent) measured once per host
  at campaign start and archived, so client-side network ceilings are
  evidence rather than conjecture in bottleneck attribution.

## 7. Analysis (fixed before execution)

- Primary metrics per run: write-phase MiB/s, read-phase MiB/s (each = phase
  MiB / phase seconds from the tool's own totals), and combined = total MiB
  of both phases / total elapsed seconds of both phases. Sum-of-rates is not
  computed anywhere.
- Latency: per-phase p99 from the tool's per-phase percentile output; never
  combined across phases.
- Exponent fits: OLS of log10(metric) on log10(concurrency) per provider x
  paradigm x workload x operation; beta, SE, t-based 95% CI, R^2. Cells with
  fewer than 3 concurrency levels are blank.
- Saturation: highest level with >= 10% marginal gain over the previous.
- Pooled model: log10(combined) ~ log10(conc) x paradigm x workload fixed
  effects, provider random intercept; provider random slope tested with the
  50:50 chi-square mixture AND a parametric bootstrap (B >= 200, seed 42).
- The analysis implementation is sweep/recompute_from_raw.py and
  sweep/refit_exponents.py, committed before the first v2 run.

## 8. Configuration recording

Before the first run on each provider, an as-executed configuration record
is captured to configs/as_executed_<provider>.json: VM SKU, documented NIC
limit, block volume product/tier/size, file service product/protocol/mount
options, object storage class and endpoint. Sources: live Terraform state +
provider APIs, not memory.

## 9. Publication

- All raw artefacts, manifests, telemetry, this protocol, and the analysis
  scripts are published in github.com/tshivhidzo/cloud-storage-bench under a
  new tag (sweep-v2) and a new Zenodo version upon completion.
- Defective or superseded datasets are never deleted: they move to
  quarantine/ with SHA-256 digests and a README stating why.
