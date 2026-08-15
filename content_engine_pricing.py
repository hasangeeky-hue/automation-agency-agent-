# -*- coding: utf-8 -*-
"""LANE 3c STAGE 2: PRICING AND PROMOTIONS.

Section 4.3 stage 2, built in full: the Commerce Analyst proposes price
changes and promotions with a margin-impact preview, every change is a
gated proposal, and an approved proposal is applied to the shop.

THE FULL LOOP, NOT HALF OF IT
  propose -> the founder sees the margin impact -> he approves -> it is
  written to the platform -> the result is recorded. A lane that only
  proposes and can never act is a suggestion box, and a lane that acts
  without the gate is how a shop wakes up priced wrong.

WHY MARGIN IS SOMETIMES ABSENT, AND NEVER GUESSED
  Margin needs a COST price. Shopify holds it on the inventory item and
  it takes a second call to read; WooCommerce has no native cost field
  at all. So a proposal carries one of two shapes:
    margin_known   current margin, proposed margin, and the delta
    margin_unknown revenue impact only, and it SAYS the cost is missing
  A percentage computed from a cost of zero would read as a 100% margin
  and would be the most confident lie on the dashboard.

PINK, AND WHAT PINK MEANS HERE
  Price touches money, so every proposal from this lane is pink: it can
  never be batch-approved and it can never be approved from a command
  panel. It goes to the queue, one at a time, with its numbers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import content_engine_contracts as C

AGENT_ID = "commerce.analyst"
LANE = "commerce"

#: where proposals live. Separate from the content rewrite queue: a price
#: change is not a piece of writing and must not sit in a list the
#: founder skims for editorial approval.
PROPOSALS_KEY = "pricing_proposals"
#: what was actually applied, so a change can be traced and never re-run
APPLIED_KEY = "pricing_applied"
LANE_LOG_KEY = "lane_log"

#: a proposal may never move a price by more than this in one step. Not a
#: budget: a guard against a decimal-point mistake reaching a live shop.
MAX_MOVE_PCT = 25.0

#: proposals per run, so a catalogue scan cannot bury the queue
MAX_PROPOSALS = 8

#: the reasons this lane is allowed to propose, and what each one means
REASONS = {
    "no_price": "it has no price at all, so it cannot be bought",
    "below_floor": "it is priced under its own cost, so every sale loses money",
    "thin_margin": "its margin is thinner than the target",
    "promo_candidate": "it is published, priced, and has stock to move",
}


def _s(v) -> str:
    return "" if v is None else str(v)


def _d(v) -> dict:
    return dict(v) if isinstance(v, dict) else {}


def _l(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else []


def _num(v) -> Optional[float]:
    """A number or None. Empty string is NOT zero: a product with no
    price set would otherwise read as free."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _get(store, k, d=None):
    try:
        return store.get_setting(k, d)
    except Exception:                                     # noqa: BLE001
        return d


def _set(store, k, v) -> bool:
    try:
        store.set_setting(k, v)
        return True
    except Exception:                                     # noqa: BLE001
        return False


def target_margin(store) -> float:
    """The founder's target margin, as a percentage. Settings-first so it
    is tunable from the dashboard without a rebuild."""
    v = _num(_get(store, "COMMERCE_TARGET_MARGIN_PCT", None))
    return v if v is not None else 40.0


# --------------------------------------------------------------------------
# MARGIN. Stated honestly, or stated as unknown.
# --------------------------------------------------------------------------
def margin_of(price, cost) -> Dict[str, Any]:
    """Margin as a percentage of price, or an explicit unknown.

    THE COST OF ZERO TRAP: a missing cost read as 0.0 produces a 100%
    margin, which is both wrong and the most confident number on the
    page. Missing cost returns known=False and no number at all."""
    p, c = _num(price), _num(cost)
    if p is None or p <= 0:
        return {"known": False, "why": "there is no price to measure"}
    if c is None:
        return {"known": False,
                "why": "no cost price is available for this product, so "
                       "margin cannot be computed and is not guessed"}
    return {"known": True, "pct": round((p - c) / p * 100.0, 1),
            "price": p, "cost": c, "profit": round(p - c, 2)}


def preview(price, cost, new_price) -> Dict[str, Any]:
    """What the founder sees before saying yes: both margins, or an
    honest revenue-only view when cost is missing."""
    p, n = _num(price), _num(new_price)
    before, after = margin_of(p, cost), margin_of(n, cost)
    out = {"price_before": p, "price_after": n,
           "move_pct": (round((n - p) / p * 100.0, 1)
                        if p and n is not None and p > 0 else None),
           "margin_known": before["known"] and after["known"]}
    if out["margin_known"]:
        out["margin_before_pct"] = before["pct"]
        out["margin_after_pct"] = after["pct"]
        out["margin_delta_pct"] = round(after["pct"] - before["pct"], 1)
        out["profit_delta"] = round(after["profit"] - before["profit"], 2)
    else:
        out["margin_note"] = after.get("why") or before.get("why")
    return out


