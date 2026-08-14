# -*- coding: utf-8 -*-
"""PHASE 1 GATE: every employee answers "what did you do today".

Definition of done (Section 6, P1):
  - every roster agent answers /agents/{id}/report
  - /company/today matches the sum of the agents
  - yesterday's snapshot is retrievable

The spec's own example is the core case: a day with 1 finished job, 1
failed (gdrive), and 1 open proposal must yield exactly those items
with the right kinds - a blocked tool must never be counted as a
pending approval.
"""
from __future__ import annotations

import sys
from datetime import date

import content_engine_contracts as C
import content_engine_report as RP
import content_engine_roster as R

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


class Store:
    def __init__(self):
        self.d, self.j = {}, []

    def get_setting(self, k, default=None):
        return self.d.get(k, default)

    def set_setting(self, k, v):
        self.d[k] = v

    def list_jobs(self, status=None):
        return list(self.j)

    def daily_cost(self):
        return 2.5


print("=" * 74)
print("PHASE 1 - THE DAILY REPORT")
print("=" * 74)

# The company's day, not this machine's local one. This line used to read
# date.today(): when the two disagreed, jobs stamped "today" were invisible
# to a report reading a different date, which is the same off-by-one the
# Integrations Engineer hit on its first run.
TODAY = C.today()
s = Store()
s.j = [
    {"job_id": "done1", "status": "published", "updated_at": TODAY,
     "_runs": {"content_producer": TODAY}},
    {"job_id": "dead1", "status": "failed", "updated_at": TODAY,
     "halt_reason": "gdrive rejected: 403 API disabled",
     "_runs": {"publisher": TODAY}},
    {"job_id": "wait1", "status": "AWAITING_APPROVAL", "updated_at": TODAY,
     "_runs": {"qa_compliance": TODAY}},
]

# ---- A. THE SPEC'S OWN EXAMPLE ------------------------------------------
print("\nA. ONE FINISHED, ONE FAILED, ONE WAITING")
r_prod = RP.report_today(s, "mkt.producer")
t("the producer is credited with the piece it wrote",
  len(r_prod["finished"]) == 1, str(r_prod["finished"]))
t("and is NOT blamed for another step's failure",
  len(r_prod["couldnt"]) == 0, str(r_prod["couldnt"]))
r_pub = RP.report_today(s, "mkt.distributor")
t("the publisher owns the failure, because it owned the step",
  len(r_pub["couldnt"]) == 1, str(r_pub["couldnt"]))
t("and the failure carries its CAUSE, not just a label",
  "403" in r_pub["couldnt"][0]["cause"])
r_qa = RP.report_today(s, "mkt.creative_director")
decisions = [n for n in r_qa["needs"] if n["kind"] == "decision"]
t("the waiting piece is a DECISION for a human", len(decisions) == 1,
  str(r_qa["needs"]))
t("and it names the action that resolves it",
  decisions and decisions[0]["action"].endswith("/approve"))

# ---- B. A BROKEN TOOL IS NOT AN APPROVAL --------------------------------
print("\nB. BLOCKED AND DECISION NEVER MERGE")
try:
    C.need("x", "approval")
    t("an invented need kind is refused", False, "it was allowed")
except ValueError:
    t("an invented need kind is refused", True)
t("the two kinds are the only two", set(C.NEED_KINDS) == {"decision",
                                                          "blocked"})

# ---- C. EVERY EMPLOYEE ANSWERS ------------------------------------------
print("\nC. EVERY EMPLOYEE ON THE ROSTER ANSWERS")
missing = []
for a in R.roster():
    rep = RP.report_today(s, a["id"])
    if not isinstance(rep, dict) or "finished" not in rep:
        missing.append(a["id"])
t("all %d employees answer the question" % len(R.roster()), not missing,
  str(missing))
t("and every FLOWS step is attributed to one of them",
  R.check()["ok"], str(R.check()["problems"]))

# ---- D. THE ROLLUP IS THE SUM, BY CONSTRUCTION --------------------------
print("\nD. THE COCKPIT ROLLUP CANNOT DISAGREE WITH THE CARDS")
cards = RP.agent_cards(s)
ct = RP.company_today(s)
fin = sum(len(c["report"]["finished"]) for c in cards)
cno = sum(len(c["report"]["couldnt"]) for c in cards)
ned = sum(len(c["report"]["needs"]) for c in cards)
t("finished matches the cards", ct["finished_n"] == fin,
  f"{ct['finished_n']} vs {fin}")
t("couldnt matches the cards", ct["couldnt_n"] == cno)
t("needs matches the cards", ct["need_n"] == ned)
t("and the top cause is named", bool(ct["top_causes"]),
  str(ct["top_causes"]))

# ---- E. THE CARD IS HONEST ----------------------------------------------
print("\nE. THE CARD TELLS THE TRUTH ABOUT ITS DESK")
by_id = {c["id"]: c for c in cards}
t("a not-staffed desk says so", by_id["commerce.analyst"]["badge"]
  == "notstaffed")
t("an architected desk is not called live",
  by_id["media.buyer"]["badge"] == "architected")
t("a live lane is marked live", by_id["mkt.producer"]["badge"] == "live")
t("every slot carries a real connector state",
  all(sl["status"] in C.CONNECTOR_STATES
      for c in cards for sl in c["slots"]))
t("an empty playbook says which day of training it is on",
  any("still learning" in ln for c in cards for ln in c["learned"]))

# ---- F. THE ARCHIVE, WRITTEN ONCE ---------------------------------------
print("\nF. YESTERDAY IS RETRIEVABLE, AND WRITTEN ONCE")
a = RP.snapshot(s)
b = RP.snapshot(s)
t("the first snapshot writes every employee", a["written"] == len(cards),
  str(a))
t("A SECOND FIRING WRITES NOTHING (idempotent per day)",
  b["written"] == 0, str(b))
got = RP.report_on(s, TODAY, "mkt.producer")
t("and the day can be read back", got["ok"] and "finished" in got["report"])
t("an unknown day says so rather than inventing one",
  RP.report_on(s, "1999-01-01")["ok"] is False)

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
