#!/usr/bin/env bash
# teardown_v21.sh -- consolidated, checked teardown of everything the v2.1
# rerun created, on all five clouds (or the ones named).
#
#   ./scripts/teardown_v21.sh --dry-run                 # show what would happen
#   ./scripts/teardown_v21.sh                           # all five, asks per provider
#   ./scripts/teardown_v21.sh --yes aws azure           # named providers, no prompts
#
# Run from the clone (~/publish/cloud-storage-bench-thesis-v1) in Git Bash,
# with each provider's credentials loaded in THIS window:
#   aws      usual AWS credentials (aws sts get-caller-identity works)
#   azure    az login (both scopes: management and graph)
#   gcp      gcloud logged in; export GCP_PROJECT=multi-cloud-420821
#   huawei   export HW_ACCESS_KEY / HW_SECRET_KEY        (from credentials.csv)
#   alibaba  export ALICLOUD_ACCESS_KEY / ALICLOUD_SECRET_KEY
# A provider whose credentials are missing is skipped, never half-destroyed.
#
# Per provider, in order:
#   1. credentials check
#   2. archive check: rerun_<provider>.tgz (and rerun_azure_mc2.tgz) must be in
#      ARCHIVE_DIR -- refuses otherwise (override with --force)
#   3. host check: storage Terraform state on the first host must be empty
#   4. leftover buckets: Alibaba orphan bucket(s) emptied and deleted via the
#      host; GCP and AWS csb-bench buckets listed and removed
#   5. storage modules and both hosts destroyed (second_client=true)
#   6. leak check (CLI for aws/azure/gcp; console checklist for huawei/alibaba)
#   7. reminder of the campaign keys to delete
# Nothing secret is written to the log; credentials reach a host only through
# ssh stdin and are never stored there.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE_DIR="${ARCHIVE_DIR:-/c/Users/Tshivhidzo/OneDrive - Cape Peninsula University of Technology/Thesis/2026/cloud-storage-bench}"
REMOTE="\$HOME/cloud-storage-bench-thesis-v1"
KEY="${SSH_PUBLIC_KEY_FILE:-$HOME/.ssh/id_rsa.pub}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
LOG="$ROOT/teardown_v21_$(date +%Y%m%d_%H%M%S).log"

DRY=0; YES=0; FORCE=0; PROVIDERS=()
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --yes)     YES=1 ;;
    --force)   FORCE=1 ;;
    aws|azure|gcp|huawei|alibaba) PROVIDERS+=("$a") ;;
    *) echo "unknown argument: $a"; exit 2 ;;
  esac
