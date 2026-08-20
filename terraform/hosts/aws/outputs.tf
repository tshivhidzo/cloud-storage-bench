output "host_ip"  { value = aws_instance.host.public_ip }
output "region"   { value = var.region }
output "locality" { value = "local" } # af-south-1 is in South Africa
output "ssh" {
  value = "ssh ubuntu@${aws_instance.host.public_ip}"
}
output "ready_check" {
  value = "ssh ubuntu@${aws_instance.host.public_ip} 'ls /var/lib/csb-bootstrap-complete && elbencho --version'"
}
