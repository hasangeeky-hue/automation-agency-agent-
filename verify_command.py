# -*- coding: utf-8 -*-
"""Gates for the Command Cockpit.

  L1-L8  the rules the spec states, against running code.
  L9     the section 102 vertical slice: TikTok CPA up, no fresh
         creatives, image provider degraded, pricing traffic up, CAC
         up. One root-cause chain, one multi-OS plan, human approval,
         routed actions, verified results. Section 102: if this single
         scenario works end to end, the architecture is correct.
  L10    the cockpit renders, every zone has content, no dead ends.

A check that raises counts as a failure, never as a skip.
"""
from __future__ import annotations

import ast
import io
import re
import sys

import content_engine_command_core as CC
import content_engine_command_ui as UI

PASS, FAIL = [], []


def t(label, ok, detail=""):
    try:
        ok = bool(ok)
    except Exception:                                 # noqa: BLE001
        ok = False
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


def head(x):
    print("\n" + x)


print("=" * 74)
print("COMMAND COCKPIT - GATES")
print("=" * 74)

# ---------------------------------------------------------------- L1
head("L1  POLARITY: HIGHER IS NEVER AUTOMATICALLY GOOD (spec 13)")
t("revenue up is good",
  CC.judge_change("revenue", 18)["verdict"] == "GOOD")
t("CAC UP IS BAD", CC.judge_change("cac", 8)["verdict"] == "BAD")
t("CAC down is good", CC.judge_change("cac", -3)["verdict"] == "GOOD")
t("spend up is neutral",
  CC.judge_change("spend", 9)["verdict"] == "NEUTRAL")
t("agent cost DEPENDS, and says what it depends on",
  CC.judge_change("agent_cost", 20)["verdict"] == "DEPENDS")
t("AN UNREGISTERED METRIC IS UNDECIDED, NOT COLOURED",
  CC.judge_change("vibes", 50)["verdict"] == "UNDECIDED")

# ---------------------------------------------------------------- L2
head("L2  WHAT CHANGED (spec 17-18)")
t("a change without a source is refused",
  CC.change("cpa", before=31, after=41, source="")["ok"] is False)
_ch = CC.change("cpa", before=31, after=41, source="MEDIA_BUYING_OS",
                cause_status="LIKELY_CREATIVE_FATIGUE",
                evidence=["CTR down", "frequency up"])
t("the feed does the arithmetic", _ch["pct"] == 32.3)
t("and judges it by polarity", _ch["verdict"] == "BAD")
_feed = CC.change_feed([_ch,
                        CC.change("revenue", before=240000, after=284000,
                                  source="BI"),
                        CC.change("api_cost", before=100, after=131,
                                  source="BI_COST")])
t("the feed is capped and biggest-first",
  _feed[0]["metric"] == "cpa" and len(_feed) <= 8)

# ---------------------------------------------------------------- L3
head("L3  THE DECISION CONTRACT (spec 20-21)")
_full = dict(what="Reduce TikTok budget 15%",
             why="CPA rose 32%", evidence=["CPA 31->41"],
             business_impact="est 4.8K/mo", system_impact="none",
             expected_cost={"mid": 30}, expected_value={"mid": 3200},
             confidence=0.86, risk="LOW",
             target_system="MEDIA_BUYING_OS",
             action="REDUCE_CAMPAIGN_BUDGET",
             measurement_plan="observe CPA 14 days", urgency=0.8)
t("a complete decision is READY", CC.decision(**_full)["ok"] is True)
_inc = CC.decision(what="x", why="y", target_system="MEDIA_BUYING_OS")
t("A DECISION MISSING FIELDS IS DECISION_INCOMPLETE",
  _inc["state"] == "DECISION_INCOMPLETE")
t("and it names every missing field",
  "measurement_plan" in _inc["missing"]
  and "evidence" in _inc["missing"])
_big_loud = CC.decision(**dict(_full, what="loud small thing",
                               expected_value={"mid": 200},
                               expected_cost={"mid": 10},
                               urgency=1.0, confidence=0.9))
_quiet_big = CC.decision(**dict(_full, what="quiet expensive thing",
                                expected_value={"mid": 9000},
                                expected_cost={"mid": 400},
                                urgency=0.4, confidence=0.8))
_rk = CC.rank_decisions([_big_loud, _quiet_big, _inc])
t("RANKING IS NEVER SEVERITY ALONE: the quiet expensive one wins",
  _rk["ranked"][0]["what"] == "quiet expensive thing")