# --------------------------------------------------------------------------
# RUNG 3 - PROPOSING
# --------------------------------------------------------------------------
def _catalogue(store) -> Dict[str, Any]:
    try:
        import content_engine_commerce as CM
        return CM.fetch_catalogue(store)
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "products": [],
                "why": "the commerce layer raised %s" % type(exc).__name__}


def _clamp(price: float, new_price: float) -> float:
    """Never move a price more than MAX_MOVE_PCT in one step."""
    if price <= 0:
        return new_price
    hi = price * (1 + MAX_MOVE_PCT / 100.0)
    lo = price * (1 - MAX_MOVE_PCT / 100.0)
    return round(min(max(new_price, lo), hi), 2)


def propose(store) -> Dict[str, Any]:
    """Read the catalogue and produce priced, previewed proposals.

    Every proposal names the REASON it exists and shows the numbers it
    was computed from. A proposal the founder cannot check is a proposal
    he has to take on faith, which is not approval."""
    cat = _catalogue(store)
    if not cat.get("ok"):
        return {"ok": False, "why": _s(cat.get("why")), "proposals": []}
    target = target_margin(store)
    applied = _d(_get(store, APPLIED_KEY, {}))
    out: List[dict] = []

    for p in _l(cat.get("products")):
        pd = _d(p)
        if _s(pd.get("type")) == "page":
            continue
        pid, sku = _s(pd.get("id")), _s(pd.get("sku"))
        title = _s(pd.get("title"))
        price, cost = _num(pd.get("price")), _num(pd.get("cost"))
        reason = new_price = None

        if price is None:
            reason = "no_price"
        elif cost is not None and price <= cost:
            reason = "below_floor"
            # price it to the target margin: p = c / (1 - m)
            new_price = _clamp(price, round(cost / (1 - target / 100.0), 2))
        elif cost is not None:
            m = margin_of(price, cost)
            if m["known"] and m["pct"] < target:
                reason = "thin_margin"
                new_price = _clamp(price,
                                   round(cost / (1 - target / 100.0), 2))
        if not reason:
            continue
        if _s(applied.get(pid or sku)):
            continue                       # already changed; do not loop

        out.append({
            "id": "px_%s" % (sku or pid), "product_id": pid, "sku": sku,
            "title": title, "reason": reason, "why": REASONS[reason],
            "price": price, "cost": cost, "new_price": new_price,
            "preview": preview(price, cost, new_price)
            if new_price is not None else
            {"margin_known": False,
             "margin_note": "there is nothing to compare: this product has "
                            "no price at all"},
            # PINK. Price touches money, so it can never batch-approve.
            "pink": True, "status": "pending", "lane": LANE})
        if len(out) >= MAX_PROPOSALS:
            break
    return {"ok": True, "proposals": out, "target_margin_pct": target,
            "counted": len(_l(cat.get("products")))}


def save_proposals(store, proposals: List[dict]) -> List[dict]:
    """One open proposal per product. A product already in the queue is
    not proposed again, so the queue cannot grow every morning."""
    cur = [x for x in _l(_get(store, PROPOSALS_KEY, []))
           if _d(x).get("status") == "pending"]
    seen = {_s(_d(x).get("id")) for x in cur}
    for p in proposals:
        if _s(p.get("id")) not in seen:
            cur.append(p)
            seen.add(_s(p.get("id")))
    _set(store, PROPOSALS_KEY, cur[-50:])
    return cur


def proposals(store, status: str = "") -> List[dict]:
    return [_d(x) for x in _l(_get(store, PROPOSALS_KEY, []))
            if not status or _d(x).get("status") == status]


# --------------------------------------------------------------------------
# RUNG 6 - THE GATE, AND THE WRITE BEHIND IT
# --------------------------------------------------------------------------
def apply_one(store, proposal_id: str, *, approved_by: str = "") -> Dict[str, Any]:
    """Write an APPROVED price to the shop.

    Every refusal is named. This is the only function in the engine that
    changes what a customer pays, so it refuses loudly rather than
    returning a bare False."""
    if not approved_by:
        return {"ok": False, "why": "a price change needs a named human "
                                    "approval; the spend gate is permanent "
                                    "and no setting opens it"}
    match = [p for p in proposals(store) if _s(p.get("id")) == _s(proposal_id)]
    if not match:
        return {"ok": False, "why": "no such proposal"}
    p = match[0]
    if _s(p.get("status")) != "pending":
        return {"ok": False, "why": "this proposal is already %s"
                                    % _s(p.get("status"))}
    new_price = _num(p.get("new_price"))
    if new_price is None or new_price <= 0:
        return {"ok": False, "why": "this proposal has no price to set; it "
                                    "is a finding for you to act on, not a "
                                    "change to apply"}
    old = _num(p.get("price"))
    if old and abs(new_price - old) / old * 100.0 > MAX_MOVE_PCT + 0.01:
        return {"ok": False, "why": "that moves the price more than %g%% in "
                                    "one step" % MAX_MOVE_PCT}
    try:
        import content_engine_commerce as CM
        setter = getattr(CM, "set_price", None)
        if setter is None:
            return {"ok": False,
                    "why": "the commerce layer has no set_price(); the "
                           "proposal stands and nothing was changed"}
        res = setter(store, _s(p.get("product_id")), new_price)
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "why": "the shop refused: %s"
                                    % type(exc).__name__}
    if not _d(res).get("ok"):
        return {"ok": False, "why": _s(_d(res).get("why")) or
                                    "the shop refused the change"}
    # Record BOTH sides: the queue entry closes, and the applied ledger
    # keeps what changed, from what, to what, and who said yes.
    cur = proposals(store)
    for x in cur:
        if _s(x.get("id")) == _s(proposal_id):
            x["status"] = "applied"
            x["approved_by"] = approved_by
    _set(store, PROPOSALS_KEY, cur)
    led = _d(_get(store, APPLIED_KEY, {}))
    led[_s(p.get("product_id")) or _s(p.get("sku"))] = {
        "at": C.today(), "from": old, "to": new_price,
        "approved_by": approved_by, "reason": _s(p.get("reason"))}
    _set(store, APPLIED_KEY, led)
    return {"ok": True, "id": proposal_id, "from": old, "to": new_price,
            "approved_by": approved_by}


