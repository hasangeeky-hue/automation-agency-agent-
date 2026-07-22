"""
content_engine_code_skills.py
============================================================================
The pure-code skill handlers (SECTION 9). No LLM. Called by the orchestrator
as CODE_HANDLERS[skill](job).

  SKILL 2   authority_backlinks : backlink math / gap analysis
  SKILL 12  lead_sourcing       : collect + dedupe + email-verify
  SKILL 8   publisher           : CMS/social/email publish (idempotent)
  SKILL 14s outreach_send       : send + track (idempotent)

Network I/O is behind injectable module-level hooks that default to reading
code-collected data already on the job payload, so every handler runs and
self-tests OFFLINE. In production, set the hooks (or replace the payload
pre-population) to your real data sources:

    import content_engine_code_skills as cs
    cs.SOURCE_FN    = my_apollo_pull          # returns list[dict] of raw leads
    cs.VERIFY_FN    = my_email_verifier        # (email) -> bool
    cs.BACKLINK_FN  = my_ahrefs_pull           # returns {client, competitors}
    cs.PUBLISH_FN   = my_cms_publisher         # (job, piece) -> external ref
    cs.SEND_FN      = my_esp_sender            # (job, email) -> external ref

Idempotency: publisher/outreach_send guard on an external ref already written
to the payload, so a retry never double-fires.
============================================================================
"""

from __future__ import annotations

import re
from typing import Callable, Optional

# --- pluggable I/O hooks (default: offline, read from payload) --------------
SOURCE_FN: Optional[Callable[[dict], list]] = None   # -> raw leads
VERIFY_FN: Optional[Callable[[str], bool]] = None    # -> email deliverable?
BACKLINK_FN: Optional[Callable[[dict], dict]] = None # -> {client, competitors}
PUBLISH_FN: Optional[Callable[[dict, dict], str]] = None  # -> CMS ref (WordPress)
SOCIAL_FN: Optional[Callable[[dict, dict, str], str]] = None  # (job, piece, channel) -> ref
SEND_FN: Optional[Callable[[dict, dict], str]] = None     # -> external ref

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _default_verify(email: str) -> bool:
    """Syntactic-only fallback. Replace VERIFY_FN with an MX/SMTP verifier."""
    return bool(email and _EMAIL_RE.match(email.strip()))


# ---------------------------------------------------------------------------
# SKILL 12 — Lead Sourcing
# ---------------------------------------------------------------------------
def lead_sourcing(job: dict) -> dict:
    payload = job.setdefault("payload", {})
    raw = SOURCE_FN(job) if SOURCE_FN else payload.get("raw_leads", [])
    verify = VERIFY_FN or _default_verify

    seen: set[str] = set()
    leads: list[dict] = []
    dropped_dupe = dropped_invalid = 0
    for lead in raw or []:
        email = (lead.get("email") or "").strip().lower()
        key = email or (lead.get("domain") or lead.get("company") or "").strip().lower()
        if not key:
            dropped_invalid += 1
            continue
        if key in seen:
            dropped_dupe += 1
            continue
        seen.add(key)
        if email and not verify(email):
            dropped_invalid += 1
            continue
        leads.append(lead)

    payload["leads"] = leads
    return {
        "raw": len(raw or []),
        "deduped": len(raw or []) - dropped_dupe,
        "verified": len(leads),
        "dropped_duplicate": dropped_dupe,
        "dropped_invalid": dropped_invalid,
    }


