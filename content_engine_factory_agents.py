# -*- coding: utf-8 -*-
"""CONTENT FACTORY OS: the four agents, and the deterministic conductor.

Spec sections 21, 31-32, 52-53, 68, 72, 74-77, 98, 108.

FOUR AGENTS. NOT SEVENTEEN.
---------------------------
Section 72 names exactly four things that reason:

    1. PLANNER      signals + learning -> plan + brief
    2. CREATOR      brief -> draft, variants, asset requests
    3. QA           content -> PASS / WARNING / FAIL
    4. PERFORMANCE  results -> learning

Everything else is a service in content_engine_factory_os.py. Section 73
is explicit and this module holds the line: versioning, permissions,
approval, scheduling, distribution, tool routing, platform validation and
state transitions do not reason and must not cost a token.

WHY THE ORCHESTRATOR IS NOT AN AGENT
------------------------------------
Section 74: the conductor is deterministic. It reads a table and calls
the next thing. An orchestrator that reasons about what to do next is a
fifth agent wearing a coordinator's name, and its decisions are the ones
nobody can reproduce when the output is wrong.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import content_engine_factory_os as FOS

_s, _d, _l, _f = FOS._s, FOS._d, FOS._l, FOS._f

# ===========================================================================
# 72. THE FOUR
# ===========================================================================
AGENTS = ("PLANNER", "CREATOR", "QA", "PERFORMANCE")

AGENT_PURPOSE = {
    "PLANNER": "turns signals and learning into plans and briefs",
    "CREATOR": "writes copy and asks the tool router for assets",
    "QA": "checks brand, quality, platform and claims",
    "PERFORMANCE": "reads returned results and writes learning",
}

#: What each agent is allowed to DO. Not documentation: enforced by
#: guard() below. The Performance agent explicitly cannot create or
#: publish content (section 68), and no agent can approve (section 54).
AGENT_CAN = {
    "PLANNER": ("read_signals", "read_learning", "write_plan",
                "write_brief"),
    "CREATOR": ("read_brief", "write_blocks", "request_asset",
                "write_variant"),
    "QA": ("read_content", "write_qa_result"),
    "PERFORMANCE": ("read_performance", "write_learning"),
}

#: Actions no agent may ever take, whatever it asks for.
FORBIDDEN = ("approve_content", "distribute_content", "publish_content",
             "change_lock", "spend_budget", "delete_content")


class NotPermitted(Exception):
    """An agent asked for something outside its remit."""


def guard(agent, action) -> Dict[str, Any]:
    """May this agent do this? A rule, not a prompt instruction."""
    a, act = _s(agent).upper(), _s(action).lower()
    if a not in AGENTS:
        return {"ok": False, "why": "'" + _s(agent) + "' is not one of the "
                "four agents this factory has"}
    if act in FORBIDDEN:
        return {"ok": False, "why": (
            "'" + act + "' is forbidden to every agent. Approval, "
            "distribution and publishing are human actions, and a lock is "
            "a human's decision that an agent must not undo.")}
    if act not in AGENT_CAN[a]:
        return {"ok": False, "why": (
            "the " + a + " agent " + AGENT_PURPOSE[a] + "; '" + act
            + "' is not among the things it does. Allowed: "
            + ", ".join(AGENT_CAN[a]))}
    return {"ok": True, "why": a + " may " + act}


# ===========================================================================
# 75. LOOP LIMITS. Exceeding one is NEEDS_HUMAN, never another try.
# ===========================================================================
BUDGET = {"max_steps": 8, "max_tool_calls": 6, "max_retries": 2,
          "max_cost_usd": 0.50, "timeout_s": 120}

RUN_STATES = ("RUNNING", "DONE", "NEEDS_HUMAN", "REFUSED")


def new_run(agent, objective, *, budget=None, at="") -> Dict[str, Any]:
    b = dict(BUDGET)
    b.update({k: v for k, v in _d(budget).items() if k in BUDGET})
    return {"id": FOS._id(agent, objective, at),
            "agent": _s(agent).upper(),
            "objective": _s(objective),
            "state": "RUNNING",
            "budget": b,
            "used": {k: 0 for k in b},
            "exit_condition": None,
            "started_at": _s(at),
            "steps": []}


def spend(run, *, steps=0, tool_calls=0, retries=0, cost_usd=0.0,
          seconds=0) -> Dict[str, Any]:
    """Charge a run. Exhausting ANY limit escalates to a person.

    Section 75 forbids `while not perfect: try again`. There is no retry
    branch here on purpose: the only thing exhaustion produces is
    NEEDS_HUMAN, and a caller that wants another attempt has to open a
    new run with a new budget, which is visible.
    """
    r = dict(_d(run))
    u = dict(_d(r.get("used")))
    b = _d(r.get("budget"))
    u["max_steps"] = _f(u.get("max_steps"), 0) + steps
    u["max_tool_calls"] = _f(u.get("max_tool_calls"), 0) + tool_calls
    u["max_retries"] = _f(u.get("max_retries"), 0) + retries
    u["max_cost_usd"] = round(_f(u.get("max_cost_usd"), 0) + cost_usd, 6)
    u["timeout_s"] = _f(u.get("timeout_s"), 0) + seconds
    r["used"] = u
    blown = [k for k in b if _f(u.get(k), 0) > _f(b.get(k), 0)]
    if blown:
        r["state"] = "NEEDS_HUMAN"
        r["exit_condition"] = blown
        r["why"] = ("this run exhausted " + ", ".join(blown)
                    + " and stopped. It did not try again: a loop that "
                    "retries until it likes the answer has no ceiling.")
    return r


def finish(run, *, state="DONE", why="") -> Dict[str, Any]:
    r = dict(_d(run))
    if r.get("state") == "NEEDS_HUMAN":
        return r
    st = _s(state).upper()
    r["state"] = st if st in RUN_STATES else "DONE"
    r["why"] = _s(why) or r.get("why") or "completed within budget"
    return r


# ===========================================================================
# 76. STRUCTURED OUTPUTS. Never chat between agents.
# ===========================================================================
#: Section 76. Each agent returns a named shape, validated here. Passing
#: prose between agents is how a factory ends up with a plan nobody can
#: query and a QA result nobody can gate on.
SCHEMAS = {
    "ContentPlan": ("name", "period_start", "period_end", "goal", "items"),
    "ContentBrief": ("objective", "audience", "funnel_stage", "topic",
                     "primary_message", "supporting_points", "cta",
                     "channel", "format", "paid_or_organic",
                     "success_metric"),
    "ContentDraft": ("blocks", "channel", "format", "notes"),
    "QAResult": ("state", "checks", "recommended_corrections"),
    "ContentLearning": ("attribute_type", "attribute_value", "channel",
                        "metric", "performance_value", "sample_size",
                        "confidence"),
}


def validate_output(name, payload) -> Dict[str, Any]:
    """Does this agent output have the fields its contract promises?"""
    want = SCHEMAS.get(_s(name))
    if want is None:
        return {"ok": False, "why": "'" + _s(name) + "' is not a declared "
                "agent output shape"}
    d = _d(payload)
    missing = [k for k in want if k not in d]
    return {"ok": not missing, "missing": missing,
            "why": ("every field present" if not missing
                    else "missing " + ", ".join(missing))}


# ===========================================================================
# 108. FACT / INFERENCE / RECOMMENDATION
# ===========================================================================
CLAIM_KINDS = ("FACT", "INFERENCE", "RECOMMENDATION")


def claim(kind, text, *, evidence=None) -> Dict[str, Any]:
    """Section 108. A FACT must point at a signal or a performance row.

    An agent that says "pain-point hooks perform better" without a
    reference is inferring. Labelling that a FACT is how a dashboard
    starts quoting its own guesses back to itself a month later.
    """
    k = _s(kind).upper()
    if k not in CLAIM_KINDS:
        return {"kind": "INFERENCE", "text": _s(text), "evidence": None,
                "why": ("'" + _s(kind) + "' is not a claim kind, so this "
                        "is treated as an inference rather than promoted "
                        "to a fact")}
    ev = _d(evidence)
    if k == "FACT" and not (ev.get("signal_id")
                            or ev.get("performance_id")
                            or ev.get("learning_id")):
        return {"kind": "INFERENCE", "text": _s(text), "evidence": ev,
                "downgraded": True,
                "why": ("a FACT must reference a content_signal or a "
                        "content_performance record. This one references "
                        "neither, so it is an inference.")}
    return {"kind": k, "text": _s(text), "evidence": ev or None,
            "why": ("referenced" if k == "FACT" else k.lower())}


def split_claims(items) -> Dict[str, List[Dict]]:
    out = {k: [] for k in CLAIM_KINDS}
    for it in _l(items):
        c = claim(_d(it).get("kind"), _d(it).get("text"),
                  evidence=_d(it).get("evidence"))
        out[c["kind"]].append(c)
    return out


# ===========================================================================
# AGENT 1 - PLANNER (sections 21, 72)
# ===========================================================================
def planner_inputs(*, signals=(), scheduled=(), goals=None, campaigns=(),
                   learning=(), capacity=None) -> Dict[str, Any]:
    """Exactly what section 21 says the planner receives. No more.

    Capacity is included because a plan that ignores it is a wish list.
    """
    return {"signals": [_d(s) for s in _l(signals)],
            "scheduled": [_d(s) for s in _l(scheduled)],
            "goals": _d(goals),
            "campaigns": [_d(c) for c in _l(campaigns)],
            "learning": [_d(x) for x in _l(learning)],
            "capacity": _d(capacity)}


def planner_run(inputs, *, run=None, at="") -> Dict[str, Any]:
    """Signals and learning to a DRAFT plan. It never schedules.

    Section 21: the planner returns a DRAFT and a human accepts, edits or
    rejects. Auto-scheduling would make every other approval gate
    decorative, because the calendar would already be full.
    """
    r = run or new_run("PLANNER", "plan from signals", at=at)
    g = guard("PLANNER", "write_plan")
    if not g["ok"]:
        return {"run": finish(r, state="REFUSED", why=g["why"]),
                "plan": None, "why": g["why"]}
    inp = _d(inputs)
    sigs = [s for s in _l(inp.get("signals"))
            if FOS.signal_is_actionable(s).get("ok")]
    if not sigs:
        return {"run": finish(r, state="DONE",
                              why="no actionable signal"),
                "plan": None,
                "why": ("no signal in the inbox can become a plan. Every "
                        "one is dismissed, expired, or carries no topic. "
                        "The planner will not invent a topic to fill a "
                        "week.")}
    cap = _f(_d(inp.get("capacity")).get("items_per_week"))
    ranked = sorted(sigs, key=lambda s: -(_f(_d(s).get("priority"), 0) or 0))
    if cap:
        ranked = ranked[:int(cap)]
    learning = _l(inp.get("learning"))
    items, used = [], []
    for s in ranked:
        d = _d(s)
        lift = _best_learning(learning, d)
        items.append({
            "signal_id": d.get("id"),
            "topic": d.get("topic"),
            "objective": d.get("recommended_action") or "unspecified",
            "audience": d.get("audience"),
            "channel": (_l(d.get("recommended_format")) or [None])[0],
            "format": (_l(d.get("recommended_format")) or [None])[0],
            "paid_or_organic": ("PAID" if d.get("source_system")
                                == "MEDIA_BUYING_OS" else "ORGANIC"),
            "priority": d.get("priority"),
            "scheduled_date": None,
            "status": "DRAFT",
            "because": _plan_reason(d, lift),
        })
        if lift:
            used.append(lift.get("id"))
    plan = {"name": "Draft plan", "period_start": None, "period_end": None,
            "goal": _d(inp.get("goals")).get("goal"),
            "status": "DRAFT", "items": items,
            "learning_used": used,
            "created_by": "PLANNER"}
    v = validate_output("ContentPlan", plan)
    r = spend(r, steps=1, cost_usd=0.0)
    return {"run": finish(r, why="drafted " + str(len(items)) + " item(s)"),
            "plan": plan if v["ok"] else None,
            "valid": v,
            "why": ("a DRAFT of " + str(len(items)) + " item(s), ranked by "
                    "the priority the sending system set. Nothing is "
                    "scheduled: a human accepts, edits or rejects each "
                    "one.")}


def _best_learning(learning, signal) -> Optional[Dict]:
    """The strongest learning that applies to this signal's channel."""
    ch = _s(_d(signal).get("channel")).upper()
    cands = [_d(x) for x in _l(learning)
             if _s(_d(x).get("status")).upper() == "ACTIVE"
             and (not ch or _s(_d(x).get("channel")).upper() in ("", ch))]
    if not cands:
        return None
    return sorted(cands, key=lambda x: -(_f(x.get("lift"), 0) or 0))[0]


