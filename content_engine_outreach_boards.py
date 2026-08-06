"""
content_engine_outreach_boards.py
============================================================================
LEADS & OUTREACH — 13 boards, 224 cards. Replaces two sections (Lead Machine,
Email & Outreach) that held 24 cards, rendered the same leads table twice and
drew the same funnel four different ways.

These two were not reports — they carry a working launch pad. Every interactive
block is carried over VERBATIM as pre-rendered HTML through ctx["live"], not
rebuilt: the outbox, the replies inbox, the leads table, the Maps sourcing
form. Send logic is untouched.

Five fabricated numbers are gone rather than restyled:
  - "Leads by source" hardcoded Prospeo to 0 and gave every lead to "Web search"
  - "Email quality" drew a 100% donut from a literal 100
  - "Volume by sender alias" assumed every email left from marketing@
  - the funnel skeletons' 100/55/28 bar widths read as conversion rates
  - "Deliverability guard" was three static tick marks over real machinery

Run offline self-check:  python content_engine_outreach_boards.py
============================================================================
"""
from __future__ import annotations

import re

from content_engine_seo_boards import (
    TEAL, VIOLET, BLUE, GREEN, AMBER, PINK, _H, _CH, _pct_color, _link, _rows,
    _linkrows, _donut, _split_donut, _trend, _spark, _hbars, _gauge, _score_gauge,
    _histogram, _heatmap, _riskmatrix, _statusgrid, _treemap, _waterfall, _delta,
    _viz, _vizcards, _head, _sub, _subnav, _slug, _CURRENT_BOARD, _TAB_CSS,
    BOARD_CTA, VISIBLE_CARDS,
)

BOARD_CTA.update({
    "Lead Manager": ("Source local leads", "seoTab('olaunch')"),
    "Launch Pad": ("Send today's batch", "act('/outreach/send_all')"),
    "Lead Sourcing": ("Source local leads", "seoTab('olaunch')"),
    "Lead Quality": ("Open Approvals", "nav('appr')"),
    "ICP & Scoring": ("Open BI", "nav('bi')"),
    "Territories": ("Open GEO", "nav('seo')"),
    "The Outbox": ("Send today's batch", "act('/outreach/send_all')"),
    "Sequence": ("Send today's batch", "act('/outreach/send_all')"),
    "Routing": ("Open System & Wiring", "nav('system')"),
    "Deliverability": ("Open System & Wiring", "nav('system')"),
    "Replies": ("Refresh replies", "act('/replies/refresh')"),
    "Bookings": ("Open Cal.com", "window.open('https://cal.com/bookings')"),
    "Attribution": ("Record a won deal", "biDeal()"),
    "Cost per Outcome": ("Open BI", "nav('bi')"),
})


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return list(v) if isinstance(v, (list, tuple)) else []


def _f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return float(d)


def _i(v, d=0):
    try:
        return int(_f(v, d))
    except Exception:
        return int(d)


def _n(v, dash="—"):
    return dash if v is None else v


def _money(v, dash="—"):
    return dash if v in (None, "") else f"€{_f(v):,.2f}"


def _ctx(ctx):
    """Coerce once at the boundary — a wrong shape must never crash a board."""
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in ("sourcing", "quality", "icp", "territories", "sends", "sequence",
              "routing", "deliverability", "replies", "bookings", "attribution",
              "costs", "tracking", "sourcing_mom", "campaign_costs",
              "leads_per_day", "live"):
        out[k] = _D(out.get(k))
    return out


def _live(ctx, key):
    """Pre-rendered interactive HTML, carried over from the old sections
    unchanged. Never rebuilt here — the send buttons must keep working."""
    v = _D(ctx.get("live")).get(key)
    return v if isinstance(v, str) else ""


def _vbars(m, a=VIOLET, b=TEAL):
    """Grouped columns for month-over-month. Draws only what was measured."""
    m = _D(m)
    groups = _L(m.get("groups"))
    if not groups:
        return ""
    series = [("this month", _L(m.get("this_month")), b)]
    if m.get("ready") and _L(m.get("last_month")):
        series.insert(0, ("last month", _L(m.get("last_month")), a))
    return _CH().vbars([str(g)[:8] for g in groups], series)


def _triple(ctx, key):
    """(rows, cols, grid) for a heatmap/cohort, always a usable triple."""
    v = _D(ctx).get(key)
    if (isinstance(v, (list, tuple)) and len(v) == 3
            and all(isinstance(x, (list, tuple)) for x in v)):
        return list(v[0]), list(v[1]), [list(r) for r in v[2]]
    return [], [], []


def _slots(rows, n, filled, empty_title, empty_sub, empty_why, src, accent=BLUE):
    out = []
    rows = _L(rows)
    for i in range(n):
        if i < len(rows):
            out.append(filled(i, rows[i]))
        else:
            out.append((f"{empty_title} {i + 1}", "—", empty_sub, "",
                        empty_why, src, accent, ""))
    return out


# ======================================================================
#  (1) LAUNCH PAD  (16)
# ======================================================================
def board_launch(ctx) -> str:
    ctx = _ctx(ctx)
    sc, sd, dv = ctx["sourcing"], ctx["sends"], ctx["deliverability"]
    sq, rp, bk = ctx["sequence"], ctx["replies"], ctx["bookings"]
    tk = ctx["tracking"]
    cards = [
        ("Ready to send today", _i(dv.get("headroom")), "within today's cap",
         _score_gauge(_f(dv.get("cap_used")), 90),
         (f"{_i(dv.get('sent_today'))} of {_i(dv.get('cap'))} sent. "
          + str(dv.get("note", ""))),
         "warmup cap", _pct_color(_f(dv.get("cap_used")), 90),
         "<button class='cta' onclick=\"act('/outreach/send_all')\">Send today's batch</button>"),
        ("Follow-ups due", _i(sq.get("due_count")), "leads waiting on the next touch",
         _statusgrid([(e[:16], False, f"touch {t}") for e, t in _L(sq.get("due"))[:9]]),
         ("A stalled sequence is the most common reason a reply rate collapses."
          if sq.get("due_count") else
          "Nobody is overdue. Every lead is either finished or inside the gap."),
         "sent stamps", AMBER if sq.get("due_count") else GREEN,
         "<button class='cta' onclick=\"act('/outreach/send_all')\">Send them</button>"),
        ("Replies waiting", _i(rp.get("total")), "in the inbox", "",
         ("Drafted answers are below — read, edit, send." if rp.get("total")
          else "No replies to work through."),
         "IMAP", GREEN if rp.get("total") else BLUE,
         "<button class='cta' onclick=\"act('/replies/refresh')\">Refresh replies</button>"),
        ("Leads in the pipeline", _i(sc.get("found")), "sourced",
         _trend([("leads/day", _L(sc.get("series")), TEAL)]),
         f"{_i(sc.get('verified'))} verified, {_i(sc.get('qualified'))} qualified.",
         "outreach jobs", GREEN if sc.get("found") else AMBER, ""),
        ("Emails sent", _i(sd.get("total")), "all time",
         _trend([("sends/day", _L(sd.get("series")), BLUE)]),
         f"To {_i(sd.get('recipients'))} people, "
         f"{sd.get('avg_per_recipient', 0)} each on average.",
         "sent stamps", GREEN if sd.get("total") else AMBER, ""),
        ("Reply rate", f"{rp.get('reply_rate', 0)}%", "of sends answered",
         _score_gauge(min(100, _f(rp.get("reply_rate")) * 5), 50),
         "Cold outreach at 5–10% is working. Under 2% is targeting, not volume.",
         "computed", _pct_color(100 - _f(rp.get("reply_rate")) * 5, 50), ""),
        ("Consultations booked", _i(bk.get("accepted")), "real calls", "",
         ("Read from Cal.com, not inferred from clicks. These are real "
          "bookings on a real calendar."),
         "Cal.com", GREEN if bk.get("accepted") else AMBER, ""),
        ("Suppressed addresses", _i(dv.get("suppressed")), "never emailed again",
         "", (f"{_i(dv.get('bounces'))} bounces, "
              f"{_i(dv.get('unsubscribes'))} unsubscribes."),
         "suppression list", AMBER if dv.get("suppressed") else GREEN, ""),
        ("Open tracking", "on" if tk.get("enabled") else "off",
         "pixel + wrapped links", "",
         (str(tk.get("caveat", "")) if tk.get("enabled")
          else str(tk.get("note", ""))),
         "your setting", BLUE,
         "<button class='cta' onclick='trackToggle()'>"
         + ("Turn tracking off" if tk.get("enabled") else "Turn tracking on")
         + "</button>"),
        ("Not yet contacted", _i(sq.get("not_started")), "leads with no email sent",
         "", ("Sourced and sitting still. Every one is a send you have already "
              "paid to find."),
         "computed", AMBER if sq.get("not_started") else GREEN, ""),
        ("Sequence finished", _i(sq.get("complete")), "had all 3 touches", "",
         "Nothing more will be sent to these unless you start a new campaign.",
         "computed", BLUE, ""),
        ("Campaigns", _i(sc.get("campaigns")), "outreach jobs", "",
         "Each campaign is one sourcing and sending cycle.",
         "jobs", BLUE, ""),
        ("Cost per reply", _money(_D(ctx["costs"]).get("per_reply")), "outreach spend",
         "", "The real unit cost at the top of your sales funnel.",
         "computed", GREEN if _D(ctx["costs"]).get("per_reply") else AMBER, ""),
        ("Bookings from replies", f"{bk.get('reply_to_booking', 0)}%",
         "replies that became calls", "",
         "The conversion that decides whether chasing replies is worth it.",
         "computed", BLUE, ""),
        ("Domain protection", "ramping" if _i(dv.get("cap")) < 200 else "at full speed",
         f"cap {_i(dv.get('cap'))}/day", "",
         str(dv.get("note", "")),
         "warmup", GREEN, ""),
        ("Where to act", "the outbox", "read, edit, send", "",
         "Every email waits for your approval. Nothing sends itself.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('ooutbox')\">Open the outbox</button>"),
    ]
    return (_head("🚀", "Launch pad",
                  "Everything you need to run today's outreach, and nothing "
                  "that sends without you.")
            + _live(ctx, "maps_form") + _live(ctx, "outbox_pointer")
            + _vizcards(cards))


