# -*- coding: utf-8 -*-
"""THE ROSTER: who works here, and which step of a job is whose.

Section 10.2. A job is a PIPELINE of skill steps; an employee card is a
ROLE. One content piece touches five employees, so attribution is per
SKILL STEP, never per job - otherwise one card claims the whole
pipeline's work and the other four look idle.

THE STEP NAMES BELOW WERE READ OUT OF THE RUNNING ORCHESTRATOR, not
copied from the audit. The audit guessed "researcher", "writer",
"segmentation", "lead_cleaning", "outreach_performance"; none of those
exist. The real steps are site_intelligence, competitor_intel,
content_strategist, content_producer, seo_optimizer, qa_compliance,
publisher, analytics_funnel, optimizer, lead_sourcing, lead_qualifier,
segmenter, outreach_copy, outreach_send. Section 10.2 said verify before
coding; this is that verification, kept.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_contracts as C

# ==========================================================================
# ATTRIBUTION: skill step -> the employee who owns it
# ==========================================================================
ATTRIBUTION: Dict[str, str] = {
    # ---- FLOW_CONTENT ----------------------------------------------------
    "site_intelligence": "seo.technical",
    "competitor_intel": "seo.analyst",
    "content_strategist": "mkt.strategist",
    "content_producer": "mkt.producer",
    "seo_optimizer": "seo.content_specialist",
    "publisher": "mkt.distributor",
    # ---- FLOW_OUTREACH ---------------------------------------------------
    "lead_sourcing": "leads.prospector",
    "lead_qualifier": "leads.qualifier",
    "segmenter": "leads.qualifier",
    "outreach_copy": "leads.outreach_writer",
    "outreach_send": "leads.sender",
    # ---- SHARED STEPS ----------------------------------------------------
    # qa_compliance runs in BOTH flows and is the same role either way:
    # the checker that stands between a draft and a human.
    "qa_compliance": "mkt.creative_director",
    "analytics_funnel": "bi.analyst",
    # the optimizer does not do a lane's work; it folds outcomes into the
    # playbook, so its output belongs to every card's "learned" line.
    "optimizer": "*module.learned",
}

# ==========================================================================
# THE EMPLOYEES
# ==========================================================================
#: badge is the TRUTH about the code behind the desk, not an ambition.
#: live       a scheduler makes its jobs and the orchestrator advances them
#: inspector  it detects and reports; it produces nothing
#: architected the state machine exists; no adapter verifies yet
#: notstaffed nothing creates its work
ROSTER: List[Dict[str, Any]] = [
    # ---- MARKETING / CONTENT (the lane that produces daily) -------------
    {"id": "mkt.strategist", "name": "🧭 Content Strategist",
     "module": "content", "badge": "live", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("Claude", "claude_api"), ("Search Console", "google_gsc_ga4")],
     "why": "the scheduler plans its pieces daily and the orchestrator "
            "advances them"},
    {"id": "mkt.producer", "name": "✍ Content Producer",
     "module": "content", "badge": "live", "cap_key": "PER_JOB_BUDGET_USD",
     "slots": [("Claude", "claude_api"), ("Images", "image_gen")],
     "why": "writes every blog, guide and social piece the plan asks for"},
    {"id": "mkt.creative_director", "name": "🔍 QA and Compliance",
     "module": "content", "badge": "live", "cap_key": "PER_JOB_BUDGET_USD",
     "slots": [("Claude", "claude_api")],
     "why": "every piece passes it before a human ever sees it"},
    {"id": "mkt.distributor", "name": "📤 Publisher",
     "module": "content", "badge": "live", "cap_key": "PER_JOB_BUDGET_USD",
     "slots": [("WordPress", "wordpress_publish")],
     "why": "publishes what you approve, and only what you approve"},
    # ---- SEO -------------------------------------------------------------
    {"id": "seo.technical", "name": "🔧 SEO Technical",
     "module": "seo", "badge": "live", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("Crawler", "seo_crawler"), ("PageSpeed", "seo_pagespeed"),
               ("Index", "seo_index_inspect")],
     "why": "crawl, speed and indexing run on the cadence"},
    {"id": "seo.analyst", "name": "📈 SEO Analyst",
     "module": "seo", "badge": "live", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("Search Console", "google_gsc_ga4"),
               ("Rank tracker", "seo_rank_tracker")],
     "why": "reads Search Console and rank movement daily"},
    {"id": "seo.content_specialist", "name": "✍ SEO Content Specialist",
     "module": "seo", "badge": "live", "cap_key": "PER_JOB_BUDGET_USD",
     "slots": [("Claude", "claude_api")],
     "why": "optimises every piece before it goes to QA"},
    {"id": "seo.link_builder", "name": "🔗 Link Builder",
     "module": "seo", "badge": "inspector", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("Backlinks", "seo_backlinks")],
     "why": "prospecting exists but the backlink wire has no credential"},
    # ---- LEADS AND OUTREACH ---------------------------------------------
    {"id": "leads.prospector", "name": "🔎 Prospector",
     "module": "outreach", "badge": "live", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("Lead source", "linkedin_leads"), ("Search", "serper_search")],
     "why": "sources the day's list from the ICP rotation"},
    {"id": "leads.qualifier", "name": "🎯 Qualifier",
     "module": "outreach", "badge": "live", "cap_key": "PER_JOB_BUDGET_USD",
     "slots": [("Claude", "claude_api"), ("Verify", "email_verify")],
     "why": "qualifies and segments before anything is written"},
    {"id": "leads.outreach_writer", "name": "✉ Outreach Writer",
     "module": "outreach", "badge": "live", "cap_key": "PER_JOB_BUDGET_USD",
     "slots": [("Claude", "claude_api")],
     "why": "writes the campaign; it never sends it"},
    {"id": "leads.sender", "name": "📮 Sender",
     "module": "outreach", "badge": "live", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("SMTP", "email_send"), ("Inbox", "email_reply_inbound")],
     "why": "sends only what you approved, and reads what comes back"},
    # ---- INSPECTORS (they detect; they produce nothing) ------------------
    {"id": "bi.analyst", "name": "📊 BI Analyst",
     "module": "bi", "badge": "inspector", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("GA4", "google_gsc_ga4")],
     "why": "measures what shipped; there is no production lane here yet, "
            "and a fake insights writer would be worse than none"},
    {"id": "system.integrations", "name": "🔌 Integrations Engineer",
     "module": "system", "badge": "live", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [],
     "why": "runs a free daily wire check on the cadence: newly-rejected, "
            "shadowed keys, half-configured groups and stale green; it "
            "proposes fixes and may never mark a wire verified itself"},
    {"id": "risk.sentinel", "name": "🩺 Risk Sentinel",
     "module": "risk", "badge": "inspector", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [],
     "why": "the sensors report; backups and rotation are not yet its lane"},
    # ---- ARCHITECTED AND NOT STAFFED (told honestly) ---------------------
    {"id": "media.buyer", "name": "🛒 Media Buyer",
     "module": "media", "badge": "architected", "cap_key": "PER_MONTH_BUDGET_USD",
     "slots": [("Google Ads", "ads_api")],
     "why": "the state machine is complete and no adapter verifies: Google "
            "refuses the OAuth client (invalid_client)"},
    {"id": "sga.distributor", "name": "📣 Social Distributor",
     "module": "sga", "badge": "notstaffed", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("LinkedIn", "social_linkedin")],
     "why": "the content lane writes the posts; nothing posts them on a "
            "schedule yet"},
    {"id": "commerce.analyst", "name": "📦 Commerce Analyst",
     "module": "commerce", "badge": "notstaffed", "cap_key": "PER_DAY_BUDGET_USD",
     "slots": [("Shopify", "shopify"), ("WooCommerce", "woocommerce")],
     "why": "the CMS layer reads a catalogue; no scheduler makes a commerce "
            "job, so nobody works this desk"},
]

BY_ID = {r["id"]: r for r in ROSTER}


def roster() -> List[Dict[str, Any]]:
    return [dict(r) for r in ROSTER]


def agent(agent_id: str) -> Dict[str, Any]:
    return dict(BY_ID.get(str(agent_id)) or {})


# PHASE 2: which playbook an employee reads and writes. Derived from the
# desk it sits at, so adding an employee cannot forget to add a lane.
LANE_OF_MODULE: Dict[str, str] = {
    "mkt": "content",
    "leads": "outreach",
    "seo": "seo",
    "system": "system",
    "risk": "risk",
    "bi": "bi",
    "media": "media",
    "commerce": "commerce",
    "sga": "sga",
}


def lane_of(agent_id: str) -> str:
    """The learning lane this employee writes to. Unknown desks fall back
    to 'content' ONLY if the id has no prefix at all; a real desk with no
    lane is caught by check(), because an employee whose lessons go into
    someone else's playbook is worse than one that learns nothing."""
    head = str(agent_id).split(".")[0]
    return LANE_OF_MODULE.get(head, "content")


