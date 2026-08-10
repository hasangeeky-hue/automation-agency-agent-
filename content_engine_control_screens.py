# -*- coding: utf-8 -*-
"""SYSTEM CONTROL PLANE: the thirteen MVP screens.

Spec sections 3-8, 11-16, 18-25, 28-33, 35-37, 39-48, 51-65, 68-70,
74-77, 97-99, 106-109.

THIRTEEN SCREENS, the MVP list of section 109, no more. Section 6 rules
every status here: icon AND word, never colour alone. The palette is the
shared light system with the system-blue accent for infrastructure.
"""
from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Optional

import content_engine_control_plane as CP

_s, _d, _l, _f = CP._s, CP._d, CP._l, CP._f


def e(x) -> str:
    return html.escape(_s(x), quote=True)


def _n(x, dash="not measured") -> str:
    if x is None or x == "":
        return dash
    try:
        v = float(x)
    except (TypeError, ValueError):
        return e(x)
    return (f"{int(v):,}" if abs(v - int(v)) < 1e-9 else f"{v:,.2f}")


CSS = """<style>
.sc-root{--bg:#F7F8FA;--sf:#FFFFFF;--sf2:#F9FAFB;--bd:#E5E7EB;
--tx:#111827;--tx2:#4B5563;--mu:#9CA3AF;--hu:#2563EB;--ai:#7C3AED;
--ok:#16A34A;--wa:#D97706;--er:#DC2626;--sys:#0284C7;
background:var(--bg);color:var(--tx);border-radius:12px;padding:16px;
font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;
font-size:14px;line-height:1.55}
.sc-root *{box-sizing:border-box}
.sc-h1{font-size:24px;font-weight:600;margin:0 0 4px}
.sc-h2{font-size:16px;font-weight:600;margin:18px 0 8px}
.sc-meta{font-size:12px;color:var(--mu)}
.sc-note{font-size:12px;color:var(--tx2);margin:6px 0 12px;max-width:76ch}
.sc-card{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:14px;margin:0 0 10px}
.sc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
gap:10px;margin:0 0 14px}
.sc-kpi{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:12px 14px}
.sc-kpi span{display:block;font-size:11px;color:var(--mu);
text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px}
.sc-kpi b{display:block;font-size:24px;font-weight:600;line-height:1.15;
font-variant-numeric:tabular-nums}
.sc-kpi i{display:block;font-style:normal;font-size:11px;
color:var(--mu);margin-top:4px}
.sc-tbl{width:100%;border-collapse:collapse;font-size:13px;
background:var(--sf)}
.sc-tbl th{text-align:left;font-size:11px;text-transform:uppercase;
letter-spacing:.05em;color:var(--mu);font-weight:600;padding:8px 10px;
border-bottom:1px solid var(--bd)}
.sc-tbl td{padding:9px 10px;border-bottom:1px solid var(--bd);
color:var(--tx2);vertical-align:top}
.sc-tbl td.num{text-align:right;font-variant-numeric:tabular-nums;
color:var(--tx)}
.sc-scroll{overflow-x:auto;border:1px solid var(--bd);border-radius:10px;
margin:0 0 12px}
.sc-pill{display:inline-block;font-size:10px;font-weight:500;
padding:2px 8px;border-radius:20px;border:1px solid var(--bd);
color:var(--tx2);background:var(--sf2)}
.sc-ok{color:var(--ok)}.sc-wa{color:var(--wa)}.sc-er{color:var(--er)}
.sc-mu{color:var(--mu)}.sc-sys{color:var(--sys)}.sc-ai{color:var(--ai)}
.sc-pill-ok{border-color:var(--ok);color:var(--ok)}
.sc-pill-wa{border-color:var(--wa);color:var(--wa)}
.sc-pill-er{border-color:var(--er);color:var(--er)}
.sc-pill-ai{border-color:var(--ai);color:var(--ai)}
.sc-pill-sys{border-color:var(--sys);color:var(--sys)}
.sc-empty{background:var(--sf);border:1px dashed var(--bd);
border-radius:10px;padding:18px}
.sc-empty b{display:block;font-size:15px;font-weight:600;margin:0 0 6px}
.sc-empty p{margin:0;font-size:13px;color:var(--tx2);max-width:68ch}
.sc-cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.sc-row{display:flex;gap:10px;justify-content:space-between;
align-items:baseline;padding:8px 0;border-bottom:1px solid var(--bd)}
.sc-row:last-child{border-bottom:0}
.sc-node{border:1px solid var(--bd);border-radius:9px;background:var(--sf2);
padding:8px 11px;margin:0 0 6px;cursor:pointer}
.sc-node:hover{border-color:var(--hu)}
.sc-node b{font-size:13px;color:var(--tx)}
.sc-node .sc-meta{margin-left:6px}
.sc-kids{margin-left:26px;border-left:2px solid var(--bd);
padding-left:12px}
.sc-edge{font-size:10px;letter-spacing:.05em;color:var(--mu);
margin:2px 0 2px 26px}
.sc-trace{display:flex;flex-direction:column;gap:0}
.sc-step{display:flex;gap:10px;align-items:baseline;padding:7px 0 7px 14px;
border-left:2px solid var(--bd);font-size:13px}
.sc-step.bad{border-left-color:var(--er)}
.sc-step b{min-width:180px}
@media (max-width:900px){.sc-cols{grid-template-columns:1fr}}
</style>"""

