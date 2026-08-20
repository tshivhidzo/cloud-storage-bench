#!/usr/bin/env python3
"""
azure_blob_runner_v2.py -- corrected Azure Blob runner for the sweep campaign.

Fixes three defects found in v1 (scripts/azure_blob_runner.py) that made its
throughput an artifact of the runner rather than of Azure Blob:
  1. v1 submitted work in synchronised batches (each batch as slow as its
     slowest op). v2 workers run independently until the deadline.
  2. v1 used threads (Python GIL serialises TLS/HTTP CPU work; throughput
     FELL at high thread counts). v2 uses processes.
  3. v1 mapped 'balanced' to pure writes. v2 runs a write phase then a read
     phase, mirroring elbencho's balanced template.

Emits the same csv schema (one row per phase) so parse_results.py is unchanged.
Deploy: copy over scripts/azure_blob_runner.py ON THE HOST (the archived v1
stays untouched in the repo; the instrument change is disclosed in the paper).
"""
from __future__ import annotations
import argparse, csv, os, random, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor

LAT_CAP = 10_000  # per-thread latency reservoir (memory + pickle bound)

OBJ_SIZE = {"read": 64 << 10, "write": 64 << 10, "balanced": 64 << 10,
            "metadata": 4 << 10, "largeobj": 16 << 20}


def conn_str():
    cs = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if cs:
        return cs
    acct = os.environ.get("AZURE_STORAGE_ACCOUNT")
    key = os.environ.get("AZURE_STORAGE_KEY")
    if not (acct and key):
        sys.exit("set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT+KEY")
    return (f"DefaultEndpointsProtocol=https;AccountName={acct};"
            f"AccountKey={key};EndpointSuffix=core.windows.net")


def worker(args):
    """One process running n_threads independent I/O loops until the deadline.
    Hybrid model: bounded process count (memory-safe on 16 GB hosts) with
    threads inside each; at <=4 threads/process the GIL cost is negligible
    for network-bound SDK calls. Returns (ops, bytes, latencies)."""
    wid, n_threads, container, size, op, deadline, cstr = args
    from concurrent.futures import ThreadPoolExecutor
    from azure.storage.blob import BlobServiceClient
    # socket timeouts: a dead connection must fail (and be retried/skipped),
    # never block forever -- blocked workers outlive their run and were found
    # squatting on 14 GB of host RAM, OOM-killing every subsequent run.
    cont = BlobServiceClient.from_connection_string(
        cstr, connection_timeout=20, read_timeout=60,
    ).get_container_client(container)
    payload = os.urandom(size) if op == "write" else None

    def loop(tid):
        ops, moved, lats, i = 0, 0, [], 0
        while time.time() < deadline:
            name = f"w{wid}t{tid}-obj-{i % 256}"
            t = time.time()
            try:
                if op == "write":
                    cont.upload_blob(name, payload, overwrite=True)
                else:
                    # stream chunks; never hold a whole object in RAM
                    for _ in cont.download_blob(name).chunks():
                        pass
            except Exception:
                i += 1
                continue
            dt = (time.time() - t) * 1000
            # reservoir sample: bounded memory/pickle cost, unbiased percentiles
            if len(lats) < LAT_CAP:
                lats.append(dt)
            else:
                j = random.randint(0, ops)
                if j < LAT_CAP:
                    lats[j] = dt
            ops += 1; moved += size; i += 1
        return ops, moved, lats

    with ThreadPoolExecutor(max_workers=n_threads) as tx:
        parts = list(tx.map(loop, range(n_threads)))
    return (sum(p[0] for p in parts), sum(p[1] for p in parts),
            [l for p in parts for l in p[2]])


MAX_PROCS = 16  # memory-safe on 4 vCPU / 16 GB; threads supply the rest

def run_phase(container, size, op, concurrency, duration, cstr):
    deadline = time.time() + duration
    n_procs = min(concurrency, MAX_PROCS)
    base, extra = divmod(concurrency, n_procs)
    args = [(w, base + (1 if w < extra else 0), container, size, op, deadline, cstr)
            for w in range(n_procs)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=n_procs) as ex:
        results = list(ex.map(worker, args))
    elapsed = max(time.time() - t0, 1e-6)
    ops = sum(r[0] for r in results)
    moved = sum(r[1] for r in results)
    lats = sorted(l for r in results for l in r[2])
    return ops, moved, lats, elapsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", required=True)
    ap.add_argument("--concurrency", type=int, required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--csvfile", required=True)
    a = ap.parse_args()
    cstr = conn_str()
    size = OBJ_SIZE[a.workload]

    # phase plan mirrors elbencho: balanced = write pass then read pass
    # (read pass reads the objects the write pass laid down, per worker).
    # Phase budget must fit the harness subprocess window (duration + 300 s):
    # measured phases get duration//2 each; prep gets duration//4 (unmeasured).
    if a.workload == "balanced":
        phases = [("write", a.duration // 2), ("read", a.duration // 2)]
    elif a.workload in ("write", "metadata"):
        phases = [("write", a.duration // 2)]
    else:  # read / largeobj: prep write pass (unmeasured), then measured read
        prep_dur = max(60, a.duration // 4)
        run_phase(a.container, size, "write", a.concurrency, prep_dur, cstr)
        phases = [("read", a.duration // 2)]

    rows = []
    for op, dur in phases:
        ops, moved, lats, elapsed = run_phase(a.container, size, op,
                                              a.concurrency, dur, cstr)
        if not lats:
            sys.exit(f"no successful Azure Blob {op} operations -> nothing written")
        rows.append({"operation": op,
                     "throughput_mb_s": round(moved / elapsed / 1e6, 2),
                     "iops": round(ops / elapsed, 1),
                     "lat_mean_ms": round(statistics.mean(lats), 3),
                     "lat_p95_ms": round(lats[int(0.95 * len(lats)) - 1], 3),
                     "lat_p99_ms": round(lats[int(0.99 * len(lats)) - 1], 3)})
    with open(a.csvfile, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"azure_blob_runner_v2: {r['operation']} {r['throughput_mb_s']} MB/s "
              f"{r['iops']} ops/s")


if __name__ == "__main__":
    main()
