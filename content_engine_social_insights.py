"""
content_engine_social_insights.py
============================================================================
THE READ SIDE OF SOCIAL. Seven channels, seven key-gated sockets, one
registry - so a Metricool-grade page can be built now and lit channel by
channel as each key arrives.

WHY THIS MODULE HAS TO EXIST
  Every social connector in this engine is POST-ONLY. LinkedInPoster,
  MetaPoster, InstagramPoster, TwitterPoster and TikTokPoster expose
  available() and post(), and nothing else. Followers, reach, impressions,
  likes, comments, shares and best-time-to-post all live behind each
  platform's INSIGHTS api, which was never wired. That is why the SGA
  boards emitted {measured, needs, note} instead of numbers: they were
  built honest, with nothing to read.

THE CONTRACT EVERY SOCKET KEEPS
  summary() returns the SAME shape for every channel:
    {connected, reason, followers, reach, impressions, engagement, clicks,
     posts, series[], top_posts[]}
  A socket with no key returns connected=False and a reason naming the
  exact missing setting. It NEVER returns a zero that could be mistaken
  for a measurement, and it never invents a number.

  Endpoints are each platform's documented current version, and each
  version is a setting - so an API sunset is a config change, not a code
  change. Unverified against live accounts until a key exists, by
  definition; the first live call reports exactly what the platform said.
============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("social_insights")

# THE CHANNEL REGISTRY - one list. Screens, the agent, the gates and the
# store key all import THIS. A second hand-written channel list is the bug
# class that has bitten this engine five times.
CHANNELS = (
    ("facebook",  "Facebook",        "#1877F2", "f"),
    ("instagram", "Instagram",       "#C13584", "ig"),
    ("linkedin",  "LinkedIn",        "#0A66C2", "in"),
    ("tiktok",    "TikTok",          "#161823", "tt"),
    ("x",         "X",               "#111111", "X"),
    ("youtube",   "YouTube",         "#FF0000", "yt"),
    ("gbp",       "Google Business", "#34A853", "G"),
)
ORDER = tuple(c[0] for c in CHANNELS)
NAME = {c[0]: c[1] for c in CHANNELS}
COLOUR = {c[0]: c[2] for c in CHANNELS}
MARK = {c[0]: c[3] for c in CHANNELS}

SETTING_KEY = "social_insights"

# The metric slots a channel screen shows. Every slot is present on every
# channel; a channel that cannot measure one says so rather than showing 0.
SLOTS = ("followers", "reach", "impressions", "engagement", "clicks", "posts")

# channel -> the settings its read API needs. Named exactly, so a screen can
# tell the founder WHICH key is missing instead of "not connected".
KEYS = {
    "facebook":  ("META_ACCESS_TOKEN", "META_PAGE_ID"),
    "instagram": ("META_ACCESS_TOKEN", "IG_BUSINESS_ID"),
    "linkedin":  ("LINKEDIN_ORG_TOKEN", "LINKEDIN_ORG_URN"),
    "tiktok":    ("TIKTOK_ACCESS_TOKEN", "TIKTOK_BUSINESS_ID"),
    "x":         ("TWITTER_BEARER_TOKEN", "TWITTER_USER_ID"),
    "youtube":   ("YOUTUBE_CHANNEL_ID",),
    "gbp":       ("GBP_LOCATION_NAME",),
}

# which channels ride the service account already reading GSC/GA4 rather
# than a token of their own
SERVICE_ACCOUNT_CHANNELS = ("youtube", "gbp")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env(k: str) -> str:
    try:
        import content_engine_connectors as C
        return C._env(k) or ""
    except Exception:
        return ""


def _requests():
    try:
        import content_engine_connectors as C
        return C._requests()
    except Exception:
        return None


def _blank(cid: str, reason: str) -> dict:
    """The honest empty shape. Every slot present, every value None - never
    zero, because zero is a measurement and this is an absence."""
    return {"channel": cid, "name": NAME.get(cid, cid), "connected": False,
            "reason": reason, "at": _now(),
            **{s: None for s in SLOTS},
            "series": [], "top_posts": [], "reactions": {}, "best_time": {},
            # every later-built layer has its slot from the start, so a
            # screen never has to ask whether a key exists before reading
            "posts_rows": [], "demographics": {}, "inbox": [],
            "paid": {"spend": None, "cpm": None, "cpc": None,
                     "cost_per_result": None, "results": None}}


def missing_keys(cid: str) -> list:
    """Which settings this channel still needs, in order."""
    need = list(KEYS.get(cid, ()))
    if cid in SERVICE_ACCOUNT_CHANNELS:
        # these use the service account that already reads GSC and GA4
        return [k for k in need if not _env(k)]
    return [k for k in need if not _env(k)]


def connected(cid: str) -> bool:
    return bool(cid in KEYS and not missing_keys(cid) and _requests())


def reason_for(cid: str) -> str:
    miss = missing_keys(cid)
    if not miss:
        return ""
    where = ("the Connect board" if cid not in SERVICE_ACCOUNT_CHANNELS
             else "the Connect board (it rides your existing Google service "
                  "account, so only the id is needed)")
    return (f"{NAME.get(cid, cid)} analytics needs "
            + " + ".join(miss) + f" on {where}. Until then this channel "
            f"shows no numbers rather than zeros.")


# ---------------------------------------------------------------------------
# THE SOCKETS. Each pulls its channel's real insights; each is unverified
# against a live account until its key exists.
# ---------------------------------------------------------------------------
def _meta_insights(cid: str, obj_id: str, metrics: str) -> dict:
    r, tok = _requests(), _env("META_ACCESS_TOKEN")
    v = _env("META_API_VERSION") or "v21.0"
    base = f"https://graph.facebook.com/{v}/{obj_id}"
    prof = r.get(base, params={
        "fields": ("followers_count,fan_count" if cid == "facebook"
                   else "followers_count,media_count"),
        "access_token": tok}, timeout=30).json()
    ins = r.get(f"{base}/insights", params={
        "metric": metrics, "period": "day", "access_token": tok},
        timeout=30).json()
    got = {}
    for row in (ins.get("data") or []):
        vals = row.get("values") or []
        got[row.get("name")] = sum(float(x.get("value") or 0)
                                   for x in vals if isinstance(x.get("value"),
                                                               (int, float)))
    out = _blank(cid, "")
    out.update({"connected": True, "reason": "",
                "followers": prof.get("followers_count") or prof.get("fan_count"),
                "reach": got.get("page_impressions_unique")
                or got.get("reach") or got.get("impressions"),
                "impressions": got.get("page_impressions") or got.get("impressions"),
                "engagement": got.get("page_post_engagements")
                or got.get("accounts_engaged"),
                "clicks": got.get("page_consumptions") or got.get("website_clicks")})
    return out


def fetch(cid: str) -> dict:
    """One channel's insights, or the honest blank with its missing keys."""
    if cid not in KEYS:
        return _blank(cid, f"{cid} is not in the channel registry")
    if not _requests():
        return _blank(cid, "the HTTP client is unavailable on this box")
    miss = missing_keys(cid)
    if miss:
        return _blank(cid, reason_for(cid))
    try:
        if cid == "facebook":
            return _meta_insights(cid, _env("META_PAGE_ID"),
                                  "page_impressions,page_impressions_unique,"
                                  "page_post_engagements,page_consumptions")
        if cid == "instagram":
            return _meta_insights(cid, _env("IG_BUSINESS_ID"),
                                  "impressions,reach,accounts_engaged,"
                                  "website_clicks")
        if cid == "linkedin":
            return _linkedin()
        if cid == "tiktok":
            return _tiktok()
        if cid == "x":
            return _x()
        if cid == "youtube":
            return _youtube()
        if cid == "gbp":
            return _gbp()
    except Exception as e:
        return _blank(cid, f"{NAME.get(cid, cid)}: {type(e).__name__}: "
                           f"{str(e)[:130]}")
    return _blank(cid, "no socket for this channel yet")


