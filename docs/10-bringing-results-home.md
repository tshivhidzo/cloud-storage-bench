# Bringing the Results Home

In this lab you pack each provider's results on its host, copy them to the
laptop, and check them before anything is destroyed.

## Pack on host 1

```bash
cd ~/cloud-storage-bench-thesis-v1/sweep
python3 rerun_status.py --provider <provider> --host2 $H2P > status_<provider>_final.txt
NB=$(find .. -maxdepth 2 -name 'netbaseline_<provider>*.json'); echo "$NB"
tar czf rerun_<provider>.tgz results-rerun-v21-<provider> rerun_<provider>_s*.log status_<provider>_final.txt $NB
sha256sum rerun_<provider>.tgz
```

Alibaba also adds `rerun_alibaba_fb.log`; the Azure two-host test is packed
separately as `rerun_azure_mc2.tgz` with the two `lscpu` files.

## Copy to the laptop

```bash
scp ubuntu@$H:~/cloud-storage-bench-thesis-v1/sweep/rerun_<provider>.tgz ~/publish/
cp ~/publish/rerun_<provider>.tgz "$ONE/"
sha256sum ~/publish/rerun_<provider>.tgz "$ONE/rerun_<provider>.tgz"
```

All three checksums (host, laptop, synced copy) must match.

## Check before teardown

Extract each archive and confirm, run by run:

- every planned run has a data file, a stdout log and an mpstat file;
- the mpstat file covers all four cores;
- the elbencho SHA-256 is the same in every record;
- teardown is `ok` (or explained in the deviations log).

`sweep/analyze_v21.py` does this as part of lab 11. Do not destroy a provider's
hosts until its archive has passed: the hosts are the only place the data
exists until then.

> Two findings at this step changed the paper. Block and file runs at
> 64 threads were write-only on four providers, as the protocol allows, which
> left those read fits with three thread levels. And elbencho had written the
> S3 access-key identifier, and on AWS a session token, into every object CSV
> (lab 13 removes them).

Next: [Analysis](11-analysis.md)
