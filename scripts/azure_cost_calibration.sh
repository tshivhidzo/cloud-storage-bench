#!/usr/bin/env bash
# azure_cost_calibration.sh -- make Azure Files/Blob capacity charges large
# enough to resolve in the billing export, so their rates can be derived the
# same way as every other cell (billed cost / billed GB-months).
#
# What it does: creates one storage account with ~100 GB in a blob container
# and ~100 GB in a file share. Only 1 GB is uploaded from the laptop; the rest
# is produced by SERVER-SIDE copies, so the upload takes minutes, not hours.
#
# Usage (Git Bash, az logged in):
#   ./scripts/azure_cost_calibration.sh up      # create + fill (leave 48 h)
#   ./scripts/azure_cost_calibration.sh down    # destroy everything
#
# Expected spend for a 48 h window at southafricanorth standard rates:
# blob ~ $0.15, files ~ $0.45 -- both comfortably above billing resolution.
set -euo pipefail

RG="csb-cal-rg"
LOC="southafricanorth"
SA="csbcal$(date +%s | tail -c 7)"   # unique-ish account name
COPIES=99                            # 1 seed + 99 copies = ~100 GB each

if [ "${1:-}" = "down" ]; then
  RG_EXIST=$(az group exists -n "$RG")
  if [ "$RG_EXIST" = "true" ]; then
    az group delete -n "$RG" --yes
    echo "calibration resources deleted."
  else
    echo "nothing to delete."
  fi
  exit 0
fi

[ "${1:-}" = "up" ] || { echo "usage: $0 up|down"; exit 1; }

echo "== creating resource group + storage account =="
az group create -n "$RG" -l "$LOC" -o none
az storage account create -n "$SA" -g "$RG" -l "$LOC" \
  --sku Standard_LRS --kind StorageV2 -o none
KEY=$(az storage account keys list -n "$SA" -g "$RG" --query "[0].value" -o tsv)

az storage container create -n cal --account-name "$SA" --account-key "$KEY" -o none
az storage share create -n cal --quota 120 --account-name "$SA" --account-key "$KEY" -o none

echo "== generating 1 GB seed file locally =="
SEED="$(mktemp -d)/seed.bin"
python - "$SEED" <<'EOF'
import os, sys
with open(sys.argv[1], 'wb') as f:
    for _ in range(1024):
        f.write(os.urandom(1024 * 1024))
EOF

echo "== uploading seed (once) to blob and file share =="
az storage blob upload -f "$SEED" -c cal -n seed.bin \
  --account-name "$SA" --account-key "$KEY" --overwrite -o none
az storage file upload -s cal --source "$SEED" -p seed.bin \
  --account-name "$SA" --account-key "$KEY" -o none
rm -f "$SEED"

echo "== fanning out ${COPIES} server-side copies (no further upload) =="
SRC_BLOB="https://${SA}.blob.core.windows.net/cal/seed.bin"
SRC_FILE="https://${SA}.file.core.windows.net/cal/seed.bin"
for i in $(seq 1 $COPIES); do
  az storage blob copy start --source-uri "$SRC_BLOB" \
    --destination-container cal --destination-blob "copy_${i}.bin" \
    --account-name "$SA" --account-key "$KEY" -o none
  az storage file copy start --source-uri "$SRC_FILE" \
    --destination-share cal --destination-path "copy_${i}.bin" \
    --account-name "$SA" --account-key "$KEY" -o none
  printf '\rcopies started: %d/%d' "$i" "$COPIES"
done
echo

echo "== done =="
echo "account: $SA   resource group: $RG"
echo "Leave this running for 48 hours, then allow ~24 h billing lag before"
echo "exporting Cost analysis (group by Meter) for the calibration window."
echo "Tear down with:  $0 down"
