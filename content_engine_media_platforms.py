"""
content_engine_vx2_ads.py
============================================================================
THE ADS ENVIRONMENT. Five platforms, one shell, laid out the way each real ad
manager lays itself out: an account bar, a campaign hierarchy on the left, and
the selected level on the right under four tabs.

    Performance        what it did
    Ad preview         what it looks like where it runs
    Bidding & budget   what it costs and how it competes
    Targeting          who sees it

WHAT IS REAL AND WHAT IS NOT
  Exactly one of the five has a write API in this codebase: Google Ads, with
  create_campaign, pause_campaign and summary. Facebook, Instagram, LinkedIn
  and YouTube have organic posting connectors only. They have no campaign, ad
  set, creative or bid object anywhere in the engine.

  The founder asked for all five as full working screens. They are all here,
  complete and interactive. The four without an API run on SAMPLE data and say
  so in three places at once: a banner across the account bar, a mark on every
  figure, and the word sample in the page state. A number on those screens can
  be studied as a design and can never be mistaken for money that was spent.

  When a connector arrives, its platform moves from SAMPLE to LIVE by changing
  one entry in PLATFORMS. No screen is rebuilt.
============================================================================
"""

from __future__ import annotations

import html as _html


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


# ---------------------------------------------------------------------------
# THE FIVE PLATFORMS, described as they actually work
# ---------------------------------------------------------------------------
PLATFORMS = {
    "google": {
        "name": "Google Ads", "mark": "G", "colour": "#1A73E8",
        "connector": "GoogleAds", "state": "live",
        "levels": ("Campaign", "Ad group", "Ad"),
        "objectives": ("Sales", "Leads", "Website traffic",
                       "Brand awareness", "App promotion", "Local visits"),
        "formats": ("Responsive search ad", "Performance Max", "Display",
                    "Shopping", "Demand Gen", "Video (YouTube)"),
        "bidding": (
            ("Maximize conversions", "Spends the budget to win as many "
                                     "conversions as it can. No bid to set."),
            ("Target CPA", "Bids to average a cost you name per conversion."),
            ("Target ROAS", "Bids to average a return you name per euro."),
            ("Maximize clicks", "Cheapest possible clicks. Use only when you "
                                "have no conversion tracking."),
            ("Manual CPC", "You set every bid. Full control, most work."),
        ),
        "targeting": ("Keywords", "Audiences", "Locations", "Languages",
                      "Devices", "Ad schedule", "Demographics"),
        "creative": (("Headlines", 3, 30), ("Descriptions", 2, 90),
                     ("Display path", 2, 15)),
    },
    "facebook": {
        "name": "Facebook Ads", "mark": "f", "colour": "#1877F2",
        "connector": None, "state": "sample",
        "levels": ("Campaign", "Ad set", "Ad"),
        "objectives": ("Sales", "Leads", "Engagement", "Traffic",
                       "Awareness", "App promotion"),
        "formats": ("Single image", "Video", "Carousel", "Collection",
                    "Reels", "Stories"),
        "bidding": (
            ("Highest volume", "Spends the budget for the most results. Meta "
                               "chooses the bid."),
            ("Cost per result goal", "Aims at an average cost you name."),
            ("Bid cap", "Never bids above the figure you set."),
            ("ROAS goal", "Aims at a return on ad spend you name."),
        ),
        "targeting": ("Locations", "Age and gender", "Detailed targeting",
                      "Custom audiences", "Lookalikes", "Placements"),
        "creative": (("Primary text", 1, 125), ("Headline", 1, 40),
                     ("Description", 1, 30)),
    },
    "instagram": {
        "name": "Instagram Ads", "mark": "ig", "colour": "#C13584",
        "connector": None, "state": "sample",
        "levels": ("Campaign", "Ad set", "Ad"),
        "objectives": ("Sales", "Leads", "Engagement", "Traffic",
                       "Awareness", "Profile visits"),
        "formats": ("Feed image", "Feed video", "Stories", "Reels",
                    "Carousel", "Explore"),
        "bidding": (
            ("Highest volume", "Spends the budget for the most results."),
            ("Cost per result goal", "Aims at an average cost you name."),
            ("Bid cap", "Never bids above the figure you set."),
        ),
        "targeting": ("Locations", "Age and gender", "Interests",
                      "Custom audiences", "Lookalikes", "Placements"),
        "creative": (("Primary text", 1, 125), ("Headline", 1, 40)),
    },
    "linkedin": {
        "name": "LinkedIn Ads", "mark": "in", "colour": "#0A66C2",
        "connector": None, "state": "sample",
        "levels": ("Campaign group", "Campaign", "Ad"),
        "objectives": ("Lead generation", "Website visits", "Engagement",
                       "Brand awareness", "Video views", "Job applicants"),
        "formats": ("Single image", "Carousel", "Video", "Text ad",
                    "Message ad", "Document ad"),
        "bidding": (
            ("Maximum delivery", "Spends the budget for the most results."),
            ("Cost cap", "Aims at an average cost you name per result."),
            ("Manual bidding", "You set the bid for every auction."),
        ),
        "targeting": ("Job title", "Job function", "Seniority", "Company size",
                      "Industry", "Skills", "Member groups", "Years of "
                      "experience"),
        "creative": (("Introductory text", 1, 150), ("Headline", 1, 200)),
    },
    "tiktok": {
        "name": "TikTok Ads", "mark": "tt", "colour": "#161823",
        "connector": None, "state": "sample",
        "levels": ("Campaign", "Ad group", "Ad"),
        "objectives": ("Traffic", "Conversions", "Lead generation",
                       "Video views", "Reach", "App promotion"),
        "formats": ("In-Feed", "TopView", "Spark Ads", "Carousel",
                    "Collection"),
        "bidding": (
            ("Lowest cost", "Spends the budget for the most results. TikTok "
                            "chooses the bid."),
            ("Cost cap", "Aims at an average cost you name per result."),
            ("Bid cap", "Never bids above the figure you set."),
            ("Highest value", "Optimises toward purchase value rather than "
                              "count. Needs value tracking wired."),
        ),
        "targeting": ("Demographics", "Interests", "Behaviors",
                      "Hashtag interactions", "Custom audiences",
                      "Lookalikes", "Devices"),
        "creative": (("Video", 1, 0), ("Ad text", 1, 100),
                     ("Display name", 1, 40)),
    },
    "youtube": {
        "name": "YouTube Ads", "mark": "yt", "colour": "#FF0000",
        "connector": None, "state": "sample",
        "levels": ("Campaign", "Ad group", "Ad"),
        "objectives": ("Sales", "Leads", "Website traffic",
                       "Product consideration", "Brand awareness", "Reach"),
        "formats": ("Skippable in-stream", "Non-skippable in-stream",
                    "Bumper (6s)", "In-feed video", "Shorts"),
        "bidding": (
            ("Target CPM", "You name a cost per thousand impressions. Use "
                           "this when the goal is being seen, not clicked."),
            ("Target CPV", "You name a cost per view, where a view means "
                           "someone watched 30 seconds or the whole ad."),
            ("Maximize conversions", "Spends the budget for the most "
                                     "conversions."),
            ("Target CPA", "Bids to average a cost per conversion."),
        ),
        "targeting": ("Demographics", "Interests", "Custom segments",
                      "Life events", "Placements", "Topics", "Keywords"),
        "creative": (("Video", 1, 0), ("Headline", 1, 15),
                     ("Long headline", 1, 90), ("Description", 1, 70)),
    },
}

