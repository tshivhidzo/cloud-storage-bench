#!/usr/bin/env python3
"""Review-requested sensitivity and reporting analyses (peer review, r14).

Generates, deterministically from the archived recompute-output tables and
boot_draws.csv, everything the manuscript's review-response additions quote:

1. Completion probabilities (accepted/attempts) with 95% Wilson intervals by
   paradigm x concurrency  -> table_completionprob.tex + macros.
2. Time-limit sensitivity: per-operation OLS refits excluding the 35
   --timelimit runs, vs the archived full fits -> max shift macro.
3. Aggregation sensitivity: per-operation refits on the four concurrency
   level means vs the 12 run-level observations -> max shift macro.
4. CPU-gate threshold sensitivity: gated counts and object-exponent shift
   direction at 70/80/90 percent thresholds -> macros.
5. Sizing-stratum overlap: count of 16-thread runs entering both strata,
   plus mutually exclusive (c16-removed) stratum refits -> macros.
6. Tail-latency reporting: endpoint medians (c1, c64) per operation and
   paradigm, and object folds excluding Azure (different p99 estimator)
   -> macros.  Folds are medians across providers of per-provider ratios
   of rep-mean p99 (the same construction as prose_numbers.py).
7. Bootstrap Monte Carlo uncertainty of the reported p-value -> macros.
8. Provider-sensitivity of the pooled model: random-slope LR test refitted
   without Azure (the visible outlier) -> macros.

All outputs are written with explicit LF newlines. Run from the repository
root: python3 sweep/review_analyses.py
"""
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

OUT = Path("recompute-output")
BASE = {"balanced": 20.0, "largeobj": 40.0}
TOL = 1.5
PROV = ["aws", "azure", "gcp", "huawei", "alibaba"]
OPS = [("write", "write_tput_mib_s"), ("read", "read_tput_mib_s")]
MACROS = {}


def wilson(k, n, z=1.959963984540054):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def ols_beta(pts):
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if n < 3 or sxx == 0 or len(set(xs)) < 3:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def load_runs():
    return list(csv.DictReader(open(OUT / "runs_recomputed.csv")))


def load_full_betas():
    return {(r["provider"], r["paradigm"], r["workload"], r["operation"]):
            float(r["beta"])
            for r in csv.DictReader(open(OUT / "exponents_recomputed.csv"))
            if r.get("beta")}


def perop_points(runs, filt):
    """(cell -> [(log10 c, log10 tput)]) per operation under a run filter."""
    cells = defaultdict(list)
    for r in runs:
        if not filt(r):
            continue
        for op, col in OPS:
            if r[col]:
                cells[(r["provider"], r["paradigm"], r["workload"], op)].append(
                    (math.log10(int(r["concurrency"])),
                     math.log10(float(r[col]))))
    return cells


def refit_max_shift(runs, filt, full):
    worst, cell_n = 0.0, 0
    for key, pts in perop_points(runs, filt).items():
        b = ols_beta(pts)
        if b is None or key not in full:
            continue
        cell_n += 1
        worst = max(worst, abs(b - full[key]))
    return worst, cell_n


def completion_table():
    rows = list(csv.DictReader(open(OUT / "attempts_by_cell.csv")))
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r["paradigm"], int(r["concurrency"]))
        agg[k][0] += int(r["attempts"])
        agg[k][1] += int(r["accepted"])
    lines = [r"\begin{tabular}{lcccc}", r"\toprule",
             r"Paradigm & c=1 & c=4 & c=16 & c=64 \\", r"\midrule"]
    for para in ("block", "file", "object"):
        cells = []
        for c in (1, 4, 16, 64):
            a, k = agg[(para, c)]
            p, lo, hi = wilson(k, a)
            cells.append(f"{p:.2f} [{lo:.2f}, {hi:.2f}]")
        lines.append(para.capitalize() + " & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (OUT / "table_completionprob.tex").write_text(
        "\n".join(lines) + "\n", newline="\n")
    words = {1: "one", 4: "four", 16: "sixteen", 64: "sixtyfour"}
    for c in (1, 4, 16, 64):
        a, k = agg[("object", c)]
        p, lo, hi = wilson(k, a)
        MACROS[f"complObjC{words[c]}"] = f"{p:.2f} [{lo:.2f}, {hi:.2f}]"


