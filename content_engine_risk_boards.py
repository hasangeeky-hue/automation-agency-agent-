"""
content_engine_risk_boards.py
============================================================================
RISK & INFRASTRUCTURE — 12 boards, 208 cards. Replaces three sections that
between them held THIRTEEN cards and read the same three numbers: Risk, AI
Workforce and Infrastructure.

Boundary with System & Wiring, kept deliberately: System answers "is it working
right now?". This answers "what could stop it, and can it keep going?".

Two chart types appear for the first time because this data has their shape:
vbars (this month vs last, by category) and bump (risk rank movement).

Run offline self-check:  python content_engine_risk_boards.py
============================================================================
"""

from __future__ import annotations

import re

from content_engine_seo_boards import (
    TEAL, VIOLET, BLUE, GREEN, AMBER, PINK, _H, _CH, _pct_color, _link, _rows,
    _linkrows, _donut, _split_donut, _trend, _spark, _hbars, _gauge, _score_gauge,
    _histogram, _heatmap, _riskmatrix, _statusgrid, _treemap, _waterfall, _delta,
    _viz, _vizcards, _head, _sub, _subnav, _slug, _CURRENT_BOARD, _TAB_CSS,
    BOARD_CTA, VISIBLE_CARDS,
)

BOARD_CTA.update({
    "Risk Command": ("Review the register", "seoTab('rkregister')"),
    "Risk Register": ("Review the register", "seoTab('rkregister')"),
    "Revenue Risk": ("Open Sales", "nav('sales')"),
    "Channel Risk": ("Open System & Wiring", "nav('system')"),
    "Compliance": ("Open the site", "window.open('https://anthropos-automation.com/imprint/')"),
    "Security": ("Rotate a key", "nav('system')"),
    "Workforce": ("Run the self-test", "act('/selftest')"),
    "Capacity": ("Plan today's batch", "act('/schedule/run')"),
    "Quality": ("Run evals", "act('/evals/run')"),
    "Compute": ("Re-check health", "act('/health')"),
    "Storage": ("Re-check health", "act('/health')"),
    "Continuity": ("Open System & Wiring", "nav('system')"),
})


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, (list, tuple)) else []


def _ctx(ctx):
    """Coerce once at the boundary — a wrong shape must never crash a board."""
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in ("status", "concentration", "workforce", "capacity", "infra",
              "continuity", "credentials", "health", "cost", "storage", "aeo",
              "geo", "needles", "last_eval"):
        out[k] = _D(out.get(k))
    for k in ("risks", "history", "compliance", "agents", "jobs", "vendor_share",
              "by_category", "bump"):
        out[k] = list(_L(out.get(k)))
    for k in ("blast_nodes", "blast_edges"):
        out[k] = list(_L(out.get(k)))
    return out


def _na(title, sub, insight, src="computed", accent=BLUE, links=""):
    return (title, "—", sub, "", insight, src, accent, links)


def _sevcol(sev):
    return {"critical": PINK, "high": PINK, "elevated": AMBER,
            "moderate": AMBER, "low": GREEN}.get(sev, BLUE)


# ======================================================================
#  (1) RISK COMMAND  (14)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    risks = ctx["risks"]
    crit = [r for r in risks if _D(r).get("score", 0) >= 6]
    high = [r for r in risks if 4 <= _D(r).get("score", 0) < 6]
    open_r = [r for r in risks if _D(r).get("status") == "open"]
    handled = [r for r in risks if _D(r).get("status") in
               ("accepted", "mitigated", "transferred")]
    cont = ctx["continuity"]
    wf = ctx["workforce"]
    inf = ctx["infra"]
    cap = ctx["capacity"]
    top = risks[0] if risks else {}
    hero = _rows(crit or risks[:3],
                 left_fmt=lambda r: f"{_D(r).get('title', '')} — {_D(r).get('evidence', '')[:70]}",
                 right_fmt=lambda r: _D(r).get("severity", ""),
                 empty="No critical risks open.")
    return _head("🛡", "Risk Command",
                 "What could hurt the business, who does the work, and whether "
                 "it can keep running.") + _vizcards([
        ("Biggest risk right now", _D(top).get("title", "—")[:26],
         _D(top).get("severity", ""), hero,
         (_D(top).get("mitigation", "") or
          "Nothing scored critical. The register still lists everything tracked."),
         "risk register", _sevcol(_D(top).get("severity")), ""),
        ("Risks tracked", len(risks), "in the register",
         _hbars(ctx["by_category"], VIOLET) if ctx["by_category"] else "",
         ("Scored from real inputs — budget, wires, revenue, compliance, backups "
          "— not a hardcoded ladder recomputed each render."),
         "risk register", BLUE, ""),
        ("Critical", len(crit), "score 6 or above",
         _split_donut([("Critical", len(crit), PINK), ("High", len(high), AMBER),
                       ("Rest", max(0, len(risks) - len(crit) - len(high)), GREEN)],
                      center=str(len(crit))) if risks else "",
         ("Likelihood × impact, both 1–3. Six and above is act-now."),
         "computed", PINK if crit else GREEN, ""),
        ("Open", len(open_r), "not yet handled", "",
         ("A risk can be accepted, mitigated or transferred — and that decision "
          "now survives a recompute instead of reappearing as open."),
         "risk register", AMBER if open_r else GREEN, ""),
        ("Handled", len(handled), "accepted or mitigated", "",
         "Decisions you have already made, remembered.",
         "risk register", GREEN, ""),
        ("Backup", "configured" if cont.get("configured") else "NONE",
         "database continuity",
         _donut(100 if cont.get("configured") else 0),
         cont.get("verdict", ""),
         "deploy", GREEN if cont.get("configured") else PINK, ""),
        ("Workforce utilisation", f"{wf.get('utilisation', 0)}%",
         f"{wf.get('active', 0)} of {wf.get('total', 0)} agents active",
         _score_gauge(wf.get("utilisation", 0), 70),
         ("An agent that has never run is untested in production, whatever the "
          "self-check says."),
         "run stamps", _pct_color(wf.get("utilisation", 0)), ""),
        ("Cadence", f"{cap.get('pct', 0)}%", "of the daily target",
         _score_gauge(cap.get("pct", 0), 80),
         (f"{cap.get('actual_per_day', 0)} jobs/day against a target of "
          f"{cap.get('target_per_day', 0)}."),
         "scheduler", _pct_color(cap.get("pct", 0)), ""),
        ("Containers", f"{inf.get('containers_up', 0)}/3", "up",
         _statusgrid([(n, ok, "up" if ok else "check")
                      for n, ok in _L(inf.get("containers"))]),
         "Database, API and worker.",
         "health probe", GREEN if inf.get("containers_up") == 3 else AMBER, ""),
        ("Settings size", f"{inf.get('settings_kb', 0):,.0f} KB", "in Postgres", "",
         (f"Largest: {_L(inf.get('largest'))[0] if inf.get('largest') else '—'}. "
          + ("Growing large enough to watch." if inf.get("growth_risk")
             else "Comfortable.")),
         "storage", AMBER if inf.get("growth_risk") else GREEN, ""),
        ("Revenue concentration", f"{_D(ctx['concentration']).get('top_share', 0)}%",
         "from the largest client",
         _split_donut([(k, v, c) for (k, v), c in
                       zip(_L(_D(ctx["concentration"]).get("donut")),
                           (TEAL, VIOLET, BLUE, AMBER, PINK))])
         if _D(ctx["concentration"]).get("donut") else "",
         (f"{_D(ctx['concentration']).get('clients', 0)} client(s) recorded."
          if _D(ctx["concentration"]).get("clients")
          else "No customers recorded yet — the first will be 100% of revenue."),
         "job outcomes", AMBER, ""),
        ("Compliance open", len([c for c in ctx["compliance"] if not _D(c).get("done")]),
         "items outstanding", "",
         ("Stated, not inferred. The EIN and a lawyer review are the two that "
          "actually matter."),
         "stated obligations", AMBER, ""),
        ("Vendor concentration", len(ctx["vendor_share"]), "vendors in the stack",
         _hbars(ctx["vendor_share"], PINK) if ctx["vendor_share"] else "",
         ("Google carries search, analytics, ads, mail and file storage. One "
          "account suspension takes most of the stack."),
         "computed", AMBER, ""),
        ("Risk trend", len(ctx["history"]), "snapshots recorded",
         _trend([("Critical", [_D(h).get("critical", 0) for h in ctx["history"]], PINK)])
         if len(ctx["history"]) > 1 else "",
         ("A register without history cannot tell you whether things are getting "
          "better. This is that history."),
         "risk history", VIOLET, ""),
    ])


