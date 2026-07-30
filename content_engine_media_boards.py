"""
content_engine_media_boards.py
============================================================================
THE MEDIA BUYER'S BOARDS — 16 boards, 296 cards, in the same UI system as
SEO/AEO/GEO: four groups, card ids, severity sort, a CTA on every card,
progressive disclosure, 11 chart types.

The card kit is imported from content_engine_seo_boards rather than copied,
so a fix to the card component fixes both sections at once.

Google Ads is not connected yet. Cards that need it say so and offer a Connect
button — the same honest-degrade contract as DataForSEO on the SEO side. The
boards that DON'T need it (landing page match, competition, cross-channel
interlock, unit economics) work today.

Run offline self-check:  python content_engine_media_boards.py
============================================================================
"""

from __future__ import annotations

import re

from content_engine_seo_boards import (
    TEAL, VIOLET, BLUE, GREEN, AMBER, PINK, _H, _CH, _pct_color, _link, _rows,
    _linkrows, _donut, _split_donut, _trend, _spark, _hbars, _gauge, _score_gauge,
    _histogram, _heatmap, _riskmatrix, _statusgrid, _treemap, _waterfall, _delta,
    _viz, _vizcards, _head, _sub, _subnav, _slug, _CURRENT_BOARD, _TAB_CSS,
    BOARD_CTA, VISIBLE_CARDS,
)

# The media boards get their own CTA map, merged into the shared registry so
# _viz() picks the right action for whichever board is rendering.
BOARD_CTA.update({
    "Media Command": ("Refresh Google Ads", "runAds()"),
    "Account Health": ("Refresh Google Ads", "runAds()"),
    "Campaign Types": ("Refresh Google Ads", "runAds()"),
    "Search Terms": ("Pull search terms", "runAds()"),
    "Keywords & QS": ("Refresh Google Ads", "runAds()"),
    "Bidding": ("Refresh Google Ads", "runAds()"),
    "Budget & Pacing": ("Refresh Google Ads", "runAds()"),
    "Targeting": ("Refresh Google Ads", "runAds()"),
    "Audiences": ("Refresh Google Ads", "runAds()"),
    "Ads & Assets": ("Refresh Google Ads", "runAds()"),
    "Conversion": ("Refresh Google Ads", "runAds()"),
    "Landing Pages": ("Re-crawl the site", "runCrawl()"),
    "Competition": ("Scan competitors", "scanCompetitors()"),
    "Keyword Research": ("Get keyword ideas", "runAds()"),
    "Interlock": ("Rebuild the interlock", "runInterlock()"),
    "Media Work Orders": ("Refresh Google Ads", "runAds()"),
})

_CONNECT = ("Connect Google Ads on the System Map. The API itself is free — "
            "this needs an OAuth client, a refresh token, and Google's "
            "approval of the developer token.")


_DICT_KEYS = ("ads", "terms", "kw", "assets", "conv_actions", "targeting",
              "audiences", "ad_status", "changes", "recs", "kw_ideas", "econ",
              "targets", "interlock", "crawl", "geo", "competitor_intel",
              "pacing", "is_summary")
_LIST_KEYS = ("markets", "is_rows", "bid_advice", "funnel", "orders")


def _ctx(ctx):
    """Coerce the board context to the types the boards expect.

    Three production outages this session came from a value being a different
    SHAPE than the fixture assumed — api_meters dicts, GA4 floats, serp_ads
    lists. Normalising once at the boundary makes a wrong shape impossible to
    crash a board, whatever the store hands us."""
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in _DICT_KEYS:
        v = out.get(k)
        out[k] = v if isinstance(v, dict) else {}
    for k in _LIST_KEYS:
        v = out.get(k)
        out[k] = list(v) if isinstance(v, (list, tuple)) else []
    return out


def _off(reason=""):
    return reason or _CONNECT


def _na(title, sub, insight, src="Google Ads API", links=""):
    """A card that CANNOT have a number yet — stated plainly, never a fake 0."""
    return (title, "—", sub, "", insight, src, AMBER, links)


# ======================================================================
#  ① MEDIA COMMAND  (14)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    ads = ctx.get("ads") or {}
    econ = ctx.get("econ") or {}
    tgt = ctx.get("targets") or {}
    inter = ctx.get("interlock") or {}
    on = bool(ads.get("connected"))
    spend = ads.get("spend", 0)
    conv = ads.get("conversions", 0)
    cac = (inter.get("cac") or {})
    ready = tgt.get("ready")
    return _head("🎯", "Media Command",
                 "The whole account in one screen: what it costs, what it returns, "
                 "and the next decision worth making.") + _vizcards([
        ("Account status", "live" if on else "not connected", "Google Ads API",
         _statusgrid([("Google Ads API", on, "live" if on else "needs OAuth"),
                      ("Unit economics", bool(ready), "set" if ready else "3 numbers needed"),
                      ("Cross-channel interlock", bool(inter), "built" if inter else "not run"),
                      ("Landing pages", bool(ctx.get("crawl")), "crawled" if ctx.get("crawl") else "run a crawl")]),
         (_off() if not on else f"{ads.get('enabled', 0)} campaigns enabled."),
         "connector status", GREEN if on else AMBER, ""),
        ("Spend (30d)", f"€{spend:,.0f}" if on else "—", "across all campaigns",
         _spark([]) if not on else "",
         (_off() if not on else "Everything below is judged against this."),
         "Google Ads API", BLUE if on else AMBER, ""),
        ("Conversions (30d)", conv if on else "—", "recorded by Google", "",
         (_off() if not on else
          "Google only sees what the tag reports — the offline import makes this "
          "mean 'won deals' instead of 'form fills'."),
         "Google Ads API", BLUE if on else AMBER, ""),
        ("Cost per conversion", f"€{spend/conv:,.0f}" if (on and conv) else "—",
         f"target €{tgt.get('target_cpa_lead') or tgt.get('target_cpa_consult') or '—'}",
         _score_gauge(min(100, 100 * (tgt.get("target_cpa_lead") or 1) / max(spend / conv, 1)), 100)
         if (on and conv and ready) else "",
         ("Needs unit economics before this number can be judged." if not ready else
          _off() if not on else "Measured against the CPA your margins actually allow."),
         "computed", VIOLET, ""),
        ("Target CPA",
         (f"€{(tgt.get('target_cpa_lead') or tgt.get('target_cpa_consult')):,.0f}"
          if (ready and (tgt.get('target_cpa_lead') or tgt.get('target_cpa_consult')))
          else "—"), "what a lead may cost",
         _score_gauge(70, 70) if ready else "",
         (tgt.get("reason") or "Enter your unit economics." if not ready else
          f"Average deal €{float(econ.get('avg_deal_value') or 0):,.0f} × "
          f"{econ.get('gross_margin_pct') or 0}% margin × "
          f"{econ.get('consult_to_client_pct') or 0}% close = "
          f"€{float(tgt.get('gross_per_client') or 0):,.0f} gross per client. "
          "Keeping 70% of it caps a lead at this."),
         "unit economics", GREEN if ready else AMBER,
         "" if ready else "<div class='cta'><button class='cbtn sm' onclick='openEcon()'>"
                          "Enter the 3 numbers</button></div>"),
        ("Target ROAS", f"{tgt.get('target_roas')}x" if ready else "—", "revenue per €1 spent",
         _score_gauge(min(100, (tgt.get("target_roas") or 0) * 20), 60) if ready else "",
         ("Derived from your gross margin — not a number picked out of the air."
          if ready else "Needs unit economics."),
         "unit economics", GREEN if ready else AMBER, ""),
        ("Break-even CPA",
         (f"€{float(tgt.get('break_even_cpa_consult') or 0):,.0f}"
          if (ready and tgt.get('break_even_cpa_consult')) else "—"),
         "per booked consultation", "",
         ("Above this you are paying to lose money." if ready else "Needs unit economics."),
         "unit economics", PINK if ready else AMBER, ""),
        ("Blended CAC", f"€{cac.get('cac'):,.0f}" if cac.get("cac") else "—",
         "all channels combined", "",
         (f"{cac.get('verdict', '')}. Ads €{cac.get('ads_spend', 0):,.0f} + engine "
          f"€{cac.get('engine_spend', 0):,.0f} ÷ {cac.get('customers', 0)} customers."
          if cac.get("cac") else
          "The only number that answers 'is this working'. Needs customers won."),
         "cross-channel", GREEN if cac.get("verdict") == "profitable" else AMBER, ""),
        ("Payback ratio", f"{cac.get('payback_ratio')}x" if cac.get("payback_ratio") else "—",
         "gross margin ÷ CAC",
         _score_gauge(min(100, (cac.get("payback_ratio") or 0) * 20), 60)
         if cac.get("payback_ratio") else "",
         ("Above 3× is a healthy acquisition business." if cac.get("payback_ratio")
          else "Fills once customers are recorded."),
         "cross-channel", VIOLET, ""),
        ("Wasted spend", f"€{(ctx.get('terms') or {}).get('wasted_spend', 0):,.0f}" if on else "—",
         "clicks that never converted", "",
         (_off() if not on else
          f"{(ctx.get('terms') or {}).get('wasted_pct', 0)}% of spend went to search terms "
          "with clicks and zero conversions. One click adds them as negatives."),
         "search terms report", PINK if on else AMBER, ""),
        ("Impression share", f"{(ctx.get('is_summary') or {}).get('share', 0)}%" if on else "—",
         "of auctions you appear in", "",
         (_off() if not on else
          "Lost to budget means add money. Lost to rank means fix quality. "
          "Different problems, opposite fixes."),
         "Google Ads API", BLUE if on else AMBER, ""),
        ("Policy problems", len((ctx.get("ad_status") or {}).get("disapproved") or []) if on else "—",
         "disapproved ads", "",
         (_off() if not on else
          "A disapproved ad stops serving silently. Nothing was watching for this."),
         "Google Ads API", PINK if on else AMBER, ""),
        ("Cross-channel links", f"{inter.get('links_live', 0)}/{inter.get('links_total', 8)}",
         "SEO ↔ AEO ↔ GEO ↔ Ads", _gauge(inter.get("links_live", 0), 8),
         ("Every section used to be blind to the others. These are the wires "
          "between them — most work without Google Ads."),
         "interlock engine", GREEN if inter.get("links_live") else AMBER, ""),
        ("Open decisions", len(ctx.get("orders") or []), "waiting on you", "",
         "Ranked by impact ÷ effort, like the SEO queue.",
         "work orders", AMBER, ""),
    ])