def _linkedin() -> dict:
    r = _requests()
    urn = _env("LINKEDIN_ORG_URN")
    H = {"Authorization": f"Bearer {_env('LINKEDIN_ORG_TOKEN')}",
         "LinkedIn-Version": _env("LINKEDIN_API_VERSION") or "202409",
         "X-Restli-Protocol-Version": "2.0.0"}
    fol = r.get("https://api.linkedin.com/rest/networkSizes/"
                f"{urn}?edgeType=CompanyFollowedByMember",
                headers=H, timeout=30).json()
    st = r.get("https://api.linkedin.com/rest/organizationalEntityShareStatistics"
               f"?q=organizationalEntity&organizationalEntity={urn}",
               headers=H, timeout=30).json()
    tot = ((st.get("elements") or [{}])[0]
           .get("totalShareStatistics") or {})
    out = _blank("linkedin", "")
    out.update({"connected": True, "reason": "",
                "followers": fol.get("firstDegreeSize"),
                "impressions": tot.get("impressionCount"),
                "reach": tot.get("uniqueImpressionsCount"),
                "clicks": tot.get("clickCount"),
                "engagement": (tot.get("likeCount") or 0)
                + (tot.get("commentCount") or 0) + (tot.get("shareCount") or 0),
                "reactions": {"likes": tot.get("likeCount"),
                              "comments": tot.get("commentCount"),
                              "shares": tot.get("shareCount")}})
    return out


