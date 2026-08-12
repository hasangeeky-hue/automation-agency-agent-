"""
content_engine_media_center.py
============================================================================
THE MEDIA BUYING OS SECTION. This replaces the 16-tab media UI completely.

DECISION FIRST. The founder's order and the spec's section 32: the first
screen answers "what needs me today", not "how many impressions were
there". Numbers come with denominators, absences render as absences, and
every button that could cost money routes through the order queue that
already holds the approval tiers.

WHAT THIS FILE IS ALLOWED TO DO: read the engines and draw HTML. It calls
content_engine_media_os / _plan / _perf / _creative for every fact, and
POSTS to /mediaos/* and /media/* for every action. It computes nothing of
its own, because a screen with its own arithmetic eventually disagrees
with the engine it fronts.

THE LIVE CONTROLS SURVIVE. The email OS rebuild once silently dropped the
outbox and the founder found out from the silence. So: the agent band with
its OFF/OBSERVE/PROPOSE ladder, the orders board with approve and execute,
the Google pulls, the GA4/GSC tracking boards and the media agent's draft
flow all keep their existing handlers and endpoints. Same names, same
wires, new rooms.

Every element id is prefixed mc- because the dashboard renders every
section at once and a bare id collides with someone else's.
============================================================================
"""

from __future__ import annotations

import html
import json
import logging

import content_engine_media_creative as MC
import content_engine_media_os as M
import content_engine_media_perf as MF
import content_engine_media_plan as MP
from content_engine_os_core import _D, _L

log = logging.getLogger("content_engine.media_center")


def e(v) -> str:
    return html.escape(str("" if v is None else v), quote=True)


def _n(v, dash="--"):
    """A number or an honest dash. Never a fake zero."""
    if v is None or v == "":
        return dash
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{v:,}" if isinstance(v, int) else e(v)


def _money(v, cur="EUR"):
    return "--" if v in (None, "") else f"{float(v):,.2f} {e(cur)}"


#: The screens. One tuple, used by the nav, the panels and the gates, so
#: a tab cannot exist without a panel or a panel without a tab.
SCREENS = (
    ("cmd", "🎯", "Command Centre", "What needs you today"),
    ("camps", "📋", "Campaigns", "Everything, with its real state"),
    ("wiz", "🧭", "New Campaign", "The eight steps"),
    ("launch", "🚀", "Launch Centre", "Checked before it costs anything"),
    ("adman", "🗂️", "Ad Manager", "Every platform's own room"),
    ("plan", "📐", "Planner", "Budget, allocation, what-if"),
    ("creat", "🎨", "Creatives", "The library and what it learned"),
    ("aud", "👥", "Audiences", "Who, and what each platform drops"),
    ("alx", "📈", "Analytics", "The workbench: query, drill, decide"),
    ("intel", "🔍", "Search & Bidding", "Terms, keywords, pace, waste"),
    ("anom", "⚠️", "Anomalies & Verdicts", "What broke its own baseline"),
    ("cross", "🔗", "Cross-Channel", "Paid and organic in one picture"),
    ("comp", "🥊", "Competition & Research", "Who else is in the auction"),
    ("plat", "🔌", "Platforms & Tracking", "Connections, pulls, tags"),
)


# ---------------------------------------------------------------------------
# SMALL KIT. One <table> element per table; the row-per-grid mistake made
# every row size its own columns and nothing lined up.
# ---------------------------------------------------------------------------
def table(heads, rows, empty="nothing here yet") -> str:
    if not rows:
        return f"<p class='mc-empty'>{e(empty)}</p>"
    h = "".join(f"<th>{e(x)}</th>" for x in heads)
    b = "".join("<tr>" + "".join(
        f"<td>{c if isinstance(c, str) and c.startswith('<') else e(c)}</td>"
        for c in row) + "</tr>" for row in rows)
    return ("<div class='mc-scroll'><table class='mc-tbl'>"
            f"<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>")


def card(title, body, sub="") -> str:
    return ("<div class='mc-card'><p class='mc-ct'>" + e(title) + "</p>"
            + (f"<p class='mc-cs'>{e(sub)}</p>" if sub else "")
            + body + "</div>")


def kpi(label, value, of="") -> str:
    return ("<div class='mc-kpi'><b>" + value + "</b>"
            f"<span>{e(label)}</span>"
            + (f"<i>{e(of)}</i>" if of else "") + "</div>")


def chart(series, *, h=110, w=640, color="#2563EB", title="",
          source="platform daily rollups") -> str:
    """The kit's line chart, in media's frame.

    The local SVG this replaces filtered None out of the series, which
    quietly bridged measurement gaps; the kit breaks the polyline at a
    gap and says so in the footer. Refusing below two real points is
    kept here because the callers rely on the wording."""
    import content_engine_ui_kit as UK
    pts = [(str(b), float(v)) for b, v in series
           if v is not None and str(v) != ""]
    if len(pts) < 2:
        return (f"<p class='mc-empty'>{e(title)}: not enough measured "
                f"points to draw a line ({len(pts)} of 2). A chart appears "
                f"when there are at least two days of data.</p>")
    vals = [v for _b, v in pts]
    lo, hi = min(vals), max(vals)
    return (f"<div class='mc-chart'>"
            + UK.line([(float(v) if v is not None and str(v) != "" else None)
                       for _b, v in series], title=title, source=source)
            + f"<span class='mc-chmeta'>{e(pts[0][0])} to {e(pts[-1][0])} "
            f"&middot; low {lo:,.0f} &middot; high {hi:,.0f} &middot; "
            f"latest {vals[-1]:,.0f}</span></div>")

def chart_bars(rows, *, title="", color="#4C8DFF", unit="") -> str:
    """Horizontal bars, scaled to the biggest value. Same refusal rule."""
    rows = [(str(k), float(v)) for k, v in rows if v is not None]
    if not rows:
        return (f"<p class='mc-empty'>{e(title)}: nothing measured to "
                f"draw.</p>")
    top = max(v for _k, v in rows) or 1.0
    bars = "".join(
        f"<div class='mc-hbar'><span>{e(k)[:34]}</span>"
        f"<span class='mc-hbtrack'><span style='width:"
        f"{max(2, int(v / top * 100))}%;background:{color}'></span></span>"
        f"<i>{v:,.0f}{e(unit)}</i></div>" for k, v in rows)
    return (f"<div class='mc-chart'><span class='mc-chtitle'>{e(title)}"
            f"</span>{bars}</div>")


def chart_funnel(stages, *, title="Funnel") -> str:
    """The funnel as narrowing bars: stage, count, and the drop between
    stages named, because the drop IS the finding."""
    st = [(str(k), float(v)) for k, v in stages if v]
    if len(st) < 2:
        return ("<p class='mc-empty'>the funnel needs at least two real "
                "stages; nothing is invented to fill it</p>")
    top = st[0][1] or 1.0
    out = []
    for i, (k, v) in enumerate(st):
        drop = ""
        if i:
            prev = st[i - 1][1]
            pct = v / prev * 100 if prev else 0
            drop = f"{pct:.1f}% of {st[i - 1][0].lower()}"
        out.append(
            f"<div class='mc-hbar'><span>{e(k)}</span>"
            f"<span class='mc-hbtrack'><span style='width:"
            f"{max(2, int(v / top * 100))}%'></span></span>"
            f"<i>{v:,.0f}</i><p>{e(drop)}</p></div>")
    return (f"<div class='mc-chart'><span class='mc-chtitle'>{e(title)}"
            f"</span>" + "".join(out) + "</div>")


def _off(d, what) -> str:
    """The honest banner for an unconnected pull."""
    reason = _D(d).get("reason") or (f"no {what} on record yet; press "
                                     f"'Pull platforms now'")
    return f"<p class='mc-empty'>{e(reason)}</p>"


def _band(ctx) -> str:
    """The agent band. Same switch, same handlers, same honesty."""
    level = str(ctx.get("media_auto_level") or "unknown").lower()
    verd = ctx.get("media_verdicts") or {}
    n_v = len(verd.get("verdicts") or ())
    orders = [o for o in (ctx.get("media_orders") or ())
              if o.get("status") == "open"]
    blind = verd.get("blind") or []
    word = {"off": "OFF - pulls run, the agent stays silent",
            "observe": "OBSERVE 24/7 - judging, writing verdicts, "
                       "drafting nothing",
            "propose": "PROPOSE - verdicts become drafts in the queue",
            }.get(level, "switch state could not be read")

    def _lvl(lv, lab):
        on = " s3on" if level == lv else ""
        return (f"<button class='s3lvl{on}' "
                f"onclick=\"mediaAutoSet('{lv}',this)\">{lab}</button>")

    return ("<div class='s3band'>"
            "<div class='s3who'><p class='s3k'>Your media buying agent</p>"
            f"<p class='s3state'><b>{e(word)}</b></p>"
            f"<p class='s3sub'>{n_v} verdict(s) standing &middot; "
            f"{len(orders)} draft(s) waiting for your approval"
            + (f" &middot; blind on {len(blind)} rule(s)" if blind else "")
            + ". Nothing spends without your click; there is no auto-spend "
              "level at all.</p></div>"
            "<div class='s3cmds'>"
            "<button class='cta s3go' onclick=\"act('/ads/pull')\">"
            "Pull platforms now</button>"
            "<button class='cta' onclick=\"act('/ads/interlock')\">"
            "Rebuild interlock</button>"
            "<button class='cta a2draft' onclick='mediaOptimize(this)'>"
            "Run the rules now</button>"
            "<button class='cta' onclick='mcPost(\"/mediaos/propose\",{},"
            "this)'>Judge baselines now</button>"
            "</div>"
            "<div class='s3ladder' role='group' aria-label='media agent level'>"
            + _lvl("off", "OFF") + _lvl("observe", "OBSERVE")
            + _lvl("propose", "PROPOSE") + "</div></div>")


def _orders_board(ctx, limit=12) -> str:
    import content_engine_media_orders as MO
    orders = list(ctx.get("media_orders") or ())
    if not orders:
        return ("<p class='mc-empty'>No orders in the queue. The agent "
                "writes one when a rule fires with full evidence; you "
                "approve it here before anything runs.</p>")
    rows = []
    for o in [x for x in orders if x.get("status") == "open"][:limit]:
        ev = o.get("evidence") or {}
        conf = o.get("confidence")
        rows.append((
            e(o.get("code")), e(MO.lifecycle_of(o)), e(o.get("say"))[:100],
            e(f"{ev.get('metric', '')} vs {ev.get('threshold', '')}"),
            (f"{conf:.0%}" if isinstance(conf, (int, float))
             else "not stated"),
            e(o.get("risk") or "-"),
            f"<button class='mc-btn' onclick=\"mediaApprove('{e(o.get('id'))}'"
            f",this)\">Approve</button> "
            f"<button class='mc-btn mc-go' onclick=\"mediaRun('{e(o.get('id'))}'"
            f",this)\">Execute</button>"))
    decided = [x for x in orders if x.get("status") != "open"]
    lc = {}
    for x in decided:
        w = MO.lifecycle_of(x)
        lc[w] = lc.get(w, 0) + 1
    return (table(("code", "lifecycle", "what", "evidence", "confidence",
                   "risk", "decision"), rows, "no open orders")
            + "<p class='mc-note'>"
            + (", ".join(f"{n} {w}" for w, n in sorted(lc.items()))
               if lc else "nothing decided yet")
            + ". <button class='mc-btn' onclick=\"mcPost('/mediaos/verify',"
              "{},this)\">Verify executed orders against the last platform "
              "read</button></p>")


# ---------------------------------------------------------------------------
# THE SCREENS
# ---------------------------------------------------------------------------
#: Which glyph an action wears in TODAY'S ACTIONS. Spec section 32:
#: scale up, reduce, tracking warning, create creative.
GLYPH = {"budget_shift": "↑", "resume_campaign": "↑", "budget_allocate": "↑",
         "pause_campaign": "↓", "bid_change": "↓", "audience_exclude": "↓",
         "negative_keyword": "↓",
         "utm_fix": "⚠", "tag_missing": "⚠", "tag_paused": "⚠",
         "pixel_missing": "⚠", "event_silent": "⚠", "landing_fix": "⚠",
         "creative_rotate": "＋", "launch_campaign": "＋"}


def _action_card(o) -> str:
    """One of TODAY'S ACTIONS: glyph, sentence, confidence, decision."""
    ev = o.get("evidence") or {}
    conf = o.get("confidence")
    g = GLYPH.get(o.get("code"), "•")
    cls = {"↑": "up", "↓": "down", "⚠": "warn", "＋": "make"}.get(g, "flat")
    return (
        f"<div class='mc-act mc-act-{cls}'>"
        f"<span class='mc-glyph'>{g}</span>"
        f"<div class='mc-actbody'>"
        f"<b>{e(o.get('say'))[:120]}</b>"
        f"<span>{e(ev.get('metric', ''))} against "
        f"{e(ev.get('threshold', ''))} over {e(ev.get('window', ''))}"
        f"</span>"
        f"<span>Confidence "
        + (f"{conf:.0%} ({e(o.get('confidence_basis', ''))})"
           if isinstance(conf, (int, float)) else "not stated")
        + f" &middot; risk {e(o.get('risk') or '-')}"
          f" &middot; {e(o.get('expected_effect') or '')}</span></div>"
        f"<div class='mc-actbtns'>"
        f"<button class='mc-btn' onclick=\"mediaApprove('{e(o.get('id'))}'"
        f",this)\">Approve</button>"
        f"<button class='mc-btn mc-go' onclick=\"mediaRun('{e(o.get('id'))}'"
        f",this)\">Execute</button></div></div>")


