#!/usr/bin/env bash
# leak_check.sh [provider ...] -- list anything this harness may have left
# running. Uses each provider's CLI; skips providers whose CLI is absent.
# ANY output under a provider means something is still billing you.
set -uo pipefail
PROVIDERS=("$@")
[ ${#PROVIDERS[@]} -eq 0 ] && PROVIDERS=(aws azure gcp)

for p in "${PROVIDERS[@]}"; do
  echo "=============================== $p ==============================="
  case "$p" in
    aws)
      command -v aws >/dev/null || { echo "(aws CLI not installed, skipping)"; continue; }
      echo "-- EC2 instances (non-terminated):"
      aws ec2 describe-instances \
        --filters "Name=tag:Project,Values=cloud-storage-bench" \
        --query 'Reservations[].Instances[?State.Name!=`terminated`].[InstanceId,State.Name,InstanceType]' \
        --output text 2>/dev/null
      echo "-- EBS volumes:"
      aws ec2 describe-volumes --query 'Volumes[].[VolumeId,State,Size]' --output text 2>/dev/null
      echo "-- EFS filesystems:"
      aws efs describe-file-systems --query 'FileSystems[].[FileSystemId,LifeCycleState]' --output text 2>/dev/null
      echo "-- S3 benchmark buckets:"
      aws s3 ls 2>/dev/null | grep 'csb-bench' || true
      ;;
    azure)
      command -v az >/dev/null || { echo "(az CLI not installed, skipping)"; continue; }
      echo "-- resources in csb-bench-rg:"
      az resource list -g csb-bench-rg -o table 2>/dev/null || echo "(resource group gone -- good)"
      ;;
    gcp)
      command -v gcloud >/dev/null || { echo "(gcloud not installed, skipping)"; continue; }
      echo "-- compute instances:"
      gcloud compute instances list --filter="labels.project=cloud-storage-bench" 2>/dev/null
      echo "-- disks:"
      gcloud compute disks list 2>/dev/null | grep -i csb || true
      echo "-- buckets:"
      gsutil ls 2>/dev/null | grep csb-bench || true
      ;;
    *)
      echo "(no automated leak check for $p -- check the console manually:"
      echo " ECS/EVS/OBS for huawei, ECS/disks/OSS for alibaba)"
      ;;
  esac
  echo
done
echo "Empty output under a provider = clean. Anything listed is still billing."
