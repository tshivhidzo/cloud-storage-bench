# QUICKSTART — running the campaign from a Windows 10 laptop

This is the exact sequence for **your** setup: a Windows 10 laptop as the driver,
and one Ubuntu 22.04 benchmark VM per provider doing the actual measuring. The
VMs are now **provisioned by Terraform** — you don't click through any console.
The laptop only runs Terraform, SSHes in, and pulls files back; no measurement
happens on it, so Windows never touches a result.

Do **AWS end-to-end first**, look at the bill, then repeat for the others.

> The golden rule, from your own harness: **report what you measure.** Blank
> cells are disclosed as gaps. Nothing here invents a number.

---

## Host topology and regions

Each host sits in the same region as the storage it measures, so every provider
is benchmarked locally to its own storage.

| Provider | Host region | Locality | VM (4 vCPU / 16 GB / 100 GB SSD) |
|----------|-------------|----------|----------------------------------|
| AWS      | af-south-1 (Cape Town) | local | m5.xlarge |
| Azure    | southafricanorth (Johannesburg) | local | Standard_D4s_v3 |
| GCP      | africa-south1 (Johannesburg) | local | e2-standard-4 |
| Huawei   | af-south-1 (Johannesburg) | local | c6.xlarge.4 |
| Alibaba  | me-central-1 (Dubai) | **offshore** | ecs.g6.xlarge |

Alibaba has **no African region** — its host is offshore and the harness labels
it `offshore` in the module output. Report that honestly in Chapter 4/5; it is a
real confound for the Alibaba latency figures, not something to paper over.

Each host gets its **own dedicated VPC/VNet**, SSH locked to your public IP, a
**least-privilege role** (no long-lived keys ever land on the host), and an
**8-hour auto-shutdown** so a forgotten VM can't bill all week.

---

## 0. One-time laptop setup (20 min)

Install on Windows 10:

1. **Git for Windows** (gives Git Bash + `ssh`/`scp`): https://git-scm.com/download/win
2. **Terraform** for Windows: https://developer.hashicorp.com/terraform/install
3. **AWS CLI v2** (add the Azure/GCP CLIs when you reach those providers).

Run everything below in **Git Bash**, not PowerShell.

Make an SSH key if you don't have one:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa    # press enter through the prompts
```

Authenticate the provider CLI you're about to use (e.g. `aws configure`, or
`az login`, or `gcloud auth application-default login`). Terraform uses these
credentials **from your laptop** to create the host — they never go onto it.

---

## 1. Bring up the AWS benchmark host

```bash
cd ~/cloud-storage-bench
./scripts/host_up.sh aws
```

This detects your public IP, locks SSH to it, creates the VPC/subnet/gateway,
the least-privilege instance role, and the VM; then waits for cloud-init to
install python3, sysstat, ifstat, fio, nfs-common, Terraform, elbencho (with S3
support) and the cloud SDKs. It prints the host IP and confirms
`elbencho --version` when the host is ready.

Useful knobs:

```bash
AUTO_SHUTDOWN_HOURS=12 ./scripts/host_up.sh aws     # longer campaign
GCP_PROJECT=my-project ./scripts/host_up.sh gcp     # GCP needs the project id
```

> A full 45-run provider slice can outrun the 8-hour timer. Either raise
> `AUTO_SHUTDOWN_HOURS` up front, or cancel the timer on the host with
> `sudo shutdown -c` — and then remember to tear the host down yourself.

---

## 2. Copy the harness to the host and SSH in

```bash
scp -r ~/cloud-storage-bench ubuntu@<AWS_HOST_IP>:~/
ssh ubuntu@<AWS_HOST_IP>
cd ~/cloud-storage-bench
```

---

## 3. Credentials on the host

The host carries an **instance role**, so for AWS you create **no**
`credentials.env` at all — boto3, the CLI and Terraform pick the role up
automatically. That is the whole point of the role-based model in
`ACCESS_AND_AUTH.md`.

Only if a provider forces static keys, copy the template on the host and source
it — never commit it, never paste keys into chat:

```bash
cp configs/credentials.env.example configs/credentials.env
set -a && source configs/credentials.env && set +a
```

---

## 4. Verify access BEFORE spending anything

```bash
python3 scripts/auth_preflight.py --providers aws --out results/auth_report.json --strict
```

Fix whatever it flags until AWS shows **READY**. Two minutes here saves hours.

---

## 5. Record the network context

```bash
cp configs/targets.example.csv configs/targets.csv   # trim to your real endpoints
python3 scripts/network_probe.py --targets configs/targets.csv --out results/network_probe.json
```

---

## 6. Dry-run the plan (spends nothing)

```bash
python3 scripts/run_campaign.py --providers aws --dry-run
```

Expect the AWS slice: 3 paradigms × 5 workloads × 3 reps = **45 runs** at
concurrency 16.

---

## 7. Initialise the storage-target module (once, on the host)

```bash
cd terraform/aws && terraform init && cd ../..
```

AWS is complete for **object, block and file** and mounts EBS/EFS onto the host
automatically. The other providers' **object** modules are complete; their
block/file modules are scaffolds to finish first (`terraform/README.md`).

---

## 8. Run the campaign

```bash
python3 scripts/run_campaign.py --providers aws --paradigms all \
    --workloads all --reps 3 --concurrency 16 --seed 42 --outdir ./results
