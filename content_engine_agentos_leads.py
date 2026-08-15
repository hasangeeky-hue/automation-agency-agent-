# -*- coding: utf-8 -*-
"""AGENT OS: turn 12 (Leads and Outreach). Nine screens.

  12a Manager's Command Center   12f Sender / Tracker's desk
  12b Prospector's desk          12g Sources + Department Control Room
  12c Data Cleaner's desk        12h Email Campaign Board
  12d Qualifier's desk           12i Customer Segmentation Board
  12e Outreach Writer's desk

FOUR EMPLOYEES, NINE DESKS
  12c, 12d and 12i are all leads.qualifier. 12f and 12h are both
  leads.sender. Each of those screens names its worker and says it shares
  one, for the same reason 8c and 8e do: two desks are a real distinction
  in the work, and two headcounts would be a lie about the payroll.

THE REGION GATE, HONESTLY
  The wireframe says the Data Cleaner "hard-blocks EU leads from
  outreach". THE ENGINE HAS NO SUCH BLOCK, and it should not: Germany and
  Switzerland are two of the five target markets in
  content_engine_outreach.TARGET_MARKETS, so blocking the EU would block
  the business. What the engine actually enforces is narrower and real:
  open-tracking is a consent matter in those markets and can be switched
  off for every send; the suppression list is absolute; the warm-up ramp
  caps daily volume; and no message leaves without the SEND gate.

  Drawing the hard block would be false-green pointing the other way:
  showing a safety control that does not exist.

  DECIDED 2026-08-15 by the founder: no per-country exclusion. Europe and
  Germany stay in scope. That settles the wireframe line, and it moves the
  whole compliance weight onto open tracking, which is opt-OUT in the
  engine and therefore ON unless switched off. 12c shows its LIVE state
  and offers the switch, because a control described but not shown is a
  control nobody uses.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_os_kit as K

_e, _l, _d = K._e, K._l, K._d

#: his subnav for this module: the label, and the screen
#: it opens. Anchors, exactly as his own markup uses.
SUBNAV_LEADS = [('Command Center', '12a'), ('Prospector', '12b'), ('Data Cleaner', '12c'), ('Qualifier', '12d'), ('Outreach Writer', '12e'), ('Sender / Tracker', '12f'), ('Sources & Control', '12g'), ('Campaigns', '12h'), ('Segmentation', '12i')]

STAFF_12 = ("leads.prospector", "leads.qualifier", "leads.outreach_writer",
            "leads.sender")

#: desks that share a worker -> the disclosure each must carry
SHARED_DESKS = {
    "12c": ("leads.qualifier", "12d and 12i"),
    "12d": ("leads.qualifier", "12c and 12i"),
    "12i": ("leads.qualifier", "12c and 12d"),
    "12f": ("leads.sender", "12h"),
    "12h": ("leads.sender", "12f"),
}


def _card(ctx, aid) -> Dict[str, Any]:
    for c in _l(_d(ctx).get("cards")):
        if _d(c).get("id") == aid:
            return _d(c)
    return {}


def _cards(ctx, *ids) -> List[dict]:
    want = set(ids)
    return [c for c in _l(_d(ctx).get("cards")) if _d(c).get("id") in want]


def _outreach_jobs(ctx) -> List[dict]:
    return [_d(j) for j in _l(_d(ctx).get("jobs"))
            if str(_d(j).get("type")) == "outreach_campaign"]


def _consts():
    """Read from the engine, never re-typed here."""
    out = {"markets": (), "verticals": (), "ramp": (), "touches": 0,
           "rotation": ()}
    try:
        import content_engine_outreach as O
        out["markets"] = tuple(getattr(O, "TARGET_MARKETS", ()) or ())
        out["verticals"] = tuple(getattr(O, "ICP_VERTICALS", ()) or ())
        out["ramp"] = tuple(getattr(O, "WARMUP_RAMP", ()) or ())
        out["touches"] = int(getattr(O, "SEQUENCE_TOUCHES", 0) or 0)
    except Exception:                                     # noqa: BLE001
        pass
    try:
        import content_engine_scheduler as S
        out["rotation"] = tuple(getattr(S, "ICP_ROTATION", ()) or ())
    except Exception:                                     # noqa: BLE001
        pass
    return out


def _tracking_on(ctx) -> bool:
    """True when open tracking is collecting. Defaults to True in the
    engine (it is opt-OUT), which is exactly why the screen shows the
    live value rather than describing the switch."""
    v = _d(ctx).get("tracking_on")
    return True if v is None else bool(v)


def _shared_note(sid: str) -> str:
    if sid not in SHARED_DESKS:
        return ""
    who, others = SHARED_DESKS[sid]
    return K.bp("<span class='ox-lbl'>One worker, more than one desk</span>"
                "<p class='ox-sub'>This desk is worked by the same employee "
                "as %s: <b>%s</b>. The desks are separate because the "
                "questions are. The headcount is one.</p>"
                % (_e(others), _e(who)))


def _desk(ctx, sid, title, sub, agent_id, *, extra: str = "", quick=None,
          note: str = "") -> str:
    card = _card(ctx, agent_id)
    if not card:
        return K.screen(sid, title, sub,
                        "<p class='ox-nodata'>%s is not on the roster, so "
                        "this desk has no worker</p>" % _e(agent_id),
                        staffed_by="nobody", badge_kind="notstaffed")
    blocks = [K.agent_card(card)]
    shared = _shared_note(sid)
    if shared:
        blocks.append(shared)
    if extra:
        blocks.append(extra)
    if len(blocks) == 1:
        blocks.append(K.bp("<span class='ox-lbl'>Its lane</span>"
                           "<p class='ox-sub'>%s</p>" % _e(card.get("why"))))
    return K.screen(
        sid, title, sub,
        K.grid(*blocks, cols="two")
        + K.cmdchat(agent_id, _e(card.get("name")), quick=quick or [],
                    context_note=note),
        staffed_by=_e(card.get("name")), badge_kind=_e(card.get("badge")))


# ==========================================================================
def _s12a(ctx) -> str:
    js = _outreach_jobs(ctx)
    cards = _cards(ctx, *STAFF_12)
    waiting = [j for j in js if str(j.get("status")) == "AWAITING_APPROVAL"]
    c = _consts()
    return K.screen(
        "12a", "Manager's Command Center",
        "The funnel, the source mix, the staff, and the sends waiting on you.",
        K.grid(K.bp(K.stat(len(js), "campaigns", "/jobs")),
               K.bp(K.stat(len(waiting), "waiting on you", "/jobs")),
               K.bp(K.stat(len(c["markets"]) or None, "target markets",
                           "outreach.TARGET_MARKETS")),
               K.bp(K.stat(c["touches"] or None, "touches per sequence",
                           "outreach.SEQUENCE_TOUCHES")))
        + K.bp("<span class='ox-lbl'>Reply rate</span>"
               "<p class='ox-sub'>Reply rate is the honest measure here and "
               "it is not shown as a number until sends exist. Open rate is "
               "deliberately not the headline: it is a tracking pixel that "
               "Apple Mail and corporate gateways pre-fetch, so it reads "
               "high whatever happened.</p>" + K.source_chip("/outreach"))
        + K.grid(*[K.agent_card(x, compact=True) for x in cards]),
        staffed_by="four employees", badge_kind="live")


def _s12b(ctx) -> str:
    c = _consts()
    rot = "".join("<tr><td>%s</td><td>%s</td></tr>" % (_e(v), _e(city))
                  for v, city in c["rotation"][:14])
    return _desk(
        ctx, "12b", "Prospector's desk",
        "Build a pull across sources, each with its cost and its risk.",
        "leads.prospector",
        extra=K.bp("<span class='ox-lbl'>Today's rotation</span>"
                   + (("<div class='ox-tw'><table class='ox-t'><thead><tr>"
                       "<th>Vertical</th><th>City</th></tr></thead><tbody>%s"
                       "</tbody></table></div>" % rot) if rot else
                      "<p class='ox-nodata'>no rotation configured</p>")
                   + K.source_chip("scheduler.ICP_ROTATION")),
        quick=["Source today's list", "Which source is cheapest?"],
        note="Paid sourcing spends money, so it respects the daily cap and "
             "becomes a proposal above the threshold.")


def _s12c(ctx) -> str:
    c = _consts()
    markets = ", ".join(_e(m) for m in c["markets"]) or "not configured"
    real = K.bp(
        "<span class='ox-lbl'>What the region rule actually is</span>"
        "<p class='ox-sub'>Your target markets are <b>%s</b>. Two of them "
        "are in Europe, so a hard EU block would block the business and the "
        "engine does not have one.</p>"
        "<p class='ox-sub'>What IS enforced, and cannot be switched off from "
        "a screen:</p><ul class='ox-rep'>"
        "<li class='ok'>the suppression list is absolute: unsubscribes, "
        "bounces and complaints never receive another message</li>"
        "<li class='ok'>the warm-up ramp caps how many go out per day</li>"
        "<li class='ok'>open tracking can be switched off for every send, "
        "because in Germany and Switzerland tracking without consent is a "
        "GDPR matter</li>"
        "<li class='ok'>nothing sends without the permanent SEND gate</li>"
        "</ul>" % markets)
    # THE FOUNDER'S DECISION, 2026-08-15: no per-country exclusion. Europe
    # and Germany stay in. That settles the wireframe's "hard-block EU"
    # line, and it moves the whole compliance weight onto the one control
    # that is real: open tracking.
    on = _tracking_on(ctx)
    gap = K.bp(
        "<span class='ox-lbl'>Per-country rules: decided</span>"
        "<p class='ox-sub'>The wireframe describes this desk as hard-blocking "
        "EU leads. The engine has no such block, you have decided you do not "
        "want one, and Europe and Germany stay in scope. Nothing here "
        "excludes a country.</p>"
        "<p class='ox-sub'>That decision puts the entire compliance weight on "
        "open tracking, because contacting someone in Germany is not the "
        "issue. Tracking whether they opened it, without consent, is.</p>")
    track = K.bp(
        "<span class='ox-lbl'>Open tracking, right now</span>"
        "<div class='ox-slots'><span class='ox-slot ox-s-%s'><b>%s</b>"
        "Tracking is %s</span></div>"
        "<p class='ox-sub'>%s</p>"
        "<div class='ox-pa-b'>"
        "<button type='button' class='ox-btn%s' onclick=\"osTracking(false)\">"
        "Turn tracking off</button>"
        "<button type='button' class='ox-btn' onclick=\"osTracking(true)\">"
        "Turn it on</button></div>%s"
        % ("rejected" if on else "verified", "✕" if on else "●",
           "ON" if on else "OFF",
           ("It defaults to on. Two of your five markets are Germany and "
            "Switzerland, so this is the switch that matters for you."
            if on else
            "Opens and clicks are not collected. Reply rate stays the "
            "honest measure, and it always was."),
           " ox-btn-p" if on else "", K.source_chip("POST /outreach/tracking")),
        cls="ox-plan" if on else "")
    gap = gap + track
    return _desk(
        ctx, "12c", "Data Cleaner's desk",
        "Verify, dedupe, enrich, and the region rule as it really stands.",
        "leads.qualifier", extra=real + gap,
        quick=["Verify today's list", "How many were suppressed?"],
        note="Cleaning is free and automatic. Nothing here sends.")


def _s12d(ctx) -> str:
    c = _consts()
    return _desk(
        ctx, "12d", "Qualifier's desk",
        "Scoring, segments and personas.",
        "leads.qualifier",
        extra=K.bp("<span class='ox-lbl'>The ICP it scores against</span>"
                   "<div class='ox-slots'>%s</div>"
                   "<p class='ox-sub'>A lead outside these verticals is not "
                   "silently dropped: it scores low and says why.</p>%s"
                   % ("".join("<span class='ox-slot'>%s</span>" % _e(v)
                              for v in c["verticals"])
                      or "<span class='ox-nodata'>no ICP configured</span>",
                      K.source_chip("outreach.ICP_VERTICALS"))),
        quick=["Re-score the current list", "Why did this one score low?"],
        note="Scoring is free and automatic. A score is not a send.")


def _s12e(ctx) -> str:
    return _desk(
        ctx, "12e", "Outreach Writer's desk",
        "Personalises the offer on Marketing's template. Cold email is not a "
        "newsletter and is not written like one.",
        "leads.outreach_writer",
        extra=K.bp("<span class='ox-lbl'>What it learns from</span>"
                   "<p class='ox-sub'>Subject lines that booked a call go "
                   "into THIS desk's playbook, not the blog writer's. That "
                   "separation is new: before it, the two lanes taught each "
                   "other the wrong lessons.</p>"
                   + K.source_chip("/agents/leads.outreach_writer/learned")),
        quick=["Draft the next campaign", "Shorter subject lines"],
        note="This desk has no send capability at all. It writes and stops.")


def _s12f(ctx) -> str:
    c = _consts()
    ramp = ", ".join(str(n) for n in c["ramp"]) or "not configured"
    return _desk(
        ctx, "12f", "Sender / Tracker's desk",
        "Compliance, the send gate, live tracking and follow-ups.",
        "leads.sender",
        extra=K.bp("<span class='ox-lbl'>The three things that hold a send</span>"
                   "<ul class='ox-rep'>"
                   "<li class='ok'>the SEND gate: you approve, then it goes</li>"
                   "<li class='ok'>the warm-up ramp: %s per day, in order, so "
                   "a fresh domain is not torched</li>"
                   "<li class='ok'>the suppression list, which no approval "
                   "overrides</li></ul>"
                   "<p class='ox-sub'>Follow-ups stop the moment someone "
                   "replies. %d touches maximum.</p>%s"
                   % (_e(ramp), c["touches"],
                      K.source_chip("outreach.WARMUP_RAMP"))),
        quick=["What is queued to send?", "Pause all sending"],
        note="Approving here still hits the send gate. There is no path from "
             "this panel to an inbox that skips it.")


def _s12g(ctx) -> str:
    cards = _cards(ctx, *STAFF_12)
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_e(_d(x).get("name")), K.badge(_e(_d(x).get("badge"))),
           "".join("<span class='ox-slot ox-s-%s'><b>%s</b>%s</span>"
                   % (_e(_d(s).get("status")),
                      K.STATUS_LABEL.get(str(_d(s).get("status")),
                                         K.STATUS_LABEL["empty"])[0],
                      _e(_d(s).get("tool")))
                   for s in _l(_d(x).get("slots"))) or "none",
           _e(_d(x).get("cap_key") or "")) for x in cards)
    return K.screen(
        "12g", "Sources and Department Control Room",
        "Cost and risk per source, autonomy per employee, and the rules that "
        "no setting can relax.",
        "<div class='ox-tw'><table class='ox-t'><thead><tr><th>Employee</th>"
        "<th>Staffing</th><th>Tool slots</th><th>Cap</th></tr></thead><tbody>"
        "%s</tbody></table></div>" % rows
        + K.bp("<span class='ox-lbl'>Hard rules</span>"
               "<ul class='ox-rep'>"
               "<li>SEND is a permanent gate. Autonomy cannot open it.</li>"
               "<li>The suppression list is absolute.</li>"
               "<li>Paid sourcing respects the daily cap and parks the job "
               "when it is reached, reporting the cap by name.</li></ul>"),
        staffed_by="you", badge_kind="")


def _s12h(ctx) -> str:
    return _desk(
        ctx, "12h", "Email Campaign Board",
        "Bulk sends built by Marketing, routed through an ESP or the "
        "platform's own API.",
        "leads.sender",
        extra=K.grid(
            K.planned("Klaviyo or another ESP", "an ESP API credential"),
            K.planned("Platform-native bulk API", "the platform credential")),
        quick=["What is queued?", "Which route would this campaign take?"],
        note="Routing changes how a message is delivered. It never changes "
             "whether you approved it.")


def _s12i(ctx) -> str:
    c = _consts()
    return _desk(
        ctx, "12i", "Customer Segmentation Board",
        "Lifecycle segments, plus lead source and location.",
        "leads.qualifier",
        extra=K.bp("<span class='ox-lbl'>Where segments come from</span>"
                   "<p class='ox-sub'>Segments are derived from the lead's "
                   "own record: vertical, city and how it entered. They are "
                   "not invented categories, so a segment with nobody in it "
                   "is absent rather than shown as zero.</p>"
                   "<div class='ox-slots'>%s</div>%s"
                   % ("".join("<span class='ox-slot'>%s</span>" % _e(m)
                              for m in c["markets"]),
                      K.source_chip("outreach.TARGET_MARKETS"))),
        quick=["Show the biggest segment", "Export this segment"],
        note="Import and export move a list. Neither one sends anything.")


# ==========================================================================
SCREENS_12 = ("12a", "12b", "12c", "12d", "12e", "12f", "12g", "12h", "12i")


def leads_section(ctx: Dict[str, Any]) -> str:
    """5 · Leads & Outreach, in the shell his wireframe uses.

    Sidebar of modules, this module's screens as a subnav
    nested under it, and the screens stacked in main. His own
    subnav links are anchors, so stacking is how his prototype
    navigates rather than a shortcut.
    """
    ctx = _d(ctx)
    body = (_s12a(ctx) + _s12b(ctx) + _s12c(ctx)
            + _s12d(ctx) + _s12e(ctx) + _s12f(ctx) + _s12g(ctx) + _s12h(ctx)
            + _s12i(ctx))
    return ("<div class='osx'>"
            + K.frame('5 · Leads & Outreach', SUBNAV_LEADS, body)
            + "</div>")



def check(ctx: Dict[str, Any] = None) -> Dict[str, Any]:
    ctx = _d(ctx)
    problems = []
    html = leads_section(ctx)
    for sid in SCREENS_12:
        n = html.count("id='os-%s'" % sid)
        if n == 0:
            problems.append("screen %s not rendered" % sid)
        elif n > 1:
            problems.append("screen %s rendered %d times" % (sid, n))
    # every shared desk must disclose that it shares a worker
    for sid, (who, _others) in SHARED_DESKS.items():
        if not _card(ctx, who):
            continue
        seg = html[html.find("id='os-%s'" % sid):]
        seg = seg[:seg.find("</section>") + 10]
        if "One worker" not in seg:
            problems.append("%s does not disclose that it shares a worker"
                            % sid)
    # THE SAFETY CLAIM. 12c must keep saying that the EU hard block the
    # wireframe describes is NOT in the engine. Showing a safety control
    # that does not exist is false-green pointing the other way, and it is
    # the one thing on this turn that could get the founder in trouble.
    flat = " ".join(html.split())
    if "the engine does not have one" not in flat:
        problems.append("12c no longer states that the EU hard block is "
                        "absent from the engine")
    if "SEND gate" not in flat:
        problems.append("the send gate is not named on this turn")
    # The founder keeps Europe in scope, so the tracking switch is the
    # real control and must be shown live, not described.
    if "Open tracking, right now" not in flat:
        problems.append("12c does not show the LIVE open-tracking state")
    if "osTracking(" not in html:
        problems.append("the tracking switch is not wired to anything")
    return {"ok": not problems, "problems": problems,
            "screens": len(SCREENS_12), "chars": len(html)}


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
