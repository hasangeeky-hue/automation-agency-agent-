"""
content_engine_os_optin.py
============================================================================
CONSENT CAPTURE: THE SIGNUP FORM, THE CONFIRMATION, THE UNSUBSCRIBE PAGE.

DOUBLE OPT-IN, PROPERLY
  signup()  records PENDING and returns a token
  confirm() records SUBSCRIBED with when, how, from where
  unsubscribe() records UNSUBSCRIBED and suppresses in the same act

  PENDING is not a subscriber. Nothing marketing may be sent to a PENDING
  address, and the orchestrator's consent gate already refuses it. That is
  the whole point of the state existing.

WHAT IS STORED AS EVIDENCE
  The timestamp, the method, the source page and the IP. Under GDPR the
  question asked later is not "did they subscribe" but "show me". An email
  address with no record of how it arrived is not defensible, and this
  engine sells into Germany and Switzerland.

THE TOKEN
  Derived from the address and a server secret, so it can be checked
  without storing a table of live tokens, and cannot be guessed from the
  address alone. It is single purpose: a confirm token cannot unsubscribe
  and an unsubscribe token cannot confirm.

THE PAGES ARE PLAIN
  A confirmation page is read once by somebody who is mildly annoyed. It
  says what happened and nothing else.
============================================================================
"""

from __future__ import annotations

import hashlib
import hmac
import html as _html

import content_engine_os_core as CORE
from content_engine_os_core import _D, norm_email, now

SECRET_KEY = "os_optin_secret"


def _secret(store) -> bytes:
    """A per-install secret, generated once and kept in settings. Not an
    env var: this must survive a redeploy or every live confirmation link
    in somebody's inbox stops working."""
    try:
        v = store.get_setting(SECRET_KEY, "")
    except Exception:
        v = ""
    if not v:
        import os as _os
        v = hashlib.sha256(_os.urandom(32)).hexdigest()
        try:
            store.set_setting(SECRET_KEY, v)
        except Exception:
            pass
    return str(v).encode()


def token(store, email, purpose) -> str:
    return hmac.new(_secret(store),
                    f"{purpose}|{norm_email(email)}".encode(),
                    hashlib.sha256).hexdigest()[:32]


def check(store, email, purpose, tok) -> bool:
    return hmac.compare_digest(token(store, email, purpose), str(tok or ""))


def _base() -> str:
    try:
        import content_engine_connectors as C
        return (C._env("PUBLIC_BASE_URL") or C._env("ENGINE_PUBLIC_URL")
                or "").rstrip("/")
    except Exception:
        return ""


def confirm_url(store, email) -> str:
    return (f"{_base()}/subscribe/confirm?e={norm_email(email)}"
            f"&t={token(store, email, 'confirm')}")


def unsubscribe_url(store, email) -> str:
    return (f"{_base()}/unsubscribe?e={norm_email(email)}"
            f"&t={token(store, email, 'unsub')}")


# ---------------------------------------------------------------------------
def signup(store, email, *, repo=None, source="", ip="", name="",
           company="") -> dict:
    """Step one. Records PENDING and asks the sender for a confirmation.

    PENDING deliberately cannot receive marketing. If the confirmation is
    never clicked, this address stays outside every audience for ever, and
    that is the correct outcome rather than a bug."""
    import content_engine_os_store as ST
    em = norm_email(email)
    if not CORE.valid_email(em):
        return {"ok": False, "message": "that is not a valid email address"}
    repo = repo or ST.repo_for(store)
    prof = CORE.upsert_profile(repo, {"email": em, "name": name,
                                      "company": company,
                                      "source": source or "signup form"})
    cur = {c.get("email"): c for c in repo.all("consents")}.get(em)
    if _D(cur).get("status") == "SUBSCRIBED":
        return {"ok": True, "already": True, "profile_id": prof.get("id"),
                "message": "that address is already confirmed"}
    CORE.set_consent(repo, em, "PENDING", source=source or "signup form",
                     method="double opt-in", evidence=f"ip={ip} at={now()}")
    import content_engine_os_send as SEND
    sent = SEND.send_confirmation(store, repo, em, confirm_url(store, em))
    return {"ok": True, "profile_id": prof.get("id"),
            "confirm_sent": bool(sent.get("ok")),
            "message": ("check your inbox: nothing else will be sent until "
                        "you confirm"
                        if sent.get("ok") else
                        "recorded as pending, but the confirmation email "
                        "could not be sent: " + str(sent.get("message", "")))}


