"""
content_engine_api.py
============================================================================
REST bridge so n8n (or anything) can drive and TEST the engine over HTTP.

Two layers:
  1. Core functions (api_*) — plain Python, no HTTP. Fully unit-tested offline.
  2. build_app() — wraps them in FastAPI routes (only if fastapi is installed).

Endpoints (what n8n calls):
  GET  /health                      -> preflight (every connection)
  GET  /skills                      -> list runnable skills
  POST /skills/{skill}/taste        -> run ONE agent on a literal INPUT and see
                                       its output. This is "taste every agent":
                                       test each skill in isolation before launch.
                                       body: {"input": {...}, "brand": {...}}
  POST /jobs                        -> create a job. body: {type, brand, payload}
  GET  /jobs/{id}                   -> status + payload
  POST /jobs/{id}/approve           -> flip the human gate
  POST /jobs/{id}/ready_to_measure  -> flip the measurement gate (n8n cron)
  POST /tick                        -> advance one runnable job (the worker beat)

Run the server (needs `pip install fastapi uvicorn`):
  uvicorn content_engine_api:app --host 0.0.0.0 --port 8000
Dev with zero API cost: USE_FIXTURES=1 (after RECORD_FIXTURES=1 capture).
============================================================================
"""

from __future__ import annotations

import base64
import datetime as _dt
import logging
import hashlib
import os
from typing import Optional

import content_engine_orchestrator as orch
from content_engine_providers import build_prompt, call_provider
from content_engine_health import run_health

# The engine's job store. Swap to Postgres by setting STORE=pg + DATABASE_URL.
_STORE = None

# HTTP request models. Defined at MODULE LEVEL on purpose: this file uses
# `from __future__ import annotations`, so FastAPI sees the route hints as
# strings and resolves them against module globals — a class defined inside
# build_app() would not be found (FastAPI then mis-reads the body as a query
# param -> 422). Guarded so the module still imports without pydantic.
try:
    from pydantic import BaseModel

    class TasteBody(BaseModel):
        model_config = {"protected_namespaces": ()}
        input: dict
        brand: Optional[dict] = None
        model: Optional[str] = None

    class JobBody(BaseModel):
        type: str
        brand: dict = {}
        payload: dict = {}
        job_id: Optional[str] = None
except Exception:  # pydantic absent (core-only use, no HTTP)
    BaseModel = None  # type: ignore

# `Request` must live at MODULE level for the same reason as the models above:
# `from __future__ import annotations` turns `request: Request` into a string
# hint that FastAPI resolves against module globals. Imported inside build_app()
# it would be invisible -> FastAPI treats `request` as a query field -> 422.
try:
    from fastapi import Request  # noqa: E402
except Exception:
    Request = None  # type: ignore


def get_store():
    global _STORE
    if _STORE is None:
        if os.getenv("STORE", "memory").lower() == "pg":
            from content_engine_store_pg import PgJobStore, init_db
            _STORE = PgJobStore(os.environ["DATABASE_URL"])
            init_db(_STORE)
        else:
            _STORE = orch.InMemoryJobStore()
        # Let connectors read credentials the founder saved via the dashboard's
        # Connect form (settings store), not just env vars.
        try:
            import content_engine_connectors as _C
            _C.set_settings_provider(_STORE.get_setting)
            if hasattr(_STORE, "add_daily_cost"):
                _C.set_cost_recorder(_STORE.add_daily_cost)   # external spend -> the cap
            if hasattr(_STORE, "set_setting"):
                _C.set_settings_writer(_STORE.set_setting)     # suppression + send caps
        except Exception:
            pass
        try:   # dashboard-saved brand CI feeds every content agent
            import content_engine_brand as _B
            _B.set_ci_provider(_STORE.get_setting)
        except Exception:
            pass
        try:   # live web-research spend counts toward the monthly cap/meters
            import content_engine_providers as _P
            if hasattr(_STORE, "add_daily_cost"):
                _P.set_web_research_cost_sink(lambda cost, usage: _STORE.add_daily_cost(cost))
        except Exception:
            pass
    return _STORE


# ---------------------------------------------------------------------------
# Core API functions (no HTTP)
# ---------------------------------------------------------------------------
_TASTEABLE = {
    "site_intelligence", "competitor_intel", "content_strategist",
    "content_producer", "content_producer_image", "seo_optimizer",
    "qa_compliance", "analytics_funnel", "optimizer", "segmenter",
    "lead_qualifier", "outreach_copy", "ads_optimizer",
}


def api_health() -> dict:
    return run_health()


def api_list_skills() -> dict:
    return {"skills": sorted(_TASTEABLE),
            "code_skills": sorted(orch.CODE_HANDLERS.keys()),
            "pipelines": {"content_piece": list(orch.FLOW_CONTENT.keys()),
                          "outreach_campaign": list(orch.FLOW_OUTREACH.keys())}}


def api_taste_skill(skill: str, skill_input: dict, brand: Optional[dict] = None,
                    model: Optional[str] = None) -> dict:
    """Run ONE skill on a LITERAL input (bypasses prepare_input) so you can test
    an agent in isolation. Uses the skill's routed model unless overridden."""
    if skill not in _TASTEABLE:
        return {"error": f"unknown or non-LLM skill '{skill}'",
                "tasteable": sorted(_TASTEABLE)}
    route = orch.ROUTES.get(skill, {})
    chosen = model or route.get("engine")
    if chosen == "code":
        # code+narrate skills (site_intelligence, analytics_funnel, segmenter)
        # do their LLM work through a narrate/label model.
        chosen = route.get("narrate") or route.get("label")
    if not chosen:
        return {"error": f"skill '{skill}' has no LLM engine to taste"}
    spec = build_prompt(skill, {"payload": skill_input, "brand": brand or {}})
    result = call_provider(chosen, spec)
    return {"skill": skill, "model": chosen, "output": result.data,
            "usage": result.usage, "cost_usd": result.cost_usd,
            "warnings": result.warnings}


def api_create_job(job_type: str, brand: dict, payload: dict,
                   job_id: Optional[str] = None) -> dict:
    if job_type not in ("content_piece", "outreach_campaign"):
        return {"error": f"unknown job type '{job_type}'"}
    store = get_store()
    jid = job_id or f"job_{abs(hash((job_type, str(payload)))) % 10_000_000}"
    job = orch.new_job(jid, job_type, brand, payload)
    store.save(job)
    return {"job_id": jid, "status": job["status"]}


def api_list_jobs(status: Optional[str] = None) -> dict:
    """List jobs, optionally by status. Used by the n8n measurement cron to find
    jobs sitting in 'published' / 'sent' that are due for measurement."""
    store = get_store()
    if not hasattr(store, "list_jobs"):
        return {"jobs": [], "error": "store has no list_jobs"}
    jobs = store.list_jobs(status)
    return {"jobs": [{"job_id": j["job_id"], "type": j["type"],
                      "status": j["status"]} for j in jobs]}


def api_list_measurable() -> dict:
    """Jobs whose measurement window has already opened (published/sent with an
    elapsed measure_at). For monitoring; the engine opens the gate by time on
    its own, so a plain /tick advances them without an explicit flip."""
    store = get_store()
    if not hasattr(store, "list_jobs"):
        return {"jobs": []}
    out = []
    for status in ("published", "sent"):
        for j in store.list_jobs(status):
            step = orch.flow_for(j).get(j["status"])
            if step and orch._wait_open(j, step):
                out.append({"job_id": j["job_id"], "type": j["type"],
                            "status": j["status"], "measure_at": j.get("measure_at")})
    return {"jobs": out}


def api_get_job(job_id: str) -> dict:
    try:
        job = get_store().get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    return {"job_id": job_id, "type": job["type"], "status": job["status"],
            "approved": job.get("approved", False),
            "ready_to_measure": job.get("ready_to_measure", False),
            "cost_so_far_usd": job.get("cost_so_far_usd", 0.0),
            # Why a job produced no learning. Without these the dashboard can
            # only show that a job finished, not that it finished having
            # measured nothing — which is the difference between a piece that
            # failed and a piece nobody ever looked at.
            "unmeasured_reason": job.get("unmeasured_reason", ""),
            "learned_nothing": job.get("learned_nothing", ""),
            "rewrite_proposed": job.get("rewrite_proposed", False),
            "measure_at": job.get("measure_at", ""),
            # WHY A JOB FAILED. This whitelist is hand-written, and the three
            # fields the orchestrator writes when a step dies were not in it —
            # so advance() recorded "qa_compliance: no model produced a valid
            # result", the database kept it, and every reader that went through
            # this function saw a failed job with no reason whatsoever. The
            # probe printed "It stopped at 'failed'." and stopped, twice, while
            # the answer sat one column away.
            #
            # factory_report.py reads the store directly, which is the only
            # reason the reasons were ever visible at all.
            "halt_reason": job.get("halt_reason", ""),
            "qa_verdict": job.get("qa_verdict", ""),
            "needs_human": job.get("needs_human", False),
            "payload": job.get("payload", {})}


def _set_flag(job_id: str, flag: str) -> dict:
    store = get_store()
    try:
        job = store.get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    job[flag] = True
    store.save(job)
    return {"job_id": job_id, flag: True, "status": job["status"]}


def _log_decision(store, action: str, what: str, detail: str = "") -> None:
    """EVERY DECISION LEAVES A DATED LINE.

    The founder clicked Approve, the backend obeyed, and no screen anywhere
    recorded that it happened - "it does not tell its really approved or
    not". One append-only list, written at the endpoints where decisions
    actually land, read by the Cockpit's Decision Log. Best-effort: a
    logging hiccup must never block the decision itself."""
    try:
        from datetime import datetime, timezone
        rows = list(store.get_setting("decision_log", []) or [])
        rows.append({"at": datetime.now(timezone.utc).isoformat(),
                     "action": action, "what": str(what)[:140],
                     "detail": str(detail)[:200]})
        store.set_setting("decision_log", rows[-200:])
    except Exception:
        pass


def api_approve(job_id: str, note: str = "") -> dict:
    """Approve a piece for publish/send. An optional note is recorded on the job
    (and shown in the approval log) so your instruction is on the record."""
    store = get_store()
    try:
        job = store.get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    if note:
        job.setdefault("payload", {})["approval_note"] = note
    job["approved"] = True
    store.save(job)
    # YOUR APPROVAL IS AN OUTCOME. The founder reading a piece and pressing
    # Approve is the strongest quality signal this engine receives, and it
    # taught the playbook nothing - the learning loop only listened to
    # measurements arriving 21 days later. Best-effort: a learning hiccup
    # must never block an approval.
    p = job.get("payload", {}) or {}
    title = (p.get("content_producer") or {}).get("title") or ""
    try:
        import content_engine_learning as L
        client = job.get("client_id") or (job.get("brand", {}) or {}).get(
            "brand_name", "")
        if title:
            kw = (p.get("config") or {}).get("primary_keyword") or ""
            L.record_outcome(client, "approved_piece",
                             f"{title}" + (f" [kw: {kw}]" if kw else ""))
    except Exception:
        pass
    # THE TRAIL. Approving moved the piece out of the "awaiting" filter, so
    # it vanished from the queue with no explanation of where it went.
    try:
        import content_engine_site_taxonomy as _T
        chans = _T.channels_of(p.get("config") or {})
        dest = " + ".join(c.title() for c in chans) or "Website"
    except Exception:
        dest = "Website"
    _log_decision(store, "approved", title or job_id,
                  f"publishing to {dest}" + (f" · note: {note}" if note else ""))
    return {"job_id": job_id, "approved": True, "status": job.get("status"),
            "note": note,
            "message": f"Approved — publishing to {dest} next. Logged in the "
                       f"Cockpit's Decision Log; the learning agent recorded "
                       f"what you liked."}


def api_decline(job_id: str, note: str = "") -> dict:
    """Decline a piece WITH a correction note and send it BACK to be re-made using
    your feedback (not just halted). The note is fed to the writer so the rewrite
    fixes exactly what you flagged. Nothing publishes/sends."""
    store = get_store()
    try:
        job = store.get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    from datetime import datetime, timezone
    p = job.setdefault("payload", {})
    p.setdefault("revision_notes", []).append(
        {"note": note, "at": datetime.now(timezone.utc).isoformat()})
    p["revision_note"] = note                      # latest — fed into the rewrite
    # A REJECTION TEACHES TOO. What the founder sends back - and why - is
    # exactly what the playbook needs to stop producing. Best-effort.
    # (title captured HERE - two lines down the payload pops it)
    _t = (p.get("content_producer") or {}).get("title") or job_id
    if note.strip():
        try:
            import content_engine_learning as L
            _client = job.get("client_id") or (job.get("brand", {}) or {}).get(
                "brand_name", "")
            L.record_outcome(_client, "rejected_piece",
                             f"'{_t}': {note.strip()[:140]}")
        except Exception:
            pass
    job.pop("approved", None)
    job.pop("qa_verdict", None)
    if job.get("type") == "outreach_campaign":
        for k in ("outreach_copy", "qa_compliance"):
            p.pop(k, None)
        job["status"] = "segmented"                # re-run outreach_copy with the note
    else:
        for k in ("content_producer", "seo_optimizer", "qa_compliance", "image_url", "taxonomy"):
            p.pop(k, None)
        job["status"] = "planned"                  # re-run the writer with the note
    store.save(job)
    _log_decision(store, "sent_back", _t, note.strip()[:120] or "declined")
    return {"ok": True, "job_id": job_id, "status": job["status"], "note": note,
            "message": "sent back for a rewrite using your note"}


def api_ready_to_measure(job_id: str) -> dict:
    return _set_flag(job_id, "ready_to_measure")


def api_tick() -> dict:
    """One pass of the engine. Called by the worker container on a loop.

    The OS queue is drained HERE rather than from a button, which is what
    makes it a worker rather than a form. It is wrapped: an OS problem must
    never stop the content pipeline that has been running for months. It
    still sends nothing that a human has not approved, because drain() only
    picks up rows carrying approved=True."""
    store = get_store()
    status = orch.tick(store)
    queue = {}
    try:
        import content_engine_os as _OS
        jobs = store.list_jobs(status=None) if hasattr(store, "list_jobs") else []
        queue = _OS.drain(store, jobs=jobs)
    except Exception as e:
        log.warning("os queue drain skipped this tick: %s", e)
        queue = {"ok": False, "message": f"{type(e).__name__}: {e}"}
    # Once a day, from the worker: the Drive and Sheets mirror, the recurring
    # sheet imports, and a read of the mailbox for bounces. Each is wrapped
    # on its own so one failing cannot stop the other two.
    extras = {}
    for name, fn in (("mirror", lambda: _OS.mirror(store)),
                     ("sources", lambda: _OS.source_run(store, force=False)),
                     ("bounces", lambda: _OS.read_bounces(store))):
        try:
            import content_engine_os as _OS
            extras[name] = fn()
        except Exception as e:
            extras[name] = {"ok": False, "message": f"{type(e).__name__}: {e}"}
    return {"advanced": status is not None, "status": status, "queue": queue,
            **extras}


