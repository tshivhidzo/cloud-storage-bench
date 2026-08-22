#!/usr/bin/env python3
"""
make_figures.py -- generates every manuscript figure from the recomputed
tables (and, for the instrument-correction figure, the quarantined v1 data),
completing the raw-to-figure audit chain:

    raw artefacts -> recompute_from_raw.py -> refit_exponents.py -> THIS
                  -> manuscript/figures/*.png

Outputs (deterministic filenames, referenced by manuscript/main.tex):
    manuscript/figures/fig1_recomputed.png
    manuscript/figures/fig2_recomputed.png
    manuscript/figures/fig3_azure_instrument.png
    manuscript/figures/fig4_recomputed_p99.png
Run from the repository root: python3 sweep/make_figures.py
"""
from __future__ import annotations
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("manuscript/figures"); OUT.mkdir(parents=True, exist_ok=True)
RO = Path("recompute-output")
PROV = ["aws", "azure", "gcp", "huawei", "alibaba"]
LBL = {"aws": "AWS", "azure": "Azure", "gcp": "GCP",
       "huawei": "Huawei", "alibaba": "Alibaba"}
MARK = {"block": "s", "file": "^", "object": "o"}
LS = {"block": "--", "file": "-.", "object": "-"}
COL = {"block": "#666666", "file": "#1f77b4", "object": "#d62728"}


def load_runs():
    rows = list(csv.DictReader(open(RO / "runs_recomputed.csv")))
    for r in rows:
        r["concurrency"] = int(r["concurrency"])
    return rows


def cell_mean(rows, prov, para, wl, c, col="combined_tput_mib_s"):
    v = [float(r[col]) for r in rows
         if r["provider"] == prov and r["paradigm"] == para
         and r["workload"] == wl and r["concurrency"] == c and r.get(col)]
    return sum(v) / len(v) if v else None


def fig1(rows):
    fig, axes = plt.subplots(2, 5, figsize=(15, 6), sharex=True)
    for ri, wl in enumerate(["balanced", "largeobj"]):
        for ci, prov in enumerate(PROV):
            ax = axes[ri][ci]
            for para in ["block", "file", "object"]:
                xs = [c for c in (1, 4, 16, 64)
                      if cell_mean(rows, prov, para, wl, c)]
                ys = [cell_mean(rows, prov, para, wl, c) for c in xs]
                ax.plot(xs, ys, marker=MARK[para], ls=LS[para],
                        color=COL[para], label=para, ms=4, lw=1.3)
            ax.set_xscale("log", base=2); ax.set_yscale("log")
            ax.set_xticks([1, 4, 16, 64])
            ax.set_xticklabels(["1", "4", "16", "64"])
            ax.tick_params(labelsize=8)
            if ri == 0:
                ax.set_title(LBL[prov], fontsize=10)
            if ci == 0:
                ax.set_ylabel(("Balanced" if wl == "balanced" else
                               "Large-object") + "\nMiB/s (bytes/time)",
                              fontsize=9)
            if ri == 1:
                ax.set_xlabel("threads", fontsize=8)
            ax.grid(True, which="both", alpha=0.25, lw=0.4)
    axes[0][0].legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(OUT / "fig1_recomputed.png", dpi=200)


def fig2():
    ex = [r for r in csv.DictReader(open(RO / "exponents_recomputed.csv"))
          if r["operation"] == "combined" and r["beta"]]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for ai, wl in enumerate(["balanced", "largeobj"]):
        ax = axes[ai]; y = 0; ypos = []; labels = []
        for para in ["object", "file", "block"]:
            for prov in PROV:
                rec = next((r for r in ex if r["provider"] == prov
                            and r["paradigm"] == para
                            and r["workload"] == wl), None)
                if rec:
                    b, lo, hi = (float(rec["beta"]), float(rec["ci_lo"]),
                                 float(rec["ci_hi"]))
                    ax.errorbar(b, y, xerr=[[b - lo], [hi - b]],
                                fmt=MARK[para], color=COL[para], ms=5,
                                capsize=2, lw=1)
                labels.append(LBL[prov]); ypos.append(y); y += 1
            y += 1
        ax.axvline(0, color="k", lw=0.6); ax.axvline(1, color="k", lw=0.6, ls=":")
        ax.set_yticks(ypos); ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel(r"scaling exponent $\beta$ (95% CI)", fontsize=9)
        ax.set_title("Balanced" if wl == "balanced" else "Large-object",
                     fontsize=10)
        ax.grid(True, axis="x", alpha=0.25, lw=0.4)
        ax.invert_yaxis()
    for para in ["object", "file", "block"]:
        axes[0].plot([], [], MARK[para], color=COL[para], label=para)
    axes[0].legend(fontsize=8, loc="lower right")
    fig.tight_layout(); fig.savefig(OUT / "fig2_recomputed.png", dpi=200)


