# Observability Stack

**Status: DEPLOYED** (2026-04-15)

## Deployment

- **Guest**: CT172 on ssd-mirror (20GB, 2 cores, 2GB RAM)
- **OS**: Ubuntu 24.04
- **IP**: 10.20.30.172
- **Stack**: Prometheus + Grafana + json-exporter in Docker Compose
- **Grafana URL**: https://grafana.laxdog.uk (valid LE cert via DNS-01)
- **Prometheus URL**: https://prometheus.laxdog.uk (valid LE cert via DNS-01)
- **Config in repo**: `config/observability/`

## Prometheus

- Scrape interval: 15s
- Retention: 1 year (`--storage.tsdb.retention.time=1y`)
- Storage: on LXC rootfs (ssd-mirror), included in daily vzdump backup automatically
- Config lives in repo: `ansible/roles/observability/` or `config/prometheus/`

## Grafana

- Deployed alongside Prometheus in the same LXC via Docker Compose
- Auth: Grafana native (no Authentik integration for now — internal tool)
- Access: `grafana.laxdog.uk` via NPM (LAN / Tailscale only, no Cloudflare proxy)
- Admin credentials: vaulted in `ansible/secrets.yml` as `grafana_admin_password`
- Port: 3000

## Scrape targets (Phase 2)

| Target | Endpoint | Transport |
|---|---|---|
| raffle-raptor prod | `https://raffle-raptor.lax.dog/statusz` | Public HTTPS (prod is NOT on the Tailnet) |
| raffle-raptor staging | `https://raffle-raptor-dev.lax.dog/statusz` or direct via Tailscale | Tailscale (rr-node-staging-local at 100.88.35.124) |
| Future targets | Additive — no redesign needed | — |

### RR /statusz shape (as of 2026-04-14)
Both prod and dev expose a rich JSON payload at `/statusz`:
- Runtime: `git_sha`, `app_version`, `build_time_utc`
- Disk: `disk_total_bytes`, `disk_used_bytes`, `disk_free_bytes`, `disk_used_pct`
- App: `app_env`, `alerts_enabled`, `selected_webhook_target`
- Parse state: `active_parse_total_count`, `active_parse_issue_count`, per-field OK counts
- Signal eligibility: per-signal-type candidates, alerts, suppressions
- Worker: `worker_running`, `success_rate_5m`, `overdue_count`, `p95_ms`
- Snapshots: `oldest_active_snapshot_age_sec`

This will need a `/metrics` Prometheus exporter or a JSON-to-Prometheus adapter. Options:
1. RR ships a native `/metrics` endpoint (cleanest)
2. Use `json_exporter` to scrape `/statusz` and map fields
3. Custom exporter script on CT172

## Auth / access

| Hostname | Backend | Purpose |
|---|---|---|
| `grafana.laxdog.uk` | CT172:3000 | Grafana dashboards (internal only) |
| `prometheus.laxdog.uk` | CT172:9090 | Prometheus UI (internal debugging only) |

Both via NPM with AdGuard rewrites. No external Cloudflare exposure — these are internal operational tools.

## Backup

Daily vzdump to tank-backups (same schedule as all guests — 04:30, zstd, 14-day retention). Prometheus data is on the LXC rootfs so it's included automatically.

## Repo structure

```
ansible/roles/observability/
  tasks/main.yml
  templates/
    docker-compose.yml.j2
    prometheus.yml.j2
config/homelab.yaml  (observability: block with scrape targets)
```

Docker compose committed to repo and deployed via Ansible (follows source-of-truth principle).

## Nagios integration

Existing Nagios checks for RR (`check_raffle_raptor.py`) continue to provide alerting. Prometheus/Grafana adds trending, historical analysis, and dashboards — it does NOT replace Nagios for alerting.

## What this is NOT

- Not RR-specific — other scrape jobs (node_exporter on Proxmox host, AdGuard stats, etc.) will be added as targets grow
- No dashboards until RR ships `docs/statusz_contract.md` defining the stable metrics interface
- Not a replacement for Nagios alerting — complementary trending/visualisation layer

## Log Aggregation (Loki)

### Components
- **Loki**: log storage and query engine (added to CT172 docker-compose)
- **Promtail**: log shipping agent (deployed via Ansible to all guests and remote nodes)
- **Grafana**: already running, Loki added as a data source

### Deployment
- Loki added to CT172 `config/observability/docker-compose.yml`
- Promtail deployed via Ansible role: `ansible/roles/promtail/`
- Config driven from `config/homelab.yaml`

### Promtail deployment model
**Option A — Promtail on every guest** (chosen). Rationale:
- VM120 Docker JSON logs require local socket access (`docker_sd_configs`)
- Remote nodes (Tailscale-only) can only ship logs from a local agent
- Granular per-host labels with clean separation
- Ansible role makes deployment consistent across all host types

### Log sources

| Source | Count | Log format | Transport |
|---|---|---|---|
| LXCs (Ubuntu 24.04) | 15 | journald + syslog | Promtail binary → Loki HTTP push |
| VMs (Ubuntu) | 3 (120, 133, 171) | journald + syslog | Promtail binary → Loki HTTP push |
| VM122 (HAOS) | 1 | N/A (excluded — HAOS has no package manager) | — |
| VM120 Docker containers | ~12 | JSON Docker logs | Promtail docker_sd_configs on VM120 |
| CT172 Docker containers | 4 | JSON Docker logs | Promtail docker_sd_configs on CT172 |
| Proxmox host (PVE) | 1 | journald + syslog | Promtail binary → Loki HTTP push |
| rr-node-staging-local | 1 | journald + syslog | Promtail binary → Loki via Tailscale |
| rr-node-prod-mums | 1 | journald + syslog | Promtail binary → Loki via Tailscale |

### Retention
- **Period**: 90 days (`limits_config.retention_period: 90d`)
- **Estimated volume**: ~50–100 MB/day compressed across all sources → ~4.5–9 GB for 90 days
- **Storage**: Loki data volume on CT172 rootfs (ssd-mirror), included in daily vzdump backup
- CT172 has 18 GB free disk — comfortable headroom

### Repo structure
```
config/observability/loki.yml           — Loki server config
config/observability/promtail.yml       — Base Promtail config (reference)
config/observability/docker-compose.yml — Updated with Loki service
ansible/roles/promtail/
  tasks/main.yml                        — Install binary, deploy config, enable service
  templates/promtail.yml.j2             — Host-specific config (journald + optional docker)
  handlers/main.yml                     — Restart handler
```

## Phase plan

| Phase | Scope | Depends on |
|---|---|---|
| **1 (this doc)** | Design and CT ID reservation | — |
| **2** | Deploy CT172 with Prometheus + Grafana | User approval |
| **3** | Add RR scrape targets | RR `/metrics` or json_exporter config |
| **4** | Build Grafana dashboards | RR `statusz_contract.md` |
| **5** | Add infrastructure targets (node_exporter, etc.) | Phase 2 complete |
| **6** | Log aggregation — Loki on CT172, Promtail on all guests | Phase 2 complete |
