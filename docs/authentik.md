# Authentik

This doc tracks the Authentik SSO setup and forward-auth integration currently applied by this repo.

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
- Apps with native client auth (Jellyfin, Plex) should not be put behind forward-auth to avoid
  breaking non-browser clients. They should use native app auth instead.
- Authentik config is managed by a container-side script (no click-ops).

## LDAP provider pattern
- Repo-managed LDAP groundwork for Jellyfin now exists.
- Source of truth:
  - `config/homelab.yaml` under `authentik.ldap`
  - `ansible/roles/authentik/templates/authentik_sso_setup.py.j2`
  - `ansible/roles/authentik/templates/docker-compose.yaml.j2`
  - `ansible/roles/authentik/tasks/main.yml`
- Managed pieces:
  - LDAP application/provider: `Jellyfin LDAP`
  - LDAP outpost: `Jellyfin LDAP Outpost`
  - Dedicated bind user: `jellyfin-ldap-bind`
  - Dedicated Jellyfin access group: `jellyfin-users`
  - Invitation-only Jellyfin enrollment flow: `jellyfin-user-enrollment`
  - LDAPS listener on CT170 port `636`
- Current runtime status:
  - LDAP outpost container is up and healthy on CT170.
  - Provider/application/outpost objects are created from repo.
  - A dedicated bind secret is vaulted as `authentik_jellyfin_ldap_bind_password`.
  - Bind/search validation works; CT167 binds as `cn=jellyfin-ldap-bind,ou=users,DC=jellyfin,DC=laxdog,DC=uk` and filters to the `jellyfin-users` group.
  - Pilot LDAP login (`ldapservice`) succeeds against Jellyfin via the plugin on both `jellyfin.lax.dog` and `jellyfin.laxdog.uk` (2026-04-23).
  - **Jellyfin no longer sits behind NPM forward-auth.** External access via `jellyfin.lax.dog` uses native Jellyfin login with the LDAP plugin; `authentik_protect` was removed from the Jellyfin External NPM entry on 2026-04-23.
- Current certificate posture:
  - The LDAP outpost uses Authentik's self-signed certificate.
  - CT167 imports that certificate, but Jellyfin is currently configured with
    `SkipSslVerify=true` as a temporary groundwork compromise until a dedicated trusted LDAP cert
    or hostname is introduced.

## Jellyfin self-service workflow
- Repo-managed flow `jellyfin-user-enrollment` is the current safe path for future Jellyfin users.
- Flow shape:
  - Invitation stage (`Jellyfin Invite Gate`)
  - Prompt stage for `username`, `name`, `email`, and `password`
  - User-write stage that creates an **internal** Authentik user and adds it to `jellyfin-users`
  - User-login stage
- Invite links use:
  - `https://auth.lax.dog/if/flow/jellyfin-user-enrollment/?itoken=<invite_uuid>`
- This keeps signup closed by default and only allows operator-issued invites.
- Operator/user steps are documented in `docs/runbooks/jellyfin-user-management.md`.

## Recovery posture
- Authentik recovery is **not** self-service yet for Jellyfin users.
- Current runtime blockers:
  - no repo-managed SMTP/email settings in this estate
  - no Authentik email stage configured
  - no recovery flow bound to the default Authentik brand
- Do not implement a non-mail recovery flow for Jellyfin users; that would be an unsafe reset path.
- Current operator fallback: reset the user's Authentik password manually.

## Current protected hosts
`authentik_protect: true` at NPM (source: `config.npm.external_proxy_hosts`):
- `ha.lax.dog`
- `lax.dog` (apex → Heimdall)
- `prowlarr.lax.dog`
- `sonarr.lax.dog`
- `radarr.lax.dog`
- `cleanuparr.lax.dog`
- `sabnzbd.lax.dog`
- `qbittorrent.lax.dog`

No internal (`laxdog.uk`) proxy host is forward-auth-protected today.

## High-level plan
1. Provision Authentik LXC and install via Docker Compose.
2. Create NPM proxy hosts for `auth.lax.dog` + `auth.laxdog.uk`.
3. Configure Authentik via the container-side script:
   - `ansible/roles/authentik/templates/authentik_sso_setup.py.j2`
   - Custom auth flow with TOTP for admin services.
   - Proxy providers + applications for admin routes.
   - Embedded outpost configuration.
4. Update NPM to enforce forward-auth on all external (`lax.dog`) proxy hosts.
5. Validation coverage currently checks:
- Authentik reachable at both domains via HTTPS.
- Forward-auth protects external hosts.
- OIDC app login automation is pending.

## Security notes
- Use Cloudflare proxy for `lax.dog` (hide origin).
- Restrict NPM external access to Cloudflare IP ranges only (update from Cloudflare published ranges).
- Rate-limit or WAF rules at Cloudflare.
- Prefer OIDC where supported; fall back to forward-auth for the rest.

## OIDC support matrix
Native or well-supported OIDC:
- FreshRSS (native OpenID Connect support).
- Jellyfin (SSO plugin supports OIDC).
- Proxmox (OpenID Connect realms).
- Nextcloud (OIDC via `user_oidc`).
- ownCloud (OIDC user auth).

Proxy-protected (no native OIDC in settings docs):
- Radarr (`None`, `Basic`, `Forms`, or `External` auth).
- Sonarr (`None`, `Basic`, `Forms`).
- Prowlarr (`Basic`, `Forms`, `External`).
- Lidarr (`None`, `Basic`, `Forms`).
- Bazarr (`Basic` or `Form`).
- Home Assistant uses its own auth providers (no first-party OIDC provider role).
- Healthchecks supports app auth and headers, but not native OIDC login.

Notes:
- For proxy-only apps, enforce Authentik forward-auth on external hosts.
- For OIDC-capable apps, configure them to use Authentik for identity on LAN and external.
- For client apps that don't handle OIDC (Jellyfin/Plex), keep NPM access lists "public" and rely on
  the app's native auth. Do not apply forward-auth in front of these services.

## Related services to consider
Requests / media discovery:
- Jellyseerr (request management for Jellyfin/Emby).
- Overseerr (request management for Plex).

File sharing / collaboration:
- Nextcloud (OIDC support via `user_oidc`).
- ownCloud (OIDC user auth).

## Open items
- Decide which OIDC-capable apps to wire up next (FreshRSS is the obvious starter now that Jellyfin LDAP is shipped).
- LDAP TLS: current posture uses Authentik's self-signed cert with `SkipSslVerify=true` on CT167. Swap in a dedicated trusted LDAP cert or hostname, then flip SkipSslVerify off.
- Repo-managed SMTP + recovery flow for Authentik-backed Jellyfin users.
