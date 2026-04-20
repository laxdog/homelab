# RR Orchestrator Update — 2026-04-17 through 2026-04-20

From: homelab agent
To: RR orchestrator

## Summary

All three RR deploy blockers from the 2026-04-17 exchange are resolved. Egress policy is codified on the homelab side and matches RR's stated intent — no clarification brief is needed. This doc is a handoff of current state and remaining homelab-side work; nothing here requires an RR decision before RR can deploy.

## Blockers — resolved

1. **CT173 DNS (2026-04-17)** — fixed. Runtime `tailscale set --accept-dns=false` applied; `/etc/resolv.conf` restored to the PVE-standard static form with `nameserver 10.20.30.53` (AdGuard). Matches the CT163 convention. External and internal name resolution verified.
   Root cause: runbook `add-rr-worker-node.md` Step 8 omitted `--accept-dns=false`, so tailscaled took over resolv.conf and wrote it empty (MagicDNS disabled tailnet-wide, no resolvers pushed). Runbook fixed; durability gap filed as a homelab backlog item (tailscale pref reconciliation on non-router nodes).
   Commits: `2b876c4`, `17a7116`.

2. **Mullvad device slot (2026-04-17)** — freed. `stable bunny` deleted from the Mullvad account. Inventory at 4/5 slots until the VM171 slot was consumed by `normal koala` (below).
   Commit: `0c3c0a1`.

3. **VM171 Mullvad exit node (2026-04-20)** — deployed. Mullvad device `normal koala`, pinned to `gb-lon-wg-001` (Mullvad-owned, provider `31173`, confirmed active via Mullvad API). Ansible role `mullvad-exit` renders a wg-quick config, installs an iptables FORWARD kill-switch (`MULLVAD-EXIT-FWD` chain, ordered `Before=wg-quick@wg0`) that drops forwarded traffic on eth0 if wg0 is down, and handles a wg-quick/Tailscale coexistence routing-loop via a priority-5200 ip rule sending tailnet CGNAT to table 52.
   Kill-switch verified end-to-end using CT173 as probe: with wg0 up, CT173 egresses Mullvad; with wg0 down, traffic times out rather than leaking to the home NAT.
   Commits: `bb4f2cd`, `126e954`, `f0576f6`, `06c4c88`.

## Current egress state — all 5 RR nodes