def s_cmd(r, ctx) -> str:
    try:
        sm = MF.summary(r)
    except Exception as ex:
        return card("Command Centre",
                    f"<p class='mc-empty'>the summary could not be computed: "
                    f"{e(type(ex).__name__)}</p>")
    cpa, roas = sm.get("cpa") or {}, sm.get("roas") or {}
    biz = {}
    try:
        import content_engine_api as A
        biz = MF.business(r, A.get_store())
    except Exception:
        biz = {}
    # THE BIG FIGURES, spec section 32: revenue, spend, blended ROAS,
    # blended CPA, conversions. Denominator under each, absence as absence.
    wdays = ctx.get("window_days")
    wdays = wdays if wdays in (7, 30, 90) else 30
    ro30 = {}
    try:
        ro30 = MF.rollup(r, days=wdays)["totals"]
    except Exception:
        pass

    def big(label, v, sub=""):
        return ("<div class='mc-big'><span class='mc-bigk'>" + e(label)
                + "</span><b>" + (_n(v) if not isinstance(v, str) else e(v))
                + "</b><span class='mc-bigs'>" + e(sub) + "</span></div>")

    figures = ("<div class='mc-bigs30'>MEDIA COMMAND CENTER &middot; last "
               + str(wdays) + " days</div><div class='mc-bigrow'>"
               + big("Revenue", ro30.get("conversion_value"),
                     "tracked conversion value")
               + big("Spend", sm.get("spend"), "")
               + big("Blended ROAS", roas.get("value"),
                     roas.get("of") or "nothing to measure yet")
               + big("Blended CPA", cpa.get("value"),
                     cpa.get("of") or "nothing to measure yet")
               + big("Conversions", sm.get("conversions"), "")
               + (big("Gross profit", biz.get("gross_profit"),
                      f"at {biz.get('margin_pct')}% margin")
                  if biz.get("ok") else
                  big("Gross profit", None, "set your margin in unit "
                                            "economics"))
               + "</div>")
    # The spend and conversion trend, drawn, not tabled.
    daily = {}
    try:
        for row in MF.rollup(r, days=wdays)["rows"]:
            d = daily.setdefault(row["bucket"], {"spend": 0.0, "conv": 0.0})
            d["spend"] += float(row["spend"] or 0)
            d["conv"] += float(row["conversions"] or 0)
    except Exception:
        pass
    days_sorted = sorted(daily)
    figures += ("<div class='mc-chrow'>"
                + chart([(d, daily[d]["spend"]) for d in days_sorted],
                        title="Spend per day, 30d")
                + chart([(d, daily[d]["conv"]) for d in days_sorted],
                        title="Conversions per day, 30d", color="#3FD98B")
                + "</div>")
    # AI STATUS, spec section 32.
    camps = r.all("media_campaigns")
    monitored = sum(1 for c in camps
                    if c.get("state") in ("ACTIVE", "PAUSED", "SCHEDULED"))
    act = sm.get("needs_action") or []
    watch = sm.get("watching") or []
    nj = sm.get("not_judged") or []
    orders_open = [o for o in (ctx.get("media_orders") or ())
                   if o.get("status") == "open"]
    scale_ops = sum(1 for o in orders_open
                    if GLYPH.get(o.get("code")) == "↑")
    track = sum(1 for o in orders_open if GLYPH.get(o.get("code")) == "⚠")
    status = ("<div class='mc-statrow'>"
              + "".join(f"<div class='mc-stat'><b>{n}</b><span>{e(lab)}"
                        f"</span></div>" for n, lab in (
                            (monitored, "campaigns monitored"),
                            (len(act), "require attention"),
                            (scale_ops, "scaling opportunities"),
                            (track, "tracking anomalies"),
                            (len(watch), "on watch"),
                            (len(nj), "too new to judge")))
              + "</div>")
    # TODAY'S ACTIONS, spec section 32: cards with glyphs, not a table.
    todays = ("".join(_action_card(o) for o in orders_open[:8])
              or "<p class='mc-empty'>Nothing needs a decision right now. "
                 "The agent writes an action card here when a rule fires "
                 "with full evidence; quiet is a finding.</p>")
    if act and not orders_open:
        todays += ("<p class='mc-note'>anomalies stand without verdicts; "
                   "press 'Judge baselines now' above to turn them into "
                   "action cards</p>")
    disputed = sm.get("most_disputed") or []
    disp = table(("campaign", "spread", "why"),
                 [(d["name"], d["spread"], d["why"][:110])
                  for d in disputed],
                 "no conversion has an attributable touch yet")
    losers = [x for x in (biz.get("rows") or []) if x.get("flag")]
    biznote = (f"<p class='mc-note'>{e(biz.get('message', ''))}</p>"
               + (table(("campaign", "spend", "revenue", "gross profit",
                         "ROAS"),
                        [(x["name"], _n(x["spend"]), _n(x["revenue"]),
                          _n(x["gross_profit"]), _n(x["roas"]))
                         for x in losers[:5]])
                  if losers else "")
               if biz.get("ok") else
               "<p class='mc-empty'>" + e(biz.get("message")
               or "profit needs your margin") + "</p>"
               "<button class='mc-btn' onclick='openEcon()'>Set unit "
               "economics</button>")
    return (figures
            + card("AI STATUS", status)
            + _band(ctx)
            + card("TODAY'S ACTIONS", todays,
                   "each card carries its evidence, confidence and risk; "
                   "nothing runs without your click")
            + card("What the business keeps", biznote,
                   "ROAS is a platform number; profit is yours")
            + card("Where the attribution models disagree most", disp,
                   "any single number you quote for these is a choice"))


def s_camps(r, ctx) -> str:
    camps = sorted(r.all("media_campaigns"),
                   key=lambda c: str(c.get("updated_at") or ""), reverse=True)
    rows = []
    for c in camps[:60]:
        w = MP.wizard_state(r, c.get("id"))
        rows.append((
            f"<a class='mc-link' onclick=\"mcDetail('{e(c.get('id'))}')\">"
            f"{e(c.get('name'))}</a>",
            e(c.get("provider") or "-"),
            e(c.get("objective")), e(c.get("state")),
            _money(c.get("budget_amount"), c.get("currency") or "EUR")
            + " " + e(str(c.get("budget_type") or "").lower()),
            f"{w['complete']}/{w['total']} steps",
            f"<button class='mc-btn' onclick=\"mcPost('/mediaos/validate',"
            f"{{campaign_id:'{e(c.get('id'))}'}},this)\">Validate</button> "
            f"<button class='mc-btn mc-go' onclick=\"mcTab('launch')\">"
            f"Pre-flight</button>"))
    body = (table(("campaign", "platform", "objective", "state", "budget",
                   "wizard", "actions"), rows,
                  "No campaigns in the canonical model yet. Start one under "
                  "New Campaign; a sync will also pull what already runs on "
                  "a connected platform.")
            + "<p class='mc-note'>click a campaign name for the deep "
              "view: trend, audiences, creatives, placements, diagnosis "
              "and execution history</p>"
            + "".join(_detail(r, c, ctx) for c in camps[:8]))
    st = [s for s in (ctx.get("sync_runs") or ())][:1]
    sync = ("<button class='mc-btn' onclick=\"mcPost('/mediaos/sync',{},this)\">"
            "Sync with the platforms now</button>"
            "<p class='mc-note'>The database saying ACTIVE while the platform "
            "says PAUSED is the lie sync exists to catch."
            + (f" Last run: {e(str(st[0].get('completed_at'))[:16])}"
               if st else " No sync has run yet.") + "</p>")
    adopted = sum(1 for c in camps
                  if _D(c.get("provider_config")).get("adopted"))
    adopt = ("<button class='mc-btn mc-go' "
             "onclick=\"mcPost('/mediaos/adopt',{},this)\">"
             "Adopt the old Google Ads data</button>"
             "<p class='mc-note'>Pulls the campaigns the OLD system already "
             "recorded into this model: names, states, budgets and their "
             "30-day totals. No key is touched and running it twice updates "
             "rather than duplicates."
             + (f" {adopted} campaign(s) here are adopted already."
                if adopted else " Nothing has been adopted yet.") + "</p>")
    return (card("Every campaign, with its real state", body)
            + card("Transform: bring the old system's data in", adopt)
            + card("Synchronisation", sync))


def _wpane(i, key, label, why, body, *, last=False) -> str:
    nav = ("<div class='mc-wnav'>"
           + (f"<button class='mc-btn' onclick='mcStep({i - 1})'>&larr; "
              f"Back</button>" if i > 0 else "")
           + (f"<button class='mc-btn mc-go' onclick='mcStep({i + 1})'>"
              f"Next &rarr;</button>" if not last else "")
           + "</div>")
    return (f"<div class='mc-wstep{' mc-on' if i == 0 else ''}' "
            f"id='mc-wstep-{i}'>"
            f"<p class='mc-wtitle'>STEP {i + 1} &middot; {e(label)}</p>"
            f"<p class='mc-cs'>{e(why)}</p>{body}{nav}</div>")


def s_wiz(r, ctx) -> str:
    """The 8-step wizard, ONE STEP AT A TIME. The spec's exact words:
    do not put the entire campaign configuration into one giant form."""
    drafts = [c for c in r.all("media_campaigns")
              if c.get("state") in ("DRAFT", "VALIDATION_FAILED")]
    drafts.sort(key=lambda c: str(c.get("updated_at") or ""), reverse=True)
    draft = drafts[0] if drafts else None
    w = MP.wizard_state(r, draft.get("id")) if draft else None
    rail = "".join(
        f"<button class='mc-dot{' mc-don' if w and w['steps'][i]['done'] else ''}' "
        f"onclick='mcStep({i})' title='{e(lab)}'>{i + 1}</button>"
        for i, (_k, lab, _why) in enumerate(MP.WIZARD_STEPS))
    header = ("<div class='mc-wrail'>" + rail + "</div>"
              + (f"<p class='mc-note'>Building: <b>{e(draft.get('name'))}"
                 f"</b> &middot; {w['complete']} of {w['total']} steps done. "
                 f"{e((w.get('next') or {}).get('why') or 'ready')}</p>"
                 if draft else
                 "<p class='mc-note'>No draft yet. Steps 1 to 3 create "
                 "one; everything is read from the record, so closing the "
                 "tab loses nothing.</p>"))
    S = MP.WIZARD_STEPS
    panes = []
    # STEP 1 - Objective: radio choices, then the KPI, per spec section 9.
    objs = "".join(
        f"<label class='mc-radio'><input type='radio' name='mc-cobj' "
        f"value='{e(o)}'{' checked' if o == 'LEADS' else ''}>"
        f"<b>{e(o.title().replace('_', ' '))}</b></label>"
        for o in M.OBJECTIVES)
    kpis = "".join(f"<option value='{e(k)}'>{e(k)}</option>" for k in MP.KPIS)
    panes.append(_wpane(
        0, S[0][0], S[0][1], S[0][2],
        "<p class='mc-wq'>What are you trying to achieve?</p>"
        f"<div class='mc-radios'>{objs}</div>"
        f"<div class='mc-form'><label>Primary KPI"
        f"<select id='mc-ckpi'>{kpis}</select></label>"
        "<label>Campaign name<input id='mc-cname' "
        "placeholder='Autumn leads DE'></label></div>"))
    # STEP 2 - Platforms: connection status + what each can do.
    prows = []
    for p in M.PROVIDERS:
        live, why = M.Adapter(p).available()
        cannot = [o for o in M.OBJECTIVES if not M.supports(p, o)["ok"]]
        prows.append(
            f"<label class='mc-radio'><input type='radio' name='mc-cprov' "
            f"value='{e(p)}'{' checked' if p == 'google' else ''}>"
            f"<b>{e(p.title())}</b>"
            f"<i>{'✓ Connected' if live else 'not connected'}</i>"
            f"<span>{e('cannot do: ' + ', '.join(cannot) if cannot else 'all objectives')}"
            f" &middot; calls the middle level a "
            f"{e(M.LEVEL_WORDS.get(p, 'ad group'))}</span></label>")
    panes.append(_wpane(1, S[1][0], S[1][1], S[1][2],
                        "<div class='mc-radios'>" + "".join(prows)
                        + "</div><p class='mc-note'>a platform that is not "
                          "connected can still be planned; the launch order "
                          "holds until its key exists</p>"))
    # STEP 3 - Budget, with the AI allocation and its WHY.
    alloc = MP.allocate(r, 3000)
    ahtml = ("".join(
        f"<div class='mc-alloc'><b>{e(x['provider'])}</b>"
        f"<span class='mc-allocbar'><span style='width:"
        f"{min(100, int((x.get('share') or 0) * 100))}%'></span></span>"
        f"<i>{int((x.get('share') or 0) * 100)}% &middot; "
        f"{_n(x.get('amount'))}</i>"
        f"<p>{e(x.get('why', ''))[:140]}</p></div>"
        for x in (alloc.get("rows") or []))
        + f"<p class='mc-note'>{e(alloc.get('message', ''))}</p>")
    panes.append(_wpane(2, S[2][0], S[2][1], S[2][2],
                        "<div class='mc-form'>"
                        "<label>Budget type<select id='mc-cbt'>"
                        "<option value='DAILY'>DAILY</option>"
                        "<option value='LIFETIME'>LIFETIME</option>"
                        "</select></label>"
                        "<label>Amount<input id='mc-cbud' type='number' "
                        "min='0' placeholder='50'></label>"
                        "<label>Start<input id='mc-cstart' type='date'>"
                        "</label>"
                        "<label>End<input id='mc-cend' type='date'></label>"
                        "<button class='mc-btn mc-go' "
                        "onclick='mcNewCampaign(this)'>Save draft</button>"
                        "</div>"
                        "<p class='mc-wq'>AI allocation of a 3,000 example "
                        "budget, and why:</p>" + ahtml))
    # STEP 4 - Audience, against the draft.
    aud_body = (_attach_audience(r, draft) if draft else
                "<p class='mc-empty'>save the draft in step 3 first</p>")
    panes.append(_wpane(3, S[3][0], S[3][1], S[3][2], aud_body))
    # STEP 5 - Creative.
    cre_body = (_attach_creative(r, draft) if draft else
                "<p class='mc-empty'>save the draft in step 3 first</p>")
    panes.append(_wpane(4, S[4][0], S[4][1], S[4][2], cre_body))
    # STEP 6 - Tracking.
    trk = ("✓ conversion tracking is configured" if MP._tracking_live()
           else "⚠ " + MP._tracking_why())
    panes.append(_wpane(5, S[5][0], S[5][1], S[5][2],
                        f"<p class='mc-check mc-"
                        f"{'ok' if MP._tracking_live() else 'warning'}'>"
                        f"{e(trk)}</p>"
                        "<p class='mc-note'>tags are managed on the "
                        "Tracking screen; the pre-flight warns rather than "
                        "blocks on this</p>"))
    # STEP 7 - Review: the real pre-flight of the draft.
    if draft:
        pf = MP.pre_flight(r, draft["id"])
        rev = "".join(
            "<div class='mc-check mc-" + x["state"].lower() + "'>"
            + {"OK": "✓", "WARNING": "⚠", "ERROR": "✗"}[x["state"]]
            + f" <b>{e(x['name'])}</b><span>{e(x['detail'])[:90]}</span>"
              "</div>" for x in pf["checks"]) \
            + f"<p class='mc-note'>{e(pf['message'])}</p>"
    else:
        rev = "<p class='mc-empty'>nothing to review yet</p>"
    panes.append(_wpane(6, S[6][0], S[6][1], S[6][2], rev))
    # STEP 8 - Launch / Schedule.
    if draft:
        cid = e(draft["id"])
        lch = (f"<button class='mc-btn mc-go' onclick=\"mcPost("
               f"'/mediaos/launch',{{campaign_id:'{cid}'}},this)\">"
               f"Launch campaign</button> "
               f"<input id='mc-wwhen-{cid}' type='datetime-local'> "
               f"<button class='mc-btn' onclick=\"mcLaunchAt('{cid}',this,'mc-wwhen-{cid}')\">"
               f"Schedule</button>"
               "<p class='mc-note'>launching queues ONE order behind the "
               "approval tier; a blocking error in step 7 refuses it with "
               "the list</p>")
    else:
        lch = "<p class='mc-empty'>nothing to launch yet</p>"
    panes.append(_wpane(7, S[7][0], S[7][1], S[7][2], lch, last=True))
    other = ("<p class='mc-note'>Other drafts: "
             + ", ".join(e(c.get("name")) for c in drafts[1:6])
             + "</p>" if len(drafts) > 1 else "")
    return card("New Campaign", header + "".join(panes) + other,
                "one step at a time; the record remembers where you were")