def _plan_reason(sig, lift) -> str:
    d = _d(sig)
    bits = ["from " + _s(d.get("source_system")) + " signal "
            + _s(d.get("signal_type"))]
    if d.get("metric_name") and d.get("metric_value") is not None:
        bits.append(_s(d.get("metric_name")) + " "
                    + _s(d.get("metric_value")))
    if lift:
        bits.append("past learning: " + _s(lift.get("attribute_value"))
                    + " on " + _s(lift.get("channel")) + " ran "
                    + _s(lift.get("lift")) + "% against baseline over "
                    + _s(lift.get("sample_size")) + " item(s)")
    return "; ".join(bits)


def build_brief(plan_item, *, signal=None, brand=None) -> Dict[str, Any]:
    """A brief carries the evidence, so the Studio never has to invent it."""
    it, sg = _d(plan_item), _d(signal)
    brief = {
        "objective": it.get("objective"),
        "audience": it.get("audience") or _d(brand).get("audience"),
        "funnel_stage": it.get("funnel_stage") or "UNSPECIFIED",
        "topic": it.get("topic") or sg.get("topic"),
        "primary_message": sg.get("message") or it.get("topic"),
        "supporting_points": _l(sg.get("evidence_json")),
        "cta": it.get("cta"),
        "channel": it.get("channel"),
        "format": it.get("format"),
        "paid_or_organic": it.get("paid_or_organic"),
        "success_metric": it.get("success_metric") or sg.get("metric_name"),
        "evidence": {"signal_id": sg.get("id"),
                     "source_system": sg.get("source_system")},
    }
    v = validate_output("ContentBrief", brief)
    return {"brief": brief, "valid": v,
            "why": ("evidence is carried from the signal rather than "
                    "restated, so nothing in the Studio has to be "
                    "remembered or re-guessed")
            if sg else ("no signal attached, so this brief carries no "
                        "evidence and nothing in it may be quoted as "
                        "fact")}


