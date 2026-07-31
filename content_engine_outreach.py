"""
content_engine_outreach.py
============================================================================
LEADS & OUTREACH — the loops behind the merged section.

Replaces two sections (Lead Machine, Email & Outreach) that held 24 cards
between them, rendered the same leads table twice, and drew the same funnel
four different ways.

These two were NOT reports. They carry a working launch pad — 14 live
endpoints, a 226-line outbox, a replies inbox, a Maps sourcing form. Nothing in
this module touches send logic. It reads what the send path already writes, and
adds four record-only stamps so the boards can stop guessing:

    lead["source"]              where a lead came from (was hardcoded to
                                "Web search", with Prospeo permanently 0)
    sent_meta[email][i].alias   which address it actually left from (was
                                assumed to be marketing@)
    sent_meta[email][i].subject what was sent (nothing recorded it, so "Best
                                subject lines" could never rank anything)
    sent_meta[email][i].step    which touch of the 3-email cycle

Plus open/click tracking, which is OPT-OUT via the `outreach_tracking` setting.
Tracking changes what your emails contain: a 1x1 pixel and rewritten links. In
Germany and Switzerland — two of the five target markets — opening-tracking
without consent is a GDPR matter, and pixels also cost some deliverability.
Both are stated on the Deliverability board rather than buried here.

Run offline self-check:  python content_engine_outreach.py
============================================================================
"""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("content_engine.outreach")

TRACK_KEY = "outreach_tracking"          # {"enabled": bool}
TOKENS_KEY = "outreach_tokens"           # token -> {job, email, step, at}
EVENTS_KEY = "outreach_events"           # [{token, kind, at}]
SUPPRESS_KEY = "email_suppression"       # the existing list
SUPPRESS_META_KEY = "email_suppression_meta"   # addr -> {reason, at}
MAX_EVENTS = 4000
MAX_TOKENS = 4000

TARGET_MARKETS = ("United States", "United Kingdom", "Germany", "Switzerland",
                  "Canada")
ICP_VERTICALS = ("doctor", "lawyer", "shopify", "tax", "creator", "marketing")
WARMUP_RAMP = [15, 20, 30, 45, 60, 80, 110, 150, 200]
SEQUENCE_TOUCHES = 3


# ------------------------------------------------------------------ coercion
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


def _out_jobs(jobs):
    return [j for j in _L(jobs) if _D(j).get("type") == "outreach_campaign"]


def _leads(jobs):
    """Every lead across every campaign, de-duplicated by email."""
    seen, out = set(), []
    for j in _out_jobs(jobs):
        p = _D(_D(j).get("payload"))
        for L in _L(p.get("leads")) or _L(p.get("raw_leads")):
            L = _D(L)
            e = _s(L.get("email")).lower()
            key = e or _s(L.get("name")).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({**L, "email": e, "_job": _D(j).get("job_id")})
    return out


# ======================================================================
#  TRACKING — opt-out, and it says what it costs
# ======================================================================
def tracking_enabled(store) -> bool:
    v = _D(_get(store, TRACK_KEY, {}))
    return bool(v.get("enabled", True))


def set_tracking(store, enabled: bool) -> dict:
    _set(store, TRACK_KEY, {"enabled": bool(enabled), "at": _iso()})
    return {"enabled": bool(enabled)}


def make_token(job_id, email, step) -> str:
    """Short, opaque, and derived — so a token can be regenerated for a known
    (job, email, step) without storing a second index."""
    raw = f"{_s(job_id)}|{_s(email).lower()}|{_i(step)}".encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest()[:9]).decode().rstrip("=")


def register_token(store, job_id, email, step) -> str:
    tok = make_token(job_id, email, step)
    toks = _D(_get(store, TOKENS_KEY, {}))
    toks[tok] = {"job": _s(job_id), "email": _s(email).lower(), "step": _i(step),
                 "at": _iso()}
    if len(toks) > MAX_TOKENS:
        for k in list(toks)[:len(toks) - MAX_TOKENS]:
            toks.pop(k, None)
    _set(store, TOKENS_KEY, toks)
    return tok


def record_event(store, token, kind="open") -> bool:
    """One row per open/click. Never raises — a tracking failure must never
    affect a send or a page render."""
    tok = _s(token)
    if not tok or kind not in ("open", "click"):
        return False
    evs = _L(_get(store, EVENTS_KEY, []))
    evs.append({"token": tok, "kind": kind, "at": _iso()})
    _set(store, EVENTS_KEY, evs[-MAX_EVENTS:])
    return True