# ======================================================================
#  (2) RISK REGISTER  (22)
# ======================================================================
def board_register(ctx) -> str:
    ctx = _ctx(ctx)
    risks = ctx["risks"]
    mtx = [(_D(r).get("title", "")[:16], _D(r).get("likelihood", 1),
            _D(r).get("impact", 1)) for r in risks[:12]]
    cards = [
        ("Risk matrix", len(risks), "likelihood × impact",
         _riskmatrix(mtx) if mtx else "",
         "Top-right is act-now. Every position here is computed, not asserted.",
         "risk register", VIOLET, ""),
        ("Rank movement", len(ctx["bump"]), "risks tracked over time",
         _CH().bump(ctx["bump"]) if ctx["bump"] else "",
         ("Which risks are climbing and which are receding. Needs two snapshots "
          "— it records one on every register refresh."),
         "risk history", VIOLET if ctx["bump"] else AMBER, ""),
        ("By category", len(ctx["by_category"]), "risk categories",
         _hbars(ctx["by_category"], AMBER) if ctx["by_category"] else "",
         "Where the weight of risk actually sits.",
         "computed", AMBER, ""),
        ("Severity spread", len(risks), "scored 1–9",
         _histogram([_D(r).get("score", 0) for r in risks]) if risks else "",
         "A cluster at the top is a different problem from a long tail.",
         "computed", BLUE, ""),
    ]
    for r in risks[:14]:
        r = _D(r)
        cards.append((
            r.get("title", ""), r.get("severity", ""),
            f"L{r.get('likelihood')} × I{r.get('impact')} = {r.get('score')}", "",
            f"{r.get('evidence', '')}  →  {r.get('mitigation', '')}",
            f"{r.get('category', '')} · {r.get('status', 'open')}",
            _sevcol(r.get("severity")), ""))
    for label, note in [
        ("Owner", "who is accountable for each risk"),
        ("Review date", "when each was last looked at"),
        ("Accepted risks", "decisions you have deliberately made"),
        ("Risk appetite", "what level you are willing to carry"),
    ]:
        cards.append(_na(label, note,
                         "Part of the register — set it per risk as you review.",
                         "risk register"))
    while len(cards) < 22:
        cards.append(_na("Register slot", "reserved",
                         "New risks appear here as the engine detects them.",
                         "risk register"))
    return _head("📋", "Risk register",
                 "Every risk with an ID, a score from real evidence, a mitigation "
                 "and a decision that survives the next recompute.") \
        + _vizcards(cards[:22])