# ======================================================================
#  ② ACCOUNT HEALTH & POLICY  (20)
# ======================================================================
def board_health(ctx) -> str:
    ctx = _ctx(ctx)
    ads = ctx.get("ads") or {}
    st = ctx.get("ad_status") or {}
    conv = ctx.get("conv_actions") or {}
    chg = ctx.get("changes") or {}
    rec = ctx.get("recs") or {}
    on = bool(ads.get("connected"))
    camps = ads.get("campaigns") or []
    r = _off(ads.get("reason"))
    return _head("🩺", "Account health & policy",
                 "Is the account structurally sound, and is anything silently "
                 "switched off?") + _vizcards([
        ("Campaigns", len(camps) if on else "—", f"{ads.get('enabled', 0)} enabled" if on else "",
         _treemap([(c["name"][:18], c["cost"]) for c in camps[:8]]) if camps else "",
         (r if not on else "Every campaign, with its type, status and spend."),
         "Google Ads API", BLUE if on else AMBER, ""),
        _na("Enabled vs paused", "campaign status split",
            r if not on else "Paused campaigns still hold budget allocation decisions."),
        ("Disapproved ads", len(st.get("disapproved") or []) if on else "—",
         "not serving at all", "",
         (r if not on else
          "A disapproved ad is invisible spend capacity. This is the fastest "
          "thing to fix in any account."),
         "policy summary", PINK if (st.get("disapproved")) else (GREEN if on else AMBER), ""),
        ("Limited ads", len(st.get("limited") or []) if on else "—",
         "serving with restrictions", "",
         (r if not on else "Approved-limited ads reach far fewer people than you think."),
         "policy summary", AMBER, ""),
        _na("Ad groups per campaign", "structure density",
            r if not on else "Too many keywords per ad group dilutes relevance."),
        _na("Keywords per ad group", "structure density",
            r if not on else "Tight themes score higher on ad relevance."),
        _na("Match type mix", "exact / phrase / broad",
            r if not on else "Broad match without smart bidding is how budgets vanish."),
        _na("Duplicate keywords", "competing against yourself",
            r if not on else "The same keyword in two ad groups splits its own data."),
        _na("Ad groups with one ad", "no test running",
            r if not on else "An ad group with a single RSA has nothing to learn from."),
        _na("Campaigns without conversion tracking", "flying blind",
            r if not on else "Spending without a conversion action is spending blind."),
        ("Conversion actions", conv.get("enabled", "—") if on else "—", "enabled", "",
         (r if not on else
          f"{conv.get('primary', 0)} marked primary. Only primary actions drive "
          "smart bidding — the rest are just reporting."),
         "conversion_action", BLUE if on else AMBER, ""),
        ("Offline import", conv.get("offline", "—") if on else "—", "upload actions", "",
         (r if not on else
          "Without an upload action Google optimises toward form fills, not "
          "clients. This is the single biggest lever on lead quality."),
         "conversion_action", AMBER, ""),
        ("Optimisation score", "—", "Google's own rating", "",
         (r if not on else f"{rec.get('count', 0)} recommendations available."),
         "recommendation", BLUE if on else AMBER, ""),
        ("Google recommendations", rec.get("count", "—") if on else "—", "suggestions", "",
         (r if not on else
          "Worth reading, not worth auto-applying — Google optimises for spend."),
         "recommendation", BLUE if on else AMBER, ""),
        ("Changes (30d)", len(chg.get("changes") or []) if on else "—", "recorded edits", "",
         (r if not on else
          "Every performance change should be traceable to an edit. This is that record."),
         "change_event", BLUE if on else AMBER, ""),
        _na("Auto-applied changes", "made by Google, not you",
            r if not on else "Google can auto-apply its own recommendations. Check this is off."),
        _na("Shared budgets", "budget pooling",
            r if not on else "Shared budgets hide which campaign is actually capped."),
        _na("Negative keyword lists", "account-level hygiene",
            r if not on else "Shared negative lists stop the same waste in every campaign."),
        _na("Account age & spend history", "learning data available",
            r if not on else "Smart bidding needs history; a new account behaves differently."),
        _na("Currency & timezone", "reporting integrity",
            r if not on else "A mismatched timezone shifts every day-part decision."),
    ])


# ======================================================================
#  ③ CAMPAIGN TYPES & MIX  (20)
# ======================================================================
_TYPES = [("SEARCH", "Search", "intent that already exists"),
          ("PERFORMANCE_MAX", "Performance Max", "Google's black box — needs its own loop"),
          ("DISPLAY", "Display", "cheap reach, weak intent"),
          ("VIDEO", "Video / YouTube", "demand creation"),
          ("DEMAND_GEN", "Demand Gen", "social-style placement"),
          ("SHOPPING", "Shopping", "product feed — not relevant to a service business")]


def board_types(ctx) -> str:
    ctx = _ctx(ctx)
    ads = ctx.get("ads") or {}
    on = bool(ads.get("connected"))
    by_type = ads.get("by_type") or {}
    camps = ads.get("campaigns") or []
    r = _off(ads.get("reason"))
    cards = [
        ("Campaign type mix", len(by_type) if on else "—", "types running",
         _treemap([(lbl, by_type.get(code, 0)) for code, lbl, _d in _TYPES]) if by_type else "",
         (r if not on else
          "Each type needs a different optimisation loop. Running them all with "
          "one playbook is the most common way accounts leak money."),
         "Google Ads API", BLUE if on else AMBER, ""),
    ]
    for code, label, desc in _TYPES:
        spend = by_type.get(code, 0)
        n = sum(1 for c in camps if c.get("type") == code)
        cards.append((f"{label} spend", f"€{spend:,.0f}" if on else "—",
                      f"{n} campaign(s)" if on else desc, "",
                      (r if not on else f"{desc}. €{spend:,.0f} of the account."),
                      "Google Ads API", BLUE if on else AMBER, ""))
    cards += [
        _na("PMax asset groups", "creative sets inside PMax",
            r if not on else "PMax lives or dies on asset group quality."),
        _na("PMax search themes", "the only keyword-like control PMax has",
            r if not on else "Search themes are how you steer PMax toward intent."),
        _na("PMax brand exclusions", "stop paying for your own name",
            r if not on else "Without brand exclusions PMax eats your cheapest brand traffic."),
        _na("PMax placement exclusions", "where the money actually went",
            r if not on else "PMax will spend on apps and junk placements unless excluded."),
        _na("Display placement quality", "sites your ads appeared on",
            r if not on else "Display placement reports routinely reveal app-junk spend."),
        _na("Video view rate", "engagement on YouTube",
            r if not on else "View rate is the first signal a video creative is wrong."),
        _na("Network split", "Search vs Partners vs Display",
            r if not on else "Search Partners and Display Expansion quietly change performance."),
        _na("Type efficiency", "CPA by campaign type",
            r if not on else "Compare the same outcome across types before shifting budget."),
        _na("Type conversion share", "which type brings the leads",
            r if not on else "Spend share and conversion share are rarely the same."),
        _na("Recommended mix", "for a B2B service business",
            "Search first for existing intent; PMax only once conversion tracking is "
            "trustworthy; Display and Video for remarketing, not cold reach."),
        _na("Incrementality risk", "is PMax taking credit for brand demand?",
            "PMax often reports conversions that brand search would have won anyway."),
        _na("New type opportunity", "what is not running yet",
            "Demand Gen and remarketing are usually the cheapest untouched inventory."),
        _na("Type launch order", "what to run first",
            "Search on high-intent keywords, then remarketing, then PMax once "
            "conversion tracking is trustworthy. PMax first is how new accounts "
            "burn a budget learning nothing."),
    ]
    return _head("🗂", "Campaign types & mix",
                 "Search, Performance Max, Display, Video and Demand Gen are five "
                 "different jobs. This is where the money sits across them.") + _vizcards(cards)


# ======================================================================
#  ④ SEARCH TERMS & WASTE  (18)
# ======================================================================
def board_terms(ctx) -> str:
    ctx = _ctx(ctx)
    t = ctx.get("terms") or {}
    on = bool(t.get("connected"))
    r = _off(t.get("reason"))
    terms = t.get("terms") or []
    waste_terms = t.get("waste_terms") or []
    conv_terms = t.get("converting_terms") or []
    return _head("🔍", "Search terms & wasted spend",
                 "What people actually typed. The highest-frequency, highest-return "
                 "task in any Google Ads account — and it was not built.") + _vizcards([
        ("Search terms seen", len(terms) if on else "—", "in the last 30 days", "",
         (r if not on else "Every real query that triggered an ad."),
         "search_term_view", BLUE if on else AMBER, ""),
        ("Wasted spend", f"€{t.get('wasted_spend', 0):,.0f}" if on else "—",
         f"{t.get('wasted_pct', 0)}% of total" if on else "clicks, no conversions",
         _donut(t.get("wasted_pct", 0)) if on else "",
         (r if not on else
          "Terms with 3+ clicks and zero conversions. This is the money you get "
          "back first, and it costs nothing but a click."),
         "computed", PINK if t.get("wasted_spend") else (GREEN if on else AMBER), ""),
        ("Negative candidates", len(t.get("negative_candidates") or []) if on else "—",
         "ready to block", "",
         (r if not on else "Reviewed and added in one action, not one at a time."),
         "computed", AMBER,
         _rows(waste_terms, left_fmt=lambda x: x.get("term", "")[:40],
               right_fmt=lambda x: f"€{x.get('cost', 0):.0f} · {x.get('clicks', 0)} clicks",
               empty="Nothing wasteful found." if on else "Connect Google Ads.")),
        ("Converting terms", len(conv_terms) if on else "—", "brought a lead", "",
         (r if not on else
          "These are the terms to protect, raise bids on, and write content about."),
         "search_term_view", GREEN if conv_terms else AMBER,
         _rows(conv_terms, left_fmt=lambda x: x.get("term", "")[:40],
               right_fmt=lambda x: f"{x.get('conversions', 0)} conv · €{x.get('cost', 0):.0f}",
               empty="No converting terms yet." if on else "Connect Google Ads.")),
        _na("Terms not yet keywords", "proven demand, unclaimed",
            r if not on else "A converting search term with no matching keyword is free money."),
        _na("Broad match spill", "how far broad match wandered",
            r if not on else "Broad match without tight negatives is the classic budget leak."),
        _na("Irrelevant term themes", "clustered waste",
            r if not on else "'free', 'jobs', 'salary', 'course' — the usual suspects."),
        _na("Brand vs non-brand terms", "who already knew you",
            r if not on else "Brand terms flatter every metric. Split them or be misled."),
        _na("Competitor terms", "people searching a rival",
            r if not on else "Expensive, low intent to switch — but sometimes worth it."),
        _na("Question terms", "informational intent",
            r if not on else "Question searches rarely convert in paid — they are SEO's job."),
        _na("Long-tail share", "specific vs generic",
            r if not on else "Long-tail terms convert better and cost less, almost always."),
        _na("Term → landing page match", "did they get what they asked for?",
            r if not on else "Message match is the cheapest conversion-rate lever there is."),
        _na("New terms this week", "what changed",
            r if not on else "New terms appearing is how you catch drift early."),
        _na("Cost per term", "spend concentration",
            r if not on else "A handful of terms usually carry most of the spend."),
        _na("Zero-impression keywords", "keywords never triggered",
            r if not on else "Dead keywords clutter the account and hide real ones."),
        _na("Negative conflicts", "negatives blocking real keywords",
            r if not on else "A negative can silently switch off a keyword you are paying for."),
        _na("Negative list coverage", "account-wide protection",
            r if not on else "Shared negative lists apply the same lesson everywhere."),
        _na("Waste trend", "is it getting better?",
            r if not on else "Waste percentage over time is the scoreboard for this loop."),
    ])


