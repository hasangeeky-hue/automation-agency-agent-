# -*- coding: utf-8 -*-
"""THE AGENT OS KIT: the five components every wireframe screen composes from.

Section 10.1 is explicit: extend the server-rendered kit, do not introduce a
second UI system. So this module adds the wireframe's Industry design system
and its five reusable objects, and every screen in the OS is built from them.

WHY THE TOKENS ARE DEFINED ON .osx AND NEVER READ FROM THE HOST SHELL
--------------------------------------------------------------------
The last redesign lost a day to var() indirection: a rule written as
var(--s1,#f8fafc) inside the old dark shell resolved to the DARK value,
because --s1 existed. The fallback never fired. So the OS declares its own
prefixed properties on its own root element and reads only those. Nothing
here inherits a colour from whatever section it is dropped into.

THE FIVE COMPONENTS (build once, reuse on all 54 screens)
  bp()            the blueprint object: square, hairline, 4 registration marks
  badge()         the staffing badge, from the roster, never hand-set
  agent_card()    the acv2 card: today's report + what it learned + tool slots
  connector_row() one wire in the registry, in the four honest states
  cmdchat()       the command panel, scoped to exactly one agent

HONESTY RULES THAT LIVE IN THE COMPONENTS, NOT IN THE SCREENS
  - a number renders with the endpoint that produced it (source chip)
  - status is icon AND word, never colour alone
  - absence renders as "no source", never as zero
  - a pink action carries the gate that holds it, and cannot batch-approve
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import content_engine_contracts as C

# --------------------------------------------------------------------------
# the badge vocabulary. one definition, shared by every screen and the gate.
# --------------------------------------------------------------------------
BADGE_LABEL = {
    "live": ("●", "Live lane"),
    "inspector": ("◐", "Inspector only"),
    "architected": ("○", "Architected"),
    "notstaffed": ("▢", "Not staffed"),
}
STATUS_LABEL = {
    "verified": ("●", "Verified"),
    "present": ("◐", "Creds present"),
    "rejected": ("✕", "Refusing"),
    "empty": ("○", "No credential"),
}


def _e(v: Any) -> str:
    return (str("" if v is None else v)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _l(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else []


def _d(v) -> dict:
    return dict(v) if isinstance(v, dict) else {}


# ==========================================================================
# 1. THE BLUEPRINT OBJECT
# ==========================================================================
def bp(inner: str, *, cls: str = "", ident: str = "") -> str:
    """A square, hairline-bordered card with four corner registration marks.
    The DS calls these blueprint objects and they are the only card shape in
    the OS: rounding anything here would put a second visual language back."""
    i = (" id='%s'" % _e(ident)) if ident else ""
    return ("<div class='ox-bp %s'%s>"
            "<i class='ox-c tl'></i><i class='ox-c tr'></i>"
            "<i class='ox-c bl'></i><i class='ox-c br'></i>"
            "%s</div>" % (_e(cls), i, inner))


# ==========================================================================
# 2. THE STAFFING BADGE
# ==========================================================================
def badge(kind: str, why: str = "") -> str:
    """Never hand-set in a screen (rule 0.3). It comes from the roster, and
    the roster's badge is the truth about the code behind the desk."""
    k = str(kind or "notstaffed")
    if k not in BADGE_LABEL:
        raise ValueError("unknown staffing badge %r; the four are %s"
                         % (k, ", ".join(BADGE_LABEL)))
    icon, word = BADGE_LABEL[k]
    t = (" title='%s'" % _e(why)) if why else ""
    return ("<span class='ox-badge ox-b-%s'%s><b>%s</b>%s</span>"
            % (k, t, icon, _e(word)))


def source_chip(endpoint: str) -> str:
    """Every hero number says where it came from. A number with no source is
    the oldest lie a dashboard tells."""
    if not endpoint:
        return "<span class='ox-src ox-src-none'>no source</span>"
    return "<span class='ox-src'>%s</span>" % _e(endpoint)


def stat(value: Any, label: str, endpoint: str = "", *, unit: str = "") -> str:
    """A hero number. ABSENCE IS NOT ZERO: None renders as 'no data', because
    a zero invites a decision and a blank tells the truth."""
    if value is None:
        v = "<span class='ox-nodata'>no data</span>"
    else:
        v = _e(value) + (("<span class='ox-unit'>%s</span>" % _e(unit))
                         if unit else "")
    return ("<div class='ox-stat'><div class='ox-stat-n'>%s</div>"
            "<div class='ox-stat-l'>%s</div>%s</div>"
            % (v, _e(label), source_chip(endpoint)))


# ==========================================================================
# 3. THE ACV2 AGENT CARD  (the doctrine's Difference 4, rendered)
# ==========================================================================
def agent_card(card: Dict[str, Any], *, compact: bool = False) -> str:
    """Renders one AGENT_CARD from the contract. Nothing here is invented:
    every field is read from /agents, which merges roster + health + report
    + playbook."""
    c = _d(card)
    rep = _d(c.get("report"))
    slots = _l(c.get("slots"))
    learned = _l(c.get("learned"))

    head = ("<div class='ox-ac-head'><div><h4>%s</h4>"
            "<div class='ox-ac-id'>%s</div></div>%s</div>"
            % (_e(c.get("name")), _e(c.get("id")),
               badge(_e(c.get("badge") or "notstaffed"),
                     _e(c.get("why") or ""))))

    # ---- TODAY'S REPORT: finished / couldn't / need you -------------------
    fin, cno, need = (_l(rep.get("finished")), _l(rep.get("couldnt")),
                      _l(rep.get("needs")))
    chips = ("<div class='ox-chips'>"
             "<span class='ox-chip ok'>%d finished</span>"
             "<span class='ox-chip bad'>%d couldn't</span>"
             "<span class='ox-chip ask'>%d need you</span></div>"
             % (len(fin), len(cno), len(need)))
    lines = []
    for f in fin[:3]:
        lines.append("<li class='ok'>%s</li>" % _e(_d(f).get("what")))
    for f in cno[:3]:
        # A FAILURE ALWAYS CARRIES ITS CAUSE. The engine guarantees it.
        lines.append("<li class='bad'>%s <em>%s</em></li>"
                     % (_e(_d(f).get("what")),
                        _e(_d(f).get("cause") or "no reason recorded")))
    for n in need[:3]:
        nd = _d(n)
        kind = _e(nd.get("kind"))
        lines.append("<li class='%s'>%s %s <em>%s</em></li>"
                     % ("ask" if kind == "decision" else "blocked",
                        "🙋" if kind == "decision" else "⛔",
                        _e(nd.get("what")), _e(nd.get("why"))))
    if not lines:
        lines.append("<li class='quiet'>nothing recorded today</li>")
    report = ("<div class='ox-ac-sec'><span class='ox-lbl'>Today's report</span>"
              "%s<ul class='ox-rep'>%s</ul></div>" % (chips, "".join(lines)))

    # ---- WHAT I'VE LEARNED ----------------------------------------------
    lrn = ("<div class='ox-ac-sec'><span class='ox-lbl'>What I've learned</span>"
           "<ul class='ox-learn'>%s</ul></div>"
           % "".join("<li>%s</li>" % _e(x) for x in (learned[:3] or
                                                     ["still learning"])))

    # ---- NAMED TOOL SLOTS with live status dots -------------------------
    sl = []
    for s in slots:
        sd = _d(s)
        st = str(sd.get("status") or "empty")
        icon, word = STATUS_LABEL.get(st, STATUS_LABEL["empty"])
        why = _e(sd.get("reason") or word)
        sl.append("<span class='ox-slot ox-s-%s' title='%s'><b>%s</b>%s</span>"
                  % (_e(st), why, icon, _e(sd.get("tool") or sd.get("wire"))))
    tools = ("<div class='ox-ac-sec'><span class='ox-lbl'>Tools</span>"
             "<div class='ox-slots'>%s</div></div>"
             % ("".join(sl) or "<span class='ox-nodata'>no tools assigned</span>"))

    cap = ""
    if c.get("cap_usd") is not None:
        cap = ("<div class='ox-ac-cap'>cap <b>%s</b> &middot; used <b>%s</b>"
               "%s</div>" % (_e(c.get("cap_usd")), _e(c.get("used_usd")),
                             source_chip("/agents")))
    body = head + report + ("" if compact else lrn + tools) + cap
    return bp(body, cls="ox-ac")


