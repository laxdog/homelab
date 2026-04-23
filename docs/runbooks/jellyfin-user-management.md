# Jellyfin User Management

This runbook covers the homelab-owned auth workflow for CT167 Jellyfin.

## Current model
- Jellyfin runs on CT167 and uses native Jellyfin login on both `jellyfin.laxdog.uk` and `jellyfin.lax.dog`.
- Jellyfin authenticates normal users against the Authentik LDAP outpost on CT170.
- Local Jellyfin `admin` is permanent break-glass and should not be removed.
- Normal users should be created through Authentik, not manually inside Jellyfin.

## Operator workflow: invite a new Jellyfin user
1. Log into Authentik at `https://auth.lax.dog/if/admin/`.
2. Create an invitation bound to flow `jellyfin-user-enrollment`.
3. Set the invitation to `single_use=true`.
4. Set `fixed_data` for the fields you want to prefill or lock. Safe baseline:
   ```json
   {
     "username": "newuser",
     "email": "newuser@example.com",
     "name": "New User"
   }
   ```
5. Send the invite link to the user:
   - `https://auth.lax.dog/if/flow/jellyfin-user-enrollment/?itoken=<invite_uuid>`
6. The user completes Authentik enrollment and is created as an internal Authentik user in group `jellyfin-users`.
7. On the first successful Jellyfin login, the Jellyfin LDAP plugin auto-creates the Jellyfin profile.

## User workflow: first login
1. Open the Authentik invite link.
2. Confirm or fill the prompted account details.
3. Set an Authentik password.
4. After enrollment completes, go to either Jellyfin hostname:
   - `https://jellyfin.laxdog.uk`
   - `https://jellyfin.lax.dog`
5. Log in to Jellyfin with the Authentik username and password.

## Password reset / recovery
- Self-service forgot-password is currently **not** available.
- Exact blocker: this estate has no repo-managed Authentik SMTP/email delivery configured, no Authentik email stage, and no recovery flow bound to the brand. Without mail delivery there is no safe self-service reset path.
- Until SMTP is implemented, an operator must reset the user password in Authentik.

## Operator workflow: reset a Jellyfin user's password
1. Log into Authentik admin.
2. Find the Authentik user record for the Jellyfin user.
3. Set a new password in Authentik.
4. Tell the user to log back into Jellyfin with the new Authentik password.

## Jellyfin-local users
- Keep local Jellyfin `admin` as break-glass.
- Do not create long-term local non-admin Jellyfin users unless there is a temporary incident workaround.
- If a legacy local Jellyfin user should move to central auth, delete the local Jellyfin account first, then bring the user back through the Authentik invite flow.
