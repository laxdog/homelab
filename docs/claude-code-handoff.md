# Homelab Session Handoff

For full estate reference see `AGENTS.md` in the repo root.
For current task backlog see `docs/backlog.md`.
For per-agent docs see `docs/agents/`.
For significant changes see `docs/changelog.md`.
For runbooks see `docs/runbooks/`.

## Current session context
- Last updated: 2026-04-22
- Current HEAD: b5961a6
- Session summary: Authentik + CT167 Jellyfin LDAP pilot-auth follow-up completed. Exact Authentik root cause was provider wiring: the LDAP outpost bind flow was effectively being read from `authorization_flow`, while the repo had set the intended bind flow on `authentication_flow`; updating the repo-managed provider setup to set `authorization_flow: default-authentication-flow` fixed CT167 LDAP bind/search. Exact Jellyfin root cause was plugin config drift: CT167 had been managed with `Jellyfin.Plugin.LDAP_Auth.xml`, but the live LDAP plugin was reading `LDAP-Auth.xml`, and the managed XML serialized `LdapProfileImageFormat` as `0`, which caused the plugin to fall back to its built-in sample config (`CN=BindUser,DC=contoso,DC=com`). Updated repo config/template to manage `LDAP-Auth.xml` and serialize `LdapProfileImageFormat` as `Default`, then re-applied CT167 narrowly. Runtime status now: Authentik LDAP bind/search from CT167 works, local Jellyfin `admin` still works as break-glass, and a non-admin pilot LDAP Jellyfin login for `ldapservice` succeeds end-to-end. `cjess` remains local and untouched. Ingress intentionally unchanged: `jellyfin.lax.dog` still has Authentik forward-auth and the next narrow pass should remove that to avoid auth stacking before migrating real users.

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