# ==========================================================================
# 4. THE CONNECTOR REGISTRY ROW
# ==========================================================================
def connector_row(h: Dict[str, Any]) -> str:
    """One wire, in the four honest states. Green is impossible here without
    a timestamp, because the contract refuses to construct that row at all."""
    r = _d(h)
    st = str(r.get("status") or "empty")
    icon, word = STATUS_LABEL.get(st, STATUS_LABEL["empty"])
    when = _e(r.get("last_verified") or "")
    note = []
    if r.get("aliased_from"):
        note.append("running on %s, not its own key" % _e(r["aliased_from"]))
    if r.get("shadowed"):
        note.append("saved value is NOT the one in use")
    return ("<tr>"
            "<td class='ox-wire'>%s</td>"
            "<td><span class='ox-dot ox-s-%s'><b>%s</b>%s</span></td>"
            "<td>%s</td>"
            "<td>%s</td>"
            "<td>%s</td></tr>"
            % (_e(r.get("wire")), _e(st), icon, _e(word),
               (when[:16].replace("T", " ") if st == "verified"
                else "<span class='ox-nodata'>never</span>"),
               _e(r.get("reason") or ""),
               ("<span class='ox-warn'>%s</span>" % "; ".join(note))
               if note else ", ".join(_e(x) for x in _l(r.get("feeds")))))


