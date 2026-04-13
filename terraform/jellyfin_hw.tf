# jellyfin-hw (CT167)
#
# Privileged LXC for Jellyfin hardware transcoding via the host's Intel UHD 630
# iGPU. The generic LXC loop in guests.tf cannot represent this guest because
# it needs:
#   - privileged mode (unprivileged = false)
#   - explicit storage (ssd-mirror ZFS, referenced directly not via try() fallback)
#   - device passthrough for /dev/dri/card0 and /dev/dri/renderD128
#   - a host bind-mount of /tank/media at /mnt/media (read-only)
#
# IMPORTANT — this resource cannot be created by `terraform apply` alone.
#
# Proxmox restricts THREE distinct operations on privileged LXCs to
# interactive `root@pam` only, refusing both `terraform-prov@pve` and any
# `root@pam!<tokenid>` API token:
#   1. `pct set <id> -features ...`   (changing feature flags on privileged)
#   2. `pct set <id> -mp<n> /host,...` (bind mount_point with host path)
#   3. `pct set <id> -dev<n> /dev/...` (device passthrough)
# The orchestrator (scripts/run.py) authenticates as `terraform-prov@pve`,
# so none of these can be done from Terraform without manual root password
# entry on every apply.
#
# The pragmatic split is:
#   - The bare LXC (rootfs, network, cpu, memory, OS) is created on the host
#     via `pct create` with all root@pam-only options baked in, then
#     `terraform import`-ed into state. This file's resource block describes
#     the desired shape so future TF runs can manage what they're allowed to
#     manage; root@pam-only attributes are in `lifecycle.ignore_changes` so
#     plans stay clean.
#   - Subsequent in-container provisioning is done by the `jellyfin-hw`
#     Ansible role.
#
# To recreate CT167 from scratch, run as root on 10.20.30.46:
#   pct create 167 tank-templates:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst \
#     --hostname jellyfin-hw \
#     --cores 4 --memory 4096 --swap 512 \
#     --rootfs tank-vmdata:20 \
#     --net0 name=eth0,bridge=vmbr0,ip=10.20.30.167/24,gw=10.20.30.1 \
#     --nameserver 10.20.30.53 \
#     --unprivileged 0 \
#     --features nesting=1,keyctl=1 \
#     --onboot 1 \
#     --mp0 /tank/media,mp=/mnt/media,ro=1 \
#     --dev0 /dev/dri/card0,gid=44,mode=0660 \
#     --dev1 /dev/dri/renderD128,gid=993,mode=0660 \
#     --ssh-public-keys /root/.ssh/authorized_keys \
#     --start 1
# Then from terraform/:
#   terraform import proxmox_virtual_environment_container.jellyfin_hw 167
#
# Render group GIDs (host == container, both Debian/Ubuntu have render=993,
# video=44). The dev0/dev1 GIDs match the in-container groups so Jellyfin's
# Docker container (which adds groups 993 and 44) can read the devices.

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
    swap      = 512
  }

  console {
    enabled   = true
    tty_count = 2
    type      = "tty"
  }

  # NOTE: mount_point and device_passthrough for /tank/media, /dev/dri/card0,
  # /dev/dri/renderD128 are applied out-of-band by the proxmox-jellyfin-hw
  # Ansible role (see comment at top of file). They're in ignore_changes so
  # plans stay clean.
  #
  # Both bind mount_points (volume = host path) and device_passthrough require
  # interactive root@pam in Proxmox; neither terraform-prov@pve nor a root@pam
  # API token are accepted. Ansible runs as root via SSH on the host so it can
  # do both via `pct set`.

  started       = true
  start_on_boot = true

  lifecycle {
    ignore_changes = [
      description,
      device_passthrough,
      features,
      initialization,
      mount_point,
      operating_system[0].template_file_id,
      tags,
    ]
  }
}
