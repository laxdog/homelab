# VPN & Mullvad Configuration

## Mullvad Account
- **Account**: 1935183178135569
- **Device limit**: 5
- **Credentials**: homelab vault as `mullvad_account` (partial — RR nodes use RR repo vault)

## Device Inventory

Keep this up to date whenever devices are added or removed.

| Mullvad Name | Node | WG Public Key (partial) | Server | Created |
|---|---|---|---|---|
| live panda | VM120 media-stack (Gluetun) | `cOcvD/tp...` | Mullvad France (unpinned) | 2026-03-22 |
| known eel | CT163 rr-application-staging-proxmox (Gluetun) | `eFY1vCT...` | Mullvad UK London (gb-lon-wg-002, Mullvad-owned) | 2026-02-26 |
| well raven | rr-application-prod-vps (Gluetun) | `WqjCL+V...` | Mullvad UK London (gb-lon-wg-003, Mullvad-owned — RR migration 2026-04-20, Phase 5 allowlist update pending) | 2026-02-26 |
| holy llama | Operator phone/laptop (Mullvad app direct, not via Gluetun) | `T+saClF...` | — | 2026-02-06 |
| normal koala | VM171 tailscale-gateway (wg-quick, role `mullvad-exit`) | `smCBm+S...` | Mullvad UK London (gb-lon-wg-001, pinned — Mullvad-owned) | 2026-04-20 |

**5/5 device slots used** — account is full. Must delete a device before registering a new WireGuard key.

**Mapping verified 2026-04-17** (live panda, known eel, well raven) and **2026-04-20** (normal koala) by deriving the X25519 public key from each node's WireGuard private key and matching against the Mullvad account. `holy llama` is the only device not tied to a homelab-managed node — presumed to be the operator's Mullvad app on phone or laptop connecting directly.

> **Caveat — RR-managed Gluetun config**: CT163 and prod VPS run their Gluetun containers from RR's compose (not this repo). The `Server` column here reflects what the RR orchestrator reports; homelab Ansible does not independently verify `SERVER_HOSTNAMES` or the peer pubkey on these nodes. Pin changes are driven by the RR orchestrator. CT163 migration to `gb-lon-wg-002` completed 2026-04-20; prod VPS migration to `gb-lon-wg-003` reported complete on RR's side 2026-04-20 with `VPN_EGRESS_IP_ALLOWLIST` update pending their Phase 5 follow-up — until that lands, the prod VPS Gluetun container may be running with a stale allowlist and failing egress-IP validation. Homelab will update the egress map snapshot once RR confirms Phase 5 complete.

## WireGuard Private Keys

Private keys are vaulted:
- **Homelab vault** (`ansible/secrets.yml`): `gluetun_wireguard_private_key` → VM120 media-stack Gluetun
- **Homelab vault** (`ansible/secrets.yml`): `mullvad_vm171_wg_private_key` → VM171 tailscale-gateway wg-quick (role `mullvad-exit`)
- **RR repo vault** (on CT163 and prod VPS): separate keys for known eel and well raven — managed by RR agent, not homelab

## Tailscale Exit Node (VM171)

VM171 (tailscale-gateway) at 10.20.30.171 / Tailscale 100.120.120.126 advertises:
- `10.20.30.0/24` — homelab LAN subnet route
- `0.0.0.0/0` + `::/0` — full exit node

VM171 itself has `CorpDNS: false` (`--accept-dns=false`) — it does not apply Tailscale DNS settings to its own resolver. It uses AdGuard (10.20.30.53) directly via eth0.

### Using VM171 as exit node

When using VM171 as exit node:
- All internet traffic routes through Mullvad UK London (`gb-lon-wg-001`, egress IP in `141.98.252.0/24` pool) — **not** the homelab public IP.
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
1. All traffic exits via Mullvad UK London (`gb-lon-wg-001`, egress in `141.98.252.0/24` pool) — VM171's own outbound plus all forwarded exit-node traffic.
2. All DNS goes to AdGuard (`10.20.30.53`) — ad blocking active, internal services accessible
3. `laxdog.uk` resolves via AdGuard rewrites, `lax.dog` via Cloudflare, everything else via Quad9/Cloudflare DoH

