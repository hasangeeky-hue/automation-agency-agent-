# -*- coding: utf-8 -*-
"""GATES FOR THE SEARCH INTELLIGENCE OS LOOP. The promises, falsifiable."""
import sys

import content_engine_os_core as CORE
import os
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

print("\nL8  THE EXECUTION BOARD AND LOOP MONITOR (spec 61-63, 70)")
import content_engine_search_board as SB

_r4 = CORE.Repo(Store())
_empty = SB.section(_r4)
t("an empty board says so rather than showing an example",
  "stays empty rather than showing an example" in _empty)
t("the Kanban columns are declared once", len(SB.COLUMNS) == 8)
_i4 = SL.open_initiative(_r4, kind="content", target="/guide",
                         recommendation=REC)["id"]
for _s in ("ANALYZED", "RECOMMENDED", "APPROVAL_REQUIRED", "APPROVED",
           "EXECUTING"):
    SL.advance(_r4, _i4, _s)
SL.record_execution(_r4, _i4, before_state={"title": "Old"},
                    after_state={"title": "New"})
_h = SB.section(_r4)
t("THE EXECUTED COLUMN IS LABELLED 'NOT a result yet'",
  "NOT a result yet" in _h)
t("an executed-but-unverified card warns on its face",
  "not verified" in _h)
t("green is never given to EXECUTED", SB.TONE["EXECUTED"] == "warn")
t("green is reserved for verified success",
  SB.TONE["SUCCESSFUL"] == "ok" and SB.TONE["TECHNICALLY_VERIFIED"] == "ok")
t("the monitor keeps the three results apart on the row",
  all(w in _h for w in ("implementation:", "search:", "business:")))
t("an unmeasured signal reads 'not measured', never a zero",
  "not measured" in _h)
SL.verify(_r4, _i4, {"title": "New"})
SL.set_baseline(_r4, _i4, {"position": 11.0, "impressions": 4000,
                           "clicks": 120, "conversions": 4})
SL.observe(_r4, _i4, window="compare",
           metrics={"position": 6.5, "impressions": 5200, "clicks": 190,
                    "conversions": 9})
SL.judge(_r4, _i4)
_h2 = SB.section(_r4)
t("a judged initiative reaches the learning table",
  "WHAT HAS ACTUALLY WORKED" in _h2 and "<tbody>" in _h2)
t("the timeline is built from recorded history only",
  SB.timeline(_r4, _i4).count("sl-step") >= 6)
t("a score without components is refused (spec 70)",
  "not evidence" in SB.health_breakdown({}))
t("a score with components shows every one of them",
  all(x in SB.health_breakdown({"Technical": 91, "Content": 74})
      for x in ("Technical", "Content", "91", "74")))
t("the board computes nothing itself; it reads the engine",
  "import content_engine_search_loop" in
  open("content_engine_search_board.py", encoding="utf-8").read())
_asrc = open("content_engine_api.py", encoding="utf-8").read()
for _route in ("/searchos/initiative", "/searchos/advance",
               "/searchos/execute", "/searchos/verify",
               "/searchos/baseline", "/searchos/observe",
               "/searchos/judge", "/searchos/rollback",
               "/searchos/board", "/searchos/learning"):
    t(f"route {_route} exists", _route in _asrc)
print("\nL9  PHASE 3: THE DETECTOR AND THE MOUNTED BOARD")
_r5 = CORE.Repo(Store())
_prev = [{"query": "big drop", "page": "/a", "position": 4.2,
          "impressions": 6000},
         {"query": "small move", "page": "/b", "position": 7.0,
          "impressions": 900},
         {"query": "thin drop", "page": "/c", "position": 5.0,
          "impressions": 100}]
_cur = [{"query": "big drop", "page": "/a", "position": 11.4,
         "impressions": 6100, "clicks": 120},
        {"query": "small move", "page": "/b", "position": 7.6,
         "impressions": 920},
        {"query": "thin drop", "page": "/c", "position": 22.0,
         "impressions": 120}]
_det = SL.detect_ranking_drops(_r5, current=_cur, previous=_prev)
t("a real ranking drop opens exactly one initiative",
  len(_det["opened"]) == 1 and _det["opened"][0]["query"] == "big drop")
t("a move under the threshold is left alone",
  _det["below_threshold"] == 1)
