#!/usr/bin/env python3
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple


def _auth_header(username: str, password: str) -> str:
    token = f"{username}:{password}".encode("utf-8")
    return "Basic " + urllib.request.base64.b64encode(token).decode("ascii")


def request_json(
    method: str,
    url: str,
    username: str,
    password: str,
    payload: Optional[Dict] = None,
    timeout: int = 60,
    ok_statuses: Tuple[int, ...] = (200, 201, 202),
) -> Dict:
    body = None
    headers = {"Accept": "application/json", "Authorization": _auth_header(username, password)}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status not in ok_statuses:
                raise RuntimeError(f"{method} {url}: unexpected status {resp.status}")
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if exc.code in ok_statuses:
            return json.loads(raw) if raw else {}
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {raw}") from exc


def couch_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def list_databases(base: str, user: str, password: str) -> List[str]:
    data = request_json("GET", couch_url(base, "_all_dbs"), user, password)
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected _all_dbs response: {data}")
    return data


def ensure_database(base: str, user: str, password: str, db: str) -> None:
    request_json(
        "PUT",
        couch_url(base, urllib.parse.quote(db, safe="")),
        user,
        password,
        ok_statuses=(201, 202, 412),
    )


def get_db_security(base: str, user: str, password: str, db: str) -> Dict:
    return request_json("GET", couch_url(base, f"{urllib.parse.quote(db, safe='')}/_security"), user, password)


def set_db_security(base: str, user: str, password: str, db: str, sec: Dict) -> None:
    request_json(
        "PUT",
        couch_url(base, f"{urllib.parse.quote(db, safe='')}/_security"),
        user,
        password,
        payload=sec,
        ok_statuses=(200, 201),
    )


def fetch_all_docs(base: str, user: str, password: str, db: str) -> List[Dict]:
    path = f"{urllib.parse.quote(db, safe='')}/_all_docs?include_docs=true&attachments=true"
    data = request_json("GET", couch_url(base, path), user, password, timeout=120)
    rows = data.get("rows", [])
    docs = [row.get("doc") for row in rows if row.get("doc") and not row.get("id", "").startswith("_design/_auth")]
    return docs


def fetch_deleted_docs(base: str, user: str, password: str, db: str) -> List[Dict]:
    path = f"{urllib.parse.quote(db, safe='')}/_changes?since=0&style=all_docs&include_docs=true"
    data = request_json("GET", couch_url(base, path), user, password, timeout=120)
    results = data.get("results", [])
    deleted_docs = []
    for row in results:
        if row.get("deleted"):
            doc = row.get("doc") or {}
            if doc.get("_id") and doc.get("_rev"):
                doc["_deleted"] = True
                deleted_docs.append(doc)
    return deleted_docs


def bulk_write(base: str, user: str, password: str, db: str, docs: List[Dict], chunk_size: int = 500) -> None:
    for i in range(0, len(docs), chunk_size):
        chunk = docs[i : i + chunk_size]
        payload = {"docs": chunk, "new_edits": False}
        request_json(
            "POST",
            couch_url(base, f"{urllib.parse.quote(db, safe='')}/_bulk_docs"),
            user,
            password,
            payload=payload,
            timeout=120,
            ok_statuses=(201, 202),
        )


def db_stats(base: str, user: str, password: str, db: str) -> Dict:
    return request_json("GET", couch_url(base, urllib.parse.quote(db, safe="")), user, password)


def choose_dbs(all_dbs: List[str], selected: List[str], include_system: bool) -> List[str]:
    if selected:
        missing = [db for db in selected if db not in all_dbs]
        if missing:
            raise RuntimeError("DBs missing on source: " + ", ".join(missing))
        return selected
    if include_system:
        return all_dbs
    return [db for db in all_dbs if not db.startswith("_")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate CouchDB DBs using _all_docs + _bulk_docs.")
    parser.add_argument("--src-url", required=True)
    parser.add_argument("--src-user", required=True)
    parser.add_argument("--src-pass", required=True)
    parser.add_argument("--dst-url", required=True)
    parser.add_argument("--dst-user", required=True)
    parser.add_argument("--dst-pass", required=True)
    parser.add_argument("--db", action="append", default=[], help="DB name to migrate (repeatable)")
    parser.add_argument("--include-system", action="store_true", help="Include _users/_replicator if --db not set")
    args = parser.parse_args()

    all_dbs = list_databases(args.src_url, args.src_user, args.src_pass)
    dbs = choose_dbs(all_dbs, args.db, args.include_system)
    print("Databases selected:", ", ".join(dbs))

    failures = 0
    for db in dbs:
        print(f"\nMigrating {db} ...")
        ensure_database(args.dst_url, args.dst_user, args.dst_pass, db)
        docs = fetch_all_docs(args.src_url, args.src_user, args.src_pass, db)
        deleted_docs = fetch_deleted_docs(args.src_url, args.src_user, args.src_pass, db)
        if deleted_docs:
            docs.extend(deleted_docs)
        print(f"docs fetched: {len(docs)} (deleted={len(deleted_docs)})")
        if docs:
            bulk_write(args.dst_url, args.dst_user, args.dst_pass, db, docs)
        if db != "_users":
            sec = get_db_security(args.src_url, args.src_user, args.src_pass, db)
            set_db_security(args.dst_url, args.dst_user, args.dst_pass, db, sec)

        src = db_stats(args.src_url, args.src_user, args.src_pass, db)
        dst = db_stats(args.dst_url, args.dst_user, args.dst_pass, db)
        src_counts = (src.get("doc_count"), src.get("doc_del_count"))
        dst_counts = (dst.get("doc_count"), dst.get("doc_del_count"))
        print(f"counts src={src_counts} dst={dst_counts}")
        if src_counts != dst_counts:
            failures += 1
            print("count mismatch")

    if failures:
        raise SystemExit(1)
    print("\nMigration completed successfully.")


if __name__ == "__main__":
    main()