### VM171 Tailscale config note

VM171 has `accept_dns: false` (`CorpDNS: false`) — it ignores Tailscale-pushed DNS and uses the homelab network DNS (AdGuard) directly via eth0. This is correct behaviour for a subnet router/exit node.

### Adding Mullvad to VM171

**DONE 2026-04-20.** VM171 egresses via Mullvad UK London `gb-lon-wg-001` as Mullvad device `normal koala`.

- Ansible role: `ansible/roles/mullvad-exit/`
- Runbook: `docs/runbooks/add-mullvad-exit-node.md`
- Vault key: `mullvad_vm171_wg_private_key` in `ansible/secrets.yml`

Current behaviour:
- VM171's own outbound traffic → Mullvad (egress `141.98.252.208` observed 2026-04-20, in `141.98.252.0/24` SNAT pool).
- Forwarded Tailscale exit-node traffic → Mullvad (same pool).
- LAN subnet routing (Tailscale → `10.20.30.0/24`) → eth0, unchanged.
- Kill-switch iptables rules (chain `MULLVAD-EXIT-FWD`, installed by `mullvad-exit-killswitch.service` before `wg-quick@wg0`) drop forwarded traffic on eth0 if wg0 is down, preventing leak.

### Remote peer reachability (post-Mullvad)

Tailscale's `Self.Online: false` for VM171 post-Mullvad is **expected**, not a bug.

Root cause: VM171's NAT-discovered public IP moved from `212.56.120.65` (home router, UDP-hole-punchable) to `141.98.252.208` (Mullvad — strict NAT, blocks inbound UDP from arbitrary sources). UDP hole-punching no longer works for peers that don't share the LAN.

Functional impact:
- **LAN peers** (CT163, CT173, staging-home, VM133 nagios, CT172 observability, etc. at `10.20.30.x`): unaffected. Direct P2P still works via the LAN address — confirmed with `tailscale ping` showing `via 10.20.30.171:41641`.
- **Remote peers** (rr-worker-prod-mums, rr-application-prod-vps, operator phone/laptop): direct connection to VM171 no longer works. Fall back to Tailscale DERP relay (`DERP(lhr)`, 39–263 ms measured from mums). Tailscale rate-limits DERP to ~10 Mbps per connection.
- **No remote client uses VM171 as exit node today**, so there is no functional impact — DERP latency is paid only for direct tailnet control traffic to VM171, not bulk data. If a remote client were cut over to use VM171 as exit node, ~10 Mbps / 40–260 ms is the latency/bandwidth floor.

### Future: unblocking direct P2P if a remote client needs VM171 as exit node

If a remote Tailscale client (mums, prod VPS, operator phone) ever needs VM171 as its exit node, direct P2P won't work due to strict Mullvad NAT. Options:

1. **Port-forward UDP 41641 → `10.20.30.171` on the home router.** Preferred fix. Re-enables NAT traversal from outside via the home router's stable public IP. Low effort (ASUS NVRAM edit), no runtime cost. Tracked in backlog.
2. **Accept DERP relay.** Works today, no config change needed. Adds 40–260 ms per hop and is rate-limited to ~10 Mbps by Tailscale. Fine for control traffic and low-bandwidth workloads; not suitable for bulk data.

LAN clients (CT163, CT173, staging-home, etc.) are unaffected either way — they always direct-connect via `10.20.30.x`.

## Egress IP Map (all nodes)