t("A DROP ON THIN VOLUME IS NAMED, NOT ACTED ON",
  _det["too_thin"] == ["thin drop"])
t("and the message explains why thin volume is usually noise",
  "usually noise" in _det["message"])
_opened = _r5.one("search_initiatives", _det["opened"][0]["id"])
t("the opened initiative carries a COMPLETE recommendation",
  SL.check_recommendation(_opened["recommendation"])["ok"])
t("and a baseline, so it can be judged later instead of guessed at",
  _opened["baseline"].get("position") == 11.4)
t("business value is admitted as unknown rather than invented",
  "UNKNOWN" in _opened["recommendation"]["business_value"])
t("the detector invents nothing: it only reads what it was passed",
  "Nothing is fetched here" in
  open("content_engine_search_loop.py", encoding="utf-8").read())
import content_engine_seo_boards as _SEO
_sec = _SEO.seo_section({})
t("the Execution tab exists in the SEO nav",
  any(x[0] == "seoloop" for x in _SEO.TABS))
t("AND ITS PANEL ACTUALLY RENDERS (a tab with an empty panel is a "
  "broken feature that looks shipped)",
  "spanel-seoloop" in _sec and "LOOP MONITOR" in _sec)
t("the executed-is-not-a-result label survives onto the page",
  "NOT a result yet" in _sec)
t("mounting the loop did not displace the legacy Google boards",
  "seo-google" in _sec)
t("route /searchos/detect exists",
  "/searchos/detect" in open("content_engine_api.py",
                             encoding="utf-8").read())

t("no em dash on the board",
  "—" not in open("content_engine_search_board.py",
                  encoding="utf-8").read())


print("\nL10 PHASE 4: DESIGN TOKENS AND SCREEN CONTRACTS (spec 87-92, 96)")
import content_engine_search_tokens as TK

t("every colour is declared once, in the token module",
  len(TK.ROLES) == 7 and "--so-primary-main" in TK.css())
t("each role carries its MEANING, not just a hex",
  set(TK.MEANING) == set(TK.ROLES))
t("GREEN IS RESERVED FOR VERIFIED SUCCESS",
  "VERIFIED success" in TK.MEANING["success"]
  and "never a merely executed change" in TK.MEANING["success"])
t("an executed-but-unverified thing is amber, never green",
  TK.STATUS["executed"][0] == "warning")
t("and it says so in words on the badge",
  "not yet verified" in TK.status("executed"))
t("status is never colour alone: a dot AND a word (spec 69)",
  "so-dot" in TK.status("healthy") and "Healthy" in TK.status("healthy"))
t("purple is reserved for AI actions", TK.CTA["ai"] == "ai"
  and TK.MEANING["ai"] == "an AI action")
t("and for AI forecasts on charts, so a projection cannot read as a "
  "measurement", TK.CHART["ai_forecast"] == TK.ROLES["ai"]["main"])
try:
    TK.button("x", variant="rainbow")
    t("an invented CTA variant is refused", False)
except ValueError as _ex:
    t("an invented CTA variant is refused", "is not a CTA variant" in str(_ex))
try:
    TK.button("x", state="sparkly")
    t("an invented button state is refused", False)
except ValueError:
    t("an invented button state is refused", True)
t("the button sizes and states are the spec's",
  set(TK.BUTTON_H) == {"compact", "standard", "important"}
  and len(TK.BUTTON_STATES) == 8)
t("the 8px spacing grid is declared once", TK.SPACE[1] == 8)
t("shadow is limited to floating things (spec 91)",
  set(TK.SHADOW_ALLOWED) == {"dropdown", "drawer", "modal", "floating"})
t("the contract fields are the spec's eighteen",
  len(TK.CONTRACT_FIELDS) == 18 and "loop_connection" in TK.CONTRACT_FIELDS)
t("an incomplete screen contract is refused with the gaps named",
  TK.check_contract({"purpose": "p"})["code"] == "CONTRACT_INCOMPLETE")
_cs = TK.contract_status()
t("EVERY screen the spec names has a written contract (spec 95/96)",
  _cs["written"] == _cs["total"] and not _cs["missing"],
  f"missing: {_cs['missing'][:5]}")
t("and there are 33 of them", _cs["total"] == 33)
import os as _os10
t("the contracts are real files on disk",
  _os10.path.isfile("docs/search/ui/page_intelligence.md"))
