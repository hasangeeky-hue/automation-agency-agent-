"""
content_engine_system.py
============================================================================
S1-S18 — THE SYSTEM & WIRING DATA LAYER.

Health used to be binary: a wire was live or it wasn't. This turns the data the
engine ALREADY records into the answers an operator actually needs:

    wire_rows()        S6  all 30 wires, each with severity + what it breaks
    agent_stats()      S3  per-skill runs, success rate, model, prompt version
    model_usage()      S13 Haiku vs Opus split, from the _runs stamps
    prompt_versions()  S16 version drift per skill
    throughput()       S2  jobs/day, queue depth, stage distribution
    failure_patterns() S4  error type x day - a diagnosis, not a list
    degraded()         S5  needs-human backlog
    freshness()        S14 which engines ran, which are overdue
    quotas()           S11 headroom against each API's real ceiling
    cost_split()       S10/S12 spend per API, per agent, vs the cap
    dependency_edges() S8  what breaks what, downstream
    storage_health()   S17 Postgres + settings-row size

Pure functions over data already in the store. No network, no new credentials.

Run offline self-check:  python content_engine_system.py
============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("system")

# Real ceilings, so "headroom" means something.
QUOTAS = {
    "google_gsc_ga4": ("URL Inspection", 2000, "per day, free"),
    "seo_index_inspect": ("URL Inspection", 2000, "per day, free"),
    "seo_pagespeed": ("PageSpeed", 25000, "per day with a key; heavily limited without"),
    "serper_search": ("Serper credits", 2500, "per month on the usual plan"),
    "claude_api": ("Anthropic", 0, "no hard call cap - the €200 budget is the ceiling"),
}

# S8 - what breaks what. Read as: if the KEY is down, the VALUES stop working.
DEPENDS = {
    "claude_api": ["content", "outreach", "replies", "judge", "aeo", "seo_fixer"],
    "wordpress_publish": ["publish", "seo_fixes", "schema", "internal_links"],
    "email_send": ["outreach", "replies", "link_pitches"],
    "email_reply_inbound": ["replies", "reply_agent"],
    "google_gsc_ga4": ["seo_keywords", "seo_decay", "indexing", "interlock", "geo_markets"],
    "serper_search": ["rank_tracker", "competitors", "aeo_google", "prospecting", "maps_leads"],
    "seo_crawler": ["on_page", "technical", "internal_links", "landing_pages", "llms_txt"],
    "seo_backlinks": ["off_page", "link_gap"],
    "ads_api": ["media_buying", "search_terms", "quality_score", "bidding", "pacing"],
    "calcom_bookings": ["bookings", "blended_cac", "offline_conversions"],
    "google_sheets": ["mirror"],
    "google_drive": ["mirror"],
}


def _now():
    return datetime.now(timezone.utc)


def _days_since(iso) -> float:
    if not iso:
        return 1e9
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (_now() - t).total_seconds() / 86400.0
    except Exception:
        return 1e9


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, (list, tuple)) else []


# ======================================================================
#  S6 - WIRES
# ======================================================================
ALWAYS_ON = {"seo_crawler", "email_verify", "requests_installed"}


def wire_rows(status: dict, diag: list) -> list:
    """Every wire in status(), joined to its diagnostic. A wire with no _DIAG
    entry used to be invisible — now it is listed as undocumented rather than
    silently absent."""
    status = _D(status)
    by_key = {d[0]: d for d in _L(diag) if d}
    rows = []
    for key, live in sorted(status.items()):
        d = by_key.get(key)
        always = key in ALWAYS_ON
        rows.append({
            "key": key,
            "name": (d[1] if d else key.replace("_", " ").title()),
            "live": bool(live),
            "always_on": always,
            "why": ("" if live else (d[2] if d else "no credential documented")),
            "breaks": (d[3] if d else "not documented"),
            "fix": (d[4] if d else ""),
            "documented": bool(d),
            "severity": ("ok" if (live or always) else
                         "critical" if key in ("claude_api",) else
                         "warn"),
            "downstream": DEPENDS.get(key, []),
        })
    return rows


def wire_summary(rows: list) -> dict:
    rows = _L(rows)
    live = [r for r in rows if r["live"] or r["always_on"]]
    down = [r for r in rows if not (r["live"] or r["always_on"])]
    return {"total": len(rows), "live": len(live), "down": len(down),
            "pct": round(100 * len(live) / max(len(rows), 1)),
            "undocumented": [r["key"] for r in rows if not r["documented"]],
            "critical_down": [r for r in down if r["severity"] == "critical"],
            "blocked_features": sorted({f for r in down for f in r["downstream"]})}


# ======================================================================
#  S3 / S13 / S16 - AGENTS, MODELS, PROMPT VERSIONS
# ======================================================================
def agent_stats(jobs: list, skills: list = None) -> list:
    """Per-skill run counts and success, read from the _runs stamps the
    orchestrator already writes on every LLM step."""
    runs, fails = {}, {}
    for j in _L(jobs):
        for skill, stamp in _D(j.get("_runs")).items():
            r = runs.setdefault(skill, {"skill": skill, "runs": 0, "models": {},
                                        "versions": set(), "last": ""})
            r["runs"] += 1
            m = _D(stamp).get("model", "?")
            r["models"][m] = r["models"].get(m, 0) + 1
            v = _D(stamp).get("prompt_version")
            if v:
                r["versions"].add(v)
            at = _D(stamp).get("at", "")
            if at > r["last"]:
                r["last"] = at
        if j.get("status") in ("failed", "halted_budget"):
            last = list(_D(j.get("_runs")).keys())
            if last:
                fails[last[-1]] = fails.get(last[-1], 0) + 1
    out = []
    for skill in (skills or sorted(runs)):
        r = runs.get(skill, {"skill": skill, "runs": 0, "models": {},
                             "versions": set(), "last": ""})
        f = fails.get(skill, 0)
        out.append({"skill": skill, "runs": r["runs"], "failures": f,
                    "success_pct": round(100 * (r["runs"] - f) / r["runs"], 1)
                    if r["runs"] else None,
                    "models": r["models"], "versions": sorted(r["versions"]),
                    "version_drift": len(r["versions"]) > 1,
                    "last_run": r["last"],
                    "never_run": r["runs"] == 0})
    return out


def model_usage(jobs: list) -> dict:
    """S13 — which model actually ran. The card for this was a hardcoded empty
    string; the data was being recorded the whole time."""
    counts = {}
    for j in _L(jobs):
        for _skill, stamp in _D(j.get("_runs")).items():
            m = _D(stamp).get("model", "?")
            counts[m] = counts.get(m, 0) + 1
    total = sum(counts.values())
    cheap = sum(v for k, v in counts.items() if "haiku" in str(k).lower())
    return {"counts": counts, "total": total,
            "cheap_pct": round(100 * cheap / total, 1) if total else 0,
            "frontier_pct": round(100 * (total - cheap) / total, 1) if total else 0}


def prompt_versions(jobs: list) -> list:
    """S16 — a prompt changing silently on Tuesday is a debugging ghost on
    Wednesday. These stamps exist to prevent that and were never read."""
    seen = {}
    for j in _L(jobs):
        for skill, stamp in _D(j.get("_runs")).items():
            v = _D(stamp).get("prompt_version")
            if v:
                seen.setdefault(skill, set()).add(v)
    return [{"skill": s, "versions": sorted(vs), "drift": len(vs) > 1}
            for s, vs in sorted(seen.items())]


# ======================================================================
#  S2 / S4 / S5 - THROUGHPUT, FAILURES, DEGRADED MODE
# ======================================================================
_TERMINAL = ("optimized", "revision_needed", "halted_budget", "failed")


def throughput(jobs: list, days: int = 14) -> dict:
    jobs = _L(jobs)
    by_day, by_status = {}, {}
    for j in jobs:
        d = str(j.get("created_at", ""))[:10]
        if d:
            by_day[d] = by_day.get(d, 0) + 1
        by_status[j.get("status", "?")] = by_status.get(j.get("status", "?"), 0) + 1
    recent = sorted(by_day.items())[-days:]
    queue = [j for j in jobs if j.get("status") not in _TERMINAL]
    waiting = [j for j in jobs if j.get("status") == "AWAITING_APPROVAL"
               and not j.get("approved")]
    return {"total": len(jobs), "by_status": by_status,
            "daily": recent, "series": [n for _d, n in recent],
            "queue_depth": len(queue), "awaiting_approval": len(waiting),
            "done": by_status.get("optimized", 0),
            "failed": by_status.get("failed", 0) + by_status.get("halted_budget", 0)}


def failure_patterns(jobs: list, days: int = 7) -> dict:
    """S4 — a list of errors is not a diagnosis. This is error type x day."""
    kinds, grid_days, cells = {}, [], {}
    for j in _L(jobs):
        if j.get("status") not in ("failed", "halted_budget"):
            continue
        err = str(j.get("error") or j.get("last_error") or j.get("status") or "unknown")
        kind = err.split(":")[0][:26] or "unknown"
        day = str(j.get("updated_at") or j.get("created_at") or "")[:10]
        kinds[kind] = kinds.get(kind, 0) + 1
        if day:
            if day not in grid_days:
                grid_days.append(day)
            cells[(kind, day)] = cells.get((kind, day), 0) + 1
    grid_days = sorted(grid_days)[-days:]
    rows = sorted(kinds, key=lambda k: -kinds[k])[:8]
    matrix = [[cells.get((k, d), 0) for d in grid_days] for k in rows]
    mx = max((v for row in matrix for v in row), default=0) or 1
    return {"kinds": kinds, "total": sum(kinds.values()),
            "rows": rows, "days": grid_days,
            "matrix": [[round(100 * v / mx) for v in row] for row in matrix],
            "top": sorted(kinds.items(), key=lambda kv: -kv[1])[:8]}


def degraded(jobs: list) -> dict:
    """S5 — advance() catches every exception and flags needs_human. Nothing
    ever showed that backlog."""
    stuck = [j for j in _L(jobs)
             if _D(j.get("payload")).get("needs_human") or j.get("needs_human")]
    return {"count": len(stuck),
            "jobs": [{"job_id": j.get("job_id"), "status": j.get("status"),
                      "type": j.get("type")} for j in stuck[:20]]}


# ======================================================================
#  S14 - FRESHNESS
# ======================================================================
def freshness(engine_runs: dict, cadence: dict) -> list:
    """Which engines ran, which are overdue. A confident number produced by a
    stale engine is the worst failure mode this system has."""
    runs = _D(engine_runs)
    out = []
    for name, cfg in sorted(_D(cadence).items()):
        every = _D(cfg).get("every_days", 1)
        age = _days_since(runs.get(name))
        never = age > 1e8
        out.append({"engine": name, "every_days": every,
                    "days_since": None if never else round(age, 1),
                    "never_run": never,
                    "overdue": never or age >= every,
                    "cost": _D(cfg).get("cost", "free"),
                    "last": runs.get(name, "")})
    return out


def freshness_matrix(rows: list):
    """engine x staleness, for a heatmap. 100 = fresh, 0 = long overdue."""
    rows = _L(rows)[:12]
    labels = [r["engine"] for r in rows]
    cols = ["due in", "age"]
    grid = []
    for r in rows:
        age = 100 if r["never_run"] else max(
            0, round(100 - 100 * (r["days_since"] or 0) / max(r["every_days"], 1)))
        grid.append([100 - age, age])
    return labels, cols, grid


# ======================================================================
#  S10 / S11 / S12 - COST AND QUOTA
# ======================================================================
def quotas(meters: dict, status: dict) -> list:
    out = []
    for key, (label, ceiling, note) in QUOTAS.items():
        used = _D(_D(meters).get(key)).get("calls", 0)
        out.append({"key": key, "label": label, "ceiling": ceiling, "note": note,
                    "used": used, "live": bool(_D(status).get(key)),
                    "pct": round(100 * used / ceiling, 1) if ceiling else 0,
                    "unlimited": ceiling == 0})
    return out


def cost_split(meters: dict, month_spent: float, month_cap: float) -> dict:
    """S10/S12 — api_meters() stores {api: {month, spent, calls}}. Summing the
    raw values raised TypeError once already; parse it properly."""
    rows = []
    for api, m in _D(meters).items():
        m = _D(m)
        try:
            spent = float(m.get("spent") or 0)
        except (TypeError, ValueError):
            spent = 0.0
        rows.append({"api": api, "spent": round(spent, 2),
                     "calls": int(m.get("calls") or 0)})
    rows.sort(key=lambda r: -r["spent"])
    total = sum(r["spent"] for r in rows)
    return {"rows": rows, "total": round(total, 2),
            "month_spent": round(float(month_spent or 0), 2),
            "month_cap": round(float(month_cap or 0), 2),
            "pct_of_cap": round(100 * float(month_spent or 0) / float(month_cap or 1), 1),
            "treemap": [(r["api"], r["spent"]) for r in rows if r["spent"]][:8],
            "waterfall": [(r["api"], r["spent"]) for r in rows[:6]]}


# ======================================================================
#  S8 / S17 - DEPENDENCIES AND STORAGE
# ======================================================================
def dependency_graph(rows: list):
    """(nodes, edges) for a digraph — what breaks what."""
    rows = _L(rows)
    nodes, edges, seen = [], [], set()
    for r in rows:
        if not r.get("downstream"):
            continue
        if r["key"] not in seen:
            nodes.append((r["key"], r["name"][:16], bool(r["live"] or r["always_on"])))
            seen.add(r["key"])
        for d in r["downstream"][:3]:
            if d not in seen:
                nodes.append((d, d[:16], bool(r["live"] or r["always_on"])))
                seen.add(d)
            edges.append((r["key"], d))
    return nodes[:14], edges[:20]


def storage_health(store) -> dict:
    """S17 — the settings row holds the crawl, the audit and the work orders.
    It has a practical size limit and nothing was watching it."""
    out = {"kind": type(store).__name__, "keys": {}, "ok": True}
    for key in ("seo_crawl", "seo_audit", "seo_workorders", "seo_inspect",
                "ads_snapshot", "crosschannel", "google_insights"):
        try:
            v = store.get_setting(key, None)
        except Exception:
            v = None
        try:
            import json
            size = len(json.dumps(v)) if v is not None else 0
        except Exception:
            size = 0
        out["keys"][key] = size
    out["total_bytes"] = sum(out["keys"].values())
    out["largest"] = max(out["keys"].items(), key=lambda kv: kv[1], default=("", 0))
    return out


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    DIAG = [("claude_api", "Claude AI brain", "no key", "engine can't think", "ANTHROPIC_API_KEY"),
            ("wordpress_publish", "Publish to WordPress", "no app password",
             "articles can't post", "WORDPRESS_URL + WORDPRESS_APP_PASSWORD")]
    status = {"claude_api": True, "wordpress_publish": False, "seo_crawler": True,
              "seo_backlinks": False, "serper_search": True}
    rows = wire_rows(status, DIAG)
    assert len(rows) == 5, rows
    wp = next(r for r in rows if r["key"] == "wordpress_publish")
    assert not wp["live"] and wp["documented"] and "articles can't post" in wp["breaks"]
    undoc = next(r for r in rows if r["key"] == "seo_backlinks")
    assert not undoc["documented"] and undoc["breaks"] == "not documented", undoc
    crawler = next(r for r in rows if r["key"] == "seo_crawler")
    assert crawler["always_on"] and crawler["severity"] == "ok"
    s = wire_summary(rows)
    assert s["total"] == 5 and s["down"] == 2, s
    assert "seo_backlinks" in s["undocumented"], s["undocumented"]
    assert "publish" in s["blocked_features"] and "off_page" in s["blocked_features"], s

    jobs = [
        {"job_id": "a", "status": "optimized", "created_at": "2026-07-29T09:00:00",
         "updated_at": "2026-07-29T10:00:00",
         "_runs": {"content_producer": {"model": "claude-opus-4-8", "prompt_version": "v1",
                                        "at": "2026-07-29T09:10:00"},
                   "qa_compliance": {"model": "claude-haiku-4-5", "prompt_version": "v1",
                                     "at": "2026-07-29T09:20:00"}}},
        {"job_id": "b", "status": "failed", "created_at": "2026-07-30T09:00:00",
         "updated_at": "2026-07-30T09:30:00", "error": "TimeoutError: upstream",
         "_runs": {"content_producer": {"model": "claude-haiku-4-5", "prompt_version": "v2",
                                        "at": "2026-07-30T09:05:00"}}},
        {"job_id": "c", "status": "AWAITING_APPROVAL", "approved": False,
         "created_at": "2026-07-30T11:00:00", "payload": {"needs_human": True}},
    ]
    ag = agent_stats(jobs)
    cp = next(a for a in ag if a["skill"] == "content_producer")
    assert cp["runs"] == 2 and cp["failures"] == 1 and cp["success_pct"] == 50.0, cp
    assert cp["version_drift"] and cp["versions"] == ["v1", "v2"], cp
    assert next(a for a in agent_stats(jobs, ["never_used"]))["never_run"] is True

    mu = model_usage(jobs)
    assert mu["total"] == 3 and mu["cheap_pct"] == 66.7, mu
    assert mu["frontier_pct"] == 33.3, mu

    pv = prompt_versions(jobs)
    assert any(p["drift"] for p in pv), pv

    tp = throughput(jobs)
    assert tp["total"] == 3 and tp["failed"] == 1 and tp["awaiting_approval"] == 1, tp
    assert tp["queue_depth"] == 1, tp          # only the AWAITING one is non-terminal
    assert len(tp["series"]) == 2, tp["series"]

    fp = failure_patterns(jobs)
    assert fp["total"] == 1 and fp["rows"] == ["TimeoutError"], fp
    assert fp["matrix"] and fp["matrix"][0][0] == 100, fp["matrix"]

    dg = degraded(jobs)
    assert dg["count"] == 1 and dg["jobs"][0]["job_id"] == "c", dg

    CAD = {"crawl": {"every_days": 7, "cost": "free"},
           "ranks": {"every_days": 1, "cost": "cheap"}}
    fr = freshness({"crawl": _now().isoformat()}, CAD)
    crawl_row = next(r for r in fr if r["engine"] == "crawl")
    assert not crawl_row["overdue"] and crawl_row["days_since"] == 0.0, crawl_row
    ranks_row = next(r for r in fr if r["engine"] == "ranks")
    assert ranks_row["never_run"] and ranks_row["overdue"], ranks_row
    labels, cols, grid = freshness_matrix(fr)
    assert labels and len(grid) == len(labels) and len(grid[0]) == 2

    q = quotas({"serper_search": {"calls": 250}}, {"serper_search": True})
    ser = next(x for x in q if x["key"] == "serper_search")
    assert ser["used"] == 250 and ser["pct"] == 10.0, ser
    assert next(x for x in q if x["key"] == "claude_api")["unlimited"] is True

    cs = cost_split({"serper": {"spent": 1.31, "calls": 58},
                     "anthropic": {"spent": 4.02, "calls": 120}}, 12.5, 200)
    assert cs["total"] == 5.33 and cs["rows"][0]["api"] == "anthropic", cs
    assert cs["pct_of_cap"] == 6.2, cs          # 12.50 of 200
    assert cs["treemap"][0] == ("anthropic", 4.02), cs["treemap"]

    nodes, edges = dependency_graph(rows)
    assert nodes and edges, (nodes, edges)
    assert any(n[0] == "claude_api" for n in nodes)

    class _S:
        def get_setting(self, k, d=None):
            return {"a": 1} if k == "seo_crawl" else None
    sh = storage_health(_S())
    assert sh["keys"]["seo_crawl"] > 0 and sh["keys"]["seo_audit"] == 0, sh
    assert sh["largest"][0] == "seo_crawl", sh["largest"]
    print("system self-check OK — wires incl. undocumented, agent stats, model "
          "split, prompt drift, throughput, failure matrix, degraded, freshness, "
          "quotas, cost split, dependency graph, storage")
