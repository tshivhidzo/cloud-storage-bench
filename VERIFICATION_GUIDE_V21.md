# Verification guide: v2.1 campaign (sweep-v2.1)

Audience: any reader verifying the archive against the revised manuscript
*Client-Concurrency Scaling of Managed Cloud Storage Across Five Public
Clouds: Separating Client and Service Limits* (Future Internet,
futureinternet-4640878). Each statement below gives the command that checks
it and the expected result.

Authoritative artefact: the repository at annotated tag `sweep-v2.1`
(github.com/tshivhidzo/cloud-storage-bench), version DOI `10.5281/zenodo.23434883`,
under the all-versions concept DOI 10.5281/zenodo.22032835. The earlier
(August 2026) campaign remains verifiable with `VERIFICATION_GUIDE.md`
(tag `sweep-v1-audited-r14`, version DOI 10.5281/zenodo.22681160), whose
content is unchanged in this release.

Environment used for the release: Python 3.10.12 with the packages in
`requirements-analysis.txt` (matplotlib 3.10.9). Run all commands from the
repository root.

## 1. The protocol preceded the measurements

```bash
git show -s --format='%ci %H' protocol-v2.1-locked
git log --format='%ci %s' --reverse sweep/run_rerun_v21.py | head -1
```

Expected: the tag `protocol-v2.1-locked` dates from 12 October 2026, before
the first run recorded in any manifest (earliest `ts_start` in
`results-rerun-v21/*/results-rerun-v21-*/run_manifest.jsonl`). Changes to
code after the tag are housekeeping (bucket emptying, the `--fb` option, the
D5 driver, analysis and paper scripts) and are described in
`sweep/DEVIATIONS_V21.md`.

## 2. Integrity of the data

```bash
(cd results-rerun-v21 && sha256sum -c --quiet manifest.sha256) && echo data-ok
(cd v21-output && sha256sum -c --quiet manifest.sha256) && echo outputs-ok
(cd paper-v21 && sha256sum -c --quiet manifest.sha256) && echo paper-ok
```

Expected: `data-ok`, `outputs-ok`, `paper-ok`. `results-rerun-v21/PROVENANCE.md`
lists the SHA-256 of each host-side archive and describes the one change made
to them (removal of credential identifiers).

## 3. Attempt accounting

```bash
python3 - <<'EOF'
import json, glob
att = ok = 0
for f in sorted(glob.glob('results-rerun-v21/*/results-rerun-v21-*/run_manifest.jsonl')):
    recs = [json.loads(l) for l in open(f) if l.strip()]
    runs = {r['run_id'] for r in recs}
    good = {r['run_id'] for r in recs if r['status'] == 'ok'}
    print(f.split('/')[1], len(runs), len(recs), len(good))
    att += len(recs) if 'mc2' not in f else 0
    ok += len(good) if 'mc2' not in f else 0
print('total attempts', att, 'accepted', ok)
EOF
```

Expected: 228 accepted runs from 233 attempts across the five providers, and
3 of 3 in `azure-mc2` (deviation D5). The five failed attempts are explained
in `sweep/DEVIATIONS_V21.md` (D1 to D3).

## 4. No credentials in the archive

```bash
grep -rlE 'LTAI[0-9A-Za-z]{8}|GOOG1[0-9A-Z]{8}|ASIA[0-9A-Z]{12}|AKIA[0-9A-Z]{12}' results-rerun-v21 | wc -l
grep -rhoE '"--s3(key|secret|sessiontoken)" "[^"]*"' results-rerun-v21 | sort | uniq -c
```

Expected: `0`, then only `"REDACTED"` values (150 keys, 36 session tokens).

## 5. Reproduce every v2.1 result

```bash
python3 sweep/analyze_v21.py --root results-rerun-v21 --out /tmp/v21-check
for f in v21-output/*.csv; do cmp "$f" "/tmp/v21-check/$(basename "$f")" && echo "same $(basename "$f")"; done

python3 sweep/make_v21_paper.py --v21 /tmp/v21-check \
  --d5 results-rerun-v21/azure-mc2 --v1 recompute-output \
  --manifests results-rerun-v21 --out /tmp/paper-check
for f in paper-v21/*.tex; do cmp "$f" "/tmp/paper-check/$(basename "$f")" && echo "same $(basename "$f")"; done
```

Expected: every CSV in `v21-output/` and every table and macro file in
`paper-v21/` reproduced byte for byte. The macro file `v21_macros.tex` holds
the values that the manuscript prints in its text; the tables are input by
the manuscript unchanged. Figures (`paper-v21/figures/*.png`) are regenerated
by the same command; PNG bytes can differ between matplotlib builds, so they
are compared visually rather than by hash.

## 6. Where each manuscript result comes from

| Manuscript item | Source in this archive |
|---|---|
| Table 5 (completion) | `paper-v21/tab_v21_completion.tex`, from the manifests |
| Table 6 (exponents, both intervals) | `paper-v21/tab_v21_exponents.tex`, from `v21-output/exponents.csv` |
| Table 7, Figure 2 (client vs service) | `tab_v21_clientservice.tex`, `ext128_multi.csv`, `cpu_cells.csv`, `azure-mc2/` |
| Table 8, Figure 3 (runner comparison) | `tab_v21_equiv.tex`, `equivalence.csv` |
| Table 9 (block vs documented limits) | `tab_v21_block.tex`, `runs.csv`; limits cited in the manuscript |
| Table 10, Figure 5 (earlier vs present) | `tab_v21_replication.tex`, `v21-output/exponents.csv`, `recompute-output/exponents_recomputed.csv` |
| Appendix A (network) | `tab_v21_network.tex`, `network.csv`, `netbaseline_*.json` |
| Appendix B (reservoir) | `tab_v21_reservoir.tex`, `reservoir.csv` |
| Deviations D1 to D5 | `sweep/DEVIATIONS_V21.md` |
| Earlier campaign values (Section 3, Appendix C) | `VERIFICATION_GUIDE.md` and `recompute-output/` (unchanged from r14) |

## 7. Artefact identity

The Zenodo deposit for this version is the byte-literal output of

```bash
TZ=Africa/Johannesburg git archive --format=zip \
  --prefix=cloud-storage-bench-thesis-v1/ sweep-v2.1 > sweep-v2.1-<shortsha>.zip
```

and its SHA-256 is published in the Zenodo record's description (it cannot be
recorded inside the tree it hashes).

## 8. Known limitations of the archive

The host-side archives with unredacted command lines are not published. The
iperf3 30-second runs are archived as per-run summaries only. The two Azure
hosts in D5 ran on different processor generations (see
`azure-mc2/lscpu_host*.txt`). Cloud billing exports for the v2.1 campaign are
not included.
