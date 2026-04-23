# Media-Stack Agent

## Scope
- VM120 at 10.20.30.120
- `/opt/media-stack/` on VM120
- Docker compose for arr stack
- Bazarr, Sonarr, Radarr, Prowlarr, SABnzbd, qBittorrent, Tdarr, Cleanuparr
- Media library management

## Out of scope
Do not touch:
- Proxmox host config or Ansible roles (except media-stack role)
- Terraform resources
- AdGuard, NPM, Nagios config
- CT167 (jellyfin-hw) — homelab agent scope
- `/srv/data/media` or `/srv/data/downloads` (tank virtiofs mounts — do not delete or reorganise)

## Auth model — ownership boundary
Media-stack owns the auth-model **decisions** for the services it runs (Jellyfin, the arr stack, downloaders): which auth provider, which clients need to keep working, forward-auth vs app-native, which users/groups have access. Homelab owns the **implementation** — NPM proxy host config, Authentik providers/applications/outposts, Jellyfin LDAP plugin install on CT167, group/user provisioning in Authentik.

Coordination pattern: media-stack states the intent and constraints; homelab wires it up via `ansible/` + `config/homelab.yaml`. Example (2026-04-23): decision to drop NPM forward-auth on `jellyfin.lax.dog` in favour of Jellyfin-native LDAP via the Authentik LDAP outpost on CT170 — media-stack called the direction, homelab implemented it across the `authentik.ldap` and `jellyfin.ldap` config blocks and the NPM external proxy host.

Current Jellyfin user-state direction:
- local Jellyfin `admin` stays permanently as break-glass
- normal users should be invited and enrolled through Authentik
- local legacy users that should move to central auth should be deleted in Jellyfin first, then re-added through the Authentik invite flow

## Entry points
- VM120: `ssh ubuntu@10.20.30.120`
- Compose files: `/opt/media-stack/`
- Appdata: `/opt/media-stack/appdata/`
- Repo config: `config/homelab.yaml` media_stack: block
- Repo role: `ansible/roles/media-stack/`

## Current stack status
Running containers on VM120: bazarr, tdarr, tdarr-node, prowlarr, sonarr, radarr, qbittorrent, sabnzbd, gluetun, cleanuparr

Retired (2026-04-14): Plex and Jellyfin on VM120 — CT167 Jellyfin is production.

## Important notes
- **virtiofs mounts**: `/srv/data/media` and `/srv/data/downloads` are tank pool datasets mounted into VM120 via virtiofs. Do not touch these paths.
- **Tdarr**: recently added, docs in `docs/tdarr.md`
- **Bazarr SQLAlchemy patch**: was required, now resolved upstream. Patch file at `/opt/media-stack/appdata/bazarr/fix/ui.py` is no longer applied. Safe to remove.

## Principle
Docker compose files should be committed to this repo and deployed via Ansible. Currently compose files live directly on VM120 — moving them to the repo is a backlog item.

## Backlog

- [ ] Move docker compose files into repo
  - Context: compose files currently live on VM120 at /opt/media-stack/. They should be in the repo and deployed via Ansible to follow the source-of-truth principle.
  - Effort: high
  - Added: 2026-04-14

- [ ] Remove stale Bazarr patch file
  - Context: /opt/media-stack/appdata/bazarr/fix/ui.py no longer needed. Safe to delete.
  - Effort: low
  - Added: 2026-04-14

- [ ] Investigate Cleanuparr
  - Context: Cleanuparr is running on VM120 as part of the media stack. Understand what it does, whether it's configured correctly, and whether it needs any homelab-side config or monitoring.
  - Effort: low
  - Added: 2026-04-14