# ---------------------------------------------------------------------------
# SKILL 2 — Authority / Backlinks (math only)
# ---------------------------------------------------------------------------
def authority_backlinks(job: dict) -> dict:
    payload = job.setdefault("payload", {})
    data = BACKLINK_FN(job) if BACKLINK_FN else payload.get("backlinks", {})
    client_rd = {d.lower() for d in (data.get("client", {}) or {}).get("referring_domains", [])}

    # Count how many competitors link from each domain the client lacks.
    gap_counts: dict[str, int] = {}
    competitor_rd_union: set[str] = set()
    for comp in data.get("competitors", []) or []:
        rds = {d.lower() for d in comp.get("referring_domains", [])}
        competitor_rd_union |= rds
        for d in rds - client_rd:
            gap_counts[d] = gap_counts.get(d, 0) + 1

    gap_domains = sorted(gap_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    result = {
        "client_referring_domains": len(client_rd),
        "competitor_referring_domains": len(competitor_rd_union),
        # domains linking to >=2 competitors but not the client = highest-value targets
        "priority_gap_domains": [d for d, n in gap_domains if n >= 2][:20],
        "all_gap_domains": [d for d, _ in gap_domains][:100],
        "gap_count": len(gap_domains),
    }
    payload["authority"] = result
    return result


# ---------------------------------------------------------------------------
# SKILL 8 — Publisher (idempotent, multi-channel: CMS + social)
# ---------------------------------------------------------------------------
def _target_channels(job: dict) -> list:
    """Where to publish this piece. Defaults to the website only (preserves prior
    behavior); set payload.config.deploy_channels to fan out, e.g.
    ["wordpress", "linkedin", "twitter"]."""
    cfg = job.get("payload", {}).get("config", {}) or {}
    channels = cfg.get("deploy_channels") or ["wordpress"]
    return [str(c).lower() for c in channels]


def publisher(job: dict) -> dict:
    payload = job.setdefault("payload", {})
    if payload.get("published_ref"):
        return {"already_published": payload["published_ref"]}
    piece = payload.get("content_producer", {})

    refs: dict[str, str] = {}
    for ch in _target_channels(job):
        if ch in ("wordpress", "cms", "web", "blog"):
            refs[ch] = PUBLISH_FN(job, piece) if PUBLISH_FN else f"pub_{job['job_id']}"
        else:
            refs[ch] = (SOCIAL_FN(job, piece, ch) if SOCIAL_FN
                        else f"social_{ch}_{job['job_id']}")

    # Primary ref = the CMS/web post if there is one, else the first channel.
    primary = (refs.get("wordpress") or refs.get("cms") or refs.get("web")
               or refs.get("blog") or next(iter(refs.values()), f"pub_{job['job_id']}"))
    payload["published_ref"] = primary
    payload["published_refs"] = refs
    return {"published_ref": primary, "channels": refs}


# ---------------------------------------------------------------------------
# SKILL 14 (send phase) — Outreach Send (idempotent)
# ---------------------------------------------------------------------------
def outreach_send(job: dict) -> dict:
    payload = job.setdefault("payload", {})
    if payload.get("send_ref"):
        return {"already_sent": payload["send_ref"]}
    email = payload.get("outreach_copy", {})
    ref = SEND_FN(job, email) if SEND_FN else f"send_{job['job_id']}"
    payload["send_ref"] = ref
    return {"send_ref": ref}


# Registry the orchestrator imports.
CODE_HANDLERS: dict[str, Callable[[dict], dict]] = {
    "lead_sourcing": lead_sourcing,
    "authority_backlinks": authority_backlinks,
    "publisher": publisher,
    "outreach_send": outreach_send,
}


# ---------------------------------------------------------------------------
# Self-check: unit tests for the code skills + a full Pipeline B run through
# the LIVE orchestrator (LLM stubbed). No network, no API.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # --- lead_sourcing: dedupe + verify ---
    job = {"job_id": "j1", "payload": {"raw_leads": [
        {"email": "A@x.com", "company": "X"},
        {"email": "a@x.com", "company": "X dup"},     # dupe (case-insensitive)
        {"email": "bad-email", "company": "Y"},        # invalid syntax
        {"email": "c@z.io", "company": "Z"},
        {"domain": "no-email.com", "company": "W"},     # kept via domain key
    ]}}
    r = lead_sourcing(job)
    assert r["verified"] == 3, r
    assert r["dropped_duplicate"] == 1 and r["dropped_invalid"] == 1, r
    assert len(job["payload"]["leads"]) == 3

    # --- authority_backlinks: gap math ---
    job2 = {"job_id": "j2", "payload": {"backlinks": {
        "client": {"referring_domains": ["a.com", "b.com"]},
        "competitors": [
            {"name": "R1", "referring_domains": ["a.com", "c.com", "d.com"]},
            {"name": "R2", "referring_domains": ["c.com", "e.com"]},
        ]}}}
    r2 = authority_backlinks(job2)
    assert r2["client_referring_domains"] == 2, r2
    assert "c.com" in r2["priority_gap_domains"], r2   # linked by 2 competitors, not client
    assert "d.com" in r2["all_gap_domains"] and "d.com" not in r2["priority_gap_domains"], r2

    # --- idempotency ---
    job3 = {"job_id": "j3", "payload": {}}
    a = publisher(job3); b = publisher(job3)
    assert a["published_ref"] == "pub_j3" and "already_published" in b

    # --- Pipeline B end-to-end through the live orchestrator (LLM stubbed) ---
    import content_engine_orchestrator as orch
    from content_engine_prep import prepare_input

    captured = {}

    def stub_llm(job, skill, store):
        inp = prepare_input(skill, job)
        captured[skill] = inp
        canned = {
            "lead_qualifier": {"results": []},
            "segmenter": {"segments": []},
            "outreach_copy": {"subject_variants": ["A", "B"],
                              "body": "Hi. 123 Main St. Unsubscribe {{unsubscribe_token}}",
                              "cta": "Reply", "personalization_used": []},
            "qa_compliance": {"verdict": "pass", "brand_voice_match": True,
                              "issues": [], "claims_check": {}, "compliance": {}},
            "analytics_funnel": {"headline": "", "what_worked": [], "what_dropped": [],
                                 "biggest_leak": {}, "recommended_focus_next": ""},
            "optimizer": {"insights": [], "double_down": [], "reduce_or_cut": [],
                          "next_cycle": {}},
        }.get(skill, {"ok": True})
        return canned, 0.003
    orch._LLM_HOOK = stub_llm

    store = orch.InMemoryJobStore()
    bjob = orch.new_job("job_B_e2e", "outreach_campaign",
                        {"brand_name": "Anthropos", "offer": "AI automation"},
                        {"raw_leads": [{"email": "lead@co.com", "company": "Co"}],
                         "buckets": [{"bucket_id": 1, "rfm": 9, "engagement": 8,
                                      "churn": 1, "size": 10, "avg_ltv": 100}],
                         "category": "saas",
                         "lead": {"first_name": "Sam", "company": "Co",
                                  "industry": "saas", "signal": "hiring"},
                         "config": {"our_offer": "AI automation", "proof_point": "",
                                    "sender_name": "M", "physical_address": "123 Main St"}})
    store.put(bjob)
    s = orch.tick(store)
    assert s == "AWAITING_APPROVAL", f"B expected gate, got {s}"
    assert bjob["payload"]["leads"], "lead_sourcing did not populate leads"
    assert bjob["payload"].get("send_ref") is None, "sent before approval!"
    orch.approve("job_B_e2e", store)
    s = orch.tick(store)
    assert s == "sent", f"B expected send then measure-wait, got {s}"
    assert bjob["payload"]["outreach_send"]["send_ref"] == "send_job_B_e2e"
    bjob["ready_to_measure"] = True
    store.save(bjob)
    s = orch.tick(store)
    assert s == "optimized", f"B expected optimized, got {s}"
    assert captured["qa_compliance"]["content_type"] == "email_outreach", \
        "QA content_type should be email_outreach for Pipeline B"

    orch._LLM_HOOK = orch.run_llm_skill  # restore
    print("OK — code skills verified (lead dedupe/verify, backlink gap math, "
          "idempotent publish/send) + Pipeline B chained end-to-end through the "
          "orchestrator. (No network, no API.)")
