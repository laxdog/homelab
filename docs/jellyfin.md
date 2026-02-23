# Jellyfin

Jellyfin runs in the `media-stack` VM and is exposed via NPM.

## Policy
- Jellyfin is **not** protected by NPM forward-auth.
- Jellyfin uses **native logins** so Android/TV clients keep working.
- Optional SSO for the web UI can be added later via the Jellyfin SSO plugin.

## Hostnames
- Internal: `jellyfin.laxdog.uk`
- External: `jellyfin.lax.dog`

## Bootstrap (no click-ops)
The media-stack role automates the initial wizard:
- Sets server name from `config.homelab.yaml` (`jellyfin.server_name`).
- Applies language/metadata defaults.
- Creates the admin user from vault (`jellyfin_admin_password`).
- Marks the startup wizard as complete.

If you ever need to re-run the bootstrap, delete the Jellyfin config directory
and re-run `./scripts/run.py guests`.
