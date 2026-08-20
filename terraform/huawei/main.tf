terraform {
  required_providers {
    huaweicloud = { source = "huaweicloud/huaweicloud", version = "~> 1.60" }
    random      = { source = "hashicorp/random", version = "~> 3.0" }
  }
}
# Runs ON the benchmark host. Auth: env HW_ACCESS_KEY / HW_SECRET_KEY.
provider "huaweicloud" { region = var.region }

resource "random_string" "s" {
  length  = 8
  upper   = false
  special = false
}

# ----- OBJECT (OBS, S3-compatible; benchmarked by elbencho S3 mode) -----
resource "huaweicloud_obs_bucket" "obj" {
  count         = var.paradigm == "object" ? 1 : 0
  bucket        = "csb-bench-${random_string.s.result}"
  acl           = "private"
  force_destroy = true
}

# ----- Host + network discovery (created by hosts/huawei) -----
data "huaweicloud_compute_instance" "host" {
  count = var.paradigm != "object" ? 1 : 0
  name  = var.host_name
}
data "huaweicloud_vpc" "csb" {
  count = var.paradigm == "file" ? 1 : 0
  name  = "csb-bench-vpc"
}
data "huaweicloud_vpc_subnet" "csb" {
  count = var.paradigm == "file" ? 1 : 0
  name  = "csb-bench-subnet"
}
data "huaweicloud_networking_secgroup" "csb" {
  count = var.paradigm == "file" ? 1 : 0
  name  = "csb-bench-sg"
}

# ----- BLOCK (EVS volume, attached and mounted on the host) -----
resource "huaweicloud_evs_volume" "block" {
  count             = var.paradigm == "block" ? 1 : 0
  name              = "csb-bench-block"
  availability_zone = data.huaweicloud_compute_instance.host[0].availability_zone
  volume_type       = "SSD"
  size              = var.volume_gb
}
resource "huaweicloud_compute_volume_attach" "block" {
  count       = var.paradigm == "block" ? 1 : 0
  instance_id = data.huaweicloud_compute_instance.host[0].id
  volume_id   = huaweicloud_evs_volume.block[0].id

  provisioner "local-exec" {
    # Newly attached virtio disk: first unmounted, non-root data disk.
    command = <<-CMD
      set -e
      DEV=""
      for i in $(seq 1 60); do
        for c in /dev/vdb /dev/vdc /dev/vdd /dev/sdb /dev/sdc; do
          [ -b "$c" ] || continue
          MNT=$(lsblk -no MOUNTPOINT "$c" | tr -d '[:space:]')
          [ -z "$MNT" ] && { DEV="$c"; break; }
        done
        [ -n "$DEV" ] && break
        sleep 2
      done
      [ -n "$DEV" ] || { echo "attached EVS device not found"; exit 1; }
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

# ----- FILE (SFS Turbo, NFS; service minimum 500 GB) -----
# NFS traffic must be allowed inside the VPC (the host SG only opens SSH).
resource "huaweicloud_networking_secgroup_rule" "nfs" {
  count             = var.paradigm == "file" ? 1 : 0
  security_group_id = data.huaweicloud_networking_secgroup.csb[0].id
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "10.45.0.0/16" # the csb-bench-vpc CIDR
}
resource "huaweicloud_sfs_turbo" "file" {
  count             = var.paradigm == "file" ? 1 : 0
  name              = "csb-bench-file"
  size              = 500 # SFS Turbo minimum; disclose vs the 100 GB elsewhere
  share_proto       = "NFS"
  availability_zone = data.huaweicloud_compute_instance.host[0].availability_zone
  vpc_id            = data.huaweicloud_vpc.csb[0].id
  subnet_id         = data.huaweicloud_vpc_subnet.csb[0].id
  security_group_id = data.huaweicloud_networking_secgroup.csb[0].id

  provisioner "local-exec" {
    command = <<-CMD
      set -e
      sudo mkdir -p ${var.mount_file}
      sudo umount ${var.mount_file} 2>/dev/null || true
      for i in $(seq 1 30); do
        sudo mount -t nfs -o vers=3,nolock \
          ${self.export_location} ${var.mount_file} && break
        sleep 10
      done
      mountpoint -q ${var.mount_file} || { echo "SFS Turbo mount failed"; exit 1; }
      sudo chmod 777 ${var.mount_file}
    CMD
  }
  provisioner "local-exec" {
    when = destroy
    # destroy provisioners cannot reference var.*; path matches mount_file default
    command = "sudo umount /mnt/file || true"
  }
}
