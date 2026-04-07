#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
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


def ensure_lovelace_resource(base_url: str, token: str, url: str, res_type: str = "module") -> None:
    resources = ws_call(base_url, token, "lovelace/resources")
    normalized_url = url.split("?", 1)[0]
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        existing_url = str(resource.get("url", ""))
        if existing_url.split("?", 1)[0] != normalized_url:
            continue
        if existing_url == url and resource.get("type") == res_type:
            return
        ws_call(
            base_url,
            token,
            "lovelace/resources/update",
            resource_id=resource["id"],
            url=url,
            res_type=res_type,
        )
        return

    ws_call(base_url, token, "lovelace/resources/create", url=url, res_type=res_type)


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


def pretty_climate_name(entity_id: str) -> str:
    object_id = entity_id.split(".", 1)[1]
    return object_id.replace("_", " ").title()


def boost_timer_entity(control: dict) -> str:
    explicit = str(control.get("timer_entity", "")).strip()
    if explicit:
        return explicit
    script_entity = str(control.get("script_entity", "")).strip()
    if not script_entity.startswith("script."):
        raise RuntimeError("remote_heating_controls entry is missing a usable script_entity for timer derivation")
    return f"timer.{script_entity.split('.', 1)[1]}"


def boost_restore_state_entity(control: dict) -> str:
    explicit = str(control.get("restore_state_entity", "")).strip()
    if explicit:
        return explicit
    script_entity = str(control.get("script_entity", "")).strip()
    if not script_entity.startswith("script."):
        raise RuntimeError("remote_heating_controls entry is missing a usable script_entity for restore-state derivation")
    return f"input_text.{script_entity.split('.', 1)[1]}_restore_state"


