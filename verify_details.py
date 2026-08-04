# -*- coding: utf-8 -*-
"""THE DETAIL WINDOW, PROVEN AGAINST A REAL RENDER.

Every claim this feature makes is checked here against HTML that was actually
produced, not against the source that was supposed to produce it. A board
self-check that renders with an empty context has passed while the function it
tests raised - so this file renders the whole dashboard with real jobs and
reads the output back.

  1  one card renderer, not two
  2  every authored src token classified          (static)
  3  every RENDERED src token classified          (runtime)
  4  every card has exactly one detail pane
  5  every pane carries all six required sections
  6  no duplicate DOM ids anywhere on the page
  7  the dialog, its handlers and Esc exist
  8  no evidence explanation is too short to be useful
  9  declared / link-only cards are visibly badged as not-measurement

Run:  python verify_details.py
"""
from __future__ import annotations

import collections
import html as _html
import re
import sys

FAILS: list = []
PASSES: list = []


def check(name, ok, detail=""):
    (PASSES if ok else FAILS).append(name)
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  {detail}" if detail else ""))
    return ok


# ONE FIXTURE, used by the page render AND the decision checks. They used to
# be two, which is how the page rendered zero decision panes while the decision
# test was green: each was right about its own data and neither described the
# other's.
_BODY = ("## Why this matters\n\n"
         + "Retailers lose margin every hour a rival price moves. " * 12
         + "\n\n## What to do\n\n- Track daily\n- Alert on change\n\n"
           "![hero](x.png)\n\n## The cost of waiting\n\n"
         + "Waiting is expensive. " * 30)

_PRODUCER = {"title": "Pricefy Alternative: Automated Price Monitoring",
             "body": _BODY,
             "meta_title": "Pricefy Alternative: Automated Price Monitoring "
                           "For Retail Teams 2026",
             "meta_description": "Monitor competitor prices automatically.",
             "cta_text": "Book a call", "hashtags": ["#pricing", "#retail"],
             "image_prompts": ["a", "b", "c"]}

_STRAT = {"calendar": [{"date": "2026-08-06", "type": "blog",
                        "primary_keyword": "price monitoring",
                        "target_segment": "ecommerce ops leads",
                        "business_goal": "pipeline", "priority": "high",
                        "rationale": "Competitor brand term with clear buying "
                                     "intent and no page of ours ranking for "
                                     "it."}]}

# deploy_channels is the real key - api.py writes it when the job is created
_CFG = {"deploy_channels": ["website", "linkedin"]}

JOB_FULL = {"job_id": "j_full", "type": "content_piece",
            "status": "AWAITING_APPROVAL", "cost_so_far_usd": 0.31,
            "created_at": "2026-08-05",
            "payload": {"content_producer": _PRODUCER,
                        "content_strategist": _STRAT, "config": _CFG,
                        "qa_compliance": {
                            "verdict": "revise", "brand_voice_match": True,
                            "issues": [
                                {"issue": "Claims 40% time saving with no source",
                                 "location": "section 3", "severity": "high",
                                 "fix": "Attribute it or soften to a range"},
                                {"issue": "Second CTA repeats the first",
                                 "location": "end", "severity": "low",
                                 "fix": "Remove one"}]},
                        "seo_optimizer": {
                            "seo_ready": False,
                            "checks": {"title": True, "meta": False,
                                       "h1": True, "internal_links": False},
                            "fixes": ["Add a meta description",
                                      "Link to two related guides"]}}}

JOB_BARE = {"job_id": "j_bare", "type": "content_piece",
            "status": "AWAITING_APPROVAL", "cost_so_far_usd": 0.04,
            "created_at": "2026-08-05",
            "payload": {"content_producer": _PRODUCER, "config": _CFG}}

JOB_FAILED = {"job_id": "j_fail", "type": "content_piece", "status": "failed",
              "cost_so_far_usd": 0.09, "created_at": "2026-08-05",
              "halt_reason": "qa_compliance: no model produced a valid result "
                             "after 3 attempts",
              "payload": {"content_producer": _PRODUCER, "config": _CFG}}

JOBS = [JOB_FULL, JOB_BARE, JOB_FAILED,
        {"job_id": "job_b2", "type": "content_piece", "status": "optimized",
         "payload": {}, "cost_so_far_usd": 0.11},
        {"job_id": "job_e5", "type": "outreach_campaign", "status": "sent",
         "payload": {"raw_leads": [{}] * 40, "leads": [{}] * 31,
                     "send_ref": "x"}, "cost_so_far_usd": 0.02}]


