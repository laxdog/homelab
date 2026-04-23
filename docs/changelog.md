# Changelog

Significant infrastructure changes by date. Agents should add entries here for major changes.

## 2026-04-23
- Home Assistant endpoint truth re-verified live: `http://10.20.30.122:8123` returned HTTP 200, while the old `10.20.30.134` address failed with `No route to host`. Current HA docs/config were already aligned to VM122, so no IP correction was needed beyond preserving that evidence.
- Home Assistant heating dashboard config now includes the new living-room Sonoff ambient sensor (`sensor.ewelink_snzb_02p_temperature` + `sensor.ewelink_snzb_02p_humidity`) as a repo-managed overview card rendered alongside the relevant downstairs TRV data (`climate.dining_area`, `climate.front_window`). No heating-control semantics changed.

## 2026-04-22
- Authentik/Jellyfin LDAP follow-up completed for CT167 pilot login. Root cause of the Authentik bind failure was provider wiring: the LDAP outpost was reading its bind flow from `authorization_flow`, while the repo had been setting the intended bind flow on `authentication_flow`. Updated the Authentik setup template so the Jellyfin LDAP provider now sets `authorization_flow` to `default-authentication-flow`, and the managed bind user path is repaired to `users` during apply. CT167 LDAP bind/search now succeeds against CT170.
- CT167 Jellyfin LDAP pilot login now works end-to-end for a non-admin pilot user. Root cause of the remaining Jellyfin-side failure was plugin config drift: the role had been managing `Jellyfin.Plugin.LDAP_Auth.xml` while the live plugin was reading `LDAP-Auth.xml`, and the managed XML also serialized `LdapProfileImageFormat` as `0`, which caused the plugin to fall back to its built-in sample config (`CN=BindUser,DC=contoso,DC=com`). Updated repo config to manage `LDAP-Auth.xml` and serialize `LdapProfileImageFormat` as `Default`. Re-applied the narrow CT167 role, validated local `admin` still works, and validated a pilot LDAP-backed Jellyfin login for `ldapservice` (non-admin, `AuthenticationProviderId=Jellyfin.Plugin.LDAP_Auth.LdapAuthenticationProviderPlugin`). `cjess` remains local and untouched. Ingress unchanged: `jellyfin.lax.dog` still has Authentik forward-auth and needs a later cutover pass to avoid auth stacking.
- Authentik/Jellyfin LDAP groundwork added for CT167 central-auth prep. Repo now manages an Authentik LDAP application/provider/outpost on CT170 plus CT167 Jellyfin LDAP plugin/config deployment. Runtime verification: LDAP outpost container is healthy on CT170, Jellyfin LDAP plugin is loaded on CT167, and local Jellyfin `admin` remains usable as break-glass. Remaining blocker: LDAP bind/search from CT167 to Authentik still returns `Invalid credentials (49)`, so pilot LDAP login is not yet ready. Ingress unchanged: `jellyfin.lax.dog` is still behind Authentik forward-auth and needs a later cutover pass once LDAP bind is fixed.
- CT172 `docker-compose-plugin` vs `docker-compose-v2` apt collision resolved (carried over from the 2026-04-20 incident). Root cause traced via `/var/log/apt/history.log`: on 2026-04-14 someone ran `apt-get install -y docker.io docker-compose-v2` on CT172, installing Ubuntu's native docker stack alongside the Docker CE stack the `docker-host` role maintains. Fleet check confirmed CT172 was the only affected host (14 other docker hosts clean). Purged `docker-compose-v2`, `docker.io`, `containerd` on CT172; `docker.io`'s postrm tried to invoke `/var/lib/docker/nuke-graph-directory.sh` which would have wiped docker-ce's data directory — the LXC's block-device restriction blocked the umount, which incidentally saved the containers. Neutralised the nuke script (moved to `/root/nuke-graph-directory.sh.disabled-20260422`) and completed the purge cleanly. All 4 observability containers (loki, grafana, prometheus, json-exporter) stayed up throughout. `docker compose version` → v5.1.3.
- `docker-host` role hardened with an "ensure absent" task for Ubuntu-native docker packages (`docker.io`, `docker-compose-v2`, `containerd`) — cheap insurance against repeat manual installs re-introducing the file collision.

## 2026-04-20 (later)
- `loki.laxdog.uk` drift reconciled. Root cause: declared in `config/homelab.yaml` five days earlier (commit `d644d90`) but Ansible apply hadn't fully run against adguard + NPM since. Full apply today revealed three role bugs that all contributed:
  1. **NPM update task payload** (fixed, commit `9e2e0f5`): `locations: null` from NPM's API tripped `| default([])` and caused a 400 on Update, which halted the loop and blocked the Create task — meaning no new proxy hosts (Loki) got created, and existing grafana/prometheus updates also failed.
  2. **AdGuard role flushes rewrites on every run**: the template renders `rewrites: []` (loop over `config.adguard.rewrites` somehow produces empty) then restarts AdGuard, relying on subsequent API `/control/rewrite/add` tasks to repopulate. Today the `/control/safesearch/status` task 404d (API endpoint drift in AdGuard) and halted the play before the rewrite-add tasks ran — ALL 31 `*.laxdog.uk` rewrites were wiped for ~2 minutes until I restored them via direct API calls. High-risk pattern; filed to backlog.
  3. **CT172 apt conflict**: `docker-compose-plugin` tried to install and collided with `docker-compose-v2` over `/usr/libexec/docker/cli-plugins/docker-compose`. dpkg left docker-ce in `iU` state, docker.service failed to start, all observability containers went down. Recovered by `--force-overwrite` + `systemctl start docker.socket docker.service`, then `docker start` on the stopped containers. Filed to backlog.
