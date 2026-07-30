"""
content_engine_ads.py
============================================================================
M1-M14 — THE MEDIA BUYER'S DATA LAYER.

Everything a senior media buyer reads before making a decision, pulled from the
official Google Ads API (which costs nothing) via GAQL.

Key-gated by design: the Ads account is not connected yet, so every pull
returns {"connected": False, "reason": ...} rather than a fabricated number.
The boards render the reason and a Connect button — same contract as
DataForSEO on the SEO side.

    account()        campaigns, types, status, budgets, IS metrics
    search_terms()   L4 — the highest-frequency task in any Ads account
    keywords()       L6 — with Quality Score and its three components
    ad_assets()      L17/L18 — RSA assets + extensions, with performance labels
    segments()       L7/L11 — device, geo, hour, day
    conversion_actions()  L3 — tracking integrity
    targeting()      L14 — presence-vs-interest, the silent waste source
    audiences()      L15
    change_history() L19
    recommendations() Google's own suggestions + optimisation score
    keyword_ideas()  L16 — Keyword Planner. Google's own tool, no vendor needed.

Plus the piece that has nothing to do with the API:

    unit_economics() L9 — average deal value x margin x close rate -> the
                     target CPA and target ROAS that make every other number
                     mean something. Works today.

Run offline self-check:  python content_engine_ads.py
============================================================================
"""

from __future__ import annotations

import logging

log = logging.getLogger("ads")

ECON_KEY = "ads_unit_economics"
SNAP_KEY = "ads_snapshot"

_OFF = {"connected": False,
        "reason": ("Google Ads is not connected — the credentials are still "
                   "placeholders. Everything on this board is one OAuth away; "
                   "the API itself is free.")}


def _ads():
    import content_engine_connectors as C
    return C.GoogleAds()


def _query(gaql: str, cost_note: str = ""):
    """Run one GAQL query. -> (rows, error). Never raises, never invents."""
    g = _ads()
    if not g.available():
        return [], _OFF["reason"]
    try:
        import content_engine_connectors as C
        tok = g._access_token()
        if not tok:
            return [], "Google rejected the credentials (no access token)."
        j = C._post_json(f"{g._base()}/googleAds:searchStream",
                         {"query": gaql}, headers=g._headers(tok))
        if j is None:
            return [], "The Google Ads API call failed — see the System Map diagnostic."
        rows = []
        for batch in (j if isinstance(j, list) else [j]):
            rows.extend(batch.get("results", []) or [])
        return rows, ""
    except Exception as e:
        log.warning("GAQL failed: %s", e)
        return [], f"{type(e).__name__}: {e}"


def _m(r, *path, default=0):
    """Safely walk a nested Google Ads response node."""
    cur = r
    for p in path:
        cur = (cur or {}).get(p)
        if cur is None:
            return default
    return cur


def _micros(v):
    try:
        return round(float(v or 0) / 1e6, 2)
    except (TypeError, ValueError):
        return 0.0


# ======================================================================
#  L9 — UNIT ECONOMICS.  No API needed. This is what makes a CPC judgeable.
# ======================================================================
DEFAULT_ECON = {"avg_deal_value": 0.0, "gross_margin_pct": 0.0,
                "consult_to_client_pct": 0.0, "lead_to_consult_pct": 0.0,
                "currency": "EUR"}


def get_economics(store=None) -> dict:
    if store is not None:
        try:
            saved = store.get_setting(ECON_KEY, None)
            if saved:
                return {**DEFAULT_ECON, **saved}
        except Exception:
            pass
    return dict(DEFAULT_ECON)


def set_economics(store, **kw) -> dict:
    econ = get_economics(store)
    for k, v in kw.items():
        if k in DEFAULT_ECON and v not in (None, ""):
            try:
                econ[k] = float(v) if k != "currency" else str(v)
            except (TypeError, ValueError):
                pass
    try:
        store.set_setting(ECON_KEY, econ)
    except Exception as e:
        log.warning("economics save failed: %s", e)
    return econ


