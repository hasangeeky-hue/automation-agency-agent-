"""
content_engine_os_content.py
============================================================================
ENGINE 5: TEMPLATES, THE RENDERER, AND THE ONE RESOLVER.

TWO JOBS IN ONE FILE, ON PURPOSE
  1. A structured email document (blocks) rendered to email-safe HTML, and
     versioned so a published template is never overwritten.
  2. resolve_email(): the single function that answers "what exactly will
     this person receive at this step". Both the preview and the sender
     call it. That is the whole point of it being here.

WHY resolve_email() MOVED
  It used to be a private function inside the API module, so the preview
  screen could not reach it and read fields off the payload that no job
  carries. Every campaign therefore previewed as empty while the sender
  worked fine, which is the defect that made the last build a dummy show.
  It now has one home. content_engine_api.py imports it. The rule the file
  enforces: WHAT YOU PREVIEW IS WHAT SENDS, byte for byte.

BLOCKS, NOT FREE HTML
  An agent returns a structured document. The renderer turns it into
  table-based, inline-styled, Outlook-safe HTML. Letting a model emit raw
  HTML directly is how an editor becomes unmaintainable and a layout
  becomes unpredictable.

RENDERER ONLY. Nothing here sends, queues or fetches.
============================================================================
"""

from __future__ import annotations

import html as _html
import re

from content_engine_os_core import _D, _L, now, rid

BLOCK_TYPES = ("heading", "text", "image", "button", "divider", "spacer",
               "social", "product", "footer")

#: The tokens a template may personalise with. Anything else is reported by
#: the preview as an unknown token rather than silently rendered empty.
KNOWN_TOKENS = ("first_name", "last_name", "name", "company", "job_title",
                "city", "country", "website", "industry", "booking_url",
                "unsubscribe_url", "sender_name")

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


# ---------------------------------------------------------------------------
# THE RESOLVER. One definition, two callers.
# ---------------------------------------------------------------------------
def resolve_email(job, email, touch=1):
    """(lead, qual, subject, body) for one recipient at one sequence step.

    1 = intro, 2 = bump, 3 = final. A manual edit saved against this exact
    (email, touch) wins over anything the agent generated, because the
    founder correcting a sentence must be what leaves the building.

    This is the engine's ONLY answer to "what does this person get", and it
    is deliberately pure: it reads the job and returns text. It does not
    send, stamp or store.
    """
    job = _D(job)
    p = _D(job.get("payload"))
    em = str(email or "").strip().lower()
    leads = _L(p.get("leads"))
    lead = next((L for L in leads
                 if str(_D(L).get("email") or "").strip().lower() == em), None)
    if not lead:
        return None
    qmap = {str(_D(r).get("id", "")).lower(): r
            for r in _L(_D(p.get("lead_qualifier")).get("results"))}
    q = qmap.get(em) or {}
    import content_engine_connectors as C
    oc = _D(p.get("outreach_copy"))
    base_subj = (_L(oc.get("subject_variants"))
                 or ["Quick idea for {{company}}"])[0]
    # An edit can be saved against ANY touch. Edits keyed by email alone are
    # legacy and only apply to touch 1.
    edits = _D(p.get("email_edits"))
    edit = edits.get(f"{em}|{int(touch)}") or (edits.get(em)
                                               if int(touch) <= 1 else None)
    if edit and _D(edit).get("body"):
        return (lead, q, _D(edit).get("subject") or "", _D(edit).get("body") or "")
    return (lead, q) + C.outreach_touch(lead, q, base_subj, oc.get("body", ""),
                                        touch, oc)


