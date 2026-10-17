# Stage 2 and Supplementary Runs

In this lab you run the remaining planned measurements, check the two-client
runs, and add the two supplementary tests the campaign needed.

## Stage 2

Stage 2 holds file runs, the 128-thread level, the two-client runs and, on AWS,
the runner comparison and reservoir runs (AWS 36, Azure 15, GCP, Huawei and
Alibaba 18 each). **host 1**, window 0:

```bash
timeout 3 bash -c "</dev/tcp/$H2P/1611" && echo svc-ok      # not needed on Azure
python3 run_rerun_v21.py --provider <provider> --host2 $H2P --stage 2 --dry-run | head -1
python3 run_rerun_v21.py --provider <provider> --host2 $H2P --stage 2 2>&1 | tee -a rerun_<provider>_s2.log
```

Then `--resume` and `rerun_status.py` as in lab 7.

## Checking a two-client run

Both hosts must have written their share. The purge count after a
`-mc2` run says so directly:

```
purge: csb-bench-xxxx: 2621440 objects deleted     # 2 hosts x 64 threads x 20,480
```

GCP has no batch delete, so read the count from the Terraform teardown time or
the elbencho CSV instead. Large GCP object runs took about 8 hours each, almost
all of it Terraform deleting objects one by one.

## Fresh-bucket repeats (deviation D1)

The three Alibaba cells measured on a reused bucket are repeated once, as
supplementary runs with their own IDs. The `--fb` option builds only the runs
named, with unchanged parameters:

```bash
python3 run_rerun_v21.py --provider alibaba --host2 $H2P \
  --fb alibaba-object-balanced-c64-r1,alibaba-object-balanced-c16-r2,alibaba-object-balanced-c04-r2 \
  2>&1 | tee -a rerun_alibaba_fb.log
```

Expected purges: 1,310,720, 327,680 and 81,920 objects.

## Azure two-host test (deviation D5)

The runner comparison on AWS showed the Python runner becomes CPU-bound on a
4 vCPU host by 64 threads, and Azure ran at 100% CPU from 16 threads. Only a
second client can show whether Azure Blob or the client was the limit. Write
the design into the deviations log first, then:

**laptop**: give host 1 its own key to host 2 and copy the files.

```bash
for h in $H $H2; do
  scp "$ONE/sweep/azure_mc2.py" "$ONE/sweep/azure_blob_runner_v2.py" "$ONE/sweep/sweep_design_v21.py" \
      ubuntu@$h:~/cloud-storage-bench-thesis-v1/sweep/
done
ssh ubuntu@$H 'test -f ~/.ssh/id_ed25519 || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -q; cat ~/.ssh/id_ed25519.pub' \
  | ssh ubuntu@$H2 'cat >> ~/.ssh/authorized_keys && echo key-added'
```

**host 1**, window 0:

```bash
cd ~/cloud-storage-bench-thesis-v1/sweep && source ~/.bashrc
python3 azure_mc2.py --host2 $H2P --dry-run      # runner SHA-256 must match on both hosts
python3 azure_mc2.py --host2 $H2P 2>&1 | tee -a rerun_azure_mc2.log
lscpu > lscpu_host1.txt; ssh ubuntu@$H2P lscpu > lscpu_host2.txt
```

Each repetition provisions a fresh storage account, runs the unchanged runner at
64 threads on both hosts at once (separate containers), records mpstat on both,
and tears down. The connection string reaches host 2 only through `/dev/shm`.

Result: two hosts gave 1.78 times the write and 1.80 times the read throughput,
and host 1 delivered the same as alone. Host 2 had landed on an older
processor (E5-2673 v4 at 2.3 GHz against Platinum 8171M at 2.6 GHz), which
explains the shortfall from 2. The limit was the client.

Next: [Bringing the Results Home](10-bringing-results-home.md)
