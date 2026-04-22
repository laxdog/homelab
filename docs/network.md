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
- Last octet = VM/CT ID (e.g. CT167 = .167, VM122 = .122)
- Exception: CT153 (adguard) = .53 (DNS convention)
- All 20 guests have DHCP static reservations on the router
- For the full domain architecture (laxdog.uk vs lax.dog), see `AGENTS.md`

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

## External DNS (Cloudflare `lax.dog` zone)

Source of truth for record intent is Cloudflare; this doc captures the decisions behind what's exposed externally vs kept tailnet-only. Services moving to tailnet-only get their `lax.dog` record deleted and are reached via their `laxdog.uk` equivalent on the LAN or via Tailscale.

**Records that remain (9):**
| Record | Type | Proxy | Reason |
|---|---|---|---|
| `lax.dog` | A | proxied | Apex, target of the wildcard CNAME |
| `*.lax.dog` | CNAME | proxied | Wildcard → apex. Load-bearing: `cleanuparr`, `prowlarr`, `qbittorrent`, `radarr`, `sabnzbd`, `sonarr` all reach external via this. Removal backlogged (see below). |
| `auth.lax.dog` | A | proxied | Authentik outpost endpoint — must stay external, other external services forward-auth against it |
| `ha.lax.dog` | A | proxied | Home Assistant, externally accessible behind Authentik forward-auth (pending decision on Google Home integration / forward-auth exemption) |
| `jellyfin.lax.dog` | A | proxied | Still external pending LDAP bind fix + native-login cutover |
| `couchdb.lax.dog` | A | proxied | Obsidian CouchDB sync endpoint. Currently broken (see backlog) — record retained until that decision is made |
| `raffle-raptor.lax.dog` | A | **DNS-only** | Prod RR app, points direct to VPS `159.195.59.97` — not on home NAT |
| `raffle-raptor-dev.lax.dog` | A | proxied | Staging RR app on home infra |
| `_acme-challenge.lax.dog` | TXT | n/a | DNS-01 certbot token (Let's Encrypt) |

**Records deleted 2026-04-22** (services moved to tailnet/LAN-only):
| Record | Type | Replacement | Reason |
|---|---|---|---|
| `nagios.lax.dog` | A | `nagios.laxdog.uk` (internal NPM proxy, LAN/Tailscale only) | Monitoring UI doesn't need public exposure |
| `netalertx.lax.dog` | A | `netalertx.laxdog.uk` | LAN monitoring, same rationale |
| `proxmox.lax.dog` | A | `proxmox.laxdog.uk` | Hypervisor UI — LAN/Tailscale only, reduces attack surface |
| `stream.lax.dog` | A | none | Orphan left over from Plex retirement (2026-04-14). No NPM/AdGuard config referred to it. |

All four deletions were pre-flight-verified: AdGuard rewrite for the `laxdog.uk` equivalent in place, NPM internal proxy host serving on `10.20.30.154`, HTTP probe returned 200/302 from the internal path. `stream.lax.dog` was a pure orphan with no internal equivalent to verify.

**Wildcard removal — backlogged.** The 6 media-stack services (`cleanuparr`, `prowlarr`, `qbittorrent`, `radarr`, `sabnzbd`, `sonarr`) resolve externally only via `*.lax.dog` — there are no explicit CF records for them. Removing the wildcard breaks their external path. They'll be migrated off the wildcard (either tailnet-only or explicit records) in a follow-up; see `docs/backlog.md`.


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
