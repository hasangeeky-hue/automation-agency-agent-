# -*- coding: utf-8 -*-
"""CONTENT FACTORY OS: the nine screens.

Spec sections 5-20, 24-36, 39-42, 46-53, 55, 61-62, 80-83, 101-105.

NINE SCREENS. Section 5 sets the ceiling and says in the same breath: do
not create dozens of nested modules. Every screen below answers a
question a person actually has, and section 101-105 give each one an
acceptance test it has to pass.

THE PALETTE IS LIGHT ON PURPOSE (section 8). This is a different surface
from the dark Search OS, and colour carries MEANING here (section 9):
blue is a human doing something, purple is AI doing something, teal is
planning, green is approved, amber needs review, red failed. Platform
colours appear only as small identifiers, never as a dashboard theme.
"""
from __future__ import annotations

import html
import json
from typing import Any, Dict, Iterable, List, Optional

import content_engine_factory_os as FOS
import content_engine_factory_agents as FA

_s, _d, _l, _f = FOS._s, FOS._d, FOS._l, FOS._f


def e(x) -> str:
    return html.escape(_s(x), quote=True)


def _n(x, dash="not measured") -> str:
    """A number, or an honest word. Never a zero standing in for absence."""
    if x is None or x == "":
        return dash
    try:
        f = float(x)
    except (TypeError, ValueError):
        return e(x)
    return (f"{int(f):,}" if abs(f - int(f)) < 1e-9 else f"{f:,.2f}")


# ===========================================================================
# 8-11. THE DESIGN SYSTEM
# ===========================================================================
TOKENS = {
    "bg": "#F7F8FA", "surface": "#FFFFFF", "surface2": "#F9FAFB",
    "border": "#E5E7EB", "text": "#111827", "text2": "#4B5563",
    "muted": "#9CA3AF", "human": "#2563EB", "ai": "#7C3AED",
    "planning": "#0F766E", "success": "#16A34A", "warning": "#D97706",
    "error": "#DC2626",
}

#: Section 9. What each colour is allowed to mean. A palette without this
#: becomes decoration, and then a red chip means "important" instead of
#: "failed" and the screen stops carrying information.
MEANING = {
    "human": "a human does this",
    "ai": "AI does this",
    "planning": "planning",
    "success": "approved, distributed, succeeded",
    "warning": "needs review",
    "error": "failed, rejected, destructive",
    "muted": "draft, neutral",
}

#: Section 10. The complete CTA vocabulary. button() refuses anything
#: outside it, so a new variant cannot be invented at a call site and
#: quietly mean nothing.
CTA_KINDS = ("human", "ai", "secondary", "destructive")

CTA_LABELS = {
    "human": ("Create Content", "Approve", "Send to Distribution",
              "Publish", "Accept All", "Accept Selected", "Save",
              "Upload", "Create Plan", "Open Review Queue",
              "Request Changes", "Send to Review", "Add Content",
              "Create Variant", "Use", "Restore", "Connect"),
    "ai": ("Build Plan", "Generate Draft", "Create Variations",
           "Generate Image", "Revise", "AI Plan Week", "Analyze Inbox",
           "Generate Variants", "Rewrite", "Shorten", "Expand",
           "Improve Hook", "Adapt Platform", "Create Video Concept",
           "Generate"),
    "secondary": ("Preview", "Compare", "Edit", "Save", "Dismiss",
                  "Open Performance", "Use in Planner", "Filters"),
    "destructive": ("Reject", "Archive"),
}


def button(label, kind="secondary", *, onclick="", small=False) -> str:
    """One button. Refuses a kind the design system does not define.

    Section 10 fixes the CTA vocabulary. Allowing an arbitrary variant
    here is how "primary" ends up meaning four different things on four
    screens.
    """
    k = _s(kind).lower()
    if k not in CTA_KINDS:
        raise ValueError("'" + _s(kind) + "' is not a CTA kind. Use one "
                         "of: " + ", ".join(CTA_KINDS))
    mark = "✦ " if k == "ai" else ""
    cls = "cf-btn cf-btn-" + k + (" cf-btn-sm" if small else "")
    return ("<button class='" + cls + "'"
            + (" onclick=\"" + e(onclick) + "\"" if onclick else "")
            + ">" + mark + e(label) + "</button>")


CSS = """<style>
.cf-root{--bg:#F7F8FA;--sf:#FFFFFF;--sf2:#F9FAFB;--bd:#E5E7EB;
--tx:#111827;--tx2:#4B5563;--mu:#9CA3AF;--hu:#2563EB;--ai:#7C3AED;
--pl:#0F766E;--ok:#16A34A;--wa:#D97706;--er:#DC2626;
background:var(--bg);color:var(--tx);border-radius:12px;padding:16px;
font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;
font-size:14px;line-height:1.55}
.cf-root *{box-sizing:border-box}
.cf-h1{font-size:24px;font-weight:600;margin:0 0 12px;color:var(--tx)}
.cf-h2{font-size:16px;font-weight:600;margin:18px 0 8px;color:var(--tx)}
.cf-meta{font-size:12px;color:var(--mu)}
.cf-note{font-size:12px;color:var(--tx2);margin:6px 0 12px;max-width:74ch}
.cf-card{background:var(--sf);border:1px solid var(--bd);border-radius:10px;
padding:14px;margin:0 0 10px}
.cf-grid{display:grid;gap:10px}
.cf-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
gap:10px;margin:0 0 14px}
.cf-kpi{background:var(--sf);border:1px solid var(--bd);border-radius:10px;
padding:12px 14px}
.cf-kpi b{display:block;font-size:26px;font-weight:600;
font-variant-numeric:tabular-nums;color:var(--tx);line-height:1.2}
.cf-kpi span{display:block;font-size:12px;color:var(--mu);
text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px}
.cf-kpi i{display:block;font-style:normal;font-size:11px;color:var(--mu);
margin-top:4px}
.cf-btn{font:inherit;font-size:13px;font-weight:500;padding:7px 13px;
border-radius:8px;border:1px solid var(--bd);background:var(--sf);
color:var(--tx);cursor:pointer;margin:0 6px 6px 0}
.cf-btn-sm{font-size:12px;padding:5px 10px}
.cf-btn-human{background:var(--hu);border-color:var(--hu);color:#fff}
.cf-btn-ai{background:var(--ai);border-color:var(--ai);color:#fff}
.cf-btn-secondary{background:var(--sf);color:var(--tx2)}
.cf-btn-destructive{background:var(--sf);border-color:var(--er);
color:var(--er)}
.cf-tbl{width:100%;border-collapse:collapse;font-size:13px;
background:var(--sf)}
.cf-tbl th{text-align:left;font-size:11px;text-transform:uppercase;
letter-spacing:.05em;color:var(--mu);font-weight:600;padding:8px 10px;
border-bottom:1px solid var(--bd)}
.cf-tbl td{padding:9px 10px;border-bottom:1px solid var(--bd);
color:var(--tx2);vertical-align:top}
.cf-scroll{overflow-x:auto;border:1px solid var(--bd);border-radius:10px;
margin:0 0 12px}
.cf-pill{display:inline-block;font-size:11px;font-weight:500;
padding:2px 8px;border-radius:20px;border:1px solid var(--bd);
color:var(--tx2);background:var(--sf2)}
.cf-hu{color:var(--hu)}.cf-ai{color:var(--ai)}.cf-pl{color:var(--pl)}
.cf-ok{color:var(--ok)}.cf-wa{color:var(--wa)}.cf-er{color:var(--er)}
.cf-mu{color:var(--mu)}
.cf-pill-ok{border-color:var(--ok);color:var(--ok)}
.cf-pill-wa{border-color:var(--wa);color:var(--wa)}
.cf-pill-er{border-color:var(--er);color:var(--er)}
.cf-pill-ai{border-color:var(--ai);color:var(--ai)}
.cf-pill-pl{border-color:var(--pl);color:var(--pl)}
.cf-empty{background:var(--sf);border:1px dashed var(--bd);
border-radius:10px;padding:20px;text-align:left}
.cf-empty b{display:block;font-size:15px;font-weight:600;margin:0 0 6px}
.cf-empty p{margin:0 0 10px;font-size:13px;color:var(--tx2);max-width:66ch}
.cf-cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.cf-studio{display:grid;grid-template-columns:260px 1fr 360px;gap:12px;
align-items:start}
.cf-review{display:grid;grid-template-columns:260px 1fr 300px;gap:12px;
align-items:start}
.cf-row{display:flex;gap:10px;align-items:baseline;justify-content:space-between;
padding:9px 0;border-bottom:1px solid var(--bd)}
.cf-row:last-child{border-bottom:0}
/* a queue row is a LINK now: every queued piece can be opened and read
   before it is approved. It must still look like a row, not a link. */
a.cf-row{text-decoration:none;color:inherit;cursor:pointer}
a.cf-row:hover{background:var(--sf2)}
.cf-on{box-shadow:inset 3px 0 0 var(--hu);padding-left:8px}
.cf-blk{background:var(--sf2);border:1px solid var(--bd);border-radius:8px;
padding:10px 12px;margin:0 0 8px}
.cf-blk header{display:flex;gap:8px;align-items:center;margin:0 0 6px}
.cf-blk header b{font-size:11px;letter-spacing:.06em;color:var(--mu);
text-transform:uppercase}
.cf-lock{font-size:11px;color:var(--hu)}
.cf-diff-add{background:rgba(22,163,74,.10);
border-left:2px solid var(--ok);padding:4px 8px;display:block}
.cf-diff-del{background:rgba(220,38,38,.08);
border-left:2px solid var(--er);padding:4px 8px;display:block;
text-decoration:line-through}
@media (max-width:1100px){.cf-studio,.cf-review{grid-template-columns:1fr}
.cf-cols{grid-template-columns:1fr}}
</style>"""


