# v2.1 rerun runbook (Future Internet futureinternet-4640878, due 30 October 2026)

Protocol: `sweep/SWEEP_PROTOCOL_V2_1_AMENDMENT.md` on top of the locked
`sweep/SWEEP_PROTOCOL_V2.md`. Orchestrator: `sweep/run_rerun_v21.py`.
Progress and gates: `sweep/rerun_status.py`.

## Calendar

| Dates | What |
|---|---|
| Mon 12 to Tue 13 Oct | Credentials checked, protocol committed and tagged, first provider up |
| Tue 13 to Wed 14 Oct | All five providers up and stage 1 launched |
| Wed 14 to Sat 17 Oct | Stage 1 completes and retries; stage 2 starts provider by provider |
| Tue 20 Oct, 23:59 SAST | Stopping rule: no run starts after this (built into the code) |
| Wed 21 Oct | Everything torn down and leak-checked; results brought home |
| 21 to 24 Oct | Analysis, figures, tables (I do this as each provider's data arrives) |
| 24 to 27 Oct | Manuscript revision and response letter |
| 27 to 29 Oct | Dr Kabaso reviews |
| Fri 30 Oct | Resubmit in SuSy |

The run is split into two stages so that whatever happens, the paper's main
findings are covered first. Stage 1 is object and block storage, 24 runs per
provider (120 in total). Stage 2 is file storage, the 128-thread level, the
two-client runs and the AWS runner comparison.

| Provider | Stage 1 | Stage 2 | Total |
|---|---|---|---|
| AWS | 24 | 36 (12 file, 3 at 128 threads, 3 two-client, 12 runner, 6 reservoir) | 60 |
| Azure | 24 | 15 (12 file, 3 at 128 threads) | 39 |
| GCP | 24 | 18 (12 file, 3 at 128 threads, 3 two-client) | 42 |
| Huawei | 24 | 18 | 42 |
| Alibaba | 24 | 18 | 42 |

Estimated cloud cost: roughly USD 500 to 750 (about R8,300 to R12,400) in
total, mostly object storage request charges. Set a budget alert on each
account before launching.

## Rules that do not change

- Credentials live only in the shell of the machine that uses them. Never in
  a file under OneDrive, never in a commit, never pasted into chat.
- Every attempt is logged. Failed runs are retried with `--resume`, at most
  twice each; a run that fails three times is a disclosed blank.
- Tear down and leak-check each provider as soon as it is finished.

## Step 0. Readiness questions (I ask these per provider; answer yes or no only)

AWS: `aws sts get-caller-identity` works and shows the August account;
af-south-1 enabled; budget alert set.

Azure: `az account show` shows the August subscription, state Enabled; quota
for two Standard_D4s_v3 VMs (8 vCPU) in southafricanorth.

GCP: `gcloud auth list` and `gcloud config get project` show the August
account and project, billing enabled; a NEW HMAC key created after August.

Huawei: console login works, account unrestricted; a NEW AK/SK created after
August; EVS, SFS Turbo and OBS still activated in af-south-1.

Alibaba: LTAI AccessKey rotated after August; ECS, NAS and OSS still
activated in me-central-1; account verification still valid.

## Step 1. Commit and tag the protocol before any run (once)

On your laptop, in Git Bash:

```bash
cd ~/publish/cloud-storage-bench-thesis-v1
git pull --ff-only origin main
ONE="/c/Users/Tshivhidzo/OneDrive - Cape Peninsula University of Technology/Thesis/2026/cloud-storage-bench"
for f in sweep/SWEEP_PROTOCOL_V2_1_AMENDMENT.md sweep/sweep_design_v21.py \
         sweep/run_rerun_v21.py sweep/s3_equiv_runner.py sweep/purge_s3.py \
         sweep/rerun_status.py sweep/netbaseline.sh \
         scripts/host_up.sh terraform/hosts/aws/main.tf RERUN_V21_RUNBOOK.md \
         terraform/hosts/aws/second_client.tf terraform/hosts/azure/second_client.tf \
         terraform/hosts/gcp/second_client.tf terraform/hosts/huawei/second_client.tf \
         terraform/hosts/alibaba/second_client.tf; do
  cp "$ONE/$f" "$f"
done
git status --short                       # GATE: exactly these 16 paths, nothing else
python3 sweep/run_rerun_v21.py --provider aws --host2 10.0.0.2 --dry-run --stage 1 | head -2
                                         # GATE: "v2.1 plan for aws: 24 runs"
git add -A
git commit -m "v2.1 rerun: protocol amendment (staged, stop 20 Oct), orchestrator, runners, purge, status, second client"
git tag -a protocol-v2.1-locked -m "v2.1 protocol fixed before the first run"
git push origin main protocol-v2.1-locked
git ls-remote --tags origin | grep protocol-v2.1     # GATE: tag is on GitHub
```

Paste me the output of the last line. Its timestamp in the GitHub tag is the
evidence that the protocol was fixed before measurement.

## Step 2. Bring up both client hosts for one provider

In a fresh Git Bash window, set that provider's credentials in this window
only (as you did in August), then:

```bash
cd ~/publish/cloud-storage-bench-thesis-v1
export AUTO_SHUTDOWN_HOURS=0       # the campaign outlives the default 8-hour timer
export SECOND_CLIENT=true
./scripts/host_up.sh aws           # azure / gcp / huawei / alibaba (gcp also needs GCP_PROJECT)
```

Write down the four addresses it prints: first host public IP (`H1`), second
host public IP (`H2`), second host private IP (`H2P`).

If `terraform apply` fails on `second_client.tf`, paste me the error; the
second-host Terraform has not been run against a live account before.

## Step 3. Copy the harness to both hosts; start the second host's services

```bash
H1=<first host public ip>; H2=<second host public ip>; H2P=<second host private ip>
scp -r ~/publish/cloud-storage-bench-thesis-v1 ubuntu@$H1:~/cloud-storage-bench
scp -r ~/publish/cloud-storage-bench-thesis-v1 ubuntu@$H2:~/cloud-storage-bench
ssh ubuntu@$H2 'sudo apt-get install -y iperf3 && iperf3 -s -D && elbencho --service && nproc'
```

GATE: the last line prints `4`. On Azure leave out `&& elbencho --service`
(the second Azure host is only the iperf3 server).

## Step 4. On the first host: checks, network baseline, dry run

```bash
ssh ubuntu@$H1
tmux new -s rerun
cd ~/cloud-storage-bench
nproc                                              # GATE: 4
sudo apt-get install -y iperf3
python3 scripts/auth_preflight.py --providers aws --strict          # GATE: ready
bash sweep/netbaseline.sh aws $H2P                 # GATE: send and receive medians printed
cd sweep
python3 run_rerun_v21.py --provider aws --host2 $H2P --dry-run --stage 1   # GATE: 24 runs
```

(Set `H2P` again inside the host shell: `H2P=<second host private ip>`.)

Provider-specific shell setup before the dry run:

- GCP, Huawei, Alibaba: export the S3 block for that provider from
  `JOURNAL_SWEEP_RUNBOOK.md` in this tmux shell. For Alibaba it must be the
  `oss-me-central-1-internal.aliyuncs.com` endpoint; the orchestrator refuses
  to start otherwise.
- Huawei and Alibaba: also export the provider credentials Terraform reads
  (`HW_ACCESS_KEY`/`HW_SECRET_KEY`, `ALICLOUD_ACCESS_KEY`/`ALICLOUD_SECRET_KEY`).
- Azure: run the `host_env_setup` commands from `terraform output` (on the
  laptop, in `terraform/hosts/azure`) on the host, so the managed identity is used.
- AWS: nothing; the instance role is used.

## Step 5. Launch stage 1

```bash
python3 run_rerun_v21.py --provider aws --host2 $H2P --stage 1 2>&1 | tee -a rerun_aws_s1.log
```

Detach with Ctrl-b then d. Reattach any time with `tmux attach -t rerun`.

After the first object run finishes, run this in a second tmux window
(Ctrl-b then c) and paste me the output:

```bash
cd ~/cloud-storage-bench/sweep && python3 rerun_status.py --provider aws --host2 $H2P
```

## Step 6. Close stage 1, then stage 2

When stage 1 ends:

```bash
python3 run_rerun_v21.py --provider aws --host2 $H2P --stage 1 --resume 2>&1 | tee -a rerun_aws_s1.log
python3 rerun_status.py --provider aws --host2 $H2P     # GATE: stage 1 "to run 0"
python3 run_rerun_v21.py --provider aws --host2 $H2P --stage 2 2>&1 | tee -a rerun_aws_s2.log
```

Then the same `--resume` and status check for stage 2. After the first
two-client run on each provider, tell me; I will give you the one-line
listing that confirms both hosts wrote their own objects.

The code stops starting new runs after 20 October, 23:59 SAST. If it stops
there, that is the protocol working, not a fault.

## Step 7. Bring the results home and tear down the same day

On the first host:

```bash
cd ~/cloud-storage-bench/sweep
python3 rerun_status.py --provider aws --host2 $H2P > status_aws_final.txt
tar czf rerun_aws.tgz results-rerun-v21-aws rerun_aws_s*.log status_aws_final.txt
exit
```

On the laptop:

```bash
scp ubuntu@$H1:~/cloud-storage-bench/sweep/rerun_aws.tgz ~/publish/
ssh ubuntu@$H2 'pkill iperf3; elbencho --quit --hosts localhost' || true
./scripts/teardown_all.sh aws
./scripts/leak_check.sh                 # GATE: nothing listed for aws
unset SECOND_CLIENT
```

Close the window to clear the credentials.

## Step 8. Hand over

Tell me which provider is done and that `rerun_<provider>.tgz` is in
`~/publish/`. Copy it into the OneDrive `cloud-storage-bench` folder so I can
read it, and I will parse it and start the analysis while the others finish.
