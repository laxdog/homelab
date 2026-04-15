# Storage

Source of truth: `config/homelab.yaml`.

## Pools

| Pool | Type | Disks | Size | Purpose |
|---|---|---|---:|---|
| ssd-fast | ZFS solo | Kingston SA400 894G (SATA) | 888G | High-IOPS guest rootfs: CT153 AdGuard, CT163 RR-dev, CT170 Authentik |
| ssd-mirror | ZFS mirror | 2x ORICO 477G (SATA) | 476G | Redundant guest rootfs: all other guests including CT172 observability |
| tank | ZFS raidz1 | 3x Seagate 10TB SAS | 27.3T | Bulk: media, downloads, backups, templates |
| local-lvm | LVM thin | NVMe (shared with boot) | 156G | Nearly empty — only cloud-init ISOs |
| local | dir | NVMe | 69G | ISOs, templates, import images |

All guest rootfs disks were migrated to SSD pools on 2026-04-13. `autotrim=on` on both SSD pools. TRIM works natively via onboard Intel SATA (AHCI).

## ZFS datasets

- `/tank/media` — media library (virtiofs to VM120)
- `/tank/downloads` — download staging (virtiofs to VM120)
- `/tank/personal`
- `/tank/backups` — daily vzdump target
- `/tank/templates`
- `/tank/scratch`

## Backups

- Daily vzdump at 04:30 to `/tank/backups/dump/`
- All 20 guests backed up (zstd, 14-day retention)
- ~43 GB/day compressed, ~600 GB steady-state

## Proxmox storage IDs

| ID | Type | Path/Pool | Content |
|---|---|---|---|
| local | dir | /var/lib/vz | iso, backup, vztmpl, import |
| local-lvm | lvmthin | pve/data | rootdir, images (nearly empty) |
| ssd-fast | zfspool | ssd-fast | rootdir, images |
| ssd-mirror | zfspool | ssd-mirror | rootdir, images |
| tank-backups | dir | /tank/backups | backup |
| tank-templates | dir | /tank/templates | iso, vztmpl, import, snippets |
| tank-vmdata | zfspool | tank | images, rootdir (legacy — CT167 bind mount only) |

## Media-Stack storage model

- VM120 root disk on ssd-mirror (OS + appdata at `/opt/media-stack/appdata/`)
- Media/downloads via virtiofs mounts from tank pool (not VM disks):
  - `/srv/data/media` → `tank-media`
  - `/srv/data/downloads` → `tank-downloads`
- Plex and Jellyfin on VM120 are retired — CT167 is production Jellyfin
