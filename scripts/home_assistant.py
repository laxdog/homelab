#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
import websocket
import yaml


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with (repo_root() / "config" / "homelab.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def read_vault_var(var_name: str) -> str:
    default_vault = Path.home() / ".ansible_vault_pass"
    if not default_vault.exists():
        raise RuntimeError("Missing ~/.ansible_vault_pass")
    cmd = [
        "ansible",
        "localhost",
        "-c",
        "local",
        "-m",
        "ansible.builtin.debug",
        "-a",
        f"var={var_name}",
        "-e",
        f"@{repo_root() / 'ansible' / 'secrets.yml'}",
        "--vault-password-file",
        str(default_vault),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    match = re.search(rf'"{re.escape(var_name)}":\s*"([^"]+)"', proc.stdout)
    if not match:
        raise RuntimeError(f"Could not read vault var: {var_name}")
    return match.group(1)


def ha_token(base_url: str, username: str, password: str, client_id: str) -> str:
    r = requests.post(
        f"{base_url}/auth/login_flow",
        json={"client_id": client_id, "redirect_uri": client_id, "handler": ["homeassistant", None]},
        timeout=10,
    )
    r.raise_for_status()
    flow_id = r.json()["flow_id"]
    r = requests.post(
        f"{base_url}/auth/login_flow/{flow_id}",
        json={"client_id": client_id, "username": username, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    code = r.json()["result"]
    r = requests.post(
        f"{base_url}/auth/token",
        data={"grant_type": "authorization_code", "code": code, "client_id": client_id},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def ws_call(base_url: str, token: str, message_type: str, **payload: Any) -> Any:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    ws = websocket.create_connection(ws_url, timeout=10)
    try:
        first = json.loads(ws.recv())
        if first.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected websocket pre-auth message: {first}")
        ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"Websocket auth failed: {auth}")
        message = {"id": 1, "type": message_type}
        message.update(payload)
        ws.send(json.dumps(message))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                if not msg.get("success", False):
                    raise RuntimeError(f"{message_type} failed: {msg}")
                return msg.get("result")
    finally:
        ws.close()


def ws_core_update(base_url: str, token: str, payload: dict) -> dict:
    result = ws_call(base_url, token, "config/core/update", **payload)
    return result if isinstance(result, dict) else {}


def ha_auth_from_config() -> Tuple[dict, str, str]:
    cfg = load_config()
    ha_cfg = cfg["home_assistant"]
    base = f"http://{cfg['services']['vms']['home-assistant']['ip']}:8123"
    password = read_vault_var("home_assistant_admin_password")
    token = ha_token(base, ha_cfg["admin_username"], password, ha_cfg["onboarding_client_id"])
    return cfg, base, token


def ensure_area(base_url: str, token: str, area_name: str) -> str:
    areas = ws_call(base_url, token, "config/area_registry/list")
    for area in areas:
        if area.get("name") == area_name:
            return area["area_id"]
    created = ws_call(base_url, token, "config/area_registry/create", name=area_name)
    return created["area_id"]


def shelly_entity_name(base_name: str, entity_id: str) -> str:
    domain = entity_id.split(".", 1)[0]
    object_id = entity_id.split(".", 1)[1]
    if domain == "switch":
        return base_name
    if domain == "binary_sensor" and entity_id.endswith("_input_0"):
        return f"{base_name} Input"
    if domain == "binary_sensor" and entity_id.endswith("_cloud"):
        return f"{base_name} Cloud"
    if domain == "binary_sensor" and entity_id.endswith("_restart_required"):
        return f"{base_name} Restart Required"
    if domain == "button" and entity_id.endswith("_restart"):
        return f"{base_name} Restart"
    if domain == "sensor" and entity_id.endswith("_temperature"):
        return f"{base_name} Temperature"
    if domain == "sensor" and entity_id.endswith("_signal_strength"):
        return f"{base_name} Signal Strength"
    if domain == "sensor" and entity_id.endswith("_last_restart"):
        return f"{base_name} Last Restart"
    if domain == "update" and entity_id.endswith("_firmware"):
        return f"{base_name} Firmware"
    if domain == "update" and entity_id.endswith("_beta_firmware"):
        return f"{base_name} Beta Firmware"
    tail = object_id.split("_")[-1].replace("-", " ").title()
    return f"{base_name} {tail}".strip()


def cmd_apply_core() -> None:
    cfg, base, token = ha_auth_from_config()
    ha_cfg = cfg["home_assistant"]
    headers = {"Authorization": f"Bearer {token}"}

    requests.post(
        f"{base}/api/services/homeassistant/set_location",
        headers=headers,
        json={
            "latitude": ha_cfg["latitude"],
            "longitude": ha_cfg["longitude"],
            "elevation": int(ha_cfg["elevation_m"]),
        },
        timeout=10,
    ).raise_for_status()

    ws_core_update(
        base,
        token,
        {
            "location_name": ha_cfg["location_name"],
            "latitude": ha_cfg["latitude"],
            "longitude": ha_cfg["longitude"],
            "elevation": int(ha_cfg["elevation_m"]),
            "unit_system": ha_cfg["unit_system"],
            "time_zone": ha_cfg["time_zone"],
            "currency": ha_cfg["currency"],
        },
    )

    r = requests.get(f"{base}/api/config", headers=headers, timeout=10)
    r.raise_for_status()
    c = r.json()
    print(
        "Updated HA core config:",
        c.get("location_name"),
        c.get("latitude"),
        c.get("longitude"),
        c.get("elevation"),
        c.get("time_zone"),
    )


def cmd_sync_devices() -> None:
    cfg, base, token = ha_auth_from_config()
    overrides = cfg.get("home_assistant", {}).get("device_overrides", [])
    if not overrides:
        print("No home_assistant.device_overrides configured; nothing to do.")
        return

    devices = ws_call(base, token, "config/device_registry/list")
    entities = ws_call(base, token, "config/entity_registry/list")
    entities_by_device: Dict[str, List[dict]] = {}
    for entity in entities:
        device_id = entity.get("device_id")
        if device_id:
            entities_by_device.setdefault(device_id, []).append(entity)

    changed = 0
    for override in overrides:
        integration = override["integration"]
        identifier = override["identifier"]
        desired_name = override["name"]
        desired_area = override.get("area")

        device = next(
            (
                d
                for d in devices
                if any(
                    pair
                    and len(pair) == 2
                    and pair[0] == integration
                    and str(pair[1]).upper() == str(identifier).upper()
                    for pair in d.get("identifiers", [])
                )
            ),
            None,
        )
        if not device:
            print(f"WARN: no device found for {integration}:{identifier}")
            continue

        update_payload: Dict[str, Any] = {"device_id": device["id"]}
        if desired_area:
            area_id = ensure_area(base, token, desired_area)
            if device.get("area_id") != area_id:
                update_payload["area_id"] = area_id
        if device.get("name_by_user") != desired_name:
            update_payload["name_by_user"] = desired_name

        if len(update_payload) > 1:
            ws_call(base, token, "config/device_registry/update", **update_payload)
            changed += 1
            print(f"Updated device: {desired_name}")
        else:
            print(f"Device already correct: {desired_name}")

        if integration == "shelly":
            for entity in entities_by_device.get(device["id"], []):
                expected_name = shelly_entity_name(desired_name, entity["entity_id"])
                if entity.get("name") != expected_name:
                    ws_call(
                        base,
                        token,
                        "config/entity_registry/update",
                        entity_id=entity["entity_id"],
                        name=expected_name,
                    )
                    changed += 1
                    print(f"Updated entity name: {entity['entity_id']} -> {expected_name}")

    print(f"Device sync complete. Changes applied: {changed}")


def cmd_add_tplink() -> None:
    cfg, base, token = ha_auth_from_config()
    tplink_cfg = cfg.get("home_assistant", {}).get("tplink", {})
    hubs = tplink_cfg.get("hubs", [])
    if not hubs:
        print("No home_assistant.tplink.hubs configured; nothing to do.")
        return

    username_var = tplink_cfg.get("username_var", "tplink_username")
    password_var = tplink_cfg.get("password_var", "tplink_password")
    try:
        username = read_vault_var(username_var)
        password = read_vault_var(password_var)
    except Exception as exc:
        raise RuntimeError(
            f"TP-Link credentials missing. Add vault vars '{username_var}' and '{password_var}'."
        ) from exc

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for hub in hubs:
        hub_name = hub.get("name", hub.get("host", "tplink-hub"))
        host = hub.get("host", "")
        mac = str(hub.get("mac", "")).lower()

        start = requests.post(
            f"{base}/api/config/config_entries/flow",
            headers=headers,
            json={"handler": "tplink", "show_advanced_options": False},
            timeout=20,
        )
        start.raise_for_status()
        flow_id = start.json()["flow_id"]

        step = requests.post(
            f"{base}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"host": host},
            timeout=30,
        )
        step.raise_for_status()
        step_json = step.json()

        if step_json.get("type") == "abort":
            reason = step_json.get("reason", "")
            if reason == "already_configured":
                print(f"TP-Link hub already configured: {hub_name}")
                continue
            raise RuntimeError(f"TP-Link flow aborted for {hub_name}: {step_json}")

        if step_json.get("step_id") == "pick_device":
            options = step_json.get("data_schema", [{}])[0].get("options", [])
            selected = None
            for option in options:
                if not isinstance(option, list) or len(option) != 2:
                    continue
                option_id, option_label = option
                if mac and mac in str(option_id).lower():
                    selected = option_id
                    break
                if host and host in str(option_label):
                    selected = option_id
            if not selected:
                raise RuntimeError(f"Could not match discovered TP-Link device for {hub_name}")
            step = requests.post(
                f"{base}/api/config/config_entries/flow/{flow_id}",
                headers=headers,
                json={"device": selected},
                timeout=30,
            )
            step.raise_for_status()
            step_json = step.json()

        if step_json.get("step_id") == "user_auth_confirm":
            final = requests.post(
                f"{base}/api/config/config_entries/flow/{flow_id}",
                headers=headers,
                json={"username": username, "password": password},
                timeout=30,
            )
            final.raise_for_status()
            result = final.json()
        else:
            result = step_json

        if result.get("type") == "create_entry":
            print(f"Configured TP-Link hub: {hub_name}")
            continue
        if result.get("type") == "abort" and result.get("reason") == "already_configured":
            print(f"TP-Link hub already configured: {hub_name}")
            continue
        raise RuntimeError(f"Unexpected TP-Link flow result for {hub_name}: {result}")


def cmd_summary() -> None:
    cfg, base, token = ha_auth_from_config()
    headers = {"Authorization": f"Bearer {token}"}

    config = requests.get(f"{base}/api/config", headers=headers, timeout=10).json()
    states = requests.get(f"{base}/api/states", headers=headers, timeout=20).json()
    entries = requests.get(f"{base}/api/config/config_entries/entry", headers=headers, timeout=20).json()

    print(
        "Config:",
        f"name={config.get('location_name')}",
        f"lat={config.get('latitude')}",
        f"lon={config.get('longitude')}",
        f"elevation={config.get('elevation')}",
        f"timezone={config.get('time_zone')}",
    )
    print(f"Total entities: {len(states)}")
    counts = Counter(s["entity_id"].split(".")[0] for s in states)
    for domain, count in counts.most_common():
        print(f"- {domain}: {count}")

    print("Unavailable/unknown:")
    bad = [s["entity_id"] for s in states if s.get("state") in {"unavailable", "unknown"}]
    if bad:
        for entity_id in bad:
            print(f"- {entity_id}")
    else:
        print("- none")

    print("Config entries:")
    for entry in entries:
        print(f"- {entry.get('domain')}: {entry.get('title')} ({entry.get('state')})")


def cmd_sync_heating_dashboard() -> None:
    cfg, base, token = ha_auth_from_config()
    dashboard_cfg = cfg.get("home_assistant", {}).get("heating_dashboard", {})
    if not dashboard_cfg:
        print("No home_assistant.heating_dashboard configured; nothing to do.")
        return

    title = dashboard_cfg.get("title", "Heating")
    dashboard_url_path = dashboard_cfg.get("dashboard_url_path", "heating-overview")
    view_path = dashboard_cfg.get("view_path", "overview")
    icon = dashboard_cfg.get("icon", "mdi:radiator")
    style = dashboard_cfg.get("style", "default")
    boiler_entity = dashboard_cfg.get("boiler_entity")
    climate_entities = dashboard_cfg.get("climate_entities", [])
    lockout_enable_script = "script.heating_lockout_enable"
    lockout_disable_script = "script.heating_lockout_disable"
    on_automation_entity = "automation.heating_boiler_on_demand"

    cards = []
    if style == "mushroom":
        resources = ws_call(base, token, "lovelace/resources")
        mushroom_present = any(
            isinstance(resource, dict)
            and "lovelace-mushroom" in str(resource.get("url", ""))
            for resource in resources
        )
        if not mushroom_present:
            raise RuntimeError(
                "Mushroom card resource is missing. Install HACS + Mushroom first, then rerun sync-heating-dashboard."
            )
        if boiler_entity:
            cards.append(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": boiler_entity,
                    "name": "Gas Boiler",
                    "icon_color": "red",
                    "fill_container": False,
                }
            )
        cards.append(
            {
                "type": "grid",
                "title": "Heating Control",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "custom:mushroom-template-card",
                        "primary": "Automation Status",
                        "secondary": (
                            "{{ 'Enabled (Automatic Heating)' if is_state('"
                            + on_automation_entity
                            + "', 'on') else 'Lockout Active' }}"
                        ),
                        "icon": "mdi:radiator",
                        "icon_color": (
                            "{{ 'red' if is_state('"
                            + on_automation_entity
                            + "', 'on') else 'grey' }}"
                        ),
                    },
                    {
                        "type": "custom:mushroom-template-card",
                        "primary": "Enable Lockout",
                        "secondary": "Disable auto-heating and turn boiler off",
                        "icon": "mdi:snowflake-alert",
                        "icon_color": "blue",
                        "tap_action": {
                            "action": "call-service",
                            "service": "script.turn_on",
                            "target": {"entity_id": lockout_enable_script},
                        },
                    },
                    {
                        "type": "custom:mushroom-template-card",
                        "primary": "Disable Lockout",
                        "secondary": "Resume automatic heating control",
                        "icon": "mdi:radiator",
                        "icon_color": "red",
                        "tap_action": {
                            "action": "call-service",
                            "service": "script.turn_on",
                            "target": {"entity_id": lockout_disable_script},
                        },
                    },
                ],
            }
        )
        climate_cards = []
        for entity_id in climate_entities:
            climate_cards.append(
                {
                    "type": "custom:mushroom-climate-card",
                    "entity": entity_id,
                    "show_temperature_control": True,
                    "fill_container": False,
                }
            )
        cards.append(
            {
                "type": "grid",
                "title": "TRVs",
                "columns": 2,
                "square": False,
                "cards": climate_cards,
            }
        )
    else:
        if boiler_entity:
            cards.append(
                {
                    "type": "entities",
                    "title": "Boiler",
                    "entities": [boiler_entity],
                    "state_color": True,
                }
            )
        for entity_id in climate_entities:
            cards.append({"type": "thermostat", "entity": entity_id})

    heating_view = {
        "title": title,
        "path": view_path,
        "icon": icon,
        "cards": cards,
        "badges": [],
    }

    dashboards = ws_call(base, token, "lovelace/dashboards/list")
    if not any(d.get("url_path") == dashboard_url_path for d in dashboards):
        ws_call(
            base,
            token,
            "lovelace/dashboards/create",
            url_path=dashboard_url_path,
            title=title,
            icon=icon,
            show_in_sidebar=True,
            require_admin=False,
        )

    try:
        lovelace_config = ws_call(base, token, "lovelace/config", url_path=dashboard_url_path)
    except RuntimeError as exc:
        if "config_not_found" in str(exc):
            lovelace_config = {"views": []}
        else:
            raise
    if not isinstance(lovelace_config, dict):
        lovelace_config = {"views": []}

    views = lovelace_config.get("views", [])
    if not isinstance(views, list):
        views = []

    replaced = False
    for idx, view in enumerate(views):
        if isinstance(view, dict) and view.get("path") == view_path:
            views[idx] = heating_view
            replaced = True
            break
    if not replaced:
        views.append(heating_view)

    lovelace_config["views"] = views
    ws_call(base, token, "lovelace/config/save", url_path=dashboard_url_path, config=lovelace_config)
    action = "Updated" if replaced else "Created"
    print(f"{action} Heating dashboard at /{dashboard_url_path}/{view_path}")


def build_heating_demand_template(climate_entities: list, deadband_c: float, invert: bool = False) -> str:
    lines = ["{% set climate_entities = ["]
    for entity_id in climate_entities:
        lines.append(f"  '{entity_id}',")
    lines.extend(
        [
            "] %}",
            "{% set ns = namespace(demand=false) %}",
            "{% for entity_id in climate_entities %}",
            "{% set mode = states(entity_id) %}",
            "{% set hvac_action = state_attr(entity_id, 'hvac_action') %}",
            "{% set current = state_attr(entity_id, 'current_temperature') %}",
            "{% set target = state_attr(entity_id, 'temperature') %}",
            "{% if mode in ['heat', 'auto'] and (",
            f"      hvac_action == 'heating' or (current is number and target is number and (target - current) >= {deadband_c})",
            "   ) %}",
            "{% set ns.demand = true %}",
            "{% endif %}",
            "{% endfor %}",
            "{{ not ns.demand }}" if invert else "{{ ns.demand }}",
        ]
    )
    return "\n".join(lines)


def build_schedule_template(schedule_windows: list, invert: bool = False) -> str:
    if not schedule_windows:
        return "{{ false }}" if invert else "{{ true }}"

    weekday_map = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    windows = []
    for idx, window in enumerate(schedule_windows):
        start = str(window.get("start", "00:00:00"))
        end = str(window.get("end", "23:59:59"))
        weekday_tokens = window.get("weekdays", [])
        weekday_values = []
        for token in weekday_tokens:
            key = str(token).strip().lower()[:3]
            if key not in weekday_map:
                raise RuntimeError(
                    f"Invalid weekday '{token}' in home_assistant.heating_control.schedule[{idx}]"
                )
            weekday_values.append(weekday_map[key])
        if not weekday_values:
            raise RuntimeError(
                f"home_assistant.heating_control.schedule[{idx}] must include at least one weekday"
            )
        windows.append((start, end, weekday_values))

    lines = [
        "{% set now_dt = now() %}",
        "{% set current_wd = now_dt.weekday() %}",
        "{% set current_time = now_dt.strftime('%H:%M:%S') %}",
        "{% set ns = namespace(active=false) %}",
    ]
    for idx, (start, end, weekdays) in enumerate(windows):
        weekday_literal = "[" + ", ".join(str(x) for x in weekdays) + "]"
        lines.append(f"{{% set start_{idx} = '{start}' %}}")
        lines.append(f"{{% set end_{idx} = '{end}' %}}")
        lines.append(f"{{% set weekdays_{idx} = {weekday_literal} %}}")
        lines.append(f"{{% if current_wd in weekdays_{idx} %}}")
        lines.append(f"  {{% if start_{idx} <= end_{idx} %}}")
        lines.append(f"    {{% if current_time >= start_{idx} and current_time < end_{idx} %}}")
        lines.append("      {% set ns.active = true %}")
        lines.append("    {% endif %}")
        lines.append("  {% else %}")
        lines.append(f"    {{% if current_time >= start_{idx} or current_time < end_{idx} %}}")
        lines.append("      {% set ns.active = true %}")
        lines.append("    {% endif %}")
        lines.append("  {% endif %}")
        lines.append("{% endif %}")

    lines.append("{{ not ns.active }}" if invert else "{{ ns.active }}")
    return "\n".join(lines)


def cmd_sync_heating_control() -> None:
    cfg, base, token = ha_auth_from_config()
    dashboard_cfg = cfg.get("home_assistant", {}).get("heating_dashboard", {})
    boiler_entity = dashboard_cfg.get("boiler_entity")
    climate_entities = dashboard_cfg.get("climate_entities", [])
    if not boiler_entity or not climate_entities:
        raise RuntimeError(
            "home_assistant.heating_dashboard.boiler_entity and climate_entities must be set."
        )

    control_cfg = cfg.get("home_assistant", {}).get("heating_control", {})
    deadband_c = float(control_cfg.get("deadband_c", 0.5))
    on_for = control_cfg.get("on_for", "00:02:00")
    off_for = control_cfg.get("off_for", "00:07:00")
    schedule_off_for = control_cfg.get("schedule_off_for", "00:02:00")
    min_on_seconds = int(control_cfg.get("min_on_seconds", 480))
    min_off_seconds = int(control_cfg.get("min_off_seconds", 300))
    schedule_windows = control_cfg.get("schedule", [])

    demand_template = build_heating_demand_template(climate_entities, deadband_c)
    no_demand_template = build_heating_demand_template(climate_entities, deadband_c, invert=True)
    schedule_active_template = build_schedule_template(schedule_windows)
    schedule_inactive_template = build_schedule_template(schedule_windows, invert=True)

    lockout_enable_script = {
        "alias": "Heating Lockout Enable",
        "sequence": [
            {
                "action": "automation.turn_off",
                "target": {"entity_id": "automation.heating_boiler_on_demand"},
            },
            {
                "action": "switch.turn_off",
                "target": {"entity_id": boiler_entity},
            },
        ],
        "mode": "single",
    }
    lockout_disable_script = {
        "alias": "Heating Lockout Disable",
        "sequence": [
            {
                "action": "automation.turn_on",
                "target": {"entity_id": "automation.heating_boiler_on_demand"},
            }
        ],
        "mode": "single",
    }

    on_automation = {
        "alias": "Heating Boiler On Demand",
        "description": "Turn boiler on when any configured TRV demands heat inside configured schedule windows.",
        "mode": "single",
        "triggers": [{"trigger": "template", "value_template": demand_template, "for": on_for}],
        "conditions": [
            {"condition": "state", "entity_id": boiler_entity, "state": "off"},
            {"condition": "template", "value_template": schedule_active_template},
            {
                "condition": "template",
                "value_template": (
                    f"{{{{ (as_timestamp(now()) - as_timestamp(states['{boiler_entity}'].last_changed, 0)) >= {min_off_seconds} }}}}"
                ),
            },
        ],
        "actions": [{"action": "switch.turn_on", "target": {"entity_id": boiler_entity}}],
    }
    off_automation = {
        "alias": "Heating Boiler Off When Satisfied",
        "description": "Turn boiler off when all configured TRVs are satisfied.",
        "mode": "single",
        "triggers": [{"trigger": "template", "value_template": no_demand_template, "for": off_for}],
        "conditions": [
            {"condition": "state", "entity_id": boiler_entity, "state": "on"},
            {
                "condition": "template",
                "value_template": (
                    f"{{{{ (as_timestamp(now()) - as_timestamp(states['{boiler_entity}'].last_changed, 0)) >= {min_on_seconds} }}}}"
                ),
            },
        ],
        "actions": [{"action": "switch.turn_off", "target": {"entity_id": boiler_entity}}],
    }
    schedule_off_automation = {
        "alias": "Heating Boiler Off Outside Schedule",
        "description": "Turn boiler off when outside configured heating schedule windows.",
        "mode": "single",
        "triggers": [
            {
                "trigger": "template",
                "value_template": schedule_inactive_template,
                "for": schedule_off_for,
            }
        ],
        "conditions": [
            {"condition": "state", "entity_id": boiler_entity, "state": "on"},
            {
                "condition": "template",
                "value_template": (
                    f"{{{{ (as_timestamp(now()) - as_timestamp(states['{boiler_entity}'].last_changed, 0)) >= {min_on_seconds} }}}}"
                ),
            },
        ],
        "actions": [{"action": "switch.turn_off", "target": {"entity_id": boiler_entity}}],
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for script_id, payload in [
        ("heating_lockout_enable", lockout_enable_script),
        ("heating_lockout_disable", lockout_disable_script),
    ]:
        response = requests.post(
            f"{base}/api/config/script/config/{script_id}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        print(f"Synced script.{script_id}")

    for entity_id, payload in [
        ("automation.heating_boiler_on_demand", on_automation),
        ("automation.heating_boiler_off_when_satisfied", off_automation),
        ("automation.heating_boiler_off_outside_schedule", schedule_off_automation),
    ]:
        response = requests.post(
            f"{base}/api/config/automation/config/{entity_id}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        print(f"Synced {entity_id}")

    scripts_reload_response = requests.post(
        f"{base}/api/services/script/reload",
        headers=headers,
        json={},
        timeout=20,
    )
    scripts_reload_response.raise_for_status()
    print("Reloaded scripts")

    reload_response = requests.post(
        f"{base}/api/services/automation/reload",
        headers=headers,
        json={},
        timeout=20,
    )
    reload_response.raise_for_status()
    print("Reloaded automations")


def main() -> None:
    parser = argparse.ArgumentParser(description="Home Assistant helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply-core")
    sub.add_parser("sync-devices")
    sub.add_parser("add-tplink")
    sub.add_parser("sync-heating-dashboard")
    sub.add_parser("sync-heating-control")
    sub.add_parser("summary")
    args = parser.parse_args()

    if args.command == "apply-core":
        cmd_apply_core()
    elif args.command == "sync-devices":
        cmd_sync_devices()
    elif args.command == "add-tplink":
        cmd_add_tplink()
    elif args.command == "sync-heating-dashboard":
        cmd_sync_heating_dashboard()
    elif args.command == "sync-heating-control":
        cmd_sync_heating_control()
    elif args.command == "summary":
        cmd_summary()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
