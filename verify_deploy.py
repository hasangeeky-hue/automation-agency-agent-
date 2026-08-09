# -*- coding: utf-8 -*-
"""Prove the Search Intelligence OS actually landed, on the box.

Run this INSIDE the running container:

    docker compose -f deploy/docker-compose.yml exec -T api \\
        python verify_deploy.py

It renders the SEO section server-side, the same way the dashboard does,
and reports what is really there. It does not curl the site, because
curling / returns the auth wall and grepping that proves nothing: an
empty result there looks identical whether the feature shipped or not.

Exit code is 0 only if every check passes.
"""
from __future__ import annotations

import ast
import re
import sys
import traceback

FAILED = []
PASSED = []


def check(label, ok, detail=""):
    (PASSED if ok else FAILED).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))
    return ok


def head(t):
    print("\n" + t)
    print("-" * 74)


print("=" * 74)
print("SEARCH INTELLIGENCE OS + CONTENT FACTORY OS - DEPLOY VERIFICATION")
print("=" * 74)

# ---------------------------------------------------------------- modules
head("1. THE MODULES ARE IN THIS IMAGE")
MODULES = {
    "content_engine_search_loop": "the closed loop and the four domain loops",
    "content_engine_search_board": "the execution board",
    "content_engine_search_tokens": "the design tokens and the contract",
    "content_engine_search_screens": "every screen",
    "content_engine_search_data": "entities, identity, retention, CMS, reports",
    "content_engine_search_rules": "the rules and the self audit",
    "content_engine_seo_boards": "the section that assembles them",
}
mods = {}
for name, what in MODULES.items():
    try:
        mods[name] = __import__(name)
        check(name + " (" + what + ")", True)
    except Exception as exc:                          # noqa: BLE001
        check(name + " (" + what + ")", False, repr(exc)[:90])

if len(mods) < len(MODULES):
    print("\nSTOPPING: the image does not contain the new code.")
    print("The build did not pick up the new files. Rebuild with:")
    print("  docker compose -f deploy/docker-compose.yml up -d --build")
    sys.exit(1)

SEO = mods["content_engine_seo_boards"]
SS = mods["content_engine_search_screens"]
RU = mods["content_engine_search_rules"]
SL = mods["content_engine_search_loop"]
DAT = mods["content_engine_search_data"]

# ---------------------------------------------------------------- render
head("2. THE SECTION RENDERS")
section = ""
try:
    section = SEO.seo_section({}, "<div id='legacy-probe'>legacy</div>")
    check("seo_section built", True)
    print("       " + str(len(section)) + " characters")
except Exception:                                     # noqa: BLE001
    check("seo_section built", False, "raised")
    traceback.print_exc()
    sys.exit(1)


class Panels:
    """Split the assembled HTML into panels by id, count the text."""

    def __init__(self, html):
        self.ids = re.findall(r"id=['\"]([^'\"]+)", html)
        self.panels = {}
        for m in re.finditer(
                r"id=['\"](spanel-[^'\"]+)['\"](.*?)"
                r"(?=id=['\"]spanel-|$)", html, re.S):
            body = re.sub(r"<[^>]+>", " ", m.group(2))
            self.panels[m.group(1)] = len(" ".join(body.split()))


P = Panels(section)

# ---------------------------------------------------------------- tabs
head("3. EVERY TAB IS DECLARED, GROUPED AND FILLED")
tabs = [t[0] for t in SEO.TABS]
grouped = set()
for g in SEO.GROUPS:
    grouped.update(g[3])

check("twenty-five tabs are declared", len(SEO.TABS) >= 25,
      "found " + str(len(SEO.TABS)))
orphans = [t for t in tabs if t not in grouped]
check("no tab belongs to no group", not orphans, orphans)
dupes = sorted(set(x for x in P.ids if P.ids.count(x) > 1))
check("no duplicate element id on the page", not dupes, dupes)

