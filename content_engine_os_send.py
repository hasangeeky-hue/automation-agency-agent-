"""
content_engine_os_send.py
============================================================================
ENGINE 6b AND 7: CAMPAIGNS, THE ORCHESTRATOR, THE QUEUE, CONSENT GATES.

THE ABSOLUTE RULE, WRITTEN WHERE IT IS ENFORCED
    NO AGENT, AND NO REQUEST HANDLER, MAY CALL AN EMAIL PROVIDER.
    Everything goes:
        campaign or flow
          -> resolve the audience
          -> consent check
          -> suppression check
          -> frequency check
          -> sender check
          -> rate limit check
          -> QUEUE
          -> worker
          -> provider adapter
    This module is the ONLY importer of content_engine_os_providers.
    verify_os.py parses every other file's imports and fails the build if
    one of them reaches a provider directly. The rule is a test, not a
    paragraph in a document nobody reads.

WHY THE QUEUE EXISTS AT ALL
  A web request that sends inside the handler has no memory. If it dies at
  recipient 300 of 800 nobody knows which 300, and pressing the button
  again sends 300 people a second copy. The queue makes each recipient a
  row with a state, so a crash is resumable and a duplicate is impossible.

AND NOTHING SENDS WITHOUT A HUMAN
  approve() is a separate act from queue(). The worker only ever picks up
  rows on an approved campaign. That is this founder's standing rule and
  it is enforced here rather than remembered.
============================================================================
"""

from __future__ import annotations

import logging

import content_engine_os_audience as AUD
import content_engine_os_content as CONTENT
import content_engine_os_core as CORE
import content_engine_os_providers as PROV
from content_engine_os_core import (CAMPAIGN_MOVES, CAMPAIGN_STATES, _D, _L,
                                    norm_email, now, rid)

log = logging.getLogger("content_engine.os.send")

#: How many marketing emails one person may receive in a rolling window.
#: A number, not a vibe: three touches over fourteen days is this engine's
#: own sequence, so a fourth inside that window is a mistake by definition.
FREQUENCY_MAX = 3
FREQUENCY_DAYS = 14

#: Every reason a recipient can be refused. The review screen prints these
#: verbatim, so the founder sees WHY 183 people were dropped.
GATE_REASONS = {
    "SUPPRESSED": "on the suppression list",
    "UNSUBSCRIBED": "unsubscribed",
    "INVALID": "not a valid address",
    "FREQUENCY": f"already had {FREQUENCY_MAX} emails in "
                 f"{FREQUENCY_DAYS} days",
    "NO_CONTENT": "no subject or body resolves for this person",
    "RATE_LIMIT": "past today's sending cap",
    "ALREADY_QUEUED": "already queued for this campaign",
}


# ---------------------------------------------------------------------------
# THE CAMPAIGN STATE MACHINE
# ---------------------------------------------------------------------------
def move_campaign(repo, campaign_id, to_state) -> dict:
    """The only way a campaign changes state. An illegal move is refused
    with the moves that ARE legal, so the message teaches instead of just
    blocking."""
    c = repo.one("campaigns", campaign_id)
    if not c:
        return {"ok": False, "error": "no such campaign in this workspace"}
    if to_state not in CAMPAIGN_STATES:
        return {"ok": False, "error": f"{to_state} is not a campaign state"}
    frm = c.get("state") if c.get("state") in CAMPAIGN_STATES else "DRAFT"
    if to_state not in CAMPAIGN_MOVES.get(frm, ()):
        allowed = ", ".join(CAMPAIGN_MOVES.get(frm, ())) or "nothing"
        return {"ok": False,
                "error": f"a {frm} campaign cannot go to {to_state}",
                "message": f"a {frm} campaign can only move to: {allowed}"}
    c["state"] = to_state
    c["state_at"] = now()
    repo.put("campaigns", c)
    CORE.audit(repo, "founder", "campaign_state", campaign_id,
               f"{frm} -> {to_state}")
    return {"ok": True, "state": to_state,
            "message": f"{c.get('name')} is now {to_state.lower()}"}