def _attach_audience(r, draft) -> str:
    cid = e(draft.get("id"))
    groups = r.find("ad_groups", campaign_id=draft.get("id"))
    have = [r.one("audiences", g.get("audience_id"))
            for g in groups if g.get("audience_id")]
    have = [a for a in have if a]
    cur = ("<p class='mc-note'>attached: "
           + ", ".join(e(a.get("name")) for a in have) + "</p>"
           if have else "<p class='mc-empty'>no audience attached yet; the "
                        "platform would choose one for you</p>")
    auds = "".join(f"<option value='{e(a.get('id'))}'>{e(a.get('name'))}"
                   f"</option>" for a in r.all("audiences")[:50]) \
        or "<option value=''>none yet - create one below</option>"
    types = "".join(f"<option value='{e(t)}'>{e(t)}</option>"
                    for t in MC.AUDIENCE_TYPES)
    fields = ", ".join(sorted(MC.TARGET_FIELDS)[:10])
    return (cur
            + f"<div class='mc-form'><label>Attach an audience"
              f"<select id='mc-aud-{cid}'>{auds}</select></label>"
              f"<button class='mc-btn mc-go' onclick=\"mcAttach('{cid}',"
              f"this)\">Attach (with the creative from step 5)</button>"
              f"</div>"
              "<p class='mc-wq'>or define a new one, provider-neutrally:"
              "</p>"
              "<div class='mc-form'>"
              "<label>Name<input id='mc-waname'></label>"
              f"<label>Type<select id='mc-watype'>{types}</select></label>"
              "<label>Definition (JSON)<textarea id='mc-wadef' rows='3' "
              "placeholder='{\"countries\": [\"DE\"]}'></textarea></label>"
              "<button class='mc-btn' onclick=\"mcNewAudience(this,"
              "'mc-wa')\">Save audience</button>"
              f"<p class='mc-note'>targetable fields include {e(fields)}; "
              f"what a platform cannot express is DROPPED and named, "
              f"never silently widened</p></div>")


def _attach_creative(r, draft) -> str:
    cid = e(draft.get("id"))
    ads = r.find("ads", campaign_id=draft.get("id"))
    have = [r.one("creatives", a.get("creative_id"))
            for a in ads if a.get("creative_id")]
    have = [c for c in have if c]
    cur = ("<p class='mc-note'>attached: "
           + ", ".join(e(c.get("name")) for c in have) + "</p>"
           if have else "<p class='mc-empty'>no creative attached; there "
                        "is nothing to show anyone yet</p>")
    cres = "".join(f"<option value='{e(x.get('id'))}'>{e(x.get('name'))}"
                   f"</option>" for x in r.all("creatives")[:50]) \
        or "<option value=''>none yet - create one below</option>"
    types = "".join(f"<option value='{e(t)}'>{e(t)}</option>"
                    for t in MC.CREATIVE_TYPES)
    stages = "".join(f"<option value='{e(s)}'>{e(s)}</option>"
                     for s in MC.FUNNEL_STAGES)
    return (cur
            + f"<div class='mc-form'><label>Attach a creative"
              f"<select id='mc-cre-{cid}'>{cres}</select></label>"
              f"<label>Landing page<input id='mc-lp-{cid}' "
              f"placeholder='https://landing.page'></label>"
              f"<button class='mc-btn mc-go' onclick=\"mcAttach('{cid}',"
              f"this)\">Attach group + ad</button></div>"
              "<p class='mc-wq'>or add to the library, with the attributes "
              "the engine learns from:</p>"
              "<div class='mc-form'>"
              "<label>Name<input id='mc-wcrname'></label>"
              f"<label>Format<select id='mc-wcrtype'>{types}</select>"
              f"</label>"
              "<label>Concept<input id='mc-wcrconcept' "
              "placeholder='Save 30%'></label>"
              "<label>Angle<input id='mc-wcrangle' "
              "placeholder='pain-point'></label>"
              "<label>Hook<input id='mc-wcrhook' "
              "placeholder='Still booking by phone?'></label>"
              "<label>Persona<input id='mc-wcrpersona'></label>"
              "<label>CTA<input id='mc-wcrcta'></label>"
              f"<label>Funnel stage<select id='mc-wcrstage'>{stages}"
              f"</select></label>"
              "<label>Headline<input id='mc-wcrhead'></label>"
              "<label>Primary text<input id='mc-wcrtext'></label>"
              "<button class='mc-btn' onclick=\"mcNewCreative(this,"
              "'mc-wcr')\">Save + publish v1</button></div>")


def _detail(r, c, ctx) -> str:
    """The deep campaign screen, spec section 33: status, KPIs, trend,
    audiences, creatives, placements, diagnosis, execution history."""
    cid = c.get("id")
    ro = MF.rollup(r, campaign_id=cid, days=30)
    tot = ro["totals"]
    head = ("<div class='mc-bigrow'>"
            + "".join(f"<div class='mc-big'><span class='mc-bigk'>{e(k)}"
                      f"</span><b>{v}</b><span class='mc-bigs'>{e(s)}"
                      f"</span></div>" for k, v, s in (
                ("Status", e(c.get("state")), c.get("state_why") or ""),
                ("Platform", e(c.get("provider") or "-"), ""),
                ("Objective", e(c.get("objective")), ""),
                ("Budget", _money(c.get("budget_amount"),
                                  c.get("currency") or "EUR"),
                 str(c.get("budget_type") or "").lower()),
                ("ROAS", _n((tot.get("roas") or {}).get("value")),
                 (tot.get("roas") or {}).get("of") or ""),
                ("CPA", _n((tot.get("cpa") or {}).get("value")),
                 (tot.get("cpa") or {}).get("of") or ""),
                ("CTR", _n((tot.get("ctr") or {}).get("value")),
                 "percent"),
            )) + "</div>")
    trend = ("<div class='mc-chrow'>"
             + chart([(x["bucket"], x["spend"]) for x in ro["rows"]],
                     title="Spend", w=400)
             + chart([(x["bucket"], (x.get("roas") or {}).get("value"))
                      for x in ro["rows"]],
                     title="ROAS", color="#3FD98B", w=400)
             + "</div>"
             + table(("day", "spend", "clicks", "conv", "CPA", "ROAS"),
                     [(x["bucket"], _n(x["spend"]), _n(x["clicks"]),
                       _n(x["conversions"]),
                       _n((x.get("cpa") or {}).get("value")),
                       _n((x.get("roas") or {}).get("value")))
                      for x in ro["rows"][-14:]],
                     ro["message"]))
    groups = r.find("ad_groups", campaign_id=cid)
    auds = [r.one("audiences", g.get("audience_id"))
            for g in groups if g.get("audience_id")]
    audtab = table(("audience", "type", "platform can express"),
                   [(a.get("name"), a.get("type"),
                     MC.map_to_provider(a.get("definition"),
                                        c.get("provider"))
                     .get("message", "")[:90] if c.get("provider") else "-")
                    for a in auds if a],
                   "no audience attached; the platform chooses one")
    ads = r.find("ads", campaign_id=cid)
    perf = {x["id"]: x for x in MC.creative_performance(r)}
    cres = []
    for a in ads:
        cr = r.one("creatives", a.get("creative_id")) or {}
        px = perf.get(cr.get("id")) or {}
        cres.append((cr.get("name") or "(no creative)",
                     cr.get("angle") or "-", _n(px.get("spend") or None),
                     _n(px.get("cpa")), _n(px.get("roas"))))
    cretab = table(("creative", "angle", "spend", "CPA", "ROAS"), cres,
                   "no ad on this campaign yet")
    plc = MF.breakdown(r, "placement", campaign_id=cid)
    plctab = (table(("placement", "spend", "conv", "ROAS"),
                    [(x["value"], _n(x["spend"]), _n(x["conversions"]),
                      _n((x.get("roas") or {}).get("value")))
                     for x in plc["rows"][:8]])
              if plc["rows"] else
              f"<p class='mc-empty'>{e(plc['message'])}</p>")
    # AI DIAGNOSIS: this campaign's anomalies and its open orders.
    sc = [a for a in MF.scan(r, save=False)["anomalies"]
          if a["campaign_id"] == cid]
    mine = [o for o in (ctx.get("media_orders") or ())
            if str(o.get("key")) == str(cid) and o.get("status") == "open"]
    diag = (("".join(f"<p class='mc-note'>⚠ {e(a['evidence'])}</p>"
                     for a in sc[:3])
             + "".join(_action_card(o) for o in mine[:3]))
            or "<p class='mc-empty'>nothing is broken against this "
               "campaign's own baseline, and no action is waiting. Quiet "
               "is a finding.</p>")
    hist = [o for o in (ctx.get("media_orders") or ())
            if str(o.get("key")) == str(cid) and o.get("status") != "open"]
    histtab = table(("action", "lifecycle", "result"),
                    [(o.get("say", "")[:80], _lifecycle_word(o),
                      o.get("result", "")[:60]) for o in hist[:8]],
                    "nothing has been executed against this campaign")
    return ("<div class='mc-detail' id='mc-det-" + e(cid) + "'>"
            + head
            + card("Trend, 14 days", trend)
            + card("Audiences", audtab)
            + card("Creatives", cretab)
            + card("Placements", plctab)
            + card("AI diagnosis", diag)
            + card("Execution history", histtab)
            + "</div>")


def _lifecycle_word(o) -> str:
    try:
        import content_engine_media_orders as MO
        return MO.lifecycle_of(o)
    except Exception:
        return str(o.get("status") or "")


def s_launch(r, ctx) -> str:
    cands = [c for c in r.all("media_campaigns")
             if c.get("state") in ("DRAFT", "READY", "SCHEDULED",
                                   "VALIDATION_FAILED")]
    if not cands:
        return card("Launch Centre",
                    "<p class='mc-empty'>Nothing is waiting to launch. "
                    "Draft a campaign under New Campaign first.</p>")
    out = []
    for c in cands[:12]:
        pf = MP.pre_flight(r, c.get("id"))
        lights = "".join(
            "<div class='mc-check mc-" + x["state"].lower() + "'>"
            + {"OK": "✓", "WARNING": "⚠", "ERROR": "✗"}[x["state"]]
            + f" <b>{e(x['name'])}</b><span>{e(x['detail'])[:100]}</span></div>"
            for x in pf["checks"])
        cid = e(c.get("id"))
        # [Preview]: what the person will actually see, from the attached
        # creative, before a cent moves. Spec section 22 / 36.
        ads = r.find("ads", campaign_id=c.get("id"))
        cre = (r.one("creatives", ads[0].get("creative_id"))
               if ads and ads[0].get("creative_id") else None) or {}
        prev = (f"<div class='mc-preview' id='mc-prev-{cid}'>"
                f"<span class='mc-prevtag'>Approximate preview &middot; "
                f"{e(c.get('provider') or '-')}</span>"
                f"<b>{e(cre.get('headline') or cre.get('hook') or cre.get('concept') or '(no headline yet)')}</b>"
                f"<p>{e(cre.get('primary_text') or cre.get('description') or '(no primary text yet)')}</p>"
                f"<i>{e((ads[0].get('landing_page_url') if ads else '') or 'no landing page')}</i>"
                f"<button class='mc-btn'>{e(cre.get('cta') or 'Learn more')}"
                f"</button></div>") if cre or ads else \
            (f"<div class='mc-preview' id='mc-prev-{cid}'>"
             f"<p class='mc-empty'>no creative attached, so there is "
             f"nothing to preview</p></div>")
        btns = ("<div class='mc-wnav'>"
                f"<button class='mc-btn' onclick=\"mcToggle('mc-prev-{cid}')"
                f"\">Preview</button>"
                + (f"<button class='mc-btn mc-go' onclick=\"mcPost("
                   f"'/mediaos/launch',{{campaign_id:'{cid}'}},this)\">"
                   f"Launch Campaign</button> "
                   f"<input id='mc-when-{cid}' type='datetime-local'> "
                   f"<button class='mc-btn' onclick=\"mcLaunchAt('{cid}',"
                   f"this)\">Schedule</button>"
                   if pf["ok"] else
                   f"<span class='mc-note'>blocked: "
                   f"{e(', '.join(pf['errors']))}. Launch stays off until "
                   f"every blocking error clears.</span>")
                + "</div>")
        out.append(card(f"{c.get('name')} ({pf['level']})",
                        lights + prev + btns, pf["message"][:160]))
    # THE PUBLISH LOG, spec section 19: every step, every provider
    # error, nothing hidden.
    jobs = sorted(r.all("publish_jobs"),
                  key=lambda j: str(j.get("updated_at") or ""),
                  reverse=True)
    logs = []
    for j in jobs[:5]:
        c2 = r.one("media_campaigns", j.get("campaign_id")) or {}
        steps = "".join(
            "<div class='mc-check mc-"
            + {"OK": "ok", "SKIPPED": "ok", "PENDING": "warning",
               "HELD": "warning"}.get(x.get("status"), "error") + "'>"
            + {"OK": "✓", "SKIPPED": "✓", "PENDING": "⏳",
               "HELD": "⚠"}.get(x.get("status"), "✕")
            + f" <b>{e(x.get('step'))}</b>"
            + f"<span>{e(x.get('status'))}: {e(x.get('detail'))[:100]}"
            + (f" [{e(_D(x.get('error')).get('category'))}"
               f"{', retryable' if _D(x.get('error')).get('retryable') else ''}]"
               if x.get("error") else "") + "</span></div>"
            for x in _L(j.get("steps")))
        logs.append(card(
            f"Publish: {c2.get('name', j.get('campaign_id'))} "
            f"({j.get('state')})", steps,
            f"attempt {int(j.get('attempt') or 1)}; idempotent: re-running "
            f"cannot create a duplicate"))
    pl = ("".join(logs)
          or "<p class='mc-empty'>no publish job has run yet; the step "
             "log appears here the first time a launch executes</p>")
    return ("<p class='mc-note'>A launch never talks to a platform from "
            "here. It queues ONE order in the media queue and waits behind "
            "the same approval tier as every other spend.</p>" + "".join(out)
            + card("The publish log", pl,
                   "spec section 19: provider errors are shown, not "
                   "hidden"))


