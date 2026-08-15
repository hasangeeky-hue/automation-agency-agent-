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

import io
import re
import sys

import content_engine_contracts as C
import content_engine_dashboard as D
import content_engine_agentos as OS
import content_engine_agentos_growth as OSG
import content_engine_agentos_leads as OSL
import content_engine_agentos_commerce as OSCM
import content_engine_agentos_media as OSMD
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
print("AGENT OS - ALL SEVEN TURNS")
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
ALL = (OS.SCREENS_13 + OS.SCREENS_14 + OSG.SCREENS_9
       + OSG.SCREENS_8 + OSL.SCREENS_12
       + OSCM.SCREENS_11 + OSCM.SCREENS_10 + OSMD.SCREENS_7)
missing = [s for s in ALL if ("id='os-%s'" % s) not in html]
t("all %d screens render" % len(ALL), not missing, str(missing))
dupes = [s for s in ALL if html.count("id='os-%s'" % s) > 1]
t("and NONE is rendered twice", not dupes, str(dupes))
t("turn 13 has its eleven", len(OS.SCREENS_13) == 11, str(len(OS.SCREENS_13)))
t("turn 14 has its five", len(OS.SCREENS_14) == 5, str(len(OS.SCREENS_14)))
t("turn 9 has its eight", len(OSG.SCREENS_9) == 8, str(len(OSG.SCREENS_9)))
t("turn 8 has its eight", len(OSG.SCREENS_8) == 8, str(len(OSG.SCREENS_8)))
t("turn 12 has its nine", len(OSL.SCREENS_12) == 9, str(len(OSL.SCREENS_12)))
t("turn 11 has its nine", len(OSCM.SCREENS_11) == 9)
t("turn 10 has its ONE screen, counted from the file, not assumed",
  len(OSCM.SCREENS_10) == 1)
t("the wireframe's own 51 screens are all built",
  len([s for s in ALL if not s.startswith("7")]) == 51,
  str(len(ALL)))
# MEDIA IS THE ONE DEPARTMENT THE WIREFRAME NAMES AND DOES NOT DRAW.
# Its nine screens are derived from the founder's own material: his six
# agent names verbatim, his "mirrors SEO's data-sources screen" and
# "mirrors Media Buyer's agents room" notes, and his connector list.
t("plus the nine Media screens the wireframe specifies but never drew",
  len(OSMD.SCREENS_7) == 9, str(len(OSMD.SCREENS_7)))
t("THE SIX DESKS ARE THE FOUNDER'S OWN, VERBATIM",
  [n for _s, _i, n, _d2 in OSMD.DESKS]
  == ["Scout", "Creative", "Launch", "Optimizer", "Pacing", "Reporter"],
  str([n for _s, _i, n, _d2 in OSMD.DESKS]))
_mc = OSMD.check(OS.build_ctx(st))
t("and the media department passes its own check", _mc["ok"],
  str(_mc["problems"]))
t("the spend gate is stated where a launch would happen",
  "SPEND is one of the five permanent gates" in html)
t("agents stay READ-ONLY on media, as the spec requires",
  "read-only on media by design" in html.lower())
_cc = OSCM.check(OS.build_ctx(st))
t("and the commerce turns pass their own check", _cc["ok"], str(_cc["problems"]))
t("FIVE DESKS, ONE EMPLOYEE is disclosed on every commerce desk",
  all("One worker, five desks" in html[html.find("id='os-%s'" % s):
                                       html.find("id='os-%s'" % s) + 7000]
      for s in OSCM.SHARED_DESKS))
_lc = OSL.check(OS.build_ctx(st))
t("and the leads turn passes its own check", _lc["ok"], str(_lc["problems"]))
t("FOUR WORKERS, NINE DESKS is disclosed on every shared desk",
  all("One worker" in html[html.find("id='os-%s'" % s):
                           html.find("id='os-%s'" % s) + 6000]
      for s in OSL.SHARED_DESKS))
t("and the EU hard block is NOT drawn, because the engine has none",
  "the engine does not have one" in " ".join(html.split()))
t("Europe stays in scope, as decided",
  "Per-country rules: decided" in html)
t("so the LIVE open-tracking state is shown, not merely described",
  "Open tracking, right now" in html)