| Node | Egress IP | Method | Notes |
|---|---|---|---|
| VM120 media-stack | 193.32.126.214 | Mullvad FR (unpinned) | arr stack downloads |
| VM171 tailscale-gateway | 141.98.252.208 | Mullvad UK London (gb-lon-wg-001, **pinned**) | Host egress + Tailscale exit-node forwarded traffic. Snapshot 2026-04-20; SNAT pool so egress IP can shift within 141.98.252.0/24. |
| rr-application-staging-proxmox (CT163) | 141.98.252.239 | Mullvad UK London via Gluetun (gb-lon-wg-002, Mullvad-owned, **pinned**) | RR staging scraper. Migrated off `gb-lon-wg-201` (xtom, inactive) on 2026-04-20 — RR-reported. SNAT pool so egress IP can shift within `141.98.252.0/24`. |
| rr-application-prod-vps | *pending* | Mullvad UK London (gb-lon-wg-003, Mullvad-owned, **pinned** — RR migration 2026-04-20) | RR prod scraper. RR updated `SERVER_HOSTNAMES` 2026-04-20; `VPN_EGRESS_IP_ALLOWLIST` update pending RR Phase 5 follow-up. Current egress not confirmed by homelab — do not fingerprint. Pre-migration snapshot was `146.70.119.78` (gb-lon-wg-301 M247). |
| rr-worker-staging-home | 141.98.252.208 | Mullvad UK London via VM171 (Tailscale exit node) | Cut over 2026-04-20. `--exit-node-allow-lan-access=true` keeps LAN-direct paths (CT163 DB proxy, AdGuard, NPM). SNAT pool — snapshot IP. |
| rr-worker-prod-proxmox (CT173) | 212.56.120.65 | Bare NAT | Operator home static IP (unique — staging-home moved to Mullvad via VM171 on 2026-04-20) |
| rr-worker-prod-mums | 109.155.65.157 | Bare NAT | mum's residential IP (unique) |
| rr-application-prod-vps (host) | 159.195.59.97 | Direct VPS IP | SSH, Tailscale, HTTPS |
| Operator home | 212.56.120.65 | ISP static | — |
| Mum's house | 109.155.65.157 | ISP dynamic (BT/EE) | May change |

## Egress Policy

- **Every RR worker gets a unique egress IP. No sharing.**
- **Prod workers**: bare NAT, no VPN.
- **Staging workers**: VPN, unique exit IP per worker. `rr-worker-staging-home` egresses via VM171 tailscale-gateway → Mullvad UK London (cut over 2026-04-20).
- **App nodes**: Mullvad via Gluetun. IPs rotate within Mullvad UK because `SERVER_HOSTNAMES` is unpinned — **documented IPs are snapshots, not stable identifiers**.

## Notes

- VM120 Gluetun is unpinned (Mullvad France, no `SERVER_HOSTNAMES`) — consider pinning to prevent exit IP rotation
- VM120 media-stack egress rotates within Mullvad FR because its Gluetun is unpinned (no `SERVER_HOSTNAMES`). CT163 (`gb-lon-wg-002`) and prod VPS (`gb-lon-wg-301`) are both pinned — no server rotation expected, subject to Mullvad's SNAT behaviour documented below. Do not build allow-lists against VM120 egress without pinning first.
- **Mullvad egress NAT model — partially known, partially assumed.**
  - Ingress endpoint (`ipv4_addr_in` from the Mullvad API) and external egress are *different IPs within the same /24* on Mullvad-owned servers.
  - VM171 (gb-lon-wg-001): ingress `141.98.252.130`, egress `141.98.252.208`.
  - CT163 (gb-lon-wg-002): ingress `141.98.252.222`, egress `141.98.252.239` (RR-reported, 2026-04-20).
  - Prod VPS (gb-lon-wg-003): ingress per Mullvad API is `185.195.232.66`; egress TBD — RR Phase 5 allowlist update pending before the container can confirm egress.
  - Three migrations tracked; two with confirmed egress, one pending. The `141.98.252.0/24` assumption is being re-examined given gb-lon-wg-003's ingress sits in `185.195.232.0/24` (Mullvad-owned subnet block spans multiple /24s — server ingress and egress pools may not share a /24 across all 001..008).
  - Egress appears **stable per-session**: VM171 held `141.98.252.208` across 3+ days and one kill-switch bounce. Behaviour across `wg-quick` restart or key rotation is not tested.
  - **RR has moved to /24 CIDR allowlist matching** on their Gluetun `VPN_EGRESS_IP_ALLOWLIST` (in line with the safer-than-single-IP recommendation below) — pending Phase 5.
  - If single-IP pinning of egress becomes load-bearing anywhere, verify the guarantee with Mullvad support. For allow-lists, **/24 granularity is safer** than pinning a single egress IP.
- Mullvad device inventory should be audited whenever a device is added or removed
- **Never exceed 5 devices** — check this doc before registering a new WireGuard key
