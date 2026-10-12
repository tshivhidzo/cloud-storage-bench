# Second client host for the v2.1 rerun (multi-client runs and the iperf3
# network baseline). Off unless second_client=true.
variable "second_client" {
  type    = bool
  default = false
}

resource "google_compute_firewall" "rerun_internal" {
  name          = "csb-bench-allow-rerun-internal"
  network       = google_compute_network.csb.name
  source_ranges = ["10.44.0.0/16"]
  target_tags   = ["csb-bench"]
  allow {
    protocol = "tcp"
    ports    = ["1611", "5201"] # elbencho service, iperf3
  }
}

resource "google_compute_instance" "host2" {
  count        = var.second_client ? 1 : 0
  name         = "csb-bench-host2-gcp"
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
    access_config {}
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

output "host_private_ip" { value = google_compute_instance.host.network_interface[0].network_ip }
output "host2_ip" {
  value = join("", [for h in google_compute_instance.host2 : h.network_interface[0].access_config[0].nat_ip])
}
output "host2_private_ip" {
  value = join("", [for h in google_compute_instance.host2 : h.network_interface[0].network_ip])
}
