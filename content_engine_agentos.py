# -*- coding: utf-8 -*-
"""AGENT OS: turn 13 (Web & Data Core) and turn 14 (Cockpit).

Sixteen screens, composed entirely from content_engine_os_kit (module: content_engine_agentos). Screen ids
and titles are the wireframe's own, read out of the handoff file, not
invented here.

  13a Core Command Center      13g Analytics
  13b Integrations Desk        13h Sources + Staff Control Room
  13c Data Steward Desk        13i Tool Connection Hub
  13d Developer Desk           13j Health & Risk Monitor
  13e Infra / SRE Desk         13k Connector / API Map
  13f Orchestrator Desk
  14a Cockpit Home             14d System Health & Activity
  14b Unified Approval Queue   14e System Control Room
  14c All-Agents Grid

THE RULE THAT SHAPES EVERY SCREEN HERE
--------------------------------------
A desk is a VIEW of a lane; a lane has exactly one owner. So each screen
names the employee who works it, and one employee legitimately appears on
several. Where no employee exists, the screen says so and shows nothing
rather than borrowing another desk's numbers.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_contracts as C
import content_engine_os_kit as K

_e, _l, _d = K._e, K._l, K._d

#: his subnav for this module: the label, and the screen
#: it opens. Anchors, exactly as his own markup uses.
#: HIS FINAL REVISION reordered and renamed this subnav and added
#: new screens to it. Taken from the 56-screen file, not carried
#: forward from the 51-screen one.
SUBNAV_CORE = [('Command Center', '13a'), ('Integrations', '13b'), ('Data Steward', '13c'), ('ERP & Data Hub', '16a'), ('Mutation Ledger', '16b'), ('Developer', '13d'), ('Infra / SRE', '13e'), ('Orchestrator', '13f'), ('Analytics', '13g'), ('Sources & Control', '13h'), ('Tool Hub', '13i'), ('Health & Risk', '13j'), ('Connector Map', '13k')]

#: his subnav for this module: the label, and the screen
#: it opens. Anchors, exactly as his own markup uses.
SUBNAV_COCKPIT = [('Cockpit Home', '14a'), ('Approval Queue', '14b'), ('All Agents', '14c'), ('Health & Activity', '14d'), ('Control Room', '14e')]

#: the six departments of the wireframe, and who actually staffs each
MODULES = [
    ("seo", "🔍 SEO / AEO / GEO", "seo"),
    ("content", "📣 Marketing / Content", "content"),
    ("commerce", "📦 Commerce", "commerce"),
    ("outreach", "🎯 Leads & Outreach", "outreach"),
    ("system", "🗄 Web & Data Core", "system"),
    ("media", "🛒 Media Buying", "media"),
]

#: desks the wireframe draws that have no employee, and the honest reason
UNSTAFFED_DESKS = {
    "13c": ("🗄 Data Steward",
            "a schema and quality desk is worth having and costs nothing to "
            "run, because it would be code only. It is not built yet, so "
            "this screen shows no numbers."),
    "13d": ("👨‍💻 Developer",
            "deliberately not built. A code-writing agent with access to the "
            "live site is the one thing the five gates cannot make safe, so "
            "this desk stays empty on purpose."),
}


# ==========================================================================
# CONTEXT
# ==========================================================================
def build_ctx(store) -> Dict[str, Any]:
    """Everything the sixteen screens read, gathered once.

    Every value here comes from an endpoint that already exists. Nothing on
    these screens is computed a second, different way: that is how a headline
    comes to disagree with the table underneath it."""
    ctx: Dict[str, Any] = {"cards": [], "health": [], "company": {},
                           "integrations": {}, "proposals": [], "roster": [],
                           "staffing": [], "errors": []}
    try:
        import content_engine_report as RP
        ctx["cards"] = RP.agent_cards(store)
        ctx["company"] = RP.company_today(store)
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("report: %s" % type(exc).__name__)
    try:
        import content_engine_connectors as CN
        ctx["health"] = [dict(r) for r in CN.health()]
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("connectors: %s" % type(exc).__name__)
    try:
        import content_engine_integrations as INT
        ctx["integrations"] = INT.self_tests(store)
        ctx["int_proposals"] = INT.proposals(store)
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("integrations: %s" % type(exc).__name__)
        ctx["int_proposals"] = []
    try:
        import content_engine_roster as R
        ctx["roster"] = R.roster()
        ctx["staffing"] = R.staffing_all()
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("roster: %s" % type(exc).__name__)
    try:
        ctx["proposals"] = list(store.get_setting("proposals", []) or [])
    except Exception:                                     # noqa: BLE001
        ctx["proposals"] = []
    # The Commerce Analyst's daily inspection, for turn 11 and turn 10.
    try:
        import content_engine_commerce_desk as _CD
        ctx["commerce"] = _CD.inspect(store)
        import content_engine_commerce as _CM
        _cat = _CM.fetch_catalogue(store)
        ctx["commerce"]["products"] = list(_cat.get("products") or [])
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("commerce: %s" % type(exc).__name__)
        ctx["commerce"] = {"ok": False, "products": [],
                           "why": "the commerce desk raised %s"
                                  % type(exc).__name__, "findings": []}
    # Stage 2 pricing proposals. These are PINK and they are the only
    # thing in the OS that can change what a customer pays, so they must
    # reach the cockpit queue rather than living on one commerce screen.
    try:
        import content_engine_pricing as _PX
        ctx["price_proposals"] = _PX.proposals(store, "pending")
        ctx["price_applied"] = _PX.proposals(store, "applied")
        ctx["target_margin_pct"] = _PX.target_margin(store)
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("pricing: %s" % type(exc).__name__)
        ctx["price_proposals"], ctx["price_applied"] = [], []
    # The social queue: written posts and why they have not gone out.
    try:
        import content_engine_social_desk as _SD
        ctx["social"] = _SD.queue(store)
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("social: %s" % type(exc).__name__)
        ctx["social"] = {}
    # The media engine, for module 1's nine screens.
    try:
        import content_engine_agentos_media as _MD
        ctx["media"] = _MD.build_media_ctx(store)
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("media: %s" % type(exc).__name__)
        ctx["media"] = {"ok": False,
                        "why": "the media reader raised %s"
                               % type(exc).__name__}
    # The Risk Sentinel's posture. The backup question is the single most
    # consequential thing on this dashboard, so it is read every render.
    try:
        import content_engine_risk_desk as _RD
        ctx["risk"] = _RD.inspect(store)
    except Exception as exc:                              # noqa: BLE001
        ctx["errors"].append("risk: %s" % type(exc).__name__)
        ctx["risk"] = {"findings": [], "host_cron": ""}
    # Open tracking: a live compliance state, not a description. The
    # founder keeps Europe in scope, so this switch is the real control.
    try:
        import content_engine_outreach as _O
        ctx["tracking_on"] = bool(_O.tracking_enabled(store))
    except Exception:                                     # noqa: BLE001
        ctx["tracking_on"] = None
    # The jobs themselves, for the pipeline and calendar screens in t8/t9.
    try:
        ctx["jobs"] = [dict(j) for j in store.list_jobs(status=None)]
    except Exception:                                     # noqa: BLE001
        ctx["jobs"] = []
    return ctx


def _cards_for(ctx, module: str) -> List[dict]:
    return [c for c in _l(ctx.get("cards"))
            if _d(c).get("module") == module]


def _counts(ctx) -> Dict[str, int]:
    h = _l(ctx.get("health"))
    return {st: sum(1 for r in h if _d(r).get("status") == st)
            for st in C.CONNECTOR_STATES}


# ==========================================================================
# TURN 13 - WEB & DATA CORE
# ==========================================================================
def _s13a(ctx) -> str:
    co = _d(ctx.get("company"))
    n = _counts(ctx)
    stats = K.grid(
        K.bp(K.stat(co.get("finished_n"), "finished today", "/company/today")),
        K.bp(K.stat(co.get("couldnt_n"), "couldn't", "/company/today")),
        K.bp(K.stat(co.get("need_n"), "waiting on you", "/company/today")),
        K.bp(K.stat(n.get("verified"), "wires verified", "/connectors/health")),
    )
    causes = _l(co.get("top_causes"))
    why = ("<ul class='ox-rep'>%s</ul>"
           % "".join("<li class='bad'>%s</li>" % _e(c) for c in causes[:4])
           ) if causes else "<p class='ox-nodata'>nothing failed today</p>"
    flow = K.bp(
        "<span class='ox-lbl'>Data flow</span>"
        "<p class='ox-sub'>Every wire normalises through one hub before any "
        "desk reads it. A wire that is refusing breaks the line here rather "
        "than silently returning nothing downstream.</p>" + _flow_map(ctx))
    return K.screen(
        "13a", "Core Command Center",
        "Data flow map, staff, approvals, and what the core owes you today.",
        stats + K.grid(flow, K.bp("<span class='ox-lbl'>Why work stopped</span>"
                                  + why), cols="two"),
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


def _flow_map(ctx) -> str:
    """The connector map as a table rather than a drawing: a line's colour is
    not information a screen reader can use, and the wire's state is the
    whole point of the picture."""
    rows = []
    for r in _l(ctx.get("health"))[:14]:
        rd = _d(r)
        st = str(rd.get("status") or "empty")
        icon, word = K.STATUS_LABEL.get(st, K.STATUS_LABEL["empty"])
        feeds = ", ".join(_e(f) for f in _l(rd.get("feeds"))) or "nothing yet"
        rows.append("<tr><td class='ox-wire'>%s</td>"
                    "<td><span class='ox-dot ox-s-%s'><b>%s</b>%s</span></td>"
                    "<td>HUB</td><td>%s</td></tr>"
                    % (_e(rd.get("wire")), _e(st), icon, _e(word), feeds))
    if not rows:
        return "<p class='ox-nodata'>no wires to map</p>"
    return ("<div class='ox-tw'><table class='ox-t'><thead><tr><th>Tool</th>"
            "<th>State</th><th>Normalises via</th><th>Feeds</th></tr></thead>"
            "<tbody>%s</tbody></table></div>" % "".join(rows))


def _s13b(ctx) -> str:
    it = _d(ctx.get("integrations"))
    findings = _l(it.get("findings"))
    props = _l(ctx.get("int_proposals"))
    n = _counts(ctx)
    head = K.grid(
        K.bp(K.stat(it.get("checked"), "wires checked", "/integrations")),
        K.bp(K.stat(len(findings), "faults found", "/integrations")),
        K.bp(K.stat(n.get("rejected"), "refusing now", "/connectors/health")),
        K.bp(K.stat(n.get("present"), "creds present, unproven",
                    "/connectors/health")),
    )
    fl = []
    for f in findings[:10]:
        fd = _d(f)
        fl.append("<tr><td class='ox-wire'>%s</td><td>%s</td><td>%s</td>"
                  "<td>%s</td></tr>"
                  % (_e(fd.get("wire")), _e(fd.get("kind")),
                     _e(fd.get("what")), _e(fd.get("fix"))))
    faults = ("<div class='ox-tw'><table class='ox-t'><thead><tr><th>Wire</th>"
              "<th>Kind</th><th>What</th><th>Fix</th></tr></thead><tbody>%s"
              "</tbody></table></div>" % "".join(fl)) if fl else \
        "<p class='ox-nodata'>no configuration faults found on this run</p>"
    panel = K.cmdchat(
        "system.integrations", "🔌 Integrations Engineer",
        pending=[{"id": p.get("wire"), "what": p.get("what"),
                  "why": p.get("fix"), "pink": False} for p in props],
        quick=["Re-check every wire now", "Explain the shadowed keys",
               "List wires never verified"],
        context_note="This desk finds faults and proposes fixes. It cannot "
                     "mark a wire verified: only a real accepted call does "
                     "that, which is what keeps the dots honest.")
    return K.screen(
        "13b", "Integrations Desk",
        "Connection health, honest freshness, and the re-authorisations "
        "waiting on you.",
        head + "<div class='ox-ac-sec'><span class='ox-lbl'>Faults found "
               "today</span>" + faults + "</div>"
        + K.connector_table(_l(ctx.get("health"))) + panel,
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


def _unstaffed_screen(sid: str, title: str, sub: str) -> str:
    who, why = UNSTAFFED_DESKS[sid]
    return K.screen(
        sid, title, sub,
        K.bp("<div class='ox-planned'><span class='ox-pl'>Not staffed</span>"
             "<h4>%s</h4><p>%s</p>"
             "<p class='ox-need'>Nothing is shown here because nothing "
             "produces it. A number on this screen would have to be borrowed "
             "from another desk.</p></div>" % (_e(who), _e(why)),
             cls="ox-plan"),
        staffed_by="nobody", badge_kind="notstaffed")


def _s13e(ctx) -> str:
    cards = _cards_for(ctx, "risk")
    body = (K.grid(*[K.agent_card(c) for c in cards]) if cards else
            "<p class='ox-nodata'>the risk desk did not report</p>")
    rk = _d(ctx.get("risk"))
    fs = _l(rk.get("findings"))
    rows = "".join(
        "<li class='%s'>%s <em>%s</em></li>"
        % ("bad" if _d(f).get("severity") == "bad" else "ask",
           _e(_d(f).get("what")), _e(_d(f).get("fix")))
        for f in fs) or "<li class='ok'>nothing outstanding</li>"
    age = rk.get("backup_age_days")
    note = K.bp(
        "<span class='ox-lbl'>Backup posture</span>"
        + K.stat(age, "days since a proven backup", "/risk/posture")
        + "<ul class='ox-rep'>" + rows + "</ul>"
        + ("<p class='ox-sub'>The engine runs in a container with no docker "
           "CLI and no view of the host disk, so it cannot take a backup or "
           "see one. It can only be TOLD, with a timestamp. Install this on "
           "the host once and the proof starts arriving:</p>"
           "<pre style='overflow-x:auto;font-size:.74rem;white-space:pre-wrap;"
           "word-break:break-all'>" + _e(rk.get("host_cron")) + "</pre>"
           if age is None else
           "<p class='ox-sub'>Proof arrives from the host cron. A backup this "
           "engine cannot verify is not counted.</p>"),
        cls="ox-plan" if age is None else "")
    return K.screen(
        "13e", "Infra / SRE Desk",
        "VPS, DNS, SSL, uptime, backups. The sensors report; the lane is "
        "not on the clock yet.",
        K.grid(body, note, cols="two"),
        staffed_by="🩺 Risk Sentinel", badge_kind="inspector")


def _s13f(ctx) -> str:
    co = _d(ctx.get("company"))
    return K.screen(
        "13f", "Orchestrator Desk",
        "Classify, propose, approve, dispatch. This is the engine itself, "
        "not an employee, so it files no daily report.",
        K.grid(
            K.bp("<span class='ox-lbl'>What the machine did</span>"
                 + K.stat(co.get("finished_n"), "steps completed today",
                          "/company/today")
                 + "<p class='ox-sub'>The orchestrator advances jobs, holds "
                   "the gates and folds outcomes into each lane's playbook. "
                   "It is the loop every employee runs inside.</p>"),
            K.bp("<span class='ox-lbl'>The five permanent gates</span>"
                 "<ul class='ox-rep'>"
                 "<li>SPEND</li><li>PUBLISH</li><li>SEND</li>"
                 "<li>DEPLOY</li><li>CROSS-MODULE COMMAND</li></ul>"
                 "<p class='ox-sub'>Autonomy settings may add a gate. No "
                 "code path removes one, and the deploy check fails the "
                 "build if a bypass appears.</p>"),
            cols="two"),
        staffed_by="the engine", badge_kind="")


def _s13g(ctx) -> str:
    cards = _cards_for(ctx, "bi")
    return K.screen(
        "13g", "Analytics",
        "Every source in one place, each number carrying the endpoint that "
        "produced it.",
        (K.grid(*[K.agent_card(c) for c in cards]) if cards else
         "<p class='ox-nodata'>the analytics desk did not report</p>")
        + K.bp("<span class='ox-lbl'>Why there is no insights writer</span>"
               "<p class='ox-sub'>This desk measures and does not produce. "
               "An insights writer that invents a narrative over thin data "
               "is worse than an empty panel, so the badge stays inspector "
               "until a real analysis lane exists.</p>"),
        staffed_by="📊 BI Analyst", badge_kind="inspector")


def _s13h(ctx) -> str:
    rows = []
    for a in _l(ctx.get("roster")):
        ad = _d(a)
        slots = ", ".join(_e(t) for t, _w in _l(ad.get("slots"))) or "none"
        rows.append("<tr><td>%s</td><td class='ox-wire'>%s</td><td>%s</td>"
                    "<td>%s</td><td>%s</td></tr>"
                    % (_e(ad.get("name")), _e(ad.get("id")),
                       K.badge(_e(ad.get("badge"))), slots,
                       _e(ad.get("cap_key"))))
    return K.screen(
        "13h", "Sources + Staff Control Room",
        "Who may touch which wire, and under which cap. This table governs "
        "every command panel in the OS.",
        "<div class='ox-tw'><table class='ox-t'><thead><tr><th>Employee</th>"
        "<th>Id</th><th>Staffing</th><th>Named tools</th><th>Cap key</th>"
        "</tr></thead><tbody>%s</tbody></table></div>" % "".join(rows)
        + K.bp("<span class='ox-lbl'>Rule</span><p class='ox-sub'>An employee "
               "may only touch the wires named on its own row. A command sent "
               "from any panel is scoped to that one desk, which is why the "
               "panel header names it.</p>"),
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


def _s13i(ctx) -> str:
    """Tool Connection Hub.

    KEYED BY ENV KEY, NOT BY WIRE. The first draft keyed each input by the
    wire name, which POST /connect does not accept: it takes allow-listed
    credential keys. A wire is not a key, and there is no map between them
    in the engine because presence is computed per adapter. Rather than
    hand-write a thirty-row mapping that must agree with ninety-three keys
    (the bug class this project keeps meeting), the hub asks for exactly
    what the endpoint accepts, grouped by the provider prefix it already
    carries in its own name.

    PRESENCE ONLY: no credential value is ever rendered, and the engine
    never returns one."""
    try:
        import content_engine_connectors as CN
        keys = sorted(CN.CONNECTOR_ENV_KEYS)
    except Exception:                                     # noqa: BLE001
        keys = []
    groups: Dict[str, List[str]] = {}
    for k in keys:
        groups.setdefault(str(k).split("_")[0].upper(), []).append(str(k))
    blocks = []
    for g, ks in sorted(groups.items()):
        rows = "".join(
            "<tr><td class='ox-wire'>%s</td>"
            "<td><input class='ox-in' type='password' autocomplete='off' "
            "placeholder='paste to set or replace' id='oskey-%s'></td>"
            "<td><button type='button' class='ox-btn' "
            "onclick=\"osSaveKey('%s')\">Save</button></td></tr>"
            % (_e(k), _e(k), _e(k)) for k in ks)
        blocks.append(K.bp(
            "<span class='ox-lbl'>%s</span>"
            "<div class='ox-tw'><table class='ox-t'><thead><tr>"
            "<th>Credential key</th><th>Value</th><th></th></tr></thead>"
            "<tbody>%s</tbody></table></div>" % (_e(g), rows)))
    return K.screen(
        "13i", "Tool Connection Hub",
        "Plug-and-play credentials. The engine stores keys and never reads "
        "one back, so this screen can only ever tell you whether the wire "
        "it feeds went green.",
        K.bp("<span class='ox-lbl'>Why a saved key is still amber</span>"
             "<p class='ox-sub'>Saving a credential proves only that you "
             "typed something. The dot turns green when the provider accepts "
             "a real call and the engine holds the timestamp. Creds-present "
             "is amber on purpose, and it is the whole reason this OS can "
             "be trusted about what is connected.</p>"
             + K.source_chip("POST /connect"))
        + K.connector_table(_l(ctx.get("health")))
        + K.grid(*blocks),
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


def _s13j(ctx) -> str:
    pulse = []
    for c in _l(ctx.get("cards")):
        cd = _d(c)
        rep = _d(cd.get("report"))
        bad = len(_l(rep.get("couldnt")))
        state = ("down" if bad else
                 ("warn" if cd.get("badge") in ("inspector", "architected",
                                                "notstaffed") else "ok"))
        icon = {"ok": "●", "warn": "◐", "down": "✕"}[state]
        cls = {"ok": "verified", "warn": "present", "down": "rejected"}[state]
        pulse.append("<tr><td>%s</td><td>%s</td>"
                     "<td><span class='ox-dot ox-s-%s'><b>%s</b>%s</span></td>"
                     "<td>%d</td><td>%d</td></tr>"
                     % (_e(cd.get("name")), K.badge(_e(cd.get("badge"))),
                        cls, icon, state, len(_l(rep.get("finished"))), bad))
    return K.screen(
        "13j", "Health & Risk Monitor",
        "A pulse per employee, computed from what it actually reported today, "
        "not from a label someone typed.",
        "<div class='ox-tw'><table class='ox-t'><thead><tr><th>Employee</th>"
        "<th>Staffing</th><th>Pulse</th><th>Finished</th><th>Couldn't</th>"
        "</tr></thead><tbody>%s</tbody></table></div>" % "".join(pulse)
        + K.bp("<span class='ox-lbl'>How the pulse is derived</span>"
               "<p class='ox-sub'>A desk reads down when it recorded a "
               "failure today, warns when it is not a live lane, and reads "
               "ok only when it is live and nothing failed. No pulse on this "
               "screen is hand-set.</p>"),
        staffed_by="🩺 Risk Sentinel", badge_kind="inspector")


def _s13k(ctx) -> str:
    by_group: Dict[str, List[dict]] = {}
    for r in _l(ctx.get("health")):
        by_group.setdefault(str(_d(r).get("group") or "other"), []).append(_d(r))
    blocks = []
    for g, rows in sorted(by_group.items()):
        blocks.append(K.bp(
            "<span class='ox-lbl'>%s</span>" % _e(g)
            + "<div class='ox-slots'>%s</div>" % "".join(
                "<span class='ox-slot ox-s-%s' title='%s'><b>%s</b>%s</span>"
                % (_e(r.get("status")), _e(r.get("reason") or ""),
                   K.STATUS_LABEL.get(str(r.get("status")),
                                      K.STATUS_LABEL["empty"])[0],
                   _e(r.get("wire"))) for r in rows)))
    return K.screen(
        "13k", "Connector / API Map",
        "Every tool, grouped by provider, with the department it feeds.",
        K.grid(*blocks) + K.connector_table(_l(ctx.get("health"))),
        staffed_by="🔌 Integrations Engineer", badge_kind="live")


# ==========================================================================
# TURN 14 - THE COCKPIT
# ==========================================================================
def _s14a(ctx) -> str:
    co = _d(ctx.get("company"))
    staffing = {_d(s).get("module"): _d(s) for s in _l(ctx.get("staffing"))}
    cards = []
    for mid, label, mod in MODULES:
        st = staffing.get(mod) or {}
        mcards = _cards_for(ctx, mod)
        fin = sum(len(_l(_d(c.get("report")).get("finished"))) for c in mcards)
        ned = sum(len(_l(_d(c.get("report")).get("needs"))) for c in mcards)
        cards.append(K.bp(
            "<div class='ox-ac-head'><h4>%s</h4>%s</div>"
            "<div class='ox-chips'><span class='ox-chip ok'>%d finished</span>"
            "<span class='ox-chip ask'>%d need you</span>"
            "<span class='ox-chip'>%d staff</span></div>"
            "<p class='ox-sub'>%s</p>%s"
            % (_e(label), K.badge(_e(st.get("badge") or "notstaffed"),
                                  _e(st.get("why") or "")),
               fin, ned, len(mcards), _e(st.get("why") or ""),
               K.source_chip("/agents"))))
    top = K.grid(
        K.bp(K.stat(co.get("finished_n"), "finished across the company",
                    "/company/today")),
        K.bp(K.stat(co.get("couldnt_n"), "couldn't", "/company/today")),
        K.bp(K.stat(co.get("need_n"), "need your decision", "/company/today")),
        K.bp(K.stat(len(_l(ctx.get("roster"))), "employees", "/agents")),
    )
    panel = K.cmdchat(
        "cockpit", "🧭 Orchestrator",
        quick=["Pause everything", "What needs me right now?",
               "Which wires are refusing?"],
        context_note="A command here becomes a proposal for you to approve. "
                     "The cockpit never executes a gated action directly.")
    return K.screen(
        "14a", "Cockpit Home",
        "All six modules at a glance, and today across the whole company.",
        top + K.grid(*cards) + panel,
        staffed_by="you", badge_kind="")


def _s14b(ctx) -> str:
    """The unified queue. DECISION AND BLOCKED ARE NEVER MERGED: a broken
    tool counted as a pending approval hides an outage inside a to-do list."""
    decisions, blocked = [], []
    for c in _l(ctx.get("cards")):
        cd = _d(c)
        for n in _l(_d(cd.get("report")).get("needs")):
            nd = _d(n)
            nd["_who"] = cd.get("name")
            (decisions if nd.get("kind") == "decision" else blocked).append(nd)

    # PINK ITEMS JOIN THE DECISION LIST, flagged. A price change that
    # never appears in the cockpit is a proposal nobody sees, and the
    # whole point of one queue is that nothing waits somewhere else.
    for pp in _l(ctx.get("price_proposals")):
        pd = _d(pp)
        pv = _d(pd.get("preview"))
        detail = ("margin %s%% to %s%%" % (pv.get("margin_before_pct"),
                                           pv.get("margin_after_pct"))
                  if pv.get("margin_known") else _e(pv.get("margin_note")))
        decisions.append({
            "_who": "📦 Commerce Analyst", "kind": "decision", "_pink": True,
            "what": "price %s: %s to %s" % (_e(pd.get("title"))[:40],
                                            pd.get("price"),
                                            pd.get("new_price")),
            "why": "%s. %s" % (_e(pd.get("why")), detail),
            "action": "/commerce/price/%s/approve" % _e(pd.get("id"))})

    def _tbl(items, empty):
        if not items:
            return "<p class='ox-nodata'>%s</p>" % _e(empty)
        return ("<div class='ox-tw'><table class='ox-t'><thead><tr>"
                "<th>From</th><th>What</th><th>Why</th><th>Where</th>"
                "</tr></thead><tbody>%s</tbody></table></div>"
                % "".join("<tr><td>%s</td><td>%s%s</td><td>%s</td>"
                          "<td class='ox-wire'>%s</td></tr>"
                          % (_e(i.get("_who")),
                             ("<span class='ox-pink'>pink: never batch</span> "
                              if i.get("_pink") else ""),
                             _e(i.get("what")), _e(i.get("why")),
                             _e(i.get("action")))
                          for i in items))
    return K.screen(
        "14b", "Unified Approval Queue",
        "Every module's pending decisions in one inbox, split from the "
        "things that are simply broken.",
        K.grid(
            K.bp("<span class='ox-lbl'>🙋 Your decision (%d)</span>%s"
                 % (len(decisions), _tbl(decisions, "nothing waiting on you"))),
            K.bp("<span class='ox-lbl'>⛔ Blocked, not yours to approve (%d)"
                 "</span>%s"
                 % (len(blocked), _tbl(blocked, "no tool is refusing"))),
            cols="two")
        + K.bp("<span class='ox-lbl'>Why these two lists never merge</span>"
               "<p class='ox-sub'>A refusing connector is not a pending "
               "approval. Counting it as one is how an outage sits quietly "
               "in an approval list for a week while you assume someone "
               "will click it.</p>"),
        staffed_by="you", badge_kind="")


def _s14c(ctx) -> str:
    cards = _l(ctx.get("cards"))
    live = sum(1 for c in cards if _d(c).get("badge") == "live")
    head = K.grid(
        K.bp(K.stat(len(cards), "employees on the roster", "/agents")),
        K.bp(K.stat(live, "live lanes", "/agents")),
        K.bp(K.stat(28, "desks in the OS", "roster mapping")),
    )
    return K.screen(
        "14c", "All-Agents Grid",
        "Every employee across all six modules. Eighteen workers cover "
        "twenty-eight desks, because a desk is a view of a lane.",
        head + K.grid(*[K.agent_card(c) for c in cards]),
        staffed_by="you", badge_kind="")


def _s14d(ctx) -> str:
    co = _d(ctx.get("company"))
    n = _counts(ctx)
    causes = _l(co.get("top_causes"))
    log = []
    for c in _l(ctx.get("cards")):
        cd = _d(c)
        for f in _l(_d(cd.get("report")).get("finished"))[:2]:
            log.append("<tr><td>%s</td><td>%s</td><td>finished</td></tr>"
                       % (_e(cd.get("name")), _e(_d(f).get("what"))))
        for f in _l(_d(cd.get("report")).get("couldnt"))[:2]:
            log.append("<tr><td>%s</td><td>%s</td>"
                       "<td class='ox-warn'>%s</td></tr>"
                       % (_e(cd.get("name")), _e(_d(f).get("what")),
                          _e(_d(f).get("cause"))))
    return K.screen(
        "14d", "System Health & Activity",
        "One truthful status view, and the audit log underneath it.",
        K.grid(
            K.bp(K.stat(n.get("verified"), "verified", "/connectors/health")),
            K.bp(K.stat(n.get("present"), "present, unproven",
                        "/connectors/health")),
            K.bp(K.stat(n.get("rejected"), "refusing", "/connectors/health")),
            K.bp(K.stat(n.get("empty"), "no credential",
                        "/connectors/health")))
        + K.bp("<span class='ox-lbl'>Top causes of stopped work</span>"
               + ("<ul class='ox-rep'>%s</ul>"
                  % "".join("<li class='bad'>%s</li>" % _e(x)
                            for x in causes[:5])
                  if causes else
                  "<p class='ox-nodata'>nothing failed today</p>"))
        + ("<div class='ox-tw'><table class='ox-t'><thead><tr><th>Employee"
           "</th><th>Work</th><th>Outcome</th></tr></thead><tbody>%s</tbody>"
           "</table></div>" % "".join(log[:40]) if log else
           "<p class='ox-nodata'>no activity recorded today</p>"),
        staffed_by="you", badge_kind="")


def _s14e(ctx) -> str:
    gates = ["SPEND", "PUBLISH", "SEND", "DEPLOY", "CROSS-MODULE COMMAND"]
    return K.screen(
        "14e", "System Control Room",
        "The global rules that govern every module.",
        K.grid(
            K.bp("<span class='ox-lbl'>The five permanent gates</span>"
                 + "<div class='ox-slots'>%s</div>" % "".join(
                     "<span class='ox-slot ox-s-verified'><b>●</b>%s</span>"
                     % _e(g) for g in gates)
                 + "<p class='ox-sub'>Always on. An autonomy setting may add "
                   "a gate and can never remove one. There is no switch on "
                   "this screen for these, by design.</p>"),
            K.bp("<span class='ox-lbl'>Autonomy default</span>"
                 "<p class='ox-sub'>Propose and wait for approval. Employees "
                 "draft; you say go. Raising autonomy can only widen what "
                 "runs automatically inside the low-stakes band, never past "
                 "a gate.</p>" + K.source_chip("/control/autonomy")),
            cols="two")
        + K.bp("<span class='ox-lbl'>Budget</span>"
               "<p class='ox-sub'>Per-job and per-day caps are enforced in "
               "the orchestrator. A lane that hits its cap parks the job and "
               "reports it as couldn't, with the cap named. Silence would be "
               "the failure mode; a parked job that says why is not.</p>"
               + K.source_chip("/budget")),
        staffed_by="you", badge_kind="")


# ==========================================================================
# ASSEMBLY
# ==========================================================================
SCREENS_13 = ("13a", "13b", "13c", "13d", "13e", "13f", "13g", "13h", "13i",
              "13j", "13k")
SCREENS_14 = ("14a", "14b", "14c", "14d", "14e")


def core_section(ctx: Dict[str, Any]) -> str:
    """6 · Web & Data Core, in the shell his wireframe uses.

    Sidebar of modules, this module's screens as a subnav
    nested under it, and the screens stacked in main. His own
    subnav links are anchors, so stacking is how his prototype
    navigates rather than a shortcut.
    """
    import content_engine_agentos_hub as HUB
    ctx = _d(ctx)
    body = (_s13a(ctx) + _s13b(ctx)
            + _unstaffed_screen("13c", "Data Steward Desk",
                                "Schema, mapping, quality, distribution.")
            + _unstaffed_screen("13d", "Developer Desk",
                                "Command to work to gated deploy.")
            + _s13e(ctx) + _s13f(ctx) + _s13g(ctx) + _s13h(ctx)
            + _s13i(ctx) + _s13j(ctx) + _s13k(ctx)
            # HIS FINAL REVISION: 16a and 16b join this module.
            + HUB.core_extra(ctx))
    return ("<div class='osx'>"
            + K.frame('6 · Web & Data Core', SUBNAV_CORE, body)
            + "</div>")



def cockpit_section(ctx: Dict[str, Any]) -> str:
    """Cockpit, in the shell his wireframe uses.

    Sidebar of modules, this module's screens as a subnav
    nested under it, and the screens stacked in main. His own
    subnav links are anchors, so stacking is how his prototype
    navigates rather than a shortcut.
    """
    ctx = _d(ctx)
    body = (_s14a(ctx) + _s14b(ctx) + _s14c(ctx) + _s14d(ctx) + _s14e(ctx))
    return ("<div class='osx'>"
            + K.frame('Cockpit', SUBNAV_COCKPIT, body)
            + "</div>")



def check(ctx: Dict[str, Any] = None) -> Dict[str, Any]:
    """Every declared screen must actually render, and carry its id."""
    ctx = _d(ctx)
    problems = []
    html = core_section(ctx) + cockpit_section(ctx)
    for sid in SCREENS_13 + SCREENS_14:
        if ("id='os-%s'" % sid) not in html:
            problems.append("screen %s declared but not rendered" % sid)
        if html.count("id='os-%s'" % sid) > 1:
            problems.append("screen %s rendered twice" % sid)
    return {"ok": not problems, "problems": problems,
            "screens": len(SCREENS_13) + len(SCREENS_14), "chars": len(html)}


if __name__ == "__main__":
    r = check({})
    assert r["ok"], r["problems"]
    print("screens:", r["screens"], "chars:", r["chars"])
