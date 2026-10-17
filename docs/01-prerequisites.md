# Prerequisites

In this lab you prepare the laptop that drives the campaign and the five cloud
accounts it will use.

## Cloud accounts

You need an account with billing enabled on each provider, in the regions
below, with enough quota for two 4 vCPU hosts plus one storage target at a
time.

| Provider | Region | Host type | Services that must be activated |
|---|---|---|---|
| AWS | af-south-1 (opt-in region; enable it first) | m5.xlarge | EC2, EBS, EFS, S3 |
| Azure | southafricanorth | Standard_D4s_v3 (8 vCPU quota for two) | VMs, Managed Disks, Files, Blob |
| GCP | africa-south1 | e2-standard-4 | Compute Engine, Filestore (`file.googleapis.com`), Cloud Storage |
| Huawei | af-south-1 | c6.xlarge.4 | ECS, EVS, SFS Turbo, OBS |
| Alibaba | me-central-1 | ecs.hfg6.xlarge | ECS, ESSD, NAS, OSS |

Set a budget alert on every account before you continue. The largest cost is
object-storage request charges: a 128-thread object run writes and reads
2.6 million objects.

## Laptop tools

Install, and check that each command prints a version:

```bash
git --version
terraform version
aws --version
az version
gcloud version
python3 --version        # 3.10 or later, with numpy and matplotlib for labs 11-12
ssh -V
```

Create an SSH key if you do not have one, and keep its passphrase:

```bash
ls ~/.ssh/id_rsa.pub || ssh-keygen -t rsa -b 4096
```

Load it once per window so you are not asked for the passphrase on every
connection:

```bash
eval $(ssh-agent) && ssh-add
```

## The repository

```bash
mkdir -p ~/publish && cd ~/publish
git clone https://github.com/tshivhidzo/cloud-storage-bench.git cloud-storage-bench-thesis-v1
cd cloud-storage-bench-thesis-v1
```

The clone opens on `main`, which holds the code the labs use. This guide is on
the separate branch `cloud-bench-guide` and is not needed in the clone. To work
from exactly the released state rather than the latest `main`, check out the
tag on a branch of your own:

```bash
git checkout -b my-campaign sweep-v2.1
```

Keep a working copy outside git as well (we used a OneDrive folder, referred to
as `ONE`). Edits are made there and copied into the clone before each commit.

```bash
ONE="/c/Users/<you>/OneDrive/.../cloud-storage-bench"
```

## Rules that hold for every lab

- Credentials live only in the shell that uses them: never in a file under
  `ONE`, never in a commit, never pasted into a chat or an issue.
- Every attempt is recorded. A run is never accepted or rejected because of its
  result.
- A problem found during the campaign is written into the deviations log
  (`sweep/DEVIATIONS_V21.md`) when it is found, together with how it will be
  treated, before its results are looked at.

Next: [Credentials](02-credentials.md)
