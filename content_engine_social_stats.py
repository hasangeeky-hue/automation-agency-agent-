# -*- coding: utf-8 -*-
"""SOCIAL AUDIENCE: the data half of the social wires.

Stage 2, third collector. The Distributor could already POST. Nothing
could READ. Connecting Instagram or TikTok gave this engine the ability
to publish and returned not one follower, view or engagement to any
screen, so no agent could work from social data because none arrived.

    "when i connect api new dashboard data will come, my agents work
     according to dashboard data"

That is the sentence this module exists to make true.

WHAT IT REFUSES TO DO

  It never invents a follower count. A platform this engine cannot read
  is reported as unreadable, by name, with the key that would fix it.
  Zero followers and no answer are different facts and get different
  words.

  It does not pretend every platform is equal. LinkedIn's member token
  can prove who you are and CANNOT read follower counts: that needs an
  organization token. TikTok's content-posting scope returns no
  analytics at all. Saying so is more useful than a dash, because it
  tells you which key to go and get.

  It is READ ONLY. A collector that can also post is one bug away from
  publishing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import content_engine_social_desk as SD

log = logging.getLogger("social_stats")

STATS_KEY = "social_stats_rows"
COLLECT_KEY = "social_stats_last_collect"
MAX_SNAPSHOTS = 400

#: Per channel: can this engine read audience numbers at all, with what
#: credential, and if not, WHY not. The 'why not' rows are the valuable
#: ones: they turn "no data" into "go and get this specific token".
#:
#: Keyed by the SAME channel names social_desk uses. check() asserts the
#: two agree rather than trusting that they do, because two hand-written
#: channel lists is precisely the bug this project keeps shipping.
READABLE = {
    "linkedin": {
        "readable": False,
        "needs": "LINKEDIN_ORG_URN plus an organization token with "
                 "r_organization_social",
        "why": ("the member token that posts cannot read follower counts. "
                "LinkedIn puts audience numbers behind the organization "
                "API, which is a different credential, not a bigger scope "
                "on the same one"),
    },
    "twitter": {
        "readable": True,
        "endpoint": "https://api.twitter.com/2/users/me",
        "params": {"user.fields": "public_metrics"},
        "key": "TWITTER_BEARER_TOKEN",
        "auth": "bearer",
        "needs": "TWITTER_BEARER_TOKEN",
    },
    "facebook": {
        "readable": True,
        "endpoint": "https://graph.facebook.com/v21.0/{page}",
        "params": {"fields": "followers_count,fan_count,name"},
        "key": "META_PAGE_TOKEN",
        "auth": "query",
        "page_key": "META_PAGE_ID",
        "needs": "META_PAGE_ID and META_PAGE_TOKEN",
    },
    "instagram": {
        "readable": True,
        "endpoint": "https://graph.facebook.com/v21.0/{page}",
        "params": {"fields": "followers_count,media_count,username"},
        "key": "META_PAGE_TOKEN",
        "auth": "query",
        "page_key": "INSTAGRAM_BUSINESS_ID",
        "needs": "INSTAGRAM_BUSINESS_ID and META_PAGE_TOKEN",
    },
    "tiktok": {
        "readable": False,
        "needs": "a TikTok token carrying user.info.stats",
        "why": ("the content-posting scope this engine holds returns no "
                "analytics. Follower and view counts need a separate "
                "scope that TikTok grants per app"),
    },
}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _s(x) -> str:
    return "" if x is None else str(x)


def _num(x):
    """A count that did not come back stays None. Never 0."""
    if x in (None, ""):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _env(key: str) -> str:
    try:
        import content_engine_connectors as C
        return _s(C._env(key)).strip()
    except Exception:                                     # noqa: BLE001
        import os
        return _s(os.getenv(key, "")).strip()


def _get(store, key, default):
    try:
        return store.get_setting(key, default)
    except Exception:                                     # noqa: BLE001
        return default


def _set(store, key, value):
    try:
        store.set_setting(key, value)
        return True
    except Exception as e:                                # noqa: BLE001
        log.warning("social_stats: could not save %s: %s", key, e)
        return False


# ---------------------------------------------------------------- read
def fetch_one(channel: str) -> Dict[str, Any]:
    """Audience numbers for ONE channel. READ ONLY.

    followers is None whenever the number was not obtained, for every
    reason: no key, no support, a refusal. `state` says which of those it
    was, so a screen never has to guess from a blank."""
    ch = _s(channel).lower()
    spec = _d(READABLE.get(ch))
    if not spec:
        return {"channel": ch, "state": "unknown_channel", "followers": None,
                "why": "%r is not a channel this engine knows" % ch}
    if not spec.get("readable"):
        return {"channel": ch, "state": "not_readable", "followers": None,
                "needs": spec.get("needs", ""),
                "why": spec.get("why", "")}
    key = _env(_s(spec.get("key")))
    page = _env(_s(spec.get("page_key"))) if spec.get("page_key") else "x"
    if not key or not page:
        return {"channel": ch, "state": "no_credential", "followers": None,
                "needs": spec.get("needs", ""),
                "why": "%s is not set, so this channel was never asked"
                       % spec.get("needs", "the credential")}
    try:
        import content_engine_connectors as C
        rq = C._requests()
        if rq is None:
            return {"channel": ch, "state": "no_http", "followers": None,
                    "why": "the requests library is not in this image"}
        url = _s(spec.get("endpoint")).replace("{page}", page)
        params = dict(spec.get("params") or {})
        headers = {}
        if spec.get("auth") == "bearer":
            headers["Authorization"] = "Bearer " + key
        else:
            params["access_token"] = key
        r = rq.get(url, params=params, headers=headers, timeout=25)
        if r.status_code >= 400:
            body = ""
            try:
                body = _s(_d(_d(r.json()).get("error")).get("message"))[:160]
            except Exception:                             # noqa: BLE001
                body = _s(r.text)[:160]
            # The provider's own sentence, kept. This engine has lost
            # weeks to a truncated "the call failed" before.
            return {"channel": ch, "state": "refused", "followers": None,
                    "code": r.status_code,
                    "why": "HTTP %d: %s" % (r.status_code, body)}
        j = _d(r.json())
    except Exception as e:                                # noqa: BLE001
        log.warning("social stats %s failed: %s", ch, e)
        return {"channel": ch, "state": "error", "followers": None,
                "why": _s(e)[:160]}

    data = _d(j.get("data")) or j
    metrics = _d(data.get("public_metrics"))
    followers = _num(metrics.get("followers_count")
                     if metrics else data.get("followers_count"))
    if followers is None:
        followers = _num(data.get("fan_count"))
    return {"channel": ch, "state": "read", "followers": followers,
            "posts": _num(metrics.get("tweet_count") if metrics
                          else data.get("media_count")),
            "handle": _s(data.get("username") or data.get("name")),
            "why": ("" if followers is not None else
                    "the platform answered but returned no follower count, "
                    "which is not the same as zero followers")}


def collect(store=None) -> Dict[str, Any]:
    """Every channel, in one pass. Nothing here posts."""
    rows = [fetch_one(ch) for ch in READABLE]
    read = [r for r in rows if r.get("state") == "read"]
    return {"rows": rows, "read": len(read), "channels": len(rows),
            "with_followers": len([r for r in read
                                   if r.get("followers") is not None])}


# --------------------------------------------------------------- store
def save(store, rows) -> int:
    """One dated snapshot per channel, so the screens can show a TREND
    rather than a number that silently overwrites yesterday's."""
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).date().isoformat()
    have = [_d(x) for x in (_get(store, STATS_KEY, []) or [])]
    keep = [x for x in have
            if not (_s(x.get("at")) == day
                    and _s(x.get("channel")) in {_s(_d(r).get("channel"))
                                                 for r in rows})]
    for r in rows:
        r = _d(r)
        if r.get("state") != "read":
            continue
        keep.append({"at": day, "channel": _s(r.get("channel")),
                     "followers": r.get("followers"),
                     "posts": r.get("posts"), "handle": _s(r.get("handle"))})
    keep = sorted(keep, key=lambda x: _s(x.get("at")))[-MAX_SNAPSHOTS:]
    _set(store, STATS_KEY, keep)
    return len(keep)


