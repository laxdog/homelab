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
  - Adds boiler control, lockout controls, group target sliders, apply buttons, and thermostat cards for configured TRVs.
  - Adds a 48h combined TRV temperature graph plus one per-TRV graph card (current vs target) when HACS `mini-graph-card` is installed.
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
  - Creates/updates schedule event automations from `config.home_assistant.heating_control.schedule_events`:
    - `automation.heating_event_*`
  - Demand logic uses TRV `hvac_action == heating`, with fallback to
    `(target - current) >= deadband_c`.
  - Anti-cycling controls are configurable in `config.home_assistant.heating_control`:
    `deadband_c`, `on_for`, `off_for`, `min_on_seconds`, `min_off_seconds`.
  - Current tuning:
    - `deadband_c: 0.5`
    - `on_for: 00:02:00`
    - `off_for: 00:03:00`
    - `min_on_seconds: 180`
    - `min_off_seconds: 300`
  - Semantics:
    - `off_for` = no-demand hold time before boiler off is allowed.
    - `min_on_seconds` = minimum boiler runtime before off is allowed.
    - Effective off timing is the later of those two conditions.
  - This replaces the need for a separate Active Heating Manager add-on for this setup.

## Scheduling
- Schedule is code-defined in `config.home_assistant.heating_control.schedule_events`.
- Each event declares `time`, `weekdays`, `action` (`set_temp` or `"off"`), and `targets`.
- Targets can be explicit climate entities or group names: `house`, `upstairs`, `downstairs`.
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

## Credential reference
- Username: `config.home_assistant.admin_username` (currently `mrobinson`)
- Password variable: `home_assistant_admin_password`
- Proxmox note field (VM metadata) is managed from `config.homelab.yaml` and includes:
  - `ui:mrobinson|home_assistant_admin_password`
  - `ssh:root|root_password`
