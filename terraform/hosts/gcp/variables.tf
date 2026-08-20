variable "project" {
  type        = string
  description = "Your GCP project id."
}
variable "region" {
  type    = string
  default = "africa-south1" # Johannesburg -- local to South Africa
}
variable "zone" {
  type    = string
  default = "africa-south1-a"
}
variable "machine_type" {
  type    = string
  default = "e2-standard-4" # 4 vCPU / 16 GB
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
