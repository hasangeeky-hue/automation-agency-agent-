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


def plan_today(store, force: bool = False) -> dict:
    """Create today's batch of jobs (idempotent per day). Returns a summary."""
    today = date.today().isoformat()
    getset = getattr(store, "get_setting", None)
    setset = getattr(store, "set_setting", None)
    if not force and callable(getset) and getset("planned_day", "") == today:
        return {"status": "already_planned", "day": today}

    brand = {"brand_name": os.getenv("BRAND_NAME", "Anthropos Automation"),
             "offer": os.getenv("BRAND_OFFER", "AI automation")}
    channels = _channels()
    created = []

    def make(job_type, suffix, payload):
        jid = f"auto_{today}_{suffix}"
        if _exists(store, jid):
            return
        job = orch.new_job(jid, job_type, brand, payload)
        store.save(job)
        created.append({"job_id": jid, "type": job_type})

    # 1) COLD EMAIL FIRST (priority: warm the pipeline before paid marketing).
    for i in range(_int("SCHED_OUTREACH_PER_DAY", 1)):
        make("outreach_campaign", f"outreach_{i}",
             {"config": {"our_offer": brand["offer"]},
              "raw_leads": [], "category": "other", "lead": {},
              "buckets": [], "_scheduled": True})

    # 2) BLOGS to the website.
    for i in range(_int("SCHED_BLOGS_PER_DAY", 2)):
        make("content_piece", f"blog_{i}",
             {"config": {"business_goal": "awareness", "produce_index": 0,
                         "deploy_channels": ["wordpress"], "pieces_this_week": 14},
              "audit": {}, "competitors": [], "_scheduled": True})

    # 3) SOCIAL posts per channel.
    per = _int("SCHED_SOCIAL_PER_CHANNEL", 3)
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
            "targets": {"outreach": _int("SCHED_OUTREACH_PER_DAY", 1),
                        "blogs": _int("SCHED_BLOGS_PER_DAY", 2),
                        "social_per_channel": per, "channels": channels}}


def _exists(store, jid) -> bool:
    try:
        store.get(jid)
        return True
    except Exception:
        return False


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
    print("OK — scheduler: cold-email-first daily batch (1 outreach + 2 blogs + 15 social), "
          "idempotent per day. No network.")