def render():
    import content_engine_dashboard as D
    jobs = JOBS
    # THROUGH THE REAL PATH. Calling _calendar_list() directly with rows I
    # built by hand proved the renderer works and proved nothing about whether
    # the dashboard ever reaches it - the page rendered with zero decision
    # panes while that test was green. api.py builds these contexts and passes
    # them in; so does this.
    import content_engine_seo_ops as OPS

    class _Store:
        """Minimal store: enough for context building, no database."""
        def __init__(self):
            self._s = {}

        def get_setting(self, key, default=None):
            return self._s.get(key, default)

        def set_setting(self, key, value):
            self._s[key] = value

        def all_jobs(self):
            return list(jobs)

        def list_jobs(self, *a, **k):
            return list(jobs)

    store = _Store()
    health = {"healthy": True, "anthropic": {"status": "ok"},
              "postgres": {"status": "ok"}}
    try:
        factory_ctx = OPS.build_factory_ctx(store, jobs=jobs)
    except Exception as e:
        print(f"  (build_factory_ctx raised {type(e).__name__}: {e})")
        factory_ctx = None
    try:
        cockpit_ctx = OPS.build_cockpit_ctx(store, jobs=jobs, health=health)
    except Exception as e:
        print(f"  (build_cockpit_ctx raised {type(e).__name__}: {e})")
        cockpit_ctx = None

    return D.dashboard_html(
        jobs=jobs, st={"wordpress_publish": True, "google_sheets": False},
        health=health,
        month_spent=63, month_cap=200, day_spent=4.2, day_cap=50,
        factory_ctx=factory_ctx, cockpit_ctx=cockpit_ctx,
        taste_skills=["content_producer", "seo_optimizer"])


