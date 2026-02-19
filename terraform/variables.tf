variable "proxmox_username" {
  description = "Proxmox API username (e.g. root@pam or terraform-prov@pve)"
  type        = string
  default     = null
}

variable "proxmox_password" {
  description = "Proxmox API password"
  type        = string
  default     = null
  sensitive   = true
}

variable "proxmox_api_token" {
  description = "Proxmox API token, if used instead of username/password"
  type        = string
  default     = null
  sensitive   = true
}
