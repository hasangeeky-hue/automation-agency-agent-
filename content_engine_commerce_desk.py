# -*- coding: utf-8 -*-
"""LANE 3c, STAGE 1: THE COMMERCE ANALYST as an inspector.

Section 4.3 is explicit about the two stages, and this is stage 1:
detection with contracts, badge stays INSPECTOR. Stage 2 is the pricing
and promotions lane, where every change is a gated proposal with a margin
preview, and only that stage earns a live badge.

WHY IT COSTS NOTHING
  Like the Integrations Engineer, this desk is pure code reading a
  catalogue the CMS layer already fetches. No model call, no paid API.
  A roster entry is free; only paid steps cost money.

WHAT IT WILL NOT DO
  It will not report a stock level for a product whose platform does not
  give one. Woo returns null for stock_quantity when the shop is not
  tracking stock for that item, and "not tracked" is not "none left".
  Every finding here names the field it read.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import content_engine_contracts as C

AGENT_ID = "commerce.analyst"
LANE = "commerce"

#: at or below this, a tracked product is called low
LOW_STOCK = 5

#: where its day is written, so the daily report can read it back
LANE_LOG_KEY = "lane_log"


def _s(v) -> str:
    return "" if v is None else str(v)


def _num(v):
    """A number, or None. Empty string is NOT zero: Woo sends '' for a
    product with no price set, and reading that as 0.00 would invent a
    free product."""
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


# --------------------------------------------------------------------------
# RUNG 1 - CONTEXT
# --------------------------------------------------------------------------
def context(store) -> Dict[str, Any]:
    """The catalogue, and whether reading it even worked."""
    try:
        import content_engine_commerce as CM
        cat = CM.fetch_catalogue(store)
    except Exception as exc:                              # noqa: BLE001
        cat = {"ok": False, "products": [], "count": None,
               "why": "the commerce layer raised %s" % type(exc).__name__}
    return {"ok": bool(cat.get("ok")),
            "platform": _s(cat.get("platform")),
            "products": list(cat.get("products") or []),
            "why": _s(cat.get("why")),
            "read_at": datetime.now(timezone.utc).isoformat()}


# --------------------------------------------------------------------------
# RUNG 3 - THE LANE: four checks, each naming the field it read
# --------------------------------------------------------------------------
def _low_stock(products) -> List[dict]:
    out = []
    for p in products:
        n = _num(p.get("stock"))
        if n is None:
            continue                       # not tracked, which is not zero
        if n <= LOW_STOCK:
            out.append({"kind": "low_stock", "sku": _s(p.get("sku")),
                        "what": "%s is down to %g" % (_s(p.get("title")), n),
                        "field": "stock",
                        "fix": "reorder, or mark it out of stock so the "
                               "shop stops selling what you cannot ship"})
    return out


def _no_price(products) -> List[dict]:
    out = []
    for p in products:
        if _s(p.get("type")) == "page":
            continue
        if _num(p.get("price")) is None:
            out.append({"kind": "no_price", "sku": _s(p.get("sku")),
                        "what": "%s has no price set" % _s(p.get("title")),
                        "field": "price",
                        "fix": "set a price, or unpublish it"})
    return out


def _dead_sku(products) -> List[dict]:
    live = {"active", "publish", "published"}
    out = []
    for p in products:
        st = _s(p.get("status")).lower()
        if st and st not in live:
            out.append({"kind": "dead_sku", "sku": _s(p.get("sku")),
                        "what": "%s is %s, so nobody can buy it"
                                % (_s(p.get("title")), st),
                        "field": "status",
                        "fix": "publish it or remove it from the catalogue"})
    return out


def _duplicates(products) -> List[dict]:
    seen: Dict[str, int] = {}
    for p in products:
        t = _s(p.get("title")).strip().lower()
        if t:
            seen[t] = seen.get(t, 0) + 1
    return [{"kind": "duplicate", "sku": "",
             "what": "%d products share the title %r" % (n, t),
             "field": "title",
             "fix": "they compete with each other in search; merge or "
                    "differentiate them"}
            for t, n in sorted(seen.items()) if n > 1]


def inspect(store) -> Dict[str, Any]:
    """The whole free battery. Returns findings; writes nothing."""
    ctx = context(store)
    if not ctx["ok"]:
        return {"ok": False, "why": ctx["why"], "findings": [],
                "counted": None, "platform": ctx["platform"]}
    ps = ctx["products"]
    findings = (_dead_sku(ps) + _low_stock(ps) + _no_price(ps)
                + _duplicates(ps))
    tracked = sum(1 for p in ps if _num(p.get("stock")) is not None)
    priced = sum(1 for p in ps if _num(p.get("price")) is not None)
    return {"ok": True, "platform": ctx["platform"], "counted": len(ps),
            "tracked_stock": tracked, "priced": priced,
            "findings": findings, "why": ""}


# --------------------------------------------------------------------------
# RUNG 7 - THE REPORT
# --------------------------------------------------------------------------
def run(store) -> Dict[str, Any]:
    """One working day for the Commerce Analyst."""
    day = C.today()
    res = inspect(store)
    finished, couldnt, needs = [], [], []

    if res["ok"]:
        finished.append({"what": "read %d products from %s and found %d "
                                 "issue(s)" % (res["counted"], res["platform"],
                                               len(res["findings"])),
                         "job_ids": []})
        # STAGE 1 REPORTS. It does not propose a price change: that is
        # stage 2, and a price touches money, so it will arrive as a
        # gated proposal with a margin preview or not at all.
        for f in res["findings"][:6]:
            needs.append(C.need(
                what=f["what"], kind="decision",
                action="/commerce#" + (f["sku"] or f["kind"]),
                why=f["fix"]))
    else:
        couldnt.append({"what": "the daily catalogue read",
                        "cause": res["why"] or "the catalogue could not be "
                                               "read, and no reason was "
                                               "recorded, which is itself a "
                                               "bug"})

    log = dict(_get(store, LANE_LOG_KEY, {}) or {})
    per_day = dict(log.get(day) or {})
    per_day[AGENT_ID] = {"finished": finished, "couldnt": couldnt,
                         "needs": needs}
    log[day] = per_day
    for old in sorted(log)[:-14]:
        log.pop(old, None)
    _set(store, LANE_LOG_KEY, log)

    # RUNG 2 - MEMORY. Only real observations, and never an empty cycle.
    learned = ["%s: %s" % (f["kind"], f["what"]) for f in res["findings"][:5]]
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
    """Stage 1 must not pretend to be stage 2."""
    problems = []
    # Ask the MODULE what it defines, not its own text. The first version
    # grepped its own source and found these very names in this very
    # tuple, so it failed the moment it was written.
    for forbidden in ("set_price", "apply_discount", "publish",
                      "create_promotion"):
        if callable(globals().get(forbidden)):
            problems.append("stage 1 must not write: %s() exists" % forbidden)
    # THE BADGE RULE, NOW THAT STAGE 2 EXISTS.
    # This module is still stage 1 and still may not write. What changed
    # is that a LIVE badge is no longer automatically wrong: it is earned
    # by content_engine_pricing, which proposes and applies behind the
    # spend gate. So a live badge is only legitimate while that lane is
    # present AND still holding its gate. If stage 2 were ever deleted or
    # its gate removed, this desk would go back to being an inspector and
    # the badge would be a lie, so the two are checked against each other
    # rather than each trusting the other.
    try:
        import content_engine_roster as R
        badge = R.agent(AGENT_ID).get("badge")
        if badge == "live":
            import inspect

            import content_engine_pricing as PX
            src = inspect.getsource(PX.apply_one)
            if "spend gate is permanent" not in src or \
                    "approved_by" not in src:
                problems.append("the badge says live, but stage 2 no longer "
                                "requires a named human approval")
            if not PX.check()["ok"]:
                problems.append("the badge says live, but stage 2 fails its "
                                "own check: " + str(PX.check()["problems"]))
    except ImportError:
        problems.append("the badge says live with no stage 2 lane present; "
                        "stage 1 alone is an inspector (4.3)")
    except Exception as exc:                              # noqa: BLE001
        problems.append("roster unreadable: %s" % type(exc).__name__)
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, d=None):
            return self.d.get(k, d)

        def set_setting(self, k, v):
            self.d[k] = v

    r = check()
    assert r["ok"], r["problems"]
    out = run(_S())
    print("ok:", out["result"]["ok"], "| why:", out["result"]["why"][:60])
    print("report:", out["report"])
