variable "paradigm" {
  type = string
  validation {
    condition     = contains(["block", "file", "object"], var.paradigm)
    error_message = "paradigm must be block, file, or object."
  }
}
variable "region" {
  type    = string
  default = "southafricanorth"
}
variable "resource_group" {
  type    = string
  default = "csb-bench-rg" # must match the hosts/azure resource group
}
variable "host_vm_name" {
  type    = string
  default = "csb-bench-host-azure"
}
variable "volume_gb" {
  type    = number
  default = 100
}
variable "mount_block" {
  type    = string
  default = "/mnt/block"
}
variable "mount_file" {
  type    = string
  default = "/mnt/file"
}
