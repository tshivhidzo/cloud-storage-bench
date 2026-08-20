#!/usr/bin/env python3
"""
export_azure_costs.py -- derive normalised focus_costs.csv rows for Azure from
your REAL bill via `az consumption usage list`. Each rate is billed cost /
billed GB-month actually consumed; nothing comes from a rate card.

Meter mapping (Storage service):
  block  : meters containing 'Disk'  (Managed Disks)
  file   : meters containing 'File'  (Azure Files)
  object : meters containing 'Blob'  (Blob Storage)

Run from the laptop (az CLI authenticated), AFTER billing has landed
(Azure lags 24-48h):
  python3 scripts/export_azure_costs.py --start 2026-08-01 --end 2026-08-05 \
      --region southafricanorth --out results-azure/focus_costs.csv
"""
from __future__ import annotations
import argparse, csv, json, shutil, subprocess, sys
from collections import defaultdict
from pathlib import Path


def az_usage(start, end):
    az = shutil.which("az") or shutil.which("az.cmd") or "az"
    cmd = [az, "consumption", "usage", "list",
           "--start-date", start, "--end-date", end, "-o", "json"]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit(f"az consumption query failed:\n{cp.stderr}")
    return json.loads(cp.stdout)


def classify(row):
    cat = (row.get("meterCategory") or "").lower()
    name = (row.get("meterName") or "").lower()
    sub = (row.get("meterSubCategory") or "").lower()
    if "storage" not in cat and "disk" not in cat:
        return None
    hay = f"{name} {sub}"
    if "disk" in hay:
        return "block"
    if "file" in hay:
        return "file"
    if "blob" in hay or "data stored" in hay:
        return "object"
    return None


def is_capacity_meter(row):
    unit = (row.get("unitOfMeasure") or row.get("unit") or "").lower()
    return "gb" in unit and ("month" in unit or "/ month" in unit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--region", default="southafricanorth")
    ap.add_argument("--out", default="results-azure/focus_costs.csv")
    a = ap.parse_args()

    rows = az_usage(a.start, a.end)
    cost = defaultdict(float)
    qty = defaultdict(float)
    seen = defaultdict(set)
    for r in rows:
        cat = classify(r)
        if not cat or not is_capacity_meter(r):
            continue
        cost[cat] += float(r.get("pretaxCost") or r.get("cost") or 0)
        qty[cat] += float(r.get("quantity") or 0)
        seen[cat].add(r.get("meterName") or "?")

    def rate(cat):
        return f"{cost[cat] / qty[cat]:.6f}" if qty.get(cat, 0) > 0 else ""

    out_rows = []
    for paradigm in ("block", "file", "object"):
        r = rate(paradigm)
        out_rows.append({"provider": "azure", "paradigm": paradigm,
                         "region": a.region,
                         "capacity_usd_per_gb_month": r,
                         "egress_usd_per_gb": ""})  # in-region: no billed egress
        src = ", ".join(sorted(seen.get(paradigm, []))) or "NO BILLED USAGE FOUND"
        print(f"azure/{paradigm}: capacity={r or 'BLANK'} USD/GB-month  "
              f"(cost ${cost.get(paradigm, 0):.4f} / {qty.get(paradigm, 0):.4f} GB-mo)  from: {src}")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if out.exists():
        existing = [r for r in csv.DictReader(open(out))
                    if r["provider"].strip().lower() != "azure"
                    and not r["provider"].strip().startswith("#")]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "paradigm", "region",
                                          "capacity_usd_per_gb_month",
                                          "egress_usd_per_gb"])
        w.writeheader()
        w.writerows(out_rows + existing)
    print(f"\nWrote {out}. Next: python3 scripts/add_costs.py "
          f"--outdir ./results-azure --costs {out}")


if __name__ == "__main__":
    main()
