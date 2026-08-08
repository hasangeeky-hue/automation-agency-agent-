# -*- coding: utf-8 -*-
"""GATES FOR LEADS & OUTREACH, KLAVIYO GRADE.

The one that matters most: the preview must REFUSE a send while a
personalisation token would render empty. A warning is something people
click past; "Hi ," cannot be unsent.
"""
from __future__ import annotations

import ast
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


import content_engine_email_campaigns as EC
import content_engine_email_segments as ES
import content_engine_email_preview as EP
import content_engine_outreach_screens as OLS
import content_engine_outreach_boards as OB


class _S:
    def __init__(self, d=None): self.d = dict(d or {})
    def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
    def set_setting(self, k, v): self.d[k] = v


_JOBS = [{"job_id": "j1", "type": "outreach_campaign", "status": "sent",
          "created_at": "2026-08-01T09:00:00",
          "payload": {"name": "Munich clinics",
                      "leads": [{"email": "a@x.de", "name": "Ann",
                                 "company": "X", "score": 80,
                                 "country": "Germany"},
                                {"email": "b@y.de", "name": "Bo",
                                 "company": "", "score": 40,
                                 "country": "USA"}],
                      "sent_at": {"a@x.de": ["2026-08-01T10:00:00"],
                                  "b@y.de": ["2026-08-01T10:00:00"]}}}]
_STORE = _S({"outreach_tokens": {
                 "t1": {"job": "j1", "email": "a@x.de", "step": 1,
                        "at": "2026-08-01T10:00:00"},
                 "t2": {"job": "j1", "email": "b@y.de", "step": 1,
                        "at": "2026-08-01T10:00:00"}},
             "outreach_events": [
                 {"token": "t1", "kind": "open", "at": "2026-08-01T11:00:00"},
                 {"token": "t1", "kind": "click", "at": "2026-08-01T12:00:00",
                  "url": "https://anthropos-automation.com/book"}]})


@gate(1, "THE HARD ONE: an empty token blocks the send")
def _g1():
    lead = {"name": "Ann", "company": ""}
    p = EP.render("Hi {{name}} at {{company}}", "<p>x</p>", lead)
    assert p["blocking"] is True, "an empty token did not block"
    assert "{{company}}" in p["block_reason"]
    assert "Fill the field" in p["block_reason"], (
        "the block must say what to DO, not only that it is blocked")
    good = EP.render("Hi {{name}}", "<p>x</p>", lead)
    assert good["blocking"] is False
    api = io.open("content_engine_api.py", encoding="utf-8").read()
    assert 'prev.get("blocking")' in api, (
        "the approve endpoint does not consult the preview, so the block "
        "could be clicked past - which is the whole point of it")
    assert "refused: " in api
    return "blocked, named, and the approve path obeys it"


@gate(2, "every rate carries its denominator")
def _g2():
    c = EC.campaigns(_STORE, _JOBS)[0]
    assert c["open_of"] == "1 of 2" and c["click_of"] == "1 of 2"
    assert c["ctor_of"] == "1 of 1"
    pct, txt = EC._rate(3, 0)
    assert pct is None and "no denominator" in txt, (
        "a rate over nothing must not render as 0%")
    return "open, click and CTOR each state what they divided by"


@gate(3, "an untracked campaign reports nothing, not zero")
def _g3():
    c = EC.campaigns(_S(), _JOBS)[0]
    assert c["opens"] is None and c["open_rate"] is None
    assert c["open_of"] == "not tracked"
    return "no pixel, no number - and it says which"


@gate(4, "opens are unique by token, never raw events")
def _g4():
    s = _S(dict(_STORE.d))
    s.d["outreach_events"] = (list(s.d["outreach_events"])
                              + [{"token": "t1", "kind": "open",
                                  "at": "2026-08-01T13:00:00"}] * 5)
    c = EC.campaigns(s, _JOBS)[0]
    assert c["opens"] == 1, (
        f"{c['opens']} opens from one recipient reloading - unique-by-token "
        f"is the only honest count")
    return "six events, one reader"


@gate(5, "the Apple caveat exists once and rides every open-derived screen")
def _g5():
    assert "Apple Mail" in EC.MPP_CAVEAT and "Clicks are the number" in EC.MPP_CAVEAT
    ctx = {"campaigns": EC.campaigns(_STORE, _JOBS)}
    p = OLS.build_panels(ctx)
    carried = [t for t in ("olaunch", "ooutbox", "ocost")
               if EC.MPP_CAVEAT[:30] in p[t]]
    assert len(carried) == 3, f"the caveat is missing from {carried}"
    src = io.open("content_engine_outreach_screens.py", encoding="utf-8").read()
    assert "Apple Mail Privacy" not in src, (
        "the caveat is retyped in the screens instead of imported")
    return "one sentence, three screens, zero copies"


@gate(6, "a profile is a person with their own history, in time order")
def _g6():
    rows = EC.profiles(_STORE, _JOBS)
    ann = [r for r in rows if r["email"] == "a@x.de"][0]
    assert ann["opens"] == 1 and ann["clicks"] == 1 and ann["sends"] == 1
    kinds = [x["kind"] for x in ann["timeline"]]
    assert kinds[0] == "sent", "the timeline must start with the send"
    assert "click" in kinds
    ats = [str(x.get("at") or "") for x in ann["timeline"]]
    assert ats == sorted(ats), "the timeline is out of order"
    return f"{len(rows)} people, each with their own events"