_TONE = {"HEALTHY": "ok", "RUNNING": "sys", "DEGRADED": "wa",
         "FAILED": "er", "OFFLINE": "er", "STALLED": "wa",
         "BACKLOG": "wa", "DISABLED": "", "UNKNOWN": "", "WAITING": "sys",
         "VALID": "ok", "EXPIRED": "er", "EXPIRING_SOON": "wa",
         "PASS": "ok", "WARNING": "wa", "FAIL": "er", "ACTIVE": "er",
         "SUCCESSFUL": "ok", "OK": "ok", "CRITICAL": "er"}


def mark(status) -> str:
    """Section 6: icon plus word, never colour alone."""
    st = _s(status).upper() or "UNKNOWN"
    label = CP.STATUS_MARK.get(st, "? " + st.title())
    # a neutral tone is the base pill, not a dangling modifier class
    _t = _TONE.get(st, "sys")
    return ("<span class='sc-pill" + ((" sc-pill-" + _t) if _t else "") + "'>"
            + e(label if st in CP.STATUS_MARK
                else {"STALLED": "▲ Stalled", "WAITING": "◌ Waiting",
                      "BACKLOG": "▲ Backlog", "PASS": "● Pass",
                      "WARNING": "▲ Warning", "FAIL": "● Fail",
                      "VALID": "● Valid", "EXPIRED": "● Expired",
                      "EXPIRING_SOON": "▲ Expiring",
                      "SUCCESSFUL": "● Done", "OK": "● OK",
                      "ACTIVE": "● Active",
                      "CRITICAL": "● Critical"}.get(st, "? " + st))
            + "</span>")


def kpi(label, value, *, note="") -> str:
    return ("<div class='sc-kpi'><span>" + e(label) + "</span><b>"
            + value + "</b>"
            + ("<i>" + e(note) + "</i>" if note else "") + "</div>")


def empty(title, why) -> str:
    return ("<div class='sc-empty'><b>" + e(title) + "</b><p>" + e(why)
            + "</p></div>")