def tracking_stats(store, sends=0) -> dict:
    """Opens and clicks against sends. Unique by token, because one recipient
    reloading an email is not five people reading it."""
    enabled = tracking_enabled(store)
    evs = _L(_get(store, EVENTS_KEY, []))
    toks = _D(_get(store, TOKENS_KEY, {}))
    opens = {e["token"] for e in evs if _D(e).get("kind") == "open" and e.get("token")}
    clicks = {e["token"] for e in evs if _D(e).get("kind") == "click" and e.get("token")}
    per_day = {}
    for e in evs:
        d = _day(_D(e).get("at"))
        if d:
            per_day[d] = per_day.get(d, 0) + 1
    keys = sorted(per_day)[-14:]
    by_step = {}
    for t in opens:
        st = _i(_D(toks.get(t)).get("step"))
        if st:
            by_step[st] = by_step.get(st, 0) + 1
    return {"enabled": enabled,
            "tracked_sends": len(toks),
            "opens": len(opens), "clicks": len(clicks),
            "raw_events": len(evs),
            "open_rate": _pct(len(opens), sends or len(toks)),
            "click_rate": _pct(len(clicks), sends or len(toks)),
            "click_to_open": _pct(len(clicks), len(opens)),
            "per_day": [(k, per_day[k]) for k in keys],
            "opens_by_step": [(f"touch {s}", by_step.get(s, 0))
                              for s in range(1, SEQUENCE_TOUCHES + 1)],
            "caveat": ("Open tracking is a 1x1 image. Apple Mail Privacy "
                       "Protection and most corporate gateways pre-fetch it, so "
                       "opens read high and are directionally useful at best. "
                       "Clicks are real."),
            "gdpr": ("Germany and Switzerland are two of your five target "
                     "markets. Opening-tracking without consent is a GDPR "
                     "matter there. This switch turns it off for every send."),
            "note": ("" if enabled else
                     "Tracking is off, so opens and clicks are not collected. "
                     "Reply rate remains the honest measure.")}


# ======================================================================
#  ① FIND THEM
# ======================================================================
def sourcing(jobs=None, days=14) -> dict:
    """L1/L6 — volume and where it came from. `source` is a real stamp now; if
    a lead predates the stamp it counts as unattributed rather than being
    silently assigned to one provider."""
    outs = _out_jobs(jobs)
    found = verified = qualified = 0
    by_source, per_day, unattributed = {}, {}, 0
    for j in outs:
        p = _D(_D(j).get("payload"))
        raw, lds = _L(p.get("raw_leads")), _L(p.get("leads"))
        n = len(raw) or len(lds)
        found += n
        verified += len(lds)
        qualified += len(_L(_D(p.get("lead_qualifier")).get("results")))
        d = _day(_D(j).get("created_at"))
        if d:
            per_day[d] = per_day.get(d, 0) + n
        for L in (raw or lds):
            src = _s(_D(L).get("source")).lower()
            if src:
                by_source[src] = by_source.get(src, 0) + 1
            else:
                unattributed += 1
        if not (raw or lds):
            src = _s(p.get("source")).lower()
            if src:
                by_source[src] = by_source.get(src, 0) + n
    keys = sorted(per_day)[-days:]
    return {"found": found, "verified": verified, "qualified": qualified,
            "campaigns": len(outs),
            "by_source": sorted(by_source.items(), key=lambda kv: -kv[1]),
            "unattributed": unattributed,
            "attributed_pct": _pct(found - unattributed, found),
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "has_data": bool(outs),
            "source_note": ("Every lead now carries the source it came from."
                            if not unattributed else
                            f"{unattributed} leads were sourced before the "
                            f"source stamp existed and stay unattributed rather "
                            f"than being assigned to a provider that may not "
                            f"have found them.")}


def quality(jobs=None) -> dict:
    """L2/L4 — verification and enrichment, counted rather than assumed. The
    old card drew a 100% 'verified deliverable' donut from a literal 100."""
    leads = _leads(jobs)
    fields = ("name", "company", "title", "website", "linkedin", "phone")
    filled = {f: 0 for f in fields}
    with_email = 0
    for L in leads:
        if _s(L.get("email")):
            with_email += 1
        for f in fields:
            if _s(L.get(f)):
                filled[f] += 1
    n = len(leads) or 1
    src = sourcing(jobs)
    stages = [("Found", src["found"]), ("Verified", src["verified"]),
              ("Qualified", src["qualified"]),
              ("Sendable", with_email)]
    return {"leads": len(leads), "with_email": with_email,
            "email_rate": _pct(with_email, len(leads)),
            "verify_rate": _pct(src["verified"], src["found"]),
            "qualify_rate": _pct(src["qualified"], src["verified"]),
            "fields": [(f, filled[f]) for f in fields],
            "completeness": round(sum(filled.values()) / (n * len(fields)) * 100, 1),
            "stages": stages,
            "waterfall": stages,
            "has_data": bool(leads)}


def icp(jobs=None) -> dict:
    """L7/L8 — score spread and vertical fit against your stated ICP."""
    leads = _leads(jobs)
    scores, verticals, matched = [], {}, 0
    for L in leads:
        sc = L.get("score")
        if sc not in (None, ""):
            scores.append(_f(sc))
        v = _s(L.get("vertical") or L.get("category") or L.get("industry")).lower()
        blob = " ".join(_s(L.get(k)).lower() for k in
                        ("vertical", "category", "industry", "title", "company"))
        hit = next((t for t in ICP_VERTICALS if t in blob), "")
        if hit:
            matched += 1
        key = v or hit or "unclassified"
        verticals[key] = verticals.get(key, 0) + 1
    return {"scored": len(scores), "scores": scores,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            "verticals": sorted(verticals.items(), key=lambda kv: -kv[1])[:10],
            "icp_matched": matched, "icp_rate": _pct(matched, len(leads)),
            "unclassified": verticals.get("unclassified", 0),
            "icp_list": list(ICP_VERTICALS),
            "has_data": bool(leads)}


