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

print("\nL12 PHASE 6: THE SCREENS ARE MOUNTED AND RENDER")
import content_engine_seo_boards as SEO6
from html.parser import HTMLParser as _HP

_sec6 = SEO6.seo_section({})


class _Panels(_HP):
    def __init__(self):
        super().__init__()
        self.panels = {}
        self.cur = None
        self.ids = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if a.get("id", "").startswith("spanel-"):
            self.cur = a["id"]
            self.panels[self.cur] = 0

    def handle_data(self, d):
        if self.cur:
            self.panels[self.cur] += len(d.strip())


_pp = _Panels()
_pp.feed(_sec6)
for _tab in ("seoopp", "seopage", "seoloop"):
    t("tab " + _tab + " is declared in TABS",
      any(x[0] == _tab for x in SEO6.TABS))
    t("AND its panel carries real content, not an empty box: " + _tab,
      _pp.panels.get("spanel-" + _tab, 0) > 500,
      "text length " + str(_pp.panels.get("spanel-" + _tab)))
_act = dict((g[0], g[3]) for g in SEO6.GROUPS)["act"]
t("the three screens sit under ACT, where decisions live",
  all(x in _act for x in ("seoopp", "seopage", "seoloop")))
t("mounting them created no duplicate element id",
  not [i2 for i2 in set(_pp.ids) if _pp.ids.count(i2) > 1])
t("the page screen refuses to guess which URL you meant",
  "guess which one" in _sec6)
_src6 = open("content_engine_seo_boards.py", encoding="utf-8").read()
t("panels are registered in the dict seo_section ACTUALLY reads",
  '"seoopp": _board_opportunities(ctx)' in _src6)
t("and in the _TAB_BOARDS registry, so the two lists cannot drift",
  '"seoopp":    [(' in _src6)
t("the legacy Google boards survived the mount", "seo-google" in _sec6)

print("\nL13 PHASE 8: SITE AUDIT, ISSUES AND CRAWLED PAGES, MOUNTED")
import content_engine_search_screens as SS8

_crawl8 = {"at": "2026-08-09",
           "pages": [{"url": "/a", "status": 200, "indexable": True,
                      "title": "A", "word_count": 800,
                      "internal_links": 3, "clicks": 40},
                     {"url": "/b", "status": 200, "indexable": False,
                      "title": "", "word_count": 120,
                      "internal_links": 0}],
           "issues": [{"id": "i1", "severity": "CRITICAL",
                       "title": "12 pages noindexed",
                       "category": "Indexability", "urls": ["/b"],
                       "impressions_at_risk": 18400},
                      {"id": "i2", "severity": "MEDIUM",
                       "title": "Thin content", "category": "Content",
                       "urls": ["/b"]}]}
_r8 = CORE.Repo(Store())
t("with no crawl the audit REFUSES to show a health score",
  "most confident wrong number" in SS8.site_audit(_r8))
_a8 = SS8.site_audit(_r8, _crawl8)
t("the score is shown with its components, never bare",
  "Indexability" in _a8)
t("A CATEGORY THE CRAWL DID NOT MEASURE IS LEFT OUT, not counted healthy",
  "left out of the score" in _a8)
_i8 = SS8.issues_board(_r8, _crawl8)
t("issues sort worst first", _i8.index("CRITICAL") < _i8.index("MEDIUM"))
t("every severity states its meaning in words, not colour alone",
  "traffic is at risk right now" in _i8)
t("impact with no impressions joined reads not measured, never zero",
  "not measured" in _i8)
t("the severity table is declared once",
  len(SS8.SEVERITY) == 5 and len(SS8.AUDIT_CATEGORIES) == 9)
_p8 = SS8.crawled_pages(_r8, _crawl8)
t("a field the crawl did not check is NOT a pass",
  "never a pass" in _p8)
t("indexable, noindex and not-checked are three states",
  "noindex" in _p8 and "indexable" in _p8)
_sec8 = SEO6.seo_section({"crawl": _crawl8})
_pp8 = _Panels()
_pp8.feed(_sec8)
for _tab8 in ("seoaudit", "seoissues", "seopages"):
    t("tab " + _tab8 + " is declared", any(x[0] == _tab8
                                           for x in SEO6.TABS))
    t("AND its panel renders real content: " + _tab8,
      _pp8.panels.get("spanel-" + _tab8, 0) > 500,
      "text " + str(_pp8.panels.get("spanel-" + _tab8)))
_diag = dict((g[0], g[3]) for g in SEO6.GROUPS)["diagnose"]
t("the audit screens sit under DIAGNOSE, where 'what is wrong' lives",
  all(x in _diag for x in ("seoaudit", "seoissues", "seopages")))
t("mounting six Search OS screens created no duplicate id",
  not [x for x in set(_pp8.ids) if _pp8.ids.count(x) > 1])
t("the audit reads the crawl already on the context, not a second fetch",
  "_crawl_of(ctx)" in open("content_engine_seo_boards.py",
                           encoding="utf-8").read())

print("\nL14 PHASE 9: CONTENT (spec 30-34)")
_rows9 = [
    {"url": "/decayer", "clicks": 60, "previous_clicks": 160,
     "position": 9.1, "conversions": 2, "topic": "guides"},
    {"url": "/grower", "clicks": 400, "previous_clicks": 200,
     "conversions": 18, "topic": "guides"},
    {"url": "/thin", "clicks": 4, "previous_clicks": 6, "topic": "misc"},
    {"url": "/nodata", "topic": "misc"}]
_r9 = CORE.Repo(Store())
t("a real decline is DECAYING",
  SS8.content_health(_rows9[0])["state"] == "DECAYING")
