#!/usr/bin/env python3
"""
export_aws_costs.py -- derive the normalised focus_costs.csv rows for AWS from
your REAL bill via the Cost Explorer API. Nothing is priced from a rate card:
each rate is UnblendedCost / UsageQuantity actually billed in the window.

Mapping (af-south-1 usage types):
  block  : EBS  "...EBS:VolumeUsage..."      (GB-month)
  file   : EFS  "...TimedStorage..." (EFS)   (GB-month)
  object : S3   "...TimedStorage-ByteHrs"    (GB-month)
  egress : "...DataTransfer-Out-Bytes"       (GB)

Run from the laptop (where the AWS CLI is authenticated), AFTER billing data
for the campaign window has landed (usually ~24h behind):
  python3 scripts/export_aws_costs.py --start 2026-07-30 --end 2026-08-03 \
      --region af-south-1 --out results/focus_costs.csv
Note: each Cost Explorer API request costs $0.01.
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys
from collections import defaultdict
from pathlib import Path


def ce_query(start, end, region):
    cmd = ["aws", "ce", "get-cost-and-usage",
           "--time-period", f"Start={start},End={end}",
           "--granularity", "DAILY",
           "--metrics", "UnblendedCost", "UsageQuantity",
           "--group-by", "Type=DIMENSION,Key=SERVICE",
           "Type=DIMENSION,Key=USAGE_TYPE",
           "--filter", json.dumps({"Dimensions": {"Key": "REGION",
                                                  "Values": [region]}}),
           "--output", "json"]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit(f"cost explorer query failed:\n{cp.stderr}")
    return json.loads(cp.stdout)


def classify(keys):
    """keys = [SERVICE, USAGE_TYPE]. S3 and EFS BOTH bill capacity under
    'TimedStorage-ByteHrs', so the service dimension is what disambiguates."""
    service = keys[0].lower()
    ut = keys[1].lower()
    if "datatransfer-out-bytes" in ut:
        return "egress"
    if "ebs:volumeusage" in ut:
        return "block"
    if "timedstorage" in ut:
        if "simple storage service" in service:
            return "object"      # S3 capacity
        if "elastic file system" in service:
            return "file"        # EFS capacity
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (exclusive)")
    ap.add_argument("--region", default="af-south-1")
    ap.add_argument("--out", default="results/focus_costs.csv")
    a = ap.parse_args()

    data = ce_query(a.start, a.end, a.region)
    cost = defaultdict(float)
    qty = defaultdict(float)
    seen = defaultdict(set)
    for day in data.get("ResultsByTime", []):
        for g in day.get("Groups", []):
            keys = g["Keys"]
            cat = classify(keys)
            if not cat:
                continue
            cost[cat] += float(g["Metrics"]["UnblendedCost"]["Amount"])
            qty[cat] += float(g["Metrics"]["UsageQuantity"]["Amount"])
            seen[cat].add(" / ".join(keys))

    def rate(cat):
        if qty.get(cat, 0) > 0:
            return f"{cost[cat] / qty[cat]:.6f}"
        return ""  # no billed usage -> honest blank, never invented

    egress_rate = rate("egress")
    rows = []
    for paradigm in ("block", "file", "object"):
        r = rate(paradigm)
        rows.append({"provider": "aws", "paradigm": paradigm,
                     "region": a.region,
                     "capacity_usd_per_gb_month": r,
                     "egress_usd_per_gb": egress_rate})
        src = ", ".join(sorted(seen.get(paradigm, []))) or "NO BILLED USAGE FOUND"
        print(f"aws/{paradigm}: capacity={r or 'BLANK'} USD/GB-month  "
              f"(cost ${cost.get(paradigm, 0):.4f} / {qty.get(paradigm, 0):.4f} GB-mo)"
              f"  from: {src}")
    print(f"egress: {egress_rate or 'BLANK'} USD/GB  "
          f"(cost ${cost.get('egress', 0):.4f} / {qty.get('egress', 0):.4f} GB)")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if out.exists():  # keep rows for other providers, replace aws ones
        existing = [r for r in csv.DictReader(open(out))
                    if r["provider"].strip().lower() != "aws"
                    and not r["provider"].strip().startswith("#")]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["provider", "paradigm", "region",
                                          "capacity_usd_per_gb_month",
                                          "egress_usd_per_gb"])
        w.writeheader()
        w.writerows(rows + existing)
    print(f"\nWrote {out} ({len(rows)} aws rows; other providers preserved). "
          f"Next: python3 scripts/add_costs.py --outdir ./results")


if __name__ == "__main__":
    main()
