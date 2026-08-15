# -*- coding: utf-8 -*-
"""Gate for the bookings collector, and for the feed it shares.

The interesting failures here are not inside either collector. They are
in the seam: two modules now write content_engine_bi.py's deals key, and
whichever ran last must not erase the other. That is checked from BOTH
sides, because a one-sided check would have passed while the bug was
still live in the other direction, which is exactly what happened while
this was being written.
"""
from __future__ import annotations

import content_engine_bi as BI
import content_engine_bookings as BK
import content_engine_orders as OR
import content_engine_scheduler as SCH

_P, _F = [], []


def t(label, cond, detail=""):
    (_P if cond else _F).append(label)
    print(("  OK   " if cond else "  FAIL ") + label
          + (("   " + str(detail)[:130]) if detail and not cond else ""))
    return bool(cond)


def _store(data=None):
    return BK._FakeStore(data or {})


print("=" * 74)
print("BOOKINGS, AND THE FEED TWO COLLECTORS SHARE")
print("=" * 74)

print("")
print("A. THE MODULE PASSES ITS OWN CHECK")
for c in BK.check()["checks"]:
    t(c["name"], c["pass"], c["detail"])

print("")
print("B. A BOOKING IS NOT A SALE")
_st = _store({BK.BOOKINGS_KEY: [{"id": "b1", "client": "Ada",
                                 "at": "2026-08-01", "accepted": True}],
              BK.WON_KEY: {}})
t("an accepted booking contributes NOTHING to revenue on its own",
  BI.revenue(BK.to_deals(_st))["total"] == 0.0
  and BI.revenue(BK.to_deals(_st))["deals"] == 0)
t("and it is visible as pipeline instead of vanishing",
  BK.pipeline(BK.list_bookings(_st), {})["accepted"] == 1)
t("the engine refuses to guess what the project was worth",
  not BK.win(_st, "b1", None, approved_by="Founder")["ok"])
_ok = BK.win(_st, "b1", 2500, approved_by="Founder", source="referral")
t("a human with a number and a name turns it into revenue", _ok["ok"], _ok)
t("and only THEN does revenue move",
  BI.revenue(BK.to_deals(_st))["total"] == 2500.0)

print("")
print("C. ONE FEED, TWO OWNERS, NEITHER ERASES THE OTHER")
# Booking first, then an orders collect on top of it.
_s1 = _store({BI.DEALS_KEY: [{"id": "book-b1", "client": "C",
                              "value": 900.0, "at": "2026-08-01",
                              "source": "referral"}]})
OR.save(_s1, [OR.normalise({"id": 7, "created_at": "2026-08-03T00:00:00Z",
                            "email": "a@x.com",
                            "customer": {"first_name": "Ada"},
                            "total_price": "50.00", "source_name": "web",
                            "financial_status": "paid", "test": False,
                            "line_items": []}, "shopify")])
_split = OR.countable(OR.list_orders(_s1))
_keep = [d for d in _s1.get_setting(BI.DEALS_KEY, [])
         if not str(d.get("id", "")).startswith("ord-")]
_s1.set_setting(BI.DEALS_KEY, _keep + OR.to_deals(_split["orders"]))
_ids = [d["id"] for d in _s1.get_setting(BI.DEALS_KEY, [])]
t("AN ORDERS COLLECT DOES NOT DELETE A WON BOOKING",
  "book-b1" in _ids and "ord-7" in _ids, _ids)
t("and revenue is the sum of both, not one of them",
  BI.revenue(_s1.get_setting(BI.DEALS_KEY, []))["total"] == 950.0)

# Now the other direction: a bookings sync on top of order rows.
_s2 = _store({BI.DEALS_KEY: [{"id": "ord-1", "client": "Shop", "value": 10.0,
                              "at": "2026-08-01", "source": "direct"}],
              BK.BOOKINGS_KEY: [{"id": "b9", "client": "B",
                                 "at": "2026-08-02"}],
              BK.WON_KEY: {}})
BK.win(_s2, "b9", 900, approved_by="Founder", source="referral")
_ids2 = [d["id"] for d in _s2.get_setting(BI.DEALS_KEY, [])]
t("A BOOKINGS SYNC DOES NOT DELETE AN ORDER", "ord-1" in _ids2
  and "book-b9" in _ids2, _ids2)
t("each owner stamps a prefix, so ownership is readable",
  all(str(i).startswith(("ord-", "book-")) for i in _ids + _ids2))

print("")
print("D. ABSENCE, ONCE MORE")
t("a conversion rate over no bookings is None, not 0.0",
  BK.pipeline([])["conversion_rate"] is None)
t("a wire that cannot be read reports count=None, never 0",
  BK.fetch(None).get("count") is None)
t("and it names the key a human has to go and set",
  "CALCOM_API_KEY" in str(BK.fetch(None).get("why")))

print("")
print("E. ON THE CADENCE, AND IT CANNOT SPEND")
t("bookings has its own cadence key", "bookings" in SCH.SEO_CADENCE)
t("it is free: one read, no model call",
  SCH.SEO_CADENCE.get("bookings", {}).get("cost") == "free")
t("it does not collide with the orders key",
  "orders" in SCH.SEO_CADENCE and "bookings" in SCH.SEO_CADENCE)

print("")
print("F. THE VOCABULARY IS STILL SHARED")
t("a source BI does not know is refused rather than coerced to 'other'",
  not BK.win(_store({BK.BOOKINGS_KEY: [{"id": "z", "client": "C",
                                        "at": "2026-08-01"}],
                     BK.WON_KEY: {}}),
             "z", 100, approved_by="H", source="tiktok")["ok"])

print("")
print("=" * 74)
print("%d passed, %d failed" % (len(_P), len(_F)))
if _F:
    for f in _F:
        print("  FAILED: " + f)
print("=" * 74)
raise SystemExit(1 if _F else 0)
