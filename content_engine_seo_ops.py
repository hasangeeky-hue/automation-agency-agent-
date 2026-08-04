"""
content_engine_seo_ops.py
============================================================================
The SEO pipeline's control room. One place that RUNS each engine, persists
what it produced, and assembles the context every board renders from.

    run_crawl()      E1  crawl + link graph + money-page support + audit
    run_inspect()    E2  Google's index verdict per URL      (free)
    run_speed()      E3  PageSpeed / Core Web Vitals         (free)
    run_indexnow()   E4  push new URLs to Bing/Yandex        (free)
    run_ranks()      E6  daily rank check for the tracked set
    run_aeo()        E14 AI-answer visibility + quotable audit
    run_offpage()    E11 backlink profile
    run_prospecting() E12 find -> qualify -> pitch (sends nothing)
    run_fixes()      E7/E8/E9 apply auto-fixes, draft copy proposals
    run_all()        the nightly sequence, cheapest-first

    build_ctx()      everything the 11 boards need, read from storage

Every function degrades honestly: a missing key produces a stated reason,
never a fabricated number.

Run offline self-check:  python content_engine_seo_ops.py
============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("seo_ops")

K_CRAWL, K_GRAPH, K_MONEY = "seo_crawl", "seo_graph", "seo_money"
K_AUDIT, K_INSPECT, K_SPEED = "seo_audit", "seo_inspect", "seo_speed"
K_RANKS, K_RUNS, K_QUOT = "seo_ranks", "seo_engine_runs", "seo_quotable"
K_LLMS, K_KEYWORDS, K_INDEXNOW = "seo_llms_txt", "seo_keywords", "seo_indexnow"
K_LOCAL = "seo_local"
K_ACCESS, K_ENTITY, K_NAP = "aeo_crawler_access", "aeo_entity", "geo_nap"
K_ADS, K_INTER = "ads_snapshot", "crosschannel"

MAX_CRAWL_URLS = 300
MAX_INSPECT = 180          # free quota is 2000/day; stay well under
MAX_SPEED = 10
MAX_RANK_KEYWORDS = 80


def _D(v):
    """Any value -> a dict. The store is not always shaped how we assume."""
    return v if isinstance(v, dict) else {}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(store, key, default=None):
    try:
        return store.get_setting(key, default)
    except Exception:
        return default


def _set(store, key, value):
    try:
        store.set_setting(key, value)
    except Exception as e:
        log.warning("could not persist %s: %s", key, e)


def _stamp(store, engine):
    runs = _get(store, K_RUNS, {}) or {}
    runs[engine] = _now()
    _set(store, K_RUNS, runs)


def _site(store):
    import content_engine_connectors as C
    return (C._env("WORDPRESS_URL") or C._env("GSC_SITE_URL")
            or "https://anthropos-automation.com").rstrip("/")


def _trim_crawl(crawl: dict) -> dict:
    """Keep the crawl small enough for a settings row: the fixer needs titles
    and links, nothing needs every anchor tuple."""
    out = dict(crawl)
    urls = []
    for r in (crawl.get("urls") or [])[:MAX_CRAWL_URLS]:
        r = dict(r)
        r["internal_links"] = (r.get("internal_links") or [])[:40]
        r["outbound_links"] = (r.get("outbound_links") or [])[:10]
        r.pop("anchors", None)
        r["h2"] = (r.get("h2") or [])[:12]
        r["h3"] = []
        urls.append(r)
    out["urls"] = urls
    return out


# ======================================================================
#  ENGINES
# ======================================================================
def run_crawl(store, *, max_urls: int = MAX_CRAWL_URLS, delay: float = 0.2) -> dict:
    """E1 + E5. Crawl, build the link graph, then run the full audit and turn
    every finding into a work order. Zero API cost."""
    import content_engine_crawler as CR
    import content_engine_seo as SEO
    import content_engine_workorders as WO

    base = _site(store)
    crawl = CR.crawl_site(base, max_urls=max_urls, delay=delay)
    graph = CR.link_graph(crawl)
    money = CR.money_page_support(crawl, graph)

    gsc, prev_pages, qp = {}, [], []
    try:
        import content_engine_connectors as C
        g = C.Google()
        if g.available():
            gsc = (C.google_insights() or {}).get("gsc") or {}
            prev_pages = g.gsc_range("page", 56, 28, limit=100)
            qp = g.gsc_query_page(28, 500)
    except Exception as e:
        log.warning("GSC feed for audit unavailable: %s", e)

    audit = SEO.full_audit(crawl=crawl, graph=graph, gsc=gsc,
                           gsc_prev_pages=prev_pages, query_page=qp,
                           inspect=_get(store, K_INSPECT, {}) or {})
    _set(store, K_CRAWL, _trim_crawl(crawl))
    _set(store, K_GRAPH, graph)
    _set(store, K_MONEY, money)
    _set(store, K_AUDIT, audit)
    stats = WO.refresh(store, audit)
    _stamp(store, "crawl")
    return {"crawled": crawl.get("count", 0), "issues": audit["summary"]["total"],
            "scores": audit["scores"], "work_orders": stats,
            "orphans": graph.get("orphan_count", 0),
            "striking": len(audit.get("striking") or [])}


def run_inspect(store, *, limit: int = MAX_INSPECT, refresh: bool = False,
                save_every: int = 15) -> dict:
    """E2. Google's own index verdict per URL. Free, 2,000/day.

    RESUMABLE by design: one call per URL over ~180 URLs takes minutes, and a
    container restart mid-run used to throw away everything. Now it
      * skips URLs already inspected (pass refresh=True to re-check them), and
      * persists every `save_every` URLs,
    so an interrupted run picks up where it stopped instead of starting over.
    """
    import content_engine_connectors as C
    g = C.Google()
    if not g.available():
        return {"connected": False, "reason": "Google service account not connected"}
    crawl = _get(store, K_CRAWL, {}) or {}
    all_urls = [r["url"] for r in (crawl.get("urls") or []) if r.get("status") == 200]
    if not all_urls:
        return {"connected": True, "inspected": 0, "reason": "run a crawl first"}

    known = dict(_get(store, K_INSPECT, {}) or {})
    todo = all_urls if refresh else [u for u in all_urls if u not in known]
    todo = todo[:limit]
    if not todo:
        indexed = sum(1 for r in known.values() if r.get("verdict") == "PASS")
        return {"connected": True, "inspected": 0, "total_known": len(known),
                "indexed": indexed, "remaining": 0,
                "reason": "every crawled URL has already been inspected — "
                          "pass refresh=True to re-check"}

    done = 0
    for u in todo:
        try:
            r = g.url_inspect(u)
        except Exception as e:                 # one bad URL must not lose the batch
            log.warning("inspect %s failed: %s", u, e)
            continue
        if r:
            known[u] = r
            done += 1
        if done and done % save_every == 0:    # checkpoint — survives a kill
            _set(store, K_INSPECT, dict(known))   # copy: the in-memory store
                                                  # aliases whatever we hand it
    _set(store, K_INSPECT, dict(known))
    _stamp(store, "inspect")
    indexed = sum(1 for r in known.values() if r.get("verdict") == "PASS")
    remaining = len([u for u in all_urls if u not in known])
    return {"connected": True, "inspected": done, "total_known": len(known),
            "indexed": indexed, "not_indexed": len(known) - indexed,
            "remaining": remaining, "crawled_total": len(all_urls)}


def run_speed(store, *, limit: int = MAX_SPEED) -> dict:
    """E3. One representative URL per template — Lighthouse + CrUX field data."""
    import content_engine_connectors as C
    ps = C.PageSpeed()
    if not ps.available():
        return {"connected": False, "reason": "requests not installed"}
    crawl = _get(store, K_CRAWL, {}) or {}
    live = [r for r in (crawl.get("urls") or []) if r.get("status") == 200]
    picks, seen = [], set()
    for r in live:
        kind = ("home" if r.get("depth") == 0 else
                "service" if "/services/" in r["url"] else
                "guide" if "/guide" in r["url"] else
                "blog" if "/blog" in r["url"] else "other")
        if kind in seen:
            continue
        seen.add(kind)
        picks.append(r["url"])
    picks = (picks + [r["url"] for r in live])[:limit]
    if not picks:
        return {"connected": True, "checked": 0,
                "reason": "no crawled pages yet — run a crawl first"}
    results = ps.check_many(picks, limit=limit)
    _set(store, K_SPEED, results)
    _stamp(store, "speed")
    perf = [r.get("performance", 0) for r in results]
    out = {"connected": True, "checked": len(results), "attempted": len(picks),
           "avg_performance": round(sum(perf) / max(len(perf), 1))}
    if not results:
        # A silent zero here is the exact failure mode this engine exists to
        # avoid. PageSpeed works keyless but is heavily rate-limited.
        out["reason"] = ("PageSpeed returned nothing for any URL. It works without "
                         "a key but is rate-limited hard — set PAGESPEED_API_KEY "
                         "(free from Google Cloud) to raise the quota.")
    return out


def run_indexnow(store, urls=None) -> dict:
    """E4. Instant submission to Bing/Yandex + a sitemap ping for Google."""
    import content_engine_connectors as C
    idx = C.IndexNow()
    if urls is None:
        crawl = _get(store, K_CRAWL, {}) or {}
        urls = [r["url"] for r in (crawl.get("urls") or [])
                if r.get("status") == 200][:200]
    if not urls:
        # Nothing to submit -> do not touch the network at all (a sitemap ping
        # with no new URLs is pure noise, and it made this run block offline).
        return {"status": "no_urls", "ping": "skipped", "submitted": 0,
                "reason": "run a crawl first", "at": _now()}
    status = idx.submit(urls)
    ping = idx.ping_sitemap() if status == "submitted" else "skipped"
    out = {"status": status, "ping": ping,
           "submitted": len(urls) if status == "submitted" else 0, "at": _now()}
    _set(store, K_INDEXNOW, out)
    _stamp(store, "indexnow")
    return out


def tracked_keywords(store, limit: int = MAX_RANK_KEYWORDS) -> list:
    """The daily-tracked set: whatever you saved, else auto-derived from your
    real Search Console queries (highest opportunity first)."""
    saved = _get(store, K_KEYWORDS, []) or []
    if saved:
        return saved[:limit]
    audit = _get(store, K_AUDIT, {}) or {}
    out = [r["query"] for r in (audit.get("striking") or [])]
    gsc = ((_get(store, "google_insights", {}) or {}).get("gsc") or {})
    for r in sorted(gsc.get("queries") or [], key=lambda x: -x.get("impressions", 0)):
        if r.get("key") and r["key"] not in out:
            out.append(r["key"])
    return out[:limit]


def run_ranks(store, *, markets=("us",), limit: int = MAX_RANK_KEYWORDS) -> dict:
    """E6. Daily rank for the tracked set, with day-over-day deltas."""
    import content_engine_connectors as C
    s = C.Serper()
    if not s.available():
        return {"connected": False, "reason": "SERPER_API_KEY not set"}
    kws = tracked_keywords(store, limit)
    if not kws:
        return {"connected": True, "checked": 0,
                "reason": "no keywords yet — run a crawl so Search Console data can seed the list"}
    domain = _site(store).replace("https://", "").replace("http://", "").strip("/")
    fresh = s.rank_batch(kws, domain, markets=markets, limit=limit)
    history = _get(store, K_RANKS, []) or []
    prev = {(h.get("query"), h.get("market")): h.get("position", 0)
            for h in history if h.get("at", "")[:10] != _now()[:10]}
    for r in fresh:
        was = prev.get((r["query"], r["market"]), 0)
        r["at"] = _now()
        r["previous"] = was
        r["delta"] = (was - r["position"]) if (was and r["position"]) else 0
    history = (history + fresh)[-1200:]
    _set(store, K_RANKS, history)
    _stamp(store, "ranks")
    found = sum(1 for r in fresh if r.get("found"))
    return {"connected": True, "checked": len(fresh), "ranking": found,
            "up": sum(1 for r in fresh if r.get("delta", 0) > 0),
            "down": sum(1 for r in fresh if r.get("delta", 0) < 0)}


def run_aeo(store, *, limit: int = 30) -> dict:
    """E14 + E15/E16/E17/E18/E19/E20.

    Probes every connected AI engine, extracts citations, scores answer quality,
    checks whether the AI crawlers are even ALLOWED to read you, audits the
    entity graph, and records a history row so the boards can show a trend.
    """
    import content_engine_aeo as AEO
    crawl = _get(store, K_CRAWL, {}) or {}
    rivals = []
    try:
        ci = _get(store, "competitor_intel", {}) or {}
        rivals = [c.get("domain") for c in (ci.get("competitors") or []) if c.get("domain")]
    except Exception:
        pass
    site = _site(store)
    domain = site.replace("https://", "").replace("http://", "").strip("/")

    # E16 first — if the bots are blocked, everything else is academic.
    access = AEO.crawler_access(site)
    _set(store, K_ACCESS, access)

    out = AEO.run_probes(store, brand="Anthropos", domain=domain,
                         rivals=rivals[:6], limit=limit)
    _set(store, K_QUOT, AEO.quotable_audit(crawl))
    _set(store, K_ENTITY, AEO.entity_audit(crawl))
    _set(store, K_LLMS, AEO.llms_txt(crawl, site_name="Anthropos Automation",
                                     description="AI and n8n business automation for small "
                                                 "and mid-sized companies."))
    _stamp(store, "aeo")
    return {"score": out.get("score", 0), "mention_rate": out.get("mention_rate", 0),
            "prompts": out.get("prompts_tested", 0),
            "engines_live": out.get("engines_live", 0),
            "citations": (out.get("citations") or {}).get("total", 0),
            "gaps": len(out.get("gaps") or []),
            "ai_crawlers_blocked": access.get("blocked_count", 0),
            "ai_crawlers_allowed": access.get("allowed_count", 0)}


def run_geo(store, *, grid_queries: int = 4) -> dict:
    """E21 + E22 — the GEOGRAPHIC half: hreflang, language coverage, market
    performance, service areas, and the local pack grid."""
    import content_engine_geo as GEO
    crawl = _get(store, K_CRAWL, {}) or {}
    gsc = ((_get(store, "google_insights", {}) or {}).get("gsc") or {})
    audit = GEO.run_market_audit(store, crawl, gsc)

    domain = _site(store).replace("https://", "").replace("http://", "").strip("/")
    queries = [q["query"] for q in (_get(store, K_AUDIT, {}) or {}).get("striking", [])]
    if not queries:
        queries = [r.get("key", "") for r in (gsc.get("queries") or [])][:grid_queries]
    grid = GEO.local_grid([q for q in queries if q][:grid_queries], domain)
    if grid:
        _set(store, GEO.GRID_KEY, grid)
    _set(store, K_NAP, GEO.nap_consistency(
        crawl, name=_get(store, "BRAND_NAME", "Anthropos Automation") or ""))
    _stamp(store, "geo")
    return {"score": audit.get("score", 0),
            "hreflang_issues": (audit.get("hreflang") or {}).get("issue_count", 0),
            "uncovered_markets": (audit.get("language") or {}).get("uncovered", []),
            "missing_market_pages": (audit.get("service_areas") or {}).get("missing", []),
            "grid_cells": len(grid)}


def run_offpage(store) -> dict:
    """E11. Your backlink profile — the one thing that genuinely needs a vendor."""
    import content_engine_offpage as OFF
    domain = _site(store).replace("https://", "").replace("http://", "").strip("/")
    prof = OFF.profile(domain, store)
    _stamp(store, "offpage")
    return {"connected": prof.get("connected", False),
            "referring_domains": prof.get("referring_domains", 0),
            "reason": prof.get("reason", "")}


def run_prospecting(store, *, limit: int = 12) -> dict:
    """E12. Find link prospects and draft pitches. SENDS NOTHING."""
    import content_engine_offpage as OFF
    audit = _get(store, K_AUDIT, {}) or {}
    kws = [r["query"] for r in (audit.get("striking") or [])][:4] or \
          ["business automation", "n8n automation"]
    domain = _site(store).replace("https://", "").replace("http://", "").strip("/")
    crawl = _get(store, K_CRAWL, {}) or {}
    best = sorted([r for r in (crawl.get("urls") or []) if r.get("status") == 200],
                  key=lambda r: -(r.get("words") or 0))
    asset = best[0] if best else {}
    return OFF.run_prospecting(
        store, keywords=kws, brand="Anthropos", domain=domain,
        asset_url=asset.get("url", ""), asset_title=asset.get("title", ""),
        asset_value="an original, data-backed guide", sender_name="Murtuja Hasan",
        limit=limit)


def run_fixes(store, *, limit: int = 20, auto_only: bool = True,
              dry_run: bool = False, types=None) -> dict:
    """E7/E8/E9. Apply what may be applied; draft what must be approved."""
    import content_engine_seo_fixer as FIX
    crawl = _get(store, K_CRAWL, {}) or {}
    rep = FIX.run_batch(store, crawl=crawl, limit=limit, auto_only=auto_only,
                        dry_run=dry_run, types=types)
    _stamp(store, "fixes")
    return rep


def run_all(store, *, deep: bool = False) -> dict:
    """The nightly sequence, cheapest-first. Free engines always run; paid ones
    only when their key is present."""
    out = {"at": _now()}
    steps = [("crawl", lambda: run_crawl(store)),
             ("inspect", lambda: run_inspect(store)),
             ("speed", lambda: run_speed(store)),
             ("indexnow", lambda: run_indexnow(store)),
             ("fixes", lambda: run_fixes(store, auto_only=True)),
             ("ranks", lambda: run_ranks(store))]
    if deep:
        steps += [("aeo", lambda: run_aeo(store)),
                  ("geo", lambda: run_geo(store)),
                  ("offpage", lambda: run_offpage(store)),
                  ("prospecting", lambda: run_prospecting(store))]
    for name, fn in steps:
        try:
            out[name] = fn()
        except Exception as e:                 # one engine failing never stops the rest
            log.warning("seo engine %s failed: %s", name, e)
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return out


def run_ads(store) -> dict:
    """M1-M8 — pull everything the media boards read. Free API; key-gated, so
    an unconnected account returns stated reasons rather than zeros."""
    import content_engine_ads as ADS
    from datetime import date
    snap = {"at": _now(),
            "ads": ADS.account(), "terms": ADS.search_terms(), "kw": ADS.keywords(),
            "assets": ADS.ad_assets(), "conv_actions": ADS.conversion_actions(),
            "targeting": ADS.targeting(), "audiences": ADS.audiences(),
            "ad_status": ADS.ad_status(), "changes": ADS.change_history(),
            "recs": ADS.recommendations(), "segments": ADS.segments()}
    camps = (snap["ads"] or {}).get("campaigns") or []
    snap["pacing"] = ADS.pacing(camps, date.today().day)
    snap["is_rows"] = [{"campaign": c.get("name", ""),
                        **ADS.impression_share_verdict(c)} for c in camps]
    snap["is_summary"] = {
        "share": round(sum(c.get("is_share", 0) for c in camps) / max(len(camps), 1), 1),
        "budget": round(sum(c.get("is_lost_budget", 0) for c in camps) / max(len(camps), 1), 1),
        "rank": round(sum(c.get("is_lost_rank", 0) for c in camps) / max(len(camps), 1), 1)}
    tgt = ADS.targets(ADS.get_economics(store))
    snap["bid_advice"] = [{"campaign": c.get("name", ""),
                           **ADS.bid_strategy_advice(c, tgt)} for c in camps]
    seeds = [q["query"] for q in (_get(store, K_AUDIT, {}) or {}).get("striking", [])][:10]
    if not seeds:
        seeds = [r.get("key", "") for r in
                 ((_get(store, "google_insights", {}) or {}).get("gsc") or {}).get("queries", [])][:10]
    snap["kw_ideas"] = ADS.keyword_ideas([s for s in seeds if s])
    _set(store, K_ADS, snap)
    _stamp(store, "ads")
    return {"connected": bool((snap["ads"] or {}).get("connected")),
            "reason": (snap["ads"] or {}).get("reason", ""),
            "campaigns": len(camps),
            "wasted_spend": (snap["terms"] or {}).get("wasted_spend", 0)}


def run_interlock(store) -> dict:
    """L22 — the cross-channel wiring. Works WITHOUT Google Ads."""
    import content_engine_crosschannel as CX
    import content_engine_ads as ADS
    snap = _get(store, K_ADS, {}) or {}
    bookings = customers = 0
    try:
        import content_engine_connectors as C
        bookings = int((C.CalCom().summary() or {}).get("booked", 0) or 0)
    except Exception:
        pass
    try:
        jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
        for j in jobs:
            o = (j.get("payload", {}) or {}).get("outcome") or {}
            customers += int(o.get("customers", 0) or 0)
    except Exception:
        pass
    api_spend = 0.0
    try:
        api_spend = float(store.monthly_cost()) if hasattr(store, "monthly_cost") else 0.0
    except Exception:
        pass
    out = CX.interlock(
        store,
        crawl=_get(store, K_CRAWL, {}) or {}, audit=_get(store, K_AUDIT, {}) or {},
        gsc=((_get(store, "google_insights", {}) or {}).get("gsc") or {}),
        aeo=_get(store, "aeo_visibility", {}) or {},
        geo=_get(store, "geo_market_audit", {}) or {},
        ads=snap.get("ads") or {}, search_terms=snap.get("terms") or {},
        econ=ADS.get_economics(store), bookings=bookings, customers=customers,
        api_spend=api_spend)
    _stamp(store, "interlock")
    return {"links_live": out.get("links_live", 0),
            "cannibalised": (out.get("overlap") or {}).get("count", 0),
            "gap_cover": len(out.get("gap_cover") or []),
            "paid_only_markets": [m["market"] for m in (out.get("markets") or [])
                                  if m.get("paid_is_only_lever")],
            "cac": (out.get("cac") or {}).get("cac")}


def build_media_ctx(store, *, competitor_intel=None) -> dict:
    """Everything the 16 media boards read."""
    import content_engine_ads as ADS
    snap = _get(store, K_ADS, {}) or {}
    inter = _get(store, K_INTER, {}) or {}
    econ = ADS.get_economics(store)
    ctx = dict(snap)
    ctx.update({
        "econ": econ, "targets": ADS.targets(econ), "interlock": inter,
        "crawl": _get(store, K_CRAWL, {}) or {},
        "geo": _get(store, "geo_market_audit", {}) or {},
        "markets": inter.get("markets") or [],
        "competitor_intel": competitor_intel or (_get(store, "competitor_intel", {}) or {}),
        "orders": [], "funnel": [],
    })
    # M13 — findings become tracked jobs, the same as the SEO side.
    try:
        ctx["orders"] = ADS.work_orders(snap)
    except Exception as e:
        log.warning("ads work orders failed: %s", e)
    # The Conversion board's sankey: paid + organic in one picture, from
    # whatever is real. No data -> no funnel, never a decorative one.
    try:
        cac = _D(inter.get("cac"))
        gsc = _D(_D(_get(store, "google_insights", {})).get("gsc"))
        organic_clicks = sum(int(q.get("clicks", 0) or 0) for q in (gsc.get("queries") or []))
        a = _D(snap.get("ads"))
        ctx["funnel"] = ADS.funnel_flows(
            impressions=a.get("impressions", 0), clicks=a.get("clicks", 0),
            leads=int(a.get("conversions", 0) or 0),
            bookings=cac.get("bookings", 0), customers=cac.get("customers", 0),
            organic_clicks=organic_clicks)
    except Exception as e:
        log.warning("funnel build failed: %s", e)

    ctx.setdefault("ads", {"connected": False})
    for k in ("terms", "kw", "assets", "conv_actions", "targeting", "audiences",
              "ad_status", "changes", "recs", "kw_ideas"):
        ctx.setdefault(k, {})
    for k in ("pacing", "is_summary"):
        ctx.setdefault(k, {})
    for k in ("is_rows", "bid_advice"):
        ctx.setdefault(k, [])
    return ctx



def build_system_ctx(store, *, status=None, health=None, meters=None,
                     month_spent=0.0, month_cap=200.0, jobs=None,
                     needles=None, last_eval=None, diag=None,
                     connect_html="", legacy_svgs="", build_tag="") -> dict:
    """Everything the 12 System & Wiring boards read. Pure reads — this never
    writes a setting and never touches a credential."""
    import content_engine_system as SYS
    # EVERY stored credential, checked, every render. Finding a bad paste used
    # to take an hour of staring at one failure; there are 85 of these fields.
    try:
        import content_engine_connectors as _CC
        cred_problems = _CC.credential_audit()
    except Exception:
        cred_problems = []
    # What the section agents found on their last sweep. One store key, read
    # here; no board computes its own health.
    try:
        import content_engine_agents as _AG
        agent_findings = _AG.load_findings(store)
    except Exception:
        agent_findings = {}
    # The receipt for anything an agent did on its own.
    try:
        import content_engine_fixes as _FXX
        fix_ledger = _FXX.ledger(store, 30)
        fix_ledger_summary = _FXX.ledger_summary(store)
    except Exception:
        fix_ledger, fix_ledger_summary = [], {}
    try:
        import content_engine_scheduler as SCH
        cadence = SCH.SEO_CADENCE
    except Exception:
        cadence = {}
    try:
        import content_engine_schemas as SC
        skills = sorted(SC.SCHEMAS)
    except Exception:
        skills = []
    jobs = jobs if isinstance(jobs, list) else []
    status = status if isinstance(status, dict) else {}
    diag = diag if isinstance(diag, list) else []
    wires = SYS.wire_rows(status, diag)
    return {
        "fix_ledger": fix_ledger,
        "fix_ledger_summary": fix_ledger_summary,
        "agent_findings": agent_findings,
        "cred_problems": cred_problems,
        "status": status, "diag": diag, "wires": wires,
        "summary": SYS.wire_summary(wires),
        "agents": SYS.agent_stats(jobs, skills),
        "models": SYS.model_usage(jobs),
        "versions": SYS.prompt_versions(jobs),
        "throughput": SYS.throughput(jobs),
        "failures": SYS.failure_patterns(jobs),
        "degraded": SYS.degraded(jobs),
        "freshness": SYS.freshness(_get(store, K_RUNS, {}) or {}, cadence),
        "quotas": SYS.quotas(meters or {}, status),
        "cost": SYS.cost_split(meters or {}, month_spent, month_cap),
        "dep_graph": SYS.dependency_graph(wires),
        "storage": SYS.storage_health(store),
        "needles": needles or {}, "last_eval": last_eval or {},
        "health": health or {}, "jobs": jobs,
        "connect_html": connect_html or "", "legacy_svgs": legacy_svgs or "",
        "build_tag": build_tag or "",
    }



def _campaign_list(store):
    try:
        import content_engine_sga as SGA
        return SGA.list_campaigns(store)
    except Exception:
        return []


MISSING_KEY_GROUPS = {
    "AI answer engines": ["OPENAI_API_KEY", "PERPLEXITY_API_KEY",
                          "GEMINI_API_KEY", "OPENAI_AEO_MODEL",
                          "PERPLEXITY_MODEL", "GEMINI_MODEL"],
    "Email identity": ["EMAIL_COMPANY", "EMAIL_FROM_NAME", "EMAIL_SENDER_TITLE",
                       "EMAIL_WEBSITE", "EMAIL_PHONE", "EMAIL_ADDRESS",
                       "EMAIL_LOGO_URL", "EMAIL_BRAND_COLOR",
                       "EMAIL_BOOKING_URL", "EMAIL_UNSUBSCRIBE_URL",
                       "EMAIL_MANAGE_URL", "EMAIL_HTML"],
    "Mail transport": ["SMTP_PORT", "SMTP_FROM", "SMTP_STARTTLS",
                       "IMAP_PORT", "IMAP_FOLDER"],
    "Reply agent": ["REPLY_OUR_OFFER", "REPLY_SENDER_NAME", "REPLY_CONTEXT",
                    "REPLY_AUTO_SEND"],
    "WordPress": ["WORDPRESS_USER", "WP_STATUS"],
    "Advanced": ["CI_JSON", "IMAGE_API_URL", "LINKEDIN_API_KEY",
                 "LINKEDIN_PROVIDER_URL", "GOOGLE_ADS_API_VERSION",
                 "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "GOOGLE_ADS_OFFLINE_ACTION"],
}


def build_cockpit_ctx(store, *, jobs=None, status=None, health=None,
                      content_plan=None, seo=None, bi=None, outreach=None,
                      sga=None, media=None, risk=None, system=None,
                      live=None, month_spent=0.0, day_spent=0.0) -> dict:
    """Everything the 15 AI Cockpit boards read.

    This is the only context that reads ALL the others — it turns each system's
    signal into a decision. It computes nothing new; it routes."""
    import content_engine_cockpit as CK
    import content_engine_orchestrator as ORCH
    jobs = jobs if isinstance(jobs, list) else []
    caps = ORCH.budget_caps(store) if hasattr(ORCH, "budget_caps") else {}
    playbook = {}
    try:
        import content_engine_learning as LRN
        _client = (_get(store, "brand_name", "") or
                   _D(_get(store, "brand_ci_json", {})).get("brand_name") or
                   "Anthropos")
        playbook = LRN.get_playbook(_client) or {}
    except Exception as e:
        log.warning("playbook unavailable: %s", e)
    deals = []
    try:
        import content_engine_bi as BI
        deals = BI.list_deals(store)
    except Exception:
        pass
    return {
        # THE SAME ACTIONABLE ROWS THE CALENDAR USES, filtered to what is
        # waiting. You were being asked to approve a piece you could not
        # see - the Approve button and the words it applies to lived on
        # two different screens.
        "approval_rows": [r for r in _calendar_rows(jobs)
                          if r.get("state") == "awaiting"],
        "decisions": CK.decisions(seo=seo, content=None, outreach=outreach,
                                  bi=bi, sga=sga, media=media, risk=risk,
                                  system=system, jobs=jobs),
        "router": CK.signal_router(seo=seo, content=None, outreach=outreach,
                                   bi=bi, sga=sga, media=media, risk=risk,
                                   system=system),
        "approvals": CK.approvals(jobs, content_plan),
        "proposals": CK.proposals(store),
        "turnaround": CK.turnaround(jobs),
        "budget": CK.budget_view(caps, spent_month=month_spent,
                                 spent_day=day_spent,
                                 log=ORCH.budget_log(store)
                                 if hasattr(ORCH, "budget_log") else []),
        "autonomy": CK.autonomy(caps),
        "capability": CK.capability(status, MISSING_KEY_GROUPS),
        "engine": CK.engine_state(health, jobs, caps, month_spent),
        "playbook": CK.playbook_view(playbook, deals),
        "experiments": CK.experiments(store),
        "log": CK.decision_log(store),
        "live": live if isinstance(live, dict) else {},
    }


def _calendar_rows(jobs, content_plan=None):
    """ONE dated list: everything planned AND everything written.

    The calendar showed plan items only, as bars. A piece that had already
    been WRITTEN and was sitting in the approval queue never appeared there at
    all - so the screen called "the week" was missing the only rows you could
    actually act on.

    Each row carries its own preview, rendered by destination. Never raises;
    a row that cannot render says why instead of vanishing."""
    import content_engine_factory as _FF
    out = []
    for j in (jobs or []):
        j = _D(j)
        if j.get("type") != "content_piece":
            continue
        st = str(j.get("status") or "")
        if st in ("published", "optimized", "learned", "discarded"):
            continue
        state = ("awaiting" if st == "AWAITING_APPROVAL" else
                 "failed" if st in ("failed", "revision_needed") else "planned")
        try:
            pv = _FF.preview_for_job(j)
        except Exception as e:
            pv = {"html": "", "destination": "", "written": False,
                  "why": f"preview unavailable: {type(e).__name__}"}
        pc = _D(_D(j.get("payload")).get("content_producer"))
        out.append({
            "job_id": str(j.get("job_id") or ""),
            "title": str(pc.get("title") or j.get("job_id") or ""),
            "destination": pv.get("destination", ""),
            "when": str(j.get("created_at") or "")[:10],
            "state": state,
            "written": pv.get("written", False),
            # THE REAL REASON WINS. This read `pv.why or halt_reason`, so a
            # FAILED piece reported "planned, not written yet" - the generic
            # no-body message - and buried the actual failure underneath it.
            # A row that explains itself wrongly is worse than one that says
            # nothing: it stops you looking.
            "why": (str(j.get("halt_reason") or "") if state == "failed"
                    else pv.get("why", "") or str(j.get("halt_reason") or "")),
            "preview_html": pv.get("html", ""),
            # THE WHOLE JOB rides along so the decision detail can read the
            # strategist's rationale, the QA issues and the real spend. All of
            # it was already on the job; none of it reached the screen where
            # the approve button is. In-memory only - nothing is serialised.
            "job": j,
        })
    # plan items that have no job yet - they are coming, and they say so
    _items = _D(content_plan).get("items")
    for it in (_items if isinstance(_items, (list, tuple)) else []):
        it = _D(it)
        _ch = it.get("channels")
        _ch = _ch if isinstance(_ch, (list, tuple)) else []
        out.append({"job_id": "", "title": str(it.get("title") or ""),
                    "destination": ", ".join(str(c) for c in _ch) or "Website",
                    "when": str(it.get("date") or it.get("day") or "planned"),
                    "state": "planned", "written": False,
                    "why": "Planned, not written yet - approve the plan and "
                           "the writer starts.",
                    "preview_html": ""})
    out.sort(key=lambda r: (r.get("when") or "9999"))
    return out


def build_factory_ctx(store, *, jobs=None, status=None, ci=None, piece=None,
                      content_plan=None, seo=None, bi=None, outreach=None,
                      sga=None, media=None, risk=None, image_key=None) -> dict:
    """Everything the 16 Content Factory boards read, including the six
    platform previews and the strategy brief that ends the planner's blindness."""
    import content_engine_factory as F
    jobs = jobs if isinstance(jobs, list) else []
    brief = F.strategy_brief(store, seo=seo, bi=bi, outreach=outreach, sga=sga,
                             media=media, risk=risk, status=status)
    el = brief.get("eligibility") or F.channel_eligibility(status)
    # the piece to preview: the newest one awaiting approval, else the newest
    pc = piece
    if pc is None:
        cands = [j for j in jobs if _D(j).get("type") == "content_piece"]
        awaiting = [j for j in cands
                    if _D(j).get("status") == "AWAITING_APPROVAL"] or cands
        awaiting.sort(key=lambda j: _D(j).get("created_at") or "", reverse=True)
        _job = _D(awaiting[0]) if awaiting else {}
        pc = _D(_D(_job.get("payload")).get("content_producer"))
    chans = []
    for j in jobs:
        cfg = _D(_D(j).get("payload")).get("config") or {}
        chans += [str(c).lower() for c in (_D(cfg).get("deploy_channels") or [])]
    chans = sorted(set(chans)) or ["website"]
    kw = _D(pc).get("target_keyword") or ""
    # THE IMAGE STATE OF THE PIECE YOU ARE LOOKING AT.
    # _ensure_hero_image already recorded WHY an image was missing
    # (image_error / image_skipped) and nothing ever read it back out - so the
    # preview honestly showed a picture-less piece and said nothing at all.
    # A diagnostic nobody renders is not a diagnostic. It says now.
    _pl = _D(_job).get("payload") or {} if "_job" in dir() else {}
    _row = {}
    try:
        _cal = (_D(_pl.get("content_strategist")).get("calendar") or [])
        _ix = int(_D(_pl.get("config")).get("produce_index", 0) or 0)
        _row = _D(_cal[_ix]) if 0 <= _ix < len(_cal) else _D(_cal[0] if _cal else {})
    except Exception:
        _row = {}
    _ptype = _row.get("type") or _D(_pl.get("config")).get("type") or "blog"
    _iurl = _D(pc).get("image_url") or _pl.get("image_url") or ""
    image_state = {
        "type": _ptype, "url": _iurl, "ok": bool(_iurl),
        "skipped": bool(_pl.get("image_skipped")),
        "reason": (_pl.get("image_error") or _pl.get("image_skipped") or
                   ("" if _iurl else "no image, and no reason recorded - this "
                    "piece was produced before the engine explained itself. "
                    "Re-run it and the reason will appear here.")),
    }
    return {
        "brief": brief, "eligibility": el, "piece": pc,
        "previews": F.previews(pc, chans, keyword=kw,
                               image_reason=image_state["reason"]),
        "images": F.image_status(status, image_key=image_key),
        "image_need": F.image_needed(_ptype, chans),
        "image_state": image_state,
        "piece_job_id": (_job.get("job_id") if "_job" in dir() else ""),
        "calendar_rows": _calendar_rows(jobs, content_plan),
        "ci": F.ci_compliance(pc, ci),
        "pipeline": F.pipeline(jobs),
        "routing": F.routing(jobs, el),
        "repurposing": F.repurposing(pc, chans),
        "throughput": F.throughput(jobs),
        "plan": _D(content_plan),
        "post_publish": F.post_publish(jobs),
        "campaigns": F.campaigns_assigned(
            jobs, content_plan, _campaign_list(store)),
    }


