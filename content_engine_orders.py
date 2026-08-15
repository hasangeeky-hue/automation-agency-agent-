# -*- coding: utf-8 -*-
"""ORDERS: the data the engine has never had.

Stage 2 of the data contract. Until this module existed there was no
order data anywhere in the engine, which is why top sellers, slow movers,
lifecycle, revenue by channel and ROAS were all empty. They were not
broken screens. They were screens with nothing to draw.

Two things are stored, because they answer different questions:

    orders  the canonical order, WITH ITS LINE ITEMS, because "which
            product sold" is a question about a line, not an order
    deals   the projection content_engine_bi.py already consumes, so
            revenue() and customers() light up with no change to them

READ ONLY. Nothing here writes to a shop. Order data is a read of what
already happened, and the moment a collector can also write is the moment
a bug can charge a customer.

Three refusals worth stating up front, because each one has an
attractive wrong answer:

  A shop with no orders is NOT a failed call. Zero is a fact; a refused
  read is a different fact. They get different words.

  An order with no total is NOT a zero-value order. It stays None and
  the screens say "not measured". Summing it as zero quietly lowers
  every average that touches it.

  A test order is NOT revenue. It is excluded, COUNTED, and named, so a
  founder who wonders where his test purchase went can see it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import content_engine_bi as BI
import content_engine_commerce as CM

log = logging.getLogger("orders")

ORDERS_KEY = "orders_rows"
COLLECT_KEY = "orders_last_collect"
MAX_ORDERS = 2000

#: Shopify and Woo describe where an order came from in their own words.
#: BI accepts exactly six. Mapping between the two is the whole job of
#: this table, and getting it wrong is silent: list_deals() coerces any
#: unknown source to "other", so a typo here would not raise, it would
#: just make revenue-by-channel permanently and quietly wrong.
#: check() asserts every value below is one BI actually knows.
SOURCE_MAP = {
    "web": "direct",
    "shopify_draft_order": "outreach",
    "draft_order": "outreach",
    "pos": "direct",
    "iphone": "direct",
    "android": "direct",
    "checkout_next": "direct",
    "": "other",
}

#: Financial states that mean money actually moved. Anything else is
#: named rather than dropped: a pending order is not revenue, but it is
#: also not nothing, and a founder should be able to see the difference.
PAID_STATES = ("paid", "partially_paid", "authorized")


# ------------------------------------------------------------- coercion
def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _s(x) -> str:
    return "" if x is None else str(x)


def _money(x):
    """A missing amount stays missing.

    float(None) raises and float("") raises, so the tempting guard is
    `float(x or 0)`. That turns every absent total into a real zero and
    drags down every average built on top of it. None survives instead,
    and the components already know how to render "not measured"."""
    if x in (None, ""):
        return None
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def _get(store, key, default):
    try:
        return store.get_setting(key, default)
    except Exception:                                     # noqa: BLE001
        return default


def _set(store, key, value):
    try:
        store.set_setting(key, value)
        return True
    except Exception as e:                                # noqa: BLE001
        log.warning("orders: could not save %s: %s", key, e)
        return False


def map_source(raw: str) -> str:
    """One shop's word for a channel, in the vocabulary BI speaks."""
    key = _s(raw).strip().lower()
    if key in SOURCE_MAP:
        return SOURCE_MAP[key]
    # An unmapped channel is 'other', which is honest, but it is also a
    # signal that this table has fallen behind the shop. unmapped_sources()
    # surfaces them so they can be mapped deliberately instead of
    # disappearing into a bucket.
    return "other"


def unmapped_sources(orders=None) -> List[str]:
    """Channels the shop reported that this module does not know yet."""
    seen = set()
    for o in _l(orders):
        raw = _s(_d(o).get("source_raw")).strip().lower()
        if raw and raw not in SOURCE_MAP:
            seen.add(raw)
    return sorted(seen)


