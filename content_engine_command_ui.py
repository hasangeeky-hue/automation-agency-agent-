# -*- coding: utf-8 -*-
"""COMMAND COCKPIT: the one screen.

Spec sections 3-12, 15-19, 25-31, 33-34, 42-55, 60-62, 94, 101-103,
107-109.

ONE CANVAS, TEN ZONES (section 94), exception-first (section 55): when
the machine is healthy it says so in one line and business takes the
room; a problem expands, normal stays compact. Detail lives in the
domain OS behind a deep link (section 75), and no domain table is
rebuilt here (section 109).
"""
from __future__ import annotations

import html
import os
from typing import Any, Dict, Iterable, List, Optional

import content_engine_command_core as CC

_s, _d, _l, _f = CC._s, CC._d, CC._l, CC._f


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


def _money(x, dash="not measured") -> str:
    v = _f(x)
    if v is None:
        return dash
    return "€" + (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}")


CSS = """<style>
.ck-root{--bg:#F7F8FA;--sf:#FFFFFF;--sf2:#F9FAFB;--bd:#E5E7EB;
--tx:#111827;--tx2:#4B5563;--mu:#9CA3AF;--hu:#2563EB;--ai:#7C3AED;
--ok:#16A34A;--wa:#D97706;--er:#DC2626;--sys:#0284C7;
background:var(--bg);color:var(--tx);border-radius:12px;padding:16px;
font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;
font-size:14px;line-height:1.5}
.ck-root *{box-sizing:border-box}
.ck-h1{font-size:22px;font-weight:600;margin:0 0 8px}
.ck-h2{font-size:14px;font-weight:600;margin:0 0 8px}
.ck-meta{font-size:11px;color:var(--mu)}
.ck-note{font-size:12px;color:var(--tx2);max-width:76ch}
.ck-card{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:12px 14px;margin:0 0 10px}
.ck-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;
align-items:start}
.ck-wrap{display:grid;grid-template-columns:1fr 360px;gap:12px;
align-items:start}
.ck-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
gap:10px;margin:0 0 10px}
.ck-kpi{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:10px 12px}
.ck-kpi span{display:block;font-size:10px;color:var(--mu);
text-transform:uppercase;letter-spacing:.05em;margin:0 0 3px}
.ck-kpi b{display:block;font-size:24px;font-weight:600;line-height:1.1;
font-variant-numeric:tabular-nums}
.ck-kpi i{display:block;font-style:normal;font-size:11px;margin-top:3px}
.ck-pill{display:inline-block;font-size:10px;font-weight:500;
padding:2px 8px;border-radius:20px;border:1px solid var(--bd);
color:var(--tx2);background:var(--sf2)}
.ck-ok{color:var(--ok)}.ck-wa{color:var(--wa)}.ck-er{color:var(--er)}
.ck-ai{color:var(--ai)}.ck-mu{color:var(--mu)}.ck-sys{color:var(--sys)}
.ck-pill-ok{border-color:var(--ok);color:var(--ok)}
.ck-pill-wa{border-color:var(--wa);color:var(--wa)}
.ck-pill-er{border-color:var(--er);color:var(--er)}
.ck-pill-ai{border-color:var(--ai);color:var(--ai)}
.ck-row{display:flex;gap:10px;justify-content:space-between;
align-items:baseline;padding:6px 0;border-bottom:1px solid var(--bd)}
.ck-row:last-child{border-bottom:0}
.ck-strip{background:#FEF2F2;border:1px solid var(--er);
border-radius:10px;padding:10px 14px;margin:0 0 12px;display:flex;
gap:12px;align-items:baseline;flex-wrap:wrap}
.ck-strip b{color:var(--er)}
.ck-btn{font:inherit;font-size:12px;font-weight:500;padding:6px 11px;
border-radius:8px;border:1px solid var(--bd);background:var(--sf);
color:var(--tx2);cursor:pointer;margin:0 5px 4px 0}
.ck-btn-hu{background:var(--hu);border-color:var(--hu);color:#fff}
.ck-btn-ai{background:var(--ai);border-color:var(--ai);color:#fff}
.ck-btn-er{border-color:var(--er);color:var(--er)}
.ck-chain{border-left:2px solid var(--bd);padding-left:12px;margin:6px 0}
.ck-chain div{padding:4px 0;font-size:12px;color:var(--tx2)}
.ck-empty{border:1px dashed var(--bd);border-radius:10px;padding:14px;
font-size:12px;color:var(--tx2);background:var(--sf)}
.ck-cmdr{background:var(--sf);border:1px solid var(--ai);
border-radius:10px;padding:14px;position:sticky;top:8px}
@media (max-width:1100px){.ck-wrap,.ck-grid{grid-template-columns:1fr}
.ck-cmdr{position:static}}
</style>"""


