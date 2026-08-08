"""
content_engine_os_bounce.py
============================================================================
READING BOUNCES OUT OF THE MAILBOX, BECAUSE SMTP HAS NO WEBHOOK.

WHY THIS EXISTS
  Delivered and bounced were blank on every screen, and the honest reason
  was that SMTP tells you nothing: a Gmail relay accepts the message and
  the failure arrives later, as an email, in the same mailbox everything
  else lands in. An ESP would post a webhook. You do not have an ESP, you
  have a mailbox, and the mailbox already knows.

WHAT A BOUNCE LOOKS LIKE
  A delivery status notification: From a mailer-daemon or postmaster, with
  a message/delivery-status part carrying Action: failed and a Status code.
  The first digit of that code is the whole decision:

      5.x.x   permanent. The address is wrong or gone. Suppress it.
      4.x.x   temporary. A full mailbox, a greylist, a server that was
              down. Record it and do NOT suppress: throwing away a real
              prospect because their server was busy on Tuesday is the
              expensive mistake.

  Some servers send neither, so there is a last-resort text scan. It only
  ever produces a SOFT bounce: guessing "permanent" from prose is how a
  good address gets suppressed for ever.

IDEMPOTENT BY THE MESSAGE ID
  Every notification carries its own Message-ID. The event key is derived
  from it, so re-reading the same mailbox writes nothing twice.

READ ONLY. Nothing here sends, and nothing marks your mail as read.
============================================================================
"""

from __future__ import annotations

import email
import logging
import re

import content_engine_os_core as CORE
from content_engine_os_core import _D, _L, norm_email, now

log = logging.getLogger("content_engine.os.bounce")

#: Who a bounce comes from. Matched loosely on purpose: every provider
#: spells its daemon differently and none of them are worth a table.
DAEMONS = ("mailer-daemon", "postmaster", "mail delivery",
           "delivery status", "returned mail", "delivery has failed",
           "undeliverable", "delivery incomplete")

STATUS_RE = re.compile(r"^\s*status:\s*([245])\.(\d+)\.(\d+)", re.I | re.M)
ACTION_RE = re.compile(r"^\s*action:\s*(failed|delayed|delivered)", re.I | re.M)
FINAL_RE = re.compile(r"^\s*final-recipient:\s*[^;]*;\s*(\S+)", re.I | re.M)
ORIG_RE = re.compile(r"^\s*original-recipient:\s*[^;]*;\s*(\S+)", re.I | re.M)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

#: Phrases that mean "gone", used ONLY to decide the reason shown to a
#: human. They never upgrade a soft bounce to a hard one on their own.
HARD_WORDS = ("user unknown", "no such user", "does not exist",
              "recipient rejected", "address rejected", "invalid recipient",
              "unknown recipient", "mailbox unavailable",
              "account has been disabled", "no longer in use")
SOFT_WORDS = ("quota", "mailbox full", "over quota", "temporarily",
              "try again", "greylist", "deferred", "timed out",
              "connection refused", "too many")

SEEN_KEY = "os_bounce_seen"


def classify(text) -> tuple:
    """(kind, code, why). kind is "hard", "soft" or "".

    The DSN status code decides. Prose is used only to name the reason,
    because a server that says "user unknown" inside a 4.x.x code is a
    server having a bad day, not an address that has gone."""
    t = str(text or "")
    low = t.lower()
    m = STATUS_RE.search(t)
    code = ".".join(m.groups()) if m else ""
    words = ([w for w in HARD_WORDS if w in low]
             + [w for w in SOFT_WORDS if w in low])
    why = words[0] if words else ""
    if m:
        kind = "hard" if m.group(1) == "5" else "soft"
        return kind, code, (why or ("permanent refusal" if kind == "hard"
                                    else "a temporary failure"))
    if ACTION_RE.search(t) or any(d in low for d in DAEMONS):
        # No code. SOFT, deliberately: guessing permanence from prose is
        # how a good address is suppressed for ever.
        return "soft", "", (why or "a failure with no status code, so it is "
                                   "treated as temporary")
    return "", "", ""


def recipient_of(msg, body) -> str:
    """Who the bounce is about, which is never the From of the bounce."""
    for part in msg.walk() if hasattr(msg, "walk") else []:
        if part.get_content_type() in ("message/delivery-status",
                                       "text/rfc822-headers"):
            raw = _part_text(part)
            for rx in (FINAL_RE, ORIG_RE):
                hit = rx.search(raw)
                if hit:
                    return norm_email(hit.group(1).strip("<>"))
    for rx in (FINAL_RE, ORIG_RE):
        hit = rx.search(body)
        if hit:
            return norm_email(hit.group(1).strip("<>"))
    mine = norm_email(_env("IMAP_USER") or _env("EMAIL_FROM"))
    for cand in EMAIL_RE.findall(body):
        em = norm_email(cand)
        if em != mine and not any(d in em for d in ("mailer-daemon",
                                                    "postmaster")):
            return em
    return ""


def _env(k, d=""):
    try:
        import content_engine_connectors as C
        return C._env(k, d)
    except Exception:
        import os
        return os.environ.get(k, d)


def _part_text(part) -> str:
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return str(part.get_payload())
        return payload.decode(part.get_content_charset() or "utf-8",
                              "replace")
    except Exception:
        return ""


def flatten(msg) -> str:
    if not hasattr(msg, "walk"):
        return str(msg)
    out = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        out.append(_part_text(part))
    return "\n".join(out)


