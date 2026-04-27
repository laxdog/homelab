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

- [x] Jellyfin ingress cutover after LDAP bind works — DONE 2026-04-23
  - Context: `jellyfin.lax.dog` had been behind Authentik forward-auth after the LDAP groundwork landed. Final cutover removed the stacked forward-auth layer, re-validated native Jellyfin login on both hostnames, and kept local `admin` as break-glass.
  - Outcome: both `jellyfin.laxdog.uk` and `jellyfin.lax.dog` now present native Jellyfin login directly against CT167, with LDAP-backed normal users and a local break-glass admin.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-22, Completed: 2026-04-23

## Medium Priority

- [ ] NPM `nginx-proxy-manager-config` role: cert issuance OOM + Update task halts Create task
  - Context: Surfaced 2026-04-27 during CT175 obsidian rollout (and previously on 2026-04-20 with `loki.laxdog.uk`). When the laxdog-internal-le cert SAN list grows and a new cert needs issuing, NPM's backend (`max_old_space_size=250` MB) gets OOM-killed under the cert-create + nginx-reload-storm load. After NPM auto-restarts, the role's "Update proxy host when needed" task starts hitting NPM 502s on existing external proxy hosts (specifically the `*.lax.dog` ones with `laxdog-external-le`); when the loop fails, Ansible removes the host from subsequent tasks for that play, so "Create AdGuard proxy host when missing" never runs and any new proxy hosts in `config/homelab.yaml` don't get materialised in NPM. Today worked around by creating proxy hosts directly via `POST /api/nginx/proxy-hosts` with the new cert id.
  - Proposed fix: split the role's loops so a Create-missing-hosts pass runs *before* the Update-existing pass (so net-new entries land even if updates trip), and/or bump NPM's `node --max_old_space_size` so cert work doesn't OOM the API. Both changes are small, but need testing against the live NPM dataset (47+ proxy hosts, 24 certs).
  - Effort: low–medium
  - Scope: homelab
  - Added: 2026-04-27

- [ ] AdGuard role's template render task silently skipped on multi-host applies
  - Context: 2026-04-27 ran `ansible-playbook guests.yml --limit "obsidian,nginx-proxy-manager,adguard,heimdall,organizr,nagios"` to roll out CT175. Recap reported `adguard ok=9 changed=0`, but the new `obsidian.laxdog.uk` and `obsidian-api.laxdog.uk` rewrites declared in `config/homelab.yaml` did NOT make it into `/opt/AdGuardHome/AdGuardHome.yaml` (file mtime stayed on 2026-04-21). Re-running with `--limit adguard` produced `ok=42 changed=3` and the rewrites appeared as expected. The "Render AdGuardHome configuration" task has no `when:` clause, so it should always run — repro mechanism unclear. Possibly related to the NPM play's `failed=1` earlier in the same playbook run interacting with shared facts or with the `meta: flush_handlers` + `notify: Restart AdGuardHome` chain.
  - Risk: silent — recap looks clean. If a future apply renders ALL of AdGuard's declared state but selectively skips it, drift accumulates without notice. Same `template render` task is also the load-bearing path that 2026-04-20's incident classified as "high-risk" (it can wipe rewrites entirely if it renders empty).
  - Proposed fix: add an explicit drift-detection assertion at the end of the AdGuard play that re-reads the rendered file and fails if any declared rewrite/user_rule isn't present. Cheap belt-and-braces. Repro the original skip first to understand the mechanism.
  - Effort: low (assertion); medium (root-cause)
  - Scope: homelab
  - Added: 2026-04-27

- [ ] Authentik SMTP + recovery flow for Jellyfin users
  - Context: Authentik now has a repo-managed invitation-only Jellyfin enrollment flow, but forgot-password remains blocked. Current runtime has no repo-managed SMTP/email delivery, no Authentik email stage, and no recovery flow bound to the default brand. Until mail exists, password resets stay operator-driven.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-23

