"""
content_engine_media_plan.py
============================================================================
PHASE 3: THE MEDIA PLANNER, BUDGET ALLOCATION, THE SIMULATOR, THE LAUNCH.

FORECASTS ARE RANGES OR THEY ARE LIES
  Every number this file produces about the future comes back as a low,
  a base and a high, with the assumption that produced it named beside
  it. A single expected CPA is a promise nobody can keep, and a founder
  who plans a month around one is planning around a rounding error.

  With no history it refuses to forecast at all rather than inventing a
  benchmark. "Industry average" is somebody else's business.

ALLOCATION USES MARGINAL RETURN, NOT AVERAGE
  The mistake this file exists to avoid: Meta at ROAS 4.1 and TikTok at
  1.8 does not mean move everything to Meta. The next thousand euros on
  Meta does not earn what the last thousand earned, because the cheapest
  audience is bought first. Allocation therefore works on the MARGINAL
  return implied by the spend curve, caps how far it will move money in
  one step, and prints the reasoning.

THE LAUNCH GATE
  pre_flight() composes the campaign validation from media_os with the
  things only a plan knows: whether the platforms are reachable, whether
  the audience survives its capability mapping, whether a creative is
  attached, whether tracking exists. It returns VALID, WARNING or ERROR
  and a launch never proceeds on an ERROR.

NOTHING HERE SPENDS MONEY OR CALLS A PLATFORM. Every write still goes
through the order engine that already holds the approval tiers.
============================================================================
"""

from __future__ import annotations

import logging
import math

import content_engine_media_creative as MC
import content_engine_media_os as M
import content_engine_os_core as CORE
from content_engine_os_core import _D, _L, now, rid

log = logging.getLogger("content_engine.media_plan")

#: The eight steps. Declared once so the wizard, the validator and the
#: progress indicator cannot disagree about what is left to do.
WIZARD_STEPS = (
    ("objective", "Objective", "What are you trying to achieve, and which "
                               "number tells you it worked"),
    ("platforms", "Platforms", "Where it runs, and what each one can "
                               "actually do"),
    ("budget", "Budget", "How much, over how long, split how"),
    ("audience", "Audience", "Who, and what each platform will drop"),
    ("creative", "Creative", "What they see"),
    ("tracking", "Tracking", "How you will know it worked"),
    ("review", "Review", "Everything at once, before it costs anything"),
    ("launch", "Launch", "Schedule it or send it"),
)

#: The KPI a plan is judged on. One list, used by the planner and the
#: optimisation policy, so a plan cannot target something nothing measures.
KPIS = ("CPA", "ROAS", "REVENUE", "LEADS", "CTR", "CPC", "CPM")

#: How far allocation will move money in a single pass. A reallocation
#: that swings 60 percent of a budget overnight destroys the learning
#: phase on every campaign it touches, and the platforms punish it.
MAX_SHIFT = 0.25

#: Below this an arm has not earned an opinion. Same floor the creative
#: matrix uses, stated once and imported rather than retyped.
MIN_CONV = MC.MIN_CONVERSIONS


# ---------------------------------------------------------------------------
# HISTORY. Everything the planner knows comes from what was measured.
# ---------------------------------------------------------------------------
def history(r, days=90) -> dict:
    """Spend and outcome per platform, from ad_metrics. No benchmarks."""
    camps = {c.get("id"): c for c in r.all("media_campaigns")}
    by = {}
    for m in r.all("ad_metrics"):
        c = camps.get(m.get("campaign_id")) or {}
        p = m.get("provider") or c.get("provider")
        if not p:
            continue
        b = by.setdefault(p, {"provider": p, "spend": 0.0, "impressions": 0.0,
                              "clicks": 0.0, "conversions": 0.0,
                              "conversion_value": 0.0, "days": set()})
        for k in ("spend", "impressions", "clicks", "conversions",
                  "conversion_value"):
            try:
                b[k] += float(m.get(k) or 0)
            except Exception:
                pass
        if m.get("day"):
            b["days"].add(m["day"])
    out = {}
    for p, b in by.items():
        days_seen = len(b.pop("days"))
        spend, conv = b["spend"], b["conversions"]
        out[p] = {**b, "days": days_seen,
                  "cpa": round(spend / conv, 2) if conv else None,
                  "roas": round(b["conversion_value"] / spend, 2) if spend else None,
                  "cvr": (round(conv / b["clicks"] * 100, 2)
                          if b["clicks"] else None),
                  "daily_spend": round(spend / days_seen, 2) if days_seen else None,
                  "enough": conv >= MIN_CONV}
    return out


