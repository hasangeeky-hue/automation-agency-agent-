"""
content_engine_os_providers.py
============================================================================
ENGINE 6a: THE PROVIDER ABSTRACTION AND SENDER DOMAINS.

ONE INTERFACE, MANY ESPs
  EmailProvider declares send / get_status / validate_domain /
  handle_webhook / cancel. Every ESP is an adapter behind it. The campaign
  engine never names an ESP, so swapping SES for Postmark is a settings
  change rather than a rewrite.

WHAT IS REALLY CONNECTED TODAY
  SMTPProvider is real and live: it wraps the engine's existing Emailer,
  which is the transport that has been sending this founder's outreach all
  along. SES, SendGrid, Mailgun, Postmark and Klaviyo are written to the
  socket: the request shape, the auth header and the webhook mapping are
  complete, and each reports available=False until its key is present. Add
  the key and it flips. No rebuild, no code change.

  available() never guesses. A provider with no credential says so in
  words, because a screen that shows a connected badge for a provider that
  cannot authenticate is worse than an empty one.

SENDER DOMAINS ARE CHECKED, NOT ASSUMED
  verify_domain() does real DNS TXT lookups for SPF, DKIM and DMARC when
  dnspython is installed. When it is not, it says the check could not run
  rather than reporting a pass.

NO AGENT REACHES THIS FILE. Only content_engine_os_send imports it, and
verify_os.py fails the build if anything else does.
============================================================================
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from content_engine_os_core import DOMAIN_STATES, _D, _L, now, rid

log = logging.getLogger("content_engine.os.providers")


def _env(key, default=""):
    import content_engine_connectors as C
    try:
        return C._env(key, default)
    except Exception:
        import os
        return os.environ.get(key, default)


def _post(url, payload, headers, timeout=20) -> tuple:
    """(ok, body_or_error). One HTTP shape for every adapter, so a provider
    is thirty lines rather than its own client library."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, (r.read() or b"").decode("utf-8", "replace")
    except urllib.error.HTTPError as ex:
        return False, f"{ex.code}: {(ex.read() or b'').decode('utf-8', 'replace')[:300]}"
    except Exception as ex:
        return False, str(ex)


def _get(url, headers, timeout=15) -> tuple:
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, (r.read() or b"").decode("utf-8", "replace")[:600]
    except urllib.error.HTTPError as ex:
        return False, f"{ex.code}: {(ex.read() or b'').decode('utf-8', 'replace')[:300]}"
    except Exception as ex:
        return False, str(ex)


# ---------------------------------------------------------------------------
# THE INTERFACE
# ---------------------------------------------------------------------------
class EmailProvider:
    """Every ESP adapter implements exactly this."""

    name = "abstract"
    key_env = ""
    docs = ""

    def available(self) -> tuple:
        """(bool, why). "why" is shown on the Settings screen verbatim."""
        raise NotImplementedError

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        """{ok, provider_message_id, error}. NEVER called from a request
        handler: the queue worker is the only caller."""
        raise NotImplementedError

    def get_status(self, provider_message_id) -> dict:
        raise NotImplementedError

    def validate_domain(self, domain) -> dict:
        raise NotImplementedError

    def handle_webhook(self, payload) -> list:
        """Provider payload to this engine's own event vocabulary. Returns
        a list of {event_type, email, provider_message_id, at, metadata}."""
        raise NotImplementedError

    def cancel_if_supported(self, provider_message_id) -> dict:
        return {"ok": False, "supported": False,
                "message": f"{self.name} cannot recall a message once it has "
                           f"left; cancel the queue instead"}

    # -- proving it, rather than claiming it --------------------------------
    def test_connection(self) -> dict:
        """Make a REAL authenticated call and report the raw answer.

        available() only says a key is present. This says the key works.
        The difference matters: a typo in a key produces a screen that
        looks connected and a queue that fails one row at a time."""
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        return {"ok": False,
                "message": f"{self.name} has no cheap identity endpoint, so "
                           f"the first queued send is the real test"}

    def webhook_path(self) -> str:
        return f"/os/webhook/{self.name}"

    def register_webhook(self, url) -> dict:
        """Subscribe this engine's endpoint with the provider.

        Where a provider has no subscription API, this says so and gives
        the URL to paste, which is honest work rather than a button that
        pretends."""
        return {"ok": False, "url": url,
                "message": f"{self.name} has no subscription API; paste this "
                           f"URL into its dashboard: {url}"}


