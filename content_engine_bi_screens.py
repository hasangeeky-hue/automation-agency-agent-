# -*- coding: utf-8 -*-
"""BI OS: the nine MVP screens.

Spec sections 3-4, 21-25, 43-48, 76-79, 83-85, 88-89, 95-97, 104.

NINE SCREENS, NOT FIFTEEN. Section 95 names the MVP set and adds "this
is enough, do not build every reporting page immediately". The full
fifteen-item navigation is the destination; these nine are the thing
that has to work first.

TWO SCREENS ARE MANDATORY (sections 96, 97): Costs and Agent Economics.
Without them this is the old BI with a new coat, which is precisely the
mistake the revised specification was written to correct.

EVERY COST FIGURE CARRIES ITS QUALITY. Section 79 lists six states from
EXACT down to UNKNOWN, and section 101 an ingestion priority. A number
rendered without saying whether a provider reported it or we estimated
it is the same class of lie as a metric with no source.
"""
from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Optional

import content_engine_bi_cost as COST
import content_engine_bi_economics as ECON

_s, _d, _l, _f = COST._s, COST._d, COST._l, COST._f


def e(x) -> str:
    return html.escape(_s(x), quote=True)


def _n(x, dash="not measured") -> str:
    """A number, or an honest word. A zero is a measurement; absence is
    not, and rendering one as the other is how an unmonitored cost looks
    like a controlled one."""
    if x is None or x == "":
        return dash
    try:
        f = float(x)
    except (TypeError, ValueError):
        return e(x)
    return (f"{int(f):,}" if abs(f - int(f)) < 1e-9 else f"{f:,.2f}")


def _money(x, cur="EUR", dash="not measured") -> str:
    if x is None or x == "":
        return dash
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(
        _s(cur).upper(), "")
    try:
        v = float(x)
    except (TypeError, ValueError):
        return e(x)
    return sym + (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}")


def _pct(x, dash="not measured") -> str:
    if x is None:
        return dash
    try:
        return f"{float(x) * 100:,.1f}%"
    except (TypeError, ValueError):
        return e(x)


# ---------------------------------------------------------------------------
# 79. COST DATA QUALITY, rendered
# ---------------------------------------------------------------------------
_QUALITY_TONE = {"EXACT": "ok", "PROVIDER_REPORTED": "ok",
                 "CALCULATED": "", "ALLOCATED": "wa",
                 "ESTIMATED": "wa", "UNKNOWN": "er"}

_QUALITY_NOTE = {
    "EXACT": "from an invoice",
    "PROVIDER_REPORTED": "the provider reported this with the call",
    "CALCULATED": "exact usage times a dated price",
    "ALLOCATED": "a share of a shared cost, by a stated rule",
    "ESTIMATED": "modelled, not measured",
    "UNKNOWN": "no cost could be established",
}


def quality_pill(q) -> str:
    k = _s(q).upper() or "UNKNOWN"
    return ("<span class='bi-pill bi-pill-" + _QUALITY_TONE.get(k, "wa")
            + "' title='" + e(_QUALITY_NOTE.get(k, "")) + "'>"
            + e(k.replace("_", " ").title()) + "</span>")


