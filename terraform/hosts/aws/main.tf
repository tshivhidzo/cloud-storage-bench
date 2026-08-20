terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.region }

data "aws_availability_zones" "available" { state = "available" }

# Canonical Ubuntu Server 22.04 LTS (kernel 5.15), per the thesis host spec
data "aws_ami" "ubuntu2204" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# ---------------------- Dedicated VPC (isolated per provider) ----------------
resource "aws_vpc" "csb" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "csb-bench-vpc" }
}
resource "aws_subnet" "csb" {
  vpc_id                  = aws_vpc.csb.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = { Name = "csb-bench-subnet" }
}
resource "aws_internet_gateway" "csb" {
  vpc_id = aws_vpc.csb.id
  tags   = { Name = "csb-bench-igw" }
}
resource "aws_route_table" "csb" {
  vpc_id = aws_vpc.csb.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.csb.id
  }
  tags = { Name = "csb-bench-rt" }
}
resource "aws_route_table_association" "csb" {
  subnet_id      = aws_subnet.csb.id
  route_table_id = aws_route_table.csb.id
}

# SSH only from the operator; NFS within the VPC so EFS can be mounted.
resource "aws_security_group" "csb" {
  name        = "csb-bench-sg"
  description = "Benchmark host: SSH from operator, NFS in-VPC, egress all"
  vpc_id      = aws_vpc.csb.id
  ingress {
    description = "SSH from operator only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.operator_cidr]
  }
  ingress {
    description = "NFS (EFS mount) within the VPC"
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.csb.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------------- Least-privilege instance role (no long-lived keys) ---------
resource "aws_iam_role" "csb" {
  name = "csb-bench-host-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy" "csb" {
  name = "csb-bench-least-privilege"
  role = aws_iam_role.csb.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BlockStorageForBenchmark"
        Effect = "Allow"
        Action = [
          "ec2:CreateVolume", "ec2:DeleteVolume", "ec2:AttachVolume",
          "ec2:DetachVolume", "ec2:DescribeVolumes", "ec2:DescribeInstances",
          "ec2:DescribeTags", "ec2:CreateTags", "ec2:DescribeAvailabilityZones"
        ]
        Resource = "*"
      },
      {
        # Read-only lookups terraform's data.aws_instance performs, plus the
        # ENI permissions EFS CreateMountTarget/DeleteMountTarget require.
        Sid    = "TerraformSelfDiscoveryAndEfsEni"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstanceTypes", "ec2:DescribeInstanceAttribute",
          "ec2:DescribeSubnets", "ec2:DescribeSecurityGroups",
          "ec2:DescribeNetworkInterfaces",
          "ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Sid    = "FileStorageForBenchmark"
        Effect = "Allow"
        Action = [
          "elasticfilesystem:CreateFileSystem", "elasticfilesystem:DeleteFileSystem",
          "elasticfilesystem:CreateMountTarget", "elasticfilesystem:DeleteMountTarget",
          "elasticfilesystem:DescribeFileSystems", "elasticfilesystem:DescribeMountTargets",
          "elasticfilesystem:DescribeLifecycleConfiguration",
          "elasticfilesystem:DescribeBackupPolicy",
          "elasticfilesystem:DescribeFileSystemPolicy",
          "elasticfilesystem:DescribeMountTargetSecurityGroups",
          "elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite",
          "elasticfilesystem:TagResource"
        ]
        Resource = "*"
      },
      {
        Sid      = "ObjectStorageBucketAdminScopedToPrefix"
        Effect   = "Allow"
        Action   = ["s3:CreateBucket", "s3:DeleteBucket", "s3:ListBucket",
                    "s3:GetBucketLocation", "s3:PutBucketTagging",
                    # read-only lookups terraform's aws_s3_bucket resource
                    # performs after create/refresh
                    "s3:GetBucketPolicy", "s3:GetBucketAcl", "s3:GetBucketCORS",
                    "s3:GetBucketWebsite", "s3:GetBucketVersioning",
                    "s3:GetAccelerateConfiguration", "s3:GetBucketRequestPayment",
                    "s3:GetBucketLogging", "s3:GetLifecycleConfiguration",
                    "s3:GetReplicationConfiguration", "s3:GetEncryptionConfiguration",
                    "s3:GetBucketObjectLockConfiguration", "s3:GetBucketTagging",
                    "s3:ListBucketMultipartUploads", "s3:ListBucketVersions"]
        Resource = "arn:aws:s3:::${var.bucket_prefix}*"
      },
      {
        Sid      = "ObjectStorageDataScopedToPrefix"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject",
                    "s3:DeleteObjectVersion", # force_destroy empties the bucket
                    "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = "arn:aws:s3:::${var.bucket_prefix}*/*"
      }
    ]
  })
}
resource "aws_iam_instance_profile" "csb" {
  name = "csb-bench-host-profile"
  role = aws_iam_role.csb.name
}

# ------------------------------ The host -------------------------------------
resource "aws_key_pair" "csb" {
  key_name   = "csb-bench-key"
  public_key = var.ssh_public_key
}
resource "aws_instance" "host" {
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
  tags = { Name = "csb-bench-host-aws", Project = "cloud-storage-bench" }
}
