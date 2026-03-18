# Home Assistant

Source of truth:
- `config/homelab.yaml` -> `services.vms.home-assistant`, `home_assistant`
- `ansible/secrets.yml` -> `home_assistant_admin_password`

## Repo vs Runtime Boundary
- The repo is the source of truth for:
  - HAOS VM provisioning/bootstrap
  - HA core config applied by repo helpers
  - device naming/areas from `device_overrides`
  - generated heating automations/scripts/dashboard
  - generated light routines, Hue scene cycling, and repo-managed remote bindings
- The repo does not by itself guarantee the full live HA runtime state.
- Runtime state may also include:
  - manual HACS/frontend-card installs
  - manually created helpers
  - unmanaged or historical automations/scripts/scenes
  - recorder/history/logbook data
  - integration-local state and storage inside HAOS
- After a rebuild or restore, re-running the repo helpers should be treated as reconciling repo-managed HA behavior back into the instance, not as proof that every live/runtime artifact is recreated.

## Bootstrap behavior
- HAOS VM is provisioned by Terraform.
- HAOS disk image is imported only when the target VM disk has no partition table
  (prevents destructive re-image on repeated applies).
- During `scripts/run.py guests`, role `home-assistant-bootstrap` checks `/api/onboarding`.
- The same role enforces reverse-proxy trust in HAOS `configuration.yaml` from
  `config.home_assistant.http`:
  - `use_x_forwarded_for`
  - `trusted_proxies`
  This prevents `400 Bad Request` behind NPM after rebuilds.
- If onboarding is not complete, it creates the initial owner user via API.
- The same role also completes onboarding steps from `config/homelab.yaml`:
  - `core_config` (location, coordinates, elevation, units, timezone, currency)
  - `analytics` (enabled/disabled)
  - `integration`
- If onboarding is already complete, no onboarding data is changed.
- Shelly devices listed in `config.home_assistant.shelly_devices` are configured
  via Home Assistant config-entry flow during `scripts/run.py guests`.
  Re-runs are idempotent (`already_configured` is treated as no-change).
- HACS is not installed by automation on HAOS; treat it as a one-time manual
  bootstrap step. After HACS + Mushroom are installed, dashboard layout is
  managed from repo via `scripts/home_assistant.py sync-heating-dashboard`.
  For current dashboard/graph setup also install:
  - `ApexCharts Card` (HACS frontend)
  - `mini-graph-card` (optional fallback)

## Access
- Internal: `https://ha.laxdog.uk`
- External: `https://ha.lax.dog` (behind NPM/Authentik policy)
- Proxy trust source-of-truth: `config.home_assistant.http.trusted_proxies`
  (defaults to the NPM LXC IP if omitted).

## Backup And Recovery
### What The Repo Gives You
- Repo-evidenced:
  - HAOS VM provisioning/bootstrap
  - onboarding user + core onboarding config
  - reverse-proxy trust in HAOS `configuration.yaml`
  - Shelly config-entry bootstrap
  - repo-managed timers / helpers for heating boosts
  - repo-managed device naming/areas
  - repo-managed automations/scripts/dashboards/light routines/remote bindings from `scripts/home_assistant.py`
- Practical meaning:
  - the repo can rebuild and reconcile the Home Assistant platform and the repo-owned HA behavior
  - the repo is not, by itself, a full-fidelity backup of all HA runtime state

### What The Repo Does Not Give You By Itself
- Not evidenced in repo:
  - native HA backup schedule configuration
  - backup retention policy
  - off-box or off-site backup export/copy
  - restore drill / restore validation history
- Repo-only rebuild should not be assumed to restore:
  - HACS itself or HACS-installed frontend cards until reinstalled
  - manually created helpers beyond what the repo explicitly writes
  - unmanaged runtime-only automations/scripts/scenes
  - integration-local runtime state stored only inside HA
  - recorder/history/logbook data

### Current Backup Evidence
- Backup creation capability:
  - runtime-evidenced
  - evidence:
    - HA `backup` integration is loaded
    - HA service domain `backup` exists with `create_automatic`
