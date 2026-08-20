variable "region" {
  type    = string
  default = "southafricanorth" # Johannesburg -- local to South Africa
}
variable "resource_group" {
  type    = string
  default = "csb-bench-rg"
}
variable "vm_size" {
  type    = string
  default = "Standard_D4s_v3" # 4 vCPU / 16 GB
}
variable "root_gb" {
  type    = number
  default = 100
}
variable "ssh_public_key" {
  type = string
}
variable "operator_cidr" {
  type        = string
  description = "Your public IP as a /32; SSH is locked to this."
}
variable "auto_shutdown_hours" {
  type    = number
  default = 8
}
variable "elbencho_version" {
  type    = string
  default = "3.1-1" # release tags are v<major>.<minor>-<patch>, e.g. v3.1-1
}