def build_sga_ctx(store, *, jobs=None, status=None, insights=None, deals=None,
                  month_spent=0.0, month_cap=200.0, emails_sent=0,
                  target_per_channel=1) -> dict:
    """Everything the 14 SGA boards read.

    Scope is SOCIAL — paid and unpaid — plus the Google data hub. Google Ads
    keeps its own Media Buying section and nothing here reads it."""
    import content_engine_sga as SGA
    jobs = jobs if isinstance(jobs, list) else []
    insights = insights if isinstance(insights, dict) else (
        _get(store, "google_insights", {}) or {})
    camps = SGA.list_campaigns(store)
    p_ = SGA.posts(jobs)
    bl = SGA.blog_push(jobs)
    paid = SGA.paid_social(store, camps)
    chans = sorted({c for x in camps
                    for c in (_D(x).get("channels") or [])
                    if isinstance(c, str)}) or None
    return {
        "campaigns": camps,
        "calendar": SGA.calendar(camps),
        "posts": p_,
        "cadence": SGA.cadence(p_, target_per_channel, chans),
        "creatives": SGA.creatives(jobs),
        "blog": bl,
        "channels": SGA.channel_health(status, p_),
        "audience": SGA.audience(store, status),
        "engagement": SGA.engagement(store),
        "paid": paid,
        "traffic": SGA.social_traffic(insights, p_, camps),
        "revenue": SGA.social_revenue(deals, p_, paid),
        "budget": SGA.budget(camps, paid, month_spent, month_cap, bl),
        "hub": SGA.google_hub(store, status, jobs, emails_sent=emails_sent),
        "cost_series": SGA.cost_series(jobs),
    }


