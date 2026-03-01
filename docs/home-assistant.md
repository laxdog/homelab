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
  - Adds boiler control and thermostat cards for configured TRVs.
  - Current URL path is `/<dashboard_url_path>/<view_path>` (default `/heating-overview/overview`).
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
