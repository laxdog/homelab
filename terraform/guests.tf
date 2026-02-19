locals {
  ubuntu_vms = { for name, meta in local.vms : name => meta if meta.os == "ubuntu" }
}

resource "proxmox_virtual_environment_container" "lxcs" {
  for_each = local.lxcs

  node_name = local.node
  vm_id     = each.value.id
  hostname  = each.key
  tags      = ["terraform"]

  unprivileged = try(each.value.unprivileged, local.defaults.lxc.unprivileged)

  operating_system {
    template_file_id = proxmox_virtual_environment_download_file.ubuntu_lxc.id
    type             = "ubuntu"
  }

  initialization {
    ip_config {
      ipv4 {
        address = "${each.value.ip}/24"
        gateway = local.config.network.gateway
      }
    }

    user_account {
      keys = [trimspace(file(local.config.proxmox.ssh_public_key_path))]
    }
  }

  network_interface {
    name   = "eth0"
    bridge = local.bridge
  }

  disk {
    datastore_id = local.storage.vm_disk
    size         = try(each.value.disk_gb, local.defaults.lxc.disk_gb)
  }

  features {
    nesting = try(each.value.nesting, local.defaults.lxc.nesting)
  }

  cpu {
    cores = try(each.value.cores, local.defaults.lxc.cores)
  }

  memory {
    dedicated = try(each.value.memory_mb, local.defaults.lxc.memory_mb)
  }

  started       = true
  start_on_boot = true
}

resource "proxmox_virtual_environment_vm" "vms" {
  for_each = local.ubuntu_vms

  node_name = local.node
  vm_id     = each.value.id
  name      = each.key
  tags      = ["terraform"]

  agent {
    enabled = false
  }

  cpu {
    cores = try(each.value.cores, local.defaults.vm.cores)
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = try(each.value.memory_mb, local.defaults.vm.memory_mb)
  }

  disk {
    datastore_id = local.storage.vm_disk
    import_from  = proxmox_virtual_environment_download_file.ubuntu_cloud_image.id
    interface    = "scsi0"
    size         = try(each.value.disk_gb, local.defaults.vm.disk_gb)
  }

  network_device {
    bridge = local.bridge
  }

  initialization {
    ip_config {
      ipv4 {
        address = "${each.value.ip}/24"
        gateway = local.config.network.gateway
      }
    }

    user_account {
      username = "ubuntu"
      keys     = [trimspace(file(local.config.proxmox.ssh_public_key_path))]
    }
  }

  operating_system {
    type = "l26"
  }

  startup {
    order = "3"
  }

  started = true
}
