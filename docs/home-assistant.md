# Home Assistant

Source of truth:
- `config/homelab.yaml` -> `services.vms.home-assistant`, `home_assistant`
- `ansible/secrets.yml` -> `home_assistant_admin_password`

## Bootstrap behavior
- HAOS VM is provisioned by Terraform.
- HAOS disk image is imported only when the target VM disk has no partition table
  (prevents destructive re-image on repeated applies).
- During `scripts/run.py guests`, role `home-assistant-bootstrap` checks `/api/onboarding`.
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

## Access
- Internal: `https://ha.laxdog.uk`
- External: `https://ha.lax.dog` (behind NPM/Authentik policy)

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
  - Adds boiler control, schedule/override status, lockout controls, override controls, and thermostat cards for configured TRVs.
  - Lockout actions are available directly on this heating page:
    - `Enable Lockout` (disables auto-heating + turns boiler off)
    - `Disable Lockout` (re-enables auto-heating)
  - Override actions are available directly on this heating page:
    - `Enable Override` (allow heating outside schedule windows)
    - `Disable Override` (return to schedule control)
    - `Boost 1 Hour` (temporary override for one hour)
  - Current URL path is `/<dashboard_url_path>/<view_path>` (default `/heating-overview/overview`).
  - Supports `style: mushroom` (HACS Mushroom cards) or `style: default`.
  - `style: mushroom` requires HACS + Mushroom to already be installed in Home Assistant.
- `python3 scripts/home_assistant.py sync-heating-control`
  - Creates/updates five HA scripts:
    - `script.heating_lockout_enable`
    - `script.heating_lockout_disable`
    - `script.heating_override_enable`
    - `script.heating_override_disable`
    - `script.heating_override_boost_1h`
  - Creates/updates five HA automations:
    - `automation.heating_schedule_gate`
    - `automation.heating_override_gate`
    - `automation.heating_boiler_on_demand`
    - `automation.heating_boiler_off_when_satisfied`
    - `automation.heating_boiler_off_outside_schedule`
  - Creates schedule window automations from `config.home_assistant.heating_control.schedule`:
    - `automation.heating_schedule_start_*`
    - `automation.heating_schedule_end_*`
  - Schedule window automations are preserved if they already exist so they can be edited in HA UI without Git changes.
  - Demand logic uses TRV `hvac_action == heating`, with fallback to
    `(target - current) >= deadband_c`.
  - Boiler-on automation runs when schedule gate is on, or manual override is on.
  - Boiler-off automation enforces shutdown outside schedule windows.
  - Anti-cycling controls are configurable in `config.home_assistant.heating_control`:
    `deadband_c`, `on_for`, `off_for`, `schedule_off_for`, `min_on_seconds`, `min_off_seconds`.
  - This replaces the need for a separate Active Heating Manager add-on for this setup.

## UI schedule control
- After initial sync, schedule windows can be edited in Home Assistant UI without repo changes:
  - `Settings -> Automations & Scenes`
  - Edit `Heating Schedule Start - ...` and `Heating Schedule End - ...` automations.
- Schedule automations are only auto-created when missing; rerunning sync preserves existing UI-edited window automations.
- Use Heating dashboard actions for ad-hoc control:
  - `Enable Override`, `Disable Override`, `Boost 1 Hour`
  - `Enable Lockout`, `Disable Lockout`
- `python3 scripts/home_assistant.py summary`
  - Prints current HA config, integration entries, and unavailable entities.

## Device mapping (in code)
- Shelly device naming/areas are defined in `config.home_assistant.device_overrides`.
- Current mappings:
  - `E4B32329D38C` -> `Living Room Light` in `Living Room`
  - `78EE4CC4B590` -> `Gas Boiler` in `Alleyway`
- TP-Link hub target is defined in `config.home_assistant.tplink.hubs`:
  - `KH100 Hub` at `10.20.30.55` (`9c:53:22:14:a4:01`)

## Credential reference
- Username: `config.home_assistant.admin_username` (currently `mrobinson`)
- Password variable: `home_assistant_admin_password`
- Proxmox note field (VM metadata) is managed from `config.homelab.yaml` and includes:
  - `ui:mrobinson|home_assistant_admin_password`
  - `ssh:root|root_password`
