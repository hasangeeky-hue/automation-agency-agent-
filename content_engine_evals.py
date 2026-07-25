"""
content_engine_evals.py
============================================================================
S5 INSTRUMENTS — "an agent without evals is a rumor."

A small, real eval set: fixed tasks with a known-good rubric. On demand (a
button on the dashboard, or a cron) we run each task through its skill and let
the CHEAP judge grade the output. That turns "it worked when I watched" into a
number you can trust and trend.

Also computes the three drift NEEDLES the dashboard shows:
  - task success  (last eval pass-rate)
  - human takeover (share of jobs aborted / rejected / edited)
  - cost per task  (avg $ spent per job)

run_evals() costs a few cents (mostly Haiku). It never raises.
============================================================================
"""
from __future__ import annotations

# --- the eval set. Each case: a skill, a literal input shaped like the skill's
#     prompt expects, and a rubric the judge grades against. Extend freely.
EVAL_CASES = [
    # ---- outreach copy (cheap model) ----
    {"name": "Outreach · US doctor", "skill": "outreach_copy", "threshold": 70,
     "input": {"category": "doctor", "our_offer": "AI systems that cut clinic admin by 10 hrs/week",
               "proof_point": "", "sender_name": "Hasan", "sender_company": "Anthropos Automation",
               "website": "anthropos-automation.com", "booking_url": "https://anthropos-automation.com/free-audit/",
               "unsubscribe_token": "{{unsubscribe_token}}",
               "lead": {"name": "Dr. Sarah Lee", "company": "Lakeside Family Clinic", "title": "Owner",
                        "country": "USA"}},
     "rubric": "Cold email to a US clinic owner. Must be specific to healthcare, one clear CTA to book, "
               "friendly not spammy, no invented results."},
    {"name": "Outreach · DE tax consultant (German)", "skill": "outreach_copy", "threshold": 70,
     "input": {"category": "tax_consultant", "our_offer": "Automatisierung für Steuerkanzleien",
               "proof_point": "", "sender_name": "Hasan", "sender_company": "Anthropos Automation",
               "website": "anthropos-automation.com", "booking_url": "https://anthropos-automation.com/free-audit/",
               "unsubscribe_token": "{{unsubscribe_token}}",
               "lead": {"name": "Herr Müller", "company": "Müller Steuerberatung", "title": "Partner",
                        "country": "Germany"}},
     "rubric": "Cold email to a German tax consultant. MUST be written in German, specific to their work, "
               "one clear CTA, professional, no fake claims."},
    {"name": "Outreach · UK Shopify store", "skill": "outreach_copy", "threshold": 70,
     "input": {"category": "shopify", "our_offer": "automation that recovers abandoned carts + support",
               "proof_point": "", "sender_name": "Hasan", "sender_company": "Anthropos Automation",
               "website": "anthropos-automation.com", "booking_url": "https://anthropos-automation.com/free-audit/",
               "unsubscribe_token": "{{unsubscribe_token}}",
               "lead": {"name": "Jamie", "company": "Northgoods", "title": "Founder", "country": "UK"}},
     "rubric": "Cold email to a UK Shopify founder. Specific to e-commerce, one CTA, concise, not scammy."},
    # ---- media buyer (frontier — judgment) ----
    {"name": "Media · doctors DACH €200/mo", "skill": "media_buyer", "threshold": 65,
     "input": {"offer": "AI automation that saves clinics 10 hrs/week", "goal": "leads",
               "monthly_budget": 200, "landing_url": "https://anthropos-automation.com/",
               "icp": {"verticals": ["doctors", "clinics"], "countries": ["Germany", "Switzerland"],
                       "deal_size": "$2,000-$10,000"}, "creatives": [], "past_learnings": {}},
     "rubric": "Google Ads campaign for clinics in DE/CH on a €200/mo budget. Must: match keywords to "
               "healthcare, keep budget within cap, give 3+ distinct headlines, include negative keywords, "
               "give a rationale, and NOT invent performance numbers."},
    {"name": "Media · lawyers USA", "skill": "media_buyer", "threshold": 65,
     "input": {"offer": "automation for small law firms", "goal": "leads", "monthly_budget": 300,
               "landing_url": "https://anthropos-automation.com/", "creatives": [], "past_learnings": {},
               "icp": {"verticals": ["lawyers", "law firms"], "countries": ["USA"], "deal_size": "$3,000-$10,000"}},
     "rubric": "Google Ads campaign for US law firms. Tight targeting, budget within cap, distinct headlines, "
               "negative keywords, honest estimates, clear rationale."},
    # ---- reply responder (cheap) ----
    {"name": "Reply · interested prospect", "skill": "reply_responder", "threshold": 70,
     "input": {"from": "ceo@acme.com", "subject": "Re: quick idea", "message": "Sounds interesting, how much?",
               "our_offer": "AI automation projects, $2k-$10k depending on scope", "sender_name": "Hasan",
               "context": "We scope on a free call first."},
     "rubric": "Reply to an interested prospect asking price. Should answer from given facts only, be warm "
               "and concise, and offer to book a call. Must NOT invent a fixed price beyond what's given."},
    {"name": "Reply · complaint routes to human", "skill": "reply_responder", "threshold": 70,
     "input": {"from": "angry@acme.com", "subject": "Re: your email", "message": "This is spam, remove me now.",
               "our_offer": "AI automation", "sender_name": "Hasan", "context": ""},
     "rubric": "Reply to an angry unsubscribe/complaint. Must confirm removal politely, NOT pitch again, and "
               "(for complaints) flag needs_human. No defensiveness."},
]


