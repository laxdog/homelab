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
- Repo-evidenced:
  - HAOS bootstrap/onboarding path
  - reverse-proxy trust enforcement
  - repo-managed HA reconciliation commands
  - repo-managed boost timers/helpers written into HAOS `configuration.yaml`
- Runtime-evidenced:
  - HA `backup` integration is loaded
  - HA exposes backup service `backup.create_automatic`
  - backup entities exist:
    - `event.backup_automatic_backup`
    - `sensor.backup_next_scheduled_automatic_backup`
    - `sensor.backup_last_successful_automatic_backup`
    - `sensor.backup_last_attempted_automatic_backup`
- Not established from runtime checks:
  - whether automatic backup scheduling is actually configured and working
  - backup retention
  - off-box/off-site export/copy
  - successful restore history
- Current entity state observed during the audit:
  - all of the backup status sensors/events above were `unknown`
- Practical recovery rule:
  - if a native HA backup exists, restore it first, then rerun repo-managed HA helper commands
  - if no native HA backup exists, rebuild HAOS/bootstrap from repo and expect only repo-managed HA behavior to be recoverable without additional manual work
- Confidence boundary:
  - repo-managed HA recovery confidence is decent
  - full HA runtime recovery confidence is still limited by missing backup-policy and restore-drill evidence

## Runtime Drift Baseline (2026-03-18)
- Runtime-only entities were observed in live HA during the current audit.
- Removed in the conservative cleanup slice:
  - `automation.zigbee_living_room_remote_toggle_living_room_light_test`
  - `automation.living_room_styrbar_*`
  - `automation.ad_hoc_laundry_power_cutoff_until_2026_03_12_11_00_2`
  - `automation.bedroom_weekday_sunrise_2`
- Current classification:
  - leave alone for now, but document as unmanaged history:
    - `automation.ad_hoc_*`
    - `automation.office_heat_boost_until_2026_03_09_16_05_utc`
  - likely intentional but unmanaged, and still active enough to need confirmation:
    - `automation.dining_room_remote_*`
  - definitely unmanaged scripts left alone because they are still coupled to the active unmanaged dining-room remote family:
    - `script.dining_room_remote_boundary_flash`
    - `script.dining_room_remote_hold_brightness_down`
    - `script.dining_room_remote_hold_brightness_up`
  - current repo-managed aliases, not drift:
    - `automation.cancel_bedroom_heating_boost`
    - `automation.cancel_living_room_heating_boost`
    - `automation.holiday_*`
  - no longer present in the current runtime snapshot:
    - `scene.heating_high_target_alert_snapshot`
    - `scene.living_room_heating_boost_indicator_snapshot`
- Working rule:
  - do not delete runtime-only entities until they are either absorbed into repo-managed behavior or confirmed to be stale and unused.
  - `docs/rebuild.md` still needs separate alignment later once unrelated worktree edits are out of the way.

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
  - downstairs also has a startup-only fail-safe branch enabled by
    `fail_safe_off_on_uncertain_restore: true`
  - reconcile automations (`automation.reconcile_living_room_heating_boost`,
    `automation.reconcile_bedroom_heating_boost`) drive the actual TRVs toward that desired state
- Restart/reload recovery for boosts now comes from the timer/helper desired-state model rather
  than from long-running runner scripts surviving in-flight.
- On startup/reload:
  - active timers cause reconcile to re-assert the boost temperature
  - inactive timers with a populated restore helper cause reconcile to keep restoring the saved
    pre-boost state until the targets actually match, then clear the helper
  - downstairs only: if HA starts with the timer inactive, the restore helper empty, and all three
    downstairs targets still at the boost setpoint, reconcile fails safe to `off`
- Migration status:
  - legacy `script.boost_*_runner` scripts are now removed by `sync-remote-heating-controls`
  - `automation.cancel_living_room_heating_boost` and `automation.cancel_bedroom_heating_boost`
    are current repo-managed cancel automations, not legacy residue
  - boost-related snapshot scenes are no longer present in the current runtime snapshot
  - unmanaged boost residue still observed: `automation.office_heat_boost_until_2026_03_09_16_05_utc`
  - if `timer.boost_downstairs_restore_guard` appears as `unavailable`, treat it as stale runtime
    residue from the abandoned guard-timer experiment, not as current repo-managed behavior
