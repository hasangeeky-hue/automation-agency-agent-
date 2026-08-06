# -*- coding: utf-8 -*-
"""
verify_vx2_seo.py
============================================================================
GATES FOR THE SEO AUDIT ENVIRONMENT AND THE EIGHT NEW REPAIRS.

The promise being tested: every problem the engine can detect is shown on
exactly one screen, explained in words, and carries a button whose appearance
matches what it is allowed to do. No button may claim a power the engine does
not have, and no repair may publish without a human.
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


import content_engine_vx2_seo as S
import content_engine_seo_fixer8 as F8
import content_engine_workorders as WO
import content_engine_vx2 as V


# ---------------------------------------------------------------------------
# 1-5  COVERAGE: nothing detected may be invisible or unexplained
# ---------------------------------------------------------------------------
@gate(1, "every problem the engine can detect is explained in words")
def _g1():
    missing = sorted(set(WO.TYPE_OF) - set(S.EXPLAIN))
    assert not missing, f"no explanation written for: {missing}"
    thin = [c for c, t in S.EXPLAIN.items() if len(t) < 60]
    assert not thin, f"explanations too short to be useful: {thin}"
    return f"{len(S.EXPLAIN)} explanations, shortest {min(len(t) for t in S.EXPLAIN.values())} chars"


@gate(2, "no explanation describes a code the engine cannot detect")
def _g2():
    extra = sorted(set(S.EXPLAIN) - set(WO.TYPE_OF))
    assert not extra, f"explained but never detected: {extra}"
    return "no phantom problems"


@gate(3, "every problem appears on exactly one screen")
def _g3():
    seen = {}
    for tab, (_t, codes) in S.TAB_CODES.items():
        for c in codes:
            assert c not in seen, (
                f"{c} is on both {seen[c]} and {tab}. A problem on two "
                f"screens gets fixed twice or not at all")
            seen[c] = tab
    missing = sorted(set(WO.TYPE_OF) - set(seen))
    assert not missing, f"detected but shown on no screen: {missing}"
    return f"{len(seen)} problems across {len(S.TAB_CODES)} screens, no overlap"


@gate(4, "every fixable problem says what pressing the button does")
def _g4():
    need = [c for c in WO.TYPE_OF if S.action_class(c) != "MANUAL"]
    missing = sorted(set(need) - set(S.DOES))
    assert not missing, f"a button with no stated effect: {missing}"
    return f"{len(need)} buttons, each with its effect written down"


@gate(5, "every unfixable problem says where it IS fixed")
def _g5():
    manual = [c for c in WO.TYPE_OF if S.action_class(c) == "MANUAL"]
    missing = sorted(set(manual) - set(S.MANUAL_WHERE))
    assert not missing, f"no destination given for: {missing}"
    return f"{len(manual)} manual problems, each with a destination"


# ---------------------------------------------------------------------------
# 6-9  THE ACTION CLASSES: a button may not lie about its power
# ---------------------------------------------------------------------------
@gate(6, "the action class comes from the scheduler's own tables")
def _g6():
    for c in WO.SAFE_AUTO_CODES:
        assert S.action_class(c) == "NOW", c
    for c in WO.BODY_AUTO_CODES:
        assert S.action_class(c) == "BODY", c
    for c in WO.APPROVAL_CODES:
        assert S.action_class(c) == "DRAFT", c
    for c in WO.THEME_CODES - WO.APPROVAL_CODES:
        assert S.action_class(c) == "MANUAL", c
    return "four classes, all read from content_engine_workorders"


@gate(7, "the four classes never share a look")
def _g7():
    looks = [v[1] for v in S.ACTION_LOOK.values()]
    assert len(set(looks)) == 4, f"two classes share a css class: {looks}"
    labels = [v[0] for v in S.ACTION_LOOK.values()]
    assert len(set(labels)) == 4, f"two classes share a label: {labels}"
    for cls in looks:
        assert f".cta.{cls}{{" in S.CSS.replace(" ", ""), \
            f"{cls} has no style, so it looks identical to the others"
    return ", ".join(f"{k}={v[1]}" for k, v in S.ACTION_LOOK.items())


@gate(8, "a MANUAL problem never renders a button that posts")
def _g8():
    manual = [c for c in WO.TYPE_OF if S.action_class(c) == "MANUAL"]
    orders = [{"id": f"o{i}", "code": c, "url": f"/p{i}", "severity": "high",
               "impact": 10, "status": "open"}
              for i, c in enumerate(manual)]
    html = S.issues_panel({"orders": orders}, manual)
    assert "s2fix(" not in html, (
        "a manual problem offered a fix button, which cannot work")
    assert "s2manual(" in html, "it must still say where it IS fixed"
    return f"{len(manual)} manual problems, 0 fix buttons"


@gate(9, "a fixable problem with pages renders exactly one fix button")
def _g9():
    orders = [{"id": "o1", "code": "schema_missing", "url": "/a",
               "severity": "high", "impact": 60, "status": "open"},
              {"id": "o2", "code": "schema_missing", "url": "/b",
               "severity": "high", "impact": 60, "status": "open"}]
    html = S.issues_panel({"orders": orders}, ["schema_missing"])
    assert html.count("s2fix(") == 1, "one row, one button"
    assert "o1,o2" in html, "the button must carry both page ids"
    assert "a2now" in html, "schema_missing is a NOW fix and must look like one"
    return "one button, both ids, correct class"


# ---------------------------------------------------------------------------
# 10-13  THE EIGHT NEW REPAIRS
# ---------------------------------------------------------------------------
@gate(10, "the eight formerly unfixable problems now have a repair")
def _g10():
    was = {"h1_missing", "h1_multiple", "heading_order",
           "broken_internal_link", "canonical_mismatch", "canonical_override",
           "not_indexed", "not_found"}
    assert F8.FIXER8_CODES == was, f"the set changed: {F8.FIXER8_CODES ^ was}"
    for c in was:
        assert S.action_class(c) == "DRAFT", (
            f"{c} must be approval gated, it is {S.action_class(c)}")
    fixable = sum(1 for c in WO.TYPE_OF if S.action_class(c) != "MANUAL")
    assert fixable == 25, f"{fixable} fixable, expected 25"
    return f"{fixable} of {len(WO.TYPE_OF)} now fixable, up from 17"


@gate(11, "the fix list is imported, never retyped")
def _g11():
    src = io.open("content_engine_workorders.py", encoding="utf-8").read()
    assert "from content_engine_seo_fixer8 import FIXER8_CODES" in src, (
        "workorders must import the list, not hold a second copy")
    # TYPE_OF and EFFORT legitimately name all 33 codes: they are the
    # DETECTION vocabulary. What must not exist twice is a hand-written SET of
    # which codes are fixable. Only set literals are checked, by parsing, so
    # this cannot be fooled by a code name appearing in a dict or a comment.
    import ast
    dupes = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assign):
            continue
        name = getattr(node.targets[0], "id", "")
        if not isinstance(node.value, ast.Set):
            continue
        vals = {x.value for x in node.value.elts
                if isinstance(x, ast.Constant) and isinstance(x.value, str)}
        hit = vals & set(F8.FIXER8_CODES)
        if hit:
            dupes.append(f"{name} hand-lists {sorted(hit)}")
    assert not dupes, (
        "a second hand-written set of fixable codes exists: "
        + "; ".join(dupes) + ". That is the two-lists bug this engine has "
        "hit five times")
    return "one fix list, imported; detection vocabulary is separate"


@gate(12, "no repair can publish without a human")
def _g12():
    src = io.open("content_engine_seo_fixer8.py", encoding="utf-8").read()
    i = src.find("def propose(")
    j = src.find("def apply(")
    assert i > 0 and j > i
    drafting = src[i:j]
    for bad in ("update_post", "wp.", ".submit(", ".publish("):
        assert bad not in drafting, (
            f"propose() calls {bad}, so drafting a fix would change the site")
    return "propose() writes nothing; only apply() does, and only when clicked"


@gate(13, "a content repair can never truncate the post it repairs")
def _g13():
    long_body = "<h3>a</h3>" + ("<p>x</p>" * 400)
    r = F8.propose({"code": "h1_missing"}, {"title": "T", "content": long_body})
    p = r["proposal"]
    assert len(p["after_full"]) > len(p["after"]), (
        "the full body must be carried separately from the preview")
    assert long_body in p["after_full"], "the original body must survive intact"
    out = F8.apply({"url": "/x", "extra": {"proposal": {
        "field": "content", "after": "<p>preview only</p>", "says": "x"}}})
    assert out["status"] == "failed", (
        "apply() accepted a proposal with no full body; that would replace an "
        "article with its own first paragraph")
    return f"preview {len(p['after'])} chars, body {len(p['after_full'])} chars, "\
           "and a proposal without the body is refused"


# ---------------------------------------------------------------------------
# 14-17  THE SCREENS
# ---------------------------------------------------------------------------
@gate(14, "the health header renders with no data and says so")
def _g14():
    h = S.health_header({})
    assert "not measured" in h, "an absent score must say it is absent"
    assert ">--<" in h, "an absent overall must not print as 0"
    h2 = S.health_header({"scores": {"overall": 96, "technical": 88},
                          "crawl": {"pages": 176}})
    assert ">96<" in h2 and "176" in h2
    return "absent reads as absent, present reads as present"


@gate(15, "all ten SEO subsections route to a screen, and the four audit "
          "screens really carry issue rows")
def _g15():
    subs = [m for m in V.MANIFEST if m["module"] == "seo"]
    assert len(subs) == 10, f"{len(subs)} SEO subsections, expected 10"
    orders = [{"id": f"o{i}", "code": c, "url": f"/p{i}", "severity": "high",
               "impact": 60, "status": "open", "evidence": "seeded"}
              for i, c in enumerate(sorted(WO.TYPE_OF))]
    ctx = {"orders": orders}
    audit_tabs, seen_rows = set(), 0
    for m in subs:
        html = V.special(m, ctx, {})
        assert len(html) > 400, f"{m['tab']} rendered almost nothing"
        assert "v2head" in html, f"{m['tab']} lost its title"
        assert "s2hd" in html, f"{m['tab']} lost the health header"
        n = html.count("class='s2issue")
        if n:
            audit_tabs.add(m["tab"])
            seen_rows += n
    # THE CHECK THAT WAS MISSING. An earlier version of this gate only looked
    # for the header, which the fallback screen also renders, so a wrong tab
    # id would have passed while showing no issues at all.
    assert audit_tabs == {"seocmd", "seotech", "seoonpage", "seokw", "seowork"}, \
        f"the audit screens did not render issue rows: {sorted(audit_tabs)}"
    return f"10 of 10; 5 audit screens carrying {seen_rows} issue rows"


@gate(21, "the header reads the crawl record the crawler actually writes")
def _g21():
    real = {"base": "https://x.test", "at": "2026-08-06T09:12:00Z",
            "count": 176, "urls": [{"url": "/a"}]}
    h = S.health_header({"crawl": real, "scores": {"overall": 78}})
    assert "176" in h, (
        "the crawler writes 'count'; reading 'pages' printed 0 over a real "
        "176-page crawl")
    assert "2026-08-06" in h, "the crawl date must be shown"
    return "count and at, as written by content_engine_crawler"


@gate(22, "the fix buttons carry their own base styling")
def _g22():
    css = S.CSS.replace(" ", "").replace("\n", "")
    assert ".s2act.cta," in css or ".s2act.cta{" in css, (
        "the issue-row buttons are inside .s2act, which VX2's .v2act rules do "
        "not match, so without a base rule the browser draws its own chrome")
    for prop in ("border:1pxsolidvar(--ln)", "border-radius:6px", "padding:"):
        assert prop in css, f"the base button rule is missing {prop}"
    assert ".cta.a2manual{border-style:dashed;border-color:var(--ft)" in css, (
        "the manual button must set its border COLOUR too, or it renders "
        "black against the dashed style")
    return "base rule present; all four classes fully specified"


@gate(16, "the work-order screen offers bulk approval only for drafted fixes")
def _g16():
    ctx = {"orders": [{"id": "o1", "code": "title_long", "type": "title",
                       "url": "/a", "status": "open", "severity": "medium",
                       "impact": 30,
                       "extra": {"proposal": {"after": "A better title"}}}]}
    html = S.workorders_screen(ctx, [])
    assert "approve-all?type=title" in html, "no bulk path for a drafted fix"
    assert "A better title" in html, "the proposal must be readable first"
    plain = S.workorders_screen({"orders": [dict(ctx["orders"][0], extra={})]}, [])
    assert "approve-all" not in plain, (
        "bulk approve was offered for an order with nothing drafted")
    return "bulk approval appears only when there is something to read"


@gate(17, "an issue row shows the actual URLs, not just a count")
def _g17():
    orders = [{"id": "o1", "code": "meta_missing", "url": "/pricing",
               "severity": "high", "impact": 60, "status": "open",
               "evidence": "no description tag"}]
    html = S.issues_panel({"orders": orders}, ["meta_missing"])
    assert "/pricing" in html, "the affected URL must be on the page"
    assert "no description tag" in html, "the evidence must be readable"
    assert S.EXPLAIN["meta_missing"][:40] in html, "the explanation must show"
    return "URL, evidence and explanation all present"


# ---------------------------------------------------------------------------
# 18-20  THE ROUND TRIP: detected, drafted, queued, approved
# ---------------------------------------------------------------------------
class _Store:
    """The smallest store the fixer will accept. No network, no database."""

    def __init__(self, orders):
        self._s = {WO.SETTING_KEY: orders}

    def get_setting(self, k, d=None):
        return self._s.get(k, d)

    def set_setting(self, k, v):
        self._s[k] = v


@gate(18, "one of the eight walks from detected to drafted, unattended")
def _g18():
    import content_engine_seo_fixer as FIX
    order = WO.make_order("h1_missing", "https://x.test/pricing",
                          severity="high", detail="no H1 on the page")
    store = _Store([order])
    crawl = {"urls": [{"url": "https://x.test/pricing", "status": 200,
                       "title": "Pricing", "content": "<p>body text</p>"}]}
    rep = FIX.run_batch(store, crawl=crawl, auto_only=False, limit=5)
    assert rep["attempted"] == 1, f"the order was not picked up: {rep}"
    saved = store.get_setting(WO.SETTING_KEY) or []
    prop = (saved[0].get("extra") or {}).get("proposal") or {}
    assert prop, (
        "h1_missing ran and left no proposal. Before this build it answered "
        f"'no automated handler for this yet'. Report: {rep}")
    assert prop["field"] == "content"
    assert "<h1>Pricing</h1>" in prop.get("after_full", "")
    assert saved[0]["status"] == "awaiting_approval", (
        f"it must wait for a human, it is {saved[0]['status']}")
    return f"detected, drafted, waiting: {prop['says'][:52]}"


@gate(19, "a refusal is recorded as an answer, not a silent skip")
def _g19():
    import content_engine_seo_fixer as FIX
    order = WO.make_order("h1_missing", "https://x.test/ok", severity="low")
    store = _Store([order])
    crawl = {"urls": [{"url": "https://x.test/ok", "status": 200,
                       "title": "Fine", "content": "<h1>Already here</h1>"}]}
    FIX.run_batch(store, crawl=crawl, auto_only=False, limit=5)
    saved = (store.get_setting(WO.SETTING_KEY) or [])[0]
    assert "already has an H1" in (saved.get("result") or ""), (
        f"the refusal was not written down: {saved.get('result')!r}")
    return "the queue says why, in words"


@gate(20, "approving something never drafted is refused, not guessed at")
def _g20():
    src = io.open("content_engine_api.py", encoding="utf-8").read()
    assert "Nothing has been drafted for this page yet" in src, (
        "the apply endpoint must refuse an order with no proposal")
    assert "F8.apply(order) if order.get(\"code\") in F8.FIXER8_CODES" in src, (
        "the apply endpoint does not route the eight new repairs to fixer8, "
        "so approving one would run the title/meta handler on it")
    return "two apply paths, routed by code; nothing drafted means nothing done"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 74)
    print("SEO AUDIT GATES")
    print("=" * 74)
    for n, name, detail in PASS:
        print(f"  [{n:>2}] PASS  {name}" + (f"\n         {detail}" if detail else ""))
    for n, name, why in FAIL:
        print(f"  [{n:>2}] FAIL  {name}\n         {why}")
    print("-" * 74)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
