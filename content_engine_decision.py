"""EVERYTHING YOU NEED BEFORE YOU APPROVE SOMETHING.

The approval row showed a title, a date and a destination. Meanwhile the job
it described was already carrying the strategist's written reason for the
piece, the QA verdict with per-issue severity AND a suggested fix for each,
the SEO checks, and the exact money already spent on it. None of that reached
the screen where the decision gets made.

This is not new data collection. Every field here was already on the job:

    job["payload"]["content_strategist"]["calendar"][i]  rationale, goal,
                                                          segment, priority,
                                                          primary_keyword
    job["payload"]["content_producer"]                    title, body, meta,
                                                          cta, hashtags,
                                                          image_prompts
    job["payload"]["qa_compliance"]                       verdict, issues[]
                                                            {issue, location,
                                                             severity, fix}
    job["payload"]["seo_optimizer"]                       seo_ready, fixes[]
    job["cost_so_far_usd"]                                real money

THREE STATES, DESIGNED TOGETHER
Every field renders in one of three ways, and all three are built at once:

    present   the value, plus what it means for the decision
    not run   "this has not been checked", plus the button to check it
    failed    the real halt_reason, verbatim, plus retry

That is deliberate. If the layout only worked when the data was there, then
how complete your jobs happen to be would decide whether the screen works.
A missing measurement is a state, not a gap.

NOTHING HERE DECIDES ANYTHING. It reports, and it offers the same actions the
row already had. Every publish, send and spend still waits for you.
"""

from __future__ import annotations

import re

GOOD = "#3FD98B"
WARN = "#F5B14C"
BAD = "#FF6B93"
DIM = "#8E9BBE"

# Google truncates beyond these. Not our rule - theirs.
META_TITLE_MAX = 60
META_DESC_MAX = 155

# A channel you cannot take back once it is out.
IRREVERSIBLE = {"linkedin", "twitter", "facebook", "instagram", "youtube"}


def _d(v):
    return v if isinstance(v, dict) else {}


def _l(v):
    return list(v) if isinstance(v, (list, tuple)) else []


def _s(v):
    return str(v or "").strip()


def _result(job, skill):
    return _d(_d(job.get("payload")).get(skill))


def _state_of(job, skill):
    """present | not_run | failed - and WHY, in the engine's own words."""
    if _result(job, skill):
        return "present", ""
    halt = _s(job.get("halt_reason"))
    if halt and skill.split("_")[0] in halt.lower():
        return "failed", halt
    if _s(job.get("status")) in ("failed", "revision_needed") and halt:
        return "failed", halt
    return "not_run", ""


# ------------------------------------------------------------------ numbers

def numbers(job) -> list:
    """Countable facts about this piece. Each one is a real count of real
    text - nothing here is estimated, and nothing is rounded away."""
    prod = _result(job, "content_producer")
    body = _s(prod.get("body"))
    out = []
    if body:
        words = len(re.findall(r"\b[\w'-]+\b", body))
        out.append(("Words", f"{words:,}",
                    "Roughly %d minute%s to read." % (max(1, round(words / 225)),
                                                      "" if round(words / 225) == 1 else "s")))
        secs = len(re.findall(r"^##\s+", body, re.M))
        out.append(("Sections", str(secs),
                    "H2 headings. A long piece with few headings is hard to scan."))
        inline = len(re.findall(r"!\[", body))
        prompts = len(_l(prod.get("image_prompts")))
        out.append(("Images", str(inline or prompts),
                    "In the body." if inline else
                    "Prompts written; images not placed in the body yet."))
    cost = job.get("cost_so_far_usd")
    if cost is not None:
        out.append(("Spent so far", f"€{float(cost or 0):.2f}",
                    "Already gone, whether you approve this or not."))
    mt, md = _s(prod.get("meta_title")), _s(prod.get("meta_description"))
    if mt:
        over = len(mt) - META_TITLE_MAX
        out.append(("Meta title", f"{len(mt)} chars",
                    f"{over} over - Google will cut it." if over > 0
                    else "Inside Google's limit."))
    if md:
        over = len(md) - META_DESC_MAX
        out.append(("Meta description", f"{len(md)} chars",
                    f"{over} over - Google will rewrite it." if over > 0
                    else "Inside Google's limit."))
    tags = _l(prod.get("hashtags"))
    if tags:
        out.append(("Hashtags", str(len(tags)), ", ".join(str(t) for t in tags[:6])))
    return out


