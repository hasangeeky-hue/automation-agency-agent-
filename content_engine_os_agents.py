"""
content_engine_os_agents.py
============================================================================
ENGINE 10: THE INTERNAL AGENT API, AS A SERVICE LAYER.

WHY THIS FILE EXISTS SEPARATELY FROM THE HTTP ROUTES
  An agent must never touch the database, and it must never touch a
  provider. It calls a domain service; the service enforces tenancy,
  validates, records what happened, and returns a plain dict. The HTTP
  layer above is a thin translation of that. Swapping Claude for anything
  else changes nothing here.

EVERY CALL IS AUDITED
  Each entry point opens an agent_run, logs an agent_action per side
  effect, and closes the run. The Agent Runs screen is that table. An
  agent action nobody can reconstruct afterwards is an agent action that
  will eventually be blamed on the wrong thing.

WHAT AN AGENT MAY DO
  create profiles and leads, enrich them, define segments, draft campaigns
  and templates, ask for a plan, and QUEUE. What it may not do: send,
  approve, suppress somebody without a reason, or reach an ESP. queue()
  here is the same orchestrator the founder's own button calls, so every
  gate applies identically.
============================================================================
"""

from __future__ import annotations

import content_engine_os_analytics as AN
import content_engine_os_audience as AUD
import content_engine_os_content as CONTENT
import content_engine_os_core as CORE
import content_engine_os_flows as FLOWS
import content_engine_os_send as SEND
from content_engine_os_core import _D, _L, Repo

#: What an agent is allowed to ask for. An unlisted action is refused by
#: name, so a model inventing an endpoint gets an error it can read rather
#: than a 404 it will retry forever.
ACTIONS = ("profiles.upsert", "leads.upsert", "profiles.enrich",
           "segments.save", "templates.save", "campaigns.save",
           "campaigns.plan", "campaigns.queue", "flows.save",
           "flows.enroll", "analytics.campaign", "profiles.timeline")

#: Things only a person may do. Listed here so the refusal message can name
#: the rule rather than saying "forbidden".
HUMAN_ONLY = {
    "campaigns.approve": "an email is released by you, never by an agent",
    "campaigns.send": "nothing reaches a provider except through the queue "
                      "worker, after your approval",
    "profiles.suppress": "a suppression is a legal record; it is added by "
                         "you or by a bounce, not by a model",
    "flows.activate": "a flow goes live when you say so",
}