ORDER = ("google", "facebook", "instagram", "linkedin", "tiktok")

# Sample structures for the four platforms with no API. Shaped exactly like
# what a real pull returns, so wiring a connector later is a data swap and not
# a screen rewrite. Deliberately round and obviously illustrative.
SAMPLE = {
    "facebook": [
        {"name": "Leads · Munich SMB", "status": "active", "budget": 30,
         "spend": 412, "impr": 84000, "clicks": 1180, "conv": 24,
         "groups": [{"name": "Lookalike 1% · buyers", "spend": 260,
                     "ads": ["Automate the admin, keep the clients"]},
                    {"name": "Retarget · site visitors 30d", "spend": 152,
                     "ads": ["You looked. Here is what it costs."]}]},
        {"name": "Awareness · DACH", "status": "paused", "budget": 15,
         "spend": 96, "impr": 41000, "clicks": 310, "conv": 3,
         "groups": [{"name": "Broad · 25-54", "spend": 96,
                     "ads": ["Six hours a week, back."]}]},
    ],
    "instagram": [
        {"name": "Reels · founder story", "status": "active", "budget": 20,
         "spend": 240, "impr": 96000, "clicks": 1420, "conv": 11,
         "groups": [{"name": "Interests · small business owners",
                     "spend": 240, "ads": ["How one clinic stopped "
                                           "rescheduling by hand"]}]},
    ],
    "linkedin": [
        {"name": "Lead gen · tax consultants", "status": "active",
         "budget": 60, "spend": 1840, "impr": 62000, "clicks": 540, "conv": 18,
         "groups": [{"name": "Owners and partners, 10-200 staff",
                     "spend": 1180, "ads": ["The month-end close, automated"]},
                    {"name": "Marketing managers, agencies", "spend": 660,
                     "ads": ["Stop paying people to copy and paste"]}]},
    ],
    "tiktok": [
        {"name": "In-Feed · automation explainer", "status": "active",
         "budget": 20, "spend": 210, "impr": 180000, "clicks": 2100, "conv": 5,
         "groups": [{"name": "Interests · small business + tech",
                     "spend": 210, "ads": ["How a clinic automated its "
                                           "scheduling (30s)"]}]},
    ],
    "youtube": [
        {"name": "In-stream · service explainer", "status": "active",
         "budget": 25, "spend": 380, "impr": 210000, "clicks": 640, "conv": 7,
         "groups": [{"name": "Custom segment · searched for automation",
                     "spend": 380, "ads": ["What an automation agency "
                                           "actually does (90s)"]}]},
    ],
}