done
[ ${#PROVIDERS[@]} -eq 0 ] && PROVIDERS=(aws azure gcp huawei alibaba)

exec > >(tee -a "$LOG") 2>&1
say()  { printf '%s\n' "$*"; }
ok()   { printf '   [ok]   %s\n' "$*"; }
warn() { printf '   [WARN] %s\n' "$*"; }
bad()  { printf '   [STOP] %s\n' "$*"; }
run()  { if [ $DRY -eq 1 ]; then printf '   (dry-run) %s\n' "$*"; else "$@"; fi; }
ask()  { [ $YES -eq 1 ] && return 0; [ $DRY -eq 1 ] && return 0
         read -r -p "   $1 [y/N] " r < /dev/tty; [[ "$r" =~ ^[Yy]$ ]]; }
tfout(){ terraform -chdir="$ROOT/terraform/hosts/$1" output -raw "$2" 2>/dev/null | grep -E '^[0-9.]+$' || true; }

say "teardown_v21 $(date -u +%FT%TZ)  providers: ${PROVIDERS[*]}  dry-run=$DRY"
say "log: $LOG"
declare -A RESULT

creds_ok() {
  case "$1" in
    aws)     aws sts get-caller-identity --query Account --output text >/dev/null 2>&1 ;;
    azure)   [ "$(az account show --query state -o tsv 2>/dev/null)" = "Enabled" ] \
               && az account get-access-token --query expiresOn -o tsv >/dev/null 2>&1 \
               && az account get-access-token --resource-type ms-graph --query expiresOn -o tsv >/dev/null 2>&1 ;;
    gcp)     [ -n "${GCP_PROJECT:-}" ] && gcloud auth print-access-token >/dev/null 2>&1 ;;
    huawei)  [ ${#HW_ACCESS_KEY} -ge 16 ] 2>/dev/null && [ ${#HW_SECRET_KEY} -ge 30 ] 2>/dev/null ;;
    alibaba) [ ${#ALICLOUD_ACCESS_KEY} -ge 16 ] 2>/dev/null && [ ${#ALICLOUD_SECRET_KEY} -ge 20 ] 2>/dev/null ;;
  esac
}
: "${HW_ACCESS_KEY:=}" "${HW_SECRET_KEY:=}" "${ALICLOUD_ACCESS_KEY:=}" "${ALICLOUD_SECRET_KEY:=}"

archives_ok() {
  local need=("rerun_$1.tgz"); [ "$1" = "azure" ] && need+=("rerun_azure_mc2.tgz")
  local f missing=0
  for f in "${need[@]}"; do
    if [ -s "$ARCHIVE_DIR/$f" ]; then ok "archive present: $f"; else bad "archive missing: $ARCHIVE_DIR/$f"; missing=1; fi
  done
  return $missing
}

host_state_ok() {   # storage Terraform state on host 1 must be empty
  local p=$1 h; h=$(tfout "$p" host_ip)
  if [ -z "$h" ]; then ok "no host recorded in Terraform (already destroyed?)"; return 0; fi
  local n
  n=$("${SSH[@]}" "ubuntu@$h" "terraform -chdir=$REMOTE/terraform/$p state list 2>/dev/null | wc -l" 2>/dev/null)
  if [ -z "$n" ]; then warn "host $h not reachable over ssh (IP rule? run fix_ssh_ip.sh $p); state not checked"; return 0; fi
  if [ "$n" = "0" ]; then ok "storage state on host $h is empty"; return 0; fi
  bad "storage state on host $h still lists $n resource(s):"
  "${SSH[@]}" "ubuntu@$h" "terraform -chdir=$REMOTE/terraform/$p state list" 2>/dev/null | sed 's/^/          /'
  say "          destroy them on the host first, e.g. in its tmux window 0:"
  say "          terraform -chdir=$REMOTE/terraform/$p destroy -auto-approve -var paradigm=<object|file|block>"
  return 1
}

leftover_buckets() {
  local p=$1 h b
  case "$p" in
    alibaba)
      h=$(tfout alibaba host_ip)
      [ -z "$h" ] && { warn "no Alibaba host left; check OSS for csb-bench buckets in the console"; return; }
      if ! "${SSH[@]}" "ubuntu@$h" true 2>/dev/null; then
        warn "Alibaba host $h not reachable over ssh, so OSS buckets could NOT be listed;"
        warn "check OSS in the console for csb-bench-* buckets (known orphan: csb-bench-zc7vpqnd) and delete them there"
        return
      fi
      say "   listing csb-bench buckets on OSS (via host $h, keys passed on stdin only)"
      local listcmd='cd '"$REMOTE"'/sweep && python3 -c "import purge_s3 as p; [print(b[\"Name\"]) for b in p.client().list_buckets().get(\"Buckets\",[]) if b[\"Name\"].startswith(\"csb-bench\")]"'
      local env; env=$(printf 'export S3_ACCESS_KEY=%q S3_SECRET_KEY=%q S3_ENDPOINT=https://oss-me-central-1-internal.aliyuncs.com S3_REGION=me-central-1 S3_VIRT_ADDR=1\n' "$ALICLOUD_ACCESS_KEY" "$ALICLOUD_SECRET_KEY")
      local buckets; buckets=$(printf '%s\n%s\n' "$env" "$listcmd" | "${SSH[@]}" "ubuntu@$h" 'bash -s' 2>/dev/null)
      if [ -z "$buckets" ]; then ok "no csb-bench buckets on OSS"; return; fi
      for b in $buckets; do
        warn "OSS bucket still present: $b"
        if ask "empty and delete OSS bucket $b?"; then
          local del='cd '"$REMOTE"'/sweep && python3 purge_s3.py --bucket '"$b"' && python3 -c "import purge_s3 as p; p.client().delete_bucket(Bucket=\"'"$b"'\"); print(\"deleted '"$b"'\")"'
          if [ $DRY -eq 1 ]; then say "   (dry-run) empty + delete $b via host"; else printf '%s\n%s\n' "$env" "$del" | "${SSH[@]}" "ubuntu@$h" 'bash -s'; fi
        fi
      done ;;
    gcp)
      local list; list=$(gcloud storage ls --project="$GCP_PROJECT" 2>/dev/null | grep csb-bench || true)
      if [ -z "$list" ]; then ok "no csb-bench buckets on GCS"; return; fi
      for b in $list; do
        warn "GCS bucket still present: $b"
        ask "delete $b and all its objects?" && run gcloud storage rm -r "$b" --project="$GCP_PROJECT"
      done ;;
    aws)
      local list; list=$(aws s3 ls 2>/dev/null | awk '{print $3}' | grep '^csb-bench' || true)
      if [ -z "$list" ]; then ok "no csb-bench buckets on S3"; return; fi
      for b in $list; do
        warn "S3 bucket still present: $b"
        ask "delete s3://$b and all its objects?" && run aws s3 rb "s3://$b" --force
      done ;;
    *) : ;;
  esac
}

