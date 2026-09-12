# Literature search log — 8 September 2026

Purpose: bounded, repeatable support for the manuscript's novelty statement
(Related Work). Engine: a web search index queried through the Anthropic
web-search tool. Domain restriction was REQUESTED per query (listed below);
the engine demonstrably did not apply it strictly, since records from
arxiv.org and image-ppubs.uspto.gov were returned alongside the requested
domains. All returned records are listed with their URLs regardless of
domain. Native ACM DL / IEEE Xplore search interfaces and Google Scholar
were NOT queried. Ten records were returned per query (30 in total).

Inclusion rule applied to title/abstract: client-side concurrency (thread or
parallelism) scaling of managed block, file AND object storage measured on
two or more public providers.

Screening codes: MET = meets rule; PART = meets part of the rule (retained as
comparator or context); EXCL = outside rule (reason given).

## Query 1 — requested domains: dl.acm.org, ieeexplore.ieee.org
"cloud storage benchmark concurrency scaling object block file multiple public cloud providers throughput threads"

| # | Record | URL | Decision |
|---|--------|-----|----------|
| 1 | Design and Implementation of a Concurrency Benchmark Tool for Cloud Storage Systems | https://ieeexplore.ieee.org/abstract/document/8791849/ | EXCL: consumer file-sync services (Dropbox, Box, OneDrive, Google Drive), not managed block/file/object |
| 2 | Agni: An Efficient Dual-access File System over Object Storage | https://dl.acm.org/doi/pdf/10.1145/3357223.3362703 | EXCL: system design over a single object backend |
| 3 | MOLNs: A cloud platform for interactive, reproducible and scalable spatial stochastic computational experiments | https://arxiv.org/pdf/1508.03604 | EXCL: application platform (outside requested domains) |
| 4 | A Comparative Taxonomy and Survey of Public Cloud Infrastructure Vendors | https://arxiv.org/pdf/1710.01476 | EXCL: survey without measurements (outside requested domains) |
| 5 | HVSTO: Efficient Privacy Preserving Hybrid Storage in Cloud Data Center | https://arxiv.org/pdf/1405.6200 | EXCL: not a measurement study (outside requested domains) |
| 6 | COSBench: cloud object storage benchmark (ICPE 2013) | https://dl.acm.org/doi/10.1145/2479871.2479900 | PART: object-only benchmark tool; retained comparator [cosbench] |
| 7 | COSBench: A Benchmark Tool for Cloud Object Storage Services (IEEE) | https://ieeexplore.ieee.org/abstract/document/6253618/ | PART: duplicate of #6 (earlier venue) |
| 8 | Performance analysis of mdx II: A next-generation cloud platform | https://arxiv.org/pdf/2502.10820 | EXCL: single private platform (outside requested domains) |
| 9 | System and method ... cloud score associated with resource usage (patent) | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11934885 | EXCL: patent (outside requested domains) |
| 10 | Reducing Failure Probability of cloud storage services using Multi-Clouds | https://arxiv.org/pdf/1310.4919 | EXCL: availability, not performance scaling (outside requested domains) |

## Query 2 — requested domains: dl.acm.org, ieeexplore.ieee.org
"cloud object storage throughput parallelism threads scaling measurement study client-side"

