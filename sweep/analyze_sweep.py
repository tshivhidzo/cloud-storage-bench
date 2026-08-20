#!/usr/bin/env python3
"""
analyze_sweep.py -- pre-registered analysis for the concurrency-scaling paper.

Implements the analysis plan fixed before data collection:
  * Primary: OLS of log10(total_throughput_mbps) on log10(concurrency), fitted
    per paradigm x provider x workload cell (up to 12 obs: 4 levels x 3 reps).
    Reports beta, SE, 95% CI, R^2 per fitted line.
  * CPU gate: runs whose mpstat mean CPU exceeds 80% are flagged; a
    sensitivity refit excluding gated runs is reported alongside the primary.
  * Saturation: level at which marginal throughput gain drops below 10%.
  * Pooled model (>=2 providers present): mixed-effects with provider random
    intercept + random slope on log concurrency (statsmodels, if available);
    likelihood-ratio test of the random slope = formal test of H4.

Usage (from the laptop, in cloud-storage-bench/):
    python3 sweep/analyze_sweep.py results-sweep-huawei [results-sweep-aws ...]
    python3 sweep/analyze_sweep.py --glob "results-sweep-*"

Outputs into ./sweep-analysis/:
    exponents.csv        one row per fitted line (primary + gated-excluded)
    exponents_table.md   formatted table for the paper
    curves_<provider>.png  throughput-vs-concurrency, faceted by paradigm
Integrity: cells with fewer than 3 concurrency levels of data are reported
with beta blank and flagged low-coverage; nothing is imputed.
"""
from __future__ import annotations
import argparse, csv, glob, math, sys
from collections import defaultdict
from pathlib import Path

CPU_GATE_PCT = 80.0
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179}


def load_rows(dirs):
    rows = []
    for d in dirs:
        f = Path(d) / "all_runs.csv"
        if not f.exists():
            print(f"WARNING: no all_runs.csv in {d}, skipping", file=sys.stderr)
            continue
        for r in csv.DictReader(open(f)):
            if r.get("mode", "sweep") == "factorial":
                continue
            t = (r.get("total_throughput_mbps") or "").strip()
            if not t:
                continue
            rows.append({
                "provider": r["provider"], "paradigm": r["paradigm"],
                "workload": r["workload"], "conc": int(r["concurrency"]),
                "rep": r.get("rep", ""), "tput": float(t),
                "cpu": float(r["cpu_util_pct"]) if (r.get("cpu_util_pct") or "").strip() else None,
            })
    return rows


