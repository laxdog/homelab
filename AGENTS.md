# AGENTS.md

## What this repo is

This is the homelab infrastructure repo. It manages Proxmox guests, Ansible roles, Terraform resources, DNS (AdGuard), reverse proxy (NPM), monitoring (Nagios), remote nodes, Home Assistant config, and supporting services.

## Core principle

This repo is the source of truth for all infrastructure. No changes should be made directly on any host without being reproducible from this repo. Agents must not push config onto boxes without committing it.

## Who reads this file

Both Claude and Codex agents pick up AGENTS.md automatically. All agents operating in this repo must read this file before taking any action.

## Agent roster

| Agent | Status | Scope | Detail |
|---|---|---|---|
| homelab | Active | Proxmox, Ansible, Terraform, Nagios, AdGuard, NPM, storage, networking, remote nodes | This file + docs/backlog.md |
| home-assistant | Active | VM122 HA config, automations, scripts, dashboards, heating | docs/agents/home-assistant.md |
| media-stack | Active | VM120 arr stack, docker compose, media library | docs/agents/media-stack.md |
| batocera | Inactive | 10.20.30.212, CRT setup | docs/agents/batocera.md |
| raffle-raptor | Consumer only | Uses CT163, Nagios checks, Tailscale DB proxy — does NOT commit here | docs/agents/raffle-raptor.md |

## Cross-agent boundaries: SSO / auth

Auth-model **decisions** for a service (forward-auth vs app-native, which provider, which clients must keep working, who has access) live with the agent that owns that service:
- media-stack → Jellyfin + arr stack + downloaders (`docs/agents/media-stack.md`)
- home-assistant → HA (`docs/agents/home-assistant.md`)
- homelab → everything else it runs (Proxmox UI, Nagios, NetAlertX, router, NPM itself, etc.)

Auth **implementation** is always homelab's: NPM proxy host config, Authentik providers/applications/outposts, LDAP plugin installs on the backing host, group/user provisioning in Authentik, secrets vaulting. The owning agent asks for a change; homelab wires it up in `config/homelab.yaml` + `ansible/`.

Worked example (2026-04-23): media-stack called the direction on Jellyfin — use Authentik LDAP outpost + Jellyfin-native LDAP plugin, drop NPM forward-auth so Android/TV clients keep working, keep local `admin` as break-glass, and bring future normal users in through Authentik invites instead of Jellyfin-local accounts. homelab implemented it across `authentik.ldap`, `jellyfin.ldap`, the `authentik` + `jellyfin-hw` Ansible roles, the Jellyfin External NPM entry, and the Jellyfin user-management runbook. See `docs/authentik.md`, `docs/jellyfin.md`, `docs/media-routing.md`, `docs/runbooks/jellyfin-user-management.md`.

## Estate overview

### Proxmox host
- IP: 10.20.30.46, PVE 9.x (kernel 6.17.9-1-pve)
- Boot: NVMe WDC PC SN520 256GB (nvme0n1)
- Router: ASUS RT-AC86U at 10.20.30.1 (ssh admin@10.20.30.1, key-based)

### Storage pools

| Pool | Type | Disks | Size | Alloc | Purpose |
|---|---|---|---:|---:|---|
| ssd-fast | ZFS solo | Kingston SA400 894G (SATA) | 888G | 17G (2%) | High-IOPS guest rootfs: CT153 AdGuard, CT163 RR-dev, CT170 Authentik |
| ssd-mirror | ZFS mirror | 2x ORICO 477G (SATA) | 476G | 48G (10%) | Redundant guest rootfs: all other 16 guests |
| tank | ZFS raidz1 | 3x Seagate 10TB SAS | 27.3T | 1.3T (4%) | Bulk: media, downloads, backups, templates, tank-vmdata |
| local-lvm | LVM thin | NVMe (shared with boot) | 156G | 0.01% | Nearly empty — only 3 cloud-init ISOs |
| local | dir | NVMe | 69G | 17% | ISOs, templates, import images |