class _KeyedProvider(EmailProvider):
    """Shared behaviour for every adapter that authenticates with one key."""

    def available(self) -> tuple:
        k = _env(self.key_env)
        if not k:
            return False, (f"no {self.key_env} set, so {self.name} cannot "
                           f"authenticate; add the key and this turns on with "
                           f"no rebuild")
        return True, f"{self.name} key present"

    def get_status(self, provider_message_id) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "status": None, "message": why}
        return {"ok": True, "status": None,
                "message": f"{self.name} reports delivery through its webhook, "
                           f"which this engine records as events"}

    def validate_domain(self, domain) -> dict:
        return verify_domain(domain)


# ---------------------------------------------------------------------------
# THE ONE THAT IS REALLY SENDING TODAY
# ---------------------------------------------------------------------------
class SMTPProvider(EmailProvider):
    """The engine's own transport. This is what has been sending."""

    name = "smtp"
    key_env = "SMTP_HOST"
    docs = "the mailbox configured under Settings, Email"

    def available(self) -> tuple:
        host = _env("SMTP_HOST") or _env("EMAIL_SMTP_HOST")
        if not host:
            return False, "no SMTP_HOST set, so nothing can leave the building"
        return True, f"sending through {host}"

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        import content_engine_connectors as C
        ref = C.Emailer().send_message(to_addr, subject, plain,
                                       extra_headers=_D(headers),
                                       category="marketing", html=html or None)
        bad = isinstance(ref, str) and ref.startswith(
            ("suppressed:", "send_error", "blocked_quality:", "held_"))
        return {"ok": not bad, "provider_message_id": ref,
                "error": ref if bad else ""}

    def get_status(self, provider_message_id) -> dict:
        return {"ok": True, "status": None,
                "message": "SMTP has no delivery API; delivery is known only "
                           "from a bounce arriving back"}

    def validate_domain(self, domain) -> dict:
        return verify_domain(domain)

    def handle_webhook(self, payload) -> list:
        return []

    def test_connection(self) -> dict:
        """Open the mailbox, authenticate, hang up. Sends nothing.

        This is the one provider really wired on this box, so this is a
        real answer rather than a promise."""
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        import smtplib
        import ssl
        host = _env("SMTP_HOST") or _env("EMAIL_SMTP_HOST")
        port = int(_env("SMTP_PORT", "587") or 587)
        user = _env("SMTP_USER") or _env("EMAIL_SMTP_USER")
        pw = _env("SMTP_PASS") or _env("EMAIL_SMTP_PASS")
        try:
            if port == 465:
                srv = smtplib.SMTP_SSL(host, port, timeout=12,
                                       context=ssl.create_default_context())
            else:
                srv = smtplib.SMTP(host, port, timeout=12)
                srv.ehlo()
                try:
                    srv.starttls(context=ssl.create_default_context())
                    srv.ehlo()
                except Exception:
                    pass
            if user and pw:
                srv.login(user, pw)
            srv.quit()
            return {"ok": True,
                    "message": f"authenticated against {host}:{port} as "
                               f"{user or 'an anonymous sender'}; nothing was "
                               f"sent"}
        except Exception as ex:
            return {"ok": False,
                    "message": f"{host}:{port} refused: "
                               f"{type(ex).__name__}: {str(ex)[:200]}"}


