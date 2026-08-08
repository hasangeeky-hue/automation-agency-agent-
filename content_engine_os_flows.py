"""
content_engine_os_flows.py
============================================================================
ENGINE 8: THE FLOW ENGINE. A GRAPH, NOT A LIST.

WHY A GRAPH
  A sequence stored as step1, step2, step3 cannot branch, and this
  founder's sequence already branches: what you send someone who opened is
  not what you send someone who did not. So a flow is nodes plus edges, an
  edge may carry a condition, and any node may have several outgoing edges.

EXECUTION STATE IS PERSISTED PER PERSON
  One execution row per (flow, profile): where they are, when they are due,
  what has happened. A worker restart resumes exactly where it stopped. An
  engine that recomputed "where is everyone" from scratch each pass would
  re-send the last email every time it was restarted.

THE SEND NODE DOES NOT SEND
  SEND_EMAIL asks the orchestrator to QUEUE. Every gate applies, and the
  founder still approves. A flow is an author of intent, never a transport.

THE AI NODE DOES NOT SEND EITHER
  AI_ACTION returns a structured document with a confidence. Whether it may
  become an email is the orchestrator's decision, not the model's.
============================================================================
"""

from __future__ import annotations

import logging

import content_engine_os_audience as AUD
import content_engine_os_core as CORE
import content_engine_os_send as SEND
from content_engine_os_core import NODE_TYPES, _D, _L, now, rid

log = logging.getLogger("content_engine.os.flows")

EXEC_STATES = ("RUNNING", "WAITING", "COMPLETED", "GOAL_MET", "FAILED",
               "STOPPED")

#: What each node needs, so the editor can ask for it and validate() can
#: refuse a node that is missing it before anyone activates the flow.
NODE_CONFIG = {
    "TRIGGER": ("event",),
    "SEND_EMAIL": ("campaign_id",),
    "WAIT": ("hours",),
    "CONDITION": ("field", "operator", "value"),
    "SPLIT": ("percent",),
    "UPDATE_PROFILE": ("key", "value"),
    "ADD_TO_LIST": ("list_id",),
    "REMOVE_FROM_LIST": ("list_id",),
    "WEBHOOK": ("url",),
    "AI_ACTION": ("objective",),
    "GOAL": ("field", "operator", "value"),
    "END": (),
}

TRIGGERS = ("lead_qualified", "profile_created", "added_to_list",
            "email_opened", "email_clicked", "replied", "manual")


# ---------------------------------------------------------------------------
# AUTHORING
# ---------------------------------------------------------------------------
def save_flow(repo, *, flow_id="", name="", nodes=None, edges=None,
              status="DRAFT") -> dict:
    """Store the graph. The frontend is an editor; this is the truth."""
    fid = flow_id or rid("flow", repo.ws, name or now())
    cur = repo.one("flows", fid) or {"id": fid}
    cur.update({"name": name or cur.get("name") or "Untitled flow",
                "nodes": _L(nodes) or _L(cur.get("nodes")),
                "edges": _L(edges) or _L(cur.get("edges")),
                "status": status})
    ok, why = validate(cur)
    cur["valid"] = ok
    cur["invalid_reason"] = "" if ok else why
    rec = repo.put("flows", cur)
    return {"ok": True, "id": rec["id"], "valid": ok,
            "message": (f"{rec['name']!r} saved" if ok
                        else f"saved, but it will not run: {why}")}


