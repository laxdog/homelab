# Remote Nodes (WiFi Laptops)

Source of truth: `config/homelab.yaml` under `remote_nodes`.

## Scope
This baseline is for WiFi-only remote laptops that are administered over SSH + Tailscale.

Current nodes:
- inventory name: `rr-node-prod-mums`
- LAN bootstrap IP: `10.20.30.75`, Tailscale: `100.118.218.126`
- desired hostname: `rr-node-prod-mums`
- inventory name: `rr-node-staging-local`
- LAN bootstrap IP: `10.20.30.153`, Tailscale: `100.88.35.124`
- desired hostname: `rr-node-staging-local`
- NOTE: Ansible inventory uses Tailscale IPs for both nodes (not LAN IPs)
- purpose: staging remote node for future remote deploy testing
- current tailscale state: joined (`BackendState=Running`)
- exit-node capability: enabled (`Self.ExitNodeOption=true`)
- key expiry: disabled (`Self.KeyExpiry=null`)

Role split:
- `rr-node-staging-local` is the staging node for remote deploy validation.
- `rr-node-prod-mums` remains the production-style remote node baseline reference.

## Repo Layout
- inventory generation: `scripts/run.py` (`remote_nodes` -> `remote_nodes_hosts`)
- apply playbook: `ansible/playbooks/remote-nodes.yml`
- baseline role: `ansible/roles/remote-node-baseline`
- tailscale role (reused): `ansible/roles/tailscale-router`
- vaulted WiFi secrets: `ansible/secrets.yml` (per-value vault entries)

## What The Baseline Configures
- hostname + `/etc/hosts` mapping
- OpenSSH service enabled
- unattended upgrades enabled (`/etc/apt/apt.conf.d/20auto-upgrades` + service)
- `uptimed` installed/enabled
- lid-close suspend disabled in `/etc/systemd/logind.conf`:
  - `HandleLidSwitch=ignore`
  - `HandleLidSwitchExternalPower=ignore`
  - `HandleLidSwitchDocked=ignore`
- sleep targets hard-masked to prevent desktop power managers from suspending:
  - `sleep.target`
  - `suspend.target`
  - `hibernate.target`
  - `hybrid-sleep.target`
- conservative self-check watchdog:
  - script: `/usr/local/sbin/remote-node-healthcheck`
  - timer: `remote-node-healthcheck.timer` (every 5 minutes)
  - behavior:
    - logs and tracks sustained network failures
    - restarts `tailscaled` if inactive
    - restarts `NetworkManager` after 3 failed checks (cooldown 15m)
    - performs one bounded reboot only after 45m sustained failure (cooldown 24h)
- tailscale package + service installed/enabled
- forwarding sysctls enabled for exit-node capability
- helper for manual join:
  - `/usr/local/sbin/tailscale-phase1-up`
- WiFi hardening for reboot-safe pre-login access:
  - configured fleet SSIDs are forced system-wide (`connection.permissions=''`)
  - configured fleet SSIDs keep their configured autoconnect + priority values
  - configured fleet SSID PSKs are persisted in NetworkManager (`psk-flags=0`)
  - WiFi power saving is disabled via `/etc/NetworkManager/conf.d/99-remote-node-wifi-powersave.conf`
  - non-catalog stale WiFi profiles have autoconnect disabled to avoid selecting user-bound profiles
  - KWallet PAM hooks in `/etc/pam.d/sddm` are commented for unattended-node behavior

## Tailscale Notes
- Remote nodes can override global tailscale settings via:
  - `remote_nodes.nodes.<name>.tailscale`
- For this node:
  - `advertise_routes: []`
  - `advertise_exit_node: true`
  - `accept_dns: false`

This keeps it as an exit-node target without advertising LAN subnet routes.

## WiFi Root Cause (Observed)
The laptop previously became unreachable after reboot with NetworkManager showing
"waiting for authorization". Root cause was user-bound/stale WiFi profiles in netplan/NM
state (for example `connection.permissions=user:mrobinson` and `wifi-security.psk-flags=1`)
which are not reliable for unattended pre-login reconnect.

NetworkManager log evidence looked like:
- `no secrets: No agents were available for this request`
- `state change: need-auth -> failed (reason 'no-secrets')`

That indicates dependency on desktop secret agents (KWallet/plasma NM agent) for some
profiles, which is not acceptable for remote unattended nodes.

The durable fix is to normalize the active deployment WiFi profile as a system profile,
disable autoconnect on stale non-active profiles, and hard-mask sleep targets for unattended nodes
so lid events cannot suspend the host via desktop power managers.

Current expected active profile state:
- `connection.permissions=''`
- `connection.autoconnect=yes`
- `connection.autoconnect-priority=100`
- `802-11-wireless-security.psk-flags=0`

