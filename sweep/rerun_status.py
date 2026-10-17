#!/usr/bin/env python3
"""
rerun_status.py -- progress and sanity gates for a v2.1 provider run.

    python3 rerun_status.py --provider aws [--host2 10.42.1.23]

Prints, per stage: planned, ok, failed attempts, still to run, exhausted
(3 failed attempts). Then checks the raw output of every ok run: elbencho or
runner csv present and non-empty, per-core mpstat rows present, instrument
hash recorded. Exit status 1 if any ok run fails a gate.
"""
from __future__ import annotations
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import sweep_design_v21 as D  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--host2", default="")
    ap.add_argument("--outdir", default=None)
    a = ap.parse_args()
    out = Path(a.outdir or f"./results-rerun-v21-{a.provider}")
    plan = {r["run_id"]: r for r in D.plan(a.provider, multi_client=bool(a.host2))}
    recs = defaultdict(list)
    mf = out / "run_manifest.jsonl"
    if mf.exists():
        for line in mf.read_text().splitlines():
            try:
                r = json.loads(line)
                recs[r["run_id"]].append(r)
            except json.JSONDecodeError:
                pass
    print(f"{a.provider}: manifest {mf} ({sum(len(v) for v in recs.values())} attempts)")
    for stage in (1, 2):
        ids = [k for k, r in plan.items() if r["stage"] == stage]
        ok = [k for k in ids if any(x.get("status") == "ok" for x in recs[k])]
        fails = sum(1 for k in ids for x in recs[k] if x.get("status") != "ok")
        exhausted = [k for k in ids if k not in ok and len(recs[k]) >= 3]
        todo = [k for k in ids if k not in ok and k not in exhausted]
        print(f"  stage {stage}: planned {len(ids):>3}  ok {len(ok):>3}  "
              f"failed attempts {fails:>3}  to run {len(todo):>3}  "
              f"exhausted {len(exhausted)}")
        for k in exhausted:
            print(f"     exhausted: {k}  last error: {recs[k][-1].get('error', '')[:100]}")
    fb = [k for k in recs if k.endswith("-fb")]
    if fb:
        fb_ok = [k for k in fb if any(x.get("status") == "ok" for x in recs[k])]
        print(f"  supplementary -fb (D1): attempted {len(fb):>2}  ok {len(fb_ok):>2}")
    bad = 0
    for k, attempts in recs.items():
        good = [x for x in attempts if x.get("status") == "ok"]
        if not good:
            continue
        r = good[-1]
        problems = []
        csv = Path(r.get("raw_csv", ""))
        if not csv.exists() or csv.stat().st_size == 0:
            problems.append("raw csv missing/empty")
        tel = Path(r.get("telemetry", ""))
        if not tel.exists() or "all" not in tel.read_text() or " 0 " not in tel.read_text():
            problems.append("per-core mpstat rows missing")
        if r.get("tool") == "elbencho" and not r.get("elbencho_sha256"):
            problems.append("elbencho hash missing")
        if r.get("tool") != "elbencho" and not r.get("runner_sha256"):
            problems.append("runner hash missing")
        if r.get("teardown", "ok") != "ok":
            problems.append("TEARDOWN FAILED: check billing")
        if problems:
            bad += 1
            print(f"  GATE FAIL {k}: {'; '.join(problems)}")
    stray = list(HERE.glob("csb-bench*"))
    if stray:
        bad += 1
        print(f"  GATE FAIL: local files named like buckets in {HERE} "
              f"(S3 endpoint not set?): {[p.name for p in stray][:5]}")
    print("  gates: " + ("all ok runs pass" if not bad else f"{bad} problem(s)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
