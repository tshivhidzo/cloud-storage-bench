terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.0" }
  }
}
# Runs ON the benchmark host using the VM's service account (metadata creds).
# Set env GOOGLE_PROJECT=<project id> on the host.
provider "google" {
  project = var.project != "" ? var.project : null
  region  = var.region
}
resource "random_string" "s" {
  length  = 8
  upper   = false
  special = false
}

# ----- OBJECT (GCS; benchmarked via S3 interoperability endpoint + HMAC) -----
resource "google_storage_bucket" "obj" {
  count                       = var.paradigm == "object" ? 1 : 0
  name                        = "csb-bench-${random_string.s.result}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# ----- Host discovery (created by hosts/gcp) -----
data "google_compute_instance" "host" {
  count = var.paradigm != "object" ? 1 : 0
  name  = var.host_name
  zone  = var.zone
}

# ----- BLOCK (pd-ssd disk, attached and mounted on the host) -----
resource "google_compute_disk" "block" {
  count = var.paradigm == "block" ? 1 : 0
  name  = "csb-bench-block"
  type  = "pd-ssd"
  zone  = var.zone
  size  = var.volume_gb
}
resource "google_compute_attached_disk" "block" {
  count       = var.paradigm == "block" ? 1 : 0
  disk        = google_compute_disk.block[0].id
  instance    = data.google_compute_instance.host[0].id
  device_name = "csbblock" # exposed at /dev/disk/by-id/google-csbblock

  provisioner "local-exec" {
    command = <<-CMD
      set -e
      DEV=""
      for i in $(seq 1 60); do
        CAND="/dev/disk/by-id/google-csbblock"
        if [ -e "$CAND" ]; then DEV="$(readlink -f "$CAND")"; break; fi
        sleep 2
      done
      [ -n "$DEV" ] && [ -b "$DEV" ] || { echo "attached disk not found"; exit 1; }
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

# ----- FILE (Filestore, NFS; BASIC_HDD minimum 1024 GB) -----
resource "google_filestore_instance" "file" {
  count    = var.paradigm == "file" ? 1 : 0
  name     = "csb-bench-file"
  location = var.zone
  tier     = "BASIC_HDD"

  file_shares {
    name        = "bench"
    capacity_gb = 1024 # service minimum; disclose vs the 100 GB elsewhere
  }
  networks {
    network = "csb-bench-net"
    modes   = ["MODE_IPV4"]
  }

  provisioner "local-exec" {
    command = <<-CMD
      set -e
      sudo mkdir -p ${var.mount_file}
      sudo umount ${var.mount_file} 2>/dev/null || true
      for i in $(seq 1 30); do
        sudo mount -t nfs -o nfsvers=3,nolock \
          ${self.networks[0].ip_addresses[0]}:/bench ${var.mount_file} && break
        sleep 10
      done
      mountpoint -q ${var.mount_file} || { echo "Filestore mount failed"; exit 1; }
      sudo chmod 777 ${var.mount_file}
    CMD
  }
  provisioner "local-exec" {
    when = destroy
    # destroy provisioners cannot reference var.*; path matches mount_file default
    command = "sudo umount /mnt/file || true"
  }
}
