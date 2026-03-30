# Media Stack Handoff: Bazarr SQLAlchemy Patch

Date: 2026-03-28
Author: Claude Code (homelab session)
Audience: media-stack manager

---

## What Was Wrong

**Bazarr 1.5.6 (`lscr.io/linuxserver/bazarr:latest`, build `v1.5.6-ls342`, built 2026-03-24) has a SQLAlchemy 2.0 API incompatibility that causes the browser UI to show a setup wizard instead of the dashboard.**

### Mechanics

In `app/ui.py` inside the container, the route that serves the main page does:

```python
try:
    configured = database.scalar(System.configured)
except Exception:
    configured = '0'

inject["isConfigured"] = configured != '0'
```

In SQLAlchemy 2.0, `session.scalar(column_attribute)` is not valid — it requires a `Select` statement. This raises `ArgumentError`, which is silently swallowed by the `except Exception` block, setting `configured = '0'` on every single page load. The JavaScript app reads `window.Bazarr.isConfigured = false` and shows the setup wizard.

### Why it looked healthy from the outside

`curl https://bazarr.laxdog.uk/` returns `HTTP 200` — the HTML shell loads fine. The problem only manifests when the browser runs the JavaScript. This is why CLI checks (`curl`, NPM-to-backend probes) all passed while the browser showed nothing useful.

The SQLite database itself is healthy — `system.configured = '1'` is correctly set. The failure is purely in reading it.

---

## The Fix Applied

### Patched file

`/opt/media-stack/appdata/bazarr/fix/ui.py`

This is a copy of the container's original `ui.py` with two minimal changes:

1. Added import: `from sqlalchemy import select`
2. Fixed both scalar calls:
   - `database.scalar(System.configured)` → `database.scalar(select(System.configured))`
   - `database.scalar(System.updated)` → `database.scalar(select(System.updated))`

No other changes were made.

### Compose change

`/opt/media-stack/arr/docker-compose.yaml` — added a read-only bind mount to the `bazarr` service volumes:

```yaml
- "/opt/media-stack/appdata/bazarr/fix/ui.py:/app/bazarr/bin/bazarr/app/ui.py:ro"
```

This mount shadows the container's built-in `ui.py` with the patched version. It survives container restarts and image re-pulls as long as the compose file is unchanged.

---

## Removal Condition — This Patch Must Be Cleaned Up

**When Bazarr updates to a version that fixes this bug upstream, the bind mount must be removed from the compose file and the fix directory can be deleted. Leaving it in place after an upstream fix will silently mask the updated file or break if the file path changes in a newer image.**

### How to tell if the upstream fix is in

After pulling a new Bazarr image, before restarting with the bind mount in place, check whether the upstream code already uses `select()`:

```bash
# Start a temporary container to inspect, bypassing the bind mount
docker run --rm --entrypoint grep \
  lscr.io/linuxserver/bazarr:latest \
  -n "select(System" /app/bazarr/bin/bazarr/app/ui.py
```

If that returns matches, the upstream image has the fix. Remove the bind mount entry from the compose file and delete `/opt/media-stack/appdata/bazarr/fix/` before restarting.

If it returns nothing, the bug is still present — keep the bind mount.

### Cleanup steps (when upstream fix is confirmed)

```bash
# 1. Remove the bind mount line from compose
sudo nano /opt/media-stack/arr/docker-compose.yaml
# Delete: - "/opt/media-stack/appdata/bazarr/fix/ui.py:/app/bazarr/bin/bazarr/app/ui.py:ro"

# 2. Restart Bazarr
cd /opt/media-stack/arr && sudo docker compose up -d bazarr

# 3. Verify isConfigured is still true
curl -s http://10.20.30.120:6767/ | grep -o '"isConfigured":[^,}]*'

# 4. Remove the fix directory
sudo rm -rf /opt/media-stack/appdata/bazarr/fix/
```

---

## Current Stack State (as of 2026-03-28)

### Container lineup

| Container | Image | Port | Status | Compose file |
|---|---|---|---|---|
| jellyfin | `jellyfin/jellyfin:latest` | 8096 | Up | `core/docker-compose.yaml` |
| plex | `linuxserver/plex:latest` | 32400 | Up | `core/docker-compose.yaml` |
| sonarr | `linuxserver/sonarr:latest` | 8989 | Up | `arr/docker-compose.yaml` |
| radarr | `linuxserver/radarr:latest` | 7878 | Up | `arr/docker-compose.yaml` |
| bazarr | `linuxserver/bazarr:latest` | 6767 | Up | `arr/docker-compose.yaml` |
| prowlarr | `linuxserver/prowlarr:latest` | 9696 | Up | `arr/docker-compose.yaml` |
| cleanuparr | `cleanuparr/cleanuparr:latest` | 11011 | Up | `arr/docker-compose.yaml` |
| gluetun | `qmcgaw/gluetun:latest` | 8080, 6789, 8000 | Up (healthy) | `downloaders/docker-compose.yaml` |
| sabnzbd | `linuxserver/sabnzbd:latest` | 6789 (via gluetun) | Up | `downloaders/docker-compose.yaml` |
| qbittorrent | `linuxserver/qbittorrent:latest` | 8080 (via gluetun) | Up | `downloaders/docker-compose.yaml` |

All containers are on the `arr_default` Docker network unless noted. `sabnzbd` and `qbittorrent` use `network_mode: service:gluetun` — their traffic is routed entirely through the gluetun VPN container.

### Storage — virtiofs mounts

The VM has two host datasets presented via virtiofs:

| Mount point | virtiofs tag | Host dataset | Size | Use |
|---|---|---|---|---|
| `/srv/data/media` | `tank-media` | `tank/media` on Proxmox host | 18T | Media library (read-only in Jellyfin/Plex, read-write at virtiofs level) |
| `/srv/data/downloads` | `tank-downloads` | `tank/downloads` on Proxmox host | 18T | Download working area |

App config and state live on the VM root disk at `/opt/media-stack/appdata/<container>/`. This is backed up via Proxmox vzdump. The virtiofs datasets are **not** in any automated backup or snapshot schedule.

Sonarr, Radarr, SABnzbd, and qBittorrent all see `/srv/data` as `/data` inside the container. Jellyfin and Plex see `/srv/data/media` as `/media:ro`.

### Prowlarr indexer state

Live check on 2026-03-28 shows **7 indexers configured, both protocols present**:

| Indexer | Protocol | Enabled |
|---|---|---|
| NZBFinder | Usenet | Yes |
| NZBgeek | Usenet | Yes |
| NzbPlanet | Usenet | Yes |
| Knaben | Torrent | Yes |
| LimeTorrents | Torrent | Yes |
| TorrentDownload | Torrent | Yes |
| TVChaosUK | Torrent | Yes |

Prowlarr is configured with `fullSync` to both Sonarr and Radarr. There is no torrent indexer gap as of this date — a previous understanding that only Usenet indexers were configured appears to have been outdated.

---

## Relevant File Locations

| File | Purpose |
|---|---|
| `/opt/media-stack/appdata/bazarr/fix/ui.py` | Patched ui.py — the active fix |
| `/opt/media-stack/arr/docker-compose.yaml` | Contains the bind mount entry |
| `/app/bazarr/bin/bazarr/app/ui.py` | Container path being shadowed by the bind mount |
| `/opt/media-stack/appdata/bazarr/config/config.yaml` | Bazarr runtime config |
| `/opt/media-stack/appdata/bazarr/db/bazarr.db` | Bazarr SQLite database |
| `/opt/media-stack/appdata/bazarr/log/bazarr.log` | Bazarr application log |
