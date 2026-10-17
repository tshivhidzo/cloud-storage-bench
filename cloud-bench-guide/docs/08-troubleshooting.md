# Troubleshooting a Running Campaign

Every problem below happened during the October 2026 campaign. Each entry gives
the symptom, the cause, the fix, and whether it became a recorded deviation.
The rule throughout: record the problem and its treatment in
`sweep/DEVIATIONS_V21.md` before looking at the affected results, and never
change a measurement parameter mid-campaign.

## Bucket emptying

**AWS: `SlowDown` during purge.** Deleting 1.3 million objects with 32
parallel batches exceeded S3's per-prefix delete rate. Fix: `purge_s3.py` uses
4 workers, adaptive retries and back-off. Housekeeping commit; no deviation.

**Alibaba: `MissingArgument` on every `DeleteObjects`.** Recent boto3 sends a
CRC32 checksum; OSS (and OBS) require `Content-MD5`. Nothing was deleted,
Terraform could not delete the non-empty bucket, and the next object run
reused it. Fix: `purge_s3.py` registers a `before-sign` handler that sets
`Content-MD5` and removes the CRC headers. Copy the fixed script to the host;
it is reloaded at the next purge without restarting the campaign:

```bash
scp "$ONE/sweep/purge_s3.py" ubuntu@$H:~/cloud-storage-bench-thesis-v1/sweep/
ssh ubuntu@$H 'grep -c Content-MD5 ~/cloud-storage-bench-thesis-v1/sweep/purge_s3.py'
```

Deviation D1: three object runs had measured on a bucket holding earlier
objects. They were kept and flagged, the three cells were repeated once on
fresh buckets (lab 9), and both results are reported. Writes on the reused
bucket were 9 to 15% slower; the exponent moved by 0.008.

**`SecondLevelDomainForbidden` from OSS.** `S3_VIRT_ADDR=1` was missing after
reloading credentials. Re-export it; the reload command now includes it.

**Alibaba: an empty orphan bucket.** A failed Terraform operation left
`csb-bench-zc7vpqnd` outside the state. Harmless (empty), deleted at teardown.

## Teardown

**GCP: `Error 404: No such object` in `force_destroy`.** A race inside the
provider's parallel delete. The measurement was complete and the next run got
a new bucket. Deviation D4, no effect.

**A leftover Terraform lock file** after an interrupted run. With local state
it does not block the next apply; check
`terraform -chdir=../terraform/<provider> state list` is empty.

## Two-client runs

**Huawei: `Unreachable service: host2:1611`.** Stage 2 was started with
`H2P=host2`, because `history | grep` found the variable name, not the
number. All three two-client runs failed within 5 s, before measuring
(deviation D2). Fix: read the address from the laptop
(`terraform output -raw host2_private_ip`) and resume with the number.

## Access

**SSH times out on every host.** The laptop's IP changed; see lab 4
(`fix_ssh_ip.sh`). The campaigns keep running.

**Azure Terraform: `AADSTS70043` or `AADSTS50076`.** The 12-hour sign-in limit
or MFA for Graph; sign in again with both scopes (lab 2).

**`${#!v}: event not found`.** History expansion in an interactive shell; use
`${#VAR}` per variable.

## Is it still running?

```bash
tmux ls
ps -ef | grep -E 'run_rerun_v21|elbencho|terraform' | grep -v grep
tail -15 rerun_<provider>_s1.log
```

The status script counts attempts from the manifest. If a run was started but
has no record, it was interrupted; check the Terraform state and the mount
before resuming.

Next: [Stage 2 and Supplementary Runs](09-stage-2-and-supplementary.md)
