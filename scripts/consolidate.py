#!/usr/bin/env python3
"""
consolidate.py -- merge per-provider all_runs.csv fragments into one dataset,
write results/manifest.sha256 (integrity over every raw artefact + the merged
csv), and results/completeness_report.txt stating how many of the 225 design
cells actually have data. This is the honesty gate: if coverage is below 225,
the thesis reports the real N and the gaps -- it does not assume 225.

Fragments are discovered at results/all_runs.csv and results/*/all_runs.csv.
"""
from __future__ import annotations
import argparse, csv, hashlib, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from design import (SCHEMA, PROVIDERS, PARADIGMS, WORKLOADS, REPS, FULL_GRID_N)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def has_metric(row):
    if row.get("workload") == "metadata":
        return str(row.get("metadata_ops_per_s", "")).strip() != ""
    return str(row.get("total_throughput_mbps", "")).strip() != ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="./results")
    a = ap.parse_args()
    outdir = Path(a.outdir)
    fragments = []
    if (outdir / "all_runs.csv").exists():
        fragments.append(outdir / "all_runs.csv")
    fragments += sorted(outdir.glob("*/all_runs.csv"))
    if not fragments:
        sys.exit(f"no all_runs.csv fragments under {outdir}")

    # One row per run_id. Fragments contain one row per ATTEMPT, so prefer the
    # attempt that carries a real metric over earlier failed (blank) attempts;
    # among rows with metrics, the last one wins (latest attempt).
    best, order = {}, []
    for frag in fragments:
        for row in csv.DictReader(open(frag)):
            rid = row.get("run_id", "")
            norm = {k: row.get(k, "") for k in
                    (SCHEMA + [c for c in row.keys() if c not in SCHEMA])}
            if rid not in best:
                best[rid] = norm
                order.append(rid)
            elif has_metric(norm) or not has_metric(best[rid]):
                best[rid] = norm
    merged = [best[r] for r in order]
    fields = SCHEMA + [c for c in merged[0].keys() if c not in SCHEMA] if merged else SCHEMA
    out_csv = outdir / "all_runs.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(merged)

    # completeness over the 225 factorial cells (concurrency 16 only)
    factorial = [r for r in merged if str(r.get("concurrency")) == "16"]
    filled = {r["run_id"] for r in factorial if has_metric(r)}
    by_prov = defaultdict(lambda: [0, 0])
    expected = set()
    for prov in PROVIDERS:
        for para in PARADIGMS:
            for wl in WORKLOADS:
                for rep in REPS:
                    rid = f"{prov}-{para}-{wl}-c16-r{rep}"
                    expected.add(rid)
                    by_prov[prov][1] += 1
                    if rid in filled:
                        by_prov[prov][0] += 1
    n_filled = len(filled & expected)

    lines = ["COMPLETENESS REPORT", "=" * 50,
             f"Full factorial design: {FULL_GRID_N} cells "
             f"(5 providers x 3 paradigms x 5 workloads x 3 reps, concurrency 16).",
             f"Cells with a real measured metric: {n_filled}/{FULL_GRID_N}.",
             f"Coverage: {100*n_filled/FULL_GRID_N:.1f}%.", "",
             "Per provider (filled / expected):"]
    for prov in PROVIDERS:
        got, exp = by_prov[prov]
        lines.append(f"  {prov:9} {got:3}/{exp}")
    missing = sorted(expected - filled)
    lines += ["", f"Missing cells: {len(missing)}"]
    lines += [f"  {m}" for m in missing[:60]]
    if len(missing) > 60:
        lines.append(f"  ... and {len(missing)-60} more")
    lines += ["", "REPORT THIS N. Do not claim 225 unless it says 225/225.",
              "Blank cells are honest gaps to be disclosed, not filled."]
    (outdir / "completeness_report.txt").write_text("\n".join(lines) + "\n")

    # manifest over merged csv + every raw artefact
    man = [f"{sha256(out_csv)}  {out_csv.name}"]
    raw = outdir / "raw"
    if raw.is_dir():
        for p in sorted(raw.rglob("*")):
            if p.is_file() and p.name != ".gitkeep":
                man.append(f"{sha256(p)}  raw/{p.relative_to(raw)}")
    (outdir / "manifest.sha256").write_text("\n".join(man) + "\n")

    print(f"Merged {len(merged)} rows from {len(fragments)} fragment(s).")
    print(f"Coverage: {n_filled}/{FULL_GRID_N} cells.")
    print(f"Wrote {out_csv}, completeness_report.txt, manifest.sha256")
    print("READ results/completeness_report.txt before writing Chapter 5.")


if __name__ == "__main__":
    main()