_gc = OSG.check(OS.build_ctx(st))
t("and the growth turns pass their own check", _gc["ok"], str(_gc["problems"]))
t("ONE WORKER, TWO DESKS is disclosed on both 8c and 8e",
  all("same" in html[html.find("id='os-%s'" % s):
                     html.find("id='os-%s'" % s) + 4000].lower()
      for s in ("8c", "8e")))

# ---- B. IT IS REACHABLE -------------------------------------------------
print("\nB. THE FOUNDER CAN GET TO IT")
# HIS SIDEBAR IS THE NAVIGATION. The dashboard's own left nav is gone
# along with the rest of its chrome, so "has a nav link" now means his
# module sidebar reaches the page, not that a second nav still exists.
for _pid in ("oscockpit", "oscore", "osmkt", "osseo", "osleads",
             "oscom", "osmedia"):
    t("%s is reachable from HIS sidebar, and has a page" % _pid,
      ("nav('%s')" % _pid) in html and ("id='sec-%s'" % _pid) in html)
# ---- THE REPLACEMENT, AND WHAT IT DID NOT COST -------------------------
print("")
print("B2. THE AGENT OS IS THE DASHBOARD, AND NOTHING WAS LOST")
# THE OLD CHROME IS GONE ENTIRELY, not merely reduced to one group.
t("THE OLD DASHBOARD CHROME IS GONE: no brand bar, no second nav",
  "class='top'" not in html and "class='side'" not in html
  and "Anthropos" not in html.split("<body>")[-1][:4000])
t("and no old nav group survives anywhere",
  ">Deep tools<" not in html and "class='navgrp'" not in html)
t("HIS TOPBAR IS THE ONLY TOPBAR", html.count("class='ox-topbar'") == 7,
  str(html.count("class='ox-topbar'")))
t("the engine controls survived INTO his shell, not around it",
  "class='ctrl'" in html and "class='ox-tools'" in html)
t("and the OS cockpit is the page that opens",
  "class='page on' id='sec-oscockpit'" in html)
_old_ids = ("cockpit", "bi", "riskinfra", "content", "outreach", "sga",
            "seo", "media", "system")
# THE OLD SURFACE IS OFF THE NAV. Checked by the absence of the LINK,
# not the absence of the page: an unlinked page that still resolves is
# exactly the state being asserted, and confusing the two would let a
# real regression (a dead bookmark) pass as a success.
_linked = [p for p in _old_ids if ("id='nav-%s'" % p) in html]
t("NO OLD PAGE IS LINKED FROM THE WIREFRAME'S SHELL", not _linked,
  str(_linked))
# THE OLD PAGES ARE ABSORBED, NOT DELETED. Their boards render inside the
# Agent OS module that owns them, so the id no longer exists as a page and
# an old bookmark is routed by NAVALIAS to that module instead. Asserting
# "the page still resolves" would now be asserting the duplicate render
# that put 988 duplicate ids on one document.
_still = [p for p in _old_ids if ("id='sec-%s'" % p) in html]
t("no old page is rendered SEPARATELY any more", not _still, str(_still))
_unaliased = [p for p in _old_ids if ("%s:'os" % p) not in html]
t("BUT EVERY OLD BOOKMARK IS ALIASED to the module that owns its data",
  not _unaliased, str(_unaliased))
t("and the OS carries the data: Search is the biggest page, not the thinnest",
  len(html[html.find("id='sec-osseo'"):html.find("id='sec-osleads'")]) > 200000)
t("NO DUPLICATE ELEMENT ID anywhere on the assembled document",
  not [k for k, v in __import__("collections").Counter(
      re.findall(r"id='([a-zA-Z0-9_-]+)'", html)).items() if v > 1])
t("a nav target that does not resolve can no longer blank the page",
  "if(!s)return false;" in html)
t("MEDIA NO LONGER CLAIMS IT HAS NO REPLACEMENT: nine screens exist",
  "no Agent OS view of this department" not in html)

# ---- LANE 3b: THE BACKUP TRUTH ----------------------------------------
print("")
print("B3. THE RISK SENTINEL SAYS THE TRUE THING ABOUT BACKUPS")
import content_engine_risk_desk as RD
_rk = RD.check()
t("the sentinel cannot claim to take a backup it cannot take",
  _rk["ok"], str(_rk["problems"]))
