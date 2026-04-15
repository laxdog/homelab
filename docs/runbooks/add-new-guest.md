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
5. **DNS and access** — choose the right domain:
   - **Internal only** (`laxdog.uk`): add AdGuard rewrite (`subdomain.laxdog.uk → 10.20.30.154`) + NPM proxy host. NPM handles the LE cert via HTTP-01. No Cloudflare needed.
   - **External** (`lax.dog`): add Cloudflare A record + NPM external proxy host + Authentik forward-auth if sensitive. Only use this if the service genuinely needs internet access.
   - See `AGENTS.md` "Domain architecture" for full details.
6. Add NPM proxy host to `config.npm.proxy_hosts` (internal) or `config.npm.external_proxy_hosts` (external)
7. Add Nagios check if needed (host definition + service checks in Nagios config)
8. Run `terraform plan` -> `terraform apply`
9. Run Ansible playbook if a role is needed
10. Verify service health
11. Commit all changes with a descriptive message