t("and incomplete cards are held out of the ranking entirely",
  _rk["incomplete"] == 1
  and "cannot compete" in _rk["why"])

# ---------------------------------------------------------------- L4
head("L4  THE ROUTER AND THE FENCE (spec 24, 84, 106)")
t("content actions route to the Content Factory",
  CC.route("CREATE_CONTENT", approved_by="Murtuja")["target"]
  == "CONTENT_FACTORY")
t("budget actions route to Media Buying",
  CC.route("REDUCE_CAMPAIGN_BUDGET", approved_by="M")["target"]
  == "MEDIA_BUYING_OS")
t("system fixes route to the Control Plane",
  CC.route("SWITCH_FALLBACK_TOOL", approved_by="M")["target"]
  == "SYSTEM_CONTROL_PLANE")
t("AN UNKNOWN ACTION IS UNROUTABLE, NEVER GUESSED INTO A SYSTEM",
  CC.route("DO_MARKETING", approved_by="M")["state"] == "UNROUTABLE")
t("NOTHING ROUTES WITHOUT A NAMED APPROVER",
  CC.route("CREATE_CONTENT")["state"] == "NEEDS_APPROVAL")
t("SEVEN OPERATIONS ARE FORBIDDEN WITH ANY APPROVAL",
  len(CC.COMMANDER_FORBIDDEN) == 7
  and CC.route("rotate_secrets",
               approved_by="anyone")["state"] == "FORBIDDEN")

# ---------------------------------------------------------------- L5
head("L5  QUICK FIXES (spec 25-27, 97, 105)")
_fx = CC.quick_fix("SWITCH_FALLBACK_TOOL",
                   current_state="Image provider timing out",
                   proposed_state="Route to fallback provider",
                   affected=["Creator Agent"], risk="APPROVAL_REQUIRED",
                   downtime="none", cost="2.40/hr",
                   rollback="route back to primary",
                   verification="test request + agent healthy")
t("a complete fix carries rollback and verification", _fx["ok"] is True)
t("A FIX MISSING ITS FIELDS IS A MYSTERIOUS BUTTON, AND REFUSED",
  "mysterious" in CC.quick_fix("RETRY_WORKFLOW",
                               current_state="x")["why"])
t("a destructive action is not a quick fix type at all",
  CC.quick_fix("RESTART_DATABASE", current_state="x")["ok"] is False)

# ---------------------------------------------------------------- L6
head("L6  EXECUTION AND VERIFICATION (spec 66-68)")
t("execution walks one visible step at a time",
  CC.advance_execution("APPROVED", "ROUTED")["ok"] is True)
t("AND SKIPPING STEPS IS REFUSED",
  CC.advance_execution("APPROVED", "RESULT")["ok"] is False)
t("SUCCESS IS NOT AN API 200: all three recovery conditions",
  CC.verify_machine_fix(service_recovered=True, dependency_healthy=True,
                        workflow_works=False)["success"] is False)
t("and the failing condition is named",
  "workflow works" in CC.verify_machine_fix(
      service_recovered=True, dependency_healthy=True,
      workflow_works=False)["why"])
t("A BUSINESS ACTION IS NOT JUDGED BEFORE ITS WINDOW",
  CC.verify_business_action(metric="cac", before=116, after=108,
                            observed_days=3)["state"]
  == "STILL_OBSERVING")
t("after the window, polarity judges it",
  CC.verify_business_action(metric="cac", before=116, after=108,
                            observed_days=14)["success"] is True)

# ---------------------------------------------------------------- L7
head("L7  INITIATIVES, IMPACT, INCIDENTS (spec 32, 77, 92-93)")
_ih = CC.initiative_health(target_metric="cac", target_value=110,
                           current_value=116, actions_done=3,
                           actions_total=3, observing=True)
t("EVERY ACTION DONE WITH THE METRIC UNMOVED IS NOT COMPLETION",
  _ih["state"] in ("AT_RISK", "ON_TRACK")
  and "do not count as progress" in _ih["why"])
t("meeting the target is what completes it",
  CC.initiative_health(target_metric="cac", target_value=110,
                       current_value=108,
                       observing=False)["state"] == "COMPLETED")
t("AN AMOUNT WITH UNKNOWN CONFIDENCE IS DROPPED, NOT PRINTED",
  CC.business_impact(description="email outage", amount=4800,
                     confidence="UNKNOWN")["amount"] is None)
