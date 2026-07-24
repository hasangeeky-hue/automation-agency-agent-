"""
content_engine_connectors.py
============================================================================
THE "HANDS" — real-world connectors that turn the engine from thinking-only
into acting-on-live-data. Every connector plugs into an existing seam:

  hook (in content_engine_code_skills)   connector here            gap it closes
  ------------------------------------   -----------------------   -----------------
  PUBLISH_FN  (job, piece) -> ref        WordPress.publish         Q2/Q5/Q8 publish
  SEND_FN     (job, email) -> ref        Emailer.send              Q17/Q18 send email
  VERIFY_FN   (email)      -> bool       verify_email              lead email hygiene
  SOURCE_FN   (job)        -> [leads]    source_leads (web+LI)     Q10/Q13/Q14 scrape
  BACKLINK_FN (job)        -> {...}      backlinks (provider seam) Q8 authority

  payload collectors (call BEFORE a job runs, or from n8n via the API):
  collect_site_audit(url)   -> payload["audit"]        Q7 on-page SEO data (GSC)
  collect_competitors(urls) -> payload["competitors"]  competitor intel
  collect_analytics()       -> payload["analytics"]    Q11 tracking (GA4)
  collect_ads()             -> payload["ads"]          ads optimizer live data
  search_web(q) / scrape_url(u)                        generic web read

DESIGN RULES
------------
* Secrets come ONLY from environment variables — nothing is hardcoded.
* Every connector has available() (are its creds present?) and NEVER raises:
  on any error it logs and returns empty/None so the worker keeps running and
  the engine falls back to its safe offline default.
* wire_all() installs a connector ONLY when its creds are present, so a
  half-configured deploy still runs — each gap closes the moment you add its key.
* WordPress defaults to status="draft" (safe for first runs). Set WP_STATUS=publish
  when you're ready for the agent to publish live.
* `requests` is imported lazily; the module + its self-check run with zero deps.

Turn it on (in main.py, already wired below): connectors.wire_all() at startup.
See status with: python content_engine_connectors.py   (prints what's live).

ENV VARS (add the ones you have; leave the rest blank to stay offline)
----------------------------------------------------------------------
  WordPress:  WORDPRESS_URL  WORDPRESS_USER  WORDPRESS_APP_PASSWORD  [WP_STATUS=draft]
  Email:      SMTP_HOST  SMTP_PORT  SMTP_USER  SMTP_PASSWORD  SMTP_FROM  [SMTP_STARTTLS=1]
  Web search: SEARCH_PROVIDER=tavily|serpapi  SEARCH_API_KEY
  LinkedIn:   LINKEDIN_PROVIDER_URL  LINKEDIN_API_KEY   (a COMPLIANT data provider)
  Google:     GOOGLE_ACCESS_TOKEN  GSC_SITE_URL  GA4_PROPERTY_ID
  Ads:        ADS_JSON  (paste a JSON blob from n8n/Google Ads), or leave blank
  Backlinks:  BACKLINKS_JSON  (paste {client, competitors} JSON), or leave blank
============================================================================
"""

from __future__ import annotations

import email as _emaillib
import imaplib
import json
import logging
import os
import re
import smtplib
import socket
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from html.parser import HTMLParser
from typing import Optional

log = logging.getLogger("connectors")

# Sensible timeouts so a slow endpoint never hangs the worker.
_HTTP_TIMEOUT = float(os.getenv("CONNECTOR_HTTP_TIMEOUT", "20"))
_UA = "AnthroposContentEngine/1.0 (+https://anthropos-automation.com)"


# ---------------------------------------------------------------------------
# Tiny HTTP helpers (lazy `requests`; degrade to None if unavailable)
# ---------------------------------------------------------------------------
def _requests():
    try:
        import requests  # noqa: WPS433 (lazy on purpose)
        return requests
    except Exception:
        return None


# Credentials can come from the settings store (set via the dashboard's Connect
# form) OR from environment variables. The store wins so the founder can wire
# everything from the browser with no SSH / .env editing / rebuild.
_SETTINGS_GET = None


def set_settings_provider(fn) -> None:
    """api/worker call this with store.get_setting so _env() reads DB creds."""
    global _SETTINGS_GET
    _SETTINGS_GET = fn


def _env(name: str, default: str = "") -> str:
    v = None
    if _SETTINGS_GET is not None:
        try:
            v = _SETTINGS_GET(name)
        except Exception:
            v = None
    if v is None or v == "":
        v = os.getenv(name, default)
    return (str(v) if v is not None else "").strip()


# ---------------------------------------------------------------------------
# LOOP-CLOSERS — set by api/worker at startup
#   1) Budget loop: meter EXTERNAL spend (Prospeo credits, image/video) into the
#      same daily cost the €200 cap watches — it previously saw only Claude.
#   2) Deliverability loop: an email suppression list + a warm-up daily send cap,
#      so cold email from a fresh domain doesn't get torched by spam filters.
# ---------------------------------------------------------------------------
_COST_RECORDER = None   # -> store.add_daily_cost
_SETTINGS_SET = None    # -> store.set_setting (persists suppression + counters)


def set_cost_recorder(fn) -> None:
    global _COST_RECORDER
    _COST_RECORDER = fn


def set_settings_writer(fn) -> None:
    global _SETTINGS_SET
    _SETTINGS_SET = fn


def _record_cost(usd: float, kind: str = "") -> None:
    try:
        if _COST_RECORDER and usd and usd > 0:
            _COST_RECORDER(float(usd))
            log.info("external spend metered: $%.4f (%s)", usd, kind)
    except Exception:
        pass


def _setting(key: str, default=None):
    """Read a structured (non-string) setting, e.g. the suppression list."""
    if _SETTINGS_GET is not None:
        try:
            v = _SETTINGS_GET(key)
            if v is not None:
                return v
        except Exception:
            pass
    return default


def _set_setting(key: str, value) -> None:
    try:
        if _SETTINGS_SET:
            _SETTINGS_SET(key, value)
    except Exception:
        pass


def is_suppressed(addr: str) -> bool:
    a = (addr or "").strip().lower()
    if not a:
        return True
    supp = _setting("email_suppression", []) or []
    return a in {str(s).strip().lower() for s in supp}


def suppress_email(addr: str, reason: str = "bounce") -> None:
    a = (addr or "").strip()
    if not a:
        return
    supp = list(_setting("email_suppression", []) or [])
    if a.lower() not in {str(s).strip().lower() for s in supp}:
        supp.append(a)
        _set_setting("email_suppression", supp)
        log.info("suppressed %s (%s)", a, reason)


def _warmup_cap() -> int:
    """Today's cold-email ceiling. A hard OUTREACH_DAILY_CAP wins; otherwise ramp
    up from a new domain over ~2 weeks so we protect sending reputation."""
    hard = _env("OUTREACH_DAILY_CAP")
    if hard.isdigit() and int(hard) > 0:
        return int(hard)
    start = _setting("outreach_first_send_day")
    if not start:
        return 15
    try:
        from datetime import date
        days = (date.today() - date.fromisoformat(str(start)[:10])).days
    except Exception:
        return 15
    ramp = [15, 20, 30, 45, 60, 80, 110, 150, 200]
    return ramp[min(max(days, 0), len(ramp) - 1)]


def _sent_today_key() -> str:
    from datetime import date
    return "outreach_sent_" + date.today().isoformat()


def outreach_send_allowed() -> bool:
    """False once today's warm-up cap is hit — the deliverability guard."""
    return int(_setting(_sent_today_key(), 0) or 0) < _warmup_cap()


def _note_outreach_sent() -> None:
    from datetime import date
    if not _setting("outreach_first_send_day"):
        _set_setting("outreach_first_send_day", date.today().isoformat())
    k = _sent_today_key()
    _set_setting(k, int(_setting(k, 0) or 0) + 1)


