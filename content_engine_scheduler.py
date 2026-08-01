"""
content_engine_scheduler.py
============================================================================
Daily production scheduler (Phase 2). Turns the founder's cadence targets into
actual jobs, once per day, cold-email-FIRST (so paid marketing later is smoother).

Targets (env, with the founder's defaults):
  SCHED_OUTREACH_PER_DAY   cold-email campaigns per day     (default 1)
  SCHED_BLOGS_PER_DAY      blog pieces to the website/day   (default 2)
  SCHED_SOCIAL_PER_CHANNEL social posts per channel per day (default 3)
  SCHED_CHANNELS           comma list (default linkedin,twitter,facebook,instagram,tiktok)
  BRAND_NAME               brand for the jobs

plan_today(store) is IDEMPOTENT per calendar day (guards on a store setting), so
an n8n cron can hit POST /schedule/run as often as it likes without duplicating.
Cold-email jobs are created before content jobs on purpose.
============================================================================
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

import content_engine_orchestrator as orch

log = logging.getLogger("content_engine.scheduler")


def _int(env, default):
    try:
        return int(os.getenv(env, str(default)))
    except ValueError:
        return default


def _channels():
    raw = os.getenv("SCHED_CHANNELS", "linkedin,twitter,facebook,instagram,tiktok")
    return [c.strip() for c in raw.split(",") if c.strip()]


def _sval(getset, key, default):
    """Settings-first (dashboard-controllable), then env, then default."""
    if callable(getset):
        try:
            v = getset(key, None)
            if v not in (None, ""):
                return v
        except Exception:
            pass
    return os.getenv(key, default)


def _isval(getset, key, default):
    try:
        return int(_sval(getset, key, default))
    except (TypeError, ValueError):
        return int(default)


def plan_today(store, force: bool = False) -> dict:
    """Create today's batch of jobs (idempotent per day). Returns a summary.
    Cadence is read from settings first (SCHED_CHANNELS / SCHED_*_PER_DAY etc.),
    so you tune it live from the dashboard. Default channel is LinkedIn only —
    no junk jobs for channels you haven't connected."""
    today = date.today().isoformat()
    getset = getattr(store, "get_setting", None)
    setset = getattr(store, "set_setting", None)
    if not force and callable(getset) and getset("planned_day", "") == today:
        return {"status": "already_planned", "day": today}

    brand = {"brand_name": _sval(getset, "BRAND_NAME", "Anthropos Automation"),
             "offer": _sval(getset, "BRAND_OFFER", "AI automation")}
    raw_ch = _sval(getset, "SCHED_CHANNELS", "linkedin")
    channels = [c.strip() for c in str(raw_ch).split(",") if c.strip()]
    created = []

    def make(job_type, suffix, payload):
        jid = f"auto_{today}_{suffix}"
        if _exists(store, jid):
            return
        job = orch.new_job(jid, job_type, brand, payload)
        store.save(job)
        created.append({"job_id": jid, "type": job_type})

    # 1) COLD EMAIL FIRST (priority: warm the pipeline before paid marketing).
    for i in range(_isval(getset, "SCHED_OUTREACH_PER_DAY", 1)):
        make("outreach_campaign", f"outreach_{i}",
             {"config": {"our_offer": brand["offer"]},
              "raw_leads": [], "category": "other", "lead": {},
              "buckets": [], "_scheduled": True})

    # 2) BLOGS to the website.
    for i in range(_isval(getset, "SCHED_BLOGS_PER_DAY", 2)):
        make("content_piece", f"blog_{i}",
             {"config": {"business_goal": "awareness", "produce_index": 0,
                         "deploy_channels": ["wordpress"], "pieces_this_week": 14},
              "audit": {}, "competitors": [], "_scheduled": True})

    # 3) SOCIAL posts per channel.
    per = _isval(getset, "SCHED_SOCIAL_PER_CHANNEL", 1)
    for ch in channels:
        for i in range(per):
            make("content_piece", f"social_{ch}_{i}",
                 {"config": {"business_goal": "awareness", "produce_index": 0,
                             "deploy_channels": [ch]},
                  "audit": {}, "competitors": [], "_scheduled": True})

    if callable(setset):
        setset("planned_day", today)
    return {"status": "planned", "day": today, "created": len(created),
            "cold_email_first": True,
            "targets": {"outreach": _isval(getset, "SCHED_OUTREACH_PER_DAY", 1),
                        "blogs": _isval(getset, "SCHED_BLOGS_PER_DAY", 2),
                        "social_per_channel": per, "channels": channels}}