def targets(econ: dict) -> dict:
    """Turn business economics into the numbers a media buyer bids against.

    A CPC is not 'good' or 'bad' on its own — it is good relative to what a
    customer is worth. This is the calculation that judgement rests on, and
    nothing in the engine had it.
    """
    deal = float(econ.get("avg_deal_value") or 0)
    margin = float(econ.get("gross_margin_pct") or 0) / 100.0
    close = float(econ.get("consult_to_client_pct") or 0) / 100.0
    l2c = float(econ.get("lead_to_consult_pct") or 0) / 100.0
    if not (deal and margin and close):
        return {"ready": False,
                "reason": ("Enter average deal value, gross margin % and "
                           "consult-to-client % — three numbers — and every CPC, "
                           "CPA and ROAS on this board becomes judgeable.")}
    gross_per_client = deal * margin
    max_cpa_client = gross_per_client                 # break-even per CLIENT
    target_cpa_client = gross_per_client * 0.30       # keep 70% of the margin
    max_cpa_consult = max_cpa_client * close
    target_cpa_consult = target_cpa_client * close
    target_cpa_lead = target_cpa_consult * l2c if l2c else 0.0
    target_roas = (1 / 0.30) if margin else 0.0
    return {"ready": True,
            "gross_per_client": round(gross_per_client, 2),
            "break_even_cpa_client": round(max_cpa_client, 2),
            "target_cpa_client": round(target_cpa_client, 2),
            "break_even_cpa_consult": round(max_cpa_consult, 2),
            "target_cpa_consult": round(target_cpa_consult, 2),
            "target_cpa_lead": round(target_cpa_lead, 2),
            "target_roas": round(target_roas, 1),
            "currency": econ.get("currency", "EUR")}


def judge_cpc(cpc: float, conv_rate_pct: float, tgt: dict) -> dict:
    """Is this CPC good? Only answerable with the economics above."""
    if not tgt.get("ready") or not conv_rate_pct:
        return {"verdict": "unknown", "reason": "needs unit economics + a conversion rate"}
    cpa = float(cpc or 0) / (conv_rate_pct / 100.0)
    target = tgt["target_cpa_lead"] or tgt["target_cpa_consult"]
    if not target:
        return {"verdict": "unknown", "reason": "no target CPA yet"}
    ratio = cpa / target
    verdict = ("good" if ratio <= 1 else "watch" if ratio <= 1.5 else "losing money")
    return {"verdict": verdict, "implied_cpa": round(cpa, 2),
            "target_cpa": round(target, 2), "ratio": round(ratio, 2)}