# ======================================================================
#  ⑤ KEYWORDS & QUALITY SCORE  (20)
# ======================================================================
def board_keywords(ctx) -> str:
    ctx = _ctx(ctx)
    k = ctx.get("kw") or {}
    on = bool(k.get("connected"))
    r = _off(k.get("reason"))
    kws = k.get("keywords") or []
    low = k.get("low_qs") or []
    dist = k.get("qs_distribution") or {}
    return _head("🔑", "Keywords & Quality Score",
                 "Quality Score sets what you pay per click. It is available "
                 "from the API and was never read.") + _vizcards([
        ("Average Quality Score", k.get("avg_qs", "—") if on else "—", "out of 10",
         _score_gauge((k.get("avg_qs", 0) or 0) * 10, 70) if on else "",
         (r if not on else
          "Each point of Quality Score changes your cost per click materially. "
          "It is the cheapest CPC reduction available."),
         "keyword_view", _pct_color((k.get("avg_qs", 0) or 0) * 10) if on else AMBER, ""),
        ("QS distribution", sum(dist.values()) if dist else "—", "keywords scored",
         _hbars([(f"QS {i}", dist.get(str(i), 0)) for i in range(1, 11)], VIOLET) if dist else "",
         (r if not on else "Where the account sits. Everything at 4 or below is expensive."),
         "keyword_view", VIOLET if on else AMBER, ""),
        ("Low Quality Score", len(low) if on else "—", "at 4 or below", "",
         (r if not on else
          "These cost the most per click and are the fastest CPC win in the account."),
         "keyword_view", PINK if low else (GREEN if on else AMBER),
         _rows(low, left_fmt=lambda x: x.get("text", "")[:34],
               right_fmt=lambda x: f"QS {x.get('qs')} · €{x.get('cost', 0):.0f}",
               empty="No low-quality keywords." if on else "Connect Google Ads.")),
        _na("Ad relevance", "one of the three QS components",
            r if not on else "Below average means the ad does not match the keyword."),
        _na("Expected CTR", "one of the three QS components",
            r if not on else "Below average means the copy is not compelling at this position."),
        _na("Landing page experience", "one of the three QS components",
            r if not on else
            "This is measurable from your own crawl — the interlock board wires it."),
        ("Keywords", len(kws) if on else "—", "active", "",
         (r if not on else "Every keyword with its cost, clicks and conversions."),
         "keyword_view", BLUE if on else AMBER, ""),
        _na("Match type performance", "exact vs phrase vs broad",
            r if not on else "Compare CPA by match type before widening anything."),
        _na("Top spending keywords", "where the money goes",
            r if not on else "Spend concentration tells you where scrutiny belongs."),
        _na("Zero-conversion keywords", "cost without return",
            r if not on else "Pause or fix — but only past statistical significance."),
        _na("Keyword CPA vs target", "judged against your economics",
            r if not on else "A keyword is only expensive relative to what a client is worth."),
        _na("Bid vs first-page estimate", "are you even in the auction?",
            r if not on else "Bidding below the first-page estimate buys nothing."),
        _na("Keyword conversion rate", "clicks that become leads",
            r if not on else "The number that converts a CPC into a CPA."),
        _na("Search volume trend", "is demand growing?",
            r if not on else "Falling volume explains falling conversions without a fault."),
        _na("Keyword cannibalisation", "same keyword, two ad groups",
            r if not on else "Duplicates split their own performance data."),
        _na("Paused keyword history", "what was switched off and why",
            r if not on else "Paused winners are common after a hasty cleanup."),
        _na("Keyword → ad relevance", "does the ad mention the keyword?",
            r if not on else "The single most reliable ad-relevance fix."),
        _na("Statistical significance", "is there enough data to act?",
            "Nothing should be paused on 3 clicks. This gate stops the agent acting on noise."),
        _na("Seasonality", "predictable demand swings",
            r if not on else "Seasonality adjustments prevent panic edits."),
        _na("New keyword candidates", "from search terms and SEO",
            r if not on else "The interlock board feeds this from your organic data."),
    ])


# ======================================================================
#  ⑥ BIDDING & STRATEGY  (24)
# ======================================================================
_STRATS = [("MANUAL_CPC", "Manual CPC", "full control, no per-auction signals"),
           ("MAXIMIZE_CLICKS", "Maximise Clicks", "traffic, not outcomes"),
           ("MAXIMIZE_CONVERSIONS", "Maximise Conversions", "spends the whole budget"),
           ("TARGET_CPA", "Target CPA", "needs ~15-30 conversions/month"),
           ("TARGET_ROAS", "Target ROAS", "needs conversion VALUES, not just counts"),
           ("MAXIMIZE_CONVERSION_VALUE", "Max Conversion Value", "value-based"),
           ("TARGET_IMPRESSION_SHARE", "Target Impression Share", "visibility, not efficiency")]


def board_bidding(ctx) -> str:
    ctx = _ctx(ctx)
    ads = ctx.get("ads") or {}
    tgt = ctx.get("targets") or {}
    on = bool(ads.get("connected"))
    r = _off(ads.get("reason"))
    camps = ads.get("campaigns") or []
    advice = ctx.get("bid_advice") or []
    strat_mix = {}
    for c in camps:
        strat_mix[c.get("bid_strategy") or "?"] = strat_mix.get(c.get("bid_strategy") or "?", 0) + 1
    cards = [
        ("Bid strategy mix", len(strat_mix) if on else "—", "strategies in use",
         _hbars(sorted(strat_mix.items(), key=lambda kv: -kv[1]), VIOLET) if strat_mix else "",
         (r if not on else
          "Bid strategy is the single biggest lever in the account, and the "
          "wrong one wastes months in a learning phase."),
         "Google Ads API", VIOLET if on else AMBER, ""),
        ("Strategy fit", len([a for a in advice if not a.get("ok")]) if on else "—",
         "campaigns on the wrong strategy", "",
         (r if not on else
          "Smart bidding below ~15 conversions a month cannot learn. Manual "
          "bidding above ~30 leaves money on the table."),
         "computed", PINK if any(not a.get("ok") for a in advice) else (GREEN if on else AMBER),
         _rows(advice, left_fmt=lambda a: a.get("campaign", "")[:28],
               right_fmt=lambda a: a.get("advice", "")[:52],
               empty="Every campaign suits its data volume." if on else "Connect Google Ads.")),
        ("Target CPA in use",
         (f"€{tgt.get('target_cpa_lead')}" if tgt.get("ready") and tgt.get("target_cpa_lead")
          else "—"),
         "your economics say this", _score_gauge(70, 70) if tgt.get("ready") else "",
         ((tgt.get("reason") or "Enter your unit economics.") if not tgt.get("ready") else
          "Set campaign targets to this, and never move a target more than 20% "
          "at once — larger jumps restart the learning phase."),
         "unit economics", GREEN if tgt.get("ready") else AMBER, ""),
    ]
    for code, label, note in _STRATS:
        n = strat_mix.get(code, 0)
        cards.append((f"{label}", n if on else "—", "campaigns" if on else note, "",
                      (r if not on else f"{note}. {n} campaign(s) using it."),
                      "Google Ads API", BLUE if on else AMBER, ""))
    cards += [
        _na("Learning phase", "campaigns still learning",
            r if not on else "Never judge or edit a campaign mid-learning."),
        _na("Days since last target change", "stability",
            r if not on else "Targets need 2-3 weeks to settle before another move."),
        _na("Device bid adjustments", "mobile / desktop / tablet",
            r if not on else "Mobile converts differently for B2B. Almost always."),
        _na("Location bid adjustments", "per market",
            r if not on else "Your five markets do not deserve the same bid."),
        _na("Ad schedule adjustments", "hour and day",
            r if not on else "B2B buys during business hours in its own timezone."),
        _na("Audience bid adjustments", "remarketing uplift",
            r if not on else "Returning visitors are worth more. Bid like it."),
        _na("Demographic adjustments", "age and household income",
            r if not on else "Rarely used, occasionally decisive."),
        _na("Seasonality adjustments", "planned demand shifts",
            r if not on else "Tell Google about a promotion instead of letting it guess."),
        _na("Data exclusions", "ignore broken tracking periods",
            r if not on else "A tracking outage poisons smart bidding unless excluded."),
        _na("Portfolio strategies", "shared bidding across campaigns",
            r if not on else "Portfolios pool learning data — useful at low volume."),
        _na("Bid vs impression share", "am I bidding to be seen?",
            r if not on else "Target Impression Share buys visibility, not efficiency."),
        _na("CPC trend", "is the auction getting more expensive?",
            r if not on else "Rising CPC with flat CPA is fine; with rising CPA is not."),
        _na("Conversion value tracking", "needed for ROAS bidding",
            r if not on else "Target ROAS is impossible without values on conversions."),
        _na("Value rules", "adjust value by location, device, audience",
            r if not on else "A German lead may be worth more than a US one. Say so."),
    ]
    return _head("⚖️", "Bidding & strategy",
                 "Bidding is the job. Strategy selection, five kinds of adjustment, "
                 "learning phases, and the discipline not to touch it too often.") + _vizcards(cards)


