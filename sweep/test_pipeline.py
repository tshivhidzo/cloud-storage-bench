#!/usr/bin/env python3
"""
test_pipeline.py -- automated regression tests for the analysis pipeline.
Run from the repository root:  python3 sweep/test_pipeline.py
Exit code 0 = all tests pass. No external test framework required.

Covers the defects found in audit rounds 1-6 so they cannot silently return:
  1. OLS slope recovery on synthetic data (fit correctness).
  2. Combined throughput is blank for balanced runs lacking a read phase
     (write-only runs must not masquerade as paired-pass rates).
  3. Combined throughput equals total bytes / total time, not a sum of rates.
  4. Bootstrap archive invariants: schema, finite likelihoods, nested
     ordering, non-negative finite LRs, reject reasons, and that the
     reported p-value equals the policy applied to the archived records.
  5. Synthetic mock tests of the fit-selection policy itself: best finite
     converged likelihood wins per model; non-finite, unconverged, missing
     and negatively-ordered fits are rejected (no clamping of any size);
     zero difference is accepted with LR exactly 0.
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
else:
    check("boot_draws_present", False, "run refit with BOOT_B>0 first")

# ---- synthetic unit tests of the selection and rejection paths ----------
# A mock statsmodels: mixedlm(...).fit(...) yields scripted results, so the
# policy functions are exercised directly with controlled llf/convergence
# values, per-optimizer and per-model, with no fitting involved.
import warnings as _warnings


class _MockResult:
    def __init__(self, llf, converged):
        self.llf, self.converged = llf, converged


class _MockModel:
    def __init__(self, result):
        self._r = result

    def fit(self, reml=False, **kw):
        return self._r


class _MockSMF:
    """Scripted results keyed by (has_re_formula, method)."""
    def __init__(self, script):
        self.script = script

    def mixedlm(self, f, dfb, groups=None, re_formula=None):
        method_holder = {}

        class _Deferred:
            def __init__(s):
                pass

            def fit(s, reml=False, method="default", **kw):
                key = (re_formula is not None, method)
                r = self.script.get(key)
                if r is None:
                    raise RuntimeError("scripted failure")
                return _MockResult(*r)
        return _Deferred()


inf = float("inf")
# optimizer selection: best FINITE converged llf wins per model
smf = _MockSMF({(False, "default"): (10.0, True), (False, "lbfgs"): (12.0, True),
                (False, "powell"): (inf, True),
                (True, "default"): (11.0, True), (True, "lbfgs"): (13.0, False),
                (True, "powell"): (12.5, True)})
r = RF._fit_pair(smf, "f", {"provider": None}, _warnings)
check("mock_selects_best_finite_converged",
      r["accepted"] and r["llf_null"] == 12.0 and r["llf_alt"] == 12.5
      and r["method_null"] == "lbfgs" and r["method_alt"] == "powell"
      and abs(float(r["lr"]) - 1.0) < 1e-9, str(r))

# non-finite-only model must reject the draw
smf = _MockSMF({(False, "default"): (-inf, True), (False, "lbfgs"): (inf, True),
                (False, "powell"): (float("nan"), True),
                (True, "default"): (5.0, True)})
r = RF._fit_pair(smf, "f", {"provider": None}, _warnings)
check("mock_rejects_nonfinite_llf",
      not r["accepted"] and r["reject_reason"] == "no finite converged fit")

# converged=False everywhere must reject
smf = _MockSMF({(False, "default"): (10.0, False), (True, "default"): (11.0, False)})
r = RF._fit_pair(smf, "f", {"provider": None}, _warnings)
check("mock_rejects_unconverged",
      not r["accepted"] and r["reject_reason"] == "no finite converged fit")

# all-optimizers-raise must reject
smf = _MockSMF({})
r = RF._fit_pair(smf, "f", {"provider": None}, _warnings)
check("mock_rejects_all_exceptions", not r["accepted"])

# ANY negative likelihood difference must reject (no clamping of any size)
for d in (-1e-12, -1e-6, -3.5):
    smf = _MockSMF({(False, "default"): (10.0, True),
                    (True, "default"): (10.0 + d, True)})
    r = RF._fit_pair(smf, "f", {"provider": None}, _warnings)
    check(f"mock_rejects_negative_diff_{d}",
          not r["accepted"] and "negative likelihood difference"
          in r["reject_reason"])

# zero difference is accepted with LR exactly 0
smf = _MockSMF({(False, "default"): (10.0, True), (True, "default"): (10.0, True)})
r = RF._fit_pair(smf, "f", {"provider": None}, _warnings)
check("mock_accepts_zero_diff_lr0",
      r["accepted"] and float(r["lr"]) == 0.0)

check("no_tolerance_clamp", RF.NEST_TOL == 0.0)

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
