output "host_ip"  { value = huaweicloud_vpc_eip.csb.address }
output "region"   { value = var.region }
output "locality" { value = "local" } # af-south-1 (Johannesburg) is in South Africa
output "ssh"      { value = "ssh ubuntu@${huaweicloud_vpc_eip.csb.address}" }
output "ready_check" {
  value = "ssh ubuntu@${huaweicloud_vpc_eip.csb.address} 'ls /var/lib/csb-bootstrap-complete && elbencho --version'"
}
