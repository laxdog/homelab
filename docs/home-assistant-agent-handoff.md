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

## Runtime Drift Baseline (2026-03-18)
- Runtime-only entities were observed in live HA during the current audit.
- Current classification:
  - likely intentional but unmanaged:
    - `automation.ad_hoc_*`
    - `automation.office_heat_boost_until_2026_03_09_16_05_utc`
    - `automation.dining_room_remote_*`
  - likely stale residue:
    - `automation.bedroom_weekday_sunrise_2`
    - `automation.living_room_styrbar_*`
    - `scene.heating_high_target_alert_snapshot`
    - `scene.living_room_heating_boost_indicator_snapshot`
    - `automation.ad_hoc_laundry_power_cutoff_until_2026_03_12_11_00_2`
  - definitely unmanaged:
    - `automation.zigbee_living_room_remote_toggle_living_room_light_test`
    - `script.dining_room_remote_boundary_flash`
    - `script.dining_room_remote_hold_brightness_down`
    - `script.dining_room_remote_hold_brightness_up`
  - uncertain and should be confirmed before cleanup:
    - `automation.cancel_bedroom_heating_boost`
    - `automation.cancel_living_room_heating_boost`
    - `automation.holiday_*`
- Working rule:
  - do not delete runtime-only entities until they are either absorbed into repo-managed behavior or confirmed to be stale and unused.

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
- Boosts are now backed by repo-managed HA timers and restore-state helpers created through
  the HAOS bootstrap path, then reconciled by generated HA automations/scripts.
- Desired-state model for boosts:
  - timer = source of truth for whether a boost should still be active
  - restore-state helper = source of truth for the pre-boost TRV state that still needs restoring
  - reconcile automations (`automation.reconcile_living_room_heating_boost`,
    `automation.reconcile_bedroom_heating_boost`) drive the actual TRVs toward that desired state
- Restart/reload recovery for boosts now comes from the timer/helper desired-state model rather
  than from long-running runner scripts surviving in-flight.
- On startup/reload:
  - active timers cause reconcile to re-assert the boost temperature
  - inactive timers with a populated restore helper cause reconcile to keep restoring the saved
    pre-boost state until the targets actually match, then clear the helper
- Migration status:
  - legacy `script.boost_*_runner` scripts are now removed by `sync-remote-heating-controls`
  - `automation.cancel_living_room_heating_boost` and `automation.cancel_bedroom_heating_boost`
    are current repo-managed cancel automations, not legacy residue
  - boost-related snapshot scenes are no longer present in the current runtime snapshot
  - unmanaged boost residue still observed: `automation.office_heat_boost_until_2026_03_09_16_05_utc`
- Validation status from the latest pass:
  - bedroom expiry-while-HA-down recovery was verified directly and reconciled back to `off / 20C`
  - downstairs expiry-while-HA-down exposed the original early-helper-clear bug and drove the
    follow-up fix that keeps helper state authoritative until restore is actually complete
  - repeated HA bootstrap apply is idempotent (`changed=0` on repeat runs)
  - repeated `sync-remote-heating-controls` is now idempotent after handling HA's `400` response
    when a legacy runner script is already gone
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
- If remote heating boost behavior changes, remember that `sync-remote-heating-controls` is only
  half of the rollout; the HAOS-side timer/input_text helpers are created from repo during
  `scripts/run.py guests`.
- If the changed behavior can be exercised from this environment, test it directly in live HA before
  declaring success. Do not leave first discovery of regressions to the user.
- Re-run `scripts/run.py validate` after HA changes.
- If behavior changes by design, update:
  - `docs/home-assistant.md`
  - `docs/rebuild.md`
  - this handoff doc
