terraform {
  required_providers {
    aws      = { source = "hashicorp/aws",      version = "~> 5.0" }
    external = { source = "hashicorp/external", version = "~> 2.3" }
  }
}
provider "aws" { region = var.region }

# --- Discover this benchmark host from instance metadata (IMDSv2) ------------
# The hashicorp/http data source cannot do the PUT that IMDSv2 requires, so we
# shell out to curl (IMDSv2 first, IMDSv1 fallback).
data "external" "iid" {
  program = ["bash", "-c", <<-EOT
    TOKEN=$(curl -sf -X PUT -H "X-aws-ec2-metadata-token-ttl-seconds: 60" \
      http://169.254.169.254/latest/api/token || true)
    if [ -n "$TOKEN" ]; then
      ID=$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
        http://169.254.169.254/latest/meta-data/instance-id)
    else
      ID=$(curl -sf http://169.254.169.254/latest/meta-data/instance-id)
    fi
    printf '{"id":"%s"}' "$ID"
  EOT
  ]
}
locals {
  self_instance_id = var.instance_id != "" ? var.instance_id : data.external.iid.result.id
}
data "aws_instance" "host" { instance_id = local.self_instance_id }

# =========================== OBJECT (S3) ====================================
resource "aws_s3_bucket" "obj" {
  count         = var.paradigm == "object" ? 1 : 0
  bucket_prefix = "csb-bench-"
  force_destroy = true
}

# =========================== BLOCK (EBS) ====================================
resource "aws_ebs_volume" "block" {
  count             = var.paradigm == "block" ? 1 : 0
  availability_zone = data.aws_instance.host.availability_zone
  size              = var.volume_gb
  type              = "gp3"
}
resource "aws_volume_attachment" "block" {
  count       = var.paradigm == "block" ? 1 : 0
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.block[0].id
  instance_id = local.self_instance_id
  # format (once) and mount on the host running terraform.
  # The device is located by EBS volume id (NVMe serial) -- size-based
  # detection is ambiguous because the root disk can have the same size.
  provisioner "local-exec" {
    command = <<-CMD
      set -e
      VOLID="${replace(aws_ebs_volume.block[0].id, "-", "")}"
      DEV=""
      for i in $(seq 1 60); do
        CAND="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_$${VOLID}"
        if [ -e "$CAND" ]; then DEV="$(readlink -f "$CAND")"; break; fi
        sleep 2
      done
      [ -n "$DEV" ] && [ -b "$DEV" ] || { echo "EBS device for $${VOLID} not found"; exit 1; }
      sudo blkid "$DEV" || sudo mkfs.ext4 -F "$DEV"
      sudo mkdir -p ${var.mount_block}
      sudo umount ${var.mount_block} 2>/dev/null || true
      sudo mount "$DEV" ${var.mount_block}
      sudo chmod 777 ${var.mount_block}
    CMD
  }
  provisioner "local-exec" {
    when    = destroy
    # NOTE: destroy provisioners cannot reference var.*; path must match var.mount_block default
    command = "sudo umount /mnt/block || true"
  }
}

# =========================== FILE (EFS) =====================================
resource "aws_efs_file_system" "file" {
  count           = var.paradigm == "file" ? 1 : 0
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"
}
resource "aws_efs_mount_target" "file" {
  count           = var.paradigm == "file" ? 1 : 0
  file_system_id  = aws_efs_file_system.file[0].id
  subnet_id       = var.subnet_id != "" ? var.subnet_id : data.aws_instance.host.subnet_id
  security_groups = data.aws_instance.host.vpc_security_group_ids
  provisioner "local-exec" {
    command = <<-CMD
      set -e
      sudo mkdir -p ${var.mount_file}
      for i in $(seq 1 30); do
        sudo mount -t nfs4 -o nfsvers=4.1 \
          ${aws_efs_file_system.file[0].dns_name}:/ ${var.mount_file} && break
        sleep 10
      done
      sudo chmod 777 ${var.mount_file}
    CMD
  }
  provisioner "local-exec" {
    when    = destroy
    # NOTE: destroy provisioners cannot reference var.*; path must match var.mount_file default
    command = "sudo umount /mnt/file || true"
  }
}
