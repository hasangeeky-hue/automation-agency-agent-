"""
content_engine_seo_boards.py
============================================================================
Every SEO card renders HERE, not in content_engine_dashboard.py — that file is
already 300KB+ and must not grow.

11 boards. Each card carries a NUMBER, a plain-English READ of what the number
means, and (where one exists) the action that fixes it. Zeros are shown with
context, never hidden and never faked: "position 42 = page 5, nobody scrolls
that far" beats a blank card.

Boards -> dashboard pages:
    seocmd    1  SEO Command
    seotech   2  Technical  + 3 Indexing
    seoonpage 4  On-Page    + 7 Internal Links
    seo       5  Keywords   + 6 Content + 9 AEO + competitor delta   (existing page)
    seooff    8  Off-Page   + 10 Local
    seowork   12 Work Orders

Run offline self-check:  python content_engine_seo_boards.py
============================================================================
"""

from __future__ import annotations

TEAL, VIOLET, BLUE, GREEN, AMBER, PINK = (
    "#2FE3D2", "#8B7CFF", "#4C8DFF", "#3FD98B", "#F5B14C", "#FF6B93")


def _H():
    """Late import of the dashboard's render helpers (avoids a circular import
    at module load — dashboard imports us, we import it only when rendering)."""
    import content_engine_dashboard as D
    return D


def _pct_color(v, good=80, ok=50):
    return GREEN if v >= good else (AMBER if v >= ok else PINK)


def _cards(rows, cols=3):
    """rows = [(title, big, sub, body, insight, src, accent)] -> a card grid."""
    H = _H()
    inner = "".join(H._insight_card(t, b, s, body or "", ins or "", src or "", acc)
                    for t, b, s, body, ins, src, acc in rows)
    return f"<div class='grid g{cols}' style='margin-top:8px'>{inner}</div>"


def _head(icon, title, desc):
    H = _H()
    return (f"<div class='card full' style='margin-top:12px'><p class='ct'>{icon} {H._esc(title)}</p>"
            f"<p class='cc'>{H._esc(desc)}</p></div>")


def _rows(items, right_fmt=lambda x: "", left_fmt=lambda x: str(x), limit=12, empty=""):
    H = _H()
    if not items:
        return H._empty(empty or "Nothing here yet.")
    return "".join(
        f"<div class='fe'><span class='mut'>{H._esc(left_fmt(i))}</span>"
        f"<span class='dim' style='margin-left:auto'>{H._esc(right_fmt(i))}</span></div>"
        for i in items[:limit])


def _btn(label, action):
    return (f"<div class='ctrl' style='margin-top:10px'>"
            f"<button class='cbtn' onclick=\"{action}\">{label}</button></div>")


def _not_run(what, action_label, action):
    H = _H()
    return (f"<div class='card full' style='margin-top:12px'><p class='ct'>{H._esc(what)}</p>"
            f"<p class='cc'>Not run yet — this board fills the moment it does. "
            f"Costs nothing to run.</p>{_btn(action_label, action)}</div>")


# ======================================================================
#  BOARD 1 — SEO COMMAND  (12 cards)
# ======================================================================
def board_command(ctx) -> str:
    H = _H()
    sc = ctx.get("scores") or {}
    audit = ctx.get("audit") or {}
    orders = ctx.get("orders") or []
    gsc = ((ctx.get("insights") or {}).get("gsc") or {})
    ga4 = ((ctx.get("insights") or {}).get("ga4") or {})
    inspect = ctx.get("inspect") or {}
    aeo = ctx.get("aeo") or {}
    crawl = ctx.get("crawl") or {}

    pages = crawl.get("count", 0)
    indexed = sum(1 for r in inspect.values() if r.get("verdict") == "PASS")
    q = gsc.get("queries") or []
    clicks = sum(r.get("clicks", 0) for r in q)
    impr = sum(r.get("impressions", 0) for r in q)
    sessions = ((ga4.get("totals") or {}).get("sessions")) or 0
    open_orders = [o for o in orders if o.get("status") == "open"]
    done = [o for o in orders if o.get("status") == "done"]
    crit = [o for o in open_orders if o.get("severity") == "critical"]

    vis, tech, onp = sc.get("visibility", 0), sc.get("technical", 0), sc.get("on_page", 0)
    off = (ctx.get("offpage") or {}).get("score", 0)
    aeo_score = aeo.get("score", 0)

    top3 = sorted(open_orders, key=lambda o: -o.get("priority", 0))[:3]
    moves = _rows(top3, left_fmt=lambda o: f"◆ {o.get('fix') or o.get('code')}",
                  right_fmt=lambda o: o.get("url", "").split("/")[-1][:28] or "site-wide",
                  empty="No open work — the queue is clear.")
    risks = []
    if crit:
        risks.append(f"⛔ {len(crit)} critical issue(s) — indexing or server level")
    if pages and indexed and indexed < pages * 0.8:
        risks.append(f"⚠ Only {indexed}/{len(inspect)} inspected URLs are indexed")
    for d in (audit.get("decay") or [])[:2]:
        risks.append(f"↓ {d['url'].split('/')[-1][:32]} lost {abs(d['change_pct'])}% of clicks")
    if not (ctx.get("offpage") or {}).get("connected"):
        risks.append("🔌 Backlink profile unmeasured — DataForSEO not connected")
    risk_html = _rows(risks, left_fmt=lambda s: s, empty="Nothing flagged right now.")

    fixed = _rows(sorted(done, key=lambda o: o.get("done_at") or "", reverse=True),
                  left_fmt=lambda o: f"✓ {o.get('result') or o.get('code')}",
                  right_fmt=lambda o: (o.get("done_at") or "")[:10],
                  empty="No automated fixes applied yet.")
    changed = []
    for r in (audit.get("rising") or [])[:3]:
        changed.append(f"▲ {r['url'].split('/')[-1][:30]} +{r['gained']} clicks")
    for r in (audit.get("decay") or [])[:3]:
        changed.append(f"▼ {r['url'].split('/')[-1][:30]} {r['change_pct']}%")
    changed_html = _rows(changed, left_fmt=lambda s: s,
                         empty="Needs two crawls to compare — check back after the next run.")

    return _head("🧭", "SEO Command", "Six scores, the three moves that matter, and what the machine did without you.") + _cards([
        ("Overall SEO score", sc.get("overall", 0), "of 100", "",
         f"Composite of visibility, technical, on-page, off-page and AEO across {sc.get('pages_scored',0)} pages.",
         "computed from your own crawl + Search Console", _pct_color(sc.get("overall", 0))),
        ("Indexed URLs", f"{indexed}/{len(inspect) or pages}",
         "confirmed by Google", "",
         ("Google confirmed these pages are in the index. Anything not indexed cannot rank at all."
          if inspect else "Run the index inspection to get Google's own verdict per URL — it's free."),
         "URL Inspection API", _pct_color(100 * indexed / max(len(inspect), 1))),
        ("Technical health", tech, "of 100", "",
         f"{len(audit.get('technical') or [])} technical findings across the crawl.",
         "own crawler", _pct_color(tech)),
        ("On-page score", onp, "of 100", "",
         f"{len(audit.get('on_page') or [])} on-page findings — titles, metas, headings, schema, alt text.",
         "own crawler", _pct_color(onp)),
        ("Off-page authority", off or "—", "of 100", "",
         ((ctx.get("offpage") or {}).get("reason")
          or f"{(ctx.get('offpage') or {}).get('referring_domains', 0)} referring domains."),
         "DataForSEO" if off else "not connected", _pct_color(off) if off else AMBER),
        ("AEO presence", aeo_score or "—", "of 100", "",
         (f"You appear in {aeo.get('mention_rate', 0)}% of {aeo.get('prompts_tested', 0)} buyer-intent AI answers."
          if aeo else "Run an AI-visibility probe to see whether AI answers name you."),
         "Claude + Serper" if aeo else "not run", _pct_color(aeo_score) if aeo else AMBER),
        ("Organic sessions", f"{sessions:,}", "last 28 days", "",
         ("Real visits from search." if sessions
          else "Zero sessions is expected while rankings are still climbing — impressions come first."),
         "GA4", BLUE),
        ("Search clicks", f"{clicks:,}", f"on {impr:,} impressions", "",
         (f"CTR {round(100*clicks/impr,1)}% — people saw you {impr:,} times."
          if impr else "No impressions yet: Google hasn't ranked these pages high enough to show them."),
         "Search Console", TEAL),
        ("Today's top 3 moves", len(top3), "highest impact ÷ effort", moves,
         "Ranked by how much they move rankings against how long they take.",
         "work-order engine", VIOLET),
        ("What changed", len(changed), "pages up or down", changed_html,
         "Week-over-week movement per page — the early warning that used to be silent.",
         "Search Console comparison", AMBER),
        ("Fixed while you slept", len(done), "auto-applied", fixed,
         "Schema, internal links and alt text are applied without asking. Copy always waits for you.",
         "work-order log", GREEN),
        ("Risk radar", len(risks), "flagged", risk_html,
         "Anything that could cost you traffic if it stays unfixed.",
         "audit + index status", PINK if risks else GREEN),
    ])