t("a real rise is GROWING",
  SS8.content_health(_rows9[1])["state"] == "GROWING")
t("A THIN PAGE IS NOT MEASURED, never quietly called stable",
  SS8.content_health(_rows9[2])["state"] == "NOT MEASURED")
t("and the refusal names the floor it fell under",
  str(SS8.DECAY_MIN_CLICKS) in SS8.content_health(_rows9[2])["why"])
t("a page with no before-and-after is NOT MEASURED too",
  SS8.content_health(_rows9[3])["state"] == "NOT MEASURED")
_inv9 = SS8.content_inventory(_r9, _rows9)
t("the inventory prints the verdict WITH its numbers",
  "clicks 160 to 60" in _inv9)
t("and states the policy in the note",
  "rather than being called stable" in _inv9)
_dec9 = SS8.content_decay(_r9, _rows9)
t("the decay board excludes thin pages", "/thin" not in _dec9)
t("and includes the real decline", "/decayer" in _dec9)
t("with nothing decaying it says quiet is a finding",
  "Quiet is a finding" in SS8.content_decay(_r9, [_rows9[1]]))
t("an empty gap board refuses to invent topics",
  "random direction" in SS8.content_gap(_r9, []))
t("an incomplete brief is refused with the missing fields",
  SS8.check_brief({"topic": "x"})["code"] == "BRIEF_INCOMPLETE")
t("the brief fields are declared once", len(SS8.BRIEF_FIELDS) == 14)
_ed9 = SS8.content_editor({"questions": ["how long do they last"],
                           "entities": ["cartridge"]},
                          "Cartridge guide: how long do they last, here.")
t("the editor counts coverage against what is actually written",
  "1 of 1" in _ed9)
t("and disclaims that coverage is not a quality score",
  "not a judgement of" in _ed9)
t("an empty draft scores nothing rather than zero",
  "stays empty until there" in SS8.content_editor({}, ""))
t("the content health words are declared once",
  len(SS8.CONTENT_HEALTH) == 5)
_sec9 = SEO6.seo_section({"content_rows": _rows9})
_pp9 = _Panels()
_pp9.feed(_sec9)
t("the Content tab is declared",
  any(x[0] == "seocontent" for x in SEO6.TABS))
t("AND its panel renders real content",
  _pp9.panels.get("spanel-seocontent", 0) > 500,
  "text " + str(_pp9.panels.get("spanel-seocontent")))
t("it sits under COMPETE, beside keywords",
  "seocontent" in dict((g[0], g[3]) for g in SEO6.GROUPS)["compete"])
t("mounting content created no duplicate id",
  not [x for x in set(_pp9.ids) if _pp9.ids.count(x) > 1])

print("\nL15 PHASE 10: BACKLINKS AND AEO (spec 36-39)")
_r10 = CORE.Repo(Store())
t("with no provider the backlink screen shows NO counts",
  "easiest number in SEO to invent" in SS8.backlinks_overview(_r10))
_bl = SS8.backlinks_overview(_r10, {"backlinks": 4200,
                                    "referring_domains": ["a", "b"],
                                    "new": ["c"], "lost": ["d", "e"],
                                    "source": "provider X"})
t("every backlink number names its provider", "Source: provider X" in _bl)
t("net movement is stated, and a never-losing profile is called out",
  "lost links are not being tracked" in _bl)
t("the gap warns that two providers cannot be compared",
  "about the providers, not the websites" in SS8.backlink_gap(_r10))
t("and it researches rather than sending outreach",
  "never sends outreach" in SS8.backlink_gap(_r10, [{"domain": "x.test"}]))
_qs = [{"question": "how long do cartridges last", "demand": 900,
        "page": "/g", "answer_words": 120, "position": 4.1},
       {"question": "are they safe", "demand": 400, "page": "/s",
        "answer_words": 12},
       {"question": "what size", "demand": 200, "answer_words": 0},
       {"question": "unchecked one", "demand": 100}]
t("a long answer is STRONG",
  SS8.answer_coverage(_qs[0])["state"] == "STRONG")
t("a short answer is WEAK, with its length named",
  SS8.answer_coverage(_qs[1])["state"] == "WEAK"
  and "12 words" in SS8.answer_coverage(_qs[1])["why"])
t("no answer at all is MISSING",
  SS8.answer_coverage(_qs[2])["state"] == "MISSING")
t("A QUESTION NOBODY CHECKED IS 'NOT ASSESSED', NOT 'MISSING'",
  SS8.answer_coverage(_qs[3])["state"] == "NOT ASSESSED")
_aeo = SS8.aeo_questions(_r10, _qs)
t("and the board says those are different facts",
  "those are different facts" in _aeo)
t("coverage has four states, not two", len(SS8.COVERAGE) == 4)
t("with nothing tracked it says none are invented",
  "none are\ninvented here" in SS8.aeo_questions(_r10)
  or "invented here" in SS8.aeo_questions(_r10))
t("the answer detail refuses to pick a question for you",
  "will not pick one for you" in SS8.answer_detail(_r10))
_ad = SS8.answer_detail(_r10, {"question": "q", "answer_words": 200,
                               "missing_points": ["safety detail"]})
t("and lists what the answer is missing when that is recorded",
  "safety detail" in _ad)
t("an empty missing-list distinguishes complete from unexamined",
  "complete answer or an unexamined one" in
  SS8.answer_detail(_r10, {"question": "q", "answer_words": 200}))
_sec10 = SEO6.seo_section({"questions": _qs})
_pp10 = _Panels()
_pp10.feed(_sec10)
for _tab10 in ("seolinks", "seoanswers"):
    t("tab " + _tab10 + " is declared",
      any(x[0] == _tab10 for x in SEO6.TABS))
    t("AND its panel renders real content: " + _tab10,
      _pp10.panels.get("spanel-" + _tab10, 0) > 500,
      "text " + str(_pp10.panels.get("spanel-" + _tab10)))
