resource "proxmox_lxc" "nginx-proxy-manager" {
  # Changes
  hostname        = "nginx-proxy-manager"
  description     = "Container for Nginx proxy manager"
  cores           = 2
  memory          = 2048

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
    ip     = "10.20.30.101/24" # Changes
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