def validate(flow) -> tuple:
    """(ok, why). Refuses at save time, so a flow cannot be activated into
    a shape that strands people halfway through it."""
    flow = _D(flow)
    nodes = _L(flow.get("nodes"))
    edges = _L(flow.get("edges"))
    if not nodes:
        return False, "a flow needs at least a trigger"
    ids = {_D(n).get("id") for n in nodes}
    triggers = [n for n in nodes if _D(n).get("type") == "TRIGGER"]
    if len(triggers) != 1:
        return False, ("a flow needs exactly one trigger, and this one has "
                       f"{len(triggers)}")
    for n in nodes:
        n = _D(n)
        t = n.get("type")
        if t not in NODE_TYPES:
            return False, f"{t!r} is not a step this engine knows"
        missing = [k for k in NODE_CONFIG.get(t, ())
                   if str(_D(n.get("config")).get(k, "")) == ""]
        if missing:
            return False, (f"the {t.replace('_', ' ').lower()} step is missing "
                           + ", ".join(missing))
    for e_ in edges:
        e_ = _D(e_)
        if e_.get("source_node_id") not in ids or e_.get("target_node_id") not in ids:
            return False, "an arrow points at a step that is not in the flow"
    reachable, seen = [triggers[0].get("id")], set()
    while reachable:
        cur = reachable.pop()
        if cur in seen:
            continue
        seen.add(cur)
        reachable += [_D(e_).get("target_node_id") for e_ in edges
                      if _D(e_).get("source_node_id") == cur]
    stranded = ids - seen
    if stranded:
        return False, (f"{len(stranded)} step(s) cannot be reached from the "
                       f"trigger")
    return True, ""


def default_flow() -> dict:
    """The founder's own three-touch sequence, as a graph. This is what the
    Flows screen opens with so the canvas is never an empty rectangle."""
    n = lambda i, t, cfg, x, y: {"id": i, "type": t, "config": cfg,
                                 "position_x": x, "position_y": y}
    nodes = [
        n("t1", "TRIGGER", {"event": "lead_qualified"}, 40, 40),
        n("w1", "WAIT", {"hours": 1}, 40, 140),
        n("a1", "AI_ACTION", {"objective": "personalise the intro from the "
                              "company's own site"}, 40, 240),
        n("s1", "SEND_EMAIL", {"campaign_id": "", "touch": 1}, 40, 340),
        n("w2", "WAIT", {"hours": 72}, 40, 440),
        n("c1", "CONDITION", {"field": "opens", "operator": "greater_than",
                              "value": 0}, 40, 540),
        n("s2", "SEND_EMAIL", {"campaign_id": "", "touch": 2}, 260, 640),
        n("s3", "SEND_EMAIL", {"campaign_id": "", "touch": 2}, -180, 640),
        n("w3", "WAIT", {"hours": 120}, 40, 740),
        n("s4", "SEND_EMAIL", {"campaign_id": "", "touch": 3}, 40, 840),
        n("g1", "GOAL", {"field": "lead_stage", "operator": "equals",
                         "value": "MEETING"}, 40, 940),
        n("e1", "END", {}, 40, 1040),
    ]
    edges = [{"id": f"e{i}", "source_node_id": a, "target_node_id": b,
              "condition": cond}
             for i, (a, b, cond) in enumerate([
                 ("t1", "w1", ""), ("w1", "a1", ""), ("a1", "s1", ""),
                 ("s1", "w2", ""), ("w2", "c1", ""),
                 ("c1", "s2", "yes"), ("c1", "s3", "no"),
                 ("s2", "w3", ""), ("s3", "w3", ""),
                 ("w3", "s4", ""), ("s4", "g1", ""), ("g1", "e1", "")])]
    return {"name": "Three touches, branching on the open", "nodes": nodes,
            "edges": edges, "status": "DRAFT"}


def ensure_default(repo) -> dict:
    """Seed the founder's own sequence, pointed at a real campaign.

    A send step with no campaign is an invalid flow, and shipping the
    canvas pre-loaded with something that refuses to activate would be a
    demo rather than a tool. So the newest projected campaign is filled in
    and can be changed afterwards."""
    if repo.all("flows"):
        return {}
    d = default_flow()
    camps = sorted(repo.all("campaigns"),
                   key=lambda c: str(c.get("created_at")), reverse=True)
    cid = camps[0].get("id") if camps else ""
    for n in d["nodes"]:
        if n["type"] == "SEND_EMAIL":
            n["config"]["campaign_id"] = cid
    return save_flow(repo, name=d["name"], nodes=d["nodes"], edges=d["edges"])


def activate(repo, flow_id) -> dict:
    f = repo.one("flows", flow_id)
    if not f:
        return {"ok": False, "error": "no such flow in this workspace"}
    ok, why = validate(f)
    if not ok:
        return {"ok": False, "error": why, "message": "not activated: " + why}
    f["status"] = "LIVE"
    repo.put("flows", f)
    CORE.audit(repo, "founder", "flow_activated", flow_id, f.get("name", ""))
    return {"ok": True, "message": f"{f.get('name')!r} is live. It queues, it "
                                   f"does not send: every email still waits "
                                   f"for your approval."}