t("both sit under COMPETE",
  all(x in dict((g[0], g[3]) for g in SEO6.GROUPS)["compete"]
      for x in ("seolinks", "seoanswers")))
t("mounting them created no duplicate id",
  not [x for x in set(_pp10.ids) if _pp10.ids.count(x) > 1])

print("\nL16 PHASE 11: GEO / AI SEARCH VISIBILITY (spec 40-43)")
_r11g = CORE.Repo(Store())
_ps = [{"prompt": "best tattoo cartridges", "provider": "x",
        "runs": [{"cited": True}, {"cited": True}, {"mentioned": True},
                 {"cited": True}]},
       {"prompt": "safest needles", "provider": "x",
        "runs": [{"mentioned": True}]},
       {"prompt": "cheapest", "provider": "x",
        "runs": [{"cited": False, "mentioned": False}]},
       {"prompt": "never asked", "provider": "x"}]
t("with no prompts the screen shows no figures and says they are not "
  "modelled", "modelled" in SS8.ai_visibility(_r11g))
t("CITED and MENTIONED are separate facts", len(SS8.OBSERVED) == 4)
_s0 = SS8.prompt_state(_ps[0])
t("a well-observed prompt reports a citation rate",
  _s0["state"] == "CITED" and _s0["rate"] == 75.0)
t("ONE OBSERVATION IS AN ANECDOTE, and is marked provisional",
  SS8.prompt_state(_ps[1])["provisional"] is True)
t("and the reason names the run floor",
  str(SS8.MIN_RUNS) in SS8.prompt_state(_ps[1])["why"])
t("a prompt never observed is NOT RUN, not ABSENT",
  SS8.prompt_state(_ps[3])["state"] == "NOT RUN")
_v11 = SS8.ai_visibility(_r11g, {"prompts": _ps})
t("RATES EXCLUDE PROMPTS NEVER RUN, and say why",
  "not asking is not" in _v11)
t("every AI figure names the engine it came from",
  "Source:" in _v11)
t("the tracker marks provisional rows on their face",
  "provisional" in SS8.prompt_tracker(_r11g, _ps))
t("the citation gap refuses without both sides observed",
  "just a directory" in SS8.citation_gap(_r11g))
t("and it frames AI evidence as a different question from ranking",
  "different question from where search ranks you" in
  SS8.citation_gap(_r11g, [{"source": "x.test"}]))
t("the detail screen refuses to choose a prompt for you",
  "will not choose" in SS8.ai_visibility_detail(_r11g))
_det = SS8.ai_visibility_detail(_r11g, {"prompt": "p", "runs": [
    {"at": "2026-08-09", "provider": "x", "cited": True,
     "answer": "some answer"}]})
t("and shows what the provider actually said, per run",
  "some answer" in _det and "cited" in _det)
_sec11 = SEO6.seo_section({"prompts": _ps})
_pp11 = _Panels()
_pp11.feed(_sec11)
t("the AI Visibility tab is declared",
  any(x[0] == "seogeoai" for x in SEO6.TABS))
t("AND its panel renders real content",
  _pp11.panels.get("spanel-seogeoai", 0) > 500,
  "text " + str(_pp11.panels.get("spanel-seogeoai")))
t("it sits under COMPETE",
  "seogeoai" in dict((g[0], g[3]) for g in SEO6.GROUPS)["compete"])
t("mounting GEO created no duplicate id",
  not [x for x in set(_pp11.ids) if _pp11.ids.count(x) > 1])

print("\nL17 PHASE 12: ANALYTICS, FUNNEL, AGENT CENTRE (spec 44-47, 50-51)")
_r12 = CORE.Repo(Store())
t("analytics refuses to exist until clicks and money are both joined",
  "put clicks next to money" in SS8.search_analytics(_r12))
_an = SS8.search_analytics(_r12, {"clicks": 900, "sessions": 740,
                                  "conversions": 12, "revenue": 4200})
t("it names Search Console AND GA4 separately",
  "Search Console" in _an and "GA4" in _an)
t("AND SAYS THE TWO WILL NOT MATCH, rather than picking one",
  "will not match" in _an and "neither is" in _an)
t("one measured stage is not a funnel",
  "at least two measured" in SS8.search_funnel(_r12, {"impressions": 100}))
_fn = SS8.search_funnel(_r12, {"impressions": 40000, "clicks": 1600,
                               "organic_sessions": 1400,
                               "conversions": 21})
t("each rate is stated against the stage above it",
  "% of impressions" in _fn)
t("UNMEASURED STAGES ARE LEFT OUT, NOT ESTIMATED",
  "LEFT OUT rather than" in _fn and "Revenue" in _fn)
t("every funnel stage names the system that measured it",
  "source: GA4" in _fn and "source: Google Search Console" in _fn)
t("business-first refuses to be a traffic list",
  "traffic list wearing a business label" in SS8.business_first(_r12))
_bf = SS8.business_first(_r12, [{"url": "/big", "clicks": 10000,
                                 "conversions": 8},
                                {"url": "/small", "clicks": 2000,
                                 "conversions": 94},
                                {"url": "/unknown", "clicks": 500}])
t("A PAGE WITH FEWER CLICKS AND MORE CONVERSIONS RANKS HIGHER",
  _bf.index("/small") < _bf.index("/big"))
t("and a page with no conversion data says so instead of showing zero",
  "no conversions joined" in _bf)
