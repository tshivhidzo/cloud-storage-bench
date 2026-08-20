variable "paradigm" {
  type = string
  validation {
    condition     = contains(["block", "file", "object"], var.paradigm)
    error_message = "paradigm must be block, file, or object."
  }
}
variable "region" {
  type    = string
  default = "africa-south1"
}
variable "zone" {
  type    = string
  default = "africa-south1-a"
}
variable "project" {
  type    = string
  default = ""
}
variable "host_name" {
  type    = string
  default = "csb-bench-host-gcp"
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