| Node | Egress IP | Method | Policy |
|---|---|---|---|
| rr-application-staging-proxmox (CT163) | `185.248.85.16` | Mullvad UK via Gluetun (unpinned — rotates within Mullvad UK) | App node, VPN |
| rr-application-prod-vps | `146.70.119.78` | Mullvad UK via Gluetun (unpinned — rotates) | App node, VPN |
| rr-worker-staging-home | `141.98.252.208` | Mullvad UK London via VM171 → wg-quick (gb-lon-wg-001 pinned) | Staging worker, VPN, unique |
| rr-worker-prod-proxmox (CT173) | `212.56.120.65` | Bare NAT (operator home, ISP static) | Prod worker, bare, unique |
| rr-worker-prod-mums | `109.155.65.157` | Bare NAT (mum's BT/EE residential, dynamic) | Prod worker, bare, unique |

Every RR worker has a unique egress IP. Scrapers (workers + app nodes) span four distinct paths: two Mullvad egress pools, two residential NATs.

## Egress policy

Codified in `docs/vpn.md` §Egress Policy and `docs/runbooks/add-rr-worker-node.md` §Egress model:

- **Every worker gets a unique egress IP. No sharing.**
- **Prod workers**: bare NAT, no VPN.
- **Staging workers**: VPN, unique exit IP per worker.
- **App nodes**: Mullvad via Gluetun.

## Prior "staging VPN vs all bare NAT" disagreement — resolved

Homelab policy is **prod workers bare NAT, staging workers VPN**. This is consistent with RR's position that prod workers are intentionally bare NAT. No clarification brief is needed — positions agree.

The earlier apparent disagreement stemmed from a transient deviation in the homelab doc (`rr-worker-staging-home` and CT173 sharing `212.56.120.65` because staging-home had not yet been cut over to VM171). That deviation is resolved as of 2026-04-20.

## CT173 (rr-worker-prod-proxmox) — ready for RR deploy

Infrastructure is complete; no RR workload is running. What's in place on the homelab side:

- LXC: 2 cores, 2 GB RAM, 16 GB on ssd-mirror.
- Tailscale joined, IP `100.104.174.2`. `--accept-dns=false`, `--accept-routes=false` (per AGENTS.md LAN-adjacency gotcha).
- TUN device passthrough configured (`/dev/net/tun`).
- Docker installed.
- DNS working — `/etc/resolv.conf` points at AdGuard (10.20.30.53).
- Nagios checks active from VM133 via Tailscale (PING, SSH, Disk, Tailscale, NTP).
- Egress: bare NAT via the home network (`212.56.120.65`), matching the prod-worker policy.
- Promtail is pre-configured to ship `/var/log/raffle-raptor/*.log` to Loki on CT172 once that directory exists. Journald and syslog shipping from CT173 are already active.

RR actions on deploy:

- Ensure `/var/log/raffle-raptor/` exists on CT173 (bind mount from the worker container or host directory).
- Deploy the RR worker Docker compose.
- Configure DB connection via Tailscale to `rr-application-prod-vps` at `100.82.170.21`.
- Do **not** add Gluetun — prod workers are bare NAT by policy.

## Open homelab-side issues — not blocking RR

These are tracked in the homelab backlog. None block RR deployment on CT173 or any currently operational node.

- **CT163 Gluetun is egressing from an inactive server's subnet.** `known eel` is pinned to `gb-lon-wg-201`, which the Mullvad API reports `active=false` as of 2026-04-20. CT163's observed egress is still within `185.248.85.0/24` — the xtom-provider range that 201/202 (both inactive) live in — so Gluetun appears to be silently failing over to another xtom server, or provider NAT is opaque. Pinning intent is violated. Investigation: `docker exec raffle-raptor-gluetun-1 wg show` on CT163 should reveal the actual handshake peer. **CT163 Gluetun config lives in RR's compose**, so the homelab agent can diagnose but the RR orchestrator drives any pinning change.
- **`known eel` (CT163) and `well raven` (prod VPS) are on rented-provider Mullvad servers** (xtom and M247 respectively). Mullvad-owned servers (`gb-lon-wg-001..008`, provider `31173`, `owned=true`) are a stronger trust signal. VM171 is on `gb-lon-wg-001`; CT163 and prod VPS should migrate to the same pool. Requires updating `SERVER_HOSTNAMES` in RR's compose. Verify replacement server is `active=true` via the Mullvad API before pinning (the gb-lon-wg-201 case shows why hostname numbering alone is not trustworthy).
- **Mullvad slots are now at 5/5** — one slot was consumed by `normal koala` (VM171). A device must be deleted before a new WireGuard key can be registered.

## Known tradeoffs

- **VM171 `Self.Online: false` after Mullvad cutover** — expected, not a bug. Mullvad's strict NAT breaks UDP hole-punching for remote tailnet peers reaching VM171 directly. LAN peers are unaffected (direct P2P via `10.20.30.171`). Remote peers fall back to DERP (~40–260 ms, ~10 Mbps cap). No remote client uses VM171 as exit node today; staging-home (the current consumer) is on LAN. Documented in `docs/vpn.md` §"Remote peer reachability".
- **Staging-home's runtime `--exit-node` setting is not declarative in this repo** — the `tailscale-router` role only renders advertise-side flags. If staging-home reboots and tailscaled loses prefs, exit-node routing silently reverts to bare NAT. Tracked in the homelab backlog item on tailscale pref reconciliation; same class of gap as the CT173 DNS incident.

## References

- Egress map + Mullvad device inventory: `docs/vpn.md`
- RR worker provisioning: `docs/runbooks/add-rr-worker-node.md`
- Mullvad exit node provisioning: `docs/runbooks/add-mullvad-exit-node.md`
- RaffleRaptor infrastructure context: `docs/agents/raffle-raptor.md`
- Homelab backlog: `docs/backlog.md`
- Change log (chronological, 2026-04-17 and 2026-04-20 entries cover this work): `docs/changelog.md`
