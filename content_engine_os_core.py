"""
content_engine_os_core.py
============================================================================
THE EMAIL & LEAD ENGAGEMENT OS: TENANCY, DOMAIN MODEL, VOCABULARY.

This is engine 1 and engine 2 of the master specification, plus the single
vocabulary every other OS module imports. Nothing in this file sends,
renders or fetches.

WHY EVERY CONSTANT LIVES HERE
  Five outages in this engine came from two hand-written word lists that
  disagreed: one module wrote a value, another gated on a value, and nobody
  owned the pair. Campaign states, job states, event types, consent states,
  suppression reasons, segment operators and node types are declared once,
  here, and imported everywhere. verify_os.py fails the build if a second
  module declares its own copy.

TENANCY IS ENFORCED IN THE BACKEND, NEVER TRUSTED FROM THE FRONTEND
  Repo(store, workspace_id) is the only way into storage. It stamps
  workspace_id on write and filters on read. A record belonging to another
  workspace is invisible to get(), all() and delete(), so a guessed id
  returns nothing rather than someone else's data.

THE PROJECTION IS WHY THIS IS NOT A DUMMY SHOW
  The founder already has real campaigns, leads, sends, opens and clicks
  living in job payloads. project() reads them and produces Profiles,
  Leads, Campaigns, Messages, Email jobs and Events. The OS therefore
  opens full of his own data on the first render, with nothing to migrate.
============================================================================
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

log = logging.getLogger("content_engine.os")

# ---------------------------------------------------------------------------
# THE VOCABULARY. One definition each. Imported, never re-typed.
# ---------------------------------------------------------------------------
DEFAULT_WORKSPACE = "ws_anthropos"

#: Campaign lifecycle. A campaign may only move along CAMPAIGN_MOVES.
CAMPAIGN_STATES = ("DRAFT", "REVIEW", "SCHEDULED", "QUEUED", "SENDING",
                   "SENT", "COMPLETED", "CANCELLED", "FAILED")

#: The legal transitions. Anything not listed is refused by move_campaign().
CAMPAIGN_MOVES = {
    "DRAFT": ("REVIEW", "CANCELLED"),
    "REVIEW": ("DRAFT", "SCHEDULED", "QUEUED", "CANCELLED"),
    "SCHEDULED": ("QUEUED", "DRAFT", "CANCELLED"),
    "QUEUED": ("SENDING", "CANCELLED", "FAILED"),
    "SENDING": ("SENT", "FAILED", "CANCELLED"),
    "SENT": ("COMPLETED", "FAILED"),
    "COMPLETED": (),
    "CANCELLED": (),
    "FAILED": ("DRAFT",),
}

#: One queued email, per recipient.
JOB_STATES = ("QUEUED", "PROCESSING", "SENT", "DELIVERED", "BOUNCED",
              "FAILED", "CANCELLED", "SUPPRESSED")

#: Immutable facts. Never edited, only appended.
EVENT_TYPES = ("EMAIL_QUEUED", "EMAIL_SENT", "EMAIL_DELIVERED",
               "EMAIL_BOUNCED", "EMAIL_OPENED", "EMAIL_CLICKED",
               "EMAIL_UNSUBSCRIBED", "EMAIL_SPAM_COMPLAINT",
               "EMAIL_CONVERTED")

#: Marketing consent. SUPPRESSED is a state a person is put INTO by a
#: suppression record; it is not something they choose.
CONSENT_STATES = ("SUBSCRIBED", "PENDING", "UNSUBSCRIBED", "SUPPRESSED",
                  "NEVER_SUBSCRIBED")

SUPPRESSION_REASONS = ("UNSUBSCRIBE", "BOUNCE", "SPAM_COMPLAINT", "MANUAL",
                       "COMPLIANCE")

#: Flow graph. Stored as nodes plus edges, never as an ordered list, because
#: an ordered list cannot branch and this engine's sequences branch on open.
NODE_TYPES = ("TRIGGER", "SEND_EMAIL", "WAIT", "CONDITION", "SPLIT",
              "UPDATE_PROFILE", "ADD_TO_LIST", "REMOVE_FROM_LIST",
              "WEBHOOK", "AI_ACTION", "GOAL", "END")

#: Sender domain lifecycle. Production marketing sending requires VERIFIED.
DOMAIN_STATES = ("PENDING", "VERIFYING", "VERIFIED", "FAILED", "SUSPENDED")

#: Every comparison a segment may make. See content_engine_os_audience.
SEGMENT_OPS = ("equals", "not_equals", "contains", "not_contains",
               "greater_than", "less_than", "greater_or_equal",
               "less_or_equal", "exists", "not_exists", "in", "not_in",
               "before", "after")

#: Lead lifecycle, which is deliberately NOT the same thing as consent.
LEAD_STAGES = ("NEW", "ENRICHED", "QUALIFIED", "CONTACTED", "ENGAGED",
               "INTERESTED", "MEETING", "OPPORTUNITY", "CUSTOMER", "LOST")

#: Who may do what. One list, imported by the tenancy module and by the
#: route guard, so a role that grants nothing cannot be invented in a form.
ROLES = ("owner", "admin", "member", "viewer")

#: role -> what it may do. "write" covers creating and editing; "send"
#: covers approving a queue; "admin" covers members, domains and providers.
ROLE_GRANTS = {
    "owner":  ("read", "write", "send", "admin"),
    "admin":  ("read", "write", "send", "admin"),
    "member": ("read", "write"),
    "viewer": ("read",),
}

#: Every collection the OS persists. Repo refuses an unknown name so a typo
#: cannot silently create a second, invisible store.
COLLECTIONS = (
    "workspaces", "users", "workspace_members",
    "profiles", "profile_properties", "companies", "leads",
    "lists", "list_members", "segments",
    "templates", "template_versions",
    "campaigns", "campaign_messages",
    "flows", "flow_executions",
    "email_jobs", "email_events",
    "consents", "suppressions",
    "sender_domains", "providers",
    "agent_runs", "agent_actions", "audit_logs", "daily_metrics",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, list) else []


def norm_email(v) -> str:
    return str(v or "").strip().lower()


def valid_email(v) -> bool:
    return bool(_EMAIL_RE.match(norm_email(v)))


def rate(n, d):
    """(percent, "N of D"). Every rate in this OS carries its denominator,
    because a percentage with no population behind it is a rumour.

    A rate over nothing is (None, "nothing sent yet"), never 0%: zero
    percent of zero is a statement about a population that does not exist.
    """
    try:
        n, d = float(n or 0), float(d or 0)
    except Exception:
        return None, ""
    if d <= 0:
        return None, "nothing to measure yet"
    return round(n / d * 100, 1), f"{int(n):,} of {int(d):,}"


def rid(prefix: str, *parts) -> str:
    """A stable id. Stable matters: the projection reruns on every render,
    and a record that changed id each time would break every link on the
    page and duplicate every event."""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8", "ignore"))
    return f"{prefix}_{h.hexdigest()[:16]}"


def parse_at(v):
    """A timestamp from anywhere in this engine, as an aware datetime."""
    s = str(v or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def days_ago(v):
    d = parse_at(v)
    if not d:
        return None
    return max(0, int((datetime.now(timezone.utc) - d).total_seconds() // 86400))


# ---------------------------------------------------------------------------
# THE REPOSITORY. The only door to storage.
# ---------------------------------------------------------------------------
class Repo:
    """Tenant-scoped storage over the engine's settings store.

    Records live under "os:{collection}" as a list of dicts, each carrying
    workspace_id. Reads filter by workspace, writes stamp it. There is no
    method that accepts a workspace_id from the caller after construction,
    which is what makes frontend-supplied tenancy impossible rather than
    merely discouraged.
    """

    def __init__(self, store, workspace_id: str = DEFAULT_WORKSPACE):
        self.store = store
        self.ws = str(workspace_id or DEFAULT_WORKSPACE)

    # -- raw settings access ------------------------------------------------
    def _key(self, coll: str) -> str:
        if coll not in COLLECTIONS:
            raise KeyError(f"unknown collection: {coll}")
        return f"os:{coll}"

    def _read(self, coll: str) -> list:
        # _key() is called OUTSIDE the guard on purpose: an unknown
        # collection is a typo in this codebase, and swallowing it would
        # create a second, invisible store that always reads empty.
        key = self._key(coll)
        try:
            v = self.store.get_setting(key, [])
        except Exception as ex:
            log.warning("os read %s failed: %s", coll, ex)
            return []
        return v if isinstance(v, list) else []

    def _write(self, coll: str, rows: list) -> None:
        try:
            self.store.set_setting(self._key(coll), rows)
        except Exception as ex:
            log.error("os write %s failed: %s", coll, ex)

    # -- scoped api ---------------------------------------------------------
    def all(self, coll: str) -> list:
        return [r for r in self._read(coll)
                if isinstance(r, dict) and r.get("workspace_id") == self.ws]

    def find(self, coll: str, **where) -> list:
        out = self.all(coll)
        for k, v in where.items():
            out = [r for r in out if r.get(k) == v]
        return out

    def one(self, coll: str, rec_id: str):
        for r in self.all(coll):
            if r.get("id") == rec_id:
                return r
        return None

    def put(self, coll: str, rec: dict) -> dict:
        """Insert or replace by id, always inside this workspace.

        A record whose id exists in ANOTHER workspace is treated as absent,
        so a guessed id creates a new record here instead of overwriting
        someone else's."""
        rec = dict(_D(rec))
        rec["workspace_id"] = self.ws
        rec.setdefault("id", rid(coll[:3], self.ws, coll, now()))
        rec.setdefault("created_at", now())
        rec["updated_at"] = now()
        rows = self._read(coll)
        for i, r in enumerate(rows):
            if (isinstance(r, dict) and r.get("id") == rec["id"]
                    and r.get("workspace_id") == self.ws):
                rows[i] = rec
                self._write(coll, rows)
                return rec
        rows.append(rec)
        self._write(coll, rows[-20000:])
        return rec

    def delete(self, coll: str, rec_id: str) -> bool:
        rows = self._read(coll)
        keep = [r for r in rows
                if not (isinstance(r, dict) and r.get("id") == rec_id
                        and r.get("workspace_id") == self.ws)]
        if len(keep) == len(rows):
            return False
        self._write(coll, keep)
        return True

    def append(self, coll: str, rec: dict) -> dict:
        """Append-only write for immutable collections (events, audit).

        No id lookup, no replace: an event that can be rewritten is not a
        record of what happened."""
        rec = dict(_D(rec))
        rec["workspace_id"] = self.ws
        rec.setdefault("id", rid("ev", self.ws, coll, now(), len(self._read(coll))))
        rec.setdefault("created_at", now())
        rows = self._read(coll)
        rows.append(rec)
        self._write(coll, rows[-50000:])
        return rec