CSS = """<style>
.bi-root{--bg:#F7F8FA;--sf:#FFFFFF;--sf2:#F9FAFB;--bd:#E5E7EB;
--tx:#111827;--tx2:#4B5563;--mu:#9CA3AF;--hu:#2563EB;--ai:#7C3AED;
--pl:#0F766E;--ok:#16A34A;--wa:#D97706;--er:#DC2626;
background:var(--bg);color:var(--tx);border-radius:12px;padding:16px;
font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;
font-size:14px;line-height:1.55}
.bi-root *{box-sizing:border-box}
.bi-h1{font-size:24px;font-weight:600;margin:0 0 4px}
.bi-h2{font-size:16px;font-weight:600;margin:18px 0 8px}
.bi-meta{font-size:12px;color:var(--mu)}
.bi-note{font-size:12px;color:var(--tx2);margin:6px 0 12px;max-width:76ch}
.bi-card{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:14px;margin:0 0 10px}
.bi-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:10px;margin:0 0 14px}
.bi-kpi{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:12px 14px}
.bi-kpi span{display:block;font-size:11px;color:var(--mu);
text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px}
.bi-kpi b{display:block;font-size:26px;font-weight:600;line-height:1.15;
font-variant-numeric:tabular-nums}
.bi-kpi i{display:block;font-style:normal;font-size:11px;
color:var(--mu);margin-top:4px}
.bi-tbl{width:100%;border-collapse:collapse;font-size:13px;
background:var(--sf)}
.bi-tbl th{text-align:left;font-size:11px;text-transform:uppercase;
letter-spacing:.05em;color:var(--mu);font-weight:600;padding:8px 10px;
border-bottom:1px solid var(--bd)}
.bi-tbl td{padding:9px 10px;border-bottom:1px solid var(--bd);
color:var(--tx2);vertical-align:top}
.bi-tbl td.num{text-align:right;font-variant-numeric:tabular-nums;
color:var(--tx)}
.bi-scroll{overflow-x:auto;border:1px solid var(--bd);border-radius:10px;
margin:0 0 12px}
.bi-pill{display:inline-block;font-size:10px;font-weight:500;
padding:2px 8px;border-radius:20px;border:1px solid var(--bd);
color:var(--tx2);background:var(--sf2)}
.bi-pill-ok{border-color:var(--ok);color:var(--ok)}
.bi-pill-wa{border-color:var(--wa);color:var(--wa)}
.bi-pill-er{border-color:var(--er);color:var(--er)}
.bi-ok{color:var(--ok)}.bi-wa{color:var(--wa)}.bi-er{color:var(--er)}
.bi-mu{color:var(--mu)}
.bi-empty{background:var(--sf);border:1px dashed var(--bd);
border-radius:10px;padding:18px}
.bi-empty b{display:block;font-size:15px;font-weight:600;margin:0 0 6px}
.bi-empty p{margin:0;font-size:13px;color:var(--tx2);max-width:68ch}
.bi-cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.bi-row{display:flex;gap:10px;justify-content:space-between;
align-items:baseline;padding:8px 0;border-bottom:1px solid var(--bd)}
.bi-row:last-child{border-bottom:0}
.bi-bar{height:9px;border-radius:5px;background:rgba(148,163,184,.2);
overflow:hidden;margin:5px 0 0}
.bi-bar span{display:block;height:100%;background:var(--hu)}
.bi-bar.wa span{background:var(--wa)}
.bi-bar.er span{background:var(--er)}
.bi-wf{display:flex;gap:8px;align-items:baseline;padding:7px 0;
border-bottom:1px solid var(--bd);font-size:13px}
.bi-wf b{margin-left:auto;font-variant-numeric:tabular-nums}
@media (max-width:900px){.bi-cols{grid-template-columns:1fr}}
</style>"""


def kpi(label, value, *, note="") -> str:
    return ("<div class='bi-kpi'><span>" + e(label) + "</span><b>"
            + value + "</b>"
            + ("<i>" + e(note) + "</i>" if note else "") + "</div>")


def empty(title, why) -> str:
    return ("<div class='bi-empty'><b>" + e(title) + "</b><p>" + e(why)
            + "</p></div>")


def _bar(frac, tone="") -> str:
    try:
        pct = max(0, min(100, int(float(frac) * 100)))
    except (TypeError, ValueError):
        pct = 0
    return ("<div class='bi-bar " + tone + "'><span style='width:"
            + str(pct) + "%'></span></div>")