# seosrc is the one tab NOT built from the panels dict: it carries the
# legacy Google boards, which arrive from the caller. On the live
# dashboard that is a very large block; here it is whatever probe we
# passed in. So it is checked against its own contract rather than
# against a size that would only measure our probe string.
empty = []
for t in tabs:
    if t == "seosrc":
        continue
    n = P.panels.get("spanel-" + t, 0)
    if n < 200:
        empty.append(t + "=" + str(n))
check("every engine tab renders a panel with real content", not empty,
      empty)

_src = re.search(r"id=['\"]spanel-seosrc['\"](.*?)"
                 r"(?=id=['\"]spanel-|$)", section, re.S)
check("the legacy Google boards land inside the Sources panel",
      bool(_src) and "legacy-probe" in _src.group(1),
      "panel missing" if not _src else "probe not inside it")
check("and there is exactly ONE Sources panel",
      P.ids.count("spanel-seosrc") == 1,
      str(P.ids.count("spanel-seosrc")))

# ---------------------------------------------------------------- shell
head("4. THE SHELL IS ABOVE THE TABS, NOT BEHIND ONE")
# The check whose absence is the whole reason this file exists
# in its second version: every panel was proved to HAVE
# content and none was proved to have the RIGHT content.
check("NO OLD SCREEN IS DRAWN ANYWHERE",
      "YOUR SEO AGENT" not in section)
check("the default tab is the NEW command centre",
      SEO.TABS[0][0] == "seocmd"
      and "SEARCH COMMAND CENTER" in section)
check("no tab label is double-escaped",
      "&amp;amp;" not in section)
check("the shell frame rendered", "ss-shell" in section)
check("it sits above the first tab chip",
      "ss-shell" in section and "stab-" in section
      and section.index("ss-shell") < section.index("stab-"))
check("the freshness bar rendered", "ss-bar" in section)

# ------------------------------------------------------- the new screens
head("5. THE NEW SCREENS ARE THE ONES BEING DRAWN")
MARKERS = {
    "seocmd": "SEARCH COMMAND CENTER",
    "seogeo": "LOCAL &amp; MARKETS",
    "seowork": "CONTENT BRIEF",
    "seorules": "WHAT THIS SYSTEM REFUSES TO DO",
    "seosystem": "COMPONENT LIBRARY",
    "seodata": "THE CANONICAL MODEL",
    "seoreport": "REPORTS",
    "seoloops": "THE LOOPS",
    "seofind": "COMMAND PALETTE",
    "seoanalytics": "SEARCH ANALYTICS",
    "seoagents": "AGENT CENTRE",
    "seogeoai": "AI SEARCH VISIBILITY",
    "seodomain": "DOMAIN OVERVIEW",
    "seokwx": "KEYWORD EXPLORER",
    "seorank": "POSITION TRACKING",
}
for tab, marker in MARKERS.items():
    m = re.search(r"id=['\"]spanel-" + tab + r"['\"](.*?)"
                  r"(?=id=['\"]spanel-|$)", section, re.S)
    check(tab + " draws '" + marker + "'",
          bool(m) and marker in m.group(1),
          "panel missing" if not m else "marker not in panel")

# ---------------------------------------------------------------- rules
head("6. THE OS PASSES ITS OWN AUDIT, ON THIS BOX")
try:
    aud = RU.audit()
    for x in aud["results"]:
        check(x["id"] + ": " + x["rule"], x["state"] == "HOLDS",
              x["evidence"][:80])
    check("every rule holds", aud["state"] == "ALL HOLD",
          str(aud["broken"]) + " broken")
except Exception as exc:                              # noqa: BLE001
    check("the self audit ran", False, repr(exc)[:90])

