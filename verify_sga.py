# -*- coding: utf-8 -*-
"""GATES FOR THE SOCIAL ANALYTICS SECTION. Every promise, made falsifiable.

The one that matters most: a channel with no read key must show NOTHING
rather than a zero. A zero is a measurement; an absent API is not, and a
dashboard that cannot tell them apart is worse than no dashboard.
"""
from __future__ import annotations

import io
import re
import sys
import traceback

PASS, FAIL = [], []


def gate(n, name):
    def deco(fn):
        try:
            PASS.append((n, name, fn() or ""))
        except AssertionError as ex:
            FAIL.append((n, name, str(ex)))
        except Exception as ex:
            FAIL.append((n, name, f"{type(ex).__name__}: {ex}\n"
                                  + traceback.format_exc(limit=3)))
        return fn
    return deco


import content_engine_social_insights as SI
import content_engine_sga_screens as SGS
import content_engine_sga_boards as SB


class _S:
    def __init__(self, d=None): self.d = dict(d or {})
    def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
    def set_setting(self, k, v): self.d[k] = v


@gate(1, "one channel registry, imported everywhere")
def _g1():
    assert len(SI.CHANNELS) == 7 and set(SI.KEYS) == set(SI.ORDER)
    src = io.open("content_engine_sga_screens.py", encoding="utf-8").read()
    assert "SI.ORDER" in src and "SI.NAME" in src, (
        "the screens must import the registry, not retype the channels")
    boards = io.open("content_engine_sga_boards.py", encoding="utf-8").read()
    assert "content_engine_social_insights" in boards
    return f"{len(SI.CHANNELS)} channels: {', '.join(SI.ORDER)}"


@gate(2, "a channel with no key shows NOTHING, never a zero")
def _g2():
    for cid in SI.ORDER:
        b = SI.fetch(cid)
        assert b["connected"] is False
        for slot in SI.SLOTS:
            assert b[slot] is None, (
                f"{cid}.{slot} is {b[slot]!r}; an absent API must render as "
                f"absent, and 0 is a measurement")
    html = SGS.channel_panel({}, "instagram")
    assert "sg-none" in html, "the honest dash is missing from the tile"
    assert ">0<" not in html.replace("</b>0<", ""), "a zero leaked into a tile"
    return "7 channels, 6 slots each, 0 invented numbers"


@gate(3, "every empty state names the exact missing setting")
def _g3():
    for cid in SI.ORDER:
        r = SI.reason_for(cid)
        assert r, f"{cid} has no reason"
        for k in SI.missing_keys(cid):
            assert k in r, f"{cid} reason does not name {k}"
    html = SGS.channel_panel({}, "linkedin")
    assert "LINKEDIN_ORG_TOKEN" in html and "LINKEDIN_ORG_URN" in html
    return "7 reasons, each naming its keys"


@gate(4, "the fourteen panels render on empty and hostile contexts")
def _g4():
    shapes = ({}, None, "not a dict", 42,
              {k: None for k in ("social", "posts", "traffic", "revenue",
                                 "paid", "budget", "hub", "blog", "calendar",
                                 "creatives", "engagement", "campaigns")},
              {"traffic": {"channels": "notalist"}, "revenue": {"waterfall": 5}},
              {"social": {"channels": "bad"}, "social_history": "bad"})
    for ctx in shapes:
        p = SGS.build_panels(ctx)
        assert len(p) == 14, f"{len(p)} panels on {type(ctx).__name__}"
        for tid, h in p.items():
            assert h and len(h) > 60, f"{tid} rendered nothing"
    return f"14 panels, {len(shapes)} context shapes, no crash"


@gate(5, "the tile and chart budget is met")
def _g5():
    p = SGS.build_panels({})
    tiles = sum(h.count("class='sg-tile'") for h in p.values())
    charts = sum(h.count("class='sg-chart'") for h in p.values())
    assert tiles >= 90, f"only {tiles} tiles"
    assert charts >= 30, f"only {charts} charts"
    return f"{tiles} tiles, {charts} charts across 14 screens"


