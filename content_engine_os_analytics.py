"""
content_engine_os_analytics.py
============================================================================
ENGINE 9: THE EVENT PROCESSOR AND THE AGGREGATION LAYER.

RAW EVENTS ARE NOT A DASHBOARD
  Counting fifty thousand events on every page load is how a dashboard
  becomes something nobody opens. rollup() walks the event list once and
  writes daily rows per campaign; every screen reads the rows.

THE TWO HONESTY RULES THIS FILE OBEYS
  1. Every rate carries its denominator. "42%" alone is a rumour.
  2. Any number derived from OPENS carries the Apple caveat. Mail Privacy
     Protection pre-fetches images, so an open is a weaker fact than a
     click and saying so is not a disclaimer, it is the measurement.

WHAT IS DELIBERATELY EMPTY
  Delivered and bounced stay None until an ESP webhook reports them. SMTP
  has no delivery receipt. Rendering 0 there would be a claim that nothing
  bounced, and an absence is not a zero.
============================================================================
"""

from __future__ import annotations

import content_engine_os_core as CORE
from content_engine_os_core import _D, _L, rate, rid

MPP_CAVEAT = ("Opens are counted from a tracking pixel. Apple Mail Privacy "
              "Protection loads that pixel whether or not a person read "
              "anything, so treat opens as a ceiling and clicks as the "
              "measurement.")

#: The event types that roll up into a daily row.
COUNTED = ("EMAIL_QUEUED", "EMAIL_SENT", "EMAIL_DELIVERED", "EMAIL_BOUNCED",
           "EMAIL_OPENED", "EMAIL_CLICKED", "EMAIL_UNSUBSCRIBED",
           "EMAIL_SPAM_COMPLAINT", "EMAIL_CONVERTED")

_SHORT = {"EMAIL_QUEUED": "queued", "EMAIL_SENT": "sent",
          "EMAIL_DELIVERED": "delivered", "EMAIL_BOUNCED": "bounced",
          "EMAIL_OPENED": "opens", "EMAIL_CLICKED": "clicks",
          "EMAIL_UNSUBSCRIBED": "unsubscribes",
          "EMAIL_SPAM_COMPLAINT": "complaints",
          "EMAIL_CONVERTED": "conversions"}


def _day(v) -> str:
    return str(v or "")[:10]


def rollup(repo) -> dict:
    """One pass over the events, into daily_metrics rows keyed by
    (day, campaign). Idempotent: the row id is derived from the pair, so a
    second run overwrites rather than doubles."""
    buckets = {}
    for e_ in repo.all("email_events"):
        k = e_.get("event_type")
        if k not in COUNTED:
            continue
        key = (_day(e_.get("timestamp")), e_.get("campaign_id") or "")
        b = buckets.setdefault(key, {s: 0 for s in _SHORT.values()})
        b[_SHORT[k]] += 1
    # Unique-by-person opens and clicks. Five opens from one recipient is
    # one person being reminded, not five people interested.
    uniq = {}
    for e_ in repo.all("email_events"):
        if e_.get("event_type") not in ("EMAIL_OPENED", "EMAIL_CLICKED"):
            continue
        key = (_day(e_.get("timestamp")), e_.get("campaign_id") or "")
        which = "u_opens" if e_.get("event_type") == "EMAIL_OPENED" else "u_clicks"
        uniq.setdefault(key, {"u_opens": set(), "u_clicks": set()})[which].add(
            e_.get("profile_id"))
    for (day, cid), b in buckets.items():
        u = uniq.get((day, cid), {})
        repo.put("daily_metrics", {
            "id": rid("dm", repo.ws, day, cid), "day": day,
            "campaign_id": cid,
            "unique_opens": len(u.get("u_opens", ())),
            "unique_clicks": len(u.get("u_clicks", ())), **b})
    return {"ok": True, "days": len({d for d, _ in buckets}),
            "rows": len(buckets),
            "message": f"{len(buckets)} daily row(s) rebuilt"}