# ======================================================================
#  BOARD 2 — TECHNICAL  (18 cards)
# ======================================================================
def board_technical(ctx) -> str:
    H = _H()
    crawl = ctx.get("crawl") or {}
    graph = ctx.get("graph") or {}
    audit = ctx.get("audit") or {}
    speed = ctx.get("speed") or []
    if not crawl:
        return _not_run("🔧 Technical health & crawl", "▶ Run the first crawl", "runCrawl()")

    urls = crawl.get("urls") or []
    codes = {}
    for r in urls:
        s = r.get("status", 0)
        key = "no response" if s == 0 else f"{s // 100}xx"
        codes[key] = codes.get(key, 0) + 1
    tech = audit.get("technical") or []

    def n(code):
        return sum(1 for i in tech if i["code"] == code)

    ok = sum(1 for r in urls if r.get("status") == 200)
    noindex = sum(1 for r in urls if "noindex" in (r.get("robots") or ""))
    thin = sum(1 for r in urls if r.get("status") == 200 and r.get("words", 0) < 300)
    dup_t = n("title_duplicate") or sum(1 for i in (audit.get("on_page") or [])
                                        if i["code"] == "title_duplicate")
    dup_m = sum(1 for i in (audit.get("on_page") or []) if i["code"] == "meta_duplicate")
    slow = [r for r in urls if r.get("ms", 0) > 2500]
    avg_ms = round(sum(r.get("ms", 0) for r in urls) / max(len(urls), 1))
    https = sum(1 for r in urls if r["url"].startswith("https://"))
    depth = graph.get("depth_spread") or {}
    deep = sum(v for k, v in depth.items() if k not in ("0", "1", "2", "unreachable"))
    unreach = depth.get("unreachable", 0)
    perf = [s.get("performance", 0) for s in speed if s]
    avg_perf = round(sum(perf) / len(perf)) if perf else 0
    lcp = [s.get("lcp_ms", 0) for s in speed if s.get("lcp_ms")]
    avg_lcp = round(sum(lcp) / len(lcp)) if lcp else 0
    cls_vals = [s.get("cls", 0) for s in speed if s.get("cls") is not None]
    avg_cls = round(sum(cls_vals) / len(cls_vals), 3) if cls_vals else 0

    code_body = _rows(sorted(codes.items(), key=lambda kv: kv[0]),
                      left_fmt=lambda kv: kv[0], right_fmt=lambda kv: f"{kv[1]} URLs")
    broken_body = _rows(graph.get("broken_internal") or [],
                        left_fmt=lambda b: b["from"].split("/")[-1][:30] or "/",
                        right_fmt=lambda b: "→ " + b["to"].split("/")[-1][:26],
                        empty="No broken internal links — every link resolves.")
    slow_body = _rows(sorted(slow, key=lambda r: -r.get("ms", 0)),
                      left_fmt=lambda r: r["url"].split("/")[-1][:34] or "/",
                      right_fmt=lambda r: f"{r.get('ms',0)}ms",
                      empty="Every page responded under 2.5s.")
    depth_body = _rows(sorted(depth.items()),
                       left_fmt=lambda kv: ("unreachable by link" if kv[0] == "unreachable"
                                            else f"{kv[0]} click(s) from home"),
                       right_fmt=lambda kv: f"{kv[1]} pages")

    return _head("🔧", "Technical health & crawl",
                 f"Your own crawler read {len(urls)} URLs. Everything here is measured, not estimated.") + _cards([
        ("Pages crawled", len(urls), f"{ok} returned 200", code_body,
         f"{ok} of {len(urls)} URLs are live and readable by a search engine.",
         "own crawler", _pct_color(100 * ok / max(len(urls), 1))),
        ("Status codes", len(codes), "distinct response types", code_body,
         "Anything that isn't 2xx or an intended 301 is wasted crawl budget.",
         "own crawler", BLUE),
        ("Broken internal links", graph.get("broken_count", 0), "links to nowhere", broken_body,
         ("Each one wastes crawl budget and dead-ends a reader."
          if graph.get("broken_count") else "Clean — nothing links into a void."),
         "link graph", PINK if graph.get("broken_count") else GREEN),
        ("404 pages", n("not_found"), "not found", "",
         "A 404 that used to rank leaks every link pointing at it. Redirect it.",
         "own crawler", PINK if n("not_found") else GREEN),
        ("Server errors", n("server_error"), "5xx responses", "",
         "5xx tells Google your site is unreliable — it crawls less when it sees these.",
         "own crawler", PINK if n("server_error") else GREEN),
        ("Unreachable URLs", n("unreachable"), "no response at all", "",
         "These never responded. Either they're gone, or something is blocking the crawler.",
         "own crawler", PINK if n("unreachable") else GREEN),
        ("Redirect chains", n("redirect_chain"), "multi-hop redirects", "",
         "Every extra hop loses a little link equity and slows the visitor down.",
         "own crawler", AMBER if n("redirect_chain") else GREEN),
        ("Canonical conflicts", n("canonical_mismatch") + sum(
            1 for i in (audit.get("on_page") or []) if i["code"] == "canonical_mismatch"),
         "point somewhere unexpected", "",
         "A canonical pointing at the wrong page tells Google to ignore this one.",
         "own crawler", AMBER),
        ("Noindex pages", noindex, "excluded from Google", "",
         ("Intentional on utility pages; a disaster on a page you want ranking."
          if noindex else "No page is accidentally hidden from Google."),
         "robots meta", AMBER if noindex else GREEN),
        ("Orphan pages", graph.get("orphan_count", 0), "no internal links in",
         _rows(graph.get("orphans") or [], left_fmt=lambda u: u.split("/")[-1][:38] or "/",
               empty="Every page is linked from somewhere."),
         "Google finds pages by following links. An orphan is invisible unless the sitemap saves it.",
         "link graph", PINK if graph.get("orphan_count") else GREEN),
        ("Click depth", deep, "pages 3+ clicks deep", depth_body,
         "Pages buried deep get crawled less often and rank worse. Aim for 3 clicks or fewer.",
         "link graph", AMBER if deep else GREEN),
        ("Unreachable by link", unreach, "sitemap-only", "",
         ("These exist in the sitemap but nothing links to them."
          if unreach else "Every page is reachable by following links."),
         "link graph", AMBER if unreach else GREEN),
        ("Duplicate titles", dup_t, "shared across pages", "",
         "Two pages with one title look like one page to Google — it picks one and drops the other.",
         "own crawler", AMBER if dup_t else GREEN),
        ("Duplicate metas", dup_m, "shared descriptions", "",
         "Less damaging than duplicate titles, but it wastes your SERP pitch.",
         "own crawler", AMBER if dup_m else GREEN),
        ("Thin pages", thin, "under 300 words", "",
         "Thin pages rarely rank and can drag the whole site's quality signal down.",
         "own crawler", AMBER if thin else GREEN),
        ("Server response", f"{avg_ms}ms", "average across the crawl", slow_body,
         (f"{len(slow)} page(s) took over 2.5s — that's felt by both visitors and Googlebot."
          if slow else "Every page responded quickly."),
         "own crawler", _pct_color(100 if avg_ms < 800 else 60 if avg_ms < 2000 else 20)),
        ("Core Web Vitals", avg_perf or "—", "PageSpeed performance score",
         _rows(speed, left_fmt=lambda s: s.get("url", "").split("/")[-1][:30] or "/",
               right_fmt=lambda s: f"{s.get('performance',0)} · LCP {s.get('lcp_ms',0)}ms",
               empty="Run a speed check — the API is free."),
         (f"Average LCP {avg_lcp}ms, CLS {avg_cls}. Google wants LCP under 2500ms."
          if speed else "PageSpeed Insights costs nothing and needs no key."),
         "PageSpeed Insights API", _pct_color(avg_perf) if speed else AMBER),
        ("HTTPS coverage", f"{https}/{len(urls)}", "secure URLs", "",
         ("Every crawled URL is HTTPS." if https == len(urls)
          else "Some URLs are still HTTP — that is a ranking and trust problem."),
         "own crawler", GREEN if https == len(urls) else PINK),
    ])