- [ ] VM171 Mullvad egress monitoring (detect silent wg-quick policy-routing loss)
  - Context: on 2026-04-22 06:32 unattended-upgrades triggered a `systemd-networkd` restart that flushed ip-rules. Tailscale self-healed its rules; wg-quick didn't, and the role's pri 5200/5208/5209 rules stayed gone for ~30 h before being detected by an unrelated audit. VM171's own egress silently fell back to home NAT (`212.56.120.65`) and `rr-worker-staging-home`'s exit-node-forwarded traffic black-holed at the kill-switch tail DROP. Commit 1ab02e9 on 2026-04-23 installs a `PartOf=systemd-networkd.service` drop-in so wg-quick follows networkd's lifecycle, which closes the specific regression — but a monitor that would have caught the outage on detection rather than audit is still missing.
  - Proposed check: a Nagios `VM171 Mullvad Egress` service that periodically confirms VM171 is egressing through Mullvad. Two plausible shapes:
    - **A — SSH-driven from VM133.** Add a `check_vm171_egress.sh` that `ssh`es into VM171 (needs a dedicated read-only nagios key + matching `authorized_keys` entry) and runs `curl -s --max-time 5 https://am.i.mullvad.net/json | jq -e '.mullvad_exit_ip == true and (.ip | startswith("146.70.189."))'`. Reuses the existing `check_raffle_raptor.py` pattern of a custom check on VM133 + a service definition in `homelab.cfg.j2`. Blast radius: new SSH key plumbing, one script, one service entry. Alert thresholds: CRITICAL if `mullvad_exit_ip: false`, WARNING if IP outside the expected `146.70.189.0/24` pool (pool will change if VM171 is ever re-pinned away from ie-dub-wg-101, so this value must be re-checked on re-pin).
    - **B — HTTP-health endpoint on VM171.** Run a tiny systemd timer on VM171 that every N minutes writes current egress state to a static file served by a minimal HTTP service (or Caddy), then use the existing `http_backend_checks` mechanism to probe it. Cleaner, no SSH key, but more new surface (HTTP service on VM171, log rotation, etc.).
  - Recommendation: option A is the cheaper first pass, option B only if we later want a shared "per-host egress observability" pattern.
  - Priority: medium. The 2026-04-23 drop-in covers the known trigger; this is for the class of failure modes we haven't enumerated (rule-flushing triggers we haven't seen yet, Mullvad server rotation away from `ie-dub-wg-101` — especially relevant now that VM171 sits on a rented M247 IE server where the `known eel` failure mode applies, wg0 handshake failures that still leave the interface up, etc.).
  - Effort: low–medium
  - Scope: homelab
  - Added: 2026-04-23

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

- [x] Extend tailscale pref reconciliation to non-router nodes — DONE 2026-04-23
  - Context: the original `tailscale_router` role only attached to subnet-router / exit-node advertisers (VM171, CT163, staging-home, mums, prod-vps, CT172). Tailnet-joined leaves (CT173 rr-worker-prod-proxmox, VM133 nagios) had no reconciliation and could drift silently — VM133 was showing `CorpDNS=true` and CT173 had `ExitNodeAllowLANAccess=true` against declared defaults.
  - Resolved by Option C: renamed `ansible/roles/tailscale-router` → `ansible/roles/tailscale-node`, renamed inventory group `tailscale_router_hosts` → `tailscale_node_hosts`, updated all role-list references in `config/homelab.yaml` (+playbooks, AGENTS.md, runbooks, tailscale.md). Moved CT173's `tailscale:` block from `remote_nodes.nodes.rr-worker-prod-proxmox` into `services.lxcs.rr-worker-prod-proxmox` (the LXC's real home) and added `tailscale_node` to its roles. Added a `tailscale:` block + `tailscale_node` role to `services.vms.nagios` for VM133. All 8 infra tailnet hosts now reconcile their declared prefs on every ansible apply and pass the role's two config-layer assertions.
  - Added: 2026-04-17, router-node part completed 2026-04-20, full coverage completed 2026-04-23

