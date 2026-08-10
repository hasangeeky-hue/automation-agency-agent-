# -*- coding: utf-8 -*-
"""DEMO MODE: sample fixtures and the kit gallery.

The audit's finding 8: with nothing wired, every screen is a wall of
empty states, so the UI cannot be judged until the wiring round. This
module fixes that the honest way: FIXTURES THAT SAY THEY ARE FIXTURES.

Every demo payload carries source="SAMPLE DATA" and every gallery page
carries a banner. Demo numbers can never be mistaken for the business,
because the one unforgivable version of demo mode is the one someone
screenshots into a decision.

gallery() renders every kit component and all seven charts with sample
data: it is both the design review page and the visual regression
artifact for verify_ui_kit.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_ui_kit as UK

SRC = "SAMPLE DATA"
BANNER = ("<div style='background:#FEF3C7;border:1px solid #D97706;"
          "border-radius:10px;padding:8px 14px;margin:0 0 12px;"
          "font-size:12px;color:#92400E'><b>SAMPLE DATA.</b> Every "
          "figure on this page is a fixture for judging the design. "
          "Nothing here is the business.</div>")

# ---------------------------------------------------------------------------
# fixtures: one realistic month, gaps included on purpose
# ---------------------------------------------------------------------------
DAYS = ["Jul %d" % d for d in range(12, 32)] + ["Aug %d" % d
                                                for d in range(1, 11)]

REVENUE_30D = [8.4, 9.1, 8.8, 9.6, 10.2, 9.4, 8.9, 10.8, 11.2, 10.6,
               11.9, 12.4, None, None, 12.1, 12.8, 13.4, 12.9, 13.8,
               14.2, 13.6, 14.9, 15.2, 14.8, 15.6, 16.1, 15.4, 16.8,
               17.2, 16.9]
REVENUE_PREV = [7.2, 7.8, 7.4, 8.1, 8.6, 8.2, 7.9, 8.8, 9.2, 8.9, 9.6,
                9.9, 10.1, 9.8, 10.2, 10.6, 10.9, 10.4, 11.1, 11.4,
                11.0, 11.8, 12.1, 11.9, 12.3, 12.6, 12.2, 12.9, 13.1,
                12.8]

DEMO: Dict[str, Any] = {
    "business": {"revenue": 284000, "revenue_pct": 18,
                 "contribution": 94000, "contribution_pct": 12,
                 "spend": 48000, "spend_pct": 9,
                 "customers": 418, "customers_pct": 13,
                 "cac": 114, "cac_pct": -3,
                 "pipeline": 620000, "pipeline_pct": 8},
    "channels": [("Paid Social", 62000), ("Organic Search", 31000),
                 ("Email", 18400), ("Paid Search", 24800),
                 ("Direct", 12200)],
    "channel_cost": [("Paid Social", 28000), ("Organic Search", 1280),
                     ("Email", 680), ("Paid Search", 20000),
                     ("Direct", None)],
    "spend_by_platform": [
        ("Meta", [4.1, 4.4, 4.2, 4.8, 5.1, 4.9, 5.2]),
        ("Google", [3.2, 3.1, 3.4, 3.6, 3.3, 3.8, 3.9]),
        ("TikTok", [1.8, 2.1, 2.4, 2.2, 2.6, 2.9, 3.1])],
    "week": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "campaign_eff": [(8400, 4.2, "Prospecting A"),
                     (12100, 3.1, "Retargeting"),
                     (4200, 5.8, "Brand Search"),
                     (9800, 1.9, "TikTok Broad"),
                     (2400, None, "New Test")],
    "cost_parts": [("Media", 48000), ("AI models", 3100),
                   ("Data APIs", 2000), ("Creative tools", 1400),
                   ("Cloud", 1240), ("Other", 700)],
    "waterfall_steps": [("COGS", 40000), ("Media", 48000),
                        ("AI", 3100), ("Tools", 2000), ("Cloud", 1240),
                        ("Other", None)],
    "keywords": [
        {"kw": "ai automation agency", "pos": 6.2,
         "trend": [11, 10, 9, 9, 8, None, 7, 7, 6, 6]},
        {"kw": "n8n consultant", "pos": 12.4,
         "trend": [18, 16, 15, 15, 14, 13, 13, 12, 12, 12]},
        {"kw": "automation cost guide", "pos": 3.1,
         "trend": [9, 8, 6, 5, 4, 4, 3, 3, 3, 3]}],
    "funnel": [("Impressions", 1840000), ("Clicks", 41800),
               ("Sessions", 33400), ("Leads", 2814),
               ("Customers", 418)],
}


# ---------------------------------------------------------------------------
# the gallery
# ---------------------------------------------------------------------------
def gallery() -> str:
    """Every kit piece, rendered once, from fixtures that admit it."""
    d = DEMO
    b = d["business"]
    out: List[str] = [UK.CSS, UK.JS, "<div class='uk'>", BANNER,
                      "<p class='uk-h1'>UI Kit Gallery</p>",
                      "<p class='uk-meta'>One design system. Every "
                      "component below is the single shared copy.</p>"]

    # --- scorecards with polarity
    out.append("<p class='uk-h2'>Scorecards (polarity-aware)</p>"
               "<div class='uk-kpis'>"
               + UK.kpi("Revenue", UK.money(b["revenue"]),
                        delta=b["revenue_pct"], verdict="GOOD",
                        freshness="updated 6 min ago")
               + UK.kpi("CAC", UK.money(b["cac"]), delta=b["cac_pct"],
                        verdict="GOOD",
                        why="CAC falling is good; the kit never assumes "
                            "higher is better")
               + UK.kpi("Spend", UK.money(b["spend"]),
                        delta=b["spend_pct"], verdict="NEUTRAL")
               + UK.kpi("Pipeline", UK.money(b["pipeline"]),
                        delta=b["pipeline_pct"], verdict="GOOD")
               + UK.kpi("Refund rate", "1.2%", delta=14, verdict="BAD")
               + UK.kpi("New metric", UK.n(None))
               + "</div>")

    # --- the seven charts
    out.append(UK.line(REVENUE_30D, title="Revenue, last 30 days",
                       source=SRC, freshness="updated 6 min ago",
                       compare=REVENUE_PREV))
    out.append(UK.hbar(d["channels"], title="Revenue by channel",
                       source=SRC, value_fmt=UK.money))
    out.append(UK.stacked(d["week"], d["spend_by_platform"],
                          title="Spend by platform, this week (k)",
                          source=SRC))
    out.append(UK.scatter(d["campaign_eff"],
                          title="Campaign efficiency",
                          source=SRC, x_label="spend",
                          y_label="ROAS"))
    out.append(UK.donut(d["cost_parts"], title="Cost structure",
                        source=SRC, value_fmt=UK.money))
    out.append(UK.waterfall("Revenue", 284000, d["waterfall_steps"],
                            title="Margin waterfall", source=SRC,
                            end_label="Contribution"))
    out.append("<div class='uk-chart'><p class='uk-h2' "
               "style='margin:0 0 8px'>Sparklines in a table</p>"
               + UK.table(
                   ("Keyword", "Position", "Trend (30d)"),
                   [((UK.e(k["kw"]), ("num", UK.n(k["pos"])),
                      UK.sparkline(k["trend"], source=SRC)), None)
                    for k in d["keywords"]])
               + "</div>")

    # --- refusals, on purpose
    out.append("<p class='uk-h2'>What the charts refuse</p>")
    out.append(UK.line([1, 2, 3], title="Chart with no source",
                       source=""))
    out.append(UK.line([None, None, None],
                       title="Nothing measured this window",
                       source=SRC))

    # --- components
    out.append("<p class='uk-h2'>Status is icon plus word</p>"
               "<div class='uk-card'>"
               + " ".join(UK.status(s) for s in
                          ("HEALTHY", "DEGRADED", "FAILED", "RUNNING",
                           "STALLED", "UNKNOWN")) + "</div>")
    out.append("<p class='uk-h2'>Buttons, badges, notes</p>"
               "<div class='uk-card'>"
               + UK.button("Approve", "human", onclick="void(0)")
               + UK.button("Generate Draft", "ai", onclick="void(0)")
               + UK.button("Preview", onclick="void(0)")
               + UK.button("Reject", "danger", onclick="void(0)")
               + " Inbox" + UK.badge(18)
               + " lecture, compressed" + UK.note(
                   "the whole explanation lives here now, on hover, "
                   "instead of a paragraph on the screen")
               + "</div>")
    out.append(UK.empty("No signals yet",
                        "Signals arrive from the other systems; the "
                        "factory observes nothing itself.",
                        cta="Open Inbox", onclick="void(0)"))

    # --- table with drawer
    out.append("<p class='uk-h2'>Table with row drawer</p>"
               + UK.table(("Campaign", "Spend", "ROAS"),
                          [((UK.e("Prospecting A"),
                             ("num", UK.money(8400)),
                             ("num", "4.2")), "demo-d1")],
                          drawer_prefix="")
               + UK.drawer("demo-d1",
                           "<b>Prospecting A</b> "
                           + UK.pill("Meta")
                           + "<p class='uk-meta'>drill-down detail "
                           "renders here without leaving the page, the "
                           "old dashboard's seeDetails pattern kept"
                           "</p>"))

    # --- the subsection template
    out.append("<p class='uk-h2'>The subsection template "
               "(every screen converts to this in Round 2)</p>")
    out.append(UK.subsection(
        "Paid performance",
        freshness="Media 3 min · GA4 26 min",
        kpis=(UK.kpi("Spend", UK.money(48000), delta=9,
                     verdict="NEUTRAL")
              + UK.kpi("ROAS", "3.4", delta=6, verdict="GOOD")
              + UK.kpi("CPA", UK.money(114), delta=-3, verdict="GOOD")),
        chart=UK.line(REVENUE_30D, title="Revenue vs previous period",
                      source=SRC, compare=REVENUE_PREV),
        breakdown=UK.hbar(d["channels"], title="By channel", source=SRC,
                          value_fmt=UK.money),
        table_html=UK.table(("Channel", "Revenue"),
                            [((UK.e(a), ("num", UK.money(v))), None)
                             for a, v in d["channels"]])))
    out.append("</div>")
    return "".join(out)


def demo_ctx(section) -> Dict[str, Any]:
    """Fixture ctx per OS section, for ?demo=1 in Round 2. Every payload
    is stamped so a screen rendering it says SAMPLE on its face."""
    base = {"_demo": True, "period": "Last 30 days (SAMPLE)",
            "workspace": "Anthropos (sample)"}
    if section == "bi":
        base.update({"revenue": {"total": 284000}, "cogs": 40000,
                     "media_spend": 48000, "ai_cost": 3100,
                     "tool_cost": 4390, "cloud_cost": 1240,
                     "customers": 418})
    if section == "cockpit":
        base.update({"business": {
            k: {"value": DEMO["business"][k],
                "pct": DEMO["business"][k + "_pct"]}
            for k in ("revenue", "contribution", "spend", "customers",
                      "cac", "pipeline")}})
    return base
