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

## Variables expected in vault
- `nut_admin_password`
- `terraform_user_password`
- `npm_admin_password`
- `npm_api_password`
- `npm_access_password`
- `cloudflare_api_token`
- `root_password`
- `root_password_hash`
