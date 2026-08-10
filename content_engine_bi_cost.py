# -*- coding: utf-8 -*-
"""BI OS: COST INTELLIGENCE.

Spec sections 1-2, 5-8, 12-16, 26-32, 38-41, 56-57, 60-67, 74, 76-81,
99-102.

WHY THIS MODULE EXISTS
----------------------
content_engine_bi.py computes the VALUE half of the business: deals,
revenue, funnel, demand, channel mix. It has no idea what any of it
cost. Section 1 says that is the wrong model:

    BUSINESS VALUE
      - media - AI - API - content generation - data provider
      - automation - infrastructure - other variable
    = CONTRIBUTION VALUE

so REVENUE is not PROFIT and ROAS is not a business return. This module
is the cost half, and it is BI core rather than a billing setting.

FOUR RULES THAT SHAPE EVERY FUNCTION BELOW
------------------------------------------
  Section 6: vendor pricing is NEVER hard-coded. Prices change, and a
  constant in a source file silently rewrites last quarter's numbers.
  Pricing lives in dated versions and a historical cost is computed with
  the price that was in force on that date.

  Section 79: every cost carries HOW IT WAS KNOWN. Provider-reported,
  calculated, allocated and estimated are four different confidences and
  a dashboard that renders them identically is lying by omission.

  Section 13: media spend and software/API cost are never summed into
  one number. They behave differently, they are budgeted separately, and
  mixing them makes both meaningless.

  Section 82: this module sees usage, cost and provider. It never sees,
  stores or renders a key. Credentials stay behind a reference.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _s(x) -> str:
    return "" if x is None else str(x)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _id(*parts) -> str:
    return hashlib.sha1("|".join(_s(p) for p in parts)
                        .encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# 2. WHAT COST INTELLIGENCE TRACKS
# ===========================================================================
#: Section 5. Every tool category. A tool that fits none of these is
#: OTHER and says so; inventing a category per vendor makes the cost
#: breakdown as long as the vendor list and therefore useless.
CATEGORIES = ("AI_MODEL", "SEARCH_DATA", "SERP", "SEO", "SOCIAL", "MEDIA",
              "EMAIL", "CRM", "ENRICHMENT", "SCRAPING", "IMAGE", "VIDEO",
              "AUDIO", "AUTOMATION", "STORAGE", "DATABASE", "COMPUTE",
              "OTHER")

#: Section 13. THE ONE SEPARATION THAT MUST NEVER COLLAPSE. Media spend
#: buys attention; software cost runs the machine. Summing them produces
#: a number that is neither a marketing budget nor an operating cost.
MEDIA_CATEGORIES = ("MEDIA",)

SOFTWARE_CATEGORIES = tuple(c for c in CATEGORIES
                            if c not in MEDIA_CATEGORIES)

#: Section 28. Fixed cost is committed whether or not anyone uses it;
#: variable cost follows usage. Forecasting needs them apart, because
#: only one of the two responds to changing behaviour.
FIXED_MODELS = ("MONTHLY_FIXED",)

#: Section 7. Every pricing model the registry accepts.
PRICING_MODELS = ("PER_TOKEN", "PER_1K_TOKENS", "PER_1M_TOKENS",
                  "PER_REQUEST", "PER_RESULT", "PER_CREDIT", "PER_IMAGE",
                  "PER_VIDEO_SECOND", "PER_VIDEO_MINUTE",
                  "PER_AUDIO_MINUTE", "PER_SEARCH", "PER_RECORD",
                  "PER_EMAIL", "PER_CONTACT", "PER_GB",
                  "PER_COMPUTE_HOUR", "MONTHLY_FIXED", "TIERED", "HYBRID")

#: How many of one unit make the priced quantity. PER_1K_TOKENS means
#: the price is quoted per thousand, so the divisor is 1000.
_UNIT_DIVISOR = {"PER_TOKEN": 1.0, "PER_1K_TOKENS": 1000.0,
                 "PER_1M_TOKENS": 1000000.0}

#: Section 79. HOW a cost figure came to be known, worst to best. The
#: order matters: a rollup reports the WEAKEST quality in it, because a
#: total containing one estimate is an estimate.
QUALITY = ("UNKNOWN", "ESTIMATED", "ALLOCATED", "CALCULATED",
           "PROVIDER_REPORTED", "EXACT")

#: Section 101. The order to prefer when more than one source could
#: answer. Provider-reported beats our own arithmetic every time.
INGESTION_PRIORITY = ("PROVIDER_REPORTED", "CALCULATED", "ALLOCATED",
                      "ESTIMATED")


def weakest_quality(qualities) -> str:
    """The weakest link in a rollup. A total is only as good as its worst
    input, and reporting the best one is how an estimate gets promoted to
    a fact by addition."""
    q = [x for x in (_s(v).upper() for v in _l(qualities)) if x in QUALITY]
    if not q:
        return "UNKNOWN"
    return min(q, key=lambda x: QUALITY.index(x))


# ===========================================================================
# 5-6. THE TOOL REGISTRY AND ITS DATED PRICING
# ===========================================================================
TOOL_FIELDS = ("id", "workspace_id", "name", "provider", "category",
               "capability", "billing_model", "currency", "status",
               "credential_reference", "pricing_source",
               "pricing_updated_at", "monthly_fixed_cost",
               "minimum_commitment", "included_usage", "overage_rules",
               "rate_limit", "quota", "metadata")

SECRET_HINTS = ("api_key", "apikey", "secret", "token", "password",
                "authorization", "bearer", "credential_value")


def register_tool(**kw) -> Dict[str, Any]:
    """One tool in the registry. REFUSES to store anything key-shaped.

    Section 82: BI sees usage, cost and provider. A registry row that
    accidentally carries a token gets that token into every export,
    backup and screenshot the registry ever appears in.
    """
    row = {k: kw.get(k) for k in TOOL_FIELDS}
    leaked = [k for k in kw
              if any(h in _s(k).lower() for h in SECRET_HINTS)
              and _s(k) != "credential_reference"]
    if leaked:
        return {"ok": False, "state": "REFUSED", "fields": sorted(leaked),
                "why": ("a tool registry row may hold a "
                        "credential_reference and never a credential. "
                        "Refused field(s): " + ", ".join(sorted(leaked)))}
    cat = _s(row.get("category")).upper()
    row["category"] = cat if cat in CATEGORIES else "OTHER"
    row["unknown_category"] = cat not in CATEGORIES and bool(cat)
    row["currency"] = _s(row.get("currency")).upper() or "EUR"
    row["status"] = _s(row.get("status")).upper() or "ACTIVE"
    row["id"] = row.get("id") or _id(row.get("name"), row.get("provider"))
    row["is_media"] = row["category"] in MEDIA_CATEGORIES
    return {"ok": True, "tool": row,
            "why": ("registered as " + row["category"]
                    + (" (media spend, kept apart from software cost)"
                       if row["is_media"] else " (software/API cost)"))}


def price_version(tool_id, *, effective_from, pricing_model, pricing,
                  currency="EUR", source="", verified_at="",
                  effective_to=None) -> Dict[str, Any]:
    """One dated price. Section 6: pricing is versioned, never constant.

    effective_to of None means "still in force". A historical report must
    use the version that was live on ITS date, so last quarter's numbers
    do not silently change when a vendor raises a price.
    """
    pm = _s(pricing_model).upper()
    if pm not in PRICING_MODELS:
        return {"ok": False, "state": "REFUSED",
                "why": ("'" + _s(pricing_model) + "' is not a pricing "
                        "model this registry knows. Choices are "
                        + ", ".join(PRICING_MODELS[:6]) + " and others.")}
    if not _s(effective_from):
        return {"ok": False, "state": "REFUSED",
                "why": ("a price with no effective_from cannot be used "
                        "for a historical cost, which is the entire "
                        "reason prices are versioned.")}
    return {"ok": True, "version": {
        "id": _id(tool_id, effective_from, pm),
        "tool_id": _s(tool_id), "effective_from": _s(effective_from),
        "effective_to": effective_to,
        "currency": _s(currency).upper() or "EUR",
        "pricing_model": pm, "pricing_json": _d(pricing),
        "source": _s(source) or "not recorded",
        "verified_at": _s(verified_at)},
        "why": "priced from " + _s(effective_from)}


def price_on(versions, tool_id, on_date) -> Optional[Dict[str, Any]]:
    """The price in force for this tool on this date. None if unpriced.

    Returning None rather than the newest price is deliberate: costing a
    January call at March's price is a quiet, permanent error, and a
    missing price is a fact worth surfacing.
    """
    day = _s(on_date)[:10]
    live = []
    for v in _l(versions):
        d = _d(v)
        if _s(d.get("tool_id")) != _s(tool_id):
            continue
        if _s(d.get("effective_from"))[:10] > day:
            continue
        to = d.get("effective_to")
        if to and _s(to)[:10] < day:
            continue
        live.append(d)
    if not live:
        return None
    return sorted(live, key=lambda x: _s(x.get("effective_from")))[-1]


# ===========================================================================
# 8. THE CANONICAL USAGE EVENT
# ===========================================================================
USAGE_FIELDS = ("id", "workspace_id", "tool_id", "provider",
                "agent_run_id", "workflow_run_id", "business_campaign_id",
                "content_id", "campaign_id", "lead_id", "page_id",
                "task_type", "operation", "request_count", "input_units",
                "output_units", "total_units", "unit_type", "duration",
                "cost", "currency", "status", "occurred_at", "metadata")

USAGE_STATUS = ("SUCCESS", "FAILED", "RETRY", "REJECTED", "CACHED")

#: Section 38. Which statuses produced nothing usable. Their cost is
#: real money and must be visible as waste rather than folded into a
#: total that looks like productive spend.
WASTE_STATUS = ("FAILED", "RETRY", "REJECTED")


def usage_event(**kw) -> Dict[str, Any]:
    """One external call, in the shape section 8 defines."""
    row = {k: kw.get(k) for k in USAGE_FIELDS}
    st = _s(row.get("status")).upper() or "SUCCESS"
    row["status"] = st if st in USAGE_STATUS else "SUCCESS"
    row["currency"] = _s(row.get("currency")).upper() or "EUR"
    row["request_count"] = _f(row.get("request_count"), 1) or 1
    for k in ("input_units", "output_units", "total_units"):
        row[k] = _f(row.get(k))
    if row["total_units"] is None:
        parts = [x for x in (row["input_units"], row["output_units"])
                 if x is not None]
        row["total_units"] = sum(parts) if parts else None
    row["cost"] = _f(row.get("cost"))
    row["is_waste"] = row["status"] in WASTE_STATUS
    row["id"] = row.get("id") or _id(row.get("tool_id"),
                                     row.get("occurred_at"),
                                     row.get("operation"),
                                     row.get("agent_run_id"))
    return row


def cost_of(event, versions, *, tool=None) -> Dict[str, Any]:
    """What one call cost, and HOW that was known.

    Section 101 in order:
      1. the provider told us          -> PROVIDER_REPORTED
      2. exact usage x a dated price   -> CALCULATED
      3. neither                       -> UNKNOWN, and it says so

    It never guesses. An unpriced call returns UNKNOWN with the reason,
    because a zero here would understate spend forever and a made-up
    number would be worse.
    """
    ev = _d(event)
    if ev.get("cost") is not None:
        return {"cost": _f(ev["cost"]), "currency": ev.get("currency"),
                "quality": "PROVIDER_REPORTED",
                "why": "the provider reported this cost with the call"}
    pv = price_on(versions, ev.get("tool_id"), ev.get("occurred_at"))
    if pv is None:
        return {"cost": None, "quality": "UNKNOWN",
                "why": ("no price is on record for tool "
                        + _s(ev.get("tool_id")) + " on "
                        + _s(ev.get("occurred_at"))[:10]
                        + ". The call is counted; its cost is not "
                        "invented.")}
    pm = _s(pv.get("pricing_model"))
    pj = _d(pv.get("pricing_json"))
    cur = pv.get("currency")
    if pm in _UNIT_DIVISOR:
        div = _UNIT_DIVISOR[pm]
        rin = _f(pj.get("input"), 0) or 0
        rout = _f(pj.get("output"), 0) or 0
        rcache = _f(pj.get("cached_input"))
        cin = _f(ev.get("input_units"), 0) or 0
        cout = _f(ev.get("output_units"), 0) or 0
        ccache = _f(ev.get("cached_input_units"), 0) or 0
        amount = (cin / div) * rin + (cout / div) * rout
        if rcache is not None and ccache:
            # Cached input is normally cheaper. Charging it at the full
            # input rate overstates AI cost on every cached call.
            amount += (ccache / div) * rcache
        return {"cost": round(amount, 6), "currency": cur,
                "quality": "CALCULATED",
                "why": ("usage times the price in force on "
                        + _s(pv.get("effective_from"))[:10])}
    per = _f(pj.get("unit_price"))
    if per is None:
        return {"cost": None, "quality": "UNKNOWN",
                "why": ("the " + pm + " price for this tool has no "
                        "unit_price recorded")}
    qty = (_f(ev.get("total_units"))
           if ev.get("total_units") is not None
           else _f(ev.get("request_count"), 1))
    return {"cost": round((qty or 0) * per, 6), "currency": cur,
            "quality": "CALCULATED",
            "why": (_s(qty) + " x " + _s(per) + " per unit, priced from "
                    + _s(pv.get("effective_from"))[:10])}


# ===========================================================================
# 80. MULTI-CURRENCY
# ===========================================================================
def convert(amount, *, from_currency, to_currency, rate=None,
            fx_date="") -> Dict[str, Any]:
    """Convert, keeping the original. Section 80: never discard it.

    Without a rate it returns UNCONVERTED rather than assuming parity.
    Treating 100 USD as 100 EUR is a 7 to 15 percent error that nothing
    downstream can detect.
    """
    a = _f(amount)
    fc, tc = _s(from_currency).upper(), _s(to_currency).upper()
    if a is None:
        return {"ok": False, "why": "no amount to convert"}
    if fc == tc:
        return {"ok": True, "original_amount": a, "original_currency": fc,
                "reporting_amount": a, "reporting_currency": tc,
                "fx_rate": 1.0, "fx_date": _s(fx_date),
                "why": "same currency, no conversion"}
    r = _f(rate)
    if r is None or r <= 0:
        return {"ok": False, "state": "UNCONVERTED",
                "original_amount": a, "original_currency": fc,
                "reporting_currency": tc,
                "why": ("no FX rate for " + fc + " to " + tc + ". The "
                        "amount is kept in its own currency rather than "
                        "assumed to be one to one.")}
    return {"ok": True, "original_amount": a, "original_currency": fc,
            "reporting_amount": round(a * r, 6), "reporting_currency": tc,
            "fx_rate": r, "fx_date": _s(fx_date),
            "why": _s(a) + " " + fc + " at " + _s(r) + " on "
                   + (_s(fx_date) or "an unrecorded date")}


# ===========================================================================
# 26-27. ALLOCATION
# ===========================================================================
COST_KINDS = ("DIRECT_COST", "ALLOCATED_COST", "SHARED_COST")

ALLOCATION_METHODS = ("DIRECT", "USAGE_PROPORTIONAL",
                      "REQUEST_PROPORTIONAL", "TOKEN_PROPORTIONAL",
                      "REVENUE_PROPORTIONAL", "EQUAL_SPLIT", "MANUAL")


def allocate(amount, targets, *, method="USAGE_PROPORTIONAL",
             weights=None) -> Dict[str, Any]:
    """Spread a shared cost across targets by a stated rule.

    Everything this returns is marked ALLOCATED, never EXACT. A monthly
    subscription split across six projects is a decision about how to
    apportion, not a measurement, and section 79 forbids hiding that.
    """
    a = _f(amount)
    tg = [_s(t) for t in _l(targets) if _s(t)]
    m = _s(method).upper()
    if a is None or not tg:
        return {"ok": False,
                "why": "an allocation needs an amount and at least one "
                       "target"}
    if m not in ALLOCATION_METHODS:
        return {"ok": False,
                "why": "'" + m + "' is not an allocation method"}
    w = _d(weights)
    if m == "EQUAL_SPLIT" or not w:
        if m != "EQUAL_SPLIT" and not w:
            return {"ok": False, "state": "NO BASIS",
                    "why": (m + " needs weights to divide by. Without "
                            "them the split would be equal while "
                            "claiming to be proportional, which is a "
                            "different and unstated decision.")}
        share = a / len(tg)
        rows = [{"target": t, "amount": round(share, 6),
                 "basis": 1.0 / len(tg)} for t in tg]
    else:
        total = sum(_f(w.get(t), 0) or 0 for t in tg)
        if total <= 0:
            return {"ok": False, "state": "NO BASIS",
                    "why": ("every weight is zero, so there is no "
                            "proportion to allocate by")}
        rows = [{"target": t,
                 "amount": round(a * (_f(w.get(t), 0) or 0) / total, 6),
                 "basis": round((_f(w.get(t), 0) or 0) / total, 6)}
                for t in tg]
    return {"ok": True, "method": m, "kind": "ALLOCATED_COST",
            "quality": "ALLOCATED", "rows": rows, "total": a,
            "why": (_s(a) + " split across " + str(len(tg))
                    + " target(s) by " + m + ". This is an apportionment "
                    "rule, not a measurement.")}


# ===========================================================================
# 29-31. BUDGETS, FORECAST, GUARDRAILS
# ===========================================================================
BUDGET_SCOPES = ("WORKSPACE", "OS", "AGENT", "TOOL", "WORKFLOW",
                 "CAMPAIGN")

GUARDRAIL_STATES = ("NORMAL", "80_PERCENT", "90_PERCENT", "LIMITED",
                    "EXCEEDED")


def forecast(spent, *, budget, elapsed_fraction) -> Dict[str, Any]:
    """Project month end from spend so far. Section 29.

    Refuses to project from almost no elapsed time: three days of spend
    times ten is not a forecast, it is one number wearing a trend, and
    acting on it early is how a budget alarm loses its credibility.
    """
    s = _f(spent)
    b = _f(budget)
    el = _f(elapsed_fraction)
    if s is None or el is None or el <= 0:
        return {"state": "NO FORECAST",
                "why": ("a projection needs spend so far and how much of "
                        "the period has elapsed")}
    if el < 0.15:
        return {"state": "TOO EARLY", "spent": s, "elapsed": el,
                "why": (str(round(el * 100)) + "% of the period has "
                        "elapsed. Projecting from this little is "
                        "arithmetic, not a forecast.")}
    projected = s / el
    out = {"state": "PROJECTED", "spent": s, "elapsed": el,
           "projected": round(projected, 2), "budget": b,
           "why": (_s(round(s, 2)) + " spent at "
                   + str(round(el * 100)) + "% elapsed projects to "
                   + _s(round(projected, 2)))}
    if b:
        out["variance"] = round(projected - b, 2)
        out["over"] = projected > b
        out["why"] += (", against a budget of " + _s(b)
                       + (" (over by " + _s(round(projected - b, 2)) + ")"
                          if projected > b else " (within budget)"))
    return out


def guardrail(spent, budget) -> Dict[str, Any]:
    """Which band this budget is in, and what that permits.

    Section 31. The bands restrict, they do not stop the business: at
    100 percent optional expensive operations are blocked and a human
    can still override, because a hard stop on a real campaign is its
    own kind of damage.
    """
    s, b = _f(spent, 0) or 0, _f(budget)
    if not b or b <= 0:
        return {"state": "NORMAL", "used": None,
                "why": "no budget is set for this scope, so nothing is "
                       "restricted"}
    used = s / b
    if used >= 1.0:
        st, act = "EXCEEDED", ("optional expensive operations are "
                               "blocked; a human can override")
    elif used >= 0.9:
        st, act = "LIMITED", "non-essential jobs are restricted"
    elif used >= 0.8:
        st, act = "80_PERCENT", "warning only, nothing is restricted"
    else:
        st, act = "NORMAL", "nothing is restricted"
    if used >= 0.9 and used < 1.0:
        st = "90_PERCENT" if used < 0.95 else "LIMITED"
    return {"state": st, "used": round(used, 4), "spent": s, "budget": b,
            "action": act,
            "why": (str(round(used * 100, 1)) + "% of budget used; "
                    + act)}


# ===========================================================================
# 32. THE COST POLICY ENGINE
# ===========================================================================
POLICY_LIMITS = ("max_run_cost", "max_daily_spend",
                 "max_generation_attempts", "max_tool_calls",
                 "max_retries", "max_provider_cost", "max_model_tier")


def check_policy(policy, proposed) -> Dict[str, Any]:
    """Would this run breach a cost policy? Checked BEFORE spending.

    A limit discovered after the money is gone is an audit note. This
    runs first, names the limit and the number, and returns BLOCKED so a
    caller cannot mistake it for advice.
    """
    p, q = _d(policy), _d(proposed)
    breaches = []
    for k in POLICY_LIMITS:
        lim = _f(p.get(k))
        val = _f(q.get(k))
        if lim is None or val is None:
            continue
        if val > lim:
            breaches.append({"limit": k, "allowed": lim, "proposed": val})
    if not breaches:
        return {"ok": True, "state": "WITHIN POLICY",
                "why": "nothing proposed exceeds a configured limit"}
    return {"ok": False, "state": "BLOCKED", "breaches": breaches,
            "why": ("; ".join(_s(b["limit"]) + " allows "
                              + _s(b["allowed"]) + ", this asks for "
                              + _s(b["proposed"]) for b in breaches)
                    + ". Checked before the spend, not after it.")}


# ===========================================================================
# 38-40. WASTE
# ===========================================================================
def waste(events, versions=()) -> Dict[str, Any]:
    """What was spent producing nothing usable. Section 38.

    Failed, retried and rejected calls cost the same money as successful
    ones. A total that hides them makes an expensive agent look merely
    busy, and this is the number that tells a founder to change a
    default rather than buy more capacity.
    """
    rows = [_d(e) for e in _l(events)]
    if not rows:
        return {"state": "NO DATA",
                "why": "no usage events in this window"}
    total = wasted = 0.0
    quals, unpriced = [], 0
    by_reason: Dict[str, float] = {}
    for e in rows:
        c = cost_of(e, versions)
        quals.append(c["quality"])
        amt = _f(c.get("cost"))
        if amt is None:
            unpriced += 1
            continue
        total += amt
        if e.get("is_waste"):
            wasted += amt
            key = _s(e.get("status"))
            by_reason[key] = round(by_reason.get(key, 0.0) + amt, 6)
    pct = (wasted / total * 100) if total else None
    return {"state": "OK", "total": round(total, 4),
            "wasted": round(wasted, 4),
            "waste_pct": (round(pct, 1) if pct is not None else None),
            "by_reason": by_reason,
            "unpriced_events": unpriced,
            "quality": weakest_quality(quals),
            "why": (("no cost could be established for any event"
                     if not total else
                     _s(round(wasted, 2)) + " of " + _s(round(total, 2))
                     + " produced nothing usable ("
                     + _s(round(pct, 1)) + "%)")
                    + (". " + str(unpriced) + " event(s) had no price on "
                       "record and are counted but not costed."
                       if unpriced else ""))}


# ===========================================================================
# 65-66. CACHE ECONOMICS AND DEDUPLICATION
# ===========================================================================
def cache_economics(hits, misses, *, avoided_unit_cost=None
                    ) -> Dict[str, Any]:
    """What caching saved. Section 65.

    The saving is ESTIMATED, and says so: an avoided call has no invoice,
    so its cost is what the call would have cost, which is a
    counterfactual rather than a measurement.
    """
    h, m = _f(hits, 0) or 0, _f(misses, 0) or 0
    rate = (h / (h + m)) if (h + m) else None
    unit = _f(avoided_unit_cost)
    saved = (h * unit) if unit is not None else None
    return {"hits": h, "misses": m,
            "hit_rate": (round(rate, 4) if rate is not None else None),
            "calls_avoided": h,
            "estimated_saving": (round(saved, 4)
                                 if saved is not None else None),
            "quality": "ESTIMATED",
            "why": (_s(int(h)) + " call(s) avoided"
                    + ("; saving is ESTIMATED because an avoided call "
                       "has no invoice" if saved is not None else
                       "; no unit cost supplied, so no saving is "
                       "claimed"))}


def dedupe_key(*, workspace, operation, params, freshness_window="") -> str:
    """Section 66. The identity of a request, for cache reuse."""
    flat = "&".join(_s(k) + "=" + _s(v)
                    for k, v in sorted(_d(params).items()))
    return _id(workspace, operation, flat, freshness_window)


# ===========================================================================
# 41-42. ANOMALIES
# ===========================================================================
ANOMALY_TYPES = ("API_COST_SPIKE", "TOKEN_SPIKE", "VIDEO_COST_SPIKE",
                 "CLOUD_COST_SPIKE", "RETRY_STORM", "SCRAPING_SPIKE",
                 "EMAIL_COST_SPIKE", "UNUSED_SUBSCRIPTION",
                 "QUOTA_NEAR_LIMIT")

#: How far above the recent baseline counts as a spike, and the minimum
#: baseline below which a ratio means nothing. Two euros becoming six is
#: a 200 percent rise and not news.
SPIKE_RATIO = 1.5
MIN_BASELINE = 5.0


def detect_anomaly(kind, *, actual, baseline, driver="",
                   window="") -> Dict[str, Any]:
    """One cost anomaly, with the number that fired it. Section 42.

    Refuses to fire on a baseline too small to carry a ratio, which is
    the difference between an alert that gets read and one that gets
    muted.
    """
    k = _s(kind).upper()
    a, b = _f(actual), _f(baseline)
    if k not in ANOMALY_TYPES:
        return {"state": "UNKNOWN TYPE",
                "why": "'" + k + "' is not an anomaly type"}
    if a is None or b is None:
        return {"state": "INSUFFICIENT_DATA",
                "why": "an anomaly needs both an actual and a baseline"}
    if b < MIN_BASELINE:
        return {"state": "INSUFFICIENT_DATA", "actual": a, "baseline": b,
                "why": ("a baseline of " + _s(b) + " is too small for a "
                        "ratio to mean anything. Doubling a trivial "
                        "number is not a spike.")}
    ratio = a / b
    if ratio < SPIKE_RATIO:
        return {"state": "NORMAL", "ratio": round(ratio, 3),
                "why": (_s(round((ratio - 1) * 100, 1))
                        + "% against baseline, below the "
                        + _s(int((SPIKE_RATIO - 1) * 100))
                        + "% threshold")}
    return {"state": "ANOMALY", "type": k, "actual": a, "baseline": b,
            "ratio": round(ratio, 3),
            "severity": ("HIGH" if ratio >= 2 else "MEDIUM"),
            "driver": _s(driver) or "not identified",
            "window": _s(window),
            "monthly_impact": round((a - b) * 30, 2),
            "why": (_s(round((ratio - 1) * 100)) + "% above a baseline of "
                    + _s(b) + (". Driver: " + _s(driver) if driver else
                               ". No driver identified yet.")
                    + " If it persists that is "
                    + _s(round((a - b) * 30, 2)) + " a month.")}


# ===========================================================================
# 62-63. SUBSCRIPTION UTILISATION AND REDUNDANCY
# ===========================================================================
def subscription_utilisation(monthly_cost, *, quota, used) -> Dict:
    """What a fixed plan is actually returning. Section 62."""
    c, q, u = _f(monthly_cost), _f(quota), _f(used)
    if c is None:
        return {"state": "NO COST", "why": "no monthly cost recorded"}
    if not q or q <= 0:
        return {"state": "NO QUOTA", "monthly_cost": c,
                "why": ("no quota recorded, so utilisation cannot be "
                        "computed. The cost is still real.")}
    pct = (u or 0) / q
    return {"state": ("UNDERUSED" if pct < 0.25 else "OK"),
            "monthly_cost": c, "utilisation": round(pct, 4),
            "cost_per_used_unit": (round(c / u, 6) if u else None),
            "why": (str(round(pct * 100, 1)) + "% of quota used for "
                    + _s(c) + " a month"
                    + (". A smaller plan may cover this."
                       if pct < 0.25 else ""))}


def redundancy(tools) -> List[Dict[str, Any]]:
    """Two tools serving one capability. Section 63: FLAG, never cancel.

    Cancelling on a rule would eventually cut the fallback that keeps a
    campaign alive during an outage. This surfaces the pair and the
    numbers and stops there.
    """
    by_cap: Dict[str, List[dict]] = {}
    for t in _l(tools):
        d = _d(t)
        cap = _s(d.get("capability")).upper()
        if cap:
            by_cap.setdefault(cap, []).append(d)
    out = []
    for cap, rows in by_cap.items():
        if len(rows) < 2:
            continue
        out.append({
            "capability": cap,
            "tools": [{"name": r.get("name"),
                       "monthly_cost": _f(r.get("monthly_fixed_cost")),
                       "status": r.get("status")} for r in rows],
            "state": "REDUNDANCY REVIEW",
            "why": (str(len(rows)) + " tools serve " + cap + ". This is "
                    "flagged for a human to look at and nothing is "
                    "cancelled: a second provider is also a fallback.")})
    return out


# ===========================================================================
# 74. COST CENTRES
# ===========================================================================
COST_CENTERS = ("SEO", "PAID_ACQUISITION", "CONTENT", "EMAIL", "SALES",
                "INFRASTRUCTURE", "AI_PLATFORM", "BI")


# ===========================================================================
# 1, 73. THE CONTRIBUTION WATERFALL
# ===========================================================================
#: Section 73. The order costs come off revenue. Named here once so the
#: waterfall on screen and the arithmetic below cannot disagree.
WATERFALL = ("revenue", "cogs", "media", "ai", "tools", "cloud",
             "other_variable")


def contribution(**parts) -> Dict[str, Any]:
    """Revenue minus every variable cost. Section 1.

    Returns CONTRIBUTION and refuses to call it profit. Section 73 is
    explicit: contribution is not net profit unless every business
    expense is in it, and salaries, rent and tax are not in this model.
    """
    rev = _f(parts.get("revenue"))
    if rev is None:
        return {"state": "NO REVENUE",
                "why": ("contribution starts from revenue, and none was "
                        "supplied")}
    steps, running, missing = [], rev, []
    for key in WATERFALL[1:]:
        v = _f(parts.get(key))
        if v is None:
            missing.append(key)
            continue
        running -= v
        steps.append({"step": key, "amount": v,
                      "running": round(running, 2)})
    return {"state": "OK", "revenue": rev, "steps": steps,
            "contribution": round(running, 2),
            "missing": missing,
            "is_net_profit": False,
            "why": ("revenue less " + str(len(steps)) + " cost line(s) "
                    "gives CONTRIBUTION, which is NOT net profit: "
                    "salaries, rent and tax are not in this model."
                    + (" Not supplied and therefore not deducted: "
                       + ", ".join(missing) + "." if missing else ""))}


def split_media_and_software(events, versions=()) -> Dict[str, Any]:
    """Section 13. Media spend and software cost, never one number."""
    media = software = 0.0
    quals = []
    for e in _l(events):
        d = _d(e)
        c = cost_of(d, versions)
        quals.append(c["quality"])
        amt = _f(c.get("cost"))
        if amt is None:
            continue
        cat = _s(_d(d.get("metadata")).get("category")).upper()
        if cat in MEDIA_CATEGORIES:
            media += amt
        else:
            software += amt
    return {"media_spend": round(media, 4),
            "software_cost": round(software, 4),
            "quality": weakest_quality(quals),
            "why": ("media spend buys attention and software cost runs "
                    "the machine. They are budgeted separately and "
                    "summing them produces a number that is neither.")}


# ===========================================================================
# 102. THE MINIMUM TABLES THIS DOMAIN ADDS
# ===========================================================================
TABLES = ("tool_registry", "tool_pricing_versions", "tool_usage_events",
          "cost_centers", "cost_allocation_rules", "cost_budgets",
          "cost_alerts", "agent_economics_daily",
          "workflow_economics_daily", "tool_economics_daily",
          "subscription_costs", "cost_anomalies", "cost_forecasts")

# ===========================================================================
# 58, 103. THE COST EVENTS BI CONSUMES
# ===========================================================================
COST_EVENTS = ("TOOL_USAGE_RECORDED", "AGENT_COST_RECORDED",
               "WORKFLOW_COST_RECORDED", "CONTENT_COST_RECORDED",
               "SEO_ACTION_COST_RECORDED", "CAMPAIGN_COST_UPDATED",
               "EMAIL_COST_UPDATED", "INFRASTRUCTURE_COST_UPDATED")

BI_EVENTS = COST_EVENTS + ("AGENT_RUN_COMPLETED", "API_USAGE_RECORDED",
                           "WORKFLOW_COMPLETED", "CONTENT_COST_UPDATED",
                           "SEO_ACTION_COST_UPDATED",
                           "CAMPAIGN_SPEND_UPDATED", "INFRA_COST_UPDATED",
                           "REVENUE_RECORDED")


def receive_cost_event(raw) -> Dict[str, Any]:
    """The front door for a cost event from any OS. Section 59."""
    d = _d(raw)
    ev = _s(d.get("event")).upper()
    if ev not in BI_EVENTS:
        return {"ok": False, "event": ev,
                "why": ("'" + ev + "' is not a cost event BI consumes. "
                        "An undeclared event has no handler and would "
                        "be dropped silently.")}
    usage, cost = _d(d.get("usage")), _d(d.get("cost"))
    return {"ok": True, "event": ev,
            "usage": usage_event(
                tool_id=d.get("tool"), provider=d.get("provider"),
                workspace_id=d.get("workspace_id"),
                agent_run_id=d.get("agent_run_id"),
                workflow_run_id=d.get("workflow_id"),
                content_id=d.get("content_id"),
                campaign_id=d.get("campaign_id"),
                operation=d.get("operation") or d.get("tool"),
                unit_type=usage.get("unit"),
                total_units=usage.get("quantity"),
                cost=cost.get("amount"),
                currency=cost.get("currency"),
                status=d.get("status"),
                occurred_at=d.get("timestamp"),
                metadata={"source_system": d.get("source_system"),
                          "category": d.get("category")}),
            "why": "normalized from " + _s(d.get("source_system"))}
