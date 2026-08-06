"""
content_engine_vx2_seo.py
============================================================================
THE SEO AUDIT ENVIRONMENT. Ten subsections, one grammar: find the problem,
read what it costs, press the thing that repairs it.

WHY THIS REPLACES THE CARD GRID
  The old SEO section reported. It told you a score was 96 and left you to
  work out which of 2,294 cards to act on. An audit tool does the opposite:
  it leads with the list of what is wrong, sorted by what it costs, and puts
  the repair on the same row as the problem.

THE ONE RULE THAT MATTERS HERE
  A button's appearance is decided by what it is ALLOWED to do, never by what
  it is about. There are exactly four action classes and they never share a
  look, so a click can never surprise you:

    NOW      it repairs immediately and nothing a reader sees changes
    BODY     it repairs immediately and DOES edit the page a reader sees
    DRAFT    it writes a fix and waits for you
    MANUAL   no button, because no button here could honestly work

  The class comes from content_engine_workorders, which is also what the
  scheduler obeys. One vocabulary: the screen cannot promise a power the
  engine does not have.
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_workorders as WO

# ---------------------------------------------------------------------------
# THE 33 PROBLEMS, IN WORDS
# ---------------------------------------------------------------------------
# Every code the engine can detect, with what it costs in plain language. An
# issue row with no explanation is the "machanical answer" problem again: a
# label that names a thing without telling you why you should care.
EXPLAIN = {
    # --- schema -----------------------------------------------------------
    "schema_missing": (
        "Search engines and AI assistants read structured data to understand "
        "what a page IS. Without it they guess, and a guess rarely wins a "
        "rich result or an AI citation."),
    # --- on page ----------------------------------------------------------
    "img_alt_missing": (
        "An image with no alt text is invisible to search, to screen readers "
        "and to image search traffic. It is also an accessibility failure."),
    "og_missing": (
        "With no Open Graph tags, anyone sharing this page on LinkedIn or "
        "WhatsApp posts a blank grey box instead of your headline and image. "
        "Shares get far fewer clicks."),
    "h1_missing": (
        "The H1 is the strongest on-page signal of what a page is about. A "
        "page without one makes search engines fall back to guessing from "
        "the title tag or the first heading they find."),
    "h1_multiple": (
        "Several H1s on one page split the topic signal. Search engines "
        "cannot tell which one is the subject, so none of them counts fully."),
    "heading_order": (
        "Headings that skip levels (H2 straight to H4) break the document "
        "outline. Search engines and screen readers both use that outline to "
        "understand structure, so the page reads as less organised."),
    # --- internal links ---------------------------------------------------
    "few_internal_links": (
        "A page with almost no internal links receives almost no authority "
        "from the rest of your site. It ranks on its own strength alone."),
    "orphan_page": (
        "Nothing on your site links to this page. Search engines can only "
        "find it through the sitemap, which they treat as a much weaker "
        "signal. Readers will never stumble on it at all."),
    # --- title ------------------------------------------------------------
    "title_missing": (
        "With no title tag, search engines write one for you from the page "
        "content. You lose control of the single most clicked line in the "
        "search result."),
    "title_short": (
        "A very short title wastes the space you are given. Room that could "
        "carry the keyword and a reason to click is simply left empty."),
    "title_long": (
        "Titles past about 60 characters get cut off with an ellipsis. The "
        "end of your sentence, often the persuasive part, never gets read."),
    "title_duplicate": (
        "Two pages with the same title compete with each other. Search "
        "engines pick one and suppress the other, so you lose a result you "
        "already earned."),
    "ctr_gap": (
        "This page ranks well but far fewer people click it than normally "
        "click that position. The ranking is done; the title and description "
        "are what is failing."),
    # --- meta -------------------------------------------------------------
    "meta_missing": (
        "With no meta description, search engines paste an arbitrary sentence "
        "from the page. You lose the one line of sales copy you are given "
        "underneath every result."),
    "meta_short": (
        "A very short description leaves most of the available space blank "
        "next to competitors who used all of theirs."),
    "meta_long": (
        "Descriptions past about 155 characters are truncated. Your call to "
        "action is usually what gets cut."),
    "meta_duplicate": (
        "Identical descriptions across pages tell a reader the results are "
        "interchangeable, so they pick whichever is first, which may not be "
        "you."),
    # --- content ----------------------------------------------------------
    "thin_content": (
        "There is not enough on this page to answer the question it targets. "
        "Thin pages rarely rank, and in numbers they drag down how the whole "
        "site is judged."),
    "decay_refresh": (
        "This page used to bring traffic and is now falling. Decay is usually "
        "a fresher competitor rather than a penalty, and a genuine update "
        "normally recovers it."),
    "cannibalization": (
        "Two of your own pages target the same search. They split the clicks "
        "and the links between them, so neither reaches the position one "
        "merged page would have held."),
    # --- indexing ---------------------------------------------------------
    "not_indexed": (
        "This page is not in the index. It cannot receive a single visit from "
        "search, no matter how good it is."),
    "indexnow_pending": (
        "This page has changed and search engines have not been told. "
        "IndexNow notifies them in seconds instead of waiting for a crawl "
        "that may take weeks."),
    "canonical_missing": (
        "Without a canonical tag, any URL variation (tracking parameters, a "
        "trailing slash) can be treated as a separate page, splitting the "
        "authority the real page earned."),
    "canonical_mismatch": (
        "This page's canonical tag points somewhere else, so search engines "
        "credit the other URL and this one effectively does not exist."),
    "canonical_override": (
        "Something is overriding the canonical you set. The page you intended "
        "to rank is not the page being indexed."),
    # --- technical --------------------------------------------------------
    "broken_internal_link": (
        "A link on your site leads nowhere. Readers hit a dead end, and the "
        "authority that link was passing is thrown away."),
    "not_found": (
        "This URL returns 404 but is still linked or still ranking. Every "
        "visit it receives is a lost visitor."),
    "server_error": (
        "The server is failing on this page. Repeated errors get a page "
        "dropped from the index, and they cost you every visitor meanwhile."),
    "redirect_chain": (
        "This URL redirects through several hops before it arrives. Each hop "
        "slows the page and leaks a little of the link value."),
    "slow_page": (
        "This page loads slowly enough to affect both ranking and the share "
        "of visitors who leave before it appears."),
    "noindex": (
        "This page carries a noindex tag, so it is deliberately excluded from "
        "search. If that was not deliberate, the page is invisible."),
    "mobile_fail": (
        "This page fails on mobile. Google ranks using the mobile version, so "
        "a mobile problem is a ranking problem on every device."),
    "unreachable": (
        "The crawler could not reach this page at all. If our crawler cannot, "
        "a search engine probably cannot either."),
}

# What a repair actually does, so the button's promise is written down and
# testable rather than implied by its label.
DOES = {
    "schema_missing": "writes JSON-LD structured data into the page head",
    "img_alt_missing": "writes alt text for every image that has none",
    "indexnow_pending": "pings IndexNow so search engines re-crawl now",
    "few_internal_links": "inserts a relevant internal link into the body",
    "orphan_page": "links to this page from a related post",
    "title_missing": "writes a title, keyword first, under 60 characters",
    "title_short": "rewrites the title to use the space available",
    "title_long": "shortens the title to under 60 characters",
    "title_duplicate": "rewrites one of the two so they stop competing",
    "ctr_gap": "rewrites title and description to earn the clicks the "
               "position should already be getting",
    "meta_missing": "writes a description under 155 characters with a reason "
                    "to click",
    "meta_short": "extends the description to use the space",
    "meta_long": "shortens the description to under 155 characters",
    "meta_duplicate": "rewrites one so the two results read differently",
    "thin_content": "drafts the missing sections for your review",
    "decay_refresh": "drafts a refresh against what now ranks above you",
    "cannibalization": "proposes which page to keep and what to merge",
    "h1_missing": "inserts an H1 built from the page title",
    "h1_multiple": "demotes the extra H1s to H2 and keeps the first",
    "heading_order": "renumbers headings so no level is skipped",
    "broken_internal_link": "repoints the link, or removes it if there is no "
                            "replacement",
    "canonical_missing": "sets the canonical to this page's own URL",
    "canonical_mismatch": "sets the canonical to the page you meant to rank",
    "canonical_override": "removes the override and restores your canonical",
    "not_indexed": "submits the URL and asks for a re-inspection",
    "not_found": "puts a 301 to the closest live page, or retires the URL",
}

# The eight that no dashboard button can honestly own, and where they are
# actually fixed. Naming the destination is the difference between an
# explanation and a shrug.
MANUAL_WHERE = {
    "server_error": "your host's error log, then the plugin or theme causing it",
    "slow_page": "the theme and image sizes, or a caching layer",
    "mobile_fail": "the theme's mobile stylesheet",
    "redirect_chain": "the redirect rules in your host or SEO plugin",
    "noindex": "the page's own SEO settings, if the noindex was not intended",
    "unreachable": "your host: the crawler could not connect at all",
    "og_missing": "the theme header, which needs the Open Graph tags added",
    "canonical_missing": "the theme header or your SEO plugin's canonical setting",
}

# Which subsection owns which codes. Every code appears exactly once, checked
# by a gate, so nothing can be detected and then shown on no screen.
TAB_CODES = {
    "seotech": ("Technical & Indexing",
                ["server_error", "unreachable", "slow_page", "mobile_fail",
                 "redirect_chain", "noindex", "not_found",
                 "not_indexed", "indexnow_pending", "canonical_missing",
                 "canonical_mismatch", "canonical_override"]),
    "seoonpage": ("On-Page & Links",
                  ["h1_missing", "h1_multiple", "heading_order",
                   "img_alt_missing", "og_missing", "schema_missing",
                   "few_internal_links", "orphan_page",
                   "broken_internal_link"]),
    "seokw": ("Keywords & Content",
              ["title_missing", "title_short", "title_long",
               "title_duplicate", "ctr_gap", "meta_missing", "meta_short",
               "meta_long", "meta_duplicate", "thin_content",
               "decay_refresh", "cannibalization"]),
}

SEVERITY = {"critical": ("Error", 0), "high": ("Error", 1),
            "medium": ("Warning", 2), "low": ("Notice", 3)}


# ---------------------------------------------------------------------------
# ACTION CLASS - the single source of what a button may do
# ---------------------------------------------------------------------------
def action_class(code: str) -> str:
    """NOW / BODY / DRAFT / MANUAL, read from the scheduler's own tables."""
    if code in WO.SAFE_AUTO_CODES:
        return "NOW"
    if code in WO.BODY_AUTO_CODES:
        return "BODY"
    if code in WO.APPROVAL_CODES:
        return "DRAFT"
    return "MANUAL"