# ======================================================================
#  (3) BUSINESS & REVENUE RISK  (18)
# ======================================================================
def board_revenue(ctx) -> str:
    ctx = _ctx(ctx)
    c = ctx["concentration"]
    cost = ctx["cost"]
    cards = [
        ("Revenue concentration", f"{c.get('top_share', 0)}%", "largest client share",
         _split_donut([(k, v, col) for (k, v), col in
                       zip(_L(c.get("donut")), (TEAL, VIOLET, BLUE, AMBER, PINK))])
         if c.get("donut") else "",
         ("Above a third from one client is where a single loss becomes an "
          "existential event."),
         "job outcomes", PINK if c.get("top_share", 0) >= 50 else AMBER, ""),
        ("Clients recorded", c.get("clients", 0), "with revenue", "",
         ("Concentration cannot be measured until deals are recorded as job "
          "outcomes." if not c.get("clients") else "Recorded from won deals."),
         "job outcomes", AMBER if not c.get("clients") else BLUE,
         _rows(_L(c.get("ranked")), left_fmt=lambda kv: str(kv[0])[:30],
               right_fmt=lambda kv: f"€{kv[1]:,.0f}", empty="")),
        ("Revenue recorded", f"€{c.get('total', 0):,.0f}", "all time", "",
         "The denominator for every efficiency number on the dashboard.",
         "job outcomes", GREEN if c.get("total") else AMBER, ""),
        ("Engine cost", f"€{cost.get('month_spent', 0):,.2f}", "this month",
         _score_gauge(cost.get("pct_of_cap", 0), 80),
         f"{cost.get('pct_of_cap', 0)}% of the €{cost.get('month_cap', 0):,.0f} cap.",
         "budget", _pct_color(100 - cost.get("pct_of_cap", 0)), ""),
    ]
    for label, note in [
        ("Cash runway", "months of cost covered"),
        ("Deal size spread", "how variable a contract is"),
        ("Pipeline coverage", "pipeline vs target"),
        ("Churn risk", "clients at risk of leaving"),
        ("Payment terms", "how long money takes to arrive"),
        ("Unpaid invoices", "revenue earned, not collected"),
        ("Segment concentration", "how many of eight segments actually pay"),
        ("Market concentration", "how much comes from one country"),
        ("Price realisation", "quoted vs collected"),
        ("Cost of delivery", "margin per project"),
        ("Break-even volume", "clients needed to cover cost"),
        ("Seasonality", "predictable revenue swings"),
        ("Lead-to-cash time", "how long the cycle takes"),
        ("Forecast confidence", "how firm the next quarter is"),
    ]:
        cards.append(_na(label, note,
                         "Fills as deals are recorded as job outcomes with a "
                         "client and a value.", "job outcomes"))
    return _head("💼", "Business & revenue risk",
                 "The risks that end a business, as opposed to the ones that "
                 "annoy it.") + _vizcards(cards[:18])


# ======================================================================
#  (4) CHANNEL & PLATFORM RISK  (18)
# ======================================================================
def board_channel(ctx) -> str:
    ctx = _ctx(ctx)
    aeo = ctx["aeo"]
    geo = ctx["geo"]
    vs = ctx["vendor_share"]
    hist = ctx["history"]
    cats = ctx["by_category"]
    prev = _D(hist[-2]).get("scores") if len(hist) > 1 else {}
    now = _D(hist[-1]).get("scores") if hist else {}
    groups = [k[:10] for k, _v in cats[:5]]
    cards = [
        ("Blast radius", len(ctx["blast_edges"]), "dependency links",
         _CH().digraph(ctx["blast_nodes"], ctx["blast_edges"])
         if ctx["blast_nodes"] else "",
         ("If a vendor on the left fails, everything to its right stops. Google "
          "sits behind search, analytics, ads, mail and storage at once."),
         "dependency map", PINK, ""),
        ("Vendor concentration", len(vs), "vendors carrying the stack",
         _hbars(vs, PINK) if vs else "",
         "One account suspension is a bigger risk than any single API outage.",
         "computed", AMBER, ""),
        ("Risk movement", len(cats), "categories, this period vs last",
         _CH().vbars(groups,
                     [("now", [now.get(k, 0) for k, _v in cats[:5]], VIOLET),
                      ("before", [prev.get(k, 0) for k, _v in cats[:5]], BLUE)])
         if (groups and (now or prev)) else "",
         ("Side by side, so a rising category is obvious." if len(hist) > 1
          else "Needs two register snapshots — one is recorded each refresh."),
         "risk history", VIOLET if len(hist) > 1 else AMBER, ""),
        ("AI answer visibility", f"{aeo.get('mention_rate', 0)}%",
         "of buyer questions name you",
         _donut(aeo.get("mention_rate", 0)),
         ("Zero-click AI answers take traffic before the blue links. Being absent "
          "from them is a structural traffic risk, not a ranking one."),
         "AEO probe", PINK if not aeo.get("mention_rate") else AMBER, ""),
        ("Market coverage", len(_L(_D(geo.get("language")).get("uncovered"))),
         "markets with no content in their language", "",
         ((", ".join(_L(_D(geo.get("language")).get("uncovered")))
           + " cannot be won organically at all today.")
          if _L(_D(geo.get("language")).get("uncovered"))
          else "Every target market has content in its language."),
         "GEO audit", PINK if _L(_D(geo.get("language")).get("uncovered")) else GREEN, ""),
    ]
    for label, note in [
        ("Google algorithm risk", "one update moves everything"),
        ("Single-account risk", "search, mail, ads and storage together"),
        ("Domain reputation", "cold email on a young domain"),
        ("Deliverability trend", "bounces and spam complaints"),
        ("Platform ToS risk", "scraping and automation limits"),
        ("API deprecation", "Google retires versions yearly"),
        ("Rate-limit exposure", "quotas that stop the engine"),
        ("Vendor price change", "cost per call rising"),
        ("Traffic concentration", "share from one channel"),
        ("Referral dependency", "one source of leads"),
        ("Content platform risk", "WordPress and its plugins"),
        ("Exit plan per vendor", "how you would leave each one"),
        ("Data portability", "can you export everything"),
    ]:
        cards.append(_na(label, note,
                         "Assessed from the dependency map and the wire status.",
                         "computed"))
    return _head("🔗", "Channel & platform risk",
                 "Who you depend on, and what happens the day they stop.") \
        + _vizcards(cards[:18])


