"""
content_engine_media_metrics.py
============================================================================
THE ANALYTICS ENGINE. The metric registry, the one query service, the
data-quality layer and the AI data contract. Spec: the analytics master
specification, sections 1-12 and 49-50, 58-61, 65.

THE ABSOLUTELY CRITICAL METRIC RULE (spec section 8)
  Ratio metrics are NEVER averaged from rows. CTR is SUM(clicks) over
  SUM(impressions), computed at the end, over whatever slice the query
  asked for. The registry carries each metric's aggregation; there is no
  second place where a formula lives, so a chart and a table cannot
  disagree about what CPA means.

THE GOLDEN RULE (spec section 65)
  Every dashboard, chart, table and AI insight goes through
  analytics_query(). Totals, timeseries and breakdowns are computed from
  the SAME filtered row set in the same call, so "dashboard spend" and
  "table spend" are one number by construction, not by testing luck.

THE AI DATA CONTRACT (spec sections 49-50)
  The AI receives what the engine computed, interprets it, and returns
  facts separated from hypotheses. A number the engine did not return
  cannot appear in an insight, because insights are BUILT from the query
  result object and nothing else. Missing data returns
  INSUFFICIENT_DATA, never an invented figure.

WHAT THIS ENGINE REFUSES TO PRETEND
  - Currency: this workspace runs one reporting currency (EUR). Rows
    carry their currency; nothing is silently summed across currencies
    (a mixed-currency slice is flagged in data_quality).
  - Timezone: provider days are stored as the provider reported them;
    no silent boundary shifting. Recorded in data_quality.
  - reach, frequency, video quartiles: registered metrics with NO
    collected source yet; querying them answers INSUFFICIENT_DATA.
============================================================================
"""

from __future__ import annotations

import datetime as _dt
import logging

import content_engine_media_perf as MF
from content_engine_os_core import _D, _L, now

log = logging.getLogger("content_engine.media_metrics")

REPORTING_CURRENCY = "EUR"

#: THE METRIC REGISTRY, spec section 7. One entry per metric; charts,
#: tables, KPI cards and the AI all read THIS. aggregation "sum" reads a
#: base column; "ratio" is numerator-sum over denominator-sum with an
#: optional multiplier, computed after aggregation, never averaged.
REGISTRY = {
    "spend":            {"display": "Spend", "category": "delivery",
                         "unit": "currency", "agg": "sum",
                         "column": "spend", "polarity": "neutral",
                         "decimals": 2},
    "impressions":      {"display": "Impressions", "category": "delivery",
                         "unit": "count", "agg": "sum",
                         "column": "impressions", "polarity": "neutral",
                         "decimals": 0},
    "clicks":           {"display": "Clicks", "category": "traffic",
                         "unit": "count", "agg": "sum",
                         "column": "clicks", "polarity": "positive",
                         "decimals": 0},
    "conversions":      {"display": "Conversions", "category": "conversion",
                         "unit": "count", "agg": "sum",
                         "column": "conversions", "polarity": "positive",
                         "decimals": 0},
    "revenue":          {"display": "Revenue", "category": "revenue",
                         "unit": "currency", "agg": "sum",
                         "column": "conversion_value",
                         "polarity": "positive", "decimals": 2},
    "ctr":              {"display": "CTR", "category": "traffic",
                         "unit": "percent", "agg": "ratio",
                         "num": "clicks", "den": "impressions",
                         "mult": 100.0, "polarity": "positive",
                         "decimals": 2},
    "cpc":              {"display": "CPC", "category": "traffic",
                         "unit": "currency", "agg": "ratio",
                         "num": "spend", "den": "clicks", "mult": 1.0,
                         "polarity": "negative", "decimals": 2},
    "cpm":              {"display": "CPM", "category": "delivery",
                         "unit": "currency", "agg": "ratio",
                         "num": "spend", "den": "impressions",
                         "mult": 1000.0, "polarity": "negative",
                         "decimals": 2},
    "cvr":              {"display": "CVR", "category": "conversion",
                         "unit": "percent", "agg": "ratio",
                         "num": "conversions", "den": "clicks",
                         "mult": 100.0, "polarity": "positive",
                         "decimals": 2},
    "cpa":              {"display": "CPA", "category": "conversion",
                         "unit": "currency", "agg": "ratio",
                         "num": "spend", "den": "conversions", "mult": 1.0,
                         "polarity": "negative", "decimals": 2},
    "roas":             {"display": "ROAS", "category": "revenue",
                         "unit": "ratio", "agg": "ratio",
                         "num": "conversion_value", "den": "spend",
                         "mult": 1.0, "polarity": "positive",
                         "decimals": 2},
    # Registered but with NO collected source yet. Queries answer
    # INSUFFICIENT_DATA instead of a fabricated zero. Spec sections 9-10.
    "reach":            {"display": "Reach", "category": "delivery",
                         "unit": "count", "agg": "sum", "column": "reach",
                         "polarity": "neutral", "decimals": 0,
                         "uncollected": True},
    "frequency":        {"display": "Frequency", "category": "delivery",
                         "unit": "ratio", "agg": "ratio",
                         "num": "impressions", "den": "reach", "mult": 1.0,
                         "polarity": "neutral", "decimals": 2,
                         "uncollected": True},
    "video_views":      {"display": "Video views", "category": "engagement",
                         "unit": "count", "agg": "sum",
                         "column": "video_views", "polarity": "positive",
                         "decimals": 0, "uncollected": True},
}