# ======================================================================
#  THE GOOGLE ADS PULLS  (all key-gated)
# ======================================================================
def account(days: int = 30) -> dict:
    """L1/L7/L13 — every campaign with its type, status, budget and the
    impression-share metrics that separate 'spend more' from 'fix quality'."""
    rows, err = _query(f"""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type, campaign.bidding_strategy_type,
               campaign_budget.amount_micros, metrics.cost_micros, metrics.clicks,
               metrics.impressions, metrics.conversions, metrics.conversions_value,
               metrics.search_impression_share,
               metrics.search_budget_lost_impression_share,
               metrics.search_rank_lost_impression_share, metrics.ctr,
               metrics.average_cpc
        FROM campaign WHERE segments.date DURING LAST_{days}_DAYS""")
    if err:
        return {"connected": False, "reason": err, "campaigns": []}
    camps = []
    for r in rows:
        c, m, b = r.get("campaign", {}), r.get("metrics", {}), r.get("campaignBudget", {})
        camps.append({
            "id": c.get("id"), "name": c.get("name", ""), "status": c.get("status", ""),
            "type": c.get("advertisingChannelType", ""),
            "bid_strategy": c.get("biddingStrategyType", ""),
            "budget": _micros(b.get("amountMicros")),
            "cost": _micros(m.get("costMicros")),
            "clicks": int(float(m.get("clicks", 0) or 0)),
            "impressions": int(float(m.get("impressions", 0) or 0)),
            "conversions": round(float(m.get("conversions", 0) or 0), 1),
            "conv_value": round(float(m.get("conversionsValue", 0) or 0), 2),
            "ctr": round(float(m.get("ctr", 0) or 0) * 100, 2),
            "avg_cpc": _micros(m.get("averageCpc")),
            "is_share": round(float(m.get("searchImpressionShare", 0) or 0) * 100, 1),
            "is_lost_budget": round(float(m.get("searchBudgetLostImpressionShare", 0) or 0) * 100, 1),
            "is_lost_rank": round(float(m.get("searchRankLostImpressionShare", 0) or 0) * 100, 1)})
    by_type = {}
    for c in camps:
        by_type[c["type"] or "UNKNOWN"] = by_type.get(c["type"] or "UNKNOWN", 0) + c["cost"]
    return {"connected": True, "campaigns": camps, "by_type": by_type,
            "spend": round(sum(c["cost"] for c in camps), 2),
            "conversions": round(sum(c["conversions"] for c in camps), 1),
            "conv_value": round(sum(c["conv_value"] for c in camps), 2),
            "enabled": sum(1 for c in camps if c["status"] == "ENABLED")}


def search_terms(days: int = 30, limit: int = 300) -> dict:
    """L4 — what people ACTUALLY typed. The single highest-ROI report there is."""
    rows, err = _query(f"""
        SELECT search_term_view.search_term, search_term_view.status,
               campaign.name, ad_group.name, metrics.cost_micros, metrics.clicks,
               metrics.impressions, metrics.conversions
        FROM search_term_view WHERE segments.date DURING LAST_{days}_DAYS
        ORDER BY metrics.cost_micros DESC LIMIT {limit}""")
    if err:
        return {"connected": False, "reason": err, "terms": []}
    terms = [{"term": _m(r, "searchTermView", "searchTerm", default=""),
              "status": _m(r, "searchTermView", "status", default=""),
              "campaign": _m(r, "campaign", "name", default=""),
              "ad_group": _m(r, "adGroup", "name", default=""),
              "cost": _micros(_m(r, "metrics", "costMicros")),
              "clicks": int(float(_m(r, "metrics", "clicks") or 0)),
              "impressions": int(float(_m(r, "metrics", "impressions") or 0)),
              "conversions": round(float(_m(r, "metrics", "conversions") or 0), 1)}
             for r in rows]
    return {"connected": True, "terms": terms, **waste(terms)}


def waste(terms: list, min_clicks: int = 3) -> dict:
    """Terms that cost money and returned nothing — the negative-keyword list."""
    bad = [t for t in terms or []
           if t.get("clicks", 0) >= min_clicks and not t.get("conversions")]
    bad.sort(key=lambda t: -t.get("cost", 0))
    total = sum(t.get("cost", 0) for t in terms or []) or 1
    wasted = sum(t.get("cost", 0) for t in bad)
    return {"wasted_spend": round(wasted, 2),
            "wasted_pct": round(100 * wasted / total, 1),
            "waste_terms": bad[:50],
            "negative_candidates": [t["term"] for t in bad[:50]],
            "converting_terms": sorted(
                [t for t in terms or [] if t.get("conversions")],
                key=lambda t: -t["conversions"])[:30]}