# ---------------------------------------------------------------------------
# PROFILES, COMPANIES, LEADS
# ---------------------------------------------------------------------------
PROFILE_FIELDS = ("email", "phone", "first_name", "last_name", "company_id",
                  "company", "job_title", "website", "linkedin_url",
                  "country", "city", "timezone", "language", "source",
                  "source_id", "last_activity_at")


def split_name(full) -> tuple:
    parts = [p for p in str(full or "").replace(",", " ").split() if p]
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def upsert_profile(repo: Repo, data: dict) -> dict:
    """One person, keyed on email. Custom properties go to their own
    collection so an agent adding "pain_point" never needs a schema change."""
    data = _D(data)
    em = norm_email(data.get("email"))
    if not em:
        return {}
    pid = rid("prf", repo.ws, em)
    cur = repo.one("profiles", pid) or {"id": pid}
    rec = dict(cur)
    for f in PROFILE_FIELDS:
        v = data.get(f)
        if v not in (None, "", []):
            rec[f] = v
    rec["email"] = em
    if not rec.get("first_name") and data.get("name"):
        rec["first_name"], rec["last_name"] = split_name(data.get("name"))
    if not rec.get("consent"):
        # A consent record can exist BEFORE the profile does: somebody fills
        # in the signup form, the address is recorded as PENDING, and only
        # then is a profile written. Defaulting to NEVER_SUBSCRIBED here
        # would silently overwrite a real permission with an absence.
        rec["consent"] = (consent_index(repo).get(rec["email"])
                          or "NEVER_SUBSCRIBED")
    out = repo.put("profiles", rec)
    props = _D(data.get("properties"))
    for k, v in props.items():
        set_property(repo, pid, k, v)
    return out