# ===========================================================================
# 01 EXECUTIVE (sections 4, 73)
# ===========================================================================
def executive(ctx=None) -> str:
    """Section 4. Revenue, contribution, spend, AI/tools, CAC.

    The old executive screen showed revenue and called it performance.
    This one shows what is left after the machine is paid for, because
    section 1 says revenue is not profit and ROAS is not a business
    return.
    """
    c = _d(ctx)
    rev = _f(_d(c.get("revenue")).get("total"))
    media = _f(c.get("media_spend"))
    tools = _f(c.get("tool_cost"))
    cust = _f(c.get("customers"))
    # The one waterfall, computed in enrich(). A fallback exists only
    # for a caller that bypassed enrich(), and uses the identical inputs.
    wf = _d(c.get("waterfall")) or COST.contribution(
        revenue=rev, cogs=_f(c.get("cogs")), media=media,
        ai=_f(c.get("ai_cost")), tools=tools,
        cloud=_f(c.get("cloud_cost")),
        other_variable=_f(c.get("other_variable")))
    cac = ECON.true_cac(customers=cust, media=media,
                        marketing_ai=_f(c.get("ai_cost")),
                        marketing_tools=tools,
                        content_allocated=_f(c.get("content_allocated")),
                        data_allocated=_f(c.get("data_allocated")))
    out = ["<p class='bi-h1'>Business Command Center</p>",
           "<p class='bi-meta'>Revenue is not profit. Every figure here "
           "is net of what it cost to produce.</p>"]
    if rev is None:
        return "".join(out) + empty(
            "No revenue recorded",
            "The contribution model starts from revenue. Until a deal is "
            "recorded there is nothing to subtract costs from, and this "
            "screen will not show a cost total pretending to be a "
            "business picture.")
    out.append("<div class='bi-kpis'>"
               + kpi("Revenue", _money(rev))
               + kpi("Contribution",
                     _money(wf.get("contribution")
                            if wf.get("state") == "OK" else None),
                     note="revenue less variable cost, NOT net profit")
               + kpi("Media spend", _money(media))
               + kpi("AI and tools", _money(tools),
                     note="software, kept apart from media")
               + kpi("Marketing CAC",
                     _money(cac.get("marketing_cac")))
               + kpi("Full acquisition CAC",
                     _money(cac.get("full_acquisition_cac")),
                     note="includes the machine behind it")
               + "</div>")
    if wf.get("state") == "OK":
        # the picture first, the arithmetic under it; a missing cost
        # line is NAMED on the chart, never deducted as zero
        try:
            import content_engine_ui_kit as UK
            _steps = ([(_s(_d(st).get("step")).replace("_", " "),
                        _d(st).get("amount"))
                       for st in _l(wf.get("steps"))]
                      + [(m.replace("_", " "), None)
                         for m in _l(wf.get("missing"))])
            if _steps:
                out.append(UK.waterfall(
                    "Revenue", wf.get("revenue"), _steps,
                    title="Where revenue goes",
                    source="cost events and revenue records",
                    end_label="Contribution"))
        except Exception as _wfe:
            out.append("<p class='bi-note bi-wa'>The waterfall chart "
                       "could not draw: " + e(repr(_wfe)[:90])
                       + ". The rows below are the same numbers.</p>")
        out.append("<p class='bi-h2'>Margin waterfall</p>"
                   "<div class='bi-card'>")
        out.append("<div class='bi-row'><span>Revenue</span><b>"
                   + _money(rev) + "</b></div>")
        for st in _l(wf.get("steps")):
            sd = _d(st)
            out.append("<div class='bi-row'><span>less "
                       + e(_s(sd.get("step")).replace("_", " "))
                       + "</span><b>" + _money(sd.get("amount"))
                       + " <span class='bi-meta'>-> "
                       + _money(sd.get("running")) + "</span></b></div>")
        out.append("<div class='bi-row'><span><b>Contribution</b></span>"
                   "<b class='bi-ok'>" + _money(wf.get("contribution"))
                   + "</b></div></div>")
        out.append("<p class='bi-note'>" + e(wf.get("why")) + "</p>")
    if cac.get("missing_components"):
        out.append("<p class='bi-note bi-wa'>Full acquisition CAC is "
                   "missing " + e(", ".join(cac["missing_components"]))
                   + ", so it understates the true cost. Both CACs are "
                   "shown because replacing the standard one silently "
                   "breaks every external comparison.</p>")
    return "".join(out)


# ===========================================================================
# 02 GROWTH
# ===========================================================================
def growth(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("channels"))]
    if not rows:
        return ("<p class='bi-h1'>Growth</p>"
                + empty("No channel data",
                        "Channel performance comes from the OS that owns "
                        "each channel. This screen compares them; it "
                        "does not measure any of them itself."))
    body = ""
    for r in rows:
        cost = _f(r.get("cost"))
        val = _f(r.get("value"))
        eff = (round(val / cost, 2) if cost and val is not None else None)
        body += ("<tr><td>" + e(r.get("channel")) + "</td>"
                 + "<td class='num'>" + _money(val) + "</td>"
                 + "<td class='num'>" + _money(cost) + "</td>"
                 + "<td class='num'>" + _n(eff, "not comparable")
                 + "</td>"
                 + "<td>" + quality_pill(r.get("quality")) + "</td>"
                 + "<td class='bi-meta'>"
                 + e(ECON._attr_note(r.get("attribution"))) + "</td>"
                 + "</tr>")
    return ("<p class='bi-h1'>Growth</p>"
            + "<p class='bi-note'>Efficiency is value divided by the "
            + "cost of getting it, so a channel that returns less per "
            + "unit spent ranks below a smaller one that returns "
            + "more.</p>"
            + "<div class='bi-scroll'><table class='bi-tbl'><thead><tr>"
            "<th>Channel</th><th>Value</th><th>Cost</th>"
            "<th>Value per unit cost</th><th>Cost quality</th>"
            "<th>Attribution</th></tr></thead><tbody>"
            + body + "</tbody></table></div>")


