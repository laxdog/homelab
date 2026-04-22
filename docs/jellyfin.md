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
- Current runtime status:
  - LDAP plugin is installed and loaded on CT167.
  - Local `admin` authentication still works after the plugin/config rollout.
  - Existing local users `admin` and `cjess` remain local in this pass.
  - Pilot LDAP login is not ready yet because Authentik LDAP bind/search validation is still
    failing from CT167.

## Current caveat
- `jellyfin.lax.dog` is still behind Authentik forward-auth at NPM today. That is not the desired
  long-term Jellyfin auth model and will need a dedicated cutover pass after LDAP login works.
