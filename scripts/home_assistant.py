#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

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


def ws_core_update(base_url: str, token: str, payload: dict) -> dict:
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
        ws.send(json.dumps({"id": 1, "type": "config/core/update", **payload}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                if not msg.get("success", False):
                    raise RuntimeError(f"config/core/update failed: {msg}")
                return msg.get("result", {})
    finally:
        ws.close()


def cmd_apply_core() -> None:
    cfg = load_config()
    ha_cfg = cfg["home_assistant"]
    base = f"http://{cfg['services']['vms']['home-assistant']['ip']}:8123"
    password = read_vault_var("home_assistant_admin_password")
    token = ha_token(base, ha_cfg["admin_username"], password, ha_cfg["onboarding_client_id"])

    headers = {"Authorization": f"Bearer {token}"}

    # Public REST service for lat/lon/elevation.
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

    # Websocket core update for remaining core config keys.
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


def cmd_summary() -> None:
    cfg = load_config()
    ha_cfg = cfg["home_assistant"]
    base = f"http://{cfg['services']['vms']['home-assistant']['ip']}:8123"
    password = read_vault_var("home_assistant_admin_password")
    token = ha_token(base, ha_cfg["admin_username"], password, ha_cfg["onboarding_client_id"])
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Home Assistant helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply-core")
    sub.add_parser("summary")
    args = parser.parse_args()

    if args.command == "apply-core":
        cmd_apply_core()
    elif args.command == "summary":
        cmd_summary()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
