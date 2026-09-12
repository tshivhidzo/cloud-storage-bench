# Verification guide (r14)

Audience: any researcher, scholar or auditor verifying the archive against
the measurement manuscript. Purpose: every claim below is stated with the
exact command that verifies it and the expected output. Deviation from a
stated expected value is a reportable finding. This guide was rewritten in
full at r10; r11 added the completion and sizing sensitivity analyses
(Sections 0 and 11); r12 made those analyses byte-reproducible on every
platform and extended the container and the merged manifest to cover them;
r13 corrected release documentation only; r14 adds the peer-review
analyses (Section 11: completion probabilities, residual and lack-of-fit
diagnostics, time-limit and CPU-threshold refits, exclusive sizing strata,
full pooled-model output and a no-Azure sensitivity, all fitted under the
archived maximum-likelihood policy), archives exponents at five decimals,
draws individual repetitions in figure 1, records the literature-search
log, and adds a manuscript-to-archive path check (Section 12). r14 also
re-archives `boot_draws.csv` as regenerated from scratch in the pinned
container on the release machine: every numeric field reproduced the
r7-r13 file byte-for-byte, and only the reason strings of its three
rejected draws changed, because the committed file predated the r7
wording change (Section 7). No measurement data or primary statistical
result changed.

Authoritative artefact: the repository at annotated tag `sweep-v1-audited-r14`
(github.com/tshivhidzo/cloud-storage-bench), immutable version DOI
`10.5281/zenodo.22681160`, under the all-versions concept DOI
10.5281/zenodo.22032835. No measurement data or primary statistical
result has changed since r10; r14 re-archives the exponent tables and
`exponents_recomputed.csv` at five decimals (every value unchanged to the
three decimals previously archived) so that no interval displays as
zero-width.
Superseded tags, all preserved unchanged:
`sweep-v1`, `thesis-v1`, `sweep-v1-audited` (pre-remediation commit
c952e6ff), `sweep-v1-audited-r2` (failed publication attempt: tagged the r1
tree), `sweep-v1-audited-r3` (first complete publication; pre-round-3
statistics), `sweep-v1-audited-r4` (round-3 remediation, superseded before
release: placeholder version-DOI in the manuscript), `sweep-v1-audited-r5` (version DOI 10.5281/zenodo.22056327; superseded by
the round-5 bootstrap-validity remediation), `sweep-v1-audited-r6`
(version DOI 10.5281/zenodo.22057377; superseded by the round-6
artefact-identity remediation -- its deposit was not the literal tagged
tree and its metadata identified r5), `sweep-v1-audited-r7` (version
DOI 10.5281/zenodo.22057803; failed publication attempt: the tag captured
only file deletions while the deposit carried the remediated working tree),
`sweep-v1-audited-r8` (version DOI 10.5281/zenodo.22058064, commit
fe0dba4d; content boundary VALID -- extracted tag and deposit matched
file-for-file and hash-for-hash -- but the deposit was a re-zip rather than
the literal `git archive` output, and the record's version field was left
blank), and `sweep-v1-audited-r9` (version DOI 10.5281/zenodo.22075555,
commit 7d5f5a90; the FIRST byte-identical tag-to-DOI deposit -- superseded
only because its committed pooled_model.txt predated the zero-tolerance
policy wording and its record description carried the commit SHA where the
archive SHA-256 belonged), and `sweep-v1-audited-r10` (version DOI
10.5281/zenodo.22078882, commit c82a8686; the formally closed technical
audit baseline -- superseded only by the addition of the completion and
sizing sensitivity analyses required by the measurement-manuscript audit;
its data and statistical results are unchanged in r11), and
`sweep-v1-audited-r11` (version DOI 10.5281/zenodo.22086561, commit
0aece48d; added the completion and sizing sensitivity analyses -- superseded
because its three committed sensitivity text outputs carried
platform-dependent CRLF newlines and so were not byte-reproducible, its
container script and merged manifest did not cover the new outputs, and its
Section 9 still named the r10 tag), and `sweep-v1-audited-r12` (version
DOI 10.5281/zenodo.22100902, commit e58754d1; statistically valid and
byte-verified end to end -- superseded only for release documentation: its
CITATION.cff carried the previous day's release date, its Section 8 claimed
a manuscript statement that the final manuscript no longer contains, and
its Section 9 stated unqualified archive determinism when zip output is
timezone-dependent), and `sweep-v1-audited-r13` (version DOI
10.5281/zenodo.22101440, commit 6fea2f8a; release-documentation
corrections only -- superseded by the peer-review analyses of r14, whose
first draft exported REML and unconverged model fits, a defect caught in
review and corrected before this release with unconditional regression
gates). Verify against the r14 commit only; the
per-folder `manifest.sha256` files are the integrity ground truth
(Section 6). This guide's earlier versions are superseded in their
entirety.