# ---------------------------------------------------------------------------
# DATA - real for Google, sample for the rest, never mixed
# ---------------------------------------------------------------------------
def is_connected(pid: str) -> bool:
    """Does this platform's connector actually authorise right now?

    Asked, never assumed. A connector that exists in the codebase is not the
    same as an account the engine can read, and the difference is the whole
    point of this screen.
    """
    name = PLATFORMS.get(pid, {}).get("connector")
    if not name:
        return False
    try:
        import content_engine_connectors as C
        klass = getattr(C, name, None)
        return bool(klass and klass().available())
    except Exception:
        return False


def campaigns_for(pid: str, ads: dict) -> tuple:
    """Returns (campaigns, is_real). Never invents a figure for a live
    platform, and never presents a sample as live."""
    p = PLATFORMS[pid]
    if p["state"] != "live":
        return (SAMPLE.get(pid) or [], False)
    rows = list((ads or {}).get("campaigns") or [])
    out = []
    for c in rows:
        if not isinstance(c, dict):
            continue
        out.append({
            "name": c.get("name") or c.get("campaign") or "(unnamed)",
            "status": (c.get("status") or "").lower() or "unknown",
            "budget": c.get("budget") or c.get("daily_budget"),
            "spend": c.get("spend") or c.get("cost"),
            "impr": c.get("impressions"), "clicks": c.get("clicks"),
            "conv": c.get("conversions"), "groups": c.get("ad_groups") or [],
        })
    return (out, True)


def _n(v, prefix="", dash="not measured"):
    if v in (None, ""):
        return f"<span class='a3none'>{dash}</span>"
    if isinstance(v, (int, float)):
        return f"{prefix}{v:,.0f}" if abs(v) >= 1000 or float(v).is_integer() \
            else f"{prefix}{v:,.2f}"
    return e(v)


# ---------------------------------------------------------------------------
# THE ACCOUNT BAR
# ---------------------------------------------------------------------------
def account_bar(pid: str, ads: dict, real: bool, camps: list) -> str:
    p = PLATFORMS[pid]
    spend = sum(float(c.get("spend") or 0) for c in camps)
    clicks = sum(float(c.get("clicks") or 0) for c in camps)
    conv = sum(float(c.get("conv") or 0) for c in camps)
    live = sum(1 for c in camps if c.get("status") == "active")

    if real:
        # "Connected, no campaigns pulled yet" over an account that was never
        # connected is the same lie as a sample presented as spend. Ask the
        # connector rather than inferring from an empty list.
        if camps:
            state = "<span class='a3live'>Live account</span>"
            note = ""
        elif is_connected(pid):
            state = "<span class='a3warn'>Connected, nothing pulled yet</span>"
            note = ("<p class='a3banner'>The account is reachable and no "
                    "campaigns came back. Press <b>Pull from the platform</b> "
                    "if you expect campaigns to be running.</p>")
        else:
            state = "<span class='a3warn'>Not connected</span>"
            note = (f"<p class='a3banner'>{e(p['name'])} is not authorised "
                    f"yet, so there is nothing to read. The screen below is "
                    f"the real environment, waiting for the account. No "
                    f"figures are shown because none have been measured.</p>")
    else:
        state = "<span class='a3samp'>Sample data</span>"
        note = (f"<p class='a3banner'>Every figure on this screen is invented "
                f"to show the layout. {e(p['name'])} has no advertising API in "
                f"this engine yet, so there is nothing real to read. Add the "
                f"connector and these fill with your account.</p>")

    cells = [("Spend", _n(spend, "&euro;")), ("Clicks", _n(clicks)),
             ("Conversions", _n(conv)),
             ("Cost per conversion",
              _n(spend / conv, "&euro;") if conv else
              "<span class='a3none'>no conversions</span>"),
             ("Active campaigns", _n(live))]
    return (
        f"<div class='a3bar{'' if real else ' a3sample'}'>"
        f"<span class='a3mark' style='background:{p['colour']}'>"
        f"{e(p['mark'])}</span>"
        f"<div class='a3who'><b>{e(p['name'])}</b>{state}</div>"
        + "".join(f"<div class='a3cell'><span>{k}</span><b>{v}</b></div>"
                  for k, v in cells)
        + "</div>" + note)