#: The one diminishing-returns curve. Fifteen percent softer per doubling
#: of spend. It is an ASSUMPTION, not a measurement, and every caller says
#: so out loud. It lives here as ONE number because the forecast and the
#: allocator both use it: a forecast that scales linearly while the
#: allocator decays would put two contradictory numbers on one screen.
DECAY_PER_DOUBLING = 0.85

#: Below this a platform's own spend is too small to decay against.
DECAY_FLOOR = 1000.0


def efficiency_decay(base_spend, new_spend) -> float:
    """How much worse the next euro performs than the last one did.

    Returns 1.0 when the new spend is not bigger than the base, because
    nothing is being stretched. Above it, performance softens smoothly by
    DECAY_PER_DOUBLING: the cheapest audience is bought first, so the tenth
    thousand never performs like the first."""
    b = max(float(base_spend or 0), 1.0)
    n = max(float(new_spend or 0), 1.0)
    if n <= b:
        return 1.0
    return round(DECAY_PER_DOUBLING ** math.log(n / b, 2), 4)


def marginal_roas(stats) -> float:
    """What the NEXT euro on this platform is likely to return."""
    s = _D(stats)
    avg = s.get("roas")
    if not avg:
        return 0.0
    return round(avg * efficiency_decay(DECAY_FLOOR, s.get("spend") or 0), 3)


def allocate(r, total_budget, *, current=None, days=90) -> dict:
    """Split a budget across platforms on MARGINAL return.

    Refuses to allocate on platforms with no history rather than guessing,
    and never moves more than MAX_SHIFT of the budget in one pass."""
    try:
        total = float(total_budget or 0)
    except Exception:
        return {"ok": False, "message": "the budget has to be a number"}
    if total <= 0:
        return {"ok": False, "message": "the budget has to be more than zero"}
    hist = history(r, days)
    ready = {p: s for p, s in hist.items() if s.get("enough")}
    if not ready:
        live = [p for p in M.PROVIDERS if M.Adapter(p).available()[0]]
        even = round(total / len(live), 2) if live else 0
        return {"ok": True, "basis": "no history",
                "rows": [{"provider": p, "share": round(1 / len(live), 3),
                          "amount": even, "why": "split evenly because "
                                                 "nothing has run here yet"}
                         for p in live],
                "message": ("No platform has "
                            f"{MIN_CONV} conversions yet, so there is nothing "
                            "to allocate ON. The split is even and the only "
                            "honest thing to do is run it and look again in "
                            "two weeks. Inventing a split from an industry "
                            "benchmark would be somebody else's business, "
                            "not yours.")}
    marg = {p: marginal_roas(s) for p, s in ready.items()}
    tot = sum(marg.values()) or 1.0
    cur = _D(current)
    rows = []
    for p, s in ready.items():
        want = total * (marg[p] / tot)
        now_amt = float(cur.get(p) or 0)
        if now_amt:
            cap = now_amt * MAX_SHIFT
            want = max(now_amt - cap, min(now_amt + cap, want))
        rows.append({
            "provider": p, "amount": round(want, 2),
            "share": round(want / total, 3),
            "average_roas": s.get("roas"), "marginal_roas": marg[p],
            "conversions": int(s.get("conversions") or 0),
            "why": (f"average ROAS {s.get('roas')}, but the next euro is "
                    f"modelled at {marg[p]} because this platform has "
                    f"already absorbed {s.get('spend'):,.0f} and the cheap "
                    f"inventory goes first"
                    + (f". Capped at {int(MAX_SHIFT * 100)} percent of its "
                       f"current {now_amt:,.0f} so the learning phase "
                       f"survives" if now_amt else ""))})
    rows.sort(key=lambda x: -x["amount"])
    skipped = [p for p in hist if p not in ready]
    return {"ok": True, "basis": "marginal return", "rows": rows,
            "skipped": skipped,
            "message": (f"{total:,.0f} split across {len(rows)} platform(s) "
                        f"on MARGINAL return, not average: doubling a "
                        f"campaign at ROAS 4 does not buy another ROAS 4."
                        + (f" {len(skipped)} platform(s) left out for having "
                           f"under {MIN_CONV} conversions."
                           if skipped else ""))}


