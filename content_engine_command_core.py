# -*- coding: utf-8 -*-
"""COMMAND COCKPIT: the engine.

Spec sections 0-2, 13, 17-27, 29-32, 36-41, 66-68, 76-77, 84-93,
96-100, 103-107.

WHAT THE COCKPIT IS (section 1)
-------------------------------
Not another analytics dashboard: COMMAND, DIAGNOSIS, DECISION, ACTION,
VERIFICATION. Every visible issue must end in one of IGNORE, MONITOR,
ANALYZE, DECIDE, FIX, ROUTE or ESCALATE (section 103). No dead-end
cards, and no duplicate of any domain OS: detail lives behind a deep
link.

THE BOUNDARY THAT MAKES IT SAFE (sections 24, 84, 106)
------------------------------------------------------
The cockpit NEVER calls a provider. Every action goes through the
Action Router to the OS that owns execution, and the Commander may
read, correlate, prioritise and plan but may not touch a database, an
ad platform, a website, a secret or a firewall. It coordinates the
systems; it does not replace them.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _s(x) -> str:
    return "" if x is None else str(x)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _id(*parts) -> str:
    return hashlib.sha1("|".join(_s(p) for p in parts)
                        .encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# 13. POLARITY. Higher is never automatically good.
# ===========================================================================
POLARITY = {"revenue": "GOOD_UP", "contribution": "GOOD_UP",
            "customers": "GOOD_UP", "pipeline": "GOOD_UP",
            "leads": "GOOD_UP", "conversions": "GOOD_UP",
            "cac": "BAD_UP", "cpa": "BAD_UP", "refunds": "BAD_UP",
            "churn": "BAD_UP", "error_rate": "BAD_UP",
            "api_cost": "BAD_UP", "latency": "BAD_UP",
            "waste": "BAD_UP",
            "spend": "NEUTRAL", "agent_cost": "DEPENDS"}


def judge_change(metric, pct) -> Dict[str, Any]:
    """Is this movement good, bad, neutral or undecidable?

    A metric with no registered polarity is UNDECIDED and says so: a
    cockpit that colours unknown metrics green is guessing on the
    operator's behalf.
    """
    m = _s(metric).lower()
    p = _f(pct)
    pol = POLARITY.get(m)
    if p is None:
        return {"verdict": "UNDECIDED", "why": "no change measured"}
    if pol is None:
        return {"verdict": "UNDECIDED",
                "why": ("'" + m + "' has no registered polarity, so this "
                        "movement is shown without a colour rather than "
                        "guessed at")}
    if pol == "NEUTRAL":
        return {"verdict": "NEUTRAL", "why": m + " up or down is not "
                "good or bad by itself"}
    if pol == "DEPENDS":
        return {"verdict": "DEPENDS",
                "why": (m + " rising is fine if the value it produces "
                        "rises faster; that needs the economics screen, "
                        "not a colour")}
    good_up = pol == "GOOD_UP"
    good = (p > 0) == good_up
    return {"verdict": "GOOD" if good else "BAD",
            "why": (m + (" rose " if p > 0 else " fell ")
                    + _s(abs(round(p, 1))) + "%, which is "
                    + ("good" if good else "bad") + " for this metric")}


# ===========================================================================
# 17-18. WHAT CHANGED
# ===========================================================================
def change(metric, *, before, after, source, cause_status="UNKNOWN",
           evidence=()) -> Dict[str, Any]:
    """One change card. Refuses a change without its source.

    Section 17: the operator must not inspect charts by hand, so the
    feed does the arithmetic and names where each number came from.
    """
    b, a = _f(before), _f(after)
    if b is None or a is None:
        return {"ok": False,
                "why": "a change needs both sides of the comparison"}
    if not _s(source):
        return {"ok": False,
                "why": "a change with no source cannot be checked"}
    pct = ((a - b) / abs(b) * 100) if b else None
    j = judge_change(metric, pct)
    return {"ok": True, "metric": _s(metric), "before": b, "after": a,
            "pct": (round(pct, 1) if pct is not None else None),
            "verdict": j["verdict"], "verdict_why": j["why"],
            "source": _s(source),
            "cause_status": _s(cause_status).upper() or "UNKNOWN",
            "evidence": [_s(x) for x in _l(evidence)],
            "importance": abs(pct or 0)}


def change_feed(changes, *, limit=8) -> List[Dict[str, Any]]:
    """The biggest movements first, capped. Thirty rows is a report."""
    rows = [c for c in (_d(x) for x in _l(changes)) if c.get("ok")]
    return sorted(rows, key=lambda c: -(c.get("importance") or 0))[:limit]


# ===========================================================================
# 20-21. DECISIONS
# ===========================================================================
#: Section 21. Every field, or DECISION_INCOMPLETE. A decision missing
#: its measurement plan is a hope with a button on it.
DECISION_FIELDS = ("what", "why", "evidence", "business_impact",
                   "system_impact", "expected_cost", "expected_value",
                   "confidence", "risk", "target_system", "action",
                   "measurement_plan")

DECISION_TYPES = ("BUSINESS_OPPORTUNITY", "BUSINESS_RISK", "MEDIA_ACTION",
                  "CONTENT_ACTION", "SEO_ACTION", "SYSTEM_FIX",
                  "COST_ACTION")


def decision(**kw) -> Dict[str, Any]:
    d = {k: kw.get(k) for k in DECISION_FIELDS}
    d["type"] = (_s(kw.get("type")).upper()
                 if _s(kw.get("type")).upper() in DECISION_TYPES
                 else "BUSINESS_RISK")
    missing = [k for k in DECISION_FIELDS if kw.get(k) in (None, "", [])]
    if missing:
        return {"ok": False, "state": "DECISION_INCOMPLETE",
                "missing": missing,
                "why": ("a decision missing " + ", ".join(missing)
                        + " cannot be approved. Section 21: every card "
                        "carries its evidence, its cost and how the "
                        "result will be measured, or it is not a "
                        "decision.")}
    d.update({"ok": True, "state": "READY",
              "id": _id(d["what"], d["target_system"]),
              "urgency": _f(kw.get("urgency"), 0.5),
              "effort": _f(kw.get("effort"), 0.5)})
    return d


def rank_decisions(decisions) -> Dict[str, Any]:
    """Section 20: impact, urgency, risk, confidence, cost and effort.
    NEVER severity alone: a loud small problem must not outrank a quiet
    expensive one."""
    rows = [d for d in (_d(x) for x in _l(decisions)) if d.get("ok")]
    dropped = [d for d in (_d(x) for x in _l(decisions))
               if not d.get("ok")]
    scored = []
    for d in rows:
        val = _f(_d(d.get("expected_value")).get("mid")) \
            if isinstance(d.get("expected_value"), dict) \
            else _f(d.get("expected_value"), 0)
        cost = _f(_d(d.get("expected_cost")).get("mid")) \
            if isinstance(d.get("expected_cost"), dict) \
            else _f(d.get("expected_cost"), 0)
        net = (val or 0) - (cost or 0)
        conf = _f(d.get("confidence"), 0.5) or 0.5
        urg = _f(d.get("urgency"), 0.5) or 0.5
        risk_pen = {"LOW": 0.0, "MEDIUM": 0.15,
                    "HIGH": 0.35}.get(_s(d.get("risk")).upper(), 0.15)
        eff_pen = (_f(d.get("effort"), 0.5) or 0.5) * 0.1
        score = net * conf * (0.6 + 0.4 * urg) * (1 - risk_pen) \
            - eff_pen * abs(net)
        scored.append((round(score, 2), d))
    scored.sort(key=lambda x: -x[0])
    return {"ranked": [dict(d, score=s) for s, d in scored],
            "incomplete": len(dropped),
            "why": ("ranked by expected net value weighted by "
                    "confidence, urgency, risk and effort. "
                    + (str(len(dropped)) + " DECISION_INCOMPLETE "
                       "card(s) are not ranked: an unmeasurable "
                       "decision cannot compete with a measurable one."
                       if dropped else "every candidate was complete."))}


# ===========================================================================
# 24, 84, 96. THE ACTION ROUTER AND THE FENCE
# ===========================================================================
#: Section 24. Action class -> the ONE OS that executes it. The cockpit
#: holds no provider client and never will.
ROUTES = {
    "CREATE_CONTENT": "CONTENT_FACTORY",
    "CREATE_VARIANTS": "CONTENT_FACTORY",
    "REDUCE_CAMPAIGN_BUDGET": "MEDIA_BUYING_OS",
    "INCREASE_CAMPAIGN_BUDGET": "MEDIA_BUYING_OS",
    "LAUNCH_CREATIVE": "MEDIA_BUYING_OS",
    "OPTIMIZE_PAGE": "SEO_OS",
    "PUBLISH_ARTICLE": "SEO_OS",
    "SEND_REENGAGEMENT": "EMAIL_OS",
    "CREATE_FOLLOWUP_TASK": "CRM_OS",
    "RESTART_WORKER": "SYSTEM_CONTROL_PLANE",
    "SWITCH_FALLBACK_TOOL": "SYSTEM_CONTROL_PLANE",
    "RETRY_WORKFLOW": "SYSTEM_CONTROL_PLANE",
    "RECONNECT_API": "SYSTEM_CONTROL_PLANE",
}

#: Section 84. What the Commander may never do directly, whoever asks.
COMMANDER_FORBIDDEN = ("change_production_database", "call_ad_platform",
                       "publish_website", "rotate_secrets",
                       "restart_database", "delete_data",
                       "change_firewall")


def route(action, *, approved_by="") -> Dict[str, Any]:
    """Send one action to the OS that owns it. Refuses without a human.

    Section 106: Commander -> Router -> Domain OS -> execution. An
    unknown action is refused rather than guessed into a system, and an
    unapproved one never leaves.
    """
    a = _s(action).upper()
    if a.lower() in COMMANDER_FORBIDDEN:
        return {"ok": False, "state": "FORBIDDEN",
                "why": ("'" + a.lower() + "' is forbidden to the "
                        "Commander outright. It is not routable with "
                        "any approval; a human does it in the owning "
                        "system.")}
    target = ROUTES.get(a)
    if target is None:
        return {"ok": False, "state": "UNROUTABLE",
                "why": ("'" + a + "' maps to no owning OS. It is not "
                        "guessed into one: a misrouted action executes "
                        "in the wrong system with the wrong "
                        "guardrails.")}
    if not _s(approved_by).strip():
        return {"ok": False, "state": "NEEDS_APPROVAL", "target": target,
                "why": ("routing is the moment an action becomes real, "
                        "so it carries the approver's name or it does "
                        "not leave the cockpit")}
    return {"ok": True, "state": "ROUTED", "action": a, "target": target,
            "approved_by": _s(approved_by),
            "why": a + " routed to " + target}


# ===========================================================================
# 25-27, 97, 105. QUICK FIXES
# ===========================================================================
QUICK_FIX_TYPES = ("RETRY_WORKFLOW", "RESTART_STATELESS_WORKER",
                   "RECONNECT_API", "RETRY_SYNC", "SWITCH_FALLBACK_TOOL",
                   "REQUEUE_JOB", "RESUME_QUEUE")

FIX_RISK = ("SAFE", "APPROVAL_REQUIRED", "HIGH_RISK")

#: Section 105. A fix without these is a mysterious [Fix] button.
FIX_FIELDS = ("current_state", "proposed_state", "affected", "risk",
              "downtime", "cost", "rollback", "verification")


def quick_fix(ftype, **kw) -> Dict[str, Any]:
    t = _s(ftype).upper()
    if t not in QUICK_FIX_TYPES:
        return {"ok": False,
                "why": ("'" + t + "' is not an MVP quick fix. "
                        "Destructive infrastructure actions are not "
                        "quick fixes at all.")}
    missing = [k for k in FIX_FIELDS if kw.get(k) in (None, "")]
    if missing:
        return {"ok": False, "state": "INCOMPLETE", "missing": missing,
                "why": ("a fix missing " + ", ".join(missing) + " is a "
                        "mysterious [Fix] button, which section 105 "
                        "forbids")}
    risk = _s(kw.get("risk")).upper()
    return {"ok": True, "type": t,
            "risk": risk if risk in FIX_RISK else "APPROVAL_REQUIRED",
            **{k: kw.get(k) for k in FIX_FIELDS if k != "risk"},
            "id": _id(t, kw.get("current_state")),
            "why": (t + " is " + (risk if risk in FIX_RISK
                                  else "APPROVAL_REQUIRED")
                    + ", with rollback and verification stated")}


# ===========================================================================
# 66-68. EXECUTION AND VERIFICATION
# ===========================================================================
#: Section 66. A decision does not vanish at approval; it walks this
#: chain visibly until the loop closes.
EXEC_CHAIN = ("APPROVED", "ROUTED", "EXECUTING", "EXECUTED", "VERIFYING",
              "OBSERVING", "RESULT")


def advance_execution(current, target) -> Dict[str, Any]:
    c, t = _s(current).upper(), _s(target).upper()
    if c not in EXEC_CHAIN or t not in EXEC_CHAIN:
        return {"ok": False, "why": "not an execution state"}
    ci, ti = EXEC_CHAIN.index(c), EXEC_CHAIN.index(t)
    if ti != ci + 1:
        return {"ok": False,
                "why": ("execution moves one visible step at a time; "
                        + c + " to " + t + " skips "
                        + str(ti - ci - 1) + " step(s), and a skipped "
                        "step is where a failure hides")}
    return {"ok": True, "state": t, "why": c + " to " + t}


def verify_machine_fix(*, service_recovered, dependency_healthy,
                       workflow_works) -> Dict[str, Any]:
    """Section 68: SUCCESS IS NOT AN API 200. All three, or not done."""
    parts = {"service recovered": bool(service_recovered),
             "dependency healthy": bool(dependency_healthy),
             "affected workflow works": bool(workflow_works)}
    bad = [k for k, v in parts.items() if not v]
    return {"success": not bad, "parts": parts,
            "why": ("all three conditions hold" if not bad else
                    "the call may have returned 200, but "
                    + " and ".join(bad) + " is not true, so this is "
                    "not recovered")}


def verify_business_action(*, metric, before, after, observed_days,
                           min_days=7) -> Dict[str, Any]:
    """Business success needs the metric to move AFTER enough
    observation. Three days of a fourteen-day window is weather."""
    od = _f(observed_days, 0) or 0
    if od < min_days:
        return {"success": None, "state": "STILL_OBSERVING",
                "why": (str(int(od)) + " day(s) observed against a "
                        "minimum " + str(min_days) + ". Judging now "
                        "measures the weather, not the action.")}
    b, a = _f(before), _f(after)
    if b is None or a is None:
        return {"success": None, "state": "UNMEASURED",
                "why": "the target metric was not measured on one side"}
    j = judge_change(metric, (a - b) / abs(b) * 100 if b else None)
    return {"success": j["verdict"] == "GOOD", "state": "MEASURED",
            "verdict": j["verdict"], "why": j["why"]}


# ===========================================================================
# 29-32. LOOPS AND INITIATIVES
# ===========================================================================
INITIATIVE_STATES = ("ON_TRACK", "AT_RISK", "OFF_TRACK", "WAITING",
                     "COMPLETED", "FAILED")


def initiative_health(*, target_metric, target_value, current_value,
                      direction="BELOW", actions_done=0,
                      actions_total=0, observing=False) -> Dict[str, Any]:
    """Section 32: measured on the TARGET OUTCOME, never on actions done.

    Every action executed with the metric unmoved is not ON_TRACK; it is
    the machinery working and the business not responding, which is the
    single most important thing an initiative card can say.
    """
    t, c = _f(target_value), _f(current_value)
    if t is None or c is None:
        return {"state": "WAITING",
                "why": ("the target metric is not yet measured; actions "
                        + _s(int(actions_done)) + "/"
                        + _s(int(actions_total)) + " done, which is "
                        "progress of the machinery, not of the outcome")}
    met = (c <= t) if _s(direction).upper() == "BELOW" else (c >= t)
    if met:
        return {"state": "COMPLETED" if not observing else "ON_TRACK",
                "why": (_s(target_metric) + " is " + _s(c)
                        + " against a target of " + _s(t))}
    gap = abs(c - t) / abs(t) if t else None
    if observing:
        st = "AT_RISK" if gap and gap > 0.10 else "ON_TRACK"
    else:
        st = "OFF_TRACK"
    return {"state": st,
            "why": (_s(target_metric) + " is " + _s(c) + " against a "
                    "target of " + _s(t) + " ("
                    + _s(round((gap or 0) * 100, 1)) + "% away). "
                    + _s(int(actions_done)) + "/"
                    + _s(int(actions_total)) + " action(s) executed, "
                    "and executed actions do not count as progress: "
                    "the metric does.")}


# ===========================================================================
# 40-41, 76-77. ROOT CAUSE AND BUSINESS IMPACT
# ===========================================================================
def root_chain(links) -> Dict[str, Any]:
    """Section 40: BUSINESS EFFECT -> PROCESS CAUSE -> SYSTEM CAUSE.

    Each link carries its layer, so the chain reads as the business
    symptom, the process that starved it, and the system that broke.
    """
    rows = [_d(x) for x in _l(links)]
    if len(rows) < 2:
        return {"ok": False,
                "why": ("a chain of one is a symptom, not a cause. Two "
                        "links minimum, ending at a system cause.")}
    return {"ok": True, "chain": rows,
            "root": rows[-1],
            "why": " because ".join(_s(r.get("text")) for r in rows)}


IMPACT_CONFIDENCE = ("DIRECT", "HIGH", "MEDIUM", "LOW", "UNKNOWN")


def business_impact(*, description, amount=None, confidence="UNKNOWN"
                    ) -> Dict[str, Any]:
    """Section 77: never invent a fake exact euro impact.

    An amount with UNKNOWN confidence is refused: the description stays,
    the number does not, because a made-up figure gets quoted in the
    decision that follows it.
    """
    conf = _s(confidence).upper()
    if conf not in IMPACT_CONFIDENCE:
        conf = "UNKNOWN"
    a = _f(amount)
    if a is not None and conf == "UNKNOWN":
        return {"description": _s(description), "amount": None,
                "confidence": "UNKNOWN",
                "why": ("an amount was offered with UNKNOWN confidence "
                        "and is dropped: the impact is described, not "
                        "priced, until something ties a number to it")}
    return {"description": _s(description), "amount": a,
            "confidence": conf,
            "why": ("estimated at " + _s(a) + " with " + conf
                    + " confidence" if a is not None else
                    "described without a figure, which is honest when "
                    "no figure exists")}


# ===========================================================================
# 92-93. INCIDENT AGGREGATION AND NOTIFICATION POLICY
# ===========================================================================
def aggregate_incident(errors) -> Dict[str, Any]:
    """Section 92: 47 timeouts are ONE incident with 47 occurrences."""
    rows = [_d(x) for x in _l(errors)]
    if not rows:
        return {"incidents": [], "why": "nothing to aggregate"}
    by_key: Dict[str, dict] = {}
    for r in rows:
        key = _id(r.get("component"), r.get("kind"))
        if key in by_key:
            by_key[key]["occurrences"] += 1
        else:
            by_key[key] = {"component": r.get("component"),
                           "kind": r.get("kind"),
                           "severity": r.get("severity") or "P2",
                           "occurrences": 1,
                           "first_at": r.get("at")}
    return {"incidents": sorted(by_key.values(),
                                key=lambda x: -x["occurrences"]),
            "why": (str(len(rows)) + " error(s) collapse into "
                    + str(len(by_key)) + " incident(s); a page of "
                    "identical alerts is how the different one gets "
                    "missed")}


NOTIFY_WHEN = ("HUMAN_ACTION_REQUIRED", "P0", "P1", "TARGET_THREATENED",
               "HIGH_VALUE_OPPORTUNITY", "APPROVAL_REQUIRED",
               "SECURITY", "BUDGET_BREACH")


def should_notify(reason) -> Dict[str, Any]:
    r = _s(reason).upper()
    if r in NOTIFY_WHEN:
        return {"notify": True, "why": r + " warrants an interruption"}
    return {"notify": False,
            "why": ("'" + r + "' stays visible on the cockpit and does "
                    "not interrupt anyone. Section 93: notification is "
                    "for action, not awareness.")}


# ===========================================================================
# 36-38, 80-83, 99-100. THE COMMANDER
# ===========================================================================
#: Section 99. What the Commander receives. Structured snapshots only,
#: never raw dumps and never model memory.
COMMANDER_INPUT = ("business", "system", "cost", "data_health",
                   "changes", "risks", "opportunities", "incidents",
                   "loops", "initiatives")

#: Section 100. What it returns.
COMMANDER_OUTPUT = ("situation", "top_changes", "top_risks",
                    "top_opportunities", "decisions", "quick_fixes",
                    "system_diagnosis", "business_diagnosis",
                    "confidence", "data_limitations")

MAX_RECOMMENDATIONS = 5


def commander(question, snapshots=None) -> Dict[str, Any]:
    """The one Commander. Snapshots in, structure out, five actions max.

    Section 36: it never answers an operational question from model
    memory. No snapshots means NO EVIDENCE, not a fluent guess, and
    section 80 caps recommendations at five because thirty is a report,
    not a command.
    """
    sn = _d(snapshots)
    supplied = [k for k in COMMANDER_INPUT if sn.get(k)]
    if not supplied:
        return {"state": "NO_EVIDENCE", "question": _s(question),
                "why": ("no snapshot was supplied. The Commander reads "
                        "structured state and refuses to compose an "
                        "answer from memory: a confident answer about "
                        "an unobserved system is the most expensive "
                        "sentence this cockpit could produce.")}
    facts, limitations = [], [k for k in COMMANDER_INPUT
                              if not sn.get(k)]
    biz = _d(sn.get("business"))
    for k, v in list(biz.items())[:6]:
        facts.append("business." + _s(k) + " = " + _s(v))
    sysd = _d(sn.get("system"))
    sick = [k for k, v in sysd.items()
            if _s(_d(v).get("status") if isinstance(v, dict) else v)
            .upper() in ("DEGRADED", "FAILED", "STALLED")]
    for k in sick:
        facts.append("system." + _s(k) + " is "
                     + _s(_d(sysd[k]).get("status")
                          if isinstance(sysd[k], dict) else sysd[k]))
    changes = change_feed(sn.get("changes"), limit=5)
    risks = _l(sn.get("risks"))[:3]
    opps = _l(sn.get("opportunities"))[:3]
    decs = rank_decisions(sn.get("decisions") or [])
    recs = decs["ranked"][:MAX_RECOMMENDATIONS]
    return {
        "state": "OK", "question": _s(question),
        "situation": (("business " + _s(biz.get("summary")))
                      if biz.get("summary") else
                      str(len(facts)) + " measured fact(s)"),
        "facts": facts,
        "top_changes": changes,
        "top_risks": risks,
        "top_opportunities": opps,
        "decisions": recs,
        "quick_fixes": _l(sn.get("quick_fixes"))[:3],
        "system_diagnosis": (", ".join(sick) + " unhealthy"
                             if sick else "no system reports unhealthy"),
        "business_diagnosis": (changes[0]["metric"] + " moved most ("
                               + _s(changes[0]["pct"]) + "%)"
                               if changes else "no change supplied"),
        "confidence": ("REDUCED" if limitations else "NORMAL"),
        "data_limitations": limitations,
        "why": ("at most " + str(MAX_RECOMMENDATIONS) + " ranked "
                "action(s), from snapshots only"
                + (". Confidence REDUCED: no snapshot for "
                   + ", ".join(limitations) if limitations else "")),
    }


# ===========================================================================
# 86-88. SNAPSHOT, EVENTS, API
# ===========================================================================
SNAPSHOT_FIELDS = ("timestamp", "workspace_id", "business_state",
                   "system_state", "cost_state", "risk_state",
                   "opportunity_state", "decision_state", "data_health",
                   "system_health")

COMMAND_EVENTS = ("REVENUE_UPDATED", "LEAD_CREATED", "CUSTOMER_CREATED",
                  "CAMPAIGN_PERFORMANCE_UPDATED",
                  "SEO_OPPORTUNITY_CREATED",
                  "CONTENT_PERFORMANCE_UPDATED",
                  "EMAIL_PERFORMANCE_UPDATED", "AGENT_HEALTH_CHANGED",
                  "WORKFLOW_FAILED", "LOOP_STALLED", "CONNECTION_FAILED",
                  "SERVER_DEGRADED", "API_COST_SPIKE",
                  "INCIDENT_CREATED", "ACTION_COMPLETED")

COMMAND_API = (
    ("GET", "/command/overview"), ("GET", "/command/changes"),
    ("GET", "/command/decisions"), ("GET", "/command/quick-fixes"),
    ("GET", "/command/loops"), ("GET", "/command/initiatives"),
    ("GET", "/command/incidents"), ("GET", "/command/costs"),
    ("GET", "/command/system-health"), ("POST", "/command/analyze"),
    ("POST", "/command/decisions/{id}/approve"),
    ("POST", "/command/quick-fixes/{id}/approve"),
    ("POST", "/command/actions/route"))

#: Section 103. What a visible issue may end in. Rendered on cards so a
#: dead end is visible as a bug.
OUTCOMES = ("IGNORE", "MONITOR", "ANALYZE", "DECIDE", "FIX", "ROUTE",
            "ESCALATE")
