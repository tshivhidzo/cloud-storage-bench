variable "paradigm" {
  type = string
  validation {
    condition     = contains(["block", "file", "object"], var.paradigm)
    error_message = "paradigm must be block, file, or object."
  }
}
variable "region" {
  type    = string
  default = "af-south-1"
}
variable "host_name" {
  type    = string
  default = "csb-bench-host-huawei"
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
