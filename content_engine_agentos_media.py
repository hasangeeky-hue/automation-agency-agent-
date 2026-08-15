# -*- coding: utf-8 -*-
"""AGENT OS: MEDIA BUYING, module 1. Nine screens.

  7a Manager's Command Center   7f Pacing's desk
  7b Scout's desk               7g Reporter's desk
  7c Creative's desk            7h Data Sources
  7d Launch's desk              7i Agents Room
  7e Optimizer's desk

EVERY PART OF THIS IS READ OUT OF THE FOUNDER'S WIREFRAME
  The handoff draws no Media screens, but it specifies the department
  completely, and nothing here is invented:

  - the six desks are its own list, verbatim:
      media: ['Scout','Creative','Launch','Optimizer','Pacing','Reporter']
    and its cockpit card agrees (agents: 6).
  - the shape is the shape every other module uses: a Command Center,
    one screen per desk, a Data Sources screen and a control room. The
    wireframe says so twice, in its own words: "Tools layer mirrors
    SEO's data-sources screen" and "Control Room mirrors Media Buyer's
    agents room exactly - autonomy level, data access + cost cap,
    activity log, per employee". THIS module's agents room is the
    canonical one the others copy, so it is built to that description.
  - its connectors are the ones the wireframe lists as feeding Media
    Buyer: Google Ads, Meta, TikTok, LinkedIn.
  - its own state line: "ARCHITECTED - adapters return UNSUPPORTED,
    Google Ads OAuth broken".

THE TURN NUMBER IS THE ONE THING I CHOSE
  The wireframe's ids come from turn numbers and Media Buying has none:
  it is "module 1" with no drawn turn. Screens are numbered 7a to 7i
  because 7 is the free number directly below t8, so the ids sort in
  front of the departments they precede. That is a filing decision, not
  a design one, and renaming them is one line.

PINK, READ OFF THE FOUNDER'S OWN TWO EXAMPLES
  His approval queue marks 'Scale Meta "Retarget" +$50/day' as NOT pink
  and 'Add $300 to TikTok test budget' as PINK. The rule that fits both:
  moving spend inside an already-approved budget is gated but batchable;
  anything that RAISES the total committed budget is pink and goes one
  at a time. Both are still gated. SPEND is a permanent gate.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_os_kit as K

_e, _l, _d = K._e, K._l, K._d

AGENT = "media.buyer"

#: the founder's own six, verbatim from cockpitAgents.media
DESKS = [
    ("7b", "🔍", "Scout", "finds where the money could work: accounts, "
                          "objectives and what each platform can actually do"),
    ("7c", "🎨", "Creative", "the assets and the variants, and which ones "
                             "earned their impressions"),
    ("7d", "🚀", "Launch", "puts a campaign live, and never without you"),
    ("7e", "📈", "Optimizer", "proposes moving spend towards what is working"),
    ("7f", "💰", "Pacing", "whether the month is on track to spend what it "
                           "was given, and no more"),
    ("7g", "📊", "Reporter", "what the money bought, attributed honestly"),
]

#: the wireframe's own list of what feeds Media Buyer
MEDIA_WIRES = [
    ("Google Ads", "ads_api"),
    ("Meta", "social_facebook"),
    ("TikTok", "social_tiktok"),
    ("LinkedIn", "social_linkedin"),
]

#: his own state line for this module
MODULE_STATE = ("adapters return UNSUPPORTED_CAPABILITY and Google Ads "
                "refuses the OAuth client, so nothing here can launch or "
                "spend yet")


def _card(ctx) -> Dict[str, Any]:
    for c in _l(_d(ctx).get("cards")):
        if _d(c).get("id") == AGENT:
            return _d(c)
    return {}


def _media(ctx) -> Dict[str, Any]:
    return _d(_d(ctx).get("media"))


def build_media_ctx(store) -> Dict[str, Any]:
    """Read the media engine, and degrade honestly.

    Every call is wrapped separately: one broken reader must not blank
    the whole department, and a panel that cannot be filled says which
    call failed rather than rendering an empty grid."""
    out: Dict[str, Any] = {"ok": False, "why": "", "errors": []}
    try:
        import content_engine_media_os as M
        r = M.repo(store)
        out["repo"] = True
        out["ok"] = True
    except Exception as exc:                              # noqa: BLE001
        out["why"] = "the media repository would not open (%s)" % type(exc).__name__
        return out

    def _try(name, fn):
        try:
            out[name] = fn()
        except Exception as exc:                          # noqa: BLE001
            out[name] = None
            out["errors"].append("%s: %s" % (name, type(exc).__name__))

    import content_engine_media_os as M
    _try("accounts", lambda: M.accounts(r))
    _try("capability", lambda: M.capability_table())
    _try("drift", lambda: M.drift(r))
    try:
        import content_engine_media_metrics as MM
        _try("pacing", lambda: MM.pacing(r, store))
        _try("quality", lambda: MM.data_quality(r, store))
    except Exception:                                     # noqa: BLE001
        pass
    try:
        import content_engine_media_plan as MP
        _try("history", lambda: MP.history(r))
    except Exception:                                     # noqa: BLE001
        pass
    try:
        import content_engine_media_perf as PF
        _try("business", lambda: PF.business(r, store))
    except Exception:                                     # noqa: BLE001
        pass
    try:
        import content_engine_media_creative as MC
        _try("creatives", lambda: MC.creative_performance(r))
    except Exception:                                     # noqa: BLE001
        pass
    return out


# --------------------------------------------------------------------------
def _wire_rows(ctx) -> str:
    health = {_d(h).get("wire"): _d(h) for h in _l(_d(ctx).get("health"))}
    rows = []
    for label, wire in MEDIA_WIRES:
        h = health.get(wire, {})
        st = _e(h.get("status") or "empty")
        icon, word = K.STATUS_LABEL.get(str(h.get("status")),
                                        K.STATUS_LABEL["empty"])
        rows.append("<tr><td>%s</td><td class='ox-wire'>%s</td>"
                    "<td><span class='ox-dot ox-s-%s'><b>%s</b>%s</span></td>"
                    "<td>%s</td></tr>"
                    % (_e(label), _e(wire), st, icon, _e(word),
                       _e(h.get("reason") or "")))
    return ("<div class='ox-tw'><table class='ox-t'><thead><tr>"
            "<th>Platform</th><th>Wire</th><th>State</th><th>Reason</th>"
            "</tr></thead><tbody>%s</tbody></table></div>" % "".join(rows))


def _blocked_note(ctx) -> str:
    """The module's own state line, shown on every desk that cannot act."""
    return K.bp("<span class='ox-lbl'>Why nothing here spends yet</span>"
                "<p class='ox-sub'>%s</p>"
                "<p class='ox-need'>Needs: <b>the Google Ads OAuth client "
                "reissued</b>, and an adapter that reports a real "
                "capability rather than UNSUPPORTED.</p>" % _e(MODULE_STATE),
                cls="ox-plan")