def build_outreach_ctx(store, *, jobs=None, reply_drafts=None, bookings=None,
                       deals=None, live=None) -> dict:
    """Everything the 13 Leads & Outreach boards read.

    Reads only. Send logic is untouched — the interactive blocks are passed in
    through `live` already rendered, so the outbox buttons keep calling the same
    endpoints they always did."""
    import content_engine_outreach as O
    jobs = jobs if isinstance(jobs, list) else []
    sc = O.sourcing(jobs)
    sd = O.sends(jobs)
    rp = O.replies(reply_drafts, sd, jobs)
    bk = O.bookings(bookings, rp)
    supp = _get(store, "email_suppression", []) or []
    meta = _get(store, "email_suppression_meta", {}) or {}
    sent_today = 0
    try:
        import content_engine_connectors as CN
        sent_today = int(_get(store, CN._sent_today_key(), 0) or 0)
    except Exception:
        pass
    outreach_cost = sum(float(_D(j).get("cost_so_far_usd", 0) or 0)
                        for j in jobs if _D(j).get("type") == "outreach_campaign")
    return {
        "sourcing": sc, "quality": O.quality(jobs), "icp": O.icp(jobs),
        "territories": O.territories(jobs), "sends": sd,
        "sequence": O.sequence(jobs), "routing": O.routing(sd),
        "deliverability": O.deliverability(store, sd, supp, meta,
                                           sent_today=sent_today),
        "replies": rp, "bookings": bk,
        "attribution": O.attribution(deals, sc, sd),
        "costs": O.unit_costs(sc, sd, rp, bk, deals, outreach_cost=outreach_cost),
        "tracking": O.tracking_stats(store, sends=sd.get("total", 0)),
        "sourcing_mom": O.sourcing_mom(jobs),
        "suppression_heat": O.suppression_heat(meta),
        "campaign_costs": O.campaign_costs(jobs),
        "sends_cohort": O.sends_cohort(jobs),
        "lead_rows": O.lead_rows(jobs),
        "leads_per_day": O.leads_per_day(jobs),
        "field_coverage": O.lead_field_coverage(jobs),
        "live": live if isinstance(live, dict) else {},
    }


