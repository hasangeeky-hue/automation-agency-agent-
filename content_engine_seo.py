"""
content_engine_seo.py
============================================================================
E5 + SCORING — the SEO brain. Pure math, zero API cost, zero network.

Everything here is a function of data already collected elsewhere:
    crawl    <- content_engine_crawler.crawl_site()
    gsc      <- connectors.Google.gsc_full() / gsc_query_page() / range pulls
    inspect  <- connectors.Google.url_inspect() results
    speed    <- connectors.PageSpeed results

It produces FINDINGS (typed, ranked, with evidence) — the raw material the
work-order engine turns into actual fixes, and the numbers every SEO card
renders. Nothing here invents a claim: every finding carries the metric it
came from.

Run offline self-check:  python content_engine_seo.py
============================================================================
"""

from __future__ import annotations

import re
from typing import Optional

# ---- thresholds an SEO would actually use -------------------------------
TITLE_MIN, TITLE_MAX = 30, 60
META_MIN, META_MAX = 70, 160
THIN_WORDS = 300
STRIKING_LO, STRIKING_HI = 4.0, 20.0
DECAY_DROP_PCT = 20.0
SLOW_MS = 2500

# severity -> how much it moves the needle (used for ranking work orders)
SEVERITY = {"critical": 100, "high": 60, "medium": 30, "low": 10}


def _f(row, *names, default=0):
    for n in names:
        if n in row:
            return row[n]
    return default


