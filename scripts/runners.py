"""
runners.py -- build and execute the measurement commands for one run and write
the untouched tool output to results/raw/. One elbencho execution path drives
block, file and object; Azure Blob object storage uses the SDK runner; FIO is a
cross-check only. Nothing here computes or invents a metric -- it only runs the
tool and captures what the tool prints. parse_results.py does the extraction.
"""
from __future__ import annotations
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from design import WORKLOAD_PARAMS


_IMDS_STATE = {"from_imds": False, "expiry": 0.0}


def _refresh_aws_role_creds():
    """elbencho does NOT use the AWS SDK default credential chain: without
    explicit keys it sends anonymous (unsigned) requests. On an EC2 host we
    therefore fetch the instance role's temporary credentials from IMDSv2 and
    export them for _s3_env_flags. Refreshed when close to expiry. Stores
    nothing on disk; the manifest redacts them."""
    import urllib.request
    if os.environ.get("S3_ACCESS_KEY") and not _IMDS_STATE["from_imds"]:
        return  # user-provided static keys take precedence
    if _IMDS_STATE["from_imds"] and time.time() < _IMDS_STATE["expiry"] - 600:
        return  # current temporary creds still comfortably valid
    try:
        base = "http://169.254.169.254/latest"
        tok_req = urllib.request.Request(
            base + "/api/token", method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"})
        token = urllib.request.urlopen(tok_req, timeout=3).read().decode()
        hdr = {"X-aws-ec2-metadata-token": token}
        url = base + "/meta-data/iam/security-credentials/"
        role = urllib.request.urlopen(
            urllib.request.Request(url, headers=hdr), timeout=3).read().decode().strip()
        doc = json.loads(urllib.request.urlopen(
            urllib.request.Request(url + role, headers=hdr), timeout=3).read())
        os.environ["S3_ACCESS_KEY"] = doc["AccessKeyId"]
        os.environ["S3_SECRET_KEY"] = doc["SecretAccessKey"]
        os.environ["S3_SESSION_TOKEN"] = doc["Token"]
        from datetime import datetime
        exp = datetime.fromisoformat(doc["Expiration"].replace("Z", "+00:00"))
        _IMDS_STATE.update(from_imds=True, expiry=exp.timestamp())
    except Exception:
        pass  # not on EC2 / no role: the run will fail visibly if creds missing


def _s3_env_flags():
    """S3 endpoint/credential flags. Keys are only passed when actually set;
    temporary (role) credentials also require the session token."""
    flags = []
    ep = os.environ.get("S3_ENDPOINT", "")
    if ep:
        flags += ["--s3endpoint", ep]
    reg = os.environ.get("S3_REGION", "")
    if reg:
        flags += ["--s3region", reg]  # request signing region (default us-east-1)
    if os.environ.get("S3_VIRT_ADDR", "") == "1":
        flags += ["--s3virtaddr"]  # e.g. Alibaba OSS rejects path-style requests
    key = os.environ.get("S3_ACCESS_KEY", "")
    sec = os.environ.get("S3_SECRET_KEY", "")
    tok = os.environ.get("S3_SESSION_TOKEN", "")
    if key and sec:
        flags += ["--s3key", key, "--s3secret", sec]
        if tok:
            flags += ["--s3sessiontoken", tok]
    return flags


def _size_bytes(s):
    """'64k' -> 65536, '16m' -> 16777216."""
    units = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    s = s.lower().strip()
    return int(float(s[:-1]) * units[s[-1]]) if s[-1] in units else int(s)


_SECRET_FLAGS = {"--s3key", "--s3secret", "--s3sessiontoken"}


def _redacted_cmd(argv):
    """Command string for the manifest with credential values masked."""
    out, mask = [], False
    for a in argv:
        out.append("***" if mask else a)
        mask = a in _SECRET_FLAGS
    return " ".join(shlex.quote(a) for a in out)


def _elbencho_flags(paradigm, workload, target, concurrency, csv_path):
    """Return the elbencho argv for a POSIX (block/file) or S3 (object) run.

    Flag names follow elbencho >= 3.0. If your build differs, adjust the
    templates in configs/elbencho/commands.json rather than editing code.
    """
    wp = WORKLOAD_PARAMS[workload]
    bs = wp["block_size"]
    size = f"{wp['dataset_gb']}g"
    common = ["elbencho", "-t", str(concurrency), "-b", bs,
              "--lat", "--latpercent",           # mean + percentile latency
              "--csvfile", csv_path]
    if paradigm in ("block", "file"):
        if workload == "metadata":
            # metadata: mkdir + create (0-byte) + stat + delete; ops/s + latency.
            # No --direct: metadata ops move no payload.
            return common + ["-d", "-w", "-s", "0", "-n", "10", "-N", "10000",
                             "--stat", "--delfiles", "--deldirs", target]
        common += ["--direct", "-s", size]        # bypass page cache, real device
        # target is a mount directory; bench against one shared file in it so
        # -s is the TOTAL dataset (threads split the file's ranges).
        tgt = target.rstrip("/") + "/csb.dat"
        if workload == "write":
            return common + ["-w", tgt]
        if workload == "balanced":
            # write then read pass; mix reported by parser from both phases
            return common + ["-w", "-r", tgt]
        # read / largeobj: execute_run does a prep write pass first
        return common + ["-r", tgt]
    else:  # object / S3-compatible; target is the bucket name
        s3 = common + _s3_env_flags()
        if workload == "metadata":
            # create (0-byte) + stat + delete objects; ops/s + latency
            return s3 + ["-w", "-s", "0", "-n", "10", "-N", "10000",
                         "--stat", "--delfiles", target]
        # Objects sized so the TOTAL equals dataset_gb. elbencho uploads one
        # MPU part per block (-b); S3 requires parts >= 5 MiB (except the last)
        # and <= 10,000 parts per object. So: blocks >= 5 MiB can form large
        # multipart objects; smaller blocks must use single-block objects
        # (one PUT/GET each) -- the S3-native small-object workload.
        bs_bytes = _size_bytes(bs)
        per_thread_bytes = max(1, wp["dataset_gb"] * (1024 ** 3) // concurrency)
        if bs_bytes >= 5 * 1024 * 1024:
            cap = bs_bytes * 8000                      # stay under 10k parts
            n_files = max(1, -(-per_thread_bytes // cap))  # ceil division
            obj_mb = max(1, per_thread_bytes // n_files // (1024 * 1024))
            s3 += ["-n", "1", "-N", str(n_files), "-s", f"{obj_mb}m"]
        else:
            n_files = max(1, per_thread_bytes // bs_bytes)
            s3 += ["-n", "1", "-N", str(n_files), "-s", bs]
        if workload == "write":
            return s3 + ["-w", target]
        if workload == "balanced":
            # write then read pass, mirroring the block/file balanced template
            return s3 + ["-w", "-r", target]
        # read / largeobj: execute_run does a prep write pass first
        return s3 + ["-r", target]
    raise ValueError(f"no elbencho template for {paradigm}/{workload}")


def drop_caches():
    """Best-effort page-cache drop so reads hit the device, not RAM."""
    try:
        subprocess.run("sync", shell=True, check=False)
        subprocess.run("echo 3 | sudo tee /proc/sys/vm/drop_caches",
                       shell=True, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # non-fatal; recorded as a note by the caller if it fails


class Telemetry:
    """Capture guest CPU telemetry (mpstat) alongside the measured window."""
    def __init__(self, out_path, duration_s):
        self.out_path = out_path
        self.duration_s = duration_s
        self.proc = None

    def start(self):
        try:
            f = open(self.out_path, "w")
            self.proc = subprocess.Popen(
                ["mpstat", "1", str(self.duration_s)],
                stdout=f, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            self.proc = None  # sysstat not installed; telemetry left blank

    def stop(self):
        if self.proc:
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()


def execute_run(run, target, raw_dir, warmup_s, duration_s, dry_run=False):
    """Execute one run. Returns a result dict describing what happened.

    On any failure the run is recorded with status=failed and an error note;
    NO metric is fabricated. parse_results.py will leave failed cells blank.
    """
    run_id = run["run_id"]
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = str(raw_dir / f"{run_id}.elbencho.csv")
    log_path = str(raw_dir / f"{run_id}.stdout.log")
    tel_path = str(raw_dir / f"{run_id}.mpstat.txt")

    azure_object = (run["provider"] == "azure" and run["paradigm"] == "object")
    if azure_object:
        tool = "azure_blob_sdk"
        argv = ["python3", str(Path(__file__).parent / "azure_blob_runner.py"),
                "--workload", run["workload"], "--concurrency", str(run["concurrency"]),
                "--duration", str(duration_s), "--container", target,
                "--csvfile", csv_path]
    else:
        tool = "elbencho"
        # AWS object runs: derive the regional S3 endpoint if none was given
        # (credentials come from the instance role, so no keys are set).
        if run["paradigm"] == "object" and run["provider"] == "aws":
            region = (os.environ.get("AWS_REGION")
                      or os.environ.get("AWS_DEFAULT_REGION") or "af-south-1")
            os.environ.setdefault("S3_ENDPOINT",
                                  f"https://s3.{region}.amazonaws.com")
            os.environ.setdefault("S3_REGION", region)
            _refresh_aws_role_creds()
        argv = _elbencho_flags(run["paradigm"], run["workload"], target,
                               run["concurrency"], csv_path)

    result = {"run_id": run_id, "tool": tool, "target": target,
              "raw_csv": csv_path, "raw_log": log_path, "telemetry": tel_path,
              "warmup_s": warmup_s, "duration_s": duration_s,
              "status": "planned", "cmd": _redacted_cmd(argv),
              "error": ""}

    if dry_run:
        result["status"] = "dry-run"
        return result

    # Read-only workloads run against freshly provisioned (empty) storage, so
    # first lay down the dataset with one silent prep write pass.
    if tool == "elbencho" and run["workload"] in ("read", "largeobj"):
        prep = ["-w" if a == "-r" else a for a in argv]
        prep[prep.index(csv_path)] = csv_path + ".prep"
        try:
            subprocess.run(prep, timeout=duration_s + 300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass  # if prep failed, the measured run will fail visibly below

    # 1) drop caches, 2) warm up, 3) start telemetry, 4) measured window
    drop_caches()
    if warmup_s > 0:
        warm = list(argv)
        try:
            subprocess.run(warm, timeout=warmup_s + 30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    tel = Telemetry(tel_path, duration_s)
    tel.start()
    t0 = time.time()
    try:
        with open(log_path, "w") as log:
            cp = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                                timeout=duration_s + 300)
        result["returncode"] = cp.returncode
        result["status"] = "ok" if cp.returncode == 0 else "failed"
        if cp.returncode != 0:
            result["error"] = f"tool exited {cp.returncode}; see {log_path}"
    except FileNotFoundError as e:
        result["status"] = "failed"
        result["error"] = f"tool not found: {e}. Install elbencho on this host."
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "measurement timed out"
    finally:
        tel.stop()
        result["measured_wall_s"] = round(time.time() - t0, 1)
    return result
