"""THE CONTENT FACTORY, ALL THIRTEEN STATES, IN ONE SCREEN.

    docker compose -f deploy/docker-compose.yml exec api python factory_report.py

Read-only. No LLM calls. No spend. Nothing published, nothing sent.

WHY THIS EXISTS. Asked to audit the content factory I audited image generation,
because images were what I had in my head, and reported it as a factory audit.
The factory is thirteen states and eight skills; I had looked at one function
inside one of them. A report that enumerates the whole surface makes "what I
was thinking about" unable to masquerade as "what exists".

Every section answers a question that was previously answered by recollection.
"""
import sys
from collections import Counter

W = 78


def rule(title=""):
    print()
    print(("== " + title + " ").ljust(W, "=") if title else "=" * W)


def main() -> int:
    import content_engine_api as API
    import content_engine_orchestrator as O
    import content_engine_connectors as C
    import content_engine_factory as F
    import content_engine_code_skills as CS
    import content_engine_site_taxonomy as T

    store = API.get_store()
    try:
        jobs = store.list_jobs()
    except Exception:
        jobs = store.all() if hasattr(store, "all") else []
    pieces = [j for j in jobs if (j or {}).get("type") == "content_piece"]
    pieces.sort(key=lambda j: j.get("created_at") or "", reverse=True)

    print("CONTENT FACTORY REPORT".center(W))
    print(f"{len(jobs)} jobs total, {len(pieces)} content pieces".center(W))

    # ---------------------------------------------------------------- FLOW
    rule("1. FLOW — the thirteen states, and how far pieces actually get")
    flow = O.FLOWS.get("content_piece", {}) if hasattr(O, "FLOWS") else {}
    order = list(flow.keys())
    counts = Counter(str(j.get("status")) for j in pieces)
    reached = Counter()
    for j in pieces:
        st = str(j.get("status"))
        if st in order:
            for s in order[:order.index(st) + 1]:
                reached[s] += 1
    for st in order:
        skill = getattr(flow.get(st), "skill", None) or "-"
        here = counts.get(st, 0)
        bar = "#" * min(30, reached.get(st, 0))
        print(f"  {st:<20} {skill:<20} here:{here:<4} reached:"
              f"{reached.get(st, 0):<4} {bar}")
    stuck = {s: c for s, c in counts.items() if s not in order}
    if stuck:
        print()
        print("  NOT A FLOW STATE (terminal or error):")
        for s, c in sorted(stuck.items(), key=lambda kv: -kv[1]):
            print(f"    {s:<24} {c}")
    print()
    print("  A wall in the 'reached' column is where the factory stops. "
          "Anything at 0 has never run on a real job.")

    # ------------------------------------------------------------ CHANNELS
    rule("2. CHANNELS — does the publisher speak the same language as the boards?")
    # TEST THE BEHAVIOUR, DO NOT RESTATE THE LIST. The first version of this
    # section hard-coded the publisher's old CMS names here — so it compared a
    # list invented in this file against PLATFORMS and reported a break that
    # had already been fixed. A diagnostic that carries its own copy of the
    # thing it is checking is the bug it is checking for.
    plats = list(F.PLATFORMS)
    print(f"  PLATFORMS (previews / image rules) : {', '.join(plats)}")
    print(f"  publisher default when a job sets nothing : "
          f"{CS._target_channels({})}")
    print()
    print("  does each name reach the right place?")
    bad = []
    for alias in ("website", "wordpress", "wp", "cms", "blog", "linkedin",
                  "instagram", "x", "ig", "twitter", "youtube", "facebook"):
        canon = T.channel(alias)
        site = T.is_website(alias)
        known = canon in F.PLATFORMS
        ok = known and (site == (canon == "website"))
        if not ok:
            bad.append(alias)
        print(f"    {alias:<12} -> {canon:<12}"
              f"{'the SITE' if site else 'social':<10}"
              f"{'ok' if ok else 'UNKNOWN TO PLATFORMS'}")
    print()
    if bad:
        print(f"  !! {bad} do not resolve to a channel the preview and image")
        print("     rules know. Those jobs publish blind.")
    else:
        print("  Every alias resolves to a canonical channel that both the")
        print("  publisher and the preview/image rules recognise.")

    used = Counter()
    for j in pieces:
        cfg = ((j.get("payload") or {}).get("config") or {})
        raw = cfg.get("deploy_channels")
        for ch in (raw or ["(unset -> website)"]):
            used[T.channel(ch) if raw else "(unset -> website)"] += 1
    print()
    print("  what your jobs ACTUALLY carry (canonicalised):")
    for ch, n in used.most_common():
        role = ("the SITE" if ch.startswith("(unset") or T.is_website(ch)
                else "social" if ch in F.PLATFORMS else "UNKNOWN")
        print(f"    {ch:<22} {n:<4} {role}")
    social = sum(n for ch, n in used.items()
                 if ch in F.PLATFORMS and ch != "website")
    print()
    print(f"  pieces whose config names a social channel: {social}")
    if not social:
        print("  !! Every social channel is built and unreachable — nothing")
        print("     is putting them in deploy_channels.")

    # --------------------------------------------------------------- GATES
    rule("3. GATES — what each content type is allowed to receive")
    print(f"  {'type':<18}{'image':<8}{'linkedin':<10}{'research':<10}"
          f"{'length':<22}category")
    for t in T.CONTENT_TYPES:
        import content_engine_prep as P
        print(f"  {t:<18}{str(T.wants_image(t)):<8}"
              f"{str(T.wants_linkedin(t)):<10}{str(T.wants_research(t)):<10}"
              f"{P._LENGTH_BY_TYPE.get(t, '(blog default)'):<22}"
              f"{T.KIND_CATEGORY.get(t, '(nowhere)')}")
    print()
    print("  Three of these columns were hand-written lists that disagreed")
    print("  with the strategist. Printed here so a disagreement is visible.")

    # --------------------------------------------------------------- IMAGE
    rule("4. IMAGE — per piece")
    ic = Counter()
    reasons = Counter()
    for j in pieces:
        pl = j.get("payload") or {}
        pc = pl.get("content_producer") or {}
        if pc.get("image_url") or pl.get("image_url"):
            ic["has"] += 1
        elif pl.get("image_skipped"):
            ic["skipped"] += 1
        elif pl.get("image_error"):
            ic["failed"] += 1
            reasons[str(pl["image_error"])[:60]] += 1
        elif not pc:
            ic["never produced"] += 1
        else:
            ic["no reason recorded"] += 1
    for k, n in ic.most_common():
        print(f"  {k:<22} {n}")
    for r, n in reasons.most_common(5):
        print(f"      x{n}  {r}")

    # ------------------------------------------------------------ LINKEDIN
    rule("5. LINKEDIN — text, credentials, image attachment")
    with_post = sum(1 for j in pieces
                    if ((j.get("payload") or {}).get("content_producer")
                        or {}).get("linkedin_post"))
    print(f"  pieces carrying a written LinkedIn post : {with_post}"
          f" of {len(pieces)}")
    tok, urn = C._env("LINKEDIN_POST_TOKEN"), C._env("LINKEDIN_AUTHOR_URN")
    print(f"  LINKEDIN_POST_TOKEN                     : "
          f"{'set' if tok else 'NOT SET'}")
    print(f"  LINKEDIN_AUTHOR_URN                     : "
          f"{'set' if urn else 'NOT SET'}")
    if C._env("LINKEDIN_API_KEY"):
        print("  LINKEDIN_API_KEY is set — note this feeds PROSPEO lead")
        print("  sourcing, NOT posting. It is not the posting token.")
    print(f"  poster would attach an image when one exists : yes "
          f"(publish_social calls post_image)")
    if not (tok and urn):
        print("  => NOT LIVE. Nothing will post.")

    # -------------------------------------------------------------- PUBLISH
    rule("6. PUBLISH — what actually reached the site")
    pub = [j for j in pieces if (j.get("payload") or {}).get("published_ref")]
    print(f"  pieces with a published_ref : {len(pub)} of {len(pieces)}")
    chans = Counter()
    for j in pub:
        for ch in ((j.get("payload") or {}).get("published_refs") or {}):
            chans[ch] += 1
    for ch, n in chans.most_common():
        print(f"      {ch:<16} {n}")
    with_img = sum(1 for j in pub
                   if ((j.get("payload") or {}).get("content_producer")
                       or {}).get("image_url"))
    print(f"  of those, carrying an image : {with_img}")

    # WAITING IS NOT STUCK. measuring:0 in section 1 looks like a wall and is
    # usually a clock: a published job sits on a time gate until its
    # measurement window opens, and tick() re-claims it each cycle and reports
    # idle. I read section 1, found no advance, and called it a structural gap
    # for two rounds. It was a countdown.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    print()
    print("  measurement windows:")
    if not pub:
        print("    (nothing published yet)")
    for j in pub:
        ma = str(j.get("measure_at") or "")
        if not ma:
            print(f"    {str(j.get('job_id'))[:22]:<24} NO measure_at stamped "
                  f"— this one really is stuck")
            continue
        try:
            due = datetime.fromisoformat(ma.replace("Z", "+00:00"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            days = (due - now).days
            state = (f"opens in {days}d" if days > 0 else "OPEN — due to measure")
        except Exception:
            state = f"unparseable measure_at: {ma[:24]}"
        print(f"    {str(j.get('job_id'))[:22]:<24} {state}")

    # ---------------------------------------------------------------- WIRES
    rule("7. WIRES — credentials, by the wire they power")
    try:
        import credentials as CR
        for key, w in CR.WIRES.items():
            have = [n for n in w["needs"] if C._env(n)]
            state = "LIVE" if len(have) == len(w["needs"]) else \
                f"{len(have)}/{len(w['needs'])}"
            miss = [n for n in w["needs"] if not C._env(n)]
            print(f"  [{state:^6}] {w['label']:<26}"
                  + (f"missing: {', '.join(miss)}" if miss else ""))
    except Exception as e:
        print(f"  (credentials map unavailable: {e})")
    bad = C.credential_audit()
    if bad:
        print()
        print(f"  {len(bad)} stored value(s) look wrong (SET but unusable):")
        for r in bad:
            print(f"      {r['key']:<24} {r['problem'][:44]}")

    # ------------------------------------------------------------- FAILURES
    rule("8. FAILURES — every distinct reason, with counts")
    # WITH DATES. A count alone cannot tell damage already done from damage
    # still happening, and every fix in this codebase has been judged on a
    # number that included jobs from before the fix existed.
    fr, newest, oldest = Counter(), {}, {}
    for j in pieces:
        if str(j.get("status")) not in ("failed", "revision_needed"):
            continue
        why = str(j.get("halt_reason") or j.get("qa_verdict")
                  or ((j.get("payload") or {}).get("error"))
                  or "(no reason recorded)")
        when = str(j.get("created_at") or "")[:10]
        fr[why] += 1
        if when:
            newest[why] = max(newest.get(why, ""), when)
            oldest[why] = min(oldest.get(why, "9999"), when)
    if not fr:
        print("  No failed pieces.")
    for why, n in fr.most_common(12):
        span = (f"{oldest.get(why, '?')} .. {newest.get(why, '?')}"
                if oldest.get(why) != newest.get(why)
                else newest.get(why, "?"))
        print(f"  x{n:<4} [{span:<24}]")
        # WRAPPED, NOT CLIPPED. This printed the first 64 characters, which cut
        # off "Last problem: ..." — the part added specifically to say WHY a
        # skill failed. A report that truncates the reason is the same failure
        # as not recording it.
        import textwrap
        for line in textwrap.wrap(why, W - 12):
            print(f"            {line}")
    print()
    print("  The date span is the point. A reason whose NEWEST job predates a")
    print("  fix is history; one still appearing today is a live bug.")

    rule()
    print("Read-only. Nothing was published, sent, or spent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