Current expected non-catalog profile state:
- `connection.autoconnect=no` (unless explicitly cataloged in `config.remote_nodes.wifi_networks`)

## Apply Commands
- apply remote-node baseline only:
  - `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass python3 scripts/run.py remote-nodes`

## Validation Commands (Targeted)
From control host:
- `ssh mrobinson@10.20.30.75 'hostnamectl --static'`
- `ssh mrobinson@10.20.30.75 'sudo -n true'`
- `ssh mrobinson@10.20.30.75 'systemctl is-active ssh tailscaled unattended-upgrades remote-node-healthcheck.timer'`
- `ssh mrobinson@10.20.30.75 'grep -E "^(HandleLidSwitch|HandleLidSwitchExternalPower|HandleLidSwitchDocked)=" /etc/systemd/logind.conf'`
- `ssh mrobinson@10.20.30.75 'sudo tailscale status --json | jq -r .BackendState'`
- `ssh mrobinson@10.20.30.153 'hostnamectl --static'`
- `ssh mrobinson@10.20.30.153 'sudo -n true'`
- `ssh mrobinson@10.20.30.153 'systemctl is-active ssh tailscaled unattended-upgrades remote-node-healthcheck.timer'`
- `ssh mrobinson@10.20.30.153 'grep -E "^(HandleLidSwitch|HandleLidSwitchExternalPower|HandleLidSwitchDocked)=" /etc/systemd/logind.conf'`
- `ssh mrobinson@10.20.30.153 'sudo tailscale status --json | jq -r .BackendState'`

## Fleet WiFi Model (Vaulted)
- Network definitions live in `config.remote_nodes.wifi_networks`.
- Each entry references a vaulted password variable:
  - `ssid`
  - `password_var`
  - `autoconnect`
  - `autoconnect_priority`
- Password values live only in `ansible/secrets.yml` (vaulted), for example:
  - `remote_node_wifi_woof50_psk`
  - `remote_node_wifi_dog50_psk`
  - `remote_node_wifi_dog24_psk`
  - `remote_node_wifi_dog_psk`

Current fleet catalog:
- `woof50` (priority 100)
- `dog50` (priority 90)
- `dog24` (priority 80)
- `dog` (priority 70)
- `PSNI surveillance van #3` (priority 60)

Current fallback note:
- `PSNI surveillance van #3` is now vaulted and deployed as a system fallback profile (`autoconnect=yes`, `permissions=''`, `psk-flags=0`).

To add a new fleet SSID safely:
1. Add network entry under `config.remote_nodes.wifi_networks`.
2. Add vaulted secret var in `ansible/secrets.yml`.
3. Re-run remote baseline:
   - `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass python3 scripts/run.py remote-nodes`

## Nagios Status
- Not wired into Nagios checks yet.
- Groundwork is repo-managed host definition + remote baseline role.
- Recommended next step: add checks only after stable reachable address strategy is decided (tailscale IP/FQDN and Nagios reachability path).

## Deferred
- scraper app deployment
- Tailscale auth-key automation
- battery telemetry integration
- headless WiFi bootstrap workflow
- automatic Nagios onboarding of remote nodes

## KWallet Handling
- Baseline now disables KWallet PAM hooks in `/etc/pam.d/sddm` for unattended remote nodes.
- We do not remove all KDE/KWallet packages in phase 1.
- Requirement is that WiFi reconnect does not depend on KWallet or logged-in desktop agents.

## Tailscale Persistence / Key Expiry
- Local CLI can prove joined/running state and current key expiry timestamp:
  - `sudo tailscale status --json | jq -r '.BackendState,.Self.KeyExpiry,.Self.ExitNodeOption'`
- CLI cannot disable key expiry policy; this requires Tailscale admin UI.
- For unattended remote nodes, verify in admin UI:
  - device `rr-node-prod-mums`
  - disable/extend key expiry policy as desired for long-lived unattended access

## On-Site Tomorrow (if SSID changes)
If connecting this laptop to a different WiFi at the destination:
1. Join destination WiFi once.
2. Verify SSH on LAN.
3. Re-run:
   - `python3 scripts/run.py remote-nodes`
4. Reboot once and verify SSH returns.
5. Complete Tailscale login:
   - `ssh mrobinson@<laptop-ip> 'sudo /usr/local/sbin/tailscale-phase1-up'`
   - approve in Tailscale admin.

## Open WiFi Policy
- Arbitrary open-SSID autoconnect is intentionally not enabled for this node class.
- Reason: captive portals/rogue SSIDs can steal priority and strand unattended admin access.
- Safe pattern is to add known-good SSIDs to the vaulted catalog with explicit priorities.

## Process Note
- Remote-node changes should be committed locally at stable checkpoints.
- Pushes remain explicit/manual; do not auto-push from agent workflows.
