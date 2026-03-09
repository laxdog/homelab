# TODO

## Obsidian LiveSync (next session)
- [ ] Recover cross-device sync cleanly using a fresh remote DB path:
  - phone as source of truth
  - rebuild to a new DB name (e.g. `obsidian_main_v2`)
  - re-join desktop with fetch-only path
  - avoid desktop initializer/upload flow until key/profile mismatch is resolved

## Monitoring / Alerts
- [ ] Fix Nagios HTTP check command bug: `check_http` uses `-P` (POST body) instead of `-p` (port) in `ansible/roles/nagios/templates/homelab.cfg.j2`.
- [ ] Re-apply Nagios role and verify `HTTP proxmox.lax.dog` / `HTTP proxmox.laxdog.uk` checks return `OK`.
- [ ] Decide whether `ha.laxdog.uk` should be expected to return `200` via NPM; if yes, fix HA proxy trust config so NPM traffic is accepted.
- [ ] Decide whether prod raffle-raptor should expose `/statusz`; if no, disable that specific statusz check to remove false CRITs.

## Home Assistant / Heating
- [ ] Evaluate calendar-driven heating schedule option (Google Calendar-backed triggers with repo-managed automation logic).
- [ ] Consider replacing custom TRV orchestration with Better Thermostat + UI card after a 1-room pilot.

## Home Assistant / Battery UX
- [ ] Evaluate and install **Battery Notes** HACS integration for device battery metadata + maintenance workflow:
  - tracks battery type, last replaced date, low/not-reported conditions, and exposes events/actions for automations.
  - supports Battery+ style entities and templates for devices that only expose voltage/binary/text battery signals.
  - useful follow-up: add automation to mark battery replaced on battery-increase events.
- [ ] Add **Auto-Entities** card for “only low battery” devices (dynamic list, no manual entity maintenance):
  - include `sensor` entities with `device_class: battery` and numeric `state <= threshold` (e.g. `<= 20`).
  - exclude `unknown` / `unavailable`.
  - sort ascending by numeric state so critical devices appear first.
  - show on main dashboard + optionally on heating/dashboard page.
