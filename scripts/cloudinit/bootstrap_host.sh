#!/bin/bash
# ---------------------------------------------------------------------------
# bootstrap_host.sh -- cloud-init user-data for every benchmark host.
# Brings an Ubuntu 22.04 VM up fully ready to run the campaign: measurement
# tools, Terraform, elbencho (with S3 support), the cloud SDKs, and a billing
# guardrail that powers the host off after ${AUTO_SHUTDOWN_HOURS} hours.
#
# Templated variables (substituted by Terraform):
#   ${AUTO_SHUTDOWN_HOURS}   integer hours before self-shutdown (0 = disabled)
#   ${ELBENCHO_VERSION}      elbencho release to install
# ---------------------------------------------------------------------------
set -euxo pipefail
exec > >(tee -a /var/log/csb-bootstrap.log) 2>&1
export DEBIAN_FRONTEND=noninteractive

echo "=== csb bootstrap starting $(date -u) ==="

apt-get update
apt-get install -y \
  python3 python3-pip python3-venv \
  sysstat ifstat fio \
  nfs-common jq unzip curl wget git gnupg software-properties-common \
  lsb-release ca-certificates apt-transport-https

# --- Terraform (the harness provisions its own storage targets from the host) --
curl -fsSL https://apt.releases.hashicorp.com/gpg \
  | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  > /etc/apt/sources.list.d/hashicorp.list
apt-get update && apt-get install -y terraform

# --- elbencho, built WITH S3 support (drives all three paradigms) -------------
EB_VER="${ELBENCHO_VERSION}"
# Release assets are named without a version: elbencho-static_amd64.deb
EB_DEB="elbencho-static_amd64.deb"
if curl -fsSL -o "/tmp/$${EB_DEB}" \
   "https://github.com/breuner/elbencho/releases/download/v$${EB_VER}/$${EB_DEB}"; then
  apt-get install -y "/tmp/$${EB_DEB}" || dpkg -i "/tmp/$${EB_DEB}" || true
else
  echo "WARNING: elbencho $${EB_VER} .deb not fetched. Install it manually and" \
       "confirm 'elbencho --version' reports S3 support before running." \
       | tee /etc/motd.csb
fi

# --- Python SDKs used by the runners -----------------------------------------
pip3 install --upgrade pip
pip3 install boto3 azure-storage-blob google-cloud-storage pandas matplotlib

# --- sysstat data collection on (mpstat telemetry) ---------------------------
sed -i 's/^ENABLED=.*/ENABLED="true"/' /etc/default/sysstat || true
systemctl enable --now sysstat || true

# --- Passwordless sudo for the mount/drop-caches steps the harness performs ---
echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/90-csb-benchmark
chmod 440 /etc/sudoers.d/90-csb-benchmark

# --- Billing guardrail: self-shutdown so a forgotten host cannot bill for days -
if [ "${AUTO_SHUTDOWN_HOURS}" -gt 0 ]; then
  MINUTES=$(( ${AUTO_SHUTDOWN_HOURS} * 60 ))
  shutdown -h +$${MINUTES} "csb: auto-shutdown after ${AUTO_SHUTDOWN_HOURS}h" || true
  cat > /etc/motd.csb <<MOTD

  *** cloud-storage-bench benchmark host ***
  This host will POWER OFF automatically after ${AUTO_SHUTDOWN_HOURS} hours.
  Cancel with:  sudo shutdown -c
  Re-arm with:  sudo shutdown -h +MINUTES
  A long campaign may outlive this timer -- cancel it before a full run.

MOTD
  cat /etc/motd.csb >> /etc/motd || true
fi

# --- Readiness marker the launch script polls for ----------------------------
touch /var/lib/csb-bootstrap-complete
echo "=== csb bootstrap finished $(date -u) ==="
