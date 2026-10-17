# Fundamentals: The Scripts From First Principles

The labs use scripts, because 233 attempts across five clouds cannot be run by
hand. This section takes each script apart and does its job manually, once, so
that you know exactly what it measures and could rebuild it without the
repository. Each page ends by naming the script that automates what you just
did, so you can read its code with the manual version in mind.

Do these on one provider (AWS is the simplest: no keys on the host) with one
client host up, after lab 5.

1. [One Measurement by Hand](F1-one-run-by-hand.md): provision a target, drop
   caches, warm up, measure, record CPU, tear down, for block, file and object
   storage. *Automated by* `scripts/provision.py`, `scripts/runners.py`,
   `sweep/run_rerun_v21.py`.
2. [The Design and the Orchestrator](F2-design-and-orchestrator.md): how 228
   runs are derived from five rules, shuffled, staged, retried and stopped.
   *Automated by* `sweep/sweep_design_v21.py`, `sweep/run_rerun_v21.py`,
   `sweep/rerun_status.py`.
3. [Object Storage Over the S3 API](F3-object-storage.md): endpoints,
   addressing styles, signing, and emptying a bucket with `DeleteObjects`.
   *Automated by* `sweep/purge_s3.py`.
4. [Telemetry and the Network](F4-telemetry-and-network.md): what `mpstat`
   reports, how busy time is computed per core, and what iperf3 measures.
   *Automated by* `sweep/netbaseline.sh` and the telemetry in
   `run_rerun_v21.py`.
5. [Two Clients and the Runner Test](F5-two-clients-and-runner.md): elbencho's
   distributed mode, the SDK runner's design, and the logic that separates a
   client limit from a service limit. *Automated by* `sweep/s3_equiv_runner.py`,
   `sweep/azure_blob_runner_v2.py`, `sweep/azure_mc2.py`.
6. [The Statistics](F6-statistics.md): the scaling exponent, both confidence
   intervals and the ratios, computed by hand from the raw CSV files.
   *Automated by* `sweep/analyze_v21.py`, `sweep/make_v21_paper.py`.
7. [Provenance and Release](F7-provenance.md): hashes, manifests, redaction and
   a byte-reproducible archive. *Automated by* `scripts/release_v21.sh`.

Back to the [labs](../../README.md).
