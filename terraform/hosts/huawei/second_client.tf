# Second client host for the v2.1 rerun (multi-client runs and the iperf3
# network baseline). Off unless second_client=true.
variable "second_client" {
  type    = bool
  default = false
}

# the security group deletes its default rules, so intra-VPC traffic between
# the two clients must be allowed explicitly
resource "huaweicloud_networking_secgroup_rule" "rerun_elbencho" {
  security_group_id = huaweicloud_networking_secgroup.csb.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 1611
  port_range_max    = 1611
  remote_ip_prefix  = "10.45.0.0/16"
}
resource "huaweicloud_networking_secgroup_rule" "rerun_iperf" {
  security_group_id = huaweicloud_networking_secgroup.csb.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 5201
  port_range_max    = 5201
  remote_ip_prefix  = "10.45.0.0/16"
}

resource "huaweicloud_vpc_eip" "csb2" {
  count = var.second_client ? 1 : 0
  publicip { type = "5_bgp" }
  bandwidth {
    name        = "csb-bench-bw2"
    size        = 100
    share_type  = "PER"
    charge_mode = "traffic"
  }
}

resource "huaweicloud_compute_instance" "host2" {
  count              = var.second_client ? 1 : 0
  name               = "csb-bench-host2-huawei"
  image_id           = data.huaweicloud_images_image.ubuntu2204.id
  flavor_id          = var.flavor_id
  security_group_ids = [huaweicloud_networking_secgroup.csb.id]
  availability_zone  = var.availability_zone
  key_pair           = huaweicloud_compute_keypair.csb.name
  system_disk_type   = "SSD"
  system_disk_size   = var.root_gb
  network {
    uuid = huaweicloud_vpc_subnet.csb.id
  }
  user_data = templatefile(
    "${path.module}/../../../scripts/cloudinit/bootstrap_host.sh", {
      AUTO_SHUTDOWN_HOURS = var.auto_shutdown_hours
      ELBENCHO_VERSION    = var.elbencho_version
  })
  tags = { Project = "cloud-storage-bench" }
}

resource "huaweicloud_compute_eip_associate" "csb2" {
  count       = var.second_client ? 1 : 0
  public_ip   = huaweicloud_vpc_eip.csb2[0].address
  instance_id = huaweicloud_compute_instance.host2[0].id
}

output "host_private_ip"  { value = huaweicloud_compute_instance.host.access_ip_v4 }
output "host2_ip"         { value = join("", huaweicloud_vpc_eip.csb2[*].address) }
output "host2_private_ip" { value = join("", huaweicloud_compute_instance.host2[*].access_ip_v4) }
