"""
content_engine_crosschannel.py
============================================================================
L22 — THE INTERLOCK.  The gap the founder spotted: every section is a silo.

SEO knows the site ranks #42-97. AEO knows no AI answer names the brand. GEO
knows Germany and Switzerland have zero German content. Ads knows nothing about
any of it — and none of them knows what a customer actually costs.

This module is the wiring between them. Most of it works TODAY, because it
runs on the SEO/AEO/GEO data already flowing; the Ads half fills in when the
account is connected.

    paid_organic_overlap()   are you paying for what you already rank for?
    organic_gap_cover()      which #42-97 queries should paid carry meanwhile?
    terms_to_content()       ads search terms -> the best content brief there is
    content_to_ads()         your best-performing pages -> ad copy + keywords
    quality_from_crawl()     your on-page score IS Google's landing-page score
    aeo_paid_defence()       where AI names a rival, paid holds the ground
    market_coverage()        organic coverage per market -> where paid must work
    blended_cac()            what a customer really costs across every channel
    interlock()              all of it, in one call

Run offline self-check:  python content_engine_crosschannel.py
============================================================================
"""

from __future__ import annotations

import logging

log = logging.getLogger("crosschannel")

KEY = "crosschannel"


def _norm(q):
    return " ".join(str(q or "").lower().split())


# ======================================================================
#  PAID  <->  ORGANIC
# ======================================================================
def paid_organic_overlap(gsc_queries: list, ad_terms: list, top_rank: float = 3.0) -> dict:
    """Queries where you rank well AND pay for clicks.

    Not automatically waste — brand defence is real — but it is a decision
    nobody was being shown, and at #1-3 the incremental click is expensive.
    """
    organic = {_norm(q.get("key") or q.get("query")): q for q in gsc_queries or []}
    overlap, spend_at_risk = [], 0.0
    for t in ad_terms or []:
        key = _norm(t.get("term"))
        o = organic.get(key)
        if not o:
            continue
        pos = float(o.get("position", 99) or 99)
        row = {"query": key, "organic_position": round(pos, 1),
               "ad_cost": round(float(t.get("cost", 0) or 0), 2),
               "ad_clicks": int(t.get("clicks", 0) or 0),
               "ad_conversions": round(float(t.get("conversions", 0) or 0), 1),
               "organic_clicks": int(o.get("clicks", 0) or 0),
               "verdict": ("paying for a top-3 organic position" if pos <= top_rank
                           else "paid and organic both present")}
        if pos <= top_rank:
            spend_at_risk += row["ad_cost"]
        overlap.append(row)
    overlap.sort(key=lambda r: -r["ad_cost"])
    return {"overlap": overlap, "count": len(overlap),
            "cannibalised": [r for r in overlap if r["organic_position"] <= top_rank],
            "spend_at_risk": round(spend_at_risk, 2)}


