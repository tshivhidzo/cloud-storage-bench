#!/usr/bin/env python3
"""
azure_blob_runner.py -- object-storage runner for Azure Blob (the one non-S3
service), emitting the SAME csv fields elbencho does so parse_results.py stays
uniform. Uses the azure-storage-blob SDK. Reports throughput (MB/s), IOPS
(objects/s) and per-operation latency percentiles. Never fabricates: if the SDK
or credentials are missing it exits non-zero and writes nothing.
"""
from __future__ import annotations
import argparse, csv, os, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    sys.exit("azure-storage-blob not installed: pip install azure-storage-blob")

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", required=True)
    ap.add_argument("--concurrency", type=int, required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--csvfile", required=True)
    a = ap.parse_args()

    svc = BlobServiceClient.from_connection_string(conn_str())
    cont = svc.get_container_client(a.container)
    try:
        cont.create_container()
    except Exception:
        pass
    size = OBJ_SIZE[a.workload]
    payload = os.urandom(size)
    is_write = a.workload in ("write", "balanced", "metadata")
    latencies, ops, deadline = [], 0, time.time() + a.duration
    bytes_moved = 0

    # seed objects for read workloads
    if not is_write:
        for i in range(max(a.concurrency, 16)):
            cont.upload_blob(f"seed-{i}", payload, overwrite=True)

    def one(i):
        nonlocal bytes_moved
        name = f"obj-{i % 1024}"
        t = time.time()
        if is_write:
            cont.upload_blob(name, payload, overwrite=True)
        else:
            cont.download_blob(f"seed-{i % max(a.concurrency,16)}").readall()
        dt = (time.time() - t) * 1000
        return dt, size

    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        i = 0
        while time.time() < deadline:
            futs = [ex.submit(one, i + k) for k in range(a.concurrency)]
            i += a.concurrency
            for f in futs:
                try:
                    dt, nb = f.result()
                    latencies.append(dt); ops += 1; bytes_moved += nb
                except Exception:
                    pass

    if not latencies:
        sys.exit("no successful Azure Blob operations -> writing nothing (honest)")
    elapsed = a.duration
    tput = bytes_moved / elapsed / 1e6           # MB/s
    iops = ops / elapsed
    latencies.sort()
    op = "write" if is_write else "read"
    row = {"operation": op, "throughput_mb_s": round(tput, 2),
           "iops": round(iops, 1),
           "lat_mean_ms": round(statistics.mean(latencies), 3),
           "lat_p95_ms": round(latencies[int(0.95 * len(latencies)) - 1], 3),
           "lat_p99_ms": round(latencies[int(0.99 * len(latencies)) - 1], 3)}
    with open(a.csvfile, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader(); w.writerow(row)
    print(f"azure_blob_runner: {op} {tput:.1f} MB/s {iops:.0f} ops/s -> {a.csvfile}")


if __name__ == "__main__":
    main()