### VMs (4)

| VMID | Name | IP | Storage | Purpose |
|---:|---|---|---|---|
| 120 | media-stack | 10.20.30.120 | ssd-mirror | Docker arr stack + Tdarr |
| 122 | home-assistant | 10.20.30.122 | ssd-mirror | HAOS |
| 133 | nagios | 10.20.30.133 | ssd-mirror | Nagios monitoring (Tailscale: 100.120.89.28) |
| 171 | tailscale-gateway | 10.20.30.171 | ssd-mirror | Tailscale subnet router |

### LXCs (15)

| CTID | Name | IP | Storage | Purpose |
|---:|---|---|---|---|
| 128 | couchdb | 10.20.30.128 | ssd-mirror | CouchDB (Obsidian LiveSync) |
| 153 | adguard | 10.20.30.53 | ssd-fast | Canonical internal DNS |
| 154 | nginx-proxy-manager | 10.20.30.154 | ssd-mirror | Reverse proxy / TLS |
| 156 | apt-cacher-ng | 10.20.30.156 | ssd-mirror | APT cache for all LXCs |
| 157 | freshrss | 10.20.30.157 | ssd-mirror | FreshRSS |
| 158 | netalertx | 10.20.30.158 | ssd-mirror | NetAlertX |
| 159 | healthchecks | 10.20.30.159 | ssd-mirror | Healthchecks |
| 160 | dashboard | 10.20.30.160 | ssd-mirror | Dashboard helper |
| 161 | static-sites | 10.20.30.161 | ssd-mirror | Static sites |
| 162 | browser | 10.20.30.162 | ssd-mirror | Firefox container |
| 163 | rr-application-staging-proxmox | 10.20.30.163 | ssd-fast | RR staging app (Tailscale: 100.92.43.108) |
| 164 | organizr | 10.20.30.164 | ssd-mirror | Organizr |
| 166 | heimdall | 10.20.30.166 | ssd-mirror | Heimdall dashboard |
| 167 | jellyfin-hw | 10.20.30.167 | ssd-mirror | Jellyfin with iGPU hardware transcoding |
| 170 | authentik | 10.20.30.170 | ssd-fast | Authentik identity provider |
| 172 | observability | 10.20.30.172 | ssd-mirror | Prometheus + Grafana + json-exporter |

### Remote nodes

