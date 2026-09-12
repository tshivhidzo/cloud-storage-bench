#!/usr/bin/env bash
# Full-chain regeneration + byte-verification inside the pinned container.
set -e
sha256sum recompute-output/boot_draws.csv | awk '{print $1}' > /tmp/committed.sha
python3 sweep/recompute_from_raw.py
: > recompute-output/boot_draws.csv          # truncate: regenerate from scratch
BOOT_B=30 BOOT_SEED=42 python3 sweep/refit_exponents.py > /dev/null
BOOT_B=50 BOOT_SEED=43 python3 sweep/refit_exponents.py > /dev/null
BOOT_B=50 BOOT_SEED=44 python3 sweep/refit_exponents.py > /dev/null
BOOT_B=50 BOOT_SEED=45 python3 sweep/refit_exponents.py > /dev/null
BOOT_B=20 BOOT_SEED=46 python3 sweep/refit_exponents.py
python3 sweep/make_figures.py
python3 sweep/prose_numbers.py > /dev/null
# Sensitivity analyses: regenerate and byte-verify all five outputs.
SA_FILES="recompute-output/attempts_by_cell.csv recompute-output/sensitivity_sizing.csv recompute-output/table_completion.tex recompute-output/table_sizing.tex recompute-output/sensitivity_macros.tex"
sha256sum $SA_FILES > /tmp/sa_committed.sha
python3 sweep/sensitivity_analysis.py
if sha256sum -c /tmp/sa_committed.sha; then echo "SENSITIVITY-OUTPUTS-BYTE-IDENTICAL"; else echo "SENSITIVITY-OUTPUTS-DIFFER (defect inside the container; reportable)"; exit 1; fi
# Review analyses (r14): regenerate and byte-verify all outputs, including the
# model fits selected under the archived ML policy.
RV_FILES="recompute-output/table_completionprob.tex recompute-output/table_pooledfe.tex recompute-output/review_macros.tex recompute-output/diagnostics_perop.csv recompute-output/diagnostics_combined.csv recompute-output/completion_by_cell_full.csv recompute-output/timelimit_phases.csv recompute-output/sizing_exclusion.csv recompute-output/pooled_covariance.txt recompute-output/pooled_fit_flags.json"
sha256sum $RV_FILES > /tmp/rv_committed.sha
python3 sweep/review_analyses.py > /dev/null
if sha256sum -c /tmp/rv_committed.sha; then echo "REVIEW-OUTPUTS-BYTE-IDENTICAL"; else echo "REVIEW-OUTPUTS-DIFFER (defect inside the container; reportable)"; exit 1; fi
python3 sweep/test_pipeline.py
NEW=$(sha256sum recompute-output/boot_draws.csv | awk '{print $1}')
OLD=$(cat /tmp/committed.sha)
echo "committed boot_draws sha: $OLD"
echo "regenerated boot_draws sha: $NEW"
if [ "$NEW" = "$OLD" ]; then echo "BOOT-DRAWS-BYTE-IDENTICAL"; else echo "BOOT-DRAWS-DIFFER (defect inside the container; reportable)"; exit 1; fi
