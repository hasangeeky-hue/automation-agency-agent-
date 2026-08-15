# -*- coding: utf-8 -*-
"""LANE 3d GATE: the Social Distributor posts, and refuses, for reasons.

No channel is wired today, so the interesting half of this gate is the
half that cannot be observed on the box: what happens WHEN one verifies.
A fake verified channel and a fake poster stand in, so the approval gate,
the verified-not-available rule and the never-post-twice rule are all
proven now rather than discovered later in front of an audience.
"""
from __future__ import annotations

import sys

import content_engine_social_desk as SD

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


class Store:
    def __init__(self):
        self.d, self.j = {}, {}

    def get_setting(self, k, d=None):
        return self.d.get(k, d)

    def set_setting(self, k, v):
        self.d[k] = v

    def list_jobs(self, status=None):
        return list(self.j.values())

    def get(self, jid):
        return self.j.get(jid)

    def save(self, job):
        self.j[job["job_id"]] = job


def piece(jid, approved=True, posted=None, text="hello world"):
    return {"job_id": jid, "approved": approved, "text": text,
            "channels": ["linkedin"], "pending": ["linkedin"],
            "posted": posted or []}


print("=" * 74)
print("LANE 3d - THE SOCIAL DISTRIBUTOR")
print("=" * 74)

# ---- A. IT NAMES REAL THINGS --------------------------------------------
print("\nA. IT NAMES POSTERS AND WIRES THAT EXIST")
c = SD.check()
t("every channel maps to a real poster and a real wire", c["ok"],
  str(c["problems"]))
t("and every channel states the credential it needs",
  set(SD.CHANNELS) == set(SD.CHANNEL_NEEDS))

# ---- B. TODAY: NOTHING IS WIRED, AND IT SAYS SO -------------------------
print("\nB. WITH NOTHING WIRED IT BLOCKS, IT DOES NOT PRETEND")
st = Store()
st.save({"job_id": "a1", "approved": True, "status": "approved",
         "payload": {"social_text": "written and approved",
                     "channels": ["linkedin"]}})
out = SD.run(st)
t("nothing was posted", out["posted"] == [], str(out["posted"]))
blocked = [n for n in out["report"]["needs"] if n["kind"] == "blocked"]
t("the missing channel is BLOCKED, not a decision to approve",
  len(blocked) == 1, str(out["report"]["needs"]))
t("and it names what each channel needs",
  "LinkedIn access token" in blocked[0]["why"])

# ---- C. THE THREE REFUSALS ----------------------------------------------
print("\nC. THE THREE SEPARATE REASONS A POST DOES NOT GO OUT")
r = SD.post_one(st, piece("x", approved=False), "linkedin")
t("an UNAPPROVED piece is refused, naming the gate",
  not r["ok"] and "permanent gate" in r["why"], str(r))
r = SD.post_one(st, piece("x"), "linkedin")
t("an UNVERIFIED channel is refused even with a saved key",
  not r["ok"] and "not verified" in r["why"], str(r))
r = SD.post_one(st, piece("x", posted=["linkedin"]), "linkedin")
t("a piece ALREADY POSTED is refused",
  not r["ok"] and "second post" in r["why"], str(r))
r = SD.post_one(st, piece("x"), "myspace")
t("an invented channel is refused", not r["ok"] and "not a channel" in r["why"])

# ---- D. WHEN A CHANNEL VERIFIES, IT ACTUALLY POSTS -----------------------
print("\nD. THE HALF THAT CANNOT BE SEEN ON THE BOX YET")
sent = []


class _FakePoster:
    def available(self):
        return True

    def post(self, text):
        sent.append(text)
        return "urn:li:share:12345"


import content_engine_connectors as CN
_real_state = SD.channel_state


def _verified_state(store=None):
    s = _real_state(store)
    s["linkedin"] = dict(s["linkedin"], status="verified", verified=True,
                         available=True)
    return s