# ======================================================================
#  ⑦ BUDGET & PACING  (18)
# ======================================================================
def board_budget(ctx) -> str:
    ctx = _ctx(ctx)
    ads = ctx.get("ads") or {}
    p = ctx.get("pacing") or {}
    on = bool(ads.get("connected"))
    r = _off(ads.get("reason"))
    camps = ads.get("campaigns") or []
    is_rows = ctx.get("is_rows") or []
    return _head("💰", "Budget & pacing",
                 "Is the money going out at the right speed, and into the right "
                 "campaigns?") + _vizcards([
        ("Month pacing", f"{p.get('pace_pct', 0)}%" if p.get("ready") else "—",
         p.get("status", "of budget") if p.get("ready") else "projected vs budget",
         _score_gauge(min(100, p.get("pace_pct", 0)), 100) if p.get("ready") else "",
         (r if not on else
          f"€{p.get('spend', 0):,.0f} spent, projecting €{p.get('projected', 0):,.0f} "
          f"against €{p.get('month_budget', 0):,.0f}."),
         "computed", (PINK if p.get("status") == "over" else
                      AMBER if p.get("status") == "under" else GREEN) if on else AMBER, ""),
        ("Daily budget", f"€{sum(c.get('budget', 0) for c in camps):,.0f}" if on else "—",
         "across campaigns",
         _hbars([(c["name"][:16], c["budget"]) for c in camps[:8]], BLUE) if camps else "",
         (r if not on else "The cap that decides whether impression share is winnable."),
         "Google Ads API", BLUE if on else AMBER, ""),
        ("Budget-limited campaigns", len([c for c in camps if c.get("is_lost_budget", 0) > 10])
         if on else "—", "losing auctions to budget", "",
         (r if not on else
          "These would win more auctions if funded. This is the ONE case where "
          "adding money is the right answer."),
         "impression share", AMBER, ""),
        ("Rank-limited campaigns", len([c for c in camps if c.get("is_lost_rank", 0) > 10])
         if on else "—", "losing auctions to quality", "",
         (r if not on else
          "Do NOT add budget here. More money on a rank problem just buys more "
          "expensive losses."),
         "impression share", PINK if on else AMBER, ""),
        ("Impression share", f"{(ctx.get('is_summary') or {}).get('share', 0)}%" if on else "—",
         "auctions entered",
         _split_donut([("Won", (ctx.get("is_summary") or {}).get("share", 0), GREEN),
                       ("Lost to budget", (ctx.get("is_summary") or {}).get("budget", 0), AMBER),
                       ("Lost to rank", (ctx.get("is_summary") or {}).get("rank", 0), PINK)])
         if on else "",
         (r if not on else
          "The whole diagnostic in one chart: money problem, quality problem, or neither."),
         "Google Ads API", BLUE if on else AMBER,
         _rows(is_rows, left_fmt=lambda x: x.get("campaign", "")[:28],
               right_fmt=lambda x: x.get("verdict", ""), empty="")),
        _na("Spend by campaign", "where the money went",
            r if not on else "Concentration is fine if the CPA justifies it."),
        _na("Spend vs conversion share", "efficiency by campaign",
            r if not on else "A campaign taking 60% of spend for 20% of leads is the first cut."),
        _na("Budget reallocation", "move money to what works",
            r if not on else "The ads optimiser proposes moves; you approve them."),
        _na("Overspend risk", "days above budget",
            r if not on else "Google can spend up to 2× daily budget on any single day."),
        _na("Underspend", "budget left unused",
            r if not on else "Unused budget on a profitable campaign is lost growth."),
        _na("Monthly cap vs engine cap", "your €200 total",
            "Ad spend is separate from the engine's API budget — but both come "
            "out of the same business."),
        _na("Cost per day", "spend rhythm",
            r if not on else "Sharp daily swings usually mean a bidding or budget change."),
        _na("Weekend vs weekday spend", "when the money goes",
            r if not on else "B2B weekend spend is often pure waste."),
        _na("Forecast to month end", "where this lands",
            r if not on else "Projected from run-rate, not guessed."),
        _na("Budget by market", "your five countries",
            r if not on else "Germany has no organic content — its budget should reflect that."),
        _na("Budget by campaign type", "Search vs PMax vs Display",
            r if not on else "PMax will take whatever it is given. Cap it deliberately."),
        _na("Shared budget usage", "pooled spend",
            r if not on else "Shared budgets obscure which campaign is actually capped."),
        _na("Recommended budget", "to capture lost impression share",
            r if not on else "Only meaningful for campaigns losing share to BUDGET."),
    ])


# ======================================================================
#  ⑧ LOCATION & LANGUAGE TARGETING  (20)
# ======================================================================
def board_targeting(ctx) -> str:
    ctx = _ctx(ctx)
    tg = ctx.get("targeting") or {}
    geo = ctx.get("geo") or {}
    on = bool(tg.get("connected"))
    r = _off(tg.get("reason"))
    risky = tg.get("presence_risk") or []
    markets = ctx.get("markets") or []
    cards = [
        ("Presence vs interest", len(risky) if on else "—",
         "campaigns targeting 'interest'", "",
         (r if not on else
          "'Presence OR interest' shows your ads to people merely SEARCHING about "
          "a location. It is one of the largest silent waste sources in Google Ads, "
          "and it is on by default."),
         "geo_target_type_setting", PINK if risky else (GREEN if on else AMBER), ""),
        ("Markets targeted", len(markets) or 5, "USA · UK · DE · CH · CA",
         _hbars([(m.get("market", "")[:12], m.get("organic_impressions", 0))
                 for m in markets], BLUE) if markets else "",
         ("Organic reach per market — where paid has to carry the load."),
         "GEO audit", BLUE, ""),
        ("Paid-only markets", len([m for m in markets if m.get("paid_is_only_lever")]),
         "no content in their language", "",
         ((", ".join(m["market"] for m in markets if m.get("paid_is_only_lever"))
           + " have no pages in their language. Paid is not an option there — it is "
             "the only lever until content ships.")
          if any(m.get("paid_is_only_lever") for m in markets)
          else "Every market has content in its language."),
         "GEO audit", PINK if any(m.get("paid_is_only_lever") for m in markets) else GREEN, ""),
    ]
    from content_engine_geo import MARKETS as _MK
    _by = {m.get("market"): m for m in (markets or [])}
    for _canon in _MK:                      # always five cards, data or not —
        m = _by.get(_canon["name"], {"market": _canon["name"],   # the count must
                                     "organic_pages": 0,          # not depend on
                                     "organic_impressions": 0,    # the data
                                     "has_landing_page": False})
        cards.append((f"{m.get('market', '')}", m.get("organic_pages", 0), "organic pages",
                      _donut(100 if m.get("has_landing_page") else 0),
                      (f"{m.get('organic_impressions', 0)} organic impressions. "
                       + ("No landing page for this market yet."
                          if not m.get("has_landing_page") else "Has a landing page.")),
                      "GEO audit", GREEN if m.get("has_landing_page") else AMBER, ""))
    cards += [
        _na("Location bid adjustments", "per country",
            r if not on else "Five markets, five economics, five bids."),
        _na("Excluded locations", "where you refuse to show",
            r if not on else "Excluding is as important as including."),
        _na("Radius targeting", "distance-based",
            r if not on else "Rarely right for a remote service business."),
        _na("Location performance", "CPA by country",
            r if not on else "The number that justifies each market's budget."),
        _na("Language targeting", "which language settings",
            r if not on else
            "Language targeting matches the browser, not the ad. Both must line up."),
        _na("German-language readiness", "for DE and CH",
            "You write German and have zero German pages. Paid ads in German "
            "pointing at English pages will convert badly — the landing page has "
            "to come first."),
        _na("Currency by market", "pricing presentation",
            r if not on else "CHF, EUR, GBP, USD, CAD — each changes perceived price."),
        _na("Timezone by market", "ad scheduling",
            r if not on else "One ad schedule cannot serve five timezones."),
        _na("Market CPC benchmark", "what a click costs there",
            r if not on else "US clicks cost multiples of German ones in this category."),
        _na("Market competition", "who else bids there",
            "The competitor scan covers this from the SERP side."),
        _na("Market opportunity score", "where to expand next",
            "DE and CH: real demand, your language, zero content, low competition."),
        _na("Location report vs targeting", "where ads ACTUALLY showed",
            r if not on else
            "The location report often reveals countries you never intended to target."),
    ]
    return _head("🌍", "Location & language targeting",
                 "Not where your ads performed — how they are CONFIGURED. This is "
                 "where five markets quietly become one wasted budget.") + _vizcards(cards)


# ======================================================================
#  ⑨ AUDIENCES  (18)
# ======================================================================
def board_audiences(ctx) -> str:
    ctx = _ctx(ctx)
    a = ctx.get("audiences") or {}
    on = bool(a.get("connected"))
    r = _off(a.get("reason"))
    auds = a.get("audiences") or []
    return _head("👥", "Audiences",
                 "Who sees the ads, and who is worth paying more for.") + _vizcards([
        ("Audiences in use", len(auds) if on else "—", "attached to campaigns", "",
         (r if not on else "Observation or targeting — the distinction matters enormously."),
         "ad_group_audience_view", BLUE if on else AMBER, ""),
        _na("Remarketing lists", "people who already visited",
            r if not on else
            "Your site has 266 pages and real visitors. Not remarketing to them is "
            "the cheapest missed opportunity in the account."),
        _na("List sizes", "are they big enough to serve?",
            r if not on else "Search remarketing needs 1,000 users; Display needs 100."),
        _na("Customer match", "upload your client list",
            r if not on else "Your own customers are the best seed audience you have."),
        _na("Similar audiences", "lookalikes of your converters",
            r if not on else "Built from customer match — free, and usually effective."),
        _na("In-market segments", "actively shopping",
            r if not on else "Google knows who is researching automation right now."),
        _na("Affinity segments", "broad interest",
            r if not on else "Too broad for B2B search; useful for Video."),
        _na("Detailed demographics", "company size proxies",
            r if not on else "Limited for B2B, but occasionally sharp."),
        _na("Observation vs targeting", "the setting that changes everything",
            r if not on else
            "Observation reports without restricting. Targeting restricts. Choosing "
            "the wrong one either wastes money or kills reach."),
        _na("Audience bid adjustments", "pay more for warm traffic",
            r if not on else "A returning visitor is worth a premium bid."),
        _na("Audience CPA", "efficiency by segment",
            r if not on else "This is what justifies the adjustment above."),
        _na("Excluded audiences", "who not to pay for",
            r if not on else "Existing customers and job seekers, usually."),
        _na("Converted-user exclusion", "stop paying for won deals",
            r if not on else "Nothing wastes budget like re-advertising to a client."),
        _na("Audience overlap", "double-paying for the same person",
            r if not on else "Overlapping lists inflate cost and confuse attribution."),
        _na("Site visitors not converted", "the warmest untouched pool",
            r if not on else "They read your content and left. Follow them."),
        _na("Consent & privacy", "can you build these lists?",
            "Your cookie banner is consent-gated — remarketing lists only fill "
            "from users who accepted."),
        _na("Audience → content match", "what did they read?",
            "The crawler knows which page each visitor saw. That is a segment."),
        _na("Audience expansion", "Google widening your reach",
            r if not on else "Audience expansion silently loosens your targeting."),
    ])


