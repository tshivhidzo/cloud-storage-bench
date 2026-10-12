# Second client host for the v2.1 rerun (multi-client runs and the iperf3
# network baseline). Off unless second_client=true; identical type, subnet,
# security group and instance role as the first host.
variable "second_client" {
  type    = bool
  default = false
}

resource "aws_instance" "host2" {
  count                  = var.second_client ? 1 : 0
  ami                    = data.aws_ami.ubuntu2204.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.csb.id
  vpc_security_group_ids = [aws_security_group.csb.id]
  key_name               = aws_key_pair.csb.key_name
  iam_instance_profile   = aws_iam_instance_profile.csb.name
  root_block_device {
    volume_size = var.root_gb
    volume_type = "gp3"
  }
  user_data = templatefile("${path.module}/../../../scripts/cloudinit/bootstrap_host.sh", {
    AUTO_SHUTDOWN_HOURS = var.auto_shutdown_hours
    ELBENCHO_VERSION    = var.elbencho_version
  })
  tags = { Name = "csb-bench-host2-aws", Project = "cloud-storage-bench" }
}

output "host_private_ip"  { value = aws_instance.host.private_ip }
output "host2_ip"         { value = join("", aws_instance.host2[*].public_ip) }
output "host2_private_ip" { value = join("", aws_instance.host2[*].private_ip) }
