"""
content_engine_vx2.py
============================================================================
THE NEW UI. Four boards, 127 subsections, FOUR LEVELS, parallel to the old.

WHY THIS EXISTS
  2,294 cards across 9 sections and 127 tabs. 88% of the cards could only be
  read. The browser built 81,742 elements on every load. The founder could not
  find the twelve percent that mattered, and said so: "i lost this is why i
  came to you".

THE GRAMMAR (the design document, not a summary of it)
  Level 1   the four boards     DECIDE MAKE MARKET RUN - the whole navigation
  Level 2   a board             the question, ONE number that answers it, a
                                plain reading, "What to do", then its
                                subsections as a LIST you enter - never their
                                contents dumped inline
  Level 3   a readout           one subsection per screen: breadcrumb, header
                                with a hero value drawn in its shape, then
                                every measurement as one line, problems
                                coloured and grouped first
  Level 4   the record          any line, tapped: where the number came from,
                                what kind of number it is, the full reading,
                                and the line's own buttons

  6 shapes  SCORE RATIO COUNT TREND SPLIT TABLE (+ STATE, PREVIEW), drawn by
  content_engine_vx2_shapes exactly as the design draws them, and only when
  the data really has that shape.

  one rule  a measurement that fits no shape is a sentence, not a card

HOW 127 SUBSECTIONS ARE BUILT AT ONCE
  Not by hand. Every existing board already produces its measurements as
  8-tuples through ONE funnel: seo_boards._vizcards, named-imported into all
  nine board modules. capture() swaps that name in each namespace, runs the
  existing board function, and collects the tuples instead of the HTML.

  So the new UI reads the SAME data the old boards read, through the SAME
  functions, and can never drift from them. Adding a subsection later is a row
  in MANIFEST, not a new screen.

SAFETY
  This module renders. It does not fetch, compute, publish, send or spend.
  It is served at /vx2 while the old dashboard keeps serving / untouched.
  Deleting this file returns the system exactly to where it was.
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_vx2_shapes as shapes

# the nine modules whose _vizcards must be swapped during capture
_MODULES = ("cockpit", "factory", "seo", "outreach", "media", "bi", "risk",
            "sga", "system")

# board id -> (label, question, which sections it absorbs)
BOARDS = (
    ("decide", "Decide", "What needs me?", ("cockpit",)),
    ("make", "Make", "What are we publishing?", ("factory", "sga")),
    ("market", "Market", "Are we being found and heard?",
     ("seo", "outreach", "media")),
    ("run", "Run", "Is the machine healthy and paying?",
     ("system", "risk", "bi")),
)

# the six shapes, plus the two specials. The label is what the reader sees.
SHAPES = {
    "SCORE": "0-100 against a threshold",
    "RATIO": "X of Y, where Y is knowable",
    "COUNT": "a plain quantity",
    "TREND": "the same number over time",
    "SPLIT": "parts of a whole",
    "TABLE": "many rows, each actionable",
    "STATE": "up, down or off, per thing",
    "PREVIEW": "the artefact itself",
}

# shape assignment by keyword, first match wins. Auditable, not hand-waved.
_SHAPE_RULES = (
    ("PREVIEW", ("preview", "creative library", "creative & image", "serp")),
    ("TABLE", ("queue", "jobs", "failures", "register", "work orders",
               "outbox", "manager", "sequence", "replies", "bookings",
               "search terms", "keyword research", "experiments", "log",
               "sourcing", "wires", "connect", "agents", "dependencies")),
    ("STATE", ("keys", "autonomy", "engine state", "deploy", "channel health",
               "data flow", "loop map", "compliance", "security", "continuity",
               "routing", "brand & ci", "territories", "google hub", "sources")),
    ("SCORE", ("command", "health", "quality", "brief", "drift", "freshness",
               "deliverability", "landing pages", "technical", "on-page")),
    ("RATIO", ("indexing", "capacity", "storage", "compute", "coverage",
               "icp", "conversion", "attribution", "funnel", "aeo", "geo",
               "workforce")),
    ("SPLIT", ("channels", "campaign types", "targeting", "audiences",
               "audience", "markets", "repurposing", "bidding", "engagement",
               "assets", "keywords", "off-page")),
    ("TREND", ("demand", "traffic", "revenue", "spend", "cost", "budget",
               "pacing", "throughput", "customers", "economics",
               "consultations", "lead gen", "outreach", "push", "paid social",
               "blog", "competition", "cross-channel", "risk", "playbook",
               "what works", "content value", "pipeline", "strategy",
               "calendar", "planner", "launch", "router", "approvals",
               "decision")),
)


def _shape_for(label: str) -> str:
    low = str(label or "").lower()
    for shape, keys in _SHAPE_RULES:
        if any(k in low for k in keys):
            return shape
    return "COUNT"


# ---------------------------------------------------------------------------
# THE MANIFEST - built from the REAL tab tables, never hand-typed
# ---------------------------------------------------------------------------
def build_manifest() -> list:
    """Every subsection: board, label, icon, shape, and the function that
    already renders it. Read from each module's own TABS/_TAB_BOARDS, so it
    cannot describe a board that does not exist."""
    import importlib
    sec_to_board = {}
    for bid, _lab, _q, sections in BOARDS:
        for s in sections:
            sec_to_board[s] = bid
    out = []
    for mod in _MODULES:
        M = importlib.import_module(f"content_engine_{mod}_boards")
        tabs = {t[0]: (t[1], t[2]) for t in getattr(M, "TABS", ())}
        counts = getattr(M, "_TAB_COUNTS", {}) or getattr(M, "CARD_COUNTS", {})
        seen = set()
        for tab_id, entries in (getattr(M, "_TAB_BOARDS", {}) or {}).items():
            seen.add(tab_id)
            icon, label = tabs.get(tab_id, ("", tab_id))
            fn = entries[0][1] if entries else None
            out.append({
                "board": sec_to_board.get(mod, "run"),
                "module": mod, "tab": tab_id, "icon": icon, "label": label,
                "shape": _shape_for(label), "cards": counts.get(tab_id, 0),
                "fn": fn, "note": "",
            })
        # A DECLARED TAB WITH NO RENDERER IS STILL A SUBSECTION. 'Sources' is
        # rendered by seo_section's own panel rather than _TAB_BOARDS, so a
        # naive read of that table loses it silently and reports 126 of 127.
        # Carry it with an honest note instead of dropping it.
        for tab_id, (icon, label) in tabs.items():
            if tab_id in seen:
                continue
            out.append({
                "board": sec_to_board.get(mod, "run"),
                "module": mod, "tab": tab_id, "icon": icon, "label": label,
                "shape": _shape_for(label), "cards": counts.get(tab_id, 0),
                "fn": None,
                "note": ("Rendered by its section's own panel, not by the "
                         "board table. It keeps its place here so the count "
                         "stays honest."),
            })
    return out


MANIFEST = build_manifest()


# ---------------------------------------------------------------------------
# CAPTURE - the mechanism that makes 127 subsections one renderer
# ---------------------------------------------------------------------------
def capture(fn, ctx) -> list:
    """Run an existing board function and collect the MEASUREMENTS it would
    have drawn, instead of its HTML.

    _vizcards is named-imported into all nine board modules, so the name has
    to be swapped in each namespace: patching only the source module would
    leave the other eight bound to the original. Always restored, even when
    the board raises - a board that fails must not take its neighbours down.
    """
    import importlib
    rows = []

    def _grab(cards, cols=3):
        for c in (cards or ()):
            if isinstance(c, (list, tuple)) and len(c) >= 6:
                rows.append(c)
        return ""

    mods, saved = [], {}
    for m in _MODULES:
        try:
            M = importlib.import_module(f"content_engine_{m}_boards")
        except Exception:
            continue
        if hasattr(M, "_vizcards"):
            mods.append(M)
            saved[id(M)] = M._vizcards
            M._vizcards = _grab
    try:
        fn(ctx)
    except Exception as e:
        rows.append((f"This subsection failed to read",
                     type(e).__name__, str(e)[:120], "",
                     "The other subsections are unaffected. The failure is "
                     "in the board that produces this data, not in the view.",
                     "the board itself", "#FF6B93", ""))
    finally:
        for M in mods:
            M._vizcards = saved[id(M)]
    return rows


# ---------------------------------------------------------------------------
# WIRING - where every button on a card is allowed to land
# ---------------------------------------------------------------------------
# The old dashboard's nav() is called with three different kinds of id: a
# section ("system"), a tab inside a section ("sysconnect"), and an alias the
# old NAVALIAS table resolved ("appr" -> cockpit). VX2 has to answer all three
# or its buttons go dead, which is the single failure this rebuild exists to
# stop. Anything that resolves to nothing SAYS SO instead of silently doing
# nothing - a button that lies is worse than a button that is missing.
#
# section or alias -> MODULE, never straight to a board. The board is then
# derived from BOARDS above, so there is exactly one place that says which
# module lives on which board. Writing the board here as well would be the
# same two-hand-written-lists bug that has bitten this engine five times.
_SEC_MODULE = {
    "cockpit": "cockpit", "factory": "factory", "content": "factory",
    "sga": "sga", "seo": "seo", "outreach": "outreach", "media": "media",
    "system": "system", "risk": "risk", "riskinfra": "risk", "bi": "bi",
    # the old NAVALIAS table, resolved to the module it meant
    "agents": "system", "map": "system", "overview": "system",
    "workforce": "risk", "infra": "risk", "business": "bi", "marketing": "bi",
    "sales": "bi", "customer": "bi", "finance": "bi", "budget": "bi",
    "exec": "bi", "leads": "outreach", "email": "outreach", "social": "sga",
    "google": "sga", "ads": "sga", "mission": "cockpit", "ops": "cockpit",
    "appr": "cockpit", "learn": "cockpit",
}


def wiring() -> dict:
    """tab id -> board id, for every one of the 127. Built from the manifest,
    so a tab that exists is always reachable and one that does not is never
    claimed."""
    return {m["tab"]: m["board"] for m in MANIFEST}


def section_wiring() -> dict:
    """section or alias -> [board, first subsection of that section].

    Landing on the BOARD alone was not enough: pressing "Open Risk" while
    already on the Run board changed nothing on screen, which is the same
    silence the founder objected to when approving a page told him nothing.
    A section link now lands on that section's first subsection, so the screen
    always moves when you press something.
    """
    first = {}
    for m in MANIFEST:
        first.setdefault(m["module"], (m["board"], m["tab"]))
    out = {}
    for sec, mod in _SEC_MODULE.items():
        if mod in first:
            out[sec] = list(first[mod])
    return out


# ---------------------------------------------------------------------------
# render helpers - light, minimal, button-first
# ---------------------------------------------------------------------------
def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


_SEV = {"#FF6B93": ("bad", "var(--bad)"), "#F5B14C": ("warn", "var(--warnc)"),
        "#3FD98B": ("ok", "var(--okc)")}


def _tone(accent):
    """Old palette accent -> new state. Anything else is quiet."""
    return _SEV.get(str(accent or "").upper(), ("quiet", "var(--ft)"))


_EVIDENCE = None


def _evidence(src: str) -> dict:
    """What kind of number this is, from the evidence table. Cached import;
    an honest 'Unclassified' when the token is unknown, never a guess."""
    global _EVIDENCE
    if _EVIDENCE is None:
        try:
            import content_engine_evidence as E
            _EVIDENCE = E
        except Exception:
            _EVIDENCE = False
    if not _EVIDENCE:
        return {"label": "Unknown", "why": "The evidence module is unavailable."}
    try:
        return _EVIDENCE.classify(src)
    except Exception:
        return {"label": "Unknown", "why": "Classification failed."}


def _line(card) -> tuple:
    """One measurement as (weight, html). Problems weigh less so they sort up.

    LEVEL 4 LIVES ON THIS LINE. The row carries its whole record in data
    attributes: value, reading, source, and the evidence class of that source.
    Tapping the line opens the record; the buttons on the line still work
    directly and never open it.
    """
    title = card[0] if len(card) > 0 else ""
    big = card[1] if len(card) > 1 else ""
    sub = card[2] if len(card) > 2 else ""
    insight = card[4] if len(card) > 4 else ""
    src = card[5] if len(card) > 5 else ""
    accent = card[6] if len(card) > 6 else ""
    links = card[7] if len(card) > 7 else ""
    state, col = _tone(accent)
    weight = {"bad": 0, "warn": 1, "quiet": 2, "ok": 3}[state]
    cls = f" v2-{state}" if state in ("bad", "warn") else ""
    ev = _evidence(src)
    return (weight,
            f"<div class='v2row{cls}' role='button' tabindex='0' "
            f"onclick='vx2rec(this,event)' "
            f"onkeydown=\"if(event.key==='Enter')vx2rec(this,event)\" "
            f"data-nm='{e(title)}' data-val='{e(big)}' data-sub='{e(sub)}' "
            f"data-why='{e(insight)}' data-src='{e(src)}' "
            f"data-kind='{e(ev.get('label', ''))}' "
            f"data-kmean='{e(ev.get('why') or ev.get('meaning') or '')}' "
            f"data-state='{state}'>"
            f"<span class='v2dot' style='background:{col}'></span>"
            f"<span class='v2nm'>{e(title)}</span>"
            f"<span class='v2why'>{e(insight)[:110]}</span>"
            f"<span class='v2val' style='color:{col}'>{e(big)}</span>"
            f"<span class='v2sub'>{e(sub)[:22]}</span>"
            + (f"<span class='v2act'>{links}</span>" if links else "")
            + f"<span class='v2go'>&rsaquo;</span></div>")


def _bad_count(cards) -> int:
    return sum(1 for c in cards
               if _tone(c[6] if len(c) > 6 else "")[0] in ("bad", "warn"))


def _sec_head(entry, n_cards, n_bad=0) -> str:
    """The one-line title every subsection wears, whatever screen follows."""
    return (f"<div class='v2head'><div><h3>{e(entry['label'])}</h3>"
            f"<p class='v2sub2'>{n_cards} measurements"
            + (f" &middot; <b style='color:var(--bad)'>{n_bad} want attention</b>"
               if n_bad else " &middot; nothing wants attention")
            + f"</p></div>"
            f"<span class='v2shape'>{entry['shape']}</span></div>")


def _rows(cards, entry, title=None) -> str:
    """Measurements as sorted lines, problems first."""
    lines = sorted((_line(c) for c in cards), key=lambda t: t[0])
    if not lines:
        why = (entry or {}).get("note") or (
            "Nothing measured here yet. This subsection has no data on your "
            "box, which is not the same as a zero.")
        return f"<p class='v2empty'>{e(why)}</p>"
    body = "".join(h for _w, h in lines)
    if title:
        return (f"<div class='s2meas'><h4>{e(title)}</h4>{body}</div>")
    return body


def readout(entry, ctx) -> str:
    """A subsection's lines with its title, used by the special screens."""
    cards = capture(entry["fn"], ctx) if entry.get("fn") else []
    return _sec_head(entry, len(cards), _bad_count(cards)) + _rows(cards, entry)