def empty(why) -> str:
    return "<div class='ck-empty'>" + e(why) + "</div>"


def deep_link(label, target) -> str:
    return ("<button class='ck-btn' onclick=\"ckOpen('" + e(target)
            + "')\">Open " + e(label) + "</button>")


# ---------------------------------------------------------------------------
# incident strip (47)
# ---------------------------------------------------------------------------
def incident_strip(ctx) -> str:
    inc = [_d(x) for x in _l(_d(ctx).get("incidents"))
           if _s(_d(x).get("severity")).upper() in ("P0", "P1")]
    if not inc:
        return ""
    i = inc[0]
    return ("<div class='ck-strip'><b>" + e(i.get("severity")) + " "
            + e(i.get("title") or i.get("component")) + "</b>"
            + "<span class='ck-note'>" + e(i.get("why")) + "</span>"
            + "<span>" + deep_link("Incident", "incident")
            + "<button class='ck-btn ck-btn-hu'>Quick Fix</button>"
            + "</span></div>")


# ---------------------------------------------------------------------------
# zone A: business pulse (12-14)
# ---------------------------------------------------------------------------
def business_pulse(ctx) -> str:
    b = _d(_d(ctx).get("business"))
    if not b:
        return ("<p class='ck-h2'>Business Pulse</p>"
                + empty("No business snapshot. Revenue, contribution, "
                        "CAC and pipeline come from the BI OS; this "
                        "zone renders what BI reports and invents "
                        "nothing."))
    cells = []
    for key, label in (("revenue", "Revenue"),
                       ("contribution", "Contribution"),
                       ("spend", "Spend"), ("customers", "Customers"),
                       ("cac", "CAC"), ("pipeline", "Pipeline")):
        row = _d(b.get(key))
        val = row.get("value") if row else b.get(key)
        pct = row.get("pct") if row else None
        j = CC.judge_change(key, pct)
        tone = {"GOOD": "ck-ok", "BAD": "ck-er",
                "NEUTRAL": "ck-mu"}.get(j["verdict"], "ck-mu")
        cells.append("<div class='ck-kpi'><span>" + label + "</span><b>"
                     + (_money(val) if key not in ("customers",)
                        else _n(val)) + "</b>"
                     + ("<i class='" + tone + "' title='"
                        + e(j["why"]) + "'>"
                        + ("+" if (_f(pct) or 0) > 0 else "")
                        + _n(pct, "") + "%</i>" if pct is not None
                        else "<i class='ck-mu'>no comparison</i>")
                     + "</div>")
    return ("<p class='ck-h2'>Business Pulse "
            + "<span class='ck-meta'>polarity per metric: CAC up is "
            "bad, spend up is neutral</span></p>"
            + "<div class='ck-kpis'>" + "".join(cells) + "</div>")