def kpi(label, value, *, note="") -> str:
    return ("<div class='cf-kpi'><span>" + e(label) + "</span><b>"
            + _n(value) + "</b>"
            + ("<i>" + e(note) + "</i>" if note else "") + "</div>")


def empty(title, why, cta_label="", cta_kind="human", onclick="") -> str:
    """An empty state that says what is missing and what fills it."""
    return ("<div class='cf-empty'><b>" + e(title) + "</b><p>" + e(why)
            + "</p>"
            + (button(cta_label, cta_kind, onclick=onclick)
               if cta_label else "") + "</div>")


def _pill(text, tone="") -> str:
    cls = "cf-pill" + (" cf-pill-" + tone if tone else "")
    return "<span class='" + cls + "'>" + e(text) + "</span>"


_STATUS_TONE = {"APPROVED": "ok", "PUBLISHED": "ok", "DISTRIBUTED": "ok",
                "REVIEW": "wa", "CHANGES_REQUESTED": "wa",
                "FAILED": "er", "REJECTED": "er", "ARCHIVED": "",
                "PRODUCTION": "ai", "BRIEF": "pl", "IDEA": "pl",
                "SCHEDULED": "pl"}


def status_pill(status) -> str:
    st = _s(status).upper()
    return _pill(st.replace("_", " ").title(), _STATUS_TONE.get(st, ""))


# ===========================================================================
# 6-7. THE SHELL
# ===========================================================================
NAV = (("cfcmd", "Command Center"), ("cfinbox", "Inbox"),
       ("cfplan", "Planner"), ("cfstudio", "Studio"),
       ("cflib", "Library"), ("cfreview", "Review"),
       ("cfdist", "Distribution"), ("cfperf", "Performance"),
       ("cfset", "Settings"))


def header(ctx=None) -> str:
    """Section 7. Brand, campaign, market, channel, health, agents.

    Deliberately no analytics filters: this header orients you, it does
    not slice data. Slicing belongs on Performance.
    """
    c = _d(ctx)
    working = _l(c.get("agent_runs"))
    live = [x for x in working if _s(_d(x).get("state")) == "RUNNING"]
    health = _d(c.get("data_health"))
    tone = {"HEALTHY": "ok", "DEGRADED": "wa", "ERROR": "er",
            "NOT CONFIGURED": ""}.get(_s(health.get("state")).upper(), "")
    return ("<div class='cf-card' style='display:flex;flex-wrap:wrap;"
            "gap:10px;align-items:center;justify-content:space-between'>"
            + "<div style='display:flex;gap:8px;flex-wrap:wrap'>"
            + _pill(_s(c.get("brand") or "No brand") + " ▾")
            + _pill(_s(c.get("campaign") or "All Campaigns") + " ▾")
            + _pill(_s(c.get("market") or "All Markets") + " ▾")
            + _pill(_s(c.get("channel") or "All Channels") + " ▾")
            + "</div><div style='display:flex;gap:8px;flex-wrap:wrap'>"
            + _pill("Data " + (_s(health.get("state")) or "not checked"),
                    tone)
            + _pill(("✦ " + str(len(live)) + " agent working")
                    if live else "✦ no agent running",
                    "ai" if live else "")
            + _pill("\U0001F514 " + str(len(_l(c.get("notifications")))))
            + "</div></div>")


