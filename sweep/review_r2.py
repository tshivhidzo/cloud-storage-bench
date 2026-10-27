#!/usr/bin/env python3
"""
review_r2.py -- reanalysis of the archived v2.1 campaign for the second
round of comments on the Future Internet revision (October 2026).

Nothing here is new measurement. Every value is computed from the archived
artefacts already published with tag sweep-v2.1:
  v21-output/runs.csv            (analyze_v21.py, one row per accepted run)
  results-rerun-v21/<p>/.../raw  (elbencho CSVs, runner CSVs, mpstat -P ALL)
  results-rerun-v21/*/run_manifest.jsonl
  recompute-output/runs_recomputed.csv   (earlier campaign, per run)

Outputs (to --out, default v21-output/review-r2/):
  phase_coverage.csv     planned vs measured write and read phases
  lack_of_fit.csv        pure-error lack-of-fit F test per primary cell
  level_gains.csv        level means, repeat ranges and level-to-level gains
  common_range.csv       per-operation exponents refitted over 1-16 threads
  replication_matched.csv  earlier vs present exponents over matched levels
  ext128_exponents.csv   prespecified object exponents over 1-128 threads
  cpu_gates.csv          per-run CPU gates (amendment section C)
  cpu_gated_refits.csv   prespecified sensitivity refits without gated runs
  phase_cpu.csv          phase-aligned client CPU per object run
  host_ratios.csv        64-thread, 128-thread and two-host values per repeat
  d5_hosts.csv           Azure two-host test: each host, each repeat, each phase
  accounting.json        attempts and invocations, by definition
  r2_macros.tex, tab_r2_*.tex, figures/fig_r2_*.png  (read by the manuscript)
"""
from __future__ import annotations
import argparse, csv, json, math, re, statistics as st
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy import stats

PROV = ["aws", "azure", "gcp", "huawei", "alibaba"]
PNAME = {"aws": "AWS", "azure": "Azure", "gcp": "GCP", "huawei": "Huawei", "alibaba": "Alibaba"}
PARA = ["block", "file", "object"]
MB_TO_MIB = 1e6 / 1048576
COL = {"aws": "#E69F00", "azure": "#0072B2", "gcp": "#009E73", "huawei": "#D55E00", "alibaba": "#CC79A7"}  # as make_v21_paper.py


def num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def rd(p):
    return list(csv.DictReader(open(p, newline="")))


