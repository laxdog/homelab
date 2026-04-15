# Services

Source of truth: `config/homelab.yaml`.

## VMs
- media-stack (Docker + NFS role)
- home-assistant (HAOS)
- nagios
- tailscale-gateway (Tailscale subnet router + exit node)

## LXCs
- adguard
- nginx-proxy-manager
- couchdb
- apt-cacher-ng
- freshrss
- netalertx
- healthchecks
- dashboard
- static-sites
- browser
- raffle-raptor-dev
- organizr
- heimdall
- authentik

## Host-level
- NUT server (UPS USB)

## NPM Hostnames
External (`lax.dog`):
- External access is enabled behind Authentik for admin services.
- `lax.dog` -> Heimdall (Authentik-protected root landing page)
- `auth.lax.dog` -> Authentik
- `jellyfin.lax.dog` -> Jellyfin (native auth; no forward-auth)
- `nagios.lax.dog` -> Nagios (Authentik SSO + TOTP)
- `proxmox.lax.dog` -> Proxmox (native Proxmox login)
- `netalertx.lax.dog` -> NetAlertX (Authentik forward-auth)
- `ha.lax.dog` -> Home Assistant (Authentik forward-auth)
- `couchdb.lax.dog` -> CouchDB
- `raffle-raptor-dev.lax.dog` -> raffle-raptor-dev via NPM (`10.20.30.163:8081`)

Internal (`laxdog.uk`):
- `laxdog.uk` -> Heimdall (internal root landing page)
- `dns.laxdog.uk` -> AdGuard UI
- `npm.laxdog.uk` -> Nginx Proxy Manager UI
- `proxmox.laxdog.uk` -> Proxmox UI
- `organizr.laxdog.uk`
- `heimdall.laxdog.uk`
- `rss.laxdog.uk`
- `netalertx.laxdog.uk`
- `health.laxdog.uk`
- `couchdb.laxdog.uk`
- `browser.laxdog.uk`
- `apt.laxdog.uk`
- `sites.laxdog.uk`
- `auth.laxdog.uk`
- `ha.laxdog.uk`
- `nagios.laxdog.uk`
- `jellyfin.laxdog.uk`
- `plex.laxdog.uk`
- `prowlarr.laxdog.uk`
- `sonarr.laxdog.uk`
- `radarr.laxdog.uk`
- `cleanuparr.laxdog.uk`
- `sabnzbd.laxdog.uk`
- `qbittorrent.laxdog.uk`
- `router.laxdog.uk`
- `unifi-primary.laxdog.uk`
- `unifi-secondary.laxdog.uk`
- `raffle-raptor-dev.laxdog.uk` -> raffle-raptor-dev via NPM (`10.20.30.163:8081`)

## Notes
- Media stack day-1 app layout is repo-managed under `/opt/media-stack`.
- Compose projects are split into `core` (Plex, Jellyfin), `arr` (Prowlarr, Sonarr, Radarr, Cleanuparr), and `downloaders` (Gluetun, SABnzbd, qBittorrent).
- Jellyfin is exposed internally and externally without forward-auth to keep native apps working.
  Bootstrap is automated; see `docs/jellyfin.md`.
- Media-stack internal UI routes are internal-only (`laxdog.uk`) and terminate at NPM:
  - `jellyfin.laxdog.uk` -> `10.20.30.167:8097` (CT167 jellyfin-hw, hardware transcoding)
  - `prowlarr.laxdog.uk` -> `10.20.30.120:9696`
  - `sonarr.laxdog.uk` -> `10.20.30.120:8989`
  - `radarr.laxdog.uk` -> `10.20.30.120:7878`
  - `cleanuparr.laxdog.uk` -> `10.20.30.120:11011`
  - `sabnzbd.laxdog.uk` -> `10.20.30.120:6789`
  - `qbittorrent.laxdog.uk` -> `10.20.30.120:8080`
- Dashboard entries in both Organizr and Heimdall are generated from `config.npm.proxy_hosts`; adding a proxy host entry automatically adds a dashboard link.
- Heimdall can also include non-NPM links via `config.heimdall.extra_items` (for example `Raffle Raptor Prod` at `https://raffle-raptor.lax.dog`).
- `media-stack` now provides a real internal NFS baseline:
  - export path: `/srv/data`
  - allowed CIDR: `10.20.30.0/24`
  - bulk data mounted from a ZFS-backed Proxmox data disk (not root disk)
- Intel Quick Sync preparation for `media-stack` is infra-managed:
  - Proxmox host exposes Intel iGPU to VM `120` (`hostpci0`)
  - guest checks verify `/dev/dri/renderD128` for later Docker media containers
- Internal proxy hosts use HTTPS via Let's Encrypt (DNS-01) in NPM.
- `couchdb.lax.dog` is externally reachable for Obsidian LiveSync clients (CORS enabled for the Obsidian origin set).
- Authentik is active as IdP and forward-auth provider for selected admin endpoints.
- Proxmox OIDC login has been disabled; use local Proxmox realms (`pam`/`pve`).
- Home Assistant reverse-proxy trust (`use_x_forwarded_for` + `trusted_proxies`) is repo-managed from `config.home_assistant.http`.
- Home Assistant owner bootstrap is automated during onboarding with `config.home_assistant.*` and `home_assistant_admin_password`.
- AdGuard config export/import workflow is documented in `docs/adguard.md`.
- Proxmox tags/notes are managed by `scripts/proxmox_metadata.py` (see `docs/proxmox-metadata.md`).
- `raffle-raptor-dev` is marked `tun_required` and receives `/dev/net/tun` passthrough from Proxmox for Gluetun-based networking.
- `raffle-raptor-dev` exposes a staging-only Postgres discovery path over Tailscale for `raptor-node-staging`:
  - endpoint: `100.92.43.108:5432` (Tailscale IP only)
  - source restriction: `100.88.35.124/32` only
  - DB user: `rr_discovery_staging` (read-only discovery role)
  - password source-of-truth: `ansible/secrets-rr-staging.yml` (`rr_discovery_staging_db_password`, vaulted)
  - current staging worker bootstrap copy: `/etc/raffle-raptor/remote-discovery-db.env` on `raptor-node-staging`
  - managed by Ansible role `rr-staging-db-access` (runtime units + firewall + pg_hba + role grants)
- `tailscale-gateway` is a dedicated VM used for remote LAN access via Tailscale:
  - advertises subnet route `10.20.30.0/24`
  - advertises exit-node capability for optional/on-demand client use
  - does not force DNS override on clients in phase 1
  - see `docs/tailscale.md` for manual join/approval/split-DNS steps
- Apt-cacher remediation status (`2026-03-28`): all Debian/Ubuntu LXCs on Proxmox `10.20.30.46` are configured with `Acquire::http::Proxy "http://10.20.30.156:3142/"` and `Acquire::https::Proxy "http://10.20.30.156:3142/"`; `apt-cacher-ng` itself remains intentionally excluded.