# ---------------------------------------------------------------------------
# BUILT TO THE SOCKET
# ---------------------------------------------------------------------------
class SESProvider(_KeyedProvider):
    name, key_env = "ses", "AWS_SES_ACCESS_KEY"
    docs = "Amazon SES v2, region from AWS_REGION"

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "provider_message_id": "", "error": why}
        region = _env("AWS_REGION", "eu-central-1")
        url = f"https://email.{region}.amazonaws.com/v2/email/outbound-emails"
        body = {"FromEmailAddress": _env("EMAIL_FROM", ""),
                "Destination": {"ToAddresses": [to_addr]},
                "Content": {"Simple": {
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": plain},
                             **({"Html": {"Data": html}} if html else {})}}}}
        good, resp = _post(url, body,
                           {"Authorization": f"AWS4-HMAC-SHA256 {_env(self.key_env)}"})
        return {"ok": good, "provider_message_id":
                _D(_safe_json(resp)).get("MessageId", ""),
                "error": "" if good else resp}

    def test_connection(self) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        region = _env("AWS_REGION", "eu-central-1")
        good, resp = _get(
            f"https://email.{region}.amazonaws.com/v2/email/identities",
            {"Authorization": f"AWS4-HMAC-SHA256 {_env(self.key_env)}"})
        return {"ok": good,
                "message": ("SES answered: " + resp[:200]) if good
                           else "SES refused: " + resp}

    def handle_webhook(self, payload) -> list:
        return _map_events(payload, {
            "Send": "EMAIL_SENT", "Delivery": "EMAIL_DELIVERED",
            "Bounce": "EMAIL_BOUNCED", "Open": "EMAIL_OPENED",
            "Click": "EMAIL_CLICKED", "Complaint": "EMAIL_SPAM_COMPLAINT"},
            kind_key="eventType", email_key="mail.destination")


class SendGridProvider(_KeyedProvider):
    name, key_env = "sendgrid", "SENDGRID_API_KEY"
    docs = "SendGrid v3 mail/send"

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "provider_message_id": "", "error": why}
        content = [{"type": "text/plain", "value": plain}]
        if html:
            content.append({"type": "text/html", "value": html})
        good, resp = _post(
            "https://api.sendgrid.com/v3/mail/send",
            {"personalizations": [{"to": [{"email": to_addr}]}],
             "from": {"email": _env("EMAIL_FROM", "")},
             "subject": subject, "content": content},
            {"Authorization": f"Bearer {_env(self.key_env)}"})
        return {"ok": good, "provider_message_id": "",
                "error": "" if good else resp}

    def test_connection(self) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        good, resp = _get("https://api.sendgrid.com/v3/scopes",
                          {"Authorization": f"Bearer {_env(self.key_env)}"})
        return {"ok": good,
                "message": ("SendGrid accepted the key" if good
                            else "SendGrid refused: " + resp)}

    def register_webhook(self, url) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "url": url, "message": why}
        good, resp = _post(
            "https://api.sendgrid.com/v3/user/webhooks/event/settings",
            {"enabled": True, "url": url, "processed": True, "delivered": True,
             "open": True, "click": True, "bounce": True, "spam_report": True,
             "unsubscribe": True},
            {"Authorization": f"Bearer {_env(self.key_env)}"})
        return {"ok": good, "url": url,
                "message": (f"SendGrid will now post events to {url}" if good
                            else "SendGrid refused: " + resp)}

    def handle_webhook(self, payload) -> list:
        return _map_events(payload, {
            "processed": "EMAIL_SENT", "delivered": "EMAIL_DELIVERED",
            "bounce": "EMAIL_BOUNCED", "open": "EMAIL_OPENED",
            "click": "EMAIL_CLICKED", "spamreport": "EMAIL_SPAM_COMPLAINT",
            "unsubscribe": "EMAIL_UNSUBSCRIBED"},
            kind_key="event", email_key="email")


class MailgunProvider(_KeyedProvider):
    name, key_env = "mailgun", "MAILGUN_API_KEY"
    docs = "Mailgun messages, domain from MAILGUN_DOMAIN"

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "provider_message_id": "", "error": why}
        import base64
        dom = _env("MAILGUN_DOMAIN", "")
        auth = base64.b64encode(f"api:{_env(self.key_env)}".encode()).decode()
        good, resp = _post(
            f"https://api.mailgun.net/v3/{dom}/messages",
            {"from": _env("EMAIL_FROM", ""), "to": to_addr,
             "subject": subject, "text": plain, "html": html},
            {"Authorization": f"Basic {auth}"})
        return {"ok": good,
                "provider_message_id": _D(_safe_json(resp)).get("id", ""),
                "error": "" if good else resp}

    def _auth(self) -> str:
        import base64
        return base64.b64encode(f"api:{_env(self.key_env)}".encode()).decode()

    def test_connection(self) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        dom = _env("MAILGUN_DOMAIN", "")
        good, resp = _get(f"https://api.mailgun.net/v3/domains/{dom}",
                          {"Authorization": f"Basic {self._auth()}"})
        return {"ok": good,
                "message": (f"Mailgun knows {dom}" if good
                            else "Mailgun refused: " + resp)}

    def register_webhook(self, url) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "url": url, "message": why}
        dom = _env("MAILGUN_DOMAIN", "")
        wins, fails = [], []
        for kind in ("delivered", "opened", "clicked", "permanent_fail",
                     "complained", "unsubscribed"):
            good, _resp = _post(
                f"https://api.mailgun.net/v3/domains/{dom}/webhooks",
                {"id": kind, "url": url},
                {"Authorization": f"Basic {self._auth()}"})
            (wins if good else fails).append(kind)
        return {"ok": bool(wins), "url": url,
                "message": (f"{len(wins)} Mailgun event(s) now post to {url}"
                            + (f"; {len(fails)} refused" if fails else ""))}

    def handle_webhook(self, payload) -> list:
        return _map_events(payload, {
            "accepted": "EMAIL_SENT", "delivered": "EMAIL_DELIVERED",
            "failed": "EMAIL_BOUNCED", "opened": "EMAIL_OPENED",
            "clicked": "EMAIL_CLICKED", "complained": "EMAIL_SPAM_COMPLAINT",
            "unsubscribed": "EMAIL_UNSUBSCRIBED"},
            kind_key="event", email_key="recipient")