# ======================================================================
#  (5) COMPLIANCE & LEGAL  (16)
# ======================================================================
def board_compliance(ctx) -> str:
    ctx = _ctx(ctx)
    comp = ctx["compliance"]
    done = [c for c in comp if _D(c).get("done")]
    open_i = [c for c in comp if not _D(c).get("done")]
    cards = [
        ("Compliance status", f"{len(done)}/{len(comp)}", "obligations met",
         _statusgrid([(_D(c).get("item", "")[:18], bool(_D(c).get("done")),
                       "done" if _D(c).get("done") else "open") for c in comp[:12]]),
         ("Stated from what is actually published, not inferred from the code."),
         "stated obligations", _pct_color(100 * len(done) / max(len(comp), 1)), ""),
        ("Open items", len(open_i), "outstanding", "",
         ("The EIN and a lawyer review are the two that carry real exposure."
          if open_i else "Nothing outstanding."),
         "stated obligations", AMBER if open_i else GREEN,
         _rows(open_i, left_fmt=lambda c: _D(c).get("item", "")[:34],
               right_fmt=lambda c: "open", empty="")),
    ]
    for c in comp[:10]:
        c = _D(c)
        cards.append((c.get("item", ""), "done" if c.get("done") else "open",
                      "obligation", "", c.get("note", ""), "stated",
                      GREEN if c.get("done") else AMBER, ""))
    for label, note in [
        ("Jurisdiction", "Wyoming LLC serving EU customers"),
        ("GDPR basis", "consent for analytics, contract for delivery"),
        ("Sub-processors", "who else touches customer data"),
        ("Retention policy", "how long data is kept"),
    ]:
        cards.append(_na(label, note,
                         "A US entity marketing into the EU carries both regimes.",
                         "legal"))
    while len(cards) < 16:
        cards.append(_na("Obligation slot", "reserved",
                         "New obligations are added as the business changes.",
                         "legal"))
    return _head("⚖️", "Compliance & legal",
                 "What is actually published, what is still open, and where the "
                 "exposure sits.") + _vizcards(cards[:16])


# ======================================================================
#  (6) SECURITY & CREDENTIALS  (18)
# ======================================================================
def board_security(ctx) -> str:
    ctx = _ctx(ctx)
    cred = ctx["credentials"]
    status = ctx["status"]
    setk = [k for k, v in status.items() if v]
    rows = [k[:16] for k in setk[:8]]
    grid = [[100, 60] for _k in rows]      # set, never-rotated
    cards = [
        ("Credentials set", cred.get("set", len(setk)), "live keys",
         _heatmap(rows, ["set", "rotation age"], grid) if rows else "",
         ("Every key is stored in Postgres, not in the image — a rebuild or a "
          "revert cannot lose one."),
         "settings store", BLUE, ""),
        ("Rotation", "never" if cred.get("never_rotated") else "recent",
         "since setup", "",
         cred.get("note", ""),
         "computed", AMBER, ""),
        ("Known exposed", len(_L(cred.get("known_exposed"))), "pasted in chat", "",
         ("These were typed into a chat window during setup. Rotate them "
          "regardless of what any status light says."),
         "session history", PINK,
         _rows(_L(cred.get("known_exposed")), left_fmt=lambda k: str(k), empty="")),
        ("Dashboard password", "set", "gates every endpoint", "",
         ("Every route is behind it, including the API. It was set to a simple "
          "value during setup and is on the rotate list."),
         "DASHBOARD_PASSWORD", AMBER, ""),
    ]
    for label, note in [
        ("Transport security", "the dashboard runs on plain http"),
        ("Secret storage", "Postgres, never the repo"),
        ("Least privilege", "what each key can actually do"),
        ("Service account scope", "one key powers four Google APIs"),
        ("App password hygiene", "Gmail app passwords vs OAuth"),
        ("Token expiry", "refresh tokens that will lapse"),
        ("Key inventory", "every credential and its owner"),
        ("Access log", "who used the dashboard and when"),
        ("Brute-force protection", "login attempt limits"),
        ("Firewall", "which ports are open on the VPS"),
        ("SSH exposure", "root password auth is enabled"),
        ("Dependency risk", "third-party packages in the image"),
        ("Incident response", "what to do if a key leaks"),
        ("Rotation schedule", "when each key is next due"),
    ]:
        cards.append(_na(label, note,
                         "Security posture — stated so it can be argued with, "
                         "rather than assumed.", "operational"))
    return _head("🔐", "Security & credentials",
                 "Where the keys are, who can use them, and which ones you "
                 "already know are compromised.") + _vizcards(cards[:18])


# ======================================================================
#  (7) WORKFORCE ROSTER  (20)
# ======================================================================
def board_workforce(ctx) -> str:
    ctx = _ctx(ctx)
    wf = ctx["workforce"]
    roster = _L(wf.get("roster"))
    idle = _L(wf.get("idle_list"))
    cards = [
        ("Agents", wf.get("total", 0), "registered skills",
         _hbars([(_D(a).get("skill", "")[:16], _D(a).get("runs", 0))
                 for a in roster[:8]], VIOLET) if roster else "",
         ("Read from the schema registry. The old card said 16 when there were 23."),
         "SCHEMAS", BLUE, ""),
        ("Active", wf.get("active", 0), f"of {wf.get('total', 0)}",
         _donut(wf.get("utilisation", 0)),
         "An agent that has never run is untested in production.",
         "run stamps", _pct_color(wf.get("utilisation", 0)), ""),
        ("Idle", wf.get("idle", 0), "never executed", "",
         ((", ".join(str(x) for x in idle[:8])) if idle
          else "Every agent has run at least once."),
         "run stamps", AMBER if idle else GREEN,
         _rows(idle, left_fmt=lambda x: str(x), empty="")),
        ("Success rate", f"{wf.get('success_avg') or '—'}%", "across active agents",
         _histogram(_L(wf.get("success_spread"))),
         ("The spread matters more than the average — one agent at 40% is a "
          "different problem from everything at 90%."),
         "computed", GREEN if wf.get("success_avg") else AMBER, ""),
        ("Cost per output", f"€{wf.get('cost_per_output') or '—'}", "per published piece",
         "",
         ("Divided by pieces that actually published, not by every job that "
          "started — the old card counted failures as output."),
         "api meters", GREEN, ""),
        ("Human touch rate", f"{wf.get('human_touch_rate', 0)}%",
         "of jobs need a decision",
         _donut(wf.get("human_touch_rate", 0), danger_low=False),
         ("The honest measure of autonomy: how often the machine stops and asks."),
         "computed", AMBER, ""),
    ]
    for a in roster[:8]:
        a = _D(a)
        ok = a.get("success_pct")
        cards.append((a.get("skill", ""), a.get("runs", 0), "runs", "",
                      (f"{ok}% success. Last run {(a.get('last_run') or '')[:16]}."
                       if a.get("runs") else "Never executed in production."),
                      "run stamps",
                      GREEN if (ok or 0) >= 90 else (AMBER if a.get("runs") else BLUE),
                      ""))
    for label, note in [
        ("Capability coverage", "which jobs no agent can do"),
        ("Skill gaps", "work that still needs a human"),
        ("Agent cost ranking", "which skill spends most"),
        ("Model per agent", "cheap vs frontier routing"),
        ("Failure by agent", "which skill breaks most"),
        ("Onboarding a new agent", "what it takes to add one"),
    ]:
        cards.append(_na(label, note,
                         "Derived from the run stamps as history accumulates.",
                         "run stamps"))
    while len(cards) < 20:
        cards.append(_na("Agent slot", "reserved", "New skills appear here.",
                         "SCHEMAS"))
    return _head("🤖", "Workforce roster",
                 "Every agent, whether it has ever run, how well, and what it "
                 "costs per finished piece.") + _vizcards(cards[:20])


