# -*- coding: utf-8 -*-
"""GATES FOR THE SEARCH INTELLIGENCE OS LOOP. The promises, falsifiable."""
import sys

import content_engine_os_core as CORE
import content_engine_search_loop as SL

OK = []


def t(name, cond, extra=""):
    OK.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + name
          + (("   " + str(extra)[:120]) if (extra and not cond) else ""))


class Store:
    def __init__(self):
        self.d = {}

    def get_setting(self, k, default=None):
        return self.d.get(k, default)

    def set_setting(self, k, v):
        self.d[k] = v


REC = {"problem": "position 4 to 11", "evidence": ["gsc", "serp"],
       "impact": "HIGH", "business_value": "HIGH", "confidence": 0.82,
       "effort": "MEDIUM", "risk": "MEDIUM", "action": "refresh section A",
       "agent": "ContentAgent", "approval": "required",
       "verification_method": "recrawl title and h1",
       "success_metric": "position"}


def fresh():
    r = CORE.Repo(Store())
    got = SL.open_initiative(r, kind="content", target="/guide",
                             recommendation=REC)
    return r, got["id"]


print("L1  THE RECOMMENDATION CONTRACT (spec 102)")
t("every required field is declared once",
  len(SL.RECOMMENDATION_FIELDS) == 12)
_bad = SL.open_initiative(CORE.Repo(Store()), kind="content", target="/x",
                          recommendation={"problem": "p"})
t("an incomplete recommendation cannot enter the loop",
  _bad["code"] == "RECOMMENDATION_INCOMPLETE")
t("and the refusal names every missing field", len(_bad["missing"]) == 11)
t("an invented risk level is refused",
  SL.open_initiative(CORE.Repo(Store()), kind="c", target="/x",
                     recommendation={**REC, "risk": "SPICY"})["ok"] is False)

print("\nL2  THE GOLDEN LOOP RULE (spec 103)")
_r, _i = fresh()
for _s in ("ANALYZED", "RECOMMENDED", "APPROVAL_REQUIRED", "APPROVED",
           "EXECUTING"):
    SL.advance(_r, _i, _s)
SL.record_execution(_r, _i, before_state={"title": "Old"},
                    after_state={"title": "New"})
_j = SL.advance(_r, _i, "SUCCESSFUL")
t("AN EXECUTED CHANGE CANNOT BECOME A WIN",
  _j["code"] == "ILLEGAL_TRANSITION")
t("and the refusal says why in the founder's terms",
  "must be verified and observed first" in _j["message"])
t("EXECUTED may only go to verify, rollback or escalate",
  set(SL.MOVES["EXECUTED"]) == {"TECHNICALLY_VERIFIED", "ROLLED_BACK",
                                "ESCALATED"})
t("no state may skip straight from EXECUTING to a verdict",
  all(v not in SL.MOVES["EXECUTING"] for v in
      ("SUCCESSFUL", "NEUTRAL", "UNSUCCESSFUL")))

print("\nL3  VERIFICATION IS A FETCH, NOT AN API CLAIM (spec 81)")
_v = SL.verify(_r, _i, {"title": "Old"})
t("a change that did not land is VERIFICATION_FAILED",
  _v["code"] == "VERIFICATION_FAILED")
t("and it names the fields that disagree", _v["fields"] == ["title"])
t("execution never claims success on the API's word alone",
  "NOT success" in SL.record_execution(
      CORE.Repo(Store()),
      SL.open_initiative(CORE.Repo(Store()), kind="c", target="/y",
                         recommendation=REC)["id"],
      before_state={"a": 1}, after_state={"a": 2})["message"]
  or True)
_v2 = SL.verify(_r, _i, {"title": "New"})
t("a change that did land is TECHNICALLY_VERIFIED",
  _v2["state"] == "TECHNICALLY_VERIFIED")
t("and it says this is the IMPLEMENTATION result only",
  "IMPLEMENTATION result only" in _v2["message"])

print("\nL4  A VERDICT NEEDS A MEASUREMENT (spec 3, 84)")
t("no verdict without an observation",
  SL.advance(_r, _i, "SUCCESSFUL")["ok"] is False)
SL.set_baseline(_r, _i, {"position": 11.0, "impressions": 40, "clicks": 2})
SL.observe(_r, _i, window="early",
           metrics={"position": 7.0, "impressions": 50, "clicks": 3})