Environment: Python 3.10.12, packages per `requirements-analysis.txt`
(numpy 2.2.6, pandas 2.3.3, scipy 1.15.3, statsmodels 0.14.6,
matplotlib 3.10.9); complete transitive lock in `requirements-lock.txt`.
Bootstrap draw-file BYTE-identity is guaranteed only inside the pinned
container (`Dockerfile`; single-threaded BLAS, locked dependencies) and
only on a CPU for which OpenBLAS selects the same kernel family as the
release run, because OpenBLAS chooses CPU-specific kernels at import time
and different kernels can differ in the last bits of floating-point
reductions. The r14 release run: Intel Core i7-5600U, OpenBLAS core type
`Haswell` (as printed by `OPENBLAS_VERBOSE=2 python3 -c "import numpy"`
inside the container), Docker Engine on WSL 2. Outside the container, or
on a CPU that selects another kernel family, mixed-model optimisation is
BLAS/threading-sensitive: expect statistical agreement of the bootstrap p
and of the draw accounting (204 attempts, 200 valid, 4 rejected), and
exact reproduction of everything else in the chain, which is
deterministic arithmetic.

## 0. Reproduce the entire results chain

```bash
python3 sweep/recompute_from_raw.py     # raw artefacts -> per-run/per-phase tables
python3 sweep/refit_exponents.py        # tables -> exponents + pooled model + LaTeX tables
python3 sweep/make_figures.py           # tables (+ quarantine) -> all four figure PNGs
python3 sweep/prose_numbers.py          # every prose-quoted statistic -> prose_numbers.txt
python3 sweep/sensitivity_analysis.py   # completion + sizing analyses (Section 11)
python3 sweep/review_analyses.py        # peer-review analyses + model output (Section 11)
python3 sweep/test_pipeline.py          # regression tests; exit 0 = all pass
python3 sweep/check_manuscript_paths.py <main.tex>   # every manuscript-named path exists (Section 12)
```

Or, for the guaranteed-bytewise environment:
`docker build -t csb . && docker run csb` -- the container's default command
(`sweep/container_verify.sh`) regenerates the ENTIRE chain including all
five bootstrap batches from scratch, the five sensitivity outputs and the
ten review-analysis outputs, and exits non-zero unless the regenerated
`boot_draws.csv`, sensitivity outputs and review outputs are all
byte-identical (SHA-256) to the committed ones. The base image is pinned to the linux/amd64 image digest (not the
multi-arch manifest list) in the Dockerfile, so the byte-identity claim is
tied to one concrete platform image and, for the draw file, to the CPU
kernel family recorded in the Environment note.

`refit_exponents.py` without `BOOT_B` reuses the archived bootstrap draw
file. To regenerate draws: truncate `recompute-output/boot_draws.csv`, then
run batches `BOOT_B=<n> BOOT_SEED=s python3 sweep/refit_exponents.py` for
s = 42, 43, 44, 45, 46 with accepted-draw counts 30, 50, 50, 50, 20
(archive totals: 204 attempts, 200 accepted). Bytewise identity of the
regenerated file is guaranteed inside the container on the release CPU
kernel family only (Environment note; Section 7 for the r14 regeneration).

Everything the manuscript reports comes from these scripts' outputs. The
manuscript's tables are `\input` copies of `recompute-output/table_combined.tex`,
`table_perop.tex`, `table_attempts.tex`, `table_completion.tex`,
`table_completionprob.tex`, `table_sizing.tex` and `table_pooledfe.tex`, and
its prose statistics enter via generated macros (`prose_macros.tex`,
`sensitivity_macros.tex`, `review_macros.tex`); its figures are the four PNGs `make_figures.py` writes
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
totals 611 attempts, 360 accepted. Manifests are append-only JSONL. All 360 accepted runs and all failures
that reached execution carry credential-masked command lines; 99 attempts
that failed BEFORE provisioning completed (e.g. Terraform bucket-deletion
conflicts) have no cmd field by construction -- their error field records
the provisioning failure instead.

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