# ===========================================================================
# 03 FUNNEL
# ===========================================================================
def funnel(ctx=None) -> str:
    c = _d(ctx)
    stages = [_d(x) for x in _l(c.get("funnel"))]
    if len(stages) < 2:
        return ("<p class='bi-h1'>Funnel</p>"
                + empty("Not enough measured stages",
                        "A funnel needs at least two measured stages. "
                        "Estimating the gaps would produce a shape that "
                        "reads as insight and is arithmetic on invented "
                        "numbers."))
    top = _f(stages[0].get("count"), 1) or 1
    out = ["<p class='bi-h1'>Funnel</p>"]
    prev = None
    for st in stages:
        n = _f(st.get("count"), 0) or 0
        rate = (n / prev if prev else None)
        cost = _f(st.get("cost"))
        out.append("<div class='bi-card'><div class='bi-wf'><span>"
                   + e(st.get("stage")) + "</span><b>" + _n(n)
                   + "</b></div>" + _bar(n / top)
                   + "<p class='bi-meta'>"
                   + (("conversion from the stage above: " + _pct(rate))
                      if rate is not None else "top of funnel")
                   + (" &middot; cost per unit " + _money(cost / n)
                      if cost and n else "")
                   + "</p></div>")
        prev = n
    return "".join(out)