```

Each run provisions its target, drops caches, warms up 60 s, measures 900 s,
writes raw output to `results/raw/`, checksums it, and tears the target down.
Watch the first two runs complete and tear down cleanly before walking away.

Optional scaling sweep (feeds the scaling exponents; not part of the 225):

```bash
python3 scripts/run_campaign.py --sweep --providers aws --paradigms all \
    --levels 1,4,16,64 --reps 3 --outdir ./results
```

---

## 9. Extract, cross-check, cost

```bash
python3 scripts/parse_results.py --outdir ./results          # -> results/all_runs.csv
python3 scripts/fio_crosscheck.py --mount /mnt/block --workload read --concurrency 16 \
    --elbencho-tput <v> --elbencho-iops <v> --elbencho-lat <v>
python3 scripts/add_costs.py --outdir ./results --costs results/focus_costs.csv --basis-gb 100
```

---

## 10. Pull results back, then TEAR DOWN

On the **laptop**:

```bash
mkdir -p ~/campaign/aws
scp -r ubuntu@<AWS_HOST_IP>:~/cloud-storage-bench/results/* ~/campaign/aws/
./scripts/host_down.sh aws      # destroys the host and its VPC
./scripts/leak_check.sh aws     # MUST come back empty
```

`leak_check.sh` lists any instance, volume, filesystem or bucket still alive.
**Empty output = clean.** Anything listed is still costing you money.

---

## 11. Repeat for the other providers

```bash
./scripts/host_up.sh azure
GCP_PROJECT=my-project ./scripts/host_up.sh gcp
./scripts/host_up.sh huawei
./scripts/host_up.sh alibaba
```

Then steps 2–10 on each, with `--providers <that provider>`. Keep each
provider's results under `~/campaign/<provider>/`. You can run the **object**
paradigm on all five immediately; complete the block/file scaffolds before
running those two paradigms on the non-AWS clouds.

When everything is finished:

```bash
./scripts/teardown_all.sh       # storage targets + hosts, every provider
./scripts/leak_check.sh         # verify
```

---

## 12. Merge and get the honesty gate

Put every provider's `all_runs.csv` under one tree
(`results/aws/all_runs.csv`, `results/azure/all_runs.csv`, …), then:

```bash
python3 scripts/consolidate.py --outdir ./results
```

Read `results/completeness_report.txt`. **225/225** means a full dataset; e.g.
**135/225** means the thesis reports **N = 135** and the gaps. That is not a
failure — it is the honesty the harness exists to protect.

---

## 13. Send the results back

Upload into our chat:

- `results/all_runs.csv` (the dataset — required)
- `results/completeness_report.txt`
- `results/manifest.sha256`
- your real cost export (if step 9 produced one)
- optionally `results/network_probe.json`, `results/auth_report.json`

With the **real** `all_runs.csv` I will regenerate Chapter 5, the ANOVA and cost
tables, and the black-and-white figures **from your measurements**, reconcile
every number across Chapter 5 / Chapter 6 / the appendices, and rewrite the
abstract and conclusions in completed-study language.

---

## If something fails

- **`host_up.sh` fails on credentials** → authenticate that provider's CLI on the laptop first.
- **SSH times out** → your public IP changed (common on home/mobile links). Re-run `host_up.sh`; it re-detects and updates the rule.
- **auth_preflight fails** → fix that provider's permissions; don't skip ahead.
- **terraform errors on block/file for a non-AWS provider** → that scaffold needs completing; object still runs.
- **elbencho missing after bootstrap** → the release URL changed; install it manually per `configs/elbencho/NOTES.md`.
- **a metadata run shows no MB/s** → expected; metadata is ops/s + latency.
- **coverage below 225** → fine and honest; report the real N.

**Never fill a gap with an invented number.** That is what failed the first
examination, and this whole harness exists to prevent it.