ACTION_LOOK = {
    "NOW": ("Fix now", "a2now",
            "Repairs immediately. Nothing a reader sees will change."),
    "BODY": ("Fix now, edits the page", "a2body",
             "Repairs immediately and DOES change the page a reader sees."),
    "DRAFT": ("Draft a fix", "a2draft",
              "Writes the fix and waits. Nothing changes until you approve."),
    "MANUAL": ("How to fix this", "a2manual",
               "No button can do this one. It is fixed outside the engine."),
}


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


# ---------------------------------------------------------------------------
# THE HEADER - the same on all ten screens
# ---------------------------------------------------------------------------
def health_header(ctx: dict) -> str:
    """Site health, its parts, and when it was last measured."""
    sc = (ctx or {}).get("scores") or {}
    overall = sc.get("overall")
    parts = [("Technical", sc.get("technical")), ("Indexing", sc.get("indexing")),
             ("On-page", sc.get("on_page")), ("Off-page", sc.get("off_page")),
             ("Visibility", sc.get("visibility")), ("Answer engines", sc.get("aeo")),
             ("Local", sc.get("local"))]
    # The crawler writes {"base", "at", "count", "urls"}. Reading "pages"
    # first, as an earlier draft did, silently printed "0 pages crawled" over
    # a real 176-page crawl: a true-looking number that was never measured.
    crawl = (ctx or {}).get("crawl") or {}
    pages = (sc.get("pages_scored") or crawl.get("count")
             or crawl.get("pages") or len(crawl.get("urls") or ()))
    when = crawl.get("at") or crawl.get("crawled_at") or ""

    def band(v):
        if v is None:
            return "s2none"
        return "s2bad" if v < 60 else ("s2warn" if v < 85 else "s2ok")

    bars = "".join(
        f"<div class='s2part'><span class='s2pl'>{e(n)}</span>"
        f"<span class='s2bar'><i class='{band(v)}' style='width:"
        f"{max(0, min(100, int(v or 0)))}%'></i></span>"
        f"<span class='s2pv {band(v)}'>"
        + (f"{int(v)}" if v is not None else "not measured") + "</span></div>"
        for n, v in parts)

    big = f"{int(overall)}" if overall is not None else "--"
    note = ("Not measured yet. Run a crawl and these fill in."
            if overall is None else
            "100 means every check the engine knows how to run came back clean.")
    return (
        "<div class='s2hd'>"
        f"<div class='s2score {band(overall)}'><b>{big}</b>"
        f"<span>Site health</span></div>"
        f"<div class='s2parts'>{bars}</div>"
        "<div class='s2crawl'>"
        f"<p class='s2cn'><b>{e(pages or 0)}</b> pages crawled</p>"
        f"<p class='s2cw'>{e(when) or 'no crawl on record'}</p>"
        "<button class='cta' onclick=\"act('/seo/crawl')\">Re-crawl now</button>"
        "<button class='cta' onclick=\"act('/seo/run-all')\">Run every check</button>"
        "</div>"
        f"<p class='s2note'>{e(note)}</p>"
        "</div>")