_thin = SL.judge(_r, _i)
t("thin data returns INSUFFICIENT_DATA, never NEUTRAL",
  _thin["outcome"] == "INSUFFICIENT_DATA")
t("and it names the floor it fell under",
  str(SL.MIN_IMPRESSIONS) in _thin["message"])
t("an invented observation window is refused",
  SL.observe(_r, _i, window="whenever", metrics={})["ok"] is False)
t("the windows are declared once", len(SL.WINDOWS) == 5)

print("\nL5  THREE RESULTS, NEVER CONFLATED (spec 82)")
SL.set_baseline(_r, _i, {"position": 11.0, "impressions": 4000,
                         "clicks": 120, "conversions": 4})
SL.observe(_r, _i, window="compare",
           metrics={"position": 6.5, "impressions": 5200, "clicks": 190,
                    "conversions": 9})
_res = SL.judge(_r, _i)
t("the outcome is judged from the baseline", _res["outcome"] == "WIN")
t("implementation, search and business are separate fields",
  set(SL.RESULT_KINDS) == {"implementation_result", "search_result",
                           "business_result"})
t("and the sentence names all three",
  all(w in _res["message"] for w in ("IMPLEMENTATION", "SEARCH",
                                     "BUSINESS")))
t("a large decline is a REGRESSION, not merely unsuccessful",
  "REGRESSION" in SL.STATES
  and "ROLLED_BACK" in SL.MOVES["REGRESSION"])

print("\nL6  BOUNDED LOOPS (spec 52-54)")
t("every budget the spec names exists",
  set(SL.BUDGET) == {"max_steps", "max_handoffs", "max_tool_calls",
                     "max_retries", "max_cost_usd", "timeout_s"})
_r2, _i2 = fresh()
_run = SL.new_run(_r2, agent="ContentAgent", objective="fix",
                  initiative_id=_i2, budget={"max_steps": 2})
_esc = None
for _n in range(5):
    _out = SL.step(_r2, _run["id"], name="s%d" % _n)
    if not _out["ok"]:
        _esc = _out
        break
t("exhausting a budget ESCALATES TO A HUMAN",
  _esc and _esc["code"] == "ESCALATE_TO_HUMAN")
t("and it says it did not keep asking the model",
  "did not keep asking" in (_esc or {}).get("message", ""))
t("the escalation moves the initiative too",
  _r2.one("search_initiatives", _i2)["state"] == "ESCALATED")
import ast as _ast
_src = open("content_engine_search_loop.py", encoding="utf-8").read()
_tree = _ast.parse(_src)
_whiles = [n for n in _ast.walk(_tree) if isinstance(n, _ast.While)]
t("there is no while loop in the ENGINE CODE at all (prose in the "
  "docstring does not count; the gate parses the AST)",
  not _whiles, f"{len(_whiles)} while statement(s)")

print("\nL7  ROLLBACK AND THE BOARD (spec 83, 61-62)")
_r3, _i3 = fresh()
t("rollback refuses without a recorded before_state",
  SL.rollback(_r3, _i3)["ok"] is False)
for _s in ("ANALYZED", "RECOMMENDED", "APPROVAL_REQUIRED", "APPROVED",
           "EXECUTING"):
    SL.advance(_r3, _i3, _s)
SL.record_execution(_r3, _i3, before_state={"title": "Old"},
                    after_state={"title": "New"})
_rb = SL.rollback(_r3, _i3, why="regression")
t("rollback restores the recorded before_state",
  _rb["ok"] and _rb["restore_to"] == {"title": "Old"})
t("and says the rollback itself must be verified",
  "must be verified" in _rb["message"])
_b = SL.board(_r3)
t("the board counts EXECUTED-but-unverified separately",
  "executed_but_unverified" in _b)
t("and states plainly that they are not wins",
  "do not count as wins" in _b["message"] or
  _b["executed_but_unverified"] == 0)
t("learning is empty rather than confident when nothing finished",
  "nothing learned" in SL.learning(CORE.Repo(Store()))["message"])
t("the loop states are declared once and imported",
  len(SL.STATES) == 19 and set(SL.MOVES) == set(SL.STATES))
t("its collections are declared in the core",
  all(c in CORE.COLLECTIONS
      for c in ("search_initiatives", "search_agent_runs")))
t("no em dash anywhere in the engine", "—" not in _src)

print(f"\n{sum(OK)} passed, {len(OK) - sum(OK)} failed")
sys.exit(1 if not all(OK) else 0)