# ======================================================================
#  ⑩ ADS, ASSETS & EXTENSIONS  (20)
# ======================================================================
def board_ads(ctx) -> str:
    ctx = _ctx(ctx)
    a = ctx.get("assets") or {}
    st = ctx.get("ad_status") or {}
    on = bool(a.get("connected"))
    r = _off(a.get("reason"))
    labels = a.get("labels") or {}
    low = a.get("low") or []
    best = a.get("best") or []
    return _head("✍️", "Ads, assets & extensions",
                 "The words people actually read — and the extensions that decide "
                 "how much of the page you own.") + _vizcards([
        ("Asset performance", sum(labels.values()) if labels else "—", "rated assets",
         _split_donut([("Best", labels.get("BEST", 0), GREEN),
                       ("Good", labels.get("GOOD", 0), TEAL),
                       ("Low", labels.get("LOW", 0), PINK),
                       ("Learning", labels.get("PENDING", 0), AMBER)]) if labels else "",
         (r if not on else "Google grades every headline and description. Read the grades."),
         "ad_group_ad_asset_view", VIOLET if on else AMBER, ""),
        ("Low performers", len(low) if on else "—", "assets to replace", "",
         (r if not on else "Replace these first — they are dragging the whole ad down."),
         "asset view", PINK if low else (GREEN if on else AMBER),
         _rows(low, left_fmt=lambda x: x.get("text", "")[:44],
               right_fmt=lambda x: x.get("field", ""), empty="No low-rated assets.")),
        ("Best performers", len(best) if on else "—", "keep and clone", "",
         (r if not on else "Write the next batch in the shape of these."),
         "asset view", GREEN if best else AMBER,
         _rows(best, left_fmt=lambda x: x.get("text", "")[:44],
               right_fmt=lambda x: x.get("field", ""), empty="")),
        ("Disapproved", len(st.get("disapproved") or []) if on else "—", "not serving", "",
         (r if not on else "Fix immediately — these are switched off, silently."),
         "policy summary", PINK if st.get("disapproved") else (GREEN if on else AMBER), ""),
        _na("RSA strength", "Google's ad-strength rating",
            r if not on else "Poor or Average ad strength caps your reach."),
        _na("Headlines per ad group", "should be 15",
            r if not on else "Fewer headlines means fewer combinations to learn from."),
        _na("Descriptions per ad group", "should be 4",
            r if not on else "Same principle as headlines."),
        _na("Pinned assets", "control vs learning",
            r if not on else "Over-pinning stops Google testing — sometimes right, usually not."),
        _na("Keyword in headline", "relevance signal",
            r if not on else "The most reliable ad-relevance fix there is."),
        _na("Sitelink extensions", "extra links under the ad",
            r if not on else "Sitelinks add space and CTR. Cheapest extension win."),
        _na("Callout extensions", "short benefit phrases",
            r if not on else "Free real estate on the results page."),
        _na("Structured snippets", "categorised lists",
            r if not on else "Services, brands, types — one line of extra qualification."),
        _na("Call extension", "phone number on the ad",
            r if not on else "For a consultancy, a call is often the fastest conversion."),
        _na("Lead form extension", "capture without a landing page",
            r if not on else "Higher volume, usually lower quality. Test carefully."),
        _na("Image extensions", "visual next to the text ad",
            "You already generate images for content. They can serve here too."),
        _na("Promotion extension", "offers and discounts",
            r if not on else "Only if there is a genuine offer."),
        _na("Price extension", "package pricing",
            "Your service pages carry € / €€ / €€€ tiers. That is a price extension."),
        _na("Extension coverage", "how many are actually set",
            r if not on else "Most accounts run two and could run six."),
        _na("Ad rotation", "even vs optimised",
            r if not on else "Optimise unless you are running a controlled test."),
        _na("Ad copy from content", "your best-performing headlines",
            "The interlock board pulls high-CTR organic titles as tested ad copy."),
    ])


# ======================================================================
#  ⑪ CONVERSION & FUNNEL  (20)
# ======================================================================
def board_conversion(ctx) -> str:
    ctx = _ctx(ctx)
    c = ctx.get("conv_actions") or {}
    ads = ctx.get("ads") or {}
    inter = ctx.get("interlock") or {}
    on = bool(c.get("connected"))
    r = _off(c.get("reason"))
    cac = inter.get("cac") or {}
    funnel = ctx.get("funnel") or []
    return _head("🎣", "Conversion & funnel",
                 "From impression to a client who paid. Google only sees the first "
                 "few steps unless you tell it the rest.") + _vizcards([
        ("Full funnel", len(funnel) or "—", "impression → client",
         _CH().sankey(funnel) if funnel else "",
         ("Every stage in one picture, across paid and organic."
          if funnel else "Fills as ads and outreach produce data."),
         "cross-channel", VIOLET, ""),
        ("Conversion actions", c.get("enabled", "—") if on else "—", "enabled", "",
         (r if not on else f"{c.get('primary', 0)} count toward bidding."),
         "conversion_action", BLUE if on else AMBER, ""),
        ("Offline conversions", c.get("offline", "—") if on else "—", "upload actions", "",
         (r if not on else
          "This is the fix for lead quality. Upload WON deals and Google starts "
          "optimising for clients instead of form fills."),
         "conversion_action", PINK if (on and not c.get("offline")) else AMBER, ""),
        ("Bookings", cac.get("bookings", "—"), "consultations booked", "",
         "From Cal.com — the real money moment, and what Google should optimise for.",
         "Cal.com", GREEN if cac.get("bookings") else AMBER, ""),
        ("Customers won", cac.get("customers", "—"), "closed deals", "",
         "Recorded as job outcomes. The end of the funnel.",
         "outcomes", GREEN if cac.get("customers") else AMBER, ""),
        ("Cost per booking", f"€{cac.get('cost_per_booking'):,.0f}" if cac.get("cost_per_booking")
         else "—", "all channels", "",
         ("Blended across ads, engine spend and outreach."
          if cac.get("cost_per_booking") else "Needs bookings and spend."),
         "cross-channel", VIOLET, ""),
        _na("Conversion rate", "clicks that convert",
            r if not on else "The bridge between CPC and CPA."),
        _na("Conversion lag", "days from click to conversion",
            r if not on else "B2B lags. Judging a campaign too early is the classic error."),
        _na("Attribution model", "data-driven vs last click",
            r if not on else "Last-click undervalues everything above the fold."),
        _na("Conversion value", "revenue per conversion",
            r if not on else "Without values, ROAS bidding is impossible."),
        _na("Duplicate conversions", "double counting",
            r if not on else "A tag firing twice inflates every efficiency metric."),
        _na("Zero-conversion tags", "tracking that never fires",
            r if not on else "A tag with no conversions in 30 days is usually broken."),
        _na("Tag health", "is tracking even live?",
            "Your site runs GTM and GA4 directly. The Ads tag needs the same check."),
        _na("Form fills vs bookings", "lead quality",
            "A form fill is not a customer. The gap between these two numbers IS "
            "your lead quality problem."),
        _na("Booking → client rate", "close rate",
            "Feeds the unit economics. One of the three numbers that make CPA judgeable."),
        _na("Lead source attribution", "which channel produced it",
            "Ads, organic, outreach or direct — the interlock board splits this."),
        _na("Assisted conversions", "channels that helped",
            r if not on else "Paid often assists an organic close, and gets no credit."),
        _na("Cross-device", "researched on mobile, bought on desktop",
            r if not on else "Standard in B2B, invisible without proper tracking."),
        _na("Funnel drop-off", "where people leave",
            "The sankey above shows it. The biggest drop is where to work."),
        _na("Revenue attributed", "money, not conversions",
            "The only metric the business actually runs on."),
    ])


# ======================================================================
#  ⑫ LANDING PAGE MATCH  (16)  — works TODAY
# ======================================================================
def board_landing(ctx) -> str:
    ctx = _ctx(ctx)
    q = (ctx.get("interlock") or {}).get("quality") or {}
    crawl = ctx.get("crawl") or {}
    pages = [r for r in crawl.get("urls", []) if r.get("status") == 200]
    ready = bool(q.get("ready"))
    services = [r for r in pages if "/services/" in r.get("url", "")]
    return _head("🛬", "Landing page match",
                 "Google's Quality Score has a landing-page component. Your crawler "
                 "already measures it — these cards work today, no Ads API.") + _vizcards([
        ("Landing page experience", q.get("predicted_lp_experience", "—") if ready else "—",
         "predicted", _score_gauge(q.get("on_page_score", 0), 85) if ready else "",
         (q.get("why", "") if ready else "Run a crawl and this fills immediately."),
         "own crawler", _pct_color(q.get("on_page_score", 0)) if ready else AMBER, ""),
        ("Pages available", len(pages) or "—", "crawled and live",
         _histogram([r.get("words", 0) for r in pages if r.get("words")], unit="w"),
         "Every one of these is a potential landing page.",
         "own crawler", BLUE, ""),
        ("Service pages", len(services), "the pages that sell", "",
         "These are where paid traffic should land — not the blog.",
         "own crawler", GREEN if services else AMBER,
         _linkrows(services, url_fn=lambda r: r["url"],
                   right_fn=lambda r: f"{r.get('words', 0)} words",
                   empty="No service pages found.")),
        ("Slow pages", q.get("slow_pages", "—") if ready else "—", "over 2.5s", "",
         ("Slow landing pages lower Quality Score AND conversion rate — you pay "
          "twice for the same fault." if ready else "Needs a crawl."),
         "own crawler", PINK if q.get("slow_pages") else (GREEN if ready else AMBER), ""),
        ("Thin pages", q.get("thin_pages", "—") if ready else "—", "under 300 words", "",
         ("Thin pages score badly on landing page experience." if ready else "Needs a crawl."),
         "own crawler", AMBER, ""),
        ("Worst landing pages", len(q.get("worst") or []), "fix before sending paid traffic",
         "", "Sending paid clicks to these raises your CPC and wastes the click.",
         "own crawler", PINK if q.get("worst") else GREEN,
         _linkrows(q.get("worst") or [], url_fn=lambda r: r.get("url", ""),
                   right_fn=lambda r: f"{r.get('ms', 0)}ms · {r.get('words', 0)}w",
                   empty="No problem pages.")),
        _na("Message match score", "does the page say what the ad promised?",
            "The highest-leverage conversion fix in paid search, and it costs nothing.",
            "own crawler + ad copy"),
        _na("Above-the-fold CTA", "can they act without scrolling?",
            "Your consultation modal opens from any CTA — that part is already right.",
            "own crawler"),
        _na("Form friction", "how many fields?",
            "Your consultation form is multiple-choice by design. That was the right call.",
            "site structure"),
        _na("Mobile experience", "most paid clicks are mobile",
            "PageSpeed mobile scores drive both Quality Score and conversion rate.",
            "PageSpeed"),
        _na("Trust signals", "credentials, logos, proof",
            "Your founder credentials and story pages exist — they belong on landing pages.",
            "site content"),
        _na("Page → keyword relevance", "one page per intent",
            "Sending five different intents to one page caps relevance for all five.",
            "crawler + keywords"),
        _na("Conversion rate by page", "which page actually converts",
            "Needs GA4 goal data joined to landing page.", "GA4"),
        _na("Bounce rate by page", "instant leavers",
            "A high bounce on a paid landing page is money set on fire.", "GA4"),
        _na("German landing pages", "for DE and CH",
            "Zero German pages exist. German ads must not point at English pages.",
            "GEO audit"),
        _na("Dedicated PPC pages", "built for paid, not organic",
            "Blog posts make poor landing pages: no offer, no form, no urgency.",
            "site structure"),
    ])


