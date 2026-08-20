variable "region" {
  type    = string
  default = "af-south-1" # Johannesburg -- local to South Africa
}
variable "availability_zone" {
  type    = string
  default = "af-south-1a"
}
variable "flavor_id" {
  type    = string
  default = "c6.xlarge.4" # 4 vCPU / 16 GB
}
variable "root_gb" {
  type    = number
  default = 100
}
variable "ssh_public_key" {
  type = string
}
variable "operator_cidr" {
  type = string
}
variable "auto_shutdown_hours" {
  type    = number
  default = 8
}
variable "elbencho_version" {
  type    = string
  default = "3.1-1" # release tags are v<major>.<minor>-<patch>, e.g. v3.1-1
}