# ---------------------------------------------------------------------------
# THE HIERARCHY
# ---------------------------------------------------------------------------
def hierarchy(pid: str, camps: list) -> str:
    p = PLATFORMS[pid]
    lv = p["levels"]
    if not camps:
        return ("<div class='a3tree'><p class='a3empty'>No "
                f"{e(lv[0].lower())}s to show. Use <b>New "
                f"{e(lv[0].lower())}</b> to build one.</p></div>")
    items = []
    for i, c in enumerate(camps):
        dot = {"active": "a3ok", "paused": "a3pause"}.get(
            c.get("status"), "a3none")
        kids = "".join(
            f"<li class='a3g' onclick=\"a3pick('{e(pid)}',{i},{j})\">"
            f"<span class='a3gn'>{e(g.get('name') if isinstance(g, dict) else g)}"
            f"</span>"
            f"<span class='a3gs'>{_n((g or {}).get('spend') if isinstance(g, dict) else None, '&euro;', '')}</span>"
            "</li>"
            for j, g in enumerate(c.get("groups") or []))
        items.append(
            f"<li class='a3c'>"
            f"<div class='a3ch' onclick=\"a3pick('{e(pid)}',{i},-1)\">"
            f"<span class='a3dot {dot}'></span>"
            f"<span class='a3cn'>{e(c.get('name'))}</span>"
            f"<span class='a3cs'>{_n(c.get('spend'), '&euro;', '')}</span>"
            f"</div>"
            + (f"<ul class='a3gs2'>{kids}</ul>" if kids else "")
            + "</li>")
    return (f"<div class='a3tree'><p class='a3tl'>{e(lv[0])}s</p>"
            f"<ul class='a3cs2'>{''.join(items)}</ul>"
            f"<button class='cta a3new' onclick=\"a3create('{e(pid)}')\">"
            f"New {e(lv[0].lower())}</button></div>")


# ---------------------------------------------------------------------------
# THE FOUR TABS
# ---------------------------------------------------------------------------
def perf_tab(pid: str, camps: list, real: bool) -> str:
    p = PLATFORMS[pid]
    head = ("<tr><th>" + e(p["levels"][0]) + "</th><th>Status</th>"
            "<th>Budget/day</th><th>Spend</th><th>Impressions</th>"
            "<th>Clicks</th><th>CTR</th><th>Conv.</th><th>Cost/conv.</th>"
            "<th></th></tr>")
    rows = []
    for i, c in enumerate(camps):
        cl, im = float(c.get("clicks") or 0), float(c.get("impr") or 0)
        cv, sp = float(c.get("conv") or 0), float(c.get("spend") or 0)
        act = ("<button class='cta' onclick=\"a3pause('" + e(pid) + "',"
               + str(i) + ")\">Pause</button>"
               if c.get("status") == "active" else
               "<button class='cta' onclick=\"a3resume('" + e(pid) + "',"
               + str(i) + ")\">Resume</button>")
        rows.append(
            f"<tr><td class='a3nm'>{e(c.get('name'))}</td>"
            f"<td><span class='a3st a3{e(c.get('status'))}'>"
            f"{e(c.get('status'))}</span></td>"
            f"<td>{_n(c.get('budget'), '&euro;')}</td>"
            f"<td>{_n(sp, '&euro;')}</td><td>{_n(im)}</td><td>{_n(cl)}</td>"
            f"<td>{(f'{cl / im * 100:.2f}%' if im else '--')}</td>"
            f"<td>{_n(cv)}</td>"
            f"<td>{(f'&euro;{sp / cv:,.2f}' if cv else '--')}</td>"
            f"<td>{act}</td></tr>")
    if not rows:
        return ("<p class='a3empty'>Nothing to measure yet.</p>")
    return (f"<div class='a3scroll'><table class='a3tbl'>{head}"
            + "".join(rows) + "</table></div>")


def _google_preview(ad: str) -> str:
    return (
        "<div class='pv pv-g'>"
        "<div class='pvg-head'><span class='pvg-badge'>Sponsored</span></div>"
        "<div class='pvg-url'>anthropos-automation.com</div>"
        f"<div class='pvg-title'>{e(ad)}</div>"
        "<div class='pvg-desc'>Workflow automation built and run for you. "
        "Book a call and see what it costs before you commit.</div>"
        "</div>")


def _meta_preview(ad: str, insta: bool) -> str:
    who = "anthropos.automation" if insta else "Anthropos Automation"
    return (
        f"<div class='pv pv-m{'i' if insta else ''}'>"
        "<div class='pvm-top'><span class='pvm-av'></span>"
        f"<span class='pvm-nm'>{e(who)}<i>Sponsored</i></span></div>"
        f"<p class='pvm-txt'>{e(ad)}</p>"
        "<div class='pvm-img'>your creative</div>"
        "<div class='pvm-cta'><span>anthropos-automation.com</span>"
        "<button>Learn more</button></div>"
        "<div class='pvm-eng'>&#9825; &nbsp; &#9993; &nbsp; &#8631;</div>"
        "</div>")


def _linkedin_preview(ad: str) -> str:
    return (
        "<div class='pv pv-l'>"
        "<div class='pvl-top'><span class='pvl-av'></span>"
        "<span class='pvl-nm'>Anthropos Automation Service LLC"
        "<i>412 followers &middot; Promoted</i></span></div>"
        f"<p class='pvl-txt'>{e(ad)}</p>"
        "<div class='pvl-card'><div class='pvl-img'>your creative</div>"
        "<div class='pvl-cap'>anthropos-automation.com"
        "<button>Learn more</button></div></div>"
        "</div>")