def set_property(repo: Repo, profile_id: str, key: str, value) -> dict:
    """A custom property. Typed on write so a segment can compare it
    numerically without guessing later."""
    kind = ("number" if isinstance(value, (int, float))
            and not isinstance(value, bool)
            else "boolean" if isinstance(value, bool)
            else "list" if isinstance(value, list) else "string")
    return repo.put("profile_properties", {
        "id": rid("pp", repo.ws, profile_id, key),
        "profile_id": profile_id, "key": str(key),
        "value": value, "value_type": kind})


def properties_of(repo: Repo, profile_id: str) -> dict:
    return {r.get("key"): r.get("value")
            for r in repo.find("profile_properties", profile_id=profile_id)}


def upsert_company(repo: Repo, name, **kw) -> dict:
    nm = str(name or "").strip()
    if not nm:
        return {}
    cid = rid("cmp", repo.ws, nm.lower())
    cur = repo.one("companies", cid) or {"id": cid, "name": nm}
    cur.update({k: v for k, v in kw.items() if v not in (None, "", [])})
    return repo.put("companies", cur)


def upsert_lead(repo: Repo, profile_id, **kw) -> dict:
    """A LEAD IS NOT A PROFILE. A profile is the person; a lead is the
    acquisition opportunity around them. One company can produce several
    leads over time and one lead can involve several people, which is why
    they are separate rows rather than columns on one another."""
    lid = rid("lead", repo.ws, profile_id)
    cur = repo.one("leads", lid) or {"id": lid, "primary_profile_id": profile_id,
                                     "stage": "NEW", "score": None}
    cur.update({k: v for k, v in kw.items() if v not in (None, "")})
    if cur.get("stage") not in LEAD_STAGES:
        cur["stage"] = "NEW"
    return repo.put("leads", cur)