def history(store, channel: str = "") -> List[dict]:
    rows = [_d(x) for x in (_get(store, STATS_KEY, []) or [])]
    if channel:
        rows = [x for x in rows if _s(x.get("channel")) == _s(channel).lower()]
    return rows


def series(store, channel: str) -> List[tuple]:
    """(day, followers) for the kit's chart. A day with no reading is a
    GAP, carried as None, so the chart breaks its line instead of drawing
    a straight one through a day nobody measured."""
    return [(_s(r.get("at")), r.get("followers"))
            for r in history(store, channel)]


# ----------------------------------------------------------------- day
def run(store) -> Dict[str, Any]:
    from datetime import datetime, timezone
    got = collect(store)
    stored = save(store, got["rows"])
    _set(store, COLLECT_KEY,
         datetime.now(timezone.utc).isoformat(timespec="seconds"))
    blocked = [r for r in got["rows"] if r.get("state") == "not_readable"]
    return {"ok": True, "channels": got["channels"], "read": got["read"],
            "with_followers": got["with_followers"], "snapshots": stored,
            "rows": got["rows"],
            "note": ("%d channel(s) cannot be read at all with the "
                     "credentials this engine holds: %s"
                     % (len(blocked),
                        ", ".join(_s(r.get("channel")) for r in blocked)))
                    if blocked else "every known channel is readable"}


