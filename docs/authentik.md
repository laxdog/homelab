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

## High-level plan
1. Provision Authentik LXC and install via Docker Compose.
2. Create NPM proxy hosts for `auth.lax.dog` + `auth.laxdog.uk`.
3. Configure Authentik:
   - Admin bootstrap credentials in vault.
   - Providers and applications:
     - Forward-auth provider for NPM external routes.
     - OIDC provider(s) for supported apps (e.g., Jellyfin, FreshRSS).
4. Update NPM to enforce forward-auth on all external (`lax.dog`) proxy hosts.
5. Add validation checks:
   - Authentik reachable at both domains via HTTPS.
   - Forward-auth protects external hosts.
   - OIDC login works for at least one app.

## Security notes
- Use Cloudflare proxy for `lax.dog` (hide origin).
- Restrict NPM external access to Cloudflare IP ranges only.
- Rate-limit or WAF rules at Cloudflare.
- Prefer OIDC where supported; fall back to forward-auth for the rest.

## Open items
- Choose Authentik LXC IP/CTID.
- Decide if internal (`laxdog.uk`) hosts should require Authentik or remain LAN-only.