def save_campaign(repo, *, campaign_id="", name="", audience_kind="all",
                  audience_id="", template_id="", subject="", body="",
                  from_name="", reply_to="", scheduled_at="") -> dict:
    """Create or edit a DRAFT. A campaign past DRAFT is not editable here,
    because changing the content of something already queued means the
    preview no longer describes what sends."""
    cid = campaign_id or rid("camp", repo.ws, name or now())
    cur = repo.one("campaigns", cid) or {"id": cid, "state": "DRAFT"}
    if cur.get("state") not in ("DRAFT", "REVIEW"):
        return {"ok": False,
                "error": f"this campaign is {cur.get('state')}, so its content "
                         f"is fixed; duplicate it to change anything"}
    cur.update({k: v for k, v in {
        "name": name or cur.get("name"), "audience_kind": audience_kind,
        "audience_id": audience_id, "template_id": template_id,
        "subject": subject, "body": body, "from_name": from_name,
        "reply_to": reply_to, "scheduled_at": scheduled_at,
        "source": cur.get("source") or "native"}.items() if v != ""})
    rec = repo.put("campaigns", cur)
    return {"ok": True, "id": rec["id"], "state": rec.get("state"),
            "message": f"{rec.get('name')!r} saved as a draft"}


# ---------------------------------------------------------------------------
# CONTENT RESOLUTION FOR ONE RECIPIENT
# ---------------------------------------------------------------------------
def message_for(repo, campaign, person, touch=1, *, jobs=None) -> dict:
    """What this exact person receives. TWO SOURCES, ONE ANSWER.

    A projected campaign (one of the founder's live outreach jobs) resolves
    through content_engine_os_content.resolve_email, which merges his
    manual edits with the agent's copy and renders the branded HTML. That
    is the engine's own send path, so what shows here is what leaves.

    A native campaign resolves from its template or its own subject and
    body. Either way the caller gets {subject, plain, html}."""
    campaign, person = _D(campaign), _D(person)
    jid = campaign.get("job_id")
    if jid:
        job = next((j for j in _L(jobs)
                    if str(_D(j).get("job_id")) == str(jid)), None)
        if job:
            got = CONTENT.rendered_message(job, person.get("email"), touch)
            if got.get("ok"):
                return got
    tpl = repo.one("templates", campaign.get("template_id") or "") or {}
    subject = campaign.get("subject") or tpl.get("subject") or ""
    html = campaign.get("html") or tpl.get("html") or ""
    body = campaign.get("body") or ""
    if not html and body:
        html = CONTENT.render_blocks([{"type": "text", "content": body}])
    fields = {"first_name": person.get("first_name") or "",
              "last_name": person.get("last_name") or "",
              "name": " ".join(x for x in [person.get("first_name"),
                                           person.get("last_name")] if x),
              "company": person.get("company") or "",
              "job_title": person.get("job_title") or "",
              "city": person.get("city") or "",
              "country": person.get("country") or "",
              "website": person.get("website") or "",
              "industry": person.get("industry") or ""}
    empties = []

    def fill(text):
        def sub(m):
            k = m.group(1)
            v = str(fields.get(k, "")).strip()
            if not v and k in CONTENT.KNOWN_TOKENS:
                empties.append(k)
            return v
        return CONTENT.TOKEN_RE.sub(sub, str(text or ""))

    return {"ok": bool(subject or html or body), "subject": fill(subject),
            "plain": fill(body or CONTENT.e("")), "html": fill(html),
            "body": fill(body), "empty_tokens": sorted(set(empties)),
            "touch": int(touch), "lead": person, "edited": False}


# ---------------------------------------------------------------------------
# THE ORCHESTRATOR
# ---------------------------------------------------------------------------
def _sent_recently(repo, profile_id) -> int:
    cut = CORE.datetime.now(CORE.timezone.utc) - CORE.timedelta(days=FREQUENCY_DAYS)
    n = 0
    for e_ in repo.all("email_events"):
        if e_.get("profile_id") != profile_id or e_.get("event_type") != "EMAIL_SENT":
            continue
        at = CORE.parse_at(e_.get("timestamp"))
        if at and at >= cut:
            n += 1
    return n


