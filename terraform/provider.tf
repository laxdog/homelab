provider "proxmox" {
  endpoint = local.config.proxmox.endpoint
  insecure = true

  username  = var.proxmox_username
  password  = var.proxmox_password
  api_token = var.proxmox_api_token
}