# ======================================================================
#  BOARD 3 — INDEXING  (12 cards)
# ======================================================================
def board_indexing(ctx) -> str:
    H = _H()
    inspect = ctx.get("inspect") or {}
    crawl = ctx.get("crawl") or {}
    idx_state = ctx.get("indexnow") or {}
    if not inspect:
        return (_head("📇", "Indexing & coverage",
                      "Google's own verdict on every URL — free, 2,000 checks a day, and never used until now.")
                + _not_run("Index inspection has not run", "▶ Inspect URLs with Google",
                           "runInspect()"))

    total = len(inspect)
    passed = sum(1 for r in inspect.values() if r.get("verdict") == "PASS")
    reasons = {}
    for r in inspect.values():
        if r.get("verdict") != "PASS":
            reasons[r.get("coverageState") or "unknown"] = \
                reasons.get(r.get("coverageState") or "unknown", 0) + 1
    canon_mismatch = [u for u, r in inspect.items()
                      if r.get("googleCanonical") and r.get("userCanonical")
                      and r["googleCanonical"].rstrip("/") != r["userCanonical"].rstrip("/")]
    mobile_fail = [u for u, r in inspect.items() if r.get("mobileUsability") == "FAIL"]
    rich = sum(1 for r in inspect.values() if r.get("richResults") == "PASS")
    crawled = [r.get("lastCrawlTime", "")[:10] for r in inspect.values() if r.get("lastCrawlTime")]
    robots_blocked = sum(1 for r in inspect.values()
                         if "DISALLOWED" in (r.get("robotsTxtState") or ""))
    fetch_fail = sum(1 for r in inspect.values()
                     if r.get("pageFetchState") not in ("SUCCESSFUL", "", None))
    sitemap_n = crawl.get("count", 0)

    reason_body = _rows(sorted(reasons.items(), key=lambda kv: -kv[1]),
                        left_fmt=lambda kv: kv[0], right_fmt=lambda kv: f"{kv[1]} URLs",
                        empty="Every inspected URL is indexed.")
    crawl_body = _rows(sorted({d: crawled.count(d) for d in set(crawled)}.items(), reverse=True),
                       left_fmt=lambda kv: kv[0], right_fmt=lambda kv: f"{kv[1]} pages",
                       empty="No crawl dates returned.")
    return _head("📇", "Indexing & coverage",
                 "Google's own answer for each URL: indexed or not, which canonical it chose, when it last looked.") + _cards([
        ("Indexed", f"{passed}/{total}", "confirmed by Google", "",
         (f"{round(100*passed/max(total,1))}% of inspected URLs are in the index. "
          "Anything else cannot rank, however good it is."),
         "URL Inspection API", _pct_color(100 * passed / max(total, 1))),
        ("Not indexed", total - passed, "excluded", reason_body,
         ("Google's stated reason for each. 'Crawled – currently not indexed' usually means "
          "thin or duplicate content, not a technical fault."
          if total - passed else "Nothing excluded."),
         "URL Inspection API", PINK if total - passed else GREEN),
        ("Canonical overridden", len(canon_mismatch), "Google chose differently",
         _rows(canon_mismatch, left_fmt=lambda u: u.split("/")[-1][:38],
               empty="Google agreed with every canonical you declared."),
         ("Google ignored your canonical on these — usually a duplicate-content signal."
          if canon_mismatch else "Your canonicals are being respected."),
         "URL Inspection API", AMBER if canon_mismatch else GREEN),
        ("Mobile usability", f"{total - len(mobile_fail)}/{total}", "pass", "",
         ("Mobile-first indexing means Google ranks the mobile version. A fail here is a ranking cap."
          if mobile_fail else "Every inspected page passes on mobile."),
         "URL Inspection API", GREEN if not mobile_fail else PINK),
        ("Rich result eligible", rich, "pages with valid markup", "",
         ("These can show stars, FAQs or breadcrumbs in the SERP — more space, more clicks."
          if rich else "No page currently qualifies for a rich result. Schema is the fix."),
         "URL Inspection API", GREEN if rich else AMBER),
        ("Robots blocked", robots_blocked, "disallowed by robots.txt", "",
         ("robots.txt is telling Google to stay away from these."
          if robots_blocked else "robots.txt is not blocking anything inspected."),
         "URL Inspection API", PINK if robots_blocked else GREEN),
        ("Fetch failures", fetch_fail, "Google couldn't load", "",
         ("Google tried and failed to fetch these — a server or redirect problem."
          if fetch_fail else "Google fetched every inspected page successfully."),
         "URL Inspection API", PINK if fetch_fail else GREEN),
        ("Last crawl recency", len(set(crawled)), "distinct crawl dates", crawl_body,
         ("How recently Google looked. Pages it hasn't seen in months are pages it has deprioritised."
          if crawled else "No crawl timestamps returned."),
         "URL Inspection API", BLUE),
        ("Sitemap vs crawled", f"{sitemap_n}", "URLs known to the crawler", "",
         f"Your crawler found {sitemap_n} URLs; {total} have been checked against Google so far.",
         "own crawler + GSC", BLUE),
        ("IndexNow submissions", idx_state.get("submitted", 0), "pushed to Bing/Yandex", "",
         (f"Status: {idx_state.get('status','')}. Google ignores IndexNow, so the sitemap ping covers it."
          if idx_state else "IndexNow not configured — it is free and instant for Bing/Yandex."),
         "IndexNow API", GREEN if idx_state.get("submitted") else AMBER),
        ("Indexation diagnosis", total - passed, "to resolve", reason_body,
         ("Fix the stated reason first — requesting indexing on an unresolved page just resets the clock."
          if total - passed else "Nothing to diagnose."),
         "computed", VIOLET),
        ("Newest content", "—", "days to first index", "",
         "Once two inspections exist, this shows how long Google takes to index a new post.",
         "URL Inspection API over time", BLUE),
    ])


# ======================================================================
#  BOARD 4 — ON-PAGE  (16 cards)
# ======================================================================
def board_onpage(ctx) -> str:
    H = _H()
    crawl = ctx.get("crawl") or {}
    audit = ctx.get("audit") or {}
    orders = ctx.get("orders") or []
    if not crawl:
        return _not_run("📄 On-page quality", "▶ Run the first crawl", "runCrawl()")

    pages = [r for r in crawl.get("urls", []) if r.get("status") == 200]
    op = audit.get("on_page") or []

    def n(*codes):
        return sum(1 for i in op if i["code"] in codes)

    good_title = sum(1 for r in pages if 30 <= r.get("title_len", 0) <= 60)
    good_meta = sum(1 for r in pages if 70 <= r.get("meta_len", 0) <= 160)
    one_h1 = sum(1 for r in pages if len(r.get("h1") or []) == 1)
    words = [r.get("words", 0) for r in pages]
    avg_words = round(sum(words) / max(len(words), 1))
    imgs = sum(r.get("images", 0) for r in pages)
    no_alt = sum(r.get("images_no_alt", 0) for r in pages)
    schema_ok = sum(1 for r in pages if r.get("schema_types"))
    schema_types = {}
    for r in pages:
        for t in r.get("schema_types") or []:
            schema_types[t] = schema_types.get(t, 0) + 1
    og_ok = sum(1 for r in pages if r.get("og_ok"))
    order_ok = sum(1 for r in pages if r.get("heading_order_ok", True))
    links_avg = round(sum(len(r.get("internal_links") or []) for r in pages)
                      / max(len(pages), 1), 1)
    proposals = [o for o in orders if (o.get("extra") or {}).get("proposal")]

    worst = sorted(pages, key=lambda r: -sum(
        1 for i in op if i["url"] == r["url"]))[:20]
    worst_body = _rows(worst, left_fmt=lambda r: r["url"].split("/")[-1][:34] or "/",
                       right_fmt=lambda r: f"{sum(1 for i in op if i['url']==r['url'])} issues",
                       empty="No page has an on-page issue.")
    prop_body = _rows(proposals,
                      left_fmt=lambda o: f"{(o['extra']['proposal'].get('field') or '').upper()}: "
                                         f"{o['extra']['proposal'].get('after','')[:46]}",
                      right_fmt=lambda o: o["url"].split("/")[-1][:20],
                      empty="No copy rewrites waiting. Run the fixer to generate some.")
    schema_body = _rows(sorted(schema_types.items(), key=lambda kv: -kv[1]),
                        left_fmt=lambda kv: kv[0], right_fmt=lambda kv: f"{kv[1]} pages",
                        empty="No structured data found anywhere on the site.")
    return _head("📄", "On-page quality",
                 f"Every one of your {len(pages)} live pages, audited element by element.") + _cards([
        ("Titles in range", f"{good_title}/{len(pages)}", "30–60 characters", "",
         ("A title over 60 chars gets cut off mid-sentence in Google; under 30 wastes the slot."),
         "own crawler", _pct_color(100 * good_title / max(len(pages), 1))),
        ("Missing titles", n("title_missing"), "no <title> at all", "",
         "Google invents one from the page — badly. Always worse than writing it yourself.",
         "own crawler", PINK if n("title_missing") else GREEN),
        ("Meta descriptions", f"{good_meta}/{len(pages)}", "70–160 characters", "",
         "The meta doesn't rank you, but it decides whether the ranking earns a click.",
         "own crawler", _pct_color(100 * good_meta / max(len(pages), 1))),
        ("Missing metas", n("meta_missing"), "no description", "",
         ("Google will scrape a sentence off the page instead — rarely the one you'd pick."
          if n("meta_missing") else "Every page pitches itself in the SERP."),
         "own crawler", PINK if n("meta_missing") else GREEN),
        ("Single H1", f"{one_h1}/{len(pages)}", "exactly one", "",
         "One H1 states what the page is about. Zero or many muddies it.",
         "own crawler", _pct_color(100 * one_h1 / max(len(pages), 1))),
        ("Heading structure", f"{order_ok}/{len(pages)}", "correct hierarchy", "",
         "Skipping H2→H4 breaks the outline both screen readers and AI engines rely on.",
         "own crawler", _pct_color(100 * order_ok / max(len(pages), 1))),
        ("Average length", f"{avg_words:,}", "words per page", "",
         ("Depth alone doesn't rank, but under 300 words rarely competes for anything commercial."),
         "own crawler", BLUE),
        ("Thin pages", n("thin_content"), "under 300 words", "",
         "Expand, merge into a stronger page, or remove. Leaving them costs site-wide quality.",
         "own crawler", AMBER if n("thin_content") else GREEN),
        ("Image alt coverage", f"{imgs - no_alt}/{imgs}", "images described", "",
         (f"{no_alt} image(s) have no alt text — invisible to Google Images and to screen readers. "
          "The fixer writes these automatically." if no_alt
          else "Every image is described."),
         "own crawler", _pct_color(100 * (imgs - no_alt) / max(imgs, 1))),
        ("Schema coverage", f"{schema_ok}/{len(pages)}", "pages with JSON-LD", schema_body,
         ("Structured data is how you get FAQ boxes, breadcrumbs and AI citations. "
          "The fixer injects it automatically."),
         "own crawler", _pct_color(100 * schema_ok / max(len(pages), 1))),
        ("Open Graph", f"{og_ok}/{len(pages)}", "share-ready", "",
         "Without OG tags your links look broken when shared on LinkedIn or WhatsApp.",
         "own crawler", _pct_color(100 * og_ok / max(len(pages), 1))),
        ("Internal links per page", links_avg, "average outgoing", "",
         ("Under 3 internal links means the page hoards its authority instead of passing it on."),
         "link graph", _pct_color(100 if links_avg >= 5 else 50 if links_avg >= 3 else 20)),
        ("Duplicate titles", n("title_duplicate"), "pages sharing a title", "",
         "Google picks one and quietly ignores the rest.",
         "own crawler", AMBER if n("title_duplicate") else GREEN),
        ("Pages to fix first", len(worst), "ranked by issue count", worst_body,
         "Start at the top — these pages carry the most defects per page.",
         "computed", VIOLET),
        ("Rewrites awaiting you", len(proposals), "titles & metas drafted", prop_body,
         "Copy is never pushed without your approval. Review and click to apply.",
         "SEO fixer", AMBER if proposals else GREEN),
        ("E-E-A-T signals", "—", "author, citations, credentials", "",
         ("Google weighs who wrote it and whether it cites anything. Author bios and outbound "
          "citations on your guides are the cheapest trust signal you're not using."),
         "manual review", BLUE),
    ])