# ===========================================================================
# 04 COSTS (MANDATORY, section 96)
# ===========================================================================
def costs(ctx=None) -> str:
    """Section 96. The screen without which this is the old BI.

    Total tool cost, AI, API, cloud and media spend, cost by OS, the
    most expensive tools, waste and the budget forecast.
    """
    c = _d(ctx)
    tools = [_d(t) for t in _l(c.get("tools"))]
    events = _l(c.get("usage_events"))
    versions = _l(c.get("pricing_versions"))
    split = COST.split_media_and_software(events, versions)
    w = COST.waste(events, versions)
    by_os = _d(c.get("cost_by_os"))
    budgets = [_d(b) for b in _l(c.get("budgets"))]

    out = ["<p class='bi-h1'>Cost Intelligence</p>",
           "<p class='bi-note'>Media spend and software cost are never "
           "one number. They are budgeted separately and behave "
           "differently, and adding them produces a figure that is "
           "neither a marketing budget nor an operating cost.</p>"]
    out.append("<div class='bi-kpis'>"
               + kpi("Software and API cost",
                     _money(split.get("software_cost")))
               + kpi("Media spend", _money(split.get("media_spend")),
                     note="not a software cost")
               + kpi("AI cost", _money(_f(c.get("ai_cost"))))
               + kpi("Cloud", _money(_f(c.get("cloud_cost"))))
               + kpi("Wasted", _money(w.get("wasted")),
                     note=(_s(w.get("waste_pct")) + "% of tracked spend"
                           if w.get("waste_pct") is not None else
                           "no waste measured"))
               + "</div>")
    out.append("<p class='bi-note'>Cost quality for this window: "
               + quality_pill(split.get("quality")) + " "
               + e(_QUALITY_NOTE.get(_s(split.get("quality")).upper(), ""))
               + ".</p>")

    if not events:
        out.append(empty(
            "No usage events yet",
            "Every external call should record a usage event. Until the "
            "OS modules emit them this screen can show subscriptions and "
            "budgets but not what the machine actually consumed."))
    if w.get("unpriced_events"):
        out.append("<p class='bi-note bi-wa'>"
                   + _s(w["unpriced_events"]) + " event(s) have no price "
                   "on record. They are counted and NOT costed: a zero "
                   "there would understate spend permanently.</p>")

    out.append("<p class='bi-h2'>Cost by OS</p>")
    if not by_os:
        out.append(empty("Not attributed to an OS",
                         "Usage events carry the system that made the "
                         "call. Without that, cost cannot be split by "
                         "OS and is not guessed at."))
    else:
        mx = max((_f(v, 0) or 0) for v in by_os.values()) or 1
        out.append("<div class='bi-card'>")
        for name, amt in sorted(by_os.items(),
                                key=lambda kv: -(_f(kv[1], 0) or 0)):
            v = _f(amt, 0) or 0
            out.append("<div class='bi-row'><span>" + e(name)
                       + "</span><b>" + _money(v) + "</b></div>"
                       + _bar(v / mx))
        out.append("</div>")

    out.append("<p class='bi-h2'>Most expensive tools</p>")
    if not tools:
        out.append(empty("No tools registered",
                         "Register the tools this business pays for. "
                         "Pricing is stored in dated versions so a "
                         "historical report keeps the price that was in "
                         "force on its own date."))
    else:
        body = ""
        for t in sorted(tools,
                        key=lambda x: -(_f(_d(x).get("monthly_fixed_cost"),
                                           0) or 0))[:12]:
            util = COST.subscription_utilisation(
                t.get("monthly_fixed_cost"), quota=t.get("quota"),
                used=t.get("used"))
            body += ("<tr><td>" + e(t.get("name")) + "</td>"
                     + "<td>" + e(t.get("category")) + "</td>"
                     + "<td class='num'>"
                     + _money(t.get("monthly_fixed_cost")) + "</td>"
                     + "<td class='num'>"
                     + _pct(util.get("utilisation")) + "</td>"
                     + "<td class='bi-meta'>" + e(util.get("why"))
                     + "</td></tr>")
        out.append("<div class='bi-scroll'><table class='bi-tbl'>"
                   "<thead><tr><th>Tool</th><th>Category</th>"
                   "<th>Monthly</th><th>Utilisation</th>"
                   "<th>Note</th></tr></thead><tbody>" + body
                   + "</tbody></table></div>")
        red = COST.redundancy(tools)
        if red:
            out.append("<p class='bi-note bi-wa'>"
                       + str(len(red)) + " capability(ies) are served by "
                       "more than one paid tool. Flagged for review and "
                       "not cancelled: a second provider is also a "
                       "fallback.</p>")

    out.append("<p class='bi-h2'>Budgets and forecast</p>")
    if not budgets:
        out.append(empty("No budgets set",
                         "A budget turns a cost into a decision. Without "
                         "one there is nothing to forecast against and "
                         "no guardrail can fire."))
    else:
        body = ""
        for b in budgets:
            g = COST.guardrail(b.get("spent"), b.get("budget"))
            fc = COST.forecast(b.get("spent"), budget=b.get("budget"),
                               elapsed_fraction=b.get("elapsed"))
            tone = {"EXCEEDED": "er", "LIMITED": "er",
                    "90_PERCENT": "wa", "80_PERCENT": "wa"}.get(
                        g.get("state"), "")
            body += ("<tr><td>" + e(b.get("scope")) + "</td>"
                     + "<td class='num'>" + _money(b.get("budget"))
                     + "</td><td class='num'>" + _money(b.get("spent"))
                     + "</td><td class='num'>"
                     + _money(fc.get("projected")) + "</td>"
                     + "<td><span class='bi-pill bi-pill-" + tone + "'>"
                     + e(g.get("state")) + "</span></td>"
                     + "<td class='bi-meta'>" + e(fc.get("why"))
                     + "</td></tr>")
        out.append("<div class='bi-scroll'><table class='bi-tbl'>"
                   "<thead><tr><th>Scope</th><th>Budget</th>"
                   "<th>Spent</th><th>Projected</th><th>State</th>"
                   "<th>Basis</th></tr></thead><tbody>" + body
                   + "</tbody></table></div>")
    return "".join(out)