- Backup schedule:
  - not established from runtime checks
  - evidence:
    - `sensor.backup_next_scheduled_automatic_backup` exists but is currently `unknown`
- Backup retention:
  - not evidenced in repo
  - not established from runtime checks
- Off-box / off-site copies:
  - not evidenced in repo
  - not established from runtime checks
- Backup success / last run metadata:
  - runtime-evidenced only in a limited sense
  - evidence:
    - `sensor.backup_last_successful_automatic_backup` exists but is currently `unknown`
    - `sensor.backup_last_attempted_automatic_backup` exists but is currently `unknown`
    - `event.backup_automatic_backup` exists but is currently `unknown`
- Restore procedure:
  - partially repo-evidenced
  - evidence:
    - `docs/rebuild.md` documents HAOS bootstrap and repo re-apply steps
  - not evidenced:
    - a documented native HA backup restore walkthrough
    - restore validation / drill records

### Repo-Managed vs Runtime-Managed Recovery Boundary
- Repo-managed recovery:
  - `scripts/run.py guests` and the HA bootstrap role recover the HAOS-side platform wiring that the repo owns
  - `scripts/home_assistant.py` commands recover the repo-managed HA behavior layer
- Runtime-managed recovery:
  - anything only present in HA runtime storage, UI state, or native backups still depends on HA itself or manual recreation
- Practical boundary:
  - restoring an HA backup, if one exists, should be treated as restoring HA runtime state first
  - rerunning repo helpers after that should be treated as reconciling repo-owned intent back onto the instance

### Practical Recovery Sequence
- If a usable native HA backup exists:
  1. Restore the HA backup through Home Assistant / HAOS.
  2. Confirm HA is reachable again.
  3. Re-run the repo-managed HA reconciliation path:
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
  4. Manually confirm HACS/frontend-card availability if dashboards depend on them.
- If no usable native HA backup exists:
  1. Follow the HAOS/bootstrap path in `docs/rebuild.md`.
  2. Reinstall HACS + required frontend cards manually.
  3. Run the same repo-managed HA reconciliation commands listed above.
  4. Manually recreate anything still needed that is not repo-managed.

### Current Gaps / Risks
- Unknowns:
  - whether automatic backups are actually scheduled and working
  - how many backups are retained
  - whether backups are copied anywhere off-box/off-site
  - whether restore has been tested end-to-end
- Operational risk:
  - current recovery confidence is good for repo-managed HA behavior, but not strong for full HA runtime recovery
- Follow-up verification candidates:
  - confirm whether HA automatic backups are intentionally enabled
  - record retention/copy/export policy if one exists
  - perform or document a restore drill

## Runtime Drift Snapshot (2026-03-18)
- Runtime-only entities observed during the current audit should be treated as one of:
  - definitely unmanaged: no corresponding repo config or generator path exists
  - likely stale residue: looks like an old/generated duplicate or snapshot left behind by previous behavior
  - likely intentional but unmanaged: appears to be a real one-off/manual runtime automation, but not repo-driven
  - current repo-managed alias: runtime entity ID differs from the repo `automation_entity`, but the underlying HA config ID matches repo intent
- Current runtime-only entity families and recommendation:
  - leave alone for now, but document as unmanaged history:
    - `automation.ad_hoc_heating_2026_03_11_18_00`
    - `automation.ad_hoc_heating_2026_03_11_21_30_dining_front_restore`
    - `automation.ad_hoc_laundry_power_cutoff_until_2026_03_12_11_00`
    - `automation.ad_hoc_shield_turn_off_2026_03_17_01_42`
    - `automation.office_heat_boost_until_2026_03_09_16_05_utc`
    - recommendation: document only; remove later if these one-off runtime automations are no longer needed for audit/history
  - likely stale; remove later once you want cleanup:
    - `automation.ad_hoc_laundry_power_cutoff_until_2026_03_12_11_00_2`
    - `automation.bedroom_weekday_sunrise_2`
    - `automation.living_room_styrbar_*`
    - recommendation: remove later
  - definitely unmanaged test/manual helpers; remove later:
    - `automation.zigbee_living_room_remote_toggle_living_room_light_test`
    - `script.dining_room_remote_boundary_flash`
    - `script.dining_room_remote_hold_brightness_down`
    - `script.dining_room_remote_hold_brightness_up`
    - recommendation: remove later unless you decide to absorb the dining-room remote behavior instead
  - likely intentional but unmanaged, and still active enough to need confirmation:
    - `automation.dining_room_remote_*`
    - recommendation: needs confirmation, then either absorb into repo or deliberately leave unmanaged
  - current repo-managed aliases, not drift:
    - `automation.holiday_living_room_evening`
    - `automation.holiday_dining_area_evening`
    - `automation.cancel_living_room_heating_boost`
    - `automation.cancel_bedroom_heating_boost`
    - recommendation: leave alone
  - runtime-only families no longer present in the current snapshot:
    - `scene.heating_high_target_alert_snapshot`
    - `scene.living_room_heating_boost_indicator_snapshot`
    - recommendation: no action needed unless they reappear
