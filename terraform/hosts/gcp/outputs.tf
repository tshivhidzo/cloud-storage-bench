output "host_ip" {
  value = google_compute_instance.host.network_interface[0].access_config[0].nat_ip
}
output "region"   { value = var.region }
output "locality" { value = "local" } # africa-south1 is in South Africa
output "ssh" {
  value = "ssh ubuntu@${google_compute_instance.host.network_interface[0].access_config[0].nat_ip}"
}
output "ready_check" {
  value = "ssh ubuntu@${google_compute_instance.host.network_interface[0].access_config[0].nat_ip} 'ls /var/lib/csb-bootstrap-complete && elbencho --version'"
}