def _plan_doc(r, p) -> str:
    """One saved plan, rendered as the MEDIA PLAN document of spec
    section 34, ranges and assumptions on the page."""
    fc = _D(p.get("forecast"))
    conv = _D(fc.get("conversions"))
    cpa = _D(fc.get("cpa"))
    alloc = _L(p.get("allocation"))
    bars = "".join(
        f"<div class='mc-alloc'><b>{e(x.get('provider'))}</b>"
        f"<span class='mc-allocbar'><span style='width:"
        f"{min(100, int((x.get('share') or 0) * 100))}%'></span></span>"
        f"<i>{int((x.get('share') or 0) * 100)}% &middot; "
        f"{_n(x.get('amount'))}</i></div>"
        for x in alloc) or "<p class='mc-empty'>no allocation: nothing had "\
                           "enough history when this plan was saved</p>"
    assumps = "".join(f"<li>{e(a)}</li>" for a in _L(p.get("assumptions")))
    return ("<div class='mc-doc'>"
            "<p class='mc-doctitle'>MEDIA PLAN</p>"
            "<div class='mc-docrow'><span>Objective</span><b>"
            + e(p.get("objective")) + " on " + e(p.get("kpi") or "CPA")
            + "</b></div>"
            "<div class='mc-docrow'><span>Budget</span><b>"
            + _money(p.get("budget"), p.get("currency") or "EUR")
            + "</b></div>"
            "<div class='mc-docrow'><span>Period</span><b>"
            + e(p.get("period_start") or "?") + " to "
            + e(p.get("period_end") or "?") + "</b></div>"
            "<div class='mc-docrow'><span>Expected CPA</span><b>"
            + (f"{_n(cpa.get('low'))} to {_n(cpa.get('high'))}"
               if cpa.get("low") is not None else "no history to range on")
            + "</b></div>"
            "<div class='mc-docrow'><span>Expected conversions</span><b>"
            + (f"{_n(conv.get('low'))} to {_n(conv.get('high'))}"
               if conv.get("low") is not None else "no history to range on")
            + "</b></div>"
            "<div class='mc-docrow'><span>Targets</span><b>CPA "
            + _n(p.get("target_cpa")) + " &middot; ROAS "
            + _n(p.get("target_roas")) + " &middot; leads "
            + _n(p.get("target_leads")) + "</b></div>"
            "<p class='mc-wq'>Allocation</p>" + bars
            + ("<p class='mc-wq'>Assumptions</p><ul class='mc-assume'>"
               + assumps + "</ul>" if assumps else "")
            + "</div>")


def s_plan(r, ctx) -> str:
    plans = sorted(r.all("media_plans"),
                   key=lambda p: str(p.get("created_at") or ""),
                   reverse=True)
    docs = ("".join(_plan_doc(r, p) for p in plans[:3])
            or "<p class='mc-empty'>no media plan yet. A plan is the "
               "professional step before ads exist: objective, budget, "
               "period, an expected RANGE and the assumptions under it."
               "</p>")
    alloc = MP.allocate(r, MF._live_budget(r) or 3000)
    ahtml = ("".join(
        f"<div class='mc-alloc'><b>{e(x['provider'])}</b>"
        f"<span class='mc-allocbar'><span style='width:"
        f"{min(100, int((x.get('share') or 0) * 100))}%'></span></span>"
        f"<i>{int((x.get('share') or 0) * 100)}% &middot; "
        f"{_n(x.get('amount'))}</i><p>{e(x.get('why', ''))[:140]}</p></div>"
        for x in (alloc.get("rows") or []))
        + f"<p class='mc-note'>{e(alloc.get('message', ''))}</p>")
    objs = "".join(f"<option value='{e(o)}'>{e(o)}</option>"
                   for o in M.OBJECTIVES)
    kpis = "".join(f"<option value='{e(k)}'>{e(k)}</option>" for k in MP.KPIS)
    form = ("<div class='mc-form'>"
            f"<label>Objective<select id='mc-pobj'>{objs}</select></label>"
            "<label>Budget<input id='mc-pbud' type='number' min='1' "
            "placeholder='3000'></label>"
            f"<label>KPI<select id='mc-pkpi'>{kpis}</select></label>"
            "<label>From<input id='mc-pfrom' type='date'></label>"
            "<label>To<input id='mc-pto' type='date'></label>"
            "<label>Target CPA<input id='mc-pcpa' type='number' min='0'>"
            "</label>"
            "<button class='mc-btn mc-go' onclick='mcSavePlan(this)'>"
            "Save the plan</button></div>")
    sim = ("<div class='mc-doc'><p class='mc-doctitle'>WHAT IF?</p>"
           "<div class='mc-form'>"
           "<label>Budget now<input id='mc-snow' type='number' "
           "placeholder='3000'></label>"
           "<label>What if<input id='mc-swhat' type='number' "
           "placeholder='6000'></label>"
           "<button class='mc-btn mc-go' onclick='mcSimulate(this)'>"
           "Simulate</button></div><div id='mc-simout'><p class='mc-empty'>"
           "Conservative, base and optimistic come back, never one number. "
           "With no history it says so instead of inventing a benchmark."
           "</p></div></div>")
    return (docs
            + card("AI allocation on marginal return", ahtml,
                   "the next euro, not the average euro")
            + card("New plan", form)
            + sim)


def s_creat(r, ctx) -> str:
    # ONE pass for every creative's numbers, then a fatigue read per row.
    perf = {x["id"]: x for x in MC.creative_performance(r)}
    rows = []
    for c in r.all("creatives")[:40]:
        px = perf.get(c.get("id")) or {}
        fat = {}
        try:
            fat = MC.fatigue(r, c.get("id")) or {}
        except Exception:
            pass
        rows.append((e(c.get("name")), e(c.get("type") or "-"),
                     e(c.get("angle") or "-"), e(c.get("hook") or "-")[:40],
                     e(c.get("funnel_stage") or "-"),
                     _n(px.get("spend") or None),
                     _n(fat.get("score"), "not measured")))
    lib = table(("creative", "format", "angle", "hook", "stage", "spend",
                 "fatigue"), rows,
                "The library is empty. A creative is a concept with "
                "attributes, not a lone image; the attributes are what "
                "the engine learns from.")
    dims = "".join(f"<option value='{e(a)}'>{e(a)}</option>"
                   for a in MC.ATTRIBUTES)
    mx = {}
    try:
        mx = MC.matrix(r, "angle") or {}
    except Exception:
        pass
    verdict = (mx.get("verdict") or {})
    mtab = ("<div class='mc-form'><label>Dimension"
            f"<select id='mc-mdim' onchange='mcMatrix(this)'>{dims}</select>"
            "</label></div><div id='mc-mout'>"
            + table(("value", "spend", "conversions", "CPA"),
                    [(x.get("value"), _n(x.get("spend")),
                      _n(x.get("conversions")), _n(x.get("cpa")))
                     for x in (mx.get("rows") or [])[:12]],
                    "nothing measured per angle yet")
            + f"<p class='mc-note'>{e(verdict.get('message', ''))}</p></div>")
    learned = {}
    try:
        learned = MC.learn(r) or {}
    except Exception:
        pass
    lrn = ("<p class='mc-note'>" + e(learned.get("message", "")) + "</p>"
           + table(("attribute", "finding"),
                   [(f.get("attribute") or f.get("dimension") or "-",
                     (f.get("message") or f.get("finding") or "")[:130])
                    for f in (learned.get("findings") or [])[:10]],
                   "nothing has earned a verdict yet"))
    types = "".join(f"<option value='{e(t)}'>{e(t)}</option>"
                    for t in MC.CREATIVE_TYPES)
    stages = "".join(f"<option value='{e(s)}'>{e(s)}</option>"
                     for s in MC.FUNNEL_STAGES)
    form = ("<div class='mc-form'>"
            "<label>Name<input id='mc-crname'></label>"
            f"<label>Format<select id='mc-crtype'>{types}</select></label>"
            "<label>Concept<input id='mc-crconcept' "
            "placeholder='Save 30%'></label>"
            "<label>Angle<input id='mc-crangle' "
            "placeholder='pain-point'></label>"
            "<label>Hook<input id='mc-crhook' "
            "placeholder='Still booking by phone?'></label>"
            "<label>Persona<input id='mc-crpersona' "
            "placeholder='practice manager'></label>"
            "<label>CTA<input id='mc-crcta' placeholder='Book a call'>"
            "</label>"
            f"<label>Funnel stage<select id='mc-crstage'>{stages}</select>"
            "</label>"
            "<label>Headline<input id='mc-crhead'></label>"
            "<label>Primary text<input id='mc-crtext'></label>"
            "<button class='mc-btn mc-go' onclick='mcNewCreative(this)'>"
            "Save + publish v1</button>"
            "<p class='mc-note'>Versions are immutable: publishing again "
            "appends v2 and v1 stays measurable.</p></div>")
    exps = r.all("creative_experiments")
    erows = []
    for x in exps[:15]:
        erows.append((e(x.get("name")), e(x.get("metric")),
                      e(x.get("status")),
                      e((r.one("creatives", x.get("winner")) or {})
                        .get("name") or "none yet"),
                      f"<button class='mc-btn' onclick=\"mcPost("
                      f"'/mediaos/experiment-judge',{{experiment_id:"
                      f"'{e(x.get('id'))}'}},this)\">Judge</button>"))
    exform = ("<div class='mc-form'>"
              "<label>Name<input id='mc-xname'></label>"
              "<label>Creative ids (comma)<input id='mc-xids' "
              "placeholder='cre_a, cre_b'></label>"
              "<label>Metric<select id='mc-xmetric'>"
              "<option>cpa</option><option>roas</option>"
              "<option>ctr</option><option>cvr</option></select></label>"
              "<button class='mc-btn mc-go' onclick='mcNewExperiment(this)'>"
              "Start experiment</button>"
              "<p class='mc-note'>A winner is declared only past the sample "
              "floor and a 30 percent lead; below that the ranking is "
              "noise.</p></div>")
    briefbtn = ("<div class='mc-form'>"
                "<button class='mc-btn mc-go' onclick=\"mcPost("
                "'/mediaos/briefs',{count:3},this)\">Draft 3 briefs from "
                "the measured winners</button>"
                "<p class='mc-note'>Deterministic: briefs come from the "
                "matrix's proven attributes, never from imagination. With "
                "no verdicts it refuses.</p></div>")
    return (card("The library", lib)
            + card("The matrix: attributes, not just creatives", mtab,
                   "verdicts refuse to speak below the sample floor")
            + card("What the engine has learned", lrn + briefbtn)
            + card("Experiments",
                   table(("experiment", "metric", "status", "winner",
                          "judge"), erows,
                         "no experiment yet; start one over two or more "
                         "creatives") + exform)
            + card("New creative", form))


def s_aud(r, ctx) -> str:
    rows = []
    try:
        rows = MC.audience_rows(r)
    except Exception:
        rows = []
    atab = table(("audience", "type", "partial on", "size"),
                 [(x.get("name"), x.get("type"),
                   ", ".join(x.get("partial") or ()) or "expressed fully "
                                                        "everywhere",
                   _n(x.get("size"), "not measured")) for x in rows[:40]],
                 "No audiences yet. Define one provider-neutrally; the "
                 "mapper tells you what each platform drops.")
    types = "".join(f"<option value='{e(t)}'>{e(t)}</option>"
                    for t in MC.AUDIENCE_TYPES)
    fields = ", ".join(sorted(MC.TARGET_FIELDS)[:12]) + " ..."
    form = ("<div class='mc-form'>"
            "<label>Name<input id='mc-aname'></label>"
            f"<label>Type<select id='mc-atype'>{types}</select></label>"
            "<label>Definition (JSON)<textarea id='mc-adef' rows='3' "
            "placeholder='{\"countries\": [\"DE\"], "
            "\"job_titles\": [\"practice manager\"]}'></textarea></label>"
            "<button class='mc-btn mc-go' onclick='mcNewAudience(this)'>"
            "Save audience</button>"
            f"<p class='mc-note'>Fields any platform can target: {e(fields)}. "
            "A field none of them understands is refused at save time, with "
            "the list.</p></div>")
    return card("Audiences", atab) + card("New audience", form)


def s_perf(r, ctx) -> str:
    blocks = []
    for grain in ("DAILY", "WEEKLY", "MONTHLY"):
        ro = MF.rollup(r, grain=grain)
        tot = ro["totals"]
        rows = [(x["bucket"], x["name"], _n(x.get("spend")),
                 _n(x.get("impressions")), _n(x.get("clicks")),
                 _n((x.get("ctr") or {}).get("value")),
                 _n(x.get("conversions")),
                 _n((x.get("cpa") or {}).get("value")),
                 _n((x.get("roas") or {}).get("value")))
                for x in ro["rows"][-30:]]
        on = " mc-on" if grain == "DAILY" else ""
        blocks.append(
            f"<div class='mc-grain{on}' id='mc-grain-{grain}'>"
            + table(("bucket", "campaign", "spend", "impr", "clicks",
                     "CTR%", "conv", "CPA", "ROAS"), rows, ro["message"])
            + "<p class='mc-note'>totals: spend " + _n(tot.get("spend"))
            + " &middot; CPA " + _n((tot.get("cpa") or {}).get("value"))
            + " (" + e((tot.get("cpa") or {}).get("of") or "")
            + ") &middot; ROAS " + _n((tot.get("roas") or {}).get("value"))
            + "</p></div>")
    switch = "".join(
        f"<button class='mc-btn{' mc-go' if g == 'DAILY' else ''}' "
        f"onclick=\"mcGrain('{g}',this)\">{g}</button>"
        for g in ("DAILY", "WEEKLY", "MONTHLY"))
    dsp = {}
    for x in MF.rollup(r, grain="DAILY")["rows"]:
        dsp[x["bucket"]] = dsp.get(x["bucket"], 0.0) + float(x["spend"] or 0)
    perfchart = chart(sorted(dsp.items()), title="Spend per day, all "
                                                 "campaigns")
    cmpres = MF.compare(r)
    crows = [(m["metric"], _n(m.get("before")), _n(m.get("now")),
              (f"{m['change']:+.1f}%" if m.get("change") is not None
               else "--"), m["why"][:80]) for m in cmpres["moves"]]
    ctab = table(("metric", "last 7d before", "this 7d", "change", "why"),
                 crows)
    rec = MF.reconcile(r)
    rtab = (table(("campaign", "platform claims", "engine observed", "gap",
                   "why"),
                  [(x["name"], x["platform_claims"], x["engine_observed"],
                    x["gap"], x["why"][:110]) for x in rec["rows"][:15]],
                  rec["message"])
            + f"<p class='mc-note'>{e(rec['message'])}</p>")
    dims = []
    for by in MF.DIMENSIONS:
        bd = MF.breakdown(r, by)
        if bd["rows"]:
            dims.append(card(
                f"By {by}",
                table(("value", "spend", "conv", "CPA", "ROAS"),
                      [(x["value"], _n(x["spend"]), _n(x["conversions"]),
                        _n((x.get("cpa") or {}).get("value")),
                        _n((x.get("roas") or {}).get("value")))
                       for x in bd["rows"][:12]])))
        else:
            dims.append(f"<p class='mc-note'>{e(by)}: "
                        f"{e(bd['message'])}</p>")
    return (card("Rollups", perfchart
                 + f"<div class='mc-form'>{switch}</div>"
                 + "".join(blocks),
                 "the same numbers at whichever grain the question needs")
            + card("This week against last week", ctab)
            + card("Breakdowns", "".join(dims),
                   "country, device, placement, age, gender - only what "
                   "the rows actually carry")
            + card("Platform claims vs what this engine observed", rtab,
                   "neither number is corrected into the other"))