- Operational stance:
  - do not delete runtime-only entities casually
  - confirm whether a runtime-only entity is still referenced by real behavior before removing it
  - prefer absorbing still-needed behavior into repo-managed config/scripts before cleanup
  - treat duplicate-looking generated entities as cleanup candidates only after confirming the current repo-managed replacement is live and behaving correctly

## Automation helpers
- `python3 scripts/home_assistant.py apply-core`
  - Applies core runtime config (location name, coordinates, unit system, timezone, currency) to an already-onboarded HA instance.
- `python3 scripts/home_assistant.py sync-devices`
  - Applies `config.home_assistant.device_overrides` (device names and areas).
  - Shelly entries also apply entity naming conventions (switch/sensor/update/button labels).
- `python3 scripts/home_assistant.py add-tplink`
  - Attempts TP-Link integration for `config.home_assistant.tplink.hubs`.
  - Requires vault vars referenced by `config.home_assistant.tplink.username_var` and `config.home_assistant.tplink.password_var`.
- `python3 scripts/home_assistant.py sync-heating-dashboard`
  - Ensures a dedicated Heating dashboard exists in Lovelace using `config.home_assistant.heating_dashboard`.
  - Uses a panel-width dashboard layout to maximize horizontal space usage.
  - Adds boiler control, lockout controls, group target sliders, apply buttons, and thermostat cards for configured TRVs.
  - Adds a 48h combined TRV temperature graph plus one per-TRV graph card (current vs target, 12h window) when HACS `mini-graph-card` is installed.
  - If HACS `apexcharts-card` is installed, per-TRV graphs use ApexCharts with a smooth `Current` line and stepline `Target`.
  - If `mini-graph-card` is not installed, a reminder card is shown instead.
  - Lockout actions are available directly on this heating page:
    - `Enable Lockout` (disables auto-heating + turns boiler off)
    - `Disable Lockout` (re-enables auto-heating)
  - Group controls are available directly on this heating page:
    - `House Target` slider
    - `Upstairs Target` slider
    - `Downstairs Target` slider
  - Slider changes auto-apply to mapped TRV groups with a short `1s` settle delay.
  - Some TRVs can take several seconds before the new setpoint is reflected in entity state.
  - Current URL path is `/<dashboard_url_path>/<view_path>` (default `/heating-overview/overview`).
  - Supports `style: mushroom` (HACS Mushroom cards) or `style: default`.
  - `style: mushroom` requires HACS + Mushroom to already be installed in Home Assistant.
