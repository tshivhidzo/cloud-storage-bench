# Measuring the Network Baseline

In this lab you measure the network capacity of each client host instead of
relying on the provider's documented figure. Without it, a reviewer cannot
tell whether a throughput plateau is the storage service or the host's network.

## Short runs (before the campaign)

**host 1**, window 0, from the repository root:

```bash
cd ~/cloud-storage-bench-thesis-v1
bash sweep/netbaseline.sh <provider> $H2P
```

Three 30-second runs per direction with four parallel streams; the summary is
written to `results-rerun-v21-<provider>/netbaseline_<provider>.json`.

## Sustained run (after the campaign, before teardown)

A 30-second run can show a burst rate that the host cannot sustain ("up to
10 Gbit/s" instance types use credits). Run 600 seconds once per provider:

```bash
cd ~/cloud-storage-bench-thesis-v1/sweep
iperf3 -c $H2P -P 4 -t 600 -J > netbaseline_<provider>_600s.json && echo iperf-ok
```

## What we measured

| Provider | 30 s send / receive (Gbit/s) | 600 s | First / last minute |
|---|---|---|---|
| AWS | 9.93 / 9.94 | 9.95 | 9.95 / 9.95 |
| Azure | 1.83 / 1.77 | 1.84 | 1.84 / 1.83 |
| GCP | 7.84 / 7.53 | 7.58 | 7.41 / 7.32 |
| Huawei | 7.87 / 8.47 | 7.83 | 7.76 / 7.90 |
| Alibaba | 3.46 / 3.47 | 3.30 | 3.50 / 3.30 |

Two uses of these numbers in the paper:

- Only the Alibaba host came close to its network capacity (341 MiB/s, about
  2.9 Gbit/s, at 64 threads), so its single-host limit may be network as well
  as CPU.
- Azure meters outbound traffic only. Azure Files writes levelled at
  200 to 215 MiB/s, matching the 1.84 Gbit/s outbound rate, while reads went
  higher.

Next: [Stage 1: Object and Block Runs](07-stage-1.md)
