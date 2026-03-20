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
- `tank-vmdata` -> `tank` zfs pool (guest data disks only; used by `media-stack` bulk-data disk)

## Media-Stack Foundation
- VM `media-stack` root disk (`local-lvm`) is for OS + appdata only.
- VM `media-stack` bulk data disk is on `tank-vmdata` (ZFS-backed) and mounted in-guest at `/srv/data`.
- Shared media layout under `/srv/data`:
  - `downloads/incomplete`
  - `downloads/usenet`
  - `downloads/torrents`
  - `media/movies`
  - `media/tv`
  - `media/music`
  - `media/audiobooks`
  - `media/comedy`
  - `media/software`
  - `media/roms`
- Internal NFS export baseline is `/srv/data` from VM `120` (`10.20.30.120`) to `10.20.30.0/24`.

## TODO
- Set `prune-backups keep-all=1` for `tank-backups` storage via Ansible (currently omitted due to syntax check issues).