# ======================================================================
#  ⑬ COMPETITION  (14)  — works TODAY via Serper
# ======================================================================
def board_competition(ctx) -> str:
    ctx = _ctx(ctx)
    ci = ctx.get("competitor_intel") or {}
    # serp_ads is {query: [advertiser_domain, ...]} — a dict of LISTS. Counting
    # the raw values raised TypeError and blanked this board in production.
    serp_ads = ci.get("serp_ads") or {}
    advertisers = {}
    for _q, _doms in (serp_ads.items() if hasattr(serp_ads, "items") else []):
        for _d in (_doms if isinstance(_doms, (list, tuple)) else []):
            advertisers[_d] = advertisers.get(_d, 0) + 1
    rivals = ci.get("competitors") or []
    return _head("⚔️", "Competition",
                 "Google does not expose Auction Insights through the API. This is "
                 "the honest proxy: who actually buys ads on your queries.") + _vizcards([
        ("Advertisers on your queries", len(advertisers) or "—", "seen in sponsored slots",
         _hbars(sorted(advertisers.items(), key=lambda kv: -kv[1])[:8], PINK) if advertisers else "",
         ("Measured by scanning your real SERPs — not Auction Insights, which "
          "Google keeps out of the API."),
         "Serper", PINK if advertisers else AMBER, ""),
        ("Rivals scanned", len(rivals) or "—", "competitors profiled", "",
         ("From the SEO competitor scan — the same rivals, seen from the paid side."
          if rivals else "Run a competitor scan to fill this."),
         "competitor intel", BLUE if rivals else AMBER, ""),
        _na("Auction Insights", "impression share vs rivals",
            "Genuinely NOT available in the Google Ads API. Google only shows this "
            "in the web UI. The card above is the closest honest substitute.",
            "not available"),
        _na("Rival ad copy", "what they promise",
            "Serper captures sponsored results — their headlines are readable.", "Serper"),
        _na("Rival landing pages", "where they send traffic",
            "Worth studying before writing your own.", "Serper + crawler"),
        _na("Share of paid voice", "how often they appear vs you",
            "Counted across your tracked query set.", "Serper"),
        _na("New advertisers", "who just entered",
            "A new bidder usually means rising CPCs.", "Serper"),
        _na("CPC pressure", "is the auction heating up?",
            "Rising average CPC with stable quality means more competition.",
            "Google Ads API"),
        _na("Rival promotions", "offers they are running",
            "The competitor scan already buckets promo signals.", "competitor intel"),
        _na("Rival keyword overlap", "queries you both want",
            "Where the money fights.", "GSC + Serper"),
        _na("Organic vs paid rivals", "different lists",
            "Whoever ranks is often not whoever bids. Both matter.", "GSC + Serper"),
        _na("Defensive brand bidding", "is anyone bidding on your name?",
            "Cheap to check, expensive to ignore.", "Serper"),
        _na("Rival AI visibility", "who AI names instead of you",
            "The AEO board measures this — it is the newest competitive surface.",
            "AEO probe"),
        _na("Competitive gap", "where you can win",
            "Weak rivals on high-intent queries are the openings.", "computed"),
    ])


# ======================================================================
#  ⑭ KEYWORD RESEARCH  (16)
# ======================================================================
def board_research(ctx) -> str:
    ctx = _ctx(ctx)
    ideas = ctx.get("kw_ideas") or {}
    on = bool(ideas.get("connected"))
    r = _off(ideas.get("reason"))
    lst = ideas.get("ideas") or []
    gap = (ctx.get("interlock") or {}).get("gap_cover") or []
    return _head("🔬", "Keyword research",
                 "Google's own Keyword Planner — volume and CPC straight from the "
                 "source. No Semrush, no Ahrefs, no vendor.") + _vizcards([
        ("Keyword ideas", len(lst) if on else "—", "from Keyword Planner",
         _histogram([i.get("volume", 0) for i in lst]) if lst else "",
         (r if not on else "Real monthly volume and real top-of-page bid estimates."),
         "KeywordPlanIdeaService", BLUE if on else AMBER,
         _rows(lst, left_fmt=lambda i: i.get("keyword", "")[:34],
               right_fmt=lambda i: f"{i.get('volume', 0):,}/mo · €{i.get('low_bid', 0)}-{i.get('high_bid', 0)}",
               empty="Connect Google Ads.")),
        ("Organic gaps to cover", len(gap), "proven demand, no ranking", "",
         ("Queries you are SEEN for but rank too low to be clicked. Paid should "
          "carry these until the content catches up — demand is already proven."),
         "GSC (live today)", GREEN if gap else AMBER,
         _rows(gap, left_fmt=lambda g: g.get("query", "")[:34],
               right_fmt=lambda g: f"#{g.get('position')} · {g.get('impressions')} impr",
               empty="No weak-position queries with impressions.")),
        _na("Volume vs CPC", "cheap demand",
            r if not on else "High volume with low bids is where a small budget goes furthest."),
        _na("Competition level", "how contested",
            r if not on else "Low-competition, high-intent is the sweet spot."),
        _na("Seasonal keywords", "demand by month",
            r if not on else "Keyword Planner returns monthly breakdowns."),
        _na("Long-tail expansion", "specific, cheaper, converts better",
            r if not on else "Almost always the right starting point on a small budget."),
        _na("Question keywords", "informational",
            "These belong to SEO and AEO, not paid — they rarely convert on a click."),
        _na("Commercial keywords", "ready to buy",
            "Where paid earns its keep. The intent classifier already labels these."),
        _na("Competitor keywords", "what rivals target",
            "Expensive, but sometimes the fastest route into an auction."),
        _na("Negative research", "what to block before launch",
            "'free', 'jobs', 'course', 'salary', 'DIY' — decided up front, not after."),
        _na("Keyword grouping", "tight themes",
            "One theme per ad group is what makes ad relevance achievable."),
        _na("Match type plan", "exact / phrase / broad",
            "Start exact and phrase. Broad only once smart bidding has data."),
        _na("Budget needed", "to be visible on these",
            r if not on else "Volume × CPC estimates what visibility actually costs."),
        _na("SEO keywords worth bidding", "double coverage",
            "The interlock board decides when to bid on something you already rank for."),
        _na("German keyword research", "for DE and CH",
            "Your two uncovered markets. Keyword Planner covers German volume."),
        _na("Keyword shortlist", "what to launch with",
            "The output of this board: a costed, grouped, negatived starting list."),
    ])