def _tiktok() -> dict:
    r = _requests()
    v = _env("TIKTOK_ADS_API_VERSION") or "v1.3"
    H = {"Access-Token": _env("TIKTOK_ACCESS_TOKEN")}
    j = r.get(f"https://business-api.tiktok.com/open_api/{v}/business/get/",
              params={"business_id": _env("TIKTOK_BUSINESS_ID"),
                      "fields": '["followers_count","profile_views",'
                                '"video_views","likes","comments","shares"]'},
              headers=H, timeout=30).json()
    d = (j.get("data") or {})
    out = _blank("tiktok", "")
    out.update({"connected": True, "reason": "",
                "followers": d.get("followers_count"),
                "impressions": d.get("video_views"),
                "reach": d.get("video_views"),
                "clicks": d.get("profile_views"),
                "engagement": (d.get("likes") or 0) + (d.get("comments") or 0)
                + (d.get("shares") or 0),
                "reactions": {"likes": d.get("likes"),
                              "comments": d.get("comments"),
                              "shares": d.get("shares")}})
    return out


def _x() -> dict:
    r = _requests()
    uid = _env("TWITTER_USER_ID")
    H = {"Authorization": f"Bearer {_env('TWITTER_BEARER_TOKEN')}"}
    u = r.get(f"https://api.twitter.com/2/users/{uid}",
              params={"user.fields": "public_metrics"},
              headers=H, timeout=30).json()
    pm = ((u.get("data") or {}).get("public_metrics") or {})
    out = _blank("x", "")
    out.update({"connected": True, "reason": "",
                "followers": pm.get("followers_count"),
                "posts": pm.get("tweet_count")})
    return out


