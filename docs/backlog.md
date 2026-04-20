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

- [ ] AdGuard role: stop flushing rewrites on every run
  - Context: the adguard role renders `AdGuardHome.yaml` from a template that emits `rewrites: []`, restarts AdGuard, and then relies on downstream API tasks (`/control/rewrite/add`) to repopulate rewrites. If ANY task between the restart and the rewrite-add tasks fails (today: `/control/safesearch/status` returned 404 because that endpoint has drifted in current AdGuard versions), the play halts and ALL `*.laxdog.uk` rewrites are wiped in the interim. Today this broke DNS for all 31 internal hostnames for ~2 minutes until rewrites were restored by direct API calls. Fix: either have the template render the declared rewrites (with `enabled: true`) and skip the API-repopulate step, or make the rewrite-add tasks run BEFORE any task that could fail. Also fix the safesearch API call (404) — endpoint has moved in newer AdGuard releases.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-20

- [ ] CT172 apt: `docker-compose-plugin` vs `docker-compose-v2` file collision
  - Context: the docker-host role's canonical Docker apt source pulls `docker-compose-plugin` which owns `/usr/libexec/docker/cli-plugins/docker-compose`; Ubuntu's `docker-compose-v2` (already installed from Noble's repos) owns the same file. Ansible apply against CT172 today hit this and dpkg left `docker-ce` in `iU` (unpacked-not-configured) state, breaking `docker.service`. Recovered manually via `--force-overwrite` + `systemctl start docker.socket docker.service`. Current state is `--force-overwrite`d — the file belongs to `docker-compose-plugin` but both packages are `ii`. Next apt upgrade may re-trigger the conflict. Fix: remove `docker-compose-v2` from the image/install (role shouldn't rely on Ubuntu's version), OR remove `docker-compose-plugin` from the role's install list if Ubuntu's version is sufficient.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-20

- [x] CT163 Gluetun: `known eel` pinned to inactive server, egressing unexpectedly — RESOLVED 2026-04-20
  - Root cause: Mullvad API `active=false` means "no new registrations accepted", not "existing tunnels terminated". CT163's handshake with `gb-lon-wg-201` was established before the server went inactive, so the tunnel held. Would have failed on next Gluetun restart.
  - Resolved by: CT163 migrated to `gb-lon-wg-002` on 2026-04-20 (RR-driven).
  - Added: 2026-04-20, Completed: 2026-04-20

- [ ] Migrate `well raven` (prod VPS) Mullvad pin to Mullvad-owned server
  - Context: CT163 (`known eel`) migrated 2026-04-20 to `gb-lon-wg-002` (Mullvad-owned, provider `31173`) — per RR orchestrator report; egress now `141.98.252.239`. Prod VPS (`well raven`) still pinned to `gb-lon-wg-301` on M247 (rented). Migration target per RR is `gb-lon-wg-003`. Same pattern as CT163: RR updates Gluetun `SERVER_HOSTNAMES` in their compose, verifies replacement is `active=true` via Mullvad API, confirms new egress. Homelab updates `docs/vpn.md` egress map + device inventory once RR reports cutover.
  - Effort: low (one node, RR-driven)
  - Scope: homelab tracks state; RR drives the compose change
  - Added: 2026-04-20, CT163 half completed 2026-04-20

- [ ] Reconcile tailscale per-node prefs (`accept_dns`, `exit_node`, `advertise_exit_node`, `advertise_routes`) on non-router nodes
  - Context: the `tailscale-router` role renders a `tailscale-phase1-up` helper that bakes in declared `--advertise-*` and `--accept-dns` flags, but only runs once during operator bootstrap. Nothing in the repo reconciles runtime Tailscale state against `config/homelab.yaml` after that — if a node's runtime prefs drift (reboot, `tailscaled.state` reset, manual operator change), config and reality diverge silently. Guests without the `tailscale-router` role (e.g. CT173 `roles: [docker]`) ignore the config entirely.

    Two incidents so far:

    1. **CT173 DNS (2026-04-17)**: `accept_dns: false` declared in homelab.yaml, runtime was `accept_dns=true`, tailscaled took over `/etc/resolv.conf` and wrote an empty one (MagicDNS disabled tailnet-wide, no resolvers pushed) — DNS completely broken.
    2. **staging-home exit-node cutover (2026-04-20)**: no field exists in homelab.yaml to declare "this node CONSUMES VM171 as its exit node". The `tailscale set --exit-node=tailscale-gateway --exit-node-allow-lan-access=true` call was applied live only. If staging-home reboots and loses tailscaled prefs, the runtime setting silently reverts — staging-home's egress would fall back to bare NAT, violating the unique-egress-per-worker policy without warning.

    Scope the fix broadly enough to cover: inbound DNS handling (`--accept-dns`), exit-node consumption (`--exit-node`, `--exit-node-allow-lan-access`), exit-node advertising (`--advertise-exit-node`), subnet route advertising (`--advertise-routes`), and route acceptance (`--accept-routes`, noting the LAN-adjacency gotcha in AGENTS.md — some nodes MUST be `false`).

    Fix options: (a) idempotent `tailscale set` task in a baseline role that runs on every play, sourcing values from `config.services.{vms,lxcs}.<name>.tailscale` and `config.remote_nodes.nodes.<name>.tailscale`; extend the schema with an `exit_node` consumer field; or (b) document that these fields in homelab.yaml are aspirational for non-router nodes and surface the constraint at validation time. (a) is preferred — the config should be the source of truth.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-17, extended 2026-04-20 to cover exit-node consumption

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

- [x] Cut rr-worker-staging-home over to VM171 Mullvad exit — DONE 2026-04-20
  - Context: staging-home now egresses via VM171 → Mullvad UK (`141.98.252.208`). `--exit-node-allow-lan-access=true` keeps 10.20.30.0/24 reachable directly. Required flipping `advertise_exit_node: false` on staging-home (Tailscale rejects simultaneous advertise+consume). Unique-egress-per-worker policy now satisfied (CT173 holds 212.56.120.65 uniquely). Runtime exit-node setting NOT yet reconciled from repo — tied to existing backlog item on non-router tailscale settings reconciliation.
  - Added: 2026-04-20, Completed: 2026-04-20

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