def _rate_room() -> tuple:
    """(room_left_or_None, why). Asks the engine's own warm-up limiter
    rather than inventing a second cap that could disagree with it."""
    try:
        import content_engine_connectors as C
        cap = C._warmup_cap()
        used = 0
        try:
            import content_engine_api as A
            used = int(A.get_store().get_setting(C._sent_today_key(), 0) or 0)
        except Exception:
            pass
        return max(0, int(cap) - int(used)), f"{used} of {cap} sent today"
    except Exception:
        return None, "no sending cap is configured"


def plan(repo, campaign_id, *, jobs=None, touch=1) -> dict:
    """Dry run. Who WOULD receive this, who would not, and why, per person.

    This is what the review step of the wizard shows. It runs every gate
    the real send runs, so the number on the review screen is the number
    that leaves, not an estimate."""
    c = repo.one("campaigns", campaign_id)
    if not c:
        return {"ok": False, "error": "no such campaign in this workspace"}
    aud = AUD.resolve_audience(repo, c.get("audience_kind") or "all",
                               c.get("audience_id") or c.get("job_id") or "",
                               c.get("tree"))
    room, cap_why = _rate_room()
    already = {j.get("profile_id") for j in repo.find("email_jobs",
                                                      campaign_id=campaign_id)
               if j.get("status") in ("QUEUED", "PROCESSING")}
    ok_rows, refused = [], []
    for p in aud["eligible"]:
        pid = p.get("id")
        if pid in already:
            refused.append({"email": p.get("email"), "why": "ALREADY_QUEUED"})
            continue
        if _sent_recently(repo, pid) >= FREQUENCY_MAX:
            refused.append({"email": p.get("email"), "why": "FREQUENCY"})
            continue
        msg = message_for(repo, c, p, touch, jobs=jobs)
        if not msg.get("ok") or not (msg.get("subject") or msg.get("html")
                                     or msg.get("plain")):
            refused.append({"email": p.get("email"), "why": "NO_CONTENT"})
            continue
        ok_rows.append({"profile": p, "message": msg})
    for group, why in (("suppressed", "SUPPRESSED"),
                       ("unsubscribed", "UNSUBSCRIBED"),
                       ("invalid_address", "INVALID")):
        for em in aud["dropped_detail"].get(group, []):
            refused.append({"email": em, "why": why})
    over = max(0, len(ok_rows) - room) if room is not None else 0
    sender_ok, sender_why = PROV.sending_allowed(repo)
    return {"ok": True, "campaign": c, "audience": aud["label"],
            "pool": aud["pool"], "deliverable": len(ok_rows),
            "refused": refused,
            "refused_counts": {k: len([r for r in refused if r["why"] == k])
                               for k in GATE_REASONS},
            "reasons": GATE_REASONS, "rate_room": room, "rate_why": cap_why,
            "over_cap": over, "sender_ok": sender_ok, "sender_why": sender_why,
            "rows": ok_rows}