def fig3(rows):
    v1 = {}
    for r in csv.DictReader(open(
            "quarantine/azure-object-v1-runner/all_runs.csv")):
        t = (r.get("total_throughput_mbps") or "").strip()
        if t and r["paradigm"] == "object" and r["workload"] == "balanced":
            v1.setdefault(int(r["concurrency"]), []).append(float(t))
    v2 = {c: [float(r["combined_tput_mib_s"]) for r in rows
              if r["provider"] == "azure" and r["paradigm"] == "object"
              and r["workload"] == "balanced" and r["concurrency"] == c
              and r.get("combined_tput_mib_s")] for c in (1, 4, 16, 64)}
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for label, src, col, mk in [
            ("v1 runner (artifact; as recorded)", v1, "#999999", "x"),
            ("v2 runner (bytes/time)", v2, "#d62728", "o")]:
        xs = sorted(c for c in src if src[c])
        ys = [sum(src[c]) / len(src[c]) for c in xs]
        ax.plot(xs, ys, marker=mk, color=col, label=label, lw=1.4)
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xticks([1, 4, 16, 64]); ax.set_xticklabels(["1", "4", "16", "64"])
    ax.set_xlabel("threads"); ax.set_ylabel("MiB/s")
    ax.set_title("Azure Blob balanced: instrument correction", fontsize=10)
    ax.legend(fontsize=8); ax.grid(True, which="both", alpha=0.25, lw=0.4)
    fig.tight_layout(); fig.savefig(OUT / "fig3_azure_instrument.png", dpi=200)


def fig4():
    pp = list(csv.DictReader(open(RO / "per_phase.csv")))
    for r in pp:
        r["concurrency"] = int(r["concurrency"])
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.5), sharex=True)
    for ri, op in enumerate(["WRITE", "READ"]):
        for ci, para in enumerate(["block", "file", "object"]):
            ax = axes[ri][ci]
            for prov in PROV:
                pts = {}
                for r in pp:
                    if (r["provider"] == prov and r["paradigm"] == para
                            and r["workload"] == "balanced"
                            and r["op"] == op and r["lat_p99_ms"]):
                        pts.setdefault(r["concurrency"], []).append(
                            float(r["lat_p99_ms"]))
                xs = sorted(pts)
                ys = [sum(pts[c]) / len(pts[c]) for c in xs]
                if xs:
                    ax.plot(xs, ys, marker=MARK[para], color=COL[para],
                            alpha=0.45, lw=1, ms=3)
            ax.set_xscale("log", base=2); ax.set_yscale("log")
            ax.set_xticks([1, 4, 16, 64])
            ax.set_xticklabels(["1", "4", "16", "64"])
            if ri == 0:
                ax.set_title(para, fontsize=10)
            if ci == 0:
                ax.set_ylabel(f"{op.lower()}-phase p99 (ms)", fontsize=9)
            if ri == 1:
                ax.set_xlabel("threads", fontsize=9)
            ax.grid(True, which="both", alpha=0.25, lw=0.4)
    fig.tight_layout(); fig.savefig(OUT / "fig4_recomputed_p99.png", dpi=200)


if __name__ == "__main__":
    rows = load_runs()
    fig1(rows); fig2(); fig3(rows); fig4()
    print("wrote 4 figures to", OUT)
