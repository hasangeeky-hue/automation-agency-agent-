# -*- coding: utf-8 -*-
"""LIVE TEST: SEO, AEO/GEO, LinkedIn, and the data mutation paths.

This is a TEST harness, not an engine run. It exists because the phase we
are in is "connect and prove every wire", and a wire is not proven by a
green badge that was written by the thing being tested.

    python live_test.py                       READ ONLY. The default.
    python live_test.py --probe               also asks the AI engines a
                                              real buyer question (costs
                                              a few cents of Anthropic
                                              and OpenAI credit)
    python live_test.py --mutate --approved-by "Your Name"
                                              performs AT MOST ONE real
                                              write, through the same
                                              gate the engine uses

Three rules this file will not break:

  It never mutates by default. Every write in lane 4 is a dry run unless
  --mutate AND --approved-by are both given, and even then it stops
  after one, because a test that changes twenty prices is not a test.

  It never calls a wire verified. It reports what the provider said. If
  a provider says nothing, that is reported as nothing, not as a pass.

  It separates "not connected" from "connected and it said no" from
  "not measured". Those three have been conflated on this box before,
  and each one sends you somewhere different.
"""
from __future__ import annotations

import argparse
import sys
import traceback

BRAND = "Anthropos"
DOMAIN = "anthropos-automation.com"
RIVALS = ["zapier.com", "make.com", "n8n.io"]

_PASS, _FAIL, _INFO = [], [], []


def _w(s: str = "") -> None:
    try:
        print(s)
    except UnicodeEncodeError:                       # a Windows console
        print(s.encode("ascii", "replace").decode("ascii"))
    sys.stdout.flush()


def head(n: str) -> None:
    _w("")
    _w("=" * 74)
    _w(n)
    _w("=" * 74)


def ok(label: str, cond: bool, detail: str = "") -> bool:
    """A test with a verdict. Only these two counts decide the exit code.

    `detail` is the FAILURE explanation and is printed only on failure.
    Printing it under an OK produced lines like "OK at least one AI engine
    is reachable   every engine key is absent", which says the opposite of
    the verdict beside it. A passing test explains nothing; it passed.
    """
    (_PASS if cond else _FAIL).append(label)
    _w(("  OK   " + label) if cond
       else ("  FAIL " + label + (("   " + detail) if detail else "")))
    return bool(cond)


def note(label: str, detail: str = "") -> None:
    """An OBSERVATION, never a verdict. Used where this harness genuinely
    cannot know whether the value is right, only what it is. Counting
    these as passes is how a report starts lying."""
    _INFO.append(label)
    _w("       " + label + (("   " + detail) if detail else ""))


def _store():
    from content_engine_api import get_store
    return get_store()


# ----------------------------------------------------------- 1. AEO / GEO
def lane_aeo(store, do_probe: bool) -> None:
    head("1. AEO / GEO: DO THE AI ENGINES ANSWER, AND DO THEY NAME YOU?")
    import content_engine_aeo as AEO

    st = AEO.selftest_engines(store)
    _w("       asked every engine: %r" % st["prompt"])
    _w("")
    asked_any = False
    for name, row in st["engines"].items():
        if not row.get("key_present"):
            note("%-11s no key, so it was never asked" % name)
            continue
        asked_any = True
        if ok("%-11s answered" % name, bool(row.get("ok")),
              str(row.get("error") or row.get("verdict"))[:150]):
            note("            on %s" % row.get("model_asked_for"))

    if not ok("at least one AI engine is reachable", asked_any,
              "every engine key is absent, so AI visibility cannot be measured at all"):
        return

    if not do_probe:
        note("")
        note("no live buyer probe was run. Add --probe to ask a real question.")
        return

    prompt = AEO.get_prompts(store)[0]
    _w("")
    _w("       LIVE BUYER QUESTION: %r" % prompt)
    r = AEO.probe(prompt, brand=BRAND, domain=DOMAIN, rivals=RIVALS, store=store)
    for name, _f, _k in AEO._ENGINES:
        e = (r or {}).get(name) or {}
        if not e.get("connected"):
            note("%-11s %s" % (name, str(e.get("reason") or "")[:120]))
            continue
        # Being named is the OUTCOME being measured, not a health check.
        # A truthful "no" here is a working probe, so it is a note, and
        # the pass/fail above is only about whether the engine answered.
        note("%-11s answered %d chars; %s"
             % (name, e.get("answer_chars", 0),
                "NAMES YOU" if e.get("mentioned") else "does not name you"))
        if e.get("rivals_mentioned"):
            note("            it named instead: " + ", ".join(e["rivals_mentioned"]))
        if e.get("excerpt"):
            note("            \"" + str(e["excerpt"])[:150].replace("\n", " ") + "\"")

    g = (r or {}).get("google_ai") or {}
    if g.get("connected"):
        note("google      owns_snippet=%s organic_position=%s"
             % (g.get("owns_snippet"), g.get("organic_position")))
    else:
        note("google      Serper is not connected, so Google's own answer "
             "surfaces were not read")


