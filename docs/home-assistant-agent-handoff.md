# Home Assistant Agent Handoff

## Scope
- Manage Home Assistant VM (`10.20.30.134`) config and automations as IaC.
- Keep source of truth in `config/homelab.yaml` + `scripts/home_assistant.py`.
- Avoid manual UI edits unless explicitly required (HACS installs are still manual on HAOS).

## Source of Truth
- VM + network placement: `config/homelab.yaml` -> `services.vms.home-assistant`
- HA runtime + devices + heating + Hue scene cycle: `config/homelab.yaml` -> `home_assistant`
- HA reverse-proxy trust config: `config/homelab.yaml` -> `home_assistant.http`
- Admin password var: `ansible/secrets.yml` -> `home_assistant_admin_password`
- Automation helper script: `scripts/home_assistant.py`
- The repo does not fully define all possible live HA runtime state; unmanaged or historical
  runtime entities may still exist and should be confirmed before cleanup.

## Access
- Internal URL: `https://ha.laxdog.uk`
- External URL: `https://ha.lax.dog` (through NPM / Authentik policy)
- Direct IP URL: `http://10.20.30.134:8123`
- If `ha.laxdog.uk` shows `400 Bad Request`, re-run `scripts/run.py guests` to
  re-apply repo-managed `configuration.yaml` proxy trust settings.

## Standard Commands
- Core config apply:
  - `python3 scripts/home_assistant.py apply-core`
- Device naming/areas:
  - `python3 scripts/home_assistant.py sync-devices`
- TP-Link/Kasa hub integration:
  - `python3 scripts/home_assistant.py add-tplink`
- Heating control automations/scripts:
  - `python3 scripts/home_assistant.py sync-heating-control`
- Light routines:
  - `python3 scripts/home_assistant.py sync-light-routines`
- ZHA remote light controls:
  - `python3 scripts/home_assistant.py sync-remote-light-controls`
- ZHA remote heating controls:
  - `python3 scripts/home_assistant.py sync-remote-heating-controls`
- Heating alerts:
  - `python3 scripts/home_assistant.py sync-heating-alerts`
- Heating dashboard:
  - `python3 scripts/home_assistant.py sync-heating-dashboard`
- Hue remote scene cycle automation:
  - `python3 scripts/home_assistant.py sync-hue-scenes`
- Summary/debug:
  - `python3 scripts/home_assistant.py summary`

## Backup / Recovery Status
- Evidenced in repo:
  - HAOS bootstrap/onboarding path
  - repo-managed HA reconciliation commands
- Not evidenced in repo:
  - backup schedule policy
  - backup retention
  - off-box/off-site copy/export
  - restore drill/validation
- Current operating assumption:
  - if a native HA backup exists, restore it first, then rerun repo-managed HA helper commands
  - if no native HA backup exists, rebuild HAOS/bootstrap from repo and expect only repo-managed HA behavior to be recoverable without additional manual work

## Current Implemented Features
- Boiler/TRV orchestration via generated HA scripts + automations.
  - Boiler on-demand includes a periodic reconciliation path so missed template edges after automation reloads self-heal.
- Schedule-driven heating events from `home_assistant.heating_control.schedule_events`.
  - Current repo schedule is limited to morning routines; weekday warmup now begins at `06:50`.
- Hard-off guard windows from `home_assistant.heating_control.hard_off_windows` to suppress stray overnight TRV calls.
- Bedroom weekday sunrise light routine plus temporary holiday evening lighting from `home_assistant.light_routines`.
- Bedroom IKEA remote control for the bedroom Hue bulb from `home_assistant.remote_light_controls`.
- Living room `Heating` IKEA remote boost for selected TRVs from `home_assistant.remote_heating_controls`.
- That boost now uses raw `zha_event` matching for this remote, flashes purple on completion/cancel,
  and restores the living room light/relay state afterward.
- The same behavior is exposed in HA as `script.boost_downstairs` and `script.cancel_boost_downstairs`,
  and the heating dashboard includes buttons for both.
- Bedroom boost is also exposed as `script.boost_bedroom` and `script.cancel_boost_bedroom`,
  with right/left on the living room heating remote mapped to start/cancel.
- The public boost scripts now recover stale runner state by restarting the runner if it is still
  marked `on` but its targets are no longer actually at the boost setpoint.
- Active repo-managed boosts now override repo-managed scheduled `off` events and hard-off windows
  for the boosted TRVs. Manual `script.heating_all_off` and `script.heating_lockout_enable` still win.
- Heating high-target visual alert from `home_assistant.heating_alerts`.
- Boiler idle blue-flash alert is also generated from `home_assistant.heating_alerts`.
- Group target sliders (`house`, `upstairs`, `downstairs`) used by heating automations/dashboard.
- Shelly + TP-Link + selected ZHA device naming/area mapping through `sync-devices`.
- Hue remote scene-cycle automation generated from `home_assistant.hue_scene_cycle`.
  - `trigger_subtype` in repo config drives the generated ZHA event command.
- Heating dashboard uses Mushroom layout and ApexCharts (if installed).

## Known Constraints
- HAOS: HACS install remains manual (cannot be fully automated reliably on appliance image).
- Required frontend cards for current dashboard:
  - Mushroom
  - ApexCharts Card
  - mini-graph-card (optional fallback)
- Some ZHA remote long-press repeat behavior can be device-limited; short-press flows are currently the stable path.

## Guardrails for Future Changes
- Make changes in `config/homelab.yaml` first, then regenerate via script commands above.
- If the changed behavior can be exercised from this environment, test it directly in live HA before
  declaring success. Do not leave first discovery of regressions to the user.
- Re-run `scripts/run.py validate` after HA changes.
- If behavior changes by design, update:
  - `docs/home-assistant.md`
  - `docs/rebuild.md`
  - this handoff doc
