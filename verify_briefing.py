# -*- coding: utf-8 -*-
"""THE BRIEFING GATE: the report reaches the founder, and only the founder.

Two things are being protected here.

The first is the doctrine's Difference 3: it messages you only when a
human must decide. A daily "all fine" trains a person to stop reading,
and then the one that mattered goes unread too. So the interesting test
is not that it sends, it is that IT STAYS QUIET.

The second is that a notifier must never become a send path. This engine
already has one of those, with a gate on it. If a caller could name the
recipient, the briefing would be an ungated way to email arbitrary
people on a schedule, so no function in that module takes an address.
"""
from __future__ import annotations

import sys

import content_engine_briefing as BR

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


class Store:
    def __init__(self, **kw):
        self.d = {"BRAND_NAME": "Anthropos"}
        self.d.update(kw)
        self.sent = []

    def get_setting(self, k, d=None):
        return self.d.get(k, d)

    def set_setting(self, k, v):
        self.d[k] = v

    def list_jobs(self, status=None):
        return []

    def daily_cost(self):
        return 0.0


QUIET = {"finished_n": 4, "decisions": [], "blocked": [], "couldnt": [],
         "by_agent": []}
NEEDY = {"finished_n": 2, "by_agent": [],
         "decisions": [{"who": "QA", "what": "approve piece 12",
                        "why": "written and checked",
                        "action": "/jobs/12/approve"}],
         "blocked": [{"who": "Publisher", "what": "gdrive is refusing",
                      "why": "403 API disabled"}],
         "couldnt": [{"who": "Publisher", "what": "job 9",
                      "cause": "gdrive rejected 403"}]}

print("=" * 74)
print("THE MORNING BRIEFING")
print("=" * 74)

# ---- A. IT CANNOT BE ADDRESSED BY ANYONE --------------------------------
print("\nA. A NOTIFIER, NOT A SEND PATH")
c = BR.check()
t("no function in the module takes a recipient", c["ok"], str(c["problems"]))
st = Store(FOUNDER_EMAIL="founder@example.com")
t("the address comes from settings",
  BR.founder_address(st) == "founder@example.com")
t("and with no address set it refuses rather than guessing",
  BR.founder_address(Store()) == "")

# ---- B. SILENCE IS THE SIGNAL -------------------------------------------
print("\nB. IT STAYS QUIET WHEN NOTHING NEEDS YOU")
t("a day with nothing waiting sends NOTHING",
  BR.should_send(QUIET) is False)
t("a day with a decision sends", BR.should_send(NEEDY) is True)
t("a day with only a FAILURE still sends, because you should know",
  BR.should_send({"decisions": [], "blocked": [],
                  "couldnt": [{"what": "x", "cause": "y"}]}) is True)
t("and the weekly review goes out even on a quiet week",
  BR.should_send(QUIET, review=True) is True)

# ---- C. THE MESSAGE ITSELF ----------------------------------------------
print("\nC. WHAT IT ACTUALLY SAYS")
m = BR.compose(st, NEEDY)
t("the subject counts what needs a human", "1 needs you" in m["subject"],
  m["subject"])
t("and it is grammatical for one item",
  "1 need you" not in m["subject"], m["subject"])
m2 = BR.compose(st, {"finished_n": 0, "by_agent": [], "couldnt": [],
                     "blocked": [],
                     "decisions": [{"what": "a"}, {"what": "b"}]})
t("and for several", "2 need you" in m2["subject"], m2["subject"])
t("the decision is listed with the route that resolves it",
  "/jobs/12/approve" in m["body"])
t("BLOCKED IS SEPARATED, and says approving will not fix it",
  "BLOCKED, NOT YOURS TO APPROVE" in m["body"]
  and "Nothing you approve will fix them" in m["body"])
t("the failure carries its cause", "gdrive rejected 403" in m["body"])
t("and it explains its own silence",
  "nothing does, nothing is sent" in m["body"])

# ---- D. IT DOES NOT SEND TWICE, OR WITHOUT A WAY TO --------------------
print("\nD. ONCE A DAY, AND ONLY IF IT CAN")
st2 = Store(FOUNDER_EMAIL="founder@example.com")
r = BR.run(st2)
t("with no SMTP it says so and does not pretend",
  r["sent"] is False and ("SMTP" in r["why"] or "quiet" in r["why"]
                          or "nothing needed" in r["why"]), str(r))
st3 = Store()
r3 = BR.run(st3, force=True)
t("with no founder address it names the setting to add",
  r3["sent"] is False, str(r3))

# a quiet day is RECORDED, so silence is never mistaken for a dead cron
st4 = Store(FOUNDER_EMAIL="f@e.com")
BR.run(st4)
t("a quiet day is recorded, so silence is not a dead cron",
  bool(st4.get_setting(BR.SENT_KEY)), str(st4.get_setting(BR.SENT_KEY)))
r4 = BR.run(st4)
t("and a second run the same day does nothing",
  r4["sent"] is False and "already sent" in r4["why"], str(r4))

# ---- E. THE PINK ITEMS ARE MARKED IN THE MAIL TOO ----------------------
print("\nE. A PRICE CHANGE IS NOT JUST ANOTHER TO-DO")
import content_engine_pricing as PX

st5 = Store(FOUNDER_EMAIL="f@e.com")
st5.set_setting(PX.PROPOSALS_KEY, [{
    "id": "px_1", "title": "A product", "price": 100.0, "new_price": 120.0,
    "why": "its margin is thinner than the target", "status": "pending",
    "pink": True, "preview": {"margin_known": False}}])
g = BR.gather(st5)
t("a pending price proposal reaches the briefing",
  any("A product" in _d.get("what", "") for _d in g["decisions"]),
  str(g["decisions"]))
t("and it is marked pink in the mail",
  any("pink" in _d.get("who", "") for _d in g["decisions"]))

# ---- F. IT RUNS ON A CLOCK, AFTER THE WORK -----------------------------
print("\nF. IT RUNS LAST, BECAUSE IT REPORTS THE DAY")
import content_engine_scheduler as SCH

t("the cadence knows it", "briefing" in SCH.SEO_CADENCE)
t("and it is free", SCH.SEO_CADENCE["briefing"]["cost"] == "free")
_src = open(SCH.__file__, encoding="utf-8").read()
t("IT RUNS AFTER THE NIGHTLY SNAPSHOT, not before",
  _src.index('_due(state, "briefing"') > _src.index('_due(state, "snapshot"'))

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
