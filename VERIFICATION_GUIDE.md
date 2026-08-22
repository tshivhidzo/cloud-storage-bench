# Verification guide (r4)

Audience: the auditor of the TOS manuscript and its companion archive.
Purpose: every claim below is stated with the exact command that verifies it
and the expected output. Deviation from a stated expected value is a
reportable finding. This guide is rewritten in full at r4; earlier guide
versions contained stale values from before the round-3 corrections and are
superseded in their entirety.

Authoritative artefact: the repository at annotated tag `sweep-v1-audited-r4`
(github.com/tshivhidzo/cloud-storage-bench) and its matching Zenodo version.
Superseded tags `sweep-v1`, `thesis-v1`, `sweep-v1-audited` (pre-remediation
commit c952e6ff), `sweep-v1-audited-r2` (failed publication attempt: tagged
the r1 tree) and `sweep-v1-audited-r3` (first complete publication; carries
the pre-round-3 statistics) are preserved unchanged. Verify against the r4
commit only; the per-folder `manifest.sha256` files are the integrity ground
truth (Section 6).

Environment: Python 3.10+, packages per `requirements-analysis.txt`
(numpy 2.2.6, pandas 2.3.3, scipy 1.15.3, statsmodels 0.14.6).

## 0. Reproduce the entire results chain

```bash
python3 sweep/recompute_from_raw.py     # raw artefacts -> per-run/per-phase tables
python3 sweep/refit_exponents.py        # tables -> exponents + pooled model + LaTeX tables
python3 sweep/make_figures.py           # tables (+ quarantine) -> all four figure PNGs
python3 sweep/test_pipeline.py          # regression tests; exit 0 = all pass
```

`refit_exponents.py` without `BOOT_B` reuses the archived bootstrap draw
file; to regenerate the draws from scratch, delete
`recompute-output/boot_draws.csv` and run five batches:
`BOOT_B=40 BOOT_SEED=s python3 sweep/refit_exponents.py` for s = 42..46.
The archived draw file reproduces exactly under those seeds.

Everything the manuscript reports comes from these scripts' outputs. The
manuscript's tables are `\input` copies of `recompute-output/table_combined.tex`
and `table_perop.tex`; its figures are the four PNGs `make_figures.py` writes
to `manuscript/figures/`. If any regenerated output differs from the
committed copy, the manuscript is wrong and that is a reportable defect.

## 1. Attempt accounting

```bash
for p in aws azure gcp huawei alibaba; do
  echo -n "$p: "; wc -l < results-sweep-$p/run_manifest.jsonl | tr -d ' '
  echo -n " attempts, "; grep -c '"status": "ok"' results-sweep-$p/run_manifest.jsonl
done
```

Expected: aws 85/72, azure 114/72, gcp 104/72, huawei 81/72, alibaba 227/72;
totals 611 attempts, 360 accepted. Manifests are append-only JSONL with full
credential-masked command lines for every attempt.

## 2. Phase-level dataset

```bash
tail -n +2 recompute-output/per_phase.csv | wc -l        # expect 536
python3 - <<'EOF'
import csv
rows = list(csv.DictReader(open("recompute-output/runs_recomputed.csv")))
wo = [r["run_id"] for r in rows if r["workload"]=="balanced"
      and r["phases_present"]=="WRITE"]
print("write-only balanced runs:", sorted(wo))
print("their combined values blank:",
      all(r["combined_tput_mib_s"]=="" for r in rows if r["run_id"] in wo))
print("runs with a defined combined rate:",
      sum(1 for r in rows if r["combined_tput_mib_s"]))   # expect 356
EOF
```

Expected: the four azure block balanced runs (c16-r3, c64-r1/r2/r3),
blank combined values, and N = 356. Combined throughput is total MiB over
total elapsed seconds and exists only where the workload's full measured
phase set is present; per-phase p99 comes from per-phase tool output and is
never aggregated across phases. Spot-check one run end to end:

```bash
grep -A20 "^WRITE" results-sweep-aws/raw/aws-object-balanced-c16-r1.stdout.log | head -25
python3 -c "
import csv
r=[x for x in csv.DictReader(open('recompute-output/per_phase.csv'))
   if x['run_id']=='aws-object-balanced-c16-r1']
[print(x['op'], x['mib'], x['elapsed_s'], x['tput_mib_s'], x['lat_p99_ms']) for x in r]"
```

## 3. As-executed design audit

```bash
python3 - <<'EOF'
import csv
rows = list(csv.DictReader(open("recompute-output/runs_recomputed.csv")))
base={"balanced":20,"largeobj":40}; f=s=o=0
for r in rows:
    c=int(r["concurrency"]); wl=r["workload"]
    ds=float(r["dataset_gb_executed"]) if r["dataset_gb_executed"] else None
    if ds is None: o+=1; continue
    exp=min(80,max(1,round(base[wl]*c/16)))
    if abs(ds-base[wl])<1.5 and c!=16: f+=1
    elif abs(ds-exp)<1.5: s+=1
    else: o+=1
print(f"fixed={f} weak-scaled={s} time-driven/other={o}")  # expect 174/162/24
n=sum(1 for r in csv.DictReader(open('recompute-output/design_audit.csv'))
      if r['mixed_sizing_within_cell']=='True')
print("mixed-sizing cells:", n)   # expect 12 (parse the column; a raw grep
                                  # for 'True' matches other columns too)
EOF
python3 -c "
import json
t=l=0
for p in ['aws','azure','gcp','huawei','alibaba']:
    for line in open(f'results-sweep-{p}/run_manifest.jsonl'):
        try: r=json.loads(line)
        except: continue
        if r.get('status')=='ok' and r.get('paradigm') in ('block','file'):
            t+=1; l+= '--timelimit' in r.get('cmd','')
print(f'{l} of {t} accepted block/file runs with --timelimit')"   # expect 35/240
```