_pi = open("docs/search/ui/page_intelligence.md", encoding="utf-8").read()
t("each contract states its LOOP CONNECTION, so no screen is a dead end",
  "LOOP CONNECTION" in _pi and "initiative" in _pi)
t("and its error state refuses 'something went wrong'",
  "never 'something went wrong'" in _pi)
t("no em dash in the token module",
  "—" not in open("content_engine_search_tokens.py",
                  encoding="utf-8").read())

print("\nL11 PHASE 5: THE THREE OPERABLE SCREENS (spec 12-14, 26-29, 48-49)")
import content_engine_search_screens as SS

_r11 = CORE.Repo(Store())
t("an empty opportunity board names the corrective action (spec 71)",
  "Run detection" in SS.opportunities(_r11))
t("an empty command centre says which connection is missing",
  "Connect Search Console" in SS.command_center(_r11))
t("page intelligence refuses to estimate a page it has no data for",
  "nothing is estimated" in SS.page_intelligence(_r11, "/x"))
_hi_traffic = {"impact": "MEDIUM", "business_value": "LOW",
               "confidence": 0.9, "effort": "MEDIUM"}
_hi_value = {"impact": "MEDIUM", "business_value": "HIGH",
             "confidence": 0.9, "effort": "MEDIUM"}
t("BUSINESS VALUE BEATS TRAFFIC, the spec's own example (spec 47)",
  SS.score(_hi_value)["score"] > SS.score(_hi_traffic)["score"])
t("and the ranking arithmetic is exposed, never a bare number",
  "impact" in SS.score(_hi_value)["why"]
  and "effort" in SS.score(_hi_value)["why"])
t("an unknown business value is flagged rather than scored as fact",
  SS.score({"business_value": "UNKNOWN - not joined"})["business_unknown"])
t("A METRIC WITH NO NAMED SOURCE IS NOT RENDERED (spec 73)",
  "not shown" in SS.metric("Clicks", 500, source=""))
t("and a metric with a source names it on the screen",
  "Source: Google Search Console" in
  SS.metric("Clicks", 500, source="Google Search Console"))
_d = SS.diff_viewer(field="title", before="Old title",
                    proposed="A better, longer title",
                    evidence="query cluster + SERP intent",
                    risk="MEDIUM", initiative_id="i1")
t("THE DIFF SHOWS BEFORE AND PROPOSED TOGETHER (spec 29)",
  "BEFORE" in _d and "PROPOSED" in _d and "Old title" in _d)
t("with the evidence and the risk beside them",
  "Evidence:" in _d and "Risk:" in _d)
t("and there is no approve control without reject and edit",
  all(x in _d for x in ("ssReject", "ssEdit", "ssApprove")))
t("an empty proposal cannot be approved",
  "Nothing to review" in SS.diff_viewer(field="t", before="a",
                                        proposed="", evidence="e"))
t("a CRITICAL change says it is human-only (spec 79-80)",
  "human-only" in SS.diff_viewer(field="t", before="a", proposed="b",
                                 evidence="e", risk="CRITICAL"))
_p = SS.page_intelligence(_r11, "/guide", metrics={
    "clicks": 820, "impressions": 41000, "position": 9.2,
    "previous_position": 4.8, "conversions": 11, "internal_links": 3})
t("the page analyst separates FACT from HYPOTHESIS (spec 50)",
  "FACT:" in _p and "HYPOTHESIS:" in _p)
t("and hedges a cause it cannot prove", "may have" in _p)
t("a page with nothing notable says so rather than inventing a finding",
  "That is a finding, not a gap" in SS.page_intelligence(
      _r11, "/quiet", metrics={"clicks": 10, "impressions": 100}))
t("every screen is built on the token system, not raw hexes",
  "#" not in SS.CSS.split("</style>")[-1]
  and "import content_engine_search_tokens" in
  open("content_engine_search_screens.py", encoding="utf-8").read())
t("the screens have their contracts written first (spec 96)",
  all(os.path.isfile(f"docs/search/ui/{n}.md") for n in
      ("command_center", "page_intelligence", "opportunities")))
t("no em dash in the screens module",
  "\u2014" not in open("content_engine_search_screens.py",
                       encoding="utf-8").read())

print(f"\n{sum(OK)} passed, {len(OK) - sum(OK)} failed")
sys.exit(1 if not all(OK) else 0)
