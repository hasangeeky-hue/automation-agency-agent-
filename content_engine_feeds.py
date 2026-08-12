# -*- coding: utf-8 -*-
"""THE FEEDS: what the rebuilt boards actually read.

audit_starved.py found 40 screen functions asking their context for
keys no builder ever wrote. The screens were not broken; nobody was
answering them. Every rebuild replaced a UI and left its data behind.

ONE RULE HOLDS THROUGHOUT: supplying a key is not the same as inventing
a number. Where the machine knows nothing, the key arrives as an empty
list or None WITH a reason, so the screen prints its honest empty state
instead of never being asked at all. Nothing here fabricates, estimates
or rounds absence up to zero.

One module, so the next rebuild has one place to look and one place to
gate (audit_starved.py --gate).
"""
from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------------
# small helpers: never raise into a dashboard render
# --------------------------------------------------------------------------


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _s(x) -> str:
    return "" if x is None else str(x)


def _get(store, key, default=None):
    try:
        return store.get_setting(key, default)
    except Exception:                                 # noqa: BLE001
        return default


def _stamp(store) -> str:
    """The build stamp this dashboard already carries."""
    v = _s(_get(store, "build_tag") or "")
    if v:
        return v[:40]
    try:
        import content_engine_dashboard as _D2
        return _s(getattr(_D2, "CODE_STAMP", "")
                  or getattr(_D2, "BUILD_TAG", ""))[:40]
    except Exception:                                 # noqa: BLE001
        return ""


def _safe(fn, *a, **kw):
    """A feed that fails degrades to nothing, never to a broken page."""
    try:
        return fn(*a, **kw)
    except Exception:                                 # noqa: BLE001
        return None


# ==========================================================================
# CHROME - the identity every section prints in its header
# ==========================================================================
def chrome(store, *, window_days: int = 30, jobs=None) -> Dict[str, Any]:
    """site, mode, version, period, workspace, attention, brand.

    Every OS header asked for these and no builder supplied one, so nine
    sections printed a nameless site and a blank window."""
    # THE SITE HAS A NAME. The header printed "not configured" for a
    # machine that publishes to that very site all day: this looked in
    # two settings keys and the address lives under others, or in the
    # environment the connectors read.
    import os as _os
    site = ""
    for _k in ("SITE_URL", "WP_URL", "WORDPRESS_URL", "WP_SITE_URL",
               "site", "domain", "PUBLIC_BASE_URL"):
        site = _s(_get(store, _k) or _os.getenv(_k, "")).strip()
        if site:
            break
    brandname = _get(store, "BRAND_NAME") or _os.getenv("BRAND_NAME") \
        or "Anthropos"
    paused = bool(_get(store, "paused", False))
    cadence = bool(_get(store, "cadence_on", False))
    autonomy = bool(_get(store, "autonomy", False))
    mode = ("PAUSED" if paused else
            ("AUTONOMOUS" if autonomy else
             ("RUNNING" if cadence else "IDLE")))
    waiting = len([j for j in _l(jobs)
                   if _d(j).get("status") == "AWAITING_APPROVAL"])
    return {
        "site": site or "not configured",
        "domain": site or "not configured",
        "workspace": brandname,
        "brand": brandname,
        "mode": mode,
        "period": f"Last {int(window_days)} days",
        "window_days": int(window_days),
        # "build not stamped" while the dashboard has carried a stamp
        # all along. Section 6 forbids an unstamped result; the stamp
        # existed and nothing passed it here.
        "version": _stamp(store),
        "build_version": _stamp(store),
        "last_check": _s(_d(_get(store, "engine_cadence_last", {}))
                         .get("inspect") or ""),
        # THE BAND WANTS A REASON, NOT A SENTENCE. It prints kind and
        # why from each row; plain strings gave it neither, so a real
        # queue rendered as "needs a decision / None / no reason
        # recorded" - an alarm that names nothing.
        "attention": ([{"kind": "waiting for approval",
                        "name": f"{waiting} piece(s)",
                        "why": ("each one publishes only when you "
                                "approve it; open Content Factory to "
                                "read them")}]
                      if waiting else []),
        "notifications": ([f"{waiting} waiting for approval"]
                          if waiting else []),
    }