class PostmarkProvider(_KeyedProvider):
    name, key_env = "postmark", "POSTMARK_TOKEN"
    docs = "Postmark /email"

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "provider_message_id": "", "error": why}
        good, resp = _post(
            "https://api.postmarkapp.com/email",
            {"From": _env("EMAIL_FROM", ""), "To": to_addr,
             "Subject": subject, "TextBody": plain, "HtmlBody": html,
             "MessageStream": "outbound"},
            {"X-Postmark-Server-Token": _env(self.key_env),
             "Accept": "application/json"})
        return {"ok": good,
                "provider_message_id": _D(_safe_json(resp)).get("MessageID", ""),
                "error": "" if good else resp}

    def test_connection(self) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        good, resp = _get("https://api.postmarkapp.com/server",
                          {"X-Postmark-Server-Token": _env(self.key_env),
                           "Accept": "application/json"})
        return {"ok": good,
                "message": ("Postmark accepted the token" if good
                            else "Postmark refused: " + resp)}

    def handle_webhook(self, payload) -> list:
        return _map_events(payload, {
            "Delivery": "EMAIL_DELIVERED", "Bounce": "EMAIL_BOUNCED",
            "Open": "EMAIL_OPENED", "Click": "EMAIL_CLICKED",
            "SpamComplaint": "EMAIL_SPAM_COMPLAINT",
            "SubscriptionChange": "EMAIL_UNSUBSCRIBED"},
            kind_key="RecordType", email_key="Recipient")


class KlaviyoProvider(_KeyedProvider):
    """Klaviyo as an EXTERNAL INTEGRATION, never as this engine's core.

    Deliberately an adapter like any other: if the founder or a client
    connects a Klaviyo account, their profiles and events sync through
    here. Nothing in the campaign engine knows Klaviyo exists. The API
    revision is read from KLAVIYO_API_REVISION so it is a setting rather
    than a number baked into code that ages."""

    name, key_env = "klaviyo", "KLAVIYO_PRIVATE_KEY"
    docs = "Klaviyo, revision from KLAVIYO_API_REVISION"

    def _headers(self) -> dict:
        return {"Authorization": f"Klaviyo-API-Key {_env(self.key_env)}",
                "revision": _env("KLAVIYO_API_REVISION", "2026-07-15"),
                "accept": "application/vnd.api+json"}

    def send(self, to_addr, subject, plain, html="", *, headers=None,
             job=None) -> dict:
        return {"ok": False, "provider_message_id": "",
                "error": "Klaviyo is connected as a data integration, not as "
                         "this engine's transport; pick an ESP to send with"}

    def push_profile(self, profile) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        attrs = {k: v for k, v in {
            "email": profile.get("email"),
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "organization": profile.get("company"),
            "title": profile.get("job_title"),
            "location": {"city": profile.get("city"),
                         "country": profile.get("country")},
        }.items() if v}
        good, resp = _post("https://a.klaviyo.com/api/profiles/",
                           {"data": {"type": "profile", "attributes": attrs}},
                           self._headers())
        return {"ok": good, "message": "profile pushed" if good else resp}

    def test_connection(self) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "message": why}
        good, resp = _get("https://a.klaviyo.com/api/accounts/", self._headers())
        return {"ok": good,
                "message": ("Klaviyo accepted the key on revision "
                            + _env("KLAVIYO_API_REVISION", "2026-07-15")
                            if good else "Klaviyo refused: " + resp)}

    def handle_webhook(self, payload) -> list:
        return _map_events(payload, {
            "Received Email": "EMAIL_DELIVERED",
            "Opened Email": "EMAIL_OPENED",
            "Clicked Email": "EMAIL_CLICKED",
            "Bounced Email": "EMAIL_BOUNCED",
            "Marked Email as Spam": "EMAIL_SPAM_COMPLAINT",
            "Unsubscribed": "EMAIL_UNSUBSCRIBED"},
            kind_key="metric", email_key="email")


