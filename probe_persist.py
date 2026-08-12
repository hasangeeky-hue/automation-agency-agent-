# -*- coding: utf-8 -*-
"""Does a write to the job store actually stick? Evidence, not theory.

revive_failed.py reported 60 revived; the very next read showed the
same 60 still failed, with their ORIGINAL timestamps. Both cannot be
innocent. This writes one harmless marker to one job and reads it back
three ways: through the store's own connection, through a brand new
connection, and as raw column vs JSON. It also names the database and
every other backend holding a connection, because "two stacks on one
database" and "an open transaction" look identical from one side.

Nothing here changes a job's status. The marker is a scratch field.

  docker compose -f deploy/docker-compose.yml exec -T api python - \
      < probe_persist.py
"""
from __future__ import annotations

import os


def main() -> int:
    from content_engine_api import get_store
    store = get_store()
    conn = store._conn
    cur = conn.cursor()

    print("=" * 70)
    print("PERSISTENCE PROBE")
    print("=" * 70)

    cur.execute("SELECT current_database(), current_schema(), "
                "pg_backend_pid(), version()")
    db, schema, pid, ver = cur.fetchone()
    print(f"\ndatabase={db} schema={schema} backend_pid={pid}")
    print("server: " + str(ver)[:60])
    print("DATABASE_URL host: "
          + str(os.getenv("DATABASE_URL", "?")).split("@")[-1])

    cur.execute("SELECT count(*) FROM jobs")
    print(f"rows in jobs: {cur.fetchone()[0]}")

    # is this connection sitting inside an open transaction?
    print(f"connection transaction status: {conn.info.transaction_status}")

    print("\n--- every backend on this database ---")
    cur.execute("SELECT pid, state, application_name, "
                "left(coalesce(query,''),60), "
                "age(now(), coalesce(xact_start, now())) "
                "FROM pg_stat_activity WHERE datname = current_database()")
    for row in cur.fetchall():
        print("  " + " | ".join(str(x) for x in row))

    # ---- the actual experiment -----------------------------------------
    cur.execute("SELECT job_id, status, data->>'status', updated_at "
                "FROM jobs WHERE status='failed' "
                "ORDER BY updated_at DESC LIMIT 1")
    row = cur.fetchone()
    conn.rollback()
    if not row:
        print("\nno failed job to probe with - nothing to prove here")
        return 0
    jid, col_status, json_status, before_at = row
    print(f"\nprobe job: {jid}")
    print(f"  before: column={col_status} json={json_status} "
          f"updated_at={before_at}")

    job = store.get(jid)
    job.setdefault("payload", {})["_persist_probe"] = "written by probe"
    store.save(job)
    print("  store.save() returned without error")

    cur2 = conn.cursor()
    cur2.execute("SELECT updated_at, data->'payload'->>'_persist_probe' "
                 "FROM jobs WHERE job_id = %s", (jid,))
    same = cur2.fetchone()
    conn.rollback()
    print(f"  read back on the SAME connection: updated_at={same[0]} "
          f"marker={same[1]!r}")

    dsn = getattr(store, "_dsn", None) or os.getenv("DATABASE_URL")
    try:
        import psycopg
        with psycopg.connect(dsn) as c2:
            with c2.cursor() as c2c:
                c2c.execute("SELECT updated_at, "
                            "data->'payload'->>'_persist_probe', status "
                            "FROM jobs WHERE job_id = %s", (jid,))
                fresh = c2c.fetchone()
        print(f"  read back on a NEW connection:  updated_at={fresh[0]} "
              f"marker={fresh[1]!r} status={fresh[2]}")
        verdict = ("THE WRITE STICKS - the revive path is what to look at"
                   if fresh[1] else
                   "THE WRITE VANISHED - saves are not reaching this table")
    except Exception as exc:                          # noqa: BLE001
        print("  second connection failed: " + repr(exc)[:120])
        verdict = "could not confirm with a second connection"

    print("\nVERDICT: " + verdict)
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