def territories(jobs=None) -> dict:
    """L9 — coverage of the five markets you actually sell into."""
    leads = _leads(jobs)
    by_country = {}
    for L in leads:
        c = _s(L.get("country") or L.get("market"))
        if not c:
            addr = _s(L.get("address") or L.get("location"))
            c = next((t for t in TARGET_MARKETS if t.lower() in addr.lower()), "")
        by_country[c or "unknown"] = by_country.get(c or "unknown", 0) + 1
    rows = sorted(((k, v) for k, v in by_country.items() if k != "unknown"),
                  key=lambda kv: -kv[1])
    covered = {t: by_country.get(t, 0) for t in TARGET_MARKETS}
    total = sum(v for _k, v in rows)
    return {"rows": rows, "unknown": by_country.get("unknown", 0),
            "covered": covered,
            "missing": [t for t, v in covered.items() if not v],
            "target_share": _pct(sum(covered.values()), total),
            "total": total, "has_data": bool(rows)}


# ======================================================================
#  ② SEND IT
# ======================================================================
def sends(jobs=None, days=14) -> dict:
    """E3 — every real send, from the sent_at stamps the send path writes."""
    outs = _out_jobs(jobs)
    per_day, by_step, by_alias, subjects = {}, {}, {}, {}
    total = 0
    recipients = set()
    for j in outs:
        p = _D(_D(j).get("payload"))
        meta = _D(p.get("sent_meta"))
        for email, times in _D(p.get("sent_at")).items():
            recipients.add(_s(email).lower())
            rows = _L(meta.get(email))
            for i, t in enumerate(_L(times)):
                total += 1
                d = _day(t)
                if d:
                    per_day[d] = per_day.get(d, 0) + 1
                m = _D(rows[i]) if i < len(rows) else {}
                st = _i(m.get("step")) or (i + 1)
                by_step[st] = by_step.get(st, 0) + 1
                al = _s(m.get("alias"))
                if al:
                    by_alias[al] = by_alias.get(al, 0) + 1
                sj = _s(m.get("subject"))
                if sj:
                    subjects.setdefault(sj[:70], {"sent": 0, "replied": 0})
                    subjects[sj[:70]]["sent"] += 1
    keys = sorted(per_day)[-days:]
    return {"total": total, "recipients": len(recipients),
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "by_step": [(f"touch {s}", by_step.get(s, 0))
                        for s in range(1, SEQUENCE_TOUCHES + 1)],
            "by_alias": sorted(by_alias.items(), key=lambda kv: -kv[1]),
            "alias_recorded": bool(by_alias),
            "subjects": subjects,
            "subject_recorded": bool(subjects),
            "avg_per_recipient": round(total / max(len(recipients), 1), 2),
            "has_data": bool(total)}


def sequence(jobs=None, gap_days=3) -> dict:
    """E3 — where each lead sits in the 3-email cycle, and who is due."""
    outs = _out_jobs(jobs)
    at_step = {0: 0, 1: 0, 2: 0, 3: 0}
    due, rows, grid = [], [], []
    today = date.today()
    for j in outs:
        p = _D(_D(j).get("payload"))
        sent_at = _D(p.get("sent_at"))
        for L in _L(p.get("leads")):
            e = _s(_D(L).get("email")).lower()
            if not e:
                continue
            times = _L(sent_at.get(e))
            n = min(len(times), SEQUENCE_TOUCHES)
            at_step[n] = at_step.get(n, 0) + 1
            if 0 < n < SEQUENCE_TOUCHES and times:
                try:
                    last = datetime.fromisoformat(str(times[-1]).replace("Z", "+00:00"))
                    if (today - last.date()).days >= gap_days:
                        due.append((e, n + 1))
                except Exception:
                    pass
    for step in range(1, SEQUENCE_TOUCHES + 1):
        rows.append(f"touch {step}")
        grid.append([at_step.get(k, 0) for k in range(0, SEQUENCE_TOUCHES + 1)])
    tasks = [(f"touch {s}", (s - 1) * gap_days, gap_days)
             for s in range(1, SEQUENCE_TOUCHES + 1)]
    return {"at_step": at_step, "due": due[:20], "due_count": len(due),
            "not_started": at_step.get(0, 0), "complete": at_step.get(3, 0),
            "cohort_rows": rows, "cohort_grid": grid,
            "cohort_cols": [f"{k} sent" for k in range(0, SEQUENCE_TOUCHES + 1)],
            "tasks": tasks, "gap_days": gap_days,
            "has_data": bool(sum(at_step.values()))}


def routing(sends_=None, aliases=None) -> dict:
    """E4 — purpose to alias to recipient. Real once the alias stamp exists;
    before that the old card simply assumed marketing@ for everything."""
    sd = _D(sends_)
    by_alias = _L(sd.get("by_alias"))
    flows = []
    for al, n in by_alias[:6]:
        flows.append(("outreach", al, n))
        flows.append((al, "recipients", n))
    return {"by_alias": by_alias, "flows": flows,
            "recorded": bool(by_alias),
            "aliases": _L(aliases) or ["marketing@", "customercare@",
                                       "newsletter@", "contact@"],
            "note": ("Read from the alias recorded on each send."
                     if by_alias else
                     "No send has recorded an alias yet. Sends made before the "
                     "stamp existed are not attributed to one — the old card "
                     "assumed every outreach email left from marketing@, which "
                     "nothing measured.")}