# ===========================================================================
# AGENT 2 - CREATOR (sections 31-32, 72)
# ===========================================================================
#: Section 31. The contextual actions, and nothing else. Each maps to a
#: structured operation; section 77 says chat calls these rather than
#: passing prose.
CREATOR_ACTIONS = ("GENERATE_DRAFT", "REWRITE", "IMPROVE_HOOK", "SHORTEN",
                   "EXPAND", "CREATE_VARIANTS", "GENERATE_IMAGE",
                   "CREATE_VIDEO_CONCEPT", "ADAPT_PLATFORM")

#: Section 32. Which actions operate on a SELECTION rather than the whole
#: piece. Regenerating a whole article to shorten one paragraph throws
#: away every human edit in it.
BLOCK_SCOPED = ("REWRITE", "IMPROVE_HOOK", "SHORTEN", "EXPAND")


def creator_action(action, *, block_id=None, instruction="",
                   blocks=(), brief=None, run=None, at="") -> Dict:
    """One Creator action, scoped and permission-checked before anything.

    Section 32: a block-scoped action receives the selected block, the
    relevant context and the instruction. It does not receive, and cannot
    rewrite, the rest of the piece.
    """
    act = _s(action).upper()
    r = run or new_run("CREATOR", act, at=at)
    if act not in CREATOR_ACTIONS:
        return {"run": finish(r, state="REFUSED",
                              why="unknown action"),
                "ok": False,
                "why": ("'" + act + "' is not a Creator action. Allowed: "
                        + ", ".join(CREATOR_ACTIONS))}
    need = "request_asset" if act in ("GENERATE_IMAGE",
                                      "CREATE_VIDEO_CONCEPT") \
        else "write_blocks"
    g = guard("CREATOR", need)
    if not g["ok"]:
        return {"run": finish(r, state="REFUSED", why=g["why"]),
                "ok": False, "why": g["why"]}
    if act in BLOCK_SCOPED:
        if not block_id:
            return {"run": finish(r, state="REFUSED", why="no selection"),
                    "ok": False,
                    "why": (act + " works on a selected block. Without "
                            "one it would regenerate the whole piece and "
                            "discard every human edit in it.")}
        target = [b for b in _l(blocks) if _d(b).get("id") == block_id]
        if not target:
            return {"run": finish(r, state="REFUSED", why="no such block"),
                    "ok": False, "why": "no block with id " + _s(block_id)}
        if _d(target[0]).get("locked"):
            return {"run": finish(r, state="REFUSED", why="locked"),
                    "ok": False,
                    "why": ("that block is locked by a human. Unlock it "
                            "first; an agent cannot.")}
        ctx = {"block": _d(target[0]),
               "brief": _d(brief),
               "instruction": _s(instruction)}
    else:
        ctx = {"blocks": [_d(b) for b in _l(blocks)],
               "brief": _d(brief), "instruction": _s(instruction)}
    if act in ("GENERATE_IMAGE", "CREATE_VIDEO_CONCEPT"):
        cap = ("IMAGE_GENERATION" if act == "GENERATE_IMAGE"
               else "VIDEO_GENERATION")
        route = FOS.route_tool(cap)
        r = spend(r, steps=1, tool_calls=1)
        if not route["available"]:
            return {"run": finish(r, state="NEEDS_HUMAN",
                                  why=route["why"]),
                    "ok": False, "route": route, "why": route["why"]}
        return {"run": finish(r, why="asset requested"), "ok": True,
                "operation": {"kind": "TOOL_REQUEST", "capability": cap,
                              "context": ctx},
                "route": route,
                "why": ("routed to a capability, not a vendor, so the "
                        "provider can change without touching the agent")}
    r = spend(r, steps=1)
    return {"run": finish(r, why=act + " prepared"), "ok": True,
            "operation": {"kind": "CONTENT_BLOCK_REWRITE"
                          if act in BLOCK_SCOPED else "CONTENT_WRITE",
                          "action": act,
                          "target_block_id": block_id,
                          "context": ctx},
            "why": ("scoped to one block" if act in BLOCK_SCOPED
                    else "operates on the whole draft")}


