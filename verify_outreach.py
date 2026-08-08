# -*- coding: utf-8 -*-
"""
verify_outreach.py
============================================================================
LEADS AND OUTREACH: THE SECTION CONTRACT.

WHAT HAPPENED TO THE GATES THAT USED TO BE HERE
  Twelve of them tested content_engine_email_campaigns, _segments and the
  fourteen-panel renderer. Those modules were deleted when the section
  became the engagement OS, so gates asserting their behaviour would be
  asserting nothing at all. They were not weakened or commented out: what
  they protected moved into verify_os.py, which tests it against the code
  that now does the work.

WHAT THIS FILE STILL OWNS
  The SECTION contract, which verify_os.py deliberately does not cover:
  that the dashboard's one call site produces one navigation grammar, no
  cards, no duplicate ids, and that the old formation is really gone from
  disk rather than merely unreferenced.

  Plus the pre-flight checks (spam signals and the link audit), the one
  piece of the old email tooling that survived, because it now reads the
  email the resolver actually produced instead of a field no job carries.
============================================================================
"""

from __future__ import annotations

import io
import os
import re
import sys

import content_engine_email_preview as EP
import content_engine_outreach_boards as OB

PASS, FAIL = [], []


def gate(n, name):
    def deco(fn):
        try:
            PASS.append((n, name, fn() or ""))
        except AssertionError as ex:
            FAIL.append((n, name, str(ex) or "assertion failed"))
        except Exception as ex:
            FAIL.append((n, name, f"{type(ex).__name__}: {ex}"))
        return fn
    return deco


class _S:
    def __init__(self):
        self.d = {}
        self.jobs = {}

    def get_setting(self, k, dflt=None):
        return self.d.get(k, dflt)

    def set_setting(self, k, v):
        self.d[k] = v

    def get(self, jid):
        return self.jobs[jid]

    def save(self, job):
        self.jobs[job["job_id"]] = job

    def list_jobs(self, status=None):
        return list(self.jobs.values())


_JOBS = [{
    "job_id": "out_1", "type": "outreach_campaign",
    "created_at": "2026-07-01T09:00:00+00:00",
    "payload": {
        "name": "Section fixture",
        "leads": [{"email": "ann@clinicx.de", "name": "Ann Weber",
                   "company": "Clinic X", "country": "Germany",
                   "city": "Munich"}],
        "outreach_copy": {"subject_variants": ["A question about {{company}}"],
                          "body": "Hi {{name}}, a short note about "
                                  "{{company}}."},
        "sent_to": {"ann@clinicx.de": ["<m1@x>"]},
        "sent_at": {"ann@clinicx.de": ["2026-07-02T09:00:00+00:00"]},
        "sent_meta": {"ann@clinicx.de": [
            {"subject": "A question about Clinic X", "step": 1,
             "at": "2026-07-02T09:00:00+00:00"}]},
    }}]


def _ctx():
    import content_engine_os as _OS
    s = _S()
    for j in _JOBS:
        s.save(j)
    return {"os": _OS.build_ctx(s, jobs=_JOBS)}


# ===========================================================================
@gate(1, "the old formation is gone, not merely unused")
def _g1():
    for f in ("content_engine_outreach_screens.py",
              "content_engine_email_campaigns.py",
              "content_engine_email_segments.py"):
        assert not os.path.exists(f), f"{f} is still on disk"
    for f in ("content_engine_api.py", "content_engine_seo_ops.py",
              "content_engine_os_screens.py",
              "content_engine_outreach_boards.py"):
        src = io.open(f, encoding="utf-8").read()
        for dead in ("outreach_screens", "email_campaigns", "email_segments"):
            assert dead not in src, f"{f} still mentions {dead}"
    boards = io.open("content_engine_outreach_boards.py",
                     encoding="utf-8").read()
    assert len(boards.splitlines()) < 120, "the boards file is still large"
    assert "TABS" not in boards and "_TAB_BOARDS" not in boards
    return "3 modules deleted, 0 references left, boards down to one function"


