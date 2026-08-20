terraform {
  required_providers {
    huaweicloud = { source = "huaweicloud/huaweicloud", version = "~> 1.60" }
  }
}
provider "huaweicloud" { region = var.region }

# Ubuntu 22.04 public image
data "huaweicloud_images_image" "ubuntu2204" {
  name        = "Ubuntu 22.04 server 64bit"
  most_recent = true
}

# ---------------------- Dedicated VPC ----------------------
resource "huaweicloud_vpc" "csb" {
  name = "csb-bench-vpc"
  cidr = "10.45.0.0/16"
}
resource "huaweicloud_vpc_subnet" "csb" {
  name       = "csb-bench-subnet"
  cidr       = "10.45.1.0/24"
  gateway_ip = "10.45.1.1"
  vpc_id     = huaweicloud_vpc.csb.id
}
resource "huaweicloud_networking_secgroup" "csb" {
  name                 = "csb-bench-sg"
  delete_default_rules = true
}
resource "huaweicloud_networking_secgroup_rule" "ssh" {
  security_group_id = huaweicloud_networking_secgroup.csb.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.operator_cidr
}
resource "huaweicloud_networking_secgroup_rule" "egress" {
  security_group_id = huaweicloud_networking_secgroup.csb.id
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "0.0.0.0/0"
}
resource "huaweicloud_vpc_eip" "csb" {
  publicip { type = "5_bgp" }
  bandwidth {
    name        = "csb-bench-bw"
    size        = 100
    share_type  = "PER"
    charge_mode = "traffic"
  }
}

resource "huaweicloud_compute_keypair" "csb" {
  name       = "csb-bench-key"
  public_key = var.ssh_public_key
}

# ------------------------------ The host -------------------------------------
resource "huaweicloud_compute_instance" "host" {
  name               = "csb-bench-host-huawei"
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
resource "huaweicloud_compute_eip_associate" "csb" {
  public_ip   = huaweicloud_vpc_eip.csb.address
  instance_id = huaweicloud_compute_instance.host.id
}