def chat_to_action(message, *, block_id=None) -> Dict[str, Any]:
    """Section 77. Chat is a front door for a structured action.

    The message is mapped to a named operation. Nothing downstream ever
    receives free text as an instruction to interpret however it likes.
    """
    m = _s(message).lower()
    table = (("shorter", "SHORTEN"), ("shorten", "SHORTEN"),
             ("longer", "EXPAND"), ("expand", "EXPAND"),
             ("hook", "IMPROVE_HOOK"), ("rewrite", "REWRITE"),
             ("variant", "CREATE_VARIANTS"), ("variation",
                                              "CREATE_VARIANTS"),
             ("image", "GENERATE_IMAGE"), ("picture", "GENERATE_IMAGE"),
             ("video", "CREATE_VIDEO_CONCEPT"),
             ("linkedin", "ADAPT_PLATFORM"), ("adapt", "ADAPT_PLATFORM"),
             ("draft", "GENERATE_DRAFT"), ("write", "GENERATE_DRAFT"))
    for needle, act in table:
        if needle in m:
            return {"ok": True, "action": act,
                    "target_block_id": block_id,
                    "instruction": _s(message),
                    "why": ("mapped to " + act + " so the Creator runs a "
                            "named operation rather than interpreting a "
                            "sentence")}
    return {"ok": False, "action": None, "instruction": _s(message),
            "why": ("this message does not map to a Creator action. It is "
                    "not guessed at: pick an action, or rephrase.")}