# ---------------------------------------------------------------------------
# THE PLAN
# ---------------------------------------------------------------------------
def forecast(r, *, budget, kpi="CPA", days=30, provider=None) -> dict:
    """A range, with the assumption named. Never a single number.

    With no history it says so and forecasts nothing, because a benchmark
    borrowed from somebody else's account is the most confident wrong
    number a media plan can contain."""
    hist = history(r)
    pool = ({provider: hist[provider]} if provider and provider in hist
            else {p: s for p, s in hist.items() if s.get("enough")})
    if not pool:
        return {"ok": False, "basis": "none",
                "message": (f"nothing here has {MIN_CONV} conversions behind "
                            f"it yet, so any forecast would be invented. Run "
                            f"a small budget for two weeks and this becomes "
                            f"answerable.")}
    spend = sum(s["spend"] for s in pool.values())
    conv = sum(s["conversions"] for s in pool.values())
    val = sum(s["conversion_value"] for s in pool.values())
    cpa = spend / conv if conv else None
    roas = val / spend if spend else None
    try:
        budget = float(budget or 0)
    except Exception:
        return {"ok": False, "message": "the budget has to be a number"}
    # The band widens with how little evidence there is. Twenty conversions
    # buys a tighter answer than eleven, and the reader should see that.
    width = 0.20 if conv >= 100 else (0.35 if conv >= 30 else 0.5)
    def band(v):
        return None if not v else {"low": round(v * (1 - width), 2),
                                   "base": round(v, 2),
                                   "high": round(v * (1 + width), 2)}
    # THE SAME CURVE THE ALLOCATOR USES. A forecast that scales the budget
    # linearly says "double the money, double the leads" on one half of the
    # screen while the allocator says the opposite on the other half.
    decay = efficiency_decay(spend, budget)
    if cpa:
        cpa = cpa / decay
    if roas:
        roas = roas * decay
    leads = (budget / cpa) if cpa else None
    return {"ok": True, "basis": f"{int(conv)} conversions over "
                                 f"{spend:,.0f} of spend",
            "kpi": kpi, "budget": budget, "days": days,
            "cpa": band(cpa), "roas": band(roas),
            "conversions": ({"low": round(leads * (1 - width)),
                             "base": round(leads),
                             "high": round(leads * (1 + width))}
                            if leads else None),
            "revenue": band(budget * roas) if roas else None,
            "confidence_band": f"plus or minus {int(width * 100)} percent",
            "efficiency_decay": decay,
            "assumptions": [
                f"past performance repeats: {int(conv)} conversions over "
                f"{spend:,.0f} of measured spend",
                (f"efficiency softens to {decay:g} of what it was, because "
                 f"{budget:,.0f} is more than the {spend:,.0f} already "
                 f"spent and the cheap audience is bought first. Same curve "
                 f"the allocator uses" if decay < 1 else
                 "no efficiency decay applied: this budget is not bigger "
                 "than what has already been spent"),
                f"the band is plus or minus {int(width * 100)} percent "
                f"because there are {int(conv)} conversions behind it, not "
                f"because anybody measured the variance",
                "no seasonality, no auction change, no creative fatigue is "
                "modelled here",
            ],
            "message": (f"between {round(leads * (1 - width))} and "
                        f"{round(leads * (1 + width))} conversions for "
                        f"{budget:,.0f}, if the last {int(conv)} repeat. "
                        f"That is an estimate with a named assumption, not a "
                        f"forecast anybody should sign."
                        if leads else "not enough history to put a range on")}


