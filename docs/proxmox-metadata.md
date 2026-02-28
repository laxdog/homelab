# Proxmox Metadata

This repo manages Proxmox VM/CT tags and Notes (description field) via:

- `scripts/proxmox_metadata.py`

## What it writes

- Tags:
- `laxdog.uk` when a guest has an internal NPM hostname.
- `lax.dog` when a guest has an external NPM hostname.
- `oidc` when listed in `config.homelab.yaml` under `proxmox_metadata.oidc_services`.
- Existing non-managed tags are preserved.

- Notes:
- One structured line per guest including:
- service name, kind, IP
- access scope (`internal`, `external`, or both)
- OIDC flag
- associated domains
- credential references (`label:username|vault_var`)
- no cleartext passwords are written to Proxmox notes

## Source of truth

- `config/homelab.yaml`:
- `proxmox_metadata.oidc_services`
- `proxmox_metadata.service_credentials`
- `npm.proxy_hosts`
- `npm.external_proxy_hosts`
- `services.vms` / `services.lxcs` (service names, IDs, IPs)

Credential variables referenced in notes are defined in:
- `ansible/secrets.yml`
- `config/homelab.yaml` -> `validation.vault_required_vars`

## Commands

- Apply metadata:
- `python3 scripts/proxmox_metadata.py`

- Check drift (CI-friendly):
- `python3 scripts/proxmox_metadata.py --check`

- Verbose:
- `python3 scripts/proxmox_metadata.py --verbose`

`scripts/run.py apply` applies metadata automatically.
Both `scripts/run.py validate` (fast) and `scripts/run.py validate --mode full` include metadata drift checking.

## Home Assistant example

`home-assistant` note references:
- `ui:mrobinson|home_assistant_admin_password`
- `ssh:root|root_password`

Read secret value from vault when needed:
- `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -c local -m ansible.builtin.debug -a "var=home_assistant_admin_password" -e @ansible/secrets.yml`
