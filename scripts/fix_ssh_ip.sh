#!/usr/bin/env bash
# fix_ssh_ip.sh [provider ...] -- re-point each host's SSH rule at your current
# public IP after it changes. Touches ONLY the SSH firewall/security-group
# resource (terraform -target), never the hosts themselves, so a running
# campaign is not disturbed.
#   ./scripts/fix_ssh_ip.sh gcp aws azure
#   ./scripts/fix_ssh_ip.sh            # defaults to gcp aws azure
# Optional: SSH_CIDR_WIDTH=24 to allow your provider's /24 instead of one /32.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${SSH_PUBLIC_KEY_FILE:-$HOME/.ssh/id_rsa.pub}"
PROVIDERS=("$@"); [ ${#PROVIDERS[@]} -eq 0 ] && PROVIDERS=(gcp aws azure)

MYIP="$(curl -fsS https://checkip.amazonaws.com || curl -fsS https://ifconfig.me)"
MYIP="$(echo "$MYIP" | tr -d '[:space:]')"
case "${SSH_CIDR_WIDTH:-32}" in
  16) CIDR="${MYIP%.*.*}.0.0/16" ;;
  24) CIDR="${MYIP%.*}.0/24" ;;
  *)  CIDR="$MYIP/32" ;;
esac
echo "Re-pointing SSH to $CIDR for: ${PROVIDERS[*]}"

COMMON=(-input=false -auto-approve -no-color
        -var "ssh_public_key=$(cat "$KEY")" -var "operator_cidr=$CIDR"
        -var "second_client=true" -var "auto_shutdown_hours=0")

for p in "${PROVIDERS[@]}"; do
  case "$p" in
    gcp)     TGT=(-target=google_compute_firewall.ssh)
             EXTRA=(-var "project=${GCP_PROJECT:-multi-cloud-420821}") ;;
    aws)     TGT=(-target=aws_security_group.csb);              EXTRA=() ;;
    azure)   TGT=(-target=azurerm_network_security_group.csb);  EXTRA=() ;;
    alibaba) TGT=(-target=alicloud_security_group_rule.ssh);    EXTRA=() ;;
    huawei)  TGT=(-target=huaweicloud_networking_secgroup_rule.ssh); EXTRA=() ;;
    *) echo "unknown provider $p"; continue ;;
  esac
  echo; echo "=== $p ==="
  OUT="$(terraform -chdir="$ROOT/terraform/hosts/$p" apply "${COMMON[@]}" "${EXTRA[@]}" "${TGT[@]}" 2>&1)"
  RESULT="$(echo "$OUT" | grep -E "^Apply complete|^Error|Resources:" | head -3)"
  echo "${RESULT:-$(echo "$OUT" | tail -15)}"
  if echo "$OUT" | grep -qE "Resources: [0-9]+ added, [0-9]+ changed, [1-9][0-9]* destroyed|Resources: [1-9][0-9]* added"; then
    if [ "$p" != "alibaba" ] && [ "$p" != "huawei" ]; then
      echo "!!! $p: something other than the SSH rule was added or destroyed -- STOP and check"
    fi
  fi
done
echo; echo "Done. Test with: ssh ubuntu@<host ip> hostname"
