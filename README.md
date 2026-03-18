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
4. `scripts/run.py metadata` (optional manual re-sync of Proxmox tags/notes)

## Validate
- Run fast validation (default): `scripts/run.py validate`
- Run full validation: `scripts/run.py validate --mode full`
- Validation covers:
- Vault secrets presence.
- Proxmox host storage/datasets and subnet collision checks.
- Guest SSH reachability and apt-cacher proxy config.
- Proxmox VM/CT metadata drift check (`scripts/proxmox_metadata.py --check`).
- Docker/compose presence on Docker guests.
- Tailscale gateway service/sysctl readiness checks (pre-join safe).
- AdGuard DNS behavior (known good + known bad + internal rewrites).
- NPM proxy host/access list/cert/redirect behavior.
- Cloudflare DNS records (present + removed records).
- Organizr and Heimdall entries for all NPM internal hosts.
- Nagios service, version, config syntax, rendered object counts, and web endpoint checks.
- Service port checks for core services.

`--mode fast` is optimized for routine checks (critical health, key DNS/HTTPS paths, metadata drift).
`--mode full` runs the complete end-to-end validation suite.

## Repo layout
- `config/`: single source-of-truth
- `terraform/`: Proxmox provisioning
- `ansible/`: host + guest configuration
- `scripts/`: orchestrator
- `docs/`: runbooks
  - includes `docs/tailscale.md` for phase-1 remote-access setup steps
