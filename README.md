# cloud-storage-bench

Reproducible cross-cloud storage benchmarking harness for the thesis: block,
file and object storage across AWS, Azure, GCP, Huawei and Alibaba, measured with
one tool (elbencho) through one execution path into one 26-field dataset
(`all_runs.csv`). FIO is an independent cross-check on block runs; an Azure Blob
SDK runner covers the one non-S3 object service.

This is the **runnable implementation** of the harness described in the project's`HARNESS_RUNBOOK.md`, `ARCHITECTURE.md`, `HARDWARE_AND_PLACEMENT.md`
and `ACCESS_AND_AUTH.md`. Those documents are the design; this folder is the code
that executes it.

## Start here

Read **`QUICKSTART_WINDOWS.md`** — the step-by-step for driving the campaign from
a Windows 10 laptop against per-provider Ubuntu hosts.

## The one rule

**Report what you measured.** Missing metrics are left blank and flagged, never
invented. `consolidate.py` writes a completeness report stating the real N. A
smaller complete-and-real dataset beats a full-looking fabricated one — that is
the whole reason this harness exists.

## Layout

```
cloud-storage-bench/
  README.md
  QUICKSTART_WINDOWS.md        step-by-step for your Windows-driven topology
  scripts/
    design.py                  single source of truth: 225-run design + 26-field schema
    run_campaign.py            orchestrator (provision -> measure -> teardown)
    runners.py                 builds/executes elbencho (+azure/fio) commands
    provision.py               one interface over the per-provider Terraform modules
    parse_results.py           raw tool output -> 26-field all_runs.csv (never invents)
    auth_preflight.py          verify secure access per provider (stores no secrets)
    network_probe.py           latency/hops/locality + line speed
    azure_blob_runner.py       object runner for Azure Blob (non-S3)
    fio_crosscheck.py          validate elbencho against FIO on block runs
    add_costs.py               real billing export -> normalised cost columns
    consolidate.py             merge fragments + manifest + completeness report
    figure_style.py            Times New Roman / grayscale style for thesis figures
    host_up.sh                 provision one provider's benchmark VM, wait for readiness
    host_down.sh               destroy that host and its VPC
    teardown_all.sh            destroy storage targets + hosts, every provider
    leak_check.sh              list anything still running (i.e. still billing)
    cloudinit/bootstrap_host.sh  host bootstrap: tools, SDKs, auto-shutdown
  configs/
    credentials.env.example    env-var contract (copy locally, never commit)
    targets.example.csv        endpoints + local/offshore classification
    focus_costs.example.csv    shape of your real billing export
    elbencho/NOTES.md          elbencho install + flag notes
  terraform/
    README.md                  module contract + per-provider completeness status
    aws/  azure/  gcp/  huawei/  alibaba/     storage targets (block/file/object)
    hosts/                     the benchmark VMs themselves
      aws/  azure/  gcp/  huawei/  alibaba/
  results/                     outputs land here (git-ignored)
```

## Provisioning the benchmark hosts

```bash
./scripts/host_up.sh aws            # dedicated VPC, least-privilege role, auto-shutdown
./scripts/host_down.sh aws          # destroy host + VPC
./scripts/teardown_all.sh           # everything, every provider
./scripts/leak_check.sh             # verify nothing is still billing
```

Hosts run in local African regions where they exist (AWS af-south-1, Azure
southafricanorth, GCP africa-south1, Huawei af-south-1). Alibaba has no African
region, so its host is `me-central-1` and is labelled **offshore** — a real
limitation to disclose, not to hide.

## Pipeline

```
auth_preflight -> network_probe -> run_campaign -> parse_results
              -> fio_crosscheck -> add_costs -> consolidate -> completeness_report
```

## Honesty properties built into the code

- `parse_results.py` writes a blank cell (plus a note in `parse_notes.txt`) for
  any metric absent from the raw output — no zeros, no interpolation.
- `run_campaign.py` records every attempt (`run_manifest.jsonl`); failed runs
  produce no raw output, so their cells stay blank by construction.
- `consolidate.py` counts real coverage against the 225-cell design and lists the
  missing cells.
- `add_costs.py` refuses to run without your real billing export; it prices
  nothing itself.
- Every raw artefact and the merged CSV are SHA-256 checksummed in
  `manifest.sha256`.
