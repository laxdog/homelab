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

## Source of truth

- `config/homelab.yaml`:
- `proxmox_metadata.oidc_services`
- `proxmox_metadata.service_credentials`
- `npm.proxy_hosts`
- `npm.external_proxy_hosts`

## Commands

- Apply metadata:
- `python3 scripts/proxmox_metadata.py`

- Check drift (CI-friendly):
- `python3 scripts/proxmox_metadata.py --check`

- Verbose:
- `python3 scripts/proxmox_metadata.py --verbose`

`scripts/run.py apply` applies metadata automatically.
Both `scripts/run.py validate` (fast) and `scripts/run.py validate --mode full` include metadata drift checking.
