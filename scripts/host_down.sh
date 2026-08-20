#!/usr/bin/env bash
# host_down.sh <provider> -- destroy that provider's benchmark host + its VPC.
set -euo pipefail
PROVIDER="${1:?usage: host_down.sh <provider>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/terraform/hosts/$PROVIDER"
KEY="${SSH_PUBLIC_KEY_FILE:-$HOME/.ssh/id_rsa.pub}"
EXTRA=()
[ "$PROVIDER" = "gcp" ] && EXTRA+=(-var "project=${GCP_PROJECT:-}")
cd "$DIR"
terraform destroy -input=false -auto-approve \
  -var "ssh_public_key=$(cat "$KEY" 2>/dev/null || echo x)" \
  -var "operator_cidr=0.0.0.0/32" "${EXTRA[@]}"
echo "$PROVIDER host destroyed."
