# -*- coding: utf-8 -*-
"""SYSTEM CONTROL PLANE: the engine.

Spec sections 0-2, 9-10, 13-17, 23, 26-27, 34, 41-42, 66-76, 82-95,
101-107, 112-118.

WHAT THIS IS AND IS NOT
-----------------------
BI answers "is the business healthy?". This answers "is the machine that
runs the business healthy?". Section 2 draws the boundary: the control
plane creates no content, runs no campaigns and sends no email. It shows
whether the systems that do are alive, what they depend on, what they
cost, and where a loop is stuck.

THE RULE THAT SHAPES THE HEALTH MODEL (section 2)
-------------------------------------------------
A failed OPTIONAL dependency degrades its dependent; a failed REQUIRED
dependency fails it. Content Factory with a dead image provider is
DEGRADED, not OFFLINE, because text still ships. Collapsing those two
states is how an operator restarts a system that was mostly working.

THE TRANSPARENCY RULE (section 112)
-----------------------------------
Who called what, why, when, what it cost, what it returned, whether it
succeeded, what depends on it, and what broke when it failed. Anything
here that cannot answer those is incomplete, and says so rather than
filling the gap with a guess.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _s(x) -> str:
    return "" if x is None else str(x)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _id(*parts) -> str:
    return hashlib.sha1("|".join(_s(p) for p in parts)
                        .encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# 82-83. THE REGISTRIES
# ===========================================================================
COMPONENT_TYPES = ("OS", "SERVICE", "AGENT", "WORKFLOW", "API", "TOOL",
                   "DATABASE", "QUEUE", "SERVER", "STORAGE", "WEBHOOK",
                   "N8N_WORKFLOW")

STATUSES = ("HEALTHY", "DEGRADED", "FAILED", "DISABLED", "UNKNOWN",
            "RUNNING", "OFFLINE")

#: Section 6. Status is never colour alone: icon AND word, always.
STATUS_MARK = {"HEALTHY": "● Healthy", "DEGRADED": "▲ Degraded",
               "FAILED": "● Failed", "RUNNING": "◌ Running",
               "DISABLED": "○ Disabled", "UNKNOWN": "? Unknown",
               "OFFLINE": "● Offline"}

#: Section 14. Every edge names its relationship; an unlabeled arrow on
#: a wiring map is decoration.
RELATIONSHIPS = ("USES", "CALLS", "SENDS_TO", "READS_FROM", "WRITES_TO",
                 "TRIGGERS", "DEPENDS_ON", "FALLBACK_TO")

CRITICALITY = ("REQUIRED", "OPTIONAL")


def component(name, ctype, *, owner_os="", environment="PRODUCTION",
              status="UNKNOWN", version="", id=None, **meta
              ) -> Dict[str, Any]:
    """One node in the system registry. Unknown types are refused, not
    coerced: a node of a type the map cannot draw is a modelling error
    worth hearing about at registration, not at render."""
    t = _s(ctype).upper()
    if t not in COMPONENT_TYPES:
        return {"ok": False,
                "why": ("'" + t + "' is not a component type. Choices: "
                        + ", ".join(COMPONENT_TYPES))}
    st = _s(status).upper()
    return {"ok": True, "component": {
        "id": id or _id(name, t), "name": _s(name),
        "component_type": t, "owner_os": _s(owner_os),
        "environment": _s(environment).upper() or "PRODUCTION",
        "status": st if st in STATUSES else "UNKNOWN",
        "version": _s(version), "metadata": dict(meta)}}


def dependency(source_id, target_id, *, relationship="DEPENDS_ON",
               criticality="REQUIRED", fallback_id=None,
               status="UNKNOWN") -> Dict[str, Any]:
    """One edge. Section 15: EDGES THEMSELVES CAN FAIL, so an edge
    carries its own status; two healthy services with a broken contract
    between them is an integration failure the nodes cannot show."""
    rel = _s(relationship).upper()
    if rel not in RELATIONSHIPS:
        return {"ok": False,
                "why": "'" + rel + "' is not an edge relationship"}
    crit = _s(criticality).upper()
    return {"ok": True, "edge": {
        "id": _id(source_id, target_id, rel),
        "source": _s(source_id), "target": _s(target_id),
        "relationship": rel,
        "criticality": crit if crit in CRITICALITY else "REQUIRED",
        "fallback_component_id": fallback_id,
        "status": _s(status).upper() or "UNKNOWN"}}


# ===========================================================================
# 2, 10. DERIVED HEALTH
# ===========================================================================
def derive_health(components, edges) -> Dict[str, Dict[str, Any]]:
    """Every component's EFFECTIVE status, with the reason attached.

    Propagation (section 2, 83):
      a REQUIRED dependency FAILED      -> dependent FAILED
      an OPTIONAL dependency FAILED     -> dependent DEGRADED
      any dependency DEGRADED           -> dependent DEGRADED
      a FAILED edge                     -> dependent DEGRADED
    A component's own reported failure always wins over propagation, and
    every derived status carries WHY, because a red node whose reason is
    three hops away is a diagnosis the operator has to redo by hand.
    """
    comps = {_d(c).get("id"): dict(_d(c)) for c in _l(components)}
    by_source: Dict[str, List[dict]] = {}
    for e in _l(edges):
        d = _d(e)
        by_source.setdefault(_s(d.get("source")), []).append(d)
    out: Dict[str, Dict[str, Any]] = {}

    def eff(cid, seen) -> Tuple[str, str]:
        if cid in out:
            return out[cid]["status"], out[cid]["why"]
        if cid in seen:
            return "UNKNOWN", "circular dependency at " + cid
        seen = seen | {cid}
        c = comps.get(cid)
        if c is None:
            return "UNKNOWN", "not in the registry"
        own = _s(c.get("status")).upper() or "UNKNOWN"
        if own in ("FAILED", "OFFLINE", "DISABLED"):
            out[cid] = {"status": own, "why": "its own reported state",
                        "own": own}
            return own, out[cid]["why"]
        worst, why = own, ("its own reported state" if own != "UNKNOWN"
                           else "no report and no failing dependency")
        for e in by_source.get(cid, ()):
            tst, _twhy = eff(_s(e.get("target")), seen)
            tname = _d(comps.get(_s(e.get("target")))).get(
                "name") or e.get("target")
            crit = _s(e.get("criticality"))
            if _s(e.get("status")).upper() == "FAILED":
                cand, cwhy = "DEGRADED", ("the " + _s(e.get("relationship"))
                                          + " edge to " + _s(tname)
                                          + " has failed even though "
                                          "both ends are up")
            elif tst in ("FAILED", "OFFLINE"):
                if crit == "REQUIRED":
                    cand, cwhy = "FAILED", (_s(tname) + " is down and is "
                                            "REQUIRED")
                else:
                    cand, cwhy = "DEGRADED", (_s(tname) + " is down but "
                                              "OPTIONAL, so this still "
                                              "partly works")
            elif tst == "DEGRADED":
                cand, cwhy = "DEGRADED", (_s(tname) + " is degraded "
                                          "beneath it")
            else:
                continue
            if _RANK.get(cand, 0) > _RANK.get(worst, 0):
                worst, why = cand, cwhy
        out[cid] = {"status": worst, "why": why, "own": own}
        return worst, why

    for cid in comps:
        eff(cid, frozenset())
    return out


_RANK = {"UNKNOWN": 0, "HEALTHY": 1, "RUNNING": 1, "DEGRADED": 2,
         "DISABLED": 2, "FAILED": 3, "OFFLINE": 3}


def health_score(area_components) -> Dict[str, Any]:
    """Section 9. A score that can always be expanded.

    The number is the mean of the per-area scores and NOTHING else; an
    unexplained 94% is a decoration, so the parts ship with the total.
    """
    areas = {}
    for area, statuses in _d(area_components).items():
        sts = [_s(x).upper() for x in _l(statuses)]
        if not sts:
            continue
        pts = [100 if s in ("HEALTHY", "RUNNING")
               else 50 if s in ("DEGRADED", "DISABLED")
               else 0 if s in ("FAILED", "OFFLINE") else None
               for s in sts]
        known = [p for p in pts if p is not None]
        areas[area] = (round(sum(known) / len(known)) if known else None)
    known_areas = {k: v for k, v in areas.items() if v is not None}
    if not known_areas:
        return {"score": None, "areas": areas,
                "why": ("every component is UNKNOWN, so there is no "
                        "score. Unknown is not healthy.")}
    total = round(sum(known_areas.values()) / len(known_areas))
    return {"score": total, "areas": areas,
            "state": ("HEALTHY" if total >= 90 else
                      "DEGRADED" if total >= 60 else "CRITICAL"),
            "why": ("the mean of " + str(len(known_areas)) + " area "
                    "scores; UNKNOWN components are excluded from the "
                    "arithmetic, not counted as healthy")}


# ===========================================================================
# 17. IMPACT ANALYSIS
# ===========================================================================
def impact(component_id, components, edges) -> Dict[str, Any]:
    """What breaks if this disconnects. Section 17: mandatory.

    Walks DEPENDENTS transitively and reports them by type, so
    "Disconnect SERP Provider?" answers with the four workflows, two
    agents and one OS that stop working, before the click.
    """
    comps = {_d(c).get("id"): _d(c) for c in _l(components)}
    if component_id not in comps:
        return {"ok": False, "why": _s(component_id)
                + " is not in the registry"}
    rev: Dict[str, List[str]] = {}
    for e in _l(edges):
        d = _d(e)
        rev.setdefault(_s(d.get("target")), []).append(_s(d.get("source")))
    # A bounded walk, not a while: each pass can only add components
    # that exist, so |components| passes reach the fixed point.
    hit = set(rev.get(component_id, ()))
    for _ in range(len(comps)):
        grew = False
        for cid in list(hit):
            for src in rev.get(cid, ()):
                if src not in hit:
                    hit.add(src)
                    grew = True
        if not grew:
            break
    by_type: Dict[str, List[str]] = {}
    for cid in sorted(hit):
        c = comps.get(cid, {})
        by_type.setdefault(_s(c.get("component_type")) or "UNKNOWN",
                           []).append(_s(c.get("name")) or cid)
    return {"ok": True, "component": comps[component_id].get("name"),
            "affected": by_type,
            "count": len(hit),
            "why": (("nothing depends on it; disconnecting is safe"
                     if not hit else
                     str(len(hit)) + " component(s) sit above it: "
                     + "; ".join(t + ": " + ", ".join(n)
                                 for t, n in sorted(by_type.items()))))}


# ===========================================================================
# 86. HEARTBEATS
# ===========================================================================
#: Missed beats before DEGRADED, and before OFFLINE. A single late beat
#: is jitter, not an outage.
HEARTBEAT_DEGRADED_AFTER = 2
HEARTBEAT_OFFLINE_AFTER = 5


def heartbeat_state(expected_interval_s, last_seen_s_ago) -> Dict:
    """What a silence means. Never-seen is UNKNOWN, not OFFLINE: a
    worker that has not started has not crashed."""
    iv, ago = _f(expected_interval_s), _f(last_seen_s_ago)
    if not iv or iv <= 0:
        return {"state": "UNKNOWN",
                "why": "no heartbeat interval is declared"}
    if ago is None:
        return {"state": "UNKNOWN",
                "why": ("never seen. A worker that has not started has "
                        "not crashed; those need different responses.")}
    missed = ago / iv
    if missed >= HEARTBEAT_OFFLINE_AFTER:
        return {"state": "OFFLINE", "missed": round(missed, 1),
                "why": (str(round(missed, 1)) + " intervals silent, past "
                        "the " + str(HEARTBEAT_OFFLINE_AFTER)
                        + "-interval threshold")}
    if missed >= HEARTBEAT_DEGRADED_AFTER:
        return {"state": "DEGRADED", "missed": round(missed, 1),
                "why": str(round(missed, 1)) + " intervals silent"}
    return {"state": "HEALTHY", "missed": round(missed, 1),
            "why": "last beat within tolerance"}


# ===========================================================================
# 87-88. WORKFLOW RUNS AND STEPS
# ===========================================================================
def workflow_trace(steps) -> Dict[str, Any]:
    """Section 37. The trace whose point is WHERE it failed."""
    rows = [_d(x) for x in _l(steps)]
    if not rows:
        return {"state": "NO STEPS", "why": "nothing recorded"}
    failed = [r for r in rows
              if _s(r.get("status")).upper() == "FAILED"]
    total_ms = sum(_f(r.get("duration"), 0) or 0 for r in rows)
    cost = sum(_f(r.get("cost"), 0) or 0 for r in rows)
    return {"state": "FAILED" if failed else "OK",
            "steps": rows,
            "failed_at": (_s(failed[0].get("step")) if failed else None),
            "duration_ms": total_ms, "cost": round(cost, 4),
            "why": (("failed at '" + _s(failed[0].get("step"))
                     + "': " + (_s(failed[0].get("error"))
                                or "no error recorded"))
                    if failed else
                    str(len(rows)) + " step(s) in "
                    + str(int(total_ms)) + "ms")}


def rerun_check(steps) -> Dict[str, Any]:
    """Section 38. Which steps are safe to re-run.

    A completed step with a side effect (send, publish, spend, write to
    an external system) re-run blindly creates duplicates, so the answer
    is per step and the risky ones are named.
    """
    risky = []
    for r in (_d(x) for x in _l(steps)):
        if (_s(r.get("status")).upper() != "FAILED"
                and r.get("side_effect")):
            risky.append(_s(r.get("step")))
    return {"safe": not risky, "risky_steps": risky,
            "why": ("every completed step is idempotent or effect-free"
                    if not risky else
                    "re-running would repeat side effect(s) at: "
                    + ", ".join(risky) + ". Retry the FAILED step only.")}


# ===========================================================================
# 41-42. LOOPS
# ===========================================================================
LOOP_STATES = ("RUNNING", "WAITING", "SUCCESSFUL", "DEGRADED", "STALLED",
               "FAILED", "STOPPED")

#: How many times the normal wait may elapse before WAITING is STALLED.
STALL_MULTIPLE = 3.0


def loop_state(run) -> Dict[str, Any]:
    """One loop's state, with stall detection. Section 42.

    WAITING and STALLED are different findings: one is the design
    working, the other is the design stuck, and the boundary is the
    declared normal wait times three, never a feeling.
    """
    r = _d(run)
    st = _s(r.get("status")).upper()
    waited = _f(r.get("waited_s"))
    normal = _f(r.get("normal_wait_s"))
    if st == "WAITING" and waited is not None and normal:
        if waited > normal * STALL_MULTIPLE:
            return {"state": "STALLED",
                    "stage": r.get("current_stage"),
                    "expected": r.get("next_expected_event"),
                    "waited_s": waited, "normal_s": normal,
                    "why": ("waiting on '"
                            + _s(r.get("next_expected_event"))
                            + "' for " + str(int(waited / 60)) + " min "
                            "against a normal " + str(int(normal / 60))
                            + " min. That is "
                            + str(round(waited / normal, 1))
                            + "x normal: stuck, not patient.")}
        return {"state": "WAITING", "stage": r.get("current_stage"),
                "expected": r.get("next_expected_event"),
                "why": ("waiting on '" + _s(r.get("next_expected_event"))
                        + "' within its normal window")}
    if st in LOOP_STATES:
        return {"state": st, "stage": r.get("current_stage"),
                "why": _s(r.get("why")) or ("reported " + st.lower())}
    return {"state": "STOPPED", "stage": r.get("current_stage"),
            "why": "'" + st + "' is not a loop state; treated as stopped"}


# ===========================================================================
# 66-67. CORRELATION TRACE
# ===========================================================================
def trace(events, correlation_id) -> Dict[str, Any]:
    """Every event sharing one correlation id, as one timeline.

    Section 66: this is how "who called what, when, and what came back"
    is answered across systems without reading five logs.
    """
    cid = _s(correlation_id)
    rows = sorted((_d(e) for e in _l(events)
                   if _s(_d(e).get("correlation_id")) == cid),
                  key=lambda x: _s(x.get("at")))
    if not rows:
        return {"state": "NOT FOUND", "correlation_id": cid,
                "why": ("no event carries this correlation id. Either it "
                        "never ran, or a system in the chain is not "
                        "propagating the id, which is itself a finding.")}
    failed = [r for r in rows if _s(r.get("status")).upper() == "FAILED"]
    return {"state": "FAILED" if failed else "OK",
            "correlation_id": cid, "events": rows,
            "systems": sorted({_s(r.get("source")) for r in rows}),
            "cost": round(sum(_f(r.get("cost"), 0) or 0 for r in rows), 4),
            "why": (str(len(rows)) + " event(s) across "
                    + str(len({_s(r.get('source')) for r in rows}))
                    + " system(s)"
                    + ((", failing at " + _s(failed[0].get("source")))
                       if failed else ""))}


# ===========================================================================
# 68-73. ALERTS AND ROOT CAUSE
# ===========================================================================
ALERT_TYPES = ("API_DOWN", "AGENT_FAILURE", "WORKFLOW_FAILURE",
               "LOOP_STALLED", "SERVER_HIGH_CPU", "MEMORY_HIGH",
               "DISK_HIGH", "QUEUE_BACKLOG", "DATABASE_ERROR",
               "CREDENTIAL_EXPIRING", "QUOTA_NEAR_LIMIT", "COST_SPIKE",
               "ERROR_RATE_SPIKE", "WEBHOOK_FAILURE", "N8N_FAILURE")

SEVERITIES = ("P0", "P1", "P2", "P3", "P4")


def alert(atype, *, severity, component, why, at="") -> Dict[str, Any]:
    t, sv = _s(atype).upper(), _s(severity).upper()
    if t not in ALERT_TYPES:
        return {"ok": False, "why": "'" + t + "' is not an alert type"}
    if sv not in SEVERITIES:
        return {"ok": False, "why": "'" + sv + "' is not a severity"}
    return {"ok": True, "alert": {
        # Dedup key deliberately excludes the timestamp (section 71): the
        # same failure firing every minute is one incident, not sixty.
        "id": _id(t, component),
        "type": t, "severity": sv, "component": _s(component),
        "why": _s(why), "at": _s(at), "status": "ACTIVE"}}


def dedupe_alerts(alerts) -> List[Dict[str, Any]]:
    """Section 71. One card per (type, component), first occurrence kept,
    count carried. Sixty copies of one failure is how alerts get muted
    and the sixty-first, different one gets missed."""
    seen: Dict[str, dict] = {}
    for a in (_d(x) for x in _l(alerts)):
        key = _s(a.get("id")) or _id(a.get("type"), a.get("component"))
        if key in seen:
            seen[key]["occurrences"] += 1
            seen[key]["last_at"] = a.get("at")
        else:
            seen[key] = dict(a, occurrences=1, last_at=a.get("at"))
    return sorted(seen.values(),
                  key=lambda x: SEVERITIES.index(_s(x.get("severity"))
                                                 if _s(x.get("severity"))
                                                 in SEVERITIES else "P4"))


def root_cause(component_id, components, edges, health=None
               ) -> Dict[str, Any]:
    """Section 73. The chain from a sick component down to why.

    Walks the unhealthy dependencies until it reaches one whose problem
    is its OWN, and reports the chain: degraded because X, because Y,
    because Z's latency. The last link is the one to fix.
    """
    comps = {_d(c).get("id"): _d(c) for c in _l(components)}
    h = health or derive_health(components, edges)
    by_source: Dict[str, List[dict]] = {}
    for e in _l(edges):
        by_source.setdefault(_s(_d(e).get("source")), []).append(_d(e))
    chain, cur, seen = [], _s(component_id), set()
    # Bounded by the component count: a chain cannot be longer than the
    # registry, and the seen-set breaks cycles.
    for _ in range(len(comps) + 1):
        if not cur or cur in seen:
            break
        seen.add(cur)
        st = _d(h.get(cur))
        chain.append({"component": _d(comps.get(cur)).get("name") or cur,
                      "status": st.get("status"),
                      "why": st.get("why")})
        nxt = None
        for e in by_source.get(cur, ()):
            tid = _s(e.get("target"))
            tst = _s(_d(h.get(tid)).get("status"))
            if tst in ("FAILED", "OFFLINE", "DEGRADED"):
                nxt = tid
                break
        cur = nxt
    return {"chain": chain,
            "root": chain[-1] if chain else None,
            "why": (" because ".join(_s(c["component"]) + " is "
                                     + _s(c["status"]).lower()
                                     for c in chain)
                    if len(chain) > 1 else
                    "the problem is this component's own, not inherited")}


# ===========================================================================
# 74-76. SECRETS: METADATA ONLY
# ===========================================================================
SECRET_STATES = ("VALID", "EXPIRING_SOON", "EXPIRED", "INVALID",
                 "PERMISSION_CHANGED", "UNKNOWN")


def mask(value) -> str:
    """sk-....4dk2. The middle never survives, whatever the length."""
    v = _s(value)
    if not v:
        return "not set"
    if len(v) <= 8:
        return "•" * 8
    return v[:3] + "•" * 8 + v[-4:]


def secret_meta(*, provider, credential_reference, environment="PRODUCTION",
                status="UNKNOWN", created="", last_used="", expires="",
                used_by=()) -> Dict[str, Any]:
    """Credential METADATA. The value is not a parameter on purpose: a
    function that never receives a secret cannot leak one."""
    st = _s(status).upper()
    return {"provider": _s(provider),
            "credential_reference": _s(credential_reference),
            "environment": _s(environment).upper(),
            "status": st if st in SECRET_STATES else "UNKNOWN",
            "created": _s(created), "last_used": _s(last_used),
            "expires": _s(expires),
            "used_by": [_s(x) for x in _l(used_by)]}


# ===========================================================================
# 23. CONNECTION TEST
# ===========================================================================
def connection_test(checks) -> Dict[str, Any]:
    """Roll one connection's checks up. FAIL beats WARNING beats PASS,
    and a missing permission is a WARNING with its name, because "test
    passed" over a write permission that is absent is the lie that
    surfaces at campaign launch."""
    rows = [_d(c) for c in _l(checks)]
    if not rows:
        return {"state": "FAIL", "why": "no check ran, which is a "
                "failure and not a pass"}
    states = [_s(r.get("state")).upper() for r in rows]
    state = ("FAIL" if "FAIL" in states
             else "WARNING" if "WARNING" in states else "PASS")
    bad = [r for r in rows if _s(r.get("state")).upper() != "PASS"]
    return {"state": state, "checks": rows,
            "why": ("every check passed" if not bad else
                    "; ".join(_s(b.get("check")) + ": "
                              + _s(b.get("why")) for b in bad)[:300])}


# ===========================================================================
# 26-27. DATA MAPPING
# ===========================================================================
TRANSFORMS = ("DIRECT", "RENAME", "CAST", "NORMALIZE_CURRENCY",
              "NORMALIZE_DATE", "ENUM_MAP", "DERIVED", "LOOKUP",
              "CUSTOM_FUNCTION")


def apply_mapping(mapping_rows, provider_payload) -> Dict[str, Any]:
    """Section 27. Test a mapping on a sample. Refuses to activate when a
    required field is missing from the sample, and never invents one."""
    src = _d(provider_payload)
    out, problems = {}, []
    for m in (_d(x) for x in _l(mapping_rows)):
        pf = _s(m.get("provider_field"))
        tf = _s(m.get("internal_field"))
        tr = _s(m.get("transformation")).upper() or "DIRECT"
        if tr not in TRANSFORMS:
            problems.append(pf + ": unknown transformation " + tr)
            continue
        if pf not in src:
            if m.get("required"):
                problems.append(pf + ": required and absent from the "
                                     "sample")
            continue
        val = src[pf]
        if tr == "CAST":
            val = _f(val, val)
        out[tf] = val
    return {"ok": not problems, "normalized": out,
            "problems": problems,
            "why": ("mapping produces " + str(len(out)) + " field(s)"
                    if not problems else
                    "NOT ACTIVATED: " + "; ".join(problems))}


# ===========================================================================
# 52, 91. REAL LOCAL INFRASTRUCTURE METRICS
# ===========================================================================
def local_metrics() -> Dict[str, Any]:
    """What this box can measure about itself, honestly.

    Reads /proc and the filesystem, which exist inside the container on
    the VPS. A metric the platform cannot supply is None with the
    reason, never a plausible number: on Windows there is no /proc and
    the load average is reported as unavailable, not as 0.0.
    """
    out: Dict[str, Any] = {"host": os.getenv("HOSTNAME") or "unknown"}
    try:
        import shutil
        du = shutil.disk_usage("/")
        out["disk_pct"] = round(du.used / du.total * 100, 1)
        out["disk_total_gb"] = round(du.total / 1e9, 1)
    except Exception:                                 # noqa: BLE001
        out["disk_pct"] = None
    try:
        out["load"] = round(os.getloadavg()[0], 2)
        out["cpus"] = os.cpu_count()
    except (AttributeError, OSError):
        out["load"] = None
        out["load_why"] = ("the platform does not expose a load average "
                           "(no /proc here); reported as unavailable, "
                           "not as zero")
    try:
        mem = {}
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                mem[k.strip()] = _f(v.split()[0]) if v.split() else None
        tot, avail = mem.get("MemTotal"), mem.get("MemAvailable")
        if tot and avail is not None:
            out["mem_pct"] = round((tot - avail) / tot * 100, 1)
            out["mem_total_gb"] = round(tot / 1e6, 1)
    except OSError:
        out["mem_pct"] = None
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            out["uptime_days"] = round(_f(fh.read().split()[0], 0)
                                       / 86400, 1)
    except OSError:
        out["uptime_days"] = None
    return out


def infra_state(m) -> Dict[str, Any]:
    """Judge the metrics that exist; say nothing about the ones that do
    not. Thresholds: disk and memory over 90 is critical, over 75
    degraded; load over 2x cores degraded."""
    d = _d(m)
    problems, judged = [], 0
    disk = _f(d.get("disk_pct"))
    if disk is not None:
        judged += 1
        if disk >= 90:
            problems.append("disk at " + str(disk) + "%")
        elif disk >= 75:
            problems.append("disk filling: " + str(disk) + "%")
    mem = _f(d.get("mem_pct"))
    if mem is not None:
        judged += 1
        if mem >= 90:
            problems.append("memory at " + str(mem) + "%")
    load, cpus = _f(d.get("load")), _f(d.get("cpus"))
    if load is not None and cpus:
        judged += 1
        if load > cpus * 2:
            problems.append("load " + str(load) + " on "
                            + str(int(cpus)) + " cpu(s)")
    if judged == 0:
        return {"state": "UNKNOWN",
                "why": "no metric could be measured on this platform"}
    crit = [p for p in problems if "at 9" in p or " at " in p and
            _f(p.split(" at ")[-1].rstrip("%"), 0) >= 90]
    return {"state": ("FAILED" if crit else
                      "DEGRADED" if problems else "HEALTHY"),
            "judged": judged, "problems": problems,
            "why": ("; ".join(problems) if problems else
                    str(judged) + " metric(s) measured, all within "
                    "bounds")}


# ===========================================================================
# 56-57. QUEUES
# ===========================================================================
def queue_state(*, pending, normal_pending, oldest_s=None,
                workers=None) -> Dict[str, Any]:
    p, n = _f(pending, 0) or 0, _f(normal_pending)
    if not n or n <= 0:
        return {"state": "UNKNOWN", "pending": p,
                "why": ("no normal depth is declared, so buildup cannot "
                        "be told from busy")}
    if p > n * 3:
        return {"state": "BACKLOG", "pending": p,
                "why": (str(int(p)) + " pending against a normal "
                        + str(int(n)) + ". "
                        + ("Workers: " + _s(workers) + ". " if workers
                           is not None else "")
                        + "Possible cause: a worker is down or slow.")}
    return {"state": "HEALTHY", "pending": p,
            "why": str(int(p)) + " pending, within the normal "
                   + str(int(n))}


# ===========================================================================
# 94, 101-102. EVENTS, PERMISSIONS, THE AI FENCE
# ===========================================================================
SYSTEM_EVENTS = ("COMPONENT_HEALTH_CHANGED", "CONNECTION_FAILED",
                 "CONNECTION_RECOVERED", "AGENT_FAILED",
                 "AGENT_RECOVERED", "WORKFLOW_FAILED",
                 "WORKFLOW_RECOVERED", "LOOP_STALLED", "LOOP_COMPLETED",
                 "SERVER_DEGRADED", "QUEUE_BACKLOG",
                 "CREDENTIAL_EXPIRING", "COST_SPIKE", "API_RATE_LIMIT",
                 "DEPLOYMENT_COMPLETED")

ROLES = ("OWNER", "SYSTEM_ADMIN", "DEVELOPER", "OPERATOR", "VIEWER")

PERMISSIONS = ("VIEW_SYSTEM_MAP", "MANAGE_CONNECTIONS",
               "VIEW_SECRET_METADATA", "ROTATE_SECRET",
               "RESTART_SERVICE", "MANAGE_WORKFLOW", "RETRY_RUN",
               "MANAGE_AGENT", "VIEW_LOGS", "MANAGE_INFRASTRUCTURE")

ROLE_GRANTS = {
    "OWNER": PERMISSIONS,
    "SYSTEM_ADMIN": PERMISSIONS,
    "DEVELOPER": ("VIEW_SYSTEM_MAP", "MANAGE_CONNECTIONS",
                  "VIEW_SECRET_METADATA", "MANAGE_WORKFLOW", "RETRY_RUN",
                  "MANAGE_AGENT", "VIEW_LOGS"),
    "OPERATOR": ("VIEW_SYSTEM_MAP", "RETRY_RUN", "VIEW_LOGS"),
    "VIEWER": ("VIEW_SYSTEM_MAP",),
}


def can(role, permission) -> bool:
    return _s(permission).upper() in ROLE_GRANTS.get(_s(role).upper(), ())


#: Section 102. What the AI may never do on its own, whatever it is
#: asked. Diagnose yes; destroy no.
AI_FORBIDDEN = ("delete_credential", "restart_database",
                "destroy_container", "delete_storage",
                "rotate_production_secret", "restart_vps")


def ai_may(action) -> Dict[str, Any]:
    a = _s(action).lower()
    if a in AI_FORBIDDEN:
        return {"ok": False,
                "why": ("'" + a + "' is forbidden to the AI without "
                        "explicit human approval. The analyst diagnoses "
                        "and recommends; it does not operate the "
                        "machinery.")}
    return {"ok": True, "why": "diagnostic action"}


# ===========================================================================
# 103-105. THE SYSTEM ANALYST
# ===========================================================================
def analyst(question, *, components=(), edges=(), telemetry=None
            ) -> Dict[str, Any]:
    """One analyst, section 103. Telemetry first, FACT/INFERENCE/
    RECOMMENDATION always separated (section 105).

    A FACT cites a measured number from the registry or telemetry. If
    the telemetry cannot support an answer, the analyst says what is
    missing instead of composing something fluent.
    """
    q = _s(question).lower()
    h = derive_health(components, edges)
    comps = {_d(c).get("id"): _d(c) for c in _l(components)}
    tel = _d(telemetry)
    sick = [(cid, st) for cid, st in h.items()
            if _s(st.get("status")) in ("DEGRADED", "FAILED", "OFFLINE")]
    facts, inferences, recommendations = [], [], []
    for cid, st in sick:
        name = _d(comps.get(cid)).get("name") or cid
        facts.append({"kind": "FACT",
                      "text": _s(name) + " is "
                      + _s(st.get("status")).lower() + ": "
                      + _s(st.get("why"))})
    for key, val in tel.items():
        facts.append({"kind": "FACT", "text": _s(key) + " = " + _s(val)})
    if sick:
        # Explain the TOP of the cascade, not the leaf. The sick list
        # arrives in recursion order, so its first element is often the
        # failed leaf whose chain is itself; the component with the
        # LONGEST root-cause chain is the one the operator is asking
        # about, and its chain ends at that leaf.
        chains = [(cid, root_cause(cid, components, edges, health=h))
                  for cid, _st in sick]
        cid, rc = max(chains,
                      key=lambda x: len(_l(_d(x[1]).get("chain"))))
        if rc.get("root") and len(rc.get("chain", ())) > 1:
            inferences.append({"kind": "INFERENCE",
                               "text": ("the likely root is "
                                        + _s(_d(rc["root"])
                                             .get("component"))
                                        + ", reached through: "
                                        + _s(rc["why"]))})
            recommendations.append({"kind": "RECOMMENDATION",
                                    "text": ("inspect "
                                             + _s(_d(rc["root"])
                                                  .get("component"))
                                             + " first; everything "
                                             "above it is downstream")})
    if not facts:
        return {"state": "NO EVIDENCE", "question": _s(question),
                "facts": [], "inferences": [], "recommendations": [],
                "why": ("the registry and telemetry hold nothing that "
                        "bears on this. The analyst does not compose an "
                        "answer without evidence.")}
    return {"state": "OK", "question": _s(question),
            "facts": facts, "inferences": inferences,
            "recommendations": recommendations,
            "why": (str(len(facts)) + " fact(s), "
                    + str(len(inferences)) + " inference(s), "
                    + str(len(recommendations)) + " recommendation(s), "
                    "kept apart because a guess promoted to a fact gets "
                    "acted on as one")}


# ===========================================================================
# 82-93, 102. THE TABLES
# ===========================================================================
TABLES = ("system_components", "system_dependencies", "health_checks",
          "agent_heartbeats", "workflow_runs", "workflow_run_steps",
          "system_loops", "loop_runs", "n8n_instances", "n8n_workflows",
          "infrastructure_nodes", "connections", "connection_mappings",
          "incidents")