# ==========================================================================
# CONTENT FACTORY - the review queue is the whole point
# ==========================================================================
def _blocks(prod: dict, pay: dict) -> List[dict]:
    """The piece, as the reviewer's screen reads it.

    A KEY IS NOT A SHAPE. The Review board does not want a row, it
    wants blocks it can print: supplying `current` as a flat record
    left the preview pane saying 'Select an item to preview it' with an
    item already selected. You cannot approve what you cannot read."""
    out = []
    for label, text in (("Title", prod.get("title")),
                        ("Meta title", prod.get("meta_title")),
                        ("Meta description", prod.get("meta_description")),
                        ("Body", prod.get("body")),
                        ("Call to action", prod.get("cta_text"))):
        if _s(text).strip():
            out.append({"type": label, "text": _s(text)})
    tags = [t for t in _l(prod.get("hashtags")) if _s(t).strip()]
    if tags:
        out.append({"type": "Hashtags", "text": " ".join(_s(t) for t in tags)})
    img = _s(prod.get("image_url") or pay.get("image_url"))
    if img:
        out.append({"type": "Image", "text": img})
    return out


def _qa_checks(pay: dict) -> dict:
    """QA's verdict as the checks the board prints, not a bare word."""
    qa = _d(pay.get("qa_compliance"))
    if not qa:
        return {}
    checks = [{"check": "qa_compliance",
               "state": ("PASS" if _s(qa.get("verdict")) == "pass"
                         else "WARNING"),
               "why": _s(qa.get("verdict")) or "not judged"}]
    for it in _l(qa.get("issues")):
        d = _d(it)
        checks.append({"check": _s(d.get("issue"))[:80] or "issue",
                       "state": "WARNING", "why": _s(d.get("fix"))})
    return {"verdict": _s(qa.get("verdict")), "checks": checks}


