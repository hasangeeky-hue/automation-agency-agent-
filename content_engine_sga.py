"""
content_engine_sga.py
============================================================================
SGA — SOCIAL, GROWTH & ADS. The loops behind the merged section.

Replaces three sections (Social Media, Google Hub, Ads & Growth) that held 27
cards, ZERO charts, and 19 panels that were literally _empty().

Scope, as decided: this section owns PAID AND UNPAID SOCIAL — planning,
creative, posting, and the analytics behind them — plus the Google data hub.
Google Ads keeps its own 296-card Media Buying section; nothing here duplicates
it.

The honest position this module takes:

  Every social connector is WRITE-ONLY. LinkedInPoster, TwitterPoster,
  MetaPoster, InstagramPoster and TikTokPoster expose exactly post(). There is
  no read path for likes, comments, shares, reach or followers anywhere in the
  engine. So this module does NOT invent them. Engagement and audience numbers
  return absent with the exact API scope that would fill them.

  What it does instead is measure what is real and add the one thing that
  needs no platform token: UTM tagging. With utm_source/medium/campaign/content
  stamped on every posted link, GA4 already reports sessions and conversions
  PER POST. For a B2B agency selling €2k-10k projects, "which post produced a
  booked call" beats "which post got likes".

Run offline self-check:  python content_engine_sga.py
============================================================================
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote, urlencode, urlparse, urlunparse

log = logging.getLogger("content_engine.sga")

CAMPAIGNS_KEY = "sga_campaigns"
CREATIVES_KEY = "sga_creatives"
AUDIENCE_KEY = "sga_audience_snapshots"     # only ever written by a real read
PAID_KEY = "sga_paid_social"                # only ever written by a real read
HUB_KEY = "sga_hub_counts"
MAX_CAMPAIGNS = 200

CHANNELS = ("linkedin", "facebook", "instagram", "youtube", "twitter", "tiktok")
CHANNEL_LABEL = {"linkedin": "LinkedIn", "facebook": "Facebook",
                 "instagram": "Instagram", "youtube": "YouTube",
                 "twitter": "X / Twitter", "tiktok": "TikTok"}
CHANNEL_WIRE = {"linkedin": "social_linkedin", "facebook": "social_facebook",
                "instagram": "social_instagram", "youtube": "social_youtube",
                "twitter": "social_twitter", "tiktok": "social_tiktok"}
# The exact read scope that would make each analytics board real. Named so a
# blank card points at a setting, never at a vendor to go buy.
READ_SCOPE = {
    "linkedin": "LinkedIn r_organization_social (page statistics)",
    "facebook": "Meta Graph API read_insights on the Page",
    "instagram": "Meta Graph API instagram_manage_insights",
    "youtube": "YouTube Analytics API (OAuth, yt-analytics.readonly)",
    "twitter": "X API v2 tweet metrics (paid tier)",
    "tiktok": "TikTok Business API video insights",
}
PAID_SCOPE = {
    "facebook": "Meta Marketing API (ads_read)",
    "instagram": "Meta Marketing API (ads_read)",
    "linkedin": "LinkedIn Ads API (r_ads_reporting)",
    "tiktok": "TikTok Ads API (reporting)",
}
FORMATS = ("text", "image", "video", "link", "carousel")


# ------------------------------------------------------------------ coercion
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


def _s(v):
    return str(v or "").strip()


def _day(v):
    return str(v or "")[:10]


def _iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pct(part, whole, nd=1):
    w = _f(whole)
    return round(100 * _f(part) / w, nd) if w else 0.0


def _slug(v):
    return re.sub(r"[^a-z0-9]+", "-", _s(v).lower()).strip("-")[:48]


def _get(store, key, default=None):
    try:
        return store.get_setting(key, default)
    except Exception:
        return default


def _set(store, key, value):
    try:
        store.set_setting(key, value)
        return True
    except Exception as e:
        log.warning("could not persist %s: %s", key, e)
        return False


# ======================================================================
#  UTM — the one real win that needs no platform token
# ======================================================================
def utm_url(url, channel, campaign="", post_id="", medium=None) -> str:
    """Tag a posted link so GA4 can attribute the session to THIS post.

    Without this every social visit lands in GA4 as undifferentiated "Social"
    and no post can be credited. With it, sessions, engagement and conversions
    are reportable per post — free, no platform API, no vendor."""
    u = _s(url)
    if not u or not u.lower().startswith(("http://", "https://")):
        return u
    ch = _s(channel).lower() or "social"
    try:
        parts = urlparse(u)
    except Exception:
        return u
    tags = {"utm_source": ch,
            "utm_medium": _s(medium) or "social",
            "utm_campaign": _slug(campaign) or "organic",
            "utm_content": _slug(post_id) or "post"}
    existing = parts.query
    if "utm_source=" in existing:          # never double-tag
        return u
    q = (existing + "&" if existing else "") + urlencode(tags)
    return urlunparse(parts._replace(query=q))


def tag_links(text, channel, campaign="", post_id="", medium=None) -> str:
    """Rewrite every bare URL in a post body with its UTM-tagged version."""
    t = _s(text)
    if not t:
        return t
    return re.sub(r"https?://[^\s<>\"')]+",
                  lambda m: utm_url(m.group(0), channel, campaign, post_id, medium),
                  t)


# ======================================================================
#  ① PLAN IT — campaigns and creatives
# ======================================================================
def list_campaigns(store) -> list:
    out = []
    for c in _L(_get(store, CAMPAIGNS_KEY, [])):
        c = _D(c)
        if not c.get("name"):
            continue
        out.append({
            "id": _s(c.get("id")) or _slug(c.get("name")),
            "name": _s(c.get("name"))[:80],
            "objective": _s(c.get("objective")) or "awareness",
            "channels": [ch for ch in _L(c.get("channels")) if ch in CHANNELS],
            "start": _day(c.get("start")), "end": _day(c.get("end")),
            "budget": _f(c.get("budget")),
            "paid": bool(c.get("paid")),
            "note": _s(c.get("note"))[:240],
        })
    return sorted(out, key=lambda c: c["start"] or "", reverse=True)


def save_campaign(store, name, objective="awareness", channels=None, start=None,
                  end=None, budget=0.0, paid=False, note="") -> dict:
    """A campaign is the object every other board hangs off — the calendar, the
    creative library, the UTM tag and the paid/organic split all key on it."""
    name = _s(name)
    if not name:
        return {"ok": False, "error": "a campaign name is required"}
    chans = [c for c in (_L(channels) or []) if _s(c).lower() in CHANNELS]
    rows = _L(_get(store, CAMPAIGNS_KEY, []))
    cid = _slug(name)
    row = {"id": cid, "name": name[:80],
           "objective": _s(objective) or "awareness",
           "channels": [_s(c).lower() for c in chans] or list(CHANNELS[:2]),
           "start": _day(start) or _day(_iso()),
           "end": _day(end), "budget": _f(budget), "paid": bool(paid),
           "note": _s(note)[:240], "at": _iso()}
    rows = [r for r in rows if _s(_D(r).get("id")) != cid] + [row]
    _set(store, CAMPAIGNS_KEY, rows[-MAX_CAMPAIGNS:])
    return {"ok": True, "campaign": row, "total": len(rows)}


def delete_campaign(store, campaign_id) -> bool:
    rows = _L(_get(store, CAMPAIGNS_KEY, []))
    kept = [r for r in rows if _s(_D(r).get("id")) != _s(campaign_id)]
    if len(kept) == len(rows):
        return False
    _set(store, CAMPAIGNS_KEY, kept)
    return True


def calendar(campaigns=None, days=21) -> dict:
    """P3 — the plan on a timeline, as day offsets for a gantt."""
    rows = _L(campaigns)
    today = date.today()
    tasks = []
    for c in rows:
        c = _D(c)
        try:
            st = date.fromisoformat(_day(c.get("start")))
        except Exception:
            continue
        try:
            en = date.fromisoformat(_day(c.get("end"))) if c.get("end") else st + timedelta(days=6)
        except Exception:
            en = st + timedelta(days=6)
        off = (st - today).days + 7
        length = max(1, (en - st).days + 1)
        if -7 <= off <= days:
            tasks.append((_s(c.get("name"))[:22], max(0, off), min(length, days)))
    live = [c for c in rows
            if _day(_D(c).get("start")) <= today.isoformat()
            and (not _D(c).get("end") or _day(_D(c).get("end")) >= today.isoformat())]
    return {"tasks": tasks[:10], "live": live, "planned": len(rows),
            "live_count": len(live),
            "paid": sum(1 for c in rows if _D(c).get("paid")),
            "organic": sum(1 for c in rows if not _D(c).get("paid")),
            "budget": round(sum(_f(_D(c).get("budget")) for c in rows), 2),
            "has_data": bool(rows)}


# ======================================================================
#  ② PUSH IT — what actually went out
# ======================================================================
def _social_jobs(jobs):
    out = []
    for j in _L(jobs):
        d = _D(j)
        refs = _D(_D(d.get("payload")).get("published_refs"))
        if not refs:
            continue
        for ch, ref in refs.items():
            ch = _s(ch).lower()
            if ch in ("wordpress", "cms", "web", "blog"):
                continue
            out.append({"job": _s(d.get("job_id")), "channel": ch,
                        "ref": _s(ref),
                        "at": _day(d.get("published_at") or d.get("created_at")),
                        "ok": bool(ref) and "_not_configured" not in _s(ref)
                        and "unknown" not in _s(ref),
                        "piece": _D(_D(d.get("payload")).get("content_producer"))})
    return out


def posts(jobs=None, days=14) -> dict:
    """P6 — real posts per channel, and how many actually left the building."""
    rows = _social_jobs(jobs)
    by_channel, per_day, failed = {}, {}, {}
    grid_cols, idx = [], {}
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        idx[d] = len(grid_cols)
        grid_cols.append(d[5:])
    grid = [[0] * len(grid_cols) for _ in CHANNELS]
    for r in rows:
        ch = r["channel"]
        by_channel[ch] = by_channel.get(ch, 0) + (1 if r["ok"] else 0)
        if not r["ok"]:
            failed[ch] = failed.get(ch, 0) + 1
        if r["at"]:
            per_day[r["at"]] = per_day.get(r["at"], 0) + (1 if r["ok"] else 0)
            if r["at"] in idx and ch in CHANNELS:
                grid[CHANNELS.index(ch)][idx[r["at"]]] += 1 if r["ok"] else 0
    keys = sorted(per_day)[-days:]
    return {"total": sum(by_channel.values()), "attempted": len(rows),
            "by_channel": [(CHANNEL_LABEL.get(c, c), n)
                           for c, n in sorted(by_channel.items(), key=lambda kv: -kv[1])],
            "failed": [(CHANNEL_LABEL.get(c, c), n)
                       for c, n in sorted(failed.items(), key=lambda kv: -kv[1])],
            "failed_total": sum(failed.values()),
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "cohort_rows": [CHANNEL_LABEL.get(c, c) for c in CHANNELS],
            "cohort_cols": grid_cols, "cohort_grid": grid,
            "channels_live": len([c for c, n in by_channel.items() if n]),
            "has_data": bool(rows)}


def cadence(posts_=None, target_per_channel=1, channels=None) -> dict:
    """P7 — are you hitting the plan? The old card asked '3 posts/channel/day?'
    with no data and no stored target."""
    p = _D(posts_)
    chans = [c for c in (_L(channels) or list(CHANNELS))]
    per_day = _L(p.get("per_day"))
    daily_target = max(1, _i(target_per_channel)) * max(1, len(chans))
    hit = sum(1 for _d, v in per_day if v >= daily_target)
    rows = [(d, v, daily_target) for d, v in per_day]
    return {"target_per_channel": _i(target_per_channel),
            "channels_planned": len(chans),
            "daily_target": daily_target,
            "days_measured": len(per_day),
            "days_on_target": hit,
            "adherence": _pct(hit, len(per_day)),
            "rows": rows,
            "avg": round(sum(v for _d, v in per_day) / len(per_day), 1) if per_day else 0,
            "has_data": bool(per_day)}


def creatives(jobs=None) -> dict:
    """P4 — what format each post used. Read from the produced piece, so this
    is real without any new store."""
    rows = _social_jobs(jobs)
    by_format = {f: 0 for f in FORMATS}
    with_image = with_video = 0
    for r in rows:
        piece = _D(r.get("piece"))
        if piece.get("video_url"):
            by_format["video"] += 1
            with_video += 1
        elif piece.get("image_url"):
            by_format["image"] += 1
            with_image += 1
        elif piece.get("link") or piece.get("url"):
            by_format["link"] += 1
        else:
            by_format["text"] += 1
    total = sum(by_format.values())
    return {"total": total,
            "by_format": [(f, by_format[f]) for f in FORMATS if by_format[f]],
            "treemap": [(f, by_format[f]) for f in FORMATS if by_format[f]],
            "with_image": with_image, "with_video": with_video,
            "image_rate": _pct(with_image, total),
            "video_rate": _pct(with_video, total),
            "text_only": by_format["text"],
            "text_only_rate": _pct(by_format["text"], total),
            "has_data": bool(total)}


def blog_push(jobs=None, days=14) -> dict:
    """P8 — long-form published to the site, with its cost."""
    rows, per_day, cost = [], {}, 0.0
    for j in _L(jobs):
        d = _D(j)
        refs = _D(_D(d.get("payload")).get("published_refs"))
        if not any(_s(k).lower() in ("wordpress", "cms", "web", "blog") for k in refs):
            continue
        at = _day(d.get("published_at") or d.get("created_at"))
        piece = _D(_D(d.get("payload")).get("content_producer"))
        rows.append({"job": _s(d.get("job_id")), "at": at,
                     "title": _s(piece.get("title"))[:70],
                     "cost": _f(d.get("cost_so_far_usd"))})
        cost += _f(d.get("cost_so_far_usd"))
        if at:
            per_day[at] = per_day.get(at, 0) + 1
    keys = sorted(per_day)[-days:]
    return {"total": len(rows), "cost": round(cost, 2),
            "per_piece": round(cost / len(rows), 2) if rows else None,
            "recent": sorted(rows, key=lambda r: r["at"], reverse=True)[:10],
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "has_data": bool(rows)}


# ======================================================================
#  ③ DID IT LAND
# ======================================================================
def channel_health(status=None, posts_=None) -> dict:
    """P12 — per platform: connected, and did anything actually post."""
    st = _D(status)
    p = _D(posts_)
    posted = {c.lower(): n for c, n in
              [(k, v) for k, v in _D({CHANNEL_LABEL.get(c, c): n
                                      for c, n in _L(p.get("by_channel"))}).items()]}
    by_label = {label: n for label, n in _L(p.get("by_channel"))}
    rows = []
    for ch in CHANNELS:
        wire = CHANNEL_WIRE[ch]
        connected = bool(st.get(wire))
        n = _i(by_label.get(CHANNEL_LABEL[ch]))
        rows.append({"channel": ch, "label": CHANNEL_LABEL[ch],
                     "connected": connected, "posts": n,
                     "posting": bool(n),
                     "read_scope": READ_SCOPE[ch],
                     "state": ("posting" if n else
                               "connected, nothing posted" if connected else
                               "not connected")})
    return {"rows": rows,
            "connected": sum(1 for r in rows if r["connected"]),
            "posting": sum(1 for r in rows if r["posting"]),
            "total": len(rows),
            "statusgrid": [(r["label"], r["connected"], r["state"][:18]) for r in rows],
            "has_data": True}


def audience(store=None, status=None) -> dict:
    """P15 — follower counts over time.

    Returns absent unless a real read has written a snapshot. No connector can
    read followers today, so this is empty by construction rather than by
    accident, and it names the scope that would change that."""
    snaps = _L(_get(store, AUDIENCE_KEY, [])) if store else []
    st = _D(status)
    per_channel, series = {}, {}
    for s in snaps:
        s = _D(s)
        ch = _s(s.get("channel")).lower()
        if ch not in CHANNELS:
            continue
        per_channel[ch] = _i(s.get("followers"))
        series.setdefault(ch, []).append(_i(s.get("followers")))
    missing = [CHANNEL_LABEL[c] for c in CHANNELS if st.get(CHANNEL_WIRE[c])
               and c not in per_channel]
    return {"snapshots": len(snaps),
            "per_channel": [(CHANNEL_LABEL[c], v) for c, v in per_channel.items()],
            "series": [(CHANNEL_LABEL[c], v) for c, v in series.items()],
            "total": sum(per_channel.values()),
            "measured": bool(snaps),
            "needs": [(CHANNEL_LABEL[c], READ_SCOPE[c]) for c in CHANNELS],
            "missing_but_connected": missing,
            "note": ("Follower counts come from a snapshot written by a real "
                     "platform read. No social connector in this engine can read "
                     "yet — every one of them is post-only — so this stays empty "
                     "rather than showing a number nothing measured.")
            if not snaps else ""}


def engagement(store=None) -> dict:
    """P14 — likes, comments, shares. Same construction as audience(): absent
    until a real read exists, with the scope named."""
    rows = _L(_get(store, "sga_engagement", [])) if store else []
    return {"rows": rows, "measured": bool(rows),
            "needs": [(CHANNEL_LABEL[c], READ_SCOPE[c]) for c in CHANNELS],
            "heat_rows": [], "heat_cols": [], "heat": [],
            "note": ("Likes, comments and shares need a read scope on each "
                     "platform. Until one is connected, the honest performance "
                     "measure is the traffic and the bookings a post produced — "
                     "both of which ARE measured, on the Social to Traffic and "
                     "Social to Revenue boards.")}


def paid_social(store=None, campaigns=None) -> dict:
    """P9/P19 — paid spend and cost per result per platform.

    No Meta / LinkedIn / TikTok Ads connector exists. Planned paid campaigns
    are shown from your own campaign objects; SPEND stays absent until a
    reporting scope is connected."""
    rows = _L(_get(store, PAID_KEY, [])) if store else []
    planned = [c for c in _L(campaigns) if _D(c).get("paid")]
    by_platform = {}
    for r in rows:
        r = _D(r)
        ch = _s(r.get("channel")).lower()
        if ch in CHANNELS:
            by_platform[ch] = by_platform.get(ch, 0.0) + _f(r.get("spend"))
    return {"measured": bool(rows),
            "planned": planned, "planned_count": len(planned),
            "planned_budget": round(sum(_f(_D(c).get("budget")) for c in planned), 2),
            "by_platform": [(CHANNEL_LABEL.get(c, c), v) for c, v in by_platform.items()],
            "spend": round(sum(by_platform.values()), 2),
            "needs": [(CHANNEL_LABEL[c], PAID_SCOPE[c])
                      for c in CHANNELS if c in PAID_SCOPE],
            "note": ("Paid social spend needs a reporting scope on each ad "
                     "platform. Your planned budgets are shown from the campaigns "
                     "you set here; actual spend and cost-per-result appear once "
                     "a platform is connected. Google Ads is deliberately NOT "
                     "here — it has its own Media Buying section.")}


def social_traffic(insights=None, posts_=None, campaigns=None) -> dict:
    """P18 — what social actually sent to the site.

    GA4 channel data is real today. Per-POST attribution becomes real as soon
    as UTM-tagged links start going out, because GA4 already reports by
    utm_campaign and utm_content."""
    ga = _D(_D(insights).get("ga4"))
    rows = []
    for r in _L(ga.get("channels")):
        r = _D(r)
        name = _s(r.get("sessionDefaultChannelGroup") or r.get("channel"))
        if name:
            rows.append((name, _f(r.get("sessions"))))
    total = sum(v for _n, v in rows)
    social = sum(v for n, v in rows if "social" in n.lower())
    p = _D(posts_)
    flows = []
    for label, n in _L(p.get("by_channel"))[:5]:
        flows.append((label, "social sessions", max(1, n)))
    if social:
        flows.append(("social sessions", "site", social))
    return {"channels": rows, "total_sessions": total,
            "social_sessions": social,
            "social_share": _pct(social, total),
            "posts": _i(p.get("total")),
            "sessions_per_post": (round(social / _i(p.get("total")), 1)
                                  if p.get("total") and social else None),
            "flows": flows,
            "has_ga4": bool(rows),
            "utm_ready": True,
            "note": ("GA4 reports the social CHANNEL today. Per-post numbers "
                     "come from the UTM tags now stamped on every posted link — "
                     "utm_campaign is the campaign, utm_content is the post — so "
                     "GA4 can credit an individual post without any platform API.")}


def social_revenue(deals=None, posts_=None, paid=None) -> dict:
    """P20 — did social produce money. Reads the deals recorded in BI."""
    dl = _L(deals)
    social_deals = [d for d in dl if _s(_D(d).get("source")).lower()
                    in ("social", "organic", "referral")]
    rev = sum(_f(_D(d).get("value")) for d in social_deals)
    total_rev = sum(_f(_D(d).get("value")) for d in dl)
    spend = _f(_D(paid).get("spend"))
    n = _i(_D(posts_).get("total"))
    stages = [("Posts", n),
              ("Social sessions", _i(_D(paid).get("_sessions"))),
              ("Deals", len(social_deals))]
    return {"deals": len(social_deals), "revenue": round(rev, 2),
            "share_of_revenue": _pct(rev, total_rev),
            "revenue_per_post": round(rev / n, 2) if (n and rev) else None,
            "roi": _pct(rev - spend, spend) if spend else None,
            "waterfall": [(a, b) for a, b in stages if b or a == "Posts"],
            "matrix": [(_s(_D(d).get("client"))[:12], 2, 2) for d in social_deals[:6]],
            "has_data": bool(social_deals),
            "note": ("Deals are counted here when they were recorded with a "
                     "social, organic or referral source. Tag the source when "
                     "you record a won deal and this board fills itself."
                     if not social_deals else "")}


def budget(campaigns=None, paid=None, month_spent=0.0, month_cap=200.0,
           blog=None) -> dict:
    """P21/P5 — the paid/organic split and the pacing against your cap."""
    planned = round(sum(_f(_D(c).get("budget")) for c in _L(campaigns)
                        if _D(c).get("paid")), 2)
    spend = _f(_D(paid).get("spend"))
    content_cost = _f(_D(blog).get("cost"))
    cap = _f(month_cap, 200) or 200
    return {"planned_paid": planned, "actual_paid": spend,
            "organic_cost": content_cost,
            "engine_spend": round(_f(month_spent), 2), "cap": cap,
            "pct_of_cap": _pct(month_spent, cap),
            "split": [("paid (planned)", planned), ("organic (content)", content_cost)],
            "paid_share": _pct(planned, planned + content_cost),
            "committed": round(planned + content_cost, 2),
            "has_data": bool(planned or content_cost),
            "note": ("Paid figures are your PLANNED budgets until an ad platform "
                     "reporting scope is connected. Organic cost is what the "
                     "engine actually spent producing the content.")}


# ======================================================================
#  ④ GOOGLE HUB — real counts, not estimates
# ======================================================================
def google_hub(store=None, status=None, jobs=None, emails_sent=0,
               sheets_rows=None, drive_files=None) -> dict:
    """P23 — what the hub actually holds.

    The old cards read len(jobs) and printed "≈ N rows mirrored" — a local
    count presented as a Google fact, which stayed confident even with the wire
    down. Real counts are used when a read supplies them; otherwise the card
    says the number is local and unverified."""
    st = _D(status)
    local_jobs = len(_L(jobs))
    cached = _D(_get(store, HUB_KEY, {})) if store else {}
    rows = sheets_rows if sheets_rows is not None else cached.get("sheets_rows")
    files = drive_files if drive_files is not None else cached.get("drive_files")
    return {
        "sheets_connected": bool(st.get("google_sheets")),
        "drive_connected": bool(st.get("google_drive")),
        "gmail_connected": bool(st.get("email_send")),
        "sheets_rows": _i(rows) if rows is not None else None,
        "drive_files": _i(files) if files is not None else None,
        "sheets_verified": rows is not None,
        "drive_verified": files is not None,
        "local_jobs": local_jobs,
        "emails_sent": _i(emails_sent),
        "last_read": _s(cached.get("at")),
        "ring": [("job rows (local)", local_jobs), ("emails sent", _i(emails_sent))],
        "note": ("These are counts read back from Google."
                 if (rows is not None and files is not None) else
                 "Sheets and Drive are write-only in this engine, so the hub "
                 "cannot yet be asked how many rows or files it holds. The "
                 "numbers shown are LOCAL counts of what was sent — the old "
                 "cards printed the same figure as though Google had confirmed "
                 "it."),
    }


def record_hub_counts(store, sheets_rows=None, drive_files=None) -> dict:
    """Written only by a real read, so a verified count can never be faked."""
    cur = _D(_get(store, HUB_KEY, {}))
    if sheets_rows is not None:
        cur["sheets_rows"] = _i(sheets_rows)
    if drive_files is not None:
        cur["drive_files"] = _i(drive_files)
    cur["at"] = _iso()
    _set(store, HUB_KEY, cur)
    return cur


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()

    # ---- UTM: the one thing that needs no platform token ----
    u = utm_url("https://anthropos-automation.com/guides/n8n", "linkedin",
                "Q3 launch", "social_linkedin_0")
    assert "utm_source=linkedin" in u and "utm_medium=social" in u
    assert "utm_campaign=q3-launch" in u and "utm_content=social-linkedin-0" in u
    assert utm_url(u, "linkedin", "x", "y") == u, "must never double-tag"
    assert utm_url("not a url", "linkedin") == "not a url"
    keep = utm_url("https://x.com/a?ref=1", "facebook")
    assert "ref=1" in keep and "utm_source=facebook" in keep, "existing query kept"
    body = tag_links("See https://anthropos-automation.com/x and thanks",
                     "instagram", "Launch", "p1")
    assert "utm_source=instagram" in body and body.startswith("See http")

    # ---- campaigns ----
    assert save_campaign(st, "")["ok"] is False
    r = save_campaign(st, "Q3 Launch", "leads", ["linkedin", "instagram"],
                      "2026-07-28", "2026-08-10", 400, paid=True)
    assert r["ok"] and r["campaign"]["id"] == "q3-launch"
    save_campaign(st, "Always On", "awareness", ["linkedin"], "2026-07-01")
    cs = list_campaigns(st)
    assert len(cs) == 2 and cs[0]["channels"] == ["linkedin", "instagram"]
    cal = calendar(cs)
    assert cal["planned"] == 2 and cal["paid"] == 1 and cal["organic"] == 1
    assert cal["budget"] == 400.0
    assert delete_campaign(st, "always-on") and len(list_campaigns(st)) == 1

    # ---- posts: a not_configured ref is NOT a post ----
    jobs = [
        {"job_id": "social_linkedin_0", "type": "content_piece",
         "created_at": "2026-07-30T09:00:00Z", "cost_so_far_usd": 0.2,
         "payload": {"published_refs": {"linkedin": "urn:li:share:123"},
                     "content_producer": {"title": "T", "image_url": "i.png"}}},
        {"job_id": "social_tiktok_0", "type": "content_piece",
         "created_at": "2026-07-30T09:00:00Z",
         "payload": {"published_refs": {"tiktok": "tiktok_not_configured:x"},
                     "content_producer": {}}},
        {"job_id": "blog_1", "type": "content_piece",
         "created_at": "2026-07-29T09:00:00Z", "cost_so_far_usd": 0.6,
         "payload": {"published_refs": {"wordpress": "post_9"},
                     "content_producer": {"title": "A blog"}}},
    ]
    p = posts(jobs)
    assert p["attempted"] == 2 and p["total"] == 1, (p["attempted"], p["total"])
    assert p["failed_total"] == 1 and p["failed"][0][0] == "TikTok"
    assert p["by_channel"][0] == ("LinkedIn", 1)
    assert len(p["cohort_rows"]) == len(CHANNELS)

    cd = cadence(p, target_per_channel=1, channels=["linkedin", "tiktok"])
    assert cd["daily_target"] == 2 and cd["days_measured"] >= 1
    assert 0 <= cd["adherence"] <= 100

    cr = creatives(jobs)
    assert cr["total"] == 2 and cr["with_image"] == 1
    assert cr["text_only"] == 1

    bp = blog_push(jobs)
    assert bp["total"] == 1 and bp["per_piece"] == 0.6

    ch = channel_health({"social_linkedin": True}, p)
    assert ch["connected"] == 1 and ch["posting"] == 1
    assert all(r["read_scope"] for r in ch["rows"]), "every row names its scope"

    # ---- the three that must stay ABSENT, with the scope named ----
    au = audience(st, {"social_linkedin": True})
    assert au["measured"] is False and au["total"] == 0
    assert "post-only" in au["note"] and au["needs"]
    en = engagement(st)
    assert en["measured"] is False and "read scope" in en["note"]
    ps = paid_social(st, cs)
    assert ps["measured"] is False and ps["spend"] == 0
    assert ps["planned_count"] == 1 and ps["planned_budget"] == 400.0
    assert "Google Ads is deliberately NOT here" in ps["note"]

    # ---- traffic + revenue ----
    ins = {"ga4": {"channels": [{"sessionDefaultChannelGroup": "Organic Social",
                                 "sessions": 120},
                                {"sessionDefaultChannelGroup": "Organic Search",
                                 "sessions": 400}]}}
    tr = social_traffic(ins, p, cs)
    assert tr["social_sessions"] == 120 and tr["social_share"] > 0
    assert tr["has_ga4"] and tr["flows"]
    sr = social_revenue([{"client": "A", "value": 3000, "source": "social"},
                         {"client": "B", "value": 5000, "source": "outreach"}], p, ps)
    assert sr["deals"] == 1 and sr["revenue"] == 3000.0
    assert sr["share_of_revenue"] == 37.5

    bg = budget(cs, ps, month_spent=41.7, month_cap=200.0, blog=bp)
    assert bg["planned_paid"] == 400.0 and bg["organic_cost"] == 0.6
    assert bg["pct_of_cap"] > 0

    # ---- google hub: a local count must not read as a Google fact ----
    gh = google_hub(st, {"google_sheets": True}, jobs, emails_sent=12)
    assert gh["sheets_rows"] is None and gh["sheets_verified"] is False
    assert "LOCAL counts" in gh["note"], gh["note"]
    record_hub_counts(st, sheets_rows=340, drive_files=57)
    gh2 = google_hub(st, {"google_sheets": True}, jobs, emails_sent=12)
    assert gh2["sheets_rows"] == 340 and gh2["sheets_verified"] is True
    assert "read back from Google" in gh2["note"]

    # ---- hostile shapes ----
    for bad in (None, {}, [], "x", 0, {"ga4": "no"}, [{"payload": "no"}]):
        posts(bad if isinstance(bad, list) else None)
        creatives(bad if isinstance(bad, list) else None)
        blog_push(bad if isinstance(bad, list) else None)
        cadence(bad, 1, None)
        channel_health(bad, bad)
        audience(None, bad)
        engagement(None)
        paid_social(None, bad if isinstance(bad, list) else None)
        social_traffic(bad, bad, None)
        social_revenue(bad if isinstance(bad, list) else None, bad, bad)
        budget(bad if isinstance(bad, list) else None, bad, 0, 0, bad)
        google_hub(None, bad, None)
        calendar(bad if isinstance(bad, list) else None)
        list_campaigns(S())

    print("sga self-check OK — UTM tagging never double-tags and keeps existing "
          "query strings, a *_not_configured ref counts as a FAILED post rather "
          "than a post, campaigns drive the calendar and the paid/organic split, "
          "engagement/audience/paid-spend stay absent with the exact read scope "
          "named, and the Google hub refuses to present a local count as a "
          "Google-confirmed one.")