# ---------------------------------------------------------------------------
# SPECIAL SUBSECTIONS - where a list of measurements is the wrong shape
# ---------------------------------------------------------------------------
# Most of the 127 are answered well by grouped lines. Two groups are not. The
# ten SEO subsections are an audit, which means the list of what is WRONG has
# to lead and each row has to carry its repair. The Media Command subsection
# is an ad manager, which means a hierarchy and a creative preview.
#
# Both still read the same captured measurements underneath, so nothing here
# can invent a figure the old boards would not also show.
_SEO_SCREENS = {
    "seocmd": "command", "seotech": "technical", "seoonpage": "issues",
    "seokw": "issues", "seowork": "workorders", "seoaeo": "aeo",
    "seooff": "backlinks", "seogen": "geo_gen", "seogeo": "geo_local",
}


def special(entry, ctx, extra) -> str:
    """Route a subsection to its purpose-built screen, or to the default."""
    tab, mod = entry.get("tab"), entry.get("module")
    try:
        if mod == "seo":
            import content_engine_vx2_seo as S
            kind = _SEO_SCREENS.get(tab)
            cards = capture(entry["fn"], ctx) if entry.get("fn") else []
            head = _sec_head(entry, len(cards), _bad_count(cards))
            if kind == "command":
                return head + S.command_screen(ctx, cards)
            if kind == "technical":
                return head + S.technical_screen(ctx, cards)
            if kind == "issues":
                return head + S.issue_screen(tab, ctx, cards)
            if kind == "workorders":
                return head + S.workorders_screen(ctx, cards)
            if kind == "aeo":
                return (head + S.health_header(ctx) + S.aeo_screen(ctx)
                        + _rows(cards, entry, title="Measurements"))
            if kind == "backlinks":
                return (head + S.health_header(ctx) + S.backlinks_screen(ctx)
                        + _rows(cards, entry, title="Measurements"))
            if kind == "geo_gen":
                return (head + S.health_header(ctx) + S.geo_gen_screen(ctx)
                        + _rows(cards, entry, title="Measurements"))
            if kind == "geo_local":
                return (head + S.health_header(ctx) + S.geo_local_screen(ctx)
                        + _rows(cards, entry, title="Measurements"))
            # Sources keeps its measurements under the audit header, so the
            # score you judge them against is on screen with them.
            return head + S.health_header(ctx) + _rows(cards, entry)
        if mod == "media" and tab == "mbcmd":
            import content_engine_vx2_ads as A
            cards = capture(entry["fn"], ctx) if entry.get("fn") else []
            return (_sec_head(entry, len(cards), _bad_count(cards))
                    + A.ads_screen(extra.get("ads") or {})
                    + _rows(cards, entry, title="Measurements"))
    except Exception as ex:
        return (_sec_head(entry, 0)
                + "<p class='v2empty'>This screen failed to build: "
                + f"{e(type(ex).__name__)}. The other subsections are "
                + "unaffected.</p>")
    return ""


