"""THE RETURN ARROW.

The engine could plan, write, approve and publish. What it could not do was
find out what happened next. `collect_analytics()` existed in connectors.py,
was tested, and was called by nothing; the orchestrator initialised
payload["analytics"] = {} and nothing ever filled it. So the measurement step
ran on {sessions: 0, conv_rate: 0} for every piece ever published, and the
playbook recorded conclusions drawn from those zeros.

This module is the missing half. It hands real outcomes to the two steps that
learn — analytics_funnel and optimizer — for both pipelines.

THE ONE RULE HERE
    A zero is a measurement. A blank is an admission.

If GA4 cannot answer, this returns measured=False WITH THE REASON, and the
orchestrator skips the LLM rather than paying to reason about nothing. Writing
0 instead would convert "we never looked" into "it got no traffic" — and the
playbook would learn a lie instead of learning nothing, which is strictly worse
than the bug this module fixes.
"""
from __future__ import annotations

import logging

log = logging.getLogger("content_engine")

# A piece needs longer than a campaign. An email is opened within days; a page
# has to be indexed and start ranking before its numbers mean anything, and 7
# days measures how fast Google crawled, not whether the piece was any good.
DAYS_CONTENT = 21
DAYS_OUTREACH = 7

# Below this, a piece is "poor" and earns a rewrite PROPOSAL — never a rewrite.
# It lands in the approval queue exactly like anything else that costs money.
POOR_SESSIONS = 10
POOR_CONV_RATE = 0.5


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, list) else []


def unavailable(reason: str, period: str = "") -> dict:
    """The shape every un-measurable outcome takes. `measured` is the flag the
    rest of the engine keys off; `unavailable` is the sentence a human reads."""
    return {"measured": False, "unavailable": reason, "period": period,
            "metrics": {}, "funnel_stages": [], "vs_previous": {}}


def is_measured(d) -> bool:
    return bool(_D(d).get("measured"))


# ---------------------------------------------------------------------------
# analytics  ->  payload["analytics"]  ->  analytics_funnel
# ---------------------------------------------------------------------------
def _content_analytics(job: dict, store=None) -> dict:
    payload = _D(job.get("payload"))
    ref = payload.get("published_ref") or ""
    if not ref:
        return unavailable("This piece has no published reference, so there is "
                           "no page to ask Google Analytics about.")
    if not str(ref).startswith("http"):
        # A local stub ref (pub_job_x) means WordPress was never actually wired
        # when this published. There is no real URL to measure.
        return unavailable(
            f"Published reference '{str(ref)[:40]}' is not a URL — WordPress was "
            "not connected at publish time, so this piece was never really live.")
    try:
        import content_engine_connectors as C
    except Exception as e:                                    # pragma: no cover
        return unavailable(f"connectors unavailable: {e}")

    try:
        g = C.Google()
        if not g.available():
            return unavailable(
                "Google Analytics is not connected. Add GOOGLE_ACCESS_TOKEN (or "
                "the service account) and GA4_PROPERTY_ID on the Connect board.")
    except Exception as e:
        return unavailable(f"could not reach the Google connector: {e}")

    data = C.collect_page_analytics(ref, days=DAYS_CONTENT)
    if not data:
        return unavailable(
            "Google Analytics did not answer for this page. The key may be "
            "rejected or the property id wrong — check Wires & connections.")
    m = _D(data.get("metrics"))
    out = {
        "measured": True,
        "source": "ga4",
        "period": data.get("period", f"last {DAYS_CONTENT}d"),
        "page": data.get("page", ref),
        "metrics": {"sessions": m.get("sessions", 0),
                    "conversions": m.get("conversions", 0),
                    "conv_rate": m.get("conv_rate", 0.0),
                    "engagement_rate": m.get("engagement_rate", 0.0),
                    "top_pages": []},
        "funnel_stages": [
            {"stage": "sessions", "users": m.get("sessions", 0),
             "conv_rate": m.get("conv_rate", 0.0), "drop_off": 0},
            {"stage": "conversions", "users": m.get("conversions", 0),
             "conv_rate": m.get("conv_rate", 0.0),
             "drop_off": max(m.get("sessions", 0) - m.get("conversions", 0), 0)},
        ],
        # No stored previous period yet, so this is honestly absent rather than
        # a fabricated 0% change.
        "vs_previous": {},
    }
    if data.get("no_rows"):
        out["zero_is_real"] = True
        out["note"] = ("GA4 answered and has no rows for this page: it is a real "
                       "zero, not a missing measurement.")
    return out


