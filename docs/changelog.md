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
