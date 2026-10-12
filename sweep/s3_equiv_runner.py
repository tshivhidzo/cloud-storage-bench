#!/usr/bin/env python3
"""
s3_equiv_runner.py -- S3 port of azure_blob_runner_v2.py for the v2.1
equivalence test (SWEEP_PROTOCOL_V2_1_AMENDMENT.md, section F).

Everything that defines the measurement is kept identical to the Azure runner:
bounded process pool (<= 16) with threads inside each process, independent
worker loops until a shared deadline, duration-driven phases (balanced = write
pass then read pass, duration/2 each), 64 KiB objects reused by name modulo
256 per thread, streaming reads, per-thread latency reservoir, and the same
csv row schema. The only substitution is the client library: boto3 against an
S3-compatible endpoint instead of the Azure Blob SDK. The reservoir size is a
command-line argument so its effect on p99 can be measured.

Credentials and endpoint come from S3_ENDPOINT / S3_REGION and, when set,
S3_ACCESS_KEY / S3_SECRET_KEY / S3_SESSION_TOKEN; otherwise boto3's default
chain (e.g. the EC2 instance role) is used.
"""
from __future__ import annotations
import argparse, csv, os, random, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor

OBJ_SIZE = {"read": 64 << 10, "write": 64 << 10, "balanced": 64 << 10,
            "metadata": 4 << 10, "largeobj": 16 << 20}
MAX_PROCS = 16  # identical to azure_blob_runner_v2


def make_client(max_pool):
    import boto3
    from botocore.config import Config
    kw = {}
    if os.environ.get("S3_ENDPOINT"):
        kw["endpoint_url"] = os.environ["S3_ENDPOINT"]
    if os.environ.get("S3_REGION"):
        kw["region_name"] = os.environ["S3_REGION"]
    if os.environ.get("S3_ACCESS_KEY") and os.environ.get("S3_SECRET_KEY"):
        kw["aws_access_key_id"] = os.environ["S3_ACCESS_KEY"]
        kw["aws_secret_access_key"] = os.environ["S3_SECRET_KEY"]
        if os.environ.get("S3_SESSION_TOKEN"):
            kw["aws_session_token"] = os.environ["S3_SESSION_TOKEN"]
    # socket timeouts as in the Azure runner; pool sized to the thread count
    cfg = Config(connect_timeout=20, read_timeout=60,
                 max_pool_connections=max(10, max_pool + 2),
                 s3={"addressing_style": "virtual"
                     if os.environ.get("S3_VIRT_ADDR") == "1" else "auto"})
    return boto3.client("s3", config=cfg, **kw)


def worker(args):
    wid, n_threads, bucket, size, op, deadline, lat_cap = args
    from concurrent.futures import ThreadPoolExecutor
    s3 = make_client(n_threads)
    payload = os.urandom(size) if op == "write" else None

    def loop(tid):
        ops, moved, lats, i = 0, 0, [], 0
        while time.time() < deadline:
            key = f"w{wid}t{tid}-obj-{i % 256}"
            t = time.time()
            try:
                if op == "write":
                    s3.put_object(Bucket=bucket, Key=key, Body=payload)
                else:
                    body = s3.get_object(Bucket=bucket, Key=key)["Body"]
                    for _ in body.iter_chunks(chunk_size=1 << 20):
                        pass
            except Exception:
                i += 1
                continue
            dt = (time.time() - t) * 1000
            if len(lats) < lat_cap:
                lats.append(dt)
            else:
                j = random.randint(0, ops)
                if j < lat_cap:
                    lats[j] = dt
            ops += 1; moved += size; i += 1
        return ops, moved, lats

    with ThreadPoolExecutor(max_workers=n_threads) as tx:
        parts = list(tx.map(loop, range(n_threads)))
    return (sum(p[0] for p in parts), sum(p[1] for p in parts),
            [l for p in parts for l in p[2]])


def run_phase(bucket, size, op, concurrency, duration, lat_cap):
    deadline = time.time() + duration
    n_procs = min(concurrency, MAX_PROCS)
    base, extra = divmod(concurrency, n_procs)
    args = [(w, base + (1 if w < extra else 0), bucket, size, op, deadline, lat_cap)
            for w in range(n_procs)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=n_procs) as ex:
        results = list(ex.map(worker, args))
    elapsed = max(time.time() - t0, 1e-6)
    return (sum(r[0] for r in results), sum(r[1] for r in results),
            sorted(l for r in results for l in r[2]), elapsed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", required=True)
    ap.add_argument("--concurrency", type=int, required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--csvfile", required=True)
    ap.add_argument("--lat-cap", type=int, default=10_000)
    a = ap.parse_args()
    size = OBJ_SIZE[a.workload]
    if a.workload == "balanced":
        phases = [("write", a.duration // 2), ("read", a.duration // 2)]
    elif a.workload in ("write", "metadata"):
        phases = [("write", a.duration // 2)]
    else:
        run_phase(a.bucket, size, "write", a.concurrency,
                  max(60, a.duration // 4), a.lat_cap)
        phases = [("read", a.duration // 2)]
    rows = []
    for op, dur in phases:
        ops, moved, lats, elapsed = run_phase(a.bucket, size, op,
                                              a.concurrency, dur, a.lat_cap)
        if not lats:
            sys.exit(f"no successful S3 {op} operations -> nothing written")
        rows.append({"operation": op,
                     "throughput_mb_s": round(moved / elapsed / 1e6, 2),
                     "iops": round(ops / elapsed, 1),
                     "lat_mean_ms": round(statistics.mean(lats), 3),
                     "lat_p95_ms": round(lats[int(0.95 * len(lats)) - 1], 3),
                     "lat_p99_ms": round(lats[int(0.99 * len(lats)) - 1], 3),
                     "lat_samples": len(lats), "lat_cap": a.lat_cap})
    with open(a.csvfile, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"s3_equiv_runner: {r['operation']} {r['throughput_mb_s']} MB/s "
              f"{r['iops']} ops/s p99={r['lat_p99_ms']} ms "
              f"(samples={r['lat_samples']}, cap={r['lat_cap']})")


if __name__ == "__main__":
    main()
