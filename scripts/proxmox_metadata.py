#!/usr/bin/env python3
import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


MANAGED_TAG_KEYS = {"lax.dog", "laxdog.uk", "oidc"}


@dataclass
class Guest:
    name: str
    kind: str
    vmid: int
    ip: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with (repo_root() / "config" / "homelab.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run_cmd(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def ssh_cmd(target: str, remote_args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    remote_cmd = " ".join(shlex.quote(arg) for arg in remote_args)
    return run_cmd(["ssh", target, remote_cmd], check=check)


def parse_tags(raw: str) -> List[str]:
    if not raw:
        return []
    if ";" in raw:
        parts = raw.split(";")
    else:
        parts = raw.split(",")
    return [p.strip() for p in parts if p.strip()]


def build_guests(cfg: dict) -> Dict[str, Guest]:
    guests: Dict[str, Guest] = {}
    for name, meta in cfg["services"].get("vms", {}).items():
        guests[name] = Guest(name=name, kind="qemu", vmid=int(meta["id"]), ip=str(meta["ip"]))
    for name, meta in cfg["services"].get("lxcs", {}).items():
        guests[name] = Guest(name=name, kind="lxc", vmid=int(meta["id"]), ip=str(meta["ip"]))
    return guests


def build_domains_by_service(cfg: dict, guests: Dict[str, Guest]) -> Dict[str, List[str]]:
    ip_to_service = {guest.ip: name for name, guest in guests.items()}
    out: Dict[str, set] = {name: set() for name in guests}

    proxy_hosts = list(cfg.get("npm", {}).get("proxy_hosts", []))
    if cfg.get("npm", {}).get("external_enabled", False):
        proxy_hosts.extend(cfg.get("npm", {}).get("external_proxy_hosts", []))

    for host in proxy_hosts:
        service_name = ip_to_service.get(str(host.get("forward_host", "")))
        if service_name:
            out[service_name].add(str(host.get("domain", "")))

    return {name: sorted(domains) for name, domains in out.items()}


def build_tags(cfg: dict, service_name: str, domains: List[str]) -> List[str]:
    tags: set = set()
    internal_domain = cfg["naming"]["domains"]["internal"]
    external_domain = cfg["naming"]["domains"]["external"]

    for domain in domains:
        if domain.endswith(f".{internal_domain}"):
            tags.add("laxdog.uk")
        if domain.endswith(f".{external_domain}"):
            tags.add("lax.dog")

    if service_name in set(cfg.get("proxmox_metadata", {}).get("oidc_services", [])):
        tags.add("oidc")
    return sorted(tags)


def build_credentials(cfg: dict, service_name: str, guest: Guest) -> List[dict]:
    service_creds = cfg.get("proxmox_metadata", {}).get("service_credentials", {}).get(service_name, [])
    if service_creds:
        return service_creds

    default_ssh = cfg.get("proxmox_metadata", {}).get("default_credentials", {}).get("ssh")
    if default_ssh and guest.kind in {"lxc", "qemu"}:
        return [{"label": "ssh", **default_ssh}]
    return []


def build_note(service_name: str, guest: Guest, domains: List[str], creds: List[dict], oidc_enabled: bool) -> str:
    access = []
    if any(d.endswith(".laxdog.uk") for d in domains):
        access.append("internal")
    if any(d.endswith(".lax.dog") for d in domains):
        access.append("external")
    access_value = ",".join(access) if access else "none"
    domains_value = ",".join(domains) if domains else "none"
    oidc_value = "yes" if oidc_enabled else "no"

    if creds:
        creds_value = ",".join(
            f"{c.get('label','cred')}:{c.get('username','unknown')}|{c.get('password_var','unset')}" for c in creds
        )
    else:
        creds_value = "none"

    return (
        f"managed_by=scripts/proxmox_metadata.py;service={service_name};kind={guest.kind};"
        f"ip={guest.ip};access={access_value};oidc={oidc_value};domains={domains_value};creds={creds_value}"
    )


def current_config(target: str, node: str, guest: Guest) -> Tuple[List[str], str]:
    path = f"/nodes/{node}/{guest.kind}/{guest.vmid}/config"
    result = ssh_cmd(target, ["pvesh", "get", path, "--output-format", "json"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Failed to read {guest.name}")
    data = json.loads(result.stdout)
    return parse_tags(data.get("tags", "")), str(data.get("description", "") or "")


def apply_config(target: str, node: str, guest: Guest, tags: List[str], note: str) -> None:
    path = f"/nodes/{node}/{guest.kind}/{guest.vmid}/config"
    tag_value = ",".join(tags)
    ssh_cmd(target, ["pvesh", "set", path, "--tags", tag_value, "--description", note], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Proxmox VM/CT tags and notes from config/homelab.yaml")
    parser.add_argument("--check", action="store_true", help="Check for drift and exit non-zero if changes needed")
    parser.add_argument("--verbose", action="store_true", help="Print per-guest details")
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.get("proxmox_metadata", {}).get("enabled", False):
        print("Proxmox metadata sync disabled (proxmox_metadata.enabled=false).")
        return

    target = f"{cfg['proxmox']['ssh_user']}@{cfg['proxmox']['ssh_host']}"
    node = cfg["proxmox"]["node"]
    guests = build_guests(cfg)
    domains_map = build_domains_by_service(cfg, guests)
    oidc_services = set(cfg.get("proxmox_metadata", {}).get("oidc_services", []))

    changes = []
    for service_name, guest in guests.items():
        desired_managed_tags = build_tags(cfg, service_name, domains_map.get(service_name, []))
        creds = build_credentials(cfg, service_name, guest)
        desired_note = build_note(
            service_name=service_name,
            guest=guest,
            domains=domains_map.get(service_name, []),
            creds=creds,
            oidc_enabled=service_name in oidc_services,
        )

        current_tags, current_note = current_config(target, node, guest)
        retained_tags = [tag for tag in current_tags if tag not in MANAGED_TAG_KEYS]
        desired_tags = sorted(set(retained_tags + desired_managed_tags))

        tags_changed = sorted(current_tags) != desired_tags
        note_changed = current_note.strip() != desired_note.strip()
        if tags_changed or note_changed:
            changes.append((service_name, guest, current_tags, desired_tags, current_note, desired_note))

        if args.verbose:
            status = "changed" if (tags_changed or note_changed) else "ok"
            print(f"{service_name:<18} {guest.kind}:{guest.vmid} {status}")

    if args.check:
        if changes:
            print("Metadata drift detected:")
            for service_name, guest, _, desired_tags, _, _ in changes:
                print(f"- {service_name} ({guest.kind}:{guest.vmid}) -> tags={';'.join(desired_tags)}")
            raise SystemExit(1)
        print("Metadata is in sync.")
        return

    for service_name, guest, _, desired_tags, _, desired_note in changes:
        apply_config(target, node, guest, desired_tags, desired_note)
        print(f"Updated {service_name} ({guest.kind}:{guest.vmid})")

    if not changes:
        print("No metadata changes needed.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        print(stderr or str(exc), file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:  # pylint: disable=broad-except
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