# ======================================================================
#  BOARD 5 — KEYWORDS & RANK  (18 cards)
# ======================================================================
def board_keywords(ctx) -> str:
    H = _H()
    audit = ctx.get("audit") or {}
    gsc = ((ctx.get("insights") or {}).get("gsc") or {})
    ranks = ctx.get("ranks") or []
    q = gsc.get("queries") or []
    spread = audit.get("spread") or {}
    striking = audit.get("striking") or []
    intent = audit.get("intent") or {}
    branded = audit.get("branded") or {}
    zero = audit.get("zero_click") or []
    ctr_gaps = audit.get("ctr_gaps") or []
    cannib = audit.get("cannibalization") or []

    total_impr = sum(r.get("impressions", 0) for r in q)
    total_clicks = sum(r.get("clicks", 0) for r in q)
    avg_pos = round(sum(r.get("position", 0) for r in q) / max(len(q), 1), 1)
    up = sum(1 for r in ranks if r.get("delta", 0) > 0)
    down = sum(1 for r in ranks if r.get("delta", 0) < 0)
    tracked = len({r.get("query") for r in ranks})
    features = {}
    for r in ranks:
        for f in r.get("features", []):
            features[f] = features.get(f, 0) + 1

    striking_body = _rows(striking, left_fmt=lambda r: r["query"][:40],
                          right_fmt=lambda r: f"#{r['position']} · {r['impressions']} impr · +{r['potential_clicks']} possible",
                          empty="No queries sit between #4 and #20 yet.")
    spread_body = H._bars([(k, v) for k, v in spread.items()], VIOLET) if spread else H._empty("Fills from Search Console.")
    cannib_body = _rows(cannib, left_fmt=lambda r: r["query"][:38],
                        right_fmt=lambda r: f"{r['page_count']} pages competing",
                        empty="No two pages compete for the same query.")
    ctr_body = _rows(ctr_gaps, left_fmt=lambda r: r["query"][:38],
                     right_fmt=lambda r: f"#{r['position']} · {r['ctr_actual']}% vs {r['ctr_expected']}% expected",
                     empty="No ranking page is underperforming on clicks.")
    zero_body = _rows(zero, left_fmt=lambda r: r["query"][:38],
                      right_fmt=lambda r: f"{r['impressions']} impr · {r['reason']}",
                      empty="Every query with impressions earns at least one click.")
    intent_body = H._bars([(k.title(), v["clicks"]) for k, v in intent.items()], TEAL) if intent else ""
    feature_body = _rows(sorted(features.items(), key=lambda kv: -kv[1]),
                         left_fmt=lambda kv: kv[0].replace("_", " ").title(),
                         right_fmt=lambda kv: f"{kv[1]} queries",
                         empty="Run the rank tracker to see which SERP features appear.")
    country_body = _rows(gsc.get("countries") or [],
                         left_fmt=lambda r: str(r.get("key", "")).upper(),
                         right_fmt=lambda r: f"{r.get('impressions',0)} impr · {r.get('clicks',0)} clicks",
                         empty="No country data yet.")
    device_body = _rows(gsc.get("devices") or [],
                        left_fmt=lambda r: str(r.get("key", "")).title(),
                        right_fmt=lambda r: f"{r.get('impressions',0)} impr",
                        empty="No device data yet.")
    return _head("🔑", "Keyword & rank intelligence",
                 "Where you rank, what's one push from page one, and what's quietly fighting itself.") + _cards([
        ("Queries ranking", len(q), "distinct queries seen", "",
         (f"You appear for {len(q)} queries at an average position of #{avg_pos}."
          if q else "No Search Console query data for this window."),
         "Search Console", TEAL),
        ("Striking distance", len(striking), "queries at #4–#20", striking_body,
         ("These already rank — they just don't rank high enough to be clicked. "
          "This is the highest-return list on the whole dashboard."
          if striking else "Nothing in the #4–#20 band yet — that band fills as pages climb."),
         "computed from Search Console", GREEN if striking else AMBER),
        ("Position spread", sum(spread.values()) if spread else 0, "queries by rank band", spread_body,
         (f"{spread.get('1-3',0)} on the podium, {spread.get('4-10',0)} on page one, "
          f"{spread.get('11-20',0)} on page two."),
         "Search Console", VIOLET),
        ("Average position", f"#{avg_pos}" if q else "—", f"across {len(q)} queries", "",
         (f"That's page {int((avg_pos-1)//10)+1} of Google. Clicks effectively start on page one."
          if q else "No ranking data yet."),
         "Search Console", _pct_color(100 - min(avg_pos, 50) * 2)),
        ("Impressions", f"{total_impr:,}", "times shown in Google", "",
         ("Impressions come before clicks, and clicks come before customers. "
          "Rising impressions with flat clicks means you're climbing but not yet high enough."),
         "Search Console", BLUE),
        ("Clicks", f"{total_clicks:,}", f"CTR {round(100*total_clicks/total_impr,1) if total_impr else 0}%", "",
         ("Real visitors from search." if total_clicks
          else "Zero clicks with impressions present is normal below page one."),
         "Search Console", GREEN if total_clicks else AMBER),
        ("Tracked keywords", tracked, "checked daily", "",
         ("Search Console averages 28 days and lags 2–3 days. Daily tracking is how you know "
          "whether yesterday's fix worked." if tracked
          else "Rank tracking not started — Serper is already connected, so this costs about $5/month."),
         "Serper" if tracked else "not started", GREEN if tracked else AMBER),
        ("Moved up", up, "keywords improved", "",
         ("Day-over-day gains." if tracked else "Starts once daily tracking runs twice."),
         "rank tracker", GREEN),
        ("Moved down", down, "keywords dropped", "",
         ("Investigate any drop of 5+ positions — usually a competitor's new page."
          if down else "Nothing lost ground."),
         "rank tracker", PINK if down else GREEN),
        ("CTR underperformers", len(ctr_gaps), "good rank, poor clicks", ctr_body,
         ("Ranking well and still not clicked means the title and description aren't selling. "
          "Cheapest fix in SEO — no new content, no new links."
          if ctr_gaps else "No obvious title/meta underperformance."),
         "computed", AMBER if ctr_gaps else GREEN),
        ("Zero-click queries", len(zero), "seen, never clicked", zero_body,
         ("Split into two causes: too low to be seen, or seen and ignored. The reason column says which."
          if zero else "Nothing is being shown and ignored."),
         "computed", AMBER if zero else GREEN),
        ("Cannibalisation", len(cannib), "queries with 2+ of your pages", cannib_body,
         ("Your own pages splitting one query's authority. Consolidate or clearly separate their intent."
          if cannib else "No self-competition detected."),
         "Search Console query×page", PINK if cannib else GREEN),
        ("Intent mix", sum(v["queries"] for v in intent.values()) if intent else 0,
         "informational / commercial / transactional", intent_body,
         (f"Commercial and transactional queries are the ones that turn into consultations. "
          f"You currently earn {intent.get('commercial',{}).get('clicks',0)} commercial clicks."
          if intent else "Fills from Search Console."),
         "computed", TEAL),
        ("Branded vs not", f"{branded.get('non_branded',0)}/{len(q)}", "non-branded queries", "",
         ("Non-branded traffic is new demand; branded traffic is people who already knew you. "
          "Early on, almost everything should be non-branded."),
         "computed", BLUE),
        ("SERP features", len(features), "feature types seen", feature_body,
         ("Featured snippets, People Also Ask and AI Overviews take clicks before the blue links. "
          "Owning them matters more every year."),
         "rank tracker", VIOLET),
        ("Markets", len(gsc.get("countries") or []), "countries showing you", country_body,
         "Your five target markets are USA, UK, Germany, Switzerland and Canada.",
         "Search Console", BLUE),
        ("Devices", len(gsc.get("devices") or []), "device split", device_body,
         "Google ranks the mobile version. If mobile impressions dominate, mobile issues are ranking issues.",
         "Search Console", BLUE),
        ("Next keywords to target", len(striking[:10]), "highest opportunity",
         _rows(striking[:10], left_fmt=lambda r: r["query"][:40],
               right_fmt=lambda r: f"+{r['potential_clicks']} clicks if top 3",
               empty="Fills once queries reach the #4–#20 band."),
         "Ordered by the clicks you'd gain reaching the top three.",
         "computed", GREEN),
    ])