# ===========================================================================
# 01 SYSTEM OVERVIEW (sections 7-9)
# ===========================================================================
def overview(ctx=None) -> str:
    """Twenty seconds to overall health, with the score expandable."""
    c = _d(ctx)
    comps = _l(c.get("components"))
    edges = _l(c.get("edges"))
    h = c.get("health") or CP.derive_health(comps, edges)
    by_type: Dict[str, List[str]] = {}
    for comp in comps:
        d = _d(comp)
        st = _s(_d(h.get(d.get("id"))).get("status"))
        by_type.setdefault(d.get("component_type"), []).append(st)
    score = CP.health_score({t: sts for t, sts in by_type.items()})
    alerts = CP.dedupe_alerts(c.get("alerts"))
    active = [a for a in alerts if _s(a.get("status")) == "ACTIVE"]

    def frac(t):
        sts = by_type.get(t, [])
        ok = sum(1 for s in sts if s in ("HEALTHY", "RUNNING"))
        return (str(ok) + " / " + str(len(sts))) if sts else "none"

    out = ["<p class='sc-h1'>System Control Plane</p>",
           "<p class='sc-meta'>Environment: "
           + e(c.get("environment") or "PRODUCTION")
           + " &middot; last check: "
           + e(c.get("last_check") or "not recorded") + "</p>"]
    if not comps:
        return "".join(out) + empty(
            "Nothing is registered",
            "The control plane draws what the registry holds. Register "
            "components and dependencies and this screen fills; it does "
            "not scan the codebase and guess.")
    out.append("<div class='sc-kpis'>"
               + kpi("System health",
                     (_n(score.get("score")) + "%") if score.get("score")
                     is not None else "unknown",
                     note=_s(score.get("state") or ""))
               + kpi("Modules", frac("OS"))
               + kpi("Agents", frac("AGENT"))
               + kpi("Workflows", frac("WORKFLOW"))
               + kpi("Connections", frac("API"))
               + kpi("Incidents", _n(len(active), "0"))
               + "</div>")
    out.append("<div class='sc-card'><p class='sc-meta' "
               "style='margin:0 0 6px'>The score is the mean of these "
               "and nothing else</p>")
    for area, val in sorted(_d(score.get("areas")).items()):
        out.append("<div class='sc-row'><span>" + e(area) + "</span><b>"
                   + (_n(val) if val is not None else "unknown")
                   + "</b></div>")
    out.append("</div>")
    out.append("<div class='sc-cols'><div>"
               "<p class='sc-h2'>Business OS health</p>")
    for comp in comps:
        d = _d(comp)
        if d.get("component_type") != "OS":
            continue
        st = _d(h.get(d.get("id")))
        out.append("<div class='sc-row'><span>" + e(d.get("name"))
                   + "</span>" + mark(st.get("status"))
                   + "</div>"
                   + ("<p class='sc-meta'>" + e(st.get("why")) + "</p>"
                      if _s(st.get("status")) not in ("HEALTHY", "")
                      else ""))
    out.append("</div><div><p class='sc-h2'>Infrastructure</p>")
    infra = [x for x in comps if _d(x).get("component_type")
             in ("SERVER", "DATABASE", "QUEUE", "STORAGE")]
    if not infra:
        out.append(empty("No infrastructure registered",
                         "Servers, databases, queues and storage appear "
                         "here once registered."))
    for comp in infra:
        d = _d(comp)
        st = _d(h.get(d.get("id")))
        out.append("<div class='sc-row'><span>" + e(d.get("name"))
                   + "</span>" + mark(st.get("status")) + "</div>")
    out.append("</div></div>")
    out.append("<p class='sc-h2'>Current incidents</p>")
    if not active:
        out.append("<p class='sc-note'>None active. An empty incident "
                   "list with a populated registry means quiet, not "
                   "unmonitored.</p>")
    for a in active[:6]:
        out.append("<div class='sc-row'><span>"
                   + e(a.get("component")) + " &middot; "
                   + e(_s(a.get("type")).replace("_", " ").title())
                   + ("<span class='sc-meta'> x"
                      + str(a.get("occurrences")) + "</span>"
                      if (a.get("occurrences") or 1) > 1 else "")
                   + "</span><span class='sc-pill sc-pill-er'>"
                   + e(a.get("severity")) + "</span></div>")
    return "".join(out)


# ===========================================================================
# 02 WIRING MAP (sections 11-17)
# ===========================================================================
def wiring(ctx=None) -> str:
    """OS to agent to API to infrastructure, as a clickable tree.

    Every node shows its EFFECTIVE health and every edge its
    relationship, because an unlabeled arrow is decoration. The detail
    drawer answers section 16 without leaving the screen.
    """
    c = _d(ctx)
    comps = _l(c.get("components"))
    edges = _l(c.get("edges"))
    # The old system blueprint SVG (every connection in the machine) is
    # still built by the dashboard and passed in; it belongs under the
    # live tree, not in the bin.
    legacy = _s(c.get("legacy_svgs"))
    if not comps:
        return ("<p class='sc-h1'>Wiring Map</p>"
                + empty("Nothing to draw",
                        "The map draws the registry. Register components "
                        "and dependencies first.")
                + legacy)
    h = c.get("health") or CP.derive_health(comps, edges)
    by_id = {_d(x).get("id"): _d(x) for x in comps}
    kids: Dict[str, List[dict]] = {}
    has_parent = set()
    for ed in edges:
        d = _d(ed)
        kids.setdefault(_s(d.get("source")), []).append(d)
        has_parent.add(_s(d.get("target")))
    roots = [cid for cid in by_id if cid not in has_parent]

    def node(cid, depth, seen):
        if depth > 6 or cid in seen:
            return ""
        seen = seen | {cid}
        d = by_id.get(cid)
        if d is None:
            return ""
        st = _d(h.get(cid))
        imp = CP.impact(cid, comps, edges)
        drawer = (e(d.get("name")) + "|" + _s(d.get("component_type"))
                  + "|" + _s(st.get("status")) + "|" + e(st.get("why"))
                  + "|" + e(_s(imp.get("why"))[:200]))
        parts = ["<div class='sc-node' data-sc='" + e(drawer)
                 + "' onclick='scDrawer(this)'><b>" + e(d.get("name"))
                 + "</b> <span class='sc-meta'>"
                 + e(_s(d.get("component_type")).lower()) + "</span> "
                 + mark(st.get("status")) + "</div>"]
        cs = kids.get(cid, ())
        if cs:
            parts.append("<div class='sc-kids'>")
            for ed2 in cs:
                rel = _s(ed2.get("relationship"))
                est = _s(ed2.get("status")).upper()
                parts.append("<div class='sc-edge'>" + e(rel)
                             + (" &middot; edge " + e(est.lower())
                                if est == "FAILED" else "")
                             + (" &middot; "
                                + e(_s(ed2.get("criticality")).lower())
                                if ed2.get("criticality") else "")
                             + "</div>")
                parts.append(node(_s(ed2.get("target")), depth + 1, seen))
            parts.append("</div>")
        return "".join(parts)

    body = "".join(node(r, 0, frozenset())
                   for r in sorted(roots,
                                   key=lambda x: _s(by_id[x].get("name"))))
    return ("<p class='sc-h1'>Wiring Map</p>"
            + "<p class='sc-note'>Click a node for its health, the "
            "reason, and what breaks if it disconnects. A failed "
            "OPTIONAL dependency degrades its dependent; a failed "
            "REQUIRED one fails it, which is why a dead image provider "
            "leaves the factory degraded rather than offline.</p>"
            + body
            + "<div class='sc-card' id='sc-drawer' style='display:none'>"
              "</div>"
            + "<script>function scDrawer(el){var p=el.dataset.sc.split('|');"
              "var d=document.getElementById('sc-drawer');"
              "d.style.display='block';"
              "d.innerHTML='<b>'+p[0]+'</b> <span class=sc-meta>'+p[1]"
              "+'</span><br>Status: '+p[2]+'<br>Why: '+p[3]"
              "+'<br>If disconnected: '+p[4];}</script>"
            + legacy)


