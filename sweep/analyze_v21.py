#!/usr/bin/env python3
"""
analyze_v21.py -- analysis of the v2.1 rerun (SWEEP_PROTOCOL_V2_1_AMENDMENT.md),
organised around the Future Internet reviewers' comments.

Input: one extracted rerun archive per provider, laid out as
    <root>/<provider>/results-rerun-v21-<provider>/run_manifest.jsonl
    <root>/<provider>/results-rerun-v21-<provider>/raw/*
    <root>/<provider>/results-rerun-v21-<provider>/netbaseline_<provider>.json
    <root>/<provider>/sweep/netbaseline_<provider>_600s.json   (if present)

Conventions (same as recompute_from_raw.py for v1):
  * elbencho phase throughput = phase MiB / phase seconds, both "[last]"
    (the slowest thread), final attempt only (csv files append on retry).
  * combined = (write MiB + read MiB) / (write s + read s); defined only
    when both phases are present (write-only runs hit --timelimit 600,
    protocol v2 section 3: they enter write fits only).
  * p99 per phase from elbencho stdout "IO lat % us" (log-binned).
  * SDK runners (azure_blob_runner_v2, s3_equiv_runner) report MB/s (1e6);
    converted to MiB/s here so every throughput is in MiB/s.
  * CPU busy = 100 - %idle - %iowait from mpstat -P ALL (5 s).
  * Exponent beta = OLS slope of log10(throughput) on log10(concurrency),
    primary runs at 1/4/16/64 threads. Two 95% intervals: run-level
    (t, n-2 df) and level-mean (fit on the level means, t, k-2 df).

Outputs (to --out, default ./v21-output/): runs.csv, exponents.csv,
cpu_cells.csv, ext128_multi.csv, equivalence.csv, reservoir.csv,
network.csv, completion.csv, summary.txt
"""
from __future__ import annotations
import argparse, csv, json, math, re, statistics as st
from collections import defaultdict
from pathlib import Path

MB_TO_MIB = 1e6 / 1048576
PCT = re.compile(r"IO lat % us\s*:\s*\[([^\]]+)\]")
P99 = re.compile(r"99%<=(\d+)")
PH = re.compile(r"^(WRITE|READ)\s")
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 16: 2.120, 18: 2.101, 20: 2.086, 22: 2.074}


def tcrit(df):
    if df in T975:
        return T975[df]
    return T975[max(k for k in T975 if k <= df)] if df > 1 else float("nan")


def ols(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - a - b * x for x, y in zip(xs, ys)]
    sse = sum(r * r for r in res)
    sst = sum((y - my) ** 2 for y in ys)
    se = math.sqrt(sse / (n - 2) / sxx) if n > 2 else float("nan")
    h = tcrit(n - 2) * se
    return dict(beta=b, se=se, lo=b - h, hi=b + h, n=n,
                r2=1 - sse / sst if sst else float("nan"))


def final_phases(csv_path):
    rows = list(csv.DictReader(open(csv_path)))
    if not rows:
        return {}
    idx = max((i for i, r in enumerate(rows) if r["operation"] == "READ"), default=None)
    if idx is not None and idx > 0 and rows[idx - 1]["operation"] == "WRITE":
        sel = [rows[idx - 1], rows[idx]]
    elif idx is not None:
        sel = [rows[idx]]
    else:
        sel = [rows[max(i for i, r in enumerate(rows) if r["operation"] == "WRITE")]]
    out = {}
    for r in sel:
        mib, ms = float(r["MiB [last]"]), float(r["time ms [last]"])
        out[r["operation"].lower()] = dict(mib=mib, s=ms / 1000.0,
                                          tput=mib / (ms / 1000.0) if ms else float("nan"))
    return out


def stdout_p99(path):
    out, cur = {}, None
    try:
        for line in open(path, errors="ignore"):
            m = PH.match(line)
            if m:
                cur = m.group(1).lower()
            m = PCT.search(line)
            if m and cur:
                m99 = P99.search(m.group(1))
                if m99:
                    out[cur] = int(m99.group(1)) / 1000.0
    except FileNotFoundError:
        pass
    return out