def main():
    print("=" * 68)
    print("VERIFY DETAILS - rendered, then read back")
    print("=" * 68)

    # ---- 1  one card renderer
    print("\n[1] one card renderer")
    import content_engine_seo_boards as SB
    import content_engine_dashboard as D
    import inspect
    n_args = len(inspect.signature(SB._viz).parameters)
    check("seo_boards._viz is the 8-arg card renderer", n_args == 8, f"args={n_args}")
    check("dashboard no longer defines a rival _viz",
          not hasattr(D, "_viz") and hasattr(D, "_chartpanel"))

    # ---- 2  static token gate
    print("\n[2] every authored src token is classified and explained")
    import content_engine_evidence as EV
    ok, probs = EV.verify()
    check("static evidence table complete", ok, f"{len(probs)} problem(s)")
    for p in probs[:8]:
        print("        " + p)

    # ---- render once
    print("\n[render]")
    html = render()
    print(f"  {len(html) // 1024} KB of HTML")

    # ---- 3  runtime token gate
    print("\n[3] every RENDERED src token is classified")
    ok, probs = EV.verify_rendered(html)
    check("runtime evidence complete", ok, f"{len(probs)} unclassified")
    for p in probs[:10]:
        print("        " + p)

    # ---- 4  card == pane
    print("\n[4] every card has a detail pane")
    cards = (len(re.findall(r"<div class='card sev-", html))
             + len(re.findall(r"<div class='card overflowcard sev-", html)))
    # Tier 1 panes are id='pane-...'; Tier 2 decision panes are id='dec-...'
    # and carry a different, richer set of sections. Counting them together
    # made a working page look broken.
    panes = len(re.findall(r"class='dpane' id='pane-", html))
    btns = len(re.findall(r"seeDetails\('pane-", html))
    check("cards == card panes", cards == panes, f"{cards} cards, {panes} panes")
    check("cards == see-details buttons", cards == btns, f"{btns} buttons")

    # ---- 5  pane completeness
    print("\n[5] every card pane carries its required sections")
    required = ["The number", "What kind of number this is",
                "Where it comes from", "Why this colour",
                "What you can do from here"]
    pane_blocks = re.findall(r"<div class='dpane' id='pane-.*?</div></div>",
                             html, re.S)
    missing = collections.Counter()
    for blk in pane_blocks:
        for r in required:
            if f"<h4>{r}</h4>" not in blk:
                missing[r] += 1
    for r in required:
        check(f"section present: {r}", missing[r] == 0,
              f"missing on {missing[r]}" if missing[r] else "")

    # ---- 6  duplicate ids
    print("\n[6] no duplicate DOM ids")
    # ids INSIDE <script> are JS templates ("id='\"+wid+\"'"), not real
    # elements. Counting them reported duplicates that do not exist.
    body_only = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    ids = (re.findall(r"\sid='([^']+)'", body_only)
           + re.findall(r'\sid="([^"]+)"', body_only))
    dupes = {i: n for i, n in collections.Counter(ids).items() if n > 1}
    check("all element ids unique", not dupes,
          f"{len(dupes)} duplicated" if dupes else f"{len(ids)} ids")
    for i, n in list(dupes.items())[:8]:
        print(f"        {i!r} x{n}")

    # ---- 7  dialog + handlers
    print("\n[7] the dialog and its handlers exist")
    for frag, label in (("id='dlgwrap'", "dialog root"),
                        ("id='dlgbody'", "dialog body"),
                        ("function seeDetails", "seeDetails()"),
                        ("function closeDetails", "closeDetails()"),
                        ("async function microCmd", "microCmd()"),
                        ("e.key==='Escape'", "Esc closes"),
                        ("aria-modal='true'", "aria-modal"),
                        ("_dlgHome.appendChild", "pane is moved back, not copied")):
        check(label, frag in html)

    # ---- 8  explanation quality
    print("\n[8] no explanation too short to be useful")
    shorts = [t for t, (c, w) in EV.SOURCES.items() if len(str(w).strip()) < 40]
    check("every explanation >= 40 chars", not shorts,
          f"{len(shorts)} short" if shorts else f"{len(EV.SOURCES)} tokens")

    # ---- 9  non-measurements are badged
    print("\n[9] cards that are not measurements say so")
    badged = len(re.findall(r"class='evb'", html))
    unclass = len(re.findall(r"Unclassified</span>", html))
    toks = [_html.unescape(t) for t in
            re.findall(r"<h4>Where it comes from</h4><p><b>([^<]*)</b>", html)]
    dist = collections.Counter(EV.classify(t)["cls"] for t in toks)
    expect = dist["computed"] + dist["declared"] + dist["navigation"] + dist["unclassified"]
    check("every non-measured card carries a badge", badged == expect,
          f"{badged} badges vs {expect} non-measured cards")
    check("zero unclassified badges on the page", unclass == 0, f"{unclass} found")
    print("        " + "  ".join(f"{k}={v}" for k, v in dist.most_common()))

    # ---- 10  TIER 2: the decision record, in all three states
    print("\n[10] decision detail - present / not run / failed")
    import content_engine_seo_ops as OPS
    import content_engine_factory_boards as FB

    rows = OPS._calendar_rows([JOB_FULL, JOB_BARE, JOB_FAILED])
    check("every row carries its job", all("job" in r for r in rows),
          f"{len(rows)} rows")

    # THE PAGE, not the renderer. Checking _calendar_list() in isolation said
    # the decision record worked while the actual dashboard shipped zero of
    # them, because nothing built factory_ctx. Assert against `html`.
    n_dec = len(re.findall(r"id='dec-", html))
    check("decision panes reach the rendered page", n_dec > 0,
          f"{n_dec} on the page")
    h2 = html

    for frag, label in (
            ("Competitor brand term", "PRESENT: strategist rationale"),
            ("HIGH", "PRESENT: QA severity"),
            ("Attribute it or soften", "PRESENT: QA suggested fix"),
            ("Not SEO-ready", "PRESENT: SEO verdict"),
            ("9 over", "PRESENT: meta title over Google's limit"),
            ("NOT reversible", "PRESENT: linkedin is irreversible"),
            ("The QA check has not run", "NOT RUN: QA states absence"),
            ("The strategy step has not run", "NOT RUN: strategist"),
            ("The QA check failed", "FAILED: QA names the failure"),
            ("no model produced a valid result", "FAILED: real halt_reason"),
            ("Send back to the writer", "micro-command button"),
            ("<textarea class='dmc'", "micro-command is a textarea"),
            ("See the full record", "opens the detail window")):
        check(label, frag in h2)
    # scoped to the calendar rows - other screens legitimately still use
    # confirm(), and a page-wide search would fail on those
    row_html = FB._calendar_list({"calendar_rows": rows}, prefix="chk")
    check("no browser prompt() left on the approval row",
          "prompt(" not in row_html)
    check("the row still offers Approve", "/approve'" in row_html)

    # ---- 11  every link card says where it goes
    print("\n[11] link cards state their destination")
    targets = collections.Counter(re.findall(r"nav\('(\w+)'", html))
    unknown = sorted(t for t in targets if t not in EV.DESTINATIONS)
    check("every nav() target is described", not unknown,
          f"{len(targets)} targets, {len(unknown)} undescribed")
    for t in unknown[:10]:
        print(f"        nav('{t}') x{targets[t]} has no DESTINATIONS entry")
    n_where = len(re.findall(r"<h4>What is on the other side</h4>", html))
    check("destination sections rendered", n_where > 0, f"{n_where} cards")
    for d, why in EV.DESTINATIONS.items():
        if len(why.strip()) < 40:
            check(f"destination {d} explained", False, "too short")

    # ---- result
    print("\n" + "=" * 68)
    print(f"{len(PASSES)} passed, {len(FAILS)} failed")
    if FAILS:
        for f in FAILS:
            print("  FAILED: " + f)
        sys.exit(1)
    print("ALL CHECKS PASS - verified against rendered HTML, no network")


if __name__ == "__main__":
    main()
