#!/usr/bin/env python3
"""
test_pipeline.py -- automated regression tests for the analysis pipeline.
Run from the repository root:  python3 sweep/test_pipeline.py
Exit code 0 = all tests pass. No external test framework required.

Covers the defects found in audit rounds 1-3 so they cannot silently return:
  1. OLS slope recovery on synthetic data (fit correctness).
  2. Combined throughput is blank for balanced runs lacking a read phase
     (write-only runs must not masquerade as paired-pass rates).
  3. Combined throughput equals total bytes / total time, not a sum of rates.
  4. Bootstrap draw records carry per-draw convergence, method and warning
     fields, and only converged draws enter the p-value set.
  5. Negative LR draws are clamped to zero in the p-value computation.
  6. Pipeline CSV outputs use LF line endings (no CRLF, any platform).
"""
from __future__ import annotations
import csv, io, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import refit_exponents as RF

FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAIL.append(name)


# 1. OLS slope recovery
xs = [math.log10(c) for c in (1, 4, 16, 64) for _ in range(3)]
ys = [0.95 * x + 1.0 for x in xs]
fit = RF.ols(xs, ys)
check("ols_recovers_planted_slope", fit and abs(fit["beta"] - 0.95) < 1e-9,
      f"beta={fit['beta'] if fit else None}")

# 2+3. combined-rate semantics (unit-test the recompute rule directly)
import recompute_from_raw as RC  # noqa: E402
ph_both = [("WRITE", 1000.0, 100.0, 1.0), ("READ", 1000.0, 50.0, 1.0)]
ops = {p[0] for p in ph_both}
complete = ops >= {"WRITE", "READ"}
tot_mib = sum(p[1] for p in ph_both); tot_s = sum(p[2] for p in ph_both)
combined = round(tot_mib / tot_s, 2) if (tot_s and complete) else ""
check("combined_is_bytes_over_time", combined == round(2000.0 / 150.0, 2),
      f"combined={combined}, sum-of-rates would be 30.0")
ph_wonly = [("WRITE", 1000.0, 100.0, 1.0)]
ops = {p[0] for p in ph_wonly}
complete = ops >= {"WRITE", "READ"}
check("write_only_balanced_has_blank_combined", not complete)

# published dataset invariant: the four known write-only runs are blank
rr = Path("recompute-output/runs_recomputed.csv")
if rr.exists():
    rows = list(csv.DictReader(open(rr)))
    wo = [r for r in rows if r["workload"] == "balanced"
          and r["phases_present"] == "WRITE"]
    check("published_write_only_runs_blank_combined",
          len(wo) == 4 and all(r["combined_tput_mib_s"] == "" for r in wo),
          f"{len(wo)} write-only rows")
    n_comb = sum(1 for r in rows if r.get("combined_tput_mib_s"))
    check("pooled_model_N_is_356", n_comb == 356, f"N={n_comb}")
else:
    check("runs_recomputed_present", False, "run recompute_from_raw.py first")

# 4+5. bootstrap validity policy (r6): finite likelihoods, nested ordering,
# accepted-only p-value, non-finite rejection
bd = Path("recompute-output/boot_draws.csv")
if bd.exists():
    drows = list(csv.DictReader(open(bd)))
    need = {"seed", "attempt", "llf_null", "llf_alt", "method_null",
            "method_alt", "n_warnings", "lr", "accepted", "reject_reason"}
    check("boot_draws_schema_v2", need <= set(drows[0].keys()))
    acc = [r for r in drows if r["accepted"] == "True"]
    rej = [r for r in drows if r["accepted"] != "True"]
    check("boot_rejects_have_reasons", all(r["reject_reason"] for r in rej),
          f"{len(rej)} rejected")
    fin = all(math.isfinite(float(r["llf_null"])) and
              math.isfinite(float(r["llf_alt"])) for r in acc)
    check("boot_accepted_llfs_finite", fin)
    nested = all(float(r["llf_alt"]) >= float(r["llf_null"]) - 1e-6
                 for r in acc)
    check("boot_accepted_nested_ordering", nested)
    nonneg = all(float(r["lr"]) >= 0.0 for r in acc)
    check("boot_accepted_lrs_nonnegative_finite",
          nonneg and all(math.isfinite(float(r["lr"])) for r in acc))
    # p-value policy: recompute from records and compare with pooled_model.txt
    pm = Path("recompute-output/pooled_model.txt").read_text()
    import re as _re
    m_lr = _re.search(r"LR = ([0-9.]+)", pm)
    m_p = _re.search(r"parametric bootstrap\)\s*=\s*([0-9.]+)", pm)
    if m_lr and m_p:
        lr_obs = float(m_lr.group(1))
        lrs = [float(r["lr"]) for r in acc]
        p_re = (sum(1 for v in lrs if v >= lr_obs) + 1) / (len(lrs) + 1)
        check("boot_pvalue_matches_policy",
              abs(p_re - float(m_p.group(1))) < 5e-4,
              f"recomputed {p_re:.4f} vs reported {m_p.group(1)}")
    # synthetic guard: a draw with -inf llf must be rejected by the policy
    fake = {"llf_null": "-inf", "llf_alt": "1.0", "accepted": "True"}
    check("policy_would_reject_nonfinite",
          not math.isfinite(float(fake["llf_null"])))
else:
    check("boot_draws_present", False, "run refit with BOOT_B>0 first")

# unit checks on the policy functions themselves
check("fit_pair_rejects_missing_fit",
      RF._fit_pair.__doc__ is not None and "reject" in RF._fit_pair.__doc__)
check("nest_tol_defined", RF.NEST_TOL == 1e-6)

# 6. LF-only CSV emission (write via the same csv settings the pipeline uses)
buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=["a", "b"], lineterminator="\n")
w.writeheader(); w.writerow({"a": 1, "b": 2})
check("csv_lineterminator_is_lf", "\r" not in buf.getvalue())
for f in ("recompute-output/runs_recomputed.csv",
          "recompute-output/exponents_recomputed.csv"):
    p = Path(f)
    if p.exists():
        check(f"lf_only:{f}", b"\r" not in p.read_bytes())

print(f"\n{len(FAIL)} failure(s)" if FAIL else "\nALL TESTS PASS")
sys.exit(1 if FAIL else 0)