def ha_delay(seconds: float) -> str:
    if float(seconds).is_integer():
        return f"00:00:{int(seconds):02d}"
    return f"00:00:{seconds:04.1f}"


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
    concept_views_cfg = dashboard_cfg.get(
        "concept_views",
        [
            {
                "title": "A",
                "path": "hybrid-a",
                "icon": "mdi:view-dashboard",
                "concept": "hybrid_a",
            },
            {
                "title": "B",
                "path": "hybrid-b",
                "icon": "mdi:view-grid-plus",
                "concept": "hybrid_b",
            },
            {
                "title": "C",
                "path": "hybrid-c",
                "icon": "mdi:cellphone-thermometer",
                "concept": "hybrid_c",
            },
            {
                "title": "D",
                "path": "hybrid-d",
                "icon": "mdi:tune-variant",
                "concept": "hybrid_d",
            },
        ],
    )
    boiler_entity = dashboard_cfg.get("boiler_entity")
    climate_entities = dashboard_cfg.get("climate_entities", [])
    groups = dashboard_cfg.get("groups", {})
    upstairs_climates = groups.get("upstairs", [])
    downstairs_climates = groups.get("downstairs", [])
    temp_helpers = dashboard_cfg.get("temp_helpers", {})
    house_target_entity = temp_helpers.get("house", "input_number.house_target")
    upstairs_target_entity = temp_helpers.get("upstairs", "input_number.upstairs_target")
    downstairs_target_entity = temp_helpers.get("downstairs", "input_number.downstairs_target")
    lockout_enable_script = "script.heating_lockout_enable"
    lockout_disable_script = "script.heating_lockout_disable"
    house_set_script = "script.heating_set_house_temp"
    upstairs_set_script = "script.heating_set_upstairs_temp"
    downstairs_set_script = "script.heating_set_downstairs_temp"
    downstairs_boost_script = "script.boost_downstairs"
    downstairs_boost_cancel_script = "script.cancel_boost_downstairs"
    bedroom_boost_script = "script.boost_bedroom"
    bedroom_boost_cancel_script = "script.cancel_boost_bedroom"
    all_off_script = "script.heating_all_off"
    downstairs_timer_entity = "timer.boost_downstairs"
    bedroom_timer_entity = "timer.boost_bedroom"
    on_automation_entity = "automation.heating_boiler_on_demand"
    bedroom_entity = "climate.bedroom_2"
    simple_thermostat_url = "/local/repo-managed-cards/simple-thermostat.js?v=2.5.0"
    mini_climate_url = "/local/repo-managed-cards/mini-climate-card-bundle.js?v=2.7.3"
    stale_concept_paths = {"concept-a", "concept-b", "concept-c"}

    def climate_list_literal(entity_ids: List[str]) -> str:
        return "[" + ", ".join(f"'{entity_id}'" for entity_id in entity_ids) + "]"

    def calling_for_heat_secondary(entity_ids: List[str]) -> str:
        return (
            "{% set ns = namespace(items=[]) %}"
            + f"{{% for entity_id in {climate_list_literal(entity_ids)} %}}"
            + "{% if state_attr(entity_id, 'hvac_action') == 'heating' %}"
            + "{% set ns.items = ns.items + [state_attr(entity_id, 'friendly_name') or entity_id] %}"
            + "{% endif %}"
            + "{% endfor %}"
            + "{{ ns.items | join(', ') if ns.items else 'No rooms actively heating' }}"
        )

    def calling_for_heat_count(entity_ids: List[str]) -> str:
        return (
            "{% set ns = namespace(count=0) %}"
            + f"{{% for entity_id in {climate_list_literal(entity_ids)} %}}"
            + "{% if state_attr(entity_id, 'hvac_action') == 'heating' %}"
            + "{% set ns.count = ns.count + 1 %}"
            + "{% endif %}"
            + "{% endfor %}"
            + "{{ ns.count }}"
        )

    def boost_active_count(entity_ids: List[str]) -> str:
        return (
            "{{ "
            + ("1" if entity_ids == downstairs_climates else "1")
            + " if "
            + ("is_state('" + downstairs_timer_entity + "', 'active')" if entity_ids == downstairs_climates else "is_state('" + bedroom_timer_entity + "', 'active')")
            + " else 0 }}"
        )

    def timer_secondary(timer_entity: str) -> str:
        return (
            "{% if is_state('"
            + timer_entity
            + "', 'active') %}"
            + "Until {{ as_timestamp(state_attr('"
            + timer_entity
            + "', 'finishes_at')) | timestamp_custom('%H:%M') }}"
            + "{% else %}Idle{% endif %}"
        )

    def room_secondary(entity_id: str) -> str:
        return (
            "{{ state_attr('"
            + entity_id
            + "', 'current_temperature') | round(1) }}C now"
            + " • {{ state_attr('"
            + entity_id
            + "', 'temperature') | round(1) }}C target"
            + " • {{ state_attr('"
            + entity_id
            + "', 'hvac_action') or states('"
            + entity_id
            + "') }}"
        )

    def room_icon_color(entity_id: str) -> str:
        return (
            "{{ 'red' if state_attr('"
            + entity_id
            + "', 'hvac_action') == 'heating' else "
            + "'orange' if is_state('"
            + entity_id
            + "', 'heat') else 'grey' }}"
        )

    def action_card(
        name: str,
        secondary: str,
        icon_name: str,
        icon_color: str,
        entity_id: str,
    ) -> Dict[str, Any]:
        return {
            "type": "custom:mushroom-template-card",
            "primary": name,
            "secondary": secondary,
            "icon": icon_name,
            "icon_color": icon_color,
            "multiline_secondary": True,
            "tap_action": {
                "action": "call-service",
                "service": "script.turn_on",
                "target": {"entity_id": entity_id},
            },
        }

    def service_card(
        name: str,
        secondary: str,
        icon_name: str,
        icon_color: str,
        service: str,
        target_entity_ids: List[str],
        service_data: Any = None,
    ) -> Dict[str, Any]:
        card = {
            "type": "custom:mushroom-template-card",
            "primary": name,
            "secondary": secondary,
            "icon": icon_name,
            "icon_color": icon_color,
            "multiline_secondary": True,
            "tap_action": {
                "action": "call-service",
                "service": service,
                "target": {"entity_id": target_entity_ids if len(target_entity_ids) > 1 else target_entity_ids[0]},
            },
        }
        if service_data:
            card["tap_action"]["data"] = service_data
        return card

    def timer_card(name: str, timer_entity: str, icon_name: str, active_color: str) -> Dict[str, Any]:
        return {
            "type": "custom:mushroom-template-card",
            "entity": timer_entity,
            "primary": name,
            "secondary": timer_secondary(timer_entity),
            "icon": icon_name,
            "icon_color": (
                "{{ '" + active_color + "' if is_state('" + timer_entity + "', 'active') else 'grey' }}"
            ),
        }

    def room_status_card(entity_id: str) -> Dict[str, Any]:
        return {
            "type": "custom:mushroom-template-card",
            "entity": entity_id,
            "primary": pretty_climate_name(entity_id),
            "secondary": room_secondary(entity_id),
            "icon": "mdi:radiator",
            "icon_color": room_icon_color(entity_id),
            "multiline_secondary": True,
            "tap_action": {"action": "more-info"},
        }

    def climate_control_card(entity_id: str) -> Dict[str, Any]:
        return {
            "type": "custom:mushroom-climate-card",
            "entity": entity_id,
            "show_temperature_control": True,
            "fill_container": False,
        }

    def mini_climate_card(entity_id: str, name: Any = None, group: bool = False) -> Dict[str, Any]:
        card = {
            "type": "custom:mini-climate",
            "entity": entity_id,
            "secondary_info": {"type": "hvac-action"},
            "toggle": {"default": True},
            "group": group,
        }
        if name:
            card["name"] = name
        return card

    def simple_thermostat_card(entity_id: str, compact: bool = False) -> Dict[str, Any]:
        card: Dict[str, Any] = {
            "type": "custom:simple-thermostat",
            "entity": entity_id,
            "layout": {"step": "row"},
            "control": {"hvac": True},
            "sensors": [
                {"attribute": "current_temperature", "name": "Current", "unit": "°C"},
                {"attribute": "hvac_action", "name": "Action"},
            ],
            "header": {
                "icon": {
                    "heating": "mdi:radiator",
                    "idle": "mdi:radiator-disabled",
                    "off": "mdi:radiator-off",
                }
            },
        }
        if compact:
            card["header"] = False
            card["control"] = False
            card["layout"] = {"step": "row", "sensors": {"type": "list", "labels": False}}
        return card

    def room_graph_card(entity_id: str, hours: int = 12) -> Dict[str, Any]:
        if apexcharts_present:
            return {
                "type": "custom:apexcharts-card",
                "header": {"show": True, "title": pretty_climate_name(entity_id)},
                "graph_span": f"{hours}h",
                "apex_config": {
                    "chart": {"height": 180},
                    "stroke": {"width": [2, 2], "curve": ["smooth", "stepline"]},
                },
                "series": [
                    {
                        "entity": entity_id,
                        "attribute": "current_temperature",
                        "name": "Current",
                        "color": "#42a5f5",
                    },
                    {
                        "entity": entity_id,
                        "attribute": "temperature",
                        "name": "Target",
                        "color": "#ff9800",
                    },
                ],
            }
        return {
            "type": "custom:mini-graph-card",
            "name": pretty_climate_name(entity_id),
            "hours_to_show": hours,
            "points_per_hour": 4,
            "line_width": 2,
            "show": {
                "icon": False,
                "name": True,
                "state": True,
                "legend": True,
            },
            "entities": [
                {
                    "entity": entity_id,
                    "attribute": "current_temperature",
                    "name": "Current",
                    "color": "#42a5f5",
                },
                {
                    "entity": entity_id,
                    "attribute": "temperature",
                    "name": "Target",
                    "color": "#ff9800",
                    "show_line": False,
                    "show_points": True,
                },
                ],
            }

    def summary_chips() -> Dict[str, Any]:
        return {
            "type": "custom:mushroom-chips-card",
            "chips": [
                {"type": "entity", "entity": boiler_entity, "icon_color": "red", "content_info": "state"},
                {
                    "type": "template",
                    "icon": "mdi:fire-circle",
                    "icon_color": "{{ 'red' if (" + calling_for_heat_count(climate_entities) + ")|int > 0 else 'grey' }}",
                    "content": "{{ " + calling_for_heat_count(climate_entities) + " }} heating",
                },
                {
                    "type": "template",
                    "icon": "mdi:fire",
                    "icon_color": "{{ 'red' if is_state('" + downstairs_timer_entity + "', 'active') else 'grey' }}",
                    "content": "{{ 'Downstairs boost' if is_state('" + downstairs_timer_entity + "', 'active') else 'Downstairs idle' }}",
                },
                {
                    "type": "template",
                    "icon": "mdi:bed",
                    "icon_color": "{{ 'red' if is_state('" + bedroom_timer_entity + "', 'active') else 'grey' }}",
                    "content": "{{ 'Bedroom boost' if is_state('" + bedroom_timer_entity + "', 'active') else 'Bedroom idle' }}",
                },
            ],
        }

    def downstairs_summary_card() -> Dict[str, Any]:
        return {
            "type": "custom:mushroom-template-card",
            "primary": "Downstairs",
            "secondary": (
                "Target {{ states('"
                + downstairs_target_entity
                + "') }}C"
                + " • {{ "
                + calling_for_heat_count(downstairs_climates)
                + " }} heating"
                + " • {{ "
                + calling_for_heat_secondary(downstairs_climates)
                + " }}"
            ),
            "icon": "mdi:stairs-down",
            "icon_color": (
                "{{ 'red' if is_state('" + downstairs_timer_entity + "', 'active') else "
                + "'orange' if (" + calling_for_heat_count(downstairs_climates) + ")|int > 0 else 'grey' }}"
            ),
            "multiline_secondary": True,
        }

    def downstairs_hero_card(columns: int = 2) -> Dict[str, Any]:
        return {
            "type": "vertical-stack",
            "cards": [
                {"type": "markdown", "content": "## Downstairs"},
                downstairs_summary_card(),
                {
                    "type": "custom:mushroom-number-card",
                    "entity": downstairs_target_entity,
                    "name": "Downstairs Target",
                    "icon": "mdi:stairs-down",
                    "display_mode": "slider",
                    "icon_color": "green",
                    "fill_container": False,
                },
                {
                    "type": "grid",
                    "columns": columns,
                    "square": False,
                    "cards": [
                        action_card(
                            "On",
                            "Apply downstairs target",
                            "mdi:radiator",
                            "red",
                            "script.heating_set_downstairs_temp",
                        ),
                        service_card(
                            "Off",
                            "Turn off downstairs rooms",
                            "mdi:radiator-off",
                            "blue-grey",
                            "climate.turn_off",
                            downstairs_climates,
                        ),
                        action_card(
                            "Boost",
                            "23C for 30 minutes",
                            "mdi:fire",
                            "red",
                            downstairs_boost_script,
                        ),
                        action_card(
                            "Cancel",
                            "Restore pre-boost state",
                            "mdi:fire-off",
                            "deep-purple",
                            downstairs_boost_cancel_script,
                        ),
                    ],
                },
                timer_card("Downstairs Boost", downstairs_timer_entity, "mdi:fire", "red"),
            ],
        }

    def bedroom_hero_actions(columns: int = 2) -> Dict[str, Any]:
        return {
            "type": "grid",
            "columns": columns,
            "square": False,
            "cards": [
                service_card(
                    "On",
                    "Set Bedroom to heat mode",
                    "mdi:bed",
                    "red",
                    "climate.set_hvac_mode",
                    [bedroom_entity],
                    {"hvac_mode": "heat"},
                ),
                service_card(
                    "Off",
                    "Turn Bedroom off",
                    "mdi:bed-empty",
                    "blue-grey",
                    "climate.turn_off",
                    [bedroom_entity],
                ),
                action_card(
                    "Boost",
                    "23C for 30 minutes",
                    "mdi:fire",
                    "red",
                    bedroom_boost_script,
                ),
                action_card(
                    "Cancel",
                    "Restore pre-boost state",
                    "mdi:fire-off",
                    "deep-purple",
                    bedroom_boost_cancel_script,
                ),
            ],
        }

    def bedroom_hero_simple() -> Dict[str, Any]:
        return {
            "type": "vertical-stack",
            "cards": [
                {"type": "markdown", "content": "## Bedroom"},
                simple_thermostat_card(bedroom_entity),
                bedroom_hero_actions(),
                timer_card("Bedroom Boost", bedroom_timer_entity, "mdi:bed", "red"),
            ],
        }

    def bedroom_hero_mini() -> Dict[str, Any]:
        return {
            "type": "vertical-stack",
            "cards": [
                {"type": "markdown", "content": "## Bedroom"},
                mini_climate_card(bedroom_entity, name="Bedroom"),
                bedroom_hero_actions(),
                timer_card("Bedroom Boost", bedroom_timer_entity, "mdi:bed", "red"),
            ],
        }

    def target_cards() -> List[Dict[str, Any]]:
        return [
            {
                "type": "custom:mushroom-number-card",
                "entity": house_target_entity,
                "name": "House Target",
                "icon": "mdi:home-thermometer",
                "display_mode": "slider",
                "icon_color": "red",
                "fill_container": False,
            },
            {
                "type": "custom:mushroom-number-card",
                "entity": upstairs_target_entity,
                "name": "Upstairs Target",
                "icon": "mdi:stairs-up",
                "display_mode": "slider",
                "icon_color": "orange",
                "fill_container": False,
            },
            {
                "type": "custom:mushroom-number-card",
                "entity": downstairs_target_entity,
                "name": "Downstairs Target",
                "icon": "mdi:stairs-down",
                "display_mode": "slider",
                "icon_color": "green",
                "fill_container": False,
            },
        ]

    def quick_action_cards() -> List[Dict[str, Any]]:
        return [
            action_card(
                "Boost Downstairs",
                "Front Window, Dining Area, Bathroom to 23C",
                "mdi:fire",
                "red",
                downstairs_boost_script,
            ),
            action_card(
                "Cancel Downstairs",
                "Restore pre-boost downstairs state",
                "mdi:fire-off",
                "deep-purple",
                downstairs_boost_cancel_script,
            ),
            action_card(
                "Boost Bedroom",
                "Bedroom to 23C",
                "mdi:bed",
                "red",
                bedroom_boost_script,
            ),
            action_card(
                "Cancel Bedroom",
                "Restore bedroom pre-boost state",
                "mdi:bed-empty",
                "deep-purple",
                bedroom_boost_cancel_script,
            ),
            action_card(
                "All Off",
                "Turn all managed TRVs off",
                "mdi:radiator-off",
                "blue-grey",
                all_off_script,
            ),
            action_card(
                "Enable Lockout",
                "Disable auto-heating and turn boiler off",
                "mdi:snowflake-alert",
                "blue",
                lockout_enable_script,
            ),
            action_card(
                "Disable Lockout",
                "Resume automatic heating control",
                "mdi:radiator",
                "red",
                lockout_disable_script,
            ),
        ]

    resources = ws_call(base, token, "lovelace/resources")
    mushroom_present = any(
        isinstance(resource, dict)
        and "lovelace-mushroom" in str(resource.get("url", ""))
        for resource in resources
    )
    mini_graph_present = any(
        isinstance(resource, dict)
        and "mini-graph-card" in str(resource.get("url", ""))
        for resource in resources
    )
    apexcharts_present = any(
        isinstance(resource, dict)
        and "apexcharts-card" in str(resource.get("url", ""))
        for resource in resources
    )
    if style == "mushroom" and not mushroom_present:
        raise RuntimeError(
            "Mushroom card resource is missing. Install HACS + Mushroom first, then rerun sync-heating-dashboard."
        )
    ensure_lovelace_resource(base, token, simple_thermostat_url)
    ensure_lovelace_resource(base, token, mini_climate_url)

    def build_overview_view() -> Dict[str, Any]:
        if style != "mushroom":
            cards: List[Dict[str, Any]] = []
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
            return {
                "title": title,
                "path": view_path,
                "icon": icon,
                "cards": cards,
                "badges": [],
            }

        section_cards: List[Dict[str, Any]] = []
        if boiler_entity:
            section_cards.append(
                {
                    "type": "custom:mushroom-entity-card",
                    "entity": boiler_entity,
                    "name": "Gas Boiler",
                    "icon_color": "red",
                    "fill_container": False,
                }
            )
        section_cards.append(
            {
                "type": "grid",
                "title": "Heating Control",
                "columns": 4,
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
                    *target_cards(),
                    *quick_action_cards()[:4],
                ],
            }
        )
        section_cards.append(
            {
                "type": "grid",
                "title": "TRVs",
                "columns": 4,
                "square": False,
                "cards": [climate_control_card(entity_id) for entity_id in climate_entities],
            }
        )
        if mini_graph_present:
            section_cards.append(
                {
                    "type": "custom:mini-graph-card",
                    "name": "TRV Temperatures (48h)",
                    "hours_to_show": 48,
                    "points_per_hour": 4,
                    "line_width": 2,
                    "show": {
                        "icon": False,
                        "name": True,
                        "state": False,
                        "legend": True,
                    },
                    "entities": [
                        {
                            "entity": entity_id,
                            "attribute": "current_temperature",
                            "name": pretty_climate_name(entity_id),
                        }
                        for entity_id in climate_entities
                    ],
                }
            )
            section_cards.append(
                {
                    "type": "grid",
                    "title": "TRV Graphs",
                    "columns": 2,
                    "square": False,
                    "cards": [room_graph_card(entity_id) for entity_id in climate_entities],
                }
            )
        else:
            section_cards.append(
                {
                    "type": "markdown",
                    "title": "TRV Temperature Graphs",
                    "content": (
                        "Install HACS `mini-graph-card` to enable TRV temperature charts on this page."
                    ),
                }
            )
        return {
            "title": title,
            "path": view_path,
            "icon": icon,
            "panel": True,
            "cards": [{"type": "vertical-stack", "cards": section_cards}],
            "badges": [],
        }

    def build_hybrid_a_view(view_title: str, view_icon: str, path: str) -> Dict[str, Any]:
        cards: List[Dict[str, Any]] = [
            {
                "type": "markdown",
                "content": (
                    "## Hybrid A\n"
                    "Operational and summary-first. Dual-use layout with strong hero controls, fast zone actions, and compact room rows underneath."
                ),
            },
            summary_chips(),
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [downstairs_hero_card(), bedroom_hero_simple()],
            },
            {
                "type": "grid",
                "title": "Whole-house Controls",
                "columns": 3,
                "square": False,
                "cards": target_cards(),
            },
            {
                "type": "grid",
                "title": "Quick Actions",
                "columns": 4,
                "square": False,
                "cards": quick_action_cards(),
            },
            {
                "type": "grid",
                "title": "Room Rows",
                "columns": 2,
                "square": False,
                "cards": [mini_climate_card(entity_id, name=pretty_climate_name(entity_id)) for entity_id in climate_entities],
            },
        ]
        if mini_graph_present:
            cards.extend(
                [
                    {
                        "type": "custom:mini-graph-card",
                        "name": "Whole-house temperatures (24h)",
                        "hours_to_show": 24,
                        "points_per_hour": 4,
                        "line_width": 2,
                        "show": {"icon": False, "name": True, "state": False, "legend": True},
                        "entities": [
                            {
                                "entity": entity_id,
                                "attribute": "current_temperature",
                                "name": pretty_climate_name(entity_id),
                            }
                            for entity_id in climate_entities
                        ],
                    },
                    {
                        "type": "grid",
                        "title": "Detailed Room Trends",
                        "columns": 2,
                        "square": False,
                        "cards": [room_graph_card(entity_id) for entity_id in climate_entities],
                    },
                ]
            )
        return {
            "title": view_title,
            "path": path,
            "icon": view_icon,
            "panel": True,
            "cards": [{"type": "vertical-stack", "cards": cards}],
            "badges": [],
        }

    def build_hybrid_b_view(view_title: str, view_icon: str, path: str) -> Dict[str, Any]:
        cards: List[Dict[str, Any]] = [
            {
                "type": "markdown",
                "content": (
                    "## Hybrid B\n"
                    "Dense desktop-first control room. Hero zones on top, then compact simple-thermostat room panels in a tighter grid."
                ),
            },
            summary_chips(),
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    downstairs_hero_card(),
                    bedroom_hero_simple(),
                ],
            },
            {
                "type": "grid",
                "title": "Targets",
                "columns": 3,
                "square": False,
                "cards": target_cards(),
            },
            {"type": "markdown", "content": "## Upstairs Rooms"},
            {
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": [simple_thermostat_card(entity_id, compact=True) for entity_id in upstairs_climates],
            },
            {"type": "markdown", "content": "## Downstairs Rooms"},
            {
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": [simple_thermostat_card(entity_id, compact=True) for entity_id in downstairs_climates],
            },
        ]
        return {
            "title": view_title,
            "path": path,
            "icon": view_icon,
            "panel": True,
            "cards": [{"type": "vertical-stack", "cards": cards}],
            "badges": [],
        }

    def build_hybrid_c_view(view_title: str, view_icon: str, path: str) -> Dict[str, Any]:
        cards: List[Dict[str, Any]] = [
            {
                "type": "markdown",
                "content": (
                    "## Hybrid C\n"
                    "Mobile-first. One-column reading order, strong hero cards, mini-climate rows, and large quick actions."
                ),
            },
            summary_chips(),
            downstairs_hero_card(),
            bedroom_hero_mini(),
            *target_cards(),
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    *quick_action_cards(),
                ],
            },
            {
                "type": "grid",
                "title": "Room Rows",
                "columns": 1,
                "square": False,
                "cards": [mini_climate_card(entity_id, name=pretty_climate_name(entity_id)) for entity_id in climate_entities],
            },
        ]
        return {
            "title": view_title,
            "path": path,
            "icon": view_icon,
            "panel": True,
            "cards": [{"type": "vertical-stack", "cards": cards}],
            "badges": [],
        }

    def build_hybrid_d_view(view_title: str, view_icon: str, path: str) -> Dict[str, Any]:
        rich_room_cards = []
        for entity_id in climate_entities:
            rich_room_cards.append(
                {
                    "type": "vertical-stack",
                    "cards": [
                        room_status_card(entity_id),
                        simple_thermostat_card(entity_id, compact=True),
                        room_graph_card(entity_id, hours=6) if mini_graph_present else mini_climate_card(entity_id, group=True),
                    ],
                }
            )

        cards: List[Dict[str, Any]] = [
            {
                "type": "markdown",
                "content": (
                    "## Hybrid D\n"
                    "Supported rich-panel substitute for `better-thermostat-ui-card`.\n\n"
                    "`better-thermostat-ui-card` is not used here because the managed climate entities in this setup are `tplink` climates, not `better_thermostat` climates."
                ),
            },
            summary_chips(),
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [downstairs_hero_card(), bedroom_hero_simple()],
            },
            {
                "type": "grid",
                "title": "Zone Targets",
                "columns": 3,
                "square": False,
                "cards": target_cards(),
            },
            {
                "type": "grid",
                "title": "Rich Room Panels",
                "columns": 2,
                "square": False,
                "cards": rich_room_cards,
            },
        ]
        return {
            "title": view_title,
            "path": path,
            "icon": view_icon,
            "panel": True,
            "cards": [{"type": "vertical-stack", "cards": cards}],
            "badges": [],
        }

    views_to_sync = [build_overview_view()]
    if style == "mushroom":
        concept_builders = {
            "hybrid_a": build_hybrid_a_view,
            "hybrid_b": build_hybrid_b_view,
            "hybrid_c": build_hybrid_c_view,
            "hybrid_d": build_hybrid_d_view,
        }
        for concept_view in concept_views_cfg:
            concept_name = concept_view.get("concept")
            builder = concept_builders.get(concept_name)
            if not builder:
                continue
            views_to_sync.append(
                builder(
                    concept_view.get("title", concept_name.replace("_", " ").title()),
                    concept_view.get("icon", icon),
                    concept_view.get("path", concept_name),
                )
            )

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

    managed_paths = {view.get("path") for view in views_to_sync if isinstance(view, dict)}
    views = [
        view
        for view in views
        if not (isinstance(view, dict) and view.get("path") in stale_concept_paths and view.get("path") not in managed_paths)
    ]

    actions = []
    for target_view in views_to_sync:
        replaced = False
        for idx, view in enumerate(views):
            if isinstance(view, dict) and view.get("path") == target_view.get("path"):
                views[idx] = target_view
                replaced = True
                break
        if not replaced:
            views.append(target_view)
        actions.append(("Updated" if replaced else "Created", target_view.get("path")))

    lovelace_config["views"] = views
    ws_call(base, token, "lovelace/config/save", url_path=dashboard_url_path, config=lovelace_config)
    for action, saved_path in actions:
        print(f"{action} Heating dashboard view at /{dashboard_url_path}/{saved_path}")