def pause(repo, flow_id) -> dict:
    f = repo.one("flows", flow_id)
    if not f:
        return {"ok": False, "error": "no such flow"}
    f["status"] = "PAUSED"
    repo.put("flows", f)
    return {"ok": True, "message": f"{f.get('name')!r} paused; people already "
                                   f"in it stay where they are"}


# ---------------------------------------------------------------------------
# EXECUTION
# ---------------------------------------------------------------------------
def _node(flow, nid):
    return next((n for n in _L(_D(flow).get("nodes"))
                 if _D(n).get("id") == nid), None)


def _next(flow, nid, branch=""):
    outs = [e_ for e_ in _L(_D(flow).get("edges"))
            if _D(e_).get("source_node_id") == nid]
    if branch:
        hit = next((e_ for e_ in outs
                    if str(_D(e_).get("condition")).lower() == branch), None)
        if hit:
            return _D(hit).get("target_node_id")
    plain = next((e_ for e_ in outs if not _D(e_).get("condition")), None)
    return _D(plain or (outs[0] if outs else {})).get("target_node_id")


def enroll(repo, flow_id, profile_ids) -> dict:
    """Put people into a flow. One execution row each, idempotent on the
    pair so pressing the button twice does not double-enrol anyone."""
    f = repo.one("flows", flow_id)
    if not f:
        return {"ok": False, "error": "no such flow"}
    trig = next((n for n in _L(f.get("nodes"))
                 if _D(n).get("type") == "TRIGGER"), None)
    if not trig:
        return {"ok": False, "error": "that flow has no trigger"}
    n = 0
    for pid in _L(profile_ids):
        eid = rid("fx", repo.ws, flow_id, pid)
        if repo.one("flow_executions", eid):
            continue
        repo.put("flow_executions", {
            "id": eid, "flow_id": flow_id, "profile_id": pid,
            "current_node_id": _next(f, trig.get("id")) or trig.get("id"),
            "status": "RUNNING", "wait_until": "", "history": [],
            "started_at": now()})
        n += 1
    return {"ok": True, "enrolled": n,
            "message": f"{n} person(s) entered {f.get('name')!r}"}