DIMENSIONS = ("date", "platform", "campaign", "ad_group", "ad", "creative",
              "country", "device", "placement", "objective")
GRANULARITIES = ("DAY", "WEEK", "MONTH")
QUALITY_STATES = ("LIVE", "RECENT", "DELAYED", "ESTIMATED", "PARTIAL",
                  "MISSING", "SYNCING", "ERROR")

#: How old a provider's last read may be before its label degrades.
FRESH_HOURS, RECENT_HOURS = 6, 30


# ---------------------------------------------------------------------------
# AGGREGATION. Sums first, ratios after, always.
# ---------------------------------------------------------------------------
_BASE = ("spend", "impressions", "clicks", "conversions",
         "conversion_value")


def _zero() -> dict:
    return {b: 0.0 for b in _BASE}


def _add(acc, row) -> None:
    for b in _BASE:
        try:
            acc[b] += float(row.get(b) or 0)
        except Exception:
            pass


def metric_value(key, sums) -> dict:
    """One metric over one aggregated slice: value + the denominator it
    stands on, or INSUFFICIENT_DATA with the reason."""
    m = REGISTRY.get(key)
    if not m:
        return {"metric": key, "value": None, "status": "UNKNOWN_METRIC",
                "why": f"{key!r} is not in the registry. It has: "
                       + ", ".join(sorted(REGISTRY))}
    if m.get("uncollected"):
        return {"metric": key, "value": None,
                "status": "INSUFFICIENT_DATA",
                "why": f"{m['display']} is registered but no provider "
                       f"pull collects it yet; nothing is invented"}
    if m["agg"] == "sum":
        return {"metric": key,
                "value": round(float(sums.get(m["column"]) or 0),
                               m["decimals"]),
                "status": "OK"}
    n = float(sums.get(m["num"]) or 0)
    d = float(sums.get(m["den"]) or 0)
    if d <= 0:
        return {"metric": key, "value": None,
                "status": "INSUFFICIENT_DATA",
                "why": f"no {m['den']} in this slice; a {m['display']} "
                       f"over nothing is a rumour, not a zero"}
    return {"metric": key, "value": round(n / d * m["mult"], m["decimals"]),
            "of": f"{n:,.0f} / {d:,.0f}", "status": "OK"}


# ---------------------------------------------------------------------------
# THE QUERY ENGINE
# ---------------------------------------------------------------------------
def _parse_day(s):
    try:
        s = str(s)[:10]
        return _dt.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except Exception:
        return None


def _bucket_of(day, gran) -> str:
    if gran == "DAY":
        return day
    d = _parse_day(day)
    if not d:
        return day
    if gran == "WEEK":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    return day[:7]


