# Stage 1: Object and Block Runs

In this lab you run the 24 object and block runs per provider on which the
main findings rest, and check them before moving on.

## Launch

**host 1**, tmux window 0:

```bash
cd ~/cloud-storage-bench-thesis-v1/sweep
python3 run_rerun_v21.py --provider <provider> --host2 $H2P --stage 1 2>&1 | tee -a rerun_<provider>_s1.log
```

Detach with Ctrl-b then d. Do not press Ctrl-C while a run is in progress: an
interrupted run writes no manifest record and may leave a target provisioned.

For each run the orchestrator empties leftover buckets (Alibaba), provisions a
fresh target with Terraform, drops caches, warms up for 60 s, measures while
`mpstat -P ALL 5` records every core, writes one manifest record, empties the
bucket and tears the target down.

## Watch it

Open window 1 (Ctrl-b then c) for reading only; it has no credentials.

```bash
cd ~/cloud-storage-bench-thesis-v1/sweep
grep -E '^\[|purge:|->' rerun_<provider>_s1.log | tail -8
ps -ef | grep -E 'run_rerun_v21|elbencho|terraform' | grep -v grep
python3 rerun_status.py --provider <provider> --host2 $H2P
```

Healthy signs:

- each object run is followed by `purge: csb-bench-xxxx: N objects deleted`,
  with N = threads x 20,480 (1,310,720 at 64 threads);
- each object run gets a **new** bucket name;
- `rerun_status.py` shows no `GATE FAIL`.

A reused bucket name, `0 objects deleted`, or `TEARDOWN FAILED` means the
bucket was not emptied; stop and read lab 8 before the next object run.

## Close stage 1

When the log ends with `finished: ok=... failed=...`, retry failures in
**window 0** (credentials are only there):

```bash
python3 run_rerun_v21.py --provider <provider> --host2 $H2P --stage 1 --resume 2>&1 | tee -a rerun_<provider>_s1.log
python3 rerun_status.py --provider <provider> --host2 $H2P
```

Gate: stage 1 shows `ok 24` and `to run 0`.

> On Alibaba a retry was started in window 1, which had no credentials.
> Terraform refused to start, nothing was measured, and the attempt still
> counted towards the retry limit (deviation D3). Check
> `echo ${#S3_ACCESS_KEY}` before any `--resume`.

## What stage 1 produced

| Provider | Stage 1 | Notes |
|---|---|---|
| AWS | 24/24 | purge needed throttling (lab 8) |
| Azure | 24/24 | |
| GCP | 24/24 | one teardown hit a transient 404 (D4) |
| Huawei | 24/24 | |
| Alibaba | 24/24 after retries | buckets not emptied for three runs (D1); credential-less retry (D3) |

Next: [Troubleshooting a Running Campaign](08-troubleshooting.md)
