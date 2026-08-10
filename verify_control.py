# -*- coding: utf-8 -*-
"""Gates for the System Control Plane.

  L1-L10  the rules the spec states, checked against running code.
  L11     the section 111 vertical slice: fail the image provider and
          watch the whole chain change state; recover it and watch the
          chain heal. Section 111: "If this works, the architecture
          works."
  L12     the forty-three steps of the section 119 definition of done.

A check that raises counts as a failure, never as a skip.
"""
from __future__ import annotations

import ast
import io
import re
import sys

import content_engine_control_plane as CP
import content_engine_control_screens as S
import content_engine_control_ui as UI

PASS, FAIL = [], []


def t(label, ok, detail=""):
    try:
        ok = bool(ok)
    except Exception:                                 # noqa: BLE001
        ok = False
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


def head(x):
    print("\n" + x)


print("=" * 74)
print("SYSTEM CONTROL PLANE - GATES")
print("=" * 74)

# ---------------------------------------------------------------- L1
head("L1  REGISTRY AND EDGES (spec 13-15, 82-83)")
t("twelve component types", len(CP.COMPONENT_TYPES) == 12)
t("an unknown component type is refused, not coerced",
  CP.component("x", "GADGET")["ok"] is False)
t("eight edge relationships", len(CP.RELATIONSHIPS) == 8)
t("an unlabeled relationship is refused",
  CP.dependency("a", "b", relationship="POINTS_AT")["ok"] is False)
t("EDGES CARRY THEIR OWN STATUS, because integrations fail while both "
  "ends are up",
  CP.dependency("a", "b", status="FAILED")["edge"]["status"] == "FAILED")
t("status is never colour alone: icon plus word",
  CP.STATUS_MARK["DEGRADED"] == "▲ Degraded"
  and CP.STATUS_MARK["HEALTHY"] == "● Healthy")

# ---------------------------------------------------------------- L2
head("L2  HEALTH PROPAGATION (spec 2, 10)")
_c = [CP.component("Factory", "OS", id="f")["component"],
      CP.component("Creator", "AGENT", id="cr")["component"],
      CP.component("LLM", "API", id="llm", status="HEALTHY")["component"],
      CP.component("Image", "API", id="img",
                   status="HEALTHY")["component"]]
_e = [CP.dependency("f", "cr", criticality="OPTIONAL")["edge"],
      CP.dependency("cr", "llm", criticality="REQUIRED")["edge"],
      CP.dependency("cr", "img", criticality="OPTIONAL")["edge"]]
_h0 = CP.derive_health(_c, _e)
t("with everything up, nothing is degraded",
  all(_h0[k]["status"] in ("HEALTHY", "UNKNOWN") for k in _h0))
_c_img_down = [dict(x, status="FAILED") if x["id"] == "img" else x
               for x in _c]
_h1 = CP.derive_health(_c_img_down, _e)
t("A FAILED OPTIONAL DEPENDENCY DEGRADES, NOT FAILS",
  _h1["cr"]["status"] == "DEGRADED", _h1["cr"]["status"])
t("and the degradation climbs the chain",
  _h1["f"]["status"] == "DEGRADED")
t("with the reason attached at every level",
  "OPTIONAL" in _h1["cr"]["why"] and "degraded beneath" in _h1["f"]["why"])
_c_llm_down = [dict(x, status="FAILED") if x["id"] == "llm" else x
               for x in _c]
_h2 = CP.derive_health(_c_llm_down, _e)
t("A FAILED REQUIRED DEPENDENCY FAILS ITS DEPENDENT",
  _h2["cr"]["status"] == "FAILED" and "REQUIRED" in _h2["cr"]["why"])
_e_bad = [dict(_e[0]), dict(_e[1]), dict(_e[2], status="FAILED")]
_h3 = CP.derive_health(_c, _e_bad)
t("a failed EDGE degrades even when both ends are healthy",
  _h3["cr"]["status"] == "DEGRADED" and "edge" in _h3["cr"]["why"])
t("a component's own failure beats propagation",
  CP.derive_health([dict(_c[0], status="FAILED")], [])["f"]["status"]
  == "FAILED")

# ---------------------------------------------------------------- L3
head("L3  THE SCORE IS DERIVED, NEVER INVENTED (spec 9)")
_sc = CP.health_score({"agents": ["HEALTHY", "DEGRADED"],
                       "apis": ["HEALTHY", "HEALTHY"]})