def cmd_sync_status_lights() -> None:
    cfg, base, token = ha_auth_from_config()
    status_cfg = cfg.get("home_assistant", {}).get("status_lights", {})
    if not status_cfg:
        print("No home_assistant.status_lights configured; nothing to do.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    title = str(status_cfg.get("title", "Status Lights")).strip()
    dashboard_url_path = str(status_cfg.get("dashboard_url_path", "status-lights")).strip()
    view_path = str(status_cfg.get("view_path", "overview")).strip()
    icon = str(status_cfg.get("icon", "mdi:led-strip-variant")).strip()
    snooze_timer_entity = str(status_cfg.get("snooze_timer_entity", "timer.status_light_snooze")).strip()
    if not snooze_timer_entity.startswith("timer."):
        raise RuntimeError("home_assistant.status_lights.snooze_timer_entity must be a timer.* entity")

    baseline_cfg = status_cfg.get("baseline", {}) or {}
    targets = status_cfg.get("targets", []) or []
    events = status_cfg.get("events", {}) or {}
    if not targets:
        raise RuntimeError("home_assistant.status_lights.targets must contain at least one target")
    if not events:
        raise RuntimeError("home_assistant.status_lights.events must contain at least one semantic event")

    def merged_baseline(target: dict) -> dict:
        merged = dict(baseline_cfg)
        target_baseline = target.get("baseline", {}) or {}
        if isinstance(target_baseline, dict):
            merged.update(target_baseline)
        return merged

    def target_payload(target: dict, source: dict) -> dict:
        capability = str(target.get("capability", "rgb")).strip().lower()
        data: Dict[str, Any] = {}
        brightness_pct = source.get("brightness_pct")
        if brightness_pct is not None:
            data["brightness_pct"] = int(brightness_pct)
        transition = source.get("transition")
        if transition is not None:
            data["transition"] = float(transition)
        if capability == "rgb" and source.get("rgb_color") is not None:
            data["rgb_color"] = [int(component) for component in source.get("rgb_color", [])]
        elif capability in {"color_temp", "ct"} and source.get("color_temp_kelvin") is not None:
            data["color_temp_kelvin"] = int(source.get("color_temp_kelvin"))
        return data

    def available_condition(entity_id: str) -> dict:
        return {
            "condition": "template",
            "value_template": "{{ states('" + entity_id + "') not in ['unavailable', 'unknown'] }}",
        }

    def apply_baseline_sequence(target: dict) -> List[dict]:
        entity_id = str(target.get("entity_id", "")).strip()
        baseline = merged_baseline(target)
        desired_state = str(baseline.get("state", "on")).strip().lower()
        if desired_state == "off":
            action = {
                "action": "light.turn_off",
                "target": {"entity_id": entity_id},
            }
        else:
            payload = target_payload(target, baseline)
            if not payload:
                payload = {"brightness_pct": 1, "transition": 0}
            action = {
                "action": "light.turn_on",
                "target": {"entity_id": entity_id},
                "data": payload,
            }
        return [{"choose": [{"conditions": [available_condition(entity_id)], "sequence": [action]}]}]

    def apply_quiet_sequence(target: dict) -> List[dict]:
        entity_id = str(target.get("entity_id", "")).strip()
        return [
            {
                "choose": [
                    {
                        "conditions": [available_condition(entity_id)],
                        "sequence": [{"action": "light.turn_off", "target": {"entity_id": entity_id}}],
                    }
                ]
            }
        ]

    def effect_sequence(target: dict, effect: dict) -> List[dict]:
        entity_id = str(target.get("entity_id", "")).strip()
        flashes = max(1, int(effect.get("flashes", 1)))
        on_seconds = float(effect.get("on_seconds", 0.5))
        off_seconds = float(effect.get("off_seconds", 0.25))
        payload = target_payload(target, effect)
        if "brightness_pct" not in payload:
            payload["brightness_pct"] = 100
        payload.setdefault("transition", 0)
        return [
            {
                "choose": [
                    {
                        "conditions": [available_condition(entity_id)],
                        "sequence": [
                            {
                                "repeat": {
                                    "count": flashes,
                                    "sequence": [
                                        {
                                            "action": "light.turn_on",
                                            "target": {"entity_id": entity_id},
                                            "data": payload,
                                        },
                                        {"delay": ha_delay(on_seconds)},
                                        {
                                            "action": "light.turn_off",
                                            "target": {"entity_id": entity_id},
                                        },
                                        {"delay": ha_delay(off_seconds)},
                                    ],
                                }
                            }
                        ],
                    }
                ]
            }
        ]

    baseline_parallel = {"parallel": [{"sequence": apply_baseline_sequence(target)} for target in targets]}
    quiet_parallel = {"parallel": [{"sequence": apply_quiet_sequence(target)} for target in targets]}

    baseline_script_entity = "script.status_light_apply_baseline"
    quiet_script_entity = "script.status_light_apply_quiet"
    event_script_entity = "script.status_light_event"
    unsnooze_script_entity = "script.status_light_unsnooze"
    reconcile_automation_entity = "automation.status_light_reconcile"

    baseline_script_payload = {
        "alias": "Status Light Apply Baseline",
        "sequence": [baseline_parallel],
        "mode": "restart",
    }
    quiet_script_payload = {
        "alias": "Status Light Apply Quiet",
        "sequence": [quiet_parallel],
        "mode": "restart",
    }

    event_choices: List[dict] = []
    event_options: List[str] = []
    for event_key, event_cfg in events.items():
        event_name = str(event_key).strip()
        event_options.append(event_name)
        parallel_effect = {"parallel": [{"sequence": effect_sequence(target, event_cfg)} for target in targets]}
        event_choices.append(
            {
                "conditions": [{"condition": "template", "value_template": "{{ event_key == '" + event_name + "' }}"}],
                "sequence": [
                    parallel_effect,
                    {
                        "choose": [
                            {
                                "conditions": [
                                    {
                                        "condition": "template",
                                        "value_template": "{{ not is_state('" + snooze_timer_entity + "', 'active') }}",
                                    }
                                ],
                                "sequence": [
                                    {
                                        "action": "script.turn_on",
                                        "target": {"entity_id": baseline_script_entity},
                                    }
                                ],
                            }
                        ]
                    },
                ],
            }
        )

    event_script_payload = {
        "alias": "Status Light Event",
        "description": "Repo-managed semantic event entrypoint for status-light notifications.",
        "fields": {
            "event_key": {
                "name": "Event key",
                "description": "Semantic status-light event to emit.",
                "required": True,
                "selector": {"select": {"options": event_options}},
            }
        },
        "sequence": [
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ is_state('" + snooze_timer_entity + "', 'active') }}",
                            }
                        ],
                        "sequence": [],
                    }
                ],
                "default": [{"choose": event_choices}],
            }
        ],
        "mode": "queued",
        "max": 10,
    }

    test_script_specs = [
        ("script.status_light_test_boost_extend", "Status Light Test Boost Extend", "boost_extend"),
        ("script.status_light_test_boiler_off", "Status Light Test Boiler Off", "boiler_off"),
    ]
    snooze_script_specs = [
        ("script.status_light_snooze_30m", "Status Light Snooze 30m", "00:30:00"),
        ("script.status_light_snooze_60m", "Status Light Snooze 60m", "01:00:00"),
        ("script.status_light_snooze_120m", "Status Light Snooze 120m", "02:00:00"),
    ]
    until_next_day_time = str(status_cfg.get("snooze_until_next_day_time", "07:00:00")).strip()
    until_next_day_duration_template = (
        "{% set target = today_at('"
        + until_next_day_time
        + "') + timedelta(days=1) %}"
        + "{% set seconds = (as_timestamp(target) - as_timestamp(now())) | int(0) %}"
        + "{{ '%02d:%02d:%02d' | format(seconds // 3600, (seconds % 3600) // 60, seconds % 60) }}"
    )

    script_payloads: List[Tuple[str, dict]] = [
        (baseline_script_entity, baseline_script_payload),
        (quiet_script_entity, quiet_script_payload),
        (event_script_entity, event_script_payload),
        (
            unsnooze_script_entity,
            {
                "alias": "Status Light Unsnooze",
                "sequence": [
                    {
                        "action": "timer.cancel",
                        "target": {"entity_id": snooze_timer_entity},
                    },
                    {
                        "action": "script.turn_on",
                        "target": {"entity_id": baseline_script_entity},
                    },
                ],
                "mode": "restart",
            },
        ),
        (
            "script.status_light_snooze_until_next_day",
            {
                "alias": "Status Light Snooze Until Next Day",
                "sequence": [
                    {
                        "action": "timer.start",
                        "target": {"entity_id": snooze_timer_entity},
                        "data": {"duration": until_next_day_duration_template},
                    },
                    {
                        "action": "script.turn_on",
                        "target": {"entity_id": quiet_script_entity},
                    },
                ],
                "mode": "restart",
            },
        ),
    ]

    for script_entity, alias, duration in snooze_script_specs:
        script_payloads.append(
            (
                script_entity,
                {
                    "alias": alias,
                    "sequence": [
                        {
                            "action": "timer.start",
                            "target": {"entity_id": snooze_timer_entity},
                            "data": {"duration": duration},
                        },
                        {
                            "action": "script.turn_on",
                            "target": {"entity_id": quiet_script_entity},
                        },
                    ],
                    "mode": "restart",
                },
            )
        )

    for script_entity, alias, event_key in test_script_specs:
        script_payloads.append(
            (
                script_entity,
                {
                    "alias": alias,
                    "sequence": [
                        {
                            "action": "script.turn_on",
                            "target": {"entity_id": event_script_entity},
                            "data": {"variables": {"event_key": event_key}},
                        }
                    ],
                    "mode": "restart",
                },
            )
        )

    for script_entity, payload in script_payloads:
        script_id = script_entity.split(".", 1)[1]
        resp = requests.post(
            f"{base}/api/config/script/config/{script_id}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        print(f"Synced {script_entity}")

    reconcile_automation_id = reconcile_automation_entity.split(".", 1)[1]
    reconcile_payload = {
        "alias": "Status Light Reconcile",
        "description": "Repo-managed reconciliation for status-light baseline vs snooze state.",
        "mode": "restart",
        "triggers": [
            {"trigger": "homeassistant", "event": "start"},
            {"trigger": "event", "event_type": "timer.finished", "event_data": {"entity_id": snooze_timer_entity}},
        ],
        "conditions": [],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ is_state('" + snooze_timer_entity + "', 'active') }}",
                            }
                        ],
                        "sequence": [
                            {
                                "action": "script.turn_on",
                                "target": {"entity_id": quiet_script_entity},
                            }
                        ],
                    }
                ],
                "default": [
                    {
                        "action": "script.turn_on",
                        "target": {"entity_id": baseline_script_entity},
                    }
                ],
            }
        ],
    }
    automation_resp = requests.post(
        f"{base}/api/config/automation/config/{reconcile_automation_id}",
        headers=headers,
        json=reconcile_payload,
        timeout=20,
    )
    automation_resp.raise_for_status()
    print(f"Synced {reconcile_automation_entity}")

    requests.post(f"{base}/api/services/script/reload", headers=headers, json={}, timeout=20).raise_for_status()
    requests.post(f"{base}/api/services/automation/reload", headers=headers, json={}, timeout=20).raise_for_status()
    print("Reloaded status-light scripts and automations")

    resources = ws_call(base, token, "lovelace/resources")
    mushroom_present = any(
        isinstance(resource, dict) and "lovelace-mushroom" in str(resource.get("url", ""))
        for resource in resources
    )

    def operator_card(name: str, secondary: str, icon_name: str, icon_color: str, entity_id: str) -> Dict[str, Any]:
        if mushroom_present:
            return {
                "type": "custom:mushroom-template-card",
                "primary": name,
                "secondary": secondary,
                "icon": icon_name,
                "icon_color": icon_color,
                "multiline_secondary": True,
                "tap_action": {
                    "action": "call-service",
                    "service": "script.turn_on",
                    "target": {"entity_id": entity_id},
                },
            }
        return {
            "type": "button",
            "name": name,
            "icon": icon_name,
            "tap_action": {
                "action": "call-service",
                "service": "script.turn_on",
                "target": {"entity_id": entity_id},
            },
        }

    def target_card(entity_id: str, name: str) -> Dict[str, Any]:
        if mushroom_present:
            return {
                "type": "custom:mushroom-light-card",
                "entity": entity_id,
                "name": name,
                "show_brightness_control": False,
                "use_light_color": True,
                "collapsible_controls": False,
            }
        return {"type": "entities", "title": name, "entities": [entity_id]}

    view_cards: List[Dict[str, Any]] = []
    if mushroom_present:
        view_cards.append(
            {
                "type": "custom:mushroom-chips-card",
                "chips": [
                    {
                        "type": "template",
                        "icon": "mdi:led-strip-variant",
                        "icon_color": "{{ 'amber' if is_state('" + snooze_timer_entity + "', 'active') else 'green' }}",
                        "content": "{{ 'Snoozed' if is_state('" + snooze_timer_entity + "', 'active') else 'Live' }}",
                    },
                    {
                        "type": "template",
                        "icon": "mdi:timer-outline",
                        "content": "{% if is_state('"
                        + snooze_timer_entity
                        + "', 'active') %}Until {{ as_timestamp(state_attr('"
                        + snooze_timer_entity
                        + "', 'finishes_at')) | timestamp_custom('%H:%M') }}{% else %}No snooze{% endif %}",
                    },
                ],
            }
        )
    view_cards.extend(
        [
            {
                "type": "grid",
                "title": "Targets",
                "columns": 2,
                "square": False,
                "cards": [
                    target_card(str(target.get("entity_id", "")).strip(), str(target.get("name", str(target.get("entity_id", "")).strip())).strip())
                    for target in targets
                ],
            },
            {
                "type": "entities",
                "title": "Status Light State",
                "entities": [snooze_timer_entity],
            },
            {
                "type": "grid",
                "title": "Operator Controls",
                "columns": 3,
                "square": False,
                "cards": [
                    operator_card("Apply Baseline", "Restore live baseline", "mdi:lightbulb-auto", "green", baseline_script_entity),
                    operator_card("Test Boost Extend", "Emit semantic test event", "mdi:fire", "red", "script.status_light_test_boost_extend"),
                    operator_card("Test Boiler Off", "Emit semantic test event", "mdi:water-boiler-off", "blue", "script.status_light_test_boiler_off"),
                    operator_card("Snooze 30m", "Suppress events for 30 minutes", "mdi:timer-outline", "amber", "script.status_light_snooze_30m"),
                    operator_card("Snooze 60m", "Suppress events for 1 hour", "mdi:timer-sand", "amber", "script.status_light_snooze_60m"),
                    operator_card("Snooze 120m", "Suppress events for 2 hours", "mdi:timer-sand-complete", "amber", "script.status_light_snooze_120m"),
                    operator_card("Until Next Day", "Suppress until " + until_next_day_time, "mdi:weather-night", "amber", "script.status_light_snooze_until_next_day"),
                    operator_card("Unsnooze", "Restore baseline immediately", "mdi:bell-ring", "green", unsnooze_script_entity),
                ],
            },
        ]
    )

    dashboard_view = {
        "title": title,
        "path": view_path,
        "icon": icon,
        "cards": view_cards,
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
            views[idx] = dashboard_view
            replaced = True
            break
    if not replaced:
        views.append(dashboard_view)
    lovelace_config["views"] = views
    ws_call(base, token, "lovelace/config/save", url_path=dashboard_url_path, config=lovelace_config)
    print(f"{'Updated' if replaced else 'Created'} Status Lights dashboard view at /{dashboard_url_path}/{view_path}")


def build_heating_demand_template(
    climate_entities: list,
    deadband_c: float,
    hvac_action_max_above_target_c: float,
    invert: bool = False,
) -> str:
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
            (
                "      (hvac_action == 'heating' and "
                "(current is not number or target is not number or current < "
                f"(target + {hvac_action_max_above_target_c})))"
            ),
            f"      or (current is number and target is number and (target - current) >= {deadband_c})",
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


def slugify_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def normalize_hue_trigger_command(trigger_subtype: str) -> str:
    normalized = trigger_subtype.strip().lower()
    alias_map = {
        "turn_off": "off_short_release",
        "off": "off_short_release",
        "turn_on": "on_short_release",
        "on": "on_short_release",
    }
    return alias_map.get(normalized, normalized)


def subtract_minutes(time_str: str, minutes: int) -> str:
    return (datetime.strptime(time_str, "%H:%M:%S") - timedelta(minutes=minutes)).strftime("%H:%M:%S")


def normalize_weekdays(weekdays: List[str], field_name: str) -> List[str]:
    normalized: List[str] = []
    for token in weekdays:
        key = str(token).strip().lower()[:3]
        if key not in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
            raise RuntimeError(f"Invalid weekday '{token}' in {field_name}")
        normalized.append(key)
    return normalized


def cmd_sync_heating_control() -> None:
    cfg, base, token = ha_auth_from_config()
    dashboard_cfg = cfg.get("home_assistant", {}).get("heating_dashboard", {})
    boiler_entity = dashboard_cfg.get("boiler_entity")
    climate_entities = dashboard_cfg.get("climate_entities", [])
    if not boiler_entity or not climate_entities:
        raise RuntimeError(
            "home_assistant.heating_dashboard.boiler_entity and climate_entities must be set."
        )

    groups_cfg = dashboard_cfg.get("groups", {})
    groups = {
        "house": groups_cfg.get("house", climate_entities),
        "upstairs": groups_cfg.get("upstairs", []),
        "downstairs": groups_cfg.get("downstairs", []),
    }
    default_bulk_temp = float(dashboard_cfg.get("bulk_set_temperature_c", 20.0))
    temp_helpers = dashboard_cfg.get("temp_helpers", {})
    house_target_entity = temp_helpers.get("house", "input_number.house_target")
    upstairs_target_entity = temp_helpers.get("upstairs", "input_number.upstairs_target")
    downstairs_target_entity = temp_helpers.get("downstairs", "input_number.downstairs_target")

    control_cfg = cfg.get("home_assistant", {}).get("heating_control", {})
    deadband_c = float(control_cfg.get("deadband_c", 0.3))
    hvac_action_max_above_target_c = float(control_cfg.get("hvac_action_max_above_target_c", 0.0))
    on_for = control_cfg.get("on_for", "00:02:00")
    off_for = control_cfg.get("off_for", "00:07:00")
    min_on_seconds = int(control_cfg.get("min_on_seconds", 480))
    min_off_seconds = int(control_cfg.get("min_off_seconds", 300))
    hard_off_windows = control_cfg.get("hard_off_windows", [])
    schedule_events = control_cfg.get("schedule_events", [])
    remote_heating_controls = cfg.get("home_assistant", {}).get("remote_heating_controls", [])

    def unique_entities(items: list) -> list:
        seen = set()
        out = []
        for entity_id in items:
            if entity_id not in seen:
                seen.add(entity_id)
                out.append(entity_id)
        return out

    def resolve_targets(targets: list) -> list:
        resolved = []
        for target in targets:
            target_str = str(target)
            if target_str in groups:
                resolved.extend(groups[target_str])
            elif target_str.startswith("climate."):
                resolved.append(target_str)
            else:
                raise RuntimeError(
                    f"Invalid heating target '{target_str}'. Use a climate entity_id or one of: {', '.join(groups.keys())}"
                )
        return unique_entities(resolved)

    def climate_set_actions(entities: list, temperature_c: Any) -> list:
        return [
            {
                "action": "climate.set_hvac_mode",
                "target": {"entity_id": entities},
                "data": {"hvac_mode": "heat"},
            },
            {
                "action": "climate.set_temperature",
                "target": {"entity_id": entities},
                "data": {"temperature": temperature_c},
            },
        ]

    def climate_off_actions(entities: list) -> list:
        return [
            {
                "action": "climate.set_hvac_mode",
                "target": {"entity_id": entities},
                "data": {"hvac_mode": "off"},
            }
        ]

    boost_timers_by_target: dict[str, list[str]] = {}
    for control in remote_heating_controls:
        try:
            timer_entity = boost_timer_entity(control)
        except RuntimeError:
            continue
        for target in [str(entity).strip() for entity in control.get("targets", []) if str(entity).strip()]:
            boost_timers_by_target.setdefault(target, []).append(timer_entity)

    def boost_inactive_template(entity_id: str) -> str:
        timers = boost_timers_by_target.get(entity_id, [])
        if not timers:
            return "{{ true }}"
        checks = " and ".join(f"is_state('{timer}', 'idle')" for timer in timers)
        return "{{ " + checks + " }}"

    def any_boost_active_template(entities: list) -> str:
        timers = unique_entities(
            timer
            for entity_id in entities
            for timer in boost_timers_by_target.get(entity_id, [])
        )
        if not timers:
            return "{{ false }}"
        checks = " or ".join(f"is_state('{timer}', 'active')" for timer in timers)
        return "{{ " + checks + " }}"

    def climate_off_actions_respecting_boosts(entities: list) -> list:
        actions: list[dict] = []
        for entity_id in entities:
            actions.append(
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": boost_inactive_template(entity_id),
                                }
                            ],
                            "sequence": climate_off_actions([entity_id]),
                        }
                    ]
                }
            )
        return actions

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    house_entities = resolve_targets(["house"])
    upstairs_entities = resolve_targets(["upstairs"]) if groups.get("upstairs") else []
    downstairs_entities = resolve_targets(["downstairs"]) if groups.get("downstairs") else []

    lockout_enable_script = {
        "alias": "Heating Lockout Enable",
        "sequence": [
            {
                "action": "automation.turn_off",
                "target": {"entity_id": "automation.heating_boiler_on_demand"},
            },
            {"action": "switch.turn_off", "target": {"entity_id": boiler_entity}},
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

    scripts_to_sync = {
        "heating_lockout_enable": lockout_enable_script,
        "heating_lockout_disable": lockout_disable_script,
        "heating_set_house_temp": {
            "alias": "Heating Set House Temperature",
            "sequence": climate_set_actions(
                house_entities,
                (
                    f"{{{{ target_temp | default(states('{house_target_entity}')) "
                    f"| float({default_bulk_temp}) }}}}"
                ),
            ),
            "mode": "single",
        },
        "heating_set_upstairs_temp": {
            "alias": "Heating Set Upstairs Temperature",
            "sequence": climate_set_actions(
                upstairs_entities,
                (
                    f"{{{{ target_temp | default(states('{upstairs_target_entity}')) "
                    f"| float({default_bulk_temp}) }}}}"
                ),
            ),
            "mode": "single",
        },
        "heating_set_downstairs_temp": {
            "alias": "Heating Set Downstairs Temperature",
            "sequence": climate_set_actions(
                downstairs_entities,
                (
                    f"{{{{ target_temp | default(states('{downstairs_target_entity}')) "
                    f"| float({default_bulk_temp}) }}}}"
                ),
            ),
            "mode": "single",
        },
        "heating_all_off": {
            "alias": "Heating All Off",
            "sequence": climate_off_actions(house_entities),
            "mode": "single",
        },
    }

    for script_id, payload in scripts_to_sync.items():
        response = requests.post(
            f"{base}/api/config/script/config/{script_id}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        print(f"Synced script.{script_id}")

    demand_template = build_heating_demand_template(
        climate_entities,
        deadband_c,
        hvac_action_max_above_target_c,
    )
    no_demand_template = build_heating_demand_template(
        climate_entities,
        deadband_c,
        hvac_action_max_above_target_c,
        invert=True,
    )
    hard_off_entities = unique_entities(
        [
            entity_id
            for window in hard_off_windows
            for entity_id in resolve_targets(window.get("targets", ["house"]))
        ]
    )
    hard_off_window_template = build_schedule_template(hard_off_windows) if hard_off_windows else "{{ false }}"

    on_automation = {
        "alias": "Heating Boiler On Demand",
        "description": "Turn boiler on when any configured TRV demands heat; includes periodic fallback evaluation.",
        "mode": "single",
        "triggers": [
            {"trigger": "template", "value_template": demand_template, "for": on_for},
            {"trigger": "homeassistant", "event": "start"},
            {"trigger": "time_pattern", "minutes": "/1"},
        ],
        "conditions": [
            {"condition": "state", "entity_id": boiler_entity, "state": "off"},
            {"condition": "template", "value_template": demand_template},
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
        "description": "Turn boiler off when all configured TRVs are satisfied; includes periodic fallback evaluation.",
        "mode": "single",
        "triggers": [
            {"trigger": "template", "value_template": no_demand_template, "for": off_for},
            {"trigger": "homeassistant", "event": "start"},
            {"trigger": "time_pattern", "minutes": "/1"},
        ],
        "conditions": [
            {"condition": "state", "entity_id": boiler_entity, "state": "on"},
            {"condition": "template", "value_template": no_demand_template},
            {
                "condition": "template",
                "value_template": (
                    f"{{{{ (as_timestamp(now()) - as_timestamp(states['{boiler_entity}'].last_changed, 0)) >= {min_on_seconds} }}}}"
                ),
            },
        ],
        "actions": [{"action": "switch.turn_off", "target": {"entity_id": boiler_entity}}],
    }
    house_slider_automation = {
        "alias": "Heating Apply House Target On Change",
        "description": "Apply house target helper value to all house TRVs when slider changes.",
        "mode": "restart",
        "triggers": [{"trigger": "state", "entity_id": house_target_entity, "for": "00:00:01"}],
        "conditions": [],
        "actions": [
            {
                "action": "script.turn_on",
                "target": {"entity_id": "script.heating_set_house_temp"},
                "data": {"variables": {"target_temp": "{{ trigger.to_state.state }}"}},
            }
        ],
    }
    upstairs_slider_automation = {
        "alias": "Heating Apply Upstairs Target On Change",
        "description": "Apply upstairs target helper value to upstairs TRVs when slider changes.",
        "mode": "restart",
        "triggers": [{"trigger": "state", "entity_id": upstairs_target_entity, "for": "00:00:01"}],
        "conditions": [],
        "actions": [
            {
                "action": "script.turn_on",
                "target": {"entity_id": "script.heating_set_upstairs_temp"},
                "data": {"variables": {"target_temp": "{{ trigger.to_state.state }}"}},
            }
        ],
    }
    downstairs_slider_automation = {
        "alias": "Heating Apply Downstairs Target On Change",
        "description": "Apply downstairs target helper value to downstairs TRVs when slider changes.",
        "mode": "restart",
        "triggers": [{"trigger": "state", "entity_id": downstairs_target_entity, "for": "00:00:01"}],
        "conditions": [],
        "actions": [
            {
                "action": "script.turn_on",
                "target": {"entity_id": "script.heating_set_downstairs_temp"},
                "data": {"variables": {"target_temp": "{{ trigger.to_state.state }}"}},
            }
        ],
    }
    hard_off_automation = {
        "alias": "Heating Enforce Hard Off Window",
        "description": "Force configured TRVs and boiler off during hard-off windows to override stray vendor schedules, except while a repo-managed boost is actively running for a target.",
        "mode": "restart",
        "triggers": [
            {"trigger": "homeassistant", "event": "start"},
            {"trigger": "template", "value_template": hard_off_window_template, "for": "00:00:01"},
            {"trigger": "time_pattern", "minutes": "/1"},
            {"trigger": "state", "entity_id": hard_off_entities},
            {"trigger": "state", "entity_id": boiler_entity, "to": "on"},
        ],
        "conditions": [{"condition": "template", "value_template": hard_off_window_template}],
        "actions": [
            *climate_off_actions_respecting_boosts(hard_off_entities),
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ not (%s) }}" % any_boost_active_template(hard_off_entities)[3:-3],
                            }
                        ],
                        "sequence": [
                            {"action": "switch.turn_off", "target": {"entity_id": boiler_entity}},
                        ],
                    }
                ]
            },
        ],
    }

    automations_to_sync = [
        ("automation.heating_boiler_on_demand", on_automation),
        ("automation.heating_boiler_off_when_satisfied", off_automation),
        ("automation.heating_apply_house_target_on_change", house_slider_automation),
        ("automation.heating_apply_upstairs_target_on_change", upstairs_slider_automation),
        ("automation.heating_apply_downstairs_target_on_change", downstairs_slider_automation),
    ]
    if hard_off_windows:
        automations_to_sync.append(("automation.heating_enforce_hard_off_window", hard_off_automation))

    desired_managed_automation_ids = {entity_id for entity_id, _ in automations_to_sync}
    for entity_id, payload in automations_to_sync:
        response = requests.post(
            f"{base}/api/config/automation/config/{entity_id}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        print(f"Synced {entity_id}")

    desired_event_entities = set()
    for event in schedule_events:
        event_name = str(event.get("name", "unnamed event")).strip()
        event_slug = slugify_name(event_name)
        entity_id = f"automation.heating_event_{event_slug}"
        desired_event_entities.add(entity_id)
        desired_managed_automation_ids.add(entity_id)

        event_time = str(event.get("time", "")).strip()
        weekdays = [str(day).strip().lower()[:3] for day in event.get("weekdays", [])]
        action = str(event.get("action", "")).strip().lower()
        target_entities = resolve_targets(event.get("targets", []))

        if not event_time or not weekdays or not target_entities:
            raise RuntimeError(f"Incomplete schedule event '{event_name}'")

        if action == "set_temp":
            if "temperature_c" not in event:
                raise RuntimeError(f"schedule event '{event_name}' missing temperature_c")
            event_actions = climate_set_actions(target_entities, float(event["temperature_c"]))
        elif action == "off":
            event_actions = climate_off_actions_respecting_boosts(target_entities)
        else:
            raise RuntimeError(f"schedule event '{event_name}' has unsupported action '{action}'")

        payload = {
            "alias": f"Heating Event - {event_name}",
            "description": (
                "Repo-managed heating schedule event."
                if action != "off"
                else "Repo-managed heating schedule event that skips targets with an active repo-managed boost."
            ),
            "mode": "single",
            "triggers": [{"trigger": "time", "at": event_time}],
            "conditions": [{"condition": "time", "weekday": weekdays}],
            "actions": event_actions,
        }
        response = requests.post(
            f"{base}/api/config/automation/config/{entity_id}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        print(f"Synced {entity_id}")

    states_response = requests.get(f"{base}/api/states", headers=headers, timeout=20)
    states_response.raise_for_status()
    all_entities = [state.get("entity_id", "") for state in states_response.json()]

    legacy_automation_ids = {
        "automation.heating_boiler_off_outside_schedule",
        "automation.heating_schedule_gate",
        "automation.heating_override_gate",
    }
    for entity_id in all_entities:
        if entity_id.startswith("automation.heating_schedule_start_") or entity_id.startswith(
            "automation.heating_schedule_end_"
        ):
            legacy_automation_ids.add(entity_id)
        if entity_id.startswith("automation.heating_") and entity_id not in desired_managed_automation_ids:
            legacy_automation_ids.add(entity_id)

    for entity_id in sorted(legacy_automation_ids):
        delete_response = requests.delete(
            f"{base}/api/config/automation/config/{entity_id}",
            headers=headers,
            timeout=20,
        )
        if delete_response.status_code in {200, 204}:
            print(f"Deleted {entity_id}")
        elif delete_response.status_code == 400:
            print(f"Skipped deleting {entity_id} (not storage-managed)")
        elif delete_response.status_code != 404:
            delete_response.raise_for_status()

    for script_id in ["heating_override_enable", "heating_override_disable", "heating_override_boost_1h"]:
        delete_response = requests.delete(
            f"{base}/api/config/script/config/{script_id}",
            headers=headers,
            timeout=20,
        )
        if delete_response.status_code in {200, 204}:
            print(f"Deleted script.{script_id}")
        elif delete_response.status_code == 400:
            print(f"Skipped deleting script.{script_id} (not storage-managed)")
        elif delete_response.status_code != 404:
            delete_response.raise_for_status()

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


def cmd_sync_light_routines() -> None:
    cfg, base, token = ha_auth_from_config()
    routines = cfg.get("home_assistant", {}).get("light_routines", [])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    desired_entities = set()

    for idx, routine in enumerate(routines):
        name = str(routine.get("name", f"Light Routine {idx + 1}")).strip()
        target_entity = str(routine.get("target_entity") or routine.get("light_entity") or "").strip()
        automation_entity = str(
            routine.get("automation_entity", f"automation.light_routine_{slugify_name(name)}")
        ).strip()
        weekdays = normalize_weekdays(routine.get("weekdays", []), f"light routine '{name}' weekdays")
        start_date = str(routine.get("start_date", "")).strip()
        end_date = str(routine.get("end_date", "")).strip()
        routine_type = str(routine.get("type", "sunrise")).strip().lower()

        if not target_entity or not automation_entity or not weekdays:
            raise RuntimeError(f"Incomplete light routine '{name}'")

        desired_entities.add(automation_entity)
        conditions: List[dict] = [{"condition": "time", "weekday": weekdays}]
        if start_date:
            conditions.append(
                {
                    "condition": "template",
                    "value_template": f"{{{{ now().date() >= as_datetime('{start_date}').date() }}}}",
                }
            )
        if end_date:
            conditions.append(
                {
                    "condition": "template",
                    "value_template": f"{{{{ now().date() <= as_datetime('{end_date}').date() }}}}",
                }
            )

        if routine_type == "sunrise":
            end_time = str(routine.get("end_time", "")).strip()
            duration_minutes = int(routine.get("duration_minutes", 0))
            start_brightness_pct = int(routine.get("start_brightness_pct", 1))
            end_brightness_pct = int(routine.get("end_brightness_pct", 100))
            rgb_stops = routine.get("rgb_stops", [])
            start_kelvin = int(routine.get("start_color_temp_kelvin", 2000))
            end_kelvin = int(routine.get("end_color_temp_kelvin", 6500))

            if not end_time or duration_minutes <= 0:
                raise RuntimeError(f"Incomplete sunrise light routine '{name}'")
            if rgb_stops and len(rgb_stops) != duration_minutes + 1:
                raise RuntimeError(
                    f"light routine '{name}' rgb_stops must contain exactly {duration_minutes + 1} entries"
                )

            start_time = subtract_minutes(end_time, duration_minutes)
            actions: List[dict] = []
            for step in range(duration_minutes + 1):
                ratio = step / duration_minutes
                brightness_pct = int(
                    round(start_brightness_pct + (end_brightness_pct - start_brightness_pct) * ratio)
                )
                data: Dict[str, Any] = {
                    "brightness_pct": brightness_pct,
                    "transition": 55,
                }
                if rgb_stops:
                    data["rgb_color"] = [int(component) for component in rgb_stops[step]]
                else:
                    color_temp_kelvin = int(round(start_kelvin + (end_kelvin - start_kelvin) * ratio))
                    data["color_temp_kelvin"] = color_temp_kelvin
                actions.append(
                    {
                        "action": "light.turn_on",
                        "target": {"entity_id": target_entity},
                        "data": data,
                    }
                )
                if step < duration_minutes:
                    actions.append({"delay": "00:01:00"})

            payload = {
                "alias": name,
                "description": "Repo-managed light routine.",
                "mode": "restart",
                "triggers": [{"trigger": "time", "at": start_time}],
                "conditions": conditions,
                "actions": actions,
            }
        elif routine_type == "fixed_window":
            start_time = str(routine.get("start_time", "")).strip()
            end_time = str(routine.get("end_time", "")).strip()
            start_weekdays = normalize_weekdays(
                routine.get("start_weekdays", weekdays), f"light routine '{name}' start_weekdays"
            )
            end_weekdays = normalize_weekdays(
                routine.get("end_weekdays", weekdays), f"light routine '{name}' end_weekdays"
            )
            on_service = str(routine.get("on_service", "")).strip() or (
                "switch.turn_on" if target_entity.startswith("switch.") else "light.turn_on"
            )
            off_service = str(routine.get("off_service", "")).strip() or (
                "switch.turn_off" if target_entity.startswith("switch.") else "light.turn_off"
            )
            on_data = routine.get("on_data", {})
            off_data = routine.get("off_data", {})
            last_on_date = str(routine.get("last_on_date") or end_date).strip()
            last_off_date = str(routine.get("last_off_date") or end_date).strip()

            if not start_time or not end_time:
                raise RuntimeError(f"Incomplete fixed_window light routine '{name}'")

            start_conditions: List[dict] = [
                {"condition": "trigger", "id": "start"},
                {"condition": "time", "weekday": start_weekdays},
            ]
            end_conditions: List[dict] = [
                {"condition": "trigger", "id": "end"},
                {"condition": "time", "weekday": end_weekdays},
            ]
            if start_date:
                start_conditions.append(
                    {
                        "condition": "template",
                        "value_template": f"{{{{ now().date() >= as_datetime('{start_date}').date() }}}}",
                    }
                )
                end_conditions.append(
                    {
                        "condition": "template",
                        "value_template": f"{{{{ now().date() >= as_datetime('{start_date}').date() }}}}",
                    }
                )
            if last_on_date:
                start_conditions.append(
                    {
                        "condition": "template",
                        "value_template": f"{{{{ now().date() <= as_datetime('{last_on_date}').date() }}}}",
                    }
                )
            if last_off_date:
                end_conditions.append(
                    {
                        "condition": "template",
                        "value_template": f"{{{{ now().date() <= as_datetime('{last_off_date}').date() }}}}",
                    }
                )

            payload = {
                "alias": name,
                "description": "Repo-managed light routine.",
                "mode": "restart",
                "triggers": [
                    {"trigger": "time", "id": "start", "at": start_time},
                    {"trigger": "time", "id": "end", "at": end_time},
                ],
                "conditions": [],
                "actions": [
                    {
                        "choose": [
                            {
                                "conditions": start_conditions,
                                "sequence": [
                                    {
                                        "action": on_service,
                                        "target": {"entity_id": target_entity},
                                        "data": on_data,
                                    }
                                ],
                            },
                            {
                                "conditions": end_conditions,
                                "sequence": [
                                    {
                                        "action": off_service,
                                        "target": {"entity_id": target_entity},
                                        "data": off_data,
                                    }
                                ],
                            },
                        ]
                    }
                ],
            }
        else:
            raise RuntimeError(f"Unsupported light routine type '{routine_type}' for '{name}'")

        response = requests.post(
            f"{base}/api/config/automation/config/{automation_entity}",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        print(f"Synced {automation_entity}")

    states_response = requests.get(f"{base}/api/states", headers=headers, timeout=20)
    states_response.raise_for_status()
    all_entities = [state.get("entity_id", "") for state in states_response.json()]
    for entity_id in sorted(
        entity_id
        for entity_id in all_entities
        if entity_id.startswith("automation.light_routine_") and entity_id not in desired_entities
    ):
        delete_response = requests.delete(
            f"{base}/api/config/automation/config/{entity_id}",
            headers=headers,
            timeout=20,
        )
        if delete_response.status_code in {200, 204}:
            print(f"Deleted {entity_id}")
        elif delete_response.status_code == 400:
            print(f"Skipped deleting {entity_id} (not storage-managed)")
        elif delete_response.status_code != 404:
            delete_response.raise_for_status()

    requests.post(f"{base}/api/services/automation/reload", headers=headers, json={}, timeout=20).raise_for_status()
    print("Reloaded automations")


def cmd_sync_hue_scenes() -> None:
    cfg, base, token = ha_auth_from_config()
    hue_cfg = cfg.get("home_assistant", {}).get("hue_scene_cycle", {})
    if not hue_cfg:
        print("No home_assistant.hue_scene_cycle configured; nothing to do.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    remote_identifier = str(hue_cfg.get("remote_identifier", "")).upper()
    light_entity = str(hue_cfg.get("light_entity", "")).strip()
    automation_entity = str(hue_cfg.get("automation_entity", "automation.living_room_hue_scene_cycle")).strip()
    trigger_subtype = str(hue_cfg.get("trigger_subtype", "turn_off")).strip()
    trigger_command = normalize_hue_trigger_command(trigger_subtype)
    scenes = hue_cfg.get("scenes", [])

    if not remote_identifier or not light_entity or not scenes:
        raise RuntimeError("hue_scene_cycle config missing required fields")
    if not trigger_command:
        raise RuntimeError("hue_scene_cycle.trigger_subtype must not be empty")

    devices = ws_call(base, token, "config/device_registry/list")
    remote_device = next(
        (
            d
            for d in devices
            if any(
                pair
                and len(pair) == 2
                and pair[0] == "zha"
                and str(pair[1]).upper() == remote_identifier
                for pair in d.get("identifiers", [])
            )
        ),
        None,
    )
    if not remote_device:
        raise RuntimeError(f"Could not find ZHA remote with IEEE {remote_identifier}")

    scene_names = [str(scene["name"]).strip() for scene in scenes if str(scene.get("name", "")).strip()]
    if not scene_names:
        raise RuntimeError("hue_scene_cycle.scenes must include at least one named scene")
    scene_map: Dict[str, Dict[str, Any]] = {}
    for scene in scenes:
        scene_name = str(scene["name"]).strip()
        if not scene_name:
            continue
        light_data: Dict[str, Any] = {
            "brightness_pct": int(scene.get("brightness_pct", 70)),
            "transition": 0.7,
        }
        if "rgb_color" in scene and scene.get("rgb_color") is not None:
            light_data["rgb_color"] = scene.get("rgb_color")
        elif "color_temp_kelvin" in scene and scene.get("color_temp_kelvin") is not None:
            light_data["color_temp_kelvin"] = int(scene.get("color_temp_kelvin", 3000))
        scene_map[scene_name.lower()] = light_data

    relax = scene_map.get("relax", {"brightness_pct": 45, "color_temp_kelvin": 2200, "transition": 0.7})
    read = scene_map.get("read", {"brightness_pct": 80, "color_temp_kelvin": 2900, "transition": 0.7})
    concentrate = scene_map.get("concentrate", {"brightness_pct": 90, "color_temp_kelvin": 4300, "transition": 0.7})
    energize = scene_map.get("energize", {"brightness_pct": 100, "color_temp_kelvin": 6500, "transition": 0.7})
    nightlight = scene_map.get("nightlight", {"brightness_pct": 15, "rgb_color": [255, 140, 80], "transition": 0.7})

    automation_id = automation_entity.split(".", 1)[1]
    automation_payload = {
        "alias": "Living Room Hue Scene Cycle",
        "description": f"Cycle popular Hue-like scenes when ZHA command '{trigger_command}' fires.",
        "mode": "single",
        "triggers": [
            {
                "trigger": "event",
                "event_type": "zha_event",
                "event_data": {
                    "device_ieee": remote_identifier.lower(),
                    "command": trigger_command,
                },
            }
        ],
        "conditions": [],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [{"condition": "state", "entity_id": light_entity, "state": "off"}],
                        "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": relax}],
                    },
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": (
                                    "{{ is_state('"
                                    + light_entity
                                    + "', 'on') and (state_attr('"
                                    + light_entity
                                    + "', 'color_temp_kelvin') | int(0)) <= 2400 }}"
                                ),
                            }
                        ],
                        "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": read}],
                    },
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": (
                                    "{{ is_state('"
                                    + light_entity
                                    + "', 'on') and (state_attr('"
                                    + light_entity
                                    + "', 'color_temp_kelvin') | int(0)) > 2400 and (state_attr('"
                                    + light_entity
                                    + "', 'color_temp_kelvin') | int(0)) <= 3400 }}"
                                ),
                            }
                        ],
                        "sequence": [
                            {"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": concentrate}
                        ],
                    },
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": (
                                    "{{ is_state('"
                                    + light_entity
                                    + "', 'on') and (state_attr('"
                                    + light_entity
                                    + "', 'color_temp_kelvin') | int(0)) > 3400 and (state_attr('"
                                    + light_entity
                                    + "', 'color_temp_kelvin') | int(0)) <= 5200 }}"
                                ),
                            }
                        ],
                        "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": energize}],
                    },
                    {
                        "conditions": [{"condition": "template", "value_template": "{{ is_state('" + light_entity + "', 'on') }}"}],
                        "sequence": [
                            {"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": nightlight}
                        ],
                    },
                ],
                "default": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": relax}],
            }
        ],
    }
    resp = requests.post(
        f"{base}/api/config/automation/config/{automation_id}",
        headers=headers,
        json=automation_payload,
        timeout=20,
    )
    resp.raise_for_status()
    print(f"Synced {automation_entity}")

    requests.post(f"{base}/api/services/automation/reload", headers=headers, json={}, timeout=20).raise_for_status()
    print("Reloaded automations")