# ---------------------------------------------------------------- fetch
def fetch_orders(store, platform: str = "", limit: int = 250,
                 since: str = "") -> Dict[str, Any]:
    """Read orders from the connected shop. READ ONLY.

    Returns {ok, platform, orders, count, why}. `count` is None when the
    call failed and an integer when it succeeded, so a caller can always
    tell "no orders" from "no answer" without reading prose.
    """
    st = CM.status(store)
    plat = platform or next((p for p, v in st.items()
                             if v["connected"] and p in ("shopify", "woocommerce")), "")
    if not plat:
        return {"ok": False, "platform": "", "orders": [], "count": None,
                "why": "no shop platform holds all of its keys yet"}
    if not st.get(plat, {}).get("connected"):
        return {"ok": False, "platform": plat, "orders": [], "count": None,
                "why": (CM.PLATFORMS[plat]["label"] + " is missing "
                        + ", ".join(st[plat]["missing"]))}
    rq = CM._requests()
    if rq is None:
        return {"ok": False, "platform": plat, "orders": [], "count": None,
                "why": "the requests library is not installed in this image"}
    try:
        if plat == "shopify":
            dom = CM._env(store, "SHOPIFY_SHOP_DOMAIN").replace("https://", "")
            tok = CM._env(store, "SHOPIFY_ADMIN_TOKEN")
            params = {"limit": min(int(limit), 250), "status": "any"}
            if since:
                params["created_at_min"] = since
            r = rq.get("https://%s/admin/api/2024-10/orders.json" % dom,
                       headers={"X-Shopify-Access-Token": tok},
                       params=params, timeout=30)
            if r.status_code >= 400:
                # read_orders is a SEPARATE scope from read_products. A shop
                # whose catalogue reads fine will still refuse orders, and
                # without naming the scope this reads as a broken key.
                return {"ok": False, "platform": plat, "orders": [],
                        "count": None,
                        "why": ("Shopify refused the order read (%d). The "
                                "admin token needs read_orders, which is a "
                                "separate scope from read_products."
                                % r.status_code)}
            raw = _l(_d(r.json()).get("orders"))
        elif plat == "woocommerce":
            base = CM._env(store, "WOO_SITE_URL").rstrip("/")
            params = {"per_page": min(int(limit), 100)}
            if since:
                params["after"] = since
            r = rq.get(base + "/wp-json/wc/v3/orders",
                       auth=(CM._env(store, "WOO_CONSUMER_KEY"),
                             CM._env(store, "WOO_CONSUMER_SECRET")),
                       params=params, timeout=30)
            if r.status_code >= 400:
                return {"ok": False, "platform": plat, "orders": [],
                        "count": None,
                        "why": ("WooCommerce refused the order read (%d). "
                                "The REST key needs read access to orders."
                                % r.status_code)}
            raw = _l(r.json())
        else:
            return {"ok": False, "platform": plat, "orders": [], "count": None,
                    "why": "%s does not expose orders" % plat}
    except Exception as e:                                # noqa: BLE001
        log.warning("order fetch failed: %s", e)
        return {"ok": False, "platform": plat, "orders": [], "count": None,
                "why": "the shop could not be reached: %s" % str(e)[:120]}

    orders = [normalise(o, plat) for o in map(_d, raw)]
    return {"ok": True, "platform": plat, "orders": orders,
            "count": len(orders),
            "why": ("the shop answered and has no orders in this window"
                    if not orders else "")}