def queue(repo, campaign_id, *, jobs=None, touch=1) -> dict:
    """Write one QUEUED row per eligible recipient. SENDS NOTHING.

    Separated from approve() on purpose: queueing is reversible and
    inspectable, sending is neither."""
    pl = plan(repo, campaign_id, jobs=jobs, touch=touch)
    if not pl.get("ok"):
        return pl
    c = pl["campaign"]
    # SENDING is deliberately allowed: a three touch sequence is mid flight
    # for weeks, and refusing to queue its follow ups would strand everyone
    # who has only had touch one.
    if c.get("state") in ("SENT", "COMPLETED", "CANCELLED"):
        return {"ok": False, "queued": 0, "refused": 0,
                "error": f"this campaign is already {c.get('state').lower()}",
                "message": f"this campaign is {c.get('state').lower()}; "
                           f"duplicate it to send anything more"}
    n = 0
    for row in pl["rows"]:
        p, msg = row["profile"], row["message"]
        mid = rid("msg", repo.ws, campaign_id, p.get("email"), touch)
        repo.put("campaign_messages", {
            "id": mid, "campaign_id": campaign_id, "profile_id": p.get("id"),
            "email": p.get("email"), "touch": int(touch),
            "subject": msg.get("subject", ""), "state": "QUEUED",
            "job_id": c.get("job_id", ""), "edited": bool(msg.get("edited"))})
        repo.put("email_jobs", {
            "id": rid("ej", repo.ws, campaign_id, p.get("email"), touch),
            "campaign_id": campaign_id, "profile_id": p.get("id"),
            "message_id": mid, "email": p.get("email"), "status": "QUEUED",
            "provider": PROV.get_provider().name, "attempts": 0,
            "scheduled_at": c.get("scheduled_at") or now(),
            "approved": False, "touch": int(touch)})
        CORE.record_event(repo, "EMAIL_QUEUED", profile_id=p.get("id"),
                          campaign_id=campaign_id, message_id=mid)
        n += 1
    if c.get("state") in ("DRAFT", "REVIEW", "SCHEDULED"):
        move_campaign(repo, campaign_id,
                      "REVIEW" if c.get("state") == "DRAFT" else "QUEUED")
        if repo.one("campaigns", campaign_id).get("state") == "REVIEW":
            move_campaign(repo, campaign_id, "QUEUED")
    CORE.audit(repo, "founder", "campaign_queued", campaign_id, f"{n} queued")
    return {"ok": True, "queued": n, "refused": len(pl["refused"]),
            "message": (f"{n} recipient(s) queued. Nothing has been sent: "
                        f"press Approve to release them."
                        if n else
                        "nothing was queued; every recipient was refused by a "
                        "gate, and the review screen says which")}


def queue_for_person(repo, campaign_id, profile_id, *, touch=1, jobs=None,
                     flow_id="") -> dict:
    """Queue ONE recipient. This is the door a flow knocks on.

    Every gate the bulk path runs, run for one person. A flow that could
    reach the queue by a shorter route would be a second, weaker set of
    rules, and the whole point of the orchestrator is that there is only
    one."""
    c = repo.one("campaigns", campaign_id)
    if not c:
        return {"ok": False, "message": "that step points at a campaign that "
                                        "does not exist"}
    person = next((p for p in AUD.people(repo) if p.get("id") == profile_id),
                  None)
    if not person:
        return {"ok": False, "message": "that person is not in this workspace"}
    em = norm_email(person.get("email"))
    if not CORE.valid_email(em):
        return {"ok": False, "message": GATE_REASONS["INVALID"]}
    if em in CORE.suppression_index(repo):
        return {"ok": False, "message": GATE_REASONS["SUPPRESSED"]}
    if person.get("consent") == "UNSUBSCRIBED":
        return {"ok": False, "message": GATE_REASONS["UNSUBSCRIBED"]}
    if _sent_recently(repo, profile_id) >= FREQUENCY_MAX:
        return {"ok": False, "message": GATE_REASONS["FREQUENCY"]}
    ejid = rid("ej", repo.ws, campaign_id, em, touch)
    existing = repo.one("email_jobs", ejid)
    if existing and existing.get("status") in ("QUEUED", "PROCESSING", "SENT"):
        return {"ok": False, "message": GATE_REASONS["ALREADY_QUEUED"]}
    msg = message_for(repo, c, person, touch, jobs=jobs)
    if not msg.get("ok"):
        return {"ok": False, "message": GATE_REASONS["NO_CONTENT"]}
    mid = rid("msg", repo.ws, campaign_id, em, touch)
    repo.put("campaign_messages", {
        "id": mid, "campaign_id": campaign_id, "profile_id": profile_id,
        "email": em, "touch": int(touch), "subject": msg.get("subject", ""),
        "state": "QUEUED", "flow_id": flow_id, "job_id": c.get("job_id", "")})
    repo.put("email_jobs", {
        "id": ejid, "campaign_id": campaign_id, "profile_id": profile_id,
        "message_id": mid, "email": em, "status": "QUEUED", "attempts": 0,
        "provider": PROV.get_provider().name, "flow_execution_id": flow_id,
        "scheduled_at": now(), "approved": False, "touch": int(touch)})
    CORE.record_event(repo, "EMAIL_QUEUED", profile_id=profile_id,
                      campaign_id=campaign_id, flow_id=flow_id,
                      message_id=mid)
    return {"ok": True, "message": f"{em} queued for your approval"}