def rendered_message(job, email, touch=1) -> dict:
    """The resolved email PLUS the branded HTML the recipient really sees.

    compose_outreach() is the sender's own renderer (signature, address,
    unsubscribe, logo). Calling it here is what makes the preview honest:
    the screen shows the same bytes the transport is handed, not a
    reconstruction of them."""
    got = resolve_email(job, email, touch)
    if not got:
        return {"ok": False,
                "error": "that address is not a lead on this campaign"}
    lead, qual, subject, body = got
    plain, html = body, ""
    try:
        import content_engine_connectors as C
        plain, html = C.Emailer().compose_outreach(body, job)
    except Exception as ex:                     # a broken mailer config must
        html = ""                               # not blank the preview
        _note = str(ex)
    edits = _D(_D(job.get("payload")).get("email_edits"))
    return {"ok": True, "subject": subject, "body": body,
            "plain": plain, "html": html, "lead": lead, "qual": qual,
            "touch": int(touch),
            "edited": bool(edits.get(f"{str(email).lower()}|{int(touch)}")
                           or (int(touch) == 1 and edits.get(str(email).lower())))}


# ---------------------------------------------------------------------------
# THE BLOCK RENDERER
# ---------------------------------------------------------------------------
_WRAP = ("<table role='presentation' width='100%' cellpadding='0' "
         "cellspacing='0' style='background:#f4f5f7;padding:24px 0'>"
         "<tr><td align='center'>"
         "<table role='presentation' width='600' cellpadding='0' "
         "cellspacing='0' style='width:600px;max-width:100%;background:#fff;"
         "border-radius:8px;font-family:-apple-system,Segoe UI,Helvetica,"
         "Arial,sans-serif;color:#1a1d21'>")
_WRAP_END = "</table></td></tr></table>"


def render_block(b) -> str:
    """One block to email-safe HTML. Tables and inline styles only: Outlook
    ignores most of a stylesheet and every float you were counting on."""
    b = _D(b)
    t = b.get("type")
    pad = "padding:8px 32px"
    if t == "heading":
        lvl = int(b.get("level") or 2)
        size = {1: 28, 2: 22, 3: 18}.get(lvl, 22)
        return (f"<tr><td style='{pad};padding-top:24px'>"
                f"<div style='font-size:{size}px;font-weight:700;"
                f"line-height:1.25'>{e(b.get('content'))}</div></td></tr>")
    if t == "text":
        return (f"<tr><td style='{pad};font-size:15px;line-height:1.6;"
                f"color:#33383d'>"
                + "".join(f"<p style='margin:0 0 12px'>{e(par)}</p>"
                          for par in str(b.get("content") or "").split("\n\n"))
                + "</td></tr>")
    if t == "image":
        alt = e(b.get("alt") or "")
        return (f"<tr><td style='{pad}'><img src='{e(b.get('url'))}' "
                f"alt='{alt}' width='536' style='width:100%;max-width:536px;"
                f"display:block;border:0'></td></tr>")
    if t == "button":
        return (f"<tr><td style='{pad};padding-top:16px;padding-bottom:16px'>"
                f"<table role='presentation' cellpadding='0' cellspacing='0'>"
                f"<tr><td style='background:{e(b.get('color') or '#2f6bff')};"
                f"border-radius:6px'>"
                f"<a href='{e(b.get('url'))}' style='display:inline-block;"
                f"padding:12px 24px;color:#fff;text-decoration:none;"
                f"font-weight:600;font-size:15px'>{e(b.get('label'))}</a>"
                f"</td></tr></table></td></tr>")
    if t == "divider":
        return (f"<tr><td style='{pad}'><div style='height:1px;"
                f"background:#e3e6ea'></div></td></tr>")
    if t == "spacer":
        return (f"<tr><td style='height:{int(b.get('height') or 24)}px'>"
                f"&nbsp;</td></tr>")
    if t == "social":
        links = "".join(
            f"<a href='{e(_D(s).get('url'))}' style='color:#5a626b;"
            f"text-decoration:none;margin-right:12px;font-size:13px'>"
            f"{e(_D(s).get('label'))}</a>" for s in _L(b.get("items")))
        return f"<tr><td style='{pad}'>{links}</td></tr>"
    if t == "product":
        return (f"<tr><td style='{pad}'>"
                f"<div style='border:1px solid #e3e6ea;border-radius:6px;"
                f"padding:16px'><div style='font-weight:600'>"
                f"{e(b.get('title'))}</div>"
                f"<div style='font-size:14px;color:#5a626b;margin-top:4px'>"
                f"{e(b.get('description'))}</div>"
                f"<div style='margin-top:8px;font-weight:600'>"
                f"{e(b.get('price'))}</div></div></td></tr>")
    if t == "footer":
        return (f"<tr><td style='{pad};padding-top:24px;padding-bottom:24px;"
                f"font-size:12px;color:#8a9199;line-height:1.5'>"
                f"{e(b.get('content'))}<br>"
                f"<a href='{{{{unsubscribe_url}}}}' style='color:#8a9199'>"
                f"Unsubscribe</a></td></tr>")
    return ""