def normalise(raw: dict, platform: str) -> Dict[str, Any]:
    """One shop's order, in this engine's words."""
    raw = _d(raw)
    if platform == "shopify":
        cust = _d(raw.get("customer"))
        client = (" ".join(x for x in (_s(cust.get("first_name")),
                                       _s(cust.get("last_name"))) if x).strip()
                  or _s(raw.get("email")) or "unnamed")
        src_raw = _s(raw.get("source_name"))
        lines = [{"sku": _s(li.get("sku")),
                  "title": _s(li.get("title")),
                  "qty": int(li.get("quantity") or 0),
                  "price": _money(li.get("price")),
                  "product_id": _s(li.get("product_id"))}
                 for li in map(_d, _l(raw.get("line_items")))]
        return {"id": _s(raw.get("id")),
                "number": _s(raw.get("order_number")),
                "at": _s(raw.get("created_at"))[:10],
                "client": client[:80],
                "email": _s(raw.get("email")),
                "value": _money(raw.get("total_price")),
                "currency": _s(raw.get("currency")),
                "source_raw": src_raw,
                "source": map_source(src_raw),
                "financial_status": _s(raw.get("financial_status")),
                "fulfillment_status": _s(raw.get("fulfillment_status")),
                "cancelled": bool(raw.get("cancelled_at")),
                "test": bool(raw.get("test")),
                "line_items": lines}
    # WooCommerce
    bill = _d(raw.get("billing"))
    client = (" ".join(x for x in (_s(bill.get("first_name")),
                                   _s(bill.get("last_name"))) if x).strip()
              or _s(bill.get("email")) or "unnamed")
    src_raw = _s(_d(raw.get("meta_data")).get("source") or "web")
    lines = [{"sku": _s(li.get("sku")), "title": _s(li.get("name")),
              "qty": int(li.get("quantity") or 0),
              "price": _money(li.get("price")),
              "product_id": _s(li.get("product_id"))}
             for li in map(_d, _l(raw.get("line_items")))]
    status_ = _s(raw.get("status")).lower()
    return {"id": _s(raw.get("id")), "number": _s(raw.get("number")),
            "at": _s(raw.get("date_created"))[:10],
            "client": client[:80], "email": _s(bill.get("email")),
            "value": _money(raw.get("total")),
            "currency": _s(raw.get("currency")),
            "source_raw": src_raw, "source": map_source(src_raw),
            # Woo has no financial_status; 'completed'/'processing' are the
            # states where money moved. Mapped here so PAID_STATES stays
            # one vocabulary rather than two.
            "financial_status": ("paid" if status_ in ("completed", "processing")
                                 else status_),
            "fulfillment_status": status_,
            "cancelled": status_ in ("cancelled", "refunded"),
            "test": False, "line_items": lines}


# ---------------------------------------------------------------- store
def save(store, orders) -> Dict[str, Any]:
    """Merge by id so a re-collect updates rather than duplicates."""
    have = {_s(_d(o).get("id")): _d(o) for o in _l(_get(store, ORDERS_KEY, []))}
    added, updated = 0, 0
    for o in _l(orders):
        oid = _s(_d(o).get("id"))
        if not oid:
            continue
        if oid in have:
            updated += 1
        else:
            added += 1
        have[oid] = _d(o)
    rows = sorted(have.values(), key=lambda o: _s(o.get("at")), reverse=True)
    rows = rows[:MAX_ORDERS]
    _set(store, ORDERS_KEY, rows)
    return {"stored": len(rows), "added": added, "updated": updated}


def list_orders(store) -> List[dict]:
    return [_d(o) for o in _l(_get(store, ORDERS_KEY, []))]


def countable(orders) -> Dict[str, Any]:
    """Split what counts as revenue from what does not, and NAME the rest.

    Everything excluded is counted. A silent filter is how a founder ends
    up asking why the dashboard disagrees with Shopify."""
    live, test, cancelled, unpaid, unmeasured = [], 0, 0, 0, 0
    for o in map(_d, _l(orders)):
        if o.get("test"):
            test += 1
            continue
        if o.get("cancelled"):
            cancelled += 1
            continue
        if _s(o.get("financial_status")).lower() not in PAID_STATES:
            unpaid += 1
            continue
        if o.get("value") is None:
            # Counted separately from unpaid: this one DID sell, we just
            # do not know for how much. Dropping it into unpaid would
            # imply the customer never paid, which is a different claim.
            unmeasured += 1
            continue
        live.append(o)
    return {"orders": live, "counted": len(live), "excluded_test": test,
            "excluded_cancelled": cancelled, "excluded_unpaid": unpaid,
            "excluded_no_total": unmeasured}