# ===========================================================================
# 03 CONNECTION CENTER (sections 18-23)
# ===========================================================================
def connections(ctx=None) -> str:
    """Every wire, live from connectors.status(), plus tests."""
    c = _d(ctx)
    wires = _d(c.get("wires"))
    tests = _d(c.get("connection_tests"))
    # THE PASTE-IN BOARD, restored. The dashboard has always built these
    # connect forms (saveConnect -> /connect, allow-listed keys, masked
    # fields, values write-only) and passes them in as connect_html; the
    # shim dropped them, which left SSH as the only way to add a key.
    forms = _s(c.get("connect_html"))
    forms_html = (("<p class='sc-h2' style='margin-top:18px'>Add, replace "
                   "or disconnect keys</p>" + forms) if forms else "")
    if not wires:
        return ("<p class='sc-h1'>Connections</p>"
                + empty("No wire status supplied",
                        "This screen reads the live connector status "
                        "map. Nothing here is assumed connected.")
                + forms_html)
    on = [k for k, v in wires.items() if v]
    out = ["<p class='sc-h1'>Connections</p>",
           "<div class='sc-kpis'>"
           + kpi("Connected", _n(len(on)))
           + kpi("Not connected", _n(len(wires) - len(on)))
           + "</div>",
           "<p class='sc-note'>Presence only: a key on the Connect board "
           "counts, its value is never read here. A connection that is "
           "present but failing shows in its test, not in this "
           "column.</p>"]
    body = ""
    for name in sorted(wires):
        t = _d(tests.get(name))
        body += ("<tr><td>" + e(name.replace("_", " ")) + "</td>"
                 + "<td>" + mark("HEALTHY" if wires[name]
                                 else "DISABLED") + "</td>"
                 + "<td>" + (mark(t.get("state")) if t else
                             "<span class='sc-meta'>not tested</span>")
                 + "</td>"
                 + "<td class='sc-meta'>"
                 + e(_s(t.get("why"))[:110] if t else "")
                 + "</td></tr>")
    out.append("<div class='sc-scroll'><table class='sc-tbl'><thead><tr>"
               "<th>Wire</th><th>Configured</th><th>Last test</th>"
               "<th>Detail</th></tr></thead><tbody>" + body
               + "</tbody></table></div>")
    out.append(forms_html)
    return "".join(out)


# ===========================================================================
# 04 DATA MAPPING (sections 24-27)
# ===========================================================================
def mapping(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("mappings"))]
    if not rows:
        return ("<p class='sc-h1'>Data Mapping</p>"
                + empty("No mappings declared",
                        "Provider field to transformation to internal "
                        "field to who uses it. Declared per integration; "
                        "an integration with no mapping here is a black "
                        "box, which section 113 forbids."))
    body = "".join(
        "<tr><td>" + e(m.get("provider")) + "</td>"
        + "<td><code>" + e(m.get("provider_field")) + "</code></td>"
        + "<td>" + e(m.get("transformation") or "DIRECT") + "</td>"
        + "<td><code>" + e(m.get("internal_field")) + "</code></td>"
        + "<td>" + e(", ".join(_l(m.get("used_by"))) or "not recorded")
        + "</td>"
        + "<td>" + ("required" if m.get("required") else "optional")
        + "</td></tr>" for m in rows)
    test = _d(c.get("mapping_test"))
    return ("<p class='sc-h1'>Data Mapping</p>"
            + "<div class='sc-scroll'><table class='sc-tbl'><thead><tr>"
            "<th>Provider</th><th>Field</th><th>Transform</th>"
            "<th>Internal</th><th>Used by</th><th>Req</th>"
            "</tr></thead><tbody>" + body + "</tbody></table></div>"
            + (("<p class='sc-h2'>Last mapping test</p><p class='sc-note "
                + ("sc-ok" if test.get("ok") else "sc-er") + "'>"
                + e(test.get("why")) + "</p>") if test else ""))


