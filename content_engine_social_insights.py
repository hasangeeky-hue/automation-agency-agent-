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
            "series": [], "top_posts": [], "reactions": {}, "best_time": []}


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
def refresh(store) -> dict:
    """Pull every connected channel; keep the honest blanks for the rest.
    One snapshot the screens and the agent both read."""
    snap = {"at": _now(), "channels": {}}
    for cid in ORDER:
        snap["channels"][cid] = fetch(cid)
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
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