# ===========================================================================
# SCREEN 01 - COMMAND CENTER (sections 12-14, 101)
# ===========================================================================
def command_center(ctx=None) -> str:
    """Five questions, section 12. Workflow, not an analytics warehouse.

    Section 14 warns against recreating GA4 here. The counters are
    workflow counters; revenue appears only if attribution is real, and
    says so when it is not.
    """
    c = _d(ctx)
    counts = _d(c.get("counts"))
    sigs = [_d(s) for s in _l(c.get("signals"))]
    top = sorted([s for s in sigs
                  if FOS.signal_is_actionable(s).get("ok")],
                 key=lambda s: -(_f(s.get("priority"), 0) or 0))[:3]
    review = [_d(x) for x in _l(c.get("needs_review"))][:5]
    learning = [_d(x) for x in _l(c.get("learning"))][:4]
    loop = FOS.loop_state(_d(c.get("loop_counts")))

    body = ["<p class='cf-h1'>Content Factory</p>",
            "<div>" + button("Create Content", "human",
                             onclick="cfCreate()")
            + button("Build Plan", "ai", onclick="cfPlanWeek()") + "</div>",
            "<div class='cf-kpis'>",
            kpi("Inbox", counts.get("inbox")),
            kpi("Production", counts.get("production")),
            kpi("Review", counts.get("review")),
            kpi("Ready", counts.get("ready")),
            kpi("Published", counts.get("published")),
            "</div>",
            ("<p class='cf-note'>These are workflow counters. Reach, "
             "revenue and spend live on Performance and in the OS that "
             "measured them; this screen exists to tell you what to do "
             "next, not to restate GA4.</p>")]

    body.append("<div class='cf-cols'><div>")
    body.append("<p class='cf-h2'>What should we create?</p>")
    if not top:
        body.append(empty("Nothing in the inbox is actionable",
                          "No signal carries a topic yet, or every one "
                          "has been handled. The factory will not invent "
                          "a topic to fill a week.",
                          "Open Inbox", "human", "cfGo('cfinbox')"))
    else:
        for s in top:
            body.append(
                "<div class='cf-card'>"
                + _pill(_s(s.get("source_system")).replace("_", " "), "pl")
                + " " + _pill("Priority " + _n(s.get("priority")))
                + "<p style='margin:8px 0 4px;font-weight:600'>"
                + e(s.get("topic")) + "</p>"
                + "<p class='cf-meta'>" + e(_evidence_line(s)) + "</p>"
                + button("Create Plan", "human",
                         onclick="cfPlan('" + e(s.get("id")) + "')",
                         small=True)
                + button("Create Variations", "ai",
                         onclick="cfVary('" + e(s.get("id")) + "')",
                         small=True)
                + "</div>")
    body.append("</div><div>")
    body.append("<p class='cf-h2'>Workflow</p><div class='cf-card'>")
    for label, key in (("Idea", "idea"), ("Brief", "brief"),
                       ("Creating", "creating"), ("Review", "review"),
                       ("Approved", "approved")):
        body.append("<div class='cf-row'><span>" + label + "</span><b>"
                    + _n(counts.get(key), "0") + "</b></div>")
    body.append("</div>")
    body.append("<p class='cf-note cf-"
                + ("ok" if loop["state"] == "CLOSING"
                   else "wa" if loop["state"] == "NOT YET CLOSED"
                   else "mu") + "'>Loop: " + e(loop["state"]) + ". "
                + e(loop["why"]) + "</p>")
    body.append("</div></div>")

    body.append("<div class='cf-cols'><div>")
    body.append("<p class='cf-h2'>Needs review</p>")
    if not review:
        body.append(empty("Nothing is waiting on a reviewer",
                          "When a draft passes QA it appears here.", "",
                          "human"))
    else:
        for x in review:
            body.append("<div class='cf-row'><span>"
                        + e(x.get("title")) + "</span>"
                        + status_pill(x.get("status")) + "</div>")
        body.append(button("Open Review Queue", "human",
                           onclick="cfGo('cfreview')"))
    body.append("</div><div>")
    body.append("<p class='cf-h2'>Recent learning</p>")
    if not learning:
        body.append(empty("No learning yet",
                          "Learning appears once published content has "
                          "returned performance and a result has been "
                          "classified. Until then the planner is working "
                          "from signals alone.", "Open Performance",
                          "secondary", "cfGo('cfperf')"))
    else:
        for lr in learning:
            lift = lr.get("lift")
            arrow = ("↑" if (_f(lift, 0) or 0) > 0
                     else "↓" if (_f(lift, 0) or 0) < 0 else "→")
            body.append("<div class='cf-row'><span>"
                        + e(_s(lr.get("attribute_value")) or "unnamed")
                        + " <span class='cf-meta'>"
                        + e(_s(lr.get("attribute_type"))) + " · n="
                        + _n(lr.get("sample_size")) + "</span></span><b>"
                        + arrow + " " + _n(lift, "not compared")
                        + "</b></div>")
        body.append(button("Use in Planner", "secondary",
                           onclick="cfGo('cfplan')"))
    body.append("</div></div>")
    return "".join(body)


def _evidence_line(sig) -> str:
    s = _d(sig)
    bits = []
    if s.get("metric_name") and s.get("metric_value") is not None:
        bits.append(_s(s["metric_name"]) + " " + _s(s["metric_value"]))
    ev = s.get("evidence_json")
    if isinstance(ev, list) and ev:
        bits.append(str(len(ev)) + " evidence item(s)")
    if not bits:
        return ("no evidence attached, so nothing here may be quoted as "
                "fact in a brief")
    return " · ".join(bits)


# ===========================================================================
# SCREEN 02 - INBOX (sections 15-17, 102)
# ===========================================================================
INBOX_TABS = ("All", "SEO", "Paid", "Social", "CRM", "Email", "Manual")

_TAB_SOURCE = {"SEO": "SEO_OS", "Paid": "MEDIA_BUYING_OS",
               "Social": "SOCIAL_OS", "CRM": "CRM_OS",
               "Email": "EMAIL_OS", "Manual": "MANUAL"}


def inbox(ctx=None) -> str:
    """Section 102: where it came from, what happened, why it matters."""
    c = _d(ctx)
    sigs = [FOS.normalize_signal(s) for s in _l(c.get("signals"))]
    tab = _s(c.get("inbox_tab") or "All")
    if tab in _TAB_SOURCE:
        sigs = [s for s in sigs
                if s.get("source_system") == _TAB_SOURCE[tab]]
    out = ["<p class='cf-h1'>Content Inbox</p>",
           "<div>" + "".join(
               button(t, "secondary" if t != tab else "human",
                      onclick="cfInboxTab('" + t + "')", small=True)
               for t in INBOX_TABS) + "</div>",
           "<div>" + button("Analyze Inbox", "ai",
                            onclick="cfAnalyzeInbox()") + "</div>"]
    if not sigs:
        out.append(empty(
            "No signals",
            "Signals arrive here from the SEO OS, the Media Buying OS, "
            "the Email OS, the CRM and Analytics. This screen shows what "
            "those systems observed; it does not observe anything "
            "itself.", "", "human"))
        return "".join(out)
    for s in sorted(sigs, key=lambda x: -(_f(x.get("priority"), 0) or 0)):
        act = FOS.signal_is_actionable(s)
        pr = _f(s.get("priority"), 0) or 0
        band = "HIGH" if pr >= 70 else "MEDIUM" if pr >= 40 else "LOW"
        tone = "er" if band == "HIGH" else "wa" if band == "MEDIUM" else ""
        ev = s.get("evidence_json")
        ev_rows = ("".join("<li>" + e(_evidence_item(x)) + "</li>"
                           for x in _l(ev))
                   if isinstance(ev, list) else "")
        out.append(
            "<div class='cf-card'>"
            + _pill(band, tone) + " "
            + _pill(_s(s.get("source_system")).replace("_", " "), "pl")
            + " " + _pill(_s(s.get("signal_type")).replace("_", " "))
            + ("" if not s.get("unknown_source") else
               " " + _pill("unknown source", "wa"))
            + "<p style='margin:8px 0 2px;font-size:15px;font-weight:600'>"
            + e(s.get("topic")) + "</p>"
            + ("<p class='cf-meta'>" + e(s.get("message")) + "</p>"
               if s.get("message") else "")
            + ("<p class='cf-h2' style='margin:10px 0 4px;font-size:12px'>"
               "Evidence</p><ul class='cf-meta' style='margin:0 0 8px;"
               "padding-left:18px'>" + ev_rows + "</ul>" if ev_rows else
               "<p class='cf-note cf-wa'>No evidence was attached. This "
               "can still be planned, but nothing in it may be quoted as "
               "fact.</p>")
            + ("<p class='cf-meta'>Suggested: "
               + e(", ".join(_s(x) for x in _l(
                   s.get("recommended_format"))) or "not suggested")
               + "</p>")
            + ("<p class='cf-meta'>Confidence: "
               + _n(s.get("confidence"), "not stated") + "</p>")
            + (button("Create Plan", "human",
                      onclick="cfPlan('" + e(s.get("id")) + "')",
                      small=True)
               if act.get("ok") else
               "<p class='cf-note cf-er'>" + e(act.get("why")) + "</p>")
            + button("Create Variations", "ai",
                     onclick="cfVary('" + e(s.get("id")) + "')", small=True)
            + button("Dismiss", "destructive",
                     onclick="cfDismiss('" + e(s.get("id")) + "')",
                     small=True)
            + "</div>")
    return "".join(out)


