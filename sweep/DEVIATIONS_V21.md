# v2.1 rerun: deviations log

Each entry is written when the problem is found, before the affected runs'
results are looked at. Times are SAST.

## D1. Alibaba: bucket not emptied between object runs (13 Oct 2026)

What happened. purge_s3.py could not delete objects on Alibaba OSS. OSS
answered every DeleteObjects call with "MissingArgument", because current
boto3 sends a CRC32 checksum and OSS requires Content-MD5. Terraform's
destroy then failed on the non-empty bucket, so the bucket
(csb-bench-vkkec61a) stayed in the Terraform state and was reused.

Runs affected (from run_manifest.jsonl):

| Run | Status | Effect |
|---|---|---|
| alibaba-object-balanced-c16-r1 | ok | first run on the bucket, so it started empty as intended; teardown failed |
| alibaba-block-balanced-c16-r2 | failed | Terraform apply failed on the leftover bucket; counted as attempt 1 of 3 and retried under the normal rule |
| alibaba-object-balanced-c64-r1 | ok | ran on a bucket already holding objects from earlier runs |
| alibaba-object-balanced-c16-r2 | ok | ran on a bucket already holding objects from earlier runs |
| alibaba-object-balanced-c04-r2 | ok | ran on a bucket already holding objects from earlier runs |
| alibaba-object-balanced-c64-r3 | running when found | NOT affected: the fixed purge before its provision emptied csb-bench-vkkec61a (1,307,320 objects deleted in 220 s), so it ran on an empty bucket (same name) |

Fix. purge_s3.py now sends Content-MD5 on DeleteObjects and drops the CRC
headers. This is housekeeping only: no measurement code or parameter
changed. It was committed separately after protocol-v2.1-locked. The fix
takes effect at the first purge after it is copied to the host.

Decision, fixed before the results are looked at (revised 13 Oct, when the
count rose from two runs to three; c64-r3 was then found unaffected):

1. The three runs on a reused bucket (c64-r1, c16-r2, c04-r2) stay in the dataset as executed,
   because the measurement followed the protocol (same parameters, same
   dataset per thread, object names overwritten in place). They are flagged
   `bucket_reused`. The primary analysis uses all runs as executed.
2. If time allows after Alibaba stage 2 and before STOP_AT, the same three
   cells are repeated once each on a fresh bucket under separate run IDs
   (suffix `-fb`). These are supplementary runs, not retries.
3. A sensitivity analysis replaces each reused-bucket run with its `-fb`
   repeat where one exists, or drops it where none exists. Both results
   are reported.

Result (16 Oct 2026; the three -fb repeats ran ok on new buckets). On a
reused bucket, write throughput was 9 to 15% lower than on the fresh repeat
of the same cell (c64 260.7 vs 287.7, c16 69.1 vs 81.0, c04 18.3 vs 20.8
MiB/s). Read throughput was unchanged (ratios 0.96 to 0.995). The Alibaba
object exponents barely move:

| Operation | As executed | Reused runs replaced by -fb | Reused runs dropped |
|---|---|---|---|
| Write | 0.966 [0.949, 0.983] | 0.974 [0.957, 0.992] | 0.973 [0.958, 0.989] |
| Read | 0.920 [0.872, 0.968] | 0.921 [0.871, 0.972] | 0.925 [0.868, 0.982] |
| Combined | 0.947 [0.922, 0.972] | 0.952 [0.922, 0.982] | 0.953 [0.922, 0.985] |

## D5. Supplementary Azure two-host object test (decided 16 Oct 2026)

Written before the test is run. It is supplementary: it is not part of
protocol-v2.1-locked and is reported separately from the primary results.

Why. The AWS runner-equivalence runs (stage 2) showed that the SDK runner
becomes client-CPU-bound on a 4 vCPU host by 64 threads. Every Azure object
cell ran at about 100% client CPU from 16 threads. Without a second client,
the Azure Blob service limit cannot be separated from the client limit.
The other four object services have two-client runs in the plan; Azure did
not, because the runner has no distributed mode.

Design, fixed now. Three repetitions of `azure-object-balanced-c64-rN-mc2az`:

- `azure_blob_runner_v2.py` (unchanged, same SHA-256 as the primary runs),
  workload balanced, `--concurrency 64 --duration 2400`, run at the same
  time on both Azure hosts (D4s_v3, same subnet);
- one fresh storage account per repetition, provisioned by the same
  Terraform module; host 1 uses container `bench`, host 2 container
  `bench2`, so object names cannot collide;
- start skew between hosts recorded; per-core mpstat on both hosts;
- aggregate throughput per phase = sum of the two hosts' phase throughput.
  The runner's phases are deadline-driven (1200 s each), so the windows
  overlap except for the start skew.

