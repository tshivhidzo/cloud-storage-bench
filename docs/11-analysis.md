# Analysis

In this lab you turn the archives into the numbers the paper reports, and see
which reviewer question each output answers.

## Lay out the data

Extract each archive into one folder per provider, so that
`<root>/<provider>/results-rerun-v21-<provider>/run_manifest.jsonl` exists, and
put `netbaseline_<provider>_600s.json` under `<root>/<provider>/sweep/`. The
released dataset already has this layout in `results-rerun-v21/`.

## Run

```bash
python3 sweep/analyze_v21.py --root results-rerun-v21 --out v21-output
```

| Output | What it holds | Question it answers |
|---|---|---|
| `runs.csv` | per run: phase throughput, p99, CPU (all-core and busiest core) | everything below |
| `exponents.csv` | per provider, paradigm and operation: beta with run-level and level-mean 95% intervals | do results hold under both interval constructions? |
| `completion.csv` | attempts and accepted runs | is there completion bias? |
| `cpu_cells.csv` | CPU per cell, busiest core, share of samples above 90% | was a single core saturated? |
| `ext128_multi.csv` | 64 threads on one host vs 128 on one host vs 2 x 64 | client limit or service limit? |
| `equivalence.csv` | SDK runner vs elbencho on AWS S3 | does the Azure runner behave like elbencho? |
| `reservoir.csv` | p99 by reservoir size | is Azure p99 sensitive to the estimator? |
| `network.csv` | 30 s and 600 s iperf3 | could a result be network-bound? |

## How to read the client-versus-service test

If the service is the limit, a second client does not raise the total and
slows the first client. If the client is the limit, a second client raises the
total by up to two while the first client's throughput is unchanged, and extra
threads on the saturated host add little.

| Object | 128 threads, 1 host | 2 hosts x 64 | Reading |
|---|---|---|---|
| AWS read | 1.95x | 1.99x | no limit within 128 threads |
| Alibaba | about 1.0x | 1.8 to 2.0x | single client was the limit |
| Azure | 0.93x | 1.78 to 1.80x | single client (runner CPU) was the limit |
| GCP write | 1.51x | 1.51x | limit outside the client |
| Huawei | about 1.0 to 1.3x | 1.3x, host CPU falls | limit outside the client |

## Cross-check from a second source

Recompute key values from elbencho's stdout summaries, which are independent of
the CSV parser:

```bash
grep -h 'Throughput MiB/s' results-rerun-v21/aws/results-rerun-v21-aws/raw/aws-block-balanced-c04-r?.stdout.log
```

## Earlier campaign comparison

`sweep/make_v21_paper.py` (lab 12) reads the earlier campaign's exponents from
`recompute-output/exponents_recomputed.csv`. Comparing the fixed-size earlier
block writes with the weakly scaled present ones showed that block write
throughput depends on the volume written, not the thread count: at four
threads AWS wrote 87 MiB/s for 5 GiB but 50 MiB/s for 20 GB.

Next: [Tables, Figures and the Manuscript](12-manuscript.md)
