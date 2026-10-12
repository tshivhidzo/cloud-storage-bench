#!/usr/bin/env python3
"""
run_rerun_v21.py -- orchestrator for the v2.1 rerun
(SWEEP_PROTOCOL_V2_1_AMENDMENT.md). One provider per host, inside tmux.

Reuses the archived harness read-only (provision.py for targets, runners.py
for cache drops, credential flags and redaction); the v1 orchestrator
run_sweep.py is not touched, so the v1 campaign stays reproducible.

What differs from run_sweep.py, all required by the amendment:
  * plan from sweep_design_v21 (seed 43, balanced only, 128-thread object
    level, multi-client and AWS equivalence/reservoir runs)
  * uniform weak scaling, 1280 MiB per thread, sizes passed in MiB
  * every block/file run --timelimit 600; object runs untimed with a
    2700 s subprocess window; SDK runners get --duration 2400
  * mpstat -P ALL every 5 s for the whole measured window (per-core)
  * SHA-256 of the elbencho binary and of the runner script in every record
  * refuses to start if the Alibaba endpoint is not "-internal."

    python3 run_rerun_v21.py --provider aws --dry-run
    python3 run_rerun_v21.py --provider aws --host2 10.42.1.23 --resume
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import runners                      # noqa: E402  (archived harness, read-only)
import sweep_design_v21 as D        # noqa: E402

AZURE_RUNNER = HERE / "azure_blob_runner_v2.py"
EQUIV_RUNNER = HERE / "s3_equiv_runner.py"
WARMUP_S = 60
_HASH_CACHE = {}


def sha256_of(path):
    if not path or not Path(path).exists():
        return ""
    p = str(Path(path).resolve())
    if p not in _HASH_CACHE:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _HASH_CACHE[p] = h.hexdigest()
    return _HASH_CACHE[p]


class PerCoreTelemetry:
    """mpstat -P ALL every 5 s until stopped (window length is not known in
    advance for dataset-driven runs, so no sample count is fixed)."""
    def __init__(self, out_path):
        self.out_path, self.proc, self.fh = out_path, None, None

    def start(self):
        try:
            self.fh = open(self.out_path, "w")
            self.proc = subprocess.Popen(["mpstat", "-P", "ALL", "5"],
                                         stdout=self.fh, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            self.proc = None

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        if self.fh:
            self.fh.close()


def build_argv(run, target, csv_path, host2):
    """argv for one run plus (tool, runner_path)."""
    c, para, mode = run["concurrency"], run["paradigm"], run["mode"]
    if para == "object" and run["provider"] == "azure":
        return (["python3", str(AZURE_RUNNER), "--workload", "balanced",
                 "--concurrency", str(c), "--duration", str(D.OBJECT_DURATION_S),
                 "--container", target, "--csvfile", csv_path],
                "azure_blob_runner_v2", AZURE_RUNNER)
    if mode in ("equiv", "reservoir"):
        return (["python3", str(EQUIV_RUNNER), "--workload", "balanced",
                 "--concurrency", str(c), "--duration", str(D.OBJECT_DURATION_S),
                 "--bucket", target, "--csvfile", csv_path,
                 "--lat-cap", str(run["lat_cap"])],
                "s3_equiv_runner", EQUIV_RUNNER)
    common = ["elbencho", "-t", str(c), "-b", "64k", "--lat", "--latpercent",
              "--csvfile", csv_path]
    if para in ("block", "file"):
        return (common + ["--timelimit", str(D.BLOCKFILE_TIMELIMIT_S), "--direct",
                          "-s", f"{D.dataset_mib(c)}m", "-w", "-r",
                          target.rstrip("/") + "/csb.dat"],
                "elbencho", shutil.which("elbencho"))
    # object, S3-compatible: per thread 1280 MiB as 20480 objects of 64 KiB
    n_obj = D.PER_THREAD_MIB * 1024 // 64
    argv = common + runners._s3_env_flags() + ["-n", "1", "-N", str(n_obj),
                                               "-s", D.OBJECT_SIZE]
    if mode == "multi":
        argv += ["--hosts", f"localhost,{host2}"]
    return argv + ["-w", "-r", target], "elbencho", shutil.which("elbencho")


def execute(run, target, raw_dir, host2):
    rid = run["run_id"]
    csv_path = str(raw_dir / f"{rid}.elbencho.csv")
    log_path = str(raw_dir / f"{rid}.stdout.log")
    tel_path = str(raw_dir / f"{rid}.mpstat.txt")
    if run["paradigm"] == "object" and run["provider"] == "aws":
        region = (os.environ.get("AWS_REGION")
                  or os.environ.get("AWS_DEFAULT_REGION") or "af-south-1")
        os.environ.setdefault("S3_ENDPOINT", f"https://s3.{region}.amazonaws.com")
        os.environ.setdefault("S3_REGION", region)
        runners._refresh_aws_role_creds()
    argv, tool, runner_path = build_argv(run, target, csv_path, host2)
    res = {"tool": tool, "cmd": runners._redacted_cmd(argv),
           "raw_csv": csv_path, "raw_log": log_path, "telemetry": tel_path,
           "elbencho_sha256": sha256_of(shutil.which("elbencho")),
           "runner_sha256": sha256_of(runner_path) if tool != "elbencho" else "",
           "status": "planned", "error": ""}
    window = (D.BLOCKFILE_TIMELIMIT_S * 2 + 300 if run["paradigm"] != "object"
              else D.SUBPROCESS_WINDOW_S)
    started_services = False
    if run["mode"] == "multi":
        subprocess.run(["elbencho", "--service"], check=False)
        started_services = True
    runners.drop_caches()
    if tool == "elbencho":            # warm-up identical to v1: argv, killed at 90 s
        try:
            subprocess.run(argv, timeout=WARMUP_S + 30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    tel = PerCoreTelemetry(tel_path)
    tel.start()
    t0 = time.time()
    try:
        with open(log_path, "w") as log:
            cp = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                                timeout=window)
        res["returncode"] = cp.returncode
        res["status"] = "ok" if cp.returncode == 0 else "failed"
        if cp.returncode:
            res["error"] = f"tool exited {cp.returncode}; see {log_path}"
    except subprocess.TimeoutExpired:
        res.update(status="failed", error="measurement timed out")
    except FileNotFoundError as e:
        res.update(status="failed", error=f"tool not found: {e}")
    finally:
        tel.stop()
        res["measured_wall_s"] = round(time.time() - t0, 1)
        if started_services:
            subprocess.run(["elbencho", "--quit", "--hosts", "localhost"],
                           check=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    return res


def purge(args):
    """Empty benchmark buckets before teardown (best effort, never fails a run)."""
    try:
        subprocess.run([sys.executable, str(HERE / "purge_s3.py"), *args],
                       timeout=3600)
    except subprocess.TimeoutExpired:
        print("    (purge timed out; teardown will try force_destroy)")


def guards(plan, provider):
    objs = [r for r in plan if r["paradigm"] == "object"]
    if objs and provider in ("gcp", "huawei", "alibaba"):
        missing = [v for v in ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY")
                   if not os.environ.get(v)]
        if missing:
            sys.exit(f"REFUSING TO RUN: {missing} not set for {provider} object "
                     "runs. Export the S3_* block from the runbook in THIS shell.")
    if objs and provider == "alibaba" and "-internal." not in os.environ.get(
            "S3_ENDPOINT", ""):
        sys.exit("REFUSING TO RUN: Alibaba S3_ENDPOINT must be the internal "
                 "endpoint (oss-me-central-1-internal.aliyuncs.com). The public "
                 "endpoint measures the host's 100 Mbit/s bandwidth cap.")
    if any(r["mode"] == "multi" for r in plan) and not shutil.which("elbencho"):
        sys.exit("REFUSING TO RUN: elbencho missing")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True,
                    choices=["aws", "azure", "gcp", "huawei", "alibaba"])
    ap.add_argument("--host2", default="",
                    help="private IP of the second client (enables multi-client)")
    ap.add_argument("--modes", default="primary,ext128,multi,equiv,reservoir")
    ap.add_argument("--stage", default="1", choices=["1", "2", "all"],
                    help="run stage 1 (object+block primary) first; stage 2 after "
                         "stage 1 is complete on this provider")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    import provision as provision_mod   # imported late: dry runs need no terraform
    outdir = Path(a.outdir or f"./results-rerun-v21-{a.provider}")
    modes = set(a.modes.split(","))
    plan = [r for r in D.plan(a.provider, multi_client=bool(a.host2))
            if r["mode"] in modes and (a.stage == "all" or r["stage"] == int(a.stage))]
    manifest = outdir / "run_manifest.jsonl"
    if a.resume and manifest.exists():
        done, tries = set(), {}
        for line in manifest.read_text().splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue          # a run killed mid-write leaves a partial line
            tries[rec["run_id"]] = tries.get(rec["run_id"], 0) + 1
            if rec.get("status") == "ok":
                done.add(rec["run_id"])
        exhausted = [r["run_id"] for r in plan
                     if r["run_id"] not in done and tries.get(r["run_id"], 0) >= 3]
        if exhausted:
            print(f"retry limit reached (3 attempts), reported as blanks: {exhausted}")
        plan = [r for r in plan if r["run_id"] not in done
                and r["run_id"] not in exhausted]
    print(f"v2.1 plan for {a.provider}: {len(plan)} runs")
    for i, r in enumerate(plan, 1):
        print(f"{i:>3} {r['run_id']:38} {r['mode']:9} {r['paradigm']:6} "
              f"c={r['concurrency']:<3} hosts={r['hosts']} "
              f"dataset={r['dataset_mib']} MiB")
    if a.dry_run:
        print("dry-run: nothing provisioned, nothing measured, nothing billed.")
        return
    guards(plan, a.provider)

    raw = outdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    ok = failed = 0
    with open(manifest, "a") as mf:
        stop_at = datetime.fromisoformat(D.STOP_AT)
        for i, run in enumerate(plan, 1):
            if datetime.now(timezone.utc) > stop_at:
                print(f"STOP_AT {D.STOP_AT} reached: {len(plan) - i + 1} run(s) "
                      "not started; they are reported as not executed.")
                break
            print(f"[{i}/{len(plan)}] {run['run_id']} ({run['mode']}, "
                  f"stage {run['stage']})", flush=True)
            rec = {"ts_start": datetime.now(timezone.utc).isoformat(), **run}
            target = None
            try:
                if run["provider"] == "alibaba":
                    # before EVERY Alibaba provision: a block/file apply also
                    # destroys a leftover object bucket, which fails if non-empty
                    purge(["--prefix", "csb-bench-"])
                if run["provider"] == "azure" and run["paradigm"] == "object":
                    subprocess.run(["pkill", "-f", "azure_blob_runner"])
                    time.sleep(2)
                target = provision_mod.provision(run["provider"], run["paradigm"])
                rec["region"] = target.get("region", "")
                rec["target"] = target.get("target", "")
                rec.update(execute(run, target["target"], raw, a.host2))
            except Exception as e:
                rec.update(status="failed", error=f"{type(e).__name__}: {e}")
            finally:
                # GCS's S3 interface has no multi-object delete, so GCP is left
                # to Terraform's force_destroy (which deletes in parallel)
                if (target and run["paradigm"] == "object"
                        and run["provider"] in ("aws", "huawei", "alibaba")):
                    purge(["--bucket", target["target"]])
                if target:
                    try:
                        provision_mod.teardown(run["provider"], run["paradigm"])
                        rec["teardown"] = "ok"
                    except Exception as e:
                        rec["teardown"] = f"FAILED: {e} -- CHECK BILLING"
            rec["ts_end"] = datetime.now(timezone.utc).isoformat()
            mf.write(json.dumps(rec) + "\n"); mf.flush()
            if rec.get("status") == "ok":
                ok += 1
            else:
                failed += 1
                print(f"    -> {rec.get('status')}: {rec.get('error', '')}")
    print(f"\nfinished: ok={ok} failed={failed} of {len(plan)}. "
          f"Manifest: {manifest}. Re-run with --resume to retry failures "
          "(at most two retries per run, protocol section G).")


if __name__ == "__main__":
    main()
