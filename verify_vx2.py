# -*- coding: utf-8 -*-
"""
verify_vx2.py
============================================================================
THE GATES FOR VX2. Every claim made about the new layout, made falsifiable.

Run:  python verify_vx2.py

The rule this file exists to enforce: VX2 may not claim a number the old
dashboard does not also produce, may not ship a button that does nothing, and
may not cost the old dashboard anything. If any of the three stops being true,
this file fails loudly rather than the founder discovering it by clicking.
============================================================================
"""
from __future__ import annotations

import io
import json
import re
import sys
import traceback

PASS, FAIL = [], []


def gate(n, name):
    def deco(fn):
        try:
            detail = fn()
            PASS.append((n, name, detail or ""))
        except AssertionError as e:
            FAIL.append((n, name, str(e)))
        except Exception as e:
            FAIL.append((n, name, f"{type(e).__name__}: {e}\n"
                                  + traceback.format_exc(limit=3)))
        return fn
    return deco


import content_engine_vx2 as V
import content_engine_dashboard as D


# ---------------------------------------------------------------------------
# 1-4  THE MANIFEST IS THE REAL SYSTEM, NOT A DESCRIPTION OF IT
# ---------------------------------------------------------------------------
# THE NUMBER CHANGED, AND HERE IS WHY.
# Leads and outreach used to be fourteen tabs of cards inside VX2's
# manifest. It became the engagement OS, which is one environment on the
# dashboard rather than a table of tabs, so it contributes ONE destination
# instead of fourteen: 127 - 14 + 1 = 114. The gates below were not
# loosened to make a failure go away; they were re-pointed at what the
# manifest now honestly describes, and gate 2 was split so the section
# that is no longer a board is checked as a section.
SUBSECTIONS = 114
SECTIONS_NOT_BOARDS = {"outreach"}


@gate(1, f"the manifest holds exactly {SUBSECTIONS} subsections")
def _g1():
    assert len(V.MANIFEST) == SUBSECTIONS, f"manifest has {len(V.MANIFEST)}"
    return str(SUBSECTIONS)


@gate(2, "every subsection is read from a module's own TABS, not typed by hand")
def _g2():
    import importlib
    for m in V.MANIFEST:
        if m["module"] in SECTIONS_NOT_BOARDS:
            M = importlib.import_module(f"content_engine_{m['module']}_boards")
            assert not getattr(M, "TABS", ()), (
                f"{m['module']} declares tabs again; it is meant to be one "
                f"section now")
            assert m["tab"] == m["module"], "a section stands for itself"
            continue
        M = importlib.import_module(f"content_engine_{m['module']}_boards")
        tabs = {t[0] for t in getattr(M, "TABS", ())}
        assert m["tab"] in tabs, (
            f"{m['tab']} is in the manifest but not in "
            f"content_engine_{m['module']}_boards.TABS")
    return (f"{SUBSECTIONS - len(SECTIONS_NOT_BOARDS)} tabs read from their "
            f"module, {len(SECTIONS_NOT_BOARDS)} section carried whole")


@gate(3, "no subsection is claimed twice, and none is lost")
def _g3():
    keys = [(m["module"], m["tab"]) for m in V.MANIFEST]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"duplicate subsections: {sorted(dupes)}"
    import importlib
    declared = 0
    for mod in V._MODULES:
        M = importlib.import_module(f"content_engine_{mod}_boards")
        declared += len(getattr(M, "TABS", ()))
    want = SUBSECTIONS - len(SECTIONS_NOT_BOARDS)
    assert declared == want, (
        f"the nine modules declare {declared} tabs, not {want}")
    return f"{declared} declared, {SUBSECTIONS} carried, 0 duplicated"


@gate(4, "a subsection with no renderer says why, in words")
def _g4():
    orphans = [m for m in V.MANIFEST if not m["fn"]]
    for m in orphans:
        assert m["note"] and len(m["note"]) > 40, (
            f"{m['tab']} has no renderer and no explanation")
    return f"{len(orphans)} orphan(s), each explained"


