locals {
  config = yamldecode(file("${path.module}/../config/homelab.yaml"))

  node    = local.config.proxmox.node
  bridge  = local.config.network.bridge
  storage = local.config.proxmox.storages

  vms  = local.config.services.vms
  lxcs = local.config.services.lxcs
}