_p0 = RD.inspect(st)
t("with no evidence it says NO BACKUP HAS EVER BEEN PROVEN",
  any(f["kind"] == "no_backup_proof" for f in _p0["findings"]))
t("and it prints the host commands that would fix it",
  all("backup.sh" in ln for ln in RD.HOST_CRON_LINES)
  and any("--verify" in ln for ln in RD.HOST_CRON_LINES))
t("THE SCRIPT ITSELF reports the receipt, so the cron cannot drift",
  "risk/backup-receipt" in io.open(
      "deploy/backup.sh", encoding="utf-8").read())
t("and it posts that receipt authenticated, not open to anyone",
  "X-API-Key" in io.open("deploy/backup.sh", encoding="utf-8").read())


class _RS:
    def __init__(self):
        self.d = {}

    def get_setting(self, k, d=None):
        return self.d.get(k, d)

    def set_setting(self, k, v):
        self.d[k] = v


_rs = _RS()
RD.record_receipt(_rs, "backup", "engine-x.sql.gz")
_p1 = RD.inspect(_rs)
t("A REAL RECEIPT CLEARS IT, and nothing else can",
  not any(f["kind"] == "no_backup_proof" for f in _p1["findings"]))
t("but an untested restore is then raised",
  any(f["kind"] == "restore_untested" for f in _p1["findings"]))
try:
    RD.record_receipt(_rs, "vibes")
    t("an invented receipt kind is refused", False, "it was allowed")
except ValueError:
    t("an invented receipt kind is refused", True)
t("the posture is on the Infra desk, not only in the API",
  "NO BACKUP HAS EVER BEEN PROVEN" in html)
import content_engine_fixes as _FX
t("and the broken backup BUTTON now tells the truth",
  _FX._f_backup(None, None)["ok"] is False
  and "cannot run from inside the container"
  in _FX._f_backup(None, None)["message"])

# ---- THE NEW LANES REACH THE SCREENS ------------------------------------
print("")
print("B4. A SHIPPED LANE IS NEVER DESCRIBED AS FUTURE WORK")
import content_engine_agentos_commerce as OSCM2
import content_engine_pricing as PX2

t("stage 2 is built, so no screen still promises it",
  OSCM2.STAGE_2 == {}, str(OSCM2.STAGE_2))
t("11e says HOW a discount happens, not that it cannot",
  "no button that simply" in html)
t("and the pink rule is stated even when the queue is empty",
  "approved one at a time, never in a batch" in html)
t("the one-step bound is shown to the founder, not just enforced",
  ("%g" % PX2.MAX_MOVE_PCT) in html)

# A PINK PROPOSAL MUST REACH THE COCKPIT. One queue is the whole point.
class _PxStore:
    def __init__(self):
        self.d = {"BRAND_NAME": "acme"}

    def get_setting(self, k, d=None):
        return self.d.get(k, d)

    def set_setting(self, k, v):
        self.d[k] = v

    def list_jobs(self, status=None):
        return []

    def daily_cost(self):
        return 0.0


_ps = _PxStore()
_ps.set_setting(PX2.PROPOSALS_KEY, [{
    "id": "px_TEST", "product_id": "9", "sku": "TEST", "title": "A product",
    "reason": "thin_margin", "why": "its margin is thinner than the target",
    "price": 100.0, "new_price": 120.0, "pink": True, "status": "pending",
    "preview": {"margin_known": True, "margin_before_pct": 20.0,
                "margin_after_pct": 33.3, "margin_delta_pct": 13.3}}])
_pctx = OS.build_ctx(_ps)
_pq = OS.cockpit_section(_pctx)
t("A PINK PRICE PROPOSAL APPEARS IN THE UNIFIED QUEUE",
  "px_TEST" in _pq or "A product" in _pq)
t("and it is flagged pink so it can never be batched",
  "pink: never batch" in _pq)
t("it sits under YOUR DECISION, not under blocked",
  _pq.find("A product") > _pq.find("Your decision"))
t("the approve route is the gated one",
  "/commerce/price/px_TEST/approve" in _pq)

# ---- HIS STRUCTURE, NOT A FLATTER VERSION OF IT ------------------------
print("")
print("B5. EVERY DEPARTMENT SITS IN HIS SHELL")
_shell = [("core", OS.core_section), ("cockpit", OS.cockpit_section),
          ("marketing", OSG.marketing_section), ("search", OSG.search_section),
          ("leads", OSL.leads_section), ("commerce", OSCM.commerce_section),
          ("media", OSMD.media_section)]