# ------------------------------------------------------------------ why

def why_it_exists(job) -> dict:
    """The strategist's own written reason. It has been on the job all along."""
    state, halt = _state_of(job, "content_strategist")
    if state != "present":
        return {"state": state, "halt": halt}
    strat = _result(job, "content_strategist")
    cal = _l(strat.get("calendar"))
    idx = _d(_d(job.get("payload")).get("config")).get("produce_index", 0)
    row = _d(cal[idx]) if 0 <= idx < len(cal) else (_d(cal[0]) if cal else {})
    return {"state": "present",
            "rationale": _s(row.get("rationale")),
            "goal": _s(row.get("business_goal")),
            "segment": _s(row.get("target_segment")),
            "priority": _s(row.get("priority")),
            "keyword": _s(row.get("primary_keyword"))}


# ------------------------------------------------------------------ risk

def risk(job) -> dict:
    """QA's verdict, with every issue's severity, location and SUGGESTED FIX.
    The fix text was already being written and never shown."""
    state, halt = _state_of(job, "qa_compliance")
    if state != "present":
        return {"state": state, "halt": halt}
    qa = _result(job, "qa_compliance")
    issues = []
    for it in _l(qa.get("issues")):
        it = _d(it)
        issues.append({"issue": _s(it.get("issue")),
                       "where": _s(it.get("location")),
                       "sev": _s(it.get("severity")).lower() or "medium",
                       "fix": _s(it.get("fix"))})
    counts = {}
    for i in issues:
        counts[i["sev"]] = counts.get(i["sev"], 0) + 1
    return {"state": "present", "verdict": _s(qa.get("verdict")),
            "voice": qa.get("brand_voice_match"), "issues": issues,
            "counts": counts}


def seo(job) -> dict:
    state, halt = _state_of(job, "seo_optimizer")
    if state != "present":
        return {"state": state, "halt": halt}
    s = _result(job, "seo_optimizer")
    checks = _d(s.get("checks"))
    passed = sum(1 for v in checks.values() if v)
    return {"state": "present", "ready": bool(s.get("seo_ready")),
            "passed": passed, "total": len(checks),
            "fixes": [_s(f) for f in _l(s.get("fixes"))]}


# ------------------------------------------------------------------ if I click

def consequences(job) -> list:
    """What pressing Approve actually does, per channel, and whether it can be
    undone. 'Reversible' is not a general property - it is per destination."""
    try:
        import content_engine_site_taxonomy as T
        chans = T.channels_of(_d(_d(job.get("payload")).get("config")))
    except Exception:
        chans = ["website"]
    out = []
    for c in (chans or ["website"]):
        c = _s(c).lower()
        if c in IRREVERSIBLE:
            out.append((c, False,
                        "Once posted it is public immediately. Deleting it "
                        "later does not un-send notifications or remove it "
                        "from anyone's feed history."))
        else:
            out.append((c, True,
                        "Publishes to your site. You can unpublish it again "
                        "from here, and the URL simply stops resolving."))
    return out


# ------------------------------------------------------------------ render

def _esc(v):
    import html
    return html.escape(str(v if v is not None else ""), quote=True)


def _sec(title, inner):
    return f"<div class='dsec'><h4>{_esc(title)}</h4>{inner}</div>"


