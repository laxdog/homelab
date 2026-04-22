# Media Routing Split (Internal vs External)

Source of truth: `config/homelab.yaml`.

## Internal (`*.laxdog.uk`)
- Purpose: LAN/Tailscale access without Authentik prompt at NPM.
- Path: client -> internal DNS -> NPM (`10.20.30.154`) -> media backend (`10.20.30.120:*`).
- Servarr behavior (`sonarr`/`radarr`/`prowlarr`): keep app auth at `Forms + DisabledForLocalAddresses`; internal proxied `*.laxdog.uk` requests currently return UI `200` (no login prompt) while external `*.lax.dog` remains upstream-authenticated.
- Hosts:
  - `jellyfin.laxdog.uk` -> `10.20.30.167:8097` (CT167 jellyfin-hw)
  - `prowlarr.laxdog.uk` -> `10.20.30.120:9696`
  - `sonarr.laxdog.uk` -> `10.20.30.120:8989`
  - `radarr.laxdog.uk` -> `10.20.30.120:7878`
  - `cleanuparr.laxdog.uk` -> `10.20.30.120:11011`
  - `sabnzbd.laxdog.uk` -> `10.20.30.120:6789`
  - `qbittorrent.laxdog.uk` -> `10.20.30.120:8080`

## External (`*.lax.dog`)
- Purpose: externally addressable hostnames guarded by Authentik forward auth at NPM.
- Guard: NPM `authentik_protect: true` on each media external host.
- Hosts prepared in NPM/Authentik:
  - `plex.lax.dog`
  - `jellyfin.lax.dog`
  - `prowlarr.lax.dog`
  - `sonarr.lax.dog`
  - `radarr.lax.dog`
  - `cleanuparr.lax.dog`
  - `sabnzbd.lax.dog`
  - `qbittorrent.lax.dog`

## Implementation Notes
- NPM config path: `config.npm.proxy_hosts` + `config.npm.external_proxy_hosts`.
- Authentik app/outpost path: `config.authentik.proxy_apps`.
- Dashboard links are generated from `config.npm.proxy_hosts` (internal URLs).
- Downloader VPN boundary is unchanged: SABnzbd and qBittorrent still run behind Gluetun.

## Jellyfin caveat
- Current live state is inconsistent with the intended client-friendly model:
  - `jellyfin.laxdog.uk` is LAN-open at NPM and points to CT167.
  - `jellyfin.lax.dog` is still behind Authentik forward-auth and points to CT167.
- Once Jellyfin-native LDAP login is working, `jellyfin.lax.dog` should be removed from the
  forward-auth path in a narrow ingress cutover pass. Leaving forward-auth in front of Jellyfin
  creates stacked auth and is hostile to native clients.
- No routing or forward-auth change was made during the LDAP groundwork pass.

## Validation Approach
- Internal DNS checks should use authoritative resolver directly (`dig @10.20.30.53 ...`) and cross-check when resolver drift is suspected.
- NPM checks should use SNI-correct requests (`curl --resolve host:443:10.20.30.154 https://host/`).
- Use GET semantics for app UI checks where HEAD is known to be misleading.
- If internal Servarr auth behavior regresses, capture backend request headers on VM120 before redesigning routing (source IP and `X-Forwarded-*` from NPM).