def save_plan(r, *, plan_id="", objective="LEADS", budget=0.0, currency="EUR",
              period_start="", period_end="", target_cpa=None,
              target_roas=None, target_leads=None, kpi="CPA") -> dict:
    """A media plan: what you want, what it costs, what it might return."""
    if objective not in M.OBJECTIVES:
        return {"ok": False,
                "message": f"{objective!r} is not an objective. They are: "
                           + ", ".join(M.OBJECTIVES)}
    if kpi not in KPIS:
        return {"ok": False,
                "message": f"{kpi!r} is not a KPI this engine measures. It "
                           f"measures: " + ", ".join(KPIS)}
    alloc = allocate(r, budget)
    fc = forecast(r, budget=budget, kpi=kpi)
    pid = plan_id or rid("mplan", r.ws, objective, period_start or now())
    rec = r.put("media_plans", {
        "id": pid, "objective": objective, "budget": float(budget or 0),
        "currency": currency, "period_start": period_start,
        "period_end": period_end, "target_cpa": target_cpa,
        "target_roas": target_roas, "target_leads": target_leads,
        "kpi": kpi, "allocation": alloc.get("rows"),
        "forecast": {k: v for k, v in fc.items() if k != "message"},
        "assumptions": fc.get("assumptions", [])})
    return {"ok": True, "id": rec["id"], "allocation": alloc, "forecast": fc,
            "message": f"plan saved. {alloc['message']} {fc.get('message', '')}"}


def simulate(r, *, budget, compare_to=None, kpi="CPA") -> dict:
    """What if the budget were different. Three columns, never one.

    Conservative, base and optimistic, and the word "estimate" appears in
    the output because somebody will screenshot this and show it to a
    client."""
    base = forecast(r, budget=budget, kpi=kpi)
    if not base.get("ok"):
        return base
    out = {"ok": True, "scenarios": [], "kpi": kpi,
           "caveat": "These are estimates from your own past performance, "
                     "not guarantees. Nothing here models seasonality, an "
                     "auction change, or the fact that a bigger budget "
                     "usually buys a worse audience."}
    for label, b in (("now", float(compare_to or budget)),
                     ("proposed", float(budget))):
        f = forecast(r, budget=b, kpi=kpi)
        if f.get("ok"):
            out["scenarios"].append({"label": label, "budget": b,
                                     "conversions": f.get("conversions"),
                                     "cpa": f.get("cpa"),
                                     "revenue": f.get("revenue"),
                                     "band": f.get("confidence_band")})
    if len(out["scenarios"]) == 2:
        a, b2 = out["scenarios"]
        ca, cb = _D(a.get("conversions")), _D(b2.get("conversions"))
        ac, bc = ca.get("base") or 0, cb.get("base") or 0
        # Whether the ranges overlap is a fact about the numbers, so it gets
        # CHECKED rather than asserted. Claiming an overlap that is not there
        # is exactly the kind of confident sentence this engine must not print.
        lo, hi = (ca, cb) if ac <= bc else (cb, ca)
        overlaps = (lo.get("high") or 0) >= (hi.get("low") or 0)
        out["overlaps"] = overlaps
        out["message"] = (
            f"{a['budget']:,.0f} to {b2['budget']:,.0f} moves the middle "
            f"estimate from {ac} to {bc} conversions. "
            + (f"The ranges overlap ({lo.get('low')} to {lo.get('high')} "
               f"against {hi.get('low')} to {hi.get('high')}), which is the "
               f"honest way of saying the difference may not survive contact "
               f"with the auction." if overlaps else
               f"The ranges do not overlap ({lo.get('low')} to "
               f"{lo.get('high')} against {hi.get('low')} to "
               f"{hi.get('high')}), so the difference is real IF the "
               f"assumptions hold. They are assumptions."))
    return out