def runner_phases(csv_path):
    out = {}
    for r in csv.DictReader(open(csv_path)):
        out[r["operation"]] = dict(tput=float(r["throughput_mb_s"]) * MB_TO_MIB,
                                   p99=float(r["lat_p99_ms"]),
                                   mean_ms=float(r["lat_mean_ms"]))
    return out


def mpstat(path):
    """Per-run CPU: mean all-CPU busy, mean of the busiest core, share of
    samples where any core is >= 90 % busy."""
    samples = defaultdict(dict)
    hdr = None
    try:
        for line in open(path, errors="ignore"):
            parts = line.split()
            if "CPU" in parts and "%idle" in parts:
                hdr = parts
                continue
            if not hdr or len(parts) != len(hdr) or parts[0] == "Average:":
                continue
            ci = hdr.index("CPU")
            try:
                idle = float(parts[hdr.index("%idle")])
                iow = float(parts[hdr.index("%iowait")])
            except ValueError:
                continue
            samples[parts[0]][parts[ci]] = 100.0 - idle - iow
    except FileNotFoundError:
        return {}
    alls, maxc, hot = [], [], 0
    for t, d in samples.items():
        cores = [v for k, v in d.items() if k != "all"]
        if "all" in d and cores:
            alls.append(d["all"])
            maxc.append(max(cores))
            hot += max(cores) >= 90.0
    if not alls:
        return {}
    return dict(cpu_all=st.mean(alls), cpu_maxcore=st.mean(maxc),
                cpu_all_p95=sorted(alls)[int(0.95 * (len(alls) - 1))],
                hot_share=hot / len(alls), n_samples=len(alls))


def load(root, prov):
    base = root / prov
    d = base / f"results-rerun-v21-{prov}"
    recs = [json.loads(l) for l in open(d / "run_manifest.jsonl") if l.strip()]
    attempts = defaultdict(list)
    for r in recs:
        attempts[r["run_id"]].append(r)
    runs = []
    for rid, att in attempts.items():
        ok = [r for r in att if r.get("status") == "ok"]
        if not ok:
            continue
        r = ok[-1]
        row = dict(run_id=rid, provider=prov, paradigm=r["paradigm"], mode=r["mode"],
                   conc=r["concurrency"], rep=r["rep"], hosts=r.get("hosts", 1),
                   tool=r.get("tool", ""), lat_cap=r.get("lat_cap", ""),
                   attempts=len(att), dataset_mib=r.get("dataset_mib"),
                   stage=r.get("stage"))
        csvp = base / r["raw_csv"]
        if r.get("tool") == "elbencho":
            ph = final_phases(csvp)
            p99 = stdout_p99(base / r["raw_log"])
        else:
            ph = runner_phases(csvp)
            p99 = {k: v["p99"] for k, v in ph.items()}
        for op in ("write", "read"):
            row[f"{op}_tput"] = ph.get(op, {}).get("tput")
            row[f"{op}_p99_ms"] = p99.get(op)
            row[f"{op}_mib"] = ph.get(op, {}).get("mib")
            row[f"{op}_s"] = ph.get(op, {}).get("s")
        if all(row.get(f"{op}_s") for op in ("write", "read")):
            row["combined_tput"] = ((row["write_mib"] + row["read_mib"]) /
                                    (row["write_s"] + row["read_s"]))
        elif r.get("tool") != "elbencho" and row["write_tput"] and row["read_tput"]:
            row["combined_tput"] = None   # duration-driven: no shared byte total
        else:
            row["combined_tput"] = None
        row["phases"] = "+".join(op.upper() for op in ("write", "read") if row[f"{op}_tput"])
        row.update(mpstat(base / r["telemetry"]))
        runs.append(row)
    return runs, attempts