def _row_dim(row, dim, joins) -> str:
    if dim == "date":
        return str(row.get("day") or "")[:10]
    if dim == "platform":
        return str(row.get("provider") or "")
    if dim == "campaign":
        return str(row.get("campaign_id") or "")
    if dim == "ad_group":
        return str(row.get("ad_group_id") or "")
    if dim == "ad":
        return str(row.get("ad_id") or "")
    if dim == "creative":
        return (str(row.get("creative_id") or "")
                or joins["ad_creative"].get(str(row.get("ad_id") or ""), ""))
    if dim == "objective":
        return joins["camp_objective"].get(
            str(row.get("campaign_id") or ""), "")
    return str(row.get(dim) or "")


def analytics_query(r, store, query) -> dict:
    """THE one canonical analytics call, spec sections 11-12.

    Everything (totals, comparison, timeseries, breakdowns, quality) is
    computed from one filtered row set in one pass per period."""
    q = _D(query)
    dr = _D(q.get("date_range"))
    to_d = _parse_day(dr.get("to")) or _dt.date.today()
    from_d = _parse_day(dr.get("from")) or (to_d - _dt.timedelta(days=29))
    if from_d > to_d:
        return {"ok": False, "message": "date_range.from is after .to; "
                                        "nothing was computed"}
    span = (to_d - from_d).days + 1
    comparison = str(_D(q.get("comparison")).get("type")
                     or "PREVIOUS_PERIOD")
    cmp_to = from_d - _dt.timedelta(days=1)
    cmp_from = cmp_to - _dt.timedelta(days=span - 1)
    metrics = [m for m in _L(q.get("metrics"))] or \
        ["spend", "revenue", "conversions", "cpa", "roas"]
    dims = [d for d in _L(q.get("dimensions")) if d in DIMENSIONS] or ["date"]
    gran = str(q.get("granularity") or "DAY")
    if gran not in GRANULARITIES:
        return {"ok": False,
                "message": f"{gran!r} is not a granularity. They are: "
                           + ", ".join(GRANULARITIES)}
    f = _D(q.get("filters"))
    plats = {str(x).lower() for x in _L(f.get("platforms"))}
    fsets = {k: {str(x) for x in _L(f.get(k))}
             for k in ("campaign_ids", "ad_group_ids", "ad_ids",
                       "creative_ids", "countries", "devices",
                       "placements")}
    # joins built once
    camps = {c.get("id"): c for c in r.all("media_campaigns")}
    joins = {"camp_objective": {str(k): str(v.get("objective") or "")
                                for k, v in camps.items()},
             "camp_name": {str(k): str(v.get("name") or k)
                           for k, v in camps.items()},
             "ad_creative": {str(a.get("id")): str(a.get("creative_id")
                                                   or "")
                             for a in r.all("ads")}}
    cre_names = {str(c.get("id")): str(c.get("name") or c.get("id"))
                 for c in r.all("creatives")}
    grp_names = {str(g.get("id")): str(g.get("name") or g.get("id"))
                 for g in r.all("ad_groups")}
    ad_names = {str(a.get("id")): str(a.get("name") or a.get("id"))
                for a in r.all("ads")}

    def keep(row) -> bool:
        if plats and str(row.get("provider") or "").lower() not in plats:
            return False
        checks = (("campaign_ids", "campaign_id"),
                  ("ad_group_ids", "ad_group_id"), ("ad_ids", "ad_id"),
                  ("countries", "country"), ("devices", "device"),
                  ("placements", "placement"))
        for fk, col in checks:
            if fsets[fk] and str(row.get(col) or "") not in fsets[fk]:
                return False
        if fsets["creative_ids"]:
            cid = (str(row.get("creative_id") or "")
                   or joins["ad_creative"].get(str(row.get("ad_id") or ""),
                                               ""))
            if cid not in fsets["creative_ids"]:
                return False
        return True

    cur_t, prev_t = _zero(), _zero()
    series, breaks = {}, {d: {} for d in dims if d != "date"}
    adopted, currencies, row_ids = 0, set(), set()
    for m in r.all("ad_metrics"):
        rid_ = str(m.get("id") or "")
        if rid_ in row_ids:      # duplicate provider rows never double
            continue
        row_ids.add(rid_)
        if not keep(m):
            continue
        day = _parse_day(m.get("day"))
        if day is None:
            if not m.get("day"):
                adopted += 1     # adopted aggregates: outside date math
            continue
        currencies.add(str(m.get("currency") or REPORTING_CURRENCY))
        if cmp_from <= day <= cmp_to:
            _add(prev_t, m)
        if not (from_d <= day <= to_d):
            continue
        _add(cur_t, m)
        b = _bucket_of(str(m.get("day"))[:10], gran)
        _add(series.setdefault(b, _zero()), m)
        for d in breaks:
            v = _row_dim(m, d, joins)
            if v:
                _add(breaks[d].setdefault(v, _zero()), m)

    def project(sums) -> dict:
        return {k: metric_value(k, sums) for k in metrics}

    def label(dim, key) -> str:
        return {"campaign": joins["camp_name"],
                "creative": cre_names, "ad_group": grp_names,
                "ad": ad_names}.get(dim, {}).get(key, key)

    totals = project(cur_t)
    prev = project(prev_t)
    deltas = {}
    for k in metrics:
        a, b = prev.get(k, {}).get("value"), totals.get(k, {}).get("value")
        deltas[k] = (round((b - a) / a * 100, 1)
                     if a not in (None, 0) and b is not None else None)
    return {
        "ok": True,
        "query": {"from": from_d.isoformat(), "to": to_d.isoformat(),
                  "granularity": gran, "metrics": metrics,
                  "dimensions": dims,
                  "comparison": {"type": comparison,
                                 "from": cmp_from.isoformat(),
                                 "to": cmp_to.isoformat()}},
        "totals": totals,
        "comparison": {"totals": prev, "change_percent": deltas},
        "timeseries": [{"bucket": b, **{k: metric_value(k, s)
                                        for k in metrics}}
                       for b, s in sorted(series.items())],
        "breakdowns": {d: sorted(
            [{"key": k, "label": label(d, k),
              **{mk: metric_value(mk, s) for mk in metrics}}
             for k, s in vals.items()],
            key=lambda x: -(float(_D(x.get("spend")).get("value") or 0)))
            for d, vals in breaks.items()},
        "data_quality": data_quality(r, store, adopted=adopted,
                                     currencies=currencies),
        "generated_at": now(),
    }


