"""
design.py -- single source of truth for the experimental design and the
26-field output schema. Imported by run_campaign.py, parse_results.py and
consolidate.py so the plan, the parser and the completeness report can never
drift apart.

Design (from SKILL.md):
  5 providers x 3 paradigms x 5 workloads x 3 reps = 225 runs at concurrency 16.
  Separate concurrency sweep (levels 1/4/16/64, largeobj workload) supplies the
  scaling exponents and is NOT part of the 225.
"""
from __future__ import annotations
import itertools
import random

PROVIDERS = ["aws", "azure", "gcp", "huawei", "alibaba"]
PARADIGMS = ["block", "file", "object"]
WORKLOADS = ["read", "write", "balanced", "metadata", "largeobj"]
REPS = [1, 2, 3]
FACTORIAL_CONCURRENCY = 16
SWEEP_LEVELS = [1, 4, 16, 64]
SWEEP_WORKLOAD = "largeobj"
DEFAULT_SEED = 42
FULL_GRID_N = len(PROVIDERS) * len(PARADIGMS) * len(WORKLOADS) * len(REPS)  # 225

# The 26-field all_runs.csv schema (thesis Appendix D data dictionary).
# Order is stable; parser writes exactly these columns, blanks for missing.
SCHEMA = [
    "run_id",                 # 1  deterministic id: provider-paradigm-workload-cNN-rN
    "timestamp_utc",          # 2  ISO-8601 UTC when the measurement window ended
    "provider",               # 3  aws|azure|gcp|huawei|alibaba
    "region",                 # 4  cloud region string actually used
    "paradigm",               # 5  block|file|object
    "workload",               # 6  read|write|balanced|metadata|largeobj
    "rep",                    # 7  1|2|3
    "concurrency",            # 8  thread count (16 factorial; 1/4/16/64 sweep)
    "tool",                   # 9  elbencho|azure_blob_sdk|fio
    "block_size",             # 10 IO/object size used for this workload
    "dataset_size_gb",        # 11 total dataset moved (GB)
    "warmup_s",               # 12 warm-up seconds before measurement
    "duration_s",             # 13 measurement window seconds
    "read_throughput_mbps",   # 14
    "write_throughput_mbps",  # 15
    "total_throughput_mbps",  # 16
    "read_iops",              # 17
    "write_iops",             # 18
    "total_iops",             # 19
    "lat_mean_ms",            # 20
    "lat_p95_ms",             # 21
    "lat_p99_ms",             # 22
    "metadata_ops_per_s",     # 23 populated only for the metadata workload
    "cpu_util_pct",           # 24 guest telemetry mean CPU utilisation
    "raw_artifact_path",      # 25 path to the untouched tool output for this run
    "raw_sha256",             # 26 checksum of that raw artefact
]
assert len(SCHEMA) == 26, f"schema must be 26 fields, got {len(SCHEMA)}"

# Per-workload parameters. These drive the tool command lines. Metadata moves no
# payload and is reported in ops/s + latency, never MB/s.
WORKLOAD_PARAMS = {
    #            block_size  dataset_gb  rw_mix (read fraction; None=metadata)
    "read":     {"block_size": "64k",  "dataset_gb": 20, "read_frac": 1.0},
    "write":    {"block_size": "64k",  "dataset_gb": 20, "read_frac": 0.0},
    "balanced": {"block_size": "64k",  "dataset_gb": 20, "read_frac": 0.5},
    "metadata": {"block_size": "4k",   "dataset_gb": 2,  "read_frac": None},
    "largeobj": {"block_size": "16m",  "dataset_gb": 40, "read_frac": 1.0},
}


def run_id(provider, paradigm, workload, concurrency, rep):
    return f"{provider}-{paradigm}-{workload}-c{concurrency:02d}-r{rep}"


def factorial_plan(providers=None, paradigms=None, workloads=None, reps=None,
                   concurrency=FACTORIAL_CONCURRENCY, seed=DEFAULT_SEED):
    """Return the seeded-random-ordered list of factorial runs."""
    providers = providers or PROVIDERS
    paradigms = paradigms or PARADIGMS
    workloads = workloads or WORKLOADS
    reps = reps or REPS
    plan = []
    for prov, para, wl, rep in itertools.product(providers, paradigms, workloads, reps):
        plan.append({
            "run_id": run_id(prov, para, wl, concurrency, rep),
            "provider": prov, "paradigm": para, "workload": wl,
            "concurrency": concurrency, "rep": rep, "mode": "factorial",
        })
    random.Random(seed).shuffle(plan)
    return plan


def sweep_plan(providers=None, paradigms=None, levels=None, reps=None,
               seed=DEFAULT_SEED):
    """Concurrency sweep runs (largeobj workload). Not part of the 225."""
    providers = providers or PROVIDERS
    paradigms = paradigms or PARADIGMS
    levels = levels or SWEEP_LEVELS
    reps = reps or REPS
    plan = []
    for prov, para, lvl, rep in itertools.product(providers, paradigms, levels, reps):
        plan.append({
            "run_id": run_id(prov, para, SWEEP_WORKLOAD, lvl, rep),
            "provider": prov, "paradigm": para, "workload": SWEEP_WORKLOAD,
            "concurrency": lvl, "rep": rep, "mode": "sweep",
        })
    random.Random(seed + 1).shuffle(plan)
    return plan