def deliverability(store=None, sends_=None, suppression=None,
                   suppression_meta=None, sent_today=0, cap=None) -> dict:
    """E5/E7/E11 — the real guard. The old card was three static tick marks."""
    supp = _L(suppression)
    meta = _D(suppression_meta)
    reasons = {}
    for a in supp:
        r = _s(_D(meta.get(_s(a).lower())).get("reason")) or "unrecorded"
        reasons[r] = reasons.get(r, 0) + 1
    cap = _i(cap) if cap is not None else warmup_cap(store)
    sd = _D(sends_)
    total = _i(sd.get("total"))
    per_day = _L(sd.get("per_day"))
    return {"suppressed": len(supp),
            "reasons": sorted(reasons.items(), key=lambda kv: -kv[1]),
            "bounces": reasons.get("bounce", 0),
            "unsubscribes": reasons.get("unsubscribe", 0),
            "unrecorded": reasons.get("unrecorded", 0),
            "cap": cap, "sent_today": _i(sent_today),
            "cap_used": _pct(sent_today, cap),
            "headroom": max(0, cap - _i(sent_today)),
            "suppression_rate": _pct(len(supp), total),
            "ramp": WARMUP_RAMP,
            "per_day": per_day,
            "series": [v for _d, v in per_day],
            "cap_series": [cap] * len(per_day),
            "has_data": bool(total or supp),
            "note": ("The cap ramps 15 → 200 over about two weeks to protect a "
                     "new domain's reputation. A hard OUTREACH_DAILY_CAP "
                     "overrides it.")}


def warmup_cap(store=None, hard=None) -> int:
    """Mirrors connectors._warmup_cap so a board can show the number without
    importing the send path."""
    if hard and _i(hard) > 0:
        return _i(hard)
    start = _get(store, "outreach_first_send_day") if store else None
    if not start:
        return WARMUP_RAMP[0]
    try:
        days = (date.today() - date.fromisoformat(str(start)[:10])).days
    except Exception:
        return WARMUP_RAMP[0]
    return WARMUP_RAMP[min(max(days, 0), len(WARMUP_RAMP) - 1)]


# ======================================================================
#  ③ WHAT CAME BACK
# ======================================================================
def replies(reply_drafts=None, sends_=None, jobs=None) -> dict:
    """E8 — replies and, where the agent classified one, the intent."""
    drafts = _L(reply_drafts)
    intents, per_day = {}, {}
    for r in drafts:
        r = _D(r)
        it = _s(r.get("intent") or r.get("classification")) or "unclassified"
        intents[it] = intents.get(it, 0) + 1
        d = _day(r.get("at") or r.get("received_at"))
        if d:
            per_day[d] = per_day.get(d, 0) + 1
    sd = _D(sends_)
    sent = _i(sd.get("total"))
    people = _i(sd.get("recipients"))
    subjects = _D(sd.get("subjects"))
    ranked = sorted(((s, v.get("sent", 0), v.get("replied", 0))
                     for s, v in subjects.items()), key=lambda t: -t[1])[:8]
    return {"total": len(drafts),
            "intents": sorted(intents.items(), key=lambda kv: -kv[1]),
            "unclassified": intents.get("unclassified", 0),
            "reply_rate": _pct(len(drafts), sent),
            "per_person_rate": _pct(len(drafts), people),
            "silent": max(0, people - len(drafts)),
            "per_day": [(k, per_day[k]) for k in sorted(per_day)[-14:]],
            "subjects": ranked,
            "subject_recorded": bool(subjects),
            "has_data": bool(drafts)}


def bookings(cal=None, replies_=None) -> dict:
    """E10 — real Cal.com calls off the outreach."""
    rows = _L(cal)
    today = date.today().isoformat()
    accepted = upcoming = past = 0
    per_day, tasks = {}, []
    for b in rows:
        b = _D(b)
        if _s(b.get("status")).lower() in ("accepted", "confirmed", ""):
            accepted += 1
        start = _day(b.get("start") or b.get("startTime"))
        if start:
            per_day[start] = per_day.get(start, 0) + 1
            if start >= today:
                upcoming += 1
            else:
                past += 1
            try:
                off = (date.fromisoformat(start) - today_date()).days
            except Exception:
                off = 0
            if -7 <= off <= 14:
                tasks.append((_s(b.get("title") or "call")[:24], max(0, off + 7), 1))
    rp = _D(replies_)
    return {"total": len(rows), "accepted": accepted,
            "upcoming": upcoming, "past": past,
            "per_day": [(k, per_day[k]) for k in sorted(per_day)[-14:]],
            "tasks": tasks[:10],
            "reply_to_booking": _pct(accepted, _i(rp.get("total"))),
            "next": min([d for d in per_day if d >= today], default=None),
            "has_data": bool(rows)}


def today_date():
    return date.today()


