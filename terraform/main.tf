terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
    }
  }
}

variable "pm_api_url" {
  description = "The Proxmox API URL"
  default     = "https://10.20.30.237:8006/api2/json"
}

variable "pm_user" {
  description = "The Proxmox user"
  default     = "terraform-prov@pve"
}

variable "pm_password" {
  description = "The Proxmox password"
}

provider "proxmox" {
  pm_api_url  = var.pm_api_url
  pm_user     = var.pm_user
  pm_password = var.pm_password
}

resource "proxmox_vm_qemu" "vm" {
  name              = "test-vm"
  target_node       = "pve"
  iso               = "local:iso/ubuntu-22.04.2-live-server-amd64.iso"
  full_clone        = true
  cores             = 2
  memory            = 2048
  scsihw            = "virtio-scsi-pci"
  bootdisk          = "scsi0"
  os_type           = "cloud-init"
  disk {
    slot            = 0
    size            = "20G"
    type            = "scsi"
    storage         = "local-zfs"
    iothread        = 0
  }
  network {
    model           = "virtio"
    bridge          = "vmbr0"
  }

  lifecycle {
    ignore_changes = [
      disk
    ]
  }
}