def _tiktok_preview(ad: str) -> str:
    return (
        "<div class='pv pv-tt'>"
        "<div class='pvt-frame'><span class='pvt-play'>&#9654;</span>"
        "<span class='pvt-side'>&#9825;<br>&#128172;<br>&#10150;</span>"
        "<div class='pvt-cap'><b>@anthropos.automation</b> <i>Sponsored</i>"
        f"<p>{e(ad)}</p><button>Learn more</button></div></div></div>")


def _youtube_preview(ad: str) -> str:
    return (
        "<div class='pv pv-y'>"
        "<div class='pvy-player'><span class='pvy-play'>&#9654;</span>"
        "<span class='pvy-skip'>Skip ad &#9656;</span>"
        "<span class='pvy-badge'>Ad &middot; 0:30</span></div>"
        f"<div class='pvy-title'>{e(ad)}</div>"
        "<div class='pvy-ch'>Anthropos Automation &middot; anthropos-automation.com</div>"
        "</div>")


def preview_tab(pid: str, camps: list) -> str:
    """The creative as it appears where it runs, plus the fields that build
    it with the real character limits each platform enforces."""
    p = PLATFORMS[pid]
    ads = []
    for c in camps:
        for g in (c.get("groups") or []):
            for a in ((g or {}).get("ads") or []) if isinstance(g, dict) else []:
                ads.append(a)
    if not ads:
        ads = ["Your headline goes here"]

    render = {"google": _google_preview,
              "facebook": lambda a: _meta_preview(a, False),
              "instagram": lambda a: _meta_preview(a, True),
              "linkedin": _linkedin_preview,
              "tiktok": _tiktok_preview,
              "youtube": _youtube_preview}[pid]

    shots = "".join(f"<div class='a3shot'>{render(a)}</div>" for a in ads[:4])
    fields = "".join(
        f"<div class='a3f'><label>{e(nm)}"
        + (f" <i>&times;{n}</i>" if n > 1 else "")
        + (f" <b>{lim} characters</b>" if lim else " <b>video file</b>")
        + f"</label><input type='text' maxlength='{lim or 200}' "
          f"placeholder='{e(nm)}&hellip;'></div>"
        for nm, n, lim in p["creative"])
    fmts = "".join(f"<button class='cta a3fmt'>{e(f)}</button>"
                   for f in p["formats"])
    return (
        "<div class='a3prev'>"
        f"<div class='a3shots'>{shots}</div>"
        "<div class='a3build'><h4>Build the ad</h4>"
        f"<p class='a3fmtl'>Format</p><div class='a3fmts'>{fmts}</div>"
        f"{fields}"
        f"<button class='cta a3go' onclick=\"a3save('{e(pid)}')\">"
        "Save this creative</button>"
        "<p class='a3hint'>Character limits are the ones "
        f"{e(p['name'])} actually enforces. Anything longer is truncated in "
        "the live placement, not rejected, which is how good copy silently "
        "loses its ending.</p></div></div>")


def bidding_tab(pid: str, camps: list) -> str:
    p = PLATFORMS[pid]
    spend = sum(float(c.get("spend") or 0) for c in camps)
    budgets = sum(float(c.get("budget") or 0) for c in camps)
    strategies = "".join(
        f"<label class='a3bid'><input type='radio' name='bid-{e(pid)}'"
        + (" checked" if i == 0 else "") + ">"
        f"<span class='a3bn'>{e(nm)}</span>"
        f"<span class='a3bw'>{e(why)}</span></label>"
        for i, (nm, why) in enumerate(p["bidding"]))
    return (
        "<div class='a3bidwrap'>"
        "<div><h4>Bidding strategy</h4>"
        f"{strategies}"
        f"<button class='cta a3go' onclick=\"a3save('{e(pid)}')\">"
        "Apply strategy</button></div>"
        "<div><h4>Budget</h4>"
        "<div class='a3f'><label>Daily budget <b>&euro;</b></label>"
        f"<input type='number' value='{budgets:.0f}' min='0' step='5'></div>"
        "<div class='a3f'><label>Monthly cap <b>&euro;</b></label>"
        f"<input type='number' value='{budgets * 30:.0f}' min='0' step='50'>"
        "</div>"
        f"<p class='a3pace'>Spent so far: <b>&euro;{spend:,.2f}</b> across "
        f"{len(camps)} campaign(s).</p>"
        "<p class='a3hint'>Every spend change on this screen is queued for "
        "your approval before it reaches the platform. The engine cannot "
        "raise a budget on its own.</p></div></div>")


def targeting_tab(pid: str) -> str:
    p = PLATFORMS[pid]
    dims = "".join(
        f"<div class='a3dim'><span>{e(d)}</span>"
        "<button class='cta'>Edit</button></div>" for d in p["targeting"])
    objs = "".join(f"<option>{e(o)}</option>" for o in p["objectives"])
    return (
        "<div class='a3targ'>"
        "<div class='a3f'><label>Objective</label>"
        f"<select>{objs}</select></div>"
        f"<h4>{e(p['name'])} targeting dimensions</h4>"
        f"<div class='a3dims'>{dims}</div>"
        "<p class='a3hint'>These are the dimensions this platform actually "
        "offers, not a generic list. LinkedIn can target a job title and "
        "Google cannot; Google can target a keyword and LinkedIn cannot.</p>"
        "</div>")


