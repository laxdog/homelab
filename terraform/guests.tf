locals {
  ubuntu_vms = { for name, meta in local.vms : name => meta if meta.os == "ubuntu" }
  haos_vms   = { for name, meta in local.vms : name => meta if meta.os == "haos" }
}

resource "proxmox_virtual_environment_container" "lxcs" {
  for_each = local.lxcs_generic

  node_name = local.node
  vm_id     = each.value.id
  tags      = ["terraform"]

  unprivileged = try(each.value.unprivileged, local.defaults.lxc.unprivileged)

  operating_system {
    template_file_id = "${local.storage.templates_dir}:vztmpl/${local.config.proxmox.templates.lxc.file_name}"
    type             = "ubuntu"
  }

  initialization {
    hostname = each.key

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
    datastore_id = try(each.value.storage, local.storage.vm_disk)
    size         = try(each.value.disk_gb, local.defaults.lxc.disk_gb)
  }

  features {
    nesting = try(each.value.nesting, local.defaults.lxc.nesting)
    keyctl  = try(each.value.keyctl, local.defaults.lxc.keyctl)
  }

  cpu {
    cores = try(each.value.cores, local.defaults.lxc.cores)
  }

  memory {
    dedicated = try(each.value.memory_mb, local.defaults.lxc.memory_mb)
  }

  started       = true
  start_on_boot = true

  lifecycle {
    ignore_changes = [
      description,
      features[0].keyctl,
      initialization,
      operating_system[0].template_file_id,
      tags,
    ]
  }
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
    datastore_id = try(each.value.storage, local.storage.vm_disk)
    import_from  = "${local.storage.templates_dir}:import/${local.config.proxmox.templates.vm.file_name}"
    interface    = "scsi0"
    size         = try(each.value.disk_gb, local.defaults.vm.disk_gb)
  }

  network_device {
    bridge = local.bridge
  }

  initialization {
    datastore_id = local.storage.vm_disk
    interface    = "ide2"
    type         = "nocloud"

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

  # Optional virtiofs shares (Proxmox directory mappings). Per-VM list under
  # `services.vms.<name>.virtiofs` in homelab.yaml.
  dynamic "virtiofs" {
    for_each = try(each.value.virtiofs, [])
    content {
      mapping = virtiofs.value.mapping
      cache   = try(virtiofs.value.cache, null)
    }
  }

  operating_system {
    type = "l26"
  }

  startup {
    order = "3"
  }

  started = true

  lifecycle {
    ignore_changes = [
      description,
      hostpci,
      tags,
    ]
  }
}

resource "proxmox_virtual_environment_vm" "haos_vms" {
  for_each = local.haos_vms

  node_name = local.node
  vm_id     = each.value.id
  name      = each.key
  tags      = ["terraform"]

  cpu {
    cores = try(each.value.cores, local.defaults.vm.cores)
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = try(each.value.memory_mb, local.defaults.vm.memory_mb)
  }

  disk {
    datastore_id = local.storage.vm_disk
    import_from  = "${local.storage.templates_dir}:import/${local.config.proxmox.templates.haos.file_name}"
    interface    = "scsi0"
    size         = try(each.value.disk_gb, local.defaults.vm.disk_gb)
  }

  network_device {
    bridge = local.bridge
  }

  operating_system {
    type = "l26"
  }

  bios          = "ovmf"
  machine       = "q35"
  boot_order    = ["scsi0"]
  scsi_hardware = "virtio-scsi-pci"

  efi_disk {
    datastore_id      = local.storage.vm_disk
    type              = "4m"
    pre_enrolled_keys = false
  }

  serial_device {
    device = "socket"
  }

  vga {
    type = "serial0"
  }

  startup {
    order = "2"
  }

  started = true

  lifecycle {
    ignore_changes = [
      description,
      tags,
    ]
  }
}
