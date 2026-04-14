# Home Assistant Agent

## Scope
- VM122 at 10.20.30.122 (HAOS)
- All automations, scripts, dashboards, heating logic, status lights
- `config/homelab.yaml` home_assistant: block
- `scripts/home_assistant.py` generator
- `ansible/roles/home-assistant-bootstrap/` (if present)
- Terraform: `haos_vms["home-assistant"]`

## Out of scope
Do not touch:
- Proxmox host config
- Ansible roles other than home-assistant-*
- Terraform resources other than haos_vms
- Any other VM or LXC
- AdGuard, NPM, Nagios config (request changes from homelab agent)

## Entry points
- Live HA: http://10.20.30.122:8123
- Internal: https://ha.laxdog.uk
- External: https://ha.lax.dog (Authentik-protected)
- Config: `config/homelab.yaml` (home_assistant: block)

## Access
- No SSH addon installed currently (see backlog)
- QEMU guest agent not running (HAOS doesn't ship it)
- API access requires a long-lived token (generate via Profile -> Security -> Long-Lived Access Tokens)
- Proxmox console: `qm terminal 122` (interactive only, cannot be scripted)

## Principle
All automations, scripts, dashboards, and helpers should be defined in `config/homelab.yaml` and generated/applied via scripts or the bootstrap role. HA runtime `.storage` internals (integrations, entity registry, device registry) are intentionally runtime-managed.

## Backlog

- [ ] Install HA SSH addon for CLI access
  - Context: no SSH to HAOS currently. Addon enables `ha` CLI for automation.
  - Effort: low
  - Added: 2026-04-14

- [ ] Add HA long-lived token to vault
  - Context: needed for API-driven config changes. Generate in HA UI, vault as `ha_long_lived_token` in `ansible/secrets.yml`.
  - Effort: low
  - Added: 2026-04-14

- [ ] Audit UI-managed config vs repo-managed
  - Context: some HA config may have been added via UI only and not reflected in repo. Identify and bring into repo management.
  - Effort: medium
  - Added: 2026-04-14
