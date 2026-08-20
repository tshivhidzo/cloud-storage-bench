"""
sweep_design.py -- journal sweep campaign design (concurrency scaling paper).
Separate from the archived thesis harness; imports it read-only for the
schema, run-id convention and provider/paradigm lists so nothing can drift.

Design: 5 providers x 3 paradigms x 2 workloads (balanced, largeobj)
        x 4 concurrency levels (1, 4, 16, 64) x 3 reps = 360 runs.
Hosts:  thesis-class 4 vCPU / 16 GB (retained deliberately for comparability
        with the thesis dataset at c16). Runs whose mean CPU utilisation
        exceeds 80% are flagged CPU-bound by the analysis and disclosed.
"""
from __future__ import annotations
import itertools, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import design as base  # noqa: E402  (thesis harness, read-only)

SWEEP_WORKLOADS = ["balanced", "largeobj"]
SWEEP_LEVELS = [1, 4, 16, 64]
SEED = base.DEFAULT_SEED
SCHEMA = base.SCHEMA
CPU_GATE_PCT = 80.0

# Weak-scaling anchor: per-thread dataset constant, equal to the thesis
# campaign's 16-thread sizes. Total dataset = BASE * concurrency/16,
# capped at 80 GB so block/file targets (100 GB) are never overfilled.
BASE_DATASET_GB = {"read": 20, "write": 20, "balanced": 20,
                   "metadata": 2, "largeobj": 40}

def scaled_dataset_gb(workload, concurrency):
    base = BASE_DATASET_GB[workload]
    return min(80, max(1, round(base * concurrency / 16)))

def sweep_plan(providers=None, paradigms=None, workloads=None,
               levels=None, reps=None, seed=SEED):
    providers = providers or base.PROVIDERS
    paradigms = paradigms or base.PARADIGMS
    workloads = workloads or SWEEP_WORKLOADS
    levels = levels or SWEEP_LEVELS
    reps = reps or base.REPS
    plan = []
    for prov, para, wl, lvl, rep in itertools.product(
            providers, paradigms, workloads, levels, reps):
        plan.append({
            "run_id": base.run_id(prov, para, wl, lvl, rep),
            "provider": prov, "paradigm": para, "workload": wl,
            "concurrency": lvl, "rep": rep, "mode": "sweep",
        })
    random.Random(seed + 1).shuffle(plan)
    return plan