# ---------------------------------------------------------------------------
# CONSENT AND SUPPRESSION
# ---------------------------------------------------------------------------
def set_consent(repo: Repo, email, status, *, source="", method="",
                evidence="") -> dict:
    """Consent with its provenance. "SUBSCRIBED" with no record of where and
    how is not a defence, it is a claim."""
    em = norm_email(email)
    if status not in CONSENT_STATES:
        return {"ok": False, "error": f"unknown consent state: {status}"}
    repo.put("consents", {
        "id": rid("cons", repo.ws, em), "email": em, "status": status,
        "consent_source": source, "consent_method": method,
        "evidence": evidence, "consent_at": now(),
        "unsubscribed_at": now() if status == "UNSUBSCRIBED" else ""})
    prof = repo.one("profiles", rid("prf", repo.ws, em))
    if prof:
        prof["consent"] = status
        repo.put("profiles", prof)
    return {"ok": True, "email": em, "status": status}


def suppress(repo: Repo, email, reason, note="") -> dict:
    """A suppression OVERRIDES eligibility. It is checked before consent,
    because a hard bounce does not become deliverable by resubscribing."""
    em = norm_email(email)
    if reason not in SUPPRESSION_REASONS:
        return {"ok": False, "error": f"unknown suppression reason: {reason}"}
    repo.put("suppressions", {
        "id": rid("sup", repo.ws, em), "email": em, "reason": reason,
        "note": note, "suppressed_at": now()})
    prof = repo.one("profiles", rid("prf", repo.ws, em))
    if prof:
        prof["consent"] = "SUPPRESSED"
        repo.put("profiles", prof)
    return {"ok": True, "email": em, "reason": reason}