def build_bi_ctx(store, *, insights=None, jobs=None, agents=None, meters=None,
                 month_spent=0.0, month_cap=200.0, reply_drafts=None,
                 bookings=None, status=None) -> dict:
    """Everything the 14 Business Intelligence boards read.

    Six sections used to share one context dict and render the same four numbers
    six ways. This builds each loop once, from the source that actually owns it:
    GA4/GSC for demand, outreach jobs for pipeline, Cal.com for consultations,
    recorded deals for revenue, and the meters for cost."""
    import content_engine_bi as BI
    jobs = jobs if isinstance(jobs, list) else []
    insights = insights if isinstance(insights, dict) else (
        _get(store, "google_insights", {}) or {})
    deals = BI.list_deals(store)
    ec = BI.econ(store)
    tg = BI.targets(store)
    lg = BI.leadgen(jobs)
    ou = BI.outreach(jobs, reply_drafts)
    co = BI.consultations(bookings)
    rev = BI.revenue(deals)
    sp = BI.spend_view(meters, month_spent, month_cap, jobs)
    ch = BI.channel_mix(insights)
    mk = BI.markets(insights)
    hist = BI.record_bi_snapshot(store, ch, mk)
    dm = BI.demand(insights)
    cn = BI.content_attribution(insights, jobs)
    fn = BI.funnel(jobs, reply_drafts, bookings, deals)
    return {
        "exec": BI.executive_brief(
            store, status=status, spend=sp, funnel_=fn, demand_=dm, markets_=mk,
            content_=cn, econ_=ec, revenue_=rev, leadgen_=lg,
            unit_=None),
        "channels_mom": BI.mom(hist, "channels"),
        "markets_mom": BI.mom(hist, "markets"),
        "leads_mom": BI.leads_mom(jobs),
        "client_bump": BI.client_rank_movement(deals),
        "demand": dm,
        "markets": mk,
        "channels": ch,
        "content": cn,
        "leadgen": lg, "outreach": ou, "consultations": co,
        "funnel": fn,
        "revenue": rev, "customers": BI.customers(deals),
        "econ": ec, "targets": tg,
        "unit": BI.unit_economics(deals, sp, ec, bookings, lg.get("found", 0)),
        "spend": sp,
        "cost": BI.cost_per_outcome(jobs, agents, deals, bookings,
                                    lg.get("found", 0)),
        "attainment": BI.attainment(tg, rev, lg, co),
        "deals": deals,
    }