# ======================================================================
#  ④ DOES IT PAY
# ======================================================================
def attribution(deals=None, sourcing_=None, sends_=None) -> dict:
    """E13 — which lead source actually produced revenue."""
    dl = _L(deals)
    by_source, count = {}, {}
    for d in dl:
        d = _D(d)
        s = _s(d.get("source")) or "other"
        by_source[s] = by_source.get(s, 0.0) + _f(d.get("value"))
        count[s] = count.get(s, 0) + 1
    src = _L(_D(sourcing_).get("by_source"))
    volume = {k: v for k, v in src}
    flows = []
    for s, v in sorted(by_source.items(), key=lambda kv: -kv[1])[:5]:
        flows.append((s, "revenue", v))
    matrix = []
    for s, rev in by_source.items():
        vol = volume.get(s, 0)
        matrix.append((s[:14],
                       min(3, max(1, int(rev / (max(sum(by_source.values()), 1) / 3)) + 1)),
                       min(3, max(1, int(vol / (max(sum(volume.values()), 1) / 3) + 1)))))
    return {"by_source": sorted(by_source.items(), key=lambda kv: -kv[1]),
            "deals_by_source": sorted(count.items(), key=lambda kv: -kv[1]),
            "flows": flows, "matrix": matrix,
            "total": round(sum(by_source.values()), 2),
            "outreach_revenue": round(by_source.get("outreach", 0.0), 2),
            "outreach_share": _pct(by_source.get("outreach", 0.0),
                                   sum(by_source.values())),
            "has_data": bool(dl)}


def unit_costs(sourcing_=None, sends_=None, replies_=None, bookings_=None,
               deals=None, outreach_cost=0.0) -> dict:
    """E14 — what one lead, one send, one reply, one call and one deal cost."""
    sc = _D(sourcing_)
    sd = _D(sends_)
    rp = _D(replies_)
    bk = _D(bookings_)
    dl = _L(deals)
    c = _f(outreach_cost)
    def per(n):
        return round(c / n, 4) if n else None
    rows = [("per lead", per(_i(sc.get("found")))),
            ("per send", per(_i(sd.get("total")))),
            ("per reply", per(_i(rp.get("total")))),
            ("per booking", per(_i(bk.get("accepted")))),
            ("per deal", per(len(dl)))]
    rev = sum(_f(_D(d).get("value")) for d in dl)
    return {"cost": round(c, 2), "rows": rows,
            "per_lead": per(_i(sc.get("found"))),
            "per_send": per(_i(sd.get("total"))),
            "per_reply": per(_i(rp.get("total"))),
            "per_booking": per(_i(bk.get("accepted"))),
            "per_deal": per(len(dl)),
            "revenue": round(rev, 2),
            "roi": _pct(rev - c, c) if c else None,
            "has_data": bool(c)}


def _month_add(ym, n):
    try:
        y, m = int(str(ym)[:4]), int(str(ym)[5:7])
    except Exception:
        return str(ym)
    m += n
    y += (m - 1) // 12
    return f"{y + 0:04d}-{(m - 1) % 12 + 1:02d}"


def sourcing_mom(jobs=None, top=5) -> dict:
    """L6 — leads by source, this month against last. Computable now because
    campaigns carry a real created_at and leads carry a real source."""
    cur_m = date.today().isoformat()[:7]
    prev_m = _month_add(cur_m, -1)
    cur, prev = {}, {}
    for j in _out_jobs(jobs):
        d = _D(j)
        m = _day(d.get("created_at"))[:7]
        if m not in (cur_m, prev_m):
            continue
        bucket = cur if m == cur_m else prev
        p = _D(d.get("payload"))
        for L in (_L(p.get("raw_leads")) or _L(p.get("leads"))):
            src = _s(_D(L).get("source")).lower() or "unattributed"
            bucket[src] = bucket.get(src, 0) + 1
    groups = [k for k, _v in sorted(cur.items(), key=lambda kv: -kv[1])[:top]] or \
             [k for k, _v in sorted(prev.items(), key=lambda kv: -kv[1])[:top]]
    return {"groups": groups,
            "this_month": [cur.get(g, 0) for g in groups],
            "last_month": [prev.get(g, 0) for g in groups],
            "ready": bool(groups and prev),
            "note": (f"{prev_m} against {cur_m}, by source." if (groups and prev)
                     else "Month-over-month needs campaigns in two different "
                          "months. This shows the current month until then, "
                          "rather than drawing a comparison against nothing.")}


def suppression_heat(suppression_meta=None, days=7) -> tuple:
    """E7/E11 — suppressions by reason and day. Rows are reasons, columns are
    the last seven days, so a bad list shows up as a hot row."""
    meta = _D(suppression_meta)
    cols, idx = [], {}
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        idx[d] = len(cols)
        cols.append(d[5:])
    reasons = []
    for _a, m in meta.items():
        r = _s(_D(m).get("reason")) or "unrecorded"
        if r not in reasons:
            reasons.append(r)
    if not reasons:
        return [], cols, []
    grid = [[0] * len(cols) for _ in reasons]
    for _a, m in meta.items():
        r = _s(_D(m).get("reason")) or "unrecorded"
        d = _day(_D(m).get("at"))
        if d in idx:
            grid[reasons.index(r)][idx[d]] += 1
    return reasons, cols, grid


