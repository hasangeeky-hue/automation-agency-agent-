"""
content_engine_vx2_seo.py
============================================================================
THE SEO / AEO / GEO ENVIRONMENT, SEMRUSH GRADE. Ten subsections plus the
Pages screen, one grammar: find the problem, read what it costs, press the
thing that repairs it - or command the agent to press all of them.

THE LAYERS
  the agent band     command the fleet: fix everything, draft everything,
                     approve everything, and the OFF / SAFE / ALL switch
  the audit band     health ring, the three decision counts, seven sub-scores
  the issue rows     one row per problem type, count, cost, repair
  the pages screen   the same queue keyed by URL: every page, its problems,
                     one button that fixes everything fixable on it

THE ONE RULE THAT MATTERS HERE
  A button's appearance is decided by what it is ALLOWED to do, never by what
  it is about. Four action classes, four looks, read from
  content_engine_workorders - the same tables the scheduler obeys. And every
  button lands on the fixer's ONE dispatch (run_batch), so a click can never
  behave differently from the nightly run.

WIRING (all endpoints exist in content_engine_api)
  /seo/run-orders    execute or draft a set of order ids through the dispatch
  /seo/fix-page      everything fixable on one URL
  /seo/fix-all       the agent's unattended set, now
  /seo/draft-all     draft every approval-gated fix (LLM cost capped per click)
  /seo/approve-all   publish every drafted rewrite of one type
  /seo/fix/{id}      approve ONE drafted proposal
  /seo/auto          the OFF / SAFE / ALL ladder the scheduler obeys
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_workorders as WO
import content_engine_vx2_shapes as SH

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


def _open(orders):
    return [o for o in (orders or ())
            if o.get("status") in ("open", "awaiting_approval", "")]


# ---------------------------------------------------------------------------
# THE AGENT COMMAND BAND - you have agents; this is where you command them
# ---------------------------------------------------------------------------
def agent_band(ctx: dict) -> str:
    """The fleet's cockpit: status in words, three bulk commands, the ladder.

    Every button here drives machinery that already runs unattended; the band
    only makes the commands visible. The level is READ from the scheduler's
    own switch, never assumed - if it cannot be read, the band says so."""
    orders = _open((ctx or {}).get("orders"))
    drafted = [o for o in orders if (o.get("extra") or {}).get("proposal")]
    n_fix = sum(1 for o in orders if action_class(o.get("code")) != "MANUAL")
    n_man = sum(1 for o in orders if action_class(o.get("code")) == "MANUAL")
    level = str((ctx or {}).get("auto_level") or "unknown").lower()
    runs = (ctx or {}).get("engine_runs") or {}
    last_fix = runs.get("fixes") or ""

    lvl_word = {"off": "OFF - the agent waits for your clicks",
                "safe": "SAFE 24/7 - invisible fixes run unattended",
                "all": "ALL - includes body edits readers can see",
                }.get(level, "switch state could not be read")

    kinds = sorted({o.get("type") for o in drafted if o.get("type")})
    approve_btns = "".join(
        f"<button class='cta a2draft' onclick=\"act('/seo/approve-all?"
        f"type={e(k)}')\">Approve every {e(k)} rewrite</button>"
        for k in kinds[:4])

    def _lvl(lv, label):
        on = " s3on" if level == lv else ""
        return (f"<button class='s3lvl{on}' "
                f"onclick=\"seoAutoSet('{lv}',this)\">{label}</button>")

    return (
        "<div class='s3band'>"
        "<div class='s3who'>"
        "<p class='s3k'>Your SEO agent</p>"
        f"<p class='s3state'><b>{e(lvl_word)}</b>"
        + (f" &middot; last fix run {e(str(last_fix)[:16])}" if last_fix else
           " &middot; no fix run recorded yet")
        + "</p>"
        f"<p class='s3sub'>{n_fix} problems it can repair &middot; "
        f"{len(drafted)} drafted and waiting for you &middot; "
        f"{n_man} need hands outside the engine. Safe fixes change nothing "
        f"a reader sees; everything else is drafted and queued below.</p>"
        "</div>"
        "<div class='s3cmds'>"
        "<button class='cta s3go' onclick=\"act('/seo/fix-all')\">"
        "Agent: fix everything it may, now</button>"
        + (f"<button class='cta a2draft' onclick=\"s3draftall(this)\">"
           f"Agent: draft fixes for all {n_fix}</button>" if n_fix else "")
        + approve_btns
        + "</div>"
        "<div class='s3ladder' role='group' aria-label='unattended level'>"
        + _lvl("off", "OFF") + _lvl("safe", "SAFE 24/7") + _lvl("all", "ALL")
        + "</div></div>")


# ---------------------------------------------------------------------------
# THE AUDIT BAND - ring, the three decision counts, seven sub-scores
# ---------------------------------------------------------------------------
def health_header(ctx: dict) -> str:
    """Site health as the SEMrush band: the ring, the three counts that are
    decisions, and the seven sub-scores. Absent data reads as absent."""
    sc = (ctx or {}).get("scores") or {}
    overall = sc.get("overall")
    parts = [("Technical", sc.get("technical")), ("Indexing", sc.get("indexing")),
             ("On-page", sc.get("on_page")), ("Off-page", sc.get("off_page")),
             ("Visibility", sc.get("visibility")), ("Answer engines", sc.get("aeo")),
             ("Local", sc.get("local"))]
    # The crawler writes {"base","at","count","urls"}; reading "pages" first
    # once printed "0 pages crawled" over a real 176-page crawl.
    crawl = (ctx or {}).get("crawl") or {}
    pages = (sc.get("pages_scored") or crawl.get("count")
             or crawl.get("pages") or len(crawl.get("urls") or ()))
    when = crawl.get("at") or crawl.get("crawled_at") or ""

    orders = _open((ctx or {}).get("orders"))
    drafted = sum(1 for o in orders if (o.get("extra") or {}).get("proposal"))
    n_fix = sum(1 for o in orders if action_class(o.get("code")) != "MANUAL")
    n_man = sum(1 for o in orders if action_class(o.get("code")) == "MANUAL")

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

    if overall is not None:
        ring = SH.score_ring(float(overall), size=104)
    else:
        ring = "<span class='s2nonebig'>--</span>"
    note = ("Not measured yet. Run a crawl and these fill in."
            if overall is None else
            "100 means every check the engine knows how to run came back clean.")
    return (
        "<div class='s2hd'>"
        f"<div class='s2score {band(overall)}'>{ring}"
        f"<span>Site health</span></div>"
        "<div class='s3trio'>"
        f"<div class='s3cell s3e'><b>{n_fix}</b><span>fixable from this "
        f"screen</span></div>"
        f"<div class='s3cell s3d'><b>{drafted}</b><span>drafted, waiting for "
        f"you</span></div>"
        f"<div class='s3cell s3w'><b>{n_man}</b><span>manual: theme or host "
        f"work</span></div></div>"
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


def _issue_row(r: dict, ctx: dict, scope: str = "") -> str:
    """scope prefixes every element id. The old dashboard renders ALL
    panels at once, and the same code appears on Command, its own tab AND
    Work Orders - three ids called iss-server_error on one page, and
    getElementById answering with whichever came first. That is the exact
    duplicate-id class that broke the calendar preview once already."""
    code = r["code"]
    sid = f"{scope}{code}"
    label, cls, promise = ACTION_LOOK[r["action"]]
    sev_word = SEVERITY.get(r["severity"], ("Notice", 3))[0]
    sev_cls = {"Error": "s2bad", "Warning": "s2warn", "Notice": "s2none"}[sev_word]
    n = r["n"]
    title = code.replace("_", " ")
    headline = (f"{n} page{'s' if n != 1 else ''} affected") if n else "clean"

    drafted = [o for o in r["orders"] if (o.get("extra") or {}).get("proposal")]
    undone = [o for o in r["orders"] if not (o.get("extra") or {}).get("proposal")]

    # THE BUTTONS, WIRED TO WHAT THEY CLAIM.
    #   run    -> /seo/run-orders: the fixer's dispatch. Applies NOW/BODY
    #             codes, drafts DRAFT codes. This used to point at the
    #             APPROVE endpoint, which refuses anything undrafted - a
    #             button that looked live and was not.
    #   approve-> /seo/fix/{id} per drafted order, which publishes.
    btns = []
    if not n:
        btns.append("<span class='s2clean'>nothing to fix</span>")
    elif r["action"] == "MANUAL":
        where = MANUAL_WHERE.get(code, "outside the engine")
        btns.append(f"<button class='cta {cls}' "
                    f"onclick=\"s2manual('{e(sid)}')\">{e(label)}</button>"
                    f"<div class='s2man' id='s2m-{e(sid)}' "
                    f"style='display:none'>Fixed in: {e(where)}</div>")
    else:
        if undone:
            ids = ",".join(str(o.get("id")) for o in undone[:100])
            btns.append(f"<button class='cta {cls}' "
                        f"onclick=\"s3run('{e(ids)}',this)\">{e(label)}"
                        f"{'' if len(undone) == 1 else f' &middot; {len(undone)}'}"
                        f"</button>")
        if drafted:
            ids = ",".join(str(o.get("id")) for o in drafted[:100])
            btns.append(f"<button class='cta a2draft' "
                        f"onclick=\"s2fix('{e(code)}','{e(ids)}',this)\">"
                        f"Approve {len(drafted)} drafted</button>")

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
        f"<div class='s2issue{' s2quiet' if not n else ''}' id='iss-{e(sid)}'>"
        f"<div class='s2ir' onclick=\"s2open('{e(sid)}')\">"
        f"<span class='s2sev {sev_cls}'>{sev_word}</span>"
        f"<span class='s2code'>{e(title)}</span>"
        f"<span class='s2n'>{e(headline)}</span>"
        f"<span class='s2act'>{''.join(btns)}</span>"
        "</div>"
        f"<div class='s2body' id='b-{e(sid)}' style='display:none'>"
        f"<p class='s2why'>{e(EXPLAIN.get(code, 'No explanation written for this check yet.'))}</p>"
        + (f"<p class='s2does'><b>Pressing that button:</b> {e(DOES[code])}. "
           f"{e(promise)}</p>" if code in DOES and n else
           f"<p class='s2does'>{e(promise)}</p>" if n else "")
        + (f"<ul class='s2urls'>{urls}{more}</ul>" if n else "")
        + "</div></div>")


def issues_panel(ctx: dict, codes: list, *, title: str = "",
                 scope: str = "") -> str:
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
    return head + "".join(_issue_row(r, ctx, scope) for r in rows)


# ---------------------------------------------------------------------------
# THE PAGES SCREEN - the same queue, keyed by URL
# ---------------------------------------------------------------------------
def pages_screen(ctx: dict) -> str:
    """Every page with open problems: its counts, its worst issue, and one
    button that runs everything fixable on it through the single dispatch."""
    orders = _open((ctx or {}).get("orders"))
    by_url = {}
    for o in orders:
        by_url.setdefault(str(o.get("url") or "(no url)"), []).append(o)
    pages = sorted(by_url.items(),
                   key=lambda kv: -sum(float(o.get("impact") or 0)
                                       for o in kv[1]))
    head = (f"<div class='s2sum'><span class='s2big'>{len(pages)}</span>"
            f"<span class='s2lb'>pages carrying open problems</span>"
            f"<span class='s2big s2bad'>{len(orders)}</span>"
            f"<span class='s2lb'>problems across them</span></div>")
    if not pages:
        return head + ("<p class='s2empty'>No page carries an open problem. "
                       "Either the site is clean or no audit has run; the "
                       "crawl date in the band above says which.</p>")
    rows = []
    for i, (url, ords) in enumerate(pages[:40]):
        errs = sum(1 for o in ords
                   if SEVERITY.get(o.get("severity"), ("", 3))[0] == "Error")
        worst = max(ords, key=lambda o: float(o.get("impact") or 0))
        fixable = [o for o in ords if action_class(o.get("code")) != "MANUAL"]
        drafted = sum(1 for o in ords if (o.get("extra") or {}).get("proposal"))
        fixes = "".join(
            f"<div class='s3fx'>"
            f"<span class='s2sev {('s2bad' if action_class(o.get('code')) in ('NOW','BODY') else 's2none') if False else ''}' "
            f"style='color:var(--{ {'NOW':'okc','BODY':'warnc','DRAFT':'ac','MANUAL':'ft'}[action_class(o.get('code'))] })'>"
            f"{action_class(o.get('code'))}</span>"
            f"<span class='s3fxn'>{e(str(o.get('code')).replace('_',' '))}"
            + (f" <i class='s3prop'>draft ready</i>"
               if (o.get('extra') or {}).get('proposal') else "")
            + "</span>"
            f"<span class='s3fxw'>{e(DOES.get(o.get('code'), MANUAL_WHERE.get(o.get('code'), '')))[:70]}</span>"
            + (f"<button class='cta a2draft' onclick=\"s2fix('one','{e(o.get('id'))}',this)\">Approve</button>"
               if (o.get('extra') or {}).get('proposal') else
               (f"<button class='cta {ACTION_LOOK[action_class(o.get('code'))][1]}' "
                f"onclick=\"s3run('{e(o.get('id'))}',this)\">"
                f"{e(ACTION_LOOK[action_class(o.get('code'))][0])}</button>"
                if action_class(o.get('code')) != 'MANUAL' else
                f"<span class='s2clean'>{e(MANUAL_WHERE.get(o.get('code'), 'manual'))[:38]}</span>"))
            + "</div>"
            for o in sorted(ords, key=lambda x: -float(x.get("impact") or 0))[:12])
        rows.append(
            f"<div class='s3pg' id='pg-{i}'>"
            f"<div class='s3pr' onclick=\"s2open('pg{i}')\">"
            f"<span class='s3pill{' s3pe' if errs else ''}'>{len(ords)}</span>"
            f"<a class='s3url' href='{e(url)}' target='_blank' rel='noopener' "
            f"onclick='event.stopPropagation()'>{e(url)}</a>"
            f"<span class='s2n'>{errs} error{'s' if errs != 1 else ''} &middot; "
            f"worst: {e(str(worst.get('code')).replace('_', ' '))}"
            + (f" &middot; {drafted} drafted" if drafted else "") + "</span>"
            f"<span class='s2act'>"
            + (f"<button class='cta s3go' "
               f"onclick=\"s3fixpage('{e(url)}',this)\">Fix this page"
               f" &middot; {len(fixable)}</button>" if fixable else
               "<span class='s2clean'>manual only</span>")
            + "</span></div>"
            f"<div class='s2body' id='b-pg{i}' style='display:none'>{fixes}"
            "</div></div>")
    more = ("" if len(pages) <= 40 else
            f"<p class='s2more' style='list-style:none'>and {len(pages) - 40} "
            f"more pages, worst first</p>")
    return head + "".join(rows) + more


# ---------------------------------------------------------------------------
# ROBOTS & AI ACCESS - robots.txt, llms.txt, who may read you
# ---------------------------------------------------------------------------
def robots_panel(ctx: dict) -> str:
    acc = (ctx or {}).get("crawler_access") or {}
    llms = (ctx or {}).get("llms_txt") or ""
    bots = acc.get("bots") or []

    def chk(ok, text, extra=""):
        cls = "y" if ok else ("n" if ok is False else "q")
        mark = "&#10003;" if ok else ("&#10005;" if ok is False else "?")
        return (f"<div class='s3chk'><i class='{cls}'>{mark}</i>{text}"
                f"{extra}</div>")

    left = ["<p class='s3k'>robots.txt</p>"]
    if not acc:
        left.append("<p class='s2empty'>Not checked yet. The crawler-access "
                    "probe runs with the AEO engine; press it and this fills "
                    "with your live robots rules.</p>"
                    "<button class='cta' onclick=\"act('/aeo/probe')\">"
                    "Probe now</button>")
    else:
        left.append(chk(bool(acc.get("robots_found")),
                        "robots.txt exists and answers"))
        left.append(chk(bool(acc.get("has_sitemap")),
                        "Sitemap declared in it"))
        blocked = int(acc.get("blocked_count") or 0)
        left.append(chk(blocked == 0,
                        f"{blocked} AI crawler(s) blocked" if blocked
                        else "No AI crawler is blocked"))
        if acc.get("reason"):
            left.append(f"<p class='s2empty'>{e(acc['reason'])}</p>")

    right = ["<p class='s3k'>llms.txt &middot; what AI engines are told "
             "about you</p>"]
    if llms:
        lines = str(llms).count("\n") + 1
        right.append(chk(True, f"Generated &middot; {len(str(llms)) // 1024} KB, "
                               f"{lines} lines &middot; served at /seo/llms.txt"))
        right.append("<button class='cta' onclick=\"act('/aeo/probe')\">"
                     "Regenerate with the next probe</button>")
    else:
        right.append(chk(False, "Not generated yet - AI engines have nothing "
                                "curated to read about you"))
        right.append("<button class='cta' onclick=\"act('/aeo/probe')\">"
                     "Generate it now</button>")

    grid = ""
    if bots:
        cells = []
        for b in bots[:12]:
            down = bool(b.get("blocked")) or str(b.get("status", "")).lower() in (
                "blocked", "disallowed")
            col = "var(--bad)" if down else "var(--okc)"
            word = "blocked" if down else "allowed"
            cells.append(f"<div class='s3bot'><i style='background:{col}'></i>"
                         f"{e(b.get('bot') or b.get('vendor') or '?')}"
                         f"<span>{word}</span></div>")
        grid = ("<p class='s3k'>AI crawlers &middot; from your live robots "
                "rules</p><div class='s3bots'>" + "".join(cells) + "</div>"
                "<p class='s2empty' style='padding:6px 2px'>A blocked AI "
                "crawler cannot cite you. Changing a rule is a robots.txt "
                "edit; the engine drafts it, your theme carries it.</p>")

    return ("<div class='s3two'><div class='s3panel'>" + "".join(left)
            + "</div><div class='s3panel'>" + "".join(right) + grid
            + "</div></div>")


# ---------------------------------------------------------------------------
# BACKLINKS - authority, the gap, the pitch pipeline
# ---------------------------------------------------------------------------
def backlinks_screen(ctx: dict) -> str:
    off = (ctx or {}).get("offpage") or {}
    gap = (ctx or {}).get("link_gap") or []
    pstats = (ctx or {}).get("prospect_stats") or {}
    prospects = (ctx or {}).get("prospects") or []

    out = []
    if not off.get("connected"):
        out.append(f"<div class='s3banner'>{e(off.get('reason') or 'DataForSEO is not connected.')}"
                   " The four cells below fill the hour the key is added; "
                   "everything under them runs free, now.</div>")
        cells = [("Authority score", None), ("Backlinks", None),
                 ("Referring domains", None), ("New / lost &middot; 30d", None)]
    else:
        cells = [("Authority score", off.get("rank") or off.get("authority")),
                 ("Backlinks", off.get("backlinks")),
                 ("Referring domains", off.get("referring_domains")),
                 ("New / lost &middot; 30d",
                  f"{off.get('new', '?')} / {off.get('lost', '?')}")]
    out.append("<div class='s3stats'>" + "".join(
        f"<div class='s3stat'><span class='s3k'>{k}</span>"
        + (f"<b>{e(v)}</b>" if v not in (None, "") else
           "<b class='s2nonebig'>--</b><span class='s3d'>needs DataForSEO"
           "</span>")
        + "</div>" for k, v in cells) + "</div>")

    out.append("<p class='s3k' style='margin-top:16px'>The link gap &middot; "
               "free, from SERP overlap with rivals</p>")
    if gap:
        rows = []
        for g in gap[:12]:
            if isinstance(g, dict):
                dom = g.get("domain") or g.get("url") or "?"
                why = g.get("why") or g.get("reason") or ""
                n = g.get("links") or g.get("count") or ""
            else:
                dom, why, n = str(g), "", ""
            rows.append(f"<div class='s3fx'><span class='s3fxn mono'>{e(dom)}"
                        f"</span><span class='s3fxw'>{e(why)[:80]}</span>"
                        f"<span class='s2n'>{e(n)}</span>"
                        f"<button class='cta a2draft' "
                        f"onclick=\"act('/seo/prospecting')\">Draft a pitch"
                        f"</button></div>")
        out.append("".join(rows))
    else:
        out.append("<p class='s2empty'>No gap computed yet. It builds from "
                   "rank overlap with rivals; run the off-page engine and "
                   "name rivals to fill it.</p>"
                   "<button class='cta' onclick=\"act('/seo/offpage')\">"
                   "Run off-page now</button>")

    out.append("<p class='s3k' style='margin-top:16px'>Pitch pipeline &middot; "
               "your outreach machinery, aimed at links</p>")
    out.append("<div class='s3stats'>"
               f"<div class='s3stat'><span class='s3k'>Prospects</span>"
               f"<b>{int(pstats.get('total') or len(prospects) or 0)}</b></div>"
               f"<div class='s3stat'><span class='s3k'>Awaiting approval</span>"
               f"<b>{int(pstats.get('awaiting_approval') or 0)}</b></div>"
               f"<div class='s3stat'><span class='s3k'>Contacted</span>"
               f"<b>{int(pstats.get('contacted') or 0)}</b></div>"
               f"<div class='s3stat'><span class='s3k'>Replied &middot; placed"
               f"</span><b>{int(pstats.get('replied') or 0)}"
               f"<span style='font-size:13px;color:var(--ft)'> &middot; "
               f"{int(pstats.get('placed') or 0)}</span></b></div></div>")
    out.append("<p class='s2empty' style='padding:6px 2px'>Nothing sends "
               "itself: every pitch is drafted, queued, and waits for your "
               "approval like every other email in the engine.</p>")
    return "".join(out)


# ---------------------------------------------------------------------------
# AEO - do answer engines name you, and what feeds them
# ---------------------------------------------------------------------------
def aeo_screen(ctx: dict) -> str:
    aeo = (ctx or {}).get("aeo") or {}
    prompts = aeo.get("prompts") or []
    llms = (ctx or {}).get("llms_txt") or ""
    quot = (ctx or {}).get("quotable") or {}

    named = sum(1 for p in prompts if p.get("mentioned"))
    hero = (SH.ratio_bar(named, len(prompts)) if prompts else
            "<span class='s2nonebig'>--</span>")
    out = [f"<div class='s3aeohd'><div><p class='s3k'>Mention rate</p>{hero}"
           f"<p class='s3d'>{aeo.get('engines_live', 0)} engine(s) probed "
           f"live</p></div>"
           "<button class='cta s3go' onclick=\"act('/aeo/probe')\">"
           "Probe the engines now</button></div>"]

    if prompts:
        rows = []
        for p in prompts[:10]:
            hit = bool(p.get("mentioned"))
            pill = ("<span class='s3pill' style='background:var(--okbg);"
                    "color:var(--okc)'>named you</span>" if hit else
                    "<span class='s3pill s3pe'>not you</span>")
            rivals = p.get("rivals_mentioned") or []
            rv = (", ".join(map(str, rivals[:3])) if rivals
                  else "no rival named either - open ground")
            rows.append(f"<div class='s3fx'><span class='s3fxn'>"
                        f"{e(p.get('prompt'))[:70]}</span>{pill}"
                        f"<span class='s3fxw'>{e(rv)[:70]}</span></div>")
        out.append("<p class='s3k'>Question by question &middot; last probe"
                   "</p>" + "".join(rows))
    else:
        out.append("<p class='s2empty'>No probe on record. Press the button "
                   "above: it asks the live engines your buyers' questions "
                   "and records who they named.</p>")

    levers = []
    levers.append(f"<div class='s3fx'><span class='s3fxn'>llms.txt</span>"
                  f"<span class='s3fxw'>"
                  + ("generated and served" if llms else
                     "not generated - engines have nothing curated to read")
                  + "</span><button class='cta a2draft' "
                    "onclick=\"act('/aeo/probe')\">"
                  + ("Regenerate" if llms else "Generate") + "</button></div>")
    # quotable's shape varies by engine version: "blocks" has been a list of
    # blocks AND a plain count. Read either; never crash on real data.
    _q = (quot.get("blocks") or quot.get("pages") or 0) if isinstance(quot, dict) else 0
    nq = _q if isinstance(_q, int) else len(_q)
    levers.append(f"<div class='s3fx'><span class='s3fxn'>Quotable blocks"
                  f"</span><span class='s3fxw'>"
                  + (f"{nq} pages carry a liftable 40-word answer" if nq else
                     "no page carries a block an engine can lift verbatim")
                  + "</span></div>")
    out.append("<p class='s3k' style='margin-top:14px'>What feeds an answer "
               "engine</p>" + "".join(levers))
    return "".join(out)


# ---------------------------------------------------------------------------
# GEO - markets, and the local pack
# ---------------------------------------------------------------------------
def geo_gen_screen(ctx: dict) -> str:
    g = (ctx or {}).get("geo") or {}
    ranks = (ctx or {}).get("ranks") or []
    out = []
    cells = [("GEO score", g.get("score")),
             ("Markets uncovered", len(g.get("uncovered_markets") or ())),
             ("Market pages missing", len(g.get("missing_market_pages") or ())),
             ("hreflang issues", len(g.get("hreflang_issues") or ()))]
    out.append("<div class='s3stats'>" + "".join(
        f"<div class='s3stat'><span class='s3k'>{k}</span>"
        + (f"<b>{e(v)}</b>" if v not in (None, "") else
           "<b class='s2nonebig'>--</b>")
        + "</div>" for k, v in cells) + "</div>")
    out.append("<button class='cta' style='margin-top:10px' "
               "onclick=\"act('/geo/audit')\">Audit markets now</button>")
    if ranks:
        by = {}
        for r in ranks:
            if isinstance(r, dict):
                by.setdefault(str(r.get("market") or r.get("gl") or "all"),
                              []).append(r)
        rows = []
        for mk, rs in sorted(by.items(), key=lambda kv: -len(kv[1]))[:6]:
            best = min((int(r.get("position") or 99) for r in rs), default=99)
            rows.append(f"<div class='s3fx'><span class='s3fxn'>{e(mk)}</span>"
                        f"<span class='s3fxw'>{len(rs)} tracked keywords"
                        f"</span><span class='s2n'>best position {best}"
                        f"</span></div>")
        out.append("<p class='s3k' style='margin-top:14px'>By market &middot; "
                   "from live SERPs</p>" + "".join(rows))
    else:
        out.append("<p class='s2empty'>No rank rows today. The rank engine "
                   "runs on the cadence; its rows land here per market.</p>")
    return "".join(out)


def geo_local_screen(ctx: dict) -> str:
    nap = (ctx or {}).get("nap") or {}
    grid = (ctx or {}).get("local_grid") or []
    local = (ctx or {}).get("local") or {}
    out = []

    def chk(ok, text, extra=""):
        cls = "y" if ok else ("n" if ok is False else "q")
        mark = "&#10003;" if ok else ("&#10005;" if ok is False else "?")
        return (f"<div class='s3chk'><i class='{cls}'>{mark}</i>{text}"
                f"{extra}</div>")

    out.append("<p class='s3k'>Local pack &middot; Munich</p>")
    if nap:
        ok = nap.get("consistent")
        out.append(chk(bool(ok) if ok is not None else None,
                       "NAP consistent across footer, imprint and schema"
                       if ok else "NAP inconsistency found - name, address or "
                       "phone differ between pages"))
        if nap.get("issues"):
            for i in list(nap["issues"])[:4]:
                out.append(f"<p class='s2empty'>{e(i)}</p>")
    else:
        out.append(chk(None, "NAP not checked yet - runs with the GEO audit"))
    gbp = bool(local.get("connected") or local.get("gbp"))
    out.append(chk(gbp if gbp else False,
                   "Google Business Profile connected" if gbp else
                   "Google Business Profile not connected - the rank grid "
                   "stays honest and empty until it is"))
    if grid:
        out.append(f"<p class='s3k' style='margin-top:12px'>Rank grid &middot; "
                   f"{len(grid)} cells measured</p>")
    out.append("<button class='cta' style='margin-top:10px' "
               "onclick=\"act('/geo/audit')\">Run the local audit</button>")
    return "".join(out)


# ---------------------------------------------------------------------------
# THE SCREENS the router calls
# ---------------------------------------------------------------------------
def command_screen(ctx: dict, cards) -> str:
    """SEO Command: the agent band, the audit band, the ten repairs worth
    the most, and the door to the Pages screen."""
    orders = (ctx or {}).get("orders") or []
    rows = _rows_for(orders, list(EXPLAIN))
    top = [r for r in rows if r["n"]][:10]
    if top:
        body = ("<h4 class='s2h4'>The ten repairs worth the most, in order"
                "</h4>" + "".join(_issue_row(r, ctx, "cmd-") for r in top))
    else:
        body = ("<p class='s2empty'>Nothing is queued for repair. Either the "
                "site is clean or no audit has run. The crawl date above "
                "tells you which.</p>")
    # PAGES LIVES HERE NOW, inline. It was a separate VX2 route; the founder
    # cancelled VX2 and the old dashboard has no fetch-a-screen mechanism, so
    # the per-page command sits right under the top issues where it is
    # always visible - nothing hidden behind a click.
    pages = ("<h4 class='s2h4'>Pages &middot; command page by page</h4>"
             + pages_screen(ctx))
    return (agent_band(ctx) + health_header(ctx) + body + pages
            + _measure_rows(cards))


def technical_screen(ctx: dict, cards) -> str:
    """Technical & Indexing: its issues plus robots.txt, llms.txt and the
    AI crawler grid - the machine-access layer lives with technical."""
    _t, codes = TAB_CODES["seotech"]
    return (health_header(ctx) + robots_panel(ctx)
            + issues_panel(ctx, codes, scope="tech-") + _measure_rows(cards))


def issue_screen(tab: str, ctx: dict, cards) -> str:
    _title, codes = TAB_CODES[tab]
    return (health_header(ctx)
            + issues_panel(ctx, codes, scope=f"{tab}-")
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
    return (agent_band(ctx) + health_header(ctx) + bulk
            + issues_panel(ctx, list(EXPLAIN), scope="wo-")
            + _measure_rows(cards))


def cockpit_card(ctx: dict) -> str:
    """The SEO command card for the Decide board: the same machinery,
    pressed without leaving the cockpit."""
    sc = (ctx or {}).get("scores") or {}
    overall = sc.get("overall")
    orders = _open((ctx or {}).get("orders"))
    drafted = sum(1 for o in orders if (o.get("extra") or {}).get("proposal"))
    n_fix = sum(1 for o in orders if action_class(o.get("code")) != "MANUAL")
    unindexed = sum(1 for o in orders if o.get("code") == "not_indexed")
    level = str((ctx or {}).get("auto_level") or "unknown").lower()
    ring = (SH.score_ring(float(overall), size=46)
            if overall is not None else "<span class='s2nonebig'>--</span>")
    return (
        "<div class='s3ck'>"
        f"<span class='s3ckring'>{ring}</span>"
        f"<span class='s3ckt'><b>Found &middot; site health "
        f"{'--' if overall is None else int(overall)}</b>"
        f"<span>agent at {e(level.upper() if level != 'unknown' else '?')}"
        f" &middot; {n_fix} fixable &middot; {drafted} drafted and waiting"
        + (f" &middot; {unindexed} unindexed" if unindexed else "")
        + "</span></span>"
        "<span class='s2act'>"
        "<button class='cta s3go' onclick=\"act('/seo/fix-all')\">"
        "Agent: fix everything</button>"
        + (f"<button class='cta a2draft' onclick=\"seoTab('seowork')\">"
           f"Review the {drafted}</button>" if drafted else "")
        + (f"<button class='cta' onclick=\"act('/seo/indexnow')\">"
           f"Submit {unindexed}</button>" if unindexed else "")
        + "</span></div>")


def _measure_rows(cards) -> str:
    """Measurements that are not issues still belong on the screen, but under
    the issues, because a number you cannot act on never outranks a repair.

    Early return BEFORE the import: on the old dashboard cards is always
    empty, and the cancelled VX2 module should not be imported just to
    return an empty string."""
    if not cards:
        return ""
    import content_engine_vx2 as V
    lines = sorted((V._line(c) for c in cards), key=lambda t: t[0])
    return ("<div class='s2meas'><h4>Measurements</h4>"
            + "".join(h for _w, h in lines) + "</div>")


CSS = """
/* ---- the agent command band ---- */
.s3band{display:flex;gap:16px;align-items:center;flex-wrap:wrap;
padding:13px 16px;border:1px solid var(--ln);border-left:3px solid var(--ac);
border-radius:11px;background:var(--card);margin:0 0 14px}
.s3band .s3who{flex:1;min-width:240px}
.s3k{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;
letter-spacing:.13em;text-transform:uppercase;color:var(--ft);margin:0 0 4px}
.s3state{margin:0;font-size:13px}
.s3sub{margin:3px 0 0;font-size:11.5px;color:var(--ft);line-height:1.5;
max-width:52ch}
.s3cmds{display:flex;gap:8px;flex-wrap:wrap}
.cta.s3go{background:var(--ac);color:#fff;border-color:var(--ac)}
.cta.s3go:hover{filter:brightness(1.1)}
.s3ladder{display:flex;border:1px solid var(--ln);border-radius:8px;
overflow:hidden}
.s3lvl{font-family:ui-monospace,Menlo,monospace;font-size:11px;font-weight:700;
padding:7px 12px;border:0;background:transparent;color:var(--ft);
cursor:pointer}
.s3lvl.s3on{background:var(--ac);color:#fff}
/* ---- the audit band ---- */
.s2hd{display:grid;grid-template-columns:auto auto 1fr auto;gap:20px;
align-items:center;padding:16px 18px;border:1px solid var(--ln);
border-radius:10px;margin:0 0 18px;background:var(--card)}
.s2score{display:flex;flex-direction:column;align-items:center;min-width:96px;
padding:8px 10px;gap:4px}
.s2score span{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ft)}
.s2score.s2ok{color:var(--okc)}.s2score.s2warn{color:var(--warnc)}
.s2score.s2bad{color:var(--bad)}.s2score.s2none{color:var(--ft)}
.s2nonebig{font-family:ui-monospace,Menlo,monospace;font-size:34px;
font-weight:800;color:var(--ft)}
.s3trio{display:flex;flex-direction:column;gap:7px}
.s3cell{border:1px solid var(--ln);border-radius:9px;padding:7px 12px;
display:flex;align-items:baseline;gap:8px;min-width:180px}
.s3cell b{font-family:ui-monospace,Menlo,monospace;font-size:19px;
font-weight:700}
.s3cell span{font-size:11px;color:var(--dm)}
.s3cell.s3e{border-left:3px solid var(--bad)}.s3cell.s3e b{color:var(--bad)}
.s3cell.s3d{border-left:3px solid var(--ac)}.s3cell.s3d b{color:var(--ac)}
.s3cell.s3w{border-left:3px solid var(--warnc)}.s3cell.s3w b{color:var(--warnc)}
.s2parts{display:grid;grid-template-columns:1fr;gap:4px}
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
.s2crawl{text-align:right;display:flex;flex-direction:column;gap:5px;
align-items:flex-end}
.s2cn{margin:0;font-size:13px}.s2cw{margin:0;font-size:11px;color:var(--ft)}
.s2note{grid-column:1/-1;margin:2px 0 0;font-size:11.5px;color:var(--ft)}
/* ---- issues ---- */
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
.s2sev{font-size:9.5px;font-weight:800;letter-spacing:.09em;
text-transform:uppercase;width:62px;flex:none}
.s2sev.s2bad{color:var(--bad)}.s2sev.s2warn{color:var(--warnc)}
.s2sev.s2none{color:var(--ft)}
.s2code{flex:1;font-size:13.5px;text-transform:capitalize;min-width:0;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.s2n{font-size:12px;color:var(--dm);white-space:nowrap}
.s2act{flex:none;display:flex;gap:6px;align-items:center}
.s2clean{font-size:11px;color:var(--ft)}
.s2body{padding:2px 14px 14px 76px;border-top:1px solid var(--ln)}
.s2why{margin:10px 0 6px;font-size:13px;line-height:1.6;color:var(--dm);
max-width:66ch}
.s2does{margin:0 0 8px;font-size:12.5px;line-height:1.55;color:var(--tx);
max-width:66ch}
.s2urls{margin:6px 0 0;padding:0 0 0 16px;font-size:12px;line-height:1.75}
.s2urls a{color:var(--ac);text-decoration:none}
.s2urls a:hover{text-decoration:underline}
.s2ev,.s2prop{display:block;color:var(--ft);font-size:11px}
.s2prop{color:var(--okc)}
.s2more{color:var(--ft);list-style:none}
.s2man{margin:8px 0 0;font-size:12.5px;color:var(--dm)}
.s2h4{font-size:12px;letter-spacing:.08em;text-transform:uppercase;
color:var(--ft);margin:18px 0 8px}
.s2meas{margin-top:26px;border-top:1px solid var(--ln);padding-top:6px}
.s2meas h4{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ft);margin:10px 0 4px}
.s2bulk{border:1px solid var(--ln);border-left:3px solid var(--ac);
border-radius:8px;padding:12px 14px;margin:0 0 14px;display:flex;gap:10px;
align-items:center;flex-wrap:wrap;background:var(--card)}
.s2bulk p{margin:0;font-size:13px;flex:1;min-width:220px}
.s2empty{font-size:13px;color:var(--ft);padding:12px 10px;margin:0;
line-height:1.55}
/* base for every button on these screens */
.s2act .cta,.s2bulk .cta,.s2crawl .cta,.s3band .cta,.s3panel .cta,
.s3fx .cta,.s3door .cta,.s3aeohd .cta,.s3ck .cta{font-size:11.5px;
padding:4px 10px;border:1px solid var(--ln);border-radius:6px;
background:var(--card);color:var(--tx);cursor:pointer;font-family:inherit;
white-space:nowrap}
.s2act .cta:hover,.s3fx .cta:hover{filter:brightness(1.08)}
.s2act .cta[disabled],.s3fx .cta[disabled]{opacity:.55;cursor:default}
.cta.a2now{border-color:var(--okc);color:var(--okc)}
.cta.a2body{border-color:var(--warnc);color:var(--warnc)}
.cta.a2draft{border-color:var(--ac);color:var(--ac)}
.cta.a2manual{border-style:dashed;border-color:var(--ft);color:var(--ft)}
/* ---- pages ---- */
.s3pg{border:1px solid var(--ln);border-radius:8px;margin:0 0 6px;
background:var(--card);overflow:hidden}
.s3pr{display:flex;align-items:center;gap:12px;padding:9px 12px;cursor:pointer}
.s3pr:hover{background:var(--hov)}
.s3pill{font-family:ui-monospace,Menlo,monospace;font-size:10px;
font-weight:700;border-radius:8px;padding:2px 8px;background:var(--warnbg);
color:var(--warnc);flex:none}
.s3pill.s3pe{background:var(--badbg);color:var(--bad)}
.s3url{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;color:var(--ac);text-decoration:none;font-size:12.5px}
.s3url:hover{text-decoration:underline}
.s3fx{display:flex;gap:12px;align-items:center;padding:6px 0;font-size:12.5px;
border-bottom:1px solid var(--ln)}
.s3fx:last-child{border-bottom:0}
.s3fx .s2sev{width:52px}
.s3fxn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.s3fxn.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.s3prop{font-style:normal;font-size:10px;color:var(--okc);
font-family:ui-monospace,monospace}
.s3fxw{flex:1.2;min-width:0;color:var(--ft);font-size:11.5px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.s3door{margin:14px 0 0}
/* ---- robots / llms / two-up panels ---- */
.s3two{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 16px}
.s3panel{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:13px 15px}
.s3chk{display:flex;gap:9px;align-items:center;font-size:12.5px;padding:5px 0}
.s3chk i{width:15px;height:15px;border-radius:50%;flex:none;display:flex;
align-items:center;justify-content:center;color:#fff;font-size:9px;
font-style:normal}
.s3chk i.y{background:var(--okc)}.s3chk i.n{background:var(--bad)}
.s3chk i.q{background:var(--ft)}
.s3bots{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));
gap:7px;margin-top:6px}
.s3bot{display:flex;gap:8px;align-items:center;border:1px solid var(--ln);
border-radius:8px;padding:7px 10px;font-size:12px}
.s3bot i{width:8px;height:8px;border-radius:50%;flex:none}
.s3bot span{margin-left:auto;font-family:ui-monospace,monospace;
font-size:10.5px;color:var(--ft)}
/* ---- stats / banner ---- */
.s3banner{border:1px dashed var(--warnc);background:var(--warnbg);
color:var(--warnc);border-radius:9px;padding:9px 13px;font-size:12.5px;
margin:0 0 12px}
.s3stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
gap:9px}
.s3stat{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:10px 13px;display:flex;flex-direction:column;gap:4px}
.s3stat b{font-family:ui-monospace,Menlo,monospace;font-size:20px;
font-weight:700;line-height:1}
.s3d{font-size:10.5px;color:var(--ft)}
.s3aeohd{display:flex;gap:16px;align-items:center;justify-content:space-between;
flex-wrap:wrap;margin:0 0 14px}
/* ---- the cockpit card ---- */
.s3ck{display:flex;gap:13px;align-items:center;flex-wrap:wrap;
border:1px solid var(--ln);border-left:3px solid var(--bad);border-radius:9px;
background:var(--card);padding:10px 13px;margin:0 0 7px}
.s3ckring{flex:none;color:var(--bad)}
.s3ckt{flex:1;min-width:200px;display:flex;flex-direction:column;gap:1px}
.s3ckt b{font-size:13.5px}
.s3ckt span{font-size:11.5px;color:var(--dm)}
@media (max-width:900px){.s2hd{grid-template-columns:1fr}
.s2crawl{text-align:left;align-items:flex-start}.s2body{padding-left:14px}
.s3two{grid-template-columns:1fr}}
"""

JS = ("<script>"
      "function s2open(c){var b=document.getElementById('b-'+c);"
      "if(b)b.style.display=(b.style.display==='none')?'block':'none';}"
      "function s2manual(c){var m=document.getElementById('s2m-'+c);"
      "if(m)m.style.display=(m.style.display==='none')?'block':'none';"
      "var b=document.getElementById('b-'+c);if(b)b.style.display='block';"
      "if(window.event)window.event.stopPropagation();}"
      # APPROVE drafted proposals - one POST per order to /seo/fix/{id}
      "async function s2fix(code,ids,btn){"
      "if(window.event)window.event.stopPropagation();"
      "var list=String(ids||'').split(',').filter(Boolean);"
      "if(!list.length){toast('Nothing drafted for '+code);return;}"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Publishing\\u2026';}"
      "var ok=0,bad=0,last='';"
      "for(var i=0;i<list.length;i++){try{"
      "var r=await fetch('/seo/fix/'+list[i],{method:'POST'});"
      "var j=await r.json();"
      "if(j&&(j.ok!==false)&&(j.status==='done'||j.applied||j.ok)){ok++;}"
      "else{bad++;last=(j&&(j.result||j.error))||'refused';}"
      "}catch(e){bad++;last='could not reach the engine';}}"
      "if(btn){btn.disabled=false;btn.textContent=lab;}"
      "toast(ok+' published'+(bad?(', '+bad+' could not be: '+last):'')"
      "+(ok?'. Re-run the checks to see the score move.':''),!bad);}"
      # RUN a set of orders through the fixer's dispatch: applies what it
      # may, drafts what needs you. One POST, one report.
      "async function s3run(ids,btn){"
      "if(window.event)window.event.stopPropagation();"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}"
      "try{var r=await fetch('/seo/run-orders',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({ids:String(ids||'').split(',').filter(Boolean)})});"
      "var j=await r.json();"
      "toast((j&&j.message)||JSON.stringify(j).slice(0,140),j&&j.ok!==false);"
      "}catch(e){toast('could not reach the engine \\u2014 nothing changed',"
      "false);}if(btn){btn.disabled=false;btn.textContent=lab;}}"
      # FIX ONE PAGE: everything fixable on a URL through the same dispatch
      "async function s3fixpage(url,btn){"
      "if(window.event)window.event.stopPropagation();"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}"
      "try{var r=await fetch('/seo/fix-page',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({url:url})});var j=await r.json();"
      "toast((j&&j.message)||'done',j&&j.ok!==false);}"
      "catch(e){toast('could not reach the engine \\u2014 nothing changed',"
      "false);}if(btn){btn.disabled=false;btn.textContent=lab;}}"
      # DRAFT EVERYTHING the agent may not apply alone (LLM cost capped)
      "async function s3draftall(btn){"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Drafting\\u2026';}"
      "try{var r=await fetch('/seo/draft-all',{method:'POST'});"
      "var j=await r.json();"
      "toast((j&&j.message)||'drafting ran',j&&j.ok!==false);}"
      "catch(e){toast('could not reach the engine \\u2014 nothing changed',"
      "false);}if(btn){btn.disabled=false;btn.textContent=lab;}}"
      # THE LADDER - the same /seo/auto switch the scheduler obeys
      "async function seoAutoSet(level,btn){"
      "try{var r=await fetch('/seo/auto',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({level:level})});var j=await r.json();"
      "toast((j&&(j.message||j.error))||('level '+level),j&&j.ok!==false);"
      "if(j&&j.ok!==false&&btn&&btn.parentNode){"
      "btn.parentNode.querySelectorAll('.s3lvl').forEach(function(x){"
      "x.classList.remove('s3on');});btn.classList.add('s3on');}}"
      "catch(e){toast('could not reach the engine \\u2014 the switch is "
      "unchanged',false);}}"
      # Buttons whose actions wait on the wiring round. A silent
      # dead button reads as broken; these say what they wait for.
      # THE WIRING ROUND ARRIVED. Each of these posts to an endpoint the
      # API already serves - ssRerun was the founder's own report, and
      # /aeo/probe had been sitting there the whole time. The three with
      # no endpoint still say so instead of pretending.
      "function uiNotWired(n){var m=n+': there is no endpoint for this yet. It is on the build list, not silently broken.';if(window.toast)toast(m);else alert(m);}"
      "function ssPost(u,body,btn,ask){"
      "if(ask&&!confirm(ask))return;"
      "var b=btn||(window.event&&window.event.target)||null;"
      "if(b&&b.tagName!=='BUTTON'&&b.closest)b=b.closest('button');"
      "var old=b?b.textContent:'';if(b){b.disabled=true;b.textContent='Working…';}"
      "fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify(body||{})})"
      ".then(function(r){return r.json().catch(function(){return {};});})"
      ".then(function(j){var ok=(j.ok!==false)&&!j.error;"
      "if(window.toast)toast(ok?(j.message||'Done.'):('Failed: '+(j.error||'unknown')));"
      "if(ok&&window.keepPlace)keepPlace();"
      "else if(b){b.disabled=false;b.textContent=old;}})"
      ".catch(function(e){if(window.toast)toast('Failed: '+e);"
      "if(b){b.disabled=false;b.textContent=old;}});}"
      "function ssRerun(a,btn){ssPost('/aeo/probe',{},btn,"
      "'Ask every connected AI engine your tracked prompts again? It costs a few model calls.');}"
      "function ssPrompts(a,btn){var p=prompt('One prompt per line - what should we watch AI engines answer?');"
      "if(!p)return;ssPost('/aeo/prompts',{prompts:p.split('\\n').filter(Boolean)},btn);}"
      "function ssCmd(id,btn){ssPost('/searchos/execute',{id:id},btn);}"
      "function ssDraft(a,btn){ssPost('/seo/draft-all',{},btn,"
      "'Draft the pending changes? Nothing goes live until you approve it.');}"
      "function ssResearch(a,btn){ssPost('/competitors/scan',{},btn);}"
      "function ssCompetitors(a,btn){ssPost('/competitors/scan',{},btn);}"
      "function ssDomain(a,btn){ssPost('/competitors/scan',{},btn);}"
      "function ssTrack(a,btn){ssPost('/seo/ranks',{},btn,"
      "'Check where you rank right now?');}"
      "function ssKeywords(a,btn){ssPost('/seo/crawl',{},btn,"
      "'Crawl the site to refresh what it covers?');}"
      # a filter over rows already on the page: no endpoint, no reload
      "function ssSearch(a){try{var q=(document.getElementById('ss-q')||{}).value||'';"
      "q=q.toLowerCase();var n=0;"
      "document.querySelectorAll('.ss-row,.ss-tbl tbody tr').forEach(function(r){"
      "var hit=!q||r.textContent.toLowerCase().indexOf(q)>=0;"
      "r.style.display=hit?'':'none';if(hit)n++;});"
      "if(window.toast)toast(n+' row(s) match');}catch(e){}}"
      # THE ORPHANS: called by these screens, defined nowhere, silent on
      # every click. Wired where the endpoint is unambiguous.
      "function ssFix(id,btn){ssPost('/seo/fix/'+encodeURIComponent(id),{},btn,"
      "'Apply this fix to the live site?');}"
      "function ssPage(u,btn){ssPost('/seo/fix-page',{url:u},btn,"
      "'Fix this page now?');}"
      "function ssPublish(id,btn){ssPost('/jobs/'+encodeURIComponent(id)+'/approve',{},btn,"
      "'Approve and publish this piece?');}"
      "function ssAnswer(id,btn){ssPost('/replies/answer',{id:id},btn);}"
      "function ssDecay(a,btn){ssPost('/seo/crawl',{},btn,"
      "'Re-crawl to see what has decayed?');}"
      # nothing serves these yet - each says so instead of failing quietly
      "function ssReport(a,btn){ssPost('/seo/report',{},btn);}"
      "function ssBriefFill(a){uiNotWired('Generate the missing brief parts')}"
      # /seo/brief exists now, so these save for real
      "function ssBrief(k){var t=prompt('The brief for '+(k||'this page')+':');"
      "if(t===null)return;ssPost('/seo/brief',{key:k||'default',text:t});}"
      "function ssBriefSave(k,btn){var el=document.getElementById('ss-brief');"
      "if(!el){ssBrief(k);return;}"
      "ssPost('/seo/brief',{key:k||'default',text:el.value},btn);}"
      "function ssSave(id,btn){var el=document.getElementById('ss-edit');"
      "if(!el){if(window.toast)toast('nothing to save on this screen');return;}"
      "ssPost('/content/save',{job_id:id,field:'body',text:el.value},btn);}"
      "</script>")