def data_quality(r, store, *, adopted=0, currencies=None) -> dict:
    """Spec sections 10, 56-59: freshness per provider, named honestly."""
    per = {}
    runs = sorted(r.all("sync_runs"),
                  key=lambda x: str(x.get("completed_at") or ""),
                  reverse=True)
    # A RUN ONLY MAKES THE PLATFORMS IT ACTUALLY READ FRESH. A run named
    # "all" that could not reach TikTok lists TikTok in errors, and a
    # platform in that list is NOT fresh. The first cut of this let the
    # Google snapshot mark every platform LIVE, which is precisely the
    # lie a data-quality panel exists to prevent.
    last_by = {}
    for x in runs:
        at = str(x.get("completed_at") or "")
        if not at:
            continue
        named = str(x.get("provider") or "")
        failed = " ".join(str(e).lower() for e in _L(x.get("errors")))
        targets = ([named] if named and named != "all"
                   else ["google", "meta", "linkedin", "tiktok"])
        for p in targets:
            if p in failed:
                continue
            last_by.setdefault(p, at)
    try:
        snap_at = str((store.get_setting("ads_snapshot", {}) or {})
                      .get("at") or "")
    except Exception:
        snap_at = ""
    if snap_at:
        # the ads snapshot is a GOOGLE pull; it says nothing about the
        # other three and is not allowed to speak for them
        last_by.setdefault("google", snap_at)
    nownow = _dt.datetime.now(_dt.timezone.utc)
    for p in ("google", "meta", "linkedin", "tiktok"):
        at = last_by.get(p) or ""
        if not at:
            per[p] = {"status": "MISSING", "last_sync": None,
                      "why": "no pull or sync has ever read this platform"}
            continue
        try:
            t = _dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=_dt.timezone.utc)
            hours = (nownow - t).total_seconds() / 3600
        except Exception:
            hours = None
        st = ("LIVE" if hours is not None and hours <= FRESH_HOURS else
              "RECENT" if hours is not None and hours <= RECENT_HOURS else
              "DELAYED")
        per[p] = {"status": st, "last_sync": at,
                  "age_hours": round(hours, 1) if hours is not None
                  else None}
    cur = sorted(currencies or set())
    return {"providers": per,
            "adopted_aggregates_excluded": adopted,
            "estimated_flags": "not collected from providers yet; nothing "
                               "is marked exact that is not",
            "currency": {"reporting": REPORTING_CURRENCY, "seen": cur,
                         "mixed": len(cur) > 1,
                         "note": ("MIXED CURRENCIES IN SLICE - sums are "
                                  "not corrected; treat totals with care"
                                  if len(cur) > 1 else
                                  "single currency; no FX applied")},
            "timezone": "provider-reported days; no boundary shifting "
                        "applied"}