def sizing_exclusive(runs, full):
    overlap = 0
    strata = {"fixed": [], "weak": []}
    for r in runs:
        ds = r["dataset_gb_executed"]
        if not ds:
            continue
        ds = float(ds); c = int(r["concurrency"]); wl = r["workload"]
        exp_weak = min(80.0, max(1.0, round(BASE[wl] * c / 16)))
        in_f = abs(ds - BASE[wl]) < TOL
        in_w = abs(ds - exp_weak) < TOL
        if in_f and in_w:
            overlap += 1
            continue  # exclusive assignment: drop the shared c16 runs
        if in_f:
            strata["fixed"].append(r)
        if in_w:
            strata["weak"].append(r)
    MACROS["sizeOverlapRuns"] = str(overlap)
    worst, n_est = 0.0, 0
    order_ok = True
    per_para = defaultdict(list)
    for name, rs in strata.items():
        for key, pts in perop_points(rs, lambda r: True).items():
            b = ols_beta(pts)
            if b is None:
                continue
            n_est += 1
            if key in full:
                worst = max(worst, abs(b - full[key]))
            if key[2] == "balanced":
                per_para[key[1]].append(b)
    if per_para.get("object") and per_para.get("block"):
        order_ok = min(per_para["object"]) > max(per_para["block"])
    MACROS["sizeExclMaxShift"] = f"{worst:.2f}"
    MACROS["sizeExclCells"] = str(n_est)
    MACROS["sizeExclOrderPreserved"] = "preserved" if order_ok else "NOT preserved"


def cpu_thresholds(runs, full):
    words = {70: "Seventy", 80: "Eighty", 90: "Ninety"}
    for th in (70, 80, 90):
        gated = [r for r in runs if r["cpu_util_pct"]
                 and float(r["cpu_util_pct"]) > th]
        MACROS[f"cpuGatedAt{words[th]}"] = str(len(gated))
        deltas = []
        cells = perop_points(runs, lambda r: not (
            r["cpu_util_pct"] and float(r["cpu_util_pct"]) > th))
        for key, pts in cells.items():
            if key[1] != "object" or key not in full:
                continue
            b = ols_beta(pts)
            if b is not None:
                deltas.append(b - full[key])
        MACROS[f"cpuObjMinDeltaAt{words[th]}"] = f"{min(deltas):+.2f}" if deltas else "n/a"


def latency_endpoints():
    pp = list(csv.DictReader(open(OUT / "per_phase.csv")))
    def rep_mean(prov, para, op, c):
        v = [float(r["lat_p99_ms"]) for r in pp
             if r["provider"] == prov and r["paradigm"] == para
             and r["workload"] == "balanced" and r["op"] == op
             and int(r["concurrency"]) == c and r["lat_p99_ms"]]
        return sum(v) / len(v) if v else None
    for op in ("WRITE", "READ"):
        for para in ("block", "file", "object"):
            a_vals, b_vals, folds, folds_ex = [], [], [], []
            for prov in PROV:
                a, b = rep_mean(prov, para, op, 1), rep_mean(prov, para, op, 64)
                if a and b:
                    a_vals.append(a); b_vals.append(b)
                    folds.append(b / a)
                    if not (para == "object" and prov == "azure"):
                        folds_ex.append(b / a)
            tag = op.capitalize() + para.capitalize()
            MACROS[f"pEndCone{tag}"] = f"{statistics.median(a_vals):.1f}"
            MACROS[f"pEndCsixtyfour{tag}"] = f"{statistics.median(b_vals):.1f}"
            if para == "object":
                MACROS[f"pFoldExAz{op.capitalize()}Object"] = \
                    f"{statistics.median(folds_ex):.1f}"


