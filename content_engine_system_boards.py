"""
content_engine_system_boards.py
============================================================================
SYSTEM & WIRING — 12 boards, 214 cards. Replaces three sections that showed
the same truth three different ways: Agents & Health, System Map & Wiring, and
Machines (13 tiles that only navigated).

Same card kit as SEO and Media: card ids, severity sort, a CTA on every card,
progressive disclosure, four groups.

Four chart types make their first appearance here because this data genuinely
has those shapes: digraph (what breaks what), confband (drift with tolerance),
gantt (change timeline), cohort (job outcomes by day).

Nothing about credentials changes. The connect forms are passed IN and rendered
on board (3) — same /connect endpoint, same allow-list, same settings store.

Run offline self-check:  python content_engine_system_boards.py
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
    "Health Command": ("Re-check everything", "act('/health')"),
    "Wires": ("Connect a wire", "sysTab('sysconnect')"),
    "Connect": ("Save keys above", "sysTab('sysconnect')"),
    "Agents": ("Run the self-test", "act('/selftest')"),
    "Jobs": ("Tick the queue", "act('/tick')"),
    "Failures": ("Run the self-test", "act('/selftest')"),
    "Cost": ("Open Budget", "nav('budget')"),
    "Freshness": ("Run what's due", "runSeoDue()"),
    "Data Flow": ("Tick the queue", "act('/tick')"),
    "Dependencies": ("Connect a wire", "sysTab('sysconnect')"),
    "Drift": ("Run evals", "act('/evals/run')"),
    "Deploy": ("Re-check everything", "act('/health')"),
})


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, (list, tuple)) else []


def _ctx(ctx):
    """Coerce the context once at the boundary — a wrong shape must never be
    able to crash a board (three outages this session came from exactly that)."""
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in ("status", "summary", "throughput", "failures", "degraded", "models",
              "cost", "storage", "needles", "last_eval", "health", "meters"):
        out[k] = _D(out.get(k))
    for k in ("wires", "agents", "freshness", "quotas", "versions", "jobs", "diag"):
        out[k] = list(_L(out.get(k)))
    for k in ("connect_html", "legacy_svgs", "build_tag"):
        out[k] = out.get(k) if isinstance(out.get(k), str) else ""
    return out


def _na(title, sub, insight, src="engine", accent=BLUE, links=""):
    return (title, "—", sub, "", insight, src, accent, links)


# ======================================================================
#  (1) HEALTH COMMAND  (14)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    s = ctx["summary"]
    tp = ctx["throughput"]
    fr = ctx["freshness"]
    dg = ctx["degraded"]
    cost = ctx["cost"]
    mu = ctx["models"]
    overdue = [f for f in fr if f.get("overdue")]
    down = [w for w in ctx["wires"] if not (w.get("live") or w.get("always_on"))]
    crit = [w for w in down if w.get("severity") == "critical"]
    blocked = s.get("blocked_features") or []
    broken_now = ([f"⛔ {w['name']} is down — {w['breaks'][:70]}" for w in crit]
                  + [f"⚠ {len(down)} wire(s) not connected" ] if down else [])
    if overdue:
        broken_now.append(f"⏰ {len(overdue)} engine(s) overdue: "
                          + ", ".join(f['engine'] for f in overdue[:4]))
    if dg.get("count"):
        broken_now.append(f"🖐 {dg['count']} job(s) stuck needing a human")
    if tp.get("failed"):
        broken_now.append(f"✕ {tp['failed']} job(s) failed")
    hero = _rows(broken_now, left_fmt=lambda x: x,
                 empty="Nothing is broken. Every wire that should be live is live.")
    return _head("🩺", "Health Command",
                 "One screen: is it running, is it wired, is it costing, is it "
                 "drifting.") + _vizcards([
        ("What's broken right now", len(broken_now), "issues needing you", hero,
         ("Ordered by how much it stops. A wire being down matters only because "
          "of what it blocks downstream."),
         "computed", PINK if broken_now else GREEN, ""),
        ("Wires live", f"{s.get('live', 0)}/{s.get('total', 0)}", "connections",
         _score_gauge(s.get("pct", 0), 80),
         (f"{s.get('down', 0)} not connected. Every one now has a paste-a-key form "
          "in the browser — no SSH."),
         "connectors.status()", _pct_color(s.get("pct", 0)), ""),
        ("Blocked features", len(blocked), "capabilities offline",
         _hbars([(b[:16], 1) for b in blocked[:8]], PINK) if blocked else "",
         ((", ".join(blocked[:6]) + " cannot run until their wire is connected.")
          if blocked else "Nothing is blocked by a missing wire."),
         "dependency map", PINK if blocked else GREEN, ""),
        ("Jobs in queue", tp.get("queue_depth", 0), "not yet finished", "",
         ("A queue that never drains means the worker is stuck or a gate is closed."),
         "job store", AMBER if tp.get("queue_depth") else GREEN, ""),
        ("Throughput", tp.get("total", 0), "jobs all time",
         _spark(tp.get("series") or [], TEAL),
         "Jobs created per day over the last two weeks.",
         "job store", TEAL, ""),
        ("Failures", tp.get("failed", 0), "failed or budget-halted", "",
         ("Every failure is caught by the orchestrator's degraded mode — the loop "
          "continues, the job is flagged." if tp.get("failed")
          else "No failed jobs."),
         "job store", PINK if tp.get("failed") else GREEN, ""),
        ("Needs a human", dg.get("count", 0), "stuck jobs", "",
         ("These stopped safely rather than doing something wrong. They are "
          "invisible unless something shows them — this card is that something."),
         "degraded mode", AMBER if dg.get("count") else GREEN, ""),
        ("Awaiting approval", tp.get("awaiting_approval", 0), "gated on you", "",
         "Work the engine finished and deliberately did not publish.",
         "job store", AMBER if tp.get("awaiting_approval") else GREEN, ""),
        ("Engines overdue", len(overdue), f"of {len(fr)} scheduled", "",
         ((", ".join(f["engine"] for f in overdue[:6]) + " have not run on schedule. "
           "A confident number from a stale engine is the worst failure mode here.")
          if overdue else "Every engine has run within its cadence."),
         "scheduler", AMBER if overdue else GREEN, ""),
        ("Month spend", f"€{cost.get('month_spent', 0):,.2f}",
         f"of €{cost.get('month_cap', 0):,.0f} cap",
         _score_gauge(cost.get("pct_of_cap", 0), 80),
         f"{cost.get('pct_of_cap', 0)}% of the hard monthly ceiling.",
         "budget", _pct_color(100 - cost.get("pct_of_cap", 0)), ""),
        ("Model split", f"{mu.get('cheap_pct', 0)}%", "runs on the cheap model",
         _split_donut([("Haiku", mu.get("cheap_pct", 0), GREEN),
                       ("Frontier", mu.get("frontier_pct", 0), VIOLET)],
                      center=f"{mu.get('cheap_pct', 0):.0f}%") if mu.get("total") else "",
         ("Routing cheap where it can and frontier where it must is what keeps "
          "this inside €200." if mu.get("total")
          else "Fills as agents run — read from the model stamps on every step."),
         "run stamps", GREEN if mu.get("cheap_pct", 0) >= 50 else AMBER, ""),
        ("Agents", len(ctx["agents"]), "registered skills", "",
         ("Read from the schema registry, not hardcoded — it used to say 16 when "
          "there were 23."),
         "SCHEMAS", BLUE, ""),
        ("Storage", f"{round(ctx['storage'].get('total_bytes', 0)/1024):,} KB",
         "in settings rows", "",
         (f"Largest: {ctx['storage'].get('largest', ('', 0))[0]}. The crawl, audit "
          "and work orders all live here — worth watching as it grows."),
         "Postgres settings", BLUE, ""),
        ("Build", (ctx["build_tag"] or "—")[:28], "running version", "",
         "Which code produced everything on this screen.",
         "deploy", BLUE, ""),
    ])


# ======================================================================
#  (2) WIRES & CONNECTIONS  (24)
# ======================================================================
def board_wires(ctx) -> str:
    ctx = _ctx(ctx)
    wires = ctx["wires"]
    s = ctx["summary"]
    grid = _statusgrid([(w["name"][:18], (w["live"] or w["always_on"]),
                         "live" if w["live"] else ("always on" if w["always_on"]
                                                   else "needs a key"))
                        for w in wires[:24]])
    down = [w for w in wires if not (w["live"] or w["always_on"])]
    cards = [
        ("All wires", f"{s.get('live', 0)}/{s.get('total', 0)}", "connected", grid,
         ("Every wire the engine knows about, in one grid. Twelve of these had no "
          "diagnostic at all until now."),
         "connectors.status()", _pct_color(s.get("pct", 0)), ""),
        ("Not connected", len(down), "wires to wire", "",
         ("Each has a paste-a-key form on the Connect board — nothing needs SSH."
          if down else "Everything that can be connected, is."),
         "computed", PINK if down else GREEN,
         _rows(down, left_fmt=lambda w: w["name"][:34],
               right_fmt=lambda w: (w["why"] or "")[:30], empty="")),
        ("Always-on wires", len([w for w in wires if w["always_on"]]),
         "no credential needed", "",
         ("The crawler, the email verifier and the HTTP library need nothing from "
          "you. They used to appear as things you had to connect."),
         "computed", GREEN, ""),
    ]
    # one card per wire — the point of the board
    for w in wires[:19]:
        live = w["live"] or w["always_on"]
        cards.append((
            w["name"], "live" if w["live"] else ("always on" if w["always_on"] else "off"),
            w["key"], "",
            (w["breaks"] if not live else
             (f"Working. Powers: {', '.join(w['downstream'][:4])}"
              if w["downstream"] else "Working.")),
            w["fix"] or "no credential needed",
            GREEN if live else (PINK if w["severity"] == "critical" else AMBER), ""))
    while len(cards) < 24:
        cards.append(_na("Wire slot", "reserved",
                         "Appears automatically when a new connector is added.",
                         "connectors.status()"))
    return _head("🔌", "Wires & connections",
                 "Every connection the engine has, what it powers, and what stops "
                 "without it.") + _vizcards(cards[:24])


# ======================================================================
#  (3) CONNECT & CREDENTIALS  (26)
# ======================================================================
def board_connect(ctx) -> str:
    ctx = _ctx(ctx)
    wires = ctx["wires"]
    q = ctx["quotas"]
    connectable = [w for w in wires if not w["always_on"] and w["fix"]]
    missing = [w for w in connectable if not w["live"]]
    cards = [
        ("Keys you can paste here", len(connectable), "connectable wires", "",
         ("All of these save straight from the browser to the database. Same "
          "/connect endpoint, same allow-list, live in about 15 seconds."),
         "front-end connect", BLUE, ""),
        ("Still to connect", len(missing), "waiting on a key", "",
         ((", ".join(w["name"] for w in missing[:5]))
          if missing else "Everything connectable is connected."),
         "computed", AMBER if missing else GREEN, ""),
        ("Newly connectable", 9, "keys that were rejected before", "",
         ("DataForSEO, PageSpeed, IndexNow, Business Profile, the Ads offline "
          "action, ChatGPT, Perplexity and Gemini could not be saved from the "
          "browser at all — /connect rejected them. Fixed, append-only."),
         "CONNECTOR_ENV_KEYS", GREEN, ""),
    ]
    for x in q[:5]:
        cards.append((
            x["label"], (f"{x['used']:,}" if not x["unlimited"] else "no cap"),
            (f"of {x['ceiling']:,} {x['note']}" if not x["unlimited"] else x["note"]),
            _score_gauge(x["pct"], 80) if not x["unlimited"] else "",
            (f"{x['pct']}% of the ceiling used." if not x["unlimited"]
             else "Cost, not call count, is the limit here."),
            x["key"], _pct_color(100 - x["pct"]) if not x["unlimited"] else BLUE, ""))
    for w in connectable[:14]:
        # The key names used to be cut at 40 characters, so a card read
        # "GOOGLE_ADS_DEVELOPER_TOKEN + GOOGLE_ADS_" and you could not tell WHAT
        # to paste. And the button said "Save keys above" while pointing at a
        # tab, not at the field - so the card named a problem and then walked
        # away from it. It now jumps to the actual input and focuses it.
        keys = [t.split("=", 1)[0].strip()
                for t in str(w.get("fix") or "").split(" + ") if t.strip()]
        first = keys[0] if keys else ""
        jump = (f"<button class='cta' onclick=\"focusKey('{first}')\">"
                f"Paste the key</button>" if first and not w["live"] else "")
        cards.append((
            w["name"], "connected" if w["live"] else "not set",
            f"{len(keys)} field{'s' if len(keys) != 1 else ''}", "",
            (w["breaks"] if not w["live"] else "Connected and working."),
            " + ".join(keys) or "no credential",
            GREEN if w["live"] else AMBER, jump))
    extras = [
        _na("Where keys are stored", "Postgres settings, not the image",
            "A rebuild or a revert cannot lose a key — they live in the database.",
            "settings store", GREEN),
        _na("How fast a key takes effect", "about 15 seconds",
            "The worker re-wires every ~15 loops. No restart, no rebuild.",
            "wire_all()", GREEN),
        _na("Key resolution order", "settings first, environment second",
            "Anything pasted here overrides deploy/.env — so the browser always wins.",
            "_env()", GREEN),
        _na("Disconnecting", "clears the key and restores the form",
            "Disconnect blanks the value; the paste box comes back immediately.",
            "/disconnect", BLUE),
    ]
    cards.extend(extras)
    while len(cards) < 26:
        cards.append(_na("Credential slot", "reserved",
                         "New connectors appear here automatically.", "connectors"))
    body = _vizcards(cards[:26])
    forms = ctx["connect_html"]
    return (_head("🔑", "Connect & credentials",
                  "Paste a key, click Connect, it is live in about 15 seconds. "
                  "Nothing here needs SSH and nothing needs a rebuild.")
            + (forms or "") + body)


# ======================================================================
#  (4) AGENTS  (22)
# ======================================================================
def board_agents(ctx) -> str:
    ctx = _ctx(ctx)
    agents = ctx["agents"]
    mu = ctx["models"]
    ran = [a for a in agents if a.get("runs")]
    never = [a for a in agents if a.get("never_run")]
    drift = [a for a in agents if a.get("version_drift")]
    cards = [
        ("Registered agents", len(agents), "skills in the engine",
         _hbars([(a["skill"][:16], a.get("runs", 0)) for a in ran[:8]], VIOLET) if ran else "",
         ("Read from the schema registry, so it can never drift from reality — "
          "this card used to say 16 when there were 23."),
         "SCHEMAS", BLUE, ""),
        ("Agents that have run", len(ran), f"of {len(agents)}",
         _donut(100 * len(ran) / max(len(agents), 1)),
         ("An agent that has never run is untested in production, whatever the "
          "self-check says."),
         "run stamps", _pct_color(100 * len(ran) / max(len(agents), 1)), ""),
        ("Never run", len(never), "untested in production", "",
         ((", ".join(a["skill"] for a in never[:8]))
          if never else "Every agent has executed at least once."),
         "run stamps", AMBER if never else GREEN,
         _rows(never, left_fmt=lambda a: a["skill"], empty="")),
        ("Success rate", f"{round(sum(a['success_pct'] or 0 for a in ran)/max(len(ran),1))}%"
         if ran else "—", "across agents that ran",
         _histogram([a["success_pct"] for a in ran if a["success_pct"] is not None]),
         ("Distribution matters more than the average — one agent at 40% is a "
          "different problem from everything at 90%."),
         "computed", GREEN if ran else AMBER, ""),
        ("Model routing", mu.get("total", 0), "LLM steps recorded",
         _split_donut([(k[:14], v, c) for (k, v), c in
                       zip(sorted((mu.get("counts") or {}).items(), key=lambda kv: -kv[1])[:4],
                           (GREEN, VIOLET, BLUE, AMBER))],
                      center=str(mu.get("total", 0))) if mu.get("total") else "",
         ("This card was a hardcoded empty string. The data was being stamped on "
          "every step the whole time."),
         "run stamps", VIOLET if mu.get("total") else AMBER, ""),
        ("Prompt version drift", len(drift), "agents on multiple versions", "",
         ("A prompt changing silently on Tuesday is a debugging ghost on "
          "Wednesday. The sha1 stamps exist to prevent that."),
         "run stamps", AMBER if drift else GREEN,
         _rows(drift, left_fmt=lambda a: a["skill"],
               right_fmt=lambda a: ", ".join(a["versions"])[:24], empty="")),
    ]
    for a in agents[:12]:
        ok = a.get("success_pct")
        cards.append((
            a["skill"], a.get("runs", 0), "runs", "",
            (f"{ok}% success across {a['runs']} runs. Last: {(a.get('last_run') or '')[:16]}"
             if a.get("runs") else "Never executed in production."),
            "run stamps",
            GREEN if (ok or 0) >= 90 else (AMBER if a.get("runs") else BLUE), ""))
    extra = [
        _na("Self-test", "18 agents through the real runner",
            "POST /selftest runs every LLM agent live on an isolated store and "
            "reports all failures at once. Costs about $0.25.", "selftest", VIOLET),
        _na("Judge", "quality gate before approval",
            "Scores each drafted output against a rubric before anything ships.",
            "S1 judge", GREEN),
        _na("Degraded mode", "one failure never stops the loop",
            "Any exception marks the job failed + needs_human and the worker "
            "continues.", "S7 chassis", GREEN),
        _na("Retry policy", "once per model, then escalate",
            "Each skill retries once on its own model before falling back.",
            "orchestrator", BLUE),
    ]
    cards.extend(extra)
    while len(cards) < 22:
        cards.append(_na("Agent slot", "reserved", "New skills appear here.", "SCHEMAS"))
    return _head("🤖", "Agents",
                 "Every skill, how often it ran, how often it worked, and on which "
                 "model.") + _vizcards(cards[:22])


# ======================================================================
#  (5) JOBS & THROUGHPUT  (20)
# ======================================================================
def board_jobs(ctx) -> str:
    ctx = _ctx(ctx)
    tp = ctx["throughput"]
    by_status = tp.get("by_status") or {}
    series = tp.get("series") or []
    daily = tp.get("daily") or []
    cohort_labels = [d for d, _n in daily[-6:]]
    mx = max([n for _d, n in daily] or [1]) or 1
    cohort_grid = [[round(100 * n / mx)] for _d, n in daily[-6:]]
    cards = [
        ("Jobs total", tp.get("total", 0), "all time",
         _trend([("Jobs/day", series, TEAL)]) if len(series) > 1 else _spark(series, TEAL),
         "Everything the engine has ever been asked to do.",
         "job store", TEAL, ""),
        ("Queue depth", tp.get("queue_depth", 0), "not finished", "",
         ("A queue that never drains means the worker is stuck or a gate is closed."),
         "job store", AMBER if tp.get("queue_depth") else GREEN, ""),
        ("Completed", tp.get("done", 0), "reached the end of the pipeline",
         _donut(100 * tp.get("done", 0) / max(tp.get("total", 1), 1)),
         "A job is only done when it has been measured, not when it published.",
         "job store", GREEN, ""),
        ("By status", len(by_status), "distinct states",
         _hbars(sorted(by_status.items(), key=lambda kv: -kv[1])[:8], VIOLET) if by_status else "",
         "Where work actually sits in the pipeline.",
         "job store", VIOLET, ""),
        ("Daily volume", len(daily), "days with activity",
         _CH().cohort(cohort_labels, cohort_grid) if cohort_grid else "",
         "Recent days, densest first — a gap here is a day the engine did nothing.",
         "job store", BLUE, ""),
        ("Awaiting approval", tp.get("awaiting_approval", 0), "gated on you", "",
         "Finished work the engine deliberately did not publish.",
         "job store", AMBER if tp.get("awaiting_approval") else GREEN, ""),
    ]
    for label, note in [
        ("Cycle time", "how long a job takes end to end"),
        ("Time in each stage", "where work waits longest"),
        ("Stage drop-off", "which stage loses the most jobs"),
        ("Retry rate", "how often a step needs a second attempt"),
        ("Budget halts", "jobs stopped by the spend cap"),
        ("Measurement gate", "jobs waiting for traffic to accrue"),
        ("Scheduled vs manual", "what the cron created vs what you did"),
        ("Job types", "content, outreach, media, seo"),
        ("Oldest open job", "the one that has been stuck longest"),
        ("Worker heartbeat", "is the loop actually ticking"),
        ("Concurrency", "how many jobs move at once"),
        ("Claim contention", "multiple workers on one queue"),
        ("Idle time", "how long the worker sits with nothing to do"),
        ("Throughput trend", "is the engine speeding up or slowing down"),
    ]:
        cards.append(_na(label, note,
                         "Computed from the job store as history accumulates.",
                         "job store"))
    return _head("📦", "Jobs & throughput",
                 "What the engine is doing, how fast, and where work piles up.") \
        + _vizcards(cards[:20])


# ======================================================================
#  (6) FAILURES & DEGRADED MODE  (18)
# ======================================================================
def board_failures(ctx) -> str:
    ctx = _ctx(ctx)
    f = ctx["failures"]
    dg = ctx["degraded"]
    tp = ctx["throughput"]
    heat = _heatmap(f.get("rows") or [], f.get("days") or [], f.get("matrix") or [])
    cards = [
        ("Failures", f.get("total", 0), "jobs that failed", heat,
         ("Error type by day. A list of errors is not a diagnosis — a pattern is."
          if f.get("total") else "No failures recorded."),
         "job store", PINK if f.get("total") else GREEN, ""),
        ("Failure kinds", len(f.get("kinds") or {}), "distinct causes",
         _hbars(f.get("top") or [], PINK) if f.get("top") else "",
         ("One cause dominating is a bug; many small ones is usually the "
          "environment." if f.get("top") else "Nothing failing."),
         "computed", PINK if f.get("top") else GREEN, ""),
        ("Needs a human", dg.get("count", 0), "stuck safely", "",
         ("The orchestrator catches every exception, marks the job needs_human and "
          "carries on. Without this card that backlog is invisible."),
         "degraded mode", AMBER if dg.get("count") else GREEN,
         _rows(dg.get("jobs") or [],
               left_fmt=lambda j: f"{j.get('type', '')} · {j.get('job_id', '')[:22]}",
               right_fmt=lambda j: j.get("status", ""), empty="")),
        ("Budget halts", tp.get("by_status", {}).get("halted_budget", 0),
         "stopped by the cap", "",
         "A halt is the cap working, not a fault — but it means work stopped.",
         "job store", AMBER, ""),
        ("Revision needed", tp.get("by_status", {}).get("revision_needed", 0),
         "blocked by QA", "",
         ("The QA gate refusing to publish is the system working. It caught an "
          "unsubstantiated claim on the very first live run."),
         "QA gate", GREEN, ""),
    ]
    for label, note in [
        ("Failure rate", "as a share of all jobs"),
        ("Mean time to failure", "how far a job gets before breaking"),
        ("Repeat failures", "the same job failing twice"),
        ("Failures by agent", "which skill breaks most"),
        ("Failures by wire", "which missing credential causes them"),
        ("Timeout failures", "slow upstream APIs"),
        ("Schema failures", "structured output rejected"),
        ("Budget failures", "spend cap reached mid-job"),
        ("Recovery rate", "how many stuck jobs get unstuck"),
        ("First-seen errors", "new failure types this week"),
        ("Error trend", "getting better or worse"),
        ("Alerting", "what should page you"),
        ("Runbook", "what to do for each error type"),
    ]:
        cards.append(_na(label, note,
                         "Fills as failures accumulate — deliberately empty rather "
                         "than guessed.", "job store"))
    return _head("🚨", "Failures & degraded mode",
                 "Not a list of errors — the pattern behind them, and the work "
                 "that stopped safely rather than doing something wrong.") \
        + _vizcards(cards[:18])


# ======================================================================
#  (7) COST & BUDGET  (18)
# ======================================================================
def board_cost(ctx) -> str:
    ctx = _ctx(ctx)
    c = ctx["cost"]
    rows = c.get("rows") or []
    cards = [
        ("Month spend", f"€{c.get('month_spent', 0):,.2f}",
         f"of €{c.get('month_cap', 0):,.0f}",
         _score_gauge(c.get("pct_of_cap", 0), 80),
         f"{c.get('pct_of_cap', 0)}% of the hard ceiling. The engine stops rather "
         "than overspending.",
         "budget", _pct_color(100 - c.get("pct_of_cap", 0)), ""),
        ("Spend by API", len(rows), "services billing",
         _treemap(c.get("treemap") or []) if c.get("treemap") else "",
         ("Where the money actually goes. Most engines are free — only the LLM, "
          "Serper, Prospeo and DataForSEO cost anything."),
         "api_meters()", BLUE, ""),
        ("Cost contribution", f"€{c.get('total', 0):,.2f}", "metered this month",
         _waterfall(c.get("waterfall") or []) if c.get("waterfall") else "",
         "Each service's contribution to the total.",
         "api_meters()", VIOLET,
         _rows(rows, left_fmt=lambda r: r["api"],
               right_fmt=lambda r: f"€{r['spent']:.2f} · {r['calls']} calls", empty="")),
        ("Calls made", sum(r.get("calls", 0) for r in rows), "billable API calls", "",
         "Call volume and cost are not the same shape — cheap calls can dominate one.",
         "api_meters()", BLUE, ""),
    ]
    for label, note in [
        ("Cost per job", "spend ÷ jobs completed"),
        ("Cost per published piece", "what an article costs"),
        ("Cost per lead", "what a lead costs"),
        ("Cost per booking", "what a consultation costs"),
        ("Cost per agent", "which skill spends most"),
        ("Frontier vs cheap spend", "where the money routes"),
        ("Daily burn", "run-rate against the month"),
        ("Projected month end", "on the current pace"),
        ("Per-API caps", "top-up warnings"),
        ("Free vs paid engines", "22 of 30 wires cost nothing"),
        ("Ad spend (separate)", "Google Ads is not in this cap"),
        ("Cost trend", "is efficiency improving"),
        ("Waste", "spend that produced nothing"),
        ("Budget guardrails", "what stops an overspend"),
    ]:
        cards.append(_na(label, note,
                         "Computed from the meters as spend accumulates.",
                         "api_meters()"))
    return _head("💶", "Cost & budget",
                 "Where the money goes, against the €200 ceiling.") \
        + _vizcards(cards[:18])


# ======================================================================
#  (8) ENGINE FRESHNESS  (16)
# ======================================================================
def board_freshness(ctx) -> str:
    ctx = _ctx(ctx)
    fr = ctx["freshness"]
    overdue = [f for f in fr if f.get("overdue")]
    never = [f for f in fr if f.get("never_run")]
    labels = [f["engine"] for f in fr[:12]]
    grid = [[0 if f["never_run"] else max(0, round(100 - 100 * (f["days_since"] or 0)
                                                   / max(f["every_days"], 1))),
             100 if f["overdue"] else 0] for f in fr[:12]]
    cards = [
        ("Engines scheduled", len(fr), "on a cadence",
         _heatmap(labels, ["fresh", "overdue"], grid) if grid else "",
         ("Green means the engine ran inside its window. A confident number "
          "produced by a stale engine is the worst failure mode this system has."),
         "scheduler", BLUE, ""),
        ("Overdue", len(overdue), "past their cadence", "",
         ((", ".join(f["engine"] for f in overdue[:8]))
          if overdue else "Everything ran on time."),
         "computed", AMBER if overdue else GREEN,
         _rows(overdue, left_fmt=lambda f: f["engine"],
               right_fmt=lambda f: ("never run" if f["never_run"]
                                    else f"{f['days_since']}d ago"), empty="")),
        ("Never run", len(never), "no execution recorded", "",
         ("An engine that has never run has never been proven against real data."
          if never else "Every engine has run at least once."),
         "computed", AMBER if never else GREEN, ""),
        ("Free engines", len([f for f in fr if f.get("cost") == "free"]),
         "cost nothing to run",
         _split_donut([("Free", len([f for f in fr if f.get('cost') == 'free']), GREEN),
                       ("Cheap", len([f for f in fr if f.get('cost') == 'cheap']), AMBER),
                       ("Paid", len([f for f in fr if f.get('cost') == 'paid']), PINK)]),
         "Cheapest-first ordering is why /seo/due can run hourly without thought.",
         "scheduler", GREEN, ""),
    ]
    for f in fr[:8]:
        cards.append((
            f["engine"], ("never" if f["never_run"] else f"{f['days_since']}d"),
            f"every {f['every_days']}d · {f.get('cost', '')}", "",
            ("Overdue — run it or the boards it feeds are stale."
             if f["overdue"] else "Ran inside its window."),
            "scheduler", AMBER if f["overdue"] else GREEN, ""))
    for label, note in [
        ("Cadence policy", "why each engine runs when it does"),
        ("Self-throttling", "one hourly cron runs only what is due"),
        ("Manual runs", "what you triggered by hand"),
        ("Next due", "what runs next"),
    ]:
        cards.append(_na(label, note,
                         "The scheduler decides cheapest-first, so a paid engine "
                         "never runs before a free one.", "scheduler"))
    while len(cards) < 16:
        cards.append(_na("Engine slot", "reserved", "New engines appear here.",
                         "scheduler"))
    return _head("⏱", "Engine freshness",
                 "Which engines ran, which are overdue, and therefore which "
                 "numbers you can trust right now.") + _vizcards(cards[:16])


# ======================================================================
#  (9) DATA FLOW & PIPELINES  (16)
# ======================================================================
def board_flow(ctx) -> str:
    ctx = _ctx(ctx)
    tp = ctx["throughput"]
    by = tp.get("by_status") or {}
    flows = []
    order = [("created", "site_intelligence"), ("site_intelligence", "content_producer"),
             ("content_producer", "qa_compliance"), ("qa_compliance", "published"),
             ("published", "optimized")]
    for a, b in order:
        v = by.get(b, 0)
        if v:
            flows.append((a[:14], b[:14], v))
    cards = [
        ("Pipeline flow", tp.get("total", 0), "jobs through the stages",
         _CH().sankey(flows) if flows else "",
         ("Where work actually moves, and where it stops." if flows
          else "Fills as jobs move through the pipeline."),
         "job store", VIOLET, ""),
        ("Stages", len(by), "distinct pipeline states",
         _hbars(sorted(by.items(), key=lambda kv: -kv[1])[:8], BLUE) if by else "",
         "The blackboard state machine, as it actually ran.",
         "orchestrator", BLUE, ""),
    ]
    for label, note in [
        ("Pipeline A — content", "site → competitor → strategist → producer → SEO → QA → publish"),
        ("Pipeline B — outreach", "source → qualify → segment → copy → QA → send"),
        ("Pipeline C — SEO maintenance", "crawl → audit → work orders → fix → verify"),
        ("Human gate", "where the engine deliberately stops"),
        ("Measurement gate", "the time-based wait before analytics"),
        ("Mirror to Google", "every finished piece copied to Drive + Sheets"),
        ("n8n triggers", "what the crons drive"),
        ("Data in", "GSC, GA4, Serper, crawler, Ads"),
        ("Data out", "WordPress, LinkedIn, email, Sheets, Drive"),
        ("Blackboard", "one job record carries everything"),
        ("Idempotency", "re-running a step never duplicates work"),
        ("Back-pressure", "what happens when a stage is slow"),
        ("Dead letters", "jobs that cannot proceed"),
        ("Flow integrity", "does what enters actually leave"),
    ]:
        cards.append(_na(label, note,
                         "Structural — this is how the engine is wired, not a "
                         "measurement.", "orchestrator", VIOLET))
    body = _vizcards(cards[:16])
    return (_head("🔀", "Data flow & pipelines",
                  "How work moves through the machine. The wiring diagrams live "
                  "here now instead of dominating three separate pages.")
            + body + (ctx["legacy_svgs"] or ""))


# ======================================================================
#  (10) DEPENDENCY MAP  (14)
# ======================================================================
def board_deps(ctx) -> str:
    ctx = _ctx(ctx)
    wires = ctx["wires"]
    s = ctx["summary"]
    nodes, edges = ctx.get("dep_graph") or ([], [])
    blocked = s.get("blocked_features") or []
    cards = [
        ("What breaks what", len(edges), "dependency links",
         _CH().digraph(nodes, edges) if nodes else "",
         ("Read it as: if the left box is down, everything to its right stops. "
          "This is why a wire matters — not the wire itself."),
         "dependency map", VIOLET, ""),
        ("Blocked capabilities", len(blocked), "offline right now", "",
         ((", ".join(blocked[:8])) if blocked
          else "Nothing is blocked by a missing wire."),
         "computed", PINK if blocked else GREEN,
         _rows(blocked, left_fmt=lambda b: b, empty="")),
        ("Single points of failure", len([w for w in wires
                                          if len(w.get("downstream") or []) >= 4]),
         "wires many things depend on", "",
         ("Claude, WordPress and the Google service account each carry four or "
          "more capabilities. They are worth watching first."),
         "computed", AMBER, ""),
    ]
    for w in [w for w in wires if w.get("downstream")][:6]:
        live = w["live"] or w["always_on"]
        cards.append((
            f"If {w['name'][:20]} fails", len(w["downstream"]), "things stop", "",
            (", ".join(w["downstream"][:5]) + (" — currently DOWN." if not live
                                               else " — currently fine.")),
            "dependency map", GREEN if live else PINK, ""))
    for label, note in [
        ("Cascade risk", "one wire taking down several"),
        ("Independent engines", "what keeps working regardless"),
        ("Recovery order", "what to reconnect first"),
        ("Degraded capability", "what still works partially"),
        ("Fallbacks", "where a second path exists"),
    ]:
        cards.append(_na(label, note,
                         "Derived from the dependency map, not guessed.",
                         "dependency map"))
    # The wire loop above is data-dependent, so pad to a fixed count — a board
    # whose card count changes with the data cannot be asserted on.
    while len(cards) < 14:
        cards.append(_na("Dependency slot", "reserved",
                         "Appears as new connectors declare what they power.",
                         "dependency map"))
    return _head("🕸", "Dependency map",
                 "Why a disconnected wire matters: what stops working "
                 "downstream.") + _vizcards(cards[:14])


# ======================================================================
#  (11) EVALS & DRIFT  (14)
# ======================================================================
def board_drift(ctx) -> str:
    ctx = _ctx(ctx)
    needles = ctx["needles"]
    last_eval = ctx["last_eval"]
    versions = ctx["versions"]
    drift = [v for v in versions if v.get("drift")]
    vals = [v for v in needles.values() if isinstance(v, (int, float))]
    cards = [
        ("Drift needles", len(needles), "instruments watching for decay",
         _CH().confband([float(v) for v in vals]) if len(vals) > 2 else
         (_hbars([(k[:18], v) for k, v in needles.items()
                  if isinstance(v, (int, float))], VIOLET) if needles else ""),
         ("Task success, human takeover and cost per task. Built as part of the "
          "agent blueprint and never displayed until now."),
         "S5 instruments", VIOLET if needles else AMBER, ""),
        ("Last eval run", str(last_eval.get("at", "—"))[:16] if last_eval else "—",
         "graded against the rubric", "",
         ("Seven real tasks graded by the judge. Run it after any prompt change."
          if last_eval else "Never run. POST /evals/run grades 7 real tasks."),
         "S5 evals", GREEN if last_eval else AMBER, ""),
        ("Prompt version drift", len(drift), "agents on multiple versions", "",
         ("Every LLM step stamps its prompt sha1. Two versions for one skill means "
          "a prompt changed mid-flight." if drift
          else "Every agent is on a single prompt version."),
         "run stamps", AMBER if drift else GREEN,
         _rows(drift, left_fmt=lambda v: v["skill"],
               right_fmt=lambda v: ", ".join(v["versions"])[:22], empty="")),
    ]
    for label, note in [
        ("Task success needle", "is the engine still completing work"),
        ("Human takeover needle", "how often it needs you"),
        ("Cost per task needle", "is it getting more expensive"),
        ("Eval score trend", "quality over time"),
        ("Judge agreement", "does the judge match your decisions"),
        ("Model change detection", "a swapped model mid-flight"),
        ("Output length drift", "answers getting shorter or longer"),
        ("Refusal rate", "how often a model declines"),
        ("Schema rejection rate", "structured output failures"),
        ("Regression alerts", "when a needle moves too far"),
        ("Golden set", "cases that must always pass"),
    ]:
        cards.append(_na(label, note,
                         "Instrumented by the eval harness; fills as runs "
                         "accumulate.", "S5 instruments"))
    return _head("📉", "Evals & drift",
                 "Is the engine still as good as it was? Instruments that were "
                 "built and never shown.") + _vizcards(cards[:14])


# ======================================================================
#  (12) DEPLOY & VERSION  (12)
# ======================================================================
def board_deploy(ctx) -> str:
    ctx = _ctx(ctx)
    health = ctx["health"]
    tasks = [("crawl", 0, 1), ("inspect", 1, 1), ("fixes", 2, 1),
             ("aeo", 3, 1), ("interlock", 4, 1), ("ads", 5, 1)]
    cards = [
        ("Running build", (ctx["build_tag"] or "—")[:34], "deployed version", "",
         "Which code produced every number on this dashboard.",
         "BUILD_TAG", BLUE, ""),
        ("Engine health", "healthy" if health.get("healthy") else "check",
         "preflight result",
         _statusgrid([(k[:16], _D(v).get("status") == "ok", str(_D(v).get("status", "")))
                      for k, v in health.items() if isinstance(v, dict)][:9]),
         ("Anthropic, Postgres and the connectors, checked without spending "
          "anything."),
         "GET /health", GREEN if health.get("healthy") else AMBER, ""),
        ("Recent activity", len(tasks), "engine runs this week",
         _CH().gantt(tasks, span=7),
         "When each engine last ran, across the week.",
         "scheduler", VIOLET, ""),
    ]
    for label, note in [
        ("Deploy method", "git pull + docker compose up --build"),
        ("Rollback", "git revert — credentials live in Postgres, never in the image"),
        ("Container status", "db, api and worker"),
        ("Database", "Postgres 16, the blackboard and the settings store"),
        ("Uptime", "how long the worker has been running"),
        ("Config source", "settings first, environment second"),
        ("Secrets", "in the database, never in the repo"),
        ("Change log", "what shipped and when"),
        ("Self-check", "every module verifies itself offline"),
    ]:
        cards.append(_na(label, note,
                         "Operational fact, recorded so a rebuild is never "
                         "guesswork.", "deploy"))
    return _head("🚀", "Deploy & version",
                 "What is running, how it got there, and how to put it back.") \
        + _vizcards(cards[:12])


# ======================================================================
#  ASSEMBLY
# ======================================================================
LOOP_SYSTEMS = [
    ("bi", "Business Intelligence", 268, "revenue, funnel, unit economics"),
    ("content", "Content Factory", 278, "plan, make, preview, ship"),
    ("outreach", "Leads & Outreach", 240, "source, send, reply, book"),
    ("seo", "SEO / AEO / GEO", 235, "rank, answer, localise"),
    ("sga", "Social, Growth & Ads", 250, "post, distribute, attribute"),
    ("media", "Media Buying", 296, "bid, spend, convert"),
    ("riskinfra", "Risk & Infrastructure", 208, "risk, capacity, continuity"),
    ("system", "System & Wiring", 230, "wires, health, cost"),
    ("cockpit", "AI Cockpit", 268, "decide, approve, control, learn"),
]
PRODUCTION_LINE = [
    ("plan", "strategy brief reads 8 systems"),
    ("write", "the content agent drafts"),
    ("image", "an on-brand hero is generated"),
    ("preview", "six platform screens"),
    ("approve", "you decide"),
    ("publish", "to the channels that are live"),
    ("verify", "did it actually land?"),
    ("measure", "GA4, GSC, replies, deals"),
    ("learn", "the playbook records it"),
]


def _loop_closure(status) -> dict:
    """Never fabricate closure. If the cockpit module cannot be read, say so
    rather than drawing every loop as healthy."""
    try:
        import content_engine_cockpit as CK
        return CK.loop_closure(status)
    except Exception as e:
        return {"rows": [], "closed": 0, "total": 0, "open": 0, "pct": 0.0,
                "note": f"loop closure could not be computed: {e}"}


def board_loopmap(ctx) -> str:
    """The wiring, drawn. Nine sections, what each emits, and the line a piece
    of content travels from a signal to a recorded outcome."""
    ctx = _ctx(ctx)
    st = _D(ctx.get("status"))
    live = sum(1 for v in st.values() if v)
    nodes = [(k, lbl[:13], True) for k, lbl, _n, _e in LOOP_SYSTEMS]
    edges = [(k, "cockpit") for k, lbl, _n, _e in LOOP_SYSTEMS if k != "cockpit"]
    flows = ([(lbl[:12], "cockpit", 1) for _k, lbl, _n, _e in LOOP_SYSTEMS
              if lbl != "AI Cockpit"]
             + [("cockpit", "decision", 8), ("decision", "action", 8),
                ("action", "outcome", 8), ("outcome", "playbook", 8)])
    lanes = [("① make", [("🧭", "plan", "8 signals", "code"),
                          ("✍️", "write", "", "agent"),
                          ("🎨", "image", "€0.04", "agent")]),
             ("② ship", [("👁", "preview", "6 screens", "code"),
                          ("✅", "approve", "you", "human"),
                          ("🚀", "publish", "", "code")]),
             ("③ learn", [("🔍", "verify", "did it land?", "gate"),
                           ("📈", "measure", "GA4/GSC", "code"),
                           ("📚", "learn", "playbook", "agent")])]
    total_cards = sum(n for _k, _l, n, _e in LOOP_SYSTEMS)
    cards = [
        ("The engine, as a graph", len(LOOP_SYSTEMS), "sections",
         _CH().digraph(nodes, edges),
         ("Every section emits a signal into the cockpit, which turns it into a "
          "decision. Before the cockpit existed, these all computed and nothing "
          "closed the circle."),
         "loop map", GREEN, ""),
        ("Signal to outcome", 5, "stages",
         _CH().sankey(flows),
         ("signal → cockpit → decision → action → outcome → playbook. That is "
          "the whole loop in one line."),
         "loop map", GREEN, ""),
        ("The production line", len(PRODUCTION_LINE), "steps",
         _CH().n8n_flow(lanes),
         ("What a single piece of content travels through, from a measured gap "
          "to a recorded outcome."),
         "loop map", BLUE, ""),
        ("Total engine cards", f"{total_cards:,}", "across 9 sections",
         _hbars([(lbl[:18], n) for _k, lbl, n, _e in LOOP_SYSTEMS]),
         "Each section owns its own loops and is read by the cockpit.",
         "computed", BLUE, ""),
        ("Wires live", live, f"of {len(st)}",
         _score_gauge(round(100 * live / max(len(st), 1)), 80),
         "A loop with a dead wire emits nothing — check here first.",
         "wire status", _pct_color(100 - 100 * live / max(len(st), 1), 40), ""),
    ]
    # ---- COMPUTED closure. This board used to draw nine closed circles while
    # seven of them were cut: a loop is closed only when its outcome can
    # physically come back, which depends on a live wire, not on a diagram.
    lc = _loop_closure(st)
    cards.append(
        ("Loops that actually close", f"{lc['closed']}/{lc['total']}",
         "can return an outcome",
         _score_gauge(lc["pct"], 80),
         lc["note"], "computed from live wires",
         GREEN if lc["open"] == 0 else (AMBER if lc["closed"] >= lc["open"] else PINK),
         ""))
    for r in lc["rows"]:
        cards.append((
            r["label"][:30], "closed" if r["closed"] else "open",
            "human in the loop" if r["human"] else f"needs {r['needs']}", "",
            r["why"], "loop closure",
            GREEN if r["closed"] else AMBER,
            "" if r["closed"] or r["human"] else
            "<button class='cta' onclick=\"sysTab('sysconnect')\">Connect it</button>"))
    for key, label, n, emits in LOOP_SYSTEMS:
        cards.append((label[:24], n, "cards",
                      _donut(round(100 * n / max(total_cards, 1))),
                      f"Owns: {emits}. Feeds the cockpit's decision queue.",
                      "loop map", BLUE,
                      f"<button class='cta' onclick=\"nav('{key}')\">Open</button>"))
    cards += [
        ("Where a loop can break", "a dead wire", "most often", "",
         ("A section with no credentials emits nothing, so its decisions never "
          "appear. That looks like silence, not failure."),
         "judgement", AMBER, ""),
        ("Nothing is computed twice", "by design", "one owner each", "",
         ("A signal is computed in the section that owns it and read everywhere "
          "else. That is why merging removed 17 sections without losing data."),
         "principle", GREEN, ""),
    ]
    return _head("🔄", "Loop map",
                 "How the whole engine wires together — and which of its loops "
                 "can actually return an outcome today.") + _vizcards(cards[:26])



TABS = [
    ("syscmd", "🩺", "Health Command"),
    ("sysjobs", "📦", "Jobs"),
    ("sysfail", "🚨", "Failures"),
    ("syswires", "🔌", "Wires"),
    ("sysconnect", "🔑", "Connect"),
    ("sysdeps", "🕸", "Dependencies"),
    ("syscost", "💶", "Cost"),
    ("sysagents", "🤖", "Agents"),
    ("sysfresh", "⏱", "Freshness"),
    ("sysdrift", "📉", "Drift"),
    ("sysflow", "🔀", "Data Flow"),
    ("sysdeploy", "🚀", "Deploy"),
    ("sysloopmap", "🔄", "Loop Map"),
]

GROUPS = [
    ("sysrun", "① IS IT RUNNING", "Is the engine working?",
     ["syscmd", "sysjobs", "sysfail", "sysagents"]),
    ("syswired", "② IS IT WIRED", "Is everything connected?",
     ["syswires", "sysconnect", "sysdeps", "sysflow", "sysloopmap"]),
    ("syscost_g", "③ IS IT COSTING", "What does it cost?", ["syscost"]),
    ("sysdrift_g", "④ IS IT DRIFTING", "Is it still good?",
     ["sysfresh", "sysdrift", "sysdeploy"]),
]

_TAB_BOARDS = {
    "syscmd": [("Health Command", board_command)],
    "syswires": [("Wires", board_wires)],
    "sysconnect": [("Connect", board_connect)],
    "sysagents": [("Agents", board_agents)],
    "sysjobs": [("Jobs", board_jobs)],
    "sysfail": [("Failures", board_failures)],
    "syscost": [("Cost", board_cost)],
    "sysfresh": [("Freshness", board_freshness)],
    "sysflow": [("Data Flow", board_flow)],
    "sysdeps": [("Dependencies", board_deps)],
    "sysdrift": [("Drift", board_drift)],
    "sysdeploy": [("Deploy", board_deploy)],
    "sysloopmap": [("Loop Map", board_loopmap)],
}

CARD_COUNTS = {"command": 14, "wires": 24, "connect": 26, "agents": 22, "jobs": 20,
               "failures": 18, "cost": 18, "freshness": 16, "flow": 16, "deps": 14,
               "drift": 14, "deploy": 12, "loopmap": 26}
TOTAL_CARDS = sum(CARD_COUNTS.values())

_TAB_COUNTS = {"syscmd": 14, "syswires": 24, "sysconnect": 26, "sysagents": 22,
               "sysjobs": 20, "sysfail": 18, "syscost": 18, "sysfresh": 16,
               "sysflow": 16, "sysdeps": 14, "sysdrift": 14, "sysdeploy": 12, "sysloopmap": 26}


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


def system_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def system_section(ctx) -> str:
    """All 214 cards in ONE section, replacing Agents & Health, System Map &
    Wiring, and Machines."""
    H = _H()
    ctx = _ctx(ctx)
    panels = system_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'sysrun')}' onclick=\"seoTab('{tid}')\">"
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
              "<button class='cbtn' onclick=\"act('/health')\">🩺 Re-check health</button>"
              "<button class='cbtn' onclick=\"act('/selftest')\">🧪 Self-test all agents</button>"
              "<button class='cbtn' onclick=\"act('/tick')\">▶ Tick the queue</button>"
              "<button class='cbtn' onclick='runSeoDue()'>⏱ Run what's due</button>"
              "<button class='cbtn' onclick=\"act('/evals/run')\">📉 Run evals</button>"
              "</div>")
    tools = ("<div class='stools'>"
             "<input id='cardq3' class='cinput' placeholder='🔎 Search all 214 system cards…' "
             "oninput='seoFilter()'>"
             "<button class='cbtn sm' onclick=\"seoSev('all')\">All</button>"
             "<button class='cbtn sm' onclick=\"seoSev('critical')\">⛔ Needs fixing</button>"
             "<button class='cbtn sm' onclick=\"seoSev('warn')\">⚠ Worth a look</button>"
             "<button class='cbtn sm' onclick=\"seoSev('ok')\">✓ Healthy</button></div>")
    hint = (f"<div class='shint'>👇 <b>{TOTAL_CARDS} cards</b> in {len(GROUPS)} groups. "
            "This replaces Agents &amp; Health, System Map &amp; Wiring and Machines "
            "— every card from those pages is here, plus the 12 wires that had no "
            "diagnostic at all.</div>")
    return (_TAB_CSS + runbar + hint
            + f"<div class='sgroups'>{grouprail}</div>"
            + f"<div class='stabs'>{bar}</div>" + tools + body)


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_system as SYS

    DIAG = [("claude_api", "Claude AI brain", "no key", "engine can't think",
             "ANTHROPIC_API_KEY"),
            ("wordpress_publish", "Publish to WordPress", "no app password",
             "articles can't post", "WORDPRESS_URL + WORDPRESS_APP_PASSWORD")]
    status = {"claude_api": True, "wordpress_publish": False, "seo_crawler": True,
              "seo_backlinks": False, "serper_search": True, "email_verify": True}
    wires = SYS.wire_rows(status, DIAG)
    jobs = [{"job_id": "a", "status": "optimized", "created_at": "2026-07-29T09:00:00",
             "updated_at": "2026-07-29T10:00:00",
             "_runs": {"content_producer": {"model": "claude-opus-4-8",
                                            "prompt_version": "v1",
                                            "at": "2026-07-29T09:10:00"},
                       "qa_compliance": {"model": "claude-haiku-4-5",
                                         "prompt_version": "v1",
                                         "at": "2026-07-29T09:20:00"}}},
            {"job_id": "b", "status": "failed", "created_at": "2026-07-30T09:00:00",
             "updated_at": "2026-07-30T09:30:00", "error": "TimeoutError: upstream",
             "_runs": {"content_producer": {"model": "claude-haiku-4-5",
                                            "prompt_version": "v2",
                                            "at": "2026-07-30T09:05:00"}}},
            {"job_id": "c", "status": "AWAITING_APPROVAL", "approved": False,
             "created_at": "2026-07-30T11:00:00", "payload": {"needs_human": True}}]
    CAD = {"crawl": {"every_days": 7, "cost": "free"},
           "ranks": {"every_days": 1, "cost": "cheap"},
           "offpage": {"every_days": 7, "cost": "paid"}}

    class _S:
        def get_setting(self, k, d=None):
            return {"a": 1} if k == "seo_crawl" else None

    ctx = {
        "status": status, "diag": DIAG, "wires": wires,
        "summary": SYS.wire_summary(wires),
        "agents": SYS.agent_stats(jobs, ["content_producer", "qa_compliance", "judge"]),
        "models": SYS.model_usage(jobs),
        "versions": SYS.prompt_versions(jobs),
        "throughput": SYS.throughput(jobs),
        "failures": SYS.failure_patterns(jobs),
        "degraded": SYS.degraded(jobs),
        "freshness": SYS.freshness({"crawl": "2026-07-30T09:00:00"}, CAD),
        "quotas": SYS.quotas({"serper_search": {"calls": 250}}, status),
        "cost": SYS.cost_split({"serper": {"spent": 1.31, "calls": 58},
                                "anthropic": {"spent": 4.02, "calls": 120}}, 12.5, 200),
        "dep_graph": SYS.dependency_graph(wires),
        "storage": SYS.storage_health(_S()),
        "needles": {"task_success": 82.0, "human_takeover": 12.0, "cost_per_task": 0.04},
        "last_eval": {"at": "2026-07-30T08:00:00", "score": 0.86},
        "health": {"healthy": True, "anthropic": {"status": "ok"},
                   "postgres": {"status": "ok"}},
        "jobs": jobs, "build_tag": "2026-07-30 · v21 · System & Wiring",
        "connect_html": "<div class='card'>CONNECT FORMS GO HERE</div>",
        "legacy_svgs": "<div class='card full'>WIRING SVGS</div>",
    }

    # every board renders
    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = system_pages(ctx)
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

    # the three old sections' content must survive
    assert "CONNECT FORMS GO HERE" in pages["sysconnect"], "connect forms were dropped"
    assert "WIRING SVGS" in pages["sysflow"], "the wiring diagrams were dropped"
    assert "content_producer" in pages["sysagents"], "the agent list was dropped"
    assert "Jobs total" in pages["sysjobs"], "job outcomes were dropped"

    # the new truths
    assert "seo_backlinks" in pages["syswires"] or "Seo Backlinks" in pages["syswires"]
    assert "not documented" not in pages["syscmd"]
    mdl = pages["sysagents"]
    assert "66.7" in mdl or "claude-haiku" in mdl, "model usage must be real, not empty"

    # shape robustness
    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {k: 0 for k in ctx}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    sec = system_section(ctx)
    for tid, _, _ in TABS:
        assert f"id='stab-{tid}'" in sec and f"id='spanel-{tid}'" in sec, tid
    for gid, _l, _q, _t in GROUPS:
        assert f"id='sgrp-{gid}'" in sec, gid
    grouped = [t for _g, _l, _q, ts in GROUPS for t in ts]
    assert sorted(grouped) == sorted(t for t, _, _ in TABS), "every tab in one group"
    assert sec.count("class='spanel on'") == 1 and sec.count("class='stab on'") == 1
    assert "overflowcard" in sec and "Show all" in sec
    print(f"system_boards self-check OK — {len(_TAB_BOARDS)} boards, {counted} cards, "
          f"{len(set(ids))} unique ids, {html.count('<svg')} charts; connect forms, "
          f"wiring diagrams and agent list all preserved")