# ---------------------------------------------------------------------------
# LEVEL 3 - THE READOUT: one subsection, its own screen
# ---------------------------------------------------------------------------
_GROUPS = ((0, "Needs attention"), (1, "Needs attention"),
           (3, "Healthy"), (2, "Readings"))


def readout_page(tab: str, kw: dict) -> str:
    """Breadcrumb, header with the hero drawn in its shape, then every
    measurement grouped: what wants you first, the healthy, the quiet."""
    # THE PAGES SCREEN is VX2-only: the same 600 work orders keyed by URL
    # instead of by issue type. It lives outside the manifest because the
    # manifest mirrors the founder's 127 and this is a second door, not a
    # 128th room.
    if tab == "seopages":
        import content_engine_vx2_seo as S
        ctx = ctxs_from(kw).get("seo") or {}
        return ("<div class='v2crumb'>"
                "<a href='#market' onclick=\"return vx2go('market')\">Market"
                "</a><span>&rsaquo;</span>"
                "<a href='#seocmd' onclick=\"return vx2read('seocmd')\">SEO"
                "</a><span>&rsaquo;</span><b>Pages</b></div>"
                "<div class='v2readbody'>"
                + S.health_header(ctx) + S.pages_screen(ctx) + "</div>")
    entry = next((m for m in MANIFEST if m["tab"] == tab), None)
    if not entry:
        return "<p class='v2empty'>No subsection by that name.</p>"
    board_label = next(b[1] for b in BOARDS if b[0] == entry["board"])
    ctx = ctxs_from(kw).get(entry["module"]) or {}
    cards = capture(entry["fn"], ctx) if entry.get("fn") else []
    n_bad = _bad_count(cards)

    crumb = (f"<div class='v2crumb'>"
             f"<a href='#{e(entry['board'])}' "
             f"onclick=\"return vx2go('{e(entry['board'])}')\">"
             f"{e(board_label)}</a><span>&rsaquo;</span>"
             f"<b>{e(entry['label'])}</b>"
             f"<span>&middot;</span><span>{len(cards)} measurements</span>"
             f"</div>")

    # the special screens ARE this level; they keep their own bodies
    sp = special(entry, ctx, {"ads": kw.get("ads") or {}})
    if sp:
        return crumb + f"<div class='v2readbody'>{sp}</div>"

    # hero: the subsection's own first measurement, drawn in its shape. The
    # first card of every old board is its command number, so this is real
    # data given the design's ink, never a decoration.
    hero = ""
    if cards:
        c0 = cards[0]
        state0 = _tone(c0[6] if len(c0) > 6 else "")[0]
        hero = shapes.hero(entry["shape"], c0[1] if len(c0) > 1 else "",
                           str(c0[2] if len(c0) > 2 else ""),
                           accent_state=state0)
    head = (f"<div class='v2head v2head3'><div>"
            f"<h3>{e(entry['label'])}</h3>"
            f"<p class='v2sub2'>"
            + (f"<b style='color:var(--bad)'>{n_bad} want attention</b>"
               if n_bad else "nothing wants attention")
            + f"</p></div>"
            f"<span class='v2hero'>{hero}</span>"
            f"<span class='v2shape'>{entry['shape']}</span></div>")

    if not cards:
        why = entry.get("note") or (
            "Nothing measured here yet. This subsection has no data on your "
            "box, which is not the same as a zero.")
        return crumb + f"<div class='v2readbody'>{head}" \
                       f"<p class='v2empty'>{e(why)}</p></div>"

    # grouped lines: problems first with their name on the group, then the
    # healthy, then the quiet readings. Nothing hidden behind a click.
    lines = sorted((( * _line(c),) for c in cards), key=lambda t: t[0])
    blocks, done = [], set()
    for w, gname in _GROUPS:
        if gname in done:
            continue
        ws = (0, 1) if gname == "Needs attention" else (w,)
        got = [h for lw, h in lines if lw in ws]
        if not got:
            continue
        done.add(gname)
        blocks.append(f"<p class='v2grp'>{e(gname)}</p>" + "".join(got))
    return crumb + f"<div class='v2readbody'>{head}{''.join(blocks)}</div>"