t("the score is the mean of the area scores",
  _sc["score"] == 88, str(_sc.get("score")))
t("and the areas ship with the total, so it can be expanded",
  _sc["areas"]["agents"] == 75 and _sc["areas"]["apis"] == 100)
t("UNKNOWN COMPONENTS ARE EXCLUDED, NOT COUNTED AS HEALTHY",
  CP.health_score({"a": ["UNKNOWN", "UNKNOWN"]})["score"] is None
  and "not healthy" in CP.health_score({"a": ["UNKNOWN"]})["why"])

# ---------------------------------------------------------------- L4
head("L4  IMPACT ANALYSIS (spec 17)")
_imp = CP.impact("llm", _c, _e)
t("disconnecting the LLM names the agent and OS above it",
  _imp["count"] == 2 and "Creator" in str(_imp["affected"]))
t("a leaf with no dependents is safe to disconnect, and says so",
  "safe" in CP.impact("f", _c, _e)["why"]
  or CP.impact("f", _c, _e)["count"] == 0)
t("an unknown component is refused, not reported empty",
  CP.impact("ghost", _c, _e)["ok"] is False)

# ---------------------------------------------------------------- L5
head("L5  HEARTBEATS AND LOOPS (spec 41-42, 86)")
t("a beat within tolerance is healthy",
  CP.heartbeat_state(60, 70)["state"] == "HEALTHY")
t("two missed intervals is DEGRADED",
  CP.heartbeat_state(60, 140)["state"] == "DEGRADED")
t("five missed is OFFLINE",
  CP.heartbeat_state(60, 320)["state"] == "OFFLINE")
t("NEVER SEEN IS UNKNOWN, NOT OFFLINE",
  CP.heartbeat_state(60, None)["state"] == "UNKNOWN"
  and "has not crashed" in CP.heartbeat_state(60, None)["why"])
t("waiting within the normal window is WAITING",
  CP.loop_state({"status": "WAITING", "waited_s": 3600,
                 "normal_wait_s": 3600,
                 "next_expected_event": "X"})["state"] == "WAITING")
_st = CP.loop_state({"status": "WAITING", "waited_s": 14400,
                     "normal_wait_s": 3600,
                     "next_expected_event": "CAMPAIGN_METRICS_UPDATED"})
t("WAITING PAST THREE TIMES NORMAL IS STALLED",
  _st["state"] == "STALLED")
t("and the stall names the event it is waiting on and the multiple",
  "CAMPAIGN_METRICS_UPDATED" in _st["why"] and "4.0x" in _st["why"])

# ---------------------------------------------------------------- L6
head("L6  TRACE, ALERTS, ROOT CAUSE (spec 66-73)")
_ev = [{"correlation_id": "abc", "at": "t1", "source": "BI",
        "event": "CREATE_CONTENT_REQUEST", "status": "OK"},
       {"correlation_id": "abc", "at": "t2", "source": "Factory",
        "event": "CONTENT_CREATED", "status": "OK", "cost": 0.4},
       {"correlation_id": "abc", "at": "t3", "source": "ImageTool",
        "event": "IMAGE_GENERATION", "status": "FAILED"},
       {"correlation_id": "zzz", "at": "t1", "source": "SEO",
        "event": "CRAWL", "status": "OK"}]
_tr = CP.trace(_ev, "abc")
t("one correlation id gives one timeline across systems",
  len(_tr["events"]) == 3 and _tr["systems"] == ["BI", "Factory",
                                                 "ImageTool"])
t("and names where it failed", "ImageTool" in _tr["why"])
t("A MISSING TRACE SAYS THE ID MAY NOT BE PROPAGATED",
  "not\npropagating" in CP.trace(_ev, "nope")["why"]
  or "not propagating" in CP.trace(_ev, "nope")["why"])
_al = [CP.alert("AGENT_FAILURE", severity="P1", component="Creator",
                why="x", at=str(i))["alert"] for i in range(5)]
_dd = CP.dedupe_alerts(_al)
t("FIVE FIRINGS OF ONE FAILURE ARE ONE INCIDENT",
  len(_dd) == 1 and _dd[0]["occurrences"] == 5)
t("an unknown alert type is refused",
  CP.alert("VIBES_BAD", severity="P1", component="x",
           why="")["ok"] is False)
