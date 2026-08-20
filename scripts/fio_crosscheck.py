#!/usr/bin/env python3
"""
fio_crosscheck.py -- independent cross-check of elbencho against the field-
standard tool FIO on a sample block run. Runs FIO, extracts its throughput/IOPS/
latency from JSON, and reports the percentage difference vs the elbencho values
you pass in (take them from all_runs.csv for that cell). A close match is your
evidence that the unified tool is sound. Prints a table; stores nothing invented.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys


def run_fio(mount, workload, concurrency, size_gb=4, runtime=120):
    if not shutil.which("fio"):
        sys.exit("fio not installed: sudo apt install -y fio")
    rw = {"read": "read", "write": "write", "balanced": "rw"}.get(workload, "read")
    cmd = ["fio", f"--name=crosscheck", f"--directory={mount}", "--direct=1",
           f"--rw={rw}", "--bs=64k", f"--numjobs={concurrency}",
           f"--size={size_gb}G", f"--runtime={runtime}", "--time_based",
           "--group_reporting", "--output-format=json"]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit(f"fio failed:\n{cp.stderr[-1000:]}")
    d = json.loads(cp.stdout)
    j = d["jobs"][0]
    side = "read" if rw != "write" else "write"
    s = j[side]
    return {"throughput_mbps": s["bw"] / 1024.0,      # KiB/s -> MiB/s
            "iops": s["iops"],
            "lat_mean_ms": s["lat_ns"]["mean"] / 1e6}


def pct(a, b):
    return None if not b else round(100 * (a - b) / b, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mount", required=True)
    ap.add_argument("--workload", default="read")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--elbencho-tput", type=float, required=True)
    ap.add_argument("--elbencho-iops", type=float, required=True)
    ap.add_argument("--elbencho-lat", type=float, required=True)
    a = ap.parse_args()
    fio = run_fio(a.mount, a.workload, a.concurrency)
    print(f"{'metric':12} {'elbencho':>12} {'fio':>12} {'diff %':>8}")
    for name, e, f in (("throughput", a.elbencho_tput, fio["throughput_mbps"]),
                       ("iops", a.elbencho_iops, fio["iops"]),
                       ("lat_mean_ms", a.elbencho_lat, fio["lat_mean_ms"])):
        print(f"{name:12} {e:>12.2f} {f:>12.2f} {str(pct(e,f)):>8}")
    print("\nA small percentage difference (single digits) supports the unified "
          "elbencho results. A large gap means investigate before trusting them.")


if __name__ == "__main__":
    main()
