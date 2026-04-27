# Obsidian

CT175 (`10.20.30.175`). Runs the [linuxserver/obsidian](https://github.com/linuxserver/docker-obsidian) Webtop image — full Obsidian.app accessed in a browser via KasmVNC. Joins the existing CouchDB on CT128 (`obsidian_main` DB) as another LiveSync peer alongside the Mac/phone, and exposes the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin so MCP servers (and other agents) can read/write the vault programmatically.

## Architecture

```
Mac / phone (LiveSync peers)
        ↑
        │ HTTPS replication
        ↓
CT128 couchdb (obsidian_main)
        ↑
        │ HTTPS replication
        ↓
CT175 obsidian (this LXC)
  ├── /config           — Obsidian config + plugins (host: ./config)
  └── /config/vault     — materialised vault, owned by uid 1000
        ↑
        │ HTTPS Local REST API (plugin runs inside Obsidian)
        ↓
  obsidian-api.laxdog.uk → MCP server → Claude Code
```

## Repo-managed pieces

Everything except the one-time GUI bootstrap is declared here:

| What | Where |
|---|---|
| LXC (id 175, 2 GB RAM, 16 GB disk, ssd-mirror) | `config/homelab.yaml` `services.lxcs.obsidian` (Terraform reads this) |
| Docker compose for `lscr.io/linuxserver/obsidian:latest` | `ansible/roles/obsidian/templates/docker-compose.yaml.j2` |
| Webtop basic-auth user/password | `config.passwords.obsidian` + vaulted `obsidian_webtop_password` |
| AdGuard rewrites for `obsidian.laxdog.uk` and `obsidian-api.laxdog.uk` | `config/homelab.yaml` `adguard.rewrites` |
| NPM proxy hosts (UI on :3000, REST API on :27123, both internal-only) | `config/homelab.yaml` `npm.proxy_hosts` |
| Cert 17 SAN expansion | `config/homelab.yaml` `npm.certificates[0].domains` |
| Heimdall / Organizr exclusions for `obsidian-api.laxdog.uk` | `ansible/roles/heimdall/tasks/main.yml`, `ansible/roles/organizr/tasks/main.yml` |
| Nagios port checks (Webtop :3000, REST API :27123) | `config/homelab.yaml` `nagios.service_ports` |
| Playbook play (`obsidian_hosts`) | `ansible/playbooks/guests.yml` |

## What is NOT repo-managed (one-time GUI bootstrap)

These steps run once after the LXC is up and the container is running. The Local REST API plugin generates a key on first start that we cannot pre-seed; everything else is just one-time plugin install + paste.

### 0. Prerequisites

- LXC 175 created (`terraform plan` / `terraform apply`).
- Container deployed (`scripts/run.py guests` or targeted Ansible apply on `obsidian_hosts`).
- DNS rewrites + NPM cert applied.
- Browse to `https://obsidian.laxdog.uk`. The KasmVNC login should appear. Username: `obsidian`. Password: from vault, `obsidian_webtop_password`.

### 1. Open or create the vault

1. Inside the Obsidian app (running in the browser desktop), choose **Open folder as vault**.
2. Point at `/config/vault` (the host-side `./vault` is bind-mounted there).
3. Trust the vault when prompted.

### 2. Install Self-hosted LiveSync

1. Settings → Community plugins → enable, then browse for **Self-hosted LiveSync**, install, enable.
2. On the Mac, in LiveSync settings → **Copy Setup URI**. (Encodes the entire LiveSync config including E2EE passphrase.)
3. In the new server-side Obsidian, LiveSync settings → **Open Setup URI** → paste.
4. Confirm the import; LiveSync will start a fetch from the existing `obsidian_main` DB on CT128. First sync pulls ~6,500 docs / ~22 MB.
5. Set sync mode to **LiveSync** (continuous) once the initial fetch completes.

This LXC is now another peer in the same LiveSync mesh as Mac/phone.

### 3. Install Local REST API

1. Community plugins → browse for **Local REST API**, install, enable.
2. Open its settings. Note the auto-generated **API Key** — copy it.
3. Enable **Non-encrypted (HTTP) Server**. Default port is `27123`. (HTTPS on `27124` stays on by default; we proxy the HTTP port through NPM for simpler upstream config.)
4. Confirm the plugin is bound to `0.0.0.0` (or `host: 0.0.0.0` in plugin settings) so the container's port mapping reaches it. If it's bound to `127.0.0.1` only, requests from outside the container will hit the port but get nothing.
5. Verify from any host on the LAN/Tailscale: `curl -k -H "Authorization: Bearer <key>" https://obsidian-api.laxdog.uk/`. Should return JSON metadata.

### 4. Persist the API key

Add the API key to the vault and update `validation.vault_required_vars`:

```bash
ansible-vault encrypt_string --vault-password-file ~/.ansible_vault_pass \
  --name 'obsidian_local_rest_api_key' '<paste-key-here>' \
  >> ansible/secrets.yml
```

(Move the produced block to its alphabetical home in `secrets.yml`.) Then add `obsidian_local_rest_api_key` to `validation.vault_required_vars` in `config/homelab.yaml` so future apply-time validation fails fast if it's missing.

### 5. Optional plugins

Install whatever else you actually use (Templater, Dataview, etc.) the same way. None of these are repo-managed — they live in the materialised vault under `/config/vault/.obsidian/plugins/` and replicate via LiveSync.

## MCP integration (workstation-side)

After bootstrap, point Claude Code at the REST API. Two candidate servers, decide here:

- [`MarkusPfundstein/mcp-obsidian`](https://github.com/MarkusPfundstein/mcp-obsidian) — most established, simple CRUD-style tools. Safer first pick.
- [`j-shelfwood/obsidian-local-rest-api-mcp`](https://github.com/j-shelfwood/obsidian-local-rest-api-mcp) — newer, AI-native task-oriented tool surface.

Either way, configure with:

```
URL:    https://obsidian-api.laxdog.uk
Bearer: <obsidian_local_rest_api_key from secrets.yml>
```

and register in your Claude Code MCP config. Self-signed cert behind NPM is fine — NPM terminates with the laxdog-internal-le cert, so the workstation client just sees a normal LE cert.

## Operational notes

- **Restart container:** `ssh root@10.20.30.175 'cd /docker/docker-compose-obsidian && docker compose restart'`
- **Tail logs:** `ssh root@10.20.30.175 'cd /docker/docker-compose-obsidian && docker compose logs -f'`
- **Vault on disk:** `/docker/docker-compose-obsidian/config/vault/` on CT175. Standard markdown — back this up if you want a plaintext snapshot independent of CouchDB. (LiveSync's CouchDB-side data is encrypted; the on-disk copy here is plaintext.)
- **Plugin updates:** Community plugins update from inside Obsidian. Updates are device-specific in LiveSync (each peer manages its own plugin install state). The `usePluginSyncV2` flag means plugin *settings* sync; the binaries do not.
- **If LiveSync trips the rebuild guard** (e.g. someone wipes `obsidian_main` again): same recovery as the original incident — clear `_security` is still set with `livesync` member, and use **"Fetch from remote"** here, not "Overwrite remote", so this peer doesn't accidentally clobber the canonical Mac copy.

## Future options

- **Authentik forward-auth on the Webtop UI only.** Keep `obsidian-api.laxdog.uk` unprotected (API key is enough), add Authentik forward-auth on `obsidian.laxdog.uk` if the basic-auth fence is judged insufficient. Pure NPM config change — no code.
- **External access (`lax.dog`).** If you ever want to hit the Webtop from off-LAN/off-Tailscale, add a Cloudflare A record + external NPM proxy host + Authentik forward-auth. Don't expose `obsidian-api.laxdog.uk` externally; route MCP traffic only over Tailscale.
- **Headless materialised vault as backup source.** The `./config/vault` dir on CT175 is a continuously-synced plaintext copy. A periodic ZFS snapshot or rsync of that path is a useful disaster-recovery angle independent of CouchDB.

## See also

- `docs/runbooks/add-new-guest.md` — guest provisioning
- AGENTS.md → "Domain architecture" — laxdog.uk vs lax.dog rules
- Memory `project_obsidian_couchdb.md` — the `livesync` user / `_security` gotcha that bit us when the CouchDB DB was recreated
