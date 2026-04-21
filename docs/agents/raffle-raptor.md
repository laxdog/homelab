# RaffleRaptor — Infrastructure Context

## Status
CONSUMER ONLY — RaffleRaptor agents do not commit to this repo.

## What this repo provides to RaffleRaptor
- **CT163** (rr-application-staging-proxmox) at 10.20.30.163 — 40GB on ssd-fast, Tailscale 100.92.43.108
- **Tailscale DB proxy**: socat on CT163 proxying PostgreSQL from Docker container to rr-worker-staging-home (100.88.35.124:5432)
- **Nagios monitoring**: all RR checks defined in homelab Nagios config on VM133
- **Ansible role**: `rr-staging-db-access` manages DB user, firewall rules, and socat proxy on CT163

## RaffleRaptor does NOT
- Commit to this repo
- Manage Proxmox, Ansible, or Terraform resources
- Own Nagios check definitions (homelab agent does)

## How to request infra changes
Contact the homelab agent. Examples:
- New Nagios check -> homelab agent adds it to homelab.cfg
- CT163 disk resize -> homelab agent does it via Proxmox + config/homelab.yaml
- New DB proxy rule -> homelab agent updates rr-staging-db-access role

## Current monitoring
Nagios checks for RR (all on VM133):
- **rr-application-prod-vps**: statusz, healthz, HTTP domain, VPN, snapshot, total-perf, Cloudflare
- **rr-application-staging-proxmox**: healthz, statusz, HTTP domain (both laxdog.uk and lax.dog), VPN, snapshot, total-perf, Cloudflare
- Notifications: prod enabled, dev enabled (re-enabled 2026-04-14)