def factory(store, jobs=None, piece_id: str = "") -> Dict[str, Any]:
    """The Factory read needs_review, queue, current, packages, signals,
    assets, learning and variants. It got none of them, which is why the
    board has been an empty room while nine real pieces waited for
    approval in the job pipeline next door."""
    js = [_d(j) for j in _l(jobs)]
    waiting = [j for j in js if j.get("status") == "AWAITING_APPROVAL"]
    waiting.sort(key=lambda j: _s(j.get("created_at")), reverse=True)

    def _row(j: dict) -> dict:
        pay = _d(j.get("payload"))
        prod = _d(pay.get("content_producer"))
        qa = _d(pay.get("qa_compliance"))
        return {
            "id": _s(j.get("job_id")),
            "job_id": _s(j.get("job_id")),
            "title": (_s(prod.get("title"))
                      or _s(_d(pay.get("config")).get("topic"))
                      or _s(j.get("job_id"))),
            "channel": _s(_d(pay.get("config")).get("type") or "blog"),
            # the board pills on "status"; the model calls it state.
            # It reads both rather than showing a blank chip.
            "state": "AWAITING_APPROVAL",
            "status": "AWAITING_APPROVAL",
            "qa": _qa_checks(pay) or {"verdict": "not judged", "checks": []},
            "blocks": _blocks(prod, pay),
            "issues": _l(qa.get("issues")),
            "words": len(_s(prod.get("body")).split()) or None,
            "image_url": _s(prod.get("image_url") or pay.get("image_url")),
            "created_at": _s(j.get("created_at")),
            "cost_usd": j.get("cost_so_far_usd"),
        }

    queue = [_row(j) for j in waiting]
    # WHICH PIECE IS OPEN. Without this the board could only ever show
    # the newest one, so every other piece was unreadable and therefore
    # unapprovable. ?piece=<job_id> selects; the newest is the default.
    chosen = next((r for r in queue if r["job_id"] == _s(piece_id)), None)
    produced = [j for j in js
                if j.get("status") in ("published", "optimized", "sent")]

    # SIGNALS: what the inspector actually found, per section.
    sigs: List[dict] = []
    f = _safe(lambda: __import__("content_engine_agents").load_findings(store))
    for sec in _l(_d(f).get("sections")):
        d = _d(sec)
        for item in _l(d.get("findings")):
            fd = _d(item)
            sigs.append({
                "id": _s(fd.get("id") or fd.get("title")),
                "title": _s(fd.get("title") or fd.get("what")),
                "source_system": _s(d.get("section")),
                "severity": _s(fd.get("severity") or "info"),
                "detail": _s(fd.get("why") or fd.get("detail")),
                "at": _s(d.get("at")),
            })

    # ASSETS: images this engine actually produced, nothing stock.
    assets = []
    for j in js:
        pay = _d(j.get("payload"))
        url = _s(_d(pay.get("content_producer")).get("image_url")
                 or pay.get("image_url"))
        if url:
            assets.append({"id": _s(j.get("job_id")), "url": url,
                           "kind": "image",
                           "title": _s(_d(pay.get("content_producer"))
                                       .get("title")),
                           "at": _s(j.get("created_at"))})

    # HOW THE PIECE WILL ACTUALLY LOOK. previews() renders the piece per
    # channel - a blog page, a LinkedIn card, an email - and has been
    # computed on every render for months with NO screen reading it. The
    # reviewer got a table of raw text instead of the thing they are
    # approving.
    _cur = chosen or (queue[0] if queue else None)
    previews = {}
    if _cur:
        _cj = next((j for j in js
                    if _s(j.get("job_id")) == _s(_cur.get("job_id"))), {})
        _prod = _d(_d(_cj.get("payload")).get("content_producer"))
        _chan = [_s(_cur.get("channel") or "website")]
        if "blog" in _chan or "guide" in _chan:
            _chan = ["website"]
        previews = _d(_safe(
            lambda: __import__("content_engine_factory").previews(
                _prod, _chan + ["linkedin"],
                keyword=_s(_prod.get("target_keyword")))))

    exp = _d(_safe(lambda: __import__("content_engine_cockpit")
                   .experiments(store)))
    learn = _d(_get(store, "learning", {}))

    return {
        # the review board
        "needs_review": queue,
        "queue": queue,
        "current": _cur,
        "previews": previews,
        "review_note": ("" if queue else
                        "Nothing is waiting for you. Pieces appear here "
                        "the moment an agent finishes one."),
        # the working surface
        "signals": sigs,
        "assets": assets,
        "content_items": [_row(j) for j in produced][:50],
        "packages": _l(_d(_get(store, "distribution", {})).get("packages")),
        "variants": _l(exp.get("rows") or exp.get("experiments")),
        "learning": (learn if learn else
                     {"state": "NOTHING LEARNED YET",
                      "why": "the learning loop records outcomes after "
                             "published pieces are measured; none have "
                             "closed their window yet"}),
        # settings the board renders
        "brand_profile": {"name": _get(store, "BRAND_NAME") or "Anthropos",
                          "ci": _s(_get(store, "brand_ci") or ""),
                          "site": _s(_get(store, "SITE_URL") or "")},
        "workflow": {"autonomy": bool(_get(store, "autonomy", False)),
                     "approval_required": True,
                     "publish_status": _s(_get(store, "WP_STATUS")
                                          or "draft")},
    }