- `python3 scripts/home_assistant.py sync-heating-control`
  - Creates/updates six HA scripts:
    - `script.heating_lockout_enable`
    - `script.heating_lockout_disable`
    - `script.heating_set_house_temp`
    - `script.heating_set_upstairs_temp`
    - `script.heating_set_downstairs_temp`
    - `script.heating_all_off`
  - Creates/updates boiler control automations:
    - `automation.heating_boiler_on_demand`
    - `automation.heating_boiler_off_when_satisfied`
    - `automation.heating_enforce_hard_off_window` (when `hard_off_windows` are configured)
  - Creates/updates schedule event automations from `config.home_assistant.heating_control.schedule_events`:
    - `automation.heating_event_*`
  - Demand logic uses TRV `hvac_action == heating` only while a valve is still below target
    (`hvac_action_max_above_target_c` tolerance), with fallback to `(target - current) >= deadband_c`.
  - Anti-cycling controls are configurable in `config.home_assistant.heating_control`:
    `deadband_c`, `hvac_action_max_above_target_c`, `on_for`, `off_for`, `min_on_seconds`,
    `min_off_seconds`, `hard_off_windows`.
  - Current tuning:
    - `deadband_c: 0.5`
    - `hvac_action_max_above_target_c: 0.0`
    - `on_for: 00:02:00`
    - `off_for: 00:03:00`
    - `min_on_seconds: 180`
    - `min_off_seconds: 300`
  - Semantics:
    - Boiler on-demand uses both template edge detection and a `time_pattern` fallback reconciliation,
      so missed demand edges after reloads recover automatically.
    - `off_for` = no-demand hold time before boiler off is allowed.
    - `min_on_seconds` = minimum boiler runtime before off is allowed.
    - Effective off timing is the later of those two conditions.
    - `hard_off_windows` = forced-off windows that turn configured TRVs and the boiler back off
      if device-side schedules or manual changes bring them on unexpectedly.
  - This replaces the need for a separate Active Heating Manager add-on for this setup.
- `python3 scripts/home_assistant.py sync-light-routines`
  - Creates/updates repo-managed light automations from `config.home_assistant.light_routines`.
  - Supports both sunrise ramps and fixed on/off windows, including temporary date-bounded schedules.
  - Current repo-managed light routine is a weekday `Bedroom Weekday Sunrise` that starts at `08:35:55`
    and reaches full brightness at `08:45:55`.
  - The bedroom sunrise currently uses an explicit RGB sunrise palette rather than a pure color-temperature ramp.
  - Current temporary holiday lighting runs the living room and dining area lights from `18:30` until `00:00`
    each night from Wednesday, March 11, 2026 through Monday, March 16, 2026.
- `python3 scripts/home_assistant.py sync-hue-scenes`
  - Creates/updates a ZHA automation (`config.home_assistant.hue_scene_cycle.automation_entity`)
    to cycle scenes from the Hue remote button.
  - Reads remote IEEE + light target + scenes from `config.home_assistant.hue_scene_cycle`.
  - `trigger_subtype` is honored when generating the ZHA event trigger.
  - Accepts direct ZHA event commands such as `off_short_release`, or shorthand values
    `turn_off` / `turn_on` which map to `off_short_release` / `on_short_release`.
- `python3 scripts/home_assistant.py sync-remote-light-controls`
  - Creates/updates repo-managed ZHA remote automations from
    `config.home_assistant.remote_light_controls`.
  - Current bedroom remote behavior:
    - middle/top short press both map to the same ZHA `on` event, so both toggle the bedroom Hue bulb
      full warm / full off
    - bottom short press sets the bedroom Hue bulb to 30% brightness
    - long press up/down adjusts brightness in 10% steps
    - left/right short press cycle scenes backward/forward