def cmd_sync_remote_light_controls() -> None:
    cfg, base, token = ha_auth_from_config()
    controls = cfg.get("home_assistant", {}).get("remote_light_controls", [])
    if not controls:
        print("No home_assistant.remote_light_controls configured; nothing to do.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    devices = ws_call(base, token, "config/device_registry/list")

    for control in controls:
        name = str(control.get("name", "Remote Light Control")).strip()
        automation_entity = str(control.get("automation_entity", "")).strip()
        remote_identifier = str(control.get("remote_identifier", "")).upper()
        light_entity = str(control.get("light_entity", "")).strip()
        full_on = dict(control.get("full_on", {}))
        brightness_step_pct = int(control.get("brightness_step_pct", 20))
        scenes = control.get("scenes", [])

        if not automation_entity or not remote_identifier or not light_entity or not scenes:
            raise RuntimeError(f"Incomplete remote_light_controls entry '{name}'")

        remote_device = next(
            (
                d
                for d in devices
                if any(
                    pair
                    and len(pair) == 2
                    and pair[0] == "zha"
                    and str(pair[1]).upper() == remote_identifier
                    for pair in d.get("identifiers", [])
                )
            ),
            None,
        )
        if not remote_device:
            raise RuntimeError(f"Could not find ZHA remote with IEEE {remote_identifier}")

        scene_map: Dict[str, Dict[str, Any]] = {}
        for scene in scenes:
            scene_name = str(scene.get("name", "")).strip()
            if not scene_name:
                continue
            light_data: Dict[str, Any] = {
                "brightness_pct": int(scene.get("brightness_pct", 70)),
                "transition": 0.4,
            }
            if "rgb_color" in scene and scene.get("rgb_color") is not None:
                light_data["rgb_color"] = scene.get("rgb_color")
            elif "color_temp_kelvin" in scene and scene.get("color_temp_kelvin") is not None:
                light_data["color_temp_kelvin"] = int(scene.get("color_temp_kelvin", 3000))
            scene_map[scene_name.lower()] = light_data

        relax = scene_map.get("relax", {"brightness_pct": 45, "color_temp_kelvin": 2200, "transition": 0.4})
        read = scene_map.get("read", {"brightness_pct": 80, "color_temp_kelvin": 2900, "transition": 0.4})
        concentrate = scene_map.get(
            "concentrate", {"brightness_pct": 90, "color_temp_kelvin": 4300, "transition": 0.4}
        )
        energize = scene_map.get("energize", {"brightness_pct": 100, "color_temp_kelvin": 6500, "transition": 0.4})
        nightlight = scene_map.get("nightlight", {"brightness_pct": 15, "rgb_color": [255, 140, 80], "transition": 0.4})

        full_on_payload: Dict[str, Any] = {"brightness_pct": 100, "color_temp_kelvin": 4000, "transition": 0.4}
        full_on_payload.update(full_on)

        next_scene_action = {
            "choose": [
                {
                    "conditions": [{"condition": "state", "entity_id": light_entity, "state": "off"}],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": relax}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) <= 2400 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": read}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) > 2400 and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) <= 3400 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": concentrate}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) > 3400 and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) <= 5200 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": energize}],
                },
                {
                    "conditions": [{"condition": "template", "value_template": "{{ is_state('" + light_entity + "', 'on') }}"}],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": nightlight}],
                },
            ],
            "default": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": relax}],
        }

        previous_scene_action = {
            "choose": [
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'rgb_color') | default([], true)) == [255, 140, 80] }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": energize}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) > 5200 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": concentrate}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) > 3400 and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) <= 5200 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": read}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) > 2400 and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) <= 3400 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": relax}],
                },
                {
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": (
                                "{{ is_state('"
                                + light_entity
                                + "', 'on') and (state_attr('"
                                + light_entity
                                + "', 'color_temp_kelvin') | int(0)) <= 2400 }}"
                            ),
                        }
                    ],
                    "sequence": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": nightlight}],
                },
            ],
            "default": [{"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": nightlight}],
        }

        automation_id = automation_entity.split(".", 1)[1]
        automation_payload = {
            "alias": name,
            "description": "Repo-managed ZHA remote light control.",
            "mode": "single",
            "triggers": [
                {
                    "trigger": "device",
                    "domain": "zha",
                    "device_id": remote_device["id"],
                    "type": "remote_button_short_press",
                    "subtype": "turn_on",
                    "id": "toggle_on",
                },
                {
                    "trigger": "device",
                    "domain": "zha",
                    "device_id": remote_device["id"],
                    "type": "remote_button_short_press",
                    "subtype": "turn_off",
                    "id": "toggle_off",
                },
                {
                    "trigger": "device",
                    "domain": "zha",
                    "device_id": remote_device["id"],
                    "type": "remote_button_long_press",
                    "subtype": "dim_up",
                    "id": "brighten",
                },
                {
                    "trigger": "device",
                    "domain": "zha",
                    "device_id": remote_device["id"],
                    "type": "remote_button_long_press",
                    "subtype": "dim_down",
                    "id": "dim",
                },
                {
                    "trigger": "device",
                    "domain": "zha",
                    "device_id": remote_device["id"],
                    "type": "remote_button_short_press",
                    "subtype": "left",
                    "id": "scene_prev",
                },
                {
                    "trigger": "device",
                    "domain": "zha",
                    "device_id": remote_device["id"],
                    "type": "remote_button_short_press",
                    "subtype": "right",
                    "id": "scene_next",
                },
            ],
            "conditions": [],
            "actions": [
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ trigger.id in ['toggle_on', 'toggle_off'] and is_state('"
                                    + light_entity
                                    + "', 'off') }}",
                                }
                            ],
                            "sequence": [
                                {"action": "light.turn_on", "target": {"entity_id": light_entity}, "data": full_on_payload}
                            ],
                        },
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ trigger.id in ['toggle_on', 'toggle_off'] and is_state('"
                                    + light_entity
                                    + "', 'on') }}",
                                }
                            ],
                            "sequence": [{"action": "light.turn_off", "target": {"entity_id": light_entity}}],
                        },
                        {
                            "conditions": [{"condition": "trigger", "id": "brighten"}],
                            "sequence": [
                                {
                                    "action": "light.turn_on",
                                    "target": {"entity_id": light_entity},
                                    "data": {"brightness_step_pct": brightness_step_pct, "transition": 0.2},
                                }
                            ],
                        },
                        {
                            "conditions": [{"condition": "trigger", "id": "dim"}],
                            "sequence": [
                                {
                                    "action": "light.turn_on",
                                    "target": {"entity_id": light_entity},
                                    "data": {"brightness_pct": 30, "transition": 0.2},
                                }
                            ],
                        },
                        {
                            "conditions": [{"condition": "trigger", "id": "scene_prev"}],
                            "sequence": [previous_scene_action],
                        },
                        {
                            "conditions": [{"condition": "trigger", "id": "scene_next"}],
                            "sequence": [next_scene_action],
                        },
                    ]
                }
            ],
        }
        resp = requests.post(
            f"{base}/api/config/automation/config/{automation_id}",
            headers=headers,
            json=automation_payload,
            timeout=20,
        )
        resp.raise_for_status()
        print(f"Synced {automation_entity}")

    requests.post(f"{base}/api/services/automation/reload", headers=headers, json={}, timeout=20).raise_for_status()
    print("Reloaded automations")