- [x] Runbook add-rr-worker-node.md Step 8 missing `--accept-dns=false` — DONE 2026-04-20
  - Resolved by replacing the hardcoded `tailscale up` command with a reference to `/usr/local/sbin/tailscale-phase1-up`, which is rendered from declared config by the `tailscale_node` role (renamed from `tailscale_router` on 2026-04-23). New workers now add `tailscale_node` to their roles list in Step 2, so phase1-up exists at Step 8 time. Eliminates the join→first-apply window.
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

- [ ] Fix VM133 (Nagios) direct-LAN SSH — Permission denied (publickey)
  - Context: SSH to `mrobinson@10.20.30.133` fails with `Permission denied (publickey)`. TCP reachability is fine — the handshake completes and sshd rejects the key. Ansible reports this as `UNREACHABLE!` in play output, which is misleading (earlier backlog wording called it "unreachable" — it is not). Nagios monitoring itself still works because its checks come over Tailscale (100.120.89.28) with a different key path; only direct LAN SSH as the unprivileged `mrobinson` user is broken.
  - Known consequences:
    - Promtail deployment to VM133 fails — no VM133 journal logs in Loki.
    - Any `remote-nodes.yml` apply that reaches the nagios-delegate tasks (`Deploy Nagios remote-node check scripts to VM133` + `Deploy Nagios remote-nodes.cfg to VM133` + `Ensure remote-nodes.cfg is included in nagios.cfg`) aborts with UNREACHABLE on the delegation. Remote-node-baseline tasks that precede those still apply; tasks after don't. Working around this today by ordering other `remote-node-baseline` tasks before the nagios-delegate block (did this 2026-04-23 when adding Docker daemon.json management to the role).
  - Fix direction: either distribute the nagios-admin ssh key to VM133 under `mrobinson`'s `authorized_keys` (it clearly was, then wasn't), or switch the delegations to use `ubuntu@10.20.30.133` with sudo/become, or delegate via the tailscale IP instead of the LAN IP.
  - Effort: low once diagnosed
  - Scope: homelab
  - Added: 2026-04-15, re-scoped 2026-04-23 after remote-nodes.yml consequence surfaced

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

- [x] apt-cacher-ng stale DNS for CDN-backed repos — RESOLVED 2026-04-22
  - Context: incident 2026-04-22 — a 9-day-old apt-cacher-ng process on CT156 was serving dead CloudFront edges for `download.docker.com`. CloudFront rotated away from the IPs it had on startup (`18.239.236.x` gone); every CONNECT SYN-retried and timed out, surfacing to clients as `HTTP/1.0 502 CONNECT error: Connection timeout`. Blocked docker-repo apt operations on every proxied host (CT163, CT173, etc.) until the service was manually restarted.
  - Resolved by: declared `DnsCacheSeconds: 3600` explicitly in `/etc/apt-cacher-ng/acng.conf` via the `apt_cacher` role (`ansible/roles/apt_cacher/tasks/main.yml`). Applied to CT156, service restarted via handler, `CONNECT download.docker.com` now returns 200 in ~220 ms. Second apply is idempotent (`changed=0`).
  - Caveat — if this recurs: the upstream default was already 1800 s, so a 9-day process *should* have re-resolved many times over. If we see another case of stale CDN IPs, the DnsCacheSeconds knob alone won't be enough and a weekly systemd-timer restart as a backstop is the next step. Explicit config also means the value is now auditable in git rather than implicit default.
  - Added: 2026-04-22, Completed: 2026-04-22

## Future

- [ ] Migrate to OPNsense
  - Context: current router is stock ASUS RT-AC86U. DHCP reservations are MAC-only (no hostname support on stock firmware). OPNsense will provide proper named DHCP, better VLAN support, and cleaner integration with the homelab. Guest SSIDs were causing issues with Merlin so stock firmware is being used in the interim.
  - Effort: high
  - Added: 2026-04-14
