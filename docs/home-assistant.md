# Home Assistant

Source of truth:
- `config/homelab.yaml` -> `services.vms.home-assistant`, `home_assistant`
- `ansible/secrets.yml` -> `home_assistant_admin_password`

## Bootstrap behavior
- HAOS VM is provisioned by Terraform.
- During `scripts/run.py guests`, role `home-assistant-bootstrap` checks `/api/onboarding`.
- If onboarding is not complete, it creates the initial owner user via API.
- If onboarding is already complete, no user is changed.

## Access
- Internal: `https://ha.laxdog.uk`
- External: `https://ha.lax.dog` (behind NPM/Authentik policy)

## Credential reference
- Username: `config.home_assistant.admin_username` (currently `mrobinson`)
- Password variable: `home_assistant_admin_password`