# ===========================================================================
# 05 AGENT ECONOMICS (MANDATORY, section 97)
# ===========================================================================
def agent_economics(ctx=None) -> str:
    """Section 97. Which agents earn their keep.

    Ordered by cost per ACCEPTED output, not by total spend. An
    expensive agent that lands everything is fine; a cheap one that
    lands nothing is not, and cost per run cannot tell them apart.
    """
    c = _d(ctx)
    rows = [ECON.agent_card(_d(a), accepted_outputs=_d(a).get("accepted"))
            for a in _l(c.get("agents"))]
    if not rows:
        return ("<p class='bi-h1'>Agent Economics</p>"
                + empty("No agent runs recorded",
                        "Agents record their cost and their outcome per "
                        "run. Until one has run there is nothing to "
                        "judge, and a zero here would read as a free "
                        "agent rather than an unused one."))
    tot_cost = sum(_f(r.get("total_cost"), 0) or 0 for r in rows)
    tot_runs = sum(_f(r.get("runs"), 0) or 0 for r in rows)
    tot_ok = sum(_f(r.get("successful_runs"), 0) or 0 for r in rows)
    vals = [_f(r.get("business_value")) for r in rows
            if r.get("attribution") != "UNKNOWN"]
    attributed = sum(v for v in vals if v is not None) if vals else None
    out = ["<p class='bi-h1'>Agent Economics</p>",
           "<div class='bi-kpis'>"
           + kpi("Agent cost", _money(tot_cost))
           + kpi("Runs", _n(tot_runs))
           + kpi("Successful", _n(tot_ok),
                 note=(_pct(tot_ok / tot_runs) if tot_runs else ""))
           + kpi("Cost per success",
                 _money(tot_cost / tot_ok if tot_ok else None),
                 note="not cost per run")
           + kpi("Value attributed", _money(attributed),
                 note="only where attribution is not UNKNOWN")
           + "</div>",
           "<p class='bi-note'>Cost per successful run, not per run. An "
           "agent that runs a hundred times and succeeds twice has a "
           "flattering cost per run and a terrible cost per success, and "
           "only the second says whether to keep paying for it.</p>"]
    body = ""
    for r in sorted(rows, key=lambda x: -(_f(x.get("cost_per_accepted"),
                                             0) or 0)):
        tone = {"EXPENSIVE": "er", "WATCH": "wa"}.get(r.get("status"), "")
        body += ("<tr><td>" + e(r.get("agent_id"))
                 + ("<br><span class='bi-meta'>thin sample</span>"
                    if r.get("thin") else "") + "</td>"
                 + "<td class='num'>" + _n(r.get("runs")) + "</td>"
                 + "<td class='num'>" + _pct(r.get("success_rate"))
                 + "</td>"
                 + "<td class='num'>" + _money(r.get("total_cost"))
                 + "</td>"
                 + "<td class='num'>" + _money(r.get("cost_per_success"))
                 + "</td>"
                 + "<td class='num'>" + _money(r.get("cost_per_accepted"))
                 + "</td>"
                 + "<td class='num'>" + _money(r.get("business_value"))
                 + "</td>"
                 + "<td>" + _n(r.get("roi"), _s(r.get("roi_state")))
                 + "</td>"
                 + "<td><span class='bi-pill bi-pill-" + tone + "'>"
                 + e(r.get("status")) + "</span></td></tr>")
    out.append("<div class='bi-scroll'><table class='bi-tbl'><thead><tr>"
               "<th>Agent</th><th>Runs</th><th>Success</th><th>Cost</th>"
               "<th>Per success</th><th>Per accepted</th><th>Value</th>"
               "<th>ROI</th><th>Status</th></tr></thead><tbody>"
               + body + "</tbody></table></div>")
    unattr = [r for r in rows if r.get("roi_state") == "UNATTRIBUTED"]
    if unattr:
        out.append("<p class='bi-note bi-wa'>" + str(len(unattr))
                   + " agent(s) have value recorded but nothing tying it "
                   "to them. Their ROI is blank rather than computed: a "
                   "ratio built on a coincidence gets quoted in a "
                   "decision and cannot be defended in the review of "
                   "it.</p>")
    return "".join(out)