# ------------------------------------------------------------- behaviour
head("7. THE RULES BEHAVE, NOT JUST DECLARE")
try:
    check("a rate over zero impressions is None, not 0.0",
          RU.ratio([0], [0])["value"] is None)
    check("two observations is INSUFFICIENT_DATA, not NEUTRAL",
          RU.verdict(10, 10, n=2)["verdict"] == "INSUFFICIENT_DATA")
    check("EXECUTED cannot jump to SUCCESSFUL",
          "SUCCESSFUL" not in SL.MOVES.get("EXECUTED", ()))
    check("a live CMS write defaults to a dry run",
          DAT.apply_change("wordpress", "update_title", "/x", "a", "b")
          ["state"] == "DRY RUN")
    check("and needs a named approver to go live",
          DAT.apply_change("wordpress", "update_title", "/x", "a", "b",
                           dry_run=False)["state"] == "NEEDS APPROVAL")
    check("http and https are not merged into one page",
          DAT.url_identity("http://a.test/x")
          != DAT.url_identity("https://a.test/x"))
    try:
        SS.metric("x", 1)
        check("a metric with no source is refused", False, "it rendered")
    except TypeError:
        check("a metric with no source is refused", True)
except Exception as exc:                              # noqa: BLE001
    check("the behaviour checks ran", False, repr(exc)[:90])

# ------------------------------------------------------------ live data
head("8. IS REAL GOOGLE DATA REACHING THE SCREENS?")
# Reporting only. Nothing here can fail the deploy: a store that has not
# pulled yet is not a broken build. It is here so that "Search Console is
# connected but the screens are empty" is never a mystery again.
try:
    import content_engine_search_bridge as BR
    import content_engine_seo_ops as OPS
    import content_engine_api as A
    live = OPS.build_ctx(A.get_store())
    ins = (live.get("insights") or {})
    gsc, ga4 = (ins.get("gsc") or {}), (ins.get("ga4") or {})
    print("       last Google pull: " + str(ins.get("at") or "never"))
    print("       Search Console: "
          + (str(len(gsc.get("queries") or [])) + " queries, "
             + str(len(gsc.get("daily") or [])) + " days"
             if gsc else "NO DATA IN THE STORE"))
    _chan = [str((c or {}).get("sessionDefaultChannelGroup") or "?")
             for c in (ga4.get("channels") or [])]
    print("       GA4: " + ("connected, channels: "
                            + (", ".join(_chan) or "none")
                            if ga4 else "NO DATA IN THE STORE"))
    print("       rank tracker rows: " + str(len(live.get("ranks") or [])))
    print("")
    fed = BR.enrich(live)
    for key in BR.MAPPING:
        val = fed.get(key)
        if val in (None, {}, [], "manual"):
            print("       -- " + key.ljust(18)
                  + "no data yet; the screen will say what is missing")
        else:
            size = (str(len(val)) + " row(s)"
                    if isinstance(val, list) else
                    str(len(val)) + " field(s)"
                    if isinstance(val, dict) else str(val))
            print("       OK " + key.ljust(18) + size)
    tot = fed.get("search_totals") or {}
    if tot.get("clicks") is not None:
        print("")
        print("       Search totals now on the command screen: "
              + str(tot.get("clicks")) + " clicks, "
              + str(tot.get("impressions")) + " impressions, CTR "
              + str(tot.get("ctr")) + "%, avg position "
              + str(tot.get("position")) + " (impression-weighted)")
        if tot.get("sessions") is not None:
            print("       Organic sessions from GA4: "
                  + str(tot.get("sessions")))
        else:
            print("       Organic sessions: NOT AVAILABLE")
            print("       reason: " + str(tot.get("sessions_note")))
except Exception as exc:                              # noqa: BLE001
    print("       could not read the live store: " + repr(exc)[:100])
    print("       (this is not a deploy failure; the code still shipped)")