def bootstrap_mc():
    rows = [r for r in csv.DictReader(open(OUT / "boot_draws.csv"))
            if r["accepted"] in ("True", "1", "true")]
    n = len(rows)
    obs = 0.4438
    k = sum(1 for r in rows if float(r["lr"]) >= obs)
    p = (1 + k) / (1 + n)
    se = math.sqrt(p * (1 - p) / n)
    MACROS["bootValidDraws"] = str(n)
    MACROS["bootP"] = f"{p:.4f}"
    MACROS["bootMCSE"] = f"{se:.3f}"
    MACROS["bootPLow"] = f"{max(0.0, p - 1.96 * se):.2f}"
    MACROS["bootPHigh"] = f"{min(1.0, p + 1.96 * se):.2f}"



FORMULA = "y ~ x * C(paradigm) * C(workload)"


def _frame(runs, exclude_provider=None):
    import pandas as pd
    recs = [r for r in runs if r["combined_tput_mib_s"]
            and r["provider"] != exclude_provider]
    return pd.DataFrame({
        "y": [math.log10(float(r["combined_tput_mib_s"])) for r in recs],
        "x": [math.log10(int(r["concurrency"])) for r in recs],
        "paradigm": [r["paradigm"] for r in recs],
        "workload": [r["workload"] for r in recs],
        "provider": [r["provider"] for r in recs]})