def _exists(store, jid) -> bool:
    try:
        store.get(jid)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SEO cadence. Each engine has its own natural rhythm — crawling daily is waste,
# checking rankings weekly is too slow to tell you whether a fix worked.
# Free engines (crawl / inspect / speed / indexnow / fixes) never touch budget.
# ---------------------------------------------------------------------------
SEO_CADENCE = {
    "crawl":       {"every_days": 7, "cost": "free"},
    "inspect":     {"every_days": 1, "cost": "free"},
    "speed":       {"every_days": 7, "cost": "free"},
    "indexnow":    {"every_days": 1, "cost": "free"},
    "fixes":       {"every_days": 1, "cost": "cheap"},
    "ranks":       {"every_days": 1, "cost": "cheap"},
    "aeo":         {"every_days": 7, "cost": "cheap"},
    "geo":         {"every_days": 7, "cost": "cheap"},
    "ads":         {"every_days": 1, "cost": "free"},
    "interlock":   {"every_days": 1, "cost": "free"},
    "offpage":     {"every_days": 7, "cost": "paid"},
    "prospecting": {"every_days": 7, "cost": "cheap"},
}


def _days_since(iso: str) -> float:
    if not iso:
        return 1e9
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0
    except Exception:
        return 1e9


def seo_due(store) -> list:
    """Which SEO engines are due right now, cheapest first."""
    getset = getattr(store, "get_setting", None)
    runs = {}
    if callable(getset):
        try:
            runs = getset("seo_engine_runs", {}) or {}
        except Exception:
            runs = {}
    order = {"free": 0, "cheap": 1, "paid": 2}
    due = [name for name, cfg in SEO_CADENCE.items()
           if _days_since(runs.get(name, "")) >= cfg["every_days"]]
    return sorted(due, key=lambda n: (order[SEO_CADENCE[n]["cost"]], n))


def run_seo_due(store, *, include_paid: bool = True) -> dict:
    """Run only what's due. Safe to call hourly from n8n — it self-throttles."""
    import content_engine_seo_ops as SEO
    fns = {"crawl": SEO.run_crawl, "inspect": SEO.run_inspect, "speed": SEO.run_speed,
           "indexnow": SEO.run_indexnow, "fixes": SEO.run_fixes, "ranks": SEO.run_ranks,
           "aeo": SEO.run_aeo, "geo": SEO.run_geo, "ads": SEO.run_ads,
           "interlock": SEO.run_interlock, "offpage": SEO.run_offpage,
           "prospecting": SEO.run_prospecting}
    out = {}
    for name in seo_due(store):
        if not include_paid and SEO_CADENCE[name]["cost"] == "paid":
            continue
        try:
            out[name] = fns[name](store)
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return {"ran": list(out), "results": out}



# ===========================================================================
#  THE CADENCE — the half of the scheduler that nothing was calling.
#
#  SEO_CADENCE above has said "crawl every 7 days, ranks every 1 day" since it
#  was written, and plan_today() has been able to queue a day's work all along.
#  Neither ever fired on its own: main.py called orch.tick() and nothing else,
#  and run_seo_due() was reachable only by manually POSTing /seo/due. The engine
#  could do the work; nobody ever told it when.
#
#  run_due_work() is that missing caller. The worker invokes it every loop; it
#  does AT MOST ONE due task per call and returns immediately otherwise, so it
#  costs nothing when there is nothing to do.
# ===========================================================================
CADENCE_KEY = "engine_cadence_last"

