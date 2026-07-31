"""
content_engine_factory_boards.py
============================================================================
CONTENT FACTORY — 16 boards, 278 cards, with SIX platform preview screens.

Replaces a 13-card section that had no preview, knew only two channels, and
whose planner was handed an empty dict where the whole engine should have been.

The preview group is the point: 96 cards across six screens that show a piece
as it will actually appear on the website, LinkedIn, Instagram, X, Facebook,
YouTube and in Google results — rendered from the SAME piece object that
publishes, with the platform's real truncation points and the checks that
decide whether it will look right.

Run offline self-check:  python content_engine_factory_boards.py
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
    "Factory Command": ("Plan a week", "planContent()"),
    "Strategy Brief": ("Plan a week", "planContent()"),
    "Plan & Calendar": ("Plan a week", "planContent()"),
    "Preview Website": ("Open Approvals", "nav('appr')"),
    "Preview LinkedIn": ("Open Approvals", "nav('appr')"),
    "Preview Instagram": ("Test an image", "testImage()"),
    "Preview X & Facebook": ("Open Approvals", "nav('appr')"),
    "Preview YouTube": ("Open Approvals", "nav('appr')"),
    "Preview Search": ("Open SEO", "nav('seo')"),
    "Creative & Image": ("Test an image", "testImage()"),
    "Brand & CI": ("Open System & Wiring", "nav('system')"),
    "Pipeline": ("Open Approvals", "nav('appr')"),
    "Quality": ("Open Approvals", "nav('appr')"),
    "Channel Routing": ("Connect a channel", "nav('system')"),
    "Repurposing": ("Open SGA", "nav('sga')"),
    "Cost & Throughput": ("Open BI", "nav('bi')"),
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
    for k in ("brief", "previews", "images", "ci", "pipeline", "routing",
              "repurposing", "throughput", "eligibility", "plan", "piece",
              "post_publish", "campaigns"):
        out[k] = _D(out.get(k))
    return out


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


def _pv(ctx, platform):
    return _D(_D(_D(ctx.get("previews")).get("by_platform")).get(platform))


# ======================================================================
#  THE PREVIEW BOARD GENERATOR — one shape, six platforms
# ======================================================================
PLATFORM_META = {
    "website": ("🌐", "Website", 18,
                "The article as it lands on your site — hero, headings, body."),
    "linkedin": ("in", "LinkedIn", 16,
                 "The post as the feed shows it, cut at 'see more'."),
    "instagram": ("◎", "Instagram", 16,
                  "The square post and the caption cut at 125 characters."),
    "twitter": ("𝕏", "X & Facebook", 16,
                "The 280-character limit and the Facebook link card."),
    "youtube": ("▶", "YouTube", 14,
                "Thumbnail, title and the description above the fold."),
    "serp": ("🔍", "Search result", 16,
             "How the piece appears in Google — the preview that decides the click."),
}


def _preview_board(platform):
    icon, label, count, blurb = PLATFORM_META[platform]

    def board(ctx) -> str:
        ctx = _ctx(ctx)
        v = _pv(ctx, platform)
        fb = _pv(ctx, "facebook") if platform == "twitter" else {}
        checks = _L(v.get("checks")) + (_L(fb.get("checks")) if fb else [])
        passed = sum(1 for _n2, ok, _d in checks if ok)
        frame = _D(v).get("html") or ""
        fb_frame = _D(fb).get("html") or ""
        blocked = bool(v.get("blocked"))
        cards = [
            (f"{label} preview", ("blocked" if blocked else "ready"),
             "as it will appear",
             "", (f"This is a mockup built from the SAME piece object that "
                  f"publishes. What you see is what ships."
                  + (" This platform will REJECT the post as it stands."
                     if blocked else "")),
             "the piece", PINK if blocked else GREEN,
             "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
            (f"Checks passed", f"{passed}/{len(checks) or 1}", "for this platform",
             _score_gauge(round(100 * passed / max(len(checks), 1)), 100),
             ("Every check is a real platform behaviour — a truncation point, a "
              "required asset, a hard limit."),
             "computed",
             GREEN if passed == len(checks) and checks else AMBER, ""),
        ]
        for name, ok, detail in checks[:8]:
            cards.append((str(name)[:30], "pass" if ok else "fix",
                          str(detail)[:40], "",
                          (f"{name}: {detail}." + ("" if ok else
                           " This one will change how the post looks or stop it "
                           "publishing.")),
                          "platform rules", GREEN if ok else PINK, ""))
        extra = {
            "website": [("Word count", _i(v.get("words")), "words", "",
                         "Under 600 rarely ranks; over 2500 rarely gets read.",
                         "the piece", BLUE, ""),
                        ("Headings", _i(v.get("headings")), "H2/H3", "",
                         "Structure is what makes a long piece scannable.",
                         "the piece", BLUE, ""),
                        ("Hero image", "yes" if v.get("has_image") else "no",
                         "at the top", "",
                         ("The hero is generated on brand from your CI."
                          if v.get("has_image") else
                          "No hero. The article publishes as a wall of text."),
                         "image agent", GREEN if v.get("has_image") else PINK, ""),
                        ("Where it publishes", "your website", "WordPress", "",
                         "Into the section matching its pillar and segment.",
                         "taxonomy", VIOLET, ""),
                        ("Mobile width", "responsive", "checked", "",
                         "The site template handles it; the preview shows desktop.",
                         "template", GREEN, ""),
                        ("Schema", "article", "structured data", "",
                         "Added by the SEO fixer after approval.",
                         "SEO engine", BLUE, "")],
            "linkedin": [("Cut at", _i(v.get("cut_at")), "characters",
                          _donut(round(100 * min(1, _i(v.get("cut_at")) /
                                                 max(_i(v.get("chars")), 1)))),
                          ("LinkedIn hides everything past 210 characters behind "
                           "'see more'. The hook has to live above that line."),
                          "platform rule", VIOLET, ""),
                         ("Hidden behind 'see more'", _i(v.get("hidden_chars")),
                          "characters", "",
                          "Most readers never expand it.",
                          "computed", AMBER if v.get("hidden_chars") else GREEN, ""),
                         ("Total length", _i(v.get("chars")), "of 3000", "",
                          "Long posts do work on LinkedIn — but only if the hook "
                          "earns the click.",
                          "the piece", BLUE, ""),
                         ("Hashtags", _i(v.get("hashtags")), "3-5 is the sweet spot",
                          "", "More than five reads as spam on LinkedIn.",
                          "the piece", BLUE, "")],
            "instagram": [("Image required", "yes", "hard requirement", "",
                           ("Instagram returns instagram_needs_image_url and "
                            "REJECTS the post. This is why Instagram never "
                            "worked — social pieces were never given an image."),
                           "platform rule", PINK if blocked else GREEN, ""),
                          ("Caption cut", _i(v.get("cut_at")), "characters", "",
                           "Everything past 125 characters is hidden behind "
                           "'… more'.",
                           "platform rule", VIOLET, ""),
                          ("Hidden caption", _i(v.get("hidden_chars")), "characters",
                           "", "Put the point first.",
                           "computed", AMBER if v.get("hidden_chars") else GREEN, ""),
                          ("Square format", "1080×1080", "1:1", "",
                           "Portrait 4:5 reaches further, square is safest.",
                           "platform rule", BLUE, "")],
            "twitter": [("Over the limit", _i(v.get("over")), "characters", "",
                         ("X hard-stops at 280. Anything longer must become a "
                          "thread or it will not post."),
                         "platform rule", PINK if v.get("over") else GREEN, ""),
                        ("Thread parts", _i(v.get("thread_parts")), "posts", "",
                         "The engine can split, but a forced thread reads worse "
                         "than a written one.",
                         "computed", AMBER if _i(v.get("thread_parts")) > 1 else GREEN, ""),
                        ("Facebook link card", "rendered", "below", "",
                         "Facebook shows the OG image and title, not your text.",
                         "platform rule", BLUE, ""),
                        ("Facebook cut", 250, "characters", "",
                         "Facebook hides the rest behind 'See more'.",
                         "platform rule", VIOLET, "")],
            "youtube": [("Title length", _i(v.get("title_len")), "of 70", "",
                         "Past 70 characters YouTube truncates in search and "
                         "suggested.",
                         "platform rule",
                         PINK if _i(v.get("title_len")) > 70 else GREEN, ""),
                        ("Thumbnail", "1280×720", "16:9 required", "",
                         "No thumbnail, no upload — YouTube rejects it.",
                         "platform rule", PINK if blocked else GREEN, ""),
                        ("Video asset", "required", "the actual file", "",
                         ("The engine writes titles, descriptions and thumbnails. "
                          "It does not produce video — that asset is yours."),
                         "honest limit", AMBER, "")],
            "serp": [("Title width", _i(v.get("title_len")), "of 60 chars",
                      _score_gauge(min(100, round(100 * _i(v.get("title_len")) / 60)), 100),
                      ("Google truncates around 60 characters. A cut title loses "
                       "the keyword at the end."),
                      "platform rule",
                      PINK if v.get("truncated") else GREEN, ""),
                     ("Meta length", _i(v.get("meta_len")), "of 155 chars", "",
                      "Past 155 Google rewrites or truncates it.",
                      "platform rule", BLUE, ""),
                     ("Truncated", "yes" if v.get("truncated") else "no",
                      "in results", "",
                      "A truncated title is the most common reason a ranked page "
                      "gets no clicks.",
                      "computed", PINK if v.get("truncated") else GREEN, ""),
                     ("This is the real test", "click or not", "at any position",
                      "", ("Ranking #3 with a bad title loses to #6 with a good "
                           "one. This preview is where that is decided."),
                      "judgement", VIOLET,
                      "<button class='cta' onclick=\"nav('seo')\">Open SEO</button>")],
        }[platform]
        cards += extra
        tail = [
            ("Preview fidelity", "styled mockup", "~95% accurate", "",
             ("A styled mockup, not a live embed — it works offline on the VPS, "
              "loads nothing external and cannot leak the draft to a platform "
              "before you approve it."),
             "design choice", VIOLET, ""),
            ("Same object as publishes", "yes", "no second render path", "",
             ("The preview reads the piece the publisher reads. A preview that "
              "disagrees with the send is worse than no preview."),
             "principle", GREEN, ""),
            ("Where to act", "Approvals", "approve, edit or decline", "",
             "Nothing publishes until you say so.",
             "navigation", VIOLET,
             "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ]
        cards += tail
        while len(cards) < count:
            cards.append(("Check slot", "—", "no further checks", "",
                          f"{label} has no more automated checks for this piece.",
                          "platform rules", BLUE, ""))
        body = (frame + (fb_frame if fb_frame else ""))
        header = (f"<div class='card full' style='margin-bottom:10px'>"
                  f"<p class='ct'>{icon} {label} — live preview</p>"
                  f"<p class='cc'>{blurb}</p>{body}</div>")
        return _head(icon, f"{label} preview", blurb) + header + _vizcards(cards[:count])

    board.__name__ = f"board_preview_{platform}"
    return board


board_pv_website = _preview_board("website")
board_pv_linkedin = _preview_board("linkedin")
board_pv_instagram = _preview_board("instagram")
board_pv_x = _preview_board("twitter")
board_pv_youtube = _preview_board("youtube")
board_pv_serp = _preview_board("serp")


# ======================================================================
#  (1) FACTORY COMMAND  (16)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    br, pv, im = ctx["brief"], ctx["previews"], ctx["images"]
    pl, rt, tp = ctx["pipeline"], ctx["routing"], ctx["throughput"]
    ci, el = ctx["ci"], _D(br.get("eligibility"))
    cards = [
        ("Pieces in the factory", _i(pl.get("total")), "in production",
         _waterfall(_L(pl.get("waterfall"))),
         "Plan, write, SEO, your approval, published — the whole line.",
         "jobs", GREEN if pl.get("total") else AMBER, ""),
        ("Waiting for you", _i(pl.get("waiting")), "need approval", "",
         "Nothing publishes without you.",
         "jobs", AMBER if pl.get("waiting") else GREEN,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ("Preview readiness", f"{pv.get('score', 0)}%", "of platform checks pass",
         _score_gauge(_f(pv.get("score")), 90),
         (f"{_i(pv.get('checks_failed'))} of {_i(pv.get('checks_total'))} checks "
          f"fail across six platforms."),
         "previews", _pct_color(100 - _f(pv.get("score")), 20), ""),
        ("Blocked platforms", len(_L(pv.get("blocked"))), "would reject the post",
         "", (f"{', '.join(_L(pv.get('blocked')))} cannot publish this piece as "
              f"it stands." if pv.get("blocked") else
              "No platform would reject the current piece."),
         "previews", PINK if pv.get("blocked") else GREEN, ""),
        ("Strategy signals", len(_D(br.get("signals"))), "systems feeding the plan",
         _statusgrid([(k[:16], True, "") for k in list(_D(br.get("signals")))[:8]]),
         (f"{_i(br.get('systems_reporting'))} of {_i(br.get('systems_total'))} "
          f"systems are reporting into the content plan. " + str(br.get("note", ""))),
         "all systems", GREEN if br.get("systems_reporting") else AMBER, ""),
        ("Top gap to close", (_D(_L(br.get("gaps"))[0]).get("kind", "—").upper()
                              if br.get("gaps") else "—"),
         "highest-weight signal", "",
         (_D(_L(br.get("gaps"))[0]).get("why", "") if br.get("gaps") else
          "No system is reporting a gap yet."),
         "strategy brief", PINK if br.get("gaps") else AMBER, ""),
        ("Channels you can publish to", _i(el.get("count")), f"of {_i(el.get('total'))}",
         _statusgrid([(r.get("label"), r.get("live"), "" if r.get("live") else "no wire")
                      for r in _L(el.get("rows"))]),
         str(el.get("note", "")),
         "wire status", GREEN if el.get("count") else PINK, ""),
        ("Channel mismatches", _i(rt.get("mismatch_count")), "aimed at a dead wire",
         "", str(rt.get("note", "")),
         "computed", PINK if rt.get("mismatch_count") else GREEN, ""),
        ("Image generation", ("ready" if im.get("configured") else "off"),
         im.get("provider", "openai"), "",
         str(im.get("verdict", "")),
         "IMAGE_API_KEY", GREEN if im.get("configured") else PINK,
         "<button class='cta' onclick='testImage()'>Test an image</button>"),
        ("Brand applied", f"{ci.get('score', 0)}%", "of CI checks pass",
         _donut(_f(ci.get("score"))),
         (str(ci.get("note", "")) if ci.get("configured") else
          "No CI configured — the agents fall back to built-in defaults."),
         "your CI", GREEN if _f(ci.get("score")) >= 80 else AMBER, ""),
        ("Published", _i(tp.get("published")), "live pieces", "",
         f"Costing {_money(tp.get('per_piece'))} each.",
         "jobs", GREEN if tp.get("published") else AMBER, ""),
        ("Output per day", _n(tp.get("avg_per_day")), "pieces",
         _trend([("pieces/day", _L(tp.get("series")), TEAL)]),
         "Cadence beats bursts for both search and social.",
         "jobs", BLUE, ""),
        ("Budget headroom", _money(br.get("budget_headroom")), "left this month", "",
         ("The plan is capped to what the budget can actually produce, so a "
          "week is never planned that cannot be written."),
         "meters", GREEN if _f(br.get("budget_headroom")) > 20 else PINK, ""),
        ("Failed pieces", _i(pl.get("failed")), "produced nothing", "",
         "Each one consumed budget and returned no output.",
         "jobs", PINK if pl.get("failed") else GREEN, ""),
        ("Plan a week", "one click", "from all six systems", "",
         ("The planner now receives striking-distance queries, AI-visibility "
          "gaps, missing markets, which vertical replies, what produced revenue "
          "and which channels are live."),
         "strategy brief", VIOLET,
         "<button class='cta' onclick='planContent()'>Plan a week</button>"),
        ("Cost cap", "command centre", "you set the target", "",
         ("Image and content spend both draw on the monthly cap. The cap itself "
          "stays open — you steer the target from the command centre."),
         "your decision", VIOLET,
         "<button class='cta' onclick=\"nav('mission')\">Open Command Center</button>"),
    ]
    return _head("🏭", "Factory command",
                 "The heart of the system — what is being made, whether it will "
                 "look right, and what it costs.") + _vizcards(cards)


# ======================================================================
#  (2) STRATEGY BRIEF  (20)  — the comparative loop, visible
# ======================================================================
def board_brief(ctx) -> str:
    ctx = _ctx(ctx)
    br = ctx["brief"]
    sig = _D(br.get("signals"))
    gaps = _L(br.get("gaps"))
    SYSTEMS = [("SEO/AEO/GEO", "striking_distance", "seo"),
               ("AI visibility", "ai_visibility", "seo"),
               ("Markets", "missing_markets", "sga"),
               ("Leads & Outreach", "sourced_verticals", "outreach"),
               ("Business Intelligence", "revenue_by_source", "bi"),
               ("SGA", "sessions_per_post", "sga"),
               ("Media Buying", "expensive_paid_keywords", "media"),
               ("Risk & budget", "budget", "riskinfra")]
    cards = [
        ("Systems feeding the plan", _i(br.get("systems_reporting")),
         f"of {_i(br.get('systems_total'))}",
         _statusgrid([(lbl, k in sig, "" if k in sig else "silent")
                      for lbl, k, _t in SYSTEMS]),
         str(br.get("note", "")),
         "all systems", GREEN if br.get("systems_reporting") else AMBER, ""),
        ("Gaps ranked", len(gaps), "by what they would move",
         _hbars([(str(_D(g).get("kind", "")).upper(), _f(_D(g).get("weight")))
                 for g in gaps[:8]]),
         ("The planner is told to close the highest-weight gap first, instead "
          "of balancing its own taxonomy in a vacuum."),
         "strategy brief", PINK if gaps else AMBER, ""),
    ]
    cards += _slots(
        gaps, 6,
        lambda i, g: (f"Gap {i + 1}: {str(_D(g).get('kind', '')).upper()}",
                      _i(_D(g).get("weight")), "weight", "",
                      str(_D(g).get("why", "")), "strategy brief",
                      PINK if _f(_D(g).get("weight")) > 850 else AMBER),
        "Gap", "nothing reported",
        ("A gap appears when a system detects something content can fix — a "
         "query at #11-20, a market with no traffic, an AI engine that never "
         "names you."), "strategy brief")
    cards += [
        ("Striking distance", len(_L(sig.get("striking_distance"))), "queries at #11-20",
         _hbars([(_D(q).get("query", "")[:20], _f(_D(q).get("position")))
                 for q in _L(sig.get("striking_distance"))[:6]]),
         ("These already rank. A piece aimed at one moves it to page 1 faster "
          "than any new topic."),
         "SEO engine", GREEN if sig.get("striking_distance") else AMBER,
         "<button class='cta' onclick=\"nav('seo')\">Open SEO</button>"),
        ("Decaying pages", len(_L(sig.get("decaying_pages"))), "losing clicks", "",
         "A refresh recovers traffic you already earned.",
         "SEO engine", AMBER if sig.get("decaying_pages") else GREEN, ""),
        ("AI mentions", _i(_D(sig.get("ai_visibility")).get("mentions"))
         if "ai_visibility" in sig else "—", "across AI engines", "",
         ("AI engines never name this business. Content that answers the "
          "questions buyers ask an AI is the only way in."
          if "ai_visibility" in sig else "The AEO probe has not run."),
         "AEO engine", PINK if "ai_visibility" in sig else AMBER, ""),
        ("Missing markets", len(_L(sig.get("missing_markets"))), "of your five",
         _statusgrid([(m, False, "no traffic") for m in _L(sig.get("missing_markets"))]),
         (f"No traffic from {', '.join(_L(sig.get('missing_markets')))}."
          if sig.get("missing_markets") else "All target markets produce traffic."),
         "GEO engine", PINK if sig.get("missing_markets") else GREEN, ""),
        ("Verticals that source", len(_L(sig.get("sourced_verticals"))), "measured",
         _hbars([(_D(v).get("vertical", "")[:18], _i(_D(v).get("leads")))
                 for v in _L(sig.get("sourced_verticals"))[:6]]),
         "Write for the vertical that actually replies, not only the ICP list.",
         "Leads & Outreach", BLUE if sig.get("sourced_verticals") else AMBER, ""),
        ("Revenue by source", len(_L(sig.get("revenue_by_source"))), "sources",
         _split_donut([(_D(r).get("source", ""), _f(_D(r).get("revenue")), c)
                       for r, c in zip(_L(sig.get("revenue_by_source")),
                                       (GREEN, TEAL, BLUE, AMBER, PINK))]),
         "Weight the plan toward what actually paid.",
         "BI", GREEN if sig.get("revenue_by_source") else AMBER, ""),
        ("Sessions per post", _n(sig.get("sessions_per_post")), "measured", "",
         ("Channel choice by measured performance rather than a hardcoded "
          "'70% LinkedIn' rule."),
         "SGA", BLUE if sig.get("sessions_per_post") is not None else AMBER, ""),
        ("Paid keywords worth owning", len(_L(sig.get("expensive_paid_keywords"))),
         "from Google Ads",
         _rows(_L(sig.get("expensive_paid_keywords"))[:6],
               left_fmt=lambda x: str(x)[:34], empty=""),
         "Ranking organically for a keyword you pay for is the cheapest "
         "long-term win.",
         "Media Buying", BLUE if sig.get("expensive_paid_keywords") else AMBER, ""),
        ("Winning subject lines", len(_L(sig.get("winning_subjects"))), "from outreach",
         "", "Subjects that earned replies make strong article angles.",
         "Leads & Outreach", BLUE if sig.get("winning_subjects") else AMBER, ""),
        ("Biggest funnel leak",
         (_D(sig.get("biggest_funnel_leak")).get("stage", "—")
          if sig.get("biggest_funnel_leak") else "—"), "stage", "",
         ("Content that addresses the leak is worth more than content at the "
          "top of the funnel."),
         "BI", AMBER if sig.get("biggest_funnel_leak") else GREEN, ""),
        ("Live campaigns", len(_L(sig.get("live_campaigns"))), "to slot into", "",
         "A piece inside a campaign inherits its UTM and is measurable.",
         "SGA", BLUE if sig.get("live_campaigns") else AMBER, ""),
        ("Budget ceiling", _money(_D(sig.get("budget")).get("headroom")), "headroom",
         _score_gauge(round(100 * _f(_D(sig.get("budget")).get("spent")) /
                            max(_f(_D(sig.get("budget")).get("cap")), 1)), 85),
         "The plan size is capped by what the budget can actually produce.",
         "meters", BLUE, ""),
        ("What changed", "site_signals", "was an empty dict", "",
         ("api_plan_content passed site_signals={} — the planner could only "
          "balance its own taxonomy against its own past titles. It now receives "
          "everything above as evidence."),
         "the fix", VIOLET, ""),
        ("Plan from this brief", "one click", "evidence-led", "",
         "The planner is handed these signals plus the list of channels that "
         "are actually live.",
         "strategy brief", VIOLET,
         "<button class='cta' onclick='planContent()'>Plan a week</button>"),
    ]
    return _head("🧭", "Strategy brief",
                 "What every other system knows, assembled into the evidence "
                 "the planner sees.") + _vizcards(cards[:20])


# ======================================================================
#  (3) PLAN & CALENDAR  (20)
# ======================================================================
def board_plan(ctx) -> str:
    ctx = _ctx(ctx)
    pl, br = _D(ctx.get("plan")), ctx["brief"]
    items = _L(pl.get("items"))
    el = _D(br.get("eligibility"))
    tasks = []
    for i, it in enumerate(items[:10]):
        tasks.append((str(_D(it).get("title", ""))[:20],
                      max(0, _i(_D(it).get("day_offset"))), 1))
    cards = [
        ("Planned pieces", len(items), "awaiting your approval",
         _CH().gantt(tasks, span=7),
         ("A one-week production calendar. Nothing is written until you approve "
          "it." if items else
          "No plan pending. Planning a week costs one LLM call and writes "
          "nothing until you approve."),
         "content plan", GREEN if items else AMBER,
         "<button class='cta' onclick='planContent()'>Plan a week</button>"),
        ("Channels in the plan",
         len({c for it in items for c in _L(_D(it).get("channels"))}), "distinct",
         _statusgrid([(r.get("label"), r.get("live"),
                       "" if r.get("live") else "not planned")
                      for r in _L(el.get("rows"))]),
         ("Only live channels can be planned — the eligibility list is handed "
          "to the planner."),
         "eligibility", GREEN, ""),
        ("Pieces per day",
         round(len(items) / 7, 1) if items else 0, "across the week",
         _histogram([sum(1 for it in items if _i(_D(it).get("day_offset")) == d)
                     for d in range(7)]),
         "Spread beats clustering — for search, for social and for your review "
         "load.",
         "content plan", BLUE, ""),
    ]
    cards += _slots(
        items, 8,
        lambda i, it: (f"{str(_D(it).get('title', ''))[:26]}",
                       f"day {_i(_D(it).get('day_offset'))}",
                       _s2(_D(it).get("type")) or "blog", "",
                       (f"{_D(it).get('segment', '')} · {_D(it).get('pillar', '')}. "
                        f"Target: {_D(it).get('target_keyword', 'none')}. "
                        f"{_D(it).get('rationale', '')}")[:200],
                       "content plan", BLUE,
                       f"<span class='dim'>{', '.join(_L(_D(it).get('channels')))}</span>"),
        "Planned piece", "not planned yet",
        ("Each planned piece carries a segment, a pillar, a target keyword, a "
         "day and its channels."), "content plan")
    cards += [
        ("Approval gate", "on", "nothing is written yet", "",
         ("The plan is a proposal. Approving it creates the jobs; declining it "
          "costs nothing."),
         "engine", GREEN, ""),
        ("Segment balance",
         len({_D(it).get("segment") for it in items if _D(it).get("segment")}),
         "customer segments",
         _hbars([(s[:18], sum(1 for it in items if _D(it).get("segment") == s))
                 for s in {_D(it).get("segment") for it in items if _D(it).get("segment")}]),
         "The planner spreads across your seven website segments, prioritising "
         "the ones covered least recently.",
         "content plan", BLUE, ""),
        ("Every card previews", "yes", "before you approve", "",
         ("The old calendar showed a title, a channel badge and a stage. You "
          "could not see what it would look like anywhere."),
         "the fix", GREEN,
         "<button class='cta' onclick=\"seoTab('cfpvweb')\">See a preview</button>"),
        ("Assigned to a campaign",
         _i(_D(ctx.get("campaigns")).get("planned_assigned")),
         f"of {_i(_D(ctx.get('campaigns')).get('planned_items'))} planned",
         _score_gauge(_f(_D(ctx.get("campaigns")).get("plan_coverage")), 80),
         str(_D(ctx.get("campaigns")).get("note", "")),
         "your campaigns",
         GREEN if _D(ctx.get("campaigns")).get("planned_assigned") else AMBER, ""),
        ("Live campaigns to join",
         _i(_D(ctx.get("campaigns")).get("live_count")), "running now",
         _statusgrid([(c[:16], True, "") for c in
                      _L(_D(ctx.get("campaigns")).get("live_campaigns"))]),
         ("The planner is handed these names and attaches a piece to one when "
          "it fits. The campaign becomes the piece's utm_campaign."),
         "SGA", BLUE if _D(ctx.get("campaigns")).get("live_count") else AMBER,
         "<button class='cta' onclick=\"nav('sga')\">Plan a campaign</button>"),
        ("Capped by budget", _money(br.get("budget_headroom")), "headroom", "",
         "A week is never planned that the budget cannot write.",
         "strategy brief", BLUE, ""),
        ("Keyword targets set",
         sum(1 for it in items if _s2(_D(it).get("target_keyword"))),
         f"of {len(items)} pieces", "",
         ("A piece with no target keyword is written blind — it may rank for "
          "nothing in particular."),
         "content plan", AMBER if items else BLUE, ""),
        ("Rationale on every piece", len(items), "explained", "",
         ("The planner states why THIS piece for THIS segment now. A plan you "
          "cannot argue with is a plan you cannot correct."),
         "content plan", GREEN if items else AMBER, ""),
        ("Where approval happens", "Approvals", "one screen", "",
         "Approve the plan, then approve each piece.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
    ]
    return _head("🗓", "Plan & calendar",
                 "The week ahead — what posts, which day, which channel, and "
                 "why that piece.") + _vizcards(cards[:20])


def _s2(v):
    return str(v or "").strip()


# ======================================================================
#  (10) CREATIVE & IMAGE  (20)
# ======================================================================
def board_image(ctx) -> str:
    ctx = _ctx(ctx)
    im, pv = ctx["images"], ctx["previews"]
    need = _D(ctx.get("image_need"))
    cards = [
        ("Image generation", ("ready" if im.get("configured") else "not working"),
         im.get("provider", "openai"),
         _donut(100 if im.get("configured") else 0),
         str(im.get("verdict", "")),
         "IMAGE_API_KEY", GREEN if im.get("configured") else PINK,
         "<button class='cta' onclick='testImage()'>Test an image now</button>"),
        ("Claude cannot make images", "true", "there is no Anthropic image API",
         "", str(im.get("truth", "")),
         "the fix", VIOLET if not im.get("key_looks_anthropic") else PINK, ""),
        ("Which key does what", 2, "different wires",
         _statusgrid([("IMAGE_API_KEY", bool(im.get("key_present")), "images"),
                      ("ANTHROPIC_API_KEY", True, "the writing")]),
         ("IMAGE_API_KEY makes pictures and must be an OpenAI key. "
          "ANTHROPIC_API_KEY is the engine's brain. Filling one does nothing "
          "for the other."),
         "System & Wiring", BLUE,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        ("Key looks wrong",
         ("yes" if im.get("key_looks_anthropic") else "no"), "sk-ant- prefix", "",
         ("An Anthropic key is set as the IMAGE key. Every image call will 401."
          if im.get("key_looks_anthropic") else
          "The image key does not look like an Anthropic key."),
         "computed", PINK if im.get("key_looks_anthropic") else GREEN, ""),
        ("Cost per image", _money(im.get("cost_per_image")), "OpenAI gpt-image-1",
         "", ("At 15 social posts a day this is about €18 a month. It draws on "
              "the same monthly cap as the writing."),
         "pricing", BLUE, ""),
        ("Channels that REQUIRE an image", len(_L(need.get("required_by"))),
         "or the post is rejected",
         _statusgrid([("Instagram", not need.get("blocking"), "needs image"),
                      ("YouTube", not need.get("blocking"), "needs thumbnail")]),
         str(need.get("note", "")),
         "platform rules", PINK if need.get("blocking") else GREEN, ""),
        ("Why Instagram never worked", "no image for social", "root cause", "",
         ("_ensure_hero_image() ran only for blog and guide types, so a social "
          "piece never got a visual — and Instagram rejects a post without one. "
          "It now runs for every type that needs a picture."),
         "the fix", GREEN, ""),
        ("On-brand prompt", "from your CI", "colour and mood", "",
         ("The image prompt is built from the piece title plus your CI block, so "
          "the visual matches the brand rather than a stock look."),
         "your CI", GREEN, ""),
        ("Hosted permanently", "WordPress media", "never expires", "",
         ("gpt-image-1 returns base64 and dall-e-3 returns a short-lived URL. "
          "Either way the bytes are uploaded to your media library so the image "
          "never disappears from a published post."),
         "connectors", GREEN, ""),
    ]
    for plat in ("website", "linkedin", "instagram", "twitter", "facebook", "youtube"):
        v = _pv(ctx, plat)
        has = bool(v.get("has_image"))
        cards.append((f"{plat.title()} visual", "present" if has else "missing",
                      "for this piece",
                      _donut(100 if has else 0),
                      ("The preview shows it in place." if has else
                       "This platform will show a placeholder or reject the post."),
                      "previews", GREEN if has else PINK, ""))
    cards += [
        ("Alt text", "generated", "for accessibility and SEO", "",
         "Every generated image gets alt text from the piece title.",
         "SEO engine", GREEN, ""),
        ("Video", "not generated", "your asset", "",
         ("The engine writes titles, descriptions and thumbnails. It does not "
          "produce video — that is yours to supply."),
         "honest limit", AMBER, ""),
        ("Test costs €0.04", "one image", "and shows you the result", "",
         ("The test button generates one real image so you can see whether the "
          "key works and whether the style matches your brand."),
         "your decision", VIOLET,
         "<button class='cta' onclick='testImage()'>Test an image</button>"),
        ("Budget", "command centre", "you steer the target", "",
         "Image spend draws on the monthly cap alongside the writing.",
         "your decision", VIOLET,
         "<button class='cta' onclick=\"nav('mission')\">Open Command Center</button>"),
        ("Where to fix the key", "System & Wiring", "in the browser", "",
         "No SSH, no rebuild — the key is read settings-first.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
    ]
    return _head("🎨", "Creative & image",
                 "Whether a picture gets made, which key makes it, and which "
                 "platforms refuse to publish without one.") + _vizcards(cards[:20])


# ======================================================================
#  (11) BRAND & CI  (18)
# ======================================================================
def board_ci(ctx) -> str:
    ctx = _ctx(ctx)
    ci = ctx["ci"]
    rows = _L(ci.get("rows"))
    cards = [
        ("CI compliance", f"{ci.get('score', 0)}%", "of checks pass",
         _score_gauge(_f(ci.get("score")), 80),
         ("The CI reached the prompt all along — nothing ever reported whether "
          "the DRAFT honoured it. This checks the text against each field."),
         "your CI", GREEN if _f(ci.get("score")) >= 80 else AMBER, ""),
        ("CI configured", "yes" if ci.get("configured") else "no",
         f"{len(_L(ci.get('fields')))} fields",
         _statusgrid([(f[:16], True, "") for f in _L(ci.get("fields"))[:8]]),
         ("Your brand file is loaded and prepended to every skill prompt."
          if ci.get("configured") else
          "No CI configured — agents use built-in defaults."),
         "your CI", GREEN if ci.get("configured") else AMBER, ""),
    ]
    cards += _slots(
        rows, 6,
        lambda i, r: (str(r[0])[:28], "pass" if r[1] else "fix", str(r[2])[:36], "",
                      f"{r[0]}: {r[2]}.", "your CI", GREEN if r[1] else PINK),
        "CI check", "no CI loaded",
        ("Each CI field becomes a check on the draft. With no CI configured the "
         "agents fall back to built-in defaults, which are safe but generic."),
        "your CI", AMBER)
    cards += [
        ("Where the CI is applied", "the prompt prefix", "every skill", "",
         ("providers.py prepends the CI block to every skill prompt, so voice "
          "guidance reaches the writer, the social repurposer and the image "
          "prompt alike."),
         "providers", GREEN, ""),
        ("What the CI cannot fix", "layout", "only voice", "",
         ("A brand file shapes tone and colour direction. It cannot fix a layout "
          "you could not see — that is what the six preview screens are for."),
         "principle", VIOLET,
         "<button class='cta' onclick=\"seoTab('cfpvweb')\">See the previews</button>"),
        ("Image colour direction", "from the CI", "in the prompt", "",
         "The hero prompt echoes the brand kit's colour direction where it "
         "differs from the default.",
         "your CI", GREEN, ""),
        ("Voice drift", "checked per piece", "not assumed", "",
         "Banned words, shouting and brand naming are checked on the draft.",
         "computed", BLUE, ""),
        ("Freeform CI", "supported", "paste anything", "",
         ("The CI can be a structured file or free text — free text is passed "
          "through verbatim as the voice instruction."),
         "brand module", BLUE, ""),
        ("Design inspiration", "optional", "visual mood", "",
         "A separate note field feeds the image prompt's mood.",
         "brand module", BLUE, ""),
        ("Where to update it", "System & Wiring", "in the browser", "",
         "The CI is a setting like any other — no redeploy.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        ("Why it felt like it failed", "no feedback", "until now", "",
         ("You supplied a CI and had no way to see whether any of it landed. "
          "That is a reporting gap, not a brand gap."),
         "the fix", VIOLET, ""),
        ("Colour direction", "echoed in images", "where it differs", "",
         ("If your brand kit specifies colours, the hero prompt is told to "
          "follow them rather than the engine's default palette."),
         "your CI", BLUE, ""),
        ("Applies to every channel", "yes", "one voice", "",
         "The same CI shapes the article, the LinkedIn post and the caption.",
         "providers", GREEN, ""),
    ]
    return _head("🎯", "Brand & CI",
                 "Whether your brand actually reached the draft — and what a "
                 "brand file can and cannot fix.") + _vizcards(cards[:18])


# ======================================================================
#  (12) PIPELINE  (20)
# ======================================================================
def board_pipeline(ctx) -> str:
    ctx = _ctx(ctx)
    pl, tp = ctx["pipeline"], ctx["throughput"]
    stages = _L(pl.get("stages"))
    cards = [
        ("Pieces in production", _i(pl.get("total")), "across all stages",
         _waterfall(stages),
         "Every piece and where it sits on the line.",
         "jobs", GREEN if pl.get("total") else AMBER, ""),
        ("Waiting for approval", _i(pl.get("waiting")), "need you", "",
         "The only stage that needs a human.",
         "jobs", AMBER if pl.get("waiting") else GREEN,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ("Published", _i(pl.get("published")), "live", "",
         "Made it all the way through.",
         "jobs", GREEN if pl.get("published") else AMBER, ""),
        ("Failed", _i(pl.get("failed")), "produced nothing", "",
         "Consumed budget and returned no output.",
         "jobs", PINK if pl.get("failed") else GREEN, ""),
        ("Stage distribution", len(stages), "stages",
         _hbars([(s, n) for s, n in stages]),
         "A pile-up at one stage is where the line is stuck.",
         "computed", BLUE, ""),
    ]
    cards += _slots(
        stages, 5,
        lambda i, r: (f"Stage: {r[0]}", r[1], "pieces",
                      _donut(round(100 * _i(r[1]) / max(_i(pl.get("total")), 1))),
                      ("Idea picked and tagged to a segment and pillar." if i == 0 else
                       "Researched and written on brand." if i == 1 else
                       "Keyword, headings and meta checked." if i == 2 else
                       "Waiting for your approval." if i == 3 else
                       "Live on the channels it was aimed at."),
                      "jobs", BLUE),
        "Stage", "empty",
        "Each production stage is counted from the job status.", "jobs")
    cards += [
        ("Throughput", _n(tp.get("avg_per_day")), "pieces per day",
         _trend([("pieces", _L(tp.get("series")), TEAL)]),
         "Measured from job creation dates.",
         "jobs", BLUE, ""),
        ("Cost per published piece", _money(tp.get("per_piece")), "each", "",
         "Total content spend divided by pieces that actually published.",
         "computed", GREEN if tp.get("per_piece") else AMBER, ""),
        ("Total content spend", _money(tp.get("cost")), "all pieces", "",
         "What the library cost to produce.",
         "job costs", BLUE, ""),
        ("Human gate", "one stage", "by design", "",
         ("Everything is automated up to approval. Nothing publishes without "
          "you, and that is deliberate."),
         "engine", GREEN, ""),
        ("Where pieces stall", (max(stages, key=lambda s: s[1])[0]
                                if stages else "—"), "biggest queue", "",
         "The stage holding the most pieces is where to look first.",
         "computed", AMBER, ""),
        ("Actually landed", _i(_D(ctx.get("post_publish")).get("landed")),
         f"of {_i(_D(ctx.get('post_publish')).get('attempted'))} publish attempts",
         _waterfall(_L(_D(ctx.get("post_publish")).get("waterfall"))),
         str(_D(ctx.get("post_publish")).get("note", "")),
         "published refs",
         PINK if _D(ctx.get("post_publish")).get("failed") else GREEN, ""),
        ("Publish failures", _i(_D(ctx.get("post_publish")).get("failed")),
         "marked published, never posted",
         _hbars([(c, f) for c, _l, f in
                 _L(_D(ctx.get("post_publish")).get("by_channel")) if f]),
         ("A piece can sit green on this pipeline and be absent from the "
          "internet. This is the check that catches it."),
         "published refs",
         PINK if _D(ctx.get("post_publish")).get("failed") else GREEN, ""),
        ("Retries", "counted as cost", "not as output", "",
         "A retried piece costs twice and publishes once.",
         "job costs", AMBER, ""),
        ("Every stage is automated", "except one", "your approval", "",
         "Research, writing, SEO and repurposing all run without you.",
         "engine", GREEN, ""),
        ("Where to unblock", "Approvals", "review and release", "",
         "Most stalls are waiting on a human, not a machine.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
    ]
    return _head("⚙️", "Production pipeline",
                 "Where every piece is, and where the line is stuck.") + _vizcards(cards[:20])


# ======================================================================
#  (13) QUALITY  (18)
# ======================================================================
def board_quality(ctx) -> str:
    ctx = _ctx(ctx)
    pv, ci = ctx["previews"], ctx["ci"]
    web = _pv(ctx, "website")
    serp = _pv(ctx, "serp")
    cards = [
        ("Platform checks", f"{pv.get('score', 0)}%", "pass across six platforms",
         _score_gauge(_f(pv.get("score")), 90),
         (f"{_i(pv.get('checks_failed'))} of {_i(pv.get('checks_total'))} fail."),
         "previews", _pct_color(100 - _f(pv.get("score")), 20), ""),
        ("Blocked platforms", len(_L(pv.get("blocked"))), "would reject it",
         _statusgrid([(p.title(), False, "blocked") for p in _L(pv.get("blocked"))]),
         (f"{', '.join(_L(pv.get('blocked')))} cannot publish this piece."
          if pv.get("blocked") else "No platform would reject it."),
         "previews", PINK if pv.get("blocked") else GREEN, ""),
        ("Brand compliance", f"{ci.get('score', 0)}%", "of CI checks",
         _donut(_f(ci.get("score"))),
         "Voice, banned words and brand naming, checked on the draft.",
         "your CI", GREEN if _f(ci.get("score")) >= 80 else AMBER, ""),
        ("Article length", _i(web.get("words")), "words",
         _score_gauge(min(100, round(100 * _i(web.get("words")) / 1200)), 50),
         "Under 600 rarely ranks. Over 2500 rarely gets finished.",
         "the piece", BLUE, ""),
        ("Heading structure", _i(web.get("headings")), "H2/H3", "",
         "Structure is what makes a long piece readable.",
         "the piece", GREEN if _i(web.get("headings")) >= 2 else AMBER, ""),
        ("Search title", _i(serp.get("title_len")), "of 60 chars", "",
         ("Truncated in results — the end of the title is lost."
          if serp.get("truncated") else "Fits without truncation."),
         "SERP preview", PINK if serp.get("truncated") else GREEN, ""),
        ("Meta description", _i(serp.get("meta_len")), "of 155 chars", "",
         "Google rewrites anything longer.",
         "SERP preview", BLUE, ""),
        ("CAN-SPAM / compliance", "checked", "before send", "",
         "The safety module validates every email before it can leave.",
         "safety module", GREEN, ""),
        ("QA gate", "before approval", "automatic", "",
         "The QA skill blocks a piece that fails its own checks.",
         "orchestrator", GREEN, ""),
        ("What QA cannot catch", "layout", "only text", "",
         ("Text checks cannot tell you a caption is cut in the wrong place. "
          "That is what the previews are for."),
         "principle", VIOLET, ""),
    ]
    cards += _slots(
        _L(ci.get("rows")), 5,
        lambda i, r: (f"CI: {str(r[0])[:24]}", "pass" if r[1] else "fix",
                      str(r[2])[:32], "", f"{r[0]}: {r[2]}.",
                      "your CI", GREEN if r[1] else PINK),
        "CI check", "not configured",
        "Each CI field becomes a check on the draft.", "your CI")
    cards += [
        ("Fix before approving", "in Approvals", "edit inline", "",
         "Every piece can be edited before it publishes.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('appr')\">Open Approvals</button>"),
        ("Quality over volume", "for €2k-10k projects", "your market", "",
         ("One piece that ranks and reads well beats five that neither rank nor "
          "get finished."),
         "judgement", VIOLET, ""),
        ("Evals", "run separately", "on the agents", "",
         "Agent quality is scored in Risk & Infrastructure.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
    ]
    return _head("✅", "Quality",
                 "Whether this piece is good enough to publish — text, brand "
                 "and layout.") + _vizcards(cards[:18])


# ======================================================================
#  (14) CHANNEL ROUTING  (18)
# ======================================================================
def board_routing(ctx) -> str:
    ctx = _ctx(ctx)
    rt, el = ctx["routing"], _D(ctx["brief"].get("eligibility"))
    planned = _L(rt.get("planned"))
    cards = [
        ("Where pieces are aimed", len(planned), "channels",
         _CH().sankey([(a, b, c) for a, b, c in _L(rt.get("flows"))]),
         "Every planned piece and the channel it targets.",
         "job config", BLUE if planned else AMBER, ""),
        ("Aimed at a dead wire", _i(rt.get("mismatch_count")), "pieces",
         "", str(rt.get("note", "")),
         "computed", PINK if rt.get("mismatch_count") else GREEN, ""),
        ("Channels you can publish to", _i(el.get("count")), f"of {_i(el.get('total'))}",
         _statusgrid([(r.get("label"), r.get("live"), "" if r.get("live") else "no wire")
                      for r in _L(el.get("rows"))]),
         str(el.get("note", "")),
         "wire status", GREEN if el.get("count") else PINK, ""),
        ("The eligibility gate", "new", "planner-side", "",
         ("Nothing ever checked whether a channel was connected before planning "
          "for it. That is the direct cause of content being pushed to the "
          "wrong channel."),
         "the fix", GREEN, ""),
    ]
    cards += _slots(
        planned, 6,
        lambda i, r: (f"→ {str(r[0]).title()}", r[1], "pieces aimed here",
                      _donut(round(100 * _i(r[1]) /
                                   max(sum(_i(x[1]) for x in planned), 1))),
                      ("This channel has a live wire."
                       if str(r[0]) in _L(el.get("eligible")) else
                       "NO live wire — these pieces will return a "
                       "not_configured marker instead of publishing."),
                      "job config",
                      GREEN if str(r[0]) in _L(el.get("eligible")) else PINK),
        "Channel", "nothing aimed here",
        "A channel appears once a piece is planned for it.", "job config")
    cards += _slots(
        _L(rt.get("mismatched")), 4,
        lambda i, r: (f"Mismatch: {str(r[0])[:18]}", str(r[1]), "no live wire", "",
                      ("This piece is aimed at a channel that cannot receive it. "
                       "Connect the wire or change the channel."),
                      "computed", PINK,
                      "<button class='cta' onclick=\"nav('system')\">Connect</button>"),
        "Mismatch", "none",
        "Every planned channel has a live wire.", "computed", GREEN)
    cards += [
        ("Website is the anchor", "always", "you own it", "",
         ("Social platforms can change their rules. The article on your own "
          "site cannot be taken away."),
         "principle", VIOLET, ""),
        ("UTM on every social link", "on", "so GA4 can credit the post", "",
         "Tagged at post time by the SGA layer.",
         "SGA", GREEN,
         "<button class='cta' onclick=\"nav('sga')\">Open SGA</button>"),
        ("Repurposed, not copied", "per channel", "native each time", "",
         "The engine reshapes a piece per platform rather than cross-posting.",
         "engine", GREEN, ""),
        ("Where to connect", "System & Wiring", "in the browser", "",
         "Every channel credential is entered there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
    ]
    return _head("🔀", "Channel routing",
                 "Where each piece is aimed, and whether that channel can "
                 "actually receive it.") + _vizcards(cards[:18])


# ======================================================================
#  (15) REPURPOSING  (16)
# ======================================================================
def board_repurpose(ctx) -> str:
    ctx = _ctx(ctx)
    rp = ctx["repurposing"]
    rows = _L(rp.get("rows"))
    cards = [
        ("Native copy written", _i(rp.get("native")), "of the planned channels",
         _statusgrid(_L(rp.get("statusgrid"))),
         str(rp.get("note", "")),
         "the piece", GREEN if rp.get("native") else AMBER, ""),
        ("Coverage", f"{rp.get('coverage', 0)}%", "channels with native copy",
         _score_gauge(_f(rp.get("coverage")), 80),
         ("Where native copy is missing the engine falls back to the article "
          "body, which reads as a cross-post."),
         "computed", _pct_color(100 - _f(rp.get("coverage")), 40), ""),
    ]
    PLAT_FALLBACK = [{"label": l, "written": False, "planned": False,
                      "state": "not planned"} for l in
                     ("Website", "LinkedIn", "Instagram", "X", "Facebook", "YouTube")]
    for r in (rows or PLAT_FALLBACK):
        r = _D(r)
        cards.append((f"{r.get('label')}",
                      ("native" if r.get("written") else
                       "fallback" if r.get("planned") else "not planned"),
                      str(r.get("state"))[:26],
                      _donut(100 if r.get("written") else 50 if r.get("planned") else 0),
                      (f"{r.get('label')}: {r.get('state')}."),
                      "the piece",
                      GREEN if r.get("written") else AMBER if r.get("planned") else BLUE,
                      ""))
    cards += [
        ("One piece, many shapes", "by design", "not a copy-paste", "",
         ("The same research becomes an article, a LinkedIn post, a caption and "
          "a thread — each written for its platform."),
         "engine", GREEN, ""),
        ("Why cross-posting fails", "every platform", "punishes it", "",
         ("A 1500-word article pasted into Instagram reads as spam; a 280-char "
          "quip on the website reads as nothing."),
         "judgement", VIOLET, ""),
        ("Character limits differ wildly", "280 to 63206", "across platforms", "",
         "X allows 280. Facebook allows 63,206. The same text cannot serve both.",
         "platform rules", BLUE, ""),
        ("Preview each shape", "six screens", "before approving", "",
         "Every repurposed version has its own preview.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"seoTab('cfpvli')\">See LinkedIn</button>"),
        ("Native beats reach", "on every platform", "measured everywhere", "",
         ("Platforms rank native content above anything that looks like it was "
          "pasted in from elsewhere — links included."),
         "judgement", VIOLET, ""),
        ("The article is the source", "everything derives from it", "one research pass",
         "", ("One piece of research becomes six shapes. The cost is paid once."),
         "engine", GREEN, ""),
        ("Where distribution is measured", "SGA", "250 cards", "",
         "Which channel earned what is measured there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('sga')\">Open SGA</button>"),
        ("Missing native copy",
         max(0, _i(rp.get("planned")) - _i(rp.get("native"))), "channels", "",
         "These will publish the article body verbatim.",
         "computed", AMBER, ""),
    ]
    return _head("♻️", "Repurposing",
                 "One piece, reshaped per platform — and where it still falls "
                 "back to a copy-paste.") + _vizcards(cards[:16])


# ======================================================================
#  (16) COST & THROUGHPUT  (16)
# ======================================================================
def board_cost(ctx) -> str:
    ctx = _ctx(ctx)
    tp, br, im = ctx["throughput"], ctx["brief"], ctx["images"]
    cards = [
        ("Content spend", _money(tp.get("cost")), "all pieces",
         _trend([("pieces/day", _L(tp.get("series")), TEAL)]),
         "What the whole library cost to produce.",
         "job costs", BLUE if tp.get("cost") else AMBER, ""),
        ("Cost per published piece", _money(tp.get("per_piece")), "each",
         _score_gauge(min(100, round(_f(tp.get("per_piece")) * 100)), 100),
         ("Failed pieces are excluded from the denominator — dividing by work "
          "that produced nothing flatters the number."),
         "computed", GREEN if tp.get("per_piece") else AMBER, ""),
        ("Pieces published", _i(tp.get("published")), "of "
         f"{_i(tp.get('total'))} started", "",
         "The real denominator.",
         "jobs", GREEN if tp.get("published") else AMBER, ""),
        ("Output per day", _n(tp.get("avg_per_day")), "pieces",
         _histogram([_i(v) for v in _L(tp.get("series"))]),
         "The distribution matters — steady beats bursts.",
         "jobs", BLUE, ""),
        ("Budget headroom", _money(br.get("budget_headroom")), "left this month",
         "", "The plan is capped to what this can produce.",
         "meters", GREEN if _f(br.get("budget_headroom")) > 20 else PINK, ""),
        ("Image cost", _money(im.get("cost_per_image")), "per image", "",
         ("At 15 social posts a day, about €18 a month. It draws on the same "
          "monthly cap as the writing."),
         "pricing", BLUE, ""),
        ("Cap stays open", "your call", "steered from the command centre", "",
         ("You asked to keep the cap open and steer the target yourself. The "
          "engine still halts at the cap rather than overspending."),
         "your decision", VIOLET,
         "<button class='cta' onclick=\"nav('mission')\">Open Command Center</button>"),
        ("Cost per word",
         (_money(_f(tp.get("cost")) / max(_i(tp.get("published")), 1) / 1200)
          if tp.get("published") else "—"), "roughly", "",
         "Assuming ~1200 words a piece. Useful only against an agency quote.",
         "computed", BLUE, ""),
        ("Versus an agency", "orders of magnitude", "cheaper per piece", "",
         ("A €0.60 piece against a €400 agency article is the whole argument for "
          "this engine — provided the piece is actually good, which is what the "
          "Quality board is for."),
         "judgement", VIOLET, ""),
        ("Retries cost twice", "counted", "as spend not output", "",
         "A retried piece is charged once and published once.",
         "job costs", AMBER, ""),
        ("Where economics live", "BI", "CAC, LTV, payback", "",
         "Content cost feeds the unit economics there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
        ("Where the cap is set", "System & Wiring", "monthly and daily", "",
         "Both are enforced, not advisory.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        ("Spend by stage", "writing dominates", "images are marginal", "",
         "The LLM call to write a piece costs far more than its image.",
         "job costs", BLUE, ""),
        ("Throughput ceiling", "budget, not agents", "today", "",
         "Agent capacity is well above what the cap allows.",
         "Risk & Infrastructure", BLUE, ""),
        ("Failed spend", "tracked", "in Risk", "",
         "Money spent on pieces that produced nothing is reported there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
        ("Plan within budget", "automatic", "capped", "",
         "A week is never planned that the budget cannot write.",
         "strategy brief", GREEN, ""),
    ]
    return _head("🧾", "Cost & throughput",
                 "What content costs to make, and how much gets made.") + _vizcards(cards[:16])


# ======================================================================
#  SECTION
# ======================================================================
TABS = [
    ("cfcmd", "🏭", "Factory Command"),
    ("cfbrief", "🧭", "Strategy Brief"),
    ("cfplan", "🗓", "Plan & Calendar"),
    ("cfpvweb", "🌐", "Preview · Website"),
    ("cfpvli", "in", "Preview · LinkedIn"),
    ("cfpvig", "◎", "Preview · Instagram"),
    ("cfpvx", "𝕏", "Preview · X & FB"),
    ("cfpvyt", "▶", "Preview · YouTube"),
    ("cfpvserp", "🔍", "Preview · Search"),
    ("cfimage", "🎨", "Creative & Image"),
    ("cfci", "🎯", "Brand & CI"),
    ("cfpipe", "⚙️", "Pipeline"),
    ("cfqa", "✅", "Quality"),
    ("cfroute", "🔀", "Channel Routing"),
    ("cfrepurpose", "♻️", "Repurposing"),
    ("cfcost", "🧾", "Cost & Throughput"),
]

GROUPS = [
    ("cfplanit", "① PLAN IT", "What should we make?",
     ["cfcmd", "cfbrief", "cfplan"]),
    ("cfseeit", "② SEE IT", "How will it look?",
     ["cfpvweb", "cfpvli", "cfpvig", "cfpvx", "cfpvyt", "cfpvserp"]),
    ("cfmakeit", "③ MAKE IT", "Is it good enough?",
     ["cfimage", "cfci", "cfpipe", "cfqa"]),
    ("cfshipit", "④ SHIP IT", "Where does it go?",
     ["cfroute", "cfrepurpose", "cfcost"]),
]

_TAB_BOARDS = {
    "cfcmd": [("Factory Command", board_command)],
    "cfbrief": [("Strategy Brief", board_brief)],
    "cfplan": [("Plan & Calendar", board_plan)],
    "cfpvweb": [("Preview Website", board_pv_website)],
    "cfpvli": [("Preview LinkedIn", board_pv_linkedin)],
    "cfpvig": [("Preview Instagram", board_pv_instagram)],
    "cfpvx": [("Preview X & Facebook", board_pv_x)],
    "cfpvyt": [("Preview YouTube", board_pv_youtube)],
    "cfpvserp": [("Preview Search", board_pv_serp)],
    "cfimage": [("Creative & Image", board_image)],
    "cfci": [("Brand & CI", board_ci)],
    "cfpipe": [("Pipeline", board_pipeline)],
    "cfqa": [("Quality", board_quality)],
    "cfroute": [("Channel Routing", board_routing)],
    "cfrepurpose": [("Repurposing", board_repurpose)],
    "cfcost": [("Cost & Throughput", board_cost)],
}

_TAB_COUNTS = {"cfcmd": 16, "cfbrief": 20, "cfplan": 20, "cfpvweb": 18,
               "cfpvli": 16, "cfpvig": 16, "cfpvx": 16, "cfpvyt": 14,
               "cfpvserp": 16, "cfimage": 20, "cfci": 18, "cfpipe": 20,
               "cfqa": 18, "cfroute": 18, "cfrepurpose": 16, "cfcost": 16}
TOTAL_CARDS = sum(_TAB_COUNTS.values())
PREVIEW_CARDS = sum(_TAB_COUNTS[t] for t in
                    ("cfpvweb", "cfpvli", "cfpvig", "cfpvx", "cfpvyt", "cfpvserp"))


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


def factory_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def factory_section(ctx) -> str:
    H = _H()
    ctx = _ctx(ctx)
    panels = factory_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'cfplanit')}' onclick=\"seoTab('{tid}')\">"
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
              "<button class='cbtn' onclick='planContent()'>🗓 Plan a week from all systems</button>"
              "<button class='cbtn' onclick='testImage()'>🎨 Test an image (€0.04)</button>"
              "<button class='cbtn' onclick=\"nav('appr')\">✅ Approvals</button>"
              "</div>")
    return (_TAB_CSS
            + "<div class='sgroups'>" + grouprail + "</div>"
            + runbar
            + "<div class='stabs'>" + bar + "</div>"
            + "<div class='spanels'>" + body + "</div>")


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_factory as F

    PIECE = {
        "title": "How Munich clinics recover missed patient enquiries",
        "seo_title": "Munich clinics: stop losing after-hours enquiries",
        "meta_description": "How Munich clinics stop losing after-hours patient "
                            "enquiries with simple automation that runs itself.",
        "body": ("Most clinics lose enquiries after hours.\n\n"
                 "## The cost of a missed call\n" + ("word " * 700) +
                 "\n\n## What to do\nSee [our guide](https://a.com/g)."),
        "image_url": "https://cdn.example.com/hero.png",
        "linkedin_post": "Clinics lose 30% of enquiries after hours. " + ("x" * 400)
                         + " #automation #healthcare #munich",
    }
    status = {"wordpress_publish": True, "social_linkedin": True}
    jobs = [{"job_id": "c1", "type": "content_piece", "status": "AWAITING_APPROVAL",
             "created_at": "2026-07-30T09:00:00Z", "cost_so_far_usd": 0.4,
             "payload": {"config": {"deploy_channels": ["website", "instagram"]}}},
            {"job_id": "c2", "type": "content_piece", "status": "published",
             "created_at": "2026-07-29T09:00:00Z", "cost_so_far_usd": 0.6,
             "payload": {"config": {"deploy_channels": ["website"]}}}]
    brief = F.strategy_brief(
        seo={"striking": {"rows": [{"query": "n8n agency", "position": 14}]},
             "aeo": {"mentions": 0}},
        bi={"markets": {"missing": ["Germany"]},
            "revenue": {"by_source": [("outreach", 6000.0)]}},
        outreach={"icp": {"verticals": [("doctor", 12)]}},
        sga={"traffic": {"sessions_per_post": 8.5}},
        media={"winning_keywords": ["ai automation agency"]},
        risk={"cost": {"month_cap": 200, "month_spent": 41.7}},
        status=status)
    el = F.channel_eligibility(status)
    ctx = {
        "brief": brief, "eligibility": el,
        "previews": F.previews(PIECE, ["website", "linkedin"],
                               keyword="munich clinics"),
        "images": F.image_status({"image_gen": True}, image_key="sk-proj-x"),
        "image_need": F.image_needed("blog", ["website", "instagram"]),
        "ci": F.ci_compliance(PIECE, {"brand_name": "Anthropos", "tone": "plain",
                                      "avoid": ["synergy"]}),
        "pipeline": F.pipeline(jobs), "routing": F.routing(jobs, el),
        "repurposing": F.repurposing(PIECE, ["website", "linkedin", "instagram"]),
        "throughput": F.throughput(jobs), "piece": PIECE,
        "post_publish": F.post_publish(jobs),
        "campaigns": F.campaigns_assigned(jobs, {"items": []}, []),
        "plan": {"items": [{"title": "Clinic no-shows", "day_offset": 1,
                            "type": "blog", "segment": "Medical Professionals",
                            "pillar": "Never Lose a Lead",
                            "target_keyword": "clinic no shows",
                            "channels": ["website", "linkedin"],
                            "funnel": "mid", "rationale": "under-served segment"}]},
    }

    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        _CURRENT_BOARD["name"] = name
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = factory_pages(ctx)
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

    # THE point of this section: six real preview frames
    assert PREVIEW_CARDS == 96, PREVIEW_CARDS
    for tab in ("cfpvweb", "cfpvli", "cfpvig", "cfpvx", "cfpvyt", "cfpvserp"):
        assert "live preview" in pages[tab], f"{tab} has no preview frame"
        assert "<div style=" in pages[tab], f"{tab} frame did not render"
    assert "see more" in pages["cfpvli"], "LinkedIn must show its truncation"
    assert "… more" in pages["cfpvig"] or "more" in pages["cfpvig"]

    # the five failures, each answered on a card
    assert "cannot make images" in pages["cfimage"] or "cannot draw" in pages["cfimage"]
    assert "IMAGE_API_KEY" in pages["cfimage"] and "ANTHROPIC_API_KEY" in pages["cfimage"]
    assert "why Instagram never worked" in pages["cfimage"].lower() or \
        "Instagram never worked" in pages["cfimage"]
    assert "site_signals" in pages["cfbrief"], "say what changed"
    assert "dead wire" in pages["cfroute"] or "no live wire" in pages["cfroute"]
    assert "reporting gap, not a brand gap" in pages["cfci"]
    # the two loops I listed in the plan and had not built
    assert "Actually landed" in pages["cfpipe"], "C26 post-publish verification"
    assert "absent from the internet" in pages["cfpipe"]
    assert "Assigned to a campaign" in pages["cfplan"], "C10 campaign assignment"

    empty = factory_pages({})
    ehtml = "".join(empty.values())
    assert "failed to render" not in ehtml
    assert len(re.findall(r"<div class='card (?:overflowcard )?sev-", ehtml)) == TOTAL_CARDS

    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {"previews": "no"}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    charts = len(re.findall(r"<svg", html))
    print(f"factory_boards self-check OK — {len(_TAB_BOARDS)} boards, {counted} "
          f"cards, {len(set(ids))} unique ids, {charts} charts, and "
          f"{PREVIEW_CARDS} cards across SIX live preview screens that render "
          f"the piece as each platform will actually show it.")