@gate(2, "the section is the OS shell, with one navigation grammar")
def _g2():
    sec = OB.outreach_section(_ctx())
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


@gate(3, "the rail is the founder's information architecture")
def _g3():
    import content_engine_os_screens as SCR
    groups = [g for g, _ in SCR.NAV if g]
    for want in ("Acquisition", "Audience", "Engagement", "Sending",
                 "Automation", "Analytics", "Settings"):
        assert want in groups, f"the rail lost {want}"
    ids = [pid for _g, items in SCR.NAV for pid, _l in items]
    assert len(ids) == len(set(ids)), "a destination appears twice"
    assert set(ids) == set(SCR.PANELS), "a destination with no screen"
    return f"{len(groups)} groups, {len(ids)} screens, all reachable"


@gate(4, "the dashboard no longer pastes the old blocks into the section")
def _g4():
    dash = io.open("content_engine_dashboard.py", encoding="utf-8").read()
    assert '_octx["live"] = {}' in dash, (
        "the dashboard is pasting the old cards into the section again")
    sec = OB.outreach_section(_ctx(), live={"outbox": "<b>CARRIED</b>"})
    assert "CARRIED" in sec, "the carrier stopped working"
    return "no legacy blocks passed; the carrier still works if used"


@gate(5, "the renderers cannot send")
def _g5():
    for f in ("content_engine_os_screens.py", "content_engine_os_analytics.py",
              "content_engine_os_editors.py"):
        src = io.open(f, encoding="utf-8").read()
        for bad in ("Emailer", "send_personalized", "smtplib", "requests."):
            assert bad not in src, f"{f} contains {bad}"
    return "3 renderers, none of them can reach a transport"


@gate(6, "the routes exist and the legacy ones are gone")
def _g6():
    api = io.open("content_engine_api.py", encoding="utf-8").read()
    for r in ('"/os/sync"', '"/os/campaign/{cid}"', '"/os/message/save"',
              '"/os/campaign/queue"', '"/os/campaign/approve"',
              '"/os/queue/work"', '"/os/segment/count"', '"/os/flow/advance"',
              '"/os/webhook/{provider}"', '"/internal/v1/agent"',
              '"/os/rules"', '"/os/migrate"', '"/os/workspace/switch"',
              '"/os/member/add"', '"/os/provider/test"', '"/os/send-one"',
              '"/os/template/render"', '"/subscribe"', '"/unsubscribe"'):
        assert r in api, f"missing route {r}"
    for dead in ('"/outreach/segment"', '"/outreach/preview"',
                 '"/outreach/flow/run"', '"/outreach/flow/approve"'):
        assert dead not in api, f"{dead} backs a button that no longer exists"
    assert 'p.get("html")' not in api, (
        "the preview is reading a payload field no job carries again")
    return "19 routes present, 4 legacy endpoints removed"


@gate(7, "the pre-flight checks read a real email")
def _g7():
    sig = EP.spam_signals("FREE!! ACT NOW!!", "<p>hi</p>", has_text_part=False)
    names = {s["name"]: s["ok"] for s in sig}
    assert names["Spam words"] is False, "a spam subject passed"
    assert names["Shouting"] is False and names["Exclamation marks"] is False
    assert all(len(s["why"]) > 30 for s in sig), "a signal with no reason"
    links = EP.links("<a href='http://x.test/a'>a</a>", "https://engine.test")
    assert links[0]["https"] is False, "an http link was not flagged"
    assert "/t/c/" in links[0]["tracked_as"], "the tracked url is not shown"
    src = io.open("content_engine_os.py", encoding="utf-8").read()
    assert "def preflight(" in src and "spam_signals" in src, (
        "the checks are not wired to the resolved email")
    return "8 signals, link audit, and they run on the resolved email"


@gate(8, "the section survives a context that is missing or hostile")
def _g8():
    for ctx in ({}, {"os": None}, {"os": {}}, {"os": {"campaigns": "bad"}}):
        html = OB.outreach_section(ctx)
        assert html and len(html) > 80, "the section rendered nothing"
    return "4 broken contexts, 4 readable pages, no traceback"


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
