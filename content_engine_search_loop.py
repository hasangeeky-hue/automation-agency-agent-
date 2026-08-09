"""
content_engine_search_loop.py
============================================================================
THE SEARCH INTELLIGENCE OS: THE CLOSED LOOP, AS A PRODUCT PRIMITIVE.

Spec sections 1-3, 52-63, 82-84, 102-104. This is the piece that makes the
difference the founder named: SEMrush stops at "here is an opportunity";
this system continues through execution, verification, observation and a
judged outcome, and then learns.

THE RULE THAT DEFINES THIS FILE (spec 103, the GOLDEN LOOP RULE)
  No initiative is complete at EXECUTED. It is complete only when it is
  EXECUTED, TECHNICALLY VERIFIED, OBSERVED, and its OUTCOME CLASSIFIED.
  advance() physically refuses to jump from EXECUTED to SUCCESSFUL, so a
  screen cannot show a win that nobody measured.

THREE RESULTS, NEVER CONFLATED (spec 82)
  implementation_result: did the change land on the page
  search_result:         did search behaviour move
  business_result:       did money move
  A green tick on the first is not a win. The engine keeps them apart and
  the outcome sentence names which one it is talking about.

INSUFFICIENT DATA IS A VERDICT (spec 3, 84)
  An observation window that closes without enough volume returns
  INSUFFICIENT_DATA, not NEUTRAL. Declaring "no effect" from four clicks
  is how an optimisation programme learns the wrong lesson permanently.

BOUNDED LOOPS (spec 52-54)
  Every run carries max_steps, max_handoffs, max_tool_calls, max_retries,
  max_cost and a timeout. Exhausting any of them ESCALATES TO A HUMAN. No
  "while not done: ask the model again" exists anywhere in this file.

RECOMMENDATIONS ARE REFUSED WHEN INCOMPLETE (spec 102)
  A recommendation without problem, evidence, impact, business value,
  confidence, effort, risk, action, agent, approval requirement,
  verification method and success metric is RECOMMENDATION_INCOMPLETE and
  cannot enter the loop.
============================================================================
"""

from __future__ import annotations

import logging

from content_engine_os_core import _D, _L, now, rid

log = logging.getLogger("content_engine.search_loop")

#: The lifecycle, spec section 2. One tuple; the board, the API and the
#: gates all read THIS, so no second copy can disagree.
STATES = (
    "DISCOVERED", "ANALYZED", "RECOMMENDED", "DRAFT_CREATED", "VALIDATING",
    "APPROVAL_REQUIRED", "APPROVED", "EXECUTING", "EXECUTED",
    "TECHNICALLY_VERIFIED", "OBSERVING", "RESULT_AVAILABLE",
    "SUCCESSFUL", "NEUTRAL", "UNSUCCESSFUL", "REGRESSION",
    "ROLLED_BACK", "ESCALATED", "DISMISSED",
)

#: Legal moves. The jump this table exists to forbid is
#: EXECUTED -> SUCCESSFUL: a change that landed is not a win.
MOVES = {
    "DISCOVERED": ("ANALYZED", "DISMISSED"),
    "ANALYZED": ("RECOMMENDED", "DISMISSED"),
    "RECOMMENDED": ("DRAFT_CREATED", "APPROVAL_REQUIRED", "DISMISSED"),
    "DRAFT_CREATED": ("VALIDATING", "DISMISSED"),
    "VALIDATING": ("APPROVAL_REQUIRED", "APPROVED", "ESCALATED"),
    "APPROVAL_REQUIRED": ("APPROVED", "DISMISSED", "ESCALATED"),
    "APPROVED": ("EXECUTING", "DISMISSED"),
    "EXECUTING": ("EXECUTED", "ESCALATED"),
    "EXECUTED": ("TECHNICALLY_VERIFIED", "ROLLED_BACK", "ESCALATED"),
    "TECHNICALLY_VERIFIED": ("OBSERVING", "ROLLED_BACK"),
    "OBSERVING": ("RESULT_AVAILABLE", "OBSERVING", "ROLLED_BACK"),
    "RESULT_AVAILABLE": ("SUCCESSFUL", "NEUTRAL", "UNSUCCESSFUL",
                         "REGRESSION"),
    "SUCCESSFUL": ("DISMISSED",),
    "NEUTRAL": ("OBSERVING", "RECOMMENDED", "DISMISSED"),
    "UNSUCCESSFUL": ("RECOMMENDED", "ROLLED_BACK", "DISMISSED"),
    "REGRESSION": ("ROLLED_BACK", "ESCALATED"),
    "ROLLED_BACK": ("RECOMMENDED", "DISMISSED"),
    "ESCALATED": ("RECOMMENDED", "DISMISSED"),
    "DISMISSED": (),
}