def build_risk_ctx(store, *, status=None, health=None, meters=None,
                   month_spent=0.0, month_cap=200.0, jobs=None, agents=None,
                   needles=None, last_eval=None, content_cost=0.0,
                   storage=None) -> dict:
    """Everything the 12 Risk & Infrastructure boards read. Recomputes the
    register, keeps the mitigation decisions, and records a history snapshot so
    the trend charts have something real to draw."""
    import content_engine_risk as RK
    status = status if isinstance(status, dict) else {}
    jobs = jobs if isinstance(jobs, list) else []
    agents = agents if isinstance(agents, list) else []
    live = sum(1 for v in status.values() if v)
    waiting = sum(1 for j in jobs
                  if _D(j).get("status") == "AWAITING_APPROVAL" and not _D(j).get("approved"))
    leads = sum(len(_D(_D(j).get("payload")).get("leads") or []) for j in jobs)
    backup = _get(store, "backup_config", None)
    fresh = RK.register(status=status, month_spent=month_spent, month_cap=month_cap,
                        jobs=jobs, wires_down=max(0, len(status) - live),
                        waiting=waiting, healthy=bool(_D(health).get("healthy")),
                        leads=leads, backup=backup,
                        aeo=_get(store, "aeo_visibility", {}) or {},
                        geo=_get(store, "geo_market_audit", {}) or {})
    risks = RK.merge_register(RK.load_register(store), fresh)
    RK.save_register(store, risks)
    hist = RK.record_snapshot(store, risks)
    nodes, edges = RK.channel_blast(status)
    infra_hist = RK.record_infra_snapshot(
        store, settings_bytes=(storage or {}).get("total_bytes", 0), jobs=len(jobs))
    rows, grid = RK.cohort_grid(agents)
    try:
        import content_engine_scheduler as SCH
        targets = {"blogs": 2, "outreach": 1, "social_per_channel": 1}
    except Exception:
        targets = {}
    return {
        "risks": risks, "history": hist,
        "by_category": RK.by_category(risks),
        "bump": RK.rank_movement(hist, [r["key"] for r in risks[:5]]),
        "concentration": RK.concentration(jobs),
        "compliance": RK.compliance(),
        "credentials": RK.credential_age(status),
        "vendor_share": RK.vendor_share(status),
        "blast_nodes": nodes, "blast_edges": edges,
        "workforce": RK.workforce(agents, jobs, content_cost=content_cost),
        "capacity": RK.capacity(jobs, targets),
        "cohort_rows": rows, "cohort_grid": grid,
        "infra": RK.infra(storage or {}, health or {}, _get(store, K_RUNS, {}) or {}),
        "continuity": RK.continuity(backup),
        # the four signature charts the plan specified
        "revenue_path": RK.revenue_path(jobs),
        "run_series": RK.run_series(_get(store, K_RUNS, {}) or {}),
        "infra_history": infra_hist,
        "storage_forecast": RK.storage_forecast(infra_hist),
        "backup_coverage": RK.backup_coverage(backup),
        "status": status, "agents": agents, "jobs": jobs,
        "health": health or {}, "needles": needles or {}, "last_eval": last_eval or {},
        "cost": {"month_spent": month_spent, "month_cap": month_cap,
                 "pct_of_cap": round(100 * float(month_spent or 0)
                                     / float(month_cap or 1), 1)},
        "aeo": _get(store, "aeo_visibility", {}) or {},
        "geo": _get(store, "geo_market_audit", {}) or {},
    }


