# -*- coding: utf-8 -*-
"""AGENT OS: turn 9 (Marketing / Content) and turn 8 (SEO / AEO / GEO).

Sixteen more screens, composed from content_engine_os_kit. Ids and titles
are the wireframe's own, read out of the handoff file.

  9a Command Center            8a Manager's Command Center
  9b Strategist's desk         8b Engineer's desk
  9c Weekly Approval Room      8c Analyst's desk
  9d Creative Director's desk  8d Content Specialist's desk
  9e Producer's desk           8e Keyword Strategist's desk
  9f Distributor's desk        8f Link Builder's desk
  9g Content Calendar          8g Data Sources
  9h Tools and Control Room    8h Control Room

THE CASE THIS TURN EXISTS TO MAKE HONESTLY
------------------------------------------
8c and 8e are two desks with one worker: the Analyst and the Keyword
Strategist are both seo.analyst. The wireframe draws them separately and
that is right, because they answer different questions. What would be
wrong is letting the reader believe two people are employed. Each of the
two screens names the same worker and says so on its face.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_os_kit as K

_e, _l, _d = K._e, K._l, K._d

#: job status -> the plain-English pipeline stage the founder reads
PIPELINE = [
    ("created", "planned"),
    ("researched", "researched"),
    ("drafted", "written"),
    ("optimized", "optimised"),
    ("AWAITING_APPROVAL", "waiting on you"),
    ("approved", "approved"),
    ("published", "published"),
]

#: things the wireframe draws for this department that have no wire at all
PLANNED_CHANNELS = [
    ("Metricool scheduling", "a Metricool API key"),
    ("Newsletter", "an ESP credential (Klaviyo or SMTP list)"),
    ("Trade fair and community", "nothing to connect; this is human work"),
]


def _cards(ctx, *ids) -> List[dict]:
    want = set(ids)
    return [c for c in _l(_d(ctx).get("cards")) if _d(c).get("id") in want]


def _card(ctx, aid) -> Dict[str, Any]:
    for c in _l(_d(ctx).get("cards")):
        if _d(c).get("id") == aid:
            return _d(c)
    return {}


def _jobs(ctx) -> List[dict]:
    return [_d(j) for j in _l(_d(ctx).get("jobs"))]


def _pipeline_strip(ctx) -> str:
    js = _jobs(ctx)
    cells = []
    for status, label in PIPELINE:
        n = sum(1 for j in js if str(j.get("status")) == status)
        cells.append(K.bp(K.stat(n, label, "/jobs")))
    return K.grid(*cells)


def _waiting(ctx) -> List[dict]:
    return [j for j in _jobs(ctx)
            if str(j.get("status")) == "AWAITING_APPROVAL"
            and j.get("approved") is not True]


def _desk(ctx, sid, title, sub, agent_id, *, extra: str = "",
          quick=None, note: str = "") -> str:
    """One employee's desk: its card, whatever the screen adds, and the
    command panel scoped to that employee."""
    card = _card(ctx, agent_id)
    if not card:
        body = ("<p class='ox-nodata'>%s is not on the roster, so this desk "
                "has no worker and shows nothing</p>" % _e(agent_id))
        return K.screen(sid, title, sub, body, staffed_by="nobody",
                        badge_kind="notstaffed")
    panel = K.cmdchat(agent_id, _e(card.get("name")), quick=quick or [],
                      context_note=note)
    return K.screen(sid, title, sub,
                    K.grid(K.agent_card(card), extra or K.bp(
                        "<span class='ox-lbl'>Its lane</span>"
                        "<p class='ox-sub'>%s</p>" % _e(card.get("why"))),
                        cols="two") + panel,
                    staffed_by=_e(card.get("name")),
                    badge_kind=_e(card.get("badge")))


# ==========================================================================
# TURN 9 - MARKETING / CONTENT
# ==========================================================================
STAFF_9 = ("mkt.strategist", "mkt.producer", "mkt.creative_director",
           "mkt.distributor")


def _s9a(ctx) -> str:
    waiting = _waiting(ctx)
    cards = _cards(ctx, *STAFF_9)
    return K.screen(
        "9a", "Command Center",
        "The pipeline, the four staff, and what is waiting on you.",
        _pipeline_strip(ctx)
        + K.bp("<span class='ox-lbl'>Waiting on you</span>"
               + ("<ul class='ox-rep'>%s</ul>"
                  % "".join("<li class='ask'>🙋 %s</li>" % _e(j.get("job_id"))
                            for j in waiting[:8])
                  if waiting else
                  "<p class='ox-nodata'>nothing is waiting on you</p>")
               + K.source_chip("/jobs"))
        + K.grid(*[K.agent_card(c, compact=True) for c in cards]),
        staffed_by="four employees", badge_kind="live")


def _s9b(ctx) -> str:
    return _desk(
        ctx, "9b", "Strategist's desk",
        "Segmentation, competitor reading, concept building, the weekly plan.",
        "mkt.strategist",
        extra=K.bp("<span class='ox-lbl'>What it plans from</span>"
                   "<ul class='ox-rep'>"
                   "<li>the business type the CMS layer detected</li>"
                   "<li>Search Console demand, where the wire is verified</li>"
                   "<li>its own playbook: topics that earned position</li>"
                   "</ul><p class='ox-sub'>Competitor ad reading is drawn in "
                   "the wireframe and has no wire. It is not shown as a "
                   "number here.</p>"),
        quick=["Plan next week", "Which topics are working?",
               "Skip listicles this month"],
        note="Planning is free and automatic. This desk cannot spend or "
             "publish, so a command here changes what gets written next.")


def _s9c(ctx) -> str:
    waiting = _waiting(ctx)
    rows = "".join(
        "<tr id='osjob-%s'><td class='ox-wire'>%s</td><td>%s</td>"
        "<td><button type='button' class='ox-btn ox-btn-p' "
        "onclick=\"osApproveJob('%s')\">Approve</button>"
        "<button type='button' class='ox-btn' "
        "onclick=\"osDeclineJob('%s')\">Send back</button></td></tr>"
        % (_e(j.get("job_id")), _e(j.get("job_id")),
           _e(j.get("status")), _e(j.get("job_id")),
           _e(j.get("job_id"))) for j in waiting)
    table = ("<div class='ox-tw'><table class='ox-t'><thead><tr><th>Piece</th>"
             "<th>Stage</th><th>Decision</th></tr></thead><tbody>%s</tbody>"
             "</table></div>" % rows) if rows else \
        "<p class='ox-nodata'>nothing is waiting for approval</p>"
    return K.screen(
        "9c", "Weekly Approval Room",
        "Your meeting, digitised. This is the pipeline's one gate.",
        K.bp("<span class='ox-lbl'>Pieces waiting (%d)</span>%s%s"
             % (len(waiting), table, K.source_chip("/jobs/{id}/approve")))
        + K.bp("<span class='ox-lbl'>Why nothing skips this room</span>"
               "<p class='ox-sub'>Publishing is one of the five permanent "
               "gates. QA can hold a piece back and can never pass one "
               "through on your behalf, so everything written arrives "
               "here.</p>"),
        staffed_by="you", badge_kind="")


def _s9d(ctx) -> str:
    return _desk(
        ctx, "9d", "Creative Director's desk",
        "Receives the brief, decides how it gets made, and checks it before "
        "you ever see it.",
        "mkt.creative_director",
        quick=["Hold anything off-brand", "What failed QA this week?"],
        note="This desk can HOLD a piece. It can never approve one for you.")


def _s9e(ctx) -> str:
    card = _card(ctx, "mkt.producer")
    drive = [h for h in _l(_d(ctx).get("health"))
             if _d(h).get("wire") == "google_drive"]
    drive_note = ""
    if drive and _d(drive[0]).get("status") == "rejected":
        drive_note = K.bp(
            "<span class='ox-lbl'>Saved to Drive</span>"
            "<p class='ox-sub'>Drive is refusing: %s. Work is produced and "
            "stored in the engine; the Drive copy the wireframe draws is "
            "not happening until this is fixed.</p>"
            % _e(_d(drive[0]).get("reason")), cls="ox-plan")
    return _desk(
        ctx, "9e", "Producer's desk",
        "AI tool or human, saved to Drive.",
        "mkt.producer",
        extra=drive_note or K.bp(
            "<span class='ox-lbl'>Its lane</span>"
            "<p class='ox-sub'>%s</p>" % _e(card.get("why"))),
        quick=["Write the next piece", "Redo this one shorter"],
        note="Every piece is a draft. Nothing this desk makes reaches the "
             "site without passing QA and then you.")


def _s9f(ctx) -> str:
    planned = K.grid(*[K.planned(w, n) for w, n in PLANNED_CHANNELS])
    return _desk(
        ctx, "9f", "Distributor's desk",
        "Scheduling, newsletter, trade fair, bookings and community.",
        "mkt.distributor",
        extra=K.bp("<span class='ox-lbl'>Channels drawn but not wired</span>"
                   "<p class='ox-sub'>WordPress publishing is live. The rest "
                   "of this desk's channels have no credential, so they are "
                   "laid out and empty rather than filled with samples.</p>")
        + planned,
        quick=["Publish the approved queue", "Which channel refused?"],
        note="Publishing is a permanent gate. This desk ships what you "
             "approved and nothing else.")


def _s9g(ctx) -> str:
    js = _jobs(ctx)
    by_day: Dict[str, List[dict]] = {}
    for j in js:
        day = str(j.get("updated_at") or j.get("created_at") or "")[:10]
        if day:
            by_day.setdefault(day, []).append(j)
    rows = "".join(
        "<tr><td class='ox-wire'>%s</td><td>%d</td><td>%s</td></tr>"
        % (_e(day), len(items),
           ", ".join(sorted({_e(i.get("status")) for i in items})))
        for day, items in sorted(by_day.items(), reverse=True)[:21])
    return K.screen(
        "9g", "Content Calendar",
        "The whole pipeline as one shared timeline.",
        (("<div class='ox-tw'><table class='ox-t'><thead><tr><th>Day</th>"
          "<th>Pieces</th><th>Stages</th></tr></thead><tbody>%s</tbody>"
          "</table></div>" % rows) if rows else
         "<p class='ox-nodata'>no pieces have moved yet, so the calendar is "
         "empty rather than showing a grid of zeros</p>")
        + K.bp("<span class='ox-lbl'>Note</span>"
               "<p class='ox-sub'>A day with no work is absent from this "
               "list, not drawn as zero. A gap and a zero are different "
               "facts and this project has confused them before.</p>"
               + K.source_chip("/jobs")),
        staffed_by="four employees", badge_kind="live")


def _s9h(ctx) -> str:
    cards = _cards(ctx, *STAFF_9)
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_e(_d(c).get("name")), K.badge(_e(_d(c).get("badge"))),
           "".join("<span class='ox-slot ox-s-%s'><b>%s</b>%s</span>"
                   % (_e(_d(s).get("status")),
                      K.STATUS_LABEL.get(str(_d(s).get("status")),
                                         K.STATUS_LABEL["empty"])[0],
                      _e(_d(s).get("tool")))
                   for s in _l(_d(c).get("slots"))) or "none",
           _e(_d(c).get("autonomy") or "Propose, I approve"))
        for c in cards)
    return K.screen(
        "9h", "Tools and Control Room",
        "Assign a provider per slot, and manage the four employees.",
        "<div class='ox-tw'><table class='ox-t'><thead><tr><th>Employee</th>"
        "<th>Staffing</th><th>Tool slots</th><th>Autonomy</th></tr></thead>"
        "<tbody>%s</tbody></table></div>" % rows
        + K.bp("<span class='ox-lbl'>Autonomy cannot open a gate</span>"
               "<p class='ox-sub'>Raising autonomy widens what runs without "
               "asking inside the low-stakes band. Publish, send and spend "
               "stay gated at every setting, including the highest.</p>"),
        staffed_by="you", badge_kind="")


# ==========================================================================
# TURN 8 - SEO / AEO / GEO
# ==========================================================================
STAFF_8 = ("seo.technical", "seo.analyst", "seo.content_specialist",
           "seo.link_builder")
SEO_WIRES = ("seo_crawler", "seo_pagespeed", "seo_index_inspect",
             "seo_indexnow", "seo_rank_tracker", "seo_backlinks",
             "google_gsc_ga4", "serper_search")


def _s8a(ctx) -> str:
    cards = _cards(ctx, *STAFF_8)
    live = sum(1 for c in cards if _d(c).get("badge") == "live")
    wires = [h for h in _l(_d(ctx).get("health"))
             if _d(h).get("wire") in SEO_WIRES]
    ok = sum(1 for h in wires if _d(h).get("status") == "verified")
    return K.screen(
        "8a", "Manager's Command Center",
        "The whole search department at a glance.",
        K.grid(K.bp(K.stat(len(cards), "employees", "/agents")),
               K.bp(K.stat(live, "live lanes", "/agents")),
               K.bp(K.stat(ok, "search wires verified", "/connectors/health")),
               K.bp(K.stat(len(wires) - ok, "not proven",
                           "/connectors/health")))
        + K.grid(*[K.agent_card(c, compact=True) for c in cards]),
        staffed_by="four employees", badge_kind="live")


def _s8b(ctx) -> str:
    return _desk(
        ctx, "8b", "Engineer's desk",
        "A full technical audit, where every row ends in a fix rather than a "
        "score.",
        "seo.technical",
        extra=K.bp("<span class='ox-lbl'>What runs, and what it costs</span>"
                   "<ul class='ox-rep'>"
                   "<li>crawl, weekly, free</li>"
                   "<li>index inspection and IndexNow, daily, free</li>"
                   "<li>PageSpeed, weekly, free</li></ul>"
                   "<p class='ox-sub'>Free engines run automatically. A paid "
                   "engine respects the cap and becomes a proposal above the "
                   "threshold.</p>"),
        quick=["Run the crawl now", "What is not indexed?"],
        note="Fixes are proposed. Nothing edits the live site without you.")


def _s8c(ctx) -> str:
    return _desk(
        ctx, "8c", "Analyst's desk",
        "Rank tracking and AI-citation tracking, which is the AEO and GEO "
        "edge.",
        "seo.analyst",
        extra=K.bp("<span class='ox-lbl'>One worker, two desks</span>"
                   "<p class='ox-sub'>This is the same employee as the "
                   "Keyword Strategist on 8e. Two desks, because they answer "
                   "different questions; one worker, because one lane owner "
                   "keeps one playbook. Splitting it would give you two "
                   "half-taught memories.</p>"),
        quick=["What moved this week?", "Where are we cited by AI?"],
        note="Read only. This desk reports and changes nothing.")


def _s8d(ctx) -> str:
    return _desk(
        ctx, "8d", "Content Specialist's desk",
        "On-page fixes and answer blocks, in one queue.",
        "seo.content_specialist",
        quick=["Optimise the drafts waiting", "Add answer blocks to services"],
        note="It edits drafts before QA sees them. It never publishes.")


def _s8e(ctx) -> str:
    return _desk(
        ctx, "8e", "Keyword Strategist's desk",
        "Opportunities, and the hand-off to Content in one step.",
        "seo.analyst",
        extra=K.bp("<span class='ox-lbl'>Same worker as 8c</span>"
                   "<p class='ox-sub'>The Analyst and the Keyword Strategist "
                   "are one employee. The wireframe draws two desks and that "
                   "is right; showing two headcounts would not be.</p>"),
        quick=["Find gaps worth writing", "Hand the top three to Content"],
        note="A hand-off creates a planned piece. It does not write one, and "
             "it does not spend.")


def _s8f(ctx) -> str:
    card = _card(ctx, "seo.link_builder")
    blocked = K.bp(
        "<span class='ox-lbl'>Why this desk is an inspector</span>"
        "<p class='ox-sub'>%s</p>"
        "<p class='ox-need'>Needs: <b>a backlink data credential</b></p>"
        % _e(card.get("why") or "no credential for the backlink wire"),
        cls="ox-plan")
    return _desk(
        ctx, "8f", "Link Builder's desk",
        "Off-page work, where every outreach send is gated by you.",
        "seo.link_builder", extra=blocked,
        quick=["List prospects worth contacting"],
        note="Link outreach is email, so it passes the permanent SEND gate "
             "like every other message.")


def _s8g(ctx) -> str:
    wires = [_d(h) for h in _l(_d(ctx).get("health"))
             if _d(h).get("wire") in SEO_WIRES]
    return K.screen(
        "8g", "Data Sources",
        "A provider per slot, so the department is not tied to one vendor.",
        K.connector_table(wires)
        + K.bp("<span class='ox-lbl'>Provider-agnostic on purpose</span>"
               "<p class='ox-sub'>Rank and search data can come from more "
               "than one vendor. The slot is the thing an employee owns; the "
               "provider behind it is swappable, and swapping one does not "
               "change what any desk is allowed to do.</p>"),
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


def _s8h(ctx) -> str:
    cards = _cards(ctx, *STAFF_8)
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_e(_d(c).get("name")), K.badge(_e(_d(c).get("badge"))),
           _e(_d(c).get("autonomy") or "Propose, I approve"),
           _e(_d(c).get("cap_key") or ""))
        for c in cards)
    logs = []
    for c in cards:
        rep = _d(_d(c).get("report"))
        for f in _l(rep.get("finished"))[:2]:
            logs.append("<li class='ok'>%s: %s</li>"
                        % (_e(_d(c).get("name")), _e(_d(f).get("what"))))
        for f in _l(rep.get("couldnt"))[:2]:
            logs.append("<li class='bad'>%s: %s</li>"
                        % (_e(_d(c).get("name")), _e(_d(f).get("cause"))))
    return K.screen(
        "8h", "Control Room",
        "Per-employee autonomy, data access, and the activity log.",
        "<div class='ox-tw'><table class='ox-t'><thead><tr><th>Employee</th>"
        "<th>Staffing</th><th>Autonomy</th><th>Cap</th></tr></thead><tbody>%s"
        "</tbody></table></div>" % rows
        + K.bp("<span class='ox-lbl'>Today's activity</span>"
               + ("<ul class='ox-rep'>%s</ul>" % "".join(logs[:12]) if logs
                  else "<p class='ox-nodata'>nothing recorded today</p>")
               + K.source_chip("/agents/{id}/report")),
        staffed_by="you", badge_kind="")


# ==========================================================================
# ASSEMBLY
# ==========================================================================
SCREENS_9 = ("9a", "9b", "9c", "9d", "9e", "9f", "9g", "9h")
SCREENS_8 = ("8a", "8b", "8c", "8d", "8e", "8f", "8g", "8h")


def marketing_section(ctx: Dict[str, Any]) -> str:
    ctx = _d(ctx)
    return ("<div class='osx'>" + _s9a(ctx) + _s9b(ctx) + _s9c(ctx)
            + _s9d(ctx) + _s9e(ctx) + _s9f(ctx) + _s9g(ctx) + _s9h(ctx)
            + "</div>")


def search_section(ctx: Dict[str, Any]) -> str:
    ctx = _d(ctx)
    return ("<div class='osx'>" + _s8a(ctx) + _s8b(ctx) + _s8c(ctx)
            + _s8d(ctx) + _s8e(ctx) + _s8f(ctx) + _s8g(ctx) + _s8h(ctx)
            + "</div>")


def check(ctx: Dict[str, Any] = None) -> Dict[str, Any]:
    ctx = _d(ctx)
    problems = []
    html = marketing_section(ctx) + search_section(ctx)
    for sid in SCREENS_9 + SCREENS_8:
        n = html.count("id='os-%s'" % sid)
        if n == 0:
            problems.append("screen %s declared but not rendered" % sid)
        elif n > 1:
            problems.append("screen %s rendered %d times" % (sid, n))
    # THE DISCLOSURE. 8c and 8e are one employee, and both screens must
    # say so on their face. Only assertable when the worker exists: an
    # empty context renders a "not on the roster" desk, where the question
    # does not arise.
    if _card(ctx, "seo.analyst"):
        for sid in ("8c", "8e"):
            seg = html[html.find("id='os-%s'" % sid):]
            seg = seg[:seg.find("</section>") + 10]
            if "same" not in seg.lower() or "worker" not in seg.lower():
                problems.append("%s does not disclose that it shares a worker"
                                % sid)
    return {"ok": not problems, "problems": problems,
            "screens": len(SCREENS_9) + len(SCREENS_8), "chars": len(html)}


if __name__ == "__main__":
    import content_engine_agentos as _A

    class _S:
        def get_setting(self, k, d=None):
            return {"BRAND_NAME": "acme"}.get(k, d)

        def set_setting(self, k, v):
            pass

        def list_jobs(self, status=None):
            return []

        def daily_cost(self):
            return 0.0

    r = check(_A.build_ctx(_S()))
    assert r["ok"], r["problems"]
    print("screens:", r["screens"], "chars:", r["chars"])
