# Homelab Backlog

Homelab agent scope only. Per-agent backlogs live in `docs/agents/<name>.md`.

## Format
- [ ] Short description
  - Context: why this matters
  - Effort: low/medium/high
  - Added: date

---

## High Priority

- [x] Fix Authentik LDAP bind for Jellyfin groundwork — DONE 2026-04-22
  - Root cause 1: Authentik LDAP outpost bind flow wiring. The outpost currently reads its bind flow from the provider `authorization_flow`, not `authentication_flow`; our repo-managed setup had set `authentication_flow: default-authentication-flow` but left `authorization_flow` on the implicit-consent provider default. Result: valid bind credentials still returned LDAP `Invalid credentials (49)`. Fixed by updating the Authentik setup template so the Jellyfin LDAP provider sets `authorization_flow` to the intended bind flow and re-applying the narrow Authentik role.
  - Root cause 2: CT167 Jellyfin plugin config path/serialization drift. The role was managing `Jellyfin.Plugin.LDAP_Auth.xml`, while the installed plugin actually read `LDAP-Auth.xml`. The managed XML also wrote `LdapProfileImageFormat` as `0`; after restart the plugin fell back to its built-in sample config (`CN=BindUser,DC=contoso,DC=com`). Fixed by switching the managed filename to `LDAP-Auth.xml`, serializing `LdapProfileImageFormat` as `Default`, and re-applying the narrow CT167 role.
  - Outcome: CT167 LDAP bind/search now works, local Jellyfin `admin` still works, and a non-admin pilot LDAP-backed Jellyfin login for `ldapservice` now succeeds. `cjess` remains local and untouched.
  - Added: 2026-04-22, Completed: 2026-04-22

- [ ] Jellyfin ingress cutover after LDAP bind works
  - Context: `jellyfin.lax.dog` is still behind Authentik forward-auth today. That must be removed once Jellyfin-native LDAP login is validated, otherwise web/native clients will hit stacked auth. Keep `admin` as local break-glass.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-22

## Medium Priority

- [ ] VM171 Mullvad kill-switch re-verification (wg0-down test)
  - Context: the mullvad-exit killswitch template changed 2026-04-21 (commit 8a0d76f) — subnet-route rules flipped from terminal `ACCEPT` to `RETURN` so subnet-routed packets fall through to `ts-forward` for SNAT marking. Chain structure proves the kill-switch DROP at the tail still catches any non-subnet / non-Mullvad tailscale0 forwarding, but the end-to-end test (bring wg0 down → confirm exit-node-client traffic drops at eth0) was NOT exercised post-change to avoid interrupting staging-home's live exit-node traffic.
  - Scope: schedule a ~30s maintenance blip on VM171 wg0, verify that (a) staging-home's egress to internet via VM171 drops during the outage, (b) subnet-route traffic to 10.20.30.0/24 continues to work, (c) once wg0 is back, everything recovers without manual intervention.
  - Effort: low (setup + tcpdump from staging-home during wg0 stop/start)
  - Scope: homelab
  - Added: 2026-04-21

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