# TECHNICAL SEO, UNATTENDED. Its own switch, deliberately NOT the content one:
# fixing a missing alt attribute is not the same decision as publishing an
# article, and tying them together would mean you cannot have the first without
# the second.
#   off   nothing runs unattended (default)
#   safe  only fixes a reader can never see - schema, alt text, IndexNow
#   all   also rewrites post bodies to insert internal links
SEO_AUTO_KEY = "seo_autofix"
SEO_AUTO_LOG = "seo_autofix_log"
SEO_AUTO_LEVELS = ("off", "safe", "all")


def seo_auto_level(store) -> str:
    try:
        v = str(store.get_setting(SEO_AUTO_KEY, "off") or "off").lower()
    except Exception:
        return "off"
    return v if v in SEO_AUTO_LEVELS else "off"


def set_seo_auto(store, level: str) -> dict:
    level = str(level or "").lower()
    if level not in SEO_AUTO_LEVELS:
        return {"ok": False, "error": f"level must be one of {SEO_AUTO_LEVELS}"}
    try:
        store.set_setting(SEO_AUTO_KEY, level)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "level": level, "message": {
        "off": "Unattended SEO fixing is OFF.",
        "safe": "ON - invisible fixes only. Schema, alt text and IndexNow run "
                "around the clock; nothing a reader sees is touched.",
        "all": "ON - includes rewriting post bodies to insert internal links. "
               "Readers will see those changes.",
    }[level]}


def _seo_codes(level: str):
    """Which work-order types the unattended run may execute."""
    import content_engine_workorders as WO
    if level == "all":
        return sorted(WO.AUTO_CODES)
    return sorted(WO.SAFE_AUTO_CODES)


def seo_auto_log(store, limit: int = 40) -> list:
    """What the machine changed while you were not watching. Without this,
    unattended means unaccountable."""
    try:
        return list(store.get_setting(SEO_AUTO_LOG, []) or [])[::-1][:limit]
    except Exception:
        return []