| # | Record | URL | Decision |
|---|--------|-----|----------|
| 1 | SteelDB: Diagnosing Kernel-Space Bottlenecks in Cloud OLTP Databases | https://arxiv.org/pdf/2603.29052 | EXCL: databases (outside requested domains) |
| 2 | An Empirical Evaluation of Serverless Cloud Infrastructure for Large-Scale Data Processing | https://arxiv.org/pdf/2501.07771 | EXCL: serverless compute (outside requested domains) |
| 3 | An Architecture for Memory Centric Active Storage (MCAS) | https://arxiv.org/pdf/2103.00007 | EXCL: architecture (outside requested domains) |
| 4 | Performance analysis of mdx II | https://arxiv.org/pdf/2502.10820 | EXCL: duplicate of Q1 #8 |
| 5 | Understanding I/O Performance Behaviors of Cloud Storage from a Client's Perspective (ACM TOS 2017) | https://dl.acm.org/doi/10.1145/3078838 | PART: client-side parallelism varied, object storage, single provider class; retained comparator [hou] |
| 6 | FAST CLOUD: Pushing the Envelope on Delay Performance of Cloud Storage with Coding | https://arxiv.org/pdf/1301.1294 | EXCL: coding/latency modelling (outside requested domains) |
| 7 | LibCOS: Enabling Converged HPC and Cloud Data Stores with MPI | https://dl.acm.org/doi/fullHtml/10.1145/3578178.3578236 | EXCL: HPC library over a single object backend |
| 8 | WOC: Dual-Path Weighted Object Consensus Made Efficient | https://arxiv.org/pdf/2512.20485 | EXCL: consensus protocol (outside requested domains) |
| 9 | Evolving the Cloud Block Store with Performance, Elasticity, Availability, and Hardware Offloading (ACM TOS) | https://dl.acm.org/doi/10.1145/3705925 | EXCL: single-provider block store architecture |
| 10 | A Ceph S3 Object Data Store for HEP | https://arxiv.org/pdf/2311.16321 | EXCL: on-premises Ceph (outside requested domains) |

## Query 3 — requested domains: dl.acm.org, ieeexplore.ieee.org, link.springer.com, usenix.org
"cross-provider cloud storage performance comparison block file object concurrency scaling exponent"

| # | Record | URL | Decision |
|---|--------|-----|----------|
| 1 | Design and Evaluation of a Simple Data Interface for Efficient Data Transfer Across Diverse Storage | https://arxiv.org/pdf/2009.03190 | EXCL: transfer interface; AWS–GCP network only (outside requested domains) |
| 2 | Demystifying Object-based Big Data Storage Systems | https://arxiv.org/pdf/2406.00550 | EXCL: on-premises object systems (outside requested domains) |
| 3 | MOLNs | https://arxiv.org/pdf/1508.03604 | EXCL: duplicate of Q1 #3 |
| 4 | CrossFS: Improving Cross-Domain File System Performance with CRDT-Based Metadata Synchronization (ACM TOS) | https://dl.acm.org/doi/10.1145/3777470 | EXCL: file-system design |
| 5 | Performance analysis of mdx II | https://arxiv.org/pdf/2502.10820 | EXCL: duplicate of Q1 #8 |
| 6 | Adaptive data striping and replication across multiple storage clouds (patent) | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9348840 | EXCL: patent (outside requested domains) |
| 7 | Offloading of remote service interactions to virtualized service devices (patent) | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12197397 | EXCL: patent (outside requested domains) |
| 8 | An In-depth Comparative Analysis of Cloud Block Storage Workloads: Findings and Implications (ACM TOS) | https://dl.acm.org/doi/fullHtml/10.1145/3572779 | PART: two providers, block only, trace analysis not benchmarking; context only |
| 9 | HVSTO | https://arxiv.org/pdf/1405.6200 | EXCL: duplicate of Q1 #5 |
| 10 | Cloud file transfers using cloud file descriptors (patent) | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12120172 | EXCL: patent (outside requested domains) |

## Totals (counted from the rows above)

30 returned; 0 MET; 4 PART (Q1 #6, Q1 #7 [duplicate of Q1 #6], Q2 #5, Q3 #8);
26 EXCL: 17 marked as outside the requested domains, 4 duplicates of other
returned records (all four also arXiv records outside the requested
domains, so 21 of the 26 lie outside them), and 5 in-domain records
excluded on scope (Q1 #1, #2; Q2 #7, #9; Q3 #4).

Additional comparators in the manuscript (CloudCmp, Schad et al., Iosup et
al., Uta et al., Jiang et al., Durner et al., CNSBench, Traeger et al.,
Bermbach et al., Leis & Kuschewski, Anna) were located by citation chasing
from these records and prior knowledge; their bibliographic details were
verified against the Crossref API on 24 August 2026.
