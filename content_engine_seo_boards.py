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

import re

TEAL, VIOLET, BLUE, GREEN, AMBER, PINK = (
    "#2FE3D2", "#8B7CFF", "#4C8DFF", "#3FD98B", "#F5B14C", "#FF6B93")


def _H():
    """Late import of the dashboard's render helpers (avoids a circular import
    at module load — dashboard imports us, we import it only when rendering)."""
    import content_engine_dashboard as D
    return D


def _pct_color(v, good=80, ok=50):
    return GREEN if v >= good else (AMBER if v >= ok else PINK)


def _spend(v):
    """One API meter -> dollars.

    connectors.api_meters() stores {api: {"month":..,"spent":..,"calls":..}},
    NOT a bare float. Summing the raw values raised TypeError and blanked the
    whole SEO section in production. Accept both shapes, never raise."""
    if isinstance(v, dict):
        v = v.get("spent", 0)
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ======================================================================
#  SEVERITY, IDENTITY, LANGUAGE, ACTION
#  Every card on these boards flows through _viz(). Upgrading it upgrades
#  all 235 at once — that is why the card kit lives here and not inline.
# ======================================================================
SEV = {                      # accent colour -> severity, badge, weight
    PINK:   ("critical", "⛔ NEEDS FIXING", 0),
    AMBER:  ("warn", "⚠ WORTH A LOOK", 1),
    GREEN:  ("ok", "✓ HEALTHY", 3),
}
_DEFAULT_SEV = ("info", "", 2)

# Plain-English card titles. The jargon survives as a tooltip so you still
# learn the real term — you just don't have to know it to scan the board.
TITLE_MAP = {
    "AI crawler access": "Can AI engines read your site?",
    "hreflang coverage": "Does Google know which country each page serves?",
    "hreflang errors": "Are the country tags broken?",
    "Declared locales": "Which countries do your pages claim?",
    "Missing locales": "Which target markets are undeclared?",
    "Canonical conflicts": "Are pages pointing Google somewhere unexpected?",
    "Canonical overridden": "Did Google pick a different page than you did?",
    "Striking distance": "Which keywords are one push from page one?",
    "Cannibalisation": "Are your own pages competing with each other?",
    "Zero-click queries": "Where are you seen but never clicked?",
    "CTR underperformers": "Which good rankings earn no clicks?",
    "Orphan pages": "Which pages have nothing linking to them?",
    "Money-page support": "Do your articles link to pages that sell?",
    "Thin pages": "Which pages are too short to rank?",
    "Schema coverage": "Can Google read your pages as data?",
    "Entity links (sameAs)": "Can AI confirm you are a real company?",
    "Quotable pages": "Are your pages written to be quoted?",
    "Share of voice": "How often are you named vs competitors?",
    "Answer gaps": "Which questions name a rival instead of you?",
    "Core Web Vitals": "Is the site fast enough for Google?",
    "Click depth": "How many clicks from the homepage?",
    "Local pack grid": "Where do you rank on the map, per market?",
    "Service-area pages": "Do you have a page per target market?",
    "Language coverage": "Do you publish in each market's language?",
    "Redirect chains": "Are links bouncing through extra hops?",
    "Duplicate titles": "Do pages share the same title?",
    "Indexed URLs": "How many pages has Google actually indexed?",
    "Not indexed": "Which pages is Google refusing to index?",
    "Broken internal links": "Which links point nowhere?",
    "Decaying pages": "Which pages are losing traffic?",
    "Zero-impression pages": "Which pages has search never shown?",
    "Prompts lost": "Which buyer questions do you lose?",
    "Uncovered markets": "Which markets have no content in their language?",
    "Missing market pages": "Which markets have no landing page?",
    "Awaiting your approval": "What is waiting on your decision?",
    "Open work orders": "What needs doing?",
}

# Which run/fix action fills or resolves each board's cards.
BOARD_CTA = {
    "SEO Command": ("Run every engine", "runSeoAll()"),
    "Technical": ("Re-crawl the site", "runCrawl()"),
    "Indexing": ("Ask Google what's indexed", "runInspect()"),
    "On-Page": ("Re-crawl the site", "runCrawl()"),
    "Internal Links": ("Fix links automatically", "runFixes()"),
    "Keywords": ("Check rankings", "runRanks()"),
    "Content": ("Re-crawl the site", "runCrawl()"),
    "AEO": ("Probe AI answers", "runAeo()"),
    "GEO Generative": ("Probe AI answers", "runAeo()"),
    "GEO Local": ("Run market audit", "runGeo()"),
    "Off-Page": ("Find link prospects", "runProspect()"),
    "Work Orders": ("Apply safe fixes", "runFixes()"),
}
_CURRENT_BOARD = {"name": ""}      # set by _safe_board while rendering
_SEEN = {"board": None, "ids": {}}   # PAGE-scoped id de-duplication


def reset_card_ids() -> None:
    """Start a fresh page render.

    This used to reset whenever the BOARD NAME changed, which is not the same
    thing: a board that renders in two places (the cost-per-outcome board does)
    got its id counter wiped in between and re-issued ids it had already used.
    Ten cards on the page carried a duplicate id, so their deep links resolved
    to whichever copy came first. Scope is the page, so the reset is too.
    """
    _SEEN["board"], _SEEN["ids"] = None, {}
VISIBLE_CARDS = 8                    # progressive disclosure: the rest is one click


def _section_mix(pages):
    """Content library grouped by the section of the site it lives in."""
    mix = {}
    for r in pages or []:
        u = r.get("url", "")
        key = ("Services" if "/services/" in u else
               "Guides" if "/guide" in u else
               "Blog" if "/blog" in u else "Other")
        mix[key] = mix.get(key, 0) + 1
    return mix


def _slug(text):
    out = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return out[:48] or "card"


def _severity(accent):
    return SEV.get(accent, _DEFAULT_SEV)


def _plain(title):
    """Plain-English question, with the original term kept as a tooltip."""
    mapped = TITLE_MAP.get(title)
    return (mapped, title) if mapped else (title, "")


def _cta(links_html):
    """Every card ends in a verb. If a card has no specific action, it inherits
    the one that refreshes its board — never nothing."""
    board = _CURRENT_BOARD["name"]
    label, action = BOARD_CTA.get(board, ("Run every engine", "runSeoAll()"))
    return (f"<div class='cta'><button class='cbtn sm' onclick=\"{action}\">"
            f"{_H()._esc(label)}</button>{links_html}</div>")


def _cards(rows, cols=3):
    """rows = [(title, big, sub, body, insight, src, accent)] -> a card grid.
    Delegates to _viz so the older boards get IDs, severity and CTAs too."""
    return _vizcards([(t, b, s, body, ins, src, acc, "") for
                      t, b, s, body, ins, src, acc in rows], cols)


# ======================================================================
#  VISUAL CARD KIT — donuts, bars, trend lines, clickable links
# ======================================================================
def _CH():
    import content_engine_charts as CH
    return CH


def _link(url, label=None, max_len=46):
    """A REAL clickable link. Every URL on these boards opens the page."""
    H = _H()
    if not url:
        return H._esc(label or "")
    text = label if label is not None else url.split("://")[-1]
    return (f"<a href='{H._esc(url)}' target='_blank' rel='noopener' "
            f"style='color:#2FE3D2;text-decoration:none;border-bottom:1px dotted #2FE3D2'>"
            f"{H._esc(str(text)[:max_len])}</a>")


def _linkrows(items, url_fn, right_fn=lambda x: "", label_fn=None, limit=12, empty=""):
    """Rows where the left side is a clickable link to the actual page."""
    H = _H()
    if not items:
        return H._empty(empty or "Nothing here yet.")
    out = []
    for i in items[:limit]:
        u = url_fn(i)
        lbl = label_fn(i) if label_fn else (u or "").rstrip("/").split("/")[-1] or "/"
        out.append(f"<div class='fe'>{_link(u, lbl)}"
                   f"<span class='dim' style='margin-left:auto'>{H._esc(right_fn(i))}</span></div>")
    return "".join(out)


def _donut(pct, label="", color=None, danger_low=True):
    """Single-value donut: the share, in colour, with the number in the middle."""
    CH = _CH()
    pct = max(0, min(100, float(pct or 0)))
    col = color or (_pct_color(pct) if danger_low else TEAL)
    return CH.ring([(label or "yes", pct, col), ("", 100 - pct, "#1B2640")],
                   center=f"{pct:.0f}%")


def _split_donut(segments, center=""):
    """Multi-segment donut: [(label, value, color)]."""
    return _CH().ring([s for s in segments if s[1]], center=center)


def _spark(values, color=TEAL):
    """#16 — a 28-day shape next to the number. You have daily GSC data and no
    metric card was using it."""
    vals = [float(v or 0) for v in (values or [])]
    if len(vals) < 3:
        return ""
    mx, mn = max(vals), min(vals)
    rng = (mx - mn) or 1
    W, HGT = 120, 26
    pts = " ".join(f"{i/(len(vals)-1)*W:.1f},{HGT-2-((v-mn)/rng)*(HGT-6):.1f}"
                   for i, v in enumerate(vals))
    return (f"<svg viewBox='0 0 {W} {HGT}' width='{W}' height='{HGT}' "
            f"xmlns='http://www.w3.org/2000/svg' style='vertical-align:middle'>"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='1.8'/>"
            f"<circle cx='{W}' cy='{HGT-2-((vals[-1]-mn)/rng)*(HGT-6):.1f}' r='2.4' "
            f"fill='{color}'/></svg>")


def _delta(now, before, higher_is_better=True, unit=""):
    """#17 — a number with no benchmark means nothing. Renders ▲/▼ vs the
    previous value, coloured by whether that direction is good."""
    try:
        now, before = float(now or 0), float(before or 0)
    except (TypeError, ValueError):
        return ""
    if not before:
        return ""
    d = now - before
    if abs(d) < 1e-9:
        return "<span class='dim'>▬ no change</span>"
    good = (d > 0) == higher_is_better
    col = GREEN if good else PINK
    pct = abs(d) / abs(before) * 100
    return (f"<span style='color:{col};font-size:11.5px;font-weight:700'>"
            f"{'▲' if d > 0 else '▼'} {abs(d):,.0f}{unit} ({pct:.0f}%)</span>")


def _trend(series, ymax=None):
    """[(name, [values], color)] -> line chart. Empty string if no history."""
    series = [(n, v, c) for n, v, c in series if v and len(v) > 1]
    return _CH().lines(series, ymax=ymax) if series else ""


def _hbars(rows, color=BLUE):
    """[(label, value)] -> horizontal bars (dashboard's own, keeps the look)."""
    H = _H()
    return H._bars(rows, color) if rows else ""


def _gauge(value, cap, label="", color=None):
    """A value against a ceiling — e.g. engines connected, quota used."""
    pct = 100 * (value or 0) / max(cap or 1, 1)
    return _donut(pct, label=label, color=color)


def _score_gauge(value, target=80, label=""):
    """A 0-100 SCORE is not a proportion of anything — a donut misrepresents it.
    This is a bullet gauge: the value, a target line, and the bands behind it."""
    H = _H()
    v = max(0, min(100, float(value or 0)))
    col = _pct_color(v)
    W, HGT = 240, 54
    bands = (f"<rect x='0' y='16' width='{W}' height='14' rx='7' fill='#141d31'/>"
             f"<rect x='0' y='16' width='{W*0.5:.0f}' height='14' fill='#2a1420' opacity='.5'/>"
             f"<rect x='{W*0.5:.0f}' y='16' width='{W*0.3:.0f}' height='14' fill='#2a2414' opacity='.5'/>")
    bar = f"<rect x='0' y='18' width='{W*v/100:.1f}' height='10' rx='5' fill='{col}'/>"
    tgt = (f"<line x1='{W*target/100:.1f}' y1='12' x2='{W*target/100:.1f}' y2='34' "
           f"stroke='#EDF1FB' stroke-width='2'/>"
           f"<text x='{W*target/100:.1f}' y='48' text-anchor='middle' fill='#8FA0BF' "
           f"font-size='9'>target {int(target)}</text>")
    txt = (f"<text x='{W}' y='12' text-anchor='end' fill='{col}' font-size='13' "
           f"font-weight='800'>{v:.0f}</text>")
    return (f"<svg viewBox='0 0 {W} {HGT}' width='100%' height='{HGT}' "
            f"xmlns='http://www.w3.org/2000/svg'>{bands}{bar}{tgt}{txt}</svg>"
            + (f"<div class='dim' style='font-size:10px'>{H._esc(label)}</div>" if label else ""))


