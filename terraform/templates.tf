resource "proxmox_virtual_environment_download_file" "ubuntu_lxc" {
  content_type = "vztmpl"
  datastore_id = local.storage.templates_dir
  node_name    = local.node

  url       = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64-root.tar.xz"
  file_name = "ubuntu-24.04-root.tar.xz"
}

resource "proxmox_virtual_environment_download_file" "ubuntu_cloud_image" {
  content_type = "import"
  datastore_id = local.storage.local_dir
  node_name    = local.node

  url       = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
  file_name = "ubuntu-24.04-cloudimg-amd64.qcow2"
}
