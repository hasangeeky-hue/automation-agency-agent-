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

MAX_CRAWL_URLS = 300
MAX_INSPECT = 180          # free quota is 2000/day; stay well under
MAX_SPEED = 10
MAX_RANK_KEYWORDS = 80


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


def run_inspect(store, *, limit: int = MAX_INSPECT) -> dict:
    """E2. Google's own index verdict per URL. Free, 2,000/day."""
    import content_engine_connectors as C
    g = C.Google()
    if not g.available():
        return {"connected": False, "reason": "Google service account not connected"}
    crawl = _get(store, K_CRAWL, {}) or {}
    urls = [r["url"] for r in (crawl.get("urls") or [])
            if r.get("status") == 200][:limit]
    if not urls:
        return {"connected": True, "inspected": 0, "reason": "run a crawl first"}
    prev = _get(store, K_INSPECT, {}) or {}
    fresh = g.inspect_batch(urls, limit=limit)
    merged = {**prev, **fresh}
    _set(store, K_INSPECT, merged)
    _stamp(store, "inspect")
    indexed = sum(1 for r in merged.values() if r.get("verdict") == "PASS")
    return {"connected": True, "inspected": len(fresh), "total_known": len(merged),
            "indexed": indexed}


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
    results = ps.check_many(picks, limit=limit)
    _set(store, K_SPEED, results)
    _stamp(store, "speed")
    perf = [r.get("performance", 0) for r in results]
    return {"connected": True, "checked": len(results),
            "avg_performance": round(sum(perf) / max(len(perf), 1))}


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
    """E14. Do AI answers name you? Plus the on-site quotable audit + llms.txt."""
    import content_engine_aeo as AEO
    crawl = _get(store, K_CRAWL, {}) or {}
    rivals = []
    try:
        ci = _get(store, "competitor_intel", {}) or {}
        rivals = [c.get("domain") for c in (ci.get("competitors") or []) if c.get("domain")]
    except Exception:
        pass
    domain = _site(store).replace("https://", "").replace("http://", "").strip("/")
    out = AEO.run_probes(store, brand="Anthropos", domain=domain,
                         rivals=rivals[:6], limit=limit)
    _set(store, K_QUOT, AEO.quotable_audit(crawl))
    _set(store, K_LLMS, AEO.llms_txt(crawl, site_name="Anthropos Automation",
                                     description="AI and n8n business automation for small "
                                                 "and mid-sized companies."))
    _stamp(store, "aeo")
    return {"score": out.get("score", 0), "mention_rate": out.get("mention_rate", 0),
            "prompts": out.get("prompts_tested", 0), "gaps": len(out.get("gaps") or [])}


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
              dry_run: bool = False) -> dict:
    """E7/E8/E9. Apply what may be applied; draft what must be approved."""
    import content_engine_seo_fixer as FIX
    crawl = _get(store, K_CRAWL, {}) or {}
    rep = FIX.run_batch(store, crawl=crawl, limit=limit, auto_only=auto_only,
                        dry_run=dry_run)
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
                  ("offpage", lambda: run_offpage(store)),
                  ("prospecting", lambda: run_prospecting(store))]
    for name, fn in steps:
        try:
            out[name] = fn()
        except Exception as e:                 # one engine failing never stops the rest
            log.warning("seo engine %s failed: %s", name, e)
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return out


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
