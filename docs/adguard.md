# AdGuard Home

AdGuard is managed in two ways:
- Base config (filters, upstreams, rewrites, user rules) is stored in `config/homelab.yaml`.
- An export script can pull config from a running instance into the repo for backup/sync.
- Optional per-device behavior can be managed with `adguard.client_overrides` in `config/homelab.yaml`.

## Export from a running instance

Use the export script to snapshot AdGuard settings:

```bash
ADGUARD_PASSWORD='...' scripts/adguard_export.py \
  --url http://10.20.30.53:80 \
  --user admin \
  --out config/adguard-export.yaml \
  --apply config/homelab.yaml
```

Notes:
- `--apply` updates `config/homelab.yaml` with blocklists, allowlists, user rules, and upstream DNS.
- By default rewrites in `config/homelab.yaml` are preserved. Use `--include-rewrites` if you want to replace them with the exported rewrite list.
- The export file (`config/adguard-export.yaml`) is a full snapshot for reference/backup.

## Apply to the managed AdGuard instance

After updating `config/homelab.yaml`, re-run the guest playbook:

```bash
scripts/run.py guests
```

This updates filters, upstreams, and user rules on the managed AdGuard LXC.

Example SmartTube tuning (minimal scope):
- Keep filtering enabled for the device.
- Add client-scoped allow rules in `adguard.user_rules` for only the YouTube domains needed by that device IP.

## Tailnet DNS

The Tailscale tailnet pushes AdGuard (`10.20.30.53`) as the global nameserver with "Override local DNS" = ON, so every Tailscale-connected client uses AdGuard for *all* DNS (ad-blocking + `*.laxdog.uk` rewrites). This is set in the Tailscale admin console (https://login.tailscale.com/admin/dns) and is **not** managed by Ansible — the `tailscale.split_dns` block previously in `config/homelab.yaml` was unimplemented intent.

If the tailnet config is reset in the admin console, restore: global nameserver `10.20.30.53`, "Override local DNS" toggle ON. Optionally add a secondary nameserver (e.g. `1.1.1.1`) for soft-fail when AdGuard is unreachable.

### Per-client allow rules and the router-as-resolver gotcha

Per-client allow rules in `adguard.user_rules` (e.g. `@@||example.com^$client='charlotte-mbp'`) match on the source IP that AdGuard sees. They only work when the client queries AdGuard *directly* — i.e. the client's resolver is `10.20.30.53`.

If a client's resolver is the LAN router (`10.20.30.1`), the router forwards the query to AdGuard but AdGuard sees the source as `10.20.30.1`, not the original client. Per-client rules don't match, and the global blocklists apply. Symptom: a domain that's allowlisted for a specific client is still blocked for that client some of the time.

When investigating "why is this domain blocked for client X" complaints, check the AdGuard query log for the source IP — if blocked queries appear from `10.20.30.1`, the fix is on the client side (point it at `10.20.30.53` directly), not in `user_rules`.