def _evidence_item(x) -> str:
    if isinstance(x, dict):
        return " ".join(_s(k) + ": " + _s(v) for k, v in x.items())
    return _s(x)


def signal_drawer(sig) -> str:
    """Section 17. One signal, in full, with its business reason."""
    s = FOS.normalize_signal(sig) if sig else {}
    if not s.get("topic"):
        return empty("No signal selected",
                     "Open a signal to see its source, evidence and the "
                     "content it suggests.", "", "human")
    rows = (("Source", s.get("source_system")),
            ("Signal type", s.get("signal_type")),
            ("Metric", _s(s.get("metric_name")) + " "
             + _n(s.get("metric_value"), "")),
            ("Priority", _n(s.get("priority"), "not stated")),
            ("Confidence", _n(s.get("confidence"), "not stated")),
            ("Received", s.get("received_at")),
            ("Expires", s.get("expires_at") or "no expiry set"),
            ("Suggested", ", ".join(_s(x) for x in
                                    _l(s.get("recommended_format")))
             or "not suggested"))
    return ("<p class='cf-h2'>" + e(s.get("topic")) + "</p>"
            + "<div class='cf-card'>"
            + "".join("<div class='cf-row'><span class='cf-meta'>"
                      + e(k) + "</span><b>" + e(v or "not recorded")
                      + "</b></div>" for k, v in rows)
            + "</div>"
            + "<p class='cf-note'>The sending system computed these. "
            + "The factory records them and never recomputes or corrects "
            + "another OS's numbers.</p>"
            + button("Create Content Plan", "human",
                     onclick="cfPlan('" + e(s.get("id")) + "')"))


# ===========================================================================
# SCREEN 03 - PLANNER (sections 18-23)
# ===========================================================================
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday")


def planner(ctx=None) -> str:
    c = _d(ctx)
    plan = _d(c.get("plan"))
    items = [_d(x) for x in _l(plan.get("items"))]
    mode = _s(c.get("plan_mode") or "Week")
    out = ["<p class='cf-h1'>Planner</p>",
           "<div>" + "".join(
               button(m, "human" if m == mode else "secondary",
                      onclick="cfPlanMode('" + m + "')", small=True)
               for m in ("Week", "Month", "Campaign")) + "</div>",
           "<div>" + button("Add Content", "human", onclick="cfAdd()")
           + button("AI Plan Week", "ai", onclick="cfPlanWeek()")
           + "</div>"]
    if not items:
        out.append(empty(
            "No plan yet",
            "A plan comes from accepted signals. The planner drafts it "
            "and you accept, edit or reject each item: it never schedules "
            "anything on its own, because a calendar that fills itself "
            "makes every approval after it decorative.",
            "Build Plan", "ai", "cfPlanWeek()"))
        return "".join(out)
    st = _s(plan.get("status") or "DRAFT").upper()
    out.append("<p class='cf-note'>Plan status: " + e(st)
               + ". Allowed next: "
               + e(", ".join(FOS.PLAN_MOVES.get(st, ())) or "nothing")
               + ".</p>")
    if _s(mode) == "Week":
        out.append("<div class='cf-grid' style='grid-template-columns:"
                   "repeat(auto-fit,minmax(150px,1fr))'>")
        for i, day in enumerate(DAYS[:5]):
            todays = [x for x in items
                      if _s(x.get("weekday")).lower() == day.lower()
                      or (x.get("weekday") is None
                          and items.index(x) % 5 == i)]
            out.append("<div class='cf-card'><p class='cf-meta'>"
                       + day + "</p>")
            for x in todays:
                out.append("<p style='margin:6px 0 2px;font-weight:600;"
                           "font-size:13px'>" + e(x.get("topic")) + "</p>"
                           + _pill(_s(x.get("format") or "format not set"))
                           + " " + status_pill(x.get("status"))
                           + "<p class='cf-meta'>" + e(x.get("because"))
                           + "</p>")
            if not todays:
                out.append("<p class='cf-meta'>nothing planned</p>")
            out.append("</div>")
        out.append("</div>")
    rows = "".join(
        "<tr><td>" + e(x.get("topic")) + "</td>"
        + "<td>" + e(x.get("channel") or "not set") + "</td>"
        + "<td>" + e(x.get("format") or "not set") + "</td>"
        + "<td>" + e(x.get("paid_or_organic") or "not set") + "</td>"
        + "<td>" + _n(x.get("priority"), "not ranked") + "</td>"
        + "<td>" + status_pill(x.get("status")) + "</td>"
        + "<td class='cf-meta'>" + e(x.get("because")) + "</td></tr>"
        for x in items)
    out.append("<div class='cf-scroll'><table class='cf-tbl'><thead><tr>"
               "<th>Topic</th><th>Channel</th><th>Format</th>"
               "<th>Paid/Organic</th><th>Priority</th><th>Status</th>"
               "<th>Why this</th></tr></thead><tbody>" + rows
               + "</tbody></table></div>")
    out.append(button("Accept All", "human", onclick="cfAcceptAll()")
               + button("Accept Selected", "human",
                        onclick="cfAcceptSel()")
               + button("Edit", "secondary", onclick="cfEditPlan()")
               + button("Reject", "destructive", onclick="cfRejectPlan()"))
    if plan.get("learning_used"):
        out.append("<p class='cf-note'>This draft used "
                   + str(len(_l(plan.get("learning_used"))))
                   + " past learning record(s). The loop is feeding the "
                   "planner.</p>")
    return "".join(out)