# ----------------------------------------------------------- projections
def to_deals(orders) -> List[dict]:
    """Orders in the shape content_engine_bi.py already reads.

    A repeat customer is marked recurring, which is what makes
    bi.customers() able to report a repeat rate at all."""
    seen: Dict[str, int] = {}
    for o in map(_d, _l(orders)):
        key = _s(o.get("email") or o.get("client")).lower()
        seen[key] = seen.get(key, 0) + 1
    out = []
    for o in map(_d, _l(orders)):
        key = _s(o.get("email") or o.get("client")).lower()
        out.append({"id": "ord-" + _s(o.get("id")),
                    "client": _s(o.get("client")) or "unnamed",
                    "value": o.get("value"),
                    "at": _s(o.get("at")),
                    "source": _s(o.get("source")),
                    "recurring": seen.get(key, 0) > 1})
    return out


def top_sellers(orders, n: int = 10) -> List[dict]:
    """Which products actually sold. THE reason line items are stored.

    A deal carries one total and no products, so this question cannot be
    answered from the deals projection at any level of cleverness."""
    agg: Dict[str, dict] = {}
    for o in map(_d, _l(orders)):
        for li in map(_d, _l(o.get("line_items"))):
            key = _s(li.get("sku")) or _s(li.get("product_id")) or _s(li.get("title"))
            if not key:
                continue
            row = agg.setdefault(key, {"sku": _s(li.get("sku")),
                                       "title": _s(li.get("title")),
                                       "units": 0, "revenue": 0.0,
                                       "revenue_known": True})
            row["units"] += int(li.get("qty") or 0)
            price = li.get("price")
            if price is None:
                # One unpriced line makes this product's revenue an
                # estimate, and a total containing an estimate is an
                # estimate. Said out loud rather than rounded away.
                row["revenue_known"] = False
            else:
                row["revenue"] += price * int(li.get("qty") or 0)
    rows = sorted(agg.values(), key=lambda r: -r["units"])
    for r in rows:
        r["revenue"] = round(r["revenue"], 2) if r["revenue_known"] else None
    return rows[:n]


def revenue_by_channel(orders) -> List[tuple]:
    """Revenue per channel, in BI's own vocabulary."""
    by: Dict[str, float] = {}
    for o in map(_d, _l(orders)):
        if o.get("value") is None:
            continue
        src = _s(o.get("source")) or "other"
        by[src] = by.get(src, 0.0) + o["value"]
    return sorted(((k, round(v, 2)) for k, v in by.items()), key=lambda kv: -kv[1])


# ------------------------------------------------------------------ day
def run(store) -> Dict[str, Any]:
    """The collector's working day: read the shop, store, project."""
    from datetime import datetime, timezone
    got = fetch_orders(store)
    if not got.get("ok"):
        return {"ok": False, "why": got.get("why"), "counted": 0}

    saved = save(store, got["orders"])
    all_orders = list_orders(store)
    split = countable(all_orders)
    deals = to_deals(split["orders"])

    # The deals projection is written where BI already looks, so the
    # revenue and customer screens need no change to come alive. It is
    # replaced rather than appended: these deals ARE the orders, and
    # appending would double every figure on the next collect.
    _set(store, BI.DEALS_KEY, deals[:BI.MAX_DEALS])
    _set(store, COLLECT_KEY,
         datetime.now(timezone.utc).isoformat(timespec="seconds"))

    unmapped = unmapped_sources(all_orders)
    return {"ok": True, "platform": got.get("platform"),
            "fetched": got.get("count"), **saved, **split,
            "deals_written": len(deals[:BI.MAX_DEALS]),
            "top_sellers": top_sellers(split["orders"], 5),
            "by_channel": revenue_by_channel(split["orders"]),
            "unmapped_sources": unmapped,
            "note": ("every channel the shop reported is mapped"
                     if not unmapped else
                     "these channels are counted as 'other' until mapped: "
                     + ", ".join(unmapped))}