# ===========================================================================
# AGENT 3 - QA (sections 52-53, 72)
# ===========================================================================
def qa_run(blocks, *, channel="", assets=(), brief=None, brand=None,
           run=None, at="") -> Dict[str, Any]:
    """One QA agent. It CALLS the deterministic validators first.

    Section 52 says one agent covers brand, grammar, required fields,
    claims, links, CTA, platform rules and asset availability, and that
    it may call deterministic validators. Everything checkable without
    judgement is checked without a model, so the model is only asked
    about the things that genuinely need an opinion.
    """
    r = run or new_run("QA", "review content", at=at)
    g = guard("QA", "write_qa_result")
    if not g["ok"]:
        return {"run": finish(r, state="REFUSED", why=g["why"]),
                "result": None, "why": g["why"]}
    checks = FOS.run_validators(blocks, channel=channel, assets=assets)
    judged = _brand_checks(blocks, brand)
    all_checks = checks + judged
    verdict = FOS.qa_verdict(all_checks)
    corrections = []
    for c in all_checks:
        cd = _d(c)
        if _s(cd.get("state")).upper() in ("FAIL", "WARNING"):
            corrections.append({"check": cd.get("check"),
                                "state": cd.get("state"),
                                "fix": _fix_for(cd)})
    result = {"state": verdict["state"], "checks": all_checks,
              "recommended_corrections": corrections}
    v = validate_output("QAResult", result)
    r = spend(r, steps=1)
    return {"run": finish(r, why="qa " + verdict["state"]),
            "result": result, "valid": v,
            "verdict": verdict,
            "why": (str(len(checks)) + " deterministic check(s) ran with "
                    "no model at all; " + str(len(judged)) + " needed "
                    "judgement. " + _s(verdict.get("why"))[:200])}


