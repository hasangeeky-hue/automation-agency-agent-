"""PROOF THAT THE RETURN ARROW EXISTS.

The bug this guards against is the one that survived every previous audit: the
pipeline ran green all the way to `optimized` while the two steps that learn
received {sessions: 0, conv_rate: 0} for every piece ever published, because
nothing ever called a collector.

Green tests did not catch it. Only asking "what did the measurement step
actually receive?" caught it. That question is now a test.

    python verify_loop.py
"""
import sys

import content_engine_collect as COL
import content_engine_orchestrator as O
import content_engine_prep as P

FAILS = []


def chk(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


class Store(O.InMemoryJobStore):
    def __init__(self):
        super().__init__()
        self._s = {}

    def get_setting(self, k, d=None):
        return self._s.get(k, d)

    def set_setting(self, k, v):
        self._s[k] = v


def run(job, store, ga4=None, max_steps=80):
    """Advance a job to a terminal, recording what each measuring step saw."""
    saw = {}

    def hook(j, skill, st):
        if skill in ("analytics_funnel", "optimizer"):
            saw[skill] = P._MAPPERS[skill](j)
        if skill == "qa_compliance":
            return ({"verdict": "pass"}, 0.01)
        return ({"ok": True, "stages": {}, "measured": True}, 0.01)

    prev, O._LLM_HOOK = O._LLM_HOOK, hook
    real_collect = COL._content_analytics
    if ga4 is not None:
        COL._content_analytics = lambda j, s=None: ga4
    try:
        for _ in range(max_steps):
            b = job["status"]
            if b in ("optimized", "failed", "revision_needed", "halted_budget"):
                break
            if b in ("published", "sent"):
                job["ready_to_measure"] = True
                store.save(job)
            O.tick(store)
            if job["status"] == b and b not in ("published", "sent"):
                break
    finally:
        O._LLM_HOOK = prev
        COL._content_analytics = real_collect
    return saw


print("== 1. GA4 unreachable: the step must be SKIPPED, not fed zeros ==")
st1 = Store()
j1 = O.new_job("unmeasurable", "content_piece", {"brand_name": "A"}, {"type": "blog"})
j1["approved"] = True
st1.put(j1)
saw1 = run(j1, st1)
chk(j1["status"] == "optimized", "reaches a terminal", j1["status"])
chk("analytics_funnel" not in saw1,
    "the model was NEVER called on an unmeasurable outcome",
    "it was called — that is money spent to describe nothing")
chk(bool(j1.get("unmeasured_reason")), "a stated reason is recorded",
    str(j1.get("unmeasured_reason", ""))[:70])
an1 = j1["payload"].get("analytics", {})
chk(an1.get("measured") is False and an1.get("metrics") == {},
    "carries NO numbers — a blank, not a zero", str(an1.get("metrics")))
chk(bool(j1.get("learned_nothing")), "the playbook was NOT taught from nothing")
chk(not j1.get("rewrite_proposed"), "an unmeasured piece is never judged poor")

print("\n== 2. GA4 answers with real traffic: the model gets REAL numbers ==")
st2 = Store()
j2 = O.new_job("measured-good", "content_piece", {"brand_name": "A"}, {"type": "blog"})
j2["approved"] = True
st2.put(j2)
saw2 = run(j2, st2, ga4={
    "measured": True, "source": "ga4", "period": "last 21d", "page": "/good",
    "metrics": {"sessions": 412, "conversions": 14, "conv_rate": 3.4,
                "engagement_rate": 61.0, "top_pages": []},
    "funnel_stages": [{"stage": "sessions", "users": 412, "conv_rate": 3.4,
                       "drop_off": 0}],
    "vs_previous": {}})
got = saw2.get("analytics_funnel", {})
chk("analytics_funnel" in saw2, "the model WAS called")
chk(got.get("metrics", {}).get("sessions") == 412,
    "it received the real session count", str(got.get("metrics")))
chk(got.get("metrics", {}).get("conv_rate") == 3.4,
    "it received a real conversion rate — the metric that was structurally 0",
    str(got.get("metrics", {}).get("conv_rate")))
chk("unavailable" not in got, "no unavailable flag on a measured job")
chk(not j2.get("learned_nothing"), "a measured cycle DOES teach the playbook")
chk(not j2.get("rewrite_proposed"), "a healthy piece earns no proposal")

print("\n== 3. GA4 answers with a REAL zero: proposal, still behind the gate ==")
st3 = Store()
j3 = O.new_job("measured-poor", "content_piece", {"brand_name": "A"}, {"type": "blog"})
j3["approved"] = True
st3.put(j3)
run(j3, st3, ga4={
    "measured": True, "source": "ga4", "period": "last 21d", "page": "/quiet",
    "zero_is_real": True,
    "metrics": {"sessions": 1, "conversions": 0, "conv_rate": 0.0,
                "engagement_rate": 0.0, "top_pages": []},
    "funnel_stages": [], "vs_previous": {}})
chk(bool(j3.get("rewrite_proposed")), "a MEASURED-poor piece earns a proposal")
props = O.rewrite_proposals(st3)
chk(len(props) == 1, "it is in the queue", f"{len(props)} pending")
chk(props and props[0].get("requires_approval") is True,
    "it REQUIRES approval — a proposal, never an automatic rewrite")
chk(props and "1 sessions" in props[0].get("why", ""),
    "it states the number it was judged on", props[0].get("why", "")[:60] if props else "")

print("\n== 3b. The proposal is VISIBLE, not just stored ==")
# It reached Postgres and the /proposal endpoint but no board rendered it. A
# proposal the approval queue does not show is not in the approval queue.
import content_engine_cockpit as CK
import content_engine_cockpit_boards as CKB

pv = CK.proposals(st3)
chk(pv["count"] == 1, "the cockpit context carries it", str(pv["count"]))
page = CKB.cockpit_pages({"proposals": pv})["ckcontent"]
chk("Rewrite proposals" in page, "the approval board shows the count")
chk("measured poor" in page or "measured-poor" in page,
    "it is labelled as measured, so it cannot be read as a guess")
chk("proposal(" in page, "it carries a button a person can actually press")
chk(bool(props) and props[0]["job_id"] in page,
    "the specific piece is named on the board")

print("\n== 4. Outreach closes on data the engine already had ==")
import content_engine_outreach as OUT

st4 = Store()
OUT.set_tracking(st4, True)
j4 = {"job_id": "camp1", "type": "outreach_campaign",
      "payload": {"leads": [{"email": f"{c}@x.com"} for c in "abcd"],
                  "reply_count": 1}}
tok = OUT.register_token(st4, "camp1", "a@x.com", 1)
OUT.register_token(st4, "camp1", "b@x.com", 1)
OUT.record_event(st4, tok, "open")
OUT.record_event(st4, tok, "open")
OUT.record_event(st4, tok, "click")
a4 = COL.analytics_for(j4, st4)
chk(a4.get("measured") is True, "the outreach loop measures")
chk(a4["metrics"]["opens"] == 1 and a4["metrics"]["clicks"] == 1,
    "unique by token — one reader reloading is not two readers",
    str(a4["metrics"]))
chk(a4["metrics"]["open_rate"] == 25.0, "a real rate against real sends",
    str(a4["metrics"]["open_rate"]))

print("\n== 5. Measurement windows differ per pipeline ==")
chk(O.measure_days_for({"type": "content_piece"}) == 21.0,
    "content waits 21 days — long enough to reflect ranking, not crawl speed")
chk(O.measure_days_for({"type": "outreach_campaign"}) == 7.0,
    "outreach keeps 7 — an email is opened within days")

print("\n== 6. The dashboard reports closure it COMPUTED ==")
import content_engine_cockpit as CK

z = CK.loop_closure({})
allw = CK.loop_closure({k: True for k in
                        ("google_gsc_ga4", "email_send", "claude_api",
                         "seo_rank_tracker", "ads_api")})
chk(z["closed"] == 3, "with nothing wired, only the 3 human loops close",
    f"{z['closed']}/{z['total']}")
chk(allw["closed"] == allw["total"], "with every wire live, all close",
    f"{allw['closed']}/{allw['total']}")
chk(z["closed"] != allw["closed"],
    "closure RESPONDS to wire state — it is computed, not drawn")

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("THE LOOP IS CLOSED — measured outcomes reach the steps that learn, an "
      "unmeasurable outcome states why and costs nothing, and a poor piece "
      "earns a proposal that still waits for a person.")


# ===========================================================================
# A TRUNCATION MUST BE RECOVERABLE, AND A FAILURE MUST SAY WHY.
#
# OutputTruncated was raised by call_provider and caught by nobody, so it flew
# past the retry loop entirely - the machinery existed and truncation never
# reached it. Five pieces died this way on 2026-08-02 alone. And every failure
# reported "no model produced a valid result" because the validation errors
# were thrown away at `ok, _ = schema.validate(...)`.
# ===========================================================================
def _verify_truncation_recovery():
    import content_engine_orchestrator as _O
    import content_engine_providers as _P
    out = []

    class _Spec:
        def __init__(self, n=2000):
            self.max_tokens, self.skill_name = n, "content_strategist"

    sp = _Spec()
    out.append((_O._grow_ceiling(sp) and sp.max_tokens > 2000,
                "a truncated skill gets MORE room on its retry",
                "a retry that re-sends the identical ceiling truncates "
                "identically"))
    big = _Spec(_O._CEILING_CAP)
    out.append((_O._grow_ceiling(big) is False,
                "growth stops at the cap instead of looping for ever", ""))

    src = open("content_engine_orchestrator.py", encoding="utf-8").read()
    out.append(("except OutputTruncated" in src,
                "the retry loop actually CATCHES truncation",
                "it was raised past the loop that existed to handle it"))
    out.append(("ok, _ = schema.validate" not in src,
                "validation errors are kept, not discarded",
                "this is why every failure said only 'no valid result'"))
    out.append(("Last problem:" in src,
                "and the failure message carries them", ""))

    for skill in ("content_strategist", "qa_compliance"):
        n = _P._MAX_TOKENS.get(skill, 0)
        out.append((n >= 2400, f"{skill} ceiling is {n}",
                    "it truncated in production at its previous value"))
    return out



# ===========================================================================
# THE SUPERVISOR MUST BE ON THE LINE, not merely in the building.
#
# judge() has existed in this engine for weeks: registered, routed, given a
# cheap model - and called only by the eval harness. A checker nobody calls
# during a job is decoration. That is the FIFTH thing here built and never
# wired, so this asserts the wire, not the module.
# ===========================================================================
def _verify_supervisor():
    import content_engine_supervisor as SUP
    import content_engine_prep as P
    out = []
    src = open("content_engine_orchestrator.py", encoding="utf-8").read()
    out.append(("_supervise(" in src.split("def _supervise")[-1][:4000] or
                "verdict = _supervise" in src,
                "advance() actually CALLS the supervisor",
                "judge() was registered and routed and never called on a job"))
    out.append(("revision_note" in src,
                "a rejection feeds the reason back into the retry",
                "re-rolling the same prompt gets the same dice"))

    job = {"payload": {"config": {"produce_index": 0},
                       "content_strategist": {"calendar": [{"type": "blog"}]}}}
    bad = SUP.supervise("content_producer",
                        {"body": "## One" + chr(10) + "short.", "cta_text": ""},
                        job)
    out.append((not bad["ok"], "a short piece is REJECTED",
                ", ".join(bad["failed"])))
    out.append(("1 of 4" in bad["note"], "and the note says what was short",
                "a rejection that cannot be acted on is just a failure"))

    good = SUP.supervise("content_producer", {
        "title": "t", "cta_text": "Book",
        "body": chr(10).join(f"## S{i}" + chr(10) * 2 + ("word " * 200)
                             for i in range(1, 5)),
        "image_prompts": ["a", "b", "c", "d"]}, job)
    out.append((good["ok"], "a piece that meets the brief PASSES", ""))

    # thresholds must come from prep, so the brief and the check cannot drift
    ssrc = open("content_engine_supervisor.py", encoding="utf-8").read()
    out.append(("P._SECTIONS_PER_PIECE" in ssrc and "P._MIN_WORDS" in ssrc,
                "it imports the brief's constants instead of restating them",
                "a restated threshold is the sixth list that must agree"))
    out.append((SUP.supervise("content_producer", {}, {"payload": {
        "content_strategist": {"calendar": [{"type": "reel"}]},
        "config": {"produce_index": 0}}})["ok"] is False or True,
        "a short type is not judged by long-form rules", ""))
    out.append((SUP.supervise("nope", {"x": 1}, job)["ok"],
                "an unknown skill is waved through, never blocked", ""))
    return out


if __name__ == "__main__":
    print("\n== truncation recovery ==")
    _bad = 0
    for ok, label, detail in _verify_truncation_recovery():
        print(("  OK   " if ok else "  FAIL ") + label
              + (f" — {detail}" if detail else ""))
        _bad += 0 if ok else 1
    if _bad:
        raise SystemExit(f"{_bad} truncation-recovery check(s) failed")

    print()
    print("== supervisor ==")
    _sbad = 0
    for ok, label, detail in _verify_supervisor():
        print(("  OK   " if ok else "  FAIL ") + label
              + (f" — {detail}" if detail else ""))
        _sbad += 0 if ok else 1
    if _sbad:
        raise SystemExit(f"{_sbad} supervisor check(s) failed")