# ---------------------------------------------------------------------------
# THE LAUNCH GATE
# ---------------------------------------------------------------------------
def pre_flight(r, campaign_id) -> dict:
    """Everything checked at once, before it costs anything.

    Composes media_os.validate with the things only a plan knows. Returns
    VALID, WARNING or ERROR, and launch() refuses on ERROR."""
    c = r.one("media_campaigns", campaign_id)
    if not c:
        return {"ok": False, "level": "ERROR", "checks": [],
                "message": "no such campaign in this workspace"}
    checks = []

    def add(name, state, detail):
        checks.append({"name": name, "state": state, "detail": detail})

    p = c.get("provider")
    if not p:
        add("Platform", "ERROR", "no platform chosen")
    else:
        live, why = M.Adapter(p).available()
        add("Account connected", "OK" if live else "ERROR", why)
        cap = M.supports(p, c.get("objective"))
        add("Objective supported", "OK" if cap["ok"] else "ERROR", cap["why"])

    add("Budget", "OK" if float(c.get("budget_amount") or 0) > 0 else "ERROR",
        f"{c.get('budget_amount')} {c.get('currency')} "
        f"{str(c.get('budget_type') or '').lower()}"
        if c.get("budget_amount") else "no budget set")

    add("Schedule", "OK" if c.get("start_at") else "WARNING",
        c.get("start_at") or "no start date, so it begins immediately")

    groups = r.find("ad_groups", campaign_id=campaign_id)
    add("Ad groups", "OK" if groups else "ERROR",
        f"{len(groups)} group(s)" if groups
        else "nothing to put the budget behind")

    ads = r.find("ads", campaign_id=campaign_id)
    add("Ads", "OK" if ads else "ERROR",
        f"{len(ads)} ad(s)" if ads else "no ad, so there is nothing to show")

    # The audience, and what this platform will quietly drop from it.
    aud_ids = {g.get("audience_id") for g in groups if g.get("audience_id")}
    if not aud_ids:
        add("Audience", "WARNING", "no audience attached, so the platform "
                                   "will choose one for you")
    for aid in aud_ids:
        a = r.one("audiences", aid) or {}
        mapped = MC.map_to_provider(a.get("definition"), p) if p else {}
        add(f"Audience: {a.get('name', aid)}",
            "WARNING" if mapped.get("dropped") else "OK",
            mapped.get("message", ""))

    # A creative, and whether it can be learned from.
    cre_ids = {a.get("creative_id") for a in ads if a.get("creative_id")}
    if not cre_ids:
        add("Creative", "ERROR", "no creative attached to any ad")
    for cid in cre_ids:
        cr = r.one("creatives", cid) or {}
        thin = [x for x in MC.ATTRIBUTES if not str(cr.get(x) or "").strip()]
        add(f"Creative: {cr.get('name', cid)}",
            "WARNING" if thin else "OK",
            (f"missing {', '.join(thin)}, so this can be measured but not "
             f"learned from" if thin else "fully attributed"))
        # THE COMPATIBILITY ENGINE, spec section 12: is this asset a shape
        # the platform accepts, judged from real dimensions, never waved
        # through on an unknown.
        if p:
            import content_engine_media_manifest as MAN
            comp = MAN.compatibility(cr, p)
            add(f"Compatibility: {cr.get('name', cid)}",
                "OK" if comp["verdict"] == "SUPPORTED" else "WARNING",
                f"{comp['verdict']}: {comp['why'][:110]}")

    # all([]) is True, which would have printed "every ad has one" over a
    # campaign with no ads at all. An empty set is not a pass.
    missing_lp = [a for a in ads if not a.get("landing_page_url")]
    add("Landing page", "OK" if ads and not missing_lp else "WARNING",
        f"all {len(ads)} ad(s) have one" if ads and not missing_lp
        else (f"{len(missing_lp)} of {len(ads)} ad(s) have no landing page"
              if ads else "no ads yet, so nothing to check"))

    add("Tracking", "OK" if _tracking_live() else "WARNING", _tracking_why())

    errors = [x for x in checks if x["state"] == "ERROR"]
    warnings = [x for x in checks if x["state"] == "WARNING"]
    level = "ERROR" if errors else ("WARNING" if warnings else "VALID")
    return {"ok": not errors, "level": level, "checks": checks,
            "errors": [x["name"] for x in errors],
            "warnings": [x["name"] for x in warnings],
            "message": ("everything checks out"
                        if level == "VALID" else
                        f"{len(warnings)} thing(s) worth a look before you "
                        f"spend" if not errors else
                        f"cannot launch: " + ", ".join(x["name"] for x in errors))}


def _tracking_live() -> bool:
    try:
        import content_engine_connectors as C
        return bool(C._env("GA4_PROPERTY_ID") or C._env("GTM_CONTAINER_ID"))
    except Exception:
        return False


def _tracking_why() -> str:
    return ("conversion tracking is configured"
            if _tracking_live() else
            "no GA4 property or tag container is set, so conversions will be "
            "whatever the platform claims and nothing will check it")


