# Services

Source of truth: `config/homelab.yaml`.

## VMs
- media-stack (Docker)
- nfs-server
- home-assistant (HAOS)

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

## Host-level
- NUT server (UPS USB)

## NPM Hostnames
External (`lax.dog`):
- `dns.lax.dog` -> AdGuard UI (auth)
- `sites.lax.dog` -> static-sites (public)

Internal (`laxdog.uk`):
- `dns.laxdog.uk` -> AdGuard UI
- `npm.laxdog.uk` -> Nginx Proxy Manager UI
- `organizr.laxdog.uk`
- `heimdall.laxdog.uk`
- `rss.laxdog.uk`
- `netalertx.laxdog.uk`
- `health.laxdog.uk`
- `couchdb.laxdog.uk`
- `browser.laxdog.uk`
- `apt.laxdog.uk`
- `sites.laxdog.uk`

## Notes
- Media stack compose is a placeholder and needs service definitions added.
- NFS server role is a placeholder pending storage attachment strategy.