def _desk(ctx, sid, icon, name, sub, *, extra: str = "", quick=None,
          note: str = "") -> str:
    card = _card(ctx)
    if not card:
        return K.screen(sid, "%s %s's desk" % (icon, name), sub,
                        "<p class='ox-nodata'>media.buyer is not on the "
                        "roster</p>", staffed_by="nobody",
                        badge_kind="notstaffed")
    shared = K.bp(
        "<span class='ox-lbl'>One worker, six desks</span>"
        "<p class='ox-sub'>Scout, Creative, Launch, Optimizer, Pacing and "
        "Reporter are six views of <b>media.buyer</b>. Six boards, one lane "
        "owner, one playbook. Splitting them would mean nobody owns the "
        "spend.</p>")
    blocks = [K.agent_card(card), shared]
    if extra:
        blocks.append(extra)
    blocks.append(_blocked_note(ctx))
    return K.screen(
        sid, "%s %s's desk" % (icon, name), sub,
        K.grid(*blocks, cols="two")
        + K.cmdchat(AGENT, "%s %s" % (icon, name), quick=quick or [],
                    context_note=note),
        staffed_by=_e(card.get("name")), badge_kind=_e(card.get("badge")))


# --------------------------------------------------------------------------
def _s7a(ctx) -> str:
    m = _media(ctx)
    card = _card(ctx)
    pac = _d(m.get("pacing"))
    biz = _d(m.get("business"))
    accts = _l(m.get("accounts"))
    return K.screen(
        "7a", "Manager's Command Center",
        "The whole media department at a glance: what is connected, what is "
        "pacing, and what is waiting on you.",
        K.grid(
            K.bp(K.stat(len(accts) or None, "ad accounts", "/mediaos")),
            K.bp(K.stat(pac.get("spend_to_date"), "spent this month",
                        "/mediaos/pacing")),
            K.bp(K.stat(pac.get("month_budget"), "budget", "/mediaos/pacing")),
            K.bp(K.stat(biz.get("revenue"), "revenue attributed",
                        "/mediaos/business")))
        + _blocked_note(ctx)
        + K.grid(K.agent_card(card) if card else "", _wire_rows(ctx),
                 cols="two"),
        staffed_by=_e(card.get("name") or "nobody"),
        badge_kind=_e(card.get("badge") or "notstaffed"))


