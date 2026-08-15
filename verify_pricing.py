# -*- coding: utf-8 -*-
"""LANE 3c STAGE 2 GATE: the only code that changes what a customer pays.

No shop is connected, so the half that matters most cannot be observed
on the box: what happens when one IS. A fake catalogue and a fake
set_price stand in, so the spend gate, the one-step bound, the
never-apply-twice rule and the honest-margin rule are all proven now.

A price change is the most consequential thing this engine can do to a
stranger. Every refusal below has its own test.
"""
from __future__ import annotations

import sys

import content_engine_commerce as CM
import content_engine_pricing as PX

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


class Store:
    def __init__(self):
        self.d = {}

    def get_setting(self, k, d=None):
        return self.d.get(k, d)

    def set_setting(self, k, v):
        self.d[k] = v


CATALOGUE = {
    "ok": True, "platform": "shopify", "products": [
        # priced under its own cost: every sale loses money
        {"id": "1", "sku": "A1", "title": "Losing money", "type": "shirt",
         "status": "active", "price": "10.00", "cost": "14.00"},
        # thin margin against a 40% target
        {"id": "2", "sku": "B2", "title": "Thin", "type": "shirt",
         "status": "active", "price": "100.00", "cost": "80.00"},
        # healthy: must NOT be proposed
        {"id": "3", "sku": "C3", "title": "Healthy", "type": "shirt",
         "status": "active", "price": "100.00", "cost": "40.00"},
        # no price at all: a finding, not a change
        {"id": "4", "sku": "D4", "title": "Unpriced", "type": "shirt",
         "status": "active", "price": "", "cost": "5.00"},
        # priced, no cost known: margin must not be invented
        {"id": "5", "sku": "E5", "title": "No cost", "type": "shirt",
         "status": "active", "price": "50.00", "cost": None},
    ]}

print("=" * 74)
print("LANE 3c STAGE 2 - PRICING AND PROMOTIONS")
print("=" * 74)

# ---- A. MARGIN IS HONEST OR ABSENT --------------------------------------
print("\nA. A MARGIN IS NEVER GUESSED")
m = PX.margin_of(100, 60)
t("with a cost it is computed", m["known"] and m["pct"] == 40.0, str(m))
m0 = PX.margin_of(100, None)
t("WITHOUT A COST IT REFUSES, rather than reading cost as zero",
  not m0["known"] and "not guessed" in m0["why"], str(m0))
t("a cost of zero would have read as a 100% margin, and does not",
  PX.margin_of(100, 0)["pct"] == 100.0)
pv = PX.preview(100, 60, 120)
t("the preview shows both margins and the delta",
  pv["margin_before_pct"] == 40.0 and pv["margin_after_pct"] == 50.0
  and pv["margin_delta_pct"] == 10.0, str(pv))
pv0 = PX.preview(100, None, 120)
t("and with no cost it shows revenue only, and SAYS why",
  pv0["margin_known"] is False and "no cost price" in pv0["margin_note"])

# ---- B. IT PROPOSES FOR NAMED REASONS -----------------------------------
print("\nB. EVERY PROPOSAL CARRIES ITS REASON AND ITS NUMBERS")
PX._catalogue = lambda store: CATALOGUE
st = Store()
res = PX.propose(st)
by = {p["sku"]: p for p in res["proposals"]}
t("the below-cost product is proposed", "A1" in by, str(sorted(by)))
t("and its reason is that it sells at a loss",
  by.get("A1", {}).get("reason") == "below_floor")
t("the thin-margin product is proposed", "B2" in by)
t("THE HEALTHY PRODUCT IS LEFT ALONE", "C3" not in by, str(sorted(by)))
t("the unpriced product is raised as a finding with no new price",
  by.get("D4", {}).get("new_price") is None)
t("EVERY proposal is pink, so none can be batch-approved",
  all(p["pink"] is True for p in res["proposals"]))