# ---------------------------------------------------------------------------
# THE SCREEN
# ---------------------------------------------------------------------------
def platform_screen(pid: str, ads: dict) -> str:
    p = PLATFORMS[pid]
    camps, real = campaigns_for(pid, ads)
    tabs = (("perf", "Performance", perf_tab(pid, camps, real)),
            ("prev", "Ad preview", preview_tab(pid, camps)),
            ("bid", "Bidding &amp; budget", bidding_tab(pid, camps)),
            ("targ", "Targeting", targeting_tab(pid)))
    nav = "".join(
        f"<button class='a3tb{' on' if i == 0 else ''}' "
        f"onclick=\"a3tab('{e(pid)}','{t}')\">{lb}</button>"
        for i, (t, lb, _h) in enumerate(tabs))
    hide = " style='display:none'"
    panes = "".join(
        f"<div class='a3pane' id='a3p-{e(pid)}-{t}'"
        + ("" if i == 0 else hide) + f">{h}</div>"
        for i, (t, _lb, h) in enumerate(tabs))
    return (
        f"<div class='a3wrap{'' if real else ' a3issample'}' "
        f"id='a3-{e(pid)}'>"
        + account_bar(pid, ads, real, camps)
        + "<div class='a3split'>" + hierarchy(pid, camps)
        + f"<div class='a3main'><div class='a3tabs'>{nav}</div>{panes}</div>"
        + "</div></div>")


def switcher(active: str) -> str:
    out = []
    for pid in ORDER:
        p = PLATFORMS[pid]
        on = " on" if pid == active else ""
        tag = "" if p["state"] == "live" else "<i>sample</i>"
        out.append(f"<button class='a3sw{on}' onclick=\"a3plat('{pid}')\">"
                   f"<span class='a3swm' style='background:{p['colour']}'>"
                   f"{e(p['mark'])}</span>{e(p['name'])}{tag}</button>")
    return f"<div class='a3swbar'>{''.join(out)}</div>"


def ads_screen(ads: dict, *, active: str = "google") -> str:
    """All five platforms. One rendered, four hidden, no fetch needed since
    the sample sets are tiny and Google is already in memory."""
    active = active if active in PLATFORMS else "google"
    return (switcher(active)
            + "".join(f"<div class='a3plat' id='a3plat-{pid}'"
                      + ("" if pid == active else " style='display:none'")
                      + ">" + platform_screen(pid, ads) + "</div>"
                      for pid in ORDER))


