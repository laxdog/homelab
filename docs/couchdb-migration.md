# CouchDB Migration

This runbook migrates CouchDB data from the old host to the new homelab instance.

## Script

- `scripts/couchdb_migrate.py`

It migrates DBs using CouchDB `_replicate` and validates `doc_count` + `doc_del_count`.

## Typical command

```bash
python3 scripts/couchdb_migrate.py \
  --src-url http://10.20.30.128:5984 \
  --src-user admin \
  --src-pass '<old-admin-password>' \
  --dst-url http://10.20.30.165:5984 \
  --dst-user admin \
  --dst-pass '<new-admin-password>' \
  --db obsidian_main \
  --db obsidian_myvault
```

## Notes

- Prefer explicit DB list for Obsidian migrations.
- Keep old CouchDB online and read-only for rollback until clients are stable.
- If source admin password is unknown, set a temporary admin password on old CouchDB and rotate after migration.
