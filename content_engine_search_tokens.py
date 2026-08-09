"""
content_engine_search_tokens.py
============================================================================
THE SEARCH OS DESIGN SYSTEM. Spec sections 8-11, 51, 66-71, 87-92.

WHY THIS FILE EXISTS AT ALL
  The spec's instruction is blunt: "Never duplicate raw visual values
  throughout components." Every previous screen in this engine picked its
  own hex codes, which is why the media section and the SEO section do
  not look like one product. Nothing below is a suggestion; css() emits
  these as custom properties and a gate fails the build if a component
  hard-codes a colour that lives here.

THE COLOUR CONTRACT (spec 9), which is about MEANING, not taste:
  BLUE   a user action        Run Audit, Publish, Save
  PURPLE an AI action         Analyze, Generate Fix, Optimize
  GREEN  VERIFIED success     Indexed, Verified, Improved
  AMBER  attention/waiting    Observing, Warning
  RED    critical/failure     Broken, Execution Failed, Regression
  GRAY   neutral data
  The rule that matters: green is never given to something merely
  executed. EXECUTED is amber until it is verified, because the whole
  product exists to stop "we changed it" reading as "it worked".

STATUS IS NEVER COLOUR ALONE (spec 69). status() returns a dot AND a
word, so the screen is readable to someone who cannot distinguish the
dot, and honest to someone reading a screenshot in greyscale.
============================================================================
"""

from __future__ import annotations

#: §8 BASE. Neutral workstation, not a marketing page.
BASE = {
    "bg": "#F7F8FA", "surface": "#FFFFFF", "raised": "#FFFFFF",
    "border": "#E5E7EB", "text": "#111827", "text2": "#4B5563",
    "muted": "#9CA3AF",
}

#: The same palette for the dark shell this engine's dashboard already
#: uses. Declared HERE rather than improvised per screen.
BASE_DARK = {
    "bg": "#0A0F1E", "surface": "#0E1526", "raised": "#131C33",
    "border": "#1B2640", "text": "#E8EEFF", "text2": "#8FA0C8",
    "muted": "#5A6A8F",
}

#: §8 semantic roles. Each carries its soft background.
ROLES = {
    "primary": {"main": "#2563EB", "hover": "#1D4ED8",
                "active": "#1E40AF", "soft": "#EFF6FF"},
    "ai":      {"main": "#7C3AED", "hover": "#6D28D9",
                "active": "#5B21B6", "soft": "#F5F3FF"},
    "success": {"main": "#16A34A", "hover": "#15803D",
                "active": "#166534", "soft": "#F0FDF4"},
    "warning": {"main": "#D97706", "hover": "#B45309",
                "active": "#92400E", "soft": "#FFFBEB"},
    "danger":  {"main": "#DC2626", "hover": "#B91C1C",
                "active": "#991B1B", "soft": "#FEF2F2"},
    "info":    {"main": "#0284C7", "hover": "#0369A1",
                "active": "#075985", "soft": "#F0F9FF"},
    "neutral": {"main": "#4B5563", "hover": "#374151",
                "active": "#1F2937", "soft": "#F9FAFB"},
}

#: §9 MEANING. What each role is allowed to say. A gate reads this table,
#: so a screen cannot quietly paint an unverified thing green.
MEANING = {
    "primary": "a user action",
    "ai": "an AI action",
    "success": "a VERIFIED success, never a merely executed change",
    "warning": "attention, or waiting for a measurement",
    "danger": "critical, failed or regressed",
    "info": "informational",
    "neutral": "data with no verdict attached",
}

#: §10 CTA hierarchy. variant -> role.
CTA = {"primary": "primary", "secondary": "neutral", "ai": "ai",
       "danger": "danger", "ghost": "neutral"}

#: §11 sizes.
BUTTON_H = {"compact": 32, "standard": 40, "important": 44}
BUTTON_STATES = ("default", "hover", "active", "focus", "disabled",
                 "loading", "success", "failure")

#: §88 typography, §89 8px spacing grid, §90 radius.
TYPE = {"page_title": (24, 600), "section": (16, 600), "body": (14, 400),
        "table": (13, 400), "meta": (12, 400), "kpi": (26, 600)}
SPACE = (4, 8, 12, 16, 20, 24, 32, 40, 48)
RADIUS = {"input": 8, "button": 8, "card": 10, "modal": 12}

#: §91 shadow only for floating things; borders everywhere else.
SHADOW_ALLOWED = ("dropdown", "drawer", "modal", "floating")

#: §69 status: a dot AND a word, always.
STATUS = {
    "healthy": ("success", "Healthy"),
    "verified": ("success", "Verified"),
    "improved": ("success", "Improved"),
    "warning": ("warning", "Warning"),
    "observing": ("warning", "Observing"),
    "running": ("info", "Running"),
    "executed": ("warning", "Executed, not yet verified"),
    "critical": ("danger", "Critical"),
    "failed": ("danger", "Failed"),
    "regression": ("danger", "Regression"),
    "neutral": ("neutral", "No verdict"),
    "missing": ("neutral", "Not measured"),
}

#: §51 chart series. Purple is reserved for AI forecasts so a projection
#: can never be mistaken for a measurement.
CHART = {"primary": "#2563EB", "comparison": "#9CA3AF",
         "positive": "#16A34A", "warning": "#D97706",
         "critical": "#DC2626", "ai_forecast": "#7C3AED"}


def token(name) -> str:
    """One CSS custom property name. Components call THIS, never a hex."""
    return f"var(--so-{name})"


