# Secrets

Secrets are managed with Ansible Vault.

## Common commands
- Create: `ansible-vault create ansible/secrets.yml`
- Edit: `ansible-vault edit ansible/secrets.yml`
- View: `ansible-vault view ansible/secrets.yml`

## Vault password
Use a local password file (not committed) and configure the orchestrator to pass it.

## Variables expected in vault
- `nut_admin_password`
