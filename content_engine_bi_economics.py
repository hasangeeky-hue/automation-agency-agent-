# -*- coding: utf-8 -*-
"""BI OS: AGENT, TOOL AND DECISION ECONOMICS.

Spec sections 17-20, 24, 33-37, 43-44, 47-50, 53-57, 68-71, 86-93, 105.

THE QUESTION THIS MODULE ANSWERS
--------------------------------
Not "did the agent run" but "was it worth paying for". Section 105:

    DID IT EXECUTE?  DID IT WORK?  WHAT DID IT COST?
    WHAT VALUE DID IT CREATE?  WAS IT ECONOMICALLY WORTHWHILE?

An agent evaluated on token usage looks efficient while producing
nothing anyone approves. An agent evaluated on runs looks busy. The only
number that decides whether to keep paying for it is cost per ACCEPTED
output against the value that output influenced.

THE METRIC THAT MATTERS MOST (section 91)
-----------------------------------------
Cost per generated asset is close to useless. Cost per ACCEPTED asset is
the real one, because rejected work costs the same money and returns
nothing. The same applies to runs (successful, not total) and drafts
(published, not written). Every rate here is computed on the accepted
denominator and says which it used.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import content_engine_bi_cost as COST

_s, _d, _l, _f = COST._s, COST._d, COST._l, COST._f
_id = COST._id


# ===========================================================================
# 19. ATTRIBUTION CONFIDENCE
# ===========================================================================
#: Section 19. How firmly a value is tied to the thing that produced it.
#: Every ROI figure in this module carries one, because "this agent made
#: 18,400 euro" is a claim whose strength varies enormously and a
#: dashboard that renders all four identically is inviting a bad
#: decision.
ATTRIBUTION = ("DIRECT", "ASSISTED", "ESTIMATED", "UNKNOWN")


def _attr_note(level) -> str:
    return {
        "DIRECT": "the value is tied to this by a recorded identifier",
        "ASSISTED": ("this contributed alongside other touches; the "
                     "value is shared, not owned"),
        "ESTIMATED": "modelled from a pattern, not observed for this item",
        "UNKNOWN": ("nothing connects this to a business result; the "
                    "value column is blank rather than guessed"),
    }.get(_s(level).upper(), "attribution not stated")


# ===========================================================================
# 17-20. AGENT ECONOMICS
# ===========================================================================
AGENT_ECON_FIELDS = ("date", "agent_id", "workspace_id", "runs",
                     "successful_runs", "failed_runs", "tokens",
                     "tool_calls", "api_cost", "model_cost",
                     "external_tool_cost", "total_cost",
                     "actions_generated", "actions_approved",
                     "actions_executed", "business_value_attributed")

#: Below this many runs a per-run average is one or two data points
#: wearing a decimal point.
MIN_RUNS_FOR_RATE = 5


def agent_economics(row) -> Dict[str, Any]:
    """One agent's day, with every derived rate and its denominator.

    Section 91: cost per SUCCESSFUL run, not cost per run. An agent that
    runs a hundred times and succeeds twice has a flattering cost per run
    and a terrible cost per success, and only the second one tells you
    whether to keep it.
    """
    d = _d(row)
    runs = _f(d.get("runs"), 0) or 0
    ok = _f(d.get("successful_runs"), 0) or 0
    total = _f(d.get("total_cost"))
    if total is None:
        parts = [_f(d.get(k)) for k in ("api_cost", "model_cost",
                                        "external_tool_cost")]
        got = [p for p in parts if p is not None]
        total = sum(got) if got else None
    approved = _f(d.get("actions_approved"))
    executed = _f(d.get("actions_executed"))
    generated = _f(d.get("actions_generated"))
    value = _f(d.get("business_value_attributed"))
    conf = _s(d.get("attribution") or "UNKNOWN").upper()
    if conf not in ATTRIBUTION:
        conf = "UNKNOWN"

    def per(n, label):
        if total is None:
            return None, "no cost recorded"
        if not n:
            return None, ("nothing " + label + " yet, so a per-" + label
                          + " cost would divide by zero")
        return round(total / n, 4), ("cost divided by " + _s(int(n)) + " "
                                     + label)

    cps, cps_why = per(ok, "successful run")
    cpa, cpa_why = per(approved, "approved action")
    cpx, cpx_why = per(executed, "executed action")

    out = {
        "agent_id": d.get("agent_id"), "date": d.get("date"),
        "runs": runs, "successful_runs": ok,
        "failed_runs": _f(d.get("failed_runs"), max(runs - ok, 0)),
        "success_rate": (round(ok / runs, 4) if runs else None),
        "total_cost": total,
        "cost_per_run": (round(total / runs, 4)
                         if total is not None and runs else None),
        "cost_per_success": cps, "cost_per_success_why": cps_why,
        "cost_per_approved_action": cpa,
        "cost_per_executed_action": cpx,
        "actions_generated": generated, "actions_approved": approved,
        "approval_rate": (round(approved / generated, 4)
                          if approved is not None and generated else None),
        "business_value": value,
        "attribution": conf,
        "attribution_note": _attr_note(conf),
        "thin": runs < MIN_RUNS_FOR_RATE,
    }
    if runs < MIN_RUNS_FOR_RATE:
        out["why"] = (_s(int(runs)) + " run(s) is below the "
                      + str(MIN_RUNS_FOR_RATE) + " these averages need. "
                      "The figures are shown and marked thin rather than "
                      "hidden, because a founder still wants to see the "
                      "first days of a new agent.")
    else:
        out["why"] = (_s(int(ok)) + " of " + _s(int(runs))
                      + " runs succeeded"
                      + ("" if cps is None else
                         ", at " + _s(cps) + " per success"))
    out.update(agent_roi(total, value, confidence=conf))
    return out


def agent_roi(cost, value, *, confidence="UNKNOWN") -> Dict[str, Any]:
    """Section 19. ROI, or an honest refusal to compute one.

    Refuses when attribution is UNKNOWN. A ratio built on a value nobody
    can tie to the agent is a number that will be quoted in a decision
    and cannot be defended in the review of that decision.
    """
    c, v = _f(cost), _f(value)
    conf = _s(confidence).upper()
    if c is None or c <= 0:
        return {"roi": None, "roi_state": "NO COST",
                "roi_why": ("no cost recorded, so there is no return to "
                            "compute against")}
    if v is None:
        return {"roi": None, "roi_state": "NO VALUE ATTRIBUTED",
                "roi_why": ("no business value is attributed to this "
                            "agent. That is not the same as it having "
                            "produced none.")}
    if conf == "UNKNOWN":
        return {"roi": None, "roi_state": "UNATTRIBUTED", "cost": c,
                "value": v,
                "roi_why": ("a value of " + _s(v) + " exists but nothing "
                            "connects it to this agent. An ROI here "
                            "would be arithmetic on a coincidence.")}
    return {"roi": round((v - c) / c, 3), "roi_state": "OK",
            "cost": c, "value": v, "attribution": conf,
            "roi_why": (_s(v) + " attributed against " + _s(c)
                        + " of cost, " + conf.lower()
                        + " attribution: " + _attr_note(conf))}


def agent_card(row, *, accepted_outputs=None) -> Dict[str, Any]:
    """Section 20. The card that says whether an agent is worth it.

    The status is set by cost per ACCEPTED output, not by total spend. An
    expensive agent that lands everything is fine; a cheap one that lands
    nothing is not.
    """
    ec = agent_economics(row)
    acc = _f(accepted_outputs)
    total = ec.get("total_cost")
    cpa = (round(total / acc, 4)
           if total is not None and acc else None)
    if cpa is None:
        state, why = "NOT ASSESSED", (
            "nothing accepted yet, so cost per accepted output cannot be "
            "computed. Total spend alone does not say whether this agent "
            "is expensive.")
    else:
        rate = (acc / _f(ec.get("actions_generated"), acc) or 1)
        if cpa > 10 and (ec.get("approval_rate") or 1) < 0.6:
            state = "EXPENSIVE"
            why = (_s(cpa) + " per accepted output with an approval rate "
                   "of " + _s(round((ec.get("approval_rate") or 0) * 100))
                   + "%. Most of what it makes is not used.")
        elif cpa > 10:
            state = "WATCH"
            why = (_s(cpa) + " per accepted output. High, but most of "
                   "what it makes is accepted.")
        else:
            state = "OK"
            why = _s(cpa) + " per accepted output"
    return dict(ec, accepted_outputs=acc, cost_per_accepted=cpa,
                status=state, status_why=why)


# ===========================================================================
# 33-37. THE COST-AWARE MODEL AND TOOL ROUTER
# ===========================================================================
#: Section 33. Task classes, cheapest capability first. A router that
#: sends everything to the strongest model is the single largest
#: avoidable AI cost in an agentic system.
TASK_TIERS = ("CLASSIFICATION", "SIMPLE_REWRITE", "DRAFTING",
              "ANALYSIS", "BUSINESS_STRATEGY", "CRITICAL_JUDGEMENT")

_TIER_INDEX = {t: i for i, t in enumerate(TASK_TIERS)}

OPTIMISE_FOR = ("COST", "QUALITY", "SPEED", "BALANCED")


def route_model(task_tier, candidates, *, optimise="BALANCED",
                budget_remaining=None) -> Dict[str, Any]:
    """Choose a model on utility, not on price alone. Section 34.

        Utility = capability fit + quality + reliability
                  - cost penalty - latency penalty

    Section 34 forbids both failure modes explicitly: never the cheapest
    blindly, never the most expensive blindly. A model that cannot do
    the task is not a saving at any price.
    """
    tier = _s(task_tier).upper()
    if tier not in _TIER_INDEX:
        return {"ok": False, "state": "UNKNOWN TASK",
                "why": "'" + tier + "' is not a task tier"}
    need = _TIER_INDEX[tier]
    rows = [_d(c) for c in _l(candidates)]
    if not rows:
        return {"ok": False, "state": "NO CANDIDATES",
                "why": "no model was offered for this task"}
    capable = [r for r in rows
               if _TIER_INDEX.get(_s(r.get("max_tier")).upper(), -1) >= need]
    if not capable:
        return {"ok": False, "state": "NONE CAPABLE",
                "why": ("no candidate can handle a " + tier + " task. "
                        "Falling back to a cheaper model here would "
                        "spend money on an answer that cannot be used.")}
    w = {"COST": (0.15, 0.15, 0.60, 0.10),
         "QUALITY": (0.55, 0.25, 0.10, 0.10),
         "SPEED": (0.20, 0.15, 0.15, 0.50),
         "BALANCED": (0.35, 0.25, 0.30, 0.10)}[
             _s(optimise).upper() if _s(optimise).upper() in OPTIMISE_FOR
             else "BALANCED"]
    max_cost = max((_f(r.get("cost_per_1k"), 0) or 0) for r in capable) or 1
    max_lat = max((_f(r.get("latency_ms"), 0) or 0) for r in capable) or 1
    scored = []
    for r in capable:
        q = _f(r.get("quality"), 0.5) or 0.5
        rel = _f(r.get("reliability"), 0.9) or 0.9
        cpen = (_f(r.get("cost_per_1k"), 0) or 0) / max_cost
        lpen = (_f(r.get("latency_ms"), 0) or 0) / max_lat
        score = w[0] * q + w[1] * rel - w[2] * cpen - w[3] * lpen
        scored.append((round(score, 4), r))
    scored.sort(key=lambda x: -x[0])
    best_score, best = scored[0]
    cheapest = min(capable,
                   key=lambda r: _f(r.get("cost_per_1k"), 0) or 0)
    note = ""
    if best is not cheapest:
        note = (" It is not the cheapest capable option: "
                + _s(cheapest.get("name")) + " costs less but scored "
                "lower on quality or reliability for a " + tier
                + " task.")
    if budget_remaining is not None:
        rem = _f(budget_remaining, 0) or 0
        if rem <= 0:
            return {"ok": False, "state": "BUDGET EXHAUSTED",
                    "why": ("the budget for this scope is spent. The "
                            "router will not pick a model rather than "
                            "quietly switching to a worse one.")}
    return {"ok": True, "state": "SELECTED", "model": best.get("name"),
            "score": best_score, "optimise": _s(optimise).upper(),
            "candidates_considered": len(capable),
            "rejected_incapable": len(rows) - len(capable),
            "why": (_s(best.get("name")) + " scored highest for a " + tier
                    + " task optimising for " + _s(optimise).upper()
                    + "." + note)}


def route_tool(capability, providers, *, policy=None) -> Dict[str, Any]:
    """Primary, secondary, fallback. Section 35.

    A fallback that costs many times the primary is NOT taken
    automatically. Silently switching to a provider at ten times the
    price during an outage turns a degraded hour into an invoice nobody
    approved.
    """
    rows = [_d(p) for p in _l(providers)]
    up = [r for r in rows if _s(r.get("status")).upper() in
          ("", "AVAILABLE", "ACTIVE", "HEALTHY")]
    if not rows:
        return {"ok": False, "state": "NO PROVIDER",
                "why": "no provider is registered for "
                       + _s(capability).upper()}
    if not up:
        return {"ok": False, "state": "ALL DOWN",
                "why": ("every provider for " + _s(capability).upper()
                        + " is unavailable. Nothing is faked.")}
    ordered = sorted(up, key=lambda r: {"PRIMARY": 0, "SECONDARY": 1,
                                        "FALLBACK": 2}.get(
                                            _s(r.get("role")).upper(), 3))
    primary = ordered[0]
    base = _f(rows[0].get("unit_cost"))
    pick = _f(primary.get("unit_cost"))
    limit = _f(_d(policy).get("max_fallback_multiple"), 3.0) or 3.0
    if (base and pick and pick > base * limit
            and _s(primary.get("role")).upper() != "PRIMARY"):
        return {"ok": False, "state": "NEEDS AUTHORIZATION",
                "provider": primary.get("name"),
                "multiple": round(pick / base, 2),
                "why": (_s(primary.get("name")) + " costs "
                        + _s(round(pick / base, 1)) + "x the primary. "
                        "Section 35: a fallback that expensive needs "
                        "authorization rather than an automatic switch.")}
    return {"ok": True, "state": "SELECTED",
            "provider": primary.get("name"),
            "role": _s(primary.get("role")).upper() or "PRIMARY",
            "why": (_s(primary.get("name")) + " is the highest-priority "
                    "available provider for "
                    + _s(capability).upper())}


# ===========================================================================
# 24, 43, 69. TOOL ECONOMICS AND HEALTH
# ===========================================================================
def tool_economics(tool, events, versions=(), *, value=None,
                   outcomes=None) -> Dict[str, Any]:
    """One tool: what it cost, how it behaved, what it returned."""
    t = _d(tool)
    rows = [_d(e) for e in _l(events)
            if _s(_d(e).get("tool_id")) == _s(t.get("id"))]
    reqs = sum(_f(r.get("request_count"), 1) or 1 for r in rows)
    failed = [r for r in rows if _s(r.get("status")).upper() == "FAILED"]
    w = COST.waste(rows, versions)
    lat = [x for x in (_f(r.get("duration")) for r in rows)
           if x is not None]
    n_out = _f(outcomes)
    total = w.get("total")
    return {
        "tool": t.get("name"), "category": t.get("category"),
        "requests": reqs,
        "failure_rate": (round(len(failed) / len(rows), 4)
                         if rows else None),
        "avg_latency_ms": (round(sum(lat) / len(lat), 1) if lat else None),
        "total_cost": total,
        "wasted_cost": w.get("wasted"),
        "waste_pct": w.get("waste_pct"),
        "quality": w.get("quality"),
        "cost_per_outcome": (round(total / n_out, 4)
                             if total is not None and n_out else None),
        "business_value": _f(value),
        "why": (_s(int(reqs)) + " request(s), "
                + (_s(round(total, 2)) if total is not None else "no cost")
                + (". " + _s(w.get("waste_pct")) + "% wasted"
                   if w.get("waste_pct") else "")
                + ". Cost quality: " + _s(w.get("quality")))}


def quota_state(used, quota, *, resets_in_days=None) -> Dict[str, Any]:
    """Section 67-68. Quota is a risk even when the cost is zero.

    A free API that stops answering at its limit halts the work exactly
    as hard as an unpaid one, so this is reported separately from cost.
    """
    u, q = _f(used), _f(quota)
    if q is None or q <= 0:
        return {"state": "NO QUOTA", "why": "no quota recorded"}
    pct = (u or 0) / q
    st = ("EXCEEDED" if pct >= 1 else "AT RISK" if pct >= 0.8
          else "NORMAL")
    return {"state": st, "used_pct": round(pct, 4),
            "resets_in_days": resets_in_days,
            "why": (str(round(pct * 100, 1)) + "% of quota consumed"
                    + (", resets in " + _s(resets_in_days) + " day(s)"
                       if resets_in_days is not None else "")
                    + (". This is a availability risk regardless of cost."
                       if st != "NORMAL" else ""))}


# ===========================================================================
# 44. THREE HEALTHS, KEPT APART
# ===========================================================================
HEALTHS = ("DATA_HEALTH", "TOOL_HEALTH", "COST_HEALTH")

HEALTH_QUESTION = {
    "DATA_HEALTH": "are our inputs correct and fresh?",
    "TOOL_HEALTH": "are the providers operating correctly?",
    "COST_HEALTH": "are we operating economically?",
}


# ===========================================================================
# 48-50, 92-93. UNIT ECONOMICS
# ===========================================================================
def unit_cost(total_cost, count, *, unit, accepted_only=True
              ) -> Dict[str, Any]:
    """A cost per something, with the denominator named.

    Section 91-92: the denominator is the whole argument. Cost per draft
    and cost per PUBLISHED draft differ by the rejection rate, and only
    the second is a business number.
    """
    c, n = _f(total_cost), _f(count)
    if c is None:
        return {"value": None, "why": "no cost recorded"}
    if not n:
        return {"value": None, "unit": unit,
                "why": ("no " + _s(unit) + " to divide by. A cost with "
                        "nothing to show for it is not a unit cost, it "
                        "is a loss.")}
    return {"value": round(c / n, 4), "unit": unit, "count": n,
            "accepted_only": bool(accepted_only),
            "why": (_s(round(c, 2)) + " over " + _s(int(n)) + " "
                    + _s(unit)
                    + (" (accepted only)" if accepted_only else
                       " (INCLUDING rejected, which flatters the number)"))}


def true_cac(*, customers, media, marketing_ai=None, marketing_tools=None,
             content_allocated=None, data_allocated=None) -> Dict:
    """Section 49. Both CACs, never one silently replacing the other.

    Marketing CAC is what everyone benchmarks. Full acquisition CAC is
    what the business actually pays. Showing only the second breaks
    every comparison; showing only the first hides the machine's cost.
    """
    n = _f(customers)
    m = _f(media)
    if not n:
        return {"state": "NO CUSTOMERS",
                "why": "no customers in the window, so no CAC"}
    if m is None:
        return {"state": "NO MEDIA SPEND",
                "why": "media spend is required for a marketing CAC"}
    extras = {"marketing_ai": _f(marketing_ai),
              "marketing_tools": _f(marketing_tools),
              "content_allocated": _f(content_allocated),
              "data_allocated": _f(data_allocated)}
    present = {k: v for k, v in extras.items() if v is not None}
    missing = [k for k, v in extras.items() if v is None]
    full = m + sum(present.values())
    return {"state": "OK",
            "marketing_cac": round(m / n, 2),
            "full_acquisition_cac": round(full / n, 2),
            "customers": n,
            "components": dict(present, media=m),
            "missing_components": missing,
            "quality": ("CALCULATED" if not missing else "ALLOCATED"),
            "why": ("marketing CAC is media over customers; full "
                    "acquisition CAC adds the AI, tooling and allocated "
                    "production behind it. Both are shown because "
                    "replacing the first breaks every external "
                    "comparison."
                    + (" Not supplied and therefore not included: "
                       + ", ".join(missing) + "." if missing else ""))}


def cost_per_revenue(tool_cost, revenue) -> Dict[str, Any]:
    """Section 93. What one unit of revenue costs in AI and tooling."""
    c, r = _f(tool_cost), _f(revenue)
    if c is None or not r:
        return {"value": None,
                "why": "needs both AI/tool cost and revenue"}
    return {"value": round(c / r, 6),
            "why": (_s(round(c, 2)) + " of AI and tooling per "
                    + _s(round(r, 2)) + " of revenue, so "
                    + _s(round(c / r, 4)) + " per unit of revenue")}


# ===========================================================================
# 53-57, 86-87. DECISION ECONOMICS
# ===========================================================================
def option(name, *, expected_value_low, expected_value_high,
           expected_cost_low, expected_cost_high, confidence=None,
           risk="MEDIUM", time_to_result="", evidence=None
           ) -> Dict[str, Any]:
    """One option, as a RANGE. Section 53.

    Point estimates on a forecast are false precision. A range with a
    confidence is a claim someone can argue with, which is the point.
    """
    vl, vh = _f(expected_value_low), _f(expected_value_high)
    cl, ch = _f(expected_cost_low), _f(expected_cost_high)
    if None in (vl, vh, cl, ch):
        return {"ok": False, "name": _s(name),
                "why": ("an option needs a value range AND a cost range. "
                        "Section 53: no recommendation without its "
                        "execution cost.")}
    return {"ok": True, "name": _s(name),
            "expected_value": (vl, vh), "expected_cost": (cl, ch),
            "expected_net": (round(vl - ch, 2), round(vh - cl, 2)),
            "confidence": _f(confidence),
            "risk": _s(risk).upper() or "MEDIUM",
            "time_to_result": _s(time_to_result),
            "evidence": _l(evidence),
            "why": ("net " + _s(round(vl - ch, 2)) + " to "
                    + _s(round(vh - cl, 2)) + " after an execution cost "
                    "of " + _s(cl) + " to " + _s(ch))}


def rank_options(options) -> Dict[str, Any]:
    """Rank by expected NET value, not by expected revenue. Section 87.

    Ranking on revenue recommends the biggest spend every time. The
    worked example in the spec is exactly this: paid looks best on
    revenue and worst on net.
    """
    rows = [o for o in (_d(x) for x in _l(options)) if o.get("ok")]
    if not rows:
        return {"state": "NO OPTIONS",
                "why": ("nothing to rank. An option without a cost range "
                        "is not scored rather than assumed free.")}
    def midnet(o):
        lo, hi = o["expected_net"]
        return (lo + hi) / 2.0
    ranked = sorted(rows, key=lambda o: -midnet(o))
    top = ranked[0]
    by_revenue = sorted(rows,
                        key=lambda o: -((o["expected_value"][0]
                                         + o["expected_value"][1]) / 2.0))
    note = ""
    if by_revenue[0] is not top:
        note = (" Ranked on revenue the answer would have been "
                + _s(by_revenue[0]["name"]) + ", which costs more than "
                "it returns relative to " + _s(top["name"]) + ".")
    return {"state": "RANKED", "ranked": ranked,
            "recommended": top["name"],
            "why": (_s(top["name"]) + " has the highest expected NET "
                    "value." + note)}


def decision_card(option_row, *, media_cost=None, tool_cost=None
                  ) -> Dict[str, Any]:
    """Section 54. What an approver sees before saying yes.

    Business impact, execution cost split into media and tooling, and
    the expected net. Approving a number without its cost beside it is
    the habit this whole specification exists to end.
    """
    o = _d(option_row)
    if not o.get("ok"):
        return {"state": "NOT APPROVABLE",
                "why": _s(o.get("why")) or "the option is incomplete"}
    m, t = _f(media_cost), _f(tool_cost)
    known = [x for x in (m, t) if x is not None]
    total = sum(known) if known else None
    lo, hi = o["expected_net"]
    return {"state": "READY", "name": o["name"],
            "expected_value": o["expected_value"],
            "media_cost": m, "tool_cost": t,
            "total_execution_cost": total,
            "expected_net": (lo, hi),
            "confidence": o.get("confidence"),
            "why": ("media and tooling are shown separately because they "
                    "are budgeted separately; the net is what the "
                    "business keeps if this works.")}


def estimate_variance(estimated, actual) -> Dict[str, Any]:
    """Section 56-57. Compare, and keep it so estimates improve.

    An estimator nobody scores stays wrong forever. This is the record
    that lets the next estimate be better than the last.
    """
    e, a = _f(estimated), _f(actual)
    if e is None or a is None:
        return {"state": "INCOMPLETE",
                "why": "both an estimate and an actual are needed"}
    if e == 0:
        return {"state": "NO BASELINE",
                "why": "an estimate of zero has no percentage variance"}
    var = (a - e) / e
    return {"state": "OK", "estimated": e, "actual": a,
            "variance": round(var, 4),
            "direction": ("OVER" if var > 0 else "UNDER" if var < 0
                          else "EXACT"),
            "why": (_s(a) + " actual against " + _s(e) + " estimated, "
                    + _s(round(var * 100, 1)) + "%. Stored so the next "
                    "estimate for this action type is better.")}


# ===========================================================================
# 70-71. WORKFLOW ECONOMICS
# ===========================================================================
def workflow_economics(row) -> Dict[str, Any]:
    """One workflow: runs, cost, and cost per thing that shipped."""
    d = _d(row)
    runs = _f(d.get("runs"), 0) or 0
    total = _f(d.get("total_cost"))
    published = _f(d.get("published"))
    approved = _f(d.get("approved"))
    value = _f(d.get("business_value"))
    conf = _s(d.get("attribution") or "UNKNOWN").upper()
    return {
        "workflow": d.get("name"), "runs": runs,
        "success_rate": _f(d.get("success_rate")),
        "avg_cost": (round(total / runs, 4)
                     if total is not None and runs else None),
        "total_cost": total,
        "approval_rate": (round(approved / runs, 4)
                          if approved is not None and runs else None),
        "cost_per_published": (round(total / published, 4)
                               if total is not None and published
                               else None),
        "business_value": value,
        "attribution": conf if conf in ATTRIBUTION else "UNKNOWN",
        "why": (_s(int(runs)) + " run(s)"
                + ("" if total is None else
                   ", " + _s(round(total, 2)) + " total")
                + ("" if not published else
                   ", " + _s(round((total or 0) / published, 2))
                   + " per published item")
                + ". " + _attr_note(conf))}


# ===========================================================================
# 88. COST RISK TYPES
# ===========================================================================
COST_RISKS = ("COST_RISK", "API_COST_SPIKE", "AGENT_COST_SPIKE",
              "TOOL_REDUNDANCY", "QUOTA_RISK", "SUBSCRIPTION_WASTE",
              "RETRY_WASTE", "MODEL_OVERUSE", "TOOL_OPTIMIZATION")


# ===========================================================================
# 89-90. OPTIMISATION SUGGESTIONS
# ===========================================================================
def optimisation(kind, *, saving_low, saving_high, risk="LOW",
                 confidence=None, quality_impact="NONE",
                 effort="LOW") -> Dict[str, Any]:
    """A saving, with what it costs in quality. Section 90.

    Never recommends a cheaper tool on price alone. A provider costing
    20% more that rejects 40% fewer outputs is cheaper per ACCEPTED
    output, and a recommendation that ignores that destroys the thing it
    was meant to improve.
    """
    k = _s(kind).upper()
    lo, hi = _f(saving_low), _f(saving_high)
    if k not in COST_RISKS:
        return {"ok": False,
                "why": "'" + k + "' is not a cost optimisation type"}
    if lo is None or hi is None:
        return {"ok": False, "kind": k,
                "why": ("a saving must be a range. A single number here "
                        "is false precision on a forecast.")}
    qi = _s(quality_impact).upper() or "NONE"
    if qi in ("HIGH", "SEVERE"):
        return {"ok": False, "kind": k, "saving": (lo, hi),
                "quality_impact": qi,
                "why": ("this would save " + _s(lo) + " to " + _s(hi)
                        + " and cost " + qi + " quality. Section 90: "
                        "cheaper is not an improvement if the output "
                        "stops being usable.")}
    return {"ok": True, "kind": k, "saving": (lo, hi),
            "risk": _s(risk).upper(), "confidence": _f(confidence),
            "quality_impact": qi, "effort": _s(effort).upper(),
            "why": (_s(lo) + " to " + _s(hi) + " a month, "
                    + _s(risk).lower() + " risk, quality impact "
                    + qi.lower())}


# ===========================================================================
# 94. THE SENTENCE THE BI OS MUST BE ABLE TO SAY
# ===========================================================================
def executive_summary(*, revenue, media, ai_tools, by_os=None,
                      customers=None, top_waste=None,
                      best_source=None) -> Dict[str, Any]:
    """Section 94. The paragraph, assembled only from supplied numbers.

    Every clause is dropped if its input is missing rather than filled
    with a plausible figure. A summary that reads well because it
    invented the gaps is the most dangerous artefact this OS could
    produce.
    """
    r, m, t = _f(revenue), _f(media), _f(ai_tools)
    if r is None:
        return {"state": "NO REVENUE",
                "why": "the summary starts from revenue and none was "
                       "supplied"}
    bits = ["Revenue " + _s(round(r, 2)) + "."]
    if m is not None:
        bits.append("Media spend " + _s(round(m, 2)) + ".")
    if t is not None:
        bits.append("AI and tooling " + _s(round(t, 2)) + ".")
    for name, amt in sorted(_d(by_os).items(),
                            key=lambda kv: -(_f(kv[1], 0) or 0))[:4]:
        bits.append(_s(name) + " cost " + _s(round(_f(amt, 0) or 0, 2))
                    + ".")
    cac = None
    if customers:
        parts = [x for x in (m, t) if x is not None]
        if parts:
            cac = round(sum(parts) / _f(customers), 2)
            bits.append("Blended full acquisition cost "
                        + _s(cac) + " per customer.")
    if best_source:
        bits.append("Most economically efficient growth source: "
                    + _s(best_source) + ".")
    if top_waste:
        bits.append("Largest unnecessary cost: " + _s(top_waste) + ".")
    missing = [k for k, v in (("media", m), ("ai_tools", t),
                              ("customers", customers)) if v is None]
    return {"state": "OK", "summary": " ".join(bits),
            "full_acquisition_cac": cac,
            "missing": missing,
            "why": ("assembled only from figures that were supplied."
                    + (" Not stated because not supplied: "
                       + ", ".join(missing) + "." if missing else ""))}
