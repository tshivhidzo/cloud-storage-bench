#!/usr/bin/env python3
"""
run_campaign.py -- campaign orchestrator.

For each run in the seeded plan it: provisions the storage target (provision.py
-> Terraform), drops caches, warms up, measures for the window, captures
telemetry, writes untouched raw output + a per-run record, then tears the target
down. It writes results/run_manifest.jsonl describing every attempt (ok/failed).
It NEVER writes a metric -- parse_results.py does that from the raw output, and
failed runs simply have no raw output, so their all_runs.csv cells stay blank.

Run ONE provider per host (the topology in HARNESS_RUNBOOK.md):
    python3 scripts/run_campaign.py --providers aws --paradigms all \
        --workloads all --reps 3 --concurrency 16 --seed 42 --outdir ./results
Preview only (spends nothing):
    python3 scripts/run_campaign.py --dry-run
Concurrency sweep (scaling exponents; not part of the 225):
    python3 scripts/run_campaign.py --sweep --providers aws --levels 1,4,16,64
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import design
import runners
import provision as provision_mod


def _csv_list(val, allowed=None, cast=str):
    if val in (None, "all", ""):
        return None
    out = [cast(x.strip()) for x in val.split(",") if x.strip()]
    if allowed:
        bad = [x for x in out if x not in allowed]
        if bad:
            sys.exit(f"error: unknown value(s) {bad}; allowed {sorted(allowed)}")
    return out


def build_plan(args):
    if args.sweep:
        return design.sweep_plan(
            providers=_csv_list(args.providers, set(design.PROVIDERS)),
            paradigms=_csv_list(args.paradigms, set(design.PARADIGMS)),
            levels=_csv_list(args.levels, cast=int) or design.SWEEP_LEVELS,
            reps=list(range(1, args.reps + 1)),
            seed=args.seed)
    return design.factorial_plan(
        providers=_csv_list(args.providers, set(design.PROVIDERS)),
        paradigms=_csv_list(args.paradigms, set(design.PARADIGMS)),
        workloads=_csv_list(args.workloads, set(design.WORKLOADS)),
        reps=list(range(1, args.reps + 1)),
        concurrency=args.concurrency,
        seed=args.seed)


def print_plan(plan, args):
    print(f"\nRun plan: {len(plan)} runs  "
          f"(mode={'sweep' if args.sweep else 'factorial'}, seed={args.seed})")
    if not args.sweep:
        full = design.FULL_GRID_N
        note = "== full 225 grid" if len(plan) == full else f"of the {full}-run full grid"
        print(f"  {len(plan)} {note}")
    print(f"{'#':>3}  {'run_id':32}  {'prov':7} {'paradigm':8} {'workload':9} "
          f"{'conc':>4} {'rep':>3}")
    for i, r in enumerate(plan, 1):
        print(f"{i:>3}  {r['run_id']:32}  {r['provider']:7} {r['paradigm']:8} "
              f"{r['workload']:9} {r['concurrency']:>4} {r['rep']:>3}")
    print()


def main():
    ap = argparse.ArgumentParser(description="Cloud storage benchmark campaign")
    ap.add_argument("--providers", default="all")
    ap.add_argument("--paradigms", default="all")
    ap.add_argument("--workloads", default="all")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=design.FACTORIAL_CONCURRENCY)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--levels", default="1,4,16,64")
    ap.add_argument("--seed", type=int, default=design.DEFAULT_SEED)
    ap.add_argument("--outdir", default="./results")
    ap.add_argument("--warmup", type=int, default=60, help="warm-up seconds")
    ap.add_argument("--duration", type=int, default=900, help="measure seconds")
    ap.add_argument("--dry-run", action="store_true", help="print plan, run nothing")
    ap.add_argument("--keep-targets", action="store_true",
                    help="do NOT tear down targets (debug only; keeps billing!)")
    ap.add_argument("--resume", action="store_true",
                    help="skip runs already recorded as ok in the manifest")
    args = ap.parse_args()

    plan = build_plan(args)
    if args.resume:
        manifest_path = Path(args.outdir) / "run_manifest.jsonl"
        done = set()
        if manifest_path.exists():
            for line in manifest_path.read_text().splitlines():
                try:
                    rec = json.loads(line)
                    if rec.get("status") == "ok":
                        done.add(rec["run_id"])
                except json.JSONDecodeError:
                    pass  # a run interrupted mid-write leaves a partial line
        skipped = [r for r in plan if r["run_id"] in done]
        plan = [r for r in plan if r["run_id"] not in done]
        print(f"--resume: skipping {len(skipped)} already-ok run(s), "
              f"{len(plan)} remaining")
    print_plan(plan, args)
    if args.dry_run:
        print("dry-run: nothing provisioned, nothing measured, nothing billed.")
        return

    outdir = Path(args.outdir)
    (outdir / "raw").mkdir(parents=True, exist_ok=True)
    manifest = outdir / "run_manifest.jsonl"
    ok = failed = 0
    t_start = time.time()
    with open(manifest, "a") as mf:
        for i, run in enumerate(plan, 1):
            print(f"[{i}/{len(plan)}] {run['run_id']} ...", flush=True)
            rec = {"ts_start": datetime.now(timezone.utc).isoformat(), **run}
            target = None
            try:
                target = provision_mod.provision(run["provider"], run["paradigm"],
                                                 region=None)
                rec["region"] = target.get("region", "")
                rec["target"] = target.get("target", "")
                res = runners.execute_run(
                    run, target.get("target", ""), outdir / "raw",
                    warmup_s=args.warmup, duration_s=args.duration)
                rec.update(res)
            except Exception as e:  # provisioning or execution blew up
                rec["status"] = "failed"
                rec["error"] = f"{type(e).__name__}: {e}"
            finally:
                if target and not args.keep_targets:
                    try:
                        provision_mod.teardown(run["provider"], run["paradigm"])
                        rec["teardown"] = "ok"
                    except Exception as e:
                        rec["teardown"] = f"FAILED: {e} -- CHECK BILLING"
            rec["ts_end"] = datetime.now(timezone.utc).isoformat()
            mf.write(json.dumps(rec) + "\n")
            mf.flush()
            if rec.get("status") == "ok":
                ok += 1
            else:
                failed += 1
                print(f"    -> {rec.get('status')}: {rec.get('error','')}")

    mins = (time.time() - t_start) / 60
    print(f"\nCampaign finished in {mins:.1f} min. ok={ok} failed={failed} "
          f"of {len(plan)}.")
    print(f"Raw output: {outdir/'raw'}   Attempt log: {manifest}")
    print("Next: python3 scripts/parse_results.py --outdir", args.outdir)
    if failed:
        print(f"NOTE: {failed} run(s) produced no data. Their all_runs.csv cells "
              "will be blank and flagged -- that is correct, not an error.")


if __name__ == "__main__":
    main()