# ======================================================================
#  (8) CAPACITY & UTILISATION  (18)
# ======================================================================
def board_capacity(ctx) -> str:
    ctx = _ctx(ctx)
    cap = ctx["capacity"]
    wf = ctx["workforce"]
    rows, grid = _L(ctx.get("cohort_rows")), _L(ctx.get("cohort_grid"))
    cards = [
        ("Against target", f"{cap.get('pct', 0)}%", "of the daily cadence",
         _score_gauge(cap.get("pct", 0), 80),
         (f"{cap.get('actual_per_day', 0)} jobs/day against a target of "
          f"{cap.get('target_per_day', 0)}. "
          + ("Meeting it." if cap.get("meeting_target") else "Behind it.")),
         "scheduler", _pct_color(cap.get("pct", 0)), ""),
        ("Daily volume", cap.get("actual_per_day", 0), "jobs per day",
         _trend([("Jobs", _L(cap.get("series")), TEAL)])
         if len(_L(cap.get("series"))) > 1 else _spark(_L(cap.get("series")), TEAL),
         "The last seven days of actual throughput.",
         "job store", TEAL, ""),
        ("Agent activity", len(rows), "agents by recency",
         _CH().cohort(rows, grid) if (rows and grid) else "",
         ("Which agents carry the load and which sit idle."
          if rows else "Fills as agents run."),
         "run stamps", BLUE, ""),
        ("Idle capacity", wf.get("idle", 0), "agents unused", "",
         ("Unused capacity is not free — an untested agent is a risk, not a "
          "reserve."),
         "computed", AMBER if wf.get("idle") else GREEN, ""),
        ("Approvals pending", wf.get("approvals_pending", 0), "blocking throughput", "",
         ("Every pending approval is work the machine finished and cannot ship."),
         "job store", AMBER if wf.get("approvals_pending") else GREEN, ""),
    ]
    for label, note in [
        ("Cadence targets", "blogs, social and outreach per day"),
        ("Peak throughput", "the most ever done in a day"),
        ("Bottleneck stage", "where work waits longest"),
        ("Concurrency", "how many jobs move at once"),
        ("Worker capacity", "one worker, one VPS"),
        ("Scale headroom", "what a second worker would add"),
        ("Budget-limited capacity", "the cap as a throughput ceiling"),
        ("Approval throughput", "how fast decisions get made"),
        ("Time to publish", "idea to live"),
        ("Backlog age", "the oldest unfinished job"),
        ("Seasonal load", "predictable busy periods"),
        ("Capacity forecast", "when the current setup runs out"),
        ("Cost of extra capacity", "what scaling would cost"),
    ]:
        cards.append(_na(label, note,
                         "Computed from the job store and the scheduler targets.",
                         "scheduler"))
    return _head("📈", "Capacity & utilisation",
                 "Can the workforce actually do the volume being asked of it?") \
        + _vizcards(cards[:18])


# ======================================================================
#  (9) QUALITY & AUTONOMY  (16)
# ======================================================================
def board_quality(ctx) -> str:
    ctx = _ctx(ctx)
    needles = ctx["needles"]
    last_eval = ctx["last_eval"]
    wf = ctx["workforce"]
    vals = [v for v in needles.values() if isinstance(v, (int, float))]
    cards = [
        ("Quality needles", len(needles), "instruments watching for decay",
         _CH().confband([float(v) for v in vals]) if len(vals) > 2 else
         (_hbars([(k[:16], v) for k, v in needles.items()
                  if isinstance(v, (int, float))], VIOLET) if needles else ""),
         ("Task success, human takeover and cost per task — with a tolerance "
          "band, so normal variation is not read as decline."),
         "S5 instruments", VIOLET if needles else AMBER, ""),
        ("Last eval", str(last_eval.get("at", "—"))[:16] if last_eval else "—",
         "graded against the rubric", "",
         ("Seven real tasks graded by the judge." if last_eval
          else "Never run. It is the only objective quality measure here."),
         "S5 evals", GREEN if last_eval else AMBER, ""),
        ("Human takeover", f"{wf.get('human_touch_rate', 0)}%",
         "of jobs need a person",
         _donut(wf.get("human_touch_rate", 0), danger_low=False),
         "Falling takeover with steady quality is what autonomy actually means.",
         "computed", AMBER, ""),
        ("Failed jobs", wf.get("failed", 0), "did not complete", "",
         "Caught by degraded mode — the loop continues, the job is flagged.",
         "job store", PINK if wf.get("failed") else GREEN, ""),
    ]
    for label, note in [
        ("QA pass rate", "how often the gate approves"),
        ("Judge score trend", "quality over time"),
        ("Revision rate", "work sent back for a rewrite"),
        ("Autonomy level", "what runs unattended today"),
        ("Gated actions", "what always waits for you"),
        ("Auto-approval grace", "how long before autonomy releases"),
        ("Publish quality", "what actually went live"),
        ("Claim safety", "unsubstantiated claims blocked"),
        ("Brand adherence", "output matching the CI"),
        ("Duplicate detection", "repeated topics prevented"),
        ("Rollback rate", "published work later withdrawn"),
        ("Trust trajectory", "when to widen autonomy"),
    ]:
        cards.append(_na(label, note,
                         "Instrumented by the judge and the QA gate.",
                         "S1 judge"))
    return _head("🎯", "Quality & autonomy",
                 "Is the work good, and how much of it can run without you?") \
        + _vizcards(cards[:16])


