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


def run(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> None:
    merged_env = os.environ.copy()
    if "ANSIBLE_VAULT_PASSWORD_FILE" not in merged_env:
        default_vault = Path.home() / ".ansible_vault_pass"
        if default_vault.exists():
            merged_env["ANSIBLE_VAULT_PASSWORD_FILE"] = str(default_vault)
    if env:
        merged_env.update(env)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, env=merged_env)


def write_inventory(cfg: dict) -> Path:
    ansible_dir = repo_root() / "ansible"
    inventory_path = ansible_dir / "inventory.yml"

    proxmox = cfg["proxmox"]
    guests = cfg["services"]

    inventory = {
        "proxmox_hosts": {
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
        if meta.get("os") != "ubuntu":
            continue
        inventory["guests"]["hosts"][name] = {
            "ansible_host": meta["ip"],
            "ansible_ssh_user": "ubuntu",
            "ansible_ssh_private_key_file": proxmox["ssh_private_key_path"],
        }
        inventory["vms"]["hosts"][name] = inventory["guests"]["hosts"][name]
        for role in meta.get("roles", []):
            group = f"{role.replace('-', '_')}_hosts"
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
            group = f"{role.replace('-', '_')}_hosts"
            inventory.setdefault(group, {"hosts": {}})
            inventory[group]["hosts"][name] = inventory["guests"]["hosts"][name]

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    with inventory_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(inventory, fh, sort_keys=True)

    return inventory_path


def terraform_apply(env: Optional[dict] = None) -> None:
    tf_dir = repo_root() / "terraform"
    run(["terraform", "-chdir=terraform", "init"], cwd=repo_root(), env=env)
    run(["terraform", "-chdir=terraform", "apply", "-auto-approve"], cwd=repo_root(), env=env)

def read_vault_var(var_name: str) -> Optional[str]:
    vault_pass = os.environ.get("ANSIBLE_VAULT_PASSWORD_FILE")
    if not vault_pass:
        default_vault = Path.home() / ".ansible_vault_pass"
        if default_vault.exists():
            vault_pass = str(default_vault)
    if not vault_pass:
        return None
    secrets_path = repo_root() / "ansible" / "secrets.yml"
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
        f"@{secrets_path}",
        "--vault-password-file",
        vault_pass,
    ]
    result = subprocess.run(
        cmd,
        cwd=str(repo_root()),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    marker = f'"{var_name}":'
    for line in result.stdout.splitlines():
        if marker in line:
            _, value = line.split(marker, 1)
            value = value.strip().strip('"')
            return value
    return None


def resolve_terraform_env(cfg: dict) -> dict:
    env: dict = {}
    if os.environ.get("TF_VAR_proxmox_api_token"):
        return env

    username = os.environ.get("TF_VAR_proxmox_username")
    if not username:
        username = cfg.get("proxmox", {}).get("terraform_user")
    if username:
        env["TF_VAR_proxmox_username"] = username

    if not os.environ.get("TF_VAR_proxmox_password"):
        password = read_vault_var("terraform_user_password")
        if password:
            env["TF_VAR_proxmox_password"] = password

    has_user = bool(os.environ.get("TF_VAR_proxmox_username") or env.get("TF_VAR_proxmox_username"))
    has_pass = bool(os.environ.get("TF_VAR_proxmox_password") or env.get("TF_VAR_proxmox_password"))
    if has_user and has_pass:
        return env

    raise SystemExit(
        "Terraform credentials missing. Set TF_VAR_proxmox_username + "
        "TF_VAR_proxmox_password or TF_VAR_proxmox_api_token, or add "
        "terraform_user_password to ansible/secrets.yml with ANSIBLE_VAULT_PASSWORD_FILE."
    )


def ansible_playbook(playbook: str) -> None:
    playbook_path = repo_root() / "ansible" / "playbooks" / playbook
    if not playbook_path.exists():
        raise FileNotFoundError(playbook_path)
    tmp_root = Path("/tmp/ansible")
    (tmp_root / "tmp").mkdir(parents=True, exist_ok=True)
    (tmp_root / "collections").mkdir(parents=True, exist_ok=True)
    env = {
        "ANSIBLE_HOME": str(tmp_root),
        "ANSIBLE_LOCAL_TMP": str(tmp_root / "tmp"),
        "ANSIBLE_COLLECTIONS_PATHS": str(tmp_root / "collections"),
    }
    run(["ansible-playbook", str(playbook_path)], cwd=repo_root(), env=env)


def proxmox_metadata_sync(check: bool = False) -> None:
    script = repo_root() / "scripts" / "proxmox_metadata.py"
    cmd = [str(script)]
    if check:
        cmd.append("--check")
    run(cmd, cwd=repo_root())


def cmd_apply() -> None:
    cfg = load_config()
    write_inventory(cfg)
    ansible_playbook("host.yml")
    tf_env = resolve_terraform_env(cfg)
    terraform_apply(env=tf_env)
    ansible_playbook("post-terraform.yml")
    ansible_playbook("guests.yml")
    proxmox_metadata_sync(check=False)


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
    proxmox_metadata_sync(check=True)
    ansible_playbook("validate.yml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Homelab orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply")
    sub.add_parser("host")
    sub.add_parser("guests")
    sub.add_parser("metadata")
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
    elif args.command == "metadata":
        proxmox_metadata_sync(check=False)
    elif args.command == "validate":
        cmd_validate()
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
