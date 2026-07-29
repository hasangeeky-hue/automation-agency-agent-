"""
content_engine_competitors.py
============================================================================
Competitive Intelligence capture — fills the competitor cards from sources the
engine ALREADY has (Serper search/news/maps, own GSC queries, homepage fetch,
Claude synthesis). No fabrication: every signal carries its source; AI-derived
scores are labelled. Cards that need SimilarWeb/social/AI-visibility tools stay
honestly empty.

Flow:  discover_competitors() -> scan_competitor(domain) per competitor
       -> synthesize() (one cheap Claude call) -> saved to settings
       'competitor_intel' -> rendered in the SEO/AEO/GEO section.
Cost per full scan: ~6-9 Serper credits per competitor + one Haiku call.
============================================================================
"""

from __future__ import annotations

import json
import os
import re

import content_engine_connectors as C

# domains that rank everywhere but are never "competitors"
_PLATFORMS = {
    "reddit.com", "linkedin.com", "youtube.com", "wikipedia.org", "facebook.com",
    "medium.com", "quora.com", "clutch.co", "upwork.com", "fiverr.com", "g2.com",
    "capterra.com", "amazon.com", "google.com", "instagram.com", "x.com",
    "twitter.com", "trustpilot.com", "forbes.com", "github.com", "gartner.com",
    "zapier.com", "make.com", "shopify.com", "wordpress.com", "hubspot.com",
    "salesforce.com", "mckinsey.com", "ibm.com", "microsoft.com", "n8n.io",
}

_SEED_QUERIES = [
    "AI automation agency for small business",
    "n8n automation agency",
    "AI agents for local businesses",
    "business process automation service",
    "AI lead generation agency",
]

_TECH_SIGNS = [
    ("wp-content", "WordPress"), ("cdn.shopify", "Shopify"), ("wix.com", "Wix"),
    ("squarespace", "Squarespace"), ("webflow", "Webflow"), ("_next/", "Next.js"),
    ("googletagmanager", "GTM"), ("gtag(", "GA4"), ("intercom", "Intercom"),
    ("crisp.chat", "Crisp"), ("hs-scripts", "HubSpot"), ("calendly", "Calendly"),
    ("cal.com", "Cal.com"), ("elementor", "Elementor"),
]

_NEWS_BUCKETS = [
    ("funding", ("funding", "raise", "raised", "investment", "seed round", "series ")),
    ("partnerships", ("partner", "partnership", "teams up", "collaborat")),
    ("expansion", ("expand", "expansion", "opens", "new office", "enters ")),
    ("launches", ("launch", "release", "unveil", "introduc", "new product")),
    ("hiring", ("hiring", "jobs", "recruit", "headcount")),
    ("promotions", ("discount", "offer", "promo", "sale", "free trial")),
]


def _own_domain() -> str:
    site = C._env("GSC_SITE_URL") or C._env("EMAIL_WEBSITE") or ""
    m = re.search(r"(?:https?://)?(?:www\.)?([^/\s]+)", site)
    return (m.group(1).lower() if m else "").strip()


