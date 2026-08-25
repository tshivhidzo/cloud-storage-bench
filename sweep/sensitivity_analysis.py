#!/usr/bin/env python3
"""Completion-selection and sizing-regime sensitivity analyses.

Two analyses the measurement manuscript reports:

1. Attempt-level completion analysis: attempts, acceptances and failure
   stages by paradigm, workload and concurrency, from the same per-provider
   run_manifest.jsonl files used by recompute_from_raw.py.  Failure stages:
     provisioning  -- terraform apply / control-plane (incl. purge timeout)
     timeout       -- measurement window exceeded
     tool_exit     -- benchmark tool exited nonzero
   Outputs: attempts_by_cell.csv, table_completion.tex, and macros appended
   to sensitivity_macros.tex.

2. Sizing-regime stratified exponent fits: per-operation OLS of
   log10(throughput) on log10(concurrency) computed separately for
   (a) runs whose executed dataset equals the fixed total (20 GB balanced /
       40 GB large-object) and
   (b) runs consistent with the weak-scaling rule
       (base * concurrency/16, capped at 80 GB).
   c16 runs satisfy both rules and are included in both strata (stated in
   the manuscript).  Azure object duration-driven runs have no dataset
   target and appear in neither stratum.  A stratum cell is fitted only
   when >= 3 concurrency levels are present.
   Outputs: sensitivity_sizing.csv, table_sizing.tex.

All outputs are written with LF newlines explicitly (csv writers use
newline="" with lineterminator="\n"; text writers pass newline="\n"), so
regeneration is byte-identical to the committed files on every platform;
sweep/test_pipeline.py enforces this end to end.

Run from the repository root: python3 sweep/sensitivity_analysis.py
"""
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

DIRS = {"aws": "results-sweep-aws", "azure": "results-sweep-azure",
        "gcp": "results-sweep-gcp", "huawei": "results-sweep-huawei",
        "alibaba": "results-sweep-alibaba"}
OUT = Path("recompute-output")
BASE = {"balanced": 20.0, "largeobj": 40.0}
TOL = 1.5


def classify_failure(err):
    e = (err or "").lower()
    if "terraform" in e or "timeoutexpired" in e:
        return "provisioning"
    if "measurement timed out" in e:
        return "timeout"
    if "tool exited" in e:
        return "tool_exit"
    return "other"


