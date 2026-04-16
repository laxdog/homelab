# Changelog

Significant infrastructure changes by date. Agents should add entries here for major changes.

## 2026-04-14
- VM122 HA migrated from 10.20.30.134 to 10.20.30.122 (IP convention fix)
- All 19 guests migrated from NVMe/tank to SSD (ssd-fast + ssd-mirror pools)
- Plex retired — NPM proxy hosts, AdGuard rewrites, Nagios checks, Authentik app all removed
- AdGuard: optimistic caching enabled, Cloudflare DoH added as fallback upstream
- AdGuard: charlotte-mbp and nvidia-shield persistent clients (MAC-based matching)
- Remote nodes: battery management (TLP on X270), powertop, chrony, WiFi sync, Nagios monitoring
- Nagios: remote-node checks deployed (PING, SSH, Disk, Tailscale, CPU temp, NTP for both nodes)
- Tailscale installed on VM133 (nagios-vm133) for monitoring remote nodes
- AdGuard role: dns_config management (cache_optimistic, upstream_dns, resolve_clients, local_ptr)
- AdGuard role: flush_handlers fix for destructive template render bug
- AGENTS.md structure created with per-agent docs, runbooks, changelog
- Router (ASUS RT-AC86U) access documented in config and network docs
- docs/backlog.md created with 15 items across all scopes
- DHCP static reservations added for all 19 guests on the router
- OPNsense migration added to backlog (future)

## 2026-04-15
- CT172 (observability) deployed — Prometheus + Grafana + json-exporter
- RR statusz scraping: prod + staging, 30s interval, 35 metrics per env
- 5 Grafana dashboards provisioned: Worker Health, Phase Timing, Playwright Fallback, Parse & Issues, Infra Health
- grafana.laxdog.uk + prometheus.laxdog.uk NPM + AdGuard routes
- json-exporter: removed deprecated rr_queue_depth, renamed p95_total_duration → p95_scrape_duration, added playwright latency metrics
- Heimdall: Grafana + Prometheus icon slug mappings
- Cert 17 renewed with grafana + prometheus SANs via certbot --expand DNS-01 (Cloudflare API). Valid LE cert, no -k needed.
- Incorrect Cloudflare A records for grafana/prometheus removed (laxdog.uk is internal-only, no CF records)
- Loki 2.9.10 deployed on CT172 for log aggregation (90-day retention)
- Promtail Ansible role created and deployed to 20 hosts (15 LXCs, 3 VMs, PVE host, raptor-node-staging)
- CT172 RAM bumped from 1GB to 2GB for Loki headroom
- Loki added as Grafana datasource (provisioned)
- loki.laxdog.uk NPM proxy host + AdGuard rewrite added
- VM133 (Nagios) SSH unreachable — added to backlog
- raffle-raptor-prod VPS (159.195.59.97) joined to Tailnet as 100.82.170.21
- Promtail deployed to prod VPS with RR app log scraping (/var/log/raffle-raptor/*.log)
- Nagios checks for prod VPS: PING, SSH, Disk, Tailscale, NTP via Tailscale IP
- SSH hardened on prod VPS: UFW restricts port 22 to operator home, mum's house, Tailscale only
- Domain architecture documented in AGENTS.md (laxdog.uk internal vs lax.dog external, DNS-01 cert model)
- Full docs consistency pass: storage.md rewritten, 8 other docs updated for post-migration accuracy

## 2026-04-08
- SSD hardware: 3 SATA SSDs installed (Kingston 894G + 2x ORICO 477G)
- SSDs moved from SAS2004 HBA to onboard Intel SATA controller (TRIM now working)
- ssd-fast and ssd-mirror ZFS pools created and registered as Proxmox storage
- ATA Secure Erase recovered both ORICO drives from degraded performance
- Overnight audit: Nagios alert root cause (Plex 401 + RR-dev 502), full estate health check
- AdGuard: amplitude.com unblocked for client 10.20.30.83 (charlotte-mbp)

## 2026-04-07
- CT167 jellyfin-hw created (privileged LXC with iGPU passthrough for hardware transcoding)
- Jellyfin ingress cut over from VM120 to CT167 (NPM, AdGuard, Nagios updated)
- CT154 (NPM) moved to tank-vmdata, CT170 (Authentik) moved to tank-vmdata

## 2026-03-28
- Bazarr internal routing added (AdGuard rewrite, NPM proxy host, Heimdall entry)
- Bazarr SQLAlchemy patch applied (now resolved upstream)
- log-policy role deployed to all LXCs
- Cloudflare DNS: 28 *.laxdog.uk A records added

## 2026-03-22
- Remote-node baseline deployed to raptor-node-staging
- WiFi hardening, healthcheck timer, failsafe reboot policy
- Tailscale router role added for remote nodes
- 5 Grafana dashboards provisioned: Worker Health, Phase Timing, Playwright Fallback, Parse & Issues, Infra Health
- grafana.laxdog.uk and prometheus.laxdog.uk NPM + AdGuard routes