# ---------------------------------------------------------------------------
# THE ISSUE TABLE - one row per problem type, expanding to the URLs
# ---------------------------------------------------------------------------
def _rows_for(orders: list, codes: list) -> list:
    """Group open work orders by code, biggest cost first."""
    by = {}
    for o in orders or ():
        c = o.get("code")
        if c in codes and o.get("status") in ("open", "awaiting_approval", ""):
            by.setdefault(c, []).append(o)
    out = []
    for c in codes:
        got = by.get(c) or []
        sev = "medium"
        if got:
            sev = min((o.get("severity") or "low" for o in got),
                      key=lambda s: SEVERITY.get(s, ("Notice", 3))[1])
        out.append({
            "code": c, "orders": got, "n": len(got),
            "severity": sev,
            "impact": round(sum(float(o.get("impact") or 0) for o in got), 1),
            "action": action_class(c),
        })
    out.sort(key=lambda r: (-r["n"], SEVERITY.get(r["severity"], ("", 3))[1]))
    return out


def _issue_row(r: dict, ctx: dict) -> str:
    code = r["code"]
    label, cls, promise = ACTION_LOOK[r["action"]]
    sev_word = SEVERITY.get(r["severity"], ("Notice", 3))[0]
    sev_cls = {"Error": "s2bad", "Warning": "s2warn", "Notice": "s2none"}[sev_word]
    n = r["n"]
    title = code.replace("_", " ")

    if n:
        headline = (f"{n} page{'s' if n != 1 else ''} affected")
    else:
        headline = "clean"

    # the button. MANUAL never renders one that posts.
    if not n:
        btn = "<span class='s2clean'>nothing to fix</span>"
    elif r["action"] == "MANUAL":
        where = MANUAL_WHERE.get(code, "outside the engine")
        btn = (f"<button class='cta {cls}' onclick=\"s2manual('{e(code)}')\">"
               f"{e(label)}</button>"
               f"<div class='s2man' id='s2m-{e(code)}' style='display:none'>"
               f"Fixed in: {e(where)}</div>")
    else:
        ids = ",".join(str(o.get("id")) for o in r["orders"][:50])
        btn = (f"<button class='cta {cls}' "
               f"onclick=\"s2fix('{e(code)}','{e(ids)}',this)\">"
               f"{e(label)}{'' if n == 1 else f' &middot; {n}'}</button>")

    urls = "".join(
        f"<li><a href='{e(o.get('url'))}' target='_blank' rel='noopener'>"
        f"{e(o.get('url'))}</a>"
        + (f"<span class='s2ev'>{e(o.get('evidence'))[:90]}</span>"
           if o.get("evidence") else "")
        + (f"<span class='s2prop'>proposed: {e((o.get('extra') or {}).get('proposal',{}).get('after',''))[:80]}</span>"
           if (o.get("extra") or {}).get("proposal") else "")
        + "</li>"
        for o in r["orders"][:25])
    more = (f"<li class='s2more'>and {n - 25} more</li>" if n > 25 else "")

    return (
        f"<div class='s2issue{' s2quiet' if not n else ''}' id='iss-{e(code)}'>"
        f"<div class='s2ir' onclick=\"s2open('{e(code)}')\">"
        f"<span class='s2sev {sev_cls}'>{sev_word}</span>"
        f"<span class='s2code'>{e(title)}</span>"
        f"<span class='s2n'>{e(headline)}</span>"
        f"<span class='s2act'>{btn}</span>"
        "</div>"
        f"<div class='s2body' id='b-{e(code)}' style='display:none'>"
        f"<p class='s2why'>{e(EXPLAIN.get(code, 'No explanation written for this check yet.'))}</p>"
        + (f"<p class='s2does'><b>Pressing that button:</b> {e(DOES[code])}. "
           f"{e(promise)}</p>" if code in DOES and n else
           f"<p class='s2does'>{e(promise)}</p>" if n else "")
        + (f"<ul class='s2urls'>{urls}{more}</ul>" if n else "")
        + "</div></div>")


