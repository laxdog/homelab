# jellyfin-hw (CT167)
#
# Privileged LXC for Jellyfin hardware transcoding via the host's Intel UHD 630
# iGPU. The generic LXC loop in guests.tf cannot represent this guest because
# it needs:
#   - privileged mode (unprivileged = false)
#   - non-default storage (tank-vmdata ZFS, not local-lvm thin pool)
#   - device passthrough for /dev/dri/card0 and /dev/dri/renderD128
#   - a host bind-mount of /tank/media at /mnt/media (read-only)
#
# The host /dev/dri device numbers are major 226 (DRM):
#   card0      → 226:0   (Display Resource Manager card)
#   renderD128 → 226:128 (render-only node, the one Jellyfin actually uses)
#
# The bpg/proxmox provider's `device_passthrough` block writes Proxmox 8.2+
# `dev[N]` lines into /etc/pve/lxc/167.conf. Proxmox then handles the
# underlying cgroup allow + bind-mount internally, replacing the legacy
# `lxc.cgroup2.devices.allow` + `lxc.mount.entry` pattern.
#
# Render group GIDs:
#   - host: render=104, video=44
#   - inside Ubuntu 24.04 LXC: render=993, video=44
# We set the GID on the device node to match the in-container group so the
# Jellyfin Docker container (which adds groups 993 and 44) can read it.

locals {
  jellyfin_hw = local.config.services.lxcs["jellyfin-hw"]
}

resource "proxmox_virtual_environment_container" "jellyfin_hw" {
  node_name = local.node
  vm_id     = local.jellyfin_hw.id
  tags      = ["terraform"]

  unprivileged = false

  operating_system {
    template_file_id = "${local.storage.templates_dir}:vztmpl/${local.config.proxmox.templates.lxc.file_name}"
    type             = "ubuntu"
  }

  initialization {
    hostname = "jellyfin-hw"

    ip_config {
      ipv4 {
        address = "${local.jellyfin_hw.ip}/24"
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
    datastore_id = local.jellyfin_hw.storage
    size         = local.jellyfin_hw.disk_gb
  }

  features {
    nesting = true
    keyctl  = true
  }

  cpu {
    cores = local.jellyfin_hw.cores
  }

  memory {
    dedicated = local.jellyfin_hw.memory_mb
  }

  # /tank/media (host) → /mnt/media (container), read-only
  mount_point {
    volume    = "/tank/media"
    path      = "/mnt/media"
    read_only = true
  }

  # /dev/dri/card0 — DRM card device, video group inside container
  device_passthrough {
    path = "/dev/dri/card0"
    gid  = 44
    mode = "0660"
  }

  # /dev/dri/renderD128 — render node, render group inside container
  device_passthrough {
    path = "/dev/dri/renderD128"
    gid  = 993
    mode = "0660"
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