destroy_all() {
  local p=$1 para
  for para in object file block; do
    if [ -d "$ROOT/terraform/$p" ]; then
      if [ $DRY -eq 1 ]; then
        say "   (dry-run) terraform -chdir=terraform/$p destroy -var paradigm=$para"
      elif terraform -chdir="$ROOT/terraform/$p" destroy -input=false -auto-approve -no-color -var "paradigm=$para" >/dev/null 2>&1; then
        ok "laptop-side storage module ($para): nothing left"
      else
        warn "laptop-side storage module ($para): destroy reported an issue (usually: no state on the laptop)"
      fi
    fi
  done
  local extra=(); [ "$p" = "gcp" ] && extra+=(-var "project=$GCP_PROJECT")
  say "   destroying both hosts, network and identity"
  if run terraform -chdir="$ROOT/terraform/hosts/$p" destroy -input=false -auto-approve -no-color \
       -var "ssh_public_key=$(cat "$KEY" 2>/dev/null || echo x)" -var "operator_cidr=0.0.0.0/32" \
       -var "second_client=true" -var "auto_shutdown_hours=0" "${extra[@]}" | tail -3; then
    [ $DRY -eq 1 ] || ok "hosts destroyed"
  else
    bad "host destroy failed -- re-run for $p after reading the error above"; return 1
  fi
}

leak() {
  case "$1" in
    aws|azure|gcp) run "$ROOT/scripts/leak_check.sh" "$1" ;;
    huawei)  say "   Huawei console, region AF-Johannesburg: ECS, EVS, SFS Turbo, OBS (csb-bench-*), EIP, VPC must all be empty" ;;
    alibaba) say "   Alibaba console, region UAE (Dubai) me-central-1: ECS, Block Storage, NAS, OSS (csb-bench-*), EIP, VPC must all be empty" ;;
  esac
}

keys_reminder() {
  case "$1" in
    aws)     say "   keys: none campaign-specific (hosts used the instance role)" ;;
    azure)   say "   keys: none (managed identity, destroyed with the resource group)" ;;
    gcp)     say "   keys: delete the campaign HMAC key:"
             say "         gcloud storage hmac list --project=\$GCP_PROJECT"
             say "         gcloud storage hmac update <ACCESS_ID> --deactivate --project=\$GCP_PROJECT"
             say "         gcloud storage hmac delete <ACCESS_ID> --project=\$GCP_PROJECT" ;;
    huawei)  say "   keys: console > My Credentials > Access Keys: delete the campaign AK/SK; delete credentials.csv" ;;
    alibaba) say "   keys: RAM console > Users > csb-bench > AccessKey: delete the campaign key; delete the CSV" ;;
  esac
}

for p in "${PROVIDERS[@]}"; do
  say ""; say "=============================== $p ==============================="
  if ! creds_ok "$p"; then bad "credentials for $p not loaded in this window -- skipped"; RESULT[$p]="skipped (credentials)"; continue; fi
  ok "credentials loaded"
  if ! archives_ok "$p" && [ $FORCE -eq 0 ]; then RESULT[$p]="stopped (archive missing)"; continue; fi
  if ! host_state_ok "$p"; then RESULT[$p]="stopped (storage still in host state)"; continue; fi
  leftover_buckets "$p"
  if ! ask "destroy ALL $p resources now (hosts, network, storage)?"; then RESULT[$p]="not confirmed"; continue; fi
  if destroy_all "$p"; then
    leak "$p"; keys_reminder "$p"
    if [ $DRY -eq 1 ]; then RESULT[$p]="would be destroyed (dry run)"; else RESULT[$p]="destroyed -- confirm leak check, delete keys"; fi
  else
    RESULT[$p]="DESTROY FAILED -- check billing"
  fi
done

say ""; say "=============================== summary ==============================="
for p in "${PROVIDERS[@]}"; do printf '  %-8s %s\n' "$p" "${RESULT[$p]:-not run}"; done
say ""; say "Full log: $LOG"
[ $DRY -eq 1 ] && say "This was a dry run: nothing was destroyed."