# ======================================================================
#  BOARD 6 — CONTENT PERFORMANCE  (14 cards)
# ======================================================================
def board_content(ctx) -> str:
    H = _H()
    audit = ctx.get("audit") or {}
    gsc = ((ctx.get("insights") or {}).get("gsc") or {})
    ga4 = ((ctx.get("insights") or {}).get("ga4") or {})
    crawl = ctx.get("crawl") or {}
    pages = gsc.get("pages") or []
    decayed = audit.get("decay") or []
    risers = audit.get("rising") or []
    live = [r for r in crawl.get("urls", []) if r.get("status") == 200]

    zero_impr = [r for r in live if not any(
        (p.get("key") or "").rstrip("/").endswith(r["url"].split("/")[-1]) for p in pages)]
    thin = [r for r in live if r.get("words", 0) < 300]
    top = sorted(pages, key=lambda p: -p.get("clicks", 0))[:12]

    decay_body = _rows(decayed, left_fmt=lambda r: r["url"].split("/")[-1][:36] or "/",
                       right_fmt=lambda r: f"{r['change_pct']}% ({r['clicks_before']}→{r['clicks_now']})",
                       empty="No page has lost significant traffic.")
    rise_body = _rows(risers, left_fmt=lambda r: r["url"].split("/")[-1][:36] or "/",
                      right_fmt=lambda r: f"+{r['gained']} clicks",
                      empty="Needs a second window to compare.")
    top_body = _rows(top, left_fmt=lambda p: str(p.get("key", "")).split("/")[-1][:36] or "/",
                     right_fmt=lambda p: f"{p.get('clicks',0)} clicks · {p.get('impressions',0)} impr",
                     empty="No page data from Search Console yet.")
    zero_body = _rows(zero_impr, left_fmt=lambda r: r["url"].split("/")[-1][:38] or "/",
                      empty="Every page has been shown in search at least once.")
    ga4_body = _rows(ga4.get("pages") or [],
                     left_fmt=lambda p: str(p.get("pagePath", p.get("key", "")))[:38],
                     right_fmt=lambda p: f"{p.get('sessions',0)} sessions",
                     empty="No Analytics page data yet.")
    return _head("📚", "Content performance & decay",
                 f"All {len(live)} live pages measured against what search actually did with them.") + _cards([
        ("Live pages", len(live), "crawled and indexable", "",
         f"The library is {len(live)} pages. Publishing more only helps once these earn their keep.",
         "own crawler", BLUE),
        ("Pages earning clicks", len(pages), "seen in Search Console", top_body,
         (f"{len(pages)} of {len(live)} pages have search impressions."
          if pages else "No page has search data in this window yet."),
         "Search Console", _pct_color(100 * len(pages) / max(len(live), 1))),
        ("Decaying pages", len(decayed), "down more than 20%", decay_body,
         ("A page falling off a cliff used to be completely silent. These need a refresh, "
          "not a replacement." if decayed
          else "Nothing is in decline — or there isn't a second window to compare yet."),
         "Search Console comparison", PINK if decayed else GREEN),
        ("Rising pages", len(risers), "gaining clicks", rise_body,
         ("Double down on whatever these have in common." if risers
          else "Needs two comparison windows."),
         "Search Console comparison", GREEN),
        ("Zero-impression pages", len(zero_impr), "published, never shown", zero_body,
         ("Published but invisible. Usually not indexed, orphaned, or targeting a query nobody searches."
          if zero_impr else "Every page has appeared in search."),
         "crawl × Search Console", AMBER if zero_impr else GREEN),
        ("Thin pages", len(thin), "under 300 words", "",
         "Merge these into a stronger page rather than leaving them to dilute the site.",
         "own crawler", AMBER if thin else GREEN),
        ("Top pages by traffic", len(top), "ranked", top_body,
         "Your best performers. Internal links from these pass the most authority.",
         "Search Console", TEAL),
        ("Analytics top pages", len(ga4.get("pages") or []), "by sessions", ga4_body,
         "What visitors actually read after they arrive.",
         "GA4", BLUE),
        ("Refresh queue", len(decayed) + len(thin), "pages needing work",
         _rows(decayed + [{"url": r["url"], "change_pct": "thin"} for r in thin],
               left_fmt=lambda r: r["url"].split("/")[-1][:36] or "/",
               right_fmt=lambda r: str(r.get("change_pct", "")),
               empty="Nothing queued for a refresh."),
         "Refreshing an existing page beats writing a new one almost every time.",
         "computed", AMBER),
        ("Prune candidates", len(thin), "merge or remove", "",
         ("Thin pages with no impressions are pure drag — merge them into a real guide."
          if thin else "Nothing obviously worth pruning."),
         "computed", AMBER if thin else GREEN),
        ("Topic clusters", 8, "audience segments", "",
         ("Regulated, medical, e-commerce, service, freelancers, creators, B2B, business-launch. "
          "Each cluster needs its service page linked from every guide in it."),
         "site taxonomy", VIOLET),
        ("Content gaps", len(audit.get("striking") or []), "queries without a strong page", "",
         ("Every striking-distance query is a page that could be better — or a page that "
          "should exist and doesn't."),
         "computed", GREEN),
        ("Publishing cadence", "—", "posts per week", "",
         "The engine's scheduler drives this. Consistency matters more than volume.",
         "scheduler", BLUE),
        ("Refreshes shipped", len([o for o in (ctx.get("orders") or [])
                                   if o.get("code") == "decay_refresh" and o.get("status") == "done"]),
         "completed by the machine", "",
         "Refreshes the engine has already regenerated and republished.",
         "work-order log", GREEN),
    ])


# ======================================================================
#  BOARD 7 — INTERNAL LINKS  (12 cards)
# ======================================================================
def board_links(ctx) -> str:
    H = _H()
    graph = ctx.get("graph") or {}
    money = ctx.get("money") or {}
    orders = ctx.get("orders") or []
    if not graph:
        return _not_run("🔗 Internal linking & architecture", "▶ Run the first crawl", "runCrawl()")

    anchors = graph.get("anchors") or []
    top_linked = graph.get("top_linked") or []
    generic = sum(c for a, c in anchors
                  if a in ("click here", "read more", "here", "learn more", "this"))
    inserted = [o for o in orders if o.get("type") == "internal_links" and o.get("status") == "done"]

    anchor_body = _rows(anchors, left_fmt=lambda kv: kv[0][:40] or "(empty)",
                        right_fmt=lambda kv: f"{kv[1]}×", empty="No anchor text captured.")
    linked_body = _rows(top_linked, left_fmt=lambda kv: kv[0].split("/")[-1][:36] or "/",
                        right_fmt=lambda kv: f"{kv[1]} inbound", empty="No internal links found.")
    money_body = _rows(sorted((money.get("supported") or {}).items(), key=lambda kv: kv[1]),
                       left_fmt=lambda kv: kv[0].split("/")[-1][:36] or "/",
                       right_fmt=lambda kv: f"{kv[1]} inbound links",
                       empty="No service pages found in the crawl.")
    orphan_body = _rows(graph.get("orphans") or [],
                        left_fmt=lambda u: u.split("/")[-1][:38] or "/",
                        empty="Every page has at least one internal link pointing to it.")
    inserted_body = _rows(inserted, left_fmt=lambda o: o.get("result", "")[:56],
                          right_fmt=lambda o: (o.get("done_at") or "")[:10],
                          empty="No links inserted automatically yet.")
    return _head("🔗", "Internal linking & architecture",
                 "You wrote the guides by hand — nothing ever verified they point at the pages that sell.") + _cards([
        ("Internal links", graph.get("total_internal_links", 0), "total across the site", "",
         "Internal links are the only ranking factor you control completely.",
         "link graph", BLUE),
        ("Average inbound", graph.get("avg_inbound", 0), "links per page", "",
         "Pages with no inbound links are invisible; pages with many get crawled most.",
         "link graph", _pct_color(min(100, graph.get("avg_inbound", 0) * 25))),
        ("Orphan pages", graph.get("orphan_count", 0), "nothing links here", orphan_body,
         ("The fixer links these automatically when it finds a natural anchor phrase."
          if graph.get("orphan_count") else "No orphans."),
         "link graph", PINK if graph.get("orphan_count") else GREEN),
        ("Most-linked pages", len(top_linked), "by inbound count", linked_body,
         "These hold the most internal authority — link OUT from them to what you want ranking.",
         "link graph", TEAL),
        ("Anchor text spread", len(anchors), "distinct anchors", anchor_body,
         ("Descriptive anchors tell Google what the target page is about."),
         "link graph", VIOLET),
        ("Generic anchors", generic, "\"click here\" / \"read more\"", "",
         ("Generic anchor text passes no topical signal — it's a wasted link."
          if generic else "No generic anchor text found."),
         "link graph", AMBER if generic else GREEN),
        ("Click depth", len(graph.get("depth_spread") or {}), "depth levels",
         H._bars([(("unreachable" if k == "unreachable" else f"{k} clicks"), v)
                  for k, v in sorted((graph.get("depth_spread") or {}).items())], VIOLET)
         if graph.get("depth_spread") else "",
         "Anything more than three clicks from the homepage gets crawled rarely.",
         "link graph", BLUE),
        ("Money-page support", f"{money.get('coverage_pct', 0)}%", "of articles link to a service page",
         money_body,
         (f"{money.get('articles_linking_to_money',0)} of {money.get('articles',0)} articles point at "
          "a page that can actually sell. Every guide should."),
         "link graph", _pct_color(money.get("coverage_pct", 0))),
        ("Weakest money pages", len(money.get("weakest") or []), "least supported",
         _rows(money.get("weakest") or [], left_fmt=lambda kv: kv[0].split("/")[-1][:36],
               right_fmt=lambda kv: f"{kv[1]} inbound",
               empty="No service pages in the crawl."),
         "These are the pages that convert — and the ones getting the least internal support.",
         "computed", AMBER),
        ("Broken internal links", graph.get("broken_count", 0), "point to nothing", "",
         ("Each dead-ends a reader and wastes crawl budget."
          if graph.get("broken_count") else "No broken links."),
         "link graph", PINK if graph.get("broken_count") else GREEN),
        ("Links inserted", len(inserted), "added automatically", inserted_body,
         "The fixer only ever links a phrase you already wrote — it never inserts new sentences.",
         "SEO fixer", GREEN),
        ("Cluster integrity", 8, "segments to keep linked", "",
         ("Each of your eight audience segments should be a closed loop: guides → service page → "
          "sibling guides. Gaps here leak authority out of the cluster."),
         "site taxonomy", VIOLET),
    ])


