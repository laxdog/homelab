# Prod DB Tailscale reachability — clarifications before implementing

**Date:** 2026-04-20
**Context:** homelab mirroring staging's DB-access pattern onto prod VPS.

## Homelab → RR

Staging pattern (CT163) for reference: `socat` on the host listens on the Tailscale IP:5432 and forwards to the DB container's internal IP; iptables on `tailscale0` restricts source peers. **Postgres config itself is untouched** — no `listen_addresses` or `pg_hba` changes on the homelab side. The `timescaledb` container stays stock; auth is whatever the image provides.

Three things needed before homelab can mirror this on prod VPS:

1. **Does the prod DB container accept connections from the docker bridge subnet?** Staging does — that's how socat reaches it. If prod is localhost-only (or pg_hba is narrower), socat forwarding won't work and we need a different approach.
2. **Prod DB credentials** — database name, worker user name, worker password. Either paste them here, or confirm that the `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` env vars on `raffle-raptor-db-1` on prod VPS are authoritative and we should pull from `docker inspect`.
3. **Confirm you want the staging pattern replicated** — socat + iptables at host level, no postgres config changes on our side. Your earlier mention of `listen_addresses` and `pg_hba` is RR-side (inside your container) — homelab's side is socat + iptables only. If you want something different, say so.

## RR → homelab (confirmation)

1. Prod DB container accepts docker bridge connections (same as staging).
2. Pull creds from `docker inspect` on `raffle-raptor-db-1` — `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` env vars authoritative.
3. Replicate staging pattern exactly.

## Implementation decision (homelab, post-RR-confirm)

- `POSTGRES_*` env vars are the **admin** credentials. Rather than use them directly for workers (admin privileges on prod DB), homelab mirrors staging's pattern of a **dedicated read-only worker user**:
  - Username: `rr_discovery_prod` (mirrors `rr_discovery_staging`).
  - Password: 32 random chars from `/dev/urandom`, vaulted as `rr_discovery_prod_db_password`.
  - Role creates the user with SELECT-only grants on public schema + `pg_hba` rule scoped to the DB container's gateway IP.
- `allowed_tailscale_source` set to two /32 entries: `100.118.218.126/32` (mums), `100.104.174.2/32` (CT173). Not tailnet-wide.

## Follow-up round — rr_worker adoption (2026-04-20, later)

RR clarified: drop `rr_discovery_prod`, provision `rr_worker` on prod with DML grants matching staging exactly. Grants: `GRANT SELECT, INSERT, UPDATE`.

Homelab recon surfaced config/reality drift on both environments before proceeding:

- Staging's ansible config declares `rr_discovery_staging` as the worker user, but the live worker actually connects as **`rr_worker`** (two idle sessions in `pg_stat_activity`). `rr_discovery_staging` is orphaned.
- Both `rr_discovery_*` and `rr_worker` had identical grants including `DELETE, REFERENCES, TRIGGER, TRUNCATE` on top of `SELECT, INSERT, UPDATE` — much broader than the role's declared SELECT-only. Someone ran ad-hoc `GRANT` statements outside the role's management.
- `rr_worker` was **already provisioned on both environments by RR directly** with passwords not known to homelab.

Prod implementation (strict, per RR's written spec):

- Role extended with `grants` config (list of priv keywords; default `['SELECT']`) — REVOKE ALL then GRANT declared set. Not additive — if a priv isn't listed, rr_worker won't have it.
- Role extended with `remove_users` config — runs `REASSIGN OWNED + DROP OWNED + DROP ROLE IF EXISTS` (identifier-safe via `format('%I', ...)` inside PL/pgSQL EXECUTE). Terminates active sessions first.
- Config change on prod VPS: `username: rr_worker`, `password_var: rr_worker_prod_db_password`, `grants: [SELECT, INSERT, UPDATE]`, `remove_users: [rr_discovery_prod]`.
- Vault: new `rr_worker_prod_db_password` (32 random chars); `rr_discovery_prod_db_password` removed.
- Password for rr_worker on prod was overwritten by the role's `ALTER ROLE` — whatever RR had set before is gone. **RR needs to pick up the new password from homelab vault before deploying prod workers.** See `docs/agents/raffle-raptor.md` §"Secret handoff".

### Verified post-apply

| check | result |
|---|---|
| `rr_worker` grants on prod | `SELECT, INSERT, UPDATE` on 14 tables (exactly) — `DELETE/REFERENCES/TRIGGER/TRUNCATE` removed |
| `rr_discovery_prod` | dropped; no longer in pg_roles |
| pg_hba.conf | `rr_worker` rules present (172.30.0.1/32 scram, reject else); `rr_discovery_prod` rules stripped |
| mums + CT173 TCP → prod:5432 | ALLOW (unchanged) |
| VM171 TCP → prod:5432 | BLOCK (unchanged) |

### Staging untouched this round

Per RR's request, staging was not modified. Staging's config/reality drift (orphaned `rr_discovery_staging`; `rr_worker` password RR-managed and not in homelab vault) is filed as a backlog item for a future coordinated cleanup.

### Impact warning for RR

**Prod `rr_worker` now has `SELECT, INSERT, UPDATE` only.** Before this session it had `SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER, TRUNCATE`. If the prod worker code uses `DELETE` or `TRUNCATE`, it will fail — this is RR getting what RR's written spec asked for, but worth verifying against the actual codebase before deploying prod workers.

## Delivered commits

Original round:
- `f81f400` refactor(rr-db-access): rename from rr-staging-db-access + support multi-source
- `7cc8b43` feat(rr-db-access): add prod VPS — rr_discovery_prod via Tailscale

Follow-up round (rr_worker):
- role changes + strict grants + remove_users + config update + vault swap + docs (see `git log --oneline` after this file was committed)

## Verified 2026-04-20 (initial round, rr_discovery_prod)

| from → to | expect | got |
|---|---|---|
| mums → prod:5432 | ALLOW | ✓ |
| CT173 → prod:5432 | ALLOW | ✓ |
| VM171 → prod:5432 | BLOCK | ✓ |
| staging-home → CT163:5432 | ALLOW (no regression) | ✓ |
| VM171 → CT163:5432 | BLOCK (no regression) | ✓ |

psql auth from mums and CT173 not exercised end-to-end — neither host has `psql` installed. RR's worker container has the pg client and is the real test. Password in homelab vault — superseded in the follow-up round below (see `rr_worker_prod_db_password`).
