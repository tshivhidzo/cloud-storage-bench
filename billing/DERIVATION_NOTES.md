# Cost rate derivations (real bills -> focus_costs.csv)

All rates are **billed cost / billed GB-months** from the provider's own bill
export in this folder. Nothing is taken from a rate card. GB-month = GB x hours
/ 720. Each derived rate lands on a clean list price, validating the unit
interpretation.

## Huawei (HuaweiDashboard_..._Aug-2026.xlsx)

| paradigm | bill line | cost | usage | rate USD/GB-mo |
|---|---|---|---|---|
| block | EVS Ultra-High IO, 100 GB x 69.9578 h | 2.23864866 | 9.71636 GB-mo | **0.2304** |
| file | SFS Turbo standard, 500 GB x 2.6694 h | 0.18686104 | 1.85378 GB-mo | **0.1008** |
| object | OBS Capacity 3.52179 GB-h | 0.0001125 | 0.0048914 GB-mo | **0.0230** |

Egress: internal upload/download billed at 0; no storage egress rate exists in
the bill -> blank.

**Observation for the thesis:** OBS *request* charges dominated the Huawei bill:
PUT 71.60 + GET 4.99 + DELETE 3.10 = 79.70 USD of the 98.23 USD total -- almost
entirely from the three object-metadata runs (~14.3M PUTs, 12.5M GETs, 7.8M
DELETEs). The harness's cost model (capacity + egress) does not capture
per-request pricing; metadata-heavy workloads are billed on a completely
different axis. This is a finding, not a flaw: report it.

## Alibaba (<account-id-redacted>-..._consumedetailbillv2monthsummary.csv)

| paradigm | bill line | cost | usage | rate USD/GB-mo |
|---|---|---|---|---|
| block | ESSD system disk, 100 GiB x 68.5125 h | 2.6551833 | 9.51563 GB-mo | **0.2790** |
| file | NAS storage usage 57.2383 GB-h (2 lines) | 0.0085857 | 0.0794976 GB-mo | **0.1080** |
| object | OSS Standard Capacity 189.486 GB-h | 0.0053688 | 0.2631751 GB-mo | **0.0204** |

Block rate is derived from the system disk (same ESSD category, precisely known
size x duration); the 15 small per-run data-disk lines match the 15 block runs.

**WARNING -- possible resource leak:** one "Data Disk" line bills 2.65503 USD,
i.e. a 100 GB ESSD alive for ~68 h (the host's whole lifetime), separate from
the system disk. That looks like an orphaned data disk from an interrupted
early run. Check ECS -> Disks in the me-central-1 console and delete it if
present; run leak_check.sh.

## AWS (Cost Explorer API via export_aws_costs.py, service+usage-type classified)

| paradigm | source | rate USD/GB-mo |
|---|---|---|
| block | EC2 / EBS:VolumeUsage.gp3 | **0.1047** |
| file | Elastic File System / TimedStorage | **0.3900** |
| object | Simple Storage Service / TimedStorage-ByteHrs | **0.0274** |

Each rate equals the published af-south-1 list price, validating the
billed-cost / billed-GB-month derivation. Egress billed at 0 in-region.
Note: S3 and EFS both bill capacity under "TimedStorage-ByteHrs"; the SERVICE
dimension is required to separate them (fixed 2026-08-06).

## GCP (console Reports export, SKU granularity)

| paradigm | SKU | cost | usage | rate USD/GB-mo |
|---|---|---|---|---|
| block | SSD backed PD Capacity in Johannesburg | 9.29 | 49.80 GiB-mo | **0.1865** |
| file | Filestore Capacity Basic HDD (Standard) Johannesburg | 0.87 | 4.86 GiB-mo | **0.1790** |
| object | Standard Storage Johannesburg | 0.70 | 34.99 GiB-mo | **0.0200** |

Request charges again dominate: Class A operations (10,410,735 requests,
$52.03) and Class B (2,471,431, $0.97) account for nearly all of GCP's
Cloud Storage spend, mirroring the Huawei OBS finding.

## Azure file/object (dedicated cost-calibration measurement)

Campaign-scale Azure Files/Blob charges fell below the billing export's
resolution, so a calibration was run: 100 GiB held in each service
(storage account csbcal181902, resource group csb-cal-rg) from
2026-08-08T09:38Z for ~72 h. Rates derived from the complete billed day
of 9 August (source: "Azure - cost-analysis - csb-cal-rg.csv"):

| paradigm | meter | cost (full day) | rate USD/GB-mo |
|---|---|---|---|
| object | Hot LRS Data Stored | 0.0706453704 | **0.0212** (x30/100) |
| file | LRS Data Stored | 0.2796782472 | **0.0839** (x30/100) |

Both rates equal Azure's published southafricanorth prices, validating
the derivation. Partial-day ratios on 8 August (0.542 / 0.583 of the
full day) are consistent with the 09:38 UTC window start. All fifteen
provider-paradigm cost cells are now billing-derived; the Azure block
rate remains the manifest-hours approximation noted above.

## Pending
- Azure: consumption API returned no rows (lag or offer type) -> retry export_azure_costs.py or portal export
- GCP: the downloaded report is service-level totals only (no usage quantities).
  Re-export with SKU granularity: Billing -> Reports -> Group by: SKU -> download
  CSV. Note: Cloud Storage cost (46.89 USD) is mostly request charges from the
  metadata runs, not capacity -- the SKU breakdown will separate them.