# ---------------------------------------------------------------------------
# LEVEL 2 - A BOARD: the question, its answer, what to do, and the list
# ---------------------------------------------------------------------------
def _board_stats(bid: str, kw: dict) -> list:
    """(entry, cards, bad, warn) for each subsection of a board. One capture
    per subsection, reused by the answer, the to-do list, and the list."""
    ctxs = ctxs_from(kw)
    out = []
    for m in MANIFEST:
        if m["board"] != bid:
            continue
        cards = capture(m["fn"], ctxs.get(m["module"]) or {}) if m.get("fn") else []
        bad = sum(1 for c in cards if _tone(c[6] if len(c) > 6 else "")[0] == "bad")
        warn = sum(1 for c in cards if _tone(c[6] if len(c) > 6 else "")[0] == "warn")
        out.append((m, cards, bad, warn))
    return out


def board_page(bid, label, question, kw) -> str:
    """LEVEL 2. The number that answers the question, a plain reading,
    the few things worth doing, then the subsections as a list you enter.
    A board never dumps its subsections' contents - that is the scroll wall
    this design exists to kill."""
    stats = _board_stats(bid, kw)
    n_bad = sum(b for _m, _c, b, _w in stats)
    n_warn = sum(w for _m, _c, _b, w in stats)
    hot = [(m, b + w) for m, _c, b, w in stats if b + w]
    hot.sort(key=lambda t: -t[1])

    # THE ANSWER. Market answers with site health when a crawl has scored it;
    # every board answers with what wants attention. Both are computed from
    # the same measurements the lines show - never a number of their own.
    if bid == "market" and (kw.get("seo_ctx") or {}).get("scores", {}).get("overall") is not None:
        overall = (kw["seo_ctx"]["scores"] or {}).get("overall")
        hero = shapes.score_ring(float(overall))
        unit = "site health"
    else:
        n = n_bad + n_warn
        hero = shapes.count_big(n, "")
        unit = "need you now" if n else "nothing needs you"

    if hot:
        worst = hot[0][0]["label"]
        reading = (f"{n_bad + n_warn} of this board's measurements want "
                   f"attention, across {len(hot)} of its {len(stats)} "
                   f"subsections. The loudest is {worst}.")
    else:
        reading = ("Every measurement on this board is either healthy or "
                   "quiet. Nothing here is waiting on you.")

    # WHAT TO DO: the worst lines across the whole board, with their real
    # buttons, each naming the subsection it lives in.
    todo = []
    for m, cards, b, w in stats:
        if not (b + w):
            continue
        for c in cards:
            state, col = _tone(c[6] if len(c) > 6 else "")
            if state not in ("bad", "warn"):
                continue
            links = c[7] if len(c) > 7 and c[7] else ""
            todo.append((0 if state == "bad" else 1, 0 if links else 1,
                         m, c, state, col, links))
    todo.sort(key=lambda t: (t[0], t[1]))
    todo_html = ""
    if todo:
        rows = []
        for _s, _l, m, c, state, col, links in todo[:5]:
            rows.append(
                f"<div class='v2row v2-{state}'>"
                f"<span class='v2dot' style='background:{col}'></span>"
                f"<span class='v2nm'>{e(c[0])}"
                f"<em>{e(m['label'])}</em></span>"
                f"<span class='v2why'>{e(c[4] if len(c) > 4 else '')[:110]}</span>"
                f"<span class='v2val' style='color:{col}'>{e(c[1] if len(c) > 1 else '')}</span>"
                + (f"<span class='v2act'>{links}</span>" if links else "")
                + f"<span class='v2act'><button class='v2open' "
                  f"onclick=\"vx2read('{e(m['tab'])}')\">Open</button></span>"
                  f"</div>")
        more = len(todo) - 5
        todo_html = ("<p class='v2grp'>What to do</p>" + "".join(rows)
                     + (f"<p class='v2more'>and {more} more, each inside its "
                        f"subsection</p>" if more > 0 else ""))

    # THE LIST. Name, shape, count, state dot. Entering one opens Level 3.
    items = []
    for m, cards, b, w in stats:
        col = ("var(--bad)" if b else "var(--warnc)" if w else "var(--ft)")
        items.append(
            f"<div class='v2row v2li' role='button' tabindex='0' "
            f"onclick=\"vx2read('{e(m['tab'])}')\" "
            f"onkeydown=\"if(event.key==='Enter')vx2read('{e(m['tab'])}')\">"
            f"<span class='v2dot' style='background:{col}'></span>"
            f"<span class='v2nm'>{e(m['label'])}</span>"
            + (f"<span class='v2why'>{b + w} want attention</span>" if b + w
               else "<span class='v2why'></span>")
            + f"<span class='v2sub'>{len(cards) or '&ndash;'}</span>"
            f"<span class='v2shape'>{m['shape']}</span>"
            f"<span class='v2go'>&rsaquo;</span></div>")

    # THE COCKPIT CARD: on Decide, the SEO agent's commands sit at the top,
    # so the whole fleet can be run without ever opening the Market board.
    seo_card = ""
    if bid == "decide":
        try:
            import content_engine_vx2_seo as _S
            seo_card = ("<p class='v2grp'>Command the SEO agent</p>"
                        + _S.cockpit_card(kw.get("seo_ctx") or {}))
        except Exception:
            seo_card = ""

    return (f"<div class='v2board'><p class='v2q'>{e(question)}</p>"
            f"<div class='v2ans'><span class='v2hero'>{hero}</span>"
            f"<span class='v2unit'>{e(unit)}</span></div>"
            f"<p class='v2reading'>{e(reading)}</p>"
            + seo_card + todo_html
            + f"<p class='v2grp'>Its {len(stats)} subsections</p>"
            + "".join(items) + "</div>")


