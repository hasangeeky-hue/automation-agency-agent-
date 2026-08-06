"""
content_engine_vx2.py
============================================================================
THE NEW UI. Four boards, 127 subsections, one renderer, parallel to the old.

WHY THIS EXISTS
  2,294 cards across 9 sections and 127 tabs. 88% of the cards could only be
  read. The browser built 81,742 elements on every load. The founder could not
  find the twelve percent that mattered, and said so: "i lost this is why i
  came to you".

THE GRAMMAR
  4 boards          DECIDE  MAKE  MARKET  RUN      the whole navigation
  4 screens         boards / a board / a readout / a record
  6 data shapes     SCORE RATIO COUNT TREND SPLIT TABLE  (+ STATE, PREVIEW)
  one rule          a measurement that fits no shape is a sentence, not a card

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
# render helpers - light, minimal, button-first
# ---------------------------------------------------------------------------
def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


_SEV = {"#FF6B93": ("bad", "#D2453C"), "#F5B14C": ("warn", "#C07B12"),
        "#3FD98B": ("ok", "#1F7A4C")}


def _tone(accent):
    """Old palette accent -> new state. Anything else is quiet."""
    return _SEV.get(str(accent or "").upper(), ("quiet", "#9AA0A5"))


def _line(card) -> tuple:
    """One measurement as (weight, html). Problems weigh less so they sort up."""
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
    return (weight,
            f"<div class='v2row{cls}'>"
            f"<span class='v2dot' style='background:{col}'></span>"
            f"<span class='v2nm'>{e(title)}</span>"
            f"<span class='v2why'>{e(insight)[:110]}</span>"
            f"<span class='v2val' style='color:{col}'>{e(big)}</span>"
            f"<span class='v2sub'>{e(sub)[:22]}</span>"
            + (f"<span class='v2act'>{links}</span>" if links else "")
            + f"</div>")


def readout(entry, ctx) -> str:
    """LEVEL 3 - a subsection. Every measurement as one line, problems first."""
    cards = capture(entry["fn"], ctx) if entry.get("fn") else []
    lines = sorted((_line(c) for c in cards), key=lambda t: t[0])
    n_bad = sum(1 for c in cards
                if _tone(c[6] if len(c) > 6 else "")[0] in ("bad", "warn"))
    head = (f"<div class='v2head'><div><h3>{e(entry['label'])}</h3>"
            f"<p class='v2sub2'>{len(cards)} measurements"
            + (f" &middot; <b style='color:#D2453C'>{n_bad} want attention</b>"
               if n_bad else " &middot; nothing wants attention")
            + f"</p></div>"
            f"<span class='v2shape'>{entry['shape']}</span></div>")
    if not lines:
        why = entry.get("note") or ("Nothing measured here yet. This "
                                    "subsection has no data on your box, "
                                    "which is not the same as a zero.")
        return head + f"<p class='v2empty'>{e(why)}</p>"
    return head + "".join(h for _w, h in lines)


def board_page(bid, label, question, ctxs, manifest) -> str:
    """LEVEL 2 - a board: its subsections, problems surfaced first."""
    subs = [m for m in manifest if m["board"] == bid]
    blocks = []
    for m in subs:
        ctx = ctxs.get(m["module"]) or {}
        blocks.append(f"<section class='v2sec' id='vx2-{e(m['tab'])}'>"
                      + readout(m, ctx) + "</section>")
    return (f"<div class='v2board'><p class='v2q'>{e(question)}</p>"
            f"<h2 class='v2h2'>{e(label)}</h2>"
            f"<p class='v2meta'>{len(subs)} subsections</p>"
            + "".join(blocks) + "</div>")


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
# derived from BOARDS below, so there is exactly one place that says which
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
.v2q{font-size:14px;color:var(--dm);margin:0 0 2px}
.v2h2{font-size:30px;font-weight:800;letter-spacing:-.03em;margin:0 0 3px;
text-wrap:balance}
.v2meta{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--ft);
margin:0 0 24px;letter-spacing:.08em;text-transform:uppercase}
.v2sec{margin:0 0 26px;scroll-margin-top:70px;border-radius:8px}
.v2sec.v2hit{outline:2px solid var(--ac);outline-offset:6px}
.v2head{display:flex;align-items:flex-end;gap:14px;padding:0 0 8px;
border-bottom:1px solid var(--ln);margin-bottom:2px}
.v2head h3{margin:0;font-size:17px;font-weight:700;letter-spacing:-.015em}
.v2sub2{margin:2px 0 0;font-size:12px;color:var(--ft)}
.v2shape{margin-left:auto;font-family:ui-monospace,Menlo,monospace;font-size:9.5px;
font-weight:700;letter-spacing:.1em;color:var(--ft);border:1px solid var(--ln);
border-radius:4px;padding:2px 7px;white-space:nowrap}
.v2row{display:flex;gap:12px;align-items:center;padding:7px 10px;
border-bottom:1px solid var(--ln);font-size:13.5px;border-radius:5px}
.v2row:hover{background:var(--hov)}
.v2dot{width:6px;height:6px;border-radius:50%;flex:none}
.v2nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.v2why{flex:1.3;min-width:0;color:var(--ft);font-size:12px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.v2val{font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;
font-size:14px;font-weight:700;white-space:nowrap}
.v2sub{color:var(--ft);font-size:11px;white-space:nowrap;
font-family:ui-monospace,Menlo,monospace}
.v2act{display:flex;gap:6px;flex:none}
.v2act .cta,.v2act .cbtn,.v2act button{font-size:11.5px;padding:4px 10px;
border-radius:6px;border:1px solid var(--ln);background:var(--card);
color:var(--tx);cursor:pointer;font-family:inherit;white-space:nowrap}
.v2act button:hover{border-color:var(--ac);color:var(--ac)}
.v2act button[disabled]{opacity:.55;cursor:default}
.v2act .empty,.v2act .mut,.v2act .dim{color:var(--ft);font-size:11px}
.v2-bad{background:var(--badbg)}
.v2-warn{background:var(--warnbg)}
.v2empty{font-size:13px;color:var(--ft);padding:12px 10px;margin:0;line-height:1.55}
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
:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
@media (max-width:820px){.v2why,.v2row .v2sub{display:none}
.v2main{padding:18px 12px 70px}.v2h2{font-size:24px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def ctxs_from(kw: dict) -> dict:
    """The dashboard's kwargs -> module name -> context. Same dict object the
    old boards get, so the two UIs cannot read different numbers."""
    return {m: (kw.get(f"{m}_ctx") or {}) for m in _MODULES}


def board_html(bid: str, kw: dict) -> str:
    """One board, rendered on its own. This is what /vx2/board/<id> returns."""
    row = next((b for b in BOARDS if b[0] == bid), None)
    if not row:
        return "<p class='v2empty'>No board by that name.</p>"
    _b, label, q, _s = row
    return board_page(bid, label, q, ctxs_from(kw), MANIFEST)


def page(active: str = "decide", **kw) -> str:
    """The whole new UI.

    ONE BOARD IS SENT, NOT FOUR. The old dashboard shipped 2,236 cards and
    81,742 elements on every load, and the founder's verdict on that was
    "this design gonna make the engine slow". Four boards rendered together
    would have repeated the mistake in a new font. The other three arrive from
    /vx2/board/<id> the first time you open them, and stay in the page after
    that, so the second visit is instant and the first is small.
    """
    import json as _json
    active = active if any(b[0] == active for b in BOARDS) else "decide"
    counts = {bid: sum(1 for m in MANIFEST if m["board"] == bid)
              for bid, *_ in BOARDS}

    nav = ["<div class='v2nav'><span class='v2brand'>Anthropos</span>"]
    for bid, label, _q, _s in BOARDS:
        on = "on" if bid == active else ""
        nav.append(f"<button id='v2b-{bid}' class='{on}' "
                   f"onclick=\"vx2go('{bid}')\">{e(label)}"
                   f"<span class='v2n'>{counts[bid]}</span></button>")
    nav.append("<a class='v2back' href='/'>the old dashboard &rsaquo;</a></div>")

    pages = []
    for bid, label, q, _s in BOARDS:
        if bid == active:
            inner, loaded = board_html(bid, kw), "1"
        else:
            inner, loaded = (f"<div class='v2board'><p class='v2q'>{e(q)}</p>"
                             f"<h2 class='v2h2'>{e(label)}</h2>"
                             f"<p class='v2meta'>{counts[bid]} subsections"
                             f"</p><p class='v2empty'>Reading your engine"
                             f"&hellip;</p></div>"), "0"
        style = "" if bid == active else "display:none"
        pages.append(f"<div id='vx2-{bid}' class='v2page' data-loaded='{loaded}'"
                     f" style='{style}'>{inner}</div>")

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

    js = ("<script>"
          "window.VX2TAB=" + _json.dumps(wiring()) + ";"
          "window.VX2SEC=" + _json.dumps(section_wiring()) + ";"
          "async function vx2load(b){"
          "var p=document.getElementById('vx2-'+b);"
          "if(!p||p.getAttribute('data-loaded')==='1')return;"
          "try{var r=await fetch('/vx2/board/'+b);"
          "p.innerHTML=await r.text();p.setAttribute('data-loaded','1');}"
          "catch(err){p.innerHTML=\"<p class='v2empty'>Could not reach the "
          "engine for this board. Nothing changed.</p>\";}}"
          "async function vx2go(b,tab){"
          "document.querySelectorAll('.v2page').forEach(function(p){"
          "p.style.display=(p.id==='vx2-'+b)?'':'none';});"
          "document.querySelectorAll('.v2nav button').forEach(function(x){"
          "x.classList.remove('on');});"
          "var nb=document.getElementById('v2b-'+b);if(nb)nb.classList.add('on');"
          "await vx2load(b);"
          "try{history.replaceState(null,'','#'+(tab||b));}catch(e){}"
          "if(tab){var t=document.getElementById('vx2-'+tab);"
          "if(t){t.scrollIntoView({block:'start'});"
          "t.classList.add('v2hit');setTimeout(function(){"
          "t.classList.remove('v2hit');},1600);return false;}}"
          "window.scrollTo(0,0);return false;}"
          # THE THREE OVERRIDES. nav/seoTab/sysTab move around the OLD
          # dashboard's sections, which do not exist here. Redefining them
          # after the shared script means all 151 existing call sites land on
          # the right VX2 subsection without a single card being edited.
          "function nav(id){id=String(id||'');"
          "if(window.VX2TAB[id]!==undefined)return vx2go(window.VX2TAB[id],id);"
          "var s=window.VX2SEC[id];if(s)return vx2go(s[0],s[1]);"
          "toast('This link points at \\''+id+'\\', which has no place in the "
          "new layout yet. Nothing was changed.');return false;}"
          "function seoTab(t){return nav(t);}"
          "function sysTab(t){return nav(t);}"
          "window.addEventListener('load',function(){"
          "var h=(location.hash||'').replace('#','');if(!h)return;"
          "if(window.VX2TAB[h]!==undefined)vx2go(window.VX2TAB[h],h);"
          "else if(document.getElementById('vx2-'+h))vx2go(h);});"
          "</script>")

    dlg = ("<div id='dlgwrap' onclick='if(event.target===this)closeDetails()' "
           "role='dialog' aria-modal='true' aria-labelledby='dlgtitle'>"
           "<div class='dlg'><div class='dlghead'><h3 id='dlgtitle'>Details"
           "</h3><button class='dlgx' id='dlgx' onclick='closeDetails()' "
           "aria-label='Close details'>&#10005;</button></div>"
           "<div class='dlgbody' id='dlgbody'></div></div></div>")

    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Anthropos VX2</title><style>" + CSS + "</style></head>"
            "<body class='v2wrap'>" + "".join(nav)
            + "<div class='v2main'>" + "".join(pages) + "</div>"
            + dlg + shared + js + "</body></html>")


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
                 "dlgwrap", "VX2TAB"):
        assert need in html, f"page is missing {need}"
    assert html.count("function nav(") == 2, "the nav override must come after"
    print(f"first paint {len(html)//1024} KB (one board of four, empty context)")
