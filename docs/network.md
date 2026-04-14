# Network

Source of truth: `config/homelab.yaml`.

## Subnet
- 10.20.30.0/24
- Gateway: 10.20.30.1
- Proxmox host: 10.20.30.46 (vmbr0)

## Router
- Model: ASUS RT-AC86U (Asuswrt-Merlin 3.0.0.4.386)
- SSH: `ssh admin@10.20.30.1` (key-based, uses `~/.ssh/id_rsa`)
- DHCP static reservations: `nvram get dhcp_staticlist` / `nvram set dhcp_staticlist=...` then `nvram commit` and `service restart_dnsmasq`
- Format: `<MAC>IP>>` entries concatenated, e.g. `<A0:9A:8E:35:E5:02>10.20.30.83>>`

## Reserved
- AdGuard/DNS: 10.20.30.53
- Authentik: 10.20.30.170
- Home Assistant: 10.20.30.122
- Nagios: 10.20.30.133
- Router: 10.20.30.1
- UniFi links: 10.20.30.50, 10.20.30.51

## Guest IPs
- 10.20.30.100-199 reserved for Proxmox guests
- CTID=IP convention where possible

## DHCP
- 10.20.30.200-249
- LAN clients must use `10.20.30.53` as primary DNS.
- Root-cause note: if router DHCP hands out both `10.20.30.53` and `10.20.30.1`, clients may choose either and bypass internal rewrites.
- Preferred fix: DHCP option 6 should advertise only `10.20.30.53`.
- Safety fallback: router DNS (`10.20.30.1`) should forward LAN DNS queries to AdGuard (`10.20.30.53`).
- Optional enforcement: set `config.validation.require_router_dns_consistency: true` to make validate fail when router DNS does not match AdGuard rewrites.

## Domains
- External: `lax.dog` (Cloudflare)
- Internal: `laxdog.uk` (AdGuard rewrites -> NPM)

## Remote Access (Phase 1)
- Tailscale subnet router/exit node VM: `tailscale-gateway` (`10.20.30.171`).
- Advertised subnet route: `10.20.30.0/24`.
- Exit node is available for optional/on-demand client use.
- DNS design for phase 1 is split DNS only:
  - configure in Tailscale admin: `laxdog.uk` -> `10.20.30.53` (AdGuard).
  - do not force all DNS through AdGuard in phase 1.
- See `docs/tailscale.md` for operational steps.

## Legacy/temporary
- Old servarr: 10.20.30.74
- Old NAS: 10.20.30.151
- Old server: 10.20.30.155
