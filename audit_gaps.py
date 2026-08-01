"""WHAT IS ACTUALLY STOPPING THE MACHINE — every loop, every gap, one list.

    docker compose -f deploy/docker-compose.yml exec api python audit_gaps.py

"Nothing works" and "the cards are empty" are symptoms with different causes,
and until they are separated you cannot fix either. This walks every loop the
engine owns and reports, for each one, the ONE thing standing in its way:

    BLOCKED   a credential is missing, so the loop cannot run at all
    STARVED   it runs, but nothing has fed it yet, so its cards are honestly empty
    BROKEN    it ran and failed - with the reason
    RUNNING   it is working

A card showing zero is not the same as a card that is broken. This says which.
Reads live state only; invents nothing.
"""
import sys
from collections import Counter

BLOCKED, STARVED, BROKEN, RUNNING = "BLOCKED", "STARVED", "BROKEN", "RUNNING"


def main() -> int:
    import content_engine_api as API
    import content_engine_connectors as C
    import content_engine_dashboard as D

    store = API.get_store()
    get = getattr(store, "get_setting", lambda *a: None)
    try:
        status = C.status()
    except Exception as e:
        print("cannot read connector status:", e)
        return 1
    jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
    by_status = Counter(j.get("status", "?") for j in jobs)
    fails = Counter()
    for j in jobs:
        if j.get("status") in ("failed", "revision_needed", "halted_budget"):
            r = str(j.get("halt_reason") or j.get("qa_verdict") or j["status"])
            fails[r.split(":")[0].strip()[:60]] += 1

    def wire(k):
        return bool(status.get(k))

    def deals():
        try:
            import content_engine_bi as BI
            return len(BI.list_deals(store) or [])
        except Exception:
            return 0

    published = by_status.get("published", 0) + by_status.get("optimized", 0)
    sent = by_status.get("sent", 0)
    measured = sum(by_status.get(s, 0) for s in ("measured", "tracked", "learned", "optimized"))

    # (loop, the wire it needs, what it needs fed, live count, the fix)
    LOOPS = [
        ("Content: plan -> write -> approve -> publish",
         ["claude_api", "wordpress_publish"], "approved pieces", published,
         "approve a piece in AI Cockpit -> Approvals"),
        ("Content measurement: published -> GA4 -> playbook",
         ["google_gsc_ga4"], "published pieces past their window", measured,
         "wait for a measurement window to open"),
        ("Outreach: source -> qualify -> send",
         ["email_send", "web_search"], "approved campaigns", sent,
         "approve a campaign in AI Cockpit -> Approvals - Outreach"),
        ("Outreach measurement: opens, clicks, replies",
         ["email_reply_inbound"], "sent campaigns with tracking on", sent,
         "turn tracking on in Leads & Outreach"),
        ("SEO: crawl -> fix -> rank",
         ["seo_crawler", "seo_rank_tracker"], "SEO runs", 0,
         "the cadence runs these hourly once the engine is started"),
        ("AEO: are the AI engines quoting you",
         ["claude_api"], "answer engines connected", 0,
         "add OPENAI_API_KEY / PERPLEXITY_API_KEY / GEMINI_API_KEY"),
        ("Social distribution",
         ["social_linkedin"], "published social posts", 0,
         "connect the channels you actually want to post to"),
        ("Paid: bid -> spend -> CPA",
         ["ads_api"], "live campaigns", 0, "campaigns must be approved to spend"),
        ("Money: work -> deal -> revenue",
         [], "recorded deals", deals(),
         "record your first deal in Business Intelligence"),
        ("Bookings",
         ["calcom_bookings"], "booked consultations", 0, "connect Cal.com"),
    ]

    print("=" * 68)
    print("WHY EACH LOOP IS OR IS NOT PRODUCING")
    print("=" * 68)
    tally = Counter()
    for name, wires, feeds, n, fix in LOOPS:
        missing = [w for w in wires if not wire(w)]
        if missing:
            state, why = BLOCKED, f"needs {', '.join(missing)}"
        elif n:
            state, why = RUNNING, f"{n} {feeds}"
        else:
            state, why = STARVED, f"no {feeds} yet"
        tally[state] += 1
        print(f"  {state:<8} {name}")
        print(f"           {why}")
        if state != RUNNING:
            print(f"           -> {fix}")
    print()
    print("  " + " · ".join(f"{k} {v}" for k, v in tally.most_common()))

    print()
    print("=" * 68)
    print("JOBS THAT FAILED, BY CAUSE")
    print("=" * 68)
    if not fails:
        print("  none")
    for reason, n in fails.most_common(8):
        print(f"  {n:>3} x  {reason}")

    print()
    print("=" * 68)
    print("FRONT-END GAPS  (settable keys with NO field on the dashboard)")
    print("=" * 68)
    allowed = set(C.CONNECTOR_ENV_KEYS)
    # If the render fails, SAY SO. Reporting an empty page as "40 keys have no
    # field" is a false alarm dressed as a finding - the same mistake that once
    # condemned a perfectly good database backup.
    html, render_err = "", ""
    try:
        html = API.api_dashboard_html()
    except Exception as e:
        render_err = f"{type(e).__name__}: {e}"
    if len(html) < 20000:
        try:
            html = D.dashboard_html(
                jobs=jobs, st=status, health={"healthy": True}, month_spent=0,
                month_cap=200, day_spent=0, day_cap=50, taste_skills=[])
            render_err = ""
        except Exception as e:
            render_err = render_err or f"{type(e).__name__}: {e}"
    if len(html) < 20000:
        print(f"  SKIPPED - the dashboard did not render ({render_err or 'too small'}).")
        print("  Run this INSIDE the api container, where the store is reachable.")
        html = ""
    import re
    on_page = set(re.findall(r"<input[^>]*name='([A-Z0-9_]+)'", html)) if html else allowed
    # A CONNECTED key deliberately shows "connected + Disconnect" instead of an
    # input, so "no field" is the correct rendering for it - not a gap. The
    # first version of this audit reported all 33 connected keys as unreachable,
    # which is a false alarm, and a false alarm in an audit is worse than a
    # missing check: it sends you hunting for a problem that is not there.
    def _is_set(k):
        try:
            return bool(str(get(k, "") or "").strip())
        except Exception:
            return False

    # Without a readable store every key looks "not set", so a CONNECTED key
    # gets misfiled as unreachable. Say that plainly instead of producing a
    # confident wrong list - this file has now produced two false alarms and
    # both came from reporting an unknown as a finding.
    store_readable = any(_is_set(k) for k in list(allowed)[:40])
    if not store_readable:
        print("  NOTE: settings are not readable from here, so 'connected' "
              "cannot be told apart from 'missing'.")
        print("  Run this inside the api container for an accurate split.")
    no_field = allowed - on_page
    connected = sorted(k for k in no_field if _is_set(k))
    unreachable = sorted(no_field - set(connected))
    print(f"  allow-listed keys        : {len(allowed)}")
    print(f"  with a field on screen   : {len(allowed & on_page)}")
    print(f"  already connected        : {len(connected)}  "
          f"(no input by design - Disconnect first to replace)")
    if unreachable:
        print(f"  UNREACHABLE (real gap)   : {len(unreachable)}")
        for k in unreachable:
            print(f"     {k}")
    else:
        print("  UNREACHABLE (real gap)   : 0  "
              "- every unset key has a field you can type into")

    unlabelled = sorted(on_page - set(re.findall(r"<label for='f-([A-Z0-9_]+)'", html)))
    if unlabelled:
        print(f"\n  fields with NO label ({len(unlabelled)}): {unlabelled[:8]}")

    print()
    print("=" * 68)
    print("CREDENTIALS THE PROVIDER ACTIVELY REJECTED")
    print("=" * 68)
    # A key that is SET but REFUSED is the worst state: the dashboard shows it
    # as configured, the loop that needs it does nothing, and the only evidence
    # is a stack trace in the logs. During the run that produced this file, a
    # Google token refresh returned 401 and it printed as noise in the middle of
    # the output rather than as a finding.
    try:
        rejected = C.auth_reasons() or {}
    except Exception as e:
        rejected = {}
        print(f"  could not read rejection state: {e}")
    if rejected:
        for k, why in rejected.items():
            print(f"  REJECTED  {k}")
            print(f"            {str(why)[:100]}")
        print("\n  A rejected key is not a missing key. Replace it - "
              "do not add another.")
    else:
        print("  none - every saved credential that has been used was accepted")

    print()
    print("=" * 68)
    print("THE ONE THING TO DO NEXT")
    print("=" * 68)
    blocked = [n for n, w, _f, _c, _x in LOOPS if any(not wire(x) for x in w)]
    if by_status.get("AWAITING_APPROVAL"):
        print(f"  {by_status['AWAITING_APPROVAL']} piece(s) are waiting for YOUR approval.")
        print("  Nothing downstream of them can run until you decide.")
    elif blocked:
        print(f"  {len(blocked)} loop(s) are blocked on a credential. Start with:")
        print(f"    {blocked[0]}")
    elif tally[STARVED]:
        print("  Nothing is blocked. The loops are STARVED - they are waiting for")
        print("  work to finish, not for you to fix anything.")
    else:
        print("  Everything is running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