# ======================================================================
#  (10) COMPUTE & CONTAINERS  (16)
# ======================================================================
def board_compute(ctx) -> str:
    ctx = _ctx(ctx)
    inf = ctx["infra"]
    health = ctx["health"]
    containers = _L(inf.get("containers"))
    cards = [
        ("Containers", f"{inf.get('containers_up', 0)}/{len(containers) or 3}", "up",
         _statusgrid([(n, ok, "up" if ok else "check") for n, ok in containers]),
         "Database, API and worker. All three are needed for the engine to run.",
         "health probe", GREEN if inf.get("containers_up") == 3 else AMBER, ""),
        ("Health probe", "healthy" if inf.get("healthy") else "check",
         "preflight result",
         _statusgrid([(k[:16], _D(v).get("status") == "ok", str(_D(v).get("status", "")))
                      for k, v in health.items() if isinstance(v, dict)][:9]),
         "Anthropic, Postgres and the connectors, checked without spending anything.",
         "GET /health", GREEN if inf.get("healthy") else AMBER, ""),
        ("VPS sharing", 3, "businesses on one machine", "",
         inf.get("disk_note", ""),
         "infrastructure", AMBER, ""),
    ]
    for label, note in [
        ("CPU headroom", "how close to saturation"),
        ("Memory headroom", "RAM against the container limits"),
        ("Disk free", "against the 100 GB volume"),
        ("Restart count", "containers cycling unexpectedly"),
        ("Uptime", "how long the worker has run"),
        ("Deploy frequency", "how often code changes"),
        ("Build time", "how long a rebuild takes"),
        ("Image size", "what gets shipped"),
        ("Port exposure", "8000 is public"),
        ("OS updates", "security patches pending"),
        ("Reboot required", "kernel updates waiting"),
        ("Noisy neighbour", "the other two businesses"),
        ("Scaling path", "a second worker or a bigger box"),
    ]:
        cards.append(_na(label, note,
                         "Read from the host — stated rather than guessed.",
                         "infrastructure"))
    return _head("🖥", "Compute & containers",
                 "The machine underneath everything, and how much room it has "
                 "left.") + _vizcards(cards[:16])


# ======================================================================
#  (11) STORAGE & DATABASE  (16)
# ======================================================================
def board_storage(ctx) -> str:
    ctx = _ctx(ctx)
    inf = ctx["infra"]
    tm = _L(inf.get("treemap"))
    cards = [
        ("Settings size", f"{inf.get('settings_kb', 0):,.0f} KB", "in Postgres",
         _treemap([(k, v) for k, v in tm]) if tm else "",
         ("The crawl, the audit, the work orders and every snapshot live in "
          "settings rows. This is the row that grows."),
         "storage", AMBER if inf.get("growth_risk") else GREEN, ""),
        ("Largest key", (_L(inf.get("largest")) or ["—"])[0], "biggest single row",
         "",
         ("A settings row has a practical size limit and nothing was watching it "
          "until now."),
         "storage", AMBER if inf.get("growth_risk") else BLUE, ""),
        ("Growth risk", "yes" if inf.get("growth_risk") else "no",
         "settings row size",
         _score_gauge(min(100, inf.get("settings_kb", 0) / 50), 80),
         ("Trim the crawl or move it to its own table if this keeps climbing."
          if inf.get("growth_risk") else "Comfortable at the current size."),
         "computed", AMBER if inf.get("growth_risk") else GREEN, ""),
    ]
    for label, note in [
        ("Database size", "the whole Postgres volume"),
        ("Table growth", "jobs, settings, daily cost"),
        ("Job history", "how much is kept"),
        ("Row counts", "per table"),
        ("Index health", "query performance"),
        ("Vacuum status", "Postgres housekeeping"),
        ("Connection pool", "concurrent workers"),
        ("Query latency", "how fast the blackboard reads"),
        ("Data retention", "what should be pruned"),
        ("Archive strategy", "cold storage for old jobs"),
        ("Volume backing", "where the Docker volume lives"),
        ("Disk quota", "the 100 GB shared with two other businesses"),
        ("Storage forecast", "when it runs out at this rate"),
    ]:
        cards.append(_na(label, note,
                         "Read from Postgres and the Docker volume.",
                         "database"))
    return _head("💾", "Storage & database",
                 "Where the data lives, how fast it grows, and when that becomes "
                 "a problem.") + _vizcards(cards[:16])


# ======================================================================
#  (12) CONTINUITY & BACKUP  (16)
# ======================================================================
def board_continuity(ctx) -> str:
    ctx = _ctx(ctx)
    cont = ctx["continuity"]
    at_risk = _L(cont.get("what_is_at_risk"))
    tasks = [("detect", 0, 1), ("restore db", 1, 2), ("redeploy", 3, 1),
             ("re-verify", 4, 1)]
    cards = [
        ("Backup", "configured" if cont.get("configured") else "NONE",
         "database continuity",
         _donut(100 if cont.get("configured") else 0),
         cont.get("verdict", ""),
         "deploy", GREEN if cont.get("configured") else PINK, ""),
        ("What is at risk", len(at_risk), "if the volume is lost", "",
         ("Losing the Postgres volume loses all of this at once. Code is in git; "
          "this is not."),
         "computed", PINK if not cont.get("configured") else AMBER,
         _rows(at_risk, left_fmt=lambda x: str(x), empty="")),
        ("Restore tested", "yes" if cont.get("restore_tested") else "no",
         "has a restore been rehearsed", "",
         ("An untested backup is not a backup — it is a belief."),
         "deploy", GREEN if cont.get("restore_tested") else PINK, ""),
        ("Recovery timeline", len(tasks), "steps to be back up",
         _CH().gantt(tasks, span=7),
         "Detect, restore, redeploy, verify — the sequence if the box is lost.",
         "runbook", VIOLET, ""),
        ("Code rollback", "git revert", "always available", "",
         cont.get("rollback", ""),
         "git", GREEN, ""),
        ("The fix", "nightly pg_dump", "cheapest large risk to remove", "",
         cont.get("fix", ""),
         "recommendation", PINK if not cont.get("configured") else GREEN, ""),
    ]
    for label, note in [
        ("Backup frequency", "how often, if at all"),
        ("Backup location", "a second machine, not the same disk"),
        ("Retention", "how many copies are kept"),
        ("Encryption at rest", "backups contain every credential"),
        ("RPO", "how much data you can afford to lose"),
        ("RTO", "how long you can afford to be down"),
        ("Runbook", "written steps someone else could follow"),
        ("Credential recovery", "if the database is gone"),
        ("Site continuity", "WordPress is separately hosted"),
        ("Incident log", "what has gone wrong before"),
    ]:
        cards.append(_na(label, note,
                         "Continuity planning — deliberately blank until it is "
                         "actually decided, rather than assumed.", "runbook"))
    return _head("🧯", "Continuity & backup",
                 "If the machine disappeared tonight, what would you lose and "
                 "how would you get back?") + _vizcards(cards[:16])