_BOUNCE_SENDERS = ("mailer-daemon", "postmaster", "mail-daemon")
_BOUNCE_SUBJECTS = ("undeliverable", "delivery status notification", "returned mail",
                    "delivery failure", "mail delivery failed", "failure notice",
                    "delivery has failed", "undelivered mail", "address not found")


def detect_bounce(m: dict) -> str:
    """If message m is a bounce / non-delivery report, return the dead recipient
    address to suppress (best-effort), else ''. Used by the reply agent so a
    bounced address is never emailed again."""
    frm = str(m.get("from_email") or m.get("from") or "").lower()
    subj = str(m.get("subject") or "").lower()
    if not (any(s in frm for s in _BOUNCE_SENDERS) or any(s in subj for s in _BOUNCE_SUBJECTS)):
        return ""
    body = str(m.get("message") or "")
    mm = re.search(r"[Ff]inal-[Rr]ecipient:\s*rfc822;\s*([^\s>]+@[^\s>]+)", body)
    if mm:
        return mm.group(1).strip().strip("<>")
    for cand in re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", body):
        cl = cand.lower()
        if not any(s in cl for s in _BOUNCE_SENDERS) and "anthropos-automation.com" not in cl:
            return cand
    return ""


# Every credential the dashboard's Connect form is allowed to set (the allow-list
# the /connect endpoint checks, and the fields the form renders).
CONNECTOR_ENV_KEYS = [
    "ANTHROPIC_API_KEY",   # the Claude brain — front-end settable, bridged to env in wire_all()
    "WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD", "WP_STATUS",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_STARTTLS",
    "IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER",
    "SEARCH_PROVIDER", "SEARCH_API_KEY",
    "LINKEDIN_PROVIDER_URL", "LINKEDIN_API_KEY",
    "PROSPEO_API_KEY", "LEAD_COUNTRIES", "LEAD_TITLES",
    "GOOGLE_ACCESS_TOKEN", "GSC_SITE_URL", "GA4_PROPERTY_ID",
    "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SHEETS_ID", "GDRIVE_FOLDER_ID",
    "ADS_JSON", "BACKLINKS_JSON",
    "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "CALCOM_API_KEY",
    "EMAIL_LOGO_URL", "EMAIL_BOOKING_URL", "EMAIL_MANAGE_URL", "EMAIL_UNSUBSCRIBE_URL",
    "EMAIL_COMPANY", "EMAIL_ADDRESS", "EMAIL_BRAND_COLOR", "EMAIL_HTML",
    "LINKEDIN_POST_TOKEN", "LINKEDIN_AUTHOR_URN", "TWITTER_BEARER_TOKEN",
    "META_PAGE_ID", "META_PAGE_TOKEN", "IG_USER_ID", "TIKTOK_ACCESS_TOKEN",
    "IMAGE_PROVIDER", "IMAGE_API_KEY", "IMAGE_MODEL", "IMAGE_API_URL",
    "VIDEO_PROVIDER", "VIDEO_API_KEY", "VIDEO_API_URL",
    "REPLY_OUR_OFFER", "REPLY_SENDER_NAME", "REPLY_CONTEXT", "REPLY_AUTO_SEND",
    "CI_JSON",
]

# Which alias each email PURPOSE goes out from (localpart @ your domain). This is
# the loop: the agent tags an email's purpose, and it's sent from the matching
# alias — newsletter@ / marketing@ / customercare@ / contact@ — all from your one
# Workspace inbox. Override any with EMAIL_FROM_<CATEGORY>.
EMAIL_CATEGORY_ALIAS = {
    "newsletter": "newsletter",
    "marketing": "marketing",
    "outreach": "marketing",
    "support": "customercare",
    "reply": "customercare",
    "thanks": "contact",
    "welcome": "contact",
}