def api_answer_replies(limit: int = 20, dry_run: bool = False) -> dict:
    """Trigger the inbound-reply agent (Q18b): read unread replies, draft
    answers, auto-send only the safe ones (respects REPLY_AUTO_SEND; complaints
    are always held for a human). Call from an n8n cron."""
    import content_engine_reply_agent as reply_agent
    return reply_agent.answer_replies(limit=limit, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Customer replies: draft-and-hold for the founder to review, edit, and send.
# Drafts live in the 'reply_drafts' setting so the dashboard can show them.
# ---------------------------------------------------------------------------
def _reply_drafts():
    st = get_store()
    return list((getattr(st, "get_setting", lambda *a: [])("reply_drafts", []) or []))


def _save_reply_drafts(drafts):
    st = get_store()
    if hasattr(st, "set_setting"):
        st.set_setting("reply_drafts", drafts)


def api_replies_refresh(limit: int = 20) -> dict:
    """Read unread customer replies, have the agent DRAFT an answer to each
    (never auto-sent), and store them for the founder to review/edit/send."""
    res = api_answer_replies(limit=limit, dry_run=True)
    if res.get("status") != "ok":
        return {"ok": False, "error": res.get("reason") or res.get("status") or "reply read failed"}
    drafts = _reply_drafts()
    seen = {d.get("id") for d in drafts}
    from datetime import datetime, timezone
    added = 0
    for r in res.get("results", []):
        if r.get("status") == "bounce_suppressed":
            continue
        rid = r.get("message_id") or (r.get("from", "") + "|" + (r.get("subject_in") or ""))
        if not rid or rid in seen:
            continue
        drafts.append({
            "id": rid, "from_email": r.get("from", ""), "from_name": r.get("from_name", ""),
            "subject_in": r.get("subject_in", ""), "message_in": r.get("message_in", ""),
            "draft_subject": r.get("reply_subject", ""), "draft_body": r.get("reply_body", ""),
            "intent": r.get("intent", ""), "needs_human": bool(r.get("needs_human")),
            "status": "pending", "at": datetime.now(timezone.utc).isoformat(),
        })
        seen.add(rid)
        added += 1
    _save_reply_drafts(drafts)
    return {"ok": True, "added": added, "pending": sum(1 for d in drafts if d.get("status") == "pending")}


def api_reply_edit(reply_id, subject, body) -> dict:
    """Save the founder's edit of a drafted reply (fix the agent before sending)."""
    drafts = _reply_drafts()
    for d in drafts:
        if d.get("id") == reply_id:
            if subject is not None:
                d["draft_subject"] = subject
            if body is not None:
                d["draft_body"] = body
            d["edited"] = True
            _save_reply_drafts(drafts)
            return {"ok": True, "id": reply_id}
    return {"ok": False, "error": "reply not found"}


def api_reply_send(reply_id) -> dict:
    """Send the (edited) reply to the customer from customercare@, threaded to
    their original message. Marks the draft sent."""
    drafts = _reply_drafts()
    d = next((x for x in drafts if x.get("id") == reply_id), None)
    if not d:
        return {"ok": False, "error": "reply not found"}
    if d.get("status") == "sent":
        return {"ok": False, "error": "already sent"}
    import content_engine_connectors as C
    to = d.get("from_email", "")
    if not to:
        return {"ok": False, "error": "no recipient address on this reply"}
    ref = C.Emailer().send_message(
        to, d.get("draft_subject", "") or ("Re: " + (d.get("subject_in") or "")),
        d.get("draft_body", ""),
        extra_headers={"In-Reply-To": d.get("id", ""), "References": d.get("id", "")},
        category="support")
    ok = isinstance(ref, str) and not ref.startswith(("suppressed", "send_error", "blocked", "held"))
    d["status"] = "sent" if ok else "error"
    d["send_ref"] = ref
    _save_reply_drafts(drafts)
    return {"ok": ok, "ref": ref, "id": reply_id}


def api_reply_dismiss(reply_id) -> dict:
    """Dismiss a reply draft (no answer needed). Kept as 'dismissed', not deleted."""
    drafts = _reply_drafts()
    for d in drafts:
        if d.get("id") == reply_id:
            d["status"] = "dismissed"
            _save_reply_drafts(drafts)
            return {"ok": True, "id": reply_id}
    return {"ok": False, "error": "reply not found"}


def _settings():
    st = get_store()
    return {"paused": bool(getattr(st, "get_setting", lambda *a: False)("paused", False)),
            "autonomy": bool(getattr(st, "get_setting", lambda *a: False)("autonomy", False))}


def api_control(action: str) -> dict:
    """Global run controls from the dashboard: pause / resume everything."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "this store has no control state"}
    if action == "pause":
        store.set_setting("paused", True)
    elif action == "resume":
        store.set_setting("paused", False)
    else:
        return {"error": f"unknown control '{action}'"}
    return {"paused": store.get_setting("paused", False)}


def api_autonomy(on: bool = True) -> dict:
    """Toggle 'run without me' autonomy (the agents proceed on their own)."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "this store has no control state"}
    store.set_setting("autonomy", bool(on))
    return {"autonomy": bool(on)}


def api_record_outcome(job_id: str, leads: int = 0, revenue: float = 0.0,
                       customers: int = 0) -> dict:
    """Record real business RESULTS on a job (leads booked, revenue, customers)
    so the dashboard can show ROI, not just cost. Called by n8n / your CRM."""
    store = get_store()
    try:
        job = store.get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    oc = job.setdefault("payload", {}).setdefault("outcome", {})
    oc["leads"] = int(oc.get("leads", 0)) + int(leads)
    oc["revenue"] = round(float(oc.get("revenue", 0.0)) + float(revenue), 2)
    oc["customers"] = int(oc.get("customers", 0)) + int(customers)
    store.save(job)
    # S2: a real WIN feeds the learning loop so the money agents get smarter.
    if int(leads) > 0 or float(revenue) > 0:
        try:
            import content_engine_learning as L
            p = job.get("payload", {}) or {}
            client = job.get("client_id") or (job.get("brand", {}) or {}).get("brand_name", "")
            mb = p.get("media_buyer")
            if isinstance(mb, dict) and mb.get("campaign_name"):
                L.record_outcome(client, "campaign_theme", mb["campaign_name"])
            subj = ((p.get("email", {}) or {}).get("subject_variants") or [None])[0] or p.get("subject")
            if subj:
                L.record_outcome(client, "email_subject", subj)
        except Exception:
            pass
    return {"job_id": job_id, "outcome": oc}


def api_connect(values: dict) -> dict:
    """Save connector credentials from the dashboard's Connect form into the
    settings store — connectors read them live (no restart). Only allow-listed
    keys are accepted."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "this store can't save credentials"}
    import content_engine_connectors as C
    allowed = set(C.CONNECTOR_ENV_KEYS)
    saved, warnings = [], []
    for k, v in (values or {}).items():
        if k in allowed and v not in (None, ""):
            val = str(v).strip()          # a trailing space is always a paste slip
            store.set_setting(k, val)
            saved.append(k)
            # SAVE IT, THEN SAY WHAT LOOKS WRONG. Never block: a validator that
            # refuses a key it does not recognise is a worse failure than one
            # that warns. The board saved IMAGE_PROVIDER as "open ai" and
            # IMAGE_API_KEY as a pasted shell command, in silence, and the
            # engine then spent days reporting that a provider had answered.
            try:
                bad = C.credential_problem(k, val)
            except Exception:
                bad = ""
            if bad:
                warnings.append(f"{k} {bad}")
    return {"saved": saved, "warnings": warnings, "status": C.status()}


def api_disconnect(keys) -> dict:
    """Clear connector credentials from the settings store (dashboard 'Disconnect'
    button). Blanks each allow-listed key so its wire reverts to disconnected and
    the paste-in box comes back — all from the front-end, no SSH."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "this store can't edit credentials"}
    import content_engine_connectors as C
    allowed = set(C.CONNECTOR_ENV_KEYS)
    if isinstance(keys, str):
        keys = [x.strip() for x in keys.split(",")]
    cleared = []
    for k in (keys or []):
        if k in allowed:
            store.set_setting(k, "")   # blank -> connector.available() becomes False
            cleared.append(k)
    return {"cleared": cleared, "status": C.status()}


def api_media_chat(job_id, message):
    """Talk to the media buyer. If job_id points at a drafted campaign, it can
    revise that campaign in place. With no campaign it answers as a planning
    assistant. Returns {'reply', 'changed'}."""
    store = get_store()
    job = None
    if job_id:
        try:
            job = store.get(job_id)
        except Exception:
            job = None
    p = (job or {}).get("payload", {}) or {}
    campaign = p.get("media_buyer") or {}
    history = p.get("media_chat_history") or []
    try:
        from content_engine_providers import build_prompt, call_provider
        spec = build_prompt("media_chat", {"job_id": job_id or "", "brand": (job or {}).get("brand", {}),
            "payload": {"campaign": campaign, "message": message or "", "history": history[-10:]}})
        data = (call_provider(orch.FRONTIER_MODEL, spec).data) or {}
    except Exception as e:
        return {"reply": f"(agent error: {str(e)[:120]})", "changed": False}
    reply = data.get("reply") or "(no reply)"
    # only persist a revision when we actually have a campaign job to save it on
    changed = (bool(job) and bool(campaign) and bool(data.get("changed"))
               and isinstance(data.get("campaign"), dict) and data["campaign"].get("campaign_name"))
    if changed:
        p["media_buyer"] = data["campaign"]
    if job:
        p["media_chat_history"] = (history + [{"role": "user", "text": message or ""},
                                              {"role": "agent", "text": reply}])[-20:]
        job["payload"] = p
        try:
            store.save(job)
        except Exception:
            pass
    return {"reply": reply, "changed": bool(changed)}


def _brand_dict():
    """Brand identity for content jobs — name + offer from settings, defaults else."""
    store = get_store()
    g = getattr(store, "get_setting", lambda *a: None)
    return {"brand_name": g("brand_name") or "Anthropos Automation",
            "offer": g("brand_offer") or "AI & automation systems for small businesses"}


log = logging.getLogger("content_engine.api")


def _safe_google_insights(force: bool = False) -> dict:
    """Cached GSC+GA4 replication for the dashboards; {} on any failure."""
    try:
        import content_engine_connectors as C
        return C.google_insights(force=force) or {}
    except Exception:
        return {}


def api_refresh_insights() -> dict:
    """Force-refresh the cached full GSC+GA4 pull (↻ button)."""
    get_store()
    gi = _safe_google_insights(force=True)
    if not gi:
        return {"ok": False, "error": "Google pull failed — GSC/GA4 connected?"}
    return {"ok": True, "at": gi.get("at", ""),
            "gsc_queries": len((gi.get("gsc") or {}).get("queries", [])),
            "ga4_days": len((gi.get("ga4") or {}).get("daily", []))}


def api_competitor_scan(domains=None, limit: int = 5) -> dict:
    """Run the competitive-intelligence capture (discover -> scan -> synthesize).
    Costs ~6-9 Serper credits per competitor + one cheap Claude call."""
    get_store()   # wire settings so Serper/Google/Claude keys resolve
    import content_engine_competitors as CI
    return CI.run_scan(domains=domains, limit=max(1, min(6, int(limit or 5))))


def api_source_maps_leads(vertical: str, city: str, count: int = 20) -> dict:
    """Source LOCAL leads from Google Maps (Serper) + find their emails (Prospeo),
    synchronously, and create an outreach campaign already at 'sourced' — the
    normal flow (qualify -> write -> QA -> YOUR approval -> capped send) takes it
    from there. Nothing is emailed by this call."""
    vertical = (vertical or "").strip()
    city = (city or "").strip()
    if not vertical or not city:
        return {"ok": False, "error": "need a business type and a city"}
    count = max(1, min(40, int(count or 20)))
    import content_engine_connectors as C
    import content_engine_code_skills as cs
    if not C.Serper().available():
        return {"ok": False, "error": "Serper is not connected (SERPER_API_KEY)"}
    query = f"{vertical} in {city}"
    raw = C.maps_leads(query, count)
    if not raw:
        return {"ok": False, "error": f"Maps returned nothing for '{query}' — try a broader term"}
    store = get_store()
    jid = f"maps_{abs(hash((query, count))) % 10_000_000}"
    job = orch.new_job(jid, "outreach_campaign", _brand_dict(),
                       {"raw_leads": raw,
                        "config": {"lead_source": "maps", "maps_query": query,
                                   "lead_limit": count, "vertical": vertical, "city": city}})
    srcinfo = cs.lead_sourcing(job)          # dedupe + verify (same step the worker runs)
    job["status"] = "sourced"                # ready for the qualifier
    store.save(job)
    with_email = sum(1 for L in job["payload"].get("leads", []) if L.get("email"))
    return {"ok": True, "job_id": jid, "query": query,
            "businesses": len(job["payload"].get("leads", [])),
            "with_verified_email": with_email, "sourcing": srcinfo,
            "next": "The qualifier picks it up on the next engine step (▶ Run one step or START)."}


def _live_campaign_names(store):
    """Campaigns running today, so a planned piece can be attached to one and
    inherit its utm_campaign."""
    try:
        import content_engine_sga as SGA
        from datetime import date
        today = date.today().isoformat()
        return [c["name"] for c in SGA.list_campaigns(store)
                if (c.get("start") or "") <= today
                and (not c.get("end") or c["end"] >= today)][:8]
    except Exception:
        return []


def _safe(fn):
    """Call a context builder; a failure must never stop planning."""
    try:
        return fn() or {}
    except Exception as e:
        log.warning("planner signal source failed: %s", e)
        return {}


def api_plan_content(count=8):
    """Ask the planner to propose a batch of on-brand pieces for you to approve.
    Stores the plan as 'pending' — no jobs are created until you approve it."""
    store = get_store()
    g = getattr(store, "get_setting", lambda *a: None)
    import content_engine_site_taxonomy as TAX
    recent = []
    coverage = {s["name"]: 0 for s in TAX.SEGMENTS}   # balance target: even across all 7
    try:
        for j in (store.list_jobs() if hasattr(store, "list_jobs") else []):
            pl = j.get("payload", {}) or {}
            t = (pl.get("content_producer", {}) or {}).get("title")
            if t:
                recent.append(t)
            seg = (pl.get("taxonomy") or {}).get("segment") or (pl.get("config", {}) or {}).get("segment")
            if seg in coverage:
                coverage[seg] += 1
    except Exception:
        pass
    icp = g("icp") or {"verticals": ["doctors", "lawyers", "Shopify stores", "tax consultants",
                                     "content creators", "marketing managers"],
                       "countries": ["USA", "UK", "Germany", "Switzerland", "Canada"],
                       "deal_size": "$2,000-$10,000"}
    # site_signals was {} — the planner could only balance its own taxonomy
    # against its own past titles. Every system in this engine already computes
    # what a strategist would ask for; hand it over as evidence.
    brief, eligible = {}, ["website"]
    try:
        import content_engine_factory as _F
        import content_engine_seo_ops as _SO
        _jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
        _st = _connectors_status()
        brief = _F.strategy_brief(
            store,
            seo=_safe(lambda: _SO.build_ctx(store)),
            bi=_safe(lambda: _SO.build_bi_ctx(store, jobs=_jobs, status=_st)),
            outreach=_safe(lambda: _SO.build_outreach_ctx(store, jobs=_jobs)),
            sga=_safe(lambda: _SO.build_sga_ctx(store, jobs=_jobs, status=_st)),
            media=_safe(lambda: _SO.build_media_ctx(store)),
            risk=_safe(lambda: _SO.build_risk_ctx(store, status=_st, jobs=_jobs)),
            status=_st)
        eligible = brief.get("eligibility", {}).get("eligible") or ["website"]
    except Exception as e:
        log.warning("strategy brief unavailable, planning without it: %s", e)
    payload = {"count": int(count), "goal": "authority + leads", "icp": icp,
               "segments": TAX.SEGMENT_NAMES, "pillars": TAX.PILLAR_NAMES,
               "coverage": coverage, "recent_titles": recent[-30:],
               "site_signals": brief.get("signals", {}),
               "priority_gaps": [g.get("why") for g in brief.get("gaps", [])[:5]],
               "channel_eligibility": eligible,
               "live_campaigns": _live_campaign_names(store)}
    try:
        from content_engine_providers import build_prompt, call_provider
        mdl = (orch.ROUTES.get("content_planner", {}) or {}).get("engine") or orch.FRONTIER_ALT
        spec = build_prompt("content_planner", {"payload": payload, "brand": _brand_dict()})
        data = call_provider(mdl, spec).data or {}
    except Exception as e:
        return {"error": f"planner failed: {str(e)[:140]}"}
    items = [it for it in (data.get("plan") or []) if it.get("title")]
    if not items:
        return {"error": "the planner returned no pieces — try again"}
    plan = {"status": "pending", "period": data.get("period", ""), "items": items}
    if hasattr(store, "set_setting"):
        store.set_setting("content_plan", plan)
    return {"ok": True, "count": len(items), "plan": plan}


def api_approve_plan():
    """Approve the pending plan: create one content job per piece. They then flow
    through the normal pipeline (write -> QA -> publish)."""
    store = get_store()
    plan = getattr(store, "get_setting", lambda *a: None)("content_plan")
    if not plan or not plan.get("items"):
        return {"error": "no pending plan to approve"}
    if plan.get("status") == "approved":
        return {"error": "this plan is already approved"}
    brand = _brand_dict()
    created = []
    for it in plan["items"]:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        directive = (f"Write this exact piece: '{title}'. Angle: {it.get('angle','')}. "
                     f"Target keyword: {it.get('target_keyword','')}. Type: {it.get('type','blog')}. "
                     f"Audience segment: {it.get('segment','')}. Service pillar: {it.get('pillar','')}.")
        # channels: where it posts (website + LinkedIn by default); publish date from day_offset
        channels = [str(c).lower() for c in (it.get("channels") or ["website", "linkedin"])]
        channels = ["wordpress" if c in ("website", "web", "blog") else c for c in channels] or ["wordpress"]
        pub_date = ""
        try:
            from datetime import date, timedelta
            pub_date = (date.today() + timedelta(days=int(it.get("day_offset", 0) or 0))).isoformat()
        except Exception:
            pub_date = ""
        payload = {"type": it.get("type", "blog"),
                   "config": {"weekly_priorities": directive, "chosen_topic": title,
                              "target_keyword": it.get("target_keyword", ""), "pieces_this_week": 1,
                              # carry the planner's segment+pillar so the piece stays on-target
                              "segment": it.get("segment", ""), "pillar": it.get("pillar", ""),
                              "deploy_channels": channels, "publish_date": pub_date}}
        jid = f"plan_{abs(hash(title)) % 10_000_000}"
        api_create_job("content_piece", brand, payload, job_id=jid)
        created.append(jid)
    plan["status"] = "approved"
    if hasattr(store, "set_setting"):
        store.set_setting("content_plan", plan)
    return {"ok": True, "created": len(created), "jobs": created}


def api_clear_plan():
    store = get_store()
    if hasattr(store, "set_setting"):
        store.set_setting("content_plan", {"status": "cleared", "items": []})
    return {"ok": True}


def _outreach_email_for(job, email, touch=1):
    """(lead, qual, subject, body) for one recipient at a given sequence step.

    THE RESOLVER NOW HAS ONE HOME. It used to live here, private to the API
    module, which meant the preview screen could not reach it: it read
    payload.subject and payload.html, fields no job carries, so every
    campaign previewed as empty while the sender worked perfectly. The
    logic moved to content_engine_os_content.resolve_email and both the
    preview and the send path call it. What you preview is what sends.

    This wrapper stays because the outbox, the batch sender and the single
    sender all call it by this name.
    """
    import content_engine_os_content as OSC
    return OSC.resolve_email(job, email, touch)


def _outreach_alias(mailer=None):
    """Which address outreach actually leaves from. send_personalized() routes
    on category="marketing", so ask the mailer rather than assuming."""
    try:
        return (mailer or __import__("content_engine_connectors").Emailer()
                ).from_for("marketing") or ""
    except Exception:
        return ""


def _append_ref(p, email, ref, subject=None, step=None, alias=None,
                job_id=None):
    """Record a send in the touch history (sent_to[email] is a LIST, one ref per
    email sent — this is what tracks the 3-email cycle) plus the send TIME in a
    parallel sent_at[email] list, which drives the follow-up schedule/timeline."""
    from datetime import datetime, timezone
    m = p.setdefault("sent_to", {})
    cur = m.get(email)
    if isinstance(cur, list):
        cur.append(ref)
    elif cur:                       # migrate a legacy single ref -> list
        m[email] = [cur, ref]
    else:
        m[email] = [ref]
    ok = isinstance(ref, str) and not ref.startswith(("suppressed", "send_error", "blocked", "held"))
    if ok:                          # only stamp a time for a real send
        at = p.setdefault("sent_at", {})
        at.setdefault(email, []).append(datetime.now(timezone.utc).isoformat())
        # Record-only metadata, parallel to sent_at. The dashboard used to
        # ASSUME every outreach email left from marketing@ and had no idea what
        # subject was sent, so "Best subject lines" could never rank anything.
        # Nothing here changes what was sent — it records what already was.
        try:
            meta = p.setdefault("sent_meta", {})
            meta.setdefault(email, []).append({
                "subject": (subject or "")[:160],
                "step": int(step) if step else len(at.get(email, [])),
                "alias": alias or "",
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
        except Exception as e:
            log.warning("send stamp failed for %s (the send itself was fine): %s",
                        email, e)


def api_outreach_edit(job_id, email, subject, body, touch=1, store=None):
    """Save the founder's manual edit of one email (fix the agent's text). The
    edited version is what previews AND what sends.

    THE ONE WRITER of payload['email_edits']. `store` is injectable so the
    engagement OS and the tests write through this same function rather
    than growing a second writer that could disagree with the reader."""
    store = store if store is not None else get_store()
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "no recipient"}
    p = job.setdefault("payload", {})
    p.setdefault("email_edits", {})[f"{email}|{int(touch or 1)}"] = {
        "subject": subject or "", "body": body or ""}
    try:
        store.save(job)
    except Exception:
        pass
    return {"ok": True, "email": email, "touch": int(touch or 1)}


def api_outreach_send_one(job_id, email, touch=None):
    """Send the NEXT email in this lead's 3-step sequence (or a specific `touch`).
    Steps: 1=intro, 2=follow-up bump, 3=final note. After 3, we stop."""
    store = get_store()
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    email = (email or "").strip()
    import content_engine_connectors as C
    p = job.setdefault("payload", {})
    step = int(touch) if touch else C.next_touch((p.get("sent_to") or {}).get(email.lower()))
    if not step or step > C.SEQUENCE_TOUCHES:
        return {"ok": False, "error": "sequence complete — 3 emails already sent (or stopped)"}
    got = _outreach_email_for(job, email, step)
    if not got:
        return {"ok": False, "error": "lead not in this campaign"}
    _lead, _q, subj, body = got
    _mailer = C.Emailer()
    ref = _mailer.send_personalized(email, subj, body, job)
    _append_ref(p, email.lower(), ref, subject=subj, step=step,
                alias=_outreach_alias(_mailer), job_id=job_id)
    try:
        store.save(job)
    except Exception:
        pass
    ok = isinstance(ref, str) and not ref.startswith(("suppressed:", "send_error", "blocked_quality:", "held_"))
    return {"ok": ok, "ref": ref, "email": email, "touch": step}


def api_outreach_send_batch(job_id, emails=None):
    """Send the NEXT sequence step to a list of leads (or ALL leads). Each lead
    advances one step (1->2->3) per run; leads already at 3 are skipped. Cap-honored."""
    store = get_store()
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    p = job.get("payload", {}) or {}
    leads = p.get("leads") or []
    targets = [e.strip().lower() for e in emails] if emails else \
        [(L.get("email") or "").strip().lower() for L in leads if L.get("email")]
    sent, held, failed, done = 0, 0, 0, 0
    import content_engine_connectors as C
    mailer = C.Emailer()
    sent_map = p.setdefault("sent_to", {})
    for email in targets:
        if not email:
            continue
        step = C.next_touch(sent_map.get(email))
        if not step:                 # sequence complete or blocked -> skip
            done += 1
            continue
        got = _outreach_email_for(job, email, step)
        if not got:
            failed += 1
            continue
        _l, _q, subj, body = got
        ref = mailer.send_personalized(email, subj, body, job)
        _append_ref(p, email, ref, subject=subj, step=step,
                    alias=_outreach_alias(mailer), job_id=job_id)
        if isinstance(ref, str) and ref.startswith("held_"):
            held += 1
        elif isinstance(ref, str) and not ref.startswith(("suppressed:", "send_error", "blocked_quality:")):
            sent += 1
        else:
            failed += 1
    try:
        store.save(job)
    except Exception:
        pass
    return {"ok": True, "sent": sent, "held_by_cap": held, "failed": failed,
            "already_done": done, "total": len(targets)}


def api_outreach_send_all():
    """Send EVERY ready email across all outreach campaigns (the command-center
    'send all' button). Honors the warm-up cap — the rest queue for coming days."""
    store = get_store()
    sent = held = total = 0
    for j in (store.list_jobs() if hasattr(store, "list_jobs") else []):
        if j.get("type") != "outreach_campaign":
            continue
        res = api_outreach_send_batch(j.get("job_id"))
        sent += res.get("sent", 0)
        held += res.get("held_by_cap", 0)
        total += res.get("total", 0)
    return {"ok": True, "sent": sent, "held_by_cap": held, "total": total}


def api_outreach_trash(job_id, email, restore=False):
    """Soft-delete an email to the junk box (recoverable — never lost), or restore it."""
    store = get_store()
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    email = (email or "").strip().lower()
    p = job.setdefault("payload", {})
    trash = p.setdefault("email_trashed", [])
    if restore:
        p["email_trashed"] = [e for e in trash if e != email]
    elif email not in trash:
        trash.append(email)
    try:
        store.save(job)
    except Exception:
        pass
    return {"ok": True, "email": email, "trashed": not restore}


def api_save_ci(text, drive_folder=None, inspiration=None):
    """Save the brand/CI the content agents write on-brand from (dashboard)."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "store cannot save settings"}
    store.set_setting("brand_ci", text or "")
    if drive_folder is not None:
        store.set_setting("brand_ci_drive", drive_folder)
    if inspiration is not None:
        store.set_setting("brand_ci_inspiration", inspiration)
    try:
        import content_engine_brand as _B
        _B.reset_cache()
    except Exception:
        pass
    return {"ok": True, "saved": True, "chars": len(text or "")}


def api_start(autonomous: bool = False):
    """Switch the machine on.

    SUPERVISED (the default, and what the START button now calls): unpause, turn
    the cadence on so work is queued and the SEO engines run, and publish
    APPROVED pieces. Autonomy is explicitly set OFF — every piece waits for you.

    AUTONOMOUS (a separate, deliberate choice): additionally releases anything
    that has sat at the gate longer than AUTONOMY_GRACE_HOURS and publishes it
    without you.

    These used to be the same button. Pressing START set autonomy=True, and the
    worker's auto_approve_stale() then published anything you had not reviewed
    within 24 hours — which is not what "keep every publish behind approval"
    means. Splitting them is the whole point of this function."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "store cannot save settings"}
    store.set_setting("paused", False)
    store.set_setting("cadence_on", True)
    store.set_setting("WP_STATUS", "publish")   # APPROVED + QA-passed pieces go live
    store.set_setting("autonomy", bool(autonomous))
    try:
        import content_engine_scheduler as scheduler
        planned = scheduler.plan_today(store, force=True)
    except Exception as e:
        planned = {"error": str(e)[:120]}
    return {"ok": True, "running": True,
            "mode": "autonomous" if autonomous else "supervised",
            "planned": planned,
            "message": ("Running. Every piece waits for your approval."
                        if not autonomous else
                        "Running AUTONOMOUSLY — anything you do not review "
                        f"within {orch.AUTONOMY_GRACE_HOURS:.0f}h publishes itself.")}


def api_stop():
    """Stop everything: pause, cadence off, autonomy off."""
    store = get_store()
    if not hasattr(store, "set_setting"):
        return {"error": "store cannot save settings"}
    store.set_setting("paused", True)
    store.set_setting("cadence_on", False)
    store.set_setting("autonomy", False)
    return {"ok": True, "running": False, "message": "Stopped."}


def api_autopilot(on=True):
    """Backwards-compatible shim. Kept because /autopilot/run is a documented
    endpoint, but it no longer grants autonomy — supervised is the default now."""
    return api_start(autonomous=False) if on else api_stop()


def api_run_evals():
    """S5: run the eval set, grade with the judge, store the result so the
    dashboard needles update. Costs a few cents."""
    try:
        import content_engine_evals as E
        result = E.run_evals()
    except Exception as e:
        return {"error": f"eval run failed: {str(e)[:140]}"}
    try:
        store = get_store()
        if hasattr(store, "set_setting"):
            store.set_setting("last_eval_run", result)
    except Exception:
        pass
    return result


def api_media_activate(job_id):
    """1-click activate: push an APPROVED drafted campaign live into Google Ads."""
    store = get_store()
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    if not job.get("approved"):
        return {"ok": False, "error": "Approve the campaign first, then activate."}
    if job.get("status") == "campaign_live":
        return {"ok": False, "error": "This campaign is already live."}
    p = job.get("payload", {}) or {}
    draft = p.get("media_buyer") or {}
    if not draft:
        return {"ok": False, "error": "no drafted campaign"}
    import content_engine_connectors as C
    ga = C.GoogleAds()
    if not ga.available():
        return {"ok": False, "error": "Connect Google Ads first on the System Map page, then deploy."}
    landing = (p.get("config", {}) or {}).get("landing_url", "")
    res = ga.create_campaign(draft, landing)
    if res.get("ok"):
        job["status"] = "campaign_live"
        p["campaign_ref"] = res.get("campaign")
        job["payload"] = p
        try:
            store.save(job)
        except Exception:
            pass
    return res


def api_media_abort(job_id):
    """Abort: pause a LIVE campaign in Google Ads, or discard a draft/approved one."""
    store = get_store()
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    p = job.get("payload", {}) or {}
    if job.get("status") == "campaign_live":
        import content_engine_connectors as C
        res = C.GoogleAds().pause_campaign(p.get("campaign_ref", ""))
        if res.get("ok"):
            job["status"] = "aborted"
            try:
                store.save(job)
            except Exception:
                pass
        return res
    # draft / approved but not live -> just discard it
    job["status"] = "aborted"
    job["approved"] = False
    try:
        store.save(job)
    except Exception:
        pass
    return {"ok": True, "detail": "campaign discarded"}


def api_media_draft():
    """One-click: run the media buyer now on your ICP (+ any recent creatives) and
    save the drafted campaign so it shows as a card with every control."""
    store = get_store()
    creatives = []
    try:
        if hasattr(store, "list_jobs"):
            for j in store.list_jobs():
                pl = j.get("payload", {}) or {}
                c = pl.get("creatives") or pl.get("image") or pl.get("image_brief")
                if c:
                    creatives.append(c if isinstance(c, str) else str(c)[:220])
                if len(creatives) >= 4:
                    break
    except Exception:
        pass
    payload = {
        "offer": "AI & automation systems that save small businesses 10+ hours a week",
        "goal": "leads", "monthly_budget": 200,
        "landing_url": "https://anthropos-automation.com/",
        "icp": {"verticals": ["doctors", "lawyers", "Shopify stores", "tax consultants",
                              "content creators", "marketing managers"],
                "countries": ["USA", "UK", "Germany", "Switzerland", "Canada"],
                "deal_size": "$2,000-$10,000"},
        "creatives": creatives, "past_learnings": []}
    try:
        from content_engine_providers import build_prompt, call_provider
        spec = build_prompt("media_buyer", {"payload": payload, "brand": {}})
        model = orch.ROUTES.get("media_buyer", {}).get("engine") or orch.FRONTIER_MODEL
        draft = (call_provider(model, spec).data) or {}
    except Exception as e:
        return {"ok": False, "error": f"agent error: {str(e)[:140]}"}
    if not draft.get("campaign_name"):
        return {"ok": False, "error": "the agent did not return a campaign — try again"}
    # S1: judge the draft before it's shown for approval (cheap model).
    try:
        from content_engine_judge import judge
        draft["_quality"] = judge("campaign", draft)
    except Exception:
        pass
    jid = f"media_{abs(hash(str(draft))) % 10_000_000}"
    job = {"job_id": jid, "type": "media_campaign", "status": "AWAITING_APPROVAL",
           "approved": False, "brand": {},
           "payload": {"media_buyer": draft, "config": {"landing_url": payload["landing_url"]}}}
    try:
        store.save(job)
    except Exception as e:
        return {"ok": False, "error": f"could not save: {str(e)[:100]}"}
    return {"ok": True, "job_id": jid, "campaign": draft.get("campaign_name")}


def api_schedule_run(force: bool = False) -> dict:
    """Create today's production batch (cold-email-first). Call from an n8n daily
    cron. Idempotent per day unless force=True."""
    import content_engine_scheduler as scheduler
    return scheduler.plan_today(get_store(), force=force)


def api_auto_run() -> dict:
    """Autonomy beat: release pieces that waited too long at the human gate (only
    if Autonomy is ON), then advance one job. Call from an n8n cron."""
    store = get_store()
    released = orch.auto_approve_stale(store)
    status = orch.tick(store)
    return {"auto_approved": released, "advanced": status is not None, "status": status}


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Dashboard login (Phase 1). A single password (DASHBOARD_PASSWORD) gates the
# control center. No password set = open (localhost/dev behind an SSH tunnel).
# ---------------------------------------------------------------------------
def _dash_password() -> str:
    return os.getenv("DASHBOARD_PASSWORD", "")


def _dash_token() -> str:
    pw = _dash_password()
    return hashlib.sha256(("aa-dash|" + pw).encode()).hexdigest() if pw else ""


def dash_authed(cookies: dict) -> bool:
    """True if the request may see the dashboard."""
    if not _dash_password():
        return True
    return (cookies or {}).get("aa_dash") == _dash_token()


_STATUS_COLOR = {"working": "#46E08B", "live": "#46E08B",
                 "partial": "#2FE3D2", "needs key": "#F5B14C"}


def _connectors_status() -> dict:
    try:
        import content_engine_connectors as C
        return C.status()
    except Exception:
        return {}


def _eighteen(st: dict) -> list:
    """The 18 capabilities + a live status derived from the connector map."""
    def L(k):
        return bool(st.get(k))
    social = L("social_linkedin") or L("social_twitter") or L("social_facebook")
    gsc = L("google_gsc_ga4")
    return [
        ("1 · Content agents", "working"),
        ("2 · Deploy content", "live" if L("wordpress_publish") else "needs key"),
        ("3 · Create content", "working"),
        ("4 · Social channels", "live" if social else "needs key"),
        ("5 · Deploy method", "live" if L("wordpress_publish") else "needs key"),
        ("6 · Store content (Drive)", "live" if L("google_drive") else "needs key"),
        ("7 · SEO technical", "live" if gsc else "partial"),
        ("8 · Keyword strategy", "working"),
        ("9 · Agent hub (Sheets)", "live" if L("google_sheets") else "partial"),
        ("10 · Web search", "live" if L("web_search") else "needs key"),
        ("11 · Tracking (GA4)", "live" if gsc else "needs key"),
        ("12 · Categorise", "working"),
        ("13 · Web scrape", "live" if L("web_search") else "needs key"),
        ("14 · LinkedIn leads", "live" if L("linkedin_leads") else "needs key"),
        ("15 · Lead scoring", "working"),
        ("16 · Customer groups", "working"),
        ("17 · Cold emails", "working"),
        ("18 · Send + reply email", "live" if L("email_send") else "needs key"),
    ]


def _blueprint_svg(st: dict) -> str:
    """A simple 'circuit board' wiring map. Destination nodes turn green when
    their connector is live, amber when the key is still missing."""
    def col(k):
        return "#46E08B" if st.get(k) else "#F5B14C"

    def node(x, y, w, label, color, sub=""):
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="9" '
            f'fill="#0F1626" stroke="{color}" stroke-width="1.6"/>'
            f'<text x="{x + w/2}" y="{y + (20 if sub else 28)}" fill="#EAF0FF" '
            f'font-size="12" font-weight="600" text-anchor="middle">{label}</text>'
            + (f'<text x="{x + w/2}" y="{y + 35}" fill="{color}" font-size="10" '
               f'text-anchor="middle">{sub}</text>' if sub else ""))

    def wire(x1, y1, x2, y2):
        return (f'<path d="M{x1} {y1} C {(x1+x2)/2} {y1}, {(x1+x2)/2} {y2}, {x2} {y2}" '
                f'stroke="#2FE3D2" stroke-width="1.4" fill="none" opacity="0.55"/>')

    parts = ['<svg viewBox="0 0 900 470" width="100%" xmlns="http://www.w3.org/2000/svg" '
             'style="max-width:100%;height:auto">']
    # sources (left)
    parts.append(node(20, 40, 150, "Web / Search", col("web_search"), "search + scrape"))
    parts.append(node(20, 120, 150, "LinkedIn", col("linkedin_leads"), "leads"))
    parts.append(node(20, 350, 150, "n8n", "#8B7CFF", "triggers / cron"))
    # center: VPS
    parts.append('<rect x="330" y="150" width="240" height="150" rx="14" fill="#0C1120" '
                 'stroke="#2FE3D2" stroke-width="2"/>')
    parts.append('<text x="450" y="185" fill="#2FE3D2" font-size="14" font-weight="700" '
                 'text-anchor="middle">VPS — Agents + Engine</text>')
    parts.append('<text x="450" y="210" fill="#9AA6C6" font-size="11" '
                 'text-anchor="middle">orchestrator · blackboard · dashboard</text>')
    parts.append('<text x="450" y="232" fill="#9AA6C6" font-size="11" '
                 'text-anchor="middle">Postgres (source of truth)</text>')
    parts.append('<text x="450" y="270" fill="#46E08B" font-size="11" '
                 'text-anchor="middle">Claude (Opus / Haiku)</text>')
    # Google hub (right top)
    ghue = "#46E08B" if (st.get("google_sheets") or st.get("google_drive")) else "#F5B14C"
    parts.append('<rect x="700" y="30" width="180" height="120" rx="12" fill="#0F1626" '
                 f'stroke="{ghue}" stroke-width="1.8"/>')
    parts.append('<text x="790" y="55" fill="#EAF0FF" font-size="12" font-weight="700" '
                 'text-anchor="middle">Google Workspace</text>')
    parts.append(f'<text x="790" y="78" fill="{col("google_sheets")}" font-size="11" '
                 'text-anchor="middle">Sheets · dashboard</text>')
    parts.append(f'<text x="790" y="98" fill="{col("google_drive")}" font-size="11" '
                 'text-anchor="middle">Drive · content JSON</text>')
    parts.append(f'<text x="790" y="118" fill="{col("email_send")}" font-size="11" '
                 'text-anchor="middle">Gmail · sending</text>')
    # destinations (right)
    parts.append(node(700, 190, 180, "WordPress", col("wordpress_publish"), "publish"))
    social_live = st.get("social_linkedin") or st.get("social_twitter") or st.get("social_facebook")
    parts.append(node(700, 260, 180, "Social channels",
                      "#46E08B" if social_live else "#F5B14C", "LI · X · FB · IG · TT"))
    parts.append(node(700, 330, 180, "Email out + replies", col("email_send"), "Gmail / IMAP"))
    # wires
    parts.append(wire(170, 63, 330, 200))
    parts.append(wire(170, 143, 330, 220))
    parts.append(wire(170, 373, 330, 260))
    parts.append(wire(570, 200, 700, 90))     # VPS <-> Google
    parts.append(wire(570, 230, 700, 215))    # -> WordPress
    parts.append(wire(570, 250, 700, 290))    # -> Social
    parts.append(wire(570, 270, 700, 355))    # -> Email
    parts.append("</svg>")
    return "".join(parts)


def _login_html(error: str = "", nxt: str = "") -> str:
    import content_engine_dashboard as D
    return D.login_html(error, nxt)


# ---------------------------------------------------------------------------
# SEO engine (E1-E14). HTTP-free so it stays unit-testable offline.
# ---------------------------------------------------------------------------
_SEO_ACTIONS = {
    "crawl": "run_crawl", "inspect": "run_inspect", "speed": "run_speed",
    "indexnow": "run_indexnow", "ranks": "run_ranks", "aeo": "run_aeo",
    "offpage": "run_offpage", "prospecting": "run_prospecting",
    "fixes": "run_fixes", "all": "run_all", "geo": "run_geo",
    "ads": "run_ads", "interlock": "run_interlock",
}


def api_seo(action: str) -> dict:
    """Run one SEO engine (or the whole nightly sequence) and report honestly."""
    fn_name = _SEO_ACTIONS.get(action)
    if not fn_name:
        return {"ok": False, "error": f"unknown SEO action '{action}'"}
    try:
        import content_engine_seo_ops as SEO
        result = getattr(SEO, fn_name)(get_store())
        return {"ok": True, "action": action, "result": result}
    except Exception as e:
        log.exception("seo action %s failed", action)
        return {"ok": False, "action": action, "error": f"{type(e).__name__}: {e}"}


def api_seo_workorders(status: str = "") -> dict:
    try:
        import content_engine_workorders as WO
        orders = WO.load(get_store())
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return {"ok": True, "stats": WO.stats(orders), "orders": orders[:200]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def api_seo_approve_all(kind: str = "title", limit: int = 250) -> dict:
    """Approve and publish EVERY drafted rewrite of one type.

    271 individual approvals is not a workflow, it is a wall. The per-order
    route stays for reviewing one at a time; this is the bulk path, and it
    only ever touches orders that already carry a model-written proposal the
    founder can read on the board first."""
    try:
        import content_engine_workorders as WO
        import content_engine_seo_fixer as FIX
        store = get_store()
        orders = WO.load(store)
        targets = [o for o in orders
                   if o.get("type") == kind
                   and (o.get("extra") or {}).get("proposal")
                   and o.get("status") in ("awaiting_approval", "open")][:limit]
        if not targets:
            return {"ok": True, "applied": 0,
                    "reason": f"no drafted {kind} rewrites are waiting — "
                              f"run the fixer first to generate them"}
        applied, failed = 0, []
        for o in targets:
            out = FIX.apply_proposal(o)
            WO.mark(store, o["id"], out["status"], out.get("result", ""))
            if out["status"] == "done":
                applied += 1
            else:
                failed.append({"url": o.get("url"), "why": out.get("result", "")})
        _log_decision(store, "seo_fix_approved",
                      f"bulk: every drafted '{kind}' rewrite",
                      f"{applied} published, {len(failed)} failed")
        return {"ok": True, "applied": applied, "failed": len(failed),
                "details": failed[:10], "type": kind,
                "message": f"{applied} '{kind}' rewrite(s) published to the "
                           f"live site; {len(failed)} failed. Logged in the "
                           f"Decision Log."}
    except Exception as e:
        log.exception("bulk approve failed")
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def api_seo_apply(order_id: str) -> dict:
    """Approve and publish ONE drafted change.

    Routes by code, because there are now two apply paths. The title and meta
    rewrites go through the original fixer. The eight repairs added later
    (headings, broken links, canonicals, indexing) go through fixer8, which
    knows that a canonical is a meta field, an IndexNow submit is a ping, and
    a redirect is a rule the engine cannot write at all.
    """
    try:
        import content_engine_workorders as WO
        import content_engine_seo_fixer as FIX
        import content_engine_seo_fixer8 as F8
        store = get_store()
        order = next((o for o in WO.load(store) if o.get("id") == order_id), None)
        if not order:
            return {"ok": False, "error": "work order not found"}
        if not (order.get("extra") or {}).get("proposal"):
            return {"ok": False, "status": "skipped",
                    "result": ("Nothing has been drafted for this page yet. "
                               "Run the fixer first, read what it proposes, "
                               "then approve it.")}
        out = (F8.apply(order) if order.get("code") in F8.FIXER8_CODES
               else FIX.apply_proposal(order))
        WO.mark(store, order_id, out["status"], out.get("result", ""))
        _log_decision(store, "seo_fix_approved",
                      f"{order.get('code')} on {str(order.get('url'))[:80]}",
                      str(out.get("result", ""))[:120])
        return {"ok": out["status"] == "done", **out}
    except Exception as e:
        log.exception("apply fix failed")
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


EDITABLE_LEAD_FIELDS = ("name", "title", "company", "linkedin", "phone",
                        "country", "website", "vertical", "email")


def api_lead_edit(job_id, email, fields):
    """Update one lead in place. Only the listed fields, and only ones actually
    sent — a blank box must not wipe a value that is already there."""
    store = get_store()
    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "no lead selected"}
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    p = job.setdefault("payload", {})
    changed = {}
    for bucket in ("leads", "raw_leads"):
        for L in (p.get(bucket) or []):
            if not isinstance(L, dict):
                continue
            if (L.get("email") or "").strip().lower() != email:
                continue
            for k in EDITABLE_LEAD_FIELDS:
                v = (fields or {}).get(k)
                if v is None or str(v).strip() == "":
                    continue                       # blank = leave alone
                L[k] = str(v).strip()[:200]
                changed[k] = L[k]
            L["edited_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(
                timespec="seconds")
    if not changed:
        return {"ok": False, "error": "nothing to change"}
    try:
        store.save(job)
    except Exception as e:
        return {"ok": False, "error": f"could not save: {e}"}
    return {"ok": True, "email": email, "changed": sorted(changed),
            "message": f"{email}: updated {', '.join(sorted(changed))}."}


def api_lead_delete(job_id, email, reason="removed by hand"):
    """Soft-remove a lead. It leaves the sendable list and is suppressed, so it
    can never be emailed again — but the record is kept, because a deleted lead
    you paid to source is still evidence about your sourcing."""
    store = get_store()
    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "error": "no lead selected"}
    try:
        job = store.get(job_id)
    except Exception:
        return {"ok": False, "error": "campaign not found"}
    p = job.setdefault("payload", {})
    before = len(p.get("leads") or [])
    p["leads"] = [L for L in (p.get("leads") or [])
                  if (L or {}).get("email", "").strip().lower() != email]
    removed = p.setdefault("leads_removed", [])
    if email not in [str(x.get("email", "")) for x in removed if isinstance(x, dict)]:
        removed.append({"email": email, "reason": str(reason)[:120],
                        "at": _dt.datetime.now(_dt.timezone.utc).isoformat(
                            timespec="seconds")})
    try:
        import content_engine_connectors as C
        C.suppress_email(email, "removed_by_hand")
    except Exception as e:
        log.warning("could not suppress removed lead %s: %s", email, e)
    try:
        store.save(job)
    except Exception as e:
        return {"ok": False, "error": f"could not save: {e}"}
    return {"ok": True, "email": email, "removed": before - len(p["leads"]),
            "message": f"{email} removed and suppressed — it will not be emailed."}