# ===========================================================================
# 05 AGENT HEALTH (sections 28-34)
# ===========================================================================
def agents(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(a) for a in _l(c.get("agents"))]
    if not rows:
        return ("<p class='sc-h1'>Agent Health</p>"
                + empty("No agent has reported",
                        "Agents emit heartbeats and per-run telemetry. "
                        "Silence here means none has run, which is not "
                        "the same as all healthy."))
    body = ""
    for a in rows:
        hb = CP.heartbeat_state(a.get("heartbeat_interval_s"),
                                a.get("last_seen_s_ago"))
        body += ("<tr><td>" + e(a.get("name"))
                 + "<br><span class='sc-meta'>" + e(a.get("os"))
                 + "</span></td>"
                 + "<td>" + mark(a.get("status") or hb.get("state"))
                 + "</td>"
                 + "<td>" + e(a.get("current_task") or "idle") + "</td>"
                 + "<td class='num'>" + _n(a.get("runs_today")) + "</td>"
                 + "<td class='num'>"
                 + (_n(_f(a.get("success_rate"), 0) * 100) + "%"
                    if a.get("success_rate") is not None
                    else "not measured") + "</td>"
                 + "<td class='num'>" + _n(a.get("tool_calls")) + "</td>"
                 + "<td class='num'>" + _n(a.get("cost_today"))
                 + "</td>"
                 + "<td class='sc-meta'>"
                 + e(a.get("last_error") or "none") + "</td></tr>")
    return ("<p class='sc-h1'>Agent Health</p>"
            + "<p class='sc-note'>A missed heartbeat is DEGRADED after "
            + str(CP.HEARTBEAT_DEGRADED_AFTER) + " intervals and OFFLINE "
            "after " + str(CP.HEARTBEAT_OFFLINE_AFTER) + ". Never seen "
            "is UNKNOWN: a worker that has not started has not "
            "crashed.</p>"
            + "<div class='sc-scroll'><table class='sc-tbl'><thead><tr>"
            "<th>Agent</th><th>Status</th><th>Task</th><th>Runs</th>"
            "<th>Success</th><th>Tool calls</th><th>Cost</th>"
            "<th>Last error</th></tr></thead><tbody>" + body
            + "</tbody></table></div>")


# ===========================================================================
# 06 WORKFLOWS (sections 35-38)
# ===========================================================================
def workflows(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(w) for w in _l(c.get("workflows"))]
    current = _d(c.get("workflow_trace"))
    out = ["<p class='sc-h1'>Workflows</p>"]
    if not rows and not current:
        return "".join(out) + empty(
            "No workflow runs recorded",
            "Runs and their step traces appear here as they execute.")
    if rows:
        body = "".join(
            "<tr><td>" + e(w.get("name")) + "</td>"
            + "<td>" + e(w.get("owner_os")) + "</td>"
            + "<td>" + e(w.get("trigger") or "not recorded") + "</td>"
            + "<td>" + mark(w.get("status")) + "</td>"
            + "<td class='num'>" + _n(w.get("executions")) + "</td>"
            + "<td class='num'>"
            + (_n(_f(w.get("success_rate"), 0) * 100) + "%"
               if w.get("success_rate") is not None else "not measured")
            + "</td>"
            + "<td class='num'>" + _n(w.get("cost")) + "</td></tr>"
            for w in rows)
        out.append("<div class='sc-scroll'><table class='sc-tbl'>"
                   "<thead><tr><th>Workflow</th><th>OS</th>"
                   "<th>Trigger</th><th>Status</th><th>Runs</th>"
                   "<th>Success</th><th>Cost</th></tr></thead><tbody>"
                   + body + "</tbody></table></div>")
    if current:
        tr = CP.workflow_trace(current.get("steps"))
        out.append("<p class='sc-h2'>Execution trace: "
                   + e(current.get("name")) + "</p>"
                   "<div class='sc-trace'>")
        for st in _l(tr.get("steps")):
            d = _d(st)
            bad = _s(d.get("status")).upper() == "FAILED"
            out.append("<div class='sc-step" + (" bad" if bad else "")
                       + "'><b>" + e(d.get("step")) + "</b>"
                       + mark(d.get("status"))
                       + "<span class='sc-meta'>"
                       + (_n(d.get("duration")) + "ms"
                          if d.get("duration") is not None else "")
                       + ((" &middot; " + e(d.get("error")))
                          if bad and d.get("error") else "")
                       + "</span></div>")
        out.append("</div><p class='sc-note'>" + e(tr.get("why"))
                   + "</p>")
        rr = CP.rerun_check(current.get("steps"))
        out.append("<p class='sc-note " + ("sc-ok" if rr["safe"]
                                           else "sc-wa") + "'>Re-run: "
                   + e(rr.get("why")) + "</p>")
    return "".join(out)