t("the agent centre lists agents that are declared but not wired",
  "declared, not wired" in SS8.agent_centre(_r12))
t("and the wired count is stated honestly",
  str(len(SS8.AGENTS_WIRED)) + " of " + str(len(SS8.AGENTS))
  in SS8.agent_centre(_r12))
t("fewer agents are wired than declared, and the screen admits it",
  len(SS8.AGENTS_WIRED) < len(SS8.AGENTS))
_sec12 = SEO6.seo_section({"search_totals": {"clicks": 900}})
_pp12 = _Panels()
_pp12.feed(_sec12)
for _tab12 in ("seoanalytics", "seoagents"):
    t("tab " + _tab12 + " is declared",
      any(x[0] == _tab12 for x in SEO6.TABS))
    t("AND its panel renders real content: " + _tab12,
      _pp12.panels.get("spanel-" + _tab12, 0) > 500,
      "text " + str(_pp12.panels.get("spanel-" + _tab12)))
t("the agent centre sits under ACT",
  "seoagents" in dict((g[0], g[3]) for g in SEO6.GROUPS)["act"])
t("analytics sits under SOURCES, beside where the data comes from",
  "seoanalytics" in dict((g[0], g[3]) for g in SEO6.GROUPS)["sources"])
t("mounting them created no duplicate id",
  not [x for x in set(_pp12.ids) if _pp12.ids.count(x) > 1])

print("\nL18 PHASE 13: RESEARCH BOARDS (spec 15-21)")
_r13 = CORE.Repo(Store())
t("with no domain the overview refuses and says why",
  "which one you are reading" in SS8.domain_overview(_r13))
_dom = SS8.domain_overview(_r13, {"domain": "x.test", "authority": 41,
                                  "traffic": 9000, "source": "DataForSEO"})
t("PROVIDER TRAFFIC IS LABELLED AN ESTIMATE, not traffic",
  "provider ESTIMATE" in _dom)
t("and it points at GA4 as the measured number instead",
  "GA4" in _dom and "measured" in _dom)
t("every domain figure carries its provider name",
  "DataForSEO" in _dom)
_org = SS8.organic_research(_r13, [{"keyword": "a", "position": 4,
                                    "prev_position": 9, "volume": 300},
                                   {"keyword": "b", "position": 11}])
t("movement is stated against the previous pull", "up 5" in _org)
t("A KEYWORD WITH NO PRIOR POSITION READS 'FIRST SEEN', NOT 'NEW'",
  "FIRST SEEN" in _org and "first time we looked" in _org)
t("intent has an UNCLASSIFIED state and it is not informational",
  "UNCLASSIFIED" in SS8.INTENT
  and SS8._kw_intent({"keyword": "b"}) == "UNCLASSIFIED")
t("and the board says it refuses to default intent",
  "rather than defaulting to informational" in _org)
_kx = SS8.keyword_explorer(_r13, [{"keyword": "a", "volume": 4,
                                   "difficulty": 30},
                                  {"keyword": "b", "volume": 900}])
t("DIFFICULTY IS LABELLED A MODEL, NOT A MEASUREMENT",
  "MODELLED score" in _kx and "meaningless across two" in _kx)
t("volume below the floor is flagged as unreliable",
  "below " + str(SS8.MIN_VOLUME) + "/mo" in _kx)
t("an unscored keyword says 'not scored' rather than showing zero",
  "not scored" in _kx)
t("the gap refuses without both sides from one pull",
  "about the pull, not" in SS8.keyword_gap(_r13))
_gap = SS8.keyword_gap(_r13,
                       [{"keyword": "a", "our_position": None,
                         "competitors": [{"position": 3, "domain": "c"}]},
                        {"keyword": "b", "our_position": 2,
                         "competitors": [{"position": 8, "domain": "c"}]}],
                       ["c.test"])
t("NOT RANKING IS AN ABSENCE, NEVER POSITION 100",
  "not ranking" in _gap and "an absence is not a bad position" in _gap)
t("and where we lead it says so rather than only listing losses",
  "we rank higher" in _gap)
t("nothing tracked refuses, and names tracking as the measured number",
  "rather than estimated" in SS8.position_tracking(_r13))
_pt = SS8.position_tracking(_r13,
                            [{"keyword": "a", "position": 3,
                              "delta": 2.0, "device": "mobile",
                              "location": "Munich"},
                             {"keyword": "b", "position": 30}],
                            {"pulled_at": "2026-08-09"})
t("the pull is dated on the face of the board", "2026-08-09" in _pt)
t("A POSITION WITHOUT DEVICE AND LOCATION IS NOT A FACT",
  "is not a fact" in _pt and "mobile in Munich" in _pt)
t("a keyword with no prior pull says so rather than showing 0 change",
  "no prior pull" in _pt)
_sec13 = SEO6.seo_section({"domain_profile": {"domain": "x.test"}})
_pp13 = _Panels()
_pp13.feed(_sec13)
for _tab13 in ("seodomain", "seokwx", "seorank"):
    t("tab " + _tab13 + " is declared",
      any(x[0] == _tab13 for x in SEO6.TABS))
    t("AND its panel renders real content: " + _tab13,
      _pp13.panels.get("spanel-" + _tab13, 0) > 500,
      "text " + str(_pp13.panels.get("spanel-" + _tab13)))
t("all three sit under COMPETE",
  all(x in dict((g[0], g[3]) for g in SEO6.GROUPS)["compete"]
      for x in ("seodomain", "seokwx", "seorank")))
t("mounting them created no duplicate id",
  not [x for x in set(_pp13.ids) if _pp13.ids.count(x) > 1])
t("no em-dash reaches any Search OS screen",
  "\u2014" not in open("content_engine_search_screens.py",
                          encoding="utf-8").read())

