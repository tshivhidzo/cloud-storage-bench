variable "region" {
  type        = string
  default     = "me-central-1" # Dubai -- NO African region exists; this is OFFSHORE
  description = "Alibaba has no South African region. This host is offshore and must be reported as such."
}
variable "zone_id" {
  type    = string
  default = "me-central-1a"
}
variable "instance_type" {
  type    = string
  default = "" # empty = auto-pick an available 4 vCPU / 16 GB x86 type
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

variable "cpu_cores" {
  type    = number
  default = 4 # set 8 (with memory_gb = 32) for the scaling-sweep campaign
}
variable "memory_gb" {
  type    = number
  default = 16
}
