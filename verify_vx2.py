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
@gate(1, "the manifest holds exactly 127 subsections")
def _g1():
    assert len(V.MANIFEST) == 127, f"manifest has {len(V.MANIFEST)}"
    return "127"


@gate(2, "every subsection is read from a module's own TABS, not typed by hand")
def _g2():
    import importlib
    for m in V.MANIFEST:
        M = importlib.import_module(f"content_engine_{m['module']}_boards")
        tabs = {t[0] for t in getattr(M, "TABS", ())}
        assert m["tab"] in tabs, (
            f"{m['tab']} is in the manifest but not in "
            f"content_engine_{m['module']}_boards.TABS")
    return f"all 127 tabs exist in their module"


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
    assert declared == 127, f"the nine modules declare {declared} tabs, not 127"
    return f"{declared} declared, 127 carried, 0 duplicated"


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


@gate(8, "every JS function a card button calls is defined on the page")
def _g8():
    called = set()
    for lk in LINKS:
        called |= set(re.findall(r"onclick=[\"']\s*([A-Za-z_$][\w]*)\s*\(", lk))
    missing = [f for f in sorted(called)
               if f"function {f}(" not in PAGE
               and f"function {f} (" not in PAGE]
    assert not missing, f"dead buttons, no such function: {missing}"
    return f"{len(called)} distinct handlers, all defined"


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
@gate(13, "one board is sent, not four")
def _g13():
    loaded = PAGE.count("data-loaded='1'")
    lazy = PAGE.count("data-loaded='0'")
    assert loaded == 1 and lazy == 3, (
        f"{loaded} board(s) rendered and {lazy} deferred; expected 1 and 3")
    return "1 rendered, 3 fetched on first open"


@gate(14, "first paint is under 400 KB with an empty context")
def _g14():
    kb = len(PAGE) / 1024
    assert kb < 400, f"first paint is {kb:.0f} KB"
    return f"{kb:.0f} KB (the old dashboard shipped 5,700 KB)"


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


@gate(25, "the old dashboard offers a way into the new one")
def _g25():
    c, _A = _client()
    c.post("/login", data={"password": "testpw"}, follow_redirects=False)
    r = c.get("/", headers=_HTML)
    assert "href='/vx2'" in r.text, (
        "there is no link from / to /vx2, so the only way in is typing the "
        "URL exactly right")
    r2 = c.get("/vx2", headers=_HTML)
    assert "Anthropos VX2" in r2.text, "/vx2 did not serve VX2 when signed in"
    assert "Business Control Center" not in r2.text, (
        "/vx2 served the old dashboard")
    return "a link in, and /vx2 serves VX2"


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