- Validation status from the latest pass:
  - bedroom expiry-while-HA-down recovery was verified directly and reconciled back to `off / 20C`
  - downstairs expiry-while-HA-down was rerun cleanly on `2026-03-19` and the narrower fail-safe now covers it:
    - timer comes back `idle`
    - downstairs restore helper comes back empty
    - `front_window`, `dining_area`, and `bathroom` reconcile to `off`
  - direct probe showed the root cause:
    - the YAML-defined downstairs restore helper does not retain its value across a full HA VM restart
  - practical status:
    - bedroom proof is strong
    - downstairs no longer relies on exact restore in that uncertain startup case; it now fails safe to `off`
    - normal downstairs `heat / 20C` restore while HA stays up was revalidated
    - ordinary manual downstairs heating still worked after the fail-safe fired
  - repeated HA bootstrap apply is idempotent (`changed=0` on repeat runs)
  - repeated `sync-remote-heating-controls` is now idempotent after handling HA's `400` response
    when a legacy runner script is already gone
- Active repo-managed boosts now override repo-managed scheduled `off` events and hard-off windows
  for the boosted TRVs. Manual `script.heating_all_off` and `script.heating_lockout_enable` still win.
- Downstairs/bedroom boost reconcile now relies on startup, timer-finished, helper-change, and
  1-minute fallback triggers only. It no longer self-triggers on target TRV state changes, which
  avoids restore loops when a stale helper collides with live TRV state.
- Heating high-target visual alert from `home_assistant.heating_alerts`.
- Boiler idle blue-flash alert is also generated from `home_assistant.heating_alerts`.
- Group target sliders (`house`, `upstairs`, `downstairs`) used by heating automations/dashboard.
- Shelly + TP-Link + selected ZHA device naming/area mapping through `sync-devices`.
- Hue remote scene-cycle automation generated from `home_assistant.hue_scene_cycle`.
  - `trigger_subtype` in repo config drives the generated ZHA event command.
- Heating dashboard uses Mushroom layout and ApexCharts (if installed).
- Heating dashboard review concepts now exist side by side on the same Lovelace dashboard:
  - `overview` = existing baseline page kept intact
  - `hybrid-a` = operational / summary-first hybrid
  - `hybrid-b` = dense desktop-first room-control hybrid
  - `hybrid-c` = mobile-first hybrid
  - `hybrid-d` = supported rich-panel substitute for `better-thermostat-ui-card`
  - dashboard tab labels are currently shortened to `Heating`, `A`, `B`, `C`, `D`
    so all concept pages remain reachable on narrower screens and kiosk browsers
- Current UI recommendation:
  - best overall starting point: `hybrid-a`
  - best mobile-specific concept: `hybrid-c`
  - best room-adjustment concept: `hybrid-b`
- Card dependency stance for these concept views:
  - use the cards already installed in HA (`lovelace-mushroom`, `mini-graph-card`, `apexcharts-card` when present)
  - repo-managed local card assets are now staged into HA `/local/repo-managed-cards/` by the
    bootstrap role for:
    - `simple-thermostat`
    - `mini-climate-card`
  - do not use `better-thermostat-ui-card` with the current `tplink` climate entities; it is a
    `better_thermostat` companion card, not a generic climate card

## Known Constraints
- HAOS: HACS install remains manual (cannot be fully automated reliably on appliance image).
- Required frontend cards for current dashboard:
  - Mushroom
  - ApexCharts Card
  - mini-graph-card (optional fallback)
- Some ZHA remote long-press repeat behavior can be device-limited; short-press flows are currently the stable path.
- Fully Kiosk Browser:
  - not integrated in HA yet
  - no `fully_kiosk` config entry, device, or entities were present in the latest runtime check
  - when picked up again, use the official HA Fully Kiosk Browser integration rather than an old custom approach
  - sensible first slice:
    - add the tablet to HA
    - confirm status entities
    - confirm `screen on` / `screen off`
    - confirm dashboard `load_url`
    - defer motion/screen-wake automation until the base integration is stable

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
