# -*- coding: utf-8 -*-
"""LANE 3a GATE: the Integrations Engineer is an employee, not a screen.

Definition of done (Section 6, P3): the scheduler creates its work, the
lane runs it, the report includes it, the guardrail holds it, and the
badge flips only after all of that.

The rung this gate guards hardest is the guardrail. This employee exists
to watch the connector health that Phase 0 made honest. If it could mark
a wire verified from its own free checks, it would re-introduce exactly
the false green Phase 0 removed, from inside the machinery built to
prevent it. So: it finds faults, it proposes fixes, and it may never
write a verdict.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import content_engine_connectors as CN
import content_engine_contracts as C
import content_engine_integrations as INT
import content_engine_learning as L
import content_engine_report as RP
import content_engine_roster as R
import content_engine_scheduler as SCH

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


NOW = datetime.now(timezone.utc)
OLD = (NOW - timedelta(days=40)).isoformat()
FRESH = (NOW - timedelta(days=1)).isoformat()

print("=" * 74)
print("LANE 3a - THE INTEGRATIONS ENGINEER")
print("=" * 74)

# ---- A. IT WATCHES WIRES THAT ACTUALLY EXIST ----------------------------
print("\nA. IT WATCHES REAL WIRES")
chk = INT.check()
t("every wire it names is a real wire", chk["ok"], str(chk["problems"]))
t("it sits on the roster", bool(R.agent(INT.AGENT_ID)))
t("and it writes to the system lane",
  R.lane_of(INT.AGENT_ID) == INT.LANE == "system")

# ---- B. THE FINDING NOBODY NOTICES --------------------------------------
print("\nB. A WIRE THAT WAS FINE YESTERDAY AND REFUSES TODAY")
mem = {"connector_health": {
    "wordpress_publish": {"status": "rejected", "reason": "401 rejected token",
                          "last_verified": FRESH},
    "claude_api": {"status": "verified", "last_verified": OLD},
}}
CN.set_settings_reader(lambda k, d=None: mem.get(k, d))
CN.set_settings_writer(lambda k, v: mem.__setitem__(k, v))
CN._SHADOWED = {"WP_APP_PASSWORD": "the saved value was malformed and the "
                                   "environment copy was used"}

s = Store()
s.d[INT._SEEN_KEY] = {"wordpress_publish": "verified", "claude_api": "verified"}
out = INT.run(s, NOW)
kinds = {f["kind"] for f in out["findings"]}
by_kind = {}
for f in out["findings"]:
    by_kind.setdefault(f["kind"], []).append(f)

t("it caught the wire that started refusing", "newly_rejected" in kinds,
  str(sorted(kinds)))
t("and quoted the provider's own words",
  any("401" in f["cause"] for f in by_kind.get("newly_rejected", [])))
t("it named the fix, not just the fault",
  all(f["fix"].strip() for f in out["findings"]))

# ---- C. THE CRUELLEST CLASS ---------------------------------------------
print("\nC. A KEY THAT IS SAVED BUT NOT THE ONE BEING USED")
t("a shadowed key is reported", "shadowed" in kinds, str(sorted(kinds)))
t("and it says the edit you make will do nothing",
  any("no effect" in f["fix"] for f in by_kind.get("shadowed", [])))

# ---- D. GREEN THAT STOPPED MEANING ANYTHING -----------------------------
print("\nD. VERIFIED 40 DAYS AGO IS NOT VERIFIED TODAY")
t("stale green is surfaced", "stale" in kinds, str(sorted(kinds)))
t("but it is NOT silently downgraded on the board",
  CN.health() and all(r["status"] == "verified" for r in CN.health()
                      if r["wire"] == "claude_api"))

# ---- E. THE GUARDRAIL THIS LANE EXISTS TO RESPECT ------------------------
print("\nE. IT PROPOSES. IT NEVER MARKS ANYTHING VERIFIED.")
before = {w: dict(v) for w, v in mem["connector_health"].items()}
INT.run(s, NOW)
after = {w: dict(v) for w, v in (mem.get("connector_health") or {}).items()}
t("NO VERDICT WAS WRITTEN BY THIS EMPLOYEE", before == after,
  str(after))
t("nothing it can do turns a wire green",
  not any(f.get("kind") == "verified" for f in out["findings"]))
props = INT.proposals(s)
t("a re-auth is a PROPOSAL, pending a person",
  bool(props) and all(p["status"] == "pending" for p in props), str(props))
t("and every proposal points at where to fix it",
  all(p["action"].startswith("/connect#") for p in props))

# ---- F. IT DOES NOT NAG, AND IT DOES NOT FORGET -------------------------
print("\nF. ONE PROPOSAL PER FAULT - BUT IT ASKS AGAIN IF IT BREAKS AGAIN")
n1 = len(INT.proposals(s))
INT.run(s, NOW)
t("a second run does not duplicate the proposal",
  len(INT.proposals(s)) == n1, f"{n1} -> {len(INT.proposals(s))}")
mem["connector_health"]["wordpress_publish"] = {"status": "verified",
                                                "last_verified": FRESH}
INT.run(s, NOW)
t("a FIXED wire drops off the list",
  not any(p["wire"] == "wordpress_publish" for p in INT.proposals(s)),
  str(INT.proposals(s)))
mem["connector_health"]["wordpress_publish"] = {"status": "rejected",
                                                "reason": "401 again",
                                                "last_verified": FRESH}
INT.run(s, NOW)
t("AND IT ASKS AGAIN WHEN THE SAME WIRE BREAKS AGAIN",
  any(p["wire"] == "wordpress_publish" for p in INT.proposals(s)),
  str(INT.proposals(s)))

# ---- G. IT ANSWERS THE QUESTION EVERY EMPLOYEE ANSWERS -------------------
print("\nG. WHAT DID YOU DO TODAY")
rep = RP.report_today(s, INT.AGENT_ID)
t("it reports a day of work", bool(rep["finished"]), str(rep))
t("its asks are DECISIONS, not blocked tools",
  all(n["kind"] in C.NEED_KINDS for n in rep["needs"])
  and any(n["kind"] == "decision" for n in rep["needs"]), str(rep["needs"]))
roll = RP.company_today(s)
cards = RP.agent_cards(s)
fin = sum(len(c["report"]["finished"]) for c in cards)
t("and the company rollup still equals the sum of the cards",
  roll["finished_n"] == fin, f"{roll['finished_n']} vs {fin}")
t("its own card carries its work",
  any(c["id"] == INT.AGENT_ID and c["report"]["finished"] for c in cards))

# ---- H. IT REMEMBERS BETWEEN RUNS ---------------------------------------
print("\nH. MEMORY: IT KNOWS WHICH WIRES MISBEHAVE")
pb = L.get_playbook("acme", "system")
t("the system playbook has cycles", pb["cycles"] > 0, str(pb["cycles"]))
t("and it remembers a specific wire",
  any("wordpress" in str(x).lower() for x in pb["observations"]),
  str(pb["observations"])[:120])
t("an observation is not filed as a WIN (it is a fault it saw)",
  not pb["winning_topics"], str(pb["winning_topics"]))
learned = RP.learned_lines(s, INT.AGENT_ID)
t("its card recites what IT learned, not the writer's lessons",
  any("wordpress" in ln.lower() or "shadow" in ln.lower() for ln in learned),
  str(learned))

# ---- I. THE SCHEDULE, AND WHAT IT MAY COST ------------------------------
print("\nI. IT HAS A WORKING DAY, AND IT IS FREE")
t("the cadence knows the lane", "integrations" in SCH.SEO_CADENCE)
t("and declares it free, because it makes no calls",
  SCH.SEO_CADENCE["integrations"]["cost"] == "free")
src = open(SCH.__file__, encoding="utf-8").read()
t("IT RUNS BEFORE THE NIGHTLY ARCHIVE, or its day is frozen empty",
  src.index('_due(state, "integrations"') < src.index('_due(state, "snapshot"'))

# ---- J. THE BADGE ONLY FLIPS WHEN ALL OF THAT IS TRUE -------------------
print("\nJ. THE BADGE IS EARNED")
me = R.agent(INT.AGENT_ID)
t("it is no longer an inspector", me["badge"] == "live", me["badge"])
t("and the badge names what makes it live", "cadence" in me["why"].lower()
  or "daily" in me["why"].lower(), me["why"])

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