@gate(6, "all seven channels sit behind ONE switcher")
def _g6():
    p = SGS.build_panels({})
    holders = [t for t, h in p.items() if "a3swbar" in h]
    assert holders == ["sgachannels"], (
        f"the channel environment must live on one tab, found {holders}")
    env = p["sgachannels"]
    for cid in SI.ORDER:
        assert f"sg-c-{cid}" in env, f"{cid} is not in the environment"
        assert f"sgChan('{cid}')" in env, f"{cid} has no switch button"
    return "7 channels, one switcher, one tab"


@gate(7, "every chart carries a title and an honest empty state")
def _g7():
    p = SGS.build_panels({})
    for tid, h in p.items():
        titles = h.count("class='sg-ct'")
        charts = h.count("class='sg-chart'")
        assert titles == charts, f"{tid}: {charts} charts, {titles} titles"
    blank = SGS.chart("X", "", "because the key is missing")
    assert "because the key is missing" in blank
    assert "sg-empty" in blank
    return "every chart titled; empty states explain themselves"


@gate(8, "the section replaced the cards and carries its own clothes")
def _g8():
    sec = SB.sga_section({})
    stray = re.findall(r"<div class='card (?:overflowcard )?sev-", sec)
    assert not stray, f"{len(stray)} old cards still render"
    for need in ("class='sg-tile'", "class='sg-chart'", "a3swbar",
                 "function sgChan(", ".seoscr{"):
        assert need in sec, f"section missing {need}"
    ids = re.findall(r"\sid='([^']+)'", sec)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    assert not dup, f"duplicate ids: {dup[:6]}"
    return f"0 cards, {len(ids)} unique ids, handlers and styles aboard"


@gate(9, "refresh reports honestly and invents no history")
def _g9():
    s = _S()
    snap = SI.refresh(s)
    assert len(snap["channels"]) == 7 and snap["live"] == []
    assert "lights up" in snap["message"]
    assert s.d.get("social_history") is None, (
        "a refresh with nothing measured wrote a history row anyway")
    return "0 live reported honestly, 0 history rows invented"


@gate(10, "the endpoint, the cadence and the ctx keys are wired")
def _g10():
    api = io.open("content_engine_api.py", encoding="utf-8").read()
    assert '"/social/refresh"' in api, "no refresh endpoint"
    import content_engine_scheduler as S
    assert S.SEO_CADENCE.get("social", {}).get("every_days") == 1
    import content_engine_seo_ops as O
    assert hasattr(O, "run_social")
    ctx = O.build_sga_ctx(_S())
    for k in ("social", "social_history"):
        assert k in ctx, f"build_sga_ctx lost {k}"
    return "endpoint, daily cadence, and both ctx keys"


@gate(11, "the eight analytics keys are on the Connect board")
def _g11():
    import content_engine_dashboard as D
    keys = {k for _t, _s, _w, fs in D.EXTRA_KEY_GROUPS for k, _h in fs}
    need = {"META_PAGE_ID", "IG_BUSINESS_ID", "LINKEDIN_ORG_TOKEN",
            "LINKEDIN_ORG_URN", "TIKTOK_BUSINESS_ID", "TWITTER_USER_ID",
            "YOUTUBE_CHANNEL_ID", "GBP_LOCATION_NAME"}
    missing = sorted(need - keys)
    assert not missing, f"no field on the Connect board for: {missing}"
    # and every field the module reads must be settable there
    for cid in SI.ORDER:
        for k in SI.KEYS[cid]:
            assert k in keys or k in ("META_ACCESS_TOKEN",
                                      "TIKTOK_ACCESS_TOKEN",
                                      "TWITTER_BEARER_TOKEN"), (
                f"{k} is read by the module but cannot be set on the board")
    return f"{len(need)} analytics fields, all settable from the front end"


@gate(12, "the screens never fetch, post or write")
def _g12():
    src = io.open("content_engine_sga_screens.py", encoding="utf-8").read()
    for bad in ("requests.", "httpx.", "urlopen", "subprocess",
                "store.set_setting", ".post(", "SI.refresh"):
        assert bad not in src, f"the renderer contains {bad}"
    return "renderer only, no side effects"


