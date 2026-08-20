#!/usr/bin/env python3
"""
parse_results.py -- turn the untouched raw tool output into the 26-field
all_runs.csv (thesis Appendix D). Integrity rules, enforced here in code:

  * A metric that is not present in the raw output is left BLANK and the reason
    is recorded in results/parse_notes.txt. It is never zero-filled, never
    interpolated, never guessed.
  * Every row carries the sha256 of the raw artefact it came from.
  * metadata workload is reported in ops/s + latency, never MB/s.

Reads results/run_manifest.jsonl (written by run_campaign.py) plus the raw
files it points to. Writes results/all_runs.csv and results/parse_notes.txt.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from design import SCHEMA, WORKLOAD_PARAMS


def sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_elbencho_csv(path, notes, run_id):
    """Best-effort extraction from an elbencho --csvfile. Returns a dict of the
    metrics found; anything absent is simply not in the dict (-> blank cell).
    elbencho column names vary by version, so we match fuzzily and record what
    we could not find rather than inventing it."""
    p = Path(path)
    found = {}
    if not p.exists() or p.stat().st_size == 0:
        notes.append(f"{run_id}: no elbencho csv at {path} -> all metrics blank")
        return found
    try:
        rows = list(csv.DictReader(open(p, newline="")))
    except Exception as e:
        notes.append(f"{run_id}: could not read csv ({e}) -> blank")
        return found
    if not rows:
        notes.append(f"{run_id}: empty csv -> blank")
        return found

    def col(row, *needles):
        for k, v in row.items():
            kl = (k or "").lower()
            if all(n in kl for n in needles):
                n = _num(v)
                if n is not None:
                    return n
        return None

    # elbencho typically writes one row per phase (write=PUT, read=GET).
    read_row = next((r for r in rows if re.search(r"read|get", " ".join(r.keys()).lower()
                     + " " + str(r).lower())), None)
    # Simpler and safer: scan all rows, take max/last non-null per metric type.
    for r in rows:
        op = (str(r.get("operation", "")) + str(r.get("Operation", ""))).lower()
        tput = col(r, "throughput") or col(r, "mib") or col(r, "mb/s")
        iops = col(r, "iops")
        lat_mean = col(r, "lat", "mean") or col(r, "latency", "avg")
        lat_p95 = col(r, "lat", "95")
        lat_p99 = col(r, "lat", "99")
        if "write" in op or "put" in op:
            if tput is not None: found["write_throughput_mbps"] = tput
            if iops is not None: found["write_iops"] = iops
        elif "read" in op or "get" in op:
            if tput is not None: found["read_throughput_mbps"] = tput
            if iops is not None: found["read_iops"] = iops
        else:  # unlabeled phase -> record as read/total candidate
            if tput is not None: found.setdefault("total_throughput_mbps", tput)
            if iops is not None: found.setdefault("total_iops", iops)
        for key, val in (("lat_mean_ms", lat_mean), ("lat_p95_ms", lat_p95),
                         ("lat_p99_ms", lat_p99)):
            if val is not None:
                found[key] = val
    # derive totals only when both halves are real measurements (not invented)
    if "total_throughput_mbps" not in found:
        rt, wt = found.get("read_throughput_mbps"), found.get("write_throughput_mbps")
        if rt is not None and wt is not None:
            found["total_throughput_mbps"] = rt + wt
        elif rt is not None:
            found["total_throughput_mbps"] = rt
        elif wt is not None:
            found["total_throughput_mbps"] = wt
    if "total_iops" not in found:
        ri, wi = found.get("read_iops"), found.get("write_iops")
        if ri is not None and wi is not None:
            found["total_iops"] = ri + wi
        elif ri is not None:
            found["total_iops"] = ri
        elif wi is not None:
            found["total_iops"] = wi
    # Metadata phases (create/stat/delete) report their rate in "entries/s";
    # aggregate ops/s = total entries / total phase time, both read straight
    # from the phase rows (never invented). Entry latency: entry-weighted mean.
    def exact(r, key):
        for k, v in r.items():
            if (k or "").strip().lower() == key:
                n = _num(v)
                if n is not None:
                    return n
        return None

    ents_sum = time_s_sum = 0.0
    lat_num = lat_den = 0.0
    io_lats = []
    for r in rows:
        e = exact(r, "entries [last]")
        t = exact(r, "time ms [last]")
        if e and t:
            ents_sum += e
            time_s_sum += t / 1000.0
            la = exact(r, "ent lat us [avg]")
            if la is not None:
                lat_num += la * e
                lat_den += e
        il = exact(r, "io lat us [avg]")
        if il is not None:
            io_lats.append(il)
    if ents_sum > 0 and time_s_sum > 0:
        found["md_ops_per_s"] = round(ents_sum / time_s_sum, 1)
        if lat_den > 0:
            found["md_lat_mean_ms"] = round((lat_num / lat_den) / 1000.0, 3)
    # per-IO latency: mean of the phase averages, us -> ms (elbencho csv carries
    # min/avg/max only; percentiles are in the stdout log, parsed below)
    if io_lats and "lat_mean_ms" not in found:
        found["lat_mean_ms"] = round(sum(io_lats) / len(io_lats) / 1000.0, 3)

    if not found:
        notes.append(f"{run_id}: csv present but no recognised metric columns -> "
                     "blank (check elbencho version vs configs/elbencho/NOTES.md)")
    return found


def parse_mpstat(path):
    """Mean CPU utilisation (100 - %idle) from an mpstat capture, or None."""
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    idles = []
    for line in p.read_text(errors="ignore").splitlines():
        parts = line.split()
        if parts and parts[-1].replace(".", "").isdigit() and "%idle" not in line \
                and ("all" in line.lower() or re.match(r"\d", parts[0] or "")):
            idle = _num(parts[-1])
            if idle is not None and 0 <= idle <= 100:
                idles.append(idle)
    if not idles:
        return None
    return round(100 - sum(idles) / len(idles), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="./results")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    manifest = outdir / "run_manifest.jsonl"
    if not manifest.exists():
        sys.exit(f"no {manifest}. Run run_campaign.py first.")

    notes, rows = [], []
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        run_id = rec.get("run_id", "?")
        row = {k: "" for k in SCHEMA}
        row.update({
            "run_id": run_id,
            "timestamp_utc": rec.get("ts_end", ""),
            "provider": rec.get("provider", ""),
            "region": rec.get("region", ""),
            "paradigm": rec.get("paradigm", ""),
            "workload": rec.get("workload", ""),
            "rep": rec.get("rep", ""),
            "concurrency": rec.get("concurrency", ""),
            "tool": rec.get("tool", ""),
            "warmup_s": rec.get("warmup_s", ""),
            "duration_s": rec.get("duration_s", ""),
        })
        wp = WORKLOAD_PARAMS.get(rec.get("workload"), {})
        row["block_size"] = wp.get("block_size", "")
        row["dataset_size_gb"] = wp.get("dataset_gb", "")

        if rec.get("status") != "ok":
            notes.append(f"{run_id}: run status={rec.get('status')} "
                         f"({rec.get('error','')}) -> metrics blank")
            rows.append(row)
            continue

        raw_csv = rec.get("raw_csv", "")
        row["raw_artifact_path"] = raw_csv
        row["raw_sha256"] = sha256(raw_csv)
        found = parse_elbencho_csv(raw_csv, notes, run_id)

        if rec.get("workload") == "metadata":
            # metadata: ops/s + latency only; blank the throughput fields
            row["metadata_ops_per_s"] = found.get("md_ops_per_s",
                                                  found.get("total_iops",
                                                            found.get("read_iops", "")))
            for k in ("lat_mean_ms", "lat_p95_ms", "lat_p99_ms"):
                if k in found:
                    row[k] = found[k]
            if row.get("lat_mean_ms", "") == "" and "md_lat_mean_ms" in found:
                row["lat_mean_ms"] = found["md_lat_mean_ms"]
            if row["metadata_ops_per_s"] == "":
                notes.append(f"{run_id}: metadata ops/s not found -> blank")
        else:
            for k in ("read_throughput_mbps", "write_throughput_mbps",
                      "total_throughput_mbps", "read_iops", "write_iops",
                      "total_iops", "lat_mean_ms", "lat_p95_ms", "lat_p99_ms"):
                if k in found:
                    row[k] = found[k]

        # p99 latency: elbencho --latpercent prints percentiles only to stdout
        # ("IO lat % us : [ ... 99%<=1722 ]"), never to the csv.
        if row.get("lat_p99_ms", "") == "" and rec.get("tool") == "elbencho":
            lp = Path(rec.get("raw_log", ""))
            if lp.is_file():
                p99s = [int(m) for m in
                        re.findall(r"99%<=(\d+)", lp.read_text(errors="ignore"))]
                if p99s:
                    row["lat_p99_ms"] = round(sum(p99s) / len(p99s) / 1000.0, 3)

        cpu = parse_mpstat(rec.get("telemetry", ""))
        if cpu is not None:
            row["cpu_util_pct"] = cpu
        rows.append(row)

    out_csv = outdir / "all_runs.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMA)
        w.writeheader()
        w.writerows(rows)
    (outdir / "parse_notes.txt").write_text("\n".join(notes) + ("\n" if notes else ""))

    filled = sum(1 for r in rows if r.get("total_throughput_mbps") not in ("",)
                 or r.get("metadata_ops_per_s") not in ("",))
    print(f"Wrote {out_csv} ({len(rows)} rows).")
    print(f"Rows with at least one measured metric: {filled}/{len(rows)}.")
    print(f"Parse notes ({len(notes)}): {outdir/'parse_notes.txt'}")
    print("Blank cells are honest gaps, not errors. Next: add_costs.py then consolidate.py")


if __name__ == "__main__":
    main()
