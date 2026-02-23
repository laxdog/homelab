# Authentik

This doc tracks the Authentik SSO setup and forward-auth integration. It will evolve as we implement.

## Goals
- One Authentik instance used for:
  - External access (`lax.dog`) via NPM forward-auth.
  - Internal SSO (`laxdog.uk`) for OIDC-enabled apps on LAN.
- Keep internal access working even when external access is disabled.

## Domains
- External: `auth.lax.dog`
- Internal: `auth.laxdog.uk`

Both hostnames should point to the same Authentik instance via NPM.

## Current decisions
- Authentik runs as a single instance.
- LXC: `170` / `10.20.30.170`.
- External hosts (`lax.dog`) are always protected via forward-auth.
- Internal hosts (`laxdog.uk`) remain LAN-open unless the app supports OIDC and needs identity.
- Apps with native client auth (Jellyfin, Plex) are not put behind forward-auth to avoid breaking
  non-browser clients. They keep local logins and may optionally add OIDC for web SSO.
- Authentik config is managed by a container-side script (no click-ops).

## High-level plan
1. Provision Authentik LXC and install via Docker Compose.
2. Create NPM proxy hosts for `auth.lax.dog` + `auth.laxdog.uk`.
3. Configure Authentik via the container-side script:
   - `ansible/roles/authentik/templates/authentik_sso_setup.py.j2`
   - Custom auth flow with TOTP for admin services.
   - Proxy providers + applications for admin routes.
   - Embedded outpost configuration.
4. Update NPM to enforce forward-auth on all external (`lax.dog`) proxy hosts.
5. Add validation checks:
   - Authentik reachable at both domains via HTTPS.
   - Forward-auth protects external hosts.
   - OIDC login works for at least one app.

## Security notes
- Use Cloudflare proxy for `lax.dog` (hide origin).
- Restrict NPM external access to Cloudflare IP ranges only. Cloudflare publishes its IPv4/IPv6 ranges. citeturn6open0turn6open1
- Rate-limit or WAF rules at Cloudflare.
- Prefer OIDC where supported; fall back to forward-auth for the rest.

## OIDC support matrix
Native or well-supported OIDC:
- FreshRSS (native OpenID Connect support). citeturn4open4
- Jellyfin (SSO plugin supports OIDC). citeturn4open3
- Proxmox (OpenID Connect realms). citeturn4open0
- Nextcloud (OIDC user auth via `user_oidc`). citeturn4open1
- ownCloud (OIDC user auth). citeturn4open2

Proxy-protected (no native OIDC in settings docs):
- Radarr (`None`, `Basic`, `Forms`, or `External` auth). citeturn4search3
- Sonarr (`None`, `Basic`, `Forms`). citeturn4search4
- Prowlarr (`Basic`, `Forms`, `External`). citeturn4search0
- Lidarr (`None`, `Basic`, `Forms`). citeturn4open0
- Bazarr (`Basic` or `Form`). citeturn4open1
- Home Assistant uses its own auth providers (no OIDC provider listed). citeturn4search2
- Healthchecks (supports a login or an auth header, but not OIDC). citeturn5open0

Notes:
- For proxy-only apps, enforce Authentik forward-auth on external hosts.
- For OIDC-capable apps, configure them to use Authentik for identity on LAN and external.
- For client apps that don't handle OIDC (Jellyfin/Plex), keep NPM access lists "public" and rely on
  the app's native auth. Do not apply forward-auth in front of these services.

## Related services to consider
Requests / media discovery:
- Jellyseerr (request management for Jellyfin/Emby). citeturn7open0
- Overseerr (request management for Plex). citeturn7open1

File sharing / collaboration:
- Nextcloud (OIDC support via `user_oidc`). citeturn4open1
- ownCloud (OIDC user auth). citeturn4open2

## Open items
- Decide which OIDC-capable apps to wire up first (Jellyfin and FreshRSS are good starters).
- Jellyfin: keep local login enabled for client apps; consider OIDC SSO for web UI only.
