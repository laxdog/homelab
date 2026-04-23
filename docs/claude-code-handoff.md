# Homelab Session Handoff

For full estate reference see `AGENTS.md` in the repo root.
For current task backlog see `docs/backlog.md`.
For per-agent docs see `docs/agents/`.
For significant changes see `docs/changelog.md`.
For runbooks see `docs/runbooks/`.

## Current session context
- Last updated: 2026-04-23
- Current HEAD: 33774b7
- Session summary: Home Assistant follow-up shifted away from the recent ambient/TRV heating presentation; that issue is now explicitly backlogged for later layout review rather than being iterated further in place. Added a new repo-managed Lights dashboard at `/house-lights/overview`, generated from `home_assistant.lights_dashboard` by `python3 scripts/home_assistant.py sync-lights-dashboard`. Live inventory used for the first pass: `light.philips_lct015` (Living Room Hue Bulb, color + color temperature), `light.aurora_fwbulb01` (Dining Area Zigbee Bulb, brightness), `light.philips_lct015_2` (Bedroom Hue Bulb, currently unavailable but still included as a user-facing room light), and `light.philips_lwa001` (unassigned/unavailable, surfaced in an Unassigned section). Dedicated status bulb `light.philips_lct012` is intentionally excluded from this general-use lights page. Dashboard design is control-first: quick all-on/all-off actions plus room sections using capability-aware Mushroom light cards so color, color temperature, brightness, and effect controls only appear where the live entity supports them. One unrelated dirty file remains out of scope and untouched: `ansible/inventory.yml`.

## Durable user preferences
- Safety-first over speed
- Accuracy over speed
- No opportunistic changes
- Narrow commits only
- Do not include unrelated dirty files
- Do not push unless explicitly told
- Prefer proving live state over assuming from repo only
- If a task is app-side and not homelab-owned, stop at a precise boundary/handoff

## Key operational notes

### Ansible apply pattern
```bash
cd /home/mrobinson/source/homelab/ansible
ANSIBLE_VAULT_PASSWORD_FILE=/home/mrobinson/.ansible_vault_pass \
ANSIBLE_ROLES_PATH=./roles \
ansible-playbook -i inventory.yml playbooks/guests.yml --limit '<host>'
```

### Known quirk
`guests.yml --limit 'adguard,nginx-proxy-manager,heimdall'` can get stuck or wander into unrelated NPM cert work. Workaround: use a narrow temporary playbook targeting only the needed roles.

### Terraform credentials
```bash
cd terraform
TF_VAR_proxmox_username='terraform-prov@pve' \
TF_VAR_proxmox_password='<from vault: terraform_user_password>' \
terraform plan
```

### AdGuard API
```bash
curl -u admin:<from vault: adguard_admin_password> http://10.20.30.53/control/...
```

### Router access
```bash
ssh admin@10.20.30.1  # key-based, no password
nvram get dhcp_staticlist  # DHCP reservations
```

### Remote nodes
Both use Tailscale IPs in the ansible inventory:
- rr-worker-staging-home: `ssh mrobinson@100.88.35.124`
- rr-worker-prod-mums: `ssh mrobinson@100.118.218.126`

### Nagios (VM133)
Accessible via Tailscale: `ssh ubuntu@100.120.89.28`
Config: `/usr/local/nagios/etc/objects/homelab.cfg` + `remote-nodes.cfg`

### AdGuard role destructive-render pattern
The AdGuard ansible role renders a partial template that overwrites the full AdGuardHome.yaml. A `meta: flush_handlers` after the template task forces an immediate restart so API tasks see the post-render empty state and rebuild via drift detection. This is a known architectural pattern — do not remove the flush_handlers.