# ===========================================================================
# 07 LOOP MAP (sections 39-43)
# ===========================================================================
def loops(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("loops"))]
    if not rows:
        return ("<p class='sc-h1'>Loop Map</p>"
                + empty("No loop is registered",
                        "The content, SEO, paid, email and BI loops "
                        "report their stage and their waiting condition "
                        "here. A loop nobody can see stalls quietly."))
    out = ["<p class='sc-h1'>Loop Map</p>",
           "<p class='sc-note'>WAITING and STALLED are different "
           "findings: one is the design working, the other is it stuck. "
           "The boundary is the declared normal wait times "
           + str(int(CP.STALL_MULTIPLE)) + ", never a feeling.</p>"]
    for r in rows:
        st = CP.loop_state(r)
        out.append("<div class='sc-card'><div class='sc-row'><span><b>"
                   + e(r.get("name")) + "</b> <span class='sc-meta'>"
                   + e(r.get("owner_os")) + "</span></span>"
                   + mark(st.get("state")) + "</div>"
                   + "<p class='sc-meta'>Stage: "
                   + e(st.get("stage") or "not started")
                   + (" &middot; iteration " + _n(r.get("iteration"))
                      if r.get("iteration") is not None else "")
                   + "</p>"
                   + "<p class='sc-note'>" + e(st.get("why"))
                   + "</p></div>")
    return "".join(out)


# ===========================================================================
# 08 N8N (sections 44-48)
# ===========================================================================
def n8n(ctx=None) -> str:
    c = _d(ctx)
    inst = _d(c.get("n8n"))
    flows = [_d(x) for x in _l(inst.get("workflows"))]
    if not inst:
        return ("<p class='sc-h1'>n8n</p>"
                + empty("No n8n instance registered",
                        "Register the instance and map each workflow to "
                        "its owner OS and business purpose. Section 118: "
                        "n8n must not become an invisible second "
                        "architecture outside the OS."))
    out = ["<p class='sc-h1'>n8n</p>",
           "<div class='sc-kpis'>"
           + kpi("Status", mark(inst.get("status")))
           + kpi("Workflows", _n(len(flows), "0"))
           + kpi("Success rate",
                 (_n(_f(inst.get("success_rate"), 0) * 100) + "%"
                  if inst.get("success_rate") is not None
                  else "not measured"))
           + "</div>"]
    if flows:
        body = "".join(
            "<tr><td>" + e(w.get("internal_name"))
            + "<br><span class='sc-meta'>#"
            + e(w.get("external_workflow_id")) + "</span></td>"
            + "<td>" + e(w.get("owner_os") or "UNMAPPED") + "</td>"
            + "<td>" + e(w.get("business_purpose") or "not stated")
            + "</td>"
            + "<td>" + mark(w.get("status")) + "</td>"
            + "<td class='sc-meta'>" + e(w.get("last_execution") or
                                         "never") + "</td></tr>"
            for w in flows)
        out.append("<div class='sc-scroll'><table class='sc-tbl'>"
                   "<thead><tr><th>Workflow</th><th>Owner OS</th>"
                   "<th>Purpose</th><th>Status</th><th>Last run</th>"
                   "</tr></thead><tbody>" + body + "</tbody></table>"
                   "</div>")
        unmapped = [w for w in flows if not w.get("owner_os")]
        if unmapped:
            out.append("<p class='sc-note sc-wa'>" + str(len(unmapped))
                       + " workflow(s) have no owner OS. Unmapped n8n is "
                       "a second architecture nobody governs.</p>")
    return "".join(out)


