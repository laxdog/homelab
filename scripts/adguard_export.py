#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc


def fetch_json(base_url, user, password, path, timeout=10):
    req = urllib.request.Request(base_url + path)
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data)


def normalize_filters(filters):
    normalized = []
    for item in filters or []:
        normalized.append({
            "name": item.get("name"),
            "url": item.get("url"),
            "enabled": bool(item.get("enabled", True)),
        })
    return normalized


def export_config(base_url, user, password):
    filtering = fetch_json(base_url, user, password, "/control/filtering/status")
    dns_info = fetch_json(base_url, user, password, "/control/dns_info")
    rewrites = fetch_json(base_url, user, password, "/control/rewrite/list")
    clients = fetch_json(base_url, user, password, "/control/clients")
    blocked_services = fetch_json(base_url, user, password, "/control/blocked_services/list")
    tls_status = fetch_json(base_url, user, password, "/control/tls/status")
    status = fetch_json(base_url, user, password, "/control/status")

    user_rules = [rule for rule in (filtering.get("user_rules") or []) if str(rule).strip()]

    return {
        "status": status,
        "filtering": {
            "enabled": filtering.get("enabled"),
            "interval": filtering.get("interval"),
            "blocklists": normalize_filters(filtering.get("filters")),
            "allowlists": normalize_filters(filtering.get("whitelist_filters")),
            "user_rules": user_rules,
        },
        "dns": {
            "upstream_dns": dns_info.get("upstream_dns") or [],
            "bootstrap_dns": dns_info.get("bootstrap_dns") or [],
            "fallback_dns": dns_info.get("fallback_dns") or [],
            "ratelimit": dns_info.get("ratelimit"),
            "blocking_mode": dns_info.get("blocking_mode"),
            "cache_size": dns_info.get("cache_size"),
            "cache_enabled": dns_info.get("cache_enabled"),
        },
        "rewrites": rewrites or [],
        "clients": clients,
        "blocked_services": blocked_services or [],
        "tls": tls_status,
    }


def update_homelab_config(homelab_path, export_data, include_rewrites):
    data = yaml.safe_load(Path(homelab_path).read_text())
    adguard = data.setdefault("adguard", {})
    filters = adguard.setdefault("filters", {})

    filters["blocklists"] = export_data["filtering"]["blocklists"]
    filters["allowlists"] = export_data["filtering"]["allowlists"]
    adguard["user_rules"] = [rule for rule in export_data["filtering"]["user_rules"] if str(rule).strip()]

    dns = adguard.setdefault("dns", {})
    if export_data["dns"]["upstream_dns"]:
        dns["upstream_dns"] = export_data["dns"]["upstream_dns"]
    if export_data["dns"]["bootstrap_dns"]:
        dns["bootstrap_dns"] = export_data["dns"]["bootstrap_dns"]

    if include_rewrites:
        adguard["rewrites"] = export_data["rewrites"]

    Path(homelab_path).write_text(yaml.safe_dump(data, sort_keys=False))


def main():
    parser = argparse.ArgumentParser(description="Export AdGuard Home configuration.")
    parser.add_argument("--url", required=True, help="Base URL, e.g. http://10.20.30.53:80")
    parser.add_argument("--user", required=True, help="Admin username")
    parser.add_argument("--password", help="Admin password (prefer --password-env)")
    parser.add_argument("--password-env", default="ADGUARD_PASSWORD", help="Env var for password")
    parser.add_argument("--out", default="config/adguard-export.yaml", help="Output file")
    parser.add_argument("--apply", default=None, help="Update config/homelab.yaml with exported values")
    parser.add_argument("--include-rewrites", action="store_true", help="Overwrite rewrites in homelab config")

    args = parser.parse_args()

    password = args.password
    if not password and args.password_env:
        password = os.environ.get(args.password_env)
    if not password:
        print("Password not provided. Set --password or ADGUARD_PASSWORD.", file=sys.stderr)
        sys.exit(1)

    export_data = export_config(args.url, args.user, password)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(export_data, sort_keys=False))

    if args.apply:
        update_homelab_config(args.apply, export_data, args.include_rewrites)


if __name__ == "__main__":
    main()