- Loki end-state: `https://loki.laxdog.uk/ready` returns 200 "ready"; cert 22 (new LE cert auto-created by NPM role with loki in SAN list) is in use on proxy host 64.conf; AdGuard rewrite present; backend healthy.
- Grafana + Prometheus unchanged and still serving.

## 2026-04-20
- VM171 (tailscale-gateway) now egresses via Mullvad. Device `normal koala` on `gb-lon-wg-001` (Mullvad-owned, pinned). Role `mullvad-exit` deployed via Ansible: `wg-quick@wg0` up, iptables FORWARD kill-switch (`MULLVAD-EXIT-FWD` chain, installed by `mullvad-exit-killswitch.service` ordered `Before=wg-quick`) blocks eth0 leak path. VM171 own egress + forwarded Tailscale exit-node traffic now routes through Mullvad UK (`141.98.252.0/24` pool). Mullvad slot count 5/5.
- Tailnet / wg-quick coexistence bug found and fixed: wg-quick's pri-5209 policy rule catches de-NAT'd reply packets destined for tailnet CGNAT and loops them back via wg0. Fix: pri-5200 rule sending `100.64.0.0/10` and `fd7a:115c:a1e0::/48` to Tailscale's table 52, installed via wg0.conf PostUp/PreDown in the role.
- Mullvad server `gb-lon-wg-201` (known eel's pin) confirmed inactive via API. CT163 Gluetun is silently failing over somewhere in the xtom subnet — investigation + migration to Mullvad-owned servers filed as backlog items.
- Verified new Mullvad mapping: VM171's derived public key matches `normal koala` in Mullvad account. Device inventory 5/5, verification note dated 2026-04-20.
- Known post-Mullvad tradeoff documented in vpn.md: `Self.Online: false` expected (strict Mullvad NAT breaks UDP hole-punching for remote peers). LAN peers unaffected; remote peers fall back to DERP (40-260 ms, ~10 Mbps cap). No remote client uses VM171 as exit node today. Port-forward UDP 41641 on home router filed as backlog for future need.
- rr-worker-staging-home cut over to VM171 as Tailscale exit node. Runtime: `tailscale set --advertise-exit-node=false --exit-node=tailscale-gateway --exit-node-allow-lan-access=true`. Staging-home now egresses via Mullvad UK (`141.98.252.208`) instead of home NAT (`212.56.120.65`). Verified: CT163:5432, LAN (AdGuard, NPM) all reachable; Nagios checks still green. `advertise_exit_node` flipped to `false` in homelab.yaml (Tailscale forbids simultaneous advertise+consume). CT173 now holds `212.56.120.65` uniquely — unique-egress-per-worker policy satisfied.

## 2026-04-17
- CT173 DNS fix: `tailscale set --accept-dns=false` + restored `/etc/resolv.conf` to PVE-standard `nameserver 10.20.30.53`. Root cause: runbook Step 8 `tailscale up` was missing `--accept-dns=false`, tailscaled took over resolv.conf and wrote it empty (tailnet has MagicDNS disabled, no resolvers pushed to this node). Two durability gaps filed in `docs/backlog.md` — the primary fix is reconciling `accept_dns` at the config layer for non-router nodes.
- RR worker egress policy tightened in `docs/vpn.md` and `docs/runbooks/add-rr-worker-node.md`: every worker gets a unique egress IP (no sharing). Prod = bare NAT, staging = VPN. staging-home/CT173 shared 212.56.120.65 flagged as a known deviation pending VM171 Mullvad exit deployment. App-node Mullvad IPs documented as rotating snapshots, not stable.

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
- Renamed remote nodes to role-based naming convention: raptor-node-staging → rr-node-staging-local, mums-house-mbp → rr-node-prod-mums, raffle-raptor-prod → rr-node-prod-vps
- CT173 (rr-worker-prod-proxmox) created — 2 cores, 2GB RAM, 16GB on ssd-mirror, Docker, Tailscale (100.104.174.2), Promtail, Nagios checks
- remote-node-baseline WiFi tasks extracted to include_tasks with wifi_enabled conditional — headless LXCs can now skip WiFi management
- Second rename pass to rr-type-env-location convention: raffle-raptor-dev → rr-application-staging-proxmox, rr-node-prod-vps → rr-application-prod-vps, rr-node-staging-local → rr-worker-staging-home, rr-node-prod-mums → rr-worker-prod-mums
- docs/vpn.md created: Mullvad device inventory (5 devices mapped), egress IP map, Tailscale exit node + split DNS docs
- docs/runbooks/add-rr-worker-node.md created: full provisioning runbook for new RR worker LXCs
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