def cmd_sync_remote_heating_controls() -> None:
    cfg, base, token = ha_auth_from_config()
    controls = cfg.get("home_assistant", {}).get("remote_heating_controls", [])
    if not controls:
        print("No home_assistant.remote_heating_controls configured; nothing to do.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    devices = ws_call(base, token, "config/device_registry/list")

    def flash_delay(seconds: float) -> str:
        if float(seconds).is_integer():
            return f"00:00:{int(seconds):02d}"
        return f"00:00:{seconds:04.1f}"

    def indicator_flash_sequence(
        relay_entity: str,
        light_entity: str,
        prefix: str,
        rgb_color: List[int],
        flash_count: int,
        flash_seconds: float,
    ) -> List[dict]:
        if not relay_entity or not light_entity:
            return []

        return [
            {
                "variables": {
                    f"{prefix}_relay_was_on": "{{ is_state('" + relay_entity + "', 'on') }}",
                    f"{prefix}_light_was_on": "{{ is_state('" + light_entity + "', 'on') }}",
                    f"{prefix}_light_brightness": "{{ state_attr('" + light_entity + "', 'brightness') }}",
                    f"{prefix}_light_color_mode": "{{ state_attr('" + light_entity + "', 'color_mode') }}",
                    f"{prefix}_light_xy_x": "{{ (state_attr('" + light_entity + "', 'xy_color') or [none, none])[0] }}",
                    f"{prefix}_light_xy_y": "{{ (state_attr('" + light_entity + "', 'xy_color') or [none, none])[1] }}",
                    f"{prefix}_light_color_temp_kelvin": "{{ state_attr('" + light_entity + "', 'color_temp_kelvin') }}",
                }
            },
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "state",
                                "entity_id": relay_entity,
                                "state": "off",
                            }
                        ],
                        "sequence": [
                            {
                                "action": "switch.turn_on",
                                "target": {"entity_id": relay_entity},
                            },
                            {"delay": "00:00:02"},
                        ],
                    }
                ]
            },
            {
                "repeat": {
                    "count": flash_count,
                    "sequence": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": light_entity},
                            "data": {
                                "rgb_color": rgb_color,
                                "brightness_pct": 100,
                                "transition": 0,
                            },
                        },
                        {"delay": flash_delay(flash_seconds)},
                        {"action": "light.turn_off", "target": {"entity_id": light_entity}},
                        {"delay": flash_delay(flash_seconds)},
                    ],
                }
            },
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ "
                                + prefix
                                + "_light_was_on and "
                                + prefix
                                + "_light_color_mode == 'color_temp' and "
                                + prefix
                                + "_light_color_temp_kelvin is not none }}",
                            }
                        ],
                        "sequence": [
                            {
                                "action": "light.turn_on",
                                "target": {"entity_id": light_entity},
                                "data": {
                                    "brightness": "{{ " + prefix + "_light_brightness | int(255) }}",
                                    "color_temp_kelvin": "{{ " + prefix + "_light_color_temp_kelvin | int }}",
                                    "transition": 0,
                                },
                            }
                        ],
                    },
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ "
                                + prefix
                                + "_light_was_on and "
                                + prefix
                                + "_light_color_mode != 'color_temp' and "
                                + prefix
                                + "_light_xy_x is not none and "
                                + prefix
                                + "_light_xy_y is not none }}",
                            }
                        ],
                        "sequence": [
                            {
                                "action": "light.turn_on",
                                "target": {"entity_id": light_entity},
                                "data": {
                                    "brightness": "{{ " + prefix + "_light_brightness | int(255) }}",
                                    "xy_color": [
                                        "{{ " + prefix + "_light_xy_x | float }}",
                                        "{{ " + prefix + "_light_xy_y | float }}",
                                    ],
                                    "transition": 0,
                                },
                            }
                        ],
                    },
                ],
                "default": [
                    {
                        "choose": [
                            {
                                "conditions": [
                                    {
                                        "condition": "template",
                                        "value_template": "{{ " + prefix + "_light_was_on }}",
                                    }
                                ],
                                "sequence": [
                                    {
                                        "action": "light.turn_on",
                                        "target": {"entity_id": light_entity},
                                        "data": {
                                            "brightness": "{{ " + prefix + "_light_brightness | int(255) }}",
                                            "transition": 0,
                                        },
                                    }
                                ],
                            }
                        ],
                        "default": [
                            {
                                "action": "light.turn_off",
                                "target": {"entity_id": light_entity},
                            }
                        ],
                    }
                ],
            },
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ not " + prefix + "_relay_was_on }}",
                            }
                        ],
                        "sequence": [
                            {
                                "action": "switch.turn_off",
                                "target": {"entity_id": relay_entity},
                            }
                        ],
                    }
                ]
            },
        ]

    for control in controls:
        name = str(control.get("name", "Remote Heating Control")).strip()
        automation_entity = str(control.get("automation_entity", "")).strip()
        remote_identifier = str(control.get("remote_identifier", "")).upper()
        trigger_type = str(control.get("trigger_type", "remote_button_short_press")).strip()
        trigger_subtype = str(control.get("trigger_subtype", "turn_on")).strip()
        cancel_trigger_type = str(control.get("cancel_trigger_type", "remote_button_short_press")).strip()
        cancel_trigger_subtype = str(control.get("cancel_trigger_subtype", "turn_off")).strip()
        trigger_command = str(control.get("trigger_command", "")).strip()
        cancel_command = str(control.get("cancel_command", "")).strip()
        trigger_args = control.get("trigger_args", {}) or {}
        cancel_args = control.get("cancel_args", {}) or {}
        script_entity = str(control.get("script_entity", "")).strip()
        cancel_script_entity = str(control.get("cancel_script_entity", "")).strip()
        timer_entity = boost_timer_entity(control)
        restore_state_entity = boost_restore_state_entity(control)
        targets = [str(entity).strip() for entity in control.get("targets", []) if str(entity).strip()]
        duration_minutes = int(control.get("duration_minutes", 30))
        temperature_c = float(control.get("temperature_c", 23))
        fail_safe_off_on_uncertain_restore = bool(control.get("fail_safe_off_on_uncertain_restore", False))
        indicator_relay_entity = str(control.get("indicator_relay_entity", "")).strip()
        indicator_light_entity = str(control.get("indicator_light_entity", "")).strip()
        completion_flash_rgb_color = control.get("completion_flash_rgb_color", [170, 0, 255])
        completion_flash_seconds = float(control.get("completion_flash_seconds", 1))

        if (
            not automation_entity
            or not remote_identifier
            or not targets
        ):
            raise RuntimeError(f"Incomplete remote_heating_controls entry '{name}'")

        use_event_start = bool(trigger_command)
        use_event_cancel = bool(cancel_command)
        if not use_event_start and (not trigger_type or not trigger_subtype):
            raise RuntimeError(f"Incomplete start trigger for remote_heating_controls entry '{name}'")
        if not use_event_cancel and (not cancel_trigger_type or not cancel_trigger_subtype):
            raise RuntimeError(f"Incomplete cancel trigger for remote_heating_controls entry '{name}'")

        remote_device = next(
            (
                d
                for d in devices
                if any(
                    pair
                    and len(pair) == 2
                    and pair[0] == "zha"
                    and str(pair[1]).upper() == remote_identifier
                    for pair in d.get("identifiers", [])
                )
            ),
            None,
        )
        if not remote_device:
            raise RuntimeError(f"Could not find ZHA remote with IEEE {remote_identifier}")

        if use_event_start:
            start_trigger = {
                "trigger": "event",
                "event_type": "zha_event",
                "event_data": {
                    "device_ieee": remote_identifier.lower(),
                    "command": trigger_command,
                    "args": trigger_args,
                },
                "id": "boost",
            }
        else:
            start_trigger = {
                "trigger": "device",
                "domain": "zha",
                "device_id": remote_device["id"],
                "type": trigger_type,
                "subtype": trigger_subtype,
                "id": "boost",
            }

        if use_event_cancel:
            cancel_wait_trigger = {
                "trigger": "event",
                "event_type": "zha_event",
                "event_data": {
                    "device_ieee": remote_identifier.lower(),
                    "command": cancel_command,
                    "args": cancel_args,
                },
            }
        else:
            cancel_wait_trigger = {
                "trigger": "device",
                "domain": "zha",
                "device_id": remote_device["id"],
                "type": cancel_trigger_type,
                "subtype": cancel_trigger_subtype,
            }
        completion_flash_sequence = indicator_flash_sequence(
            indicator_relay_entity,
            indicator_light_entity,
            "completion_indicator",
            completion_flash_rgb_color,
            1,
            completion_flash_seconds,
        )
        extend_flash_sequence = indicator_flash_sequence(
            indicator_relay_entity,
            indicator_light_entity,
            "extend_indicator",
            [255, 0, 0],
            2,
            1,
        )

        restore_state_value_template = (
            "{{ "
            + "({"
            + ", ".join(
                [
                    (
                        "'"
                        + target
                        + "': {'mode': states('"
                        + target
                        + "'), 'temperature': state_attr('"
                        + target
                        + "', 'temperature')}"
                    )
                    for target in targets
                ]
            )
            + "} | to_json) }}"
        )

        restore_sequence: List[dict] = []
        for target in targets:
            restore_mode_template = "{{ restore_state.get('" + target + "', {}).get('mode') }}"
            restore_mode_off_template = "{{ restore_state.get('" + target + "', {}).get('mode') == 'off' }}"
            restore_temp_exists_template = "{{ restore_state.get('" + target + "', {}).get('temperature') is not none }}"
            restore_temp_template = "{{ restore_state.get('" + target + "', {}).get('temperature') | float }}"
            restore_sequence.extend(
                [
                    {
                        "choose": [
                            {
                                "conditions": [
                                    {
                                        "condition": "template",
                                        "value_template": restore_mode_off_template,
                                    }
                                ],
                                "sequence": [
                                    {
                                        "choose": [
                                            {
                                                "conditions": [
                                                    {
                                                        "condition": "template",
                                                        "value_template": restore_temp_exists_template,
                                                    }
                                                ],
                                                "sequence": [
                                                    {
                                                        "action": "climate.set_temperature",
                                                        "target": {"entity_id": target},
                                                        "data": {"temperature": restore_temp_template},
                                                    }
                                                ],
                                            }
                                        ]
                                    },
                                    {
                                        "action": "climate.set_hvac_mode",
                                        "target": {"entity_id": target},
                                        "data": {"hvac_mode": "off"},
                                    }
                                ],
                            }
                        ],
                        "default": [
                            {
                                "action": "climate.set_hvac_mode",
                                "target": {"entity_id": target},
                                "data": {"hvac_mode": restore_mode_template},
                            },
                            {
                                "choose": [
                                    {
                                        "conditions": [
                                        {
                                            "condition": "template",
                                            "value_template": restore_temp_exists_template,
                                            }
                                        ],
                                        "sequence": [
                                            {
                                                "action": "climate.set_temperature",
                                                "target": {"entity_id": target},
                                                "data": {"temperature": restore_temp_template},
                                            }
                                        ],
                                    }
                                ]
                            },
                        ],
                    }
                ]
            )

        all_targets_restored_template = (
            "{{ "
            + " and ".join(
                [
                    (
                        "("
                        f"(restore_state.get('{target}', {{}}).get('mode') == 'off' and states('{target}') == 'off')"
                        " or "
                        f"(restore_state.get('{target}', {{}}).get('mode') != 'off' and states('{target}') == restore_state.get('{target}', {{}}).get('mode'))"
                        ") and ("
                        f"(restore_state.get('{target}', {{}}).get('temperature') is none)"
                        " or "
                        f"(((state_attr('{target}', 'temperature') | float(0)) - (restore_state.get('{target}', {{}}).get('temperature') | float(0))) | abs < 0.01)"
                        ")"
                    )
                    for target in targets
                ]
            )
            + " }}"
        )

        automation_id = automation_entity.split(".", 1)[1]
        if not script_entity or not cancel_script_entity:
            raise RuntimeError(f"Missing script entities for remote_heating_controls entry '{name}'")

        script_id = script_entity.split(".", 1)[1]
        cancel_script_id = cancel_script_entity.split(".", 1)[1]
        targets_currently_boosted_template = (
            "{{ "
            + " and ".join(
                [
                    (
                        f"(states('{target}') == 'heat' and "
                        f"((state_attr('{target}', 'temperature') | float(0)) >= {temperature_c - 0.01}))"
                    )
                    for target in targets
                ]
            )
            + " }}"
        )

        ensure_boost_actions: List[dict] = []
        ensure_off_actions: List[dict] = []
        for target in targets:
            ensure_boost_actions.append(
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ not (states('"
                                    + target
                                    + "') == 'heat' and ((state_attr('"
                                    + target
                                    + "', 'temperature') | float(0)) >= "
                                    + str(temperature_c - 0.01)
                                    + ")) }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "climate.set_hvac_mode",
                                    "target": {"entity_id": target},
                                    "data": {"hvac_mode": "heat"},
                                },
                                {
                                    "action": "climate.set_temperature",
                                    "target": {"entity_id": target},
                                    "data": {"temperature": temperature_c},
                                },
                            ],
                        }
                    ]
                }
            )
            ensure_off_actions.append(
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ states('" + target + "') != 'off' }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "climate.set_hvac_mode",
                                    "target": {"entity_id": target},
                                    "data": {"hvac_mode": "off"},
                                }
                            ],
                        }
                    ]
                }
            )

        script_payload = {
            "alias": name,
            "sequence": [
                {
                    "variables": {
                        "boost_is_active": "{{ is_state('" + timer_entity + "', 'active') }}",
                        "targets_currently_boosted": targets_currently_boosted_template,
                    }
                },
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ boost_is_active and targets_currently_boosted }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "timer.start",
                                    "target": {"entity_id": timer_entity},
                                    "data": {"duration": f"00:{duration_minutes:02d}:00"},
                                },
                                *extend_flash_sequence,
                            ],
                        }
                    ],
                    "default": [
                        {
                            "action": "input_text.set_value",
                            "target": {"entity_id": restore_state_entity},
                            "data": {"value": restore_state_value_template},
                        },
                        {
                            "action": "timer.start",
                            "target": {"entity_id": timer_entity},
                            "data": {"duration": f"00:{duration_minutes:02d}:00"},
                        },
                        {
                            "action": "climate.set_hvac_mode",
                            "target": {"entity_id": targets},
                            "data": {"hvac_mode": "heat"},
                        },
                        {
                            "action": "climate.set_temperature",
                            "target": {"entity_id": targets},
                            "data": {"temperature": temperature_c},
                        },
                    ],
                },
            ],
            "mode": "restart",
        }
        cancel_script_payload = {
            "alias": f"Cancel {name}",
            "sequence": [
                {
                    "variables": {
                        "has_restore_state": "{{ states('" + restore_state_entity + "') not in ['', 'unknown', 'unavailable'] }}",
                        "restore_state": "{{ (states('" + restore_state_entity + "') if states('" + restore_state_entity + "') not in ['', 'unknown', 'unavailable'] else '{}') | from_json }}",
                        "targets_currently_boosted": targets_currently_boosted_template,
                    }
                },
                {
                    "action": "timer.cancel",
                    "target": {"entity_id": timer_entity},
                },
                {
                    "choose": [
                        {
                            "conditions": [{"condition": "template", "value_template": "{{ has_restore_state }}"}],
                            "sequence": completion_flash_sequence + restore_sequence,
                        },
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ targets_currently_boosted and "
                                    + ("true" if fail_safe_off_on_uncertain_restore else "false")
                                    + " }}",
                                }
                            ],
                            "sequence": ensure_off_actions,
                        },
                    ]
                },
            ],
            "mode": "single",
        }

        script_resp = requests.post(
            f"{base}/api/config/script/config/{script_id}",
            headers=headers,
            json=script_payload,
            timeout=20,
        )
        script_resp.raise_for_status()
        print(f"Synced {script_entity}")

        cancel_script_resp = requests.post(
            f"{base}/api/config/script/config/{cancel_script_id}",
            headers=headers,
            json=cancel_script_payload,
            timeout=20,
        )
        cancel_script_resp.raise_for_status()
        print(f"Synced {cancel_script_entity}")

        reconcile_automation_id = automation_id + "_reconcile"
        reconcile_automation_payload = {
            "alias": f"Reconcile {name}",
            "description": "Repo-managed reconciliation for heating boost desired state.",
            "mode": "restart",
            "triggers": [
                {"trigger": "homeassistant", "event": "start"},
                {"trigger": "event", "event_type": "timer.finished", "event_data": {"entity_id": timer_entity}},
                {"trigger": "time_pattern", "minutes": "/1"},
                {"trigger": "state", "entity_id": restore_state_entity},
            ],
            "conditions": [],
            "actions": [
                {
                    "variables": {
                        "boost_is_active": "{{ is_state('" + timer_entity + "', 'active') }}",
                        "has_restore_state": "{{ states('" + restore_state_entity + "') not in ['', 'unknown', 'unavailable'] }}",
                        "restore_state": "{{ (states('" + restore_state_entity + "') if states('" + restore_state_entity + "') not in ['', 'unknown', 'unavailable'] else '{}') | from_json }}",
                        "all_targets_restored": all_targets_restored_template,
                        "targets_currently_boosted": targets_currently_boosted_template,
                    }
                },
                {
                    "choose": [
                        {
                            "conditions": [{"condition": "template", "value_template": "{{ boost_is_active }}"}],
                            "sequence": ensure_boost_actions,
                        },
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ has_restore_state and not all_targets_restored }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "choose": [
                                        {
                                            "conditions": [
                                                {
                                                    "condition": "template",
                                                    "value_template": "{{ trigger.platform == 'event' and trigger.event.event_type == 'timer.finished' }}",
                                                }
                                            ],
                                            "sequence": completion_flash_sequence,
                                        }
                                    ]
                                },
                                *restore_sequence,
                            ],
                        },
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ has_restore_state and all_targets_restored }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "input_text.set_value",
                                    "target": {"entity_id": restore_state_entity},
                                    "data": {"value": ""},
                                }
                            ],
                        },
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ trigger.platform == 'homeassistant' and not boost_is_active and not has_restore_state and targets_currently_boosted and "
                                    + ("true" if fail_safe_off_on_uncertain_restore else "false")
                                    + " }}",
                                }
                            ],
                            "sequence": ensure_off_actions,
                        },
                    ]
                },
            ],
        }

        automation_payload = {
            "alias": name,
            "description": "Repo-managed ZHA remote heating control.",
            "mode": "single",
            "triggers": [start_trigger],
            "conditions": [],
            "actions": [
                {
                    "action": "script.turn_on",
                    "target": {"entity_id": script_entity},
                }
            ],
        }

        cancel_automation_payload = {
            "alias": f"Cancel {name}",
            "description": "Repo-managed ZHA remote heating cancel control.",
            "mode": "single",
            "triggers": [
                {
                    **cancel_wait_trigger,
                    "id": "cancel",
                }
            ],
            "conditions": [],
            "actions": [
                {
                    "action": "script.turn_on",
                    "target": {"entity_id": cancel_script_entity},
                }
            ],
        }

        resp = requests.post(
            f"{base}/api/config/automation/config/{automation_id}",
            headers=headers,
            json=automation_payload,
            timeout=20,
        )
        resp.raise_for_status()
        print(f"Synced {automation_entity}")

        cancel_automation_id = automation_id + "_cancel"
        cancel_automation_resp = requests.post(
            f"{base}/api/config/automation/config/{cancel_automation_id}",
            headers=headers,
            json=cancel_automation_payload,
            timeout=20,
        )
        cancel_automation_resp.raise_for_status()
        print(f"Synced automation.{cancel_automation_id}")

        reconcile_automation_resp = requests.post(
            f"{base}/api/config/automation/config/{reconcile_automation_id}",
            headers=headers,
            json=reconcile_automation_payload,
            timeout=20,
        )
        reconcile_automation_resp.raise_for_status()
        print(f"Synced automation.{reconcile_automation_id}")

        legacy_runner_id = script_id + "_runner"
        legacy_runner_resp = requests.delete(
            f"{base}/api/config/script/config/{legacy_runner_id}",
            headers=headers,
            timeout=20,
        )
        if legacy_runner_resp.status_code not in (200, 400, 404):
            legacy_runner_resp.raise_for_status()
        if legacy_runner_resp.status_code == 200:
            print(f"Removed legacy script.{legacy_runner_id}")

    requests.post(f"{base}/api/services/automation/reload", headers=headers, json={}, timeout=20).raise_for_status()
    requests.post(f"{base}/api/services/script/reload", headers=headers, json={}, timeout=20).raise_for_status()
    print("Reloaded automations")