def suppression_index(repo: Repo) -> dict:
    return {norm_email(r.get("email")): r for r in repo.all("suppressions")}


def consent_index(repo: Repo) -> dict:
    return {norm_email(r.get("email")): r.get("status") for r in repo.all("consents")}


# ---------------------------------------------------------------------------
# EVENTS. Immutable and idempotent.
# ---------------------------------------------------------------------------
def event_key(kind, profile_id, campaign_id, message_id, at, extra="") -> str:
    return rid("evk", kind, profile_id or "", campaign_id or "",
               message_id or "", str(at or "")[:19], str(extra))


def record_event(repo: Repo, kind, *, profile_id="", campaign_id="",
                 flow_id="", message_id="", at=None, metadata=None,
                 _index=None) -> dict:
    """Append one fact. Idempotent on (kind, who, which message, when):
    a webhook delivered twice must not double a click, and the projection
    reruns on every page render."""
    if kind not in EVENT_TYPES:
        return {}
    at = at or now()
    key = event_key(kind, profile_id, campaign_id, message_id, at,
                    _D(metadata).get("url", ""))
    seen = _index if _index is not None else {
        r.get("event_key") for r in repo.all("email_events")}
    if key in seen:
        return {}
    if _index is not None:
        _index.add(key)
    return repo.append("email_events", {
        "id": key, "event_key": key, "event_type": kind,
        "profile_id": profile_id, "campaign_id": campaign_id,
        "flow_id": flow_id, "message_id": message_id,
        "timestamp": at, "metadata": _D(metadata)})


def events_for(repo: Repo, *, profile_id=None, campaign_id=None) -> list:
    out = repo.all("email_events")
    if profile_id:
        out = [e for e in out if e.get("profile_id") == profile_id]
    if campaign_id:
        out = [e for e in out if e.get("campaign_id") == campaign_id]
    return sorted(out, key=lambda e: str(e.get("timestamp") or ""))


# ---------------------------------------------------------------------------
# AUDIT. Every agent action, recorded.
# ---------------------------------------------------------------------------
def start_run(repo: Repo, agent_type, task) -> dict:
    return repo.put("agent_runs", {
        "id": rid("run", repo.ws, agent_type, task, now()),
        "agent_type": agent_type, "task": task, "status": "RUNNING",
        "started_at": now(), "completed_at": "", "token_usage": 0,
        "cost": 0.0, "output": ""})


def finish_run(repo: Repo, run_id, status="OK", output="", cost=0.0,
               tokens=0) -> dict:
    r = repo.one("agent_runs", run_id)
    if not r:
        return {}
    r.update({"status": status, "completed_at": now(), "output": str(output)[:2000],
              "cost": float(cost or 0), "token_usage": int(tokens or 0)})
    return repo.put("agent_runs", r)


def log_action(repo: Repo, run_id, action_type, target_type="", target_id="",
               inp=None, outp=None) -> dict:
    return repo.append("agent_actions", {
        "agent_run_id": run_id, "action_type": action_type,
        "target_type": target_type, "target_id": target_id,
        "input": inp if isinstance(inp, (dict, list, str)) else str(inp),
        "output": outp if isinstance(outp, (dict, list, str)) else str(outp),
        "timestamp": now()})


def audit(repo: Repo, actor, action, target="", detail="") -> dict:
    return repo.append("audit_logs", {
        "actor": actor, "action": action, "target": target,
        "detail": str(detail)[:800], "at": now()})


# ---------------------------------------------------------------------------
# THE TIMELINE
# ---------------------------------------------------------------------------
_EVENT_WORDS = {
    "EMAIL_QUEUED": "Queued to send",
    "EMAIL_SENT": "Email sent",
    "EMAIL_DELIVERED": "Delivered",
    "EMAIL_BOUNCED": "Bounced",
    "EMAIL_OPENED": "Email opened",
    "EMAIL_CLICKED": "Link clicked",
    "EMAIL_UNSUBSCRIBED": "Unsubscribed",
    "EMAIL_SPAM_COMPLAINT": "Marked as spam",
    "EMAIL_CONVERTED": "Converted",
}