def exponents(runs):
    out = []
    cells = defaultdict(list)
    for r in runs:
        if r["mode"] == "primary":
            cells[(r["provider"], r["paradigm"])].append(r)
    for (prov, para), rs in sorted(cells.items()):
        for op in ("write", "read", "combined"):
            pts = [(r["conc"], r[f"{op}_tput"]) for r in rs
                   if r.get(f"{op}_tput")]
            xs = [math.log10(c) for c, _ in pts]
            ys = [math.log10(v) for _, v in pts]
            f = ols(xs, ys)
            lv = defaultdict(list)
            for c, v in pts:
                lv[c].append(math.log10(v))
            levels = sorted(lv)
            fm = ols([math.log10(c) for c in levels], [st.mean(lv[c]) for c in levels])
            row = dict(provider=prov, paradigm=para, op=op, levels=len(levels),
                       n=len(pts), levels_present="/".join(map(str, levels)))
            if f:
                row.update(beta=f["beta"], se=f["se"], lo_run=f["lo"], hi_run=f["hi"],
                           r2=f["r2"])
            if fm:
                row.update(lo_mean=fm["lo"], hi_mean=fm["hi"])
            # level means for the record
            for c in levels:
                row[f"mean_c{c}"] = 10 ** st.mean(lv[c])
            out.append(row)
    return out