def render_blocks(blocks) -> str:
    body = "".join(render_block(b) for b in _L(blocks))
    if not any(_D(b).get("type") == "footer" for b in _L(blocks)):
        body += render_block({"type": "footer",
                              "content": "You are receiving this because we "
                                         "believed it would be useful."})
    return _WRAP + body + _WRAP_END


def tokens_in(*texts) -> list:
    found = []
    for t in texts:
        found += TOKEN_RE.findall(str(t or ""))
    return sorted(set(found))


def unknown_tokens(*texts) -> list:
    return [t for t in tokens_in(*texts) if t.split(".")[0] not in KNOWN_TOKENS]


# ---------------------------------------------------------------------------
# TEMPLATES AND VERSIONS
# ---------------------------------------------------------------------------
def save_template(repo, name, *, blocks=None, html="", subject="",
                  preview_text="", publish=False) -> dict:
    """Save a draft, or publish a version.

    A PUBLISHED VERSION IS NEVER OVERWRITTEN. Publishing appends. A campaign
    that went out on version 3 must still be readable after version 4 is
    written, or the record of what you sent is a guess."""
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "error": "a template needs a name"}
    tid = rid("tpl", repo.ws, nm.lower())
    body = html or render_blocks(blocks)
    cur = repo.one("templates", tid) or {"id": tid, "name": nm, "version": 0}
    rec = dict(cur)
    rec.update({"name": nm, "subject": subject, "preview_text": preview_text,
                "blocks": _L(blocks), "html": body})
    if publish:
        v = int(cur.get("version") or 0) + 1
        rec["version"] = v
        rec["published_at"] = now()
        repo.put("template_versions", {
            "id": rid("tplv", repo.ws, tid, v), "template_id": tid,
            "version": v, "subject": subject, "preview_text": preview_text,
            "blocks": _L(blocks), "html": body, "published_at": now()})
    out = repo.put("templates", rec)
    return {"ok": True, "id": out["id"], "version": out.get("version", 0),
            "message": (f"{nm!r} published as version {out.get('version')}"
                        if publish else f"{nm!r} saved as a draft")}


def template_rows(repo) -> list:
    vers = {}
    for v in repo.all("template_versions"):
        vers[v.get("template_id")] = vers.get(v.get("template_id"), 0) + 1
    return [{"id": t.get("id"), "name": t.get("name"),
             "subject": t.get("subject", ""),
             "version": t.get("version", 0),
             "versions": vers.get(t.get("id"), 0),
             "blocks": len(_L(t.get("blocks"))),
             "published_at": t.get("published_at", ""),
             "updated_at": t.get("updated_at", "")}
            for t in repo.all("templates")]


def from_agent(doc) -> dict:
    """Accept an agent's structured email document and keep only what the
    renderer understands. A model that invents a block type gets it dropped
    with a note, never rendered as raw markup."""
    doc = _D(doc)
    kept, refused = [], []
    for b in _L(doc.get("blocks")):
        if _D(b).get("type") in BLOCK_TYPES:
            kept.append(b)
        else:
            refused.append(_D(b).get("type"))
    return {"subject": doc.get("subject", ""),
            "preview_text": doc.get("preview_text", ""),
            "blocks": kept, "refused": refused,
            "confidence": doc.get("confidence")}