def timeline(repo: Repo, profile_id: str) -> list:
    """Everything that happened to one person, in order: how they were
    found, what the agents learned, what left, what came back."""
    prof = repo.one("profiles", profile_id) or {}
    rows = []
    if prof.get("created_at"):
        rows.append({"at": prof["created_at"], "kind": "discovered",
                     "what": "Lead discovered",
                     "detail": prof.get("source") or "source not recorded"})
    lead = repo.one("leads", rid("lead", repo.ws, profile_id))
    if lead and lead.get("score") is not None:
        rows.append({"at": lead.get("updated_at") or lead.get("created_at", ""),
                     "kind": "enriched", "what": "Qualified by the agent",
                     "detail": f"score {lead.get('score')}, "
                               f"stage {lead.get('stage')}"})
    for m in repo.find("campaign_messages", profile_id=profile_id):
        if m.get("sent_at"):
            rows.append({"at": m["sent_at"], "kind": "sent",
                         "what": f"Email {m.get('touch') or 1} sent",
                         "detail": m.get("subject") or "(no subject recorded)",
                         "message_id": m.get("id"),
                         "campaign_id": m.get("campaign_id")})
    for ev in events_for(repo, profile_id=profile_id):
        k = ev.get("event_type")
        if k == "EMAIL_SENT":
            continue                      # already listed with its subject
        rows.append({"at": ev.get("timestamp"), "kind": k.lower(),
                     "what": _EVENT_WORDS.get(k, k),
                     "detail": _D(ev.get("metadata")).get("url", "")})
    for a in repo.all("agent_actions"):
        if a.get("target_id") == profile_id:
            rows.append({"at": a.get("timestamp"), "kind": "agent",
                         "what": f"Agent: {a.get('action_type')}",
                         "detail": str(a.get("output"))[:120]})
    return sorted([r for r in rows if r.get("at")],
                  key=lambda r: str(r["at"]))


# ---------------------------------------------------------------------------
# THE PROJECTION. His real data, as OS records.
# ---------------------------------------------------------------------------
def _touch_count(sent_to_val) -> int:
    v = sent_to_val
    if isinstance(v, list):
        return len(v)
    return 1 if v else 0


