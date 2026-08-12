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

    print("=" * 70)
    print(f"REVIVED {len(revived)} job(s); the worker picks them up "
          "within seconds.")
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