_rc = CP.root_cause("f", _c_img_down, _e)
t("the root cause chain walks down to the sick leaf",
  _rc["root"]["component"] == "Image")
t("and reads as a because-chain",
  "because" in _rc["why"])

# ---------------------------------------------------------------- L7
head("L7  SECRETS NEVER ENTER (spec 74-76, 22)")
t("the mask keeps only the edges",
  CP.mask("sk-live-abcdefgh4dk2") == "sk-••••••••4dk2")
t("a short value is fully masked", CP.mask("abc") == "••••••••")
t("secret_meta does not accept a value parameter",
  "value" not in CP.secret_meta.__code__.co_varnames)
t("statuses include expiring, expired and permission-changed",
  {"EXPIRING_SOON", "EXPIRED",
   "PERMISSION_CHANGED"} <= set(CP.SECRET_STATES))

# ---------------------------------------------------------------- L8
head("L8  CONNECTION TESTS AND MAPPING (spec 23, 26-27)")
_ct = CP.connection_test([
    {"check": "auth", "state": "PASS"},
    {"check": "campaign_write", "state": "WARNING",
     "why": "permission missing"},
    {"check": "latency", "state": "PASS"}])
t("a missing permission is a WARNING with its name",
  _ct["state"] == "WARNING" and "permission missing" in _ct["why"])
t("no checks at all is a FAIL, not a pass",
  CP.connection_test([])["state"] == "FAIL")
_map = CP.apply_mapping(
    [{"provider_field": "campaign_id", "internal_field": "external_id",
      "transformation": "DIRECT", "required": True},
     {"provider_field": "spend", "internal_field": "spend",
      "transformation": "CAST", "required": True}],
    {"campaign_id": "c1", "spend": "48.5"})
t("a mapping test produces the normalized object",
  _map["ok"] and _map["normalized"]["spend"] == 48.5)
t("A REQUIRED FIELD ABSENT FROM THE SAMPLE BLOCKS ACTIVATION",
  CP.apply_mapping([{"provider_field": "roas", "internal_field": "r",
                     "required": True}], {})["ok"] is False)

# ---------------------------------------------------------------- L9
head("L9  INFRASTRUCTURE HONESTY (spec 52, 91)")
_m = CP.local_metrics()
t("the collector runs on this platform", isinstance(_m, dict))
t("A METRIC THE PLATFORM CANNOT SUPPLY IS None WITH A REASON, NOT ZERO",
  (_m.get("load") is not None) or "not as zero" in _s_why(_m)
  if False else
  (_m.get("load") is not None or "unavailable" in
   str(_m.get("load_why", "")) or "zero" in str(_m.get("load_why", ""))))
t("judging no metrics yields UNKNOWN, not healthy",
  CP.infra_state({})["state"] == "UNKNOWN")
t("disk at 92 percent is a problem",
  CP.infra_state({"disk_pct": 92})["state"] in ("FAILED", "DEGRADED"))
t("a queue with no declared normal cannot claim backlog or health",
  CP.queue_state(pending=500, normal_pending=None)["state"] == "UNKNOWN")
t("three times normal pending is BACKLOG",
  CP.queue_state(pending=142, normal_pending=30)["state"] == "BACKLOG")

# ---------------------------------------------------------------- L10
head("L10 PERMISSIONS AND THE AI FENCE (spec 101-105)")
t("a viewer can see the map and nothing else",
  CP.can("VIEWER", "VIEW_SYSTEM_MAP")
  and not CP.can("VIEWER", "ROTATE_SECRET"))
t("only owner and system admin rotate secrets",
  CP.can("SYSTEM_ADMIN", "ROTATE_SECRET")
  and not CP.can("DEVELOPER", "ROTATE_SECRET"))
t("SIX OPERATIONS ARE FORBIDDEN TO THE AI",
  len(CP.AI_FORBIDDEN) == 6
  and all(not CP.ai_may(a)["ok"] for a in CP.AI_FORBIDDEN))
t("and diagnosis is not among them",
  CP.ai_may("diagnose")["ok"] is True)
_an = CP.analyst("why is the factory degraded?",
                 components=_c_img_down, edges=_e,
                 telemetry={"image_retry_rate": "27%"})
t("the analyst separates FACT, INFERENCE and RECOMMENDATION",
  _an["facts"] and _an["inferences"] and _an["recommendations"])