# ======================================================================
#  (2) LEAD SOURCING  (20)
# ======================================================================
def board_sourcing(ctx) -> str:
    ctx = _ctx(ctx)
    sc = ctx["sourcing"]
    by_src = _L(sc.get("by_source"))
    per_day = _L(sc.get("per_day"))
    cards = [
        ("Leads found", _i(sc.get("found")), "sourced by the engine",
         _trend([("leads/day", _L(sc.get("series")), TEAL)]),
         ("Everything the lead agent has surfaced." if sc.get("has_data")
          else "No outreach campaign has run yet."),
         "outreach jobs", GREEN if sc.get("found") else AMBER, ""),
        ("Sources in use", len(by_src), "distinct providers",
         _split_donut([(s, v, c) for (s, v), c in
                       zip(by_src[:5], (TEAL, VIOLET, BLUE, AMBER, PINK))]),
         (str(sc.get("source_note", "")) if by_src else
          "Nothing has recorded a source yet."),
         "lead source stamp", GREEN if len(by_src) > 1 else AMBER, ""),
        ("Attributed to a source", f"{sc.get('attributed_pct', 0)}%", "of leads",
         _score_gauge(_f(sc.get("attributed_pct")), 90),
         ("The old card gave every lead to 'Web search' and showed Prospeo as 0 "
          "forever — because the Prospeo path never stamped a source at all. "
          "It does now."),
         "lead source stamp",
         GREEN if _f(sc.get("attributed_pct")) >= 90 else AMBER, ""),
        ("Unattributed", _i(sc.get("unattributed")), "sourced before the stamp",
         "", ("These stay unattributed rather than being assigned to a provider "
              "that may not have found them."),
         "computed", AMBER if sc.get("unattributed") else GREEN, ""),
        ("Leads by source", len(by_src), "ranked",
         _hbars([(s[:20], v) for s, v in by_src[:8]]),
         "Ranked by volume. One source is a single point of failure.",
         "lead source stamp", BLUE, ""),
        ("Leads month over month",
         len(_L(_D(ctx.get("sourcing_mom")).get("groups"))), "sources compared",
         _vbars(ctx.get("sourcing_mom")),
         _D(ctx.get("sourcing_mom")).get("note", ""),
         "campaign dates",
         GREEN if _D(ctx.get("sourcing_mom")).get("ready") else AMBER, ""),
        ("Busiest day", max([v for _d, v in per_day], default=0), "leads in one day",
         _histogram([_i(v) for _d, v in per_day]),
         "The distribution matters more than the total — spiky means one scrape.",
         "computed", BLUE, ""),
        ("Leads per campaign",
         (round(_i(sc.get("found")) / _i(sc.get("campaigns")), 1)
          if sc.get("campaigns") else "—"), "average yield", "",
         "Low yield means the query or the territory is too narrow.",
         "computed", BLUE, ""),
        ("Campaigns run", _i(sc.get("campaigns")), "sourcing cycles", "",
         "Each one sources, qualifies, writes and waits for your approval.",
         "jobs", BLUE, ""),
        ("Cost per lead", _money(_D(ctx["costs"]).get("per_lead")), "engine spend",
         "", ("Outreach spend divided by leads found. It ignores lead quality "
              "entirely, so a falling cost per lead can still mean a worse "
              "pipeline."),
         "computed", GREEN if _D(ctx["costs"]).get("per_lead") else AMBER, ""),
    ]
    cards += _slots(
        by_src, 6,
        lambda i, r: (f"Source: {r[0][:22]}", r[1], "leads",
                      _donut(round(100 * r[1] / max(_i(sc.get("found")), 1))),
                      ("Google Maps local businesses." if r[0] == "maps" else
                       "Prospeo verified work emails." if r[0] == "prospeo" else
                       "Web search results turned into company leads."
                       if r[0] == "web" else
                       "Posted in from outside the engine."),
                      "lead source stamp", BLUE, ""),
        "Source", "not in use yet",
        ("The engine can source from Google Maps, Prospeo and web search. This "
         "slot fills when another one starts producing."), "lead source stamp")
    cards += [
        ("Maps sourcing", "live", "type a business type and a city", "",
         ("Scrapes real local businesses, finds a verified email for each, and "
          "drops them into the normal pipeline. Nothing is emailed by it."),
         "Serper + Prospeo", GREEN,
         "<button class='cta' onclick=\"seoTab('olaunch')\">Open the form</button>"),
        ("Where to act", "Launch Pad", "source and send", "",
         "This board measures sourcing. The Launch Pad is where you start one.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('olaunch')\">Open Launch Pad</button>"),
        ("Deduplication", "on", "by email address", "",
         "The same person appearing in two campaigns is counted once.",
         "computed", GREEN, ""),
        ("Verified rate", f"{sc.get('found') and round(100 * _i(sc.get('verified')) / _i(sc.get('found')), 1) or 0}%",
         "survive verification", "",
         "Unverifiable addresses bounce, and bounces cost domain reputation.",
         "email verifier", BLUE, ""),
    ]
    return _head("🧲", "Lead sourcing",
                 "How many leads, from where, and how steadily.") + _vizcards(cards[:20])


# ======================================================================
#  (3) LEAD QUALITY & VERIFICATION  (18)
# ======================================================================
def board_quality(ctx) -> str:
    ctx = _ctx(ctx)
    q, sc = ctx["quality"], ctx["sourcing"]
    fields = _L(q.get("fields"))
    cards = [
        ("Verification funnel", _i(q.get("with_email")), "sendable leads",
         _waterfall([(n, v) for n, v in _L(q.get("stages"))]),
         ("Found, verified, qualified, sendable — every step measured, none "
          "of them a bar width chosen to look right."),
         "computed", GREEN if q.get("with_email") else AMBER, ""),
        ("Verified deliverable", f"{q.get('email_rate', 0)}%", "have a real address",
         _donut(_f(q.get("email_rate"))),
         ("The old card drew a 100% donut whenever any lead existed — a literal "
          "100, not a measurement. This is the actual share."),
         "computed", _pct_color(100 - _f(q.get("email_rate")), 30), ""),
        ("Verification rate", f"{q.get('verify_rate', 0)}%", "of found leads",
         _score_gauge(_f(q.get("verify_rate")), 70),
         "How many sourced leads survive email verification.",
         "email verifier", _pct_color(100 - _f(q.get("verify_rate")), 40), ""),
        ("Qualification rate", f"{q.get('qualify_rate', 0)}%", "of verified leads",
         _score_gauge(_f(q.get("qualify_rate")), 50),
         ("How many verified leads match your ICP. Narrowing the ICP "
          "lowers this by definition, without anything actually getting "
          "worse."),
         "lead qualifier", _pct_color(100 - _f(q.get("qualify_rate")), 50), ""),
        ("Enrichment completeness", f"{q.get('completeness', 0)}%",
         "of fields filled",
         _hbars([(f, v) for f, v in fields]),
         ("Name, company, title, website, LinkedIn, phone. A thin record makes "
          "a generic email, and generic emails do not get replies."),
         "lead records", _pct_color(100 - _f(q.get("completeness")), 50), ""),
        ("Leads on file", _i(q.get("leads")), "deduplicated", "",
         ("Distinct people across every campaign. Someone in three "
          "campaigns counts once, so this is your real list size."),
         "computed", BLUE, ""),
        ("Lost at verification", _i(sc.get("found")) - _i(sc.get("verified")),
         "no usable address", "",
         "Sourced but unreachable. They cost credits and cannot be emailed.",
         "computed", AMBER, ""),
        ("Lost at qualification", _i(sc.get("verified")) - _i(sc.get("qualified")),
         "real but off-ICP", "",
         "Reachable people who are not your buyer — sourcing is aiming wide.",
         "computed", AMBER, ""),
    ]
    cards += _slots(
        fields, 6,
        lambda i, r: (f"Field: {r[0]}", r[1], "leads have it",
                      _donut(round(100 * r[1] / max(_i(q.get("leads")), 1))),
                      "Coverage of this field across the lead list.",
                      "lead records", BLUE),
        "Field", "not present",
        "Each enrichment field is counted across every lead.", "lead records")
    cards += [
        ("Bounce protection", "automatic", "suppression on failure", "",
         "A bounced address is suppressed and never emailed again.",
         "connectors", GREEN, ""),
        ("Quality gate", "before send", "CAN-SPAM validator", "",
         "Every email is checked for required elements before it can leave.",
         "safety module", GREEN, ""),
        ("Where to act", "Approvals", "review before sending", "",
         "Nothing is emailed without you approving it first.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ("Sendable now", _i(q.get("with_email")), "have an address", "",
         "The real ceiling on today's send, before the daily cap applies.",
         "computed", GREEN if q.get("with_email") else AMBER, ""),
    ]
    # The leads table rendered in BOTH old sections. It belongs here once —
    # this is the board about the lead records themselves.
    return (_head("🔬", "Lead quality & verification",
                  "How many leads are real, reachable and worth writing to.")
            + _vizcards(cards[:18]) + _live(ctx, "leads_table"))