def issues_panel(ctx: dict, codes: list, *, title: str = "") -> str:
    orders = (ctx or {}).get("orders") or []
    rows = _rows_for(orders, codes)
    live = [r for r in rows if r["n"]]
    total = sum(r["n"] for r in rows)
    errs = sum(r["n"] for r in rows
               if SEVERITY.get(r["severity"], ("Notice", 3))[0] == "Error")
    head = (f"<div class='s2sum'>"
            f"<span class='s2big s2bad'>{errs}</span><span class='s2lb'>errors</span>"
            f"<span class='s2big s2warn'>{total - errs}</span>"
            f"<span class='s2lb'>warnings and notices</span>"
            f"<span class='s2big'>{len(live)}</span>"
            f"<span class='s2lb'>of {len(rows)} checks failing</span></div>")
    if not orders:
        head += ("<p class='s2empty'>No audit on record yet. Press "
                 "<b>Run every check</b> above and this fills with real "
                 "pages from your site.</p>")
    return head + "".join(_issue_row(r, ctx) for r in rows)


# ---------------------------------------------------------------------------
# THE TEN SCREENS
# ---------------------------------------------------------------------------
def _measure_rows(cards) -> str:
    """Measurements that are not issues still belong on the screen, but under
    the issues, because a number you cannot act on never outranks a repair."""
    import content_engine_vx2 as V
    if not cards:
        return ""
    lines = sorted((V._line(c) for c in cards), key=lambda t: t[0])
    return ("<div class='s2meas'><h4>Measurements</h4>"
            + "".join(h for _w, h in lines) + "</div>")