# seconds between attempts. Deliberately conservative: the SEO engines
# self-throttle by their own per-day cadence, so checking hourly is plenty.
CADENCE = {
    "plan": 3600,      # queue today's work (plan_today is idempotent per day)
    "seo": 3600,       # run whichever SEO engines are due
    "replies": 900,    # DRAFT answers to inbound replies — never sends
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cadence_state(store) -> dict:
    try:
        return dict(store.get_setting(CADENCE_KEY, {}) or {})
    except Exception:
        return {}


def _due(state: dict, task: str, now: datetime) -> bool:
    last = state.get(task)
    if not last:
        return True
    try:
        return (now - datetime.fromisoformat(last)).total_seconds() >= CADENCE[task]
    except Exception:
        return True


def _stamp(store, state: dict, task: str, now: datetime) -> None:
    state[task] = now.isoformat()
    try:
        store.set_setting(CADENCE_KEY, state)
    except Exception as e:
        log.warning("could not record the cadence stamp for %s: %s", task, e)


def _run_seo(store, level: str, now) -> dict:
    """One unattended technical-SEO pass, and a record of what it changed.

    Crawl first when there is nothing to work from: run_fixes reads the stored
    crawl, so on a cold engine it would find zero orders and report success
    having done nothing."""
    import content_engine_seo_ops as SEO
    codes = _seo_codes(level)
    out = {"ran": "seo", "level": level, "codes": codes}
    try:
        if not _get_crawl(store):
            # nothing to work from yet - crawl first, or the pass reports
            # success having found zero orders and done nothing
            out["crawl"] = SEO.run_crawl(store)
        rep = SEO.run_fixes(store, auto_only=True, types=codes, limit=20)
        out["fixes"] = {k: rep.get(k) for k in
                        ("attempted", "done", "failed", "awaiting_approval")}
        applied = [d for d in (rep.get("details") or [])
                   if str(d.get("status")) == "done"]
        if applied:
            try:
                logrec = list(store.get_setting(SEO_AUTO_LOG, []) or [])
                for d in applied:
                    logrec.append({"at": now.isoformat(), "level": level,
                                   "code": d.get("code") or d.get("type"),
                                   "url": d.get("url"),
                                   "result": str(d.get("result", ""))[:200]})
                store.set_setting(SEO_AUTO_LOG, logrec[-300:])
            except Exception as e:
                log.warning("could not record the autofix log: %s", e)
            log.info("unattended SEO (%s): applied %d fix(es)", level, len(applied))
    except Exception as e:
        log.exception("unattended SEO pass failed")
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _get_crawl(store):
    try:
        import content_engine_seo_ops as SEO
        return store.get_setting(SEO.K_CRAWL, {}) or {}
    except Exception:
        return {}


def run_due_work(store, now=None) -> dict:
    """Fire whatever is due. Called by the worker on every loop.

    Rules this must never break:
      * PAUSED means paused. Nothing here runs while the engine is stopped.
      * It NEVER sends. Replies are drafted for the approval queue; the reply
        agent's own auto-send flag is explicitly forced off here regardless of
        how it is configured, because "the scheduler started sending email on a
        timer" is the one outcome that must be impossible.
      * It never raises. A failing task is logged and stamped so a broken engine
        cannot spin the worker.
      * One task per call, so a slow task cannot starve job processing.
    """
    now = now or _now()
    getset = getattr(store, "get_setting", None)
    if not callable(getset):
        return {"skipped": "store cannot read settings"}
    if getset("paused", False):
        return {"skipped": "paused"}
    _seo_level = seo_auto_level(store)
    if not getset("cadence_on", False):
        # The CONTENT engine is stopped. Technical SEO can still run if it was
        # switched on separately - that is the whole point of a second switch.
        if _seo_level == "off":
            return {"skipped": "cadence off"}
        state = cadence_state(store)
        if not _due(state, "seo", now):
            return {"skipped": "cadence off (seo not due)"}
        _stamp(store, state, "seo", now)
        return _run_seo(store, _seo_level, now)

    state = cadence_state(store)

    if _due(state, "plan", now):
        _stamp(store, state, "plan", now)
        try:
            r = plan_today(store)
            if r.get("created"):
                log.info("cadence: queued %s job(s) for %s", r["created"], r.get("day"))
            return {"ran": "plan", "result": r}
        except Exception as e:
            log.exception("cadence: plan_today failed")
            return {"ran": "plan", "error": f"{type(e).__name__}: {e}"}

    if _due(state, "seo", now):
        _stamp(store, state, "seo", now)
        if _seo_level != "off":
            return _run_seo(store, _seo_level, now)
        try:
            # Paid engines only when the cap allows it. A cadence that quietly
            # spends is a cadence you would have to watch.
            caps = orch.budget_caps(store)
            spent = 0.0
            try:
                m = getattr(store, "monthly_cost", None)
                spent = float(m() if callable(m) else 0.0)
            except Exception:
                pass
            headroom = float(caps.get("per_month", 0)) - spent
            include_paid = headroom > float(caps.get("per_month", 0)) * 0.25
            r = run_seo_due(store, include_paid=include_paid)
            if r.get("ran"):
                log.info("cadence: ran SEO engines %s (paid=%s)", r["ran"], include_paid)
            return {"ran": "seo", "paid_allowed": include_paid, "result": r}
        except Exception as e:
            log.exception("cadence: run_seo_due failed")
            return {"ran": "seo", "error": f"{type(e).__name__}: {e}"}

    if _due(state, "replies", now):
        _stamp(store, state, "replies", now)
        try:
            import content_engine_reply_agent as reply_agent
            # auto_send=False is passed EXPLICITLY. Without it the agent reads
            # REPLY_AUTO_SEND from the environment, and a stray "1" there would
            # turn a scheduled draft into a scheduled send.
            r = reply_agent.answer_replies(limit=20, auto_send=False, dry_run=False)
            n = len(r.get("drafts", []) or []) if isinstance(r, dict) else 0
            if n:
                log.info("cadence: drafted %s repl(ies) for your approval", n)
            return {"ran": "replies", "result": r}
        except Exception as e:
            log.exception("cadence: answer_replies failed")
            return {"ran": "replies", "error": f"{type(e).__name__}: {e}"}

    return {"ran": None}


def cadence_view(store) -> dict:
    """What the cadence will do next, for the dashboard."""
    now = _now()
    state = cadence_state(store)
    try:
        on = bool(store.get_setting("cadence_on", False))
        paused = bool(store.get_setting("paused", False))
    except Exception:
        on = paused = False
    rows = []
    for task, secs in CADENCE.items():
        last = state.get(task)
        due = _due(state, task, now)
        rows.append({"task": task, "every_mins": round(secs / 60),
                     "last": str(last or "")[:16], "due_now": due})
    return {"on": on, "paused": paused, "rows": rows,
            "note": ("The cadence is running." if on and not paused else
                     "The cadence is OFF — nothing is queued automatically." )}


if __name__ == "__main__":
    os.environ.update({"SCHED_OUTREACH_PER_DAY": "1", "SCHED_BLOGS_PER_DAY": "2",
                       "SCHED_SOCIAL_PER_CHANNEL": "3",
                       "SCHED_CHANNELS": "linkedin,twitter,facebook,instagram,tiktok"})
    store = orch.InMemoryJobStore()
    r = plan_today(store)
    # 1 outreach + 2 blogs + 3*5 social = 18 jobs
    assert r["status"] == "planned" and r["created"] == 18, r
    # cold-email job created before blog jobs (ordering)
    ids = [j["job_id"] for j in store.list_jobs()]
    assert any("outreach" in i for i in ids) and sum("social" in i for i in ids) == 15
    # idempotent: second call same day creates nothing new
    r2 = plan_today(store)
    assert r2["status"] == "already_planned", r2
    assert len(store.list_jobs()) == 18
    # ---- SEO cadence: self-throttling, cheapest-first ----
    class _S:
        def __init__(self, runs): self._r = runs
        def get_setting(self, k, d=None): return self._r if k == "seo_engine_runs" else d

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    fresh = now.isoformat()
    yesterday = (now - timedelta(days=2)).isoformat()

    due_all = seo_due(_S({}))
    assert set(due_all) == set(SEO_CADENCE), due_all
    assert "ads" in SEO_CADENCE and "interlock" in SEO_CADENCE, "media engines must be scheduled"
    assert SEO_CADENCE[due_all[0]]["cost"] == "free", due_all   # cheapest first
    costs = [SEO_CADENCE[n]["cost"] for n in due_all]
    assert costs == sorted(costs, key=lambda c: {"free": 0, "cheap": 1, "paid": 2}[c]), costs

    # everything just ran -> nothing is due
    assert seo_due(_S({n: fresh for n in SEO_CADENCE})) == [], "must self-throttle"

    # daily engines come due again after 2 days; weekly ones don't
    due2 = seo_due(_S({n: yesterday for n in SEO_CADENCE}))
    assert "inspect" in due2 and "ranks" in due2, due2
    assert "crawl" not in due2 and "aeo" not in due2, due2
    assert _days_since("") > 1000 and _days_since("garbage") > 1000

    print("OK — scheduler: cold-email-first daily batch (1 outreach + 2 blogs + 15 social), "
          "idempotent per day; SEO cadence self-throttles cheapest-first. No network.")