# ======================================================================
#  (4) ICP & SCORING  (18)
# ======================================================================
def board_icp(ctx) -> str:
    ctx = _ctx(ctx)
    ic = ctx["icp"]
    verts = _L(ic.get("verticals"))
    cards = [
        ("ICP match rate", f"{ic.get('icp_rate', 0)}%", "of leads fit",
         _score_gauge(_f(ic.get("icp_rate")), 60),
         ("Matched against your stated ICP: doctors, lawyers, Shopify stores, "
          "tax consultants, content creators, marketing managers."),
         "lead qualifier", _pct_color(100 - _f(ic.get("icp_rate")), 40), ""),
        ("Score distribution", _i(ic.get("scored")), "leads scored",
         _histogram([_i(v) for v in _L(ic.get("scores"))]),
         ("The shape matters: a flat spread means the scorer is not "
          "discriminating between good and bad leads."),
         "lead qualifier", BLUE if ic.get("scored") else AMBER, ""),
        ("Average score", _n(ic.get("avg_score")), "across scored leads", "",
         "Useful only against its own spread, which is the chart above.",
         "lead qualifier", BLUE, ""),
        ("Verticals present", len(verts), "distinct",
         _treemap([(v[:18], n) for v, n in verts[:8]]),
         "Size is lead count. A single dominant block is a narrow pipeline.",
         "lead records", BLUE if verts else AMBER, ""),
        ("Verticals ranked", len(verts), "by lead count",
         _hbars([(str(v)[:20], n) for v, n in verts[:8]]),
         "The same data as the treemap, ranked — easier to read exact numbers.",
         "lead records", BLUE, ""),
        ("Unclassified", _i(ic.get("unclassified")), "no vertical recorded", "",
         ("These cannot be scored against the ICP, so they dilute the match "
          "rate above."),
         "computed", AMBER if ic.get("unclassified") else GREEN, ""),
        ("Your ICP", len(_L(ic.get("icp_list"))), "target verticals",
         _statusgrid([(t, any(t in str(v).lower() for v, _n2 in verts), "")
                      for t in _L(ic.get("icp_list"))]),
         "Green means at least one lead in that vertical has been sourced.",
         "your ICP", VIOLET, ""),
        ("ICP-matched leads", _i(ic.get("icp_matched")), "fit the profile", "",
         ("The only leads worth spending sends on. Sending outside this "
          "set costs sender reputation as well as money."),
         "computed", GREEN if ic.get("icp_matched") else AMBER, ""),
    ]
    cards += _slots(
        verts, 8,
        lambda i, r: (f"Vertical: {str(r[0])[:20]}", r[1], "leads",
                      _donut(round(100 * r[1] / max(_i(ic.get("scored")) or 1, 1))),
                      "Share of the lead list in this vertical.",
                      "lead records", BLUE),
        "Vertical", "none sourced",
        ("Your ICP names six verticals. This slot fills when leads arrive from "
         "another of them."), "lead records")
    cards += [
        ("Widen or narrow?",
         ("narrow" if _f(ic.get("icp_rate")) < 50 else "holding"),
         "targeting verdict", "",
         ("Under half the leads fit, so sourcing is casting too wide — that "
          "wastes verification credits and send capacity."
          if _f(ic.get("icp_rate")) < 50 else
          "Most sourced leads fit the profile."),
         "computed", AMBER if _f(ic.get("icp_rate")) < 50 else GREEN, ""),
        ("Where to act", "BI", "which vertical actually pays", "",
         "This board shows who you are targeting. BI shows who paid.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
    ]
    return _head("🎯", "ICP & scoring",
                 "Are you writing to the right people?") + _vizcards(cards[:18])


# ======================================================================
#  (5) TERRITORIES & VERTICALS  (18)
# ======================================================================
def board_territories(ctx) -> str:
    ctx = _ctx(ctx)
    tr = ctx["territories"]
    rows = _L(tr.get("rows"))
    covered = _D(tr.get("covered"))
    cards = [
        ("Markets with leads", len(rows), "countries",
         _CH().geo([(k, v) for k, v in rows[:10]]) if rows else "",
         ("Where your sourced leads actually are." if rows else
          "No lead carries a country yet."),
         "lead records", GREEN if rows else AMBER, ""),
        ("Target-market share", f"{tr.get('target_share', 0)}%",
         "of leads in your five markets",
         _score_gauge(_f(tr.get("target_share")), 80),
         ("USA, UK, Germany, Switzerland and Canada. Leads outside them rarely "
          "convert and still cost credits to verify."),
         "computed", _pct_color(100 - _f(tr.get("target_share")), 40), ""),
        ("Markets with no leads", len(_L(tr.get("missing"))), "of your five", "",
         (f"Nothing sourced from: {', '.join(_L(tr.get('missing')))}."
          if tr.get("missing") else "All five markets are producing leads."),
         "computed", PINK if tr.get("missing") else GREEN, ""),
        ("Country unknown", _i(tr.get("unknown")), "leads with no country", "",
         "These cannot be counted toward any market and dilute the share above.",
         "lead records", AMBER if tr.get("unknown") else GREEN, ""),
    ]
    for m in ("United States", "United Kingdom", "Germany", "Switzerland", "Canada"):
        v = _i(covered.get(m))
        cards.append((m, v, "leads",
                      _donut(round(100 * v / max(_i(tr.get("total")), 1))),
                      (f"{round(100 * v / max(_i(tr.get('total')), 1), 1)}% of "
                       f"sourced leads." if v else
                       f"No leads sourced from {m} yet."
                       + (" Note the site has no German content, which limits "
                          "inbound from here too."
                          if m in ("Germany", "Switzerland") else "")),
                      "lead records", GREEN if v else PINK, ""))
    cards += [
        ("Market composition", len(rows), "markets by share",
         _treemap([(k[:18], v) for k, v in rows[:8]]),
         "Size is lead count. One dominant tile is a single-market pipeline.",
         "lead records", BLUE if rows else AMBER, ""),
        ("Leads by market", len(rows), "ranked",
         _hbars([(k[:20], v) for k, v in rows[:8]]),
         ("Ranked by lead count. Volume by market says nothing about "
          "which market actually converts."), "lead records", BLUE, ""),
        ("Top market", (rows[0][0] if rows else "—"),
         f"{rows[0][1]} leads" if rows else "no data", "",
         "Where sourcing is currently concentrated.",
         "lead records", BLUE, ""),
        ("Market concentration",
         (f"{round(100 * rows[0][1] / max(_i(tr.get('total')), 1))}%"
          if rows else "—"), "from the top market", "",
         "One market above 60% means a local change moves everything.",
         "computed", AMBER, ""),
        ("Off-target leads", f"{100 - _f(tr.get('target_share')):.0f}%",
         "outside your five", "",
         "Not worthless, but they convert at a different rate.",
         "computed", AMBER if _f(tr.get("target_share")) < 60 else GREEN, ""),
        ("Language coverage", "English only", "site content", "",
         ("Germany and Switzerland are target markets and the site has no "
          "German content. Cold email in English to a German SME converts "
          "worse than the same email in German."),
         "site audit", PINK,
         "<button class='cta' onclick=\"nav('seo')\">Open GEO</button>"),
        ("Where to act", "GEO board", "language and market coverage", "",
         "This board shows where the leads are. GEO shows how to reach the "
         "markets that produce none.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('seo')\">Open GEO</button>"),
        ("Leads with a country", 
         _i(tr.get("total")), "of the lead list", "",
         ("Only these can be counted toward a market. A lead with no country "
          "is invisible to every number on this board."),
         "lead records", BLUE if tr.get("total") else AMBER, ""),
        ("Markets live vs plan",
         f"{len([1 for v in covered.values() if v])}/5", "target markets", "",
         "The plan names five. This is how many are actually producing leads.",
         "computed",
         GREEN if len([1 for v in covered.values() if v]) >= 4 else AMBER, ""),
    ]
    return _head("🌍", "Territories & verticals",
                 "Which markets your leads come from, against the five you "
                 "sell into.") + _vizcards(cards[:18])


# ======================================================================
#  (6) THE OUTBOX  (18)
# ======================================================================
def board_outbox(ctx) -> str:
    ctx = _ctx(ctx)
    sq, sd, dv = ctx["sequence"], ctx["sends"], ctx["deliverability"]
    at = _D(sq.get("at_step"))
    cards = [
        ("Queue by sequence step", sum(_i(v) for v in at.values()), "leads",
         _statusgrid([(f"{k} sent", _i(k) > 0, f"{_i(v)} leads")
                      for k, v in sorted(at.items())]),
         "Where every lead sits in the 3-email cycle.",
         "sent stamps", BLUE if sq.get("has_data") else AMBER, ""),
        ("Not started", _i(sq.get("not_started")), "no email sent yet", "",
         ("Sourced, approved and sitting still. These cost nothing to "
          "hold, and earn nothing either."),
         "computed", AMBER if sq.get("not_started") else GREEN, ""),
        ("In sequence",
         _i(at.get(1, 0)) + _i(at.get(2, 0)), "part way through", "",
         "Between touch 1 and touch 3. Most replies come from touches 2 and 3.",
         "computed", BLUE, ""),
        ("Finished", _i(sq.get("complete")), "all 3 sent", "",
         ("Nothing further will be sent to these. The sequence is "
          "complete, whether or not it worked."),
         "computed", BLUE, ""),
        ("Due now", _i(sq.get("due_count")), "past the follow-up gap",
         _statusgrid([(e[:16], False, f"touch {t}") for e, t in _L(sq.get("due"))[:9]]),
         f"The gap is {sq.get('gap_days', 3)} days between touches.",
         "computed", AMBER if sq.get("due_count") else GREEN,
         "<button class='cta' onclick=\"act('/outreach/send_all')\">Send today's batch</button>"),
        ("Today's send capacity", _i(dv.get("headroom")), "emails left today",
         _score_gauge(_f(dv.get("cap_used")), 90),
         f"{_i(dv.get('sent_today'))} of {_i(dv.get('cap'))} used.",
         "warmup cap", _pct_color(_f(dv.get("cap_used")), 90), ""),
        ("Sends recorded", _i(sd.get("total")), "all time", "",
         "Counted from real send timestamps, not campaign dates.",
         "sent stamps", GREEN if sd.get("total") else AMBER, ""),
        ("People reached", _i(sd.get("recipients")), "distinct addresses", "",
         ("Distinct people emailed at least once. Repeat sends to the "
          "same person do not increase this number."),
         "computed", BLUE, ""),
        ("Touches per person", _n(sd.get("avg_per_recipient")), "average", "",
         "Below 2 means the follow-up sequence is not running.",
         "computed", AMBER if _f(sd.get("avg_per_recipient")) < 2 else GREEN, ""),
        ("Approval gate", "on", "nothing sends itself", "",
         ("Every email waits for you. The send buttons below are the only way "
          "anything leaves."),
         "engine", GREEN, ""),
    ]
    cards += _slots(
        _L(sd.get("by_step")), 3,
        lambda i, r: (f"Sends at {r[0]}", r[1], "emails",
                      _donut(round(100 * _i(r[1]) / max(_i(sd.get("total")), 1))),
                      ("The opener." if i == 0 else
                       "The first follow-up — usually the best replier."
                       if i == 1 else "The last touch before the sequence stops."),
                      "sent stamps", BLUE),
        "Touch", "none sent",
        "Each touch of the 3-email cycle is counted separately.", "sent stamps")
    cards += [
        ("Trash and edit", "per email", "before it sends", "",
         "Any drafted email can be rewritten or dropped from the outbox below.",
         "outbox", BLUE, ""),
        ("Send one or send all", "both", "your choice", "",
         "Send a single lead's next touch, or run the whole due batch at once.",
         "outbox", BLUE, ""),
        ("Cap-honoured", "always", "batch respects the daily limit", "",
         "A batch stops at the cap rather than burning the domain.",
         "connectors", GREEN, ""),
        ("Suppression respected", "always", "before every send", "",
         "A suppressed address is skipped even if it is still in a campaign.",
         "connectors", GREEN, ""),
        ("Where to act", "below", "the live outbox", "",
         "The queue itself is under this board — read, edit, send.",
         "navigation", VIOLET, ""),
    ]
    return (_head("📬", "The outbox",
                  "Every drafted email, and the buttons that send them.")
            + _vizcards(cards[:18]) + _live(ctx, "outbox"))


# ======================================================================
#  (7) SEQUENCE & CADENCE  (18)
# ======================================================================
def board_sequence(ctx) -> str:
    ctx = _ctx(ctx)
    sq, sd, rp = ctx["sequence"], ctx["sends"], ctx["replies"]
    by_step = _L(sd.get("by_step"))
    cards = [
        ("Where leads sit", sum(_i(v) for v in _D(sq.get("at_step")).values()),
         "across the cycle",
         _CH().cohort(_L(sq.get("cohort_cols")), _L(sq.get("cohort_grid"))),
         "Rows are touches, columns are how many emails a lead has received.",
         "sent stamps", BLUE if sq.get("has_data") else AMBER, ""),
        ("The 3-email cycle", 3, "touches per lead",
         _CH().gantt(_L(sq.get("tasks")), span=12),
         f"Touch 1, then {sq.get('gap_days', 3)} days, then again.",
         "engine", VIOLET, ""),
        ("Follow-up gap", f"{sq.get('gap_days', 3)} days", "between touches", "",
         "Too short reads as pestering; too long and you are forgotten.",
         "engine", BLUE, ""),
        ("Overdue", _i(sq.get("due_count")), "past the gap", "",
         ("A stalled sequence is the most common cause of a collapsing reply "
          "rate." if sq.get("due_count") else "Nothing is overdue."),
         "computed", AMBER if sq.get("due_count") else GREEN,
         "<button class='cta' onclick=\"act('/outreach/send_all')\">Send them</button>"),
        ("Sends by touch", len(by_step), "steps measured",
         _hbars([(s, v) for s, v in by_step]),
         ("If touch 1 dwarfs touches 2 and 3, the sequence is starting people "
          "and abandoning them."),
         "sent stamps", BLUE, ""),
    ]
    cards += _slots(
        by_step, 3,
        lambda i, r: (f"{str(r[0]).title()} sent", r[1], "emails",
                      _donut(round(100 * _i(r[1]) / max(_i(sd.get("total")), 1))),
                      ("The opener — the one most people judge you on."
                       if i == 0 else
                       "The follow-up that historically wins the most replies."
                       if i == 1 else
                       "The final touch. After this the lead is left alone."),
                      "sent stamps", BLUE),
        "Touch", "none sent",
        "Each step is counted from the recorded send stamp.", "sent stamps")
    cards += _slots(
        _L(sq.get("due")), 6,
        lambda i, r: (f"Due: {str(r[0])[:22]}", f"touch {r[1]}", "ready to send",
                      "", "Past the follow-up gap and waiting.",
                      "computed", AMBER),
        "Due slot", "nobody overdue",
        ("A lead appears here once it has passed the follow-up gap without the "
         "next touch being sent."), "computed", GREEN)
    cards += [
        ("Completion rate",
         (f"{round(100 * _i(sq.get('complete')) / max(sum(_i(v) for v in _D(sq.get('at_step')).values()), 1))}%"
          if sq.get("has_data") else "—"), "finished all 3", "",
         "A low rate with high touch-1 volume means the sequence is not running.",
         "computed", BLUE, ""),
        ("Reply by touch", _i(rp.get("total")), "replies recorded", "",
         ("Which touch wins replies needs the reply linked back to a send. The "
          "step stamp now exists, so this sharpens as new replies arrive."),
         "sent stamps", BLUE if rp.get("total") else AMBER, ""),
        ("Touches per person", _n(sd.get("avg_per_recipient")), "average", "",
         ("Below 2 means people are being started and abandoned — the opener "
          "goes out and the follow-ups never do."),
         "computed", AMBER if _f(sd.get("avg_per_recipient")) < 2 else GREEN, ""),
        ("Where to act", "the outbox", "send the due batch", "",
         "Everything overdue can go out in one click, capped.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('ooutbox')\">Open the outbox</button>"),
    ]
    return _head("🔁", "Sequence & cadence",
                 "Where every lead sits in the 3-email cycle, and who is "
                 "due.") + _vizcards(cards[:18])


# ======================================================================
#  (8) SENDER & ROUTING  (16)
# ======================================================================
def board_routing(ctx) -> str:
    ctx = _ctx(ctx)
    rt, sd = ctx["routing"], ctx["sends"]
    by_alias = _L(rt.get("by_alias"))
    cards = [
        ("Aliases in use", len(by_alias), "sending addresses",
         _CH().sankey(_L(rt.get("flows"))),
         str(rt.get("note", "")),
         "send stamp", GREEN if rt.get("recorded") else AMBER, ""),
        ("Alias recorded", "yes" if rt.get("recorded") else "not yet",
         "on each send", "",
         ("The old card assumed every outreach email left from marketing@ and "
          "every reply from customercare@ — the alias was never recorded. It "
          "is now, on every send."),
         "send stamp", GREEN if rt.get("recorded") else AMBER, ""),
        ("Volume by alias", len(by_alias), "ranked",
         _hbars([(a[:24], v) for a, v in by_alias[:6]]),
         ("Measured from the recorded alias." if by_alias else
          "Fills from the next send."),
         "send stamp", BLUE, ""),
        ("Routing rule", 4, "purposes mapped", "",
         ("Newsletter, marketing, support and contact each leave from their own "
          "alias on your one mailbox."),
         "engine", VIOLET, ""),
    ]
    cards += _slots(
        by_alias, 6,
        lambda i, r: (f"{str(r[0])[:24]}", r[1], "emails sent",
                      _donut(round(100 * _i(r[1]) / max(_i(sd.get("total")), 1))),
                      "Share of all recorded sends from this address.",
                      "send stamp", BLUE),
        "Alias", "no sends recorded",
        ("Each alias appears here once a send has actually gone out from it."),
        "send stamp")
    cards += [
        ("One mailbox", "yes", "all aliases, one inbox", "",
         "Replies to any alias land in the same place and are read once.",
         "IMAP", GREEN, ""),
        ("Reply routing", "customercare@", "answers go out from here", "",
         "Support replies use a different alias from cold outreach on purpose.",
         "engine", BLUE, ""),
        ("Alias per purpose", "enforced", "at send time", "",
         "The category chosen at send decides the FROM address, not a guess.",
         "connectors", GREEN, ""),
        ("Domain", "one", "all aliases share it", "",
         "Reputation is per-domain, so every alias shares the same standing.",
         "connectors", BLUE, ""),
        ("Where to act", "System & Wiring", "email settings", "",
         "The mailbox, aliases and overrides all live there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System & Wiring</button>"),
        ("Override available", "EMAIL_FROM_*", "per category", "",
         "Any purpose can be pointed at a specific address if you want.",
         "connectors", BLUE, ""),
    ]
    return _head("📮", "Sender & routing",
                 "Which address each email actually left from.") + _vizcards(cards[:16])


# ======================================================================
#  (9) DELIVERABILITY & REPUTATION  (20)
# ======================================================================
def board_deliverability(ctx) -> str:
    ctx = _ctx(ctx)
    dv, tk, sd = ctx["deliverability"], ctx["tracking"], ctx["sends"]
    reasons = _L(dv.get("reasons"))
    cards = [
        ("Today's cap", _i(dv.get("cap")), "emails allowed",
         _trend([("sent/day", _L(dv.get("series")), BLUE),
                 ("cap", _L(dv.get("cap_series")), AMBER)]),
         str(dv.get("note", "")),
         "warmup", GREEN, ""),
        ("Sent today", _i(dv.get("sent_today")), f"of {_i(dv.get('cap'))}",
         _score_gauge(_f(dv.get("cap_used")), 90),
         ("The old card said 'daily send cap ramps up as the domain warms' and "
          "showed no number. This is the number."),
         "counter", _pct_color(_f(dv.get("cap_used")), 90), ""),
        ("Headroom", _i(dv.get("headroom")), "left today", "",
         "What you can still send before the engine holds the rest.",
         "computed", GREEN if dv.get("headroom") else AMBER, ""),
        ("Suppressed", _i(dv.get("suppressed")), "never emailed again",
         _split_donut([(r, v, c) for (r, v), c in
                       zip(reasons, (PINK, AMBER, BLUE, VIOLET))]),
         ("Split by reason. The list alone could not tell a bounce from an "
          "unsubscribe, and those mean very different things."),
         "suppression list", AMBER if dv.get("suppressed") else GREEN, ""),
        ("Bounces", _i(dv.get("bounces")), "hard failures", "",
         "Each one is a dead address that cost credits to source and verify.",
         "suppression list", PINK if dv.get("bounces") else GREEN, ""),
        ("Unsubscribes", _i(dv.get("unsubscribes")), "asked to stop", "",
         "Legally required to honour, and honoured automatically.",
         "suppression list", BLUE, ""),
        ("Reason unrecorded", _i(dv.get("unrecorded")), "suppressed before the stamp",
         "", ("These were suppressed before the reason was recorded, so they "
              "count as neither bounce nor unsubscribe rather than being "
              "guessed into one."),
         "suppression list", AMBER if dv.get("unrecorded") else GREEN, ""),
        ("Suppressions by day", sum(sum(r) for r in _triple(ctx, "suppression_heat")[2]),
         "in the last 7 days",
         _heatmap(*_triple(ctx, "suppression_heat")),
         ("Rows are reasons, columns are days. A hot bounce row means the list "
          "quality dropped, not that sending broke."
          if _triple(ctx, "suppression_heat")[0] else
          "Nothing has been suppressed in the last seven days."),
         "suppression list",
         PINK if sum(sum(r) for r in _triple(ctx, "suppression_heat")[2]) else GREEN, ""),
        ("Suppression rate", f"{dv.get('suppression_rate', 0)}%", "of sends",
         _score_gauge(min(100, _f(dv.get("suppression_rate")) * 10), 30),
         "Above 3% is a list-quality problem, not a sending problem.",
         "computed", _pct_color(_f(dv.get("suppression_rate")) * 10, 30), ""),
        ("Warmup ramp",
         (f"{_L(dv.get('ramp'))[0]} → {_L(dv.get('ramp'))[-1]}"
          if _L(dv.get("ramp")) else "—"),
         "over about two weeks",
         _hbars([(f"day {i}", v) for i, v in enumerate(_L(dv.get("ramp")))]),
         "A new domain sending 200 on day one gets filtered. This is why.",
         "engine", VIOLET, ""),
        # ---- tracking, and what it costs ----
        ("Open tracking", "on" if tk.get("enabled") else "off",
         "1x1 pixel + wrapped links", "",
         (str(tk.get("caveat", "")) if tk.get("enabled") else str(tk.get("note", ""))),
         "your setting", AMBER if tk.get("enabled") else BLUE,
         "<button class='cta' onclick='trackToggle()'>"
         + ("Turn it off" if tk.get("enabled") else "Turn it on") + "</button>"),
        ("GDPR note", "Germany · Switzerland", "two of your five markets", "",
         str(tk.get("gdpr", "")),
         "your setting", AMBER,
         "<button class='cta' onclick='trackToggle()'>Toggle tracking</button>"),
        ("Opens", _i(tk.get("opens")), "unique",
         _trend([("events/day", [v for _d, v in _L(tk.get("per_day"))], TEAL)]),
         (f"{tk.get('open_rate', 0)}% of {_i(tk.get('tracked_sends'))} tracked "
          f"sends. Counted once per recipient, not per reload."
          if tk.get("enabled") else "Tracking is off."),
         "tracking", BLUE if tk.get("enabled") else AMBER, ""),
        ("Clicks", _i(tk.get("clicks")), "unique", "",
         (f"{tk.get('click_rate', 0)}% of tracked sends. Clicks are real — "
          f"unlike opens, nothing pre-fetches them."
          if tk.get("enabled") else "Tracking is off."),
         "tracking", GREEN if tk.get("clicks") else BLUE, ""),
        ("Click to open", f"{tk.get('click_to_open', 0)}%", "of openers clicked",
         "", "The only open-derived number worth trusting, and only loosely.",
         "tracking", BLUE, ""),
        ("Opens by touch", len(_L(tk.get("opens_by_step"))), "steps",
         _hbars([(s, v) for s, v in _L(tk.get("opens_by_step"))]),
         ("Which touch actually gets looked at. Opens are unreliable, "
          "since privacy proxies fire them without a human reading "
          "anything."),
         "tracking", BLUE, ""),
    ]
    cards += [
        ("Unsubscribe link", "on every email", "required", "",
         "Present in every send, and honoured automatically when clicked.",
         "connectors", GREEN, ""),
        ("CAN-SPAM validator", "before send", "blocks non-compliant mail", "",
         "A missing address or unsubscribe link stops the email leaving.",
         "safety module", GREEN, ""),
        ("Reply rate as the honest measure", f"{_D(ctx['replies']).get('reply_rate', 0)}%",
         "of sends answered", "",
         ("Opens can be pre-fetched and clicks can be scanned by security "
          "gateways. A reply is a person."),
         "computed", GREEN, ""),
        ("Where to act", "System & Wiring", "mailbox and limits", "",
         "The daily cap override and mail credentials live there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System & Wiring</button>"),
    ]
    return _head("🛡", "Deliverability & reputation",
                 "The cap, the suppression list, and what tracking really "
                 "tells you.") + _vizcards(cards[:20])


# ======================================================================
#  (10) REPLIES & INTENT  (18)
# ======================================================================
def board_replies(ctx) -> str:
    ctx = _ctx(ctx)
    rp, sd, bk = ctx["replies"], ctx["sends"], ctx["bookings"]
    intents = _L(rp.get("intents"))
    subs = _L(rp.get("subjects"))
    cards = [
        ("Replies", _i(rp.get("total")), "real responses",
         _split_donut([(i2, v, c) for (i2, v), c in
                       zip(intents, (GREEN, TEAL, BLUE, AMBER, PINK))]),
         ("Read from the mailbox, not inferred." if rp.get("total")
          else "Nothing has come back yet."),
         "IMAP", GREEN if rp.get("total") else AMBER,
         "<button class='cta' onclick=\"act('/replies/refresh')\">Refresh</button>"),
        ("Reply rate", f"{rp.get('reply_rate', 0)}%", "of sends",
         _score_gauge(min(100, _f(rp.get("reply_rate")) * 5), 50),
         "5–10% on cold outreach is working. Under 2% is a targeting problem.",
         "computed", _pct_color(100 - _f(rp.get("reply_rate")) * 5, 50), ""),
        ("Reply rate per person", f"{rp.get('per_person_rate', 0)}%",
         "of people emailed", "",
         "The honest version — follow-ups inflate the per-send number.",
         "computed", BLUE, ""),
        ("Silent", _i(rp.get("silent")), "emailed, never answered", "",
         "The follow-up sequence exists for exactly this group.",
         "computed", AMBER if rp.get("silent") else GREEN, ""),
        ("Classified intents", len(intents), "kinds of reply",
         _hbars([(i2[:18], v) for i2, v in intents]),
         ("The reply agent classifies what it can; the rest wait for you."),
         "reply agent", BLUE if intents else AMBER, ""),
        ("Unclassified", _i(rp.get("unclassified")), "need a human", "",
         ("Only one intent is classified automatically today. These are read "
          "and answered by you rather than being guessed at."),
         "reply agent", AMBER if rp.get("unclassified") else GREEN, ""),
        ("Sends by touch and day",
         sum(sum(r) for r in _triple(ctx, "sends_cohort")[2]), "in the last 7 days",
         _CH().cohort(_triple(ctx, "sends_cohort")[1],
                      _triple(ctx, "sends_cohort")[2]),
         ("Rows are touches, columns are days. This is SENDS, not replies — a "
          "reply is not yet linked back to the send that earned it. The step "
          "stamp now exists, so that linkage becomes possible for replies "
          "received from here on."),
         "sent stamps", BLUE, ""),
        ("Replies per day", len(_L(rp.get("per_day"))), "days with a reply",
         _trend([("replies", [v for _d, v in _L(rp.get("per_day"))], VIOLET)]),
         "Clusters usually follow a send burst two or three days earlier.",
         "IMAP", BLUE, ""),
        ("Reply to booking", f"{bk.get('reply_to_booking', 0)}%",
         "replies that became calls", "",
         "The conversion that decides whether chasing replies pays.",
         "computed", BLUE, ""),
    ]
    cards += _slots(
        subs, 6,
        lambda i, r: (f"Subject {i + 1}", str(r[0])[:26], f"{r[1]} sent", "",
                      ("Recorded on the send, so subject performance can finally "
                       "be ranked. The old card was permanently empty because "
                       "nothing stored the subject."),
                      "send stamp", BLUE),
        "Subject", "none recorded yet",
        ("Subjects are recorded from the next send onward. The old 'Best subject "
         "lines' card could never rank anything because nothing stored them."),
        "send stamp")
    cards += [
        ("Answer drafting", "automatic", "for answerable replies", "",
         "The agent drafts; you read, edit and send. Nothing auto-sends.",
         "reply agent", GREEN, ""),
        ("Where to act", "below", "the live replies inbox", "",
         "Every drafted answer is under this board.",
         "navigation", VIOLET, ""),
        ("Unsubscribe replies", "auto-suppressed", "honoured immediately", "",
         "A reply asking to stop suppresses the address without you acting.",
         "connectors", GREEN, ""),
    ]
    return (_head("💬", "Replies & intent",
                  "What came back, what it means, and what to say.")
            + _vizcards(cards[:18]) + _live(ctx, "replies"))


# ======================================================================
#  (11) BOOKINGS & CONVERSION  (16)
# ======================================================================
def board_bookings(ctx) -> str:
    ctx = _ctx(ctx)
    bk, rp, sd, sc = ctx["bookings"], ctx["replies"], ctx["sends"], ctx["sourcing"]
    stages = [("Leads", _i(sc.get("found"))), ("Emailed", _i(sd.get("recipients"))),
              ("Replied", _i(rp.get("total"))), ("Booked", _i(bk.get("accepted")))]
    cards = [
        ("Consultations booked", _i(bk.get("accepted")), "accepted",
         _CH().gantt(_L(bk.get("tasks")), span=14),
         ("Real Cal.com bookings on a timeline." if bk.get("has_data")
          else "Cal.com is connected and has returned no bookings yet."),
         "Cal.com", GREEN if bk.get("accepted") else AMBER, ""),
        ("Outreach to booking", len(stages), "stages",
         _waterfall(stages),
         ("Lead to booked call, measured at every step. No skeleton bar widths "
          "standing in for conversion rates."),
         "computed", BLUE, ""),
        ("Upcoming", _i(bk.get("upcoming")), "calls ahead", "",
         ("Your near-term pipeline - calls already on the calendar, "
          "before any of them have actually happened."),
         "Cal.com", GREEN if bk.get("upcoming") else AMBER, ""),
        ("Held", _i(bk.get("past")), "already happened", "",
         "Each one should end recorded as won or lost.",
         "Cal.com", BLUE, ""),
        ("Next call", (bk.get("next") or "—"), "date", "",
         ("The next consultation on the calendar." if bk.get("next")
          else "Nothing scheduled ahead."),
         "Cal.com", GREEN if bk.get("next") else AMBER, ""),
        ("Total bookings", _i(bk.get("total")), "all statuses", "",
         ("Includes cancelled and pending bookings, so this is larger "
          "than the number of calls you will actually take."),
         "Cal.com", BLUE, ""),
        ("Cancelled or pending",
         max(0, _i(bk.get("total")) - _i(bk.get("accepted"))), "not accepted", "",
         "A wide gap means the booking flow attracts the wrong people.",
         "computed", AMBER, ""),
        ("Bookings per day", len(_L(bk.get("per_day"))), "days with a booking",
         _trend([("bookings", [v for _d, v in _L(bk.get("per_day"))], GREEN)]),
         ("Bookings cluster after a send burst, so a quiet day usually "
          "reflects last week's sending rather than today's."),
         "Cal.com", BLUE, ""),
        ("Reply to booking", f"{bk.get('reply_to_booking', 0)}%", "conversion", "",
         "Of everyone who replied, how many put a call in the calendar.",
         "computed", BLUE, ""),
        ("Emailed to booking",
         (f"{round(100 * _i(bk.get('accepted')) / max(_i(sd.get('recipients')), 1), 2)}%"
          if sd.get("recipients") else "—"), "end to end", "",
         "The number that says whether cold outreach works for you at all.",
         "computed", BLUE, ""),
        ("Cost per booking", _money(_D(ctx["costs"]).get("per_booking")), "engine spend",
         "", "What it costs to put one qualified call in the calendar.",
         "computed", GREEN if _D(ctx["costs"]).get("per_booking") else AMBER, ""),
        ("Cal.com wire", "connected", "reading live", "",
         "Every number on this board is real rather than assumed.",
         "System & Wiring", GREEN, ""),
    ]
    cards += _slots(
        _L(bk.get("per_day")), 3,
        lambda i, r: (f"Bookings {r[0]}", r[1], "that day", "",
                      "A day calls were booked.", "Cal.com", BLUE),
        "Booking day", "none yet",
        "Each day with a booking appears here.", "Cal.com")
    cards += [
        ("Where to act", "record the outcome", "after each call", "",
         ("A call that is not recorded as won or lost leaves revenue, CAC and "
          "close rate uncomputable."),
         "navigation", VIOLET,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
    ]
    return _head("📅", "Bookings & conversion",
                 "Calls booked off the outreach, and what they cost.") + _vizcards(cards[:16])


# ======================================================================
#  (12) LEAD → DEAL ATTRIBUTION  (16)
# ======================================================================
def board_attribution(ctx) -> str:
    ctx = _ctx(ctx)
    at, sc = ctx["attribution"], ctx["sourcing"]
    by_src = _L(at.get("by_source"))
    cards = [
        ("Revenue by lead source", len(by_src), "sources with revenue",
         _CH().sankey(_L(at.get("flows"))),
         ("Which sourcing channel actually produced money — possible only "
          "because each deal records where it came from."
          if at.get("has_data") else
          "No deal recorded yet. One deal makes this whole board live."),
         "recorded deals", GREEN if at.get("has_data") else AMBER,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Revenue from outreach", _money(at.get("outreach_revenue")), "attributed",
         _donut(_f(at.get("outreach_share"))),
         (f"{at.get('outreach_share', 0)}% of all recorded revenue came from "
          f"outreach." if at.get("has_data") else
          "Fills from the first recorded deal tagged 'outreach'."),
         "recorded deals", GREEN if at.get("outreach_revenue") else AMBER, ""),
        ("Volume vs value", len(_L(at.get("matrix"))), "sources compared",
         _riskmatrix([(s, a, b) for s, a, b in _L(at.get("matrix"))]),
         ("Lead volume against revenue produced. A source high on volume and "
          "low on value is where your credits are going to waste."),
         "computed", BLUE if at.get("matrix") else AMBER, ""),
        ("Deals by source", len(_L(at.get("deals_by_source"))), "attributed",
         _hbars([(s[:18], v) for s, v in _L(at.get("deals_by_source"))]),
         "Count rather than value — a source can win many small deals.",
         "recorded deals", BLUE, ""),
        ("Total attributed", _money(at.get("total")), "recorded revenue", "",
         "Every recorded deal carries the source it came from.",
         "recorded deals", GREEN if at.get("total") else AMBER, ""),
    ]
    cards += _slots(
        by_src, 5,
        lambda i, r: (f"Source: {str(r[0])[:20]}", _money(r[1]), "revenue",
                      _donut(round(100 * _f(r[1]) / max(_f(at.get("total")), 1))),
                      "Recorded revenue attributed to this source at deal entry.",
                      "recorded deals", BLUE),
        "Source", "no revenue yet",
        ("Each deal is tagged outreach, organic, ads, referral or direct when "
         "recorded. This fills with the next source that pays."),
        "recorded deals", AMBER)
    cards += [
        ("Lead source volume", _i(sc.get("found")), "leads sourced",
         _hbars([(s[:18], v) for s, v in _L(sc.get("by_source"))[:6]]),
         "The volume half of the comparison above.",
         "lead source stamp", BLUE, ""),
        ("Cost per deal", _money(_D(ctx["costs"]).get("per_deal")), "outreach spend",
         "", ("The number that decides whether outreach pays for itself."
              if _D(ctx["costs"]).get("per_deal") else "Needs one recorded deal."),
         "computed", GREEN if _D(ctx["costs"]).get("per_deal") else AMBER, ""),
        ("Return on outreach spend",
         (f"{_D(ctx['costs']).get('roi')}%"
          if _D(ctx["costs"]).get("roi") is not None else "—"),
         "revenue vs cost", "",
         ("Outreach revenue minus outreach cost, over cost."
          if _D(ctx["costs"]).get("roi") is not None else
          "The cost half is measured; the revenue half needs a recorded deal."),
         "computed", GREEN if _f(_D(ctx["costs"]).get("roi")) > 0 else AMBER, ""),
        ("Best-paying source", (by_src[0][0] if by_src else "—"),
         _money(by_src[0][1]) if by_src else "no deals yet", "",
         "Where to spend the next sourcing credit.",
         "recorded deals", GREEN if by_src else AMBER, ""),
        ("Where to act", "record every win", "with its source", "",
         "Attribution is only as good as the tagging at deal entry.",
         "navigation", VIOLET,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Feeds BI", "yes", "same recorded deals", "",
         "This board and BI's revenue boards read the same entries.",
         "navigation", BLUE,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
    ]
    return _head("🔗", "Lead → deal attribution",
                 "Which sourcing channel actually produced revenue.") + _vizcards(cards[:16])


# ======================================================================
#  (13) COST PER OUTCOME  (12)
# ======================================================================
def board_costs(ctx) -> str:
    ctx = _ctx(ctx)
    c = ctx["costs"]
    rows = [(n, v) for n, v in _L(c.get("rows")) if v is not None]
    cards = [
        ("Outreach spend", _money(c.get("cost")), "all campaigns",
         _hbars([(n, _f(v)) for n, v in rows]),
         "What sourcing, verifying and sending has cost in total.",
         "job costs", BLUE if c.get("cost") else AMBER, ""),
        ("Cost per lead", _money(c.get("per_lead")), "sourced", "",
         ("Spend divided by leads found. It says nothing about whether "
          "those leads were worth finding in the first place."),
         "computed", GREEN if c.get("per_lead") else AMBER, ""),
        ("Cost per send", _money(c.get("per_send")), "email", "",
         "Cheap per send. The number that matters is the next one down.",
         "computed", GREEN if c.get("per_send") else AMBER, ""),
        ("Cost per reply", _money(c.get("per_reply")), "response", "",
         "The real unit cost at the top of the sales funnel.",
         "computed", GREEN if c.get("per_reply") else AMBER, ""),
        ("Cost per booking", _money(c.get("per_booking")), "consultation", "",
         "What one qualified call in the calendar costs.",
         "computed", GREEN if c.get("per_booking") else AMBER, ""),
        ("Cost per deal", _money(c.get("per_deal")), "won", "",
         ("Needs one recorded deal." if not c.get("per_deal") else
          "The number the whole channel is judged on."),
         "computed", GREEN if c.get("per_deal") else AMBER, ""),
        ("Revenue attributed", _money(c.get("revenue")), "from recorded deals", "",
         "The other half of the return calculation.",
         "recorded deals", GREEN if c.get("revenue") else AMBER, ""),
        ("Return on spend",
         (f"{c.get('roi')}%" if c.get("roi") is not None else "—"),
         "revenue vs cost",
         _score_gauge(min(100, max(0, _f(c.get("roi")) / 10)), 50)
         if c.get("roi") is not None else "",
         ("Revenue minus cost, over cost." if c.get("roi") is not None
          else "Needs a recorded deal."),
         "computed", GREEN if _f(c.get("roi")) > 0 else AMBER, ""),
        ("Cost per lead by campaign",
         _n(_D(ctx.get("campaign_costs")).get("avg")), "average across campaigns",
         _CH().confband(_L(_D(ctx.get("campaign_costs")).get("values")), band=0.25)
         if _D(ctx.get("campaign_costs")).get("ready") else "",
         _D(ctx.get("campaign_costs")).get("note", ""),
         "per-campaign costs",
         GREEN if _D(ctx.get("campaign_costs")).get("ready") else AMBER, ""),
        ("Every unit cost", len(rows), "measured",
         _hbars([(n, _f(v)) for n, v in rows]),
         "Per lead, per send, per reply, per booking, per deal — one chart.",
         "computed", BLUE, ""),
        ("Cheapest improvement", "reply rate", "not more volume", "",
         ("Doubling the reply rate halves the cost per reply, per booking and "
          "per deal at once. Doubling volume only doubles the spend."),
         "computed", VIOLET, ""),
        ("Where to act", "BI", "business-wide economics", "",
         "This board is the outreach channel. BI is the whole business.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
    ]
    return _head("🧾", "Cost per outcome",
                 "What one lead, one send, one reply, one call and one deal "
                 "cost.") + _vizcards(cards[:12])


def _lead_manager_table(rows) -> str:
    """The table the old sections never had: LinkedIn, phone, country, source
    and the collection date AND time, with an Edit and a Delete on every row."""
    H = _H()
    rows = _L(rows)
    if not rows:
        return ("<div class='card full' style='margin-top:12px'>"
                "<p class='ct'>🗂 Lead manager</p><p class='cc'>No leads yet. "
                "Source a batch from the Launch Pad and every one of them "
                "appears here with its own row, editable and removable.</p></div>")
    head = ("<tr><th>Lead</th><th>Company</th><th>LinkedIn</th><th>Phone</th>"
            "<th>Country</th><th>Source</th><th>Collected</th><th>Fit</th>"
            "<th>Status</th><th>Manage</th></tr>")
    body = []
    for r in rows[:200]:
        r = _D(r)
        e = H._esc(str(r.get("email", "")))
        li = str(r.get("linkedin") or "")
        li_html = (f"<a href='{H._esc(li)}' target='_blank' rel='noopener' "
                   f"style='color:#4C8DFF'>profile</a>" if li.startswith("http")
                   else "<span class='dim'>—</span>")
        col = str(r.get("collected_at") or "")
        col_html = (f"{H._esc(col[:10])}<div class='dim'>{H._esc(col[11:16])}</div>"
                    if col else "<span class='dim'>not stamped</span>")
        fit = r.get("fit")
        st = str(r.get("status") or "")
        scol = {"emailed": "#3FD98B", "removed": "#F5788A"}.get(st, "#8E9BBE")
        body.append(
            f"<tr><td><b>{H._esc(str(r.get('name') or '—'))}</b>"
            f"<div class='dim'>{H._esc(str(r.get('title') or ''))}</div>"
            f"<div class='dim'>{e}</div></td>"
            f"<td>{H._esc(str(r.get('company') or '—'))}"
            f"<div class='dim'>{H._esc(str(r.get('vertical') or ''))}</div></td>"
            f"<td>{li_html}</td>"
            f"<td class='mut'>{H._esc(str(r.get('phone') or '—'))}</td>"
            f"<td class='mut'>{H._esc(str(r.get('country') or '—'))}</td>"
            f"<td class='mut'>{H._esc(str(r.get('source') or '—'))}</td>"
            f"<td class='mut'>{col_html}</td>"
            f"<td class='tnum'>{'—' if fit in (None, '') else H._esc(str(fit))}</td>"
            f"<td><span style='color:{scol};font-weight:600'>● {H._esc(st)}</span>"
            f"<div class='dim'>{r.get('touches', 0)} sent</div></td>"
            f"<td><button class='sbtn' onclick=\"leadEdit('{H._esc(str(r.get('job')))}','{e}')\">Edit</button>"
            f"<button class='sbtn' style='background:transparent;border:1px solid #F5788A;color:#F5788A;margin-left:4px' "
            f"onclick=\"leadDelete('{H._esc(str(r.get('job')))}','{e}')\">Delete</button></td></tr>")
    return ("<div class='card full' style='margin-top:12px'>"
            f"<p class='ct'>🗂 Lead manager — {len(rows)} leads</p>"
            "<p class='cc'>Every lead with the fields the old table never showed: "
            "LinkedIn, phone, country, source and the exact date and time it was "
            "collected. <b>Edit</b> fixes a wrong detail; <b>Delete</b> removes the "
            "lead and suppresses the address so it can never be emailed.</p>"
            f"<div class='tbwrap'><table><thead>{head}</thead><tbody>"
            + "".join(body) + "</tbody></table></div></div>")


# ======================================================================
#  (14) LEAD MANAGER  (16)
# ======================================================================
def board_manager(ctx) -> str:
    ctx = _ctx(ctx)
    rows = _L(ctx.get("lead_rows"))
    lpd = _D(ctx.get("leads_per_day"))
    cov = _L(ctx.get("field_coverage"))
    sc = ctx["sourcing"]
    covd = {c: (n, p) for c, n, p in cov} if cov else {}
    cards = [
        ("Leads collected per day", _i(lpd.get("total")), "with a timestamp",
         _trend([("leads/day", _L(lpd.get("series")), TEAL)]),
         (("Counted from each lead's own collected_at. The old chart bucketed by "
           "CAMPAIGN date, so a batch of sixty showed as one sixty-lead day and "
           "every other day read zero. " + str(lpd.get("note", ""))).strip()),
         "per-lead timestamp", GREEN if lpd.get("has_data") else AMBER, ""),
        ("Busiest day", _i(lpd.get("busiest")), "leads in one day",
         _histogram([_i(v) for v in _L(lpd.get("series"))]),
         ("What a good sourcing day looks like, so an ordinary day has "
          "something to be compared against."),
         "per-lead timestamp", BLUE, ""),
        ("Daily average", _n(lpd.get("avg")), "leads per active day", "",
         f"Across {_i(lpd.get('days_active'))} days that produced any lead.",
         "computed", BLUE, ""),
        ("Not timestamped", _i(lpd.get("undated")), "sourced before the stamp",
         "", ("Counted in the total but left off the chart — putting them on "
              "today would invent a sourcing day that never happened."),
         "computed", AMBER if lpd.get("undated") else GREEN, ""),
        ("Leads on file", len(rows), "in the manager below", "",
         "Every lead across every campaign, newest first.",
         "lead records", GREEN if rows else AMBER, ""),
        ("Field coverage", len(cov), "columns measured",
         _hbars([(c, p) for c, _n2, p in cov]),
         ("How many leads actually carry each field. An empty column here is a "
          "sourcing gap, not a broken table."),
         "lead records", BLUE if cov else AMBER, ""),
    ]
    for col, label, why in (
            ("linkedin", "LinkedIn profiles",
             "Prospeo returns the profile URL. It was being read and thrown "
             "away, so this column could never fill. New leads carry it."),
            ("phone", "Phone numbers",
             "Google Maps leads carry a phone; Prospeo ones usually do not."),
            ("country", "Country recorded",
             "Without it a lead cannot be counted toward any target market."),
            ("collected_at", "Timestamped",
             "Date and time the lead entered the pipeline."),
            ("vertical", "Vertical recorded",
             "Needed to score a lead against your ICP."),
            ("company", "Company recorded",
             "The single most-used field in a personalized opener.")):
        n, pc = covd.get(col, (0, 0))
        cards.append((label, n, f"{pc}% of leads",
                      _donut(pc), why, "lead records",
                      GREEN if pc >= 80 else AMBER if pc >= 30 else PINK, ""))
    cards += [
        ("Edit a lead", "per row", "fix a wrong detail", "",
         ("There was no way to correct a lead anywhere in the engine. A blank "
          "box leaves the existing value alone rather than wiping it."),
         "/leads/edit", GREEN, ""),
        ("Delete a lead", "per row", "removes and suppresses", "",
         ("Soft delete: the lead leaves the sendable list and the address is "
          "suppressed so it can never be emailed, but the record is kept — a "
          "lead you paid to source is still evidence about your sourcing."),
         "/leads/delete", GREEN, ""),
        ("Sources represented", len(_L(sc.get("by_source"))), "distinct",
         _hbars([(s2[:18], v) for s2, v in _L(sc.get("by_source"))[:6]]),
         "Every row shows which provider found that lead.",
         "lead source stamp", BLUE, ""),
        ("Where to act", "the table below", "edit, delete, open LinkedIn", "",
         ("The controls for this sit under this board, so you can act on "
          "it without leaving the page."),
         "navigation", VIOLET, ""),
    ]
    return (_head("🗂", "Lead manager",
                  "Every lead, every detail, editable — and how many arrive "
                  "each day.")
            + _vizcards(cards[:16]) + _lead_manager_table(rows))



# ======================================================================
#  SECTION
# ======================================================================
TABS = [
    # KLAVIYO'S WORDS (founder's order, 2026-08-06). The labels used to read
    # "Launch Pad", "The Outbox", "ICP & Scoring", "Routing" - the engine's
    # internal vocabulary. Ids are unchanged so every link still lands.
    ("olaunch", "\U0001F4CA", "Dashboard"),
    ("ooutbox", "\U0001F4E8", "Campaigns"),
    ("osequence", "\U0001F501", "Flows"),
    ("omanager", "\U0001F464", "Profiles"),
    ("oicp", "\U0001F3AF", "Segments"),
    ("orouting", "\U0001F441", "Preview"),
    ("osourcing", "\U0001F50D", "Lists"),
    ("oquality", "\U0001F9F9", "Data quality"),
    ("oterr", "\U0001F30D", "Geography"),
    ("odeliver", "\U0001F4EE", "Deliverability"),
    ("oreplies", "\U0001F4AC", "Inbox"),
    ("obookings", "\U0001F4C5", "Conversions"),
    ("oattrib", "\U0001F517", "Attribution"),
    ("ocost", "\U0001F4C9", "Benchmarks"),
]

GROUPS = [
    ("ofind", "① FIND THEM", "Who are we writing to?",
     ["olaunch", "osourcing", "omanager", "oquality", "oicp", "oterr"]),
    ("osend", "② SEND IT", "What goes out, and safely?",
     ["ooutbox", "osequence", "orouting", "odeliver"]),
    ("oback", "③ WHAT CAME BACK", "Did anyone answer?",
     ["oreplies", "obookings"]),
    ("opay", "④ DOES IT PAY", "Was it worth it?",
     ["oattrib", "ocost"]),
]

_TAB_BOARDS = {
    "olaunch": [("Launch Pad", board_launch)],
    "osourcing": [("Lead Sourcing", board_sourcing)],
    "omanager": [("Lead Manager", board_manager)],
    "oquality": [("Lead Quality", board_quality)],
    "oicp": [("ICP & Scoring", board_icp)],
    "oterr": [("Territories", board_territories)],
    "ooutbox": [("The Outbox", board_outbox)],
    "osequence": [("Sequence", board_sequence)],
    "orouting": [("Routing", board_routing)],
    "odeliver": [("Deliverability", board_deliverability)],
    "oreplies": [("Replies", board_replies)],
    "obookings": [("Bookings", board_bookings)],
    "oattrib": [("Attribution", board_attribution)],
    "ocost": [("Cost per Outcome", board_costs)],
}

_TAB_COUNTS = {"olaunch": 16, "osourcing": 20, "omanager": 16, "oquality": 18, "oicp": 18,
               "oterr": 18, "ooutbox": 18, "osequence": 18, "orouting": 16,
               "odeliver": 20, "oreplies": 18, "obookings": 16, "oattrib": 16,
               "ocost": 12}
TOTAL_CARDS = sum(_TAB_COUNTS.values())


def _safe_board(name, fn, ctx) -> str:
    _CURRENT_BOARD["name"] = name
    try:
        return fn(ctx)
    except Exception as e:
        H = _H()
        return ("<div class='card full' style='margin-top:12px;border-color:#FF6B93'>"
                f"<p class='ct'>⚠ {H._esc(name)} board failed to render</p>"
                f"<p class='cc'>{H._esc(type(e).__name__)}: {H._esc(str(e)[:300])}</p>"
                "<p class='cc'>Every other board is unaffected.</p></div>")


def outreach_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def outreach_section(ctx, live=None) -> str:
    """Klaviyo grammar: one band, one tab strip, one panel.

    THE LEGACY CHROME IS GONE. The group rail and the run bar were a second
    and third navigation grammar stacked on the section - the exact
    fragmentation the founder scored 0/10 on SGA. The band carries what the
    run bar used to.

    `live` keeps its old meaning: pre-rendered interactive blocks (the real
    send controls) that must not be re-implemented here. They are appended
    to the Campaigns panel so no send path changes.
    """
    H = _H()
    ctx = ctx if isinstance(ctx, dict) else {}
    import content_engine_outreach_screens as OLS
    import content_engine_seo_screens as SSCR
    panels = OLS.build_panels(ctx)
    if live:
        panels["ooutbox"] = (panels.get("ooutbox", "")
                             + "<p class='ol-k'>Send controls</p>"
                             + str(live))
    # A chip counts a real thing or nothing at all.
    _camps = ctx.get("campaigns") or []
    _q = ctx.get("flow_queue") or []
    _dr = ctx.get("reply_drafts") or []
    _sg = ctx.get("segments") or []
    _chips = {"ooutbox": len(_camps) or None, "osequence": len(_q) or None,
              "oreplies": len(_dr) or None, "oicp": len(_sg) or None}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"onclick=\"seoTab('{tid}')\"><span>{icon}</span>{H._esc(label)}"
        + (f"<span class='n'>{_chips[tid]}</span>"
           if _chips.get(tid) is not None else "")
        + "</button>"
        for i, (tid, icon, label) in enumerate(TABS))
    body = "".join(
        f"<div class='spanel{' on' if i == 0 else ''}' id='spanel-{tid}'>"
        f"{panels.get(tid, '')}</div>"
        for i, (tid, _, _) in enumerate(TABS))
    bridge = ("<style>.seoscr{--pap:var(--s2);--card:var(--s1);"
              "--ln:var(--line);--tx:var(--ink);--dm:var(--mut);"
              "--ft:var(--dim);--ac:var(--blue);--warnc:var(--warn);"
              "--okc:var(--good);--badbg:rgba(255,107,147,.09);"
              "--warnbg:rgba(245,177,76,.09);--okbg:rgba(63,217,139,.09);"
              "--hov:rgba(76,141,255,.07)}"
              + SSCR.CSS + OLS.CSS + "</style>")
    return ("<div class='seoscr'>" + bridge + SSCR.JS + OLS.JS
            + _TAB_CSS + OLS.band(ctx)
            + "<div class='stabs'>" + bar + "</div>"
            + "<div class='spanels'>" + body + "</div></div>")


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_outreach as O

    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()
    O.set_tracking(st, True)
    tok = O.register_token(st, "o1", "p0@x.com", 1)
    O.record_event(st, tok, "open")
    O.record_event(st, tok, "click")

    jobs = [{"job_id": "o1", "type": "outreach_campaign", "status": "sent",
             "created_at": "2026-07-20T09:00:00Z", "cost_so_far_usd": 1.2,
             "payload": {
                 "raw_leads": [{"email": f"p{i}@x.com", "name": f"P{i}",
                                "company": "C", "title": "Dr", "website": "w",
                                "country": "Germany" if i % 2 else "United States",
                                "vertical": "doctor", "score": 55 + i * 3,
                                "source": "maps" if i % 3 else "prospeo"}
                               for i in range(9)],
                 "leads": [{"email": f"p{i}@x.com", "name": f"P{i}", "company": "C",
                            "title": "Dr", "website": "w",
                            "country": "Germany" if i % 2 else "United States",
                            "vertical": "doctor", "score": 55 + i * 3,
                            "source": "maps" if i % 3 else "prospeo"}
                           for i in range(7)],
                 "lead_qualifier": {"results": [{}] * 5},
                 "send_ref": "x",
                 "sent_at": {"p0@x.com": ["2026-07-21T09:00:00+00:00",
                                          "2026-07-24T09:00:00+00:00"],
                             "p1@x.com": ["2026-07-22T09:00:00+00:00"]},
                 "sent_meta": {"p0@x.com": [{"alias": "marketing@a.com", "step": 1,
                                             "subject": "Quick question"},
                                            {"alias": "marketing@a.com", "step": 2,
                                             "subject": "Following up"}],
                               "p1@x.com": [{"alias": "contact@a.com", "step": 1,
                                             "subject": "Quick question"}]}}}]
    drafts = [{"intent": "question"}, {}, {}]
    cal = [{"status": "accepted", "start": "2026-08-04T10:00:00Z", "title": "Intro"}]
    deals = [{"client": "A", "value": 6000, "source": "outreach"},
             {"client": "B", "value": 2000, "source": "organic"}]

    sc = O.sourcing(jobs)
    sd = O.sends(jobs)
    rp = O.replies(drafts, sd)
    bk = O.bookings(cal, rp)
    ctx = {
        "sourcing": sc, "quality": O.quality(jobs), "icp": O.icp(jobs),
        "territories": O.territories(jobs), "sends": sd,
        "sequence": O.sequence(jobs), "routing": O.routing(sd),
        "deliverability": O.deliverability(st, sd, ["a@x.com", "b@x.com"],
                                           {"a@x.com": {"reason": "bounce"},
                                            "b@x.com": {"reason": "unsubscribe"}},
                                           sent_today=4, cap=15),
        "replies": rp, "bookings": bk,
        "attribution": O.attribution(deals, sc, sd),
        "costs": O.unit_costs(sc, sd, rp, bk, deals, outreach_cost=1.2),
        "tracking": O.tracking_stats(st, sends=sd["total"]),
        "sourcing_mom": O.sourcing_mom(jobs),
        "suppression_heat": O.suppression_heat(
            {"a@x.com": {"reason": "bounce", "at": "2026-07-30"},
             "b@x.com": {"reason": "unsubscribe", "at": "2026-07-29"}}),
        "campaign_costs": O.campaign_costs(jobs),
        "sends_cohort": O.sends_cohort(jobs),
        "lead_rows": O.lead_rows(jobs),
        "leads_per_day": O.leads_per_day(jobs),
        "field_coverage": O.lead_field_coverage(jobs),
        "live": {"outbox": "<div id='LIVE-OUTBOX'>outbox</div>",
                 "replies": "<div id='LIVE-REPLIES'>replies</div>",
                 "leads_table": "<div id='LIVE-LEADS'>leads</div>",
                 "maps_form": "<div id='LIVE-MAPS'>maps</div>",
                 "outbox_pointer": "<div id='LIVE-PTR'>ptr</div>"},
    }

    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        _CURRENT_BOARD["name"] = name
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = outreach_pages(ctx)
    assert set(pages) == {t for t, _, _ in TABS}, list(pages)
    html = "".join(pages.values())
    assert "failed to render" not in html

    counted = len(re.findall(r"<div class='card (?:overflowcard )?sev-", html))
    assert counted == TOTAL_CARDS, f"expected {TOTAL_CARDS}, rendered {counted}"
    for tab, want in _TAB_COUNTS.items():
        got = len(re.findall(r"<div class='card (?:overflowcard )?sev-", pages[tab]))
        assert got == want, f"{tab}: {got} != {want}"
    ids = re.findall(r"<div class='card (?:overflowcard )?sev-[a-z]+' id='(card-[a-z0-9-]+)'", html)
    assert len(ids) == TOTAL_CARDS and len(set(ids)) == len(ids), (len(ids), len(set(ids)))
    assert html.count("class='cta'") >= TOTAL_CARDS

    # THE launch pad must still be a launch pad: every live block carried over
    for marker in ("LIVE-OUTBOX", "LIVE-REPLIES", "LIVE-MAPS", "LIVE-PTR",
                   "LIVE-LEADS"):
        assert marker in html, f"{marker} was not carried over"
    for endpoint in ("/outreach/send_all", "/replies/refresh"):
        assert endpoint in html, f"{endpoint} is no longer reachable from the UI"

    # every fabricated number is gone
    assert "Prospeo (LinkedIn)" not in html, "the hardcoded 0 bar must not survive"
    assert "verified deliverable" not in html or "actual share" in html
    assert "assumed every outreach email" in pages["orouting"], \
        "say plainly that the alias was previously assumed"
    assert "a literal" in pages["oquality"], "call out the 100% donut"

    # the lead manager: the columns the old table never had, and real buttons
    for col in ("LinkedIn", "Phone", "Country", "Source", "Collected"):
        assert col in pages["omanager"], f"{col} column missing"
    assert "leadEdit(" in pages["omanager"] and "leadDelete(" in pages["omanager"], \
        "every row needs an Edit and a Delete"
    assert "CAMPAIGN date" in pages["omanager"], \
        "say why leads-per-day used to be wrong"

    # tracking states both costs
    assert "Apple Mail" in pages["odeliver"], "the open-tracking caveat"
    assert "GDPR" in pages["odeliver"], "the Germany/Switzerland note"

    # the honest-degrade contract holds on an empty context
    empty = outreach_pages({})
    ehtml = "".join(empty.values())
    assert "failed to render" not in ehtml
    assert len(re.findall(r"<div class='card (?:overflowcard )?sev-", ehtml)) == TOTAL_CARDS

    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {k: 0 for k in ctx}, {"live": "no"}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    charts = len(re.findall(r"<svg", html))
    print(f"outreach_boards self-check OK — {len(_TAB_BOARDS)} boards, {counted} "
          f"cards, {len(set(ids))} unique ids, {charts} charts; the outbox, "
          f"replies inbox, leads table and Maps form all carried over live, and "
          f"every fabricated number is gone rather than restyled.")