def s_attr(r, ctx) -> str:
    sp = MF.model_spread(r)
    stab = table(("campaign",) + MF.ATTRIBUTION_MODELS + ("spread", "why"),
                 [tuple([x["name"]] + [_n(x.get(m)) for m in
                                       MF.ATTRIBUTION_MODELS]
                        + [x["spread"], x["why"][:90]])
                  for x in sp["rows"][:20]], sp["message"])
    lt = MF.attribute(r, model="last_touch")
    note = ("<p class='mc-note'>" + e(lt.get("message", "")) + "</p>"
            "<p class='mc-note'>" + e(lt.get("convention", "")) + "</p>")
    return card("Five models, side by side", stab + note,
                "the disagreement is the information")


def s_anom(r, ctx) -> str:
    sc = MF.scan(r, save=False)
    arows = [(a["severity"].upper(), a["name"], a["type"],
              f"{_n(a.get('current'))} vs {_n(a.get('baseline'))} "
              f"({_n(a.get('ratio'))}x)",
              a["evidence"][:110]) for a in sc["anomalies"][:20]]
    atab = (table(("severity", "campaign", "what", "numbers", "evidence"),
                  arows, "No campaign has broken its own baseline.")
            + f"<p class='mc-note'>{e(sc['message'])}</p>")
    nj = table(("campaign", "why it is not judged"),
               [(x["name"], x["why"]) for x in sc["not_judged"][:10]],
               "every campaign has enough history to judge")
    btn = ("<div class='mc-form'>"
           "<button class='mc-btn mc-go' onclick=\"mcPost('/mediaos/propose'"
           ",{},this)\">Turn anomalies into verdicts</button>"
           "<p class='mc-note'>Each verdict lands in the order queue below "
           "with metric, threshold, window and source, and waits for your "
           "click. There is no auto-spend level at all.</p></div>")
    pol = {}
    try:
        import content_engine_api as A
        import content_engine_media_orders as MO
        pol = MO.get_policy(A.get_store())
    except Exception:
        pol = {}
    polform = (
        "<div class='mc-form'>"
        "<label>Budget change auto up to (%)"
        f"<input id='mc-pol-bud' type='number' min='0' max='25' "
        f"value='{e(pol.get('budget_change_auto_pct', 0))}'></label>"
        "<label>Auto-pause if daily spend under"
        f"<input id='mc-pol-pause' type='number' min='0' "
        f"value='{e(pol.get('pause_auto_if_daily_spend_under', 0))}'>"
        "</label>"
        "<label>Negative keywords<select id='mc-pol-neg'>"
        + "".join(f"<option{' selected' if pol.get('negative_keyword') == v else ''}>{v}</option>"
                  for v in ("approval", "auto")) + "</select></label>"
        "<button class='mc-btn mc-go' onclick='mcSavePolicy(this)'>"
        "Save policy</button>"
        "<p class='mc-note'>Every default is approval and 0. Autonomy is "
        "something YOU raise here, never something the engine assumes; a "
        "new campaign is never automatic and delete stays human-only."
        "</p></div>")
    # THE AUDIT, spec section 48: every decided action as a card that
    # shows before, after, reason, confidence, policy and result.
    decided = [o for o in (ctx.get("media_orders") or ())
               if o.get("status") != "open"]
    audits = []
    for o in decided[:6]:
        ev = o.get("evidence") or {}
        bef, aft = _D(o.get("before_state")), _D(o.get("after_state"))
        conf = o.get("confidence")
        audits.append(
            "<div class='mc-doc mc-audit'>"
            "<p class='mc-doctitle'>AI ACTION</p>"
            + "".join(f"<div class='mc-docrow'><span>{e(k)}</span>"
                      f"<b>{v}</b></div>" for k, v in (
                ("Action", e(o.get("say", ""))[:100]),
                ("Campaign", e(o.get("key", ""))[:60]),
                ("Before", e(bef.get("status") or bef.get("note")
                             or "not recorded")
                 + (f" &middot; budget {_n(bef.get('budget'))}"
                    if bef.get("budget") is not None else "")),
                ("After", e(aft.get("status") or "awaiting the next "
                                                 "platform read")),
                ("Reason", e(f"{ev.get('metric', '')} against "
                             f"{ev.get('threshold', '')} over "
                             f"{ev.get('window', '')}")),
                ("Confidence", (f"{conf:.0%} "
                                f"({e(o.get('confidence_basis', ''))})"
                                if isinstance(conf, (int, float))
                                else "not stated")),
                ("Policy", e("auto-approved by policy: "
                             + o.get("policy_why", "")
                             if o.get("approved_by") == "policy"
                             else "approved by you")),
                ("Result", e(_lifecycle_word(o)) + " &middot; "
                 + e(o.get("result", ""))[:80]),
            )) + "</div>")
    audit_html = ("".join(audits)
                  or "<p class='mc-empty'>no decided action yet; every "
                     "card will show before, after, reason, confidence, "
                     "policy and result</p>")
    return (card("What broke its own baseline", atab)
            + card("Refused for lack of history", nj,
                   "a red badge on 3 days of data is a coin toss")
            + btn
            + card("The autonomy policy", polform,
                   "what the agent may do without waking you")
            + card("The order queue", _orders_board(ctx))
            + card("The audit", audit_html,
                   "spec section 48: everything, with its before and "
                   "after"))


def s_alx(r, ctx) -> str:
    """The analytics workbench: the metric registry executed in the
    browser over an embedded cube, so a chart and its table are one
    aggregation call. Replaces the old Performance and Attribution tabs."""
    import content_engine_media_workbench as WB
    store = None
    try:
        import content_engine_api as A
        store = A.get_store()
    except Exception:
        pass
    if store is None:
        return ("<p class='mc-empty'>the store is not reachable, so the "
                "workbench has nothing true to compute</p>")
    return WB.build(r, store, ctx)


def _native_tracking(ctx) -> str:
    """GA4 and Search Console, drawn in THIS design. Replaces the old
    injected boards; same numbers, no old markup."""
    gi = _D(ctx.get("insights"))
    ga4, gsc = _D(gi.get("ga4")), _D(gi.get("gsc"))
    out = ""
    if ga4:
        t = _D(ga4.get("totals"))
        daily = _L(ga4.get("daily"))
        out += ("<div class='mc-bigrow'>"
                + "".join(f"<div class='mc-big'><span class='mc-bigk'>"
                          f"{e(k)}</span><b>{_n(v)}</b>"
                          f"<span class='mc-bigs'></span></div>"
                          for k, v in (
                    ("Sessions", t.get("sessions")),
                    ("Users", t.get("totalUsers")),
                    ("New users", t.get("newUsers")),
                    ("Engagement %",
                     round(float(t.get("engagementRate") or 0) * 100, 1)
                     if t.get("engagementRate") is not None else None)))
                + "</div>"
                + chart([(str(x.get("date") or i),
                          float(x.get("sessions") or 0))
                         for i, x in enumerate(daily)],
                        title="Sessions per day", color="#3FD98B")
                + table(("channel", "sessions"),
                        [(x.get("sessionDefaultChannelGroup"),
                          _n(x.get("sessions")))
                         for x in _L(ga4.get("channels"))[:8]],
                        "no channel split in the cached pull"))
    else:
        out += ("<p class='mc-empty'>No GA4 pull cached yet. Press "
                "'Pull platforms now' or refresh Google data; nothing is "
                "estimated to fill this in.</p>")
    if gsc:
        q = _L(gsc.get("queries"))
        imp = sum(float(x.get("impressions") or 0) for x in q)
        clk = sum(float(x.get("clicks") or 0) for x in q)
        pos = ([float(x.get("position") or 0) for x in q] or [0])
        out += ("<div class='mc-bigrow'>"
                + "".join(f"<div class='mc-big'><span class='mc-bigk'>"
                          f"{e(k)}</span><b>{v}</b>"
                          f"<span class='mc-bigs'>{e(sub)}</span></div>"
                          for k, v, sub in (
                    ("Impressions", _n(imp), ""),
                    ("Clicks", _n(clk), ""),
                    ("CTR", (f"{clk / imp * 100:.1f}" if imp else "--"),
                     f"{int(clk):,} of {int(imp):,}" if imp
                     else "nothing to measure yet"),
                    ("Avg position",
                     f"{sum(pos) / len(pos):.1f}" if q else "--",
                     f"over {len(q)} queries")))
                + "</div>"
                + table(("query", "clicks", "impressions", "position"),
                        [(x.get("query"), _n(x.get("clicks")),
                          _n(x.get("impressions")), _n(x.get("position")))
                         for x in sorted(
                             q, key=lambda y: -float(y.get("clicks") or 0)
                         )[:12]],
                        "no queries in the cached pull"))
    else:
        out += ("<p class='mc-empty'>No Search Console pull cached "
                "yet.</p>")
    return out


def _native_buyer(r, ctx) -> str:
    """The media buyer: draft a campaign, then talk to it. Native controls
    over the SAME endpoints the old page used, so no wire changed."""
    drafts = []
    for j in _L(ctx.get("jobs")):
        if str(_D(j).get("type")) == "media_campaign":
            p2 = _D(_D(j).get("payload")).get("media_buyer") or {}
            drafts.append((j.get("job_id"), p2.get("campaign_name"),
                           j.get("status")))
    rows = [(e(name or jid), e(st or ""),
             f"<button class='mc-btn' onclick=\"mcChatOpen('{e(jid)}')\">"
             f"Discuss</button> "
             f"<button class='mc-btn mc-go' onclick=\"mcPost("
             f"'/media/activate',{{job_id:'{e(jid)}'}},this)\">"
             f"Activate</button>")
            for jid, name, st in drafts[:10]]
    return ("<div class='mc-form'>"
            "<button class='mc-btn mc-go' onclick=\"mcPost("
            "'/media/draft',{},this)\">Draft a campaign with the agent"
            "</button>"
            "<p class='mc-note'>runs the existing media buyer once; the "
            "draft lands below and waits for your approval</p></div>"
            + table(("draft", "status", "actions"), rows,
                    "no agent draft on record yet")
            + "<div class='mc-form'>"
              "<input id='mc-chatjob' placeholder='job id (optional)'>"
              "<input id='mc-chatmsg' placeholder='ask the media buyer "
              "something' style='min-width:260px'>"
              "<button class='mc-btn' onclick='mcChatSend(this)'>Send"
              "</button></div>"
              "<div id='mc-chatout'></div>")


def s_plat(r, ctx) -> str:
    rows = []
    for p in M.PROVIDERS:
        live, why = M.Adapter(p).available()
        rows.append((e(p), "✓ live" if live else "not connected",
                     e(why)[:110]))
    ptab = (table(("platform", "status", "detail"), rows)
            + "<div class='mc-form'>"
              "<button class='mc-btn' onclick=\"nav('map')\">Connect a "
              "platform (Connect board)</button>"
              "<button class='mc-btn' onclick='runAds()'>Pull Google Ads "
              "data</button>"
              "<button class='mc-btn' onclick='runInterlock()'>Rebuild "
              "cross-channel</button>"
              "<button class='mc-btn' onclick='openEcon()'>Set unit "
              "economics</button></div>"
              "<p class='mc-note'>Keys are entered on the Connect board "
              "only. Nothing here reads or shows a credential; the screen "
              "flips live the moment the connector authorises.</p>")
    caps = table(("platform",) + M.OBJECTIVES,
                 [tuple([row["provider"]]
                        + [(e(row[o]) if row.get(o) else "cannot")
                           for o in M.OBJECTIVES])
                  for row in M.capability_table()])
    # THE MANIFEST: API versions verified against official docs, drift
    # named, unknowns counted instead of papered over.
    import content_engine_media_manifest as MAN
    drift = MAN.version_drift()
    dtab = table(("platform", "coded", "current (verified)", "drift",
                  "note"),
                 [(x["provider"], x["coded"], x["current"],
                   "YES" if x["drift"] else "no", x["note"][:100])
                  for x in drift])
    unk = {p: len(MAN.capabilities(p).get("unknowns") or [])
           for p in ("google", "meta", "linkedin", "tiktok")}
    dnote = ("<p class='mc-note'>capability fields still marked UNKNOWN - "
             "REQUIRES VERIFICATION: "
             + ", ".join(f"{p}: {n}" for p, n in unk.items())
             + ". An unknown stays an unknown until it is verified against "
               "official docs; nothing here is remembered from training "
               "data and presented as current.</p>")
    # AI action levels, spec section 33
    ai = {}
    try:
        import content_engine_api as A
        import content_engine_media_orders as MO
        ai = MO.get_ai_levels(A.get_store())
    except Exception:
        pass
    aitab = (table(("agent action", "level"),
                   sorted(ai.items()))
             + "<div class='mc-form'>"
               "<label>Action<select id='mc-ailvl-act'>"
             + "".join(f"<option>{e(a)}</option>" for a in sorted(ai))
             + "</select></label>"
               "<label>Level<select id='mc-ailvl-lvl'>"
               "<option>OBSERVE_ONLY</option><option>RECOMMEND</option>"
               "<option>REQUIRE_APPROVAL</option>"
               "<option>AUTO_EXECUTE</option></select></label>"
               "<button class='mc-btn' onclick=\"mcPost('/mediaos/ai-level',"
               "{action:mcV('mc-ailvl-act'),level:mcV('mc-ailvl-lvl')},"
               "this)\">Set level</button>"
               "<p class='mc-note'>every default is REQUIRE_APPROVAL; "
               "CREATE_CAMPAIGN is capped there permanently, and an "
               "AUTO_EXECUTE budget change is still refused past 50 "
               "percent</p></div>"
             if ai else "<p class='mc-empty'>levels unavailable without "
                        "the store</p>")
    out = (card("Connections", ptab)
           + card("What each platform can do", caps,
                  "three answers exist: yes, no, and not connected")
           + card("API versions: coded vs verified current", dtab + dnote,
                  "verified against official docs on 2026-08-09")
           + card("AI action permission levels", aitab,
                  "spec section 33: per action, raised by you"))
    # THE GTM AUDIT BOARD, rehomed. gtmDraft existed as a handler with no
    # board calling it, which is a dead wire wearing a function name.
    g = _D(ctx.get("gtm_audit"))
    if g.get("ready"):
        rows = []
        for kind, items in (("missing", g.get("missing")),
                            ("paused", g.get("paused")),
                            ("silent", g.get("silent"))):
            for name in _L(items)[:8]:
                nm = name if isinstance(name, str) else \
                    _D(name).get("name") or str(name)
                rows.append((e(nm), kind,
                             f"<button class='mc-btn' onclick=\"gtmDraft("
                             f"'{e(nm)}',this)\">Draft the tag</button>"))
        gtm = (table(("tag", "state", "fix"), rows,
                     "every required tag exists, is live, and has fired "
                     "recently")
               + "<button class='mc-btn' onclick=\"act('/gtm/audit')\">"
                 "Re-audit Tag Manager</button>")
    else:
        gtm = ("<p class='mc-empty'>Tag Manager is not granted yet; the "
               "audit runs the day it is. Fields are on the Connect "
               "board.</p>"
               "<button class='mc-btn' onclick=\"act('/gtm/audit')\">"
               "Audit Tag Manager</button>")
    out += card("Tag Manager audit", gtm,
                "missing, paused and silent tags, each with its one-click "
                "draft")
    out += card("The media buyer", _native_buyer(r, ctx),
                "draft with the agent, then discuss it; same endpoints, "
                "drawn in this design")
    out += card("Website tracking (GA4 / Search Console)",
                _native_tracking(ctx),
                "your own analytics, redrawn here rather than injected "
                "as the old boards")
    return out


