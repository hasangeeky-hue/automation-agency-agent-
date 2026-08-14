# -*- coding: utf-8 -*-
"""PHASE 2 GATE: memory is per lane, and it is readable back.

Definition of done (Section 6, P2):
  - every lane folds its outcomes into a playbook
  - /agents/{id}/learned answers from THAT employee's lane
  - an empty playbook says which day of training it is on

The failure this gate exists to catch is quiet and expensive: one shared
playbook means the outreach writer's lesson is filed where the blog
writer reads it. Nothing errors. Both lanes just slowly learn the wrong
things, and every card recites the same three lines so the founder
cannot tell which employee actually knows anything.
"""
from __future__ import annotations

import sys

import content_engine_learning as L
import content_engine_orchestrator as O
import content_engine_report as RP
import content_engine_roster as R

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


class Store:
    def __init__(self):
        self.d, self.j = {"BRAND_NAME": "acme"}, []

    def get_setting(self, k, default=None):
        return self.d.get(k, default)

    def set_setting(self, k, v):
        self.d[k] = v

    def list_jobs(self, status=None):
        return list(self.j)

    def daily_cost(self):
        return 0.0


print("=" * 74)
print("PHASE 2 - MEMORY, PER LANE")
print("=" * 74)

L.set_store(L.InMemoryLearningStore())

# ---- A. THE LANES DO NOT LEAK INTO EACH OTHER ---------------------------
print("\nA. ONE LANE'S LESSON STAYS IN ITS OWN LANE")
L.record_cycle("acme", {"insights": [{"finding": "long guides win"}],
                        "double_down": [{"what": "how-to guides"}],
                        "measured": True}, lane="content")
L.record_cycle("acme", {"insights": [{"finding": "short subjects win"}],
                        "double_down": [{"what": "one-line subjects"}],
                        "measured": True}, lane="outreach")
c = L.get_playbook("acme", "content")
o = L.get_playbook("acme", "outreach")
t("the writer learned its own lesson",
  any("how-to" in str(x) for x in c["winning_topics"]), str(c["winning_topics"]))
t("and NOT the outreach writer's",
  not any("subject" in str(x) for x in c["winning_topics"]),
  str(c["winning_topics"]))
t("the outreach writer kept its own",
  any("one-line" in str(x) for x in o["winning_topics"]), str(o["winning_topics"]))
t("a lane nobody has taught is honestly empty",
  L.get_playbook("acme", "seo")["cycles"] == 0)

# ---- B. THE CONTENT LANE KEEPS THE OLD KEY (nothing is orphaned) --------
print("\nB. EVERY PLAYBOOK ALREADY ON THE VPS SURVIVES")
t("'content' still reads the bare client key",
  L._lane_key("acme", "content") == "acme")
t("and another lane does not collide with it",
  L._lane_key("acme", "seo") == "acme#seo")
t("get_playbook defaults to the content lane",
  L.get_playbook("acme") == L.get_playbook("acme", "content"))

# ---- C. LANES THAT ARE NOT PIPELINES CAN STILL LEARN --------------------
print("\nC. A CADENCE LANE CAN WRITE TO ITS OWN PLAYBOOK")
L.record_lane_cycle("acme", "system", learned=["gdrive flapped twice"],
                    avoid=["retrying a 403"])
sysp = L.get_playbook("acme", "system")
t("the system lane recorded a cycle", sysp["cycles"] == 1, str(sysp["cycles"]))
t("and it remembers what to avoid",
  any("403" in str(x) for x in sysp["avoid"]), str(sysp["avoid"]))
try:
    L.record_lane_cycle("acme", "system")
    t("A QUIET DAY IS NOT A CYCLE", False, "an empty cycle was counted")
except ValueError:
    t("A QUIET DAY IS NOT A CYCLE", True)
t("and the quiet day did not inflate the count",
  L.get_playbook("acme", "system")["cycles"] == 1)

# ---- D. THE VOCABULARY LISTS AGREE (the recurring bug class) ------------
print("\nD. THE LISTS THAT MUST AGREE ARE CHECKED, NOT TYPED TWICE")
t("every job flow names the lane it teaches",
  set(O.FLOWS) <= set(O.LANE_OF_JOB), str(set(O.FLOWS) - set(O.LANE_OF_JOB)))
t("and every one of those lanes is real",
  set(O.LANE_OF_JOB.values()) <= set(L.LANES))
t("every employee's desk maps to a real lane",
  all(R.lane_of(a["id"]) in L.LANES for a in R.roster()))
t("every outcome kind files into a real lane",
  set(L._OUTCOME_LANE.values()) <= set(L.LANES))
t("and the roster's own check enforces it", R.check()["ok"],
  str(R.check()["problems"]))
try:
    L.get_playbook("acme", "marketing")
    t("an invented lane is refused", False, "it was allowed")
except ValueError:
    t("an invented lane is refused", True)

# ---- E. AN OUTCOME LANDS ON THE DESK THAT EARNED IT ---------------------
print("\nE. A SUBJECT LINE THAT BOOKED A CALL IS THE OUTREACH DESK'S WIN")
L.record_outcome("acme", "email_subject", "quick question about your intake")
t("it landed in the outreach lane",
  any("intake" in str(x) for x in
      L.get_playbook("acme", "outreach").get("winning_email_subjects", [])))
t("and NOT in the writer's",
  not L.get_playbook("acme", "content").get("winning_email_subjects"))

# ---- F. THE CARD READS THE EMPLOYEE'S OWN LANE --------------------------
print("\nF. /agents/{id}/learned ANSWERS FROM THE RIGHT PLAYBOOK")
s = Store()
w = RP.learned_lines(s, "mkt.producer")
x = RP.learned_lines(s, "leads.outreach_writer")
t("the writer recites its own lesson",
  any("how-to" in ln for ln in w), str(w))
t("the outreach writer recites a DIFFERENT one",
  any("one-line" in ln for ln in x), str(x))
t("two employees no longer read the same three lines", w != x,
  str(w) + " vs " + str(x))
u = RP.learned_lines(s, "bi.analyst")
t("an untaught employee says which day of training it is on",
  any("still learning" in ln for ln in u), str(u))

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
