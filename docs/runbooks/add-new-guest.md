# Runbook: Add a New Proxmox Guest

## When to use this
When adding a new VM or LXC to the homelab estate.

## IP convention
Last octet must match the VM/CT ID: e.g. CT167 -> 10.20.30.167. Check that the IP is free before assigning: `ping -c 1 10.20.30.<ID>`

## Storage targets
- **ssd-fast** (Kingston 888G): high-IOPS guests (AdGuard, RR-dev, Authentik)
- **ssd-mirror** (ORICO 476G mirror): everything else (redundant)

## Steps

1. Choose an ID (next available — check `qm list` and `pct list`)
2. Choose IP: `10.20.30.<ID>/24`
3. Add to `config/homelab.yaml` under `services.lxcs` or `services.vms`
4. Add Terraform resource (standard LXCs are managed by the `lxcs[]` loop in `guests.tf`; special guests like jellyfin-hw need a separate `.tf` file)
5. Add AdGuard rewrite to `config.adguard.rewrites` if the guest needs a `*.laxdog.uk` hostname
6. Add NPM proxy host to `config.npm.proxy_hosts` if the guest needs HTTPS access
7. Add Nagios check if needed (host definition + service checks in Nagios config)
8. Run `terraform plan` -> `terraform apply`
9. Run Ansible playbook if a role is needed
10. Verify service health
11. Commit all changes with a descriptive message