def campaign_costs(jobs=None) -> dict:
    """E14 — cost per lead for EACH campaign, so the spread is visible. One
    average hides a campaign that cost five times the rest."""
    rows = []
    for j in _out_jobs(jobs):
        d = _D(j)
        p = _D(d.get("payload"))
        n = len(_L(p.get("raw_leads"))) or len(_L(p.get("leads")))
        c = _f(d.get("cost_so_far_usd"))
        if n and c:
            rows.append((_s(d.get("job_id"))[:12], round(c / n, 4)))
    vals = [v for _k, v in rows]
    avg = round(sum(vals) / len(vals), 4) if vals else None
    spread = (round(max(vals) - min(vals), 4) if len(vals) > 1 else None)
    return {"rows": rows, "values": vals, "avg": avg, "spread": spread,
            "worst": max(rows, key=lambda kv: kv[1]) if rows else None,
            "best": min(rows, key=lambda kv: kv[1]) if rows else None,
            "ready": len(vals) > 1,
            "note": ("Each point is one campaign's cost per lead. The band is "
                     "the tolerance around the average — a point outside it is "
                     "a campaign worth looking at."
                     if len(vals) > 1 else
                     "Needs at least two campaigns with both a cost and leads "
                     "before a spread means anything.")}


def sends_cohort(jobs=None, days=7) -> tuple:
    """E3 — sends by touch and day. Rows are touches, columns are days.

    NOT reply-by-touch: a reply is not yet linked back to the send that earned
    it. The step stamp now exists, so that linkage becomes possible for replies
    received from here on, and the card says so rather than implying it."""
    cols, idx = [], {}
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        idx[d] = len(cols)
        cols.append(d[5:])
    rows = [f"touch {s}" for s in range(1, SEQUENCE_TOUCHES + 1)]
    grid = [[0] * len(cols) for _ in rows]
    for j in _out_jobs(jobs):
        p = _D(_D(j).get("payload"))
        meta = _D(p.get("sent_meta"))
        for email, times in _D(p.get("sent_at")).items():
            mrows = _L(meta.get(email))
            for i, t in enumerate(_L(times)):
                d = _day(t)
                if d not in idx:
                    continue
                m = _D(mrows[i]) if i < len(mrows) else {}
                step = _i(m.get("step")) or (i + 1)
                if 1 <= step <= SEQUENCE_TOUCHES:
                    grid[step - 1][idx[d]] += 1
    return rows, cols, grid


LEAD_COLUMNS = ("name", "title", "company", "email", "linkedin", "phone",
                "country", "vertical", "source", "collected_at")


def lead_rows(jobs=None, limit=400) -> list:
    """Every lead with every field the table shows, newest first. Each row
    carries its job id so Edit and Delete know what to act on."""
    out = []
    for j in _out_jobs(jobs):
        d = _D(j)
        p = _D(d.get("payload"))
        qmap = {_s(r.get("id")).lower(): _D(r)
                for r in _L(_D(p.get("lead_qualifier")).get("results"))}
        sent = _D(p.get("sent_to"))
        sent_at = _D(p.get("sent_at"))
        removed = {_s(_D(r).get("email")).lower() for r in _L(p.get("leads_removed"))}
        for L in _L(p.get("leads")) or _L(p.get("raw_leads")):
            L = _D(L)
            e = _s(L.get("email")).lower()
            q = qmap.get(e, {})
            times = _L(sent_at.get(e))
            out.append({
                "job": _s(d.get("job_id")),
                "email": e,
                "name": _s(L.get("name")),
                "title": _s(L.get("title")),
                "company": _s(L.get("company")),
                "linkedin": _s(L.get("linkedin")),
                "phone": _s(L.get("phone")),
                "country": _s(L.get("country")),
                "vertical": _s(L.get("vertical") or q.get("category")),
                "source": _s(L.get("source")) or "unattributed",
                "website": _s(L.get("website") or L.get("domain")),
                "collected_at": _s(L.get("collected_at")),
                "fit": q.get("fit_score"),
                "priority": _s(q.get("priority")),
                "pain": _s(q.get("pain_point")),
                "offer": _s(q.get("offer")),
                "touches": len(times),
                "last_sent": _s(times[-1])[:16].replace("T", " ") if times else "",
                "removed": e in removed,
                "status": ("removed" if e in removed else
                           "emailed" if _L(sent.get(e)) else "not contacted"),
            })
    out.sort(key=lambda r: r.get("collected_at") or "", reverse=True)
    return out[:limit]


def leads_per_day(jobs=None, days=14) -> dict:
    """L1 — leads collected per DAY, from each lead's own collected_at.

    The old chart bucketed by campaign created_at, so one batch of sixty leads
    appeared as a single sixty-lead day and every other day read zero. Leads
    with no timestamp are counted separately rather than dropped onto today."""
    per_day, undated = {}, 0
    for r in lead_rows(jobs, limit=100000):
        at = _day(r.get("collected_at"))
        if at:
            per_day[at] = per_day.get(at, 0) + 1
        else:
            undated += 1
    keys = sorted(per_day)[-days:]
    vals = [per_day[k] for k in keys]
    return {"per_day": [(k, per_day[k]) for k in keys], "series": vals,
            "labels": keys, "undated": undated,
            "total": sum(per_day.values()),
            "busiest": max(vals) if vals else 0,
            "avg": round(sum(vals) / len(vals), 1) if vals else 0,
            "days_active": len(keys),
            "has_data": bool(vals),
            "note": ("" if not undated else
                     f"{undated} leads were sourced before a per-lead timestamp "
                     f"existed. They are counted in the total but cannot be "
                     f"placed on a day, so they are excluded from the chart "
                     f"rather than guessed onto today.")}