def cmd_sync_heating_alerts() -> None:
    cfg, base, token = ha_auth_from_config()
    alerts = cfg.get("home_assistant", {}).get("heating_alerts", [])
    if not alerts:
        print("No home_assistant.heating_alerts configured; nothing to do.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for alert in alerts:
        name = str(alert.get("name", "Heating Alert")).strip()
        automation_entity = str(alert.get("automation_entity", "")).strip()
        alert_type = str(alert.get("alert_type", "climate_target")).strip()
        climate_entities = [str(entity).strip() for entity in alert.get("climate_entities", []) if str(entity).strip()]
        threshold_temperature_c = float(alert.get("threshold_temperature_c", 23))
        boiler_entity = str(alert.get("boiler_entity", "")).strip()
        relay_entity = str(alert.get("relay_entity", "")).strip()
        light_entity = str(alert.get("light_entity", "")).strip()
        flash_rgb_color = alert.get("flash_rgb_color", [255, 0, 0])
        flash_count = int(alert.get("flash_count", 2))
        flash_seconds = float(alert.get("flash_seconds", 1))

        if (
            not automation_entity
            or not relay_entity
            or not light_entity
            or flash_count < 1
            or flash_seconds <= 0
        ):
            raise RuntimeError(f"Incomplete heating_alerts entry '{name}'")

        if alert_type == "climate_target":
            if not climate_entities:
                raise RuntimeError(f"Missing climate_entities for heating_alerts entry '{name}'")
            triggers = []
            for entity in climate_entities:
                triggers.append(
                    {
                        "trigger": "state",
                        "entity_id": entity,
                        "attribute": "temperature",
                    }
                )
            conditions = [
                {
                    "condition": "template",
                    "value_template": "{{ trigger.to_state is not none and (trigger.to_state.attributes.temperature | float(0)) >= "
                    + str(threshold_temperature_c)
                    + " }}",
                }
            ]
        elif alert_type == "boiler_off":
            if not boiler_entity:
                raise RuntimeError(f"Missing boiler_entity for heating_alerts entry '{name}'")
            triggers = [{"trigger": "state", "entity_id": boiler_entity, "to": "off"}]
            conditions = [
                {
                    "condition": "template",
                    "value_template": "{{ trigger.from_state is not none and trigger.from_state.state == 'on' }}",
                }
            ]
        else:
            raise RuntimeError(f"Unsupported heating_alerts alert_type '{alert_type}'")

        flash_payload = {"rgb_color": flash_rgb_color, "brightness_pct": 100, "transition": 0.2}
        automation_id = automation_entity.split(".", 1)[1]
        automation_payload = {
            "alias": name,
            "description": "Repo-managed alert when a TRV target reaches the configured high temperature.",
            "mode": "restart",
            "triggers": triggers,
            "conditions": conditions,
            "actions": [
                {
                    "variables": {
                        "relay_was_on": "{{ is_state('" + relay_entity + "', 'on') }}",
                        "light_was_on": "{{ is_state('" + light_entity + "', 'on') }}",
                        "light_brightness": "{{ state_attr('" + light_entity + "', 'brightness') }}",
                        "light_color_mode": "{{ state_attr('" + light_entity + "', 'color_mode') }}",
                        "light_xy_color": "{{ state_attr('" + light_entity + "', 'xy_color') }}",
                        "light_xy_x": "{{ (state_attr('" + light_entity + "', 'xy_color') or [none, none])[0] }}",
                        "light_xy_y": "{{ (state_attr('" + light_entity + "', 'xy_color') or [none, none])[1] }}",
                        "light_color_temp_kelvin": "{{ state_attr('" + light_entity + "', 'color_temp_kelvin') }}",
                    }
                },
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ not relay_was_on }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "switch.turn_on",
                                    "target": {"entity_id": relay_entity},
                                },
                                {"delay": "00:00:02"},
                            ],
                        }
                    ]
                },
                {
                    "repeat": {
                        "count": flash_count,
                        "sequence": [
                            {
                                "action": "light.turn_on",
                                "target": {"entity_id": light_entity},
                                "data": flash_payload,
                            },
                            {"delay": f"00:00:{int(flash_seconds):02d}"},
                            {
                                "action": "light.turn_off",
                                "target": {"entity_id": light_entity},
                            },
                            {"delay": f"00:00:{int(flash_seconds):02d}"},
                        ],
                    }
                },
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ light_was_on }}",
                                },
                                {
                                    "condition": "template",
                                    "value_template": "{{ light_color_mode == 'color_temp' and light_color_temp_kelvin is not none }}",
                                },
                            ],
                            "sequence": [
                                {
                                    "action": "light.turn_on",
                                    "target": {"entity_id": light_entity},
                                    "data": {
                                        "brightness": "{{ light_brightness | int(255) }}",
                                        "color_temp_kelvin": "{{ light_color_temp_kelvin | int }}",
                                        "transition": 0,
                                    },
                                }
                            ],
                        },
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ light_was_on }}",
                                },
                                {
                                    "condition": "template",
                                    "value_template": "{{ light_color_mode != 'color_temp' and light_xy_x is not none and light_xy_y is not none }}",
                                },
                            ],
                            "sequence": [
                                {
                                    "action": "light.turn_on",
                                    "target": {"entity_id": light_entity},
                                    "data": {
                                        "brightness": "{{ light_brightness | int(255) }}",
                                        "xy_color": [
                                            "{{ light_xy_x | float }}",
                                            "{{ light_xy_y | float }}",
                                        ],
                                        "transition": 0,
                                    },
                                }
                            ],
                        },
                    ],
                    "default": [
                        {
                            "choose": [
                                {
                                    "conditions": [
                                        {
                                            "condition": "template",
                                            "value_template": "{{ light_was_on }}",
                                        }
                                    ],
                                    "sequence": [
                                        {
                                            "action": "light.turn_on",
                                            "target": {"entity_id": light_entity},
                                            "data": {
                                                "brightness": "{{ light_brightness | int(255) }}",
                                                "transition": 0,
                                            },
                                        }
                                    ],
                                }
                            ],
                            "default": [
                                {
                                    "action": "light.turn_off",
                                    "target": {"entity_id": light_entity},
                                }
                            ],
                        }
                    ],
                },
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "template",
                                    "value_template": "{{ not relay_was_on }}",
                                }
                            ],
                            "sequence": [
                                {
                                    "action": "switch.turn_off",
                                    "target": {"entity_id": relay_entity},
                                }
                            ],
                        }
                    ],
                },
            ],
        }

        resp = requests.post(
            f"{base}/api/config/automation/config/{automation_id}",
            headers=headers,
            json=automation_payload,
            timeout=20,
        )
        resp.raise_for_status()
        print(f"Synced {automation_entity}")

    requests.post(f"{base}/api/services/automation/reload", headers=headers, json={}, timeout=20).raise_for_status()
    print("Reloaded automations")

def main() -> None:
    parser = argparse.ArgumentParser(description="Home Assistant helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply-core")
    sub.add_parser("sync-devices")
    sub.add_parser("add-tplink")
    sub.add_parser("sync-heating-dashboard")
    sub.add_parser("sync-heating-control")
    sub.add_parser("sync-light-routines")
    sub.add_parser("sync-hue-scenes")
    sub.add_parser("sync-remote-light-controls")
    sub.add_parser("sync-remote-heating-controls")
    sub.add_parser("sync-heating-alerts")
    sub.add_parser("sync-status-lights")
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
    elif args.command == "sync-light-routines":
        cmd_sync_light_routines()
    elif args.command == "sync-hue-scenes":
        cmd_sync_hue_scenes()
    elif args.command == "sync-remote-light-controls":
        cmd_sync_remote_light_controls()
    elif args.command == "sync-remote-heating-controls":
        cmd_sync_remote_heating_controls()
    elif args.command == "sync-heating-alerts":
        cmd_sync_heating_alerts()
    elif args.command == "sync-status-lights":
        cmd_sync_status_lights()
    elif args.command == "summary":
        cmd_summary()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