Implementation: `sweep/refit_exponents.py::pooled_model` with the validity
policy in `_fit_model`/`_fit_pair`. Model: log10(combined) ~ log10(conc) x
C(paradigm) x C(workload), provider random intercept, N = 356. Policy, per
the round-5 audit requirements: each model (null and alternative) is fitted
with the full optimizer ladder (default, lbfgs, powell) and represented by
its highest FINITE converged log-likelihood -- a `.converged` flag alone is
insufficient; both models must yield one; nested ordering is
enforced with NO tolerance: any negative likelihood difference, of any
magnitude, rejects the draw (r7; previously a 1e-6 clamp existed and no
archived draw ever exercised it). LR values are therefore finite and
non-negative because only non-negative differences are accepted. Every
attempt is archived in `boot_draws.csv` (llf_null, llf_alt, per-model
optimizer, warning count, lr, accepted, reject_reason); the p-value uses
accepted draws only. The null baseline is the fixed-effects prediction
(exog @ fe_params), not `fittedvalues`.

Expected values at r10 (statistically identical to r6; the r7 policy change
-- rejecting rather than clamping sub-tolerance negative differences --
affected no archived draw):

```
Observed: llf_null=82.304605 (default), llf_alt=82.5265 (powell); LR = 0.4438
p (naive chi2_2)        = 0.8010
p (50:50 chi2 mixture)  = 0.6531
p (parametric bootstrap)= 0.5522   [204 attempts; 200 valid draws;
                                    4 rejected with recorded reasons]
```

The bootstrap p is corroborated by the round-5 audit's independent
finite-only diagnostic (~0.523). Byte-identity of `boot_draws.csv` under
regeneration holds inside the pinned container on the release CPU kernel
family; elsewhere, expect statistical agreement (see Environment note
above). The regression tests verify the policy directly: finite
likelihoods in all accepted rows, nested ordering, non-negative finite
LRs, reject reasons on all rejected rows, reject reasons that the current
writer can emit (`boot_reject_reasons_match_code`, r14), and that the
reported p-value equals the policy applied to the archived records.

Draw-file provenance, stated for the audit trail. The `boot_draws.csv`
committed from r7 through r13 was generated before the r7 change that
replaced the sub-tolerance clamp with unconditional rejection. That change
also renamed the rejection label from "nested ordering violated" to
"negative likelihood difference", but the draw file was not regenerated
afterwards, so its three rejected draws (seed 42 attempt 30, seed 44
attempt 28, seed 46 attempt 4) kept the old label. A full regeneration
necessarily rewrites those three strings, so the container's
BOOT-DRAWS-BYTE-IDENTICAL line was not attainable for the r7-r13 trees;
the numbers in those files were nevertheless correct, as the r14 run
shows. On 12 September 2026 the pinned container regenerated all 204
attempts from scratch on the machine described in the Environment note:
every `llf_null`, `llf_alt`, `lr`, optimizer choice, warning count and
accepted flag reproduced the committed file exactly (maximum absolute
difference 0.0 over all numeric fields), and the only differences were
the three label strings. r14 archives the regenerated file; the byte
gate therefore holds for r14 on that image and CPU, and the new test
above fails if the archived labels and the writer ever drift apart again. History for the audit trail: r1-r2 reported LR = 0.077 (defective
input) with a bootstrap that double-added random effects; r3 lacked
per-draw convergence checks; r5 accepted converged-flagged fits with
non-finite likelihoods. Each defect is documented in manuscript Section 4.4
and covered by a test.

## 8. Manuscript-to-archive tracing

The `manuscript/` directory holds the ACM-format manuscript audited through
r10. The Future Internet submission derives every generated input from the
same `recompute-output/` files (adding `table_completion.tex`,
`table_sizing.tex` and `sensitivity_macros.tex`, Section 11); its source is
submitted to the journal and is not part of this archive. Checks against
the archived manuscript:

```bash
diff manuscript/table_combined.tex recompute-output/table_combined.tex && \
diff manuscript/table_perop.tex   recompute-output/table_perop.tex && \
diff manuscript/table_attempts.tex recompute-output/table_attempts.tex && \
diff manuscript/prose_macros.tex  recompute-output/prose_macros.tex && echo GENERATED-INPUTS-IDENTICAL
python3 sweep/make_figures.py && git diff --stat -- manuscript/figures   # empty = figures reproduce
python3 sweep/prose_numbers.py && git diff --stat -- recompute-output/prose_numbers.txt  # empty = prose numbers reproduce
# From a DOI-only download (no git history), use content comparison instead:
#   cp -r manuscript/figures /tmp/committed_figs && python3 sweep/make_figures.py \
#     && diff -r /tmp/committed_figs manuscript/figures
grep -ci "pre-regist" manuscript/main.tex    # expect 0
```

`prose_numbers.txt` carries every prose-quoted statistic not in a table or
figure: the p99 fold changes, the 28-of-30 consistency result and its
geometric-mean ratio 1.08, the like-for-like Azure v1/v2 write comparison
(0.0008 vs 0.310; 2.36x at c16), the design-mix counts and the CPU-gate
count (71 of 360, 19.7%).

Every number in the manuscript is one of: (a) the two generated `\input`
tables; (b) a value printed by the pipeline scripts and quoted in prose,
regenerated by the commands above; (c) a configuration fact traceable to
`configs/AS_EXECUTED_CONFIG.md` (documentation URLs inline, unrecoverable
items marked) or `configs/host_state_extract.json`. There is no class (d).

## 9. Artefact identity (tag vs DOI deposit)

The Zenodo deposit is the byte-literal output of:

```bash
TAG=sweep-v1-audited-r14   # the authoritative tag named at the top of this guide
TZ=Africa/Johannesburg git archive --format=zip \
  --prefix=cloud-storage-bench-thesis-v1/ \
  $TAG > $TAG-<shortsha>.zip
```

Zip archive bytes depend on the archiving environment: file modification
times in zip entries are stored in local time, so the TZ variable above is
part of the release recipe (the deposits were generated under
Africa/Johannesburg; TZ=UTC provably yields a different SHA-256 for
identical content). Byte-identical regeneration is therefore claimed only
under the pinned timezone and a compatible Git/zlib generation; under any
other environment, verify content equivalence instead via the
path-inventory comparison below and the per-file checksums of Section 6.
Within the pinned environment this command regenerates
the deposit exactly. The deposit's SHA-256 cannot be recorded inside the
tree it hashes (self-reference); it is published in the Zenodo record's
description and in the release correspondence. Verification, byte level
first:

```bash
TAG=sweep-v1-audited-r14
TZ=Africa/Johannesburg git archive --format=zip \
  --prefix=cloud-storage-bench-thesis-v1/ \
  $TAG > /tmp/regen.zip
sha256sum /tmp/regen.zip <doi-download>.zip     # identical
cmp /tmp/regen.zip <doi-download>.zip && echo BYTE-IDENTICAL
unzip -z <doi-download>.zip                      # prints the peeled commit SHA
```

Inventory-level cross-check (prefix-consistent, files only):

```bash
git archive --format=tar --prefix=cloud-storage-bench-thesis-v1/ \
  $TAG | tar -t | grep -v '/$' | sort > /tmp/tag_paths.txt
unzip -Z1 <doi-download>.zip | grep -v '/$' | sort > /tmp/doi_paths.txt
diff /tmp/tag_paths.txt /tmp/doi_paths.txt && echo PATH-INVENTORY-IDENTICAL
```

The tracked tree contains no compiled bytecode and no retired outputs
(`git ls-files | grep -E '\.pyc$|boot_lr|exponents_table.tex'` returns
nothing). A DOI-only download has no git history; use the content
comparisons given in Sections 0 and 8 instead of git-based commands.

## 10. Open limitations, by design

1. The locked-protocol rerun (`sweep/SWEEP_PROTOCOL_V2.md`) is proposed,
   not executed; the study is framed as retrospective and exploratory.
2. Mechanism attributions are consistent-with hypotheses; no network or
   protocol instrumentation exists in this campaign.
3. Per-run instrument hashes absent (v2 protocol requirement).
4. Co-author review precedes any journal submission.

## 11. Completion and sizing sensitivity analyses (added at r11)

These support the measurement manuscript's completion analysis
(attempts/failures by stage, paradigm and concurrency) and its
sizing-stratified exponent refits. All outputs are regenerated
deterministically from the archived manifests and tables:

```bash
python3 sweep/sensitivity_analysis.py
```

Expected stdout, exactly:

```
attempts=611 accepted=360 failed=251 (prov=99 timeout=79 tool=73)
object exec failures by c: [22, 20, 44, 46]
sizing rows: 48
```

Outputs written to `recompute-output/`: `attempts_by_cell.csv` (attempts,
acceptances and per-stage failures by paradigm x workload x concurrency),
`table_completion.tex` (manuscript Table: attempts/accepted by paradigm and
concurrency with object execution-stage failures), `sensitivity_sizing.csv`
(all 48 stratum fits), `table_sizing.tex` (manuscript appendix table,
balanced class), and `sensitivity_macros.tex` (every prose-quoted number
from these analyses, including the maximum stratum-versus-pooled shift and
the Huawei fixed-stratum object exponents). Failure stages are classified
from the manifests' error strings: `terraform`/`TimeoutExpired` ->
provisioning, `measurement timed out` -> timeout, `tool exited` ->
tool_exit; the classifier, the counts above, end-to-end byte-identical
regeneration of all five outputs, their LF-only encoding, the 48-row fit
count and every prose-quoted macro value are covered by
`sweep/test_pipeline.py` (tests prefixed `sa_`). All five outputs are
written with explicit LF newlines on every platform (the r11 defect was
platform-dependent newline translation) and are listed in
`results-merged/manifest.sha256` (Section 6). Sizing strata: a run is in
the fixed-total stratum if its executed dataset matches 20 GB
(balanced) / 40 GB (large-object) and in the weak-scaled stratum if it
matches base x concurrency/16 capped at 80 GB; 16-thread runs satisfy both
rules and enter both strata; Azure object runs (duration-driven) enter
neither. A stratum cell is fitted only where >= 3 concurrency levels
remain.

### 11b. Peer-review analyses (added at r14)

```bash
python3 sweep/review_analyses.py
```

Expected: the printed macros include `reviewLlfNull = 82.304605`,
`reviewLlfAlt = 82.526500`, `reviewLR = 0.4438` (identical to Section 7's
primary fit), `noAzLR = 1.27`, `noAzP = 0.39`, `diagPeropCells = 45`,
`diagCombinedCells = 30`, `tlPhases = 60`, `tlPhasesHit = 4`,
`tlPhasesComplete = 56`, `sizeOverlapRuns = 84`, `sizeExclLost = 14`.
Every model fit is selected under the archived maximum-likelihood policy
(`reml=False`; best finite converged log-likelihood across the optimizer
ladder); `pooled_fit_flags.json` records method, convergence and
likelihood method per fit, and `sweep/test_pipeline.py` fails
unconditionally if that file or `pooled_model.txt` is missing or
unparseable, if any exported fit is unconverged or REML, or if the
likelihoods do not reproduce Section 7's. Outputs: `table_completionprob.tex`,
`table_pooledfe.tex`, `review_macros.tex`, `diagnostics_perop.csv`,
`diagnostics_combined.csv` (per-cell degrees of freedom, lack-of-fit F and
p, per-level residual spread with a near-zero flag, lag-1 autocorrelation,
run-level and level-mean interval half-widths), `completion_by_cell_full.csv`,
`timelimit_phases.csv` (byte-count completion ratio per time-limited
phase), `sizing_exclusion.csv` (kept/lost stratum cells under exclusive
assignment), `pooled_covariance.txt` (full-precision random-effects
covariance, implied correlation, eigenvalues) and `pooled_fit_flags.json`.
The literature-search log supporting the manuscript's novelty statement is
`configs/search_log_2026-09-08.md` (30 returned records with URLs and
screening decisions).

## 12. Manuscript-to-archive path check (added at r14)

```bash
python3 sweep/check_manuscript_paths.py <path-to-manuscript-main.tex>            # against the tree
python3 sweep/check_manuscript_paths.py <path-to-manuscript-main.tex> --zip <deposit>.zip   # against the deposit
```

Expected: `0 missing of N named paths` in both forms (N = 31 for the
Future Internet manuscript at r14). The script extracts every
`\texttt{...}` token in the manuscript that names a file or directory and
verifies its presence in the repository tree or in the entry list of the
`git archive` deposit, so the manuscript cannot name a file the published
archive does not contain.