def project(store, jobs=None, *, workspace_id=DEFAULT_WORKSPACE,
            reply_drafts=None, repo=None) -> dict:
    """Read the engine's live outreach jobs and write them into the OS.

    THIS IS THE BRIDGE. Everything the founder already has (leads, sends,
    subjects, opens, clicks, suppressions) becomes profiles, leads,
    campaigns, messages, email jobs and events. Runs on every render and is
    idempotent: ids are content-derived and events are keyed, so a second
    pass changes nothing.
    """
    repo = repo if repo is not None else Repo(store, workspace_id)
    jobs = [j for j in _L(jobs) if isinstance(j, dict)]
    out = {"profiles": 0, "leads": 0, "campaigns": 0, "messages": 0,
           "events": 0, "suppressions": 0}
    seen_events = {r.get("event_key") for r in repo.all("email_events")}
    before_ev = len(seen_events)

    # -- suppression list already kept by the sender ------------------------
    try:
        supp = store.get_setting("email_suppression", []) or []
        meta = store.get_setting("email_suppression_meta", {}) or {}
    except Exception:
        supp, meta = [], {}
    known = suppression_index(repo)
    for em in _L(supp):
        em = norm_email(em)
        if em and em not in known:
            reason = str(_D(meta).get(em, {}).get("reason", "")).upper()
            suppress(repo, em, reason if reason in SUPPRESSION_REASONS
                     else "MANUAL", note="imported from the sender's list")
            out["suppressions"] += 1

    # -- tracking tokens and their events -----------------------------------
    try:
        tokens = store.get_setting("outreach_tokens", {}) or {}
        tevents = store.get_setting("outreach_events", []) or []
    except Exception:
        tokens, tevents = {}, []

    for job in jobs:
        if job.get("type") != "outreach_campaign":
            continue
        p = _D(job.get("payload"))
        jid = str(job.get("job_id") or "")
        leads = _L(p.get("leads"))
        qmap = {norm_email(r.get("id")): r
                for r in _L(_D(p.get("lead_qualifier")).get("results"))}
        sent_to = _D(p.get("sent_to"))
        sent_at = _D(p.get("sent_at"))
        sent_meta = _D(p.get("sent_meta"))
        oc = _D(p.get("outreach_copy"))
        edits = _D(p.get("email_edits"))

        # One CAMPAIGN per job. Its content is the copy the agent wrote.
        cid = rid("camp", repo.ws, jid)
        sent_total = sum(len(_L(v)) for v in sent_at.values())
        # A three touch sequence is not finished because one email left.
        # SENDING while anybody still has a step to come; SENT only when
        # every lead has had all three. Calling it SENT early would lock
        # the campaign and refuse to queue the follow ups.
        import content_engine_connectors as _C
        touches = getattr(_C, "SEQUENCE_TOUCHES", 3)
        done = (leads and all(len(_L(sent_at.get(norm_email(_D(L).get("email")))))
                              >= touches for L in leads))
        state = ("SENT" if sent_total and done else
                 "SENDING" if sent_total else
                 "DRAFT" if not oc.get("body") else "REVIEW")
        cur = repo.one("campaigns", cid) or {}
        repo.put("campaigns", {
            "id": cid, "job_id": jid,
            "name": p.get("name") or p.get("campaign") or jid,
            "state": cur.get("state") if cur.get("state") in ("CANCELLED",
                                                              "COMPLETED")
                     else state,
            "source": "projected",
            "subject_variants": _L(oc.get("subject_variants")),
            "body": oc.get("body", ""),
            "audience_kind": "job", "audience_id": jid,
            "recipients": len(leads),
            "created_at": job.get("created_at") or now()})
        out["campaigns"] += 1

        for L in leads:
            em = norm_email(L.get("email"))
            if not em:
                continue
            q = qmap.get(em) or {}
            comp = upsert_company(repo, L.get("company"),
                                  website=L.get("website"),
                                  country=L.get("country"))
            prof = upsert_profile(repo, {
                "email": em, "name": L.get("name"),
                "company": L.get("company"), "company_id": comp.get("id", ""),
                "job_title": L.get("title") or L.get("role"),
                "website": L.get("website"),
                "linkedin_url": L.get("linkedin"),
                "country": L.get("country"), "city": L.get("city"),
                "phone": L.get("phone"),
                "source": L.get("source") or "agent",
                "source_id": jid,
                "properties": {k: v for k, v in {
                    "industry": L.get("industry"),
                    "company_size": L.get("size"),
                    "lead_score": q.get("score"),
                    "pain_point": q.get("reason") or q.get("why"),
                }.items() if v not in (None, "")},
            })
            if not prof:
                continue
            pid = prof["id"]
            out["profiles"] += 1
            touches = _touch_count(sent_to.get(em))
            upsert_lead(repo, pid, company_id=comp.get("id", ""),
                        source=L.get("source") or "agent", source_url=jid,
                        score=q.get("score"),
                        qualification_status=q.get("verdict") or "",
                        stage=("CONTACTED" if touches else
                               "QUALIFIED" if q else "NEW"),
                        assigned_agent="lead_qualifier" if q else "")
            out["leads"] += 1

            # MESSAGES: one per (campaign, person, touch). This is the row
            # the founder reads. A sent touch takes its subject from
            # sent_meta, which is the only record of what actually left.
            stamps = _L(sent_at.get(em))
            metas = _L(sent_meta.get(em))
            for i, at in enumerate(stamps):
                mrec = metas[i] if i < len(metas) else {}
                mid = rid("msg", repo.ws, cid, em, i + 1)
                repo.put("campaign_messages", {
                    "id": mid, "campaign_id": cid, "profile_id": pid,
                    "email": em, "touch": int(mrec.get("step") or i + 1),
                    "subject": mrec.get("subject") or "",
                    "alias": mrec.get("alias") or "",
                    "sent_at": at, "state": "SENT",
                    "edited": bool(edits.get(f"{em}|{i + 1}")
                                   or (i == 0 and edits.get(em))),
                    "job_id": jid})
                out["messages"] += 1
                repo.put("email_jobs", {
                    "id": rid("ej", repo.ws, cid, em, i + 1),
                    "campaign_id": cid, "profile_id": pid, "message_id": mid,
                    "email": em, "status": "SENT", "provider": "smtp",
                    "scheduled_at": at, "sent_at": at, "attempts": 1})
                if record_event(repo, "EMAIL_SENT", profile_id=pid,
                                campaign_id=cid, message_id=mid, at=at,
                                _index=seen_events):
                    out["events"] += 1

    # -- opens and clicks, from the tracking store ---------------------------
    tok_by = {}
    for tk, tv in _D(tokens).items():
        tv = _D(tv)
        em = norm_email(tv.get("email"))
        if not em:
            continue
        pid = rid("prf", repo.ws, em)
        cid = rid("camp", repo.ws, str(tv.get("job") or ""))
        step = int(tv.get("step") or 1)
        tok_by[tk] = (pid, cid, rid("msg", repo.ws, cid, em, step))
    for ev in _L(tevents):
        ev = _D(ev)
        got = tok_by.get(ev.get("token"))
        if not got:
            continue
        pid, cid, mid = got
        kind = ("EMAIL_CLICKED" if str(ev.get("kind")).lower() == "click"
                else "EMAIL_OPENED")
        if record_event(repo, kind, profile_id=pid, campaign_id=cid,
                        message_id=mid, at=ev.get("at"),
                        metadata={"url": ev.get("url", "")},
                        _index=seen_events):
            out["events"] += 1

    # -- replies, so the inbox is part of the same timeline ------------------
    for d in _L(reply_drafts):
        d = _D(d)
        em = norm_email(d.get("from") or d.get("email"))
        if not em:
            continue
        pid = rid("prf", repo.ws, em)
        if repo.one("profiles", pid):
            lead = repo.one("leads", rid("lead", repo.ws, pid))
            if lead and lead.get("stage") in ("NEW", "QUALIFIED", "CONTACTED"):
                lead["stage"] = "ENGAGED"
                repo.put("leads", lead)

    out["events_total"] = before_ev + out["events"]
    return out