# ===========================================================================
# 06 RISKS AND OPPORTUNITIES (section 88)
# ===========================================================================
def risks(ctx=None) -> str:
    c = _d(ctx)
    items = [_d(x) for x in _l(c.get("risks"))]
    opts = [_d(x) for x in _l(c.get("optimisations"))]
    out = ["<p class='bi-h1'>Risks and Opportunities</p>"]
    if not items and not opts:
        return "".join(out) + empty(
            "Nothing flagged",
            "Cost anomalies, quota risks, redundancy and waste appear "
            "here when the numbers behind them exist. An empty board "
            "means nothing has been measured yet, not that nothing is "
            "wrong.")
    if items:
        out.append("<p class='bi-h2'>Risks</p>")
        for r in items:
            tone = {"HIGH": "er", "MEDIUM": "wa"}.get(
                _s(r.get("severity")).upper(), "")
            out.append("<div class='bi-card'>"
                       + "<span class='bi-pill" + ((" bi-pill-" + tone) if tone else "") + "'>"
                       + e(r.get("severity") or "INFO") + "</span> "
                       + "<span class='bi-pill'>"
                       + e(_s(r.get("type")).replace("_", " "))
                       + "</span>"
                       + "<p style='margin:8px 0 2px;font-weight:600'>"
                       + e(r.get("title") or r.get("type")) + "</p>"
                       + "<p class='bi-meta'>" + e(r.get("why"))
                       + "</p></div>")
    if opts:
        out.append("<p class='bi-h2'>Opportunities</p>")
        for o in opts:
            if not o.get("ok"):
                out.append("<div class='bi-card'><p class='bi-meta bi-wa'>"
                           + e(o.get("why")) + "</p></div>")
                continue
            lo, hi = o.get("saving", (None, None))
            out.append("<div class='bi-card'>"
                       + "<p style='margin:0 0 2px;font-weight:600'>"
                       + e(_s(o.get("kind")).replace("_", " ").title())
                       + "</p><p class='bi-meta'>Saving "
                       + _money(lo) + " to " + _money(hi)
                       + " a month &middot; risk "
                       + e(_s(o.get("risk")).lower())
                       + " &middot; quality impact "
                       + e(_s(o.get("quality_impact")).lower())
                       + " &middot; effort "
                       + e(_s(o.get("effort")).lower())
                       + "</p></div>")
        out.append("<p class='bi-note'>A cheaper tool is only cheaper if "
                   "the output stays usable. A provider costing more that "
                   "is rejected far less often is cheaper per accepted "
                   "output, and nothing here recommends on price "
                   "alone.</p>")
    return "".join(out)


# ===========================================================================
# 07 AI DECISIONS (sections 51-54, 86-87)
# ===========================================================================
def decisions(ctx=None) -> str:
    c = _d(ctx)
    opts = [_d(o) for o in _l(c.get("options"))]
    if not opts:
        return ("<p class='bi-h1'>AI Decisions</p>"
                + empty("No options on the table",
                        "A decision needs at least two options, each "
                        "with an expected value range AND an expected "
                        "cost range. An option without its execution "
                        "cost is not scored rather than assumed free."))
    ranked = ECON.rank_options(opts)
    out = ["<p class='bi-h1'>AI Decisions</p>",
           "<p class='bi-note'>Ranked by expected NET value. Ranking on "
           "revenue recommends the largest spend every time.</p>"]
    for o in _l(ranked.get("ranked")):
        od = _d(o)
        vlo, vhi = od.get("expected_value", (None, None))
        clo, chi = od.get("expected_cost", (None, None))
        nlo, nhi = od.get("expected_net", (None, None))
        best = od.get("name") == ranked.get("recommended")
        out.append("<div class='bi-card'>"
                   + ("<span class='bi-pill bi-pill-ok'>recommended"
                      "</span> " if best else "")
                   + "<p style='margin:6px 0 4px;font-weight:600'>"
                   + e(od.get("name")) + "</p>"
                   + "<div class='bi-row'><span>Expected value</span><b>"
                   + _money(vlo) + " to " + _money(vhi) + "</b></div>"
                   + "<div class='bi-row'><span>Execution cost</span><b>"
                   + _money(clo) + " to " + _money(chi) + "</b></div>"
                   + "<div class='bi-row'><span>Expected net</span>"
                   + "<b class='bi-ok'>" + _money(nlo) + " to "
                   + _money(nhi) + "</b></div>"
                   + "<p class='bi-meta'>Confidence "
                   + _pct(od.get("confidence")) + " &middot; risk "
                   + e(_s(od.get("risk")).lower())
                   + (" &middot; " + e(od.get("time_to_result"))
                      if od.get("time_to_result") else "")
                   + "</p></div>")
    out.append("<p class='bi-note'>" + e(ranked.get("why")) + "</p>")
    return "".join(out)