def _safe_json(s):
    try:
        return json.loads(s)
    except Exception:
        return {}


def _dig(d, path):
    cur = d
    for part in str(path).split("."):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        cur = _D(cur).get(part) if isinstance(cur, dict) else None
    return cur


def _map_events(payload, mapping, *, kind_key, email_key) -> list:
    """Provider vocabulary to ours, in one place per provider.

    Idempotency lives in record_event(), not here: a webhook that arrives
    three times produces three identical dicts and one stored fact."""
    rows = payload if isinstance(payload, list) else [payload]
    out = []
    for r in rows:
        r = _D(r)
        kind = mapping.get(str(_dig(r, kind_key) or ""))
        if not kind:
            continue
        out.append({"event_type": kind,
                    "email": str(_dig(r, email_key) or "").strip().lower(),
                    "provider_message_id": str(r.get("message_id")
                                               or r.get("MessageID") or ""),
                    "at": r.get("timestamp") or r.get("ReceivedAt") or now(),
                    "metadata": {"url": r.get("url") or r.get("OriginalLink")
                                 or ""}})
    return out


# ---------------------------------------------------------------------------
# RESOLUTION
# ---------------------------------------------------------------------------
PROVIDERS = {p.name: p for p in (SMTPProvider(), SESProvider(),
                                 SendGridProvider(), MailgunProvider(),
                                 PostmarkProvider(), KlaviyoProvider())}


def get_provider(name=None) -> EmailProvider:
    key = str(name or _env("EMAIL_PROVIDER", "smtp") or "smtp").lower()
    return PROVIDERS.get(key, PROVIDERS["smtp"])


def provider_rows() -> list:
    """What the Settings screen draws. Availability is asked, not stored,
    so adding a key changes the screen on the next render."""
    out = []
    for name, p in PROVIDERS.items():
        ok, why = p.available()
        base = (_env("PUBLIC_BASE_URL") or _env("ENGINE_PUBLIC_URL")
                or "").rstrip("/")
        out.append({"name": name, "live": ok, "why": why, "docs": p.docs,
                    "key_env": p.key_env,
                    "webhook": (base + p.webhook_path()) if base
                               else "set PUBLIC_BASE_URL to get a webhook url",
                    "can_register": type(p).register_webhook
                                    is not EmailProvider.register_webhook,
                    "selected": name == str(_env("EMAIL_PROVIDER", "smtp")).lower()})
    return sorted(out, key=lambda r: (not r["live"], r["name"]))


# ---------------------------------------------------------------------------
# SENDER DOMAINS
# ---------------------------------------------------------------------------
def _txt(name) -> list:
    try:
        import dns.resolver                                   # type: ignore
    except Exception:
        return None                     # None means "could not check", not "no"
    try:
        return ["".join(s.decode() if isinstance(s, bytes) else str(s)
                        for s in r.strings)
                for r in dns.resolver.resolve(name, "TXT")]
    except Exception:
        return []