# ======================================================================
#  CONTEXT FOR THE BOARDS
# ======================================================================
def build_ctx(store, *, status=None, insights=None, meters=None,
              competitor_intel=None) -> dict:
    import content_engine_workorders as WO
    import content_engine_offpage as OFF

    audit = _get(store, K_AUDIT, {}) or {}
    orders = WO.load(store)
    prospects = OFF.load_prospects(store)
    return {
        "crawl": _get(store, K_CRAWL, {}) or {},
        "graph": _get(store, K_GRAPH, {}) or {},
        "money": _get(store, K_MONEY, {}) or {},
        "audit": audit,
        "scores": audit.get("scores") or {},
        "orders": orders,
        "order_stats": WO.stats(orders),
        "inspect": _get(store, K_INSPECT, {}) or {},
        "speed": _get(store, K_SPEED, []) or [],
        "ranks": [r for r in (_get(store, K_RANKS, []) or [])
                  if r.get("at", "")[:10] == _now()[:10]] or (_get(store, K_RANKS, []) or [])[-100:],
        "aeo": _get(store, "aeo_visibility", {}) or {},
        "aeo_history": _get(store, "aeo_history", []) or [],
        "crawler_access": _get(store, K_ACCESS, {}) or {},
        "entity": _get(store, K_ENTITY, {}) or {},
        "geo": _get(store, "geo_market_audit", {}) or {},
        "local_grid": _get(store, "geo_local_grid", []) or [],
        "nap": _get(store, K_NAP, {}) or {},
        "quotable": _get(store, K_QUOT, {}) or {},
        "llms_txt": _get(store, K_LLMS, "") or "",
        "offpage": _get(store, "backlink_profile", {}) or
                   {"connected": False,
                    "reason": "DataForSEO not connected — set DATAFORSEO_LOGIN + "
                              "DATAFORSEO_PASSWORD. Google exposes no backlink API."},
        "prospects": prospects,
        "prospect_stats": OFF.pipeline_stats(prospects),
        "link_gap": _get(store, "seo_link_gap", []) or [],
        "local": _get(store, K_LOCAL, {}) or {},
        "indexnow": _get(store, K_INDEXNOW, {}) or {},
        "insights": insights or (_get(store, "google_insights", {}) or {}),
        "status": status or {},
        "engine_runs": _get(store, K_RUNS, {}) or {},
        "meters": meters or {},
        "competitor_intel": competitor_intel or {},
    }


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    class S:
        def __init__(self): self.d = {}
        def get_setting(self, k, default=None): return self.d.get(k, default)
        def set_setting(self, k, v): self.d[k] = v

    st = S()
    # build_ctx must be safe on a completely empty store — this is what the
    # dashboard hits before anything has ever run.
    ctx = build_ctx(st)
    assert ctx["crawl"] == {} and ctx["orders"] == [], ctx
    assert ctx["offpage"]["connected"] is False and "DataForSEO" in ctx["offpage"]["reason"]
    assert ctx["order_stats"]["total"] == 0

    import content_engine_seo_boards as B
    pages = B.seo_pages(ctx)
    html = "".join(pages.values())
    assert "Not run yet" in html, "empty state must invite the first run"
    assert "None" not in html, "empty context must never render None"

    _stamp(st, "crawl")
    assert st.d["seo_engine_runs"]["crawl"].startswith("20")

    crawl = {"count": 2, "urls": [
        {"url": "https://x.com/a", "status": 200, "internal_links": ["b"] * 99,
         "anchors": [("b", "t")] * 50, "h2": ["q?"] * 30, "h3": ["x"] * 20},
        {"url": "https://x.com/b", "status": 200, "internal_links": [],
         "anchors": [], "h2": [], "h3": []}]}
    t = _trim_crawl(crawl)
    assert len(t["urls"][0]["internal_links"]) == 40, "links must be capped for storage"
    assert "anchors" not in t["urls"][0] and t["urls"][0]["h3"] == []
    assert len(t["urls"][0]["h2"]) == 12

    st.d["seo_audit"] = {"striking": [{"query": "ai automation law firm"}]}
    st.d["google_insights"] = {"gsc": {"queries": [{"key": "n8n consultant", "impressions": 90}]}}
    kws = tracked_keywords(st)
    assert kws[0] == "ai automation law firm" and "n8n consultant" in kws, kws
    st.d["seo_keywords"] = ["manual one"]
    assert tracked_keywords(st) == ["manual one"], "a saved list must win"

    # ---- run_inspect must be RESUMABLE (it kept getting killed mid-run) ----
    class _FakeG:
        def __init__(self, die_after=None):
            self.calls, self.die_after = [], die_after
        def available(self): return True
        def url_inspect(self, u):
            if self.die_after is not None and len(self.calls) >= self.die_after:
                raise KeyboardInterrupt("container restarted")
            self.calls.append(u)
            return {"url": u, "verdict": "PASS" if u.endswith(("1", "2", "3")) else "NEUTRAL",
                    "coverageState": "Submitted and indexed"}

    st2 = S()
    st2.d[K_CRAWL] = {"urls": [{"url": f"https://x.com/{i}", "status": 200} for i in range(20)]}
    import content_engine_connectors as _C
    _real_google = _C.Google
    fake = _FakeG(die_after=7)
    _C.Google = lambda: fake
    try:
        try:
            run_inspect(st2, save_every=3)      # dies after 7 URLs
        except KeyboardInterrupt:
            pass
        saved = st2.d.get(K_INSPECT, {})
        assert len(saved) == 6, f"checkpoint should have kept 6, kept {len(saved)}"

        fake2 = _FakeG()                         # resume: must SKIP the saved ones
        _C.Google = lambda: fake2
        out = run_inspect(st2)
        assert len(fake2.calls) == 14, f"resumed run re-checked too much: {len(fake2.calls)}"
        assert not set(fake2.calls) & set(saved), "resume must not re-inspect saved URLs"
        assert out["total_known"] == 20 and out["remaining"] == 0, out
        assert out["indexed"] + out["not_indexed"] == 20, out

        out2 = run_inspect(st2)                  # nothing left to do
        assert out2["inspected"] == 0 and "already been inspected" in out2["reason"], out2
    finally:
        _C.Google = _real_google

    # A broken engine must never take down the run.
    # NB: patch THIS module's globals, not `import content_engine_seo_ops` — run
    # as a script this file is __main__, and importing it by name would load a
    # second copy whose patch run_all never sees (it would then really crawl).
    _g = globals()
    _orig = _g["run_crawl"]
    _g["run_crawl"] = lambda s, **k: (_ for _ in ()).throw(RuntimeError("network down"))
    try:
        res = run_all(st)
    finally:
        _g["run_crawl"] = _orig
    assert "error" in res["crawl"] and "network down" in res["crawl"]["error"], res["crawl"]
    assert "inspect" in res, "later engines must still run after one fails"
    print("seo_ops self-check OK — empty-store safety, crawl trimming, keyword "
          "derivation, per-engine failure isolation")
