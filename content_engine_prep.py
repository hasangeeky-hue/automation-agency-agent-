"""
content_engine_prep.py
============================================================================
The data-plumbing seam (SECTION 9 "70% code"): prepare_input(skill, job) shapes
each skill's INPUT from prior step outputs on the job blackboard.

The orchestrator stores every LLM/code result at job["payload"][skill_name].
These mappers read those results (and the code-collected raw data the job was
created with) and assemble the exact INPUT each SECTION 8 prompt expects.

Raw code-collected data is expected under namespaced payload keys:
  payload["audit"]        -> crawl/PageSpeed/GSC pull      (feeds site_intelligence)
  payload["competitors"]  -> [{name, external_content}]    (feeds competitor_intel)
  payload["analytics"]    -> GA4/funnel numbers            (feeds analytics_funnel)
  payload["performance"]  -> content/outreach performance  (feeds optimizer)
  payload["config"]       -> business_goal, cta, produce_index, intent, etc.

Everything is tolerant of missing data (sensible defaults), so a partial job or
a fixture never KeyErrors. Pipeline A is fully mapped; Pipeline B skills have
working defaults you can tighten later.
============================================================================
"""

from __future__ import annotations

from content_engine_learning import get_playbook

# Map a piece type -> the "length" hint the Content Producer prompt expects.
_LENGTH_BY_TYPE = {
    "blog": "blog:1500-2000w",
    "social_carousel": "caption:150-300c",
    "reel": "reel_script:20-40s",
    "email": "email:120-200w",
}
# business_goal -> search intent for the SEO Optimizer.
_INTENT_BY_GOAL = {
    "sales": "commercial",
    "awareness": "informational",
    "retention": "informational",
}


def _cfg(job: dict) -> dict:
    return job.get("payload", {}).get("config", {}) or {}


def _client(job: dict) -> str:
    return job.get("client_id") or _brand(job).get("brand_name", "")


def _learnings(job: dict) -> Optional[dict]:
    """The client's accumulated playbook, or None on the first-ever cycle."""
    pb = get_playbook(_client(job))
    return pb if pb.get("cycles", 0) > 0 else None


def _brand(job: dict) -> dict:
    return job.get("brand", {}) or {}


def _result(job: dict, skill: str) -> dict:
    """A prior skill's stored output (empty dict if not run yet)."""
    return job.get("payload", {}).get(skill, {}) or {}


def _chosen_row(job: dict) -> dict:
    """The single calendar row this job is producing (Strategist output)."""
    calendar = _result(job, "content_strategist").get("calendar", []) or []
    idx = _cfg(job).get("produce_index", 0)
    return calendar[idx] if 0 <= idx < len(calendar) else {}


def _piece_content(job: dict) -> str:
    prod = _result(job, "content_producer")
    parts = [prod.get("title"), prod.get("body")]
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Pipeline A mappers
# ---------------------------------------------------------------------------
def _in_site_intelligence(job: dict) -> dict:
    a = job.get("payload", {}).get("audit", {}) or {}
    return {
        "site_url": a.get("site_url", ""),
        "pages_indexed": a.get("pages_indexed", 0),
        "existing_topics": a.get("existing_topics", []),
        "core_web_vitals": a.get("core_web_vitals",
                                 {"lcp_ms": 0, "cls": 0, "inp_ms": 0}),
        "mobile_friendly": a.get("mobile_friendly", True),
        "crawl_errors": a.get("crawl_errors", 0),
        "missing_schema_types": a.get("missing_schema_types", []),
        "top_gsc_queries": a.get("top_gsc_queries", []),
        "content_gaps": a.get("content_gaps", []),
    }


def _in_competitor_intel(job: dict) -> dict:
    site = _result(job, "site_intelligence")
    audit = job.get("payload", {}).get("audit", {}) or {}
    client_topics = audit.get("existing_topics") or site.get("content_opportunities", [])
    return {
        "client_topics": client_topics,
        "client_value_prop": _cfg(job).get("value_prop") or _brand(job).get("offer", ""),
        "competitors": job.get("payload", {}).get("competitors", []),
    }