def _safe_image_key():
    """The image key, read the same settings-first way everything else is, so
    the board can tell you whether it is an OpenAI key or an Anthropic one."""
    try:
        import content_engine_connectors as C
        return C._env("IMAGE_API_KEY") or ""
    except Exception:
        return ""


def _sga_emails_sent(jobs):
    """Emails the engine actually sent, from the send stamps."""
    try:
        return sum(len(v) for j in (jobs or [])
                   for v in ((j.get("payload", {}) or {}).get("sent_at", {}) or {}).values())
    except Exception:
        return 0


def _bi_bookings():
    """Cal.com bookings for the BI boards. Never raises — a booking wire that is
    down must not take the dashboard with it."""
    try:
        import content_engine_connectors as CN
        c = CN.CalCom()
        return c.bookings() if c.available() else []
    except Exception as e:
        log.warning("cal.com bookings unavailable: %s", e)
        return []


def _dashboard_kwargs() -> dict:
    """Gather live engine data ONCE, for whichever UI is asking.

    This used to be the first 180 lines of api_dashboard_html(). It was split
    out when the VX2 layout arrived, so the two UIs cannot read different
    numbers for the same question. Whatever is wrong here is wrong in both;
    whatever is right here is right in both. There is no second reader.
    """
    store = get_store()
    jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
    st = _connectors_status()
    try:
        health = run_health()
    except Exception as e:  # never let a health hiccup 500 the dashboard
        health = {"healthy": False, "anthropic": {"status": "fail", "detail": str(e)}}
    _caps = orch.budget_caps(store) if hasattr(orch, "budget_caps") else {}
    month_cap = _caps.get("per_month", getattr(orch, "PER_MONTH_BUDGET_USD", 200.0))
    day_cap = _caps.get("per_day", getattr(orch, "PER_DAY_BUDGET_USD", 50.0))
    month_spent = store.monthly_cost() if hasattr(store, "monthly_cost") else         sum(float(j.get("cost_so_far_usd", 0)) for j in jobs)
    day_spent = store.daily_cost() if hasattr(store, "daily_cost") else 0.0
    settings = _settings()
    try:
        import content_engine_connectors as _C
        bookings = _C.CalCom().summary()
        ads = _C.GoogleAds().summary()
    except Exception:
        bookings, ads = {}, {}
    # S5: the three drift needles + last eval run
    try:
        import content_engine_evals as _E
        last_eval = store.get_setting("last_eval_run", None) if hasattr(store, "get_setting") else None
        needles = _E.needles(store, last_eval)
    except Exception:
        last_eval, needles = None, {}
    # per-API usage meters (spend vs your top-up cap, so you're warned before it runs out)
    try:
        import content_engine_connectors as _C2
        meters = _C2.api_meters()
        api_limits = _C2.api_limits()
    except Exception:
        meters, api_limits = {}, {}
    # brand/CI + autopilot state
    try:
        ci_text = store.get_setting("brand_ci", "") if hasattr(store, "get_setting") else ""
        ci_drive = store.get_setting("brand_ci_drive", "") if hasattr(store, "get_setting") else ""
        wp_live = (store.get_setting("WP_STATUS", "draft") if hasattr(store, "get_setting") else "draft") == "publish"
    except Exception:
        ci_text, ci_drive, wp_live = "", "", False
    autopilot_on = bool(settings["autonomy"]) and not bool(settings["paused"]) and wp_live
    try:
        content_plan = store.get_setting("content_plan", None) if hasattr(store, "get_setting") else None
    except Exception:
        content_plan = None
    # real website tracking (GA4 + Search Console) for the Media Buying funnel
    try:
        import content_engine_connectors as _C3
        _g = _C3.Google()
        if _g.available():
            web_tracking = {"ga4": _g.ga4_summary(), "gsc": _g.gsc_top_queries()}
        else:
            web_tracking = {}
    except Exception:
        web_tracking = {}
    try:
        reply_drafts = list(st.get_setting("reply_drafts", []) or []) if hasattr(st, "get_setting") else []
    except Exception:
        reply_drafts = []
    # SEO engine context (11 boards). Read-only: assembled from what the SEO
    # engines already persisted, so the dashboard never waits on a crawl.
    try:
        import content_engine_seo_ops as _SEO
        seo_ctx = _SEO.build_ctx(
            store, status=st, insights=_safe_google_insights(), meters=meters,
            competitor_intel=(store.get_setting("competitor_intel", None)
                              if hasattr(store, "get_setting") else None))
    except Exception as e:
        log.warning("seo context unavailable: %s", e)
        seo_ctx = None
    try:
        import content_engine_seo_ops as _SEO2
        media_ctx = _SEO2.build_media_ctx(
            store, competitor_intel=(store.get_setting("competitor_intel", None)
                                     if hasattr(store, "get_setting") else None))
    except Exception as e:
        log.warning("media context unavailable: %s", e)
        media_ctx = None
    import content_engine_dashboard as D
    try:
        import content_engine_seo_ops as _SEO3
        system_ctx = _SEO3.build_system_ctx(
            store, status=st, health=health, meters=meters,
            month_spent=month_spent, month_cap=month_cap, jobs=jobs,
            needles=needles, last_eval=last_eval, diag=D._DIAG,
            build_tag=D.BUILD_TAG)
    except Exception as e:
        log.warning("system context unavailable: %s", e)
        system_ctx = None
    try:
        import content_engine_seo_ops as _SEO4
        risk_ctx = _SEO4.build_risk_ctx(
            store, status=st, health=health, meters=meters,
            month_spent=month_spent, month_cap=month_cap, jobs=jobs,
            agents=(system_ctx or {}).get("agents") if system_ctx else [],
            needles=needles, last_eval=last_eval,
            content_cost=sum(float(j.get("cost_so_far_usd", 0) or 0)
                             for j in jobs if j.get("type") != "outreach_campaign"),
            storage=(system_ctx or {}).get("storage") if system_ctx else {})
    except Exception as e:
        log.warning("risk context unavailable: %s", e)
        risk_ctx = None
    try:
        import content_engine_seo_ops as _SEO5
        bi_ctx = _SEO5.build_bi_ctx(
            store, insights=_safe_google_insights(), jobs=jobs,
            agents=(system_ctx or {}).get("agents") if system_ctx else [],
            meters=meters, month_spent=month_spent, month_cap=month_cap,
            reply_drafts=reply_drafts, bookings=_bi_bookings(), status=st)
    except Exception as e:
        log.warning("BI context unavailable: %s", e)
        bi_ctx = None
    try:
        import content_engine_seo_ops as _SEO6
        import content_engine_bi as _BI6
        outreach_ctx = _SEO6.build_outreach_ctx(
            store, jobs=jobs, reply_drafts=reply_drafts,
            bookings=_bi_bookings(), deals=_BI6.list_deals(store))
    except Exception as e:
        log.warning("outreach context unavailable: %s", e)
        outreach_ctx = None
    try:
        import content_engine_seo_ops as _SEO7
        import content_engine_bi as _BI7
        sga_ctx = _SEO7.build_sga_ctx(
            store, jobs=jobs, status=st, insights=_safe_google_insights(),
            deals=_BI7.list_deals(store), month_spent=month_spent,
            month_cap=month_cap, emails_sent=_sga_emails_sent(jobs))
    except Exception as e:
        log.warning("SGA context unavailable: %s", e)
        sga_ctx = None
    try:
        import content_engine_seo_ops as _SEO8
        import content_engine_brand as _BR8
        factory_ctx = _SEO8.build_factory_ctx(
            store, jobs=jobs, status=st,
            ci=(_BR8.get_ci() if hasattr(_BR8, "get_ci") else {}),
            content_plan=content_plan, seo=seo_ctx, bi=bi_ctx,
            outreach=outreach_ctx, sga=sga_ctx, media=media_ctx, risk=risk_ctx,
            image_key=_safe_image_key())
    except Exception as e:
        log.warning("Content Factory context unavailable: %s", e)
        # NOT None. A None context made the Content Factory render "Nothing
        # planned or written yet" over a live database - a wrong explanation,
        # visible only in a log line nobody reads. The board now prints WHY.
        factory_ctx = {"_ctx_error": f"{type(e).__name__}: {str(e)[:200]}"}
    try:
        import content_engine_seo_ops as _SEO9
        cockpit_ctx = _SEO9.build_cockpit_ctx(
            store, jobs=jobs, status=st, health=health,
            content_plan=content_plan, seo=seo_ctx, bi=bi_ctx,
            outreach=outreach_ctx, sga=sga_ctx, media=media_ctx,
            risk=risk_ctx, system=system_ctx,
            month_spent=month_spent, day_spent=day_spent)
    except Exception as e:
        log.warning("AI Cockpit context unavailable: %s", e)
        cockpit_ctx = None
    # Which of the extra keys already have a value, so the form can say "saved"
    # instead of showing an empty box for something that is set. Presence only —
    # no value is ever read back out to the browser.
    saved_keys = set()
    try:
        _get = getattr(store, "get_setting", None)
        if callable(_get):
            for _t, _s, _w, _fields in D.EXTRA_KEY_GROUPS:
                for _k, _h in _fields:
                    if str(_get(_k, "") or "").strip():
                        saved_keys.add(_k)
    except Exception as e:
        log.warning("could not read which extra keys are set: %s", e)
    return dict(
        saved_keys=saved_keys,
        seo_ctx=seo_ctx, media_ctx=media_ctx, system_ctx=system_ctx,
        risk_ctx=risk_ctx, bi_ctx=bi_ctx, outreach_ctx=outreach_ctx,
        sga_ctx=sga_ctx, factory_ctx=factory_ctx, cockpit_ctx=cockpit_ctx,
        jobs=jobs, st=st, health=health, month_spent=month_spent, month_cap=month_cap,
        day_spent=day_spent, day_cap=day_cap, taste_skills=sorted(_TASTEABLE),
        has_password=bool(_dash_password()), paused=settings["paused"],
        autonomy=settings["autonomy"], bookings=bookings, ads=ads,
        needles=needles, last_eval=last_eval, meters=meters, api_limits=api_limits,
        ci_text=ci_text if isinstance(ci_text, str) else "", ci_drive=ci_drive or "",
        autopilot_on=autopilot_on, content_plan=content_plan, web_tracking=web_tracking,
        reply_drafts=reply_drafts,
        competitor_intel=(st.get_setting("competitor_intel", None) if hasattr(st, "get_setting") else None),
        google_insights=_safe_google_insights())


