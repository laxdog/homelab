# Homelab Backlog

Homelab agent scope only. Per-agent backlogs live in `docs/agents/<name>.md`.

## Format
- [ ] Short description
  - Context: why this matters
  - Effort: low/medium/high
  - Added: date

---

## High Priority

- [ ] T420 eBay listing — finalise and publish
  - Context: memtester result pending, HBA card text to read physically, condition section needed, root password reset, iDRAC factory reset before shipping
  - Effort: low
  - Added: 2026-04-14

## Medium Priority

- [ ] CT163 Gluetun: `known eel` pinned to inactive server, egressing unexpectedly
  - Context: `known eel` device (CT163) is registered against `gb-lon-wg-201` per `docs/vpn.md`, but the Mullvad API (checked 2026-04-20 via `https://api.mullvad.net/www/relays/wireguard/`) shows that server is currently `active: false`. CT163 Gluetun is still egressing from the `185.248.85.0/24` subnet (e.g. `185.248.85.16` observed on 2026-04-17) — which is the xtom-provider range the inactive `gb-lon-wg-201/202` sit in. Gluetun appears to be auto-failing over to another xtom server (203 or 204) or the provider is doing opaque NAT, but our pinning intent is violated. Investigate by running `docker exec raffle-raptor-gluetun-1 wg show` to see the actual handshake peer, compare against the `SERVER_HOSTNAMES` env (or whatever pinning config RR uses), and determine why Gluetun isn't failing hard on an inactive pin.
  - Effort: low (investigation)
  - Scope: homelab (RR coordination may be required if Gluetun env lives in RR's compose)
  - Added: 2026-04-20

- [ ] Migrate `known eel` (CT163) and `well raven` (prod VPS) Mullvad pins to Mullvad-owned servers
  - Context: both currently pinned to rented providers — `known eel` on xtom (`gb-lon-wg-201`, inactive), `well raven` on M247 (`gb-lon-wg-301`). Mullvad-owned servers (`gb-lon-wg-001` through `gb-lon-wg-008`, provider `31173`, `owned=true`) are a stronger trust signal. VM171 Mullvad exit is being set up on `gb-lon-wg-001` — standardise the rest of the fleet on the same Mullvad-owned pool. Resolves the "egressing from inactive subnet" mystery above as a side effect. Scope: update Gluetun `SERVER_HOSTNAMES` (or equivalent pinning) on each node, verify replacement servers are `active=true` via the Mullvad API before pinning, then update `docs/vpn.md` Device Inventory. Since the Gluetun config for CT163 and prod VPS lives in RR's compose (not this repo), RR orchestrator needs to drive the change.
  - Effort: medium (two nodes, cross-repo coordination)
  - Scope: homelab (RR drives the compose change)
  - Added: 2026-04-20

- [ ] Reconcile tailscale `accept_dns` (and other per-node settings) on non-router nodes
  - Context: `remote_nodes.nodes.<name>.tailscale.accept_dns` and `services.{vms,lxcs}.<name>.tailscale.accept_dns` are only wired into a `tailscale up` helper by the `tailscale_router` role. Guests without that role (e.g. CT173 rr-worker-prod-proxmox, `roles: [docker]`) silently ignore the declared value — nothing reconciles runtime Tailscale state against config. CT173 hit this on 2026-04-17: declared `accept_dns: false`, runtime was enabled, tailscaled took over `/etc/resolv.conf` and wrote it empty (MagicDNS disabled tailnet-wide, no resolvers pushed), breaking all DNS. Fix options: (a) extend enforcement to all tailscale-joined guests via an idempotent `tailscale set --accept-dns=...` task in a baseline role; or (b) explicitly document that `accept_dns` in `config/homelab.yaml` is `tailscale_router`-role-only, and surface the constraint at config validation time. (a) is preferred — the config is the source of truth. The runbook fix (separate item below) is a workaround for this.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-17

- [ ] Runbook add-rr-worker-node.md Step 8 missing `--accept-dns=false`
  - Context: the hardcoded `tailscale up --hostname=... --accept-routes=false` in Step 8 omits `--accept-dns=false`. New workers default to accept-dns=true, tailscaled takes over `/etc/resolv.conf`, and because MagicDNS is disabled tailnet-wide the result is an empty resolv.conf (DNS broken). Every new worker provisioned from this runbook hits this. Workaround-grade fix; the real fix is reconciling `accept_dns` at the config layer (item above).
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-17

- [ ] NPM upstream healthcheck on restart
  - Context: NPM proxies to backends before they are ready after full estate restart, causing brief 502s. Options: nginx upstream health config, NPM startup delay, or replace NPM with Caddy/Traefik.
  - Effort: medium
  - Added: 2026-04-14

- [ ] Offsite backups
  - Context: all backups on tank pool on the same physical host as live data. Single point of failure. Tailscale in place for transport. Tier 1 guests (HA, RR, Authentik, CouchDB) should be replicated off-host first.
  - Effort: high
  - Added: 2026-04-14

- [x] Terraform plan as end-of-session check — DONE: documented in AGENTS.md end-of-session checklist
  - Added: 2026-04-14, Completed: 2026-04-15

- [ ] check_raffle_raptor.py not in repo
  - Context: Nagios check plugin on VM133 was deployed directly. Should be in repo under ansible/roles/nagios or similar.
  - Effort: low
  - Added: 2026-04-14

- [ ] ssd-fast Kingston — no redundancy
  - Context: Kingston 894GB solo pool hosts CT153, CT163, CT170. Daily backups to tank exist but disk failure means downtime until restore. Consider adding a mirror partner.
  - Effort: medium
  - Added: 2026-04-14

- [ ] Investigate VM133 (Nagios) SSH unreachable
  - Context: Promtail deployment failed because SSH to 10.20.30.133 is unreachable. Nagios checks work via Tailscale (100.120.89.28) but direct LAN SSH is failing. Investigate why and fix so Promtail can be deployed and VM133 logs flow into Loki.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-15

- [ ] Verify mum's house external IP for prod VPS SSH firewall
  - Context: 109.155.65.157 is a residential BT/EE dynamic IP. If it changes, SSH from mum's house to the prod VPS will break. Periodically verify the IP matches the firewall rule. Long-term fix is Tailscale-only SSH which eliminates this entirely.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-15

- [ ] Investigate Tailscale native Mullvad integration as alternative to VM171 Mullvad exit node setup
  - Context: Tailscale has a beta native Mullvad integration that lets you use Mullvad exit nodes directly in the Tailscale client without consuming a Mullvad device slot or running Gluetun on VM171. Worth evaluating once stable. Current plan (VM171 + Gluetun) is on hold pending a free Mullvad device slot.
  - Effort: low (investigation only)
  - Scope: homelab
  - Added: 2026-04-17

- [x] Configure VM171 as Mullvad exit node — DONE 2026-04-20
  - Context: VM171 is a Tailscale exit node; Mullvad WireGuard now routes its own and forwarded exit-node traffic via Mullvad. Mullvad device `normal koala` on `gb-lon-wg-001` (Mullvad-owned, pinned). Role `mullvad-exit`, runbook `docs/runbooks/add-mullvad-exit-node.md`. Verification: wg0 up, egress `141.98.252.208`, kill-switch blocks leak when wg0 down.
  - Added: 2026-04-17, Completed: 2026-04-20

- [ ] Cut rr-worker-staging-home over to VM171 Mullvad exit
  - Context: VM171 is ready (2026-04-20). Cutover is a separate deferred decision. Applying gives staging-home unique Mullvad egress (`141.98.252.0/24` pool) and closes the known-deviation shared `212.56.120.65` with CT173 (CT173 stays bare-NAT and becomes unique once staging-home moves off). LAN path to CT163 postgres must be preserved — use `tailscale set --exit-node=100.120.120.126 --exit-node-allow-lan-access=true` to keep 10.20.30.0/24 reachable directly. Remote staging-home users unaffected (staging-home is on LAN, direct P2P to VM171 via `10.20.30.171` is unaffected by Mullvad NAT).
  - Effort: low (tailscale set on staging-home + verify DB proxy still reachable)
  - Scope: homelab
  - Added: 2026-04-20

- [ ] Port-forward UDP 41641 to VM171 if a remote Tailscale client needs it as exit node
  - Context: VM171's Mullvad egress uses strict NAT → remote tailnet peers (mums, prod VPS, operator phone) can't direct-connect to VM171 for exit-node forwarding; fall back to DERP relay (40-260 ms, ~10 Mbps cap). Not needed today — no remote client uses VM171 as exit node, staging-home (the one planned consumer) is on LAN. If that changes, port-forward UDP 41641 on the home router (external → `10.20.30.171`) to restore NAT traversal. See `docs/vpn.md` §"Future: unblocking direct P2P".
  - Effort: low (ASUS NVRAM dhcp_staticlist / port-forward entry)
  - Scope: homelab
  - Added: 2026-04-20

- [x] Create rr-worker-prod-proxmox — DONE: CT173 created, Tailscale 100.104.174.2, Nagios + Promtail deployed
  - Context: future prod worker node on Proxmox. Will be a new LXC running RR worker only, connecting to rr-application-prod-vps DB via Tailscale. RR agent has this in their backlog too.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-15

## Low Priority

- [ ] Stale WiFi profiles on rr-worker-prod-mums
  - Context: 4 profiles with GNOME keyring passwords (EE-R2F2CJ, Castlewood Guest WiFi, theinternet, VM0513311) — inaccessible and dead weight.
  - Effort: low
  - Added: 2026-04-14

- [ ] AdGuard DNS plugin timeout tuning
  - Context: Nagios DNS checks show intermittent SOFT timeouts (>5s). Bumping plugin timeout (-t) would silence log churn.
  - Effort: low
  - Added: 2026-04-14

- [ ] NPM stale cert cleanup
  - Context: ~15 superseded LE cert IDs (2-16) in NPM DB. Can be deleted via API.
  - Effort: low
  - Added: 2026-04-14

- [ ] adguard.lax.dog decision
  - Context: removed from NPM as broken. dns.laxdog.uk works. Decision pending on external AdGuard access.
  - Effort: low
  - Added: 2026-04-14

- [ ] SAS3008 TRIM documentation
  - Context: SSDs moved to onboard Intel SATA. SAS3008 TRIM passthrough never tested. Worth documenting for future reference.
  - Effort: low
  - Added: 2026-04-14

- [ ] Audit Heimdall entries
  - Context: verify all services have entries and all entries point at correct URLs. Some services may have been added or retired without Heimdall being updated. Grafana/Prometheus were just added but a full audit is needed.
  - Effort: low
  - Added: 2026-04-14

## Future

- [ ] Migrate to OPNsense
  - Context: current router is stock ASUS RT-AC86U. DHCP reservations are MAC-only (no hostname support on stock firmware). OPNsense will provide proper named DHCP, better VLAN support, and cleaner integration with the homelab. Guest SSIDs were causing issues with Merlin so stock firmware is being used in the interim.
  - Effort: high
  - Added: 2026-04-14
