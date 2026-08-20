# Journal sweep (concurrency scaling paper)

Self-contained folder; the archived thesis harness in ../scripts is imported
read-only and never modified.

Design: 5 providers x 3 paradigms x {balanced, largeobj} x {1,4,16,64} threads
x 3 reps = 360 runs. Hosts: thesis-class 4 vCPU / 16 GB (comparability with
the thesis c16 dataset); runs with mean CPU > 80% are flagged CPU-bound.

Usage (on the benchmark host, inside tmux):
    cd ~/cloud-storage-bench/sweep
    python3 run_sweep.py --providers aws --dry-run     # expect 72 runs
    python3 run_sweep.py --providers aws --resume

Results land in ./results-sweep (separate from the thesis ./results).
Parse and consolidate with the thesis harness tools:
    python3 ../scripts/parse_results.py --outdir ./results-sweep
    python3 ../scripts/consolidate.py --outdir ./results-sweep
