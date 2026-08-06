"""
content_engine_email_campaigns.py
============================================================================
CAMPAIGNS AND PROFILES, KLAVIYO GRADE - built entirely on machinery that is
ALREADY LIVE on this box.

WHY THERE IS NO SOCKET HERE
  Unlike the social section, nothing in this file waits on a key. The open
  pixel (/t/o/<token>), the click redirect (/t/c/<token>), the token store
  and the event log all run today; SMTP sends today; IMAP reads today. This
  module does not fetch anything - it READS what the engine already
  recorded and shapes it into the two objects Klaviyo is built around:

    a CAMPAIGN   one send to many people, with its own funnel
    a PROFILE    one person, with every event that ever touched them

THE COUNTING RULE
  Unique by token, never by raw event. One recipient reloading an email is
  not five readers, and a rate whose denominator is unstated is a rumour -
  so every rate here carries the number it was divided by.
============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("email_campaigns")

# The open-rate caveat, written once and shown everywhere a number derived
# from opens appears. Apple Mail pre-fetches images, which fires the pixel
# for people who never read the mail; clicks do not have that problem.
MPP_CAVEAT = ("Apple Mail Privacy Protection pre-fetches images, so opens "
              "are inflated for Apple recipients. Clicks are the number to "
              "trust.")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, list) else []


def _rate(n, d):
    """A rate that always carries its denominator. Returns (pct, text)."""
    n, d = float(n or 0), float(d or 0)
    if not d:
        return (None, "no denominator yet")
    return (round(n / d * 100, 1), f"{int(n)} of {int(d)}")


def _out_jobs(jobs):
    return [j for j in _L(jobs)
            if _D(j).get("type") == "outreach_campaign"]


def _events(store):
    try:
        import content_engine_outreach as O
        return _L(store.get_setting(O.EVENTS_KEY, []))
    except Exception:
        return []


def _tokens(store):
    try:
        import content_engine_outreach as O
        return _D(store.get_setting(O.TOKENS_KEY, {}))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# CAMPAIGNS
# ---------------------------------------------------------------------------
def campaigns(store, jobs=None, bookings=None, deals=None) -> list:
    """One row per outreach job, with its real funnel.

    Every number comes from the token store and the event log, so a campaign
    that was never tracked reports no opens rather than zero opens - the
    distinction the whole dashboard rests on."""
    toks = _tokens(store)
    evs = _events(store)
    # token -> job, and the unique sets per kind
    opened, clicked = set(), set()
    click_links = {}
    first_seen = {}
    for e in evs:
        e = _D(e)
        t, k = e.get("token"), e.get("kind")
        if not t:
            continue
        if k == "open":
            opened.add(t)
        elif k == "click":
            clicked.add(t)
            u = str(e.get("url") or e.get("u") or "")[:120]
            if u:
                click_links[u] = click_links.get(u, 0) + 1
        first_seen.setdefault(t, e.get("at"))

    by_job = {}
    for t, meta in toks.items():
        jid = str(_D(meta).get("job") or _D(meta).get("job_id") or "")
        b = by_job.setdefault(jid, {"tokens": set(), "opened": set(),
                                    "clicked": set(), "steps": {}})
        b["tokens"].add(t)
        if t in opened:
            b["opened"].add(t)
        if t in clicked:
            b["clicked"].add(t)
        st = _D(meta).get("step")
        if st:
            b["steps"][st] = b["steps"].get(st, 0) + 1

    out = []
    for j in _out_jobs(jobs):
        j = _D(j)
        jid = str(j.get("job_id") or j.get("id") or "")
        p = _D(j.get("payload"))
        leads = _L(p.get("leads"))
        sent_at = _D(p.get("sent_at"))
        sent = sum(len(_L(v)) for v in sent_at.values())
        b = by_job.get(jid) or {"tokens": set(), "opened": set(),
                                "clicked": set(), "steps": {}}
        tracked = len(b["tokens"])
        nopen, nclick = len(b["opened"]), len(b["clicked"])
        # CTOR is clicks over OPENS, not over sends - it is the question
        # "of the people who read it, how many acted", and it is the one
        # rate Apple's pre-fetching does not distort in the same direction.
        ctor = _rate(nclick, nopen)
        out.append({
            "id": jid, "name": (p.get("name") or p.get("campaign")
                                or j.get("title") or f"Campaign {jid[:8]}"),
            "status": j.get("status") or "unknown",
            "created": j.get("created_at") or p.get("created_at"),
            "recipients": len(leads) or None,
            "sent": sent or None,
            "tracked": tracked or None,
            "opens": nopen if tracked else None,
            "clicks": nclick if tracked else None,
            "open_rate": _rate(nopen, tracked)[0] if tracked else None,
            "open_of": _rate(nopen, tracked)[1] if tracked else "not tracked",
            "click_rate": _rate(nclick, tracked)[0] if tracked else None,
            "click_of": _rate(nclick, tracked)[1] if tracked else "not tracked",
            "ctor": ctor[0], "ctor_of": ctor[1],
            "steps": b["steps"],
            "cost": j.get("cost_so_far_usd"),
        })
    out.sort(key=lambda c: str(c.get("created") or ""), reverse=True)
    return out


def campaign_links(store) -> list:
    """Which link earned the clicks. A CTA nobody presses is a fact worth
    seeing next to the one they do."""
    counts = {}
    for e in _events(store):
        e = _D(e)
        if e.get("kind") != "click":
            continue
        u = str(e.get("url") or e.get("u") or "").strip()
        if u:
            counts[u] = counts.get(u, 0) + 1
    return sorted(({"url": u, "clicks": n} for u, n in counts.items()),
                  key=lambda r: -r["clicks"])


def open_curve(store, hours: int = 72) -> list:
    """Opens per hour after send, so you can see the first-hour spike and
    the long tail. Built from event timestamps only."""
    toks = _tokens(store)
    buckets = [0] * hours
    for e in _events(store):
        e = _D(e)
        if e.get("kind") != "open":
            continue
        meta = _D(toks.get(e.get("token")))
        base, at = meta.get("at"), e.get("at")
        if not (base and at):
            continue
        try:
            b = datetime.fromisoformat(str(base).replace("Z", "+00:00"))
            a = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            h = int((a - b).total_seconds() // 3600)
        except Exception:
            continue
        if 0 <= h < hours:
            buckets[h] += 1
    return buckets if any(buckets) else []


# ---------------------------------------------------------------------------
# PROFILES - one person, every event, in time order
# ---------------------------------------------------------------------------
def profiles(store, jobs=None, reply_drafts=None, limit: int = 400) -> list:
    """Every lead the engine has touched, with their own history.

    This is the object the old boards never had: a person, not a row in a
    campaign. It is assembled from the leads on each job, the send log, the
    token store and the event log."""
    toks = _tokens(store)
    evs = _events(store)
    tok_by_email = {}
    for t, meta in toks.items():
        em = str(_D(meta).get("email") or "").lower()
        if em:
            tok_by_email.setdefault(em, []).append((t, _D(meta)))
    ev_by_token = {}
    for e in evs:
        e = _D(e)
        if e.get("token"):
            ev_by_token.setdefault(e["token"], []).append(e)

    replied = set()
    for r in _L(reply_drafts):
        em = str(_D(r).get("from") or _D(r).get("email") or "").lower()
        if em:
            replied.add(em)

    people = {}
    for j in _out_jobs(jobs):
        p = _D(_D(j).get("payload"))
        sent_at = _D(p.get("sent_at"))
        for L in _L(p.get("leads")):
            L = _D(L)
            em = str(L.get("email") or "").lower()
            if not em:
                continue
            rec = people.setdefault(em, {
                "email": em, "name": L.get("name"),
                "company": L.get("company"), "title": L.get("title"),
                "country": L.get("country"), "vertical": L.get("vertical"),
                "score": L.get("score"), "sends": 0, "opens": 0,
                "clicks": 0, "replied": em in replied, "timeline": []})
            times = _L(sent_at.get(em))
            rec["sends"] += len(times)
            for i, ts in enumerate(times):
                rec["timeline"].append({"at": ts, "kind": "sent",
                                        "detail": f"touch {i + 1}"})
    for em, rec in people.items():
        for t, meta in tok_by_email.get(em, []):
            for e in ev_by_token.get(t, []):
                k = _D(e).get("kind")
                if k == "open":
                    rec["opens"] += 1
                elif k == "click":
                    rec["clicks"] += 1
                rec["timeline"].append({
                    "at": _D(e).get("at"), "kind": k,
                    "detail": str(_D(e).get("url") or "")[:70]
                    or f"step {meta.get('step') or '?'}"})
        if rec["replied"]:
            rec["timeline"].append({"at": "", "kind": "replied",
                                    "detail": "they wrote back"})
        rec["timeline"].sort(key=lambda x: str(x.get("at") or ""))
    rows = list(people.values())
    rows.sort(key=lambda r: (-(r["clicks"]), -(r["opens"]), -(r["sends"])))
    return rows[:limit]


def profile_stats(rows) -> dict:
    rows = _L(rows)
    engaged = [r for r in rows if r.get("clicks") or r.get("opens")]
    return {"people": len(rows) or None,
            "engaged": len(engaged) or None,
            "clickers": len([r for r in rows if r.get("clicks")]) or None,
            "repliers": len([r for r in rows if r.get("replied")]) or None}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = []

    def t(n, c):
        ok.append(bool(c))
        print(("  OK   " if c else "  FAIL ") + n)

    class _S:
        def __init__(self, d=None): self.d = dict(d or {})
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v

    jobs = [{"job_id": "j1", "type": "outreach_campaign",
             "created_at": "2026-08-01T09:00:00", "status": "sent",
             "payload": {"name": "Munich clinics",
                         "leads": [{"email": "a@x.de", "name": "Ann",
                                    "company": "X", "score": 80},
                                   {"email": "b@y.de", "name": "Bo",
                                    "company": "Y", "score": 60}],
                         "sent_at": {"a@x.de": ["2026-08-01T10:00:00"],
                                     "b@y.de": ["2026-08-01T10:00:00"]}}}]
    s = _S({"outreach_tokens": {
                "t1": {"job": "j1", "email": "a@x.de", "step": 1,
                       "at": "2026-08-01T10:00:00"},
                "t2": {"job": "j1", "email": "b@y.de", "step": 1,
                       "at": "2026-08-01T10:00:00"}},
            "outreach_events": [
                {"token": "t1", "kind": "open", "at": "2026-08-01T11:00:00"},
                {"token": "t1", "kind": "open", "at": "2026-08-01T12:00:00"},
                {"token": "t1", "kind": "click", "at": "2026-08-01T12:05:00",
                 "url": "https://anthropos-automation.com/book"}]})

    c = campaigns(s, jobs)[0]
    t("a campaign is built from real jobs", c["name"] == "Munich clinics")
    t("opens are unique by token, not raw events", c["opens"] == 1)
    t("recipients and sends are separate numbers",
      c["recipients"] == 2 and c["sent"] == 2)
    t("every rate carries its denominator", c["open_of"] == "1 of 2")
    t("CTOR is clicks over OPENS", c["ctor"] == 100.0 and c["ctor_of"] == "1 of 1")
    empty = campaigns(_S(), jobs)[0]
    t("an untracked campaign reports nothing, not zero",
      empty["opens"] is None and empty["open_of"] == "not tracked")

    links = campaign_links(s)
    t("clicks are attributed per link", links[0]["clicks"] == 1
      and "book" in links[0]["url"])
    curve = open_curve(s)
    t("the open curve is built from real timestamps",
      curve and curve[1] == 1 and curve[2] == 1)
    t("no curve when nothing opened", open_curve(_S()) == [])

    pr = profiles(s, jobs)
    t("a profile is a person, not a row", len(pr) == 2)
    ann = [r for r in pr if r["email"] == "a@x.de"][0]
    t("the profile counts her own events",
      ann["opens"] == 2 and ann["clicks"] == 1 and ann["sends"] == 1)
    t("the timeline is in time order",
      [x["kind"] for x in ann["timeline"]][:2] == ["sent", "open"])
    t("the engaged are ranked first", pr[0]["email"] == "a@x.de")
    st = profile_stats(pr)
    t("profile stats count real people",
      st["people"] == 2 and st["clickers"] == 1)
    t("the MPP caveat exists once, in words", "Apple Mail" in MPP_CAVEAT)
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
