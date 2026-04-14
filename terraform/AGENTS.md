# Terraform — Homelab Agent Scope

Terraform in this repo manages Proxmox guest definitions only. It is homelab agent scope.

## Credentials
Sourced from ansible vault via `TF_VAR_*` env vars at runtime:
- `TF_VAR_proxmox_username` = `terraform-prov@pve`
- `TF_VAR_proxmox_password` from `terraform_user_password` in `ansible/secrets.yml`
- Vault password file: `~/.ansible_vault_pass`

## Rules
- Always run `terraform plan` before `apply`
- CT167 (jellyfin-hw) is defined separately in `jellyfin_hw.tf` (privileged LXC with GPU passthrough)
- All guest storage defaults to `ssd-mirror` via `proxmox.storages.vm_disk`
- Guests on ssd-fast have explicit `storage: ssd-fast` in homelab.yaml
- Guest IPs follow the convention: last octet = VM/CT ID

## State
State lives locally in `terraform/terraform.tfstate`. Not configured for remote state.
