# Preparing the Hosts

In this lab you copy the harness to both hosts, start the second host's
services, and give host 1 the storage credentials it needs, in one tmux shell.

## Copy the harness

`scp -r` of the whole clone is slow and copies Terraform providers and state
that must not leave the laptop. Stream a filtered tar instead:

**laptop**

```bash
for h in $H $H2; do
  tar --exclude=.git --exclude=.terraform --exclude='*.tfstate*' --exclude='results-*' \
      --exclude=quarantine --exclude='*.zip' -czf - . \
    | ssh ubuntu@$h 'mkdir -p ~/cloud-storage-bench-thesis-v1 && tar -xzf - -C ~/cloud-storage-bench-thesis-v1'
done
```

## Start host 2's services

```bash
ssh ubuntu@$H2 'sudo apt-get install -y iperf3 && iperf3 -s -D && elbencho --service && nproc'
```

On Azure leave out `elbencho --service`: the runner has no multi-host mode, so
host 2 is only the iperf3 server (until the supplementary test in lab 9).

## Open the campaign shell on host 1

```bash
ssh ubuntu@$H
tmux new -s rerun          # later: tmux attach -t rerun
cd ~/cloud-storage-bench-thesis-v1
H2P=<host 2 private ip>    # type the number; do not reuse a variable name
```

Window 0 of this tmux session is the campaign shell. Everything that needs
credentials runs there.

## Provider environment

**AWS:** nothing; the instance role is used. Install the CLI for the
preflight: `sudo apt-get install -y awscli`.

**Azure:** run the `host_env_setup` commands from the laptop's Terraform output
on the host, so Terraform and the runner use the managed identity:

```bash
terraform -chdir=terraform/hosts/azure output -raw host_env_setup | ssh ubuntu@$H 'bash -s'
# then in window 0: source ~/.bashrc
```

**GCP, Huawei, Alibaba:** elbencho reads its object-storage settings from
`S3_*` variables, not from the provider variables that Terraform uses. Pass
them as in lab 2 and source them in window 0:

| Provider | S3_ENDPOINT | Other |
|---|---|---|
| GCP | `https://storage.googleapis.com` | HMAC ID and secret; `AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED`, `AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED` |
| Huawei | `https://obs.af-south-1.myhuaweicloud.com` | `S3_REGION=af-south-1`, `S3_VIRT_ADDR=1`, plus `HW_ACCESS_KEY`/`HW_SECRET_KEY` for Terraform |
| Alibaba | `https://oss-me-central-1-internal.aliyuncs.com` | `S3_REGION=me-central-1`, `S3_VIRT_ADDR=1`, plus `ALICLOUD_ACCESS_KEY`/`ALICLOUD_SECRET_KEY` for Terraform |

> Alibaba must use the **internal** endpoint. The public endpoint leaves
> through the host's public interface, which we had created with a
> 100 Mbit/s limit; in August twelve runs measured that limit (about
> 12 MiB/s) instead of OSS. The orchestrator now refuses to start otherwise.
> Alibaba and Huawei also require virtual-hosted addressing: without
> `S3_VIRT_ADDR=1`, OSS answers `SecondLevelDomainForbidden`.

Check in window 0 (lengths only, never values):

```bash
echo "${#S3_ACCESS_KEY} ${#S3_SECRET_KEY} virt=$S3_VIRT_ADDR $S3_ENDPOINT"
getent hosts $(echo $S3_ENDPOINT | sed 's#https://##')   # Alibaba and Huawei: a 100.x internal address
```

## Preflight

```bash
nproc                                                     # 4
python3 scripts/auth_preflight.py --providers <provider> --strict
dpkg -s nfs-common >/dev/null 2>&1 || sudo apt-get install -y nfs-common
timeout 3 bash -c "</dev/tcp/$H2P/1611" && echo svc-ok     # elbencho service on host 2
timeout 3 bash -c "</dev/tcp/$H2P/5201" && echo iperf-ok   # iperf3 server on host 2
cd sweep && python3 run_rerun_v21.py --provider <provider> --host2 $H2P --dry-run --stage 1 | head -1
```

Expected: `READY`, `svc-ok`, `iperf-ok`, and `v2.1 plan for <provider>: 24 runs`.

Next: [Measuring the Network Baseline](06-network-baseline.md)
