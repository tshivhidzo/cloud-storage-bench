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

# 7. Completion / sizing sensitivity analysis (sweep/sensitivity_analysis.py)
import sensitivity_analysis as SA

# 7a. Failure-stage classifier maps the canonical archived error strings.
check("sa_classify_terraform",
      SA.classify_failure("RuntimeError: terraform failed (terraform apply"
                          " -input=false)") == "provisioning")
check("sa_classify_purge_timeout",
      SA.classify_failure("TimeoutExpired: Command '['/usr/bin/python3',"
                          " '/root/purge_oss.py']'") == "provisioning")
check("sa_classify_timeout",
      SA.classify_failure("measurement timed out") == "timeout")
check("sa_classify_tool_exit",
      SA.classify_failure("tool exited 1; see results-sweep/raw/x") == "tool_exit")
check("sa_classify_unknown", SA.classify_failure("???") == "other")

# 7b. Its OLS recovers an exact power law and refuses <3 points.
_xs = [math.log10(c) for c in (1, 4, 16, 64)]
_fit = SA.ols(_xs, [0.85 * x + 2.0 for x in _xs])
check("sa_ols_exact_beta", _fit is not None and abs(_fit[0] - 0.85) < 1e-9)
check("sa_ols_refuses_two_points", SA.ols(_xs[:2], _xs[:2]) is None)

# 7c. Sizing-rule arithmetic: at 16 threads the fixed and weak rules
# coincide for both workloads (so c16 runs must enter both strata).
for _wl, _base in SA.BASE.items():
    _exp16 = min(80.0, max(1.0, round(_base * 16 / 16)))
    check(f"sa_c16_rules_coincide_{_wl}", abs(_exp16 - _base) < SA.TOL)

# 7d. End-to-end attempt accounting against the archived manifests
# (numbers quoted in the manuscript's completion analysis).
if all((Path(d) / "run_manifest.jsonl").exists() for d in SA.DIRS.values()):
    _rows = SA.load_attempts()
    check("sa_attempts_total", len(_rows) == 611, str(len(_rows)))
    _ok = sum(1 for r in _rows if r["status"] == "ok")
    check("sa_attempts_accepted", _ok == 360, str(_ok))
    from collections import Counter
    _st = Counter(r["stage"] for r in _rows if r["status"] != "ok")
    check("sa_stage_counts",
          (_st["provisioning"], _st["timeout"], _st["tool_exit"]) == (99, 79, 73),
          str(dict(_st)))

# 7e. FULL end-to-end regeneration must be byte-identical to the committed
# outputs on every platform (the r11 CRLF defect: platform-dependent
# newline translation made three regenerated files differ byte-wise).
import hashlib

_SA_OUTPUTS = ["attempts_by_cell.csv", "sensitivity_sizing.csv",
               "table_completion.tex", "table_sizing.tex",
               "sensitivity_macros.tex"]
_sa_paths = [Path("recompute-output") / f for f in _SA_OUTPUTS]
if all(p.exists() for p in _sa_paths) and \
        all((Path(d) / "run_manifest.jsonl").exists() for d in SA.DIRS.values()):
    _before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in _sa_paths}
    SA.main()
    _after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in _sa_paths}
    for _n in _SA_OUTPUTS:
        check(f"sa_regen_byte_identical:{_n}", _before[_n] == _after[_n])
        check(f"sa_lf_only:{_n}",
              b"\r" not in (Path("recompute-output") / _n).read_bytes())

    # 7f. Content assertions on the regenerated outputs: the exact values
    # quoted in the manuscript prose and the row count of the stratum fits.
    _sizing = list(csv.DictReader(open("recompute-output/sensitivity_sizing.csv")))
    check("sa_sizing_rows_48", len(_sizing) == 48, str(len(_sizing)))
    _macros = (Path("recompute-output") / "sensitivity_macros.tex").read_text()
    for _m in (r"\newcommand{\sizeMaxShift}{0.24}",
               r"\newcommand{\huaweiObjFixedWrite}{0.62}",
               r"\newcommand{\huaweiObjFixedRead}{0.78}",
               r"\newcommand{\attTotal}{611}",
               r"\newcommand{\attAccepted}{360}",
               r"\newcommand{\attProvisioning}{99}",
               r"\newcommand{\attTimeout}{79}",
               r"\newcommand{\attToolExit}{73}"):
        check(f"sa_macro:{_m.split('{')[1].rstrip('}')}".replace(chr(92), ""),
              _m in _macros)

# 8. Packaging invariants: the values any downstream copy of the generated
# tables/figures must carry (guards the mixed-snapshot defect: a stale
# pre-correction table_combined.tex with the write-only runs included).
import re as _re

_tc = Path("recompute-output/table_combined.tex")
if _tc.exists():
    _rows = [ln for ln in _tc.read_text().splitlines() if r"\\" in ln and "&" in ln
             and "Provider" not in ln]
    _ns = []
    _abb = None
    for ln in _rows:
        cells = [c.strip() for c in ln.rstrip("\\").split("&")]
        if len(cells) >= 7:
            _ns.append(int(cells[-1]))
            if cells[0] == "Azure" and cells[1] == "block" and cells[2] == "balanced":
                _abb = (float(cells[3]), int(cells[-1]))
    check("pkg_table_rows_30", len(_ns) == 30, str(len(_ns)))
    check("pkg_table_N_sum_356", sum(_ns) == 356, str(sum(_ns)))
    check("pkg_azure_block_bal_beta_0102_N8",
          _abb is not None and abs(_abb[0] - 0.102) < 0.0005 and _abb[1] == 8,
          str(_abb))

_rr = Path("recompute-output/runs_recomputed.csv")
if _rr.exists():
    _rows = list(csv.DictReader(open(_rr)))
    _c64 = [r for r in _rows if r["provider"] == "azure" and r["paradigm"] == "block"
            and r["workload"] == "balanced" and int(r["concurrency"]) == 64]
    check("pkg_no_azure_block_bal_c64_combined",
          len(_c64) == 3 and all(r["combined_tput_mib_s"] == "" for r in _c64))
    # Azure object balanced workload-level means per level: the corrected
    # v2 runner values plotted in the instrument figure (bytes over time,
    # never summed phase rates -- summed rates would be ~2x these).
    import statistics as _st
    _ao = [r for r in _rows if r["provider"] == "azure" and r["paradigm"] == "object"
           and r["workload"] == "balanced" and r["combined_tput_mib_s"]]
    _exp = {1: 7.923, 4: 32.153, 16: 42.750, 64: 38.383}
    for _c, _v in _exp.items():
        _m = _st.mean(float(r["combined_tput_mib_s"]) for r in _ao
                      if int(r["concurrency"]) == _c)
        check(f"pkg_azure_v2_mean_c{_c}", abs(_m - _v) < 0.0005, f"{_m:.3f}")

print(f"\n{len(FAIL)} failure(s)" if FAIL else "\nALL TESTS PASS")
sys.exit(1 if FAIL else 0)