def select_fit(dfb, re_formula):
    """The archived validity policy (refit_exponents._fit_model), returning
    the selected fit object: maximum likelihood (reml=False) with every
    optimizer in the ladder; keep the converged fit with the highest FINITE
    log-likelihood; None if no optimizer qualifies.  A .converged flag alone
    is not accepted."""
    import warnings
    import statsmodels.formula.api as smf
    best, best_method = None, None
    for method in ("default", "lbfgs", "powell"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                kw = {} if method == "default" else {"method": method}
                mdl = (smf.mixedlm(FORMULA, dfb, groups=dfb["provider"],
                                   re_formula=re_formula) if re_formula
                       else smf.mixedlm(FORMULA, dfb, groups=dfb["provider"]))
                m = mdl.fit(reml=False, **kw)
            except Exception:
                continue
        llf = float(m.llf)
        if not (bool(getattr(m, "converged", False)) and math.isfinite(llf)):
            continue
        if best is None or llf > float(best.llf):
            best, best_method = m, method
    if best is not None:
        best._review_method = best_method
        best._review_reml = bool(getattr(best.model, "reml", False))
    return best


def pooled_without_azure(runs):
    """Provider-sensitivity: the random-slope LR test refitted without Azure
    under the identical ML validity policy as the primary analysis."""
    from scipy import stats
    d = _frame(runs, exclude_provider="azure")
    n, a = select_fit(d, None), select_fit(d, "~x")
    if n is None or a is None or float(a.llf) < float(n.llf):
        MACROS["noAzLR"] = "n/a"; MACROS["noAzP"] = "n/a"; MACROS["noAzN"] = str(len(d))
        return
    lr = 2 * (float(a.llf) - float(n.llf))
    pval = 0.5 * stats.chi2.sf(lr, 1) + 0.5 * stats.chi2.sf(lr, 2)
    MACROS["noAzLR"] = f"{lr:.2f}"
    MACROS["noAzP"] = f"{pval:.2f}"
    MACROS["noAzN"] = str(len(d))
    MACROS["noAzMethods"] = f"{n._review_method}/{a._review_method}"


def pooled_fe_table(runs):
    """Full fixed-effect output of the pooled null model and the variance
    components of both models, taken from the fits SELECTED under the
    archived ML validity policy (never a default or unconverged fit).
    Writes table_pooledfe.tex, pooled_covariance.txt and pooled_fit_flags.json."""
    import json
    import numpy as np
    d = _frame(runs)
    f = select_fit(d, None)
    fa = select_fit(d, "~x")
    assert f is not None and fa is not None, "no converged finite ML fit"
    lr_full = 2 * (float(fa.llf) - float(f.llf))
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"Term & Estimate & SE & 95\% CI \\", r"\midrule"]
    for name in f.fe_params.index:
        est = f.fe_params[name]; se = f.bse_fe[name]
        lo, hi = est - 1.96 * se, est + 1.96 * se
        disp = (name.replace("C(paradigm)[T.", "paradigm=")
                    .replace("C(workload)[T.", "workload=")
                    .replace("]", "").replace(":", " $\\times$ ")
                    .replace("_", "\\_"))
        lines.append(f"{disp} & {est:.3f} & {se:.3f} & "
                     f"$[{lo:.3f}, {hi:.3f}]$ \\\\")
    d["res"] = f.resid
    grp_sd = d.groupby(["paradigm", "workload"])["res"].std()
    C = np.array(fa.cov_re, dtype=float)
    v0, v1, cv = C[0, 0], C[1, 1], C[0, 1]
    corr = cv / math.sqrt(v0 * v1) if v0 > 0 and v1 > 0 else float("nan")
    eig = np.linalg.eigvalsh(C)
    lines += [r"\midrule",
              f"Null model: provider intercept variance & {float(f.cov_re.iloc[0,0]):.4f}" + r" & & \\\\",
              f"Null model: residual variance & {f.scale:.4f}" + r" & & \\\\",
              f"Alternative model: intercept variance & {v0:.3e}" + r" & & \\\\",
              f"Alternative model: slope variance & {v1:.3e}" + r" & & \\\\",
              f"Alternative model: intercept--slope covariance & {cv:.3e}" + r" & & \\\\",
              f"Alternative model: implied correlation & {corr:.6f}" + r" & & \\\\",
              f"Alternative model: residual variance & {fa.scale:.4f}" + r" & & \\\\",
              r"\bottomrule", r"\end{tabular}"]
    (OUT / "table_pooledfe.tex").write_text("\n".join(lines) + "\n",
                                            newline="\n")
    MACROS["pooledFeN"] = str(len(d))
    MACROS["altSlopeVar"] = f"{v1:.3e}"
    MACROS["altCov"] = f"{cv:.3e}"
    MACROS["altIntVar"] = f"{v0:.3e}"
    MACROS["altCorr"] = f"{corr:.6f}"
    MACROS["altMinEig"] = f"{eig.min():.3e}"
    MACROS["altPSD"] = "positive semidefinite" if eig.min() >= -1e-12 else "NOT positive semidefinite"
    MACROS["nullResidSdByGroup"] = "; ".join(
        f"{k[0]}/{k[1]} {v:.3f}" for k, v in grp_sd.items())
    MACROS["nullResidSdMin"] = f"{float(grp_sd.min()):.3f}"
    MACROS["nullResidSdMax"] = f"{float(grp_sd.max()):.3f}"
    MACROS["reviewLlfNull"] = f"{float(f.llf):.6f}"
    MACROS["reviewLlfAlt"] = f"{float(fa.llf):.6f}"
    MACROS["reviewLR"] = f"{lr_full:.4f}"
    flags = {"null": {"method": f._review_method, "converged": bool(f.converged),
                      "reml": f._review_reml, "llf": float(f.llf)},
             "alt": {"method": fa._review_method, "converged": bool(fa.converged),
                     "reml": fa._review_reml, "llf": float(fa.llf)},
             "lr": lr_full, "n": int(len(d))}
    (OUT / "pooled_fit_flags.json").write_text(json.dumps(flags, indent=1) + "\n",
                                               newline="\n")
    with open(OUT / "pooled_covariance.txt", "w", newline="\n") as fh:
        fh.write("Fits selected under the archived ML validity policy (reml=False; "
                 "best finite converged log-likelihood across default/lbfgs/powell)\n")
        fh.write(f"  null: method={f._review_method} converged={f.converged} reml={f._review_reml} llf={float(f.llf)!r}\n")
        fh.write(f"  alt : method={fa._review_method} converged={fa.converged} reml={fa._review_reml} llf={float(fa.llf)!r}\n")
        fh.write(f"  LR = {lr_full!r}  (must equal the archived pooled_model.txt LR)\n")
        fh.write("Alternative (random-slope) model: provider random-effects covariance, full precision\n")
        fh.write(f"  var(intercept) = {v0!r}\n  var(slope)     = {v1!r}\n  cov            = {cv!r}\n")
        fh.write(f"  implied correlation = {corr!r}\n  eigenvalues = {eig.tolist()!r}\n")
        fh.write("Null (random-intercept) model:\n")
        fh.write(f"  var(intercept) = {float(f.cov_re.iloc[0,0])!r}\n  residual variance = {f.scale!r}\n")
        fh.write("Null-model residual SD by paradigm/workload group:\n")
        for k, v in grp_sd.items():
            fh.write(f"  {k[0]}/{k[1]}: {v!r}\n")