- `python3 scripts/home_assistant.py sync-remote-heating-controls`
  - Creates/updates repo-managed ZHA remote heating automations from
    `config.home_assistant.remote_heating_controls`.
  - Each remote heating control also relies on a repo-managed HA timer and restore-state helper:
    - `timer.<script_entity object id>`
    - `input_text.<script_entity object id>_restore_state`
  - Those helpers are created from repo during `scripts/run.py guests`, not by the sync command itself.
  - Desired-state model:
    - the timer is the source of truth for whether a boost should still be active
    - the restore-state helper is the source of truth for the pre-boost TRV modes/setpoints that still need to be restored
    - “desired state” means:
      - while the timer is active, the target TRVs should be at the configured boost temperature in `heat` mode
      - while the timer is inactive but the helper is still populated, the target TRVs should be driven back to the saved pre-boost state
  - Reconciliation model:
    - `automation.reconcile_living_room_heating_boost`
    - `automation.reconcile_bedroom_heating_boost`
    - these run on HA startup, timer-finished events, helper changes, target state changes, and a 1-minute periodic fallback
    - on startup/reload:
      - if the timer is still active, reconcile re-applies the boost state
      - if the timer is inactive but the helper is populated, reconcile keeps trying to restore the saved pre-boost state until the targets actually match it, then clears the helper
  - Current living room `Heating` remote behavior:
    - top short press runs `script.boost_downstairs`, which boosts `Front Window`,
      `Dining Area`, and `Bathroom` to `23C` for 30 minutes, then restores their
      previous modes/setpoints
    - bottom short press runs `script.cancel_boost_downstairs`, which cancels the
      boost and restores the saved pre-boost modes/setpoints immediately
    - right short press runs `script.boost_bedroom`, which boosts `Bedroom` to `23C`
      for 30 minutes, then restores its previous mode/setpoint
    - left short press runs `script.cancel_boost_bedroom`, which cancels the bedroom
      boost and restores the saved pre-boost mode/setpoint immediately
    - active boosts are now modeled as desired state plus a restore-enabled HA timer,
      not as long-running runner scripts waiting in-flight
    - while a boost timer is active, a reconciliation automation keeps the target TRVs
      at their boost setpoint even after automation reloads or HA restart
    - when HA starts and a boost timer is still active, the reconcile automation
      re-applies the boost state from the timer/helper model
    - when a boost timer has ended but the restore-state helper is still populated,
      the reconcile automation restores the pre-boost TRV modes/setpoints and only clears the helper
      after the targets actually match the saved state
    - re-pressing an already-running boost extends it by another 30 minutes and flashes the
      living room Hue bulb red twice quickly
    - when the boost ends or is cancelled, the living room Hue bulb flashes purple once and
      then returns to its prior light/relay state
  - Migration / cleanup status for the old model:
    - old runner scripts:
      - `script.boost_downstairs_runner`: removed by the sync command if present
      - `script.boost_bedroom_runner`: removed by the sync command if present
    - old cancel automations:
      - `automation.cancel_living_room_heating_boost`
      - `automation.cancel_bedroom_heating_boost`
      - these are current repo-managed cancel automations, not legacy residue; their runtime entity IDs come from HA alias naming while the underlying config IDs remain `*_cancel`
    - snapshot scenes:
      - `scene.heating_high_target_alert_snapshot`: not present in current runtime snapshot
      - `scene.living_room_heating_boost_indicator_snapshot`: not present in current runtime snapshot
    - remaining runtime-only boost residue:
      - `automation.office_heat_boost_until_2026_03_09_16_05_utc` is still unmanaged runtime history and still needs separate cleanup if it is no longer wanted
  - Validation notes from the current migration pass:
    - Bedroom hardest restart case was verified directly:
      - start boost
      - shorten the timer to `15s`
      - stop the HA VM for `25s`
      - start HA again
      - observed result: `timer.boost_bedroom` returned `idle`, `input_text.boost_bedroom_restore_state` cleared, and `climate.bedroom_2` reconciled back to `off / 20C`
    - Downstairs hardest restart case exposed the original migration bug:
      - before the follow-up fix, `timer.boost_downstairs` could return idle after HA downtime while the helper cleared too early and the TRVs stayed at `23C`
      - the follow-up fix keeps the helper authoritative until the saved pre-boost state has actually been restored
    - Idempotence checks completed:
      - repeated `scripts/run.py guests` HA bootstrap applies completed with `changed=0`
      - repeated `sync-remote-heating-controls` now succeeds after accepting HA’s `400` response when a legacy runner script has already been deleted
    - this remote currently uses raw `zha_event` matching (`attribute_updated` on `on_off`)
      instead of the higher-level ZHA device trigger, because that proved more reliable here
- `python3 scripts/home_assistant.py sync-heating-alerts`
  - Creates/updates repo-managed heating alert automations from
    `config.home_assistant.heating_alerts`.
  - Current heating alert behavior:
    - when any managed TRV target reaches `23C`, the living room Shelly relay is turned on if needed,
      the living room Hue bulb flashes red once, and the prior relay/light state is restored afterward
    - when the boiler actually transitions from `on` to `off`, the living room Hue bulb flashes
      blue once and the prior relay/light state is restored afterward