# ---------------------------------------------------------------------------
# 5-7  CAPTURE - the mechanism that makes one renderer serve 127 screens
# ---------------------------------------------------------------------------
@gate(5, "capture() always restores _vizcards, even when a board explodes")
def _g5():
    import importlib
    before = {}
    for m in V._MODULES:
        M = importlib.import_module(f"content_engine_{m}_boards")
        if hasattr(M, "_vizcards"):
            before[m] = M._vizcards

    def boom(ctx):
        raise RuntimeError("deliberate")

    rows = V.capture(boom, {})
    for m, fn in before.items():
        M = importlib.import_module(f"content_engine_{m}_boards")
        assert M._vizcards is fn, f"{m}._vizcards was left swapped"
    assert rows and "failed to read" in str(rows[0][0]), \
        "a board that raises must leave a visible row, not silence"
    return f"{len(before)} modules restored after a raise"


@gate(6, "a failing subsection does not take its neighbours down")
def _g6():
    ctx = {}
    ok = sum(1 for m in V.MANIFEST[:40] if m["fn"] is None
             or V.capture(m["fn"], ctx) is not None)
    assert ok == 40, "capture returned None for some subsection"
    return "40 sampled, none returned None"


@gate(7, "VX2 reads the SAME context objects the old boards read")
def _g7():
    kw = {"seo_ctx": {"x": 1}, "bi_ctx": None}
    c = V.ctxs_from(kw)
    assert c["seo"] is kw["seo_ctx"], "seo context was copied, not shared"
    assert c["bi"] == {}, "a None context must become {}, never None"
    assert set(c) == set(V._MODULES), "a module lost its context"
    return "same object, nine modules"


# ---------------------------------------------------------------------------
# 8-12  WIRING - the part the founder asked for by name
# ---------------------------------------------------------------------------
def _all_link_html():
    out = []
    for m in V.MANIFEST:
        if not m["fn"]:
            continue
        for c in V.capture(m["fn"], {}):
            if len(c) > 7 and c[7]:
                out.append(str(c[7]))
    return out


LINKS = _all_link_html()
PAGE = V.page(active="decide")


@gate(8, "every JS function ANY screen calls is defined on the page shell")
def _g8():
    called = set()
    for lk in LINKS:
        called |= set(re.findall(r"onclick=[\"']\s*([A-Za-z_$][\w]*)\s*\(", lk))
    # THE FETCHED SCREENS TOO. Readouts arrive by fetch and cannot bring
    # their own scripts to life, so every handler they call must already be
    # on the shell. This shipped broken once: the SEO screens called s3run
    # while the shell defined nothing of the sort - a 200 endpoint behind a
    # dead button.
    import content_engine_vx2_seo as _S
    import content_engine_vx2_ads as _A
    for tab in ("seocmd", "seopages", "seotech", "seooff", "seoaeo",
                "seogeo", "seowork", "mbcmd"):
        html = V.readout_page(tab, {"seo_ctx": {
            "orders": [{"id": "x1", "code": "schema_missing", "url": "/a",
                        "severity": "high", "impact": 9, "status": "open"}],
            "auto_level": "safe"}})
        called |= set(re.findall(r"onclick=[\"']\s*([A-Za-z_$][\w]*)\s*\(",
                                 html))
    missing = [f for f in sorted(called)
               if f"function {f}(" not in PAGE
               and f"function {f} (" not in PAGE]
    assert not missing, f"dead buttons, no such function: {missing}"
    return f"{len(called)} distinct handlers, all defined on the shell"


@gate(9, "the three navigation overrides come AFTER the shared script")
def _g9():
    for f in ("nav", "seoTab", "sysTab"):
        first = PAGE.find(f"function {f}(")
        last = PAGE.rfind(f"function {f}(")
        assert last > first > -1, (
            f"{f} is defined once; VX2 must redefine it after the shared "
            f"script or it will still target the old sections")
    return "nav, seoTab, sysTab redefined last"


@gate(10, "every tab id a button navigates to resolves to a board")
def _g10():
    wire = V.wiring()
    targets = set()
    for lk in LINKS:
        targets |= set(re.findall(
            r"onclick=[\"']\s*(?:nav|seoTab|sysTab)\(\s*'([^']+)'", lk))
    secs = V.section_wiring()
    unresolved = [t for t in sorted(targets) if t not in wire and t not in secs]
    assert not unresolved, f"buttons pointing nowhere: {unresolved}"
    # a section link must land on a real subsection, not just a board
    for sec, (board, tab) in secs.items():
        assert wire.get(tab) == board, (
            f"section '{sec}' points at {tab} on {board}, which is not where "
            f"that subsection lives")
    return (f"{len(targets)} destinations resolve; {len(secs)} section "
            f"aliases each land on a real subsection")