# ======================================================================
#  KEYWORD / RANK MATH  (from Search Console)
# ======================================================================
def striking_distance(queries: list, lo: float = STRIKING_LO,
                      hi: float = STRIKING_HI, min_impr: int = 1) -> list:
    """Queries ranking #4–#20 with real impressions — one push from page one.
    This is the highest-ROI list in all of SEO and nothing computed it before."""
    out = []
    for q in queries or []:
        pos = float(_f(q, "position", default=99))
        impr = int(_f(q, "impressions", default=0))
        if lo <= pos <= hi and impr >= min_impr:
            # potential = impressions x the CTR you'd gain reaching top 3
            gain = impr * max(0.0, _ctr_at(3) - _ctr_at(pos))
            out.append({"query": _f(q, "key", "query", default=""),
                        "position": round(pos, 1), "impressions": impr,
                        "clicks": int(_f(q, "clicks", default=0)),
                        "potential_clicks": round(gain, 1),
                        "page_now": int((pos - 1) // 10) + 1})
    return sorted(out, key=lambda r: -r["potential_clicks"])


def _ctr_at(pos: float) -> float:
    """Industry CTR curve by position. Used ONLY to rank opportunities against
    each other — never displayed as a prediction of your traffic."""
    curve = {1: .28, 2: .15, 3: .11, 4: .08, 5: .06, 6: .05, 7: .04,
             8: .035, 9: .03, 10: .025}
    p = int(round(pos))
    if p <= 10:
        return curve.get(p, .025)
    if p <= 20:
        return .012
    return .004


def cannibalization(query_page_rows: list, min_impr: int = 1) -> list:
    """Two or more of YOUR pages competing for the same query. Splits authority
    and confuses Google about which page to rank. Needs query+page rows."""
    by_q = {}
    for r in query_page_rows or []:
        keys = r.get("keys") or [r.get("query", ""), r.get("page", "")]
        if len(keys) < 2:
            continue
        q, page = keys[0], keys[1]
        impr = int(_f(r, "impressions", default=0))
        if impr < min_impr:
            continue
        by_q.setdefault(q, []).append(
            {"page": page, "impressions": impr,
             "clicks": int(_f(r, "clicks", default=0)),
             "position": round(float(_f(r, "position", default=99)), 1)})
    out = []
    for q, pages in by_q.items():
        if len(pages) < 2:
            continue
        pages.sort(key=lambda p: p["position"])
        out.append({"query": q, "pages": pages, "page_count": len(pages),
                    "impressions": sum(p["impressions"] for p in pages),
                    "best": pages[0]["page"], "best_position": pages[0]["position"],
                    "competing": [p["page"] for p in pages[1:]]})
    return sorted(out, key=lambda r: -r["impressions"])


def decay(current_pages: list, previous_pages: list,
          drop_pct: float = DECAY_DROP_PCT) -> list:
    """Pages whose clicks fell >drop_pct vs the previous equal-length window.
    A page falling off a cliff used to be completely silent."""
    prev = {_f(p, "key", "page", default=""): int(_f(p, "clicks", default=0))
            for p in previous_pages or []}
    out = []
    for p in current_pages or []:
        url = _f(p, "key", "page", default="")
        now = int(_f(p, "clicks", default=0))
        was = prev.get(url, 0)
        if was <= 0:
            continue
        change = 100.0 * (now - was) / was
        if change <= -drop_pct:
            out.append({"url": url, "clicks_now": now, "clicks_before": was,
                        "change_pct": round(change, 1),
                        "lost_clicks": was - now,
                        "impressions": int(_f(p, "impressions", default=0))})
    return sorted(out, key=lambda r: -r["lost_clicks"])


def rising(current_pages: list, previous_pages: list, gain_pct: float = 20.0) -> list:
    prev = {_f(p, "key", "page", default=""): int(_f(p, "clicks", default=0))
            for p in previous_pages or []}
    out = []
    for p in current_pages or []:
        url = _f(p, "key", "page", default="")
        now = int(_f(p, "clicks", default=0))
        was = prev.get(url, 0)
        if now > was and (was == 0 or 100.0 * (now - was) / was >= gain_pct):
            out.append({"url": url, "clicks_now": now, "clicks_before": was,
                        "gained": now - was})
    return sorted(out, key=lambda r: -r["gained"])


def zero_click(queries: list, min_impr: int = 10) -> list:
    """Ranking, being seen, earning nothing. Usually a title/meta problem —
    or a position too low to click. Both are actionable, differently."""
    return sorted(
        [{"query": _f(q, "key", "query", default=""),
          "impressions": int(_f(q, "impressions", default=0)),
          "position": round(float(_f(q, "position", default=99)), 1),
          "reason": ("title/meta not compelling" if float(_f(q, "position", default=99)) <= 10
                     else "position too low to earn clicks")}
         for q in queries or []
         if int(_f(q, "impressions", default=0)) >= min_impr
         and int(_f(q, "clicks", default=0)) == 0],
        key=lambda r: -r["impressions"])


def ctr_underperformers(queries: list, min_impr: int = 20) -> list:
    """Good rank, bad CTR -> rewrite the title/meta. The cheapest win there is:
    no new content, no new links, just better copy in the SERP."""
    out = []
    for q in queries or []:
        impr = int(_f(q, "impressions", default=0))
        pos = float(_f(q, "position", default=99))
        if impr < min_impr or pos > 10:
            continue
        clicks = int(_f(q, "clicks", default=0))
        actual = clicks / impr if impr else 0
        expected = _ctr_at(pos)
        if actual < expected * 0.6:
            out.append({"query": _f(q, "key", "query", default=""),
                        "position": round(pos, 1), "impressions": impr,
                        "ctr_actual": round(actual * 100, 2),
                        "ctr_expected": round(expected * 100, 2),
                        "missed_clicks": round((expected - actual) * impr, 1)})
    return sorted(out, key=lambda r: -r["missed_clicks"])


_COMMERCIAL = ("price", "pricing", "cost", "quote", "hire", "agency", "service",
               "services", "company", "consultant", "near me", "best", "top",
               "vs", "alternative", "review", "compare", "software", "tool")
_TRANSACTIONAL = ("buy", "book", "demo", "trial", "sign up", "get started",
                  "contact", "consultation")


def intent_of(query: str) -> str:
    q = (query or "").lower()
    if any(w in q for w in _TRANSACTIONAL):
        return "transactional"
    if any(w in q for w in _COMMERCIAL):
        return "commercial"
    if q.startswith(("how", "what", "why", "when", "can", "does", "is ")):
        return "informational"
    return "informational"


def intent_split(queries: list) -> dict:
    out = {"informational": {"queries": 0, "clicks": 0, "impressions": 0},
           "commercial": {"queries": 0, "clicks": 0, "impressions": 0},
           "transactional": {"queries": 0, "clicks": 0, "impressions": 0}}
    for q in queries or []:
        b = out[intent_of(_f(q, "key", "query", default=""))]
        b["queries"] += 1
        b["clicks"] += int(_f(q, "clicks", default=0))
        b["impressions"] += int(_f(q, "impressions", default=0))
    return out


def branded_split(queries: list, brand_terms=("anthropos",)) -> dict:
    b = {"branded": 0, "non_branded": 0, "branded_clicks": 0, "non_branded_clicks": 0}
    for q in queries or []:
        key = str(_f(q, "key", "query", default="")).lower()
        clicks = int(_f(q, "clicks", default=0))
        if any(t in key for t in brand_terms):
            b["branded"] += 1; b["branded_clicks"] += clicks
        else:
            b["non_branded"] += 1; b["non_branded_clicks"] += clicks
    return b


def position_spread(queries: list) -> dict:
    buckets = {"1-3": 0, "4-10": 0, "11-20": 0, "21-50": 0, "51+": 0}
    for q in queries or []:
        p = float(_f(q, "position", default=99))
        key = ("1-3" if p <= 3 else "4-10" if p <= 10 else "11-20" if p <= 20
               else "21-50" if p <= 50 else "51+")
        buckets[key] += 1
    return buckets


# ======================================================================
#  ON-PAGE + TECHNICAL AUDIT  (from the crawl)
# ======================================================================
def _issue(code, severity, url, detail, fix, auto=False):
    return {"code": code, "severity": severity, "url": url, "detail": detail,
            "fix": fix, "auto": auto, "weight": SEVERITY.get(severity, 10)}


def on_page_audit(crawl: dict) -> list:
    """Per-URL on-page findings. `auto=True` means the fixer can apply it
    without asking (schema, alt text, internal links)."""
    issues = []
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    titles, metas = {}, {}
    for r in pages:
        url = r["url"]
        t, tl = r.get("title", ""), r.get("title_len", 0)
        if not t:
            issues.append(_issue("title_missing", "critical", url, "No <title>", "Write a title"))
        elif tl > TITLE_MAX:
            issues.append(_issue("title_long", "medium", url,
                                 f"Title {tl} chars (>{TITLE_MAX}) — truncated in Google",
                                 "Rewrite title to 50-60 chars"))
        elif tl < TITLE_MIN:
            issues.append(_issue("title_short", "medium", url,
                                 f"Title {tl} chars — wasting SERP space",
                                 "Expand title toward 55 chars"))
        if t:
            titles.setdefault(t.strip().lower(), []).append(url)

        m, ml = r.get("meta_desc", ""), r.get("meta_len", 0)
        if not m:
            issues.append(_issue("meta_missing", "high", url, "No meta description",
                                 "Write a 150-char meta description"))
        elif ml > META_MAX:
            issues.append(_issue("meta_long", "low", url, f"Meta {ml} chars (>{META_MAX})",
                                 "Trim meta to ~155 chars"))
        elif ml < META_MIN:
            issues.append(_issue("meta_short", "low", url, f"Meta {ml} chars — thin",
                                 "Expand meta toward 150 chars"))
        if m:
            metas.setdefault(m.strip().lower(), []).append(url)

        h1s = r.get("h1", [])
        if not h1s:
            issues.append(_issue("h1_missing", "high", url, "No H1", "Add one H1"))
        elif len(h1s) > 1:
            issues.append(_issue("h1_multiple", "medium", url, f"{len(h1s)} H1 tags",
                                 "Keep exactly one H1"))
        if not r.get("heading_order_ok", True):
            issues.append(_issue("heading_order", "low", url,
                                 "Heading levels skip (e.g. H2 -> H4)",
                                 "Fix heading hierarchy"))
        words = r.get("words", 0)
        if words < THIN_WORDS:
            issues.append(_issue("thin_content", "high", url,
                                 f"{words} words (<{THIN_WORDS})",
                                 "Expand or merge this page"))
        no_alt = r.get("images_no_alt", 0)
        if no_alt:
            issues.append(_issue("img_alt_missing", "medium", url,
                                 f"{no_alt} image(s) without alt text",
                                 "Generate descriptive alt text", auto=True))
        if not r.get("schema_types"):
            issues.append(_issue("schema_missing", "high", url,
                                 "No JSON-LD structured data",
                                 "Inject Article/FAQPage/Service schema", auto=True))
        if not r.get("og_ok", False):
            issues.append(_issue("og_missing", "low", url,
                                 "Open Graph title/description incomplete",
                                 "Add OG tags", auto=True))
        if not r.get("canonical"):
            issues.append(_issue("canonical_missing", "medium", url,
                                 "No canonical link", "Add self-referencing canonical"))
        elif r.get("canonical") != r["url"] and r.get("canonical") != r.get("final_url"):
            issues.append(_issue("canonical_mismatch", "high", url,
                                 f"Canonical points elsewhere: {r['canonical']}",
                                 "Verify the canonical target is intended"))
        if len(r.get("internal_links", [])) < 3:
            issues.append(_issue("few_internal_links", "medium", url,
                                 f"{len(r.get('internal_links', []))} internal links",
                                 "Add contextual internal links", auto=True))
        if "noindex" in (r.get("robots") or ""):
            issues.append(_issue("noindex", "critical", url,
                                 "Page is set to noindex", "Remove noindex if unintended"))

    for t, urls in titles.items():
        if len(urls) > 1:
            for u in urls:
                issues.append(_issue("title_duplicate", "high", u,
                                     f"Title shared with {len(urls)-1} other page(s)",
                                     "Make each title unique"))
    for m, urls in metas.items():
        if len(urls) > 1:
            for u in urls:
                issues.append(_issue("meta_duplicate", "medium", u,
                                     f"Meta shared with {len(urls)-1} other page(s)",
                                     "Make each meta unique"))
    return issues


def technical_audit(crawl: dict, graph: dict) -> list:
    issues = []
    for r in (crawl or {}).get("urls", []):
        url, status = r["url"], r.get("status", 0)
        if status == 0:
            issues.append(_issue("unreachable", "critical", url,
                                 "Did not respond", "Check the URL / server"))
        elif status >= 500:
            issues.append(_issue("server_error", "critical", url, f"HTTP {status}",
                                 "Fix the server error"))
        elif status == 404:
            issues.append(_issue("not_found", "high", url, "HTTP 404",
                                 "Restore the page or redirect it"))
        elif 300 <= status < 400 or r.get("redirected"):
            if r.get("redirect_hops", 0) > 1:
                issues.append(_issue("redirect_chain", "medium", url,
                                     f"{r['redirect_hops']} redirect hops",
                                     "Point the first link straight at the destination"))
        if r.get("ms", 0) > SLOW_MS:
            issues.append(_issue("slow_page", "medium", url,
                                 f"{r['ms']}ms server response",
                                 "Investigate caching / hosting"))
    for o in (graph or {}).get("orphans", []):
        issues.append(_issue("orphan_page", "high", o,
                             "No internal link points here — Google may never find it",
                             "Link to it from a relevant page", auto=True))
    for b in (graph or {}).get("broken_internal", []):
        issues.append(_issue("broken_internal_link", "high", b["from"],
                             f"Links to a URL that is not on the site: {b['to']}",
                             "Fix or remove the link"))
    return issues


def indexing_audit(inspect_results: dict) -> list:
    """From URL Inspection API results {url: {verdict, coverageState, ...}}."""
    issues = []
    for url, r in (inspect_results or {}).items():
        state = (r or {}).get("coverageState", "")
        verdict = (r or {}).get("verdict", "")
        if verdict and verdict != "PASS":
            issues.append(_issue("not_indexed", "critical", url,
                                 f"Google: {state or verdict}",
                                 "Resolve the reason, then request indexing"))
        gcan, dcan = (r or {}).get("googleCanonical"), (r or {}).get("userCanonical")
        if gcan and dcan and gcan.rstrip("/") != dcan.rstrip("/"):
            issues.append(_issue("canonical_override", "high", url,
                                 f"Google chose a different canonical: {gcan}",
                                 "Strengthen the intended page or consolidate"))
        if (r or {}).get("mobileUsability") == "FAIL":
            issues.append(_issue("mobile_fail", "high", url, "Mobile usability failing",
                                 "Fix the mobile layout issue"))
    return issues


# ======================================================================
#  SCORES  (0-100, all six)
# ======================================================================
def _score_from_issues(issues: list, page_count: int) -> int:
    """Penalty per page, capped. 100 = clean."""
    if page_count <= 0:
        return 0
    penalty = sum(i["weight"] for i in issues) / page_count
    return max(0, min(100, int(round(100 - penalty))))


def scores(*, crawl=None, on_page=None, technical=None, indexing=None,
           gsc=None, offpage=None, aeo=None, local=None) -> dict:
    pages = len([r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]) or 0
    tech = _score_from_issues(technical or [], pages)
    onp = _score_from_issues(on_page or [], pages)
    idx = _score_from_issues(indexing or [], pages) if indexing else 0

    queries = (gsc or {}).get("queries") or []
    spread = position_spread(queries)
    ranked = sum(spread.values())
    vis = 0
    if ranked:
        vis = int(round(100 * (spread["1-3"] * 1.0 + spread["4-10"] * 0.6
                               + spread["11-20"] * 0.25) / ranked))
    off = int(offpage.get("score", 0)) if isinstance(offpage, dict) else 0
    ae = int(aeo.get("score", 0)) if isinstance(aeo, dict) else 0
    lo = int(local.get("score", 0)) if isinstance(local, dict) else 0
    parts = [v for v in (vis, tech, onp, off, ae) if v is not None]
    return {"visibility": vis, "technical": tech, "on_page": onp,
            "indexing": idx, "off_page": off, "aeo": ae, "local": lo,
            "overall": int(round(sum(parts) / max(len(parts), 1))),
            "pages_scored": pages}


def summarize(issues: list) -> dict:
    by_code, by_sev = {}, {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for i in issues or []:
        by_code[i["code"]] = by_code.get(i["code"], 0) + 1
        by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
    return {"total": len(issues or []), "by_code": by_code, "by_severity": by_sev,
            "auto_fixable": sum(1 for i in issues or [] if i.get("auto")),
            "top": sorted(by_code.items(), key=lambda kv: -kv[1])[:10]}


def full_audit(*, crawl, graph, gsc=None, gsc_prev_pages=None,
               query_page=None, inspect=None) -> dict:
    """One call -> everything the boards and the work-order engine need."""
    gsc = gsc or {}
    queries = gsc.get("queries") or []
    op = on_page_audit(crawl)
    te = technical_audit(crawl, graph)
    ix = indexing_audit(inspect or {})
    return {
        "on_page": op, "technical": te, "indexing": ix,
        "issues": op + te + ix,
        "summary": summarize(op + te + ix),
        "striking": striking_distance(queries),
        "cannibalization": cannibalization(query_page or []),
        "decay": decay(gsc.get("pages") or [], gsc_prev_pages or []),
        "rising": rising(gsc.get("pages") or [], gsc_prev_pages or []),
        "zero_click": zero_click(queries),
        "ctr_gaps": ctr_underperformers(queries),
        "intent": intent_split(queries),
        "branded": branded_split(queries),
        "spread": position_spread(queries),
        "scores": scores(crawl=crawl, on_page=op, technical=te, indexing=ix, gsc=gsc),
    }


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    q = [{"key": "ai automation law firm", "position": 6.2, "impressions": 400, "clicks": 3},
         {"key": "anthropos automation", "position": 1.4, "impressions": 90, "clicks": 30},
         {"key": "price monitoring software", "position": 14.0, "impressions": 220, "clicks": 0},
         {"key": "how to automate intake", "position": 42.0, "impressions": 15, "clicks": 0}]
    s = striking_distance(q)
    assert [r["query"] for r in s] == ["ai automation law firm", "price monitoring software"], s
    assert s[0]["page_now"] == 1 and s[1]["page_now"] == 2, s

    zc = zero_click(q, min_impr=10)
    assert {r["query"] for r in zc} == {"price monitoring software", "how to automate intake"}, zc
    assert zc[0]["reason"].startswith("position too low"), zc[0]

    cg = ctr_underperformers(q, min_impr=20)
    assert cg and cg[0]["query"] == "ai automation law firm", cg

    cn = cannibalization([
        {"keys": ["automation for lawyers", "/guide-a"], "impressions": 100, "clicks": 2, "position": 8},
        {"keys": ["automation for lawyers", "/blog-b"], "impressions": 60, "clicks": 0, "position": 14},
        {"keys": ["solo topic", "/x"], "impressions": 10, "clicks": 1, "position": 5}])
    assert len(cn) == 1 and cn[0]["page_count"] == 2 and cn[0]["best"] == "/guide-a", cn

    d = decay([{"key": "/p1", "clicks": 4}, {"key": "/p2", "clicks": 30}],
              [{"key": "/p1", "clicks": 40}, {"key": "/p2", "clicks": 28}])
    assert len(d) == 1 and d[0]["url"] == "/p1" and d[0]["lost_clicks"] == 36, d

    assert intent_of("best automation agency") == "commercial"
    assert intent_of("book a demo") == "transactional"
    assert intent_of("how does n8n work") == "informational"
    isp = intent_split(q)
    assert isp["commercial"]["queries"] >= 1, isp

    crawl = {"urls": [
        {"url": "https://x.com/a", "status": 200, "title": "T" * 80, "title_len": 80,
         "meta_desc": "", "meta_len": 0, "h1": [], "words": 120, "images_no_alt": 2,
         "schema_types": [], "og_ok": False, "canonical": "https://x.com/a",
         "internal_links": [], "heading_order_ok": True, "robots": ""},
        {"url": "https://x.com/b", "status": 404, "title": "", "title_len": 0,
         "meta_desc": "", "meta_len": 0, "h1": [], "words": 0, "images_no_alt": 0,
         "schema_types": [], "og_ok": False, "canonical": "",
         "internal_links": [], "heading_order_ok": True, "robots": ""}]}
    graph = {"orphans": ["https://x.com/a"], "broken_internal": [
        {"from": "https://x.com/a", "to": "https://x.com/gone"}]}
    op, te = on_page_audit(crawl), technical_audit(crawl, graph)
    codes = {i["code"] for i in op}
    assert {"title_long", "meta_missing", "h1_missing", "thin_content",
            "img_alt_missing", "schema_missing", "few_internal_links"} <= codes, codes
    tcodes = {i["code"] for i in te}
    assert {"not_found", "orphan_page", "broken_internal_link"} <= tcodes, tcodes
    assert any(i["auto"] for i in op), "some issues must be auto-fixable"

    full = full_audit(crawl=crawl, graph=graph, gsc={"queries": q, "pages": []})
    assert full["summary"]["total"] == len(op) + len(te), full["summary"]
    assert 0 <= full["scores"]["overall"] <= 100, full["scores"]
    assert full["scores"]["visibility"] > 0, full["scores"]
    print("seo self-check OK — striking, cannibal, decay, ctr, audits, scores")