# ===========================================================================
# 08 INITIATIVES (sections 56-57)
# ===========================================================================
def initiatives(ctx=None) -> str:
    c = _d(ctx)
    rows = [_d(x) for x in _l(c.get("initiatives"))]
    if not rows:
        return ("<p class='bi-h1'>Initiatives</p>"
                + empty("Nothing in flight",
                        "An approved decision becomes an initiative "
                        "here, and stays open until its ACTUAL cost and "
                        "result come back. Estimated cost alone never "
                        "closes one."))
    body = ""
    for r in rows:
        var = ECON.estimate_variance(r.get("estimated_cost"),
                                     r.get("actual_cost"))
        tone = ("" if var.get("state") != "OK"
                else "er" if (_f(var.get("variance"), 0) or 0) > 0.25
                else "ok")
        body += ("<tr><td>" + e(r.get("name")) + "</td>"
                 + "<td>" + e(r.get("state") or "OPEN") + "</td>"
                 + "<td class='num'>" + _money(r.get("estimated_cost"))
                 + "</td>"
                 + "<td class='num'>" + _money(r.get("actual_cost"))
                 + "</td>"
                 + "<td><span class='bi-pill bi-pill-" + tone + "'>"
                 + (_pct(var.get("variance"))
                    if var.get("state") == "OK"
                    else e(var.get("state"))) + "</span></td>"
                 + "<td class='num'>" + _money(r.get("value")) + "</td>"
                 + "<td class='bi-meta'>" + e(var.get("why"))
                 + "</td></tr>")
    return ("<p class='bi-h1'>Initiatives</p>"
            + "<p class='bi-note'>Estimated against actual cost is kept "
            + "for every initiative, because an estimator nobody scores "
            + "stays wrong forever.</p>"
            + "<div class='bi-scroll'><table class='bi-tbl'><thead><tr>"
            "<th>Initiative</th><th>State</th><th>Estimated</th>"
            "<th>Actual</th><th>Variance</th><th>Value</th>"
            "<th>Basis</th></tr></thead><tbody>" + body
            + "</tbody></table></div>")


# ===========================================================================
# 09 DATA AND COST HEALTH (section 44)
# ===========================================================================
def health(ctx=None) -> str:
    """Section 44. Three healths, kept apart.

    Fresh inputs, working providers and economical operation are three
    different questions. One green light covering all three hides
    whichever of them is red.
    """
    c = _d(ctx)
    out = ["<p class='bi-h1'>Data and Cost Health</p>",
           "<p class='bi-note'>Three separate questions. A single health "
           "light would hide whichever one is failing.</p>"]
    for key in ECON.HEALTHS:
        block = _d(_d(c.get("health")).get(key))
        state = _s(block.get("state")).upper() or "NOT CHECKED"
        tone = {"HEALTHY": "ok", "DEGRADED": "wa", "ERROR": "er",
                "NOT CHECKED": ""}.get(state, "")
        out.append("<div class='bi-card'>"
                   + "<div class='bi-row'><span><b>"
                   + e(key.replace("_", " ").title()) + "</b><br>"
                   + "<span class='bi-meta'>"
                   + e(ECON.HEALTH_QUESTION[key]) + "</span></span>"
                   + "<span class='bi-pill" + ((" bi-pill-" + tone) if tone else "") + "'>"
                   + e(state) + "</span></div>"
                   + ("<p class='bi-meta'>" + e(block.get("why")) + "</p>"
                      if block.get("why") else
                      "<p class='bi-meta'>Nothing has reported on this "
                      "yet.</p>")
                   + "</div>")
    quotas = [_d(q) for q in _l(c.get("quotas"))]
    out.append("<p class='bi-h2'>Quotas</p>")
    if not quotas:
        out.append(empty("No quotas tracked",
                         "A free API still stops answering at its limit, "
                         "which halts the work exactly as hard as an "
                         "unpaid one. Quota is tracked separately from "
                         "cost for that reason."))
    else:
        body = ""
        for q in quotas:
            st = ECON.quota_state(q.get("used"), q.get("quota"),
                                  resets_in_days=q.get("resets_in_days"))
            tone = {"EXCEEDED": "er", "AT RISK": "wa"}.get(
                st.get("state"), "")
            body += ("<tr><td>" + e(q.get("provider")) + "</td>"
                     + "<td class='num'>" + _pct(st.get("used_pct"))
                     + "</td>"
                     + "<td><span class='bi-pill bi-pill-" + tone + "'>"
                     + e(st.get("state")) + "</span></td>"
                     + "<td class='bi-meta'>" + e(st.get("why"))
                     + "</td></tr>")
        out.append("<div class='bi-scroll'><table class='bi-tbl'>"
                   "<thead><tr><th>Provider</th><th>Used</th>"
                   "<th>State</th><th>Note</th></tr></thead><tbody>"
                   + body + "</tbody></table></div>")
    return "".join(out)
