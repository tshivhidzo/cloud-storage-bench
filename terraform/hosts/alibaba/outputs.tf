output "host_ip"  { value = alicloud_instance.host.public_ip }
output "instance_type" {
  value       = alicloud_instance.host.instance_type
  description = "record in the thesis hardware table (auto-picked when available)"
}
output "region"   { value = var.region }
output "locality" { value = "offshore" } # no African region; report honestly
output "ssh"      { value = "ssh ubuntu@${alicloud_instance.host.public_ip}" }
output "ready_check" {
  value = "ssh ubuntu@${alicloud_instance.host.public_ip} 'ls /var/lib/csb-bootstrap-complete && elbencho --version'"
}
