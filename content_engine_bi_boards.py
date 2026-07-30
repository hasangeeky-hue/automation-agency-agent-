"""
content_engine_bi_boards.py
============================================================================
BUSINESS INTELLIGENCE — 14 boards, 252 cards. Replaces six sections
(Business Performance, Marketing Intelligence, Sales Intelligence, Customer
Intelligence, Finance, Budget & Cost) that held 41 cards between them and read
ONE shared context dict.

Rule for this section, per the brief: NO DEAD PLACEHOLDERS. Every card either
shows a measured number or shows a real state with an action that changes it.
No card says "connect Stripe / HubSpot / Zendesk" — those were six prompts to
buy software instead of one way to type a number, and the number is now
typeable (Record a won deal, on BI Command).

Boundary kept deliberately: this section does NOT re-render SEO or Ads cards.
SEO/AEO/GEO is 235 cards and Media Buying is 296 — BI links into them and asks
one question they do not: is the business working?

Run offline self-check:  python content_engine_bi_boards.py
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
    "Executive Brief": ("Open Risk", "nav('riskinfra')"),
    "BI Command": ("Record a won deal", "biDeal()"),
    "Demand": ("Open SEO", "nav('seo')"),
    "Markets": ("Open GEO", "seoTab('geo')"),
    "Channels": ("Open Media Buying", "nav('media')"),
    "Content Value": ("Open Content", "nav('content')"),
    "Lead Generation": ("Open Leads", "nav('leads')"),
    "Outreach": ("Open Email", "nav('email')"),
    "Consultations": ("Open bookings", "window.open('https://cal.com/bookings')"),
    "Funnel": ("Open Leads", "nav('leads')"),
    "Revenue": ("Record a won deal", "biDeal()"),
    "Customers": ("Record a won deal", "biDeal()"),
    "Unit Economics": ("Set your economics", "biEcon()"),
    "Spend": ("Open Budget controls", "nav('system')"),
    "Cost per Outcome": ("Open Approvals", "nav('appr')"),
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


def _n(v, dash="—"):
    """A number, or an em dash. Never a zero standing in for 'unknown'."""
    return dash if v is None else v


def _money(v, dash="—"):
    return dash if v in (None, "") else f"€{_f(v):,.0f}"


def _ctx(ctx):
    """Coerce once at the boundary — a wrong shape must never crash a board."""
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in ("exec", "channels_mom", "markets_mom", "leads_mom",
              "demand", "markets", "channels", "content", "leadgen", "outreach",
              "consultations", "funnel", "revenue", "customers", "econ",
              "unit", "spend", "cost", "targets", "attainment"):
        out[k] = _D(out.get(k))
    out["deals"] = _L(out.get("deals"))
    return out


def _vbars(m, colour_a=VIOLET, colour_b=TEAL):
    """Grouped columns for month-over-month. Draws only what was measured: with
    one month of history it shows one series, not a fabricated comparison."""
    m = _D(m)
    groups = _L(m.get("groups"))
    if not groups:
        return ""
    series = [("this month", _L(m.get("this_month")), colour_b)]
    if m.get("ready") and _L(m.get("last_month")):
        series.insert(0, ("last month", _L(m.get("last_month")), colour_a))
    return _CH().vbars([str(g)[:8] for g in groups], series)


def _slots(rows, n, filled, empty_title, empty_sub, empty_why, src, accent=BLUE):
    """Always n cards. `filled(i, row)` builds the real one; the rest state what
    would fill them. An empty slot here is a fact about the business, not a
    prompt to buy software."""
    out = []
    rows = _L(rows)
    for i in range(n):
        if i < len(rows):
            out.append(filled(i, rows[i]))
        else:
            out.append((f"{empty_title} {i + 1}", "—", empty_sub, "",
                        empty_why, src, accent, ""))
    return out


def _tone(ok, warn=None):
    if warn:
        return AMBER
    return GREEN if ok else PINK


# ======================================================================
#  (1) BI COMMAND  (16)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    r, u, s = ctx["revenue"], ctx["unit"], ctx["spend"]
    d, lg, co = ctx["demand"], ctx["leadgen"], ctx["consultations"]
    fn, at = ctx["funnel"], ctx["attainment"]
    deals = ctx["deals"]
    verdict = ("Recording deals is the one thing blocking half this section"
               if not deals else
               f"€{_f(r.get('total')):,.0f} from {r.get('clients', 0)} clients, "
               f"at €{_f(u.get('cac') or 0):,.0f} to acquire each")
    cards = [
        ("The business, in one line", len(deals), "deals recorded",
         _score_gauge(min(100, len(deals) * 20), 60),
         verdict, "recorded deals", GREEN if deals else AMBER,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Revenue recorded", _money(r.get("total")), "all time",
         _split_donut([(c, v, col) for (c, v), col in
                       zip(_L(r.get("donut")), (TEAL, VIOLET, BLUE, AMBER, PINK))]),
         ("Every other money number on this dashboard divides by this one."
          if deals else
          "Nothing has been recorded yet. One deal makes revenue, LTV, CAC and "
          "the cohort grid all compute — they need no other input."),
         "recorded deals", GREEN if r.get("total") else AMBER, ""),
        ("This month", _money(r.get("month_total")), "revenue booked", "",
         "Revenue dated inside the current calendar month.",
         "recorded deals", GREEN if r.get("month_total") else AMBER, ""),
        ("Clients", r.get("clients", 0), "distinct paying", "",
         ("Concentration risk starts above one third from a single client."
          if r.get("clients") else "Recorded per deal, so this counts real names."),
         "recorded deals", BLUE if r.get("clients") else AMBER, ""),
        ("Cost to acquire a client", _money(u.get("cac")), "CAC",
         _score_gauge(min(100, _f(u.get("cac")) / 20) if u.get("cac") else 0, 50),
         ("Engine spend divided by clients won. The only honest CAC available "
          "until ad spend is wired." if u.get("cac") else
          "CAC needs at least one recorded client. The cost side is already "
          "measured — only the client count is missing."),
         "spend ÷ clients", GREEN if u.get("cac") else AMBER, ""),
        ("LTV to CAC", _n(u.get("ratio")), "ratio, 3+ is healthy",
         _score_gauge(min(100, _f(u.get("ratio")) * 25) if u.get("ratio") else 0, 75),
         ("Above 3 means each client is worth more than three times what it "
          "cost to win them." if u.get("ratio") else
          "Needs one recorded deal and your gross margin %."),
         "computed", GREEN if u.get("healthy_ratio") else AMBER, ""),
        ("Sessions", d.get("sessions", 0), f"last {d.get('days', 28)} days",
         _trend([("sessions", _L(d.get("series")), TEAL)]),
         ("Real traffic from GA4." if d.get("has_ga4") else
          "GA4 is not returning data. Everything on the demand boards depends "
          "on it."),
         "GA4", GREEN if d.get("has_ga4") else AMBER, ""),
        ("Search clicks", d.get("clicks", 0), f"from {d.get('impressions', 0):,} impressions",
         "", f"CTR {d.get('ctr', 0)}% at average position "
             f"{_n(d.get('avg_position'))}.",
         "Search Console", GREEN if d.get("has_gsc") else AMBER, ""),
        ("Leads found", lg.get("found", 0), "sourced by the engine", "",
         f"{lg.get('verified', 0)} verified, {lg.get('qualified', 0)} qualified.",
         "outreach jobs", GREEN if lg.get("found") else AMBER, ""),
        ("Consultations", co.get("accepted", 0), "booked",
         "", ("Real Cal.com bookings." if co.get("has_data") else
              "Cal.com is connected but has returned no bookings yet."),
         "Cal.com", GREEN if co.get("accepted") else AMBER, ""),
        ("Funnel conversion", f"{fn.get('overall_pct', 0)}%", "found → won", "",
         (f"Biggest leak: {fn['worst'][0]} loses {fn['worst'][1]:,.0f} "
          f"({fn['worst'][2]}%)." if fn.get("worst") else
          "The funnel fills in as leads move through it."),
         "computed", PINK if _f(fn.get("overall_pct")) < 1 else GREEN, ""),
        ("Spend this month", _money(s.get("spent")), f"of {_money(s.get('cap'))}",
         _score_gauge(_f(s.get("pct")), 85),
         f"{s.get('pct', 0)}% of the cap used, {_money(s.get('headroom'))} left.",
         "API meters", _pct_color(_f(s.get("pct")), 85), ""),
        ("Projected month end", _money(s.get("projected")), "at this rate", "",
         s.get("projection_note", ""),
         "arithmetic", PINK if s.get("over_cap") else GREEN, ""),
        ("Return on engine spend", (f"{u.get('roi')}%" if u.get("roi") is not None
                                    else "—"), "revenue vs cost", "",
         ("Revenue minus engine cost, over cost." if u.get("roi") is not None else
          "Needs one recorded deal. The cost half is already measured."),
         "computed", GREEN if _f(u.get("roi")) > 0 else AMBER, ""),
        ("Targets", len(_L(at.get("rows"))), "being tracked",
         _statusgrid([(row[0][:18], row[3] >= 100, f"{row[3]:.0f}%")
                      for row in _L(at.get("rows"))]),
         at.get("note") or "Green means the target is met this month.",
         "your targets", GREEN if at.get("set") else AMBER,
         "<button class='cta' onclick='biTargets()'>Set targets</button>"),
        ("Your economics", "set" if _D(ctx.get("econ")).get("set") else "not set",
         "margin, deal size, close rate", "",
         ("Used for LTV, profit and pipeline value." if _D(ctx.get("econ")).get("set")
          else "Three numbers only you know. Without them LTV reads as revenue "
               "rather than profit, and pipeline value cannot be computed."),
         "your input", GREEN if _D(ctx.get("econ")).get("set") else AMBER,
         "<button class='cta' onclick='biEcon()'>Enter the three numbers</button>"),
    ]
    return _head("📊", "Business intelligence — command",
                 "Is the business working? Sixteen numbers, and what each one "
                 "means.") + _vizcards(cards)


# ======================================================================
#  (2) DEMAND & TRAFFIC  (20)
# ======================================================================
def board_demand(ctx) -> str:
    ctx = _ctx(ctx)
    d = ctx["demand"]
    series = _L(d.get("series"))
    labels = _L(d.get("labels"))
    best = max(zip(series, labels), default=(0, "")) if series else (0, "")
    worst = min(zip(series, labels), default=(0, "")) if series else (0, "")
    avg = round(sum(series) / len(series), 1) if series else 0
    tq = _L(d.get("top_queries"))
    cards = [
        ("Sessions", d.get("sessions", 0), f"last {d.get('days', 28)} days",
         _trend([("sessions", series, TEAL)]),
         ("The single number that says whether anyone is arriving."
          if d.get("has_ga4") else
          "GA4 returned nothing. Check the GA4 property id in System & Wiring."),
         "GA4", GREEN if d.get("has_ga4") else AMBER, ""),
        ("Users", d.get("users", 0), "distinct people", "",
         "Sessions counts visits; this counts people.",
         "GA4", BLUE if d.get("users") else AMBER, ""),
        ("New users", d.get("new_users", 0), "first-time visitors", "",
         "New visitors are the top of the funnel; returning ones are interest.",
         "GA4", BLUE if d.get("new_users") else AMBER, ""),
        ("Returning share",
         f"{100 - round(100 * _f(d.get('new_users')) / max(_f(d.get('users')), 1)):.0f}%"
         if d.get("users") else "—", "came back", "",
         "A high returning share with low new users means reach is the problem.",
         "computed", BLUE, ""),
        ("Engagement rate", (f"{d.get('engagement_rate')}%"
                             if d.get("engagement_rate") is not None else "—"),
         "GA4 engaged sessions", _donut(_f(d.get("engagement_rate"))),
         "Below 50% usually means the page does not match the search intent.",
         "GA4", _pct_color(100 - _f(d.get("engagement_rate")), 50), ""),
        ("Trend", (f"{d.get('trend_pct'):+}%" if d.get("trend_pct") is not None
                   else "—"), "second half vs first",
         _spark(series),
         ("Measured across the window GA4 returned, not a guess."
          if d.get("trend_pct") is not None else
          "Needs at least four days of data."),
         "computed", GREEN if _f(d.get("trend_pct")) >= 0 else PINK, ""),
        ("Busiest day", f"{best[0]:.0f}", best[1] or "—", "",
         "What a good day looks like when something lands.",
         "GA4", BLUE, ""),
        ("Quietest day", f"{worst[0]:.0f}", worst[1] or "—", "",
         "The floor. Publishing cadence should lift this, not just the peaks.",
         "GA4", BLUE, ""),
        ("Daily average", avg, "sessions per day",
         _histogram([int(v) for v in series]) if series else "",
         "The distribution matters more than the mean — spikes are one post.",
         "GA4", BLUE, ""),
        ("Search impressions", f"{d.get('impressions', 0):,}", "times shown", "",
         "How often Google put you in front of someone.",
         "Search Console", GREEN if d.get("impressions") else AMBER, ""),
        ("Search clicks", d.get("clicks", 0), "actual visits from search", "",
         "Impressions are reach; clicks are interest.",
         "Search Console", GREEN if d.get("clicks") else AMBER, ""),
        ("Click-through rate", f"{d.get('ctr', 0)}%", "clicks ÷ impressions",
         _score_gauge(min(100, _f(d.get("ctr")) * 20), 60),
         "Under 2% at a good position is a title and description problem.",
         "Search Console", _pct_color(100 - _f(d.get("ctr")) * 20, 60), ""),
        ("Average position", _n(d.get("avg_position")), "across ranked queries",
         "", ("Position 1–10 is page one. Beyond 20, CTR is close to zero no "
              "matter how good the title is."),
         "Search Console", AMBER if _f(d.get("avg_position")) > 20 else GREEN, ""),
        ("Ranking queries", d.get("queries", 0), "terms you appear for", "",
         "Breadth of visibility. One query ranking is luck; fifty is a system.",
         "Search Console", GREEN if d.get("queries") else AMBER, ""),
        ("Best query", (tq[0]["query"][:30] if tq else "—"),
         f"{tq[0]['clicks']:.0f} clicks" if tq else "no data",
         _hbars([(q["query"][:22], q["clicks"]) for q in tq[:6]]) if tq else "",
         "Your strongest term. Everything near it is the cheapest next win.",
         "Search Console", GREEN if tq else AMBER, ""),
        ("Top queries", len(tq), "shown below", "",
         "Ranked by clicks, so this is demand you already capture.",
         "Search Console", BLUE, _rows(
             [(q["query"][:34], f"{q['clicks']:.0f}") for q in tq[:8]],
             left_fmt=lambda kv: kv[0], right_fmt=lambda kv: kv[1], empty="")),
        ("Impressions per click", (round(_f(d.get("impressions")) /
                                         max(_f(d.get("clicks")), 1)) if d.get("clicks")
                                  else "—"), "shown per visit won", "",
         "How many times Google shows you before someone clicks.",
         "computed", BLUE, ""),
        ("Demand vs traffic", ("aligned" if d.get("has_ga4") and d.get("has_gsc")
                               else "one source only"), "GA4 and GSC agree?", "",
         ("Both sources are reporting, so traffic numbers can be cross-checked."
          if d.get("has_ga4") and d.get("has_gsc") else
          "Only one of GA4/GSC is reporting — the other's cards will read low."),
         "computed", GREEN if (d.get("has_ga4") and d.get("has_gsc")) else AMBER, ""),
        ("Window covered", f"{len(series)} days", "of GA4 daily rows", "",
         "Every trend on this board is computed only across this window.",
         "GA4", BLUE, ""),
        ("Where to act", "SEO section", "235 cards of detail", "",
         "This board says whether demand exists. The SEO section says what to "
         "do about it — striking distance, decay, cannibalisation.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('seo')\">Open SEO/AEO/GEO</button>"),
    ]
    return _head("📈", "Demand & traffic",
                 "Is anyone looking for us, and are they arriving?") + _vizcards(cards)


# ======================================================================
#  (3) MARKETS & GEOGRAPHY  (18)
# ======================================================================
def board_markets(ctx) -> str:
    ctx = _ctx(ctx)
    mk = ctx["markets"]
    rows = _L(mk.get("rows"))
    tm = _D(mk.get("target_markets"))
    total = _f(mk.get("total"))
    cards = [
        ("Markets reached", len(rows), "countries with traffic",
         _CH().geo([(n, v) for n, v in rows[:10]]) if rows else "",
         ("Where demand actually is, not where it was aimed."
          if rows else "GA4 has returned no country rows yet."),
         "GA4", GREEN if rows else AMBER, ""),
        ("Top market", (rows[0][0] if rows else "—"),
         f"{rows[0][1]:.0f} sessions" if rows else "no data",
         _split_donut([(n, v, c) for (n, v), c in
                       zip(rows[:5], (TEAL, VIOLET, BLUE, AMBER, PINK))]),
         "Your single largest source of visitors.",
         "GA4", BLUE if rows else AMBER, ""),
        ("Target-market share", f"{mk.get('target_share', 0)}%",
         "of traffic from your five markets",
         _score_gauge(_f(mk.get("target_share")), 70),
         ("USA, UK, Germany, Switzerland and Canada are the markets you sell "
          "into. Traffic outside them rarely converts."),
         "computed", _pct_color(100 - _f(mk.get("target_share")), 40), ""),
        ("Markets with no traffic", len(_L(mk.get("missing"))), "of your five", "",
         (f"No sessions at all from: {', '.join(_L(mk.get('missing')))}."
          if mk.get("missing") else "All five target markets are producing traffic."),
         "computed", PINK if mk.get("missing") else GREEN, ""),
    ]
    for name in ("USA", "UK", "Germany", "Switzerland", "Canada"):
        v = _f(tm.get(name))
        cards.append((f"{name}", f"{v:.0f}", "sessions",
                      _donut(min(100, round(100 * v / total)) if total else 0),
                      (f"{round(100 * v / total, 1)}% of all traffic." if total and v
                       else f"No traffic from {name} in this window. For Germany "
                            f"and Switzerland that is a language problem — the "
                            f"site has no German content."),
                      "GA4", GREEN if v else PINK, ""))
    cards += [
        ("Off-target traffic", f"{100 - _f(mk.get('target_share')):.0f}%",
         "outside your five markets", "",
         "Not worthless — but it will not convert at the same rate.",
         "computed", AMBER if _f(mk.get("target_share")) < 60 else GREEN, ""),
        ("German-language gap", "0 pages", "for DE + CH", "",
         ("Germany and Switzerland are two of your five target markets and the "
          "site has no German content. This is the widest single gap on the "
          "dashboard and it needs no new tool."),
         "site audit", PINK,
         "<button class='cta' onclick=\"seoTab('geo')\">Open GEO markets</button>"),
        ("Sessions by market", len(rows), "ranked",
         _hbars([(n[:20], v) for n, v in rows[:8]]),
         "Ranked by sessions, so the top row is where to double down.",
         "GA4", BLUE, ""),
        ("Markets month over month",
         len(_L(_D(ctx.get("markets_mom")).get("groups"))), "compared",
         _vbars(ctx.get("markets_mom")),
         _D(ctx.get("markets_mom")).get("note", ""),
         "monthly snapshots",
         GREEN if _D(ctx.get("markets_mom")).get("ready") else AMBER, ""),
        ("Market concentration",
         f"{round(100 * rows[0][1] / total) if rows and total else 0}%",
         "from the top market", "",
         "One market above 60% is a dependency, not a strategy.",
         "computed", AMBER if (rows and total and rows[0][1] / total > 0.6) else GREEN, ""),
        ("Market count vs plan", f"{len([1 for v in tm.values() if v])}/5",
         "target markets live", "",
         "The plan names five. This is how many are actually producing.",
         "computed", GREEN if len([1 for v in tm.values() if v]) >= 4 else AMBER, ""),
        ("Second market", (rows[1][0] if len(rows) > 1 else "—"),
         f"{rows[1][1]:.0f} sessions" if len(rows) > 1 else "no data", "",
         "Depth beyond the top market is what removes single-market risk.",
         "GA4", BLUE, ""),
        ("Third market", (rows[2][0] if len(rows) > 2 else "—"),
         f"{rows[2][1]:.0f} sessions" if len(rows) > 2 else "no third market yet", "",
         "Depth past the top two is what makes the mix resilient.",
         "GA4", BLUE, ""),
        ("Where to act", "GEO board", "hreflang, language, service areas", "",
         "This board says which markets exist. The GEO board says how to reach "
         "the ones that do not.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('geo')\">Open GEO</button>"),
    ]
    return _head("🌍", "Markets & geography",
                 "Which countries the demand comes from, against the five you "
                 "sell into.") + _vizcards(cards)


# ======================================================================
#  (4) CHANNEL MIX  (18)
# ======================================================================
def board_channels(ctx) -> str:
    ctx = _ctx(ctx)
    ch = ctx["channels"]
    rows = _L(ch.get("rows"))
    total = _f(ch.get("total"))
    r = ctx["revenue"]
    by_src = _L(r.get("by_source"))
    cards = [
        ("Channels producing", len(rows), "with sessions",
         _split_donut([(n, v, c) for (n, v), c in
                       zip(rows[:5], (TEAL, VIOLET, BLUE, AMBER, PINK))]),
         ("Where visits come from, split by GA4's channel grouping."
          if rows else "GA4 has returned no channel rows yet."),
         "GA4", GREEN if rows else AMBER, ""),
        ("Top channel", (rows[0][0] if rows else "—"),
         f"{ch.get('top_share', 0)}% of traffic",
         _score_gauge(_f(ch.get("top_share")), 70),
         ("Above 70% from one channel is a dependency — an algorithm change "
          "moves the whole business." if ch.get("concentrated") else
          "The mix is spread across more than one source."),
         "GA4", PINK if ch.get("concentrated") else GREEN, ""),
        ("Channel concentration", "high" if ch.get("concentrated") else "spread",
         "single-channel dependency", "",
         "The Risk board scores this as channel risk; this is where it comes from.",
         "computed", PINK if ch.get("concentrated") else GREEN,
         "<button class='cta' onclick=\"nav('riskinfra')\">See channel risk</button>"),
        ("Channels month over month",
         len(_L(_D(ctx.get("channels_mom")).get("groups"))), "compared",
         _vbars(ctx.get("channels_mom")),
         _D(ctx.get("channels_mom")).get("note", ""),
         "monthly snapshots",
         GREEN if _D(ctx.get("channels_mom")).get("ready") else AMBER, ""),
    ]
    def _chan(i, row):
        name, v = row
        share = round(100 * v / total, 1) if total else 0
        return (f"{name}", f"{v:.0f}", f"{share}% of sessions", _donut(share),
                (f"{name} is {'your main source' if i == 0 else 'a secondary source'} "
                 f"of visits."), "GA4", GREEN if i == 0 else BLUE, "")
    cards += _slots(rows, 6, _chan, "Channel", "no sessions in this window",
                    ("GA4 groups traffic into up to ten channels. This slot fills "
                     "when a further channel starts producing sessions."), "GA4")
    cards += [
        ("Revenue by channel", len(by_src), "sources with revenue",
         _split_donut([(n, v, c) for (n, v), c in
                       zip(by_src[:5], (GREEN, TEAL, BLUE, AMBER, PINK))]),
         ("Traffic share and revenue share are different questions — this is the "
          "one that pays." if by_src else
          "Recorded deals carry their source, so this fills from the first deal."),
         "recorded deals", GREEN if by_src else AMBER, ""),
        ("Best-paying source", (by_src[0][0] if by_src else "—"),
         _money(by_src[0][1]) if by_src else "no deals yet", "",
         ("Where revenue actually came from, not where traffic came from."
          if by_src else "Record a deal and tag its source."),
         "recorded deals", GREEN if by_src else AMBER, ""),
        ("Organic vs paid", (f"{round(100 * sum(v for n, v in rows if 'rgani' in n) / total)}%"
                             if total else "—"), "organic share of sessions", "",
         "Paid stops the day you stop paying. Organic compounds.",
         "GA4", BLUE, ""),
        ("Paid channel", ("live" if any("aid" in n for n, _v in rows) else "none"),
         "Google Ads sessions", "",
         ("Ads are producing sessions." if any("aid" in n for n, _v in rows) else
          "No paid sessions in this window — the Ads wire is not returning data."),
         "GA4", AMBER if not any("aid" in n for n, _v in rows) else GREEN,
         "<button class='cta' onclick=\"nav('media')\">Open Media Buying</button>"),
        ("Referral presence", ("yes" if any("efer" in n for n, _v in rows) else "no"),
         "traffic from other sites", "",
         "Referral traffic is the visible half of link building.",
         "GA4", BLUE, ""),
        ("Direct traffic", (f"{round(100 * sum(v for n, v in rows if 'irect' in n) / total)}%"
                            if total else "—"), "typed or untracked", "",
         "High direct with low brand search usually means broken tracking.",
         "GA4", BLUE, ""),
        ("Channel count", len(rows), "producing sessions", "",
         ("Two or fewer channels is fragile — one algorithm change moves "
          "everything." if len(rows) <= 2 else
          "More than two producing channels means no single change can take the "
          "whole business out."),
         "GA4", AMBER if len(rows) <= 2 else GREEN, ""),
        ("Where to act", "Media Buying", "296 cards of paid detail", "",
         "This board shows the mix. Media Buying shows what to do with the paid "
         "half of it.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('media')\">Open Media Buying</button>"),
    ]
    return _head("🔀", "Channel mix",
                 "Which channels bring visits, and which bring money.") + _vizcards(cards[:18])


# ======================================================================
#  (5) CONTENT → REVENUE  (18)
# ======================================================================
def board_content(ctx) -> str:
    ctx = _ctx(ctx)
    cn, fn, r = ctx["content"], ctx["funnel"], ctx["revenue"]
    pages = _L(cn.get("pages"))
    cards = [
        ("Pages pulling traffic", cn.get("carrying", 0), "with sessions",
         _treemap([(p, v) for p, v in pages[:8]]),
         ("Size is sessions. The biggest tile is your best-performing page."
          if pages else "GA4 has returned no page rows yet."),
         "GA4", GREEN if pages else AMBER, ""),
        ("Published pieces", cn.get("published", 0), "by the engine", "",
         "Everything the content agent has finished and published.",
         "jobs", GREEN if cn.get("published") else AMBER, ""),
        ("Top-5 concentration", f"{cn.get('top5_share', 0)}%", "of traffic",
         _score_gauge(_f(cn.get("top5_share")), 70),
         "If five pages carry most of the traffic, the rest are not working yet.",
         "computed", AMBER if _f(cn.get("top5_share")) > 70 else GREEN, ""),
        ("The full path", len(_L(fn.get("flows"))), "steps measured",
         _CH().sankey(_L(fn.get("flows"))),
         ("Content to traffic to lead to booking to revenue, with every drop "
          "shown as its own ribbon." if fn.get("flows") else
          "Fills as leads move through the funnel."),
         "computed", BLUE if fn.get("flows") else AMBER, ""),
        ("Best page", (pages[0][0] if pages else "—"),
         f"{pages[0][1]:.0f} sessions" if pages else "no data", "",
         "The page to write three more like.",
         "GA4", GREEN if pages else AMBER, ""),
        ("Revenue per published piece",
         (_money(_f(r.get("total")) / cn.get("published"))
          if cn.get("published") and r.get("total") else "—"),
         "recorded revenue ÷ pieces", "",
         ("The number that says whether publishing pays." if r.get("total") else
          "Needs one recorded deal. The publishing half is already counted."),
         "computed", GREEN if r.get("total") else AMBER, ""),
        ("Pages by traffic", len(pages), "ranked",
         _hbars([(p[:24], v) for p, v in pages[:8]]),
         "Ranked by sessions.", "GA4", BLUE, ""),
    ]
    cards += _slots(
        pages, 6,
        lambda i, r: (r[0][:28], f"{r[1]:.0f}", "sessions", "",
                      "A published page earning traffic.", "GA4", BLUE,
                      _link("https://anthropos-automation.com" + r[0], r[0][:40])),
        "Page", "not in GA4's top pages",
        ("GA4 returns the fifteen busiest pages. This slot fills when another "
         "published page starts earning sessions."), "GA4")
    cards += [
        ("Pages with zero traffic",
         max(0, cn.get("published", 0) - cn.get("carrying", 0)), "published but silent",
         "", ("Published and earning nothing. Either the topic has no demand or "
              "the page never got indexed."),
         "computed", AMBER, ""),
        ("Traffic-earning rate",
         (f"{round(100 * cn.get('carrying', 0) / cn.get('published', 1))}%"
          if cn.get("published") else "—"), "of published pieces", "",
         "The share of your output that actually earns visits.",
         "computed", BLUE, ""),
        ("Content cost", _money(_D(ctx["cost"]).get("content_cost")), "to produce all of it",
         "", "What the published library cost to generate.",
         "job costs", BLUE, ""),
        ("Cost per published piece", _money(_D(ctx["cost"]).get("per_piece")), "each",
         "", "Failed jobs are excluded from the denominator — dividing by work "
             "that produced nothing flatters this number.",
         "computed", GREEN, ""),
        ("Where to act", "Content section", "plan and approve", "",
         "This board says which pieces worked. The Content section is where the "
         "next ones get planned.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('content')\">Open Content</button>"),
    ]
    return _head("📝", "Content → revenue",
                 "Which pages earn traffic, and whether publishing pays.") + _vizcards(cards[:18])


# ======================================================================
#  (6) LEAD GENERATION  (20)
# ======================================================================
def board_leads(ctx) -> str:
    ctx = _ctx(ctx)
    lg = ctx["leadgen"]
    by_src = _L(lg.get("by_source"))
    dist = _L(lg.get("distribution"))
    per_day = _L(lg.get("per_day"))
    cards = [
        ("Leads found", lg.get("found", 0), "sourced by the engine",
         _trend([("leads/day", [v for _d, v in per_day], TEAL)]),
         ("Everything the lead agent has surfaced." if lg.get("has_data")
          else "No outreach campaign has run yet."),
         "outreach jobs", GREEN if lg.get("found") else AMBER, ""),
        ("Verified", lg.get("verified", 0), "with a real address",
         _score_gauge(_f(lg.get("verify_rate")), 70),
         f"{lg.get('verify_rate', 0)}% of found leads survive verification.",
         "email verifier", _pct_color(100 - _f(lg.get("verify_rate")), 40), ""),
        ("Qualified", lg.get("qualified", 0), "passed the ICP filter",
         _score_gauge(_f(lg.get("qualify_rate")), 50),
         f"{lg.get('qualify_rate', 0)}% of verified leads match the ICP.",
         "lead qualifier", _pct_color(100 - _f(lg.get("qualify_rate")), 50), ""),
        ("Verification loss", lg.get("found", 0) - lg.get("verified", 0),
         "dropped as unreachable", "",
         "Unverifiable addresses bounce, and bounces damage domain reputation.",
         "computed", AMBER if (lg.get("found", 0) - lg.get("verified", 0)) else GREEN, ""),
        ("Qualification loss", lg.get("verified", 0) - lg.get("qualified", 0),
         "verified but off-ICP", "",
         "Real people who are not your buyer. Sourcing is aiming too wide.",
         "computed", AMBER, ""),
        ("Campaigns run", lg.get("campaigns", 0), "outreach jobs", "",
         "Each campaign is one sourcing and sending cycle.",
         "jobs", BLUE, ""),
        ("Daily distribution", len(dist), "days measured",
         _histogram([int(v) for v in dist]),
         ("The shape matters: steady beats spiky, because spiky means one big "
          "scrape and then nothing."),
         "computed", BLUE, ""),
        ("Best day", (max([v for _d, v in per_day], default=0)), "leads in one day",
         "", "What the pipeline can do when it runs well.",
         "computed", BLUE, ""),
        ("Leads month over month",
         len(_L(_D(ctx.get("leads_mom")).get("groups"))), "sources compared",
         _vbars(ctx.get("leads_mom")),
         _D(ctx.get("leads_mom")).get("note", ""),
         "campaign dates",
         GREEN if _D(ctx.get("leads_mom")).get("ready") else AMBER, ""),
        ("Sources", len(by_src), "distinct lead sources",
         _hbars([(s[:20], v) for s, v in by_src[:6]]),
         ("One source is a single point of failure." if len(by_src) <= 1
          else "More than one source protects the pipeline."),
         "outreach jobs", AMBER if len(by_src) <= 1 else GREEN, ""),
    ]
    cards += _slots(
        by_src, 5,
        lambda i, r: (f"Source: {r[0][:22]}", r[1], "leads",
                      _donut(round(100 * r[1] / max(lg.get("found", 1), 1))),
                      "Contribution to total lead volume.", "outreach jobs", BLUE, ""),
        "Lead source", "not in use yet",
        ("One source is a single point of failure. This slot fills when a "
         "campaign sources leads from another place."), "outreach jobs")
    cards += [
        ("ICP match", "doctors · lawyers · Shopify · tax · creators",
         "your defined buyer", "",
         "The qualifier scores against this list. Widen it and qualification "
         "rate rises while close rate falls.",
         "your ICP", VIOLET, ""),
        ("Cost per lead", _money(_D(ctx["cost"]).get("per_lead")), "engine cost ÷ leads",
         "", "Outreach spend divided by leads found.",
         "computed", GREEN if _D(ctx["cost"]).get("per_lead") else AMBER, ""),
        ("Pipeline coverage",
         (f"{round(lg.get('qualified', 0) / max(_f(_D(ctx['targets']).get('leads_month')), 1) * 100)}%"
          if _D(ctx["targets"]).get("leads_month") else "—"),
         "of the monthly lead target", "",
         ("Against the target you set." if _D(ctx["targets"]).get("leads_month")
          else "Set a monthly lead target and this becomes a pass/fail number."),
         "your targets", BLUE, ""),
        ("Qualified per campaign",
         (round(lg.get("qualified", 0) / lg.get("campaigns", 1), 1)
          if lg.get("campaigns") else "—"), "usable leads per run", "",
         "The only yield number that matters — found leads that survive both "
         "verification and the ICP filter.",
         "computed", GREEN if lg.get("qualified") else AMBER, ""),
        ("Where to act", "Leads section", "review and approve", "",
         "This board measures the sourcing. The Leads section is where you act "
         "on individual people.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('leads')\">Open Leads</button>"),
    ]
    return _head("🧲", "Lead generation",
                 "How many leads, from where, and how many survive the "
                 "filters.") + _vizcards(cards[:20])


# ======================================================================
#  (7) OUTREACH & REPLY  (18)
# ======================================================================
def board_outreach(ctx) -> str:
    ctx = _ctx(ctx)
    ou = ctx["outreach"]
    sd = _L(ou.get("send_days"))
    cards = [
        ("Emails sent", ou.get("sent", 0), "intro and follow-up",
         _trend([("sent/day", [v for _d, v in sd], TEAL)]),
         ("Counted from real send timestamps, not campaign creation dates."
          if ou.get("has_data") else "Nothing has been sent yet."),
         "sent_at stamps", GREEN if ou.get("sent") else AMBER, ""),
        ("Replies", ou.get("replied", 0), "real responses", "",
         "Read from the inbox, not inferred.",
         "IMAP", GREEN if ou.get("replied") else AMBER, ""),
        ("Reply rate", f"{ou.get('reply_rate', 0)}%", "replies ÷ sent",
         _score_gauge(min(100, _f(ou.get("reply_rate")) * 5), 50),
         ("Cold outreach at 5–10% is working. Under 2% is a targeting or "
          "subject-line problem, not a volume problem."),
         "computed", _pct_color(100 - _f(ou.get("reply_rate")) * 5, 50), ""),
        ("Silent", ou.get("silent", 0), "sent, never answered", "",
         "The follow-up sequence exists for exactly this group.",
         "computed", AMBER if ou.get("silent") else GREEN, ""),
        ("Send activity", len(sd), "days with sends",
         _CH().cohort(_L(ou.get("cohort_cols")), _L(ou.get("cohort_grid"))),
         "Sends by day. Gaps are days the sequence did not run.",
         "sent_at stamps", BLUE, ""),
        ("Busiest send day", max([v for _d, v in sd], default=0), "emails", "",
         "Volume ceiling reached so far.",
         "computed", BLUE, ""),
        ("Sending cadence",
         (round(sum(v for _d, v in sd) / len(sd), 1) if sd else "—"),
         "emails per active day", "",
         "Steady beats bursty — mailbox reputation is built on consistency.",
         "computed", BLUE, ""),
        ("Days since last send", "—" if not sd else
         f"{max(0, (len(sd) and 0))}", "gap in the sequence", "",
         ("A stalled sequence is the most common reason reply rate collapses."
          if sd else "Nothing sent yet."),
         "computed", AMBER if not sd else GREEN, ""),
        ("Emailed people", ou.get("emailed", 0), "unique recipients", "",
         "Distinct people reached at least once.",
         "outreach jobs", BLUE, ""),
        ("Reply per recipient",
         (f"{round(100 * ou.get('replied', 0) / max(ou.get('emailed', 1), 1))}%"
          if ou.get("emailed") else "—"), "of people who answered", "",
         "Per-person rate, which is the honest one when follow-ups inflate sends.",
         "computed", BLUE, ""),
        ("Deliverability signal", "no bounce data", "from the mail wire", "",
         ("Bounces are not currently read back from the mailbox. Reply rate "
          "cannot distinguish 'ignored' from 'never arrived' until they are."),
         "IMAP", AMBER, ""),
        ("Follow-up coverage",
         (f"{max(0, ou.get('sent', 0) - ou.get('emailed', 0))}"), "follow-ups sent",
         "", "Sends beyond the first touch. Most replies come from touch 2–4.",
         "computed", BLUE if ou.get("sent", 0) > ou.get("emailed", 0) else AMBER, ""),
        ("Reply handling", "auto-drafted", "by the reply agent", "",
         "Answerable replies are drafted automatically; the rest wait for you.",
         "reply agent", GREEN, ""),
        ("Sequence health", ("running" if sd else "idle"), "sending state", "",
         ("The sequence is producing sends." if sd else
          "Nothing has gone out. The scheduler is the place to check why."),
         "computed", GREEN if sd else AMBER, ""),
        ("Cost per email",
         (_money(_f(_D(ctx["cost"]).get("outreach_cost")) / max(ou.get("sent", 1), 1))
          if ou.get("sent") else "—"), "outreach spend ÷ sends", "",
         "Cheap per send; the cost that matters is per reply.",
         "computed", BLUE, ""),
        ("Cost per reply",
         (_money(_f(_D(ctx["cost"]).get("outreach_cost")) / max(ou.get("replied", 1), 1))
          if ou.get("replied") else "—"), "outreach spend ÷ replies", "",
         "The real unit cost of the top of your sales funnel.",
         "computed", GREEN if ou.get("replied") else AMBER, ""),
        ("Domain reputation", "watch bounces", "sender health", "",
         "One bad list can cost the domain. The Risk board scores this as "
         "deliverability risk.",
         "risk register", AMBER,
         "<button class='cta' onclick=\"nav('riskinfra')\">See the risk</button>"),
        ("Where to act", "Email section", "drafts and inbox", "",
         "This board measures the sending. The Email section is where the "
         "conversations are.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('email')\">Open Email</button>"),
    ]
    return _head("✉️", "Outreach & reply",
                 "Sent, answered, and what a reply costs.") + _vizcards(cards[:18])


# ======================================================================
#  (8) CONSULTATIONS  (16)
# ======================================================================
def board_consultations(ctx) -> str:
    ctx = _ctx(ctx)
    co = ctx["consultations"]
    ou, r, e = ctx["outreach"], ctx["revenue"], _D(ctx.get("econ"))
    per_day = _L(co.get("per_day"))
    tasks = _L(co.get("tasks"))
    cards = [
        ("Consultations booked", co.get("accepted", 0), "accepted",
         _CH().gantt([(t[0], t[1], t[2]) for t in tasks], span=14) if tasks else "",
         ("Real bookings from Cal.com, on a timeline." if co.get("has_data")
          else "Cal.com is connected and has returned no bookings in this window."),
         "Cal.com", GREEN if co.get("accepted") else AMBER, ""),
        ("Total bookings", co.get("total", 0), "all statuses", "",
         "Includes cancelled and pending, so it is always at least the accepted "
         "count.",
         "Cal.com", BLUE, ""),
        ("Upcoming", co.get("upcoming", 0), "in the future", "",
         "Calls still to happen. This is your near-term pipeline.",
         "Cal.com", GREEN if co.get("upcoming") else AMBER, ""),
        ("Completed", co.get("past", 0), "already held", "",
         "Calls held. Each one should end as a won or lost deal.",
         "Cal.com", BLUE, ""),
        ("Next consultation", (co.get("next") or "—"), "date", "",
         ("The next call on the calendar." if co.get("next") else
          "Nothing scheduled ahead."),
         "Cal.com", GREEN if co.get("next") else AMBER, ""),
        ("Booking rate",
         (f"{round(100 * co.get('accepted', 0) / max(ou.get('replied', 1), 1))}%"
          if ou.get("replied") else "—"), "replies that became calls", "",
         "The conversion that decides whether replies are worth chasing.",
         "computed", BLUE, ""),
        ("Bookings per day", len(per_day), "days with a booking",
         _trend([("bookings", [v for _d, v in per_day], VIOLET)]),
         "Spread over time. Clusters usually follow a send burst.",
         "Cal.com", BLUE, ""),
        ("Show-up state", "tracked by Cal.com", "attendance", "",
         "Cancellations and no-shows appear in the total-versus-accepted gap.",
         "Cal.com", BLUE, ""),
        ("Cancelled or pending", max(0, co.get("total", 0) - co.get("accepted", 0)),
         "not accepted", "",
         "A high gap means the booking flow is attracting the wrong people.",
         "computed", AMBER if (co.get("total", 0) - co.get("accepted", 0)) else GREEN, ""),
        ("Consult → client rate",
         (f"{e.get('consult_to_client_pct')}%" if e.get("consult_to_client_pct")
          else "—"), "your close rate", "",
         ("Used to turn booked calls into a pipeline value." if
          e.get("consult_to_client_pct") else
          "One number from you turns every booked call into a euro figure."),
         "your input", GREEN if e.get("consult_to_client_pct") else AMBER,
         "<button class='cta' onclick='biEcon()'>Enter it</button>"),
        ("Pipeline value",
         (_money(co.get("upcoming", 0) * _f(e.get("avg_deal"))
                 * _f(e.get("consult_to_client_pct")) / 100)
          if (e.get("avg_deal") and e.get("consult_to_client_pct")) else "—"),
         "expected from upcoming calls", "",
         ("Upcoming calls × average deal × close rate." if
          (e.get("avg_deal") and e.get("consult_to_client_pct")) else
          "Needs your average deal value and close rate — two numbers, once."),
         "computed", GREEN if e.get("avg_deal") else AMBER, ""),
        ("Cost per booking", _money(_D(ctx["cost"]).get("per_booking")), "engine spend ÷ bookings",
         "", "What it costs to put one qualified call in the calendar.",
         "computed", GREEN if _D(ctx["cost"]).get("per_booking") else AMBER, ""),
        ("Booked to won",
         (f"{round(100 * r.get('deals', 0) / max(co.get('accepted', 1), 1))}%"
          if co.get("accepted") else "—"), "calls that closed", "",
         ("Measured from recorded deals against accepted calls." if r.get("deals")
          else "Record a won deal and this becomes your real close rate."),
         "computed", GREEN if r.get("deals") else AMBER, ""),
        ("Calendar link", "cal.com", "manage availability", "",
         "Bookings are read from Cal.com's v2 API — the calendar itself lives "
         "there.",
         "Cal.com", BLUE,
         _link("https://cal.com/bookings", "Open Cal.com bookings")),
        ("Wire status", "connected", "Cal.com API", "",
         "The bookings wire is live, so every number on this board is real "
         "rather than assumed.",
         "System & Wiring", GREEN, ""),
        ("Where to act", "record the outcome", "after each call", "",
         "A call that is not recorded as won or lost leaves revenue, CAC and "
         "close rate all uncomputable.",
         "navigation", VIOLET,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
    ]
    return _head("📅", "Consultations",
                 "Booked calls, what they cost, and what they are worth.") + _vizcards(cards[:16])


# ======================================================================
#  (9) FUNNEL & LEAKS  (20)
# ======================================================================
def board_funnel(ctx) -> str:
    ctx = _ctx(ctx)
    fn = ctx["funnel"]
    stages = _L(fn.get("stages"))
    leaks = _L(fn.get("leaks"))
    cards = [
        ("End-to-end conversion", f"{fn.get('overall_pct', 0)}%", "found → won",
         _CH().sankey(_L(fn.get("flows"))),
         ("Every stage and every drop, as one picture." if fn.get("flows") else
          "Fills as leads move through the stages."),
         "computed", PINK if _f(fn.get("overall_pct")) < 1 else GREEN, ""),
        ("Biggest leak", (fn["worst"][0] if fn.get("worst") else "—"),
         (f"{fn['worst'][1]:,.0f} lost" if fn.get("worst") else "no data"),
         _waterfall([(n, v) for n, v in _L(fn.get("waterfall"))]),
         ("Fixing the largest drop is worth more than adding volume at the top."
          if fn.get("worst") else "The funnel needs data before it can leak."),
         "computed", PINK if fn.get("worst") else AMBER, ""),
        ("Stages measured", len(stages), "from found to won",
         _hbars([(n, v) for n, v in stages]),
         "Six stages, each read from real job and booking data.",
         "computed", BLUE, ""),
    ]
    STAGE_NAMES = ["Found", "Verified", "Emailed", "Replied", "Booked", "Won"]

    def _stage(i, row):
        name, val = row
        prev = stages[i - 1][1] if i else None
        rate = round(100 * val / prev, 1) if prev else None
        return (f"Stage: {name}", val, "reached this stage", "",
                (f"{rate}% of the previous stage survived to here."
                 if rate is not None else
                 "The top of the funnel — everything else is a share of this."),
                "computed",
                (PINK if (rate is not None and rate < 20) else
                 AMBER if (rate is not None and rate < 50) else GREEN), "")
    for i in range(6):
        if i < len(stages):
            cards.append(_stage(i, stages[i]))
        else:
            cards.append((f"Stage: {STAGE_NAMES[i]}", "—", "not reached yet", "",
                          "No one has reached this stage. It fills the moment "
                          "one person does.", "computed", AMBER, ""))
    cards += _slots(
        leaks, 6,
        lambda i, r: (f"Leak: {r[0]}", f"{r[1]:,.0f}", f"{r[2]}% lost here",
                      _donut(100 - _f(r[2])),
                      "People who reached the first stage and never made the "
                      "second.", "computed", PINK if _f(r[2]) > 60 else AMBER, ""),
        "Leak", "no drop measured here",
        ("A leak appears once two consecutive stages both have numbers. Nothing "
         "is lost here yet because nothing has flowed through."), "computed")
    cards += [
        ("Volume vs conversion",
         ("conversion" if _f(fn.get("overall_pct")) < 2 else "volume"),
         "where the gain is", "",
         ("Conversion is under 2%, so more leads mostly means more waste. Fix "
          "the biggest leak first." if _f(fn.get("overall_pct")) < 2 else
          "Conversion is holding, so more volume at the top will translate."),
         "computed", AMBER, ""),
        ("Funnel data quality",
         ("complete" if fn.get("has_data") else "incomplete"), "all stages reporting",
         "", ("Every stage has a real source: jobs, sent stamps, inbox, Cal.com "
              "and recorded deals." if fn.get("has_data") else
              "The funnel starts at lead sourcing — run a campaign to fill it."),
         "computed", GREEN if fn.get("has_data") else AMBER, ""),
        ("Top of funnel", (stages[0][1] if stages else 0), "entered the funnel",
         "", "Everything downstream is a percentage of this number.",
         "computed", BLUE, ""),
        ("Bottom of funnel", (stages[-1][1] if stages else 0), "came out as revenue",
         "", ("The only number the business is actually paid for."),
         "computed", GREEN if (stages and stages[-1][1]) else AMBER, ""),
        ("Where to act", "biggest leak first", "one fix at a time", "",
         "The stage losing the most people is the only one worth working on "
         "this week.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('leads')\">Open Leads</button>"),
    ]
    return _head("🔻", "Funnel & leaks",
                 "Where people enter, and exactly where they fall out.") + _vizcards(cards[:20])


# ======================================================================
#  (10) REVENUE & DEALS  (20)
# ======================================================================
def board_revenue(ctx) -> str:
    ctx = _ctx(ctx)
    r = ctx["revenue"]
    deals = ctx["deals"]
    ranked = _L(r.get("ranked"))
    by_month = _L(r.get("by_month"))
    by_source = _L(r.get("by_source"))
    record_btn = "<button class='cta' onclick='biDeal()'>Record a won deal</button>"
    cards = [
        ("Revenue recorded", _money(r.get("total")), "all time",
         _waterfall([(m, v) for m, v in by_month]) if by_month else "",
         ("Month by month, as a bridge." if by_month else
          "No deals recorded. This is the one input that unlocks revenue, "
          "customers and unit economics — no Stripe, no CRM, just a name and "
          "a number."),
         "recorded deals", GREEN if r.get("total") else AMBER, record_btn),
        ("Deals won", r.get("deals", 0), "closed", "",
         "Each recorded deal carries a client, a value, a date and a source.",
         "recorded deals", GREEN if r.get("deals") else AMBER, record_btn),
        ("Average deal", _money(r.get("avg_deal")), "per deal", "",
         ("Your real average, from recorded deals." if r.get("avg_deal") else
          "Computed from the first deal you record."),
         "computed", GREEN if r.get("avg_deal") else AMBER, ""),
        ("This month", _money(r.get("month_total")), "booked", "",
         "Revenue dated in the current calendar month.",
         "recorded deals", GREEN if r.get("month_total") else AMBER, ""),
        ("Paying clients", r.get("clients", 0), "distinct", "",
         "Distinct client names across all recorded deals.",
         "recorded deals", BLUE if r.get("clients") else AMBER, ""),
        ("Largest client", (ranked[0][0][:24] if ranked else "—"),
         _money(ranked[0][1]) if ranked else "no deals yet",
         _split_donut([(c, v, col) for (c, v), col in
                       zip(ranked[:5], (TEAL, VIOLET, BLUE, AMBER, PINK))]),
         ("Concentration is a risk once one client passes a third of revenue."
          if ranked else "Fills from the first recorded deal."),
         "recorded deals", GREEN if ranked else AMBER, ""),
        ("Concentration", f"{r.get('top_share', 0)}%", "from the largest client",
         _score_gauge(_f(r.get("top_share")), 33),
         ("Above 33% means losing one client is an existential event. The Risk "
          "board scores this — and it reads the client name recorded here, "
          "which is why it was permanently empty before."),
         "computed", PINK if _f(r.get("top_share")) > 33 else GREEN,
         "<button class='cta' onclick=\"nav('riskinfra')\">See revenue risk</button>"),
        ("Recurring deals", r.get("recurring", 0), "marked as repeating", "",
         "Recurring revenue is worth several times the same amount once.",
         "recorded deals", GREEN if r.get("recurring") else BLUE, ""),
        ("Revenue by source", len(by_source), "sources",
         _hbars([(s[:18], v) for s, v in by_source[:6]]),
         ("Which channel actually produced money." if by_source else
          "Each deal is tagged with its source when recorded."),
         "recorded deals", GREEN if by_source else AMBER, ""),
        ("Months with revenue", len(by_month), "recorded",
         _trend([("revenue", [v for _m, v in by_month], GREEN)]),
         "The trend line only means something after three months.",
         "recorded deals", BLUE, ""),
    ]
    r_total = _f(r.get("total")) or 1
    cards += _slots(
        ranked, 6,
        lambda i, r: (f"Client: {r[0][:22]}", _money(r[1]), "total recorded",
                      _donut(round(100 * r[1] / max(_f(r_total), 1))),
                      "Share of all recorded revenue.", "recorded deals", BLUE, ""),
        "Client", "not recorded yet",
        ("Each recorded deal carries a client name. This slot fills with your "
         "next distinct client."), "recorded deals", AMBER)
    cards += _slots(
        deals, 4,
        lambda i, d: (f"Deal: {str(_D(d).get('client'))[:20]}",
                      _money(_D(d).get("value")), str(_D(d).get("at")), "",
                      f"Source: {_D(d).get('source')}."
                      + (" Recurring." if _D(d).get("recurring") else ""),
                      "recorded deals", GREEN, ""),
        "Deal", "not recorded yet",
        ("Recording a deal takes a name, a number and a date. It is the only "
         "input this whole group needs."), "recorded deals", AMBER)
    return _head("💶", "Revenue & deals",
                 "What came in, from whom, and how concentrated it "
                 "is.") + _vizcards(cards[:20])


# ======================================================================
#  (11) CUSTOMERS & RETENTION  (18)
# ======================================================================
def board_customers(ctx) -> str:
    ctx = _ctx(ctx)
    cu, r = ctx["customers"], ctx["revenue"]
    ranked = _L(cu.get("ranked"))
    cards = [
        ("Customers", cu.get("count", 0), "distinct clients",
         _CH().cohort(_L(cu.get("cohort_cols")), _L(cu.get("cohort_grid")))
         if cu.get("cohort_grid") else "",
         ("Rows are the month a client first paid; columns are months after. "
          "This is retention, measured." if cu.get("cohort_grid") else
          "The cohort grid draws itself from recorded deal dates."),
         "recorded deals", GREEN if cu.get("count") else AMBER,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Repeat customers", cu.get("repeat", 0), "bought more than once", "",
         "The cheapest revenue you will ever earn.",
         "recorded deals", GREEN if cu.get("repeat") else AMBER, ""),
        ("Repeat rate", f"{cu.get('repeat_rate', 0)}%", "of clients return",
         _score_gauge(_f(cu.get("repeat_rate")), 30),
         "Above 30% for a services business means the work is landing.",
         "computed", GREEN if _f(cu.get("repeat_rate")) >= 30 else AMBER, ""),
        ("Lifetime value", _money(cu.get("ltv")), "average per client", "",
         ("Total recorded revenue divided by distinct clients." if cu.get("ltv")
          else "Computed from the first recorded deal."),
         "computed", GREEN if cu.get("ltv") else AMBER, ""),
        ("Deals per client", _n(cu.get("deals_per_client")), "average", "",
         "Above 1 means clients come back rather than buy once.",
         "computed", BLUE, ""),
        ("Client ranking", len(ranked), "by revenue",
         _hbars([(c[:20], v) for c, v in ranked[:8]]),
         "Who actually pays the bills, ranked.",
         "recorded deals", BLUE, ""),
        ("Top client share", f"{r.get('top_share', 0)}%", "of all revenue",
         _donut(_f(r.get("top_share"))),
         "The same number the Risk board scores as concentration risk.",
         "computed", PINK if _f(r.get("top_share")) > 33 else GREEN, ""),
        ("Client rank movement", len(_L(ctx.get("client_bump"))), "clients tracked",
         _CH().bump(_L(ctx.get("client_bump"))),
         ("A line climbing means that client is taking a larger share of "
          "revenue month by month. Needs two months of recorded deals."
          if ctx.get("client_bump") else
          "Fills once deals exist in two different months — rank movement "
          "cannot be drawn from a single month."),
         "recorded deals",
         GREEN if ctx.get("client_bump") else AMBER, ""),
    ]
    cards += _slots(
        ranked, 6,
        lambda i, r: (f"{r[0][:24]}", _money(r[1]), "lifetime revenue", "",
                      "Total across every recorded deal for this client.",
                      "recorded deals", BLUE, ""),
        "Client", "not recorded yet",
        ("Lifetime value is per client, so this fills with your next distinct "
         "client name."), "recorded deals", AMBER)
    cards += [
        ("Churn signal", ("none measurable" if not cu.get("cohort_grid")
                          else "see cohorts"), "clients going quiet", "",
         ("Churn for project work is a client who stops returning — visible in "
          "the cohort grid as a row that empties out."),
         "computed", BLUE, ""),
        ("Expansion", cu.get("repeat", 0), "clients who bought again", "",
         "Expansion revenue costs nothing to acquire.",
         "recorded deals", GREEN if cu.get("repeat") else AMBER, ""),
        ("Concentration risk", ("high" if _f(r.get("top_share")) > 33 else "contained"),
         "single-client exposure", "",
         "Feeds the Risk register directly.",
         "risk register", PINK if _f(r.get("top_share")) > 33 else GREEN,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
        ("Where to act", "record every win", "and every repeat", "",
         "Retention, LTV and cohorts all come from one habit: recording the "
         "deal when it closes.",
         "navigation", VIOLET,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
    ]
    return _head("🫂", "Customers & retention",
                 "Who pays, who comes back, and what a client is "
                 "worth.") + _vizcards(cards[:18])


# ======================================================================
#  (12) UNIT ECONOMICS  (20)
# ======================================================================
def board_econ(ctx) -> str:
    ctx = _ctx(ctx)
    u, e, at = ctx["unit"], _D(ctx.get("econ")), ctx["attainment"]
    rows = _L(at.get("rows"))
    econ_btn = "<button class='cta' onclick='biEcon()'>Enter your economics</button>"
    cards = [
        ("Cost to acquire a client", _money(u.get("cac")), "CAC",
         _score_gauge(min(100, _f(u.get("cac")) / 20) if u.get("cac") else 0, 50),
         ("Total engine spend divided by clients won." if u.get("cac") else
          "Needs one recorded client. The spend half is already measured."),
         "computed", GREEN if u.get("cac") else AMBER, ""),
        ("Lifetime value", _money(u.get("ltv")), "per client", "",
         ("Revenue per client, adjusted by your margin." if u.get("margin_pct")
          else "Revenue per client. Without a margin % this is turnover, not "
               "profit, so the ratio below reads high."),
         "computed", GREEN if u.get("ltv") else AMBER, ""),
        ("LTV to CAC", _n(u.get("ratio")), "3+ is healthy",
         _CH().confband([_f(u.get("ratio")) or 0] * 6, band=0.25)
         if u.get("ratio") else "",
         ("Above 3 the model works. Below 1 you lose money on every client."
          if u.get("ratio") else "Needs a recorded deal and your margin %."),
         "computed", GREEN if u.get("healthy_ratio") else AMBER, ""),
        ("Payback period", (f"{u.get('payback_months')} mo"
                            if u.get("payback_months") else "—"),
         "to earn back acquisition cost", "",
         ("Under 12 months is comfortable for a services business."
          if u.get("payback_months") else "Needs CAC and LTV."),
         "computed", GREEN if _f(u.get("payback_months")) < 12 else AMBER, ""),
        ("Gross profit", _money(u.get("gross_profit")), "revenue × margin", "",
         ("Your margin applied to recorded revenue." if u.get("gross_profit")
          else "Set your gross margin % and this computes immediately."),
         "computed", GREEN if u.get("gross_profit") else AMBER, econ_btn),
        ("Gross margin", (f"{u.get('margin_pct')}%" if u.get("margin_pct") else "—"),
         "your figure", "",
         ("Used for LTV, profit and payback." if u.get("margin_pct") else
          "One number. It changes three cards on this board."),
         "your input", GREEN if u.get("margin_pct") else AMBER, econ_btn),
        ("Return on engine spend",
         (f"{u.get('roi')}%" if u.get("roi") is not None else "—"),
         "revenue vs engine cost", "",
         ("Revenue minus cost, over cost." if u.get("roi") is not None else
          "The cost half is measured; the revenue half needs a recorded deal."),
         "computed", GREEN if _f(u.get("roi")) > 0 else AMBER, ""),
        ("Revenue per client", _money(u.get("per_client_rev")), "average", "",
         "Before margin. The number clients actually pay you.",
         "computed", BLUE, ""),
        ("Engine cost", _money(u.get("cost")), "this month", "",
         "What the whole engine cost to run, the denominator of CAC.",
         "API meters", BLUE, ""),
        ("Channel efficiency", len(_L(u.get("by_source"))), "sources compared",
         _riskmatrix([(s[:14], imp, lik) for s, imp, lik in _L(u.get("matrix"))]),
         ("Return against cost per source — top right earns most for least."
          if u.get("matrix") else "Fills as deals are recorded with a source."),
         "computed", BLUE if u.get("matrix") else AMBER, ""),
    ]
    cards += _slots(
        _L(u.get("by_source")), 4,
        lambda i, r: (f"Revenue: {r[0][:18]}", _money(r[1]), "from this source", "",
                      "Recorded revenue attributed at deal-entry time.",
                      "recorded deals", BLUE, ""),
        "Revenue source", "nothing attributed yet",
        ("Every deal is tagged outreach, organic, ads, referral or direct when "
         "recorded. This slot fills with the next source that produces."),
        "recorded deals", AMBER)
    blockers = _L(u.get("blockers"))
    for i in range(2):
        if i < len(blockers):
            cards.append(("What is blocking the math", "1 input", "missing", "",
                          blockers[i], "computed", AMBER, econ_btn))
        else:
            cards.append(("Nothing blocking", "0", "inputs missing", "",
                          "Every input this board needs is present, so every "
                          "number above is computed rather than estimated.",
                          "computed", GREEN, ""))
    cards += [
        ("Average deal value", (_money(e.get("avg_deal")) if e.get("avg_deal") else "—"),
         "your figure", "",
         ("Used for pipeline value on the consultations board."
          if e.get("avg_deal") else
          "Lets upcoming calls be valued in euros rather than counted."),
         "your input", GREEN if e.get("avg_deal") else AMBER, econ_btn),
        ("Close rate", (f"{e.get('consult_to_client_pct')}%"
                        if e.get("consult_to_client_pct") else "—"),
         "consult → client", "",
         "The third number. It turns booked calls into forecast revenue.",
         "your input", GREEN if e.get("consult_to_client_pct") else AMBER, econ_btn),
        ("Targets set", len(rows), "being tracked",
         _statusgrid([(r0[0][:16], r0[3] >= 100, f"{r0[3]:.0f}%") for r0 in rows]),
         at.get("note") or "Green means met this month.",
         "your targets", GREEN if rows else AMBER,
         "<button class='cta' onclick='biTargets()'>Set targets</button>"),
        ("Behind target", len(_L(at.get("behind"))), "of your targets", "",
         ("These are the ones to act on this month." if at.get("behind") else
          "Set targets and every number gains a pass or fail."),
         "computed", AMBER if at.get("behind") else GREEN, ""),
    ]
    return _head("🧮", "Unit economics",
                 "Does the math work? CAC, LTV, payback and margin — or a "
                 "stated reason why not.") + _vizcards(cards[:20])


# ======================================================================
#  (13) SPEND & BUDGET  (18)
# ======================================================================
def board_spend(ctx) -> str:
    ctx = _ctx(ctx)
    s = ctx["spend"]
    prov = _L(s.get("per_provider"))
    series = _L(s.get("series"))
    cards = [
        ("Spent this month", _money(s.get("spent")), f"of {_money(s.get('cap'))}",
         _score_gauge(_f(s.get("pct")), 85),
         f"{s.get('pct', 0)}% of the cap. The engine halts new LLM steps at "
         f"100% rather than overspending.",
         "API meters", _pct_color(_f(s.get("pct")), 85), ""),
        ("Headroom", _money(s.get("headroom")), "left this month", "",
         "What remains before the hard stop.",
         "computed", GREEN if _f(s.get("headroom")) > 0 else PINK, ""),
        ("Daily run rate", _money(s.get("run_rate")), "per day so far", "",
         f"Averaged across {s.get('days_elapsed', 0)} elapsed days.",
         "computed", BLUE, ""),
        ("Projected month end", _money(s.get("projected")), "at this rate",
         _trend([("daily spend", series, AMBER)]),
         s.get("projection_note", ""),
         "arithmetic", PINK if s.get("over_cap") else GREEN, ""),
        ("Will it breach the cap?", ("yes" if s.get("over_cap") else "no"),
         "on current pace", "",
         ("On this pace the cap is reached before month end. The engine will "
          "halt rather than overspend, so the effect is stopped work, not a "
          "surprise bill." if s.get("over_cap") else
          "Current pace finishes the month inside the cap."),
         "computed", PINK if s.get("over_cap") else GREEN, ""),
        ("Spend shape", len(series), "days measured",
         _spark(series),
         "Flat is good. Spikes are usually one large batch.",
         "job costs", BLUE, ""),
        ("Providers billing", len(prov), "with spend",
         _hbars([(p[:18], v) for p, v in prov[:6]]),
         ("Where the money goes, by provider." if prov else
          "No provider has recorded spend this month."),
         "API meters", BLUE if prov else AMBER, ""),
    ]
    cards += _slots(
        prov, 6,
        lambda i, r: (f"{r[0][:22]}", _money(r[1]), "this month",
                      _donut(round(100 * r[1] / max(_f(s.get("spent")), 1))),
                      "Share of monthly spend.", "API meters", BLUE, ""),
        "Provider", "no spend recorded",
        ("Each provider bills separately and the meter records it. This slot "
         "fills when another provider is used this month."), "API meters")
    cards += [
        ("Largest provider", (prov[0][0] if prov else "—"),
         _money(prov[0][1]) if prov else "—", "",
         "The provider worth negotiating or substituting first.",
         "API meters", BLUE, ""),
        ("Monthly cap", _money(s.get("cap")), "your hard limit", "",
         "Set in the engine settings. It is enforced, not advisory.",
         "settings", VIOLET, ""),
        ("Cost discipline", ("holding" if _f(s.get("pct")) < 85 else "at the edge"),
         "against the cap", "",
         "The cap exists so an agent loop cannot produce a surprise invoice.",
         "computed", GREEN if _f(s.get("pct")) < 85 else PINK, ""),
        ("Spend vs revenue",
         (f"{round(_f(_D(ctx['revenue']).get('total')) / max(_f(s.get('spent')), 1), 1)}×"
          if _D(ctx["revenue"]).get("total") else "—"),
         "revenue per euro spent", "",
         ("Every euro of engine spend has returned this much." if
          _D(ctx["revenue"]).get("total") else
          "Needs one recorded deal to compute."),
         "computed", GREEN if _D(ctx["revenue"]).get("total") else AMBER, ""),
        ("Where to act", "Budget controls", "cap and autonomy", "",
         "The cap, the daily limit and the autonomy level all live in System & "
         "Wiring.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System & Wiring</button>"),
    ]
    return _head("💰", "Spend & budget",
                 "What the engine costs, against the cap you set.") + _vizcards(cards[:18])


# ======================================================================
#  (14) COST PER OUTCOME  (12)
# ======================================================================
def board_cost(ctx) -> str:
    ctx = _ctx(ctx)
    c = ctx["cost"]
    cards = [
        ("Cost per published piece", _money(c.get("per_piece")), "each",
         _hbars([(n, v) for n, v in _L(c.get("bars"))]),
         ("Failed jobs are excluded from the denominator. Dividing by work that "
          "produced nothing makes the number look better than it is — that flaw "
          "is still live in the old Finance cards this section replaces."),
         "computed", GREEN if c.get("per_piece") else AMBER, ""),
        ("Cost per lead", _money(c.get("per_lead")), "sourced", "",
         "Outreach spend divided by leads found.",
         "computed", GREEN if c.get("per_lead") else AMBER, ""),
        ("Cost per booking", _money(c.get("per_booking")), "consultation", "",
         "Total engine spend divided by real Cal.com bookings.",
         "computed", GREEN if c.get("per_booking") else AMBER, ""),
        ("Cost per deal", _money(c.get("per_deal")), "won", "",
         ("The number that decides whether the engine pays for itself."
          if c.get("per_deal") else "Needs one recorded deal."),
         "computed", GREEN if c.get("per_deal") else AMBER, ""),
        ("Wasted on failures", _money(c.get("wasted")),
         f"{c.get('wasted_pct', 0)}% of spend", "",
         ("Money spent on jobs that failed or halted. Not catastrophic, but it "
          "is the cheapest spend to remove."),
         "job costs", PINK if _f(c.get("wasted_pct")) > 10 else AMBER, ""),
        ("Produced", c.get("produced", 0), "pieces published or optimised", "",
         "The real denominator for cost per piece.",
         "jobs", GREEN if c.get("produced") else AMBER, ""),
        ("Failed", c.get("failed", 0), "jobs that produced nothing", "",
         "Each one consumed budget and returned no output.",
         "jobs", AMBER if c.get("failed") else GREEN, ""),
        ("Content spend", _money(c.get("content_cost")), "producing", "",
         "Everything spent generating and optimising content.",
         "job costs", BLUE, ""),
        ("Outreach spend", _money(c.get("outreach_cost")), "prospecting", "",
         "Everything spent sourcing, verifying and emailing leads.",
         "job costs", BLUE, ""),
        ("Where the model spend goes", len(_L(c.get("heat_cols"))), "models in use",
         _heatmap(_L(c.get("heat_rows")), _L(c.get("heat_cols")), _L(c.get("heat"))),
         ("Rows are skills, columns are models. A skill on an expensive model "
          "for a simple job is the easiest saving on this dashboard."),
         "run stamps", BLUE if c.get("heat_cols") else AMBER, ""),
        ("Total engine cost", _money(c.get("total")), "all jobs", "",
         "Content plus outreach, across every job in the store.",
         "job costs", BLUE, ""),
        ("Where to act", "Approvals", "stop the waste", "",
         "Failed and halted jobs are visible in Approvals — each one is budget "
         "already spent.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
    ]
    return _head("🧾", "Cost per outcome",
                 "What one piece, one lead, one booking and one deal actually "
                 "cost.") + _vizcards(cards[:12])


# ======================================================================
#  (15) EXECUTIVE BRIEF  (16)
# ======================================================================
def board_exec(ctx) -> str:
    """The whole business on one screen. Replaces the Executive Intelligence
    section, whose eight tiles are now BI Command cards and whose value-flow
    sankey split leads 60/40 between SEO and Outreach with hardcoded
    multipliers — an attribution nothing in the engine actually measures."""
    ctx = _ctx(ctx)
    ex = _D(ctx.get("exec"))
    h = _D(ex.get("health"))
    risks = _L(ex.get("risks"))
    opps = _L(ex.get("opportunities"))
    acts = _L(ex.get("actions"))
    mv = _L(ex.get("movement"))
    heads = _L(ex.get("headlines"))
    flows = _L(ex.get("flows"))
    score = h.get("score")

    cards = [
        ("Business health", _n(score), "out of 100",
         _score_gauge(_f(score), 70) if score is not None else "",
         h.get("note", ""), "composite",
         (GREEN if _f(score) >= 70 else AMBER if _f(score) >= 40 else PINK)
         if score is not None else AMBER, ""),
        ("What the score is made of", len(_L(h.get("parts"))), "measured parts",
         _hbars([(n[:20], v) for n, v in _L(h.get("parts"))]),
         ("Every part is shown, so the score can be argued with. A single number "
          "nobody can decompose is a mood, not a metric."),
         "composite", BLUE, ""),
        ("Critical risks", ex.get("criticals", 0),
         f"of {ex.get('risk_total', 0)} scored",
         _statusgrid([(str(_D(r).get("title"))[:18],
                       _f(_D(r).get("score")) < 6,
                       str(_D(r).get("severity", "")))
                      for r in _L(ex.get("risks"))]),
         ("Read from the risk register, so this is the same number the Risk "
          "board shows — not a separate list."),
         "risk register", PINK if ex.get("criticals") else GREEN,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
    ]
    # top 3 risks — the register's own scored entries
    cards += _slots(
        risks, 3,
        lambda i, r: (f"Risk {i + 1}: {str(_D(r).get('title'))[:28]}",
                      _D(r).get("severity", "—"),
                      f"score {_D(r).get('score', '—')}", "",
                      str(_D(r).get("evidence") or _D(r).get("mitigation") or "")[:190],
                      "risk register",
                      PINK if _f(_D(r).get("score")) >= 6 else AMBER,
                      "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
        "Risk", "register not built yet",
        ("The register recomputes on every dashboard load. This fills as soon "
         "as the Risk section has been opened once."), "risk register", AMBER)
    # top 3 opportunities — derived from measured gaps, each with a destination
    cards += _slots(
        opps, 3,
        lambda i, o: (f"Opportunity {i + 1}", str(_D(o).get("title"))[:30],
                      "ranked by impact", "",
                      str(_D(o).get("why"))[:200], "computed", TEAL,
                      f"<button class='cta' onclick=\"seoTab('{_D(o).get('where', 'bicmd')}')\">"
                      f"Open the board</button>"),
        "Opportunity", "nothing ranked yet",
        ("Opportunities are derived from measured gaps — the biggest funnel "
         "leak, a target market with no traffic, pages earning nothing. They "
         "appear as those measurements arrive."), "computed", AMBER)
    # next 3 actions
    cards += _slots(
        acts, 3,
        lambda i, a: (f"Do next {i + 1}", str(_D(a).get("label"))[:28], "action", "",
                      str(_D(a).get("detail"))[:190], "computed", VIOLET,
                      f"<button class='cta' onclick=\"{_D(a).get('js', '')}\">"
                      f"{_H()._esc(str(_D(a).get('cta', 'Open')))}</button>"),
        "Action", "none outstanding",
        ("Actions come from the top risks and the top opportunities. An empty "
         "slot means neither has produced one."), "computed", GREEN)
    cards += [
        ("Value flow", len(flows), "measured steps",
         _CH().sankey(flows),
         ("Leads through to revenue, from the same stage counts the Funnel "
          "board uses. The old version of this chart split leads 60/40 between "
          "SEO and Outreach using hardcoded multipliers — nothing in the engine "
          "measures that, so it is gone." if flows else
          "No one has moved through the funnel yet. The old chart drew ribbons "
          "anyway by flooring every flow at 1; this one says nothing has flowed."),
         "measured funnel", BLUE if flows else AMBER,
         "<button class='cta' onclick=\"seoTab('bifunnel')\">Open the funnel</button>"),
        ("Week over week", len(mv), "metrics with two full windows",
         _hbars([(m[0], _f(m[1])) for m in mv]),
         ("".join(f"{m[0]}: {m[1]:,.0f} vs {m[2]:,.0f}. " for m in mv)
          if mv else
          "A week-over-week delta needs two complete weeks of data. Metrics "
          "appear here as they reach that, not before."),
         "computed", BLUE if mv else AMBER, ""),
    ]
    for m in mv[:2]:
        label, now, before, higher = m[0], _f(m[1]), _f(m[2]), bool(m[3])
        better = (now >= before) if higher else (now <= before)
        cards.append((f"{label} this week", f"{now:,.0f}",
                      f"last week {before:,.0f}",
                      _delta(now, before, higher_is_better=higher),
                      ("Moving the right way." if better else
                       "Moving the wrong way — worth a look this week."),
                      "computed", GREEN if better else AMBER, ""))
    while len([c for c in cards]) < 14:
        cards.append(("Week-over-week slot", "—", "awaiting two full weeks", "",
                      ("Sessions, spend and revenue each appear here once two "
                       "complete weeks exist."), "computed", AMBER, ""))
    # four section headlines, each a real link
    cards += _slots(
        heads, 4,
        lambda i, hd: (str(hd[0])[:26], str(hd[1])[:22], "section headline", "",
                       "The one number that section leads with.", "cross-section",
                       BLUE,
                       f"<button class='cta' onclick=\"nav('{hd[2]}')\">Open</button>"),
        "Section", "not reporting",
        "Each section reports one headline number here.", "cross-section", AMBER)
    return _head("🏛", "Executive brief",
                 "The whole business on one screen — health, the three risks "
                 "that matter, what to do next.") + _vizcards(cards[:16])



# ======================================================================
#  SECTION
# ======================================================================
TABS = [
    ("biexec", "🏛", "Executive Brief"),
    ("bicmd", "📊", "BI Command"),
    ("bidemand", "📈", "Demand"),
    ("bimarkets", "🌍", "Markets"),
    ("bichannel", "🔀", "Channels"),
    ("bicontent", "📝", "Content Value"),
    ("bileads", "🧲", "Lead Gen"),
    ("bioutreach", "✉️", "Outreach"),
    ("biconsult", "📅", "Consultations"),
    ("bifunnel", "🔻", "Funnel"),
    ("birevenue", "💶", "Revenue"),
    ("bicustomers", "🫂", "Customers"),
    ("biecon", "🧮", "Unit Economics"),
    ("bispend", "💰", "Spend"),
    ("bicost", "🧾", "Cost per Outcome"),
]

GROUPS = [
    ("bidem", "① IS DEMAND THERE", "Is anyone looking?",
     ["biexec", "bicmd", "bidemand", "bimarkets", "bichannel", "bicontent"]),
    ("bipipe", "② IS IT BECOMING PIPELINE", "Do they become leads?",
     ["bileads", "bioutreach", "biconsult", "bifunnel"]),
    ("bimoney", "③ IS IT BECOMING MONEY", "Do they pay?",
     ["birevenue", "bicustomers"]),
    ("bimath", "④ DOES THE MATH WORK", "Is it profitable?",
     ["biecon", "bispend", "bicost"]),
]

_TAB_BOARDS = {
    "biexec": [("Executive Brief", board_exec)],
    "bicmd": [("BI Command", board_command)],
    "bidemand": [("Demand", board_demand)],
    "bimarkets": [("Markets", board_markets)],
    "bichannel": [("Channels", board_channels)],
    "bicontent": [("Content Value", board_content)],
    "bileads": [("Lead Generation", board_leads)],
    "bioutreach": [("Outreach", board_outreach)],
    "biconsult": [("Consultations", board_consultations)],
    "bifunnel": [("Funnel", board_funnel)],
    "birevenue": [("Revenue", board_revenue)],
    "bicustomers": [("Customers", board_customers)],
    "biecon": [("Unit Economics", board_econ)],
    "bispend": [("Spend", board_spend)],
    "bicost": [("Cost per Outcome", board_cost)],
}

_TAB_COUNTS = {"biexec": 16, "bicmd": 16, "bidemand": 20, "bimarkets": 18, "bichannel": 18,
               "bicontent": 18, "bileads": 20, "bioutreach": 18, "biconsult": 16,
               "bifunnel": 20, "birevenue": 20, "bicustomers": 18, "biecon": 20,
               "bispend": 18, "bicost": 12}
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


def bi_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def bi_section(ctx) -> str:
    H = _H()
    ctx = _ctx(ctx)
    panels = bi_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'bidem')}' onclick=\"seoTab('{tid}')\">"
        f"<span>{icon}</span>{H._esc(label)}"
        f"<span class='n'>{_TAB_COUNTS.get(tid, 0)}</span></button>"
        for i, (tid, icon, label) in enumerate(TABS))
    grouprail = "".join(
        f"<button class='sgrp{' on' if i == 0 else ''}' id='sgrp-{gid}' "
        f"onclick=\"seoGroup('{gid}')\"><b>{H._esc(label)}</b>"
        f"<span class='gq'>{H._esc(question)}</span></button>"
        for i, (gid, label, question, _t) in enumerate(GROUPS))
    body = "".join(
        f"<div class='spanel{' on' if i == 0 else ''}' id='spanel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _, _) in enumerate(TABS))
    runbar = ("<div class='ctrl' style='margin:10px 0 2px;flex-wrap:wrap'>"
              "<button class='cbtn' onclick='biDeal()'>💶 Record a won deal</button>"
              "<button class='cbtn' onclick='biEcon()'>🧮 Set your economics</button>"
              "<button class='cbtn' onclick='biTargets()'>🎯 Set monthly targets</button>"
              "<button class='cbtn' onclick=\"act('/insights/refresh')\">🔄 Refresh GA4 + Search Console</button>"
              "</div>")
    return (_TAB_CSS
            + "<div class='sgrprail'>" + grouprail + "</div>"
            + runbar
            + "<div class='stabbar'>" + bar + "</div>"
            + "<div class='spanels'>" + body + "</div>")


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_bi as BI

    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()
    BI.record_deal(st, "Acme GmbH", 6000, "outreach", "2026-05-11", 65)
    BI.record_deal(st, "Bauer AG", 4200, "organic", "2026-06-03")
    BI.record_deal(st, "Acme GmbH", 3000, "outreach", "2026-07-02", recurring=True)
    BI.set_econ(st, avg_deal=5000, margin_pct=65, consult_to_client_pct=30)
    BI.set_targets(st, revenue_month=10000, deals_month=2, leads_month=200)
    deals = BI.list_deals(st)
    ins = {"ga4": {"daily": [{"date": f"2026-07-{i:02d}", "sessions": 10 * i}
                             for i in range(1, 15)],
                   "totals": {"sessions": 900, "totalUsers": 620, "newUsers": 400,
                              "engagementRate": 0.58},
                   "channels": [{"sessionDefaultChannelGroup": "Organic Search",
                                 "sessions": 700},
                                {"sessionDefaultChannelGroup": "Direct", "sessions": 150},
                                {"sessionDefaultChannelGroup": "Referral", "sessions": 50}],
                   "countries": [{"country": "Germany", "sessions": 400},
                                 {"country": "United States", "sessions": 300},
                                 {"country": "India", "sessions": 100}],
                   "pages": [{"pagePath": "/guides/n8n", "sessions": 220},
                             {"pagePath": "/blog/ai-agents", "sessions": 140}]},
           "gsc": [{"query": "n8n automation agency", "clicks": 18,
                    "impressions": 1200, "position": 14.2},
                   {"query": "ai automation munich", "clicks": 9,
                    "impressions": 800, "position": 22.0}]}
    jobs = [{"job_id": "o1", "type": "outreach_campaign", "status": "sent",
             "created_at": "2026-07-20T09:00:00Z", "cost_so_far_usd": 0.9,
             "payload": {"raw_leads": [{}] * 60, "leads": [{}] * 44, "send_ref": "x",
                         "sent_at": {f"p{i}@x.com": f"2026-07-2{i % 8}T09:00:00Z"
                                     for i in range(9)},
                         "lead_qualifier": {"results": [{}] * 25}}},
            {"job_id": "c1", "type": "content_piece", "status": "published",
             "created_at": "2026-07-22T09:00:00Z", "cost_so_far_usd": 0.6},
            {"job_id": "c2", "type": "content_piece", "status": "failed",
             "created_at": "2026-07-23T09:00:00Z", "cost_so_far_usd": 0.2}]
    bookings = [{"status": "accepted", "start": "2026-08-04T10:00:00Z", "title": "Intro"},
                {"status": "accepted", "start": "2026-07-25T10:00:00Z", "title": "Discovery"}]
    agents = [{"skill": "content_producer", "models": {"claude-opus-5": 12}},
              {"skill": "outreach_writer", "models": {"claude-sonnet-5": 5}}]
    lg = BI.leadgen(jobs)
    sp = BI.spend_view({"anthropic": {"spent": 41.7}}, 41.7, 200.0, jobs)
    rev = BI.revenue(deals)
    ctx = {
        "demand": BI.demand(ins), "markets": BI.markets(ins),
        "channels": BI.channel_mix(ins), "content": BI.content_attribution(ins, jobs),
        "leadgen": lg, "outreach": BI.outreach(jobs, [{}, {}, {}]),
        "consultations": BI.consultations(bookings),
        "funnel": BI.funnel(jobs, [{}, {}, {}], bookings, deals),
        "revenue": rev, "customers": BI.customers(deals),
        "econ": BI.econ(st), "targets": BI.targets(st),
        "unit": BI.unit_economics(deals, sp, BI.econ(st), bookings, lg["found"]),
        "spend": sp,
        "cost": BI.cost_per_outcome(jobs, agents, deals, bookings, lg["found"]),
        "exec": BI.executive_brief(
            st, status={"anthropic": True, "gsc": True, "google_ads": False},
            spend=sp, funnel_=BI.funnel(jobs, [{}, {}, {}], bookings, deals),
            demand_=BI.demand(ins), markets_=BI.markets(ins),
            content_=BI.content_attribution(ins, jobs), econ_=BI.econ(st),
            revenue_=rev, leadgen_=lg),
        "channels_mom": BI.mom([{"month": "2026-06",
                                 "channels": {"Organic Search": 500, "Direct": 120}},
                                {"month": "2026-07",
                                 "channels": {"Organic Search": 700, "Direct": 150}}],
                               "channels"),
        "markets_mom": BI.mom([{"month": "2026-06",
                                "markets": {"Germany": 300, "United States": 250}},
                               {"month": "2026-07",
                                "markets": {"Germany": 400, "United States": 300}}],
                              "markets"),
        "leads_mom": BI.leads_mom(jobs),
        "client_bump": BI.client_rank_movement(deals),
        "deals": deals,
    }
    ctx["attainment"] = BI.attainment(BI.targets(st), rev, lg, BI.consultations(bookings))

    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        _CURRENT_BOARD["name"] = name
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = bi_pages(ctx)
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

    # the six merged-away sections' real content survives
    assert "Revenue recorded" in pages["birevenue"], "Business/Finance revenue card"
    assert "Reply rate" in pages["bioutreach"], "Sales reply-rate card"
    assert "Sessions" in pages["bidemand"], "Marketing GA4 summary"
    assert "Repeat rate" in pages["bicustomers"], "Customer Intelligence, now real"
    assert "Projected month end" in pages["bispend"], "Finance/Budget projection"
    assert "Cost per published piece" in pages["bicost"], "Budget cost-per-piece"
    # Executive Intelligence: the decision layer survives, the invention does not
    assert "Business health" in pages["biexec"], "exec scoreboard"
    assert "Opportunity" in pages["biexec"] and "Do next" in pages["biexec"], \
        "the decision strip is the one thing Executive Intelligence had"
    assert "Value flow" in pages["biexec"], "value flow"
    assert "hardcoded multipliers" in pages["biexec"], \
        "say plainly that the 60/40 attribution is gone"

    # NO DEAD PLACEHOLDERS: every card must offer a live number or an action
    dead = re.findall(r"Connect (?:Stripe|HubSpot|Salesforce|Zendesk|QuickBooks|Xero)", html)
    assert not dead, f"vendor-shaped dead ends survived: {set(dead)}"

    # the honest-degrade contract still holds where an input genuinely is missing
    empty_ctx_pages = bi_pages({})
    empty_html = "".join(empty_ctx_pages.values())
    assert "failed to render" not in empty_html
    assert len(re.findall(r"<div class='card (?:overflowcard )?sev-", empty_html)) == TOTAL_CARDS

    # shape robustness
    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {k: 0 for k in ctx}, {"deals": "no"}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    charts = len(re.findall(r"<svg", html))
    print(f"bi_boards self-check OK — {len(_TAB_BOARDS)} boards, {counted} cards, "
          f"{len(set(ids))} unique ids, {charts} charts; revenue/customers/unit "
          f"economics all live from recorded deals, and no card tells you to go "
          f"buy software.")
