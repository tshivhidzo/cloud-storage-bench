#!/usr/bin/env python3
"""
make_v21_paper.py -- every v2.1 table, figure and prose number in the revised
manuscript, generated from the analysis outputs (no hand-typed results).

Inputs
  --v21  output dir of analyze_v21.py (runs.csv, exponents.csv, cpu_cells.csv,
         ext128_multi.csv, equivalence.csv, reservoir.csv, network.csv,
         completion.csv)
  --d5   extracted rerun_azure_mc2.tgz (results-rerun-v21-azure-mc2/...)
  --v1   recompute-output/ of the v1 pipeline (exponents_recomputed.csv)
  --manifests  dir holding <provider>/results-rerun-v21-<provider>/run_manifest.jsonl
  --out  manuscript dir: writes v21_macros.tex, tab_v21_*.tex, figures/fig_v21_*.png

Documented limits (block table, network) are configuration facts, not
measurements; their sources are listed in DOCS below and cited in the paper.
"""
from __future__ import annotations
import argparse, csv, json, math, statistics as st, sys
from collections import defaultdict
from pathlib import Path

PROV = ["aws", "azure", "gcp", "huawei", "alibaba"]
PNAME = {"aws": "AWS", "azure": "Azure", "gcp": "GCP", "huawei": "Huawei", "alibaba": "Alibaba"}
PARA = ["block", "file", "object"]
COL = {"aws": "#E69F00", "azure": "#0072B2", "gcp": "#009E73", "huawei": "#D55E00",
       "alibaba": "#CC79A7"}
MARK = {"aws": "o", "azure": "s", "gcp": "^", "huawei": "D", "alibaba": "v"}
MB_TO_MIB = 1e6 / 1048576

# documented block limits (MiB/s unless noted) -- sources in the manuscript
DOCS = {
    "aws": ("EBS gp3, 100 GB", "125 MiB/s baseline", 125.0),
    "azure": ("Standard SSD E10 tier", "500 IOPS (burst 600) $\\times$ 64 KiB = 31--38 MiB/s", 31.25),
    "gcp": ("pd-ssd, 100 GB", "240 MiB/s per-instance baseline", 240.0),
    "huawei": ("EVS ultra-high I/O, 100 GB", "170 MiB/s by size; 350 MiB/s type maximum", 350.0),
    "alibaba": ("ESSD PL1, 100 GB", "$\\min(120+0.5\\times100,350)$ = 170 MB/s", 170.0 / MB_TO_MIB * MB_TO_MIB),
}


def f(x, d=3):
    return "--" if x is None or x == "" or (isinstance(x, float) and math.isnan(x)) else f"{float(x):.{d}f}"


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def rd(path):
    return list(csv.DictReader(open(path)))