def keywords(days: int = 30, limit: int = 300) -> dict:
    """L6 — Quality Score and its three components, per keyword."""
    rows, err = _query(f"""
        SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
               ad_group_criterion.quality_info.quality_score,
               ad_group_criterion.quality_info.creative_quality_score,
               ad_group_criterion.quality_info.post_click_quality_score,
               ad_group_criterion.quality_info.search_predicted_ctr,
               campaign.name, metrics.cost_micros, metrics.clicks,
               metrics.conversions, metrics.average_cpc
        FROM keyword_view WHERE segments.date DURING LAST_{days}_DAYS
        ORDER BY metrics.cost_micros DESC LIMIT {limit}""")
    if err:
        return {"connected": False, "reason": err, "keywords": []}
    kws = [{"text": _m(r, "adGroupCriterion", "keyword", "text", default=""),
            "match": _m(r, "adGroupCriterion", "keyword", "matchType", default=""),
            "qs": int(_m(r, "adGroupCriterion", "qualityInfo", "qualityScore") or 0),
            "ad_relevance": _m(r, "adGroupCriterion", "qualityInfo",
                               "creativeQualityScore", default=""),
            "landing_page": _m(r, "adGroupCriterion", "qualityInfo",
                               "postClickQualityScore", default=""),
            "exp_ctr": _m(r, "adGroupCriterion", "qualityInfo",
                          "searchPredictedCtr", default=""),
            "campaign": _m(r, "campaign", "name", default=""),
            "cost": _micros(_m(r, "metrics", "costMicros")),
            "clicks": int(float(_m(r, "metrics", "clicks") or 0)),
            "conversions": round(float(_m(r, "metrics", "conversions") or 0), 1),
            "avg_cpc": _micros(_m(r, "metrics", "averageCpc"))} for r in rows]
    scored = [k for k in kws if k["qs"]]
    return {"connected": True, "keywords": kws,
            "avg_qs": round(sum(k["qs"] for k in scored) / max(len(scored), 1), 1),
            "low_qs": sorted([k for k in scored if k["qs"] <= 4],
                             key=lambda k: -k["cost"])[:30],
            "qs_distribution": {str(i): sum(1 for k in scored if k["qs"] == i)
                                for i in range(1, 11)}}


def ad_assets(days: int = 30) -> dict:
    """L17/L18 — RSA assets and extensions, with Google's performance labels."""
    rows, err = _query(f"""
        SELECT ad_group_ad_asset_view.field_type,
               ad_group_ad_asset_view.performance_label, asset.text_asset.text,
               campaign.name, metrics.impressions, metrics.clicks
        FROM ad_group_ad_asset_view WHERE segments.date DURING LAST_{days}_DAYS
        LIMIT 300""")
    if err:
        return {"connected": False, "reason": err, "assets": []}
    assets = [{"field": _m(r, "adGroupAdAssetView", "fieldType", default=""),
               "label": _m(r, "adGroupAdAssetView", "performanceLabel", default=""),
               "text": _m(r, "asset", "textAsset", "text", default=""),
               "campaign": _m(r, "campaign", "name", default=""),
               "impressions": int(float(_m(r, "metrics", "impressions") or 0)),
               "clicks": int(float(_m(r, "metrics", "clicks") or 0))} for r in rows]
    labels = {}
    for a in assets:
        labels[a["label"] or "UNSPECIFIED"] = labels.get(a["label"] or "UNSPECIFIED", 0) + 1
    return {"connected": True, "assets": assets, "labels": labels,
            "low": [a for a in assets if a["label"] == "LOW"][:30],
            "best": [a for a in assets if a["label"] == "BEST"][:20]}