# ----------------------------------------------------------- ai engines
head("9. WHICH AI ENGINES ARE WIRED FOR AI-VISIBILITY PROBES?")
# Presence only. The VALUE of a key is never read, printed or stored:
# whether the variable is non-empty answers the whole question, and
# printing a key into a terminal would put it in shell history.
try:
    import content_engine_aeo as AEO
    for _name, _fn, _key in AEO._ENGINES:
        # Same resolver the call uses: settings-first, then environment.
        # os.getenv alone printed "ABSENT" beside eighteen recorded
        # answers, because the key was on the Connect board.
        _has = AEO._key_present(_key)
        _impl = callable(getattr(AEO, _fn, None))
        print("       " + _name.ljust(12)
              + ("key SET   " if _has else "key ABSENT")
              + ("  probe implemented" if _impl
                 else "  *** NO PROBE FUNCTION ***"))
    _aeo = (live.get("aeo") or {}) if "live" in dir() else {}
    _res = _aeo.get("results") or []
    print("")
    print("       last AI probe run: " + str(_aeo.get("at") or "never"))
    print("       prompts observed: " + str(len(_res)))
    if _res:
        _by = {}
        for _r in _res:
            for _n, _f2, _k2 in AEO._ENGINES:
                _e = (_r or {}).get(_n) or {}
                if _e.get("connected"):
                    _by[_n] = _by.get(_n, 0) + 1
        print("       answers recorded per engine: "
              + (", ".join(k + "=" + str(n) for k, n in _by.items())
                 or "none"))
        for _r in _res[:1]:
            for _n, _f2, _k2 in AEO._ENGINES:
                _e = (_r or {}).get(_n) or {}
                if not _e.get("connected") and _e.get("reason"):
                    print("       " + _n + ": " + str(_e.get("reason"))[:96])
    else:
        print("       nothing probed yet. Use 'Probe AI answers' on the "
              "SEO section, or run the AEO engine.")
except Exception as exc:                              # noqa: BLE001
    print("       could not read the AI engines: " + repr(exc)[:100])

