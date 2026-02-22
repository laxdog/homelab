# Network

Source of truth: `config/homelab.yaml`.

## Subnet
- 10.20.30.0/24
- Gateway: 10.20.30.1
- Proxmox host: 10.20.30.46 (vmbr0)

## Reserved
- AdGuard/DNS: 10.20.30.153 (temporary; .53 already in use)
- Authentik: 10.20.30.170

## Guest IPs
- 10.20.30.100-199 reserved for Proxmox guests
- CTID=IP convention where possible

## DHCP
- 10.20.30.200-249

## Domains
- External: `lax.dog` (Cloudflare)
- Internal: `laxdog.uk` (AdGuard rewrites -> NPM)

## Legacy/temporary
- Old servarr: 10.20.30.74
- Old NAS: 10.20.30.151
- Old server: 10.20.30.155
