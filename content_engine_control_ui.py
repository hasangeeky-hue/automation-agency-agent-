# -*- coding: utf-8 -*-
"""SYSTEM CONTROL PLANE: the section, assembled.

Spec sections 3-4, 95, 99, 109-111, 119.

THIRTEEN SCREENS, the MVP list of section 109. The nav and the panels
derive from ONE list, and enrich() seeds the registry from what this
codebase actually runs: the six OS modules, the factory's four agents,
every wire in connectors.status(), and this box's own /proc. The map is
real on first render, not a demo.

WHY THIS FILE IS NOT content_engine_system_boards.py: that name is taken
by the module this replaces and the dashboard imports it at line 4357.
The old name becomes a shim, the same pattern as the factory and BI
replacements, after one of those was destroyed by writing over it.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import content_engine_control_plane as CP
import content_engine_control_screens as S

_s, _d, _l, _f = CP._s, CP._d, CP._l, CP._f
e = S.e

# ===========================================================================
# 109. THE THIRTEEN
# ===========================================================================
SCREENS: Tuple[Tuple[str, str, str, Callable, str], ...] = (
    ("scover", "01", "System Overview", S.overview,
     "Is the machine healthy, in twenty seconds?"),
    ("scwire", "02", "Wiring Map", S.wiring,
     "What is connected to what, and what breaks if it goes?"),
    ("scconn", "03", "Connections", S.connections,
     "Which wires are live, and do they actually work?"),
    ("scmap", "04", "Data Mapping", S.mapping,
     "How does a provider field become an internal one?"),
    ("scagents", "05", "Agent Health", S.agents,
     "Are the agents alive, and what are they doing?"),
    ("scwf", "06", "Workflows", S.workflows,
     "Which runs failed, and at which step?"),
    ("scloops", "07", "Loop Map", S.loops,
     "Which loops are moving, and which are stuck?"),
    ("scn8n", "08", "n8n", S.n8n,
     "Is n8n an owned part of the OS or a shadow architecture?"),
    ("scinfra", "09", "Infrastructure", S.infrastructure,
     "Is the box itself healthy?"),
    ("scusage", "10", "API and Tool Usage", S.usage,
     "What is being called, how often, at what cost?"),
    ("sclogs", "11", "Logs and Errors", S.logs,
     "What happened, and can one id trace it end to end?"),
    ("scalerts", "12", "Alerts", S.alerts,
     "What needs a human, and what is the root?"),
    ("scsecrets", "13", "Secrets", S.secrets,
     "What credentials exist, and what depends on each?"),
)


def check_screens() -> Dict[str, Any]:
    problems = []
    for sid, _n, _lab, fn, _q in SCREENS:
        if not callable(fn):
            problems.append(sid + ": no renderer")
    ids = [x[0] for x in SCREENS]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        problems.append("duplicate id: " + ", ".join(dupes))
    if len(SCREENS) != 13:
        problems.append("the MVP is thirteen screens; found "
                        + str(len(SCREENS)))
    return {"ok": not problems, "problems": problems,
            "count": len(SCREENS),
            "why": ("thirteen screens, one list"
                    if not problems else "; ".join(problems))}


_SHELL_CSS = """<style>
.sc-shell{display:grid;grid-template-columns:248px 1fr;gap:14px;
align-items:start}
.sc-nav{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:10px;position:sticky;top:8px}
.sc-nav a{display:flex;gap:9px;align-items:baseline;padding:7px 10px;
border-radius:8px;color:var(--tx2);font-size:13px;cursor:pointer}
.sc-nav a b{font-size:11px;color:var(--mu);font-weight:500;
font-variant-numeric:tabular-nums}
.sc-nav a:hover{background:var(--sf2);color:var(--tx)}
.sc-nav a.on{background:rgba(2,132,199,.08);color:var(--sys);
font-weight:600}
.sc-nav a.on b{color:var(--sys)}
.sc-panel{display:none}
.sc-panel.on{display:block}
@media (max-width:900px){.sc-shell{grid-template-columns:1fr}
.sc-nav{position:static}}
</style>"""

_SHELL_JS = """<script>
function scGo(id){
  document.querySelectorAll('.sc-panel').forEach(function(p){
    p.classList.toggle('on', p.id === 'scpanel-' + id); });
  document.querySelectorAll('.sc-nav a').forEach(function(a){
    a.classList.toggle('on', a.dataset.sc === id); });
}
</script>"""


def _nav(active) -> str:
    rows = "".join(
        "<a data-sc='" + sid + "' class='"
        + ("on" if sid == active else "")
        + "' onclick=\"scGo('" + sid + "')\"><b>" + num + "</b>"
        + e(label) + "</a>" for sid, num, label, _fn, _q in SCREENS)
    return ("<div class='sc-nav'><p class='sc-meta' "
            "style='margin:2px 0 8px;padding:0 10px'>SYSTEM CONTROL"
            "</p>" + rows
            + "<p class='sc-meta' style='padding:8px 10px 0'>BI asks "
              "whether the business is healthy. This asks whether the "
              "machine running it is.</p></div>")


def system_section(ctx=None, *, active="scover") -> str:
    """The whole control plane as one section. A failing renderer is
    caught and its panel says so; the rest of the section survives."""
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
            inner = ("<p class='sc-h1'>" + e(label) + "</p>"
                     + S.empty("This screen could not render",
                               "The renderer raised: " + _s(exc)[:200]
                               + ". The rest of the section is "
                                 "unaffected."))
        panels.append("<div class='sc-panel"
                      + (" on" if sid == active else "")
                      + "' id='scpanel-" + sid + "'>"
                      + "<p class='sc-meta'>" + num + " &middot; "
                      + e(question) + "</p>" + inner + "</div>")
    return (S.CSS + _SHELL_CSS + "<div class='sc-root'>"
            + "<div class='sc-shell'>" + _nav(active)
            + "<div>" + "".join(panels) + "</div></div>"
            + "</div>" + _SHELL_JS)


def system_pages(ctx=None) -> Dict[str, str]:
    c = _d(ctx)
    try:
        c = enrich(c)
    except Exception:                                 # noqa: BLE001
        pass
    out = {}
    for sid, _n, label, fn, _q in SCREENS:
        try:
            out[sid] = fn(c)
        except Exception as exc:                      # noqa: BLE001
            out[sid] = S.empty(label + " could not render",
                               _s(exc)[:200])
    return out


# ===========================================================================
# THE REAL REGISTRY (sections 82-83, seeded from this codebase)
# ===========================================================================
#: The six OS modules this engine actually ships, and their real module
#: files. ONE list; the registry, the overview and the wiring map all
#: derive from it.
OS_MODULES = (
    ("SEO OS", "content_engine_seo_boards"),
    ("Media Buying OS", "content_engine_media_center"),
    ("Content Factory", "content_engine_factory_ui"),
    ("Email OS", "content_engine_os"),
    ("BI OS", "content_engine_bi_ui"),
    ("System Control", "content_engine_control_ui"),
)

#: Which wires each OS depends on, by connectors.status() key. OPTIONAL
#: unless the OS is useless without it.
_OS_WIRES = {
    "SEO OS": (("google_gsc_ga4", "REQUIRED"),
               ("serper_search", "OPTIONAL"),
               ("seo_backlinks", "OPTIONAL"),
               ("claude_api", "OPTIONAL")),
    "Media Buying OS": (("ads_api", "OPTIONAL"),
                        ("claude_api", "OPTIONAL")),
    "Content Factory": (("claude_api", "REQUIRED"),
                        ("image_gen", "OPTIONAL"),
                        ("video_gen", "OPTIONAL"),
                        ("wordpress_publish", "OPTIONAL")),
    "Email OS": (("email_send", "REQUIRED"),
                 ("email_reply_inbound", "OPTIONAL")),
    "BI OS": (("google_gsc_ga4", "OPTIONAL"),),
}


def build_registry(wires=None) -> Dict[str, Any]:
    """The registry, from what actually exists.

    An OS whose module imports is HEALTHY at registration; a wire that
    connectors.status() reports absent is DISABLED, not FAILED, because
    unconfigured and broken need different responses. Nothing here is
    invented: every node corresponds to a module or a wire in this
    codebase.
    """
    comps, edges = [], []
    for name, mod in OS_MODULES:
        try:
            __import__(mod)
            st = "HEALTHY"
        except Exception:                             # noqa: BLE001
            st = "FAILED"
        comps.append(CP.component(name, "OS", status=st,
                                  version=mod)["component"])
    try:
        import content_engine_factory_agents as FA
        for a in FA.AGENTS:
            comps.append(CP.component(a.title() + " Agent", "AGENT",
                                      owner_os="Content Factory",
                                      status="HEALTHY")["component"])
            edges.append(CP.dependency(
                CP._id("Content Factory", "OS"),
                CP._id(a.title() + " Agent", "AGENT"),
                relationship="USES", criticality="OPTIONAL",
                status="HEALTHY")["edge"])
    except Exception:                                 # noqa: BLE001
        pass
    w = _d(wires)
    for wire, present in sorted(w.items()):
        comps.append(CP.component(wire, "API",
                                  status=("HEALTHY" if present
                                          else "DISABLED"))["component"])
    for os_name, deps in _OS_WIRES.items():
        for wire, crit in deps:
            if wire in w:
                edges.append(CP.dependency(
                    CP._id(os_name, "OS"), CP._id(wire, "API"),
                    relationship="USES", criticality=crit,
                    status="HEALTHY")["edge"])
    m = CP.local_metrics()
    comps.append(CP.component("VPS " + _s(m.get("host")), "SERVER",
                              status=CP.infra_state(m)["state"]
                              if any(v is not None for k, v in m.items()
                                     if k != "host") else "UNKNOWN"
                              )["component"])
    comps.append(CP.component("PostgreSQL", "DATABASE",
                              status="UNKNOWN")["component"])
    return {"components": comps, "edges": edges, "metrics": m}


def enrich(ctx) -> Dict[str, Any]:
    """Fill the screens from the live system. Caller keys are never
    overwritten, so tests keep testing their fixtures."""
    c = dict(_d(ctx))
    if "wires" not in c:
        try:
            import content_engine_connectors as CN
            c["wires"] = CN.status()
        except Exception:                             # noqa: BLE001
            c["wires"] = {}
    if "components" not in c:
        reg = build_registry(c.get("wires"))
        c["components"] = reg["components"]
        c["edges"] = c.get("edges") or reg["edges"]
        c.setdefault("infra_metrics", reg["metrics"])
    if "infra_metrics" not in c:
        c["infra_metrics"] = CP.local_metrics()
    if "health" not in c:
        c["health"] = CP.derive_health(c.get("components"),
                                       c.get("edges"))
    return c


# ===========================================================================
# 119. THE DEFINITION OF DONE (43 steps)
# ===========================================================================
DONE_STEPS = (
    "open System Overview", "see every OS status", "see agent status",
    "see workflow status", "see active incidents",
    "add an API connection", "test it", "see permission status",
    "see hidden credential metadata", "see where a connection is used",
    "see provider to internal data mapping", "test a mapping",
    "open the Wiring Map", "trace OS to agent to API to server",
    "click every node", "see dependency health",
    "see dependent components", "see agent runs", "see agent usage",
    "see agent cost", "see agent errors",
    "see a workflow execution trace", "retry a failed workflow safely",
    "see a loop stage", "detect a stalled loop", "see n8n health",
    "see n8n workflow runs", "see VPS health", "see CPU or load",
    "see memory", "see disk", "see databases", "see queues",
    "see API calls", "see quotas", "see API and tool costs",
    "search logs", "trace a correlation id", "see alerts",
    "understand a root cause", "understand dependency impact",
    "ask the System Analyst what is wrong",
    "receive an evidence-backed diagnosis",
)