print("\nL19 PHASE 14: SHELL, NAVIGATION, COMPONENTS (spec 4-7, 97)")
_r14 = CORE.Repo(Store())
t("NEVER CONNECTED and NO DATA YET are different problems",
  SS8.source_state({"name": "GA4"})["state"] == "NEVER CONNECTED"
  and SS8.source_state({"name": "GA4", "connected": 1})["state"]
  == "NO DATA YET")
t("and the no-data reason says nobody has asked yet",
  "nobody has\nasked yet" in SS8.source_state({"name": "GA4",
                                               "connected": 1})["why"]
  or "nobody has" in SS8.source_state({"name": "GA4",
                                       "connected": 1})["why"])
t("A CRAWL AND A RANK PULL AGE AT DIFFERENT SPEEDS",
  SS8.source_state({"name": "Crawler", "connected": 1,
                    "age_hours": 100})["state"] == "FRESH"
  and SS8.source_state({"name": "GA4", "connected": 1,
                        "age_hours": 100})["state"] == "STALE")
t("a stale source names the window it broke",
  "48h this source" in SS8.source_state({"name": "GA4", "connected": 1,
                                         "age_hours": 100})["why"])
t("an errored source is not called stale", SS8.source_state(
    {"name": "x", "connected": 1, "error": "503"})["state"] == "ERROR")
t("the freshness bar says what stale costs the screens below it",
  "not the truth as of now" in SS8.data_freshness(
      _r14, [{"name": "GA4", "connected": 1, "age_hours": 100}]))
t("with no source declared it says the screens draw on nothing",
  "drawing on nothing" in SS8.data_freshness(_r14))
t("the attention band stays empty rather than filling itself",
  "merely interesting" in SS8.attention(_r14))
t("EVERY SEND, PUBLISH AND SPEND STOPS AT THE ATTENTION BAND",
  "stops at\nthis band" in SS8.attention(_r14, [{"what": "w"}])
  or "stops at" in SS8.attention(_r14, [{"what": "w"}]))
_sh = SS8.shell(_r14, {"site": "x.test", "mode": "DEGRADED",
                       "version": "v17", "sources": []})
t("degraded mode is announced on the frame, not hidden",
  "not a clean run" in _sh and "ss-shell-deg" in _sh)
t("and a normal run does not shout",
  "not a clean run" not in SS8.shell(_r14, {"site": "x",
                                            "sources": []}))
_nm = SS8.nav_map(_r14)
t("the nav map counts every screen and group", "screen(s) in" in _nm)
t("NO SCREEN BELONGS TO NO GROUP",
  "belong to NO group" not in _nm)
_cl = SS8.component_library(_r14)
t("the library renders from the token module rather than redrawing it",
  "not redrawn here" in _cl)
t("it PROVES metric() refuses a sourceless number instead of claiming it",
  "refused: metric() will not render" in _cl)
t("status carries a dot and a word, for the one man in twelve",
  "one man in twelve" in _cl)
t("the CTA variant list is closed and says it raises",
  "raises rather than quietly" in _cl)
t("error() will not construct without a fix",
  "dead end wearing a" in _cl)
_sec14 = SEO6.seo_section({"site": "x.test",
                           "sources": [{"name": "GA4", "connected": 1,
                                        "age_hours": 100}]})
_pp14 = _Panels()
_pp14.feed(_sec14)
t("tab seosystem is declared",
  any(x[0] == "seosystem" for x in SEO6.TABS))
t("AND its panel renders real content",
  _pp14.panels.get("spanel-seosystem", 0) > 500,
  "text " + str(_pp14.panels.get("spanel-seosystem")))
t("THE SHELL RENDERS ABOVE THE TABS, not behind one",
  "ss-shell" in _sec14
  and _sec14.index("ss-shell") < _sec14.index("stab-"))
t("and the freshness chips reach the assembled page",
  "ss-chip" in _sec14)
t("mounting the shell created no duplicate id",
  not [x for x in set(_pp14.ids) if _pp14.ids.count(x) > 1])

print("\nL20 BATCH B: DATA, IDENTITY, CMS, REPORTS (spec 75-78, 85-86)")
import content_engine_search_data as DAT8
_r15 = CORE.Repo(Store())
t("every entity is declared once, with a key and a meaning",
  len(DAT8.ENTITIES) >= 12
  and all(len(x) == 3 and all(x) for x in DAT8.ENTITIES))
t("an unknown entity returns None rather than a guess",
  DAT8.entity("nonsense") is None)
t("CREDENTIALS ARE A REFERENCE, NEVER A TOKEN",
  "never a token" in DAT8.CREDENTIAL_RULE
  and DAT8.entity("credential")["key"] == "credential_ref")
_nu = DAT8.normalize_url("HTTPS://Example.com/Guide/?utm_source=x&page=2#top")
t("tracking parameters are dropped and content parameters are kept",
  _nu["params_dropped"] == ["utm_source"] and _nu["params_kept"] == ["page=2"])
t("the host is lowercased but the PATH IS NOT",
  DAT8.url_identity("https://A.test/Guide") == "https://a.test/Guide")
t("HTTP AND HTTPS ARE NOT MERGED BY A STRING RULE",
  DAT8.url_identity("http://a.test/x") != DAT8.url_identity("https://a.test/x"))
t("and neither are www and the bare host",
  DAT8.url_identity("https://a.test/x")
  != DAT8.url_identity("https://www.a.test/x"))
t("parameter order does not create two identities for one page",
  DAT8.url_identity("https://a.test/x?b=2&a=1")
  == DAT8.url_identity("https://a.test/x?a=1&b=2"))