def _s7b(ctx) -> str:
    m = _media(ctx)
    cap = _l(m.get("capability"))
    rows = "".join(
        "<tr><td>%s</td><td>%s</td></tr>"
        % (_e(_d(c).get("provider") or _d(c).get("name") or c),
           _e(_d(c).get("supported") if isinstance(c, dict) else ""))
        for c in cap[:12])
    return _desk(
        ctx, "7b", "🔍", "Scout",
        "Where the money could work: accounts, objectives, and what each "
        "platform can actually do.",
        extra=K.bp("<span class='ox-lbl'>What each platform supports</span>"
                   + (("<div class='ox-tw'><table class='ox-t'><thead><tr>"
                       "<th>Provider</th><th>Supported</th></tr></thead>"
                       "<tbody>%s</tbody></table></div>" % rows) if rows else
                      "<p class='ox-nodata'>no capability table; the "
                      "adapters have not reported what they can do</p>")
                   + K.source_chip("/mediaos/capability")),
        quick=["What can Meta actually do?", "Which accounts are reachable?"],
        note="Scouting reads. It cannot create a campaign or spend.")


def _s7c(ctx) -> str:
    m = _media(ctx)
    cr = _l(m.get("creatives"))
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_e(_d(c).get("name") or _d(c).get("id")),
           _e(_d(c).get("impressions")), _e(_d(c).get("ctr")))
        for c in cr[:12])
    return _desk(
        ctx, "7c", "🎨", "Creative",
        "The assets and their variants, and which ones earned their "
        "impressions.",
        extra=K.bp("<span class='ox-lbl'>Creative performance</span>"
                   + (("<div class='ox-tw'><table class='ox-t'><thead><tr>"
                       "<th>Creative</th><th>Impressions</th><th>CTR</th>"
                       "</tr></thead><tbody>%s</tbody></table></div>" % rows)
                      if rows else
                      "<p class='ox-nodata'>no creative has run, so there is "
                      "nothing to rank. An empty table here is a fact about "
                      "the account, not a missing feature.</p>")
                   + K.source_chip("/mediaos/creative")),
        quick=["Which creative is tiring?", "Draft three new variants"],
        note="Drafting a creative is free. Putting it behind money is not, "
             "and that is the Launch desk with the spend gate on it.")


def _s7d(ctx) -> str:
    return _desk(
        ctx, "7d", "🚀", "Launch",
        "Puts a campaign live. Never without you.",
        extra=K.bp("<span class='ox-lbl'>What a launch requires</span>"
                   "<ul class='ox-rep'>"
                   "<li>a verified adapter for that platform</li>"
                   "<li>a budget you approved, by name</li>"
                   "<li>a pre-flight check that the account will accept it</li>"
                   "</ul>"
                   "<p class='ox-sub'>SPEND is one of the five permanent "
                   "gates. No autonomy setting opens it, and there is no "
                   "control on this screen that launches anything "
                   "directly.</p>"),
        quick=["Pre-flight the draft campaign"],
        note="A launch is proposed with its budget and its forecast. You "
             "approve it, and only then does it go.")