T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


def ols_full(pts):
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    n = len(xs); mx = statistics.mean(xs); my = statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    dof = n - 2
    se = math.sqrt(sum(r * r for r in res) / dof / sxx) if dof > 0 else float("nan")
    return b, se, res, dof


def _diag_cells(runs, cols, use_full_key):
    cells = defaultdict(list)
    for r in runs:
        for op, col in cols:
            if r[col]:
                key = (r["provider"], r["paradigm"], r["workload"], op)
                cells[key].append((int(r["concurrency"]), int(r["rep"]),
                                   math.log10(float(r[col]))))
    return cells


def diagnostics(runs, full, cols=None, tag="perop", fname="diagnostics_perop.csv"):
    """Residual diagnostics and interval comparison for every fitted cell:
    per-level residual spread (with a near-zero-denominator flag), a
    regression lack-of-fit F test separating within-level pure error from
    departure of level means from the line, the run-level t interval versus
    the interval from the level means (an aggregation sensitivity, not a
    validated bound), lag-1 residual autocorrelation in execution order,
    and the degrees of freedom of every cell."""
    from scipy import stats
    cols = cols or OPS
    cells = _diag_cells(runs, cols, True)
    out = []
    for key, obs in sorted(cells.items()):
        obs.sort()
        levels = sorted({c for c, _, _ in obs})
        if len(levels) < 3 or len(obs) < 6:
            continue
        pts = [(math.log10(c), y) for c, _, y in obs]
        b, se, res, dof = ols_full(pts)
        hw_run = T975.get(dof, 2.0) * se
        by_lvl = defaultdict(list)
        for (c, _, y), e in zip(obs, res):
            by_lvl[c].append((y, e))
        # pure error (within level) and lack of fit (level means vs line)
        sse = sum(e * e for e in res)
        sspe = sum(sum((y - statistics.mean(v for v, _ in vals)) ** 2
                       for y, _ in vals) for vals in by_lvl.values())
        df_pe = sum(len(v) - 1 for v in by_lvl.values())
        df_lof = len(levels) - 2
        sslof = max(sse - sspe, 0.0)
        if df_lof > 0 and df_pe > 0 and sspe > 0:
            f_lof = (sslof / df_lof) / (sspe / df_pe)
            p_lof = float(stats.f.sf(f_lof, df_lof, df_pe))
        else:
            f_lof, p_lof = float("nan"), float("nan")
        sds = [statistics.pstdev([e for _, e in v]) for v in by_lvl.values()
               if len(v) > 1]
        min_sd = min(sds) if sds else float("nan")
        sd_ratio = (max(sds) / min_sd) if sds and min_sd > 0 else float("nan")
        lm = [(math.log10(c), statistics.mean(y for y, _ in by_lvl[c]))
              for c in levels]
        b_lm, se_lm, _, dof_lm = ols_full(lm)
        hw_lm = T975.get(dof_lm, 2.0) * se_lm if dof_lm > 0 else float("nan")
        num = sum(res[i] * res[i + 1] for i in range(len(res) - 1))
        den = sum(e * e for e in res)
        lag1 = num / den if den > 0 else float("nan")
        out.append({"provider": key[0], "paradigm": key[1], "workload": key[2],
                    "operation": key[3], "n": len(obs), "levels": len(levels),
                    "df_runlevel": dof, "df_levelmeans": dof_lm,
                    "df_pure_error": df_pe, "df_lack_of_fit": df_lof,
                    "beta": round(b, 4),
                    "ci_halfwidth_runlevel": round(hw_run, 4),
                    "ci_halfwidth_levelmeans": round(hw_lm, 4),
                    "resid_sd_ratio_max_min": round(sd_ratio, 2),
                    "min_level_resid_sd": round(min_sd, 5),
                    "near_zero_level_sd": int(min_sd < 0.005),
                    "lack_of_fit_F": round(f_lof, 3),
                    "lack_of_fit_p": round(p_lof, 4),
                    "lag1_resid_autocorr": round(lag1, 3),
                    "excl0_runlevel": int(abs(b) > hw_run),
                    "excl0_levelmeans": int(abs(b) > hw_lm)})
    with open(OUT / fname, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()), lineterminator="\n")
        w.writeheader(); w.writerows(out)
    ratios = [o["ci_halfwidth_levelmeans"] / o["ci_halfwidth_runlevel"]
              for o in out if o["ci_halfwidth_runlevel"] > 0]
    sdr = [o["resid_sd_ratio_max_min"] for o in out
           if not math.isnan(o["resid_sd_ratio_max_min"])]
    lag = [o["lag1_resid_autocorr"] for o in out
           if not math.isnan(o["lag1_resid_autocorr"])]
    lof = [o["lack_of_fit_p"] for o in out if not math.isnan(o["lack_of_fit_p"])]
    T = tag.capitalize()
    MACROS[f"diag{T}Cells"] = str(len(out))
    MACROS[f"diag{T}CiRatioMedian"] = f"{statistics.median(ratios):.1f}"
    MACROS[f"diag{T}CiRatioMax"] = f"{max(ratios):.1f}"
    MACROS[f"diag{T}SdRatioMedian"] = f"{statistics.median(sdr):.1f}"
    MACROS[f"diag{T}SdRatioAboveThree"] = str(sum(1 for s in sdr if s > 3))
    MACROS[f"diag{T}NearZeroSd"] = str(sum(o["near_zero_level_sd"] for o in out))
    MACROS[f"diag{T}LagMedian"] = f"{statistics.median(lag):.2f}"
    MACROS[f"diag{T}LagAboveHalf"] = str(sum(1 for l in lag if l > 0.5))
    MACROS[f"diag{T}LofSig"] = str(sum(1 for q in lof if q < 0.05))
    MACROS[f"diag{T}LofCells"] = str(len(lof))
    MACROS[f"diag{T}ZeroStatusChanges"] = str(sum(
        1 for o in out if o["excl0_runlevel"] != o["excl0_levelmeans"]))
    MACROS[f"diag{T}ExclZeroRun"] = str(sum(o["excl0_runlevel"] for o in out))
    MACROS[f"diag{T}ExclZeroLm"] = str(sum(o["excl0_levelmeans"] for o in out))
    exc = [o for o in out if o["n"] != 12 or o["levels"] != 4]
    MACROS[f"diag{T}Exceptions"] = "; ".join(
        f"{o['provider']} {o['paradigm']} {o['workload']} {o['operation']}: "
        f"n={o['n']}, {o['levels']} levels, df={o['df_runlevel']}" for o in exc) or "none"
    # headline survival: object balanced cells excluding zero under level means
    ob = [o for o in out if o["paradigm"] == "object" and o["workload"] == "balanced"]
    MACROS[f"diag{T}ObjBalExclLm"] = str(sum(o["excl0_levelmeans"] for o in ob))
    MACROS[f"diag{T}ObjBalCells"] = str(len(ob))
    fb = [o for o in out if o["paradigm"] == "file" and o["workload"] == "balanced"]
    MACROS[f"diag{T}FileBalExclLm"] = str(sum(o["excl0_levelmeans"] for o in fb))
    MACROS[f"diag{T}FileBalCells"] = str(len(fb))