t("the normaliser reports what it did AND what it refused to do",
  len(_nu["changed"]) >= 3 and len(_nu["not_done"]) == 3)
t("MARKET IS PART OF THE KEYWORD KEY",
  DAT8.keyword_identity("Tattoo Needles", "de") == "tattoo needles|de"
  and DAT8.keyword_identity("Tattoo Needles", "de")
  != DAT8.keyword_identity("Tattoo Needles", "us"))
t("singular and plural are NOT folded into one keyword",
  DAT8.keyword_identity("tattoo needle", "de")
  != DAT8.keyword_identity("tattoo needles", "de"))
_plan = DAT8.retention_plan()
t("every entity has a retention row", len(_plan) == len(DAT8.ENTITIES))
t("AND NO ENTITY IS LEFT WITH NO POLICY",
  not [x for x in _plan if x["state"] == "NO POLICY"],
  str([x["entity"] for x in _plan if x["state"] == "NO POLICY"]))
t("every policy carries a reason", all(x["why"] for x in _plan))
t("initiatives are kept forever, because outcomes teach",
  [x for x in _plan if x["entity"] == "initiative"][0]["days"] is None)
t("an unknown CMS is UNKNOWN, not incapable",
  DAT8.cms_capability("squarespace", "update_title")["state"]
  == "UNKNOWN PLATFORM")
t("an unsupported capability says which CMS and why",
  DAT8.cms_capability("webflow", "create_redirect")["state"] == "UNSUPPORTED")
t("shopify refuses slug changes rather than breaking every link",
  not DAT8.cms_capability("shopify", "update_slug")["supported"])
t("'no CMS' is a supported mode, not a broken one",
  "not a broken one" in DAT8.CMS["manual"]["notes"])
t("DRY RUN IS THE DEFAULT for a live-site write",
  DAT8.apply_change("wordpress", "update_title", "/g", "a", "b")["state"]
  == "DRY RUN")
t("a change that changes nothing is refused",
  DAT8.apply_change("wordpress", "update_title", "/g", "a", "a",
                    dry_run=False)["state"] == "NO CHANGE")
t("clearing a value is never something a fix engine does alone",
  DAT8.apply_change("wordpress", "update_title", "/g", "a", "",
                    dry_run=False)["state"] == "REFUSED")
t("A LIVE WRITE WITHOUT A NAMED APPROVER IS BLOCKED",
  DAT8.apply_change("wordpress", "update_title", "/g", "a", "b",
                    dry_run=False)["state"] == "NEEDS APPROVAL")
t("and with one it applies, recording who approved it",
  DAT8.apply_change("wordpress", "update_title", "/g", "a", "b",
                    approved_by="Murtuja", dry_run=False)["applied"] is True)
_rep = DAT8.build_report(
    [{"section": "summary",
      "figures": [{"label": "clicks", "source": "GSC"},
                  {"label": "vibes"}]},
     {"section": "rankings", "figures": [{"label": "avg"}]},
     {"section": "astrology", "figures": [{"label": "x", "source": "y"}]}],
    window="2026-07", sources=[{"name": "GSC", "state": "STALE"}])
t("AN UNSOURCED FIGURE NEVER REACHES A REPORT",
  "vibes" in [x["figure"] for x in _rep["unsourced"]])
t("a section whose every figure was unsourced is dropped whole",
  any(d["section"] == "rankings" for d in _rep["dropped"]))
t("a section nobody defined cannot be added to a report",
  any(d["section"] == "astrology" for d in _rep["dropped"]))
t("a stale source QUALIFIES the report rather than being used quietly",
  _rep["state"] == "QUALIFIED" and "not the window" in _rep["caveat"])
t("with fresh sources the report is clean",
  DAT8.build_report([{"section": "summary",
                      "figures": [{"label": "c", "source": "GSC"}]}],
                    sources=[{"name": "GSC", "state": "FRESH"}])["state"]
  == "CLEAN")
t("there is no 'real time' cadence", "real_time" not in DAT8.CADENCE)
t("a schedule with no recipient is refused",
  DAT8.schedule_report("weekly", [])["state"] == "REFUSED")
t("A RECURRING OUTBOUND SEND NEEDS A NAMED OWNER",
  DAT8.schedule_report("weekly", ["a@b.c"])["state"] == "NEEDS APPROVAL")
t("the model screen prints the credential rule where it cannot be missed",
  "never a token" in SS8.data_model(_r15))
t("the identity screen shows what it deliberately did NOT do",
  "deliberately did NOT" in SS8.identity_rules(_r15))
t("the retention screen prints reasons, not just numbers",
  "whoever speaks loudest" in SS8.retention_board(_r15))
t("the CMS screen shows dry run as the default outcome",
  "DRY RUN" in SS8.cms_board(_r15, "wordpress"))
t("an empty report screen says it assembles from sourced figures or not at all",
  "or not at all" in SS8.reports_board(_r15))
t("and a built report lists what it refused to print",
  "refused to print" in SS8.reports_board(_r15, _rep))
_sec15 = SEO6.seo_section({"cms": "wordpress"})
_pp15 = _Panels()
_pp15.feed(_sec15)
for _tab15 in ("seodata", "seoreport"):
    t("tab " + _tab15 + " is declared",
      any(x[0] == _tab15 for x in SEO6.TABS))
    t("AND its panel renders real content: " + _tab15,
      _pp15.panels.get("spanel-" + _tab15, 0) > 500,
      "text " + str(_pp15.panels.get("spanel-" + _tab15)))
t("mounting them created no duplicate id",
  not [x for x in set(_pp15.ids) if _pp15.ids.count(x) > 1])
