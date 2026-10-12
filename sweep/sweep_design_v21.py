"""
sweep_design_v21.py -- run plan for the v2.1 rerun (SWEEP_PROTOCOL_V2_1_AMENDMENT.md).

Per provider, one seeded plan (seed 43) containing:
  primary   3 paradigms x balanced x {1,4,16,64} x 3 reps          = 36 runs
  ext128    object x balanced x 128 threads x 3 reps                =  3 runs
  multi     object x balanced x 2 hosts x 64 threads x 3 reps       =  3 runs
            (S3-compatible providers only, and only when a second
             client host is supplied)
  equiv     AWS only: s3_equiv_runner (port of azure runner v2),
            object x balanced x {1,4,16,64} x 3 reps                = 12 runs
  reservoir AWS only: s3_equiv_runner at 16 and 64 threads with
            reservoir 1k / 10k / 100k per thread, 1 rep            =  6 runs

Dataset: uniform weak scaling, 1280 MiB per thread at every level
(20 GiB at 16 threads, as v2), so per-thread work is constant.

Stages (fixed before execution because the revision is due 30 October 2026):
  stage 1  object + block primary runs (the cells the main findings rest on)
  stage 2  file primary, 128-thread object, two-client, equivalence, reservoir
Each stage is shuffled separately with seed 43. Stage 2 starts on a provider
only after its stage 1 is complete (including retries). Measurement stops at
STOP_AT; runs not started by then are reported as not executed.
"""
from __future__ import annotations
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import design as base  # noqa: E402  (thesis harness, read-only)

PROTOCOL = "v2.1"
SEED = 43
WORKLOAD = "balanced"
LEVELS = [1, 4, 16, 64]
EXT_LEVEL = 128
MULTI_THREADS_PER_HOST = 64
RESERVOIR_SIZES = [1_000, 10_000, 100_000]
RESERVOIR_LEVELS = [16, 64]
PER_THREAD_MIB = 1280           # 1.25 GiB per thread at every level
OBJECT_SIZE = "64k"
OBJECT_DURATION_S = 2400        # v2 section 3: object runs, uniform
SUBPROCESS_WINDOW_S = 2700
BLOCKFILE_TIMELIMIT_S = 600     # v2 section 3: every block/file phase
REPS = [1, 2, 3]
S3_COMPATIBLE = ("aws", "gcp", "huawei", "alibaba")
STOP_AT = "2026-10-20T21:59:59+00:00"   # 20 October 2026, 23:59 SAST


def dataset_mib(concurrency, hosts=1):
    return PER_THREAD_MIB * concurrency * hosts


def _rid(prov, para, conc, rep, suffix=""):
    rid = base.run_id(prov, para, WORKLOAD, conc, rep)
    return rid + (f"-{suffix}" if suffix else "")


def plan(provider, multi_client=False, include_equiv=True):
    runs = []
    for para in base.PARADIGMS:
        for c in LEVELS:
            for rep in REPS:
                runs.append(dict(run_id=_rid(provider, para, c, rep),
                                 mode="primary", paradigm=para, concurrency=c,
                                 rep=rep, hosts=1))
    for rep in REPS:
        runs.append(dict(run_id=_rid(provider, "object", EXT_LEVEL, rep),
                         mode="ext128", paradigm="object", concurrency=EXT_LEVEL,
                         rep=rep, hosts=1))
    if multi_client and provider in S3_COMPATIBLE:
        for rep in REPS:
            runs.append(dict(run_id=_rid(provider, "object",
                                         MULTI_THREADS_PER_HOST, rep, "mc2"),
                             mode="multi", paradigm="object",
                             concurrency=MULTI_THREADS_PER_HOST, rep=rep, hosts=2))
    if include_equiv and provider == "aws":
        for c in LEVELS:
            for rep in REPS:
                runs.append(dict(run_id=_rid(provider, "object", c, rep, "eq"),
                                 mode="equiv", paradigm="object", concurrency=c,
                                 rep=rep, hosts=1, lat_cap=10_000))
        for c in RESERVOIR_LEVELS:
            for cap in RESERVOIR_SIZES:
                runs.append(dict(run_id=_rid(provider, "object", c, 1,
                                             f"rv{cap // 1000}k"),
                                 mode="reservoir", paradigm="object",
                                 concurrency=c, rep=1, hosts=1, lat_cap=cap))
    for r in runs:
        r.update(provider=provider, workload=WORKLOAD, protocol=PROTOCOL,
                 dataset_mib=dataset_mib(r["concurrency"], r["hosts"]),
                 stage=1 if (r["mode"] == "primary"
                             and r["paradigm"] in ("object", "block")) else 2)
    out = []
    for stage in (1, 2):
        part = [r for r in runs if r["stage"] == stage]
        random.Random(SEED).shuffle(part)
        out += part
    return out