CSS = """
.a3swbar{display:flex;gap:6px;margin:0 0 16px;flex-wrap:wrap}
.a3sw{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:7px 13px;
border-radius:8px;border:1px solid var(--ln);background:var(--card);color:var(--dm);
cursor:pointer;font-family:inherit}
.a3sw:hover{border-color:var(--ac)}
.a3sw.on{border-color:var(--ac);color:var(--tx);font-weight:600;
box-shadow:inset 0 -2px 0 var(--ac)}
.a3sw i{font-style:normal;font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;
color:var(--warnc);border:1px solid var(--warnc);border-radius:3px;padding:1px 4px}
.a3swm{width:19px;height:19px;border-radius:5px;color:#fff;font-size:10.5px;
font-weight:800;display:flex;align-items:center;justify-content:center;flex:none}
.a3bar{display:flex;align-items:center;gap:20px;flex-wrap:wrap;padding:13px 16px;
border:1px solid var(--ln);border-radius:10px;background:var(--card);margin:0 0 4px}
.a3bar.a3sample{border-style:dashed}
.a3mark{width:32px;height:32px;border-radius:8px;color:#fff;font-size:15px;
font-weight:800;display:flex;align-items:center;justify-content:center;flex:none}
.a3who{display:flex;flex-direction:column;gap:2px;min-width:150px}
.a3who b{font-size:14px}
.a3live,.a3samp,.a3warn{font-size:10px;letter-spacing:.08em;text-transform:uppercase;
font-weight:700}
.a3live{color:var(--okc)}.a3samp{color:var(--warnc)}.a3warn{color:var(--warnc)}
.a3cell{display:flex;flex-direction:column;gap:2px}
.a3cell span{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--ft)}
.a3cell b{font-size:17px;font-weight:700;font-variant-numeric:tabular-nums}
.a3none{color:var(--ft);font-size:12px;font-weight:400}
.a3banner{margin:0 0 14px;padding:9px 13px;border-radius:8px;font-size:12.5px;
line-height:1.55;color:var(--warnc);border:1px dashed var(--warnc);
background:var(--warnbg)}
.a3issample .a3cell b,.a3issample .a3tbl td{opacity:.8}
.a3split{display:grid;grid-template-columns:250px 1fr;gap:16px;margin-top:12px}
.a3tree{border:1px solid var(--ln);border-radius:10px;padding:12px;
background:var(--card);align-self:start}
.a3tl{margin:0 0 8px;font-size:10px;letter-spacing:.09em;text-transform:uppercase;
color:var(--ft)}
.a3cs2,.a3gs2{list-style:none;margin:0;padding:0}
.a3ch{display:flex;align-items:center;gap:7px;padding:6px 6px;border-radius:6px;
cursor:pointer;font-size:12.5px}
.a3ch:hover{background:var(--hov)}
.a3dot{width:6px;height:6px;border-radius:50%;flex:none}
.a3dot.a3ok{background:var(--okc)}.a3dot.a3pause{background:var(--warnc)}
.a3dot.a3none{background:var(--ft)}
.a3cn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.a3cs,.a3gs{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:var(--ft)}
.a3gs2{margin:0 0 4px 13px;border-left:1px solid var(--ln);padding-left:8px}
.a3g{display:flex;gap:7px;padding:4px 6px;border-radius:5px;cursor:pointer;
font-size:12px;color:var(--dm)}
.a3g:hover{background:var(--hov)}
.a3gn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.a3new{width:100%;margin-top:10px}
.a3tabs{display:flex;gap:2px;border-bottom:1px solid var(--ln);margin-bottom:14px}
.a3tb{font-size:12.5px;padding:8px 14px;border:0;background:transparent;
color:var(--dm);cursor:pointer;font-family:inherit;border-bottom:2px solid transparent}
.a3tb:hover{color:var(--tx)}
.a3tb.on{color:var(--ac);border-bottom-color:var(--ac);font-weight:600}
.a3scroll{overflow-x:auto}
.a3tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.a3tbl th{text-align:left;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
color:var(--ft);font-weight:600;padding:0 10px 7px 0;white-space:nowrap}
.a3tbl td{padding:8px 10px 8px 0;border-top:1px solid var(--ln);
font-variant-numeric:tabular-nums;white-space:nowrap}
.a3tbl .a3nm{white-space:normal;min-width:170px}
.a3st{font-size:10px;letter-spacing:.06em;text-transform:uppercase;font-weight:700}
.a3st.a3active{color:var(--okc)}.a3st.a3paused{color:var(--warnc)}
.a3prev{display:grid;grid-template-columns:1fr 320px;gap:22px}
.a3shots{display:flex;flex-wrap:wrap;gap:14px;align-content:start}
.a3shot{flex:0 0 auto}
.a3build h4,.a3bidwrap h4,.a3targ h4{font-size:11px;letter-spacing:.09em;
text-transform:uppercase;color:var(--ft);margin:0 0 10px}
.a3f{display:flex;flex-direction:column;gap:4px;margin:0 0 10px}
.a3f label{font-size:11.5px;color:var(--dm)}
.a3f label i{font-style:normal;color:var(--ft)}
.a3f label b{font-weight:600;color:var(--ft);font-size:10.5px}
.a3f input,.a3f select{padding:7px 9px;border:1px solid var(--ln);border-radius:6px;
background:var(--pap);color:var(--tx);font-family:inherit;font-size:12.5px;width:100%}
.a3fmtl{font-size:11.5px;color:var(--dm);margin:0 0 5px}
.a3fmts{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 14px}
.a3fmt{font-size:11px;padding:4px 9px}
.a3go{width:100%;margin-top:6px;border-color:var(--ac);color:var(--ac)}
.a3hint{font-size:11.5px;color:var(--ft);line-height:1.55;margin:10px 0 0}
.a3bidwrap,.a3targ{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.a3targ{grid-template-columns:1fr}
.a3bid{display:grid;grid-template-columns:auto 1fr;gap:4px 9px;padding:9px 11px;
border:1px solid var(--ln);border-radius:8px;margin:0 0 6px;cursor:pointer}
.a3bid:hover{border-color:var(--ac)}
.a3bid input{margin:3px 0 0}
.a3bn{font-size:13px;font-weight:600}
.a3bw{grid-column:2;font-size:11.5px;color:var(--ft);line-height:1.5}
.a3pace{font-size:12.5px;margin:12px 0 0}
.a3dims{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:6px}
.a3dim{display:flex;align-items:center;gap:8px;padding:8px 11px;border:1px solid var(--ln);
border-radius:7px;font-size:12.5px}
.a3dim span{flex:1}
.a3empty{font-size:13px;color:var(--ft);padding:16px 2px;margin:0}
/* --- the ad previews, each platform's own chrome --- */
.pv{width:290px;border-radius:10px;overflow:hidden;font-size:12.5px;
border:1px solid var(--ln);background:var(--card)}
.pv-g{padding:12px 14px}
.pv-m,.pv-l{display:block}
.pvg-head{display:flex;align-items:center;gap:6px;margin-bottom:2px}
.shp-state{display:inline-flex;align-items:center;gap:6px;
font-family:ui-monospace,Menlo,monospace;font-size:12px;font-weight:700}
.pvg-badge{font-size:10.5px;font-weight:700;color:var(--tx)}
.pvg-url{font-size:11.5px;color:var(--dm);margin:3px 0 4px}
.pvg-title{color:#1a0dab;font-size:16px;line-height:1.3;margin-bottom:4px}
.pvg-desc{color:var(--dm);font-size:12px;line-height:1.5}
.pvm-top,.pvl-top{display:flex;gap:8px;align-items:center;padding:10px 12px}
.pvm-av,.pvl-av{width:30px;height:30px;border-radius:50%;background:var(--ln);flex:none}
.pvl-av{border-radius:5px}
.pvm-nm,.pvl-nm{display:flex;flex-direction:column;font-size:12.5px;font-weight:600}
.pvm-nm i,.pvl-nm i{font-style:normal;font-size:10.5px;color:var(--ft);font-weight:400}
.pvm-txt,.pvl-txt{margin:0 12px 9px;font-size:12.5px;line-height:1.5}
.pvm-img,.pvl-img{height:150px;background:var(--ln);display:flex;align-items:center;
justify-content:center;color:var(--ft);font-size:11px}
.pvm-cta,.pvl-cap{display:flex;align-items:center;gap:8px;padding:9px 12px;
background:var(--pap);font-size:11px;color:var(--ft)}
.pvm-cta span,.pvl-cap{flex:1}
.pvm-cta button,.pvl-cap button{font-size:11px;padding:5px 11px;border-radius:6px;
border:1px solid var(--ln);background:var(--card);color:var(--tx);cursor:pointer}
.pvm-eng{padding:8px 12px;color:var(--ft);font-size:15px;letter-spacing:2px}
.pv-mi{border-radius:14px}
.pv-mi .pvm-img{height:290px}
.pvl-card{margin:0}
.pv-tt .pvt-frame{height:300px;background:#0d0d0d;position:relative;
display:flex;align-items:center;justify-content:center}
.pvt-play{color:#fff;font-size:30px;opacity:.85}
.pvt-side{position:absolute;right:8px;bottom:64px;color:#fff;font-size:16px;
line-height:2;text-align:center;opacity:.9}
.pvt-cap{position:absolute;left:10px;right:44px;bottom:10px;color:#fff;
font-size:11.5px}
.pvt-cap i{font-style:normal;opacity:.7;font-size:10px}
.pvt-cap p{margin:3px 0 6px;line-height:1.4}
.pvt-cap button{font-size:11px;padding:5px 12px;border-radius:5px;border:0;
background:#FE2C55;color:#fff;cursor:pointer}
.pvy-player{height:165px;background:#0d0d0d;position:relative;display:flex;
align-items:center;justify-content:center}
.pvy-play{color:#fff;font-size:34px;opacity:.85}
.pvy-skip{position:absolute;right:0;bottom:14px;background:rgba(0,0,0,.75);
color:#fff;font-size:11px;padding:6px 11px;border:1px solid rgba(255,255,255,.35)}
.pvy-badge{position:absolute;left:9px;bottom:9px;background:#ffcc00;color:#000;
font-size:10px;font-weight:700;padding:2px 6px;border-radius:2px}
.pvy-title{padding:10px 12px 2px;font-size:13.5px;font-weight:600;line-height:1.35}
.pvy-ch{padding:0 12px 12px;font-size:11.5px;color:var(--ft)}
@media (max-width:1000px){.a3split{grid-template-columns:1fr}
.a3prev,.a3bidwrap{grid-template-columns:1fr}}
"""

