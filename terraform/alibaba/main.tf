terraform {
  required_providers {
    alicloud = { source = "aliyun/alicloud", version = "~> 1.220" }
    random   = { source = "hashicorp/random", version = "~> 3.0" }
  }
}
# Runs ON the benchmark host. Auth: env ALICLOUD_ACCESS_KEY /
# ALICLOUD_SECRET_KEY / ALICLOUD_REGION.
provider "alicloud" { region = var.region }

resource "random_string" "s" {
  length  = 8
  upper   = false
  special = false
}

# ----- OBJECT (OSS, S3-compatible; benchmarked by elbencho S3 mode) -----
resource "alicloud_oss_bucket" "obj" {
  count         = var.paradigm == "object" ? 1 : 0
  bucket        = "csb-bench-${random_string.s.result}"
  acl           = "private"
  force_destroy = true
}

# ----- Host discovery (created by hosts/alibaba) -----
data "alicloud_instances" "host" {
  count      = var.paradigm != "object" ? 1 : 0
  name_regex = "^${var.host_name}$"
  status     = "Running"
}

# ----- BLOCK (ESSD cloud disk, attached and mounted on the host) -----
resource "alicloud_ecs_disk" "block" {
  count     = var.paradigm == "block" ? 1 : 0
  disk_name = "csb-bench-block"
  zone_id   = data.alicloud_instances.host[0].instances[0].availability_zone
  category  = "cloud_essd"
  size      = var.volume_gb
}
resource "alicloud_ecs_disk_attachment" "block" {
  count       = var.paradigm == "block" ? 1 : 0
  disk_id     = alicloud_ecs_disk.block[0].id
  instance_id = data.alicloud_instances.host[0].instances[0].id

  provisioner "local-exec" {
    # Newly attached virtio disk: first unmounted, non-root data disk.
    command = <<-CMD
      set -e
      DEV=""
      for i in $(seq 1 60); do
        for c in /dev/vdb /dev/vdc /dev/vdd; do
          [ -b "$c" ] || continue
          MNT=$(lsblk -no MOUNTPOINT "$c" | tr -d '[:space:]')
          [ -z "$MNT" ] && { DEV="$c"; break; }
        done
        [ -n "$DEV" ] && break
        sleep 2
      done
      [ -n "$DEV" ] || { echo "attached cloud disk not found"; exit 1; }
      sudo blkid "$DEV" || sudo mkfs.ext4 -F "$DEV"
      sudo mkdir -p ${var.mount_block}
      sudo umount ${var.mount_block} 2>/dev/null || true
      sudo mount "$DEV" ${var.mount_block}
      sudo chmod 777 ${var.mount_block}
    CMD
  }
  provisioner "local-exec" {
    when = destroy
    # destroy provisioners cannot reference var.*; path matches mount_block default
    command = "sudo umount /mnt/block || true"
  }
}

# ----- FILE (Apsara NAS, NFS) -----
resource "alicloud_nas_file_system" "file" {
  count            = var.paradigm == "file" ? 1 : 0
  file_system_type = "standard"
  protocol_type    = "NFS"
  storage_type     = "Capacity"
  description      = "csb-bench-file"
}
resource "alicloud_nas_mount_target" "file" {
  count             = var.paradigm == "file" ? 1 : 0
  file_system_id    = alicloud_nas_file_system.file[0].id
  vswitch_id        = data.alicloud_instances.host[0].instances[0].vswitch_id
  access_group_name = "DEFAULT_VPC_GROUP_NAME"

  provisioner "local-exec" {
    command = <<-CMD
      set -e
      sudo mkdir -p ${var.mount_file}
      sudo umount ${var.mount_file} 2>/dev/null || true
      for i in $(seq 1 30); do
        sudo mount -t nfs -o vers=4.0 \
          ${self.mount_target_domain}:/ ${var.mount_file} && break
        sleep 10
      done
      mountpoint -q ${var.mount_file} || { echo "NAS mount failed"; exit 1; }
      sudo chmod 777 ${var.mount_file}
    CMD
  }
  provisioner "local-exec" {
    when = destroy
    # destroy provisioners cannot reference var.*; path matches mount_file default
    command = "sudo umount /mnt/file || true"
  }
}
