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

- Staging worker password: `rr_discovery_staging_db_password` in `ansible/secrets-rr-staging.yml`
- Prod worker password: `rr_discovery_prod_db_password` in `ansible/secrets.yml`

> **Follow-up:** consolidate to a single vault file. The two-file split predates the prod rollout — staging was historically carved out into its own vault file; prod landed in the main vault; keeping both is a wart worth cleaning up later.

Extraction command template (prints plaintext to stdout):

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -i 'localhost,' -c local \
  -m debug -a 'var=<VAULT_VAR_NAME>' -e @ansible/<SECRETS_FILE>
```

Example for prod:

```bash
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass ansible localhost -i 'localhost,' -c local \
  -m debug -a 'var=rr_discovery_prod_db_password' -e @ansible/secrets.yml
```

**Operator action only.** Where RR places the value on their side (compose env var, per-worker config, secrets manager, etc.) is RR's decision — homelab documents what the password is and where it lives, not how it gets consumed downstream.

## Known issues
- **overdue_count WARN on prod statusz** — RR agent investigating worker capacity. Homelab action: none until RR agent reports back.
- **502s on rr-application-staging-proxmox (2026-04-08)** — traced to planned maintenance restart (two full-estate stopall/startall cycles for SSD hardware install). Closed as known incident.
