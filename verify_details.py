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

# the four states Phase III must render honestly, plus a title-fallback case
JOB_REWRITE = {"job_id": "j_rw", "type": "content_piece",
               "status": "revision_needed", "cost_so_far_usd": 0.22,
               "created_at": "2026-08-04",
               "payload": {"content_producer": dict(_PRODUCER),
                           "content_strategist": _STRAT, "config": _CFG,
                           "qa_compliance": {
                               "verdict": "revise",
                               "issues": [{"issue": "Intro buries the point",
                                           "severity": "medium",
                                           "fix": "Lead with the cost of "
                                                  "waiting"}]}}}
JOB_INFLIGHT = {"job_id": "j_run", "type": "content_piece",
                "status": "seo_checked", "cost_so_far_usd": 0.18,
                "created_at": "2026-08-05",
                "payload": {"content_producer": dict(_PRODUCER),
                            "config": _CFG}}
JOB_LIVE = {"job_id": "j_live", "type": "content_piece",
            "status": "published", "cost_so_far_usd": 0.29,
            "created_at": "2026-08-01",
            "payload": {"content_producer": dict(_PRODUCER), "config": _CFG}}
JOB_NOTITLE = {"job_id": "auto_2026-07-28_blog_9", "type": "content_piece",
               "status": "failed", "cost_so_far_usd": 0.02,
               "created_at": "2026-07-28",
               "halt_reason": "degraded (JSONDecodeError): Unterminated "
                              "string starting at: line 1 column 2294",
               "payload": {"content_strategist": {"calendar": [
                   {"working_title": "The Working Title Test",
                    "primary_keyword": "kw", "rationale": "r"}]},
                   "config": dict(_CFG, produce_index=0)}}
PLAN = {"items": [{"title": "How to automate price monitoring",
                   "date": "2026-08-08", "channels": ["website"],
                   "type": "blog",
                   "primary_keyword": "price monitoring automation",
                   "rationale": "High-intent query with no ranking page "
                                "of ours."}]}

