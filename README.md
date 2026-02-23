# Homelab

Infrastructure-as-code for a Proxmox-based homelab. The repo drives:
- Proxmox host baseline (packages, ZFS datasets, storage registration, NUT)
- Terraform provisioning of VMs/LXCs
- Ansible configuration of guests

Source of truth: `config/homelab.yaml`.

## Bootstrap (minimal manual)
1. Install Proxmox.
2. Set management IP to `10.20.30.46/24` and enable SSH.
3. Install your SSH public key for `root`.

## Run
1. `pip install -r scripts/requirements.txt`
2. Provide vault password (recommended: `~/.ansible_vault_pass`).
3. `scripts/run.py apply` (uses `terraform_user_password` from vault if present)

## Validate
- Run `scripts/run.py validate` after changes.
- Validation covers:
- Vault secrets presence.
- Proxmox host storage/datasets/realm and subnet collision checks.
- Guest SSH reachability and apt-cacher proxy config.
- Docker/compose presence on Docker guests.
- AdGuard DNS behavior (known good + known bad + internal rewrites).
- NPM proxy host/access list/cert/redirect behavior.
- Cloudflare DNS records (present + removed records).
- Organizr and Heimdall entries for all NPM internal hosts.
- Nagios service, version, config syntax, rendered object counts, and web endpoint checks.
- Service port checks for core services.

## Repo layout
- `config/`: single source-of-truth
- `terraform/`: Proxmox provisioning
- `ansible/`: host + guest configuration
- `scripts/`: orchestrator
- `docs/`: runbooks