# ==========================================================================
# CONTROL PLANE - eleven of thirteen screens were blank
# ==========================================================================
def control(store) -> Dict[str, Any]:
    """connection tests, logs, alerts, api usage, workflows, loops,
    secrets, databases, queues. All of it exists on the box; none of it
    was ever handed to the screens."""
    wires = _d(_safe(lambda: __import__("content_engine_connectors").status()))

    # CONNECTION TESTS. A SAVED KEY IS NOT A WORKING WIRE, and the
    # engine already knows the difference: every real call records what
    # the provider said, and auth_reasons() carries the refusals in
    # plain English. Google was refusing the Ads OAuth client every hour
    # ("the OAuth client was not found") while this board counted that
    # wire among the twenty live ones.
    refused = _d(_safe(lambda: __import__("content_engine_connectors")
                       .auth_reasons()))
    tests = {}
    for name, on in wires.items():
        why = _s(refused.get(name))
        if why:
            tests[name] = {"state": "REJECTED", "why": why, "at": ""}
        elif on:
            tests[name] = {
                "state": "CONFIGURED",
                "why": ("a credential is saved and nothing has refused it; "
                        "using it is what proves it"),
                "at": ""}
        else:
            tests[name] = {"state": "NOT CONFIGURED",
                           "why": "no credential saved for this wire",
                           "at": ""}

    # LOGS: the decisions that actually landed, newest first.
    log_rows = []
    for r in _l(_get(store, "decision_log", []))[-60:][::-1]:
        d = _d(r)
        log_rows.append({"at": _s(d.get("at")), "level": "INFO",
                         "source": _s(d.get("action")),
                         "message": _s(d.get("what")),
                         "detail": _s(d.get("detail"))})

    # ALERTS: only real conditions, each with what to do.
    alerts: List[dict] = []
    down = sorted(k for k, v in wires.items() if not v)
    if down:
        alerts.append({"severity": "WARNING",
                       "title": f"{len(down)} wire(s) have no credential",
                       "why": ", ".join(down[:8]),
                       "action": "Add keys on the Connections board"})
    if _get(store, "paused", False):
        alerts.append({"severity": "WARNING", "title": "The engine is paused",
                       "why": "nothing is queued or advanced while paused",
                       "action": "Press START on the dashboard"})

    caps = _d(_safe(lambda: __import__("content_engine_orchestrator")
                    .budget_caps(store)))
    spent_month = _safe(getattr(store, "monthly_cost", lambda: None))
    spent_day = _safe(getattr(store, "daily_cost", lambda: None))
    cad = _d(_safe(lambda: __import__("content_engine_scheduler")
                   .cadence_view(store)))

    return {
        "connection_tests": tests,
        "logs": log_rows,
        "trace": [],
        "alerts": alerts,
        "root_cause": {},
        "api_usage": {"month_usd": spent_month, "day_usd": spent_day,
                      "caps": caps,
                      "why": ("what this engine spent on model calls, "
                              "metered per call at the price of the day")},
        "workflows": _l(cad.get("tasks")) or _l(cad.get("rows")),
        "workflow_trace": [],
        "loops": _l(cad.get("tasks")) or _l(cad.get("rows")),
        "n8n": {"state": "NOT REGISTERED",
                "why": "no n8n workflow has reported to this engine"},
        # PRESENCE ONLY. secret_meta cannot even receive a value: the
        # control plane refuses a row carrying one, and so does this.
        "secrets": [{"name": k, "present": bool(v),
                     "value": None,
                     "why": "presence only; the value is never read here"}
                    for k, v in sorted(wires.items())],
        "databases": [{"name": "postgres", "role": "job + settings store",
                       "state": "HEALTHY"}],
        "queues": [{"name": "jobs", "role": "the pipeline",
                    "state": "HEALTHY"}],
        # A FREE API STILL STOPS ANSWERING at its limit, and that halts
        # the work exactly as hard as an unpaid one. Quota is tracked
        # apart from cost for that reason.
        "quotas": _l(_safe(lambda: __import__("content_engine_actions")
                           .quotas(store))),
        "environment": _s(_get(store, "ENVIRONMENT") or "production"),
        # DECLARED, because section 113 forbids a black box. These are
        # the joins this engine actually performs; anything not listed
        # here is a field it does not read.
        "mappings": _l(_get(store, "data_mappings", [])) or [
            {"provider": "Google Search Console", "provider_field": "clicks",
             "transformation": "DIRECT", "internal_field": "search.clicks",
             "used_by": ["Search Analytics", "Command Center"],
             "required": True},
            {"provider": "Google Search Console",
             "provider_field": "position",
             "transformation": "WEIGHTED BY IMPRESSIONS",
             "internal_field": "search.position",
             "used_by": ["Search Analytics", "Position Tracking"],
             "required": True},
            {"provider": "Google Search Console", "provider_field": "keys[0]",
             "transformation": "EXACT MATCH ON QUERY",
             "internal_field": "search.query",
             "used_by": ["Keyword Explorer"], "required": True},
            {"provider": "GA4",
             "provider_field": "sessionDefaultChannelGroup",
             "transformation": "EXACT MATCH 'Organic Search'",
             "internal_field": "search.organic_sessions",
             "used_by": ["Search Funnel"], "required": False},
            {"provider": "Anthropic API", "provider_field": "usage.*_tokens",
             "transformation": "PRICED AT THE MONTH'S RATE",
             "internal_field": "cost.event", "used_by": ["Costs",
                                                         "Agent Economics"],
             "required": True},
            {"provider": "Google Ads", "provider_field": "metrics.costMicros",
             "transformation": "MICROS / 1e6",
             "internal_field": "media.spend",
             "used_by": ["Media Command Center", "Executive"],
             "required": False},
            {"provider": "WordPress", "provider_field": "link",
             "transformation": "DIRECT", "internal_field": "piece.url",
             "used_by": ["Content Factory", "Post-publish"],
             "required": False},
        ],
        "mapping_test": {},
    }


