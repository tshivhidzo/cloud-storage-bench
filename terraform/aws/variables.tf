variable "paradigm" {
  type        = string
  description = "block | file | object"
  validation {
    condition     = contains(["block", "file", "object"], var.paradigm)
    error_message = "paradigm must be block, file, or object."
  }
}
variable "region" {
  type    = string
  default = "af-south-1"
}
variable "mount_block" {
  type    = string
  default = "/mnt/block"
}
variable "mount_file" {
  type    = string
  default = "/mnt/file"
}
variable "volume_gb" {
  type    = number
  default = 100
}
# When terraform runs ON the benchmark host (recommended), leave these empty and
# the module reads the host's own instance-id / AZ / subnet from IMDS.
variable "instance_id" {
  type    = string
  default = ""
}
variable "subnet_id" {
  type    = string
  default = ""
}
