# Jellyfin

The live playback Jellyfin runs on CT167 (`jellyfin-hw`) and is exposed via NPM.

## Policy
- Jellyfin should not be protected by NPM forward-auth.
- Jellyfin uses **native logins** so Android/TV clients keep working.
- Local `admin` stays as permanent break-glass admin.
- Authentik LDAP is the preferred central-auth model for Jellyfin.

## Hostnames
- Internal: `jellyfin.laxdog.uk`
- External: `jellyfin.lax.dog`

## Runtime layout
- Compose project: `/opt/jellyfin-hw/docker-compose.yaml`
- Appdata: `/opt/jellyfin-hw/config`
- Cache: `/opt/jellyfin-hw/cache`
- Hardware acceleration: `/dev/dri` passed through for Intel Quick Sync
- Published ports:
  - `8097` -> Jellyfin HTTP
  - `8920` -> Jellyfin HTTPS

## Current auth model (2026-04-23)
- **Both hostnames present native Jellyfin login.** No NPM forward-auth in front of either:
  - `jellyfin.laxdog.uk` — LAN/Tailscale, never had forward-auth.
  - `jellyfin.lax.dog` — external; forward-auth removed 2026-04-23 after Jellyfin-native LDAP was validated.
- **LDAP-backed login** via the Authentik LDAP outpost on CT170:636. Jellyfin's LDAP Authentication plugin on CT167 binds as `cn=jellyfin-ldap-bind,ou=users,DC=jellyfin,DC=laxdog,DC=uk` and filters to `cn=jellyfin-users`. Pilot user `ldapservice` succeeds on both hostnames.
- **Local `admin`** remains as permanent break-glass (independent of Authentik/LDAP health).
- **Local `cjess`** has been deleted from Jellyfin and should only be re-added later through the Authentik invite flow.

## User management workflow
- Normal Jellyfin users should be created in Authentik, not manually inside Jellyfin.
- Repo-managed Authentik flow `jellyfin-user-enrollment` exists for invitation-based self-enrollment into group `jellyfin-users`.
- The invite flow creates an internal Authentik user; Jellyfin auto-creates the Jellyfin profile on first successful LDAP login.
- Runbook: `docs/runbooks/jellyfin-user-management.md`

## Password reset posture
- Local `admin` remains the only permanent Jellyfin-local account.
- Authentik-backed Jellyfin users do **not** have self-service forgot-password yet.
- Exact blocker: no repo-managed Authentik SMTP/email delivery and no recovery flow bound to the Authentik brand.
- Until SMTP exists, operators must reset Jellyfin-user passwords in Authentik.

## Repo-managed LDAP groundwork
- Source of truth:
  - `config/homelab.yaml` under `jellyfin.ldap`
  - `ansible/roles/jellyfin-hw/tasks/main.yml`
  - `ansible/roles/jellyfin-hw/templates/ldap-plugin-config.xml.j2`
- Managed pieces:
  - Jellyfin LDAP Authentication plugin install
  - Plugin configuration file
  - LDAP CA export on CT167
  - Local admin validation after changes
