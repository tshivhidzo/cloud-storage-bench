#!/usr/bin/env python3
"""
recompute_from_raw.py -- authoritative recomputation of every reported number
from raw campaign artefacts, addressing the pre-submission audit findings:

  * Balanced throughput: the original parser summed sequential phase RATES.
    Here, combined throughput = total MiB moved in both phases / total elapsed
    seconds of both phases. Read and write phases are ALSO reported separately.
  * Tail latency: per-phase p99 taken from elbencho's stdout percentile lines
    (the csv has no percentiles); never combined across phases. The Azure SDK
    runner emits per-phase p99 directly (reservoir-sampled, disclosed).
  * Attempt selection: elbencho csv files append across retry attempts; the
    final attempt's phases are selected (last READ row and the WRITE row
    immediately preceding it, or the last WRITE row for write-only phases).
    stdout logs are overwritten per attempt and thus already final.
  * As-executed design audit: for every successful run, the actual dataset
    size (-s) and presence of --timelimit are read from the archived command
    line and reported, so the mixed pre-/post-correction conditions are
    quantified rather than asserted uniform.
  * Attempt accounting: total attempts vs successes per provider.

Outputs (./recompute-output/):
    per_phase.csv        one row per measured phase of every successful run
    runs_recomputed.csv  one row per run: read/write/combined throughput,
                         per-phase p99, dataset_gb, timelimit flag, cpu%
    design_audit.csv     sizing rule and timelimit per cell as executed
    attempts.csv         attempts vs successes per provider
Run:  python3 sweep/recompute_from_raw.py  (from cloud-storage-bench/)
"""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path

DIRS = {"aws": "results-sweep-aws", "azure": "results-sweep-azure",
        "gcp": "results-sweep-gcp", "huawei": "results-sweep-huawei",
        "alibaba": "results-sweep-alibaba"}
OUT = Path("recompute-output"); OUT.mkdir(exist_ok=True)

PCT_LINE = re.compile(r"IO lat % us\s*:\s*\[([^\]]+)\]")
P99 = re.compile(r"99%<=(\d+)")
PHASE_HDR = re.compile(r"^(WRITE|READ)\s")
SIZE_FLAG = re.compile(r"-s (\d+)([kmgt]?)m?\b|-s '?(\d+)([kmg])'?")


def parse_stdout_p99(path):
    """Return {'WRITE': p99_ms, 'READ': p99_ms} from the final attempt's log."""
    out, current = {}, None
    try:
        for line in open(path, errors="ignore"):
            m = PHASE_HDR.match(line)
            if m:
                current = m.group(1)
            m = PCT_LINE.search(line)
            if m and current:
                m99 = P99.search(m.group(1))
                if m99:
                    out[current] = int(m99.group(1)) / 1000.0  # us -> ms
    except FileNotFoundError:
        pass
    return out


def final_phases_elbencho(csv_path, workload):
    """Select the final attempt's phase rows from an append-mode elbencho csv.
    Returns list of (op, mib, elapsed_s, avg_ms)."""
    try:
        rows = list(csv.DictReader(open(csv_path)))
    except FileNotFoundError:
        return []
    if not rows:
        return []
    def g(r, k):
        v = (r.get(k) or "").strip()
        return float(v) if v else None
    parsed = [(r.get("operation", "").strip().upper(),
               g(r, "MiB [last]"), (g(r, "time ms [last]") or 0) / 1000.0,
               (g(r, "IO lat us [avg]") or 0) / 1000.0) for r in rows]
    if workload == "balanced":
        # last READ row + the WRITE row immediately before it. If no READ row
        # exists, the run's write phase hit --timelimit and elbencho ended the
        # whole benchmark (its limit ends the run, not just the phase): the
        # run is a valid WRITE-ONLY measurement and is flagged downstream via
        # the phases_present column.
        for i in range(len(parsed) - 1, -1, -1):
            if parsed[i][0] == "READ":
                for j in range(i - 1, -1, -1):
                    if parsed[j][0] == "WRITE":
                        return [parsed[j], parsed[i]]
                return [parsed[i]]
        writes = [p for p in parsed if p[0] == "WRITE"]
        return [writes[-1]] if writes else []
    if workload in ("largeobj", "read"):
        reads = [p for p in parsed if p[0] == "READ"]
        return [reads[-1]] if reads else []
    writes = [p for p in parsed if p[0] == "WRITE"]
    return [writes[-1]] if writes else []


def phases_azure(csv_path, duration_s):
    """Azure SDK runner v2: per-phase rows already; csv overwritten per attempt."""
    try:
        rows = list(csv.DictReader(open(csv_path)))
    except FileNotFoundError:
        return []
    out = []
    for r in rows:
        op = r["operation"].strip().upper()
        rate = float(r["throughput_mb_s"])
        dur = duration_s / 2.0  # v2 phase budget: duration//2 per measured phase
        out.append((op, rate * dur / 1.048576, dur,  # MB -> MiB approx
                    float(r.get("lat_mean_ms") or 0), float(r.get("lat_p99_ms") or 0)))
    return out


