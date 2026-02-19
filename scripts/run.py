#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError as exc:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(1) from exc


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config() -> dict:
    config_path = repo_root() / "config" / "homelab.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run(cmd: List[str], cwd: Optional[Path] = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def write_inventory(cfg: dict) -> Path:
    ansible_dir = repo_root() / "ansible"
    inventory_path = ansible_dir / "inventory.yml"

    proxmox = cfg["proxmox"]
    guests = cfg["services"]

    inventory = {
        "proxmox-hosts": {
            "hosts": {
                "proxmox": {
                    "ansible_host": proxmox["ssh_host"],
                    "ansible_ssh_user": proxmox["ssh_user"],
                    "ansible_ssh_private_key_file": proxmox["ssh_private_key_path"],
                }
            }
        },
        "guests": {"hosts": {}},
        "vms": {"hosts": {}},
        "lxcs": {"hosts": {}},
    }

    for name, meta in guests.get("vms", {}).items():
        inventory["guests"]["hosts"][name] = {
            "ansible_host": meta["ip"],
            "ansible_ssh_user": "root",
            "ansible_ssh_private_key_file": proxmox["ssh_private_key_path"],
        }
        inventory["vms"]["hosts"][name] = inventory["guests"]["hosts"][name]
        for role in meta.get("roles", []):
            group = f"{role}-hosts"
            inventory.setdefault(group, {"hosts": {}})
            inventory[group]["hosts"][name] = inventory["guests"]["hosts"][name]

    for name, meta in guests.get("lxcs", {}).items():
        inventory["guests"]["hosts"][name] = {
            "ansible_host": meta["ip"],
            "ansible_ssh_user": "root",
            "ansible_ssh_private_key_file": proxmox["ssh_private_key_path"],
        }
        inventory["lxcs"]["hosts"][name] = inventory["guests"]["hosts"][name]
        for role in meta.get("roles", []):
            group = f"{role}-hosts"
            inventory.setdefault(group, {"hosts": {}})
            inventory[group]["hosts"][name] = inventory["guests"]["hosts"][name]

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    with inventory_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(inventory, fh, sort_keys=True)

    return inventory_path


def terraform_apply() -> None:
    tf_dir = repo_root() / "terraform"
    run(["terraform", "-chdir=terraform", "init"], cwd=repo_root())
    run(["terraform", "-chdir=terraform", "apply", "-auto-approve"], cwd=repo_root())


def ansible_playbook(playbook: str) -> None:
    playbook_path = repo_root() / "ansible" / "playbooks" / playbook
    if not playbook_path.exists():
        raise FileNotFoundError(playbook_path)
    run(["ansible-playbook", str(playbook_path)], cwd=repo_root())


def cmd_apply() -> None:
    cfg = load_config()
    write_inventory(cfg)
    ansible_playbook("host.yml")
    terraform_apply()
    ansible_playbook("guests.yml")


def cmd_host() -> None:
    cfg = load_config()
    write_inventory(cfg)
    ansible_playbook("host.yml")


def cmd_guests() -> None:
    cfg = load_config()
    write_inventory(cfg)
    ansible_playbook("guests.yml")


def cmd_validate() -> None:
    cfg = load_config()
    inventory_path = write_inventory(cfg)
    print(f"Inventory written to {inventory_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Homelab orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply")
    sub.add_parser("host")
    sub.add_parser("guests")
    sub.add_parser("validate")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "apply":
        cmd_apply()
    elif args.command == "host":
        cmd_host()
    elif args.command == "guests":
        cmd_guests()
    elif args.command == "validate":
        cmd_validate()
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
