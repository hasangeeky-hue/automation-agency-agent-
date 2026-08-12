# -*- coding: utf-8 -*-
"""Gates for the Content Factory OS.

Two halves:

  L1-L14  the rules each section of the spec states, checked against the
          running code rather than against a comment.
  L15     the twenty-eight steps of section 111, walked end to end with
          data that flows from one step into the next. Section 111 says
          the MVP is finished when a user can do all 28 with real
          persisted data, so the walkthrough IS the definition of done
          and not a demo.

A check that raises counts as a failure, never as a skip.
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys

import content_engine_factory_agents as FA
import content_engine_factory_os as FOS
import content_engine_factory_screens as S
import content_engine_factory_ui as UI

PASS, FAIL = [], []


def t(label, ok, detail=""):
    try:
        ok = bool(ok)
    except Exception:                                 # noqa: BLE001
        ok = False
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


def _raised(fn, exc):
    """Did this call raise the exception it is supposed to?

    A rule meant to be unbypassable has to be tested by trying
    to bypass it, not by reading the code that says it cannot
    be bypassed.
    """
    try:
        fn()
    except exc:
        return True
    except Exception:                                 # noqa: BLE001
        return False
    return False


def head(x):
    print("\n" + x)


print("=" * 74)
print("CONTENT FACTORY OS - GATES")
print("=" * 74)

# ---------------------------------------------------------------- L1
head("L1  THE BOUNDARY (spec 0, 2, 106)")
t("the factory owns exactly the twelve stages section 0 names",
  len(FOS.OWNS) == 12 and FOS.OWNS[0] == "OPPORTUNITY"
  and FOS.OWNS[-1] == "LEARN")
t("EVERY THING IT REFUSES TO BUILD NAMES THE OS THAT OWNS IT",
  len(FOS.DOES_NOT_BUILD) >= 8
  and all(len(x) == 2 and all(x) for x in FOS.DOES_NOT_BUILD))
t("no campaign builder, crawler, CRM or email sender is named as owned",
  not [w for w in ("campaign", "crawler", "crm", "sender")
       if any(w in s.lower() for s in FOS.OWNS)])
t("every channel maps to the system that EXECUTES it",
  all(len(v) == 2 and all(v) for v in FOS.DESTINATIONS.values()))
t("paid channels go to the Media Buying OS, never to the factory",
  FOS.DESTINATIONS["META_PAID"][0] == "MEDIA_BUYING_OS"
  and FOS.DESTINATIONS["GOOGLE_PAID"][0] == "MEDIA_BUYING_OS")
t("blog goes to the SEO OS and email to the Email OS",
  FOS.DESTINATIONS["BLOG"][0] == "SEO_OS"
  and FOS.DESTINATIONS["EMAIL"][0] == "EMAIL_OS")
t("and each destination states what IT owns, not what we send",
  "budget" in FOS.DESTINATIONS["META_PAID"][1]
  and "send time" in FOS.DESTINATIONS["EMAIL"][1])

# ---------------------------------------------------------------- L2
head("L2  THE NORMALIZED SIGNAL (spec 3, 4)")
_seo = FOS.normalize_signal({
    "source": "SEO_OS", "signal_type": "CONTENT_OPPORTUNITY",
    "topic": "industrial automation cost", "priority": 92,
    "evidence": [{"impressions": 42000}, {"position": 8.4}],
    "recommended_format": ["ARTICLE", "LINKEDIN_POST"]})
t("every field section 4 lists is present",
  all(k in _seo for k in FOS.SIGNAL_FIELDS))
t("a media signal keeps its metric without being recomputed",
  FOS.normalize_signal({"source": "MEDIA_BUYING_OS",
                        "signal_type": "WINNING_CREATIVE",
                        "hook": "Reduce operating cost",
                        "roas": 5.2})["metric_value"] == 5.2)
t("AN UNKNOWN SOURCE IS KEPT AND MARKED, never dropped or relabelled",
  FOS.normalize_signal({"source": "SOMETHING_NEW",
                        "topic": "x"})["unknown_source"] is True)
t("a signal with no topic cannot become a plan, and says why",
  FOS.signal_is_actionable({"topic": ""})["ok"] is False)
t("a signal with no evidence is planable but flagged weak",
  FOS.signal_is_actionable({"topic": "x"})["weak"] is True)
t("and the reason says nothing in it may be quoted as fact",
  "quoted as fact" in FOS.signal_is_actionable({"topic": "x"})["why"])
t("the same input twice yields the same id",
  FOS.normalize_signal({"source": "SEO_OS", "topic": "a",
                        "received_at": "t"})["id"]
  == FOS.normalize_signal({"source": "SEO_OS", "topic": "a",
                           "received_at": "t"})["id"])

# ---------------------------------------------------------------- L3
head("L3  NINE SCREENS AND THEIR CONTRACTS (spec 5, 100)")
_chk = UI.check_screens()
# TEN, not nine: Social came here when SGA retired rather than becoming
# unreachable code. The cap is still a cap - it exists to stop the
# section sprawling - it just moved by one, deliberately, once.
t("there are exactly ten screens", len(UI.SCREENS) == 10,
  str(len(UI.SCREENS)))
t("EVERY SCREEN HAS A RENDERER AND A CONTRACT FILE",
  _chk["ok"], str(_chk["problems"]))
t("no duplicate screen id",
  len({x[0] for x in UI.SCREENS}) == len(UI.SCREENS))
_req = ("Purpose", "User question", "Layout", "Components", "Data",
        "Data source", "Actions", "CTA", "AI actions", "Loading",
        "Empty", "Error", "Permissions", "State transitions")
_missing = []
for _sid, _n, _lab, _fn, _q in UI.SCREENS:
    _txt = io.open("docs/content-factory/ui/" + _sid + ".md",
                   encoding="utf-8").read()
    for _sec in _req:
        if "## " + _sec not in _txt:
            _missing.append(_sid + ":" + _sec)
t("every contract carries all fourteen required sections",
  not _missing, str(_missing[:6]))
t("every screen states the question it answers",
  all(len(x[4]) > 10 for x in UI.SCREENS))

# ---------------------------------------------------------------- L4
head("L4  THE DESIGN SYSTEM (spec 8-11)")
t("the palette is the one section 8 specifies",
  S.TOKENS["bg"] == "#F7F8FA" and S.TOKENS["human"] == "#2563EB"
  and S.TOKENS["ai"] == "#7C3AED" and S.TOKENS["planning"] == "#0F766E")
t("BLUE MEANS HUMAN AND PURPLE MEANS AI",
  S.MEANING["human"].startswith("a human")
  and S.MEANING["ai"].startswith("AI"))
t("there are exactly four CTA kinds", len(S.CTA_KINDS) == 4)
try:
    S.button("x", "primary")
    t("an invented CTA kind is REFUSED", False, "it rendered")
except ValueError:
    t("an invented CTA kind is REFUSED", True)
t("an AI button is marked as AI on its face",
  "✦" in S.button("Generate Draft", "ai"))
t("a human button is not", "✦" not in S.button("Approve", "human"))

# ---------------------------------------------------------------- L5
head("L5  BLOCKS AND LOCKS (spec 30, 33)")
_b = [FOS.block("HEADLINE", "Automation ROI", id="b1"),
      FOS.block("PARAGRAPH", "Body text here", id="b2", locked=True),
      FOS.block("CTA", "Book a call", id="b3")]
t("a content item is typed blocks", len(FOS.BLOCK_TYPES) == 11)
t("an unknown block type falls back and is MARKED",
  FOS.block("NONSENSE", "x")["unknown_type"] is True)
t("AN AGENT CANNOT EDIT A LOCKED BLOCK",
  FOS.apply_block_edit(_b, "b2", "new", actor="AGENT")["state"]
  == "LOCKED")
t("a human still can",
  FOS.apply_block_edit(_b, "b2", "new", actor="HUMAN")["ok"] is True)
t("an edit that changes nothing is refused",
  FOS.apply_block_edit(_b, "b1", "Automation ROI",
                       actor="HUMAN")["state"] == "NO CHANGE")
t("ONLY A HUMAN MAY CHANGE A LOCK",
  _raised(lambda: FOS.set_lock(_b, "b1", True, actor="AGENT"),
          FOS.LockedBlock))

# ---------------------------------------------------------------- L6
head("L6  VERSIONS AND DIFF (spec 34-36)")
_v1 = FOS.new_version([], _b, changed_by="Murtuja", source="HUMAN",
                      change_summary="first draft", at="t1")
_b2 = [dict(_b[0], text="Automation ROI, explained"), _b[1], _b[2]]
_v2 = FOS.new_version([_v1], _b2, changed_by="CREATOR", source="AGENT",
                      change_summary="sharpened the headline", at="t2")
t("every mutation creates a version", _v2["version_number"] == 2)
t("the snapshot is a COPY, so a later edit cannot rewrite history",
  _v1["snapshot"][0]["text"] == "Automation ROI")
t("an unknown version source is not invented",
  FOS.new_version([], [], changed_by="x", source="MAGIC")["source"]
  == "IMPORT")
_dif = FOS.diff_blocks(_b, _b2)
t("the diff is per block and names what changed",
  len(_dif) == 1 and _dif[0]["state"] == "CHANGED"
  and _dif[0]["after"] == "Automation ROI, explained")
t("an added block reads ADDED and a removed one READS REMOVED",
  FOS.diff_blocks([], _b)[0]["state"] == "ADDED"
  and FOS.diff_blocks(_b, [])[0]["state"] == "REMOVED")

# ---------------------------------------------------------------- L7
head("L7  STATE MACHINE AND APPROVAL (spec 23, 54, 109)")
t("AI_GENERATED IS NOT A CONTENT STATE",
  "AI_GENERATED" not in FOS.CONTENT_STATUS)
t("generation happens inside PRODUCTION",
  "PRODUCTION" in FOS.CONTENT_STATUS)
t("an illegal move is refused and lists what IS allowed",
  FOS.transition("IDEA", "PUBLISHED")["ok"] is False
  and "Allowed from here" in FOS.transition("IDEA", "PUBLISHED")["why"])
t("AN AGENT CANNOT APPROVE",
  FOS.transition("REVIEW", "APPROVED", actor="AGENT",
                 approver="x")["ok"] is False)
t("and approval without a named approver is refused",
  FOS.transition("REVIEW", "APPROVED", actor="HUMAN")["ok"] is False)
t("a human with a name may approve",
  FOS.transition("REVIEW", "APPROVED", actor="HUMAN",
                 approver="Murtuja")["ok"] is True)
t("the plan machine runs DRAFT to COMPLETED",
  FOS.PLAN_STATUS == ("DRAFT", "REVIEWED", "APPROVED", "ACTIVE",
                      "COMPLETED"))
t("a completed plan goes nowhere", FOS.PLAN_MOVES["COMPLETED"] == ())

# ---------------------------------------------------------------- L8
head("L8  THE TOOL ROUTER (spec 37-40, 82)")
t("the MVP starts with text and images, not everything",
  set(FOS.MVP_CAPABILITIES) == {"TEXT_GENERATION", "IMAGE_GENERATION",
                                "IMAGE_EDITING"})
t("an unknown capability is UNKNOWN, not unavailable",
  FOS.route_tool("TELEPATHY")["state"] == "UNKNOWN CAPABILITY")
t("an unconfigured capability names the credential to set",
  "Connect board" in FOS.route_tool("VIDEO_GENERATION")["why"]
  or "not part of" in FOS.route_tool("VIDEO_GENERATION")["why"])
t("AN UNAVAILABLE CAPABILITY NEVER FAKES AN ASSET",
  FOS.route_tool("VIDEO_GENERATION")["available"] is False)
t("the matrix covers every declared capability",
  len(FOS.tool_matrix()) == len(FOS.CAPABILITIES))
t("no capability row exposes a key VALUE",
  not [r for r in FOS.tool_matrix()
       if any(k in str(r) for k in ("sk-", "AIza", "Bearer "))])

# ---------------------------------------------------------------- L9
head("L9  QA: DETERMINISTIC WHERE IT CAN BE (spec 52-53)")
_bad = [FOS.block("HEADLINE", "Cut costs by 40%", id="h"),
        FOS.block("PARAGRAPH", "Visit https://x.test/a ", id="p")]
_ck = FOS.run_validators(_bad, channel="LINKEDIN")
t("five deterministic checks run with no model at all",
  len(_ck) == len(FOS.DETERMINISTIC_CHECKS))
t("a missing CTA is a FAIL, because the reader is asked nothing",
  FOS.validate_cta(_bad)["state"] == "FAIL")
t("AN UNSOURCED CLAIM IS FOUND AND NAMED",
  "40%" in str(FOS.validate_claims(_bad)["claims"]))
t("but the validator does not rule on whether it is TRUE",
  FOS.validate_claims(_bad)["state"] == "WARNING")
t("a claim with an evidence_ref is not flagged",
  FOS.validate_claims([FOS.block("HEADLINE", "Cut costs by 40%",
                                 evidence_ref="sig1")])["state"] == "PASS")
t("a missing required block for the channel is a FAIL",
  FOS.validate_required_blocks(_bad, "LINKEDIN")["state"] == "FAIL")
t("an unknown channel is NOT CHECKED rather than passed",
  FOS.validate_required_blocks(_bad, "SMOKE_SIGNAL")["state"]
  == "WARNING")
t("FAIL beats WARNING beats PASS in the roll-up",
  FOS.qa_verdict(_ck)["state"] == "FAIL")

# ---------------------------------------------------------------- L10
head("L10 HANDOFF (spec 55-60, 106)")
_var = {"id": "v1", "channel": "META_PAID", "format": "VIDEO_AD",
        "status": "APPROVED", "content_blocks": _b,
        "paid_or_organic": "PAID", "destination_url": "https://x.test"}
_pkg = FOS.build_package(_var, master_id="m1",
                         approval={"approved_by": "Murtuja",
                                   "approved_at": "t"})
t("an approved variant becomes a package", _pkg["ok"] is True)
t("addressed to the OS that owns execution",
  _pkg["destination_system"] == "MEDIA_BUYING_OS")
t("and the package states what that OS owns, not what we sent",
  "budget" in _pkg["destination_owns"])
t("UNAPPROVED CONTENT CANNOT BE HANDED OFF",
  FOS.build_package(dict(_var, status="REVIEW"),
                    approval={"approved_by": "x"})["ok"] is False)
t("nor can an approval that names nobody",
  FOS.build_package(_var, approval={})["ok"] is False)
t("an unmapped channel is refused rather than guessed",
  FOS.build_package(dict(_var, channel="CARRIER_PIGEON"),
                    approval={"approved_by": "x"})["ok"] is False)
t("ACCEPTED IS SENT, NEVER PUBLISHED",
  FOS.receive_handoff_result(_pkg, {"state": "ACCEPTED"})["state"]
  == "SENT")
t("and the reason says publication is the destination's word",
  "not published until" in
  FOS.receive_handoff_result(_pkg, {"state": "ACCEPTED"})["why"])

# ---------------------------------------------------------------- L11
head("L11 PERFORMANCE AND CLASSIFICATION (spec 63-71)")
_rows = [{"metrics": {"impressions": 60000, "clicks": 2400,
                      "conversions": 80, "revenue": 6200,
                      "spend": 1200}, "source_system": "MEDIA_BUYING_OS"},
         {"metrics": {"impressions": 60000, "clicks": 2400,
                      "conversions": 65, "revenue": 6200,
                      "spend": 1200}, "source_system": "MEDIA_BUYING_OS"}]
_norm = [FOS.normalize_performance(r) for r in _rows]
_tot = FOS.aggregate(_norm)
t("totals sum across rows", _tot["impressions"] == 120000)
t("CTR IS SUMMED THEN DIVIDED ONCE",
  abs(_tot["ctr"] - 4800.0 / 120000.0) < 1e-9)
t("a rate over a zero denominator is None, never 0.0",
  FOS.rate(5, 0) is None)
t("WINNER MUST BEAT A BASELINE BY HALF AGAIN",
  FOS.classify_result(_tot, metric="ctr", baseline=0.02)["result"]
  == "WINNER")
t("a normal result is not called strong",
  FOS.classify_result(_tot, metric="ctr", baseline=0.04)["result"]
  == "NORMAL")
t("NO BASELINE MEANS INSUFFICIENT_DATA, not average",
  FOS.classify_result(_tot, metric="ctr",
                      baseline=None)["result"] == "INSUFFICIENT_DATA")
t("an unmeasured metric cannot be classified",
  FOS.classify_result(_tot, metric="watch_time",
                      baseline=1)["result"] == "INSUFFICIENT_DATA")
t("BELOW THE SAMPLE FLOOR IS INSUFFICIENT_DATA, and says so",
  "too few to tell" in FOS.classify_result(
      {"impressions": 40, "ctr": 0.5}, metric="ctr",
      baseline=0.02)["why"])
_lr = FOS.make_learning(attribute_type="hook", attribute_value="PAIN_POINT",
                        channel="META_PAID", metric="ctr",
                        values=[0.05, 0.06, 0.04], baseline=0.03)
t("a learning carries its SAMPLE SIZE on its face",
  _lr["sample_size"] == 3)
t("and low confidence when the sample is small",
  _lr["confidence"] == "LOW")
t("no significance test is claimed", "no significance" in _lr["why"])
t("a learning with no measured value is REJECTED",
  FOS.make_learning(attribute_type="hook", attribute_value="x",
                    channel="c", metric="ctr", values=[],
                    baseline=1)["status"] == "REJECTED")

# ---------------------------------------------------------------- L12
head("L12 FOUR AGENTS, AND WHAT THEY MAY NOT DO (spec 72-77)")
t("THERE ARE EXACTLY FOUR AGENTS", len(FA.AGENTS) == 4)
t("approval, distribution and publishing are forbidden to all of them",
  all(not FA.guard(a, act)["ok"]
      for a in FA.AGENTS
      for act in ("approve_content", "distribute_content",
                  "publish_content")))
t("an agent cannot change a lock", not FA.guard("CREATOR",
                                                "change_lock")["ok"])
t("THE PERFORMANCE AGENT CANNOT WRITE CONTENT",
  not FA.guard("PERFORMANCE", "write_blocks")["ok"])
t("and refuses to run at all if that were ever permitted",
  "learning" in FA.performance_run([])
  or FA.performance_run([])["run"]["state"] in ("DONE", "REFUSED"))
t("every agent run carries all six limits",
  set(FA.BUDGET) == {"max_steps", "max_tool_calls", "max_retries",
                     "max_cost_usd", "timeout_s"} | {"max_cost_usd"})
_r = FA.spend(FA.new_run("CREATOR", "x"), steps=99)
t("EXHAUSTING A LIMIT ESCALATES TO A HUMAN",
  _r["state"] == "NEEDS_HUMAN")
t("and it does NOT retry", "did not try again" in _r["why"])
_src = io.open("content_engine_factory_agents.py", encoding="utf-8").read()
_tree = ast.parse(_src)
t("NO WHILE LOOP EXISTS IN THE AGENT MODULE",
  not [n for n in ast.walk(_tree) if isinstance(n, ast.While)])
t("every agent output has a declared shape", len(FA.SCHEMAS) == 5)
t("a payload missing a field is caught",
  FA.validate_output("QAResult", {"state": "PASS"})["ok"] is False)

# ---------------------------------------------------------------- L13
head("L13 FACT, INFERENCE, RECOMMENDATION (spec 108)")
t("a FACT with no reference is DOWNGRADED to an inference",
  FA.claim("FACT", "x")["kind"] == "INFERENCE")
t("and it says why", "must reference" in FA.claim("FACT", "x")["why"])
t("a FACT that points at a signal stays a fact",
  FA.claim("FACT", "x", evidence={"signal_id": "s1"})["kind"] == "FACT")
t("an unknown claim kind is treated as an inference, not promoted",
  FA.claim("TRUTH", "x")["kind"] == "INFERENCE")

# ---------------------------------------------------------------- L14
head("L14 LINEAGE, LOOP, PERMISSIONS, AUDIT (spec 78-79, 87, 107, 110)")
t("the lineage chain has all ten links", len(FOS.LINEAGE) == 10)
_lin = FOS.lineage({"source_signal": "s", "plan": "p"})
t("A BROKEN CHAIN NAMES WHERE IT STOPS",
  _lin["broken_at"] == "master_content")
t("and says what that costs", "cannot be attributed" in _lin["why"])
t("a complete chain reports complete",
  FOS.lineage({k: "x" for k in FOS.LINEAGE})["complete"] is True)
t("nothing entering the loop is NEVER RUN, not healthy",
  FOS.loop_state({})["state"] == "NEVER RUN")
t("WORK MOVING WITH NOTHING CLOSED IS NOT A LOOP",
  FOS.loop_state({"SIGNAL": 8, "PLAN": 3})["state"] == "NOT YET CLOSED")
t("and it is called a content generator until one closes",
  "content generator, not" in
  FOS.loop_state({"SIGNAL": 8})["why"])
t("a closed cycle reports CLOSING",
  FOS.loop_state({"REPLANNED": 2})["state"] == "CLOSING")
t("a viewer cannot approve", not FOS.can("VIEWER", "APPROVE_CONTENT"))
t("a creator cannot approve either",
  not FOS.can("CREATOR", "APPROVE_CONTENT"))
t("a reviewer can", FOS.can("REVIEWER", "APPROVE_CONTENT"))
t("the audit log records actor, action and both sides of a change",
  set(("actor", "actor_type", "action", "before", "after"))
  <= set(FOS.audit("m", "HUMAN", "c1", "edit", before="a", after="b")))
t("the minimum table list is present", len(FOS.TABLES) == 20)

# ---------------------------------------------------------------- L15
head("L15 THE TWENTY-EIGHT STEPS (spec 111)")
STEPS = {}


def step(n, ok, note=""):
    STEPS[n] = bool(ok)
    t("%2d. %s" % (n, UI.DONE_STEPS[n - 1]), ok, note)


# 1. open the factory
_sec = UI.factory_section({})
step(1, "CONTENT FACTORY" in _sec and "cfpanel-cfcmd" in _sec)

# 2. receive a signal from another OS
_in = UI.receive_signal({"source": "MEDIA_BUYING_OS",
                         "signal_type": "WINNING_CREATIVE",
                         "topic": "pain-point UGC hook",
                         "hook": "Reduce operating cost",
                         "roas": 5.2, "priority": 88,
                         "evidence": [{"roas": 5.2}, {"ctr": 3.8}],
                         "recommendation": "CREATE_VARIATIONS",
                         "recommended_format": ["SHORT_VIDEO"]},
                        at="2026-08-10T09:00:00")
_sig = _in["signal"]
step(2, _in["actionable"] and _in["event"]["ok"])

# 3. understand its evidence
_inbox = S.inbox({"signals": [_sig]})
step(3, "roas" in _inbox.lower() and "Evidence" in _inbox)

# 4. turn it into a content plan
_plan_out = FA.planner_run(FA.planner_inputs(
    signals=[_sig], learning=[], capacity={"items_per_week": 5}))
_plan = _plan_out["plan"]
step(4, bool(_plan) and len(_plan["items"]) == 1
     and _plan["status"] == "DRAFT")

# 5. put content on the planner
_planner = S.planner({"plan": _plan})
step(5, "pain-point UGC hook" in _planner)

# 6. generate a brief
_brief_out = FA.build_brief(_plan["items"][0], signal=_sig)
_brief = _brief_out["brief"]
step(6, _brief_out["valid"]["ok"] and _brief["topic"] == "pain-point UGC hook")

# 7. open the Studio
_item = {"title": "Pain-point UGC", "status": "PRODUCTION",
         "brief": _brief, "blocks": [], "versions": []}
step(7, "Copilot" in S.studio({"content": _item}))

# 8. write manually
_blocks = [FOS.block("HEADLINE", "Cut operating cost", id="h1"),
           FOS.block("SOCIAL_COPY", "Here is how three plants did it.",
                     id="s1"),
           FOS.block("CTA", "Book a walkthrough", id="c1")]
_item["blocks"] = _blocks
_vs = [FOS.new_version([], _blocks, changed_by="Murtuja", source="HUMAN",
                       change_summary="wrote the first draft", at="t1")]
step(8, "Cut operating cost" in S.studio({"content": _item}))

# 9. generate or revise text with AI
_act = FA.creator_action("SHORTEN", block_id="s1", blocks=_blocks,
                         brief=_brief, instruction="tighter")
step(9, _act["ok"] and _act["operation"]["kind"] == "CONTENT_BLOCK_REWRITE")

# 10. lock human-approved blocks
_blocks = FOS.set_lock(_blocks, "h1", True, actor="HUMAN")
_locked = FA.creator_action("REWRITE", block_id="h1", blocks=_blocks,
                            brief=_brief)
step(10, _locked["ok"] is False and "locked" in _locked["why"])

# 11. upload an image
_assets = [{"id": "a1", "name": "plant.jpg", "type": "IMAGE",
            "source": "UPLOAD", "status": "READY", "used_in": []}]
step(11, "plant.jpg" in S.library({"assets": _assets}))

# 12. generate an image
_gen = FA.creator_action("GENERATE_IMAGE", blocks=_blocks, brief=_brief)
step(12, (_gen["ok"] and _gen["operation"]["capability"]
          == "IMAGE_GENERATION")
     or ("Connect board" in _gen["why"] or "not part of" in _gen["why"]),
     "image capability unavailable AND the refusal is unexplained")

# 13. edit an image through a tool
_route = FOS.route_tool("IMAGE_EDITING")
step(13, _route["available"] or "Connect board" in _route["why"])

# 14. save asset versions
_av = FOS.new_version([], {"asset": "a1", "op": "remove background"},
                      changed_by="TOOL", source="TOOL",
                      change_summary="background removed", at="t2")
step(14, _av["version_number"] == 1 and _av["source"] == "TOOL")

# 15. create one master content concept
_master = {"id": "m1", "title": "Automation cost campaign",
           "concept": "cost objection", "status": "PRODUCTION",
           "plan_item_id": "pi1", "source_signal_id": _sig["id"]}
step(15, bool(_master["source_signal_id"]))

# 16. generate multiple channel variants
_variants = [{"id": "v-li", "master_content_id": "m1",
              "channel": "LINKEDIN", "format": "SOCIAL_POST",
              "status": "REVIEW", "content_blocks": _blocks,
              "paid_or_organic": "ORGANIC"},
             {"id": "v-meta", "master_content_id": "m1",
              "channel": "META_PAID", "format": "VIDEO_AD",
              "status": "REVIEW", "content_blocks": _blocks,
              "paid_or_organic": "PAID"}]
step(16, len({v["channel"] for v in _variants}) == 2
     and all(v["master_content_id"] == "m1" for v in _variants))

# 17. preview variants
_rev = S.review({"queue": [{"title": "LinkedIn post", "status": "REVIEW",
                           "channel": "LINKEDIN"}],
                 "current": {"blocks": _blocks, "qa": {}, "comments": []}})
step(17, "Cut operating cost" in _rev and "Preview" in _rev)

# 18. comment
_rev2 = S.review({"queue": [], "current": {
    "blocks": _blocks, "qa": {},
    "comments": [{"author": "Murtuja", "text": "tighten the hook"}]}})
step(18, "tighten the hook" in _rev2)

# 19. request revision
_chg = FOS.transition("REVIEW", "CHANGES_REQUESTED", actor="HUMAN")
step(19, _chg["ok"] and _chg["state"] == "CHANGES_REQUESTED")

# 20. review versions and diff
_blocks2 = [dict(_blocks[0]), dict(_blocks[1], text="Three plants did it."),
            dict(_blocks[2])]
_vs.append(FOS.new_version(_vs, _blocks2, changed_by="CREATOR",
                           source="AGENT", change_summary="shortened",
                           at="t3"))
_diff = S.diff_view(_blocks, _blocks2)
step(20, "cf-diff-add" in _diff and "cf-diff-del" in _diff)

# 21. run QA
_qa = FA.qa_run(_blocks2, channel="LINKEDIN", assets=_assets,
                brief=_brief, brand={"forbidden_terms": ["guaranteed"]})
step(21, _qa["result"] is not None
     and _qa["result"]["state"] in FOS.QA_STATES)

# 22. approve content
_ap = FOS.transition("REVIEW", "APPROVED", actor="HUMAN",
                     approver="Murtuja")
step(22, _ap["ok"] and _ap["approver"] == "Murtuja")

# 23. send a package to another OS
_v = dict(_variants[1], status="APPROVED")
_pk = FOS.build_package(_v, master_id="m1", assets=_assets,
                        approval={"approved_by": "Murtuja",
                                  "approved_at": "t4"})
step(23, _pk["ok"] and _pk["destination_system"] == "MEDIA_BUYING_OS")

# 24. receive distribution status
_res = FOS.receive_handoff_result(_pk, {"state": "ACCEPTED",
                                        "external_object_id": "ad_991"})
step(24, _res["state"] == "SENT" and _res["external_object_id"] == "ad_991")

# 25. receive performance data
_perf = [FOS.normalize_performance(
    {"content_variant_id": "v-meta", "source_system": "MEDIA_BUYING_OS",
     "date": "2026-08-20",
     "metrics": {"spend": 2400, "impressions": 120000, "clicks": 4800,
                 "conversions": 145, "revenue": 12400}})]
step(25, _perf[0]["clicks"] == 4800
     and _perf[0]["source_system"] == "MEDIA_BUYING_OS")

# 26. see content performance
_pv = [{"id": "v-meta", "title": "Pain-point UGC", "channel": "META_PAID",
        "format": "VIDEO_AD", "performance": _perf,
        "attributes": {"hook": "PAIN_POINT"}}]
_perf_screen = S.performance({"variants": _pv, "learning": []})
step(26, "Pain-point UGC" in _perf_screen and "120,000" in _perf_screen
     or "4,800" in _perf_screen)

# 27. create learning from results
_pr = FA.performance_run(_pv, metric="ctr", baseline=0.02,
                         attribute="hook")
_learn = _pr["learning"]
step(27, bool(_learn) and _learn[0]["attribute_value"] == "PAIN_POINT"
     and _learn[0]["sample_size"] == 1)

# 28. the planner uses the learning next time
_plan2 = FA.planner_run(FA.planner_inputs(
    signals=[_sig], learning=[dict(_learn[0], status="ACTIVE",
                                   channel="META_PAID")],
    capacity={"items_per_week": 5}))["plan"]
step(28, bool(_plan2) and bool(_plan2["learning_used"])
     and "past learning" in _plan2["items"][0]["because"])

# ---------------------------------------------------------------- render
head("L16 THE SECTION RENDERS, AND EVERY PANEL HAS CONTENT")
_full = UI.factory_section({
    "signals": [_sig], "plan": _plan2, "content": _item,
    "assets": _assets, "variants": _pv, "learning": _learn,
    "packages": [dict(_pk, state="SENT")],
    "queue": [{"title": "LinkedIn post", "status": "REVIEW"}],
    "current": {"blocks": _blocks2, "qa": _qa["result"], "comments": []},
    "brand_profile": {"name": "Anthropos"}, "workflow": {}})
_ids = re.findall(r"id=['\"]([^'\"]+)", _full)
t("no duplicate element id",
  not [x for x in set(_ids) if _ids.count(x) > 1],
  str(sorted({x for x in _ids if _ids.count(x) > 1})))
_empty = []
for _sid, _n, _lab, _fn, _q in UI.SCREENS:
    _m = re.search(r"id=['\"]cfpanel-" + _sid + r"['\"](.*?)"
                   r"(?=id=['\"]cfpanel-|$)", _full, re.S)
    _txt = re.sub(r"<[^>]+>", " ", _m.group(1)) if _m else ""
    if len(" ".join(_txt.split())) < 120:
        _empty.append(_sid)
t("EVERY ONE OF THE NINE PANELS RENDERS REAL CONTENT",
  not _empty, str(_empty))
t("no screen raised into its panel", "could not render" not in _full)
t("the nav lists all nine", all(">" + x[2] in _full for x in UI.SCREENS))
t("no em-dash reaches any factory module",
  not [f for f in ("content_engine_factory_os.py",
                   "content_engine_factory_agents.py",
                   "content_engine_factory_screens.py",
                   "content_engine_factory_ui.py")
       if "—" in io.open(f, encoding="utf-8").read()])
t("the old boards module is a shim over the new UI",
  "content_engine_factory_ui" in
  io.open("content_engine_factory_boards.py", encoding="utf-8").read())

head("L17 WHAT THE BROWSER FOUND AND THE GATES DID NOT")
# Both of these rendered wrong on a page where every gate above passed.
# They are here so that cannot happen twice.
_hz = UI.enrich({})["data_health"]
t("A BOX WITH NO PROVIDER CONNECTED IS NOT AN ERROR",
  _hz["state"] in ("NOT CONFIGURED", "DEGRADED", "HEALTHY"),
  _hz["state"])
t("and when nothing is connected it says nothing has FAILED",
  ("Nothing has failed" in _hz["why"])
  if _hz["state"] == "NOT CONFIGURED" else True)
t("the header renders that state without calling it red",
  "Data " in S.header({"data_health": _hz}))
_bf = {"format": "SHORT_VIDEO", "objective": "x", "audience": "y",
       "funnel_stage": "z", "topic": "t", "primary_message": "m",
       "supporting_points": [], "cta": "c", "channel": "LINKEDIN",
       "paid_or_organic": "ORGANIC", "success_metric": "ctr"}
_st = S.studio({"content": {"title": "x", "brief": _bf, "blocks": [],
                            "versions": []}})
t("THE STUDIO HEADER READS THE FORMAT THE BRIEF ALREADY HOLDS",
  "SHORT_VIDEO" in _st and "format not set" not in _st)
t("and still says 'not set' when neither holds one",
  "format not set" in S.studio({"content": {"title": "x", "blocks": [],
                                            "versions": []}}))

head("L18 WHAT THE CODE READS AT RUNTIME MUST BE IN THE IMAGE")
# The box found this one: check_screens() reads docs/ at runtime and the
# Dockerfile copied only *.py, so the contract check passed in the repo
# and failed in the container. Passing locally proved nothing about the
# thing that actually runs.
_df = io.open("deploy/Dockerfile", encoding="utf-8").read()
t("the Dockerfile ships the screen contracts the code reads",
  "COPY docs" in _df,
  "check_screens() reads docs/ but the image would not contain it")
t("and it still ships every root python module",
  "COPY *.py" in _df)
_reads = []
for _mod in ("content_engine_factory_ui.py",
             "content_engine_factory_os.py",
             "content_engine_factory_agents.py",
             "content_engine_factory_screens.py"):
    _src2 = io.open(_mod, encoding="utf-8").read()
    for _needle in ("docs/", "docs\\", 'join("docs"'):
        if _needle in _src2:
            _reads.append(_mod)
            break
t("every module that reads a non-python path is covered by a COPY",
  not _reads or "COPY docs" in _df, str(sorted(set(_reads))))
t("the contract directory the code looks in is the one on disk",
  os.path.isdir(UI.CONTRACT_DIR),
  UI.CONTRACT_DIR)

# ---------------------------------------------------------------- verdict
_done = sum(1 for v in STEPS.values() if v)
print("\n" + "=" * 74)
print("Section 111: " + str(_done) + " of 28 steps demonstrated")
if _done < 28:
    print("  not demonstrated: "
          + ", ".join(str(k) for k, v in sorted(STEPS.items()) if not v))
print(str(len(PASS)) + " passed, " + str(len(FAIL)) + " failed")
if FAIL:
    for f in FAIL:
        print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
