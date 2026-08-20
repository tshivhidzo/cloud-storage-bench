# Terraform modules (per provider)

Every module exposes the same contract so `provision.py` can drive them
identically:

- **inputs:** `var.paradigm` (`block|file|object`) and `var.region`
- **outputs:** `target` (a POSIX mount path for block/file, or a bucket/
  container name for object) and `region`

`run_campaign.py` calls `terraform init/apply` before each run and
`terraform destroy` after it, so no target outlives its measurement.

## Completeness status (be honest in the thesis)

| Provider | object | block | file |
|----------|--------|-------|------|
| aws      | complete | complete (EBS, self-mount) | complete (EFS, self-mount) |
| azure    | complete (Blob + SDK runner) | **scaffold** | **scaffold** |
| gcp      | complete (GCS S3-interop) | **scaffold** | **scaffold** |
| huawei   | complete (OBS) | **scaffold** | **scaffold** |
| alibaba  | complete (OSS) | **scaffold** | **scaffold** |

"Scaffold" means the resource skeleton and the exact resources to add are
documented in that module's `main.tf`, but you must complete them (add the disk/
attachment or managed NFS share and the host mount) before running the block or
file paradigms on that provider. Object storage works on all five as written.

This mirrors the harness rule: run and report what actually works. If a
provider's block/file module is not completed, those cells stay empty and the
completeness report counts them as gaps — it does not invent them.

## Assumptions for the AWS block/file self-mount

The AWS module mounts EBS/EFS onto the host **running terraform** (i.e. run the
campaign on the AWS benchmark host, per the topology). The host needs an
instance profile with EC2/EFS permissions, and `nfs-common` + `jq` installed.

---

# Host modules (`terraform/hosts/<provider>/`)

These create the **benchmark VM** itself — one per provider, in the same region
as the storage it measures. Same contract everywhere:

- **inputs:** `ssh_public_key`, `operator_cidr` (SSH lock), `auto_shutdown_hours`,
  `region`, plus `project` for GCP
- **outputs:** `host_ip`, `region`, `locality` (`local`|`offshore`), `ssh`,
  `ready_check`

Drive them with `scripts/host_up.sh <provider>` and `scripts/host_down.sh <provider>`.

| Provider | Region | Locality | VM | Identity |
|----------|--------|----------|----|----------|
| aws | af-south-1 | local | m5.xlarge | IAM role + instance profile (least privilege) |
| azure | southafricanorth | local | Standard_D4s_v3 | user-assigned managed identity, RG-scoped |
| gcp | africa-south1 | local | e2-standard-4 | service account (storage + disk admin) |
| huawei | af-south-1 | local | c6.xlarge.4 | key pair; set OBS keys per host |
| alibaba | me-central-1 | **offshore** | ecs.g6.xlarge | key pair; set OSS keys per host |

Every host module builds a **dedicated VPC/VNet + subnet + gateway**, a security
group allowing SSH **only from your detected public IP**, and NFS within the VPC
so managed file storage can mount. All run the shared cloud-init in
`scripts/cloudinit/bootstrap_host.sh`, which installs the measurement tools,
Terraform, elbencho (S3-enabled) and the SDKs, and arms an **auto-shutdown**.

## Alibaba locality caveat

Alibaba Cloud has no South African region, so its host sits in `me-central-1`
(Dubai) and is labelled `offshore`. Its latency figures are not comparable
like-for-like with the four local providers — disclose this in the methodology
and limitations rather than smoothing it over.