def api_dashboard_html() -> str:
    """Render the Business Control Center: the original nine-board layout."""
    import content_engine_dashboard as D
    return D.dashboard_html(**_dashboard_kwargs())


def api_leads_html() -> str:
    """Leads and Outreach, ON ITS OWN PAGE.

    The control centre renders every section at once and comes to just over
    four megabytes. The engagement OS lives at the bottom of that, so
    reaching it means scrolling past everything else and waiting for
    everything else to draw first. This is the same section, the same
    context and the same code, served alone.

    It is NOT a second dashboard. Nothing is duplicated: it calls the one
    builder the control centre calls, so the two cannot drift.
    """
    import content_engine_dashboard as D
    import content_engine_os as OS
    import content_engine_os_screens as SCR
    store = get_store()
    jobs = store.list_jobs(status=None) if hasattr(store, "list_jobs") else []
    ctx = OS.build_ctx(store, jobs=jobs, reply_drafts=_reply_drafts())
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Leads &amp; Outreach</title>"
        "<style>" + D.CSS + "</style></head><body>"
        "<div class='top'><div class='brand'><div class='logo'>A</div>"
        "<div><h1>Leads &amp; Outreach</h1>"
        "<small>Everyone you know, and every email you sent them</small>"
        "</div></div>"
        "<div style='display:flex;gap:9px;align-items:center'>"
        "<a href='/' style='color:#8FA0C8;font-size:12px;text-decoration:none;"
        "border:1px solid #1B2640;border-radius:7px;padding:5px 11px'>"
        "Back to the control centre</a></div></div>"
        "<div class='shell'><div class='main' style='width:100%'>"
        + SCR.build(ctx) + "</div></div>"
        + D.dashboard_script({}) + "</body></html>")


def api_vx2_html(active: str = "decide") -> str:
    """Render VX2: the same nine boards, four doors, 127 subsections.

    Same data, same builders, same second. If VX2 ever disagrees with the old
    dashboard about a number, the disagreement is in the RENDERER, because the
    reader above is shared.
    """
    import content_engine_vx2 as VX2
    return VX2.page(active=active, **_dashboard_kwargs())