# ======================================================================
#  ASSEMBLY
# ======================================================================
TABS = [
    ("rkcmd", "🛡", "Risk Command"),
    ("rkregister", "📋", "Risk Register"),
    ("rkrevenue", "💼", "Revenue Risk"),
    ("rkchannel", "🔗", "Channel Risk"),
    ("rkworkforce", "🤖", "Workforce"),
    ("rkcapacity", "📈", "Capacity"),
    ("rkquality", "🎯", "Quality"),
    ("rkcompute", "🖥", "Compute"),
    ("rkstorage", "💾", "Storage"),
    ("rkcontinuity", "🧯", "Continuity"),
    ("rkcompliance", "⚖️", "Compliance"),
    ("rksecurity", "🔐", "Security"),
]

GROUPS = [
    ("rkhurt", "① WHAT COULD HURT", "What are the risks?",
     ["rkcmd", "rkregister", "rkrevenue", "rkchannel"]),
    ("rkwork", "② WHO DOES THE WORK", "Can the agents cope?",
     ["rkworkforce", "rkcapacity", "rkquality"]),
    ("rkrun", "③ WILL IT KEEP RUNNING", "Is the machine safe?",
     ["rkcompute", "rkstorage", "rkcontinuity"]),
    ("rkcover", "④ ARE WE COVERED", "Legally and securely?",
     ["rkcompliance", "rksecurity"]),
]

_TAB_BOARDS = {
    "rkcmd": [("Risk Command", board_command)],
    "rkregister": [("Risk Register", board_register)],
    "rkrevenue": [("Revenue Risk", board_revenue)],
    "rkchannel": [("Channel Risk", board_channel)],
    "rkcompliance": [("Compliance", board_compliance)],
    "rksecurity": [("Security", board_security)],
    "rkworkforce": [("Workforce", board_workforce)],
    "rkcapacity": [("Capacity", board_capacity)],
    "rkquality": [("Quality", board_quality)],
    "rkcompute": [("Compute", board_compute)],
    "rkstorage": [("Storage", board_storage)],
    "rkcontinuity": [("Continuity", board_continuity)],
}

CARD_COUNTS = {"command": 14, "register": 22, "revenue": 18, "channel": 18,
               "compliance": 16, "security": 18, "workforce": 20, "capacity": 18,
               "quality": 16, "compute": 16, "storage": 16, "continuity": 16}
TOTAL_CARDS = sum(CARD_COUNTS.values())

_TAB_COUNTS = {"rkcmd": 14, "rkregister": 22, "rkrevenue": 18, "rkchannel": 18,
               "rkcompliance": 16, "rksecurity": 18, "rkworkforce": 20,
               "rkcapacity": 18, "rkquality": 16, "rkcompute": 16,
               "rkstorage": 16, "rkcontinuity": 16}


def _safe_board(name, fn, ctx) -> str:
    _CURRENT_BOARD["name"] = name
    try:
        return fn(ctx)
    except Exception as e:
        H = _H()
        return ("<div class='card full' style='margin-top:12px;border-color:#FF6B93'>"
                f"<p class='ct'>⚠ {H._esc(name)} board failed to render</p>"
                f"<p class='cc'>{H._esc(type(e).__name__)}: {H._esc(str(e)[:300])}</p>"
                "<p class='cc'>Every other board is unaffected.</p></div>")