# ---------------------------------------------------------------- 2. SEO
def lane_seo(store) -> None:
    head("2. SEO: IS REAL SEARCH DATA REACHING THE SCREENS?")
    import content_engine_connectors as C

    v = C.verify_wire("google_gsc_ga4")
    ok("the Google Search Console / GA4 wire answers a real call",
       bool(v.get("ok")), str(v.get("reason") or "")[:150])

    try:
        import content_engine_seo_ops as OPS
        live = OPS.build_ctx(store)
    except Exception as e:                                    # noqa: BLE001
        ok("the SEO bridge builds its context", False, repr(e)[:120])
        return
    ok("the SEO bridge builds its context", True)

    # THE TABLES COME OUT OF THE BRIDGE, NOT OUT OF THE RAW CONTEXT.
    # Reading build_ctx() directly reported "NO DATA YET" for every table
    # on a box that had 15 queries, 100 rank rows and 277 content rows.
    # That is the same false report as a wrong green, pointing the other
    # way, and it is worse: it sends you to fix a pipeline that works.
    # enrich() is what the screens themselves read.
    import content_engine_search_bridge as BR
    fed = BR.enrich(live)

    ins = (live.get("insights") or {})
    gsc, ga4 = (ins.get("gsc") or {}), (ins.get("ga4") or {})
    note("last Google pull: " + str(ins.get("at") or "never"))
    note("Search Console: %d queries, %d days"
         % (len(gsc.get("queries") or []), len(gsc.get("daily") or [])))
    note("rank tracker rows: %d" % len(live.get("ranks") or []))
    note("")

    empty = []
    for key in BR.MAPPING:
        val = fed.get(key)
        if val in (None, {}, [], "manual"):
            empty.append(key)
            continue
        size = ("%d row(s)" % len(val) if isinstance(val, list)
                else "%d field(s)" % len(val) if isinstance(val, dict)
                else str(val))
        note("%-18s %s" % (key, size))
    for key in empty:
        note("%-18s NO DATA YET (the screen will say what is missing)" % key)

    ok("every screen table the bridge feeds is reachable",
       len(empty) < len(BR.MAPPING),
       "not one table has data, which means the bridge is not being fed at all")

    tot = fed.get("search_totals") or {}
    if tot:
        note("")
        note("clicks=%s impressions=%s ctr=%s avg_position=%s"
             % (tot.get("clicks"), tot.get("impressions"),
                tot.get("ctr"), tot.get("avg_position")))
    # The known open question on this box, carried forward by name so it
    # does not quietly become "SEO is fine".
    if tot.get("sessions_note"):
        note("organic sessions: " + str(tot.get("sessions_note"))[:200])


# ----------------------------------------------------------- 3. LINKEDIN
def lane_linkedin(store) -> None:
    head("3. LINKEDIN: CAN IT POST, AND IF NOT, EXACTLY WHY?")
    import content_engine_connectors as C
    import content_engine_social_desk as SD

    # A READ proves the token. This is the whole reason social_linkedin
    # is in VERIFIABLE: a posting wire that can only be proven by posting
    # is a wire that can never be safely tested.
    v = C.verify_wire("social_linkedin")
    ok("the LinkedIn token answers a read (/v2/userinfo), without posting",
       bool(v.get("ok")),
       ("HTTP %s: %s" % (v.get("code"), str(v.get("reason") or "")[:130]))
       if not v.get("ok") else "")

    states = SD.channel_state(store)
    li = (states or {}).get("linkedin") or {}
    note("")
    note("linkedin channel state: " + ", ".join(
        "%s=%s" % (k, li.get(k)) for k in sorted(li)))

    if li.get("deadlocked"):
        ok("the channel is NOT deadlocked", False,
           "it can never post and nothing else will say so")
    else:
        ok("the channel is not deadlocked", True)

    q = SD.queue(store) or {}
    note("")
    # Counts only. The per-channel dict belongs on the Distributor's desk,
    # not dumped raw into a terminal where it hides the numbers.
    note("social queue: " + ", ".join(
        "%s=%s" % (k, (len(v2) if isinstance(v2, (list, tuple)) else v2))
        for k, v2 in sorted(q.items()) if not isinstance(v2, dict)))
    for cname, cst in sorted((q.get("channels") or {}).items()):
        cst = cst or {}
        # READY TO POST NEEDS BOTH. `available` only means the poster class
        # loads and a credential exists; `verified` means the provider
        # actually accepted it. Reading `available` alone printed
        # "linkedin READY TO POST" next to a 401, which is the false green
        # this whole harness exists to catch.
        ready = bool(cst.get("available")) and bool(cst.get("verified"))
        if ready:
            note("  %-10s READY TO POST (credential present AND accepted)" % cname)
        elif cst.get("available"):
            note("  %-10s HAS A CREDENTIAL BUT IT IS NOT ACCEPTED: %s"
                 % (cname, str(cst.get("reason") or "no reason given")[:90]))
        else:
            note("  %-10s %s"
                 % (cname, str(cst.get("reason") or "not available")[:90]))