def ols(xs, ys):
    """Simple OLS y = a + b x. Returns b, se_b, r2, n."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sse = sum(e * e for e in resid)
    sst = sum((y - my) ** 2 for y in ys)
    r2 = 1 - sse / sst if sst > 0 else float("nan")
    dof = n - 2
    se = math.sqrt((sse / dof) / sxx) if dof > 0 else float("nan")
    return {"beta": b, "se": se, "r2": r2, "n": n, "dof": dof}


def fit_cells(rows, exclude_gated=False):
    cells = defaultdict(list)
    for r in rows:
        if exclude_gated and r["cpu"] is not None and r["cpu"] > CPU_GATE_PCT:
            continue
        cells[(r["provider"], r["paradigm"], r["workload"])].append(r)
    out = []
    for (prov, para, wl), rs in sorted(cells.items()):
        levels = sorted({r["conc"] for r in rs})
        xs = [math.log10(r["conc"]) for r in rs]
        ys = [math.log10(r["tput"]) for r in rs]
        gated = sum(1 for r in rs if r["cpu"] is not None and r["cpu"] > CPU_GATE_PCT)
        fit = ols(xs, ys) if len(levels) >= 3 else None
        rec = {"provider": prov, "paradigm": para, "workload": wl,
               "levels": len(levels), "n_runs": len(rs), "cpu_gated_runs": gated,
               "beta": "", "se": "", "ci_lo": "", "ci_hi": "", "r2": "",
               "flag": "" if fit else "low-coverage(<3 levels)"}
        if fit:
            t = T975.get(fit["dof"], 1.96)
            rec.update(beta=round(fit["beta"], 3), se=round(fit["se"], 3),
                       ci_lo=round(fit["beta"] - t * fit["se"], 3),
                       ci_hi=round(fit["beta"] + t * fit["se"], 3),
                       r2=round(fit["r2"], 3))
        # saturation: highest level where marginal gain vs previous >= 10%
        means = {c: sum(r["tput"] for r in rs if r["conc"] == c) /
                    max(1, len([r for r in rs if r["conc"] == c])) for c in levels}
        sat = levels[0]
        for lo, hi in zip(levels, levels[1:]):
            if means[hi] >= means[lo] * 1.10:
                sat = hi
        rec["saturation_level"] = sat
        out.append(rec)
    return out


def mixed_model(rows):
    try:
        import pandas as pd, numpy as np
        import statsmodels.formula.api as smf
        from scipy import stats
    except ImportError:
        return "statsmodels/pandas not installed; pooled model skipped."
    df = pd.DataFrame(rows)
    if df.provider.nunique() < 2:
        return "single provider; pooled model deferred until >=2 legs present."
    df["y"] = np.log10(df.tput); df["x"] = np.log10(df.conc)
    m0 = smf.mixedlm("y ~ x * C(paradigm)", df, groups=df["provider"]).fit(reml=False)
    m1 = smf.mixedlm("y ~ x * C(paradigm)", df, groups=df["provider"],
                     re_formula="~x").fit(reml=False)
    lr = 2 * (m1.llf - m0.llf)
    p = stats.chi2.sf(lr, 2)
    return (f"H4 (provider-dependent slopes): LR={lr:.2f}, p={p:.4g} "
            f"({'supported' if p < 0.05 else 'not supported'}); "
            f"providers={df.provider.nunique()}, N={len(df)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*", help="results-sweep directories")
    ap.add_argument("--glob", dest="pat", default=None)
    ap.add_argument("--outdir", default="./sweep-analysis")
    a = ap.parse_args()
    dirs = list(a.dirs) + (sorted(glob.glob(a.pat)) if a.pat else [])
    if not dirs:
        sys.exit("no input directories; pass paths or --glob 'results-sweep-*'")
    rows = load_rows(dirs)
    if not rows:
        sys.exit("no sweep rows with throughput found")
    out = Path(a.outdir); out.mkdir(exist_ok=True)

    primary = fit_cells(rows)
    gated = fit_cells(rows, exclude_gated=True)
    gmap = {(g["provider"], g["paradigm"], g["workload"]): g for g in gated}
    fields = ["provider", "paradigm", "workload", "levels", "n_runs",
              "cpu_gated_runs", "beta", "se", "ci_lo", "ci_hi", "r2",
              "saturation_level", "flag", "beta_gated_excl"]
    with open(out / "exponents.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for rec in primary:
            g = gmap.get((rec["provider"], rec["paradigm"], rec["workload"]), {})
            rec["beta_gated_excl"] = g.get("beta", "")
            w.writerow(rec)

    lines = ["| Provider | Paradigm | Workload | beta | 95% CI | R2 | sat. | gated |",
             "|---|---|---|---|---|---|---|---|"]
    for rec in primary:
        ci = f"[{rec['ci_lo']}, {rec['ci_hi']}]" if rec["beta"] != "" else "-"
        lines.append(f"| {rec['provider']} | {rec['paradigm']} | {rec['workload']} "
                     f"| {rec['beta'] or '-'} | {ci} | {rec['r2'] or '-'} "
                     f"| c{rec['saturation_level']} | {rec['cpu_gated_runs']} |")
    mm = mixed_model(rows)
    (out / "exponents_table.md").write_text("\n".join(lines) + f"\n\nPooled model: {mm}\n")

    print(f"Fitted {len(primary)} cells from {len(rows)} runs across "
          f"{len({r['provider'] for r in rows})} provider(s).")
    for rec in primary:
        print(f"  {rec['provider']:8} {rec['paradigm']:6} {rec['workload']:9} "
              f"beta={rec['beta'] if rec['beta'] != '' else '  -  '} "
              f"R2={rec['r2'] if rec['r2'] != '' else '-'} sat=c{rec['saturation_level']} "
              f"{rec['flag']}")
    print("Pooled:", mm)
    print(f"Wrote {out}/exponents.csv and exponents_table.md")


if __name__ == "__main__":
    main()