# ===========================================================================
# 09 INFRASTRUCTURE (sections 51-58)
# ===========================================================================
def infrastructure(ctx=None) -> str:
    c = _d(ctx)
    m = _d(c.get("infra_metrics"))
    st = CP.infra_state(m)
    queues = [_d(q) for q in _l(c.get("queues"))]
    dbs = [_d(x) for x in _l(c.get("databases"))]
    out = ["<p class='sc-h1'>Infrastructure</p>"]
    if not m:
        out.append(empty("No metrics",
                         "The collector reads /proc and the filesystem "
                         "inside the container. Nothing has reported."))
    else:
        out.append("<div class='sc-kpis'>"
                   + kpi("Host", e(m.get("host") or "unknown"))
                   + kpi("Status", mark(st.get("state")))
                   + kpi("Disk", (_n(m.get("disk_pct")) + "%")
                         if m.get("disk_pct") is not None
                         else "unavailable",
                         note=(_n(m.get("disk_total_gb")) + " GB total"
                               if m.get("disk_total_gb") else ""))
                   + kpi("Memory", (_n(m.get("mem_pct")) + "%")
                         if m.get("mem_pct") is not None
                         else "unavailable")
                   + kpi("Load", _n(m.get("load"), "unavailable"),
                         note=(_n(m.get("cpus")) + " cpu(s)"
                               if m.get("cpus") else ""))
                   + kpi("Uptime", (_n(m.get("uptime_days")) + " d")
                         if m.get("uptime_days") is not None
                         else "unavailable")
                   + "</div>")
        out.append("<p class='sc-note'>" + e(st.get("why")) + ". A "
                   "metric this platform cannot supply reads "
                   "unavailable, never zero.</p>")
        if m.get("load_why"):
            out.append("<p class='sc-meta'>" + e(m.get("load_why"))
                       + "</p>")
    if dbs:
        out.append("<p class='sc-h2'>Databases</p>")
        for d in dbs:
            out.append("<div class='sc-row'><span>" + e(d.get("name"))
                       + " <span class='sc-meta'>"
                       + _n(d.get("connections_used"), "?") + " / "
                       + _n(d.get("connections_max"), "?")
                       + " connections</span></span>"
                       + mark(d.get("status")) + "</div>")
    if queues:
        out.append("<p class='sc-h2'>Queues</p>")
        for q in queues:
            qs = CP.queue_state(pending=q.get("pending"),
                                normal_pending=q.get("normal_pending"),
                                workers=q.get("workers"))
            out.append("<div class='sc-row'><span>" + e(q.get("name"))
                       + "</span>" + mark(qs.get("state")) + "</div>"
                       + "<p class='sc-meta'>" + e(qs.get("why"))
                       + "</p>")
    return "".join(out)


# ===========================================================================
# 10 API AND TOOL USAGE (sections 59-63)
# ===========================================================================
def usage(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("api_usage"))]
    if not rows:
        return ("<p class='sc-h1'>API and Tool Usage</p>"
                + empty("No usage recorded",
                        "Every provider call should record a usage "
                        "event. The BI Cost OS reads the same events; "
                        "this screen is the operational view of them."))
    body = "".join(
        "<tr><td>" + e(r.get("provider")) + "</td>"
        + "<td class='num'>" + _n(r.get("requests")) + "</td>"
        + "<td class='num'>"
        + (_n(_f(r.get("success_rate"), 0) * 100) + "%"
           if r.get("success_rate") is not None else "not measured")
        + "</td>"
        + "<td class='num'>" + _n(r.get("avg_latency_ms")) + "</td>"
        + "<td class='num'>"
        + (_n(_f(r.get("quota_used"), 0) * 100) + "%"
           if r.get("quota_used") is not None else "no quota")
        + "</td>"
        + "<td class='num'>" + _n(r.get("cost")) + "</td>"
        + "<td class='sc-meta'>" + e(", ".join(_l(r.get("used_by")))
                                     or "not recorded") + "</td></tr>"
        for r in rows)
    return ("<p class='sc-h1'>API and Tool Usage</p>"
            + "<p class='sc-note'>Rate limits are shown only where the "
            "provider states them; section 63 forbids inventing "
            "one.</p>"
            + "<div class='sc-scroll'><table class='sc-tbl'><thead><tr>"
            "<th>Provider</th><th>Requests</th><th>Success</th>"
            "<th>Latency ms</th><th>Quota</th><th>Cost</th>"
            "<th>Used by</th></tr></thead><tbody>" + body
            + "</tbody></table></div>")