def _in_content_strategist(job: dict) -> dict:
    site = _result(job, "site_intelligence")
    comp = _result(job, "competitor_intel")
    audit = job.get("payload", {}).get("audit", {}) or {}
    seo_opps = list(site.get("content_opportunities", []))
    seo_opps += [q.get("query", "") for q in audit.get("top_gsc_queries", []) if q.get("query")]
    cfg = _cfg(job)
    weekly = cfg.get("weekly_priorities", "")
    pb = _learnings(job)
    if pb:
        # Fold learnings into weekly_priorities (a lever the prompt already
        # respects) AND pass the full playbook as extra context.
        weekly = (weekly + " | LEARNINGS: prioritize " +
                  ", ".join(pb.get("winning_topics", [])[:5]) +
                  "; avoid " + ", ".join(pb.get("avoid", [])[:5]) +
                  "; mix " + (pb.get("content_mix") or "balanced")).strip(" |")
    out = {
        "site_brief": site,
        "seo_opportunities": seo_opps,
        "competitor_gaps": {
            "market_gap": comp.get("market_gap", {}),
            "differentiation_angles": comp.get("differentiation_angles", []),
        },
        "business_goal": cfg.get("business_goal", "awareness"),
        "weekly_priorities": weekly,
        "segments_active": cfg.get("segments_active", []),
        "pieces_this_week": cfg.get("pieces_this_week", 5),
    }
    if pb:
        out["prior_learnings"] = pb
    return out


def _audience(job: dict) -> tuple[str, str]:
    """Who the piece is for + their pain — from config/brand, else the Anthropos
    ICP default. This is what makes the article specific, not generic."""
    cfg, br = _cfg(job), _brand(job)
    persona = (cfg.get("audience") or cfg.get("icp") or br.get("audience")
               or br.get("icp") or "Owners and managers of small service businesses "
               "(doctors, lawyers, dentists, tax consultants, Shopify stores, content "
               "creators, marketing managers) in the US, UK, Germany, Switzerland and Canada.")
    pain = (cfg.get("audience_pain") or br.get("audience_pain")
            or "Drowning in manual admin (bookings, follow-ups, lead handling, reporting), "
            "no time or in-house tech team, losing leads to slow response, unsure how AI/"
            "automation actually applies to their specific business.")
    return persona, pain


def _content_research(job: dict, row: dict) -> str:
    """Live web-research brief for THIS piece (cached on the job so it runs once).
    Best-effort: '' if research is off or web search is unavailable."""
    import os
    if os.getenv("CONTENT_WEB_RESEARCH", "1") not in ("1", "true", "True"):
        return ""
    if row.get("type", "blog") not in ("blog", "email"):   # long-form only
        return ""
    idx = str(_cfg(job).get("produce_index", 0))
    cache = job.setdefault("payload", {}).setdefault("_research", {})
    if idx in cache:
        return cache[idx] or ""
    topic = row.get("working_title") or row.get("primary_keyword") or ""
    persona, pain = _audience(job)
    try:
        from content_engine_providers import web_research
        brief = web_research(topic, context=f"Audience: {persona} Pain: {pain}")
    except Exception:
        brief = ""
    cache[idx] = brief
    return brief