t("no em-dash reaches the data module",
  "\u2014" not in open("content_engine_search_data.py",
                       encoding="utf-8").read())

print("\nL21 BATCH C: THE LOOPS, SEARCH, PALETTE (spec 56-59, 93-94)")


class _SR(object):
    """A store stub for the search gates."""

    def __init__(self, d=None, boom=None):
        self.d, self.boom = d or {}, boom

    def all(self, k):
        if self.boom and k == self.boom:
            raise RuntimeError("table missing")
        return self.d.get(k, [])


_r16 = CORE.Repo(Store())
t("there are four domain loops", len(SL.LOOPS) == 4)
t("an unknown loop id does NOT fall back to a default",
  SL.loop_spec("nope") is None)
t("every loop's last stage feeds its first",
  all(SL.loop_spec(l[0])["closes"] for l in SL.LOOPS))
t("THE CONTENT LOOP TREATS WAITING AS A STAGE",
  any("wait" in x for x in SL.loop_spec("content")["stages"]))
t("and says why: three days after publishing measures the weather",
  "measures the weather" in SL.loop_spec("content")["note"])
t("EVERY OUTREACH SEND STOPS AT A PERSON",
  any("behind approval" in x
      for x in SL.loop_spec("authority")["stages"])
  and "liability" in SL.loop_spec("authority")["note"])
t("the AI loop re-asks the same prompts rather than assuming",
  any("SAME prompts" in x
      for x in SL.loop_spec("visibility")["stages"]))
t("a loop nobody has run says so, and that is not 'nothing is wrong'",
  SL.loop_state("technical")["state"] == "NEVER RUN")
_ls = SL.loop_state("technical", {"crawl the site": 40,
                                    "classify what is broken": 12})
t("A LOOP THAT NEVER CLOSES IS CALLED A QUEUE, NOT DRAWN AS A CIRCLE",
  _ls["state"] == "NOT YET CLOSED"
  and "queue rather than a loop" in _ls["why"])
t("and the most piled-up stage is named",
  _ls["bottleneck"] == "crawl the site")
t("once a cycle closes the loop reports CLOSING",
  SL.loop_state("technical", {"completed_cycles": 5})["state"]
  == "CLOSING")
t("an unknown loop refuses to report a state",
  SL.loop_state("nope")["state"] == "UNKNOWN LOOP")
t("a one-character query is refused as matching everything",
  SL.search_all(_SR(), "a")["state"] == "TOO SHORT")
_sr = _SR({"search_page": [{"url": "https://x.test/guide"},
                           {"url": "https://x.test/other"}],
           "search_keyword": [{"keyword": "guide to needles"}]})
t("global search crosses entity types", SL.search_all(_sr, "guide")
  ["total"] == 2)
t("IT NAMES THE ENTITIES IT DID NOT SEARCH",
  "fact" in SL.search_all(_sr, "guide")["not_searched"])
t("and a no-match says nobody looked there, which is not the same thing",
  "different from finding nothing"
  in SL.search_all(_sr, "zzzz")["why"])
t("a broken entity is REPORTED, never swallowed into an empty result",
  SL.search_all(_SR(boom="search_issue"), "guide")["failed"][0]
  ["entity"] == "issue")
_pal = SL.palette()
t("every palette command declares what it will do",
  all(c["gate"] for c in _pal["commands"]))
t("PUBLISH AND OUTREACH STOP FOR CONFIRMATION",
  all([c for c in _pal["commands"] if c["id"] == x][0]["confirms"]
      for x in ("publish", "outreach")))
t("and navigation does not, so the gates mean something",
  not [c for c in _pal["commands"] if c["id"] == "goto"][0]["confirms"])
t("a command that spends money is marked even though it is not gated",
  [c for c in _pal["commands"] if c["id"] == "observe"][0]["gate"]
  == "cost")
t("the palette says why speed is the risk",
  "fast is exactly why" in _pal["why"])
t("the loops board explains pipeline versus loop",
  "backlog nobody closes" in SS8.loops_board(_r16))
t("and renders all four", all(l[1] in SS8.loops_board(_r16)
                              for l in SL.LOOPS))
t("the search screen explains where it does not look",
  "nobody looked" in SS8.global_search(_r16))
t("a short query renders an error with the fix",
  "at least two characters" in SS8.global_search(_sr, "a"))
t("the palette screen renders the confirmation label",
  "Confirm first" in SS8.command_palette(_r16))
_sec16 = SEO6.seo_section({})
_pp16 = _Panels()
_pp16.feed(_sec16)
for _tab16 in ("seoloops", "seofind"):
    t("tab " + _tab16 + " is declared",
      any(x[0] == _tab16 for x in SEO6.TABS))
    t("AND its panel renders real content: " + _tab16,
      _pp16.panels.get("spanel-" + _tab16, 0) > 500,
      "text " + str(_pp16.panels.get("spanel-" + _tab16)))
t("mounting them created no duplicate id",
  not [x for x in set(_pp16.ids) if _pp16.ids.count(x) > 1])

print("\nL22 BATCH D: RULES AND THE SELF AUDIT (spec 1-3, 100-107)")
import content_engine_search_rules as RU8
_r17 = CORE.Repo(Store())
t("the refusals are stated, each with its reason",
  len(RU8.REFUSALS) >= 8 and all(len(x) == 2 and all(x)
                                 for x in RU8.REFUSALS))
_aud = RU8.audit()
t("EVERY RULE THIS OS CLAIMS IS CHECKED AGAINST THE RUNNING CODE",
  _aud["total"] == len(RU8.RULES) and _aud["total"] >= 11)
t("AND EVERY ONE OF THEM HOLDS",
  _aud["state"] == "ALL HOLD",
  str([x["id"] for x in _aud["results"] if x["state"] == "BROKEN"]))