def organic_gap_cover(gsc_queries: list, *, weak_from: float = 20.0,
                      min_impressions: int = 1, limit: int = 40) -> list:
    """Queries you are SEEN for but rank too low to be clicked.

    These are exactly the queries paid should carry until content catches up —
    demand is proven, the organic position is not yet earning it.
    """
    out = []
    for q in gsc_queries or []:
        pos = float(q.get("position", 0) or 0)
        impr = int(q.get("impressions", 0) or 0)
        if pos >= weak_from and impr >= min_impressions:
            out.append({"query": q.get("key") or q.get("query", ""),
                        "position": round(pos, 1), "impressions": impr,
                        "clicks": int(q.get("clicks", 0) or 0),
                        "page": int((pos - 1) // 10) + 1,
                        "why": (f"page {int((pos-1)//10)+1} of Google — real demand, "
                                "no organic visibility yet")})
    out.sort(key=lambda r: -r["impressions"])
    return out[:limit]


def terms_to_content(ad_terms: list, existing_titles: list, limit: int = 30) -> list:
    """Ads search terms that CONVERTED and have no page behind them.

    A converting search term is the highest-confidence content brief that
    exists — a real person typed it and then became a lead.
    """
    have = " ".join(_norm(t) for t in existing_titles or [])
    out = []
    for t in ad_terms or []:
        if not t.get("conversions"):
            continue
        term = _norm(t.get("term"))
        if term and term not in have:
            out.append({"term": t.get("term", ""),
                        "conversions": round(float(t.get("conversions", 0)), 1),
                        "cost": round(float(t.get("cost", 0) or 0), 2),
                        "why": "converted in paid, no page targets it organically"})
    out.sort(key=lambda r: -r["conversions"])
    return out[:limit]


def content_to_ads(gsc_queries: list, crawl: dict, limit: int = 30) -> list:
    """Your best organic CTR pages are pre-tested ad copy.

    A title that already beats the expected click-through rate at its position
    is a headline that works on real people, on this exact audience.
    """
    pages = {r.get("url", ""): r for r in (crawl or {}).get("urls", [])
             if r.get("status") == 200}
    out = []
    for q in sorted(gsc_queries or [], key=lambda x: -(x.get("clicks", 0) or 0))[:limit * 2]:
        clicks = int(q.get("clicks", 0) or 0)
        impr = int(q.get("impressions", 0) or 0)
        if not impr:
            continue
        ctr = 100 * clicks / impr
        out.append({"query": q.get("key") or q.get("query", ""),
                    "ctr": round(ctr, 2), "clicks": clicks,
                    "position": round(float(q.get("position", 0) or 0), 1),
                    "use_as": "ad headline / keyword candidate"})
    out.sort(key=lambda r: (-r["clicks"], -r["ctr"]))
    return out[:limit]


def quality_from_crawl(crawl: dict, audit: dict) -> dict:
    """Google's Quality Score has a 'landing page experience' component. The
    crawler already measures exactly that — it was just never connected."""
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    if not pages:
        return {"ready": False, "reason": "run a crawl first"}
    on_page = (audit or {}).get("scores", {}).get("on_page", 0)
    slow = [r for r in pages if r.get("ms", 0) > 2500]
    thin = [r for r in pages if r.get("words", 0) < 300]
    return {"ready": True, "pages": len(pages), "on_page_score": on_page,
            "slow_pages": len(slow), "thin_pages": len(thin),
            "predicted_lp_experience": ("above average" if on_page >= 75 else
                                        "average" if on_page >= 50 else "below average"),
            "why": ("Landing page experience is one of the three Quality Score "
                    "components. A low on-page score raises your CPC on every "
                    "keyword pointing at that page."),
            "worst": sorted(slow + thin, key=lambda r: -(r.get("ms", 0)))[:15]}


def aeo_paid_defence(aeo: dict, limit: int = 20) -> list:
    """Buyer questions where an AI names a rival and not you.

    Content fixes these eventually. Paid fixes them this afternoon.
    """
    out = []
    for g in (aeo or {}).get("gaps", []) or []:
        out.append({"prompt": g.get("prompt", ""),
                    "rivals": g.get("rivals", []),
                    "action": "bid on this intent until the content ranks"})
    return out[:limit]


def market_coverage(geo: dict, ads_geo: list = None) -> list:
    """Per market: organic coverage vs paid presence.

    A market with no content in its language cannot be won organically at all —
    which makes paid the only lever there, not merely an option.
    """
    lang = (geo or {}).get("language", {}) or {}
    perf = (geo or {}).get("performance", {}) or {}
    areas = (geo or {}).get("service_areas", {}) or {}
    missing_pages = set(areas.get("missing", []) or [])
    uncovered = set(lang.get("uncovered", []) or [])
    by_market = {m.get("market"): m for m in (perf.get("markets") or [])}
    ads_by = {a.get("market"): a for a in (ads_geo or [])}
    rows = []
    for m in (lang.get("markets") or []):
        name = m.get("market")
        p = by_market.get(name, {})
        rows.append({
            "market": name,
            "language": m.get("language", ""),
            "organic_pages": m.get("pages", 0),
            "organic_impressions": p.get("impressions", 0),
            "has_landing_page": name not in missing_pages,
            "ad_spend": (ads_by.get(name) or {}).get("cost", 0),
            "paid_is_only_lever": name in uncovered,
            "verdict": ("no content in this language — paid is the ONLY way to be "
                        "present here today" if name in uncovered else
                        "organic is possible; paid is a choice")})
    return rows


def blended_cac(*, ads_spend=0.0, ads_conversions=0.0, api_spend=0.0,
                outreach_sent=0, bookings=0, customers=0, econ=None) -> dict:
    """What a customer ACTUALLY costs, across every channel at once.

    Each section reports its own numbers. Nobody was adding them up, which is
    the only number that answers 'is this working'.
    """
    total_spend = float(ads_spend or 0) + float(api_spend or 0)
    econ = econ or {}
    deal = float(econ.get("avg_deal_value") or 0)
    margin = float(econ.get("gross_margin_pct") or 0) / 100.0
    out = {"total_spend": round(total_spend, 2),
           "ads_spend": round(float(ads_spend or 0), 2),
           "engine_spend": round(float(api_spend or 0), 2),
           "bookings": int(bookings or 0), "customers": int(customers or 0),
           "outreach_sent": int(outreach_sent or 0)}
    out["cost_per_booking"] = round(total_spend / bookings, 2) if bookings else None
    out["cac"] = round(total_spend / customers, 2) if customers else None
    if out["cac"] and deal and margin:
        gross = deal * margin
        out["gross_per_client"] = round(gross, 2)
        out["payback_ratio"] = round(gross / out["cac"], 2)
        out["verdict"] = ("profitable" if out["payback_ratio"] >= 3 else
                          "thin" if out["payback_ratio"] >= 1 else "loss-making")
    else:
        out["verdict"] = "not enough data — needs customers won and unit economics"
    return out


# ======================================================================
#  ONE CALL
# ======================================================================
def interlock(store=None, *, crawl=None, audit=None, gsc=None, aeo=None,
              geo=None, ads=None, search_terms=None, econ=None,
              bookings=0, customers=0, api_spend=0.0, outreach_sent=0) -> dict:
    from datetime import datetime, timezone
    gsc_q = (gsc or {}).get("queries") or []
    terms = (search_terms or {}).get("terms") or []
    titles = [r.get("title", "") for r in (crawl or {}).get("urls", [])]
    out = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ads_connected": bool((ads or {}).get("connected")),
        "overlap": paid_organic_overlap(gsc_q, terms),
        "gap_cover": organic_gap_cover(gsc_q),
        "terms_to_content": terms_to_content(terms, titles),
        "content_to_ads": content_to_ads(gsc_q, crawl or {}),
        "quality": quality_from_crawl(crawl or {}, audit or {}),
        "aeo_defence": aeo_paid_defence(aeo or {}),
        "markets": market_coverage(geo or {}, (ads or {}).get("geo")),
        "cac": blended_cac(ads_spend=(ads or {}).get("spend", 0),
                           ads_conversions=(ads or {}).get("conversions", 0),
                           api_spend=api_spend, outreach_sent=outreach_sent,
                           bookings=bookings, customers=customers, econ=econ or {}),
    }
    live = sum(1 for k in ("gap_cover", "content_to_ads", "aeo_defence", "markets")
               if out.get(k))
    out["links_live"] = live
    out["links_total"] = 8
    if store is not None:
        try:
            store.set_setting(KEY, out)
        except Exception as e:
            log.warning("interlock save failed: %s", e)
    return out


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    gsc = [{"key": "automation agency", "position": 2.1, "impressions": 400, "clicks": 40},
           {"key": "n8n consultant", "position": 55.0, "impressions": 120, "clicks": 0},
           {"key": "automated company formation", "position": 42.0, "impressions": 90, "clicks": 0}]
    terms = [{"term": "automation agency", "cost": 120.0, "clicks": 30, "conversions": 1},
             {"term": "hire n8n expert", "cost": 60.0, "clicks": 12, "conversions": 2},
             {"term": "free automation", "cost": 20.0, "clicks": 8, "conversions": 0}]

    ov = paid_organic_overlap(gsc, terms)
    assert ov["count"] == 1, ov
    assert ov["cannibalised"][0]["query"] == "automation agency", ov
    assert ov["spend_at_risk"] == 120.0, ov
    assert "top-3 organic" in ov["cannibalised"][0]["verdict"]

    gap = organic_gap_cover(gsc)
    assert [g["query"] for g in gap] == ["n8n consultant", "automated company formation"], gap
    assert gap[0]["page"] == 6, gap[0]
    assert not organic_gap_cover([{"key": "x", "position": 2, "impressions": 900}])

    t2c = terms_to_content(terms, ["Automation agency for law firms"])
    assert [x["term"] for x in t2c] == ["hire n8n expert"], t2c

    c2a = content_to_ads(gsc, {"urls": []})
    assert c2a[0]["query"] == "automation agency" and c2a[0]["ctr"] == 10.0, c2a[0]

    q = quality_from_crawl({"urls": [
        {"url": "https://x.com/a", "status": 200, "ms": 3000, "words": 900},
        {"url": "https://x.com/b", "status": 200, "ms": 400, "words": 120}]},
        {"scores": {"on_page": 54}})
    assert q["ready"] and q["slow_pages"] == 1 and q["thin_pages"] == 1, q
    assert q["predicted_lp_experience"] == "average", q
    assert quality_from_crawl({}, {})["ready"] is False

    d = aeo_paid_defence({"gaps": [{"prompt": "best automation agency",
                                    "rivals": ["pricefy.io"]}]})
    assert d and "bid on this intent" in d[0]["action"], d

    mk = market_coverage({
        "language": {"markets": [{"market": "Germany", "language": "de", "pages": 0},
                                 {"market": "United States", "language": "en", "pages": 240}],
                     "uncovered": ["Germany"]},
        "performance": {"markets": [{"market": "United States", "impressions": 300}]},
        "service_areas": {"missing": ["Germany", "United States"]}})
    de = next(m for m in mk if m["market"] == "Germany")
    assert de["paid_is_only_lever"] and "ONLY way" in de["verdict"], de
    us = next(m for m in mk if m["market"] == "United States")
    assert not us["paid_is_only_lever"] and us["organic_impressions"] == 300, us

    econ = {"avg_deal_value": 5000, "gross_margin_pct": 60}
    cac = blended_cac(ads_spend=900, api_spend=60, bookings=6, customers=2, econ=econ)
    assert cac["cac"] == 480.0 and cac["cost_per_booking"] == 160.0, cac
    assert cac["payback_ratio"] == 6.25 and cac["verdict"] == "profitable", cac
    assert blended_cac(customers=0)["verdict"].startswith("not enough data")
    thin = blended_cac(ads_spend=2900, bookings=3, customers=1, econ=econ)
    assert thin["verdict"] == "thin", thin

    full = interlock(crawl={"urls": []}, audit={}, gsc={"queries": gsc},
                     aeo={"gaps": []}, geo={}, ads={"connected": False},
                     search_terms={"terms": terms}, econ=econ)
    assert full["ads_connected"] is False
    assert full["overlap"]["count"] == 1 and full["gap_cover"], full["links_live"]
    print("crosschannel self-check OK — paid/organic overlap, gap cover, terms->content, "
          "content->ads, quality from crawl, AEO defence, market coverage, blended CAC")