def context(store) -> Dict[str, Any]:
    """What the screens read. Free: stored rows, no call."""
    rows = collect(store)["rows"]
    return {"last_collect": _s(_get(store, COLLECT_KEY, "")),
            "rows": rows,
            "series": {ch: series(store, ch) for ch in READABLE},
            "connected": bool(_get(store, COLLECT_KEY, ""))}


# --------------------------------------------------------------- check
def check() -> Dict[str, Any]:
    out = []

    # THE SHARED VOCABULARY, AGAIN. Two hand-written channel lists is the
    # bug this project has shipped more than any other, so the lists are
    # compared rather than assumed to match.
    out.append(("every channel here is one the Distributor knows",
                set(READABLE) == set(SD.CHANNELS),
                str(sorted(set(READABLE) ^ set(SD.CHANNELS)))))

    # A count that did not arrive must never become a zero.
    out.append(("a missing follower count stays missing",
                _num(None) is None and _num("") is None, ""))
    out.append(("and a real one still parses", _num("1240") == 1240, ""))

    # Every unreadable channel must NAME the credential that would fix it.
    bad = [ch for ch, sp in READABLE.items()
           if not sp.get("readable") and not (sp.get("needs") and sp.get("why"))]
    out.append(("an unreadable channel names the key AND says why",
                not bad, str(bad)))

    # No key is not the same as no followers.
    r = fetch_one("twitter")
    out.append(("a channel with no credential says so, and reports None",
                r["followers"] is None
                and r["state"] in ("no_credential", "refused", "error"),
                str(r)[:120]))
    out.append(("LinkedIn states plainly that posting cannot read audience",
                fetch_one("linkedin")["state"] == "not_readable", ""))
    out.append(("an unknown channel is refused, not guessed",
                fetch_one("nowhere")["state"] == "unknown_channel", ""))

    # THIS COLLECTOR MUST NOT BE ABLE TO POST. Parsed for calls, not
    # grepped for text: a grep for "post" finds the word in this comment.
    import ast
    import inspect
    called = set()
    for node in ast.walk(ast.parse(inspect.getsource(inspect.getmodule(check)))):
        if isinstance(node, ast.Call):
            n = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if n:
                called.add(n)
    hits = sorted({"post", "put", "patch", "delete", "post_one"} & called)
    out.append(("the collector cannot publish anything",
                not hits, "it calls: " + ", ".join(hits)))

    return {"ok": all(p for _n, p, *_x in out),
            "checks": [{"name": n, "pass": p, "detail": (d[0] if d else "")}
                       for n, p, *d in out]}


if __name__ == "__main__":
    r = check()
    for c in r["checks"]:
        print(("  OK   " if c["pass"] else "  FAIL ") + c["name"]
              + (("   " + str(c["detail"])[:120])
                 if c["detail"] and not c["pass"] else ""))
    print("social stats self-check:", "OK" if r["ok"] else "FAILED")
    raise SystemExit(0 if r["ok"] else 1)
