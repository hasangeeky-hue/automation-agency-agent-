"""
content_engine_sga_screens.py
============================================================================
THE SOCIAL ANALYTICS SCREENS, METRICOOL GRAMMAR. Fourteen panels replacing
250 cards: an overview band, a per-channel analytics environment behind one
switcher, and the screens that already run on live data - traffic, revenue,
calendar, creative, blog, budget.

THE ONE RULE HERE
  A tile shows a NUMBER only when something measured it. A channel with no
  read key shows every slot present and the exact missing setting named -
  never a zero, because zero is a measurement and an absent API is not.

RENDERER ONLY. Draws; never fetches, spends, publishes or writes. All ids
are scoped "sg-" because the old dashboard renders every panel at once.
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_charts as CH
import content_engine_social_insights as SI


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def _num(v) -> str:
    """A measurement, or an honest dash. Never a zero standing in for
    'we could not measure this'."""
    if v is None or v == "":
        return "<b class='sg-none'>--</b>"
    try:
        f = float(v)
        if abs(f) >= 1_000_000:
            s = f"{f/1_000_000:.1f}M"
        elif abs(f) >= 1000:
            s = f"{f/1000:.1f}k"
        else:
            s = f"{f:,.0f}" if f == int(f) else f"{f:,.1f}"
    except Exception:
        s = str(v)
    return f"<b>{e(s)}</b>"


def tile(label, value, sub="") -> str:
    return ("<div class='sg-tile'><span class='sg-k'>" + e(label) + "</span>"
            + _num(value)
            + (f"<span class='sg-d'>{e(sub)}</span>" if sub else "")
            + "</div>")


def tiles(rows) -> str:
    return ("<div class='sg-tiles'>"
            + "".join(tile(*r) for r in rows) + "</div>")


def chart(title, svg, empty="") -> str:
    """A chart with a real title, or an honest empty state in its place.
    A blank frame with no explanation is how a dashboard lies quietly."""
    body = svg or f"<p class='sg-empty'>{e(empty or 'Nothing measured yet.')}</p>"
    return (f"<div class='sg-chart'><p class='sg-ct'>{e(title)}</p>{body}</div>")


def _snap(ctx) -> dict:
    s = (ctx.get("social") if isinstance(ctx, dict) else None) or {}
    return s if isinstance(s, dict) else {}


def _channels(ctx) -> dict:
    """The per-channel map, whatever shape the store really held. A stored
    snapshot from an older build can be a string or a list; a screen that
    trusts its shape is a screen that blanks the section."""
    ch = _snap(ctx).get("channels")
    return ch if isinstance(ch, dict) else {}


def _hist(ctx) -> list:
    h = (ctx.get("social_history") if isinstance(ctx, dict) else None) or []
    return [x for x in h if isinstance(x, dict)] if isinstance(h, list) else []


def _chan(ctx, cid) -> dict:
    ch = _channels(ctx).get(cid)
    return ch if isinstance(ch, dict) else SI._blank(cid, SI.reason_for(cid))


def _all_posts(ctx) -> list:
    """Every measured post across every reporting channel, newest first.
    Falls back to your own publishing log for channels that cannot report,
    so the table is never empty while you are publishing."""
    rows = []
    for cid, c in _channels(ctx).items():
        for r in (c.get("posts_rows") or []):
            if isinstance(r, dict):
                rows.append(dict(r, channel=r.get("channel") or cid))
    if not rows:
        own = (ctx.get("posts") or {})
        own = own.get("rows") if isinstance(own, dict) else None
        rows = [r for r in (own or []) if isinstance(r, dict)]
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows


def _best_time(ctx) -> dict:
    """The strongest per-channel heatmap, or the pooled one. Computed from
    real posts by the socket - never a decorative grid."""
    best = {}
    for c in _channels(ctx).values():
        bt = c.get("best_time") or {}
        if isinstance(bt, dict) and bt.get("grid") and \
                bt.get("posts", 0) > best.get("posts", 0):
            best = bt
    if best:
        return best
    return SI.best_time(_all_posts(ctx))


def _demo(ctx) -> dict:
    """Demographics merged across channels that report them."""
    out = {}
    for cid, c in _channels(ctx).items():
        d = c.get("demographics") or {}
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if isinstance(v, dict) and v:
                bag = out.setdefault(k, {})
                for kk, vv in v.items():
                    try:
                        bag[kk] = bag.get(kk, 0) + float(vv or 0)
                    except Exception:
                        continue
    return out


def _inbox(ctx) -> list:
    rows = []
    for cid, c in _channels(ctx).items():
        for m in (c.get("inbox") or []):
            if isinstance(m, dict):
                rows.append(dict(m, channel=m.get("channel") or cid))
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows


# ---------------------------------------------------------------------------
# THE COMMAND BAND
# ---------------------------------------------------------------------------
def band(ctx) -> str:
    snap = _snap(ctx)
    live = [c for c in (snap.get("live") or []) if isinstance(c, str)] if isinstance(snap.get("live"), list) else []
    at = snap.get("at") or ""
    dots = "".join(
        "<span class='sg-dot' style='background:"
        + (SI.COLOUR[c] if c in live else "var(--ft)") + "' title='"
        + e(SI.NAME[c]) + "'></span>" for c in SI.ORDER)
    return (
        "<div class='s3band'><div class='s3who'>"
        "<p class='s3k'>Social analytics</p>"
        f"<p class='s3state'><b>{len(live)} of {len(SI.ORDER)} channels "
        f"reporting</b>"
        + (f" &middot; refreshed {e(str(at)[:16])}" if at
           else " &middot; never refreshed")
        + f"</p><p class='sg-dots'>{dots}</p>"
        "<p class='s3sub'>Your posting connectors can only WRITE. Followers, "
        "reach, impressions and engagement live behind each platform's "
        "insights API; a channel lights up the day its key is on Connect, "
        "and shows nothing rather than zeros until then.</p></div>"
        "<div class='s3cmds'>"
        "<button class='cta s3go' onclick=\"act('/social/refresh')\">"
        "Refresh all channels</button>"
        "<button class='cta' onclick=\"act('/insights/refresh')\">"
        "Refresh GA4</button>"
        "<button class='cta' onclick=\"nav('map')\">Add a channel key"
        "</button></div></div>")


# ---------------------------------------------------------------------------
# 1 OVERVIEW
# ---------------------------------------------------------------------------
def overview(ctx) -> str:
    snap = _snap(ctx)
    chans = _channels(ctx)
    tot = {s: None for s in SI.SLOTS}
    for s in SI.SLOTS:
        vals = [c.get(s) for c in chans.values()
                if isinstance(c, dict) and c.get(s) is not None]
        tot[s] = sum(float(v) for v in vals) if vals else None
    posts = (ctx.get("posts") or {})
    n_posts = posts.get("total") if isinstance(posts, dict) else None
    live = [c for c in (snap.get("live") or []) if isinstance(c, str)] if isinstance(snap.get("live"), list) else []
    top = max((c for c in chans.values()
               if isinstance(c, dict) and c.get("followers") is not None),
              key=lambda c: float(c["followers"]), default=None)

    t = tiles([("Followers", tot["followers"], "across all channels"),
               ("Reach", tot["reach"], "30 days"),
               ("Impressions", tot["impressions"], "30 days"),
               ("Engagement", tot["engagement"], "likes + comments + shares"),
               ("Clicks", tot["clicks"], "to your site"),
               ("Posts published", n_posts, "from your own log"),
               ("Channels reporting", len(live), f"of {len(SI.ORDER)}"),
               ("Biggest channel",
                (top or {}).get("followers"),
                (top or {}).get("name") or "needs a key")])

    hist = _hist(ctx)
    series = []
    for cid in SI.ORDER:
        ys = [float(h[cid]) for h in hist if isinstance(h, dict) and h.get(cid)]
        if len(ys) >= 2:
            series.append((SI.NAME[cid], ys, SI.COLOUR[cid]))
    growth = chart(
        "Follower growth", CH.lines(series) if series else "",
        "No follower history yet. It builds one row a day from the moment a "
        "channel's key is connected.")

    segs = [(SI.NAME[c], float(v.get("engagement") or 0), SI.COLOUR[c])
            for c, v in chans.items()
            if isinstance(v, dict) and v.get("engagement")]
    mix = chart("Engagement by channel",
                CH.ring(segs[:5], center="mix") if segs else "",
                "No engagement measured yet - each channel's insights key "
                "fills its slice.")
    return band(ctx) + t + "<div class='sg-row'>" + growth + mix + "</div>"


# ---------------------------------------------------------------------------
# 2 CHANNELS - the per-channel environment behind one switcher
# ---------------------------------------------------------------------------
def channel_panel(ctx, cid) -> str:
    c = _chan(ctx, cid)
    live = bool(c.get("connected"))
    head = (f"<div class='sg-head' style='border-left:3px solid "
            f"{SI.COLOUR[cid]}'>"
            f"<span class='sg-mark' style='background:{SI.COLOUR[cid]}'>"
            f"{e(SI.MARK[cid])}</span>"
            f"<b>{e(SI.NAME[cid])}</b>"
            + ("<span class='sg-live'>reporting</span>" if live
               else "<span class='sg-off'>no analytics key</span>")
            + "</div>")
    why = ("" if live else
           f"<div class='s3banner'>{e(c.get('reason'))}</div>")
    t = tiles([("Followers", c.get("followers"), ""),
               ("Reach", c.get("reach"), "30 days"),
               ("Impressions", c.get("impressions"), "30 days"),
               ("Engagement", c.get("engagement"), ""),
               ("Clicks", c.get("clicks"), ""),
               ("Posts", c.get("posts"), "")])
    hist = _hist(ctx)
    ys = [float(h[cid]) for h in hist if isinstance(h, dict) and h.get(cid)]
    growth = chart("Followers over time",
                   CH.lines([(SI.NAME[cid], ys, SI.COLOUR[cid])])
                   if len(ys) >= 2 else "",
                   "Fills one point a day once this channel reports.")
    r = c.get("reactions") or {}
    segs = [(k.title(), float(v or 0), col) for (k, v), col in
            zip(r.items(), ("#1B57F0", "#7A9BE8", "#B9C6EE", "#DDE3F5"))
            if v]
    mix = chart("Reaction mix", CH.ring(segs[:4], center="") if segs else "",
                "Likes, comments and shares arrive with this channel's "
                "insights key.")
    bars = chart(
        "Reach vs impressions",
        CH.vbars(["30 days"],
                 [("Reach", [float(c.get("reach") or 0)], "#1B57F0"),
                  ("Impressions", [float(c.get("impressions") or 0)],
                   "#7A9BE8")])
        if (c.get("reach") or c.get("impressions")) else "",
        "Both arrive with the insights key.")
    return (head + why + t
            + "<div class='sg-row'>" + growth + mix + "</div>"
            + "<div class='sg-row'>" + bars + "</div>")


def channels_screen(ctx) -> str:
    sw = "".join(
        f"<button class='a3sw{' on' if i == 0 else ''}' "
        f"onclick=\"sgChan('{cid}')\">"
        f"<span class='a3swm' style='background:{SI.COLOUR[cid]}'>"
        f"{e(SI.MARK[cid])}</span>{e(SI.NAME[cid])}"
        + ("" if _chan(ctx, cid).get("connected") else "<i>no key</i>")
        + "</button>" for i, cid in enumerate(SI.ORDER))
    panels = "".join(
        f"<div class='sg-cp' id='sg-c-{cid}'"
        + ("" if i == 0 else " style='display:none'") + ">"
        + channel_panel(ctx, cid) + "</div>"
        for i, cid in enumerate(SI.ORDER))
    return (band(ctx) + f"<div class='a3swbar'>{sw}</div>" + panels)


# ---------------------------------------------------------------------------
# 3-6 ENGAGEMENT / AUDIENCE / POSTS / PAID
# ---------------------------------------------------------------------------
def engagement_screen(ctx) -> str:
    chans = _channels(ctx)
    likes = comments = shares = None
    for c in chans.values():
        r = (c or {}).get("reactions") or {}
        for key, acc in (("likes", "likes"), ("comments", "comments"),
                         ("shares", "shares")):
            if r.get(key) is not None:
                v = float(r[key])
                if acc == "likes":
                    likes = (likes or 0) + v
                elif acc == "comments":
                    comments = (comments or 0) + v
                else:
                    shares = (shares or 0) + v
    tot = None
    if any(x is not None for x in (likes, comments, shares)):
        tot = (likes or 0) + (comments or 0) + (shares or 0)
    t = tiles([("Total engagement", tot, ""), ("Likes", likes, ""),
               ("Comments", comments, ""), ("Shares", shares, "")])
    segs = [(k, float(v), col) for (k, v), col in
            zip((("Likes", likes), ("Comments", comments), ("Shares", shares)),
                ("#1B57F0", "#7A9BE8", "#B9C6EE")) if v]
    donut = chart("Reaction mix", CH.ring(segs, center="") if segs else "",
                  "No reactions measured. Each channel's insights key adds "
                  "its own.")
    per = [(SI.NAME[c], [float((v or {}).get("engagement") or 0)],
            SI.COLOUR[c]) for c, v in chans.items()
           if (v or {}).get("engagement")]
    bars = chart("Engagement by channel",
                 CH.vbars(["30 days"], per[:5]) if per else "",
                 "Fills as channels report.")
    inbox = _inbox(ctx)
    ibx = ""
    if inbox:
        ibx = ("<p class='s3k' style='margin-top:14px'>Comments waiting on a "
               f"reply &middot; {len(inbox)}</p><div class='sg-tbl'>"
               + "".join(
                   "<div class='sg-tr'>"
                   f"<span>{e(str(m.get('at'))[:16])}</span>"
                   f"<span>{e(SI.NAME.get(m.get('channel'), m.get('channel')))}</span>"
                   f"<span>{e(m.get('who'))}</span>"
                   f"<span>{e(m.get('text'))[:70]}</span></div>"
                   for m in inbox[:25]) + "</div>"
               "<p class='sg-empty'>Replying happens on the platform: the "
               "engine reads comments, and never answers as you without "
               "your words.</p>")
    else:
        ibx = ("<p class='s3k' style='margin-top:14px'>Social inbox</p>"
               "<p class='sg-empty'>Comments arrive here once Facebook or "
               "Instagram is connected. Your reply agent handles email; this "
               "is the social side, read-only by design.</p>")
    return t + "<div class='sg-row'>" + donut + bars + "</div>" + ibx


def audience_screen(ctx) -> str:
    chans = _channels(ctx)
    fol = [float(c["followers"]) for c in chans.values()
           if isinstance(c, dict) and c.get("followers") is not None]
    hist = _hist(ctx)
    net = None
    if len(hist) >= 2:
        first = sum(float(v) for k, v in hist[0].items() if k != "date")
        last = sum(float(v) for k, v in hist[-1].items() if k != "date")
        net = last - first
    t = tiles([("Total followers", sum(fol) if fol else None, ""),
               ("Channels reporting", len(fol) or None,
                f"of {len(SI.ORDER)}"),
               ("Days of history", len(hist) or None, "one row a day"),
               ("Net growth", net,
                "since the first recorded day" if net is not None
                else "needs two days of history")])
    series = []
    for cid in SI.ORDER:
        ys = [float(h[cid]) for h in hist if isinstance(h, dict) and h.get(cid)]
        if len(ys) >= 2:
            series.append((SI.NAME[cid], ys, SI.COLOUR[cid]))
    growth = chart("Follower growth", CH.lines(series) if series else "",
                   "Builds one point a day per connected channel.")
    bt = _best_time(ctx)
    heat = chart(
        "Best time to post"
        + (f" &middot; from {bt['posts']} posts" if bt.get("posts") else ""),
        CH.heatmap(bt["rows"], bt["cols"], bt["grid"]) if bt.get("grid") else "",
        "Computed from your posts' own engagement. It fills as soon as a "
        "channel reports per-post metrics.")
    d = _demo(ctx)
    demo_charts = []
    for key, title, cols in (
            ("age", "Age", ("#1B57F0", "#7A9BE8", "#B9C6EE", "#DDE3F5",
                            "#EEF1FA")),
            ("gender", "Gender", ("#1B57F0", "#C13584", "#9AA0A5")),
            ("country", "Top countries", ("#1B57F0", "#7A9BE8", "#B9C6EE",
                                          "#DDE3F5", "#EEF1FA")),
            ("seniority", "Seniority", ("#0A66C2", "#4E8FD1", "#8FB8E3",
                                        "#C4D9F0", "#E3EDF9"))):
        v = d.get(key) or {}
        top5 = sorted(v.items(), key=lambda kv: -kv[1])[:5]
        segs = [(str(k), float(n), c) for (k, n), c in zip(top5, cols) if n]
        if segs:
            demo_charts.append(chart(title, CH.ring(segs, center="")))
    if not demo_charts:
        demo_charts = [chart(
            "Who follows you", "",
            "Age, gender, country and seniority come from Meta and LinkedIn "
            "once their keys are on Connect. Nothing is estimated here.")]
    return (t + "<div class='sg-row'>" + growth + heat + "</div>"
            + "<div class='sg-row'>" + "".join(demo_charts[:2]) + "</div>"
            + ("<div class='sg-row'>" + "".join(demo_charts[2:4]) + "</div>"
               if len(demo_charts) > 2 else ""))


def posts_screen(ctx) -> str:
    """The Metricool post table: every post, its channel, its own metrics.
    A column a channel cannot measure shows a dash on that row, never a 0."""
    rows = _all_posts(ctx)
    measured = [r for r in rows if r.get("engagement") is not None]
    by_ch, by_fmt = {}, {}
    for r in rows:
        by_ch[r.get("channel") or "?"] = by_ch.get(r.get("channel") or "?", 0) + 1
        f = str(r.get("format") or "post").lower()
        by_fmt[f] = by_fmt.get(f, 0) + 1
    top = max(measured, key=lambda r: float(r["engagement"]), default=None)
    t = tiles([("Posts", len(rows) or None, "newest first"),
               ("With measured metrics", len(measured) or None,
                "needs each channel's key"),
               ("Channels", len(by_ch) or None, ""),
               ("Best post", (top or {}).get("engagement"),
                (top or {}).get("title", "")[:28] if top else "none measured")])
    segs = [(k, float(v), c) for (k, v), c in
            zip(sorted(by_fmt.items(), key=lambda kv: -kv[1])[:5],
                ("#1B57F0", "#7A9BE8", "#B9C6EE", "#DDE3F5", "#EEF1FA"))]
    donut = chart("Format mix", CH.ring(segs, center="") if segs else "",
                  "No posts on record yet.")
    if not rows:
        return (t + donut + "<p class='sg-empty'>No posts on record. Every "
                "piece the engine publishes lands here, and its real metrics "
                "arrive with that channel's key.</p>")
    body = ("<div class='sg-tbl'><div class='sg-tr sg-th'>"
            "<span>When</span><span>Channel</span><span>Post</span>"
            "<span>Likes</span><span>Comments</span><span>Shares</span>"
            "<span>Reach</span><span>Engagement</span></div>"
            + "".join(
                "<div class='sg-tr'>"
                f"<span>{e(str(r.get('at'))[:16])}</span>"
                f"<span>{e(SI.NAME.get(r.get('channel'), r.get('channel')))}</span>"
                f"<span>{e(r.get('title') or r.get('piece'))[:46]}</span>"
                f"<span>{_num(r.get('likes'))}</span>"
                f"<span>{_num(r.get('comments'))}</span>"
                f"<span>{_num(r.get('shares'))}</span>"
                f"<span>{_num(r.get('reach') or r.get('impressions'))}</span>"
                f"<span>{_num(r.get('engagement'))}</span></div>"
                for r in rows[:50]) + "</div>")
    more = ("" if len(rows) <= 50 else
            f"<p class='sg-empty'>and {len(rows) - 50} more</p>")
    return t + donut + body + more


def paid_screen(ctx) -> str:
    paid = ctx.get("paid") or {}
    paid = paid if isinstance(paid, dict) else {}
    by = paid.get("by_platform")
    by = by if isinstance(by, list) else []
    per = {}
    for cid, c in _channels(ctx).items():
        pd = c.get("paid") or {}
        if isinstance(pd, dict) and any(v is not None for v in pd.values()):
            per[cid] = pd
    spend = paid.get("spend")
    cpm = cpc = cpr = None
    if per:
        def _avg(k):
            vals = [float(v[k]) for v in per.values() if v.get(k) is not None]
            return sum(vals) / len(vals) if vals else None
        cpm, cpc, cpr = _avg("cpm"), _avg("cpc"), _avg("cost_per_result")
    t = tiles([("Paid social spend", spend, "30 days"),
               ("Planned campaigns", paid.get("planned_count"), ""),
               ("Planned budget", paid.get("planned_budget"), "&euro;"),
               ("CPM", cpm, "needs each platform's ads key"
                if cpm is None else "average across channels"),
               ("CPC", cpc, "needs each platform's ads key"
                if cpc is None else "average across channels"),
               ("Cost per result", cpr, "needs each platform's ads key"
                if cpr is None else "average across channels")])
    rows = ""
    if per:
        rows = ("<div class='sg-tbl'><div class='sg-tr sg-th'>"
                "<span>Channel</span><span>Spend</span><span>CPM</span>"
                "<span>CPC</span><span>Cost/result</span></div>"
                + "".join(
                    "<div class='sg-tr'>"
                    f"<span>{e(SI.NAME.get(cid, cid))}</span>"
                    f"<span>{_num(v.get('spend'))}</span>"
                    f"<span>{_num(v.get('cpm'))}</span>"
                    f"<span>{_num(v.get('cpc'))}</span>"
                    f"<span>{_num(v.get('cost_per_result'))}</span></div>"
                    for cid, v in per.items()) + "</div>")
    bars = chart(
        "Spend by platform",
        CH.vbars(["30 days"],
                 [(str(r.get("platform")), [float(r.get("spend") or 0)],
                   SI.COLOUR.get(str(r.get("platform")).lower(), "#1B57F0"))
                  for r in by[:5] if isinstance(r, dict)])
        if by else "",
        "Paid social spend arrives with each platform's ADS key, which is "
        "separate from its analytics key. Google Ads has its own section "
        "under Media Buying.")
    return t + rows + bars


def traffic_screen(ctx) -> str:
    tr = ctx.get("traffic") or {}
    chans = tr.get("channels") if isinstance(tr, dict) else None
    chans = chans if isinstance(chans, list) else []
    t = tiles([("Social sessions", tr.get("social_sessions"), "GA4, 28 days"),
               ("All sessions", tr.get("total_sessions"), "GA4"),
               ("Social share", tr.get("social_share"), "of all traffic"),
               ("Sessions per post", tr.get("sessions_per_post"), ""),
               ("Channels sending", len(chans) or None, "")])
    segs = [(str(c.get("channel")), float(c.get("sessions") or 0),
             SI.COLOUR.get(str(c.get("channel")).lower(), "#7A9BE8"))
            for c in chans[:5] if isinstance(c, dict) and c.get("sessions")]
    donut = chart("Sessions by social channel",
                  CH.ring(segs, center="GA4") if segs else "",
                  "GA4 has recorded no social sessions in the window yet.")
    bars = chart("Sessions by channel",
                 CH.vbars([str(c.get("channel")) for c in chans[:6]
                           if isinstance(c, dict)],
                          [("Sessions", [float(c.get("sessions") or 0)
                                         for c in chans[:6]
                                         if isinstance(c, dict)], "#1B57F0")])
                 if chans else "", "Fills from GA4.")
    return t + "<div class='sg-row'>" + donut + bars + "</div>"


def revenue_screen(ctx) -> str:
    rv = ctx.get("revenue") or {}
    t = tiles([("Revenue from social", rv.get("revenue"), "&euro;"),
               ("Deals", rv.get("deals"), ""),
               ("Revenue per post", rv.get("revenue_per_post"), "&euro;"),
               ("Share of revenue", rv.get("share_of_revenue"), ""),
               ("ROI", rv.get("roi"), "")])
    wf = ""
    steps = rv.get("waterfall") if isinstance(rv, dict) else None
    if isinstance(steps, list) and steps:
        try:
            wf = CH.waterfall([(str(s[0]), float(s[1])) for s in steps
                               if isinstance(s, (list, tuple)) and len(s) >= 2])
        except Exception:
            wf = ""
    return (t + chart("From post to money", wf,
                      "Fills once a deal is attributed to a social touch.")
            + ("<p class='sg-empty'>No social-attributed revenue yet. A deal "
               "counts here when its lead carries a social source.</p>"
               if not rv.get("has_data") else ""))


def calendar_screen(ctx) -> str:
    cal = ctx.get("calendar") or {}
    rows = cal.get("rows") if isinstance(cal, dict) else None
    rows = rows if isinstance(rows, list) else []
    t = tiles([("Scheduled", len(rows) or None, "pieces"),
               ("Campaigns", len(ctx.get("campaigns") or []) or None, ""),
               ("Cadence target", (ctx.get("cadence") or {}).get("target"),
                "per channel per week")])
    body = ("".join(
        "<div class='sg-tr'>"
        f"<span>{e(str(r.get('date'))[:10])}</span>"
        f"<span>{e(r.get('channel'))}</span>"
        f"<span>{e(r.get('title'))[:60]}</span></div>"
        for r in rows[:40] if isinstance(r, dict))
        if rows else "<p class='sg-empty'>Nothing scheduled. Plan a campaign "
                     "and its pieces appear here by date.</p>")
    return (t + "<div class='sg-tbl'>" + body + "</div>"
            + "<button class='cta s3go' onclick='sgaCampaign()'>Plan a "
              "campaign</button>")


def creative_screen(ctx) -> str:
    cr = ctx.get("creatives") or {}
    rows = cr.get("rows") if isinstance(cr, dict) else None
    rows = rows if isinstance(rows, list) else []
    t = tiles([("Creatives", cr.get("total") if isinstance(cr, dict) else len(rows) or None, ""),
               ("Used in posts", cr.get("used") if isinstance(cr, dict) else None, ""),
               ("Unused", cr.get("unused") if isinstance(cr, dict) else None, "")])
    return t + ("<p class='sg-empty'>No creative on record yet.</p>"
                if not rows else
                "<div class='sg-tbl'>" + "".join(
                    f"<div class='sg-tr'><span>{e(r.get('title'))[:60]}</span>"
                    f"<span>{e(r.get('kind'))}</span>"
                    f"<span>{_num(r.get('uses'))}</span></div>"
                    for r in rows[:30] if isinstance(r, dict)) + "</div>")


def blog_screen(ctx) -> str:
    bl = ctx.get("blog") or {}
    t = tiles([("Long-form published", bl.get("total"), ""),
               ("Pushed to social", bl.get("pushed"), ""),
               ("Clicks from search", bl.get("clicks"), "GSC"),
               ("Impressions", bl.get("impressions"), "GSC")])
    return t + ("<p class='sg-empty'>Long-form cadence and its search "
                "performance fill from your publishing log and Search "
                "Console.</p>" if not bl.get("total") else "")


def budget_screen(ctx) -> str:
    b = ctx.get("budget") or {}
    t = tiles([("Month cap", b.get("cap"), "&euro;"),
               ("Spent", b.get("spent"), "&euro;"),
               ("Organic cost", b.get("organic"), "&euro;"),
               ("Paid social", b.get("paid"), "&euro;"),
               ("Headroom", b.get("headroom"), "&euro;")])
    ser = ctx.get("cost_series") or []
    ys = [float(x) for x in ser if isinstance(x, (int, float))]
    return t + chart("Cost over time",
                     CH.lines([("Cost", ys, "#1B57F0")]) if len(ys) >= 2 else "",
                     "Builds as the engine records its own spend.")


def targeting_screen(ctx) -> str:
    rows = "".join(
        f"<div class='sg-tr'><span><b>{e(SI.NAME[cid])}</b></span>"
        f"<span>{e(', '.join(_TARGETING.get(cid, ())))}</span></div>"
        for cid in SI.ORDER)
    comps = ctx.get("competitors") or []
    comps = [c for c in comps if isinstance(c, dict)]
    add = ("<div class='sg-add'>"
           "<select id='sg-cc'>"
           + "".join(f"<option value='{cid}'>{e(SI.NAME[cid])}</option>"
                     for cid in SI.ORDER)
           + "</select>"
           "<input id='sg-ch' placeholder='their handle, e.g. rival.io'>"
           "<button class='cta s3go' onclick='sgAddComp()'>Track</button>"
           "</div>")
    if comps:
        crows = ("<div class='sg-tbl'><div class='sg-tr sg-th'>"
                 "<span>Channel</span><span>Who</span><span>Followers</span>"
                 "<span>Posts</span><span>Engagement</span><span></span></div>"
                 + "".join(
                     "<div class='sg-tr'>"
                     f"<span>{e(SI.NAME.get(c.get('channel'), c.get('channel')))}</span>"
                     f"<span>{e(c.get('handle'))}</span>"
                     f"<span>{_num(c.get('followers'))}</span>"
                     f"<span>{_num(c.get('posts'))}</span>"
                     f"<span>{_num(c.get('engagement'))}</span>"
                     f"<span><button class='cta' onclick=\"sgDropComp("
                     f"'{e(c.get('channel'))}','{e(c.get('handle'))}')\">"
                     f"Stop</button></span></div>" for c in comps[:25])
                 + "</div>"
                 "<p class='sg-empty'>A rival's numbers are read by the same "
                 "channel key that reads yours; until that key is on Connect "
                 "these stay blank rather than guessed.</p>")
    else:
        crows = ("<p class='sg-empty'>No rivals tracked. Name one and the "
                 "engine watches its public profile with the same key that "
                 "reads your own channel.</p>")
    return ("<p class='s3k'>Who each channel can reach</p>"
            "<div class='sg-tbl'>" + rows + "</div>"
            "<p class='sg-empty'>These are the dimensions each platform "
            "really offers. Saved audiences arrive with each channel's "
            "key.</p>"
            f"<p class='s3k' style='margin-top:16px'>Competitors &middot; "
            f"{len(comps)} tracked</p>" + add + crows)



_TARGETING = {
    "facebook": ("Location", "Age", "Gender", "Interests", "Behaviours",
                 "Custom audiences", "Lookalikes"),
    "instagram": ("Location", "Age", "Gender", "Interests", "Custom "
                  "audiences", "Lookalikes"),
    "linkedin": ("Job title", "Job function", "Seniority", "Company size",
                 "Industry", "Skills", "Years of experience"),
    "tiktok": ("Location", "Age", "Interests", "Behaviours", "Hashtag "
               "interactions", "Device"),
    "x": ("Keywords", "Interests", "Followers of", "Location", "Device"),
    "youtube": ("Demographics", "Interests", "Custom segments", "Life "
                "events", "Placements", "Topics"),
    "gbp": ("Local radius", "Service areas", "Categories"),
}


def hub_screen(ctx) -> str:
    h = ctx.get("hub") or {}
    t = tiles([("Sheets rows", h.get("sheet_rows"), ""),
               ("Drive files", h.get("drive_files"), ""),
               ("GA4", "live" if h.get("ga4") else None, ""),
               ("Search Console", "live" if h.get("gsc") else None, ""),
               ("Emails sent", h.get("emails_sent"), ""),
               ("Jobs recorded", h.get("jobs"), "")])
    return ("<p class='s3k'>The Google data hub</p>" + t
            + "<p class='sg-empty'>Sheets is the dashboard and store, Drive "
              "holds the content JSON, GA4 and Search Console are the "
              "engine's eyes. All four ride one service account.</p>")


# ---------------------------------------------------------------------------
def build_panels(ctx) -> dict:
    """tab id -> screen html. THE one mapping, imported by sga_section."""
    ctx = ctx if isinstance(ctx, dict) else {}
    return {
        "sgacmd": overview(ctx),
        "sgachannels": channels_screen(ctx),
        "sgaengage": engagement_screen(ctx),
        "sgaaudience": audience_screen(ctx),
        "sgaorganic": posts_screen(ctx),
        "sgapaid": paid_screen(ctx),
        "sgatraffic": traffic_screen(ctx),
        "sgarevenue": revenue_screen(ctx),
        "sgaplan": calendar_screen(ctx),
        "sgacreative": creative_screen(ctx),
        "sgablog": blog_screen(ctx),
        "sgabudget": budget_screen(ctx),
        "sgatarget": targeting_screen(ctx),
        "sgahub": hub_screen(ctx),
    }


CSS = """
.sg-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));
gap:9px;margin:0 0 14px}
.sg-tile{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:11px 13px;display:flex;flex-direction:column;gap:3px}
.sg-k{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;
color:var(--ft)}
.sg-tile b{font-family:ui-monospace,Menlo,monospace;font-size:23px;
font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.sg-none{color:var(--ft)!important;font-size:23px}
.sg-d{font-size:10.5px;color:var(--ft)}
.sg-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 12px}
.sg-chart{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:12px 14px;overflow-x:auto}
.sg-ct{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;
letter-spacing:.12em;text-transform:uppercase;color:var(--ft);margin:0 0 8px}
.sg-empty{font-size:12.5px;color:var(--ft);line-height:1.55;margin:6px 0 0}
.sg-head{display:flex;align-items:center;gap:10px;padding:10px 13px;
border:1px solid var(--ln);border-radius:10px;background:var(--card);
margin:0 0 10px}
.sg-head b{font-size:15px}
.sg-mark{width:26px;height:26px;border-radius:7px;color:#fff;font-size:11px;
font-weight:800;display:flex;align-items:center;justify-content:center;flex:none}
.sg-live{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.08em;
text-transform:uppercase;color:var(--okc)}
.sg-off{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.08em;
text-transform:uppercase;color:var(--ft)}
.sg-dots{display:flex;gap:5px;margin:5px 0 0}
.sg-dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.sg-tbl{border:1px solid var(--ln);border-radius:10px;background:var(--card);
overflow-x:auto;margin:0 0 12px}
.sg-tr{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));
gap:10px;padding:8px 13px;border-bottom:1px solid var(--ln);font-size:12.5px}
.sg-tr:last-child{border-bottom:0}
.sg-th{font-family:ui-monospace,Menlo,monospace;font-size:10px;
letter-spacing:.08em;text-transform:uppercase;color:var(--ft)}
.sg-tr b{font-family:ui-monospace,Menlo,monospace}
.sg-cp{margin-top:12px}
.sg-add{display:flex;gap:8px;margin:0 0 10px;flex-wrap:wrap}
.sg-add select,.sg-add input{padding:7px 10px;border:1px solid var(--ln);
border-radius:7px;background:var(--pap);color:var(--tx);font-family:inherit;
font-size:12.5px}
.sg-add input{flex:1;min-width:180px}
.a3sw i{font-style:normal;font-size:9.5px;letter-spacing:.08em;
text-transform:uppercase;color:var(--warnc);border:1px solid var(--warnc);
border-radius:3px;padding:1px 4px}
@media (max-width:900px){.sg-row{grid-template-columns:1fr}}
"""

JS = ("<script>"
      "async function sgAddComp(){var c=document.getElementById('sg-cc'),"
      "h=document.getElementById('sg-ch');if(!c||!h)return;"
      "if(!h.value.trim()){toast('Type a handle first.');return;}"
      "try{var r=await fetch('/social/competitor',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({channel:c.value,handle:h.value})});"
      "var j=await r.json();toast((j&&(j.message||j.error))||'added',"
      "j&&j.ok!==false);if(j&&j.ok)h.value='';}"
      "catch(e){toast('could not reach the engine',false);}}"
      "async function sgDropComp(ch,handle){"
      "try{var r=await fetch('/social/competitor',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({channel:ch,handle:handle,remove:true})});"
      "var j=await r.json();toast((j&&j.message)||'removed',true);}"
      "catch(e){toast('could not reach the engine',false);}}"
      "function sgChan(cid){try{"
      "document.querySelectorAll('.sg-cp').forEach(function(p){"
      "p.style.display=(p.id==='sg-c-'+cid)?'':'none';});"
      "document.querySelectorAll('#spanel-sgachannels .a3sw').forEach("
      "function(b){b.classList.remove('on');});"
      "if(window.event&&window.event.target){var b=window.event.target"
      ".closest('.a3sw');if(b)b.classList.add('on');}"
      "}catch(e){}return false;}"
      "</script>")
