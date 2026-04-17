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
- Split DNS ensures `*.laxdog.uk` resolves via AdGuard (10.20.30.53) — internal services remain accessible
- Non-`laxdog.uk` DNS queries go to the phone's own DNS (carrier/ISP or configured resolver like Cloudflare)
- MagicDNS is disabled on this tailnet — Tailscale node names cannot be resolved via DNS (use Tailscale IPs instead)

### Split DNS config

Configured in the Tailscale admin console:
- **Domain**: `laxdog.uk`
- **Nameserver**: `10.20.30.53` (AdGuard, CT153)
- **UseWithExitNode**: `true` — `laxdog.uk` resolves via AdGuard even when using VM171 as exit node

**MagicDNS**: disabled (`MagicDNSEnabled: false`)
- Tailscale node hostnames are not resolvable by DNS
- Use Tailscale IPs directly, or enable MagicDNS in the admin console if needed

**Global DNS override**: not configured
- Non-`laxdog.uk` queries use the phone's own DNS
- To enable AdGuard ad blocking on the phone, add `10.20.30.53` as a global nameserver in the Tailscale admin console

Verified working on VM133 (nagios): `resolvectl` shows `tailscale0` handling `~laxdog.uk` via `10.20.30.53`.

### Phone exit node behaviour (VM171)

When using VM171 as Tailscale exit node:
1. All traffic exits via `212.56.120.65` (homelab public IP, or Mullvad IP once VM171 is configured with Mullvad)
2. `laxdog.uk` queries go to AdGuard (`10.20.30.53`) — internal services accessible
3. Other DNS goes to the phone's carrier/ISP DNS (or AdGuard if global override is enabled)

### VM171 Tailscale config note

VM171 has `accept_dns: false` (`CorpDNS: false`) — it ignores Tailscale-pushed DNS and uses the homelab network DNS (AdGuard) directly via eth0. This is correct behaviour for a subnet router/exit node.

### Optional enhancements

- Enable MagicDNS in Tailscale admin console for hostname resolution on the phone
- Add `10.20.30.53` as global Tailscale DNS for ad blocking on the phone when on the exit node

Both are low risk and can be done at any time via the Tailscale admin console — no homelab agent action needed.

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
| rr-application-staging-proxmox (CT163) | 185.195.232.169 | Mullvad UK London | RR staging scraper |
| rr-application-prod-vps | 185.248.85.55 | Mullvad UK London | RR prod scraper |
| rr-worker-staging-home | 212.56.120.65 | Bare NAT | Intentional — operator home |
| rr-worker-prod-proxmox (CT173) | 212.56.120.65 | Bare NAT | Intentional — shares operator home NAT |
| rr-worker-prod-mums | 109.155.65.157 | Bare NAT | Intentional — mum's residential IP |
| rr-application-prod-vps (host) | 159.195.59.97 | Direct VPS IP | SSH, Tailscale, HTTPS |
| Operator home | 212.56.120.65 | ISP static | — |
| Mum's house | 109.155.65.157 | ISP dynamic (BT/EE) | May change |

## Notes

- VM120 Gluetun is unpinned (Mullvad France, no `SERVER_HOSTNAMES`) — consider pinning to prevent exit IP rotation
- rr-worker-staging-home and rr-worker-prod-proxmox share egress IP 212.56.120.65 — acceptable per RR for worker nodes (they don't scrape directly)
- Mullvad device inventory should be audited whenever a device is added or removed
- **Never exceed 5 devices** — check this doc before registering a new WireGuard key
- Egress IPs for Gluetun nodes may change after container restart if server is not pinned
