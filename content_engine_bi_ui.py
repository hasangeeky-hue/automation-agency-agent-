# -*- coding: utf-8 -*-
"""BI OS: the section, assembled.

Spec sections 3, 76, 83-85, 95, 103-104.

NINE SCREENS FOR THE MVP (section 95), not the fifteen of section 3. The
full navigation is the destination; these nine are what has to work
first, and two of them (Costs, Agent Economics) are mandatory because
without them this is the previous BI with a new coat.

WHY THIS FILE IS NOT content_engine_bi_boards.py
------------------------------------------------
That name is taken by the module this replaces, and
content_engine_dashboard imports it at line 4465. Writing over it
destroys 1,749 lines, which happened once already in this project with
the Content Factory boards. The old name survives as a shim.

ONE LIST. The nav and the panels are both derived from SCREENS, so a
screen cannot be declared in one place and drawn from another.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import content_engine_bi_cost as COST
import content_engine_bi_economics as ECON
import content_engine_bi_screens as S

_s, _d, _l, _f = COST._s, COST._d, COST._l, COST._f
e = S.e

# ===========================================================================
# 95. THE NINE
# ===========================================================================
SCREENS: Tuple[Tuple[str, str, str, Callable, str], ...] = (
    ("biexec", "01", "Executive", S.executive,
     "What is the business actually keeping?"),
    ("bigrowth", "02", "Growth", S.growth,
     "Which channel returns most per unit spent?"),
    ("bifunnel", "03", "Funnel", S.funnel,
     "Where do we lose people, and what does each stage cost?"),
    ("bicosts", "04", "Costs", S.costs,
     "What are we paying for, and what is wasted?"),
    ("biagents", "05", "Agent Economics", S.agent_economics,
     "Which agents earn their keep?"),
    ("birisks", "06", "Risks and Opportunities", S.risks,
     "What is about to cost us, and what could we save?"),
    ("bidecide", "07", "AI Decisions", S.decisions,
     "Of the options, which has the best expected NET value?"),
    ("biinit", "08", "Initiatives", S.initiatives,
     "What did we approve, and what did it really cost?"),
    ("bihealth", "09", "Data and Cost Health", S.health,
     "Are the inputs fresh, the providers working, the spend sane?"),
)

#: Section 96-97. These two cannot be dropped from the MVP.
MANDATORY = ("bicosts", "biagents")

#: Section 3. The full navigation, for reference. Screens beyond the MVP
#: are named so nobody rebuilds one under a different name later.
FULL_NAV = ("Executive Command Center", "Growth", "Marketing", "Revenue",
            "Funnel", "Content and Demand", "Cost Intelligence",
            "Agent Economics", "Tool and API Economics",
            "Risks and Opportunities", "AI Decisions", "Initiatives",
            "Reports", "Data Health", "Cost Settings")


def check_screens() -> Dict[str, Any]:
    problems = []
    for sid, _num, _label, fn, _q in SCREENS:
        if not callable(fn):
            problems.append(sid + ": no renderer")
    ids = [x[0] for x in SCREENS]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        problems.append("duplicate screen id: " + ", ".join(dupes))
    for m in MANDATORY:
        if m not in ids:
            problems.append(m + " is mandatory for the MVP and missing")
    if len(SCREENS) != 9:
        problems.append("the MVP is nine screens; found "
                        + str(len(SCREENS)))
    return {"ok": not problems, "problems": problems,
            "count": len(SCREENS),
            "why": ("nine screens, both mandatory ones present"
                    if not problems else "; ".join(problems))}


# ===========================================================================
# THE SHELL
# ===========================================================================
_SHELL_CSS = """<style>
.bi-shell{display:grid;grid-template-columns:248px 1fr;gap:14px;
align-items:start}
.bi-nav{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:10px;position:sticky;top:8px}
.bi-nav a{display:flex;gap:9px;align-items:baseline;padding:8px 10px;
border-radius:8px;color:var(--tx2);font-size:13px;cursor:pointer}
.bi-nav a b{font-size:11px;color:var(--mu);font-weight:500;
font-variant-numeric:tabular-nums}
.bi-nav a:hover{background:var(--sf2);color:var(--tx)}
.bi-nav a.on{background:rgba(37,99,235,.08);color:var(--hu);
font-weight:600}
.bi-nav a.on b{color:var(--hu)}
.bi-nav a i{font-style:normal;margin-left:auto;font-size:9px;
color:var(--wa);letter-spacing:.04em}
.bi-panel{display:none}
.bi-panel.on{display:block}
@media (max-width:900px){.bi-shell{grid-template-columns:1fr}
.bi-nav{position:static}}
</style>"""

_SHELL_JS = """<script>
function biGo(id){
  document.querySelectorAll('.bi-panel').forEach(function(p){
    p.classList.toggle('on', p.id === 'bipanel-' + id); });
  document.querySelectorAll('.bi-nav a').forEach(function(a){
    a.classList.toggle('on', a.dataset.bi === id); });
}
</script>"""


def _nav(active) -> str:
    rows = "".join(
        "<a data-bi='" + sid + "' class='" + ("on" if sid == active else "")
        + "' onclick=\"biGo('" + sid + "')\"><b>" + num + "</b>"
        + e(label) + ("<i>core</i>" if sid in MANDATORY else "") + "</a>"
        for sid, num, label, _fn, _q in SCREENS)
    return ("<div class='bi-nav'><p class='bi-meta' "
            "style='margin:2px 0 8px;padding:0 10px'>BUSINESS "
            "INTELLIGENCE</p>" + rows
            + "<p class='bi-meta' style='padding:8px 10px 0'>Costs and "
              "Agent Economics are core: without them this is revenue "
              "reporting, not business intelligence.</p></div>")


def header(ctx=None) -> str:
    """Revenue, contribution and what the machine cost, side by side."""
    c = _d(ctx)
    rev = _f(_d(c.get("revenue")).get("total"))
    tools = _f(c.get("tool_cost"))
    # Read the ONE waterfall from enrich(); computing a second one here
    # with a different cost subset is exactly how this header showed
    # 227,270 above an Executive screen showing 187,270.
    wf = _d(c.get("waterfall"))
    hz = _d(_d(c.get("health")).get("COST_HEALTH"))
    st = _s(hz.get("state")).upper() or "NOT CHECKED"
    tone = {"HEALTHY": "ok", "DEGRADED": "wa", "ERROR": "er"}.get(st, "")
    return ("<div class='bi-card' style='display:flex;flex-wrap:wrap;"
            "gap:10px;align-items:center;justify-content:space-between'>"
            + "<div style='display:flex;gap:8px;flex-wrap:wrap'>"
            + "<span class='bi-pill'>" + e(c.get("period")
                                           or "period not set")
            + "</span><span class='bi-pill'>Revenue "
            + S._money(rev) + "</span><span class='bi-pill'>"
            + "Contribution "
            + S._money(wf.get("contribution")
                       if wf.get("state") == "OK" else None)
            + "</span><span class='bi-pill'>AI and tools "
            + S._money(tools) + "</span></div>"
            + "<span class='bi-pill"
            + ((" bi-pill-" + tone) if tone else "") + "'>Cost health "
            + e(st) + "</span></div>")


def bi_section(ctx=None, *, active="biexec") -> str:
    """The whole BI OS, as one dashboard section.

    A renderer that raises is caught and its panel says so. One screen
    failing must not take the section down, and a blank panel with no
    explanation is what this project keeps having to diagnose.
    """
    c = _d(ctx)
    try:
        c = enrich(c)
    except Exception:                                 # noqa: BLE001
        pass
    panels = []
    for sid, num, label, fn, question in SCREENS:
        try:
            inner = fn(c)
        except Exception as exc:                      # noqa: BLE001
            inner = ("<p class='bi-h1'>" + e(label) + "</p>"
                     + S.empty("This screen could not render",
                               "The renderer raised: " + _s(exc)[:200]
                               + ". The rest of the section is "
                                 "unaffected, and this panel says so "
                                 "rather than showing an empty box."))
        panels.append("<div class='bi-panel"
                      + (" on" if sid == active else "")
                      + "' id='bipanel-" + sid + "'>"
                      + "<p class='bi-meta'>" + num + " &middot; "
                      + e(question) + "</p>" + inner + "</div>")
    return (S.CSS + _SHELL_CSS + "<div class='bi-root'>"
            + header(c)
            + "<div class='bi-shell'>" + _nav(active)
            + "<div>" + "".join(panels) + "</div></div>"
            + "</div>" + _SHELL_JS)


def bi_pages(ctx=None) -> Dict[str, str]:
    """Each screen alone, for a caller that wants one panel."""
    c = _d(ctx)
    try:
        c = enrich(c)
    except Exception:                                 # noqa: BLE001
        pass
    out = {}
    for sid, _num, label, fn, _q in SCREENS:
        try:
            out[sid] = fn(c)
        except Exception as exc:                      # noqa: BLE001
            out[sid] = S.empty(label + " could not render", _s(exc)[:200])
    return out


# ===========================================================================
# 103. EVENTS
# ===========================================================================
def receive(raw) -> Dict[str, Any]:
    """The front door for a cost event from any OS."""
    return COST.receive_cost_event(raw)


def enrich(ctx) -> Dict[str, Any]:
    """Derive what the screens need from what the caller supplied.

    Never overwrites a key the caller set, so a test keeps testing its
    own fixture. Cost totals are derived from usage events rather than
    accepted as a number, because a total nobody can drill into is the
    thing this specification was written against.
    """
    c = dict(_d(ctx))
    events = _l(c.get("usage_events"))
    versions = _l(c.get("pricing_versions"))
    if events and "tool_cost" not in c:
        split = COST.split_media_and_software(events, versions)
        c["tool_cost"] = split.get("software_cost")
        c.setdefault("media_spend", split.get("media_spend"))
        c["_cost_quality"] = split.get("quality")
    if events and "cost_by_os" not in c:
        by: Dict[str, float] = {}
        for ev in events:
            d = _d(ev)
            src = _s(_d(d.get("metadata")).get("source_system")) or "UNATTRIBUTED"
            amt = _f(COST.cost_of(d, versions).get("cost"))
            if amt is not None:
                by[src] = round(by.get(src, 0.0) + amt, 6)
        if by:
            c["cost_by_os"] = by
    if "waterfall" not in c:
        # THE one contribution computation. The header and the Executive
        # screen both read this; they rendered two different numbers for
        # the same fact when each called contribution() with a different
        # subset of the costs.
        c["waterfall"] = COST.contribution(
            revenue=_f(_d(c.get("revenue")).get("total")),
            cogs=_f(c.get("cogs")),
            media=_f(c.get("media_spend")),
            ai=_f(c.get("ai_cost")),
            tools=_f(c.get("tool_cost")),
            cloud=_f(c.get("cloud_cost")),
            other_variable=_f(c.get("other_variable")))
    if "health" not in c:
        w = COST.waste(events, versions) if events else {}
        pct = w.get("waste_pct")
        c["health"] = {
            "DATA_HEALTH": {"state": "NOT CHECKED",
                            "why": ("no freshness report has been "
                                    "supplied by the source systems")},
            "TOOL_HEALTH": {"state": "NOT CHECKED",
                            "why": ("no provider health report has been "
                                    "supplied")},
            "COST_HEALTH": (
                {"state": "NOT CHECKED",
                 "why": ("no usage events yet, so there is nothing to "
                         "judge. That is not the same as spending "
                         "nothing.")}
                if not events else
                {"state": ("ERROR" if (pct or 0) >= 25
                           else "DEGRADED" if (pct or 0) >= 10
                           else "HEALTHY"),
                 "why": (_s(w.get("why"))[:220])}),
        }
    return c


# ===========================================================================
# 104. THE DEFINITION OF DONE
# ===========================================================================
#: Section 104. Twenty-seven things a user must be able to do. verify_bi
#: walks this list; a line that cannot be demonstrated is not done.
DONE_STEPS = (
    "see business revenue",
    "see marketing spend",
    "see AI cost",
    "see API cost",
    "see tool cost",
    "see infrastructure cost",
    "see cost by OS",
    "see cost by agent",
    "see cost by workflow",
    "see cost by campaign",
    "see agent success rate",
    "see cost per successful agent action",
    "see tool utilisation",
    "see tool failures",
    "see wasted spend",
    "set cost budgets",
    "receive cost alerts",
    "see quota consumption",
    "see monthly cost forecast",
    "see estimated versus actual execution cost",
    "compare business value against tool cost",
    "ask why API cost increased",
    "ask which agent costs too much",
    "ask which tool should be optimised",
    "ask what our true acquisition cost is",
    "approve a cost-related action",
    "measure savings after the action and store the learning",
)
