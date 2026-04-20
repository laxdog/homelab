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

## Delivered commits

- `f81f400` refactor(rr-db-access): rename from rr-staging-db-access + support multi-source
- `7cc8b43` feat(rr-db-access): add prod VPS — rr_discovery_prod via Tailscale

## Verified 2026-04-20

| from → to | expect | got |
|---|---|---|
| mums → prod:5432 | ALLOW | ✓ |
| CT173 → prod:5432 | ALLOW | ✓ |
| VM171 → prod:5432 | BLOCK | ✓ |
| staging-home → CT163:5432 | ALLOW (no regression) | ✓ |
| VM171 → CT163:5432 | BLOCK (no regression) | ✓ |

psql auth from mums and CT173 not exercised end-to-end — neither host has `psql` installed. RR's worker container has the pg client and is the real test. Password for `rr_discovery_prod` is in homelab vault at `rr_discovery_prod_db_password`; RR needs to retrieve it from the operator out-of-band (homelab doesn't share vault with RR).
