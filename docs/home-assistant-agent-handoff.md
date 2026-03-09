# Home Assistant Agent Handoff

## Scope
- Manage Home Assistant VM (`10.20.30.134`) config and automations as IaC.
- Keep source of truth in `config/homelab.yaml` + `scripts/home_assistant.py`.
- Avoid manual UI edits unless explicitly required (HACS installs are still manual on HAOS).

## Source of Truth
- VM + network placement: `config/homelab.yaml` -> `services.vms.home-assistant`
- HA runtime + devices + heating + Hue scene cycle: `config/homelab.yaml` -> `home_assistant`
- Admin password var: `ansible/secrets.yml` -> `home_assistant_admin_password`
- Automation helper script: `scripts/home_assistant.py`

## Access
- Internal URL: `https://ha.laxdog.uk`
- External URL: `https://ha.lax.dog` (through NPM / Authentik policy)
- Direct IP URL: `http://10.20.30.134:8123`

## Standard Commands
- Core config apply:
  - `python3 scripts/home_assistant.py apply-core`
- Device naming/areas:
  - `python3 scripts/home_assistant.py sync-devices`
- TP-Link/Kasa hub integration:
  - `python3 scripts/home_assistant.py add-tplink`
- Heating control automations/scripts:
  - `python3 scripts/home_assistant.py sync-heating-control`
- Heating dashboard:
  - `python3 scripts/home_assistant.py sync-heating-dashboard`
- Hue remote scene cycle automation:
  - `python3 scripts/home_assistant.py sync-hue-scenes`
- Summary/debug:
  - `python3 scripts/home_assistant.py summary`

## Current Implemented Features
- Boiler/TRV orchestration via generated HA scripts + automations.
- Schedule-driven heating events from `home_assistant.heating_control.schedule_events`.
- Group target sliders (`house`, `upstairs`, `downstairs`) used by heating automations/dashboard.
- Shelly + TP-Link + selected ZHA device naming/area mapping through `sync-devices`.
- Hue remote scene-cycle automation generated from `home_assistant.hue_scene_cycle`.
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
- Re-run `scripts/run.py validate` after HA changes.
- If behavior changes by design, update:
  - `docs/home-assistant.md`
  - `docs/rebuild.md`
  - this handoff doc
