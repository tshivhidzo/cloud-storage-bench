# F3. Object Storage Over the S3 API

Four of the five object services speak the S3 API. They differ in the details
that broke the campaign twice.

## Endpoint, region and addressing

| Provider | Endpoint | Addressing |
|---|---|---|
| AWS | `https://s3.af-south-1.amazonaws.com` | path or virtual-hosted |
| GCP | `https://storage.googleapis.com` (HMAC interoperability) | path |
| Huawei | `https://obs.af-south-1.myhuaweicloud.com` | virtual-hosted only |
| Alibaba | `https://oss-me-central-1-internal.aliyuncs.com` (internal) | virtual-hosted only |

Path style puts the bucket in the path (`https://endpoint/bucket/key`);
virtual-hosted style puts it in the host name (`https://bucket.endpoint/key`).
OSS refuses path style with `SecondLevelDomainForbidden`, which is why
elbencho needs `--s3virtaddr` there. The region is part of the request
signature, so it must match the endpoint.

Check that an "internal" endpoint really is internal before trusting it:

```bash
getent hosts oss-me-central-1-internal.aliyuncs.com     # a 100.x address
```

## List and delete, by hand

Emptying a bucket is two calls repeated: list up to 1,000 keys, delete them in
one `DeleteObjects` request.

```python
import boto3
s3 = boto3.client("s3", endpoint_url=ENDPOINT, region_name=REGION,
                  aws_access_key_id=AK, aws_secret_access_key=SK)
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=B, PaginationConfig={"PageSize": 1000}):
    keys = [o["Key"] for o in page.get("Contents", [])]
    if keys:
        s3.delete_objects(Bucket=B, Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True})
```

Two things this naive version gets wrong, both found in the campaign:

**Rate.** S3 accepts about 3,500 deletes per second per prefix. Thirty-two
parallel batches triggered `SlowDown`. Four parallel batches, with adaptive
retries and exponential back-off on `SlowDown` or HTTP 503, emptied 1.3 million
objects in about four minutes without errors.

**Integrity header.** `DeleteObjects` must carry a checksum of its XML body.
Recent boto3 sends a CRC32 header; OSS and OBS require `Content-MD5` and answer
`MissingArgument` otherwise. Add the header just before the request is signed:

```python
import base64, hashlib
def content_md5(request, **kwargs):
    body = request.body.read() if hasattr(request.body, "read") else (request.body or b"")
    if hasattr(request.body, "seek"): request.body.seek(0)
    for h in list(request.headers.keys()):
        if h.lower().startswith("x-amz-checksum") or h.lower() == "x-amz-sdk-checksum-algorithm":
            del request.headers[h]
    request.headers["Content-MD5"] = base64.b64encode(hashlib.md5(body).digest()).decode()
s3.meta.events.register("before-sign.s3.DeleteObjects", content_md5)
```

Registering on `before-sign` matters: the header must exist before the
signature is computed, or the signature will not cover it.

Also abort unfinished multipart uploads; they keep a bucket non-empty:

```python
for up in s3.list_multipart_uploads(Bucket=B).get("Uploads", []):
    s3.abort_multipart_upload(Bucket=B, Key=up["Key"], UploadId=up["UploadId"])
```

## Why it matters to the measurement

If a bucket is not emptied, Terraform cannot delete it, its name stays in the
state, and the next object run measures on a bucket full of earlier objects. On
Alibaba that made writes 9 to 15% slower (deviation D1). The count of deleted
objects is also a free check: it must equal threads x 20,480, or twice that
for a two-client run.

GCS's S3 interface has no `DeleteObjects`; there, Terraform's `force_destroy`
deletes objects one at a time, which took hours for the largest buckets.

*Automated by* `sweep/purge_s3.py` (4 workers, adaptive retries, back-off,
Content-MD5, multipart abort, refuses any bucket not named `csb-bench*`).

Next: [Telemetry and the Network](F4-telemetry-and-network.md)
