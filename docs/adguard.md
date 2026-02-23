# AdGuard Home

AdGuard is managed in two ways:
- Base config (filters, upstreams, rewrites, user rules) is stored in `config/homelab.yaml`.
- An export script can pull config from a running instance into the repo for backup/sync.

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
