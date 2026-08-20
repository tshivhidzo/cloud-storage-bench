#!/usr/bin/env python3
"""
network_probe.py -- record the network context that the thesis references:
per-endpoint latency (ping RTT), hop count (traceroute), a local-vs-offshore
classification, plus the testing machine's line speed. Archive the JSON with the
dataset. Missing tools are recorded, not faked.
"""
from __future__ import annotations
import argparse, csv, json, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path


def ping_rtt(host, count=10):
    if not shutil.which("ping"):
        return None
    try:
        cp = subprocess.run(["ping", "-c", str(count), host],
                            capture_output=True, text=True, timeout=60)
        m = re.search(r"=\s*[\d.]+/([\d.]+)/", cp.stdout)  # min/avg/max
        return float(m.group(1)) if m else None
    except Exception:
        return None


def hops(host):
    tr = "traceroute" if shutil.which("traceroute") else None
    if not tr:
        return None
    try:
        cp = subprocess.run([tr, "-m", "30", host], capture_output=True,
                            text=True, timeout=120)
        return sum(1 for ln in cp.stdout.splitlines() if re.match(r"\s*\d+\s", ln))
    except Exception:
        return None


def line_speed():
    """Approx down/up Mbps if speedtest-cli is present; else None."""
    if not shutil.which("speedtest-cli"):
        return None
    try:
        cp = subprocess.run(["speedtest-cli", "--json"], capture_output=True,
                            text=True, timeout=120)
        d = json.loads(cp.stdout)
        return {"download_mbps": round(d.get("download", 0) / 1e6, 1),
                "upload_mbps": round(d.get("upload", 0) / 1e6, 1)}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True,
                    help="CSV with columns: name,host,region,locality")
    ap.add_argument("--out", default="results/network_probe.json")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.targets)))
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "line_speed": line_speed(), "endpoints": []}
    for r in rows:
        host = r.get("host", "").strip()
        rtt = ping_rtt(host) if host else None
        out["endpoints"].append({
            "name": r.get("name"), "host": host, "region": r.get("region"),
            "locality": r.get("locality"),  # 'local' or 'offshore', from the CSV
            "rtt_ms_avg": rtt, "hops": hops(host) if host else None})
        print(f"{r.get('name'):20} rtt={rtt} host={host}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
