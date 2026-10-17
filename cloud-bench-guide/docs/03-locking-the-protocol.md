# Locking the Protocol

In this lab you fix the design, the analysis plan and the stopping rule in a
public, timestamped tag before a single run is made. This is what lets a
reviewer trust that the analysis was not chosen after seeing the data.

## Why

The earlier campaign (August 2026) changed its procedure four times during
collection, mixed three dataset-sizing rules and ran in design order. Its
results could only be reported with heavy qualifications. The October campaign
fixed all of that in advance.

## What the protocol fixes

The protocol is `sweep/SWEEP_PROTOCOL_V2.md` plus
`sweep/SWEEP_PROTOCOL_V2_1_AMENDMENT.md`, implemented in
`sweep/sweep_design_v21.py` and `sweep/run_rerun_v21.py`:

- **Grid:** five providers, three paradigms, threads 1, 4, 16 and 64, three
  repetitions: 180 primary runs.
- **Workload:** balanced, a write pass then a read pass of 64 KiB operations.
- **Sizing:** uniform weak scaling, 1.25 GiB per thread (object runs write
  20,480 objects of 64 KiB per thread).
- **Time limits:** `--timelimit 600` on every block and file run. elbencho ends
  the whole benchmark when a phase reaches the limit, so a slow 64-thread write
  produces a write-only run, which the protocol accepts.
- **Order:** shuffled with seed 43, in two stages: stage 1 is object and block
  primary runs, stage 2 everything else.
- **Controls:** a 128-thread object level, two client hosts for object storage,
  an iperf3 network baseline, and the Azure runner compared with elbencho on
  AWS S3, including its latency-reservoir size.
- **Retries:** at most two per run; three failures make a reported blank.
- **Stopping rule:** no run starts after a fixed date (20 October 2026, 23:59
  SAST), checked in the orchestrator.

## Commit and tag

**laptop**

```bash
cd ~/publish/cloud-storage-bench-thesis-v1
git pull --ff-only origin main
python3 sweep/run_rerun_v21.py --provider aws --host2 10.0.0.2 --dry-run --stage 1 | head -2
```

Expected: `v2.1 plan for aws: 24 runs`.

```bash
git add sweep/SWEEP_PROTOCOL_V2_1_AMENDMENT.md sweep/sweep_design_v21.py sweep/run_rerun_v21.py \
        sweep/s3_equiv_runner.py sweep/purge_s3.py sweep/rerun_status.py sweep/netbaseline.sh \
        scripts/host_up.sh terraform/hosts/aws/main.tf terraform/hosts/*/second_client.tf
git status --short          # only the files above; never .terraform/ or *.tfstate
git commit -m "v2.1 protocol, orchestrator, runners, second client"
git tag -a protocol-v2.1-locked -m "protocol fixed before the first run"
git push origin main protocol-v2.1-locked
git ls-remote --tags origin | grep protocol-v2.1
```

## Verification

The tag's date must precede the first run in any manifest. After the campaign:

```bash
git show -s --format='%ci' protocol-v2.1-locked
```

Any code change after this tag must be housekeeping (it may not change what is
measured) and gets its own commit message saying so.

Next: [Provisioning the Client Hosts](04-provisioning-hosts.md)
