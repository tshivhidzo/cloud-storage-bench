#!/usr/bin/env bash
# teardown_all.sh [provider ...] -- destroy EVERYTHING this harness created:
# storage targets first, then the hosts and their VPCs. Defaults to all five.
# Run this the moment a campaign ends. Then run leak_check.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROVIDERS=("$@")
[ ${#PROVIDERS[@]} -eq 0 ] && PROVIDERS=(aws azure gcp huawei alibaba)
for p in "${PROVIDERS[@]}"; do
  echo "=============================== $p ==============================="
  for paradigm in object file block; do
    d="$ROOT/terraform/$p"
    if [ -d "$d" ]; then
      echo "-- destroying $p storage target ($paradigm)"
      (cd "$d" && terraform destroy -input=false -auto-approve \
          -var "paradigm=$paradigm" >/dev/null 2>&1) \
        && echo "   ok" || echo "   nothing to destroy / already gone"
    fi
  done
  if [ -d "$ROOT/terraform/hosts/$p" ]; then
    echo "-- destroying $p host"
    "$ROOT/scripts/host_down.sh" "$p" || echo "   host destroy reported an issue"
  fi
done
echo
echo "Now verify nothing survived:  ./scripts/leak_check.sh"
