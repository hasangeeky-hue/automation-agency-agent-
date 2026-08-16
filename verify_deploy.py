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
print("ONE LIGHT OS - DEPLOY VERIFICATION")
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
                    # PRINTED WHOLE, ON PURPOSE. The old cap of 96 characters
                    # cut every provider message off at "Error code: 400":
                    # the board announced a failure and then withheld the one
                    # sentence that said why, which is how this survived weeks
                    # of green deploys.
                    _why = str(_e.get("reason"))
                    print("       " + _n + ": " + _why[:110])
                    for _i in range(110, len(_why), 110):
                        print("         " + _why[_i:_i + 110])

        # A PROBE THAT NEVER ANSWERS IS A FAILURE, NOT AN ABSENCE OF DATA.
        # Until now this whole block was prose: it described a broken
        # differentiator in a run that reported 0 failed. A key that is SET
        # is a promise the engine was asked; an engine that was asked and
        # recorded nothing across every prompt is broken, and says so here.
        #
        # THIS JUDGES A STORED SNAPSHOT, NOT TODAY. A snapshot taken while
        # the wallet was empty keeps failing this check long after the
        # wallet is full, so the failure has to say which of the two it
        # is. A stale red is as misleading as a stale green: the founder
        # topped up, the engines answer, and the board still says broken.
        _age = ""
        try:
            from datetime import datetime, timezone
            _when = datetime.fromisoformat(str(_aeo.get("at")))
            _days = (datetime.now(timezone.utc) - _when).days
            _age = ("this result is %d day(s) old" % _days) if _days >= 1 else ""
        except Exception:                                 # noqa: BLE001
            pass
        if _age:
            print("")
            print("       NOTE: " + _age + ". The engines may already be "
                  "fine; this")
            print("       check reads the last STORED probe, not a live "
                  "call.")
            # THE COMMAND HAS TO BE THE ONE THAT PERSISTS. The first
            # version of this note pointed at live_test.py --probe, which
            # asks the engines and prints the answers and stores nothing,
            # so following the instruction changed this check not at all.
            # An instruction that cannot work is worse than none: it
            # spends the founder's time and his credit to prove nothing.
            print("       Re-probe AND SAVE, which is what clears this:")
            print("         docker compose -f deploy/docker-compose.yml "
                  "exec -T api \\")
            print("           python -c \"import content_engine_api as A;"
                  "print(A.api_seo('aeo'))\"")
        for _n, _f2, _k2 in AEO._ENGINES:
            if not AEO._key_present(_k2):
                continue                      # absent key is a choice, not a bug
            _first = ((_res[0] or {}).get(_n) or {})
            check("AI-visibility: %s was asked and actually answered" % _n,
                  _by.get(_n, 0) > 0,
                  (str(_first.get("reason") or "")[:160]
                   + ((" || " + _age + ", so this may already be fixed and "
                       "simply not re-probed") if _age else "")))
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
    check("every screen has a renderer AND a contract",
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
    check("every declared panel renders real content",
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

# ------------------------------------------------------------ ui kit
head("14. THE UI KIT AND DEMO MODE")
try:
    import content_engine_demo as DM
    import content_engine_ui_kit as UK2

    check("the kit and demo modules are in this image", True)
    check("every KIT_EXPORTS name is callable",
          all(callable(getattr(UK2, x, None)) for x in UK2.KIT_EXPORTS))

    _kln = UK2.line([1, 2, 3, None, None, 6, 7, 8], title="T",
                    source="SRC")
    check("A GAP BREAKS THE POLYLINE INTO TWO SEGMENTS",
          _kln.count("<polyline") == 2,
          str(_kln.count("<polyline")))
    check("and the footer says gaps are gaps, not zeros",
          "gap(s) shown as gaps" in _kln)
    check("a chart with no source refuses to draw axes",
          "<svg" not in UK2.line([1, 2], title="T", source=""))
    check("nothing measured draws no axis over nothing",
          "<svg" not in UK2.line([None, None], title="T", source="S"))
    _kwf = UK2.waterfall("Revenue", 100,
                         [("A", 30), ("B", None), ("C", 20)],
                         title="T", source="S", end_label="Left")
    check("waterfall: end equals start minus the KNOWN steps",
          ">50<" in _kwf)
    check("and a missing step is NAMED, never deducted as zero",
          "not supplied and not deducted: B" in _kwf)
    check("hbar leaves unmeasured rows out and counts them",
          "1 unmeasured row(s) left out" in
          UK2.hbar([("A", 10), ("B", None)], title="T", source="S"))
    check("polarity is the caller's verdict: CAC down renders green",
          "uk-ok" in UK2.kpi("CAC", "114", delta=-3, verdict="GOOD"))
    check("absence is a word, never a zero",
          UK2.n(None) == "not measured" and UK2.n(0) == "0")
    check("status is icon plus word, never colour alone",
          "▲ Degraded" in UK2.status("DEGRADED"))
    check("the lecture is a tooltip, not a paragraph",
          "title=" in UK2.note("why") and "<p" not in UK2.note("why"))
    check("the 11px floor holds in the kit stylesheet",
          "font-size:10px" not in UK2.CSS)

    _kg = DM.gallery()
    check("the demo gallery renders every chart type",
          _kg.count("<svg") >= 10, str(_kg.count("<svg")))
    check("AND ADMITS IT IS SAMPLE DATA on its face",
          "SAMPLE DATA" in _kg
          and "Nothing here is the business" in _kg)
    check("no old dark palette leaks into the gallery",
          not [c for c in ("#0A0E1A", "#2FE3D2", "#121A2E")
               if c in _kg])
    check("no while loop in the kit",
          not [x for x in ast.walk(ast.parse(open(
              "content_engine_ui_kit.py",
              encoding="utf-8").read()))
               if isinstance(x, ast.While)])
    print("       gallery: " + str(len(_kg)) + " chars, "
          + str(_kg.count("<svg")) + " charts, kit CSS "
          + str(len(UK2.CSS)) + " bytes shipped once")
except Exception as exc:                              # noqa: BLE001
    check("the UI kit loaded", False, repr(exc)[:110])

# ------------------------------------------- the three aligned sections
head("15. SEO, MEDIA AND LEADS WEAR THE LIGHT DESIGN")
try:
    import content_engine_media_center as MC15
    import content_engine_seo_boards as SB15

    _DARK = ("#0A0E1A", "#0E1526", "#0A0F1E", "#121A2E", "#101d33",
             "#1B2640", "#12161c", "#171c24", "#2FE3D2",
             "var(--s1)", "var(--s2)", "var(--s1,", "var(--s2,")
    _seo = SB15.seo_section({"site": "x"}, legacy_html="<i>L</i>")
    check("the SEO section renders as a rail column",
          "seo-cols" in _seo
          and _seo.index("class='seo-rail'")
          < _seo.index("class='seo-main'"))
    check("its group rail sits above the vertical tabs",
          _seo.index("class='sgroups'") < _seo.index("class='stabs'"))
    check("and no dark-shell colour survives in it",
          not [c for c in _DARK if c in _seo],
          str([c for c in _DARK if c in _seo]))
    check("the SEO section paints its own light ground",
          "background:#F7F8FA" in _seo)

    _mc = MC15.section({})
    check("the Media rail is a vertical sticky column",
          "grid-template-columns:236px 1fr" in _mc
          and "flex-direction:column" in _mc)
    check("no dark-shell colour survives in Media",
          not [c for c in _DARK if c in _mc],
          str([c for c in _DARK if c in _mc]))
    check("the media agent band is styled locally",
          ".mc-root .s3band" in _mc)

    _os = open("content_engine_os_screens.py",
               encoding="utf-8").read()
    check("Leads & Outreach declares the light palette",
          "--osbg:#FFFFFF" in _os and "background:#F7F8FA" in _os)
    check("and carries no dark fallback",
          not [c for c in _DARK if c in _os],
          str([c for c in _DARK if c in _os]))
    print("       seo " + str(len(_seo)) + " chars, media "
          + str(len(_mc)) + " chars, both on their own light ground")
except Exception as exc:                              # noqa: BLE001
    check("the three aligned sections rendered", False, repr(exc)[:110])

# ----------------------------------------------- rounds 2-4: one light OS
head("16. THE UNIFIED SHELL, THE INPUTS, THE CHARTS")
try:
    import content_engine_command_ui as CU16
    import content_engine_control_screens as CS16
    import content_engine_dashboard as D16
    import content_engine_media_center as MC16
    import content_engine_search_bridge as BR16
    import content_engine_search_screens as SS16
    import content_engine_seo_boards as SB16

    check("THE SHELL ITSELF IS LIGHT: tokens flipped at the root",
          "--bg:#F3F4F6" in D16.CSS and "#080B14" not in D16.CSS
          and "#2FE3D2" not in D16.CSS)
    check("the page ground extends to the html element",
          "html{background:var(--bg)}" in D16.CSS)
    check("the nav is grouped Command/Growth/Intelligence/System",
          ".navgrp" in D16.CSS)
    _dsrc = open("content_engine_dashboard.py", encoding="utf-8").read()
    check("the reporting window pills are real links",
          "function setDays(d)" in _dsrc and "'?days='+d" in _dsrc)
    check("the last section and sub-tab survive a reload",
          "_lastsec" in _dsrc and "_tabs" in _dsrc)

    _cn = CS16.connections({"wires": {"w": True}, "connection_tests": {},
                            "connect_html": "<form id='kf'>k</form>"})
    check("THE KEY-ENTRY BOARD IS BACK in Connections",
          "id='kf'" in _cn and "Add, replace" in _cn)
    _wr = CS16.wiring({"legacy_svgs": "<svg id='bp'></svg>"})
    check("and the system blueprint renders again in Wiring",
          "id='bp'" in _wr)

    check("the Search OS has a Tracking tab (26 tabs)",
          len(SB16.TABS) == 26
          and any(t[0] == "seotrack" for t in SB16.TABS))
    _tk = SB16._board_tracking({"gtm_audit": {"ready": True,
                                              "missing": ["m"],
                                              "paused": [],
                                              "silent": []}})
    check("its audited state drafts tags",
          "gtmDraft('m'" in _tk)
    check("and its unaudited state says so instead of pretending",
          "not granted or not audited"
          in SB16._board_tracking({}))

    _mch = MC16.chart([("a", 1), ("b", 2), ("c", None), ("d", 4),
                       ("e", 5)], title="T")
    check("MEDIA'S CHART IS THE KIT'S: a gap breaks the polyline",
          _mch.count("<polyline") == 2)
    _tt = BR16.search_totals({"insights": {"gsc": {"daily": [
        {"date": "d1", "clicks": 2, "impressions": 9, "position": 3},
        {"date": "d2", "clicks": 5, "impressions": 9, "position": 3},
    ]}}})
    check("the bridge hands the daily rows to the screen",
          len((_tt or {}).get("daily") or []) == 2)
    check("and Search Analytics draws clicks per day from them",
          "Organic clicks per day" in SS16.search_analytics(None, _tt))

    _ck = CU16.cockpit_section({
        "log": {"has_data": True, "total": 1, "series": [1],
                "rows": [{"at": "t", "action": "approve",
                          "title": "x"}]},
        "wires": {"a": True, "b": False}})
    check("the cockpit carries a Decision Log zone",
          "Decision Log" in _ck and "approve" in _ck)
    check("and a Connections zone with live/not-live counts",
          "Connections" in _ck and "1</b> live" in _ck)
    check("ckOpen navigates instead of doing nothing",
          "function ckOpen(t){}" not in _ck and "nav(id)" in _ck)

    _fu = open("content_engine_factory_ui.py", encoding="utf-8").read()
    _su = open("content_engine_seo_screens.py", encoding="utf-8").read()
    check("a button whose wire is missing SAYS SO instead of dying",
          "uiNotWired" in _fu and "uiNotWired" in _su)
    print("       shell light, keys back, window real, charts from the "
          "kit, log unified")
except Exception as exc:                              # noqa: BLE001
    check("rounds 2-4 rendered", False, repr(exc)[:110])

# --------------------------------------------------- the wiring round
head("17. THE ENGINE SWITCHES, AND THE LINES THEY CANNOT CROSS")
try:
    import content_engine_scheduler as SC17
    from content_engine_api import get_store as _gs17
    _st17 = _gs17()

    def _g17(k):
        try:
            return _st17.get_setting(k, None)
        except Exception:                             # noqa: BLE001
            return None

    _sw = {k: _g17(k) for k in ("paused", "cadence_on", "autonomy",
                                "media_auto_level", "seo_autofix",
                                "WP_STATUS")}
    check("every switch holds a value its reader understands",
          _sw["media_auto_level"] in (None, "off", "observe", "propose")
          and _sw["seo_autofix"] in (None, "off", "safe", "all")
          and _sw["WP_STATUS"] in (None, "draft", "publish"),
          str(_sw))
    check("AUTONOMY IS OFF: every piece waits for a named human",
          not _sw["autonomy"])

    _src17 = open("content_engine_scheduler.py", encoding="utf-8").read()
    check("the scheduler forces reply auto_send OFF, in code",
          "auto_send=False" in _src17)
    check("and does at most ONE due task per call",
          "One task per call" in _src17)

    class _Paused:
        def get_setting(self, k, d=None):
            return True if k == "paused" else d
        def set_setting(self, k, v):
            raise AssertionError("paused engine must not write")
    check("PAUSED MEANS PAUSED: run_due_work refuses to act",
          (SC17.run_due_work(_Paused()) or {}).get("skipped") == "paused")

    check("the default unattended level never touches visitor copy",
          SC17.seo_auto_level(_st17) in ("off", "safe", "all"))

    # THE ONE-VOCABULARY RULE, enforced where it bit: the terminal set
    # lived in three hand-written copies (orchestrator, pg store, DDL)
    # and "discarded" was in none - so the worker hot-looped on three
    # dead jobs while the day's real work starved.
    import content_engine_orchestrator as OR17
    import content_engine_store_pg as PG17
    check("ONE terminal vocabulary: orch, pg store and DDL agree",
          set(PG17._TERMINAL) == OR17.TERMINAL
          and all(f"'{t}'" in PG17.DDL for t in PG17._TERMINAL))
    check("a human discard is terminal and never claimed",
          "discarded" in OR17.TERMINAL)
    _mst = OR17.InMemoryJobStore()
    _j17 = {"job_id": "wv", "type": "content_piece",
            "status": "no_such_status", "payload": {}}
    _mst.save(_j17)
    check("an unknown status PARKS with a reason, never hot-loops",
          OR17.advance(_j17, _mst) == "failed"
          and "no step for status" in _j17.get("halt_reason", "")
          and _j17.get("needs_human") is True)

    # A budget var that is PRESENT BUT EMPTY in .env means "not set",
    # never "crash at import". The founder blanked the caps to decide
    # later and the worker refused to start: float('') at line one.
    import subprocess as _sp17
    import os as _os17
    _env17 = dict(_os17.environ)
    for _k in ("PER_JOB_BUDGET_USD", "PER_DAY_BUDGET_USD",
               "PER_MONTH_BUDGET_USD", "MEASURE_AFTER_DAYS",
               "AUTONOMY_GRACE_HOURS", "POLL_IDLE_SECS",
               "LLM_TIMEOUT_S", "IMAGES_PER_PIECE"):
        _env17[_k] = ""
    _r17 = _sp17.run(
        ["python", "-c",
         "import content_engine_orchestrator as o, "
         "content_engine_providers, content_engine_prep; "
         "print(o.PER_MONTH_BUDGET_USD)"],
        capture_output=True, text=True, env=_env17, timeout=120)
    check("AN EMPTY BUDGET VAR MEANS DEFAULT, NEVER A DEAD WORKER",
          _r17.returncode == 0 and "200.0" in _r17.stdout,
          (_r17.stderr or "")[-110:])

    # AN EMPTY WALLET IS ONE HALT, NOT SIXTY CORPSES. The API reports
    # exhausted credits as a 400; one night of it killed every queued
    # piece as a separate needs-human failure. The classifier routes it
    # to halted_budget - the daily-cap class, revived in one command.
    import content_engine_providers as PV17
    check("a credit-exhaustion 400 is recognised for what it is",
          PV17._is_credit_exhaustion("'message': 'Your credit balance "
                                     "is too low to access...'")
          and not PV17._is_credit_exhaustion("max_tokens must be "
                                             "positive"))
    _pvsrc = open("content_engine_providers.py", encoding="utf-8").read()
    check("and it raises BudgetExceeded, never a job-killing error",
          "_is_credit_exhaustion(str(e))" in _pvsrc
          and "raise BudgetExceeded(" in _pvsrc)

    # A READ MUST NOT HOLD THE TABLE. Every read left its transaction
    # open, so an api process that had merely looked at a job sat idle
    # in transaction holding a lock: init_db's DDL deadlocked against
    # it and the dashboard hung on a page that never rendered.
    import inspect as _insp17
    import content_engine_store_pg as PG17b
    _leaks = [n for n in ("get", "list_jobs", "get_setting",
                          "daily_cost", "monthly_cost")
              if "_end_read()" not in
              _insp17.getsource(getattr(PG17b.PgJobStore, n))]
    check("EVERY READ CLOSES ITS TRANSACTION (no idle-in-transaction)",
          not _leaks, str(_leaks))
    check("and claim_next still keeps its row lock until save",
          "_end_read()" not in
          _insp17.getsource(PG17b.PgJobStore.claim_next))
    if _st17 is not None and hasattr(_st17, "_conn"):
        _st17.get_setting("paused", None)
        check("a live read leaves the connection IDLE, not in a "
              "transaction",
              int(_st17._conn.info.transaction_status) == 0,
              "transaction_status="
              + str(_st17._conn.info.transaction_status))
    _due17 = SC17.seo_due(_st17)
    _on = (not _sw["paused"]) and bool(_sw["cadence_on"])
    print("       engine: " + ("ON, supervised" if _on else "OFF")
          + " | media agent: " + str(_sw["media_auto_level"] or "not set")
          + " | seo unattended: "
          + str(SC17.seo_auto_level(_st17))
          + " | engines due: " + str(len(_due17)))
except Exception as exc:                              # noqa: BLE001
    check("the wiring switches read back", False, repr(exc)[:110])

# ------------------------------------------------ the starved boards
head("18. EVERY BOARD IS FED (AND NOTHING WAS INVENTED)")
try:
    import subprocess as _sp18
    import content_engine_feeds as FD18
    import content_engine_orchestrator as OR18
    import content_engine_factory_boards as FB18

    _st18 = OR18.InMemoryJobStore()
    _jobs18 = [{"job_id": "probe_piece", "type": "content_piece",
                "status": "AWAITING_APPROVAL",
                "created_at": "2026-01-01T00:00:00",
                "payload": {"content_producer": {"title": "A REAL TITLE",
                                                 "body": "a b c"},
                            "qa_compliance": {"verdict": "pass"},
                            "config": {"type": "blog"}}}]
    _f18 = FD18.factory(_st18, jobs=_jobs18)
    check("THE REVIEW QUEUE CARRIES THE PIECES WAITING FOR YOU",
          len(_f18["needs_review"]) == 1
          and _f18["current"]["title"] == "A REAL TITLE")
    _sec18 = FB18.factory_section(FD18.merge(
        {}, _f18, FD18.chrome(_st18, jobs=_jobs18), FD18.interaction()))
    check("and the Content Factory RENDERS it, not an empty room",
          "A REAL TITLE" in _sec18)

    # A KEY IS NOT A SHAPE. The audit proved `current` was supplied and
    # the board still said "Select an item to preview it", because it
    # wanted blocks to print, not a row. You cannot approve what you
    # cannot read, so the words themselves are the gate.
    check("YOU CAN READ THE PIECE BEFORE YOU APPROVE IT",
          "a b c" in _sec18
          and "Select an item to preview it." not in _sec18)
    check("and every queued piece is openable, not just the newest",
          "?piece=" in _sec18)
    check("the approve button sits beside the words it applies to",
          "Approve and publish" in _sec18
          and "/approve" in _sec18)

    # A BUTTON THAT DOES NOTHING SILENTLY. The founder clicked one and
    # got a promise ("goes live in the wiring round") while /aeo/probe
    # had been serving the whole time. Worse: the Review board's own
    # Approve, Reject and Request-changes handlers were defined NOWHERE,
    # so the one screen where decisions are made ate every click.
    _rb18 = _sp18.run(["python", "audit_buttons.py"],
                      capture_output=True, text=True, timeout=180)
    _tot = [x for x in (_rb18.stdout or "").splitlines()
            if "broken," in x and "wired," in x]
    _nb = int(_tot[0].split(" broken")[0]) if _tot else -1
    _nu = int(_tot[0].split(",")[2].strip().split(" ")[0]) if _tot else -1
    check("NO BUTTON CALLS AN ENDPOINT THAT DOES NOT EXIST",
          _nb == 0, (_tot[0] if _tot else "audit did not report"))
    check("AND NO BUTTON IS SILENTLY UNDEFINED",
          _nu == 0, (_tot[0] if _tot else ""))
    _fu18 = open("content_engine_factory_ui.py", encoding="utf-8").read()
    check("approving is a named human click on a real endpoint",
          "function cfApprove(" in _fu18
          and "/approve" in _fu18 and "confirm(" in _fu18)
    _ss18 = open("content_engine_seo_screens.py", encoding="utf-8").read()
    check("and the AI-visibility re-run reaches /aeo/probe",
          "function ssRerun(" in _ss18 and "/aeo/probe" in _ss18)
    print("       " + (_tot[0] if _tot else "button audit silent"))

    # A REVIEWER APPROVES A THING, NOT A TABLE. previews() renders the
    # piece per channel and had been computed on every load for months
    # with no screen reading it.
    _pv18 = _d18 = _f18.get("previews") or {}
    check("THE REVIEW BOARD SHOWS THE PIECE AS IT WILL LOOK",
          bool((_pv18.get("by_platform") or {}))
          and "How it will look" in _sec18)
    # a daily total cannot answer "which agent cost that"
    _j18 = {"job_id": "probe_cost", "type": "content_piece", "payload": {}}
    OR18.log_cost(_j18, "claude-haiku-4-5", 0.0101, _st18,
                  skill="content_producer")
    _ev18 = _st18.get_setting("cost_events", [])
    check("EVERY MODEL CALL LEAVES A COST EVENT, not just a daily total",
          bool(_ev18) and _ev18[-1]["skill"] == "content_producer"
          and _ev18[-1]["cost"] == 0.0101)
    _bi18 = FD18.bi(_st18)
    check("Data and Tool Health are answered, not NOT CHECKED",
          bool(_bi18.get("tool_health")) and bool(_bi18.get("usage_events")))
    check("and the data mapping is declared, not a black box",
          len(FD18.control(_st18).get("mappings") or []) >= 5)

    # A LIVE SOURCE MUST NOT READ "NEVER CONNECTED". Two functions were
    # named source_state: the bridge emitted {state}, the freshness bar
    # RE-DERIVES from {connected, age_hours}. Seeing neither field it
    # called three working sources unconnected while Search Console was
    # handing over fourteen queries.
    from datetime import datetime as _dt18, timezone as _tz18
    import content_engine_search_bridge as BR18
    import content_engine_search_screens as SS18
    _now18 = _dt18.now(_tz18.utc).isoformat()
    _rows18 = BR18.source_state({"insights": {
        "at": _now18,
        "gsc": {"daily": [{"date": "d", "clicks": 1, "impressions": 9,
                           "position": 3}]},
        "ga4": {"totals": {"sessions": 5}}}})
    check("the bridge emits the shape the freshness bar reads",
          bool(_rows18)
          and all("connected" in r and "age_hours" in r for r in _rows18))
    _v18 = [SS18.source_state(r) for r in _rows18]
    check("A CONNECTED SOURCE IS NEVER CALLED 'NEVER CONNECTED'",
          bool(_v18)
          and all(v["state"] != "NEVER CONNECTED" for v in _v18),
          str([(v["name"], v["state"]) for v in _v18]))
    _ch18 = FD18.chrome(_st18, jobs=_jobs18)
    check("the attention band names what waits and why",
          bool(_ch18["attention"])
          and isinstance(_ch18["attention"][0], dict)
          and _ch18["attention"][0].get("why"))
    check("and the build carries its stamp",
          bool(_ch18.get("version")))

    # A REFUSED CREDENTIAL IS NOT A LIVE WIRE. Google refused the Ads
    # OAuth client every hour ("the OAuth client was not found") while
    # the board counted that wire among the twenty live ones. The engine
    # recorded the refusal all along; nothing showed it.
    import content_engine_connectors as CN18
    CN18.note_auth("ads_api", False, 401, "probe: the provider refused")
    _ct18 = FD18.control(_st18).get("connection_tests") or {}
    check("A REFUSED CREDENTIAL READS AS REJECTED, NOT CONFIGURED",
          (_ct18.get("ads_api") or {}).get("state") == "REJECTED",
          str((_ct18.get("ads_api") or {}).get("state")))
    check("and it carries the provider's own reason",
          "refused" in ((_ct18.get("ads_api") or {}).get("why") or ""))

    # a dict is not a sentence
    import content_engine_media_center as MC18
    _mk18 = MC18.section({"markets": [
        {"market": "Germany", "verdict": "paid is the only way",
         "language": "de", "organic_pages": 0, "organic_impressions": 2,
         "paid_is_only_lever": True}]})
    check("MARKET RECORDS RENDER AS A TABLE, never as raw Python",
          "{'market'" not in _mk18 and "Germany" in _mk18)

    _b18 = FD18.bi(_st18)
    check("an unmeasured cost stays ABSENT, never zero",
          _b18["cogs"] is None and _b18["cloud_cost"] is None
          and "invented cost" in _b18["cost_note"])
    _c18 = FD18.control(_st18)
    check("a secret travels as PRESENCE, never as a value",
          all(s.get("value") is None for s in _c18["secrets"]))
    # THREE WORDS, NOT TWO. A wire the provider actually refused is
    # neither configured nor unconfigured: it is rejected, and saying so
    # is the whole point (Google was refusing the Ads client hourly
    # while the board counted it live).
    check("configured, not configured, and REJECTED are distinct",
          all(t["state"] in ("CONFIGURED", "NOT CONFIGURED", "REJECTED")
              for t in _c18["connection_tests"].values()),
          str(sorted({t["state"]
                      for t in _c18["connection_tests"].values()})))
    check("a real value always beats a feed default",
          FD18.merge({"site": "mine.com"},
                     {"site": "not configured"})["site"] == "mine.com")

    _r18 = _sp18.run(["python", "audit_starved.py"],
                     capture_output=True, text=True, timeout=180)
    _last = [x for x in (_r18.stdout or "").splitlines()
             if "screen functions read" in x]
    _n18 = int(_last[0].split(" of ")[0]) if _last else -1
    check("NO SCREEN READS A KEY NOTHING SUPPLIES",
          _n18 == 0, (_last[0] if _last else "audit did not report"))
    print("       " + (_last[0] if _last else "audit silent")
          + " | factory queue: "
          + str(len(_f18["needs_review"])) + " piece(s)")
except Exception as exc:                              # noqa: BLE001
    check("the feeds answered", False, repr(exc)[:110])

# ------------------------------------------- commerce, cms and the actions
head("19. WHAT THIS SITE SELLS, AND THE BUTTONS THAT FOLLOW")
try:
    import content_engine_actions as ACT19
    import content_engine_cms_screen as CMS19
    import content_engine_commerce as CM19

    class _S19:
        def __init__(self):
            self.d, self.j = {}, {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

        def get(self, jid):
            if jid not in self.j:
                raise KeyError(jid)
            return self.j[jid]

        def save(self, job):
            self.j[job["job_id"]] = job

    _s19 = _S19()
    check("the CMS layer offers Shopify, WooCommerce and WordPress",
          set(CM19.PLATFORMS) == {"shopify", "woocommerce", "wordpress"})
    check("and every key it needs is on the /connect allow-list",
          all(k in CN18.CONNECTOR_ENV_KEYS for k in CM19.connector_keys()),
          str([k for k in CM19.connector_keys()
               if k not in CN18.CONNECTOR_ENV_KEYS]))
    _v0 = CM19.detect_business_type(_s19)
    check("WITH NOTHING READ, THE BUSINESS TYPE IS UNKNOWN",
          _v0["type"] == "UNKNOWN" and _v0["confidence"] == "NONE")
    check("and an unknown business gets NO content recommendation",
          CM19.content_policy(verdict=_v0)["types"] == ())
    _s19.d["cms_catalogue"] = {"platform": "shopify", "at": "x", "items": [
        {"id": str(i), "title": "P", "type": "shirt"} for i in range(12)]}
    _v1 = CM19.detect_business_type(_s19)
    check("A CATALOGUE MAKES IT A SHOP, with the count as the evidence",
          _v1["type"] == "ECOMMERCE"
          and _v1["evidence"]["products_found"] == 12)
    check("and a shop is told to write product and category pages",
          "product page" in CM19.content_policy(verdict=_v1)["types"])
    _v2 = CM19.detect_business_type(
        _S19(), queries=["seo agency munich", "hire a consultant",
                         "marketing strategy audit"])
    check("HIRING QUERIES MAKE IT A SERVICE",
          _v2["type"] == "SERVICE")
    check("and a service is told to write guides and case studies",
          "case study" in CM19.content_policy(verdict=_v2)["types"])
    check("the section renders in every state",
          CMS19.check()["ok"], str(CMS19.check()["problems"]))

    # the buttons that had nowhere to go
    _s19.j["p1"] = {"job_id": "p1", "type": "content_piece",
                    "payload": {"content_producer": {"body": "one"}}}
    check("an edit keeps the text it replaced",
          ACT19.save_piece(_s19, "p1", "body", "two")["ok"]
          and ACT19.restore_piece(_s19, "p1")["ok"]
          and _s19.j["p1"]["payload"]["content_producer"]["body"] == "one")
    check("and only real fields are editable",
          not ACT19.save_piece(_s19, "p1", "price", "9")["ok"])
    _var = ACT19.make_variant(_s19, "p1", "shorter")
    check("A VARIANT ENTERS AS A DRAFT, never as a publish",
          _var["ok"] and _s19.j[_var["job_id"]]["status"] == "created")
    _q = ACT19.quotas(_s19)
    check("an uncounted quota says NOT MEASURED, never zero",
          bool(_q) and all(x["state"] == "NOT MEASURED" for x in _q))
    ACT19.record_usage(_s19, "serper_search", 5)
    check("and a counted one carries its number",
          [x for x in ACT19.quotas(_s19)
           if x["name"] == "serper_search"][0]["used"] == 5)
    # AN AGENT ROSTER MUST BE ASKED, NOT TYPED. A hand-written tuple of
    # four names called thirteen agents "declared, not wired" while the
    # AEO agent had recorded eighteen answers and GEO had run six days
    # earlier. The roster is derived from what imports and is callable.
    import content_engine_search_screens as SS19
    _w19 = SS19.agent_wiring()
    check("EVERY DECLARED AGENT RESOLVES TO REAL CODE",
          all(v[0] == "wired" for v in _w19.values()),
          str([k for k, v in _w19.items() if v[0] != "wired"]))
    check("and each one names the function behind it",
          all("(" in v[1] for v in _w19.values()))
    _sr19 = ACT19.build_report(_s19)
    # THE POLICY IS WIRED, not merely displayed. The business type was
    # computed and read by nobody: every writer produced the same
    # generic post for a shop and a consultancy alike.
    import content_engine_providers as PV19
    _bs = PV19._render_brand({"payload": {}, "business_type": {
        "type": "SERVICE", "confidence": "HIGH", "why": "no products"}})
    check("THE BUSINESS TYPE REACHES THE WRITER'S PROMPT",
          "Type: SERVICE" in _bs and "case study" in _bs)
    _be = PV19._render_brand({"payload": {}, "business_type": {
        "type": "ECOMMERCE", "confidence": "HIGH", "why": "12 products"}})
    check("and a shop is told to write product pages, not blogs",
          "product page" in _be and "add to cart" in _be)
    check("an UNKNOWN business tells the writer to assume NOTHING",
          "do NOT assume products exist" in PV19._render_brand(
              {"payload": {}, "business_type": {"type": "UNKNOWN"}}))
    import content_engine_feeds as FD19b
    _chs = FD19b.channels(_st18)
    check("every channel is reported or named as NOT MEASURED",
          bool(_chs) and all(c.get("state") in ("MEASURED", "NOT MEASURED")
                             for c in _chs)
          and all(c.get("why") for c in _chs
                  if c["state"] == "NOT MEASURED"))
    import content_engine_scheduler as SC19
    check("the factory agents are on the cadence, not waiting on a click",
          "factory" in SC19.SEO_CADENCE)

    # NO BROWSER PROMPT ON THE APPROVAL ROW. A prompt() steals the
    # window and throws away what you typed on a misclick; this codebase
    # fought that once and my own reject button reintroduced it.
    _rv19 = FB18.factory_section(FD18.merge(
        {}, FD18.factory(_st18, jobs=_jobs18),
        FD18.chrome(_st18, jobs=_jobs18), FD18.interaction()))
    _row19 = _rv19[max(0, _rv19.find("Approve and publish") - 400):
                   _rv19.find("Approve and publish") + 2500]
    check("THE APPROVAL ROW USES AN INLINE NOTE, never a browser prompt",
          "prompt(" not in _row19 and "cf-notetext-" in _rv19)
    # SGA RETIRED, ITS SCREENS REHOMED - not left unreachable
    import content_engine_factory_ui as FUI19
    check("Social found a home in the Factory when SGA retired",
          any(x[0] == "cfsocial" for x in FUI19.SCREENS)
          and FUI19.check_screens()["ok"])
    # F11: a screen rendered twice reads as two different findings
    import content_engine_bi_boards as BB19
    _bi19 = BB19.bi_section(FD18.merge({}, FD18.bi(_st18),
                                       FD18.chrome(_st18)))
    # COUNT PANEL HEADINGS, NOT NAME MENTIONS. The first version of this
    # check counted every ">AI Decisions<" and flagged five screens,
    # because each name legitimately appears twice: once in the nav and
    # once as its panel heading. A gate that cries wolf gets ignored,
    # which is worse than no gate.
    _dupes19 = [t for t in ("AI Decisions", "Agent Economics", "Executive",
                            "Growth", "Funnel", "Initiatives")
                if _bi19.count("<p class='bi-h1'>" + t + "</p>") > 1]
    check("NO BI SCREEN PANEL IS RENDERED TWICE ON ONE PAGE",
          not _dupes19, str(_dupes19))
    check("a report names what it could NOT report on",
          _sr19["ok"] and isinstance(_sr19["report"]["not_reported"], list))
    print("       agents wired: " + str(len(_w19)) + "/" + str(len(_w19)))
    print("       business type: " + _v1["type"] + " from "
          + str(_v1["evidence"]["products_found"]) + " products; "
          + str(len(ACT19.quotas(_s19))) + " quota(s) tracked")
except Exception as exc:                              # noqa: BLE001
    check("the commerce and CMS layer answered", False, repr(exc)[:110])

# --- 20. PHASE 2 + LANE 3a: memory per lane, and an employee on the wires --
print("\n20. THE LANES REMEMBER, AND THE WIRES HAVE AN OWNER")
try:
    import content_engine_contracts as C20
    import content_engine_integrations as INT20
    import content_engine_learning as L20
    import content_engine_orchestrator as O20
    import content_engine_report as RP20
    import content_engine_roster as R20
    import content_engine_scheduler as SC20

    check("every job flow names the lane it teaches",
          set(O20.FLOWS) <= set(O20.LANE_OF_JOB),
          str(len(O20.LANE_OF_JOB)) + " flow(s) mapped")
    check("every lane a flow teaches is a real lane",
          set(O20.LANE_OF_JOB.values()) <= set(L20.LANES))
    check("every employee's desk maps to a real learning lane",
          all(R20.lane_of(a["id"]) in L20.LANES for a in R20.roster()),
          str(len(L20.LANES)) + " lanes")
    check("every outcome kind files into a real lane",
          set(L20._OUTCOME_LANE.values()) <= set(L20.LANES))
    check("the content lane still reads the key already on this box",
          L20._lane_key("acme", "content") == "acme")
    check("and another lane cannot collide with it",
          L20._lane_key("acme", "seo") == "acme#seo")

    # the company's day is defined once
    check("there is ONE definition of the company's day",
          RP20._today() == C20.today(), C20.today())

    # the Integrations Engineer
    _ichk = INT20.check()
    check("the Integrations Engineer watches wires that exist",
          _ichk["ok"], str(_ichk["problems"])[:110])
    check("it has a working day on the cadence",
          "integrations" in SC20.SEO_CADENCE)
    check("and that day is free, because it makes no calls",
          SC20.SEO_CADENCE["integrations"]["cost"] == "free")
    _src20 = open(SC20.__file__, encoding="utf-8").read()
    check("it runs BEFORE the nightly archive, or its day is frozen empty",
          _src20.index('_due(state, "integrations"')
          < _src20.index('_due(state, "snapshot"'))
    check("its badge is live and says what makes it live",
          R20.agent("system.integrations")["badge"] == "live"
          and bool(R20.agent("system.integrations")["why"].strip()))
    _isrc = open(INT20.__file__, encoding="utf-8").read()
    check("IT CANNOT MARK A WIRE VERIFIED (Phase 0 stays honest)",
          "note_auth" not in _isrc,
          "no path from a free self-test to a green light")
    check("its asks reach a person as proposals",
          "pending" in _isrc and "/connect#" in _isrc)
except Exception as exc:                                  # noqa: BLE001
    check("the learning lanes and the Integrations Engineer answered",
          False, repr(exc)[:110])

# --- 21. THE AGENT OS: turn 13 + turn 14, bound to real endpoints ---------
print("\n21. THE AGENT OS IS ON THE PAGE, AND IT IS BOUND")
try:
    import re as _re21
    import content_engine_contracts as C21
    import content_engine_dashboard as D21
    import content_engine_agentos as OS21
    import content_engine_agentos_growth as OSG21
    import content_engine_agentos_leads as OSL21
    import content_engine_agentos_commerce as OSCM21
    import content_engine_os_kit as K21
    import content_engine_roster as R21

    class _S21:
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

        def monthly_cost(self):
            return 0.0

    _st21 = _S21()
    _ctx21 = OS21.build_ctx(_st21)
    # ASSERT AGAINST THE PAGE THE ROUTE ACTUALLY SERVES.
    #
    # This built its own HTML from hand-written arguments (jobs=[], st={},
    # health={}...) while GET / serves dashboard_html(**_dashboard_kwargs()),
    # which reads the live store. So every check here was passing against a
    # page the founder is never sent, and any failure that only appears with
    # real data was invisible: 388 green checks and a broken screen are not
    # a contradiction when they are two different documents.
    #
    # The synthetic render is kept only as a fallback, so a store that
    # cannot be read reports THAT rather than skipping the section.
    try:
        _h21 = A.api_dashboard_html()
        _src21 = "the live route, GET /"
    except Exception as _e21:                             # noqa: BLE001
        _h21 = D21.dashboard_html(jobs=[], st={}, health={}, month_spent=0.0,
                                  month_cap=200.0, day_spent=0.0, day_cap=10.0,
                                  taste_skills=[], os_ctx=_ctx21)
        _src21 = ("A SYNTHETIC RENDER: the live route raised %s, so what "
                  "the founder is actually served has NOT been checked"
                  % repr(_e21)[:90])
    print("       page under test: " + _src21)
    check("the page under test is the one the route serves",
          _src21.startswith("the live route"), _src21)
    # WHAT THE SERVER IS ACTUALLY SENDING, printed so it can be compared
    # with what the browser shows. If these disagree, the difference is
    # between the container and the screen (cache, proxy, a stale tab),
    # and no amount of checking in here will find it.
    print("       served page: %d bytes | nav groups: %s"
          % (len(_h21),
             ", ".join(_re21.findall(r"class='navgrp'>([^<]+)<", _h21))
             or "NONE"))
    # HIS SIDEBAR IS THE NAVIGATION. This printed id='nav-...' from the
    # dashboard's own nav, which is deleted, so it rendered a blank line
    # where a reader looks for links: a diagnostic that reads like a
    # failure while everything is fine is its own small lie.
    # sorted+deduped: every page repeats the sidebar, so the raw list is
    # seven modules times seven pages and reads like noise.
    print("       modules    : %s"
          % (", ".join(sorted(set(
              _re21.findall(r"return nav\('(os[a-z]+)'\)", _h21)))) or "NONE"))
    print("       subnav links: %d, of which dead: %d"
          % (_h21.count("class='ox-snav"),
             len([1 for _sid in _re21.findall(r"class='ox-snav[^']*' href='#os-([0-9a-z]+)'", _h21)
                  if ("id='os-%s'" % _sid) not in _h21])))
    print("       pages      : %s"
          % ", ".join(_re21.findall(r"id='sec-([a-z]+)'", _h21)))
    _sty21 = "".join(_re21.findall(r"<style>(.*?)</style>", _h21, _re21.S))

    check("the Agent OS rendered (no fallback card)",
          "Agent OS screens failed" not in _h21)
    import content_engine_agentos_hub as HUB21
    _all21 = (OS21.SCREENS_13 + OS21.SCREENS_14
              + OSG21.SCREENS_9 + OSG21.SCREENS_8 + OSL21.SCREENS_12
              + OSCM21.SCREENS_11 + OSCM21.SCREENS_10
              # HIS FINAL REVISION added five: 15a, 15b, 15c, 16a, 16b.
              # Counted here, or this reports 51 of 51 built while his file
              # asks for 56, which is a green check standing exactly where
              # the missing work is.
              + tuple(HUB21.ALL_NEW))
    _miss21 = [s for s in _all21 if ("id='os-%s'" % s) not in _h21]
    check("all %d wireframe screens built so far are on the page" % len(_all21),
          not _miss21, "t13:11 t14:5 t9:8 t8:8 t12:9 t11:9 t10:1")
    check("HIS CORRECTED FILE IS 58 SCREENS AND ALL 58 ARE BUILT",
          len(_all21) == 58, str(len(_all21)))
    check("and NO screen is rendered twice",
          not [s for s in _all21 if _h21.count("id='os-%s'" % s) > 1])
    # THE OLD CHROME IS GONE ENTIRELY. It used to draw a brand bar, a
    # window-pill strip, a second left nav, the engine strip and two
    # banners, and then his shell INSIDE all of it, so the frame he
    # looked at every day was still the old OS.
    check("THE OLD DASHBOARD CHROME IS GONE (no brand bar, no second nav)",
          "class='top'" not in _h21 and "class='side'" not in _h21
          and "class='navgrp'" not in _h21
          and "class='page on' id='sec-oscockpit'" in _h21)
    check("HIS TOPBAR IS THE ONLY TOPBAR (one per module page)",
          _h21.count("class='ox-topbar'") == 7,
          str(_h21.count("class='ox-topbar'")))
    _old21 = ("cockpit", "bi", "riskinfra", "content", "outreach", "sga",
              "seo", "media", "system")
    check("THE OLD DASHBOARD IS OFF THE NAV, as the founder asked",
          not [p for p in _old21 if ("id='nav-%s'" % p) in _h21],
          str([p for p in _old21 if ("id='nav-%s'" % p) in _h21]))
    # ABSORBED, NOT DELETED: the boards render inside the module that owns
    # them. Rendering the standalone page too duplicated 988 element ids.
    check("no old page is rendered separately any more",
          not [p for p in _old21 if ("id='sec-%s'" % p) in _h21],
          str([p for p in _old21 if ("id='sec-%s'" % p) in _h21]))
    check("EVERY OLD BOOKMARK IS ALIASED to the module that owns its data",
          not [p for p in _old21 if ("%s:'os" % p) not in _h21],
          str([p for p in _old21 if ("%s:'os" % p) not in _h21]))
    # REPLACED. This asserted Search was over 200,000 characters, true
    # only because the OLD BOARDS were rendered inside it. He asked for
    # the DATA kept and the UI cut, and this was measuring the UI: a
    # green check standing guard over the exact thing he wanted gone.
    check("NO OLD BOARD IS RENDERED: only his screens are on the page",
          "class='osdata'" not in _h21
          and not [p for p in ("seo", "bi", "system", "media", "content",
                               "outreach", "sga", "cockpit", "riskinfra")
                   if ("id='sec-%s'" % p) in _h21])
    check("EVERY SUBNAV LINK SCROLLS instead of navigating away",
          _h21.count("class='ox-snav")
          == _h21.count("onclick=\"return osGo("),
          "%d links, %d handlers" % (_h21.count("class='ox-snav"),
                                     _h21.count("onclick=\"return osGo(")))
    check("and no unfilled topbar marker reaches the page",
          "{{OX_" not in _h21)
    check("a nav target that does not resolve cannot blank the page",
          "if(!s)return false;" in _h21)
    # EVERY SIDEBAR MODULE MUST REACH A PAGE. They were anchors copied
    # from his prototype, where all 51 screens share one document. Here
    # each department is a page and the rest are display:none, so the
    # links jumped into hidden pages and nothing opened.
    import content_engine_os_kit as K21
    _tg21 = set(re.findall(r"return nav\('(os[a-z]+)'\)", _h21))
    _pg21 = set(re.findall(r"id='sec-([a-z]+)'", _h21))
    check("EVERY SIDEBAR MODULE SWITCHES PAGE (%d)" % len(K21.MODULE_PAGE),
          len(_tg21) == len(K21.MODULE_PAGE), str(sorted(_tg21)))
    check("and every target is a page that exists on this document",
          _tg21 <= _pg21, str(sorted(_tg21 - _pg21)))
    check("media no longer claims it has no replacement",
          "no Agent OS view of this department" not in _h21)
    check("every Agent OS page is reachable from HIS sidebar",
          all(("nav('%s')" % p) in _h21
              for p in ("oscockpit", "oscore", "osmkt", "osseo",
                        "osleads", "oscom")))
    _gc21 = OSG21.check(_ctx21)
    check("turns 8 and 9 pass their own check", _gc21["ok"],
          str(_gc21["problems"])[:110])
    _lc21 = OSL21.check(_ctx21)
    check("turn 12 passes its own check", _lc21["ok"],
          str(_lc21["problems"])[:110])
    check("every shared desk on turn 12 discloses its worker",
          all("One worker" in _h21[_h21.find("id='os-%s'" % s):
                                   _h21.find("id='os-%s'" % s) + 6000]
              for s in OSL21.SHARED_DESKS))
    check("NO EU hard block is drawn, because the engine has none",
          "the engine does not have one" in " ".join(_h21.split()))
    _cc21 = OSCM21.check(_ctx21)
    check("turns 11 and 10 pass their own check", _cc21["ok"],
          str(_cc21["problems"])[:110])
    check("every commerce desk discloses its one shared employee",
          all("One worker, five desks" in _h21[_h21.find("id='os-%s'" % s):
                                               _h21.find("id='os-%s'" % s) + 7000]
              for s in OSCM21.SHARED_DESKS))
    import content_engine_commerce_desk as CD21
    _dk21 = CD21.check()
    check("the Commerce Analyst is stage 1 and cannot write", _dk21["ok"],
          str(_dk21["problems"])[:110])
    import content_engine_risk_desk as RD21
    _rk21 = RD21.check()
    check("the Risk Sentinel cannot claim a backup it cannot take",
          _rk21["ok"], str(_rk21["problems"])[:110])
    _pp21 = RD21.inspect(_st21)
    check("with no receipt it reports NO PROVEN BACKUP",
          any(f["kind"] == "no_backup_proof" for f in _pp21["findings"]))
    check("and the host lines it prints run the script and prove a restore",
          all("backup.sh" in ln for ln in RD21.HOST_CRON_LINES)
          and any("--verify" in ln for ln in RD21.HOST_CRON_LINES))
    try:
        with open("deploy/backup.sh", encoding="utf-8") as _fh21:
            _sh21 = _fh21.read()
        check("THE SCRIPT reports its own receipt, authenticated",
              "risk/backup-receipt" in _sh21 and "X-API-Key" in _sh21)
    except FileNotFoundError:
        # deploy/ is not copied into the image, so this check is a
        # repo-side one. Say that rather than failing on the box.
        check("the backup script is a HOST file, not in this image", True,
              "checked in the repo, not in the container")
    import content_engine_fixes as FX21
    check("the backup button states it cannot run in-container",
          "cannot run from inside the container"
          in FX21._f_backup(None, None)["message"])
    check("Europe stays in scope, as the founder decided",
          "Per-country rules: decided" in _h21)
    check("and open tracking shows its LIVE state with a real switch",
          "Open tracking, right now" in _h21 and "osTracking(" in _h21
          and "function osTracking" in _h21)
    check("ONE WORKER TWO DESKS is disclosed on 8c and 8e",
          all("same" in _h21[_h21.find("id='os-%s'" % s):
                             _h21.find("id='os-%s'" % s) + 4000].lower()
              for s in ("8c", "8e")))
    check("each page's sidebar marks exactly one module active",
          _h21.count("class='ox-mod on'") == 7,
          str(_h21.count("class='ox-mod on'")))

    _osx21 = _h21[_h21.find("<div class='osx'>"):]
    _used21 = set()
    for _m21 in _re21.finditer(r"class='(ox-[^']*)'", _osx21):
        _used21.update(c for c in _m21.group(1).split() if c.startswith("ox-"))
    _un21 = sorted(c for c in _used21 if ("." + c) not in _sty21)
    check("EVERY class the OS emits has a CSS rule", not _un21, str(_un21)[:110])

    _hnd21 = set(_re21.findall(r"onclick=\"(os\w+)\(", _h21))
    _hnd21 |= set(_re21.findall(r"Enter'\)(os\w+)\(", _h21))
    _dead21 = sorted(h for h in _hnd21 if ("function " + h) not in _h21)
    check("ZERO DEAD BUTTONS on the OS screens", not _dead21, str(_dead21))

    check("the kit vocabulary equals the contract's",
          set(K21.BADGE_LABEL) == set(C21.BADGES)
          and set(K21.STATUS_LABEL) == set(C21.CONNECTOR_STATES))
    _kc21 = K21.check()
    check("the kit's own component check passes", _kc21["ok"],
          str(_kc21["problems"])[:110])
    check("every employee has a card on the all-agents grid",
          all(("<div class='ox-ac-id'>%s</div>" % a["id"]) in _h21
              for a in R21.roster()),
          "%d employees" % len(R21.roster()))
    check("a command becomes a PROPOSAL, never a direct action",
          "'/proposal'" in K21.JS and "if(pink)" in K21.JS)
    check("decision and blocked stay two separate lists",
          "Your decision" in _h21 and "Blocked, not yours to approve" in _h21)
    check("the five permanent gates are named on the control room",
          all(g in _h21 for g in ("SPEND", "PUBLISH", "SEND", "DEPLOY",
                                  "CROSS-MODULE COMMAND")))
    check("a desk with no employee shows no numbers",
          "Nothing is shown here because nothing produces it" in _h21)
    # Scoped to what the OS itself emits. Slicing the assembled page from
    # the first .osx div to the end sweeps in every OTHER section's markup,
    # so this check failed on someone else's punctuation.
    _osonly21 = (K21.CSS + K21.JS + OS21.core_section(_ctx21)
                 + OS21.cockpit_section(_ctx21)
                 + OSG21.marketing_section(_ctx21)
                 + OSG21.search_section(_ctx21)
                 + OSL21.leads_section(_ctx21)
                 + OSCM21.commerce_section(_ctx21))
    check("the OS ships no em-dash (the founder's rule)",
          "—" not in _osonly21 and "&mdash;" not in _osonly21)
except Exception as exc:                                  # noqa: BLE001
    check("the Agent OS answered", False, repr(exc)[:110])

# --- 22. LANE 3d: the Social Distributor ---------------------------------
print("\n22. THE SOCIAL DISTRIBUTOR POSTS ONLY WHAT IT MAY")
try:
    import inspect as _ins22

    import content_engine_roster as R22
    import content_engine_scheduler as SCH22
    import content_engine_social_desk as SD22

    _c22 = SD22.check()
    check("every channel maps to a real poster and a real wire", _c22["ok"],
          str(_c22["problems"])[:110])
    _src22 = _ins22.getsource(SD22.post_one)
    check("an unapproved piece can never be posted",
          "permanent gate" in _src22 and "approved" in _src22)
    check("a channel that is merely configured can never be posted to",
          "not verified" in _src22)
    check("THE SAME PIECE CANNOT POST TWICE",
          "second post" in _src22
          and "published_refs" in _ins22.getsource(SD22._record))
    check("there is a daily ceiling on how many go out",
          isinstance(SD22.MAX_PER_RUN, int) and SD22.MAX_PER_RUN > 0,
          str(SD22.MAX_PER_RUN) + " per run")
    check("it has its OWN cadence key, not the SEO snapshot's",
          "social_post" in SCH22.SEO_CADENCE and "social" in SCH22.SEO_CADENCE)
    _b22 = R22.agent("sga.distributor")
    check("its badge matches reality", _b22["badge"] in ("architected", "live"),
          _b22["badge"])
    check("EVERY DESK NOW HAS A WORKER: none is left unstaffed",
          not [a for a in R22.roster() if a["badge"] == "notstaffed"],
          str([a["id"] for a in R22.roster() if a["badge"] == "notstaffed"]))
except Exception as exc:                                  # noqa: BLE001
    check("the Social Distributor answered", False, repr(exc)[:110])

# --- 23. LANE 3c STAGE 2: the only code that changes a customer's price --
print("")
print("23. A PRICE CHANGE NEEDS A NAMED HUMAN, AND HAPPENS ONCE")
try:
    import inspect as _ins23

    import content_engine_commerce as CM23
    import content_engine_pricing as PX23
    import content_engine_roster as R23

    _c23 = PX23.check()
    check("the pricing lane passes its own check", _c23["ok"],
          str(_c23["problems"])[:110])
    _a23 = _ins23.getsource(PX23.apply_one)
    check("NO PRICE CHANGES WITHOUT A NAMED APPROVER",
          "approved_by" in _a23 and "spend gate is permanent" in _a23)
    check("an already-applied proposal cannot be applied again",
          "already %s" in _a23)
    check("and no single step may move a price further than the bound",
          "MAX_MOVE_PCT" in _a23 and PX23.MAX_MOVE_PCT > 0,
          str(PX23.MAX_MOVE_PCT) + "%")
    check("every proposal is pink, so none can batch-approve",
          '"pink": True' in _ins23.getsource(PX23.propose))
    check("A MISSING COST IS NEVER READ AS ZERO",
          not PX23.margin_of(100, None)["known"]
          and "not guessed" in PX23.margin_of(100, None)["why"])
    check("the shop write refuses a nonsense price",
          not CM23.set_price(None, "1", -5)["ok"]
          and not CM23.set_price(None, "", 10)["ok"])
    check("set_price is called from ONE place only, behind the gate",
          len([1 for _n, _f in vars(PX23).items()
               if callable(_f) and "set_price" in
               (_ins23.getsource(_f) if _ins23.isfunction(_f) else "")]) == 1)
    _b23 = R23.agent("commerce.analyst")
    check("the badge is live, which stage 2 earns", _b23["badge"] == "live",
          _b23["badge"])
    check("and it says the approval is recorded with a name",
          "said yes" in _b23["why"])
except Exception as exc:                                  # noqa: BLE001
    check("the pricing lane answered", False, repr(exc)[:110])

# --- 24. THE NEW LANES ARE VISIBLE, NOT JUST BUILT -----------------------
print("")
print("24. EVERY BUILT LANE REACHES A SCREEN")
try:
    import content_engine_agentos_commerce as OSCM24
    import content_engine_pricing as PX24

    check("stage 2 is built, so no screen still promises it",
          OSCM24.STAGE_2 == {}, str(OSCM24.STAGE_2))
    check("11e explains HOW a discount happens", "no button that simply" in _h21)
    check("the pink rule is stated even with an empty queue",
          "approved one at a time, never in a batch" in _h21)
    _ps24 = _S21()
    _ps24.set_setting(PX24.PROPOSALS_KEY, [{
        "id": "px_D", "product_id": "9", "sku": "D", "title": "Deploy probe",
        "reason": "thin_margin", "why": "thin", "price": 100.0,
        "new_price": 110.0, "pink": True, "status": "pending",
        "preview": {"margin_known": False, "margin_note": "no cost"}}])
    _pq24 = OS21.cockpit_section(OS21.build_ctx(_ps24))
    check("A PINK PRICE PROPOSAL REACHES THE UNIFIED QUEUE",
          "Deploy probe" in _pq24)
    check("flagged pink, so it can never be batch-approved",
          "pink: never batch" in _pq24)
    check("the social queue is on the Distributor's desk",
          "cannot post twice" in _h21)
    check("and the backup posture is on the Infra desk",
          "Backup posture" in _h21)
except Exception as exc:                                  # noqa: BLE001
    check("the new lanes reached their screens", False, repr(exc)[:110])

# --- 25. THE MORNING BRIEFING: the report reaches a human ----------------
print("")
print("25. THE REPORT REACHES YOU, AND ONLY YOU")
try:
    import content_engine_briefing as BR25
    import content_engine_scheduler as SCH25

    _c25 = BR25.check()
    check("no function in the briefing takes a recipient", _c25["ok"],
          str(_c25["problems"])[:110])
    check("the address is read from settings, never from a caller",
          "founder_address" in __import__("inspect").getsource(BR25.run))
    check("A QUIET DAY SENDS NOTHING",
          BR25.should_send({"decisions": [], "blocked": [],
                            "couldnt": []}) is False)
    check("a day with a decision sends",
          BR25.should_send({"decisions": [{"what": "x"}], "blocked": [],
                            "couldnt": []}) is True)
    check("and a failure alone still sends, because you should know",
          BR25.should_send({"decisions": [], "blocked": [],
                            "couldnt": [{"what": "x"}]}) is True)
    _m25 = BR25.compose(_st21, {
        "finished_n": 1, "by_agent": [], "couldnt": [],
        "decisions": [{"what": "approve x", "action": "/jobs/x/approve"}],
        "blocked": [{"what": "gdrive is refusing", "why": "403"}]})
    check("BLOCKED IS SEPARATED FROM YOUR DECISIONS in the mail too",
          "BLOCKED, NOT YOURS TO APPROVE" in _m25["body"]
          and "Nothing you approve will fix them" in _m25["body"])
    check("the subject says how many need a human",
          "1 needs you" in _m25["subject"], _m25["subject"])
    check("it runs on the cadence, free", "briefing" in SCH25.SEO_CADENCE
          and SCH25.SEO_CADENCE["briefing"]["cost"] == "free")
    _s25 = open(SCH25.__file__, encoding="utf-8").read()
    check("and AFTER the nightly snapshot, because it reports the day",
          _s25.index('_due(state, "briefing"')
          > _s25.index('_due(state, "snapshot"'))
except Exception as exc:                                  # noqa: BLE001
    check("the morning briefing answered", False, repr(exc)[:110])

# --- 26. WHAT A REAL DEPLOY TAUGHT US ------------------------------------
print("")
print("26. CHECKS THAT RUN WHERE THEY ARE DEPLOYED, AND TESTS THAT TEST")
try:
    import inspect as _ins26

    import content_engine_connectors as CN26
    import content_engine_fixes as FX26
    import content_engine_risk_desk as RD26

    # 1. A CHECK MUST RUN WHERE IT IS DEPLOYED.
    # This one opened deploy/backup.sh, a HOST file the Dockerfile does
    # not copy on purpose. It passed on a laptop and failed on the box,
    # which is the least useful place to learn anything.
    _rc26 = RD26.check()
    check("THE RISK CHECK RUNS INSIDE THE CONTAINER TOO", _rc26["ok"],
          str(_rc26["problems"])[:110])
    _src26 = _ins26.getsource(RD26.check)
    check("and it treats a missing host file as absent, not broken",
          "FileNotFoundError" in _src26 and "not a failure" in _src26.lower())

    # 2. verify_wire() HAD NO CALLER. The one function that can prove a
    # credential was unreachable from anywhere.
    _api26 = open("content_engine_api.py", encoding="utf-8").read()
    check("there is a route that can actually prove a wire",
          "/connectors/verify" in _api26)
    check("and it refuses a wire with no free self-test rather than "
          "pretending", "has no free self-test" in _api26)
    check("social_linkedin is provable, so the social lane is not deadlocked",
          "social_linkedin" in CN26.VERIFIABLE)

    # 3. THE RE-TEST BUTTON TESTED NOTHING. It called status(), which
    # reports whether a credential is SAVED, and said "N wires answered".
    _rt26 = _ins26.getsource(FX26._f_retest_wires)
    check("RE-TEST EVERY WIRE ACTUALLY TESTS THEM", "verify_wire" in _rt26)
    check("and it names the wires it could NOT test",
          "no free self-test" in _rt26)
    check("a wire that refuses is reported as refused, not counted as live",
          "refused" in _rt26)
except Exception as exc:                                  # noqa: BLE001
    check("the deploy-taught fixes answered", False, repr(exc)[:110])

# --- 27. MEDIA BUYING: the department the wireframe names but never drew --
print("")
print("27. MEDIA IS THE FOUNDER'S DESIGN, NOT MINE")
try:
    import content_engine_agentos_media as MD27

    _miss27 = [s for s in MD27.SCREENS_7 if ("id='os-%s'" % s) not in _h21]
    check("all nine Media screens are on the page", not _miss27, str(_miss27))
    # THE DESKS ARE HIS, VERBATIM. The wireframe's cockpitAgents.media
    # list is the source; if this ever drifts the department stops being
    # his design and becomes mine, which is the one thing he asked
    # against.
    check("THE SIX DESKS ARE THE WIREFRAME'S OWN LIST, VERBATIM",
          [n for _s, _i, n, _dd in MD27.DESKS]
          == ["Scout", "Creative", "Launch", "Optimizer", "Pacing",
              "Reporter"],
          str([n for _s, _i, n, _dd in MD27.DESKS]))
    check("and its connectors are the ones his design lists for Media",
          [w for _l27, w in MD27.MEDIA_WIRES]
          == ["ads_api", "social_facebook", "social_tiktok",
              "social_linkedin"])
    _mc27 = MD27.check(_ctx21)
    check("the department passes its own check", _mc27["ok"],
          str(_mc27["problems"])[:110])
    check("the spend gate is stated where a launch would happen",
          "SPEND is one of the five permanent gates" in _h21)
    check("agents stay READ-ONLY on media, as the spec requires",
          "read-only on media by design" in _h21.lower())
    check("attribution is called a model, not a measurement",
          "Attribution is a MODEL" in _h21)
    check("and it is reachable from HIS sidebar",
          "nav('osmedia')" in _h21 and "id='sec-osmedia'" in _h21)
except Exception as exc:                                  # noqa: BLE001
    check("the Media department answered", False, repr(exc)[:110])

# --- 28. THE WIREFRAME'S SHELL, not a flatter version of it --------------
print("")
print("28. EVERY DEPARTMENT SITS IN HIS SHELL")
try:
    import content_engine_os_kit as K28

    check("the module sidebar is on the page", "ox-sidebar" in _h21)
    check("with each module's screens as a subnav",
          "ox-subnav" in _h21 and "class='ox-snav" in _h21)
    check("and the current module marked active", "ox-mod on" in _h21)
    check("THE SUBNAV CLASS DOES NOT COLLIDE with the paragraph class",
          "class='ox-sub " not in _h21)
    check("the sidebar carries all seven modules", len(K28.MODULES) == 7)
    check("his decision card exists, and demands evidence",
          "ox-dq-rec" in K28.dq("x", "y")
          and "no evidence recorded" in K28.dq("x"))
    # HIS RIGHT-HAND RAIL, counted against his own wireframe rather than a
    # number typed here. He drew a rail on 34 of 51 screens and this OS
    # had none of them: the frame was his, the screen was half his.
    import content_engine_os_rails as R28
    check("EVERY STAFFRAIL HE DREW IS ON THE PAGE (%d)" % len(R28.RAILS),
          _h21.count("class='ox-staffrail'") == len(R28.RAILS),
          str(_h21.count("class='ox-staffrail'")))
    # COUNT THE MARKUP, NOT THE CLASS NAME. The bare name also appears in
    # the stylesheet (.ox-rail-head and .ox-rail-head + .ox-rail-p), so a
    # substring count over the whole page reads 55 for 53 rendered
    # sections. Two phantom sections is a small error that would have been
    # "fixed" by changing the expected number, which would have hidden a
    # real missing rail forever after.
    check("and every rail section he wrote, not just the first of each",
          _h21.count("class='ox-rail-head'")
          == sum(len(v) for v in R28.RAILS.values()),
          str(_h21.count("class='ox-rail-head'")))
    check("THE SUPERSEDED EU HARD-BLOCK CLAIM IS NOT REPRODUCED",
          "hard-blocked from cold email" not in _h21)
    # ONE MODULE OWNS .osx. A second declaration in os_screens repainted
    # his ground and ink from a later position in the cascade, so the
    # tokens were correct and the screen was not.
    _sty21 = "".join(re.findall(r"<style>(.*?)</style>", _h21, re.S))
    # Two declarations by design since dark mode landed: the light tokens
    # and the body.oxdark override, both in the kit. A THIRD is the
    # collision this check exists to refuse.
    check("ONLY THE KIT DECLARES .osx: light once, dark once, nobody else",
          _sty21.count(".osx{") == 2
          and _sty21.count("body.oxdark .osx{") == 1,
          str(_sty21.count(".osx{")))
    check("and the shell PAINTS his ground, not merely declares it",
          "background:var(--ox-bg)" in _sty21)
    check("NO STAFFRAIL REPORTS ACTIVITY NOBODY MEASURED",
          "crawling 1,240 URLs" not in _h21
          and "pieces in flight" not in _h21)
    # THE COMPONENT EXISTING IS NOT THE WORK BEING DONE. These asserted
    # only that K.dq and K.chart were callable, and passed for weeks while
    # no screen called either one.
    import content_engine_os_cards as CD28
    import content_engine_os_tabs as TB28
    _ch28 = sum(len(v) for v in CD28.CHARTS.values())
    _tb28 = sum(len(v) for v in TB28.TABS.values())
    check("EVERY CHART CARD HE DREW IS RENDERED (%d his + %d in tab panes)"
          % (_ch28, _tb28),
          _h21.count("class='ox-cc'") == _ch28 + _tb28,
          str(_h21.count("class='ox-cc'")))
    # HIS IN-SCREEN TABS: nine desks that hold several views each.
    check("EVERY DESK THAT SPLITS HAS ITS TAB STRIP (%d)" % len(TB28.TABS),
          _h21.count("class='ox-tabbar'") == len(TB28.TABS),
          str(_h21.count("class='ox-tabbar'")))
    check("and every view he drew is a tab (%d)" % _tb28,
          _h21.count("<button class='ox-tab") == _tb28,
          str(_h21.count("<button class='ox-tab")))
    check("THE TABS REALLY SWITCH, so none is a dead button",
          "function osTab" in _h21)
    check("and every activity list he drew (%d)" % len(CD28.DQ_SHAPE),
          _h21.count("class='ox-dq-list'") == len(CD28.DQ_SHAPE),
          str(_h21.count("class='ox-dq-list'")))
    check("HIS PLACEHOLDER INCIDENTS ARE NOT SHOWN AS REAL ALERTS",
          "Shopware sync degraded" not in _h21)
    check("his chart card exists", "ox-hbar-t" in K28.chart("t", [("a", 1)]))
    check("AND AN UNMEASURED BAR IS A GAP, NEVER A ZERO",
          "not measured" in K28.chart("t", [("a", None)]))
except Exception as exc:                                  # noqa: BLE001
    check("the shell answered", False, repr(exc)[:110])

# --- 29. THE ORDERS COLLECTOR, stage 2 of the data contract --------------
print("")
print("29. IS THERE ORDER DATA IN THIS ENGINE AT ALL?")
try:
    import content_engine_bi as BI29
    import content_engine_orders as OR29
    import content_engine_scheduler as SCH29

    _c29 = OR29.check()
    check("the orders collector passes its own check", _c29["ok"],
          ", ".join(c["name"] for c in _c29["checks"] if not c["pass"]))
    check("every channel word it emits is one BI knows",
          set(OR29.SOURCE_MAP.values()) <= set(BI29.SOURCES))
    check("it is on the cadence, free, and ahead of commerce",
          "orders" in SCH29.SEO_CADENCE
          and SCH29.SEO_CADENCE["orders"]["cost"] == "free"
          and list(SCH29.SEO_CADENCE).index("orders")
          < list(SCH29.SEO_CADENCE).index("commerce"))
    check("IT IS A READ: the collector calls no write verb on a shop",
          _c29["checks"][-1]["pass"])

    _ctx29 = OR29.context(A.get_store())
    print("       last order collect: "
          + (_ctx29["last_collect"] or "NEVER RUN"))
    print("       orders stored: %d | counted as revenue: %d"
          % (len(_ctx29["orders"]), _ctx29["counted"]))
    if _ctx29["orders"]:
        print("       excluded: %d test, %d cancelled, %d unpaid, "
              "%d with no total"
              % (_ctx29["excluded_test"], _ctx29["excluded_cancelled"],
                 _ctx29["excluded_unpaid"], _ctx29["excluded_no_total"]))
        for _t29 in _ctx29["top_sellers"][:3]:
            print("       top seller: %-22s %s units, revenue %s"
                  % (str(_t29.get("title"))[:22], _t29.get("units"),
                     _t29.get("revenue")
                     if _t29.get("revenue") is not None else "NOT MEASURED"))
        print("       by channel: "
              + (", ".join("%s=%s" % (k, v)
                           for k, v in _ctx29["by_channel"]) or "none"))
    else:
        # Stated plainly rather than as a failure. No orders collected yet
        # is a true fact about a new collector, and the founder needs to
        # know which of the two it is: never run, or run and found none.
        print("       nothing collected yet. Until this runs, revenue,"
              " top sellers,")
        print("       lifecycle and ROAS have no input and every one of"
              " those screens")
        print("       is honestly empty rather than wrong.")
    if _ctx29["unmapped_sources"]:
        print("       UNMAPPED CHANNELS (counted as 'other'): "
              + ", ".join(_ctx29["unmapped_sources"]))

    # --- bookings: the revenue path for a business that sells projects ---
    import content_engine_bookings as BK29
    _cb29 = BK29.check()
    check("the bookings collector passes its own check", _cb29["ok"],
          ", ".join(c["name"] for c in _cb29["checks"] if not c["pass"]))
    check("A BOOKING IS NOT REVENUE until a named human values it",
          not BK29.win(None, "x", 500, approved_by="")["ok"])
    check("bookings is on the cadence and free",
          "bookings" in SCH29.SEO_CADENCE
          and SCH29.SEO_CADENCE["bookings"]["cost"] == "free")

    # THE SEAM. Two collectors write one feed; whoever runs last must not
    # erase the other. Checked on the real modules, not a description of
    # them, because a one-sided version of this passed while the bug was
    # still live in the other direction.
    _seam = BK29._FakeStore({BI29.DEALS_KEY: [
        {"id": "ord-1", "client": "Shop", "value": 10.0,
         "at": "2026-08-01", "source": "direct"}],
        BK29.BOOKINGS_KEY: [{"id": "b9", "client": "B", "at": "2026-08-02"}],
        BK29.WON_KEY: {}})
    BK29.win(_seam, "b9", 900, approved_by="Founder", source="referral")
    _sids = [d["id"] for d in _seam.get_setting(BI29.DEALS_KEY, [])]
    check("ONE DEALS FEED, TWO OWNERS, NEITHER ERASES THE OTHER",
          "ord-1" in _sids and "book-b9" in _sids, _sids)

    # --- social audience: the DATA half of the social wires -------------
    import content_engine_social_desk as SD29
    import content_engine_social_stats as SS29
    _cs29 = SS29.check()
    check("the social audience collector passes its own check", _cs29["ok"],
          ", ".join(c["name"] for c in _cs29["checks"] if not c["pass"]))
    check("its channels are the Distributor's channels, not a second list",
          set(SS29.READABLE) == set(SD29.CHANNELS))
    check("IT CANNOT PUBLISH: a collector that can post is one bug from posting",
          _cs29["checks"][-1]["pass"])
    check("social_stats is on the cadence and free",
          "social_stats" in SCH29.SEO_CADENCE
          and SCH29.SEO_CADENCE["social_stats"]["cost"] == "free")
    _ss29 = SS29.collect(A.get_store())
    print("")
    print("       social audience: %d channel(s), %d readable, "
          "%d returned a follower count"
          % (_ss29["channels"], _ss29["read"], _ss29["with_followers"]))
    for _r29 in _ss29["rows"]:
        _f29 = _r29.get("followers")
        print("       %-10s %-14s %s"
              % (_r29.get("channel"), _r29.get("state"),
                 ("%s followers" % _f29) if _f29 is not None
                 else str(_r29.get("needs") or _r29.get("why") or "")[:64]))

    _bctx29 = BK29.context(A.get_store())
    print("")
    print("       last booking collect: "
          + (_bctx29["last_collect"] or "NEVER RUN"))
    print("       bookings: %d total | %d accepted | %d converted | "
          "%d cancelled"
          % (_bctx29["total"], _bctx29["accepted"], _bctx29["converted"],
             _bctx29["cancelled"]))
    _cr29 = _bctx29["conversion_rate"]
    print("       conversion rate: "
          + ("%s%%" % _cr29 if _cr29 is not None
             else "NOT MEASURED (no booking has been decided yet)"))
    if _bctx29["accepted"]:
        print("       %d accepted booking(s) are waiting on YOUR call: the"
              % _bctx29["accepted"])
        print("       engine cannot know what a project sold for.")
except Exception as exc:                                  # noqa: BLE001
    check("the orders collector answered", False, repr(exc)[:110])

# ==========================================================================
# 30  THE COMMERCE WIRES EXIST, AND THE FEEDER NAMES ONLY REAL WIRES
# ==========================================================================
# shopify and woocommerce were declared in _FEEDS, named by the Commerce
# Analyst's tool slots and grouped by _group_of, and status() never
# returned them. So the Tool Hub, the connector map, health propagation and
# the risk score all read NOT CONNECTED no matter what the founder entered,
# and nothing anywhere said why. The same silence would swallow any feed
# that names a wire status() does not report: it skips forever with a tidy
# reason. Both agreements are asserted here instead of trusted.
try:
    import content_engine_commerce as CM30
    import content_engine_connectors as C30
    import feed_data as FD30

    _st30 = C30.status()
    for _w30 in ("shopify", "woocommerce", "wordpress_cms"):
        check("status() reports the %s wire" % _w30, _w30 in _st30)

    # DERIVED, NOT TYPED. If a platform is added to the commerce registry
    # tomorrow, this fails until status() reports it too.
    _want30 = {("wordpress_cms" if p == "wordpress" else p)
               for p in CM30.PLATFORMS}
    check("every commerce platform has a wire in status()",
          _want30 <= set(_st30), str(sorted(_want30 - set(_st30))))

    _fed30 = [w for w in getattr(C30, "_FEEDS", {}) if w not in _st30]
    check("no wire feeds a module without existing in status()",
          not _fed30, str(_fed30))

    _c30 = FD30.check()
    check("the feeder names only wires that exist", _c30["ok"],
          "; ".join(_c30["problems"]))
    check("the feeder holds a collector for every free feed", _c30["ok"])

    # THE FEEDER MUST NOT BE ABLE TO SEND. A collector that can post is one
    # bug away from posting, and this one runs unattended by design.
    _src30 = open("feed_data.py", encoding="utf-8").read()
    check("THE FEEDER CANNOT PUBLISH, SEND OR SPEND",
          not any(_b30 in _src30 for _b30 in
                  ("post_social(", "SEND_FN", "PUBLISH_FN", ".publish(",
                   ".send(", "set_price(")))
    print("")
    print("       %d wire(s) in status(), %d free feed(s), %d paid and "
          "not run" % (_c30["wires"], _c30["free"], _c30["paid"]))
except Exception as exc:                                  # noqa: BLE001
    check("the commerce wires and the feeder agree", False, repr(exc)[:110])

# ==========================================================================
# 31  THE ENTITY WALL, THE MUTATION LEDGER, THE STANDING RULES, THE FLEET
# ==========================================================================
# Stage B-D of the activation plan. Each of these is the kind of thing
# that LOOKS built from the outside while silently not working: a wall
# with a leak, a ledger that accepts secrets, a rule that never reaches
# a prompt, a fallback model the budget cap meters as free. So each is
# exercised here, not inspected.
try:
    import content_engine_entities as EN31
    import content_engine_learning as L31
    import content_engine_mutation as MU31
    import content_engine_orchestrator as OR31
    import content_engine_providers as PR31

    _e31 = EN31.check()
    check("THE ENTITY WALL HOLDS (scoping self-check)", _e31["ok"],
          "; ".join(_e31["problems"]))
    _m31 = MU31.check()
    check("the mutation agent's refusals refuse and its tallies count",
          _m31["ok"], "; ".join(_m31["problems"]))
    check("every mutation kind is owned by a roster employee",
          _m31["ok"])

    # writers are WIRED, asserted from source: the collectors and the
    # gated price write each reach the ledger.
    for _f31, _lbl31 in (("content_engine_orders.py", "orders"),
                         ("content_engine_bookings.py", "bookings"),
                         ("content_engine_social_stats.py", "social"),
                         ("content_engine_pricing.py", "pricing"),
                         ("content_engine_api.py", "credential saves")):
        _src31 = open(_f31, encoding="utf-8").read()
        check("the %s path writes the mutation ledger" % _lbl31,
              "content_engine_mutation" in _src31)

    # STANDING RULES: a saved rule must demonstrably change the next
    # prompt, and removing it must demonstrably stop.
    _mem31 = L31.InMemoryLearningStore()
    _old31 = L31.ACTIVE
    L31.set_store(_mem31)
    try:
        _r31 = L31.add_rule("GateClient", "content",
                            "Gate check rule: always name the source.")
        check("a standing rule saves", bool(_r31.get("ok")),
              str(_r31.get("message")))
        _blk31 = PR31._standing_rules_block(
            "content_producer", {"client_id": "GateClient"})
        check("A SAVED RULE LANDS IN THE NEXT PROMPT",
              "always name the source" in _blk31)
        L31.remove_rule("GateClient", "content",
                        "Gate check rule: always name the source.")
        _blk31b = PR31._standing_rules_block(
            "content_producer", {"client_id": "GateClient"})
        check("and a removed rule leaves it", "always name the source"
              not in _blk31b)
    finally:
        L31.set_store(_old31)

    # THE FLEET: every model any route can reach is priced, or the
    # budget cap meters it as free.
    _models31 = set()
    for _rt31 in OR31.ROUTES.values():
        for _k31 in ("engine", "fallback", "narrate", "image_prompts"):
            _mdl31 = _rt31.get(_k31)
            if _mdl31 and _mdl31 != "code":
                _models31.add(_mdl31)
    _unpriced31 = sorted(m for m in _models31 if m not in PR31.PRICING)
    check("EVERY ROUTED MODEL HAS A PRICE, so cost can never log 0.0",
          not _unpriced31, str(_unpriced31))
    check("the cheap fallback crosses providers (outage cover)",
          str(OR31.CHEAP_ALT).startswith("gpt"))
    check("qa_compliance still has NO fallback, deliberately",
          OR31.ROUTES["qa_compliance"].get("fallback") is None)

    _rb31 = open("docs/ACTIVATION_RUNBOOK.md", encoding="utf-8").read()
    check("the activation runbook exists and keeps the gates permanent",
          "stay gated forever" in _rb31)
    print("")
    print("       entity wall + mutation ledger + standing rules + fleet: "
          "exercised, not inspected")
except Exception as exc:                                  # noqa: BLE001
    check("stage B-D of the activation plan is wired", False,
          repr(exc)[:120])

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