def dataset_gb_from_cmd(cmd):
    """Actual total dataset from the archived -s flag (elbencho: total for
    block/file shared file; per-thread for object) times -N/-t as recorded."""
    m = re.search(r"-s '?(\d+)([kmg])'?", cmd)
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2)
    per = val / (1024 if unit == "m" else 1) if unit in "m" else val
    gb = val / 1024 if unit == "m" else (val if unit == "g" else val / 1024 / 1024)
    tm = re.search(r"-t (\d+)", cmd); nm = re.search(r"-N (\d+)", cmd)
    if "--s3endpoint" in cmd and tm and nm:  # object: -s is per file, files=-N per thread
        return round(gb * int(tm.group(1)) * int(nm.group(1)), 1)
    return round(gb, 1)


def main():
    per_phase, runs, attempts = [], [], []
    for prov, d in DIRS.items():
        man = Path(d) / "run_manifest.jsonl"
        recs, n_attempts = {}, 0
        for line in open(man):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_attempts += 1
            if r.get("status") == "ok":
                recs[r["run_id"]] = r  # last ok wins
        attempts.append({"provider": prov, "attempts": n_attempts,
                         "successes": len(recs)})
        cpu = {}
        arf = Path(d) / "all_runs.csv"
        if arf.exists():
            for r in csv.DictReader(open(arf)):
                cpu[r.get("run_id", "")] = (r.get("cpu_util_pct") or "").strip()
        for run_id, rec in sorted(recs.items()):
            wl, para = rec["workload"], rec["paradigm"]
            cmd = rec.get("cmd", "")
            raw = Path(d) / "raw"
            csvf = raw / f"{run_id}.elbencho.csv"
            stdoutf = raw / f"{run_id}.stdout.log"
            is_azure_obj = prov == "azure" and para == "object"
            row = {"run_id": run_id, "provider": prov, "paradigm": para,
                   "workload": wl, "concurrency": rec["concurrency"],
                   "rep": rec["rep"], "cpu_util_pct": cpu.get(run_id, ""),
                   "timelimit": "--timelimit" in cmd,
                   "dataset_gb_executed": dataset_gb_from_cmd(cmd),
                   "endpoint_internal": ("-internal." in cmd) if "--s3endpoint" in cmd else ""}
            if is_azure_obj:
                dm = re.search(r"--duration (\d+)", cmd)
                dur = int(dm.group(1)) if dm else 1200
                ph = phases_azure(csvf, dur)
                tot_mib = sum(p[1] for p in ph); tot_s = sum(p[2] for p in ph)
                for op, mib, el, avg, p99 in ph:
                    per_phase.append({**row, "op": op, "mib": round(mib, 1),
                                      "elapsed_s": round(el, 1),
                                      "tput_mib_s": round(mib / el, 2),
                                      "lat_avg_ms": avg, "lat_p99_ms": p99})
                    row[f"{op.lower()}_tput_mib_s"] = round(mib / el, 2)
                    row[f"{op.lower()}_p99_ms"] = p99
            else:
                ph = final_phases_elbencho(csvf, wl)
                p99s = parse_stdout_p99(stdoutf)
                tot_mib = sum(p[1] or 0 for p in ph)
                tot_s = sum(p[2] for p in ph)
                for op, mib, el, avg in ph:
                    if not mib or not el:
                        continue
                    per_phase.append({**row, "op": op, "mib": round(mib, 1),
                                      "elapsed_s": round(el, 1),
                                      "tput_mib_s": round(mib / el, 2),
                                      "lat_avg_ms": round(avg, 3),
                                      "lat_p99_ms": p99s.get(op, "")})
                    row[f"{op.lower()}_tput_mib_s"] = round(mib / el, 2)
                    row[f"{op.lower()}_p99_ms"] = p99s.get(op, "")
            row["combined_tput_mib_s"] = round(tot_mib / tot_s, 2) if tot_s else ""
            row["phases_present"] = "+".join(p[0] for p in ph)
            runs.append(row)

    def dump(name, rows):
        keys = sorted({k for r in rows for k in r}, key=lambda k: (k != "run_id", k))
        with open(OUT / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
        print(f"wrote {OUT/name} ({len(rows)} rows)")

    dump("per_phase.csv", per_phase)
    dump("runs_recomputed.csv", runs)
    dump("attempts.csv", attempts)

    # design audit: sizing + timelimit per cell
    audit = {}
    for r in runs:
        k = (r["provider"], r["paradigm"], r["workload"], r["concurrency"])
        a = audit.setdefault(k, {"sizes": set(), "timelimit": set()})
        a["sizes"].add(r["dataset_gb_executed"])
        a["timelimit"].add(r["timelimit"])
    arows = [{"provider": k[0], "paradigm": k[1], "workload": k[2],
              "concurrency": k[3],
              "dataset_gb_values": "/".join(str(s) for s in sorted(a["sizes"], key=str)),
              "mixed_sizing_within_cell": len(a["sizes"]) > 1,
              "timelimit_values": "/".join(str(t) for t in sorted(a["timelimit"]))}
             for k, a in sorted(audit.items())]
    dump("design_audit.csv", arows)


if __name__ == "__main__":
    main()