def macro(name, val):
    return f"\\newcommand{{\\{name}}}{{{val}}}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v21", required=True)
    ap.add_argument("--d5", required=True)
    ap.add_argument("--v1", required=True)
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    V, OUT = Path(a.v21), Path(a.out)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    runs = rd(V / "runs.csv")
    for r in runs:
        for k in ("conc", "hosts"):
            r[k] = int(r[k])
        for k in ("write_tput", "read_tput", "combined_tput", "write_p99_ms", "read_p99_ms",
                  "cpu_all", "cpu_maxcore", "hot_share"):
            r[k] = num(r.get(k))
    ex = rd(V / "exponents.csv")
    exd = {(e["provider"], e["paradigm"], e["op"]): e for e in ex}
    cpu = rd(V / "cpu_cells.csv")
    cpud = {(c["provider"], c["paradigm"], c["mode"], int(c["conc"])): c for c in cpu}
    em = {(e["provider"], e["op"]): e for e in rd(V / "ext128_multi.csv")}
    eq = rd(V / "equivalence.csv")
    rv = rd(V / "reservoir.csv")
    net = {n["provider"]: n for n in rd(V / "network.csv")}
    v1 = {}
    for r in rd(Path(a.v1) / "exponents_recomputed.csv"):
        if r["workload"] == "balanced":
            v1[(r["provider"], r["paradigm"], r["operation"])] = r
    M = []

    # ---------------- completion (from the manifests) ----------------
    comp_rows, tot_att, tot_ok, tot_fail = [], 0, 0, 0
    for p in PROV:
        mf = Path(a.manifests) / p / f"results-rerun-v21-{p}" / "run_manifest.jsonl"
        recs = [json.loads(l) for l in open(mf) if l.strip()]
        by = defaultdict(list)
        for r in recs:
            by[r["run_id"]].append(r)
        planned = sum(1 for k in by)
        ok = sum(1 for k, v in by.items() if any(x.get("status") == "ok" for x in v))
        att = len(recs)
        fail = att - ok
        comp_rows.append((p, planned, att, ok, fail))
        tot_att += att; tot_ok += ok; tot_fail += fail
    d5 = [json.loads(l) for l in open(Path(a.d5) / "results-rerun-v21-azure-mc2" / "run_manifest.jsonl")]
    d5ok = sum(1 for r in d5 if r["status"] == "ok")
    M += [macro("vAttempts", tot_att), macro("vRunsOk", tot_ok), macro("vFailed", tot_fail),
          macro("vDfiveOk", d5ok), macro("vRunsAll", tot_ok + d5ok),
          macro("vAttemptsAll", tot_att + len(d5))]
    wonly = [r for r in runs if r["mode"] == "primary" and r["phases"] == "WRITE"]
    M.append(macro("vWriteOnly", len(wonly)))
    with open(OUT / "tab_v21_completion.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lrrrrl}\n\\toprule\nProvider & Runs & Attempts & Accepted & Failed & Cause of failed attempts \\\\\n\\midrule\n")
        cause = {"huawei": "operator: second-host name not resolvable (D2)",
                 "alibaba": "operator: bucket not emptied (D1); missing credentials (D3)"}
        for p, pl, at, ok, fl in comp_rows:
            fh.write(f"{PNAME[p]} & {pl} & {at} & {ok} & {fl} & {cause.get(p, '--') if fl else '--'} \\\\\n")
        fh.write(f"\\midrule\nTotal & {sum(r[1] for r in comp_rows)} & {tot_att} & {tot_ok} & {tot_fail} & no storage-service or harness failure \\\\\n")
        fh.write(f"Azure two-host (D5) & {len(d5)} & {len(d5)} & {d5ok} & {len(d5) - d5ok} & -- \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")

    # ---------------- exponent table (per operation, both CIs) ----------------
    with open(OUT / "tab_v21_exponents.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llrcccrccc}\n\\toprule\n")
        fh.write(" & & \\multicolumn{4}{c}{Write phase} & \\multicolumn{4}{c}{Read phase} \\\\\n")
        fh.write("\\cmidrule(lr){3-6}\\cmidrule(lr){7-10}\n")
        fh.write("Provider & Paradigm & $\\beta$ & run-level CI & level-mean CI & $L$ & $\\beta$ & run-level CI & level-mean CI & $L$ \\\\\n\\midrule\n")
        for para in PARA:
            for p in PROV:
                cells = []
                for op in ("write", "read"):
                    e = exd.get((p, para, op))
                    if not e or not e.get("beta"):
                        cells += ["--"] * 4
                        continue
                    lv = int(e["levels"])
                    mark = "$^{\\dagger}$" if lv < 4 else ""
                    cells += [f(e["beta"]) + mark, f"[{f(e['lo_run'],2)}, {f(e['hi_run'],2)}]",
                              f"[{f(e['lo_mean'],2)}, {f(e['hi_mean'],2)}]", str(lv)]
                fh.write(f"{PNAME[p]} & {para} & " + " & ".join(cells) + " \\\\\n")
            if para != "object":
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    for p in PROV:
        for para in PARA:
            for op in ("write", "read", "combined"):
                e = exd.get((p, para, op))
                if e and e.get("beta"):
                    tag = f"{p}{para}{op}".replace("aws", "Aws").replace("azure", "Azure").replace(
                        "gcp", "Gcp").replace("huawei", "Huawei").replace("alibaba", "Alibaba")
                    tag = "b" + tag[0].upper() + tag[1:]
                    tag = tag.replace("block", "Block").replace("file", "File").replace("object", "Object").replace(
                        "write", "W").replace("read", "R").replace("combined", "C")
                    M.append(macro(tag, f(e["beta"])))
                    M.append(macro(tag + "lo", f(e["lo_run"], 2)))
                    M.append(macro(tag + "hi", f(e["hi_run"], 2)))
    from collections import Counter
    cnt = Counter()
    for e in ex:
        if e["op"] == "combined" or not e.get("beta"):
            continue
        lv = int(e["levels"]); pa = e["paradigm"]
        run_ex = float(e["lo_run"]) > 0 or float(e["hi_run"]) < 0
        mean_ex = float(e["lo_mean"]) > 0 or float(e["hi_mean"]) < 0
        cnt[(pa, lv, "n")] += 1; cnt[(pa, lv, "run")] += run_ex; cnt[(pa, lv, "mean")] += mean_ex
    for pa in PARA:
        for lv, nm in ((4, "Four"), (3, "Three")):
            for k in ("n", "run", "mean"):
                M.append(macro(f"vCi{pa.capitalize()}{nm}{k.capitalize()}", cnt[(pa, lv, k)]))
    obj_comb = [float(exd[(p, "object", "combined")]["beta"]) for p in PROV
                if exd.get((p, "object", "combined")) and exd[(p, "object", "combined")].get("beta")]
    M.append(macro("vObjCombMin", f(min(obj_comb))))
    M.append(macro("vObjCombMax", f(max(obj_comb))))

    # ---------------- replication table v1 vs v2.1 ----------------
    with open(OUT / "tab_v21_replication.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llcccc}\n\\toprule\n")
        fh.write(" & & \\multicolumn{2}{c}{Write $\\beta$} & \\multicolumn{2}{c}{Read $\\beta$} \\\\\n")
        fh.write("\\cmidrule(lr){3-4}\\cmidrule(lr){5-6}\nProvider & Paradigm & Earlier & Present & Earlier & Present \\\\\n\\midrule\n")
        shifts = []
        for para in PARA:
            for p in PROV:
                row = []
                for op in ("write", "read"):
                    o = v1.get((p, para, op)); n = exd.get((p, para, op))
                    ov = num(o["beta"]) if o else None
                    nv = num(n["beta"]) if n and n.get("beta") else None
                    row += [f(ov), f(nv) + ("$^{\\dagger}$" if n and n.get("levels") and int(n["levels"]) < 4 else "")]
                    if ov is not None and nv is not None:
                        shifts.append((abs(nv - ov), p, para, op))
                fh.write(f"{PNAME[p]} & {para} & " + " & ".join(row) + " \\\\\n")
            if para != "object":
                fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    obj_shift = max(s[0] for s in shifts if s[2] == "object")
    M.append(macro("vObjMaxShiftVone", f(obj_shift, 2)))
    M.append(macro("vObjMaxShiftElb", f(max(s[0] for s in shifts if s[2] == "object" and s[1] != "azure"), 2)))
    M.append(macro("vMaxShiftAll", f(max(s[0] for s in shifts), 2)))

    # ---------------- client vs service table ----------------
    d5agg = {"write": [], "read": []}
    d5h = {"host1": {"write": [], "read": []}, "host2": {"write": [], "read": []}}
    d5cpu = []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from analyze_v21 import mpstat
    for r in d5:
        tot = {}
        for h in ("host1", "host2"):
            rows = {x["operation"]: x for x in csv.DictReader(open(Path(a.d5) / r[f"raw_{h}_csv"]))}
            for op in rows:
                v = float(rows[op]["throughput_mb_s"]) * MB_TO_MIB
                d5h[h][op].append(v); tot[op] = tot.get(op, 0) + v
            d5cpu.append(mpstat(Path(a.d5) / r[f"raw_{h}_mpstat_txt"])["cpu_all"])
        for op in tot:
            d5agg[op].append(tot[op])
    with open(OUT / "tab_v21_clientservice.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{llrrrrrl}\n\\toprule\n")
        fh.write("Provider & Op. & 64 thr., 1 host & 128 thr., 1 host & 2 hosts $\\times$ 64 & $\\times$128 & $\\times$2 hosts & CPU \\% (64 / 128 / 2-host) \\\\\n\\midrule\n")
        for p in PROV:
            for op in ("write", "read"):
                if p == "azure":
                    b64 = st.mean(r[f"{op}_tput"] for r in runs if r["provider"] == p and r["paradigm"] == "object"
                                  and r["mode"] == "primary" and r["conc"] == 64)
                    c128 = st.mean(r[f"{op}_tput"] for r in runs if r["provider"] == p and r["mode"] == "ext128")
                    mc = st.mean(d5agg[op])
                    c2 = f"{st.mean(d5cpu):.0f}"
                    note = "$^{\\ddagger}$"
                else:
                    e = em[(p, op)]
                    b64, c128, mc = float(e["c64_1host"]), float(e["c128_1host"]), float(e["c64x2_hosts"])
                    c2 = f"{float(cpud[(p, 'object', 'multi', 64)]['cpu_all']):.0f}"
                    note = ""
                c64c = f"{float(cpud[(p, 'object', 'primary', 64)]['cpu_all']):.0f}"
                c128c = f"{float(cpud[(p, 'object', 'ext128', 128)]['cpu_all']):.0f}"
                name = PNAME[p] + note if op == "write" else ""
                cpus = f"{c64c} / {c128c} / {c2}" if op == "write" else ""
                fh.write(f"{name} & {op} & {b64:.1f} & {c128:.1f} & {mc:.1f} & {c128 / b64:.2f} & {mc / b64:.2f} & "
                         f"{cpus} \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    b64w = st.mean(r["write_tput"] for r in runs if r["provider"] == "azure" and r["paradigm"] == "object"
                   and r["mode"] == "primary" and r["conc"] == 64)
    b64r = st.mean(r["read_tput"] for r in runs if r["provider"] == "azure" and r["paradigm"] == "object"
                   and r["mode"] == "primary" and r["conc"] == 64)
    M += [macro("vDfiveWagg", f(st.mean(d5agg["write"]), 1)), macro("vDfiveRagg", f(st.mean(d5agg["read"]), 1)),
          macro("vDfiveWratio", f(st.mean(d5agg["write"]) / b64w, 2)),
          macro("vDfiveRratio", f(st.mean(d5agg["read"]) / b64r, 2)),
          macro("vDfiveHostOneW", f(st.mean(d5h["host1"]["write"]) / b64w, 2)),
          macro("vDfiveHostOneR", f(st.mean(d5h["host1"]["read"]) / b64r, 2)),
          macro("vDfiveHostTwoRel", f(st.mean(d5h["host2"]["write"]) / st.mean(d5h["host1"]["write"]), 2)),
          macro("vDfiveCpu", f(min(d5cpu), 1)),
          macro("vAzObjWsixtyfour", f(b64w, 1)), macro("vAzObjRsixtyfour", f(b64r, 1))]
    for p in ("aws", "gcp", "huawei", "alibaba"):
        for op in ("write", "read"):
            e = em[(p, op)]
            M.append(macro(f"v{PNAME[p]}{op.capitalize()}TwoHost", f(e["ratio_2hosts"], 2)))
            M.append(macro(f"v{PNAME[p]}{op.capitalize()}OneTwentyEight", f(e["ratio_128"], 2)))
    for p in PROV:
        M.append(macro(f"v{PNAME[p]}CpuSixtyFour", f(cpud[(p, "object", "primary", 64)]["cpu_all"], 0)))
        M.append(macro(f"v{PNAME[p]}CpuOneTwentyEight", f(cpud[(p, "object", "ext128", 128)]["cpu_all"], 0)))
    M.append(macro("vAzCpuSixteen", f(cpud[("azure", "object", "primary", 16)]["cpu_all"], 0)))
    gaps = [float(c["cpu_maxcore"]) - float(c["cpu_all"]) for c in cpu if float(c["cpu_all"]) >= 50]
    M.append(macro("vMaxCoreGapHigh", f(max(gaps), 1)))
    M.append(macro("vMaxCoreLow", f(max(float(c["cpu_maxcore"]) for c in cpu if float(c["cpu_all"]) < 50), 0)))

    # ---------------- equivalence / reservoir ----------------
    with open(OUT / "tab_v21_equiv.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{rrrrrrr}\n\\toprule\n")
        fh.write("Threads & \\multicolumn{2}{c}{Runner / elbencho throughput} & \\multicolumn{2}{c}{p99 (ms), runner / elbencho} & \\multicolumn{2}{c}{Client CPU (\\%)} \\\\\n")
        fh.write("\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\n & write & read & write & read & runner & elbencho \\\\\n\\midrule\n")
        for c in (1, 4, 16, 64):
            w = next(e for e in eq if e["conc"] == str(c) and e["op"] == "write")
            r = next(e for e in eq if e["conc"] == str(c) and e["op"] == "read")
            cr = float(cpud[("aws", "object", "equiv", c)]["cpu_all"])
            ce = float(cpud[("aws", "object", "primary", c)]["cpu_all"])
            fh.write(f"{c} & {float(w['runner_over_elbencho']):.2f} & {float(r['runner_over_elbencho']):.2f} & "
                     f"{float(w['runner_p99']):.0f} / {float(w['elbencho_p99']):.0f} & "
                     f"{float(r['runner_p99']):.0f} / {float(r['elbencho_p99']):.0f} & {cr:.0f} & {ce:.0f} \\\\\n")
        bet = {(e["op"], e["tool"]): e for e in eq if e["conc"] == "beta"}
        fh.write("\\midrule\n$\\beta$ & \\multicolumn{6}{l}{write: runner " + f(bet[("write", "runner")]["beta"], 2)
                 + f" [{f(bet[('write','runner')]['lo'],2)}, {f(bet[('write','runner')]['hi'],2)}], elbencho "
                 + f(bet[("write", "elbencho")]["beta"], 2) + f" [{f(bet[('write','elbencho')]['lo'],2)}, {f(bet[('write','elbencho')]['hi'],2)}]"
                 + "; read: runner " + f(bet[("read", "runner")]["beta"], 2)
                 + f" [{f(bet[('read','runner')]['lo'],2)}, {f(bet[('read','runner')]['hi'],2)}], elbencho "
                 + f(bet[("read", "elbencho")]["beta"], 2) + f" [{f(bet[('read','elbencho')]['lo'],2)}, {f(bet[('read','elbencho')]['hi'],2)}]" + "} \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    for c in (1, 4, 16, 64):
        for op in ("write", "read"):
            e = next(x for x in eq if x["conc"] == str(c) and x["op"] == op)
            M.append(macro(f"vEq{op.capitalize()}{['One','Four','Sixteen','SixtyFour'][[1,4,16,64].index(c)]}",
                           f(e["runner_over_elbencho"], 2)))
    for k, v in bet.items():
        M.append(macro(f"vEqBeta{k[0].capitalize()}{k[1].capitalize()}", f(v["beta"], 2)))
    with open(OUT / "tab_v21_reservoir.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{rrrr}\n\\toprule\nThreads & Reservoir per thread & write p99 (ms) & read p99 (ms) \\\\\n\\midrule\n")
        grp = defaultdict(list)
        for r in rv:
            grp[(int(r["conc"]), int(float(r["lat_cap"])))].append(r)
        for (c, cap), rs in sorted(grp.items()):
            wv = [float(x["write_p99_ms"]) for x in rs]; rv_ = [float(x["read_p99_ms"]) for x in rs]
            ws = f"{min(wv):.0f}--{max(wv):.0f}" if len(wv) > 1 else f"{wv[0]:.0f}"
            rs_ = f"{min(rv_):.0f}--{max(rv_):.0f}" if len(rv_) > 1 else f"{rv_[0]:.0f}"
            fh.write(f"{c} & {cap:,} ({len(rs)} run{'s' if len(rs) > 1 else ''}) & {ws} & {rs_} \\\\\n".replace(",", "{,}"))
        fh.write("\\bottomrule\n\\end{tabular}\n")

    # ---------------- block vs documented limits; network ----------------
    with open(OUT / "tab_v21_block.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lp{2.6cm}rrrp{4.2cm}}\n\\toprule\n")
        fh.write("Provider & Product & Write, 4 thr. & Write, 16 thr. & Read, 4+ thr. & Documented limit \\\\\n\\midrule\n")
        for p in PROV:
            def lm(op, c):
                v = [r[f"{op}_tput"] for r in runs if r["provider"] == p and r["paradigm"] == "block"
                     and r["mode"] == "primary" and r["conc"] == c and r[f"{op}_tput"]]
                return st.mean(v) if v else None
            reads = [lm("read", c) for c in (4, 16, 64) if lm("read", c)]
            fh.write(f"{PNAME[p]} & {DOCS[p][0]} & {lm('write',4):.0f} & {lm('write',16):.0f} & "
                     f"{(str(round(min(reads))) + '--' + str(round(max(reads)))) if round(min(reads)) != round(max(reads)) else round(min(reads))} & {DOCS[p][1]} \\\\\n")
        fh.write("\\bottomrule\n\\end{tabular}\n")
    with open(OUT / "tab_v21_network.tex", "w", newline="\n") as fh:
        fh.write("\\begin{tabular}{lrrrrr}\n\\toprule\nProvider & send (Gbit/s) & receive & 600 s sustained & first / last 60 s & retransmits \\\\\n\\midrule\n")
        for p in PROV:
            n = net[p]
            fh.write(f"{PNAME[p]} & {f(n['send_gbit_median'],2)} & {f(n['receive_gbit_median'],2)} & {f(n['sustained_600s_gbit'],2)} & "
                     f"{f(n['first60'],2)} / {f(n['last60'],2)} & {int(float(n['retransmits'])):,} \\\\\n".replace(",", "{,}"))
        fh.write("\\bottomrule\n\\end{tabular}\n")
        for p in PROV:
            M.append(macro(f"vNet{PNAME[p]}", f(net[p]["sustained_600s_gbit"], 2)))

    # block write volume effect: v1 fixed 20 GB at c4 vs v2.1 5 GB at c4
    v1runs = rd(Path(a.v1) / "runs_recomputed.csv")
    for p in ("aws", "gcp", "huawei"):
        v = [float(r["write_tput_mib_s"]) for r in v1runs if r["provider"] == p and r["paradigm"] == "block"
             and r["workload"] == "balanced" and r["concurrency"] == "4" and r["write_tput_mib_s"]]
        n4 = st.mean(r["write_tput"] for r in runs if r["provider"] == p and r["paradigm"] == "block"
                     and r["mode"] == "primary" and r["conc"] == 4)
        n16 = st.mean(r["write_tput"] for r in runs if r["provider"] == p and r["paradigm"] == "block"
                      and r["mode"] == "primary" and r["conc"] == 16)
        M += [macro(f"v{PNAME[p]}BlkWvOneFour", f(st.mean(v), 0)), macro(f"v{PNAME[p]}BlkWFour", f(n4, 0)),
              macro(f"v{PNAME[p]}BlkWSixteen", f(n16, 0))]

    # p99 folds (median over providers of p99(c64)/p99(c1), per phase and paradigm, primary)
    for para in PARA:
        for op in ("write", "read"):
            folds, folds16 = [], []
            for p in PROV:
                if para == "object" and p == "azure":
                    continue
                def pm(c):
                    v = [r[f"{op}_p99_ms"] for r in runs if r["provider"] == p and r["paradigm"] == para
                         and r["mode"] == "primary" and r["conc"] == c and r[f"{op}_p99_ms"]]
                    return st.mean(v) if v else None
                if pm(1) and pm(64):
                    folds.append(pm(64) / pm(1))
                if pm(1) and pm(16):
                    folds16.append(pm(16) / pm(1))
            if folds:
                M.append(macro(f"vFold{para.capitalize()}{op.capitalize()}", f(st.median(folds), 1)))
                M.append(macro(f"vFold{para.capitalize()}{op.capitalize()}N", len(folds)))
            M.append(macro(f"vFoldS{para.capitalize()}{op.capitalize()}", f(st.median(folds16), 1)))
            M.append(macro(f"vFoldS{para.capitalize()}{op.capitalize()}N", len(folds16)))

    with open(OUT / "v21_macros.tex", "w", newline="\n") as fh:  # LF on every platform
        fh.write("% generated by sweep/make_v21_paper.py -- do not edit\n" + "".join(M))
    figures(runs, ex, exd, v1, em, eq, cpud, d5agg, OUT)
    print(f"wrote {len(M)} macros, tables and figures to {OUT}")


def figures(runs, ex, exd, v1, em, eq, cpud, d5agg, OUT):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
                         "legend.fontsize": 8, "lines.linewidth": 1.4})
    DPI = 600
    # Fig A: throughput vs threads, rows = write/read, cols = paradigm
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.8), sharex=True)
    for i, op in enumerate(("write", "read")):
        for j, para in enumerate(PARA):
            ax = axs[i][j]
            for p in PROV:
                lv = defaultdict(list)
                for r in runs:
                    if r["provider"] == p and r["paradigm"] == para and r["mode"] == "primary" and r[f"{op}_tput"]:
                        lv[r["conc"]].append(r[f"{op}_tput"])
                        ax.scatter(r["conc"], r[f"{op}_tput"], s=6, color=COL[p], alpha=0.35, lw=0)
                cs = sorted(lv)
                ax.plot(cs, [10 ** st.mean(math.log10(v) for v in lv[c]) for c in cs], marker=MARK[p],
                        ms=3.5, color=COL[p], label=PNAME[p])
                if para == "object":
                    e128 = [r[f"{op}_tput"] for r in runs if r["provider"] == p and r["mode"] == "ext128"]
                    if e128:
                        ax.scatter(116, st.mean(e128), marker=MARK[p], facecolor="none", edgecolor=COL[p], s=22)
                    if p == "azure":
                        mc = st.mean(d5agg[op])
                    else:
                        mcv = [r[f"{op}_tput"] for r in runs if r["provider"] == p and r["mode"] == "multi"]
                        mc = st.mean(mcv) if mcv else None
                    if mc:
                        ax.scatter(142, mc, marker="*", color=COL[p], s=40, zorder=5)
            ax.set_xscale("log", base=2); ax.set_yscale("log")
            ax.set_xticks([1, 4, 16, 64, 128]); ax.set_xticklabels(["1", "4", "16", "64", "128"])
            if i == 0:
                ax.set_title(para)
            if j == 0:
                ax.set_ylabel(f"{op} MiB/s")
            if i == 1:
                ax.set_xlabel("client threads (total)")
            ax.grid(True, which="both", lw=0.3, alpha=0.5)
    h, l = axs[0][0].get_legend_handles_labels()
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.025))
    fig.text(0.5, 0.0, "object panels at 128 threads: hollow = one host $\\times$ 128, star = two hosts $\\times$ 64",
             ha="center", fontsize=8)
    fig.savefig(OUT / "figures" / "fig_v21_curves.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)

    # Fig B: exponents v1 vs v2.1, per operation
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 4.2), sharey=True)
    labels = [f"{PNAME[p]} {para}" for para in PARA for p in PROV]
    for k, op in enumerate(("write", "read")):
        ax = axs[k]
        for y, (para, p) in enumerate([(pa, p) for pa in PARA for p in PROV]):
            n = exd.get((p, para, op)); o = v1.get((p, para, op))
            if o:
                b, lo, hi = float(o["beta"]), float(o["ci_lo"]), float(o["ci_hi"])
                ax.errorbar(b, y + 0.17, xerr=[[b - lo], [hi - b]], fmt="o", ms=3, color="0.6", lw=0.9,
                            label="earlier campaign (Aug 2026)" if y == 0 else None)
            if n and n.get("beta"):
                b, lo, hi = float(n["beta"]), float(n["lo_run"]), float(n["hi_run"])
                ax.errorbar(b, y - 0.17, xerr=[[b - lo], [hi - b]], fmt="s", ms=3, color=COL[p], lw=1.1,
                            label="present campaign (Oct 2026)" if y == 0 else None)
        ax.axvline(0, color="k", lw=0.5); ax.axvline(1, color="k", lw=0.5, ls="--")
        ax.set_title(f"{op} phase"); ax.set_xlabel("$\\beta$ (95% CI, run level)")
        ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
        ax.invert_yaxis(); ax.grid(True, axis="x", lw=0.3, alpha=0.5)
    axs[0].legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fig_v21_exponents.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)

    # Fig C: client vs service ratios
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    xs, i = [], 0
    for p in PROV:
        for op in ("write", "read"):
            if p == "azure":
                b64 = st.mean(r[f"{op}_tput"] for r in runs if r["provider"] == p and r["paradigm"] == "object"
                              and r["mode"] == "primary" and r["conc"] == 64)
                r128 = st.mean(r[f"{op}_tput"] for r in runs if r["provider"] == p and r["mode"] == "ext128") / b64
                r2 = st.mean(d5agg[op]) / b64
            else:
                r128, r2 = float(em[(p, op)]["ratio_128"]), float(em[(p, op)]["ratio_2hosts"])
            ax.bar(i - 0.2, r128, 0.38, color=COL[p], alpha=0.45, edgecolor=COL[p])
            ax.bar(i + 0.2, r2, 0.38, color=COL[p], edgecolor="k", lw=0.4)
            xs.append((i, f"{PNAME[p]}\n{op}")); i += 1
        i += 0.5
    ax.axhline(1, color="k", lw=0.6); ax.axhline(2, color="k", lw=0.6, ls="--")
    ax.set_xticks([x for x, _ in xs]); ax.set_xticklabels([l for _, l in xs], fontsize=7)
    ax.set_ylabel("throughput / (64 threads, 1 host)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor="0.7", alpha=0.45, label="128 threads, one host"),
                       Patch(facecolor="0.4", edgecolor="k", label="two hosts $\\times$ 64 threads")],
              loc="upper right", frameon=False, ncol=2)
    ax.set_ylim(0, 2.4); ax.grid(True, axis="y", lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fig_v21_clientservice.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)

    # Fig D: p99 per phase
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.6), sharex=True)
    for i, op in enumerate(("write", "read")):
        for j, para in enumerate(PARA):
            ax = axs[i][j]
            for p in PROV:
                lv = defaultdict(list)
                for r in runs:
                    if r["provider"] == p and r["paradigm"] == para and r["mode"] == "primary" and r[f"{op}_p99_ms"]:
                        lv[r["conc"]].append(r[f"{op}_p99_ms"])
                cs = sorted(lv)
                if cs:
                    ax.plot(cs, [st.mean(lv[c]) for c in cs], marker=MARK[p], ms=3.5, color=COL[p],
                            label=PNAME[p], ls=":" if (para == "object" and p == "azure") else "-")
            ax.set_xscale("log", base=2); ax.set_yscale("log")
            ax.set_xticks([1, 4, 16, 64]); ax.set_xticklabels(["1", "4", "16", "64"])
            if i == 0:
                ax.set_title(para)
            if j == 0:
                ax.set_ylabel(f"{op} p99 (ms)")
            if i == 1:
                ax.set_xlabel("client threads")
            ax.grid(True, which="both", lw=0.3, alpha=0.5)
    axs[0][0].legend(loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fig_v21_p99.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)

    # Fig E: runner equivalence on AWS S3
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    for op, mk in (("write", "o"), ("read", "s")):
        cs = [1, 4, 16, 64]
        el = [float(next(e for e in eq if e["conc"] == str(c) and e["op"] == op)["elbencho_tput"]) for c in cs]
        rn = [float(next(e for e in eq if e["conc"] == str(c) and e["op"] == op)["runner_tput"]) for c in cs]
        ax.plot(cs, el, marker=mk, color="k", label=f"elbencho {op}")
        ax.plot(cs, rn, marker=mk, color=COL["azure"], ls="--", label=f"SDK runner {op}")
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xticks([1, 4, 16, 64]); ax.set_xticklabels(["1", "4", "16", "64"])
    ax.set_xlabel("client threads"); ax.set_ylabel("MiB/s (AWS S3)")
    ax.legend(frameon=False, fontsize=7); ax.grid(True, which="both", lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fig_v21_equiv.png", dpi=DPI, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    main()
