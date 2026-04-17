# VPN & Mullvad Configuration

## Mullvad Account
- **Account**: 1935183178135569
- **Device limit**: 5
- **Credentials**: homelab vault as `mullvad_account` (partial — RR nodes use RR repo vault)

## Device Inventory

Keep this up to date whenever devices are added or removed.

| Mullvad Name | Node | WG Public Key (partial) | Server | Created |
|---|---|---|---|---|
| live panda | VM120 media-stack | `cOcvD/tp...` | Mullvad France (unpinned) | 2026-03-22 |
| known eel | CT163 rr-application-staging-proxmox | `eFY1vCT...` | Mullvad UK London (gb-lon-wg-201) | 2026-02-26 |
| well raven | rr-application-prod-vps | `WqjCL+V...` | Mullvad UK London (gb-lon-wg-301) | 2026-02-26 |
| holy llama | Operator phone | `T+saClF...` | — | 2026-02-06 |
| stable bunny | UNKNOWN — candidate for deletion | `v9eaJAJ...` | — | 2026-02-06 |

**5/5 device slots used.** Must delete a device before registering a new key.

## WireGuard Private Keys

Private keys are vaulted:
- **Homelab vault** (`ansible/secrets.yml`): `gluetun_wireguard_private_key` → VM120 media-stack Gluetun
- **RR repo vault** (on CT163 and prod VPS): separate keys for known eel and well raven — managed by RR agent, not homelab

## Tailscale Exit Node (VM171)

VM171 (tailscale-gateway) at 10.20.30.171 / Tailscale 100.120.120.126 advertises:
- `10.20.30.0/24` — homelab LAN subnet route
- `0.0.0.0/0` + `::/0` — full exit node

VM171 itself has `CorpDNS: false` (`--accept-dns=false`) — it does not apply Tailscale DNS settings to its own resolver. It uses AdGuard (10.20.30.53) directly via eth0.

### Using VM171 as exit node on phone

When using VM171 as exit node:
- All internet traffic routes through homelab public IP (212.56.120.65)
- All DNS goes to AdGuard (10.20.30.53) — ad blocking active, internal services accessible
- MagicDNS is disabled on this tailnet — Tailscale node names cannot be resolved via DNS (use Tailscale IPs instead)

### DNS configuration

Global nameserver: `10.20.30.53` (AdGuard, CT153)
- All Tailscale client DNS goes to AdGuard
- `UseWithExitNode: true` — works when using VM171 as exit node
- `laxdog.uk` resolves via AdGuard rewrites (internal services)
- `lax.dog` resolves via AdGuard → Cloudflare (external services)
- Everything else via AdGuard → Quad9/Cloudflare DoH upstream
- Ad blocking active on all Tailscale clients when connected

Previous split DNS rule (`laxdog.uk → 10.20.30.53`) has been removed — redundant now that AdGuard is the global nameserver.

**MagicDNS**: disabled (`MagicDNSEnabled: false`)
- Tailscale node hostnames are not resolvable by DNS
- Use Tailscale IPs directly, or enable MagicDNS in the admin console if needed

### Phone exit node behaviour (VM171)

When using VM171 as Tailscale exit node:
1. All traffic exits via `212.56.120.65` (homelab public IP, or Mullvad IP once VM171 is configured with Mullvad)
2. All DNS goes to AdGuard (`10.20.30.53`) — ad blocking active, internal services accessible
3. `laxdog.uk` resolves via AdGuard rewrites, `lax.dog` via Cloudflare, everything else via Quad9/Cloudflare DoH

### VM171 Tailscale config note

VM171 has `accept_dns: false` (`CorpDNS: false`) — it ignores Tailscale-pushed DNS and uses the homelab network DNS (AdGuard) directly via eth0. This is correct behaviour for a subnet router/exit node.

### Adding Mullvad to VM171

Placeholder — to be completed once a device slot is freed.

Steps:
1. Delete `stable bunny` from Mullvad account (confirm it's safe first)
2. Generate new WireGuard keypair for VM171
3. Register public key in Mullvad account
4. Install Gluetun or `wg-quick` on VM171
5. VM171 becomes a Mullvad exit node
6. Tailscale clients using VM171 as exit node get Mullvad egress instead of homelab public IP
7. Update this doc with the new device name and key

## Egress IP Map (all nodes)

| Node | Egress IP | Method | Notes |
|---|---|---|---|
| VM120 media-stack | 193.32.126.214 | Mullvad FR (unpinned) | arr stack downloads |
| rr-application-staging-proxmox (CT163) | 185.248.85.16 | Mullvad UK (unpinned — rotates) | RR staging scraper. Snapshot 2026-04-17. |
| rr-application-prod-vps | 146.70.119.78 | Mullvad UK (unpinned — rotates) | RR prod scraper. Snapshot 2026-04-17. |
| rr-worker-staging-home | 212.56.120.65 | Bare NAT (deviation) | Target: VPN with unique IP via VM171 → Mullvad exit (see deviation note below) |
| rr-worker-prod-proxmox (CT173) | 212.56.120.65 | Bare NAT | Currently shares IP with rr-worker-staging-home — resolves when staging-home moves to VPN |
| rr-worker-prod-mums | 109.155.65.157 | Bare NAT | mum's residential IP (unique) |
| rr-application-prod-vps (host) | 159.195.59.97 | Direct VPS IP | SSH, Tailscale, HTTPS |
| Operator home | 212.56.120.65 | ISP static | — |
| Mum's house | 109.155.65.157 | ISP dynamic (BT/EE) | May change |

## Egress Policy

- **Every RR worker gets a unique egress IP. No sharing.**
- **Prod workers**: bare NAT, no VPN.
- **Staging workers**: VPN, unique exit IP per worker. `rr-worker-staging-home` will egress via VM171 tailscale-gateway → Mullvad exit (backlogged).
- **App nodes**: Mullvad via Gluetun. IPs rotate within Mullvad UK because `SERVER_HOSTNAMES` is unpinned — **documented IPs are snapshots, not stable identifiers**.

## Notes

- VM120 Gluetun is unpinned (Mullvad France, no `SERVER_HOSTNAMES`) — consider pinning to prevent exit IP rotation
- App-node egress IPs (CT163, prod VPS) rotate within Mullvad UK because Gluetun is unpinned (no `SERVER_HOSTNAMES`). Expect rotation after every Gluetun restart or key rotation. Do not build allow-lists or fingerprint rules against these IPs without pinning first.
- **Known deviation**: `rr-worker-staging-home` and `rr-worker-prod-proxmox` (CT173) both egress via `212.56.120.65`, violating the unique-egress-per-worker policy. Resolves when staging-home moves to VPN via VM171 Mullvad exit — see `docs/backlog.md` item "Configure VM171 as Mullvad exit node".
- Mullvad device inventory should be audited whenever a device is added or removed
- **Never exceed 5 devices** — check this doc before registering a new WireGuard key
