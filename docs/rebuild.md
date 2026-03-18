# Rebuild

## Minimal manual bootstrap
1. Install Proxmox.
2. Set management IP to `10.20.30.46/24` and enable SSH access.
3. Ensure your SSH public key is installed for `root`.

## Repo-driven rebuild
1. Install Python deps: `pip install -r scripts/requirements.txt`
2. Terraform credentials:
   - Either export `TF_VAR_proxmox_username` + `TF_VAR_proxmox_password` (or `TF_VAR_proxmox_api_token`), or
   - Ensure `terraform_user_password` is in `ansible/secrets.yml` and `ANSIBLE_VAULT_PASSWORD_FILE` is set.
3. Provide vault password (e.g. `ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass`)
4. Run orchestrator: `scripts/run.py apply`
5. Host baseline is applied first, then guests.
6. Run fast validation: `scripts/run.py validate`
7. Run full validation before/after major changes: `scripts/run.py validate --mode full`

Any remaining manual steps should be documented here.

## Tailscale phase-1 manual steps
After `scripts/run.py apply`, complete these in order:

1. SSH to the gateway VM:
   - `ssh ubuntu@10.20.30.171`
2. Join/login and advertise route+exit-node:
   - `sudo /usr/local/sbin/tailscale-phase1-up`
3. In Tailscale admin console, approve:
   - subnet route `10.20.30.0/24`
   - exit node advertisement
4. In Tailscale admin DNS settings, configure split DNS:
   - domain: `laxdog.uk`
   - nameserver: `10.20.30.53`
5. On each remote client (as needed):
   - enable subnet route acceptance
   - select the home exit node only when needed

## Home Assistant manual bootstrap (HAOS)
HAOS is appliance-style, so HACS installation is a one-time manual step.

1. Complete HA onboarding (handled by repo on first run).
2. HA reverse-proxy trust is also repo-managed on first/next `guests` apply via
   `config.home_assistant.http` (no manual `configuration.yaml` edits required).
3. Install HACS using the official guide: `https://www.hacs.xyz/docs/setup/download`
4. In HACS, install `Mushroom` (Lovelace card).
5. In HACS, install `ApexCharts Card` (primary TRV graph card).
6. Optional: install `mini-graph-card` as fallback.
7. Restart Home Assistant.
8. Re-apply HA repo automation/config:
   - `python3 scripts/run.py guests`
   - `python3 scripts/home_assistant.py apply-core`
   - `python3 scripts/home_assistant.py sync-devices`
   - `python3 scripts/home_assistant.py sync-heating-control`
   - `python3 scripts/home_assistant.py sync-light-routines`
   - `python3 scripts/home_assistant.py sync-remote-light-controls`
   - `python3 scripts/home_assistant.py sync-remote-heating-controls`
   - `python3 scripts/home_assistant.py sync-heating-alerts`
   - `python3 scripts/home_assistant.py sync-heating-dashboard`
   - `python3 scripts/home_assistant.py sync-hue-scenes`
   - `sync-heating-control` also reapplies repo-managed overnight hard-off windows.
  - `sync-light-routines` reapplies repo-managed bedroom sunrise lighting and any temporary fixed-window light schedules.
  - `sync-remote-light-controls` reapplies repo-managed ZHA remote-to-light bindings such as the bedroom STYRBAR.
  - `sync-remote-heating-controls` reapplies repo-managed ZHA remote-to-heating bindings such as the living room heating boost remote.
    It also reapplies reusable boost scripts such as `script.boost_downstairs` and `script.cancel_boost_downstairs`.
    Repo-managed boost timers and restore-state helpers come from the HAOS/bootstrap side, so
    `scripts/run.py guests` must be part of the rollout when those definitions change.
    Boost recovery now depends on the timer/helper desired-state model, so repeated
    `scripts/run.py guests` runs should remain idempotent and must not create duplicate
    `timer:` or `input_text:` sections in HAOS `configuration.yaml`.
  - `sync-heating-alerts` reapplies repo-managed visual heating alerts such as the living room red flash on `23C` targets.
  - Active repo-managed boosts override repo-managed scheduled `off` events and overnight hard-off windows
    for their own target TRVs; manual all-off/lockout controls still override everything.
   - Hue scene automation uses `config.home_assistant.hue_scene_cycle.trigger_subtype`
     for its ZHA event command (`turn_off` maps to `off_short_release`, `turn_on` to `on_short_release`).

## Home Assistant restore notes
- What repo rebuild/reapply does recover:
  - HAOS VM/bootstrap
  - repo-managed core config
  - repo-managed device naming/areas
  - repo-managed automations/scripts/dashboards/lightroutines/remote bindings
- What is not evidenced as recoverable from repo alone:
  - native HA backups themselves
  - backup schedule/retention/off-site handling
  - manually installed HACS/frontend resources until reinstalled
  - manually created helpers until recreated
  - unmanaged runtime-only automations/scripts/scenes
  - recorder/history/logbook data
- If a native HA backup exists, restore that first, then rerun the HA helper commands above.
- If no native HA backup exists, use the HAOS bootstrap flow above and treat the repo helper commands as the recovery path for repo-managed HA behavior only.

## HAOS note
Home Assistant OS uses its own networking stack and does not consume cloud-init.
Ensure your router has a DHCP reservation for `10.20.30.134` (or update `config/homelab.yaml` and NPM/AdGuard rewrites).

## Access notes
- Guests are reachable via SSH keys.
- A single vaulted root password is also set for guest console access.
- Per-service login references are written to Proxmox Notes by `scripts/proxmox_metadata.py` from `config/homelab.yaml`.
- Proxmox Notes store vault variable names only (not cleartext passwords).