def _s7e(ctx) -> str:
    m = _media(ctx)
    hist = _d(m.get("history"))
    return _desk(
        ctx, "7e", "📈", "Optimizer",
        "Proposes moving spend towards what is working.",
        extra=K.bp("<span class='ox-lbl'>How a shift is proposed</span>"
                   "<p class='ox-sub'>Moving money INSIDE a budget you "
                   "already approved is gated but can be approved in a "
                   "batch. Anything that RAISES the total committed budget "
                   "is <span class='ox-pink'>pink</span> and goes one at a "
                   "time. Both are gated; the difference is only whether "
                   "you can clear several at once.</p>"
                   + K.stat(_d(hist).get("days"), "days of history read",
                            "/mediaos/history")),
        quick=["What would you move today?", "Which campaign is decaying?"],
        note="The optimizer PROPOSES. Agents are read-only on media by "
             "design, so nothing here shifts a euro on its own.")


def _s7f(ctx) -> str:
    m = _media(ctx)
    pac = _d(m.get("pacing"))
    return _desk(
        ctx, "7f", "💰", "Pacing",
        "Whether the month is on track to spend what it was given, and no "
        "more.",
        extra=K.bp("<span class='ox-lbl'>This month</span>"
                   + K.grid(
                       K.bp(K.stat(pac.get("spend_to_date"), "spent",
                                   "/mediaos/pacing")),
                       K.bp(K.stat(pac.get("month_budget"), "budget",
                                   "/mediaos/pacing")),
                       K.bp(K.stat(pac.get("projected"), "projected",
                                   "/mediaos/pacing")))
                   + "<p class='ox-sub'>A projection with no spend behind it "
                     "is not shown as zero. Where the figure is absent the "
                     "account has not reported, which is a different fact "
                     "from having spent nothing.</p>"),
        quick=["Are we going to overspend?"],
        note="Pacing reads and warns. It cannot pause a campaign; that is a "
             "spend decision and it is yours.")


def _s7g(ctx) -> str:
    m = _media(ctx)
    biz = _d(m.get("business"))
    q = _d(m.get("quality"))
    return _desk(
        ctx, "7g", "📊", "Reporter",
        "What the money bought, attributed honestly.",
        extra=K.bp("<span class='ox-lbl'>Attributed result</span>"
                   + K.grid(
                       K.bp(K.stat(biz.get("revenue"), "revenue",
                                   "/mediaos/business")),
                       K.bp(K.stat(biz.get("orders"), "orders",
                                   "/mediaos/business")),
                       K.bp(K.stat(biz.get("roas"), "ROAS",
                                   "/mediaos/business")))
                   + "<p class='ox-sub'>Attribution is a MODEL, not a "
                     "measurement. The number above is last-touch unless it "
                     "says otherwise, and it will disagree with the "
                     "platform's own figure because the platform is marking "
                     "its own homework.</p>"
                   + ("<p class='ox-sub'>Data quality: %s</p>"
                      % _e(q.get("verdict") or q.get("state") or ""))
                   if q else ""),
        quick=["What did last month actually return?"],
        note="Reporting reads. It changes nothing.")