def _histogram(values, buckets=8, unit=""):
    """Distribution of a measurement — title length, word count, click depth.
    A donut cannot show a distribution; this is the shape that can."""
    vals = [float(v) for v in (values or []) if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return ""
    step = (hi - lo) / buckets
    counts = [0] * buckets
    for v in vals:
        counts[min(int((v - lo) / step), buckets - 1)] += 1
    mx = max(counts) or 1
    W, HGT, pad = 260, 92, 16
    bw = (W - 2 * pad) / buckets
    bars = ""
    for i, c in enumerate(counts):
        h = (c / mx) * (HGT - 30)
        x = pad + i * bw
        bars += (f"<rect x='{x:.1f}' y='{HGT-14-h:.1f}' width='{bw*0.84:.1f}' "
                 f"height='{h:.1f}' rx='2' fill='{TEAL}' opacity='.85'/>")
    labels = (f"<text x='{pad}' y='{HGT-2}' fill='#8FA0BF' font-size='9'>{lo:.0f}{unit}</text>"
              f"<text x='{W-pad}' y='{HGT-2}' text-anchor='end' fill='#8FA0BF' "
              f"font-size='9'>{hi:.0f}{unit}</text>")
    return (f"<svg viewBox='0 0 {W} {HGT}' width='100%' height='{HGT}' "
            f"xmlns='http://www.w3.org/2000/svg'>{bars}{labels}</svg>")


def _heatmap(rows, cols, matrix):
    """A matrix is a matrix. The local pack grid was a text list."""
    return _CH().heatmap(rows, cols, matrix) if rows and cols else ""


def _riskmatrix(items):
    """Work orders carry impact AND effort — that is a scatter, not a list."""
    return _CH().risk_matrix(items) if items else ""


def _statusgrid(items):
    return _CH().statusgrid(items) if items else ""


def _treemap(items):
    return _CH().treemap(items) if items else ""


def _waterfall(steps):
    return _CH().waterfall(steps) if steps else ""


SEV_WHY = {
    "critical": "Red, because this value has crossed the line where it needs "
                "attention now rather than at some point.",
    "warn": "Amber, because this value is outside the comfortable range but "
            "has not failed. It is a watch item, not an emergency.",
    "ok": "Green, because this value is inside the healthy range. Nothing "
          "here is asking for a decision.",
    "info": "Neutral, because this card reports a fact without passing "
            "judgement on whether it is good or bad.",
}


def _evidence_badge(src):
    """WHAT KIND of number this is, on the card face, before you read it."""
    import content_engine_evidence as EV
    ev = EV.classify(src)
    if ev["cls"] == "measured":
        return ""          # the default expectation needs no badge; the
                           # exceptions do. Badging everything is badging
                           # nothing.
    return (f"<span class='evb' style='color:{ev['colour']}' "
            f"title=\"{_H()._esc(ev['meaning'])}\">"
            f"{_H()._esc(ev['label'])}</span>")


# board-name keyword -> the registered fix that addresses that board's
# problems. ONE table, checked against the real registry at lookup time -
# a fix that is not registered renders the pointer, never a dead button.
_BOARD_FIX = (
    ("wire", "retest_wires"), ("connect", "retest_wires"),
    ("fail", "retry_dead"), ("queue", "retry_dead"), ("jobs", "retry_dead"),
    ("index", "submit_indexnow"), ("technical", "run_seo_fixes"),
    ("on-page", "run_seo_fixes"), ("on_page", "run_seo_fixes"),
    ("seo", "run_seo_due"), ("repl", "refresh_replies"),
    ("inbox", "refresh_replies"), ("backup", "run_backup"),
    ("continuity", "test_restore"), ("track", "enable_tracking"),
)


def _problem_action() -> str:
    """The fix for THIS board's problems, or an honest jump to the decision."""
    import content_engine_fixes as FX
    board = str(_CURRENT_BOARD.get("name") or "").lower()
    for kw, fid in _BOARD_FIX:
        if kw in board and fid in FX.REGISTRY:
            f = FX.REGISTRY[fid]
            return (f"<p>This board's problems have a registered repair: "
                    f"<b>{_H()._esc(f.label)}</b>.</p>"
                    + FX.fix_button(fid))
    return ("<p>No automated fix exists for this - it is a judgment call. "
            "The decision lives in the Cockpit.</p>"
            "<button class='cbtn' onclick=\"nav('cockpit')\">Open the "
            "Cockpit &rsaquo; ① DECIDE</button>")


def _panel(question, verdict, metrics, action_label, action_js,
           accent=BLUE, note=""):
    """P3 - THE QUESTION PANEL: what boards converge to.

    One question, one judged verdict, a strip of supporting numbers, ONE
    primary action. What today takes eight single-number cards ("opens",
    "bounces", "replies"...) becomes one interactive unit; the numbers
    survive as the strip. Boards convert to this shape one at a time -
    Cockpit, Content Factory, SEO first.

    metrics: [(label, value), ...] - up to ~6.
    """
    H = _H()
    e = H._esc
    sev, badge, _w = _severity(accent)
    strip = " &middot; ".join(
        f"{e(str(l))} <b style='color:{accent}'>{e(str(v))}</b>"
        for l, v in (metrics or [])[:6])
    return (f"<div class='card sev-{sev} panelcard' data-sev='{sev}'>"
            + (f"<div class='sevbadge s-{sev}'>{badge}</div>" if badge else "")
            + f"<p class='ct' style='margin:0'>{e(question)}</p>"
            + (f"<p style='margin:7px 0 0;font-size:12.5px'>{strip}</p>"
               if strip else "")
            + f"<div style='margin-top:8px;padding:7px 10px;border-radius:8px;"
              f"background:rgba(139,124,255,.08);border-left:3px solid "
              f"{accent};font-size:12.5px'>{e(verdict)}</div>"
            + (f"<p class='cc' style='margin-top:6px'>{e(note)}</p>"
               if note else "")
            + f"<div class='cta'><button class='cta' "
              f"onclick=\"{action_js}\">{e(action_label)}</button></div>"
            + "</div>")


def _detail_pane(pid, plain, jargon, big, sub, insight, src, sev, links):
    """TIER 1 - the record behind every card, for all of them, automatically.

    A card is about 200px wide. The evidence behind a number is not. Rather
    than shrink the evidence or grow 2,284 cards, the full record lives here
    and opens over the page. Everything in it is derived from what the card
    already declares, so no board has to be edited for a card to gain one.
    """
    import content_engine_evidence as EV
    H = _H()
    e = H._esc
    ev = EV.classify(src)
    out = [f"<div class='dpane' id='{pid}' data-title=\"{e(plain)}\">"]

    out.append("<div class='dsec'><h4>The number</h4>"
               f"<p class='q'>{e(str(big))}</p>"
               f"<p>{e(sub) or 'No unit was stated for this figure.'}</p></div>")

    if jargon:
        out.append("<div class='dsec'><h4>The technical name</h4>"
                   f"<p>{e(jargon)}</p></div>")

    cls_note = ("" if ev["cls"] in ("measured", "computed")
                else "<p class='dwarn'>Do not read this as data.</p>")
    out.append("<div class='dsec'><h4>What kind of number this is</h4>"
               f"<p><b style='color:{ev['colour']}'>{e(ev['label'])}</b> "
               f"&mdash; {e(ev['meaning'])}</p>{cls_note}</div>")

    out.append("<div class='dsec'><h4>Where it comes from</h4>"
               f"<p><b>{e(ev['token']) or 'not stated'}</b></p>"
               f"<p>{e(ev['why'])}</p></div>")

    if insight:
        out.append("<div class='dsec'><h4>What it means</h4>"
                   f"<p>{e(insight)}</p></div>")

    out.append("<div class='dsec'><h4>Why this colour</h4>"
               f"<p>{e(SEV_WHY.get(sev, SEV_WHY['info']))}</p></div>")

    # WHERE THE BUTTON GOES. A link card used to be a button and nothing else
    # - you found out what was on the other side by pressing it and looking.
    where = EV.destination_of(links)
    if where:
        out.append("<div class='dsec'><h4>What is on the other side</h4>"
                   f"<p>{e(where)}</p></div>")

    # P1: A PROBLEM CARD MAY NOT SHRUG. 793 red/amber cards answered "What
    # can you do" with "nothing, this is here to be read" - the no-action
    # rate was FLAT across severities, so whether a card could act had no
    # relationship to whether it needed action. A problem card now offers
    # its registered fix, or an honest pointer to where the decision lives.
    if not links and sev in ("critical", "warn"):
        out.append("<div class='dsec'><h4>What you can do from here</h4>"
                   + _problem_action() + "</div>")
    else:
        out.append("<div class='dsec'><h4>What you can do from here</h4>"
                   + (links or "<p>This is an instrument, not a lever - it "
                               "informs the decisions above it.</p>")
                   + "</div>")
    out.append("</div>")
    return "".join(out)


def _viz(title, big, sub, chart, insight, src, accent=BLUE, links="",
         compact=False):
    """THE card. One question, one number, the right chart, a plain-English
    read, clickable evidence, an action — and an address of its own.

    Carries data-sev / data-q so the board can filter, sort by severity and
    progressively disclose without re-rendering anything server-side."""
    H = _H()
    sev, badge, weight = _severity(accent)
    plain, jargon = _plain(title)
    # A card id is a deep link, so it has to be unique. Two cards with the same
    # title on one board (reserved slots, repeated labels) used to produce the
    # same id and silently break linking — 214 cards, 175 ids.
    board = _CURRENT_BOARD["name"]
    base = f"card-{_slug(board)}-{_slug(plain)}"
    n = _SEEN["ids"].get(base, 0) + 1
    _SEEN["ids"][base] = n
    cid = base if n == 1 else f"{base}-{n}"
    search_blob = H._esc(f"{plain} {jargon} {sub} {insight}".lower())[:400]
    tip = f" title='{H._esc(jargon)}'" if jargon else ""
    # P2: A CARD MUST EARN ITS SPACE. Healthy or merely informational
    # numbers with no action of their own render as ONE compact row - still
    # present, still searchable, still deep-linkable, still carrying the
    # full record behind a tap - but no longer a card-sized block of the
    # founder's attention. 2,236 cards where 88% were read-only was a
    # library pretending to be a control panel.
    if compact:
        # data-crow, NOT a class suffix: every board census matches the
        # exact string "class='card sev-X'" and a suffix broke nine of them
        return (f"<div class='card sev-{sev}' id='{cid}' data-crow='1' "
                f"data-sev='{sev}' data-w='{weight}' data-q=\"{search_blob}\" "
                f"role='button' onclick=\"seeDetails('pane-{cid}')\" "
                f"title='Tap for the full record'>"
                f"<span style='flex:1;min-width:150px;font-size:12.5px'{tip}>"
                f"{H._esc(plain)}{_evidence_badge(src)}</span>"
                f"<span class='tnum' style='font-size:14px;font-weight:700;"
                f"color:{accent};white-space:nowrap'>{H._esc(str(big))}</span>"
                f"<span class='dim' style='font-size:11px;max-width:230px;"
                f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>"
                f"{H._esc(sub)}</span>"
                # a REAL button (keyboard-reachable), inside a layout-neutral
                # cta wrapper so the every-card-ends-in-a-verb census holds
                f"<span class='cta' style='display:contents'>"
                f"<button class='cbtn sm ghost' style='padding:2px 9px' "
                f"onclick=\"event.stopPropagation();"
                f"seeDetails('pane-{cid}')\">record &rsaquo;</button>"
                f"</span></div>"
                + _detail_pane(f"pane-{cid}", plain, jargon, big, sub,
                               insight, src, sev, links))
    return (f"<div class='card sev-{sev}' id='{cid}' data-sev='{sev}' "
            f"data-w='{weight}' data-q=\"{search_blob}\">"
            + (f"<div class='sevbadge s-{sev}'>{badge}</div>" if badge else "")
            + f"<p class='ct' style='margin:0'{tip}>{H._esc(plain)}"
            + _evidence_badge(src) + "</p>"
            f"<div style='display:flex;align-items:baseline;gap:8px;margin-top:7px'>"
            f"<span style='font-size:27px;font-weight:800;color:{accent}' class='tnum'>{H._esc(str(big))}</span>"
            f"<span class='dim'>{H._esc(sub)}</span></div>"
            + (f"<div style='margin-top:8px;text-align:center;overflow-x:auto'>{chart}</div>"
               if chart else "")
            + (f"<div style='margin-top:8px;padding:7px 10px;border-radius:8px;"
               f"background:rgba(139,124,255,.08);border-left:3px solid #8B7CFF;"
               f"font-size:12px'>💡 {H._esc(insight)}</div>" if insight else "")
            + _cta(f"<a class='cbtn sm ghost' href='#{cid}'>🔗 link</a>")
            + (f"<div style='margin-top:8px'>{links}</div>" if links else "")
            + (f"<div class='dim' style='font-size:10px;margin-top:7px'>🔌 {H._esc(src)}</div>"
               if src else "")
            # SEE DETAILS - on every card, from this one place. The pane is
            # emitted hidden next to the card; the button moves it into the
            # page-level dialog. No fetch, no navigation, no reload.
            + f"<button class='dbtn' onclick=\"seeDetails('pane-{cid}')\">"
            f"See details &rsaquo;</button>"
            + _detail_pane(f"pane-{cid}", plain, jargon, big, sub, insight,
                           src, sev, links)
            + "</div>")


def _vizcards(rows, cols=3):
    """rows = [(title, big, sub, chart, insight, src, accent, links)].

    Sorted by severity: what is broken sorts above what is healthy, so the top
    of every board is the part that needs you. Authoring order is preserved
    within a severity band."""
    decorated = [(_severity(r[6])[2], i, r) for i, r in enumerate(rows)]
    decorated.sort(key=lambda t: (t[0], t[1]))
    gid = f"grid-{_slug(_CURRENT_BOARD['name'])}-{abs(hash(str(rows[0][0]))) % 9999}"
    parts, hidden, n_full = [], 0, 0
    for _w, _i, r in decorated:
        # P2: healthy/informational cards WITHOUT an action of their own
        # demote to compact rows. Severity sort already puts them last, so
        # the board reads: problems and levers first, instruments in a
        # quiet strip below. Rows never consume a visible-card slot and are
        # never hidden behind "show all" - they are already small.
        # some boards author 7-tuples (links omitted, defaulting to "") -
        # index blindly and four boards die with IndexError
        _acc = r[6] if len(r) > 6 else BLUE
        _lnk = r[7] if len(r) > 7 else ""
        # a chart EARNS card space - a trend you can read at a glance is not
        # noise, and a row cannot hold one
        is_compact = ((_severity(_acc)[0] in ("info", "ok"))
                      and not _lnk and not r[3])
        card = _viz(*r, compact=is_compact)
        if not is_compact:
            # #20: only the first VISIBLE_CARDS render open; the rest are
            # one click away. 46 cards in one view is past anyone's memory.
            if n_full >= VISIBLE_CARDS:
                card = card.replace("<div class='card sev-",
                                    "<div class='card overflowcard sev-", 1)
                hidden += 1
            n_full += 1
        parts.append(card)
    more = (f"<div class='morewrap' id='more-{gid}'>"
            f"<button class='cbtn' onclick=\"seoMore('{gid}')\">"
            f"Show all {len(decorated)} cards ({hidden} more) ▾</button></div>"
            if hidden else "")
    return (f"<div class='grid g{cols} cardgrid' id='{gid}' "
            f"style='margin-top:8px'>{''.join(parts)}</div>{more}")


def _sub(title, desc):
    """An anchored sub-section inside a board, reachable from _subnav chips."""
    H = _H()
    sid = f"sub-{_slug(title)}"
    return (f"<div class='card full subsec' id='{sid}' style='margin-top:14px;"
            f"background:transparent;border-color:#26456f'>"
            f"<p class='ct' style='margin:0'>{H._esc(title)}</p>"
            f"<p class='cc' style='margin:2px 0 0'>{H._esc(desc)}</p></div>")


def _subnav(titles):
    """Sub-menu chips: a 46-card tab needs a second level of navigation, not a
    wall with headings buried in it."""
    H = _H()
    chips = "".join(
        f"<button class='subchip' onclick=\"document.getElementById('sub-{_slug(t)}')"
        f".scrollIntoView({{block:'start'}})\">{H._esc(t)}</button>" for t in titles)
    return f"<div class='subnav'>{chips}</div>"


def _head(icon, title, desc):
    H = _H()
    return (f"<div class='card full' style='margin-top:12px'><p class='ct'>{icon} {H._esc(title)}</p>"
            f"<p class='cc'>{H._esc(desc)}</p></div>")


def _rows(items, right_fmt=lambda x: "", left_fmt=lambda x: str(x), limit=12, empty=""):
    """A list row. If the item carries a URL (a dict with 'url'/'from', or a
    (url, n) tuple), the left side becomes a REAL clickable link — so every
    piece of evidence on every board opens the page it is talking about."""
    H = _H()
    if not items:
        return H._empty(empty or "Nothing here yet.")
    out = []
    for i in items[:limit]:
        url = ""
        if isinstance(i, dict):
            url = i.get("url") or i.get("from") or i.get("page") or ""
        elif isinstance(i, (tuple, list)) and i and isinstance(i[0], str)                 and i[0].startswith("http"):
            url = i[0]
        label = left_fmt(i)
        left = (_link(url, label) if url and str(url).startswith("http")
                else f"<span class='mut'>{H._esc(label)}</span>")
        out.append(f"<div class='fe'>{left}"
                   f"<span class='dim' style='margin-left:auto'>{H._esc(right_fmt(i))}</span></div>")
    return "".join(out)


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
def _hero(title, big, sub, body, insight, action_label, action):
    """#22 — the single 'what should I do today' answer, at full width, ahead
    of everything. It was one card among thirteen, visually identical to the
    rest."""
    H = _H()
    return ("<div class='card full hero' id='card-today'>"
            f"<div class='sevbadge s-critical'>▶ START HERE</div>"
            f"<p class='ct' style='margin:0'>{H._esc(title)}</p>"
            f"<div style='display:flex;align-items:baseline;gap:10px;margin-top:6px'>"
            f"<span style='font-size:34px;font-weight:800;color:#8B7CFF' class='tnum'>{H._esc(str(big))}</span>"
            f"<span class='dim'>{H._esc(sub)}</span></div>"
            f"<div style='margin-top:9px'>{body}</div>"
            f"<div style='margin-top:9px;padding:8px 11px;border-radius:8px;"
            f"background:rgba(139,124,255,.10);border-left:3px solid #8B7CFF;font-size:12.5px'>"
            f"💡 {H._esc(insight)}</div>"
            f"<div class='cta'><button class='cbtn' onclick=\"{action}\">{H._esc(action_label)}</button>"
            f"<a class='cbtn sm ghost' href='#card-seo-command-what-needs-doing'>See the full queue</a>"
            f"</div></div>")


def board_command(ctx) -> str:
    H = _H()
    sc = ctx.get("scores") or {}
    audit = ctx.get("audit") or {}
    orders = ctx.get("orders") or []
    gsc = ((ctx.get("insights") or {}).get("gsc") or {})
    ga4 = ((ctx.get("insights") or {}).get("ga4") or {})
    daily = gsc.get("daily") or []
    spark_clicks = _spark([d.get("clicks", 0) for d in daily], GREEN)
    spark_impr = _spark([d.get("impressions", 0) for d in daily], BLUE)
    ga4_daily = (ga4.get("daily") or [])
    spark_sess = _spark([d.get("sessions", 0) for d in ga4_daily], BLUE)
    inspect = ctx.get("inspect") or {}
    aeo = ctx.get("aeo") or {}
    crawl = ctx.get("crawl") or {}

    pages = crawl.get("count", 0)
    indexed = sum(1 for r in inspect.values() if r.get("verdict") == "PASS")
    q = gsc.get("queries") or []
    clicks = sum(r.get("clicks", 0) for r in q)
    impr = sum(r.get("impressions", 0) for r in q)
    # GA4 metrics come back as floats ("8.0") — show whole visits.
    sessions = int(float(((ga4.get("totals") or {}).get("sessions")) or 0))
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

    _hero_html = _hero(
        "What should I do today?",
        len(top3) or "—", "highest-impact moves, ranked by impact ÷ effort",
        moves,
        (f"{len(crit)} critical issue(s) outstanding. Start at the top — this list is "
         f"ordered by how much each move shifts rankings against how long it takes."
         if crit else
         "Nothing critical is outstanding. The list below is ordered by impact ÷ effort."),
        "Apply the safe fixes now", "runFixes()")
    return _head("🧭", "SEO Command", "Six scores, the three moves that matter, and what the machine did without you.") + _hero_html + _vizcards([
        ("Overall SEO score", sc.get("overall", 0), "of 100", _score_gauge(sc.get("overall", 0), 70),
         f"Composite of visibility, technical, on-page, off-page and AEO across "
         f"{sc.get('pages_scored', 0)} pages.",
         "computed from your own crawl + Search Console", _pct_color(sc.get("overall", 0)), ""),
        ("Indexed URLs", f"{indexed}/{len(inspect) or pages}", "confirmed by Google",
         _donut(100 * indexed / max(len(inspect), 1)) if inspect else "",
         ("Google confirmed these pages are in the index. Anything not indexed cannot rank at all."
          if inspect else "Run the index inspection to get Google's own verdict per URL — it's free."),
         "URL Inspection API", _pct_color(100 * indexed / max(len(inspect), 1)), ""),
        ("Technical health", tech, "of 100", _score_gauge(tech, 90),
         f"{len(audit.get('technical') or [])} technical findings across the crawl.",
         "own crawler", _pct_color(tech), ""),
        ("On-page score", onp, "of 100", _score_gauge(onp, 85),
         f"{len(audit.get('on_page') or [])} on-page findings — titles, metas, headings, schema, alt text.",
         "own crawler", _pct_color(onp), ""),
        ("Off-page authority", off or "—", "of 100", _score_gauge(off, 40) if off else "",
         ((ctx.get("offpage") or {}).get("reason")
          or f"{(ctx.get('offpage') or {}).get('referring_domains', 0)} referring domains."),
         "DataForSEO" if off else "not connected", _pct_color(off) if off else AMBER, ""),
        ("AEO presence", aeo_score or "—", "of 100", _score_gauge(aeo_score, 30) if aeo else "",
         (f"You appear in {aeo.get('mention_rate', 0)}% of {aeo.get('prompts_tested', 0)} buyer-intent AI answers."
          if aeo else "Run an AI-visibility probe to see whether AI answers name you."),
         "Claude + Serper" if aeo else "not run", _pct_color(aeo_score) if aeo else AMBER, ""),
        ("Score breakdown", sc.get("overall", 0), "what makes up the overall score",
         _waterfall([("Visibility", vis), ("Technical", tech), ("On-page", onp),
                     ("Off-page", off), ("AEO", aeo_score)]) or
         _hbars([("Visibility", vis), ("Technical", tech), ("On-page", onp),
                 ("Off-page", off), ("AEO", aeo_score)], VIOLET),
         "The lowest bar is where the next hour of work belongs.",
         "computed", VIOLET, ""),
        ("Organic sessions", f"{sessions:,}", "last 28 days", spark_sess,
         ("Real visits from search." if sessions
          else "Zero sessions is expected while rankings are still climbing — impressions come first."),
         "GA4", BLUE, ""),
        ("Search clicks", f"{clicks:,}", f"on {impr:,} impressions",
         (spark_clicks + spark_impr) or (_donut(100 * clicks / max(impr, 1)) if impr else ""),
         (f"CTR {round(100*clicks/impr,1)}% — people saw you {impr:,} times."
          if impr else "No impressions yet: Google hasn't ranked these pages high enough to show them."),
         "Search Console", TEAL, ""),
        ("Today's top 3 moves", len(top3), "highest impact ÷ effort", "",
         "Ranked by how much they move rankings against how long they take.",
         "work-order engine", VIOLET, moves),
        ("What changed", len(changed), "pages up or down", "",
         "Week-over-week movement per page — the early warning that used to be silent.",
         "Search Console comparison", AMBER, changed_html),
        ("Fixed while you slept", len(done), "auto-applied", "",
         "Schema, internal links and alt text are applied without asking. Copy always waits for you.",
         "work-order log", GREEN, fixed),
        ("Risk radar", len(risks), "flagged", "",
         "Anything that could cost you traffic if it stays unfixed.",
         "audit + index status", PINK if risks else GREEN, risk_html),
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
        ("Titles in range", f"{good_title}/{len(pages)}", "30–60 characters",
         _histogram([r.get("title_len", 0) for r in pages if r.get("title_len")],
                    unit=" chars"),
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
        ("Average length", f"{avg_words:,}", "words per page",
         _histogram(words, unit="w"),
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
        ("Rewrites awaiting you", len(proposals), "titles & metas drafted",
         prop_body + "<div class='cta'><a class='cbtn sm ghost' "
                     "href='#card-work-orders-what-is-waiting-on-your-decision'>"
                     "→ open the approval queue</a></div>",
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
                     right_fmt=lambda p: f"{int(float(p.get('sessions', 0) or 0))} sessions",
                     empty="No Analytics page data yet.")
    return _head("📚", "Content performance & decay",
                 f"All {len(live)} live pages measured against what search actually did with them.") + _cards([
        ("Live pages", len(live), "crawled and indexable",
         _treemap(sorted(_section_mix(live).items(), key=lambda kv: -kv[1])),
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
#  BOARD 10 — GEO / GENERATIVE ENGINES  (20 cards)
# ======================================================================
def board_aeo(ctx) -> str:
    H = _H()
    aeo = ctx.get("aeo") or {}
    hist = ctx.get("aeo_history") or []
    access = ctx.get("crawler_access") or {}
    ent = ctx.get("entity") or {}
    quot = ctx.get("quotable") or {}
    crawl = ctx.get("crawl") or {}
    cites = aeo.get("citations") or {}
    eng = aeo.get("engines") or {}
    sov = aeo.get("share_of_voice") or {}
    place = aeo.get("placement") or {}
    gaps = aeo.get("gaps") or []
    n = aeo.get("prompts_tested", 0)
    won, lost = aeo.get("prompts_won", 0), aeo.get("prompts_lost", 0)
    you = sov.get("_you", 0)
    rivals = {k: v for k, v in sov.items() if k != "_you"}
    live = aeo.get("engines_live", 0)

    trend_score = _trend([("AEO score", [h.get("score", 0) for h in hist], TEAL)])
    trend_cite = _trend([("Citations", [h.get("citations", 0) for h in hist], VIOLET)])
    engine_bars = _hbars([(e.replace("_", " ").title(),
                           (eng.get(e) or {}).get("mentions", 0)) for e in
                          ("claude", "openai", "perplexity", "gemini")], VIOLET)
    sov_bars = _hbars(sorted(rivals.items(), key=lambda kv: -kv[1])[:8], PINK) if rivals else ""

    def _eng(name, label, vendor):
        e = eng.get(name) or {}
        on = e.get("connected")
        return (label, f"{e.get('mentions', 0)}/{n}" if on else "—",
                "answers naming you" if on else "not connected",
                _donut(e.get("rate", 0)) if on else "",
                (f"{vendor} names you in {e.get('rate', 0)}% of the buyer questions tested."
                 if on else (e.get("reason") or f"{vendor} needs its own API key. "
                             "Reported as not connected rather than guessed.")),
                f"{vendor} API" if on else "not connected",
                _pct_color(e.get("rate", 0), good=30, ok=10) if on else AMBER, "")

    presence = _vizcards([
        ("AEO score", aeo.get("score", 0), "of 100", _donut(aeo.get("score", 0)),
         f"Blend of AI mentions, snippet ownership and organic presence across {n} buyer questions.",
         "AEO engine", _pct_color(aeo.get("score", 0)), ""),
        ("Mention rate", f"{aeo.get('mention_rate', 0)}%", "of AI answers name you",
         _donut(aeo.get("mention_rate", 0), danger_low=True),
         f"You were named in {won} of {n} answers to questions a real buyer asks before hiring.",
         "multi-engine probe", _pct_color(aeo.get("mention_rate", 0), good=30, ok=10), ""),
        ("Prompts tested", n, "buyer questions", "",
         "Ten general plus one per audience segment — editable in the prompt library.",
         "prompt library", BLUE, ""),
        ("Won vs lost", f"{won}/{n}", "answers you appear in",
         _split_donut([("Won", won, GREEN), ("Lost", lost, PINK)], center=f"{won}"),
         ("Every lost prompt is a question where a buyer hears someone else's name."
          if lost else "You appear in every tested answer."),
         "multi-engine probe", GREEN if won else PINK, ""),
        ("Prompts lost", lost, "no mention at all", "",
         ("These are the content gaps that matter most — they are literally the "
          "questions your buyers ask." if lost else "Nothing lost."),
         "computed", PINK if lost else GREEN, ""),
        _eng("claude", "Claude", "Anthropic"),
        _eng("openai", "ChatGPT", "OpenAI"),
        _eng("perplexity", "Perplexity", "Perplexity"),
        _eng("gemini", "Gemini", "Google"),
        ("Google AI surfaces", (eng.get("google_ai") or {}).get("snippets", 0),
         "answer boxes owned",
         _donut(100 * (eng.get("google_ai") or {}).get("snippets", 0) / max(n, 1)),
         ("The answer box is what AI Overviews quote and voice assistants read aloud."),
         "Serper", GREEN if (eng.get("google_ai") or {}).get("snippets") else AMBER, ""),
        ("Visibility trend", len(hist), "probes recorded", trend_score,
         ("Each probe is a point on this line — this is how you prove AEO work is "
          "working." if len(hist) > 1
          else "Run the probe weekly; the second run starts the trend."),
         "probe history", TEAL, ""),
        ("Where you appear", place.get("first", 0), "named in the opening",
         _split_donut([("First", place.get("first", 0), GREEN),
                       ("Middle", place.get("middle", 0), AMBER),
                       ("Buried", place.get("buried", 0), PINK)],
                      center=str(place.get("first", 0))),
         "Named in the first sentence is worth far more than a mention in paragraph six.",
         "answer-quality pass", GREEN if place.get("first") else AMBER, ""),
        ("Recommended", aeo.get("recommended", 0), "answers actively recommend you",
         _donut(100 * aeo.get("recommended", 0) / max(won, 1) if won else 0),
         ("Being listed is not the same as being recommended. This counts the answers "
          "that actually endorse you."),
         "answer-quality pass", GREEN if aeo.get("recommended") else AMBER, ""),
        ("Engines connected", f"{live}/4", "AI engines probed", _gauge(live, 4),
         ("Claude runs on your existing key. ChatGPT, Perplexity and Gemini each need "
          "their own — Gemini has a free tier."),
         "connector status", _pct_color(100 * live / 4), ""),
    ])

    citations = _vizcards([
        ("Citations", cites.get("total", 0), "links to your pages in AI answers",
         _hbars(sorted((cites.get("by_engine") or {}).items(), key=lambda kv: -kv[1]), TEAL),
         ("A citation is stronger than a mention — the engine is sending people to a "
          "specific page." if cites.get("total") else
          "No AI answer has linked to you yet. Perplexity cites sources most reliably, "
          "so connecting it would show this fastest."),
         "citation extractor", GREEN if cites.get("total") else AMBER, ""),
        ("Pages cited", cites.get("unique_pages", 0), "distinct URLs", "",
         "Which of your 266 pages the engines consider quotable.",
         "citation extractor", TEAL, ""),
        ("Citations by engine", len(cites.get("by_engine") or {}), "engines citing you",
         _hbars(sorted((cites.get("by_engine") or {}).items(), key=lambda kv: -kv[1]), VIOLET),
         "Different engines cite different pages — spread means broad quotability.",
         "citation extractor", VIOLET, ""),
        ("Most-cited pages", len(cites.get("top_pages") or []), "ranked", "",
         "Study what these pages do differently, then copy it across the library.",
         "citation extractor", GREEN,
         _linkrows(cites.get("top_pages") or [], url_fn=lambda kv: kv[0],
                   right_fn=lambda kv: f"{kv[1]}×",
                   empty="No page has been cited yet.")),
        ("Citation trend", cites.get("total", 0), "over time", trend_cite,
         ("Rising citations is the clearest proof AEO work is landing."
          if len(hist) > 1 else "Starts once you have two probe runs."),
         "probe history", VIOLET, ""),
        ("Quotable but uncited", max(0, quot.get("quotable", 0) - cites.get("unique_pages", 0)),
         "ready, not yet cited", "",
         ("These pages have question headings and answers but no engine cites them — "
          "usually an authority or indexing problem, not a content one."),
         "computed", AMBER, ""),
        ("Share of voice", f"{round(100*you/max(you+sum(rivals.values()),1))}%",
         "of all brand mentions",
         _split_donut([("You", you, TEAL)] +
                      [(k, v, c) for (k, v), c in
                       zip(sorted(rivals.items(), key=lambda kv: -kv[1])[:4],
                           (PINK, AMBER, VIOLET, BLUE))], center=str(you)),
         (f"You: {you} mentions. " +
          (f"Most-named rival: {max(rivals, key=rivals.get)}." if rivals
           else "No rival was named either — the category is wide open in AI answers.")),
         "computed", TEAL if you else AMBER, ""),
        ("Rival leaderboard", len(rivals), "rivals named in your questions", sov_bars,
         ("These are the names buyers hear instead of yours." if rivals
          else "No rival dominates these answers yet."),
         "computed", PINK if rivals else GREEN, ""),
        ("Answer gaps", len(gaps), "prompts naming a rival, not you", "",
         ("Each gap is one page you could write that would put you in that answer."
          if gaps else "No rival is taking an answer you should own."),
         "computed", PINK if gaps else GREEN,
         _rows(gaps, left_fmt=lambda g: g["prompt"][:44],
               right_fmt=lambda g: ", ".join(g.get("rivals", []))[:26] or "nobody named",
               empty="No gaps.")),
        ("Prompts you own", won, "answers naming you", "",
         "Defend these — they are the questions where you already win.",
         "computed", GREEN, ""),
    ])

    bots = access.get("bots") or []
    blocked = [b for b in bots if b.get("blocked")]

    def _bot(name):
        b = next((x for x in bots if x["bot"] == name), None)
        if not b:
            return (name, "—", "not checked", "",
                    "Run the AI-visibility probe to check robots.txt.", "not run", AMBER, "")
        ok = not b["blocked"]
        return (f"{name}", "ALLOWED" if ok else "BLOCKED", b["vendor"], "",
                b["why"] + ("" if ok else
                            "  This is a hard blocker: it can never cite you while this stands."),
                "robots.txt", GREEN if ok else PINK, "")

    readiness = _vizcards([
        ("AI crawler access", f"{access.get('allowed_count', 0)}/{len(bots) or 8}",
         "AI bots allowed to read you",
         _split_donut([("Allowed", access.get("allowed_count", 0), GREEN),
                       ("Blocked", access.get("blocked_count", 0), PINK)],
                      center=str(access.get("allowed_count", 0))) if bots else "",
         ("If a bot is blocked in robots.txt it can NEVER cite you, however good the "
          "content is. This is the first thing to check and nothing checked it before."
          if bots else "Not checked yet — run the AI probe."),
         "robots.txt", PINK if blocked else (GREEN if bots else AMBER), ""),
        _bot("GPTBot"), _bot("ClaudeBot"), _bot("PerplexityBot"), _bot("Google-Extended"),
        ("robots.txt", "found" if access.get("robots_found") else "none", "on your site", "",
         ("Present and parsed." if access.get("robots_found")
          else "No robots.txt means everything is allowed — fine, but you have no control."),
         "own crawler", GREEN if access.get("robots_found") else AMBER, ""),
        ("llms.txt", "ready" if ctx.get("llms_txt") else "—", "AI crawler manifest", "",
         ("Generated from your live crawl. Upload it to your site root — one file, free, "
          "and it tells AI crawlers what you are and which pages matter."
          if ctx.get("llms_txt") else "Run the AI probe to generate it."),
         "AEO engine", GREEN if ctx.get("llms_txt") else AMBER,
         _link("/seo/llms.txt", "view the generated llms.txt") if ctx.get("llms_txt") else ""),
        ("FAQ schema", f"{quot.get('faq_schema', 0)}/{quot.get('pages', 0)}",
         "pages marked up", _donut(quot.get("faq_pct", 0)),
         "FAQPage markup hands an engine a ready-made answer. The fixer injects it free.",
         "own crawler", _pct_color(quot.get("faq_pct", 0)), ""),
        ("Structured data types", len(ent.get("schema_types") or []), "distinct types",
         _hbars((ent.get("schema_types") or [])[:6], VIOLET),
         "HowTo, QAPage and Speakable are all quotable formats most sites never use.",
         "own crawler", VIOLET, ""),
        ("Author & credentials", ent.get("person_pages", 0), "pages declaring a Person", "",
         ("Generative engines weigh who wrote it. Author markup with real credentials is "
          "the cheapest trust signal you are not using."),
         "own crawler", GREEN if ent.get("person_pages") else AMBER, ""),
        ("Entity links (sameAs)", len(ent.get("entity_links") or []), "authority profiles linked",
         _gauge(len(ent.get("entity_links") or []), 4),
         ("Wikidata, Wikipedia, LinkedIn and Crunchbase links are how an engine confirms "
          "you are a real company. Missing: "
          + (", ".join(ent.get("missing_entities") or []) or "none")),
         "own crawler", _pct_color(25 * len(ent.get("entity_links") or [])), ""),
        ("Entity score", ent.get("score", 0), "of 100", _donut(ent.get("score", 0)),
         "Organization + Person markup plus outbound authority links, combined.",
         "entity audit", _pct_color(ent.get("score", 0)), ""),
    ])

    pages = [r for r in crawl.get("urls", []) if r.get("status") == 200]
    q_pages = [r for r in pages if len([h for h in (r.get("h2") or [])
                                        if h.strip().endswith("?")]) >= 2]
    paa = []
    for r in (ctx.get("ranks") or []):
        paa.extend(r.get("paa") or [])
    paa = list(dict.fromkeys(paa))
    answered = [q for q in paa if any(q.lower()[:28] in " ".join(p.get("h2") or []).lower()
                                      for p in pages)]

    content = _vizcards([
        ("Quotable pages", f"{quot.get('quotable', 0)}/{quot.get('pages', 0)}",
         "2+ question headings", _donut(quot.get("quotable_pct", 0)),
         ("Engines quote a heading that ASKS and a paragraph that ANSWERS. Vague headings "
          "never get cited however good the prose is."),
         "own crawler", _pct_color(quot.get("quotable_pct", 0)), ""),
        ("Question headings", sum(len([h for h in (r.get("h2") or [])
                                       if h.strip().endswith("?")]) for r in pages),
         "across the library", "",
         "Your article template already uses seven question headings — that is why this works.",
         "own crawler", TEAL, ""),
        ("Pages needing work", len(quot.get("weakest") or []), "not quotable yet", "",
         "Rewrite these H2s as the questions your buyers actually ask.",
         "computed", AMBER if quot.get("weakest") else GREEN,
         _linkrows(quot.get("weakest") or [], url_fn=lambda r: r["url"],
                   right_fn=lambda r: f"{r['question_headings']} question headings",
                   empty="Every page is quotable.")),
        ("PAA questions found", len(paa), "People Also Ask", "",
         ("Google is telling you exactly what people ask around your topics."
          if paa else "Run the rank tracker — it collects PAA questions for free."),
         "Serper", TEAL if paa else AMBER,
         _rows(paa, left_fmt=lambda q: q[:52], empty="Run the rank tracker to collect these.")),
        ("PAA answered", f"{len(answered)}/{len(paa)}", "already covered",
         _donut(100 * len(answered) / max(len(paa), 1)),
         "Each unanswered PAA question is a heading you could add to an existing page.",
         "computed", _pct_color(100 * len(answered) / max(len(paa), 1)), ""),
        ("Content → prompt map", len(q_pages), "pages that could answer a buyer question", "",
         "These are your candidates for winning the prompts you currently lose.",
         "computed", TEAL,
         _linkrows(q_pages, url_fn=lambda r: r["url"],
                   right_fn=lambda r: f"{len([h for h in (r.get('h2') or []) if h.strip().endswith('?')])} questions",
                   empty="No page has question headings yet.")),
        ("Segment coverage", 8, "audience segments", "",
         ("One prompt per segment is tested: regulated, medical, e-commerce, service, "
          "freelancers, creators, B2B and business-launch."),
         "prompt library", VIOLET, ""),
        ("Unanswered buyer questions", len(gaps), "prompts with no page behind them", "",
         "Write one page per gap, with the question as the H2 and the answer directly under it.",
         "computed", AMBER if gaps else GREEN,
         _rows(gaps, left_fmt=lambda g: g["prompt"][:52], empty="Nothing unanswered.")),
        ("Freshness", sum(1 for r in pages if r.get("words", 0) > 600), "substantial pages", "",
         ("Generative engines favour recently updated, dated content. Refreshing beats "
          "publishing new when the page already ranks."),
         "own crawler", BLUE, ""),
        ("AEO fix queue", len(quot.get("weakest") or []) + len(gaps), "actions", "",
         "Quotability rewrites plus the missing answers, in one list.",
         "computed", AMBER if (quot.get("weakest") or gaps) else GREEN, ""),
    ])

    return (_head("🤖", "AEO — Answer Engine Optimisation",
                  "Buyers ask an AI before they ask you. These 46 cards measure whether "
                  "the answer says your name, which page it cites, and whether the "
                  "engines are even allowed to read you.")
            + _subnav(["Answer presence", "Citations & share of voice",
                       "AI readiness", "Answer content"])
            + _sub("Answer presence", "Are you in the answer, on every engine?") + presence
            + _sub("Citations & share of voice", "When you are named, which page gets the link?") + citations
            + _sub("AI readiness", "Can the engines read you, and is your markup quotable?") + readiness
            + _sub("Answer content", "The pages and questions that win the answers.") + content)


# ======================================================================
def board_geo_generative(ctx) -> str:
    H = _H()
    aeo = ctx.get("aeo") or {}
    hist = ctx.get("aeo_history") or []
    sov = aeo.get("share_of_voice") or {}
    eng = aeo.get("engines") or {}
    gaps = aeo.get("gaps") or []
    results = aeo.get("results") or []
    you = sov.get("_you", 0)
    rivals = {k: v for k, v in sov.items() if k != "_you"}
    total_mentions = you + sum(rivals.values())
    n = aeo.get("prompts_tested", 0)
    live = aeo.get("engines_live", 0)
    sov_pct = round(100 * you / max(total_mentions, 1), 1)

    # contested = at least one engine named us AND at least one named a rival
    contested = 0
    for r in results:
        named = any((r.get(e) or {}).get("mentioned") for e in ("claude", "openai",
                                                               "perplexity", "gemini"))
        riv = any((r.get(e) or {}).get("rivals_mentioned") for e in ("claude", "openai",
                                                                    "perplexity", "gemini"))
        if named and riv:
            contested += 1
    # engine agreement: do the connected engines name the same brands?
    agree = 0
    for r in results:
        named = [e for e in ("claude", "openai", "perplexity", "gemini")
                 if (r.get(e) or {}).get("mentioned")]
        if len(named) > 1:
            agree += 1

    def _kind(word):
        return sum(1 for r in results if word in r.get("prompt", "").lower())

    def _kind_won(word):
        return sum(1 for r in results if word in r.get("prompt", "").lower()
                   and any((r.get(e) or {}).get("mentioned")
                           for e in ("claude", "openai", "perplexity", "gemini")))

    trend_sov = _trend([("Mention rate %", [h.get("mention_rate", 0) for h in hist], TEAL)])
    trend_cit = _trend([("Citations", [h.get("citations", 0) for h in hist], VIOLET)])
    rival_bars = _hbars(sorted(rivals.items(), key=lambda kv: -kv[1])[:8], PINK) if rivals else ""
    engine_bars = _hbars([(e.title(), (eng.get(e) or {}).get("mentions", 0))
                          for e in ("claude", "openai", "perplexity", "gemini")], VIOLET)
    winning = []
    for r in results:
        for e in ("claude", "openai", "perplexity", "gemini"):
            for c in ((r.get(e) or {}).get("citations") or []):
                winning.append((c, r.get("prompt", "")))

    return _head("🌐", "GEO — Generative Engine Optimisation",
                 "Share of voice inside AI answers: who gets named when a buyer asks, "
                 "across every engine we can reach.") + _vizcards([
        ("Generative visibility", aeo.get("score", 0), "of 100", _score_gauge(aeo.get("score", 0), 30),
         f"Composite across {live} connected engine(s) and {n} buyer questions.",
         "AEO engine", _pct_color(aeo.get("score", 0)), ""),
        ("Share of voice", f"{sov_pct}%", "of all brands named",
         _split_donut([("You", you, TEAL)] +
                      [(k, v, c) for (k, v), c in
                       zip(sorted(rivals.items(), key=lambda kv: -kv[1])[:4],
                           (PINK, AMBER, VIOLET, BLUE))], center=f"{sov_pct:.0f}%"),
         (f"Of {total_mentions} brand mentions across the tested answers, {you} were you."
          if total_mentions else
          "No brand was named in any answer — the engines answered generically. "
          "That is an open category, not a loss."),
         "computed", TEAL if sov_pct >= 20 else AMBER, ""),
        ("Engines answering", f"{live}/4", "generative engines probed", _gauge(live, 4),
         "Claude is live on your key. ChatGPT, Perplexity and Gemini each need one — "
         "Gemini has a free tier, Perplexity is about $1 per 1,000 questions.",
         "connector status", _pct_color(100 * live / 4), ""),
        ("Prompts won", aeo.get("prompts_won", 0), f"of {n}",
         _split_donut([("Won", aeo.get("prompts_won", 0), GREEN),
                       ("Lost", aeo.get("prompts_lost", 0), PINK)],
                      center=str(aeo.get("prompts_won", 0))),
         "A win means at least one engine named you in its answer.",
         "computed", GREEN if aeo.get("prompts_won") else PINK, ""),
        ("Prompts contested", contested, "you AND a rival named", "",
         ("Both of you are in the answer — the buyer is comparing you right there."
          if contested else "No answer names you alongside a rival."),
         "computed", AMBER, ""),
        ("Prompts lost", aeo.get("prompts_lost", 0), "no mention", "",
         "Each one is a buyer hearing a recommendation that is not you.",
         "computed", PINK if aeo.get("prompts_lost") else GREEN, ""),
        ("Visibility trend", len(hist), "runs recorded", trend_sov,
         ("The only honest proof that GEO work is moving." if len(hist) > 1
          else "One run so far — the trend starts at the second."),
         "probe history", TEAL, ""),
        ("Top rival", (max(rivals, key=rivals.get) if rivals else "—"),
         "most-named competitor", "",
         (f"Named in {max(rivals.values())} of {n} answers." if rivals
          else "No competitor is dominating these answers."),
         "computed", PINK if rivals else GREEN, ""),
        ("Rival leaderboard", len(rivals), "brands named instead of you", rival_bars,
         ("Study what the top one publishes — engines quote what they can verify."
          if rivals else "No rival leaderboard yet."),
         "computed", PINK if rivals else GREEN, ""),
        ("Engine agreement", agree, "prompts where 2+ engines name you", "",
         ("Agreement across engines means the signal is in your content, not one model's "
          "training quirk."),
         "computed", GREEN if agree else AMBER, ""),
        ("Citation velocity", (aeo.get("citations") or {}).get("total", 0),
         "links earned in answers", trend_cit,
         "Citations are the generative equivalent of a backlink.",
         "citation extractor", VIOLET, ""),
        ("Recommendation rate", f"{round(100*aeo.get('recommended',0)/max(aeo.get('prompts_won',1),1))}%",
         "of wins actively recommend you",
         _donut(100 * aeo.get("recommended", 0) / max(aeo.get("prompts_won", 1), 1)),
         "Listed and recommended are different outcomes. This measures the second.",
         "answer-quality pass", GREEN if aeo.get("recommended") else AMBER, ""),
        ("Qualified mentions", sum(1 for r in results for e in ("claude", "openai",
                                                                "perplexity", "gemini")
                                   if ((r.get(e) or {}).get("quality") or {}).get("qualified")),
         "hedged or caveated", "",
         "Mentions wrapped in 'however' or 'less known' — visible, but not persuasive.",
         "answer-quality pass", AMBER, ""),
        ("Comparison queries", f"{_kind_won('vs')}/{_kind('vs')}", "'X vs Y' prompts won", "",
         "Comparison answers convert hardest — the buyer is already choosing.",
         "computed", TEAL, ""),
        ("'Best X' ownership", f"{_kind_won('best')}/{_kind('best')}", "prompts won", "",
         "The highest-intent generative query there is.",
         "computed", _pct_color(100 * _kind_won("best") / max(_kind("best"), 1)), ""),
        ("Alternatives queries", f"{_kind_won('alternativ')}/{_kind('alternativ')}",
         "prompts won", "",
         "Where switchers look. Being absent here loses ready-to-move buyers.",
         "computed", TEAL, ""),
        ("Winning pages", len({w[0] for w in winning}), "pages engines actually cite", "",
         "Copy the structure of these across the library.",
         "citation extractor", GREEN if winning else AMBER,
         _linkrows(list(dict.fromkeys(winning)), url_fn=lambda w: w[0],
                   right_fn=lambda w: w[1][:26],
                   empty="No page cited yet — Perplexity would show this fastest.")),
        ("Losing prompts", len(gaps), "rival named, you were not", "",
         "The shortest path to share of voice: one page per line, answering it directly.",
         "computed", PINK if gaps else GREEN,
         _rows(gaps, left_fmt=lambda g: g["prompt"][:46],
               right_fmt=lambda g: ", ".join(g.get("rivals", []))[:24],
               empty="Nothing lost to a rival.")),
        ("Segment coverage", 8, "audience segments probed", "",
         "Each of your eight segments gets its own buyer question in the prompt set.",
         "prompt library", VIOLET, ""),
        ("GEO fix queue", len(gaps) + aeo.get("prompts_lost", 0), "actions", "",
         "Lost prompts plus rival-owned answers — the generative work list.",
         "computed", AMBER if gaps else GREEN, ""),
    ])


# ======================================================================
#  BOARD 11 — GEO / LOCAL & MULTI-MARKET  (30 cards)
# ======================================================================
def board_local(ctx) -> str:
    H = _H()
    geo = ctx.get("geo") or {}
    grid = ctx.get("local_grid") or []
    gbp = (ctx.get("local") or {}).get("gbp") or {}
    hre = geo.get("hreflang") or {}
    lang = geo.get("language") or {}
    perf = geo.get("performance") or {}
    areas = geo.get("service_areas") or {}
    schema = geo.get("schema") or {}
    nap = ctx.get("nap") or {}
    comps = (ctx.get("local") or {}).get("competitors") or []
    markets = perf.get("markets") or []
    connected = bool(gbp.get("connected"))

    mk_bars = _hbars([(m["market"][:12], m["impressions"]) for m in markets], BLUE) if markets else ""
    mk_donut = _split_donut([(m["market"][:10], m["impressions"], c) for m, c in
                             zip(markets, (BLUE, TEAL, VIOLET, AMBER, GREEN))],
                            center=str(perf.get("total_impressions", 0))) if markets else ""
    lang_bars = _hbars([(k.upper(), v) for k, v in (lang.get("languages") or [])], VIOLET)
    code_bars = _hbars((hre.get("codes") or [])[:8], TEAL)

    def _market_card(name):
        m = next((x for x in markets if x["market"] == name), None)
        if not m:
            return (name, "—", "no data", "",
                    ("No Search Console data for this market yet, which means "
                     "unmeasured rather than performing badly."),
                    "Search Console", AMBER, "")
        lang_row = next((r for r in (lang.get("markets") or []) if r["market"] == name), {})
        return (name, f"{m['impressions']:,}", f"impressions · {m['clicks']} clicks",
                _donut(m.get("share_pct", 0), danger_low=False),
                (f"{m.get('share_pct', 0)}% of your total impressions, average position "
                 f"#{m.get('position', 0)}. "
                 + (f"{lang_row.get('pages', 0)} pages in {lang_row.get('language', '')}."
                    if lang_row else "")),
                "Search Console", TEAL if m["impressions"] else AMBER, "")

    return _head("📍", "GEO — Local & multi-market",
                 "Your five target markets: where you show up, in which language, and "
                 "whether the technical signals tell Google which page belongs where.") + _vizcards([
        ("Market readiness", geo.get("score", 0), "of 100", _score_gauge(geo.get("score", 0), 70),
         "Language coverage, hreflang correctness and service-area pages, combined.",
         "market audit", _pct_color(geo.get("score", 0)), ""),
        ("Markets targeted", len(markets) or 5, "USA · UK · DE · CH · CA", mk_donut,
         "Each market is a separate SERP with separate competitors.",
         "ICP definition", BLUE, ""),
        ("Impressions by market", f"{perf.get('total_impressions', 0):,}", "across your five",
         mk_bars,
         (f"Active in {len(perf.get('active') or [])}, silent in "
          f"{len(perf.get('silent') or [])}." if markets else "No market data yet."),
         "Search Console", BLUE, ""),
        ("Clicks by market", perf.get("total_clicks", 0), "real visits", "",
         ("Clicks follow rankings — with everything below position 40, near-zero is expected."),
         "Search Console", GREEN if perf.get("total_clicks") else AMBER, ""),
        ("Active markets", len(perf.get("active") or []), "showing impressions", "",
         (", ".join(perf.get("active") or [])
          or "No market shows impressions yet."),
         "Search Console", GREEN if perf.get("active") else AMBER, ""),
        ("Silent markets", len(perf.get("silent") or []), "no impressions at all", "",
         ((", ".join(perf.get("silent") or []) + " — no page is competing there yet.")
          if perf.get("silent") else "Every market shows impressions."),
         "Search Console", PINK if perf.get("silent") else GREEN, ""),
        _market_card("United States"), _market_card("United Kingdom"),
        _market_card("Germany"), _market_card("Switzerland"), _market_card("Canada"),
        ("hreflang coverage", f"{hre.get('pages_with_hreflang', 0)}/{hre.get('pages', 0)}",
         "pages declaring alternates", _donut(hre.get("coverage_pct", 0)),
         ("hreflang is how you tell Google which page serves which country. Without it, "
          "your German and English pages compete with each other."),
         "own crawler", _pct_color(hre.get("coverage_pct", 0)), ""),
        ("hreflang errors", hre.get("issue_count", 0), "problems found", "",
         ("A missing self-reference makes Google ignore the whole set — a very common and "
          "completely silent failure." if hre.get("issue_count")
          else "No hreflang errors."),
         "own crawler", PINK if hre.get("issue_count") else GREEN,
         _linkrows(hre.get("issues") or [], url_fn=lambda i: i["url"],
                   right_fn=lambda i: i["issue"][:40], empty="Clean.")),
        ("Declared locales", len(hre.get("codes") or []), "hreflang codes in use", code_bars,
         "Which country/language pairs your pages claim to serve.",
         "own crawler", TEAL, ""),
        ("Missing locales", len(hre.get("missing_markets") or []), "target markets undeclared", "",
         ((", ".join(hre.get("missing_markets") or []) + " are not declared anywhere.")
          if hre.get("missing_markets") else "Every target market is declared."),
         "computed", AMBER if hre.get("missing_markets") else GREEN, ""),
        ("Language coverage", f"{len(lang.get('languages') or [])}", "languages published",
         lang_bars,
         ("Germany and Switzerland need German pages to compete. You write German — "
          "that is the widest open door of the five markets."),
         "own crawler", VIOLET, ""),
        ("Pages per language", sum(v for _, v in (lang.get("languages") or [])),
         "total", lang_bars,
         "A market with zero pages in its language cannot rank there, full stop.",
         "own crawler", BLUE, ""),
        ("Uncovered markets", len(lang.get("uncovered") or []), "no page in their language", "",
         ((", ".join(lang.get("uncovered") or []))
          if lang.get("uncovered") else "Every market has content in its language."),
         "computed", PINK if lang.get("uncovered") else GREEN, ""),
        ("Service-area pages", f"{areas.get('covered', 0)}/5", "market landing pages",
         _donut(100 * areas.get("covered", 0) / 5),
         ("One page per market, in that market's language, is how you compete locally "
          "without an office there."),
         "own crawler", _pct_color(100 * areas.get("covered", 0) / 5),
         _linkrows([m for m in (areas.get("markets") or []) if m["has_page"]],
                   url_fn=lambda m: m["url"], label_fn=lambda m: m["market"],
                   right_fn=lambda m: "has a page", empty="No market page found.")),
        ("Missing market pages", len(areas.get("missing") or []), "to create", "",
         ((", ".join(areas.get("missing") or []))
          if areas.get("missing") else "All five markets have a page."),
         "computed", AMBER if areas.get("missing") else GREEN, ""),
        ("LocalBusiness schema", schema.get("localbusiness", 0), "pages marked up",
         _donut(schema.get("coverage_pct", 0)),
         ("LocalBusiness with areaServed is how you claim a service area without a "
          "physical address in it."),
         "own crawler", GREEN if schema.get("localbusiness") else AMBER, ""),
        ("Organization schema", schema.get("organization", 0), "pages", "",
         "The entity record that ties every market page back to one business.",
         "own crawler", GREEN if schema.get("organization") else AMBER, ""),
        ("Local pack grid", len(grid), "market × query checks",
         (lambda _mk=sorted({r["market"] for r in grid}),
                 _q=sorted({r["query"][:18] for r in grid}):
          _heatmap(_mk, _q, [[next((51 - (x.get("position") or 51)
                                    for x in grid
                                    if x["market"] == m and x["query"][:18] == q), 0)
                              for q in _q] for m in _mk]))() if grid else "",
         ("Where you sit in the map pack, per market." if grid
          else "Not run yet. Serper Maps is already connected — about one credit per cell."),
         "Serper Maps", TEAL if grid else AMBER,
         _rows(grid, left_fmt=lambda r: f"{r['market']} · {r['query'][:24]}",
               right_fmt=lambda r: (f"#{r['position']}" if r.get("position")
                                    else "not in top 50"),
               empty="Run the local grid to fill this.")),
        ("Local pack presence", sum(1 for r in grid if r.get("found")), "cells where you rank",
         _donut(100 * sum(1 for r in grid if r.get("found")) / max(len(grid), 1)) if grid else "",
         ("Local intent converts hardest and is the cheapest to win." if grid
          else "Fills once the grid runs."),
         "Serper Maps", GREEN if any(r.get("found") for r in grid) else AMBER, ""),
        ("Google Business Profile", "connected" if connected else "—", "reviews & posts", "",
         (gbp.get("reason") or
          "GBP needs its own OAuth — a service account cannot act on a business profile. "
          "Same wall as Google Ads. Local rank tracking works without it."),
         "GBP API" if connected else "not connected", GREEN if connected else AMBER, ""),
        ("Reviews", gbp.get("review_count", "—"), "total", "",
         ("Review count and recency are among the strongest local ranking factors."
          if connected else "Needs the Business Profile connection."),
         "GBP API" if connected else "not connected", BLUE, ""),
        ("Average rating", gbp.get("rating", "—"), "stars",
         _donut(20 * float(gbp.get("rating", 0) or 0)) if connected else "",
         ("Rating drives both local ranking and click-through." if connected
          else "Needs the Business Profile connection."),
         "GBP API" if connected else "not connected", BLUE, ""),
        ("Unanswered reviews", gbp.get("unanswered", "—"), "awaiting a reply", "",
         ("Replying to every review is a confirmed local ranking signal, and it is free."
          if connected else "Needs the Business Profile connection."),
         "GBP API" if connected else "not connected", AMBER, ""),
        ("NAP consistency", "checked" if nap.get("declared") else "—",
         "name / address / phone", "",
         (nap.get("note") or "Set your business name, phone and address to check this."),
         "own crawler", GREEN if nap.get("consistent") else AMBER, ""),
        ("Local competitors", len(comps), "in the map pack", "",
         ("Maps results feed your lead machine too — the same scan does both jobs."
          if comps else "Run a Maps scan to see who holds the local pack."),
         "Serper Maps", VIOLET,
         _rows(comps, left_fmt=lambda c: c.get("name", "")[:34],
               right_fmt=lambda c: f"★{c.get('rating', 0)} · {c.get('reviews', 0)} reviews",
               empty="No local competitor scan yet.")),
        ("Market opportunity", len(lang.get("uncovered") or []) + len(areas.get("missing") or []),
         "gaps to close", "",
         ("Germany and Switzerland are underserved for German-language automation content, "
          "and you write German. That is the clearest opening of the five."),
         "computed", GREEN, ""),
        ("GEO fix queue", (hre.get("issue_count", 0) + len(areas.get("missing") or [])
                           + len(lang.get("uncovered") or [])), "actions", "",
         "hreflang errors, missing market pages and language gaps, in one list.",
         "computed", AMBER, ""),
    ])


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
    seo_spend = sum(_spend(v) for k, v in (meters or {}).items()
                    if any(s in str(k) for s in ("serper", "dataforseo", "seo")))

    return _head("🛠", "SEO automation & work orders",
                 "Every finding becomes a tracked job. Markup and links apply themselves; "
                 "anything a visitor reads waits for you.") + _cards([
        ("Open work orders", len(open_o), "queued",
         _riskmatrix([((o.get("code") or "")[:14],
                       min(3, max(1, 4 - round(o.get("effort", 3) / 2))),
                       min(3, max(1, round(o.get("impact", 30) / 34) + 1)))
                      for o in sorted(open_o, key=lambda x: -x.get("priority", 0))[:12]])
         or queue_body,
         ("Ranked by impact ÷ effort, so the top of this list is always the best next hour of work."
          if open_o else "Nothing outstanding."),
         "work-order engine", AMBER if open_o else GREEN),
        ("Auto-ready", stats.get("auto_ready", 0), "machine can fix now", "",
         ("Schema, alt text, internal links and OG tags — no human words involved, so no approval needed."),
         "work-order engine", GREEN),
        ("Awaiting approval", len(approve), "copy changes drafted",
         approve_body + (
             "<div class='cta'>"
             "<button class='cbtn sm' onclick=\"approveAll('title')\">✔ Approve all titles</button>"
             "<button class='cbtn sm' onclick=\"approveAll('meta')\">✔ Approve all metas</button>"
             "</div>" if approve else ""),
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
        ("SEO engines live", f"{live}/{len(ENGINES)}", "of 22",
         _statusgrid([(lbl, bool(on), "live" if on else "needs a key")
                      for lbl, on in eng_rows]) or eng_body,
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
def _board_loop(ctx) -> str:
    """The Execution board and Loop Monitor, rendered from the loop engine.

    It needs the Repo rather than the SEO ctx, so it fetches its own and
    says so honestly if the store is unreachable."""
    try:
        import content_engine_api as A
        import content_engine_media_os as M
        import content_engine_search_board as SB
        return SB.section(M.repo(A.get_store()))
    except Exception as ex:
        return ("<p style='color:#8FA0BF;font-size:12px'>the execution "
                "board could not be drawn: "
                + type(ex).__name__ + "</p>")


_TAB_BOARDS = {
    "seocmd":    [("SEO Command", board_command)],
    "seotech":   [("Technical", board_technical), ("Indexing", board_indexing)],
    "seoonpage": [("On-Page", board_onpage), ("Internal Links", board_links)],
    "seokw":     [("Keywords", board_keywords), ("Content", board_content)],
    "seoaeo":    [("AEO", board_aeo)],
    "seogen":    [("GEO Generative", board_geo_generative)],
    "seogeo":    [("GEO Local", board_local)],
    "seooff":    [("Off-Page", board_offpage)],
    "seowork":   [("Work Orders", board_work)],
    # THE CLOSED LOOP. Its own tab, because the question it answers -
    # "did any of this actually work" - is not the same question as any
    # other board on this page.
    "seoloop":   [("Execution & Loops", _board_loop)],
}


def _safe_board(name, fn, ctx) -> str:
    """Render ONE board in isolation.

    Previously a single board raising took the entire SEO section down to a
    fallback (a TypeError in the spend meter blanked all 158 cards). Now the
    broken board shows what broke and the other ten still render."""
    _CURRENT_BOARD["name"] = name
    try:
        return fn(ctx)
    except Exception as e:
        H = _H()
        return ("<div class='card full' style='margin-top:12px;border-color:#FF6B93'>"
                f"<p class='ct'>⚠ {H._esc(name)} board failed to render</p>"
                f"<p class='cc'>{H._esc(type(e).__name__)}: {H._esc(str(e)[:300])}</p>"
                "<p class='cc'>Every other board on this page is unaffected. "
                "This is a bug — send this message and it gets fixed.</p></div>")


def seo_pages(ctx) -> dict:
    """-> {tab_id: html}. Kept as a dict so each board group can be rendered
    independently (and unit-tested), but they all live inside ONE dashboard
    section — see seo_section()."""
    return {tab: "".join(_safe_board(name, fn, ctx) for name, fn in boards)
            for tab, boards in _TAB_BOARDS.items()}


# The existing Search Console / Analytics / competitor boards are NOT a tab —
# they stay permanently visible at the top of the section, exactly where they
# always were. Tabs cover only the NEW engine boards, so nothing the founder
# already relied on can be hidden or displaced by this work.
TABS = [
    ("seocmd", "🧭", "SEO Command"),
    ("seotech", "🔧", "Technical & Indexing"),
    ("seoonpage", "📄", "On-Page & Links"),
    ("seokw", "🔑", "Keywords & Content"),
    ("seoaeo", "🤖", "AEO — Answer Engines"),
    ("seogen", "🌐", "GEO — Generative"),
    ("seogeo", "📍", "GEO — Local & Markets"),
    ("seooff", "🔗", "Off-Page & Links"),
    ("seowork", "🛠", "Work Orders"),
    ("seoloop", "🔁", "Execution & Loops"),
    ("seosrc", "📊", "Sources"),
]

# Nine flat tabs is past the limit of what anyone scans. Four groups, each
# answering one question, with the tabs as their second level.
GROUPS = [
    ("act", "③ ACT", "What should I do?",
     ["seocmd", "seowork", "seoloop"]),
    ("diagnose", "① DIAGNOSE", "What's wrong?", ["seotech", "seoonpage"]),
    ("compete", "② COMPETE", "Where do I stand?",
     ["seokw", "seoaeo", "seogen", "seogeo", "seooff"]),
    ("sources", "④ SOURCES", "Where does the data come from?", ["seosrc"]),
]

_TAB_CSS = """<style>
.shint{font-size:12px;color:#8FA0BF;margin:14px 0 6px;display:flex;align-items:center;gap:7px}
.shint b{color:#2FE3D2}
.stabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 4px;padding:8px 0 10px;
  border-bottom:2px solid #2FE3D2;position:sticky;top:0;z-index:20;background:#0A0E1A}
.stab{background:#121A2E;border:1px solid #26456f;color:#B9C6DE;border-radius:9px;
  padding:9px 14px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;
  display:flex;align-items:center;gap:6px;transition:all .15s}
.stab:hover{border-color:#2FE3D2;color:#EDF1FB;transform:translateY(-1px)}
.stab.on{background:linear-gradient(180deg,#1d3f63,#121A2E);border-color:#2FE3D2;
  color:#FFFFFF;box-shadow:0 0 0 1px #2FE3D2 inset}
.stab .n{background:#0A0E1A;border-radius:20px;padding:1px 7px;font-size:10.5px;color:#2FE3D2}
.spanel{display:none}.spanel.on{display:block}
.sgroups{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 10px}
.sgrp{background:#101d33;border:1px solid #26456f;color:#B9C6DE;border-radius:11px;
  padding:9px 14px;cursor:pointer;font-family:inherit;text-align:left;line-height:1.25}
.sgrp b{display:block;font-size:12px;letter-spacing:.04em}
.sgrp .gq{font-size:10.5px;color:#8FA0BF}
.sgrp.on{background:linear-gradient(180deg,#1d3f63,#101d33);border-color:#8B7CFF;color:#fff}
.sgrp.on .gq{color:#CFC7FF}
.stools{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:10px 0 2px}
.cinput{background:#0A0E1A;border:1px solid #26456f;color:#EDF1FB;border-radius:9px;
  padding:8px 12px;font-family:inherit;font-size:12.5px;min-width:230px;flex:1}
.cinput:focus{outline:none;border-color:#2FE3D2}
.cbtn.sm{padding:5px 10px;font-size:11.5px}
.cbtn.ghost{background:transparent;border-color:#26456f;color:#8FA0BF;text-decoration:none}
.card{position:relative}
.sevbadge{font-size:9.5px;font-weight:800;letter-spacing:.05em;margin-bottom:5px}
.s-critical{color:#FF6B93}.s-warn{color:#F5B14C}.s-ok{color:#3FD98B}
.card.sev-critical{border-color:#FF6B93}
.card.sev-warn{border-color:#F5B14C}
.cta{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
/* `.cta` was ONLY ever a flex container. 206 card buttons also carry the class,
   so they inherited display:flex and NOTHING else - rendering as raw browser
   buttons: light grey on a dark theme with a black border. They looked broken
   because they were unstyled. A button and its container cannot share a class. */
button.cta,a.cta{display:inline-flex;align-items:center;gap:5px;
  background:linear-gradient(180deg,#1d3f63,#121A2E);
  border:1px solid #2FE3D2;color:#EDF1FB;border-radius:9px;padding:7px 13px;
  font:inherit;font-size:12px;font-weight:650;cursor:pointer;text-decoration:none;
  transition:transform .12s,border-color .12s}
button.cta:hover,a.cta:hover{transform:translateY(-1px);border-color:#8B7CFF}
/* NAVIGATION is not an action. A button that only moves you now reads as a
   quiet link, so a filled button always means "this does something". */
button.goto,a.goto{display:inline-flex;align-items:center;gap:4px;background:none;
  border:0;border-bottom:1px dashed #3a4b6d;
  color:#8FA0BF;padding:2px 0;margin-top:8px;font:inherit;font-size:11.5px;
  cursor:pointer;text-decoration:none}
button.goto:hover,a.goto:hover{color:#2FE3D2;border-bottom-color:#2FE3D2}
button.goto::after,a.goto::after{content:'97';font-size:10px;opacity:.75}
.card.hidecard{display:none}
.card.overflowcard{display:none}
.cardgrid.expanded .card.overflowcard{display:block}
.morewrap{margin-top:10px;text-align:center}
.subnav{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 2px}
.subchip{background:#101d33;border:1px solid #26456f;color:#B9C6DE;border-radius:20px;
  padding:5px 13px;font-size:11.5px;cursor:pointer;font-family:inherit}
.subchip:hover{border-color:#2FE3D2;color:#EDF1FB}
.hero{grid-column:1/-1;border-color:#8B7CFF !important;
  background:linear-gradient(135deg,#151d33,#121A2E)}
.hero .ct{font-size:15px}
@media(max-width:600px){
  .grid.g3,.grid.g2{grid-template-columns:1fr}
  .sgrp{flex:1 1 45%}.stab{font-size:11.5px;padding:7px 10px}
  .cinput{min-width:100%}.subnav{overflow-x:auto;flex-wrap:nowrap}
  .card{padding:11px}.sevbadge{font-size:9px}
}
@media(max-width:860px){.stabs{overflow-x:auto;flex-wrap:nowrap}.stab{white-space:nowrap}}
</style>"""


def seo_section(ctx, legacy_html: str = "") -> str:
    """EVERY SEO card in ONE dashboard section, MERGED — nothing displaced.

    Layout:
      1. run bar + a jump link to the new boards
      2. the EXISTING Search Console / Analytics / competitor boards, always
         visible, in their original position — never behind a tab
      3. a divider, then the 11 new engine boards across 6 tabs

    The new work is additive. Anything that was on this page before this build
    is still on this page, in the same place.
    """
    H = _H()
    # THE SEMRUSH SCREENS REPLACE THE CARD BOARDS. The founder's words:
    # "old dashboard cards gonna replace". Each tab now renders the audit
    # screen from content_engine_seo_screens - the agent command band, the
    # health band, issue rows with their four action classes, the per-page
    # command table, robots and AI access, backlinks, AEO and GEO. The card
    # boards these replaced still exist as functions (the SEO context and
    # engines are untouched); only what this section DRAWS has changed.
    import content_engine_seo_screens as SCR
    panels = {
        "seocmd": SCR.command_screen(ctx, []),
        "seotech": SCR.technical_screen(ctx, []),
        "seoonpage": SCR.issue_screen("seoonpage", ctx, []),
        "seokw": SCR.issue_screen("seokw", ctx, []),
        "seoaeo": SCR.health_header(ctx) + SCR.aeo_screen(ctx),
        "seogen": SCR.health_header(ctx) + SCR.geo_gen_screen(ctx),
        "seogeo": SCR.health_header(ctx) + SCR.geo_local_screen(ctx),
        "seooff": SCR.health_header(ctx) + SCR.backlinks_screen(ctx),
        "seowork": SCR.workorders_screen(ctx, []),
        "seoloop": _board_loop(ctx),
    }
    # ONE VOCABULARY. This dict and TABS are two hand-written lists, and a
    # tab whose panel is missing here renders as an empty box that looks
    # like a broken feature. It has already happened once: seoloop was
    # added to TABS and to _TAB_BOARDS, and the page still showed nothing
    # because THIS is the dict seo_section actually reads.
    # seosrc is filled further down from the legacy Google boards, so a
    # missing key here is only a warning, never an overwrite: clobbering a
    # panel that something else fills later would be a worse bug than the
    # one this check exists to catch.
    _missing = [t for t, _i, _l in TABS if t not in panels]
    if _missing:
        import logging as _lg
        _lg.getLogger("content_engine.seo_boards").debug(
            "tabs with no panel in the primary dict: %s", _missing)
    # THE CHIPS COUNT PROBLEMS NOW, NOT CARDS. A chip that says 20 because
    # twenty tiles used to render there is a decoration; a chip that says 12
    # because twelve problems are open is a reading. Tabs whose screens are
    # not problem-shaped (AEO, GEO, backlinks, sources) carry no number
    # rather than a fake one.
    _orders = [o for o in (ctx.get("orders") or ())
               if o.get("status") in ("open", "awaiting_approval", "")]
    _per = {t: sum(1 for o in _orders
                   if o.get("code") in set(codes))
            for t, (_lbl, codes) in SCR.TAB_CODES.items()}
    counts = {"seocmd": len(_orders),
              "seotech": _per.get("seotech", 0),
              "seoonpage": _per.get("seoonpage", 0),
              "seokw": _per.get("seokw", 0),
              "seoaeo": None, "seogen": None, "seogeo": None, "seooff": None,
              "seowork": sum(1 for o in _orders
                             if (o.get("extra") or {}).get("proposal")),
              "seosrc": None}
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'act')}' "
        f"onclick=\"seoTab('{tid}')\"><span>{icon}</span>{H._esc(label)}"
        + (f"<span class='n'>{counts[tid]}</span>"
           if counts.get(tid) is not None else "")
        + "</button>"
        for i, (tid, icon, label) in enumerate(TABS))
    # 'seosrc' is a declared tab but its panel is built separately below, so
    # emitting it here too put TWO elements with id='spanel-seosrc' on the
    # page - and seoTab() resolves by id, so the ④ Sources tab switched on the
    # empty one and the Google boards looked missing.
    body = "".join(
        f"<div class='spanel{' on' if i == 0 else ''}' id='spanel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _, _) in enumerate(TABS) if tid != "seosrc")
    runbar = (
        "<div class='ctrl' style='margin:10px 0 2px;flex-wrap:wrap'>"
        "<button class='cbtn' onclick='runSeoAll()'>▶ Run every SEO engine</button>"
        "<button class='cbtn' onclick='runCrawl()'>🕷 Crawl my site (free)</button>"
        "<button class='cbtn' onclick='runInspect()'>📇 Ask Google what's indexed (free)</button>"
        "<button class='cbtn' onclick='runFixes()'>🛠 Apply safe fixes</button>"
        "<button class='cbtn' onclick='runRanks()'>📈 Check rankings</button>"
        "<button class='cbtn' onclick='runAeo()'>🤖 Probe AI answers</button>"
        "<button class='cbtn' onclick='runProspect()'>🌐 Find link prospects</button>"
        "</div>")
    total = sum(v for v in counts.values() if isinstance(v, int))
    # ---- ① group rail  ->  ② tab chips  ->  ③ the audit screens ----
    grouprail = "".join(
        f"<button class='sgrp{' on' if i == 0 else ''}' id='sgrp-{gid}' "
        f"onclick=\"seoGroup('{gid}')\"><b>{H._esc(label)}</b>"
        f"<span class='gq'>{H._esc(question)}</span></button>"
        for i, (gid, label, question, _t) in enumerate(GROUPS))
    # The card search-and-severity toolbar is gone WITH the cards it
    # filtered. A search box over elements that no longer exist is the
    # decorative toolbar the founder called out a month ago; the screens
    # sort problems first on their own.
    tools = ""
    hint = (f"<div class='shint'>👇 <b>{total} open problem"
            f"{'s' if total != 1 else ''}</b> across the audit. Every row "
            f"carries what it costs and the button that repairs it; the "
            f"agent band at the top commands all of them at once.</div>")
    legacy_head = ("<div id='seo-google' class='card full' style='margin-top:14px;"
                   "border-color:#4C8DFF'><p class='ct'>📊 Search Console &amp; Analytics</p>"
                   "<p class='cc'>Your original Google boards — same data, same order, "
                   "now with a home of their own in ④ Sources.</p></div>")
    # The Google boards become the ④ Sources panel: still every card, still
    # outside the engine tabs, but reachable from the nav instead of stranded
    # 130k characters below everything else.
    sources_panel = (f"<div class='spanel' id='spanel-seosrc'>{legacy_head}"
                     f"{legacy_html or ''}</div>")
    # THE PALETTE BRIDGE. The screens were written against semantic variable
    # names (--card, --ln, --tx ...); this maps them onto the old dashboard's
    # own dark palette, so the screens wear this dashboard's clothes instead
    # of bringing their own. Scoped to .seoscr: nothing outside the SEO
    # section can be repainted by it.
    bridge = ("<style>.seoscr{--pap:var(--s2);--card:var(--s1);"
              "--ln:var(--line);--tx:var(--ink);--dm:var(--mut);"
              "--ft:var(--dim);--ac:var(--blue);--warnc:var(--warn);"
              "--okc:var(--good);--badbg:rgba(255,107,147,.09);"
              "--warnbg:rgba(245,177,76,.09);--okbg:rgba(63,217,139,.09);"
              "--hov:rgba(76,141,255,.07)}"
              + SCR.CSS + "</style>")
    return ("<div class='seoscr'>" + bridge + SCR.JS
            + _TAB_CSS + runbar + hint
            + f"<div class='sgroups'>{grouprail}</div>"
            + f"<div class='stabs'>{bar}</div>" + tools + body + sources_panel
            + "</div>")


CARD_COUNTS = {"command": 13, "technical": 18, "indexing": 12, "on_page": 16,
               "keywords": 18, "content": 14, "internal_links": 12, "off_page": 20,
               "aeo": 46, "geo_generative": 20, "local": 32, "work_orders": 14}
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
    # one drafted copy rewrite waiting on a human — this is what the bulk
    # approve buttons act on, so the fixture must contain one.
    _await = WO.make_order("title_long", "https://x.com/guide-a/", severity="medium",
                           detail="Title 80 chars", fix="Rewrite title", auto=False)
    _await["status"] = "awaiting_approval"
    _await["extra"] = {"proposal": {"field": "title", "before": "T" * 80,
                                    "after": "AI Automation for Law Firms: Cut Intake Time",
                                    "reason": "targets a real query"}}
    orders.append(_await)

    ctx = {"crawl": crawl, "graph": graph, "money": money, "audit": audit,
           "scores": audit["scores"], "orders": orders, "order_stats": WO.stats(orders),
           # GA4 returns metrics as FLOATS — fixture must match production.
           "insights": {"gsc": dict(gsc, daily=[{"key": f"2026-07-{d:02d}", "clicks": c,
                                                 "impressions": c * 12 + 40}
                                                for d, c in enumerate([0,1,0,2,1,3,2,4,3,5], 20)]),
                        "ga4": {"daily": [{"date": f"2026-07-{d:02d}", "sessions": v}
                                          for d, v in enumerate([1,0,2,1,3,2,4], 23)],
                                "totals": {"sessions": 8.0, "engagementRate": 0.42},
                                            "pages": [{"pagePath": "/guide-a", "sessions": 5.0,
                                                       "totalUsers": 3.0}]}},
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
                   "prompts_won": 1, "prompts_lost": 1, "engines_live": 1, "recommended": 1,
                   "placement": {"first": 1, "middle": 0, "buried": 0},
                   "engines": {"claude": {"connected": True, "mentions": 1, "rate": 50.0},
                               "google_ai": {"connected": True, "snippets": 0, "ranked": 1},
                               "openai": {"connected": False, "mentions": 0, "rate": 0,
                                          "reason": "OPENAI_API_KEY not set"},
                               "perplexity": {"connected": False, "mentions": 0, "rate": 0,
                                              "reason": "PERPLEXITY_API_KEY not set"},
                               "gemini": {"connected": False, "mentions": 0, "rate": 0,
                                          "reason": "GEMINI_API_KEY not set"}},
                   "citations": {"total": 2, "unique_pages": 1,
                                 "by_engine": {"claude": 2},
                                 "top_pages": [("https://x.com/guide-a", 2)]},
                   "results": [{"prompt": "best automation agency vs zapier",
                                "claude": {"connected": True, "mentioned": True,
                                           "rivals_mentioned": ["pricefy.io"],
                                           "citations": ["https://x.com/guide-a"],
                                           "quality": {"placement": "first", "recommended": True}}},
                               {"prompt": "best n8n consultant",
                                "claude": {"connected": True, "mentioned": False,
                                           "rivals_mentioned": ["pricefy.io"], "citations": [],
                                           "quality": {"placement": "absent"}}}],
                   "share_of_voice": {"_you": 1, "pricefy.io": 1},
                   "gaps": [{"prompt": "best automation agency", "rivals": ["pricefy.io"]}]},
           "quotable": {"pages": 2, "quotable": 1, "quotable_pct": 50.0, "faq_schema": 0,
                        "faq_pct": 0.0, "weakest": [{"url": "https://x.com", "question_headings": 1}]},
           "aeo_history": [{"at": "2026-07-29T10:00:00", "score": 0, "mention_rate": 0.0,
                            "prompts": 18, "citations": 0},
                           {"at": "2026-07-30T10:00:00", "score": 40, "mention_rate": 50.0,
                            "prompts": 18, "citations": 2}],
           "crawler_access": {"checked": True, "robots_found": True, "allowed_count": 7,
                              "blocked_count": 1, "bots": [
                                  {"bot": "GPTBot", "vendor": "ChatGPT / OpenAI training",
                                   "blocked": True, "why": "the '*' catch-all rule blocks the whole site (Disallow: /)"},
                                  {"bot": "ClaudeBot", "vendor": "Claude / Anthropic",
                                   "blocked": False, "why": "the '*' catch-all rule allows crawling"},
                                  {"bot": "PerplexityBot", "vendor": "Perplexity",
                                   "blocked": False, "why": "allows crawling"},
                                  {"bot": "Google-Extended", "vendor": "Google Gemini + AI Overviews",
                                   "blocked": False, "why": "allows crawling"}]},
           "entity": {"schema_types": [("Article", 2), ("Organization", 1)],
                      "organization_pages": 1, "person_pages": 0,
                      "entity_links": ["linkedin.com"],
                      "missing_entities": ["wikidata.org", "wikipedia.org", "crunchbase.com"],
                      "score": 17, "pages": 2},
           "geo": {"score": 42,
                   "hreflang": {"pages": 2, "pages_with_hreflang": 1, "coverage_pct": 50.0,
                                "codes": [("en-US", 1)], "issues": [
                                    {"url": "https://x.com/a", "issue": "no self-referencing hreflang"}],
                                "issue_count": 1, "missing_markets": ["de-DE", "de-CH", "en-GB"]},
                   "language": {"pages": 2, "languages": [("en", 2)],
                                "markets": [{"market": "United States", "language": "en",
                                             "pages": 2, "covered": True, "share_pct": 100.0},
                                            {"market": "Germany", "language": "de",
                                             "pages": 0, "covered": False, "share_pct": 0.0}],
                                "uncovered": ["Germany", "Switzerland"]},
                   "performance": {"markets": [
                       {"market": "United States", "impressions": 300, "clicks": 2,
                        "position": 42.0, "ctr": 0.6, "share_pct": 100.0},
                       {"market": "Germany", "impressions": 0, "clicks": 0,
                        "position": 0, "ctr": 0, "share_pct": 0.0}],
                       "total_impressions": 300, "total_clicks": 2,
                       "active": ["United States"], "silent": ["Germany", "Switzerland"]},
                   "service_areas": {"markets": [{"market": "Germany", "url": "", "has_page": False}],
                                     "covered": 0, "missing": ["Germany", "Switzerland"]},
                   "schema": {"pages": 2, "localbusiness": 0, "organization": 1,
                              "has_local": False, "coverage_pct": 0.0}},
           "local_grid": [{"market": "United States", "gl": "us", "query": "automation agency",
                           "position": 0, "found": False, "features": [], "top3": []}],
           "nap": {"declared": 1, "hits": {"name": 0, "phone": 0, "address": 0},
                   "consistent": False, "note": "Wyoming registered-agent address."},
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
           "engine_runs": {"crawl": "2026-07-30T09:00:00"},
           # REAL shape from connectors.api_meters() — {api: {month,spent,calls}}.
           # A float fixture here is what let the production TypeError through.
           "meters": {"serper": {"month": "2026-07", "spent": 1.25, "calls": 40},
                      "dataforseo": {"month": "2026-07", "spent": 0.0, "calls": 0},
                      "anthropic": {"month": "2026-07", "spent": 3.10, "calls": 91}},
           "ranks": [{"query": "ai automation law firm", "delta": 2, "features": ["paa"]}]}

    # ---- REGRESSION: no board may raise on production-shaped data ----
    # Each board is called directly (not through _safe_board) so a bug surfaces
    # here instead of being swallowed into an error card on the live dashboard.
    for _name, _fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        try:
            _fn(ctx)
        except Exception as _e:
            raise AssertionError(f"board {_name} raised on real data: "
                                 f"{type(_e).__name__}: {_e}") from _e

    # the api_meters dict shape that broke production
    assert _spend({"month": "2026-07", "spent": 1.25, "calls": 40}) == 1.25
    assert _spend(2.5) == 2.5 and _spend(None) == 0.0 and _spend("x") == 0.0
    assert _spend({}) == 0.0
    _work = board_work(ctx)
    assert "$1.25" in _work, "SEO spend must sum serper+dataforseo from meter dicts"
    # GA4 floats must render as whole visits, not "8.0"
    _cmd = board_command(ctx)
    assert ">8<" in _cmd or "8 " in _cmd, "sessions must show as an integer"
    # NB: match the RENDERED value, not the bare string — SVG coordinates
    # legitimately contain things like width='8.0'.
    assert ">8.0<" not in _cmd and "8.0 sessions" not in _cmd, "GA4 float leaked into the UI"
    assert "5.0 sessions" not in board_content(ctx), "GA4 float leaked into the UI"

    # a failing board must NOT take the others down
    _boom = dict(_TAB_BOARDS)
    assert "⚠" in _safe_board("Boom", lambda c: 1 / 0, ctx), "must degrade, not raise"
    assert "ZeroDivisionError" in _safe_board("Boom", lambda c: 1 / 0, ctx)

    pages = seo_pages(ctx)
    assert set(pages) == {t for t, _, _ in TABS if t != "seosrc"}, list(pages)
    assert len(TABS) == 10 and len(GROUPS) == 4, (len(TABS), len(GROUPS))
    # every tab belongs to exactly one group
    grouped = [t for _g, _l, _q, ts in GROUPS for t in ts]
    assert sorted(grouped) == sorted(t for t, _, _ in TABS), grouped
    assert len(grouped) == len(set(grouped)), "a tab cannot be in two groups"
    html = "".join(pages.values())
    assert "failed to render" not in html, "no board may fail on real data"

    # ---- ONE section, MERGED: legacy boards stay put, new boards tabbed ----
    legacy = "<div class='card'>existing GSC/GA4/competitor boards</div>"
    sec = seo_section(ctx, legacy_html=legacy)
    # The founder's existing Google boards must be present and NOT inside a tab
    # panel — moving them behind a tab read as deleting them.
    assert legacy in sec, "the existing SEO content must never be dropped"
    assert "seooverview" not in sec, "legacy is no longer a tab — it is always visible"
    # Tabs must be reachable WITHOUT scrolling past the long Google boards:
    # the tab bar comes first, the Google boards follow, still outside any tab.
    assert sec.index("class='sgroups'") < sec.index("class='stabs'"), "groups above tabs"
    assert sec.index("class='stabs'") < sec.index(legacy), "tab bar must precede the Google boards"
    assert sec.index("id='seo-google'") < sec.index(legacy), "Google boards keep their heading"
    assert "id='spanel-seosrc'" in sec, "the Google boards need their own Sources panel"
    assert "position:sticky" in sec, "the tab bar must stay reachable while scrolling"
    # #25 mobile: single-column grids, wrapped groups, scrollable sub-nav
    assert "@media(max-width:600px)" in sec, "no mobile rules"
    assert ".grid.g3,.grid.g2{grid-template-columns:1fr}" in sec, "grids must collapse on phones"
    for tid, _, _ in TABS:
        assert f"id='stab-{tid}'" in sec, f"missing tab button {tid}"
        assert f"id='spanel-{tid}'" in sec, f"missing tab panel {tid}"
        assert f"seoTab('{tid}')" in sec, f"tab {tid} has no click handler"
    for gid, _l, _q, _t in GROUPS:
        assert f"id='sgrp-{gid}'" in sec, f"missing group button {gid}"
        assert f"seoGroup('{gid}')" in sec, f"group {gid} has no click handler"
    # THE CONTRACT CHANGED ON THE FOUNDER'S ORDER (2026-08-06): "old
    # dashboard cards gonna replace". The engine tab panels now carry the
    # audit screens - agent band, health band, issue rows, the per-page
    # command table - and the card grids are gone from them, along with the
    # toolbar that filtered those cards. Only ④ Sources keeps its cards,
    # because those are the founder's original Google boards.
    assert "id='cardq'" not in sec, (
        "the card search box is back but the cards it searched are not")
    assert sec.count("class='spanel on'") == 1, "exactly one tab may start open"
    assert sec.count("class='stab on'") == 1, "exactly one tab may start active"
    assert "same data, same order" in sec, "must reassure the Google boards are intact"
    assert TABS[0][0] == "seocmd", "SEO Command must be the first tab"
    assert "class='spanel on' id='spanel-seocmd'" in sec, \
        "the SEO Command panel must be the one open on load"
    assert "open problem" in sec, "the hint must count problems, not cards"
    assert "s3band" in sec, "the agent command band must lead SEO Command"
    assert "seoAutoSet('safe'" in sec, "the OFF/SAFE/ALL ladder is missing"
    assert "s3fixpage(" in sec, "the per-page command table is missing"
    assert "class='s2issue" in sec, "the issue rows are missing"
    assert ".seoscr{" in sec, "the palette bridge is missing - the screens "\
        "would render unstyled on the dark theme"
    assert "function s3run(" in sec, "the screens' handlers must ship with "\
        "the section - a fetched-in or scriptless screen is dead buttons"
    # the engine panels carry NO card grids; the only cards left are the
    # legacy Google boards in Sources
    _engine_panels = sec[:sec.index("id='spanel-seosrc'")]
    _stray = _re.findall(r"<div class='card (?:overflowcard )?sev-",
                         _engine_panels)
    assert not _stray, f"{len(_stray)} card(s) still render in engine panels"
    # the run bar must expose the free engines by name
    for label in ("free", "Run every SEO engine", "Crawl my site"):
        assert label in sec, f"run bar missing '{label}'"

    counted = len(_re.findall(r"<div class='card (?:overflowcard )?sev-", html))
    assert counted == TOTAL_CARDS, f"expected {TOTAL_CARDS} cards, rendered {counted}"

    # no board may render an unformatted placeholder, a None, or a raw dict
    for bad in ("None", "{}", "{'", "[{"):
        assert bad not in html, f"raw {bad} leaked into the HTML"
    # ---- the design upgrade: identity, severity, action on EVERY card ----
    ids = _re.findall(r"<div class='card (?:overflowcard )?sev-[a-z]+' id='(card-[a-z0-9-]+)'", html)
    assert len(ids) == TOTAL_CARDS, f"{len(ids)} cards have an id, expected {TOTAL_CARDS}"
    assert len(set(ids)) == len(ids),         f"card ids must be unique (they are deep links): {len(ids)} ids, {len(set(ids))} unique"
    assert html.count("data-sev=") == TOTAL_CARDS, "every card needs a severity for sorting"
    assert html.count("data-q=") == TOTAL_CARDS, "every card needs a search blob"
    assert html.count("class='cta'") >= TOTAL_CARDS, "every card must end in a verb"
    # #22 the hero, #11 the bulk-approve buttons, #8 the finding->queue link
    assert "id='card-today'" in html and "START HERE" in html, "no 'what do I do today' hero"
    assert "approveAll('title')" in html, "bulk approve button missing"
    assert "open the approval queue" in html, "findings must link to their work orders"
    # #16 sparklines on the metric cards
    assert "<polyline points=" in html, "no sparklines rendered"
    assert _spark([1, 2, 3, 4]).startswith("<svg"), "sparkline helper broken"
    assert _spark([1]) == "", "a sparkline needs at least 3 points"
    # #17 delta helper
    assert "▲" in _delta(120, 100) and "▼" in _delta(80, 100)
    assert "color:#3FD98B" in _delta(120, 100), "up on a good metric must read green"
    assert "color:#FF6B93" in _delta(120, 100, higher_is_better=False), "direction respected"
    assert _delta(5, 0) == "" and "no change" in _delta(10, 10)
    # severity sort: within a board, broken sorts above healthy
    sevs = _re.findall(r"data-sev='([a-z]+)' data-w='(\d)'", html)
    assert sevs, "severity attributes missing"
    # plain-English titles replaced the jargon, and kept it as a tooltip
    assert "Can AI engines read your site?" in html, "jargon titles not humanised"
    # #20 progressive disclosure — no board may open with more than VISIBLE_CARDS
    assert "overflowcard" in html, "progressive disclosure not applied"
    assert "Show all" in html, "the 'show all' control must exist"
    # P2: compact rows (data-crow) are exempt from the 8-open limit -
    # one line each, deliberately never hidden behind "show all"
    open_now = (html.count("<div class='card sev-")
                - html.count("data-crow='1'"))     # without overflowcard
    grids = html.count("class='grid g3 cardgrid'") + html.count("class='grid g2 cardgrid'")
    assert grids, "no card grids found"
    assert open_now <= VISIBLE_CARDS * grids,         f"{open_now} cards open across {grids} grids (max {VISIBLE_CARDS} each)"
    hidden = html.count("overflowcard sev-")
    # P2 moved most former-overflow cards into compact rows (visible but
    # one line each) - disclosure now defers only FULL cards
    assert hidden > 30, f"only {hidden} cards deferred — disclosure barely applied"
    # #2 sub-menu chips inside the 46-card AEO tab
    assert "class='subnav'" in html and "class='subchip'" in html, "no sub-navigation"
    assert "id='sub-answer-presence'" in html, "sub-sections must be anchored"

    assert "title='AI crawler access'" in html, "the real term must survive as a tooltip"
    assert not _re.search(r"\b(nan|NaN|inf)\b", html), "a non-finite number reached the UI"
    # rows carry their insight in the record pane, not inline - the 💡
    # census applies to FULL cards only (rows are counted via data-crow)
    _fulls = html.count("<div class='card sev-") - html.count("data-crow='1'")
    assert html.count("💡") >= _fulls * 0.85, "most FULL cards must carry a qualitative read"
    # honest degradation, not fake numbers
    assert "DataForSEO not connected" in html, "must state WHY off-page is empty"
    assert "not connected" in html and "—" in html
    # every board rendered its header
    for icon in ("🧭", "🔧", "📇", "📄", "🔑", "📚", "🔗", "🌐", "🤖", "📍", "🛠"):
        assert icon in html, f"board {icon} missing"
    print(f"seo_boards self-check OK — 11 boards, {counted} cards rendered, "
          f"{html.count('💡')} qualitative reads, honest empty states")
