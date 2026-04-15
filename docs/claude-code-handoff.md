# Homelab Session Handoff

For full estate reference see `AGENTS.md` in the repo root.
For current task backlog see `docs/backlog.md`.
For per-agent docs see `docs/agents/`.
For significant changes see `docs/changelog.md`.
For runbooks see `docs/runbooks/`.

## Current session context
- Last updated: 2026-04-15
- Current HEAD: (updated at session close)

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
- raptor-node-staging: `ssh mrobinson@100.88.35.124`
- mums-house-mbp: `ssh mrobinson@100.118.218.126`

### Nagios (VM133)
Accessible via Tailscale: `ssh ubuntu@100.120.89.28`
Config: `/usr/local/nagios/etc/objects/homelab.cfg` + `remote-nodes.cfg`

### AdGuard role destructive-render pattern
The AdGuard ansible role renders a partial template that overwrites the full AdGuardHome.yaml. A `meta: flush_handlers` after the template task forces an immediate restart so API tasks see the post-render empty state and rebuild via drift detection. This is a known architectural pattern — do not remove the flush_handlers.