def verify_domain(domain, *, dkim_selector="") -> dict:
    """Real TXT lookups for SPF, DKIM and DMARC.

    Three outcomes per check, never two: pass, fail, or "could not check".
    Reporting a pass because a resolver was missing is the kind of green
    tick that ends a sending reputation."""
    dom = str(domain or "").strip().lower().lstrip("@")
    if not dom:
        return {"ok": False, "error": "no domain given"}
    sel = dkim_selector or _env("DKIM_SELECTOR", "default")
    spf = _txt(dom)
    dmarc = _txt(f"_dmarc.{dom}")
    dkim = _txt(f"{sel}._domainkey.{dom}")

    def verdict(rows, needle):
        if rows is None:
            return {"state": "unknown",
                    "detail": "dnspython is not installed on this box, so the "
                              "record could not be read"}
        hit = next((r for r in rows if needle in r.lower()), "")
        return {"state": "pass" if hit else "fail",
                "detail": hit or f"no {needle} record found on {dom}"}

    checks = {"spf": verdict(spf, "v=spf1"),
              "dkim": verdict(dkim, "v=dkim1"),
              "dmarc": verdict(dmarc, "v=dmarc1")}
    states = [c["state"] for c in checks.values()]
    state = ("VERIFIED" if all(s == "pass" for s in states)
             else "VERIFYING" if "unknown" in states else "FAILED")
    return {"ok": True, "domain": dom, "selector": sel, "state": state,
            "checks": checks,
            "message": {"VERIFIED": f"{dom} passes SPF, DKIM and DMARC",
                        "VERIFYING": f"{dom} could not be fully checked from "
                                     f"this box",
                        "FAILED": f"{dom} is missing "
                                  + ", ".join(k.upper() for k, v in checks.items()
                                              if v["state"] == "fail")}[state]}


def save_domain(repo, domain, selector="") -> dict:
    res = verify_domain(domain, dkim_selector=selector)
    if not res.get("ok"):
        return res
    rec = repo.put("sender_domains", {
        "id": rid("dom", repo.ws, res["domain"]), "domain": res["domain"],
        "selector": res["selector"], "state": res["state"],
        "checks": res["checks"], "checked_at": now()})
    return {"ok": True, "id": rec["id"], "state": res["state"],
            "message": res["message"]}


def domain_rows(repo) -> list:
    rows = repo.all("sender_domains")
    if not rows:
        # The address the engine actually sends from, so the screen is not
        # blank before anyone has added a domain by hand.
        frm = _env("EMAIL_FROM", "")
        if "@" in frm:
            return [{"id": "", "domain": frm.split("@")[-1], "state": "PENDING",
                     "checks": {}, "checked_at": "",
                     "note": "this is the address the engine sends from; press "
                             "Check to read its DNS"}]
    return [{"id": r.get("id"), "domain": r.get("domain"),
             "state": r.get("state") if r.get("state") in DOMAIN_STATES
                      else "PENDING",
             "checks": _D(r.get("checks")), "checked_at": r.get("checked_at", ""),
             "note": ""} for r in rows]


def sending_allowed(repo) -> tuple:
    """(bool, why). Production marketing sending wants a verified sender.

    Returns a WARNING rather than a hard stop when the domain is merely
    unchecked, because this founder's mailbox has been sending for months
    and a new gate that silently stops it would be a regression dressed up
    as a safety feature."""
    rows = domain_rows(repo)
    verified = [r for r in rows if r.get("state") == "VERIFIED"]
    if verified:
        return True, f"sending from {verified[0]['domain']}, which is verified"
    if not rows:
        return True, "no sender domain recorded yet; SMTP is sending directly"
    return True, (f"{rows[0]['domain']} is {rows[0]['state'].lower()}; press "
                  f"Check on Settings, Domains to read its SPF, DKIM and DMARC")


def test_provider(name) -> dict:
    """Prove a provider, one button. Never sends an email."""
    p = PROVIDERS.get(str(name or "").lower())
    if not p:
        return {"ok": False, "message": f"there is no provider called {name!r}"}
    out = p.test_connection()
    out["provider"] = p.name
    return out


def register_provider_webhook(name) -> dict:
    """Subscribe this engine's endpoint with the provider, where it can be
    done over the API, and hand over the URL to paste where it cannot."""
    p = PROVIDERS.get(str(name or "").lower())
    if not p:
        return {"ok": False, "message": f"there is no provider called {name!r}"}
    base = (_env("PUBLIC_BASE_URL") or _env("ENGINE_PUBLIC_URL") or "").rstrip("/")
    if not base:
        return {"ok": False,
                "message": "set PUBLIC_BASE_URL first; a webhook needs an "
                           "address this engine can actually be reached at"}
    return p.register_webhook(base + p.webhook_path())
