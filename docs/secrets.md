# Secrets

Secrets are managed with Ansible Vault.

## Common commands
- Edit: `ansible-vault edit ansible/secrets.yml`
- Add/replace a single value:
  - `ansible-vault encrypt_string 'VALUE' --name 'var_name'`
- View a single value (per-value vault blocks):
  - `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -c local -m ansible.builtin.debug -a "var=var_name" -e @ansible/secrets.yml`

Notes:
- `ansible/secrets.yml` uses per-value vault blocks, so `ansible-vault view ansible/secrets.yml` will fail.

## Vault password
Use a local password file (not committed) and configure the orchestrator to pass it.
Recommended: `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass`
`scripts/run.py` will auto-use `~/.ansible_vault_pass` if present.

## Variables expected in vault
- `nut_admin_password`
- `terraform_user_password`
- `adguard_admin_password`
- `adguard_admin_password_hash`
- `npm_admin_password`
- `npm_api_password`
- `npm_access_password`
- `cloudflare_api_token`
- `root_password`
- `root_password_hash`
- `organizr_admin_password`
- `organizr_hash_key`
- `organizr_registration_password`
- `organizr_api_key`
- `authentik_admin_password`
- `authentik_postgres_password`
- `authentik_secret_key`
- `couchdb_admin_password`
- `healthchecks_admin_password`
- `healthchecks_secret_key`
- `nagios_admin_password`
- `jellyfin_admin_password`
- `home_assistant_admin_password`
- `discord_webhook` (Nagios alerts)
- `tplink_username` (optional; required for HA TP-Link/KH100 integration)
- `tplink_password` (optional; required for HA TP-Link/KH100 integration)

## Optional media-stack vars
- `plex_claim_token`
- `gluetun_openvpn_user`
- `gluetun_openvpn_password`
- `gluetun_wireguard_private_key`
- `gluetun_wireguard_addresses`
- `media_stack_sabnzbd_api_key`
- `media_stack_usenet_username`
- `media_stack_usenet_password`
- `media_stack_indexer_nzbgeek_api_key`
- `media_stack_indexer_nzbfinder_api_key`
- `media_stack_indexer_nzbplanet_api_key`
- `media_stack_indexer_jackett_api_key`
- `media_stack_transmission_rpc_username`
- `media_stack_transmission_rpc_password`

Notes:
- `scripts/run.py apply` will use `terraform_user_password` when the vault password file is available.