# ------------------------------------------------------ content factory
head("10. THE CONTENT FACTORY OS")
try:
    import content_engine_factory_agents as FA
    import content_engine_factory_os as FOS
    import content_engine_factory_screens as CFS
    import content_engine_factory_ui as CFU
    import content_engine_factory_boards as CFB

    check("the four factory modules are in this image", True)
    _cs = CFU.check_screens()
    check("nine screens, each with a renderer and a contract",
          _cs["ok"], str(_cs["problems"]))
    check("the old boards module is a shim over the new OS",
          "content_engine_factory_ui" in
          open("content_engine_factory_boards.py",
               encoding="utf-8").read())
    check("the dashboard's entry point still resolves",
          callable(CFB.factory_section))

    _fsec = CFB.factory_section({})
    check("the factory section renders", len(_fsec) > 5000,
          str(len(_fsec)) + " chars")
    print("       " + str(len(_fsec)) + " characters")

    _fids = re.findall(r"id=['\"]([^'\"]+)", _fsec)
    check("no duplicate element id in the factory",
          not [x for x in set(_fids) if _fids.count(x) > 1],
          str(sorted({x for x in _fids if _fids.count(x) > 1})))

    _fempty = []
    for _sid, _n, _lab, _fn, _q in CFU.SCREENS:
        _m = re.search(r"id=['\"]cfpanel-" + _sid + r"['\"](.*?)"
                       r"(?=id=['\"]cfpanel-|$)", _fsec, re.S)
        _txt = re.sub(r"<[^>]+>", " ", _m.group(1)) if _m else ""
        if len(" ".join(_txt.split())) < 100:
            _fempty.append(_sid)
    check("every one of the nine panels renders real content",
          not _fempty, str(_fempty))
    check("no factory screen raised into its panel",
          "could not render" not in _fsec)

    # The boundary, checked against the running code.
    check("paid creative is addressed to the MEDIA BUYING OS",
          FOS.DESTINATIONS["META_PAID"][0] == "MEDIA_BUYING_OS")
    check("blog goes to the SEO OS, email to the Email OS",
          FOS.DESTINATIONS["BLOG"][0] == "SEO_OS"
          and FOS.DESTINATIONS["EMAIL"][0] == "EMAIL_OS")
    check("there are exactly four agents", len(FA.AGENTS) == 4,
          str(len(FA.AGENTS)))
    check("no agent may approve, distribute or publish",
          all(not FA.guard(a, act)["ok"] for a in FA.AGENTS
              for act in ("approve_content", "distribute_content",
                          "publish_content")))
    check("an agent cannot edit a locked block",
          FOS.apply_block_edit(
              [FOS.block("HEADLINE", "x", id="b", locked=True)],
              "b", "y", actor="AGENT")["state"] == "LOCKED")
    check("approval needs a human AND a named approver",
          FOS.transition("REVIEW", "APPROVED", actor="AGENT",
                         approver="x")["ok"] is False
          and FOS.transition("REVIEW", "APPROVED",
                             actor="HUMAN")["ok"] is False
          and FOS.transition("REVIEW", "APPROVED", actor="HUMAN",
                             approver="Murtuja")["ok"] is True)
    check("AI_GENERATED is not a content state",
          "AI_GENERATED" not in FOS.CONTENT_STATUS)
    check("unapproved content cannot be handed off",
          FOS.build_package({"id": "v", "channel": "META_PAID",
                             "status": "REVIEW"},
                            approval={"approved_by": "x"})["ok"] is False)
    check("ACCEPTED is reported as SENT, never PUBLISHED",
          FOS.receive_handoff_result({}, {"state": "ACCEPTED"})["state"]
          == "SENT")
    check("WINNER needs a baseline and enough sample",
          FOS.classify_result({"ctr": 0.9, "impressions": 40},
                              metric="ctr",
                              baseline=0.02)["result"]
          == "INSUFFICIENT_DATA")
    check("a rate over a zero denominator is None, not 0.0",
          FOS.rate(5, 0) is None)
    check("exhausting an agent budget escalates and does NOT retry",
          FA.spend(FA.new_run("CREATOR", "x"),
                   steps=99)["state"] == "NEEDS_HUMAN")
    check("no while loop exists in the agent module",
          not [n for n in ast.walk(ast.parse(open(
              "content_engine_factory_agents.py",
              encoding="utf-8").read())) if isinstance(n, ast.While)])

    # What the factory is holding right now, if a store is reachable.
    print("")
    try:
        _fl = FOS.loop_state({})
        print("       factory loop: " + _fl["state"])
        print("       " + _fl["why"][:150])
    except Exception:                                 # noqa: BLE001
        pass
    _caps = [c for c in FOS.tool_matrix() if c.get("mvp")]
    for _c in _caps:
        print("       " + _c["capability"].ljust(18)
              + _c["state"].ljust(18) + _c["why"][:60])
except Exception as exc:                              # noqa: BLE001
    check("the Content Factory OS loaded", False, repr(exc)[:110])

# ---------------------------------------------------------------- verdict
print("\n" + "=" * 74)
if FAILED:
    print("DEPLOY NOT VERIFIED: " + str(len(FAILED)) + " check(s) failed, "
          + str(len(PASSED)) + " passed.")
    print("")
    for f in FAILED:
        print("  FAILED: " + f)
    print("")
    print("If the modules imported but panels are empty, the image is")
    print("older than the code. Rebuild, do not just restart:")
    print("  docker compose -f deploy/docker-compose.yml up -d --build")
    print("=" * 74)
    sys.exit(1)

print("DEPLOY VERIFIED on this box.")
print("  " + str(len(PASSED)) + " checks passed, 0 failed.")
print("  " + str(len(SEO.TABS)) + " tabs, "
      + str(len(SEO.GROUPS)) + " groups, "
      + str(len(section)) + " characters of section.")
print("  " + str(len(RU.RULES)) + " rules hold against the running code.")
print("")
print("Open the dashboard, go to the SEO section, and use the")
print("'Rules & Self Audit' tab. It runs these same checks in the browser.")
print("=" * 74)
sys.exit(0)