## Prod VPS access
- **Tailscale IP**: 100.82.170.21 (hostname: rr-application-prod-vps)
- **Public IP**: 159.195.59.97
- **Primary SSH**: `ssh mrobinson@100.82.170.21` (via Tailscale)
- **Fallback SSH**: `ssh mrobinson@159.195.59.97` (allowed from 212.56.120.65 and 109.155.65.157 only)
- **SSH hardened**: UFW restricts port 22 to operator home, mum's house, and Tailscale CGNAT range. All other SSH is denied.
- **Monitoring**: Nagios checks (PING, SSH, Disk, Tailscale, NTP) via Tailscale IP from VM133
- **Logs**: Promtail shipping journald + syslog + `/var/log/raffle-raptor/*.log` to Loki on CT172
- **Prometheus**: Scraped via json-exporter through public URL (CT172 can't reach Tailscale IPs directly)

## Node map

| Name | Role | Location | Tailscale IP |
|---|---|---|---|
| rr-application-prod-vps | Prod scraper VPS | Remote VPS (159.195.59.97) | 100.82.170.21 |
| rr-worker-prod-mums | Prod remote node | Mum's house | 100.118.218.126 |
| rr-worker-staging-home | Staging test node | Operator home LAN | 100.88.35.124 |
| rr-worker-prod-proxmox (CT173) | Prod worker LXC on Proxmox | Homelab | 100.104.174.2 |
| rr-application-staging-proxmox (CT163) | Staging app LXC on Proxmox | Homelab | 100.92.43.108 |

## Docker on RR worker nodes

The RR-worker nodes split into two camps for Docker provisioning:

- **CT173 (`rr-worker-prod-proxmox`)**: in `docker_hosts` (via `roles: [docker]`). Homelab's `docker-host` role installs and maintains Docker. RR worker runs inside that managed stack.
- **`rr-worker-prod-mums`**: NOT in `docker_hosts`. Homelab does not install Docker. RR's worker compose installs Docker on demand via `pre_tasks` in their own role. This is by design — homelab doesn't manage RR's runtime software for remote nodes.

(Staging-home is currently out of scope for RR worker deployment; Docker provisioning there will follow whichever model matches its workload once deployed.)

## Secret handoff

DB worker passwords are vaulted in this repo and must be copied into RR's compose **out-of-band**. No automated handoff exists today — operator extracts the value from the homelab vault and pastes it into RR's side.

- Staging worker password: `rr_worker_staging_db_password` in `ansible/secrets.yml`
- Prod worker password: `rr_worker_prod_db_password` in `ansible/secrets.yml`

Both entries live in the single `ansible/secrets.yml` vault (the earlier
`secrets-rr-staging.yml` split was retired on 2026-04-21 when staging was
migrated from `rr_discovery_staging` to `rr_worker` with strict grants).

Extraction command template (prints plaintext to stdout):

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -i 'localhost,' -c local \
  -m debug -a 'var=<VAULT_VAR_NAME>' -e @ansible/secrets.yml
```

Example for prod:

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -i 'localhost,' -c local \
  -m debug -a 'var=rr_worker_prod_db_password' -e @ansible/secrets.yml
```

Example for staging:

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -i 'localhost,' -c local \
  -m debug -a 'var=rr_worker_staging_db_password' -e @ansible/secrets.yml
```

**Operator action only.** Where RR places the value on their side (compose env var, per-worker config, secrets manager, etc.) is RR's decision — homelab documents what the password is and where it lives, not how it gets consumed downstream.

## DB access ownership model

Split between the two repos for the Postgres layer behind the Tailscale proxy.
Written down so divergent assumptions don't silently cause drift.

**Homelab owns (this repo, via `ansible/roles/rr-db-access/`)**
- Postgres role provisioning for the worker user (`rr_worker` on both envs)
- Password rotation via the vault — `rr_worker_{staging,prod}_db_password`
- Grants on `public` schema tables + sequences (REVOKE ALL then GRANT declared set)
- `pg_hba.conf` curated rules at the top (scram from the docker gateway /32, reject-everywhere for everything else on the worker user)
- socat listener bound to the host's Tailscale IP + `RR-DB-INGRESS` iptables chain gating tailnet source IPs

**RR owns**
- DB container lifecycle: image (`timescale/timescaledb:*-pg*`), compose, volumes, restart policy
- Schema: table structure, indexes, migrations, data
- What privileges the worker actually needs — i.e. the contract below

**Image provides (neither repo declares)**
- Baseline `pg_hba.conf` tail: `host all all all scram-sha-256` (stock timescaledb image default)
- Our security model depends on the role's specific-user rules being inserted **before** this catch-all — they are. The catch-all is only reachable for users we haven't curated.

**Grants contract (current, both envs)**
- Tables: `SELECT, INSERT, UPDATE` on all tables in `public` (strict — revoked everything else including `DELETE`, `REFERENCES`, `TRIGGER`, `TRUNCATE`)
- Sequences: `USAGE, SELECT` (USAGE required for `nextval()` on SERIAL/IDENTITY columns; SELECT alone covers `currval`/`lastval` only)
- Source of truth when a mismatch arises: RR's written spec (e.g. `docs/workers.md` in the RR repo, once it exists). Homelab role declares the grants list in `config/homelab.yaml` under each host's `rr_db_access.grants` key.

**Reproducibility / disaster recovery**
- If the DB container is recreated with a fresh volume: RR's migrations recreate the schema; homelab's `rr-db-access` role must re-run to recreate the `rr_worker` role, grants, and pg_hba rules. The vaulted password survives — the role `ALTER ROLE … LOGIN PASSWORD` re-installs it into the fresh DB.
- Order matters: schema first (so `GRANT … ON ALL TABLES` has tables to grant on), then the role apply. Running the role against a freshly-migrated DB is idempotent.

**Known risk — catch-all pg_hba rule is an image default**
- The `host all all all scram-sha-256` tail is declared by the timescaledb image, not by either repo. If the image changes that default (removes it, tightens it, or broadens it to `trust`), `rr_worker` auth could break silently, or the catch-all could start accepting users the curated rules didn't intend to expose.
- Monitoring gap: no drift-detection on `pg_hba.conf` beyond what the role itself writes. A future hardening pass could have the role strip the catch-all and manage the full file — explicit scope decision deferred.

## Grafana dashboards

RR owns its dashboards end-to-end. Homelab provides the Grafana instance (CT172, `https://grafana.laxdog.uk`) and the API credential; RR ships dashboards as JSON via the API.

- **Push target**: `POST /api/dashboards/db` with `overwrite: true` in the body. Pushing with the same UID updates in place.
- **UID prefix**: `rr-` — every RR-owned dashboard UID must start with `rr-` so homelab can identify them without digging into labels. Dashboards without this prefix are out of RR's scope to modify.
- **Authentication**: service-account token, name `rr-orchestrator`, Editor role. Grafana 10+ deprecated `/api/auth/keys`; this is the modern equivalent (service account + token).
- **Credential handoff**: token handed off out-of-band (secure channel — not in this repo, not in commits). If RR loses the token or needs it rotated, contact the homelab agent to mint a replacement via the same service account (`/api/serviceaccounts/{id}/tokens`).
- **Scope**: Editor covers dashboard CRUD + datasource read. Not enough for folder/permission/datasource management — if RR needs more, flag it as a scope change before adjusting the role.

## Known issues
- **overdue_count WARN on prod statusz** — RR agent investigating worker capacity. Homelab action: none until RR agent reports back.
- **502s on rr-application-staging-proxmox (2026-04-08)** — traced to planned maintenance restart (two full-estate stopall/startall cycles for SSD hardware install). Closed as known incident.