def command_screen(ctx: dict, cards) -> str:
    """SEO Command: health, then the ten repairs worth the most."""
    orders = (ctx or {}).get("orders") or []
    rows = _rows_for(orders, list(EXPLAIN))
    top = [r for r in rows if r["n"]][:10]
    if top:
        body = ("<h4 class='s2h4'>The ten repairs worth the most, in order"
                "</h4>" + "".join(_issue_row(r, ctx) for r in top))
    else:
        body = ("<p class='s2empty'>Nothing is queued for repair. Either the "
                "site is clean or no audit has run. The crawl date above "
                "tells you which.</p>")
    return health_header(ctx) + body + _measure_rows(cards)


def issue_screen(tab: str, ctx: dict, cards) -> str:
    _title, codes = TAB_CODES[tab]
    return (health_header(ctx) + issues_panel(ctx, codes)
            + _measure_rows(cards))


def workorders_screen(ctx: dict, cards) -> str:
    """Every open repair across all 33 checks, in one queue."""
    orders = (ctx or {}).get("orders") or []
    waiting = [o for o in orders
               if (o.get("extra") or {}).get("proposal")
               and o.get("status") in ("open", "awaiting_approval")]
    bulk = ""
    if waiting:
        kinds = sorted({o.get("type") for o in waiting if o.get("type")})
        bulk = ("<div class='s2bulk'><p><b>" + str(len(waiting))
                + "</b> drafted fixes are waiting for you. Nothing has been "
                "published.</p>"
                + "".join(
                    "<button class='cta a2draft' onclick=\"act('/seo/"
                    f"approve-all?type={e(k)}')\">Approve every "
                    f"{e(k)} rewrite</button>" for k in kinds)
                + "</div>")
    return (health_header(ctx) + bulk
            + issues_panel(ctx, list(EXPLAIN)) + _measure_rows(cards))