def write_csv(path, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="dir with one extracted archive per provider")
    ap.add_argument("--providers", default="aws,azure,gcp,huawei,alibaba")
    ap.add_argument("--out", default="v21-output")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    runs, completion, net = [], [], []
    for prov in a.providers.split(","):
        if not (root / prov / f"results-rerun-v21-{prov}").exists():
            continue
        rs, att = load(root, prov)
        runs += rs
        by = defaultdict(lambda: [0, 0])
        for rid, al in att.items():
            para = al[-1]["paradigm"]
            by[para][0] += len(al)
            by[para][1] += any(x.get("status") == "ok" for x in al)
        for para, (n_att, n_ok) in sorted(by.items()):
            completion.append(dict(provider=prov, paradigm=para, attempts=n_att,
                                   runs_ok=n_ok))
        nb = root / prov / f"results-rerun-v21-{prov}" / f"netbaseline_{prov}.json"
        row = dict(provider=prov)
        if nb.exists():
            d = json.load(open(nb))
            for dirn in ("send", "receive"):
                v = [x["gbit_s"] for x in d["runs"] if x["direction"] == dirn]
                row[f"{dirn}_gbit_median"] = st.median(v) if v else None
        n6 = root / prov / "sweep" / f"netbaseline_{prov}_600s.json"
        if not n6.exists():
            n6 = root.parent / f"netbaseline_{prov}_600s.json"
        if n6.exists():
            d = json.load(open(n6))
            iv = [i["sum"]["bits_per_second"] / 1e9 for i in d["intervals"]]
            row.update(sustained_600s_gbit=d["end"]["sum_sent"]["bits_per_second"] / 1e9,
                       first60=st.mean(iv[:60]), last60=st.mean(iv[-60:]),
                       retransmits=d["end"]["sum_sent"].get("retransmits"))
        net.append(row)
    write_csv(out / "runs.csv", runs)
    ex = exponents(runs)
    write_csv(out / "exponents.csv", ex)
    write_csv(out / "completion.csv", completion)
    write_csv(out / "network.csv", net)

    # CPU per cell (primary + ext128 + multi)
    cpu = []
    cells = defaultdict(list)
    for r in runs:
        cells[(r["provider"], r["paradigm"], r["mode"], r["conc"])].append(r)
    for k, rs in sorted(cells.items()):
        v = [r for r in rs if "cpu_all" in r]
        if not v:
            continue
        cpu.append(dict(provider=k[0], paradigm=k[1], mode=k[2], conc=k[3], n=len(v),
                        cpu_all=st.mean(r["cpu_all"] for r in v),
                        cpu_all_p95=max(r["cpu_all_p95"] for r in v),
                        cpu_maxcore=st.mean(r["cpu_maxcore"] for r in v),
                        hot_share=st.mean(r["hot_share"] for r in v)))
    write_csv(out / "cpu_cells.csv", cpu)

    # 128 threads and two clients against 64 threads on one host (object)
    em = []
    for prov in sorted({r["provider"] for r in runs}):
        def m(mode, c, op):
            v = [r[f"{op}_tput"] for r in runs if r["provider"] == prov and
                 r["paradigm"] == "object" and r["mode"] == mode and r["conc"] == c
                 and r.get(f"{op}_tput")]
            return (st.mean(v), len(v)) if v else (None, 0)
        for op in ("write", "read", "combined"):
            b64, n64 = m("primary", 64, op)
            e128, n128 = m("ext128", 128, op)
            mc, nmc = m("multi", 64, op)
            if b64 is None:
                continue
            row = dict(provider=prov, op=op, c64_1host=b64, n64=n64)
            if e128:
                row.update(c128_1host=e128, n128=n128, ratio_128=e128 / b64,
                           local_beta_64_128=math.log(e128 / b64, 2))
            if mc:
                row.update(c64x2_hosts=mc, nmc=nmc, ratio_2hosts=mc / b64,
                           local_beta_2hosts=math.log(mc / b64, 2))
            if e128 and mc:
                row["two_hosts_over_128"] = mc / e128
            em.append(row)
    write_csv(out / "ext128_multi.csv", em)

    # Equivalence (AWS): elbencho primary vs s3_equiv_runner at same levels
    eq = []
    for c in (1, 4, 16, 64):
        for op in ("write", "read"):
            e = [r for r in runs if r["provider"] == "aws" and r["paradigm"] == "object"
                 and r["mode"] == "primary" and r["conc"] == c and r.get(f"{op}_tput")]
            s = [r for r in runs if r["provider"] == "aws" and r["mode"] == "equiv"
                 and r["conc"] == c and r.get(f"{op}_tput")]
            if not e or not s:
                continue
            te, ts = st.mean(r[f"{op}_tput"] for r in e), st.mean(r[f"{op}_tput"] for r in s)
            pe = [r[f"{op}_p99_ms"] for r in e if r.get(f"{op}_p99_ms")]
            ps = [r[f"{op}_p99_ms"] for r in s if r.get(f"{op}_p99_ms")]
            eq.append(dict(conc=c, op=op, elbencho_tput=te, runner_tput=ts,
                           runner_over_elbencho=ts / te,
                           elbencho_p99=st.mean(pe) if pe else None,
                           runner_p99=st.mean(ps) if ps else None,
                           elbencho_cv=st.pstdev([r[f"{op}_tput"] for r in e]) / te,
                           runner_cv=st.pstdev([r[f"{op}_tput"] for r in s]) / ts))
    for op in ("write", "read"):
        for tool, mode in (("elbencho", "primary"), ("runner", "equiv")):
            pts = [(r["conc"], r[f"{op}_tput"]) for r in runs if r["provider"] == "aws"
                   and r["paradigm"] == "object" and r["mode"] == mode and r.get(f"{op}_tput")]
            f = ols([math.log10(c) for c, _ in pts], [math.log10(v) for _, v in pts])
            if f:
                eq.append(dict(conc="beta", op=op, tool=tool, beta=f["beta"],
                               lo=f["lo"], hi=f["hi"], n=f["n"]))
    write_csv(out / "equivalence.csv", eq)

    rv = []
    for r in sorted(runs, key=lambda r: (r["conc"], str(r["lat_cap"]))):
        if r["provider"] == "aws" and r["mode"] in ("reservoir", "equiv") and r["conc"] in (16, 64):
            rv.append(dict(run_id=r["run_id"], conc=r["conc"],
                           lat_cap=r["lat_cap"] or 10000,
                           write_p99_ms=r["write_p99_ms"], read_p99_ms=r["read_p99_ms"],
                           write_tput=r["write_tput"], read_tput=r["read_tput"]))
    write_csv(out / "reservoir.csv", rv)
    print(f"{len(runs)} runs analysed -> {out}/")


if __name__ == "__main__":
    main()