def timelimit_evidence(runs):
    """Completion indicators for every phase of every time-limited run:
    bytes moved versus the executed dataset target (ratio ~1 = completed),
    elapsed time versus the 600 s limit.  Written to timelimit_phases.csv."""
    pp = list(csv.DictReader(open(OUT / "per_phase.csv")))
    rmap = {r["run_id"]: r for r in runs}
    tl = {r["run_id"] for r in runs if r["timelimit"] == "True"}
    rows = []
    for p in pp:
        if p["run_id"] not in tl:
            continue
        r = rmap[p["run_id"]]
        target = float(r["dataset_gb_executed"]) * 1024 if r["dataset_gb_executed"] else float("nan")
        ratio = float(p["mib"]) / target if target else float("nan")
        rows.append({"run_id": p["run_id"], "op": p["op"], "mib": p["mib"],
                     "target_mib": round(target, 1), "completion_ratio": round(ratio, 4),
                     "elapsed_s": p["elapsed_s"],
                     "hit_limit": int(float(p["elapsed_s"]) >= 590),
                     "in_workload_level_rate": int(bool(r["combined_tput_mib_s"]))})
    with open(OUT / "timelimit_phases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    hit = [x for x in rows if x["hit_limit"]]
    complete = [x for x in rows if x["completion_ratio"] >= 0.99]
    MACROS["tlRuns"] = str(len(tl))
    MACROS["tlPhases"] = str(len(rows))
    MACROS["tlPhasesHit"] = str(len(hit))
    MACROS["tlPhasesComplete"] = str(len(complete))
    MACROS["tlHitMinRatio"] = f"{min(x['completion_ratio'] for x in hit):.2f}" if hit else "n/a"
    MACROS["tlHitMaxRatio"] = f"{max(x['completion_ratio'] for x in hit):.2f}" if hit else "n/a"
    MACROS["tlMaxElapsedNotHit"] = f"{max(float(x['elapsed_s']) for x in rows if not x['hit_limit']):.0f}"


def sizing_exclusive_detail(runs):
    """Same-cell comparison for the exclusive assignment: which stratum
    cells survive removing the shared c16 runs, and which are lost."""
    def build(exclusive):
        S = {"fixed": [], "weak": []}
        for r in runs:
            ds = r["dataset_gb_executed"]
            if not ds:
                continue
            ds = float(ds); c = int(r["concurrency"]); wl = r["workload"]
            ew = min(80.0, max(1.0, round(BASE[wl] * c / 16)))
            f = abs(ds - BASE[wl]) < TOL; w = abs(ds - ew) < TOL
            if exclusive and f and w:
                continue
            if f: S["fixed"].append(r)
            if w: S["weak"].append(r)
        cells = {}
        for st, rs in S.items():
            for key, pts in perop_points(rs, lambda r: True).items():
                if len({x for x, _ in pts}) >= 3:
                    cells[(st,) + key] = ols_beta(pts)
        return cells
    inc, exc = build(False), build(True)
    kept = sorted(set(inc) & set(exc)); lost = sorted(set(inc) - set(exc))
    with open(OUT / "sizing_exclusion.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["stratum", "provider", "paradigm", "workload", "operation",
                    "beta_inclusive", "beta_exclusive", "status"])
        for k in sorted(inc):
            w.writerow(list(k) + [f"{inc[k]:.4f}",
                                  f"{exc[k]:.4f}" if k in exc else "",
                                  "kept" if k in exc else "lost"])
    shifts = [abs(exc[k] - inc[k]) for k in kept]
    MACROS["sizeExclKept"] = str(len(kept))
    MACROS["sizeExclLost"] = str(len(lost))
    MACROS["sizeExclSameCellMaxShift"] = f"{max(shifts):.2f}" if shifts else "n/a"
    lost_bal = sorted({(k[1], k[2]) for k in lost if k[3] == "balanced"})
    MACROS["sizeExclLostList"] = "; ".join(
        f"{p.capitalize()} {para}" for p, para in lost_bal)
    MACROS["sizeExclHuaweiObjLost"] = "lost" if any(
        k[1] == "huawei" and k[2] == "object" for k in lost) else "retained"
    MACROS["sizeExclAlibabaFileLost"] = "lost" if any(
        k[1] == "alibaba" and k[2] == "file" and k[0] == "fixed" for k in lost) else "retained"


