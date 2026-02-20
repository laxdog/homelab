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
2. Provide vault password (e.g. `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass`)
3. `scripts/run.py apply`

## Repo layout
- `config/`: single source-of-truth
- `terraform/`: Proxmox provisioning
- `ansible/`: host + guest configuration
- `scripts/`: orchestrator
- `docs/`: runbooks