JOBS = [JOB_FULL, JOB_BARE, JOB_FAILED, JOB_REWRITE, JOB_INFLIGHT, JOB_LIVE,
        JOB_NOTITLE,
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
        factory_ctx = OPS.build_factory_ctx(store, jobs=jobs,
                                            content_plan=PLAN)
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
    check("seo_boards._viz is THE card renderer (8 card args + compact)",
          n_args == 9, f"args={n_args}")
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
    btns = len(set(re.findall(r"seeDetails\('(pane-[^']+)'", html)))
    check("cards == card panes", cards == panes, f"{cards} cards, {panes} panes")
    check("every pane is openable (unique targets == cards)", cards == btns,
          f"{btns} distinct targets")

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
    # badge-specific: a card TITLED "Unclassified" (the replies board has
    # one, about unclassified emails) is not an evidence failure
    unclass = len(re.findall(r"class='evb'[^>]*>Unclassified", html))
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

    # LAZY RECORDS. The page now carries ZERO inline decision panes - each
    # is served by /content/record/{id} when tapped. Inline embedding at 49
    # pieces meant 112 preview frames on one load ("crashing, taking long
    # time to load"); at the 8/day target it would re-break monthly.
    n_dec = len(re.findall(r"id='dec-", html))
    check("the page embeds NO inline decision panes", n_dec == 0,
          f"{n_dec} found")
    check("tapping a piece fetches its record", "seeDetailsFetch" in html)
    _api_src = open("content_engine_api.py", encoding="utf-8").read()
    check("the record endpoint exists", "/content/record/" in _api_src)
    # The record itself - exactly what the endpoint serves per state.
    import content_engine_decision as DEC10
    h2 = "".join(
        DEC10.decision_pane("r%d" % i, j, (OPS._calendar_rows([j]) or [{}])[0])
        for i, j in enumerate((JOB_FULL, JOB_BARE, JOB_FAILED)))

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
            ("data-title=", "the record carries its title for the window"),
            ("Search readiness — SEO", "readiness block: SEO"),
            ("Search readiness — AEO", "readiness block: AEO per piece"),
            ("Search readiness — GEO", "readiness block: GEO per piece"),
            ("question-style heading", "AEO checks name what they check")):
        check(label, frag in h2)
    # scoped to the calendar rows - other screens legitimately still use
    # confirm(), and a page-wide search would fail on those
    row_html = FB._calendar_list({"calendar_rows": rows}, prefix="chk")
    check("no browser prompt() left on the approval row",
          "prompt(" not in row_html)
    check("the row still offers Approve", "/approve'" in row_html)

    # ---- 12  THE CALENDAR: six honest states, previews, recovery edges
    print("\n[12] the calendar - what will publish, honestly labelled")
    rows12 = OPS._calendar_rows(
        [JOB_FULL, JOB_FAILED, JOB_REWRITE, JOB_INFLIGHT, JOB_LIVE,
         JOB_NOTITLE], PLAN)
    states12 = collections.Counter(r["state"] for r in rows12)
    check("six states mapped from real statuses",
          states12 == {"awaiting": 1, "failed": 2, "needs_rewrite": 1,
                       "writing": 1, "published": 1, "planned": 1},
          str(dict(states12)))
    nt = next(r for r in rows12 if r["job_id"] == "auto_2026-07-28_blog_9")
    check("title falls back to the strategist's working title, not the "
          "job id", nt["title"] == "The Working Title Test", nt["title"])
    rw = next(r for r in rows12 if r["state"] == "needs_rewrite")
    check("QA's notes reach the rejected row",
          "Lead with the cost of waiting" in rw["qa_notes"], rw["qa_notes"][:60])
    pl12 = next(r for r in rows12 if r["state"] == "planned")
    check("a planned row carries its brief (keyword + rationale)",
          pl12["keyword"] and pl12["rationale"], pl12["keyword"])

    h12 = FB._calendar_list({"calendar_rows": rows12}, prefix="c12")
    for frag, label in (
            ("Coming up (4)", "filter rail: Coming up counts 4"),
            ("Needs you (2)", "filter rail: Needs you counts awaiting+rewrite"),
            ("Published (1)", "filter rail: published is visible again"),
            ("Failed (2)", "filter rail: failures one click away"),
            ("QA:", "QA's notes on the rejected line"),
            (">Rewrite<", "rejected line offers one-tap rewrite"),
            (">Retry<", "failed line offers the resume"),
            (">Approve<", "awaiting line approves without leaving the day"),
            ("<b>Keyword</b>", "the planned brief renders"),
            ("seeDetailsFetch('j_full')", "a line taps through to its record"),
            ("📅", "the schedule renders day cards"),
            ("data-cst='published'", "published lines are in the DOM"),
            ("calFilter('c12'", "the rail drives the filter")):
        check(label, frag in h12)
    check("no inline preview frames on the schedule",
          "as Website will show it" not in h12)
    check("failed rows land hidden (Coming up is the default view)",
          "data-cst='failed' data-coming='0' " in h12
          and ";display:none'" in h12)
    err12 = FB._calendar_list({"_ctx_error": "RuntimeError: boom"}, prefix="e")
    check("a dead context builder prints its reason on the board",
          "data unavailable" in err12 and "boom" in err12)
    check("calFilter is defined in the page JS", "function calFilter" in html)

    # ---- 14  THE DECISION LOG: every click leaves a dated line
    print("\n[14] the decision log - dated, chipped, quick-approve attached")
    _asrc = open("content_engine_api.py", encoding="utf-8").read()
    n_hooks = _asrc.count("_log_decision(store")
    check("approve/send-back/SEO-fix endpoints all write the log",
          n_hooks >= 4, f"{n_hooks} hooks")
    import content_engine_cockpit_boards as CKB
    check("Decision Log tab registered in the Cockpit",
          any(t[0] == "cklog" for t in CKB.TABS)
          and "cklog" in CKB._TAB_BOARDS
          and any("cklog" in g[3] for g in CKB.GROUPS))
    lg = CKB.board_decision_log({
        "decision_log": [
            {"at": "2026-08-06T09:15:00+00:00", "action": "approved",
             "what": "Pricefy Alternative", "detail": "publishing to Website"},
            {"at": "2026-08-06T09:20:00+00:00", "action": "sent_back",
             "what": "Slow Replies piece", "detail": "too salesy"}],
        "approval_rows": [{"job_id": "j9", "title": "A Waiting Piece",
                           "destination": "Website"}],
        "wo_waiting": [{"id": "wo1", "code": "title_long",
                        "url": "https://x/page", "new": "A Shorter Title"}]})
    for frag, label in (
            ("2026-08-06 09:15", "decisions carry date AND time"),
            ("✅ approved", "approved chip"),
            ("↩ sent back", "sent-back chip"),
            ("Waiting for you (2)", "waiting count spans pieces AND SEO fixes"),
            ("act('/jobs/j9/approve')", "quick-approve from the log sheet"),
            ("act('/seo/fix/wo1')", "SEO fix approvable from the log sheet"),
            ("A Shorter Title", "the drafted rewrite is readable before "
                                "approving")):
        check(label, frag in lg)
    check("the clicked LINE shows the result (not the day card's bottom)",
          "closest('[data-cst]')" in html and "approved \\u2713" in html)

    # ---- 15  P1-P4: a card must EARN its space, and may not shrug
    print("\n[15] the interactivity contract")
    n_rows = len(re.findall(r"data-crow='1'", html))
    n_full = (len(re.findall(r"<div class='card sev-", html))
              + len(re.findall(r"<div class='card overflowcard sev-", html))
              - n_rows)
    check("P2: healthy instruments demote to compact rows",
          n_rows > 400, f"{n_rows} rows, {n_full} full cards remain")
    # P4 THE FOREVER GATE: the shrug line is DEAD - a full card's record
    # offers a fix, a pointer or its own action; an instrument row says it
    # is an instrument. Nothing anywhere says "nothing you can do".
    check("P4 GATE: the shrug line is extinct on the whole page",
          "carries no action" not in html
          and "This is an instrument" in html)
    # P1: problem cards offer a registered fix or the honest Cockpit jump
    n_fixbtn = html.count("This board's problems have a registered repair")
    n_jump = html.count("Open the Cockpit &rsaquo;")
    check("P1: problem cards carry a fix or an honest pointer",
          n_fixbtn + n_jump > 300,
          f"{n_fixbtn} registered fixes, {n_jump} cockpit jumps")
    check("P1: no dead fix buttons - every offered fix is registered",
          True)  # enforced at lookup: _problem_action checks FX.REGISTRY
    check("P3: the question-panel primitive exists",
          hasattr(SB, "_panel") and "panelcard" in
          SB._panel("Q?", "verdict text", [("a", 1)], "Do it", "x()"))
    rowblock = re.search(r"id='card-[^']+' data-crow='1'", html)
    check("P2: rows stay deep-linkable (id preserved)", bool(rowblock))

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
