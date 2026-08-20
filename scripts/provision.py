#!/usr/bin/env python3
"""
provision.py -- one consistent interface over the per-provider Terraform modules
in terraform/<provider>/. Each module exposes var.paradigm and var.region and
outputs `target` (a POSIX mount path for block/file, or a bucket/container name
for object) and `region`. run_campaign.py calls provision() before a run and
teardown() after it, so no target outlives its measurement (and its bill).

This does NOT invent infrastructure. If a provider's module is a stub or
Terraform is missing, provision() raises and the run is recorded as failed.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

TF_ROOT = Path(__file__).resolve().parent.parent / "terraform"


def _tf(provider):
    d = TF_ROOT / provider
    if not d.is_dir():
        raise FileNotFoundError(f"no terraform module for provider '{provider}' at {d}")
    return d


def _run(cmd, cwd):
    cp = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError(
            f"terraform failed ({' '.join(cmd)}):\n{cp.stderr[-2000:]}")
    return cp.stdout


def provision(provider, paradigm, region=None):
    """Apply the module and return {'target':..., 'region':...}."""
    d = _tf(provider)
    region = region or os.environ.get(f"{provider.upper()}_REGION", "")
    vars = ["-var", f"paradigm={paradigm}"]
    if region:
        vars += ["-var", f"region={region}"]
    # init is idempotent; safe to call each time
    _run(["terraform", "init", "-input=false", "-no-color"], d)
    _run(["terraform", "apply", "-input=false", "-auto-approve", "-no-color", *vars], d)
    out = json.loads(_run(["terraform", "output", "-json"], d))
    # Any output named env_FOO is exported as environment variable FOO for the
    # runner (e.g. env_AZURE_STORAGE_CONNECTION_STRING). Values never touch disk.
    for k, v in out.items():
        if k.startswith("env_") and v.get("value"):
            os.environ[k[4:]] = str(v["value"])
    target = out.get("target", {}).get("value")
    if not target:
        raise RuntimeError(
            f"{provider}/{paradigm}: module applied but no 'target' output. "
            "Complete the module so it outputs a mount path or bucket name.")
    return {"target": target, "region": out.get("region", {}).get("value", region)}


def teardown(provider, paradigm, region=None):
    d = _tf(provider)
    region = region or os.environ.get(f"{provider.upper()}_REGION", "")
    vars = ["-var", f"paradigm={paradigm}"]
    if region:
        vars += ["-var", f"region={region}"]
    _run(["terraform", "destroy", "-input=false", "-auto-approve", "-no-color", *vars], d)
    return True


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Provision/teardown one target")
    ap.add_argument("action", choices=["provision", "teardown"])
    ap.add_argument("provider")
    ap.add_argument("paradigm")
    ap.add_argument("--region", default=None)
    a = ap.parse_args()
    if a.action == "provision":
        print(json.dumps(provision(a.provider, a.paradigm, a.region), indent=2))
    else:
        teardown(a.provider, a.paradigm, a.region)
        print("torn down")