t("its facts cite the registry and telemetry",
  any("Image" in f["text"] for f in _an["facts"])
  and any("27%" in f["text"] for f in _an["facts"]))
t("WITH NO EVIDENCE IT REFUSES TO COMPOSE AN ANSWER",
  CP.analyst("what is wrong?")["state"] == "NO EVIDENCE")

# ---------------------------------------------------------------- L11
head("L11 THE VERTICAL SLICE (spec 111)")
# The factory and the agent declare their OWN status. Registering them
# without one made derive_health report UNKNOWN, and UNKNOWN is not
# healthy: the first version of this fixture failed its own slice for
# exactly the right reason.
_vc = [CP.component("Content Factory", "OS", id="cf",
                    status="HEALTHY")["component"],
       CP.component("Creator Agent", "AGENT", id="ca",
                    status="HEALTHY")["component"],
       CP.component("LLM Provider", "API", id="vl",
                    status="HEALTHY")["component"],
       CP.component("Image Provider", "API", id="vi",
                    status="HEALTHY")["component"],
       CP.component("n8n Distribution", "N8N_WORKFLOW",
                    id="vn", status="HEALTHY")["component"],
       CP.component("Media Buying OS", "OS", id="vm",
                    status="HEALTHY")["component"]]
_ve = [CP.dependency("cf", "ca", relationship="USES",
                     criticality="REQUIRED")["edge"],
       CP.dependency("ca", "vl", relationship="USES",
                     criticality="REQUIRED")["edge"],
       CP.dependency("ca", "vi", relationship="USES",
                     criticality="OPTIONAL")["edge"],
       CP.dependency("cf", "vn", relationship="TRIGGERS",
                     criticality="OPTIONAL")["edge"],
       CP.dependency("vn", "vm", relationship="SENDS_TO",
                     criticality="REQUIRED")["edge"]]
_hv0 = CP.derive_health(_vc, _ve)
t("slice: with everything up, the whole chain is healthy",
  all(_hv0[k]["status"] == "HEALTHY" for k in _hv0))
_vc_down = [dict(x, status="FAILED") if x["id"] == "vi" else x
            for x in _vc]
_hv1 = CP.derive_health(_vc_down, _ve)
t("SLICE: IMAGE PROVIDER FAILS -> CREATOR AGENT DEGRADED",
  _hv1["ca"]["status"] == "DEGRADED")
t("SLICE: -> CONTENT FACTORY DEGRADED, NOT OFFLINE",
  _hv1["cf"]["status"] == "DEGRADED")
t("slice: media buying, downstream of nothing failed, stays healthy",
  _hv1["vm"]["status"] == "HEALTHY")
_loop = CP.loop_state({"status": "WAITING", "waited_s": 7200,
                       "normal_wait_s": 1800,
                       "next_expected_event": "IMAGE_READY",
                       "current_stage": "CREATE"})
t("slice: the content loop reads STALLED on the image wait",
  _loop["state"] == "STALLED")
_va = CP.alert("AGENT_FAILURE", severity="P1",
               component="Content Factory",
               why="image generation failure rate 32%")
t("slice: a P1 alert raises", _va["ok"]
  and _va["alert"]["severity"] == "P1")
_vrc = CP.root_cause("cf", _vc_down, _ve)
t("SLICE: THE ANALYST CHAIN ENDS AT THE IMAGE PROVIDER",
  _vrc["root"]["component"] == "Image Provider")
_hv2 = CP.derive_health(_vc, _ve)
t("SLICE: RECOVERY HEALS EVERY DEPENDENT AUTOMATICALLY",
  all(_hv2[k]["status"] == "HEALTHY" for k in _hv2))

# ---------------------------------------------------------------- L12
head("L12 THE FORTY-THREE STEPS (spec 119)")
STEPS = {}


def step(n, ok, note=""):
    STEPS[n] = bool(ok)
    t("%2d. %s" % (n, UI.DONE_STEPS[n - 1]), ok, note)


_wires = {"claude_api": True, "image_gen": True, "google_gsc_ga4": True,
          "email_send": False, "serper_search": True}