def is_bounce(msg) -> bool:
    frm = str(msg.get("From", "")).lower()
    subj = str(msg.get("Subject", "")).lower()
    ctype = str(msg.get_content_type() or "").lower()
    return (ctype == "multipart/report"
            or any(d in frm for d in DAEMONS)
            or any(d in subj for d in DAEMONS))


def fetch(limit=100) -> list:
    """Raw messages from the mailbox. Read only: nothing is marked seen,
    nothing is deleted, and the reply agent's own pass is unaffected."""
    host, user, pw = _env("IMAP_HOST"), _env("IMAP_USER"), _env("IMAP_PASSWORD")
    if not (host and user and pw):
        return []
    import imaplib
    out = []
    try:
        box = imaplib.IMAP4_SSL(host, int(_env("IMAP_PORT", "993") or 993))
        box.login(user, pw)
        box.select(_env("IMAP_FOLDER", "INBOX"), readonly=True)
        ok, data = box.search(None, "ALL")
        ids = (data[0].split() if ok and data and data[0] else [])[-limit:]
        for i in ids:
            ok, raw = box.fetch(i, "(RFC822)")
            if ok and raw and raw[0]:
                out.append(email.message_from_bytes(raw[0][1]))
        box.close()
        box.logout()
    except Exception as ex:
        log.error("bounce read failed: %s", ex)
    return out


def read(store, repo, *, limit=100) -> dict:
    """Read the mailbox, record what bounced, suppress only what is gone.

    A hard bounce suppresses. A soft bounce is recorded as an event and
    left alone: if the same address bounces softly SOFT_LIMIT times it is
    rested rather than suppressed, because a mailbox that has been full for
    a month is not the same thing as an address that never existed."""
    host = _env("IMAP_HOST")
    if not host:
        return {"ok": False,
                "message": "no IMAP_HOST set, so the mailbox cannot be read; "
                           "add it on the System Map and bounces fill in "
                           "with no rebuild"}
    try:
        seen = set(_L(store.get_setting(SEEN_KEY, [])))
    except Exception:
        seen = set()
    profs = {p.get("email"): p.get("id") for p in repo.all("profiles")}
    msgs = fetch(limit)
    hard, soft, skipped, unknown = 0, 0, 0, 0
    for msg in msgs:
        mid = str(msg.get("Message-ID", "") or "")[:200]
        if not is_bounce(msg):
            continue
        if mid and mid in seen:
            skipped += 1
            continue
        body = flatten(msg)
        kind, code, why = classify(body + "\n" + str(msg.get("Subject", "")))
        if not kind:
            continue
        em = recipient_of(msg, body)
        if not em:
            unknown += 1
            continue
        if mid:
            seen.add(mid)
        pid = profs.get(em, "")
        CORE.record_event(repo, "EMAIL_BOUNCED", profile_id=pid,
                          at=str(msg.get("Date", "")) and now(),
                          metadata={"kind": kind, "code": code, "why": why,
                                    "email": em, "message_id": mid})
        if kind == "hard":
            CORE.suppress(repo, em, "BOUNCE", f"{code or 'permanent'}: {why}")
            hard += 1
        else:
            soft += 1
            _note_soft(store, repo, em, why)
    try:
        store.set_setting(SEEN_KEY, sorted(seen)[-5000:])
    except Exception:
        pass
    return {"ok": True, "read": len(msgs), "hard": hard, "soft": soft,
            "already_seen": skipped, "unattributable": unknown,
            "message": (f"{hard} permanent bounce(s) suppressed, {soft} "
                        f"temporary one(s) recorded and left alone, "
                        f"{skipped} already read"
                        + (f", {unknown} that named no recipient" if unknown
                           else ""))}


SOFT_LIMIT = 4
SOFT_KEY = "os_soft_bounces"


def _note_soft(store, repo, email_addr, why) -> None:
    """Count soft bounces. Past SOFT_LIMIT the address is RESTED, never
    suppressed: a mailbox full for a month is not an address that never
    existed, and a suppression cannot be undone without asking them."""
    try:
        counts = _D(store.get_setting(SOFT_KEY, {}))
    except Exception:
        counts = {}
    em = norm_email(email_addr)
    counts[em] = int(counts.get(em, 0)) + 1
    try:
        store.set_setting(SOFT_KEY, counts)
    except Exception:
        pass
    if counts[em] >= SOFT_LIMIT:
        CORE.rest(repo, em, 60,
                  f"{counts[em]} temporary bounces: {why}")


def summary(store, repo) -> dict:
    """What the Deliverability screen shows about bounces."""
    ev = [e_ for e_ in repo.all("email_events")
          if e_.get("event_type") == "EMAIL_BOUNCED"]
    hard = len([e_ for e_ in ev
                if _D(e_.get("metadata")).get("kind") == "hard"])
    addresses = {_D(e_.get("metadata")).get("email") for e_ in ev
                 if _D(e_.get("metadata")).get("email")}
    try:
        soft_counts = _D(store.get_setting(SOFT_KEY, {}))
    except Exception:
        soft_counts = {}
    return {"total": len(ev) or None, "addresses": len(addresses) or None,
            "hard": hard or None,
            "soft": (len(ev) - hard) or None,
            "watching": len([1 for v in soft_counts.values()
                             if 0 < int(v) < SOFT_LIMIT]) or None,
            "ready": bool(_env("IMAP_HOST")),
            "why": ("reading bounces from " + _env("IMAP_USER", "the mailbox")
                    if _env("IMAP_HOST") else
                    "set IMAP_HOST, IMAP_USER and IMAP_PASSWORD on the System "
                    "Map; the reply agent already uses them, so this turns on "
                    "with no rebuild")}