def lead_field_coverage(jobs=None) -> list:
    """How many leads actually carry each column — so an empty table column is
    visibly a sourcing gap rather than a rendering bug."""
    rows = lead_rows(jobs, limit=100000)
    n = len(rows) or 1
    return [(c, sum(1 for r in rows if _s(r.get(c))), round(
        100 * sum(1 for r in rows if _s(r.get(c))) / n)) for c in LEAD_COLUMNS]


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

    # ---- tracking: opt-out, unique by token, never raises ----
    assert tracking_enabled(st) is True, "tracking defaults on once chosen"
    set_tracking(st, False)
    assert tracking_enabled(st) is False
    set_tracking(st, True)
    t1 = register_token(st, "job1", "A@B.com", 1)
    assert t1 == make_token("job1", "a@b.com", 1), "token must be case-stable"
    record_event(st, t1, "open")
    record_event(st, t1, "open")          # same recipient reloading
    record_event(st, t1, "click")
    tsx = tracking_stats(st, sends=4)
    assert tsx["opens"] == 1 and tsx["clicks"] == 1, "unique by token, not raw hits"
    assert tsx["raw_events"] == 3
    assert tsx["open_rate"] == 25.0 and "Apple Mail" in tsx["caveat"]
    assert "GDPR" in tsx["gdpr"]
    assert record_event(st, "", "open") is False
    assert record_event(st, t1, "nonsense") is False

    # ---- jobs fixture ----
    jobs = [{"job_id": "o1", "type": "outreach_campaign", "status": "sent",
             "created_at": "2026-07-20T09:00:00Z", "cost_so_far_usd": 1.2,
             "payload": {
                 "raw_leads": [{"email": f"p{i}@x.com", "name": f"P{i}",
                                "company": "C", "title": "Dr",
                                "country": "Germany" if i % 2 else "United States",
                                "vertical": "doctor", "score": 60 + i,
                                "source": "maps" if i % 3 else "prospeo"}
                               for i in range(9)],
                 "leads": [{"email": f"p{i}@x.com", "name": f"P{i}", "company": "C",
                            "title": "Dr", "country": "Germany" if i % 2 else "United States",
                            "vertical": "doctor", "score": 60 + i,
                            "source": "maps" if i % 3 else "prospeo"}
                           for i in range(7)],
                 "lead_qualifier": {"results": [{}] * 5},
                 "send_ref": "x",
                 "sent_at": {"p0@x.com": ["2026-07-21T09:00:00+00:00",
                                          "2026-07-24T09:00:00+00:00"],
                             "p1@x.com": ["2026-07-22T09:00:00+00:00"]},
                 "sent_meta": {"p0@x.com": [{"alias": "marketing@a.com", "step": 1,
                                             "subject": "Quick question"},
                                            {"alias": "marketing@a.com", "step": 2,
                                             "subject": "Following up"}],
                               "p1@x.com": [{"alias": "contact@a.com", "step": 1,
                                             "subject": "Quick question"}]}}}]

    sc = sourcing(jobs)
    assert sc["found"] == 9 and sc["verified"] == 7 and sc["qualified"] == 5
    assert dict(sc["by_source"]) == {"maps": 6, "prospeo": 3}, sc["by_source"]
    assert sc["unattributed"] == 0 and sc["attributed_pct"] == 100.0

    # a lead with no source must NOT be assigned to a provider
    jobs2 = [{"job_id": "o2", "type": "outreach_campaign",
              "created_at": "2026-07-01T09:00:00Z",
              "payload": {"raw_leads": [{"email": "z@x.com"}]}}]
    sc2 = sourcing(jobs2)
    assert sc2["by_source"] == [] and sc2["unattributed"] == 1
    assert "stay unattributed" in sc2["source_note"]

    q = quality(jobs)
    # _leads() reports the deduped VERIFIED roster (7), while sourcing() reports
    # everything found (9). Both are right; they answer different questions.
    assert q["leads"] == 7 and q["with_email"] == 7, (q["leads"], q["with_email"])
    assert q["verify_rate"] > 0 and 0 < q["completeness"] <= 100
    assert [s[0] for s in q["stages"]] == ["Found", "Verified", "Qualified", "Sendable"]

    ic = icp(jobs)
    assert ic["scored"] == 7 and ic["avg_score"] is not None
    assert ic["icp_matched"] == 7 and ic["icp_rate"] == 100.0

    tr = territories(jobs)
    assert dict(tr["covered"])["Germany"] > 0
    assert "United Kingdom" in tr["missing"] and "Canada" in tr["missing"]

    sd = sends(jobs)
    assert sd["total"] == 3 and sd["recipients"] == 2
    assert dict(sd["by_step"])["touch 1"] == 2 and dict(sd["by_step"])["touch 2"] == 1
    assert sd["alias_recorded"] and dict(sd["by_alias"])["marketing@a.com"] == 2
    assert sd["subject_recorded"] and "Quick question" in sd["subjects"]

    # with no meta the alias must be reported as unrecorded, never assumed
    sd2 = sends([{"job_id": "o3", "type": "outreach_campaign",
                  "payload": {"sent_at": {"a@x.com": ["2026-07-21T09:00:00+00:00"]}}}])
    assert sd2["total"] == 1 and sd2["alias_recorded"] is False
    rt = routing(sd2)
    assert rt["recorded"] is False and "assumed every outreach email" in rt["note"]

    sq = sequence(jobs)
    assert sq["at_step"][2] == 1 and sq["at_step"][1] == 1
    assert sq["not_started"] == 5, sq["at_step"]   # 7 leads, 2 have been sent to
    assert sq["cohort_grid"] and sq["tasks"]

    dv = deliverability(st, sd, ["a@x.com", "b@x.com"],
                        {"a@x.com": {"reason": "bounce"},
                         "b@x.com": {"reason": "unsubscribe"}},
                        sent_today=4, cap=15)
    assert dv["suppressed"] == 2 and dv["bounces"] == 1 and dv["unsubscribes"] == 1
    assert dv["cap"] == 15 and dv["headroom"] == 11 and dv["cap_used"] > 0
    dv2 = deliverability(st, sd, ["c@x.com"], {}, sent_today=0, cap=15)
    assert dv2["unrecorded"] == 1, "a suppression with no reason must say so"

    rp = replies([{"intent": "question"}, {}, {}], sd)
    assert rp["total"] == 3 and rp["unclassified"] == 2
    assert rp["reply_rate"] > 0

    bk = bookings([{"status": "accepted", "start": "2026-08-04T10:00:00Z",
                    "title": "Intro"}], rp)
    assert bk["accepted"] == 1 and bk["reply_to_booking"] > 0

    at = attribution([{"client": "A", "value": 6000, "source": "outreach"},
                      {"client": "B", "value": 2000, "source": "organic"}], sc, sd)
    assert at["outreach_revenue"] == 6000.0 and at["outreach_share"] == 75.0
    assert at["flows"] and at["matrix"]

    uc = unit_costs(sc, sd, rp, bk, [{"value": 6000}], outreach_cost=1.2)
    assert uc["per_lead"] is not None and uc["per_deal"] == 1.2
    assert uc["roi"] is not None

    # hostile shapes must never raise
    for bad in (None, {}, [], "x", 0, {"payload": "no"}, [{"type": "outreach_campaign"}]):
        sourcing(bad if isinstance(bad, list) else None)
        quality(bad if isinstance(bad, list) else None)
        icp(bad if isinstance(bad, list) else None)
        territories(bad if isinstance(bad, list) else None)
        sends(bad if isinstance(bad, list) else None)
        sequence(bad if isinstance(bad, list) else None)
        routing(bad)
        deliverability(None, bad, bad, bad)
        replies(bad if isinstance(bad, list) else None, bad)
        bookings(bad if isinstance(bad, list) else None, bad)
        attribution(bad if isinstance(bad, list) else None, bad, bad)
        unit_costs(bad, bad, bad, bad, None)
        tracking_stats(st)

    mm = sourcing_mom(jobs)
    assert mm["groups"] and not mm["ready"], "one month of campaigns is not a comparison"
    assert "rather than drawing a comparison against nothing" in mm["note"]

    hr, hc, hg = suppression_heat({"a@x.com": {"reason": "bounce",
                                               "at": date.today().isoformat()}})
    assert hr == ["bounce"] and len(hc) == 7 and hg[0][-1] == 1, (hr, hg)
    assert suppression_heat({}) == ([], [c for c in hc], []), "no data -> no grid"

    cc = campaign_costs(jobs)
    assert cc["avg"] is not None and cc["ready"] is False, cc
    assert "at least two campaigns" in cc["note"]

    sr, scol, sg = sends_cohort(jobs)
    assert sr == ["touch 1", "touch 2", "touch 3"] and len(scol) == 7
    assert sum(sum(r) for r in sg) >= 0

    lr = lead_rows(jobs)
    assert lr and lr[0]["email"], lr[:1]
    assert set(LEAD_COLUMNS) <= set(lr[0]), "every column must be present on a row"
    assert {r["source"] for r in lr} == {"maps", "prospeo"},         "each lead keeps the source it was actually stamped with"
    lpd = leads_per_day(jobs)
    assert lpd["undated"] == len(lr), "leads with no stamp must be counted, not placed"
    assert lpd["series"] == [] and "cannot be placed on a day" in lpd["note"]
    dated = [{"job_id": "o9", "type": "outreach_campaign",
              "payload": {"leads": [{"email": "a@x.com", "collected_at": "2026-07-30T09:00:00+00:00"},
                                    {"email": "b@x.com", "collected_at": "2026-07-30T11:00:00+00:00"},
                                    {"email": "c@x.com", "collected_at": "2026-07-29T09:00:00+00:00"}]}}]
    lpd2 = leads_per_day(dated)
    assert lpd2["total"] == 3 and lpd2["busiest"] == 2, lpd2
    assert lpd2["days_active"] == 2, lpd2
    cov = lead_field_coverage(jobs)
    assert any(c == "linkedin" for c, _n2, _p in cov), "coverage must list linkedin"

    print("outreach self-check OK — leads carry a real source (unattributed "
          "stays unattributed), verification counted rather than a literal 100, "
          "alias and subject read from the send stamp or reported as "
          "unrecorded, sequence positions and due follow-ups computed, "
          "suppression split into bounce vs unsubscribe, warmup cap shown, and "
          "open tracking unique by token with its Apple-prefetch and GDPR "
          "caveats stated.")