def _in_content_producer(job: dict) -> dict:
    row = _chosen_row(job)
    ptype = row.get("type", "blog")
    persona, pain = _audience(job)
    comp = _result(job, "competitor_intel")
    angles = [a.get("angle", "") for a in comp.get("differentiation_angles", []) if a.get("angle")]
    # Tag this piece to the REAL website taxonomy (segment + service pillar) so it
    # targets the right audience/section instead of being a generic article.
    tax = {}
    try:
        import content_engine_site_taxonomy as TAX
        cfg = _cfg(job)
        # prefer the approved plan's explicit segment/pillar, else the strategist
        # row, else classify from the title/keyword — so it is ALWAYS on-target.
        tax = TAX.resolve(cfg.get("segment") or row.get("segment") or row.get("target_segment", ""),
                          cfg.get("pillar") or row.get("pillar") or row.get("service", ""),
                          row.get("working_title", "") or cfg.get("chosen_topic", ""),
                          row.get("primary_keyword", "") or cfg.get("target_keyword", ""))
        job.setdefault("payload", {})["taxonomy"] = tax   # persists for the publisher
    except Exception:
        tax = {}
    out = {
        "type": ptype,
        "working_title": row.get("working_title", ""),
        "primary_keyword": row.get("primary_keyword", ""),
        "target_segment": row.get("target_segment", "all"),
        "business_goal": row.get("business_goal", _cfg(job).get("business_goal", "awareness")),
        "cta": _cfg(job).get("cta", ""),
        "length": _LENGTH_BY_TYPE.get(ptype, _LENGTH_BY_TYPE["blog"]),
        # the levers that make it specific, not generic:
        "audience_persona": persona,
        "audience_pain": pain,
        "differentiation_angles": angles[:3],
        "research_brief": _content_research(job, row),
        # WEBSITE-AWARE targeting: who this is for + which service it belongs to
        "audience_segment": tax.get("segment", ""),
        "service_pillar": tax.get("pillar", ""),
        "service_promise": tax.get("service", ""),
    }
    pb = _learnings(job)
    if pb:
        out["prior_learnings"] = {"winning_topics": pb.get("winning_topics", []),
                                  "avoid": pb.get("avoid", [])}
    return out


def _ensure_hero_image(job: dict) -> None:
    """Generate ONE on-brand hero image for the blog (matching the website's dark
    cyan/violet look) and embed it at the top of the body, so the piece is never
    image-less. Best-effort + cached: runs once, skips if no image API. Gated by
    CONTENT_IMAGES (default on) and blog/guide types only."""
    import os
    if os.getenv("CONTENT_IMAGES", "1") not in ("1", "true", "True"):
        return
    p = job.setdefault("payload", {})
    piece = p.get("content_producer") or {}
    if not piece or piece.get("image_url"):
        return
    if _chosen_row(job).get("type", "blog") not in ("blog", "guide"):
        return
    title = piece.get("title") or _chosen_row(job).get("working_title", "")
    try:
        import content_engine_site_taxonomy as TAX
        import content_engine_connectors as C
        import content_engine_brand as B
        ci = ""
        try:
            ci = B.get_ci_block() if hasattr(B, "get_ci_block") else ""
        except Exception:
            ci = ""
        url = C.generate_image(TAX.image_prompt(title, ci))
    except Exception:
        url = ""
    if url:
        piece["image_url"] = url
        body = piece.get("body", "") or ""
        if url not in body:                     # embed a markdown hero at the top
            piece["body"] = f"![{title}]({url})\n\n{body}"
        p["content_producer"] = piece
        p["image_url"] = url                    # dashboard web-view reads this too


def _in_seo_optimizer(job: dict) -> dict:
    _ensure_hero_image(job)                     # add the hero image before SEO/approval
    row = _chosen_row(job)
    cfg = _cfg(job)
    intent = cfg.get("intent") or _INTENT_BY_GOAL.get(
        cfg.get("business_goal", "awareness"), "informational")
    return {
        "content": _piece_content(job),
        "primary_keyword": row.get("primary_keyword", ""),
        "intent": intent,
    }


def _in_qa_compliance(job: dict) -> dict:
    brand = _brand(job)
    regulated = str(brand.get("regulated", "no")).lower() == "yes"
    disclaimers = _cfg(job).get("required_disclaimers") \
        or ([brand["disclaimers"]] if brand.get("disclaimers") else [])

    # Pipeline B: the "piece" is the cold email from outreach_copy (CAN-SPAM path).
    if job.get("type") == "outreach_campaign":
        oc = _result(job, "outreach_copy")
        body = oc.get("body", "")
        # QA must review the REAL email that sends. The Emailer appends a compliant
        # footer at send time (physical address + unsubscribe link — see
        # _outreach_emails). Reviewing the raw body false-blocks EVERY cold email
        # for "missing unsubscribe/address" that are actually there when it sends.
        content = body
        try:
            import content_engine_connectors as _c
            plain, _html = _c.Emailer().compose_outreach(body, job)
            if plain:
                content = plain
        except Exception:
            pass
        return {
            "content_type": "email_outreach",
            "content": content,
            "cta": oc.get("cta", ""),
            "is_regulated": regulated,
            "required_disclaimers": disclaimers,
        }

    # Pipeline A: the produced content piece, typed from its calendar row.
    ptype = _chosen_row(job).get("type", "blog")
    content_type = "blog" if ptype == "blog" else (
        "email_outreach" if ptype == "email" else "social")
    return {
        "content_type": content_type,
        "content": _piece_content(job),
        "cta": _result(job, "content_producer").get("cta_text", ""),
        "is_regulated": regulated,
        "required_disclaimers": disclaimers,
    }


