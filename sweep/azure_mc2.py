#!/usr/bin/env python3
"""
azure_mc2.py -- supplementary Azure two-host object test (DEVIATIONS_V21.md D5).

Runs azure_blob_runner_v2.py (unchanged) at 64 threads on BOTH Azure hosts at
the same time against one fresh storage account per repetition (host 1:
container "bench", host 2: container "bench2"), three repetitions.

Run on host 1, inside tmux, in the shell where the Azure host_env_setup
(managed identity, ARM_*) was applied -- the same shell the stage 1/2 runs
used. Host 1 must be able to ssh to host 2 without a password (see runbook).

    python3 azure_mc2.py --host2 <host2 private ip> --dry-run
    python3 azure_mc2.py --host2 <host2 private ip>
    python3 azure_mc2.py --host2 <host2 private ip> --resume   # skip ok reps

The storage connection string reaches host 2 only through /dev/shm (RAM)
and is deleted after each repetition; it is never written to the results.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shlex, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import sweep_design_v21 as D     # noqa: E402  (STOP_AT, durations)

RUNNER = HERE / "azure_blob_runner_v2.py"
REMOTE_SWEEP = "~/cloud-storage-bench-thesis-v1/sweep"
CONC, REPS = 64, (1, 2, 3)
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
       "-o", "ConnectTimeout=10"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def rsh(host, cmd, inp=None, timeout=120):
    cp = subprocess.run(SSH + [f"ubuntu@{host}", cmd], input=inp, text=True,
                        capture_output=True, timeout=timeout)
    return cp.returncode, (cp.stdout or "") + (cp.stderr or "")


def preflight(host2):
    problems = []
    rc, out = rsh(host2, "hostname")
    if rc:
        problems.append(f"ssh to host2 failed: {out.strip()[:200]}")
        return problems, ""
    rc, out = rsh(host2, f"sha256sum {REMOTE_SWEEP}/azure_blob_runner_v2.py | cut -c1-64")
    remote_sha = out.strip()
    if rc or remote_sha != sha(RUNNER):
        problems.append(f"runner on host2 differs or missing (host2 {remote_sha[:12]}, "
                        f"host1 {sha(RUNNER)[:12]}): copy sweep/ to host2")
    rc, out = rsh(host2, "python3 -c 'import azure.storage.blob' && which mpstat")
    if rc:
        problems.append("host2 lacks azure-storage-blob or mpstat")
    if not os.environ.get("ARM_SUBSCRIPTION_ID") and not os.environ.get("ARM_USE_MSI"):
        problems.append("ARM_* not set in this shell: apply host_env_setup first")
    return problems, remote_sha


def make_container2(cs):
    from azure.storage.blob import BlobServiceClient
    svc = BlobServiceClient.from_connection_string(cs)
    try:
        svc.create_container("bench2")
    except Exception as e:
        if "ContainerAlreadyExists" not in str(e):
            raise


def one_rep(rep, host2, raw, remote_sha):
    import provision
    rid = f"azure-object-balanced-c64-r{rep}-mc2az"
    rec = {"ts_start": datetime.now(timezone.utc).isoformat(), "run_id": rid,
           "mode": "multi_azure", "paradigm": "object", "provider": "azure",
           "concurrency": CONC, "rep": rep, "hosts": 2, "workload": "balanced",
           "protocol": "v2.1-supplementary-D5", "stage": 4,
           "tool": "azure_blob_runner_v2", "runner_sha256": sha(RUNNER),
           "runner_sha256_host2": remote_sha, "status": "planned", "error": ""}
    target = None
    try:
        subprocess.run(["pkill", "-f", "azure_blob_runner"], check=False)
        rsh(host2, "pkill -f azure_blob_runner; pkill mpstat; true")
        time.sleep(2)
        target = provision.provision("azure", "object")
        rec["target"] = target["target"]
        cs = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        make_container2(cs)
        rc, out = rsh(host2, "umask 077; cat > /dev/shm/az.cs", inp=cs)
        if rc:
            raise RuntimeError(f"could not pass connection string to host2: {out[:200]}")

        p = {k: str(raw / f"{rid}.{k}") for k in
             ("host1.csv", "host1.log", "host1.mpstat.txt",
              "host2.csv", "host2.log", "host2.mpstat.txt")}
        r_csv, r_log, r_mp = (f"/tmp/{rid}.host2.csv", f"/tmp/{rid}.host2.log",
                              f"/tmp/{rid}.host2.mpstat.txt")
        rsh(host2, f"nohup mpstat -P ALL 5 > {r_mp} 2>&1 < /dev/null & "
                   f"echo $! > /tmp/{rid}.mp.pid")
        mp1 = subprocess.Popen(["mpstat", "-P", "ALL", "5"],
                               stdout=open(p["host1.mpstat.txt"], "w"),
                               stderr=subprocess.STDOUT)
        remote_cmd = (f"export AZURE_STORAGE_CONNECTION_STRING=$(cat /dev/shm/az.cs); "
                      f"python3 {REMOTE_SWEEP}/azure_blob_runner_v2.py --workload balanced "
                      f"--concurrency {CONC} --duration {D.OBJECT_DURATION_S} "
                      f"--container bench2 --csvfile {r_csv} > {r_log} 2>&1; echo rc=$?")
        argv1 = ["python3", str(RUNNER), "--workload", "balanced",
                 "--concurrency", str(CONC), "--duration", str(D.OBJECT_DURATION_S),
                 "--container", target["target"], "--csvfile", p["host1.csv"]]
        t2 = time.time()
        h2 = subprocess.Popen(SSH + [f"ubuntu@{host2}", remote_cmd],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        t1 = time.time()
        h1 = subprocess.Popen(argv1, stdout=open(p["host1.log"], "w"),
                              stderr=subprocess.STDOUT)
        rec["start_skew_s"] = round(t1 - t2, 2)
        rec["cmd_host1"] = " ".join(shlex.quote(a) for a in argv1)
        rec["cmd_host2"] = remote_cmd.split("; ", 1)[1].split(" >")[0]
        try:
            rc1 = h1.wait(timeout=D.SUBPROCESS_WINDOW_S)
            out2, _ = h2.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            h1.kill(); h2.kill()
            raise RuntimeError("measurement window exceeded")
        finally:
            mp1.terminate()
            rsh(host2, f"kill $(cat /tmp/{rid}.mp.pid) 2>/dev/null; rm -f /dev/shm/az.cs")
        rc2 = 0 if "rc=0" in (out2 or "") else 1
        rec["measured_wall_s"] = round(time.time() - t1, 1)
        for remote, local in ((r_csv, p["host2.csv"]), (r_log, p["host2.log"]),
                              (r_mp, p["host2.mpstat.txt"])):
            subprocess.run(["scp", "-q", "-o", "BatchMode=yes",
                            f"ubuntu@{host2}:{remote}", local], check=False)
        rec.update({f"raw_{k.replace('.', '_')}": v for k, v in p.items()})
        rec["returncode_host1"], rec["returncode_host2"] = rc1, rc2
        ok = rc1 == 0 and rc2 == 0 and all(Path(p[k]).exists() and Path(p[k]).stat().st_size
                                           for k in ("host1.csv", "host2.csv"))
        rec["status"] = "ok" if ok else "failed"
        if not ok:
            rec["error"] = f"host1 rc={rc1}, host2 rc={rc2}; see logs"
    except Exception as e:
        rec.update(status="failed", error=f"{type(e).__name__}: {e}"[:400])
        rsh(host2, "rm -f /dev/shm/az.cs; pkill -f azure_blob_runner; true")
    finally:
        os.environ.pop("AZURE_STORAGE_CONNECTION_STRING", None)
        if target:
            try:
                provision.teardown("azure", "object")
                rec["teardown"] = "ok"
            except Exception as e:
                rec["teardown"] = f"FAILED: {e} -- CHECK BILLING"
    rec["ts_end"] = datetime.now(timezone.utc).isoformat()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host2", required=True, help="Azure host 2 private IP")
    ap.add_argument("--outdir", default="./results-rerun-v21-azure-mc2")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    out = Path(a.outdir); raw = out / "raw"
    manifest = out / "run_manifest.jsonl"
    done = set()
    if a.resume and manifest.exists():
        for line in manifest.read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("status") == "ok":
                    done.add(r["rep"])
            except json.JSONDecodeError:
                pass
    reps = [r for r in REPS if r not in done]
    print(f"D5 Azure two-host test: {len(reps)} repetition(s) {reps}, "
          f"{CONC} threads per host, {D.OBJECT_DURATION_S} s each")
    problems, remote_sha = preflight(a.host2)
    for p in problems:
        print("  PREFLIGHT FAIL:", p)
    if problems:
        sys.exit("fix the preflight problems first")
    print(f"  preflight ok: host2 reachable, runner sha {remote_sha[:12]} on both hosts")
    if a.dry_run:
        print("dry-run: nothing provisioned, nothing measured, nothing billed.")
        return
    raw.mkdir(parents=True, exist_ok=True)
    stop_at = datetime.fromisoformat(D.STOP_AT)
    with open(manifest, "a") as mf:
        for rep in reps:
            if datetime.now(timezone.utc) > stop_at:
                print(f"STOP_AT {D.STOP_AT} reached; remaining repetitions not run.")
                break
            print(f"[rep {rep}] starting", flush=True)
            rec = one_rep(rep, a.host2, raw, remote_sha)
            mf.write(json.dumps(rec) + "\n"); mf.flush()
            print(f"[rep {rep}] {rec['status']} skew={rec.get('start_skew_s')} s "
                  f"teardown={rec.get('teardown')} {rec.get('error', '')}", flush=True)
            for h in ("host1", "host2"):
                f = Path(rec.get(f"raw_{h}_csv", ""))
                if f.is_file():
                    print(f"    {h}: " + " | ".join(l.strip() for l in f.read_text().splitlines()[1:]))


if __name__ == "__main__":
    main()
