#!/usr/bin/env python3
"""
auth_preflight.py -- verify, per provider, that credentials are present, that the
identity resolves, and (best effort) that storage permissions exist. Stores NO
secrets and prints NONE: only presence and a masked fingerprint. Writes
results/auth_report.json so the access state travels with the dataset.
Use --strict to exit non-zero if any requested provider is not ready.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

PROVIDERS = ["aws", "azure", "gcp", "huawei", "alibaba"]


def fp(val):  # masked fingerprint, never the secret itself
    if not val:
        return None
    return "sha256:" + hashlib.sha256(val.encode()).hexdigest()[:12]


def have(cmd):
    return shutil.which(cmd) is not None


def _run(cmd):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return cp.returncode == 0, (cp.stdout or cp.stderr)[:400]
    except Exception as e:
        return False, str(e)


def check_aws():
    r = {"provider": "aws",
         "env_present": bool(os.environ.get("AWS_ACCESS_KEY_ID")),
         "key_fingerprint": fp(os.environ.get("AWS_ACCESS_KEY_ID")),
         "cli": have("aws")}
    if r["cli"]:
        ok, out = _run(["aws", "sts", "get-caller-identity", "--output", "json"])
        r["identity_resolves"] = ok
        r["region"] = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", ""))
    else:
        r["identity_resolves"] = False
    r["ready"] = bool(r["cli"] and r["identity_resolves"])
    return r


def check_azure():
    r = {"provider": "azure",
         "env_present": bool(os.environ.get("AZURE_STORAGE_ACCOUNT")),
         "account_fingerprint": fp(os.environ.get("AZURE_STORAGE_ACCOUNT")),
         "cli": have("az")}
    if r["cli"]:
        ok, _ = _run(["az", "account", "show", "-o", "json"])
        r["identity_resolves"] = ok
    else:
        r["identity_resolves"] = False
    r["ready"] = bool(r["cli"] and r["identity_resolves"])
    return r


def check_gcp():
    r = {"provider": "gcp",
         "env_present": bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                             or os.environ.get("GCP_HMAC_ACCESS_KEY")),
         "hmac_fingerprint": fp(os.environ.get("GCP_HMAC_ACCESS_KEY")),
         "cli": have("gcloud")}
    if r["cli"]:
        ok, _ = _run(["gcloud", "auth", "list", "--format=json"])
        r["identity_resolves"] = ok
    else:
        r["identity_resolves"] = False
    r["ready"] = bool(r["env_present"] and (r["identity_resolves"] or r["hmac_fingerprint"]))
    return r


def check_generic_s3(name, key_env, secret_env, endpoint_env):
    r = {"provider": name,
         "env_present": bool(os.environ.get(key_env)),
         "key_fingerprint": fp(os.environ.get(key_env)),
         "endpoint": os.environ.get(endpoint_env, ""),
         "secret_present": bool(os.environ.get(secret_env))}
    r["identity_resolves"] = None  # verified at first S3 call
    r["ready"] = bool(r["env_present"] and r["secret_present"] and r["endpoint"])
    return r


CHECKS = {
    "aws": check_aws, "azure": check_azure, "gcp": check_gcp,
    "huawei": lambda: check_generic_s3("huawei", "HUAWEI_ACCESS_KEY",
                                       "HUAWEI_SECRET_KEY", "HUAWEI_OBS_ENDPOINT"),
    "alibaba": lambda: check_generic_s3("alibaba", "ALIBABA_ACCESS_KEY",
                                        "ALIBABA_SECRET_KEY", "ALIBABA_OSS_ENDPOINT"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", default="all")
    ap.add_argument("--out", default="results/auth_report.json")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    provs = PROVIDERS if a.providers == "all" else [p.strip() for p in a.providers.split(",")]
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "providers": {}}
    not_ready = []
    for p in provs:
        res = CHECKS[p]()
        report["providers"][p] = res
        state = "READY" if res.get("ready") else "NOT READY"
        print(f"{p:9} {state}  (cli={res.get('cli')}, identity={res.get('identity_resolves')})")
        if not res.get("ready"):
            not_ready.append(p)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=2))
    print(f"\nWrote {a.out} (no secrets stored).")
    if not_ready:
        print("Not ready:", ", ".join(not_ready))
        if a.strict:
            sys.exit(f"--strict: {len(not_ready)} provider(s) not ready. Fix before running.")


if __name__ == "__main__":
    main()