def _in_analytics_funnel(job: dict) -> dict:
    a = job.get("payload", {}).get("analytics", {}) or {}
    return {
        "period": a.get("period", ""),
        "metrics": a.get("metrics", {"sessions": 0, "conv_rate": 0, "top_pages": []}),
        "funnel_stages": a.get("funnel_stages", []),
        "vs_previous": a.get("vs_previous",
                             {"sessions_change_pct": 0, "conv_change_pct": 0}),
    }


def _in_optimizer(job: dict) -> dict:
    p = job.get("payload", {}).get("performance", {}) or {}
    return {
        "content_performance": p.get("content_performance", []),
        "outreach_performance": p.get("outreach_performance", []),
        "period": p.get("period", ""),
    }


# ---------------------------------------------------------------------------
# Pipeline B mappers (working defaults; tighten with your real sources)
# ---------------------------------------------------------------------------
def _in_lead_qualifier(job: dict) -> dict:
    cfg = _cfg(job)
    # give each lead a stable id (its email) + the fields the qualifier profiles on,
    # so its per-lead results (business/pain/offer) map back to the lead record.
    src = job.get("payload", {}).get("leads", []) or []
    leads = []
    for L in src:
        leads.append({
            "id": (L.get("email") or L.get("company") or "").strip().lower(),
            "company": L.get("company", ""), "title": L.get("title", ""),
            "industry": L.get("industry", "") or L.get("domain", ""),
            "size": L.get("size", ""), "signals": L.get("signal", "") or L.get("source", ""),
        })
    return {
        "our_offer": cfg.get("our_offer") or _brand(job).get("offer", ""),
        "icp": cfg.get("icp", {"ideal_size": "", "ideal_industries": [], "pains_we_solve": []}),
        "leads": leads,
    }


def _in_segmenter(job: dict) -> dict:
    return {"buckets": job.get("payload", {}).get("buckets", [])}


def _in_outreach_copy(job: dict) -> dict:
    cfg = _cfg(job)
    try:
        import content_engine_connectors as _c
        booking = cfg.get("booking_url") or _c._env(
            "EMAIL_BOOKING_URL", "https://anthropos-automation.com/free-audit/")
        website = cfg.get("website") or _c._env("EMAIL_WEBSITE", "anthropos-automation.com")
    except Exception:
        booking = cfg.get("booking_url") or "https://anthropos-automation.com/free-audit/"
        website = cfg.get("website") or "anthropos-automation.com"
    try:
        import content_engine_safety as _safety
        _lead = _safety.clean_lead(job.get("payload", {}).get("lead", {}))
    except Exception:
        _lead = job.get("payload", {}).get("lead", {})
    out = {
        "category": job.get("payload", {}).get("category", "other"),
        "lead": _lead,   # S4: external lead text cleaned before it enters the prompt
        "our_offer": cfg.get("our_offer") or _brand(job).get("offer", ""),
        "proof_point": cfg.get("proof_point", ""),
        "sender_name": cfg.get("sender_name", "") or "Hasan",
        "sender_company": cfg.get("sender_company") or _brand(job).get("brand_name", "") or "Anthropos Automation",
        "website": website,
        "physical_address": cfg.get("physical_address", ""),
        "unsubscribe_token": job.get("payload", {}).get("unsubscribe_token", "{{unsubscribe_token}}"),
        "booking_url": booking,
    }
    pb = _learnings(job)
    if pb and pb.get("winning_email_subject_style"):
        out["winning_subject_style"] = pb["winning_email_subject_style"]
    if pb and pb.get("winning_email_subjects"):
        out["winning_subjects"] = pb["winning_email_subjects"]   # S2: subjects that booked calls
    return out


