resource "proxmox_virtual_environment_download_file" "ubuntu_lxc" {
  content_type = "vztmpl"
  datastore_id = local.storage.templates_dir
  node_name    = local.node

  url       = local.config.proxmox.templates.lxc.url
  file_name = local.config.proxmox.templates.lxc.file_name
}

resource "proxmox_virtual_environment_download_file" "ubuntu_cloud_image" {
  content_type = "import"
  datastore_id = local.storage.local_dir
  node_name    = local.node

  url       = local.config.proxmox.templates.vm.url
  file_name = local.config.proxmox.templates.vm.file_name
}