# ======================================================================
#  ⑮ CROSS-CHANNEL INTERLOCK  (22)  — the gap, and it works TODAY
# ======================================================================
def board_interlock(ctx) -> str:
    ctx = _ctx(ctx)
    it = ctx.get("interlock") or {}
    ov = it.get("overlap") or {}
    gap = it.get("gap_cover") or []
    t2c = it.get("terms_to_content") or []
    c2a = it.get("content_to_ads") or []
    q = it.get("quality") or {}
    defence = it.get("aeo_defence") or []
    markets = it.get("markets") or []
    cac = it.get("cac") or {}
    ads_on = it.get("ads_connected")
    return _head("🔗", "Cross-channel interlock",
                 "The wiring between SEO, AEO, GEO and Ads. Every section used to "
                 "be blind to the others — this is the board that makes them one "
                 "system. Most of it works without Google Ads.") + _subnav(
        ["Paid vs organic", "Content flow", "Quality & defence", "Money"]) + _sub(
        "Paid vs organic", "Are the two channels helping each other or competing?") + _vizcards([
        ("Paid + organic overlap", ov.get("count", 0), "queries in both channels", "",
         ("Not automatically waste — brand defence is real — but at a top-3 organic "
          "position the incremental paid click is expensive."
          if ads_on else "Fills when Google Ads connects; the organic half is ready."),
         "GSC + search terms", AMBER if ov.get("count") else BLUE, ""),
        ("Cannibalised spend", f"€{ov.get('spend_at_risk', 0):,.0f}", "on top-3 organic queries", "",
         ("Money spent on clicks you would likely have won for free."
          if ov.get("spend_at_risk") else "Nothing being paid for twice."),
         "computed", PINK if ov.get("spend_at_risk") else GREEN,
         _rows(ov.get("cannibalised") or [],
               left_fmt=lambda x: x.get("query", "")[:34],
               right_fmt=lambda x: f"#{x.get('organic_position')} · €{x.get('ad_cost', 0):.0f}",
               empty="No overlap detected.")),
        ("Organic gaps for paid", len(gap), "proven demand, no ranking",
         _hbars([(g["query"][:18], g["impressions"]) for g in gap[:8]], TEAL) if gap else "",
         ("Your queries sit at #42-97. These have real impressions and no organic "
          "visibility — exactly what paid should cover in the meantime."),
         "GSC (live)", GREEN if gap else AMBER,
         _rows(gap, left_fmt=lambda g: g.get("query", "")[:34],
               right_fmt=lambda g: f"page {g.get('page')} · {g.get('impressions')} impr",
               empty="")),
        _na("Brand vs non-brand", "across both channels",
            "Brand traffic flatters both. Split it or be misled by both."),
        _na("Paid share of clicks", "how much traffic you rent vs own",
            "Renting all your traffic is a risk; owning none is slow. The mix matters."),
        ("Incrementality", "—", "does paid ADD customers?",
         "", ("The hardest question in media buying. Answered by pausing a "
              "campaign and watching whether total leads fall."),
         "requires a test", BLUE, ""),
    ]) + _sub("Content flow", "Each channel's data is the other's brief.") + _vizcards([
        ("Ads terms → content", len(t2c), "converted, no page exists", "",
         ("A search term that CONVERTED is the highest-confidence content brief "
          "there is — a real person typed it and became a lead."
          if ads_on else "Needs Google Ads; the content side is ready to receive it."),
         "search terms → strategist", GREEN if t2c else BLUE,
         _rows(t2c, left_fmt=lambda x: x.get("term", "")[:34],
               right_fmt=lambda x: f"{x.get('conversions')} conv", empty="")),
        ("Content → ad copy", len(c2a), "proven organic headlines", "",
         ("Titles that already beat expected click-through are pre-tested ad "
          "headlines, on this exact audience."),
         "GSC + crawler (live)", GREEN if c2a else AMBER,
         _rows(c2a, left_fmt=lambda x: x.get("query", "")[:34],
               right_fmt=lambda x: f"{x.get('ctr')}% CTR · {x.get('clicks')} clicks",
               empty="")),
        _na("SEO keywords → ad keywords", "what to bid on",
            "Striking-distance queries are candidates for paid cover."),
        _na("Ad keywords → SEO targets", "what to write about",
            "Expensive paid keywords are the strongest case for organic investment."),
        _na("Winning ad copy → page titles", "reverse flow",
            "A headline that wins in paid usually wins in the SERP too."),
        _na("Content calendar ← paid demand", "publish what people search",
            "The strategist can take its brief from converting search terms."),
    ]) + _sub("Quality & defence", "Where one channel's weakness costs the other.") + _vizcards([
        ("Landing page quality", q.get("predicted_lp_experience", "—") if q.get("ready") else "—",
         "feeds Quality Score", _score_gauge(q.get("on_page_score", 0), 85) if q.get("ready") else "",
         (q.get("why", "") if q.get("ready") else "Run a crawl."),
         "crawler → Quality Score", _pct_color(q.get("on_page_score", 0)) if q.get("ready") else AMBER, ""),
        ("AI answer defence", len(defence), "questions a rival owns", "",
         ("Where an AI names a competitor, content fixes it eventually and paid "
          "fixes it this afternoon."),
         "AEO probe (live)", PINK if defence else GREEN,
         _rows(defence, left_fmt=lambda d: d.get("prompt", "")[:38],
               right_fmt=lambda d: ", ".join(d.get("rivals", []))[:20], empty="")),
        ("Paid-only markets", len([m for m in markets if m.get("paid_is_only_lever")]),
         "no content in their language",
         _hbars([(m["market"][:12], m.get("organic_pages", 0)) for m in markets], BLUE)
         if markets else "",
         ((", ".join(m["market"] for m in markets if m.get("paid_is_only_lever"))
           + " — organic is impossible there today. Paid is the only lever until "
             "German content ships.")
          if any(m.get("paid_is_only_lever") for m in markets)
          else "Every market has content in its language."),
         "GEO audit (live)", PINK if any(m.get("paid_is_only_lever") for m in markets) else GREEN, ""),
        _na("Slow pages costing CPC", "speed → Quality Score → price",
            "A slow landing page raises the price of every keyword pointing at it."),
        _na("Schema → rich results → CTR", "shared signal",
            "Structured data helps organic CTR; ad extensions do the paid equivalent."),
        _na("Shared negative intent", "what neither channel wants",
            "'free', 'jobs', 'course' — the SEO intent classifier already flags these."),
    ]) + _sub("Money", "One number, all channels.") + _vizcards([
        ("Blended CAC", f"€{cac.get('cac'):,.0f}" if cac.get("cac") else "—",
         "every channel combined",
         _waterfall([("Ads", cac.get("ads_spend", 0)), ("Engine", cac.get("engine_spend", 0))])
         if cac.get("total_spend") else "",
         (f"{cac.get('verdict', '')} — €{cac.get('total_spend', 0):,.0f} across "
          f"{cac.get('customers', 0)} customers." if cac.get("cac")
          else "The only number that answers 'is this working'. Needs customers won."),
         "cross-channel", GREEN if cac.get("verdict") == "profitable" else AMBER, ""),
        ("Cost per booking", f"€{cac.get('cost_per_booking'):,.0f}" if cac.get("cost_per_booking")
         else "—", "across ads, SEO and outreach", "",
         ("Cal.com bookings against total spend." if cac.get("cost_per_booking")
          else "Fills as bookings arrive."),
         "Cal.com + spend", VIOLET, ""),
        ("Channel efficiency", "—", "which channel is cheapest",
         "", "Compare cost per booking by source once each has volume.",
         "computed", BLUE, ""),
        _na("Offline conversions → Google", "close the loop",
            "Upload won deals so Google optimises for clients, not form fills. This "
            "is the highest-value wire on the whole board."),
    ])


# ======================================================================
#  ⑯ WORK ORDERS & CHANGE HISTORY  (16)
# ======================================================================
def board_work(ctx) -> str:
    ctx = _ctx(ctx)
    orders = ctx.get("orders") or []
    chg = ctx.get("changes") or {}
    ads = ctx.get("ads") or {}
    on = bool(ads.get("connected"))
    r = _off(ads.get("reason"))
    open_o = [o for o in orders if o.get("status") == "open"]
    return _head("🛠", "Media work orders & changes",
                 "Every finding becomes a tracked job — the same queue discipline "
                 "as the SEO engine.") + _vizcards([
        ("Open decisions", len(open_o), "queued",
         _riskmatrix([((o.get("code") or "")[:14],
                       min(3, max(1, 4 - round(o.get("effort", 3) / 2))),
                       min(3, max(1, round(o.get("impact", 30) / 34) + 1)))
                      for o in open_o[:12]]) if open_o else "",
         ("Ranked by impact ÷ effort." if open_o else
          "Fills once Google Ads is connected and the engines run."),
         "work orders", AMBER if open_o else GREEN,
         _rows(open_o, left_fmt=lambda o: (o.get("fix") or o.get("code", ""))[:44],
               right_fmt=lambda o: o.get("severity", ""), empty="")),
        _na("Auto-applicable", "safe to apply without asking",
            "Adding negative keywords and pausing disapproved ads are reversible "
            "and safe. Bid and budget changes are not — those wait for you."),
        _na("Awaiting approval", "money-affecting changes",
            "Anything that changes spend stops here. That is deliberate."),
        ("Changes recorded", len(chg.get("changes") or []) if on else "—", "in the last 30 days",
         "", (r if not on else
              "Every performance shift should be traceable to an edit. This is that record."),
         "change_event", BLUE if on else AMBER,
         _rows(chg.get("changes") or [],
               left_fmt=lambda c: f"{c.get('resource', '')} · {c.get('user', '')[:18]}",
               right_fmt=lambda c: str(c.get("at", ""))[:10], empty="")),
        _na("Changes by type", "what gets edited most",
            r if not on else "Frequent bid edits usually mean the strategy is wrong."),
        _na("Change → performance", "did it work?",
            r if not on else "The only way to learn from an edit is to measure after it."),
        _na("Rollback", "undo a change",
            "Every applied change records its before-state, as on the SEO side."),
        _na("Experiments", "A/B test a change before committing",
            r if not on else "Drafts and experiments let you test at 50% budget."),
        _na("Change freeze", "during learning periods",
            "Editing mid-learning resets it. The engine should refuse."),
        _na("Approval history", "what you approved and when",
            "Your decisions, recorded."),
        _na("Engine runs", "when each puller last ran",
            "Stale data behind a confident number is the worst failure mode."),
        _na("Safety rules", "what the agent may never do",
            "It may never raise a budget, change a bid target by more than 20%, or "
            "launch a campaign without approval."),
        _na("Spend guardrail", "hard cap",
            "Ad spend is separate from the €200 engine cap and needs its own ceiling."),
        _na("Alerting", "when something breaks",
            "Disapproved ads, tracking failures and pacing overruns should page you."),
        _na("Weekly digest", "what happened",
            "One email: what changed, what it cost, what it returned."),
        _na("Next review", "when to look again",
            "Most of this account should be reviewed weekly, not daily."),
    ])


# ======================================================================
#  ASSEMBLY
# ======================================================================
TABS = [
    ("mbcmd", "🎯", "Media Command"),
    ("mbhealth", "🩺", "Account Health"),
    ("mbtypes", "🗂", "Campaign Types"),
    ("mbterms", "🔍", "Search Terms"),
    ("mbkw", "🔑", "Keywords & QS"),
    ("mbbid", "⚖️", "Bidding"),
    ("mbbudget", "💰", "Budget & Pacing"),
    ("mbtarget", "🌍", "Targeting"),
    ("mbaud", "👥", "Audiences"),
    ("mbads", "✍️", "Ads & Assets"),
    ("mbconv", "🎣", "Conversion"),
    ("mbland", "🛬", "Landing Pages"),
    ("mbcomp", "⚔️", "Competition"),
    ("mbresearch", "🔬", "Keyword Research"),
    ("mblink", "🔗", "Cross-Channel"),
    ("mbwork", "🛠", "Work Orders"),
]

GROUPS = [
    ("mbact", "③ ACT", "What should I do?", ["mbcmd", "mbwork"]),
    ("mbdiag", "① DIAGNOSE", "What's wrong?",
     ["mbhealth", "mbterms", "mbkw", "mbland"]),
    ("mbdecide", "② DECIDE", "Where should the money go?",
     ["mbtypes", "mbbid", "mbbudget", "mbtarget", "mbaud", "mbads", "mbresearch"]),
    ("mbsrc", "④ CONNECT", "How do the channels join up?",
     ["mblink", "mbconv", "mbcomp"]),
]

_TAB_BOARDS = {
    "mbcmd": [("Media Command", board_command)],
    "mbhealth": [("Account Health", board_health)],
    "mbtypes": [("Campaign Types", board_types)],
    "mbterms": [("Search Terms", board_terms)],
    "mbkw": [("Keywords & QS", board_keywords)],
    "mbbid": [("Bidding", board_bidding)],
    "mbbudget": [("Budget & Pacing", board_budget)],
    "mbtarget": [("Targeting", board_targeting)],
    "mbaud": [("Audiences", board_audiences)],
    "mbads": [("Ads & Assets", board_ads)],
    "mbconv": [("Conversion", board_conversion)],
    "mbland": [("Landing Pages", board_landing)],
    "mbcomp": [("Competition", board_competition)],
    "mbresearch": [("Keyword Research", board_research)],
    "mblink": [("Interlock", board_interlock)],
    "mbwork": [("Media Work Orders", board_work)],
}