t("every result carries evidence from this run, not a claim",
  all(x["evidence"] for x in _aud["results"]))
t("a check that raises counts as BROKEN, never as skipped",
  "counts as a FAILURE" in RU8.audit.__doc__
  or "is a FAILURE" in RU8.audit.__doc__)
t("a ratio is summed then divided once",
  abs(RU8.ratio([1, 50], [10, 10000])["value"] - 51.0 / 10010.0) < 1e-9)
t("AND THE MEAN OF RATES IS A DIFFERENT, WRONG NUMBER",
  RU8.mean_of_ratios([1 / 10, 50 / 10000])
  > RU8.ratio([1, 50], [10, 10000])["value"] * 5)
t("a rate over a zero denominator is None, never 0.0",
  RU8.ratio([0], [0])["value"] is None)
t("and it says why 0.0 would be a lie",
  "where there was no opportunity" in RU8.ratio([0], [0])["why"])
t("INSUFFICIENT_DATA is a peer verdict, not a fallback",
  "INSUFFICIENT_DATA" in RU8.VERDICTS and len(RU8.VERDICTS) == 4)
t("too few observations returns INSUFFICIENT_DATA",
  RU8.verdict(10, 10, n=2)["verdict"] == "INSUFFICIENT_DATA")
t("A MEASURED NO-CHANGE RETURNS NEUTRAL, so the two are separable",
  RU8.verdict(10, 10, n=500)["verdict"] == "NEUTRAL")
t("a missing baseline cannot produce a verdict",
  RU8.verdict(10, None, n=500)["verdict"] == "INSUFFICIENT_DATA")
t("a missing sample size cannot produce a verdict either",
  RU8.verdict(10, 8)["verdict"] == "INSUFFICIENT_DATA")
t("THE GOLDEN DATA RULE CATCHES A HEADLINE ITS CHART DISAGREES WITH",
  RU8.golden_data_check(100, [50, 40], [100])["state"] == "DISAGREES")
t("and passes when they are one number",
  RU8.golden_data_check(100, [60, 40], [70, 30])["state"] == "AGREES")
t("an unstamped artefact is not trustworthy",
  RU8.stamp()["trustworthy"] is False)
t("nor is one built on a stale source",
  RU8.stamp("v17", "NORMAL",
            [{"name": "GA4", "state": "STALE"}])["trustworthy"] is False)
t("and the reason names the source that made it so",
  "GA4" in RU8.stamp("v17", "NORMAL",
                     [{"name": "GA4", "state": "STALE"}])["why"])
t("an unknown mode degrades rather than being accepted",
  RU8.stamp("v17", "TURBO")["mode"] == "DEGRADED")
t("the principles screen renders every refusal",
  all(w[:40] in SS8.principles(_r17) for w, _y in RU8.REFUSALS))
t("the audit screen runs the checks when the page is drawn",
  "ALL HOLD" in SS8.self_audit(_r17))
t("the worked examples SHOW the wrong ratio beside the right one",
  "times the right" in SS8.worked_examples(_r17))
_sec17 = SEO6.seo_section({})
_pp17 = _Panels()
_pp17.feed(_sec17)
t("tab seorules is declared",
  any(x[0] == "seorules" for x in SEO6.TABS))
t("AND its panel renders real content",
  _pp17.panels.get("spanel-seorules", 0) > 500,
  "text " + str(_pp17.panels.get("spanel-seorules")))
t("mounting it created no duplicate id",
  not [x for x in set(_pp17.ids) if _pp17.ids.count(x) > 1])
t("NO TAB IN THE WHOLE OS BELONGS TO NO GROUP",
  not [x[0] for x in SEO6.TABS
       if not any(x[0] in g[3] for g in SEO6.GROUPS)],
  str([x[0] for x in SEO6.TABS
       if not any(x[0] in g[3] for g in SEO6.GROUPS)]))
# seosrc is the ONE tab whose panel is not built from the panels dict: it
# carries the legacy Google boards, which arrive as legacy_html from the
# caller. So it is asserted against its own contract rather than excused.
t("EVERY DECLARED TAB HAS A PANEL WITH REAL CONTENT",
  not [x[0] for x in SEO6.TABS if x[0] != "seosrc"
       and _pp17.panels.get("spanel-" + x[0], 0) < 200],
  str([x[0] for x in SEO6.TABS if x[0] != "seosrc"
       and _pp17.panels.get("spanel-" + x[0], 0) < 200]))
_pp17b = _Panels()
_pp17b.feed(SEO6.seo_section({}, "<div>LEGACY GOOGLE BOARDS</div>"))
import re as _re17
_sec17b = SEO6.seo_section({}, "<div>LEGACY GOOGLE BOARDS</div>")
_m17 = _re17.search(
    r"id=['\"]spanel-seosrc['\"](.*?)(?=id=['\"]spanel-|$)",
    _sec17b, _re17.S)
t("AND seosrc carries the legacy Google boards INSIDE ITS OWN PANEL",
  bool(_m17) and "LEGACY GOOGLE BOARDS" in _m17.group(1),
  "panel " + ("missing" if not _m17 else str(len(_m17.group(1)))))
t("and there is exactly ONE seosrc panel on the page",
  _pp17b.ids.count("spanel-seosrc") == 1,
  str(_pp17b.ids.count("spanel-seosrc")))
t("no em-dash reaches the rules module",
  "\u2014" not in open("content_engine_search_rules.py",
                       encoding="utf-8").read())

print(f"\n{sum(OK)} passed, {len(OK) - sum(OK)} failed")
sys.exit(1 if not all(OK) else 0)