# ===========================================================================
# SCREEN 04 - STUDIO (sections 24-36, 39-42, 103)
# ===========================================================================
def studio(ctx=None) -> str:
    """Three panes, section 24. Chat is NOT the main UI."""
    c = _d(ctx)
    item = _d(c.get("content"))
    if not item:
        return ("<p class='cf-h1'>Studio</p>"
                + empty("No content open",
                        "The Studio works on one content item at a time. "
                        "Open one from the Planner or the Review queue.",
                        "Create Content", "human", "cfCreate()"))
    blocks = [_d(b) for b in _l(item.get("blocks"))]
    brief = _d(item.get("brief"))
    versions = _l(item.get("versions"))
    out = ["<p class='cf-h1'>" + e(item.get("title") or "Untitled")
           + "</p>",
           "<div class='cf-card' style='display:flex;flex-wrap:wrap;"
           "gap:8px;align-items:center;justify-content:space-between'>"
           # The brief holds the format. Reading only item.format made
           # this header say "format not set" beside a brief that said
           # SHORT_VIDEO: two places holding one fact and disagreeing.
           + "<div>" + _pill(_s(item.get("format")
                                or brief.get("format")
                                or "format not set"))
           + " " + status_pill(item.get("status")) + " "
           + _pill("v" + _s(len(versions))) + " "
           + _pill(_s(item.get("owner") or "no owner")) + "</div>"
           + "<div>" + button("Save", "human", onclick="cfSave()",
                              small=True)
           + button("Preview", "secondary", onclick="cfPreview()",
                    small=True)
           + button("Send to Review", "human", onclick="cfToReview()",
                    small=True)
           + button("Generate Variants", "ai", onclick="cfVariants()",
                    small=True) + "</div></div>",
           "<div class='cf-studio'>"]

    # ---- left: context
    out.append("<div><p class='cf-h2'>Brief</p><div class='cf-card'>")
    if not brief:
        out.append("<p class='cf-note cf-wa'>No brief attached. Anything "
                   "written here has no stated objective, audience or "
                   "success metric to be judged against.</p>")
    else:
        for k in ("objective", "audience", "funnel_stage", "topic",
                  "primary_message", "cta", "channel", "format",
                  "paid_or_organic", "success_metric"):
            out.append("<div class='cf-row'><span class='cf-meta'>"
                       + e(k.replace("_", " ").title())
                       + "</span><b>" + e(brief.get(k) or "not set")
                       + "</b></div>")
    out.append("</div>")
    out.append("<p class='cf-h2'>Data</p><div class='cf-card'>")
    ev = _l(brief.get("supporting_points"))
    if not ev:
        out.append("<p class='cf-note'>No evidence is attached to this "
                   "brief. The Copilot cannot cite a number that is not "
                   "here, which is the point of this panel.</p>")
    else:
        for x in ev:
            out.append("<p class='cf-meta'>" + e(_evidence_item(x))
                       + "</p>")
        src = _d(brief.get("evidence")).get("source_system")
        out.append("<p class='cf-meta'>Source: " + e(src or "not recorded")
                   + "</p>")
    out.append("</div></div>")

    # ---- centre: the blocks
    out.append("<div><p class='cf-h2'>Content</p>")
    if not blocks:
        out.append(empty("Nothing written yet",
                         "Write directly, or ask the Copilot for a first "
                         "draft against the brief.",
                         "Generate Draft", "ai", "cfDraft()"))
    for b in blocks:
        locked = b.get("locked")
        out.append(
            "<div class='cf-blk'><header><b>" + e(b.get("type")) + "</b>"
            + ("<span class='cf-lock'>\U0001F512 locked by a human"
               "</span>" if locked else "")
            + "</header><div>" + e(b.get("text")) + "</div>"
            + ("" if locked else
               button("Rewrite", "ai", small=True,
                      onclick="cfBlock('REWRITE','" + e(b.get("id")) + "')")
               + button("Shorten", "ai", small=True,
                        onclick="cfBlock('SHORTEN','" + e(b.get("id"))
                        + "')")
               + button("Expand", "ai", small=True,
                        onclick="cfBlock('EXPAND','" + e(b.get("id"))
                        + "')"))
            + "</div>")
    out.append("</div>")

    # ---- right: copilot
    out.append("<div><p class='cf-h2'>Copilot</p><div class='cf-card'>")
    for label, act in (("Generate Draft", "GENERATE_DRAFT"),
                       ("Improve Hook", "IMPROVE_HOOK"),
                       ("Create Variants", "CREATE_VARIANTS"),
                       ("Generate Image", "GENERATE_IMAGE"),
                       ("Adapt Platform", "ADAPT_PLATFORM"),
                       ("Create Video Concept", "CREATE_VIDEO_CONCEPT")):
        out.append(button(label, "ai", small=True,
                          onclick="cfAct('" + act + "')"))
    out.append("<p class='cf-note'>Selecting text first scopes an action "
               "to that block. Without a selection a rewrite would "
               "regenerate the whole piece and discard every edit you "
               "made.</p></div>")
    out.append("<p class='cf-h2'>Versions</p><div class='cf-card'>")
    if not versions:
        out.append("<p class='cf-meta'>No versions yet.</p>")
    for v in list(reversed(versions))[:8]:
        vd = _d(v)
        out.append("<div class='cf-row'><span>v"
                   + _s(vd.get("version_number")) + " "
                   + _pill(_s(vd.get("source")),
                           "ai" if vd.get("source") == "AGENT" else "")
                   + "</span><span class='cf-meta'>"
                   + e(vd.get("change_summary") or "no summary")
                   + "</span></div>")
    out.append(button("Compare", "secondary", onclick="cfCompare()",
                      small=True)
               + button("Restore", "human", onclick="cfRestore()",
                        small=True))
    out.append("</div></div>")
    out.append("</div>")
    return "".join(out)


def diff_view(before, after) -> str:
    """Section 36. Added green, removed red, per block."""
    rows = FOS.diff_blocks(before, after)
    if not rows:
        return ("<p class='cf-h2'>Diff</p><p class='cf-note'>Nothing "
                "changed between these two versions.</p>")
    out = ["<p class='cf-h2'>Diff</p>"]
    for r in rows:
        out.append("<div class='cf-blk'><header><b>"
                   + e(r.get("type")) + "</b> " + _pill(
                       _s(r.get("state")),
                       "ok" if r["state"] == "ADDED"
                       else "er" if r["state"] == "REMOVED" else "wa")
                   + "</header>")
        if r.get("before") is not None:
            out.append("<span class='cf-diff-del'>" + e(r["before"])
                       + "</span>")
        if r.get("after") is not None:
            out.append("<span class='cf-diff-add'>" + e(r["after"])
                       + "</span>")
        out.append("</div>")
    out.append(button("Accept", "human", onclick="cfAcceptDiff()")
               + button("Reject", "destructive", onclick="cfRejectDiff()")
               + button("Edit", "secondary", onclick="cfEditDiff()"))
    return "".join(out)


def image_drawer(ctx=None) -> str:
    """Section 39. Ask for an image, honestly, through the router."""
    route = FOS.route_tool("IMAGE_GENERATION")
    out = ["<p class='cf-h2'>Generate image</p>"]
    if not route["available"]:
        out.append(empty("Image generation is not available",
                         _s(route["why"]), "Connect", "human",
                         "cfGo('cfset')"))
        return "".join(out)
    for label in ("Purpose", "Visual direction", "Aspect ratio",
                  "Reference asset", "Brand assets", "Text instruction"):
        out.append("<div class='cf-row'><span class='cf-meta'>"
                   + label + "</span><b class='cf-mu'>not set</b></div>")
    out.append(button("Generate", "ai", onclick="cfGenImage()"))
    out.append("<p class='cf-note'>Returns two to four candidates. "
               "Nothing is inserted until you pick one; the original is "
               "never overwritten, an edit creates an asset version.</p>")
    return "".join(out)


# ===========================================================================
# SCREEN 05 - LIBRARY (sections 47-49)
# ===========================================================================
LIB_TABS = ("All", "Images", "Video", "Brand Assets", "Generated",
            "Uploaded")


def library(ctx=None) -> str:
    """Section 47: not a DAM. Enough to find and reuse an asset."""
    c = _d(ctx)
    assets = [_d(a) for a in _l(c.get("assets"))]
    out = ["<p class='cf-h1'>Library</p>",
           "<div>" + "".join(button(t, "secondary", small=True,
                                    onclick="cfLib('" + t + "')")
                             for t in LIB_TABS) + "</div>",
           "<div>" + button("Upload", "human", onclick="cfUpload()")
           + button("Generate", "ai", onclick="cfGenImage()") + "</div>"]
    if not assets:
        out.append(empty("No assets",
                         "Uploaded and generated assets appear here with "
                         "their versions and where they are used. This is "
                         "a working library, not a full DAM.",
                         "Upload", "human", "cfUpload()"))
        return "".join(out)
    rows = "".join(
        "<tr><td>" + e(a.get("name") or "unnamed") + "</td>"
        + "<td>" + e(a.get("type") or "unknown") + "</td>"
        + "<td>" + e(a.get("dimensions") or "not recorded") + "</td>"
        + "<td>" + e(a.get("source") or "not recorded") + "</td>"
        + "<td>" + e(a.get("campaign") or "none") + "</td>"
        + "<td>" + _n(len(_l(a.get("used_in"))), "0") + "</td>"
        + "<td>" + e(a.get("created_by") or "not recorded") + "</td>"
        + "<td>" + status_pill(a.get("status")) + "</td></tr>"
        for a in assets)
    out.append("<div class='cf-scroll'><table class='cf-tbl'><thead><tr>"
               "<th>Name</th><th>Type</th><th>Dimensions</th>"
               "<th>Source</th><th>Campaign</th><th>Used in</th>"
               "<th>Created by</th><th>Status</th>"
               "</tr></thead><tbody>" + rows + "</tbody></table></div>")
    return "".join(out)