def approve(repo, campaign_id, actor="founder") -> dict:
    """The human act. Until this runs, the worker will not touch a row."""
    rows = [j for j in repo.find("email_jobs", campaign_id=campaign_id)
            if j.get("status") == "QUEUED"]
    if not rows:
        return {"ok": False,
                "message": "there is nothing queued on this campaign to "
                           "approve"}
    for j in rows:
        j["approved"] = True
        j["approved_by"] = actor
        j["approved_at"] = now()
        repo.put("email_jobs", j)
    CORE.audit(repo, actor, "campaign_approved", campaign_id,
               f"{len(rows)} recipients")
    return {"ok": True, "approved": len(rows),
            "message": f"{len(rows)} recipient(s) approved. The worker sends "
                       f"them on its next pass."}


def cancel(repo, campaign_id) -> dict:
    n = 0
    for j in repo.find("email_jobs", campaign_id=campaign_id):
        if j.get("status") in ("QUEUED", "PROCESSING"):
            j["status"] = "CANCELLED"
            repo.put("email_jobs", j)
            n += 1
    move_campaign(repo, campaign_id, "CANCELLED")
    return {"ok": True, "cancelled": n,
            "message": f"{n} queued email(s) cancelled before sending"}


# ---------------------------------------------------------------------------
# THE WORKER. The only place a provider is called.
# ---------------------------------------------------------------------------
def work_queue(repo, *, jobs=None, limit=50, provider_name=None) -> dict:
    """Send approved, queued rows. Re-checks every gate at send time.

    Re-checking is not paranoia: a person can unsubscribe between the queue
    write and the worker pass, and honouring that is the difference between
    a compliance story and an incident."""
    prov = PROV.get_provider(provider_name)
    ok_prov, why = prov.available()
    if not ok_prov:
        return {"ok": False, "sent": 0, "message": why}
    supp = CORE.suppression_index(repo)
    profs = {p.get("id"): p for p in repo.all("profiles")}
    room, _ = _rate_room()
    sent = held = failed = 0
    rows = [j for j in repo.all("email_jobs")
            if j.get("status") == "QUEUED" and j.get("approved")]
    for j in rows[:limit]:
        if room is not None and sent >= room:
            held += 1
            continue
        em = norm_email(j.get("email"))
        p = profs.get(j.get("profile_id")) or {}
        if em in supp or p.get("consent") == "UNSUBSCRIBED":
            j["status"] = "SUPPRESSED"
            j["error_message"] = GATE_REASONS["SUPPRESSED"]
            repo.put("email_jobs", j)
            held += 1
            continue
        c = repo.one("campaigns", j.get("campaign_id")) or {}
        person = next((x for x in AUD.people(repo)
                       if x.get("id") == j.get("profile_id")), p)
        msg = message_for(repo, c, person, j.get("touch") or 1, jobs=jobs)
        if not msg.get("ok"):
            j["status"] = "FAILED"
            j["error_message"] = GATE_REASONS["NO_CONTENT"]
            repo.put("email_jobs", j)
            failed += 1
            continue
        j["status"] = "PROCESSING"
        j["attempts"] = int(j.get("attempts") or 0) + 1
        repo.put("email_jobs", j)
        res = prov.send(em, msg.get("subject", ""), msg.get("plain", ""),
                        msg.get("html", ""))
        if res.get("ok"):
            j.update({"status": "SENT", "sent_at": now(),
                      "provider_message_id": res.get("provider_message_id", ""),
                      "error_message": ""})
            CORE.record_event(repo, "EMAIL_SENT", profile_id=j.get("profile_id"),
                              campaign_id=j.get("campaign_id"),
                              message_id=j.get("message_id"))
            m = repo.one("campaign_messages", j.get("message_id"))
            if m:
                m.update({"state": "SENT", "sent_at": now(),
                          "subject": msg.get("subject", "")})
                repo.put("campaign_messages", m)
            sent += 1
        else:
            j.update({"status": "FAILED", "failed_at": now(),
                      "error_message": str(res.get("error"))[:300]})
            failed += 1
        repo.put("email_jobs", j)
    for cid in {j.get("campaign_id") for j in rows}:
        left = [j for j in repo.find("email_jobs", campaign_id=cid)
                if j.get("status") in ("QUEUED", "PROCESSING")]
        c = repo.one("campaigns", cid) or {}
        if not left and c.get("state") in ("QUEUED", "SENDING"):
            move_campaign(repo, cid, "SENDING" if c.get("state") == "QUEUED"
                          else "SENT")
    return {"ok": True, "sent": sent, "held": held, "failed": failed,
            "message": f"{sent} sent, {held} held, {failed} failed"}