# ---------------------------------------------------------------------------
# zone B: machine pulse (15-16, 55)
# ---------------------------------------------------------------------------
def machine_pulse(ctx) -> str:
    m = _d(_d(ctx).get("machine"))
    if not m:
        return ("<p class='ck-h2'>Machine Pulse</p>"
                + empty("No system snapshot from the Control Plane."))
    rows, sick = [], []
    for name, st in m.items():
        status = _s(_d(st).get("status")
                    if isinstance(st, dict) else st).upper()
        why = _s(_d(st).get("why")) if isinstance(st, dict) else ""
        if status in ("HEALTHY", "RUNNING"):
            rows.append(name)
        else:
            sick.append((name, status, why))
    out = ["<p class='ck-h2'>Machine Pulse</p>"]
    if not sick:
        # Exception-first: healthy is ONE line, not half the screen.
        out.append("<div class='ck-card'><span class='ck-pill "
                   "ck-pill-ok'>● System healthy</span> "
                   "<span class='ck-meta'>" + str(len(rows))
                   + " component group(s) reporting, none degraded. "
                   "Normal state stays compact.</span></div>")
    else:
        for name, status, why in sick:
            tone = "er" if status in ("FAILED", "OFFLINE") else "wa"
            out.append("<div class='ck-card'><div class='ck-row'>"
                       "<span><b>" + e(name) + "</b></span>"
                       "<span class='ck-pill ck-pill-" + tone + "'>"
                       + ("▲ " if tone == "wa" else "● ")
                       + e(status.title()) + "</span></div>"
                       + ("<p class='ck-meta'>" + e(why) + "</p>"
                          if why else "")
                       + deep_link("System Control", "system")
                       + "</div>")
        if rows:
            out.append("<p class='ck-meta'>" + str(len(rows))
                       + " other group(s) healthy and kept compact.</p>")
    return "".join(out)


