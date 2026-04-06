locals {
  config = yamldecode(file("${path.module}/../config/homelab.yaml"))

  node    = local.config.proxmox.node
  bridge  = local.config.network.bridge
  storage = local.config.proxmox.storages

  defaults = local.config.services.defaults
  vms      = local.config.services.vms
  lxcs     = local.config.services.lxcs

  # jellyfin-hw is a privileged LXC with GPU device passthrough and a host
  # bind-mount, so it doesn't fit the generic loop. It is defined as its own
  # resource and excluded here.
  lxcs_generic = { for name, meta in local.lxcs : name => meta if name != "jellyfin-hw" }
}