def _brand_checks(blocks, brand) -> List[Dict]:
    """Forbidden and required terms. Deterministic where it can be."""
    b = _d(brand)
    forbidden = [_s(x).lower() for x in _l(b.get("forbidden_terms"))]
    text = " ".join(_s(_d(x).get("text")) for x in _l(blocks)).lower()
    hits = [w for w in forbidden if w and w in text]
    out = [{"check": "forbidden_terms",
            "state": "FAIL" if hits else "PASS",
            "hits": hits,
            "why": ("uses forbidden term(s): " + ", ".join(hits)) if hits
            else "no forbidden term appears"}]
    if not b:
        out.append({"check": "brand_tone", "state": "WARNING",
                    "why": ("no brand profile is configured, so tone was "
                            "not checked. This is a gap in Settings, not "
                            "a problem with the content.")})
    return out


def _fix_for(check) -> str:
    c = _s(_d(check).get("check"))
    table = {
        "required_blocks": "add the missing block(s) before review",
        "cta": "add a CTA block; the reader is not being asked anything",
        "claims": ("attach an evidence_ref to each claim, or soften the "
                   "wording until it is not a claim"),
        "links": "correct the malformed link(s)",
        "assets": "generate or upload the referenced asset",
        "forbidden_terms": "remove the forbidden term(s)",
        "brand_tone": "configure the brand profile in Settings",
    }
    return table.get(c, "review this manually")


