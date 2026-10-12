# Second client host for the v2.1 rerun (multi-client runs and the iperf3
# network baseline). Off unless second_client=true.
variable "second_client" {
  type    = bool
  default = false
}

resource "alicloud_security_group_rule" "rerun_elbencho" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "1611/1611"
  security_group_id = alicloud_security_group.csb.id
  cidr_ip           = "10.46.0.0/16"
}
resource "alicloud_security_group_rule" "rerun_iperf" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "5201/5201"
  security_group_id = alicloud_security_group.csb.id
  cidr_ip           = "10.46.0.0/16"
}

resource "alicloud_instance" "host2" {
  count                      = var.second_client ? 1 : 0
  instance_name              = "csb-bench-host2-alibaba"
  image_id                   = data.alicloud_images.ubuntu2204.images[0].id
  instance_type              = alicloud_instance.host.instance_type # identical type
  security_groups            = [alicloud_security_group.csb.id]
  vswitch_id                 = alicloud_vswitch.csb.id
  key_name                   = alicloud_ecs_key_pair.csb.key_pair_name
  system_disk_category       = "cloud_essd"
  system_disk_size           = var.root_gb
  internet_max_bandwidth_out = 100
  user_data = templatefile(
    "${path.module}/../../../scripts/cloudinit/bootstrap_host.sh", {
      AUTO_SHUTDOWN_HOURS = var.auto_shutdown_hours
      ELBENCHO_VERSION    = var.elbencho_version
  })
  tags = { Project = "cloud-storage-bench" }
}

output "host_private_ip"  { value = alicloud_instance.host.private_ip }
output "host2_ip"         { value = join("", alicloud_instance.host2[*].public_ip) }
output "host2_private_ip" { value = join("", alicloud_instance.host2[*].private_ip) }
