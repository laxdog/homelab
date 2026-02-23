# SSO

This doc tracks the Authentik SSO design and how it is enforced in NPM.

## Goals
- Central SSO (Authentik) for admin services.
- TOTP MFA for admin services.
- Keep native client apps (Jellyfin/Plex) working without forward-auth.

## Policy
- **Admin services** (Proxmox, Nagios, NetAlertX, Home Assistant external access) are protected by Authentik forward-auth.
- **User services with native clients** (Jellyfin, Plex) are **not** protected by forward-auth.
- Internal (`laxdog.uk`) access remains LAN-open unless an app supports OIDC natively.
- Internal infrastructure endpoints can still be protected where needed (`router.laxdog.uk`, `unifi-primary.laxdog.uk`, `unifi-secondary.laxdog.uk`).

## How it is implemented
- Authentik is configured by an idempotent server-side script (`/scripts/authentik_sso_setup.py`)
  that runs inside the Authentik container during Ansible runs.
- The script creates/updates:
  - A custom auth flow with password + TOTP.
  - Proxy providers for admin services.
  - Applications bound to those providers.
  - Embedded outpost configuration (authentik_host bound to the internal Authentik URL).
- NPM proxy hosts use `authentik_protect: true` to inject forward-auth.

## TOTP Enrollment
The first login will prompt for TOTP enrollment (Authy is fine).