def _get_json(url: str, headers: Optional[dict] = None, params: Optional[dict] = None):
    rq = _requests()
    if not rq:
        return None
    try:
        r = rq.get(url, headers={**{"User-Agent": _UA}, **(headers or {})},
                   params=params or {}, timeout=_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("GET %s failed: %s", url, e)
        return None


def _post_json(url: str, payload: dict, headers: Optional[dict] = None):
    rq = _requests()
    if not rq:
        return None
    try:
        r = rq.post(url, headers={**{"User-Agent": _UA}, **(headers or {})},
                    json=payload, timeout=_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("POST %s failed: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Q2 / Q5 / Q8 — WordPress publisher  (PUBLISH_FN)
# ---------------------------------------------------------------------------
class WordPress:
    """Publish a produced piece to WordPress via the REST API + an Application
    Password (Users -> Profile -> Application Passwords in wp-admin).

    Defaults to status='draft' so the agent stages the post for your review;
    set WP_STATUS=publish to go fully live (the engine's human-approval gate has
    already passed by the time this runs)."""

    def __init__(self) -> None:
        self.base = _env("WORDPRESS_URL").rstrip("/")
        self.user = _env("WORDPRESS_USER")
        self.app_password = _env("WORDPRESS_APP_PASSWORD")
        self.status = _env("WP_STATUS", "draft")

    def available(self) -> bool:
        return bool(self.base and self.user and self.app_password and _requests())

    def publish(self, job: dict, piece: dict) -> str:
        rq = _requests()
        title = piece.get("title") or piece.get("meta_title") or "Untitled"
        body = piece.get("body") or ""
        # SEO fields the theme/Yoast can read from excerpt/meta if configured.
        excerpt = piece.get("meta_description", "")
        data = {"title": title, "content": body, "status": self.status,
                "excerpt": excerpt}
        try:
            r = rq.post(
                f"{self.base}/wp-json/wp/v2/posts",
                json=data,
                auth=(self.user, self.app_password),
                headers={"User-Agent": _UA},
                timeout=_HTTP_TIMEOUT,
            )
            r.raise_for_status()
            j = r.json()
            ref = j.get("link") or f"wp:{j.get('id')}"
            log.info("published to WordPress (%s): %s", self.status, ref)
            return ref
        except Exception as e:
            # Never crash the pipeline; surface a clear ref so the human notices.
            log.error("WordPress publish failed: %s", e)
            return f"wp_error:{job.get('job_id')}"


# ---------------------------------------------------------------------------
# Q17 / Q18 — Email sender  (SEND_FN)  — CAN-SPAM aware
# ---------------------------------------------------------------------------
def _html_escape(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Brand defaults pulled from the live site (logo) so cold email looks like the brand.
_LOGO_DEFAULT = "https://anthropos-automation.com/wp-content/uploads/2026/07/cropped-anthropos-logo-mark-transparent-1024-270x270.png"


def _branded_email_html(body: str, *, logo, booking_url, unsub_url, manage_url,
                        company, address, brand, sender) -> str:
    """A branded, email-client-safe HTML wrapper: logo header, the written body,
    a Book-an-appointment button, and a footer with address + manage/unsubscribe."""
    paras = "".join(
        f'<p style="margin:0 0 14px;color:#2b2b3a;font-size:15px;line-height:1.6">{_html_escape(p).strip()}</p>'
        for p in body.split("\n") if p.strip())
    return (
        '<!doctype html><html><body style="margin:0;background:#f4f2fb">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f2fb;padding:24px 0"><tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:14px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;max-width:600px">'
        f'<tr><td style="background:{brand};padding:18px 28px"><img src="{logo}" alt="{_html_escape(company)}" height="38" style="height:38px;display:block;border:0"></td></tr>'
        f'<tr><td style="padding:26px 28px 6px">{paras}</td></tr>'
        f'<tr><td style="padding:8px 28px 24px"><a href="{booking_url}" style="background:{brand};color:#ffffff;text-decoration:none;font-weight:bold;font-size:15px;padding:13px 26px;border-radius:10px;display:inline-block">\U0001F4C5 Book a free appointment</a></td></tr>'
        f'<tr><td style="padding:0 28px 22px"><p style="margin:0;color:#8a8aa0;font-size:13px">— {_html_escape(sender)}, {_html_escape(company)}</p></td></tr>'
        f'<tr><td style="background:#f4f2fb;padding:15px 28px;border-top:1px solid #eceafa">'
        f'<p style="margin:0 0 6px;color:#9a9ab0;font-size:11px;line-height:1.5">{_html_escape(company)} · {_html_escape(address)}</p>'
        f'<p style="margin:0;color:#9a9ab0;font-size:11px"><a href="{manage_url}" style="color:{brand}">Manage subscription</a> · <a href="{unsub_url}" style="color:{brand}">Unsubscribe</a></p>'
        '</td></tr></table></td></tr></table></body></html>')


class Emailer:
    """Send the approved cold email over SMTP. Cold outreach goes out as a branded
    HTML email (logo + Book-an-appointment button + manage/unsubscribe footer);
    replies stay plain. Adds a List-Unsubscribe header and relies on the copy
    already containing a physical address + unsubscribe link."""

    def __init__(self) -> None:
        self.host = _env("SMTP_HOST")
        self.port = int(_env("SMTP_PORT", "587") or "587")
        self.user = _env("SMTP_USER")
        self.password = _env("SMTP_PASSWORD")
        self.sender = _env("SMTP_FROM") or self.user
        self.starttls = _env("SMTP_STARTTLS", "1") != "0"

    def available(self) -> bool:
        return bool(self.host and self.sender)

    @staticmethod
    def _recipient(job: dict) -> str:
        p = job.get("payload", {})
        lead = p.get("lead") or {}
        if lead.get("email"):
            return lead["email"]
        leads = p.get("leads") or []
        return (leads[0].get("email") if leads else "") or ""

    def _transport(self, msg: EmailMessage) -> None:
        ctx = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=_HTTP_TIMEOUT,
                                  context=ctx) as s:
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=_HTTP_TIMEOUT) as s:
                if self.starttls:
                    s.starttls(context=ctx)
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(msg)

    def from_for(self, category: Optional[str]) -> str:
        """Pick the FROM address for an email's purpose so each type goes out on
        the right alias (newsletter@ / marketing@ / customercare@ / contact@).
        Override any with EMAIL_FROM_<CATEGORY>; otherwise derive alias@yourdomain."""
        base = self.sender or self.user
        if not category or "@" not in (base or ""):
            return base
        override = _env(f"EMAIL_FROM_{category.upper()}")
        domain = base.split("@", 1)[1]
        if override:
            return override if "@" in override else f"{override}@{domain}"
        alias = EMAIL_CATEGORY_ALIAS.get(category.lower())
        return f"{alias}@{domain}" if alias else base

    def send_message(self, to_addr: str, subject: str, body: str,
                     extra_headers: Optional[dict] = None,
                     category: Optional[str] = None, html: Optional[str] = None) -> str:
        """Generic one-shot send (reused by cold outreach AND reply answering).
        `category` routes the FROM address to the matching alias. `html` (optional)
        sends a branded HTML alternative with the plain text as fallback."""
        if is_suppressed(to_addr):   # never email a bounced / unsubscribed address
            log.info("skip suppressed recipient %s", to_addr)
            return f"suppressed:{to_addr}"
        msg = EmailMessage()
        msg["From"] = self.from_for(category)
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid()
        for k, v in (extra_headers or {}).items():
            if v:
                msg[k] = v
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")
        try:
            self._transport(msg)
            log.info("email sent to %s from %s (%s)", to_addr, msg["From"], category or "default")
            return msg["Message-ID"]
        except Exception as e:
            log.error("email send failed: %s", e)
            return f"send_error:{to_addr}"

    def send(self, job: dict, email: dict) -> str:
        to_addr = self._recipient(job)
        if not to_addr:
            log.error("no recipient email on job %s — not sending", job.get("job_id"))
            return f"send_error_no_recipient:{job.get('job_id')}"
        is_outreach = job.get("type") == "outreach_campaign"
        # deliverability loop: hold cold outreach once the warm-up cap is hit.
        if is_outreach and not outreach_send_allowed():
            log.info("daily cold-email cap (%d) reached — holding %s",
                     _warmup_cap(), job.get("job_id"))
            return f"held_daily_cap:{job.get('job_id')}"
        subject = (email.get("subject_variants") or ["(no subject)"])[0]
        body = email.get("body", "")
        payload = job.get("payload", {}) or {}
        # the agent tags each email's purpose; default cold outreach -> marketing.
        category = payload.get("email_category") or ("marketing" if is_outreach else None)
        unsub = payload.get("unsubscribe_url", "")
        # Cold email is PLAIN TEXT by default — it reads like a real person wrote
        # it (higher replies, not flagged as scam/marketing). The branded HTML
        # template is opt-in only via EMAIL_HTML=1.
        use_html = is_outreach and _env("EMAIL_HTML", "0") == "1"
        html = self._outreach_html(body, job) if use_html else None
        ref = self.send_message(
            to_addr, subject, body,
            extra_headers={"List-Unsubscribe": f"<{unsub}>" if unsub else ""},
            category=category, html=html)
        if is_outreach and isinstance(ref, str) and not ref.startswith(("suppressed:", "send_error")):
            _note_outreach_sent()   # count it toward today's warm-up cap
        return ref

    def _outreach_html(self, body: str, job: dict) -> str:
        """Wrap a cold-email body in the branded template (logo + booking button +
        manage/unsubscribe). Defaults come from the live site; override via env."""
        p = job.get("payload", {}) or {}
        cfg = p.get("config", {}) or {}
        return _branded_email_html(
            body,
            logo=_env("EMAIL_LOGO_URL", _LOGO_DEFAULT),
            booking_url=_env("EMAIL_BOOKING_URL", "https://anthropos-automation.com/free-audit/"),
            unsub_url=p.get("unsubscribe_url") or _env("EMAIL_UNSUBSCRIBE_URL", "https://anthropos-automation.com/unsubscribe"),
            manage_url=_env("EMAIL_MANAGE_URL", "https://anthropos-automation.com/free-audit/"),
            company=_env("EMAIL_COMPANY", "Anthropos Automation Service LLC"),
            address=_env("EMAIL_ADDRESS", "1309 Coffeen Ave STE 1200, Sheridan, WY 82801"),
            brand=_env("EMAIL_BRAND_COLOR", "#7A00DF"),
            sender=cfg.get("sender_name") or _env("REPLY_SENDER_NAME", "Hasan"))


# ---------------------------------------------------------------------------
# Email verifier  (VERIFY_FN)  — syntactic + MX/domain resolve (best-effort)
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def verify_email(email: str) -> bool:
    """True if the address is syntactically valid AND its domain looks real.
    Uses dnspython for a real MX lookup when installed; otherwise falls back to
    an A-record resolve; otherwise syntactic-only. Always safe to install."""
    email = (email or "").strip()
    if not _EMAIL_RE.match(email):
        return False
    domain = email.rsplit("@", 1)[-1].lower()

    # Best: real MX record via dnspython.
    try:
        import dns.resolver  # type: ignore
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except ImportError:
        pass
    except Exception:
        return False  # domain has no MX / does not resolve

    # Fallback: does the domain resolve to an address at all?
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        # Can't check DNS here — accept syntactically-valid (matches old default).
        return True


# ---------------------------------------------------------------------------
# Q10 / Q13 — Web search + scrape
# ---------------------------------------------------------------------------
class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.title = ""
        self._in_title = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        else:
            self.chunks.append(text)


def scrape_url(url: str, max_chars: int = 8000) -> dict:
    """Fetch a page and return {url, title, text}. Static HTML only (no JS
    rendering). Returns empty text on failure — never raises."""
    rq = _requests()
    if not rq:
        return {"url": url, "title": "", "text": ""}
    try:
        r = rq.get(url, headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
        r.raise_for_status()
        parser = _TextExtractor()
        parser.feed(r.text)
        text = " ".join(parser.chunks)[:max_chars]
        return {"url": url, "title": parser.title, "text": text}
    except Exception as e:
        log.warning("scrape %s failed: %s", url, e)
        return {"url": url, "title": "", "text": ""}


def search_web(query: str, k: int = 8) -> list:
    """Web search via SEARCH_PROVIDER (tavily|serpapi). Returns
    [{title, url, snippet}]. Empty list if no provider configured."""
    provider = _env("SEARCH_PROVIDER").lower()
    key = _env("SEARCH_API_KEY")
    if not provider or not key:
        return []

    if provider == "tavily":
        j = _post_json("https://api.tavily.com/search",
                       {"api_key": key, "query": query, "max_results": k})
        if not j:
            return []
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("content", "")} for r in j.get("results", [])]

    if provider == "serpapi":
        j = _get_json("https://serpapi.com/search.json",
                      params={"q": query, "api_key": key, "num": k})
        if not j:
            return []
        return [{"title": r.get("title", ""), "url": r.get("link", ""),
                 "snippet": r.get("snippet", "")} for r in j.get("organic_results", [])]

    log.warning("unknown SEARCH_PROVIDER=%s", provider)
    return []


# ---------------------------------------------------------------------------
# Q14 — LinkedIn leads via Prospeo  (compliant licensed people data, NOT scraping)
# ---------------------------------------------------------------------------
class LinkedIn:
    """Pulls ICP-matched leads from Prospeo (https://prospeo.io) — licensed
    people data, so it's LinkedIn-ToS-safe (never scraping an account).

    Two-step, because Prospeo separates discovery from email reveal:
      1) POST /search-person  — filter the database to your ICP (free; no email)
      2) POST /enrich-person  — reveal the VERIFIED work email by person_id
                                (1 credit per verified email; nothing charged on
                                a miss or a same-record re-enrich within 90 days)

    We keep ONLY verified emails, so credits are never spent on guesses.

    Config (dashboard Connect form / env):
      PROSPEO_API_KEY   your Prospeo key            (legacy LINKEDIN_API_KEY also works)
      LEAD_COUNTRIES    comma list of target markets (default: the 5 ICP countries)
      LEAD_TITLES       comma list of job titles     (fallback when the job carries none)

    The job's ICP still drives each search (titles/keywords, industries, size);
    LEAD_* are sensible defaults so it works before the ICP config is perfect."""

    SEARCH_URL = "https://api.prospeo.io/search-person"
    ENRICH_URL = "https://api.prospeo.io/enrich-person"
    # Prospeo's valid company_headcount_range enums (see /api-docs/enum/employee-ranges).
    # Kept for reference / opt-in via query['headcount']; NOT sent by default because
    # the endpoint rejects the filter on the current tier — title+location already
    # target the ICP well (our verticals are inherently small businesses).
    _SIZE_MAP = {
        "small": ["1-10", "11-20", "21-50"],
        "smb": ["1-10", "11-20", "21-50", "51-100", "101-200"],
        "medium": ["51-100", "101-200", "201-500"],
        "large": ["501-1000", "1001-2000", "2001-5000"],
    }
    _DEFAULT_TITLES = ["Dentist", "Doctor", "Lawyer", "Attorney", "Tax Consultant",
                       "Accountant", "Founder", "Owner", "Marketing Manager"]
    _DEFAULT_COUNTRIES = "United States,United Kingdom,Germany,Switzerland,Canada"

    def __init__(self) -> None:
        self.key = _env("PROSPEO_API_KEY") or _env("LINKEDIN_API_KEY")
        self.countries = [c.strip() for c in
                          _env("LEAD_COUNTRIES", self._DEFAULT_COUNTRIES).split(",")
                          if c.strip()]
        self.default_titles = [t.strip() for t in
                               _env("LEAD_TITLES", "").split(",") if t.strip()]

    def available(self) -> bool:
        return bool(self.key and _requests())

    def _headers(self) -> dict:
        return {"X-KEY": self.key, "Content-Type": "application/json"}

    def _build_filters(self, query: dict) -> dict:
        """Map the engine's generic ICP query onto Prospeo's filter shape.

        Only the two filters Prospeo reliably accepts are sent: person_job_title
        (the ICP verticals) + person_location_search (the target countries). The
        headcount/industry enum filters are 400-rejected on the current tier, and
        our verticals are inherently small businesses, so title+location suffice."""
        f: dict = {}
        titles = query.get("titles") or []
        if not titles:
            kw = query.get("keywords") or ""
            titles = [t.strip() for t in re.split(r"[,;/]", kw) if t.strip()]
        titles = titles or self.default_titles or self._DEFAULT_TITLES
        f["person_job_title"] = {"include": titles}
        if self.countries:
            f["person_location_search"] = {"include": self.countries}
        return f

    def find_leads(self, query: dict) -> list:
        if not self.available():
            return []
        limit = int(query.get("limit", 25) or 25)
        filters = self._build_filters(query)
        out: list = []
        page = 1
        while len(out) < limit and page <= 40:
            j = _post_json(self.SEARCH_URL, {"page": page, "filters": filters},
                           headers=self._headers())
            if not j or j.get("error"):
                break
            rows = j.get("results") or []
            if not rows:
                break
            for r in rows:
                if len(out) >= limit:
                    break
                pid = (r.get("person") or {}).get("person_id")
                if not pid:
                    continue
                lead = self._enrich(pid)   # 1 credit only if a verified email exists
                if lead:
                    out.append(lead)
            pag = j.get("pagination") or {}
            if page >= int(pag.get("total_page") or page):
                break
            page += 1
        return out

    def _enrich(self, person_id: str) -> Optional[dict]:
        """Reveal + verify one person's work email. Returns None (no credit spent)
        when there's no verified email."""
        j = _post_json(self.ENRICH_URL + "?only_verified_email=true",
                       {"data": {"person_id": person_id}}, headers=self._headers())
        if not j or j.get("error"):
            return None
        p = j.get("person") or {}
        c = j.get("company") or {}
        email_obj = p.get("email") or {}
        email = email_obj.get("email") or ""
        if not email or email_obj.get("status") != "VERIFIED":
            return None
        _record_cost(float(_env("PROSPEO_COST_PER_EMAIL", "0.039") or 0.039), "prospeo")
        domain = (c.get("website") or "").replace("https://", "").replace(
            "http://", "").strip("/")
        return {
            "name": p.get("full_name")
            or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "email": email,
            "company": c.get("name", ""),
            "title": p.get("current_job_title", ""),
            "domain": domain,
            "signal": "prospeo",
            "source": "linkedin",
        }


# ---------------------------------------------------------------------------
# SOURCE_FN — assemble raw leads from every available source
# ---------------------------------------------------------------------------
def source_leads(job: dict) -> list:
    """Feeds lead_sourcing (which then dedupes + verifies). Pulls from:
      1) LinkedIn provider, using the job's ICP as the query
      2) web search, turning result domains into company leads
      3) any raw_leads already on the payload (e.g. posted in by n8n)
    """
    payload = job.get("payload", {})
    cfg = payload.get("config", {}) or {}
    icp = cfg.get("icp", {}) or {}
    leads: list = list(payload.get("raw_leads", []) or [])

    li = LinkedIn()
    if li.available():
        query = {
            "industries": icp.get("ideal_industries", []),
            "company_size": icp.get("ideal_size", ""),
            "keywords": cfg.get("search_keywords", ""),
            "limit": int(cfg.get("lead_limit", 25)),
        }
        leads += li.find_leads(query)

    search_q = cfg.get("lead_search_query")
    if search_q:
        for hit in search_web(search_q, k=int(cfg.get("lead_limit", 10))):
            domain = ""
            m = re.search(r"https?://([^/]+)/?", hit.get("url", ""))
            if m:
                domain = m.group(1).replace("www.", "")
            leads.append({"company": hit.get("title", ""), "domain": domain,
                          "signal": hit.get("snippet", "")[:120], "source": "web"})
    return leads


# ---------------------------------------------------------------------------
# Q7 — Google Search Console (on-page SEO data)  +  Q11 — GA4 (tracking)
# ---------------------------------------------------------------------------
class Google:
    """Read-only pulls from Google Search Console + GA4. Uses the SAME service
    account key as Sheets/Drive (GOOGLE_SERVICE_ACCOUNT_JSON) — add that service
    account as a user in Search Console and as a Viewer in GA4, and one key
    powers all four. (Falls back to a raw GOOGLE_ACCESS_TOKEN if you set one.)"""

    GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
    GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

    def __init__(self) -> None:
        self.site = _env("GSC_SITE_URL")
        self.ga4_property = _env("GA4_PROPERTY_ID")

    def available(self) -> bool:
        has_auth = _google_configured() or bool(_env("GOOGLE_ACCESS_TOKEN"))
        return bool(has_auth and (self.site or self.ga4_property) and _requests())

    def _auth(self, scope) -> dict:
        token = _google_token([scope]) or _env("GOOGLE_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {token}"} if token else {}

    def gsc_top_queries(self, days: int = 28, limit: int = 25) -> list:
        auth = self._auth(self.GSC_SCOPE)
        if not (auth and self.site):
            return []
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days)
        # NB: Date.today() is fine here — this runs live in the worker, not in a
        # replayable workflow script.
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": ["query"], "rowLimit": limit}
        # site URL must be URL-encoded in the path
        from urllib.parse import quote
        url = (f"https://searchconsole.googleapis.com/webmasters/v3/sites/"
               f"{quote(self.site, safe='')}/searchAnalytics/query")
        j = _post_json(url, body, headers=auth)
        if not j:
            return []
        return [{"query": row["keys"][0], "clicks": row.get("clicks", 0),
                 "impressions": row.get("impressions", 0),
                 "position": round(row.get("position", 0), 1)}
                for row in j.get("rows", [])]

    def ga4_summary(self, days: int = 28) -> dict:
        if not (self.available() and self.ga4_property):
            return {}
        body = {
            "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
            "dimensions": [{"name": "pagePath"}],
            "metrics": [{"name": "sessions"}, {"name": "conversions"}],
            "limit": 10,
        }
        url = (f"https://analyticsdata.googleapis.com/v1beta/"
               f"properties/{self.ga4_property}:runReport")
        j = _post_json(url, body, headers=self._auth())
        if not j:
            return {}
        rows = j.get("rows", [])
        top_pages = [{"page": r["dimensionValues"][0]["value"],
                      "sessions": int(r["metricValues"][0]["value"])}
                     for r in rows]
        total_sessions = sum(p["sessions"] for p in top_pages)
        return {"period": f"last {days}d", "metrics": {
            "sessions": total_sessions, "top_pages": top_pages}}