@gate(7, "one condition vocabulary; a field can only use its own operators")
def _g7():
    for f in ES.FIELDS:
        assert ES.ops_for(f), f"{f} offers no operators"
        for op in ES.ops_for(f):
            assert op in ES.OPS, f"{f} offers unknown operator {op}"
    assert ES.valid_condition({"field": "score", "op": "contains",
                               "value": "x"}), "a number accepted 'contains'"
    assert ES.valid_condition({"field": "nope", "op": "eq", "value": 1})
    src = io.open("content_engine_outreach_screens.py", encoding="utf-8").read()
    assert "ES.FIELDS" in src and "ES.OPS" in src, (
        "the builder retypes the vocabulary instead of importing it")
    return f"{len(ES.FIELDS)} fields, {len(ES.OPS)} operators, one list"


@gate(8, "a segment is evaluated live and can never be everyone by accident")
def _g8():
    s = _S()
    assert ES.save_segment(s, "All", [])["ok"] is False, (
        "a segment with no condition would mail everyone")
    ok = ES.save_segment(s, "Hot DE", [
        {"field": "score", "op": "gte", "value": 70},
        {"field": "country", "op": "eq", "value": "Germany"}])
    assert ok["ok"]
    people = EC.profiles(_STORE, _JOBS)
    live = ES.evaluate(people, ES.segments(s)[0]["conditions"])
    assert len(live) == 1 and live[0]["email"] == "a@x.de"
    assert ES.describe(ES.segments(s)[0]) == \
        "Lead score >= 70 and Country is Germany"
    return "live evaluation, and it reads back in plain words"


@gate(9, "THE FLOW RUNNER CANNOT SEND")
def _g9():
    tree = ast.parse(io.open("content_engine_email_segments.py",
                             encoding="utf-8").read())
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {x.name for x in n.names}
        elif isinstance(n, ast.ImportFrom):
            imports.add(n.module or "")
    assert not any("connector" in m or "outreach" in m for m in imports), (
        f"the flow module imports something that can send: {imports}")
    s = _S()
    out = ES.run_flow(s, ES.DEFAULT_FLOW, EC.profiles(_STORE, _JOBS))
    assert "Nothing has been sent" in out["message"]
    assert len(ES.flow_queue(s)) == out["queued"]
    return "it queues, it says so, and it cannot reach a mailer"


@gate(10, "the flow queue never doubles a person on the same step")
def _g10():
    s = _S()
    people = EC.profiles(_STORE, _JOBS)
    ES.run_flow(s, ES.DEFAULT_FLOW, people)
    ES.run_flow(s, ES.DEFAULT_FLOW, people)
    q = ES.flow_queue(s)
    assert len({(x["email"], x["step"]) for x in q}) == len(q)
    return f"{len(q)} person-steps, no duplicates after two runs"


@gate(11, "the preview lists every link and what a click really does")
def _g11():
    html = ('<a href="https://a.test/book">go</a>'
            '<a href="http://old.test/x">old</a>')
    p = EP.render("s", html, {}, base="https://engine.test")
    assert len(p["links"]) == 2
    assert "/t/c/<token>?u=" in p["links"][0]["tracked_as"]
    assert p["insecure_links"] == ["http://old.test/x"]
    nb = EP.render("s", html, {}, base="")
    assert nb["untracked"] is True
    assert "cannot be counted" in nb["links"][0]["tracked_as"]
    return "2 links, the http one flagged, untracked state explained"


@gate(12, "eight spam signals, each with a reason a person can act on")
def _g12():
    sig = EP.spam_signals("FREE!! ACT NOW!!", "<p>hi</p>", has_text_part=False)
    assert len(sig) == 8
    names = {s["name"]: s["ok"] for s in sig}
    for must_fail in ("Shouting", "Exclamation marks", "Words in the body",
                      "Plain-text part", "Unsubscribe present", "Spam words"):
        assert names[must_fail] is False, f"{must_fail} was not caught"
    assert all(len(s["why"]) > 30 for s in sig), (
        "a signal with no reason is a score, and a score cannot be acted on")
    clean = EP.spam_signals("A short question about your scheduling",
                            "<p>" + "word " * 60 + "unsubscribe</p>")
    assert all(s["ok"] for s in clean)
    return "8 signals, 6 caught on a bad email, 0 false alarms on a good one"


@gate(13, "the fourteen panels render on empty and hostile contexts")
def _g13():
    shapes = ({}, {k: None for k in ("campaigns", "profiles", "segments",
                                     "flows", "deliverability", "replies",
                                     "sends", "bookings", "attribution",
                                     "costs", "sourcing", "quality",
                                     "territories", "preview")},
              {"campaigns": "bad", "profiles": 5, "preview": "x",
               "segments": {}, "flow_queue": "no"})
    for ctx in shapes:
        p = OLS.build_panels(ctx)
        assert len(p) == 14, f"{len(p)} panels"
        for tid, h in p.items():
            assert h and len(h) > 50, f"{tid} rendered nothing"
    return f"14 panels, {len(shapes)} context shapes, no crash"


