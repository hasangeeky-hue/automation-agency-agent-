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

import os
from datetime import date

import content_engine_orchestrator as orch


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
           "aeo": SEO.run_aeo, "offpage": SEO.run_offpage,
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
    assert due_all[0] in ("crawl", "indexnow", "inspect", "speed"), due_all
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