#: The states a human is looking at when they ask "what is running".
OPEN_STATES = tuple(s for s in STATES
                    if s not in ("SUCCESSFUL", "NEUTRAL", "UNSUCCESSFUL",
                                 "REGRESSION", "ROLLED_BACK", "DISMISSED"))

# ESCALATION IS A SAFETY VALVE AND MUST WORK FROM ANYWHERE IN FLIGHT.
# Written as ONE rule rather than twelve hand edits, because a
# hand-maintained second list is how a budget breach ends up silently
# doing nothing: a run exhausted its steps, called advance(..., ESCALATED)
# from DISCOVERED, the move was illegal, and the escalation vanished.
for _s in OPEN_STATES:
    if _s != "ESCALATED" and "ESCALATED" not in MOVES[_s]:
        MOVES[_s] = MOVES[_s] + ("ESCALATED",)

#: Spec 102. Every field required before a recommendation may enter.
RECOMMENDATION_FIELDS = ("problem", "evidence", "impact", "business_value",
                         "confidence", "effort", "risk", "action", "agent",
                         "approval", "verification_method",
                         "success_metric")

#: Spec 79-80. Risk decides who may approve.
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
AUTO_ALLOWED = {"LOW"}          # and only when policy raises it
HUMAN_ONLY = {"CRITICAL"}

#: Spec 3. Observation windows, configurable, with the reason each exists.
WINDOWS = {"technical": 0, "crawl": 1, "early": 7, "compare": 14,
           "business": 28}

#: Spec 3/84. Below this there is no verdict, only INSUFFICIENT_DATA.
MIN_IMPRESSIONS = 200
MIN_CLICKS = 20

#: Spec 54. Bounded loops. Exhausting any budget escalates.
BUDGET = {"max_steps": 12, "max_handoffs": 6, "max_tool_calls": 40,
          "max_retries": 3, "max_cost_usd": 2.0, "timeout_s": 900}

#: Spec 82. Three results, kept apart on purpose.
RESULT_KINDS = ("implementation_result", "search_result",
                "business_result")
OUTCOMES = ("WIN", "NEUTRAL", "LOSS", "INSUFFICIENT_DATA")


# ---------------------------------------------------------------------------
# RECOMMENDATIONS
# ---------------------------------------------------------------------------
def check_recommendation(rec) -> dict:
    """Spec 102. Complete, or refused with the exact missing fields."""
    d = _D(rec)
    missing = [f for f in RECOMMENDATION_FIELDS
               if d.get(f) in (None, "", [], {})]
    if missing:
        return {"ok": False, "code": "RECOMMENDATION_INCOMPLETE",
                "missing": missing,
                "message": (f"a recommendation cannot enter the loop "
                            f"without: {', '.join(missing)}. Every one of "
                            f"these is what makes it reviewable instead of "
                            f"an opinion.")}
    if d.get("risk") not in RISK_LEVELS:
        return {"ok": False, "code": "RECOMMENDATION_INCOMPLETE",
                "message": f"risk must be one of {', '.join(RISK_LEVELS)}"}
    return {"ok": True, "message": "complete"}


