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
print("SEARCH + FACTORY + BI + CONTROL PLANE + COCKPIT - DEPLOY VERIFICATION")
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

# ------------------------------------------------------ cost-aware BI
head("11. THE COST-AWARE BI OS")
try:
    import content_engine_bi_cost as BC
    import content_engine_bi_economics as BE
    import content_engine_bi_ui as BU
    import content_engine_bi_boards as BB

    check("the four BI modules are in this image", True)
    _bchk = BU.check_screens()
    check("nine screens, Costs and Agent Economics mandatory",
          _bchk["ok"], str(_bchk["problems"]))
    check("the old boards module is a shim over the new OS",
          "content_engine_bi_ui" in
          open("content_engine_bi_boards.py", encoding="utf-8").read())
    check("the dashboard's entry point still resolves",
          callable(BB.bi_section))
    check("content_engine_bi.py still computes the value half",
          "def revenue" in open("content_engine_bi.py",
                                encoding="utf-8").read())

    _bsec = BB.bi_section({"revenue": {"total": 284000}, "cogs": 40000,
                           "media_spend": 48000, "ai_cost": 3100,
                           "tool_cost": 4390, "cloud_cost": 1240})
    check("the BI section renders", len(_bsec) > 5000,
          str(len(_bsec)) + " chars")
    print("       " + str(len(_bsec)) + " characters")
    _bids = re.findall(r"id=['\"]([^'\"]+)", _bsec)
    check("no duplicate element id in the BI section",
          not [x for x in set(_bids) if _bids.count(x) > 1])
    _bempty = []
    for _sid, _n, _lab, _fn, _q in BU.SCREENS:
        _m = re.search(r"id=['\"]bipanel-" + _sid + r"['\"](.*?)"
                       r"(?=id=['\"]bipanel-|$)", _bsec, re.S)
        _txt = re.sub(r"<[^>]+>", " ", _m.group(1)) if _m else ""
        if len(" ".join(_txt.split())) < 100:
            _bempty.append(_sid)
    check("every one of the nine BI panels renders real content",
          not _bempty, str(_bempty))
    _bvals = sorted({m for m in re.findall(
        r"Contribution[^\u20ac]{0,60}\u20ac([\d,]+)", _bsec)})
    check("HEADER AND EXECUTIVE SHOW ONE CONTRIBUTION",
          len(_bvals) == 1 and _bvals == ["187,270"], str(_bvals))

    # the money rules, against the running code
    _bwf = BC.contribution(revenue=284000, cogs=40000, media=48000,
                           ai=3100, tools=2000, cloud=1200,
                           other_variable=700)
    check("contribution is revenue less every variable cost",
          _bwf["contribution"] == 189000.0)
    check("and is never called net profit",
          _bwf["is_net_profit"] is False)
    _bvs = [BC.price_version("llm", effective_from="2026-01-01",
                             pricing_model="PER_1M_TOKENS",
                             pricing={"input": 3.0, "output": 15.0},
                             effective_to="2026-06-30")["version"],
            BC.price_version("llm", effective_from="2026-07-01",
                             pricing_model="PER_1M_TOKENS",
                             pricing={"input": 5.0,
                                      "output": 25.0})["version"]]
    check("a January call is costed at January's price",
          BC.price_on(_bvs, "llm",
                      "2026-03-15")["pricing_json"]["input"] == 3.0)
    check("an unpriced call is UNKNOWN, never zero",
          BC.cost_of(BC.usage_event(tool_id="ghost",
                                    occurred_at="2026-08-01"),
                     _bvs)["cost"] is None)
    check("a total containing an estimate IS an estimate",
          BC.weakest_quality(["EXACT", "ESTIMATED"]) == "ESTIMATED")
    check("media and software cost are never summed",
          BC.split_media_and_software(
              [BC.usage_event(tool_id="a", cost=100,
                              occurred_at="2026-08-01",
                              metadata={"category": "MEDIA"}),
               BC.usage_event(tool_id="b", cost=10,
                              occurred_at="2026-08-01",
                              metadata={"category": "AI_MODEL"})]
          )["media_spend"] == 100.0)
    check("the registry refuses a row carrying a key",
          BC.register_tool(name="x", provider="p",
                           api_key="sk-1")["ok"] is False)
    check("a policy breach is blocked BEFORE the spend",
          BC.check_policy({"max_run_cost": 3.0},
                          {"max_run_cost": 7.5})["state"] == "BLOCKED")
    check("waste on the spec's own example is 27.8 percent",
          BC.waste([BC.usage_event(tool_id="v", cost=520,
                                   status="SUCCESS",
                                   occurred_at="2026-08-01"),
                    BC.usage_event(tool_id="v", cost=140,
                                   status="FAILED",
                                   occurred_at="2026-08-01"),
                    BC.usage_event(tool_id="v", cost=60,
                                   status="REJECTED",
                                   occurred_at="2026-08-01")]
                   )["waste_pct"] == 27.8)
    _bcard = BE.agent_card({"agent_id": "video", "runs": 84,
                            "successful_runs": 71, "total_cost": 740,
                            "actions_generated": 84,
                            "actions_approved": 44},
                           accepted_outputs=44)
    check("the spec's video agent reads 16.82 per accepted, EXPENSIVE",
          _bcard["cost_per_accepted"] == 16.8182
          and _bcard["status"] == "EXPENSIVE")
    check("an unattributed value produces NO ROI",
          BE.agent_roi(100, 5000,
                       confidence="UNKNOWN")["roi_state"]
          == "UNATTRIBUTED")
    check("ranked on NET value, the biggest spend does not win",
          BE.rank_options([
              BE.option("paid", expected_value_low=6000,
                        expected_value_high=6000,
                        expected_cost_low=4000,
                        expected_cost_high=4000),
              BE.option("email", expected_value_low=3000,
                        expected_value_high=5000,
                        expected_cost_low=70, expected_cost_high=70)]
          )["recommended"] == "email")
    check("a saving that costs HIGH quality is refused",
          BE.optimisation("MODEL_OVERUSE", saving_low=240,
                          saving_high=240,
                          quality_impact="HIGH")["ok"] is False)
    check("no while loop in the cost or economics engines",
          not [n for f in ("content_engine_bi_cost.py",
                           "content_engine_bi_economics.py")
               for n in ast.walk(ast.parse(open(
                   f, encoding="utf-8").read()))
               if isinstance(n, ast.While)])