CARD_COUNTS = {"command": 14, "health": 20, "types": 20, "terms": 18, "keywords": 20,
               "bidding": 24, "budget": 18, "targeting": 20, "audiences": 18,
               "ads": 20, "conversion": 20, "landing": 16, "competition": 14,
               "research": 16, "interlock": 22, "work": 16}
TOTAL_CARDS = sum(CARD_COUNTS.values())

_TAB_COUNTS = {"mbcmd": 14, "mbhealth": 20, "mbtypes": 20, "mbterms": 18, "mbkw": 20,
               "mbbid": 24, "mbbudget": 18, "mbtarget": 20, "mbaud": 18, "mbads": 20,
               "mbconv": 20, "mbland": 16, "mbcomp": 14, "mbresearch": 16,
               "mblink": 22, "mbwork": 16}


def _safe_board(name, fn, ctx) -> str:
    _CURRENT_BOARD["name"] = name
    try:
        return fn(ctx)
    except Exception as e:
        H = _H()
        return ("<div class='card full' style='margin-top:12px;border-color:#FF6B93'>"
                f"<p class='ct'>⚠ {H._esc(name)} board failed to render</p>"
                f"<p class='cc'>{H._esc(type(e).__name__)}: {H._esc(str(e)[:300])}</p>"
                "<p class='cc'>Every other board is unaffected.</p></div>")


def media_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def media_section(ctx) -> str:
    """All 296 cards in ONE dashboard section, same system as SEO."""
    H = _H()
    panels = media_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'mbact')}' onclick=\"seoTab('{tid}')\">"
        f"<span>{icon}</span>{H._esc(label)}"
        f"<span class='n'>{_TAB_COUNTS.get(tid, 0)}</span></button>"
        for i, (tid, icon, label) in enumerate(TABS))
    grouprail = "".join(
        f"<button class='sgrp{' on' if i == 0 else ''}' id='sgrp-{gid}' "
        f"onclick=\"seoGroup('{gid}')\"><b>{H._esc(label)}</b>"
        f"<span class='gq'>{H._esc(question)}</span></button>"
        for i, (gid, label, question, _t) in enumerate(GROUPS))
    body = "".join(
        f"<div class='spanel{' on' if i == 0 else ''}' id='spanel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _, _) in enumerate(TABS))
    runbar = ("<div class='ctrl' style='margin:10px 0 2px;flex-wrap:wrap'>"
              "<button class='cbtn' onclick='runAds()'>▶ Pull Google Ads data</button>"
              "<button class='cbtn' onclick='runInterlock()'>🔗 Rebuild cross-channel (free)</button>"
              "<button class='cbtn' onclick='openEcon()'>💶 Set unit economics</button>"
              "<button class='cbtn' onclick=\"nav('map')\">🔌 Connect Google Ads</button>"
              "</div>")
    tools = ("<div class='stools'>"
             "<input id='cardq2' class='cinput' placeholder='🔎 Search all 296 media cards…' "
             "oninput='seoFilter()'>"
             "<button class='cbtn sm' onclick=\"seoSev('all')\">All</button>"
             "<button class='cbtn sm' onclick=\"seoSev('critical')\">⛔ Needs fixing</button>"
             "<button class='cbtn sm' onclick=\"seoSev('warn')\">⚠ Worth a look</button>"
             "<button class='cbtn sm' onclick=\"seoSev('ok')\">✓ Healthy</button></div>")
    hint = (f"<div class='shint'>👇 <b>{TOTAL_CARDS} media-buying cards</b> in "
            f"{len(GROUPS)} groups. Google Ads is not connected yet — cards that "
            f"need it say so instead of showing a fake zero.</div>")
    return (_TAB_CSS + runbar + hint
            + f"<div class='sgroups'>{grouprail}</div>"
            + f"<div class='stabs'>{bar}</div>" + tools + body)


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_ads as ADS
    import content_engine_crosschannel as CX

    econ = {"avg_deal_value": 5000, "gross_margin_pct": 60,
            "consult_to_client_pct": 25, "lead_to_consult_pct": 40}
    crawl = {"count": 3, "urls": [
        {"url": "https://x.com/services/regulated/", "status": 200, "title": "Regulated",
         "words": 900, "ms": 3000, "meta_desc": "d", "h2": [], "schema_types": [],
         "outbound_links": [], "internal_links": []},
        {"url": "https://x.com/blog/a/", "status": 200, "title": "Blog A", "words": 120,
         "ms": 400, "meta_desc": "", "h2": [], "schema_types": [], "outbound_links": [],
         "internal_links": []}]}
    gsc = {"queries": [{"key": "automation agency", "position": 2.1, "impressions": 400, "clicks": 40},
                       {"key": "n8n consultant", "position": 55.0, "impressions": 120, "clicks": 0}]}
    geo = {"language": {"markets": [{"market": "Germany", "language": "de", "pages": 0},
                                    {"market": "United States", "language": "en", "pages": 240}],
                        "uncovered": ["Germany"]},
           "performance": {"markets": [{"market": "United States", "impressions": 300}]},
           "service_areas": {"missing": ["Germany"]}}
    inter = CX.interlock(crawl=crawl, audit={"scores": {"on_page": 54}}, gsc=gsc,
                         aeo={"gaps": [{"prompt": "best agency", "rivals": ["pricefy.io"]}]},
                         geo=geo, ads={"connected": False}, search_terms={"terms": []},
                         econ=econ, bookings=6, customers=2, api_spend=60)
    ctx = {"ads": ADS.account(), "terms": ADS.search_terms(), "kw": ADS.keywords(),
           "assets": ADS.ad_assets(), "conv_actions": ADS.conversion_actions(),
           "targeting": ADS.targeting(), "audiences": ADS.audiences(),
           "ad_status": ADS.ad_status(), "changes": ADS.change_history(),
           "recs": ADS.recommendations(), "kw_ideas": ADS.keyword_ideas([]),
           "econ": econ, "targets": ADS.targets(econ), "interlock": inter,
           "crawl": crawl, "geo": geo, "markets": inter["markets"],
           # REAL shape from content_engine_competitors: {query: [domain, ...]}.
           # The flat {domain: count} fixture I first wrote is exactly what let a
           # TypeError reach the live dashboard and blank this board.
           "competitor_intel": {"serp_ads": {"automation agency": ["pricefy.io", "zapier.com"],
                                             "n8n consultant": ["pricefy.io"]},
                                "competitors": [{"domain": "pricefy.io"}]},
           "pacing": {"ready": False}, "is_summary": {}, "is_rows": [], "bid_advice": [],
           "funnel": [], "orders": []}

    # every board renders on this context without raising
    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = media_pages(ctx)
    assert set(pages) == {t for t, _, _ in TABS}, list(pages)
    html = "".join(pages.values())
    assert "failed to render" not in html, "a board failed on real data"

    counted = len(re.findall(r"<div class='card (?:overflowcard )?sev-", html))
    assert counted == TOTAL_CARDS, f"expected {TOTAL_CARDS} cards, rendered {counted}"
    for tab, want in _TAB_COUNTS.items():
        got = len(re.findall(r"<div class='card (?:overflowcard )?sev-", pages[tab]))
        assert got == want, f"{tab}: rendered {got}, declared {want}"

    ids = re.findall(r"<div class='card (?:overflowcard )?sev-[a-z]+' id='(card-[a-z0-9-]+)'", html)
    assert len(ids) == TOTAL_CARDS and len(set(ids)) == len(ids), \
        f"{len(ids)} ids, {len(set(ids))} unique"
    assert html.count("class='cta'") >= TOTAL_CARDS, "every card must end in a verb"
    assert html.count("data-sev=") == TOTAL_CARDS

    # honest degrade — never a fake zero where Google Ads is required
    assert "Connect Google Ads" in html, "must say WHY the numbers are missing"
    assert "not connected" in html
    # the boards that work WITHOUT the Ads API must carry real numbers
    land = pages["mbland"]
    assert "Landing page experience" in land and "average" in land, land[:200]
    link = pages["mblink"]
    assert "n8n consultant" in link, "organic gap cover must be live"
    assert "Germany" in link and "only lever until" in link, "paid-only market must surface"
    # €60 engine spend / 2 customers = €30 CAC, with Ads at zero (not connected)
    assert "€30" in link, "blended CAC must compute from the channels that ARE live"
    cmd = pages["mbcmd"]
    assert "€90" in cmd or "90" in cmd, "target CPA from unit economics must show"
    # the honest limitation is stated, not hidden
    assert "NOT available in the Google Ads API" in pages["mbcomp"], "Auction Insights caveat"
    comp = pages["mbcomp"]
    assert "pricefy.io" in comp and "zapier.com" in comp, "advertisers not aggregated"

    # ---- SHAPE ROBUSTNESS ----
    # Every board must survive whatever the store actually hands it. Three
    # outages this session were a fixture shape that did not match reality.
    _hostile = [{}, None, "not a dict", 42,
                {k: None for k in ctx}, {k: [] for k in ctx}, {k: {} for k in ctx},
                {k: "str" for k in ctx}, {k: 0 for k in ctx},
                dict(ctx, competitor_intel={"serp_ads": ["not", "a", "dict"]}),
                dict(ctx, competitor_intel={"serp_ads": {"q": 4}}),
                dict(ctx, ads={"connected": True, "campaigns": None}),
                dict(ctx, targets={"ready": True})]
    for i, bad in enumerate(_hostile):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"board {name} raised on hostile context #{i}: "
                                     f"{type(e).__name__}: {e}") from e

    sec = media_section(ctx)
    for tid, _, _ in TABS:
        assert f"id='stab-{tid}'" in sec and f"id='spanel-{tid}'" in sec, tid
    for gid, _l, _q, _t in GROUPS:
        assert f"id='sgrp-{gid}'" in sec, gid
    grouped = [t for _g, _l, _q, ts in GROUPS for t in ts]
    assert sorted(grouped) == sorted(t for t, _, _ in TABS), "every tab in exactly one group"
    assert sec.count("class='spanel on'") == 1 and sec.count("class='stab on'") == 1
    assert "overflowcard" in sec and "Show all" in sec, "progressive disclosure"
    assert "id='cardq2'" in sec, "search box"
    print(f"media_boards self-check OK — 16 boards, {counted} cards, "
          f"{len(set(ids))} unique ids, {html.count('<svg')} charts, honest degrade "
          f"on Google Ads, live data on landing/interlock/economics")