def _in_ads_optimizer(job: dict) -> dict:
    p = job.get("payload", {})
    ads = p.get("ads", {})
    seo = p.get("seo_signals")
    if not seo:
        # derive SEO signals from the content pipeline / learning playbook
        site = _result(job, "site_intelligence")
        pb = get_playbook(_client(job))
        seo = {
            "winning_keywords": pb.get("winning_topics", []),
            "ranking_pages": [],
            "content_opportunities": site.get("content_opportunities", []),
        }
    return {
        "goal": ads.get("goal", "leads"),
        "period": ads.get("period", ""),
        "monthly_budget": ads.get("monthly_budget", 0),
        "campaigns": ads.get("campaigns", []),
        "seo_signals": seo,
    }


def _in_media_buyer(job: dict) -> dict:
    """Feed the media buyer: the offer + ICP + the creatives handed over by the
    creative agents + any learnings. It drafts a Google Ads campaign from these."""
    p = job.get("payload", {})
    cfg = _cfg(job)
    icp = cfg.get("icp", {}) or {}
    pb = _learnings(job) or {}
    return {
        "offer": cfg.get("our_offer") or _brand(job).get("offer", ""),
        "goal": cfg.get("ad_goal", "leads"),
        "monthly_budget": cfg.get("ad_monthly_budget", 0),
        "landing_url": cfg.get("landing_url", ""),
        "icp": {
            "verticals": icp.get("ideal_industries") or icp.get("verticals", []),
            "countries": icp.get("countries", []),
            "deal_size": icp.get("ideal_size", ""),
        },
        "creatives": p.get("creatives", []),
        "past_learnings": {
            "winning_keywords": pb.get("winning_topics", []),
            "winning_campaign_themes": pb.get("winning_campaign_themes", []),  # S2
            "notes": pb.get("notes", ""),
        },
    }


_MAPPERS = {
    # Pipeline A
    "site_intelligence": _in_site_intelligence,
    "authority_backlinks": _in_site_intelligence,   # reuses the audit narrate input
    "competitor_intel": _in_competitor_intel,
    "content_strategist": _in_content_strategist,
    "content_producer": _in_content_producer,
    "content_producer_copy": _in_content_producer,
    "seo_optimizer": _in_seo_optimizer,
    "qa_compliance": _in_qa_compliance,
    "analytics_funnel": _in_analytics_funnel,
    "optimizer": _in_optimizer,
    # Pipeline B
    "lead_qualifier": _in_lead_qualifier,
    "segmenter": _in_segmenter,
    "outreach_copy": _in_outreach_copy,
    # Ads
    "ads_optimizer": _in_ads_optimizer,
    "media_buyer": _in_media_buyer,
}


def prepare_input(skill: str, job: dict) -> dict:
    """Shape one skill's INPUT from the job blackboard. Falls back to the raw
    payload for any skill without a dedicated mapper."""
    mapper = _MAPPERS.get(skill)
    return mapper(job) if mapper else job.get("payload", {})