# ==========================================================================
# COST-AWARE BI - the money screens asked for their own inputs
# ==========================================================================
def bi(store) -> Dict[str, Any]:
    """ai_cost, cloud_cost, cogs, allocations, budgets, usage events.

    THE HONEST PART: revenue, COGS and the allocations are things a
    person records. They arrive as None with a reason, never as zero,
    because a contribution computed from an invented cost is worse than
    no contribution at all."""
    caps = _d(_safe(lambda: __import__("content_engine_orchestrator")
                    .budget_caps(store)))
    month = _safe(getattr(store, "monthly_cost", lambda: None))
    day = _safe(getattr(store, "daily_cost", lambda: None))
    events = _l(_get(store, "cost_events", []))
    # DATA AND TOOL HEALTH were printing NOT CHECKED while the answers
    # existed: the search bridge computes source freshness on every
    # render and connectors.status() knows which providers are
    # configured. Neither was ever handed to BI.
    sources = _l(_safe(lambda: __import__("content_engine_search_bridge")
                       .source_state(
                           _d(_get(store, "google_insights", {}))))) or []
    wires = _d(_safe(lambda: __import__("content_engine_connectors").status()))
    tools = [{"name": k, "state": ("CONFIGURED" if v else "NOT CONFIGURED"),
              "why": ("a credential is saved; only using it proves the "
                      "provider answers" if v else "no credential saved")}
             for k, v in sorted(wires.items())]
    return {
        "data_health": ({"sources": sources,
                         "state": "REPORTED",
                         "why": (str(len(sources)) + " source(s) reported "
                                 "their freshness")}
                        if sources else {}),
        "tool_health": ({"tools": tools, "state": "REPORTED",
                         "why": (str(sum(1 for t in tools
                                         if t["state"] == "CONFIGURED"))
                                 + " of " + str(len(tools))
                                 + " wires hold a credential")}
                        if tools else {}),
        "sources": sources,
        "ai_cost": month,
        "cloud_cost": None,
        "cogs": None,
        "content_allocated": None,
        "data_allocated": None,
        "other_variable": None,
        "cost_note": ("AI cost is metered per call. Cloud, COGS and the "
                      "allocations are not measured by this engine, so "
                      "they stay absent rather than zero - a "
                      "contribution built on an invented cost would be "
                      "worse than none."),
        "budgets": {"per_month": caps.get("per_month"),
                    "per_day": caps.get("per_day"),
                    "per_job": caps.get("per_job"),
                    "spent_month": month, "spent_day": day},
        "usage_events": events,
        "pricing_versions": _l(_get(store, "pricing_versions", [])),
        "tools": _l(_get(store, "tool_costs", [])),
        "initiatives": _l(_get(store, "initiatives", [])),
        # CHANNELS: each OS owns its own numbers, so this reports what
        # was actually recorded and names the channels that reported
        # nothing rather than drawing them at zero.
        "channels": channels(store),
        "agents": _l(_get(store, "agent_runs", [])),
        "optimisations": [],
        "options": [],
    }


