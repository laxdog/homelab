terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
    }
  }
}

provider "proxmox" {
  pm_api_url  = var.pm_api_url
  pm_user     = var.pm_user
  pm_password = var.pm_password
  pm_tls_insecure = true
}
