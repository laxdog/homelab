# Define which mount points this LXC should have
locals {
  nginx_mounts = ["home", "docker"]
}

resource "proxmox_lxc" "nginx-proxy-manager" {
  hostname        = "nginx-proxy-manager"
  description     = "Container for Nginx proxy manager"
  cores           = 2
  memory          = 2048
  ostemplate      = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
  tags            = "terraform"
  password        = var.pm_password
  ssh_public_keys = var.mac_pub_key
  target_node     = "proxmox"
  unprivileged    = true
  start           = true
  onboot          = true

  rootfs {
    storage = "flash"
    size    = "8G"
  }

  dynamic "mountpoint" {
    for_each = { for k, v in local.mounts : k => v if contains(local.nginx_mounts, k) }
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
    ip     = "10.20.30.101/24"
    gw     = "10.20.30.1"
  }

  features {
    nesting = true
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