# ===========================================================================
# AGENT 4 - PERFORMANCE (sections 68, 72, 98)
# ===========================================================================
def performance_run(variants, *, metric="ctr", baseline=None,
                    attribute="hook", run=None, at="") -> Dict[str, Any]:
    """Results to learning. It cannot create or publish anything.

    Section 68 is explicit that this agent has no route to content
    creation, and section 70 that it may not call something a winner on
    its own. So it classifies through the deterministic classifier and
    reports FACT, INFERENCE and RECOMMENDATION separately.
    """
    r = run or new_run("PERFORMANCE", "learn from results", at=at)
    for forbidden in ("write_blocks", "distribute_content"):
        if guard("PERFORMANCE", forbidden)["ok"]:
            return {"run": finish(r, state="REFUSED",
                                  why="permission model is wrong"),
                    "why": ("the Performance agent must not be able to "
                            "write content. Refusing to run rather than "
                            "trusting a broken permission table.")}
    rows = [_d(v) for v in _l(variants)]
    if not rows:
        return {"run": finish(r, state="DONE", why="nothing to read"),
                "learning": None,
                "why": "no variant has returned performance yet"}
    groups: Dict[str, List[Dict]] = {}
    for v in rows:
        key = _s(_d(v.get("attributes")).get(attribute)) or "UNCLASSIFIED"
        groups.setdefault(key, []).append(v)
    facts, learnings = [], []
    for key, members in groups.items():
        vals = []
        for m in members:
            tot = FOS.aggregate(_l(m.get("performance")))
            val = tot.get(metric)
            if val is not None:
                vals.append(val)
            cls = FOS.classify_result(tot, metric=metric,
                                      baseline=baseline)
            m["result"] = cls
        if not vals:
            continue
        lr = FOS.make_learning(attribute_type=attribute,
                               attribute_value=key,
                               channel=_s(members[0].get("channel")),
                               metric=metric, values=vals,
                               baseline=baseline)
        if lr.get("status") == "ACTIVE":
            learnings.append(lr)
            facts.append(claim("FACT",
                               (_s(attribute) + " '" + key + "' averaged "
                                + _s(lr["performance_value"]) + " "
                                + _s(metric) + " across "
                                + _s(lr["sample_size"]) + " item(s)"),
                               evidence={"performance_id": _s(key)}))
    best = sorted(learnings,
                  key=lambda x: -(_f(x.get("lift"), 0) or 0))[:1]
    inference, recommendation = [], []
    if best:
        b = best[0]
        if _s(b.get("confidence")) == "LOW":
            inference.append(claim("INFERENCE",
                                   (_s(b["attribute_value"]) + " looks "
                                    "stronger, but on only "
                                    + _s(b["sample_size"]) + " item(s) "
                                    "that is a hint, not a pattern")))
        else:
            inference.append(claim("INFERENCE",
                                   (_s(b["attribute_value"]) + " appears "
                                    "effective for this channel and "
                                    "audience")))
            recommendation.append(claim("RECOMMENDATION",
                                        ("test 3 new "
                                         + _s(b["attribute_value"])
                                         + " variants next cycle")))
    r = spend(r, steps=1)
    v = (validate_output("ContentLearning", learnings[0])
         if learnings else {"ok": False, "why": "no learning produced"})
    return {"run": finish(r, why=str(len(learnings)) + " learning(s)"),
            "learning": learnings, "valid": v,
            "classified": [{"variant": _s(x.get("id")),
                            "result": _d(x.get("result")).get("result"),
                            "why": _d(x.get("result")).get("why")}
                           for x in rows],
            "facts": facts, "inferences": inference,
            "recommendations": recommendation,
            "why": ("facts, inferences and recommendations are kept "
                    "apart. A fact points at measured rows; an inference "
                    "is this agent's reading of them; a recommendation is "
                    "a suggestion a human accepts or ignores.")}


# ===========================================================================
# 74. THE ORCHESTRATOR. Deterministic on purpose.
# ===========================================================================
#: event -> what happens next. A table, not a decision. Reading this tells
#: you the whole workflow, which is the point.
WORKFLOW = (
    ("signal.accepted", "planner.run", "plan_created"),
    ("plan.approved", "brief.build", "brief_created"),
    ("brief.created", "creator.run", "draft_created"),
    ("draft.ready", "qa.run", "qa_complete"),
    ("qa.complete", "human.review", "awaiting_approval"),
    ("human.approved", "distribution.package", "package_ready"),
    ("package.accepted", "wait.performance", "awaiting_performance"),
    ("performance.received", "performance.run", "learning_created"),
    ("learning.created", "planner.receives", "loop_closed"),
)

#: The two places a human MUST act. Not configurable to zero in the MVP.
HUMAN_GATES = ("plan.approved", "human.approved")


def next_step(event) -> Dict[str, Any]:
    """What follows this event. No reasoning, one lookup."""
    e = _s(event).lower()
    for ev, action, result in WORKFLOW:
        if ev == e:
            return {"ok": True, "event": ev, "action": action,
                    "produces": result,
                    "human_gate": ev in HUMAN_GATES,
                    "why": ("a table lookup, not a decision. An "
                            "orchestrator that reasoned here would be a "
                            "fifth agent whose choices nobody can "
                            "reproduce.")}
    return {"ok": False, "event": e,
            "why": ("'" + e + "' is not an event in this workflow. It is "
                    "not guessed at.")}


def workflow_map() -> List[Dict[str, Any]]:
    return [{"event": e, "action": a, "produces": p,
             "human_gate": e in HUMAN_GATES} for e, a, p in WORKFLOW]
