# Runbook: Restore a Guest from Backup

## Backup location
`/tank/backups/dump/` on Proxmox host (10.20.30.46). Daily vzdump backups at 04:30, zstd compressed, 14-day retention. All 19 guests backed up.

## Find a backup
```bash
ls -lhS /tank/backups/dump/ | grep <vmid>
```

## Restore

### LXC
```bash
pct restore <ctid> /tank/backups/dump/<backup-file>.tar.zst \
  --storage ssd-mirror \
  --start 1
```

### VM
```bash
qmrestore /tank/backups/dump/<backup-file>.vma.zst <vmid> \
  --storage ssd-mirror \
  --start 1
```

## Post-restore
1. Verify the guest starts and the service responds
2. If restored to a different storage pool, update `config/homelab.yaml` and Terraform to match
3. Check Nagios — the guest should return to UP state within one check cycle (5-10 min)
