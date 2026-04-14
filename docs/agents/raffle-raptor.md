# RaffleRaptor — Infrastructure Context

## Status
CONSUMER ONLY — RaffleRaptor agents do not commit to this repo.

## What this repo provides to RaffleRaptor
- **CT163** (raffle-raptor-dev) at 10.20.30.163 — 40GB on ssd-fast, Tailscale 100.92.43.108
- **Tailscale DB proxy**: socat on CT163 proxying PostgreSQL from Docker container to raptor-node-staging (100.88.35.124:5432)
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
- **raffle-raptor-prod**: statusz, healthz, HTTP domain, VPN, snapshot, total-perf, Cloudflare
- **raffle-raptor-dev**: healthz, statusz, HTTP domain (both laxdog.uk and lax.dog), VPN, snapshot, total-perf, Cloudflare
- Notifications: prod enabled, dev enabled (re-enabled 2026-04-14)

## Known issues
- **overdue_count WARN on prod statusz** — RR agent investigating worker capacity. Homelab action: none until RR agent reports back.
- **502s on raffle-raptor-dev (2026-04-08)** — traced to planned maintenance restart (two full-estate stopall/startall cycles for SSD hardware install). Closed as known incident.