def connector_table(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ("<p class='ox-nodata'>the health store returned nothing, so "
                "this table is empty rather than green</p>")
    return ("<div class='ox-tw'><table class='ox-t'><thead><tr>"
            "<th>Wire</th><th>State</th><th>Last verified</th>"
            "<th>Reason</th><th>Feeds / note</th></tr></thead><tbody>"
            + "".join(connector_row(r) for r in rows)
            + "</tbody></table></div>")


# ==========================================================================
# 5. THE COMMAND PANEL  (Section 10.4 scope, deliberately not a chat agent)
# ==========================================================================
def cmdchat(agent_id: str, agent_name: str, *,
            pending: Optional[Sequence[Dict[str, Any]]] = None,
            quick: Optional[Sequence[str]] = None,
            context_note: str = "") -> str:
    """v1 exactly as scoped: the bar sanitises input, creates a PROPOSAL, and
    acknowledges. There is no conversational loop and no transcript store.

    The header names ONE agent so a command cannot leak to the wrong desk,
    and approving a pink item here still hits that module's own confirm gate
    (the prototype short-circuits that; production must not)."""
    items = []
    for p in _l(pending):
        pd = _d(p)
        pink = bool(pd.get("pink"))
        items.append(
            "<li class='ox-pa%s'><div class='ox-pa-w'>%s</div>"
            "<div class='ox-pa-y'>%s</div><div class='ox-pa-b'>"
            "<button type='button' class='ox-btn ox-btn-p' "
            "onclick=\"osApprove('%s','%s',%s)\">Approve</button>"
            "<button type='button' class='ox-btn' "
            "onclick=\"osReject('%s','%s')\">Reject</button>%s</div></li>"
            % (" pink" if pink else "", _e(pd.get("what")),
               _e(pd.get("why") or pd.get("cause") or ""),
               _e(agent_id), _e(pd.get("id") or pd.get("what")),
               "true" if pink else "false",
               _e(agent_id), _e(pd.get("id") or pd.get("what")),
               ("<span class='ox-pink'>spend gate: never batch</span>"
                if pink else "")))
    plist = ("<ul class='ox-pas'>%s</ul>" % "".join(items)) if items else \
        "<p class='ox-nodata'>nothing waiting on you at this desk</p>"

    qs = "".join(
        "<button type='button' class='ox-q' onclick=\"osPrefill('%s',this)\">"
        "%s</button>" % (_e(agent_id), _e(q)) for q in _l(quick))

    return bp(
        "<div class='ox-cc-h'><span class='ox-lbl'>Command</span>"
        "<h4>%s</h4><span class='ox-cc-scope'>commands reach this desk only"
        "</span></div>"
        "%s"
        "<div class='ox-cc-sec'><span class='ox-lbl'>Waiting on you</span>%s</div>"
        "<div class='ox-cc-sec'><span class='ox-lbl'>Quick actions</span>"
        "<div class='ox-qs'>%s</div></div>"
        "<div class='ox-cc-bar'>"
        "<input class='ox-in' id='oscmd-%s' type='text' "
        "placeholder='Tell %s what to do. It becomes a proposal, not an action.' "
        "onkeydown=\"if(event.key==='Enter')osSend('%s')\">"
        "<button type='button' class='ox-btn ox-btn-p' "
        "onclick=\"osSend('%s')\">Send</button></div>"
        "<p class='ox-cc-ack' id='osack-%s'></p>"
        % (_e(agent_name),
           ("<p class='ox-cc-note'>%s</p>" % _e(context_note))
           if context_note else "",
           plist, qs or "<span class='ox-nodata'>none</span>",
           _e(agent_id), _e(agent_name), _e(agent_id), _e(agent_id),
           _e(agent_id)),
        cls="ox-cc")


# ==========================================================================
# THE MODULE SHELL. His structure, not a simplification of it.
# ==========================================================================
#: the sidebar, in his order and his labels, with the anchor each opens
MODULES = (
    ("1 · Media Buyer", "7a"),
    ("2 · SEO / AEO / GEO", "8a"),
    ("3 · Marketing / Content", "9a"),
    ("4 · Commerce", "11a"),
    ("5 · Leads & Outreach", "12a"),
    ("6 · Web & Data Core", "13a"),
    ("Cockpit", "14a"),
)

#: EACH MODULE IS A PAGE, NOT AN ANCHOR ON THIS ONE.
#
# The sidebar linked every module as href='#os-7a', which is what his
# prototype does, because in his prototype all 51 screens live on one
# scrolling document. Here each department is its own dashboard page and
# the other six are display:none, so those links jumped to an anchor
# inside a hidden page and did nothing at all. The founder reported it
# exactly: "except cockpit nothing are opening". Cockpit worked only
# because it is the page that is already open.
#
# Copying a prototype's navigation into a different document model is
# how a link that is correct in the source becomes dead in the product.
#: HIS TOPBAR IS THE ONLY TOPBAR. The dashboard used to wrap this shell in
# its own brand bar, window pills, engine buttons and banners, so his
# design rendered INSIDE the old one and the frame he looked at every day
# never changed. That is what "still old system are there" meant. The
# dashboard now hands its live bits in here and renders no chrome of its
# own: one shell, and it is his.
CHROME = {"cost": "", "alerts": "", "right": ""}


def set_chrome(*, cost: str = "", alerts: str = "", right: str = "") -> None:
    """What the host page wants shown in HIS topbar, not around it."""
    CHROME["cost"], CHROME["alerts"], CHROME["right"] = cost, alerts, right


MODULE_PAGE = {
    "7a": "osmedia", "8a": "osseo", "9a": "osmkt", "11a": "oscom",
    "12a": "osleads", "13a": "oscore", "14a": "oscockpit",
}


def frame(module_label: str, subnav: Sequence, body: str, *,
          cost: str = "", alerts: str = "") -> str:
    """One department, in the shell his wireframe actually uses.

    subnav is [(label, screen_id)], rendered INSIDE the sidebar under the
    active module, exactly as his markup nests it. The links are anchors
    because that is how his own prototype moves between screens."""
    mods = []
    for label, first in MODULES:
        on = " on" if _e(label) == _e(module_label) else ""
        # Switch PAGE, then fall back to the anchor if nav() is not there
        # (the kit is also rendered in gates and previews outside the
        # dashboard, where nav does not exist).
        page = MODULE_PAGE.get(first, "")
        jump = ("onclick=\"if(typeof nav==='function')return nav('%s');\" "
                % _e(page)) if page else ""
        mods.append("<a class='ox-mod%s' %shref='#%s'>%s</a>"
                    % (on, jump, _e(page or ("os-" + first)), _e(label)))
        if on:
            # A SUBNAV LINK MUST SCROLL, NOT NAVIGATE.
            #
            # These were bare anchors to #os-8a. Changing the hash fires
            # the dashboard's routeFromHash, which calls nav('os-8a');
            # no PAGE has that id, so the fallback sent every subnav
            # click to the Cockpit. He described it exactly: "when
            # clicking sub button its stuck there, does not take me to
            # the right card". osGo scrolls to the screen inside the
            # page that is already open and returns false, so the hash
            # never changes and the router never runs.
            subs = "".join(
                "<a class='ox-snav%s' href='#os-%s' "
                "onclick=\"return osGo('%s')\">%s</a>"
                % (" on" if i == 0 else "", _e(sid), _e(sid), _e(lab))
                for i, (lab, sid) in enumerate(_l(subnav)))
            mods.append("<div class='ox-subnav'>%s</div>" % subs)
    # The host page hands its live bits in here rather than drawing a
    # second bar around this one. right= is raw HTML on purpose: it
    # carries the engine controls and the sign-out link, which are real
    # markup, not text.
    # A MARKER, NOT A READ. CHROME used to be read here, and the host
    # computes its controls AFTER the sections are rendered, so a fresh
    # process produced an empty topbar and a gate that failed for a
    # reason that had nothing to do with the topbar. The host substitutes
    # these once, at the end, when everything it needs exists.
    _cost = _e(cost) or "{{OX_COST}}"
    _al = _e(alerts) or "{{OX_ALERTS}}"
    # HIS LOGO, from the old OS. The wireframe's ◆ glyph was a placeholder;
    # the mark the old dashboard already served is the brand. The glyph
    # stays as the fallback painted by onerror, so a box with no internet
    # still shows a brand instead of a broken-image icon.
    _logo = ("<img class='ox-logo' alt='Anthropos' "
             "src='https://anthropos-automation.com/wp-content/uploads/"
             "2026/07/cropped-anthropos-logo-mark-transparent-1024-270x270"
             ".png' onerror=\"this.replaceWith('\\u25c6')\">")
    return ("<div class='ox-topbar'><span class='ox-brand'>" + _logo
            + " Mother OS</span>"
            "<span class='ox-cost'>%s</span><span>%s</span>"
            "<span class='ox-tools'>%s</span></div>"
            "<div class='ox-frame'>"
            "<div class='ox-sidebar'><div class='ox-modgroup'>Modules</div>"
            "%s</div>"
            "<div class='ox-main'>%s</div></div>"
            % (_cost, _al, "{{OX_TOOLS}}", "".join(mods), body))


def crumb(module_label: str, screen_label: str) -> str:
    """His breadcrumb: module, then the screen, in bold."""
    return ("<div class='ox-crumb'>%s <span>&#9656;</span> <b>%s</b></div>"
            % (_e(module_label), _e(screen_label)))


def dq(rec: str, evidence: str = "", *, action: str = "",
       href: str = "", pink: bool = False) -> str:
    """The decision card: a recommendation, the evidence under it, and
    what you can do about it. Fifty-one of these in his file; it is the
    unit his whole decision surface is made from.

    EVIDENCE IS NOT OPTIONAL IN SPIRIT. A recommendation with nothing
    under it is an opinion, and his own cards always carry the line that
    justifies them."""
    act = ""
    if action:
        act = ("<div class='ox-dq-actions'><a href='%s'>"
               "<button type='button' class='ox-btn%s'>%s</button></a></div>"
               % (_e(href or "#"), " ox-btn-p" if pink else "", _e(action)))
    return ("<div class='ox-dq%s'><div class='ox-dq-main'>"
            "<div class='ox-dq-rec'>%s</div>"
            "<div class='ox-dq-ev'>%s</div></div>%s</div>"
            % (" pink" if pink else "", _e(rec),
               _e(evidence) or "<span class='ox-nodata'>no evidence "
                               "recorded, which is itself worth knowing"
                               "</span>", act))


def chart(title: str, rows: Sequence, *, source: str = "") -> str:
    """A titled panel of horizontal bars, his chart-card + hbar-row.

    rows is [(label, value, max)] or [(label, value)]. A row whose value
    is None renders as a GAP, never as a zero-length bar: an unmeasured
    week and a week of nothing are different facts and a bar chart is
    where they are most easily confused."""
    rs = _l(rows)
    nums = [r[1] for r in rs if len(r) > 1 and isinstance(r[1], (int, float))]
    top = max(nums) if nums else 0
    out = []
    for r in rs:
        lab = r[0] if r else ""
        val = r[1] if len(r) > 1 else None
        mx = r[2] if len(r) > 2 else top
        if val is None:
            out.append("<div class='ox-hbar'><span class='ox-hbar-l'>%s</span>"
                       "<span class='ox-nodata'>not measured</span></div>"
                       % _e(lab))
            continue
        pct = 0
        try:
            pct = max(0, min(100, (float(val) / float(mx or 1)) * 100))
        except Exception:                                 # noqa: BLE001
            pct = 0
        out.append("<div class='ox-hbar'><span class='ox-hbar-l'>%s</span>"
                   "<span class='ox-hbar-t'><i style='width:%.1f%%'></i>"
                   "</span><b>%s</b></div>" % (_e(lab), pct, _e(val)))
    body = "".join(out) or ("<p class='ox-nodata'>nothing to chart yet</p>")
    return ("<div class='ox-cc'><div class='ox-cc-title'>%s</div>%s%s</div>"
            % (_e(title), body, source_chip(source) if source else ""))


# ==========================================================================
# SCREEN SCAFFOLD
# ==========================================================================
def screen(sid: str, title: str, sub: str, body: str, *,
           staffed_by: str = "", badge_kind: str = "",
           series: Optional[Dict[str, Any]] = None,
           activity: Optional[Sequence] = None) -> str:
    """One lettered screen (13a, 14b...). The header always says WHOSE desk
    this is, because a desk is a view of a lane and the reader must be able
    to see one employee covering several boards."""
    who = ""
    if staffed_by:
        who = ("<div class='ox-staffed'>staffed by <b>%s</b>%s</div>"
               % (_e(staffed_by),
                  (" " + badge(badge_kind)) if badge_kind else ""))
    # HIS RIGHT-HAND RAIL. He drew one on 34 of his 51 screens and it is
    # not decoration: it is where the gates that bind THIS screen are
    # stated, and where a desk points at the module that owns the work it
    # is not allowed to do. Building the frame without it left the
    # structure right and the screen half-empty.
    #
    # Looked up by screen id rather than passed in, so a screen he drew a
    # rail on cannot silently lose it when a call site is edited.
    # HIS CHART CARDS AND ACTIVITY LISTS, on the screens he drew them on.
    # The gate used to assert only that these COMPONENTS existed, and it
    # passed while not one screen called them. A toolbox is not the work.
    #
    # `series` lets a module hand real rows in, keyed by his own title.
    # Nothing supplied means the chart draws NOT MEASURED rather than an
    # empty box, so these screens now show him precisely which data his
    # engine still lacks. That is the question he built the OS to answer.
    # HIS IN-SCREEN TABS. Nine of his desks are one screen holding several
    # views: the Technical Engineer holds Crawl, Speed, Index, Schema and
    # Redirects. Flattening that into one board buries four views out of
    # five, which is what this OS did until now.
    #
    # They really switch. A strip of labels that does nothing would be a
    # dead button, and this OS gates against those.
    tabs_html = ""
    try:
        import content_engine_os_tabs as _TB
        _tabs = _TB.tabs_for(sid)
    except Exception:                                     # noqa: BLE001
        _tabs = ()
    if _tabs:
        btns, panes = [], []
        for _i, _lab in enumerate(_tabs):
            on = " on" if _i == 0 else ""
            btns.append("<button class='ox-tab%s' id='oxt-%s-%d' "
                        "onclick=\"osTab('%s',%d)\">%s</button>"
                        % (on, _e(sid), _i, _e(sid), _i, _e(_lab)))
            panes.append("<div class='ox-tabpane%s' id='oxp-%s-%d'>%s</div>"
                         % (on, _e(sid), _i,
                            # Structure now, numbers when a collector feeds
                            # it. Saying that is more use than an empty box.
                            chart(_lab, [], source="")))
        tabs_html = ("<div class='ox-tabbar'>" + "".join(btns) + "</div>"
                     + "".join(panes))

    extra = tabs_html
    try:
        import content_engine_os_cards as _CD
        _titles = _CD.charts_for(sid)
        _act = _CD.has_activity(sid)
    except Exception:                                     # noqa: BLE001
        _titles, _act = (), False
    series = series or {}
    for _t in _titles:
        extra += chart(_t, series.get(_t) or [], source=("live" if series.get(_t) else ""))
    if _act:
        rows = list(activity or [])
        if rows:
            extra += "<div class='ox-dq-list'>" + "".join(rows) + "</div>"
        else:
            # NOT his placeholder text. His file says things like "Shopware
            # sync degraded, token expired 41m ago"; printing that here
            # would invent an incident. Silence is reported as silence.
            extra += ("<div class='ox-dq-list'>"
                      + dq("Nothing recorded on this desk yet")
                      + "</div>")

    rail = ""
    try:
        import content_engine_os_rails as _R
        secs = _R.for_screen(sid)
    except Exception:                                     # noqa: BLE001
        secs = ()
    if secs:
        rail = ("<aside class='ox-staffrail'>"
                + "".join("<div class='ox-rail-head'>%s</div>"
                          "<p class='ox-rail-p'>%s</p>" % (_e(h), _e(t))
                          for h, t in secs)
                + "</aside>")
    return ("<section class='ox-screen' id='os-%s'>"
            "<div class='ox-sh'><span class='ox-sid'>%s</span>"
            "<div><h3>%s</h3><p class='ox-sub'>%s</p></div>%s</div>"
            "<div class='ox-scr%s'><div class='ox-scr-main'>%s%s</div>%s</div>"
            "</section>"
            % (_e(sid), _e(sid), _e(title), _e(sub), who,
               " railed" if rail else "", body, extra, rail))


def grid(*cards: str, cols: str = "") -> str:
    return "<div class='ox-grid %s'>%s</div>" % (_e(cols), "".join(cards))


def planned(what: str, needs: str) -> str:
    """A platform with no wire at all. It gets its layout and says exactly
    what would light it up. ZERO invented numbers: the founder chose this
    over sample data precisely so a screenshot can never be quoted as real."""
    return bp("<div class='ox-planned'><span class='ox-pl'>Planned</span>"
              "<h4>%s</h4><p>Nothing is connected, so nothing is shown.</p>"
              "<p class='ox-need'>Needs: <b>%s</b></p></div>"
              % (_e(what), _e(needs)), cls="ox-plan")


# ==========================================================================
# THE STYLESHEET. Industry tokens, declared on .osx, read only from .osx.
# ==========================================================================
CSS = """
.osx{
  --ox-bg:#f2f2f3; --ox-sf:#e9e9ea; --ox-cd:#f8f8f9;
  --ox-ink:#1d1f20; --ox-ink2:#5d5d60; --ox-ink3:#7a7a7d;
  --ox-ln:#d4d4d7; --ox-ln2:#b7b7ba;
  --ox-ac:#5980a6; --ox-acd:#416180; --ox-acw:#e4edf6;
  /* his second accent, from the handoff's own styles.css. It was the
     one token of his nine that this kit did not carry. */
  --ox-ac2:#728fab;
  --ox-dg:#a3564b; --ox-dgw:#f4e6e4;
  --ox-ok:#4f7a5b; --ox-okw:#e6efe8;
  --ox-wn:#8a6d3b; --ox-wnw:#f5efe2;
  --ox-dsp:"Barlow Condensed","Arial Narrow","Roboto Condensed",system-ui,sans-serif;
  --ox-bdy:"Barlow",system-ui,-apple-system,"Segoe UI",sans-serif;
  --ox-mn:ui-monospace,"Cascadia Mono",Consolas,monospace;
  background:var(--ox-bg); color:var(--ox-ink);
  font-family:var(--ox-bdy); font-size:14px; line-height:1.5;
  padding:18px; display:flex; flex-direction:column; gap:26px;
}
.osx h3,.osx h4{font-family:var(--ox-dsp);font-weight:600;margin:0;
  letter-spacing:.02em;color:var(--ox-ink)}
.osx h3{font-size:1.22rem;text-transform:uppercase;letter-spacing:.05em}
.osx h4{font-size:1.02rem}
.osx p{margin:0}

.osx .ox-bp{position:relative;border:1px solid var(--ox-ln);
  background:var(--ox-cd);padding:16px 18px;display:flex;
  flex-direction:column;gap:12px}
.osx .ox-c{position:absolute;width:8px;height:8px;color:var(--ox-ln2)}
.osx .ox-c::before,.osx .ox-c::after{content:"";position:absolute;
  background:currentColor}
.osx .ox-c::before{left:0;top:3.5px;width:8px;height:1px}
.osx .ox-c::after{top:0;left:3.5px;width:1px;height:8px}
.osx .ox-c.tl{left:-4px;top:-4px}   .osx .ox-c.tr{right:-4px;top:-4px}
.osx .ox-c.bl{left:-4px;bottom:-4px}.osx .ox-c.br{right:-4px;bottom:-4px}

.osx .ox-lbl{font-family:var(--ox-dsp);text-transform:uppercase;
  letter-spacing:.13em;font-size:.68rem;color:var(--ox-ink3);font-weight:600}

.osx .ox-screen{display:flex;flex-direction:column;gap:14px;
  border-top:2px solid var(--ox-ink);padding-top:14px}
.osx .ox-sh{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}
.osx .ox-sid{font-family:var(--ox-dsp);font-weight:600;font-size:.78rem;
  letter-spacing:.1em;background:var(--ox-ink);color:var(--ox-bg);
  padding:2px 8px;text-transform:uppercase}
.osx .ox-sub{color:var(--ox-ink2);font-size:.92rem;max-width:74ch}
.osx .ox-staffed{margin-left:auto;font-size:.82rem;color:var(--ox-ink3);
  display:flex;align-items:center;gap:8px}
.osx .ox-staffed b{color:var(--ox-ink2)}

.osx .ox-grid{display:grid;gap:14px;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.osx .ox-grid.wide{grid-template-columns:1fr}
.osx .ox-grid.two{grid-template-columns:repeat(auto-fit,minmax(430px,1fr))}

.osx .ox-badge{display:inline-flex;align-items:center;gap:5px;
  font-family:var(--ox-dsp);font-size:.68rem;font-weight:600;
  text-transform:uppercase;letter-spacing:.08em;padding:2px 8px;
  border:1px solid var(--ox-ln2);color:var(--ox-ink2);background:var(--ox-sf);
  white-space:nowrap}
.osx .ox-b-live{border-color:var(--ox-ac);color:var(--ox-acd);
  background:var(--ox-acw)}
.osx .ox-b-inspector{border-color:var(--ox-wn);color:var(--ox-wn);
  background:var(--ox-wnw)}
.osx .ox-b-architected{border-color:var(--ox-ln2);color:var(--ox-ink3);
  background:transparent}
.osx .ox-b-notstaffed{border-style:dashed;color:var(--ox-ink3);
  background:transparent}

.osx .ox-src{display:inline-block;font-family:var(--ox-mn);font-size:.66rem;
  color:var(--ox-ink3);border:1px solid var(--ox-ln);padding:1px 5px;
  margin-top:5px}
.osx .ox-src-none{color:var(--ox-dg);border-color:var(--ox-dg)}
.osx .ox-nodata{color:var(--ox-ink3);font-style:italic;font-size:.88rem}

.osx .ox-stat{display:flex;flex-direction:column}
.osx .ox-stat-n{font-family:var(--ox-dsp);font-size:2.1rem;line-height:1.05;
  color:var(--ox-acd);font-variant-numeric:tabular-nums}
.osx .ox-stat-l{font-family:var(--ox-dsp);text-transform:uppercase;
  letter-spacing:.09em;font-size:.72rem;color:var(--ox-ink3);font-weight:600;
  margin-top:3px}
.osx .ox-unit{font-size:.9rem;margin-left:3px;color:var(--ox-ink3)}

.osx .ox-ac-head{display:flex;justify-content:space-between;
  align-items:flex-start;gap:10px;flex-wrap:wrap}
.osx .ox-ac-id{font-family:var(--ox-mn);font-size:.72rem;color:var(--ox-ink3)}
.osx .ox-ac-sec{display:flex;flex-direction:column;gap:6px;
  border-top:1px solid var(--ox-ln);padding-top:10px}
.osx .ox-chips{display:flex;gap:6px;flex-wrap:wrap}
.osx .ox-chip{font-size:.72rem;padding:2px 7px;border:1px solid var(--ox-ln2);
  font-family:var(--ox-dsp);font-weight:600;letter-spacing:.05em}
.osx .ox-chip.ok{color:var(--ox-ok);border-color:var(--ox-ok);
  background:var(--ox-okw)}
.osx .ox-chip.bad{color:var(--ox-dg);border-color:var(--ox-dg);
  background:var(--ox-dgw)}
.osx .ox-chip.ask{color:var(--ox-acd);border-color:var(--ox-ac);
  background:var(--ox-acw)}
.osx ul.ox-rep,.osx ul.ox-learn,.osx ul.ox-pas{margin:0;padding-left:16px;
  display:flex;flex-direction:column;gap:4px;font-size:.88rem;
  color:var(--ox-ink2)}
.osx ul.ox-rep li.bad{color:var(--ox-dg)}
.osx ul.ox-rep li.blocked{color:var(--ox-dg)}
.osx ul.ox-rep li.quiet{color:var(--ox-ink3);font-style:italic}
.osx ul.ox-rep em{color:var(--ox-ink3);font-style:normal}
.osx .ox-slots{display:flex;flex-wrap:wrap;gap:6px}
.osx .ox-slot,.osx .ox-dot{display:inline-flex;align-items:center;gap:5px;
  font-size:.74rem;padding:2px 7px;border:1px solid var(--ox-ln2);
  background:var(--ox-sf);color:var(--ox-ink2);white-space:nowrap}
.osx .ox-s-verified{border-color:var(--ox-ok);color:var(--ox-ok);
  background:var(--ox-okw)}
.osx .ox-s-present{border-color:var(--ox-wn);color:var(--ox-wn);
  background:var(--ox-wnw)}
.osx .ox-s-rejected{border-color:var(--ox-dg);color:var(--ox-dg);
  background:var(--ox-dgw)}
.osx .ox-s-empty{border-style:dashed;color:var(--ox-ink3)}
.osx .ox-ac-cap{font-size:.8rem;color:var(--ox-ink3);
  border-top:1px solid var(--ox-ln);padding-top:8px}
.osx .ox-ac-cap b{color:var(--ox-ink2);font-variant-numeric:tabular-nums}

.osx .ox-tw{overflow-x:auto;border:1px solid var(--ox-ln);
  background:var(--ox-cd)}
.osx table.ox-t{border-collapse:collapse;width:100%;min-width:620px;
  font-size:.86rem}
.osx table.ox-t th,.osx table.ox-t td{text-align:left;padding:8px 12px;
  border-bottom:1px solid var(--ox-ln);vertical-align:top;color:var(--ox-ink2)}
.osx table.ox-t th{font-family:var(--ox-dsp);text-transform:uppercase;
  letter-spacing:.07em;font-size:.72rem;color:var(--ox-ink3);
  background:var(--ox-sf);font-weight:600}
.osx table.ox-t tbody tr:last-child td{border-bottom:none}
.osx .ox-wire{font-family:var(--ox-mn);font-size:.8rem;color:var(--ox-ink)}
.osx .ox-warn{color:var(--ox-dg)}

.osx .ox-cc{background:var(--ox-sf)}
.osx .ox-cc-h{display:flex;flex-direction:column;gap:2px}
.osx .ox-cc-scope{font-size:.74rem;color:var(--ox-ink3)}
.osx .ox-cc-note{font-size:.82rem;color:var(--ox-ink2)}
.osx .ox-cc-sec{display:flex;flex-direction:column;gap:6px;
  border-top:1px solid var(--ox-ln);padding-top:10px}
.osx li.ox-pa{list-style:none;border-left:3px solid var(--ox-ac);
  padding:6px 0 6px 10px;display:flex;flex-direction:column;gap:4px}
.osx li.ox-pa.pink{border-left-color:var(--ox-dg)}
.osx .ox-pa-w{color:var(--ox-ink);font-weight:600}
.osx .ox-pa-y{font-size:.82rem;color:var(--ox-ink3)}
.osx .ox-pa-b{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.osx .ox-pink{font-size:.72rem;color:var(--ox-dg);
  font-family:var(--ox-dsp);text-transform:uppercase;letter-spacing:.06em}
.osx .ox-btn{font-family:var(--ox-dsp);font-weight:600;font-size:.78rem;
  text-transform:uppercase;letter-spacing:.06em;padding:5px 12px;
  border:1px solid var(--ox-ln2);background:var(--ox-cd);color:var(--ox-ink2);
  cursor:pointer;border-radius:0}
.osx .ox-btn:hover{border-color:var(--ox-ac);color:var(--ox-acd)}
.osx .ox-btn-p{background:var(--ox-ac);border-color:var(--ox-ac);color:#fff}
.osx .ox-btn-p:hover{background:var(--ox-acd);border-color:var(--ox-acd);
  color:#fff}
.osx .ox-btn:focus-visible,.osx .ox-q:focus-visible,
.osx .ox-in:focus-visible{outline:2px solid var(--ox-acd);outline-offset:2px}
.osx .ox-qs{display:flex;flex-wrap:wrap;gap:6px}
.osx .ox-q{font-size:.76rem;padding:3px 9px;border:1px dashed var(--ox-ln2);
  background:transparent;color:var(--ox-ink2);cursor:pointer;border-radius:0}
.osx .ox-q:hover{border-style:solid;border-color:var(--ox-ac);
  color:var(--ox-acd)}
.osx .ox-cc-bar{display:flex;gap:8px;border-top:1px solid var(--ox-ln);
  padding-top:10px}
.osx .ox-in{flex:1;padding:7px 10px;border:1px solid var(--ox-ln2);
  background:var(--ox-cd);color:var(--ox-ink);font-family:var(--ox-bdy);
  font-size:.86rem;border-radius:0}
.osx .ox-cc-ack{font-size:.82rem;color:var(--ox-acd);min-height:1em}

.osx .ox-topbar{display:flex;align-items:center;gap:14px;
  border:1px solid var(--ox-ln);background:var(--ox-sf);padding:8px 14px;
  font-size:.8rem;color:var(--ox-ink2)}
.osx .ox-brand{font-family:var(--ox-dsp);font-weight:600;letter-spacing:.06em;
  color:var(--ox-ink);display:flex;align-items:center;gap:7px}
.osx .ox-logo{height:20px;width:20px;object-fit:contain;display:block}
.osx .ox-cost{margin-left:auto;font-variant-numeric:tabular-nums}
.osx .ox-frame{display:grid;grid-template-columns:210px 1fr;gap:16px;
  align-items:start}
@media (max-width:820px){.osx .ox-frame{grid-template-columns:1fr}}
.osx .ox-sidebar{border:1px solid var(--ox-ln);background:var(--ox-cd);
  padding:10px;display:flex;flex-direction:column;gap:2px;position:sticky;
  top:8px}
.osx .ox-modgroup{font-family:var(--ox-dsp);text-transform:uppercase;
  letter-spacing:.13em;font-size:.66rem;color:var(--ox-ink3);font-weight:600;
  padding:2px 6px 6px}
.osx a.ox-mod{display:block;padding:5px 8px;font-size:.82rem;
  color:var(--ox-ink2);text-decoration:none;border-left:2px solid transparent}
.osx a.ox-mod:hover{color:var(--ox-acd);background:var(--ox-sf)}
.osx a.ox-mod.on{color:var(--ox-ink);font-weight:600;
  border-left-color:var(--ox-ac);background:var(--ox-acw)}
.osx .ox-subnav{display:flex;flex-direction:column;gap:1px;
  margin:2px 0 6px 10px;border-left:1px solid var(--ox-ln);padding-left:8px}
.osx a.ox-snav{display:block;padding:3px 6px;font-size:.78rem;
  color:var(--ox-ink3);text-decoration:none}
.osx a.ox-snav:hover{color:var(--ox-acd)}
.osx a.ox-snav.on{color:var(--ox-acd);font-weight:600}
.osx .ox-main{display:flex;flex-direction:column;gap:24px;min-width:0}
/* HIS STAFFRAIL. The widths and the divider are from his own styles.css:
   .mos-staffrail{width:216px;border-left:1px solid neutral-300;padding:14px}
   A screen he drew no rail on keeps the full width rather than holding an
   empty column open, which is why the two-column rule is on .railed. */
/* his in-screen tab strip: one desk, several views */
.osx .ox-tabbar{display:flex;flex-wrap:wrap;gap:1px;margin:14px 0 0;
  border-bottom:1px solid var(--ox-ln)}
.osx button.ox-tab{background:none;border:none;border-bottom:2px solid transparent;
  padding:7px 11px;font-family:inherit;font-size:.76rem;color:var(--ox-ink3);
  cursor:pointer}
.osx button.ox-tab:hover{color:var(--ox-acd)}
.osx button.ox-tab.on{color:var(--ox-ink);font-weight:600;
  border-bottom-color:var(--ox-ac)}
.osx .ox-tabpane{display:none;padding-top:14px}
.osx .ox-tabpane.on{display:block}
/* his .dq-list{display:flex;flex-direction:column;gap:10px} */
/* the build stamp, in his topbar: proof of which code is live */
.osx .ox-build{font-family:var(--ox-mn);font-size:.66rem;
  color:var(--ox-ink3);border:1px solid var(--ox-ln);padding:2px 6px}
.osx .ox-tools{margin-left:auto;display:flex;gap:8px;align-items:center}
.osx .ox-dq-list{display:flex;flex-direction:column;gap:10px;margin-top:14px}
.osx .ox-scr{min-width:0}
.osx .ox-scr.railed{display:grid;grid-template-columns:1fr 216px;gap:14px}
.osx .ox-scr-main{min-width:0}
.osx .ox-staffrail{border-left:1px solid var(--ox-ln);padding:0 0 0 14px;
  align-self:start}
.osx .ox-rail-head{font-family:'Barlow Condensed',sans-serif;font-weight:600;
  font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;
  color:var(--ox-ink);margin:0 0 4px}
.osx .ox-rail-head + .ox-rail-p{margin-top:0}
.osx .ox-rail-p{font-size:.72rem;line-height:1.5;color:var(--ox-ink2);
  margin:0 0 14px}
@media (max-width:1100px){.osx .ox-scr.railed{grid-template-columns:1fr}
  .osx .ox-staffrail{border-left:none;border-top:1px solid var(--ox-ln);
    padding:12px 0 0}}
.osx .ox-crumb{font-size:.8rem;color:var(--ox-ink3)}
.osx .ox-crumb b{color:var(--ox-ink)}

.osx .ox-dq{display:flex;align-items:flex-start;gap:12px;
  border:1px solid var(--ox-ln);background:var(--ox-cd);padding:9px 12px;
  margin-bottom:6px}
.osx .ox-dq.pink{border-left:3px solid var(--ox-dg)}
.osx .ox-dq-main{flex:1;min-width:0}
.osx .ox-dq-rec{color:var(--ox-ink);font-weight:600;font-size:.9rem}
.osx .ox-dq-ev{color:var(--ox-ink3);font-size:.8rem;margin-top:2px}
.osx .ox-dq-actions{flex-shrink:0}
.osx .ox-dq-actions a{text-decoration:none}

.osx .ox-cc{border:1px solid var(--ox-ln);background:var(--ox-cd);
  padding:12px 14px;display:flex;flex-direction:column;gap:7px}
.osx .ox-cc-title{font-family:var(--ox-dsp);font-weight:600;font-size:.9rem;
  color:var(--ox-ink);letter-spacing:.02em}
.osx .ox-hbar{display:grid;grid-template-columns:minmax(90px,150px) 1fr auto;
  gap:9px;align-items:center;font-size:.82rem;color:var(--ox-ink2)}
.osx .ox-hbar-l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.osx .ox-hbar-t{display:block;height:9px;background:var(--ox-sf);
  border:1px solid var(--ox-ln)}
.osx .ox-hbar-t i{display:block;height:100%;background:var(--ox-ac)}
.osx .ox-hbar b{font-variant-numeric:tabular-nums;color:var(--ox-ink)}
.osx .ox-plan{border-style:dashed}
.osx .ox-pl{font-family:var(--ox-dsp);text-transform:uppercase;
  letter-spacing:.12em;font-size:.68rem;color:var(--ox-ink3);
  border:1px solid var(--ox-ln2);padding:1px 7px;align-self:flex-start}
.osx .ox-planned{display:flex;flex-direction:column;gap:7px}
.osx .ox-planned p{font-size:.86rem;color:var(--ox-ink3)}
.osx .ox-need b{color:var(--ox-ink2)}
"""

# --------------------------------------------------------------------------
# THE PANEL'S BEHAVIOUR. Section 10.4: a command becomes a PROPOSAL.
# --------------------------------------------------------------------------
JS = """
function osPrefill(aid, btn){
  var i=document.getElementById('oscmd-'+aid);
  if(i){ i.value=btn.textContent; i.focus(); }
}
function osAck(aid, msg){
  var a=document.getElementById('osack-'+aid); if(a) a.textContent=msg;
}
function osSend(aid){
  var i=document.getElementById('oscmd-'+aid); if(!i) return;
  var text=(i.value||'').trim(); if(!text){ osAck(aid,'Type a command first.');
    return; }
  osAck(aid,'Sending...');
  fetch('/proposal',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({agent:aid,text:text,source:'cmdchat'})})
   .then(function(r){return r.json();})
   .then(function(d){
     i.value='';
     osAck(aid, d && d.ok
       ? 'Queued as a proposal for you to approve. Nothing has run.'
       : 'Could not queue that: '+((d&&(d.error||d.detail))||'unknown'));
   })
   .catch(function(e){ osAck(aid,'Could not reach the engine: '+e); });
}
function osPriceApprove(id){
  // A PRICE CHANGE IS THE MOST CONSEQUENTIAL THING HERE. It confirms,
  // one at a time, and the engine records who said yes.
  if(!confirm('Approve this price change? It writes the new price to your '
      + 'shop and is recorded against your name.')) return;
  fetch('/commerce/price/'+encodeURIComponent(id)+'/approve',
    {method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({})})
   .then(function(r){return r.json();})
   .then(function(d){
     if(d && d.ok){
       osAck('commerce.analyst','Applied: '+d.from+' to '+d.to+'.');
       var row=document.getElementById('ospx-'+id); if(row) row.remove();
     } else {
       // A REFUSAL IS INFORMATION, not a glitch. Show the engine's words.
       osAck('commerce.analyst','Not applied: '+((d&&d.why)||'unknown'));
     }
   })
   .catch(function(e){ osAck('commerce.analyst','Could not reach the engine: '+e); });
}
function osPriceDecline(id){
  fetch('/commerce/price/'+encodeURIComponent(id)+'/decline',
    {method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({note:'declined from the pricing desk'})})
   .then(function(r){return r.json();})
   .then(function(d){
     osAck('commerce.analyst', d&&d.ok ? 'Declined.' :
       ('Could not decline: '+((d&&d.why)||'unknown')));
     var row=document.getElementById('ospx-'+id); if(row && d && d.ok) row.remove();
   })
   .catch(function(e){ osAck('commerce.analyst','Could not reach the engine: '+e); });
}
function osGo(sid){
  // Scroll to one screen inside the page that is already open, and mark
  // its subnav link. Returns false so the href never becomes a hash: the
  // host page routes on hash change and would navigate away instead.
  var el = document.getElementById('os-' + sid);
  if(!el) return false;
  var page = el.closest ? el.closest('.page') : null;
  if(page){
    page.querySelectorAll('a.ox-snav').forEach(function(a){
      a.className = 'ox-snav' +
        ((a.getAttribute('href') === '#os-' + sid) ? ' on' : '');
    });
  }
  el.scrollIntoView({behavior:'smooth', block:'start'});
  return false;
}
function osTab(sid, i){
  // His desks that hold several views. Switching is local to one screen,
  // so the id carries the screen: two desks open at once cannot fight.
  var n = 0;
  while(document.getElementById('oxt-'+sid+'-'+n)){
    var b = document.getElementById('oxt-'+sid+'-'+n);
    var p = document.getElementById('oxp-'+sid+'-'+n);
    if(b) b.className = 'ox-tab' + (n===i ? ' on' : '');
    if(p) p.className = 'ox-tabpane' + (n===i ? ' on' : '');
    n++;
  }
  return false;
}
function osTracking(on){
  // Open tracking is the real consent control for European markets.
  // Turning it OFF is the safe direction, so it needs no confirmation;
  // turning it ON does, because it starts collecting behaviour.
  if(on && !confirm('Turn open tracking ON? It collects opens and clicks, '
      + 'which needs consent in Germany and Switzerland.')) return;
  fetch('/outreach/tracking',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({enabled:!!on})})
   .then(function(r){return r.json();})
   .then(function(d){
     osAck('leads.qualifier', (d && d.error)
       ? ('Could not change it: '+d.error)
       : ('Open tracking is now '+(on?'ON':'OFF')+'. Reload to see the '
          + 'state update everywhere it is shown.'));
   })
   .catch(function(e){ osAck('leads.qualifier','Could not reach the engine: '+e); });
}
function osJobDecision(id, verb){
  // The approval room's one gate. It calls the SAME routes the old
  // dashboard uses, so there is exactly one path from "approved" to
  // "published" in the whole product.
  fetch('/jobs/'+encodeURIComponent(id)+'/'+verb,{method:'POST'})
   .then(function(r){return r.json();})
   .then(function(d){
     osAck('cockpit', (d && d.ok !== false)
       ? (verb==='approve' ? 'Approved. It publishes on its next tick.'
                           : 'Sent back for revision.')
       : ('Could not '+verb+': '+((d&&(d.error||d.detail))||'unknown')));
     var row=document.getElementById('osjob-'+id); if(row) row.remove();
   })
   .catch(function(e){ osAck('cockpit','Could not reach the engine: '+e); });
}
function osApproveJob(id){ osJobDecision(id,'approve'); }
function osDeclineJob(id){ osJobDecision(id,'decline'); }
function osSaveKey(key){
  var i=document.getElementById('oskey-'+key); if(!i) return;
  var v=(i.value||'').trim();
  if(!v){ osAck('cockpit','Nothing typed for '+key+'.'); return; }
  var body={}; body[key]=v;
  fetch('/connect',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)})
   .then(function(r){return r.json();})
   .then(function(d){
     i.value='';
     // A SAVED KEY IS NOT A WORKING KEY. Say so at the moment of saving,
     // or the founder reads "Saved" as "connected" and we are back to
     // false green by way of a toast.
     osAck('cockpit', (d && d.error)
       ? ('Could not save: '+d.error)
       : (key+' saved. It stays amber until a real call is accepted.'));
   })
   .catch(function(e){ osAck('cockpit','Could not reach the engine: '+e); });
}
function osMemberAdd(){
  var e=document.getElementById('os-adm-email');
  var r=document.getElementById('os-adm-role');
  var em=(e&&e.value||'').trim();
  if(!em){ osAck('cockpit','No email typed.'); return; }
  fetch('/os/member/add',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email:em, role:(r&&r.value)||'member'})})
   .then(function(x){return x.json();})
   .then(function(d){
     // the endpoint is the authority: it checks the admin grant and
     // refuses; this page only repeats what it said.
     osAck('cockpit',(d&&d.ok===false)?('Refused: '+(d.message||'no reason given'))
       :(em+' added. Reload to see the row.'));
     if(e) e.value='';
   })
   .catch(function(err){ osAck('cockpit','Could not reach the engine: '+err); });
}
function osMemberRemove(em){
  if(!window.confirm('Remove '+em+' from this workspace?')) return;
  fetch('/os/member/remove',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email:em})})
   .then(function(x){return x.json();})
   .then(function(d){
     osAck('cockpit',(d&&d.ok)?(em+' removed. Reload to see the list.')
       :('Refused: '+((d&&d.message)||'no reason given')));
   })
   .catch(function(err){ osAck('cockpit','Could not reach the engine: '+err); });
}
function osApprove(aid, item, pink){
  // A PINK ACTION NEVER APPROVES FROM HERE. The prototype short-circuited
  // this; production sends you to the module's own confirm gate.
  if(pink){
    osAck(aid,'This one spends or publishes. Open its module gate to confirm.');
    if(typeof nav==='function'){ nav('cockpit'); }
    return;
  }
  fetch('/proposal/'+encodeURIComponent(item)+'/approve',{method:'POST'})
   .then(function(r){return r.json();})
   .then(function(d){ osAck(aid, d&&d.ok ? 'Approved.' :
      'Could not approve: '+((d&&(d.error||d.detail))||'unknown')); })
   .catch(function(e){ osAck(aid,'Could not reach the engine: '+e); });
}
function osReject(aid, item){
  fetch('/proposal/'+encodeURIComponent(item)+'/decline',{method:'POST'})
   .then(function(r){return r.json();})
   .then(function(d){ osAck(aid, d&&d.ok ? 'Rejected.' :
      'Could not reject: '+((d&&(d.error||d.detail))||'unknown')); })
   .catch(function(e){ osAck(aid,'Could not reach the engine: '+e); });
}
"""


def check() -> Dict[str, Any]:
    """Gate helper: the kit's vocabulary must agree with the contract's.

    BADGE_LABEL and CONTRACT.BADGES are two hand-written lists that must
    agree. That is the bug class this project keeps meeting, so it is
    checked rather than trusted."""
    problems = []
    if set(BADGE_LABEL) != set(C.BADGES):
        problems.append("kit badges %s vs contract badges %s"
                        % (sorted(BADGE_LABEL), sorted(C.BADGES)))
    if set(STATUS_LABEL) != set(C.CONNECTOR_STATES):
        problems.append("kit statuses %s vs contract states %s"
                        % (sorted(STATUS_LABEL), sorted(C.CONNECTOR_STATES)))
    # every class the components emit must have a rule in the stylesheet
    emitted = ["ox-bp", "ox-c", "ox-badge", "ox-src", "ox-src-none", "ox-nodata",
               "ox-stat", "ox-stat-n", "ox-stat-l", "ox-unit", "ox-ac-head",
               "ox-ac-id", "ox-ac-sec", "ox-chips", "ox-chip", "ox-rep",
               "ox-learn", "ox-slots", "ox-slot", "ox-dot", "ox-ac-cap",
               "ox-tw", "ox-t", "ox-wire", "ox-warn", "ox-cc", "ox-cc-h",
               "ox-cc-scope", "ox-cc-note", "ox-cc-sec", "ox-pa", "ox-pa-w",
               "ox-pa-y", "ox-pa-b", "ox-pink", "ox-btn", "ox-btn-p", "ox-qs",
               "ox-q", "ox-cc-bar", "ox-in", "ox-cc-ack", "ox-plan", "ox-pl",
               "ox-planned", "ox-need", "ox-screen", "ox-sh", "ox-sid",
               "ox-sub", "ox-staffed", "ox-grid", "ox-lbl", "ox-pas"]
    emitted += ["ox-topbar", "ox-brand", "ox-cost", "ox-frame", "ox-sidebar",
                "ox-modgroup", "ox-mod", "ox-subnav", "ox-snav", "ox-main",
                "ox-crumb", "ox-dq", "ox-dq-main", "ox-dq-rec", "ox-dq-ev",
                "ox-dq-actions", "ox-cc", "ox-cc-title", "ox-hbar",
                "ox-hbar-l", "ox-hbar-t",
                "ox-scr", "ox-scr-main", "ox-staffrail", "ox-rail-head",
                "ox-dq-list", "ox-tabbar", "ox-tab", "ox-tabpane", "ox-tools",
                "ox-rail-p"]
    for cls in emitted:
        if ("." + cls) not in CSS:
            problems.append("class %s is emitted with no CSS rule" % cls)
    for st in STATUS_LABEL:
        if (".ox-s-" + st) not in CSS:
            problems.append("status %s has no CSS rule" % st)
    # THE PER-BADGE RULES. This loop is here because the first version of
    # the check listed class names by hand and missed ox-b-inspector and
    # ox-b-architected, so two of the four badges rendered unstyled. A hand
    # written list of things to check is the same bug as a hand written
    # list of anything else: derive it from the vocabulary instead.
    for b in BADGE_LABEL:
        if (".ox-b-" + b) not in CSS:
            problems.append("badge %s has no CSS rule" % b)
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    r = check()
    assert r["ok"], r["problems"]
    print("kit ok:", len(CSS), "chars of CSS")
