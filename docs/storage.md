# Storage

Source of truth: `config/homelab.yaml`.

## Pools
- NVMe: Proxmox VM/CT disks (`local-lvm`)
- HDD: ZFS pool `tank`

## Datasets
- `/tank/media`
- `/tank/downloads`
- `/tank/personal`
- `/tank/backups`
- `/tank/templates`
- `/tank/scratch`

## Backups
- Proxmox vzdump to `/tank/backups`
- ZFS replication for `/tank/personal` and `/tank/backups`

## Appdata
- Appdata lives on NVMe (VM/CT disks)
- Appdata backups land in `/tank/backups`

## Proxmox storage IDs
- `tank-backups` -> `/tank/backups` (backup content)
- `tank-templates` -> `/tank/templates` (iso, templates, import, snippets)
