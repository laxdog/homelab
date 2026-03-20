# Media-Stack Infra Handoff

Scope: infra foundation for VM `120` only.  
App stack deployment is intentionally deferred to a dedicated media-stack agent.

## VM Identity
- Name: `media-stack`
- VMID: `120`
- IP: `10.20.30.120`
- OS: Ubuntu 24.04

## Storage Split
- Root disk (`local-lvm`): `40G`
  - use for OS + appdata only
  - appdata path: `/opt/media-stack/appdata`
- Bulk data disk (ZFS-backed via Proxmox storage `tank-vmdata`): `scsi1`
  - in-guest mount path: `/srv/data`
  - filesystem: `ext4`
  - source device path (config-driven): `/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1`

## Bulk Data Layout
- `/srv/data/downloads/incomplete`
- `/srv/data/downloads/usenet`
- `/srv/data/downloads/torrents`
- `/srv/data/media/movies`
- `/srv/data/media/tv`
- `/srv/data/media/music`
- `/srv/data/media/audiobooks`
- `/srv/data/media/comedy`
- `/srv/data/media/software`
- `/srv/data/media/roms`

## Shared UID/GID
- Configured shared ownership model:
  - UID: `1000`
  - GID: `1000`
- Directory tree under `/srv/data` is created with `1000:1000` and mode `0775`.

## NFS Baseline (Internal Only)
- NFS server runs on VM `120`.
- Export path: `/srv/data`
- Allowed network: `10.20.30.0/24`
- Export options: `rw,sync,no_subtree_check`
- Intended use: LAN clients and internal services only.

## Intel iGPU / Quick Sync Preparation
- Proxmox sets VM `120` `hostpci0` to host Intel iGPU.
- Guest-side baseline ensures:
  - `linux-modules-extra-$(uname -r)` installed
  - `i915` module loaded and persisted (`/etc/modules-load.d/media-igpu.conf`)
  - `/dev/dri/renderD128` present for Docker `--device /dev/dri`.

## What The Next Media Agent Should Build (Day 1)
- Plex
- Jellyfin
- Sonarr
- Radarr
- Prowlarr
- NZBGet via gluetun
- qBittorrent via gluetun
- Cleanuparr

## Explicitly Deferred
- Bazarr
- Request app
- ROM manager
- Future backup/mirror pool design
- Future SATA SSD migration and wider storage redesign

## Guardrails For The Next Media Agent
- Do not change VM root disk placement (`local-lvm`) without infra review.
- Do not move guest root disks to ZFS/SAS in app-stack work.
- Keep appdata on root disk unless infra plan changes.
- Keep bulk media/download paths under `/srv/data`.
- Do not alter Proxmox passthrough/storage foundations without handing back to homelab infra agent.
