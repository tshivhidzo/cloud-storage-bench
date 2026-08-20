terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}
provider "google" {
  project = var.project
  region  = var.region
}

# ---------------------- Dedicated VPC ----------------------
resource "google_compute_network" "csb" {
  name                    = "csb-bench-net"
  auto_create_subnetworks = false
}
resource "google_compute_subnetwork" "csb" {
  name          = "csb-bench-subnet"
  ip_cidr_range = "10.44.1.0/24"
  region        = var.region
  network       = google_compute_network.csb.id
}
resource "google_compute_firewall" "ssh" {
  name          = "csb-bench-allow-ssh"
  network       = google_compute_network.csb.name
  source_ranges = [var.operator_cidr]
  target_tags   = ["csb-bench"]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
resource "google_compute_firewall" "nfs_internal" {
  name          = "csb-bench-allow-nfs-internal"
  network       = google_compute_network.csb.name
  source_ranges = ["10.44.0.0/16"]
  target_tags   = ["csb-bench"]
  allow {
    protocol = "tcp"
    ports    = ["2049", "111"]
  }
}

# ------------- Service account (no long-lived keys on the host) -------------
resource "google_service_account" "csb" {
  account_id   = "csb-bench-host"
  display_name = "cloud-storage-bench benchmark host"
}
resource "google_project_iam_member" "storage_admin" {
  project = var.project
  role    = "roles/storage.admin" # GCS buckets for the object paradigm
  member  = "serviceAccount:${google_service_account.csb.email}"
}
resource "google_project_iam_member" "compute_storage_admin" {
  project = var.project
  role    = "roles/compute.storageAdmin" # persistent disks for the block paradigm
  member  = "serviceAccount:${google_service_account.csb.email}"
}
resource "google_project_iam_member" "instance_admin" {
  project = var.project
  role    = "roles/compute.instanceAdmin.v1" # read own instance + attach/detach disks
  member  = "serviceAccount:${google_service_account.csb.email}"
}
resource "google_project_iam_member" "file_editor" {
  project = var.project
  role    = "roles/file.editor" # Filestore create/delete for the file paradigm
  member  = "serviceAccount:${google_service_account.csb.email}"
}
# Attaching a disk to the VM requires actAs on the VM's service account --
# and the caller IS that account, so it needs the role on itself.
resource "google_service_account_iam_member" "self_user" {
  service_account_id = google_service_account.csb.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.csb.email}"
}

# ------------------------------ The host -------------------------------------
resource "google_compute_instance" "host" {
  name         = "csb-bench-host-gcp"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["csb-bench"]
  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = var.root_gb
      type  = "pd-ssd"
    }
  }
  network_interface {
    subnetwork = google_compute_subnetwork.csb.id
    access_config {} # ephemeral public IP
  }
  service_account {
    email  = google_service_account.csb.email
    scopes = ["cloud-platform"]
  }
  metadata = {
    "ssh-keys"       = "ubuntu:${var.ssh_public_key}"
    "startup-script" = templatefile(
      "${path.module}/../../../scripts/cloudinit/bootstrap_host.sh", {
        AUTO_SHUTDOWN_HOURS = var.auto_shutdown_hours
        ELBENCHO_VERSION    = var.elbencho_version
    })
  }
  labels = { project = "cloud-storage-bench" }
}