t("and no proposal moves a price more than the one-step bound",
  all(abs(p["new_price"] - p["price"]) / p["price"] * 100
      <= PX.MAX_MOVE_PCT + 0.01
      for p in res["proposals"] if p.get("new_price") and p.get("price")))

# ---- C. THE GATE --------------------------------------------------------
print("\nC. NOTHING CHANGES A PRICE WITHOUT A NAMED HUMAN")
PX.save_proposals(st, res["proposals"])
r = PX.apply_one(st, "px_B2")
t("WITH NO APPROVER IT REFUSES, naming the permanent gate",
  not r["ok"] and "spend gate is permanent" in r["why"], str(r))
r = PX.apply_one(st, "px_NOPE", approved_by="murtuja")
t("an unknown proposal is refused", not r["ok"] and "no such" in r["why"])
r = PX.apply_one(st, "px_D4", approved_by="murtuja")
t("a finding with no new price cannot be applied",
  not r["ok"] and "no price to set" in r["why"], str(r))

# ---- D. THE WRITE, AND IT HAPPENS ONCE ----------------------------------
print("\nD. AN APPROVED CHANGE IS WRITTEN, EXACTLY ONCE")
wrote = []
CM.set_price = lambda store, pid, price: (
    wrote.append((pid, price)) or {"ok": True, "product_id": pid,
                                   "price": price})
r = PX.apply_one(st, "px_B2", approved_by="murtuja")
t("the approved change is applied", r["ok"], str(r))
t("and the shop was called with the real numbers",
  len(wrote) == 1 and wrote[0][0] == "2", str(wrote))
t("the ledger records who said yes",
  PX._d(st.get_setting(PX.APPLIED_KEY)).get("2", {}).get("approved_by")
  == "murtuja")
r2 = PX.apply_one(st, "px_B2", approved_by="murtuja")
t("A SECOND APPLY IS REFUSED, because it is already applied",
  not r2["ok"] and "already applied" in r2["why"], str(r2))
t("and the shop was called exactly once", len(wrote) == 1, str(wrote))

# ---- E. A REFUSING SHOP IS NOT A SILENT SUCCESS -------------------------
print("\nE. IF THE SHOP REFUSES, THE PROPOSAL STAYS OPEN")
CM.set_price = lambda store, pid, price: {"ok": False,
                                          "why": "the token is read only"}
r = PX.apply_one(st, "px_A1", approved_by="murtuja")
t("the failure is reported with the shop's own words",
  not r["ok"] and "read only" in r["why"], str(r))
t("and the proposal is still pending, not marked applied",
  any(p["id"] == "px_A1" and p["status"] == "pending"
      for p in PX.proposals(st)))

# ---- F. DECLINE ---------------------------------------------------------
print("\nF. NO IS AN ANSWER, AND IT STICKS")
t("declining closes it", PX.decline_one(st, "px_A1", "too aggressive")["ok"])
t("and it is no longer pending",
  not [p for p in PX.proposals(st, "pending") if p["id"] == "px_A1"])
t("declining twice is refused", not PX.decline_one(st, "px_A1")["ok"])

# ---- G. THE RULES CANNOT BE QUIETLY REMOVED -----------------------------
print("\nG. THE LANE'S OWN CHECK GUARDS ITS RULES")
c = PX.check()
t("the pricing lane passes its own check", c["ok"], str(c["problems"]))
# The REAL set_price, not the stand-in: reload it and check its own
# refusals. The line here used to be `not X or True`, which is a test
# that cannot fail and therefore is not a test.
import importlib

_CM = importlib.reload(importlib.import_module("content_engine_commerce"))
t("the real shop write refuses a price of zero or less",
  not _CM.set_price(None, "1", -5)["ok"]
  and "never a price change" in _CM.set_price(None, "1", -5)["why"])
t("and refuses a value that is not a number",
  not _CM.set_price(None, "1", "cheap")["ok"])
t("and refuses when no product is named",
  not _CM.set_price(None, "", 10)["ok"])

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