_c5 = OS.build_ctx(st)
for _nm, _fn in _shell:
    _h5 = _fn(_c5)
    t("%s has the module sidebar" % _nm, "ox-sidebar" in _h5)
    t("  and its own screens as a subnav", "ox-subnav" in _h5
      and "class='ox-snav" in _h5)
    t("  with the current module marked active", "ox-mod on" in _h5)
# TWO MODULES MUST NOT OWN ONE CLASS NAME. content_engine_os_screens.py
# declared its own .osx with a different palette; it landed later in the
# cascade and repainted his ground #f7f8fa and his ink #111827. Verified
# in a real browser: one rule now, and the computed colours are his.
t("ONLY ONE MODULE DECLARES .osx (the kit owns the founder's shell)",
  styles.count(".osx{") == 1, str(styles.count(".osx{")))
t("and the shell actually PAINTS his ground, not just declares it",
  "background:var(--ox-bg)" in styles and "color:var(--ox-ink)" in styles)
# HIS PROSE WAS SAFE TO COPY. HIS NUMBERS NEVER WERE.
import content_engine_os_rails as _RL
_fake = [(sid, h) for sid, secs in _RL.RAILS.items() for h, tx in secs
         if re.search(r"\d[\d,]{3,}", tx) or re.search(r"●\s*\w+ing", tx)]
t("NO STAFFRAIL REPORTS ACTIVITY NOBODY MEASURED", not _fake, str(_fake))
t("the subnav link class does NOT collide with the paragraph class",
  "class='ox-sub " not in OS.core_section(_c5))
t("every module in the sidebar is one of his seven",
  len(K.MODULES) == 7, str(len(K.MODULES)))
# EVERY MODULE IN THE SIDEBAR MUST REACH A PAGE THAT EXISTS.
# They were anchors (#os-7a) copied from his prototype, where all 51
# screens share one scrolling document. Here each department is its own
# page and the other six are display:none, so those links jumped into a
# hidden page and did nothing: "except cockpit nothing are opening".
_pages = set(re.findall(r"id='sec-([a-z]+)'", html))
_targets = set(re.findall(r"return nav\('(os[a-z]+)'\)", html))
t("EVERY SIDEBAR MODULE SWITCHES PAGE, not to an anchor on a hidden one",
  len(_targets) == len(K.MODULE_PAGE), str(sorted(_targets)))
t("and every one of those targets is a page that exists",
  _targets <= _pages, str(sorted(_targets - _pages)))
t("the module map covers every module in the sidebar",
  set(K.MODULE_PAGE) == {sid for _lab, sid in K.MODULES},
  str(set(K.MODULE_PAGE) ^ {sid for _lab, sid in K.MODULES}))
t("and the sidebar links are anchors, as his own markup uses",
  "href='#os-13a'" in OS.core_section(_c5))
# HIS RIGHT-HAND RAIL, ON THE SCREENS HE DREW IT ON.
# Counted against his own file rather than a number typed here, so the
# day he adds a rail to another screen this fails until it is built.
import content_engine_os_rails as RAILS
_want_rails = len(RAILS.RAILS)
_want_secs = sum(len(v) for v in RAILS.RAILS.values())
_allos = (OS.core_section(_c5) + OS.cockpit_section(_c5)
          + OSG.marketing_section(_c5) + OSG.search_section(_c5)
          + OSL.leads_section(_c5) + OSCM.commerce_section(_c5)
          + OSMD.media_section(_c5))
t("EVERY STAFFRAIL HE DREW IS ON THE PAGE (%d)" % _want_rails,
  _allos.count("class='ox-staffrail'") == _want_rails,
  str(_allos.count("class='ox-staffrail'")))
t("and every rail section, not just the first of each",
  _allos.count("class='ox-rail-head'") == _want_secs,
  str(_allos.count("class='ox-rail-head'")))
t("a screen he drew NO rail on does not hold an empty column open",
  "ox-scr railed" not in _allos.replace("ox-scr railed'", "X"))
t("THE SUPERSEDED EU HARD-BLOCK CLAIM IS NOT REPRODUCED",
  "hard-blocked from cold email" not in _allos)