# ===========================================================================
# 11 LOGS (sections 64-67)
# ===========================================================================
def logs(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("logs"))]
    tr = _d(c.get("trace"))
    out = ["<p class='sc-h1'>Logs and Errors</p>"]
    if not rows and not tr:
        return "".join(out) + empty(
            "No log entries supplied",
            "The unified viewer reads what the systems emit. Secrets "
            "are redacted before anything reaches this screen.")
    if rows:
        body = "".join(
            "<tr><td class='sc-meta'>" + e(_s(r.get("at"))[:19]) + "</td>"
            + "<td>" + e(r.get("source")) + "</td>"
            + "<td>" + e(r.get("severity")) + "</td>"
            + "<td>" + e(_s(r.get("message"))[:110]) + "</td>"
            + "<td class='sc-meta'>" + e(r.get("correlation_id") or "")
            + "</td></tr>" for r in rows[:40])
        out.append("<div class='sc-scroll'><table class='sc-tbl'>"
                   "<thead><tr><th>Time</th><th>Source</th><th>Level</th>"
                   "<th>Message</th><th>Correlation</th></tr></thead>"
                   "<tbody>" + body + "</tbody></table></div>")
    if tr:
        out.append("<p class='sc-h2'>Correlation trace: "
                   + e(tr.get("correlation_id")) + "</p>")
        if tr.get("state") == "NOT FOUND":
            out.append("<p class='sc-note sc-wa'>" + e(tr.get("why"))
                       + "</p>")
        else:
            out.append("<div class='sc-trace'>")
            for ev in _l(tr.get("events")):
                d = _d(ev)
                bad = _s(d.get("status")).upper() == "FAILED"
                out.append("<div class='sc-step"
                           + (" bad" if bad else "") + "'><b>"
                           + e(d.get("source")) + "</b>"
                           + e(d.get("event")) + " "
                           + mark(d.get("status") or "OK") + "</div>")
            out.append("</div><p class='sc-note'>" + e(tr.get("why"))
                       + "</p>")
    return "".join(out)


# ===========================================================================
# 12 ALERTS (sections 68-73)
# ===========================================================================
def alerts(ctx=None) -> str:
    c = _d(ctx)
    rows = CP.dedupe_alerts(c.get("alerts"))
    rc = _d(c.get("root_cause"))
    out = ["<p class='sc-h1'>Alerts</p>"]
    if not rows:
        return "".join(out) + empty(
            "No alerts",
            "Alerts deduplicate by type and component: one failure "
            "firing every minute is one incident, not sixty.")
    for a in rows:
        out.append("<div class='sc-card'>"
                   + "<span class='sc-pill sc-pill-er'>"
                   + e(a.get("severity")) + "</span> "
                   + "<span class='sc-pill'>"
                   + e(_s(a.get("type")).replace("_", " ").title())
                   + "</span>"
                   + ("<span class='sc-meta'> seen "
                      + str(a.get("occurrences")) + " time(s)</span>"
                      if (a.get("occurrences") or 1) > 1 else "")
                   + "<p style='margin:8px 0 2px;font-weight:600'>"
                   + e(a.get("component")) + "</p>"
                   + "<p class='sc-meta'>" + e(a.get("why"))
                   + "</p></div>")
    if rc.get("chain"):
        out.append("<p class='sc-h2'>Root cause chain</p>"
                   "<div class='sc-trace'>")
        for link in _l(rc.get("chain")):
            d = _d(link)
            out.append("<div class='sc-step'><b>"
                       + e(d.get("component")) + "</b>"
                       + mark(d.get("status"))
                       + "<span class='sc-meta'>" + e(d.get("why"))
                       + "</span></div>")
        out.append("</div><p class='sc-note'>The last link is the one "
                   "to fix; everything above it is downstream.</p>")
    return "".join(out)


# ===========================================================================
# 13 SECRETS (sections 74-76)
# ===========================================================================
def secrets(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("secrets"))]
    if not rows:
        return ("<p class='sc-h1'>Secrets and Credentials</p>"
                + empty("No credential metadata",
                        "Metadata only: provider, reference, status, "
                        "expiry, and what depends on it. The VALUE of a "
                        "credential never reaches this module; the "
                        "function that builds these rows does not accept "
                        "one as a parameter."))
    body = "".join(
        "<tr><td>" + e(r.get("provider")) + "</td>"
        + "<td><code>" + e(r.get("credential_reference")) + "</code></td>"
        + "<td>" + e(r.get("environment")) + "</td>"
        + "<td>" + mark(r.get("status")) + "</td>"
        + "<td class='sc-meta'>" + e(r.get("expires") or "no expiry")
        + "</td>"
        + "<td class='sc-meta'>" + e(", ".join(_l(r.get("used_by")))
                                     or "nothing recorded")
        + "</td></tr>" for r in rows)
    return ("<p class='sc-h1'>Secrets and Credentials</p>"
            + "<p class='sc-note'>Rotating a credential shows what it "
            "will touch BEFORE the rotation, because the dependency list "
            "is the difference between a rotation and an outage.</p>"
            + "<div class='sc-scroll'><table class='sc-tbl'><thead><tr>"
            "<th>Provider</th><th>Reference</th><th>Env</th>"
            "<th>Status</th><th>Expires</th><th>Used by</th>"
            "</tr></thead><tbody>" + body + "</tbody></table></div>")
