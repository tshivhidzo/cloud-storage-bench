# Journal sweep campaign runbook - concurrency scaling across five clouds

Target paper: concurrency-scaling characterisation of block, file and object
storage (the thesis's original Objective 3, deferred to future work in
Section 6.7.7 / Appendix G). Venue: Journal of Cloud Computing (Springer).

## Design (locked)

- 5 providers x 3 paradigms x 2 workloads (balanced, largeobj) x 4 concurrency
  levels (1, 4, 16, 64) x 3 reps = **360 runs**, seeded order (seed 42 + 1).
- Hosts: **thesis-class 4 vCPU / 16 GB, retained deliberately**. This keeps
  the c16 sweep rows directly comparable with the thesis dataset. The cost is
  possible CPU saturation at 64 threads: every run's mpstat mean is checked,
  runs above 80% CPU are flagged CPU-bound, and flagged cells are disclosed
  and excluded from the exponent fits as a sensitivity check.
- Same integrity rules as the thesis campaign: blanks never imputed, SHA-256
  per artefact, billing-derived costs only, coverage report before analysis.
- Analysis: per paradigm x provider x workload, OLS of log10(throughput) on
  log10(concurrency) -> scaling exponent beta with CI; mixed model with
  provider random intercept as robustness; CPU-gate flag on any run with
  mpstat mean > 80%.

## Hosts

No Terraform overrides needed: the default host definitions (4 vCPU / 16 GB)
are used as-is. Verify with `nproc` (expect 4) after SSH.

## Scripts layout

The sweep lives in its own folder, `sweep/`, and does not modify the archived
thesis harness. Copy the WHOLE sweep folder to the host once:

    scp -r sweep ubuntu@<host-ip>:~/cloud-storage-bench/


## Before anything: credentials

1. **Alibaba**: the AK/SK exposed in the August session MUST be rotated before
   reuse (RAM console -> AccessKeys). Service activations (ECS, NAS, OSS)
   should still be active; verify in console.
2. **GCP**: rotate the HMAC interop key that appeared in logs (Cloud Storage
   -> Settings -> Interoperability), and re-enable billing exports if expired.
3. **Huawei**: console login, confirm account not restricted, create fresh
   AK/SK, export HW_ACCESS_KEY / HW_SECRET_KEY in the host shell only.
4. **AWS/Azure/GCP**: role-based (instance profile / managed identity /
   service account) - no key handling; run auth_preflight.py.

## Object-storage environment (CRITICAL - elbencho reads S3_*, not provider vars)

The provider-native variables (ALICLOUD_*, HW_*) feed Terraform ONLY. elbencho
takes its endpoint and credentials from S3_* variables; without S3_ENDPOINT it
treats the bucket name as a LOCAL FILE and silently benchmarks the root disk
(contamination tell: csb-bench-* files appearing in the sweep folder).

Set in the tmux shell per provider (aws: auto-derived; azure: SDK runner, none):

  alibaba:  export S3_ENDPOINT=https://oss-me-central-1-internal.aliyuncs.com
            # INTERNAL endpoint, exactly as the thesis campaign used. The
            # public endpoint routes through the EIP bandwidth cap (a few
            # MB/s): prep writes time out and any run that completes measures
            # the EIP, not OSS. Object runs recorded against the public
            # endpoint must be quarantined and remeasured.
            export S3_REGION=me-central-1
            export S3_ACCESS_KEY=$ALICLOUD_ACCESS_KEY
            export S3_SECRET_KEY=$ALICLOUD_SECRET_KEY
            export S3_VIRT_ADDR=1
  huawei:   export S3_ENDPOINT=https://obs.af-south-1.myhuaweicloud.com
            export S3_REGION=af-south-1
            export S3_ACCESS_KEY=$HW_ACCESS_KEY
            export S3_SECRET_KEY=$HW_SECRET_KEY
            export S3_VIRT_ADDR=1
  gcp:      export S3_ENDPOINT=https://storage.googleapis.com
            export S3_ACCESS_KEY=<HMAC key>   S3_SECRET_KEY=<HMAC secret>
            (+ the two AWS_*_CHECKSUM_* overrides)

