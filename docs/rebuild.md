# Rebuild

## Minimal manual bootstrap
1. Install Proxmox.
2. Set management IP to `10.20.30.46/24` and enable SSH access.
3. Ensure your SSH public key is installed for `root`.

## Repo-driven rebuild
1. Install Python deps: `pip install -r scripts/requirements.txt`
2. Terraform credentials:
   - Either export `TF_VAR_proxmox_username` + `TF_VAR_proxmox_password` (or `TF_VAR_proxmox_api_token`), or
   - Ensure `terraform_user_password` is in `ansible/secrets.yml` and `ANSIBLE_VAULT_PASSWORD_FILE` is set.
3. Provide vault password (e.g. `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass`)
4. Run orchestrator: `scripts/run.py apply`
5. Host baseline is applied first, then guests.
6. Run fast validation: `scripts/run.py validate`
7. Run full validation before/after major changes: `scripts/run.py validate --mode full`

Any remaining manual steps should be documented here.

## Home Assistant manual bootstrap (HAOS)
HAOS is appliance-style, so HACS installation is a one-time manual step.

1. Complete HA onboarding (handled by repo on first run).
2. Install HACS using the official guide: `https://www.hacs.xyz/docs/setup/download`
3. In HACS, install `Mushroom` (Lovelace card).
4. In HACS, install `ApexCharts Card` (primary TRV graph card).
5. Optional: install `mini-graph-card` as fallback.
6. Restart Home Assistant.
7. Re-apply HA repo automation/config:
   - `python3 scripts/home_assistant.py apply-core`
   - `python3 scripts/home_assistant.py sync-devices`
   - `python3 scripts/home_assistant.py sync-heating-control`
   - `python3 scripts/home_assistant.py sync-heating-dashboard`
   - `python3 scripts/home_assistant.py sync-hue-scenes`

## HAOS note
Home Assistant OS uses its own networking stack and does not consume cloud-init.
Ensure your router has a DHCP reservation for `10.20.30.134` (or update `config/homelab.yaml` and NPM/AdGuard rewrites).

## Access notes
- Guests are reachable via SSH keys.
- A single vaulted root password is also set for guest console access.
- Per-service login references are written to Proxmox Notes by `scripts/proxmox_metadata.py` from `config/homelab.yaml`.
- Proxmox Notes store vault variable names only (not cleartext passwords).
