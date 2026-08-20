# As-executed configuration (sweep v1 campaign)

Sources, in order of authority: retained Terraform state (hosts), Terraform
definitions (targets, recreated per run), archived run manifests (regions and
command lines). Items not recoverable from these sources are marked
UNRECOVERABLE rather than reconstructed from memory. NIC limits are the
providers' documented figures for the SKU and must be cited as documentation,
not measurement; sweep protocol v2 adds a measured iperf3 baseline per host.

| Item | AWS | Azure | GCP | Huawei | Alibaba |
|---|---|---|---|---|---|
| Region (from manifests) | af-south-1 | southafricanorth | africa-south1 | af-south-1 | me-central-1 |
| Benchmark host SKU | m5.xlarge (4 vCPU/16 GB) | Standard_D4s_v3 (4 vCPU/16 GB) | e2-standard-4 (4 vCPU/16 GB) | c6.xlarge.4 (4 vCPU/16 GB) | ecs.hfg6.xlarge (from host tfstate; auto-picked 4 vCPU/16 GB class) |
| Host root disk | 100 GB | 100 GB | 100 GB (pd-ssd) | 100 GB SSD | 100 GB |
| Documented NIC limit | up to 10 Gbps (m5.xlarge, burst) | up to 2 Gbps class (D4s_v3, per Azure docs) | up to 8 Gbps (e2-standard-4, egress caps apply) | per c6 flavour docs | per hfg6 flavour docs |
| Block product/tier | EBS gp3, 100 GB (baseline 3000 IOPS/125 MB/s) | Managed Disk StandardSSD_LRS 100 GB (data), Premium_LRS (as defined for the calibration target) | pd-ssd 100 GB | EVS SSD 100 GB | ESSD/cloud disk 100 GB (definition: size var 100) |
| File product | EFS generalPurpose, elastic throughput | Azure Files Standard (SMB) | Filestore BASIC_HDD | SFS Turbo 500 GB (service minimum; size disclosed) | NAS standard, Capacity type, NFS |
| File protocol/mount | NFS4.1, defaults in bootstrap | SMB 3.x, defaults | NFS3, defaults | NFS, defaults | NFS, defaults |
| Object class | S3 Standard | Blob StorageV2 Standard LRS, private container | GCS Standard | OBS Standard | OSS Standard |
| Object endpoint (archived per run) | regional S3 endpoint (auto-derived) | SDK (account endpoint) | storage.googleapis.com (interop/HMAC) | obs.af-south-1.myhuaweicloud.com | oss-me-central-1-internal.aliyuncs.com (final dataset); public-endpoint runs quarantined |
| Instrument | elbencho 3.1-1 | elbencho 3.1-1 (block/file); azure_blob_runner v2.3 (object) | elbencho 3.1-1 | elbencho 3.1-1 | elbencho 3.1-1 |
| Mount options as executed | UNRECOVERABLE beyond bootstrap defaults (bootstrap script archived) | same | same | same | same |
| Deployed runner hash | not recorded in v1 (added in protocol v2) | not recorded in v1 (added in protocol v2) | -- | -- | -- |

Known v1 limitations this table makes explicit: runner/script hashes were not
recorded per run (protocol v2 requirement); NIC limits are documentation-based;
mount options beyond the archived bootstrap defaults are unrecoverable; the
Alibaba host instance family was auto-selected within the 4 vCPU/16 GB
constraint and its exact SKU is recovered from retained host state.

## Documentation sources for NIC limits (family documentation pages)

- AWS m5.xlarge: AWS EC2 instance types documentation (m5 family),
  docs.aws.amazon.com/ec2/latest/instancetypes/ (documented "up to 10 Gbps" burst class).
- Azure Standard_D4s_v3: learn.microsoft.com/azure/virtual-machines/dv3-dsv3-series.
- GCP e2-standard-4: cloud.google.com/compute/docs/general-purpose-machines#e2_machine_types
  (egress caps per vCPU class).
- Huawei c6.xlarge.4: support.huaweicloud.com/intl/en-us/productdesc-ecs/ (c6 family).
- Alibaba ecs.hfg6.xlarge: alibabacloud.com/help/en/ecs/user-guide/instance-family (hfg6 family).

These are family-level documented figures, cited as documentation, not
measurement; sweep protocol v2 replaces them with a measured per-host
baseline. Host SKU evidence extracted from retained state is published in
configs/host_state_extract.json (state files themselves are withheld:
they contain resource identifiers of a live account).