def segments(days: int = 30) -> dict:
    """L7/L11 — device, hour, day, geo. Every bid adjustment lives here."""
    out = {"connected": True}
    for name, dim, field in (("device", "segments.device", "device"),
                             ("hour", "segments.hour", "hour"),
                             ("day", "segments.day_of_week", "dayOfWeek")):
        rows, err = _query(f"""
            SELECT {dim}, metrics.cost_micros, metrics.clicks, metrics.conversions,
                   metrics.impressions
            FROM campaign WHERE segments.date DURING LAST_{days}_DAYS""")
        if err:
            return {"connected": False, "reason": err}
        agg = {}
        for r in rows:
            k = str(_m(r, "segments", field, default="?"))
            a = agg.setdefault(k, {"cost": 0.0, "clicks": 0, "conversions": 0.0})
            a["cost"] += _micros(_m(r, "metrics", "costMicros"))
            a["clicks"] += int(float(_m(r, "metrics", "clicks") or 0))
            a["conversions"] += float(_m(r, "metrics", "conversions") or 0)
        out[name] = {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in agg.items()}
    rows, err = _query(f"""
        SELECT geographic_view.country_criterion_id, metrics.cost_micros,
               metrics.clicks, metrics.conversions
        FROM geographic_view WHERE segments.date DURING LAST_{days}_DAYS LIMIT 60""")
    out["geo"] = [] if err else [
        {"country_id": _m(r, "geographicView", "countryCriterionId", default=""),
         "cost": _micros(_m(r, "metrics", "costMicros")),
         "clicks": int(float(_m(r, "metrics", "clicks") or 0)),
         "conversions": round(float(_m(r, "metrics", "conversions") or 0), 1)}
        for r in rows]
    return out


def conversion_actions() -> dict:
    """L3 — if the tags are broken every ROAS number is fiction."""
    rows, err = _query("""
        SELECT conversion_action.name, conversion_action.status,
               conversion_action.type, conversion_action.category,
               conversion_action.counting_type,
               conversion_action.primary_for_goal
        FROM conversion_action LIMIT 100""")
    if err:
        return {"connected": False, "reason": err, "actions": []}
    acts = [{"name": _m(r, "conversionAction", "name", default=""),
             "status": _m(r, "conversionAction", "status", default=""),
             "type": _m(r, "conversionAction", "type", default=""),
             "category": _m(r, "conversionAction", "category", default=""),
             "counting": _m(r, "conversionAction", "countingType", default=""),
             "primary": bool(_m(r, "conversionAction", "primaryForGoal", default=False))}
            for r in rows]
    return {"connected": True, "actions": acts,
            "enabled": sum(1 for a in acts if a["status"] == "ENABLED"),
            "primary": sum(1 for a in acts if a["primary"]),
            "offline": sum(1 for a in acts if "UPLOAD" in (a["type"] or ""))}


def targeting() -> dict:
    """L14 — presence vs presence-OR-INTEREST is one of the biggest silent
    waste sources in Google Ads, and you run five markets."""
    rows, err = _query("""
        SELECT campaign.name, campaign.geo_target_type_setting.positive_geo_target_type,
               campaign.geo_target_type_setting.negative_geo_target_type
        FROM campaign LIMIT 100""")
    if err:
        return {"connected": False, "reason": err, "campaigns": []}
    camps = [{"campaign": _m(r, "campaign", "name", default=""),
              "positive": _m(r, "campaign", "geoTargetTypeSetting",
                             "positiveGeoTargetType", default=""),
              "negative": _m(r, "campaign", "geoTargetTypeSetting",
                             "negativeGeoTargetType", default="")} for r in rows]
    risky = [c for c in camps if "INTEREST" in (c["positive"] or "")]
    locs, lerr = _query("""
        SELECT campaign.name, campaign_criterion.location.geo_target_constant,
               campaign_criterion.negative, campaign_criterion.bid_modifier
        FROM campaign_criterion WHERE campaign_criterion.type = 'LOCATION' LIMIT 200""")
    return {"connected": True, "campaigns": camps, "presence_risk": risky,
            "locations": [] if lerr else [
                {"campaign": _m(r, "campaign", "name", default=""),
                 "geo": _m(r, "campaignCriterion", "location",
                           "geoTargetConstant", default=""),
                 "negative": bool(_m(r, "campaignCriterion", "negative", default=False)),
                 "bid_modifier": _m(r, "campaignCriterion", "bidModifier", default=None)}
                for r in locs]}