_POSTS = [{"id": "1", "channel": "instagram", "title": "A", "format": "REEL",
           "at": "2026-08-03T09:15:00", "likes": 210, "comments": 18,
           "shares": 12, "engagement": 240, "reach": 5400,
           "impressions": 7200},
          {"id": "2", "channel": "instagram", "title": "B", "format": "IMAGE",
           "at": "2026-08-05T19:00:00", "likes": 90, "comments": 6,
           "shares": 4, "engagement": 100, "reach": 2100,
           "impressions": 2600}]
_RICH = {"social": {"at": "2026-08-06T12:00", "live": ["instagram"],
         "channels": {"instagram": {
             "channel": "instagram", "name": "Instagram", "connected": True,
             "followers": 980, "reach": 15300, "impressions": 22100,
             "engagement": 740, "clicks": 95, "posts": 52,
             "reactions": {"likes": 600, "comments": 90, "shares": 50},
             "posts_rows": _POSTS, "best_time": SI.best_time(_POSTS),
             "demographics": {"age": {"25-34": 420, "35-44": 300},
                              "gender": {"F": 520, "M": 440},
                              "country": {"DE": 610, "US": 210}},
             "inbox": [{"channel": "instagram", "who": "Dr. Weber",
                        "text": "Do you work outside Munich?",
                        "at": "2026-08-06T08:40:00"}],
             "paid": {"spend": 240, "cpm": 6.2, "cpc": 0.41,
                      "cost_per_result": 21.8, "results": 11}}}},
         "social_history": [{"date": f"2026-08-{d:02d}",
                             "instagram": 950 + d * 3} for d in range(1, 8)],
         "competitors": [{"channel": "instagram", "handle": "rival.io",
                          "followers": None, "posts": None,
                          "engagement": None}]}


@gate(13, "the post table shows each post's OWN measured metrics")
def _g13():
    h = SGS.build_panels(_RICH)["sgaorganic"]
    assert "210" in h and "5.4k" in h, "per-post metrics did not render"
    assert h.count("class='sg-tr'") == 2, "both posts must be rows"
    for col in ("Likes", "Comments", "Shares", "Reach", "Engagement"):
        assert col in h, f"the {col} column is missing"
    blank = SGS.build_panels({})["sgaorganic"]
    assert "sg-none" in blank or "No posts on record" in blank
    return "2 posts, 5 metric columns, honest when empty"


@gate(14, "the best-time heatmap is computed from real posts, never faked")
def _g14():
    assert SI.best_time([]) == {}, "an empty heatmap must stay empty"
    bt = SI.best_time(_POSTS)
    assert len(bt["grid"]) == 7 and len(bt["grid"][0]) == 6
    assert bt["grid"][0][2] == 100, "the busiest slot must be the strongest"
    h = SGS.build_panels(_RICH)["sgaaudience"]
    assert "<svg" in h and "from 2 posts" in h, "the heatmap did not draw"
    empty = SGS.build_panels({})["sgaaudience"]
    assert "as soon as a channel reports" in empty
    return "7x6 grid from 2 real posts; empty stays empty"


@gate(15, "demographics render from what the platforms really return")
def _g15():
    h = SGS.build_panels(_RICH)["sgaaudience"]
    assert h.count("class='sg-chart'") >= 4, "demographic charts missing"
    for want in ("Age", "Gender", "Top countries"):
        assert want in h, f"{want} chart missing"
    empty = SGS.build_panels({})["sgaaudience"]
    assert "Nothing is estimated here" in empty, (
        "the empty state must refuse to estimate")
    return "age, gender, country drawn; nothing estimated when absent"


