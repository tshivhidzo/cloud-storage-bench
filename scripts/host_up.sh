#!/usr/bin/env bash
# host_up.sh <provider> -- bring up one benchmark host (Git Bash friendly).
#   ./scripts/host_up.sh aws
# Auto-detects your public IP so SSH is locked to you, passes your SSH public
# key, applies the host module, then waits for cloud-init to finish.
set -euo pipefail
PROVIDER="${1:?usage: host_up.sh <aws|azure|gcp|huawei|alibaba>}"
KEY="${SSH_PUBLIC_KEY_FILE:-$HOME/.ssh/id_rsa.pub}"
HOURS="${AUTO_SHUTDOWN_HOURS:-8}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/terraform/hosts/$PROVIDER"
[ -d "$DIR" ] || { echo "no host module for '$PROVIDER'"; exit 1; }
[ -f "$KEY" ] || { echo "no SSH public key at $KEY (set SSH_PUBLIC_KEY_FILE)"; exit 1; }

MYIP="$(curl -fsS https://checkip.amazonaws.com || curl -fsS https://ifconfig.me)"
MYIP="$(echo "$MYIP" | tr -d '[:space:]')"
echo "Locking SSH to your IP: ${MYIP}/32"

EXTRA=()
if [ "$PROVIDER" = "gcp" ]; then
  EXTRA+=(-var "project=${GCP_PROJECT:?set GCP_PROJECT for gcp}")
fi

cd "$DIR"
terraform init -input=false
terraform apply -input=false -auto-approve \
  -var "ssh_public_key=$(cat "$KEY")" \
  -var "operator_cidr=${MYIP}/32" \
  -var "auto_shutdown_hours=${HOURS}" \
  "${EXTRA[@]}"

IP="$(terraform output -raw host_ip)"
REGION="$(terraform output -raw region)"
LOCALITY="$(terraform output -raw locality)"
echo
echo "Host up: $PROVIDER  ip=$IP  region=$REGION  locality=$LOCALITY"
echo "Auto-shutdown in ${HOURS}h (cancel on host with: sudo shutdown -c)"
echo "Waiting for cloud-init to finish installing tools (a few minutes)..."
for i in $(seq 1 60); do
  if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "ubuntu@$IP" \
       'test -f /var/lib/csb-bootstrap-complete' 2>/dev/null; then
    echo "Bootstrap complete."
    ssh -o StrictHostKeyChecking=no "ubuntu@$IP" \
      'elbencho --version 2>/dev/null | head -1 || echo "WARNING: elbencho missing -- install it before running"'
    break
  fi
  sleep 15
done
echo
echo "Next:"
echo "  scp -r \"$ROOT\" ubuntu@$IP:~/"
echo "  ssh ubuntu@$IP"
echo "  cd cloud-storage-bench && python3 scripts/auth_preflight.py --providers $PROVIDER --strict"
