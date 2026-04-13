#!/usr/bin/env python3
"""Merge discovered WiFi networks into homelab.yaml and secrets-wifi.yml.

Usage:
    python3 wifi_merge.py \
        --config config/homelab.yaml \
        --secrets ansible/secrets-wifi.yml \
        --new-networks '[{"ssid":"woof24","psk":"secret"}]' \
        --vault-password-file ~/.ansible_vault_pass \
        [--dry-run]
"""

import argparse
import json
import os
import re
import subprocess
import sys

import yaml


def sanitise_ssid(ssid: str) -> str:
    """Convert an SSID to a safe vault variable suffix."""
    s = ssid.lower()
    s = re.sub(r"[^a-z0-9]", "_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s


def vault_var_name(ssid: str) -> str:
    return f"remote_node_wifi_{sanitise_ssid(ssid)}_psk"


def load_existing_vault_vars(secrets_path: str) -> set:
    """Return set of variable names already in the secrets file."""
    if not os.path.exists(secrets_path):
        return set()
    with open(secrets_path) as f:
        content = f.read()
    return set(re.findall(r"^(\w+):", content, re.MULTILINE))


def encrypt_string(value: str, var_name: str, vault_pw_file: str) -> str:
    """Encrypt a string using ansible-vault and return the YAML block."""
    # Unset ANSIBLE_VAULT_PASSWORD_FILE to avoid "duplicate default vault-id"
    # when the env var and --vault-password-file both resolve to "default".
    env = {k: v for k, v in os.environ.items() if k != "ANSIBLE_VAULT_PASSWORD_FILE"}
    result = subprocess.run(
        [
            "ansible-vault",
            "encrypt_string",
            value,
            "--name",
            var_name,
            "--vault-password-file",
            vault_pw_file,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: ansible-vault encrypt_string failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def known_ssids(config: dict) -> set:
    networks = config.get("remote_nodes", {}).get("wifi_networks", [])
    return {n["ssid"] for n in networks}


def append_wifi_to_config(config_path: str, ssid: str, vault_var: str = None, is_open: bool = False):
    """Append a wifi_networks entry to homelab.yaml under remote_nodes.wifi_networks."""
    with open(config_path) as f:
        lines = f.readlines()

    # Find the last wifi_networks entry (line starting with "  - ssid:" under wifi_networks)
    insert_idx = None
    in_wifi_block = False
    indent = "  "
    for i, line in enumerate(lines):
        if re.match(r"^\s+wifi_networks:\s*$", line):
            in_wifi_block = True
            continue
        if in_wifi_block:
            if re.match(r"^\s+- ssid:", line):
                insert_idx = i
                indent = re.match(r"^(\s+)", line).group(1)
            elif re.match(r"^\s+\w", line) and not re.match(
                r"^\s+(password|autoconnect|open)", line
            ):
                # Left the wifi_networks block
                break

    if insert_idx is None:
        print(f"ERROR: Could not find wifi_networks insertion point in {config_path}", file=sys.stderr)
        sys.exit(1)

    # Find the end of the last entry block (next "- ssid:" or non-entry line)
    j = insert_idx + 1
    while j < len(lines) and not re.match(r"^\s+- ssid:", lines[j]):
        if re.match(r"^\s+\w", lines[j]) and not re.match(
            r"^\s+(password|autoconnect|open)", lines[j]
        ):
            break
        j += 1

    if is_open:
        new_entry = (
            f"{indent}- ssid: '{ssid}'\n"
            f"{indent}  open: true\n"
            f"{indent}  autoconnect: true\n"
            f"{indent}  autoconnect_priority: 30\n"
        )
    else:
        new_entry = (
            f"{indent}- ssid: '{ssid}'\n"
            f"{indent}  password_var: {vault_var}\n"
            f"{indent}  autoconnect: true\n"
            f"{indent}  autoconnect_priority: 50\n"
        )
    lines.insert(j, new_entry)

    with open(config_path, "w") as f:
        f.writelines(lines)


def main():
    parser = argparse.ArgumentParser(description="Merge WiFi networks into homelab config")
    parser.add_argument("--config", required=True, help="Path to homelab.yaml")
    parser.add_argument("--secrets", required=True, help="Path to secrets-wifi.yml")
    parser.add_argument("--new-networks", required=True, help="JSON list of {ssid, psk}")
    parser.add_argument("--vault-password-file", required=True, help="Path to vault password file")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    networks = json.loads(args.new_networks)
    config = load_config(args.config)
    existing_ssids = known_ssids(config)
    existing_vault_vars = load_existing_vault_vars(args.secrets)

    added = []
    skipped = []

    warnings = []

    for net in networks:
        ssid = net["ssid"]
        psk = net.get("psk", "")
        is_open = net.get("open", False)
        key_mgmt = net.get("key_mgmt", "")

        if ssid in existing_ssids:
            skipped.append(f"{ssid} — already in homelab.yaml")
            continue

        # Open network (no security)
        if is_open or key_mgmt == "none":
            if args.dry_run:
                added.append(f"WOULD ADD (open): ssid={ssid}")
            else:
                append_wifi_to_config(args.config, ssid, is_open=True)
                added.append(f"ADDED (open): ssid={ssid}")
            continue

        # WPA-PSK with empty/missing PSK — broken profile, skip with warning
        if not psk:
            warnings.append(f"{ssid} — WPA-PSK but empty PSK (agent-owned or broken), skipped")
            continue

        var_name = vault_var_name(ssid)
        need_vault = var_name not in existing_vault_vars

        if args.dry_run:
            vault_note = "new vault entry" if need_vault else "vault exists"
            added.append(
                f"WOULD ADD: ssid={ssid}, vault_var={var_name}, "
                f"psk={'*' * len(psk)} ({len(psk)} chars), {vault_note}"
            )
        else:
            if need_vault:
                encrypted = encrypt_string(psk, var_name, args.vault_password_file)
                with open(args.secrets, "a") as f:
                    f.write(encrypted)
                    f.write("\n")

            append_wifi_to_config(args.config, ssid, vault_var=var_name)
            added.append(f"ADDED: ssid={ssid}, vault_var={var_name}")

    # Report
    print(f"\n{'DRY RUN' if args.dry_run else 'COMPLETE'}")
    print(f"  Known SSIDs in config: {len(existing_ssids)}")
    print(f"  New networks submitted: {len(networks)}")
    print(f"  Added: {len(added)}")
    for a in added:
        print(f"    {a}")
    print(f"  Skipped: {len(skipped)}")
    for s in skipped:
        print(f"    {s}")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
        for w in warnings:
            print(f"    {w}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