@gate(11, "an unresolvable destination tells the truth instead of doing nothing")
def _g11():
    assert "has no place in the new layout yet" in PAGE, (
        "nav() must say something when it cannot resolve an id")
    assert "Nothing was changed" in PAGE, "it must also say nothing happened"
    return "nav() explains itself"


@gate(12, "the handlers are shared with the old dashboard, not copied")
def _g12():
    src = io.open("content_engine_vx2.py", encoding="utf-8").read()
    assert "dashboard_script(" in src, "VX2 does not call the shared script"
    shared = D.dashboard_script({})
    assert shared in PAGE, "the shared script is not on the page verbatim"
    # the property that actually matters: the action handlers exist ONCE on
    # the page, and that one copy came from the shared module. Only the three
    # navigation functions are allowed a second, overriding definition.
    outside = PAGE.replace(shared, "")
    for f in ("act", "toast", "keepPlace", "setBudget", "biDeal", "approveAll",
              "seeDetails", "closeDetails", "actResult"):
        assert f"function {f}(" not in outside, (
            f"VX2 defines its own {f}() outside the shared script - that is "
            f"the drift this design forbids")
    for f in ("nav", "seoTab", "sysTab"):
        assert f"function {f}(" in outside, f"{f}() is not overridden"
    return f"{len(shared) // 1024} KB shared, 3 overrides, 0 copies"


# ---------------------------------------------------------------------------
# 13-16  THE PAGE ITSELF
# ---------------------------------------------------------------------------
@gate(13, "LEVEL 2: a board is an answer and a list, never a dump")
def _g13():
    # the stylesheet names v2readbody; the first-paint MARKUP must not
    assert "class='v2readbody'" not in PAGE, (
        "a readout body is rendered inline on a board page - the scroll wall "
        "this design exists to kill")
    for bid, label, _q, _s in V.BOARDS:
        i = PAGE.find(f"id='vx2-{bid}'")
        j = PAGE.find("id='vx2-", i + 10)
        seg = PAGE[i:j if j > 0 else None]
        assert "v2ans" in seg, f"{label} has no answer block"
        assert "v2reading" in seg, f"{label} has no plain reading"
        assert "subsections</p>" in seg, f"{label} has no subsection list"
        n_li = seg.count("v2li")
        want = sum(1 for m in V.MANIFEST if m["board"] == bid)
        assert n_li == want, (
            f"{label} lists {n_li} subsections, the manifest says {want}")
    return "4 boards: answer, reading, full list, zero inline readouts"


@gate(14, "first paint is under 200 KB with an empty context")
def _g14():
    kb = len(PAGE) / 1024
    assert kb < 200, f"first paint is {kb:.0f} KB"
    return f"{kb:.0f} KB, all four boards (the old dashboard shipped 5,700 KB)"


@gate(14.2, "LEVEL 3: every readout renders by its URL")
def _g142():
    ok, empty_notes = 0, 0
    for m in V.MANIFEST:
        html = V.readout_page(m["tab"], {})
        assert "v2crumb" in html, f"{m['tab']} has no breadcrumb"
        assert "v2readbody" in html, f"{m['tab']} has no body"
        board_label = next(b[1] for b in V.BOARDS if b[0] == m["board"])
        assert board_label in html, f"{m['tab']} breadcrumb misses its board"
        ok += 1
        if m["fn"] is None:
            empty_notes += 1
            assert ("own panel" in html or "own environment" in html), (
                f"{m['tab']} lost its honest note")
    assert ok == SUBSECTIONS
    return f"{ok} of {SUBSECTIONS}, {empty_notes} carrying an honest note"


@gate(14.4, "LEVEL 4: every line carries its full record")
def _g144():
    html = V.readout_page("syscmd", {})
    rows = re.findall(r"<div class='v2row[^>]*>", html)
    carrying = [r for r in rows if "data-nm=" in r]
    assert carrying, "no line carries a record"
    for r in carrying:
        for field in ("data-nm", "data-val", "data-why", "data-src",
                      "data-kind", "data-kmean", "vx2rec"):
            assert field in r, f"a line is missing {field}: {r[:120]}"
    assert "function vx2rec(" in PAGE, "the record builder is not on the page"
    for f in ("The reading", "Where it comes from", "What kind of number"):
        assert f in PAGE, f"the record never shows '{f}'"
    return f"{len(carrying)} lines sampled, all four record fields present"


