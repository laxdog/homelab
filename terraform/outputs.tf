output "guest_ips" {
  description = "Guest IPs from config"
  value = {
    vms  = { for name, meta in local.vms : name => meta.ip }
    lxcs = { for name, meta in local.lxcs : name => meta.ip }
  }
}