# ===========================================================================
# SCREEN 06 - REVIEW (sections 50-54, 104)
# ===========================================================================
def social(ctx=None) -> str:
    """SOCIAL, REHOMED. SGA held these screens and SGA is retired; the
    system that decides what goes out on social is this one, so its
    channels, engagement, audience and posts land here rather than
    becoming unreachable code. The Google hub went to Search and paid
    went to Media Buying, which already own those questions."""
    c = _d(ctx)
    try:
        import content_engine_sga_screens as SG
    except Exception as exc:                          # noqa: BLE001
        return ("<p class='cf-h1'>Social</p>"
                + empty("The social screens did not load",
                        "They moved here when SGA was retired. Reason: "
                        + _s(type(exc).__name__)))
    # THE SCREEN TRAVELS WHOLE: markup, stylesheet AND handlers. Moving
    # the markup alone left fourteen unstyled classes and two dead
    # buttons; the gates caught both, which is exactly why they exist.
    # SG.CSS is RAW rules, not a stylesheet: emitted bare it is just text
    # on the page, which is why fourteen classes still read as unstyled
    # after the first fix. The boards module wrapped it; so must this.
    _sgcss = getattr(SG, "CSS", "")
    out = [("<style>" + _sgcss + "</style>") if _sgcss else "",
           getattr(SG, "JS", ""),
           "<p class='cf-h1'>Social</p>",
           "<p class='cf-note'>These moved here when the SGA section was "
           "retired: the system that decides what goes out on social is "
           "this one. The Google hub is in Search, paid is in Media "
           "Buying.</p>"]
    for label, fn in (("Channels", "channels_screen"),
                      ("Engagement", "engagement_screen"),
                      ("Audience", "audience_screen"),
                      ("Posts", "posts_screen")):
        f = getattr(SG, fn, None)
        if not callable(f):
            continue
        out.append("<p class='cf-h2'>" + e(label) + "</p>")
        try:
            out.append(f(c))
        except Exception as exc:                      # noqa: BLE001
            out.append("<p class='cf-note cf-wa'>" + e(label)
                       + " could not render: " + e(type(exc).__name__)
                       + ". The other screens are unaffected.</p>")
    return "".join(out)


def review(ctx=None) -> str:
    """Three columns, section 50. A reviewer never opens the Studio."""
    c = _d(ctx)
    queue = [_d(x) for x in _l(c.get("queue"))]
    current = _d(c.get("current"))
    out = ["<p class='cf-h1'>Review</p>"]
    if not queue and not current:
        out.append(empty("Nothing to review",
                         "Drafts arrive here after QA runs. Approving is "
                         "a human action: an agent can recommend it and "
                         "cannot grant it.", "", "human"))
        return "".join(out)
    out.append("<div class='cf-review'><div><p class='cf-h2'>Queue</p>")
    for q in queue:
        # EVERY PIECE IS OPENABLE. The queue used to be a list you could
        # look at and not read: only the newest piece was ever previewed,
        # so approving any other one meant approving unseen.
        _jid = _s(q.get("job_id") or q.get("id"))
        _on = " cf-on" if _jid and _jid == _s(current.get("job_id")) else ""
        out.append("<a class='cf-row" + _on + "' href='?piece=" + e(_jid)
                   + "#content'><span>" + e(q.get("title"))
                   + "<br><span class='cf-meta'>"
                   + e(q.get("channel") or "channel not set")
                   + (" &middot; " + str(q.get("words")) + " words"
                      if q.get("words") else "")
                   + "</span></span>"
                   + status_pill(q.get("status") or q.get("state"))
                   + "</a>")
    out.append("</div>")

    out.append("<div><p class='cf-h2'>Preview</p><div class='cf-card'>")
    blocks = [_d(b) for b in _l(current.get("blocks"))]
    if not blocks:
        out.append("<p class='cf-meta'>"
                   + ("This piece carries no readable body yet. It was "
                      "queued before the writer finished, or its output "
                      "was not recorded."
                      if current else "Select an item to preview it.")
                   + "</p>")
    # THE PIECE AS IT WILL LOOK, per channel. previews() has rendered a
    # blog page, a LinkedIn card and the rest on every load for months
    # and no screen ever read it, so a reviewer approved a table of raw
    # text instead of the thing that goes out.
    _pv = _d(c.get("previews"))
    _byp = _d(_pv.get("by_platform"))
    if _byp:
        out.append("<p class='cf-meta'>How it will look</p>")
        for _plat, _data in _byp.items():
            _pd = _d(_data)
            _html = _s(_pd.get("html"))
            if not _html:
                continue
            _fails = [x for x in _l(_pd.get("checks"))
                      if isinstance(x, (list, tuple)) and len(x) > 1
                      and not x[1]]
            out.append("<div class='cf-blk'><header><b>"
                       + e(_s(_plat).title()) + "</b> "
                       + "<span class='cf-meta'>"
                       + (str(_pd.get("words")) + " words"
                          if _pd.get("words") else "")
                       + (" &middot; " + str(len(_fails)) + " check(s) not met"
                          if _fails else " &middot; every check met")
                       + "</span></header><div>" + _html + "</div>")
            for _ch in _fails[:4]:
                out.append("<p class='cf-note cf-wa'>" + e(_s(_ch[0])) + ": "
                           + e(_s(_ch[2] if len(_ch) > 2 else "")) + "</p>")
            out.append("</div>")
        if _pv.get("blocked"):
            out.append("<p class='cf-note cf-wa'>Not previewable here: "
                       + e(", ".join(_s(b) for b in _l(_pv.get("blocked"))))
                       + " &mdash; those channels need media this piece "
                         "does not carry.</p>")
        out.append("<p class='cf-meta'>The words themselves</p>")
    for b in blocks:
        _txt = _s(b.get("text"))
        out.append("<div class='cf-blk'><header><b>" + e(b.get("type"))
                   + "</b></header><div style='white-space:pre-wrap'>"
                   + e(_txt) + "</div></div>")
    if current.get("job_id"):
        # APPROVING IS A HUMAN ACTION, and it belongs beside the words it
        # applies to. The endpoint is the same one the queue has always
        # used; nothing here can approve on your behalf.
        _jid2 = e(_s(current.get("job_id")))
        # NO BROWSER PROMPTS ON THE APPROVAL ROW. A prompt() steals the
        # window, cannot be corrected once dismissed, and loses what you
        # typed if you misclick - this codebase already fought that fight
        # once and the rule outlived the fix. The note is an inline field
        # that stays on the page with the words it refers to.
        out.append("<div class='cf-row' style='margin-top:10px;gap:6px'>"
                   "<span><button class='cf-btn cf-btn-human' "
                   "onclick=\"cfApprove('" + _jid2 + "',this)\">"
                   "Approve and publish</button> "
                   "<button class='cf-btn' onclick=\"cfNoteOpen('"
                   + _jid2 + "','changes')\">Request changes</button> "
                   "<button class='cf-btn' onclick=\"cfNoteOpen('"
                   + _jid2 + "','reject')\">Reject</button> "
                   "<button class='cf-btn' onclick=\"cfNoteOpen('"
                   + _jid2 + "','variant')\">Make a variant</button></span>"
                   "<span class='cf-meta'>publishes to your site; "
                   "nothing is sent without this click</span></div>"
                   "<div class='cf-card' id='cf-note-" + _jid2 + "' "
                   "style='display:none;margin-top:8px'>"
                   "<p class='cf-meta' id='cf-notewhy-" + _jid2 + "'></p>"
                   "<textarea id='cf-notetext-" + _jid2 + "' rows='3' "
                   "style='width:100%;font:inherit;font-size:12px;"
                   "border:1px solid var(--bd);border-radius:8px;"
                   "padding:8px'></textarea>"
                   "<div class='cf-row' style='margin-top:6px'>"
                   "<span><button class='cf-btn cf-btn-human' "
                   "onclick=\"cfNoteSend('" + _jid2 + "',this)\">"
                   "Send</button> "
                   "<button class='cf-btn' onclick=\"cfNoteClose('"
                   + _jid2 + "')\">Cancel</button></span>"
                   "<span class='cf-meta'>recorded, so the engine learns "
                   "from it</span></div></div>")
    out.append("</div></div>")

    out.append("<div><p class='cf-h2'>Checks</p><div class='cf-card'>")
    qa = _d(current.get("qa"))
    checks = _l(qa.get("checks"))
    if not checks:
        out.append("<p class='cf-note cf-wa'>QA has not run on this item. "
                   "Approving now means approving unchecked.</p>")
    for ch in checks:
        cd = _d(ch)
        st = _s(cd.get("state")).upper()
        out.append("<div class='cf-row'><span>"
                   + e(_s(cd.get("check")).replace("_", " ").title())
                   + "</span>" + _pill(st, {"PASS": "ok", "WARNING": "wa",
                                            "FAIL": "er"}.get(st, ""))
                   + "</div>"
                   + ("<p class='cf-meta'>" + e(cd.get("why")) + "</p>"
                      if st != "PASS" else ""))
    out.append("</div>")
    out.append("<p class='cf-h2'>Comments</p><div class='cf-card'>")
    cm = _l(current.get("comments"))
    if not cm:
        out.append("<p class='cf-meta'>No comments.</p>")
    for x in cm:
        xd = _d(x)
        out.append("<div class='cf-row'><span>" + e(xd.get("author"))
                   + "</span><span class='cf-meta'>" + e(xd.get("text"))
                   + "</span></div>")
    out.append("</div></div></div>")

    blocking = _l(qa.get("blocking"))
    out.append("<div class='cf-card'>")
    if blocking:
        out.append("<p class='cf-note cf-er'>QA returned FAIL on "
                   + str(len(blocking)) + " check(s). Approval is "
                   "available but you are approving over a known "
                   "failure, and the audit log records that.</p>")
    out.append(button("Reject", "destructive", onclick="cfReject()")
               + button("Request Changes", "human",
                        onclick="cfRequestChanges()")
               + button("Approve", "human", onclick="cfApprove()")
               + button("Send to Distribution", "human",
                        onclick="cfApproveSend()"))
    out.append("<p class='cf-note'>Approval records who granted it. An "
               "approval nobody signed cannot be defended later, so the "
               "state machine refuses one.</p></div>")
    return "".join(out)