def status(key) -> str:
    """§69. Dot plus word; never colour alone."""
    role, word = STATUS.get(key, STATUS["neutral"])
    return (f"<span class='so-status so-{role}'>"
            f"<span class='so-dot' aria-hidden='true'>&#9679;</span>"
            f"{word}</span>")


def button(label, *, variant="primary", size="standard", state="default",
           onclick="") -> str:
    """§10-11. A button may only be a declared variant, size and state."""
    if variant not in CTA:
        raise ValueError(f"{variant!r} is not a CTA variant. They are: "
                         + ", ".join(CTA))
    if size not in BUTTON_H:
        raise ValueError(f"{size!r} is not a button size")
    if state not in BUTTON_STATES:
        raise ValueError(f"{state!r} is not a button state")
    dis = " disabled" if state in ("disabled", "loading") else ""
    return (f"<button class='so-btn so-btn-{variant} so-btn-{size} "
            f"so-btn-{state}'"
            + (f" onclick=\"{onclick}\"" if onclick else "") + dis + ">"
            + ("&#9676; " if state == "loading" else
               "&#10003; " if state == "success" else
               "&#10005; " if state == "failure" else "")
            + label + "</button>")


def css(dark=True) -> str:
    """Emit every token once. This is the ONLY place a hex is written."""
    base = BASE_DARK if dark else BASE
    lines = [f"--so-{k}:{v}" for k, v in base.items()]
    for role, shades in ROLES.items():
        for shade, hexv in shades.items():
            lines.append(f"--so-{role}-{shade}:{hexv}")
    for k, v in CHART.items():
        lines.append(f"--so-chart-{k}:{v}")
    for k, v in RADIUS.items():
        lines.append(f"--so-radius-{k}:{v}px")
    root = ":root{" + ";".join(lines) + "}"
    btns = "".join(
        f".so-btn-{v}{{background:var(--so-{r}-main);color:#fff;"
        f"border:1px solid var(--so-{r}-main)}}"
        f".so-btn-{v}:hover{{background:var(--so-{r}-hover)}}"
        for v, r in CTA.items() if v not in ("secondary", "ghost"))
    return ("<style>" + root + """
.so-btn{border-radius:var(--so-radius-button);font-size:13px;
padding:0 14px;cursor:pointer;font-family:inherit;line-height:1}
.so-btn-compact{height:32px}.so-btn-standard{height:40px}
.so-btn-important{height:44px;font-weight:600}
.so-btn-secondary,.so-btn-ghost{background:transparent;
color:var(--so-text);border:1px solid var(--so-border)}
.so-btn-ghost{border-color:transparent}
.so-btn-disabled,.so-btn-loading{opacity:.55;cursor:not-allowed}
.so-status{display:inline-flex;align-items:center;gap:5px;font-size:12px}
.so-dot{font-size:9px}
.so-success .so-dot,.so-success{color:var(--so-success-main)}
.so-warning .so-dot,.so-warning{color:var(--so-warning-main)}
.so-danger .so-dot,.so-danger{color:var(--so-danger-main)}
.so-info .so-dot,.so-info{color:var(--so-info-main)}
.so-neutral .so-dot,.so-neutral{color:var(--so-muted)}
""" + btns + "</style>")


#: §96. Every screen must have a contract before it is implemented. The
#: fields are the spec's, verbatim, so a contract cannot be half written.
CONTRACT_FIELDS = ("purpose", "user_questions", "user_decisions", "data",
                   "data_source", "metrics", "filters", "components",
                   "charts", "tables", "cta", "ai_actions", "empty_state",
                   "loading_state", "error_state", "permission_state",
                   "drilldown", "loop_connection")

#: The screens the spec's navigation names. A screen missing from here
#: cannot be built, and a contract missing for one of these is the
#: build-order violation §95 warns about.
SCREENS = (
    "command_center", "domain_overview", "organic_research",
    "keyword_explorer", "keyword_gap", "competitors", "serp_explorer",
    "position_tracking", "ranking_changes", "site_audit_overview",
    "issues", "crawled_pages", "page_intelligence", "content_inventory",
    "content_gap", "content_decay", "content_brief", "content_editor",
    "internal_links", "backlinks_overview", "backlink_gap",
    "aeo_questions", "aeo_answer_detail", "geo_ai_visibility",
    "geo_prompt_tracker", "citation_gap", "search_analytics",
    "search_funnel", "opportunities", "agent_center", "execution_board",
    "loop_monitor", "reports",
)


def check_contract(doc) -> dict:
    """A contract is complete or it is refused, with the gaps named."""
    d = doc if isinstance(doc, dict) else {}
    missing = [f for f in CONTRACT_FIELDS if not str(d.get(f) or "").strip()]
    if missing:
        return {"ok": False, "code": "CONTRACT_INCOMPLETE",
                "missing": missing,
                "message": (f"a screen contract needs every field before "
                            f"the screen is built. Missing: "
                            + ", ".join(missing))}
    return {"ok": True, "message": "contract complete"}


def contract_status(docs_dir="docs/search/ui") -> dict:
    """Which screens may legally be built yet (spec 95/96)."""
    import os
    have = set()
    if os.path.isdir(docs_dir):
        have = {f[:-3] for f in os.listdir(docs_dir) if f.endswith(".md")}
    missing = [s for s in SCREENS if s not in have]
    return {"total": len(SCREENS), "written": len(have),
            "missing": missing,
            "message": (f"{len(have)} of {len(SCREENS)} screen contracts "
                        f"written. The remaining {len(missing)} screens "
                        f"may not be implemented yet: the spec puts the "
                        f"contract before the page, and skipping it is "
                        f"how a screen becomes a generic dashboard.")}
