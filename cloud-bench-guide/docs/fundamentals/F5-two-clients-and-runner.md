# F5. Two Clients and the Runner Test

A throughput curve that levels off can mean the service is full or the client
is. These two controls tell them apart.

## The logic

Run the same total load from one client and from two:

| If the limit is... | then a second client... | and the first client's throughput... |
|---|---|---|
| in the service | does not raise the total | falls |
| in the client | raises the total, up to 2x | stays the same |

Running 128 threads on one host is the cheap half of the test: if the host is
saturated, it adds little.

## Two clients with elbencho, by hand

elbencho has a distributed mode: services on each host, one master that
coordinates them and merges the results.

```bash
# host 2
elbencho --service                      # listens on port 1611
# host 1
elbencho --service                      # the master also needs a local service
elbencho --hosts localhost,$H2P -t 64 -b 64k --lat --latpercent \
  --s3endpoint ... --s3region ... --s3key ... --s3secret ... \
  -n 1 -N 20480 -s 64k -w -r "$BUCKET" --csvfile mc2.csv
elbencho --quit --hosts localhost,$H2P   # stop the services
```

`-t 64` is per host, so the total is 128 threads and 2,621,440 objects. The
master forwards the endpoint and credentials, so host 2 needs no keys. Check
reachability first: `timeout 3 bash -c "</dev/tcp/$H2P/1611" && echo ok`.
A name that does not resolve fails in 5 seconds with `Unreachable service`.

## The Azure SDK runner

Azure Blob has no S3 API, so its object runs use a Python runner. Its design
follows from the failure of its first version, which submitted work in
synchronised batches from one process; the Python interpreter lock serialised
the TLS work, and its throughput fell above four threads, a curve that looked
like the service saturating.

The corrected runner:

- splits the threads over at most 16 processes (memory-safe on 16 GB), with
  threads inside each;
- lets every thread loop independently until a deadline (write phase, then
  read phase, 1,200 s each), writing and re-reading 256 objects of 64 KiB per
  thread;
- keeps a bounded reservoir sample of latencies per thread (10,000 by default)
  for the percentiles;
- reports MB/s (10^6 bytes), which the analysis converts to MiB/s.

## The runner test

To know whether the runner measures what elbencho measures, port it to the S3
API (change only the client library: `boto3` instead of `azure-storage-blob`)
and run both against the same AWS bucket from the same host at 1, 4, 16 and 64
threads. Our result: equal within 5% for writes up to 16 threads, and at
64 threads the runner used 100% CPU and delivered about half of elbencho's
throughput. Varying the reservoir (1,000, 10,000, 100,000) left p99 unchanged
where the client was not saturated.

## Two clients for Azure

The runner has no distributed mode, so run it on both hosts at the same time,
each against its own container in the same storage account, and add the two
throughputs (the phases are deadline-driven, so the windows overlap):

```bash
# host 1, with host 1 able to ssh to host 2 with its own key
ssh ubuntu@$H2P "AZURE_STORAGE_CONNECTION_STRING=\$(cat /dev/shm/az.cs) python3 .../azure_blob_runner_v2.py \
  --workload balanced --concurrency 64 --duration 2400 --container bench2 --csvfile /tmp/h2.csv" &
python3 .../azure_blob_runner_v2.py --workload balanced --concurrency 64 --duration 2400 \
  --container bench --csvfile h1.csv
wait
```

Record `lscpu` on both hosts: our two "identical" D4s_v3 hosts had different
processors, which explained why the total was 1.8x rather than 2x.

*Automated by* `build_argv()` in `sweep/run_rerun_v21.py` (adds `--hosts`),
`sweep/s3_equiv_runner.py` (the S3 port), `sweep/azure_blob_runner_v2.py` and
`sweep/azure_mc2.py` (the Azure two-host driver).

Next: [The Statistics](F6-statistics.md)