def totals(repo, campaign_id=None) -> dict:
    """Aggregated counts, read from the rollup, never from raw events."""
    rows = repo.all("daily_metrics")
    if campaign_id:
        rows = [r for r in rows if r.get("campaign_id") == campaign_id]
    t = {v: 0 for v in _SHORT.values()}
    t.update({"unique_opens": 0, "unique_clicks": 0})
    for r in rows:
        for k in t:
            t[k] += int(r.get(k) or 0)
    sent = t["sent"]
    # An absence is not a zero: SMTP never reports delivery or bounces, so
    # those stay None until an ESP webhook says otherwise.
    delivered = t["delivered"] or None
    bounced = t["bounced"] or None
    return {
        **t, "delivered": delivered, "bounced": bounced,
        "open_rate": rate(t["unique_opens"], sent),
        "click_rate": rate(t["unique_clicks"], sent),
        "ctor": rate(t["unique_clicks"], t["unique_opens"]),
        "unsub_rate": rate(t["unsubscribes"], sent),
        "complaint_rate": rate(t["complaints"], sent),
        "conversion_rate": rate(t["conversions"], sent),
        "bounce_rate": rate(bounced, sent) if bounced is not None else (None, ""),
        "caveat": MPP_CAVEAT,
    }


def by_day(repo, campaign_id=None, days=30) -> list:
    rows = repo.all("daily_metrics")
    if campaign_id:
        rows = [r for r in rows if r.get("campaign_id") == campaign_id]
    merged = {}
    for r in rows:
        d = merged.setdefault(r.get("day"), {"day": r.get("day")})
        for k in list(_SHORT.values()) + ["unique_opens", "unique_clicks"]:
            d[k] = d.get(k, 0) + int(r.get(k) or 0)
    return sorted(merged.values(), key=lambda r: r["day"])[-days:]


def campaign_rows(repo) -> list:
    """One row per campaign, which is what the Campaigns table draws.

    The subject is the row, not the internal name: a founder scanning this
    list is looking for the email he wrote, not a job id."""
    msgs = repo.all("campaign_messages")
    by_camp = {}
    for m in msgs:
        by_camp.setdefault(m.get("campaign_id"), []).append(m)
    out = []
    for c in repo.all("campaigns"):
        cid = c.get("id")
        mine = by_camp.get(cid, [])
        t = totals(repo, cid)
        subj = (next((m.get("subject") for m in mine if m.get("subject")), "")
                or (_L(c.get("subject_variants")) or [""])[0]
                or c.get("subject") or "")
        out.append({
            "id": cid, "name": c.get("name"), "subject": subj,
            "state": c.get("state", "DRAFT"),
            "source": c.get("source", "native"),
            "job_id": c.get("job_id", ""),
            "recipients": c.get("recipients") or len({m.get("profile_id")
                                                      for m in mine}),
            "messages": len(mine),
            "sent": t["sent"], "opens": t["unique_opens"],
            "clicks": t["unique_clicks"],
            "open_rate": t["open_rate"], "click_rate": t["click_rate"],
            "unsubscribes": t["unsubscribes"],
            "edited": len([m for m in mine if m.get("edited")]),
            "variants": len(_L(c.get("subject_variants"))),
            "created_at": c.get("created_at", ""),
        })
    return sorted(out, key=lambda r: (-r["sent"], str(r.get("created_at"))),
                  reverse=False)


def message_rows(repo, campaign_id) -> list:
    """Every message on one campaign, with what happened to it. This is the
    recipient table on the campaign detail screen."""
    profs = {p.get("id"): p for p in repo.all("profiles")}
    ev = {}
    for e_ in CORE.events_for(repo, campaign_id=campaign_id):
        ev.setdefault(e_.get("message_id"), []).append(e_)
    out = []
    for m in repo.find("campaign_messages", campaign_id=campaign_id):
        kinds = [x.get("event_type") for x in ev.get(m.get("id"), [])]
        p = profs.get(m.get("profile_id")) or {}
        out.append({
            "id": m.get("id"), "email": m.get("email"),
            "profile_id": m.get("profile_id"),
            "name": " ".join(x for x in [p.get("first_name"),
                                         p.get("last_name")] if x),
            "company": p.get("company", ""),
            "touch": m.get("touch", 1), "subject": m.get("subject", ""),
            "state": m.get("state", ""), "sent_at": m.get("sent_at", ""),
            "edited": bool(m.get("edited")),
            "opened": kinds.count("EMAIL_OPENED"),
            "clicked": kinds.count("EMAIL_CLICKED"),
            "bounced": "EMAIL_BOUNCED" in kinds,
        })
    return sorted(out, key=lambda r: (str(r.get("sent_at")), r.get("email")),
                  reverse=True)