def wcsv(path, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader(); w.writerows(rows)


def fit(xs, ys):
    """OLS of log10 y on log10 x; run-level and level-mean 95% intervals."""
    x = np.log10(np.asarray(xs, float)); y = np.log10(np.asarray(ys, float))
    n = len(x)
    levels = sorted(set(xs))
    out = dict(n=n, L=len(levels), levels="/".join(str(int(c)) for c in levels))
    if n < 3 or len(levels) < 2:
        return out
    b, a = np.polyfit(x, y, 1)
    res = y - (a + b * x)
    sxx = ((x - x.mean()) ** 2).sum()
    se = math.sqrt((res ** 2).sum() / (n - 2) / sxx)
    h = stats.t.ppf(0.975, n - 2) * se
    out.update(beta=b, lo_run=b - h, hi_run=b + h)
    if len(levels) >= 3:
        lm = np.array([np.mean(y[np.asarray(xs) == c]) for c in levels])
        lx = np.log10(np.asarray(levels, float))
        bm, am = np.polyfit(lx, lm, 1)
        rm = lm - (am + bm * lx)
        sem = math.sqrt((rm ** 2).sum() / (len(levels) - 2) / ((lx - lx.mean()) ** 2).sum())
        hm = stats.t.ppf(0.975, len(levels) - 2) * sem
        out.update(beta_mean=bm, lo_mean=bm - hm, hi_mean=bm + hm)
    return out


def lack_of_fit(xs, ys):
    """Pure-error lack-of-fit F test of the straight line on log-log axes."""
    x = np.log10(np.asarray(xs, float)); y = np.log10(np.asarray(ys, float))
    xs = np.asarray(xs)
    levels = sorted(set(xs.tolist()))
    n, L = len(x), len(levels)
    if L < 3 or n - L < 1:
        return None
    b, a = np.polyfit(x, y, 1)
    sse = ((y - (a + b * x)) ** 2).sum()
    sspe = sum(((y[xs == c] - y[xs == c].mean()) ** 2).sum() for c in levels)
    sslof = sse - sspe
    df1, df2 = L - 2, n - L
    if sspe <= 0:
        return dict(F=float("inf"), df1=df1, df2=df2, p=0.0, share_lof=1.0)
    F = (sslof / df1) / (sspe / df2)
    return dict(F=F, df1=df1, df2=df2, p=float(1 - stats.f.cdf(F, df1, df2)),
                share_lof=sslof / sse if sse > 0 else 0.0)


# ------------------------------------------------------------------ mpstat
MP_HDR = re.compile(r"^(\d\d:\d\d:\d\d)(?:\s+(?:AM|PM))?\s+CPU\s")
MP_ROW = re.compile(r"^(\d\d:\d\d:\d\d)(?:\s+(AM|PM))?\s+(all|\d+)\s+(.*)$")
MP_DATE = re.compile(r"\s(\d\d)/(\d\d)/(\d{2,4})\s")


def read_mpstat(path):
    """List of samples: (datetime naive, {'all': (busy, busy_noiowait), core: ...})."""
    out, cols, day, prev_t = [], None, None, None
    cur_t, cur = None, {}
    for line in open(path, errors="ignore"):
        if day is None:
            m = MP_DATE.search(line)
            if m:
                mm, dd, yy = map(int, m.groups())
                day = datetime(yy if yy > 999 else 2000 + yy, mm, dd)
                continue
        m = MP_HDR.match(line)
        if m:
            parts = line.split()
            cols = parts[parts.index("CPU") + 1:]
            continue
        m = MP_ROW.match(line)
        if not m or cols is None or day is None:
            continue
        hh, mi, ss = map(int, m.group(1).split(":"))
        if m.group(2) == "PM" and hh != 12:
            hh += 12
        elif m.group(2) == "AM" and hh == 12:
            hh = 0
        t = day.replace(hour=hh, minute=mi, second=ss)
        if prev_t is not None and t < prev_t - timedelta(hours=1):
            day += timedelta(days=1); t += timedelta(days=1)
        vals = dict(zip(cols, map(float, m.group(4).split())))
        idle, iow = vals.get("%idle", 0.0), vals.get("%iowait", 0.0)
        if t != cur_t:
            if cur_t is not None:
                out.append((cur_t, cur))
            cur_t, cur = t, {}
        cur[m.group(3)] = (100 - idle - iow, 100 - idle)
        prev_t = t
    if cur_t is not None:
        out.append((cur_t, cur))
    return [(t, s) for t, s in out if "all" in s]


def summarise_cpu(samples):
    if not samples:
        return {}
    allb = [s["all"][0] for _, s in samples]
    cores = sorted(k for k in samples[0][1] if k != "all")
    core_busy = {c: [s[c][1] for _, s in samples if c in s] for c in cores}
    busiest = [max(s[c][0] for c in cores if c in s) for _, s in samples]
    hot = {c: sum(v > 95 for v in vs) / len(vs) for c, vs in core_busy.items() if vs}
    core_cpu = {c: [s[c][0] for _, s in samples if c in s] for c in cores}
    hot_cpu = {c: sum(v > 95 for v in vs) / len(vs) for c, vs in core_cpu.items() if vs}
    return dict(n_samples=len(samples), cpu_all=st.mean(allb), cpu_maxcore=st.mean(busiest),
                share_all_ge90=sum(v >= 90 for v in allb) / len(allb),
                share_all_ge80=sum(v >= 80 for v in allb) / len(allb),
                max_core_share_gt95=max(hot.values()) if hot else 0.0,
                max_core_share_gt95_noiowait=max(hot_cpu.values()) if hot_cpu else 0.0)


def elbencho_phases(path):
    """(op, start UTC naive, seconds) for the final WRITE/READ phases."""
    rows = list(csv.DictReader(open(path)))
    out = {}
    for r in rows:
        op = r["operation"].lower()
        if op not in ("write", "read"):
            continue
        iso = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", r["ISO date"])
        t0 = datetime.fromisoformat(iso).astimezone(timezone.utc).replace(tzinfo=None)
        out[op] = (t0, float(r["time ms [last]"]) / 1000.0)
    return out


def phase_slices(samples, phases, runner):
    """Split mpstat samples by measured phase. Runner phases are fixed 1200 s windows."""
    if not samples:
        return {}
    if runner:
        t0 = samples[0][0] - timedelta(seconds=5)
        win = {"write": (t0, t0 + timedelta(seconds=1200)), "read": (t0 + timedelta(seconds=1200), t0 + timedelta(seconds=2400))}
        offset = timedelta(0)
    else:
        if not phases:
            return {}
        first = min(v[0] for v in phases.values())
        # host clock vs UTC: round the difference to whole hours (mpstat prints local time)
        d = (samples[0][0] - first).total_seconds()
        offset = timedelta(hours=round(d / 3600))
        win = {op: (t, t + timedelta(seconds=s)) for op, (t, s) in phases.items()}
    out = {}
    for op, (a, b) in win.items():
        # a sample at time t covers (t-5 s, t]; keep samples whose interval lies in the phase
        sl = [(t, s) for t, s in samples if a + offset + timedelta(seconds=5) <= t <= b + offset]
        out[op] = summarise_cpu(sl)
    return out


def raw_dir(root, p):
    return root / "results-rerun-v21" / p / f"results-rerun-v21-{p}" / "raw"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ROOT = Path(a.root)
    OUT = Path(a.out) if a.out else ROOT / "v21-output" / "review-r2"
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    runs = rd(ROOT / "v21-output" / "runs.csv")
    for r in runs:
        r["conc"] = int(r["conc"])
        for k in ("write_tput", "read_tput", "combined_tput", "write_p99_ms", "read_p99_ms", "cpu_all", "cpu_maxcore"):
            r[k] = num(r.get(k))
    prim = [r for r in runs if r["mode"] == "primary"]
    M = []
    # Exponents at full precision. exponents.csv stores 4 decimals, and rounding those again to
    # 3 decimals moved four printed values by 0.001 (double rounding); every exponent printed in
    # the manuscript is therefore taken from these full-precision fits.
    EXA = {}
    for para in PARA:
        for p in PROV:
            for op in ("write", "read"):
                pts = [(r["conc"], r[f"{op}_tput"]) for r in prim if r["provider"] == p and r["paradigm"] == para and r[f"{op}_tput"]]
                EXA[(p, para, op)] = fit(*zip(*pts))
    V1A = {(e["provider"], e["paradigm"], e["operation"]): float(e["beta"]) for e in rd(ROOT / "recompute-output" / "exponents_recomputed.csv")
           if e["workload"] == "balanced" and num(e["beta"]) is not None}
    def mac(name, val):
        M.append(f"\\newcommand{{\\{name}}}{{{val}}}\n")

    # ---------------- 1. phase coverage ----------------
    cov = []
    for para in PARA:
        for p in PROV:
            g = [r for r in prim if r["provider"] == p and r["paradigm"] == para]
            miss = sorted({r["conc"] for r in g if r["read_tput"] is None})
            cov.append(dict(provider=p, paradigm=para, planned=len(g),
                            write_measured=sum(r["write_tput"] is not None for r in g),
                            read_measured=sum(r["read_tput"] is not None for r in g),
                            read_missing=sum(r["read_tput"] is None for r in g),
                            levels_missing_read="/".join(map(str, miss)),
                            missing_runs=" ".join(r["run_id"].split("balanced-")[1] for r in g if r["read_tput"] is None)))
    wcsv(OUT / "phase_coverage.csv", cov)
    W = sum(c["write_measured"] for c in cov); R = sum(c["read_measured"] for c in cov)
    bfR = sum(c["read_measured"] for c in cov if c["paradigm"] != "object")
    bfP = sum(c["planned"] for c in cov if c["paradigm"] != "object")
    mac("rWritePhases", W); mac("rReadPhases", R); mac("rPlannedPhases", len(prim))
    mac("rBfReads", bfR); mac("rBfPlanned", bfP); mac("rBfMissing", bfP - bfR)
    mac("rObjReads", sum(c["read_measured"] for c in cov if c["paradigm"] == "object"))

    # ---------------- 2/3. lack of fit, level gains, common range ----------------
    lof, gains, common = [], [], []
    for para in PARA:
        for p in PROV:
            for op in ("write", "read"):
                pts = [(r["conc"], r[f"{op}_tput"]) for r in prim if r["provider"] == p and r["paradigm"] == para and r[f"{op}_tput"]]
                if not pts:
                    continue
                xs, ys = zip(*pts)
                f = fit(xs, ys); t = lack_of_fit(xs, ys)
                row = dict(provider=p, paradigm=para, op=op, L=f["L"], n=f["n"], beta=f.get("beta"))
                if t:
                    row.update(t)
                lof.append(row)
                lv = sorted(set(xs))
                gm = {c: 10 ** np.mean(np.log10([y for x, y in pts if x == c])) for c in lv}
                g = dict(provider=p, paradigm=para, op=op)
                for c in lv:
                    vs = [y for x, y in pts if x == c]
                    g[f"gm_c{c}"] = gm[c]; g[f"min_c{c}"] = min(vs); g[f"max_c{c}"] = max(vs)
                for c0, c1 in zip(lv, lv[1:]):
                    g[f"gain_{c0}_{c1}"] = gm[c1] / gm[c0]
                    g[f"local_beta_{c0}_{c1}"] = math.log(gm[c1] / gm[c0]) / math.log(c1 / c0)
                gains.append(g)
                sub = [(x, y) for x, y in pts if x <= 16]
                fc = fit(*zip(*sub))
                common.append(dict(provider=p, paradigm=para, op=op, levels=fc["levels"], n=fc["n"],
                                   beta_1_16=fc.get("beta"), lo_run=fc.get("lo_run"), hi_run=fc.get("hi_run"),
                                   lo_mean=fc.get("lo_mean"), hi_mean=fc.get("hi_mean"),
                                   beta_full=f.get("beta"), L_full=f["L"]))
    wcsv(OUT / "lack_of_fit.csv", lof); wcsv(OUT / "level_gains.csv", gains); wcsv(OUT / "common_range.csv", common)
    for para in PARA:
        cells = [r for r in lof if r["paradigm"] == para and "p" in r]
        k = sum(r["p"] < 0.05 for r in cells)
        mac(f"rLof{para.capitalize()}", k); mac(f"rLof{para.capitalize()}N", len(cells))
    cells = [r for r in lof if "p" in r]
    mac("rLofAll", sum(r["p"] < 0.05 for r in cells)); mac("rLofAllN", len(cells))
    # Table: lack of fit + level gains for every cell
    with open(OUT / "tab_r2_diagnostics.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lllrrrrrr}\n\\toprule\n")
        fh.write(" & & & & \\multicolumn{3}{c}{Gain between levels} & \\multicolumn{2}{c}{Lack of fit} \\\\\n")
        fh.write("\\cmidrule(lr){5-7}\\cmidrule(lr){8-9}\n")
        fh.write("Paradigm & Provider & Op. & $\\beta$ & 1$\\to$4 & 4$\\to$16 & 16$\\to$64 & $F$ & $p$ \\\\\n\\midrule\n")
        for para in PARA:
            for p in PROV:
                for op in ("write", "read"):
                    g = next((x for x in gains if x["provider"] == p and x["paradigm"] == para and x["op"] == op), None)
                    l = next((x for x in lof if x["provider"] == p and x["paradigm"] == para and x["op"] == op), None)
                    if not g:
                        continue
                    gs = [g.get(k) for k in ("gain_1_4", "gain_4_16", "gain_16_64")]
                    gs = [f"{v:.2f}" if v else "--" for v in gs]
                    Fp = (f"{l['F']:.1f}", ("$<$0.001" if l["p"] < 0.001 else f"{l['p']:.3f}")) if l and "p" in l else ("--", "--")
                    name = PNAME[p] if op == "write" else ""
                    pa = para if (p == "aws" and op == "write") else ""
                    fh.write(f"{pa} & {name} & {op} & {l['beta']:.3f} & {' & '.join(gs)} & {Fp[0]} & {Fp[1]} \\\\\n")
            if para != "object":
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")

    # ---------------- 4. replication over matched levels ----------------
    v1 = [r for r in rd(ROOT / "recompute-output" / "runs_recomputed.csv") if r["workload"] == "balanced"]
    rep = []
    for para in PARA:
        for p in PROV:
            for op in ("write", "read"):
                a_pts = [(int(r["concurrency"]), float(r[f"{op}_tput_mib_s"])) for r in v1
                         if r["provider"] == p and r["paradigm"] == para and num(r[f"{op}_tput_mib_s"])]
                b_pts = [(r["conc"], r[f"{op}_tput"]) for r in prim if r["provider"] == p and r["paradigm"] == para and r[f"{op}_tput"]]
                if not a_pts or not b_pts:
                    continue
                common_lv = sorted(set(x for x, _ in a_pts) & set(x for x, _ in b_pts))
                fa = fit(*zip(*[q for q in a_pts if q[0] in common_lv]))
                fb = fit(*zip(*[q for q in b_pts if q[0] in common_lv]))
                fa_all, fb_all = fit(*zip(*a_pts)), fit(*zip(*b_pts))
                if fa_all["levels"] == "/".join(map(str, common_lv)) and (p, para, op) in V1A:
                    fa["beta"] = fa_all["beta"] = V1A[(p, para, op)]
                rep.append(dict(provider=p, paradigm=para, op=op, matched_levels="/".join(map(str, common_lv)),
                                earlier_all=fa_all.get("beta"), present_all=fb_all.get("beta"),
                                earlier_matched=fa.get("beta"), present_matched=fb.get("beta"),
                                shift_matched=(fb.get("beta") - fa.get("beta")) if fa.get("beta") is not None and fb.get("beta") is not None else None,
                                earlier_levels=fa_all["levels"], present_levels=fb_all["levels"]))
    wcsv(OUT / "replication_matched.csv", rep)
    obj = [r for r in rep if r["paradigm"] == "object" and r["provider"] != "azure"]
    mac("rObjMatchedShiftMax", f"{max(abs(r['shift_matched']) for r in obj):.2f}")
    mac("rObjMatchedShiftMaxThree", f"{max(abs(r['shift_matched']) for r in obj):.3f}")
    allm = [r for r in rep if r["shift_matched"] is not None]
    mx = max(allm, key=lambda r: abs(r["shift_matched"]))
    mac("rMatchedShiftMax", f"{abs(mx['shift_matched']):.2f}")
    mac("rMatchedShiftMaxCell", f"{PNAME[mx['provider']]} {mx['paradigm']} {mx['op']}")
    def dshow(r):
        d = r["present_matched"] - r["earlier_matched"]
        return "0.000" if abs(d) < 5e-4 else f"{d:+.3f}"
    for r in rep:
        r["shift_shown"] = round(r["present_matched"], 3) - round(r["earlier_matched"], 3)
    with open(OUT / "tab_r2_replication.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lllcccc}\n\\toprule\n")
        fh.write("Paradigm & Provider & Op. & Levels compared & Earlier & Present & Difference \\\\\n\\midrule\n")
        for para in PARA:
            for p in PROV:
                for op in ("write", "read"):
                    r = next((x for x in rep if x["provider"] == p and x["paradigm"] == para and x["op"] == op), None)
                    if not r:
                        continue
                    lv = r["matched_levels"].replace("/", ", ")
                    pa = para if (p == "aws" and op == "write") else ""
                    name = PNAME[p] if op == "write" else ""
                    fh.write(f"{pa} & {name} & {op} & {lv} & {r['earlier_matched']:.3f} & {r['present_matched']:.3f} & {dshow(r)} \\\\\n")
            if para != "object":
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")

    # ---------------- 5. prespecified 1-128 object exponents ----------------
    ext = []
    for p in PROV:
        for op in ("write", "read"):
            pts = [(r["conc"], r[f"{op}_tput"]) for r in runs if r["provider"] == p and r["paradigm"] == "object"
                   and r["mode"] in ("primary", "ext128") and r[f"{op}_tput"]]
            f64 = fit(*zip(*[q for q in pts if q[0] <= 64])); f128 = fit(*zip(*pts))
            ext.append(dict(provider=p, op=op, beta_1_64=f64["beta"], beta_1_128=f128["beta"], n_1_128=f128["n"],
                            lo_run=f128["lo_run"], hi_run=f128["hi_run"], lo_mean=f128.get("lo_mean"), hi_mean=f128.get("hi_mean")))
    wcsv(OUT / "ext128_exponents.csv", ext)

    # ---------------- 6. CPU gates and phase-aligned CPU ----------------
    gates, phase_rows = [], []
    for r in runs:
        p = r["provider"]; rid = r["run_id"]
        mp = raw_dir(ROOT, p) / f"{rid}.mpstat.txt"
        if not mp.exists():
            continue
        samples = read_mpstat(mp)
        s = summarise_cpu(samples)
        gA = (r["cpu_all"] or 0) > 80
        gB = s.get("max_core_share_gt95", 0) >= 0.5
        gC = s.get("max_core_share_gt95_noiowait", 0) >= 0.5
        gates.append(dict(run_id=rid, provider=p, paradigm=r["paradigm"], mode=r["mode"], conc=r["conc"],
                          cpu_all=r["cpu_all"], max_core_share_gt95=s.get("max_core_share_gt95"),
                          max_core_share_gt95_noiowait=s.get("max_core_share_gt95_noiowait"),
                          gate_mean80=int(gA), gate_core95=int(gB), gate_core95_noiowait=int(gC)))
        if r["paradigm"] == "object":
            runner = r["tool"] != "elbencho"
            el = raw_dir(ROOT, p) / f"{rid}.elbencho.csv"
            ph = {} if runner else (elbencho_phases(el) if el.exists() else {})
            sl = phase_slices(samples, ph, runner)
            row = dict(run_id=rid, provider=p, mode=r["mode"], conc=r["conc"], tool=r["tool"], host="host1")
            for op in ("write", "read"):
                for k, v in (sl.get(op) or {}).items():
                    row[f"{op}_{k}"] = v
            phase_rows.append(row)
    wcsv(OUT / "cpu_gates.csv", gates)
    gmap = {g["run_id"]: g for g in gates}
    refits = []
    for para in PARA:
        for p in PROV:
            for op in ("write", "read"):
                pts = [(r["conc"], r[f"{op}_tput"], r["run_id"]) for r in prim if r["provider"] == p and r["paradigm"] == para and r[f"{op}_tput"]]
                if not pts:
                    continue
                full = fit([x for x, _, _ in pts], [y for _, y, _ in pts])
                for gname in ("gate_mean80", "gate_core95", "gate_core95_noiowait"):
                    keep = [(x, y) for x, y, rid in pts if not gmap.get(rid, {}).get(gname)]
                    nex = len(pts) - len(keep)
                    if nex == 0:
                        continue
                    fk = fit(*zip(*keep)) if len({x for x, _ in keep}) >= 2 and len(keep) >= 3 else {}
                    refits.append(dict(provider=p, paradigm=para, op=op, gate=gname, excluded=nex,
                                       excluded_levels="/".join(sorted({str(x) for x, _, rid in pts if gmap.get(rid, {}).get(gname)}, key=int)),
                                       beta_all=full["beta"], beta_gated=fk.get("beta"), n_gated=len(keep),
                                       levels_gated=fk.get("levels"), lo_run=fk.get("lo_run"), hi_run=fk.get("hi_run")))
    wcsv(OUT / "cpu_gated_refits.csv", refits)
    mac("rGateMeanRuns", sum(g["gate_mean80"] for g in gates if g["mode"] == "primary"))
    mac("rGateCoreRuns", sum(g["gate_core95"] for g in gates if g["mode"] == "primary"))
    mac("rGateCoreNoIowRuns", sum(g["gate_core95_noiowait"] for g in gates if g["mode"] == "primary"))
    mac("rGateCoreBfRuns", sum(g["gate_core95"] for g in gates if g["mode"] == "primary" and g["paradigm"] != "object"))
    mac("rGateCells", len({(x["provider"], x["paradigm"]) for x in refits}))
    with open(OUT / "tab_r2_cpugated.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llllrrrl}\n\\toprule\n")
        fh.write("Provider & Paradigm & Op. & Gate & Excluded & $\\beta$, all runs & $\\beta$, gated runs excluded & Levels left \\\\\n\\midrule\n")
        key = lambda x: (x["provider"], x["paradigm"], x["op"])
        sets = {(key(x), x["gate"]): (x["excluded"], x["excluded_levels"]) for x in refits}
        for x in refits:
            same_a = sets.get((key(x), "gate_mean80")) == sets.get((key(x), "gate_core95_noiowait"))
            if x["gate"] == "gate_core95_noiowait" and same_a:
                continue
            if x["gate"] == "gate_core95" and sets.get((key(x), "gate_mean80")) == (x["excluded"], x["excluded_levels"]):
                continue
            gl = {"gate_mean80": "A, B$'$" if same_a else "A", "gate_core95": "B",
                  "gate_core95_noiowait": "B$'$"}[x["gate"]]
            bg = f"{x['beta_gated']:.3f}" if x["beta_gated"] is not None else "n.e."
            fh.write(f"{PNAME[x['provider']]} & {x['paradigm']} & {x['op']} & {gl} & {x['excluded']} (c{x['excluded_levels']}) & {x['beta_all']:.3f} & {bg} & {x['levels_gated'] or '--'} \\\\\n".replace("/", ", "))
        fh.write("\\bottomrule\n\\end{tabular}\n")

    # D5: both hosts, each repeat, each phase
    d5dir = ROOT / "results-rerun-v21" / "azure-mc2"
    d5man = d5dir / "results-rerun-v21-azure-mc2" / "run_manifest.jsonl"
    d5m = [json.loads(l) for l in open(d5man) if l.strip()]
    d5rows = []
    for m in d5m:
        for h in ("host1", "host2"):
            rows = {x["operation"]: x for x in csv.DictReader(open(d5dir / m[f"raw_{h}_csv"]))}
            sl = phase_slices(read_mpstat(d5dir / m[f"raw_{h}_mpstat_txt"]), {}, True)
            row = dict(run_id=m["run_id"], rep=m["rep"], host=h)
            for op in ("write", "read"):
                row[f"{op}_tput"] = float(rows[op]["throughput_mb_s"]) * MB_TO_MIB
                row[f"{op}_p99_ms"] = float(rows[op]["lat_p99_ms"])
                for k in ("cpu_all", "cpu_maxcore", "share_all_ge90"):
                    row[f"{op}_{k}"] = (sl.get(op) or {}).get(k)
            d5rows.append(row)
            phase_rows.append(dict(run_id=m["run_id"], provider="azure", mode="multi_azure", conc=64,
                                   tool="azure_blob_runner_v2", host=h,
                                   **{f"{op}_{k}": row[f"{op}_{k}"] for op in ("write", "read") for k in ("cpu_all", "cpu_maxcore", "share_all_ge90")}))
    wcsv(OUT / "d5_hosts.csv", d5rows); wcsv(OUT / "phase_cpu.csv", phase_rows)

    # ---------------- 7. host ratios with repeat variability ----------------
    hr = []
    for p in PROV:
        for op in ("write", "read"):
            base = [r[f"{op}_tput"] for r in prim if r["provider"] == p and r["paradigm"] == "object" and r["conc"] == 64 and r[f"{op}_tput"]]
            e128 = [r[f"{op}_tput"] for r in runs if r["provider"] == p and r["mode"] == "ext128" and r[f"{op}_tput"]]
            if p == "azure":
                reps = defaultdict(float)
                for x in d5rows:
                    reps[x["rep"]] += x[f"{op}_tput"]
                two = [reps[k] for k in sorted(reps)]
                h1 = [x[f"{op}_tput"] for x in d5rows if x["host"] == "host1"]
                h2 = [x[f"{op}_tput"] for x in d5rows if x["host"] == "host2"]
            else:
                two = [r[f"{op}_tput"] for r in runs if r["provider"] == p and r["mode"] == "multi" and r[f"{op}_tput"]]
                h1 = h2 = []
            def cv(v):
                return st.stdev(v) / st.mean(v) if len(v) > 1 else None
            row = dict(provider=p, op=op, c64=st.mean(base), c64_min=min(base), c64_max=max(base), c64_cv=cv(base),
                       c128=st.mean(e128), c128_min=min(e128), c128_max=max(e128), c128_cv=cv(e128),
                       two=st.mean(two), two_min=min(two), two_max=max(two), two_cv=cv(two),
                       ratio128=st.mean(e128) / st.mean(base), ratio128_lo=min(e128) / max(base), ratio128_hi=max(e128) / min(base),
                       ratio2=st.mean(two) / st.mean(base), ratio2_lo=min(two) / max(base), ratio2_hi=max(two) / min(base),
                       per_rep_c64=";".join(f"{v:.1f}" for v in base), per_rep_c128=";".join(f"{v:.1f}" for v in e128),
                       per_rep_two=";".join(f"{v:.1f}" for v in two),
                       host1=";".join(f"{v:.1f}" for v in h1), host2=";".join(f"{v:.1f}" for v in h2))
            hr.append(row)
    wcsv(OUT / "host_ratios.csv", hr)
    pc = defaultdict(list)
    for x in phase_rows:
        pc[(x["provider"], x["mode"], x["conc"], x["host"])].append(x)
    def pcm(p, mode, c, op, k, host="host1"):
        v = [x.get(f"{op}_{k}") for x in pc[(p, mode, c, host)] if x.get(f"{op}_{k}") is not None]
        return st.mean(v) if v else None
    with open(OUT / "tab_r2_hosts.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llrrrrr}\n\\toprule\n")
        fh.write(" & & \\multicolumn{3}{c}{Throughput, MiB/s: mean (range of 3 runs)} & \\multicolumn{2}{c}{Ratio to 64 threads, 1 host} \\\\\n")
        fh.write("\\cmidrule(lr){3-5}\\cmidrule(lr){6-7}\n")
        fh.write("Provider & Op. & 64 thr., 1 host & 128 thr., 1 host & 2 hosts $\\times$ 64 & 128 thr., 1 host & 2 hosts \\\\\n\\midrule\n")
        for x in hr:
            p, op = x["provider"], x["op"]
            fmt = lambda m, lo, hi: f"{m:.0f} ({lo:.0f}--{hi:.0f})"
            name = PNAME[p] + ("$^{\\ddagger}$" if p == "azure" else "") if op == "write" else ""
            fh.write(f"{name} & {op} & {fmt(x['c64'], x['c64_min'], x['c64_max'])} & {fmt(x['c128'], x['c128_min'], x['c128_max'])} & "
                     f"{fmt(x['two'], x['two_min'], x['two_max'])} & {x['ratio128']:.2f} ({x['ratio128_lo']:.2f}--{x['ratio128_hi']:.2f}) & "
                     f"{x['ratio2']:.2f} ({x['ratio2_lo']:.2f}--{x['ratio2_hi']:.2f}) \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    with open(OUT / "tab_r2_hostscpu.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lrrrrrr}\n\\toprule\n")
        fh.write(" & \\multicolumn{3}{c}{Write phase} & \\multicolumn{3}{c}{Read phase} \\\\\n")
        fh.write("\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\n")
        fh.write("Provider & 64 thr. & 128 thr. & 2 hosts & 64 thr. & 128 thr. & 2 hosts \\\\\n\\midrule\n")
        for p in PROV:
            twomode = "multi_azure" if p == "azure" else "multi"
            vals = []
            for op in ("write", "read"):
                vals += [pcm(p, "primary", 64, op, "cpu_all"), pcm(p, "ext128", 128, op, "cpu_all"), pcm(p, twomode, 64, op, "cpu_all")]
            name = PNAME[p] + ("$^{\\ddagger}$" if p == "azure" else "")
            fh.write(name + " & " + " & ".join(f"{v:.0f}" for v in vals) + " \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    for x in hr:
        tag = PNAME[x["provider"]] + x["op"].capitalize()
        mac(f"r{tag}RtwoLo", f"{x['ratio2_lo']:.2f}"); mac(f"r{tag}RtwoHi", f"{x['ratio2_hi']:.2f}")
        mac(f"r{tag}RoneLo", f"{x['ratio128_lo']:.2f}"); mac(f"r{tag}RoneHi", f"{x['ratio128_hi']:.2f}")
        mac(f"r{tag}Rtwo", f"{x['ratio2']:.2f}"); mac(f"r{tag}Rone", f"{x['ratio128']:.2f}")
    # Azure D5 per host
    with open(OUT / "tab_r2_d5.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lrrrrrr}\n\\toprule\n")
        fh.write(" & \\multicolumn{3}{c}{Write phase} & \\multicolumn{3}{c}{Read phase} \\\\\n\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\n")
        fh.write("Run, host & MiB/s & CPU \\% & time at $\\geq$90\\% & MiB/s & CPU \\% & time at $\\geq$90\\% \\\\\n\\midrule\n")
        for x in d5rows:
            fh.write(f"r{x['rep']}, {x['host'].replace('host', 'host ')} & {x['write_tput']:.1f} & {x['write_cpu_all']:.1f} & {x['write_share_all_ge90']*100:.0f}\\% & "
                     f"{x['read_tput']:.1f} & {x['read_cpu_all']:.1f} & {x['read_share_all_ge90']*100:.0f}\\% \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    h1w = [x["write_tput"] for x in d5rows if x["host"] == "host1"]; h2w = [x["write_tput"] for x in d5rows if x["host"] == "host2"]
    h1r = [x["read_tput"] for x in d5rows if x["host"] == "host1"]; h2r = [x["read_tput"] for x in d5rows if x["host"] == "host2"]
    mac("rDfiveHoneW", f"{min(h1w):.1f}--{max(h1w):.1f}"); mac("rDfiveHtwoW", f"{min(h2w):.1f}--{max(h2w):.1f}")
    mac("rDfiveHoneR", f"{min(h1r):.1f}--{max(h1r):.1f}"); mac("rDfiveHtwoR", f"{min(h2r):.1f}--{max(h2r):.1f}")
    allcpu = [x[f"{op}_cpu_all"] for x in d5rows for op in ("write", "read")]
    mac("rDfiveCpuMin", f"{min(allcpu):.1f}")
    shares = [x[f"{op}_share_all_ge90"] for x in d5rows for op in ("write", "read")]
    mac("rDfiveShareMin", f"{min(shares)*100:.0f}")
    azc = [pcm("azure", "primary", c, op, "share_all_ge90") for c in (16, 64) for op in ("write", "read")]
    mac("rAzShareMin", f"{min(azc)*100:.0f}")

    # ---------------- 8. accounting ----------------
    acc = dict(recorded_attempts_primary_plan=0, accepted_primary_plan=0)
    for p in PROV:
        mf = ROOT / "results-rerun-v21" / p / f"results-rerun-v21-{p}" / "run_manifest.jsonl"
        recs = [json.loads(l) for l in open(mf) if l.strip()]
        acc["recorded_attempts_primary_plan"] += len(recs)
        acc["accepted_primary_plan"] += len({r["run_id"] for r in recs if r["status"] == "ok"})
    acc["recorded_attempts_d5"] = len(d5m); acc["accepted_d5"] = sum(m["status"] == "ok" for m in d5m)
    acc["recorded_attempts_total"] = acc["recorded_attempts_primary_plan"] + acc["recorded_attempts_d5"]
    acc["accepted_total"] = acc["accepted_primary_plan"] + acc["accepted_d5"]
    acc["unrecorded_invocations"] = 1
    acc["unrecorded_note"] = ("DEVIATIONS_V21.md D3: an Alibaba block c16-r2 invocation stopped by hand before it "
                              "provisioned anything or wrote a manifest record")
    acc["invocations_total"] = acc["recorded_attempts_total"] + acc["unrecorded_invocations"]
    acc["alibaba_block_c16_r2_invocations"] = 4
    open(OUT / "accounting.json", "w", newline="\n").write(json.dumps(acc, indent=1))
    mac("rAttemptsAll", acc["recorded_attempts_total"]); mac("rAcceptedAll", acc["accepted_total"])
    mac("rInvocationsAll", acc["invocations_total"])

    # ---------------- 9. misc values quoted in the text ----------------
    ex = {(e["provider"], e["paradigm"], e["op"]): e for e in rd(ROOT / "v21-output" / "exponents.csv")}
    mac("rAliBlkMiB", "170.0"); mac("rAliBlkMB", f"{170.0 / MB_TO_MIB:.1f}"); mac("rAliDocMiB", f"{170 * MB_TO_MIB:.1f}")
    eh = next(x for x in hr if x["provider"] == "huawei" and x["op"] == "write")
    mac("rHuaweiWsixtyfour", f"{eh['c64']:.1f}"); mac("rHuaweiWonetwentyeight", f"{eh['c128']:.1f}")


    # ---------------- 9b. warm-up invocation: first write vs measured write ----------------
    # The orchestrator runs the measurement command once as a warm-up (stopped after 90 s) on the
    # same target and with the same --csvfile. Where the warm-up finished its write phase within
    # 90 s, elbencho appended that phase to the CSV, so the first write of the file (warm-up) and
    # the measured write (an overwrite of the same file) can be compared within one run.
    wu = []
    for r in prim:
        if r["paradigm"] not in ("block", "file"):
            continue
        f = raw_dir(ROOT, r["provider"]) / f"{r['run_id']}.elbencho.csv"
        R_ = list(csv.DictReader(open(f)))
        ws = [x for x in R_ if x["operation"] == "WRITE"]
        t = lambda x: float(x["MiB [last]"]) / (float(x["time ms [last]"]) / 1000)
        row = dict(run_id=r["run_id"], provider=r["provider"], paradigm=r["paradigm"], conc=r["conc"],
                   csv_rows=len(R_), warmup_write_complete=int(len(ws) >= 2))
        if len(ws) >= 2:
            row.update(warmup_write=t(ws[0]), measured_write=t(ws[-1]), ratio=t(ws[-1]) / t(ws[0]))
        wu.append(row)
    wcsv(OUT / "warmup_writes.csv", wu)
    have = [x for x in wu if x["warmup_write_complete"]]
    mac("rWarmupRuns", len(have)); mac("rWarmupBf", len(wu))
    with open(OUT / "tab_r2_warmup.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llrrrr}\n\\toprule\n")
        fh.write("Paradigm & Provider & Threads & Warm-up write (first write) & Measured write (overwrite) & Ratio \\\\\n\\midrule\n")
        for para in ("block", "file"):
            for p in PROV:
                for c in (1, 4):
                    g = [x for x in have if x["provider"] == p and x["paradigm"] == para and x["conc"] == c]
                    if not g:
                        continue
                    a = [x["warmup_write"] for x in g]; b = [x["measured_write"] for x in g]; q = [x["ratio"] for x in g]
                    rng = lambda v, d=0: f"{min(v):.{d}f}--{max(v):.{d}f}" if round(min(v), d) != round(max(v), d) else f"{min(v):.{d}f}"
                    fh.write(f"{para} & {PNAME[p]} & {c} ({len(g)} runs) & {rng(a)} & {rng(b)} & {rng(q, 2)} \\\\\n")
            if para == "block":
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    for p, para in (("gcp", "block"), ("huawei", "block"), ("huawei", "file")):
        q = [x["ratio"] for x in have if x["provider"] == p and x["paradigm"] == para and x["conc"] == 4]
        tag = PNAME[p] + para.capitalize()
        mac(f"rWarm{tag}Lo", f"{min(q):.1f}"); mac(f"rWarm{tag}Hi", f"{max(q):.1f}")

    # ---------------- 9c. client CPU cost of the SDK runner, S3 port (AWS) vs Azure Blob ----------------
    # phase-aligned all-core CPU divided by phase throughput: how much client CPU the runner
    # spends per MiB/s on each service, and the throughput at which a 4 vCPU host saturates.
    tput = {r["run_id"]: r for r in runs}
    cost_rows = []
    for svc, p, mode in (("S3 port (AWS S3)", "aws", "equiv"), ("Azure Blob", "azure", "primary")):
        for c in (1, 4, 16, 64):
            rs = [x for x in phase_rows if x["provider"] == p and x["mode"] == mode and x["conc"] == c and x["host"] == "host1"]
            row = dict(service=svc, conc=c, n=len(rs))
            for op in ("write", "read"):
                t = st.mean(tput[x["run_id"]][f"{op}_tput"] for x in rs)
                cpu = st.mean(x[f"{op}_cpu_all"] for x in rs)
                row.update({f"{op}_tput": t, f"{op}_cpu": cpu, f"{op}_cpu_per_mib": cpu / t})
            cost_rows.append(row)
    wcsv(OUT / "runner_cpu_cost.csv", cost_rows)
    with open(OUT / "tab_r2_runnercost.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lrrrrrrr}\n\\toprule\n")
        fh.write(" & & \\multicolumn{3}{c}{Write phase} & \\multicolumn{3}{c}{Read phase} \\\\\n\\cmidrule(lr){3-5}\\cmidrule(lr){6-8}\n")
        fh.write("Service & Threads & MiB/s & CPU \\% & CPU \\% per MiB/s & MiB/s & CPU \\% & CPU \\% per MiB/s \\\\\n\\midrule\n")
        for i, r in enumerate(cost_rows):
            name = r["service"] if r["conc"] == 1 else ""
            fh.write(f"{name} & {r['conc']} & {r['write_tput']:.1f} & {r['write_cpu']:.0f} & {r['write_cpu_per_mib']:.2f} & "
                     f"{r['read_tput']:.1f} & {r['read_cpu']:.0f} & {r['read_cpu_per_mib']:.2f} \\\\\n")
            if i == 3:
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    s3 = [r for r in cost_rows if r["service"].startswith("S3")]; az = [r for r in cost_rows if r["service"] == "Azure Blob"]
    rng = lambda v: f"{min(v):.1f}--{max(v):.1f}"
    mac("rCostSthree", rng([r[f"{op}_cpu_per_mib"] for r in s3 for op in ("write", "read")]))
    mac("rCostAzure", rng([r[f"{op}_cpu_per_mib"] for r in az for op in ("write", "read")]))
    mac("rCostSthreeLow", rng([r[f"{op}_cpu_per_mib"] for r in s3 if r["conc"] <= 4 for op in ("write", "read")]))
    mac("rCostAzureLow", rng([r[f"{op}_cpu_per_mib"] for r in az if r["conc"] <= 4 for op in ("write", "read")]))
    mac("rSthreeOneW", f"{s3[0]['write_tput']:.1f}"); mac("rAzureOneW", f"{az[0]['write_tput']:.1f}")
    mac("rSthreeSatW", f"{s3[3]['write_tput']:.0f}"); mac("rAzureSatW", f"{max(az[2]['write_tput'], az[3]['write_tput']):.0f}")
    mac("rAzureFourCpuW", f"{az[1]['write_cpu']:.0f}"); mac("rAzureFourCpuR", f"{az[1]['read_cpu']:.0f}")
    for x in refits:
        if x["provider"] == "azure" and x["paradigm"] == "object" and x["gate"] == "gate_mean80":
            t = "W" if x["op"] == "write" else "R"
            mac(f"rAzGated{t}", f"{x['beta_gated']:.2f}")
            mac(f"rAzGated{t}CI", f"[{x['lo_run']:.2f}, {x['hi_run']:.2f}]")

    # ---------------- 10. compact exponent table (replaces the dense Table 6) ----------------
    TAGP = {"aws": "Aws", "azure": "Azure", "gcp": "Gcp", "huawei": "Huawei", "alibaba": "Alibaba"}
    with open(OUT / "tab_r2_exponents.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llrccrrcc}\n\\toprule\n")
        fh.write(" & & \\multicolumn{3}{c}{Write phase ($n = 12$)} & \\multicolumn{4}{c}{Read phase} \\\\\n")
        fh.write("\\cmidrule(lr){3-5}\\cmidrule(lr){6-9}\n")
        fh.write("Paradigm & Provider & $\\beta$ & run-level & level-mean & $n$ & $\\beta$ & run-level & level-mean \\\\\n\\midrule\n")
        both = defaultdict(lambda: [0, 0])
        for para in PARA:
            for p in PROV:
                cells = []
                for op in ("write", "read"):
                    e = EXA[(p, para, op)]
                    dag = "$^{\\dagger}$" if e["L"] < 4 else ""
                    unbal = abs(e["beta_mean"] - e["beta"]) >= 5e-4
                    lm = f"[{e['lo_mean']:.2f}, {e['hi_mean']:.2f}]" + ("$^{\\S}$" if unbal else "")
                    if op == "read":
                        cells.append(str(e["n"]))
                    cells += [f"{e['beta']:.3f}{dag}", f"[{e['lo_run']:.2f}, {e['hi_run']:.2f}]", lm]
                    if unbal:
                        mac("rUnbalCell", f"{PNAME[p]} {para} {op}"); mac("rUnbalN", e["n"])
                        mac("rUnbalBetaLM", f"{e['beta_mean']:.3f}"); mac("rUnbalBeta", f"{e['beta']:.3f}")
                    ex_run = e["lo_run"] > 0 or e["hi_run"] < 0
                    ex_lm = e["lo_mean"] > 0 or e["hi_mean"] < 0
                    both[para][0] += 1; both[para][1] += int(ex_run and ex_lm)
                    tag = "b" + TAGP[p] + para.capitalize() + ("W" if op == "write" else "R")
                    M.append(f"\\renewcommand{{\\{tag}}}{{{e['beta']:.3f}}}\n")
                    M.append(f"\\renewcommand{{\\{tag}lo}}{{{e['lo_run']:.2f}}}\n")
                    M.append(f"\\renewcommand{{\\{tag}hi}}{{{e['hi_run']:.2f}}}\n")
                pa = para if p == "aws" else ""
                fh.write(f"{pa} & {PNAME[p]} & " + " & ".join(cells) + " \\\\\n")
            if para != "object":
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    for para in PARA:
        mac(f"rBoth{para.capitalize()}", both[para][1]); mac(f"rBoth{para.capitalize()}N", both[para][0])
    three = [EXA[k] for k in EXA if EXA[k]["L"] < 4]
    mac("rThreeLMWidthMin", f"{min(e['hi_mean'] - e['lo_mean'] for e in three):.1f}")
    mac("rThreeLMWidthMax", f"{max(e['hi_mean'] - e['lo_mean'] for e in three):.1f}")
    objop = [EXA[(p, "object", op)]["beta"] for p in PROV if p != "azure" for op in ("write", "read")]
    mac("rObjOpMin", f"{min(objop):.3f}"); mac("rObjOpMax", f"{max(objop):.3f}")
    fl = [EXA[(p, "file", op)]["beta"] for p in PROV for op in ("write", "read")]
    mac("rFileMin", f"{min(fl):.3f}"); mac("rFileMax", f"{max(fl):.3f}")

    # ---------------- 11. 1-128 object exponents table ----------------
    with open(OUT / "tab_r2_ext128.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lrrcrrc}\n\\toprule\n")
        fh.write(" & \\multicolumn{3}{c}{Write phase} & \\multicolumn{3}{c}{Read phase} \\\\\n\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\n")
        fh.write("Provider & 1--64 & 1--128 & run-level CI (1--128) & 1--64 & 1--128 & run-level CI (1--128) \\\\\n\\midrule\n")
        for p in PROV:
            c = []
            for op in ("write", "read"):
                e = next(x for x in ext if x["provider"] == p and x["op"] == op)
                c += [f"{e['beta_1_64']:.3f}", f"{e['beta_1_128']:.3f}", f"[{e['lo_run']:.2f}, {e['hi_run']:.2f}]"]
            mark = "$^{\\ddagger}$" if p == "azure" else ""
            fh.write(PNAME[p] + mark + " & " + " & ".join(c) + " \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")

    # ---------------- 12. sizing of the earlier campaign per cell ----------------
    fixed = {"balanced": 20.0, "largeobj": 40.0}
    v1all = rd(ROOT / "recompute-output" / "runs_recomputed.csv")
    with open(OUT / "tab_r2_v1sizing.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llll}\n\\toprule\nProvider & Paradigm & Balanced workload & Large-object workload \\\\\n\\midrule\n")
        for p in PROV:
            for para in PARA:
                cells = []
                for w in ("balanced", "largeobj"):
                    g = [r for r in v1all if r["provider"] == p and r["paradigm"] == para and r["workload"] == w]
                    if all(num(r["dataset_gb_executed"]) is None for r in g):
                        cells.append(f"duration-driven ({len(g)} runs)")
                        continue
                    g = [r for r in g if r["concurrency"] != "16"]
                    fx = sum(num(r["dataset_gb_executed"]) == fixed[w] for r in g)
                    wk = len(g) - fx
                    cells.append(f"{'fixed total' if fx > wk else 'weak scaling'} ({fx}/{wk})")
                fh.write(f"{PNAME[p] if para == 'block' else ''} & {para} & {cells[0]} & {cells[1]} \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")

    open(OUT / "r2_macros.tex", "w", newline="\n").write("% generated by sweep/review_r2.py -- do not edit\n" + "".join(M))
    figures(runs, prim, hr, d5rows, EXA, rep, OUT, ROOT)
    print(f"wrote {len(M)} macros and the review-r2 tables to {OUT}")


def figures(runs, prim, hr, d5rows, ex, rep, OUT, ROOT):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
                         "legend.fontsize": 9, "lines.linewidth": 1.4})
    DPI = 600
    # Fig 2: host ratios with per-repeat ranges
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    xs, i = [], 0
    for x in hr:
        p = x["provider"]
        for k, off, alpha, ec in (("128", -0.2, 0.45, COL[p]), ("2", 0.2, 1.0, "k")):
            m = x[f"ratio{k}"]; lo = x[f"ratio{k}_lo"]; hi = x[f"ratio{k}_hi"]
            ax.bar(i + off, m, 0.38, color=COL[p], alpha=alpha, edgecolor=ec, lw=0.4)
            ax.errorbar(i + off, m, yerr=[[m - lo], [hi - m]], fmt="none", ecolor="k", lw=0.8, capsize=2)
        xs.append((i, f"{PNAME[p]}\n{x['op']}")); i += 1
        if x["op"] == "read":
            i += 0.5
    ax.axhline(1, color="k", lw=0.6); ax.axhline(2, color="k", lw=0.6, ls="--")
    ax.set_xticks([a for a, _ in xs]); ax.set_xticklabels([b for _, b in xs], fontsize=8)
    ax.set_ylabel("throughput / (64 threads, 1 host)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor="0.7", alpha=0.45, label="128 threads, one host"),
                       Patch(facecolor="0.4", edgecolor="k", label="two hosts $\\times$ 64 threads")],
              loc="upper right", frameon=False, ncol=2)
    ax.set_ylim(0, 2.5); ax.grid(True, axis="y", lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fig_r2_clientservice.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)

    # Fig 3: runner vs elbencho, individual runs
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for k, op in enumerate(("write", "read")):
        ax = axs[k]
        for tool, mode, colr, mk, lab in (("elbencho", "primary", "k", "o", "elbencho"),
                                          ("s3_equiv_runner", "equiv", COL["azure"], "s", "SDK runner (S3 port)")):
            pts = [(r["conc"], r[f"{op}_tput"]) for r in runs if r["provider"] == "aws" and r["paradigm"] == "object"
                   and r["mode"] == mode and r["tool"] == tool and r[f"{op}_tput"] and r["conc"] <= 64]
            cs = sorted({c for c, _ in pts})
            jit = 1.06 if tool != "elbencho" else 0.94
            ax.scatter([c * jit for c, _ in pts], [v for _, v in pts], s=12, color=colr, marker=mk, alpha=0.6, lw=0)
            ax.plot(cs, [st.mean(v for c2, v in pts if c2 == c) for c in cs], color=colr, marker=mk, ms=3.5,
                    ls="-" if tool == "elbencho" else "--", label=lab)
        ax.set_xscale("log", base=2); ax.set_yscale("log")
        ax.set_xticks([1, 4, 16, 64]); ax.set_xticklabels(["1", "4", "16", "64"])
        ax.set_title(f"{op} phase"); ax.set_xlabel("client threads")
        ax.grid(True, which="both", lw=0.3, alpha=0.5)
    axs[0].set_ylabel("MiB/s (AWS S3)"); axs[0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fig_r2_equiv.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)

    # Fig 5: exponents with both interval constructions, present campaign
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 5.0), sharey=True)
    labels = [f"{PNAME[p]} {para}" for para in PARA for p in PROV]
    for k, op in enumerate(("write", "read")):
        ax = axs[k]
        for y, (para, p) in enumerate([(pa, p) for pa in PARA for p in PROV]):
            e = ex.get((p, para, op))
            if not e or e.get("beta") is None:
                continue
            XL, XH = -1.4, 1.9
            b = e["beta"]
            lr, hr_ = e["lo_run"], e["hi_run"]
            ax.errorbar(b, y - 0.15, xerr=[[b - lr], [hr_ - b]], fmt="s", ms=3, color=COL[p], lw=1.2,
                        label="run-level interval" if y == 0 else None)
            bm, lm, hm = e["beta_mean"], e["lo_mean"], e["hi_mean"]
            ax.errorbar(bm, y + 0.15, xerr=[[bm - max(lm, XL + 0.05)], [min(hm, XH - 0.05) - bm]], fmt="o", ms=3, mfc="white",
                        color=COL[p], lw=0.8, ls="--", label="level-mean interval" if y == 0 else None)
            if lm < XL + 0.05:
                ax.plot(XL + 0.05, y + 0.15, marker="<", ms=4, color=COL[p], zorder=5)
            if hm > XH - 0.05:
                ax.plot(XH - 0.05, y + 0.15, marker=">", ms=4, color=COL[p], zorder=5)
            if e["L"] < 4:
                ax.text(XL + 0.12, y - 0.02, "3 levels", fontsize=6.5, ha="left", va="center", color="0.4")
            o = next((r for r in rep if r["provider"] == p and r["paradigm"] == para and r["op"] == op), None)
            if o and o["earlier_matched"] is not None:   # same thread levels as the present fit
                ax.scatter(o["earlier_matched"], y, marker="x", s=14, color="0.45", zorder=4,
                           label="earlier campaign, matched levels (point)" if y == 0 else None)
        ax.axvline(0, color="k", lw=0.5); ax.axvline(1, color="k", lw=0.5, ls="--")
        ax.set_xlim(-1.4, 1.9)
        ax.set_title(f"{op} phase"); ax.set_xlabel("$\\beta$ with 95% intervals")
        ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=9)
        ax.invert_yaxis(); ax.grid(True, axis="x", lw=0.3, alpha=0.5)
    h, l = axs[0].get_legend_handles_labels()
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False)
    fig.savefig(OUT / "figures" / "fig_r2_exponents.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    main()