def load_attempts():
    rows = []
    for prov, d in DIRS.items():
        for line in open(Path(d) / "run_manifest.jsonl"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({
                "provider": prov, "paradigm": r["paradigm"],
                "workload": r["workload"], "concurrency": int(r["concurrency"]),
                "status": r.get("status", ""),
                "stage": "" if r.get("status") == "ok"
                         else classify_failure(r.get("error", "")),
            })
    return rows


def completion_tables(rows):
    total = len(rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    fails = [r for r in rows if r["status"] != "ok"]
    stages = defaultdict(int)
    for r in fails:
        stages[r["stage"]] += 1

    # by paradigm x concurrency (all workloads), and object-only by concurrency
    cell = defaultdict(lambda: [0, 0])  # (paradigm, c) -> [attempts, ok]
    exec_fail = defaultdict(int)        # (paradigm, c) -> execution-stage failures
    for r in rows:
        k = (r["paradigm"], r["concurrency"])
        cell[k][0] += 1
        if r["status"] == "ok":
            cell[k][1] += 1
        elif r["stage"] in ("timeout", "tool_exit"):
            exec_fail[k] += 1

    with open(OUT / "attempts_by_cell.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["paradigm", "workload", "concurrency", "attempts",
                    "accepted", "provisioning", "timeout", "tool_exit"])
        agg = defaultdict(lambda: [0, 0, 0, 0, 0])
        for r in rows:
            k = (r["paradigm"], r["workload"], r["concurrency"])
            agg[k][0] += 1
            if r["status"] == "ok":
                agg[k][1] += 1
            else:
                i = {"provisioning": 2, "timeout": 3, "tool_exit": 4}.get(r["stage"])
                if i:
                    agg[k][i] += 1
        for k in sorted(agg):
            w.writerow(list(k) + agg[k])

    # LaTeX: paradigm x concurrency attempts/accepted with execution failures
    paras = ["block", "file", "object"]
    cs = [1, 4, 16, 64]
    lines = [r"\begin{tabular}{lcccc}", r"\toprule",
             r"Paradigm & c=1 & c=4 & c=16 & c=64 \\", r"\midrule"]
    for p in paras:
        cells = []
        for c in cs:
            a, o = cell[(p, c)]
            cells.append(f"{a}\\,/\\,{o}")
        lines.append(p.capitalize() + " & " + " & ".join(cells) + r" \\")
    lines += [r"\midrule",
              "Object execution failures & " + " & ".join(
                  str(exec_fail[("object", c)]) for c in cs) + r" \\",
              r"\bottomrule", r"\end{tabular}"]
    (OUT / "table_completion.tex").write_text("\n".join(lines) + "\n", newline="\n")

    macros = {
        "attTotal": total, "attAccepted": ok, "attFailed": len(fails),
        "attProvisioning": stages["provisioning"], "attTimeout": stages["timeout"],
        "attToolExit": stages["tool_exit"],
        "objExecFailCone": exec_fail[("object", 1)],
        "objExecFailCfour": exec_fail[("object", 4)],
        "objExecFailCsixteen": exec_fail[("object", 16)],
        "objExecFailCsixtyfour": exec_fail[("object", 64)],
    }
    return macros


def ols(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0 or n < 3:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    dof = n - 2
    s2 = sum(r * r for r in resid) / dof if dof > 0 else float("nan")
    se = math.sqrt(s2 / sxx) if dof > 0 else float("nan")
    # t 97.5% quantiles for small dof
    T = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
         7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    t = T.get(dof, 2.0)
    return b, b - t * se, b + t * se, n


def sizing_strata():
    runs = list(csv.DictReader(open(OUT / "runs_recomputed.csv")))
    out_rows = []
    strata = {"fixed": [], "weak": []}
    for r in runs:
        ds = r["dataset_gb_executed"]
        if not ds:
            continue
        ds = float(ds)
        c = int(r["concurrency"])
        wl = r["workload"]
        exp_weak = min(80.0, max(1.0, round(BASE[wl] * c / 16)))
        in_fixed = abs(ds - BASE[wl]) < TOL
        in_weak = abs(ds - exp_weak) < TOL
        if in_fixed:
            strata["fixed"].append(r)
        if in_weak:
            strata["weak"].append(r)

    ops = [("write", "write_tput_mib_s"), ("read", "read_tput_mib_s")]
    for stratum, rows in strata.items():
        groups = defaultdict(list)
        for r in rows:
            groups[(r["provider"], r["paradigm"], r["workload"])].append(r)
        for key, rs in sorted(groups.items()):
            for op, col in ops:
                pts = [(math.log10(int(r["concurrency"])),
                        math.log10(float(r[col])))
                       for r in rs if r[col]]
                levels = len({p[0] for p in pts})
                if levels < 3:
                    continue
                fit = ols([p[0] for p in pts], [p[1] for p in pts])
                if fit is None:
                    continue
                b, lo, hi, n = fit
                out_rows.append({"stratum": stratum, "provider": key[0],
                                 "paradigm": key[1], "workload": key[2],
                                 "operation": op, "beta": round(b, 3),
                                 "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
                                 "n_runs": n, "n_levels": levels})
    with open(OUT / "sensitivity_sizing.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    return out_rows


def sizing_table(rows):
    """Compact LaTeX: object+block balanced betas per provider, both strata."""
    idx = {(r["stratum"], r["provider"], r["paradigm"], r["workload"],
            r["operation"]): r for r in rows}
    provs = ["aws", "azure", "gcp", "huawei", "alibaba"]
    names = {"aws": "AWS", "azure": "Azure", "gcp": "GCP",
             "huawei": "Huawei", "alibaba": "Alibaba"}
    lines = [r"\begin{tabular}{llcccc}", r"\toprule",
             r"Paradigm & Provider & \multicolumn{2}{c}{Fixed-total stratum} & "
             r"\multicolumn{2}{c}{Weak-scaled stratum} \\",
             r" & & write $\beta$ & read $\beta$ & write $\beta$ & read $\beta$ \\",
             r"\midrule"]
    for para in ["object", "block", "file"]:
        for p in provs:
            cells = []
            for st in ["fixed", "weak"]:
                for op in ["write", "read"]:
                    r = idx.get((st, p, para, "balanced", op))
                    cells.append(f"{r['beta']:.2f}" if r else "--")
            if all(c == "--" for c in cells):
                continue
            lines.append(f"{para.capitalize()} & {names[p]} & " +
                         " & ".join(cells) + r" \\")
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines.append(r"\end{tabular}")
    (OUT / "table_sizing.tex").write_text("\n".join(lines) + "\n", newline="\n")


def prose_macros(sens):
    """Stratum-vs-pooled comparison macros quoted in the manuscript prose."""
    full = {(r["provider"], r["paradigm"], r["workload"], r["operation"]):
            float(r["beta"])
            for r in csv.DictReader(open(OUT / "exponents_recomputed.csv"))
            if r.get("beta")}
    max_shift, max_key = 0.0, None
    for r in sens:
        k = (r["provider"], r["paradigm"], r["workload"], r["operation"])
        if k in full:
            d = abs(float(r["beta"]) - full[k])
            if d > max_shift:
                max_shift, max_key = d, (r["stratum"],) + k
    idx = {(r["stratum"], r["provider"], r["paradigm"], r["workload"],
            r["operation"]): float(r["beta"]) for r in sens}
    return {
        "sizeMaxShift": f"{max_shift:.2f}",
        "sizeMaxShiftCell": " ".join(max_key) if max_key else "",
        "huaweiObjFixedWrite":
            f"{idx.get(('fixed','huawei','object','balanced','write'), float('nan')):.2f}",
        "huaweiObjFixedRead":
            f"{idx.get(('fixed','huawei','object','balanced','read'), float('nan')):.2f}",
    }


def main():
    rows = load_attempts()
    macros = completion_tables(rows)
    sens = sizing_strata()
    sizing_table(sens)
    macros.update(prose_macros(sens))
    with open(OUT / "sensitivity_macros.tex", "w", newline="\n") as f:
        for k, v in macros.items():
            f.write("\\newcommand{\\%s}{%s}\n" % (k, v))
    print(f"attempts={macros['attTotal']} accepted={macros['attAccepted']} "
          f"failed={macros['attFailed']} "
          f"(prov={macros['attProvisioning']} timeout={macros['attTimeout']} "
          f"tool={macros['attToolExit']})")
    print("object exec failures by c:",
          [macros[k] for k in ("objExecFailCone", "objExecFailCfour",
                               "objExecFailCsixteen", "objExecFailCsixtyfour")])
    print(f"sizing rows: {len(sens)}")


if __name__ == "__main__":
    main()