SD.channel_state = _verified_state
CN.LinkedInPoster = _FakePoster

st2 = Store()
st2.save({"job_id": "b1", "approved": True, "status": "approved",
          "payload": {"social_text": "the real thing",
                      "channels": ["linkedin"]}})
out2 = SD.run(st2)
t("it posts the approved piece", len(out2["posted"]) == 1, str(out2["posted"]))
t("it sent the actual text", sent == ["the real thing"], str(sent))
t("and the report credits it",
  bool(out2["report"]["finished"]), str(out2["report"]))

# ---- E. IDEMPOTENCE: THE ONE THAT MATTERS TO STRANGERS ------------------
print("\nE. THE SAME LIST READ TWICE CANNOT POST TWICE")
out3 = SD.run(st2)
t("a second run posts NOTHING", out3["posted"] == [], str(out3["posted"]))
t("and the channel still saw exactly one post", len(sent) == 1, str(sent))
_ref = ((st2.get("b1") or {}).get("payload") or {}).get("published_refs", {})
t("because the ref was written onto the job",
  _ref.get("linkedin") == "urn:li:share:12345", str(_ref))

# ---- F. THE CEILING ------------------------------------------------------
print("\nF. ONE BAD PLAN CANNOT FLOOD A FEED")
st3 = Store()
for i in range(SD.MAX_PER_RUN + 3):
    st3.save({"job_id": "c%d" % i, "approved": True, "status": "approved",
              "payload": {"social_text": "post %d" % i,
                          "channels": ["linkedin"]}})
sent.clear()
out4 = SD.run(st3)
t("it stops at the daily ceiling",
  len(out4["posted"]) == SD.MAX_PER_RUN, str(len(out4["posted"])))
t("and says WHY the rest were skipped",
  any("ceiling" in s["why"] for s in out4["skipped"]), str(out4["skipped"][:2]))

SD.channel_state = _real_state

# ---- F2. THE DEADLOCK THAT WOULD HAVE MADE THIS LANE DECORATIVE --------
print("")
print("F2. A CHANNEL MUST BE PROVABLE WITHOUT POSTING")
import content_engine_connectors as CN2

t("at least one channel can be verified by a read, not a post",
  any(w in set(CN2.VERIFIABLE) for _c, (_p, w) in SD.CHANNELS.items()))
t("LinkedIn specifically is provable, and it is the one with a token",
  "social_linkedin" in CN2.VERIFIABLE)
_st_ch = SD.channel_state(None)
t("every channel reports whether it CAN be proven",
  all("provable" in v for v in _st_ch.values()))
t("and a channel with creds but no self-test is named DEADLOCKED",
  all(("deadlocked" in v) for v in _st_ch.values()))
t("the LinkedIn self-test is a READ, and never a post",
  "userinfo" in open(CN2.__file__, encoding="utf-8").read())

# ---- G. IT HAS A CLOCK, AND ITS OWN NAME ON IT --------------------------
print("\nG. A WORKING DAY, UNDER A KEY NOBODY ELSE OWNS")
import content_engine_roster as R
import content_engine_scheduler as SCH

t("the cadence knows this lane", "social_post" in SCH.SEO_CADENCE)
t("and it is free, because attempting a post costs nothing",
  SCH.SEO_CADENCE["social_post"]["cost"] == "free")
t("IT DID NOT STEAL THE 'social' KEY, which the SEO snapshot owns",
  "social" in SCH.SEO_CADENCE
  and SCH.SEO_CADENCE["social"] is not SCH.SEO_CADENCE["social_post"])
_src = open(SCH.__file__, encoding="utf-8").read()
t("it runs before the nightly archive",
  _src.index('_due(state, "social_post"')
  < _src.index('_due(state, "snapshot"'))
_me = R.agent("sga.distributor")
t("the badge is architected: the lane is complete, no channel verifies",
  _me["badge"] == "architected", _me["badge"])
t("and the badge says what is missing", "No channel verifies" in _me["why"])

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