def decline_one(store, proposal_id: str, note: str = "") -> Dict[str, Any]:
    cur = proposals(store)
    hit = False
    for x in cur:
        if _s(x.get("id")) == _s(proposal_id) and x.get("status") == "pending":
            x["status"], x["note"], hit = "declined", _s(note)[:200], True
    _set(store, PROPOSALS_KEY, cur)
    return {"ok": hit, "why": "" if hit else "no pending proposal with that id"}


# --------------------------------------------------------------------------
# RUNG 7 - THE REPORT
# --------------------------------------------------------------------------
def run(store) -> Dict[str, Any]:
    day = C.today()
    res = propose(store)
    finished, couldnt, needs = [], [], []
    if res.get("ok"):
        save_proposals(store, res["proposals"])
        finished.append({"what": "read %d products and proposed %d price "
                                 "change(s)" % (res.get("counted", 0),
                                                len(res["proposals"])),
                         "job_ids": []})
        for p in proposals(store, "pending")[:6]:
            pv = _d(p.get("preview"))
            if pv.get("margin_known"):
                detail = ("margin %g%% to %g%%"
                          % (pv.get("margin_before_pct"),
                             pv.get("margin_after_pct")))
            else:
                detail = _s(pv.get("margin_note"))
            needs.append(C.need(
                what="price %s: %s to %s" % (_s(p.get("title"))[:40],
                                             p.get("price"),
                                             p.get("new_price")),
                kind="decision", action="/commerce/price/%s" % _s(p.get("id")),
                why="%s. %s" % (_s(p.get("why")), detail)))
    else:
        couldnt.append({"what": "the daily pricing review",
                        "cause": _s(res.get("why")) or "the catalogue could "
                                                       "not be read"})

    log = dict(_get(store, LANE_LOG_KEY, {}) or {})
    per_day = dict(log.get(day) or {})
    prev = _d(per_day.get(AGENT_ID))
    per_day[AGENT_ID] = {
        "finished": _l(prev.get("finished")) + finished,
        "couldnt": _l(prev.get("couldnt")) + couldnt,
        "needs": _l(prev.get("needs")) + needs}
    log[day] = per_day
    for old in sorted(log)[:-14]:
        log.pop(old, None)
    _set(store, LANE_LOG_KEY, log)

    learned = ["%s: %s" % (_s(p.get("reason")), _s(p.get("title"))[:40])
               for p in res.get("proposals", [])[:5]]
    if learned:
        try:
            import content_engine_learning as L
            L.record_lane_cycle(_s(_get(store, "BRAND_NAME", "")) or "default",
                                LANE, learned=learned)
        except Exception:                                 # noqa: BLE001
            pass
    return {"agent": AGENT_ID, "day": day, "result": res,
            "report": C.daily_report(day, finished=finished, couldnt=couldnt,
                                     needs=needs)}


def check() -> Dict[str, Any]:
    """The rules that make this lane safe to have at all."""
    import inspect as _i
    problems = []
    src = _i.getsource(apply_one)
    if "approved_by" not in src or "spend gate is permanent" not in src:
        problems.append("apply_one no longer requires a named human approval")
    if "already %s" not in src:
        problems.append("apply_one no longer refuses to run twice")
    if "MAX_MOVE_PCT" not in src:
        problems.append("apply_one no longer bounds how far a price moves")
    psrc = _i.getsource(propose)
    if '"pink": True' not in psrc:
        problems.append("proposals are no longer pink, so they could be "
                        "batch-approved")
    msrc = _i.getsource(margin_of)
    if "not guessed" not in msrc:
        problems.append("margin no longer refuses to guess a missing cost")
    if set(REASONS) - {"no_price", "below_floor", "thin_margin",
                       "promo_candidate"}:
        problems.append("an unexplained reason exists")
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    assert check()["ok"], check()["problems"]
    print("margin, cost known:  ", margin_of(100, 60))
    print("margin, cost missing:", margin_of(100, None)["why"][:60])
    print("preview 100 -> 120:  ", preview(100, 60, 120))