def _youtube() -> dict:
    """Rides the service account already reading GSC and GA4."""
    import content_engine_connectors as C
    tok = None
    fn = getattr(C, "_google_token", None)
    if fn:
        tok = fn(["https://www.googleapis.com/auth/yt-analytics.readonly",
                  "https://www.googleapis.com/auth/youtube.readonly"])
    if not tok:
        return _blank("youtube", "YouTube analytics needs the Google service "
                                 "account granted on the channel (Settings > "
                                 "Permissions), the same account reading your "
                                 "GSC and GA4.")
    r = _requests()
    cid = _env("YOUTUBE_CHANNEL_ID")
    j = r.get("https://www.googleapis.com/youtube/v3/channels",
              params={"part": "statistics", "id": cid},
              headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
    st = ((j.get("items") or [{}])[0].get("statistics") or {})
    out = _blank("youtube", "")
    out.update({"connected": True, "reason": "",
                "followers": st.get("subscriberCount"),
                "impressions": st.get("viewCount"),
                "posts": st.get("videoCount")})
    return out


def _gbp() -> dict:
    """Google Business Profile performance, on the same service account."""
    import content_engine_connectors as C
    tok = None
    fn = getattr(C, "_google_token", None)
    if fn:
        tok = fn(["https://www.googleapis.com/auth/business.manage"])
    if not tok:
        return _blank("gbp", "Google Business Profile needs the service "
                             "account added to the location, the same account "
                             "reading your GSC and GA4.")
    r = _requests()
    loc = _env("GBP_LOCATION_NAME")
    j = r.get(f"https://businessprofileperformance.googleapis.com/v1/{loc}"
              ":fetchMultiDailyMetricsTimeSeries",
              params={"dailyMetrics": ["BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
                                       "WEBSITE_CLICKS", "CALL_CLICKS"]},
              headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
    out = _blank("gbp", "")
    out.update({"connected": True, "reason": "",
                "impressions": _sum_ts(j, "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH"),
                "clicks": _sum_ts(j, "WEBSITE_CLICKS")})
    return out


def _sum_ts(payload, metric) -> float | None:
    try:
        for row in (payload.get("multiDailyMetricTimeSeries") or []):
            for s in (row.get("dailyMetricTimeSeries") or []):
                if s.get("dailyMetric") != metric:
                    continue
                pts = ((s.get("timeSeries") or {}).get("datedValues") or [])
                return sum(float(p.get("value") or 0) for p in pts)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# PER-POST METRICS, DEMOGRAPHICS, INBOX, BEST TIME - the layers a key unlocks
# ---------------------------------------------------------------------------
def _meta_posts(cid, obj_id):
    """Recent posts with their real metrics. Facebook and Instagram share
    the Graph API; the metric names differ, so each asks for its own."""
    r, tok = _requests(), _env("META_ACCESS_TOKEN")
    v = _env("META_API_VERSION") or "v21.0"
    edge = "media" if cid == "instagram" else "posts"
    fields = ("id,caption,timestamp,media_type,permalink,like_count,"
              "comments_count" if cid == "instagram" else
              "id,message,created_time,permalink_url,shares,"
              "reactions.summary(true),comments.summary(true)")
    j = r.get(f"https://graph.facebook.com/{v}/{obj_id}/{edge}",
              params={"fields": fields, "limit": 25, "access_token": tok},
              timeout=30).json()
    out = []
    for m in (j.get("data") or []):
        if cid == "instagram":
            likes, comments = m.get("like_count"), m.get("comments_count")
            title, when = (m.get("caption") or "")[:90], m.get("timestamp")
            fmt = m.get("media_type")
        else:
            likes = ((m.get("reactions") or {}).get("summary")
                     or {}).get("total_count")
            comments = ((m.get("comments") or {}).get("summary")
                        or {}).get("total_count")
            title, when = (m.get("message") or "")[:90], m.get("created_time")
            fmt = "post"
        shares = (m.get("shares") or {}).get("count")
        eng = sum(float(x or 0) for x in (likes, comments, shares))
        out.append({"id": m.get("id"), "channel": cid, "title": title,
                    "at": when, "format": fmt,
                    "url": m.get("permalink") or m.get("permalink_url"),
                    "likes": likes, "comments": comments, "shares": shares,
                    "engagement": eng or None, "reach": None,
                    "impressions": None})
    return out


def _meta_demographics(cid, obj_id):
    """Age, gender and country splits, as Meta really returns them:
    lifetime breakdowns keyed 'M.25-34' or by country code."""
    r, tok = _requests(), _env("META_ACCESS_TOKEN")
    v = _env("META_API_VERSION") or "v21.0"
    metric = ("follower_demographics" if cid == "instagram"
              else "page_fans_gender_age,page_fans_country")
    j = r.get(f"https://graph.facebook.com/{v}/{obj_id}/insights",
              params={"metric": metric, "period": "lifetime",
                      "access_token": tok}, timeout=30).json()
    age, gender, country = {}, {}, {}
    for row in (j.get("data") or []):
        vals = (row.get("values") or [{}])[-1].get("value") or {}
        if not isinstance(vals, dict):
            continue
        for k, n in vals.items():
            if "." in str(k):
                g, band = str(k).split(".", 1)
                gender[g] = gender.get(g, 0) + float(n or 0)
                age[band] = age.get(band, 0) + float(n or 0)
            elif len(str(k)) == 2:
                country[k] = float(n or 0)
    return {"age": age, "gender": gender, "country": country}


def _linkedin_demographics():
    r = _requests()
    urn = _env("LINKEDIN_ORG_URN")
    H = {"Authorization": "Bearer " + _env("LINKEDIN_ORG_TOKEN"),
         "LinkedIn-Version": _env("LINKEDIN_API_VERSION") or "202409",
         "X-Restli-Protocol-Version": "2.0.0"}
    j = r.get("https://api.linkedin.com/rest/"
              "organizationalEntityFollowerStatistics"
              f"?q=organizationalEntity&organizationalEntity={urn}",
              headers=H, timeout=30).json()
    el = (j.get("elements") or [{}])[0]

    def _pick(key, label):
        out = {}
        for row in (el.get(key) or []):
            n = ((row.get("followerCounts") or {})
                 .get("organicFollowerCount") or 0)
            out[str(row.get(label) or "?").split(":")[-1]] = float(n)
        return out

    return {"seniority": _pick("followerCountsBySeniority", "seniority"),
            "function": _pick("followerCountsByFunction", "function"),
            "industry": _pick("followerCountsByIndustry", "industry"),
            "company_size": _pick("followerCountsByStaffCountRange",
                                  "staffCountRange")}


def _meta_inbox(cid, obj_id):
    """Comments waiting on a reply - the social equivalent of an inbox."""
    r, tok = _requests(), _env("META_ACCESS_TOKEN")
    v = _env("META_API_VERSION") or "v21.0"
    edge = "media" if cid == "instagram" else "posts"
    j = r.get(f"https://graph.facebook.com/{v}/{obj_id}/{edge}",
              params={"fields": "id,comments{id,message,from,created_time}",
                      "limit": 10, "access_token": tok}, timeout=30).json()
    out = []
    for m in (j.get("data") or []):
        for c in ((m.get("comments") or {}).get("data") or []):
            out.append({"channel": cid, "post": m.get("id"),
                        "id": c.get("id"),
                        "text": (c.get("message") or "")[:140],
                        "who": ((c.get("from") or {}).get("name") or "someone"),
                        "at": c.get("created_time")})
    return out


def _linkedin_posts():
    r = _requests()
    urn = _env("LINKEDIN_ORG_URN")
    H = {"Authorization": "Bearer " + _env("LINKEDIN_ORG_TOKEN"),
         "LinkedIn-Version": _env("LINKEDIN_API_VERSION") or "202409",
         "X-Restli-Protocol-Version": "2.0.0"}
    j = r.get(f"https://api.linkedin.com/rest/posts?author={urn}"
              "&q=author&count=25", headers=H, timeout=30).json()
    return [{"id": m.get("id"), "channel": "linkedin",
             "title": str(m.get("commentary") or "")[:90],
             "at": m.get("createdAt"), "format": "post",
             "likes": None, "comments": None, "shares": None,
             "engagement": None, "reach": None, "impressions": None}
            for m in (j.get("elements") or [])]


def _x_posts():
    """X's free tier gives each tweet's counts. Impressions are a paid-tier
    field and stay None rather than being guessed at."""
    r = _requests()
    uid = _env("TWITTER_USER_ID")
    H = {"Authorization": "Bearer " + _env("TWITTER_BEARER_TOKEN")}
    j = r.get(f"https://api.twitter.com/2/users/{uid}/tweets",
              params={"max_results": 25,
                      "tweet.fields": "created_at,public_metrics,text"},
              headers=H, timeout=30).json()
    out = []
    for m in (j.get("data") or []):
        pm = m.get("public_metrics") or {}
        eng = sum(float(pm.get(k) or 0) for k in
                  ("like_count", "reply_count", "retweet_count",
                   "quote_count"))
        out.append({"id": m.get("id"), "channel": "x",
                    "title": (m.get("text") or "")[:90],
                    "at": m.get("created_at"), "format": "tweet",
                    "likes": pm.get("like_count"),
                    "comments": pm.get("reply_count"),
                    "shares": pm.get("retweet_count"),
                    "engagement": eng or None,
                    "impressions": pm.get("impression_count"),
                    "reach": None})
    return out


def _youtube_posts():
    import content_engine_connectors as C
    fn = getattr(C, "_google_token", None)
    tok = fn(["https://www.googleapis.com/auth/youtube.readonly"]) if fn else None
    if not tok:
        return []
    r = _requests()
    H = {"Authorization": "Bearer " + tok}
    j = r.get("https://www.googleapis.com/youtube/v3/search",
              params={"part": "snippet",
                      "channelId": _env("YOUTUBE_CHANNEL_ID"),
                      "order": "date", "maxResults": 25, "type": "video"},
              headers=H, timeout=30).json()
    ids = [i.get("id", {}).get("videoId") for i in (j.get("items") or [])]
    ids = [i for i in ids if i]
    if not ids:
        return []
    st = r.get("https://www.googleapis.com/youtube/v3/videos",
               params={"part": "snippet,statistics", "id": ",".join(ids[:25])},
               headers=H, timeout=30).json()
    out = []
    for v_ in (st.get("items") or []):
        s, k = v_.get("snippet") or {}, v_.get("statistics") or {}
        eng = sum(float(k.get(x) or 0) for x in ("likeCount", "commentCount"))
        out.append({"id": v_.get("id"), "channel": "youtube",
                    "title": (s.get("title") or "")[:90],
                    "at": s.get("publishedAt"), "format": "video",
                    "likes": k.get("likeCount"),
                    "comments": k.get("commentCount"), "shares": None,
                    "engagement": eng or None,
                    "impressions": k.get("viewCount"), "reach": None})
    return out


def fetch_posts(cid):
    """Recent posts with real metrics; [] when the key is not there yet."""
    if missing_keys(cid) or not _requests():
        return []
    try:
        if cid == "facebook":
            return _meta_posts(cid, _env("META_PAGE_ID"))
        if cid == "instagram":
            return _meta_posts(cid, _env("IG_BUSINESS_ID"))
        if cid == "linkedin":
            return _linkedin_posts()
        if cid == "x":
            return _x_posts()
        if cid == "youtube":
            return _youtube_posts()
    except Exception as e:
        log.warning("%s posts failed: %s", cid, e)
    return []


def fetch_demographics(cid):
    if missing_keys(cid) or not _requests():
        return {}
    try:
        if cid == "facebook":
            return _meta_demographics(cid, _env("META_PAGE_ID"))
        if cid == "instagram":
            return _meta_demographics(cid, _env("IG_BUSINESS_ID"))
        if cid == "linkedin":
            return _linkedin_demographics()
    except Exception as e:
        log.warning("%s demographics failed: %s", cid, e)
    return {}


def fetch_inbox(cid):
    if missing_keys(cid) or not _requests():
        return []
    try:
        if cid == "facebook":
            return _meta_inbox(cid, _env("META_PAGE_ID"))
        if cid == "instagram":
            return _meta_inbox(cid, _env("IG_BUSINESS_ID"))
    except Exception as e:
        log.warning("%s inbox failed: %s", cid, e)
    return []


def best_time(rows):
    """Day x time-of-day engagement, computed from REAL posts. Empty until
    posts carry engagement, because a heatmap of nothing is a decoration."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    slots = ["00-04", "04-08", "08-12", "12-16", "16-20", "20-24"]
    grid = [[0.0] * len(slots) for _ in days]
    n = 0
    for r in rows or ():
        if not isinstance(r, dict) or not r.get("engagement"):
            continue
        raw = str(r.get("at") or "")[:19].replace("Z", "")
        try:
            from datetime import datetime
            t = datetime.fromisoformat(raw)
        except Exception:
            continue
        grid[t.weekday()][min(t.hour // 4, 5)] += float(r["engagement"])
        n += 1
    if not n:
        return {}
    mx = max(max(row) for row in grid) or 1.0
    return {"rows": days, "cols": slots, "posts": n,
            "grid": [[round(v / mx * 100) for v in row] for row in grid]}


# ---------------------------------------------------------------------------
# COMPETITORS - public profiles you name, measured by each channel's own key
# ---------------------------------------------------------------------------
COMP_KEY = "social_competitors"


def competitors(store):
    try:
        v = store.get_setting(COMP_KEY, []) or []
        return [c for c in v if isinstance(c, dict)]
    except Exception:
        return []


def track_competitor(store, channel, handle):
    """Add a rival to watch. Public profiles only; the measuring is done by
    that channel's own key, so an untracked channel says so instead of
    inventing a follower count."""
    handle = str(handle or "").strip().lstrip("@")
    if channel not in ORDER:
        return {"ok": False, "error": f"{channel} is not a tracked channel"}
    if not handle:
        return {"ok": False, "error": "no handle given; nothing added"}
    cur = competitors(store)
    if any(c.get("channel") == channel and c.get("handle") == handle
           for c in cur):
        return {"ok": True, "message": f"{handle} is already tracked"}
    cur.append({"channel": channel, "handle": handle, "added": _now(),
                "followers": None, "posts": None, "engagement": None,
                "reason": (NAME[channel] + " public metrics need that "
                           "channel's key on Connect")})
    store.set_setting(COMP_KEY, cur)
    return {"ok": True, "count": len(cur),
            "message": f"tracking {handle} on {NAME[channel]}"}


def untrack_competitor(store, channel, handle):
    cur = competitors(store)
    keep = [c for c in cur
            if not (c.get("channel") == channel and c.get("handle") == handle)]
    store.set_setting(COMP_KEY, keep)
    return {"ok": True, "count": len(keep),
            "message": f"stopped tracking {handle}"}


# ---------------------------------------------------------------------------
def refresh(store) -> dict:
    """Pull every connected channel; keep the honest blanks for the rest.
    One snapshot the screens and the agent both read."""
    snap = {"at": _now(), "channels": {}}
    for cid in ORDER:
        c = fetch(cid)
        if c.get("connected"):
            c["posts_rows"] = fetch_posts(cid)
            c["demographics"] = fetch_demographics(cid)
            c["inbox"] = fetch_inbox(cid)
            c["best_time"] = best_time(c["posts_rows"])
            if c.get("posts") is None and c["posts_rows"]:
                c["posts"] = len(c["posts_rows"])
        snap["channels"][cid] = c
    live = [c for c, v in snap["channels"].items() if v.get("connected")]
    snap["live"] = live
    try:
        hist = store.get_setting("social_history", []) or []
        row = {"date": _now()[:10]}
        for cid in ORDER:
            f = snap["channels"][cid].get("followers")
            if f is not None:
                row[cid] = f
        if len(row) > 1:
            hist = [h for h in hist if h.get("date") != row["date"]] + [row]
            store.set_setting("social_history", hist[-90:])
        store.set_setting(SETTING_KEY, snap)
    except Exception as e:
        log.warning("social snapshot save failed: %s", e)
    snap["message"] = (f"{len(live)} of {len(ORDER)} channels reporting"
                       + (f": {', '.join(NAME[c] for c in live)}" if live
                          else ". Add a channel's key on Connect and it "
                               "lights up here."))
    return snap


def load(store) -> dict:
    try:
        return store.get_setting(SETTING_KEY, {}) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = []

    def t(n, c):
        ok.append(bool(c))
        print(("  OK   " if c else "  FAIL ") + n)

    t("registry has 7 channels", len(CHANNELS) == 7 and len(ORDER) == 7)
    t("every channel names its keys", set(KEYS) == set(ORDER))
    b = _blank("instagram", "x")
    t("a blank has every slot", all(s in b for s in SLOTS))
    t("a blank is never zero", all(b[s] is None for s in SLOTS))
    t("an unkeyed channel is not connected", connected("instagram") is False)
    r = reason_for("instagram")
    t("the reason names the exact keys",
      "META_ACCESS_TOKEN" in r and "IG_BUSINESS_ID" in r)
    f = fetch("instagram")
    t("fetch on no key returns the blank, not a crash",
      f["connected"] is False and f["followers"] is None)
    t("an unknown channel is refused",
      fetch("myspace")["connected"] is False)

    class _S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v

    s = _S()
    snap = refresh(s)
    t("refresh covers every channel", len(snap["channels"]) == 7)
    t("refresh reports 0 live honestly",
      snap["live"] == [] and "lights up" in snap["message"])
    t("nothing invented into history", s.d.get("social_history") is None)
    t("every blank carries the later layers",
      all(k in b for k in ("posts_rows", "demographics", "inbox", "paid")))
    t("posts/demographics/inbox are empty without a key",
      fetch_posts("facebook") == [] and fetch_demographics("facebook") == {}
      and fetch_inbox("facebook") == [])
    t("best_time on nothing is empty, not a fake grid", best_time([]) == {})
    _bt = best_time([{"at": "2026-08-03T09:15:00", "engagement": 40},
                     {"at": "2026-08-05T19:00:00", "engagement": 10}])
    t("best_time on real posts is a 7x6 grid",
      len(_bt.get("grid", [])) == 7 and len(_bt["grid"][0]) == 6
      and _bt["posts"] == 2)
    t("the busiest slot is the strongest", _bt["grid"][0][2] == 100)
    t("a competitor needs a real handle",
      track_competitor(s, "linkedin", "")["ok"] is False)
    t("an unknown channel is refused",
      track_competitor(s, "myspace", "x")["ok"] is False)
    t("a tracked rival starts with no invented numbers",
      track_competitor(s, "linkedin", "@rival")["ok"] is True
      and competitors(s)[0]["followers"] is None)
    t("tracking twice does not duplicate",
      track_competitor(s, "linkedin", "rival")["ok"] is True
      and len(competitors(s)) == 1)
    t("untrack removes it",
      untrack_competitor(s, "linkedin", "rival")["count"] == 0)
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