def _s7h(ctx) -> str:
    return K.screen(
        "7h", "Data Sources",
        "A provider per slot, so the department is not tied to one vendor. "
        "The same shape as the Search department's sources screen.",
        _wire_rows(ctx)
        + K.bp("<span class='ox-lbl'>What each platform is for</span>"
               "<p class='ox-sub'>Google Ads and Meta carry the spend. "
               "TikTok and LinkedIn are listed by the design as feeding this "
               "department and hold credentials that have never been proven. "
               "A saved key is not a working one, and on a spending wire "
               "that difference is expensive.</p>"
               + K.source_chip("/connectors/health")),
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


def _s7i(ctx) -> str:
    """The agents room the wireframe calls canonical: autonomy level, data
    access and cost cap, and an activity log, per employee."""
    card = _card(ctx)
    rep = _d(card.get("report"))
    log = []
    for f in _l(rep.get("finished"))[:5]:
        log.append("<li class='ok'>%s</li>" % _e(_d(f).get("what")))
    for f in _l(rep.get("couldnt"))[:5]:
        log.append("<li class='bad'>%s <em>%s</em></li>"
                   % (_e(_d(f).get("what")), _e(_d(f).get("cause"))))
    rows = "".join(
        "<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (icon, _e(name), _e(card.get("autonomy") or "Propose, I approve"),
           _e(card.get("cap_key") or ""),
           "read only" if sid != "7d" else "read only; launch is gated")
        for sid, icon, name, _sub in DESKS)
    return K.screen(
        "7i", "Agents Room",
        "Autonomy, data access and cost cap, and the activity log, per "
        "employee. The wireframe calls this the pattern every other module's "
        "control room copies.",
        "<div class='ox-tw'><table class='ox-t'><thead><tr><th>Desk</th>"
        "<th>Autonomy</th><th>Cost cap</th><th>Data access</th></tr></thead>"
        "<tbody>%s</tbody></table></div>" % rows
        + K.grid(
            K.bp("<span class='ox-lbl'>Activity</span>"
                 + ("<ul class='ox-rep'>%s</ul>" % "".join(log) if log else
                    "<p class='ox-nodata'>nothing recorded today</p>")
                 + K.source_chip("/agents/media.buyer/report")),
            K.bp("<span class='ox-lbl'>The rule that governs all six</span>"
                 "<p class='ox-sub'>Agents are READ-ONLY on media by design. "
                 "Every one of these desks proposes; none of them spends. "
                 "Raising autonomy widens what runs automatically inside the "
                 "low-stakes band and can never open the spend gate.</p>"),
            cols="two"),
        staffed_by="you", badge_kind="")


# --------------------------------------------------------------------------
SCREENS_7 = ("7a", "7b", "7c", "7d", "7e", "7f", "7g", "7h", "7i")


def media_section(ctx: Dict[str, Any]) -> str:
    ctx = _d(ctx)
    return ("<div class='osx'>" + _s7a(ctx) + _s7b(ctx) + _s7c(ctx)
            + _s7d(ctx) + _s7e(ctx) + _s7f(ctx) + _s7g(ctx) + _s7h(ctx)
            + _s7i(ctx) + "</div>")


def check(ctx: Dict[str, Any] = None) -> Dict[str, Any]:
    ctx = _d(ctx)
    problems = []
    html = media_section(ctx)
    for sid in SCREENS_7:
        n = html.count("id='os-%s'" % sid)
        if n == 0:
            problems.append("screen %s not rendered" % sid)
        elif n > 1:
            problems.append("screen %s rendered %d times" % (sid, n))
    # THE DESKS ARE THE FOUNDER'S, VERBATIM. If this list ever drifts
    # from his wireframe the department stops being his design.
    want = ["Scout", "Creative", "Launch", "Optimizer", "Pacing", "Reporter"]
    got = [n for _s, _i, n, _d2 in DESKS]
    if got != want:
        problems.append("the six desks no longer match the wireframe: %s"
                        % got)
    flat = " ".join(html.split())
    # These assert the CONTENT of a staffed desk. With no roster card the
    # desks short-circuit to "nobody works here", and demanding the
    # disclosure of a desk that has no worker is asking the wrong
    # question.
    if not _card(ctx):
        return {"ok": not problems, "problems": problems,
                "screens": len(SCREENS_7), "chars": len(html),
                "note": "content checks skipped: no roster card in this ctx"}
    if "One worker, six desks" not in flat:
        problems.append("the shared-worker disclosure is missing")
    if "SPEND is one of the five permanent gates" not in flat:
        problems.append("the spend gate is not stated on the Launch desk")
    if "read-only on media by design" not in flat.lower():
        problems.append("the read-only rule is missing from the agents room")
    if "Attribution is a MODEL" not in flat:
        problems.append("the Reporter no longer warns that attribution is a "
                        "model rather than a measurement")
    return {"ok": not problems, "problems": problems,
            "screens": len(SCREENS_7), "chars": len(html)}


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

    _ctx = _A.build_ctx(_S())
    _ctx["media"] = build_media_ctx(_S())
    r = check(_ctx)
    assert r["ok"], r["problems"]
    print("screens:", r["screens"], "chars:", r["chars"])