| Name | LAN IP | Tailscale IP | Hardware | Location |
|---|---|---|---|---|
| rr-worker-staging-home | 10.20.30.153 | 100.88.35.124 | ThinkPad X270 / Ubuntu 24.04 | staging |
| rr-worker-prod-mums | 10.20.30.75 | 100.118.218.126 | MacBook Pro 12,1 (2015) / Ubuntu 24.04 | remote (Mum's House) |

Both managed by `remote-node-baseline` + `tailscale-router` roles. Battery management (TLP on X270), powertop, chrony, WiFi sync, Nagios monitoring all deployed.

### Known gotcha: --accept-routes on LAN guests

LAN-resident VMs/LXCs that join the Tailnet should NOT have `--accept-routes` enabled. The tailscale-gateway (VM171) advertises `10.20.30.0/24` as a subnet route. Any guest with `--accept-routes=true` will install this route in Tailscale's policy routing table (table 52) at higher priority than the main table, causing reply traffic to route out `tailscale0` instead of `eth0` — breaking all inbound LAN connectivity (ping, SSH, HTTP all fail).

**Fix:** `tailscale set --accept-routes=false` on the affected guest.

This was discovered when VM133 (Nagios) went unreachable after Tailscale was installed. Packets arrived on eth0 but replies were routed out tailscale0. All current Tailscale guests (VM133, CT163, VM171) have been verified with `RouteAll: false`.

### Known gotcha: router "Domain Name" field must stay blank

Do not set the ASUS RT-AC86U's LAN → DHCP Server → "Domain Name" field to `lax.dog` or `laxdog.uk` (or anything else). Any value is pushed to DHCP clients as a DNS search domain; glibc/macOS resolvers then append it to failed lookups, and because we own a Cloudflare wildcard on `*.lax.dog`, a failed internal resolve expands and hits the wildcard — returning a Cloudflare `1016` that resolvers cache.

Example of the bad path: client resolves `grafana.laxdog.uk`, AdGuard NXDOMAINs (e.g. transient), resolver retries `grafana.laxdog.uk.lax.dog`, wildcard → apex → home NAT → CF `1016`, cached.

**Fix:** blank the field on the router (LAN → DHCP Server → Domain Name), apply, and let client leases renew. Done 2026-04-21 after this surfaced during an AdGuard apply-risk incident.

### Tailscale prefs — config is source of truth

For nodes with the `tailscale_router` role (currently VM171, CT163, rr-worker-staging-home, rr-worker-prod-mums, plus new RR workers provisioned via `docs/runbooks/add-rr-worker-node.md`), per-node Tailscale prefs — `accept_dns`, `accept_routes`, `advertise_exit_node`, `advertise_routes`, `exit_node`, `exit_node_allow_lan_access` — are declared in `config/homelab.yaml` and reconciled by `tailscale set` on every `scripts/run.py guests` (or equivalent ansible apply).

Manual `tailscale set` on these nodes is **ephemeral** — the next ansible apply will revert it to declared values. For persistent changes, edit the config and re-run the play.

Two config-layer assertions run at role-apply time and fail fast on bad config:
- `advertise_exit_node: true` + `exit_node: <nonempty>` — Tailscale rejects this combination at runtime. Caught at config time with a clearer error.
- LAN-resident node (IP in `10.20.30.0/24`) + `accept_routes: true` — triggers the LAN-adjacency gotcha above. Caught at config time.

Nodes **without** the `tailscale_router` role are NOT reconciled today — their runtime Tailscale prefs can drift silently from declared values. Extending reconciliation to non-router nodes is backlogged.

### Firewall testing

When testing firewall rules that restrict access by source IP, the following hosts are available as test sources:

| Host | External IP | Tailscale IP | Notes |
|---|---|---|---|
| Operator home | 212.56.120.65 | — | Static |
| rr-worker-staging-home | 212.56.120.65 | 100.88.35.124 | On home LAN, same NAT exit as operator home — cannot use as untrusted test source |
| rr-worker-prod-mums | 109.155.65.157 | 100.118.218.126 | Dynamic residential (BT/EE) — use for testing residential IP rules |
| rr-application-prod-vps | 159.195.59.97 | 100.82.170.21 | VPS, stable public IP — best source for testing deny rules |

To get current external IP of any host: `ssh <host> "curl -4 -s https://ifconfig.me"`

rr-application-prod-vps is the best available source for testing SSH deny rules since it has a stable public IP not in any homelab allow list. To verify deny rules without an untrusted source, check iptables packet counters on the target (`sudo iptables -L ufw-user-input -n -v`).

## Key files

| Path | Purpose |
|---|---|
| `config/homelab.yaml` | Single source of truth for all infrastructure |
| `ansible/inventory.yml` | Host inventory (remote nodes use Tailscale IPs) |
| `terraform/` | Proxmox guest definitions |
| `docs/backlog.md` | Homelab agent backlog |
| `docs/agents/<name>.md` | Per-agent scope and backlog |
| `docs/changelog.md` | Significant infrastructure changes by date |
| `docs/runbooks/` | Step-by-step procedures for common operations |
| `ansible/secrets.yml` | Vault-encrypted secrets (main) |
| `ansible/secrets-wifi.yml` | Vault-encrypted WiFi PSKs |
| `ansible/secrets-rr-staging.yml` | Vault-encrypted RR DB credentials |
| `~/.ansible_vault_pass` | Vault password file |
| `docs/vpn.md` | Mullvad device inventory, egress IP map, Tailscale exit node docs |
| `docs/runbooks/add-rr-worker-node.md` | Runbook for provisioning new RR worker LXCs |

## Domain architecture

This homelab uses two domains with fundamentally different access models.

### laxdog.uk — Internal domain
- Resolved via AdGuard DNS rewrites on CT153 (all subdomains → NPM at 10.20.30.154)
- Only accessible on the LAN or via Tailscale
- SSL certs issued by NPM / Let's Encrypt via DNS-01 challenge (using Cloudflare API for the laxdog.uk zone — no public A records needed)
- No Cloudflare DNS records needed or used for this domain
- No Authentik protection (LAN-only access is sufficient)
- Examples: `heimdall.laxdog.uk`, `grafana.laxdog.uk`, `dns.laxdog.uk`, `nagios.laxdog.uk`

### lax.dog — External domain
- DNS managed via Cloudflare (API key in vault)
- Cloudflare A records point to the homelab's external IP
- Accessible from the internet
- SSL certs issued via Cloudflare / LE DNS-01 challenge using Cloudflare API
- Protected by Authentik forward-auth for sensitive services
- Examples: `jellyfin.lax.dog`, `ha.lax.dog`, `raffle-raptor.lax.dog`

### Rules for agents

**Adding a new internal service (laxdog.uk):**
1. Add AdGuard rewrite: `subdomain.laxdog.uk → 10.20.30.154` in `config/homelab.yaml` under `adguard.rewrites`
2. Add NPM proxy host pointing at the backend in `config/homelab.yaml` under `npm.proxy_hosts`
3. Add the new subdomain to cert 17's SAN list via `certbot --expand` inside the NPM container (DNS-01 via Cloudflare API)
4. No Cloudflare A records needed

**Adding a new external service (lax.dog):**
1. Add Cloudflare DNS A record → homelab external IP in `config/homelab.yaml` under `cloudflare.zones`
2. Add NPM proxy host with the Cloudflare-issued cert in `config/homelab.yaml` under `npm.external_proxy_hosts`
3. Add Authentik forward-auth config if the service is sensitive
4. Consider whether it actually needs to be external — prefer `laxdog.uk` for internal tools

**Never:**
- Add Cloudflare DNS records for `laxdog.uk` subdomains
- Expect AdGuard rewrites to work for `lax.dog` from outside the LAN

> **WARNING: laxdog.uk subdomains must NEVER have Cloudflare DNS records.** They are resolved internally via AdGuard only. Adding a Cloudflare record for a laxdog.uk subdomain exposes internal service IPs to the internet and breaks the internal-only access model. The laxdog.uk LE cert uses DNS-01 challenge via the Cloudflare API for the `laxdog.uk` zone — this does NOT require public A records.

**Troubleshooting certs:**
- Cert issues on `laxdog.uk` = NPM cert problem. The internal cert (cert 17) uses DNS-01 challenge via Cloudflare API. New SANs are added by running `certbot certonly --expand` inside the NPM container with the updated domain list.
- Cert issues on `lax.dog` = Cloudflare / LE problem (check Cloudflare dashboard)

## Running Ansible applies

Full apply is not low-risk. Known patterns that have caused outages:

- **AdGuard role applies carry DNS risk.** Two outages in two days (2026-04-20, 2026-04-21) from template bugs: schema_version missing, bootstrap_dns format mismatch, rewrites enabled flag. As of commit `72e938d` the role renders full declared state (DNS, rewrites, user_rules, persistent clients, safe_search, schema_version) directly into `AdGuardHome.yaml`, so template changes can break AdGuard startup entirely — when that happens, DNS is down for the whole homelab until recovery.
- **`docker-host` role has an apt conflict between `docker-compose-plugin` and `docker-compose-v2`** that can leave `docker.service` broken on hosts where both Ubuntu's `docker-compose-v2` and Docker's `docker-compose-plugin` want `/usr/libexec/docker/cli-plugins/docker-compose`. Failure leaves `docker-ce` in dpkg `iU` state, all containers on the host go down. (Backlog item.)

Until these are fixed:

- Prefer narrow `--limit <host>` and `--tags <name>` when reconciling drift. Scope the blast radius before every apply.
- If a broad apply is necessary, run outside peak use and have recovery commands ready:
  - **AdGuard — run applies in low-traffic windows.** Before applying any AdGuard template change, keep this restart command ready:
    ```bash
    ssh root@10.20.30.53 /opt/AdGuardHome/AdGuardHome -s restart
    ```
    If AdGuard refuses to start after a template change, inspect `/opt/AdGuardHome/AdGuardHome.yaml` for the three things that have caused startup failures so far: `schema_version: 33` at the bottom, list-shaped `bootstrap_dns` (not scalar), and `enabled: true` on each rewrite. `journalctl -u AdGuardHome -n 30` usually points at the specific yaml unmarshal error.
  - **docker-compose apt conflict** (force-overwrite + socket+service restart):
    ```bash
    ssh root@<host> 'apt-get install -y -o Dpkg::Options::=--force-overwrite docker-compose-plugin && \
      dpkg --configure -a && \
      systemctl reset-failed docker.service && \
      systemctl start docker.socket docker.service'
    ```

See commit `6825272` for the 2026-04-20 `loki.laxdog.uk` reconcile (previous-generation AdGuard outage), and `72e938d` for the 2026-04-21 template rebuild that surfaced the three AdGuard startup-failure modes above.

## Universal conventions

These apply to ALL agents.

### ALWAYS
- Read AGENTS.md and your agent detail doc before starting any session
- Check your agent's backlog at session start
- Commit all changes with narrow, descriptive messages
- Update your backlog when completing items or discovering new ones
- Verify service health after every change
- Use by-id paths for ZFS pool members
- Run `terraform plan` before `terraform apply`
- Prove live state before assuming from repo
- One guest at a time for migrations — verify each before proceeding to the next
- Document router DHCP changes in `docs/network.md`
- Add new WiFi networks via `ansible/playbooks/wifi-sync.yml`, not manually
- When adding a new guest, follow `docs/runbooks/add-new-guest.md`
- When adding a remote node, follow `docs/runbooks/add-remote-node.md`
- Guest IPs must match the convention: last octet = VM/CT ID (except CT153 adguard = .53)

### NEVER
- Push without explicit user instruction
- Make changes on hosts without committing to the repo
- Touch another agent's scope without explicit instruction
- Run `terraform apply` without `plan` first
- Move multiple guests simultaneously
- Touch `/srv/data/media` or `/srv/data/downloads` (tank virtiofs mounts)
- Run destructive commands (`rm -rf`, `zpool destroy`, `pvesm remove`, `git reset --hard`) without explicit user confirmation
- Amend or rewrite published git history

## End of session

Every agent must do the following before ending a session:

- [ ] Run `terraform plan` (homelab agent only) — confirm no unexpected drift
- [ ] Update `docs/changelog.md` with any significant changes made this session
- [ ] Update your agent backlog — tick off completed items, add new ones discovered
- [ ] Commit all uncommitted changes (narrow commits, no unrelated dirty files)
- [ ] Push only if the user has instructed you to
- [ ] Update `docs/claude-code-handoff.md` with current HEAD and brief session summary

## Infrastructure consumers

Agents/systems that USE this infrastructure but do NOT commit to this repo:
- **RaffleRaptor application agents** — use CT163, Nagios monitoring, Tailscale DB proxy. Any infra changes they need should be requested from the homelab agent. See docs/agents/raffle-raptor.md.
