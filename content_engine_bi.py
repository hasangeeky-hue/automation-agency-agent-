"""
content_engine_bi.py
============================================================================
BUSINESS INTELLIGENCE — the loops behind the merged BI section.

Replaces six sections (Business Performance, Marketing Intelligence, Sales
Intelligence, Customer Intelligence, Finance, Budget & Cost) that between them
held 41 cards and read ONE shared context dict.

The rule for this module: a number is either measured or it is absent. Nothing
here invents a value, and nothing renders a metric that has no input path.
That is why record_deal() exists — revenue, customers and unit economics had
no way in, so every card that needed them was permanently blank. Two minutes of
typing per won deal turns three boards live, with no Stripe, no CRM, no vendor.

It also fixes a disconnect between two things already shipped:
POST /jobs/{id}/outcome accepted leads/revenue/customers but NOT the client
name, while concentration() and revenue_path() on the Risk board key on
outcome.client — so revenue concentration could never populate. Deals recorded
here carry the client, and read back into both.

Run offline self-check:  python content_engine_bi.py
============================================================================
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

log = logging.getLogger("content_engine.bi")

DEALS_KEY = "bi_deals"
TARGETS_KEY = "bi_targets"
ECON_KEY = "bi_econ"
MAX_DEALS = 500

SOURCES = ("outreach", "organic", "ads", "referral", "direct", "other")


# ------------------------------------------------------------------ coercion
def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return list(v) if isinstance(v, (list, tuple)) else []


def _f(v, default=0.0):
    try:
        if isinstance(v, str):
            v = v.replace(",", "").replace("€", "").replace("$", "").strip()
        return float(v)
    except Exception:
        return float(default)


def _i(v, default=0):
    try:
        return int(_f(v, default))
    except Exception:
        return int(default)


def _iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def _day(v):
    return str(v or "")[:10]


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


def _pct(part, whole, nd=1):
    w = _f(whole)
    return round(100 * _f(part) / w, nd) if w else 0.0


def _slug(s):
    return "".join(ch if ch.isalnum() else "-" for ch in str(s).lower()).strip("-")[:40]


# ======================================================================
#  DEALS — the input path that did not exist
# ======================================================================
def list_deals(store) -> list:
    """Recorded won deals, newest first. Always a list of well-formed dicts."""
    out = []
    for d in _L(_get(store, DEALS_KEY, [])):
        d = _D(d)
        if not d.get("client"):
            continue
        out.append({
            "id": str(d.get("id") or _slug(d.get("client")) + "-" + _day(d.get("at"))),
            "client": str(d.get("client"))[:80],
            "value": _f(d.get("value")),
            "at": _day(d.get("at")) or _day(_iso()),
            "source": (str(d.get("source")).lower()
                       if str(d.get("source")).lower() in SOURCES else "other"),
            "margin_pct": _f(d.get("margin_pct")) or None,
            "recurring": bool(d.get("recurring")),
            "note": str(d.get("note") or "")[:240],
        })
    return sorted(out, key=lambda d: d["at"], reverse=True)


def record_deal(store, client, value, source="other", at=None, margin_pct=None,
                recurring=False, note="") -> dict:
    """Record a won deal. The one write that makes revenue, customers and unit
    economics computable."""
    client = str(client or "").strip()
    if not client:
        return {"ok": False, "error": "a client name is required"}
    if _f(value) <= 0:
        return {"ok": False, "error": "deal value must be greater than zero"}
    deals = _L(_get(store, DEALS_KEY, []))
    when = _day(at) or _day(_iso())
    deal = {"id": f"{_slug(client)}-{when}-{len(deals) + 1}",
            "client": client[:80], "value": _f(value), "at": when,
            "source": str(source or "other").lower(),
            "margin_pct": _f(margin_pct) if margin_pct not in (None, "") else None,
            "recurring": bool(recurring), "note": str(note or "")[:240],
            "recorded_at": _iso()}
    deals.append(deal)
    _set(store, DEALS_KEY, deals[-MAX_DEALS:])
    return {"ok": True, "deal": deal, "total_deals": len(deals)}


def delete_deal(store, deal_id) -> bool:
    deals = _L(_get(store, DEALS_KEY, []))
    kept = [d for d in deals if str(_D(d).get("id")) != str(deal_id)]
    if len(kept) == len(deals):
        return False
    _set(store, DEALS_KEY, kept)
    return True


def econ(store) -> dict:
    """The three numbers only you can supply. Absent is absent — never guessed."""
    e = _D(_get(store, ECON_KEY, {}))
    return {"avg_deal": _f(e.get("avg_deal")) or None,
            "margin_pct": _f(e.get("margin_pct")) or None,
            "consult_to_client_pct": _f(e.get("consult_to_client_pct")) or None,
            "set": bool(e.get("avg_deal") or e.get("margin_pct")
                        or e.get("consult_to_client_pct"))}


def set_econ(store, avg_deal=None, margin_pct=None, consult_to_client_pct=None) -> dict:
    e = _D(_get(store, ECON_KEY, {}))
    if avg_deal not in (None, ""):
        e["avg_deal"] = _f(avg_deal)
    if margin_pct not in (None, ""):
        e["margin_pct"] = _f(margin_pct)
    if consult_to_client_pct not in (None, ""):
        e["consult_to_client_pct"] = _f(consult_to_client_pct)
    _set(store, ECON_KEY, e)
    return e


def targets(store) -> dict:
    t = _D(_get(store, TARGETS_KEY, {}))
    return {"revenue_month": _f(t.get("revenue_month")) or None,
            "deals_month": _i(t.get("deals_month")) or None,
            "leads_month": _i(t.get("leads_month")) or None,
            "bookings_month": _i(t.get("bookings_month")) or None,
            "set": bool(t)}


def set_targets(store, **kw) -> dict:
    t = _D(_get(store, TARGETS_KEY, {}))
    for k in ("revenue_month", "deals_month", "leads_month", "bookings_month"):
        if kw.get(k) not in (None, ""):
            t[k] = _f(kw[k])
    _set(store, TARGETS_KEY, t)
    return t


# ======================================================================
#  ① DEMAND
# ======================================================================
def _ga4(insights):
    return _D(_D(insights).get("ga4"))


def _gsc(insights):
    g = _D(insights).get("gsc")
    if isinstance(g, dict):
        g = g.get("queries") or g.get("rows") or []
    return _L(g)


def demand(insights=None, days=28) -> dict:
    """D1/D2 — sessions and search demand as measured by GA4 and GSC."""
    ga = _ga4(insights)
    daily = _L(ga.get("daily"))
    series, labels = [], []
    for r in daily:
        r = _D(r)
        labels.append(_day(r.get("date")))
        series.append(_f(r.get("sessions")))
    totals = _D(ga.get("totals"))
    rows = _gsc(insights)
    clicks = sum(_f(_D(r).get("clicks")) for r in rows)
    impressions = sum(_f(_D(r).get("impressions")) for r in rows)
    positions = [_f(_D(r).get("position")) for r in rows if _D(r).get("position")]
    half = max(1, len(series) // 2)
    first, second = series[:half], series[half:]
    trend = None
    if len(series) >= 4 and sum(first):
        trend = round(100 * (sum(second) - sum(first)) / sum(first), 1)
    return {
        "has_ga4": bool(daily or totals),
        "has_gsc": bool(rows),
        "sessions": _i(totals.get("sessions")) or int(sum(series)),
        "users": _i(totals.get("totalUsers")),
        "new_users": _i(totals.get("newUsers")),
        "engagement_rate": round(_f(totals.get("engagementRate")) * 100, 1)
        if totals.get("engagementRate") else None,
        "series": series, "labels": labels,
        "trend_pct": trend,
        "clicks": int(clicks), "impressions": int(impressions),
        "ctr": _pct(clicks, impressions, 2),
        "avg_position": round(sum(positions) / len(positions), 1) if positions else None,
        "queries": len(rows),
        "top_queries": sorted(
            [{"query": str(_D(r).get("query") or (_L(_D(r).get("keys")) or [""])[0]),
              "clicks": _f(_D(r).get("clicks")),
              "impressions": _f(_D(r).get("impressions")),
              "position": _f(_D(r).get("position"))} for r in rows],
            key=lambda r: -r["clicks"])[:12],
        "days": days,
    }


def markets(insights=None) -> dict:
    """D3 — where demand actually comes from."""
    ga = _ga4(insights)
    rows = []
    for r in _L(ga.get("countries")):
        r = _D(r)
        name = str(r.get("country") or r.get("name") or "").strip()
        if name and name.lower() != "(not set)":
            rows.append((name, _f(r.get("sessions"))))
    rows.sort(key=lambda kv: -kv[1])
    total = sum(v for _n, v in rows)
    TARGET = {"United States": "USA", "United Kingdom": "UK", "Germany": "Germany",
              "Switzerland": "Switzerland", "Canada": "Canada"}
    covered = {t: 0.0 for t in TARGET.values()}
    for name, v in rows:
        if name in TARGET:
            covered[TARGET[name]] += v
    return {"rows": rows[:12], "total": total,
            "top": rows[0] if rows else None,
            "target_markets": covered,
            "target_share": _pct(sum(covered.values()), total),
            "missing": [m for m, v in covered.items() if not v],
            "has_data": bool(rows)}


def channel_mix(insights=None) -> dict:
    """D4 — organic vs paid vs direct vs referral."""
    ga = _ga4(insights)
    rows = []
    for r in _L(ga.get("channels")):
        r = _D(r)
        name = str(r.get("sessionDefaultChannelGroup") or r.get("channel")
                   or r.get("name") or "").strip()
        if name:
            rows.append((name, _f(r.get("sessions"))))
    rows.sort(key=lambda kv: -kv[1])
    total = sum(v for _n, v in rows) or 0
    top_share = _pct(rows[0][1], total) if rows else 0.0
    return {"rows": rows, "total": total,
            "top": rows[0] if rows else None,
            "top_share": top_share,
            "concentrated": top_share >= 70,
            "count": len(rows),
            "has_data": bool(rows)}


def content_attribution(insights=None, jobs=None) -> dict:
    """D5 — which published pages actually pull traffic."""
    ga = _ga4(insights)
    pages = []
    for r in _L(ga.get("pages")):
        r = _D(r)
        p = str(r.get("pagePath") or r.get("page") or "").strip()
        if p:
            pages.append((p[:44], _f(r.get("sessions"))))
    pages.sort(key=lambda kv: -kv[1])
    published = [j for j in _L(jobs)
                 if _D(j).get("status") in ("published", "optimized")]
    total = sum(v for _p, v in pages)
    top5 = sum(v for _p, v in pages[:5])
    return {"pages": pages[:10], "total": total,
            "published": len(published),
            "top5_share": _pct(top5, total),
            "carrying": len([p for p in pages if p[1] > 0]),
            "has_data": bool(pages)}


# ======================================================================
#  ② PIPELINE
# ======================================================================
def _out_jobs(jobs):
    return [j for j in _L(jobs) if _D(j).get("type") == "outreach_campaign"]


def leadgen(jobs=None, days=14) -> dict:
    """P1/P2 — how many leads, from where, and how many survive verification."""
    outs = _out_jobs(jobs)
    found = verified = qualified = 0
    by_source, per_day = {}, {}
    for j in outs:
        p = _D(_D(j).get("payload"))
        raw = _L(p.get("raw_leads"))
        lds = _L(p.get("leads"))
        found += len(raw) or len(lds)
        verified += len(lds)
        qualified += len(_L(_D(p.get("lead_qualifier")).get("results")))
        src = str(p.get("source") or p.get("lead_source") or "outreach").lower()
        by_source[src] = by_source.get(src, 0) + (len(raw) or len(lds))
        d = _day(_D(j).get("created_at"))
        if d:
            per_day[d] = per_day.get(d, 0) + (len(raw) or len(lds))
    keys = sorted(per_day)[-days:]
    return {"found": found, "verified": verified, "qualified": qualified,
            "verify_rate": _pct(verified, found),
            "qualify_rate": _pct(qualified, verified),
            "by_source": sorted(by_source.items(), key=lambda kv: -kv[1]),
            "per_day": [(k, per_day[k]) for k in keys],
            "distribution": [per_day[k] for k in keys],
            "campaigns": len(outs),
            "has_data": bool(outs)}


def outreach(jobs=None, reply_drafts=None, days=14) -> dict:
    """P3 — sent to replied, and the shape of it by day."""
    outs = _out_jobs(jobs)
    emailed = sent = 0
    send_days = {}
    for j in outs:
        p = _D(_D(j).get("payload"))
        if p.get("send_ref") or p.get("outreach_send"):
            emailed += len(_L(p.get("leads")))
        for _who, at in _D(p.get("sent_at")).items():
            d = _day(at)
            if d:
                send_days[d] = send_days.get(d, 0) + 1
                sent += 1
    replied = len(_L(reply_drafts))
    keys = sorted(send_days)[-days:]
    grid_rows = ["sent"]
    grid = [[send_days.get(k, 0) for k in keys]]
    return {"emailed": emailed, "sent": sent or emailed, "replied": replied,
            "reply_rate": _pct(replied, sent or emailed),
            "send_days": [(k, send_days[k]) for k in keys],
            "cohort_cols": [k[5:] for k in keys],
            "cohort_rows": grid_rows, "cohort_grid": grid,
            "silent": max(0, (sent or emailed) - replied),
            "has_data": bool(sent or emailed)}


def consultations(bookings=None) -> dict:
    """P4 — real Cal.com consultations, with a timeline."""
    rows = _L(bookings)
    accepted, upcoming, past, tasks = 0, 0, 0, []
    today = date.today().isoformat()
    per_day = {}
    for b in rows:
        b = _D(b)
        status = str(b.get("status", "")).lower()
        start = _day(b.get("start") or b.get("startTime") or b.get("start_time"))
        if status in ("accepted", "confirmed", ""):
            accepted += 1
        if start:
            per_day[start] = per_day.get(start, 0) + 1
            (upcoming if start >= today else past).__class__  # no-op guard
            if start >= today:
                upcoming += 1
            else:
                past += 1
            title = str(b.get("title") or b.get("eventTypeId") or "consultation")
            # gantt() wants day OFFSETS over the span, not dates.
            try:
                offset = (date.fromisoformat(start) - date.today()).days
            except Exception:
                offset = 0
            if -7 <= offset <= 14:
                tasks.append((title[:26], max(0, offset + 7), 1))
    keys = sorted(per_day)
    return {"total": len(rows), "accepted": accepted,
            "upcoming": upcoming, "past": past,
            "per_day": [(k, per_day[k]) for k in keys][-14:],
            "tasks": tasks[:10],
            "next": min([d for d in per_day if d >= today], default=None),
            "has_data": bool(rows)}


def funnel(jobs=None, reply_drafts=None, bookings=None, deals=None) -> dict:
    """P5 — one funnel, end to end, with the biggest leak named."""
    lg = leadgen(jobs)
    ou = outreach(jobs, reply_drafts)
    co = consultations(bookings)
    dl = _L(deals)
    stages = [("Found", lg["found"]), ("Verified", lg["verified"]),
              ("Emailed", ou["emailed"] or ou["sent"]), ("Replied", ou["replied"]),
              ("Booked", co["accepted"] or co["total"]), ("Won", len(dl))]
    flows, leaks = [], []
    for i in range(len(stages) - 1):
        (an, av), (bn, bv) = stages[i], stages[i + 1]
        if av:
            flows.append((an, bn, min(bv, av)))
            lost = max(0, av - bv)
            if lost:
                flows.append((an, f"lost at {an.lower()}", lost))
                leaks.append((f"{an} → {bn}", lost, _pct(lost, av)))
    worst = max(leaks, key=lambda t: t[1]) if leaks else None
    return {"stages": stages, "flows": flows, "leaks": leaks, "worst": worst,
            "overall_pct": _pct(len(dl), stages[0][1]) if stages[0][1] else 0.0,
            "waterfall": [(n, v) for n, v in stages],
            "has_data": bool(stages[0][1])}


# ======================================================================
#  ③ REVENUE & CUSTOMERS
# ======================================================================
def revenue(deals=None, months=6) -> dict:
    """R1–R4 — everything computable once deals are recorded."""
    dl = _L(deals)
    total = sum(_f(d.get("value")) for d in dl)
    by_client, by_source, by_month = {}, {}, {}
    for d in dl:
        c = str(d.get("client") or "unnamed")
        by_client[c] = by_client.get(c, 0.0) + _f(d.get("value"))
        s = str(d.get("source") or "other")
        by_source[s] = by_source.get(s, 0.0) + _f(d.get("value"))
        m = str(d.get("at"))[:7]
        by_month[m] = by_month.get(m, 0.0) + _f(d.get("value"))
    ranked = sorted(by_client.items(), key=lambda kv: -kv[1])
    keys = sorted(by_month)[-months:]
    this_month = date.today().isoformat()[:7]
    return {"total": round(total, 2), "deals": len(dl),
            "avg_deal": round(total / len(dl), 2) if dl else None,
            "largest": ranked[0] if ranked else None,
            "clients": len(by_client),
            "ranked": ranked[:10],
            "top_share": _pct(ranked[0][1], total) if ranked else 0.0,
            "donut": [(c, v) for c, v in ranked[:5]],
            "by_source": sorted(by_source.items(), key=lambda kv: -kv[1]),
            "by_month": [(k, by_month[k]) for k in keys],
            "month_total": round(by_month.get(this_month, 0.0), 2),
            "recurring": sum(1 for d in dl if d.get("recurring")),
            "has_data": bool(dl)}


def customers(deals=None, months=6) -> dict:
    """C1–C4 — cohorts, repeat rate and lifetime value, from recorded deals."""
    dl = _L(deals)
    per_client = {}
    for d in dl:
        c = str(d.get("client") or "unnamed")
        per_client.setdefault(c, []).append(d)
    repeat = [c for c, ds in per_client.items() if len(ds) > 1]
    ltv = (sum(_f(d.get("value")) for d in dl) / len(per_client)) if per_client else None
    firsts = {}
    for c, ds in per_client.items():
        firsts[c] = min(str(_D(d).get("at"))[:7] for d in ds)
    cohort_months = sorted(set(firsts.values()))[-months:]
    rows, grid = [], []
    for cm in cohort_months:
        members = [c for c, f in firsts.items() if f == cm]
        rows.append(cm)
        line = []
        for offset in range(len(cohort_months)):
            target = _month_add(cm, offset)
            active = sum(1 for c in members
                         if any(str(_D(d).get("at"))[:7] == target for d in per_client[c]))
            line.append(active)
        grid.append(line)
    ranked = sorted(((c, sum(_f(d.get("value")) for d in ds))
                     for c, ds in per_client.items()), key=lambda kv: -kv[1])
    return {"count": len(per_client), "repeat": len(repeat),
            "repeat_rate": _pct(len(repeat), len(per_client)),
            "ltv": round(ltv, 2) if ltv else None,
            "cohort_rows": rows, "cohort_grid": grid,
            "cohort_cols": [_month_add(cohort_months[0], i)[5:] for i in
                            range(len(cohort_months))] if cohort_months else [],
            "ranked": ranked[:10],
            "deals_per_client": round(len(dl) / len(per_client), 2) if per_client else None,
            "has_data": bool(dl)}


def _month_add(ym, n):
    try:
        y, m = int(str(ym)[:4]), int(str(ym)[5:7])
    except Exception:
        return str(ym)
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


# ======================================================================
#  ④ COST & UNIT ECONOMICS
# ======================================================================
def spend_view(meters=None, month_spent=0.0, month_cap=200.0, jobs=None,
               days=14) -> dict:
    """F1/F4 — spend against the cap, and a projection that says it is one."""
    m = _D(meters)
    per_provider = []
    for k, v in m.items():
        if isinstance(v, dict):
            per_provider.append((str(k), _f(v.get("spent"))))
        else:
            per_provider.append((str(k), _f(v)))
    per_provider.sort(key=lambda kv: -kv[1])
    today = date.today()
    dom = today.day or 1
    spent = _f(month_spent)
    cap = _f(month_cap, 200) or 200
    run_rate = spent / dom
    projected = run_rate * 30
    per_day = {}
    for j in _L(jobs):
        d = _day(_D(j).get("created_at"))
        if d:
            per_day[d] = per_day.get(d, 0.0) + _f(_D(j).get("cost_so_far_usd"))
    keys = sorted(per_day)[-days:]
    return {"spent": round(spent, 2), "cap": cap, "pct": _pct(spent, cap),
            "headroom": round(max(0.0, cap - spent), 2),
            "run_rate": round(run_rate, 2),
            "projected": round(projected, 2),
            "over_cap": projected > cap,
            "days_elapsed": dom,
            "per_provider": per_provider[:8],
            "series": [round(per_day[k], 4) for k in keys],
            "labels": keys,
            "projection_note": (
                f"Straight-line from {dom} days of data: €{spent:,.2f} so far is "
                f"€{run_rate:,.2f}/day, so €{projected:,.2f} by month end. This is "
                f"arithmetic, not a model — it assumes the next {max(0, 30 - dom)} "
                f"days look like the last {dom}."),
            "has_data": bool(spent or per_provider)}


def cost_per_outcome(jobs=None, agents=None, deals=None, bookings=None,
                     leads_found=0) -> dict:
    """F3 — what each real outcome cost. Failed jobs are excluded from the
    denominator: dividing by work that produced nothing flatters the number."""
    js = _L(jobs)
    produced = [j for j in js if _D(j).get("status") in ("published", "optimized")]
    failed = [j for j in js if _D(j).get("status") in ("failed", "halted_budget")]
    content_cost = sum(_f(_D(j).get("cost_so_far_usd")) for j in js
                       if _D(j).get("type") != "outreach_campaign")
    outreach_cost = sum(_f(_D(j).get("cost_so_far_usd")) for j in js
                        if _D(j).get("type") == "outreach_campaign")
    wasted = sum(_f(_D(j).get("cost_so_far_usd")) for j in failed)
    dl, bk = _L(deals), _L(bookings)
    rows, matrix, models = [], [], []
    for a in _L(agents):
        a = _D(a)
        skill = str(a.get("skill") or a.get("name") or "?")
        for mdl, n in _D(a.get("models")).items():
            if mdl not in models:
                models.append(str(mdl))
        rows.append(skill)
    heat = []
    for a in _L(agents):
        a = _D(a)
        line = []
        for mdl in models:
            line.append(_i(_D(a.get("models")).get(mdl)))
        heat.append(line)
    return {"content_cost": round(content_cost, 2),
            "outreach_cost": round(outreach_cost, 2),
            "total": round(content_cost + outreach_cost, 2),
            "produced": len(produced), "failed": len(failed),
            "wasted": round(wasted, 2),
            "wasted_pct": _pct(wasted, content_cost + outreach_cost),
            "per_piece": round(content_cost / len(produced), 2) if produced else None,
            "per_lead": round(outreach_cost / leads_found, 4) if leads_found else None,
            "per_booking": round((content_cost + outreach_cost) / len(bk), 2) if bk else None,
            "per_deal": round((content_cost + outreach_cost) / len(dl), 2) if dl else None,
            "bars": [("content", round(content_cost, 2)),
                     ("outreach", round(outreach_cost, 2)),
                     ("wasted on failures", round(wasted, 2))],
            "heat_rows": rows[:8], "heat_cols": models[:6],
            "heat": [r[:6] for r in heat[:8]],
            "has_data": bool(js)}


def unit_economics(deals=None, spend=None, economics=None, bookings=None,
                   leads_found=0) -> dict:
    """U1–U5 — CAC, LTV:CAC, payback and margin. Each returns None with a
    stated reason rather than a number built on an assumption."""
    dl = _L(deals)
    sp = _D(spend)
    ec = _D(economics)
    total_cost = _f(sp.get("spent"))
    rev = sum(_f(_D(d).get("value")) for d in dl)
    clients = len({str(_D(d).get("client")) for d in dl})
    margin = ec.get("margin_pct")
    cac = round(total_cost / clients, 2) if clients else None
    per_client_rev = round(rev / clients, 2) if clients else None
    gross = round(rev * _f(margin) / 100, 2) if (margin and rev) else None
    ltv = per_client_rev if margin is None else round(per_client_rev * _f(margin) / 100, 2) \
        if per_client_rev else None
    ratio = round(ltv / cac, 2) if (ltv and cac) else None
    payback = round(cac / (ltv / 12), 1) if (ltv and cac and ltv > 0) else None
    by_source = {}
    for d in dl:
        s = str(_D(d).get("source") or "other")
        by_source[s] = by_source.get(s, 0.0) + _f(_D(d).get("value"))
    matrix = [(s, min(3, max(1, int(v / (rev / 3) + 1)) if rev else 1),
               min(3, max(1, int(total_cost / max(len(by_source), 1) / 20) + 1)))
              for s, v in by_source.items()]
    blockers = []
    if not dl:
        blockers.append("No deals recorded yet — record one won deal and CAC, "
                        "LTV and payback all compute from data already here.")
    if margin is None:
        blockers.append("Gross margin % is not set, so LTV is revenue rather than "
                        "profit and the LTV:CAC ratio reads high.")
    return {"cac": cac, "ltv": ltv, "ratio": ratio, "payback_months": payback,
            "revenue": round(rev, 2), "gross_profit": gross,
            "margin_pct": _f(margin) if margin else None,
            "clients": clients, "cost": round(total_cost, 2),
            "roi": _pct(rev - total_cost, total_cost) if total_cost else None,
            "per_client_rev": per_client_rev,
            "by_source": sorted(by_source.items(), key=lambda kv: -kv[1]),
            "matrix": matrix,
            "healthy_ratio": (ratio is not None and ratio >= 3),
            "blockers": blockers,
            "has_data": bool(dl)}


def attainment(tg=None, rev=None, lg=None, co=None) -> dict:
    """U6 — behind or ahead. Without a target a card can only state a number."""
    t, r = _D(tg), _D(rev)
    l, c = _D(lg), _D(co)
    rows = []
    for label, target, actual in (
            ("Revenue this month", t.get("revenue_month"), r.get("month_total")),
            ("Deals this month", t.get("deals_month"), r.get("deals")),
            ("Leads this month", t.get("leads_month"), l.get("found")),
            ("Bookings this month", t.get("bookings_month"), c.get("accepted"))):
        if target:
            rows.append((label, _f(actual), _f(target), _pct(actual, target)))
    return {"rows": rows, "set": bool(rows),
            "behind": [r for r in rows if r[3] < 100],
            "note": ("No targets set. Every card can state a number but none can "
                     "say whether it is good — that needs a target to compare "
                     "against.") if not rows else ""}


BI_HISTORY_KEY = "bi_history"
MAX_BI_HISTORY = 24


def record_bi_snapshot(store, channels=None, markets=None) -> list:
    """One row per month, so 'this month vs last' can be a measurement rather
    than a guess. GA4 gives a rolling 28-day window with no month dimension —
    without this there is nothing to compare against."""
    try:
        hist = list(store.get_setting(BI_HISTORY_KEY, []) or [])
    except Exception:
        hist = []
    month = _day(_iso())[:7]
    hist = [h for h in hist if str(_D(h).get("month")) != month]
    hist.append({"month": month,
                 "channels": {str(k): _f(v) for k, v in
                              _L(_D(channels).get("rows"))[:8]},
                 "markets": {str(k): _f(v) for k, v in
                             _L(_D(markets).get("rows"))[:8]}})
    hist = sorted(hist, key=lambda h: str(_D(h).get("month")))[-MAX_BI_HISTORY:]
    try:
        store.set_setting(BI_HISTORY_KEY, hist)
    except Exception as e:
        log.warning("bi history save failed: %s", e)
    return hist


def mom(history, kind, top=5) -> dict:
    """Month-over-month by category, shaped for vbars.

    Returns {groups, this_month, last_month, ready, note}. `ready` is False
    until two months exist, and the note says so — a single month drawn as a
    comparison would be a lie with a chart around it."""
    hist = _L(history)
    if len(hist) < 2:
        cur = _D(_D(hist[-1]).get(kind)) if hist else {}
        groups = [k for k, _v in sorted(cur.items(), key=lambda kv: -_f(kv[1]))[:top]]
        return {"groups": groups,
                "this_month": [_f(cur.get(g)) for g in groups],
                "last_month": [], "ready": False,
                "note": ("Month-over-month needs two months of snapshots. One is "
                         "recorded so far, so this shows the current month only "
                         "and the comparison appears next month.")}
    prev, cur = _D(hist[-2]).get(kind), _D(hist[-1]).get(kind)
    prev, cur = _D(prev), _D(cur)
    groups = [k for k, _v in sorted(cur.items(), key=lambda kv: -_f(kv[1]))[:top]]
    return {"groups": groups,
            "this_month": [_f(cur.get(g)) for g in groups],
            "last_month": [_f(prev.get(g)) for g in groups],
            "ready": True,
            "note": (f"{_D(hist[-2]).get('month')} against "
                     f"{_D(hist[-1]).get('month')}, same categories.")}


def leads_mom(jobs=None, top=5) -> dict:
    """Lead volume by source, this month against last. Computable immediately —
    outreach jobs carry a real created_at."""
    from datetime import date as _date
    today = _date.today()
    cur_m = today.isoformat()[:7]
    prev_m = _month_add(cur_m, -1)
    cur, prev = {}, {}
    for j in _L(jobs):
        d = _D(j)
        if d.get("type") != "outreach_campaign":
            continue
        p = _D(d.get("payload"))
        n = len(_L(p.get("raw_leads"))) or len(_L(p.get("leads")))
        src = str(p.get("source") or p.get("lead_source") or "outreach").lower()
        m = _day(d.get("created_at"))[:7]
        if m == cur_m:
            cur[src] = cur.get(src, 0) + n
        elif m == prev_m:
            prev[src] = prev.get(src, 0) + n
    groups = [k for k, _v in sorted(cur.items(), key=lambda kv: -kv[1])[:top]] or \
             [k for k, _v in sorted(prev.items(), key=lambda kv: -kv[1])[:top]]
    return {"groups": groups,
            "this_month": [cur.get(g, 0) for g in groups],
            "last_month": [prev.get(g, 0) for g in groups],
            "ready": bool(groups and (prev or cur)),
            "note": (f"{prev_m} against {cur_m}, from campaign dates."
                     if groups else
                     "No campaign has run in either month yet.")}


def client_rank_movement(deals=None, months=6) -> list:
    """[(client, [rank per month])] for a bump chart. Rank 1 is the biggest
    client that month; a line climbing means a client is taking a larger share."""
    dl = _L(deals)
    if not dl:
        return []
    by_month = {}
    for d in dl:
        d = _D(d)
        m = str(d.get("at"))[:7]
        by_month.setdefault(m, {})
        c = str(d.get("client") or "unnamed")
        by_month[m][c] = by_month[m].get(c, 0.0) + _f(d.get("value"))
    keys = sorted(by_month)[-months:]
    if len(keys) < 2:
        return []
    totals = {}
    for m in keys:
        for c, v in by_month[m].items():
            totals[c] = totals.get(c, 0.0) + v
    tracked = [c for c, _v in sorted(totals.items(), key=lambda kv: -kv[1])[:5]]
    out = []
    for c in tracked:
        ranks = []
        for m in keys:
            order = sorted(by_month[m].items(), key=lambda kv: -kv[1])
            names = [n for n, _v in order]
            ranks.append(names.index(c) + 1 if c in names else len(names) + 1)
        out.append((c[:14], ranks))
    return out


def health_score(status=None, spend=None, funnel_=None, demand_=None,
                 criticals=0) -> dict:
    """A composite the CEO board can show, built only from measured parts and
    with those parts shown. A single score nobody can decompose is a mood, not
    a metric."""
    st = _D(status)
    live = sum(1 for v in st.values() if v)
    parts = []
    if st:
        parts.append(("wires live", _pct(live, len(st))))
    sp = _D(spend)
    if sp.get("cap"):
        parts.append(("budget headroom", max(0.0, 100 - _f(sp.get("pct")))))
    fn = _D(funnel_)
    if fn.get("has_data"):
        parts.append(("funnel conversion", min(100.0, _f(fn.get("overall_pct")) * 20)))
    dm = _D(demand_)
    if dm.get("has_ga4"):
        parts.append(("demand trend", min(100.0, max(0.0, 50 + _f(dm.get("trend_pct"))))))
    if criticals:
        parts.append(("risks clear", max(0.0, 100 - _f(criticals) * 20)))
    score = round(sum(v for _n, v in parts) / len(parts)) if parts else None
    return {"score": score, "parts": parts,
            "note": ("Averaged from " + ", ".join(n for n, _v in parts) + "."
                     if parts else
                     "Nothing measurable is reporting yet, so there is no score "
                     "to show. A number here without inputs would be decoration.")}


def opportunities(funnel_=None, demand_=None, markets_=None, content_=None,
                  econ_=None, revenue_=None) -> list:
    """Ranked by what they would actually move, each traced to the measurement
    it came from. No generic advice."""
    out = []
    fn, dm = _D(funnel_), _D(demand_)
    mk, cn = _D(markets_), _D(content_)
    ec, rv = _D(econ_), _D(revenue_)
    if fn.get("worst"):
        label, lost, pct = fn["worst"]
        out.append({"title": f"Fix the {label} drop",
                    "why": (f"{lost:,.0f} people are lost there, {pct}% of everyone "
                            f"who reaches that stage. It is the largest single "
                            f"leak measured."),
                    "where": "bifunnel", "weight": _f(lost)})
    for m in _L(mk.get("missing"))[:2]:
        out.append({"title": f"No traffic at all from {m}",
                    "why": (f"{m} is one of your five target markets and GA4 "
                            f"records zero sessions from it."
                            + (" The site has no German content, which is the "
                               "whole reason for DE and CH."
                               if m in ("Germany", "Switzerland") else "")),
                    "where": "bimarkets", "weight": 900})
    silent = max(0, _i(cn.get("published")) - _i(cn.get("carrying")))
    if silent:
        out.append({"title": f"{silent} published pages earn no traffic",
                    "why": ("Already written and already paid for. Getting them "
                            "indexed or retargeted costs nothing to produce."),
                    "where": "bicontent", "weight": silent * 30})
    if dm.get("avg_position") and _f(dm.get("avg_position")) > 10:
        out.append({"title": "Rankings sit off page one",
                    "why": (f"Average position {dm.get('avg_position')} across "
                            f"{dm.get('queries')} queries. Clicks stay near zero "
                            f"until that crosses 10."),
                    "where": "bidemand", "weight": 700})
    if not ec.get("set"):
        out.append({"title": "Three numbers unlock the economics boards",
                    "why": ("Gross margin, average deal and close rate. Without "
                            "them LTV reads as turnover and pipeline cannot be "
                            "valued in euros."),
                    "where": "biecon", "weight": 600})
    if not _D(revenue_).get("has_data"):
        out.append({"title": "Record your first won deal",
                    "why": ("Revenue, customers, cohorts, CAC and LTV:CAC are all "
                            "computable the moment one deal exists. Nothing else "
                            "is blocking them."),
                    "where": "birevenue", "weight": 1000})
    return sorted(out, key=lambda o: -o["weight"])[:6]


def next_actions(risks=None, opps=None, spend=None) -> list:
    """What to actually do, each pointing at the thing that does it."""
    acts = []
    for r in _L(risks)[:2]:
        r = _D(r)
        if r.get("mitigation"):
            acts.append({"label": str(r.get("title"))[:38],
                         "detail": str(r.get("mitigation"))[:150],
                         "cta": "Open Risk", "js": "nav('riskinfra')"})
    for o in _L(opps)[:2]:
        o = _D(o)
        acts.append({"label": str(o.get("title"))[:38],
                     "detail": str(o.get("why"))[:150],
                     "cta": "Open the board", "js": f"seoTab('{o.get('where', 'bicmd')}')"})
    if _f(_D(spend).get("pct")) > 85:
        acts.append({"label": "Spend is near the cap",
                     "detail": ("The engine halts new LLM steps at 100%. Raise the "
                                "cap or let it stop."),
                     "cta": "Open Spend", "js": "seoTab('bispend')"})
    return acts[:6]


def movement(demand_=None, spend=None, revenue_=None, days=7) -> list:
    """Week over week, from series already measured. Only metrics with two full
    windows appear — a delta against a partial window is noise."""
    out = []
    ser = _L(_D(demand_).get("series"))
    if len(ser) >= days * 2:
        now, before = sum(ser[-days:]), sum(ser[-days * 2:-days])
        out.append(("Sessions", now, before, True))
    sp = _L(_D(spend).get("series"))
    if len(sp) >= days * 2:
        out.append(("Spend", round(sum(sp[-days:]), 2),
                    round(sum(sp[-days * 2:-days]), 2), False))
    by_m = _L(_D(revenue_).get("by_month"))
    if len(by_m) >= 2:
        out.append(("Revenue", by_m[-1][1], by_m[-2][1], True))
    return out


def executive_brief(store=None, status=None, spend=None, funnel_=None,
                    demand_=None, markets_=None, content_=None, econ_=None,
                    revenue_=None, leadgen_=None, unit_=None) -> dict:
    """Board 15 — the whole business on one screen, every number traced to the
    board that owns it."""
    risks = []
    try:
        import content_engine_risk as RK
        risks = sorted(RK.load_register(store), key=lambda r: -_f(_D(r).get("score")))
    except Exception as e:
        log.warning("risk register unavailable to the executive brief: %s", e)
    criticals = sum(1 for r in risks if _f(_D(r).get("score")) >= 6)
    opps = opportunities(funnel_, demand_, markets_, content_, econ_, revenue_)
    return {
        "health": health_score(status, spend, funnel_, demand_, criticals),
        "risks": risks[:3], "risk_total": len(risks), "criticals": criticals,
        "opportunities": opps,
        "actions": next_actions(risks, opps, spend),
        "movement": movement(demand_, spend, revenue_),
        "flows": _L(_D(funnel_).get("flows")),
        "headlines": [
            ("SEO / AEO / GEO", f"{_i(_D(demand_).get('clicks'))} search clicks",
             "seo", _f(_D(demand_).get("clicks"))),
            ("Media Buying", f"{_i(_D(leadgen_).get('found'))} leads sourced",
             "media", _f(_D(leadgen_).get("found"))),
            ("Risk & Infrastructure", f"{criticals} critical risks",
             "riskinfra", _f(criticals) * 10),
            ("System & Wiring",
             f"{sum(1 for v in _D(status).values() if v)}/{len(_D(status))} wires live",
             "system", _f(sum(1 for v in _D(status).values() if v))),
        ],
    }


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

    # deals: the input path that did not exist
    assert record_deal(st, "", 100)["ok"] is False, "a nameless deal must be refused"
    assert record_deal(st, "Acme", 0)["ok"] is False, "a zero deal must be refused"
    r = record_deal(st, "Acme GmbH", 6000, source="outreach", at="2026-05-11",
                    margin_pct=65)
    assert r["ok"] and r["deal"]["client"] == "Acme GmbH"
    record_deal(st, "Bauer AG", 4200, source="organic", at="2026-06-03")
    record_deal(st, "Acme GmbH", 3000, source="outreach", at="2026-07-02",
                recurring=True)
    dl = list_deals(st)
    assert len(dl) == 3 and dl[0]["at"] >= dl[-1]["at"], "deals must sort newest first"
    assert all(d["source"] in SOURCES for d in dl), "source must be normalised"

    rev = revenue(dl)
    assert rev["total"] == 13200.0 and rev["clients"] == 2
    assert rev["largest"][0] == "Acme GmbH" and rev["top_share"] > 60
    cu = customers(dl)
    assert cu["count"] == 2 and cu["repeat"] == 1 and cu["repeat_rate"] == 50.0
    assert cu["ltv"] == 6600.0, cu["ltv"]

    # the client name now survives — the Risk board's concentration reads this
    assert all("client" in d for d in dl), "client must persist"

    # unit economics: no invented numbers
    ue = unit_economics(dl, {"spent": 120.0}, {"margin_pct": None})
    assert ue["cac"] == 60.0 and ue["ltv"] == 6600.0
    assert any("margin" in b for b in ue["blockers"]), "an unset margin must be stated"
    ue2 = unit_economics([], {"spent": 120.0}, {})
    assert ue2["cac"] is None and ue2["ratio"] is None, "no deals -> no invented CAC"
    assert any("No deals recorded" in b for b in ue2["blockers"])

    # demand degrades honestly
    d0 = demand({})
    assert d0["has_ga4"] is False and d0["sessions"] == 0 and d0["avg_position"] is None
    ins = {"ga4": {"daily": [{"date": "2026-07-0%d" % i, "sessions": 10 * i}
                             for i in range(1, 9)],
                   "totals": {"sessions": 360, "totalUsers": 210,
                              "engagementRate": 0.62},
                   "channels": [{"sessionDefaultChannelGroup": "Organic Search",
                                 "sessions": 300},
                                {"sessionDefaultChannelGroup": "Direct", "sessions": 60}],
                   "countries": [{"country": "Germany", "sessions": 200},
                                 {"country": "United States", "sessions": 160}],
                   "pages": [{"pagePath": "/guides/x", "sessions": 120}]},
           "gsc": [{"query": "n8n automation", "clicks": 12, "impressions": 900,
                    "position": 18.2}]}
    d1 = demand(ins)
    assert d1["has_ga4"] and d1["sessions"] == 360 and d1["users"] == 210
    assert d1["trend_pct"] is not None and d1["ctr"] > 0
    mk = markets(ins)
    assert mk["top"][0] == "Germany" and "UK" in mk["missing"]
    ch = channel_mix(ins)
    assert ch["top"][0] == "Organic Search" and ch["concentrated"] is True

    # pipeline
    jobs = [{"job_id": "o1", "type": "outreach_campaign", "status": "sent",
             "created_at": "2026-07-20T09:00:00Z", "cost_so_far_usd": 0.4,
             "payload": {"raw_leads": [{}] * 40, "leads": [{}] * 31,
                         "send_ref": "x", "sent_at": {"a@b.com": "2026-07-21T09:00:00Z",
                                                      "c@d.com": "2026-07-21T10:00:00Z"},
                         "lead_qualifier": {"results": [{}] * 18}}},
            {"job_id": "c1", "type": "content_piece", "status": "published",
             "created_at": "2026-07-22T09:00:00Z", "cost_so_far_usd": 0.6},
            {"job_id": "c2", "type": "content_piece", "status": "failed",
             "created_at": "2026-07-23T09:00:00Z", "cost_so_far_usd": 0.2}]
    lg = leadgen(jobs)
    assert lg["found"] == 40 and lg["verified"] == 31 and lg["qualified"] == 18
    ou = outreach(jobs, reply_drafts=[{}, {}])
    assert ou["sent"] == 2 and ou["replied"] == 2 and ou["reply_rate"] == 100.0
    bk = [{"status": "accepted", "start": "2026-07-28T10:00:00Z", "title": "Intro"},
          {"status": "accepted", "start": "2026-08-04T10:00:00Z", "title": "Follow"}]
    co = consultations(bk)
    assert co["total"] == 2 and co["accepted"] == 2 and co["tasks"]
    fn = funnel(jobs, [{}, {}], bk, dl)
    assert fn["stages"][0] == ("Found", 40) and fn["stages"][-1][1] == 3
    assert fn["worst"] is not None and fn["flows"], "a funnel must name its biggest leak"

    # cost: failures excluded from the denominator, and counted as waste
    cpo = cost_per_outcome(jobs, agents=[{"skill": "content_producer",
                                          "models": {"claude-opus-5": 5}}],
                           deals=dl, bookings=bk, leads_found=40)
    assert cpo["produced"] == 1 and cpo["failed"] == 1
    assert cpo["per_piece"] == 0.8, cpo["per_piece"]
    assert cpo["wasted"] == 0.2 and cpo["per_deal"] is not None

    sv = spend_view({"anthropic": {"spent": 41.7}}, 41.7, 200.0, jobs)
    assert sv["pct"] > 0 and "arithmetic, not a model" in sv["projection_note"]

    at = attainment({}, rev, lg, co)
    assert at["set"] is False and "needs a target" in at["note"]
    set_targets(st, revenue_month=10000, deals_month=2)
    at2 = attainment(targets(st), rev, lg, co)
    assert at2["set"] is True and len(at2["rows"]) == 2

    # hostile shapes must never raise
    for bad in (None, {}, [], "x", 0, {"ga4": "no"}, {"ga4": {"daily": "no"}}):
        for fn_ in (demand, markets, channel_mix):
            fn_(bad)
        leadgen(bad if isinstance(bad, list) else None)
        revenue(bad if isinstance(bad, list) else None)
        customers(bad if isinstance(bad, list) else None)
        unit_economics(None, bad, bad)
        spend_view(bad, 0, 0, None)
        cost_per_outcome(None, None, None, None)
        consultations(bad if isinstance(bad, list) else None)
        funnel(None, None, None, None)
        attainment(bad, bad, bad, bad)

    # the executive brief: composite score decomposes, nothing invented
    hs = health_score({}, {}, {}, {})
    assert hs["score"] is None and "decoration" in hs["note"], hs
    hs2 = health_score({"a": True, "b": False}, {"cap": 200, "pct": 20},
                       {"has_data": True, "overall_pct": 2.5},
                       {"has_ga4": True, "trend_pct": 10}, criticals=1)
    assert hs2["score"] is not None and len(hs2["parts"]) == 5, hs2
    assert all(0 <= v <= 100 for _n, v in hs2["parts"]), hs2["parts"]

    ops = opportunities({"worst": ("Emailed → Replied", 150, 83.0)},
                        {"avg_position": 42.0, "queries": 30},
                        {"missing": ["UK", "Switzerland"]},
                        {"published": 10, "carrying": 4}, {"set": False}, {})
    assert ops and ops[0]["weight"] >= ops[-1]["weight"], "must rank by impact"
    assert any("Record your first won deal" in o["title"] for o in ops)
    assert all(o.get("where") for o in ops), "every opportunity needs a destination"

    eb = executive_brief(st, status={"a": True}, spend={"cap": 200, "pct": 20},
                         funnel_=fn, demand_=d1, markets_=mk, content_={},
                         econ_=econ(st), revenue_=rev, leadgen_=lg)
    assert eb["flows"] == fn["flows"], "the value flow must reuse the MEASURED funnel"
    assert len(eb["headlines"]) == 4
    # no fabricated attribution survives
    assert not any("0.6" in str(f) or "0.4" in str(f) for f in eb["flows"])
    mv = movement({"series": list(range(20))}, {"series": [1.0] * 20}, rev)
    assert len(mv) >= 2 and all(len(m) == 4 for m in mv)
    assert movement({"series": [1, 2, 3]}, {}, {}) == [], \
        "a delta needs two full windows"

    print("bi self-check OK — deals recorded with the client name that "
          "concentration needs, revenue/LTV/cohorts computed, CAC and LTV:CAC "
          "absent rather than invented when inputs are missing, demand and "
          "channel mix from GA4/GSC, funnel names its biggest leak, failed jobs "
          "excluded from cost-per-outcome, and a projection that says it is "
          "arithmetic.")