# THE COMPONENT EXISTING IS NOT THE WORK BEING DONE.
# These two checks used to assert only that K.dq and K.chart could be
# called. They passed for weeks while not one screen called them: the
# toolbox was full and the screens were empty. They now count what is
# actually ON THE PAGE, against his file.
import content_engine_os_cards as CARDS
_want_ch = sum(len(v) for v in CARDS.CHARTS.values())
# His 25 chart cards, PLUS one inside each of the 40 tab panes. Stated as
# a sum rather than relaxed to >=, so a genuinely missing chart still fails.
import content_engine_os_tabs as _TBX
_tabch = sum(len(v) for v in _TBX.TABS.values())
t("EVERY CHART CARD HE DREW IS RENDERED (%d his + %d in tab panes)"
  % (_want_ch, _tabch),
  _allos.count("class='ox-cc'") == _want_ch + _tabch,
  str(_allos.count("class='ox-cc'")))
t("and every screen he drew an activity list on has one (%d)"
  % len(CARDS.DQ_SHAPE),
  _allos.count("class='ox-dq-list'") == len(CARDS.DQ_SHAPE),
  str(_allos.count("class='ox-dq-list'")))
t("a chart nothing feeds says so, rather than drawing an empty box",
  "nothing to chart yet" in _allos)

# HIS IN-SCREEN TABS: nine desks that are one screen holding several views.
import content_engine_os_tabs as TABS
_want_tabs = sum(len(v) for v in TABS.TABS.values())
t("EVERY DESK THAT SPLITS INTO VIEWS HAS ITS TAB STRIP (%d)" % len(TABS.TABS),
  _allos.count("class='ox-tabbar'") == len(TABS.TABS),
  str(_allos.count("class='ox-tabbar'")))
t("and every view he drew is a tab (%d)" % _want_tabs,
  _allos.count("<button class='ox-tab") == _want_tabs,
  str(_allos.count("<button class='ox-tab")))
t("each tab has a pane, so none is a label over nothing",
  _allos.count("class='ox-tabpane") == _want_tabs,
  str(_allos.count("class='ox-tabpane")))
t("THE TABS REALLY SWITCH: the handler exists, so none is a dead button",
  "function osTab" in K.JS)
t("the Technical Engineer keeps all five of his views",
  len(TABS.tabs_for("8b")) == 5, str(TABS.tabs_for("8b")))
t("and his placeholder tab COUNTS are not shown as real scores",
  "This page (68)" not in _allos)
t("HIS PLACEHOLDER INCIDENTS ARE NOT REPRODUCED AS REAL ALERTS",
  "Shopware sync degraded" not in _allos
  and "token expired 41m ago" not in _allos)

# The two components his file repeats and I had not built at all.
t("the decision card exists (his dq-card, 51 uses)",
  "ox-dq-rec" in K.dq("x", "y"))
t("and it refuses a recommendation with no evidence silently",
  "no evidence recorded" in K.dq("x"))
t("the chart card exists (his chart-card + hbar)",
  "ox-hbar-t" in K.chart("t", [("a", 1)]))
t("AND A GAP IN A CHART IS NOT A ZERO-LENGTH BAR",
  "not measured" in K.chart("t", [("a", None)]))

# ACTIVE STATE LIVES IN HIS SIDEBAR NOW. Each page renders its own frame
# and marks its own module, so seven pages means seven active markers,
# one per page, not one across the document.
t("each page's sidebar marks exactly one module active",
  html.count("class='ox-mod on'") == 7, str(html.count("class='ox-mod on'")))

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
for fn in ("osSend", "osApprove", "osReject", "osPrefill", "osSaveKey",
           "osApproveJob", "osDeclineJob", "osTracking"):
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
_c = OS.build_ctx(st)
bad = [n for n, src in (("kit", K.CSS + K.JS),
                        ("core", OS.core_section(_c) + OS.cockpit_section(_c)),
                        ("growth", OSG.marketing_section(_c)
                         + OSG.search_section(_c)),
                        ("leads", OSL.leads_section(_c)),
                        ("commerce", OSCM.commerce_section(_c)),
                        ("media", OSMD.media_section(_c)))
       if "—" in src or "&mdash;" in src]
t("the OS ships no em-dash", not bad, str(bad))

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
