#!/usr/bin/env python3
"""status.py -- where does the campaign stand? Latest status per run_id,
counts, and per-paradigm breakdown. Read-only; safe to run mid-campaign."""
import json
import sys
from collections import Counter
from pathlib import Path

manifest = Path(sys.argv[1] if len(sys.argv) > 1 else "results/run_manifest.jsonl")
if not manifest.exists():
    sys.exit(f"no manifest at {manifest}")

latest = {}
for line in manifest.read_text().splitlines():
    try:
        r = json.loads(line)
        latest[r["run_id"]] = r
    except json.JSONDecodeError:
        pass  # partial line from an interrupted write

ok = sorted(k for k, r in latest.items() if r.get("status") == "ok")
bad = sorted(k for k, r in latest.items() if r.get("status") != "ok")
print(f"{len(ok)} ok, {len(bad)} not-ok, {len(latest)} attempted\n")

para = Counter()
for k, r in latest.items():
    para[(r.get("paradigm", "?"), r.get("status"))] += 1
for p in ("block", "file", "object"):
    o = para.get((p, "ok"), 0)
    f = sum(v for (pp, s), v in para.items() if pp == p and s != "ok")
    print(f"  {p:7} ok={o:3}  not-ok={f}")

if bad:
    print("\nnot-ok runs (latest attempt):")
    for k in bad:
        print(f"  {k:36} {latest[k].get('status')}  {latest[k].get('error', '')[:60]}")