@gate(14, "the section is the OS shell, with one navigation grammar")
def _g14():
    # The shape this gate used to assert (a band plus a tab strip) was the
    # rejected build. The section now serves the engagement OS: a band, a
    # grouped rail, a panel, and nothing else stacked on top.
    import content_engine_os as _OS
    ctx = {"os": _OS.build_ctx(_S(), jobs=_JOBS),
           "live": {"outbox": "<b>REALSENDCONTROLS</b>"}}
    sec = OB.outreach_section(ctx)
    stray = re.findall(r"<div class='card (?:overflowcard )?sev-", sec)
    assert not stray, f"{len(stray)} old cards still render"
    body = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", sec,
                  flags=re.S)
    for chrome, what in (("sgroups", "the old group rail"),
                         ("cbtn", "the old run bar"),
                         ("class='stabs'", "the old tab strip"),
                         ("s3band", "the old band")):
        assert chrome not in body, f"{what} is back"
    assert body.count("class='os-rail'") == 1, "there must be exactly one rail"
    ids = re.findall(r"\sid='([^']+)'", sec)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    assert not dup, f"duplicate ids: {dup[:6]}"
    return f"0 cards, 0 legacy chrome, 1 rail, {len(ids)} unique ids"


@gate(15, "the rail is the founder's information architecture")
def _g15():
    import content_engine_os_screens as SCR
    groups = [g for g, _ in SCR.NAV if g]
    for want in ("Acquisition", "Audience", "Engagement", "Sending",
                 "Automation", "Analytics", "Settings"):
        assert want in groups, f"the rail lost {want}"
    ids = [pid for _g, items in SCR.NAV for pid, _l in items]
    assert len(ids) == len(set(ids)) == 22, f"{len(ids)} destinations"
    assert set(ids) == set(SCR.PANELS), "a destination with no screen"
    return f"{len(groups)} groups, {len(ids)} screens, all reachable"


@gate(16, "the live send controls were carried over, not re-implemented")
def _g16():
    import content_engine_os as _OS
    ctx = {"os": _OS.build_ctx(_S(), jobs=_JOBS)}
    sec = OB.outreach_section(ctx, live={"outbox": "<b>REALSENDCONTROLS</b>"})
    assert "REALSENDCONTROLS" in sec, (
        "the pre-rendered send block was dropped - the outbox buttons would "
        "stop working")
    sec2 = OB.outreach_section(dict(ctx, live={"outbox": "<b>VIACTX</b>"}))
    assert "VIACTX" in sec2, "the dashboard passes the blocks inside ctx"
    for f in ("content_engine_os_screens.py", "content_engine_os_analytics.py"):
        src = io.open(f, encoding="utf-8").read()
        for bad in ("Emailer", "send_personalized", "smtplib", "requests."):
            assert bad not in src, f"{f} contains {bad}"
    return "live blocks carried both ways; the renderers send nothing"


@gate(17, "the routes exist and empty input is answered in words")
def _g17():
    api = io.open("content_engine_api.py", encoding="utf-8").read()
    for r in ('"/outreach/segment"', '"/outreach/preview"',
              '"/outreach/flow/run"', '"/outreach/flow/approve"',
              '"/os/sync"', '"/os/campaign/{cid}"', '"/os/message/save"',
              '"/os/campaign/queue"', '"/os/campaign/approve"',
              '"/os/queue/work"', '"/os/segment/count"',
              '"/os/flow/advance"', '"/os/webhook/{provider}"',
              '"/internal/v1/agent"'):
        assert r in api, f"missing route {r}"
    assert "render for anyone" in api, (
        "the preview must say WHY it is empty, and it must no longer claim "
        "a campaign carries no subject when the resolver was simply never "
        "asked")
    assert "the queue is empty" in api
    assert 'p.get("html")' not in api, (
        "the preview is reading a payload field no job carries again")
    return "14 routes; empty input answered, not crashed"


@gate(18, "the ctx carries the Klaviyo layer without disturbing the old keys")
def _g18():
    import content_engine_seo_ops as O
    ctx = O.build_outreach_ctx(_S(), jobs=_JOBS)
    for k in ("campaigns", "profiles", "segments", "flows", "flow_queue",
              "preview", "campaign_links", "open_curve"):
        assert k in ctx, f"build_outreach_ctx lost {k}"
    for old in ("sourcing", "quality", "sends", "replies", "deliverability"):
        assert old in ctx, f"the old key {old} was dropped"
    return f"{len(ctx)} keys: 8 new, every old one intact"


if __name__ == "__main__":
    print("=" * 74)
    print("LEADS & OUTREACH GATES")
    print("=" * 74)
    for n, name, d in PASS:
        print(f"  [{n:>2}] PASS  {name}" + (f"\n         {d}" if d else ""))
    for n, name, why in FAIL:
        print(f"  [{n:>2}] FAIL  {name}\n         {why}")
    print("-" * 74)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
