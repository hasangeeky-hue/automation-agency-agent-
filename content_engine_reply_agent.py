"""
content_engine_reply_agent.py
============================================================================
Q18b — ANSWER INBOUND CUSTOMER REPLIES.

Reads unread replies over IMAP, drafts a reply with the `reply_responder` skill
(Claude), and — only when it's safe — sends it back over SMTP. Trigger it from
an n8n cron (e.g. every 15 min) or run it once.

SAFETY (important for a non-pro to trust it):
  * Default is DRAFT-ONLY. Nothing is sent unless REPLY_AUTO_SEND=1.
  * Even with auto-send ON, anything the model flags needs_human=true
    (complaints, refunds, legal, objections, or anything it can't answer from
    the given facts) is held as "pending_human" and never auto-sent.
  * The model is told to NEVER invent pricing/features/results — if the answer
    isn't in the provided context, it writes an honest holding reply and flags
    it for a human.

Config (env):
  IMAP_HOST / IMAP_PORT / IMAP_USER / IMAP_PASSWORD / IMAP_FOLDER   inbound
  SMTP_* (see connectors)                                           outbound
  REPLY_OUR_OFFER     one/two lines describing what you sell (grounds the model)
  REPLY_SENDER_NAME   signature name
  REPLY_CONTEXT       extra facts the model may use (hours, links, policy)
  REPLY_MODEL         default claude-haiku-4-5
  REPLY_AUTO_SEND     1 = actually send safe replies; default 0 (draft only)
  BRAND_NAME          for brand voice

Run:
  python content_engine_reply_agent.py           # offline self-check
  # in production (from a worker/n8n):
  #   import content_engine_reply_agent as r; r.answer_replies()
============================================================================
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

import content_engine_connectors as connectors

log = logging.getLogger("reply_agent")

# Model escalation for the reply skill (cheap first, stronger on invalid shape).
REPLY_MODELS = [os.getenv("REPLY_MODEL", "claude-haiku-4-5"), "claude-sonnet-5"]


# ---------------------------------------------------------------------------
# LLM runner — build the reply_responder prompt, call Claude, validate.
# Injectable (_LLM_HOOK) so the self-check runs with zero API calls.
# ---------------------------------------------------------------------------
def _default_llm(job: dict) -> Optional[dict]:
    from content_engine_providers import build_prompt, call_provider
    from content_engine_schemas import SCHEMAS

    spec = build_prompt("reply_responder", job)
    schema = SCHEMAS.get("reply_responder")
    for model in REPLY_MODELS:
        try:
            result = call_provider(model, spec)
        except Exception as e:
            log.warning("reply LLM call failed on %s: %s", model, e)
            continue
        ok, _ = schema.validate(result.data) if schema else (True, [])
        if ok and "error" not in result.data:
            return result.data
    return None


_LLM_HOOK: Callable[[dict], Optional[dict]] = _default_llm


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------
def answer_replies(limit: int = 20, auto_send: Optional[bool] = None,
                   dry_run: bool = False, inbound=None, emailer=None) -> dict:
    """Fetch unread replies, draft answers, and send the safe ones.
    Returns a structured summary (safe to log / return from an API)."""
    inbound = inbound or connectors.InboundEmail()
    if not inbound.available():
        return {"status": "skipped",
                "reason": "IMAP not configured (set IMAP_HOST/IMAP_USER/IMAP_PASSWORD)"}

    emailer = emailer or connectors.Emailer()
    if auto_send is None:
        auto_send = os.getenv("REPLY_AUTO_SEND", "0") == "1"

    our_offer = os.getenv("REPLY_OUR_OFFER", "")
    sender_name = os.getenv("REPLY_SENDER_NAME", "")
    context = os.getenv("REPLY_CONTEXT", "")
    brand = {"brand_name": os.getenv("BRAND_NAME", "")}

    results: list = []
    for m in inbound.fetch_unread(limit):
        payload = {
            "from": m.get("from", ""),
            "subject": m.get("subject", ""),
            "message": m.get("message", ""),
            "our_offer": our_offer,
            "sender_name": sender_name,
            "context": context,
        }
        job = {"job_id": m.get("message_id") or m.get("uid") or "reply",
               "brand": brand, "payload": payload}

        data = _LLM_HOOK(job)
        if not data:
            results.append({"from": m.get("from_email", ""), "status": "llm_failed"})
            continue

        entry = {
            "from": m.get("from_email", ""),
            "intent": data.get("intent"),
            "needs_human": bool(data.get("needs_human")),
            "reply_subject": data.get("reply_subject", ""),
            "reply_body": data.get("reply_body", ""),
            "notes": data.get("notes", ""),
        }

        if dry_run:
            entry["status"] = "drafted_dry_run"
        elif entry["needs_human"] or not auto_send:
            # Safe default: hold for a human (also the path when auto-send is off).
            entry["status"] = "pending_human"
        elif not emailer.available():
            entry["status"] = "no_email_transport"
        else:
            ref = emailer.send_message(
                m.get("from_email", ""), data.get("reply_subject", ""),
                data.get("reply_body", ""),
                extra_headers={"In-Reply-To": m.get("message_id", ""),
                               "References": m.get("message_id", "")})
            entry["status"] = "sent"
            entry["send_ref"] = ref
        results.append(entry)

    sent = sum(1 for r in results if r["status"] == "sent")
    held = sum(1 for r in results if r["status"] == "pending_human")
    log.info("reply agent: %d processed, %d sent, %d held for human",
             len(results), sent, held)
    return {"status": "ok", "count": len(results),
            "sent": sent, "pending_human": held, "results": results}


# ---------------------------------------------------------------------------
# Offline self-check — proves the wiring end-to-end with fakes (no IMAP/SMTP/API).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 1) The reply skill is wired into prompts/schemas/providers (offline check).
    from content_engine_providers import build_prompt
    spec = build_prompt("reply_responder",
                        {"job_id": "t", "brand": {"brand_name": "Anthropos"},
                         "payload": {"from": "a@b.com", "subject": "hi",
                                     "message": "how much?", "our_offer": "AI automation",
                                     "sender_name": "M", "context": ""}})
    assert spec.max_tokens == 500, spec.max_tokens
    assert len(spec.system_blocks) == 3 and "cache_control" in spec.system_blocks[-1]
    assert spec.schema is not None, "reply_responder schema should be registered"

    # 2) Fakes for IMAP + SMTP so the agent runs with no network.
    class FakeInbound:
        def available(self):
            return True

        def fetch_unread(self, limit):
            return [
                {"uid": "1", "from": "Sam <sam@co.com>", "from_email": "sam@co.com",
                 "subject": "pricing?", "message_id": "<a1>",
                 "message": "How much does it cost?"},
                {"uid": "2", "from": "Pat <pat@co.com>", "from_email": "pat@co.com",
                 "subject": "angry", "message_id": "<a2>",
                 "message": "This is broken and I want a refund now."},
            ]

    class FakeEmailer:
        def __init__(self):
            self.sent = []

        def available(self):
            return True

        def send_message(self, to, subject, body, extra_headers=None):
            self.sent.append((to, subject))
            return f"msgid:{to}"

    # 3) Stub the LLM: first mail is a simple answerable question; second is a
    #    complaint the model flags for a human.
    def stub(job):
        msg = job["payload"]["message"].lower()
        if "refund" in msg or "broken" in msg:
            return {"intent": "complaint", "needs_human": True,
                    "reply_subject": "Re: angry", "reply_body": "Sorry — a human will help.",
                    "notes": "escalate"}
        return {"intent": "question", "needs_human": False,
                "reply_subject": "Re: pricing?",
                "reply_body": "Happy to help — want a quick call?", "notes": ""}

    _LLM_HOOK = stub

    # auto_send ON: the simple question should send; the complaint must be HELD.
    fe = FakeEmailer()
    out = answer_replies(auto_send=True, inbound=FakeInbound(), emailer=fe)
    assert out["status"] == "ok" and out["count"] == 2, out
    assert out["sent"] == 1, f"expected 1 auto-sent, got {out['sent']}"
    assert out["pending_human"] == 1, "complaint must be held for a human"
    assert fe.sent == [("sam@co.com", "Re: pricing?")], fe.sent

    # auto_send OFF (default): nothing sends, everything is queued for a human.
    fe2 = FakeEmailer()
    out2 = answer_replies(auto_send=False, inbound=FakeInbound(), emailer=fe2)
    assert out2["sent"] == 0 and out2["pending_human"] == 2, out2
    assert fe2.sent == [], "auto_send off must not send anything"

    # No IMAP configured -> clean skip, no crash.
    class NoInbound:
        def available(self):
            return False

    assert answer_replies(inbound=NoInbound())["status"] == "skipped"

    _LLM_HOOK = _default_llm  # restore
    print("OK — reply agent verified: skill wired (prompt/schema/providers), "
          "answerable replies auto-send, complaints held for human, auto_send "
          "off holds everything, missing IMAP skips cleanly. (No network, no API.)")
