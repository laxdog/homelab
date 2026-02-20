# Rebuild

## Minimal manual bootstrap
1. Install Proxmox.
2. Set management IP to `10.20.30.46/24` and enable SSH access.
3. Ensure your SSH public key is installed for `root`.

## Repo-driven rebuild
1. Install Python deps: `pip install -r scripts/requirements.txt`
2. Export Terraform credentials: `TF_VAR_proxmox_username` + `TF_VAR_proxmox_password` (or `TF_VAR_proxmox_api_token`)
3. Provide vault password (e.g. `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass`)
4. Run orchestrator: `scripts/run.py apply`
5. Host baseline is applied first, then guests.

Any remaining manual steps should be documented here.

## Access notes
- Guests are reachable via SSH keys.
- A single vaulted root password is also set for guest console access.
