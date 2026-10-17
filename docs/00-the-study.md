# The Study Behind This Guide

This guide is the practical record of a research programme, not a
stand-alone benchmark. Read this page first: it explains where the harness
came from, what each campaign was for, which papers and conferences it fed,
and why the October 2026 campaign that the labs walk through was designed the
way it was.

## The research question

Organisations choosing managed cloud storage usually compare block, file and
object services at one level of client parallelism. The programme asked two
questions in turn:

1. **What does each paradigm deliver, on each provider, at a fixed level of
   parallelism, and at what cost?** (the MTech study)
2. **How does that performance change as the client raises its concurrency,
   and is any limit in the client or in the service?** (the journal paper)

## The arc, from thesis to journal revision

### 1. MTech thesis (2026)

The harness began as the measurement instrument for the first author's MTech
in Information Technology at the Cape Peninsula University of Technology,
supervised by Dr Boniface Kabaso: *Performance Evaluation of Object, Block and
File Storage Systems on Public Cloud Platforms*. The design documents
(`ARCHITECTURE.md`, `HARNESS_RUNBOOK.md`, `HARDWARE_AND_PLACEMENT.md`,
`ACCESS_AND_AUTH.md`) date from May to July 2026; the harness, Terraform
modules and pipeline were built by July. The thesis campaign measured the
three paradigms on AWS, Azure, Google Cloud, Huawei Cloud and Alibaba Cloud at
16 client threads, with costs, and established that provider identity is a
first-order effect. The thesis went through supervisor and language-editor
review and was finalised for examination in August 2026. Its dataset was
prepared for deposit in CPUT's eSango repository (September to October 2026,
pending repository access).

### 2. Conference papers (2025 to 2026)

The thesis work produced two conference papers:

- **SAFER-TEA 2025**: *Performance Evaluation of Object, Block and File
  Storage Systems on Public Cloud Platforms*, submitted with its camera-ready
  version prepared in August 2026; not yet published.
- **ICSSA 2026** (IEEE): *A Unified Methodology for Cross-Provider Performance
  and Cost Evaluation of Cloud Storage Paradigms for Sensor-Data Workloads*,
  accepted on 10 August 2026 and presented remotely on 23 September 2026
  (the conference ran on 22 and 23 September), with the committee's formatting corrections and IEEE PDF
  eXpress certification completed by 29 September. (The faculty did not
  support the registration fee; the timeline of that request is documented
  separately, and the lesson is in the appendix.)

### 3. The concurrency-scaling paper and the earlier campaign (August 2026)

The thesis deliberately fixed parallelism at 16 threads. The follow-up paper
asked how performance grows from 1 to 64 threads. A journal skeleton and
analysis plan were written on 15 August 2026 (first aimed at the *Journal of
Cloud Computing*), and the **earlier campaign** ran in August: 360 designed
runs, two workloads (balanced and large-object), five providers.

That campaign taught most of what this guide now prevents. It needed 611
attempts for 360 accepted runs; object-run completion fell from 0.58 to 0.39
across the thread range; the procedure was corrected four times mid-campaign;
dataset sizing mixed three rules; runs were not shuffled; only all-core CPU
was recorded; network limits were documented, not measured; and two
instruments misled before they were caught (a batching Azure runner whose
curve looked like service saturation, and a public Alibaba endpoint capped by
the host's 100 Mbit/s setting). Every attempt was kept, and the archive went
through fourteen audited releases on Zenodo (concept DOI
10.5281/zenodo.22032835; final earlier version r14, 10.5281/zenodo.22681160,
12 September 2026).

Manuscripts were also prepared for *Concurrency and Computation: Practice
and Experience* and *ACM Transactions on Storage* (20 to 22 August). They
were not submitted and await co-author feedback; the paper was submitted to
**Future Internet** (MDPI). A companion methodology paper,
*Auditable Cloud Benchmarking*, was drafted on 24 August and is on hold.

### 4. Future Internet: review and major revision (August to October 2026)

The manuscript went through three rounds of supervisor review (8 September,
12 September and 3 October) and was submitted to the Future Internet special
issue *Cloud Computing and HPC Advances for Next Generation Internet* on
5 October 2026 (manuscript futureinternet-4640878). On 10 October the journal
returned a **major revision**. All three reviewers found the work careful and
transparent; their concerns were that conditions changed during collection,
that completion fell with concurrency, that a single 4 vCPU client could not
separate client from service limits, that network limits were not measured,
and that Azure, the outlier, was measured with a different tool. Two of them
recommended a uniform rerun.

### 5. The October 2026 campaign: the subject of these labs

With the deadline extended to 30 October and a costed plan sent to the
supervisor and head of department, the study was rerun from 12 to 17 October
under a protocol tagged before the first run, with every control the reviewers
asked for. It produced 228 accepted runs from 233 attempts, five logged
deviations, and a supplementary Azure two-host test. The findings:

- object storage throughput grew close to proportionally with threads on all
  five clouds (exponents 0.922 to 0.981 for the four elbencho-measured
  services), and the earlier object results replicated to within 0.10;
- the Azure "outlier" was the client: a second host raised throughput 1.8-fold
  with the first host unchanged;
- entry-tier block volumes read at their documented limits from four threads;
  short block writes ran faster than sustained ones;
- limits outside the client appeared only for GCP writes and Huawei object
  storage.

The revised manuscript, *Client-Concurrency Scaling of Managed Cloud Storage
Across Five Public Clouds: Separating Client and Service Limits*, presents the
method as the contribution, summarises the earlier campaign and its
limitations, and cites the released dataset (10.5281/zenodo.23434883). It is
with the supervisor for review before resubmission by 30 October 2026.

## How the pieces relate

| Output | Campaign | Parallelism | Status (17 October 2026) |
|---|---|---|---|
| MTech thesis | thesis campaign | 16 threads | finalised for examination; eSango deposit pending access |
| SAFER-TEA 2025 paper | thesis campaign | 16 threads | submitted; not yet published |
| ICSSA 2026 paper (IEEE) | thesis campaign | 16 threads | presented remotely 23 September; final manuscript corrected |
| Earlier dataset, r14 | August 2026 | 1 to 64 threads | published, 10.5281/zenodo.22681160 |
| Future Internet paper | October 2026 (earlier as replication) | 1 to 128 threads, 1 to 2 hosts | in revision, resubmission by 30 October |
| Dataset sweep-v2.1 | October 2026 | 1 to 128 threads | published, 10.5281/zenodo.23434883 |
| CCPE and ACM TOS manuscripts | August 2026 | 1 to 64 threads | prepared, not submitted; awaiting co-author feedback |
| Auditable Benchmarking paper | both | n/a | draft, on hold |

Next: [Prerequisites](01-prerequisites.md)
