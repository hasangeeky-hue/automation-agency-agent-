"""
content_engine_selftest.py
============================================================================
WHOLE-SYSTEM SELF-TEST — run every agent live in one shot and report every
failure at once, instead of discovering bugs one pipeline run at a time.

It drives each LLM skill through the REAL runner (orchestrator.run_llm_skill →
prepare_input → build_prompt → routed call_provider), so it catches the whole
class of bugs we hit live: bad output schemas, mis-routed models (engine='code'),
prompt/format errors, provider errors. Pure-code steps (publisher, lead_sourcing)
have no LLM to test and are skipped. Uses an isolated in-memory store so it never
touches real jobs, and never publishes or sends anything (those are code steps,
not run here).

Costs a few dollars (one call per agent). One command:
    curl -s -X POST "localhost:8000/selftest?key=$KEY" | python3 -m json.tool
============================================================================
"""
from __future__ import annotations

_SKIP = {"publisher", "lead_sourcing", "orchestrator"}  # pure code, no LLM


def _base_payload() -> dict:
    """One rich payload that satisfies every prep mapper's reads + every unmapped
    skill's INPUT fields, so a skill only fails on a REAL bug, not missing input."""
    return {
        "config": {
            "business_goal": "leads", "our_offer": "AI automation that saves clinics 10 hours a week",
            "proof_point": "", "weekly_priorities": "AI intake for clinics", "pieces_this_week": 2,
            "segments_active": ["doctors"], "landing_url": "https://anthropos-automation.com/",
            "ad_goal": "leads", "ad_monthly_budget": 200, "booking_url": "https://anthropos-automation.com/free-audit/",
            "website": "anthropos-automation.com", "sender_name": "Hasan", "sender_company": "Anthropos Automation",
            "icp": {"verticals": ["doctors", "lawyers"], "countries": ["USA", "Germany"],
                    "ideal_industries": ["doctors"], "ideal_size": "$2,000-$10,000", "deal_size": "$2,000-$10,000"},
        },
        "category": "doctor",
        "lead": {"name": "Dr. Sarah Lee", "company": "Lakeside Clinic", "title": "Owner",
                 "country": "USA", "email": "sarah@example.com"},
        "leads": [{"name": "Dr. Sarah Lee", "company": "Lakeside Clinic", "title": "Owner"}],
        "raw_leads": [{"name": "Dr. Sarah Lee", "company": "Lakeside Clinic"}],
        "audit": {}, "competitors": [], "ads": {"goal": "leads", "period": "", "monthly_budget": 200, "campaigns": []},
        "creatives": [],
        # prior-stage results some skills read:
        "site_intelligence": {"content_opportunities": ["AI intake automation"], "summary": "Automation site."},
        "competitor_intel": {"market_gap": {"summary": "gap"}, "differentiation_angles": ["human-first"]},
        "content_strategist": {"pieces": [{"title": "AI intake for clinics", "target_keyword": "clinic automation", "angle": "save time"}]},
        "content_producer": {"title": "AI intake for clinics",
                             "body": "AI automation helps clinics onboard patients faster. It handles the repetitive steps so staff focus on care. Here is how it works in practice for a small practice."},
        "analytics_funnel": {"stages": {}}, "optimizer": {},
        "seo_signals": {"winning_keywords": ["clinic automation"]},
        "media_buyer": {"campaign_name": "Clinics DACH", "objective": "leads", "daily_budget": 10,
                        "monthly_budget": 300, "locations": ["Germany"],
                        "ad_groups": [{"theme": "clinic automation", "keywords": ["clinic automation"],
                                       "headlines": ["Automate intake", "Save 10 hrs", "AI for clinics"],
                                       "descriptions": ["We automate the boring parts.", "Book a free consult."]}],
                        "rationale": "high intent", "human_should_check": ["budget"]},
        # unmapped-skill INPUT fields:
        "kind": "campaign", "rubric": "Is this campaign tight, on-budget, and honest?",
        "item": {"campaign_name": "Clinics DACH", "daily_budget": 10},
        "count": 3, "goal": "leads",
        "icp": {"verticals": ["doctors"], "countries": ["USA"], "deal_size": "$2,000-$10,000"},
        "recent_titles": [],
        "campaign": {"campaign_name": "Clinics DACH", "daily_budget": 10}, "history": [],
        "from": "ceo@acme.com", "subject": "Re: quick idea",
        "message": "Sounds useful, can you lower the budget and tell me the price?",
        "our_offer": "AI automation projects, $2k-$10k", "sender_name": "Hasan", "context": "We scope on a free call.",
    }


def _base_job(skill: str) -> dict:
    return {
        "job_id": f"selftest_{skill}", "type": "content_piece", "client_id": "selftest",
        "brand": {"brand_name": "Anthropos Automation", "offer": "AI automation that saves 10 hours a week",
                  "industry": "Automation", "website": "anthropos-automation.com"},
        "approved": False, "cost_so_far_usd": 0.0, "model_log": [],
        "payload": _base_payload(),
    }


def run_smoke() -> dict:
    """Run every LLM agent once through the real runner; report pass/fail + error."""
    import content_engine_orchestrator as orch
    store = orch.InMemoryJobStore()   # isolated; real jobs untouched
    report = []
    for skill in sorted(orch.ROUTES):
        if skill in _SKIP:
            continue
        route = orch.ROUTES.get(skill, {}) or {}
        # skip anything with no LLM at all (pure code, no narrate)
        if route.get("engine") == "code" and not (route.get("narrate") or route.get("label")):
            continue
        try:
            data, cost = orch.run_llm_skill(_base_job(skill), skill, store)
            report.append({"skill": skill, "ok": True, "cost_usd": round(float(cost or 0), 4)})
        except Exception as e:
            report.append({"skill": skill, "ok": False,
                           "error": f"{type(e).__name__}: {str(e)[:200]}"})
    passed = sum(1 for r in report if r["ok"])
    fails = [r for r in report if not r["ok"]]
    try:
        import content_engine_connectors as C
        conn = C.status()
    except Exception as e:
        conn = {"error": str(e)[:120]}
    return {"summary": f"{passed}/{len(report)} agents OK",
            "passed": passed, "failed": len(fails), "total": len(report),
            "cost_usd": round(sum(r.get("cost_usd", 0) for r in report), 4),
            "failures": fails, "skills": report, "connectors": conn}
