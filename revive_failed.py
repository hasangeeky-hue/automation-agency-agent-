# -*- coding: utf-8 -*-
"""Revive the queue after the wallet refilled.

Run AFTER topping up Anthropic credits, from the repo root on the VPS:
  docker compose -f deploy/docker-compose.yml exec -T api python - \
      < revive_failed.py

Every 'failed' and 'halted_budget' job re-enters at the step AFTER its
last completed one (orchestrator.revive), so work already paid for is
never re-bought. revision_needed pieces are NOT touched: those are QA
verdicts waiting for you. Idempotent: a second run finds nothing dead.
"""
from __future__ import annotations


def main() -> int:
    from content_engine_api import get_store
    import content_engine_orchestrator as orch

    store = get_store()
    revived, refused = [], []
    for status in ("failed", "halted_budget"):
        for job in store.list_jobs(status=status):
            r = orch.revive(job)
            if r.get("ok"):
                store.save(job)
                revived.append((r["job_id"], r["resumed_at"]))
            else:
                refused.append(str(r.get("message"))[:100])

    # A REVIVAL THAT REPORTS SUCCESS MUST PROVE IT. The first run said
    # 60 and the next read showed the same 60 dead - a claim nobody had
    # checked. Now the script re-reads one revived job on a FRESH
    # connection and prints what the database actually holds.
    proof = ""
    if revived:
        jid = revived[0][0]
        try:
            import os

            import psycopg
            dsn = getattr(store, "_dsn", None) or os.environ["DATABASE_URL"]
            with psycopg.connect(dsn) as c2:
                with c2.cursor() as c2c:
                    c2c.execute("SELECT status, updated_at FROM jobs "
                                "WHERE job_id = %s", (jid,))
                    row = c2c.fetchone()
            if row and str(row[0]) not in ("failed", "halted_budget"):
                proof = (f"PERSISTED: {jid} now reads '{row[0]}' in the "
                         f"database (updated {row[1]}).")
            else:
                proof = (f"NOT PERSISTED: {jid} still reads "
                         f"'{row[0] if row else 'missing'}'. The revival "
                         "did not reach the database - do not trust the "
                         "count above.")
        except Exception as exc:                      # noqa: BLE001
            proof = "could not verify: " + repr(exc)[:120]

    print("=" * 70)
    print(f"REVIVED {len(revived)} job(s); the worker picks them up "
          "within seconds.")
    if proof:
        print(proof)
    for jid, at in revived[:15]:
        print(f"  {jid} resumes at '{at}'")
    if len(revived) > 15:
        print(f"  ... and {len(revived) - 15} more")
    if refused:
        print(f"refused {len(refused)} (not actually dead):")
        for m in refused[:5]:
            print("  " + m)
    print("watch: docker compose -f deploy/docker-compose.yml "
          "logs -f worker")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
