# Services

Source of truth: `config/homelab.yaml`.

## VMs
- media-stack (Docker)
- nfs-server
- home-assistant (HAOS)
- nagios

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

## Notes
- Media stack currently includes Jellyfin only; more services will be added.
- Jellyfin is exposed internally and externally without forward-auth to keep native apps working.
  Bootstrap is automated; see `docs/jellyfin.md`.
- NFS server role is a placeholder pending storage attachment strategy.
- Internal proxy hosts use HTTPS via Let's Encrypt (DNS-01) in NPM.
- Authentik is active as IdP and forward-auth provider for selected admin endpoints.
- Proxmox OIDC login has been disabled; use local Proxmox realms (`pam`/`pve`).
- Home Assistant may return HTTP 400 behind NPM until `trusted_proxies` is configured in HAOS.
- AdGuard config export/import workflow is documented in `docs/adguard.md`.
- Proxmox tags/notes are managed by `scripts/proxmox_metadata.py` (see `docs/proxmox-metadata.md`).
- `raffle-raptor-dev` is marked `tun_required` and receives `/dev/net/tun` passthrough from Proxmox for Gluetun-based networking.