def audiences(days: int = 30) -> dict:
    """L15 — remarketing, in-market, customer match; observation vs targeting."""
    rows, err = _query(f"""
        SELECT campaign.name, ad_group_criterion.type,
               ad_group_criterion.user_list.user_list,
               metrics.cost_micros, metrics.conversions, metrics.clicks
        FROM ad_group_audience_view WHERE segments.date DURING LAST_{days}_DAYS
        LIMIT 200""")
    if err:
        return {"connected": False, "reason": err, "audiences": []}
    return {"connected": True, "audiences": [
        {"campaign": _m(r, "campaign", "name", default=""),
         "type": _m(r, "adGroupCriterion", "type", default=""),
         "cost": _micros(_m(r, "metrics", "costMicros")),
         "clicks": int(float(_m(r, "metrics", "clicks") or 0)),
         "conversions": round(float(_m(r, "metrics", "conversions") or 0), 1)}
        for r in rows]}


def ad_status() -> dict:
    """L2 — a disapproved ad silently stops serving. Nothing was watching."""
    rows, err = _query("""
        SELECT ad_group_ad.status, ad_group_ad.policy_summary.approval_status,
               ad_group_ad.ad.type, campaign.name
        FROM ad_group_ad LIMIT 300""")
    if err:
        return {"connected": False, "reason": err, "ads": []}
    ads = [{"status": _m(r, "adGroupAd", "status", default=""),
            "approval": _m(r, "adGroupAd", "policySummary",
                           "approvalStatus", default=""),
            "type": _m(r, "adGroupAd", "ad", "type", default=""),
            "campaign": _m(r, "campaign", "name", default="")} for r in rows]
    return {"connected": True, "ads": ads,
            "disapproved": [a for a in ads if a["approval"] == "DISAPPROVED"],
            "limited": [a for a in ads if a["approval"] == "APPROVED_LIMITED"],
            "enabled": sum(1 for a in ads if a["status"] == "ENABLED")}


def change_history(days: int = 30) -> dict:
    """L19 — what changed, when, and by whom."""
    rows, err = _query(f"""
        SELECT change_event.change_date_time, change_event.change_resource_type,
               change_event.user_email, change_event.client_type
        FROM change_event WHERE change_event.change_date_time DURING LAST_{days}_DAYS
        LIMIT 200""")
    if err:
        return {"connected": False, "reason": err, "changes": []}
    return {"connected": True, "changes": [
        {"at": _m(r, "changeEvent", "changeDateTime", default=""),
         "resource": _m(r, "changeEvent", "changeResourceType", default=""),
         "user": _m(r, "changeEvent", "userEmail", default=""),
         "client": _m(r, "changeEvent", "clientType", default="")} for r in rows]}


def recommendations() -> dict:
    """Google's own suggestions + the optimisation score."""
    rows, err = _query("""
        SELECT recommendation.type, recommendation.campaign,
               recommendation.impact.potential_metrics.conversions
        FROM recommendation LIMIT 100""")
    if err:
        return {"connected": False, "reason": err, "recommendations": []}
    by_type = {}
    for r in rows:
        t = _m(r, "recommendation", "type", default="?")
        by_type[t] = by_type.get(t, 0) + 1
    return {"connected": True, "count": len(rows), "by_type": by_type}


def keyword_ideas(seed_keywords: list, limit: int = 60) -> dict:
    """L16 — Keyword Planner. Google's own volume and CPC data, free with the
    API. No Semrush, no Ahrefs, no third-party keyword tool needed."""
    g = _ads()
    if not g.available():
        return {"connected": False, "reason": _OFF["reason"], "ideas": []}
    try:
        import content_engine_connectors as C
        tok = g._access_token()
        if not tok:
            return {"connected": False, "reason": "no access token", "ideas": []}
        j = C._post_json(
            f"https://googleads.googleapis.com/{g.ver}/customers/{g.cid}:generateKeywordIdeas",
            {"keywordSeed": {"keywords": [k for k in (seed_keywords or [])[:20] if k]},
             "geoTargetConstants": [], "includeAdultKeywords": False},
            headers=g._headers(tok))
        ideas = []
        for r in ((j or {}).get("results") or [])[:limit]:
            m = r.get("keywordIdeaMetrics", {}) or {}
            ideas.append({"keyword": r.get("text", ""),
                          "volume": int(m.get("avgMonthlySearches", 0) or 0),
                          "competition": m.get("competition", ""),
                          "low_bid": _micros(m.get("lowTopOfPageBidMicros")),
                          "high_bid": _micros(m.get("highTopOfPageBidMicros"))})
        return {"connected": True, "ideas": sorted(ideas, key=lambda i: -i["volume"])}
    except Exception as e:
        return {"connected": False, "reason": f"{type(e).__name__}: {e}", "ideas": []}