except Exception as exc:                              # noqa: BLE001
    check("the cost-aware BI OS loaded", False, repr(exc)[:110])

# ---------------------------------------------------- control plane
head("12. THE SYSTEM CONTROL PLANE")
try:
    import content_engine_control_plane as XP
    import content_engine_control_ui as XU
    import content_engine_system_boards as XB

    check("the control plane modules are in this image", True)
    _xchk = XU.check_screens()
    check("thirteen screens, one list", _xchk["ok"],
          str(_xchk["problems"]))
    check("the old system boards module is a shim over the control plane",
          "content_engine_control_ui" in
          open("content_engine_system_boards.py",
               encoding="utf-8").read())
    check("the dashboard's entry point still resolves",
          callable(XB.system_section))

    _xsec = XB.system_section({})
    check("the section renders from the LIVE registry",
          len(_xsec) > 5000, str(len(_xsec)) + " chars")
    print("       " + str(len(_xsec)) + " characters")
    _xids = re.findall(r"id=['\"]([^'\"]+)", _xsec)
    check("no duplicate element id",
          not [x for x in set(_xids) if _xids.count(x) > 1])
    _xempty = []
    for _sid, _n, _lab, _fn, _q in XU.SCREENS:
        _m = re.search(r"id=['\"]scpanel-" + _sid + r"['\"](.*?)"
                       r"(?=id=['\"]scpanel-|$)", _xsec, re.S)
        _txt = re.sub(r"<[^>]+>", " ", _m.group(1)) if _m else ""
        if len(" ".join(_txt.split())) < 80:
            _xempty.append(_sid)
    check("every one of the thirteen panels renders real content",
          not _xempty, str(_xempty))

    # the health rules, against running code
    _xc = [XP.component("Factory", "OS", id="f",
                        status="HEALTHY")["component"],
           XP.component("Creator", "AGENT", id="cr",
                        status="HEALTHY")["component"],
           XP.component("LLM", "API", id="llm",
                        status="HEALTHY")["component"],
           XP.component("Image", "API", id="img",
                        status="FAILED")["component"]]
    _xe = [XP.dependency("f", "cr", relationship="USES",
                         criticality="REQUIRED")["edge"],
           XP.dependency("cr", "llm", relationship="USES",
                         criticality="REQUIRED")["edge"],
           XP.dependency("cr", "img", relationship="USES",
                         criticality="OPTIONAL")["edge"]]
    _xh = XP.derive_health(_xc, _xe)
    check("VERTICAL SLICE: image down degrades the agent, not fails it",
          _xh["cr"]["status"] == "DEGRADED")
    check("and the factory reads DEGRADED, not OFFLINE",
          _xh["f"]["status"] == "DEGRADED")
    check("a REQUIRED dependency down FAILS its dependent",
          XP.derive_health(
              [dict(x, status="FAILED") if x["id"] == "llm" else x
               for x in _xc], _xe)["cr"]["status"] == "FAILED")
    check("recovery heals every dependent automatically",
          all(XP.derive_health(
              [dict(x, status="HEALTHY") for x in _xc],
              _xe)[k]["status"] == "HEALTHY" for k in ("f", "cr")))
    check("UNKNOWN is excluded from the health score, not counted "
          "healthy",
          XP.health_score({"a": ["UNKNOWN"]})["score"] is None)
    check("impact analysis names dependents before a disconnect",
          XP.impact("img", _xc, _xe)["count"] == 2)
    check("waiting past 3x normal is STALLED, and named",
          XP.loop_state({"status": "WAITING", "waited_s": 14400,
                         "normal_wait_s": 3600,
                         "next_expected_event": "X"})["state"]
          == "STALLED")
    check("never-seen is UNKNOWN, not OFFLINE",
          XP.heartbeat_state(60, None)["state"] == "UNKNOWN")
    check("five firings of one failure dedupe to one incident",
          len(XP.dedupe_alerts(
              [XP.alert("AGENT_FAILURE", severity="P1", component="c",
                        why="x", at=str(i))["alert"]
               for i in range(5)])) == 1)
    check("secret_meta cannot even receive a value",
          "value" not in XP.secret_meta.__code__.co_varnames)
    check("six operations are forbidden to the AI",
          all(not XP.ai_may(a)["ok"] for a in XP.AI_FORBIDDEN))
    check("the analyst refuses to answer without evidence",
          XP.analyst("what is wrong?")["state"] == "NO EVIDENCE")
    _xan = XP.analyst("why degraded?", components=_xc, edges=_xe,
                      telemetry={"retry_rate": "27%"})
    check("with evidence it separates FACT, INFERENCE, RECOMMENDATION",
          _xan["facts"] and _xan["inferences"]
          and _xan["recommendations"])
    check("no while loop in the control engine",
          not [n for n in ast.walk(ast.parse(open(
              "content_engine_control_plane.py",
              encoding="utf-8").read())) if isinstance(n, ast.While)])

    # what only this box can answer
    print("")
    try:
        import content_engine_connectors as XC
        _xw = XC.status()
        _xon = [k for k, vv in _xw.items() if vv]
        print("       wires connected on this box: " + str(len(_xon))
              + " of " + str(len(_xw)))
        print("       " + ", ".join(sorted(_xon)[:10])
              + (" ..." if len(_xon) > 10 else ""))
    except Exception as exc:                          # noqa: BLE001
        print("       wire status unavailable: " + repr(exc)[:80])
    _xm = XP.local_metrics()
    _xi = XP.infra_state(_xm)
    print("       host " + str(_xm.get("host"))
          + " | disk " + str(_xm.get("disk_pct")) + "%"
          + " | mem " + str(_xm.get("mem_pct")) + "%"
          + " | load " + str(_xm.get("load"))
          + " | uptime " + str(_xm.get("uptime_days")) + "d")
    print("       infra verdict: " + _xi["state"] + " (" + _xi["why"]
          + ")")