# ---------------------------------------------------------------------------
# BUDGET PACING, spec sections 35-36
# ---------------------------------------------------------------------------
def pacing(r, store, *, month_budget=None) -> dict:
    today = _dt.date.today()
    first = today.replace(day=1)
    days_in = (first.replace(month=first.month % 12 + 1, day=1)
               - _dt.timedelta(days=1)).day if first.month != 12 else 31
    res = analytics_query(r, store, {
        "date_range": {"from": first.isoformat(), "to": today.isoformat()},
        "metrics": ["spend"], "dimensions": ["date"],
        "granularity": "DAY"})
    spent = float(_D(res["totals"].get("spend")).get("value") or 0)
    if month_budget is None:
        try:
            import content_engine_ads as ADS
            camps = ((store.get_setting("ads_snapshot", {}) or {})
                     .get("ads") or {}).get("campaigns") or []
            month_budget = sum(float(c.get("budget") or 0)
                               for c in camps) * days_in
        except Exception:
            month_budget = 0.0
    elapsed = today.day / days_in
    projected = spent / today.day * days_in if today.day else spent
    daily_ideal = (month_budget / days_in) if month_budget else 0
    cum, ideal, series = 0.0, 0.0, []
    by_day = {x["bucket"]: float(_D(x.get("spend")).get("value") or 0)
              for x in res["timeseries"]}
    for i in range(today.day):
        d = (first + _dt.timedelta(days=i)).isoformat()
        cum += by_day.get(d, 0.0)
        ideal += daily_ideal
        series.append({"date": d, "actual": round(cum, 2),
                       "ideal": round(ideal, 2)})
    return {"ok": True, "month_budget": round(month_budget or 0, 2),
            "spent": round(spent, 2),
            "elapsed_pct": round(elapsed * 100, 1),
            "used_pct": (round(spent / month_budget * 100, 1)
                         if month_budget else None),
            "projected": round(projected, 2),
            "variance_pct": (round((projected - month_budget)
                                   / month_budget * 100, 1)
                             if month_budget else None),
            "series": series,
            "message": ("no monthly budget is set (campaign budgets sum "
                        "to zero), so pace has nothing to be judged "
                        "against" if not month_budget else
                        f"{spent:,.0f} of {month_budget:,.0f} spent with "
                        f"{elapsed * 100:.0f}% of the month elapsed; "
                        f"projected {projected:,.0f}")}


# ---------------------------------------------------------------------------
# THE AI DATA CONTRACT, spec sections 49-50
# ---------------------------------------------------------------------------
def ai_dataset(r, store, context=None) -> dict:
    """What the AI is HANDED. It interprets this and nothing else."""
    ctx = _D(context)
    q = {"date_range": ctx.get("date_range") or {},
         "filters": ctx.get("filters") or {},
         "metrics": ["spend", "revenue", "conversions", "cpa", "roas",
                     "ctr"],
         "dimensions": ["date", "platform", "campaign", "creative"],
         "granularity": "DAY"}
    res = analytics_query(r, store, q)
    targets = {}
    try:
        import content_engine_ads as ADS
        targets = ADS.targets(ADS.get_economics(store))
    except Exception:
        pass
    return {"context": ctx, "metrics": res["totals"],
            "timeseries": res["timeseries"],
            "breakdowns": res["breakdowns"],
            "comparison": res["comparison"],
            "targets": {k: targets.get(k) for k in
                        ("target_cpa_lead", "target_roas") if targets},
            "data_quality": res["data_quality"],
            "generated_at": res["generated_at"]}


