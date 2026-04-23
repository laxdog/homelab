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
- Purpose: externally addressable hostnames, forward-auth-guarded where the client can handle a browser redirect flow.
- Guard: NPM `authentik_protect: true`, applied per-host.
- Forward-auth-guarded hosts:
  - `prowlarr.lax.dog`
  - `sonarr.lax.dog`
  - `radarr.lax.dog`
  - `cleanuparr.lax.dog`
  - `sabnzbd.lax.dog`
  - `qbittorrent.lax.dog`
- NOT forward-auth-guarded (app-native auth instead, so non-browser clients keep working):
  - `jellyfin.lax.dog` → `10.20.30.167:8097` (CT167). Jellyfin LDAP plugin against Authentik LDAP outpost on CT170:636. See `docs/jellyfin.md`.

## Implementation Notes
- NPM config path: `config.npm.proxy_hosts` + `config.npm.external_proxy_hosts`.
- Authentik app/outpost path: `config.authentik.proxy_apps`.
- Dashboard links are generated from `config.npm.proxy_hosts` (internal URLs).
- Downloader VPN boundary is unchanged: SABnzbd and qBittorrent still run behind Gluetun.

## Jellyfin ingress (current, 2026-04-23)
- Both hostnames route to the same backend — CT167 (`jellyfin-hw`) at `10.20.30.167:8097`:
  - `jellyfin.laxdog.uk` — LAN/Tailscale, LAN-open at NPM, no forward-auth.
  - `jellyfin.lax.dog` — external via Cloudflare, no forward-auth. Native Jellyfin login with LDAP plugin against Authentik LDAP outpost on CT170:636.
- Local `admin` is the permanent break-glass account (independent of Authentik/LDAP health).
- Future normal users should come in via Authentik invitation flow `jellyfin-user-enrollment`, not as manual Jellyfin-local users.
- Verified on cutover day with `/System/Info/Public` (identical `ServerId` on both hostnames) and `/Users/AuthenticateByName` with local admin (HTTP 200 + `AccessToken` on both).

## Validation Approach
- Internal DNS checks should use authoritative resolver directly (`dig @10.20.30.53 ...`) and cross-check when resolver drift is suspected.
- NPM checks should use SNI-correct requests (`curl --resolve host:443:10.20.30.154 https://host/`).
- Use GET semantics for app UI checks where HEAD is known to be misleading.
- If internal Servarr auth behavior regresses, capture backend request headers on VM120 before redesigning routing (source IP and `X-Forwarded-*` from NPM).