@gate(14.6, "the shapes are drawn, not just named")
def _g146():
    import content_engine_vx2_shapes as SH
    ring = SH.hero("SCORE", "54")
    assert "<circle" in ring and ">54<" in ring, "SCORE does not draw a ring"
    bar = SH.hero("RATIO", "189/257")
    assert "<rect" in bar and "189/257" in bar, "RATIO does not draw a bar"
    st = SH.hero("STATE", "live")
    assert "shp-state" in st, "STATE is not a dot and a word"
    assert "<circle" not in SH.hero("SCORE", "clean"), (
        "a SCORE with a word value drew a ring anyway - a shape is a claim "
        "about the data, and the data was not there")
    assert SH.sparkline([5]) == "", "a sparkline from one point is fiction"
    # and they actually appear: the market board answers with the score ring
    # when a crawl has scored the site
    seeded = V.page(active="market",
                    seo_ctx={"scores": {"overall": 78}, "orders": []})
    assert "<circle" in seeded, "the market board never draws its score ring"
    return "ring, bar, dot-and-word drawn; fictions refused"


@gate(15, "no duplicate element ids on the page")
def _g15():
    ids = re.findall(r"\sid=['\"]([^'\"]+)['\"]", PAGE)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate ids: {dupes[:8]}"
    return f"{len(ids)} ids, all unique"


@gate(16, "the CSS var names the shared handlers write are all defined")
def _g16():
    used = set(re.findall(r"var\((--[a-z0-9]+)\)", D.dashboard_script({})))
    for v in sorted(used):
        assert f"{v}:" in V.CSS, (
            f"the shared handlers style with {v}, which VX2's CSS never "
            f"defines - toasts and result lines would render invisible")
    return f"{len(used)} vars used by the handlers, all defined"


# ---------------------------------------------------------------------------
# 17-20  THE OLD DASHBOARD IS UNHARMED
# ---------------------------------------------------------------------------
@gate(17, "the old dashboard still renders, unchanged in shape")
def _g17():
    html = D.dashboard_html(
        saved_keys=set(), seo_ctx=None, media_ctx=None, system_ctx=None,
        risk_ctx=None, bi_ctx=None, outreach_ctx=None, sga_ctx=None,
        factory_ctx=None, cockpit_ctx=None, jobs=[], st={}, health={},
        month_spent=0.0, month_cap=40.0, day_spent=0.0, day_cap=10.0,
        taste_skills=[], has_password=True, paused=False, autonomy=False,
        bookings={}, ads={}, needles={}, last_eval=None, meters={},
        api_limits={}, ci_text="", ci_drive="", autopilot_on=False,
        content_plan=None, web_tracking={}, reply_drafts=[],
        competitor_intel=None, google_insights={})
    assert len(html) > 200_000, f"the old dashboard shrank to {len(html)} chars"
    assert "function act(" in html, "the extraction dropped act() from /"
    assert "AGENT_COUNTS" in html, "the extraction dropped AGENT_COUNTS"
    return f"{len(html) // 1024} KB, handlers intact"


@gate(18, "the extracted script is byte-identical for both callers")
def _g18():
    a = D.dashboard_script({"seo": 3})
    assert a.startswith('<script>window.AGENT_COUNTS={"seo": 3};')
    assert a.rstrip().endswith("</script>")
    assert D.dashboard_script({}) == D.dashboard_script(None), \
        "an empty dict and None must produce the same script"
    return f"{len(a) // 1024} KB, deterministic"


@gate(19, "the API builds its data once and hands the same dict to both UIs")
def _g19():
    src = io.open("content_engine_api.py", encoding="utf-8").read()
    assert "def _dashboard_kwargs()" in src, "the shared reader is gone"
    assert src.count("return D.dashboard_html(**_dashboard_kwargs())") == 1
    assert "VX2.page(active=active, **_dashboard_kwargs())" in src
    assert "@app.get(\"/vx2\"" in src and "/vx2/board/{bid}" in src
    return "one reader, two renderers, two routes"


