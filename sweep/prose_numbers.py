#!/usr/bin/env python3
"""
prose_numbers.py -- generates every number quoted in manuscript prose that is
not already covered by the exponent tables or figures, completing the
requirement that no reported value lives outside the generated chain.
Run from the repository root: python3 sweep/prose_numbers.py
Output: recompute-output/prose_numbers.txt (committed; regenerate and diff).
"""
from __future__ import annotations
import csv, json, math, statistics
from pathlib import Path

RO = Path("recompute-output")
PROV = ["aws", "azure", "gcp", "huawei", "alibaba"]
L = []


def emit(s):
    L.append(s)
    print(s)


# ---- p99 fold changes (balanced class, c1 -> c64, median across providers)
pp = list(csv.DictReader(open(RO / "per_phase.csv")))
for r in pp:
    r["concurrency"] = int(r["concurrency"])
emit("p99 fold change c1->c64, balanced class, median across providers:")
for op in ("WRITE", "READ"):
    for para in ("block", "file", "object"):
        folds = []
        for prov in PROV:
            def m(c):
                v = [float(r["lat_p99_ms"]) for r in pp
                     if r["provider"] == prov and r["paradigm"] == para
                     and r["workload"] == "balanced" and r["op"] == op
                     and r["concurrency"] == c and r["lat_p99_ms"]]
                return sum(v) / len(v) if v else None
            a, b = m(1), m(64)
            if a and b:
                folds.append(b / a)
        emit(f"  {op.lower():5} {para:6}: x{statistics.median(folds):.1f} "
             f"(n={len(folds)} providers)")

# ---- consistency with the fixed-concurrency campaign (c16 cells)
# Ratios use the earlier campaign's own metric definitions for comparability
# (its parser's total_throughput field), exactly as manuscript Section 4.5
# states.
def cells(path):
    out = {}
    for r in csv.DictReader(open(path)):
        t = (r.get("total_throughput_mbps") or "").strip()
        if not t or int(r["concurrency"]) != 16:
            continue
        if r.get("mode", "sweep") == "factorial" and "merged" not in str(path):
            continue
        k = (r["provider"], r["paradigm"], r["workload"])
        out.setdefault(k, []).append(float(t))
    return {k: sum(v) / len(v) for k, v in out.items()}


thesis = cells("results-merged/all_runs.csv")
sweep = {}
for p in PROV:
    sweep.update(cells(f"results-sweep-{p}/all_runs.csv"))
ratios, outliers = [], []
for k in sorted(sweep):
    if k in thesis and k[2] in ("balanced", "largeobj"):
        r_ = sweep[k] / thesis[k]
        ratios.append(r_)
        if not 0.5 <= r_ <= 2.0:
            outliers.append((k, round(r_, 2)))
gm = math.exp(sum(math.log(x) for x in ratios) / len(ratios))
emit(f"\nc16 consistency: {len(ratios)} comparable cells; "
     f"{len(ratios) - len(outliers)} within 2x; geometric-mean ratio {gm:.2f}")
emit(f"  outliers (corrected-instrument cells): {outliers}")

# ---- Azure v1/v2 instrument comparison (like-for-like write phases)
v1 = {}
for r in csv.DictReader(open("quarantine/azure-object-v1-runner/all_runs.csv")):
    t = (r.get("total_throughput_mbps") or "").strip()
    if t and r["paradigm"] == "object" and r["workload"] == "balanced":
        v1.setdefault(int(r["concurrency"]), []).append(float(t))
xs = [math.log10(c) for c, vs in v1.items() for _ in vs]
ys = [math.log10(v) for c, vs in v1.items() for v in vs]
n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
b1 = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / \
    sum((x - mx) ** 2 for x in xs)
runs = list(csv.DictReader(open(RO / "runs_recomputed.csv")))
w2c16 = [float(r["write_tput_mib_s"]) for r in runs
         if r["provider"] == "azure" and r["paradigm"] == "object"
         and r["workload"] == "balanced" and int(r["concurrency"]) == 16
         and r.get("write_tput_mib_s")]
b2 = next(r["beta"] for r in csv.DictReader(open(RO / "exponents_recomputed.csv"))
          if r["provider"] == "azure" and r["paradigm"] == "object"
          and r["workload"] == "balanced" and r["operation"] == "write"
          and r["gated_excluded"] == "False")
emit(f"\nAzure instrument (like-for-like, write phases):")
emit(f"  v1 write-only beta = {b1:.4f} (effectively zero, not negative)")
emit(f"  v2 write-phase beta = {b2}")
emit(f"  c16 write-to-write ratio v2/v1 = "
     f"{statistics.mean(w2c16) / statistics.mean(v1[16]):.2f}x")

# ---- design-mix and gate counts quoted in prose
base = {"balanced": 20, "largeobj": 40}
fx = sc = ot = 0
for r in runs:
    c = int(r["concurrency"]); wl = r["workload"]
    ds = float(r["dataset_gb_executed"]) if r["dataset_gb_executed"] else None
    if ds is None:
        ot += 1; continue
    exp = min(80, max(1, round(base[wl] * c / 16)))
    if abs(ds - base[wl]) < 1.5 and c != 16:
        fx += 1
    elif abs(ds - exp) < 1.5:
        sc += 1
    else:
        ot += 1
gated = sum(1 for r in runs if r["cpu_util_pct"]
            and float(r["cpu_util_pct"]) > 80.0)
emit(f"\ndesign mix: fixed={fx} weak-scaled={sc} time-driven/other={ot}")
emit(f"CPU-gated runs (>80% mean): {gated} of {len(runs)} "
     f"({100 * gated / len(runs):.1f}%)")

(RO / "prose_numbers.txt").write_text("\n".join(L) + "\n")
print(f"\nwrote {RO}/prose_numbers.txt")