def _repo(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> Repo:
    return Repo(store, workspace_id)


def call(store, agent_type, action, params=None, *,
         workspace_id=CORE.DEFAULT_WORKSPACE, jobs=None) -> dict:
    """The single door. Every agent request arrives here.

    Returns {ok, ...} and never raises: an agent that gets an exception
    retries, and a retry on a write is how duplicates are born."""
    params = _D(params)
    repo = _repo(store, workspace_id)
    if action in HUMAN_ONLY:
        return {"ok": False, "error": "human_only",
                "message": HUMAN_ONLY[action]}
    if action not in ACTIONS:
        return {"ok": False, "error": "unknown_action",
                "message": f"this OS does not do {action!r}. It does: "
                           + ", ".join(ACTIONS)}
    run = CORE.start_run(repo, agent_type, action)
    try:
        out = _dispatch(repo, action, params, jobs=jobs)
    except Exception as ex:                       # never leak a traceback
        CORE.finish_run(repo, run["id"], "FAILED", str(ex)[:500])
        return {"ok": False, "error": "failed", "message": str(ex)[:300]}
    CORE.log_action(repo, run["id"], action,
                    target_type=action.split(".")[0],
                    target_id=str(out.get("id") or ""),
                    inp=params, outp={k: v for k, v in out.items()
                                      if k != "rows"})
    CORE.finish_run(repo, run["id"], "OK" if out.get("ok") else "REFUSED",
                    out.get("message", ""))
    out["run_id"] = run["id"]
    return out


def _dispatch(repo, action, p, *, jobs=None) -> dict:
    if action == "profiles.upsert":
        rec = CORE.upsert_profile(repo, p)
        if not rec:
            return {"ok": False, "message": "a profile needs an email address"}
        return {"ok": True, "id": rec["id"], "message": f"{rec['email']} saved"}

    if action == "leads.upsert":
        prof = CORE.upsert_profile(repo, p)
        if not prof:
            return {"ok": False, "message": "a lead needs a contactable person"}
        lead = CORE.upsert_lead(
            repo, prof["id"], source=p.get("source"),
            source_url=p.get("source_url"), score=p.get("score"),
            intent_score=p.get("intent_score"),
            stage=p.get("stage") or "NEW",
            qualification_status=p.get("qualification_status"),
            assigned_agent=p.get("assigned_agent"))
        return {"ok": True, "id": lead["id"], "profile_id": prof["id"],
                "message": f"lead for {prof['email']} at stage {lead['stage']}"}

    if action == "profiles.enrich":
        pid = p.get("profile_id") or CORE.rid("prf", repo.ws,
                                              CORE.norm_email(p.get("email")))
        if not repo.one("profiles", pid):
            return {"ok": False, "message": "no such profile in this workspace"}
        n = 0
        for k, v in _D(p.get("properties")).items():
            CORE.set_property(repo, pid, k, v)
            n += 1
        return {"ok": True, "id": pid, "properties": n,
                "message": f"{n} property(ies) recorded"}

    if action == "segments.save":
        return AUD.save_segment(repo, p.get("name"), p.get("tree"))

    if action == "templates.save":
        doc = CONTENT.from_agent(p)
        out = CONTENT.save_template(repo, p.get("name"), blocks=doc["blocks"],
                                    subject=doc["subject"],
                                    preview_text=doc["preview_text"],
                                    publish=bool(p.get("publish")))
        out["refused_blocks"] = doc["refused"]
        return out

    if action == "campaigns.save":
        return SEND.save_campaign(
            repo, campaign_id=p.get("id", ""), name=p.get("name", ""),
            audience_kind=p.get("audience_kind", "all"),
            audience_id=p.get("audience_id", ""),
            template_id=p.get("template_id", ""),
            subject=p.get("subject", ""), body=p.get("body", ""),
            scheduled_at=p.get("scheduled_at", ""))

    if action == "campaigns.plan":
        pl = SEND.plan(repo, p.get("id", ""), jobs=jobs,
                       touch=int(p.get("touch") or 1))
        if not pl.get("ok"):
            return pl
        return {"ok": True, "id": p.get("id"), "deliverable": pl["deliverable"],
                "pool": pl["pool"], "refused": pl["refused_counts"],
                "message": f"{pl['deliverable']} of {pl['pool']} would receive "
                           f"this"}

    if action == "campaigns.queue":
        out = SEND.queue(repo, p.get("id", ""), jobs=jobs,
                         touch=int(p.get("touch") or 1))
        out["id"] = p.get("id")
        return out

    if action == "flows.save":
        return FLOWS.save_flow(repo, flow_id=p.get("id", ""),
                               name=p.get("name", ""), nodes=p.get("nodes"),
                               edges=p.get("edges"))

    if action == "flows.enroll":
        return FLOWS.enroll(repo, p.get("id", ""), p.get("profile_ids"))

    if action == "analytics.campaign":
        t = AN.totals(repo, p.get("id"))
        return {"ok": True, "id": p.get("id"), "totals": t,
                "message": f"{t['sent']} sent, {t['unique_opens']} opened, "
                           f"{t['unique_clicks']} clicked"}

    if action == "profiles.timeline":
        rows = CORE.timeline(repo, p.get("profile_id", ""))
        return {"ok": True, "id": p.get("profile_id"), "rows": rows,
                "message": f"{len(rows)} thing(s) have happened to this person"}

    return {"ok": False, "message": "unreachable"}