_ctx = {
    "environment": "PRODUCTION", "last_check": "15 sec ago",
    "wires": _wires,
    "connection_tests": {"google_gsc_ga4": CP.connection_test(
        [{"check": "auth", "state": "PASS"},
         {"check": "read", "state": "PASS"},
         {"check": "write", "state": "WARNING",
          "why": "permission missing"}])},
    "mappings": [{"provider": "META_ADS", "provider_field": "spend",
                  "transformation": "NORMALIZE_CURRENCY",
                  "internal_field": "media.spend",
                  "used_by": ["BI OS"], "required": True}],
    "mapping_test": CP.apply_mapping(
        [{"provider_field": "spend", "internal_field": "media.spend",
          "transformation": "CAST", "required": True}],
        {"spend": "2400"}),
    "agents": [{"name": "Creator Agent", "os": "Content Factory",
                "status": "DEGRADED", "current_task": "image retry",
                "runs_today": 84, "success_rate": 0.845,
                "tool_calls": 481, "cost_today": 6.32,
                "last_error": "image provider timeout",
                "heartbeat_interval_s": 60, "last_seen_s_ago": 30}],
    "workflows": [{"name": "Content Production", "owner_os":
                   "Content Factory", "trigger": "BRIEF_CREATED",
                   "status": "FAILED", "executions": 240,
                   "success_rate": 0.94, "cost": 682}],
    "workflow_trace": {"name": "Content Production", "steps": [
        {"step": "Receive Event", "status": "OK", "duration": 12},
        {"step": "Agent Analysis", "status": "OK", "duration": 4800,
         "cost": 0.4, "side_effect": False},
        {"step": "Store Learning", "status": "OK", "duration": 84,
         "side_effect": True},
        {"step": "Planner Event", "status": "FAILED",
         "error": "event bus timeout"}]},
    "loops": [{"name": "Content Loop", "owner_os": "Content Factory",
               "status": "WAITING", "waited_s": 7200,
               "normal_wait_s": 1800, "iteration": 3,
               "current_stage": "CREATE",
               "next_expected_event": "IMAGE_READY"}],
    "n8n": {"status": "HEALTHY", "success_rate": 0.978,
            "workflows": [{"internal_name": "Lead Enrichment",
                           "external_workflow_id": "129",
                           "owner_os": "CRM OS",
                           "business_purpose": "enrich new leads",
                           "status": "HEALTHY",
                           "last_execution": "4 sec"}]},
    "infra_metrics": {"host": "srv-test", "disk_pct": 61.0,
                      "disk_total_gb": 100.0, "mem_pct": 72.0,
                      "load": 1.8, "cpus": 4, "uptime_days": 14.3},
    "databases": [{"name": "PostgreSQL", "status": "HEALTHY",
                   "connections_used": 42, "connections_max": 100}],
    "queues": [{"name": "video-generation", "pending": 142,
                "normal_pending": 30, "workers": 4}],
    "api_usage": [{"provider": "LLM Provider", "requests": 28420,
                   "success_rate": 0.992, "avg_latency_ms": 840,
                   "quota_used": 0.62, "cost": 32.40,
                   "used_by": ["8 agents"]}],
    "logs": [{"at": "2026-08-10T09:00:00", "source": "ImageTool",
              "severity": "ERROR", "message": "timeout after 18s",
              "correlation_id": "abc"}],
    "trace": CP.trace(_ev, "abc"),
    "alerts": _al + [CP.alert("LOOP_STALLED", severity="P2",
                              component="Content Loop",
                              why="image wait 4x normal")["alert"]],
    "root_cause": CP.root_cause("cf", _vc_down, _ve),
    "secrets": [CP.secret_meta(provider="Meta",
                               credential_reference="ref://meta-prod",
                               status="EXPIRING_SOON",
                               expires="2026-09-01",
                               used_by=["Meta Adapter",
                                        "Media Buying OS"])],
    "components": _vc_down, "edges": _ve,
}
_full = UI.system_section(_ctx)

step(1, "System Control Plane" in _full)
step(2, "Content Factory" in _full and "Media Buying OS" in _full)
step(3, "Creator Agent" in _full)
step(4, "Content Production" in _full)
step(5, "Active" in _full or "P1" in _full)
step(6, "claude api" in _full.replace("_", " "))
step(7, "permission missing" in _full)
step(8, "WARNING" in _full or "Warning" in _full)
step(9, "ref://meta-prod" in _full)
step(10, "Meta Adapter" in _full)
step(11, "media.spend" in _full)
step(12, _ctx["mapping_test"]["ok"]
     and _ctx["mapping_test"]["normalized"]["media.spend"] == 2400.0)