def summary(repo: Repo) -> dict:
    """The counts the Overview screen reads. One pass, no rate without its
    denominator."""
    profs = repo.all("profiles")
    leads = repo.all("leads")
    evs = repo.all("email_events")
    by = {}
    for e_ in evs:
        by[e_.get("event_type")] = by.get(e_.get("event_type"), 0) + 1
    sent = by.get("EMAIL_SENT", 0)
    qualified = [l for l in leads if l.get("stage") not in ("NEW",)]
    emailable = [p for p in profs
                 if p.get("consent") not in ("UNSUBSCRIBED", "SUPPRESSED")
                 and valid_email(p.get("email"))]
    return {
        "profiles": len(profs), "leads": len(leads),
        "qualified": len(qualified),
        "ai_qualified": len([l for l in leads if l.get("score") is not None]),
        "emailable": len(emailable),
        "sent": sent, "delivered": by.get("EMAIL_DELIVERED", 0) or None,
        "opened": by.get("EMAIL_OPENED", 0), "clicked": by.get("EMAIL_CLICKED", 0),
        "unsubscribed": by.get("EMAIL_UNSUBSCRIBED", 0),
        "bounced": by.get("EMAIL_BOUNCED", 0) or None,
        "campaigns": len(repo.all("campaigns")),
        "messages": len(repo.all("campaign_messages")),
        "suppressed": len(repo.all("suppressions")),
        "companies": len(repo.all("companies")),
        "stages": {s: len([l for l in leads if l.get("stage") == s])
                   for s in LEAD_STAGES},
        "open_rate": rate(by.get("EMAIL_OPENED", 0), sent),
        "click_rate": rate(by.get("EMAIL_CLICKED", 0), sent),
        "runs": len(repo.all("agent_runs")),
        "actions": len(repo.all("agent_actions")),
    }
