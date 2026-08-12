# -*- coding: utf-8 -*-
"""Why the queue looks the way it looks. Read-only, lock-proof.

Run from the repo root on the VPS (no rebuild needed - it streams in):
  docker compose -f deploy/docker-compose.yml exec -T api python - \
      < diagnose_jobs.py
"""
from __future__ import annotations

import json


def main() -> int:
    from content_engine_api import get_store
    store = get_store()
    cur = store._conn.cursor()
    # a diagnostic must never hang the terminal it runs in
    cur.execute("SET statement_timeout = '8s'")

    print("=" * 70)
    print("QUEUE DIAGNOSIS - read only")
    print("=" * 70)

    print("\n--- jobs by status ---")
    cur.execute("SELECT status, count(*) FROM jobs "
                "GROUP BY status ORDER BY 2 DESC")
    for st, n in cur.fetchall():
        print(f"  {n:4} {st}")

    print("\n--- why the failed ones died (reason x count) ---")
    cur.execute("SELECT left(coalesce(data->>'halt_reason','(no reason "
                "recorded)'),120), count(*) FROM jobs "
                "WHERE status='failed' GROUP BY 1 ORDER BY 2 DESC")
    for reason, n in cur.fetchall():
        print(f"  {n:4} x | {reason}")

    print("\n--- when they died (per hour) ---")
    cur.execute("SELECT date_trunc('hour', updated_at), count(*) "
                "FROM jobs WHERE status='failed' GROUP BY 1 ORDER BY 1")
    for hour, n in cur.fetchall():
        print(f"  {hour} | {n}")

    print("\n--- five freshest corpses ---")
    cur.execute("SELECT job_id, type, "
                "left(coalesce(data->>'halt_reason',''),160) "
                "FROM jobs WHERE status='failed' "
                "ORDER BY updated_at DESC LIMIT 5")
    for jid, typ, why in cur.fetchall():
        print(f"  {jid} | {typ}\n      {why}")

    print("\n--- the two freshest corpses, FULL reason ---")
    cur.execute("SELECT job_id, data->>'halt_reason' FROM jobs "
                "WHERE status='failed' ORDER BY updated_at DESC LIMIT 2")
    for jid, why in cur.fetchall():
        print(f"  {jid}:\n    {why}")

    print("\n--- waiting for YOUR approval right now ---")
    cur.execute("SELECT job_id, type, updated_at FROM jobs "
                "WHERE status='AWAITING_APPROVAL' ORDER BY updated_at")
    for jid, typ, at in cur.fetchall():
        print(f"  {jid} | {typ} | since {at}")
    store._conn.rollback()

    print("\n--- cadence stamps ---")
    stamps = store.get_setting("engine_cadence_last", {}) or {}
    print("  " + (json.dumps(stamps, default=str) if stamps
                  else "never stamped"))

    print("\n--- wires ---")
    try:
        import content_engine_connectors as C
        st = C.status()
        live = sorted(k for k, v in st.items() if v)
        down = sorted(k for k, v in st.items() if not v)
        print(f"  live ({len(live)}): " + ", ".join(live))
        print(f"  waiting for keys ({len(down)}): " + ", ".join(down))
    except Exception as exc:                          # noqa: BLE001
        print("  connector status unreadable: " + repr(exc)[:120])
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
