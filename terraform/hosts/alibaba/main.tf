terraform {
  required_providers {
    alicloud = { source = "aliyun/alicloud", version = "~> 1.220" }
  }
}
provider "alicloud" { region = var.region }

data "alicloud_images" "ubuntu2204" {
  owners      = "system"
  name_regex  = "^ubuntu_22_04_x64"
  most_recent = true
}

# ---------------------- Dedicated VPC ----------------------
resource "alicloud_vpc" "csb" {
  vpc_name   = "csb-bench-vpc"
  cidr_block = "10.46.0.0/16"
}
resource "alicloud_vswitch" "csb" {
  vpc_id       = alicloud_vpc.csb.id
  cidr_block   = "10.46.1.0/24"
  zone_id      = var.zone_id
  vswitch_name = "csb-bench-vsw"
}
resource "alicloud_security_group" "csb" {
  name   = "csb-bench-sg"
  vpc_id = alicloud_vpc.csb.id
}
resource "alicloud_security_group_rule" "ssh" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "22/22"
  security_group_id = alicloud_security_group.csb.id
  cidr_ip           = var.operator_cidr
}
resource "alicloud_ecs_key_pair" "csb" {
  key_pair_name = "csb-bench-key"
  public_key    = var.ssh_public_key
}

# Discover a purchasable 4 vCPU / 16 GB x86 type in this zone -- specific
# families (g6, g7) come and go from sale in me-central-1.
data "alicloud_instance_types" "pick" {
  availability_zone    = var.zone_id
  cpu_core_count       = var.cpu_cores
  memory_size          = var.memory_gb
  system_disk_category = "cloud_essd"
}
locals {
  # exclude ARM (Yitian) families -- their names end in 'y', e.g. g8y/c8y/r8y
  x86_types = [
    for t in data.alicloud_instance_types.pick.instance_types : t.id
    if !can(regex("^ecs\\.[a-z]+[0-9]+y", t.id))
  ]
  # burstable (t*) types throttle sustained load -- unusable for benchmarking.
  # Prefer steady-performance families; fall back to burstable only if nothing
  # else is sold (and then disclose it).
  steady_types = [
    for id in local.x86_types : id if !can(regex("^ecs\\.t", id))
  ]
  instance_type = var.instance_type != "" ? var.instance_type : (
    length(local.steady_types) > 0 ? local.steady_types[0] : local.x86_types[0]
  )
}

# ------------------------------ The host -------------------------------------
resource "alicloud_instance" "host" {
  instance_name              = "csb-bench-host-alibaba"
  image_id                   = data.alicloud_images.ubuntu2204.images[0].id
  instance_type              = local.instance_type
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
