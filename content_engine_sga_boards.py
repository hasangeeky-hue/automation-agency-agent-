"""
content_engine_sga_boards.py
============================================================================
SGA — SOCIAL, GROWTH & ADS. 14 boards, 250 cards.

Replaces three sections (Social Media, Google Hub, Ads & Growth) that held 27
cards, ZERO charts, and 19 panels that were literally _empty().

Scope: paid and unpaid SOCIAL — planning, creative, posting and the analytics
behind them — plus the Google data hub. Google Ads keeps its own 296-card Media
Buying section and nothing here duplicates it.

Three boards ship deliberately empty: Audience, Engagement and the spend half
of Paid Social. Every social connector in this engine is post-only, so those
numbers have no data path at all. Each card names the exact read scope that
would fill it — "Meta Graph read_insights", "LinkedIn r_organization_social" —
never a vendor to buy, and never an invented number.

Run offline self-check:  python content_engine_sga_boards.py
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
    "SGA Command": ("Plan a campaign", "sgaCampaign()"),
    "Campaign Planner": ("Plan a campaign", "sgaCampaign()"),
    "Creative Library": ("Open Content Factory", "nav('content')"),
    "Organic Push": ("Open Approvals", "nav('appr')"),
    "Paid Social": ("Plan a campaign", "sgaCampaign()"),
    "Audience Targeting": ("Plan a campaign", "sgaCampaign()"),
    "Blog Push": ("Open Content Factory", "nav('content')"),
    "Channel Health": ("Connect a channel", "nav('system')"),
    "Audience": ("Connect a read scope", "nav('system')"),
    "Engagement": ("See traffic instead", "seoTab('sgatraffic')"),
    "Social Traffic": ("Open SEO", "nav('seo')"),
    "Social Revenue": ("Record a won deal", "biDeal()"),
    "Budget & Pacing": ("Open BI", "nav('bi')"),
    "Google Hub": ("Open System & Wiring", "nav('system')"),
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
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in ("posts", "cadence", "creatives", "blog", "channels", "audience",
              "engagement", "paid", "traffic", "revenue", "budget", "hub",
              "calendar", "cost_series"):
        out[k] = _D(out.get(k))
    out["campaigns"] = _L(out.get("campaigns"))
    return out


READ_SCOPE_ROWS = [
    ("LinkedIn", "LinkedIn r_organization_social (page statistics)"),
    ("Facebook", "Meta Graph API read_insights on the Page"),
    ("Instagram", "Meta Graph API instagram_manage_insights"),
    ("YouTube", "YouTube Analytics API (OAuth, yt-analytics.readonly)"),
    ("X / Twitter", "X API v2 tweet metrics (paid tier)"),
    ("TikTok", "TikTok Business API video insights"),
]
PAID_SCOPE_ROWS = [
    ("Facebook", "Meta Marketing API (ads_read)"),
    ("Instagram", "Meta Marketing API (ads_read)"),
    ("LinkedIn", "LinkedIn Ads API (r_ads_reporting)"),
    ("TikTok", "TikTok Ads API (reporting)"),
]


def _needs(ctx, key, fallback):
    """The scope list is a constant — never let an empty context shrink it."""
    rows = _L(_D(ctx).get(key))
    return rows if rows else list(fallback)


def _chan_rows(ctx):
    rows = _L(_D(ctx.get("channels")).get("rows"))
    if rows:
        return rows
    return [{"channel": lbl.lower(), "label": lbl, "connected": False,
             "posts": 0, "posting": False, "read_scope": scope,
             "state": "not connected"} for lbl, scope in READ_SCOPE_ROWS]


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


CH_LABELS = ("LinkedIn", "Facebook", "Instagram", "YouTube", "X / Twitter", "TikTok")


# ======================================================================
#  (1) SGA COMMAND  (16)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    p, cd, ch = ctx["posts"], ctx["cadence"], ctx["channels"]
    cal, tr, rev = ctx["calendar"], ctx["traffic"], ctx["revenue"]
    bg, paid, hub = ctx["budget"], ctx["paid"], ctx["hub"]
    cards = [
        ("Posts that actually went out", _i(p.get("total")), "delivered",
         _trend([("posts/day", _L(p.get("series")), TEAL)]),
         (f"{_i(p.get('attempted'))} attempted, {_i(p.get('failed_total'))} hit a "
          f"channel that is not connected. A post to an unconnected channel is "
          f"not a post."),
         "published refs", GREEN if p.get("total") else AMBER, ""),
        ("Channels posting", _i(ch.get("posting")), f"of {_i(ch.get('total'))}",
         _statusgrid(_L(ch.get("statusgrid"))),
         "Green means connected. The label says whether anything has gone out.",
         "wire status", GREEN if ch.get("posting") else AMBER, ""),
        ("Campaigns live", _i(cal.get("live_count")), f"of {_i(cal.get('planned'))} planned",
         _CH().gantt(_L(cal.get("tasks")), span=21),
         ("Your plan on a timeline." if cal.get("has_data") else
          "No campaign planned yet. A campaign is what the calendar, the "
          "creative library, the UTM tag and the paid split all key on."),
         "your campaigns", GREEN if cal.get("live_count") else AMBER,
         "<button class='cta' onclick='sgaCampaign()'>Plan a campaign</button>"),
        ("Cadence adherence", f"{cd.get('adherence', 0)}%", "of days on target",
         _score_gauge(_f(cd.get("adherence")), 70),
         (f"Target is {_i(cd.get('target_per_channel'))} per channel across "
          f"{_i(cd.get('channels_planned'))} channels = {_i(cd.get('daily_target'))} "
          f"posts a day. The old card asked this question and showed nothing."),
         "computed", _pct_color(100 - _f(cd.get("adherence")), 30), ""),
        ("Social sessions", _i(tr.get("social_sessions")), "visits from social",
         _donut(_f(tr.get("social_share"))),
         (f"{tr.get('social_share', 0)}% of all sessions." if tr.get("has_ga4")
          else "GA4 is not returning channel rows yet."),
         "GA4", GREEN if tr.get("social_sessions") else AMBER, ""),
        ("Sessions per post", _n(tr.get("sessions_per_post")), "average", "",
         ("The honest measure of a post while no platform read scope exists — "
          "and arguably the better one for a business selling projects."),
         "computed", BLUE, ""),
        ("Revenue from social", _money(rev.get("revenue")), "recorded", "",
         (f"{rev.get('share_of_revenue', 0)}% of all recorded revenue."
          if rev.get("has_data") else str(rev.get("note", ""))),
         "recorded deals", GREEN if rev.get("has_data") else AMBER, ""),
        ("Paid social spend", _money(paid.get("spend") if paid.get("measured") else None),
         "actual", "",
         (str(paid.get("note", "")) if not paid.get("measured") else
          "Read from the ad platforms."),
         "ad platforms", AMBER if not paid.get("measured") else GREEN, ""),
        ("Paid budget planned", _money(paid.get("planned_budget")), "across campaigns",
         "", "What you have committed to paid social in your own campaign plan.",
         "your campaigns", BLUE if paid.get("planned_budget") else AMBER, ""),
        ("Content produced", _i(ctx["creatives"].get("total")), "social pieces",
         _treemap(_L(ctx["creatives"].get("treemap"))),
         (f"{ctx['creatives'].get('video_rate', 0)}% video, "
          f"{ctx['creatives'].get('image_rate', 0)}% image, "
          f"{ctx['creatives'].get('text_only_rate', 0)}% text only."),
         "produced pieces", BLUE if ctx["creatives"].get("total") else AMBER, ""),
        ("Blog pieces published", _i(ctx["blog"].get("total")), "long-form", "",
         f"Costing {_money(ctx['blog'].get('per_piece'))} each to produce.",
         "published refs", GREEN if ctx["blog"].get("total") else AMBER, ""),
        ("UTM tagging", "on", "every posted link", "",
         ("Every link the engine posts now carries utm_source, utm_medium, "
          "utm_campaign and utm_content, so GA4 can credit an individual post "
          "with a session and a booking. No platform API needed."),
         "post path", GREEN, ""),
        ("Engagement metrics", "not available", "likes, comments, shares", "",
         str(ctx["engagement"].get("note", "")),
         "read scope", AMBER, ""),
        ("Google hub", ("verified" if hub.get("sheets_verified") else "local counts"),
         "Sheets · Drive · Gmail", "",
         str(hub.get("note", "")),
         "Google hub", GREEN if hub.get("sheets_verified") else AMBER, ""),
        ("Spend against the cap", f"{bg.get('pct_of_cap', 0)}%", "of the engine cap",
         _score_gauge(_f(bg.get("pct_of_cap")), 85),
         "Engine spend, not ad spend. Ad spend is planned-only until a platform "
         "reports it.",
         "API meters", _pct_color(_f(bg.get("pct_of_cap")), 85), ""),
        ("Where Google Ads lives", "Media Buying", "296 cards, separate", "",
         ("Google Ads is a different discipline and keeps its own section. This "
          "one is social — paid and unpaid — plus your Google data hub."),
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('media')\">Open Media Buying</button>"),
    ]
    return _head("🚀", "SGA command",
                 "Social, growth and ads on one screen — what went out, what "
                 "landed, what it cost.") + _vizcards(cards)


# ======================================================================
#  (2) CAMPAIGN PLANNER  (20)
# ======================================================================
def board_planner(ctx) -> str:
    ctx = _ctx(ctx)
    cal, camps = ctx["calendar"], ctx["campaigns"]
    plan_btn = "<button class='cta' onclick='sgaCampaign()'>Plan a campaign</button>"
    cards = [
        ("Campaign calendar", _i(cal.get("planned")), "campaigns",
         _CH().gantt(_L(cal.get("tasks")), span=21),
         ("Three weeks either side of today." if cal.get("has_data") else
          "Nothing planned. A campaign gives every post a name, a UTM tag, a "
          "budget line and a place on this timeline."),
         "your campaigns", GREEN if cal.get("has_data") else AMBER, plan_btn),
        ("Live now", _i(cal.get("live_count")), "running today", "",
         "Campaigns whose start has passed and whose end has not.",
         "computed", GREEN if cal.get("live_count") else AMBER, ""),
        ("Paid campaigns", _i(cal.get("paid")), "with a budget",
         _split_donut([("paid", _i(cal.get("paid")), PINK),
                       ("organic", _i(cal.get("organic")), TEAL)]),
         "The split between what you pay to distribute and what you post.",
         "your campaigns", BLUE, ""),
        ("Organic campaigns", _i(cal.get("organic")), "no ad spend", "",
         "Organic compounds; paid stops the day you stop paying.",
         "your campaigns", BLUE, ""),
        ("Total planned budget", _money(cal.get("budget")), "across campaigns", "",
         "Your commitment, not measured spend — no ad platform reports back yet.",
         "your campaigns", BLUE if cal.get("budget") else AMBER, ""),
        ("Objectives in play", len({_D(c).get("objective") for c in camps}),
         "distinct goals",
         _hbars([(o, sum(1 for c in camps if _D(c).get("objective") == o))
                 for o in {_D(c).get("objective") for c in camps} if o]),
         "Awareness, leads and bookings need different creative and different "
         "measurement.",
         "your campaigns", BLUE if camps else AMBER, ""),
    ]
    cards += _slots(
        camps, 8,
        lambda i, c: (f"{_D(c).get('name', '')[:24]}",
                      ("paid" if _D(c).get("paid") else "organic"),
                      f"{_D(c).get('start', '')} → {_D(c).get('end') or 'open'}",
                      _donut(100 if _D(c).get("paid") else 40),
                      (f"Objective: {_D(c).get('objective')}. Channels: "
                       f"{', '.join(_L(_D(c).get('channels'))) or 'none set'}. "
                       f"Budget {_money(_D(c).get('budget'))}."),
                      "your campaigns", PINK if _D(c).get("paid") else TEAL,
                      f"<button class='cta' onclick=\"sgaCampaignDelete('{_D(c).get('id','')}')\">"
                      f"Remove</button>"),
        "Campaign slot", "nothing planned",
        ("A campaign takes a name, an objective, the channels and a date range. "
         "Every post made while it runs is tagged with it."),
        "your campaigns", AMBER)
    cards += [
        ("Channels covered", len({c for x in camps for c in _L(_D(x).get("channels"))}),
         "distinct platforms",
         _statusgrid([(lbl, any(lbl.lower().split()[0] in
                                " ".join(_L(_D(x).get("channels"))).lower()
                                for x in camps), "")
                      for lbl in CH_LABELS]),
         "Green means at least one planned campaign targets that channel.",
         "your campaigns", BLUE, ""),
        ("Campaign → UTM", "automatic", "on every posted link", "",
         ("The campaign name becomes utm_campaign, so GA4 groups every session "
          "from that campaign together without you doing anything."),
         "post path", GREEN, ""),
        ("Planning gap",
         ("none" if cal.get("live_count") else "no live campaign"),
         "today", "",
         ("Posts made outside a campaign are tagged utm_campaign=organic. That "
          "is honest, but it means they cannot be compared against each other."
          if not cal.get("live_count") else
          "Everything posted today is attributed to a named campaign."),
         "computed", AMBER if not cal.get("live_count") else GREEN, ""),
        ("Where the content comes from", "Content Factory", "briefs and drafts", "",
         "The campaign says what to say and when; the Content Factory writes it.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('content')\">Open Content Factory</button>"),
        ("Approval gate", "on", "nothing posts itself", "",
         "Every piece waits for you in Approvals before it can go out.",
         "engine", GREEN,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ("Cadence target", _i(ctx["cadence"].get("target_per_channel")),
         "posts per channel per day", "",
         "Set by the scheduler. The Organic Push board measures you against it.",
         "scheduler", BLUE, ""),
    ]
    return _head("🗓", "Campaign planner",
                 "What you are running, on which channels, with what budget "
                 "and for how long.") + _vizcards(cards[:20])


# ======================================================================
#  (3) CREATIVE LIBRARY  (16)
# ======================================================================
def board_creative(ctx) -> str:
    ctx = _ctx(ctx)
    cr = ctx["creatives"]
    fmts = _L(cr.get("by_format"))
    cards = [
        ("Pieces produced", _i(cr.get("total")), "for social",
         _treemap(_L(cr.get("treemap"))),
         ("Size is how many posts used that format." if cr.get("has_data")
          else "Fills as the content agent produces social pieces."),
         "produced pieces", GREEN if cr.get("total") else AMBER, ""),
        ("Video", f"{cr.get('video_rate', 0)}%", "of posts",
         _donut(_f(cr.get("video_rate"))),
         ("Video outperforms static on every social platform, and it is the "
          "format this library has least of."),
         "produced pieces", _pct_color(100 - _f(cr.get("video_rate")), 70), ""),
        ("Image", f"{cr.get('image_rate', 0)}%", "of posts",
         _donut(_f(cr.get("image_rate"))),
         "An image post reliably beats a text-only post for reach.",
         "produced pieces", BLUE, ""),
        ("Text only", f"{cr.get('text_only_rate', 0)}%", "of posts",
         _donut(_f(cr.get("text_only_rate"))),
         ("Text-only posts are the cheapest to make and the weakest performers "
          "on most platforms. LinkedIn is the exception."),
         "produced pieces", AMBER if _f(cr.get("text_only_rate")) > 50 else BLUE, ""),
        ("Formats in use", len(fmts), "of 5",
         _hbars([(f, n) for f, n in fmts]),
         "Text, image, video, link, carousel.",
         "produced pieces", BLUE, ""),
    ]
    cards += _slots(
        fmts, 5,
        lambda i, r: (f"Format: {r[0]}", r[1], "posts",
                      _donut(round(100 * _i(r[1]) / max(_i(cr.get("total")), 1))),
                      "Share of the social library in this format.",
                      "produced pieces", BLUE),
        "Format", "not produced yet",
        "The library covers five formats. This fills when one is first used.",
        "produced pieces")
    cards += [
        ("Assets with an image", _i(cr.get("with_image")), "pieces", "",
         "Read from image_url on the produced piece.",
         "produced pieces", BLUE, ""),
        ("Assets with a video", _i(cr.get("with_video")), "pieces", "",
         "Read from video_url on the produced piece.",
         "produced pieces", BLUE, ""),
        ("Creative per campaign", "not grouped yet", "needs a campaign", "",
         ("Once posts carry a campaign, this board can rank formats BY campaign "
          "rather than in aggregate."),
         "your campaigns", AMBER, ""),
        ("Reuse", "one piece, many channels", "how the engine works", "",
         ("A produced piece is repurposed per channel — LinkedIn gets the long "
          "form, X gets 280 characters, Instagram gets the image."),
         "engine", GREEN, ""),
        ("Where creative is made", "Content Factory", "briefs, drafts, images", "",
         "This board measures what exists; the factory is where it is made.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('content')\">Open Content Factory</button>"),
        ("Which creative won", "see Social → Traffic", "by sessions", "",
         ("With no platform read scope, the honest ranking of a creative is the "
          "traffic and the bookings it produced — both measured."),
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('sgatraffic')\">Open Social → Traffic</button>"),
    ]
    return _head("🎨", "Creative library",
                 "What formats you are producing, and which you are short "
                 "of.") + _vizcards(cards[:16])


# ======================================================================
#  (4) ORGANIC PUSH  (20)
# ======================================================================
def board_organic(ctx) -> str:
    ctx = _ctx(ctx)
    p, cd = ctx["posts"], ctx["cadence"]
    by_ch = _L(p.get("by_channel"))
    failed = _L(p.get("failed"))
    cards = [
        ("Posts delivered", _i(p.get("total")), "actually sent",
         _CH().cohort(_L(p.get("cohort_cols")), _L(p.get("cohort_grid"))),
         "Rows are channels, columns are days. A blank row is a channel that is "
         "planned but silent.",
         "published refs", GREEN if p.get("total") else AMBER, ""),
        ("Attempted", _i(p.get("attempted")), "posts tried", "",
         ("Every attempt, including ones that hit an unconnected channel."),
         "published refs", BLUE, ""),
        ("Failed to post", _i(p.get("failed_total")), "channel not connected",
         _hbars([(c, n) for c, n in failed]),
         ("The engine returns a *_not_configured marker rather than crashing. "
          "These are counted as failures here, not as posts."),
         "published refs", PINK if p.get("failed_total") else GREEN, ""),
        ("Delivery rate",
         f"{round(100 * _i(p.get('total')) / max(_i(p.get('attempted')), 1))}%",
         "of attempts landed",
         _score_gauge(round(100 * _i(p.get("total")) / max(_i(p.get("attempted")), 1)), 90),
         "Below 100% means a channel in the plan has no credentials.",
         "computed", BLUE, ""),
        ("Posts per day", len(_L(p.get("per_day"))), "days with a post",
         _trend([("posts", _L(p.get("series")), TEAL)]),
         "Steady beats bursty — every platform rewards consistency.",
         "published refs", BLUE, ""),
        ("Cadence adherence", f"{cd.get('adherence', 0)}%", "of days on target",
         _score_gauge(_f(cd.get("adherence")), 70),
         (f"{_i(cd.get('days_on_target'))} of {_i(cd.get('days_measured'))} days "
          f"hit {_i(cd.get('daily_target'))} posts."),
         "computed", _pct_color(100 - _f(cd.get("adherence")), 30), ""),
        ("Daily average", _n(cd.get("avg")), "posts per day", "",
         f"Against a target of {_i(cd.get('daily_target'))}.",
         "computed", BLUE, ""),
        ("Channels producing", _i(p.get("channels_live")), "of 6",
         _hbars([(c, n) for c, n in by_ch]),
         "Ranked by delivered posts.",
         "published refs", BLUE, ""),
    ]
    cards += _slots(
        by_ch, 6,
        lambda i, r: (f"{r[0]}", r[1], "posts delivered",
                      _donut(round(100 * _i(r[1]) / max(_i(p.get("total")), 1))),
                      "Share of everything that actually went out.",
                      "published refs", GREEN if i == 0 else BLUE),
        "Channel", "nothing delivered",
        ("A channel appears here once a post to it has succeeded. Connect it in "
         "System & Wiring first."), "published refs")
    cards += [
        ("Approval before posting", "on", "nothing self-publishes", "",
         "Every social piece waits in Approvals.",
         "engine", GREEN,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ("Repurposing", "automatic", "one piece per channel", "",
         "The engine reshapes a piece per platform rather than cross-posting "
         "the same text everywhere.",
         "engine", GREEN, ""),
        ("UTM on every link", "on", "so GA4 can credit the post", "",
         "utm_source is the channel, utm_campaign the campaign, utm_content the "
         "post id.",
         "post path", GREEN, ""),
        ("What is missing", "engagement", "no read scope", "",
         ("Delivery is measured. Whether anyone liked it is not — no social "
          "connector here can read. See the Engagement board for exactly which "
          "scope each platform needs."),
         "read scope", AMBER,
         "<button class='cta' onclick=\"seoTab('sgaengage')\">Open Engagement</button>"),
        ("Best measure available", "sessions per post", "from GA4", "",
         "Until a read scope exists, traffic is the honest performance signal.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('sgatraffic')\">Open Social → Traffic</button>"),
        ("Scheduler cadence", _i(cd.get("target_per_channel")),
         "per channel per day", "",
         "Change it in the scheduler settings; this board measures against it.",
         "scheduler", BLUE, ""),
    ]
    return _head("📤", "Organic push",
                 "What went out, to which channel, and whether it landed.") + _vizcards(cards[:20])


# ======================================================================
#  (5) PAID SOCIAL  (20)
# ======================================================================
def board_paid(ctx) -> str:
    ctx = _ctx(ctx)
    pd_ = ctx["paid"]
    needs = _L(pd_.get("needs"))
    planned = _L(pd_.get("planned"))
    cards = [
        ("Paid spend", _money(pd_.get("spend") if pd_.get("measured") else None),
         "measured",
         _CH().vbars([c[:8] for c, _v in _L(pd_.get("by_platform"))] or ["—"],
                     [("spend", [v for _c, v in _L(pd_.get("by_platform"))] or [0],
                       PINK)]) if pd_.get("measured") else "",
         str(pd_.get("note", "")),
         "ad platforms", AMBER if not pd_.get("measured") else GREEN, ""),
        ("Planned paid budget", _money(pd_.get("planned_budget")), "committed",
         _hbars([(_D(c).get("name", "")[:18], _f(_D(c).get("budget")))
                 for c in planned]),
         ("What you have budgeted across paid campaigns. This is your plan, not "
          "measured spend."),
         "your campaigns", BLUE if pd_.get("planned_budget") else AMBER,
         "<button class='cta' onclick='sgaCampaign()'>Plan a paid campaign</button>"),
        ("Paid campaigns planned", _i(pd_.get("planned_count")), "with a budget",
         _split_donut([(_D(c).get("name", "")[:14], _f(_D(c).get("budget")), col)
                       for c, col in zip(planned, (PINK, VIOLET, BLUE, AMBER, TEAL))]),
         "Each one becomes a utm_campaign when its posts go out.",
         "your campaigns", BLUE, ""),
        ("Ad platform readiness", len(_needs(pd_, "needs", PAID_SCOPE_ROWS)),
         "platforms",
         _statusgrid([(lbl, False, "no scope")
                      for lbl, _sc in _needs(pd_, "needs", PAID_SCOPE_ROWS)]),
         ("Red across the board is the honest picture: no ad platform reports "
          "to this engine yet. The boards are built and waiting."),
         "read scope", AMBER, ""),
        ("Cost per result", "—", "needs platform reporting", "",
         ("CPA, ROAS and cost per click all come from the ad platform's "
          "reporting API. None is connected."),
         "ad platforms", AMBER, ""),
    ]
    cards += _slots(
        _needs(pd_, "needs", PAID_SCOPE_ROWS), 4,
        lambda i, r: (f"{r[0]} Ads", "not connected", "reporting scope", "",
                      f"Needs: {r[1]}. Until then no spend, no CPA and no ROAS "
                      f"can be shown for this platform.",
                      "read scope", AMBER,
                      "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        "Ad platform", "not applicable",
        "Only Meta, LinkedIn and TikTok have ad platforms this section covers.",
        "read scope")
    cards += _slots(
        planned, 5,
        lambda i, c: (f"Paid: {_D(c).get('name', '')[:20]}",
                      _money(_D(c).get("budget")), "planned", "",
                      (f"{_D(c).get('objective')} on "
                       f"{', '.join(_L(_D(c).get('channels'))) or 'no channel set'}, "
                       f"{_D(c).get('start')} → {_D(c).get('end') or 'open'}."),
                      "your campaigns", PINK),
        "Paid campaign", "none planned",
        "Mark a campaign as paid when you plan it and it appears here.",
        "your campaigns")
    cards += [
        ("Why this is separate from Google Ads", "different discipline",
         "by your decision", "",
         ("Search intent and social interruption are not the same buy. Google "
          "Ads has its own 296-card section; this one is social only."),
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('media')\">Open Media Buying</button>"),
        ("Organic first", "recommended", "while spend is unmeasured", "",
         ("Paying to distribute content you cannot yet measure means buying "
          "reach you cannot evaluate. Organic posting and UTM-tracked traffic "
          "cost nothing and are measured today."),
         "recommendation", VIOLET, ""),
        ("What connecting unlocks", 4, "boards go live", "",
         ("Spend, cost per result, paid/organic contribution and true ROI all "
          "become computable the moment one ad platform reports."),
         "read scope", BLUE, ""),
        ("Planned is not spent", "an important difference", "on this board", "",
         ("Every paid figure here is your own plan. Nothing on this board is a "
          "measured euro until a platform reports one."),
         "principle", AMBER, ""),
        ("Ad spend is not capped by the engine", "platform-billed", "outside it",
         "", ("Ad platforms bill you directly, so the €200 engine cap cannot "
              "restrain a campaign. Your platform budget is the only control."),
         "judgement", AMBER, ""),
        ("Where the money is measured", "BI", "unit economics", "",
         "CAC and LTV:CAC live in Business Intelligence and read recorded deals.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
    ]
    return _head("💳", "Paid social",
                 "What you plan to spend on social ads, and exactly what is "
                 "missing to measure it.") + _vizcards(cards[:20])


# ======================================================================
#  (6) AUDIENCE & TARGETING  (16)
# ======================================================================
def board_targeting(ctx) -> str:
    ctx = _ctx(ctx)
    camps, ch = ctx["campaigns"], ctx["channels"]
    ICP = ("doctors", "lawyers", "Shopify stores", "tax consultants",
           "content creators", "marketing managers")
    MARKETS = ("USA", "UK", "Germany", "Switzerland", "Canada")
    cards = [
        ("Your ICP", len(ICP), "verticals you sell to",
         _statusgrid([(v[:16], True, "") for v in ICP]),
         ("The same ICP the lead qualifier scores against. Social targeting "
          "should match it or the two channels pull apart."),
         "your ICP", VIOLET, ""),
        ("Target markets", len(MARKETS), "countries",
         _statusgrid([(m, True, "") for m in MARKETS]),
         "USA, UK, Germany, Switzerland, Canada.",
         "your ICP", VIOLET, ""),
        ("Channels available", _i(ch.get("total")), "platforms",
         _statusgrid(_L(ch.get("statusgrid"))),
         "Where you could target. Green means the posting wire is connected.",
         "wire status", BLUE, ""),
        ("Channel fit for B2B", "LinkedIn", "highest intent", "",
         ("For €2k-10k B2B projects LinkedIn carries the buying intent; "
          "Instagram and TikTok build recognition rather than pipeline."),
         "judgement", VIOLET, ""),
        ("Campaigns with channels set", sum(1 for c in camps if _L(_D(c).get("channels"))),
         f"of {len(camps)}", "",
         "A campaign without channels cannot be targeted or measured.",
         "your campaigns", AMBER if camps else BLUE, ""),
    ]
    cards += _slots(
        list(ICP), 6,
        lambda i, v: (f"ICP: {v}", "targetable", "on paid social", "",
                      ("Meta and LinkedIn can both target this by job title or "
                       "interest once an ad account is connected."),
                      "your ICP", BLUE),
        "ICP slot", "not defined", "Your ICP names six verticals.", "your ICP")
    cards += [
        ("German-language targeting", "no German content", "DE + CH", "",
         ("Two of your five markets are German-speaking and the site has no "
          "German content. Targeting them with English creative wastes the "
          "impression."),
         "site audit", PINK,
         "<button class='cta' onclick=\"nav('seo')\">Open GEO</button>"),
        ("Lookalikes and retargeting", "needs a pixel", "not installed", "",
         ("Retargeting and lookalike audiences need the Meta pixel or LinkedIn "
          "Insight Tag on the site. Neither is installed, and both change what "
          "your site sends to a third party."),
         "site", AMBER, ""),
        ("Audience size", "—", "needs platform access", "",
         "Estimated reach comes from the ad platform's planner.",
         "read scope", AMBER, ""),
        ("Where targeting is proven", "the lead list", "your real buyers", "",
         ("The verticals and countries in your actual lead list are better "
          "targeting evidence than any platform estimate."),
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('outreach')\">Open Leads &amp; Outreach</button>"),
        ("Match to outreach", "same ICP", "one definition", "",
         "Social targeting and cold outreach score against the same six "
         "verticals, so the two channels reinforce rather than diverge.",
         "your ICP", GREEN, ""),
    ]
    return _head("🎯", "Audience & targeting",
                 "Who you are aiming at, on which platform, and what is "
                 "missing to reach them.") + _vizcards(cards[:16])


# ======================================================================
#  (7) BLOG & LONG-FORM  (18)
# ======================================================================
def board_blog(ctx) -> str:
    ctx = _ctx(ctx)
    b = ctx["blog"]
    recent = _L(b.get("recent"))
    cards = [
        ("Pieces published", _i(b.get("total")), "long-form",
         _trend([("published/day", _L(b.get("series")), TEAL)]),
         ("Everything the engine published to the site." if b.get("has_data")
          else "Fills as the content agent publishes."),
         "published refs", GREEN if b.get("total") else AMBER, ""),
        ("Production cost", _money(b.get("cost")), "all pieces",
         _treemap([(_D(r).get("title", "")[:16] or "untitled", _f(_D(r).get("cost")))
                   for r in recent[:8] if _f(_D(r).get("cost"))]),
         "Size is what each piece cost to produce.",
         "job costs", BLUE, ""),
        ("Daily output", len(_L(b.get("per_day"))), "publishing days",
         _histogram([_i(v) for _d, v in _L(b.get("per_day"))]),
         ("The distribution of pieces per day. Steady output beats a burst "
          "followed by silence, for search and for social alike."),
         "published refs", BLUE if b.get("per_day") else AMBER, ""),
        ("Cost per piece", _money(b.get("per_piece")), "each", "",
         "The unit cost of long-form content.",
         "computed", GREEN if b.get("per_piece") else AMBER, ""),
        ("Cost by piece", len(recent), "most recent",
         _hbars([(_D(r).get("title", "")[:20] or "untitled", _f(_D(r).get("cost")))
                 for r in recent[:8]]),
         ("Ranked by what each one cost to produce. A piece far above the rest "
          "usually means the agent retried."),
         "job costs", BLUE if recent else AMBER, ""),
    ]
    cards += _slots(
        recent, 8,
        lambda i, r: (f"{_D(r).get('title', '')[:26] or 'untitled'}",
                      _D(r).get("at", ""), "published",
                      "", f"Cost {_money(_D(r).get('cost'))} to produce.",
                      "published refs", BLUE),
        "Piece", "not published yet",
        "The eight most recent published pieces appear here.", "published refs")
    cards += [
        ("Traffic these earn", "see SEO", "235 cards", "",
         ("This board measures production. The SEO section measures whether "
          "anyone found it."),
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('seo')\">Open SEO/AEO/GEO</button>"),
        ("UTM on shared links", "on", "when posted to social", "",
         "A blog link shared to social carries the campaign and post tags.",
         "post path", GREEN, ""),
        ("Long-form vs social", "different half-lives", "both needed", "",
         ("A blog earns search traffic that compounds for years; a post earns "
          "attention that decays in hours. The engine produces one piece and "
          "serves both."),
         "judgement", VIOLET, ""),
        ("German long-form", "none", "for DE + CH", "",
         "The widest content gap you have, and it affects social too.",
         "site audit", PINK, ""),
        ("Where it is written", "Content Factory", "briefs and drafts", "",
         "Plan and approve the next pieces there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('content')\">Open Content Factory</button>"),
    ]
    return _head("📰", "Blog & long-form",
                 "What the engine published to the site, and what it "
                 "cost.") + _vizcards(cards[:18])


# ======================================================================
#  (8) CHANNEL HEALTH  (18)
# ======================================================================
def board_channels(ctx) -> str:
    ctx = _ctx(ctx)
    ch = ctx["channels"]
    rows = _L(ch.get("rows"))
    cards = [
        ("Channels connected", _i(ch.get("connected")), f"of {_i(ch.get('total'))}",
         _statusgrid(_L(ch.get("statusgrid"))),
         "Green is a live posting wire. The label says whether anything has "
         "actually gone out.",
         "wire status", GREEN if ch.get("connected") else AMBER, ""),
        ("Channels posting", _i(ch.get("posting")), "have delivered a post", "",
         ("Connected and silent is the common failure — the wire is green and "
          "nothing is scheduled to it."),
         "computed", GREEN if ch.get("posting") else AMBER, ""),
        ("Connected but silent",
         max(0, _i(ch.get("connected")) - _i(ch.get("posting"))), "channels", "",
         "Credentials in place, no post delivered. Usually a scheduler gap.",
         "computed", AMBER, ""),
    ]
    for r in _chan_rows(ctx):
        r = _D(r)
        cards.append((r.get("label", ""),
                      ("posting" if r.get("posting") else
                       "connected" if r.get("connected") else "off"),
                      f"{_i(r.get('posts'))} posts delivered",
                      _donut(100 if r.get("posting") else 50 if r.get("connected") else 0),
                      (f"{r.get('state')}. Analytics for this channel would need: "
                       f"{r.get('read_scope')}."),
                      "wire status",
                      GREEN if r.get("posting") else AMBER if r.get("connected") else PINK,
                      "<button class='cta' onclick=\"nav('system')\">Connect</button>"))
    cards += [
        ("Every channel is post-only", 6, "no read scope anywhere", "",
         ("LinkedIn, Facebook, Instagram, YouTube, X and TikTok connectors all "
          "expose exactly one method: post(). That is why the Engagement and "
          "Audience boards are empty — not because they are unfinished."),
         "connectors", AMBER, ""),
        ("Posting failures", _i(ctx["posts"].get("failed_total")), "hit a dead wire",
         "", "A post to an unconnected channel returns a marker and is counted "
             "as a failure, never as a post.",
         "published refs", PINK if ctx["posts"].get("failed_total") else GREEN, ""),
        ("Where to connect", "System & Wiring", "all 6 channels", "",
         "Every social credential is entered in the browser, no SSH.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        ("Credential safety", "settings-first", "never in code", "",
         "Keys live in Postgres and are read settings-first, env second.",
         "engine", GREEN, ""),
        ("What green really means", "credentials present", "and accepted", "",
         ("A wire only reads green once something proved the credentials were "
          "accepted — presence alone is not enough."),
         "connectors", GREEN, ""),
        ("Next channel to add", "LinkedIn", "highest B2B intent", "",
         "If only one channel gets attention, this is the one for your ICP.",
         "judgement", VIOLET, ""),
        ("Posting is one-way", "by design today", "no read scope", "",
         ("The engine can publish to all six and read back from none. That is a "
          "connector gap, not a platform limitation — every one of them offers "
          "a free read API."),
         "connectors", AMBER, ""),
        ("Cross-posting", "avoided", "one piece, reshaped", "",
         ("The same text on every platform performs worse than a native version "
          "on each, which is why the engine repurposes rather than copies."),
         "engine", GREEN, ""),
        ("Channel of record", "your site", "not a platform", "",
         ("Everything published to social points back to a page you own. A "
          "platform can change its algorithm; your site cannot be taken away."),
         "principle", VIOLET, ""),
    ]
    return _head("🔌", "Channel health",
                 "Which platforms are wired, which are posting, and which are "
                 "silent.") + _vizcards(cards[:18])


# ======================================================================
#  (9) AUDIENCE  (18)
# ======================================================================
def board_audience(ctx) -> str:
    ctx = _ctx(ctx)
    au = ctx["audience"]
    needs = _L(au.get("needs"))
    cards = [
        ("Follower counts", ("measured" if au.get("measured") else "not available"),
         "across channels",
         _trend([(lbl, vals, TEAL) for lbl, vals in _L(au.get("series"))])
         if au.get("measured") else "",
         str(au.get("note", "")),
         "read scope", GREEN if au.get("measured") else AMBER, ""),
        ("Read scope per channel", len(_needs(au, "needs", READ_SCOPE_ROWS)),
         "none connected",
         _statusgrid([(lbl, False, "no read")
                      for lbl, _sc in _needs(au, "needs", READ_SCOPE_ROWS)]),
         ("The gap, drawn. Six channels can be posted to and none can be read "
          "from. This grid turns green one platform at a time."),
         "read scope", AMBER, ""),
        ("Post vs read capability", 6, "channels",
         _split_donut([("can post", 6, TEAL), ("can read", 0, PINK)]),
         ("Every connector is write-only. That is the single fact behind every "
          "blank card on this board."),
         "connectors", AMBER, ""),
        ("Why this is empty", "post-only connectors", "by construction", "",
         ("Every social connector in this engine exposes post() and nothing "
          "else. There is no read path for followers, so this board shows "
          "nothing rather than a number nobody measured."),
         "connectors", AMBER, ""),
        ("What would fill it", len(needs), "read scopes", "",
         "One per platform, listed below. Each is free — they are the "
         "platforms' own APIs, not a third-party tool.",
         "read scope", BLUE, ""),
    ]
    for lbl, scope in _needs(au, "needs", READ_SCOPE_ROWS):
        cards.append((f"{lbl} audience", "—", "needs a read scope", "",
                      f"Requires: {scope}.", "read scope", AMBER,
                      "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"))
    cards += [
        ("Connected but unreadable", len(_L(au.get("missing_but_connected"))),
         "channels posting blind", "",
         (f"{', '.join(_L(au.get('missing_but_connected')))} can post but cannot "
          f"report back." if au.get("missing_but_connected") else
          "No channel is in that state."),
         "computed", AMBER if au.get("missing_but_connected") else GREEN, ""),
        ("The honest alternative", "sessions and bookings", "already measured", "",
         ("Follower count is a vanity number for a business selling €2k-10k "
          "projects. Sessions per post and deals per campaign are measured "
          "today and predict revenue."),
         "judgement", VIOLET,
         "<button class='cta' onclick=\"seoTab('sgatraffic')\">Open Social → Traffic</button>"),
        ("What I will not do", "invent a number", "ever", "",
         ("The previous version of this section showed 'Follower growth' as a "
          "panel with no data behind it. An empty card that says why is more "
          "useful than a chart that means nothing."),
         "principle", VIOLET, ""),
        ("Cost of connecting", "€0", "these are free APIs", "",
         ("Every scope listed above is the platform's own API on a free tier. "
          "The cost is the OAuth app review, not money."),
         "read scope", BLUE, ""),
        ("Effort of connecting", "one app review each", "per platform", "",
         ("Meta and TikTok require an app review before granting insight "
          "scopes. LinkedIn requires a partner application. That is real work "
          "on your side, which is why these boards were built to wait."),
         "read scope", AMBER, ""),
        ("Order I would do them in", "LinkedIn first", "then Meta", "",
         ("LinkedIn carries your B2B buying intent, and its page statistics "
          "scope is the least painful of the four to obtain."),
         "judgement", VIOLET, ""),
        ("Audience you already own", "your lead list", "not rented", "",
         ("Followers live on a platform that can change the rules. Your lead "
          "list and your mailing list are yours."),
         "principle", VIOLET,
         "<button class='cta' onclick=\"nav('outreach')\">Open Leads &amp; Outreach</button>"),
    ]
    return _head("👥", "Audience",
                 "Follower counts — and the exact reason they are not "
                 "here.") + _vizcards(cards[:18])


# ======================================================================
#  (10) ENGAGEMENT  (18)
# ======================================================================
def board_engagement(ctx) -> str:
    ctx = _ctx(ctx)
    en = ctx["engagement"]
    needs = _L(en.get("needs"))
    tr = ctx["traffic"]
    cards = [
        ("Likes, comments, shares",
         ("measured" if en.get("measured") else "not available"), "per post",
         _heatmap(_L(en.get("heat_rows")), _L(en.get("heat_cols")), _L(en.get("heat"))),
         str(en.get("note", "")),
         "read scope", GREEN if en.get("measured") else AMBER, ""),
        ("Read scope per channel", len(_needs(en, "needs", READ_SCOPE_ROWS)),
         "none connected",
         _statusgrid([(lbl, False, "no read")
                      for lbl, _sc in _needs(en, "needs", READ_SCOPE_ROWS)]),
         "The gap, drawn. It turns green one platform at a time.",
         "read scope", AMBER, ""),
        ("The measure that does work", _i(tr.get("social_sessions")),
         "sessions from social",
         _donut(_f(tr.get("social_share"))),
         ("Traffic is measured today, without any platform API. It is the "
          "honest performance signal while engagement is unavailable."),
         "GA4", GREEN if tr.get("social_sessions") else AMBER, ""),
        ("Best time to post", "—", "needs engagement data", "",
         ("This needs per-post engagement timestamps from each platform. The old "
          "card promised 'learns from your post performance' with no data "
          "source at all."),
         "read scope", AMBER, ""),
        ("Top posts by engagement", "—", "needs a read scope", "",
         ("Ranked by likes and shares. What IS available is a ranking by "
          "sessions and by revenue — see Social → Traffic."),
         "read scope", AMBER,
         "<button class='cta' onclick=\"seoTab('sgatraffic')\">Rank by traffic instead</button>"),
    ]
    for lbl, scope in _needs(en, "needs", READ_SCOPE_ROWS):
        cards.append((f"{lbl} engagement", "—", "needs a read scope", "",
                      f"Requires: {scope}.", "read scope", AMBER,
                      "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"))
    cards += [
        ("Sessions per post", _n(tr.get("sessions_per_post")), "measured today",
         "", ("The engagement proxy that actually works right now, and the one "
              "that maps to revenue."),
         "GA4", GREEN if tr.get("sessions_per_post") else AMBER, ""),
        ("Social sessions", _i(tr.get("social_sessions")), "from GA4", "",
         "Real traffic that arrived from social, measured without any platform "
         "API.",
         "GA4", GREEN if tr.get("social_sessions") else AMBER, ""),
        ("Why traffic beats likes", "for your business", "€2k-10k projects", "",
         ("A like costs a recipient nothing. A visit to your site is a real "
          "signal of intent, and it is the one you can already measure."),
         "judgement", VIOLET, ""),
        ("When a scope is connected", "this board fills", "no rework", "",
         "The boards are built; only the read is missing.",
         "read scope", BLUE, ""),
        ("Comments are the real signal", "not likes", "for B2B", "",
         ("A comment costs the reader effort and starts a conversation you can "
          "answer. A like costs nothing and leads nowhere."),
         "judgement", VIOLET, ""),
        ("What the old card claimed", "learns from your post performance",
         "with no data source", "",
         ("The previous 'Best time to post' card said it learned from your "
          "performance. Nothing measured performance, so it could not learn "
          "anything."),
         "principle", AMBER, ""),
        ("Meanwhile", "post consistently", "and measure traffic", "",
         ("Cadence and sessions are both measured today. That is enough to run "
          "on until a scope is connected."),
         "judgement", GREEN,
         "<button class='cta' onclick=\"seoTab('sgaorganic')\">Open Organic Push</button>"),
    ]
    return _head("💬", "Engagement",
                 "What people did with your posts — and what is missing to "
                 "know it.") + _vizcards(cards[:18])


# ======================================================================
#  (11) SOCIAL → TRAFFIC  (20)
# ======================================================================
def board_traffic(ctx) -> str:
    ctx = _ctx(ctx)
    tr, p = ctx["traffic"], ctx["posts"]
    chans = _L(tr.get("channels"))
    cards = [
        ("Sessions from social", _i(tr.get("social_sessions")), "visits",
         _CH().sankey(_L(tr.get("flows"))),
         ("Posts through to sessions, from GA4." if tr.get("has_ga4") else
          "GA4 has not returned channel rows yet."),
         "GA4", GREEN if tr.get("social_sessions") else AMBER, ""),
        ("Social share of traffic", f"{tr.get('social_share', 0)}%", "of all sessions",
         _donut(_f(tr.get("social_share"))),
         "How much of your traffic social actually produces.",
         "GA4", BLUE, ""),
        ("Sessions per post", _n(tr.get("sessions_per_post")), "average", "",
         ("The clearest performance number available without a platform read "
          "scope."),
         "computed", GREEN if tr.get("sessions_per_post") else AMBER, ""),
        ("Posts delivered", _i(p.get("total")), "the denominator", "",
         "Only delivered posts count — failed ones are excluded.",
         "published refs", BLUE, ""),
        ("UTM tagging", "live", "on every posted link",
         _statusgrid([("utm_source", True, "channel"),
                      ("utm_medium", True, "social"),
                      ("utm_campaign", True, "campaign"),
                      ("utm_content", True, "post id")]),
         str(tr.get("note", "")),
         "post path", GREEN, ""),
        ("Channel mix", len(chans), "GA4 channel groups",
         _hbars([(c[:18], v) for c, v in chans[:8]]),
         "Where all your traffic comes from, social included.",
         "GA4", BLUE if chans else AMBER, ""),
    ]
    cards += _slots(
        chans, 6,
        lambda i, r: (f"{r[0][:22]}", f"{r[1]:.0f}", "sessions",
                      _donut(round(100 * _f(r[1]) / max(_f(tr.get("total_sessions")), 1))),
                      "Share of all sessions from this channel group.",
                      "GA4", GREEN if "social" in str(r[0]).lower() else BLUE),
        "Channel", "no sessions",
        "GA4 groups traffic into channels; this fills as they produce.", "GA4")
    cards += [
        ("Per-post attribution", "ready", "as soon as posts go out", "",
         ("GA4 reports by utm_campaign and utm_content, so each post's sessions "
          "are separable. Posts made before UTM tagging existed are not."),
         "post path", GREEN, ""),
        ("Per-campaign attribution", "ready", "utm_campaign", "",
         "Every post in a named campaign is grouped automatically.",
         "post path", GREEN, ""),
        ("What GA4 cannot tell you", "why they left", "engagement on-platform", "",
         ("GA4 sees the visit, not the scroll-past. Platform read scopes would "
          "add that half."),
         "judgement", AMBER, ""),
        ("Traffic to revenue", "next board", "the question that matters", "",
         "Sessions are only worth measuring if they end in a deal.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('sgarevenue')\">Open Social → Revenue</button>"),
        ("Compare with search", "SEO section", "235 cards", "",
         "Social versus organic search, side by side.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('seo')\">Open SEO</button>"),
        ("Total sessions", _i(tr.get("total_sessions")), "all channels", "",
         "The denominator for the share above.",
         "GA4", BLUE, ""),
        ("Posts made before UTM", "not attributable", "historic", "",
         ("Anything posted before UTM tagging existed cannot be credited "
          "retroactively — GA4 only knows what the link told it at the time."),
         "post path", AMBER, ""),
        ("Referral vs social", "GA4 decides", "by the linking domain", "",
         ("GA4 classifies a visit by where it came from. utm_medium=social "
          "keeps your own posts in the social group rather than scattering them "
          "across referral."),
         "GA4", BLUE, ""),
    ]
    return _head("📈", "Social → traffic",
                 "What social actually sent to your site, per channel and per "
                 "post.") + _vizcards(cards[:20])


# ======================================================================
#  (12) SOCIAL → REVENUE  (16)
# ======================================================================
def board_revenue(ctx) -> str:
    ctx = _ctx(ctx)
    rv, tr, p = ctx["revenue"], ctx["traffic"], ctx["posts"]
    cards = [
        ("Revenue attributed to social", _money(rv.get("revenue")), "recorded",
         _waterfall(_L(rv.get("waterfall"))),
         (f"{rv.get('share_of_revenue', 0)}% of all recorded revenue."
          if rv.get("has_data") else str(rv.get("note", ""))),
         "recorded deals", GREEN if rv.get("has_data") else AMBER,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Deals from social", _i(rv.get("deals")), "closed", "",
         ("Deals recorded with a social, organic or referral source."),
         "recorded deals", GREEN if rv.get("deals") else AMBER, ""),
        ("Revenue per post", _money(rv.get("revenue_per_post")), "delivered post",
         "", ("The number that decides whether posting is worth the time."
              if rv.get("revenue_per_post") else
              "Needs one recorded deal tagged social."),
         "computed", GREEN if rv.get("revenue_per_post") else AMBER, ""),
        ("Return on paid social",
         (f"{rv.get('roi')}%" if rv.get("roi") is not None else "—"),
         "revenue vs spend", "",
         ("Needs measured ad spend, which needs a platform reporting scope."
          if rv.get("roi") is None else "Revenue minus spend, over spend."),
         "computed", AMBER if rv.get("roi") is None else GREEN, ""),
        ("Share of all revenue", f"{rv.get('share_of_revenue', 0)}%", "from social",
         _donut(_f(rv.get("share_of_revenue"))),
         "Against every deal you have recorded.",
         "recorded deals", BLUE, ""),
        ("Clients by source", len(_L(rv.get("matrix"))), "plotted",
         _riskmatrix([(a, b, c) for a, b, c in _L(rv.get("matrix"))]),
         ("Each recorded social deal placed by value and by how it arrived. "
          "social_revenue() has always computed this; nothing drew it."
          if rv.get("matrix") else
          "Fills from the first deal you record with a social source."),
         "recorded deals", BLUE if rv.get("matrix") else AMBER, ""),
        ("The full path", 3, "post → session → deal",
         _CH().sankey(_L(tr.get("flows"))),
         "Each step measured: delivered posts, GA4 sessions, recorded deals.",
         "computed", BLUE, ""),
    ]
    cards += _slots(
        _L(rv.get("matrix")), 4,
        lambda i, r: (f"Client: {r[0]}", "from social", "recorded deal", "",
                      "Tagged social, organic or referral at deal entry.",
                      "recorded deals", GREEN),
        "Social deal", "none recorded",
        ("Tag the source when you record a won deal and it appears here."),
        "recorded deals", AMBER)
    cards += [
        ("Attribution honesty", "self-reported", "by you at deal entry", "",
         ("Source is what you tagged when recording the deal. That is a "
          "judgement, not a tracked path — but it is the only attribution that "
          "survives a phone call and a referral."),
         "principle", VIOLET, ""),
        ("Better attribution", "UTM + GA4 conversions", "when a form exists", "",
         ("A booking form with GA4 conversion tracking would close the loop "
          "from post to booking without you tagging anything."),
         "judgement", AMBER, ""),
        ("Cost side", "BI", "CAC and LTV:CAC", "",
         "The economics live in Business Intelligence.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
        ("Compare with outreach", "Leads & Outreach", "240 cards", "",
         "Cold email against social, on the same revenue basis.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('outreach')\">Open Leads &amp; Outreach</button>"),
        ("Sessions that produced it", _i(tr.get("social_sessions")), "social visits",
         "", "The traffic half of the equation.",
         "GA4", BLUE, ""),
    ]
    return _head("💶", "Social → revenue",
                 "Whether any of this produced money.") + _vizcards(cards[:16])


# ======================================================================
#  (13) BUDGET & PACING  (16)
# ======================================================================
def board_budget(ctx) -> str:
    ctx = _ctx(ctx)
    bg, pd_, b = ctx["budget"], ctx["paid"], ctx["blog"]
    cards = [
        ("Paid vs organic", _money(bg.get("committed")), "committed",
         _split_donut([("paid (planned)", _f(bg.get("planned_paid")), PINK),
                       ("organic (content)", _f(bg.get("organic_cost")), TEAL)]),
         str(bg.get("note", "")),
         "computed", BLUE if bg.get("has_data") else AMBER, ""),
        ("Planned paid budget", _money(bg.get("planned_paid")), "your commitment",
         "", "From the campaigns you marked paid.",
         "your campaigns", BLUE, ""),
        ("Measured paid spend",
         _money(bg.get("actual_paid") if pd_.get("measured") else None), "actual",
         "", ("Needs an ad platform reporting scope." if not pd_.get("measured")
              else "Read from the ad platforms."),
         "ad platforms", AMBER if not pd_.get("measured") else GREEN, ""),
        ("Organic content cost", _money(bg.get("organic_cost")), "to produce",
         "", "What the engine actually spent generating what you posted.",
         "job costs", GREEN if bg.get("organic_cost") else AMBER, ""),
        ("Engine spend this month", _money(bg.get("engine_spend")),
         f"of {_money(bg.get('cap'))}",
         _score_gauge(_f(bg.get("pct_of_cap")), 85),
         ("The €200 cap governs LLM spend, not ad spend — ads are billed by the "
          "platform, outside the engine."),
         "API meters", _pct_color(_f(bg.get("pct_of_cap")), 85), ""),
        ("Paid share of commitment", f"{bg.get('paid_share', 0)}%", "of the total",
         _donut(_f(bg.get("paid_share"))),
         "How much of your growth budget is rented versus owned.",
         "computed", BLUE, ""),
        ("Cost per delivered post",
         (_money(_f(bg.get("organic_cost")) / max(_i(ctx["posts"].get("total")), 1))
          if ctx["posts"].get("total") else "—"), "organic", "",
         "Content cost divided by posts that actually landed.",
         "computed", GREEN if ctx["posts"].get("total") else AMBER, ""),
        ("Cost per blog piece", _money(b.get("per_piece")), "long-form", "",
         "Long-form costs more per piece and lasts far longer.",
         "computed", BLUE, ""),
    ]
    cards += [
        ("Daily content spend", _money(_D(ctx.get("cost_series")).get("avg")),
         "average per active day",
         _CH().confband(_L(_D(ctx.get("cost_series")).get("values")), band=0.3)
         if _D(ctx.get("cost_series")).get("ready") else "",
         _D(ctx.get("cost_series")).get("note", ""),
         "job costs",
         GREEN if _D(ctx.get("cost_series")).get("ready") else AMBER, ""),
        ("Pacing", ("inside the cap" if _f(bg.get("pct_of_cap")) < 85
                    else "close to the cap"), "engine spend", "",
         "The engine halts new LLM steps at the cap rather than overspending.",
         "computed", GREEN if _f(bg.get("pct_of_cap")) < 85 else PINK, ""),
        ("No guardrail on ad spend", "platform-billed", "outside the engine", "",
         ("Ad platforms bill you directly. Nothing in this engine can stop an "
          "ad campaign overspending — only your platform budget can."),
         "judgement", AMBER, ""),
        ("Budget by campaign", len(ctx["campaigns"]), "planned",
         _hbars([(_D(c).get("name", "")[:18], _f(_D(c).get("budget")))
                 for c in ctx["campaigns"] if _f(_D(c).get("budget"))]),
         "Where the planned spend is allocated.",
         "your campaigns", BLUE, ""),
        ("Organic is free to distribute", "yes", "not free to make", "",
         ("Organic posting costs no media spend, but the content still costs "
          "engine budget to produce. That is the number above."),
         "principle", VIOLET, ""),
        ("Where the economics live", "BI", "CAC, LTV, payback", "",
         "Business Intelligence turns these costs into unit economics.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
        ("Google Ads budget", "Media Buying", "separate section", "",
         "Search spend is tracked there, not here.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('media')\">Open Media Buying</button>"),
        ("Change the cap", "System & Wiring", "engine settings", "",
         "The monthly and daily caps are set there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
    ]
    return _head("💰", "Budget & pacing",
                 "What social costs you — paid, organic and engine.") + _vizcards(cards[:16])


# ======================================================================
#  (14) GOOGLE HUB  (18)
# ======================================================================
def board_hub(ctx) -> str:
    ctx = _ctx(ctx)
    h = ctx["hub"]
    cards = [
        ("Google Sheets", ("connected" if h.get("sheets_connected") else "off"),
         "the data hub",
         _split_donut([(n, v, c) for (n, v), c in
                       zip(_L(h.get("ring")), (TEAL, VIOLET))]),
         str(h.get("note", "")),
         "wire status", GREEN if h.get("sheets_connected") else AMBER, ""),
        ("Rows in Sheets",
         (_i(h.get("sheets_rows")) if h.get("sheets_verified") else "—"),
         "confirmed by Google", "",
         ("Read back from the Sheet." if h.get("sheets_verified") else
          "The old card printed a local job count and labelled it '≈ rows "
          "mirrored'. That was this engine's number, not Google's, and it "
          "stayed confident even with the wire down."),
         "Google Sheets", GREEN if h.get("sheets_verified") else AMBER, ""),
        ("Files in Drive",
         (_i(h.get("drive_files")) if h.get("drive_verified") else "—"),
         "confirmed by Google", "",
         ("Read back from the folder." if h.get("drive_verified") else
          "Same as above — the old figure was the local published count."),
         "Google Drive", GREEN if h.get("drive_verified") else AMBER, ""),
        ("Local job rows", _i(h.get("local_jobs")), "in this engine", "",
         ("What the engine holds and would mirror. Labelled as local, because "
          "that is what it is."),
         "job store", BLUE, ""),
        ("Emails sent", _i(h.get("emails_sent")), "through Gmail", "",
         "Counted from the engine's own send stamps.",
         "send stamps", BLUE, ""),
        ("Google Drive", ("connected" if h.get("drive_connected") else "off"),
         "content store", "",
         "Each finished piece is saved as a file.",
         "wire status", GREEN if h.get("drive_connected") else AMBER, ""),
        ("Gmail (Workspace)", ("connected" if h.get("gmail_connected") else "off"),
         "send and read", "",
         "mother@ with contact@, marketing@, newsletter@ and customercare@ "
         "aliases.",
         "wire status", GREEN if h.get("gmail_connected") else AMBER, ""),
        ("Last verified read", (h.get("last_read") or "never")[:16].replace("T", " "),
         "counts from Google", "",
         ("A verified count is only written by a real read, so it can never be "
          "faked."),
         "Google hub", GREEN if h.get("last_read") else AMBER, ""),
    ]
    cards += [
        ("Why the counts are local", "Sheets and Drive are write-only", "here",
         "", ("The connectors expose append_row() and save_json() and nothing "
              "that reads. Adding a read is small — it just has not been done, "
              "and until it is, this board says so."),
         "connectors", AMBER, ""),
        ("What a real read unlocks", 3, "verified cards", "",
         "Row count, file count and storage used all become facts rather than "
         "estimates.",
         "connectors", BLUE, ""),
        ("Hub as a dashboard", "Sheets", "your own view", "",
         ("The Sheet is the human-readable mirror — open it and see every job "
          "as a row without this dashboard."),
         "Google Sheets", VIOLET, ""),
        ("Hub as a store", "Drive", "content library", "",
         "Every finished piece is a file you own, outside this engine.",
         "Google Drive", VIOLET, ""),
        ("Backup implication", "Drive is not a backup", "of Postgres", "",
         ("Content files in Drive are not a database backup. The engine's jobs, "
          "credentials and history live only in Postgres."),
         "risk register", PINK,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
        ("Wire diagnostics", "System & Wiring", "all three wires", "",
         "Connect or repair Sheets, Drive and Gmail there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        ("Service account", "one key", "Sheets, Drive, GSC and GA4", "",
         ("A single Google service-account key backs all four. If it is "
          "rejected, all four go down together."),
         "connectors", AMBER, ""),
        ("Quota", "generous", "for this volume", "",
         "Sheets and Drive API quotas are far above what this engine uses.",
         "Google hub", GREEN, ""),
        ("Where email quota is tracked", "Leads & Outreach", "warmup cap", "",
         "The daily send ceiling lives on the Deliverability board.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('outreach')\">Open Leads &amp; Outreach</button>"),
        ("Data ownership", "yours", "outside the engine", "",
         "Sheets and Drive mean your content and job history survive this "
         "engine entirely.",
         "principle", GREEN, ""),
    ]
    return _head("☁️", "Google hub",
                 "Sheets, Drive and Gmail — and which numbers Google actually "
                 "confirmed.") + _vizcards(cards[:18])


# ======================================================================
#  SECTION
# ======================================================================
TABS = [
    ("sgacmd", "🚀", "SGA Command"),
    ("sgaplan", "🗓", "Campaign Planner"),
    ("sgacreative", "🎨", "Creative Library"),
    ("sgaorganic", "📤", "Organic Push"),
    ("sgapaid", "💳", "Paid Social"),
    ("sgatarget", "🎯", "Audience Targeting"),
    ("sgablog", "📰", "Blog & Long-form"),
    ("sgachannels", "🔌", "Channel Health"),
    ("sgaaudience", "👥", "Audience"),
    ("sgaengage", "💬", "Engagement"),
    ("sgatraffic", "📈", "Social → Traffic"),
    ("sgarevenue", "💶", "Social → Revenue"),
    ("sgabudget", "💰", "Budget & Pacing"),
    ("sgahub", "☁️", "Google Hub"),
]

GROUPS = [
    ("sgaplanit", "① PLAN IT", "What are we running?",
     ["sgacmd", "sgaplan", "sgacreative", "sgatarget"]),
    ("sgapush", "② PUSH IT", "What went out?",
     ["sgaorganic", "sgapaid", "sgablog"]),
    ("sgaland", "③ DID IT LAND", "Did anyone see it?",
     ["sgachannels", "sgaaudience", "sgaengage", "sgatraffic"]),
    ("sgapay", "④ DID IT PAY", "Was it worth it?",
     ["sgarevenue", "sgabudget", "sgahub"]),
]

_TAB_BOARDS = {
    "sgacmd": [("SGA Command", board_command)],
    "sgaplan": [("Campaign Planner", board_planner)],
    "sgacreative": [("Creative Library", board_creative)],
    "sgaorganic": [("Organic Push", board_organic)],
    "sgapaid": [("Paid Social", board_paid)],
    "sgatarget": [("Audience Targeting", board_targeting)],
    "sgablog": [("Blog Push", board_blog)],
    "sgachannels": [("Channel Health", board_channels)],
    "sgaaudience": [("Audience", board_audience)],
    "sgaengage": [("Engagement", board_engagement)],
    "sgatraffic": [("Social Traffic", board_traffic)],
    "sgarevenue": [("Social Revenue", board_revenue)],
    "sgabudget": [("Budget & Pacing", board_budget)],
    "sgahub": [("Google Hub", board_hub)],
}

_TAB_COUNTS = {"sgacmd": 16, "sgaplan": 20, "sgacreative": 16, "sgaorganic": 20,
               "sgapaid": 20, "sgatarget": 16, "sgablog": 18, "sgachannels": 18,
               "sgaaudience": 18, "sgaengage": 18, "sgatraffic": 20,
               "sgarevenue": 16, "sgabudget": 16, "sgahub": 18}
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


def sga_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def sga_section(ctx) -> str:
    H = _H()
    ctx = _ctx(ctx)
    panels = sga_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'sgaplanit')}' onclick=\"seoTab('{tid}')\">"
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
              "<button class='cbtn' onclick='sgaCampaign()'>🗓 Plan a campaign</button>"
              "<button class='cbtn' onclick=\"act('/insights/refresh')\">🔄 Refresh GA4</button>"
              "<button class='cbtn' onclick=\"nav('media')\">🛒 Google Ads is over here</button>"
              "</div>")
    return (_TAB_CSS
            + "<div class='sgroups'>" + grouprail + "</div>"
            + runbar
            + "<div class='stabs'>" + bar + "</div>"
            + "<div class='spanels'>" + body + "</div>")


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_sga as SGA

    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()
    SGA.save_campaign(st, "Q3 Launch", "leads", ["linkedin", "instagram"],
                      "2026-07-28", "2026-08-10", 400, paid=True)
    SGA.save_campaign(st, "Always On", "awareness", ["linkedin"], "2026-07-01")
    camps = SGA.list_campaigns(st)
    jobs = [
        {"job_id": "social_linkedin_0", "type": "content_piece",
         "created_at": "2026-07-30T09:00:00Z", "cost_so_far_usd": 0.2,
         "payload": {"published_refs": {"linkedin": "urn:li:share:1"},
                     "content_producer": {"title": "T", "image_url": "i.png"}}},
        {"job_id": "social_instagram_0", "type": "content_piece",
         "created_at": "2026-07-30T10:00:00Z",
         "payload": {"published_refs": {"instagram": "ig_1"},
                     "content_producer": {"video_url": "v.mp4"}}},
        {"job_id": "social_tiktok_0", "type": "content_piece",
         "created_at": "2026-07-30T11:00:00Z",
         "payload": {"published_refs": {"tiktok": "tiktok_not_configured:x"},
                     "content_producer": {}}},
        {"job_id": "blog_1", "type": "content_piece",
         "created_at": "2026-07-29T09:00:00Z", "cost_so_far_usd": 0.6,
         "payload": {"published_refs": {"wordpress": "post_9"},
                     "content_producer": {"title": "A blog"}}},
    ]
    status = {"social_linkedin": True, "social_instagram": True,
              "google_sheets": True, "google_drive": True, "email_send": True}
    ins = {"ga4": {"channels": [{"sessionDefaultChannelGroup": "Organic Social",
                                 "sessions": 120},
                                {"sessionDefaultChannelGroup": "Organic Search",
                                 "sessions": 400}]}}
    p = SGA.posts(jobs)
    bl = SGA.blog_push(jobs)
    pd_ = SGA.paid_social(st, camps)
    ctx = {
        "campaigns": camps, "calendar": SGA.calendar(camps),
        "posts": p, "cadence": SGA.cadence(p, 1, ["linkedin", "instagram"]),
        "creatives": SGA.creatives(jobs), "blog": bl,
        "channels": SGA.channel_health(status, p),
        "audience": SGA.audience(st, status), "engagement": SGA.engagement(st),
        "paid": pd_, "traffic": SGA.social_traffic(ins, p, camps),
        "revenue": SGA.social_revenue([{"client": "A", "value": 3000,
                                        "source": "social"}], p, pd_),
        "budget": SGA.budget(camps, pd_, 41.7, 200.0, bl),
        "hub": SGA.google_hub(st, status, jobs, emails_sent=12),
        "cost_series": SGA.cost_series(jobs),
    }

    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        _CURRENT_BOARD["name"] = name
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = sga_pages(ctx)
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

    # the three empty-by-construction boards must name their scope, never fake
    for tab in ("sgaaudience", "sgaengage"):
        assert "read scope" in pages[tab], f"{tab} must name what would fill it"
    assert "r_organization_social" in pages["sgaaudience"]
    assert "read_insights" in pages["sgaaudience"] or "Graph API" in pages["sgaaudience"]
    assert "Marketing API" in pages["sgapaid"], "paid must name the ad scope"
    for word in ("Stripe", "HubSpot", "Hootsuite", "Buffer", "Sprout"):
        assert word not in html, f"no card may point at a vendor: {word}"

    # the Google Ads boundary the brief set
    assert "Media Buying" in pages["sgacmd"], "say where Google Ads lives"
    assert "deliberately NOT here" in pages["sgapaid"] or \
        "different discipline" in pages["sgapaid"]

    # the old misleading hub number must be called out, not repeated
    assert "local job count" in pages["sgahub"] or "local" in pages["sgahub"]
    assert "UTM" in pages["sgatraffic"] and "utm_content" in pages["sgatraffic"]

    empty = sga_pages({})
    ehtml = "".join(empty.values())
    assert "failed to render" not in ehtml
    assert len(re.findall(r"<div class='card (?:overflowcard )?sev-", ehtml)) == TOTAL_CARDS

    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {k: 0 for k in ctx}, {"campaigns": "no"}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    charts = len(re.findall(r"<svg", html))
    print(f"sga_boards self-check OK — {len(_TAB_BOARDS)} boards, {counted} cards, "
          f"{len(set(ids))} unique ids, {charts} charts; audience, engagement and "
          f"paid spend stay empty with the exact API scope named, no card points "
          f"at a vendor, and Google Ads is left in its own section.")
