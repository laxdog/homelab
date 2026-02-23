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
- python-bot
- organizr
- heimdall
- authentik

## Host-level
- NUT server (UPS USB)

## NPM Hostnames
External (`lax.dog`):
- External access is enabled behind Authentik.
- `auth.lax.dog` -> Authentik
- `jellyfin.lax.dog` -> Jellyfin (native auth; no forward-auth)
- `nagios.lax.dog` -> Nagios (basic auth)
- `proxmox.lax.dog` -> Proxmox (basic auth)

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

## Notes
- Media stack currently includes Jellyfin only; more services will be added.
- Jellyfin is exposed internally and externally without forward-auth to keep native apps working.
  Bootstrap is automated; see `docs/jellyfin.md`.
- NFS server role is a placeholder pending storage attachment strategy.
- Internal proxy hosts use HTTPS via Let's Encrypt (DNS-01) in NPM.
- Authentik will be added as the IdP for external access and OIDC for supported apps.
- Home Assistant may return HTTP 400 behind NPM until `trusted_proxies` is configured in HAOS.
- AdGuard config export/import workflow is documented in `docs/adguard.md`.