@gate(20, "VX2 never fetches, computes, publishes, sends or spends")
def _g20():
    src = io.open("content_engine_vx2.py", encoding="utf-8").read()
    for bad in ("requests.", "httpx.", "urlopen", "subprocess", "os.system",
                "store.save", "store.put", "smtplib", ".publish("):
        assert bad not in src, f"VX2 contains {bad!r}; it is a renderer only"
    return "renderer only, no side effects"


# ---------------------------------------------------------------------------
# 21-25  THE DOOR. Reaching /vx2 at all, which is where this first failed.
# ---------------------------------------------------------------------------
def _client(password="testpw"):
    import os
    os.environ["DASHBOARD_PASSWORD"] = password
    from fastapi.testclient import TestClient
    import importlib
    import content_engine_api as _A
    importlib.reload(_A)
    return TestClient(_A.app), _A


_HTML = {"accept": "text/html,application/xhtml+xml"}


@gate(21, "a signed-out browser asking for /vx2 gets the login form, not JSON")
def _g21():
    c, _A = _client()
    for p in ("/", "/vx2", "/vx2?b=market"):
        r = c.get(p, headers=_HTML, follow_redirects=False)
        assert "name='password'" in r.text, (
            f"{p} answered a browser with something that is not a login form. "
            f"This is the bug the founder hit: /vx2 returned raw JSON, so the "
            f"deep link died and the only reachable page was the old one. "
            f"Got: {r.text[:80]!r}")
        assert r.status_code == 200, (
            f"{p} returned {r.status_code}; a proxy with "
            f"proxy_intercept_errors can swallow a non-200 body")
    return "3 page paths, all served the form"


@gate(22, "a program still gets JSON, not a login page")
def _g22():
    c, _A = _client()
    r = c.get("/health", follow_redirects=False)
    assert r.status_code == 401, f"an API call must still 401, got {r.status_code}"
    assert "application/json" in (r.headers.get("content-type") or ""), (
        "an unauthenticated API call must not receive an HTML login page")
    return "401 + JSON for callers that did not ask for a page"


@gate(23, "signing in lands you where you were going")
def _g23():
    c, _A = _client()
    r = c.post("/login", data={"password": "testpw", "next": "/vx2?b=market"},
               follow_redirects=False)
    assert r.headers.get("location") == "/vx2?b=market", (
        f"a deep link must survive the login, got {r.headers.get('location')}")
    return "the destination survives the sign-in"


@gate(24, "the login form cannot be used to redirect somewhere else")
def _g24():
    c, _A = _client()
    for bad in ("https://evil.example/x", "//evil.example/x",
                "http://evil.example"):
        r = c.post("/login", data={"password": "testpw", "next": bad},
                   follow_redirects=False)
        assert r.headers.get("location") == "/", (
            f"an open redirect: next={bad!r} sent the user to "
            f"{r.headers.get('location')!r}")
    return "3 hostile destinations, all refused"


@gate(25, "VX2 is cancelled: unadvertised but still answering, and the "
          "old dashboard carries the SEO screens itself")
def _g25():
    # THE FOUNDER CANCELLED VX2 (2026-08-06). The old dashboard must not
    # advertise it any more - the screens VX2 was built to carry now live in
    # the old dashboard's own SEO section. The route stays parked for anyone
    # who typed it; deleting it is the founder's call, not a side effect.
    c, _A = _client()
    c.post("/login", data={"password": "testpw"}, follow_redirects=False)
    r = c.get("/", headers=_HTML)
    assert "href='/vx2'" not in r.text, (
        "the old dashboard still advertises the cancelled VX2")
    for need in ("s3band", "s3fixpage(", "seoAutoSet('safe'",
                 "function s3run("):
        assert need in r.text, (
            f"the old dashboard's SEO section is missing {need} - the "
            f"SEMrush screens did not land where the founder asked")
    r2 = c.get("/vx2", headers=_HTML)
    assert "Anthropos VX2" in r2.text, "/vx2 should still answer, parked"
    return "unadvertised, parked, and the screens live at / now"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 74)
    print("VX2 GATES")
    print("=" * 74)
    for n, name, detail in PASS:
        print(f"  [{n:>2}] PASS  {name}" + (f"\n         {detail}" if detail else ""))
    for n, name, why in FAIL:
        print(f"  [{n:>2}] FAIL  {name}\n         {why}")
    print("-" * 74)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