def link_rows(repo, campaign_id=None) -> list:
    """Which links were actually clicked. A click on a specific URL is the
    strongest signal this engine collects, so it gets its own table."""
    counts = {}
    for e_ in repo.all("email_events"):
        if e_.get("event_type") != "EMAIL_CLICKED":
            continue
        if campaign_id and e_.get("campaign_id") != campaign_id:
            continue
        url = _D(e_.get("metadata")).get("url") or "(url not recorded)"
        c = counts.setdefault(url, {"url": url, "clicks": 0, "people": set()})
        c["clicks"] += 1
        c["people"].add(e_.get("profile_id"))
    rows = [{"url": v["url"], "clicks": v["clicks"], "people": len(v["people"])}
            for v in counts.values()]
    return sorted(rows, key=lambda r: -r["clicks"])


def open_curve(repo, campaign_id=None, hours=72) -> list:
    """Hours between a send and its first open, bucketed. Tells the founder
    when to schedule, which is a decision rather than a number."""
    sends = {}
    for e_ in repo.all("email_events"):
        if campaign_id and e_.get("campaign_id") != campaign_id:
            continue
        if e_.get("event_type") == "EMAIL_SENT":
            sends[e_.get("message_id")] = CORE.parse_at(e_.get("timestamp"))
    buckets = [0] * 13
    for e_ in repo.all("email_events"):
        if e_.get("event_type") != "EMAIL_OPENED":
            continue
        if campaign_id and e_.get("campaign_id") != campaign_id:
            continue
        s = sends.get(e_.get("message_id"))
        o = CORE.parse_at(e_.get("timestamp"))
        if not s or not o:
            continue
        h = (o - s).total_seconds() / 3600.0
        if 0 <= h <= hours:
            buckets[min(12, int(h // 6))] += 1
    return [{"label": f"{i*6}-{i*6+6}h", "opens": n}
            for i, n in enumerate(buckets)]


def profile_rows(repo, limit=400) -> list:
    """The Profiles table: person, company, stage, engagement, consent."""
    import content_engine_os_audience as AUD
    rows = AUD.people(repo)
    for r in rows:
        r["name"] = " ".join(x for x in [r.get("first_name"),
                                         r.get("last_name")] if x) or r.get("email")
    return sorted(rows, key=lambda r: (-(r.get("clicks") or 0),
                                       -(r.get("opens") or 0),
                                       str(r.get("email"))))[:limit]


def acquisition(repo) -> dict:
    """The business questions, not the email questions. New leads, how many
    the agent qualified, how many are actually emailable."""
    leads = repo.all("leads")
    profs = repo.all("profiles")
    by_source = {}
    for p in profs:
        s = p.get("source") or "unknown"
        by_source[s] = by_source.get(s, 0) + 1
    stages = {s: len([l for l in leads if l.get("stage") == s])
              for s in CORE.LEAD_STAGES}
    scored = [l for l in leads if l.get("score") is not None]
    return {"leads": len(leads), "profiles": len(profs),
            "companies": len(repo.all("companies")),
            "ai_qualified": len(scored),
            "avg_score": (round(sum(float(l.get("score") or 0) for l in scored)
                                / len(scored), 1) if scored else None),
            "by_source": sorted(by_source.items(), key=lambda kv: -kv[1]),
            "stages": stages,
            "enrichment": rate(len([p for p in profs if p.get("company")]),
                               len(profs))}


def agent_rows(repo) -> list:
    acts = {}
    for a in repo.all("agent_actions"):
        acts[a.get("agent_run_id")] = acts.get(a.get("agent_run_id"), 0) + 1
    return [{"id": r.get("id"), "agent": r.get("agent_type"),
             "task": r.get("task"), "status": r.get("status"),
             "started_at": r.get("started_at"),
             "completed_at": r.get("completed_at", ""),
             "cost": r.get("cost", 0), "tokens": r.get("token_usage", 0),
             "actions": acts.get(r.get("id"), 0),
             "output": str(r.get("output", ""))[:200]}
            for r in sorted(repo.all("agent_runs"),
                            key=lambda r: str(r.get("started_at")),
                            reverse=True)]


def deliverability(repo) -> dict:
    t = totals(repo)
    supp = repo.all("suppressions")
    by_reason = {}
    for s in supp:
        by_reason[s.get("reason")] = by_reason.get(s.get("reason"), 0) + 1
    return {"sent": t["sent"], "bounced": t["bounced"],
            "bounce_rate": t["bounce_rate"],
            "complaints": t["complaints"], "complaint_rate": t["complaint_rate"],
            "unsubscribes": t["unsubscribes"], "unsub_rate": t["unsub_rate"],
            "suppressed": len(supp), "by_reason": by_reason}


# ---------------------------------------------------------------------------
# A/B
# ---------------------------------------------------------------------------
def variant_rows(repo, campaign_id) -> list:
    """One row per subject line under test, with what it actually did.

    Opens are counted UNIQUE BY PERSON and the denominator is that arm's
    own recipients, never the campaign total. Comparing A's opens against
    the whole campaign is how a test proves whatever you hoped."""
    msgs = repo.find("campaign_messages", campaign_id=campaign_id)
    if not msgs:
        return []
    ev = {}
    for e_ in repo.all("email_events"):
        if e_.get("campaign_id") != campaign_id:
            continue
        ev.setdefault(e_.get("message_id"), []).append(e_)
    arms = {}
    for m in msgs:
        v = m.get("variant") or "A"
        a = arms.setdefault(v, {"variant": v, "subject": m.get("subject", ""),
                                "recipients": 0, "sent": 0,
                                "opened": set(), "clicked": set()})
        a["recipients"] += 1
        if m.get("state") == "SENT" or m.get("sent_at"):
            a["sent"] += 1
        if not a["subject"] and m.get("subject"):
            a["subject"] = m.get("subject")
        for x in ev.get(m.get("id"), []):
            if x.get("event_type") == "EMAIL_OPENED":
                a["opened"].add(m.get("profile_id"))
            elif x.get("event_type") == "EMAIL_CLICKED":
                a["clicked"].add(m.get("profile_id"))
    out = []
    for v, a in sorted(arms.items()):
        out.append({"variant": v, "subject": a["subject"],
                    "recipients": a["recipients"], "sent": a["sent"],
                    "opened": len(a["opened"]), "clicked": len(a["clicked"]),
                    "open_rate": rate(len(a["opened"]), a["sent"]),
                    "click_rate": rate(len(a["clicked"]), a["sent"])})
    return out


def ab_verdict(rows) -> dict:
    """Which arm won, and whether the difference means anything yet.

    THE HONEST PART: below about a hundred sends per arm, a five point gap
    is noise. Declaring a winner off forty emails is the single most common
    way an A/B test makes a campaign worse, so this says "too early" in
    those words rather than crowning something."""
    rows = [r for r in _L(rows) if r.get("sent")]
    if len(rows) < 2:
        return {"state": "none",
                "message": "only one subject line is in play, so there is "
                           "nothing to compare"}
    best = max(rows, key=lambda r: (r["open_rate"][0] or 0))
    worst = min(rows, key=lambda r: (r["open_rate"][0] or 0))
    gap = (best["open_rate"][0] or 0) - (worst["open_rate"][0] or 0)
    smallest = min(r["sent"] for r in rows)
    if smallest < 100:
        return {"state": "early", "leader": best["variant"], "gap": gap,
                "message": f"{best['variant']} is ahead by {gap:.1f} points, "
                           f"but the smaller arm has only {smallest} sends. "
                           f"Below about 100 an arm, a gap that size is "
                           f"noise. Keep both running."}
    if gap < 5:
        return {"state": "tied", "leader": "", "gap": gap,
                "message": f"the arms are within {gap:.1f} points of each "
                           f"other, which is close enough to call a draw"}
    return {"state": "winner", "leader": best["variant"], "gap": gap,
            "message": f"{best['variant']} wins by {gap:.1f} points over "
                       f"{smallest}+ sends an arm: "
                       f"{best['subject'][:60]!r}"}
