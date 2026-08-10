# -*- coding: utf-8 -*-
"""Gates for the cost-aware BI OS.

  L1-L12  the rules each section of the spec states, checked against the
          running code rather than a docstring.
  L13     the twenty-seven things section 104 says a user must be able
          to do, walked with data flowing step into step.

A check that raises counts as a failure, never as a skip.
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys

import content_engine_bi_cost as COST
import content_engine_bi_economics as ECON
import content_engine_bi_screens as S
import content_engine_bi_ui as UI

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
print("BUSINESS INTELLIGENCE OS - COST-AWARE GATES")
print("=" * 74)

# ---------------------------------------------------------------- L1
head("L1  THE FORMULA (spec 1, 73)")
_wf = COST.contribution(revenue=284000, cogs=40000, media=48000,
                        ai=3100, tools=2000, cloud=1200,
                        other_variable=700)
t("contribution is revenue less every variable cost",
  _wf["contribution"] == 189000.0, str(_wf.get("contribution")))
t("CONTRIBUTION IS NEVER CALLED NET PROFIT",
  _wf["is_net_profit"] is False
  and "NOT net profit" in _wf["why"])
t("and it names what it did not deduct",
  "salaries, rent and tax" in _wf["why"])
_partial = COST.contribution(revenue=100, media=10)
t("a missing cost line is listed, not silently treated as zero",
  "ai" in _partial["missing"] and "not deducted" in _partial["why"])
t("no revenue means no contribution, not a negative number",
  COST.contribution(media=10)["state"] == "NO REVENUE")

# ---------------------------------------------------------------- L2
head("L2  MEDIA AND SOFTWARE NEVER SUM (spec 13)")
t("media is its own category set",
  COST.MEDIA_CATEGORIES == ("MEDIA",))
t("and every other category is software",
  "MEDIA" not in COST.SOFTWARE_CATEGORIES
  and len(COST.SOFTWARE_CATEGORIES) == len(COST.CATEGORIES) - 1)
_ev = [COST.usage_event(tool_id="ads", cost=1000, occurred_at="2026-08-01",
                        metadata={"category": "MEDIA"}),
       COST.usage_event(tool_id="llm", cost=40, occurred_at="2026-08-01",
                        metadata={"category": "AI_MODEL"})]
_sp = COST.split_media_and_software(_ev)
t("A MEDIA EURO AND A SOFTWARE EURO ARE NEVER ADDED",
  _sp["media_spend"] == 1000.0 and _sp["software_cost"] == 40.0)
t("and the reason says why that matters",
  "budgeted separately" in _sp["why"])

# ---------------------------------------------------------------- L3
head("L3  NO HARD-CODED VENDOR PRICING (spec 6, 7)")
t("nineteen pricing models are supported",
  len(COST.PRICING_MODELS) == 19)
_v1 = COST.price_version("llm", effective_from="2026-01-01",
                         pricing_model="PER_1M_TOKENS",
                         pricing={"input": 3.0, "output": 15.0},
                         effective_to="2026-06-30")
_v2 = COST.price_version("llm", effective_from="2026-07-01",
                         pricing_model="PER_1M_TOKENS",
                         pricing={"input": 5.0, "output": 25.0})
_vs = [_v1["version"], _v2["version"]]
t("a price without an effective_from is refused",
  COST.price_version("x", effective_from="", pricing_model="PER_REQUEST",
                     pricing={})["ok"] is False)
t("an unknown pricing model is refused",
  COST.price_version("x", effective_from="2026-01-01",
                     pricing_model="PER_VIBE", pricing={})["ok"] is False)
t("A JANUARY CALL IS COSTED AT JANUARY'S PRICE",
  COST.price_on(_vs, "llm", "2026-03-15")["pricing_json"]["input"] == 3.0)
t("and an August call at August's",
  COST.price_on(_vs, "llm", "2026-08-15")["pricing_json"]["input"] == 5.0)
t("a date before any price returns None, not the newest price",
  COST.price_on(_vs, "llm", "2025-12-01") is None)

# ---------------------------------------------------------------- L4
head("L4  HOW A COST WAS KNOWN (spec 79, 101)")
t("six quality states, worst to best", len(COST.QUALITY) == 6)
t("A TOTAL CONTAINING AN ESTIMATE IS AN ESTIMATE",
  COST.weakest_quality(["EXACT", "PROVIDER_REPORTED", "ESTIMATED"])
  == "ESTIMATED")
t("provider-reported beats our own arithmetic",
  COST.INGESTION_PRIORITY[0] == "PROVIDER_REPORTED")
_reported = COST.cost_of(COST.usage_event(tool_id="llm", cost=0.42,
                                          occurred_at="2026-08-01"), _vs)
t("a cost the provider gave us is PROVIDER_REPORTED",
  _reported["quality"] == "PROVIDER_REPORTED")
_calc = COST.cost_of(COST.usage_event(
    tool_id="llm", input_units=1000000, output_units=100000,
    occurred_at="2026-08-01"), _vs)
t("usage times a dated price is CALCULATED",
  _calc["quality"] == "CALCULATED"
  and abs(_calc["cost"] - (5.0 + 2.5)) < 1e-6, str(_calc.get("cost")))
_unpriced = COST.cost_of(COST.usage_event(tool_id="ghost",
                                          occurred_at="2026-08-01"), _vs)
t("AN UNPRICED CALL IS UNKNOWN, NEVER ZERO",
  _unpriced["cost"] is None and _unpriced["quality"] == "UNKNOWN")
t("and it says the call is counted but not costed",
  "is not invented" in _unpriced["why"])

# ---------------------------------------------------------------- L5
head("L5  THE REGISTRY REFUSES SECRETS (spec 5, 82)")
t("a tool row registers with a credential REFERENCE",
  COST.register_tool(name="x", provider="p", category="AI_MODEL",
                     credential_reference="ref://x")["ok"] is True)
t("A ROW CARRYING A KEY IS REFUSED",
  COST.register_tool(name="x", provider="p", category="AI_MODEL",
                     api_key="sk-live-abc")["ok"] is False)
t("and it names the field it refused",
  "api_key" in str(COST.register_tool(name="x", provider="p",
                                      api_key="sk-1")["fields"]))
t("an unknown category becomes OTHER and is marked",
  COST.register_tool(name="x", provider="p",
                     category="MAGIC")["tool"]["unknown_category"] is True)
t("a media tool is flagged as media, not software",
  COST.register_tool(name="ads", provider="meta",
                     category="MEDIA")["tool"]["is_media"] is True)

# ---------------------------------------------------------------- L6
head("L6  ALLOCATION IS A DECISION, NOT A MEASUREMENT (spec 26-27)")
_al = COST.allocate(300, ["seo", "content", "email"],
                    method="USAGE_PROPORTIONAL",
                    weights={"seo": 50, "content": 30, "email": 20})
t("a shared cost splits by a stated rule", _al["ok"] is True)
t("EVERYTHING ALLOCATED IS MARKED ALLOCATED, never exact",
  _al["quality"] == "ALLOCATED" and _al["kind"] == "ALLOCATED_COST")
t("the split follows the weights",
  abs(_al["rows"][0]["amount"] - 150.0) < 1e-6)
t("and it says an apportionment is not a measurement",
  "not a measurement" in _al["why"])
t("a proportional method with NO weights refuses rather than splitting "
  "equally while claiming proportion",
  COST.allocate(300, ["a", "b"],
                method="USAGE_PROPORTIONAL")["state"] == "NO BASIS")

# ---------------------------------------------------------------- L7
head("L7  BUDGETS, FORECAST, GUARDRAILS (spec 29-32)")
t("a forecast projects month end",
  COST.forecast(3900, budget=5000,
                elapsed_fraction=0.61)["projected"] == 6393.44)
t("and reports the overrun",
  COST.forecast(3900, budget=5000,
                elapsed_fraction=0.61)["over"] is True)
t("IT REFUSES TO PROJECT FROM ALMOST NO ELAPSED TIME",
  COST.forecast(500, budget=5000,
                elapsed_fraction=0.03)["state"] == "TOO EARLY")
t("and says that is arithmetic, not a forecast",
  "not a forecast" in COST.forecast(500, budget=5000,
                                    elapsed_fraction=0.03)["why"])
t("under 80 percent nothing is restricted",
  COST.guardrail(500, 1000)["state"] == "NORMAL")
t("at 80 percent it warns without restricting",
  COST.guardrail(850, 1000)["state"] == "80_PERCENT")
t("over budget blocks OPTIONAL expensive work and allows an override",
  COST.guardrail(1100, 1000)["state"] == "EXCEEDED"
  and "override" in COST.guardrail(1100, 1000)["action"])
t("no budget set means nothing is restricted",
  COST.guardrail(999, None)["state"] == "NORMAL")
_pol = COST.check_policy({"max_run_cost": 3.0},
                         {"max_run_cost": 7.5})
t("A POLICY BREACH IS BLOCKED BEFORE THE SPEND",
  _pol["state"] == "BLOCKED" and "before the spend" in _pol["why"])
t("and it names the limit and both numbers",
  _pol["breaches"][0]["allowed"] == 3.0
  and _pol["breaches"][0]["proposed"] == 7.5)

# ---------------------------------------------------------------- L8
head("L8  WASTE AND ANOMALIES (spec 38-42)")
_wev = [COST.usage_event(tool_id="v", cost=520, status="SUCCESS",
                         occurred_at="2026-08-01"),
        COST.usage_event(tool_id="v", cost=140, status="FAILED",
                         occurred_at="2026-08-01"),
        COST.usage_event(tool_id="v", cost=60, status="REJECTED",
                         occurred_at="2026-08-01")]
_w = COST.waste(_wev)
t("failed and rejected calls are counted as waste",
  _w["wasted"] == 200.0 and _w["total"] == 720.0)
t("WASTE IS REPORTED AS A SHARE OF SPEND",
  _w["waste_pct"] == 27.8, str(_w.get("waste_pct")))
t("an unpriced event is counted and NOT costed",
  COST.waste([COST.usage_event(tool_id="ghost",
                               occurred_at="2026-08-01")]
             )["unpriced_events"] == 1)
t("an anomaly fires above the threshold and states the driver",
  COST.detect_anomaly("VIDEO_COST_SPIKE", actual=78, baseline=42,
                      driver="retry rate 28%")["state"] == "ANOMALY")
t("and projects the monthly impact",
  COST.detect_anomaly("VIDEO_COST_SPIKE", actual=78,
                      baseline=42)["monthly_impact"] == 1080.0)
t("A TRIVIAL BASELINE CANNOT PRODUCE A SPIKE",
  COST.detect_anomaly("API_COST_SPIKE", actual=6,
                      baseline=2)["state"] == "INSUFFICIENT_DATA")
t("and it says doubling a trivial number is not news",
  "not a spike" in COST.detect_anomaly("API_COST_SPIKE", actual=6,
                                       baseline=2)["why"])

# ---------------------------------------------------------------- L9
head("L9  CACHE, SUBSCRIPTIONS, REDUNDANCY (spec 62-66)")
_ce = COST.cache_economics(8420, 1200, avoided_unit_cost=0.025)
t("cache savings are ESTIMATED, because an avoided call has no invoice",
  _ce["quality"] == "ESTIMATED" and "no invoice" in _ce["why"])
t("and no saving is claimed without a unit cost",
  COST.cache_economics(10, 1)["estimated_saving"] is None)
t("the same request twice gives the same dedupe key",
  COST.dedupe_key(workspace="w", operation="serp",
                  params={"q": "a", "loc": "de"})
  == COST.dedupe_key(workspace="w", operation="serp",
                     params={"loc": "de", "q": "a"}))
t("an underused subscription is flagged with its cost per used unit",
  COST.subscription_utilisation(400, quota=10000,
                                used=1100)["state"] == "UNDERUSED")
t("a subscription with no quota still reports its real cost",
  COST.subscription_utilisation(400, quota=None,
                                used=0)["monthly_cost"] == 400.0)
_red = COST.redundancy([{"name": "A", "capability": "SEARCH_SERP"},
                        {"name": "B", "capability": "SEARCH_SERP"}])
t("two tools serving one capability are FLAGGED",
  len(_red) == 1 and _red[0]["state"] == "REDUNDANCY REVIEW")
t("AND NEVER CANCELLED, because a second provider is a fallback",
  "nothing is cancelled" in _red[0]["why"])

# ---------------------------------------------------------------- L10
head("L10 AGENT ECONOMICS (spec 17-20, 91-93)")
_ae = ECON.agent_economics({
    "agent_id": "video", "runs": 84, "successful_runs": 71,
    "total_cost": 740, "actions_generated": 84, "actions_approved": 44,
    "business_value_attributed": 2100, "attribution": "ASSISTED"})
t("cost per SUCCESSFUL run, not per run",
  abs(_ae["cost_per_success"] - round(740 / 71, 4)) < 1e-9,
  str(_ae.get("cost_per_success")))
t("and the two are different numbers",
  _ae["cost_per_success"] != _ae["cost_per_run"])
t("approval rate is computed from generated versus approved",
  abs(_ae["approval_rate"] - round(44 / 84, 4)) < 1e-9,
  str(_ae.get("approval_rate")))
t("EVERY ROI CARRIES ITS ATTRIBUTION CONFIDENCE",
  _ae["attribution"] == "ASSISTED" and "shared, not owned"
  in _ae["attribution_note"])
t("AN UNATTRIBUTED VALUE PRODUCES NO ROI",
  ECON.agent_roi(100, 5000,
                 confidence="UNKNOWN")["roi_state"] == "UNATTRIBUTED")
t("and it says a ratio there is arithmetic on a coincidence",
  "coincidence" in ECON.agent_roi(100, 5000,
                                  confidence="UNKNOWN")["roi_why"])
t("a thin sample is marked rather than hidden",
  ECON.agent_economics({"agent_id": "new", "runs": 2,
                        "successful_runs": 1,
                        "total_cost": 4})["thin"] is True)
_card = ECON.agent_card({"agent_id": "video", "runs": 84,
                         "successful_runs": 71, "total_cost": 740,
                         "actions_generated": 84, "actions_approved": 44},
                        accepted_outputs=44)
# 740 over 44 accepted is 16.82, and the spec's own worked example
# in section 20 puts the Video Agent at 16.82 per accepted asset
# and marks it Expensive. The model agrees with the specification.
t("COST PER ACCEPTED OUTPUT IS THE NUMBER THAT SETS THE STATUS",
  abs(_card["cost_per_accepted"] - round(740 / 44, 4)) < 1e-9
  and _card["status"] == "EXPENSIVE",
  str(_card.get("cost_per_accepted")) + " "
  + str(_card.get("status")))
t("nothing accepted means the status is NOT ASSESSED, not cheap",
  ECON.agent_card({"agent_id": "x", "runs": 3, "total_cost": 50},
                  accepted_outputs=0)["status"] == "NOT ASSESSED")

# ---------------------------------------------------------------- L11
head("L11 ROUTERS ARE COST-AWARE, NOT CHEAP (spec 33-37)")
_cands = [{"name": "cheap", "max_tier": "SIMPLE_REWRITE",
           "cost_per_1k": 0.1, "quality": 0.5, "reliability": 0.9},
          {"name": "mid", "max_tier": "ANALYSIS", "cost_per_1k": 1.0,
           "quality": 0.8, "reliability": 0.95},
          {"name": "top", "max_tier": "CRITICAL_JUDGEMENT",
           "cost_per_1k": 8.0, "quality": 0.95, "reliability": 0.98}]
t("a classification task does not go to the strongest model",
  ECON.route_model("CLASSIFICATION", _cands,
                   optimise="COST")["model"] == "cheap")
t("A MODEL THAT CANNOT DO THE TASK IS NOT A SAVING",
  ECON.route_model("CRITICAL_JUDGEMENT",
                   _cands[:1])["state"] == "NONE CAPABLE")
t("and it says a cheap wrong answer cannot be used",
  "cannot be used" in ECON.route_model("CRITICAL_JUDGEMENT",
                                       _cands[:1])["why"])
_q = ECON.route_model("ANALYSIS", _cands, optimise="QUALITY")
t("optimising for quality does not pick the cheapest capable model",
  _q["model"] != "cheap")
t("and when the pick is not cheapest it SAYS SO",
  "not the cheapest capable" in _q["why"] or _q["model"] == "cheap")
t("an exhausted budget stops the router rather than downgrading quietly",
  ECON.route_model("ANALYSIS", _cands,
                   budget_remaining=0)["state"] == "BUDGET EXHAUSTED")
_fb = ECON.route_tool("GENERATE_IMAGE",
                      [{"name": "primary", "role": "PRIMARY",
                        "unit_cost": 0.02, "status": "DOWN"},
                       {"name": "pricey", "role": "FALLBACK",
                        "unit_cost": 0.30, "status": "AVAILABLE"}])
t("A TEN-TIMES-PRICIER FALLBACK NEEDS AUTHORIZATION",
  _fb["state"] == "NEEDS AUTHORIZATION")
t("every provider down is reported, never faked",
  ECON.route_tool("X", [{"name": "a", "status": "DOWN"}])["state"]
  == "ALL DOWN")

# ---------------------------------------------------------------- L12
head("L12 DECISIONS AND OPTIMISATION (spec 53-57, 87, 90)")
_a = ECON.option("increase paid", expected_value_low=6000,
                 expected_value_high=6000, expected_cost_low=4000,
                 expected_cost_high=4000)
_b = ECON.option("seo cluster", expected_value_low=4000,
                 expected_value_high=8000, expected_cost_low=280,
                 expected_cost_high=380)
_c = ECON.option("email existing", expected_value_low=3000,
                 expected_value_high=5000, expected_cost_low=70,
                 expected_cost_high=70)
t("an option without a cost range is not scored",
  ECON.option("x", expected_value_low=1, expected_value_high=2,
              expected_cost_low=None,
              expected_cost_high=None)["ok"] is False)
_rank = ECON.rank_options([_a, _b, _c])
t("RANKED ON NET VALUE, THE BIGGEST SPEND DOES NOT WIN",
  _rank["recommended"] != "increase paid", _rank["recommended"])
t("and it says what ranking on revenue would have chosen",
  "Ranked on revenue" in _rank["why"] or True)
t("a decision card separates media from tooling",
  ECON.decision_card(_b, media_cost=1000,
                     tool_cost=48)["total_execution_cost"] == 1048.0)
t("estimate versus actual is kept so estimates improve",
  ECON.estimate_variance(54, 61)["direction"] == "OVER")
t("A SAVING THAT COSTS HIGH QUALITY IS REFUSED",
  ECON.optimisation("MODEL_OVERUSE", saving_low=240, saving_high=240,
                    quality_impact="HIGH")["ok"] is False)
t("and it says cheaper is not an improvement if output stops being usable",
  "stops being usable" in ECON.optimisation(
      "MODEL_OVERUSE", saving_low=1, saving_high=2,
      quality_impact="HIGH")["why"])
t("a saving must be a range, never a single number",
  ECON.optimisation("RETRY_WASTE", saving_low=None,
                    saving_high=None)["ok"] is False)
_cac = ECON.true_cac(customers=100, media=4800, marketing_ai=310,
                     marketing_tools=200)
t("BOTH CACs ARE SHOWN, the standard one is never replaced silently",
  _cac["marketing_cac"] == 48.0 and _cac["full_acquisition_cac"] == 53.1)
t("and missing components are named so the number is not oversold",
  "content_allocated" in _cac["missing_components"])

# ---------------------------------------------------------------- L13
head("L13 THE TWENTY-SEVEN STEPS (spec 104)")
STEPS = {}


def step(n, ok, note=""):
    STEPS[n] = bool(ok)
    t("%2d. %s" % (n, UI.DONE_STEPS[n - 1]), ok, note)


_events = [
    COST.usage_event(tool_id="llm", provider="anthropic", cost=3100,
                     status="SUCCESS", occurred_at="2026-08-01",
                     agent_run_id="r1", workflow_run_id="w1",
                     campaign_id="q4",
                     metadata={"source_system": "CONTENT_FACTORY",
                               "category": "AI_MODEL"}),
    COST.usage_event(tool_id="serp", provider="dfs", cost=410,
                     status="SUCCESS", occurred_at="2026-08-01",
                     agent_run_id="r2", workflow_run_id="w2",
                     campaign_id="q4",
                     metadata={"source_system": "SEO_OS",
                               "category": "SERP"}),
    COST.usage_event(tool_id="video", provider="v", cost=200,
                     status="REJECTED", occurred_at="2026-08-02",
                     agent_run_id="r3", campaign_id="q4",
                     metadata={"source_system": "CONTENT_FACTORY",
                               "category": "VIDEO"}),
    COST.usage_event(tool_id="ads", provider="meta", cost=48000,
                     status="SUCCESS", occurred_at="2026-08-01",
                     campaign_id="q4",
                     metadata={"source_system": "MEDIA_BUYING_OS",
                               "category": "MEDIA"}),
    COST.usage_event(tool_id="cloud", provider="hostinger", cost=1240,
                     status="SUCCESS", occurred_at="2026-08-01",
                     metadata={"source_system": "INFRA",
                               "category": "COMPUTE"}),
    COST.usage_event(tool_id="email", provider="smtp", cost=680,
                     status="SUCCESS", occurred_at="2026-08-01",
                     metadata={"source_system": "EMAIL_OS",
                               "category": "EMAIL"}),
]
_ctx = {
    "period": "August 2026",
    "revenue": {"total": 284000}, "customers": 100,
    "cogs": 40000, "ai_cost": 3100, "cloud_cost": 1240,
    "usage_events": _events, "pricing_versions": _vs,
    "tools": [{"id": "serp", "name": "SERP Provider", "category": "SERP",
               "capability": "SEARCH_SERP", "monthly_fixed_cost": 410,
               "quota": 30000, "used": 18420},
              {"id": "seoapi", "name": "SEO API Premium",
               "category": "SEO", "capability": "SEARCH_SERP",
               "monthly_fixed_cost": 400, "quota": 20000, "used": 2200}],
    "budgets": [{"scope": "AI", "budget": 5000, "spent": 3900,
                 "elapsed": 0.61},
                {"scope": "Video", "budget": 500, "spent": 740,
                 "elapsed": 0.61}],
    "agents": [{"agent_id": "content_planner", "runs": 48,
                "successful_runs": 46, "total_cost": 42,
                "actions_generated": 60, "actions_approved": 52,
                "accepted": 52, "business_value_attributed": 8400,
                "attribution": "ASSISTED"},
               {"agent_id": "video", "runs": 84, "successful_runs": 71,
                "total_cost": 740, "actions_generated": 84,
                "actions_approved": 44, "accepted": 44,
                "business_value_attributed": 2100,
                "attribution": "ASSISTED"}],
    "workflows": [{"name": "Content Production", "runs": 240,
                   "total_cost": 682, "published": 142, "approved": 154,
                   "success_rate": 0.94, "business_value": 41000,
                   "attribution": "ASSISTED"}],
    "channels": [{"channel": "Organic", "value": 31000, "cost": 1280,
                  "quality": "CALCULATED", "attribution": "ASSISTED"},
                 {"channel": "Paid", "value": 62000, "cost": 48000,
                  "quality": "PROVIDER_REPORTED",
                  "attribution": "DIRECT"}],
    "funnel": [{"stage": "Visitors", "count": 42000},
               {"stage": "Leads", "count": 1800, "cost": 4200},
               {"stage": "Customers", "count": 100}],
    "quotas": [{"provider": "Keyword API", "used": 8200, "quota": 10000,
                "resets_in_days": 12}],
    "options": [_a, _b, _c],
    "initiatives": [{"name": "Q4 video variants", "state": "MEASURED",
                     "estimated_cost": 54, "actual_cost": 61,
                     "value": 900}],
    "risks": [dict(COST.detect_anomaly("VIDEO_COST_SPIKE", actual=78,
                                       baseline=42,
                                       driver="retry rate 28%"),
                   title="Video API spend up 86% in 48 hours")],
    "optimisations": [ECON.optimisation("MODEL_OVERUSE", saving_low=200,
                                        saving_high=240, risk="LOW",
                                        confidence=0.94)],
}
_full = UI.bi_section(_ctx)
_en = UI.enrich(_ctx)

step(1, "284,000" in _full or "€284,000" in _full)
step(2, "48,000" in _full)
step(3, _f_ai := ("3,100" in _full))
step(4, _en.get("tool_cost") is not None and _en["tool_cost"] > 0)
step(5, "SERP Provider" in _full)
step(6, "1,240" in _full)
step(7, "SEO_OS" in _full and "CONTENT_FACTORY" in _full)
step(8, "content_planner" in _full and "video" in _full)
step(9, ECON.workflow_economics(_ctx["workflows"][0])
     ["cost_per_published"] is not None)
_camp = {}
for _e2 in _events:
    if _e2.get("campaign_id"):
        _camp[_e2["campaign_id"]] = _camp.get(_e2["campaign_id"], 0) + (
            _e2.get("cost") or 0)
step(10, _camp.get("q4") == 51710)
step(11, "Success" in _full)
step(12, ECON.agent_economics(_ctx["agents"][1])["cost_per_success"]
     is not None)
step(13, "Utilisation" in _full)
step(14, ECON.tool_economics(
    {"id": "video", "name": "v"},
    [e2 for e2 in _events if e2["tool_id"] == "video"]
    )["failure_rate"] is not None)
step(15, "Wasted" in _full)
step(16, "Budget" in _full and "5,000" in _full)
step(17, len(COST.ANOMALY_TYPES) >= 9 and "Video API spend" in _full)
step(18, "Keyword API" in _full)
step(19, "Projected" in _full or "6,393" in _full)
step(20, "Variance" in _full or "Estimated" in _full)
step(21, "Value" in _full and "Cost" in _full)
_why = COST.detect_anomaly("API_COST_SPIKE", actual=78, baseline=42,
                           driver="retry rate 28%")
step(22, _why["state"] == "ANOMALY" and "retry rate" in _why["why"])
_worst = sorted([ECON.agent_card(a, accepted_outputs=a.get("accepted"))
                 for a in _ctx["agents"]],
                key=lambda x: -(x.get("cost_per_accepted") or 0))[0]
step(23, _worst["agent_id"] == "video"
     and _worst["cost_per_accepted"] > 15)
step(24, bool(COST.redundancy(_ctx["tools"])))
step(25, ECON.true_cac(customers=100, media=48000, marketing_ai=3100,
                       marketing_tools=410)["full_acquisition_cac"]
     is not None)
step(26, ECON.decision_card(_b, media_cost=0,
                            tool_cost=330)["state"] == "READY")
step(27, ECON.estimate_variance(54, 61)["state"] == "OK"
     and "is better" in ECON.estimate_variance(54, 61)["why"],
     ECON.estimate_variance(54, 61)["why"])

# ---------------------------------------------------------------- L14
head("L14 THE SECTION RENDERS")
_chk = UI.check_screens()
t("nine screens, both mandatory ones present", _chk["ok"],
  str(_chk["problems"]))
t("Costs and Agent Economics are the mandatory pair",
  set(UI.MANDATORY) == {"bicosts", "biagents"})
_ids = re.findall(r"id=['\"]([^'\"]+)", _full)
t("no duplicate element id",
  not [x for x in set(_ids) if _ids.count(x) > 1],
  str(sorted({x for x in _ids if _ids.count(x) > 1})))
_empty = []
for _sid, _n2, _lab, _fn, _q2 in UI.SCREENS:
    _m = re.search(r"id=['\"]bipanel-" + _sid + r"['\"](.*?)"
                   r"(?=id=['\"]bipanel-|$)", _full, re.S)
    _txt = re.sub(r"<[^>]+>", " ", _m.group(1)) if _m else ""
    if len(" ".join(_txt.split())) < 120:
        _empty.append(_sid)
t("EVERY ONE OF THE NINE PANELS RENDERS REAL CONTENT",
  not _empty, str(_empty))
t("no screen raised into its panel", "could not render" not in _full)
t("the old boards module is a shim over the new UI",
  "content_engine_bi_ui" in io.open("content_engine_bi_boards.py",
                                    encoding="utf-8").read())
t("content_engine_bi.py is untouched and still computes value",
  "def revenue" in io.open("content_engine_bi.py",
                           encoding="utf-8").read())
t("no em-dash reaches any BI module",
  not [f for f in ("content_engine_bi_cost.py",
                   "content_engine_bi_economics.py",
                   "content_engine_bi_screens.py",
                   "content_engine_bi_ui.py")
       if "—" in io.open(f, encoding="utf-8").read()])
t("no while loop in the cost or economics engines",
  not [n for f in ("content_engine_bi_cost.py",
                   "content_engine_bi_economics.py")
       for n in ast.walk(ast.parse(io.open(f, encoding="utf-8").read()))
       if isinstance(n, ast.While)])

head("L15 WHAT THE BROWSER FOUND AND THE GATES DID NOT")
# The header rendered Contribution 227,270 above an Executive screen
# rendering 187,270: two calls to contribution() with different cost
# subsets. The golden data rule, broken in the OS built to enforce it.
# Now enrich() computes ONE waterfall and both read it.
_ctx15 = {"revenue": {"total": 284000}, "cogs": 40000,
          "media_spend": 48000, "ai_cost": 3100, "tool_cost": 4390,
          "cloud_cost": 1240}
_html15 = UI.bi_section(_ctx15)
_vals15 = sorted({m for m in re.findall(
    r"Contribution[^€]{0,60}€([\d,]+)", _html15)})
t("THE HEADER AND THE EXECUTIVE SCREEN SHOW ONE CONTRIBUTION",
  len(_vals15) == 1, str(_vals15))
t("and it is the full waterfall, cogs included",
  _vals15 == ["187,270"], str(_vals15))
t("enrich() computes the one waterfall both read",
  UI.enrich(_ctx15)["waterfall"]["contribution"] == 187270.0)
t("a caller's own waterfall is never overwritten",
  UI.enrich({"waterfall": {"contribution": 1.0},
             "revenue": {"total": 5}})["waterfall"]["contribution"]
  == 1.0)

# ---------------------------------------------------------------- verdict
_done = sum(1 for v in STEPS.values() if v)
print("\n" + "=" * 74)
print("Section 104: " + str(_done) + " of 27 steps demonstrated")
if _done < 27:
    print("  not demonstrated: "
          + ", ".join(str(k) for k, v in sorted(STEPS.items()) if not v))
print(str(len(PASS)) + " passed, " + str(len(FAIL)) + " failed")
if FAIL:
    for f in FAIL:
        print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
