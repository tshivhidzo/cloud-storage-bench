#!/usr/bin/env python3
"""
purge_s3.py -- empty benchmark buckets quickly, in parallel, over the S3 API.

Why: object runs leave up to 2.6 million 64 KiB objects in a bucket (5.2
million for a two-client run). Terraform's force_destroy deletes them slowly
or, on Alibaba OSS, fails with BucketNotEmpty and blocks every later
provision (90 of 92 Alibaba provisioning failures in August 2026). Emptying
the bucket first makes teardown fast and reliable.

    python3 purge_s3.py --bucket csb-bench-abc12345   # one known bucket
    python3 purge_s3.py --prefix csb-bench-           # every matching bucket
                                                      # the credentials can list
Endpoint and credentials come from the same S3_* variables elbencho uses.
Best-effort by design: it never raises, and the orchestrator never fails a
run because of it. Deletes only buckets whose name starts with csb-bench.
"""
from __future__ import annotations
import argparse, os, sys, time
from concurrent.futures import ThreadPoolExecutor

SAFE_PREFIX = "csb-bench"


def client():
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
    cfg = Config(max_pool_connections=40, retries={"max_attempts": 5},
                 s3={"addressing_style": "virtual"
                     if os.environ.get("S3_VIRT_ADDR") == "1" else "auto"})
    return boto3.client("s3", config=cfg, **kw)


def empty_bucket(s3, bucket, workers=32):
    if not bucket.startswith(SAFE_PREFIX):
        print(f"purge: refusing to touch {bucket!r} (not a {SAFE_PREFIX} bucket)")
        return 0
    t0, deleted = time.time(), 0

    def delete_batch(keys):
        try:
            s3.delete_objects(Bucket=bucket, Delete={
                "Objects": [{"Key": k} for k in keys], "Quiet": True})
            return len(keys)
        except Exception as e:
            print(f"purge: batch failed on {bucket}: {e}")
            return 0

    paginator = s3.get_paginator("list_objects_v2")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for page in paginator.paginate(Bucket=bucket, PaginationConfig={"PageSize": 1000}):
            keys = [o["Key"] for o in page.get("Contents", [])]
            if keys:
                futures.append(ex.submit(delete_batch, keys))
        deleted = sum(f.result() for f in futures)
    try:   # unfinished multipart uploads also block bucket deletion
        for up in s3.list_multipart_uploads(Bucket=bucket).get("Uploads", []):
            s3.abort_multipart_upload(Bucket=bucket, Key=up["Key"],
                                      UploadId=up["UploadId"])
    except Exception:
        pass
    print(f"purge: {bucket}: {deleted} objects deleted in {time.time() - t0:.0f} s")
    return deleted


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bucket")
    g.add_argument("--prefix")
    a = ap.parse_args()
    try:
        s3 = client()
        if a.bucket:
            empty_bucket(s3, a.bucket)
        else:
            for b in s3.list_buckets().get("Buckets", []):
                if b["Name"].startswith(a.prefix) and b["Name"].startswith(SAFE_PREFIX):
                    empty_bucket(s3, b["Name"])
    except Exception as e:
        print(f"purge: skipped ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