# ---------------------------------------------------------------------------
# zone C: what changed (17-18)
# ---------------------------------------------------------------------------
def what_changed(ctx) -> str:
    feed = CC.change_feed(_l(_d(ctx).get("changes")))
    out = ["<p class='ck-h2'>What Changed</p>"]
    if not feed:
        return "".join(out) + empty(
            "No change computed. The feed compares this period against "
            "the previous one per metric; without two periods there is "
            "no change to report, and none is invented.")
    for c in feed:
        tone = {"GOOD": "ck-ok", "BAD": "ck-er"}.get(c["verdict"],
                                                     "ck-mu")
        arrow = "↑" if (c.get("pct") or 0) > 0 else "↓"
        out.append("<div class='ck-row'><span><b class='" + tone + "'>"
                   + arrow + " " + _n(c.get("pct"), "?") + "%</b> "
                   + e(c.get("metric"))
                   + " <span class='ck-meta'>" + e(c.get("source"))
                   + " &middot; cause "
                   + e(_s(c.get("cause_status")).lower())
                   + "</span></span>"
                   + "<span class='ck-meta'>" + _n(c.get("before"))
                   + " → " + _n(c.get("after")) + "</span></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# zone D: decision queue (19-23)
# ---------------------------------------------------------------------------
def decision_queue(ctx) -> str:
    ranked = CC.rank_decisions(_l(_d(ctx).get("decisions")))
    out = ["<p class='ck-h2'>Decision Queue</p>"]
    if not ranked["ranked"]:
        out.append(empty("Nothing needs a decision. "
                         + ("BUT " + str(ranked["incomplete"])
                            + " incomplete card(s) were refused: a "
                            "decision without evidence, cost and a "
                            "measurement plan cannot be approved."
                            if ranked["incomplete"] else
                            "An empty queue with fresh data means "
                            "quiet, not unmonitored.")))
        return "".join(out)
    for d in ranked["ranked"][:4]:
        ev = d.get("expected_value")
        out.append(
            "<div class='ck-card'>"
            + "<span class='ck-pill ck-pill-ai'>"
            + e(_s(d.get("type")).replace("_", " ").title()) + "</span>"
            + " <span class='ck-meta'>score " + _n(d.get("score"))
            + " &middot; confidence "
            + _n((_f(d.get("confidence"), 0) or 0) * 100) + "%"
            + " &middot; risk " + e(_s(d.get("risk")).lower())
            + "</span>"
            + "<p style='margin:6px 0 2px;font-weight:600'>"
            + e(d.get("what")) + "</p>"
            + "<p class='ck-meta'>" + e(d.get("why")) + "</p>"
            + "<div class='ck-row'><span>Expected net</span><b>"
            + (_money(_d(ev).get("mid")) if isinstance(ev, dict)
               else _money(ev)) + " less "
            + (_money(_d(d.get("expected_cost")).get("mid"))
               if isinstance(d.get("expected_cost"), dict)
               else _money(d.get("expected_cost"))) + "</b></div>"
            + "<div class='ck-row'><span>Executes in</span><b>"
            + e(d.get("target_system")) + "</b></div>"
            + "<div class='ck-row'><span>Measured by</span>"
            + "<span class='ck-meta'>" + e(d.get("measurement_plan"))
            + "</span></div>"
            + "<button class='ck-btn ck-btn-er'>Reject</button>"
            + "<button class='ck-btn'>Modify</button>"
            + "<button class='ck-btn ck-btn-hu'>Approve Plan</button>"
            + "</div>")
    if ranked["incomplete"]:
        out.append("<p class='ck-meta'>" + str(ranked["incomplete"])
                   + " DECISION_INCOMPLETE card(s) held back.</p>")
    return "".join(out)


# ---------------------------------------------------------------------------
# zone E: quick fix (25-27)
# ---------------------------------------------------------------------------
def quick_fix_center(ctx) -> str:
    fixes = [f for f in (_d(x) for x in _l(_d(ctx).get("quick_fixes")))
             if f.get("ok")]
    out = ["<p class='ck-h2'>Quick Fix</p>"]
    if not fixes:
        return "".join(out) + empty(
            "No safe fix is on offer. Fixes appear with their current "
            "state, proposed state, risk, rollback and verification; a "
            "bare [Fix] button is forbidden.")
    for f in fixes[:4]:
        tone = {"SAFE": "ok", "HIGH_RISK": "er"}.get(f.get("risk"), "wa")
        out.append("<div class='ck-card'>"
                   + "<span class='ck-pill ck-pill-" + tone + "'>"
                   + e(_s(f.get("risk")).replace("_", " ").lower())
                   + "</span>"
                   + "<p style='margin:6px 0 2px;font-weight:600'>"
                   + e(_s(f.get("type")).replace("_", " ").title())
                   + "</p>"
                   + "<div class='ck-row'><span>Now</span>"
                   "<span class='ck-meta'>" + e(f.get("current_state"))
                   + "</span></div>"
                   + "<div class='ck-row'><span>After</span>"
                   "<span class='ck-meta'>" + e(f.get("proposed_state"))
                   + "</span></div>"
                   + "<div class='ck-row'><span>Rollback</span>"
                   "<span class='ck-meta'>" + e(f.get("rollback"))
                   + "</span></div>"
                   + "<div class='ck-row'><span>Verified by</span>"
                   "<span class='ck-meta'>" + e(f.get("verification"))
                   + "</span></div>"
                   + "<button class='ck-btn ck-btn-hu'>Apply Fix"
                   "</button></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# zone F: loops and initiatives (28-32)
# ---------------------------------------------------------------------------
def loop_monitor(ctx) -> str:
    loops = [_d(x) for x in _l(_d(ctx).get("loops"))]
    out = ["<p class='ck-h2'>Loops</p>"]
    if not loops:
        return "".join(out) + empty(
            "No loop has reported. The content, paid, SEO and email "
            "loops report their stage here; a loop nobody can see "
            "stalls quietly.")
    for lp in loops[:4]:
        st = _s(lp.get("status")).upper()
        tone = {"STALLED": "wa", "FAILED": "er",
                "HEALTHY": "ok", "RUNNING": "ok",
                "WAITING": "ok"}.get(st, "")
        out.append("<div class='ck-row'><span><b>" + e(lp.get("name"))
                   + "</b> <span class='ck-meta'>"
                   + e(lp.get("owner_os")) + " &middot; stage "
                   + e(lp.get("current_stage") or "?") + "</span></span>"
                   + "<span class='ck-pill ck-pill-" + tone + "'>"
                   + ("▲ " if tone == "wa" else "● ") + e(st.title())
                   + "</span></div>"
                   + (("<p class='ck-meta'>" + e(lp.get("why"))
                       + "</p>") if lp.get("why") and st == "STALLED"
                      else ""))
    return "".join(out)


def initiatives(ctx) -> str:
    rows = [_d(x) for x in _l(_d(ctx).get("initiatives"))]
    out = ["<p class='ck-h2'>Initiatives</p>"]
    if not rows:
        return "".join(out) + empty(
            "No initiative in flight. An approved decision becomes one "
            "and stays open until its TARGET METRIC answers, not until "
            "its actions execute.")
    for r in rows[:3]:
        h = CC.initiative_health(
            target_metric=r.get("target_metric"),
            target_value=r.get("target_value"),
            current_value=r.get("current_value"),
            direction=r.get("direction", "BELOW"),
            actions_done=r.get("actions_done", 0),
            actions_total=r.get("actions_total", 0),
            observing=bool(r.get("observing")))
        tone = {"ON_TRACK": "ok", "COMPLETED": "ok", "AT_RISK": "wa",
                "WAITING": "", "OFF_TRACK": "er",
                "FAILED": "er"}.get(h["state"], "")
        out.append("<div class='ck-card'><div class='ck-row'><span><b>"
                   + e(r.get("name")) + "</b></span>"
                   + "<span class='ck-pill ck-pill-" + tone + "'>"
                   + e(h["state"].replace("_", " ").title())
                   + "</span></div>"
                   + "<p class='ck-meta'>" + e(h["why"]) + "</p></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# cost pulse (42-44) and data health (45-46)
# ---------------------------------------------------------------------------
def cost_pulse(ctx) -> str:
    c = _d(_d(ctx).get("cost"))
    out = ["<p class='ck-h2'>Cost Pulse</p>"]
    if not c:
        return "".join(out) + empty(
            "No cost snapshot. Media, AI/API and infrastructure spend "
            "come from the BI Cost OS; nothing here is estimated in "
            "their absence.")
    out.append("<div class='ck-row'><span>Media today</span><b>"
               + _money(c.get("media_today")) + "</b></div>"
               "<div class='ck-row'><span>AI and API today</span><b>"
               + _money(c.get("ai_api_today")) + "</b></div>"
               "<div class='ck-row'><span>Infrastructure</span><b>"
               + _money(c.get("infra_today")) + "</b></div>"
               "<div class='ck-row'><span>Month projection</span><b>"
               + _money(c.get("projection")) + "</b></div>")
    b = _f(c.get("budget"))
    p = _f(c.get("projection"))
    if b and p:
        ok = p <= b
        out.append("<p class='ck-meta " + ("ck-ok" if ok else "ck-er")
                   + "'>" + ("● On track against " if ok
                             else "● Projected OVER a budget of ")
                   + _money(b) + "</p>")
    return "".join(out)


def data_health_bar(ctx) -> str:
    d = _d(_d(ctx).get("data_health"))
    out = ["<p class='ck-h2'>Data Health</p>"]
    if not d:
        return "".join(out) + empty("No freshness report.")
    cells = []
    for src, st in sorted(d.items()):
        stt = _s(_d(st).get("state") if isinstance(st, dict)
                 else st).upper()
        tone = {"FRESH": "ok", "OK": "ok", "DELAYED": "wa",
                "STALE": "wa", "ERROR": "er"}.get(stt, "")
        cells.append("<span class='ck-pill ck-pill-" + tone + "'>"
                     + e(src) + " "
                     + ("●" if tone == "ok" else "▲" if tone == "wa"
                        else "●" if tone == "er" else "?") + "</span>")
    out.append("<div class='ck-card'>" + " ".join(cells)
               + "<p class='ck-meta' style='margin:8px 0 0'>A delayed "
               "source reduces the confidence of every decision built "
               "on it, and the affected cards say so.</p></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# zone G: the commander (33-34, 80-83)
# ---------------------------------------------------------------------------
def commander_panel(ctx) -> str:
    ans = CC.commander("situation", _d(ctx).get("snapshots"))
    out = ["<div class='ck-cmdr'><p class='ck-h2 ck-ai'>✦ Commander</p>"]
    if ans["state"] != "OK":
        out.append("<p class='ck-note'>" + e(ans["why"]) + "</p></div>")
        return "".join(out)
    out.append("<p class='ck-meta'>SITUATION</p><p class='ck-note'>"
               + e(ans["situation"]) + "</p>")
    if ans["top_risks"]:
        out.append("<p class='ck-meta'>MAIN RISK</p><p class='ck-note'>"
                   + e(_d(ans["top_risks"][0]).get("title")
                       or ans["top_risks"][0]) + "</p>")
    if ans["top_opportunities"]:
        out.append("<p class='ck-meta'>TOP OPPORTUNITY</p>"
                   "<p class='ck-note'>"
                   + e(_d(ans["top_opportunities"][0]).get("title")
                       or ans["top_opportunities"][0]) + "</p>")
    out.append("<p class='ck-meta'>SYSTEM</p><p class='ck-note'>"
               + e(ans["system_diagnosis"]) + "</p>")
    if ans["confidence"] == "REDUCED":
        out.append("<p class='ck-meta ck-wa'>CONFIDENCE REDUCED: no "
                   "snapshot for "
                   + e(", ".join(ans["data_limitations"])) + "</p>")
    out.append("<button class='ck-btn ck-btn-ai'>✦ What Should I Do?"
               "</button>"
               "<button class='ck-btn ck-btn-ai'>✦ What Is Broken?"
               "</button>"
               "<button class='ck-btn ck-btn-ai'>✦ Where Am I Losing "
               "Money?</button>")
    out.append("<p class='ck-meta'>At most "
               + str(CC.MAX_RECOMMENDATIONS)
               + " ranked actions, from snapshots only, never from "
               "model memory.</p></div>")
    return "".join(out)


# ---------------------------------------------------------------------------
# the section
# ---------------------------------------------------------------------------
CONTRACT = os.path.join("docs", "command", "cockpit.md")


def check_contract() -> Dict[str, Any]:
    ok = os.path.exists(CONTRACT)
    return {"ok": ok,
            "why": ("the cockpit contract exists" if ok else
                    "section 101: no contract, no cockpit. Missing "
                    + CONTRACT)}


ZONES = (("Business Pulse", business_pulse),
         ("Machine Pulse", machine_pulse),
         ("What Changed", what_changed),
         ("Decision Queue", decision_queue),
         ("Quick Fix", quick_fix_center),
         ("Loops", loop_monitor),
         ("Initiatives", initiatives),
         ("Cost Pulse", cost_pulse),
         ("Data Health", data_health_bar))


def decision_log_zone(ctx) -> str:
    """Every decision that LANDED, dated: approvals, budget changes,
    publishes. Suggestions live in the queue; deeds live here."""
    lg = _d(_d(ctx).get("log"))
    head = "<div class='ck-card'><p class='ck-h'>Decision Log</p>"
    if not lg.get("has_data"):
        return (head + empty("No decision recorded yet. Approve, set a "
                             "budget or publish and it lands here, "
                             "dated.") + "</div>")
    rows = ""
    for r in _l(lg.get("rows"))[:8]:
        d = _d(r)
        rows += ("<div class='ck-row'><span class='ck-meta'>"
                 + e(_s(d.get("at"))[:16].replace("T", " ")) + "</span> "
                 + "<b>" + e(_s(d.get("action"))) + "</b> "
                 + e(_s(d.get("title"))[:60])
                 + ("<span class='ck-meta'> " + e(_s(d.get("outcome"))[:40])
                    + "</span>" if d.get("outcome") else "")
                 + "</div>")
    spark = ""
    try:
        import content_engine_ui_kit as UK
        if _l(lg.get("series")):
            spark = UK.sparkline(_l(lg.get("series")),
                                 source="decision log")
    except Exception:                                 # noqa: BLE001
        spark = ""
    return (head + spark + rows + "<p class='ck-meta'>"
            + _s(lg.get("total")) + " recorded in total</p></div>")


def connections_zone(ctx) -> str:
    """Which wires are live, from the same connector status map the
    Control Plane reads. Presence only; a value never renders here."""
    w = _d(_d(ctx).get("wires"))
    head = "<div class='ck-card'><p class='ck-h'>Connections</p>"
    if not w:
        return (head + empty("No wire status supplied on this render. "
                             "The Control Plane's Connections screen is "
                             "the full view.") + "</div>")
    on = sorted(k for k, v in w.items() if v)
    off = sorted(k for k, v in w.items() if not v)
    body = ("<p><b>" + str(len(on)) + "</b> live &middot; <b>"
            + str(len(off)) + "</b> not connected</p>"
            + ("<p class='ck-meta'>not connected: "
               + e(", ".join(k.replace("_", " ") for k in off[:6]))
               + ("&hellip;" if len(off) > 6 else "") + "</p>"
               if off else "<p class='ck-meta'>every wire is live</p>")
            + deep_link("Connections", "system"))
    return head + body + "</div>"


def cockpit_section(ctx=None) -> str:
    """The one screen. A failing zone reports inside its own card."""
    c = _d(ctx)
    try:
        c = enrich(c)
    except Exception:                                 # noqa: BLE001
        pass

    def z(fn):
        try:
            return fn(c)
        except Exception as exc:                      # noqa: BLE001
            return ("<div class='ck-card ck-er'>zone failed: "
                    + e(_s(exc)[:150]) + ". The rest of the cockpit is "
                    "unaffected.</div>")

    bar = ("<div class='ck-card' style='display:flex;flex-wrap:wrap;"
           "gap:8px;align-items:center;justify-content:space-between'>"
           "<div><span class='ck-pill'>"
           + e(c.get("workspace") or "Anthropos")
           + "</span> <span class='ck-pill'>"
           + e(c.get("period") or "Last 30 days") + "</span></div>"
           "<div><span class='ck-pill'>Cost today "
           + _money(_d(c.get("cost")).get("ai_api_today"))
           + "</span></div></div>")
    left = ("<div>" + z(business_pulse)
            + "<div class='ck-grid'><div>" + z(what_changed) + "</div>"
            + "<div>" + z(machine_pulse) + "</div></div>"
            + "<div class='ck-grid'><div>" + z(decision_queue) + "</div>"
            + "<div>" + z(quick_fix_center) + "</div></div>"
            + "<div class='ck-grid'><div>" + z(loop_monitor) + "</div>"
            + "<div>" + z(initiatives) + "</div></div>"
            + "<div class='ck-grid'><div>" + z(cost_pulse) + "</div>"
            + "<div>" + z(data_health_bar) + "</div></div>"
            + "<div class='ck-grid'><div>" + z(decision_log_zone) + "</div>"
            + "<div>" + z(connections_zone) + "</div></div>"
            + "</div>")
    return (CSS + "<div class='ck-root'>"
            + incident_strip(c) + bar
            + "<div class='ck-wrap'>" + left
            + z(commander_panel) + "</div>"
            + "</div><script>function ckOpen(t){"
              "var m={incident:'system'};var id=m[t]||t;"
              "if(window.nav){nav(id);}else{location.hash='#'+id;}}"
              "</script>")


def cockpit_pages(ctx=None) -> Dict[str, str]:
    """Kept for the old caller. One page now: the cockpit IS one page."""
    return {"ckcmd": cockpit_section(ctx)}


def enrich(ctx) -> Dict[str, Any]:
    """Machine reality from the Control Plane, live. Business reality
    only from what the caller (BI) supplies: nothing invented."""
    c = dict(_d(ctx))
    if "machine" not in c:
        try:
            import content_engine_control_ui as XU
            import content_engine_control_plane as XP
            reg = XU.enrich({})
            h = reg.get("health") or {}
            by_type: Dict[str, List[str]] = {}
            comps = {_d(x).get("id"): _d(x)
                     for x in _l(reg.get("components"))}
            sick = {}
            for cid, st in h.items():
                d = comps.get(cid, {})
                t = _s(d.get("component_type"))
                by_type.setdefault(t, []).append(_s(_d(st).get("status")))
                if _s(_d(st).get("status")) in ("DEGRADED", "FAILED",
                                                "OFFLINE"):
                    sick[_s(d.get("name"))] = {"status":
                                               _d(st).get("status"),
                                               "why": _d(st).get("why")}
            if "wires" not in c and reg.get("wires"):
                c["wires"] = reg.get("wires")
            if sick:
                c["machine"] = sick
            else:
                c["machine"] = {"All systems":
                                {"status": "HEALTHY",
                                 "why": str(len(h)) + " components "
                                 "derived healthy"}}
        except Exception:                             # noqa: BLE001
            pass
    if "snapshots" not in c:
        sn = {}
        for key in ("business", "cost", "changes", "risks",
                    "opportunities", "incidents", "loops",
                    "initiatives", "decisions", "quick_fixes"):
            if c.get(key):
                sn[key] = c[key]
        if c.get("machine"):
            sn["system"] = c["machine"]
        if c.get("data_health"):
            sn["data_health"] = c["data_health"]
        if sn:
            c["snapshots"] = sn
    return c