# ---------------------------------------------------------------------------
# THE PAGE
# ---------------------------------------------------------------------------
def ctxs_from(kw: dict) -> dict:
    """The dashboard's kwargs -> module name -> context. Same dict object the
    old boards get, so the two UIs cannot read different numbers."""
    return {m: (kw.get(f"{m}_ctx") or {}) for m in _MODULES}


def board_html(bid: str, kw: dict) -> str:
    """One board's Level 2 HTML on its own, for the /vx2/board route."""
    row = next((b for b in BOARDS if b[0] == bid), None)
    if not row:
        return "<p class='v2empty'>No board by that name.</p>"
    _b, label, q, _s = row
    return board_page(bid, label, q, kw)


CSS = """
*{box-sizing:border-box}
:root{--pap:#FCFCFB;--card:#FFF;--ln:#E8E8E4;--tx:#16181A;--dm:#61666B;
--ft:#9AA0A5;--ac:#1B57F0;--bad:#C0392B;--warnc:#B5730D;--okc:#1F7A4C;
--badbg:#FDF4F3;--warnbg:#FDF9F0;--hov:#F5F7FE;
/* the four names the shared handlers write into inline styles. They come from
   the old dark theme; without them every toast renders transparent-on-white. */
--ink:#16181A;--s2:#FFFFFF;--good:#1F7A4C;--warn:#B5730D}
@media (prefers-color-scheme:dark){:root{--pap:#101214;--card:#171A1D;
--ln:#282C31;--tx:#ECEEF0;--dm:#A2A9B0;--ft:#767D85;--ac:#5B8CFF;
--bad:#FF7A6E;--warnc:#F0B54A;--okc:#4FD99A;--badbg:#241A19;--warnbg:#221D14;
--hov:#1C2126;--ink:#ECEEF0;--s2:#1D2126;--good:#4FD99A;--warn:#F0B54A}}
:root[data-theme=dark]{--pap:#101214;--card:#171A1D;--ln:#282C31;--tx:#ECEEF0;
--dm:#A2A9B0;--ft:#767D85;--ac:#5B8CFF;--bad:#FF7A6E;--warnc:#F0B54A;
--okc:#4FD99A;--badbg:#241A19;--warnbg:#221D14;--hov:#1C2126;--ink:#ECEEF0;
--s2:#1D2126;--good:#4FD99A;--warn:#F0B54A}
:root[data-theme=light]{--pap:#FCFCFB;--card:#FFF;--ln:#E8E8E4;--tx:#16181A;
--dm:#61666B;--ft:#9AA0A5;--ac:#1B57F0;--bad:#C0392B;--warnc:#B5730D;
--okc:#1F7A4C;--badbg:#FDF4F3;--warnbg:#FDF9F0;--hov:#F5F7FE;--ink:#16181A;
--s2:#FFFFFF;--good:#1F7A4C;--warn:#B5730D}
body.v2wrap{background:var(--pap);color:var(--tx);min-height:100vh;margin:0;
font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
.v2nav{display:flex;gap:3px;padding:11px 18px;border-bottom:1px solid var(--ln);
background:var(--card);position:sticky;top:0;z-index:20;align-items:center}
.v2nav button{font-size:13px;padding:7px 14px;border-radius:7px;color:var(--dm);
background:transparent;border:0;cursor:pointer;font-family:inherit;font-weight:500;
display:flex;gap:7px;align-items:center}
.v2nav button:hover{background:var(--hov)}
.v2nav button.on{background:var(--ac);color:#fff;font-weight:600}
.v2nav .v2n{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;opacity:.62}
.v2brand{font-weight:700;font-size:14px;margin-right:14px;letter-spacing:-.02em}
.v2back{margin-left:auto;font-size:12px;color:var(--ft);text-decoration:none}
.v2back:hover{color:var(--ac)}
.v2main{max-width:1180px;margin:0 auto;padding:26px 22px 90px}
/* --- level 2, a board --- */
.v2q{font-size:14px;color:var(--dm);margin:0 0 10px}
.v2ans{display:flex;align-items:center;gap:14px;margin:0 0 6px}
.v2ans .shp-count b{font-size:52px}
.v2unit{font-size:15px;color:var(--ft)}
.v2reading{font-size:14.5px;color:var(--dm);margin:0 0 8px;max-width:62ch;
line-height:1.6}
.v2grp{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;
letter-spacing:.14em;text-transform:uppercase;color:var(--ft);margin:24px 0 8px}
.v2more{font-size:12px;color:var(--ft);margin:6px 0 0;padding:0 10px}
.v2open{font-size:11.5px;padding:4px 10px;border-radius:6px;
border:1px solid var(--ln);background:var(--card);color:var(--tx);
cursor:pointer;font-family:inherit;white-space:nowrap}
.v2open:hover{border-color:var(--ac);color:var(--ac)}
/* --- level 3, a readout --- */
.v2crumb{display:flex;gap:8px;align-items:center;font-size:12.5px;
color:var(--dm);margin:0 0 16px}
.v2crumb a{color:var(--ac);text-decoration:none;font-weight:600}
.v2crumb a:hover{text-decoration:underline}
.v2crumb b{color:var(--tx);font-weight:600}
.v2crumb span{color:var(--ft)}
.v2readbody{}
.v2head{display:flex;align-items:flex-end;gap:14px;padding:0 0 8px;
border-bottom:1px solid var(--ln);margin-bottom:2px}
.v2head3{align-items:center;padding-bottom:12px}
.v2head h3{margin:0;font-size:20px;font-weight:700;letter-spacing:-.015em}
.v2sub2{margin:2px 0 0;font-size:12px;color:var(--ft)}
.v2hero{margin-left:auto;display:flex;align-items:center}
.v2shape{font-family:ui-monospace,Menlo,monospace;font-size:9.5px;
font-weight:700;letter-spacing:.1em;color:var(--ft);border:1px solid var(--ln);
border-radius:4px;padding:2px 7px;white-space:nowrap}
.v2head .v2shape{margin-left:0}
.v2head:not(.v2head3) .v2shape{margin-left:auto}
/* --- the line --- */
.v2row{display:flex;gap:12px;align-items:center;padding:7px 10px;
border-bottom:1px solid var(--ln);font-size:13.5px;border-radius:5px;
cursor:pointer}
.v2row:hover{background:var(--hov)}
.v2row:hover .v2go{color:var(--ac)}
.v2dot{width:6px;height:6px;border-radius:50%;flex:none}
.v2nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.v2nm em{display:block;font-style:normal;font-size:11px;color:var(--ft);
font-family:ui-monospace,Menlo,monospace}
.v2why{flex:1.3;min-width:0;color:var(--ft);font-size:12px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.v2val{font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;
font-size:14px;font-weight:700;white-space:nowrap}
.v2sub{color:var(--ft);font-size:11px;white-space:nowrap;
font-family:ui-monospace,Menlo,monospace}
.v2go{color:var(--ft);font-size:15px;flex:none}
.v2act{display:flex;gap:6px;flex:none}
.v2act .cta,.v2act .cbtn,.v2act button{font-size:11.5px;padding:4px 10px;
border-radius:6px;border:1px solid var(--ln);background:var(--card);
color:var(--tx);cursor:pointer;font-family:inherit;white-space:nowrap}
.v2act button:hover{border-color:var(--ac);color:var(--ac)}
.v2act button[disabled]{opacity:.55;cursor:default}
.v2act .empty,.v2act .mut,.v2act .dim{color:var(--ft);font-size:11px}
.v2-bad{background:var(--badbg)}
.v2-warn{background:var(--warnbg)}
.v2li .v2shape{flex:none}
.v2empty{font-size:13px;color:var(--ft);padding:12px 10px;margin:0;line-height:1.55}
/* --- level 4, the record --- */
.rec dt{font-family:ui-monospace,Menlo,monospace;font-size:10px;
letter-spacing:.12em;text-transform:uppercase;color:var(--ft);margin:16px 0 4px}
.rec dd{margin:0;font-size:14px;line-height:1.6;max-width:64ch}
.rec .recval{font-family:ui-monospace,Menlo,monospace;font-size:30px;
font-weight:700;line-height:1;margin:4px 0 0}
.rec .recacts{display:flex;gap:8px;margin-top:18px;flex-wrap:wrap}
#dlgwrap{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);
z-index:9998;padding:5vh 4vw;overflow:auto}
#dlgwrap.on{display:block}
.dlg{max-width:860px;margin:0 auto;background:var(--card);border-radius:12px;
border:1px solid var(--ln);box-shadow:0 20px 60px rgba(0,0,0,.3)}
.dlghead{display:flex;align-items:center;gap:12px;padding:14px 18px;
border-bottom:1px solid var(--ln)}
.dlghead h3{margin:0;font-size:16px;font-weight:700}
.dlgx{margin-left:auto;background:transparent;border:0;font-size:16px;
cursor:pointer;color:var(--ft);font-family:inherit}
.dlgbody{padding:16px 18px 22px;overflow-x:auto}
.v2sec{margin:0 0 26px;scroll-margin-top:70px;border-radius:8px}
:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
@media (max-width:820px){.v2why,.v2row .v2sub{display:none}
.v2main{padding:18px 12px 70px}.v2ans .shp-count b{font-size:38px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def page(active: str = "decide", **kw) -> str:
    """The whole new UI: Level 1 nav, four Level 2 boards, and the frame the
    Level 3 readouts load into.

    A BOARD PAGE IS LIGHT, so all four ship at once and switching is instant.
    A readout arrives from /vx2/read/<tab> when you enter it - one screen at
    a time, nothing pre-rendered into hidden panes. That is the difference
    between this and the 81,742-element page it replaces.
    """
    import json as _json
    import content_engine_vx2_seo as _SEOX
    import content_engine_vx2_ads as _ADSX
    active = active if any(b[0] == active for b in BOARDS) else "decide"
    counts = {bid: sum(1 for m in MANIFEST if m["board"] == bid)
              for bid, *_ in BOARDS}

    nav = ["<div class='v2nav'><span class='v2brand'>Anthropos</span>"]
    for bid, label, _q, _s in BOARDS:
        on = "on" if bid == active else ""
        nav.append(f"<button id='v2b-{bid}' class='{on}' "
                   f"onclick=\"return vx2go('{bid}')\">{e(label)}"
                   f"<span class='v2n'>{counts[bid]}</span></button>")
    nav.append("<a class='v2back' href='/'>the old dashboard &rsaquo;</a></div>")

    pages = []
    for bid, label, q, _s in BOARDS:
        style = "" if bid == active else "display:none"
        pages.append(f"<div id='vx2-{bid}' class='v2page' style='{style}'>"
                     + board_page(bid, label, q, kw) + "</div>")
    pages.append("<div id='vx2read' class='v2page' style='display:none'></div>")

    # every action button the boards produced, defined ONCE in the dashboard
    # module and reused here. Not copied: copied handlers drift, and a drifted
    # handler is a button that looks live and is not.
    #
    # Deliberately UNGUARDED. A try/except here would have to invent a stand-in
    # act(), and a stand-in act() is the exact drift this design forbids. If
    # this import fails the old dashboard is down too, and that outage should
    # be loud rather than dressed up as a working page.
    import content_engine_dashboard as _D
    shared = _D.dashboard_script({})

    # seopages is the one VX2-only screen: reachable, routable, but not a
    # manifest row, because the manifest mirrors the founder's 127 exactly.
    tabmap = dict(wiring(), seopages="market")
    js = ("<script>"
          "window.VX2TAB=" + _json.dumps(tabmap) + ";"
          "window.VX2SEC=" + _json.dumps(section_wiring()) + ";"
          "window.VX2CUR='" + active + "';"
          # LEVEL 1 <-> 2: show a board, hide the readout
          "function vx2go(b){"
          "var r=document.getElementById('vx2read');if(r)r.style.display='none';"
          "document.querySelectorAll('.v2page').forEach(function(p){"
          "if(p.id!=='vx2read')p.style.display=(p.id==='vx2-'+b)?'':'none';});"
          "document.querySelectorAll('.v2nav button').forEach(function(x){"
          "x.classList.remove('on');});"
          "var nb=document.getElementById('v2b-'+b);if(nb)nb.classList.add('on');"
          "window.VX2CUR=b;"
          "try{history.replaceState(null,'','#'+b);}catch(e){}"
          "window.scrollTo(0,0);return false;}"
          # LEVEL 3: fetch one readout, show it as its own screen
          "async function vx2read(tab){"
          "var r=document.getElementById('vx2read');if(!r)return false;"
          "var b=window.VX2TAB[tab];"
          "document.querySelectorAll('.v2page').forEach(function(p){"
          "p.style.display='none';});"
          "r.style.display='';"
          "r.innerHTML=\"<p class='v2empty'>Reading&hellip;</p>\";"
          "document.querySelectorAll('.v2nav button').forEach(function(x){"
          "x.classList.remove('on');});"
          "var nb=document.getElementById('v2b-'+b);if(nb)nb.classList.add('on');"
          "try{var resp=await fetch('/vx2/read/'+tab);"
          "r.innerHTML=await resp.text();}"
          "catch(err){r.innerHTML=\"<p class='v2empty'>Could not reach the "
          "engine for this readout. Nothing changed.</p>\";}"
          "try{history.replaceState(null,'','#'+tab);}catch(e){}"
          "window.scrollTo(0,0);return false;}"
          # LEVEL 4: the record, built from the line that was tapped
          "function vx2rec(el,ev){"
          "if(ev&&ev.target&&ev.target.closest&&ev.target.closest('.v2act'))return;"
          "var w=document.getElementById('dlgwrap');"
          "var bd=document.getElementById('dlgbody');"
          "var t=document.getElementById('dlgtitle');if(!w||!bd)return;"
          "var d=el.dataset;if(t)t.textContent=d.nm||'This measurement';"
          "var col={bad:'var(--bad)',warn:'var(--warnc)',ok:'var(--okc)',"
          "quiet:'var(--ft)'}[d.state]||'var(--ft)';"
          "var acts=el.querySelector('.v2act');"
          "var h=\"<dl class='rec'>\";"
          "h+=\"<p class='recval' style='color:\"+col+\"'></p>\";"
          "h+=\"<dt>The reading</dt><dd class='r-why'></dd>\";"
          "h+=\"<dt>Where it comes from</dt><dd class='r-src'></dd>\";"
          "h+=\"<dt>What kind of number</dt><dd class='r-kind'></dd>\";"
          "h+=\"</dl><div class='recacts'></div>\";"
          "bd.innerHTML=h;"
          "bd.querySelector('.recval').textContent="
          "(d.val||'--')+(d.sub?(' '+d.sub):'');"
          "bd.querySelector('.r-why').textContent="
          "d.why||'No written reading on this measurement.';"
          "bd.querySelector('.r-src').textContent="
          "d.src||'This measurement does not name its source.';"
          "bd.querySelector('.r-kind').textContent="
          "(d.kind?d.kind+'. ':'')+(d.kmean||'');"
          "if(acts)bd.querySelector('.recacts').innerHTML=acts.innerHTML;"
          "w.classList.add('on');document.body.style.overflow='hidden';}"
          # THE THREE OVERRIDES. nav/seoTab/sysTab move around the OLD
          # dashboard's sections, which do not exist here. Redefining them
          # after the shared script means every existing call site lands on
          # the right VX2 screen without a single card being edited.
          "function nav(id){id=String(id||'');"
          "if(window.VX2TAB[id]!==undefined)return vx2read(id);"
          "var s=window.VX2SEC[id];if(s)return vx2read(s[1]);"
          "if(document.getElementById('vx2-'+id))return vx2go(id);"
          "toast('This link points at \\''+id+'\\', which has no place in the "
          "new layout yet. Nothing was changed.');return false;}"
          "function seoTab(t){return nav(t);}"
          "function sysTab(t){return nav(t);}"
          # the URL is the state: #decide is a board, #seotech is a readout
          "function vx2route(){var h=(location.hash||'').replace('#','');"
          "if(!h)return;"
          "if(document.getElementById('vx2-'+h))vx2go(h);"
          "else if(window.VX2TAB[h]!==undefined)vx2read(h);}"
          "window.addEventListener('load',vx2route);"
          "window.addEventListener('hashchange',vx2route);"
          "</script>")

    dlg = ("<div id='dlgwrap' onclick='if(event.target===this)closeDetails()' "
           "role='dialog' aria-modal='true' aria-labelledby='dlgtitle'>"
           "<div class='dlg'><div class='dlghead'><h3 id='dlgtitle'>Details"
           "</h3><button class='dlgx' id='dlgx' onclick='closeDetails()' "
           "aria-label='Close details'>&#10005;</button></div>"
           "<div class='dlgbody' id='dlgbody'></div></div></div>")

    # _SEOX.JS and _ADSX.JS MUST ship with the page. The readouts arrive by
    # fetch, and fetched HTML cannot bring its own <script> to life - so if
    # these are not on the shell, every s3run/s2fix/a3plat button in every
    # SEO and Ads screen is silently undefined. That exact omission shipped
    # once: the endpoint answered 200 while the button did nothing.
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Anthropos VX2</title><style>" + CSS + shapes.CSS
            + _SEOX.CSS + _ADSX.CSS + "</style></head>"
            "<body class='v2wrap'>" + "".join(nav)
            + "<div class='v2main'>" + "".join(pages) + "</div>"
            + dlg + shared + js + _SEOX.JS + _ADSX.JS + "</body></html>")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    m = MANIFEST
    print(f"manifest: {len(m)} subsections")
    import collections
    for bid, label, _q, _s in BOARDS:
        subs = [x for x in m if x["board"] == bid]
        sh = collections.Counter(x["shape"] for x in subs)
        print(f"  {label:<8} {len(subs):>3}   "
              + "  ".join(f"{k} {v}" for k, v in sh.most_common()))
    assert len(m) == 127, f"expected 127 subsections, manifest has {len(m)}"
    noted = [x["label"] for x in m if not x["fn"]]
    assert all(x["note"] for x in m if not x["fn"]), \
        "a subsection without a renderer must carry a note saying why"
    print(f"\nall 127 present; {len(noted)} rendered elsewhere: {noted}")
    w = wiring()
    assert len(w) == 127, f"wiring covers {len(w)} of 127 tabs"
    html = page(active="decide")
    for need in ("v2nav", "vx2-decide", "function act(", "function nav(id)",
                 "dlgwrap", "VX2TAB", "vx2read", "vx2rec"):
        assert need in html, f"page is missing {need}"
    assert html.count("function nav(") == 2, "the nav override must come after"
    # LEVEL 2 IS A LIST, NOT A DUMP: no readout bodies on the first paint.
    # The stylesheet legitimately names the class; the MARKUP must not.
    assert "class='v2readbody'" not in html, "a board page leaked a readout inline"
    print(f"first paint {len(html)//1024} KB (all four boards, empty context)")
    r = readout_page("syscmd", {})
    for need in ("v2crumb", "v2readbody"):
        assert need in r, f"readout is missing {need}"
    print(f"one readout {len(r)//1024} KB")