# ---------------------------------------------------------------------------
# End-to-end wiring test: drive a full content job through the LIVE orchestrator
# with the LLM layer stubbed to canned, schema-valid outputs. Each stub call
# runs the REAL prepare_input, so this proves the chaining:
#   site -> competitor -> strategist(calendar) -> producer(row) -> seo -> qa.
# No API calls.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import content_engine_orchestrator as orch

    captured: dict[str, dict] = {}

    def canned(skill, inp):
        if skill == "site_intelligence":
            return {"health_score": 80, "top_issues": [], "quick_wins": [],
                    "content_opportunities": ["automate lead intake"],
                    "summary": "healthy"}
        if skill == "competitor_intel":
            return {"competitors": [], "market_gap": {"opportunity": "AEO guides",
                    "why_open": "nobody ranks"}, "differentiation_angles": []}
        if skill == "content_strategist":
            return {"week_of": "2026-07-20", "notes": "", "calendar": [{
                "date": "2026-07-21", "type": "blog",
                "working_title": "How law firms automate intake",
                "primary_keyword": "law firm automation",
                "target_segment": "all", "business_goal": "awareness",
                "priority": "high", "rationale": "gap"}]}
        if skill in ("content_producer", "content_producer_copy"):
            return {"title": inp["working_title"], "body": "Body about " + inp["primary_keyword"],
                    "meta_title": "t", "meta_description": "d",
                    "cta_text": inp.get("cta", ""), "hashtags": []}
        if skill == "seo_optimizer":
            return {"seo_ready": True, "checks": {}, "fixes": []}
        if skill == "qa_compliance":
            return {"verdict": "pass", "brand_voice_match": True, "issues": [],
                    "claims_check": {"all_defensible": True, "flagged_claims": []},
                    "compliance": {}}
        if skill == "analytics_funnel":
            return {"headline": "ok", "what_worked": [], "what_dropped": [],
                    "biggest_leak": {}, "recommended_focus_next": ""}
        if skill == "optimizer":
            return {"insights": [], "double_down": [], "reduce_or_cut": [],
                    "next_cycle": {}}
        return {"ok": True}

    def stub_llm(job, skill, store):
        inp = prepare_input(skill, job)     # exercise the real mapper
        captured[skill] = inp
        return canned(skill, inp), 0.004

    orch._LLM_HOOK = stub_llm

    store = orch.InMemoryJobStore()
    job = orch.new_job(
        "job_e2e", "content_piece",
        {"brand_name": "Anthropos", "offer": "AI automation", "regulated": "no"},
        {"config": {"business_goal": "awareness", "cta": "Book a consultation",
                    "produce_index": 0},
         "audit": {"site_url": "https://x.com", "existing_topics": ["intake"],
                   "top_gsc_queries": [{"query": "law automation", "position": 8,
                                        "impressions": 100, "clicks": 3}]},
         "competitors": [{"name": "RivalCo", "external_content": "some text"}],
         "analytics": {"period": "Jul", "metrics": {}, "funnel_stages": []},
         "performance": {"content_performance": [], "period": "Jul"}})
    store.put(job)

    # Run to the human gate, approve, publish, then the measurement gate.
    s = orch.tick(store)
    assert s == "AWAITING_APPROVAL", f"expected gate, got {s}"
    orch.approve("job_e2e", store)
    s = orch.tick(store)
    assert s == "published", f"expected measure-wait, got {s}"
    job["ready_to_measure"] = True
    store.save(job)
    s = orch.tick(store)
    assert s == "optimized", f"expected optimized, got {s}"

    # Prove the chaining actually happened through the mappers:
    assert captured["competitor_intel"]["client_topics"] == ["intake"], \
        "competitor_intel did not read the audit topics"
    assert captured["content_strategist"]["competitor_gaps"]["market_gap"]["opportunity"] \
        == "AEO guides", "strategist did not read competitor_intel output"
    assert captured["content_producer"]["working_title"] == "How law firms automate intake", \
        "producer did not read the chosen calendar row"
    assert captured["content_producer"]["primary_keyword"] == "law firm automation"
    assert "law firm automation" in captured["seo_optimizer"]["content"], \
        "seo_optimizer did not read the produced body"
    assert captured["seo_optimizer"]["intent"] == "informational", "intent mapping wrong"
    assert captured["qa_compliance"]["content_type"] == "blog", "qa content_type wrong"
    assert captured["qa_compliance"]["cta"] == "Book a consultation", \
        "qa did not read producer cta_text"

    orch._LLM_HOOK = orch.run_llm_skill  # restore
    print("OK — Pipeline A chained end-to-end through prepare_input: "
          "site -> competitor -> strategist -> producer -> seo -> qa -> gate -> "
          "publish -> analytics -> optimizer. (LLM stubbed; no API calls.)")