Comparison, fixed now. The aggregate is compared with the Azure single-host
64-thread primary runs (`ratio_2hosts`, as for the other providers). We
read about 2× as "the single client was the limit"; about 1× as "a limit
outside the client"; anything between is reported as measured, with no
further claim. Driver: `sweep/azure_mc2.py`.

Result (16 to 17 Oct 2026; 3 of 3 repetitions ok, all teardowns ok, the
same runner SHA-256 4e05b889b4b2 on both hosts as in the primary runs;
archive rerun_azure_mc2.tgz, SHA-256 98c4fe6e...24c1):

| | Single host, primary c64 | Two hosts, D5 (mean of 3) | Ratio |
|---|---|---|---|
| Write, aggregate | 51.6 MiB/s | 91.6 MiB/s (CV 0.8%) | 1.78 |
| Read, aggregate | 46.1 MiB/s | 82.8 MiB/s (CV 0.5%) | 1.80 |
| Host 1 write / read | 51.6 / 46.1 | 51.8 / 46.0 | 1.00 / 1.00 |
| Host 2 / host 1 | n/a | 0.77 write, 0.80 read | n/a |

Under the rule fixed above, 1.78 to 1.80 is "between" and is reported as
measured. Two further observations explain the shortfall from 2×; they
are interpretation, not part of the pre-set rule:

- Host 1 gave the same throughput with host 2 running as alone (ratio
  1.00), so the service did not slow it down at about 92 MiB/s
  aggregate.
- Both hosts ran at 99.6 to 99.9% CPU throughout. Host 2 is on an older
  processor (Intel Xeon E5-2673 v4 at 2.3 GHz, against host 1's Platinum
  8171M at 2.6 GHz, both D4s_v3), and it delivered 77 to 80% of host 1's
  throughput. That is consistent with a CPU-bound client on slower cores.

Conclusion: within about 92 MiB/s aggregate and 128 threads, the limit
is the client, not Azure Blob.

## D3. Alibaba block c16-r2: retry lost to missing credentials (14 Oct 2026)

The first `--resume` pass for alibaba-block-balanced-c16-r2 was started in a
tmux window without the Alibaba credentials. Terraform refused to start and
nothing was provisioned or measured. The retry rule counts it as attempt 2,
so one attempt remains. It is reported as an operator error, not as a
storage or harness failure.

A further attempt was then started with the credentials loaded but without
`S3_VIRT_ADDR=1`. Its pre-provision purge was skipped
(SecondLevelDomainForbidden) and the process was stopped by hand before
it wrote a manifest record. The Terraform state was checked afterwards to
confirm whether anything had been provisioned (result: no alicloud_disk in
state, no block mount; a stale lock-info file was present and did not
block the next apply). No measurement was taken, so this attempt does not
appear in the manifest. The next attempt is recorded as attempt 3, the
last allowed. Attempt 3 completed ok on 15 Oct 2026.

The `-fb` repeats in D1 are run with `run_rerun_v21.py --fb <run ids>`.
This option was added on 15 Oct, after protocol-v2.1-locked. It only
builds the three repeats named in D1 (same cell and parameters, run_id +
"-fb", stage 3) and changes nothing else.

## D4. GCP object c16-r3: transient teardown error (13 Oct 2026)

Terraform's force_destroy on csb-bench-m1q4ge7r stopped with "Error 404: No
such object ... r5/d0/r5-f3625". This is a race inside the provider's
parallel object deletion: the object had already been deleted. The
measurement had finished, and the run is ok. The next object run
(c01-r3) and every later one got a new bucket, so no bucket was reused.
Remaining buckets were checked at teardown on 17 Oct 2026 (leak_check.sh
gcp, via `gsutil ls`): no csb-bench bucket was listed, so
csb-bench-m1q4ge7r no longer exists and nothing was left billing.

## D2. Huawei stage 2 launched with `--host2 host2` (14 Oct 2026)

What happened. Stage 2 on Huawei was started with the literal name `host2`
instead of the second host's private IP. The orchestrator uses this value
only in elbencho's `--hosts localhost,<host2>` for the three two-client
runs. Single-host runs are unaffected.

Outcome. The planned /etc/hosts workaround was not applied in time. All
three two-client runs (c64-r1-mc2, c64-r2-mc2, c64-r3-mc2) failed before
measuring: elbencho reported "Timed out waiting for services to become
ready. Unreachable service: host2:1611", and the buckets were empty (0
objects purged). Each used attempt 1 of 3. The three runs were retried
with `--resume --host2 <private IP>` (IP: 10.45.1.36) as attempt 2.
The single-host stage 2 runs were unaffected.