def queue_rows(repo) -> list:
    """The queue, as the screen draws it."""
    camps = {c.get("id"): c.get("name") for c in repo.all("campaigns")}
    out = []
    for j in repo.all("email_jobs"):
        out.append({"id": j.get("id"), "email": j.get("email"),
                    "campaign": camps.get(j.get("campaign_id"), ""),
                    "campaign_id": j.get("campaign_id"),
                    "status": j.get("status"), "approved": bool(j.get("approved")),
                    "attempts": j.get("attempts", 0),
                    "provider": j.get("provider", ""),
                    "scheduled_at": j.get("scheduled_at", ""),
                    "sent_at": j.get("sent_at", ""),
                    "error": j.get("error_message", "")})
    return sorted(out, key=lambda r: str(r.get("scheduled_at")), reverse=True)


def queue_counts(repo) -> dict:
    rows = repo.all("email_jobs")
    return {s: len([j for j in rows if j.get("status") == s])
            for s in CORE.JOB_STATES}


# ---------------------------------------------------------------------------
# WEBHOOKS
# ---------------------------------------------------------------------------
def ingest_webhook(repo, payload, provider_name=None) -> dict:
    """Provider callback to engine events. Idempotent by construction: the
    event key is derived from its content, so a redelivered webhook writes
    nothing the second time."""
    prov = PROV.get_provider(provider_name)
    rows = prov.handle_webhook(payload)
    by_email = {p.get("email"): p.get("id") for p in repo.all("profiles")}
    by_msg = {j.get("provider_message_id"): j for j in repo.all("email_jobs")
              if j.get("provider_message_id")}
    n = 0
    for r in rows:
        pid = by_email.get(r.get("email"), "")
        j = by_msg.get(r.get("provider_message_id")) or {}
        if CORE.record_event(repo, r["event_type"], profile_id=pid,
                             campaign_id=j.get("campaign_id", ""),
                             message_id=j.get("message_id", ""),
                             at=r.get("at"), metadata=r.get("metadata")):
            n += 1
        if r["event_type"] == "EMAIL_BOUNCED" and r.get("email"):
            CORE.suppress(repo, r["email"], "BOUNCE", "hard bounce reported")
        if r["event_type"] == "EMAIL_SPAM_COMPLAINT" and r.get("email"):
            CORE.suppress(repo, r["email"], "SPAM_COMPLAINT", "reported by ESP")
        if r["event_type"] == "EMAIL_UNSUBSCRIBED" and r.get("email"):
            CORE.set_consent(repo, r["email"], "UNSUBSCRIBED",
                             source="esp webhook", method="link")
    return {"ok": True, "recorded": n, "seen": len(rows),
            "message": f"{n} new event(s) from {len(rows)} reported"}