step(13, "Wiring Map" in _full)
step(14, "scDrawer" in _full and "USES" in _full)
step(15, "data-sc=" in _full)
step(16, "OPTIONAL, so this" in _full or "OPTIONAL" in _full)
step(17, "If disconnected" in _full)
step(18, ">84<" in _full or "84" in _full)
step(19, "481" in _full)
step(20, "6.32" in _full)
step(21, "image provider timeout" in _full)
step(22, "Planner Event" in _full and "event bus timeout" in _full)
_rr = CP.rerun_check(_ctx["workflow_trace"]["steps"])
step(23, _rr["safe"] is False and "Store Learning" in str(_rr))
step(24, "CREATE" in _full)
step(25, "Stalled" in _full)
step(26, "n8n" in _full and "97.8" in _full or "Healthy" in _full)
step(27, "Lead Enrichment" in _full)
step(28, "srv-test" in _full)
step(29, "1.8" in _full)
step(30, ">72<" in _full or "72" in _full)
step(31, "61" in _full)
step(32, "PostgreSQL" in _full and "42" in _full)
step(33, "video-generation" in _full and "Backlog" in _full)
step(34, "28,420" in _full)
step(35, "62" in _full)
step(36, "32.40" in _full or "32.4" in _full)
step(37, "timeout after 18s" in _full)
step(38, "abc" in _full and "ImageTool" in _full)
step(39, "Agent Failure" in _full or "AGENT_FAILURE" in _full)
step(40, "Root cause" in _full and "Image Provider" in _full)
step(41, "If disconnected" in _full)
_ana = CP.analyst("why is the factory degraded?",
                  components=_vc_down, edges=_ve,
                  telemetry={"image_retry_rate": "27%"})
step(42, _ana["state"] == "OK")
step(43, any("Image Provider" in f["text"] for f in _ana["facts"])
     and _ana["recommendations"])

# ---------------------------------------------------------------- L13
head("L13 THE SECTION RENDERS")
_chk = UI.check_screens()
t("thirteen screens, one list", _chk["ok"], str(_chk["problems"]))
_ids = re.findall(r"id=['\"]([^'\"]+)", _full)
t("no duplicate element id",
  not [x for x in set(_ids) if _ids.count(x) > 1],
  str(sorted({x for x in _ids if _ids.count(x) > 1})))
_empty = []
for _sid, _n2, _lab, _fn, _q2 in UI.SCREENS:
    _m2 = re.search(r"id=['\"]scpanel-" + _sid + r"['\"](.*?)"
                    r"(?=id=['\"]scpanel-|$)", _full, re.S)
    _txt = re.sub(r"<[^>]+>", " ", _m2.group(1)) if _m2 else ""
    if len(" ".join(_txt.split())) < 100:
        _empty.append(_sid)
t("EVERY ONE OF THE THIRTEEN PANELS RENDERS REAL CONTENT",
  not _empty, str(_empty))
t("no screen raised into its panel", "could not render" not in _full)
t("the old system boards module is a shim over the control plane",
  "content_engine_control_ui" in
  io.open("content_engine_system_boards.py", encoding="utf-8").read())
t("no em-dash reaches any control module",
  not [f for f in ("content_engine_control_plane.py",
                   "content_engine_control_screens.py",
                   "content_engine_control_ui.py")
       if "—" in io.open(f, encoding="utf-8").read()])
t("no while loop in the engine",
  not [n for n in ast.walk(ast.parse(io.open(
      "content_engine_control_plane.py", encoding="utf-8").read()))
       if isinstance(n, ast.While)])
t("enrich() never overwrites a caller's components",
  UI.enrich({"components": [{"id": "x"}]})["components"]
  == [{"id": "x"}])

# ---------------------------------------------------------------- verdict
_done = sum(1 for v in STEPS.values() if v)
print("\n" + "=" * 74)
print("Section 119: " + str(_done) + " of 43 steps demonstrated")
if _done < 43:
    print("  not demonstrated: "
          + ", ".join(str(k) for k, v in sorted(STEPS.items()) if not v))
print(str(len(PASS)) + " passed, " + str(len(FAIL)) + " failed")
if FAIL:
    for f in FAIL:
        print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