def _absent(state, halt, what, fix_label, fix_call):
    """The two states that are NOT 'we have the answer'. Both offer the
    action that would produce one, so a gap is a next step, not a dead end."""
    if state == "failed":
        return (f"<p class='dwarn dbad'><b>{_esc(what)} failed.</b><br>"
                f"{_esc(halt) or 'No reason was recorded.'}</p>"
                f"<button class='cbtn' onclick=\"{fix_call}\">{_esc(fix_label)}"
                f"</button>")
    return (f"<p class='dwarn'><b>{_esc(what)} has not run.</b> "
            f"Nothing has checked this yet - that is not the same as it being "
            f"clean.</p>"
            f"<button class='cbtn' onclick=\"{fix_call}\">{_esc(fix_label)}"
            f"</button>")


def decision_pane(pid, job, row=None) -> str:
    """TIER 2 - the whole record behind one approve/publish decision."""
    row = _d(row)
    job = _d(job)
    jid = _s(job.get("job_id")) or _s(row.get("job_id"))
    prod = _result(job, "content_producer")
    title = _s(prod.get("title")) or _s(row.get("title")) or "(untitled)"
    parts = [f"<div class='dpane' id='{_esc(pid)}' "
             f"data-title=\"{_esc(title)}\">"]

    # 1 WHAT
    parts.append(_sec("What you are deciding",
                      f"<p class='q' style='font-size:19px'>{_esc(title)}</p>"
                      f"<p>{_esc(_s(row.get('destination')) or 'Destination not set')}"
                      + (f" &middot; {_esc(_s(row.get('state')))}"
                         if row.get("state") else "") + "</p>"))

    # 2 WHY IT EXISTS
    w = why_it_exists(job)
    if w.get("state") == "present" and (w.get("rationale") or w.get("goal")):
        inner = f"<p>{_esc(w['rationale'])}</p>" if w.get("rationale") else ""
        chips = [(k, v) for k, v in (("Goal", w.get("goal")),
                                     ("Audience", w.get("segment")),
                                     ("Priority", w.get("priority")),
                                     ("Keyword", w.get("keyword"))) if v]
        if chips:
            inner += ("<div class='dnum'>" + "".join(
                f"<span>{_esc(k)} <b>{_esc(v)}</b></span>" for k, v in chips)
                + "</div>")
        parts.append(_sec("Why the engine made this", inner))
    else:
        parts.append(_sec("Why the engine made this", _absent(
            w.get("state", "not_run"), w.get("halt", ""), "The strategy step",
            "Plan this properly", "toast('Open Plan my week to run the "
            "strategist for this piece.',true)")))

    # 3 THE NUMBERS
    nums = numbers(job)
    if nums:
        parts.append(_sec("The numbers", "<div class='dnum'>" + "".join(
            f"<span>{_esc(l)} <b>{_esc(v)}</b></span>" for l, v, _n in nums)
            + "</div>" + "".join(
            f"<p style='font-size:12px;color:{DIM}'>{_esc(l)} &mdash; "
            f"{_esc(n)}</p>" for l, _v, n in nums if n)))
    else:
        parts.append(_sec("The numbers",
                          "<p class='dwarn'><b>Nothing written yet.</b> There "
                          "is no text to count, so every figure here would be "
                          "zero for the wrong reason.</p>"))

    # 4 THE RISK
    r = risk(job)
    if r.get("state") == "present":
        counts = r.get("counts") or {}
        head = ", ".join(f"{n} {s}" for s, n in
                         sorted(counts.items(), key=lambda kv: -kv[1])) or "none"
        tone = ("dbad" if counts.get("high") else
                "" if counts.get("medium") or counts.get("low") else "dgood")
        inner = (f"<p class='dwarn {tone}'><b>Verdict: "
                 f"{_esc(r.get('verdict') or 'unknown')}</b> &middot; "
                 f"{_esc(head)} issue(s)"
                 + ("" if r.get("voice") is None else
                    (" &middot; brand voice matches" if r.get("voice")
                     else " &middot; <b>brand voice does not match</b>"))
                 + "</p>")
        for i in r.get("issues") or []:
            inner += (f"<p class='dwarn"
                      f"{' dbad' if i['sev'] == 'high' else ''}'>"
                      f"<b>{_esc(i['sev'].upper())}</b> &mdash; "
                      f"{_esc(i['issue'])}"
                      + (f"<br><span style='color:{DIM}'>Where: "
                         f"{_esc(i['where'])}</span>" if i["where"] else "")
                      + (f"<br><b>Suggested fix:</b> {_esc(i['fix'])}"
                         if i["fix"] else "") + "</p>")
        if not (r.get("issues") or []):
            inner += "<p>QA found nothing to flag on this piece.</p>"
        parts.append(_sec("What is wrong with it", inner))
    else:
        parts.append(_sec("What is wrong with it", _absent(
            r.get("state", "not_run"), r.get("halt", ""), "The QA check",
            "Run QA now",
            f"act('/fix/retry_job?arg={_esc(jid)}')" if jid
            else "toast('No job id on this row.',false)")))

    # 5 SEO
    s = seo(job)
    if s.get("state") == "present":
        inner = (f"<p class='dwarn {'dgood' if s['ready'] else ''}'>"
                 f"<b>{'Ready to publish' if s['ready'] else 'Not SEO-ready'}"
                 f"</b>"
                 + (f" &middot; {s['passed']} of {s['total']} checks pass"
                    if s.get("total") else "") + "</p>")
        for f in s.get("fixes") or []:
            inner += f"<p>&middot; {_esc(f)}</p>"
        parts.append(_sec("Search readiness", inner))
    else:
        parts.append(_sec("Search readiness", _absent(
            s.get("state", "not_run"), s.get("halt", ""), "The SEO check",
            "Run the SEO fixes", "act('/fix/run_seo_fixes')")))

    # 6 PREVIEW - exactly as it will publish
    frame = _s(row.get("preview_html"))
    if frame:
        parts.append(_sec("How it will look where it publishes",
                          f"<div style='max-height:520px;overflow:auto;"
                          f"border-radius:10px;background:#0B1120;padding:8px'>"
                          f"{frame}</div>"))
    else:
        parts.append(_sec("How it will look where it publishes",
                          f"<p class='dwarn'>{_esc(_s(row.get('why')) or 'Nothing has been written yet, so there is nothing to preview.')}</p>"))

    # 7 IF I CLICK
    inner = ""
    for chan, rev, note in consequences(job):
        inner += (f"<p class='dwarn {'dgood' if rev else 'dbad'}'>"
                  f"<b>{_esc(chan)}</b> &mdash; "
                  f"{'reversible' if rev else 'NOT reversible'}<br>"
                  f"{_esc(note)}</p>")
    cost = float(job.get("cost_so_far_usd") or 0)
    inner += (f"<p>Approving costs nothing further. €{cost:.2f} has already "
              f"been spent producing it, and that is not refunded by "
              f"declining.</p>")
    parts.append(_sec("If you press Approve", inner))

    # 8 MICRO-COMMAND - a real box, not a prompt()
    if jid:
        ta = f"mc-{_esc(pid)}"
        parts.append(_sec(
            "Send it back with an instruction",
            f"<p style='font-size:12px;color:{DIM}'>Write what should change. "
            f"It reaches the writer as your instruction on the next attempt, "
            f"and it is recorded against this piece.</p>"
            f"<textarea class='dmc' id='{ta}' placeholder=\"e.g. Cut the "
            f"intro to two sentences and lead with the 40% figure. Drop the "
            f"third section entirely.\"></textarea>"
            f"<div style='margin-top:8px;display:flex;gap:8px;flex-wrap:wrap'>"
            f"<button class='cta' onclick=\"microCmd('{_esc(jid)}','{ta}')\">"
            f"Send back to the writer</button>"
            f"<button class='cbtn' onclick=\"if(confirm('Remove this piece "
            f"from the queue? It will not publish.'))"
            f"act('/fix/delete_piece?arg={_esc(jid)}')\">Remove it "
            f"entirely</button></div>"))

    parts.append("</div>")
    return "".join(parts)