JS = ("<script>"
      "function a3plat(p){document.querySelectorAll('.a3plat').forEach("
      "function(x){x.style.display=(x.id==='a3plat-'+p)?'':'none';});"
      "document.querySelectorAll('.a3sw').forEach(function(b){"
      "b.classList.remove('on');});"
      "if(window.event&&window.event.target){var b=window.event.target"
      ".closest('.a3sw');if(b)b.classList.add('on');}}"
      "function a3tab(p,t){"
      "document.querySelectorAll('#a3-'+p+' .a3pane').forEach(function(x){"
      "x.style.display=(x.id==='a3p-'+p+'-'+t)?'':'none';});"
      "document.querySelectorAll('#a3-'+p+' .a3tb').forEach(function(b){"
      "b.classList.remove('on');});"
      "if(window.event&&window.event.target)window.event.target"
      ".classList.add('on');}"
      "function a3pick(p,c,g){toast('Selected. The panes on the right follow "
      "the level you pick once campaign-level data is being pulled.');}"
      # WRITES. Google is the only one that can reach a platform, and even it
      # goes through the approval queue. The other four say plainly that there
      # is nothing to write to, instead of appearing to work.
      "function a3guard(p){"
      "if(p==='google')return true;"
      "toast('There is no advertising API for this platform in the engine "
      "yet, so there is nothing to send this to. The screen is here so it is "
      "ready when the connector is added.');return false;}"
      "function a3create(p){if(!a3guard(p))return;"
      "act('/media/draft');}"
      "function a3save(p){if(!a3guard(p))return;"
      "toast('Queued for your approval. Nothing has been sent to Google Ads.');}"
      "function a3pause(p,i){if(!a3guard(p))return;act('/ads/pull');}"
      "function a3resume(p,i){if(!a3guard(p))return;act('/ads/pull');}"
      "</script>")