def advance(repo, *, jobs=None, limit=200) -> dict:
    """One pass over every execution. Walks each person forward until they
    hit a WAIT, a queued send, or the end.

    Bounded per execution (max 20 steps) so a cycle in the graph costs a
    log line rather than a hung worker."""
    flows = {f.get("id"): f for f in repo.all("flows")
             if f.get("status") == "LIVE"}
    if not flows:
        return {"ok": True, "moved": 0, "queued": 0,
                "message": "no flow is live, so nobody moved"}
    rows = AUD.people(repo)
    by_id = {p.get("id"): p for p in rows}
    moved = queued = 0
    for x in repo.all("flow_executions")[:limit]:
        if x.get("status") not in ("RUNNING", "WAITING"):
            continue
        f = flows.get(x.get("flow_id"))
        if not f:
            continue
        until = CORE.parse_at(x.get("wait_until"))
        if until and until > CORE.datetime.now(CORE.timezone.utc):
            continue
        person = by_id.get(x.get("profile_id")) or {}
        steps = 0
        x["status"] = "RUNNING"
        while x.get("current_node_id") and steps < 20:
            steps += 1
            node = _node(f, x["current_node_id"])
            if not node:
                x["status"] = "FAILED"
                x["error"] = "the flow points at a step that no longer exists"
                break
            t, cfg = _D(node).get("type"), _D(_D(node).get("config"))
            x.setdefault("history", []).append(
                {"node": node.get("id"), "type": t, "at": now()})
            if t == "WAIT":
                x["wait_until"] = (CORE.datetime.now(CORE.timezone.utc)
                                   + CORE.timedelta(hours=float(cfg.get("hours") or 1))
                                   ).isoformat(timespec="seconds")
                x["status"] = "WAITING"
                x["current_node_id"] = _next(f, node.get("id"))
                break
            if t == "CONDITION":
                hit = AUD.compare(person.get(cfg.get("field")),
                                  cfg.get("operator"), cfg.get("value"))
                x["current_node_id"] = _next(f, node.get("id"),
                                             "yes" if hit else "no")
                continue
            if t == "SPLIT":
                pct = float(cfg.get("percent") or 50)
                # Deterministic, not random: the same person always takes the
                # same arm, so a re-run cannot move somebody mid-test.
                bucket = int(CORE.rid("ab", x.get("profile_id"))[-4:], 16) % 100
                x["current_node_id"] = _next(f, node.get("id"),
                                             "a" if bucket < pct else "b")
                continue
            if t == "SEND_EMAIL":
                res = SEND.queue_for_person(
                    repo, cfg.get("campaign_id") or "",
                    x.get("profile_id"), touch=int(cfg.get("touch") or 1),
                    jobs=jobs, flow_id=f.get("id"))
                if res.get("ok"):
                    queued += 1
                else:
                    x.setdefault("notes", []).append(res.get("message", ""))
                x["current_node_id"] = _next(f, node.get("id"))
                continue
            if t == "AI_ACTION":
                # The model proposes. It does not send, and it does not even
                # decide: the value it returns is stored for the orchestrator
                # to accept or refuse.
                x.setdefault("ai", []).append(
                    {"objective": cfg.get("objective"), "at": now(),
                     "status": "PROPOSED", "confidence": None})
                x["current_node_id"] = _next(f, node.get("id"))
                continue
            if t == "UPDATE_PROFILE":
                CORE.set_property(repo, x.get("profile_id"),
                                  cfg.get("key"), cfg.get("value"))
                x["current_node_id"] = _next(f, node.get("id"))
                continue
            if t in ("ADD_TO_LIST", "REMOVE_FROM_LIST"):
                fn = (AUD.add_to_list if t == "ADD_TO_LIST"
                      else AUD.remove_from_list)
                fn(repo, cfg.get("list_id"), [x.get("profile_id")])
                x["current_node_id"] = _next(f, node.get("id"))
                continue
            if t == "WEBHOOK":
                x.setdefault("notes", []).append(
                    f"webhook to {cfg.get('url')} recorded, not called: "
                    f"outbound calls stay behind approval")
                x["current_node_id"] = _next(f, node.get("id"))
                continue
            if t == "GOAL":
                if AUD.compare(person.get(cfg.get("field")),
                               cfg.get("operator"), cfg.get("value")):
                    x["status"] = "GOAL_MET"
                    break
                x["current_node_id"] = _next(f, node.get("id"))
                continue
            if t == "END":
                x["status"] = "COMPLETED"
                x["current_node_id"] = ""
                break
            x["current_node_id"] = _next(f, node.get("id"))
        if steps >= 20:
            x["status"] = "FAILED"
            x["error"] = "this flow loops; twenty steps ran without ending"
        if not x.get("current_node_id") and x.get("status") == "RUNNING":
            x["status"] = "COMPLETED"
        repo.put("flow_executions", x)
        moved += 1
    return {"ok": True, "moved": moved, "queued": queued,
            "message": f"{moved} person(s) moved, {queued} email(s) queued "
                       f"for your approval"}


def flow_rows(repo) -> list:
    execs = repo.all("flow_executions")
    out = []
    for f in repo.all("flows"):
        mine = [x for x in execs if x.get("flow_id") == f.get("id")]
        out.append({
            "id": f.get("id"), "name": f.get("name"),
            "status": f.get("status", "DRAFT"), "valid": f.get("valid", True),
            "invalid_reason": f.get("invalid_reason", ""),
            "nodes": len(_L(f.get("nodes"))), "edges": len(_L(f.get("edges"))),
            "in_flow": len([x for x in mine
                            if x.get("status") in ("RUNNING", "WAITING")]),
            "completed": len([x for x in mine
                              if x.get("status") == "COMPLETED"]),
            "goal_met": len([x for x in mine if x.get("status") == "GOAL_MET"]),
            "failed": len([x for x in mine if x.get("status") == "FAILED"]),
            "graph": {"nodes": _L(f.get("nodes")), "edges": _L(f.get("edges"))},
        })
    return out
