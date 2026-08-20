variable "region" {
  type        = string
  default     = "af-south-1" # Cape Town -- local to South Africa
  description = "Benchmark host region; keep it equal to the storage region."
}
variable "instance_type" {
  type    = string
  default = "m5.xlarge" # 4 vCPU / 16 GB, per HARDWARE_AND_PLACEMENT.md
}
variable "root_gb" {
  type    = number
  default = 100
}
variable "ssh_public_key" {
  type        = string
  description = "Contents of your ~/.ssh/id_rsa.pub (or other public key)."
}
variable "operator_cidr" {
  type        = string
  description = "YOUR public IP as a /32, e.g. 41.x.x.x/32. SSH is locked to this."
  validation {
    condition     = can(cidrnetmask(var.operator_cidr))
    error_message = "operator_cidr must be valid CIDR, e.g. 41.1.2.3/32."
  }
}
variable "auto_shutdown_hours" {
  type        = number
  default     = 8
  description = "Host powers itself off after this many hours. 0 disables."
}
variable "elbencho_version" {
  type    = string
  default = "3.1-1" # release tags are v<major>.<minor>-<patch>, e.g. v3.1-1
}
variable "bucket_prefix" {
  type        = string
  default     = "csb-bench-"
  description = "Least-privilege S3 permissions are scoped to this prefix."
}