def context(store) -> Dict[str, Any]:
    """What the screens read. No calls, so it is free and safe to render."""
    orders = list_orders(store)
    split = countable(orders)
    return {"connected": bool(orders) or bool(_get(store, COLLECT_KEY, "")),
            "last_collect": _s(_get(store, COLLECT_KEY, "")),
            "orders": orders, "counted": split["counted"],
            "excluded_test": split["excluded_test"],
            "excluded_cancelled": split["excluded_cancelled"],
            "excluded_unpaid": split["excluded_unpaid"],
            "excluded_no_total": split["excluded_no_total"],
            "top_sellers": top_sellers(split["orders"]),
            "by_channel": revenue_by_channel(split["orders"]),
            "unmapped_sources": unmapped_sources(orders)}


# ---------------------------------------------------------------- check
def check() -> Dict[str, Any]:
    """Refuse to ship on the failure classes this repo keeps repeating."""
    out = []

    # THE SHARED VOCABULARY. Two hand-written lists that must agree is
    # the bug this codebase has shipped more than any other. BI coerces
    # an unknown source to "other" without raising, so a typo here would
    # never surface as an error, only as a permanently wrong channel
    # chart. Derived from BI.SOURCES, never retyped.
    bad = sorted({v for v in SOURCE_MAP.values() if v not in BI.SOURCES})
    out.append(("every mapped source is one BI actually knows",
                not bad, "BI does not know: " + ", ".join(bad) if bad else ""))

    out.append(("the deals projection writes where BI reads",
                hasattr(BI, "DEALS_KEY") and hasattr(BI, "MAX_DEALS"), ""))

    # A missing total must never become a zero.
    out.append(("a missing total stays missing",
                _money(None) is None and _money("") is None, ""))
    out.append(("and a real total still parses", _money("19.99") == 19.99, ""))

    # An unpriced line makes the product's revenue unknown, not smaller.
    t = top_sellers([{"line_items": [{"sku": "A", "qty": 2, "price": None}]}])
    out.append(("an unpriced line makes revenue UNKNOWN, never a low number",
                bool(t) and t[0]["revenue"] is None and t[0]["units"] == 2, ""))

    # Nothing excluded may vanish silently.
    c = countable([{"test": True}, {"cancelled": True},
                   {"financial_status": "pending"},
                   {"financial_status": "paid", "value": None},
                   {"financial_status": "paid", "value": 10.0}])
    out.append(("every excluded order is counted and named",
                c["counted"] == 1 and c["excluded_test"] == 1
                and c["excluded_cancelled"] == 1 and c["excluded_unpaid"] == 1
                and c["excluded_no_total"] == 1, str(c)[:120]))

    # A shop with no orders is not a broken shop.
    out.append(("an unmapped channel is surfaced, not swallowed",
                unmapped_sources([{"source_raw": "tiktok_shop"}]) == ["tiktok_shop"], ""))

    # THIS MODULE MUST NOT BE ABLE TO WRITE TO A SHOP. Orders are a read
    # of what already happened; a collector that can also write is one
    # bug away from charging a customer.
    #
    # Checked by parsing for CALLS, not by grepping for text. The first
    # version searched its own source for "set_price" and found the
    # search term itself, so it could never pass. A test that cannot
    # pass is as useless as one that cannot fail, and this codebase has
    # now produced both.
    import ast
    import inspect
    forbidden = ("post", "put", "patch", "delete", "set_price")
    called = set()
    for node in ast.walk(ast.parse(inspect.getsource(inspect.getmodule(check)))):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name:
                called.add(name)
    hits = sorted(set(forbidden) & called)
    out.append(("the collector cannot write to a shop",
                not hits, "it calls: " + ", ".join(hits) if hits else ""))

    return {"ok": all(p for _n, p, _d2 in out),
            "checks": [{"name": n, "pass": p, "detail": d} for n, p, d in out]}


if __name__ == "__main__":
    r = check()
    for c in r["checks"]:
        print(("  OK   " if c["pass"] else "  FAIL ") + c["name"]
              + (("   " + c["detail"]) if c["detail"] and not c["pass"] else ""))
    print("orders self-check:", "OK" if r["ok"] else "FAILED")
    raise SystemExit(0 if r["ok"] else 1)