def confirm(store, email, tok, *, ip="") -> dict:
    """Step two. This is the moment consent exists."""
    import content_engine_os_store as ST
    em = norm_email(email)
    if not check(store, em, "confirm", tok):
        return {"ok": False, "message": "that confirmation link is not valid"}
    repo = ST.repo_for(store)
    CORE.set_consent(repo, em, "SUBSCRIBED", source="double opt-in",
                     method="confirmation link",
                     evidence=f"ip={ip} confirmed_at={now()}")
    CORE.audit(repo, em, "consent_confirmed", em, f"ip={ip}")
    return {"ok": True, "message": "confirmed"}


def unsubscribe(store, email, tok="", *, reason="link", require_token=True) -> dict:
    """The last word. Sets UNSUBSCRIBED and suppresses in the same act, so
    there is no window in which a queued email could still go out."""
    import content_engine_os_store as ST
    em = norm_email(email)
    if require_token and not check(store, em, "unsub", tok):
        return {"ok": False, "message": "that unsubscribe link is not valid"}
    repo = ST.repo_for(store)
    CORE.set_consent(repo, em, "UNSUBSCRIBED", source="unsubscribe " + reason,
                     method=reason, evidence=f"at={now()}")
    CORE.suppress(repo, em, "UNSUBSCRIBE", "asked to stop")
    n = 0
    for j in repo.all("email_jobs"):
        if (j.get("email") == em
                and j.get("status") in ("QUEUED", "PROCESSING")):
            j["status"] = "CANCELLED"
            j["error_message"] = "unsubscribed while queued"
            repo.put("email_jobs", j)
            n += 1
    CORE.record_event(repo, "EMAIL_UNSUBSCRIBED", profile_id=CORE.rid(
        "prf", repo.ws, em))
    return {"ok": True, "cancelled": n,
            "message": f"removed. {n} queued email(s) cancelled."}


# ---------------------------------------------------------------------------
# THE PUBLIC PAGES. Plain, and they never leak whether an address is known.
# ---------------------------------------------------------------------------
def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{title}</title><style>
:root{{color-scheme:light dark}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;
font:16px/1.6 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;
background:#f6f7f9;color:#1a1d21;padding:24px}}
@media(prefers-color-scheme:dark){{body{{background:#0e1116;color:#e8ecf1}}
.card{{background:#161b22;border-color:#262d38}}}}
.card{{background:#fff;border:1px solid #e3e6ea;border-radius:12px;
padding:32px;max-width:520px;width:100%}}
h1{{margin:0 0 10px;font-size:22px;line-height:1.3}}
p{{margin:0 0 12px;color:#5a626b}}
@media(prefers-color-scheme:dark){{p{{color:#98a2b0}}}}
label{{display:block;font-size:13px;margin:14px 0 4px}}
input{{width:100%;padding:10px 12px;border:1px solid #cfd5dc;border-radius:8px;
font-size:15px;background:transparent;color:inherit}}
button{{margin-top:16px;padding:11px 20px;border:0;border-radius:8px;
background:#2f6bff;color:#fff;font-size:15px;font-weight:600;cursor:pointer}}
small{{color:#8a9199;font-size:12.5px}}
</style></head><body><div class="card">{body}</div></body></html>"""


def page(title, body) -> str:
    return _PAGE.format(title=e(title), body=body)


def signup_page(company="") -> str:
    return page("Subscribe", f"""
<h1>Get the occasional useful email</h1>
<p>One confirmation email first. Nothing else is sent until you click the
link in it, and you can leave at any time from the bottom of any email.</p>
<form method="post" action="/subscribe">
<label for="e">Email</label><input id="e" name="email" type="email" required>
<label for="n">Name (optional)</label><input id="n" name="name">
<label for="c">Company (optional)</label><input id="c" name="company">
<button type="submit">Subscribe</button></form>
<p><small>{e(company or 'Anthropos Automation')} stores the time, the method
and the page you used, because consent without a record of it is a claim
rather than a permission.</small></p>""")


def message_page(title, text, sub="") -> str:
    return page(title, f"<h1>{e(title)}</h1><p>{e(text)}</p>"
                       + (f"<p><small>{e(sub)}</small></p>" if sub else ""))


def unsubscribe_page(email, tok) -> str:
    return page("Unsubscribe", f"""
<h1>Leave this list</h1>
<p>Press the button and you will not be emailed again. Anything already
waiting to be sent to you is cancelled at the same moment.</p>
<form method="post" action="/unsubscribe">
<input type="hidden" name="email" value="{e(email)}">
<input type="hidden" name="t" value="{e(tok)}">
<button type="submit">Unsubscribe {e(email)}</button></form>""")