def completion_by_cell_full():
    import sys
    sys.path.insert(0, "sweep")
    import sensitivity_analysis as SA
    rows = SA.load_attempts()
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r["provider"], r["paradigm"], r["workload"], r["concurrency"])
        agg[k][0] += 1
        if r["status"] == "ok":
            agg[k][1] += 1
    with open(OUT / "completion_by_cell_full.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["provider", "paradigm", "workload", "concurrency",
                    "attempts", "accepted", "p_hat", "wilson_lo", "wilson_hi"])
        for k in sorted(agg):
            a, ok = agg[k]
            p, lo, hi = wilson(ok, a)
            w.writerow(list(k) + [a, ok, f"{p:.3f}", f"{lo:.3f}", f"{hi:.3f}"])


def main():
    runs = load_runs()
    full = load_full_betas()
    completion_table()
    tl_shift, tl_cells = refit_max_shift(
        runs, lambda r: r["timelimit"] != "True", full)
    MACROS["tlMaxShift"] = f"{tl_shift:.2f}"
    MACROS["tlCells"] = str(tl_cells)
    # cell-mean aggregation sensitivity
    worst = 0.0
    means = defaultdict(lambda: defaultdict(list))
    for r in runs:
        for op, col in OPS:
            if r[col]:
                means[(r["provider"], r["paradigm"], r["workload"], op)][
                    int(r["concurrency"])].append(float(r[col]))
    for key, by_c in means.items():
        pts = [(math.log10(c), math.log10(statistics.mean(v)))
               for c, v in by_c.items()]
        b = ols_beta(pts)
        if b is not None and key in full:
            worst = max(worst, abs(b - full[key]))
    MACROS["cellMeanMaxShift"] = f"{worst:.2f}"
    sizing_exclusive(runs, full)
    cpu_thresholds(runs, full)
    latency_endpoints()
    bootstrap_mc()
    pooled_without_azure(runs)
    pooled_fe_table(runs)
    diagnostics(runs, full)
    full_comb = {(r["provider"], r["paradigm"], r["workload"], "combined"): float(r["beta"])
                 for r in csv.DictReader(open(OUT / "exponents_recomputed.csv"))
                 if r.get("beta") and r["operation"] == "combined"}
    diagnostics(runs, full_comb, cols=[("combined", "combined_tput_mib_s")],
                tag="combined", fname="diagnostics_combined.csv")
    timelimit_evidence(runs)
    sizing_exclusive_detail(runs)
    completion_by_cell_full()
    with open(OUT / "review_macros.tex", "w", newline="\n") as f:
        for k, v in MACROS.items():
            f.write("\\newcommand{\\%s}{%s}\n" % (k, v))
    for k, v in MACROS.items():
        print(f"{k} = {v}")


if __name__ == "__main__":
    main()