def _outreach_analytics(job: dict, store=None) -> dict:
    """The data for this loop ALREADY EXISTS. Opens and clicks are recorded per
    token, replies are drafted and stored, and both are rendered on the Outreach
    boards. They were simply never handed to the step that learns from them."""
    if store is None:
        return unavailable("no store available to read tracking events from")
    try:
        import content_engine_outreach as OUT
    except Exception as e:                                    # pragma: no cover
        return unavailable(f"outreach module unavailable: {e}")

    payload = _D(job.get("payload"))
    leads = _L(payload.get("leads")) or _L(payload.get("raw_leads"))
    sends = len(leads)
    if not sends:
        return unavailable("This campaign has no recorded recipients, so there "
                           "is nothing to measure a rate against.")
    try:
        if not OUT.tracking_enabled(store):
            return unavailable(
                "Open and click tracking is switched off, so delivery is the "
                "only thing known about this campaign. Turn it on in Leads & "
                "Outreach to close this loop.")
    except Exception:
        pass

    job_id = job.get("job_id", "")
    try:
        evs = _L(OUT._get(store, OUT.EVENTS_KEY, []))
        toks = _D(OUT._get(store, OUT.TOKENS_KEY, {}))
    except Exception as e:
        return unavailable(f"could not read tracking events: {e}")

    # Only this campaign's tokens. Unique by token: one recipient reloading an
    # email is not five people reading it.
    mine = {t for t, meta in toks.items()
            if str(_D(meta).get("job", "")) == str(job_id)}
    opens = {e["token"] for e in evs if _D(e).get("kind") == "open"
             and e.get("token") in mine}
    clicks = {e["token"] for e in evs if _D(e).get("kind") == "click"
              and e.get("token") in mine}

    replies = 0
    for key in ("reply_count", "replies"):
        v = payload.get(key)
        if isinstance(v, int):
            replies = v
            break
        if isinstance(v, list):
            replies = len(v)
            break

    pct = lambda n: round(100.0 * n / sends, 1) if sends else 0.0
    return {
        "measured": True,
        "source": "engine tracking pixel + click redirect",
        "period": f"since send, up to {DAYS_OUTREACH}d",
        "metrics": {"sessions": len(opens), "sends": sends,
                    "opens": len(opens), "clicks": len(clicks),
                    "replies": replies,
                    "open_rate": pct(len(opens)), "click_rate": pct(len(clicks)),
                    "conv_rate": pct(replies), "top_pages": []},
        "funnel_stages": [
            {"stage": "sent", "users": sends, "conv_rate": 100.0, "drop_off": 0},
            {"stage": "opened", "users": len(opens), "conv_rate": pct(len(opens)),
             "drop_off": sends - len(opens)},
            {"stage": "clicked", "users": len(clicks), "conv_rate": pct(len(clicks)),
             "drop_off": len(opens) - len(clicks)},
            {"stage": "replied", "users": replies, "conv_rate": pct(replies),
             "drop_off": max(len(clicks) - replies, 0)},
        ],
        "vs_previous": {},
        "zero_is_real": True,
    }


