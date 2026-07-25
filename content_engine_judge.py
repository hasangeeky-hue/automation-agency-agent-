"""
content_engine_judge.py
============================================================================
S1 EVALUATOR + OPTIMIZER — a cheap model scores the work against a written
rubric BEFORE anything irreversible (an email, a paid campaign). Generator +
judge is the pattern behind most shipped AI quality.

Runs on the CHEAP model (Haiku) — pennies. Returns a compact verdict the
dashboard can flag on the approval card:

    {"score": 0-100, "verdict": "pass|revise|block", "issues": [...], "suggestion": ""}

Never raises — a judge failure returns a soft "revise" so it can never block the
pipeline by crashing.
============================================================================
"""
from __future__ import annotations

RUBRICS = {
    "outreach_email": (
        "Judge this cold email as a busy professional who gets 50 pitches a day. "
        "Score on: relevance to THIS recipient (not generic), one clear specific value, "
        "a single obvious call-to-action, a real booking link present, correct language, "
        "and NOT sounding like spam or a scam. Penalise fake urgency, ALL CAPS, walls of text, "
        "and invented claims."),
    "campaign": (
        "Judge this Google Ads campaign as a careful media buyer spending real money. "
        "Score on: tight keyword/theme match to the ICP, budget sanity against the monthly cap, "
        "at least 3 distinct strong headlines per ad group, negative keywords present, "
        "realistic (not invented) CPC and lead estimates, and a clear rationale. "
        "Penalise vague targeting, missing negatives, and fantasy numbers."),
    "reply": (
        "Judge this reply to an inbound customer. Score on: answers only from given facts "
        "(no invented pricing/claims), correct routing to a human for sensitive topics, warm "
        "and concise tone, one clear next step. Penalise pushiness and hallucinated facts."),
    "generic": (
        "Score the quality, correctness and usefulness of this output for its stated goal. "
        "Reward specificity and correctness; penalise vagueness, errors and invented facts."),
}


def judge(kind: str, content, rubric: str = "", model: str = "") -> dict:
    """Score `content` against a rubric. `kind` picks a built-in rubric unless an
    explicit `rubric` string is passed (used by the eval harness for per-case
    rubrics). Always returns a dict; never raises."""
    try:
        from content_engine_providers import build_prompt, call_provider
        import content_engine_orchestrator as orch
    except Exception as e:  # pragma: no cover
        return {"score": 0, "verdict": "revise", "issues": [f"judge unavailable: {e}"],
                "suggestion": "", "cost_usd": 0.0}
    rub = rubric or RUBRICS.get(kind, RUBRICS["generic"])
    mdl = model or (orch.ROUTES.get("judge", {}) or {}).get("engine") or orch.CHEAP_MODEL
    try:
        spec = build_prompt("judge", {"payload": {"kind": kind, "rubric": rub, "item": content},
                                      "brand": {}})
        res = call_provider(mdl, spec)
        data = res.data or {}
        cost = float(getattr(res, "cost_usd", 0.0) or 0.0)
    except Exception as e:
        return {"score": 0, "verdict": "revise", "issues": [f"judge error: {str(e)[:100]}"],
                "suggestion": "", "cost_usd": 0.0}
    try:
        score = int(round(float(data.get("score", 0) or 0)))
    except Exception:
        score = 0
    score = max(0, min(100, score))
    verdict = data.get("verdict") or ("pass" if score >= 75 else "revise" if score >= 50 else "block")
    issues = [str(x) for x in (data.get("issues") or [])][:5]
    return {"score": score, "verdict": verdict, "issues": issues,
            "suggestion": str(data.get("suggestion", ""))[:300], "cost_usd": round(cost, 5)}


def is_weak(quality: dict) -> bool:
    """A campaign/email is 'weak' if the judge said revise/block or scored < 75."""
    if not isinstance(quality, dict):
        return False
    return quality.get("verdict") in ("revise", "block") or int(quality.get("score", 100) or 100) < 75