After the first object run on ANY provider: check no csb-bench-* file exists
in the sweep folder and that the run log shows --s3endpoint.

## Per-provider sequence (repeat for aws, azure, gcp, huawei, alibaba)

```bash
# 1. bring up the host (defaults; run from the laptop)
./scripts/host_up.sh <provider>

# 2. on the host, preflight + env check (the recurring failure mode is env
#    vars missing inside tmux - ALWAYS verify inside the tmux shell)
python3 scripts/auth_preflight.py --providers <provider>
tmux new -s sweep
env | grep -E "HW_|ALICLOUD_|AWS_|S3_"     # inside tmux!

# 3. run the sweep (resumable)
cd ~/cloud-storage-bench/sweep
python3 run_sweep.py --providers <provider> --resume   # 72 runs/provider

# 4. parse + consolidate on the host, then pull results
python3 ../scripts/parse_results.py --outdir ./results-sweep
python3 ../scripts/consolidate.py --outdir ./results-sweep

# 5. tear down
./scripts/host_down.sh <provider>
```

Expected duration per provider: 72 runs x (60 s warm-up + 900 s measure +
overheads) = roughly 21-24 h of wall time; c64 largeobj runs may run long.
Budget guide: same hourly compute rate as the thesis campaign; object request
charges stay small because the sweep has no metadata workload.

## After all providers

```bash
python3 scripts/consolidate.py --outdir ./results-sweep     # merged coverage
python3 scripts/export_aws_costs.py --start <d1> --end <d2> # + per-provider exports
python3 scripts/add_costs.py --outdir ./results-sweep
./scripts/leak_check.sh | tee results-sweep/leak_check_$(date +%Y%m%d).txt
```

Then billing settles 1-3 days; derive rates exactly as DERIVATION_NOTES.md.

## Dataset sizing (weak scaling)

run_sweep.py sizes each run's dataset as BASE x concurrency/16 (BASE = the
thesis 16-thread sizes; capped at 80 GB). Constant per-thread work keeps all
runs inside the runner's timeout; c16 cells are identical to the thesis.
Runs executed before this change used fixed totals - their steady-state rates
remain valid, and the exact dataset per run is recorded in the manifest cmd.

Additionally, block/file phases carry --timelimit 600: on tier-capped volumes
(Azure P10 effectively ~32 MB/s at 64k I/O) the run reports its steady-state
rate instead of timing out. Object runs are never time-limited (read phases
need complete datasets). Default --duration is now 1200 (subprocess timeout
1500 s covers two 600 s phases). Where a run finishes before the limit, the
timelimit is inert and the measurement is unchanged.

## Azure Blob runner v2 (instrument correction)

The original SDK runner (v1) measured its own limits, not Blob's: batch-
barrier submission plus the Python GIL made throughput FALL at high thread
counts (rise-then-fall signature in the data). Azure object cells measured
with v1 are quarantined. sweep/azure_blob_runner_v2.py fixes this with
independent process workers and elbencho-matching balanced semantics.
Deploy on the Azure host only:
    scp sweep/azure_blob_runner_v2.py ubuntu@<AZURE-IP>:~/cloud-storage-bench/scripts/azure_blob_runner.py
then purge azure object entries from the manifest and --resume. The archived
repo copy of v1 is unchanged; the instrument change is disclosed in the paper.

## Known traps (from the thesis campaign - all still apply)

- OBS/OSS need `S3_VIRT_ADDR=1` (virtual-hosted addressing).
- GCS interop needs `AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED` and
  `AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED`.
- 10,000-part multipart limit and 5 MiB minimum part size bound the
  largeobj object/block-size combinations (16 MB objects are safe).
- Huawei/Alibaba metadata-style small-object runs need prep-writes; the
  sweep avoids metadata entirely, so timeouts should not recur.
- Alibaba me-central-1 sells instance families intermittently; the auto-pick
  now honours TF_VAR_cpu_cores/memory_gb.
- Use `scripts/status.py` from the laptop to check progress; never assume a
  broken SSH pipe killed the tmux session.