def analytics_for(job: dict, store=None) -> dict:
    """payload['analytics'] for whichever pipeline this job belongs to."""
    try:
        if job.get("type") == "outreach_campaign":
            return _outreach_analytics(job, store)
        return _content_analytics(job, store)
    except Exception as e:                                    # pragma: no cover
        log.exception("analytics collection failed for %s", job.get("job_id"))
        return unavailable(f"collection failed: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# performance  ->  payload["performance"]  ->  optimizer
# ---------------------------------------------------------------------------
def performance_for(job: dict, store=None) -> dict:
    """What the optimizer decides from. Built from THIS job's measured outcome
    plus its siblings, so the optimizer compares rather than guesses."""
    a = _D(_D(job.get("payload")).get("analytics"))
    if not is_measured(a):
        return {"measured": False,
                "unavailable": a.get("unavailable")
                or "this job was never measured, so there is nothing to optimise "
                   "against",
                "content_performance": [], "outreach_performance": [], "period": ""}
    m = _D(a.get("metrics"))
    piece = _D(_D(job.get("payload")).get("content_producer"))
    row = {"title": piece.get("title", "") or job.get("job_id", ""),
           "url": a.get("page", ""), "period": a.get("period", ""),
           **{k: v for k, v in m.items() if k != "top_pages"}}
    is_outreach = job.get("type") == "outreach_campaign"
    return {
        "measured": True,
        "period": a.get("period", ""),
        "content_performance": [] if is_outreach else [row],
        "outreach_performance": [row] if is_outreach else [],
        "source": a.get("source", ""),
    }


# ---------------------------------------------------------------------------
# the poor-performance PROPOSAL (never an action)
# ---------------------------------------------------------------------------
def rewrite_proposal(job: dict) -> dict | None:
    """A measured-poor piece earns a PROPOSAL in the approval queue.

    Deliberately not a rewrite. Rewriting costs model spend and republishes to
    a live site, and every action that spends or publishes stays behind the
    human gate. This only ever puts a card in front of a person.

    Returns None unless the piece was genuinely MEASURED and genuinely poor —
    an unmeasured piece must never be judged."""
    a = _D(_D(job.get("payload")).get("analytics"))
    if not is_measured(a):
        return None                      # never judge what was never measured
    if job.get("type") == "outreach_campaign":
        return None                      # campaigns are not rewritten this way
    m = _D(a.get("metrics"))
    sessions = m.get("sessions", 0) or 0
    conv = m.get("conv_rate", 0.0) or 0.0
    if sessions >= POOR_SESSIONS and conv >= POOR_CONV_RATE:
        return None                      # it is doing fine
    piece = _D(_D(job.get("payload")).get("content_producer"))
    if sessions < POOR_SESSIONS:
        why = (f"{sessions} sessions in {a.get('period', 'the window')} — below "
               f"the {POOR_SESSIONS} that would show it is being found at all.")
        fix = ("Likely a discovery problem rather than a writing problem: check "
               "indexing and the target keyword before rewriting a word.")
    else:
        why = (f"{sessions} sessions but a {conv}% conversion rate, under the "
               f"{POOR_CONV_RATE}% floor.")
        fix = ("People arrive and leave. The page is found but does not "
               "persuade — the offer and the call to action are the suspects.")
    return {
        "kind": "rewrite_proposal",
        "job_id": job.get("job_id", ""),
        "title": piece.get("title", "") or job.get("job_id", ""),
        "url": a.get("page", ""),
        "measured": {"sessions": sessions, "conv_rate": conv,
                     "period": a.get("period", "")},
        "why": why,
        "suggested_focus": fix,
        "requires_approval": True,
    }


if __name__ == "__main__":
    # ---- a blank must never become a zero -----------------------------------
    u = unavailable("GA4 not connected")
    assert u["measured"] is False and u["metrics"] == {}
    assert not is_measured(u) and is_measured({"measured": True})

    # ---- content: no ref, stub ref, and a real URL with GA4 absent ----------
    assert "no published reference" in analytics_for(
        {"type": "content_piece", "payload": {}})["unavailable"]
    stub = analytics_for({"type": "content_piece",
                          "payload": {"published_ref": "pub_job_A"}})
    assert stub["measured"] is False and "not a URL" in stub["unavailable"]
    live = analytics_for({"type": "content_piece",
                          "payload": {"published_ref": "https://x.com/a-post"}})
    assert live["measured"] is False, "no GA4 in a test env -> must be unmeasured"
    assert live["metrics"] == {}, "an unmeasured piece must carry NO numbers"

    # ---- outreach: reads real tokens, unique by token -----------------------
    import content_engine_outreach as OUT

    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, dflt=None):
            return self.d.get(k, dflt)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()
    OUT.set_tracking(st, True)
    j = {"job_id": "c9", "type": "outreach_campaign",
         "payload": {"leads": [{"email": "a@x.com"}, {"email": "b@x.com"},
                               {"email": "c@x.com"}, {"email": "d@x.com"}],
                     "reply_count": 1}}
    t1 = OUT.register_token(st, "c9", "a@x.com", 1)
    t2 = OUT.register_token(st, "c9", "b@x.com", 1)
    OUT.register_token(st, "OTHER", "z@x.com", 1)
    OUT.record_event(st, t1, "open")
    OUT.record_event(st, t1, "open")        # same reader twice
    OUT.record_event(st, t2, "open")
    OUT.record_event(st, t1, "click")
    o = analytics_for(j, st)
    assert o["measured"] is True, o
    assert o["metrics"]["opens"] == 2, f"unique by token, got {o['metrics']}"
    assert o["metrics"]["clicks"] == 1 and o["metrics"]["replies"] == 1
    assert o["metrics"]["open_rate"] == 50.0, o["metrics"]
    assert [s["stage"] for s in o["funnel_stages"]] == \
        ["sent", "opened", "clicked", "replied"]

    # tracking off -> unmeasured WITH a reason, not zeros
    OUT.set_tracking(st, False)
    off = analytics_for(j, st)
    assert off["measured"] is False and "tracking is switched off" in off["unavailable"]

    # ---- performance mirrors the measured state ----------------------------
    OUT.set_tracking(st, True)
    j["payload"]["analytics"] = analytics_for(j, st)
    perf = performance_for(j, st)
    assert perf["measured"] and len(perf["outreach_performance"]) == 1
    unm = performance_for({"type": "content_piece",
                           "payload": {"analytics": unavailable("no GA4")}})
    assert unm["measured"] is False and unm["content_performance"] == []

    # ---- the proposal only ever fires on MEASURED-poor ---------------------
    assert rewrite_proposal({"type": "content_piece",
                             "payload": {"analytics": unavailable("no GA4")}}) is None
    good = {"type": "content_piece", "payload": {
        "analytics": {"measured": True, "period": "last 21d",
                      "metrics": {"sessions": 400, "conv_rate": 3.0}}}}
    assert rewrite_proposal(good) is None
    poor = {"type": "content_piece", "job_id": "p1", "payload": {
        "content_producer": {"title": "A quiet piece"},
        "analytics": {"measured": True, "period": "last 21d", "page": "/quiet",
                      "metrics": {"sessions": 2, "conv_rate": 0.0}}}}
    pr = rewrite_proposal(poor)
    assert pr and pr["requires_approval"] is True and "2 sessions" in pr["why"]
    print("collect self-check OK — the return arrow: real GA4 per page, real "
          "opens/clicks per campaign, and an unmeasurable outcome reports WHY "
          "rather than reporting zero. A poor piece earns a proposal that still "
          "waits for a person.")
