# -*- coding: utf-8 -*-
"""AGENT OS GATE: the wireframe, recreated and actually bound.

Definition of done (Section 6, P5):
  - 0 unbound interactive elements on shipped screens
  - badges, cards and the registry all come from endpoints
  - source chips render

This gate asserts against the ASSEMBLED PAGE, not against the module that
produces the section. A correct section can still be dropped into a page
with its stylesheet missing, its handlers missing, or old markup appended
after it, and every one of those has happened in this project.
"""
from __future__ import annotations

import re
import sys

import content_engine_contracts as C
import content_engine_dashboard as D
import content_engine_agentos as OS
import content_engine_os_kit as K
import content_engine_roster as R

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


class Store:
    def __init__(self):
        self.d = {"BRAND_NAME": "acme"}

    def get_setting(self, k, default=None):
        return self.d.get(k, default)

    def set_setting(self, k, v):
        self.d[k] = v

    def list_jobs(self, status=None):
        return []

    def daily_cost(self):
        return 0.0

    def monthly_cost(self):
        return 0.0


print("=" * 74)
print("AGENT OS - TURN 13 AND TURN 14")
print("=" * 74)

st = Store()
# st is the CONNECTOR STATUS DICT, not a store. The context is built
# from the store separately, exactly as the API does it.
html = D.dashboard_html(jobs=[], st={}, health={}, month_spent=0.0,
                        month_cap=200.0, day_spent=0.0, day_cap=10.0,
                        taste_skills=[], os_ctx=OS.build_ctx(st))
styles = "".join(re.findall(r"<style>(.*?)</style>", html, re.S))

# ---- A. EVERY DECLARED SCREEN IS ON THE ASSEMBLED PAGE -------------------
print("\nA. SIXTEEN SCREENS, ON THE REAL PAGE")
t("the Agent OS did not fall back to its error card",
  "Agent OS screens failed" not in html)
missing = [s for s in OS.SCREENS_13 + OS.SCREENS_14
           if ("id='os-%s'" % s) not in html]
t("all 16 screens render", not missing, str(missing))
dupes = [s for s in OS.SCREENS_13 + OS.SCREENS_14
         if html.count("id='os-%s'" % s) > 1]
t("and NONE is rendered twice", not dupes, str(dupes))
t("turn 13 has its eleven", len(OS.SCREENS_13) == 11, str(len(OS.SCREENS_13)))
t("turn 14 has its five", len(OS.SCREENS_14) == 5, str(len(OS.SCREENS_14)))

# ---- B. IT IS REACHABLE -------------------------------------------------
print("\nB. THE FOUNDER CAN GET TO IT")
t("the cockpit has a nav link", "id='nav-oscockpit'" in html)
t("the core has a nav link", "id='nav-oscore'" in html)
t("both are real page sections",
  "id='sec-oscockpit'" in html and "id='sec-oscore'" in html)
t("exactly one nav link is marked active",
  html.count("class='navb act'") == 1, str(html.count("class='navb act'")))
_first = re.search(r"class='navb act' id='nav-([a-z]+)'", html)
t("and the active link is the page that is open",
  bool(_first) and ("id='sec-%s' " % _first.group(1) in html
                    or "class='page on' id='sec-%s'" % _first.group(1) in html),
  _first.group(1) if _first else "no active link")

# ---- C. NOTHING IS UNSTYLED (the rehoming lesson, three times over) -----
print("\nC. THE MARKUP TRAVELLED WITH ITS STYLESHEET")
osx = html[html.find("<div class='osx'>"):]
used = set()
for m in re.finditer(r"class='(ox-[^']*)'", osx):
    used.update(c for c in m.group(1).split() if c.startswith("ox-"))
unstyled = sorted(c for c in used if ("." + c) not in styles)
t("every ox- class the screens emit has a CSS rule", not unstyled,
  str(unstyled))
t("the kit stylesheet is on the page", ".osx .ox-bp" in styles)
t("and it declares its own tokens rather than inheriting the shell's",
  "--ox-ac:#5980a6" in styles)

# ---- D. NO DEAD BUTTONS (the audit_buttons class) -----------------------
print("\nD. EVERY CONTROL DOES SOMETHING")
handlers = set(re.findall(r"onclick=\"(os\w+)\(", html))
handlers |= set(re.findall(r"Enter'\)(os\w+)\(", html))
dead = sorted(h for h in handlers if ("function " + h) not in html)
t("every OS handler used is defined", not dead, str(dead))
t("the kit's script block shipped", "function osSend" in html)
for fn in ("osSend", "osApprove", "osReject", "osPrefill", "osSaveKey"):
    t("  %s is defined" % fn, ("function %s" % fn) in html)

# ---- E. THE COMMAND BAR PROPOSES. IT NEVER EXECUTES. --------------------
print("\nE. A COMMAND IS A PROPOSAL, NOT AN ACTION (10.4)")
t("the bar posts to the proposal route", "'/proposal'" in K.JS)
t("a PINK action refuses to approve from the panel",
  "if(pink)" in K.JS and "module gate" in K.JS)
t("there is no free-form chat loop in v1",
  "transcript" not in K.JS.lower() and "/chat" not in K.JS)
t("input reaches the engine as JSON for the safety layer to clean",
  "JSON.stringify" in K.JS)

# ---- F. BADGES AND NUMBERS COME FROM THE ENGINE -------------------------
print("\nF. NOTHING ON SCREEN IS HAND-SET")
t("the kit's badge vocabulary equals the contract's",
  set(K.BADGE_LABEL) == set(C.BADGES))
t("the kit's status vocabulary equals the contract's",
  set(K.STATUS_LABEL) == set(C.CONNECTOR_STATES))
kc = K.check()
t("and the kit's own check passes", kc["ok"], str(kc["problems"]))
t("every roster employee has a card on the all-agents grid",
  all(("<div class='ox-ac-id'>%s</div>" % a["id"]) in html
      for a in R.roster()),
  str([a["id"] for a in R.roster()
       if ("<div class='ox-ac-id'>%s</div>" % a["id"]) not in html]))
t("source chips render", "class='ox-src'" in html)
t("a number with no source is marked as such, not left bare",
  "ox-src-none" in K.CSS)

# ---- G. THE HONESTY RULES, ON SCREEN ------------------------------------
print("\nG. THE SCREENS CANNOT LIE")
t("creds-present renders amber and says why",
  "ox-s-present" in styles and "amber" in html.lower())
t("decision and blocked are two separate lists",
  "Your decision" in html and "Blocked, not yours to approve" in html)
t("the five permanent gates are named",
  all(g in html for g in ("SPEND", "PUBLISH", "SEND", "DEPLOY",
                          "CROSS-MODULE COMMAND")))
t("the Developer desk is refused out loud, not quietly skipped",
  "id='os-13d'" in html and "cannot make safe" in html)
t("a desk with no employee shows no numbers",
  "Nothing is shown here because nothing produces it" in html)
t("the hub asks for the keys the endpoint accepts, not wire names",
  "oskey-ANTHROPIC_API_KEY" in html)
t("and it warns that a saved key is still not a working key",
  "still amber" in html or "stays amber" in html)

# ---- H. THE FOUNDER'S OWN RULE ------------------------------------------
print("\nH. NO EM-DASHES ANYWHERE IN THE OS")
bad = [n for n, src in (("kit", K.CSS + K.JS),
                        ("core", OS.core_section(OS.build_ctx(st))
                         + OS.cockpit_section(OS.build_ctx(st))))
       if "—" in src or "&mdash;" in src]
t("the OS ships no em-dash", not bad, str(bad))

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
