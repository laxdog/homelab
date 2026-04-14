# Homelab Backlog

Items are grouped by priority and scope.
Agents should check this file at the start of each session and update it as work is completed or new items are identified.

## Format
Each item:
- [ ] Short description
  - Context: why this matters
  - Effort: low/medium/high
  - Scope: homelab/media-stack/rr/ha/batocera
  - Added: date

---

## High Priority

- [ ] T420 eBay listing — finalise and publish
  - Context: memtester result pending, HBA card text to read physically, condition section needed, root password reset, iDRAC factory reset before shipping
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

## Medium Priority

- [ ] NPM upstream healthcheck on restart
  - Context: NPM proxies to backends before they are ready after full estate restart, causing brief 502s. RR agent flagged this. Options: nginx upstream health config, NPM startup delay, or replace NPM with Caddy/Traefik.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-14

- [ ] Offsite backups
  - Context: all backups currently on tank pool on the same physical host as live data. Single point of failure for total data loss. Tailscale already in place for transport. Tier 1 guests (HA, RR, Authentik, CouchDB) should be replicated off-host first.
  - Effort: high
  - Scope: homelab
  - Added: 2026-04-14

- [ ] Terraform plan should be run and applied after every session to prevent drift
  - Context: TF credentials are in the vault, agent can run this autonomously. Should be a standard end-of-session check.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] check_raffle_raptor.py not in repo
  - Context: the Nagios check plugin on VM133 was deployed directly via SSH. It should be in the repo under ansible/roles/nagios or similar and deployed via Ansible.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] SSDs on SAS3008 TRIM verification
  - Context: SSDs were moved to onboard Intel SATA controller and TRIM is now confirmed working. The SAS3008 TRIM passthrough was never tested with an actual SSD connected. Low priority since TRIM is already working via AHCI — but worth documenting the test result for future reference.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] sde Kingston SSD — no redundancy
  - Context: Kingston 894GB on ssd-fast pool is a single disk with no mirror. Hosts CT153 AdGuard, CT163 RR-dev, CT170 Authentik. These are backed up daily to tank but a disk failure means downtime until restore. Consider adding a mirror partner when a suitable SSD is available.
  - Effort: medium
  - Scope: homelab
  - Added: 2026-04-14

## Low Priority

- [ ] Stale WiFi profiles on mums-house-mbp
  - Context: 4 profiles with GNOME keyring passwords (EE-R2F2CJ, Castlewood Guest WiFi, theinternet, VM0513311) — inaccessible and dead weight. Clean up manually.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] AdGuard DNS slow upstream checks
  - Context: Nagios DNS plugin checks (bazarr.laxdog.uk, iana.org etc.) show intermittent SOFT timeouts due to AdGuard occasionally taking >5s. Bumping the plugin timeout (-t flag) would silence the log churn without hiding real failures.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] NPM stale cert cleanup
  - Context: ~15 superseded LE cert IDs (2-16) in NPM DB, not in active use. Can be deleted via NPM API at leisure.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] adguard.lax.dog vs dns.lax.dog
  - Context: adguard.lax.dog was removed from NPM as broken. dns.laxdog.uk works correctly. Decision pending on whether external AdGuard access is wanted via lax.dog domain.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

- [ ] Batocera debug screenshot cleanup
  - Context: docs/batocera/.../glxgears.png leftover debug file in repo. Trivially removable.
  - Effort: low
  - Scope: batocera
  - Added: 2026-04-14

- [ ] T420 — SAS3008 TRIM cable test
  - Context: spare connector on SAS3008 breakout cable was identified but never tested due to wrong cable end. If selling T420, this is moot. If keeping it, test TRIM on SAS3008.
  - Effort: low
  - Scope: homelab
  - Added: 2026-04-14

## Media-Stack

- [ ] Remove stale Bazarr patch file
  - Context: /opt/media-stack/appdata/bazarr/fix/ui.py — patch no longer needed as upstream Bazarr fixed the SQLAlchemy bug. Safe to delete. Update docs accordingly.
  - Effort: low
  - Scope: media-stack
  - Added: 2026-04-14

## Raffle-Raptor

- [ ] overdue_count WARN on prod statusz
  - Context: RR worker intermittently falling behind (success_rate dropping to 0.67, p95 spiking to 4182ms). RR agent investigating. Homelab action: none until RR agent reports back.
  - Effort: unknown
  - Scope: rr
  - Added: 2026-04-14