def ai_insights(dataset) -> dict:
    """Deterministic interpretation of the HANDED dataset. Facts are
    computed numbers; hypotheses are labelled hypotheses; a missing
    number is INSUFFICIENT_DATA, never invented. Spec section 50."""
    ds = _D(dataset)
    tot, cmp_ = _D(ds.get("metrics")), _D(ds.get("comparison"))
    changes = _D(cmp_.get("change_percent"))
    insights = []

    def fact(kind, severity, metric, sentence, **kw):
        insights.append({"type": kind, "severity": severity,
                         "metric": metric, "fact": sentence,
                         "hypotheses": kw.get("hypotheses", []),
                         "recommended_actions": kw.get("actions", []),
                         "confidence": kw.get("confidence")})

    spend = _D(tot.get("spend")).get("value")
    if spend is None or spend == 0:
        return {"insights": [], "status": "INSUFFICIENT_DATA",
                "message": "no spend in this slice; there is nothing to "
                           "analyse and nothing will be invented"}
    cpa_now = _D(tot.get("cpa")).get("value")
    cpa_chg = changes.get("cpa")
    if cpa_now is not None and cpa_chg is not None and cpa_chg > 15:
        fact("PERFORMANCE_DECLINE", "HIGH", "cpa",
             f"CPA rose {cpa_chg:g}% against the previous period "
             f"(now {cpa_now:g}).",
             hypotheses=["creative fatigue may be contributing (check the "
                         "fatigue scores)",
                         "auction pressure may have risen (check CPM)"],
             actions=["REVIEW_CREATIVES", "REVIEW_BUDGET"],
             confidence=0.8)
    # concentration: a creative eating spend without matching revenue
    for row in _L(_D(ds.get("breakdowns")).get("creative"))[:6]:
        sp = _D(row.get("spend")).get("value") or 0
        rv = _D(row.get("revenue")).get("value") or 0
        tot_sp = spend or 1
        tot_rv = _D(tot.get("revenue")).get("value") or 0
        if sp / tot_sp > 0.3 and tot_rv and rv / tot_rv < 0.15:
            fact("SPEND_CONCENTRATION", "MEDIUM", "spend",
                 f"{row.get('label')} takes {sp / tot_sp:.0%} of spend "
                 f"but {rv / tot_rv:.0%} of revenue.",
                 hypotheses=["the creative may be fatigued or mistargeted"],
                 actions=["REVIEW_CREATIVE", "GENERATE_VARIATIONS"],
                 confidence=0.75)
    plats = _L(_D(ds.get("breakdowns")).get("platform"))
    scored = [(p.get("key"), _D(p.get("roas")).get("value"))
              for p in plats if _D(p.get("roas")).get("value") is not None]
    if len(scored) >= 2:
        scored.sort(key=lambda x: -x[1])
        (bp, bv), (wp, wv) = scored[0], scored[-1]
        if wv and bv / wv >= 1.5:
            fact("PLATFORM_DISPARITY", "MEDIUM", "roas",
                 f"{bp} returns {bv:g}x against {wp}'s {wv:g}x on the "
                 f"same window.",
                 hypotheses=["marginal return may still differ from "
                             "average; check the allocator before moving "
                             "money"],
                 actions=["REVIEW_ALLOCATION"], confidence=0.7)
    return {"insights": insights, "status": "OK",
            "message": (f"{len(insights)} insight(s), every number taken "
                        f"from the handed dataset; facts and hypotheses "
                        f"are separated" if insights else
                        "nothing crossed a threshold; quiet is a finding")}
