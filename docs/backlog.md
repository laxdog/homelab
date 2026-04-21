# Homelab Backlog

Homelab agent scope only. Per-agent backlogs live in `docs/agents/<name>.md`.

## Format
- [ ] Short description
  - Context: why this matters
  - Effort: low/medium/high
  - Added: date

---

## High Priority

_(none currently)_

## Medium Priority

- [ ] Prod VPS hardening — LAN blast radius review
  - Context: prod VPS is on the public internet and, as of 2026-04-21, has `accept_routes: true` to use VM171's `10.20.30.0/24` subnet route (needed for Promtail to reach Loki at `10.20.30.172:3100`). Consequence: if the VPS is compromised, the attacker can reach every LAN host via Tailscale. Previously the VPS only had direct peer access to tailnet-joined nodes.
  - Scope:
    - UFW/iptables on prod VPS: restrict outbound to the subnet-routed /24 to only the IPs/ports it actually needs (CT172:3100 for Loki, plus anything else justified — audit usage).
    - Review exposed services on the VPS (SSH, Docker, public-facing app, any inbound Tailscale-exposed services) — attack surface audit.
    - Consider whether accept_routes should be scoped narrower than the full /24. Tailscale doesn't support route-filtering natively, but iptables on the VPS can restrict which LAN IPs are reachable via tailscale0.
    - Review SSH hardening (key-only, fail2ban, etc.) — cross-check against current state.
  - Priority: medium. Not blocking today's work but important given the VPS is internet-facing and now has LAN reachability.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-21

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

- [x] `well raven` (prod VPS) migration — DONE 2026-04-20
  - Both app-node migrations complete. CT163 → gb-lon-wg-002, prod VPS → gb-lon-wg-003. Prod VPS Phase 5 confirmed: allowlist `185.195.232.0/24`, observed egress `185.195.232.135`. `docs/vpn.md` updated. Original backlog rationale (get both app nodes off rented-provider servers onto Mullvad-owned ones) fully satisfied.
  - Added: 2026-04-20, Completed: 2026-04-20

- [ ] Extend tailscale pref reconciliation to non-router nodes (partial progress)
  - **Done 2026-04-20** for nodes with the `tailscale_router` role (VM171, CT163, staging-home, mums — and new RR workers going forward, which now carry the role per the updated runbook). The role has: config-merge → pre-flight assertions (advertise+consume collision, LAN-adjacency gotcha) → idempotent `tailscale set` gated on BackendState=Running. Schema extended with `exit_node`, `exit_node_allow_lan_access`, `accept_routes`.
  - **Still TODO**: nodes on the tailnet that do NOT have the `tailscale_router` role. Current examples: CT173 (if role ever removed), VM133 nagios, rr-application-prod-vps, CT172 observability. These ignore their declared `tailscale` config — runtime prefs can drift silently. Options: (a) rename `tailscale-router` → `tailscale-node` and apply to every tailnet-joined guest (clean but big refactor — touches inventory groups, playbook wiring, every guest's roles list), (b) add `tailscale_router` role to every tailnet-joined guest one at a time (less invasive, but the name becomes a misnomer estate-wide), (c) extract the "assert + reconcile" tasks into a new `tailscale-node` role that runs on every tailnet-joined guest, keeping `tailscale-router` for routers only (cleanest split but introduces a new role to maintain).
  - Effort: medium (any of the above)
  - Scope: homelab
  - Added: 2026-04-17, router-node part completed 2026-04-20

- [x] Runbook add-rr-worker-node.md Step 8 missing `--accept-dns=false` — DONE 2026-04-20
  - Resolved by replacing the hardcoded `tailscale up` command with a reference to `/usr/local/sbin/tailscale-phase1-up`, which is rendered from declared config by the `tailscale_router` role. New workers now add `tailscale_router` to their roles list in Step 2, so phase1-up exists at Step 8 time. Eliminates the join→first-apply window.
  - Added: 2026-04-17, Completed: 2026-04-20

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

- [ ] T420 eBay listing — finalise and publish
  - Context: memtester result pending, HBA card text to read physically, condition section needed, root password reset, iDRAC factory reset before shipping
  - Effort: low
  - Added: 2026-04-14, Downgraded: 2026-04-20 — no active pressure to sell

- [ ] OS-level hostname drift on both remote nodes
  - Context: Both remote nodes still report their pre-rename OS hostnames: `rr-worker-prod-mums` live hostname is `mums-house-mbp`, `rr-worker-staging-home` live hostname is `raptor-node-staging` (even older — from the first rename pass). Tailscale advertises the current names correctly, but `/etc/hostname` and `/etc/hosts` are stale. `remote-node-baseline` role documents "hostname + /etc/hosts mapping" as one of its concerns — either the hostname task isn't actually running on these nodes, or it ran before the rename and hasn't been re-applied. Next time `python3 scripts/run.py remote-nodes` is run, investigate why hostname doesn't reconcile; fix if the role logic is broken. Low-impact (cosmetic for local login prompt and `/etc/hostname`; Tailscale identity is correct) but an example of declared-vs-runtime drift.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-20

- [ ] Staging config/reality drift on RR DB access — rr_discovery_staging orphaned, rr_worker RR-managed
  - Context: CT163's `rr_db_access` config declares `username: rr_discovery_staging` with `grants: [SELECT]` (via role default) and vaults `rr_discovery_staging_db_password` in `ansible/secrets-rr-staging.yml`. Live state (confirmed 2026-04-20 during prod cleanup): the staging worker actually connects as `rr_worker`, not `rr_discovery_staging`. Both users exist; both have identical `SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER, TRUNCATE` grants on 15 tables — much broader than role-declared. `rr_discovery_staging` is orphaned (no active sessions). `rr_worker`'s password was set by RR directly and is not in homelab vault. Cleanup is analogous to prod's 2026-04-20 rr_worker adoption: update config to `username: rr_worker` + `grants: [SELECT, INSERT, UPDATE]` + `remove_users: [rr_discovery_staging]`, generate + vault `rr_worker_staging_db_password`, apply — and **RR needs to pick up the new password before the next worker reconnect**, same coordinated handoff as prod. Not urgent; staging is currently working (just not per config).
  - Effort: low (same mechanism as prod)
  - Scope: homelab tracks state; RR coordinates password handoff
  - Added: 2026-04-20

- [ ] Reconcile unique-egress policy wording with RR's /24-pool interpretation
  - Context: `docs/vpn.md` §Egress Policy says "Every RR worker gets a unique egress IP. No sharing." RR has accepted that two staging workers sharing a single Mullvad /24 egress pool — but observing distinct egress IPs within that pool — satisfies the spirit of the unique-egress rule. Our policy text is stricter than RR's interpretation. Either tighten to match the policy (which rules out pool-sharing entirely) or loosen to match RR's interpretation (unique observed IP, not necessarily unique pool). Not urgent today; raised here so it gets discussed when the next staging worker is provisioned or when policy is revisited.
  - Effort: low (documentation decision)
  - Scope: homelab + RR coordination
  - Added: 2026-04-20

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