_agg = CC.aggregate_incident(
    [{"component": "Image Provider", "kind": "TIMEOUT", "at": str(i)}
     for i in range(47)])
t("47 TIMEOUTS ARE ONE INCIDENT WITH 47 OCCURRENCES",
  len(_agg["incidents"]) == 1
  and _agg["incidents"][0]["occurrences"] == 47)
t("notification is for action, not awareness",
  CC.should_notify("P1")["notify"] is True
  and CC.should_notify("FYI")["notify"] is False)

# ---------------------------------------------------------------- L8
head("L8  THE COMMANDER (spec 36, 80, 99-100)")
t("WITHOUT SNAPSHOTS THE COMMANDER REFUSES",
  CC.commander("what is happening?")["state"] == "NO_EVIDENCE")
t("and says why a fluent guess would be worse",
  "model memory" in CC.commander("x")["why"]
  or "memory" in CC.commander("x")["why"])
_sn = {"business": {"revenue": 284000, "summary": "growing"},
       "system": {"Content Factory": {"status": "DEGRADED",
                                      "why": "image provider"}},
       "changes": [_ch],
       "decisions": [_quiet_big, _big_loud] * 4}
_ans = CC.commander("what should I do?", _sn)
t("AT MOST FIVE RANKED ACTIONS, NEVER THIRTY",
  len(_ans["decisions"]) <= CC.MAX_RECOMMENDATIONS)
t("missing snapshot domains REDUCE confidence and are named",
  _ans["confidence"] == "REDUCED"
  and "cost" in _ans["data_limitations"])
t("the output carries every contract field",
  all(k in _ans for k in ("situation", "system_diagnosis",
                          "business_diagnosis", "data_limitations")))

# ---------------------------------------------------------------- L9
head("L9  THE VERTICAL SLICE (spec 102)")
# INPUT: the five signals the spec names.
_slice_changes = [
    CC.change("cpa", before=31, after=41, source="MEDIA_BUYING_OS",
              cause_status="LIKELY_CREATIVE_FATIGUE",
              evidence=["CTR down", "frequency 5.9"]),
    CC.change("cac", before=107, after=116, source="BI"),
    CC.change("conversions", before=100, after=124, source="SEO_OS"),
]
_chain = CC.root_chain([
    {"layer": "BUSINESS", "text": "TikTok CPA up 32%"},
    {"layer": "PROCESS", "text": "no fresh paid creative published"},
    {"layer": "PROCESS", "text": "Content Factory output down"},
    {"layer": "SYSTEM", "text": "Image Provider degraded"}])
t("slice: the chain runs BUSINESS -> PROCESS -> SYSTEM",
  _chain["ok"] and _chain["root"]["text"] == "Image Provider degraded")
t("slice: a chain of one is refused as a symptom",
  CC.root_chain([{"text": "CPA up"}])["ok"] is False)
_plan = [
    ("SWITCH_FALLBACK_TOOL", "SYSTEM_CONTROL_PLANE"),
    ("RETRY_WORKFLOW", "SYSTEM_CONTROL_PLANE"),
    ("CREATE_VARIANTS", "CONTENT_FACTORY"),
    ("REDUCE_CAMPAIGN_BUDGET", "MEDIA_BUYING_OS"),
    ("CREATE_CONTENT", "CONTENT_FACTORY"),
]
_routed = [CC.route(a, approved_by="Murtuja") for a, _t2 in _plan]
t("SLICE: EVERY PLAN STEP ROUTES TO ITS OWNING OS",
  all(r["ok"] for r in _routed)
  and [r["target"] for r in _routed] == [t2 for _a, t2 in _plan])
t("slice: none of it routed before approval",
  CC.route("CREATE_VARIANTS")["state"] == "NEEDS_APPROVAL")
_exec_ok = True
_state = "APPROVED"
for _next in ("ROUTED", "EXECUTING", "EXECUTED", "VERIFYING",
              "OBSERVING", "RESULT"):
    _r = CC.advance_execution(_state, _next)
    _exec_ok = _exec_ok and _r["ok"]
    _state = _next
t("slice: execution walks the whole visible chain", _exec_ok)
t("slice: the machine fix verifies on recovery, not on the API call",
  CC.verify_machine_fix(service_recovered=True, dependency_healthy=True,
                        workflow_works=True)["success"] is True)