def _root(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([^/\s]+)", url or "")
    if not m:
        return ""
    host = m.group(1).lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def discover_competitors(limit: int = 5) -> dict:
    """Who repeatedly ranks for OUR queries = our organic competitors. Uses the
    site's real GSC queries when available, seed queries otherwise. Returns
    {competitors: [domain...], queries_used: [...], serp: {query: [results]}}."""
    own = _own_domain()
    s = C.Serper()
    if not s.available():
        return {"competitors": [], "queries_used": [], "serp": {}}
    queries = []
    try:
        queries = [q.get("query", "") for q in C.Google().gsc_top_queries(limit=8) if q.get("query")]
    except Exception:
        pass
    queries = (queries or []) + _SEED_QUERIES
    queries = queries[:8]
    counts: dict = {}
    serp: dict = {}
    serp_ads: dict = {}
    for q in queries:
        try:
            rows, ads = s.search_with_ads(q, num=10)
        except Exception:
            rows, ads = s.search(q, num=10), []
        serp[q] = rows
        serp_ads[q] = [_root(a) for a in ads if _root(a)]
        for r in rows:
            d = _root(r.get("link", ""))
            if not d or d == own or d in _PLATFORMS:
                continue
            counts[d] = counts.get(d, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    return {"competitors": [d for d, _n in ranked], "queries_used": queries,
            "serp": serp, "serp_ads": serp_ads}


def _fetch_site(domain: str) -> dict:
    """One respectful GET of the competitor homepage -> title/description/tech."""
    rq = C._requests()
    if not rq:
        return {}
    try:
        r = rq.get(f"https://{domain}", timeout=20,
                   headers={"User-Agent": "Mozilla/5.0 (compatible; AnthroposBot/1.0)"})
        html = r.text[:200_000] if r.ok else ""
    except Exception:
        return {}
    if not html:
        return {}
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:140]
    desc = ""
    m = re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']{10,300})", html, re.I)
    if m:
        desc = m.group(1).strip()
    tech = sorted({name for sign, name in _TECH_SIGNS if sign in html.lower()})
    # crude pricing/promo sniff from homepage text
    text = re.sub(r"<[^>]+>", " ", html)
    prices = re.findall(r"(?:€|\$|£|CHF ?)\s?\d{2,5}", text)[:6]
    promo = bool(re.search(r"free trial|limited offer|% off|discount", text, re.I))
    return {"title": title, "description": desc, "tech": tech,
            "prices_seen": prices, "promo_on_site": promo}


def _linkedin_followers(name: str, domain: str) -> int:
    """Free social signal: LinkedIn company-page follower count as shown in
    Google result snippets. 0 when not found."""
    s = C.Serper()
    for q in (f"site:linkedin.com/company {name}", f"site:linkedin.com/company {domain}"):
        for r in s.search(q, num=3):
            m = re.search(r"([\d.,]+)\s*(?:followers|Follower)", (r.get("snippet") or "") + " " + (r.get("title") or ""))
            if m:
                try:
                    return int(re.sub(r"[.,]", "", m.group(1)))
                except Exception:
                    pass
    return 0


def ai_visibility(own_domain: str, rival_domains: list, queries: list) -> dict:
    """MEASURED AI-search visibility using our own Claude key: ask buyer-intent
    questions with live web search and count who actually gets cited/mentioned.
    Real for the Claude engine (labelled est. for others). {} on any failure."""
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return {}
    prompts = [f"What are the best providers for: {q}? Name specific companies/sites."
               for q in (queries or [])[:4]]
    counts = {d: 0 for d in [own_domain] + list(rival_domains)}
    ran = 0
    for ptxt in prompts:
        done = False
        for tool in ("web_search_20260209", "web_search_20250305"):
            try:
                r = client.messages.create(
                    model=os.getenv("CHEAP_MODEL", "claude-haiku-4-5"), max_tokens=400,
                    tools=[{"type": tool, "name": "web_search", "max_uses": 3}],
                    messages=[{"role": "user", "content": ptxt}])
                text = "".join(b.text for b in r.content
                               if getattr(b, "type", "") == "text" and getattr(b, "text", "")).lower()
                for d in counts:
                    if d and (d.lower() in text or d.split(".")[0].lower() in text):
                        counts[d] += 1
                ran += 1
                done = True
                break
            except Exception:
                continue
        if not done:
            break
    if not ran:
        return {}
    return {"prompts_run": ran, "mentions": counts, "engine": "claude"}


def scan_competitor(domain: str, serp: dict, own_queries: list) -> dict:
    """Collect every signal we can for one competitor, all source-tagged."""
    s = C.Serper()
    # SEO: where do they appear in OUR queries' SERPs?
    hits = []
    for q, rows in (serp or {}).items():
        for i, r in enumerate(rows):
            if _root(r.get("link", "")) == domain:
                hits.append({"query": q, "position": i + 1})
    # news signals
    name = domain.split(".")[0]
    news = s.news(f'"{name}" OR "{domain}"', num=8)
    buckets: dict = {k: [] for k, _w in _NEWS_BUCKETS}
    for n in news:
        t = (n.get("title") or "").lower()
        for bucket, words in _NEWS_BUCKETS:
            if any(w in t for w in words):
                buckets[bucket].append(n)
    # local presence / reviews
    places = s.maps(name, num=3)
    place = places[0] if places else {}
    site = _fetch_site(domain)
    nq = max(len(serp or {}), 1)
    return {
        "domain": domain,
        "seo_hits": hits,                       # source: serper serp of OUR queries
        "visibility_index": round(100 * len(hits) / nq),   # share of OUR SERPs (real index)
        "news": news[:5],                       # source: google news via serper
        "news_buckets": {k: v[:3] for k, v in buckets.items()},
        "maps": ({"rating": place.get("rating", 0), "reviews": place.get("reviews", 0),
                  "address": place.get("address", "")} if place else {}),
        "site": site,                           # source: their homepage
        "linkedin_followers": _linkedin_followers(name, domain),   # SERP snippet (free, real)
    }


def synthesize(competitors: list) -> dict:
    """ONE cheap Claude call: turn raw signals into health/risk/forecast/
    recommendations per competitor. Labelled AI analysis; '' -> skipped."""
    if not competitors:
        return {}
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return {}
    slim = []
    for c in competitors:
        slim.append({"domain": c["domain"],
                     "ranks_for_our_queries": c["seo_hits"][:6],
                     "news_titles": [n["title"] for n in c.get("news", [])][:5],
                     "rating": (c.get("maps") or {}).get("rating"),
                     "reviews": (c.get("maps") or {}).get("reviews"),
                     "site_title": (c.get("site") or {}).get("title"),
                     "tech": (c.get("site") or {}).get("tech"),
                     "prices_seen": (c.get("site") or {}).get("prices_seen")})
    prompt = (
        "You are a competitive-intelligence analyst for Anthropos Automation (AI-automation "
        "agency for small businesses; markets US/UK/DE/CH/CA). Using ONLY the signals below, "
        "return STRICT JSON: {\"per_competitor\": {\"<domain>\": {\"health\": 0-100, "
        "\"threat\": \"low|medium|high\", \"risk\": \"one sentence\", \"forecast\": \"one sentence\", "
        "\"products_guess\": \"<=12 words from their site title/desc\", "
        "\"revenue_band_est\": \"pre-revenue|<$1M|$1-10M|$10M+|unknown\", "
        "\"revenue_confidence\": \"low|medium\"}}, "
        "\"recommendations\": [\"3 concrete counter-moves for Anthropos\"]}. "
        "Never invent numbers not present in the signals.\n\nSIGNALS:\n" + json.dumps(slim))
    try:
        model = os.getenv("CHEAP_MODEL", "claude-haiku-4-5")
        r = client.messages.create(model=model, max_tokens=900,
                                   messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
        try:  # count the spend against the cap (haiku pricing)
            u = r.usage
            C._record_cost(u.input_tokens / 1e6 * 1.0 + u.output_tokens / 1e6 * 5.0, "anthropic")
        except Exception:
            pass
        return data
    except Exception:
        return {}


def run_scan(domains: list | None = None, limit: int = 5) -> dict:
    """The full capture: discover (or use given domains) -> scan each -> AI
    synthesis -> persisted to settings['competitor_intel']. Returns the record."""
    from datetime import datetime, timezone
    disc = {"serp": {}, "queries_used": []}
    domains = [_root(d) for d in (domains or []) if _root(d)]
    if not domains:
        disc = discover_competitors(limit=limit)
        domains = disc["competitors"]
    if not domains:
        return {"ok": False, "error": "no competitors found — Serper connected? (or pass domains)"}
    if not disc.get("serp"):
        # manual list given — still need SERP context for the SEO-share card
        s = C.Serper()
        queries = []
        try:
            queries = [q.get("query", "") for q in C.Google().gsc_top_queries(limit=6) if q.get("query")]
        except Exception:
            pass
        queries = (queries or _SEED_QUERIES)[:6]
        disc = {"serp": {q: s.search(q, num=10) for q in queries}, "queries_used": queries}
    scans = [scan_competitor(d, disc["serp"], disc.get("queries_used", [])) for d in domains[:limit]]
    ai = synthesize(scans)
    aivis = ai_visibility(_own_domain(), [c["domain"] for c in scans],
                          disc.get("queries_used", []))
    rec = {"ok": True, "scanned_at": datetime.now(timezone.utc).isoformat(),
           "queries_used": disc.get("queries_used", []),
           "competitors": scans, "ai": ai, "ai_visibility": aivis,
           "serp_ads": disc.get("serp_ads", {})}
    try:
        C._set_setting("competitor_intel", rec)
    except Exception:
        pass
    return rec