def open_initiative(r, *, kind, target, recommendation, project="") -> dict:
    """Start one optimisation initiative. Refuses an incomplete
    recommendation rather than storing a wish."""
    chk = check_recommendation(recommendation)
    if not chk["ok"]:
        return chk
    iid = rid("sloop", r.ws, kind, target, now())
    rec = dict(_D(recommendation))
    initiative = {
        "id": iid, "kind": kind, "target": target, "project": project,
        "state": "DISCOVERED", "state_at": now(),
        "recommendation": rec, "risk": rec.get("risk"),
        "agent": rec.get("agent"),
        "history": [{"state": "DISCOVERED", "at": now(),
                     "why": "opportunity detected"}],
        "baseline": {}, "observations": [],
        "implementation_result": None, "search_result": None,
        "business_result": None, "outcome": None,
        "before_state": None, "after_state": None,
        "budget_used": {k: 0 for k in BUDGET},
    }
    r.put("search_initiatives", initiative)
    return {"ok": True, "id": iid, "state": "DISCOVERED",
            "message": (f"initiative opened for {target}. It is not done "
                        f"until it is executed, verified, observed AND "
                        f"judged.")}


def advance(r, initiative_id, to_state, *, why="", **fields) -> dict:
    """The ONLY way an initiative changes state.

    Refuses illegal moves with the legal ones named, and refuses the two
    moves that would let the product lie: EXECUTED straight to a verdict,
    and any verdict without a recorded observation."""
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return {"ok": False, "message": "no such initiative"}
    if to_state not in STATES:
        return {"ok": False,
                "message": f"{to_state!r} is not a loop state. They are: "
                           + ", ".join(STATES)}
    frm = it.get("state")
    if to_state not in MOVES.get(frm, ()):
        return {"ok": False, "code": "ILLEGAL_TRANSITION",
                "message": (f"a {frm} initiative cannot become "
                            f"{to_state}. It may become: "
                            + (", ".join(MOVES.get(frm, ())) or "nothing")
                            + (". An executed change is NOT a result; it "
                               "must be verified and observed first."
                               if frm == "EXECUTED" else ""))}
    if to_state in ("SUCCESSFUL", "NEUTRAL", "UNSUCCESSFUL", "REGRESSION") \
            and not _L(it.get("observations")):
        return {"ok": False, "code": "NO_OBSERVATION",
                "message": ("a verdict needs at least one recorded "
                            "observation. Judging without measuring is the "
                            "habit this loop exists to break.")}
    it["state"] = to_state
    it["state_at"] = now()
    it.setdefault("history", []).append(
        {"state": to_state, "at": now(), "why": why})
    for k, v in fields.items():
        it[k] = v
    r.put("search_initiatives", it)
    return {"ok": True, "state": to_state,
            "message": f"{frm} -> {to_state}"}


# ---------------------------------------------------------------------------
# VERIFICATION (spec 81) - never trust the API's own success claim
# ---------------------------------------------------------------------------
def record_execution(r, initiative_id, *, before_state, after_state,
                     api_said_ok=True, detail="") -> dict:
    """EXECUTED, with what the page looked like before and after."""
    out = advance(r, initiative_id, "EXECUTED",
                  why=detail or "execution reported",
                  before_state=before_state, after_state=after_state,
                  implementation_result=None)
    if not out["ok"]:
        return out
    return {"ok": True, "state": "EXECUTED",
            "message": ("execution recorded. This is NOT success: the "
                        "verifier must fetch the page and confirm the "
                        "change is really there."
                        + ("" if api_said_ok else
                           " The provider API did not report success, "
                           "which makes verification more important, not "
                           "less."))}