CSS = """
.s2hd{display:grid;grid-template-columns:auto 1fr auto;gap:22px;align-items:center;
padding:16px 18px;border:1px solid var(--ln);border-radius:10px;margin:0 0 18px;
background:var(--card)}
.s2score{display:flex;flex-direction:column;align-items:center;min-width:96px;
padding:10px 14px;border-radius:9px;border:1px solid var(--ln)}
.s2score b{font-size:38px;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
.s2score span{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ft);margin-top:5px}
.s2score.s2ok b{color:var(--okc)}.s2score.s2warn b{color:var(--warnc)}
.s2score.s2bad b{color:var(--bad)}.s2score.s2none b{color:var(--ft)}
.s2parts{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px}
.s2part{display:flex;align-items:center;gap:9px;font-size:12px}
.s2pl{width:96px;color:var(--dm);flex:none}
.s2bar{flex:1;height:5px;background:var(--ln);border-radius:3px;overflow:hidden}
.s2bar i{display:block;height:100%;border-radius:3px}
.s2bar i.s2ok{background:var(--okc)}.s2bar i.s2warn{background:var(--warnc)}
.s2bar i.s2bad{background:var(--bad)}.s2bar i.s2none{background:var(--ln)}
.s2pv{width:74px;text-align:right;font-family:ui-monospace,Menlo,monospace;
font-size:11px;font-variant-numeric:tabular-nums}
.s2pv.s2ok{color:var(--okc)}.s2pv.s2warn{color:var(--warnc)}
.s2pv.s2bad{color:var(--bad)}.s2pv.s2none{color:var(--ft)}
.s2crawl{text-align:right;display:flex;flex-direction:column;gap:5px;align-items:flex-end}
.s2cn{margin:0;font-size:13px}.s2cw{margin:0;font-size:11px;color:var(--ft)}
.s2note{grid-column:1/-1;margin:2px 0 0;font-size:11.5px;color:var(--ft)}
.s2sum{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin:0 0 12px;
padding:0 2px}
.s2big{font-size:22px;font-weight:800;font-variant-numeric:tabular-nums}
.s2big.s2bad{color:var(--bad)}.s2big.s2warn{color:var(--warnc)}
.s2lb{font-size:12px;color:var(--ft);margin-right:16px}
.s2issue{border:1px solid var(--ln);border-radius:8px;margin:0 0 6px;
background:var(--card);overflow:hidden}
.s2issue.s2quiet{opacity:.5}
.s2ir{display:flex;align-items:center;gap:12px;padding:9px 12px;cursor:pointer}
.s2ir:hover{background:var(--hov)}
.s2sev{font-size:9.5px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;
width:62px;flex:none}
.s2sev.s2bad{color:var(--bad)}.s2sev.s2warn{color:var(--warnc)}
.s2sev.s2none{color:var(--ft)}
.s2code{flex:1;font-size:13.5px;text-transform:capitalize;min-width:0;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.s2n{font-size:12px;color:var(--dm);white-space:nowrap}
.s2act{flex:none;display:flex;gap:6px;align-items:center}
.s2clean{font-size:11px;color:var(--ft)}
.s2body{padding:2px 14px 14px 76px;border-top:1px solid var(--ln)}
.s2why{margin:10px 0 6px;font-size:13px;line-height:1.6;color:var(--dm);max-width:66ch}
.s2does{margin:0 0 8px;font-size:12.5px;line-height:1.55;color:var(--tx);max-width:66ch}
.s2urls{margin:6px 0 0;padding:0 0 0 16px;font-size:12px;line-height:1.75}
.s2urls a{color:var(--ac);text-decoration:none}
.s2urls a:hover{text-decoration:underline}
.s2ev,.s2prop{display:block;color:var(--ft);font-size:11px}
.s2prop{color:var(--okc)}
.s2more{color:var(--ft);list-style:none}
.s2man{margin:8px 0 0;font-size:12.5px;color:var(--dm)}
.s2h4{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ft);
margin:18px 0 8px}
.s2meas{margin-top:26px;border-top:1px solid var(--ln);padding-top:6px}
.s2meas h4{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ft);margin:10px 0 4px}
.s2bulk{border:1px solid var(--ln);border-left:3px solid var(--ac);border-radius:8px;
padding:12px 14px;margin:0 0 14px;display:flex;gap:10px;align-items:center;
flex-wrap:wrap;background:var(--card)}
.s2bulk p{margin:0;font-size:13px;flex:1;min-width:220px}
.s2empty{font-size:13px;color:var(--ft);padding:14px 2px;margin:0;line-height:1.6}
/* THE BASE. Without this the issue-row buttons inherit nothing: VX2 styles
   .v2act .cta and these live in .s2act, so the browser was drawing them with
   its own default chrome (border-style: outset, a black border on the dashed
   one). Caught by reading computed styles in a browser, not by reading CSS. */
.s2act .cta,.s2bulk .cta,.s2crawl .cta{font-size:11.5px;padding:4px 10px;
border:1px solid var(--ln);border-radius:6px;background:var(--card);
color:var(--tx);cursor:pointer;font-family:inherit;white-space:nowrap}
.s2act .cta:hover,.s2bulk .cta:hover,.s2crawl .cta:hover{filter:brightness(1.08)}
.s2act .cta[disabled]{opacity:.55;cursor:default}
/* the four action classes, never the same look twice */
.cta.a2now{border-color:var(--okc);color:var(--okc)}
.cta.a2body{border-color:var(--warnc);color:var(--warnc)}
.cta.a2draft{border-color:var(--ac);color:var(--ac)}
.cta.a2manual{border-style:dashed;border-color:var(--ft);color:var(--ft)}
@media (max-width:900px){.s2hd{grid-template-columns:1fr}
.s2parts{grid-template-columns:1fr}.s2crawl{text-align:left;align-items:flex-start}
.s2body{padding-left:14px}}
"""

