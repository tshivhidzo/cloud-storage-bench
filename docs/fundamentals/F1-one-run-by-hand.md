# F1. One Measurement by Hand

Every one of the 228 runs is the same seven steps. Here you do them yourself,
first for block storage, then file, then object.

## The seven steps

1. Create a fresh storage target.
2. Make it reachable from the client (mount a volume or share; name a bucket).
3. Drop the client's caches, so reads cannot be served from local memory.
4. Warm up, so the first measured second is not a cold start.
5. Measure a write pass then a read pass, recording per-core CPU throughout.
6. Record what was run and what came out.
7. Destroy the target, so it cannot affect the next run or keep billing.

## Block storage

**Step 1 and 2.** The storage module creates one 100 GB volume, attaches it to
host 1, formats it once with ext4 and mounts it at `/mnt/block`:

```bash
cd ~/cloud-storage-bench-thesis-v1/terraform/aws
terraform init -input=false
terraform apply -auto-approve -var paradigm=block
terraform output target                       # /mnt/block
df -h /mnt/block
```

**Step 3.** Write dirty pages to disk, then drop the page cache, dentries and
inodes:

```bash
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

**Step 4.** The harness runs the measurement command itself for up to 90 s and
kills it, then starts again; the first pass warms the volume and the client
stack:

```bash
CMD="elbencho -t 4 -b 64k --lat --latpercent --timelimit 600 --direct -s 5120m -w -r /mnt/block/csb.dat"
timeout 90 $CMD > /dev/null 2>&1
```

**Step 5.** Start telemetry, measure, stop telemetry:

```bash
mpstat -P ALL 5 > /tmp/run.mpstat.txt &  MP=$!
$CMD --csvfile /tmp/run.csv | tee /tmp/run.stdout.log
kill $MP
```

What each flag means:

| Flag | Meaning | Why |
|---|---|---|
| `-t 4` | 4 client threads | the concurrency level under test |
| `-b 64k` | 64 KiB per I/O | the workload's operation size |
| `-s 5120m` | 5 GiB in total | 1.25 GiB per thread (weak scaling) |
| `-w -r` | write pass, then read pass | the balanced workload |
| `--direct` | O_DIRECT, bypass the page cache | reads must come from the volume |
| `--timelimit 600` | stop a phase at 600 s | bounds slow cells; a write that hits it ends the run (write-only) |
| `--lat --latpercent` | latency histogram and percentiles | per-phase p99 |
| `--csvfile` | machine-readable phase results | input to the analysis |

**Step 6.** Note the command line, its exit code, the start and end time and the
elbencho binary's hash:

```bash
sha256sum $(which elbencho)
```

**Step 7.**

```bash
terraform destroy -auto-approve -var paradigm=block
```

## File storage

The same, with `-var paradigm=file`: the module creates the provider's file
service (EFS, Azure Files, Filestore, SFS Turbo, NAS), mounts it at `/mnt/file`
over NFS or SMB, and the command writes `/mnt/file/csb.dat`. `nfs-common` (or
`cifs-utils` on Azure) must be installed.

## Object storage

With `-var paradigm=object` the target is a bucket name, not a path. There is
nothing to mount; elbencho talks to the bucket over HTTP. On AWS the host's
instance role supplies temporary credentials:

```bash
TOKEN=$(curl -sX PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
ROLE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/)
curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE
# AccessKeyId, SecretAccessKey, Token -> pass as --s3key, --s3secret, --s3sessiontoken
BUCKET=$(terraform output -raw target)
elbencho -t 4 -b 64k --lat --latpercent \
  --s3endpoint https://s3.af-south-1.amazonaws.com --s3region af-south-1 \
  --s3key "$AK" --s3secret "$SK" --s3sessiontoken "$TK" \
  -n 1 -N 20480 -s 64k -w -r "$BUCKET" --csvfile /tmp/obj.csv
```

Here `-n 1 -N 20480 -s 64k` means one directory per thread with 20,480 objects
of 64 KiB, again 1.25 GiB per thread. There is no time limit: every object is
written and read.

> If `--s3endpoint` is missing, elbencho treats the bucket name as a **local
> file** and silently benchmarks the host's root disk. A `csb-bench-*` file
> appearing in the working directory is the sign.

Before `terraform destroy`, empty the bucket (F3); a bucket with millions of
objects is slow, and on Alibaba impossible, to delete otherwise.

## What automates this

`scripts/provision.py` wraps steps 1, 2 and 7 (`terraform apply` and `destroy`
with `-var paradigm=...`, and reads the `target` output).
`scripts/runners.py` builds the elbencho command line, refreshes AWS role
credentials and drops caches. `sweep/run_rerun_v21.py` does steps 3 to 6 for
every run and writes step 6 as one line of `run_manifest.jsonl`.

Next: [The Design and the Orchestrator](F2-design-and-orchestrator.md)
