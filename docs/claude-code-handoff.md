# Homelab Session Handoff

For full estate reference see `AGENTS.md` in the repo root.
For current task backlog see `docs/backlog.md`.
For per-agent docs see `docs/agents/`.
For significant changes see `docs/changelog.md`.
For runbooks see `docs/runbooks/`.

## Current session context
- Last updated: 2026-04-22
- Current HEAD: ced8f1b
- Session summary: Authentik + CT167 Jellyfin LDAP groundwork pass. Read current repo/docs and verified live state first: CT167 is the active Jellyfin target with hardware transcoding healthy; `jellyfin.laxdog.uk` points to CT167 without forward-auth; `jellyfin.lax.dog` still points to CT167 with Authentik forward-auth. Added repo-managed Authentik LDAP provider/application/outpost pattern on CT170 plus repo-managed CT167 Jellyfin LDAP plugin/config deployment. Runtime status: Authentik LDAP outpost container is healthy on CT170, Jellyfin LDAP plugin is installed and loaded on CT167, and local Jellyfin `admin` still authenticates as break-glass. Remaining blocker: LDAP bind/search from CT167 to Authentik still fails with `Invalid credentials (49)`, so no pilot LDAP user login was cut over. Ingress intentionally left unchanged; next pass should fix LDAP bind first, then remove `jellyfin.lax.dog` forward-auth in a narrow cutover.

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