## Scheduling
- Schedule is code-defined in `config.home_assistant.heating_control.schedule_events`.
- Each event declares `time`, `weekdays`, `action` (`set_temp` or `"off"`), and `targets`.
- Targets can be explicit climate entities or group names: `house`, `upstairs`, `downstairs`.
- Current repo schedule is intentionally minimal: weekday morning warmup/off and weekend morning on/off.
- Current weekday warmup begins at `06:50` for `Bedroom`, `Bathroom`, `Dining Area`, and `Front Window`.
- Overnight protection is code-defined in `config.home_assistant.heating_control.hard_off_windows`.
- Active repo-managed boosts (`script.boost_downstairs`, `script.boost_bedroom`) now override the
  scheduled `off` events and hard-off windows for their own target TRVs until the boost ends or is cancelled.
- Manual `script.heating_all_off` and `script.heating_lockout_enable` remain authoritative and still
  cut heating immediately.
- Bedroom sunrise lighting is code-defined in `config.home_assistant.light_routines`.
- Bedroom remote-to-light controls are code-defined in `config.home_assistant.remote_light_controls`.
- Remote-triggered heating boosts are code-defined in `config.home_assistant.remote_heating_controls`.
- Reusable downstairs boost scripts are `script.boost_downstairs` and `script.cancel_boost_downstairs`.
- Reusable bedroom boost scripts are `script.boost_bedroom` and `script.cancel_boost_bedroom`.
- Heating visual alerts are code-defined in `config.home_assistant.heating_alerts`.
- Temporary holiday lighting windows are also code-defined in `config.home_assistant.light_routines`.
- For ad-hoc changes outside schedule, use:
  - per-room thermostat cards
  - group target sliders + apply buttons on the Heating page
  - lockout buttons for maintenance/holiday behavior

## Helper Requirements
- The heating dashboard expects these HA helpers to exist:
  - `input_number.house_target`
  - `input_number.upstairs_target`
  - `input_number.downstairs_target`
- They are manually created once in HA UI (`Settings -> Devices & services -> Helpers`) and then referenced by `config.home_assistant.heating_dashboard.temp_helpers`.
- `python3 scripts/home_assistant.py summary`
  - Prints current HA config, integration entries, and unavailable entities.

## Device mapping (in code)
- Shelly device naming/areas are defined in `config.home_assistant.device_overrides`.
- Current mappings:
  - `E4B32329D38C` -> `Living Room Light` in `Living Room`
  - `78EE4CC4B590` -> `Gas Boiler` in `Alleyway`
- TP-Link hub target is defined in `config.home_assistant.tplink.hubs`:
  - `KH100 Hub` at `10.20.30.55` (`9c:53:22:14:a4:01`)
- ZHA devices currently codified in `config.home_assistant.device_overrides` include:
  - Living room Hue bulb
  - Bedroom Hue bulb
  - Hue dimmer remote

## Current operating notes
- Keep TRV scheduling in repo via `config.home_assistant.heating_control.schedule_events`.
- Keep overnight/off-window protection in repo via `config.home_assistant.heating_control.hard_off_windows`.
- For ad-hoc overrides, prefer thermostat cards/group target sliders; avoid per-TRV vendor schedules.
- For HA changes with a reachable live path, test them directly in HA before closing the work.
  Do not rely on the user to discover regressions.
- Repo-managed heating boosts now depend on HAOS `configuration.yaml` sections for `timer` and
  `input_text`; if those helpers drift or disappear, re-run `scripts/run.py guests` before re-syncing
  the HA automations/scripts.
- Long-press dimming repeat behavior on the current Hue remote integration is limited; short-press dim steps are the stable path at present.

## Credential reference
- Username: `config.home_assistant.admin_username` (currently `mrobinson`)
- Password variable: `home_assistant_admin_password`
- Proxmox note field (VM metadata) is managed from `config.homelab.yaml` and includes:
  - `ui:mrobinson|home_assistant_admin_password`
  - `ssh:root|root_password`
