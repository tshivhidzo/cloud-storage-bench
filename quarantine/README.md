# Quarantined datasets (defective-instrument evidence)

Nothing here contributes to any reported result. These artefacts are retained
because the paper discloses the instrument corrections and the evidence must
be auditable.

## azure-object-v1-runner/
Azure Blob object measurements taken with the v1 SDK runner (batch-barrier
submission + single-process GIL serialisation). Its rise-then-fall throughput
curve is an instrument artifact; the corrected v2.3 runner remeasured all
Azure object cells. Contains the campaign-snapshot manifest, consolidated
table and the object raw artefacts.

## alibaba-public-endpoint/
Alibaba OSS object runs recorded OK against the PUBLIC regional endpoint,
whose Internet-gateway bandwidth cap (measured 12 MiB/s vs several hundred
MB/s via the internal endpoint) makes them measurements of the network path,
not the storage service. Contains the pre-quarantine manifest and the raw
artefacts of the affected runs. All object results in the reported dataset
use the internal endpoint, recorded per run in its archived command line.
