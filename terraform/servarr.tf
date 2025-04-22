# Define which mount points this LXC should have
locals {
  servarr_mounts = ["home", "docker", "media"]
}

resource "proxmox_lxc" "servarr" {
  # Changes
  hostname        = "servarr"
  description     = "Container for Servarr stack"
  cores           = 4
  memory          = 4096

  # Static
  ostemplate      = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
  tags            = "terraform"
  password        = var.pm_password
  ssh_public_keys = var.mac_pub_key
  target_node     = "proxmox"
  unprivileged    = true # Set to true for security
  start           = true
  onboot          = true

  rootfs {
    storage = "flash"
    size    = "8G" # Changes
  }

  dynamic "mountpoint" {
    for_each = { for k, v in local.mounts : k => v if contains(local.servarr_mounts, k) }
    content {
      key     = mountpoint.value.key
      slot    = mountpoint.value.slot
      storage = mountpoint.value.storage
      volume  = mountpoint.value.volume
      mp      = mountpoint.value.mp
      size    = mountpoint.value.size
    }
  }

  network {
    name   = "eth0"
    bridge = "vmbr0"
    ip     = "10.20.30.100/24" # Changes
    gw     = "10.20.30.1"
  }

  features {
    nesting = true # Enable nesting to allow Docker
  }

  provisioner "remote-exec" {
    inline = [
      "apt update && apt-get upgrade -y"
    ]
    connection {
      type        = "ssh"
      user        = "root"
      private_key = file("/Users/mrobinson/.ssh/id_rsa")
      host        = split("/", self.network.0.ip)[0]
    }
  }
}

