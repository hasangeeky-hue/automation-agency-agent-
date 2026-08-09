# -*- coding: utf-8 -*-
"""CONTENT FACTORY OS: the domain and its deterministic services.

Spec sections 0-5, 22-23, 30, 33-36, 43-45, 54, 57, 63-67, 70-71, 73-74,
78-79, 87, 107, 109-110.

THE BOUNDARY (section 0, non-negotiable)
----------------------------------------
This module owns exactly one chain:

    OPPORTUNITY -> PLAN -> BRIEF -> CREATE -> ASSET -> VARIANT ->
    COLLABORATE -> PREVIEW -> APPROVE -> HANDOFF -> RESULT -> LEARN

It does NOT own ad campaigns, crawlers, keyword databases, GA4 reporting,
a CRM, an email sender, a backlink engine, a video editor or a DAM. Those
belong to the SEO OS, the Media Buying OS, the Email OS, the CRM and the
Analytics OS, and they already exist in this codebase. The factory reads
their signals through a contract and hands work back to them through a
package. Section 86: never query another OS's tables.

WHY MOST OF THIS FILE IS NOT AI
-------------------------------
Section 73 is explicit that versioning, permissions, storage, approval,
scheduling, distribution, tool routing, platform validation, analytics
calculation, state transitions and audit logging are SERVICES, not
agents. They are here, they are deterministic, and they are testable
without spending a token. Only four things reason, and they live in
content_engine_factory_agents.py.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ===========================================================================
# 0. THE BOUNDARY, STATED IN CODE
# ===========================================================================
#: What this OS builds. Anything outside it is somebody else's job.
OWNS = ("OPPORTUNITY", "PLAN", "BRIEF", "CREATE", "ASSET", "VARIANT",
        "COLLABORATE", "PREVIEW", "APPROVE", "HANDOFF", "RESULT", "LEARN")

#: Section 2. Written down so a future contributor has to delete a line
#: here before they can argue the factory should grow one of these.
DOES_NOT_BUILD = (
    ("Google/Meta/TikTok campaign builders", "MEDIA_BUYING_OS"),
    ("SEO crawler, keyword database, Search Console reporting", "SEO_OS"),
    ("GA4 reporting system", "ANALYTICS_OS"),
    ("CRM and sales pipeline", "CRM_OS"),
    ("Email sender, lists, flows", "EMAIL_OS"),
    ("Social analytics provider", "SOCIAL_OS"),
    ("Backlink engine", "SEO_OS"),
    ("Full video editor, image design tool, DAM", "external tools"),
)

# ===========================================================================
# 4. THE NORMALIZED CONTENT SIGNAL
# ===========================================================================
SOURCE_SYSTEMS = ("SEO_OS", "MEDIA_BUYING_OS", "EMAIL_OS", "CRM_OS",
                  "SOCIAL_OS", "ANALYTICS_OS", "MANUAL", "EXTERNAL_TOOL")

SIGNAL_TYPES = ("CONTENT_OPPORTUNITY", "WINNING_CREATIVE",
                "CUSTOMER_OBJECTION", "WINNING_MESSAGE", "CONTENT_DECAY",
                "COMPETITOR_MOVE", "AUDIENCE_INSIGHT", "MANUAL_REQUEST")

SIGNAL_STATUS = ("NEW", "REVIEWED", "ACCEPTED", "DISMISSED", "EXPIRED")

#: Every field section 4 lists. One place, so a signal written by the SEO
#: OS and a signal written by hand are the same shape by construction.
SIGNAL_FIELDS = (
    "id", "workspace_id", "brand_id", "source_system", "signal_type",
    "subject_type", "subject_id", "topic", "message", "metric_name",
    "metric_value", "comparison_value", "change_percent", "priority",
    "confidence", "evidence_json", "recommended_action", "received_at",
    "expires_at", "status")


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
    """A stable id from its parts, so the same input never makes two rows."""
    raw = "|".join(_s(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_signal(raw, *, received_at="") -> Dict[str, Any]:
    """One incoming signal, in the shape section 4 defines.

    An unknown source_system or signal_type is kept and marked UNKNOWN
    rather than dropped or coerced into a neighbour. A signal we cannot
    classify is still evidence that something happened; silently
    relabelling it would make the inbox lie about where work came from.
    """
    d = _d(raw)
    src = _s(d.get("source") or d.get("source_system")).upper()
    typ = _s(d.get("signal_type")).upper()
    out = {k: d.get(k) for k in SIGNAL_FIELDS}
    out["source_system"] = src if src in SOURCE_SYSTEMS else "EXTERNAL_TOOL"
    out["signal_type"] = typ if typ in SIGNAL_TYPES else "MANUAL_REQUEST"
    out["unknown_source"] = src not in SOURCE_SYSTEMS and bool(src)
    out["unknown_type"] = typ not in SIGNAL_TYPES and bool(typ)
    out["topic"] = _s(d.get("topic") or d.get("subject_theme")
                      or d.get("hook"))
    out["priority"] = _f(d.get("priority"))
    out["confidence"] = _f(d.get("confidence"))
    ev = d.get("evidence") if d.get("evidence") is not None \
        else d.get("evidence_json")
    out["evidence_json"] = ev if isinstance(ev, (list, dict)) else []
    out["recommended_action"] = (d.get("recommendation")
                                 or d.get("recommended_action"))
    out["recommended_format"] = _l(d.get("recommended_format"))
    out["received_at"] = _s(d.get("received_at") or received_at)
    out["status"] = (_s(d.get("status")).upper() or "NEW")
    if out["status"] not in SIGNAL_STATUS:
        out["status"] = "NEW"
    out["id"] = d.get("id") or _id(out["source_system"], out["signal_type"],
                                   out["topic"], out["received_at"])
    # Section 108. The metric came from another OS; this OS records it and
    # never recomputes or "corrects" it.
    out["metric_name"] = d.get("metric_name") or _metric_name(d)
    out["metric_value"] = _f(d.get("metric_value")
                             if d.get("metric_value") is not None
                             else _metric_value(d))
    return out


def _metric_name(d) -> Optional[str]:
    for k in ("roas", "ctr", "frequency", "conversions", "revenue",
              "impressions", "clicks"):
        if d.get(k) is not None:
            return k
    return None


def _metric_value(d):
    n = _metric_name(d)
    return d.get(n) if n else None


def signal_is_actionable(sig) -> Dict[str, Any]:
    """Can this signal become a plan? Says why not, when it cannot."""
    s = _d(sig)
    if s.get("status") == "DISMISSED":
        return {"ok": False, "why": "this signal was dismissed"}
    if s.get("status") == "EXPIRED":
        return {"ok": False, "why": "this signal is past its expiry"}
    if not _s(s.get("topic")).strip():
        return {"ok": False,
                "why": ("the signal carries no topic, so there is nothing "
                        "to plan content about. The sending system should "
                        "populate topic.")}
    if not s.get("evidence_json"):
        return {"ok": True, "weak": True,
                "why": ("no evidence was attached. The signal can still "
                        "be planned, but nothing here can be quoted as "
                        "fact in a brief.")}
    return {"ok": True, "weak": False, "why": "topic and evidence present"}


# ===========================================================================
# 22-23. PLANS
# ===========================================================================
PLAN_STATUS = ("DRAFT", "REVIEWED", "APPROVED", "ACTIVE", "COMPLETED")

PLAN_MOVES = {
    "DRAFT": ("REVIEWED", "APPROVED"),
    "REVIEWED": ("APPROVED", "DRAFT"),
    "APPROVED": ("ACTIVE",),
    "ACTIVE": ("COMPLETED",),
    "COMPLETED": (),
}

PLAN_ITEM_FIELDS = ("id", "plan_id", "signal_id", "topic", "objective",
                    "audience", "channel", "format", "paid_or_organic",
                    "priority", "scheduled_date", "status")


# ===========================================================================
# 30. BLOCKS
# ===========================================================================
#: Section 30. A content item is typed blocks, not a wall of text,
#: BECAUSE an agent editing one block cannot damage the rest and a lock
#: can be enforced at the block boundary.
BLOCK_TYPES = ("HEADLINE", "PARAGRAPH", "IMAGE", "VIDEO", "CTA", "QUOTE",
               "LIST", "PRODUCT", "SECTION", "HTML", "SOCIAL_COPY")

#: Section 29. Which blocks each channel expects. Used by the platform
#: validator, which is a SERVICE and not an agent: "does this have a
#: headline" is not a judgement call.
CHANNEL_BLOCKS = {
    "SOCIAL": ("HEADLINE", "SOCIAL_COPY", "CTA"),
    "LINKEDIN": ("HEADLINE", "SOCIAL_COPY", "CTA"),
    "INSTAGRAM": ("SOCIAL_COPY", "IMAGE", "CTA"),
    "TIKTOK": ("SOCIAL_COPY", "VIDEO", "CTA"),
    "PAID_AD": ("HEADLINE", "PARAGRAPH", "CTA"),
    "BLOG": ("HEADLINE", "PARAGRAPH", "SECTION", "CTA"),
    "EMAIL": ("HEADLINE", "PARAGRAPH", "CTA"),
}


def block(btype, text="", *, id=None, locked=False, **extra) -> Dict:
    t = _s(btype).upper()
    return {"id": id or _id(t, text, json.dumps(extra, sort_keys=True,
                                                default=str)),
            "type": t if t in BLOCK_TYPES else "PARAGRAPH",
            "unknown_type": t not in BLOCK_TYPES and bool(t),
            "text": _s(text), "locked": bool(locked), **extra}


# ===========================================================================
# 33. LOCKS. An agent may not touch what a human has settled.
# ===========================================================================
class LockedBlock(Exception):
    """Raised when an agent tries to modify a block a human locked."""


def apply_block_edit(blocks, block_id, new_text, *, actor="AGENT",
                     reason="") -> Dict[str, Any]:
    """Edit ONE block. Refuses a locked block when the actor is an agent.

    Section 33 says agents cannot modify locked blocks. This is enforced
    here rather than in a prompt, because a prompt is a request and this
    is a rule.
    """
    out, found, before = [], False, None
    for b in _l(blocks):
        d = _d(b)
        if d.get("id") != block_id:
            out.append(d)
            continue
        found = True
        before = d.get("text")
        if d.get("locked") and _s(actor).upper() != "HUMAN":
            return {"ok": False, "state": "LOCKED", "blocks": _l(blocks),
                    "why": ("this block is locked by a human. An agent "
                            "cannot change it; unlock it first or edit it "
                            "yourself.")}
        nd = dict(d)
        nd["text"] = _s(new_text)
        out.append(nd)
    if not found:
        return {"ok": False, "state": "NO SUCH BLOCK", "blocks": _l(blocks),
                "why": "no block with id " + _s(block_id)}
    if _s(before) == _s(new_text):
        return {"ok": False, "state": "NO CHANGE", "blocks": out,
                "why": ("before and after are identical, so this would "
                        "create a version that records nothing")}
    return {"ok": True, "state": "EDITED", "blocks": out,
            "before": before, "after": _s(new_text),
            "actor": _s(actor).upper(), "reason": _s(reason)}


def set_lock(blocks, block_id, locked=True, *, actor="HUMAN") -> List[Dict]:
    """Only a human locks or unlocks. An agent locking its own work would
    make the lock meaningless."""
    if _s(actor).upper() != "HUMAN":
        raise LockedBlock("only a human can change a lock")
    return [dict(_d(b), locked=bool(locked))
            if _d(b).get("id") == block_id else _d(b) for b in _l(blocks)]


# ===========================================================================
# 34-36. VERSIONS AND DIFF
# ===========================================================================
VERSION_SOURCES = ("HUMAN", "AGENT", "IMPORT", "TOOL", "PLATFORM_VARIANT")


def new_version(versions, snapshot, *, changed_by, source,
                change_summary="", at="") -> Dict[str, Any]:
    """Section 34: EVERY mutation creates a version.

    The snapshot is deep-copied. Storing a reference would let a later
    edit silently rewrite history, which is the one thing a version
    table exists to prevent.
    """
    src = _s(source).upper()
    if src not in VERSION_SOURCES:
        src = "IMPORT"
    prev = _l(versions)
    n = len(prev) + 1
    return {"id": _id("v", n, changed_by, at),
            "version_number": n,
            "snapshot": copy.deepcopy(snapshot),
            "changed_by": _s(changed_by),
            "source": src,
            "change_summary": _s(change_summary),
            "created_at": _s(at)}


def diff_blocks(before, after) -> List[Dict[str, Any]]:
    """Section 36. Block-level added / removed / changed, in order."""
    a = {_d(b).get("id"): _d(b) for b in _l(before)}
    b = {_d(x).get("id"): _d(x) for x in _l(after)}
    rows = []
    for bid, blk in b.items():
        if bid not in a:
            rows.append({"state": "ADDED", "id": bid,
                         "type": blk.get("type"), "before": None,
                         "after": blk.get("text")})
        elif _s(a[bid].get("text")) != _s(blk.get("text")):
            rows.append({"state": "CHANGED", "id": bid,
                         "type": blk.get("type"),
                         "before": a[bid].get("text"),
                         "after": blk.get("text")})
    for bid, blk in a.items():
        if bid not in b:
            rows.append({"state": "REMOVED", "id": bid,
                         "type": blk.get("type"),
                         "before": blk.get("text"), "after": None})
    return rows


# ===========================================================================
# 43-45. MASTER CONTENT AND VARIANTS
# ===========================================================================
#: Section 109. AI_GENERATED IS NOT A STATE. Generation is an activity
#: inside PRODUCTION, and this tuple is the reason a reviewer can never be
#: handed something whose status is "the machine made it".
CONTENT_STATUS = ("IDEA", "BRIEF", "PRODUCTION", "REVIEW",
                  "CHANGES_REQUESTED", "APPROVED", "SCHEDULED",
                  "DISTRIBUTED", "PUBLISHED", "FAILED", "ARCHIVED")

CONTENT_MOVES = {
    "IDEA": ("BRIEF", "ARCHIVED"),
    "BRIEF": ("PRODUCTION", "ARCHIVED"),
    "PRODUCTION": ("REVIEW", "ARCHIVED"),
    "REVIEW": ("CHANGES_REQUESTED", "APPROVED", "ARCHIVED"),
    "CHANGES_REQUESTED": ("PRODUCTION", "REVIEW", "ARCHIVED"),
    "APPROVED": ("SCHEDULED", "DISTRIBUTED", "CHANGES_REQUESTED"),
    "SCHEDULED": ("DISTRIBUTED", "CHANGES_REQUESTED"),
    "DISTRIBUTED": ("PUBLISHED", "FAILED"),
    "PUBLISHED": ("ARCHIVED",),
    "FAILED": ("PRODUCTION", "ARCHIVED"),
    "ARCHIVED": (),
}


class IllegalTransition(Exception):
    """A state move the machine does not allow."""


def transition(current, target, *, actor="HUMAN", approver="") -> Dict:
    """Move one content item. A SERVICE, section 73, not a judgement.

    Section 54: AI is never the final approver by default. REVIEW to
    APPROVED requires a human actor AND a named approver, and the rule
    lives here so no prompt can talk its way past it.
    """
    cur, tgt = _s(current).upper(), _s(target).upper()
    if cur not in CONTENT_MOVES:
        return {"ok": False, "state": cur,
                "why": "'" + cur + "' is not a content state"}
    if tgt not in CONTENT_MOVES.get(cur, ()):
        return {"ok": False, "state": cur,
                "why": ("cannot go from " + cur + " to " + tgt
                        + ". Allowed from here: "
                        + (", ".join(CONTENT_MOVES[cur]) or "nowhere"))}
    if tgt == "APPROVED":
        if _s(actor).upper() != "HUMAN":
            return {"ok": False, "state": cur,
                    "why": ("only a human approves content. An agent may "
                            "recommend approval and may not grant it.")}
        if not _s(approver).strip():
            return {"ok": False, "state": cur,
                    "why": ("approval must name the person granting it. "
                            "An unattributable approval cannot be "
                            "defended later.")}
    return {"ok": True, "state": tgt, "from": cur,
            "actor": _s(actor).upper(),
            "approver": _s(approver) or None,
            "why": cur + " to " + tgt}


CHANNELS = ("LINKEDIN", "INSTAGRAM", "TIKTOK", "YOUTUBE", "META_PAID",
            "GOOGLE_PAID", "BLOG", "EMAIL", "X")

FORMATS = ("ARTICLE", "SOCIAL_POST", "CAROUSEL", "SHORT_VIDEO",
           "LONG_VIDEO", "STATIC_AD", "VIDEO_AD", "EMAIL_BODY",
           "LANDING_PAGE")

PAID_OR_ORGANIC = ("PAID", "ORGANIC")


# ===========================================================================
# 37-40. TOOL ROUTER. The agent asks for a CAPABILITY, never a vendor.
# ===========================================================================
#: Section 38. MVP starts with three. Video is listed so the router can
#: answer honestly rather than pretending the capability is unknown.
CAPABILITIES = ("TEXT_GENERATION", "IMAGE_GENERATION", "IMAGE_EDITING",
                "VIDEO_GENERATION", "VIDEO_EDIT_REQUEST", "TEXT_TO_SPEECH",
                "TRANSCRIPTION", "SUBTITLE_GENERATION")

MVP_CAPABILITIES = ("TEXT_GENERATION", "IMAGE_GENERATION", "IMAGE_EDITING")

#: capability -> the credential name that would satisfy it. The router
#: reports on PRESENCE only and never reads a key's value; section 82
#: says agents see a capability, not an API key.
CAPABILITY_KEYS = {
    "TEXT_GENERATION": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
    "IMAGE_GENERATION": ("IMAGE_API_KEY", "OPENAI_API_KEY"),
    "IMAGE_EDITING": ("IMAGE_API_KEY", "OPENAI_API_KEY"),
    "VIDEO_GENERATION": ("VIDEO_API_KEY",),
    "VIDEO_EDIT_REQUEST": ("VIDEO_API_KEY",),
    "TEXT_TO_SPEECH": ("TTS_API_KEY", "OPENAI_API_KEY"),
    "TRANSCRIPTION": ("OPENAI_API_KEY",),
    "SUBTITLE_GENERATION": ("OPENAI_API_KEY",),
}


def _key_present(name) -> bool:
    """Presence only, through the same resolver a real call uses.

    connectors._env() is settings-first then environment, so a key set on
    the dashboard Connect board lives in Postgres and os.getenv cannot
    see it. Asking os.getenv reports a configured key as absent, which
    sends someone hunting a problem that is not there.
    """
    try:
        import content_engine_connectors as C
        if _s(C._env(name)).strip():
            return True
    except Exception:                                 # noqa: BLE001
        pass
    import os
    return bool(_s(os.getenv(name)).strip())


def route_tool(capability) -> Dict[str, Any]:
    """Which provider can serve this capability, and can it serve it now.

    Section 37: the agent must not depend on one vendor. It names a
    capability; this decides the provider. An unavailable capability
    returns UNAVAILABLE with the reason, and never a silent no-op.
    """
    cap = _s(capability).upper()
    if cap not in CAPABILITIES:
        return {"state": "UNKNOWN CAPABILITY", "available": False,
                "capability": cap,
                "why": ("'" + cap + "' is not a capability this factory "
                        "knows. It is unknown, which is a different "
                        "problem from unavailable.")}
    if cap not in MVP_CAPABILITIES:
        keys = CAPABILITY_KEYS.get(cap, ())
        if not any(_key_present(k) for k in keys):
            return {"state": "NOT IN MVP", "available": False,
                    "capability": cap,
                    "why": ("this capability is planned but not part of "
                            "the MVP, and no provider is configured for "
                            "it. Section 38 starts with text and images.")}
    keys = CAPABILITY_KEYS.get(cap, ())
    present = [k for k in keys if _key_present(k)]
    if not present:
        return {"state": "UNAVAILABLE", "available": False,
                "capability": cap,
                "candidates": list(keys),
                "why": ("no provider is configured for " + cap
                        + ". Set one of " + ", ".join(keys)
                        + " on the Connect board. The factory will not "
                        "fake an asset.")}
    return {"state": "AVAILABLE", "available": True, "capability": cap,
            "provider_key": present[0],
            "why": cap + " is served by the provider behind "
                   + present[0]}


def tool_matrix() -> List[Dict[str, Any]]:
    """Every capability and its real state, for the Settings screen."""
    return [dict(route_tool(c), mvp=c in MVP_CAPABILITIES)
            for c in CAPABILITIES]


# ===========================================================================
# 52-53. QA. The agent judges; these validators do not.
# ===========================================================================
QA_STATES = ("PASS", "WARNING", "FAIL")

#: Section 52 says the QA agent CAN CALL deterministic validators. These
#: are those validators. "Is there a CTA block" is not a judgement and
#: must not cost a token or vary between runs.
CLAIM_PATTERN = re.compile(
    r"(\b\d{1,3}(?:[.,]\d+)?\s?%|\b\d+x\b|\bguarantee\w*\b|\bbest\b|"
    r"\bnumber one\b|\b#1\b|\bfastest\b|\bcheapest\b|\bproven\b)",
    re.I)

URL_PATTERN = re.compile(r"https?://[^\s\)\]\"']+")


def validate_required_blocks(blocks, channel) -> Dict[str, Any]:
    want = CHANNEL_BLOCKS.get(_s(channel).upper())
    if not want:
        return {"check": "required_blocks", "state": "WARNING",
                "why": ("no block requirements are recorded for channel '"
                        + _s(channel) + "', so this was not checked")}
    have = {_d(b).get("type") for b in _l(blocks)}
    missing = [w for w in want if w not in have]
    return {"check": "required_blocks",
            "state": "FAIL" if missing else "PASS",
            "missing": missing,
            "why": ("missing " + ", ".join(missing)) if missing
            else "every block this channel requires is present"}


def validate_cta(blocks) -> Dict[str, Any]:
    ctas = [b for b in _l(blocks) if _d(b).get("type") == "CTA"
            and _s(_d(b).get("text")).strip()]
    return {"check": "cta", "state": "PASS" if ctas else "FAIL",
            "why": ("a CTA block is present and non-empty" if ctas
                    else "there is no CTA, so the reader is not asked "
                         "to do anything")}


def validate_claims(blocks) -> Dict[str, Any]:
    """Section 53. Find claims; do NOT decide whether they are true.

    A number in marketing copy either has a source or it does not, and
    that is checkable. Whether the source is good is a human call, so
    this returns WARNING and names the phrase rather than a verdict.
    """
    found = []
    for b in _l(blocks):
        d = _d(b)
        for m in CLAIM_PATTERN.finditer(_s(d.get("text"))):
            if not d.get("evidence_ref"):
                found.append({"block": d.get("id"), "phrase": m.group(0)})
    return {"check": "claims",
            "state": "WARNING" if found else "PASS",
            "claims": found,
            "why": (str(len(found)) + " claim(s) carry no cited source: "
                    + ", ".join(sorted({c["phrase"] for c in found}))
                    if found else "no unsourced claim found")}


def validate_links(blocks) -> Dict[str, Any]:
    urls = []
    for b in _l(blocks):
        urls.extend(URL_PATTERN.findall(_s(_d(b).get("text"))))
    bad = [u for u in urls if u.endswith((".", ",")) or " " in u]
    return {"check": "links",
            "state": "WARNING" if bad else "PASS",
            "urls": urls, "suspect": bad,
            "why": (str(len(bad)) + " link(s) look malformed" if bad
                    else (str(len(urls)) + " link(s), none malformed. "
                          "Whether they resolve is not checked here; "
                          "that needs a network call."))}


def validate_assets(blocks, assets) -> Dict[str, Any]:
    need = [b for b in _l(blocks)
            if _d(b).get("type") in ("IMAGE", "VIDEO")]
    have = {_s(_d(a).get("id")) for a in _l(assets)}
    missing = [_d(b).get("id") for b in need
               if _s(_d(b).get("asset_id")) not in have]
    return {"check": "assets",
            "state": "FAIL" if missing else "PASS",
            "missing": missing,
            "why": (str(len(missing)) + " media block(s) reference no "
                    "stored asset" if missing
                    else "every media block points at a stored asset")}


DETERMINISTIC_CHECKS = ("required_blocks", "cta", "claims", "links",
                        "assets")


def run_validators(blocks, *, channel="", assets=()) -> List[Dict]:
    """All deterministic checks. No model, no cost, same answer twice."""
    return [validate_required_blocks(blocks, channel),
            validate_cta(blocks),
            validate_claims(blocks),
            validate_links(blocks),
            validate_assets(blocks, assets)]


def qa_verdict(checks) -> Dict[str, Any]:
    """Roll checks into one state. FAIL beats WARNING beats PASS."""
    rows = _l(checks)
    if not rows:
        return {"state": "WARNING", "why": "nothing was checked"}
    states = [_s(_d(c).get("state")).upper() for c in rows]
    state = ("FAIL" if "FAIL" in states
             else "WARNING" if "WARNING" in states else "PASS")
    bad = [_d(c) for c in rows
           if _s(_d(c).get("state")).upper() in ("FAIL", "WARNING")]
    return {"state": state, "checks": rows,
            "blocking": [c for c in bad
                         if _s(c.get("state")).upper() == "FAIL"],
            "why": ("every check passed" if state == "PASS"
                    else "; ".join(_s(c.get("why")) for c in bad)[:400])}


# ===========================================================================
# 56-60. DISTRIBUTION. The factory hands off; it does not execute.
# ===========================================================================
#: Section 106, the golden boundary. Which OS owns execution for each
#: channel. The factory supplies the creative and NOTHING else: not the
#: audience, not the budget, not the bid, not the send time.
DESTINATIONS = {
    "LINKEDIN": ("SOCIAL_PUBLISHER", "organic social publishing"),
    "INSTAGRAM": ("SOCIAL_PUBLISHER", "organic social publishing"),
    "TIKTOK": ("SOCIAL_PUBLISHER", "organic social publishing"),
    "YOUTUBE": ("SOCIAL_PUBLISHER", "organic social publishing"),
    "X": ("SOCIAL_PUBLISHER", "organic social publishing"),
    "META_PAID": ("MEDIA_BUYING_OS",
                  "audience, budget, bid, placement and launch"),
    "GOOGLE_PAID": ("MEDIA_BUYING_OS",
                    "audience, budget, bid, placement and launch"),
    "BLOG": ("SEO_OS", "CMS execution and crawler verification"),
    "EMAIL": ("EMAIL_OS", "list, flow, send time and sending"),
}

PACKAGE_STATES = ("READY", "SENT", "SCHEDULED", "PUBLISHED", "FAILED",
                  "REJECTED")


def build_package(variant, *, master_id="", approval=None,
                  assets=(), tracking=None) -> Dict[str, Any]:
    """Section 57. The package the factory hands to an execution OS.

    Refuses to build for unapproved content. A package IS the handoff:
    once it leaves, another system may spend money on it, and "it was
    only a draft" is not recoverable at that point.
    """
    v = _d(variant)
    ch = _s(v.get("channel")).upper()
    dest = DESTINATIONS.get(ch)
    if dest is None:
        return {"state": "REJECTED", "ok": False,
                "why": ("no destination system is registered for channel "
                        "'" + ch + "'. The factory will not guess which "
                        "OS should execute it.")}
    ap = _d(approval)
    if _s(v.get("status")).upper() != "APPROVED":
        return {"state": "REJECTED", "ok": False,
                "why": ("this variant is " + _s(v.get("status"))
                        + ", not APPROVED. Handing off unapproved content "
                        "lets another system spend money on it.")}
    if not _s(ap.get("approved_by")).strip():
        return {"state": "REJECTED", "ok": False,
                "why": ("the approval names nobody. Section 79 requires "
                        "an actor on every meaningful action.")}
    return {
        "state": "READY", "ok": True,
        "master_content_id": _s(master_id),
        "variant_id": _s(v.get("id")),
        "destination_system": dest[0],
        "destination_owns": dest[1],
        "channel": ch,
        "format": _s(v.get("format")).upper(),
        "copy": {_s(_d(b).get("type")): _s(_d(b).get("text"))
                 for b in _l(v.get("content_blocks"))},
        "assets": [_d(a) for a in _l(assets)],
        "cta": _d(v.get("cta")),
        "landing_page": v.get("destination_url"),
        "tracking": _d(tracking),
        "metadata": {"paid_or_organic": _s(v.get("paid_or_organic")).upper()},
        "approval": {"approved_by": _s(ap.get("approved_by")),
                     "approved_at": _s(ap.get("approved_at"))},
        "why": ("ready for " + dest[0] + ", which owns " + dest[1]),
    }


def receive_handoff_result(pkg, result) -> Dict[str, Any]:
    """What the execution OS said back. ACCEPTED is not PUBLISHED."""
    r = _d(result)
    state = _s(r.get("state") or r.get("status")).upper()
    if state not in PACKAGE_STATES and state != "ACCEPTED":
        return {"state": "FAILED",
                "why": ("the destination returned '" + state + "', which "
                        "is not a state this contract defines")}
    return {"state": "SENT" if state == "ACCEPTED" else state,
            "external_object_id": r.get("external_object_id")
            or r.get("external_id"),
            "why": (r.get("reason") or
                    ("accepted by the destination; it is not published "
                     "until the destination says so"
                     if state == "ACCEPTED" else _s(state).lower()))}


# ===========================================================================
# 63-67, 70-71. PERFORMANCE, CLASSIFICATION, LEARNING
# ===========================================================================
PERF_FIELDS = ("date", "content_variant_id", "source_system", "platform",
               "impressions", "reach", "views", "engagements", "clicks",
               "sessions", "leads", "conversions", "revenue", "spend",
               "raw_metrics_json", "freshness")

#: Section 66. The MVP attribute set. Stored, not inferred on every read
#: (section 65), because an attribute an AI re-guesses each time is not
#: a fact you can group by.
ATTRIBUTES = ("topic", "format", "hook", "angle", "audience", "cta",
              "paid_or_organic", "channel")

RESULTS = ("WINNER", "STRONG", "NORMAL", "WEAK", "INSUFFICIENT_DATA")

#: A classification needs a target metric, a baseline and a floor. All
#: three, section 70. Below the floor the answer is INSUFFICIENT_DATA and
#: never NORMAL: too few to tell is not the same as no effect.
MIN_SAMPLE = {"impressions": 1000, "clicks": 100, "conversions": 30,
              "engagements": 200, "reach": 1000, "sessions": 100}

#: How far from baseline each band starts, as a ratio of the baseline.
BANDS = (("WINNER", 1.5), ("STRONG", 1.15), ("NORMAL", 0.85),
         ("WEAK", 0.0))


def normalize_performance(row) -> Dict[str, Any]:
    """One inbound performance row, in the shape section 64 defines."""
    d = _d(row)
    metrics = _d(d.get("metrics")) or d
    out = {k: None for k in PERF_FIELDS}
    out["content_variant_id"] = d.get("content_variant_id")
    out["source_system"] = _s(d.get("source_system")).upper() or "UNKNOWN"
    out["platform"] = d.get("platform")
    out["date"] = d.get("date") or d.get("period")
    for k in ("impressions", "reach", "views", "engagements", "clicks",
              "sessions", "leads", "conversions", "revenue", "spend"):
        out[k] = _f(metrics.get(k))
    out["raw_metrics_json"] = metrics
    out["freshness"] = d.get("freshness") or d.get("received_at")
    return out


def rate(numerator, denominator) -> Optional[float]:
    """SUM over SUM. None when there is no denominator, never 0.0.

    "No impressions" is not "a click-through rate of nought", and a zero
    there would drag every average that touches it.
    """
    n, dd = _f(numerator, 0) or 0, _f(denominator, 0) or 0
    return (n / dd) if dd else None


def aggregate(rows) -> Dict[str, Any]:
    """Totals for a set of daily rows. Ratios computed AFTER summing."""
    r = [_d(x) for x in _l(rows)]
    if not r:
        return {}
    out = {}
    for k in ("impressions", "reach", "views", "engagements", "clicks",
              "sessions", "leads", "conversions", "revenue", "spend"):
        vals = [_f(x.get(k)) for x in r if _f(x.get(k)) is not None]
        out[k] = sum(vals) if vals else None
    out["ctr"] = rate(out.get("clicks"), out.get("impressions"))
    out["cvr"] = rate(out.get("conversions"), out.get("clicks"))
    out["roas"] = rate(out.get("revenue"), out.get("spend"))
    out["days"] = len(r)
    return out


def classify_result(totals, *, metric, baseline) -> Dict[str, Any]:
    """Section 70. WINNER is earned, not asserted.

    Requires the target metric, a baseline to beat and enough sample.
    Any one of them missing returns INSUFFICIENT_DATA with the reason,
    because "we could not tell" is a finding and "average" is a claim.
    """
    t = _d(totals)
    m = _s(metric)
    val = _f(t.get(m))
    if val is None:
        return {"result": "INSUFFICIENT_DATA", "metric": m,
                "why": ("'" + m + "' was not measured for this content, "
                        "so there is nothing to classify")}
    base = _f(baseline)
    if base is None or base <= 0:
        return {"result": "INSUFFICIENT_DATA", "metric": m, "value": val,
                "why": ("no baseline to compare against. A number with "
                        "nothing to beat is not a result.")}
    floor_key = m if m in MIN_SAMPLE else ("impressions" if t.get(
        "impressions") is not None else None)
    if floor_key:
        seen = _f(t.get(floor_key), 0) or 0
        need = MIN_SAMPLE[floor_key]
        if seen < need:
            return {"result": "INSUFFICIENT_DATA", "metric": m,
                    "value": val, "sample": seen, "need": need,
                    "why": (str(int(seen)) + " " + floor_key + " is below "
                            "the " + str(need) + " this comparison needs. "
                            "NOT 'average': too few to tell.")}
    ratio = val / base
    for name, edge in BANDS:
        if ratio >= edge:
            return {"result": name, "metric": m, "value": val,
                    "baseline": base, "ratio": round(ratio, 3),
                    "why": (m + " of " + str(round(val, 4)) + " against a "
                            "baseline of " + str(round(base, 4)) + ", "
                            + str(round(ratio * 100)) + "% of baseline")}
    return {"result": "WEAK", "metric": m, "value": val, "baseline": base,
            "why": "below every band"}


def make_learning(*, attribute_type, attribute_value, channel, metric,
                  values, baseline, context="") -> Dict[str, Any]:
    """Section 67. One learning record, with its sample size on its face.

    A learning built on three creatives and one built on eighty are not
    the same claim, and a store that does not carry sample size lets the
    first masquerade as the second forever.
    """
    vals = [v for v in (_f(x) for x in _l(values)) if v is not None]
    n = len(vals)
    if n == 0:
        return {"status": "REJECTED",
                "why": "no measured values, so there is nothing to learn"}
    avg = sum(vals) / n
    base = _f(baseline)
    conf = ("LOW" if n < 5 else "MEDIUM" if n < 15 else "HIGH")
    return {
        "id": _id(attribute_type, attribute_value, channel, metric),
        "attribute_type": _s(attribute_type).upper(),
        "attribute_value": _s(attribute_value),
        "channel": _s(channel).upper(),
        "context": _s(context),
        "metric": _s(metric),
        "performance_value": round(avg, 4),
        "baseline": base,
        "lift": (round((avg / base - 1) * 100, 1)
                 if base not in (None, 0) else None),
        "sample_size": n,
        "confidence": conf,
        "status": "ACTIVE",
        "why": (str(n) + " measured item(s), average " + _s(metric)
                + " " + str(round(avg, 4))
                + ("" if base in (None, 0) else
                   ", baseline " + str(round(base, 4)))
                + ". Confidence " + conf + " from sample size alone; no "
                "significance test is claimed."),
    }


# ===========================================================================
# 78-79. PERMISSIONS AND AUDIT
# ===========================================================================
ROLES = ("OWNER", "ADMIN", "EDITOR", "CREATOR", "REVIEWER", "VIEWER")

PERMISSIONS = ("CREATE_CONTENT", "EDIT_CONTENT", "GENERATE_ASSET",
               "REVIEW_CONTENT", "APPROVE_CONTENT", "DISTRIBUTE_CONTENT",
               "MANAGE_BRAND", "MANAGE_TOOLS")

ROLE_GRANTS = {
    "OWNER": PERMISSIONS,
    "ADMIN": PERMISSIONS,
    "EDITOR": ("CREATE_CONTENT", "EDIT_CONTENT", "GENERATE_ASSET",
               "REVIEW_CONTENT", "APPROVE_CONTENT", "DISTRIBUTE_CONTENT"),
    "CREATOR": ("CREATE_CONTENT", "EDIT_CONTENT", "GENERATE_ASSET"),
    "REVIEWER": ("REVIEW_CONTENT", "APPROVE_CONTENT"),
    "VIEWER": (),
}


def can(role, permission) -> bool:
    return _s(permission).upper() in ROLE_GRANTS.get(_s(role).upper(), ())


def audit(actor, actor_type, content, action, *, before=None, after=None,
          tool="", reason="", at="") -> Dict[str, Any]:
    """Section 79. Every meaningful action, with who and what changed."""
    return {"id": _id(actor, action, content, at),
            "actor": _s(actor), "actor_type": _s(actor_type).upper(),
            "content": _s(content), "action": _s(action).upper(),
            "before": before, "after": after, "tool": _s(tool),
            "reason": _s(reason), "timestamp": _s(at)}


# ===========================================================================
# 87. THE MINIMUM DATABASE
# ===========================================================================
TABLES = ("brands", "content_signals", "content_plans",
          "content_plan_items", "master_content", "content_variants",
          "content_blocks", "content_versions", "assets", "asset_versions",
          "comments", "content_locks", "qa_reviews", "approval_requests",
          "distribution_packages", "content_performance_daily",
          "content_learning", "agent_runs", "tool_runs", "audit_logs")


# ===========================================================================
# 107. THE GOLDEN LINEAGE RULE
# ===========================================================================
LINEAGE = ("source_signal", "plan", "master_content", "variant", "asset",
           "approval", "distribution", "external_object", "performance",
           "learning")


def lineage(chain) -> Dict[str, Any]:
    """Section 107. Every content item must be traceable end to end.

    A break is not a warning to bury in a log: if a link is missing, a
    result cannot be attributed to the decision that caused it, and the
    learning built on it is about nothing.
    """
    c = _d(chain)
    have = [k for k in LINEAGE if c.get(k)]
    missing = [k for k in LINEAGE if not c.get(k)]
    first_gap = missing[0] if missing else None
    return {"complete": not missing,
            "have": have, "missing": missing,
            "broken_at": first_gap,
            "why": ("every link is present, so this content can be traced "
                    "from the signal that caused it to the learning it "
                    "produced" if not missing else
                    "the chain stops at '" + _s(first_gap) + "'. Anything "
                    "after that point cannot be attributed to the "
                    "decision that caused it.")}


# ===========================================================================
# 110. THE GOLDEN LOOP RULE
# ===========================================================================
#: Published is not done. The loop closes only when a result has been
#: classified and a learning has been used in a later plan.
LOOP_STAGES = ("SIGNAL", "PLAN", "CONTENT", "APPROVED", "DISTRIBUTED",
               "PERFORMANCE", "CLASSIFIED", "LEARNING", "REPLANNED")


def loop_state(counts) -> Dict[str, Any]:
    """Where work sits, and whether the loop has ever actually closed."""
    c = _d(counts)
    at = [(s, int(_f(c.get(s), 0) or 0)) for s in LOOP_STAGES]
    total = sum(n for _s2, n in at)
    closed = int(_f(c.get("REPLANNED"), 0) or 0)
    if total == 0:
        return {"state": "NEVER RUN", "stages": at, "closed": 0,
                "why": ("nothing has entered the factory. That is not the "
                        "same as nothing needing to be made.")}
    worst = max(at, key=lambda z: z[1])
    if closed == 0:
        return {"state": "NOT YET CLOSED", "stages": at, "closed": 0,
                "bottleneck": worst[0],
                "why": (str(total) + " item(s) are moving and NOT ONE has "
                        "produced a learning that reached the planner. "
                        "Until one does this is a content generator, not "
                        "a factory. Most work sits at: " + worst[0])}
    return {"state": "CLOSING", "stages": at, "closed": closed,
            "bottleneck": worst[0] if worst[1] else None,
            "why": (str(closed) + " item(s) have completed the full loop "
                    "and fed the planner.")}