# ======================================================================
#  BOARD 8 — OFF-PAGE  (20 cards)
# ======================================================================
def board_offpage(ctx) -> str:
    H = _H()
    prof = ctx.get("offpage") or {}
    prospects = ctx.get("prospects") or []
    gap = ctx.get("link_gap") or []
    stats = ctx.get("prospect_stats") or {}
    connected = prof.get("connected")

    def q(v):
        return v if connected else "—"

    anchors = prof.get("anchors") or []
    ref = prof.get("referring_list") or []
    by_kind = stats.get("by_kind") or {}

    ref_body = _rows(ref, left_fmt=lambda d: d.get("domain", "")[:38],
                     right_fmt=lambda d: f"DR {d.get('rank',0)} · {d.get('backlinks',0)} links",
                     empty=prof.get("reason", "Connect DataForSEO to see referring domains."))
    anchor_body = _rows(anchors, left_fmt=lambda kv: kv[0][:38],
                        right_fmt=lambda kv: f"{kv[1]}×",
                        empty="No anchor data without a backlink source.")
    gap_body = _rows(gap, left_fmt=lambda g: g["domain"][:36],
                     right_fmt=lambda g: f"links to {g['rivals_linked']} rival(s)",
                     empty="Needs your profile plus at least one rival profile.")
    pipe_body = _rows([(k, v) for k, v in (stats.get("by_status") or {}).items()],
                      left_fmt=lambda kv: kv[0].replace("_", " ").title(),
                      right_fmt=lambda kv: str(kv[1]),
                      empty="No prospects yet — run the prospector.")
    await_body = _rows([p for p in prospects if p.get("status") == "awaiting_approval"],
                       left_fmt=lambda p: f"{p.get('domain','')} — {p.get('subject','')[:38]}",
                       right_fmt=lambda p: p.get("opportunity", ""),
                       empty="No pitches waiting. Nothing is ever sent without your click.")
    kind_body = _rows(sorted(by_kind.items(), key=lambda kv: -kv[1]),
                      left_fmt=lambda kv: kv[0].replace("_", " ").title(),
                      right_fmt=lambda kv: f"{kv[1]} prospects",
                      empty="No prospects sourced yet.")
    return _head("🌐", "Off-page, backlinks & digital PR",
                 "The half of SEO this dashboard had nothing for. Prospecting works today; "
                 "your own backlink profile needs DataForSEO — Google exposes no link API.") + _cards([
        ("Referring domains", q(prof.get("referring_domains", 0)), "unique linking sites", ref_body,
         (f"{prof.get('referring_domains',0)} distinct domains link to you. Domains matter far "
          "more than raw link count." if connected else prof.get("reason", "Not connected.")),
         "DataForSEO" if connected else "not connected", TEAL if connected else AMBER),
        ("Total backlinks", q(prof.get("backlinks", 0)), "individual links", "",
         ("Many links from one site count roughly once." if connected
          else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", BLUE),
        ("Domain rank", q(prof.get("rank", 0)), "authority estimate", "",
         ("A rough authority score. Direction over months matters more than the number."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", VIOLET),
        ("Dofollow share", f"{prof.get('dofollow_pct', 0)}%" if connected else "—",
         "links passing authority", "",
         ("Nofollow links still bring traffic and trust; they just don't pass ranking signal."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", BLUE),
        ("Lost links", q(len(prof.get("lost") or [])), "disappeared", "",
         ("A lost link from a strong domain is worth chasing — often just a page redesign."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", AMBER),
        ("Broken backlinks", q(prof.get("broken_backlinks", 0)), "pointing at dead pages", "",
         ("Someone linked to a URL that now 404s. Redirect it and you recover the authority free."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", AMBER),
        ("Toxic links", q(len(prof.get("toxic") or [])), "low-quality sources", "",
         ("Only worth disavowing if there are many and they're clearly spam."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", PINK if prof.get("toxic") else GREEN),
        ("Anchor mix", q(len(anchors)), "distinct anchors", anchor_body,
         ("A natural profile is mostly brand and URL anchors. Heavy exact-match looks bought."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", VIOLET),
        ("Referring IPs", q(prof.get("referring_ips", 0)), "distinct networks", "",
         ("Many links from one IP block is a footprint of a link network."
          if connected else "Needs a backlink source."),
         "DataForSEO" if connected else "not connected", BLUE),
        ("Link gap", len(gap), "domains linking to rivals, not you", gap_body,
         ("The warmest list in off-page: they already link to someone exactly like you."
          if gap else "Scan a rival's profile to build this list."),
         "computed", GREEN if gap else AMBER),
        ("Prospect pipeline", stats.get("total", 0), "found → contacted → placed", pipe_body,
         "Every prospect the engine has sourced, and where each one stands.",
         "Serper prospecting", TEAL),
        ("Awaiting your approval", stats.get("awaiting_approval", 0), "pitches drafted", await_body,
         ("Nothing is sent automatically. Mass link-begging burns a domain, and yours was "
          "just warmed up."),
         "link pitch agent", AMBER if stats.get("awaiting_approval") else GREEN),
        ("Contacted", stats.get("contacted", 0), "pitches sent", "",
         "Sent through the same warmed mailbox and suppression rules as your cold outreach.",
         "outreach engine", BLUE),
        ("Replies", stats.get("replied", 0), "responded", "",
         ("Replies land in the same inbox the reply agent already reads."),
         "IMAP reply agent", GREEN),
        ("Links placed", stats.get("placed", 0), "verified live", "",
         ("Verified by re-crawling the page and looking for your link — not by taking their word."),
         "placement verifier", GREEN),
        ("Win rate", f"{stats.get('win_rate', 0)}%", "placed ÷ contacted", "",
         ("Anything above 5% for cold link outreach is healthy. Below that, the pitch or the "
          "targeting is off."),
         "computed", _pct_color(stats.get("win_rate", 0), good=10, ok=4)),
        ("Opportunity types", len(by_kind), "prospect sources", kind_body,
         ("Resource pages, guest posts, unlinked mentions and broken-link rebuilds — "
          "each needs a different pitch."),
         "prospecting", VIOLET),
        ("Unlinked mentions", by_kind.get("unlinked_mention", 0), "name you without a link", "",
         ("The easiest link there is: they already wrote about you, they just forgot the link."),
         "Serper + fetch", GREEN if by_kind.get("unlinked_mention") else AMBER),
        ("Guest-post targets", by_kind.get("guest_post", 0), "accept contributions", "",
         "Sites that publicly invite contributors — a real editorial link, not a paid one.",
         "Serper", BLUE),
        ("Digital PR angles", len(ctx.get("audit", {}).get("striking") or []), "data stories you own", "",
         ("Your own Search Console data is a story nobody else has. Original data earns links "
          "that pitches never will."),
         "computed", VIOLET),
    ])


# ======================================================================
#  BOARD 9 — AEO / GEO  (12 cards)
# ======================================================================
def board_aeo(ctx) -> str:
    H = _H()
    aeo = ctx.get("aeo") or {}
    quot = ctx.get("quotable") or {}
    if not aeo:
        return (_head("🤖", "AEO / GEO — AI answers",
                      "Whether AI engines name you when a buyer asks. You measure this for "
                      "competitors already; this measures it for you.")
                + _not_run("AI-visibility probe has not run", "▶ Probe AI answers", "runAeo()"))

    eng = aeo.get("engines") or {}
    sov = aeo.get("share_of_voice") or {}
    gaps = aeo.get("gaps") or []
    you = sov.get("_you", 0)
    rivals = {k: v for k, v in sov.items() if k != "_you"}

    sov_body = _rows(sorted(sov.items(), key=lambda kv: -kv[1]),
                     left_fmt=lambda kv: "You" if kv[0] == "_you" else kv[0],
                     right_fmt=lambda kv: f"{kv[1]} answers",
                     empty="No mentions recorded.")
    gap_body = _rows(gaps, left_fmt=lambda g: g["prompt"][:44],
                     right_fmt=lambda g: ", ".join(g.get("rivals", []))[:28] or "nobody named",
                     empty="No prompt names a rival instead of you.")
    eng_body = _rows(list(eng.items()),
                     left_fmt=lambda kv: kv[0].replace("_", " ").title(),
                     right_fmt=lambda kv: ("connected" if kv[1].get("connected") else "not connected"),
                     empty="")
    weak_body = _rows(quot.get("weakest") or [],
                      left_fmt=lambda r: r["url"].split("/")[-1][:38] or "/",
                      right_fmt=lambda r: f"{r['question_headings']} question headings",
                      empty="Every page has quotable question headings.")
    return _head("🤖", "AEO / GEO — AI answers",
                 "Buyers ask AI before they ask Google. This measures whether the answer says your name.") + _cards([
        ("AEO score", aeo.get("score", 0), "of 100", "",
         f"Blend of AI mentions, snippet ownership and organic presence across "
         f"{aeo.get('prompts_tested', 0)} buyer-intent prompts.",
         "Claude + Serper", _pct_color(aeo.get("score", 0))),
        ("Mention rate", f"{aeo.get('mention_rate', 0)}%", "of AI answers name you", "",
         (f"You were named in {you} of {aeo.get('prompts_tested',0)} answers to questions a "
          "real buyer would ask."),
         "Claude probe", _pct_color(aeo.get("mention_rate", 0), good=30, ok=10)),
        ("Prompts tested", aeo.get("prompts_tested", 0), "buyer-intent questions", "",
         "Ten general plus one per audience segment — the questions that precede a purchase.",
         "AEO engine", BLUE),
        ("Engines probed", len(eng), "AI surfaces", eng_body,
         ("Claude runs on your own key. Google AI surfaces come through Serper. OpenAI and "
          "Perplexity need their own keys — they're reported as not connected, never guessed."),
         "AEO engine", VIOLET),
        ("Share of voice", len(rivals) + (1 if you else 0), "brands named", sov_body,
         (f"You: {you}. " + (f"Most-named rival: {max(rivals, key=rivals.get)}."
                             if rivals else "No rival was named either.")),
         "computed", TEAL),
        ("Answer gaps", len(gaps), "prompts naming a rival, not you", gap_body,
         ("Each gap is a page you could write that would put you in that answer."
          if gaps else "No rival is taking an answer you should own."),
         "computed", PINK if gaps else GREEN),
        ("Featured snippets", (eng.get("google_ai") or {}).get("snippets", 0), "owned", "",
         ("The snippet is what voice assistants read aloud and what AI Overviews quote."),
         "Serper", GREEN if (eng.get("google_ai") or {}).get("snippets") else AMBER),
        ("Ranked on the SERP", (eng.get("google_ai") or {}).get("ranked", 0), "of the tested prompts", "",
         ("AI Overviews draw heavily on the top organic results. Ranking is still the entry ticket."),
         "Serper", BLUE),
        ("Quotable pages", f"{quot.get('quotable', 0)}/{quot.get('pages', 0)}",
         "2+ question headings", weak_body,
         ("AI engines quote a heading that asks and a paragraph that answers. Vague headings "
          "never get cited, however good the prose is."),
         "own crawler", _pct_color(quot.get("quotable_pct", 0))),
        ("FAQ schema", f"{quot.get('faq_schema', 0)}/{quot.get('pages', 0)}", "pages marked up", "",
         ("FAQPage markup is the most direct way to hand an AI engine a ready-made answer. "
          "The fixer injects it automatically."),
         "own crawler", _pct_color(quot.get("faq_pct", 0))),
        ("llms.txt", "ready" if ctx.get("llms_txt") else "—", "AI crawler manifest", "",
         ("A single file telling AI crawlers what your site is and which pages matter. "
          "Free, one upload, generated from your live crawl."),
         "AEO engine", GREEN if ctx.get("llms_txt") else AMBER),
        ("AEO fix queue", len(quot.get("weakest") or []), "pages to make quotable", "",
         ("Rewrite these H2s as the questions your buyers actually ask, then answer in the "
          "first sentence underneath."),
         "computed", AMBER if quot.get("weakest") else GREEN),
    ])


# ======================================================================
#  BOARD 10 — LOCAL  (10 cards)
# ======================================================================
def board_local(ctx) -> str:
    H = _H()
    local = ctx.get("local") or {}
    markets = ["United States", "United Kingdom", "Germany", "Switzerland", "Canada"]
    grid_rows = local.get("grid") or []
    gbp = local.get("gbp") or {}
    connected = bool(gbp.get("connected"))

    grid_body = _rows(grid_rows, left_fmt=lambda r: f"{r.get('market','')} · {r.get('query','')[:26]}",
                      right_fmt=lambda r: (f"#{r.get('position')}" if r.get("position") else "not in top 50"),
                      empty="Run a local rank check to fill this — Serper Maps is already connected.")
    return _head("📍", "Local & multi-market",
                 "Five target markets. Local intent converts hardest — and it's the cheapest to win.") + _cards([
        ("Target markets", len(markets), "USA · UK · DE · CH · CA",
         _rows(markets, left_fmt=lambda m: m, empty=""),
         "Your ICP spans five markets, each with its own SERP and its own competitors.",
         "ICP definition", BLUE),
        ("Local rank checks", len(grid_rows), "market × query", grid_body,
         ("Serper Maps is connected, so this costs about a cent per check."
          if not grid_rows else "Where you appear in the local pack, per market."),
         "Serper Maps", TEAL if grid_rows else AMBER),
        ("Google Business Profile", "connected" if connected else "—", "reviews & posts", "",
         (gbp.get("reason") or
          "GBP needs its own OAuth — the service account cannot act on a business profile. "
          "Same wall as Google Ads; local rank tracking works without it."),
         "GBP API" if connected else "not connected", GREEN if connected else AMBER),
        ("Reviews", gbp.get("review_count", "—"), "total", "",
         ("Review count and recency are among the strongest local ranking factors."
          if connected else "Needs the Business Profile connection."),
         "GBP API" if connected else "not connected", BLUE),
        ("Average rating", gbp.get("rating", "—"), "stars", "",
         ("Rating drives both ranking and click-through in the local pack."
          if connected else "Needs the Business Profile connection."),
         "GBP API" if connected else "not connected", BLUE),
        ("Unanswered reviews", gbp.get("unanswered", "—"), "awaiting a reply", "",
         ("Replying to every review is a confirmed local ranking signal — and it's free."
          if connected else "Needs the Business Profile connection."),
         "GBP API" if connected else "not connected", AMBER),
        ("NAP consistency", "—", "name/address/phone across the web", "",
         ("Your address is a Wyoming registered-agent address, so citation building matters "
          "less than for a physical local business — but it must be consistent everywhere."),
         "manual review", BLUE),
        ("Local competitors", len(local.get("competitors") or []), "in the map pack",
         _rows(local.get("competitors") or [],
               left_fmt=lambda c: c.get("name", "")[:36],
               right_fmt=lambda c: f"★{c.get('rating',0)} · {c.get('reviews',0)} reviews",
               empty="Run a Maps scan to see who holds the local pack."),
         "Maps results also feed your lead machine — the same scan does both jobs.",
         "Serper Maps", VIOLET),
        ("Market opportunity", len(markets), "ranked by gap", "",
         ("Germany and Switzerland are underserved for German-language automation content — "
          "and you write German. That's the widest open door of the five."),
         "computed", GREEN),
        ("Service-area pages", "—", "market-specific landing pages", "",
         ("One page per market, in that market's language, is how you compete locally without "
          "a physical office in each."),
         "site structure", BLUE),
    ])


# ======================================================================
#  BOARD 12 — WORK ORDERS  (14 cards)
# ======================================================================
def board_work(ctx) -> str:
    H = _H()
    orders = ctx.get("orders") or []
    stats = ctx.get("order_stats") or {}
    status = ctx.get("status") or {}
    runs = ctx.get("engine_runs") or {}
    meters = ctx.get("meters") or {}

    open_o = [o for o in orders if o.get("status") == "open"]
    approve = [o for o in orders if o.get("status") == "awaiting_approval"]
    done = [o for o in orders if o.get("status") == "done"]
    failed = [o for o in orders if o.get("status") == "failed"]
    resolved = [o for o in orders if o.get("status") == "resolved"]

    ENGINES = [("seo_crawler", "E1 Crawler"), ("seo_index_inspect", "E2 Index Inspector"),
               ("seo_pagespeed", "E3 Speed & CWV"), ("seo_indexnow", "E4 Index Pusher"),
               ("google_gsc_ga4", "E5 Striking/Decay (GSC)"), ("seo_rank_tracker", "E6 Rank Tracker"),
               ("wordpress_publish", "E7/E8/E9 Fixer (WP write)"),
               ("claude_api", "E10 Content Refresh"), ("seo_backlinks", "E11 Backlinks"),
               ("serper_search", "E12 Link Acquisition"), ("seo_gbp", "E13 Local/GBP"),
               ("claude_api", "E14 AEO Probe")]
    eng_rows = [(label, status.get(key, False)) for key, label in ENGINES]
    live = sum(1 for _, on in eng_rows if on)
    eng_body = _rows(eng_rows, left_fmt=lambda kv: kv[0],
                     right_fmt=lambda kv: "live" if kv[1] else "needs a key")
    blocked = [(l, k) for k, l in ENGINES if not status.get(k, False)]
    blocked_body = _rows(blocked, left_fmt=lambda kv: kv[0],
                         right_fmt=lambda kv: kv[1],
                         empty="Every SEO engine is wired.")
    queue_body = _rows(sorted(open_o, key=lambda o: -o.get("priority", 0)),
                       left_fmt=lambda o: f"[{o.get('severity','')[:4]}] {o.get('fix') or o.get('code')}",
                       right_fmt=lambda o: o.get("url", "").split("/")[-1][:24] or "site",
                       limit=15, empty="Queue is empty.")
    approve_body = _rows(approve,
                         left_fmt=lambda o: (o.get("extra", {}).get("proposal", {}).get("after")
                                             or o.get("result", ""))[:52],
                         right_fmt=lambda o: o.get("url", "").split("/")[-1][:20],
                         empty="Nothing waiting on you.")
    done_body = _rows(sorted(done, key=lambda o: o.get("done_at") or "", reverse=True),
                      left_fmt=lambda o: f"✓ {o.get('result','')[:52]}",
                      right_fmt=lambda o: (o.get("done_at") or "")[:10],
                      empty="No fixes applied yet.")
    type_body = _rows(sorted((stats.get("by_type") or {}).items(), key=lambda kv: -kv[1]),
                      left_fmt=lambda kv: kv[0].replace("_", " ").title(),
                      right_fmt=lambda kv: str(kv[1]), empty="No work orders yet.")
    fail_body = _rows(failed, left_fmt=lambda o: f"{o.get('code')} — {o.get('result','')[:40]}",
                      right_fmt=lambda o: o.get("url", "").split("/")[-1][:20],
                      empty="Nothing failed.")
    run_body = _rows(sorted(runs.items()), left_fmt=lambda kv: kv[0],
                     right_fmt=lambda kv: str(kv[1])[:19].replace("T", " "),
                     empty="No engine has run yet.")
    seo_spend = sum(v for k, v in (meters or {}).items()
                    if any(s in str(k) for s in ("serper", "dataforseo", "seo")))

    return _head("🛠", "SEO automation & work orders",
                 "Every finding becomes a tracked job. Markup and links apply themselves; "
                 "anything a visitor reads waits for you.") + _cards([
        ("Open work orders", len(open_o), "queued", queue_body,
         ("Ranked by impact ÷ effort, so the top of this list is always the best next hour of work."
          if open_o else "Nothing outstanding."),
         "work-order engine", AMBER if open_o else GREEN),
        ("Auto-ready", stats.get("auto_ready", 0), "machine can fix now", "",
         ("Schema, alt text, internal links and OG tags — no human words involved, so no approval needed."),
         "work-order engine", GREEN),
        ("Awaiting approval", len(approve), "copy changes drafted", approve_body,
         ("Titles, metas and body rewrites always stop here. That was your call, and it's the right one."),
         "SEO fixer", AMBER if approve else GREEN),
        ("Completed", len(done), "fixes applied", done_body,
         "Each records what changed, so anything can be traced or reversed.",
         "work-order log", GREEN),
        ("Auto-resolved", len(resolved), "fixed themselves", "",
         ("Issues that stopped appearing between crawls — usually because a fix upstream "
          "corrected them."),
         "work-order engine", GREEN),
        ("Failed", len(failed), "could not be applied", fail_body,
         ("Most common cause: WordPress strips <script> tags unless the API user has "
          "unfiltered_html." if failed else "Nothing failed."),
         "work-order log", PINK if failed else GREEN),
        ("By type", len(stats.get("by_type") or {}), "work categories", type_body,
         "Where the work actually sits — technical, on-page, schema, links or content.",
         "work-order engine", VIOLET),
        ("SEO engines live", f"{live}/{len(ENGINES)}", "of 14", eng_body,
         (f"{live} engines are wired and running. The rest need a key — each says which."),
         "connector status", _pct_color(100 * live / len(ENGINES))),
        ("Blocked on a key", len(blocked), "waiting on you", blocked_body,
         ("Each of these needs one credential or one browser click. Nothing is broken — "
          "just unwired." if blocked else "Nothing blocked."),
         "connector status", AMBER if blocked else GREEN),
        ("Last run per engine", len(runs), "timestamps", run_body,
         "If an engine hasn't run recently, its board is showing stale numbers.",
         "scheduler", BLUE),
        ("SEO API spend", f"${seo_spend:.2f}", "this month", "",
         ("Crawling, index inspection, speed checks and IndexNow all cost nothing. "
          "Only rank tracking, backlinks and AI probes spend."),
         "cost meter", GREEN),
        ("Cost per fix", f"${(seo_spend/max(len(done),1)):.3f}" if done else "—",
         "spend ÷ fixes applied", "",
         ("Most fixes are pure code, so the average stays near zero." if done
          else "Fills once fixes are applied."),
         "computed", GREEN),
        ("Forecast", "—", "projected clicks in 90 days", "",
         ("Deliberately blank. A forecast needs at least two months of your own trend data — "
          "anything sooner would be a guess dressed up as a number."),
         "not enough history", BLUE),
        ("Wire diagnostics", len(blocked), "wires down", blocked_body,
         ("Plain English, per wire: what's down, and what it costs you while it stays down."),
         "connector status", AMBER if blocked else GREEN),
    ])


# ======================================================================
#  ASSEMBLY
# ======================================================================
def seo_pages(ctx) -> dict:
    """-> {page_id: html}. The dashboard drops these straight into its PAGES."""
    return {
        "seocmd": board_command(ctx),
        "seotech": board_technical(ctx) + board_indexing(ctx),
        "seoonpage": board_onpage(ctx) + board_links(ctx),
        "seokw": board_keywords(ctx) + board_content(ctx) + board_aeo(ctx),
        "seooff": board_offpage(ctx) + board_local(ctx),
        "seowork": board_work(ctx),
    }


CARD_COUNTS = {"command": 12, "technical": 18, "indexing": 12, "on_page": 16,
               "keywords": 18, "content": 14, "internal_links": 12, "off_page": 20,
               "aeo": 12, "local": 10, "work_orders": 14}
TOTAL_CARDS = sum(CARD_COUNTS.values())


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import re as _re
    import content_engine_seo as SEO
    import content_engine_crawler as CR
    import content_engine_workorders as WO

    crawl = {"base": "https://x.com", "count": 3, "urls": [
        {"url": "https://x.com", "status": 200, "title": "Home | Anthropos", "title_len": 16,
         "meta_desc": "d" * 90, "meta_len": 90, "h1": ["Home"], "h2": ["What is this?"],
         "words": 800, "images": 2, "images_no_alt": 1, "schema_types": ["Organization"],
         "og_ok": True, "canonical": "https://x.com", "internal_links": ["https://x.com/guide-a"],
         "anchors": [("https://x.com/guide-a", "automation guide")], "heading_order_ok": True,
         "robots": "", "depth": 0, "ms": 400, "outbound_links": []},
        {"url": "https://x.com/guide-a", "status": 200, "title": "T" * 80, "title_len": 80,
         "meta_desc": "", "meta_len": 0, "h1": [], "h2": ["What is the problem?", "How does it work?"],
         "words": 120, "images": 1, "images_no_alt": 1, "schema_types": [], "og_ok": False,
         "canonical": "", "internal_links": [], "anchors": [], "heading_order_ok": False,
         "robots": "", "depth": 1, "ms": 3000, "outbound_links": []},
        {"url": "https://x.com/services/regulated", "status": 404, "title": "", "title_len": 0,
         "meta_desc": "", "meta_len": 0, "h1": [], "h2": [], "words": 0, "images": 0,
         "images_no_alt": 0, "schema_types": [], "og_ok": False, "canonical": "",
         "internal_links": [], "anchors": [], "heading_order_ok": True, "robots": "",
         "depth": 99, "ms": 100, "outbound_links": []}]}
    graph = CR.link_graph(crawl)
    money = CR.money_page_support(crawl, graph)
    gsc = {"queries": [{"key": "ai automation law firm", "position": 6.2, "impressions": 400,
                        "clicks": 3, "ctr": 0.75},
                       {"key": "anthropos", "position": 1.2, "impressions": 50, "clicks": 20, "ctr": 40}],
           "pages": [{"key": "https://x.com/guide-a", "clicks": 3, "impressions": 400}],
           "countries": [{"key": "usa", "impressions": 300, "clicks": 2}],
           "devices": [{"key": "mobile", "impressions": 250}]}
    audit = SEO.full_audit(crawl=crawl, graph=graph, gsc=gsc,
                           gsc_prev_pages=[{"key": "https://x.com/guide-a", "clicks": 40}],
                           query_page=[{"keys": ["dup q", "/a"], "impressions": 50, "clicks": 1, "position": 8},
                                       {"keys": ["dup q", "/b"], "impressions": 30, "clicks": 0, "position": 15}])
    orders = WO.from_audit(audit)
    orders[0]["status"] = "done"; orders[0]["result"] = "schema injected"; orders[0]["done_at"] = "2026-07-30T10:00:00"

    ctx = {"crawl": crawl, "graph": graph, "money": money, "audit": audit,
           "scores": audit["scores"], "orders": orders, "order_stats": WO.stats(orders),
           "insights": {"gsc": gsc, "ga4": {"totals": {"sessions": 8},
                                            "pages": [{"pagePath": "/guide-a", "sessions": 5}]}},
           "inspect": {"https://x.com": {"verdict": "PASS", "coverageState": "Submitted and indexed",
                                         "mobileUsability": "PASS", "richResults": "PASS",
                                         "lastCrawlTime": "2026-07-28T00:00:00Z",
                                         "googleCanonical": "https://x.com", "userCanonical": "https://x.com"},
                       "https://x.com/guide-a": {"verdict": "NEUTRAL",
                                                 "coverageState": "Crawled - currently not indexed",
                                                 "googleCanonical": "https://x.com/other",
                                                 "userCanonical": "https://x.com/guide-a"}},
           "speed": [{"url": "https://x.com", "performance": 78, "lcp_ms": 2100, "cls": 0.02}],
           "aeo": {"score": 40, "mention_rate": 50.0, "prompts_tested": 2,
                   "engines": {"claude": {"connected": True, "mentions": 1},
                               "google_ai": {"connected": True, "snippets": 0, "ranked": 1},
                               "openai": {"connected": False}, "perplexity": {"connected": False}},
                   "share_of_voice": {"_you": 1, "pricefy.io": 1},
                   "gaps": [{"prompt": "best automation agency", "rivals": ["pricefy.io"]}]},
           "quotable": {"pages": 2, "quotable": 1, "quotable_pct": 50.0, "faq_schema": 0,
                        "faq_pct": 0.0, "weakest": [{"url": "https://x.com", "question_headings": 1}]},
           "llms_txt": "# Anthropos",
           "offpage": {"connected": False, "reason": "DataForSEO not connected — set DATAFORSEO_LOGIN"},
           "prospects": [{"domain": "a.com", "status": "awaiting_approval", "subject": "Quick note",
                          "opportunity": "resource_page"}],
           "prospect_stats": {"total": 1, "by_status": {"awaiting_approval": 1},
                              "by_kind": {"resource_page": 1}, "awaiting_approval": 1,
                              "contacted": 0, "replied": 0, "placed": 0, "win_rate": 0},
           "link_gap": [], "local": {}, "indexnow": {},
           "status": {"seo_crawler": True, "google_gsc_ga4": True, "serper_search": True,
                      "claude_api": True, "wordpress_publish": True, "seo_pagespeed": True,
                      "seo_backlinks": False, "seo_gbp": False, "seo_indexnow": False,
                      "seo_index_inspect": True, "seo_rank_tracker": True},
           "engine_runs": {"crawl": "2026-07-30T09:00:00"}, "meters": {"serper": 1.25},
           "ranks": [{"query": "ai automation law firm", "delta": 2, "features": ["paa"]}]}

    pages = seo_pages(ctx)
    assert set(pages) == {"seocmd", "seotech", "seoonpage", "seokw", "seooff", "seowork"}, list(pages)
    html = "".join(pages.values())

    counted = html.count("<div class='card'>")
    assert counted == TOTAL_CARDS, f"expected {TOTAL_CARDS} cards, rendered {counted}"

    # no board may render an unformatted placeholder, a None, or a raw dict
    for bad in ("None", "{}", "{'", "[{"):
        assert bad not in html, f"raw {bad} leaked into the HTML"
    assert not _re.search(r"\b(nan|NaN|inf)\b", html), "a non-finite number reached the UI"
    assert html.count("💡") >= TOTAL_CARDS * 0.85, "most cards must carry a qualitative read"
    # honest degradation, not fake numbers
    assert "DataForSEO not connected" in html, "must state WHY off-page is empty"
    assert "not connected" in html and "—" in html
    # every board rendered its header
    for icon in ("🧭", "🔧", "📇", "📄", "🔑", "📚", "🔗", "🌐", "🤖", "📍", "🛠"):
        assert icon in html, f"board {icon} missing"
    print(f"seo_boards self-check OK — 11 boards, {counted} cards rendered, "
          f"{html.count('💡')} qualitative reads, honest empty states")