JS = ("<script>"
      "function s2open(c){var b=document.getElementById('b-'+c);"
      "if(b)b.style.display=(b.style.display==='none')?'block':'none';}"
      "function s2manual(c){var m=document.getElementById('s2m-'+c);"
      "if(m)m.style.display=(m.style.display==='none')?'block':'none';"
      "var b=document.getElementById('b-'+c);if(b)b.style.display='block';"
      "if(window.event)window.event.stopPropagation();}"
      # ONE fix entry point. It posts the ids the row is holding, so the
      # button repairs exactly the pages the row just told you about.
      "async function s2fix(code,ids,btn){"
      "if(window.event)window.event.stopPropagation();"
      "var list=String(ids||'').split(',').filter(Boolean);"
      "if(!list.length){toast('Nothing queued for '+code);return;}"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}"
      "var ok=0,bad=0,last='';"
      "for(var i=0;i<list.length;i++){try{"
      "var r=await fetch('/seo/fix/'+list[i],{method:'POST'});"
      "var j=await r.json();"
      "if(j&&(j.ok!==false)&&(j.status==='done'||j.applied||j.ok)){ok++;}"
      "else{bad++;last=(j&&(j.result||j.error))||'refused';}"
      "}catch(e){bad++;last='could not reach the engine';}}"
      "if(btn){btn.disabled=false;btn.textContent=lab;}"
      "toast(ok+' repaired'+(bad?(', '+bad+' could not be: '+last):'')"
      "+(ok?'. Re-run the checks to see the score move.':''),!bad);"
      "}</script>")
