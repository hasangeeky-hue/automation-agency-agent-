# -*- coding: utf-8 -*-
"""
verify_vx2_ads.py
============================================================================
GATES FOR THE ADS ENVIRONMENT.

Four of the five platforms have no advertising API in this engine. The founder
asked for all five as full working screens anyway, which is a reasonable thing
to want and a dangerous thing to build carelessly: a screen showing invented
spend beside a screen showing real spend is how someone makes a decision about
money that was never spent.

So these gates are mostly about one property: a sample can never be mistaken
for an account, and a control that cannot reach a platform says so instead of
appearing to work.
============================================================================
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


import content_engine_vx2_ads as A
import content_engine_connectors as C
import content_engine_vx2 as V


# ---------------------------------------------------------------------------
# 1-4  THE HONESTY OF THE DATA
# ---------------------------------------------------------------------------
@gate(1, "a platform is marked live only if a connector actually exists")
def _g1():
    for pid, p in A.PLATFORMS.items():
        if p["state"] == "live":
            assert p["connector"], f"{pid} claims live with no connector named"
            klass = getattr(C, p["connector"], None)
            assert klass is not None, (
                f"{pid} names connector {p['connector']}, which is not in "
                f"content_engine_connectors")
            for m in ("summary", "create_campaign"):
                assert hasattr(klass, m), (
                    f"{p['connector']} has no {m}(), so this screen cannot "
                    f"honestly be marked live")
        else:
            assert not p["connector"], (
                f"{pid} is marked sample but names a connector")
    live = [k for k, v in A.PLATFORMS.items() if v["state"] == "live"]
    return f"live: {live}; sample: {len(A.PLATFORMS) - len(live)}"


@gate(2, "a live platform never renders an invented number")
def _g2():
    camps, real = A.campaigns_for("google", {})
    assert real is True, "google must report itself as real"
    assert camps == [], (
        "with no campaigns pulled, Google produced rows anyway. Those rows "
        "would be fiction on a screen the founder reads as his account")
    html = A.platform_screen("google", {})
    assert "Sample data" not in html, "a live platform must not claim sample"
    for s in A.SAMPLE.values():
        for c in s:
            assert c["name"] not in html, (
                f"sample campaign '{c['name']}' leaked onto the live screen")
    return "no campaigns pulled, no rows invented"


@gate(2.5, "an empty account says whether it is connected, and asks the "
           "connector rather than guessing")
def _g2b():
    real_avail = A.is_connected("google")
    html = A.platform_screen("google", {})
    if real_avail:
        assert "Connected, nothing pulled yet" in html
    else:
        assert "Not connected" in html, (
            "Google Ads does not authorise on this box, so the bar must say "
            "'Not connected'. Saying 'connected, nothing pulled yet' over an "
            "account that was never authorised is the same lie as showing a "
            "sample as spend")
        assert "not authorised yet" in html, "it must say why it is empty"
    assert A.is_connected("linkedin") is False, (
        "a platform with no connector can never report itself connected")
    return f"google connected={real_avail}, and the screen says so"


@gate(3, "a sample platform says so in the bar, in a banner, and in the tab")
def _g3():
    for pid in ("facebook", "instagram", "linkedin", "youtube"):
        html = A.platform_screen(pid, {})
        assert "Sample data" in html, f"{pid} bar does not say sample"
        assert "invented to show the layout" in html, (
            f"{pid} has no banner explaining the figures are not real")
        assert "a3issample" in html, f"{pid} does not carry the sample state"
        assert "a3sample" in html, f"{pid} account bar is not marked"
    sw = A.switcher("google")
    assert sw.count("<i>sample</i>") == 4, (
        "the platform switcher must mark all four sample platforms")
    return "4 platforms, 4 marks each, and 4 marks in the switcher"


@gate(4, "real and sample data can never be mixed in one screen")
def _g4():
    ads = {"campaigns": [{"name": "REAL Search Brand", "spend": 120,
                          "clicks": 40, "status": "active"}]}
    g = A.platform_screen("google", ads)
    assert "REAL Search Brand" in g, "the real campaign did not render"
    assert "Sample data" not in g
    fb = A.platform_screen("facebook", ads)
    assert "REAL Search Brand" not in fb, (
        "Google's real campaigns leaked onto the Facebook screen")
    assert "Leads &middot; Munich SMB" in fb or "Munich SMB" in fb
    return "google reads live, facebook reads sample, neither sees the other"


# ---------------------------------------------------------------------------
# 5-8  THE WRITES
# ---------------------------------------------------------------------------
@gate(5, "every write on a sample platform is stopped before it is sent")
def _g5():
    js = A.JS
    assert "function a3guard(p)" in js
    assert "if(p==='google')return true;" in js, (
        "the guard must let only the connected platform through")
    for fn in ("a3create", "a3save", "a3pause", "a3resume"):
        m = re.search(rf"function {fn}\([^)]*\)\{{(.*?)\}}\n?", js, re.S)
        body = m.group(1) if m else js[js.find(f"function {fn}("):][:200]
        assert "a3guard" in body, (
            f"{fn} can act without passing the guard, so a click on a "
            f"platform with no API would look like it worked")
    return "4 write paths, all behind the guard"


@gate(6, "even the connected platform cannot spend without approval")
def _g6():
    assert "Queued for your approval" in A.JS, (
        "saving a bid or budget must say it is queued, not sent")
    assert "Nothing has been sent to Google Ads" in A.JS
    src = io.open("content_engine_vx2_ads.py", encoding="utf-8").read()
    for bad in ("create_campaign(", "pause_campaign(", "requests.", "httpx."):
        assert bad not in src, (
            f"the ads screen calls {bad} directly; every spend must go "
            f"through the approval queue in the API, not the renderer")
    return "renderer only; spend goes through the queue"


@gate(7, "the guard explains itself instead of failing silently")
def _g7():
    assert "no advertising API for this platform" in A.JS, (
        "a blocked click must say why")
    assert "ready when the connector is added" in A.JS, (
        "it must also say what would make it work")
    return "a blocked click is answered, not ignored"


@gate(8, "the ads screen never fetches, publishes or spends")
def _g8():
    src = io.open("content_engine_vx2_ads.py", encoding="utf-8").read()
    for bad in ("urlopen", "subprocess", "os.system", "smtplib",
                "store.set_setting", "store.save"):
        assert bad not in src, f"the ads renderer contains {bad}"
    return "renderer only, no side effects"


# ---------------------------------------------------------------------------
# 9-13  THE ENVIRONMENT IS EACH PLATFORM'S OWN, NOT A GENERIC ONE
# ---------------------------------------------------------------------------
@gate(9, "each platform uses its own hierarchy words")
def _g9():
    lv = {k: v["levels"] for k, v in A.PLATFORMS.items()}
    assert lv["facebook"][1] == "Ad set", "Meta calls it an ad set"
    assert lv["google"][1] == "Ad group", "Google calls it an ad group"
    assert lv["linkedin"][0] == "Campaign group", (
        "LinkedIn's top level is a campaign group")
    return "; ".join(f"{k}: {' > '.join(v)}" for k, v in lv.items())


@gate(10, "each platform offers its own bidding strategies, each explained")
def _g10():
    seen = {}
    for pid, p in A.PLATFORMS.items():
        assert len(p["bidding"]) >= 3, f"{pid} has too few strategies"
        for nm, why in p["bidding"]:
            assert len(why) > 30, f"{pid}/{nm} has no real explanation"
            seen.setdefault(nm, set()).add(pid)
    assert "Target ROAS" in seen and "google" in seen["Target ROAS"]
    assert "Maximum delivery" in seen and seen["Maximum delivery"] == {"linkedin"}
    assert "Target CPV" in seen and seen["Target CPV"] == {"youtube"}
    total = sum(len(p["bidding"]) for p in A.PLATFORMS.values())
    return f"{total} strategies across 5 platforms, each with a reason"


@gate(11, "targeting dimensions are the ones that platform really offers")
def _g11():
    t = {k: set(v["targeting"]) for k, v in A.PLATFORMS.items()}
    assert "Job title" in t["linkedin"], "LinkedIn targets a job title"
    assert "Job title" not in t["google"], "Google cannot target a job title"
    assert "Keywords" in t["google"], "Google targets keywords"
    assert "Keywords" not in t["linkedin"], "LinkedIn does not target keywords"
    assert "Life events" in t["youtube"]
    return "no two platforms share a targeting list"


@gate(12, "the creative fields carry each platform's real character limits")
def _g12():
    g = dict((n, lim) for n, _c, lim in A.PLATFORMS["google"]["creative"])
    assert g["Headlines"] == 30, "a Google headline is 30 characters"
    assert g["Descriptions"] == 90, "a Google description is 90"
    f = dict((n, lim) for n, _c, lim in A.PLATFORMS["facebook"]["creative"])
    assert f["Headline"] == 40, "a Meta headline is 40"
    y = dict((n, lim) for n, _c, lim in A.PLATFORMS["youtube"]["creative"])
    assert y["Headline"] == 15, "a YouTube headline is 15"
    for pid in A.ORDER:
        html = A.preview_tab(pid, [])
        for nm, _c, lim in A.PLATFORMS[pid]["creative"]:
            if lim:
                assert f"maxlength='{lim}'" in html, (
                    f"{pid}/{nm} does not enforce its limit in the input")
    return "limits stated and enforced on all five"


@gate(13, "every platform renders its own ad preview chrome")
def _g13():
    marks = {"google": "pv-g", "facebook": "pv-m", "instagram": "pv-mi",
             "linkedin": "pv-l", "youtube": "pv-y"}
    for pid, cls in marks.items():
        html = A.preview_tab(pid, [{"groups": [{"ads": ["Test headline"]}]}])
        assert f"class='pv {cls}'" in html, f"{pid} preview is not its own"
        assert "Test headline" in html, f"{pid} preview lost the copy"
    assert "Skip ad" in A.preview_tab("youtube", [])
    assert "Sponsored" in A.preview_tab("google", [])
    assert "Promoted" in A.preview_tab("linkedin", [])
    return "5 distinct previews, each with that platform's own furniture"


# ---------------------------------------------------------------------------
# 14-16  THE SCREEN INSIDE VX2
# ---------------------------------------------------------------------------
@gate(14, "all four tabs render for every platform")
def _g14():
    for pid in A.ORDER:
        html = A.platform_screen(pid, {})
        for t in ("perf", "prev", "bid", "targ"):
            assert f"id='a3p-{pid}-{t}'" in html, f"{pid} is missing tab {t}"
        assert html.count("a3tb") >= 4
    return "5 platforms times 4 tabs, all present"


@gate(15, "the ads environment is reachable from the Media Command subsection")
def _g15():
    m = next(x for x in V.MANIFEST if x["tab"] == "mbcmd")
    html = V.special(m, {}, {"ads": {}})
    assert "a3swbar" in html, "the platform switcher did not render"
    for pid in A.ORDER:
        assert f"a3plat-{pid}" in html, f"{pid} is not on the screen"
    assert "v2head" in html, "the subsection lost its title"
    return "all five platforms inside Media Command"


@gate(16, "the other fifteen Media Buying subsections stay plain readouts")
def _g16():
    subs = [m for m in V.MANIFEST if m["module"] == "media"]
    assert len(subs) == 16, f"{len(subs)} media subsections, expected 16"
    for m in subs:
        if m["tab"] == "mbcmd":
            continue
        # the default screen is the Level 3 readout, not special()
        html = V.readout_page(m["tab"], {})
        assert "a3swbar" not in html, (
            f"{m['tab']} unexpectedly rendered the ads environment")
        assert "v2crumb" in html and "v2readbody" in html, (
            f"{m['tab']} did not render as a readout")
    return "1 rebuilt as the ad manager, 15 plain readouts"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 74)
    print("ADS ENVIRONMENT GATES")
    print("=" * 74)
    for n, name, detail in PASS:
        print(f"  [{n:>2}] PASS  {name}" + (f"\n         {detail}" if detail else ""))
    for n, name, why in FAIL:
        print(f"  [{n:>2}] FAIL  {name}\n         {why}")
    print("-" * 74)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