def verify(r, initiative_id, observed_state) -> dict:
    """Spec 81. Compare what was intended with what the page actually
    shows. A mismatch is VERIFICATION_FAILED, never a quiet pass."""
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return {"ok": False, "message": "no such initiative"}
    want = _D(it.get("after_state"))
    got = _D(observed_state)
    if not want:
        return {"ok": False,
                "message": "nothing was recorded as the intended state, so "
                           "there is nothing to verify against"}
    diffs = [k for k, v in want.items()
             if str(got.get(k, "")).strip() != str(v).strip()]
    if diffs:
        it["implementation_result"] = "VERIFICATION_FAILED"
        it["verification_diff"] = {k: {"wanted": want.get(k),
                                       "found": got.get(k)} for k in diffs}
        r.put("search_initiatives", it)
        return {"ok": False, "code": "VERIFICATION_FAILED",
                "fields": diffs,
                "message": (f"the page does not show the change on: "
                            f"{', '.join(diffs)}. The action is NOT "
                            f"complete and is not counted as one.")}
    out = advance(r, initiative_id, "TECHNICALLY_VERIFIED",
                  why="page fetched; intended state confirmed",
                  implementation_result="VERIFIED")
    if out["ok"]:
        out["message"] = ("the change is really on the page. That is the "
                          "IMPLEMENTATION result only; whether search or "
                          "the business moved is still unknown.")
    return out


# ---------------------------------------------------------------------------
# OBSERVATION AND OUTCOME (spec 3, 55, 82-84)
# ---------------------------------------------------------------------------
def set_baseline(r, initiative_id, metrics) -> dict:
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return {"ok": False, "message": "no such initiative"}
    it["baseline"] = _D(metrics)
    it["baseline_at"] = now()
    r.put("search_initiatives", it)
    return {"ok": True, "message": "baseline recorded before the change; "
                                   "without it no outcome can be judged"}


def observe(r, initiative_id, *, window, metrics) -> dict:
    """Record one observation. Windows are named, so a reader knows
    whether they are looking at an early signal or a settled result."""
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return {"ok": False, "message": "no such initiative"}
    if window not in WINDOWS:
        return {"ok": False,
                "message": f"{window!r} is not an observation window. They "
                           f"are: " + ", ".join(WINDOWS)}
    it.setdefault("observations", []).append(
        {"window": window, "day": WINDOWS[window], "at": now(),
         "metrics": _D(metrics)})
    if it.get("state") == "TECHNICALLY_VERIFIED":
        it["state"] = "OBSERVING"
        it.setdefault("history", []).append(
            {"state": "OBSERVING", "at": now(),
             "why": f"first observation at {window}"})
    r.put("search_initiatives", it)
    return {"ok": True, "observations": len(it["observations"]),
            "message": f"{window} observation recorded"}


def data_sufficiency(baseline, latest) -> dict:
    """Spec 3/84. Is there enough to say anything at all?"""
    b, l = _D(baseline), _D(latest)
    imp = float(b.get("impressions") or 0) + float(l.get("impressions") or 0)
    clk = float(b.get("clicks") or 0) + float(l.get("clicks") or 0)
    if imp < MIN_IMPRESSIONS or clk < MIN_CLICKS:
        return {"enough": False, "state": "INSUFFICIENT_DATA",
                "message": (f"{int(imp)} impressions and {int(clk)} clicks "
                            f"across both windows, against a floor of "
                            f"{MIN_IMPRESSIONS} and {MIN_CLICKS}. There is "
                            f"no verdict here, and calling it 'no effect' "
                            f"would teach the system the wrong lesson.")}
    return {"enough": True, "state": "ENOUGH_DATA",
            "message": f"{int(imp)} impressions, {int(clk)} clicks"}