def run_evals(cases=None) -> dict:
    """Run every eval case through its skill and grade with the judge.
    Returns {total, passed, score, cost_usd, cases:[...]}. Never raises."""
    try:
        import content_engine_orchestrator as orch
        from content_engine_providers import build_prompt, call_provider
        from content_engine_judge import judge
    except Exception as e:  # pragma: no cover
        return {"total": 0, "passed": 0, "score": 0, "cost_usd": 0.0, "error": str(e)[:120], "cases": []}
    cases = cases or EVAL_CASES
    out, passed, cost = [], 0, 0.0
    for c in cases:
        route = orch.ROUTES.get(c["skill"], {}) or {}
        mdl = route.get("engine")
        if mdl in (None, "code"):
            mdl = route.get("narrate") or route.get("label") or orch.CHEAP_MODEL
        try:
            spec = build_prompt(c["skill"], {"payload": c["input"], "brand": c.get("brand", {})})
            res = call_provider(mdl, spec)
            output = res.data or {}
            cost += float(getattr(res, "cost_usd", 0.0) or 0.0)
        except Exception as e:
            out.append({"name": c["name"], "skill": c["skill"], "score": 0, "pass": False,
                        "issues": [f"skill error: {str(e)[:80]}"]})
            continue
        v = judge(c["skill"], output, rubric=c["rubric"])
        cost += float(v.get("cost_usd", 0.0) or 0.0)
        ok = int(v.get("score", 0)) >= int(c.get("threshold", 70))
        passed += 1 if ok else 0
        out.append({"name": c["name"], "skill": c["skill"], "score": int(v.get("score", 0)),
                    "pass": ok, "issues": v.get("issues", [])})
    total = len(cases)
    return {"total": total, "passed": passed,
            "score": round(100 * passed / total) if total else 0,
            "cost_usd": round(cost, 4), "cases": out}


def needles(store, last_eval=None) -> dict:
    """The three drift needles. Reads jobs from the store; task-success comes
    from the last eval run (or None if never run)."""
    jobs = []
    try:
        if hasattr(store, "list_jobs"):
            jobs = store.list_jobs() or []
    except Exception:
        jobs = []
    n = len(jobs)
    takeovers = sum(1 for j in jobs
                    if j.get("status") in ("aborted", "rejected") or j.get("edited")
                    or (j.get("payload", {}) or {}).get("edited"))
    costs = [float(j.get("cost_so_far_usd", 0) or 0) for j in jobs]
    return {
        "task_success": (last_eval or {}).get("score") if last_eval else None,
        "takeover_rate": round(100 * takeovers / n) if n else 0,
        "cost_per_task": round(sum(costs) / n, 4) if n else 0.0,
        "jobs": n,
        "eval_at": (last_eval or {}).get("at"),
    }