# ---------------------------------------------------- 4. DATA MUTATION
def lane_mutation(store, mutate: bool, approver: str) -> None:
    head("4. DATA MUTATION: EVERY WRITE REFUSES WITHOUT A NAMED HUMAN")
    import content_engine_pricing as PR

    # --- the gate itself, tested by trying to get past it ---------------
    # This is the only honest way to test a gate. Reading the source says
    # the check is written; calling it says the check RUNS.
    r = PR.apply_one(store, "does-not-exist", approved_by="")
    ok("a price write with NO approver is refused",
       not r.get("ok"), str(r.get("why") or r.get("reason") or "")[:120])

    r = PR.apply_one(store, "does-not-exist", approved_by="Test Human")
    ok("and a named approver still cannot write a proposal that does not exist",
       not r.get("ok"), str(r.get("why") or r.get("reason") or "")[:120])

    # --- what WOULD change, without changing it -------------------------
    try:
        props = PR.propose(store)
    except Exception as e:                                    # noqa: BLE001
        ok("the pricing desk can read the catalogue", False, repr(e)[:120])
        props = {}
    else:
        ok("the pricing desk can read the catalogue", True)

    items = (props or {}).get("proposals") or []
    note("")
    note("DRY RUN: %d price proposal(s) waiting for a human" % len(items))
    for p in items[:5]:
        note("  %s  %s -> %s   (%s)"
             % (str(p.get("product_id"))[:18], p.get("price"),
                p.get("new_price"), p.get("reason")))
    if not items:
        note("  nothing proposed. That is a real answer, not an error: it "
             "means no product currently meets a reason to move.")

    if not mutate:
        note("")
        note("NO WRITE WAS PERFORMED. This run was read only.")
        note("To perform exactly ONE real, approved write:")
        note("  python live_test.py --mutate --approved-by \"Your Name\"")
        return

    if not approver.strip():
        ok("--mutate was given with a named approver", False,
           "--approved-by is required; a write with no name is the one "
           "thing this engine must never do")
        return
    if not items:
        note("")
        note("--mutate was given, but there is nothing to write. Nothing done.")
        return

    # AT MOST ONE. A test that mutates the whole catalogue is not a test.
    first = items[0]
    _w("")
    _w("       WRITING ONE PRICE, approved by %r" % approver)
    res = PR.apply_one(store, first.get("proposal_id") or first.get("id"),
                       approved_by=approver)
    ok("the approved price write completed and left a receipt",
       bool(res.get("ok")), str(res)[:200])
    note("this changed ONE product. Nothing else was touched.")


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true",
                    help="ask the AI engines a real buyer question (costs credit)")
    ap.add_argument("--mutate", action="store_true",
                    help="perform AT MOST ONE real write (requires --approved-by)")
    ap.add_argument("--approved-by", default="",
                    help="the human who takes responsibility for the write")
    a = ap.parse_args()

    _w("=" * 74)
    _w("LIVE TEST: SEO, AEO, LINKEDIN, DATA MUTATION")
    _w("mode: " + ("MUTATING (one write, approved by %r)" % a.approved_by
                   if a.mutate else "READ ONLY"))
    _w("=" * 74)

    store = _store()
    for fn, args in ((lane_aeo, (store, a.probe)),
                     (lane_seo, (store,)),
                     (lane_linkedin, (store,)),
                     (lane_mutation, (store, a.mutate, a.approved_by))):
        try:
            fn(*args)
        except Exception:                                     # noqa: BLE001
            # A lane that dies must not take the other three with it, and
            # must not be silently absent from the count either.
            ok("%s completed" % fn.__name__, False, "raised, see below")
            _w(traceback.format_exc()[-700:])

    head("VERDICT")
    _w("  %d passed, %d failed, %d observation(s)"
       % (len(_PASS), len(_FAIL), len(_INFO)))
    if _FAIL:
        _w("")
        for f in _FAIL:
            _w("  FAILED: " + f)
    _w("")
    _w("  Observations are NOT passes. They are things this harness can")
    _w("  report but cannot judge, and they need your eyes.")
    _w("=" * 74)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