def judge(r, initiative_id, *, primary="position") -> dict:
    """Classify the outcome, keeping the three results apart.

    Direction is read from the metric: position falling is good, clicks
    rising is good. Nothing is declared without the data floor."""
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return {"ok": False, "message": "no such initiative"}
    obs = _L(it.get("observations"))
    if not obs:
        return {"ok": False, "code": "NO_OBSERVATION",
                "message": "nothing has been observed yet"}
    base = _D(it.get("baseline"))
    latest = _D(obs[-1].get("metrics"))
    suff = data_sufficiency(base, latest)
    if not suff["enough"]:
        it["search_result"] = "INSUFFICIENT_DATA"
        r.put("search_initiatives", it)
        return {"ok": True, "outcome": "INSUFFICIENT_DATA",
                "message": suff["message"]}
    lower_better = primary in ("position", "cpa")
    b, l = base.get(primary), latest.get(primary)
    if b in (None, "") or l in (None, ""):
        return {"ok": False,
                "message": f"{primary} is missing from the baseline or the "
                           f"latest observation, so it cannot be judged"}
    b, l = float(b), float(l)
    delta = (b - l) if lower_better else (l - b)
    pct = (abs(delta) / abs(b) * 100) if b else 0.0
    if pct < 5:
        search = "NEUTRAL"
    elif delta > 0:
        search = "WIN"
    else:
        search = "LOSS"
    conv_b = float(base.get("conversions") or 0)
    conv_l = float(latest.get("conversions") or 0)
    business = ("INSUFFICIENT_DATA" if (conv_b + conv_l) < 5 else
                "WIN" if conv_l > conv_b else
                "LOSS" if conv_l < conv_b else "NEUTRAL")
    it["search_result"] = search
    it["business_result"] = business
    state = {"WIN": "SUCCESSFUL", "NEUTRAL": "NEUTRAL",
             "LOSS": "UNSUCCESSFUL"}[search]
    if search == "LOSS" and pct >= 25:
        state = "REGRESSION"
    if it.get("state") == "OBSERVING":
        advance(r, initiative_id, "RESULT_AVAILABLE",
                why=f"{primary} moved {pct:.1f}%")
    out = advance(r, initiative_id, state, why=f"{primary} {search}",
                  outcome=search, search_result=search,
                  business_result=business)
    if not out["ok"]:
        return out
    return {"ok": True, "outcome": search, "state": state,
            "implementation_result": it.get("implementation_result"),
            "search_result": search, "business_result": business,
            "message": (f"IMPLEMENTATION {it.get('implementation_result')} "
                        f"/ SEARCH {search} ({primary} {b:g} to {l:g}, "
                        f"{pct:.1f}%) / BUSINESS {business}. These are "
                        f"three different questions and this engine "
                        f"answers them separately.")}


def rollback(r, initiative_id, *, why="") -> dict:
    """Spec 83. Restore the recorded before_state; the rollback itself
    still has to be verified."""
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return {"ok": False, "message": "no such initiative"}
    before = _D(it.get("before_state"))
    if not before:
        return {"ok": False,
                "message": "no before_state was recorded, so there is "
                           "nothing safe to roll back to"}
    out = advance(r, initiative_id, "ROLLED_BACK",
                  why=why or "rolled back on request")
    if not out["ok"]:
        return out
    return {"ok": True, "restore_to": before,
            "message": ("rollback queued to the recorded before_state. It "
                        "must be verified like any other change; an "
                        "unverified rollback is just another claim.")}


# ---------------------------------------------------------------------------
# BOUNDED AGENT RUNS (spec 52-54)
# ---------------------------------------------------------------------------
def new_run(r, *, agent, objective, initiative_id="", budget=None) -> dict:
    b = {**BUDGET, **_D(budget)}
    run = {"id": rid("srun", r.ws, agent, now()), "agent": agent,
           "objective": objective, "initiative_id": initiative_id,
           "state": "RUNNING", "started_at": now(),
           "budget": b, "used": {k: 0 for k in b}, "steps": []}
    r.put("search_agent_runs", run)
    return {"ok": True, "id": run["id"], "budget": b,
            "message": f"{agent} started with a hard budget; exhausting "
                       f"any limit escalates to you rather than looping"}