#: Ad Manager room -> canonical provider. Facebook and Instagram are both
#: rooms of Meta; one table so the launch form cannot disagree with the
#: adapter about who it is talking to.
ROOM_PROVIDER = {"google": "google", "facebook": "meta",
                 "instagram": "meta", "linkedin": "linkedin",
                 "tiktok": "tiktok"}


def _room_ops(r, ctx, pid) -> str:
    """The controls that make a platform room a ROOM and not a museum:
    launch from here, upload content here, send the agent from here,
    monitor here."""
    prov = ROOM_PROVIDER[pid]
    live, why = M.Adapter(prov).available()
    objs = "".join(f"<option value='{e(o)}'>{e(o)}</option>"
                   for o in M.OBJECTIVES if M.supports(prov, o)["ok"])
    auds = "".join(f"<option value='{e(a.get('id'))}'>{e(a.get('name'))}"
                   f"</option>" for a in r.all("audiences")[:50]) \
        or "<option value=''>no audience yet (platform chooses)</option>"
    cres = "".join(f"<option value='{e(x.get('id'))}'>{e(x.get('name'))}"
                   f"</option>" for x in r.all("creatives")[:50]) \
        or "<option value=''>no creative yet - upload below</option>"
    P = f"mc-{pid}"
    launch = (
        f"<p class='mc-wq'>Launch on {e(pid.title())}</p>"
        f"<div class='mc-form'>"
        f"<label>Name<input id='{P}-name' "
        f"placeholder='{e(pid.title())} leads DE'></label>"
        f"<label>Objective<select id='{P}-obj'>{objs}</select></label>"
        f"<label>Budget<input id='{P}-bud' type='number' min='0' "
        f"placeholder='30'></label>"
        f"<label>Type<select id='{P}-bt'><option>DAILY</option>"
        f"<option>LIFETIME</option></select></label>"
        f"<label>Audience<select id='{P}-aud'>{auds}</select></label>"
        f"<label>Creative<select id='{P}-cre'>{cres}</select></label>"
        f"<label>Landing<input id='{P}-lp' "
        f"placeholder='https://landing.page'></label>"
        f"<button class='mc-btn' onclick=\"mcQuick('{pid}',false,this)\">"
        f"Create + pre-flight</button>"
        f"<button class='mc-btn mc-go' onclick=\"mcQuick('{pid}',true,this)"
        f"\">Create + queue launch</button></div>"
        f"<p class='mc-note'>"
        + e(("launch queues an order behind your approval tier"
             if live else
             f"{why}; the draft saves now and the launch order holds "
             f"until the key exists")) + "</p>")
    upload = (
        f"<p class='mc-wq'>Upload content</p>"
        f"<div class='mc-form'>"
        f"<label>File (image/video)<input id='{P}-file' type='file' "
        f"accept='.png,.jpg,.jpeg,.gif,.webp,.mp4,.mov,.webm'></label>"
        f"<label>Name<input id='{P}-cname'></label>"
        f"<label>Headline<input id='{P}-chead'></label>"
        f"<label>Primary text<input id='{P}-ctext'></label>"
        f"<label>CTA<input id='{P}-ccta' placeholder='Book a call'>"
        f"</label>"
        f"<label>Angle<input id='{P}-cangle' placeholder='pain-point'>"
        f"</label>"
        f"<button class='mc-btn mc-go' onclick=\"mcUpload('{pid}',this)\">"
        f"Upload + save to library</button></div>"
        f"<p class='mc-note'>the file lands in the asset store "
        f"(hash-named, {MC.ASSET_MAX_MB} MB cap), the creative in the one "
        f"library, publishable as v1 and attachable from any room</p>")
    agent = (
        f"<p class='mc-wq'>Or send the agent</p>"
        f"<div class='mc-form'>"
        f"<button class='mc-btn' onclick=\"mcAgentContent('{prov}',this)\">"
        f"Agent: draft campaign + content for {e(pid.title())}</button>"
        f"</div>"
        f"<p class='mc-note'>runs the EXISTING media buyer once; its copy "
        f"lands as unpublished drafts in the library and the campaign "
        f"card waits for your approval. It cannot publish.</p>")
    mine = [c for c in r.all("media_campaigns")
            if c.get("provider") == prov]
    spend_by_day = {}
    for m in MF.rollup(r, provider=prov)["rows"]:
        spend_by_day[m["bucket"]] = (spend_by_day.get(m["bucket"], 0.0)
                                     + float(m["spend"] or 0))
    monitor = (
        f"<p class='mc-wq'>Monitor {e(pid.title())}</p>"
        + table(("campaign", "state", "budget"),
                [(c.get("name"), c.get("state"),
                  _money(c.get("budget_amount"), c.get("currency") or "EUR"))
                 for c in mine[:8]],
                f"no campaign in the canonical model for {prov} yet")
        + (chart(sorted(spend_by_day.items()),
                 title=f"{pid.title()} spend per day")
           if len(spend_by_day) >= 2 else
           f"<p class='mc-empty'>the {e(pid)} spend chart draws after two "
           f"days of measured data (pull or sync)</p>"))
    return ("<div class='mc-roomops'>" + launch + upload + agent + monitor
            + "</div>")


def s_adman(r, ctx) -> str:
    """The five-platform Ad Manager: Google, Meta (Facebook + Instagram),
    LinkedIn, TikTok, YouTube inside Google. The VIEW is the existing
    module, mounted; the OPS STRIP under each room is new: launch from
    here, upload content here, send the agent from here, monitor here."""
    import content_engine_media_platforms as MPL
    ads = ctx.get("ads") or {}
    bridge = ("<style>.mc-a3{--pap:#F9FAFB;--card:#FFFFFF;"
              "--ln:#E5E7EB;--tx:#111827;"
              "--dm:#4B5563;--ft:#6B7280;"
              "--ac:#2563EB;--warnc:#D97706;"
              "--okc:#16A34A;--badbg:rgba(255,107,147,.09);"
              "--warnbg:rgba(245,177,76,.09);--okbg:rgba(63,217,139,.09);"
              "--hov:rgba(76,141,255,.07)}" + MPL.CSS + "</style>")
    # the module's own pane loop, with the ops strip INSIDE each room so
    # switching platform switches the controls with it
    panes = "".join(
        "<div class='a3plat' id='a3plat-" + pid + "'"
        + ("" if pid == "google" else " style='display:none'") + ">"
        + MPL.platform_screen(pid, ads) + _room_ops(r, ctx, pid)
        + "</div>"
        for pid in MPL.ORDER)
    return (bridge + MPL.JS
            + "<div class='mc-a3'>" + MPL.switcher("google") + panes
            + "</div>"
            + "<p class='mc-note'>a platform without its key shows its "
              "SAMPLE and says so; adding the key on the Connect board "
              "flips it live with no rebuild</p>")


def s_intel(r, ctx) -> str:
    """Search Terms, Keywords, Bidding, Budget & Pacing, Landing pages.
    Every board reads the ads snapshot; unconnected states say why."""
    import content_engine_ads as ADS
    terms_d = _D(ctx.get("terms"))
    terms = _L(terms_d.get("terms"))
    if terms:
        w = ADS.waste(terms)
        ttab = (table(("search term", "clicks", "cost", "conversions"),
                      [(t.get("term"), _n(t.get("clicks")),
                        _n(t.get("cost")), _n(t.get("conversions")))
                       for t in terms[:20]])
                + f"<p class='mc-note'>wasted spend "
                  f"{_n(w.get('wasted_spend'))} "
                  f"({_n(w.get('wasted_pct'))}% of term spend); negative "
                  f"candidates: "
                + (e(", ".join(w.get("negative_candidates") or [])[:160])
                   or "none") + "</p>")
    else:
        ttab = _off(terms_d, "search terms")
    kw_d = _D(ctx.get("kw"))
    kws = _L(kw_d.get("keywords"))
    ktab = (table(("keyword", "match", "QS", "clicks", "cost"),
                  [(k.get("text") or k.get("keyword"), k.get("match_type"),
                    _n(k.get("qs") or k.get("quality_score"),
                       "not scored"), _n(k.get("clicks")),
                    _n(k.get("cost"))) for k in kws[:20]])
            if kws else _off(kw_d, "keywords"))
    tgt = _D(ctx.get("targets"))
    trows = [(k.replace("_", " "), _n(tgt.get(k)))
             for k in ("target_cpa_lead", "target_cpa_consult",
                       "target_cpa_client", "break_even_cpa_client",
                       "target_roas") if k in tgt]
    bid = _L(ctx.get("bid_advice"))
    btab = ((table(("what", "value"), trows,
                   "unit economics not set; press 'Set unit economics'")
             if trows else
             "<p class='mc-empty'>unit economics not set, so no CPC can "
             "be judged; press 'Set unit economics'</p>")
            + (table(("campaign", "advice"),
                     [(b.get("campaign"), (b.get("advice") or "ok")[:110])
                      for b in bid[:10]]) if bid else ""))
    isr = _L(ctx.get("is_rows"))
    istab = (table(("campaign", "verdict", "action"),
                   [(x.get("campaign"), x.get("verdict"),
                     (x.get("action") or "")[:100]) for x in isr[:10]])
             if isr else
             "<p class='mc-empty'>no impression-share rows yet; they "
             "arrive with the Google pull</p>")
    pac = _D(ctx.get("pacing"))
    if pac.get("ready"):
        ptab = (chart_bars([("spent so far", pac.get("spend")),
                            ("projected month-end", pac.get("projected")),
                            ("month budget", pac.get("month_budget"))],
                           title="Budget pace")
                + f"<p class='mc-note'>pace {_n(pac.get('pace_pct'))}% of "
                  f"budget: {e(pac.get('status') or '')}</p>")
    else:
        ptab = ("<p class='mc-empty'>pacing needs a Google pull with "
                "campaign budgets on it</p>")
    ads_d = _D(ctx.get("ad_status"))
    dis = _L(ads_d.get("disapproved"))
    ltab = ((table(("campaign", "issue"),
                   [(d.get("campaign"), (d.get("reason")
                                         or "disapproved")[:90])
                    for d in dis[:10]]) if dis else
             "<p class='mc-note'>no disapproved ad on record</p>")
            if ads_d.get("connected") else _off(ads_d, "ad status"))
    return (card("Search Terms: what people actually typed", ttab)
            + card("Keywords", ktab)
            + card("Bidding, judged against YOUR economics", btab,
                   "a CPC is not high or low until the margin says so")
            + card("Impression share: budget problem or quality problem",
                   istab)
            + card("Budget & Pacing", ptab)
            + card("Landing pages & disapprovals", ltab))


def s_cross(r, ctx) -> str:
    """Paid and organic in ONE picture: the interlock and the funnel."""
    inter = _D(ctx.get("interlock"))
    burn = inter.get("burn") or inter.get("overlap") or []
    if isinstance(burn, dict):
        burn = list(burn.values())
    burn = [b for b in _L(burn) if isinstance(b, (dict, str))]
    btab = (table(("term you already rank for", "organic position"),
                  [((b.get("term") if isinstance(b, dict) else str(b)),
                    (b.get("position", "<=3")
                     if isinstance(b, dict) else "<=3"))
                   for b in burn[:15]])
            + "<p class='mc-note'>every row is money paid for a click the "
              "organic result would have taken free; the agent drafts a "
              "negative-keyword order for each</p>"
            if burn else
            "<p class='mc-empty'>no paid-vs-organic overlap on record. It "
            "computes from a Google Ads pull plus Search Console; press "
            "'Rebuild interlock'.</p>")
    flows = _L(ctx.get("funnel"))
    if flows:
        # flows are (source, target, value); draw the stages in order
        stages, seen = [], set()
        for src, tgtt, v in [tuple(f) for f in flows if len(_L(f)) == 3]:
            for name, val in ((src, None), (tgtt, v)):
                if name not in seen and val is not None:
                    stages.append((name, val))
                    seen.add(name)
        fhtml = chart_funnel(stages, title="Paid + organic funnel")
    else:
        a = _D(ctx.get("ads"))
        stages = [("Ad impressions", a.get("impressions")),
                  ("Ad clicks", a.get("clicks")),
                  ("Conversions", a.get("conversions"))]
        stages = [(k, v) for k, v in stages if v]
        fhtml = (chart_funnel(stages) if len(stages) >= 2 else
                 "<p class='mc-empty'>the funnel draws when the pull "
                 "carries impressions and clicks; nothing is invented to "
                 "fill it</p>")
    cac = _D(inter.get("cac"))
    ctab = (table(("stage", "count"),
                  [(k, _n(cac.get(k))) for k in
                   ("leads", "bookings", "customers") if cac.get(k)])
            if any(cac.get(k) for k in ("leads", "bookings", "customers"))
            else "<p class='mc-empty'>no lead-to-customer counts in the "
                 "cross-channel snapshot yet</p>")
    return (card("Cross-channel: terms you pay for and already win free",
                 btab)
            + card("The funnel", fhtml,
                   "paid and organic in one picture, from whatever is real")
            + card("After the click", ctab))


