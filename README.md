# cloud-bench: A Step-by-Step Guide to Auditable Cloud Storage Benchmarking Across Five Public Clouds

This guide walks you through measuring how managed cloud storage scales with
client concurrency on five public clouds, using cloud-bench, the open harness
of the `cloud-storage-bench` repository, and doing by hand what the harness
automates. It is not a one-click benchmark. It is the practical record of a
research programme at the Cape Peninsula University of Technology that began as an MTech thesis on block,
file and object storage, produced two conference papers (SAFER-TEA 2025 and
ICSSA 2026), and led to a journal paper on concurrency scaling, *Client-
Concurrency Scaling of Managed Cloud Storage Across Five Public Clouds:
Separating Client and Service Limits* (Future Internet, in revision).

The labs follow the October 2026 campaign that answered that paper's major
revision. Every step it actually took is written down, including the ones that
went wrong, and each is tied back to the shortcoming of the earlier work that
made it necessary, so that you understand why each part of the method exists
and can reproduce or extend it. Start with [The Study Behind This
Guide](docs/00-the-study.md).

> The campaign described here cost about USD 500 to 750 in cloud charges and
> took six days of measurement. Read the whole guide before you create
> anything, and set a budget alert on every account.

## Target audience

Researchers and engineers who want to run a cross-provider storage
measurement campaign whose results will survive peer review: fixed protocol,
complete attempt accounting, separation of client limits from service limits,
and an archive that a stranger can verify.

## Campaign details

The campaign measures block, file and object storage on AWS, Microsoft Azure,
Google Cloud, Huawei Cloud and Alibaba Cloud from one 4 vCPU client host per
provider (plus a second host for two-client runs), with a sequential 64 KiB
write-then-read workload at 1, 4, 16, 64 and 128 client threads.

| Component | Version or product |
|---|---|
| Benchmark tool | elbencho 3.1-1 (block, file, S3-compatible object) |
| Azure Blob runner | `sweep/azure_blob_runner_v2.py` (Python SDK, process pool) |
| Infrastructure | Terraform 1.x, one module per provider for hosts and for storage |
| Telemetry | sysstat `mpstat -P ALL 5`, iperf3 |
| Analysis | Python 3.10, numpy, matplotlib |
| Laptop | Windows 10 with Git Bash (any Unix shell works) |
| Hosts | Ubuntu 22.04, 4 vCPU / 16 GB: m5.xlarge, D4s_v3, e2-standard-4, c6.xlarge.4, ecs.hfg6.xlarge |
| Regions | af-south-1, southafricanorth, africa-south1, af-south-1, me-central-1 |

## Where things live

This guide is kept on its own branch, `cloud-bench-guide`, so that it can be
revised without touching the code or the archived data. The code, protocol and
results it refers to are on the `main` branch of
`github.com/tshivhidzo/cloud-storage-bench`, and the exact state used in the
October 2026 campaign is the tag `sweep-v2.1`, archived at DOI
10.5281/zenodo.23434883. Lab 1 shows how to clone it.

| What | Where |
|---|---|
| This guide | branch `cloud-bench-guide` |
| Harness, protocol, analysis scripts | branch `main` |
| Code and data as released | tag `sweep-v2.1`; Zenodo DOI 10.5281/zenodo.23434883 |

## Labs

0. [The Study Behind This Guide](docs/00-the-study.md)
1. [Prerequisites](docs/01-prerequisites.md)
2. [Credentials](docs/02-credentials.md)
3. [Locking the Protocol](docs/03-locking-the-protocol.md)
4. [Provisioning the Client Hosts](docs/04-provisioning-hosts.md)
5. [Preparing the Hosts](docs/05-preparing-hosts.md)
6. [Measuring the Network Baseline](docs/06-network-baseline.md)
7. [Stage 1: Object and Block Runs](docs/07-stage-1.md)
8. [Troubleshooting a Running Campaign](docs/08-troubleshooting.md)
9. [Stage 2 and Supplementary Runs](docs/09-stage-2-and-supplementary.md)
10. [Bringing the Results Home](docs/10-bringing-results-home.md)
11. [Analysis](docs/11-analysis.md)
12. [Tables, Figures and the Manuscript](docs/12-manuscript.md)
13. [Releasing the Dataset](docs/13-release.md)
14. [Cleaning Up](docs/14-cleanup.md)

## Fundamentals

The labs use scripts. [Fundamentals: The Scripts From First
Principles](docs/fundamentals/README.md) takes each one apart and does its job
by hand, once, so that you understand what is measured and could rebuild it:

- [F1. One Measurement by Hand](docs/fundamentals/F1-one-run-by-hand.md)
- [F2. The Design and the Orchestrator](docs/fundamentals/F2-design-and-orchestrator.md)
- [F3. Object Storage Over the S3 API](docs/fundamentals/F3-object-storage.md)
- [F4. Telemetry and the Network](docs/fundamentals/F4-telemetry-and-network.md)
- [F5. Two Clients and the Runner Test](docs/fundamentals/F5-two-clients-and-runner.md)
- [F6. The Statistics](docs/fundamentals/F6-statistics.md)
- [F7. Provenance and Release](docs/fundamentals/F7-provenance.md)

A record of every deviation, and what it taught us, is in
[Appendix: Lessons Learned](docs/appendix-lessons.md).

## Conventions

- Commands marked **laptop** run in Git Bash on your own machine, inside the
  clone `~/publish/cloud-storage-bench-thesis-v1`.
- Commands marked **host 1** or **host 2** run on a provider's first or second
  client host, inside `~/cloud-storage-bench-thesis-v1`.
- `<provider>` is one of `aws`, `azure`, `gcp`, `huawei`, `alibaba`.
- `H`, `H2` and `H2P` are host 1's public IP, host 2's public IP and host 2's
  private IP, read from `terraform output`.

## Acknowledgement and licence

The lab-by-lab format, in which each step is done by hand before it is
automated, follows Kelsey Hightower's *Kubernetes The Hard Way*. The content,
method and data are those of the cloud-bench study.

The text of this guide is licensed CC BY 4.0 (see [LICENSE.md](LICENSE.md)).
The code on the `main` branch is licensed MIT.