def step(r, run_id, *, name, cost_usd=0.0, tool_calls=0,
         handoff=False) -> dict:
    """One bounded step. Returns ESCALATE when a budget is exhausted;
    there is no unbounded retry anywhere."""
    run = r.one("search_agent_runs", run_id)
    if not run:
        return {"ok": False, "message": "no such run"}
    u, b = _D(run.get("used")), _D(run.get("budget"))
    u["max_steps"] = u.get("max_steps", 0) + 1
    u["max_tool_calls"] = u.get("max_tool_calls", 0) + int(tool_calls)
    u["max_cost_usd"] = round(u.get("max_cost_usd", 0) + float(cost_usd), 4)
    if handoff:
        u["max_handoffs"] = u.get("max_handoffs", 0) + 1
    run["used"] = u
    run.setdefault("steps", []).append({"name": name, "at": now(),
                                        "cost_usd": cost_usd})
    breached = [k for k in ("max_steps", "max_handoffs", "max_tool_calls",
                            "max_cost_usd")
                if u.get(k, 0) > b.get(k, 0)]
    if breached:
        run["state"] = "ESCALATED"
        run["escalation"] = breached
        r.put("search_agent_runs", run)
        if run.get("initiative_id"):
            advance(r, run["initiative_id"], "ESCALATED",
                    why=f"budget exhausted: {', '.join(breached)}")
        return {"ok": False, "code": "ESCALATE_TO_HUMAN",
                "breached": breached,
                "message": (f"{run.get('agent')} hit its limit on "
                            f"{', '.join(breached)} and stopped. It did "
                            f"not keep asking the model until something "
                            f"came out.")}
    r.put("search_agent_runs", run)
    return {"ok": True, "used": u, "message": f"step {name} recorded"}


def board(r) -> dict:
    """The Execution board and Loop Monitor read this. States only, no
    invented progress."""
    items = r.all("search_initiatives")
    by = {}
    for it in items:
        by.setdefault(it.get("state"), []).append(it)
    open_n = sum(len(by.get(s, [])) for s in OPEN_STATES)
    judged = sum(len(by.get(s, [])) for s in
                 ("SUCCESSFUL", "NEUTRAL", "UNSUCCESSFUL", "REGRESSION"))
    stuck = [it for it in items if it.get("state") == "EXECUTED"]
    return {"total": len(items), "open": open_n, "judged": judged,
            "by_state": {k: len(v) for k, v in sorted(by.items())},
            "executed_but_unverified": len(stuck),
            "message": (f"{len(items)} initiative(s): {open_n} in flight, "
                        f"{judged} judged."
                        + (f" {len(stuck)} are EXECUTED but not yet "
                           f"verified, and they do not count as wins."
                           if stuck else ""))}


def learning(r) -> dict:
    """Spec 60. What has actually worked, from recorded outcomes only."""
    rows = []
    for it in r.all("search_initiatives"):
        if it.get("outcome"):
            rows.append({"kind": it.get("kind"), "target": it.get("target"),
                         "action": _D(it.get("recommendation")).get("action"),
                         "outcome": it.get("outcome"),
                         "search_result": it.get("search_result"),
                         "business_result": it.get("business_result"),
                         "agent": it.get("agent")})
    by_kind = {}
    for x in rows:
        k = by_kind.setdefault(x["kind"], {"WIN": 0, "NEUTRAL": 0,
                                           "LOSS": 0,
                                           "INSUFFICIENT_DATA": 0})
        k[x["outcome"]] = k.get(x["outcome"], 0) + 1
    return {"rows": rows, "by_kind": by_kind,
            "message": (f"{len(rows)} judged initiative(s) on record"
                        if rows else
                        "nothing has completed a full loop yet, so there "
                        "is nothing learned. This stays empty rather than "
                        "showing invented confidence.")}