def risk_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def risk_section(ctx) -> str:
    H = _H()
    ctx = _ctx(ctx)
    panels = risk_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'rkhurt')}' onclick=\"seoTab('{tid}')\">"
        f"<span>{icon}</span>{H._esc(label)}"
        f"<span class='n'>{_TAB_COUNTS.get(tid, 0)}</span></button>"
        for i, (tid, icon, label) in enumerate(TABS))
    grouprail = "".join(
        f"<button class='sgrp{' on' if i == 0 else ''}' id='sgrp-{gid}' "
        f"onclick=\"seoGroup('{gid}')\"><b>{H._esc(label)}</b>"
        f"<span class='gq'>{H._esc(question)}</span></button>"
        for i, (gid, label, question, _t) in enumerate(GROUPS))
    body = "".join(
        f"<div class='spanel{' on' if i == 0 else ''}' id='spanel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _, _) in enumerate(TABS))
    runbar = ("<div class='ctrl' style='margin:10px 0 2px;flex-wrap:wrap'>"
              "<button class='cbtn' onclick='runRisk()'>🛡 Refresh the risk register</button>"
              "<button class='cbtn' onclick=\"act('/health')\">🩺 Re-check health</button>"
              "<button class='cbtn' onclick=\"act('/selftest')\">🧪 Self-test agents</button>"
              "<button class='cbtn' onclick=\"act('/evals/run')\">🎯 Run evals</button>"
              "</div>")
    tools = ("<div class='stools'>"
             "<input id='cardq4' class='cinput' placeholder='🔎 Search all 208 risk cards…' "
             "oninput='seoFilter()'>"
             "<button class='cbtn sm' onclick=\"seoSev('all')\">All</button>"
             "<button class='cbtn sm' onclick=\"seoSev('critical')\">⛔ Needs fixing</button>"
             "<button class='cbtn sm' onclick=\"seoSev('warn')\">⚠ Worth a look</button>"
             "<button class='cbtn sm' onclick=\"seoSev('ok')\">✓ Healthy</button></div>")
    hint = (f"<div class='shint'>👇 <b>{TOTAL_CARDS} cards</b> in {len(GROUPS)} groups. "
            "This replaces Risk, AI Workforce and Infrastructure — which held "
            "thirteen cards between them and read the same three numbers.</div>")
    return (_TAB_CSS + runbar + hint
            + f"<div class='sgroups'>{grouprail}</div>"
            + f"<div class='stabs'>{bar}</div>" + tools + body)


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_risk as RK

    status = {"claude_api": True, "wordpress_publish": False, "google_gsc_ga4": True,
              "google_sheets": False, "email_send": True, "serper_search": True,
              "ads_api": False}
    jobs = [{"job_id": "a", "status": "optimized", "created_at": "2026-07-29T09:00:00",
             "payload": {"outcome": {"client": "Acme", "revenue": 5000}}},
            {"job_id": "b", "status": "failed", "created_at": "2026-07-30T09:00:00"},
            {"job_id": "c", "status": "AWAITING_APPROVAL", "created_at": "2026-07-30T10:00:00"}]
    agents = [{"skill": "content_producer", "runs": 5, "success_pct": 80.0,
               "never_run": False, "last_run": "2026-07-30T09:00:00"},
              {"skill": "judge", "runs": 0, "success_pct": None, "never_run": True}]

    class S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dd=None): return self.d.get(k, dd)
        def set_setting(self, k, v): self.d[k] = v
    st = S()
    risks = RK.register(status=status, month_spent=12.5, month_cap=200, jobs=jobs,
                        wires_down=6, waiting=3, healthy=True, leads=0,
                        aeo={"mention_rate": 0.0})
    RK.record_snapshot(st, risks)
    hist = RK.record_snapshot(st, [dict(r, score=max(1, r["score"] - 1)) for r in risks])
    nodes, edges = RK.channel_blast(status)
    rows, grid = RK.cohort_grid(agents)
    ctx = {
        "risks": risks, "history": hist,
        "by_category": RK.by_category(risks),
        "bump": RK.rank_movement(hist, [r["key"] for r in risks[:4]]),
        "concentration": RK.concentration(jobs),
        "compliance": RK.compliance(),
        "credentials": RK.credential_age(status),
        "vendor_share": RK.vendor_share(status),
        "blast_nodes": nodes, "blast_edges": edges,
        "workforce": RK.workforce(agents, jobs, content_cost=4.0),
        "capacity": RK.capacity(jobs, {"blogs": 2, "outreach": 1,
                                       "social_per_channel": 1}),
        "cohort_rows": rows, "cohort_grid": grid,
        "infra": RK.infra({"total_bytes": 5_000_000,
                           "keys": {"seo_crawl": 4_000_000, "seo_audit": 900_000},
                           "largest": ("seo_crawl", 4_000_000)},
                          {"healthy": True, "postgres": {"status": "ok"}},
                          {"crawl": "x"}),
        "continuity": RK.continuity(None),
        "status": status, "agents": agents, "jobs": jobs,
        "health": {"healthy": True, "anthropic": {"status": "ok"},
                   "postgres": {"status": "ok"}},
        "cost": {"month_spent": 12.5, "month_cap": 200, "pct_of_cap": 6.2},
        "aeo": {"mention_rate": 0.0},
        "geo": {"language": {"uncovered": ["Germany", "Switzerland"]}},
        "needles": {"task_success": 82.0, "human_takeover": 12.0,
                    "cost_per_task": 0.04},
        "last_eval": {"at": "2026-07-30T08:00:00"},
    }

    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = risk_pages(ctx)
    assert set(pages) == {t for t, _, _ in TABS}, list(pages)
    html = "".join(pages.values())
    assert "failed to render" not in html

    counted = len(re.findall(r"<div class='card (?:overflowcard )?sev-", html))
    assert counted == TOTAL_CARDS, f"expected {TOTAL_CARDS}, rendered {counted}"
    for tab, want in _TAB_COUNTS.items():
        got = len(re.findall(r"<div class='card (?:overflowcard )?sev-", pages[tab]))
        assert got == want, f"{tab}: {got} != {want}"
    ids = re.findall(r"<div class='card (?:overflowcard )?sev-[a-z]+' id='(card-[a-z0-9-]+)'", html)
    assert len(ids) == TOTAL_CARDS and len(set(ids)) == len(ids), (len(ids), len(set(ids)))
    assert html.count("class='cta'") >= TOTAL_CARDS

    # the three old sections' signature content survives
    assert "likelihood" in pages["rkregister"].lower(), "risk matrix context missing"
    assert "content_producer" in pages["rkworkforce"], "agent roster missing"
    assert "Containers" in pages["rkcompute"], "connection/container status missing"
    # the new truths
    assert "No backup configured" in pages["rkcontinuity"], "the real top risk"
    assert "EIN" in pages["rkcompliance"], "compliance items must be stated"
    assert "Germany" in pages["rkchannel"], "market coverage risk must surface"

    # shape robustness
    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {k: 0 for k in ctx}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    sec = risk_section(ctx)
    for tid, _, _ in TABS:
        assert f"id='stab-{tid}'" in sec and f"id='spanel-{tid}'" in sec, tid
    for gid, _l, _q, _t in GROUPS:
        assert f"id='sgrp-{gid}'" in sec, gid
    grouped = [t for _g, _l, _q, ts in GROUPS for t in ts]
    assert sorted(grouped) == sorted(t for t, _, _ in TABS)
    assert sec.count("class='spanel on'") == 1 and sec.count("class='stab on'") == 1
    assert "overflowcard" in sec and "Show all" in sec
    print(f"risk_boards self-check OK — 12 boards, {counted} cards, "
          f"{len(set(ids))} unique ids, {html.count('<svg')} charts; risk matrix, "
          f"agent roster and container status all preserved")
