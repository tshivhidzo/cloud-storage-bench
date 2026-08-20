#!/usr/bin/env python3
"""
add_costs.py -- attach NORMALISED cost columns to all_runs.csv from your REAL
billing export. It does not price anything itself; it joins your exported costs
(provider x paradigm x region) onto each run and normalises to USD per basis-GB
per month. Cells with no matching billing row are left blank and flagged -- costs
are never invented, matching the harness integrity rules.

Cost file (--costs) expected columns (a normalised FOCUS-style export):
    provider,paradigm,region,capacity_usd_per_gb_month,egress_usd_per_gb
"""
from __future__ import annotations
import argparse, csv, sys
from pathlib import Path

NEW_COLS = ["capacity_cost_usd_per_basis", "egress_cost_usd_per_basis",
            "total_cost_usd_per_basis", "cost_basis_gb"]


def load_costs(path):
    table = {}
    for r in csv.DictReader(open(path)):
        key = (r["provider"].strip().lower(), r["paradigm"].strip().lower(),
               r.get("region", "").strip())
        table[key] = r
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="./results")
    ap.add_argument("--costs", default="results/focus_costs.csv",
                    help="your real normalised billing export")
    ap.add_argument("--basis-gb", type=float, default=100.0)
    ap.add_argument("--egress-gb", type=float, default=0.0,
                    help="assumed monthly egress in GB for the egress line (0=none)")
    a = ap.parse_args()
    src = Path(a.outdir) / "all_runs.csv"
    if not src.exists():
        sys.exit(f"no {src}; run parse_results.py first")
    if not Path(a.costs).exists():
        sys.exit(f"no billing export at {a.costs}. Export your real costs first; "
                 "costs are never invented.")
    costs = load_costs(a.costs)
    rows = list(csv.DictReader(open(src)))
    fields = list(rows[0].keys()) if rows else []
    for c in NEW_COLS:
        if c not in fields:
            fields.append(c)
    notes, matched = [], 0
    for row in rows:
        for c in NEW_COLS:
            row.setdefault(c, "")
        key = (row["provider"].lower(), row["paradigm"].lower(), row["region"])
        rec = costs.get(key) or costs.get((key[0], key[1], ""))
        if not rec:
            notes.append(f"{row['run_id']}: no billing row for {key} -> cost blank")
            continue
        try:
            cap = float(rec["capacity_usd_per_gb_month"]) * a.basis_gb
            row["capacity_cost_usd_per_basis"] = round(cap, 4)
            eg_rate = (rec.get("egress_usd_per_gb") or "").strip()
            if eg_rate:  # blank = no billed egress rate; capacity-only total
                egress = float(eg_rate) * a.egress_gb
                row["egress_cost_usd_per_basis"] = round(egress, 4)
                row["total_cost_usd_per_basis"] = round(cap + egress, 4)
            else:
                row["egress_cost_usd_per_basis"] = ""
                row["total_cost_usd_per_basis"] = round(cap, 4)
            row["cost_basis_gb"] = a.basis_gb
            matched += 1
        except (ValueError, KeyError) as e:
            notes.append(f"{row['run_id']}: bad cost row ({e}) -> blank")
    with open(src, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    with open(Path(a.outdir) / "cost_notes.txt", "w") as f:
        f.write("\n".join(notes) + ("\n" if notes else ""))
    print(f"Attached costs to {matched}/{len(rows)} rows (basis {a.basis_gb} GB). "
          f"Unmatched left blank. Notes: {Path(a.outdir)/'cost_notes.txt'}")


if __name__ == "__main__":
    main()