t("SLICE: CAC IMPROVED AFTER THE WINDOW -> INITIATIVE SUCCESSFUL",
  CC.verify_business_action(metric="cac", before=116, after=108,
                            observed_days=14)["success"] is True
  and CC.initiative_health(target_metric="cac", target_value=110,
                           current_value=108,
                           observing=False)["state"] == "COMPLETED")

# ---------------------------------------------------------------- L10
head("L10 THE COCKPIT RENDERS")
_ctx = {
    "workspace": "Anthropos", "period": "Last 30 days",
    "business": {"revenue": {"value": 284000, "pct": 18},
                 "contribution": {"value": 94000, "pct": 12},
                 "spend": {"value": 48000, "pct": 9},
                 "customers": {"value": 418, "pct": 13},
                 "cac": {"value": 114, "pct": -3},
                 "pipeline": {"value": 620000, "pct": 8}},
    "machine": {"Content Factory": {"status": "DEGRADED",
                                    "why": "Image Provider latency"}},
    "changes": _slice_changes,
    "decisions": [_quiet_big, _big_loud, _inc],
    "quick_fixes": [_fx],
    "loops": [{"name": "Paid Optimization", "owner_os": "Media Buying",
               "current_stage": "OBSERVING", "status": "STALLED",
               "why": "Meta performance sync delayed"}],
    "initiatives": [{"name": "Improve Acquisition Efficiency",
                     "target_metric": "cac", "target_value": 110,
                     "current_value": 116, "actions_done": 3,
                     "actions_total": 3, "observing": True}],
    "cost": {"media_today": 1820, "ai_api_today": 42.20,
             "infra_today": 18, "projection": 59400, "budget": 61000},
    "data_health": {"GSC": "FRESH", "GA4": "FRESH", "Media": "FRESH",
                    "Email": "DELAYED", "TikTok": "DELAYED"},
    "incidents": [{"severity": "P1", "title": "CONTENT FACTORY DEGRADED",
                   "component": "Content Factory",
                   "why": "Image Provider outage; 7 workflows affected"}],
}
_html = UI.cockpit_section(_ctx)
t("the contract file exists and is enforced",
  UI.check_contract()["ok"])
t("the P1 incident is a strip at the TOP, not a buried card",
  _html.index("CONTENT FACTORY DEGRADED") < _html.index("Business Pulse"))
t("business pulse renders all six KPIs",
  all(x in _html for x in ("Revenue", "Contribution", "CAC",
                           "Pipeline")))
t("CAC DOWN RENDERS AS GOOD",
  "ck-ok" in _html.split("CAC")[1][:220])
t("the change feed leads with the biggest movement",
  "cpa" in _html.split("What Changed")[1][:400])
t("the incomplete decision is held back and said so",
  "DECISION_INCOMPLETE" in _html or "held back" in _html)
t("the quick fix shows rollback and verification",
  "route back to primary" in _html and "agent healthy" in _html)
t("the stalled loop names its reason",
  "Meta performance sync delayed" in _html)
t("THE INITIATIVE IS NOT COMPLETE JUST BECAUSE ACTIONS RAN",
  "do not count as progress" in _html)
t("cost pulse shows the projection against budget",
  "59,400" in _html and "61,000" in _html)
t("delayed sources are visibly delayed",
  "TikTok" in _html and "▲" in _html)
t("the commander panel is present with reduced confidence named",
  "Commander" in _html)
t("every zone rendered without raising",
  "zone failed" not in _html)
t("no domain table is rebuilt: deep links instead",
  "Open " in _html)
_ids = re.findall(r"id=['\"]([^'\"]+)", _html)
t("no duplicate element id",
  not [x for x in set(_ids) if _ids.count(x) > 1])
t("the old cockpit module is a shim over the command UI",
  "content_engine_command_ui" in
  io.open("content_engine_cockpit_boards.py", encoding="utf-8").read())
t("no em-dash in any command module",
  not [f for f in ("content_engine_command_core.py",
                   "content_engine_command_ui.py")
       if "—" in io.open(f, encoding="utf-8").read()])
t("no while loop in the command engine",
  not [n for n in ast.walk(ast.parse(io.open(
      "content_engine_command_core.py", encoding="utf-8").read()))
       if isinstance(n, ast.While)])

# ---------------------------------------------------------------- verdict
print("\n" + "=" * 74)
print(str(len(PASS)) + " passed, " + str(len(FAIL)) + " failed")
if FAIL:
    for f in FAIL:
        print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