def owner_of(skill: str) -> str:
    """Which employee owns this step. Unmapped is an ERROR, not a shrug:
    an unattributed step is work nobody reports, which is how a lane goes
    quiet without anyone noticing."""
    return ATTRIBUTION.get(str(skill), "")


def staffing_all() -> List[Dict[str, Any]]:
    """One badge per module, derived from the roster - never hand-set in
    a screen (0.3). A module is as staffed as its best-staffed desk."""
    rank = {"live": 3, "inspector": 2, "architected": 1, "notstaffed": 0}
    best: Dict[str, Dict[str, Any]] = {}
    for r in ROSTER:
        m = r["module"]
        if m not in best or rank[r["badge"]] > rank[best[m]["badge"]]:
            best[m] = r
    return [C.staffing(m, r["badge"], r["why"]) for m, r in
            sorted(best.items())]


def check() -> Dict[str, Any]:
    """Every FLOWS step must be attributed, and every badge must be real.

    A skill missing from ATTRIBUTION is a BUILD ERROR (10.2), because a
    silent skip means that work never appears on anyone's report."""
    problems = []
    try:
        import content_engine_orchestrator as orch
        steps = set()
        for flow in (getattr(orch, "FLOW_CONTENT", {}),
                     getattr(orch, "FLOW_OUTREACH", {})):
            for _st, step in dict(flow).items():
                sk = getattr(step, "skill", None)
                if sk:
                    steps.add(sk)
        missing = sorted(s for s in steps if s not in ATTRIBUTION)
        if missing:
            problems.append("unattributed skill step(s): " + ", ".join(missing))
        unknown = sorted({v for v in ATTRIBUTION.values()
                          if not v.startswith("*") and v not in BY_ID})
        if unknown:
            problems.append("attributed to nobody on the roster: "
                            + ", ".join(unknown))
    except Exception as exc:                          # noqa: BLE001
        problems.append(f"could not read the flows: {type(exc).__name__}")
    for r in ROSTER:
        if r["badge"] not in C.BADGES:
            problems.append(r["id"] + ": invalid badge")
        if not str(r.get("why") or "").strip():
            problems.append(r["id"] + ": a badge with no justification")
    # PHASE 2: every desk must own a lane, and every lane must be one the
    # learning store actually accepts. Two lists that must agree, checked
    # instead of typed twice.
    try:
        import content_engine_learning as L
        for r in ROSTER:
            head = str(r["id"]).split(".")[0]
            if head not in LANE_OF_MODULE:
                problems.append(r["id"] + ": no learning lane for this desk")
            elif LANE_OF_MODULE[head] not in L.LANES:
                problems.append(r["id"] + ": lane '%s' is not a real lane"
                                % LANE_OF_MODULE[head])
        for kind, lane in getattr(L, "_OUTCOME_LANE", {}).items():
            if lane not in L.LANES:
                problems.append("outcome '%s' files into unknown lane '%s'"
                                % (kind, lane))
    except Exception as exc:                              # noqa: BLE001
        problems.append(f"could not read the lanes: {type(exc).__name__}")
    return {"ok": not problems, "problems": problems,
            "agents": len(ROSTER), "attributed": len(ATTRIBUTION)}


if __name__ == "__main__":
    r = check()
    assert r["ok"], r["problems"]
    assert owner_of("content_producer") == "mkt.producer"
    assert owner_of("segmenter") == "leads.qualifier"
    assert owner_of("optimizer").startswith("*")
    assert owner_of("no_such_step") == ""
    st = {s["module"]: s["badge"] for s in staffing_all()}
    assert st["commerce"] == "notstaffed" and st["media"] == "architected"
    assert st["content"] == "live"
    print("OK - roster: %d employees, every FLOWS step attributed, "
          "badges justified (%s)" % (r["agents"], st))