# ======================================================================
#  DERIVED DIAGNOSTICS (pure code on whatever was pulled)
# ======================================================================
def pacing(campaigns: list, day_of_month: int, days_in_month: int = 30) -> dict:
    """L12 — projected month-end spend vs the budget."""
    spend = sum(c.get("cost", 0) for c in campaigns or [])
    daily_budget = sum(c.get("budget", 0) for c in campaigns or [])
    month_budget = daily_budget * days_in_month
    if not day_of_month:
        return {"ready": False}
    projected = spend / day_of_month * days_in_month
    return {"ready": True, "spend": round(spend, 2),
            "month_budget": round(month_budget, 2),
            "projected": round(projected, 2),
            "pace_pct": round(100 * projected / month_budget, 1) if month_budget else 0,
            "status": ("over" if month_budget and projected > month_budget * 1.05
                       else "under" if month_budget and projected < month_budget * 0.85
                       else "on track")}


def impression_share_verdict(c: dict) -> dict:
    """L7 — the diagnostic that decides between 'add budget' and 'fix quality'."""
    budget_lost = c.get("is_lost_budget", 0)
    rank_lost = c.get("is_lost_rank", 0)
    if budget_lost > rank_lost and budget_lost > 10:
        return {"verdict": "budget", "action": "Raise the budget — you are being "
                "capped out of auctions you would otherwise win.", "pct": budget_lost}
    if rank_lost > 10:
        return {"verdict": "rank", "action": "Do NOT add budget. Fix Quality Score, "
                "bids or ad relevance — you are losing on rank, not money.",
                "pct": rank_lost}
    return {"verdict": "healthy", "action": "Impression share is not the constraint.",
            "pct": c.get("is_share", 0)}