## 4. Quarantine

```bash
ls quarantine/azure-object-v1-runner/raw | wc -l
ls quarantine/alibaba-public-endpoint/raw | wc -l                 # expect 42
grep -c 'oss-me-central-1.aliyuncs.com' results-sweep-alibaba/run_manifest.jsonl
# public-endpoint records in the published manifest are failed attempts only:
python3 -c "
import json
ok=[json.loads(l) for l in open('results-sweep-alibaba/run_manifest.jsonl')
    if l.strip() and 'aliyuncs' in l]
ok=[r for r in ok if r.get('status')=='ok' and 'oss-me-central-1.aliyuncs.com' in r.get('cmd','')]
print('accepted public-endpoint runs in published manifest:', len(ok))"   # expect 0
```

The quarantined Alibaba manifest contains one malformed JSONL record (host
crash mid-append), preserved as found: quarantined artefacts are historical
evidence and are never sanitised. The v1 Azure figure regenerates from
`quarantine/azure-object-v1-runner/all_runs.csv` via `make_figures.py`.
Known residual gap (disclosed in the manuscript): per-run instrument hashes
were not recorded in this campaign; protocol v2 adds them.

## 5. Credential hygiene

```bash
grep -rlE "IQoJ[A-Za-z0-9/+=]{20,}" . | wc -l                     # expect 0
grep -rloE '\-\-s3(key|secret|sessiontoken)"? "?[A-Za-z0-9/+=]{16,}' . | grep -v REDACTED | wc -l   # expect 0
```

## 6. Checksum integrity

```bash
# Per-folder manifests: paths relative to their own folder.
for d in results-aws results-azure results-gcp results-huawei results-alibaba \
         results-sweep-aws results-sweep-azure results-sweep-gcp \
         results-sweep-huawei results-sweep-alibaba; do
  echo -n "$d: "; (cd $d && sha256sum -c manifest.sha256 2>/dev/null | grep -c FAILED)
done
# Merged manifest: paths relative to the REPOSITORY ROOT -- verify from the
# root, never from inside results-merged/.
sha256sum -c results-merged/manifest.sha256 2>/dev/null | grep -c FAILED
```

Expected: 0 everywhere. All text artefacts are committed and hashed as LF
bytes; `.gitattributes` (`* -text`) prevents any translation, and the
pipeline emits LF explicitly (`lineterminator="\n"`), so regenerated CSVs
hash identically to committed ones on any platform (regression-tested in
`sweep/test_pipeline.py`). Host-generated manifests over pre-redaction
originals are preserved beside each folder's manifest as
`manifest.sha256.original-unredacted`.

## 7. Statistical model

Implementation: `sweep/refit_exponents.py::pooled_model`. Model:
log10(combined) ~ log10(conc) x C(paradigm) x C(workload), provider random
intercept, N = 356. Both the observed statistic and every bootstrap draw are
fitted under a documented optimizer retry ladder (default, lbfgs, powell);
a draw enters the p-value only if both fits converge, and every draw's LR,
convergence flag, optimizer and warning count are archived in
`recompute-output/boot_draws.csv`. Negative LR draws (the expected point
mass at the variance boundary) are clamped to zero for the p-value, which
is conservative; raw values are retained in the records. The bootstrap
null baseline is the fixed-effects prediction (exog @ fe_params), not
`fittedvalues`.

Expected values at r4:

```
Observed fit: converged=True via optimizer=powell; LR = 0.4438
p (naive chi2_2)        = 0.8010
p (50:50 chi2 mixture)  = 0.6531
p (parametric bootstrap)= 0.4030   [200 draws; 200 converged; 0 rejected;
                                    60 negative LRs clamped]
```

Optimizer dependence is real at this group count (bootstrap p moves by
roughly 0.05-0.10 across optimizer choices); the manuscript discloses it
and rests no conclusion on bootstrap precision. History for the audit
trail: r1-r2 reported LR = 0.077 (defective input: four write-only runs in
the combined rate) and a bootstrap that double-added random effects; r3
reported LR = 0.444 with a bootstrap lacking per-draw convergence checks.
Both defects are documented in manuscript Section 4.4 and covered by
regression tests.

## 8. Manuscript-to-archive tracing

The manuscript source is `manuscript/` inside this repository. Checks:

```bash
diff manuscript/table_combined.tex recompute-output/table_combined.tex && \
diff manuscript/table_perop.tex   recompute-output/table_perop.tex && echo TABLES-IDENTICAL
python3 sweep/make_figures.py && git diff --stat -- manuscript/figures   # empty = figures reproduce
grep -ci "pre-regist" manuscript/main.tex    # expect 0
```

Every number in the manuscript is one of: (a) the two generated `\input`
tables; (b) a value printed by the pipeline scripts and quoted in prose,
regenerated by the commands above; (c) a configuration fact traceable to
`configs/AS_EXECUTED_CONFIG.md` (documentation URLs inline, unrecoverable
items marked) or `configs/host_state_extract.json`. There is no class (d).

## 9. Open limitations, by design

1. The locked-protocol rerun (`sweep/SWEEP_PROTOCOL_V2.md`) is proposed,
   not executed; the study is framed as retrospective and exploratory.
2. Mechanism attributions are consistent-with hypotheses; no network or
   protocol instrumentation exists in this campaign.
3. Per-run instrument hashes absent (v2 protocol requirement).
4. Co-author review precedes any journal submission.
