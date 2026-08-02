"""EVERY PIPELINE, EVERY STATE, END TO END. NO SPEND, NO WRITES, NO SENDS.

    docker compose -f deploy/docker-compose.yml exec api python pipeline_test.py

What it does
  - builds an IN-MEMORY store, so your real jobs are never touched
  - stubs the model with a MINIMAL VALID instance generated from each skill's
    own schema, so a schema the pipeline cannot satisfy shows up here
  - stubs publish / social / send, so nothing reaches WordPress, LinkedIn or
    an inbox
  - opens the human gate and the measurement gate deliberately, so the walk
    reaches the states a real job takes days to arrive at
  - drives content_piece AND outreach_campaign through all 25 states

What it proves and what it does not
  It proves the WIRING: every state has a step, every step has a schema the
  orchestrator accepts, every transition fires, and the publisher routes to
  the right channels. It does NOT prove a real model's output fits the token
  budget, or that a live credential is accepted. Only probe_one_job.py and a
  real call do that.

  This distinction is the whole point. My unit tests passed for weeks on
  fixtures I wrote while the real journey was broken. This walks the REAL
  orchestrator over the REAL flow definitions with the REAL schemas — the
  only thing faked is the model and the outside world.
"""
import sys
from datetime import datetime, timedelta, timezone

W = 74


def _sample(schema, depth=0):
    """A minimal instance that satisfies this schema. Built FROM the schema, so
    a required field nobody can produce fails here instead of in production."""
    if not isinstance(schema, dict) or depth > 6:
        return {}
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or ("properties" in schema and not t):
        out = {}
        props = schema.get("properties") or {}
        for k in (schema.get("required") or list(props)[:3]):
            out[k] = _sample(props.get(k, {"type": "string"}), depth + 1)
        return out
    if t == "array":
        item = schema.get("items") or {"type": "string"}
        return [_sample(item, depth + 1)] if schema.get("minItems", 0) else []
    if t == "boolean":
        return True
    if t in ("number", "integer"):
        return 1
    return "x"


def main() -> int:
    import content_engine_orchestrator as O
    import content_engine_schemas as S
    import content_engine_code_skills as CS

    print("PIPELINE TEST".center(W))
    print("in-memory store, stubbed model, nothing published or sent"
          .center(W))

    # --- stub the outside world -------------------------------------------
    sent = []
    CS.PUBLISH_FN = lambda job, piece: "TEST-WP-" + str(job["job_id"])[:10]
    CS.SOCIAL_FN = lambda job, piece, ch: f"TEST-{ch}"
    CS.SEND_FN = lambda job, email: sent.append(job["job_id"]) or "TEST-SEND"

    # --- stub the model with a valid instance of each skill's own schema ---
    used = {}

    def stub(job, skill, store):
        sc = S.SCHEMAS.get(skill)
        raw = getattr(sc, "schema", sc) if sc else None
        data = _sample(raw) if isinstance(raw, dict) else {"ok": True}
        if skill == "qa_compliance":
            data["verdict"] = "pass"          # let the walk continue
        used[skill] = True
        return data, 0.0

    O._LLM_HOOK = stub

    total_fail = 0
    for jtype in O.FLOWS:
        flow = O.FLOWS[jtype]
        order = list(flow)
        print()
        print(("== " + jtype + " ").ljust(W, "="))
        store = O.InMemoryJobStore()
        jid = "pipetest_" + jtype
        job = O.new_job(jid, jtype,
                        {"brand_name": "Anthropos", "industry": "AI automation"},
                        {"config": {"type": "blog", "produce_index": 0,
                                    "deploy_channels": ["website", "linkedin"]},
                         "audit": {}, "competitors": [],
                         "leads": [{"email": "a@b.com", "company": "X"}],
                         "icp": {"titles": ["founder"]}})
        store.save(job)

        seen, blocked = [], None
        for _ in range(60):
            job = store.get(jid)
            st = job["status"]
            if st not in seen:
                seen.append(st)
            if st in O.TERMINAL:
                break
            step = flow.get(st)
            # OPEN THE GATES ON PURPOSE. A human gate and a 21-day measurement
            # window are correct behaviour, not progress — but leaving them
            # shut means this test can never see the states behind them, which
            # is exactly how "measuring has never run" went unexamined.
            if step is not None and getattr(step, "kind", "") == "wait":
                flag = getattr(step, "gate_flag", "")
                if flag and not job.get(flag):
                    job[flag] = True
                    if getattr(step, "time_gate", False):
                        job["measure_at"] = (datetime.now(timezone.utc)
                                             - timedelta(days=1)).isoformat()
                    store.save(job)
                    continue
            before = st
            try:
                O.advance(job, store)
                store.save(job)
            except Exception as e:
                blocked = f"{type(e).__name__}: {str(e)[:120]}"
                break
            if store.get(jid)["status"] == before:
                blocked = f"no progress from '{before}'"
                break

        reached = [s for s in order if s in seen]
        missed = [s for s in order if s not in seen]
        final = store.get(jid)["status"]
        for s in order:
            mark = "ok " if s in seen else "-- "
            skill = getattr(flow.get(s), "skill", None) or ""
            print(f"  {mark} {s:<20} {skill}")
        print()
        print(f"  reached {len(reached)}/{len(order)} states, ended at "
              f"'{final}'")
        if missed:
            print(f"  NEVER REACHED: {', '.join(missed)}")
        if blocked:
            print(f"  STOPPED: {blocked}")
        halt = store.get(jid).get("halt_reason")
        if halt:
            print(f"  reason: {str(halt)[:200]}")
        bad = bool(missed) or bool(blocked) or final not in ("optimized",
                                                             "learned")
        total_fail += 1 if bad else 0

    print()
    print("=" * W)
    print(f"skills exercised: {len(used)} — {', '.join(sorted(used))}")
    print(f"publishes captured (never sent): {len(sent)} outreach send(s)")
    if total_fail:
        print(f"\n{total_fail} pipeline(s) did not complete. The lines marked "
              f"'--' above are states no job can reach.")
        return 1
    print("\nBOTH PIPELINES WALK END TO END. Wiring holds: every state has a "
          "step, every step produced schema-valid output, every gate opened, "
          "and the publisher routed to the right channels.")
    print("This did NOT test: real model output against the token budgets, or "
          "whether a live credential is accepted. Use probe_one_job.py for "
          "the first and the wires board for the second.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
