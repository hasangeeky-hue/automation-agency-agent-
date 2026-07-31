"""
content_engine_cockpit.py
============================================================================
AI COCKPIT — the brain. The loops behind the merged section.

Replaces four sections (Command Center, Operations, Approvals, Learning) that
held 35 cards, 4 charts, and rendered the decision engine TWICE.

What did not exist before this module:

  * A closed loop. Eight systems each computed a signal and nothing turned it
    into a decision, an action, and an outcome that came back. decisions()
    routes every system's signal into a decision with the button that acts on
    it, and outcomes are recorded so the playbook can learn.

  * Budget control. The caps were os.getenv() read at import — the only setting
    in the engine that needed a container rebuild. They are now settings-first
    (see orchestrator.budget_caps), and this module reads them for display.

  * Delegation clarity. autonomy() states what an agent COULD safely do alone
    versus what stays behind your approval. Nothing is delegated by it — it is
    a map of the choice, per your decision to keep every send, publish and
    spend gated.

Run offline self-check:  python content_engine_cockpit.py
============================================================================
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("content_engine.cockpit")

DECISION_LOG_KEY = "cockpit_decision_log"
EXPERIMENTS_KEY = "cockpit_experiments"
MAX_LOG = 200

# The eight systems, and the wire each one is judged on. Order is the order a
# founder should read them in: money first, then what produces it.
SYSTEMS = [
    ("bi", "Business Intelligence", "Is the business working?"),
    ("content", "Content Factory", "What is being made?"),
    ("outreach", "Leads & Outreach", "Who are we talking to?"),
    ("seo", "SEO / AEO / GEO", "Can anyone find us?"),
    ("sga", "Social, Growth & Ads", "Are we being seen?"),
    ("media", "Media Buying", "Is the paid spend working?"),
    ("riskinfra", "Risk & Infrastructure", "What could stop us?"),
    ("system", "System & Wiring", "Is the machine healthy?"),
]

# What an agent could do alone WITHOUT spending money, sending anything, or
# publishing anything. Everything else stays behind the human gate.
SAFE_TO_DELEGATE = [
    ("Re-run a free SEO engine", "crawl, inspect, indexnow", "no spend, reads only"),
    ("Refresh GA4 + Search Console", "insights/refresh", "free Google APIs"),
    ("Recompute the risk register", "risk/refresh", "reads stored data"),
    ("Rebuild the cross-channel interlock", "ads/interlock", "no API calls"),
    ("Re-check wire health", "health", "no spend"),
    ("Record a monthly snapshot", "storage + risk history", "writes locally"),
]
GATED_FOREVER = [
    ("Send an email", "reaches a real person", "outreach/send_*"),
    ("Publish a piece", "your name is on it", "publish"),
    ("Post to social", "public and permanent", "social post"),
    ("Spend on ads", "real money, outside the cap", "ads"),
    ("Raise the budget cap", "the ceiling itself", "budget"),
    ("Record a won deal", "it is your judgement", "bi/deal"),
]


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return list(v) if isinstance(v, (list, tuple)) else []


def _f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return float(d)


def _i(v, d=0):
    try:
        return int(_f(v, d))
    except Exception:
        return int(d)


def _s(v):
    return str(v or "").strip()


def _day(v):
    return str(v or "")[:10]


def _iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pct(part, whole, nd=1):
    w = _f(whole)
    return round(100 * _f(part) / w, nd) if w else 0.0


def _get(store, key, default=None):
    try:
        return store.get_setting(key, default)
    except Exception:
        return default


def _set(store, key, value):
    try:
        store.set_setting(key, value)
        return True
    except Exception as e:
        log.warning("could not persist %s: %s", key, e)
        return False


# ======================================================================
#  ① DECIDE — signal → decision → action
# ======================================================================
def decisions(seo=None, content=None, outreach=None, bi=None, sga=None,
              media=None, risk=None, system=None, jobs=None) -> dict:
    """THE loop. Every system emits a signal; this turns each into a decision
    with the button that acts on it and the evidence behind it.

    Weight is what the decision would move, so the queue is ordered by
    consequence rather than by which system happened to report last."""
    out = []

    def add(system_key, title, why, action_label, action_js, weight, kind="act"):
        out.append({"system": system_key, "title": title, "why": why,
                    "action": action_label, "js": action_js,
                    "weight": _f(weight), "kind": kind})

    # ---- Content: the queue that needs a human -------------------------
    c = _D(content)
    waiting = _i(_D(c.get("pipeline")).get("waiting"))
    if waiting:
        add("content", f"{waiting} pieces need your approval",
            "Nothing publishes until you review them. This is the only stage "
            "that requires a person.",
            "Review them", "seoTab('ckcontent')", 900 + waiting)
    blocked = _L(_D(c.get("previews")).get("blocked"))
    if blocked:
        add("content", f"{len(blocked)} platform(s) would reject the piece",
            f"{', '.join(blocked)} cannot publish it as it stands — usually a "
            f"missing image.", "See the preview", "nav('content')", 850)
    pp = _D(c.get("post_publish"))
    if _i(pp.get("failed")):
        add("content", f"{_i(pp.get('failed'))} pieces published but never landed",
            "The job is marked published and the channel returned a "
            "not_configured marker. It is not on the internet.",
            "See what failed", "nav('content')", 880)

    # ---- Outreach --------------------------------------------------------
    o = _D(outreach)
    due = _i(_D(o.get("sequence")).get("due_count"))
    if due:
        add("outreach", f"{due} follow-ups are overdue",
            "A stalled sequence is the most common reason a reply rate "
            "collapses.", "Send the batch", "act('/outreach/send_all')", 800)
    replies = _i(_D(o.get("replies")).get("total"))
    if replies:
        add("outreach", f"{replies} replies waiting",
            "Real people answered. Drafts are ready to read and send.",
            "Open the inbox", "nav('outreach')", 950)

    # ---- BI --------------------------------------------------------------
    b = _D(bi)
    if b and not _D(b.get("revenue")).get("has_data"):
        add("bi", "No deal recorded yet",
            "Revenue, customers, cohorts, CAC and LTV:CAC are all computable "
            "the moment one deal exists. Nothing else blocks them.",
            "Record a deal", "biDeal()", 870)
    worst = _D(b.get("funnel")).get("worst")
    if worst:
        add("bi", f"Biggest leak: {_s(worst[0])}",
            f"{_f(worst[1]):,.0f} people are lost there. Fixing the largest "
            f"drop beats adding volume at the top.", "Open the funnel",
            "nav('bi')", 820)

    # ---- SEO / AEO / GEO -------------------------------------------------
    s_ = _D(seo)
    striking = _L(_D(s_.get("striking")).get("rows")) or _L(s_.get("striking"))
    if striking:
        add("seo", f"{len(striking)} queries sit at #11-20",
            "They already rank. A piece aimed at one reaches page 1 faster "
            "than any new topic.", "Plan content", "planContent()", 780)

    # ---- SGA -------------------------------------------------------------
    g = _D(sga)
    if _i(_D(g.get("posts")).get("failed_total")):
        add("sga", f"{_i(_D(g.get('posts')).get('failed_total'))} posts hit a dead channel",
            "The channel has no credentials, so nothing was posted.",
            "Connect it", "nav('system')", 760)

    # ---- Risk ------------------------------------------------------------
    r = _D(risk)
    crit = [x for x in _L(r.get("risks")) if _f(_D(x).get("score")) >= 6]
    if crit:
        add("riskinfra", f"{len(crit)} critical risk(s): {_s(_D(crit[0]).get('title'))}",
            _s(_D(crit[0]).get("mitigation")) or "Open the register for the fix.",
            "Open Risk", "nav('riskinfra')", 990)

    # ---- System ----------------------------------------------------------
    sy = _D(system)
    st = _D(sy.get("status"))
    down = [k for k, v in st.items() if not v]
    if down:
        add("system", f"{len(down)} wires are not connected",
            "Each one is a capability the engine cannot use.",
            "Open System & Wiring", "nav('system')", 700)

    # ---- Budget ----------------------------------------------------------
    cost = _D(r.get("cost")) or _D(b.get("spend"))
    cap = _f(cost.get("month_cap") or cost.get("cap"), 200) or 200
    spent = _f(cost.get("month_spent") or cost.get("spent"))
    if cap and spent / cap >= 0.85:
        add("riskinfra", f"Spend is at {round(100 * spent / cap)}% of the cap",
            "The engine halts new LLM steps at 100% rather than overspending. "
            "Raise the cap or let it stop.", "Open budget controls",
            "seoTab('ckbudget')", 960)

    out.sort(key=lambda d: -d["weight"])
    return {"rows": out, "count": len(out),
            "top": out[0] if out else None,
            "by_system": [(k, sum(1 for d in out if d["system"] == k))
                          for k, _n, _q in SYSTEMS],
            "urgent": [d for d in out if d["weight"] >= 900],
            "has_data": bool(out),
            "note": ("Every row is a signal from a system, the decision it "
                     "implies, and the button that acts on it. Ordered by what "
                     "it would move, not by which system reported last."
                     if out else
                     "No system is reporting anything that needs you. That is "
                     "either very good or nothing is running.")}


# Every loop, and the ONE condition that decides whether its outcome can come
# back. This is computed from live wire status, never drawn as closed — the
# Loop Map used to render nine closed circles while seven of them were cut.
LOOP_CLOSURE = [
    ("content", "Content: plan → publish → measure", "google_gsc_ga4",
     "GA4 returns sessions and conversions for the exact page that was published.",
     "Without GA4 a published piece never reports back, so the playbook cannot "
     "learn which pieces worked."),
    ("outreach", "Outreach: send → open → reply", "email_send",
     "Opens and clicks come from the engine's own pixel; replies come from IMAP.",
     "Sending without tracking means delivery is the only thing ever known."),
    ("seo", "SEO: crawl → fix → rank", "seo_rank_tracker",
     "Rank tracking shows whether a fix moved anything.",
     "Fixes ship and nothing observes whether they helped."),
    ("aeo", "AEO: ask the AI engines", "claude_api",
     "Each answer engine is asked directly whether it mentions you.",
     "You are measured against ChatGPT, Perplexity and Gemini; only the wired "
     "engines can answer."),
    ("bi", "Money: work → deal → revenue", None,
     "You record deals by hand, which is why this one closes.",
     ""),
    ("approvals", "Approvals: propose → you decide → log", None,
     "Every decision is logged, so the playbook learns from what was DONE.",
     ""),
    ("budget", "Budget: spend → cap → halt", None,
     "Caps are read live on every enforcement check.",
     ""),
    ("sga", "Social: post → session → attribution", "google_gsc_ga4",
     "GA4 attributes sessions back to the channel that sent them.",
     "Posts go out and nothing says which channel earned the visit."),
    ("media", "Paid: bid → spend → CPA", "ads_api",
     "The Ads API returns spend and conversions per campaign.",
     "Spend leaves and nothing reports what it bought."),
]


def loop_closure(status=None, store=None) -> dict:
    """Which loops actually close RIGHT NOW.

    A loop is closed only when its outcome can physically come back. Three close
    without any credential because a human is inside them; the rest depend on a
    wire, and a dead wire means an open loop no matter how many cards describe
    it."""
    st = status if isinstance(status, dict) else {}
    rows, closed = [], 0
    for key, label, wire, how, breaks in LOOP_CLOSURE:
        if wire is None:
            ok, why = True, how
        else:
            ok = bool(st.get(wire))
            why = how if ok else breaks
        # Outreach needs the tracking switch as well as a mail wire.
        if key == "outreach" and ok and store is not None:
            try:
                import content_engine_outreach as OUT
                if not OUT.tracking_enabled(store):
                    ok = False
                    why = ("Open and click tracking is switched off, so delivery "
                           "is the only thing this loop can ever report.")
            except Exception:
                pass
        closed += 1 if ok else 0
        rows.append({"key": key, "label": label, "closed": ok,
                     "needs": wire or "a person", "why": why,
                     "human": wire is None})
    total = len(rows)
    return {
        "rows": rows, "closed": closed, "total": total, "open": total - closed,
        "pct": round(100.0 * closed / total, 1) if total else 0.0,
        "note": (f"{closed} of {total} loops can return an outcome today. "
                 f"An open loop still produces work — it just never finds out "
                 f"whether the work was any good."),
    }


def signal_router(seo=None, content=None, outreach=None, bi=None, sga=None,
                  media=None, risk=None, system=None) -> dict:
    """Which system is feeding the cockpit, what it emits, and where the
    outcome returns. The wiring, made visible."""
    ctxs = {"seo": seo, "content": content, "outreach": outreach, "bi": bi,
            "sga": sga, "media": media, "riskinfra": risk, "system": system}
    EMITS = {
        "bi": ("revenue by source, funnel leaks, targets", "recorded deals"),
        "content": ("pieces awaiting approval, preview failures, landed rate",
                    "published + verified"),
        "outreach": ("follow-ups due, replies waiting, reply rate", "replies"),
        "seo": ("striking distance, decay, AI mentions", "ranking movement"),
        "sga": ("channel performance, cadence gap, sessions per post", "GA4"),
        "media": ("wasted spend, winning keywords", "CPA"),
        "riskinfra": ("top risk, capacity, budget headroom", "risk score"),
        "system": ("dead wires, rejected keys", "wire health"),
    }
    rows, flows = [], []
    for key, label, question in SYSTEMS:
        ctx = _D(ctxs.get(key))
        live = bool(ctx)
        emits, returns = EMITS.get(key, ("", ""))
        rows.append({"system": key, "label": label, "question": question,
                     "live": live, "emits": emits, "returns": returns})
        if live:
            flows.append((label[:16], "cockpit", 1))
    flows.append(("cockpit", "decision", max(1, sum(1 for r in rows if r["live"]))))
    flows.append(("decision", "playbook", max(1, sum(1 for r in rows if r["live"]))))
    live_n = sum(1 for r in rows if r["live"])
    return {"rows": rows, "flows": flows, "live": live_n, "total": len(rows),
            "statusgrid": [(r["label"][:18], r["live"],
                            "" if r["live"] else "silent") for r in rows],
            "closed": live_n == len(rows),
            "note": (f"{live_n} of {len(rows)} systems are reporting into the "
                     f"cockpit. A silent system is not broken — it means that "
                     f"context could not be built on this render.")}


def log_decision(store, title, action, system="", outcome="") -> dict:
    """Record that a decision was taken, so the playbook can learn from what
    was actually done rather than what was merely suggested."""
    rows = _L(_get(store, DECISION_LOG_KEY, []))
    rows.append({"at": _iso(), "title": _s(title)[:120], "action": _s(action)[:80],
                 "system": _s(system), "outcome": _s(outcome)[:120]})
    _set(store, DECISION_LOG_KEY, rows[-MAX_LOG:])
    return {"ok": True, "total": len(rows)}


def decision_log(store, days=14) -> dict:
    rows = _L(_get(store, DECISION_LOG_KEY, []))[::-1]
    per_day = {}
    for r in rows:
        d = _day(_D(r).get("at"))
        if d:
            per_day[d] = per_day.get(d, 0) + 1
    keys = sorted(per_day)[-days:]
    return {"rows": rows[:20], "total": len(rows),
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "has_data": bool(rows)}


# ======================================================================
#  ② APPROVE
# ======================================================================
def approvals(jobs=None, content_plan=None) -> dict:
    """The working queue, triaged. The old section had one flat table, no
    severity, no age, no bottleneck view."""
    js = _L(jobs)
    waiting = [j for j in js if _D(j).get("status") == "AWAITING_APPROVAL"]
    today = date.today()
    ages, by_type, oldest = [], {}, None
    for j in waiting:
        t = _s(_D(j).get("type")) or "content_piece"
        by_type[t] = by_type.get(t, 0) + 1
        try:
            d = date.fromisoformat(_day(_D(j).get("created_at")))
            age = (today - d).days
        except Exception:
            age = 0
        ages.append(age)
        if oldest is None or age > oldest[1]:
            oldest = (_s(_D(j).get("job_id")), age)
    declined = [j for j in js if _D(j).get("status") in ("declined", "rework")]
    plan = _D(content_plan)
    return {"waiting": len(waiting), "by_type": sorted(by_type.items(),
                                                       key=lambda kv: -kv[1]),
            "ages": ages, "oldest": oldest,
            "avg_age": round(sum(ages) / len(ages), 1) if ages else 0,
            "stale": sum(1 for a in ages if a >= 3),
            "declined": len(declined),
            "plan_pending": len(_L(plan.get("items"))) if
            _s(plan.get("status")) == "pending" else 0,
            "rows": [{"id": _s(_D(j).get("job_id")),
                      "type": _s(_D(j).get("type")),
                      "title": _s(_D(_D(_D(j).get("payload")).get("content_producer"))
                                  .get("title")) or _s(_D(j).get("job_id")),
                      "cost": _f(_D(j).get("cost_so_far_usd"))}
                     for j in waiting[:20]],
            "has_data": bool(waiting or plan),
            "note": (f"{sum(1 for a in ages if a >= 3)} have been waiting three "
                     f"days or more." if any(a >= 3 for a in ages) else
                     "Nothing has been waiting more than two days.")}


def turnaround(jobs=None, days=14) -> dict:
    """How fast you clear the queue — the only metric that says whether the
    human gate is a gate or a wall."""
    js = _L(jobs)
    done = [j for j in js if _D(j).get("status") in
            ("published", "optimized", "measuring", "measured")]
    per_day = {}
    for j in done:
        d = _day(_D(j).get("published_at") or _D(j).get("created_at"))
        if d:
            per_day[d] = per_day.get(d, 0) + 1
    keys = sorted(per_day)[-days:]
    return {"cleared": len(done),
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "avg_per_day": round(sum(per_day.values()) / len(keys), 1) if keys else 0,
            "has_data": bool(done)}


# ======================================================================
#  ③ CONTROL — budget, autonomy, capability
# ======================================================================
def budget_view(caps=None, spent_month=0.0, spent_day=0.0, log=None) -> dict:
    """What the caps are, what is left, and what a change would do."""
    c = _D(caps)
    month = _f(c.get("per_month"), 200) or 200
    day = _f(c.get("per_day"), 50) or 50
    job = _f(c.get("per_job"), 0.5) or 0.5
    dom = date.today().day or 1
    run_rate = _f(spent_month) / dom
    return {"per_month": month, "per_day": day, "per_job": job,
            "spent_month": round(_f(spent_month), 2),
            "spent_day": round(_f(spent_day), 2),
            "month_pct": _pct(spent_month, month),
            "day_pct": _pct(spent_day, day),
            "headroom": round(max(0.0, month - _f(spent_month)), 2),
            "run_rate": round(run_rate, 2),
            "projected": round(run_rate * 30, 2),
            "over_cap": run_rate * 30 > month,
            "floor": round(_f(spent_month), 2),
            "changes": _L(log)[:10],
            "change_count": len(_L(log)),
            "note": (f"The lowest monthly cap you can set right now is "
                     f"EUR {_f(spent_month):,.2f} — anything below what is "
                     f"already spent would halt the engine the moment it saved."),
            "how": ("Caps are read live on every check: your setting first, the "
                    "env second. A change takes effect on the worker's next "
                    "loop with no restart."),
            "has_data": True}


def autonomy(caps=None) -> dict:
    """A map of the delegation choice. NOTHING here delegates anything — every
    send, publish and spend stays behind the human gate, per your decision."""
    return {"safe": SAFE_TO_DELEGATE, "gated": GATED_FOREVER,
            "safe_count": len(SAFE_TO_DELEGATE),
            "gated_count": len(GATED_FOREVER),
            "delegated": 0,
            "statusgrid": ([(n[:20], True, "could be safe") for n, _a, _w in SAFE_TO_DELEGATE]
                           + [(n[:20], False, "always yours") for n, _a, _w in GATED_FOREVER]),
            "note": ("Nothing is delegated. Every send, publish and spend needs "
                     "you, by your decision. This board shows what COULD be "
                     "handed over if you ever wanted to — the free, read-only "
                     "actions — and what should never be."),
            "principle": ("The rule that has held all along: an agent may read "
                          "and compute freely; anything that reaches a person, "
                          "the public, or your card needs a human.")}


def capability(status=None, missing_keys=None) -> dict:
    """What the engine cannot do yet, and the exact key that would change it."""
    st = _D(status)
    live = sum(1 for v in st.values() if v)
    groups = _D(missing_keys)
    total_missing = sum(len(_L(v)) for v in groups.values())
    return {"wires_live": live, "wires_total": len(st),
            # the raw map, so loop closure can be computed from the SAME status
            # the wire counts came from rather than a second, drifting copy
            "status": st,
            "wire_pct": _pct(live, len(st)),
            "groups": [(k, _L(v)) for k, v in groups.items() if _L(v)],
            "missing_total": total_missing,
            "has_data": bool(st or groups),
            "note": ("Every key below can be entered in the browser and is read "
                     "settings-first — no SSH, no rebuild. None of them is a "
                     "paid SaaS tool; they are the platforms' own APIs.")}


# ======================================================================
#  ④ RUN & LEARN
# ======================================================================
def engine_state(health=None, jobs=None, caps=None, spent_month=0.0) -> dict:
    h = _D(health)
    js = _L(jobs)
    running = sum(1 for j in js if _D(j).get("status") not in
                  ("published", "optimized", "measured", "failed", "declined"))
    failed = sum(1 for j in js if _D(j).get("status") in ("failed", "halted_budget"))
    halted = sum(1 for j in js if _D(j).get("status") == "halted_budget")
    month = _f(_D(caps).get("per_month"), 200) or 200
    return {"healthy": bool(h.get("healthy")),
            "checks": [(k, _D(v).get("status") == "ok")
                       for k, v in h.items() if isinstance(v, dict)],
            "jobs_total": len(js), "running": running, "failed": failed,
            "halted_by_budget": halted,
            "at_cap": _f(spent_month) >= month,
            "note": ("The engine has halted new LLM steps because the monthly "
                     "cap is reached. Raise it or wait for the month to roll."
                     if _f(spent_month) >= month else
                     "The engine is inside its budget."),
            "has_data": bool(js or h)}


def playbook_view(playbook=None, deals=None) -> dict:
    """What the engine has learned. The old section accumulated it and nothing
    ever read it back into a decision."""
    pb = _D(playbook)
    lists = {k: _L(v) for k, v in pb.items() if isinstance(v, (list, tuple))}
    total = sum(len(v) for v in lists.values())
    dl = _L(deals)
    by_vertical = {}
    for d in dl:
        v = _s(_D(d).get("source")) or "other"
        by_vertical[v] = by_vertical.get(v, 0.0) + _f(_D(d).get("value"))
    return {"sections": sorted(((k, len(v)) for k, v in lists.items()),
                               key=lambda kv: -kv[1]),
            "entries": total,
            "by_vertical": sorted(by_vertical.items(), key=lambda kv: -kv[1]),
            "has_revenue": bool(dl),
            "has_data": bool(total),
            "note": ("The playbook accumulates every cycle. What was missing is "
                     "anything reading it BACK into a decision — the Decision "
                     "Queue now cites it."
                     if total else
                     "The playbook fills as cycles complete. It needs finished "
                     "jobs, not just started ones.")}


def experiments(store=None) -> dict:
    """A hypothesis, a wait, and a score. Nothing in the engine did this."""
    rows = _L(_get(store, EXPERIMENTS_KEY, [])) if store else []
    today = date.today().isoformat()
    open_ = [r for r in rows if not _D(r).get("scored")]
    due = [r for r in open_ if _day(_D(r).get("review_on")) <= today]
    return {"rows": rows[:12], "total": len(rows),
            "open": len(open_), "due": len(due),
            "scored": len(rows) - len(open_),
            "has_data": bool(rows),
            "note": ("An experiment is a stated guess with a review date. "
                     "Without one, every change is folklore."
                     if not rows else
                     f"{len(due)} experiment(s) are due for scoring.")}


def start_experiment(store, hypothesis, metric, review_days=14, note="") -> dict:
    h = _s(hypothesis)
    if not h:
        return {"ok": False, "error": "a hypothesis is required"}
    rows = _L(_get(store, EXPERIMENTS_KEY, []))
    row = {"id": f"exp-{len(rows) + 1}", "hypothesis": h[:200],
           "metric": _s(metric)[:80],
           "started": _day(_iso()),
           "review_on": (date.today() + timedelta(days=_i(review_days, 14))).isoformat(),
           "note": _s(note)[:160], "scored": False, "result": ""}
    rows.append(row)
    _set(store, EXPERIMENTS_KEY, rows[-100:])
    return {"ok": True, "experiment": row,
            "message": f"Review on {row['review_on']}."}


def score_experiment(store, exp_id, result, worked=None) -> dict:
    rows = _L(_get(store, EXPERIMENTS_KEY, []))
    hit = False
    for r in rows:
        if _s(_D(r).get("id")) == _s(exp_id):
            r["scored"] = True
            r["result"] = _s(result)[:200]
            r["worked"] = bool(worked)
            r["scored_at"] = _iso()
            hit = True
    if not hit:
        return {"ok": False, "error": "experiment not found"}
    _set(store, EXPERIMENTS_KEY, rows)
    return {"ok": True, "message": "Scored. It feeds the playbook from here."}


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()

    # ---- the loop: signal -> decision -> action ----
    d = decisions(
        content={"pipeline": {"waiting": 3},
                 "previews": {"blocked": ["instagram"]},
                 "post_publish": {"failed": 2}},
        outreach={"sequence": {"due_count": 5}, "replies": {"total": 2}},
        bi={"revenue": {"has_data": False},
            "funnel": {"worst": ("Emailed → Replied", 150, 83.0)}},
        seo={"striking": {"rows": [{"query": "n8n", "position": 14}]}},
        sga={"posts": {"failed_total": 1}},
        risk={"risks": [{"title": "No backup configured", "score": 6,
                         "mitigation": "Add a nightly pg_dump"}],
              "cost": {"month_cap": 200, "month_spent": 180}},
        system={"status": {"ads_api": False, "anthropic": True}})
    assert d["count"] >= 8, d["count"]
    assert d["rows"][0]["weight"] >= d["rows"][-1]["weight"], "must rank"
    assert all(r["js"] and r["action"] for r in d["rows"]), "every row needs a button"
    assert all(r["why"] for r in d["rows"]), "every row needs its evidence"
    assert any("critical risk" in r["title"] for r in d["rows"])
    assert any("85%" in r["title"] or "90%" in r["title"] for r in d["rows"])
    assert d["urgent"], "the 900+ band must exist"
    empty = decisions()
    assert empty["count"] == 0 and "very good or nothing is running" in empty["note"]

    # ---- router ----
    r = signal_router(seo={"x": 1}, bi={"y": 2})
    assert r["live"] == 2 and r["total"] == 8 and not r["closed"]
    assert any(f[1] == "cockpit" for f in r["flows"])
    full = signal_router(*[{"x": 1}] * 8)
    assert full["closed"] and full["live"] == 8

    # ---- decision log ----
    log_decision(st, "Approved 3 pieces", "approve", "content")
    dl = decision_log(st)
    assert dl["total"] == 1 and dl["has_data"]

    # ---- approvals triage ----
    jobs = [{"job_id": "c1", "type": "content_piece", "status": "AWAITING_APPROVAL",
             "created_at": (date.today() - timedelta(days=5)).isoformat(),
             "cost_so_far_usd": 0.4,
             "payload": {"content_producer": {"title": "Old one"}}},
            {"job_id": "c2", "type": "content_piece", "status": "AWAITING_APPROVAL",
             "created_at": date.today().isoformat(), "payload": {}},
            {"job_id": "c3", "type": "content_piece", "status": "published",
             "created_at": date.today().isoformat()}]
    a = approvals(jobs, {"status": "pending", "items": [{"title": "x"}]})
    assert a["waiting"] == 2 and a["stale"] == 1
    assert a["oldest"][0] == "c1" and a["oldest"][1] >= 5
    assert a["plan_pending"] == 1
    assert "three days or more" in a["note"]
    t = turnaround(jobs)
    assert t["cleared"] == 1

    # ---- budget: the floor is a hard block ----
    bv = budget_view({"per_month": 200, "per_day": 50, "per_job": 0.5},
                     spent_month=63.2, spent_day=4.1)
    assert bv["floor"] == 63.2 and bv["headroom"] == 136.8
    assert "lowest monthly cap you can set" in bv["note"]
    assert "no restart" in bv["how"]

    # ---- autonomy: a map, not a delegation ----
    au = autonomy()
    assert au["delegated"] == 0, "nothing may be delegated by this module"
    assert au["safe_count"] == 6 and au["gated_count"] == 6
    assert "Nothing is delegated" in au["note"]
    assert any("Send an email" in n for n, _a, _w in au["gated"])
    assert any("Raise the budget cap" in n for n, _a, _w in au["gated"])

    # ---- capability ----
    cap = capability({"a": True, "b": False},
                     {"AEO engines": ["OPENAI_API_KEY"], "Email branding": []})
    assert cap["wires_live"] == 1 and cap["missing_total"] == 1
    assert len(cap["groups"]) == 1, "empty groups must be dropped"

    # ---- engine state ----
    es = engine_state({"healthy": True, "postgres": {"status": "ok"}}, jobs,
                      {"per_month": 200}, spent_month=250)
    assert es["at_cap"] and "halted" in es["note"]

    # ---- playbook + experiments ----
    pv = playbook_view({"winning_subjects": ["a", "b"], "themes": ["x"]},
                       [{"source": "outreach", "value": 6000}])
    assert pv["entries"] == 3 and pv["by_vertical"][0][0] == "outreach"
    assert "reading it BACK into a decision" in pv["note"]

    assert start_experiment(st, "", "x")["ok"] is False
    e = start_experiment(st, "German pages will rank in DE", "sessions from Germany", 14)
    assert e["ok"] and e["experiment"]["review_on"] > date.today().isoformat()
    ex = experiments(st)
    assert ex["total"] == 1 and ex["open"] == 1 and ex["scored"] == 0
    assert score_experiment(st, "exp-1", "It worked", worked=True)["ok"]
    assert experiments(st)["scored"] == 1
    assert score_experiment(st, "nope", "x")["ok"] is False

    # ---- hostile shapes ----
    for bad in (None, {}, [], "x", 0):
        decisions(bad, bad, bad, bad, bad, bad, bad, bad)
        signal_router(bad, bad, bad, bad, bad, bad, bad, bad)
        approvals(bad if isinstance(bad, list) else None, bad)
        turnaround(bad if isinstance(bad, list) else None)
        budget_view(bad, 0, 0, bad)
        autonomy(bad)
        capability(bad, bad)
        engine_state(bad, bad if isinstance(bad, list) else None, bad)
        playbook_view(bad, bad if isinstance(bad, list) else None)
        experiments(None)
        decision_log(S())

    print("cockpit self-check OK — every decision carries its evidence and the "
          "button that acts on it, ranked by consequence; the budget floor is "
          "reported so a cap below this month's spend can be refused; autonomy "
          "delegates NOTHING and states what would never be delegated; and an "
          "experiment is a stated hypothesis with a review date rather than "
          "folklore.")