@gate(16, "replies are drafted and posted only by a human click")
def _g16():
    # THE CONTRACT GREW. Before, the inbox was read-only and the gate
    # asserted it said so. The founder asked twice for replying, so it is
    # built - and the promise is now stronger, not weaker: the engine may
    # compose and hold a reply, but the send is a click, on a draft the
    # founder wrote, behind a browser confirm.
    h = SGS.build_panels(_RICH)["sgaengage"]
    assert "Dr. Weber" in h and "outside Munich" in h, "the comment is missing"
    assert "sgReply(" in h, "no reply button on a comment"
    assert "Nothing is ever posted without your click" in h, (
        "the reply box must state that nothing sends itself")
    s = _S()
    assert SI.draft_reply(s, {"id": "c1", "channel": "facebook"},
                          "")["ok"] is False, "an empty reply was accepted"
    d = SI.draft_reply(s, {"id": "c1", "channel": "facebook", "who": "Ann",
                           "text": "do you serve Berlin?"}, "We do.")
    assert d["ok"] and "Nothing has been posted" in d["message"]
    assert SI.reply_drafts(s)[0]["status"] == "draft", (
        "a queued reply must never start as sent")
    out = SI.send_reply(s, SI.reply_drafts(s)[0]["id"])
    assert out["ok"] is False and "META_ACCESS_TOKEN" in out["error"], (
        "sending without the key must refuse and name the key")
    # the promise must hold when there are NO comments too - a stale
    # "read-only by design" survived one build after replying was added
    empty = SGS.build_panels({})["sgaengage"]
    assert "read-only by design" not in empty, (
        "the empty inbox still claims to be read-only, which stopped being "
        "true the moment replying was built")
    assert "the send is always your click" in empty
    assert "sg-rt" in empty, "the reply queue must be visible when empty too"
    src = io.open("content_engine_sga_screens.py", encoding="utf-8").read()
    assert "confirm('Post this reply publicly now?')" in src, (
        "posting publicly must pass a browser confirm")
    api = io.open("content_engine_api.py", encoding="utf-8").read()
    for r in ('"/social/reply"', '"/social/reply/send"',
              '"/social/reply/discard"'):
        assert r in api, f"missing route {r}"
    assert "no reply id; nothing sent" in api
    return "drafted, confirmed, clicked; never auto-sent"


@gate(17, "paid tiles show per-channel CPM, CPC and cost per result")
def _g17():
    h = SGS.build_panels(_RICH)["sgapaid"]
    for want in ("CPM", "CPC", "Cost per result", "6.2", "21.8"):
        assert want in h, f"{want} missing from the paid screen"
    empty = SGS.build_panels({})["sgapaid"]
    assert "ADS key" in empty or "ads key" in empty, (
        "the empty state must name the ads key as separate from analytics")
    return "3 cost metrics per channel, averages on the tiles"


@gate(18, "competitors are tracked, listed, and never invented")
def _g18():
    h = SGS.build_panels(_RICH)["sgatarget"]
    assert "rival.io" in h and "sgAddComp" in h and "sgDropComp" in h
    assert h.count("sg-none") >= 3, (
        "a tracked rival with no key must show dashes, not zeros")
    s = _S()
    assert SI.track_competitor(s, "myspace", "x")["ok"] is False
    assert SI.track_competitor(s, "linkedin", "")["ok"] is False
    assert SI.track_competitor(s, "linkedin", "@rival")["ok"] is True
    assert SI.competitors(s)[0]["followers"] is None
    assert len(SI.competitors(s)) == 1
    SI.track_competitor(s, "linkedin", "rival")
    assert len(SI.competitors(s)) == 1, "tracking twice duplicated"
    api = io.open("content_engine_api.py", encoding="utf-8").read()
    assert '"/social/competitor"' in api
    return "add, list, remove; no invented follower counts"


if __name__ == "__main__":
    print("=" * 74)
    print("SOCIAL ANALYTICS GATES")
    print("=" * 74)
    for n, name, d in PASS:
        print(f"  [{n:>2}] PASS  {name}" + (f"\n         {d}" if d else ""))
    for n, name, why in FAIL:
        print(f"  [{n:>2}] FAIL  {name}\n         {why}")
    print("-" * 74)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