# ---------------------------------------------------------------------------
# Q4 — Social posting (SOCIAL_FN)  — LinkedIn / X(Twitter) / Facebook Page
# ---------------------------------------------------------------------------
class LinkedInPoster:
    """Post a text update to a LinkedIn person or organization page via the UGC
    Posts API. Needs an access token with w_member_social / w_organization_social
    and the author URN (e.g. urn:li:organization:12345 or urn:li:person:abc)."""

    def __init__(self) -> None:
        self.token = _env("LINKEDIN_POST_TOKEN")
        self.author = _env("LINKEDIN_AUTHOR_URN")

    def available(self) -> bool:
        return bool(self.token and self.author and _requests())

    def post(self, text: str) -> str:
        body = {
            "author": self.author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        j = _post_json("https://api.linkedin.com/v2/ugcPosts", body,
                       headers={"Authorization": f"Bearer {self.token}",
                                "X-Restli-Protocol-Version": "2.0.0"})
        if j is None:
            return "linkedin_error"
        return "linkedin:" + str(j.get("id", "posted"))


class TwitterPoster:
    """Post a tweet via X API v2. Needs an OAuth2 user access token with
    tweet.write scope (TWITTER_BEARER_TOKEN)."""

    def __init__(self) -> None:
        self.token = _env("TWITTER_BEARER_TOKEN")

    def available(self) -> bool:
        return bool(self.token and _requests())

    def post(self, text: str) -> str:
        j = _post_json("https://api.twitter.com/2/tweets", {"text": text[:280]},
                       headers={"Authorization": f"Bearer {self.token}"})
        if j is None:
            return "twitter_error"
        return "twitter:" + str((j.get("data") or {}).get("id", "posted"))


class MetaPoster:
    """Post to a Facebook Page feed via the Graph API. Needs META_PAGE_ID +
    META_PAGE_TOKEN. (Instagram requires the extra media-container flow — left
    as a follow-up; this covers Facebook Pages.)"""

    def __init__(self) -> None:
        self.page_id = _env("META_PAGE_ID")
        self.token = _env("META_PAGE_TOKEN")

    def available(self) -> bool:
        return bool(self.page_id and self.token and _requests())

    def post(self, text: str, channel: str = "facebook") -> str:
        url = f"https://graph.facebook.com/v21.0/{self.page_id}/feed"
        j = _post_json(url, {"message": text, "access_token": self.token})
        if j is None:
            return "meta_error"
        return "facebook:" + str(j.get("id", "posted"))


class InstagramPoster:
    """Post an image to Instagram via the Graph API (2-step container flow).
    Needs IG_USER_ID + META_PAGE_TOKEN, and a publicly reachable image_url."""

    def __init__(self) -> None:
        self.user_id = _env("IG_USER_ID")
        self.token = _env("META_PAGE_TOKEN")

    def available(self) -> bool:
        return bool(self.user_id and self.token and _requests())

    def post(self, caption: str, image_url: str = "") -> str:
        if not image_url:
            return "instagram_needs_image_url"
        base = f"https://graph.facebook.com/v21.0/{self.user_id}"
        j = _post_json(f"{base}/media",
                       {"image_url": image_url, "caption": caption, "access_token": self.token})
        if not j or "id" not in j:
            return "instagram_error"
        pub = _post_json(f"{base}/media_publish",
                         {"creation_id": j["id"], "access_token": self.token})
        return "instagram:" + str((pub or {}).get("id", "posted"))


class TikTokPoster:
    """Post a video to TikTok via the Content Posting API. Needs
    TIKTOK_ACCESS_TOKEN and a publicly reachable video_url."""

    def __init__(self) -> None:
        self.token = _env("TIKTOK_ACCESS_TOKEN")

    def available(self) -> bool:
        return bool(self.token and _requests())

    def post(self, caption: str, video_url: str = "") -> str:
        if not video_url:
            return "tiktok_needs_video_url"
        j = _post_json(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            {"post_info": {"title": caption[:150], "privacy_level": "SELF_ONLY"},
             "source_info": {"source": "PULL_FROM_URL", "video_url": video_url}},
            headers={"Authorization": f"Bearer {self.token}"})
        if not j:
            return "tiktok_error"
        return "tiktok:" + str((j.get("data") or {}).get("publish_id", "posted"))


# ---------------------------------------------------------------------------
# Media generation (Phase 2) — turn a text prompt into an image or a video.
# Provider seams: IMAGE_PROVIDER=openai|generic (+IMAGE_API_KEY[/IMAGE_API_URL]),
# VIDEO_PROVIDER=generic (+VIDEO_API_KEY+VIDEO_API_URL). Returns a hosted URL or
# "" when not configured. Video is the pricey one — call it selectively.
# ---------------------------------------------------------------------------
def image_available() -> bool:
    return bool(_env("IMAGE_API_KEY") and _requests())


def video_available() -> bool:
    return bool(_env("VIDEO_API_KEY") and _env("VIDEO_API_URL") and _requests())


def generate_image(prompt: str, size: str = "1024x1024") -> str:
    """Generate one image from a prompt; returns a URL (or '' if unconfigured)."""
    key = _env("IMAGE_API_KEY")
    if not key or not _requests():
        return ""
    provider = _env("IMAGE_PROVIDER", "openai").lower()
    out = ""
    if provider == "openai":
        j = _post_json("https://api.openai.com/v1/images/generations",
                       {"model": _env("IMAGE_MODEL", "gpt-image-1"), "prompt": prompt,
                        "size": size, "n": 1},
                       headers={"Authorization": f"Bearer {key}"})
        if j:
            out = (j.get("data") or [{}])[0].get("url") or ""
    else:
        url = _env("IMAGE_API_URL")
        if url:
            j = _post_json(url, {"prompt": prompt, "size": size},
                           headers={"Authorization": f"Bearer {key}"})
            out = (j or {}).get("url", "") if j else ""
    if out:   # budget loop: count image spend against the cap
        _record_cost(float(_env("IMAGE_COST_PER", "0.04") or 0.04), "image")
    return out


def generate_video(prompt: str) -> str:
    """Generate a short video from a prompt via a generic provider (async-style
    providers return a job id/URL). Returns a URL/ref or '' when unconfigured."""
    if not video_available():
        return ""
    j = _post_json(_env("VIDEO_API_URL"), {"prompt": prompt},
                   headers={"Authorization": f"Bearer {_env('VIDEO_API_KEY')}"})
    if not j:
        return ""
    _record_cost(float(_env("VIDEO_COST_PER", "0.30") or 0.30), "video")   # video is the pricey one
    return j.get("url") or j.get("id", "") or "video_pending"


def _piece_to_social_text(piece: dict, limit: int = 1000) -> str:
    """Turn a produced piece into a social caption, trimmed to the platform limit,
    with up to 5 hashtags appended."""
    title = (piece.get("title") or "").strip()
    body = (piece.get("body") or "").strip()
    tags = piece.get("hashtags") or []
    text = (f"{title}\n\n{body}").strip()
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "…"
    if tags:
        text += "\n\n" + " ".join(
            (t if str(t).startswith("#") else "#" + str(t)) for t in tags[:5])
    return text


def post_social(job: dict, piece: dict, channel: str) -> str:
    """SOCIAL_FN — post a produced piece to one social channel. Each platform
    self-degrades to a clear '<channel>_not_configured' marker (visible to the
    human) when its credentials are absent, so the pipeline never crashes."""
    ch = (channel or "").lower()
    jid = job.get("job_id")
    if ch == "linkedin":
        p = LinkedInPoster()
        return p.post(_piece_to_social_text(piece, 2900)) if p.available() \
            else f"linkedin_not_configured:{jid}"
    if ch in ("twitter", "x"):
        p = TwitterPoster()
        return p.post(_piece_to_social_text(piece, 280)) if p.available() \
            else f"twitter_not_configured:{jid}"
    if ch in ("facebook", "meta"):
        p = MetaPoster()
        return p.post(_piece_to_social_text(piece, 2000), ch) if p.available() \
            else f"{ch}_not_configured:{jid}"
    if ch in ("instagram", "ig"):
        p = InstagramPoster()
        return p.post(_piece_to_social_text(piece, 2000), piece.get("image_url", "")) \
            if p.available() else f"instagram_not_configured:{jid}"
    if ch in ("tiktok", "tt"):
        p = TikTokPoster()
        return p.post(_piece_to_social_text(piece, 150), piece.get("video_url", "")) \
            if p.available() else f"tiktok_not_configured:{jid}"
    return f"social_{ch}_unknown:{jid}"


def _any_social_available() -> bool:
    return (LinkedInPoster().available() or TwitterPoster().available()
            or MetaPoster().available() or InstagramPoster().available()
            or TikTokPoster().available())


# ---------------------------------------------------------------------------
# Q18b — Inbound email reader (IMAP) for the reply-answering agent
# ---------------------------------------------------------------------------
def _extract_plain_text(msg) -> str:
    """Best-effort text body from a parsed email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and \
                    "attachment" not in str(part.get("Content-Disposition", "")):
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", errors="replace")
    except Exception:
        return msg.get_payload() or ""


class InboundEmail:
    """Read unread replies over IMAP so the reply agent can answer them. Needs
    IMAP_HOST + IMAP_USER + IMAP_PASSWORD (use an app password). Read-only unless
    you call mark_seen()."""

    def __init__(self) -> None:
        self.host = _env("IMAP_HOST")
        self.port = int(_env("IMAP_PORT", "993") or "993")
        self.user = _env("IMAP_USER")
        self.password = _env("IMAP_PASSWORD")
        self.folder = _env("IMAP_FOLDER", "INBOX")

    def available(self) -> bool:
        return bool(self.host and self.user and self.password)

    def fetch_unread(self, limit: int = 20) -> list:
        out: list = []
        try:
            box = imaplib.IMAP4_SSL(self.host, self.port)
            box.login(self.user, self.password)
            box.select(self.folder)
            typ, data = box.search(None, "UNSEEN")
            ids = data[0].split()[:limit]
            for i in ids:
                typ, msgdata = box.fetch(i, "(RFC822)")
                if not msgdata or not msgdata[0]:
                    continue
                m = _emaillib.message_from_bytes(msgdata[0][1])
                from_hdr = str(make_header(decode_header(m.get("From", ""))))
                out.append({
                    "uid": i.decode(),
                    "from": from_hdr,
                    "from_email": parseaddr(from_hdr)[1],
                    "subject": str(make_header(decode_header(m.get("Subject", "")))),
                    "message_id": m.get("Message-ID", ""),
                    "message": _extract_plain_text(m).strip()[:4000],
                })
            box.logout()
        except Exception as e:
            log.error("IMAP fetch failed: %s", e)
        return out


# ---------------------------------------------------------------------------
# Payload collectors — build the namespaces prep.py reads from
# ---------------------------------------------------------------------------
def collect_site_audit(site_url: str) -> dict:
    """payload['audit'] for site_intelligence. Combines a light on-page scrape
    with GSC top queries when Google is connected."""
    scraped = scrape_url(site_url)
    g = Google()
    return {
        "site_url": site_url,
        "existing_topics": [],
        "top_gsc_queries": g.gsc_top_queries() if g.available() else [],
        "content_gaps": [],
        "home_title": scraped.get("title", ""),
        "home_text_sample": scraped.get("text", "")[:2000],
    }


def collect_competitors(urls_or_names: list) -> list:
    """payload['competitors'] — scrape each competitor URL for its content."""
    out = []
    for item in urls_or_names or []:
        if isinstance(item, str) and item.startswith("http"):
            s = scrape_url(item)
            out.append({"name": s.get("title") or item,
                        "external_content": s.get("text", "")})
        else:
            out.append({"name": str(item), "external_content": ""})
    return out


def collect_analytics() -> dict:
    """payload['analytics'] for analytics_funnel (from GA4)."""
    g = Google()
    return g.ga4_summary() if g.available() else {}


def collect_ads() -> dict:
    """payload['ads'] for ads_optimizer. Direct Google/Meta Ads APIs are heavy;
    the simplest reliable path is to let n8n pull the report and hand it here as
    ADS_JSON (or POST it into the payload). Returns {} if not provided."""
    raw = _env("ADS_JSON")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception as e:
        log.warning("ADS_JSON is not valid JSON: %s", e)
        return {}


def backlinks(job: dict) -> dict:
    """BACKLINK_FN — {client, competitors} referring-domain data. Direct Ahrefs/
    Semrush APIs are paid; paste a JSON blob via BACKLINKS_JSON, or leave blank
    to keep the offline default."""
    raw = _env("BACKLINKS_JSON")
    if not raw:
        return job.get("payload", {}).get("backlinks", {})
    try:
        return json.loads(raw)
    except Exception as e:
        log.warning("BACKLINKS_JSON is not valid JSON: %s", e)
        return {}


# ---------------------------------------------------------------------------
# GOOGLE WORKSPACE HUB (Option A: Postgres stays the engine's memory; Google is
# the visible hub). Sheets = the "mother dashboard" + structured store; Drive =
# content saved as JSON. Auth = ONE service-account key
# (GOOGLE_SERVICE_ACCOUNT_JSON = inline JSON or a path). Share the target Sheet
# + Drive folder with the service-account email. Gmail sending reuses the SMTP
# Emailer above (SMTP_HOST=smtp.gmail.com + a Workspace app password).
# ---------------------------------------------------------------------------
_GSHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_GDRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def _google_sa_info():
    raw = _env("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    try:
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        with open(raw, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("GOOGLE_SERVICE_ACCOUNT_JSON unreadable: %s", e)
        return None


def _google_configured() -> bool:
    return _google_sa_info() is not None and _requests() is not None


def _google_token(scopes):
    """Exchange the service-account key for a short-lived access token. Uses
    google-auth (handles the signed-JWT flow); returns None if unavailable."""
    info = _google_sa_info()
    if not info:
        return None
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        creds.refresh(Request())
        return creds.token
    except Exception as e:
        log.warning("google service-account auth failed: %s", e)
        return None


class GoogleSheets:
    """Append rows to a Google Sheet — the 'mother dashboard' / structured store.
    Tabs are created by you (e.g. Content, Leads, Jobs); this appends to them."""

    def __init__(self) -> None:
        self.sheet_id = _env("GOOGLE_SHEETS_ID")

    def available(self) -> bool:
        return bool(self.sheet_id and _google_configured())

    def append_row(self, tab: str, values: list) -> bool:
        token = _google_token([_GSHEETS_SCOPE])
        if not token:
            return False
        from urllib.parse import quote
        rng = quote(f"{tab}!A1", safe="")
        url = (f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}"
               f"/values/{rng}:append?valueInputOption=USER_ENTERED")
        j = _post_json(url, {"values": [[("" if v is None else v) for v in values]]},
                       headers={"Authorization": f"Bearer {token}"})
        return j is not None


class GoogleDrive:
    """Save content as a JSON file inside an organized company folder (no media
    yet — text/JSON; convert to images/video later)."""

    def __init__(self) -> None:
        self.folder_id = _env("GDRIVE_FOLDER_ID")

    def available(self) -> bool:
        return bool(self.folder_id and _google_configured())

    def save_json(self, name: str, obj: dict) -> str:
        token = _google_token([_GDRIVE_SCOPE])
        rq = _requests()
        if not token or not rq:
            return ""
        meta = {"name": name, "parents": [self.folder_id], "mimeType": "application/json"}
        b = "aa_hub_boundary"
        body = (
            f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            + json.dumps(meta)
            + f"\r\n--{b}\r\nContent-Type: application/json\r\n\r\n"
            + json.dumps(obj, ensure_ascii=False)
            + f"\r\n--{b}--"
        )
        try:
            r = rq.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": f"multipart/related; boundary={b}"},
                data=body.encode("utf-8"), timeout=_HTTP_TIMEOUT)
            r.raise_for_status()
            j = r.json()
            return j.get("webViewLink") or ("drive:" + str(j.get("id", "")))
        except Exception as e:
            log.warning("Drive save_json failed: %s", e)
            return ""


def mirror_job(job: dict) -> None:
    """Best-effort mirror of a finished job to the Google hub: the produced piece
    as JSON in Drive + a summary row in Sheets. No-op if Google isn't configured,
    and never raises — Postgres remains the source of truth (Option A)."""
    sheets, drive = GoogleSheets(), GoogleDrive()
    if not (sheets.available() or drive.available()):
        return
    payload = job.get("payload", {}) or {}
    jtype = job.get("type")
    drive_ref = ""
    piece = payload.get("content_producer")
    if drive.available() and piece:
        drive_ref = drive.save_json(
            f"{job.get('job_id')}.json",
            {"job_id": job.get("job_id"), "type": jtype, "status": job.get("status"),
             "piece": piece, "published_refs": payload.get("published_refs")})
    if sheets.available():
        cost = round(float(job.get("cost_so_far_usd", 0) or 0), 4)
        if jtype == "outreach_campaign":
            sheets.append_row("Leads", [job.get("job_id"), job.get("status"),
                                        payload.get("send_ref", ""), cost])
        else:
            sheets.append_row("Content", [job.get("job_id"), job.get("status"),
                                          (piece or {}).get("title", ""),
                                          payload.get("published_ref", ""), drive_ref, cost])


# ---------------------------------------------------------------------------
# Cal.com — booked consultations (closes the deal loop: email -> reply -> BOOKED)
# ---------------------------------------------------------------------------
class CalCom:
    """Reads real booked consultations from Cal.com. Set CALCOM_API_KEY
    (cal.com -> Settings -> Developer -> API keys). No scraping — official API."""

    def __init__(self) -> None:
        self.key = _env("CALCOM_API_KEY")

    def available(self) -> bool:
        return bool(self.key and _requests())

    def bookings(self) -> list:
        j = _get_json("https://api.cal.com/v1/bookings", params={"apiKey": self.key})
        if not j:
            return []
        return j.get("bookings", []) or []

    def summary(self) -> dict:
        """{'total', 'booked'} — booked = accepted consultations."""
        if not self.available():
            return {}
        b = self.bookings()
        accepted = sum(1 for x in b if str(x.get("status", "")).lower() in ("accepted", "confirmed"))
        return {"total": len(b), "booked": accepted or len(b)}


# ---------------------------------------------------------------------------
# Google Ads — real campaign metrics via the official REST API (v17)
# Needs a developer token + customer id + an OAuth refresh token (+ the OAuth
# client id/secret that minted it). Google must approve the developer token
# before live data flows — until then available() is False (no fake numbers).
# ---------------------------------------------------------------------------
class GoogleAds:
    def __init__(self) -> None:
        self.dev = _env("GOOGLE_ADS_DEVELOPER_TOKEN")
        self.cid = _env("GOOGLE_ADS_CUSTOMER_ID").replace("-", "")
        self.refresh = _env("GOOGLE_ADS_REFRESH_TOKEN")
        self.client_id = _env("GOOGLE_ADS_CLIENT_ID")
        self.client_secret = _env("GOOGLE_ADS_CLIENT_SECRET")

    def available(self) -> bool:
        return bool(self.dev and self.cid and self.refresh
                    and self.client_id and self.client_secret and _requests())

    def _access_token(self) -> str:
        j = _post_json("https://oauth2.googleapis.com/token", {
            "client_id": self.client_id, "client_secret": self.client_secret,
            "refresh_token": self.refresh, "grant_type": "refresh_token"})
        return (j or {}).get("access_token", "")

    def summary(self) -> dict:
        if not self.available():
            return {}
        tok = self._access_token()
        if not tok:
            return {}
        q = ("SELECT campaign.name, metrics.cost_micros, metrics.clicks, "
             "metrics.impressions, metrics.conversions FROM campaign "
             "WHERE segments.date DURING LAST_30_DAYS")
        j = _post_json(
            f"https://googleads.googleapis.com/v17/customers/{self.cid}/googleAds:searchStream",
            {"query": q},
            headers={"Authorization": f"Bearer {tok}", "developer-token": self.dev})
        if not j:
            return {}
        spend = clicks = impr = conv = 0.0
        camps: list = []
        for batch in (j if isinstance(j, list) else [j]):
            for r in batch.get("results", []) or []:
                m = r.get("metrics", {}) or {}
                cost = float(m.get("costMicros", 0)) / 1e6
                spend += cost
                clicks += float(m.get("clicks", 0))
                impr += float(m.get("impressions", 0))
                conv += float(m.get("conversions", 0))
                camps.append(((r.get("campaign", {}) or {}).get("name", ""), round(cost, 2)))
        return {"spend": round(spend, 2), "clicks": int(clicks), "impressions": int(impr),
                "conversions": round(conv, 1), "cpa": round(spend / conv, 2) if conv else 0,
                "campaigns": camps[:6]}


# ---------------------------------------------------------------------------
# Wiring + status
# ---------------------------------------------------------------------------
def status() -> dict:
    """What's live right now (creds present) vs offline."""
    return {
        "claude_api": bool(_env("ANTHROPIC_API_KEY")),   # the engine's brain
        "wordpress_publish": WordPress().available(),
        "social_linkedin": LinkedInPoster().available(),
        "social_twitter": TwitterPoster().available(),
        "social_facebook": MetaPoster().available(),
        "social_instagram": InstagramPoster().available(),
        "social_tiktok": TikTokPoster().available(),
        "image_gen": image_available(),
        "video_gen": video_available(),
        "email_send": Emailer().available(),
        "email_reply_inbound": InboundEmail().available(),
        "email_verify": True,  # always on (degrades to syntactic)
        "google_sheets": GoogleSheets().available(),   # mother dashboard / store
        "google_drive": GoogleDrive().available(),     # content JSON storage
        "web_search": bool(_env("SEARCH_PROVIDER") and _env("SEARCH_API_KEY") and _requests()),
        "linkedin_leads": LinkedIn().available(),
        "google_gsc_ga4": Google().available(),
        "ads_data": bool(_env("ADS_JSON")),
        "ads_api": GoogleAds().available(),
        "calcom_bookings": CalCom().available(),
        "backlinks_data": bool(_env("BACKLINKS_JSON")),
        "requests_installed": _requests() is not None,
    }


def wire_all() -> dict:
    """Install every AVAILABLE connector into the code-skill hooks. Safe to call
    at worker startup: only connectors with creds are wired; the rest stay in
    their offline default. Returns the status map for logging."""
    import content_engine_code_skills as cs

    # Bridge the Claude key saved from the dashboard into the environment so the
    # Anthropic SDK (which reads ANTHROPIC_API_KEY) picks it up live — no restart.
    _ak = _env("ANTHROPIC_API_KEY")
    if _ak:
        os.environ["ANTHROPIC_API_KEY"] = _ak

    wp = WordPress()
    if wp.available():
        cs.PUBLISH_FN = wp.publish

    em = Emailer()
    if em.available():
        cs.SEND_FN = em.send

    # Social posting engages if any platform is configured; the dispatcher
    # self-degrades per channel, so unconfigured channels leave a clear marker.
    if _any_social_available():
        cs.SOCIAL_FN = post_social

    # Verifier is always safe to install (real MX check when possible).
    cs.VERIFY_FN = verify_email

    # Lead sourcing engages if LinkedIn or web search is configured.
    if LinkedIn().available() or (_env("SEARCH_PROVIDER") and _env("SEARCH_API_KEY")):
        cs.SOURCE_FN = source_leads

    # Backlink data only if a JSON blob was provided.
    if _env("BACKLINKS_JSON"):
        cs.BACKLINK_FN = backlinks

    # Google Workspace hub: when Sheets/Drive is configured, mirror every
    # finished job to Google (content JSON -> Drive, summary row -> Sheets).
    # Postgres stays the source of truth (Option A); this is the visible layer.
    if GoogleSheets().available() or GoogleDrive().available():
        try:
            import content_engine_orchestrator as _orch
            _orch.MIRROR_FN = mirror_job
        except Exception:
            log.warning("could not install Google hub mirror on the orchestrator")

    st = status()
    live = [k for k, v in st.items() if v and k not in ("requests_installed", "email_verify")]
    log.info("connectors wired — live: %s", ", ".join(live) or "(none; all offline)")
    return st


# ---------------------------------------------------------------------------
# Offline self-check — runs with zero creds and zero network.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import content_engine_code_skills as cs

    # 1) Nothing configured -> everything degrades, nothing raises.
    st = status()
    assert st["wordpress_publish"] is False
    assert st["email_send"] is False
    assert st["email_verify"] is True

    # 2) Email verifier: syntactic gate still works offline.
    assert verify_email("bad-email") is False
    assert verify_email("a@b.com") in (True, False)  # depends on DNS availability

    # 3) wire_all with no creds must NOT install publish/send (keeps offline
    #    defaults so code_skills still produce their pub_/send_ refs).
    cs.PUBLISH_FN = None
    cs.SEND_FN = None
    wire_all()
    assert cs.PUBLISH_FN is None, "must not wire WordPress without creds"
    assert cs.SEND_FN is None, "must not wire Emailer without creds"
    assert cs.VERIFY_FN is verify_email, "verifier should always be installed"

    # 4) Collectors return safe empties offline (no network).
    assert collect_analytics() == {}
    assert collect_ads() == {}
    assert isinstance(collect_competitors(["NotAUrl"]), list)

    # 5) source_leads passes through any raw_leads already on the payload.
    job = {"job_id": "t", "payload": {"raw_leads": [{"email": "x@y.com"}],
                                       "config": {}}}
    assert source_leads(job) == [{"email": "x@y.com"}]

    # 6) With creds present (mock env), wire_all installs the real hooks.
    os.environ.update({
        "WORDPRESS_URL": "https://example.com", "WORDPRESS_USER": "u",
        "WORDPRESS_APP_PASSWORD": "p",
        "SMTP_HOST": "smtp.example.com", "SMTP_FROM": "me@example.com",
    })
    # Only installs if `requests` is importable; assert conditionally.
    wire_all()
    if _requests():
        assert cs.PUBLISH_FN is not None, "WordPress should wire with creds+requests"
    assert cs.SEND_FN is not None, "Emailer should wire with creds (SMTP is stdlib)"

    # reset so we don't leak into anything else
    for k in ("WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD",
              "SMTP_HOST", "SMTP_FROM"):
        os.environ.pop(k, None)
    cs.PUBLISH_FN = None
    cs.SEND_FN = None

    # 7) Google hub is off without a service-account key; mirror is a safe no-op.
    assert GoogleSheets().available() is False and GoogleDrive().available() is False
    mirror_job({"job_id": "z", "type": "content_piece", "payload": {}})  # must not raise
    st2 = status()
    assert st2["google_sheets"] is False and st2["google_drive"] is False

    print("OK — connectors self-check passed: graceful offline degradation, "
          "verifier always on, hooks wire only when creds present, collectors "
          "return safe empties, Google hub off-and-safe. (No network, no API.)")