# ===========================================================================
# SCREEN 07 - DISTRIBUTION (sections 55-60)
# ===========================================================================
DIST_TABS = ("Ready", "Sent", "Scheduled", "Published", "Failed")


def distribution(ctx=None) -> str:
    """Section 56. The factory hands off; it does not execute."""
    c = _d(ctx)
    pkgs = [_d(p) for p in _l(c.get("packages"))]
    out = ["<p class='cf-h1'>Distribution</p>",
           "<div>" + "".join(button(t, "secondary", small=True,
                                    onclick="cfDist('" + t + "')")
                             for t in DIST_TABS) + "</div>",
           ("<p class='cf-note'>Each package leaves for the system that "
            "owns execution. The factory supplies creative and never the "
            "audience, budget, bid or send time: those belong to the "
            "Media Buying OS, the Email OS and the SEO OS.</p>")]
    out.append("<div class='cf-card'><p class='cf-h2' "
               "style='margin-top:0'>Who executes what</p>")
    for ch, (dest, owns) in FOS.DESTINATIONS.items():
        out.append("<div class='cf-row'><span>" + e(ch) + "</span>"
                   + "<span class='cf-meta'>" + e(dest) + " owns "
                   + e(owns) + "</span></div>")
    out.append("</div>")
    if not pkgs:
        out.append(empty("Nothing queued",
                         "Approved content becomes a package here, "
                         "addressed to the OS that will execute it.",
                         "Open Review Queue", "human",
                         "cfGo('cfreview')"))
        return "".join(out)
    rows = "".join(
        "<tr><td>" + e(p.get("variant_id")) + "</td>"
        + "<td>" + e(p.get("channel")) + "</td>"
        + "<td>" + e(p.get("destination_system")) + "</td>"
        + "<td>" + status_pill(p.get("state")) + "</td>"
        + "<td>" + e(p.get("external_object_id") or "none yet") + "</td>"
        + "<td class='cf-meta'>" + e(p.get("why")) + "</td></tr>"
        for p in pkgs)
    out.append("<div class='cf-scroll'><table class='cf-tbl'><thead><tr>"
               "<th>Variant</th><th>Channel</th><th>Destination</th>"
               "<th>State</th><th>External id</th><th>Detail</th>"
               "</tr></thead><tbody>" + rows + "</tbody></table></div>")
    out.append("<p class='cf-note'>ACCEPTED is not PUBLISHED. A "
               "destination accepting a package means it received it; the "
               "package is published only when that system says so.</p>")
    return "".join(out)