def launch(r, campaign_id, *, scheduled_at="") -> dict:
    """Move a campaign towards the platform. PROPOSES, never spends.

    The actual submission is an order in the EXISTING execution engine,
    which already holds the approval tiers. This function refuses on a
    blocking error and otherwise queues the work for the founder's
    approval, exactly like every other spend in this engine."""
    pf = pre_flight(r, campaign_id)
    if not pf["ok"]:
        return {"ok": False, "level": pf["level"], "checks": pf["checks"],
                "message": pf["message"]}
    c = r.one("media_campaigns", campaign_id)
    state = "SCHEDULED" if scheduled_at else "LAUNCHING"
    if c.get("state") not in ("READY", "SCHEDULED"):
        got = M.validate(r, campaign_id)
        if not got["ok"]:
            return got
    if scheduled_at:
        c["scheduled_at"] = scheduled_at
        r.put("media_campaigns", c)
    moved = M.move(r, campaign_id, state)
    if not moved["ok"]:
        return moved
    order = _queue_order(r, c, scheduled_at)
    return {"ok": True, "state": state, "order": order,
            "warnings": pf["warnings"],
            "message": (f"{c.get('name')!r} is {state.lower()}. "
                        + order.get("message", "")
                        + (f" {len(pf['warnings'])} warning(s) noted: "
                           + ", ".join(pf["warnings"]) if pf["warnings"]
                           else ""))}


def _queue_order(r, c, scheduled_at="") -> dict:
    """One order, in the engine that already exists. No second queue."""
    try:
        import content_engine_api as A
        import content_engine_media_orders as MO
        store = A.get_store()
        order = MO.make_order(
            "launch_campaign", c.get("id"),
            platform=c.get("provider"),
            # The order engine refuses a verdict without metric, threshold,
            # window and source, and it is right to: a spend nobody can
            # justify in one line should not reach the approval board.
            evidence={"metric": "planned budget",
                      "threshold": f"{c.get('budget_amount')} "
                                   f"{c.get('currency')} "
                                   f"{str(c.get('budget_type') or '').lower()}",
                      "window": scheduled_at or c.get("start_at") or "immediate",
                      "source": "pre-flight passed with no blocking error",
                      "objective": c.get("objective"),
                      "provider_objective": c.get("provider_objective")},
            say=(f"Create {c.get('name')!r} on {c.get('provider')} at "
                 f"{c.get('budget_amount')} {c.get('currency')} "
                 f"{str(c.get('budget_type') or '').lower()}"))
        MO.upsert(store, [order])
        level = MO.auto_level(store)
        return {"ok": True, "order_id": order.get("id"), "tier": level,
                "message": (f"queued as a media order. The approval tier is "
                            f"{level!r}, so it "
                            + ("goes out on the next pass"
                               if level == "execute" else
                               "waits for you on the Media board") + ".")}
    except Exception as ex:
        log.warning("could not queue the launch order: %s", ex)
        return {"ok": False,
                "message": f"the campaign is ready but the order could not be "
                           f"queued: {type(ex).__name__}. Nothing was sent."}


# ---------------------------------------------------------------------------
# THE WIZARD'S STATE
# ---------------------------------------------------------------------------
def wizard_state(r, campaign_id="") -> dict:
    """Which of the eight steps are done, and what each one still needs.

    Driven from the record rather than from what the browser remembers, so
    closing the tab does not lose a campaign half-built."""
    c = r.one("media_campaigns", campaign_id) if campaign_id else None
    groups = r.find("ad_groups", campaign_id=campaign_id) if c else []
    ads = r.find("ads", campaign_id=campaign_id) if c else []
    done = {
        "objective": bool(c and c.get("objective")),
        "platforms": bool(c and c.get("provider")),
        "budget": bool(c and float(_D(c).get("budget_amount") or 0) > 0),
        "audience": any(g.get("audience_id") for g in groups),
        "creative": any(a.get("creative_id") for a in ads),
        "tracking": _tracking_live(),
        "review": bool(c and c.get("state") in ("READY", "SCHEDULED",
                                                "LAUNCHING", "ACTIVE")),
        "launch": bool(c and c.get("state") in ("SCHEDULED", "LAUNCHING",
                                                "ACTIVE")),
    }
    steps = [{"key": k, "label": lab, "why": why, "done": done.get(k, False)}
             for k, lab, why in WIZARD_STEPS]
    nxt = next((s for s in steps if not s["done"]), None)
    return {"campaign_id": campaign_id, "steps": steps,
            "complete": sum(1 for s in steps if s["done"]),
            "total": len(steps), "next": nxt,
            "message": (f"{sum(1 for s in steps if s['done'])} of "
                        f"{len(steps)} steps done"
                        + (f". Next: {nxt['label']} - {nxt['why']}"
                           if nxt else ". Ready to launch."))}