- [ ] Promtail role unification — wire to hosts and reconcile drift
  - Context: `ansible/roles/promtail/` exists with a full template (journal + syslog + conditional app-log scraper behind `promtail_app_logs`). But no host declares `promtail` in its `roles:` list and no host has a `promtail:` config block with scrape settings, so the `promtail_hosts` inventory group is empty and the play in `guests.yml` has never matched a host. Every live `/etc/promtail/config.yml` on the estate (CT153 adguard, CT154 NPM, CT172 observability, all RR nodes, all LAN services, etc.) was deployed manually out-of-band.
  - Evidence surfaced 2026-04-21 while adding `/var/log/raffle-raptor/*.log` scraping to 4 RR nodes — had to edit each `/etc/promtail/config.yml` by hand and restart Promtail, because there was no repo-declared path to do it cleanly. Recorded in `docs/agents/raffle-raptor.md` "Promtail app-log shipping".
  - Scope:
    - Add `promtail` role to each node's `roles:` list in `config/homelab.yaml` (or introduce a pseudo-role/group so the inventory generator picks them up).
    - Per-host `promtail:` block with `app_logs`, `app_log_path`, `app_name`, `app_env` for nodes that need app-log scraping; bare block for nodes that only need journal + syslog.
    - First apply against each host needs careful byte-diff against the existing live config — the role's template will re-render from scratch and may change label ordering / missing fields in ways that trigger a Promtail restart but leave behaviour intact. Plan for a Promtail restart per host.
    - Decide what to do with non-obvious existing labels (e.g. CT163 uses `host: raffle-raptor-dev` for its syslog scrape but `host: rr-application-staging-proxmox` for the new app-logs block).
  - Priority: medium. Current state works; cleanup makes future adds (like today's 4 RR nodes) one-line config changes instead of ssh-and-edit loops.
  - Effort: medium (touches every promtail-running host)
  - Scope: homelab
  - Added: 2026-04-21

- [ ] AdGuard role: template-wipe hazard for user_rules + persistent clients
  - Context: 2026-04-21 recon showed the original 2026-04-20 incident description was wrong. Rewrites are in fact rendered by the template (loop at lines 53–58 of `AdGuardHome.yaml.j2`, present since 2026-02-20) and do survive a play halt. The real fragility is with `user_rules` and `clients.persistent`, which the template does NOT render — they flow template-wipe → early-restart → API-repopulate. If ANY task between the restart and their API tasks fails, both are wiped until the next successful apply. Today (2026-04-21) the live AdGuard has 0 user_rules + 0 persistent clients against config declaring 19 + 2 respectively — so the incident *did* wipe state, just not the state the backlog claimed. Safesearch endpoint separately: `/control/safesearch/status` returns 200 on AdGuard 0.107.72 (not 404 as the original entry claimed); the entry was misdiagnosed. Proposed fix: render `user_rules` + `clients.persistent` in the template (same pattern as rewrites) so restart preserves them, keep the API drift-reconcile tasks as belt-and-braces, and replace the safesearch GET-then-enable/disable pattern with a single idempotent PUT to `/control/safesearch/settings` (the v0.107.30+ unified endpoint).
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-20, revised 2026-04-21

- [x] CT172 apt: `docker-compose-plugin` vs `docker-compose-v2` file collision — RESOLVED 2026-04-22
  - Root cause: on 2026-04-14 someone ran `apt-get install -y docker.io docker-compose-v2` on CT172 (apt history.log confirms). That manually pulled in Ubuntu's native `docker.io` + `docker-compose-v2` alongside the Docker CE stack the ansible `docker-host` role installs. Both `docker-compose-plugin` (Docker repo, v5.1.3) and `docker-compose-v2` (Ubuntu noble-updates, v2.40.3) declare ownership of `/usr/libexec/docker/cli-plugins/docker-compose`. The `--force-overwrite` from 2026-04-20 only transferred the binary; both packages remained installed and would re-collide on the next upgrade. Fleet check: only CT172 was affected — all 14 other docker hosts have only `docker-compose-plugin`.
  - Resolved by: purged `docker-compose-v2`, `docker.io` (was `rc`), `containerd` (was `rc`) on CT172. `docker.io` postrm called `/var/lib/docker/nuke-graph-directory.sh` which would have wiped docker-ce's shared `/var/lib/docker`; LXC blocked the umount (block-devices-not-permitted), which accidentally saved the running containers. Neutralised the nuke script (moved to `/root/nuke-graph-directory.sh.disabled-20260422`) and completed the purge. `apt-get autoremove -y` dropped bridge-utils, dns-root-data, dnsmasq-base, ubuntu-fan. All 4 observability containers (loki, grafana, prometheus, json-exporter) stayed up throughout. `dpkg -S /usr/libexec/docker/cli-plugins/docker-compose` now returns only `docker-compose-plugin`. `docker compose version` → v5.1.3. Docker-host role hardened with an "ensure-absent" task for `docker.io`, `docker-compose-v2`, `containerd` as cheap insurance against repeat manual installs.

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

- [ ] Obsidian / CouchDB sync broken
  - Context: `couchdb.lax.dog` is still externally exposed in CF (proxied A → home NAT) specifically so that Obsidian's LiveSync plugin on off-LAN devices can reach CouchDB. The external path exists but the sync itself is currently broken — Obsidian clients can't reach the CouchDB server through the external hostname, mechanism unknown (could be NPM config, CouchDB CORS, Obsidian plugin auth, or CF/Authentik interference). `couchdb.laxdog.uk` (internal) works for LAN devices. External record is retained pending diagnosis — do NOT delete `couchdb.lax.dog` from CF until sync is either fixed or moved to Tailscale-only clients.
  - Scope: diagnose from an off-LAN Obsidian device; fix or decide to retire external path.
  - Effort: low/medium
  - Scope: homelab
  - Added: 2026-04-22

- [ ] Google Home integration on Home Assistant — Authentik exemption or removal on ha.lax.dog
  - Context: `ha.lax.dog` is currently behind Authentik forward-auth in NPM (`authentik_protect: true`, verified live on CT154 proxy_host 33.conf). DNS recon on 2026-04-22 confirmed NO Google Home / Nabu Casa integration currently active — 0 queries to `*.googleapis.com` / `*.nabu.casa` from HA (10.20.30.122) in the last 8 days of AdGuard query log. If Google Home is adopted (either direct Actions project or via Nabu Casa), Google's fulfillment endpoints MUST be able to hit HA's `/api/google_assistant` without Authentik intercepting — forward-auth will break the Sync/Query/Execute flow. Two options when ready: (a) exempt `/api/google_assistant` path from forward-auth in NPM, or (b) drop forward-auth on `ha.lax.dog` entirely and rely on HA's built-in auth.
  - Scope: decide approach when/if Google Home is added; update NPM config accordingly.
  - Effort: low (NPM advanced-config change)
  - Scope: homelab
  - Added: 2026-04-22

- [ ] Remove `*.lax.dog` wildcard in Cloudflare
  - Context: the wildcard CNAME `*.lax.dog → lax.dog` is currently load-bearing for six media-stack services — `cleanuparr`, `prowlarr`, `qbittorrent`, `radarr`, `sabnzbd`, `sonarr`. None of them have explicit CF records; external access goes wildcard → apex A → home NAT → NPM. Created 2020-01-06, last modified 2024-12-20, predates most current homelab work. Can't be deleted until media-stack stops needing external DNS (tailnet-only migration) OR explicit records are added for each. Pre-flight before removal: confirm no other services rely on wildcard (grep NPM and homelab.yaml for `.lax.dog` consumers without explicit records), grep Authentik app registrations for `*.lax.dog` external_hosts, and check the `_acme-challenge` TXT path still works for cert issuance. Related: four records deleted 2026-04-22 (`nagios`, `netalertx`, `proxmox`, `stream`); wildcard covers any stale external links to those but internal laxdog.uk paths are the real substitute.
  - Scope: migrate media-stack off wildcard; then delete `*.lax.dog` CNAME.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-22

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