except Exception as exc:                              # noqa: BLE001
    check("the System Control Plane loaded", False, repr(exc)[:110])

# ------------------------------------------------------ command cockpit
head("13. THE COMMAND COCKPIT")
try:
    import content_engine_command_core as KC
    import content_engine_command_ui as KU
    import content_engine_cockpit_boards as KB

    check("the command modules are in this image", True)
    check("the section 101 contract shipped with the image",
          KU.check_contract()["ok"], KU.check_contract()["why"])
    check("the old cockpit module is a shim over the command UI",
          "content_engine_command_ui" in
          open("content_engine_cockpit_boards.py",
               encoding="utf-8").read())
    check("the dashboard's entry point still resolves",
          callable(KB.cockpit_section))
    _ksec = KB.cockpit_section({})
    check("the cockpit renders with the LIVE machine pulse",
          len(_ksec) > 3000 and "Machine Pulse" in _ksec,
          str(len(_ksec)) + " chars")
    print("       " + str(len(_ksec)) + " characters")

    check("CAC up is BAD and spend up is NEUTRAL",
          KC.judge_change("cac", 8)["verdict"] == "BAD"
          and KC.judge_change("spend", 9)["verdict"] == "NEUTRAL")
    check("an unregistered metric stays uncoloured",
          KC.judge_change("vibes", 50)["verdict"] == "UNDECIDED")
    check("a decision missing its contract is DECISION_INCOMPLETE",
          KC.decision(what="x", why="y")["state"]
          == "DECISION_INCOMPLETE")
    check("an unknown action is UNROUTABLE, never guessed",
          KC.route("DO_MARKETING", approved_by="M")["state"]
          == "UNROUTABLE")
    check("nothing routes without a named approver",
          KC.route("CREATE_CONTENT")["state"] == "NEEDS_APPROVAL")
    check("seven operations are forbidden with ANY approval",
          KC.route("rotate_secrets", approved_by="anyone")["state"]
          == "FORBIDDEN")
    check("a fix without rollback is a mysterious button, refused",
          "mysterious" in KC.quick_fix("RETRY_WORKFLOW",
                                       current_state="x")["why"])
    check("success is not an API 200",
          KC.verify_machine_fix(service_recovered=True,
                                dependency_healthy=True,
                                workflow_works=False)["success"]
          is False)
    check("a business action is not judged before its window",
          KC.verify_business_action(metric="cac", before=116, after=108,
                                    observed_days=3)["state"]
          == "STILL_OBSERVING")
    check("initiatives are measured on the metric, not actions done",
          "do not count as progress" in KC.initiative_health(
              target_metric="cac", target_value=110, current_value=116,
              actions_done=3, actions_total=3, observing=True)["why"])
    check("47 identical errors are ONE incident",
          len(KC.aggregate_incident(
              [{"component": "img", "kind": "TIMEOUT", "at": str(i)}
               for i in range(47)])["incidents"]) == 1)
    check("the Commander refuses without snapshots",
          KC.commander("what is happening?")["state"] == "NO_EVIDENCE")
    check("and returns at most five actions with them",
          KC.MAX_RECOMMENDATIONS == 5)

    # the section 102 slice, on the box
    _kchain = KC.root_chain([
        {"layer": "BUSINESS", "text": "TikTok CPA up 32%"},
        {"layer": "PROCESS", "text": "no fresh creative published"},
        {"layer": "SYSTEM", "text": "Image Provider degraded"}])
    check("SLICE: the chain runs business to process to system",
          _kchain["ok"]
          and _kchain["root"]["text"] == "Image Provider degraded")
    _kplan = [("SWITCH_FALLBACK_TOOL", "SYSTEM_CONTROL_PLANE"),
              ("CREATE_VARIANTS", "CONTENT_FACTORY"),
              ("REDUCE_CAMPAIGN_BUDGET", "MEDIA_BUYING_OS")]
    check("SLICE: every plan step routes to its owning OS",
          all(KC.route(a, approved_by="M")["target"] == t2
              for a, t2 in _kplan))
    check("SLICE: CAC improved after the window closes the initiative",
          KC.verify_business_action(metric="cac", before=116, after=108,
                                    observed_days=14)["success"] is True)
    check("no while loop in the command engine",
          not [n for n in ast.walk(ast.parse(open(
              "content_engine_command_core.py",
              encoding="utf-8").read()))
               if isinstance(n, ast.While)])

    print("")
    _kmp = KU.enrich({}).get("machine") or {}
    for _name, _st in list(_kmp.items())[:4]:
        _std = _st if isinstance(_st, dict) else {"status": _st}
        print("       machine pulse: " + str(_name) + " = "
              + str(_std.get("status"))
              + (" (" + str(_std.get("why"))[:70] + ")"
                 if _std.get("why") else ""))
except Exception as exc:                              # noqa: BLE001
    check("the Command Cockpit loaded", False, repr(exc)[:110])

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
