locals {
  mounts = {
    home = {
      key     = "0"
      slot    = 0
      storage = "/srv/host/bind-mount-point"
      volume  = "/flash/container_home"
      mp      = "/home"
      size    = "1G" # Required by Proxmox, but doesn't allocate space
    }
    docker = {
      key     = "1"
      slot    = 1
      storage = "/srv/host/bind-mount-point"
      volume  = "/flash/docker_files"
      mp      = "/docker"
      size    = "1G" # Required by Proxmox, but doesn't allocate space
    }
    media = {
      key     = "2"
      slot    = 2
      storage = "/srv/host/bind-mount-point"
      volume  = "/tank/media_root"
      mp      = "/media"
      size    = "1G" # Required by Proxmox, but doesn't allocate space
    }
  }
}
