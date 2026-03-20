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
- `auth.lax.dog` -> Authentik
- `jellyfin.lax.dog` -> Jellyfin (native auth; no forward-auth)
- `nagios.lax.dog` -> Nagios (Authentik SSO + TOTP)
- `proxmox.lax.dog` -> Proxmox (native Proxmox login)
- `netalertx.lax.dog` -> NetAlertX (Authentik forward-auth)
- `ha.lax.dog` -> Home Assistant (Authentik forward-auth)
- `couchdb.lax.dog` -> CouchDB
- `raffle-raptor-dev.lax.dog` -> raffle-raptor-dev via NPM (`10.20.30.163:8081`)

Internal (`laxdog.uk`):
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
- `router.laxdog.uk`
- `unifi-primary.laxdog.uk`
- `unifi-secondary.laxdog.uk`
- `raffle-raptor-dev.laxdog.uk` -> raffle-raptor-dev via NPM (`10.20.30.163:8081`)

## Notes
- Media stack currently includes Jellyfin only; more services will be added.
- Jellyfin is exposed internally and externally without forward-auth to keep native apps working.
  Bootstrap is automated; see `docs/jellyfin.md`.
- NFS role currently runs on `media-stack` and remains a placeholder pending storage attachment strategy.
- Internal proxy hosts use HTTPS via Let's Encrypt (DNS-01) in NPM.
- `couchdb.lax.dog` is externally reachable for Obsidian LiveSync clients (CORS enabled for the Obsidian origin set).
- Authentik is active as IdP and forward-auth provider for selected admin endpoints.
- Proxmox OIDC login has been disabled; use local Proxmox realms (`pam`/`pve`).
- Home Assistant reverse-proxy trust (`use_x_forwarded_for` + `trusted_proxies`) is repo-managed from `config.home_assistant.http`.
- Home Assistant owner bootstrap is automated during onboarding with `config.home_assistant.*` and `home_assistant_admin_password`.
- AdGuard config export/import workflow is documented in `docs/adguard.md`.
- Proxmox tags/notes are managed by `scripts/proxmox_metadata.py` (see `docs/proxmox-metadata.md`).
- `raffle-raptor-dev` is marked `tun_required` and receives `/dev/net/tun` passthrough from Proxmox for Gluetun-based networking.
- `tailscale-gateway` is a dedicated VM used for remote LAN access via Tailscale:
  - advertises subnet route `10.20.30.0/24`
  - advertises exit-node capability for optional/on-demand client use
  - does not force DNS override on clients in phase 1
  - see `docs/tailscale.md` for manual join/approval/split-DNS steps
