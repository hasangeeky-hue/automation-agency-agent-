"""ONE real content job, through the real pipeline, stopping at your approval.

The 15 JSONDecodeError failures in audit_live.py are HISTORY — dead jobs from
before the token fix. Nothing schedules new work (the scheduler is deliberately
not wired yet), so that count cannot move on its own and the fix cannot prove
itself. This proves it.

    docker compose -f deploy/docker-compose.yml exec api python probe_one_job.py

WHAT IT DOES
  - creates ONE content_piece job
  - advances it until it blocks
  - stops at AWAITING_APPROVAL and never publishes

WHAT IT COSTS
  Real model calls: site_intelligence, competitor_intel, content_strategist,
  content_producer, seo_optimizer, qa_compliance. Roughly $0.10-$0.40 for a
  blog, and your per-job cap stops it dead if it exceeds that. It prints the
  actual cost at the end.

  --dry  runs the identical path with the model stubbed, spending nothing. That
         still exercises prompt-building and the token budgets, so it proves the
         wiring but NOT that a real response fits in the budget.

Nothing here publishes, sends, or posts. The job parks at the human gate.
"""
import sys

DRY = "--dry" in sys.argv


def main() -> int:
    import content_engine_api as API
    import content_engine_orchestrator as orch

    if DRY:
        def stub(job, skill, store):
            if skill == "qa_compliance":
                return ({"verdict": "pass"}, 0.001)
            return ({"ok": True}, 0.001)
        orch._LLM_HOOK = stub
        print("DRY RUN — the model is stubbed, nothing is spent.\n")

    from datetime import datetime, timezone
    jid = "probe_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"creating {jid} ...")
    r = API.api_create_job(
        "content_piece",
        {"brand_name": "Anthropos", "industry": "AI automation"},
        {"config": {"type": "blog", "produce_index": 0}, "audit": {},
         "competitors": []},
        job_id=jid)
    if r.get("status") != "created":
        print("could not create the job:", r)
        return 1

    store = API.get_store()

    # tick() claims from the shared queue and honours the global pause switch,
    # returning None in BOTH cases — so the first version of this probe stopped
    # at 'created' having spent nothing and could not say which it was. Report
    # the pause state, then advance THIS job directly: an isolated single-job
    # test, with the engine left exactly as switched off as it was.
    paused = False
    try:
        paused = bool(store.get_setting("paused", False))
    except Exception:
        pass
    print(f"  engine paused: {paused}"
          + ("  (advancing this one job anyway — the engine stays off)"
             if paused else ""))

    # Print BEFORE each step, not after. The old version printed only on a
    # status CHANGE, so the minutes an LLM call takes looked exactly like a
    # freeze - there was no way to tell working from hung.
    import time
    t0 = time.time()

    def _elapsed():
        return f"{time.time() - t0:6.1f}s"

    seen, last = [], None
    job = store.get(jid)
    for _ in range(40):
        st = job["status"]
        if st != last:
            seen.append(st)
            last = st
        step = orch.flow_for(job).get(st)
        nxt = getattr(step, "skill", None) if step else None
        if nxt:
            print(f"  [{_elapsed()}] {st:<20} -> running {nxt} ...",
                  flush=True)
        if st in ("AWAITING_APPROVAL", "failed", "revision_needed",
                  "halted_budget", "optimized"):
            break
        before = st
        try:
            # ONE step at a time so every transition is visible as it happens
            orch.advance(job, store)
            if job["status"] != before:
                print(f"  [{_elapsed()}] {before:<20} -> {job['status']} "
                      f"(${job.get('cost_so_far_usd', 0):.4f})", flush=True)
        except Exception as e:
            print(f"  !! the step raised: {type(e).__name__}: {str(e)[:200]}")
            break
        if job["status"] == before:
            print(f"  (no further progress from '{before}')")
            break

    job = API.api_get_job(jid)
    st = job["status"]
    payload = job.get("payload") or {}
    cost = job.get("cost_so_far_usd", 0.0)

    print("\n" + "=" * 62)
    print(f"FINAL: {st}   cost ${cost:.4f}")
    print("=" * 62)

    si = payload.get("site_intelligence")
    if si and not (isinstance(si, dict) and si.get("error")):
        n = len(si.get("top_issues", []) or []) if isinstance(si, dict) else 0
        print(f"  site_intelligence CLEARED — {n} issues, "
              f"health {si.get('health_score', '?') if isinstance(si, dict) else '?'}")
        print("  ^ this is the step that killed all 15 previous content jobs.")
    else:
        print("  site_intelligence did NOT produce output.")

    if st == "AWAITING_APPROVAL":
        piece = payload.get("content_producer", {}) or {}
        print(f"\n  It is waiting for YOU. Title: "
              f"{str(piece.get('title', '(none)'))[:60]}")
        print("  Nothing was published. Approve or decline it in the dashboard.")
        print("\n  THE FIX HOLDS." if not DRY else
              "\n  Wiring holds. Re-run WITHOUT --dry to prove a real response "
              "fits the token budget.")
        return 0

    reason = job.get("halt_reason") or job.get("qa_verdict") or ""
    print(f"\n  It stopped at '{st}'.")
    if st == "created" and not reason:
        print("  Nothing ran and nothing raised. That is a WIRING problem, not "
              "a model problem — check ANTHROPIC_API_KEY on the Connect board.")
    if reason:
        print(f"  Reason: {str(reason)[:400]}")
    if "Unterminated" in str(reason) or "JSONDecode" in str(reason):
        print("\n  !! STILL TRUNCATING. The budget for the step above is still "
              "too small — raise it in content_engine_providers._MAX_TOKENS.")
    elif "ran out of room" in str(reason):
        print("\n  Truncation, but now NAMED — the message above says which "
              "skill and which budget to change.")
    print(f"\n  Steps reached: {' -> '.join(seen)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