def s_comp(r, ctx) -> str:
    """Competition and research: intel, GEO, markets, recommendations."""
    ci = _D(ctx.get("competitor_intel"))
    rows = _L(ci.get("competitors") or ci.get("rows"))
    citab = (table(("competitor", "seen"),
                   [((c.get("name") or c.get("domain") or str(c)[:40]),
                     (c.get("summary") or c.get("note") or "")[:110])
                    for c in rows[:10] if isinstance(c, (dict, str))])
             if rows else
             "<p class='mc-empty'>no competitor intel on record. The "
             "research agent writes it with sources; nothing is invented "
             "here.</p>")
    geo = _D(ctx.get("geo"))
    grows = _L(geo.get("markets") or geo.get("rows"))
    gtab = (table(("market", "note"),
                  [((g.get("market") or g.get("name") or str(g)[:30]),
                    (g.get("note") or g.get("verdict") or "")[:110])
                   for g in grows[:10] if isinstance(g, (dict, str))])
            if grows else
            "<p class='mc-empty'>no GEO market audit yet</p>")
    mk = _L(ctx.get("markets"))
    # A DICT IS NOT A SENTENCE. This printed str(m) over a list of market
    # records, so the board showed raw Python - {'market': 'Germany',
    # 'verdict': ...} - over the most useful judgement in the section:
    # which markets you can reach organically and which are paid-only.
    if mk and all(isinstance(m, dict) for m in mk):
        mtab = table(
            ("market", "language", "organic pages", "impressions",
             "what that means"),
            [(e(str(m.get("market") or m.get("name") or "")),
              e(str(m.get("language") or "")),
              _n(m.get("organic_pages")),
              _n(m.get("organic_impressions")),
              e(str(m.get("verdict") or m.get("note") or "")[:120]))
             for m in mk[:12]],
            "no markets recorded in the cross-channel snapshot")
        _paid_only = [str(m.get("market") or "") for m in mk
                      if m.get("paid_is_only_lever")]
        if _paid_only:
            mtab += ("<p class='mc-note'>Paid is the only lever in "
                     + e(", ".join(_paid_only))
                     + ": there is no content in that language yet, so "
                       "organic cannot reach those buyers today.</p>")
    elif mk:
        mtab = ("<p class='mc-note'>markets in play: "
                + e(", ".join(str(m) for m in mk[:10])) + "</p>")
    else:
        mtab = ("<p class='mc-empty'>no markets recorded in the "
                "cross-channel snapshot</p>")
    recs_d = _D(ctx.get("recs"))
    recs = _L(recs_d.get("recommendations"))
    rtab = (table(("google recommends", "note"),
                  [((x.get("type") or "")[:40],
                    (x.get("description") or "")[:110])
                   for x in recs[:10]])
            + "<p class='mc-note'>Google's recommendations optimise "
              "Google's revenue as well as yours; each becomes an order "
              "only if a rule agrees</p>"
            if recs else _off(recs_d, "recommendations"))
    chg_d = _D(ctx.get("changes"))
    chg = _L(chg_d.get("changes"))
    htab = (table(("when", "what changed"),
                  [((x.get("at") or "")[:16],
                    (x.get("summary") or x.get("change") or "")[:110])
                   for x in chg[:10]])
            if chg else _off(chg_d, "change history"))
    return (card("Competition", citab)
            + card("GEO market research", gtab + mtab)
            + card("Google's recommendations, treated as claims", rtab)
            + card("Account change history", htab))


# ---------------------------------------------------------------------------
# ASSEMBLY
# ---------------------------------------------------------------------------
def build_panels(r, ctx) -> dict:
    makers = {"cmd": lambda: s_cmd(r, ctx),
              "camps": lambda: s_camps(r, ctx),
              "wiz": lambda: s_wiz(r, ctx),
              "launch": lambda: s_launch(r, ctx),
              "adman": lambda: s_adman(r, ctx),
              "plan": lambda: s_plan(r, ctx),
              "creat": lambda: s_creat(r, ctx),
              "aud": lambda: s_aud(r, ctx),
              "alx": lambda: s_alx(r, ctx),
              "intel": lambda: s_intel(r, ctx),
              "anom": lambda: s_anom(r, ctx),
              "cross": lambda: s_cross(r, ctx),
              "comp": lambda: s_comp(r, ctx),
              "plat": lambda: s_plat(r, ctx)}
    out = {}
    for tid, _i, label, _q in SCREENS:
        try:
            out[tid] = makers[tid]()
        except Exception as ex:      # a broken screen admits it, never blanks
            log.exception("media screen %s failed", tid)
            out[tid] = (f"<div class='mc-card'><p class='mc-ct'>{e(label)}"
                        f"</p><p class='mc-empty'>this screen could not be "
                        f"drawn: {e(type(ex).__name__)}: {e(str(ex)[:120])}"
                        f"</p></div>")
    return out