def bid_strategy_advice(c: dict, tgt: dict) -> dict:
    """L10 — is this campaign on the right bid strategy for its data volume?"""
    conv = c.get("conversions", 0)
    strat = (c.get("bid_strategy") or "").upper()
    if conv < 15 and strat in ("TARGET_CPA", "TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE"):
        return {"ok": False, "advice": (
            f"{strat} needs roughly 15-30 conversions a month to learn; this "
            f"campaign has {conv}. Maximise Clicks or Manual CPC will behave "
            "more predictably until volume builds.")}
    if conv >= 30 and strat in ("MANUAL_CPC", "MAXIMIZE_CLICKS"):
        return {"ok": False, "advice": (
            f"{conv} conversions is enough for smart bidding. Target CPA at "
            f"{tgt.get('target_cpa_lead') or tgt.get('target_cpa_consult') or '—'} "
            "would let Google bid per-auction.")}
    return {"ok": True, "advice": "Bid strategy suits the current data volume."}


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    # ---- unit economics: the part that works with no API at all ----
    e = dict(DEFAULT_ECON)
    assert targets(e)["ready"] is False, "no economics -> honest 'not ready'"
    e.update(avg_deal_value=5000, gross_margin_pct=60,
             consult_to_client_pct=25, lead_to_consult_pct=40)
    t = targets(e)
    assert t["ready"] and t["gross_per_client"] == 3000.0, t
    assert t["break_even_cpa_client"] == 3000.0 and t["target_cpa_client"] == 900.0, t
    assert t["break_even_cpa_consult"] == 750.0, t          # 3000 * 0.25
    assert t["target_cpa_consult"] == 225.0, t              # 900 * 0.25
    assert t["target_cpa_lead"] == 90.0, t                  # 225 * 0.40
    assert t["target_roas"] == 3.3, t

    j = judge_cpc(cpc=4.0, conv_rate_pct=5.0, tgt=t)        # -> CPA 80 vs target 90
    assert j["verdict"] == "good" and j["implied_cpa"] == 80.0, j
    assert judge_cpc(12.0, 5.0, t)["verdict"] == "losing money", judge_cpc(12.0, 5.0, t)
    assert judge_cpc(5.5, 5.0, t)["verdict"] == "watch", judge_cpc(5.5, 5.0, t)
    assert judge_cpc(4.0, 0, t)["verdict"] == "unknown"

    # ---- every Ads pull must degrade honestly, never invent ----
    for fn, key in ((account, "campaigns"), (search_terms, "terms"),
                    (keywords, "keywords"), (ad_assets, "assets"),
                    (conversion_actions, "actions"), (targeting, "campaigns"),
                    (audiences, "audiences"), (ad_status, "ads"),
                    (change_history, "changes"), (recommendations, "recommendations")):
        out = fn()
        assert out["connected"] is False, f"{fn.__name__} claimed a connection"
        assert "not connected" in out["reason"] or "placeholder" in out["reason"], out
        assert out.get(key) == [], f"{fn.__name__} must return an empty {key}"
    assert keyword_ideas(["automation"])["connected"] is False
    assert segments()["connected"] is False

    # ---- derived diagnostics work on data from anywhere ----
    p = pacing([{"cost": 300, "budget": 20}], day_of_month=10, days_in_month=30)
    assert p["projected"] == 900.0 and p["month_budget"] == 600.0, p
    assert p["status"] == "over", p
    assert pacing([{"cost": 100, "budget": 20}], 10)["status"] == "under"

    v = impression_share_verdict({"is_lost_budget": 40, "is_lost_rank": 5})
    assert v["verdict"] == "budget" and "Raise the budget" in v["action"], v
    v2 = impression_share_verdict({"is_lost_budget": 3, "is_lost_rank": 45})
    assert v2["verdict"] == "rank" and "Do NOT add budget" in v2["action"], v2
    assert impression_share_verdict({"is_lost_budget": 2, "is_lost_rank": 3})["verdict"] == "healthy"

    a = bid_strategy_advice({"conversions": 2, "bid_strategy": "TARGET_CPA"}, t)
    assert not a["ok"] and "15-30 conversions" in a["advice"], a
    a2 = bid_strategy_advice({"conversions": 50, "bid_strategy": "MANUAL_CPC"}, t)
    assert not a2["ok"] and "smart bidding" in a2["advice"], a2
    assert bid_strategy_advice({"conversions": 50, "bid_strategy": "TARGET_CPA"}, t)["ok"]

    w = waste([{"term": "free automation", "clicks": 9, "conversions": 0, "cost": 45.0},
               {"term": "automation agency", "clicks": 6, "conversions": 2, "cost": 55.0},
               {"term": "x", "clicks": 1, "conversions": 0, "cost": 2.0}])
    assert w["wasted_spend"] == 45.0 and w["negative_candidates"] == ["free automation"], w
    assert w["wasted_pct"] == 44.1, w["wasted_pct"]
    assert w["converting_terms"][0]["term"] == "automation agency", w

    class _S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v
    st = _S()
    assert get_economics(st)["avg_deal_value"] == 0.0
    set_economics(st, avg_deal_value=5000, gross_margin_pct=60, consult_to_client_pct=25)
    assert get_economics(st)["avg_deal_value"] == 5000.0
    assert targets(get_economics(st))["ready"] is True
    print("ads self-check OK — unit economics, CPC judgement, pacing, impression "
          "share verdict, bid strategy advice, waste math, honest degrade on all "
          "10 API pulls")
