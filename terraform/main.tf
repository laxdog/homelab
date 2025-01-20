locals {
  # Variables
  ip           = "10.20.30.100"
  netmask      = "24"
  hostname     = "servarr"
  ostemplate   = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
  description  = "Container for Servarr stack"
  root_disk_gb = 8
  cores        = 4
  memory       = 4096

  # Static / computed
  network_address = "${local.ip}/${local.netmask}"
}

resource "proxmox_lxc" "basic" {
  target_node     = "proxmox"
  hostname        = local.hostname
  ostemplate      = local.ostemplate
  password        = var.pm_password
  unprivileged    = true # Set to true for security
  start           = true
  tags            = "terraform;${local.ip}"
  description     = local.description
  ssh_public_keys = var.mac_pub_key
  cores           = local.cores
  memory          = local.memory
  onboot          = true

  rootfs {
    storage = "flash"
    size    = "${local.root_disk_gb}G"
  }

  mountpoint {
    key     = "0"
    slot    = 0
    storage = "/srv/host/bind-mount-point"
    volume  = "/tank/container_home"
    mp      = "/home"
    size    = "20G"
  }

  network {
    name   = "eth0"
    bridge = "vmbr0"
    ip     = local.network_address
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
      private_key = file("~/.ssh/id_rsa")
      host        = local.ip
    }
  }
}