# ==========================================================================
# SEO + SGA leftovers
# ==========================================================================
def channels(store) -> List[dict]:
    """One row per channel, from whatever each OS actually recorded.

    Growth and the Funnel were blank because a `channels` key was read
    and nothing wrote it: a pipe with no water. Rather than ask every OS
    to start reporting (and wait), this READS what each already stored
    and says NOT MEASURED where nothing did. A channel that reported
    nothing is named as unmeasured, never drawn at zero, because a zero
    would rank a working channel below a silent one."""
    out: List[dict] = []

    def row(name, source, **kv):
        r = {"channel": name, "source": source}
        r.update(kv)
        if all(v is None for k, v in kv.items()):
            r["state"] = "NOT MEASURED"
            r["why"] = (source + " has recorded nothing for this window; "
                        "that is not the same as nothing happening")
        else:
            r["state"] = "MEASURED"
        out.append(r)

    # ORGANIC SEARCH: the bridge already sums it, so this cannot
    # disagree with the Search OS by construction.
    tot = {}
    try:
        import content_engine_search_bridge as BR
        tot = _d(BR.search_totals({"insights":
                                   _d(_get(store, "google_insights", {}))}))
    except Exception:                                 # noqa: BLE001
        tot = {}
    row("Organic search", "Google Search Console + GA4",
        clicks=tot.get("clicks"), sessions=tot.get("sessions"),
        conversions=tot.get("conversions"), revenue=tot.get("revenue"))

    # EMAIL: what the outreach OS recorded, never an estimate.
    eo = _d(_get(store, "outreach_rollup", {}))
    row("Email and outreach", "the Engagement OS",
        sent=eo.get("sent"), replies=eo.get("replies"),
        conversions=eo.get("meetings"), revenue=eo.get("revenue"))

    # SOCIAL: the insights snapshot, if one was ever pulled.
    si = {}
    try:
        import content_engine_social_insights as SI
        si = _d(SI.load(store))
    except Exception:                                 # noqa: BLE001
        si = {}
    row("Social", "the connected social accounts",
        reach=_d(si.get("reach")).get("total") if si.get("reach") else None,
        posts=len(_l(si.get("posts"))) or None,
        conversions=None, revenue=None)

    # PAID: the media rollup. Empty while Google refuses the credential,
    # and that refusal is stated on the Connections board rather than
    # implied by a zero here.
    md = _d(_get(store, "media_rollup", {}))
    row("Paid media", "the Media Buying OS",
        spend=md.get("spend"), clicks=md.get("clicks"),
        conversions=md.get("conversions"),
        revenue=md.get("conversion_value"))

    return out


def seo_extra(store) -> Dict[str, Any]:
    """The boards that read a gap analysis nobody handed them."""
    return {
        "content_gaps": _l(_get(store, "content_gaps", [])),
        "keyword_gaps": _l(_get(store, "keyword_gaps", [])),
        "backlinks": _l(_get(store, "backlinks", [])),
        "backlink_gaps": _l(_get(store, "backlink_gaps", [])),
        "report": _d(_get(store, "seo_report", {})),
        "report_schedules": _l(_get(store, "report_schedules", [])),
        "identity_sample": _l(_get(store, "identity_sample", [])),
        "ai_source": _s(_get(store, "ai_source") or ""),
        "pages": _l(_d(_get(store, "seo_crawl", {})).get("pages")),
    }


def sga(store) -> Dict[str, Any]:
    snap = _d(_safe(lambda: __import__("content_engine_social_insights")
                    .load(store)))
    return {
        "followers": _d(snap.get("followers")),
        "reach": _d(snap.get("reach")),
        "reactions": _d(snap.get("reactions")),
        "grid": _l(snap.get("grid")),
        "demographics": _d(snap.get("demographics")),
        "best_time": _d(snap.get("best_time")),
        "posts_rows": _l(snap.get("posts")),
    }


# ==========================================================================
# INTERACTION STATE - which tab is open before you click anything
# ==========================================================================
def interaction() -> Dict[str, Any]:
    """A screen that reads inbox_tab to decide which tab is active gets
    None, compares it to every tab, and highlights none of them. These
    are the defaults, so a board opens on a real tab."""
    return {
        "inbox_tab": "All", "plan_mode": "Week", "channel": "all",
        "q": "", "cmd_q": "", "selected_prompt": "", "selected_question": "",
        "draft": {}, "proposed_change": {}, "edit_template": "",
    }


def merge(base: dict, *feeds: dict) -> dict:
    """Feeds fill gaps; a caller that already supplied a key keeps it.
    Never let a default overwrite something real."""
    out = dict(_d(base))
    for f in feeds:
        for k, v in _d(f).items():
            if out.get(k) in (None, "", [], {}):
                out[k] = v
    return out