# ===========================================================================
# SCREEN 08 - PERFORMANCE (sections 61-71, 105)
# ===========================================================================
def performance(ctx=None) -> str:
    """Section 61: CONTENT performance. Not GA4, not Media Buying."""
    c = _d(ctx)
    variants = [_d(v) for v in _l(c.get("variants"))]
    learning = [_d(x) for x in _l(c.get("learning"))]
    out = ["<p class='cf-h1'>Content Performance</p>",
           ("<p class='cf-note'>This screen answers one question: what "
            "should we make more of. Spend, reach and revenue are shown "
            "as the execution systems reported them; it does not "
            "recompute another OS's numbers or try to be its "
            "dashboard.</p>")]
    if not variants:
        out.append(empty("No performance returned yet",
                         "Performance arrives from the systems that "
                         "executed the content. Until a variant has been "
                         "distributed and measured there is nothing here, "
                         "and nothing to learn from.",
                         "Open Distribution", "secondary",
                         "cfGo('cfdist')"))
        return "".join(out)
    rows_perf = []
    for v in variants:
        rows_perf.extend(_l(v.get("performance")))
    tot = FOS.aggregate(rows_perf)
    out.append("<div class='cf-kpis'>"
               + kpi("Published", len(variants))
               + kpi("Reach", tot.get("reach"))
               + kpi("Clicks", tot.get("clicks"))
               + kpi("Conversions", tot.get("conversions"))
               + kpi("Revenue", tot.get("revenue"))
               + kpi("CTR %", (None if tot.get("ctr") is None
                               else round(tot["ctr"] * 100, 2)),
                     note="summed, then divided once")
               + "</div>")
    body = "".join(
        "<tr><td>" + e(v.get("title") or v.get("id")) + "</td>"
        + "<td>" + e(v.get("channel")) + "</td>"
        + "<td>" + e(v.get("format")) + "</td>"
        + "<td>" + _n(FOS.aggregate(_l(v.get("performance"))).get("reach"))
        + "</td>"
        + "<td>" + _n(FOS.aggregate(_l(v.get("performance"))).get("clicks"))
        + "</td>"
        + "<td>" + _n(FOS.aggregate(_l(v.get("performance")))
                      .get("conversions")) + "</td>"
        + "<td>" + _result_pill(v.get("result")) + "</td></tr>"
        for v in variants)
    out.append("<div class='cf-scroll'><table class='cf-tbl'><thead><tr>"
               "<th>Content</th><th>Channel</th><th>Format</th>"
               "<th>Reach</th><th>Clicks</th><th>Conversions</th>"
               "<th>Result</th></tr></thead><tbody>" + body
               + "</tbody></table></div>")
    out.append("<div class='cf-cols'><div><p class='cf-h2'>What we have "
               "learned</p>")
    if not learning:
        out.append(empty("No learning yet",
                         "A learning needs a target metric, a baseline "
                         "and enough sample. Until one exists the planner "
                         "is working from signals alone.", "", "human"))
    for lr in learning:
        out.append("<div class='cf-row'><span>"
                   + e(lr.get("attribute_value")) + " <span class='cf-meta'>"
                   + e(lr.get("attribute_type")) + " on "
                   + e(lr.get("channel")) + "</span></span><b>"
                   + _n(lr.get("lift"), "not compared") + "% · n="
                   + _n(lr.get("sample_size")) + " · "
                   + e(lr.get("confidence")) + "</b></div>")
    out.append("</div><div><p class='cf-h2'>How a result is decided</p>"
               "<div class='cf-card'>")
    for name in FOS.RESULTS:
        out.append("<div class='cf-row'><span>" + name + "</span>"
                   + "<span class='cf-meta'>"
                   + e(_result_reason(name)) + "</span></div>")
    out.append("</div></div></div>")
    return "".join(out)


def _result_pill(result) -> str:
    r = _d(result)
    name = _s(r.get("result") or result or "INSUFFICIENT_DATA").upper()
    tone = {"WINNER": "ok", "STRONG": "ok", "NORMAL": "",
            "WEAK": "wa", "INSUFFICIENT_DATA": ""}.get(name, "")
    return _pill(name.replace("_", " ").title(), tone)


def _result_reason(name) -> str:
    return {
        "WINNER": "at least 1.5x the baseline, with enough sample",
        "STRONG": "at least 1.15x the baseline",
        "NORMAL": "within 15% of the baseline either way",
        "WEAK": "below 85% of the baseline",
        "INSUFFICIENT_DATA": ("no baseline, no target metric, or below "
                              "the sample floor. Not 'average': too few "
                              "to tell."),
    }.get(name, "")


# ===========================================================================
# SCREEN 09 - SETTINGS (sections 80-83)
# ===========================================================================
def settings(ctx=None) -> str:
    c = _d(ctx)
    brand = _d(c.get("brand_profile"))
    wf = _d(c.get("workflow"))
    out = ["<p class='cf-h1'>Settings</p>",
           "<p class='cf-h2'>Brand</p><div class='cf-card'>"]
    for k in ("name", "description", "tone", "voice", "audience",
              "products", "approved_terms", "forbidden_terms",
              "claims_rules", "colors", "logo", "reference_content"):
        v = brand.get(k)
        if isinstance(v, (list, tuple)):
            v = ", ".join(_s(x) for x in v)
        out.append("<div class='cf-row'><span class='cf-meta'>"
                   + e(k.replace("_", " ").title()) + "</span><b>"
                   + e(v or "not set") + "</b></div>")
    out.append("</div>")
    if not brand:
        out.append("<p class='cf-note cf-wa'>No brand profile is "
                   "configured, so QA cannot check tone or forbidden "
                   "terms and says so on every review rather than "
                   "passing silently.</p>")

    out.append("<p class='cf-h2'>Tools</p>"
               "<p class='cf-note'>Agents see a capability, never a key. "
               "The value of a credential is never read or displayed "
               "here; only whether one is configured.</p>"
               "<div class='cf-scroll'><table class='cf-tbl'><thead><tr>"
               "<th>Capability</th><th>MVP</th><th>State</th>"
               "<th>Detail</th></tr></thead><tbody>")
    for row in FOS.tool_matrix():
        st = _s(row.get("state"))
        out.append("<tr><td>" + e(row.get("capability")) + "</td>"
                   + "<td>" + ("yes" if row.get("mvp") else "later")
                   + "</td><td>" + _pill(st, "ok" if row.get("available")
                                         else "wa") + "</td>"
                   + "<td class='cf-meta'>" + e(row.get("why"))
                   + "</td></tr>")
    out.append("</tbody></table></div>")

    out.append("<p class='cf-h2'>Workflow</p><div class='cf-card'>")
    gates = (("Human approval required", wf.get("require_approval", True)),
             ("Default reviewer", wf.get("default_reviewer")),
             ("Paid content approval", wf.get("paid_approval", True)),
             ("SEO content approval", wf.get("seo_approval", True)),
             ("Social approval", wf.get("social_approval", True)),
             ("Auto-schedule allowed", wf.get("auto_schedule", False)),
             ("Max AI cost per content",
              wf.get("max_cost_usd", FA.BUDGET["max_cost_usd"])))
    for label, val in gates:
        out.append("<div class='cf-row'><span>" + e(label) + "</span><b>"
                   + e("yes" if val is True else "no" if val is False
                       else (val if val not in (None, "") else "not set"))
                   + "</b></div>")
    out.append("</div>")
    out.append("<p class='cf-note'>Approval cannot be switched off for "
               "the MVP. Section 54: AI is never the final approver by "
               "default, and a setting that removes the last human from "
               "the chain is not a preference.</p>")

    out.append("<p class='cf-h2'>Permissions</p>"
               "<div class='cf-scroll'><table class='cf-tbl'><thead><tr>"
               "<th>Role</th>"
               + "".join("<th>" + e(p.replace("_", " ").title()) + "</th>"
                         for p in FOS.PERMISSIONS)
               + "</tr></thead><tbody>")
    for role in FOS.ROLES:
        out.append("<tr><td>" + e(role) + "</td>"
                   + "".join("<td>" + ("✓" if FOS.can(role, p)
                                       else "·") + "</td>"
                             for p in FOS.PERMISSIONS) + "</tr>")
    out.append("</tbody></table></div>")

    out.append("<p class='cf-h2'>Connections</p><div class='cf-card'>")
    for label, owner in FOS.DOES_NOT_BUILD:
        out.append("<div class='cf-row'><span class='cf-meta'>"
                   + e(label) + "</span><b>" + e(owner) + "</b></div>")
    out.append("</div><p class='cf-note'>These are deliberately not built "
               "here. The factory reads their signals and hands work "
               "back; it does not reimplement them.</p>")
    return "".join(out)