def section(ctx) -> str:
    """The whole Media Buying OS section for the assembled dashboard."""
    ctx = dict(ctx or {})
    r = None
    try:
        import content_engine_api as A
        r = M.repo(A.get_store())
    except Exception as ex:
        log.warning("media center has no repo: %s", ex)
    if r is None:
        panels = {tid: ("<div class='mc-card'><p class='mc-ct'>"
                        + e(label) + "</p><p class='mc-empty'>the store is "
                        "not reachable, so this screen has nothing true to "
                        "show</p></div>")
                  for tid, _i, label, _q in SCREENS}
        panels["plat"] = ("<p class='mc-empty'>the store is not "
                          "reachable, so nothing true can be shown</p>")
    else:
        panels = build_panels(r, ctx)
    nav = "".join(
        f"<button class='mc-tab{' mc-on' if i == 0 else ''}' "
        f"id='mc-tab-{tid}' onclick=\"mcTab('{tid}')\">"
        f"<span>{icon}</span>{e(label)}<i>{e(q)}</i></button>"
        for i, (tid, icon, label, q) in enumerate(SCREENS))
    body = "".join(
        f"<div class='mc-panel{' mc-on' if i == 0 else ''}' "
        f"id='mc-panel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _i2, _l, _q) in enumerate(SCREENS))
    return ("<div class='mc-root'>" + CSS + JS
            + f"<div class='mc-tabs'>{nav}</div>" + body + "</div>")


CSS = """<style>
.mc-root{--mc-ln:#E5E7EB;--mc-mut:#4B5563;
--mc-ink:#111827;--mc-card:#FFFFFF;
--mc-go:#2563EB;font-size:13px;color:#111827;
--pap:#F7F8FA;--card:#FFFFFF;--ln:#E5E7EB;--tx:#111827;--dm:#4B5563;
--ft:#6B7280;--ac:#2563EB;--okc:#16A34A;--warnc:#D97706;--bad:#DC2626}
.mc-root{display:grid;grid-template-columns:236px 1fr;gap:14px;
align-items:start;background:#F7F8FA;border-radius:12px;padding:14px}
.mc-tabs{display:flex;flex-direction:column;gap:5px;margin:0;
position:sticky;top:8px;background:#FFFFFF;border:1px solid #E5E7EB;
border-radius:10px;padding:8px}
@media (max-width:900px){.mc-root{grid-template-columns:1fr}
.mc-tabs{position:static;flex-direction:row;flex-wrap:wrap}}
.mc-tab{display:flex;flex-direction:column;align-items:flex-start;gap:2px;
background:transparent;border:1px solid transparent;border-radius:8px;
padding:7px 11px;color:var(--mc-mut);cursor:pointer;width:100%;
text-align:left;font:inherit;font-size:13px}
.mc-tab:hover{background:#F9FAFB}
.mc-tab i{font-style:normal;font-size:10px;opacity:.65}
.mc-tab.mc-on{color:var(--mc-go);background:rgba(37,99,235,.08);border-color:transparent;font-weight:600}
.mc-panel{display:none}.mc-panel.mc-on{display:block}
.mc-card{background:var(--mc-card);border:1px solid var(--mc-ln);
border-radius:11px;padding:13px 15px;margin:0 0 12px}
.mc-ct{font-weight:700;color:var(--mc-ink);margin:0 0 2px}
.mc-cs{color:var(--mc-mut);font-size:11px;margin:0 0 8px}
.mc-empty{color:var(--mc-mut);font-size:12px;margin:6px 0}
.mc-note{color:var(--mc-mut);font-size:11px;margin:7px 0 0}
.mc-kpis{display:flex;flex-wrap:wrap;gap:10px}
.mc-kpi{display:flex;flex-direction:column;background:rgba(76,141,255,.06);
border:1px solid var(--mc-ln);border-radius:9px;padding:9px 13px;
min-width:110px}
.mc-kpi b{font-size:18px;font-variant-numeric:tabular-nums;
color:var(--mc-ink)}
.mc-kpi span{font-size:10px;color:var(--mc-mut);text-transform:uppercase;
letter-spacing:.4px}
.mc-kpi i{font-style:normal;font-size:10px;color:var(--mc-mut)}
.mc-scroll{overflow-x:auto}
.mc-tbl{border-collapse:collapse;width:100%;font-size:12px}
.mc-tbl th{color:var(--mc-mut);text-transform:uppercase;font-size:10px;
letter-spacing:.4px;text-align:left;padding:5px 9px;
border-bottom:1px solid var(--mc-ln)}
.mc-tbl td{padding:6px 9px;border-bottom:1px solid var(--mc-ln);
color:var(--mc-ink);font-variant-numeric:tabular-nums;
vertical-align:top}
.mc-btn{background:none;border:1px solid var(--mc-ln);border-radius:7px;
color:var(--mc-ink);padding:4px 10px;font-size:12px;cursor:pointer;
margin:2px 4px 2px 0}
.mc-btn.mc-go{border-color:var(--mc-go);color:var(--mc-go)}
.mc-form{display:flex;flex-wrap:wrap;gap:9px;align-items:flex-end}
.mc-form label{display:flex;flex-direction:column;gap:3px;font-size:11px;
color:var(--mc-mut)}
.mc-form input,.mc-form select,.mc-form textarea{background:rgba(0,0,0,.25);
border:1px solid var(--mc-ln);border-radius:7px;color:var(--mc-ink);
padding:6px 9px;font-size:12px;min-width:130px}
.mc-steps{display:flex;flex-wrap:wrap;gap:9px}
.mc-step{display:flex;gap:8px;align-items:flex-start;
border:1px solid var(--mc-ln);border-radius:9px;padding:8px 11px;
min-width:170px}
.mc-step b{color:var(--mc-go)}
.mc-step p{margin:0;color:var(--mc-ink);font-size:12px}
.mc-step span{color:var(--mc-mut);font-size:10px}
.mc-check{display:flex;gap:7px;align-items:baseline;font-size:12px;
padding:3px 0;color:var(--mc-ink)}
.mc-check span{color:var(--mc-mut);font-size:11px}
.mc-check.mc-error{color:#FF6B93}.mc-check.mc-warning{color:#F5B14C}
.mc-check.mc-ok{color:#3FD98B}
.mc-grain{display:none}.mc-grain.mc-on{display:block}
.mc-bigs30{color:var(--mc-mut);font-size:10px;letter-spacing:1.2px;
text-transform:uppercase;margin:4px 0 8px}
.mc-bigrow{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 14px}
.mc-big{display:flex;flex-direction:column;background:var(--mc-card);
border:1px solid var(--mc-ln);border-radius:11px;padding:12px 16px;
min-width:150px;flex:1}
.mc-big b{font-size:26px;font-weight:700;color:var(--mc-ink);
font-variant-numeric:tabular-nums;line-height:1.15}
.mc-bigk{font-size:10px;color:var(--mc-mut);text-transform:uppercase;
letter-spacing:.6px}
.mc-bigs{font-size:10px;color:var(--mc-mut);min-height:12px}
.mc-statrow{display:flex;flex-wrap:wrap;gap:10px}
.mc-stat{display:flex;align-items:baseline;gap:7px;
border:1px solid var(--mc-ln);border-radius:9px;padding:7px 12px}
.mc-stat b{font-size:19px;color:var(--mc-ink);
font-variant-numeric:tabular-nums}
.mc-stat span{font-size:11px;color:var(--mc-mut)}
.mc-act{display:flex;gap:12px;align-items:flex-start;
border:1px solid var(--mc-ln);border-left-width:3px;border-radius:9px;
padding:10px 13px;margin:0 0 8px}
.mc-act-up{border-left-color:#3FD98B}.mc-act-down{border-left-color:#F5B14C}
.mc-act-warn{border-left-color:#FF6B93}.mc-act-make{border-left-color:var(--mc-go)}
.mc-glyph{font-size:21px;line-height:1;margin-top:2px}
.mc-act-up .mc-glyph{color:#3FD98B}.mc-act-down .mc-glyph{color:#F5B14C}
.mc-act-warn .mc-glyph{color:#FF6B93}.mc-act-make .mc-glyph{color:var(--mc-go)}
.mc-actbody{display:flex;flex-direction:column;gap:2px;flex:1}
.mc-actbody b{color:var(--mc-ink);font-size:13px}
.mc-actbody span{color:var(--mc-mut);font-size:11px}
.mc-actbtns{display:flex;flex-direction:column;gap:4px}
.mc-wrail{display:flex;gap:6px;margin:2px 0 8px}
.mc-dot{width:28px;height:28px;border-radius:50%;
border:1px solid var(--mc-ln);background:none;color:var(--mc-mut);
cursor:pointer;font-size:12px}
.mc-dot.mc-don{border-color:#3FD98B;color:#3FD98B}
.mc-wstep{display:none;border:1px solid var(--mc-ln);border-radius:11px;
padding:13px 16px;margin:6px 0}
.mc-wstep.mc-on{display:block}
.mc-wtitle{font-size:11px;letter-spacing:1px;color:var(--mc-go);
text-transform:uppercase;margin:0 0 2px;font-weight:700}
.mc-wq{color:var(--mc-ink);font-size:12px;font-weight:600;margin:10px 0 6px}
.mc-wnav{display:flex;gap:8px;margin-top:12px;align-items:center;
flex-wrap:wrap}
.mc-radios{display:flex;flex-direction:column;gap:6px;margin:4px 0}
.mc-radio{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap;
border:1px solid var(--mc-ln);border-radius:9px;padding:8px 12px;
cursor:pointer;color:var(--mc-ink);font-size:13px}
.mc-radio i{font-style:normal;font-size:11px;color:#3FD98B}
.mc-radio span{font-size:11px;color:var(--mc-mut);width:100%}
.mc-alloc{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
margin:0 0 7px}
.mc-alloc b{width:70px;color:var(--mc-ink);font-size:12px}
.mc-alloc i{font-style:normal;font-size:12px;color:var(--mc-ink);
font-variant-numeric:tabular-nums}
.mc-alloc p{width:100%;margin:0;color:var(--mc-mut);font-size:11px}
.mc-allocbar{flex:1;min-width:120px;height:8px;border-radius:5px;
background:rgba(255,255,255,.06);overflow:hidden}
.mc-allocbar span{display:block;height:100%;background:var(--mc-go)}
.mc-doc{border:1px solid var(--mc-ln);border-radius:11px;
padding:14px 17px;margin:0 0 12px;background:var(--mc-card)}
.mc-doctitle{font-size:11px;letter-spacing:1.4px;color:var(--mc-mut);
margin:0 0 9px;font-weight:700}
.mc-docrow{display:flex;justify-content:space-between;gap:14px;
border-bottom:1px solid var(--mc-ln);padding:5px 0;font-size:13px}
.mc-docrow span{color:var(--mc-mut)}
.mc-docrow b{color:var(--mc-ink);text-align:right;
font-variant-numeric:tabular-nums}
.mc-assume{margin:2px 0 0 16px;padding:0;color:var(--mc-mut);
font-size:11px}
.mc-detail{display:none;border:1px solid var(--mc-go);border-radius:11px;
padding:12px;margin:8px 0}
.mc-detail.mc-on{display:block}
.mc-link{color:var(--mc-go);cursor:pointer;text-decoration:underline}
.mc-preview{display:none;border:1px dashed var(--mc-ln);border-radius:9px;
padding:12px 14px;margin:9px 0;max-width:420px}
.mc-preview.mc-on{display:block}
.mc-prevtag{display:block;font-size:9px;letter-spacing:1px;
color:var(--mc-mut);text-transform:uppercase;margin-bottom:5px}
.mc-preview b{display:block;color:var(--mc-ink);font-size:14px}
.mc-preview p{color:var(--mc-mut);font-size:12px;margin:3px 0}
.mc-preview i{display:block;font-style:normal;color:var(--mc-go);
font-size:10px;margin:0 0 6px}
.mc-chrow{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 12px}
.mc-chart{flex:1;min-width:280px;border:1px solid var(--mc-ln);
border-radius:11px;padding:10px 13px;background:var(--mc-card);
margin:0 0 8px}
.mc-chart svg{width:100%;height:100px;display:block}
.mc-chtitle{display:block;font-size:10px;letter-spacing:.8px;
text-transform:uppercase;color:var(--mc-mut);margin:0 0 4px}
.mc-chmeta{display:block;font-size:10px;color:var(--mc-mut);margin-top:3px;
font-variant-numeric:tabular-nums}
.mc-hbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;
margin:0 0 6px}
.mc-hbar span:first-child{width:150px;color:var(--mc-ink);font-size:11px}
.mc-hbar i{font-style:normal;color:var(--mc-ink);font-size:11px;
font-variant-numeric:tabular-nums}
.mc-hbar p{width:100%;margin:0 0 0 159px;color:var(--mc-mut);font-size:10px}
.mc-hbtrack{flex:1;min-width:110px;height:9px;border-radius:5px;
background:rgba(17,24,39,.08);overflow:hidden}
.mc-hbtrack span{display:block;height:100%;background:var(--mc-go)}
.mc-roomops{border:1px solid var(--mc-ln);border-top:2px solid var(--mc-go);
border-radius:11px;padding:12px 15px;margin:12px 0;
background:var(--mc-card)}
.mc-roomops input[type=file]{border:none;background:none;padding:4px 0}
/* the agent command band: markup shared with the SEO section, styles local */
.mc-root .s3band{display:flex;gap:16px;align-items:center;flex-wrap:wrap;
padding:13px 16px;border:1px solid #E5E7EB;border-left:3px solid #2563EB;
border-radius:11px;background:#FFFFFF;margin:0 0 14px}
.mc-root .s3who{flex:1;min-width:240px}
.mc-root .s3k{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;
letter-spacing:.13em;text-transform:uppercase;color:#6B7280;margin:0 0 4px}
.mc-root .s3state{margin:0;font-size:13px}
.mc-root .s3sub{margin:3px 0 0;font-size:11.5px;color:#6B7280;
line-height:1.5;max-width:52ch}
.mc-root .s3cmds{display:flex;gap:8px;flex-wrap:wrap}
.mc-root button.cta{display:inline-flex;align-items:center;gap:5px;
background:#FFFFFF;border:1px solid #E5E7EB;color:#111827;border-radius:9px;
padding:7px 13px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
.mc-root button.cta:hover{border-color:#2563EB}
.mc-root .cta.s3go{background:#2563EB;color:#FFFFFF;border-color:#2563EB}
.mc-root .s3ladder{display:flex;border:1px solid #E5E7EB;border-radius:8px;
overflow:hidden}
.mc-root .s3lvl{font-family:ui-monospace,Menlo,monospace;font-size:11px;
font-weight:700;padding:7px 12px;border:0;background:#FFFFFF;color:#6B7280;
cursor:pointer}
.mc-root .s3lvl.s3on{background:#2563EB;color:#FFFFFF}
</style>"""


JS = """<script>
/* The agent-band handlers live HERE now. The old media screens module
   defined them and it is gone; a button calling a function nobody defines
   is a dead control that looks alive, which is the worst kind. */
async function mediaAutoSet(level,btn){try{
var r=await fetch('/media/auto',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({level:level})});var j=await r.json();
toast((j&&(j.message||j.error))||('level '+level),j&&j.ok!==false);
if(j&&j.ok!==false){document.querySelectorAll('.s3lvl').forEach(
function(x){x.classList.remove('s3on');
if(x.textContent.toLowerCase().indexOf(level)===0)x.classList.add('s3on');});}}
catch(e){toast('could not reach the engine; the switch is unchanged',
false);}}
async function mediaOptimize(btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Judging\\u2026';}
try{var r=await fetch('/media/optimize',{method:'POST'});
var j=await r.json();toast((j&&j.message)||'ran',j&&j.ok!==false);}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
async function mediaApprove(id,btn){try{
var r=await fetch('/media/approve',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({id:id})});var j=await r.json();
toast((j&&j.message)||'approved',j&&j.ok!==false);
if(btn)btn.textContent='Approved';}catch(e){
toast('could not reach the engine',false);}}
async function mediaRun(id,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Executing\\u2026';}
try{var r=await fetch('/media/run-orders',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({ids:[id]})});var j=await r.json();
toast((j&&j.message)||'ran',j&&j.ok!==false);}catch(e){
toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
async function gtmDraft(name,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Drafting\\u2026';}
try{var r=await fetch('/gtm/draft',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({name:name})});var j=await r.json();
toast((j&&(j.result||j.message))||'drafted',j&&j.ok!==false);}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
function mcTab(t){document.querySelectorAll('.mc-panel').forEach(function(x){
x.classList.remove('mc-on');});
document.querySelectorAll('.mc-tab').forEach(function(x){
x.classList.remove('mc-on');});
var p=document.getElementById('mc-panel-'+t);if(p)p.classList.add('mc-on');
var b=document.getElementById('mc-tab-'+t);if(b)b.classList.add('mc-on');}
function mcStep(n){var steps=document.querySelectorAll('.mc-wstep');
if(n<0||n>=steps.length)return;
steps.forEach(function(x){x.classList.remove('mc-on');});
var el=document.getElementById('mc-wstep-'+n);if(el)el.classList.add('mc-on');}
function mcDetail(cid){var el=document.getElementById('mc-det-'+cid);
if(!el)return;var on=el.classList.contains('mc-on');
document.querySelectorAll('.mc-detail').forEach(function(x){
x.classList.remove('mc-on');});
if(!on){el.classList.add('mc-on');el.scrollIntoView({block:'nearest'});}}
function mcToggle(id){var el=document.getElementById(id);
if(el)el.classList.toggle('mc-on');}
function mcRadio(name){var el=document.querySelector(
'input[name="'+name+'"]:checked');return el?el.value:'';}
function mcGrain(g,btn){document.querySelectorAll('.mc-grain').forEach(
function(x){x.classList.remove('mc-on');});
var el=document.getElementById('mc-grain-'+g);if(el)el.classList.add('mc-on');
if(btn){btn.parentNode.querySelectorAll('.mc-btn').forEach(function(x){
x.classList.remove('mc-go');});btn.classList.add('mc-go');}}
async function mcPost(url,body,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}
try{var r=await fetch(url,{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify(body||{})});var j=await r.json();
toast((j&&(j.message||j.error))||'done',j&&j.ok!==false);
if(j&&j.ok!==false)setTimeout(function(){location.reload();},900);}
catch(e){toast('could not reach the engine; nothing changed',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
function mcV(id){var el=document.getElementById(id);
return el?el.value:'';}
function mcNewCampaign(btn){mcPost('/mediaos/campaign',{
name:mcV('mc-cname'),objective:mcRadio('mc-cobj'),kpi:mcV('mc-ckpi'),
provider:mcRadio('mc-cprov'),budget_type:mcV('mc-cbt'),
budget_amount:mcV('mc-cbud'),start_at:mcV('mc-cstart'),
end_at:mcV('mc-cend')},btn);}
function mcAttach(cid,btn){mcPost('/mediaos/attach',{campaign_id:cid,
audience_id:mcV('mc-aud-'+cid),creative_id:mcV('mc-cre-'+cid),
landing_page_url:mcV('mc-lp-'+cid)},btn);}
function mcLaunchAt(cid,btn,iid){mcPost('/mediaos/launch',{
campaign_id:cid,scheduled_at:mcV(iid||('mc-when-'+cid))},btn);}
function mcSavePlan(btn){mcPost('/mediaos/plan',{objective:mcV('mc-pobj'),
budget:mcV('mc-pbud'),kpi:mcV('mc-pkpi'),period_start:mcV('mc-pfrom'),
period_end:mcV('mc-pto'),target_cpa:mcV('mc-pcpa')},btn);}
async function mcSimulate(btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}
try{var r=await fetch('/mediaos/simulate',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({budget:mcV('mc-swhat'),
compare_to:mcV('mc-snow')})});var j=await r.json();
var out=document.getElementById('mc-simout');
if(out){if(j&&j.ok===false){out.innerHTML='<p class="mc-empty">'
+(j.message||'no answer')+'</p>';}else{
var h='<p class="mc-note">'+(j.message||'')+'</p>';
(j.scenarios||[]).forEach(function(s){var c=s.conversions||{};
h+='<p class="mc-note"><b>'+s.label+'</b> '+s.budget
+': conversions '+(c.low!=null?c.low+' to '+c.high:'no range')
+' ('+(s.band||'')+')</p>';});
h+='<p class="mc-empty">'+(j.caveat||'')+'</p>';out.innerHTML=h;}}}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
function mcNewCreative(btn,p){p=p||'mc-cr';
mcPost('/mediaos/creative',{
name:mcV(p+'name'),type:mcV(p+'type'),concept:mcV(p+'concept'),
angle:mcV(p+'angle'),hook:mcV(p+'hook'),persona:mcV(p+'persona'),
cta:mcV(p+'cta'),funnel_stage:mcV(p+'stage'),
headline:mcV(p+'head'),primary_text:mcV(p+'text'),publish:true},btn);}
function mcNewExperiment(btn){var ids=(mcV('mc-xids')||'').split(',')
.map(function(x){return x.trim();}).filter(Boolean);
mcPost('/mediaos/experiment',{name:mcV('mc-xname'),creative_ids:ids,
metric:mcV('mc-xmetric')},btn);}
function mcSavePolicy(btn){mcPost('/mediaos/policy',{
budget_change_auto_pct:mcV('mc-pol-bud'),
pause_auto_if_daily_spend_under:mcV('mc-pol-pause'),
negative_keyword:mcV('mc-pol-neg')},btn);}
function mcNewAudience(btn,p){p=p||'mc-a';var def={};
try{def=JSON.parse(mcV(p+'def')||'{}');}catch(e){
toast('the definition is not valid JSON; nothing was saved',false);return;}
mcPost('/mediaos/audience',{name:mcV(p+'name'),type:mcV(p+'type'),
definition:def},btn);}
window.mcChatOpen=function(jid){
var el=document.getElementById('mc-chatjob');if(el)el.value=jid;
toast('discussing draft '+jid,true);};
window.mcChatSend=async function(btn){
var job=mcV('mc-chatjob'),msg=mcV('mc-chatmsg');
if(!msg){toast('type a question first',false);return;}
var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Asking\u2026';}
try{var r=await fetch('/media/chat',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({job_id:job,message:msg})});var j=await r.json();
var out=document.getElementById('mc-chatout');
if(out)out.innerHTML="<p class='mc-note'><b>You:</b> "+mcEsc(msg)
+"</p><p class='mc-note'><b>Media buyer:</b> "
+mcEsc((j&&(j.reply||j.message))||'no reply')+"</p>";}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}};
function mcEsc(x){var d=document.createElement('div');
d.textContent=String(x==null?'':x);return d.innerHTML;}
var MC_ROOM_PROV={google:'google',facebook:'meta',instagram:'meta',
linkedin:'linkedin',tiktok:'tiktok'};
function mcQuick(pid,go,btn){var P='mc-'+pid;
mcPost('/mediaos/quicklaunch',{provider:MC_ROOM_PROV[pid]||pid,
name:mcV(P+'-name'),objective:mcV(P+'-obj'),
budget_amount:mcV(P+'-bud'),budget_type:mcV(P+'-bt'),
audience_id:mcV(P+'-aud'),creative_id:mcV(P+'-cre'),
landing_page_url:mcV(P+'-lp'),launch:!!go},btn);}
function mcUpload(pid,btn){var P='mc-'+pid;
var inp=document.getElementById(P+'-file');
var f=inp&&inp.files&&inp.files[0];
function save(url,ar){mcPost('/mediaos/creative',{name:mcV(P+'-cname'),
type:f?(f.type.indexOf('video')===0?'VIDEO':'IMAGE'):'TEXT',
asset_url:url||'',aspect_ratio:ar||'',headline:mcV(P+'-chead'),
primary_text:mcV(P+'-ctext'),cta:mcV(P+'-ccta'),
angle:mcV(P+'-cangle'),publish:true},btn);}
if(!f){save('');return;}
if(btn){btn.disabled=true;btn.textContent='Uploading\\u2026';}
var rd=new FileReader();
rd.onload=async function(){try{
var b64=String(rd.result).split(',')[1]||'';
var r=await fetch('/mediaos/asset',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({filename:f.name,data_b64:b64})});
var j=await r.json();
if(!j||j.ok===false){toast((j&&j.message)||'upload refused',false);
if(btn){btn.disabled=false;btn.textContent='Upload + save to library';}
return;}
toast(j.message||'uploaded',true);save(j.url,j.aspect_ratio);}
catch(e){toast('could not reach the engine; nothing uploaded',false);
if(btn){btn.disabled=false;btn.textContent='Upload + save to library';}}};
rd.readAsDataURL(f);}
async function mcAgentContent(prov,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Agent drafting\\u2026';}
try{var r=await fetch('/mediaos/agent-content',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({provider:prov})});var j=await r.json();
toast((j&&(j.message||j.error))||'done',j&&j.ok!==false);
if(j&&j.ok!==false)setTimeout(function(){location.reload();},1400);}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
async function mcMatrix(sel){try{var r=await fetch('/mediaos/matrix',{
method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({dimension:sel.value})});var j=await r.json();
var out=document.getElementById('mc-mout');
if(out)out.innerHTML='<p class="mc-note">'+((j&&j.message)||'')+'</p>';}
catch(e){toast('could not reach the engine',false);}}
</script>"""
