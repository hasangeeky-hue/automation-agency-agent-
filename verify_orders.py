# -*- coding: utf-8 -*-
"""Gate for the orders collector, stage 2 of the data contract.

The collector's own check() covers its internals. This file covers the
things that can only go wrong BETWEEN modules: the vocabulary it shares
with BI, the key it writes into, the cadence that calls it, and the
route that exposes it. Every one of those is a place where two files
have to agree, which is where this codebase breaks most often.
"""
from __future__ import annotations

import content_engine_bi as BI
import content_engine_orders as OR
import content_engine_scheduler as SCH

_P, _F = [], []


def t(label, cond, detail=""):
    (_P if cond else _F).append(label)
    print(("  OK   " if cond else "  FAIL ") + label
          + (("   " + str(detail)[:130]) if detail and not cond else ""))
    return bool(cond)


print("=" * 74)
print("ORDERS COLLECTOR")
print("=" * 74)

print("")
print("A. THE MODULE PASSES ITS OWN CHECK")
r = OR.check()
for c in r["checks"]:
    t(c["name"], c["pass"], c["detail"])

print("")
print("B. THE VOCABULARY IS SHARED, NOT RETYPED")
t("every source this module emits is one BI knows",
  set(OR.SOURCE_MAP.values()) <= set(BI.SOURCES),
  sorted(set(OR.SOURCE_MAP.values()) - set(BI.SOURCES)))
# The map exists to translate. If it only ever produced "other" it would
# pass the check above while being useless, so prove it really routes.
t("and the map actually routes, rather than sending everything to 'other'",
  len({v for v in OR.SOURCE_MAP.values()}) >= 3,
  sorted(set(OR.SOURCE_MAP.values())))
t("a draft order is attributed to outreach, not lost in 'other'",
  OR.map_source("shopify_draft_order") == "outreach")
t("an unknown channel falls back to 'other' AND is reported",
  OR.map_source("tiktok_shop") == "other"
  and OR.unmapped_sources([{"source_raw": "tiktok_shop"}]) == ["tiktok_shop"])

print("")
print("C. THE PROJECTION LANDS WHERE THE SCREENS ALREADY LOOK")
_raw = [
    {"id": 1, "created_at": "2026-08-01T10:00:00Z", "email": "a@x.com",
     "customer": {"first_name": "Ada"}, "total_price": "120.00",
     "source_name": "web", "financial_status": "paid", "test": False,
     "line_items": [{"sku": "SKU-A", "title": "Widget", "quantity": 2,
                     "price": "50.00", "product_id": 9}]},
    {"id": 2, "created_at": "2026-08-05T10:00:00Z", "email": "a@x.com",
     "customer": {"first_name": "Ada"}, "total_price": "80.00",
     "source_name": "shopify_draft_order", "financial_status": "paid",
     "test": False,
     "line_items": [{"sku": "SKU-A", "title": "Widget", "quantity": 1,
                     "price": "50.00", "product_id": 9}]},
    {"id": 3, "created_at": "2026-08-06T10:00:00Z", "email": "t@x.com",
     "customer": {"first_name": "Test"}, "total_price": "999.00",
     "source_name": "web", "financial_status": "paid", "test": True,
     "line_items": []},
]
_orders = [OR.normalise(x, "shopify") for x in _raw]
_split = OR.countable(_orders)
_deals = OR.to_deals(_split["orders"])
_rev = BI.revenue(_deals)
_cust = BI.customers(_deals)

t("an order becomes a deal BI can actually read", _rev["deals"] == 2, _rev)
t("A TEST ORDER IS NOT REVENUE", _rev["total"] == 200.0, _rev["total"])
t("and the test order is counted, not silently dropped",
  _split["excluded_test"] == 1, _split)
t("revenue by channel uses BI's own words",
  ("outreach", 80.0) in _rev["by_source"], _rev["by_source"])
t("a returning customer is recognised as returning",
  _cust["repeat_rate"] == 100.0, _cust["repeat_rate"])

print("")
print("D. THE QUESTION ONLY LINE ITEMS CAN ANSWER")
_top = OR.top_sellers(_split["orders"])
t("top sellers counts UNITS across orders, not orders",
  bool(_top) and _top[0]["units"] == 3, _top)
t("and it names the product, which no deal carries",
  bool(_top) and _top[0]["sku"] == "SKU-A", _top)
_unpriced = OR.top_sellers([{"line_items": [{"sku": "B", "qty": 4,
                                             "price": None}]}])
t("AN UNPRICED LINE MAKES REVENUE UNKNOWN, NEVER A SMALLER NUMBER",
  _unpriced[0]["revenue"] is None and _unpriced[0]["units"] == 4, _unpriced)

print("")
print("E. ABSENCE IS NOT ZERO, AND SILENCE IS NOT SUCCESS")
t("a missing total stays missing", OR._money(None) is None
  and OR._money("") is None)
t("an order that sold for an unknown amount is its OWN category",
  OR.countable([{"financial_status": "paid",
                 "value": None}])["excluded_no_total"] == 1)
# A failed call and an empty shop are different facts. count is None on
# failure and an integer on success, so a caller never has to read prose
# to tell them apart.
_fail = OR.fetch_orders(None)
t("a shop that cannot be read reports count=None, never 0",
  _fail.get("count") is None and not _fail.get("ok"), _fail.get("why"))
t("and it says WHY in a sentence a human can act on",
  bool(_fail.get("why")), _fail)

print("")
print("F. IT IS ON THE CADENCE, AND IT CANNOT SPEND")
t("the collector has its own cadence key", "orders" in SCH.SEO_CADENCE)
t("it is free, because it makes no model call",
  SCH.SEO_CADENCE.get("orders", {}).get("cost") == "free")
t("it does not collide with an existing cadence name",
  len([k for k in SCH.SEO_CADENCE if k == "orders"]) == 1)
# Ordering matters: the commerce desk and the pricing review should
# reason about today's orders, not yesterday's.
_keys = list(SCH.SEO_CADENCE)
t("and it is scheduled BEFORE commerce, so pricing sees fresh orders",
  "orders" in _keys and "commerce" in _keys
  and _keys.index("orders") < _keys.index("commerce"))

print("")
print("G. IT IS A READ. IT CANNOT TOUCH A CUSTOMER")
t("the collector calls no write verb on any shop",
  OR.check()["checks"][-1]["pass"])
t("and the only price-writing function in the engine is elsewhere",
  not hasattr(OR, "set_price"))

print("")
print("=" * 74)
print("%d passed, %d failed" % (len(_P), len(_F)))
if _F:
    for f in _F:
        print("  FAILED: " + f)
print("=" * 74)
raise SystemExit(1 if _F else 0)