# ---------------------------------------------------------------------------
# FastAPI wiring (optional — only if fastapi is installed)
# ---------------------------------------------------------------------------
def build_app():
    from fastapi import FastAPI
    from fastapi import Response
    from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

    app = FastAPI(title="Content Engine", version="1.0")

    # THE PAGE SHIPPED RAW. The dashboard is ~6 MB of HTML and no middleware
    # compressed it, so every load pushed all 6 MB over the founder's
    # connection - reported as "crashing, taking long time to load". Gzip
    # takes the same page to ~0.5 MB. Three lines, 12x faster transfer.
    try:
        from starlette.middleware.gzip import GZipMiddleware
        app.add_middleware(GZipMiddleware, minimum_size=2048)
    except Exception:
        pass

    @app.middleware("http")
    async def _auth_gate(request, call_next):
        # When DASHBOARD_PASSWORD is set, EVERY endpoint requires auth, so the
        # dashboard is safe to expose publicly (no tunnel needed). Browser auths
        # via the login cookie; n8n/automation via ?key= or an X-API-Key header.
        pw = _dash_password()
        if not pw:
            return await call_next(request)
        if request.url.path == "/login":
            return await call_next(request)
        # The open pixel and the click redirect are the ONLY unauthenticated
        # paths. A mail client fetching an image has no session, so gating them
        # would mean tracking silently never worked. They take an opaque token,
        # append one event (the list is hard-capped), and return an image or a
        # redirect. They read nothing and return no data.
        if request.url.path.startswith(("/t/o/", "/t/c/", "/t/v")):
            return await call_next(request)
        # THE CONSENT PAGES ARE PUBLIC BY NECESSITY. A person unsubscribing
        # has no session and must never be asked for one: an unsubscribe
        # behind a login is an unsubscribe that does not work, which is both
        # a legal problem and a spam complaint waiting to happen. They are
        # rate limited instead (see _os_rate), they return the same page
        # whether or not the address is known, and they can only reach the
        # consent functions.
        if request.url.path in ("/subscribe", "/subscribe/confirm",
                                "/unsubscribe"):
            return await call_next(request)
        cookie_ok = request.cookies.get("aa_dash") == _dash_token()
        # ITEM 8. A member with their own password gets in on their own
        # cookie. The shared password still works and still means owner.
        if not cookie_ok:
            try:
                import content_engine_os_tenancy as _TEN
                cookie_ok = bool(_TEN.user_from_cookie(
                    get_store(), request.cookies.get("aa_user")))
            except Exception:
                cookie_ok = False
        key = request.headers.get("x-api-key") or request.query_params.get("key")
        if cookie_ok or (key and key == pw):
            # ITEM 18. A ceiling on the authenticated surface too. Not to
            # keep an attacker out (they are already signed in) but so one
            # runaway loop in a page or an agent cannot walk the whole
            # engine at machine speed.
            if request.url.path.startswith(("/os/", "/internal/")):
                if not _os_rate(request, "os", 600):
                    return JSONResponse(
                        {"ok": False,
                         "message": "that is more than 600 requests a minute "
                                    "from one place. Something is looping."},
                        status_code=429)
            return await call_next(request)
        # A BROWSER GETS A LOGIN FORM. A PROGRAM GETS 401.
        #
        # This used to serve the form for "/" alone, so every other page a
        # human could type - /vx2 above all - answered a browser navigation
        # with raw JSON. The founder read that dead end as "vx2 is not
        # showing, it shows the old dashboard": the deep link never opened, so
        # the only page reachable was the one the login form landed on.
        #
        # The test is what the caller asked for, not which path it is. A page
        # request says text/html; an API call does not.
        wants_page = (request.method == "GET"
                      and "text/html" in (request.headers.get("accept") or ""))
        if wants_page:
            nxt = request.url.path
            if request.url.query:
                nxt += "?" + request.url.query
            # 200, not 401. "/" has served the login form with 200 since the
            # beginning and works through the proxy in front of this box; a
            # reverse proxy running proxy_intercept_errors would swallow a 401
            # body and show its own error page instead of the form. Changing
            # the status of the page that already works, to fix the pages that
            # do not, would be trading one broken door for another.
            return HTMLResponse(_login_html(nxt=nxt), headers=_NO_CACHE)
        return JSONResponse({"detail": "unauthorized — sign in at / or send ?key= / X-API-Key"},
                            status_code=401)

    # Ensure connectors read dashboard-saved credentials on EVERY request path
    # (not only after a get_store() call), so /health etc. reflect them too.
    try:
        import content_engine_connectors as _C
        _C.set_settings_provider(lambda k: get_store().get_setting(k))
    except Exception:
        pass

    # Browsers were caching the dashboard and showing days-old pages ("nothing
    # changed" / "data not showing"). Force revalidation on every load.
    _NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        if not dash_authed(request.cookies):
            return HTMLResponse(_login_html(), headers=_NO_CACHE)
        return HTMLResponse(api_dashboard_html(), headers=_NO_CACHE)

    # VX2 - the new layout, served BESIDE the old one. Same login, same data,
    # same handlers. "/" is untouched, so nothing that works today can break
    # here, and switching back is a URL, not a rollback.
    @app.get("/leads", response_class=HTMLResponse)
    def leads_page(request: Request):
        """The engagement OS, alone, so it is not at the bottom of four
        megabytes of everything else."""
        if not dash_authed(request.cookies):
            return HTMLResponse(_login_html(nxt="/leads"), headers=_NO_CACHE)
        return HTMLResponse(api_leads_html(), headers=_NO_CACHE)

    @app.get("/vx2", response_class=HTMLResponse)
    def vx2(request: Request, b: str = "decide"):
        if not dash_authed(request.cookies):
            return HTMLResponse(_login_html(), headers=_NO_CACHE)
        return HTMLResponse(api_vx2_html(active=b), headers=_NO_CACHE)

    @app.get("/vx2/board/{bid}", response_class=HTMLResponse)
    def vx2_board(bid: str, request: Request):
        """One board's Level 2 HTML on its own."""
        if not dash_authed(request.cookies):
            return HTMLResponse("<p>Session expired. Reload the page.</p>",
                                status_code=401)
        import content_engine_vx2 as VX2
        try:
            return HTMLResponse(VX2.board_html(bid, _dashboard_kwargs()),
                                headers=_NO_CACHE)
        except Exception as ex:
            log.warning("vx2 board %s failed: %s", bid, ex)
            return HTMLResponse(
                "<p class='v2empty'>This board could not be read: "
                f"{type(ex).__name__}. The other boards are unaffected.</p>",
                headers=_NO_CACHE)

    @app.get("/vx2/read/{tab}", response_class=HTMLResponse)
    def vx2_read(tab: str, request: Request):
        """LEVEL 3: one subsection's readout, fetched when you enter it.

        One screen at a time is the design: nothing pre-rendered into hidden
        panes, so the page never carries 53,000 invisible elements again.
        """
        if not dash_authed(request.cookies):
            return HTMLResponse("<p>Session expired. Reload the page.</p>",
                                status_code=401)
        import content_engine_vx2 as VX2
        try:
            return HTMLResponse(VX2.readout_page(tab, _dashboard_kwargs()),
                                headers=_NO_CACHE)
        except Exception as ex:
            log.warning("vx2 readout %s failed: %s", tab, ex)
            return HTMLResponse(
                "<p class='v2empty'>This readout could not be built: "
                f"{type(ex).__name__}. The other subsections are "
                "unaffected.</p>", headers=_NO_CACHE)

    @app.post("/login")
    async def login(request: Request):
        # Parse the urlencoded form by hand so we don't need python-multipart.
        from urllib.parse import parse_qs
        raw = (await request.body()).decode("utf-8", "ignore")
        form = parse_qs(raw)
        password = form.get("password", [""])[0]
        # Land where you were going, not always at "/". Only a local path is
        # accepted: an open redirect on a sign-in form is how a login page
        # gets turned into a way of sending someone somewhere else.
        nxt = form.get("next", [""])[0]
        dest = nxt if (nxt.startswith("/") and not nxt.startswith("//")) else "/"
        if _dash_password() and password == _dash_password():
            resp = RedirectResponse(url=dest, status_code=303)
            resp.set_cookie("aa_dash", _dash_token(), httponly=True,
                            samesite="lax", max_age=60 * 60 * 24 * 14)
            return resp
        # A member signing in with their own address and password. The
        # shared password is checked first so the founder's own login is
        # never slowed by a database read.
        em = form.get("email", [""])[0].strip()
        if em:
            try:
                import content_engine_os_tenancy as _TEN
                got = _TEN.check_login(get_store(), em, password)
            except Exception:
                got = {"ok": False}
            if got.get("ok"):
                resp = RedirectResponse(url=dest, status_code=303)
                resp.set_cookie("aa_user", f"{got['email']}|{got['token']}",
                                httponly=True, samesite="lax",
                                max_age=60 * 60 * 24 * 14)
                resp.set_cookie("ce_ws", got["workspace_id"], httponly=True,
                                samesite="lax")
                return resp
        return HTMLResponse(_login_html("Wrong password", nxt=dest),
                            status_code=401)

    @app.get("/logout")
    def logout():
        resp = RedirectResponse(url="/", status_code=303)
        resp.delete_cookie("aa_user")
        resp.delete_cookie("aa_dash")
        return resp

    @app.get("/health")
    def health():
        return api_health()

    @app.get("/skills")
    def skills():
        return api_list_skills()

    @app.get("/jobs")
    def list_jobs(status: Optional[str] = None):
        return api_list_jobs(status)

    @app.get("/jobs/measurable")
    def measurable():
        return api_list_measurable()

    @app.post("/skills/{skill}/taste")
    def taste(skill: str, body: TasteBody):
        return api_taste_skill(skill, body.input, body.brand, body.model)

    @app.post("/jobs")
    def create(body: JobBody):
        return api_create_job(body.type, body.brand, body.payload, body.job_id)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        return api_get_job(job_id)

    @app.post("/jobs/{job_id}/approve")
    async def approve(job_id: str, request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_approve(job_id, (data or {}).get("note", ""))

    @app.post("/jobs/{job_id}/decline")
    async def decline(job_id: str, request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_decline(job_id, (data or {}).get("note", ""))

    @app.post("/jobs/{job_id}/ready_to_measure")
    def ready(job_id: str):
        return api_ready_to_measure(job_id)

    @app.post("/tick")
    def tick():
        return api_tick()

    @app.post("/replies/answer")
    def answer_replies(limit: int = 20, dry_run: bool = False):
        return api_answer_replies(limit=limit, dry_run=dry_run)

    @app.post("/replies/refresh")
    def replies_refresh(limit: int = 20):
        return api_replies_refresh(limit=limit)

    @app.post("/reply/edit")
    async def reply_edit(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_reply_edit(data.get("id"), data.get("subject"), data.get("body"))

    @app.post("/reply/send")
    async def reply_send(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_reply_send(data.get("id"))

    @app.post("/reply/dismiss")
    async def reply_dismiss(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_reply_dismiss(data.get("id"))

    @app.post("/control/pause")
    def control_pause():
        return api_control("pause")

    @app.post("/control/resume")
    def control_resume():
        return api_control("resume")

    @app.post("/control/autonomy")
    def control_autonomy(on: bool = True):
        return api_autonomy(on)

    @app.post("/jobs/{job_id}/outcome")
    def outcome(job_id: str, leads: int = 0, revenue: float = 0.0, customers: int = 0):
        return api_record_outcome(job_id, leads, revenue, customers)

    @app.post("/schedule/run")
    def schedule_run(force: bool = False):
        return api_schedule_run(force)

    @app.post("/control/auto-run")
    def auto_run():
        return api_auto_run()

    @app.post("/connect")
    async def connect(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_connect(data if isinstance(data, dict) else {})

    @app.post("/disconnect")
    async def disconnect(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        keys = data.get("keys") if isinstance(data, dict) else None
        return api_disconnect(keys)

    @app.post("/brand/ci")
    async def brand_ci(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_save_ci(data.get("text", ""), data.get("drive_folder"),
                           data.get("inspiration"))

    @app.post("/plan/content")
    async def plan_content(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_plan_content(int(data.get("count", 8) or 8))

    # ---- open / click tracking -----------------------------------------
    # These two are the ONLY unauthenticated routes: a mail client fetching a
    # pixel has no session. They accept an opaque token, record one event and
    # return. They read nothing and expose nothing.
    _PIXEL = base64.b64decode(
        b"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

    @app.get("/t/o/{token}.png")
    def track_open(token: str):
        try:
            import content_engine_outreach as O
            O.record_event(get_store(), token, "open")
        except Exception as e:
            log.warning("open pixel not recorded: %s", e)
        return Response(content=_PIXEL, media_type="image/gif",
                        headers={"Cache-Control": "no-store, max-age=0"})

    @app.get("/t/c/{token}")
    def track_click(token: str, u: str = ""):
        """Record the click, then send the reader on. An unsafe or missing
        target goes to the site root rather than anywhere a link says."""
        try:
            import content_engine_outreach as O
            O.record_event(get_store(), token, "click")
        except Exception as e:
            log.warning("click not recorded: %s", e)
        target = u if u.startswith(("http://", "https://")) else             "https://anthropos-automation.com"
        return RedirectResponse(target, status_code=302)

    @app.post("/outreach/tracking")
    async def outreach_tracking(request: Request):
        """Turn open/click tracking on or off for every future send."""
        import content_engine_outreach as O
        try:
            d = await request.json()
        except Exception:
            d = {}
        r = O.set_tracking(get_store(), bool(d.get("enabled")))
        return {"ok": True, **r,
                "message": ("Tracking on — a 1x1 pixel and wrapped links are "
                            "added to the HTML part of every send."
                            if r["enabled"] else
                            "Tracking off — nothing is added to your emails.")}

    @app.post("/proposal")
    async def resolve_rewrite_proposal(request: Request):
        """Accept or decline a rewrite PROPOSAL. A measured-poor piece earns a
        card in the queue, never an automatic rewrite — rewriting spends money
        and republishes to a live site, and both stay behind this gate."""
        try:
            d = await request.json()
        except Exception:
            d = {}
        return orch.resolve_proposal(get_store(), d.get("job_id", ""),
                                     bool(d.get("accept")), d.get("note", ""))

    @app.post("/experiment")
    async def start_experiment(request: Request):
        """A stated hypothesis with one metric and a review date."""
        import content_engine_cockpit as CK
        try:
            d = await request.json()
        except Exception:
            d = {}
        r = CK.start_experiment(get_store(), d.get("hypothesis"),
                                d.get("metric"), d.get("review_days", 14),
                                d.get("note", ""))
        if r.get("ok"):
            r["message"] = f"Experiment saved. {r.get('message', '')}"
        return r

    @app.post("/budget")
    async def set_budget(request: Request):
        """Change the spend caps from the browser. Settings-first, so the worker
        picks it up on its next loop with no restart."""
        try:
            d = await request.json()
        except Exception:
            d = {}
        store = get_store()
        spent = 0.0
        try:
            m = getattr(store, "monthly_cost", None)
            spent = float(m() if callable(m) else 0.0)
        except Exception:
            pass
        return orch.set_budget_caps(store, per_job=d.get("per_job"),
                                    per_day=d.get("per_day"),
                                    per_month=d.get("per_month"),
                                    spent_this_month=spent,
                                    note=d.get("note", ""))

    @app.post("/fix/{fid}")
    def run_one_fix(fid: str, arg: str = ""):
        """ONE endpoint for every card-level fix.

        Before this, 314 buttons posted to seven global endpoints and not one
        card could repair its own problem. A handler per board is how a
        codebase ends up with five capabilities that were built and never
        wired; a registry with an import-time assertion cannot."""
        import content_engine_fixes as FX
        return FX.run_fix(fid, get_store(), arg)

    @app.post("/fix-all/{section}")
    def run_safe_fixes(section: str = ""):
        """Every SAFE fix a finding is asking for, in one press. Anything that
        costs money or cannot be undone is skipped and named."""
        import content_engine_fixes as FX
        return FX.run_safe_batch(get_store(), "" if section == "all" else section)

    @app.get("/fix")
    def list_fixes():
        """What the engine can repair, and which of those an agent may run."""
        import content_engine_fixes as FX
        s = FX.summary()
        s["fixes"] = [{"id": f.id, "label": f.label, "cost": f.cost,
                       "auto": f.auto, "reversible": f.reversible,
                       "requires": list(f.requires), "section": f.section}
                      for f in FX.REGISTRY.values()]
        return s

    @app.get("/content/record/{job_id}")
    def content_record(job_id: str):
        """THE DECISION RECORD, SERVED ON DEMAND.

        Every calendar row used to embed its full record (preview frames,
        QA notes, the lot) inline - 112 platform previews on one page load,
        which the founder experienced as "crashing, taking long time to
        load". The page now carries one compact line per piece; tapping it
        fetches THIS. At the founder's target volume (8 pieces/day) inline
        embedding would re-break monthly; on-demand cannot."""
        store = get_store()
        try:
            job = store.get(job_id)
        except KeyError:
            return HTMLResponse("<p style='padding:16px'>No such piece.</p>",
                                status_code=404)
        import content_engine_seo_ops as _OPS9
        import content_engine_decision as _DEC9
        rows = _OPS9._calendar_rows([job])
        row = rows[0] if rows else {}
        html = _DEC9.decision_pane("rec-live", job, row)
        # the pane class is display:none for the inline flow; served alone
        # it must be visible
        return HTMLResponse(html.replace("class='dpane'",
                                         "class='dpane' "
                                         "style='display:block'", 1))

    @app.post("/content/piece-image")
    def content_piece_image(job_id: str = ""):
        """Generate the hero image for a piece that has none, and ATTACH it.

        /content/test-image proves the key works and throws the picture away.
        A piece produced before the image gate was fixed carries image_error
        for ever and nothing could give it one — the operator was told to
        re-run a whole piece (six model calls, minutes, real money) to get a
        picture the engine could make in twenty seconds.

        Costs about EUR 0.04. Human-triggered only; publishes nothing."""
        store = get_store()
        jid = str(job_id or "").strip()
        if not jid:
            # default to the newest piece that is waiting on a person
            try:
                cands = [j for j in store.list_jobs()
                         if j.get("type") == "content_piece"
                         and j.get("status") == "AWAITING_APPROVAL"]
                cands.sort(key=lambda j: j.get("created_at") or "", reverse=True)
                jid = cands[0]["job_id"] if cands else ""
            except Exception:
                jid = ""
        if not jid:
            return {"ok": False, "error": "No piece is waiting for approval."}
        try:
            job = store.get(jid)
        except KeyError:
            return {"ok": False, "error": f"no such job: {jid}"}
        pl = job.setdefault("payload", {})
        piece = pl.get("content_producer") or {}
        if not piece:
            return {"ok": False, "error": "That job never produced a piece."}
        piece.pop("image_url", None)          # force a real attempt
        pl.pop("image_url", None)
        pl.pop("image_error", None)
        try:
            import content_engine_prep as P
            P._ensure_hero_image(job)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
        url = (pl.get("content_producer") or {}).get("image_url") or ""
        store.save(job)
        if url:
            return {"ok": True, "url": url, "job_id": jid,
                    "message": "Image generated, hosted, and attached to the "
                               "piece. Reload the preview to see it."}
        return {"ok": False, "job_id": jid,
                "error": pl.get("image_error") or "no image came back"}

    @app.post("/content/test-image")
    def content_test_image():
        """Generate ONE real image so you can see whether the key works and
        whether the style matches your brand. Costs about EUR 0.04."""
        try:
            import content_engine_connectors as C
            import content_engine_site_taxonomy as TAX
            import content_engine_brand as B
            ci = B.get_ci_block() if hasattr(B, "get_ci_block") else ""
            url = C.generate_image(TAX.image_prompt(
                "AI automation for a Munich clinic", ci))
            if url:
                return {"ok": True, "url": url,
                        "message": "Image generated and hosted. Open the URL to "
                                   "see whether the style matches your brand."}
            return {"ok": False,
                    "error": ("No image came back. Check IMAGE_API_KEY is an "
                              "OpenAI key - Anthropic has no image API, so a "
                              "Claude key cannot work here.")}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.post("/sga/campaign")
    async def sga_campaign(request: Request):
        """Save a social campaign. It becomes the utm_campaign on every post
        made while it runs, and the budget line on the paid boards."""
        import content_engine_sga as SGA
        try:
            d = await request.json()
        except Exception:
            d = {}
        r = SGA.save_campaign(get_store(), d.get("name"),
                              objective=d.get("objective", "awareness"),
                              channels=d.get("channels"), start=d.get("start"),
                              end=d.get("end"), budget=d.get("budget", 0),
                              paid=bool(d.get("paid")), note=d.get("note", ""))
        if r.get("ok"):
            c = r["campaign"]
            r["message"] = (f"{c['name']} saved — utm_campaign={c['id']} on every "
                            f"post while it runs.")
        return r

    @app.post("/sga/campaign/delete")
    async def sga_campaign_delete(request: Request):
        import content_engine_sga as SGA
        try:
            d = await request.json()
        except Exception:
            d = {}
        ok = SGA.delete_campaign(get_store(), d.get("id"))
        return {"ok": ok, "message": "Campaign removed." if ok else "Not found."}

    @app.post("/leads/edit")
    async def leads_edit(request: Request):
        """Correct one lead's details. There was no way to fix a wrong name,
        a missing LinkedIn or a bad company anywhere in the engine."""
        try:
            d = await request.json()
        except Exception:
            d = {}
        return api_lead_edit(d.get("job_id", ""), d.get("email", ""),
                             {k: d.get(k) for k in
                              ("name", "title", "company", "linkedin", "phone",
                               "country", "website", "vertical", "email")})

    @app.post("/leads/delete")
    async def leads_delete(request: Request):
        """Remove a lead from a campaign. Soft — it goes to a removed list and
        is never emailed again, rather than being erased."""
        try:
            d = await request.json()
        except Exception:
            d = {}
        return api_lead_delete(d.get("job_id", ""), d.get("email", ""),
                               d.get("reason", "removed by hand"))

    @app.post("/leads/maps")
    async def leads_maps(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_source_maps_leads(data.get("vertical", ""), data.get("city", ""),
                                     int(data.get("count", 20) or 20))

    @app.post("/insights/refresh")
    def insights_refresh():
        return api_refresh_insights()

    @app.post("/competitors/scan")
    async def competitors_scan(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        doms = data.get("domains") or []
        if isinstance(doms, str):
            doms = [d.strip() for d in doms.split(",") if d.strip()]
        return api_competitor_scan(domains=doms, limit=int(data.get("limit", 5) or 5))

    # ---- SEO engine (E1-E14) -------------------------------------------
    @app.post("/seo/crawl")
    def seo_crawl():
        return api_seo("crawl")

    @app.post("/seo/inspect")
    def seo_inspect():
        return api_seo("inspect")

    @app.post("/seo/speed")
    def seo_speed():
        return api_seo("speed")

    @app.post("/seo/indexnow")
    def seo_indexnow():
        return api_seo("indexnow")

    @app.post("/seo/ranks")
    def seo_ranks():
        return api_seo("ranks")

    @app.post("/seo/fix-all")
    def seo_fix_all():
        return api_seo("fixes")

    @app.post("/seo/run-all")
    def seo_run_all():
        return api_seo("all")

    @app.post("/seo/auto")
    async def seo_auto(request: Request):
        """Unattended technical SEO: off | safe | all.

        Deliberately separate from /system/start. Fixing a missing alt
        attribute is not the same decision as publishing an article."""
        import content_engine_scheduler as _S
        try:
            d = await request.json()
        except Exception:
            d = {}
        return _S.set_seo_auto(get_store(), d.get("level", "off"))

    @app.post("/seo/due")
    def seo_due_run():
        """Run only the SEO engines that are due (self-throttling). Point an
        hourly n8n cron here and the whole SEO loop runs itself."""
        try:
            import content_engine_scheduler as S
            return {"ok": True, **S.run_seo_due(get_store())}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.get("/seo/workorders")
    def seo_workorders():
        return api_seo_workorders()

    @app.post("/seo/fix/{order_id}")
    def seo_fix_one(order_id: str):
        return api_seo_apply(order_id)

    @app.post("/seo/approve-all")
    def seo_approve_all(type: str = "title"):
        return api_seo_approve_all(type)

    # THE EXECUTION PATH. /seo/fix/{id} APPROVES a drafted proposal and
    # refuses anything undrafted - correct, but it left the dashboard's
    # "Fix now" and "Draft a fix" buttons with nowhere honest to land.
    # These three run the fixer's ONE dispatch (run_batch) filtered to a
    # set of orders, one page, or everything draftable, so a button behaves
    # exactly like the nightly batch would on the same rows.
    @app.post("/seo/run-orders")
    async def seo_run_orders(request: Request):
        try:
            d = await request.json()
        except Exception:
            d = {}
        ids = [str(x) for x in (d.get("ids") or []) if x][:200]
        if not ids:
            return {"ok": False, "message": "no order ids given; nothing ran"}
        import content_engine_seo_ops as SEO
        store = get_store()
        rep = SEO.run_fixes(store, auto_only=False, limit=len(ids), ids=ids)
        _log_decision(store, "seo_fix_ran",
                      f"{len(ids)} order(s) by button",
                      f"done {rep.get('done', 0)}, drafted "
                      f"{rep.get('awaiting_approval', 0)}, "
                      f"failed {rep.get('failed', 0)}")
        return {"ok": True, **rep, "message":
                f"{rep.get('done', 0)} fixed now, "
                f"{rep.get('awaiting_approval', 0)} drafted for your "
                f"approval, {rep.get('skipped', 0)} skipped with a reason, "
                f"{rep.get('failed', 0)} failed."}

    @app.post("/seo/fix-page")
    async def seo_fix_page(request: Request):
        try:
            d = await request.json()
        except Exception:
            d = {}
        url = str(d.get("url") or "").strip()
        if not url:
            return {"ok": False, "message": "no url given; nothing ran"}
        import content_engine_seo_ops as SEO
        store = get_store()
        rep = SEO.run_fixes(store, auto_only=False, limit=50, urls=[url])
        _log_decision(store, "seo_fix_ran", f"whole page {url[:80]}",
                      f"done {rep.get('done', 0)}, drafted "
                      f"{rep.get('awaiting_approval', 0)}")
        return {"ok": True, **rep, "message":
                f"{url}: {rep.get('done', 0)} fixed now, "
                f"{rep.get('awaiting_approval', 0)} drafted for your "
                f"approval. Nothing publishes without you."}

    @app.post("/seo/draft-all")
    def seo_draft_all(limit: int = 100):
        """Draft every approval-gated fix. CAPPED PER CLICK: title and meta
        drafts each cost one model call, so one click drafts up to `limit`
        and says how many remain rather than silently spending the budget."""
        import content_engine_seo_ops as SEO
        import content_engine_workorders as WO
        store = get_store()
        limit = max(1, min(int(limit or 100), 250))
        rep = SEO.run_fixes(store, auto_only=False, limit=limit)
        remaining = sum(1 for o in WO.load(store)
                        if o.get("status") == "open")
        _log_decision(store, "seo_draft_all", f"batch of {limit}",
                      f"drafted {rep.get('awaiting_approval', 0)}, "
                      f"{remaining} still open")
        return {"ok": True, **rep, "message":
                f"{rep.get('done', 0)} fixed now, "
                f"{rep.get('awaiting_approval', 0)} drafted. "
                f"{remaining} orders still open - press again for the next "
                f"batch. Capped per click because copy drafts cost model "
                f"calls."}

    @app.get("/seo/llms.txt")
    def seo_llms_txt():
        from fastapi.responses import PlainTextResponse
        store = get_store()
        txt = store.get_setting("seo_llms_txt", "") if hasattr(store, "get_setting") else ""
        return PlainTextResponse(txt or "# not generated yet — run an AEO probe")

    @app.post("/aeo/probe")
    def aeo_probe():
        return api_seo("aeo")

    @app.post("/geo/audit")
    def geo_audit():
        return api_seo("geo")

    @app.post("/bi/deal")
    async def bi_deal(request: Request):
        """Record a won deal. The input path revenue, customers and unit
        economics never had — and it carries the client name that the Risk
        board's concentration chart reads."""
        import content_engine_bi as BI
        try:
            d = await request.json()
        except Exception:
            d = {}
        r = BI.record_deal(get_store(), d.get("client"), d.get("value"),
                           source=d.get("source", "other"), at=d.get("at"),
                           margin_pct=d.get("margin_pct"),
                           recurring=bool(d.get("recurring")),
                           note=d.get("note", ""))
        if r.get("ok"):
            r["message"] = (f"{r['deal']['client']} · €{r['deal']['value']:,.0f}. "
                            f"{r['total_deals']} deal(s) recorded.")
        return r

    @app.post("/bi/econ")
    async def bi_econ(request: Request):
        import content_engine_bi as BI
        try:
            d = await request.json()
        except Exception:
            d = {}
        e = BI.set_econ(get_store(), avg_deal=d.get("avg_deal"),
                        margin_pct=d.get("margin_pct"),
                        consult_to_client_pct=d.get("consult_to_client_pct"))
        return {"ok": True, "econ": e, "message": "Unit economics updated."}

    @app.post("/bi/targets")
    async def bi_targets(request: Request):
        import content_engine_bi as BI
        try:
            d = await request.json()
        except Exception:
            d = {}
        t = BI.set_targets(get_store(), **{k: d.get(k) for k in
                                           ("revenue_month", "deals_month",
                                            "leads_month", "bookings_month")})
        return {"ok": True, "targets": t, "message": "Targets set."}

    @app.post("/insights/refresh")
    def insights_refresh():
        """Re-pull GA4 + Search Console. Free — Google does not bill these."""
        try:
            import content_engine_connectors as CN
            fresh = CN.google_insights(force=True) if hasattr(CN, "google_insights") \
                else None
            ga = ((fresh or {}).get("ga4") or {})
            return {"ok": True,
                    "message": f"{len((ga.get('daily') or []))} days of GA4, "
                               f"{len((fresh or {}).get('gsc') or [])} GSC rows."}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.post("/risk/refresh")
    def risk_refresh():
        """Recompute the register from current data. Free — reads only."""
        try:
            import content_engine_seo_ops as SEO
            import content_engine_dashboard as DD
            store = get_store()
            ctx = SEO.build_risk_ctx(store, status=_connectors_status(),
                                     health=run_health(), jobs=store.list_jobs()
                                     if hasattr(store, "list_jobs") else [])
            risks = ctx.get("risks") or []
            return {"ok": True, "risks": len(risks),
                    "critical": sum(1 for r in risks if r.get("score", 0) >= 6),
                    "top": (risks[0].get("title") if risks else None)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.post("/risk/status/{risk_id}")
    async def risk_status(risk_id: str, request: Request):
        import content_engine_risk as RK
        try:
            data = await request.json()
        except Exception:
            data = {}
        ok = RK.set_status(get_store(), risk_id, data.get("status", "accepted"),
                           data.get("note", ""))
        return {"ok": ok}

    # ---- Media buying ----
    @app.post("/ads/pull")
    def ads_pull():
        return api_seo("ads")

    @app.post("/ads/interlock")
    def ads_interlock():
        return api_seo("interlock")

    @app.post("/ads/offline-conversions")
    def ads_offline():
        """M9 — feed WON deals back so Google bids for clients, not form fills."""
        import content_engine_ads as A
        store = get_store()
        rows = []
        try:
            for j in (store.list_jobs() if hasattr(store, "list_jobs") else []):
                o = (j.get("payload", {}) or {}).get("outcome") or {}
                if o.get("gclid") and o.get("revenue"):
                    rows.append({"gclid": o["gclid"], "value": o["revenue"],
                                 "conversion_date_time": o.get("won_at", "")})
        except Exception as e:
            log.warning("offline conversion gather failed: %s", e)
        return {"ok": True, **A.upload_offline_conversions(rows)}

    @app.get("/ads/economics")
    def ads_econ_get():
        import content_engine_ads as A
        econ = A.get_economics(get_store())
        return {"ok": True, "economics": econ, "targets": A.targets(econ)}

    @app.post("/ads/economics")
    async def ads_econ_set(request: Request):
        import content_engine_ads as A
        try:
            data = await request.json()
        except Exception:
            data = {}
        econ = A.set_economics(get_store(), **data)
        return {"ok": True, "economics": econ, "targets": A.targets(econ)}

    @app.get("/aeo/prompts")
    def aeo_prompts_get():
        import content_engine_aeo as AEO
        return {"ok": True, "prompts": AEO.get_prompts(get_store())}

    @app.post("/aeo/prompts")
    async def aeo_prompts_set(request: Request):
        import content_engine_aeo as AEO
        try:
            data = await request.json()
        except Exception:
            data = {}
        raw = data.get("prompts") or []
        if isinstance(raw, str):
            raw = [p for p in raw.splitlines()]
        n = AEO.set_prompts(get_store(), raw)
        return {"ok": True, "saved": n}

    @app.post("/offpage/scan")
    def offpage_scan():
        return api_seo("offpage")

    @app.post("/offpage/prospect")
    def offpage_prospect():
        return api_seo("prospecting")

    @app.post("/plan/approve")
    def plan_approve():
        return api_approve_plan()

    @app.post("/plan/clear")
    def plan_clear():
        return api_clear_plan()

    @app.post("/autopilot/run")
    def autopilot_run():
        return api_autopilot(True)

    @app.post("/autopilot/stop")
    def autopilot_stop():
        return api_autopilot(False)

    @app.post("/outreach/send_all")
    def outreach_send_all():
        return api_outreach_send_all()

    @app.post("/outreach/trash")
    async def outreach_trash(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_outreach_trash(data.get("job_id"), data.get("email", ""), bool(data.get("restore")))

    @app.post("/outreach/edit")
    async def outreach_edit(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_outreach_edit(data.get("job_id"), data.get("email", ""),
                                 data.get("subject", ""), data.get("body", ""),
                                 touch=data.get("touch", 1))

    @app.post("/outreach/send_one")
    async def outreach_send_one(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_outreach_send_one(data.get("job_id"), data.get("email", ""), data.get("touch"))

    @app.post("/outreach/send_batch")
    async def outreach_send_batch(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_outreach_send_batch(data.get("job_id"), data.get("emails"))

    @app.post("/ads/test")
    def ads_test():
        try:
            import content_engine_connectors as C
            return C.GoogleAds().diag()
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    @app.post("/system/start")
    def system_start(autonomous: bool = False):
        """Supervised by default. `?autonomous=true` is the deliberate opt-in
        to publishing without you after the grace period."""
        return api_start(autonomous=autonomous)

    @app.post("/system/stop")
    def system_stop():
        return api_stop()

    @app.post("/selftest")
    def selftest():
        try:
            import content_engine_selftest as ST
            return ST.run_smoke()
        except Exception as e:
            return {"error": str(e)[:200]}

    @app.post("/evals/run")
    def evals_run():
        return api_run_evals()

    @app.post("/api-limits/set")
    async def api_limits_set(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        try:
            import content_engine_connectors as C
            return {"limits": C.set_api_limit(str(data.get("api", "")), float(data.get("usd", 0)))}
        except Exception as e:
            return {"error": str(e)[:120]}

    # MEDIA AGENT + TAG MANAGER. Every route lands on the one dispatch or
    # the gated GTM machinery; empty input is refused in words.
    @app.post("/social/refresh")
    def social_refresh():
        """Pull every connected channel's insights. A channel with no key
        returns its honest blank naming the missing setting."""
        import content_engine_seo_ops as O
        store = get_store()
        out = O.run_social(store)
        _log_decision(store, "social_refresh",
                      f"{len(out.get('live') or ())} channel(s) reporting",
                      out.get("message", "")[:120])
        return {"ok": True, **{k: out.get(k) for k in
                               ("at", "live", "message")}}

    # ---------------------------------------------------------------
    # THE ENGAGEMENT OS
    # ---------------------------------------------------------------
    #: A small in-process limiter for the PUBLIC pages only. Not a
    #: replacement for a proper edge limiter: it is here so a single machine
    #: cannot walk a list of addresses through the signup form, which is the
    #: realistic abuse of a public consent endpoint.
    _RATE = {}
    _RATE_MAX, _RATE_WINDOW = 12, 60.0

    def _client_ip(request) -> str:
        fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        return fwd or (getattr(request.client, "host", "") or "")

    def _os_rate(request, bucket, ceiling=None) -> bool:
        import time
        ceiling = int(ceiling or _RATE_MAX)
        key = f"{bucket}|{_client_ip(request)}"
        cut = time.time() - _RATE_WINDOW
        hits = [t for t in _RATE.get(key, []) if t > cut]
        hits.append(time.time())
        _RATE[key] = hits[-(ceiling + 4):]
        if len(_RATE) > 5000:                 # never grow without bound
            _RATE.clear()
        return len(hits) <= ceiling

    async def _form_or_json(request) -> dict:
        """A browser posts a form; an integration posts JSON. Both arrive
        at the same consent function rather than at two of them."""
        ctype = (request.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            try:
                return await request.json()
            except Exception:
                return {}
        try:
            return {k: v for k, v in (await request.form()).items()}
        except Exception:
            return {}

    def _ws(request=None) -> str:
        """The workspace this request is entitled to. A cookie is a REQUEST;
        the guard decides."""
        import content_engine_os_tenancy as TEN
        want = ""
        if request is not None:
            try:
                want = request.cookies.get(TEN.WS_COOKIE) or ""
            except Exception:
                want = ""
        return TEN.require(get_store(), want, grant="read")["workspace_id"]

    def _os():
        """(module, store, jobs). One helper so no route re-derives them."""
        import content_engine_os as _OS
        st = get_store()
        js = st.list_jobs(status=None) if hasattr(st, "list_jobs") else []
        return _OS, st, js

    async def _body(request):
        try:
            return await request.json()
        except Exception:
            return {}

    @app.get("/os/campaign/{cid}", response_class=HTMLResponse)
    def os_campaign(cid: str, email: str = "", touch: int = 1):
        """The campaign detail: the real email on the left, the numbers on
        the right. The preview resolves through the engine's own send path,
        so what is drawn here is what leaves the building."""
        OS, store, jobs = _os()
        try:
            return HTMLResponse(OS.campaign_html(store, cid, jobs=jobs,
                                                 email=email, touch=touch))
        except Exception as e:
            log.exception("campaign detail failed")
            return HTMLResponse("<p class='os-empty'>That campaign could not "
                                f"be drawn: {type(e).__name__}: {e}</p>")

    @app.get("/os/profile/{pid}", response_class=HTMLResponse)
    def os_profile(pid: str):
        OS, store, _ = _os()
        try:
            return HTMLResponse(OS.profile_html(store, pid))
        except Exception as e:
            log.exception("profile detail failed")
            return HTMLResponse("<p class='os-empty'>That person could not be "
                                f"drawn: {type(e).__name__}: {e}</p>")

    @app.post("/os/sync")
    def os_sync():
        """Re-read the engine's live jobs into the OS. Idempotent."""
        OS, store, jobs = _os()
        out = OS.sync(store, jobs)
        _log_decision(store, "os_sync", f"{out.get('profiles')} profiles",
                      out.get("message", ""))
        return {"ok": True, **out}

    @app.post("/os/message/save")
    async def os_message_save(request: Request):
        """Save the founder's correction of ONE email.

        It writes payload.email_edits, which is the first thing the resolver
        consults, so this is not a note about the email: it IS the email."""
        d = await _body(request)
        OS, store, _ = _os()
        return OS.save_edit(store, d.get("campaign_id", ""),
                            (d.get("email") or "").strip().lower(),
                            d.get("touch") or 1, d.get("subject", ""),
                            d.get("body", ""))

    @app.post("/os/campaign/save")
    async def os_campaign_save(request: Request):
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, _ = _os()
        return SEND.save_campaign(
            OS.repo(store), campaign_id=d.get("id", ""), name=d.get("name", ""),
            audience_kind=d.get("audience_kind", "all"),
            audience_id=d.get("audience_id", ""),
            subject=d.get("subject", ""), body=d.get("body", ""),
            scheduled_at=d.get("scheduled_at", ""))

    @app.post("/os/campaign/plan")
    async def os_campaign_plan(request: Request):
        """The review step. Runs every gate the real send runs, so the
        number it reports is the number that would leave."""
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, jobs = _os()
        pl = SEND.plan(OS.repo(store), d.get("id", ""), jobs=jobs,
                       touch=int(d.get("touch") or 1))
        if not pl.get("ok"):
            return pl
        why = ", ".join(f"{n} {SEND.GATE_REASONS[k]}"
                        for k, n in pl["refused_counts"].items() if n)
        return {"ok": True, "deliverable": pl["deliverable"],
                "pool": pl["pool"],
                "message": (f"{pl['deliverable']} of {pl['pool']} would "
                            f"receive this"
                            + (f". Refused: {why}" if why else "")
                            + (f". {pl['rate_why']}." if pl.get("rate_why")
                               else ""))}

    @app.post("/os/campaign/queue")
    async def os_campaign_queue(request: Request):
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, jobs = _os()
        out = SEND.queue(OS.repo(store), d.get("id", ""), jobs=jobs,
                         touch=int(d.get("touch") or 1))
        _log_decision(store, "os_queued", str(d.get("id"))[:40],
                      out.get("message", ""))
        return out

    @app.post("/os/campaign/approve")
    async def os_campaign_approve(request: Request):
        """The human act. Until this runs the worker will not touch a row."""
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, _ = _os()
        out = SEND.approve(OS.repo(store), d.get("id", ""))
        _log_decision(store, "os_approved", str(d.get("id"))[:40],
                      out.get("message", ""))
        return out

    @app.post("/os/campaign/cancel")
    async def os_campaign_cancel(request: Request):
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, _ = _os()
        return SEND.cancel(OS.repo(store), d.get("id", ""))

    @app.post("/os/campaign/state")
    async def os_campaign_state(request: Request):
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, _ = _os()
        return SEND.move_campaign(OS.repo(store), d.get("id", ""),
                                  str(d.get("state") or "").upper())

    @app.post("/os/queue/work")
    def os_queue_work():
        """Send the approved rows. THE ONLY PATH TO A PROVIDER."""
        import content_engine_os_send as SEND
        OS, store, jobs = _os()
        out = SEND.work_queue(OS.repo(store), jobs=jobs)
        _log_decision(store, "os_sent", f"{out.get('sent')} sent",
                      out.get("message", ""))
        return out

    @app.post("/os/segment/save")
    async def os_segment_save(request: Request):
        d = await _body(request)
        import content_engine_os_audience as AUD
        OS, store, _ = _os()
        return AUD.save_segment(OS.repo(store), d.get("name"), d.get("tree"))

    @app.post("/os/segment/count")
    async def os_segment_count(request: Request):
        """Answer "how many people" before anything is saved."""
        d = await _body(request)
        import content_engine_os_audience as AUD
        OS, store, _ = _os()
        ok, why = AUD.validate(d.get("tree"))
        if not ok:
            return {"ok": False, "message": why}
        repo = OS.repo(store)
        n = len(AUD.members(repo, {"tree": d.get("tree")}))
        return {"ok": True, "size": n,
                "message": f"{n} people match: {AUD.describe(d.get('tree'))}"}

    @app.post("/os/segment/delete")
    async def os_segment_delete(request: Request):
        d = await _body(request)
        import content_engine_os_audience as AUD
        OS, store, _ = _os()
        return AUD.delete_segment(OS.repo(store), d.get("id", ""))

    @app.post("/os/list/save")
    async def os_list_save(request: Request):
        d = await _body(request)
        import content_engine_os_audience as AUD
        OS, store, _ = _os()
        return AUD.save_list(OS.repo(store), d.get("name"),
                             d.get("description", ""))

    @app.post("/os/template/save")
    async def os_template_save(request: Request):
        d = await _body(request)
        import content_engine_os_content as CT
        OS, store, _ = _os()
        return CT.save_template(OS.repo(store), d.get("name"),
                                blocks=d.get("blocks"),
                                subject=d.get("subject", ""),
                                preview_text=d.get("preview_text", ""),
                                publish=bool(d.get("publish")))

    @app.post("/os/flow/save")
    async def os_flow_save(request: Request):
        d = await _body(request)
        import content_engine_os_flows as FL
        OS, store, _ = _os()
        return FL.save_flow(OS.repo(store), flow_id=d.get("id", ""),
                            name=d.get("name", ""), nodes=d.get("nodes"),
                            edges=d.get("edges"))

    @app.post("/os/flow/activate")
    async def os_flow_activate(request: Request):
        d = await _body(request)
        import content_engine_os_flows as FL
        OS, store, _ = _os()
        return FL.activate(OS.repo(store), d.get("id", ""))

    @app.post("/os/flow/pause")
    async def os_flow_pause(request: Request):
        d = await _body(request)
        import content_engine_os_flows as FL
        OS, store, _ = _os()
        return FL.pause(OS.repo(store), d.get("id", ""))

    @app.post("/os/flow/enroll")
    async def os_flow_enroll(request: Request):
        d = await _body(request)
        import content_engine_os_flows as FL
        OS, store, _ = _os()
        return FL.enroll(OS.repo(store), d.get("id", ""),
                         d.get("profile_ids") or [])

    @app.post("/os/flow/advance")
    def os_flow_advance():
        """Move everyone forward one pass. Queues; never sends."""
        import content_engine_os_flows as FL
        OS, store, jobs = _os()
        return FL.advance(OS.repo(store), jobs=jobs)

    @app.post("/os/domain/check")
    async def os_domain_check(request: Request):
        d = await _body(request)
        OS, store, _ = _os()
        return OS.check_domain(store, d.get("domain"), d.get("selector", ""))

    @app.post("/os/consent")
    async def os_consent(request: Request):
        d = await _body(request)
        import content_engine_os_core as CO
        OS, store, _ = _os()
        out = CO.set_consent(OS.repo(store), d.get("email"),
                             str(d.get("status") or "").upper(),
                             source="dashboard", method="recorded by the founder")
        out.setdefault("message", f"{d.get('email')} recorded as "
                                  f"{d.get('status')}")
        return out

    @app.post("/os/suppress")
    async def os_suppress(request: Request):
        d = await _body(request)
        import content_engine_os_core as CO
        OS, store, _ = _os()
        out = CO.suppress(OS.repo(store), d.get("email"),
                          str(d.get("reason") or "MANUAL").upper(),
                          d.get("note", ""))
        out.setdefault("message", f"{d.get('email')} will never be emailed "
                                  f"again")
        return out

    @app.post("/os/rollup")
    def os_rollup():
        import content_engine_os_analytics as AZ
        OS, store, _ = _os()
        return AZ.rollup(OS.repo(store))

    @app.post("/os/webhook/{provider}")
    async def os_webhook(provider: str, request: Request):
        """An ESP callback. Idempotent by construction: the event key is
        derived from its content, so a redelivery writes nothing twice."""
        d = await _body(request)
        import content_engine_os_send as SEND
        OS, store, _ = _os()
        return SEND.ingest_webhook(OS.repo(store), d, provider)

    @app.post("/os/send-one")
    async def os_send_one(request: Request):
        """Send ONE email to ONE person, right now, from the campaign detail.

        This is the founder's own proven single-send path (the same function
        the old outbox button called), reached from the screen where he has
        just read the email and can see who gets it. It saves nothing new:
        api_outreach_send_one resolves through the same resolver the preview
        used, so the bytes on screen are the bytes that leave."""
        d = await _body(request)
        OS, store, _ = _os()
        c = OS.repo(store, _ws(request)).one("campaigns",
                                             d.get("campaign_id") or "")
        jid = (c or {}).get("job_id")
        if not jid:
            return {"ok": False,
                    "message": "this campaign is not one of the engine's "
                               "outreach jobs, so use Queue and Approve "
                               "instead"}
        out = api_outreach_send_one(jid, d.get("email"), d.get("touch"))
        out.setdefault("message",
                       f"sent to {d.get('email')}" if out.get("ok")
                       else str(out.get("error") or "not sent"))
        _log_decision(store, "os_send_one", str(d.get("email"))[:60],
                      out.get("message", ""))
        return out

    @app.get("/os/export/{name}.{fmt}")
    def os_export(name: str, fmt: str, segment: str = "", list: str = "",
                  campaign: str = "", code: str = ""):
        """Every table, as CSV, Excel or JSON. name=workbook gives one file
        with a tab per table."""
        from fastapi.responses import Response
        OS, store, _ = _os()
        try:
            flt = {k: v for k, v in (("segment", segment), ("list", list),
                                     ("campaign", campaign), ("code", code))
                   if v}
            fname, mime, data = OS.export(store, name, fmt, _ws(None), flt)
        except KeyError:
            return JSONResponse({"ok": False,
                                 "message": f"there is no table called "
                                            f"{name!r}"}, status_code=404)
        except Exception as e2:
            log.exception("export failed")
            return JSONResponse({"ok": False,
                                 "message": f"{type(e2).__name__}: {e2}"},
                                status_code=500)
        return Response(content=data, media_type=mime, headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Cache-Control": "no-store"})

    def _uploaded(d) -> tuple:
        """(filename, bytes). The browser sends base64 in JSON rather than
        multipart, so no new server dependency is needed to accept a file."""
        import base64
        raw = str(d.get("b64") or "")
        if "," in raw[:80] and raw[:5] == "data:":
            raw = raw.split(",", 1)[1]
        try:
            return str(d.get("filename") or "upload.csv"), base64.b64decode(raw)
        except Exception:
            return "", b""

    @app.post("/os/import/preview", response_class=HTMLResponse)
    async def os_import_preview(request: Request):
        """Read the file and show what WOULD happen. Writes nothing."""
        d = await _body(request)
        OS, store, _ = _os()
        name, data = _uploaded(d)
        if not data:
            return HTMLResponse("<p class='os-warn'>that file could not be "
                                "decoded</p>")
        pv = OS.import_preview(store, name, data, d.get("mapping"),
                               _ws(request))
        return HTMLResponse(OS.import_preview_html(pv))

    @app.post("/os/import/commit")
    async def os_import_commit(request: Request):
        """Write the file in, through the audited service layer."""
        d = await _body(request)
        OS, store, _ = _os()
        name, data = _uploaded(d)
        if not data:
            return {"ok": False, "message": "that file could not be decoded"}
        out = OS.import_commit(store, name, data, d.get("mapping"),
                               d.get("list_name") or "", _ws(request))
        _log_decision(store, "os_import", name[:60], out.get("message", ""))
        return out

    @app.post("/os/drive/push")
    def os_drive_push():
        """Mirror everything into the Google Drive folder. Never reads back."""
        OS, store, _ = _os()
        out = OS.drive_push(store, _ws(None))
        _log_decision(store, "os_drive", str(len(out.get("written", []))),
                      out.get("message", ""))
        return out

    @app.get("/os/page/{target}", response_class=HTMLResponse)
    def os_page(target: str, page: int = 1, size: int = 50, q: str = ""):
        """One page of one long table. Every table goes through here."""
        OS, store, _ = _os()
        try:
            return HTMLResponse(OS.page(store, target, page, size, q,
                                        _ws(None)))
        except Exception as e2:
            log.exception("paging failed")
            return HTMLResponse("<p class='os-empty'>That page could not be "
                                f"drawn: {type(e2).__name__}</p>")

    @app.get("/os/profiles/search", response_class=HTMLResponse)
    def os_profiles_search(q: str = ""):
        OS, store, _ = _os()
        return HTMLResponse(OS.search_profiles(store, q, _ws(None)))

    @app.get("/os/segment/{sid}")
    def os_segment_get(sid: str):
        OS, store, _ = _os()
        return OS.segment_get(store, sid, _ws(None))

    @app.post("/os/public-base")
    async def os_public_base(request: Request):
        """Set the address every link in your email points at. Refuses a
        host that does not resolve, does not answer, or is not HTTPS."""
        d = await _body(request)
        OS, store, _ = _os()
        out = OS.set_public_base(store, d.get("url"))
        _log_decision(store, "public_base", str(d.get("url"))[:80],
                      out.get("message", ""))
        return out

    @app.post("/os/bounces/read")
    def os_bounces_read():
        """Read the mailbox for bounces. SMTP has no webhook; the mailbox
        is where the failures actually arrive."""
        OS, store, _ = _os()
        out = OS.read_bounces(store, _ws(None))
        _log_decision(store, "os_bounces", str(out.get("hard")),
                      out.get("message", ""))
        return out

    @app.post("/os/bounces/reread")
    def os_bounces_reread():
        """Forget what has been read and read the whole mailbox again.
        Safe to press twice: an event is keyed by the bounce's own date and
        the address it names."""
        OS, store, _ = _os()
        import content_engine_os_bounce as _B
        out = _B.reread(store, OS.repo(store, _ws(None)))
        _log_decision(store, "os_bounces_reread", str(out.get("hard")),
                      out.get("message", ""))
        return out

    @app.post("/os/sheets/push")
    def os_sheets_push():
        OS, store, _ = _os()
        return OS.sheets_push(store, _ws(None))

    @app.post("/os/source/save")
    async def os_source_save(request: Request):
        d = await _body(request)
        OS, store, _ = _os()
        return OS.source_save(store, d.get("name"), d.get("sheet_id"),
                              d.get("tab", "Sheet1"), d.get("every_days", 1))

    @app.post("/os/source/drop")
    async def os_source_drop(request: Request):
        d = await _body(request)
        OS, store, _ = _os()
        return OS.source_drop(store, d.get("sheet_id"), d.get("tab"))

    @app.post("/os/source/run")
    def os_source_run():
        OS, store, _ = _os()
        return OS.source_run(store, _ws(None))

    @app.post("/os/klaviyo/pull")
    async def os_klaviyo_pull(request: Request):
        d = await _body(request)
        OS, store, _ = _os()
        return OS.klaviyo_pull(store, d.get("what") or "profiles", _ws(None))

    @app.post("/os/provider/send-test")
    async def os_provider_send_test(request: Request):
        """One real email through one adapter, to an address you name."""
        d = await _body(request)
        OS, store, _ = _os()
        out = OS.send_test(d.get("name"), d.get("to"))
        _log_decision(store, "provider_send_test", str(d.get("name")),
                      out.get("message", ""))
        return out

    @app.post("/os/upload/image")
    async def os_upload_image(request: Request):
        d = await _body(request)
        OS, store, _ = _os()
        name, data = _uploaded(d)
        if not data:
            return {"ok": False, "message": "that image could not be decoded"}
        return OS.upload_image(store, name, data)

    @app.post("/os/variant/assign")
    async def os_variant_assign(request: Request):
        d = await _body(request)
        import content_engine_os_send as _S
        OS, store, _ = _os()
        return _S.assign_variant(OS.repo(store, _ws(request)),
                                 d.get("campaign_id"), d.get("email"),
                                 d.get("variant"))

    @app.post("/os/variant/promote")
    async def os_variant_promote(request: Request):
        """Make one subject line the only one. Refuses while the arms are
        too small to mean anything."""
        d = await _body(request)
        import content_engine_os_send as _S
        OS, store, _ = _os()
        out = _S.promote_variant(OS.repo(store, _ws(request)),
                                 d.get("campaign_id"), d.get("variant", ""))
        _log_decision(store, "variant_promoted", str(d.get("campaign_id")),
                      out.get("message", ""))
        return out

    @app.post("/os/confirmation/resend")
    async def os_confirmation_resend(request: Request):
        d = await _body(request)
        import content_engine_os_send as _S
        OS, store, _ = _os()
        return _S.resend_confirmation(store, OS.repo(store, _ws(request)),
                                      d.get("email"))

    @app.post("/os/member/password")
    async def os_member_password(request: Request):
        d = await _body(request)
        import content_engine_os_tenancy as _TEN
        _OS, store, _ = _os()
        got = _TEN.require(store, _ws(request), grant="admin")
        if not got["ok"]:
            return {"ok": False, "message": got["message"]}
        if d.get("clear"):
            return _TEN.clear_password(store, got["workspace_id"],
                                       d.get("email"))
        return _TEN.set_password(store, got["workspace_id"], d.get("email"),
                                 d.get("password"))

    @app.post("/os/conversion")
    async def os_conversion(request: Request):
        """Record a booking or a sale against the last email that person
        was sent."""
        d = await _body(request)
        import content_engine_os_analytics as _AN
        OS, store, _ = _os()
        out = _AN.record_conversion(OS.repo(store, _ws(request)),
                                    d.get("email"), value=d.get("value", 0),
                                    currency=d.get("currency", "EUR"),
                                    ref=d.get("ref", ""))
        _log_decision(store, "conversion", str(d.get("email"))[:60],
                      out.get("message", ""))
        return out

    @app.get("/t/v")
    def track_conversion(e: str = "", value: float = 0.0, ref: str = "",
                         currency: str = "EUR"):
        """The conversion beacon. Public, because it is dropped on a thank
        you page that nobody signs into.

        It returns a 1x1 image so it can be an <img> tag on any page,
        including one built in a website editor that cannot run scripts."""
        from fastapi.responses import Response
        import base64 as _b64
        try:
            import content_engine_os as _OS
            import content_engine_os_analytics as _AN
            st = get_store()
            _AN.record_conversion(_OS.repo(st), e, value=value,
                                  currency=currency, ref=ref)
        except Exception as ex:
            log.warning("conversion beacon: %s", ex)
        png = _b64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
        return Response(content=png, media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @app.post("/os/rest")
    async def os_rest(request: Request):
        """Park somebody, or wake them. Deliberately NOT suppression: a
        suppression is a permanent legal record and cannot be undone without
        asking them, and most of these people have simply had enough."""
        d = await _body(request)
        OS, store, _ = _os()
        out = OS.rest_person(store, d.get("email"), int(d.get("days") or 90),
                             bool(d.get("wake")), _ws(request))
        _log_decision(store, "os_rest", str(d.get("email"))[:60],
                      out.get("message", ""))
        return out

    @app.post("/os/audience/clean")
    async def os_audience_clean(request: Request):
        """Rest a whole group from the hygiene table."""
        d = await _body(request)
        OS, store, _ = _os()
        out = OS.clean_audience(store, d.get("kind") or "silent",
                                int(d.get("days") or 90), _ws(request))
        _log_decision(store, "os_clean", str(d.get("kind")),
                      out.get("message", ""))
        return out

    @app.post("/os/rules")
    async def os_rules(request: Request):
        """The sending window and the hourly throttle."""
        d = await _body(request)
        OS, store, _ = _os()
        return OS.save_rules(store, d.get("from_hour"), d.get("to_hour"),
                             d.get("weekdays_only", True), d.get("hourly"))

    @app.post("/os/migrate")
    def os_migrate():
        """Copy the JSON collections into real tables. A copy, never a move."""
        OS, store, _ = _os()
        out = OS.migrate(store, _ws(request=None))
        _log_decision(store, "os_migrate", str(out.get("copied")),
                      out.get("message", ""))
        return out

    @app.get("/os/template/{tid}", response_class=HTMLResponse)
    def os_template(tid: str):
        OS, store, _ = _os()
        return HTMLResponse(OS.template_html(store, tid))

    @app.post("/os/template/render")
    async def os_template_render(request: Request):
        """The builder's live preview, through the sender's own renderer."""
        d = await _body(request)
        OS, _store, _ = _os()
        return OS.render_blocks(d.get("blocks"))

    @app.post("/os/workspace/create")
    async def os_workspace_create(request: Request):
        d = await _body(request)
        import content_engine_os_tenancy as TEN
        _OS, store, _ = _os()
        return TEN.create_workspace(store, d.get("name"))

    @app.post("/os/workspace/switch")
    async def os_workspace_switch(request: Request):
        """Switching is a REQUEST. The guard decides whether it is honoured,
        so a guessed id lands you back in your own workspace rather than in
        somebody else's."""
        d = await _body(request)
        import content_engine_os_tenancy as TEN
        _OS, store, _ = _os()
        got = TEN.require(store, d.get("id"), grant="read")
        r = JSONResponse({"ok": True, "workspace_id": got["workspace_id"],
                          "message": (f"now working in "
                                      f"{got['workspace_id']} as "
                                      f"{got['role']}")})
        r.set_cookie(TEN.WS_COOKIE, got["workspace_id"], httponly=True,
                     samesite="lax")
        return r

    @app.post("/os/member/add")
    async def os_member_add(request: Request):
        d = await _body(request)
        import content_engine_os_tenancy as TEN
        _OS, store, _ = _os()
        got = TEN.require(store, _ws(request), grant="admin")
        if not got["ok"]:
            return {"ok": False, "message": got["message"]}
        return TEN.add_member(store, got["workspace_id"], d.get("email"),
                              d.get("role", "member"))

    @app.post("/os/member/remove")
    async def os_member_remove(request: Request):
        d = await _body(request)
        import content_engine_os_tenancy as TEN
        _OS, store, _ = _os()
        got = TEN.require(store, _ws(request), grant="admin")
        if not got["ok"]:
            return {"ok": False, "message": got["message"]}
        return TEN.remove_member(store, got["workspace_id"], d.get("email"))

    @app.post("/os/provider/test")
    async def os_provider_test(request: Request):
        """Prove a key works. Makes one authenticated call and sends nothing."""
        d = await _body(request)
        OS, store, _ = _os()
        out = OS.test_provider(d.get("name"))
        _log_decision(store, "provider_test", str(d.get("name")),
                      out.get("message", ""))
        return out

    @app.post("/os/provider/webhook")
    async def os_provider_webhook(request: Request):
        d = await _body(request)
        OS, _store, _ = _os()
        return OS.register_webhook(d.get("name"))

    # ---------------------------------------------------------------
    # THE CONSENT PAGES. Public, rate limited, and they never reveal
    # whether an address is already known.
    # ---------------------------------------------------------------
    @app.get("/subscribe", response_class=HTMLResponse)
    def subscribe_form():
        import content_engine_os_optin as OPT
        return HTMLResponse(OPT.signup_page())

    @app.post("/subscribe", response_class=HTMLResponse)
    async def subscribe(request: Request):
        import content_engine_os_optin as OPT
        OS, store, _ = _os()
        if not _os_rate(request, "subscribe"):
            return HTMLResponse(OPT.message_page(
                "One moment", "That was a lot of requests from one place. "
                              "Try again in a minute."), status_code=429)
        d = await _form_or_json(request)
        OS.public(store, "signup", d, ip=_client_ip(request))
        # The SAME page either way: telling a stranger whether an address is
        # already on the list is an address-checking service.
        return HTMLResponse(OPT.message_page(
            "Check your inbox",
            "If that address can receive email, a confirmation is on its way. "
            "Nothing else will be sent until you click the link in it."))

    @app.get("/subscribe/confirm", response_class=HTMLResponse)
    def subscribe_confirm(request: Request, e: str = "", t: str = ""):
        import content_engine_os_optin as OPT
        OS, store, _ = _os()
        out = OS.public(store, "confirm", {"email": e, "t": t},
                        ip=_client_ip(request))
        if not out.get("ok"):
            return HTMLResponse(OPT.message_page(
                "That link did not work", str(out.get("message"))),
                status_code=400)
        return HTMLResponse(OPT.message_page(
            "You are confirmed", "Thank you. You can leave at any time from "
                                 "the bottom of any email."))

    @app.get("/unsubscribe", response_class=HTMLResponse)
    def unsubscribe_form(e: str = "", t: str = ""):
        import content_engine_os_optin as OPT
        return HTMLResponse(OPT.unsubscribe_page(e, t))

    @app.post("/unsubscribe", response_class=HTMLResponse)
    async def unsubscribe(request: Request):
        import content_engine_os_optin as OPT
        OS, store, _ = _os()
        if not _os_rate(request, "unsub"):
            return HTMLResponse(OPT.message_page(
                "One moment", "That was a lot of requests from one place. "
                              "Try again in a minute."), status_code=429)
        d = await _form_or_json(request)
        out = OS.public(store, "unsubscribe", d, ip=_client_ip(request))
        return HTMLResponse(OPT.message_page(
            "Done" if out.get("ok") else "That link did not work",
            str(out.get("message"))))

    # ---------------------------------------------------------------
    # THE AGENT DOOR. Audited, tenant scoped, and it cannot send.
    # ---------------------------------------------------------------
    @app.post("/internal/v1/agent")
    async def internal_agent(request: Request):
        d = await _body(request)
        import content_engine_os_agents as AGT
        _, store, jobs = _os()
        return AGT.call(store, d.get("agent") or "unnamed",
                        d.get("action") or "", d.get("params") or {},
                        jobs=jobs)

    @app.post("/internal/v1/{domain}/{verb}")
    async def internal_domain(domain: str, verb: str, request: Request):
        """REST shaped sugar over the same door: /internal/v1/leads/upsert
        is exactly {"action": "leads.upsert"}. One implementation, so the
        two shapes can never drift apart."""
        d = await _body(request)
        import content_engine_os_agents as AGT
        _, store, jobs = _os()
        return AGT.call(store, d.get("agent") or "unnamed",
                        f"{domain}.{verb}", d.get("params") or d,
                        jobs=jobs)





    @app.post("/social/competitors")
    def social_measure_competitors():
        """Read every tracked rival's public profile."""
        import content_engine_social_insights as SI
        return {"ok": True, **SI.measure_competitors(get_store())}

    @app.post("/social/reply")
    async def social_reply(request: Request):
        """QUEUE a reply. Never sends - that is a separate, explicit click."""
        import content_engine_social_insights as SI
        try:
            d = await request.json()
        except Exception:
            d = {}
        out = SI.draft_reply(get_store(), d.get("comment") or {},
                             d.get("text") or "")
        if out.get("ok"):
            _log_decision(get_store(), "social_reply_queued",
                          str((d.get("comment") or {}).get("who"))[:40],
                          str(d.get("text"))[:100])
        return out

    @app.post("/social/reply/send")
    async def social_reply_send(request: Request):
        """POST one approved reply publicly. Reached only from a click the
        browser has already confirmed, on a draft the founder wrote."""
        import content_engine_social_insights as SI
        try:
            d = await request.json()
        except Exception:
            d = {}
        rid = str(d.get("id") or "")
        if not rid:
            return {"ok": False, "error": "no reply id; nothing sent"}
        out = SI.send_reply(get_store(), rid)
        _log_decision(get_store(), "social_reply_sent", rid,
                      str(out.get("message") or out.get("error"))[:120])
        return out

    @app.post("/social/reply/discard")
    async def social_reply_discard(request: Request):
        import content_engine_social_insights as SI
        try:
            d = await request.json()
        except Exception:
            d = {}
        return SI.discard_reply(get_store(), str(d.get("id") or ""))

    @app.post("/social/competitor")
    async def social_competitor(request: Request):
        """Track or untrack a rival's public profile."""
        import content_engine_social_insights as SI
        try:
            d = await request.json()
        except Exception:
            d = {}
        ch, h = str(d.get("channel") or ""), str(d.get("handle") or "")
        store = get_store()
        if d.get("remove"):
            return SI.untrack_competitor(store, ch, h.lstrip("@"))
        out = SI.track_competitor(store, ch, h)
        if out.get("ok"):
            _log_decision(store, "social_competitor", f"{ch}:{h}",
                          out.get("message", ""))
        return out

    @app.post("/media/auto")
    async def media_auto(request: Request):
        import content_engine_media_orders as MO
        try:
            d = await request.json()
        except Exception:
            d = {}
        out = MO.set_auto(get_store(), d.get("level", ""))
        if out.get("ok"):
            _log_decision(get_store(), "media_auto",
                          f"level {d.get('level')}", out.get("message", ""))
        return out

    @app.post("/media/optimize")
    def media_optimize():
        import content_engine_media_orders as MO
        store = get_store()
        lvl = MO.auto_level(store)
        out = MO.optimize(store, propose=(lvl == "propose"))
        _log_decision(store, "media_optimize", f"at level {lvl}",
                      out.get("message", ""))
        return {"ok": True, **out}

    @app.post("/media/approve")
    async def media_approve(request: Request):
        import content_engine_media_orders as MO
        try:
            d = await request.json()
        except Exception:
            d = {}
        oid = str(d.get("id") or "")
        if not oid:
            return {"ok": False, "message": "no order id given; nothing changed"}
        okd = MO.mark(get_store(), oid, "approved", "approved by founder")
        _log_decision(get_store(), "media_approved", oid[:40], "")
        return {"ok": okd, "message": ("approved - press Execute to run it "
                                       "through the dispatch" if okd else
                                       "no such order")}

    @app.post("/media/run-orders")
    async def media_run_orders(request: Request):
        import content_engine_media_orders as MO
        try:
            d = await request.json()
        except Exception:
            d = {}
        ids = [str(x) for x in (d.get("ids") or []) if x][:50]
        rep = MO.run_media_batch(get_store(), ids=ids or None)
        if rep["attempted"] == 0:
            return {"ok": True, **rep,
                    "message": "nothing approved matched; approve an order "
                               "first - the dispatch only runs approved work"}
        _log_decision(get_store(), "media_ran", f"{rep['attempted']} order(s)",
                      f"done {rep['done']}, held {rep['held']}")
        return {"ok": True, **rep, "message":
                f"{rep['done']} executed, {rep['held']} held with the "
                f"reason written down, {rep['failed']} failed."}

    # ---- THE MEDIA BUYING OS -------------------------------------------
    # Thin routes over the canonical engines. No route here touches a
    # platform, a token or a password: a launch queues an order in the
    # media queue and everything else edits the internal model.
    def _mrepo():
        import content_engine_media_os as _M
        return _M.repo(get_store())

    @app.post("/mediaos/campaign")
    async def mediaos_campaign(request: Request):
        import content_engine_media_os as _M
        d = await _body(request)
        out = _M.save_campaign(
            _mrepo(), name=str(d.get("name") or ""),
            objective=str(d.get("objective") or "LEADS"),
            provider=str(d.get("provider") or ""),
            budget_type=str(d.get("budget_type") or "DAILY"),
            budget_amount=d.get("budget_amount") or 0,
            currency=str(d.get("currency") or "EUR"),
            start_at=str(d.get("start_at") or ""),
            end_at=str(d.get("end_at") or ""),
            provider_config={"kpi": str(d.get("kpi") or "CPA")})
        _log_decision(get_store(), "mediaos_campaign",
                      str(d.get("name"))[:60], out.get("message", ""))
        return out

    @app.post("/mediaos/attach")
    async def mediaos_attach(request: Request):
        """Ad group + ad in one step, the wizard's steps 4 and 5."""
        import content_engine_media_os as _M
        d = await _body(request)
        r = _mrepo()
        cid = str(d.get("campaign_id") or "")
        g = _M.save_ad_group(r, cid, name="Core",
                             audience_id=str(d.get("audience_id") or ""))
        if not g.get("ok"):
            return g
        a = _M.save_ad(r, g["id"], name="Ad 1",
                       creative_id=str(d.get("creative_id") or ""),
                       landing_page_url=str(d.get("landing_page_url") or ""))
        return {"ok": a.get("ok"),
                "message": f"{g.get('message', '')} {a.get('message', '')}"}

    @app.post("/mediaos/audience")
    async def mediaos_audience(request: Request):
        import content_engine_media_creative as _MC
        d = await _body(request)
        return _MC.save_audience(_mrepo(), name=str(d.get("name") or ""),
                                 type=str(d.get("type") or "PROSPECTING"),
                                 definition=d.get("definition") or {})

    @app.post("/mediaos/creative")
    async def mediaos_creative(request: Request):
        import content_engine_media_creative as _MC
        d = await _body(request)
        return _MC.save_creative(
            _mrepo(), name=str(d.get("name") or ""),
            type=str(d.get("type") or "IMAGE"),
            concept=str(d.get("concept") or ""),
            angle=str(d.get("angle") or ""),
            hook=str(d.get("hook") or ""),
            persona=str(d.get("persona") or ""),
            cta=str(d.get("cta") or ""),
            funnel_stage=str(d.get("funnel_stage") or "COLD"),
            headline=str(d.get("headline") or ""),
            primary_text=str(d.get("primary_text") or ""),
            landing_page_url=str(d.get("landing_page_url") or ""),
            publish=bool(d.get("publish")))

    @app.post("/mediaos/validate")
    async def mediaos_validate(request: Request):
        import content_engine_media_os as _M
        d = await _body(request)
        return _M.validate(_mrepo(), str(d.get("campaign_id") or ""))

    @app.post("/mediaos/launch")
    async def mediaos_launch(request: Request):
        import content_engine_media_plan as _MP
        d = await _body(request)
        out = _MP.launch(_mrepo(), str(d.get("campaign_id") or ""),
                         scheduled_at=str(d.get("scheduled_at") or ""))
        _log_decision(get_store(), "mediaos_launch",
                      str(d.get("campaign_id"))[:40],
                      out.get("message", "")[:120])
        return out

    @app.post("/mediaos/plan")
    async def mediaos_plan(request: Request):
        import content_engine_media_plan as _MP
        d = await _body(request)
        return _MP.save_plan(
            _mrepo(), objective=str(d.get("objective") or "LEADS"),
            budget=d.get("budget") or 0,
            kpi=str(d.get("kpi") or "CPA"),
            period_start=str(d.get("period_start") or ""),
            period_end=str(d.get("period_end") or ""),
            target_cpa=d.get("target_cpa") or None,
            target_roas=d.get("target_roas") or None,
            target_leads=d.get("target_leads") or None)

    @app.post("/mediaos/simulate")
    async def mediaos_simulate(request: Request):
        import content_engine_media_plan as _MP
        d = await _body(request)
        return _MP.simulate(_mrepo(), budget=d.get("budget") or 0,
                            compare_to=d.get("compare_to") or None)

    @app.post("/mediaos/scan")
    def mediaos_scan():
        import content_engine_media_perf as _MF
        return _MF.scan(_mrepo(), save=True)

    @app.post("/mediaos/propose")
    def mediaos_propose():
        import content_engine_media_orders as _MO
        import content_engine_media_perf as _MF
        out = _MF.propose(_mrepo(), get_store())
        # the policy pass runs after every propose; with the default policy
        # it approves nothing, and says so
        pol = _MO.apply_policy(get_store())
        out["auto_approved"] = pol.get("auto_approved", 0)
        if pol.get("auto_approved"):
            out["message"] = (out.get("message", "") + " "
                              + pol.get("message", ""))
        _log_decision(get_store(), "mediaos_propose",
                      f"{out.get('proposed')} verdict(s)",
                      out.get("message", "")[:120])
        return out

    @app.post("/mediaos/sync")
    def mediaos_sync():
        import content_engine_media_os as _M
        import content_engine_media_perf as _MF
        r = _mrepo()
        out = _M.sync(r)
        # the aggregation tables refresh with every sync, per the spec
        try:
            rolled = _MF.store_rollups(r)
            out["rollups"] = rolled.get("written")
        except Exception as ex:
            out["rollups"] = f"rollup store failed: {type(ex).__name__}"
        _log_decision(get_store(), "mediaos_sync", "",
                      out.get("message", "")[:120])
        return out

    @app.post("/mediaos/adopt")
    def mediaos_adopt():
        """THE TRANSFORMATION: old Google Ads snapshot -> canonical model.
        Reads settings only; no key, no API call."""
        import content_engine_media_os as _M
        out = _M.adopt(_mrepo(), get_store())
        _log_decision(get_store(), "mediaos_adopt",
                      f"{out.get('adopted')} adopted",
                      out.get("message", "")[:120])
        return out

    @app.post("/mediaos/policy")
    async def mediaos_policy(request: Request):
        import content_engine_media_orders as _MO
        d = await _body(request)
        if not d:
            return {"ok": True, "policy": _MO.get_policy(get_store()),
                    "message": "the current policy; every default is "
                               "approval, nothing is automatic until you "
                               "raise it"}
        out = _MO.set_policy(get_store(), **d)
        if out.get("ok"):
            _log_decision(get_store(), "media_policy",
                          ", ".join(sorted(set(d) & set(_MO.DEFAULT_POLICY))),
                          out.get("message", ""))
        return out

    @app.post("/mediaos/verify")
    def mediaos_verify():
        import content_engine_media_orders as _MO
        return _MO.verify_orders(get_store())

    @app.post("/mediaos/briefs")
    async def mediaos_briefs(request: Request):
        import content_engine_media_creative as _MC
        d = await _body(request)
        return _MC.briefs(_mrepo(), count=int(d.get("count") or 3))

    @app.post("/mediaos/experiment")
    async def mediaos_experiment(request: Request):
        import content_engine_media_creative as _MC
        d = await _body(request)
        return _MC.start_experiment(
            _mrepo(), name=str(d.get("name") or ""),
            creative_ids=d.get("creative_ids") or [],
            metric=str(d.get("metric") or "cpa"),
            hypothesis=str(d.get("hypothesis") or ""))

    @app.post("/mediaos/experiment-judge")
    async def mediaos_experiment_judge(request: Request):
        import content_engine_media_creative as _MC
        d = await _body(request)
        return _MC.judge_experiment(_mrepo(),
                                    str(d.get("experiment_id") or ""))

    @app.post("/mediaos/breakdown")
    async def mediaos_breakdown(request: Request):
        import content_engine_media_perf as _MF
        d = await _body(request)
        return _MF.breakdown(_mrepo(), str(d.get("by") or "device"),
                             campaign_id=str(d.get("campaign_id") or ""))

    @app.post("/mediaos/matrix")
    async def mediaos_matrix(request: Request):
        import content_engine_media_creative as _MC
        d = await _body(request)
        return _MC.matrix(_mrepo(), str(d.get("dimension") or "angle"))

    @app.post("/gtm/audit")
    def gtm_audit_ep():
        import content_engine_gtm as G
        store = get_store()
        ins = store.get_setting("google_insights", {}) or {}
        rep = G.audit(store, insights=ins)
        return {"ok": True, **{k: rep.get(k) for k in
                               ("ready", "at", "missing", "paused",
                                "silent", "steps")},
                "message": (f"audited: {len(rep.get('missing', []))} missing, "
                            f"{len(rep.get('silent', []))} silent"
                            if rep.get("ready") else
                            "Tag Manager is not granted yet; the steps are "
                            "on the Tracking tab")}

    @app.post("/gtm/draft")
    async def gtm_draft_ep(request: Request):
        import content_engine_gtm as G
        try:
            d = await request.json()
        except Exception:
            d = {}
        name = str(d.get("name") or "")
        if not name:
            return {"ok": False, "result": "no tag name given; nothing drafted"}
        out = G.draft_tag(get_store(), name)
        _log_decision(get_store(), "gtm_draft", name[:60],
                      out.get("result", "")[:120])
        return {"ok": out.get("status") == "done", **out}

    @app.post("/gtm/publish")
    def gtm_publish_ep():
        import content_engine_gtm as G
        out = G.publish(get_store())
        _log_decision(get_store(), "gtm_publish", "workspace",
                      out.get("result", "")[:120])
        return {"ok": out.get("status") == "done", **out,
                "message": out.get("result", "")}

    @app.post("/media/draft")
    def media_draft():
        return api_media_draft()

    @app.post("/media/chat")
    async def media_chat(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        return api_media_chat(data.get("job_id"), data.get("message", ""))

    @app.post("/media/activate/{job_id}")
    def media_activate(job_id: str):
        return api_media_activate(job_id)

    @app.post("/media/abort/{job_id}")
    def media_abort(job_id: str):
        return api_media_abort(job_id)

    return app


# Module-level `app` for `uvicorn content_engine_api:app` (guarded so the module
# still imports where fastapi isn't installed).
try:
    app = build_app()
except ImportError:  # fastapi/starlette not installed (core-only offline use)
    app = None
    # Any OTHER build error is intentionally NOT swallowed here: letting it
    # propagate makes uvicorn fail loudly with the real traceback instead of
    # silently serving app=None (which 500s every request).


if __name__ == "__main__":
    # Offline self-check: exercise the core API functions end-to-end with the
    # LLM layer stubbed. No HTTP server, no fastapi needed, no API calls.
    from content_engine_prep import prepare_input

    def stub_llm(job, skill, store):
        canned = {
            "site_intelligence": {"health_score": 90, "top_issues": [], "quick_wins": [],
                                  "content_opportunities": ["x"], "summary": "s"},
            "competitor_intel": {"competitors": [], "market_gap": {"opportunity": "g",
                                 "why_open": "w"}, "differentiation_angles": []},
            "content_strategist": {"week_of": "2026-07-20", "notes": "", "calendar": [{
                "date": "2026-07-21", "type": "blog", "working_title": "T",
                "primary_keyword": "k", "target_segment": "all",
                "business_goal": "awareness", "priority": "high", "rationale": "r"}]},
            "content_producer": {"title": "T", "body": "b", "meta_title": "m",
                                 "meta_description": "d", "cta_text": "c", "hashtags": []},
            "seo_optimizer": {"seo_ready": True, "checks": {}, "fixes": []},
            "qa_compliance": {"verdict": "pass", "brand_voice_match": True, "issues": [],
                              "claims_check": {}, "compliance": {}},
            "analytics_funnel": {"headline": "", "what_worked": [], "what_dropped": [],
                                 "biggest_leak": {}, "recommended_focus_next": ""},
            "optimizer": {"insights": [], "double_down": [{"what": "how-to"}],
                          "reduce_or_cut": [], "next_cycle": {"content_mix": "60% how-to"}},
        }.get(skill, {"ok": True})
        return canned, 0.002
    orch._LLM_HOOK = stub_llm

    # health
    h = api_health()
    assert "healthy" in h and "anthropic" in h

    # skills list
    sk = api_list_skills()
    assert "content_strategist" in sk["skills"]

    # list jobs (empty at first)
    assert api_list_jobs()["jobs"] == []

    # ads optimizer is a tasteable agent
    assert "ads_optimizer" in api_list_skills()["skills"]

    # dashboard renders HTML
    dash = api_dashboard_html()
    assert dash.startswith("<!doctype html>") and "Control Center" in dash

    # create -> tick to gate -> approve -> measure gate -> finish
    r = api_create_job("content_piece", {"brand_name": "Acme"},
                       {"config": {"produce_index": 0}, "audit": {}, "competitors": []},
                       job_id="api_job")
    assert r["status"] == "created"
    for _ in range(20):
        t = api_tick()
        if not t["advanced"]:
            break
    assert api_get_job("api_job")["status"] == "AWAITING_APPROVAL"
    api_approve("api_job")
    for _ in range(5):
        if not api_tick()["advanced"]:
            break
    assert api_get_job("api_job")["status"] == "published"
    # the measurement cron finds it via the list endpoint
    assert any(j["job_id"] == "api_job" for j in api_list_jobs("published")["jobs"])
    api_ready_to_measure("api_job")
    for _ in range(5):
        if not api_tick()["advanced"]:
            break
    assert api_get_job("api_job")["status"] == "optimized"

    # ---- THE RETURN ARROW ------------------------------------------------
    # This assertion used to require that the playbook learned from this cycle.
    # It always passed, and it was encoding the bug: GA4 is not connected in a
    # test environment, so NOTHING was measured, yet the Optimizer's canned
    # content_mix was folded into the playbook anyway. That is exactly how the
    # engine came to hold conclusions drawn from zeros.
    #
    # An unmeasured cycle must now teach the playbook nothing.
    from content_engine_learning import get_playbook
    _j = api_get_job("api_job")
    assert _j.get("unmeasured_reason"), (
        "no GA4 in a test env -> the job MUST carry a stated reason")
    assert _j.get("learned_nothing"), "an unmeasured cycle must teach nothing"
    assert get_playbook("Acme").get("content_mix") != "60% how-to", (
        "the playbook learned from a cycle in which nothing was measured")

    # ...and a MEASURED cycle must still learn. Same pipeline, GA4 answering.
    import content_engine_collect as _COL
    _real = _COL._content_analytics
    _COL._content_analytics = lambda j, st=None: {
        "measured": True, "source": "ga4", "period": "last 21d", "page": "/m",
        "metrics": {"sessions": 500, "conversions": 20, "conv_rate": 4.0,
                    "engagement_rate": 70.0, "top_pages": []},
        "funnel_stages": [], "vs_previous": {}}
    try:
        api_create_job("content_piece", {"brand_name": "Acme"},
                       {"config": {"produce_index": 0}, "audit": {},
                        "competitors": []}, job_id="api_job_m")
        for _ in range(20):
            if not api_tick()["advanced"]:
                break
        api_approve("api_job_m")
        for _ in range(6):
            if not api_tick()["advanced"]:
                break
        api_ready_to_measure("api_job_m")
        for _ in range(6):
            if not api_tick()["advanced"]:
                break
        assert api_get_job("api_job_m")["status"] == "optimized"
        assert not api_get_job("api_job_m").get("learned_nothing"),             "a measured cycle must NOT be marked as having learned nothing"
        assert get_playbook("Acme")["content_mix"] == "60% how-to",             "a MEASURED cycle must still close the learning loop"
    finally:
        _COL._content_analytics = _real

    orch._LLM_HOOK = orch.run_llm_skill
    # The dashboard rendered through the REAL api path must contain the connect
    # form. It did not: build_system_ctx writes connect_html="" and the injector
    # used setdefault, which never overwrites a present-but-empty key. The page
    # looked complete and had ZERO credential fields on it. Assert the thing the
    # user actually needs, not that the page rendered.
    _h = api_dashboard_html()
    import re as _re9
    _fields = _re9.findall(r"<input[^>]*name='([A-Z0-9_]+)'", _h)
    assert len(_fields) >= 80, (
        f"the api dashboard rendered {len(_fields)} credential fields - the "
        f"Connect form is missing from the page people actually load")
    assert "<label for='f-" in _h, "credential fields must carry labels"
    # A "Paste the key" button that lands nowhere is worse than no button: it
    # promises the thing the whole card is about and then drops you. Every jump
    # target must be a field that exists on the same page.
    _targets = set(_re9.findall(r"focusKey\('([A-Z0-9_]+)'", _h))
    _ids = set(_re9.findall(r"id='f-([A-Z0-9_]+)'", _h))
    _lost = sorted(_targets - _ids)
    assert not _lost, f"focusKey points at fields that do not exist: {_lost[:6]}"
    assert len(_targets) >= 5, (
        "unconnected wires must offer a jump straight to their input - "
        f"only {len(_targets)} do")

    print("OK — REST API core verified: health, skills, create/tick/approve/"
          "measure/finish, and the learning loop persisted the playbook. "
          "(LLM stubbed; no server, no API calls.)")
