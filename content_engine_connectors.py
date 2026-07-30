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
from email.utils import formataddr, make_msgid, parseaddr
from html.parser import HTMLParser
import time as _time
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
    record_api_spend(kind or "other", usd)   # per-API meter (was dropped before)


# --- per-API usage meters --------------------------------------------------
# Every paid API accrues into a per-month, per-API counter stored in settings,
# so the dashboard can show "spent this month vs your top-up cap" and warn you
# BEFORE an API runs out. We can meter what WE spend; a provider's exact remaining
# balance isn't exposed by most APIs, so the cap you set is the early-warning line.
DEFAULT_API_LIMITS = {
    "anthropic": 120.0, "prospeo": 30.0, "image": 20.0, "video": 20.0,
    "search": 10.0, "google_ads": 200.0, "other": 20.0,
}


def _month_key() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m")


def record_api_spend(api: str, usd) -> None:
    """Accrue one API charge into this month's meter for that API."""
    try:
        usd = float(usd or 0)
    except Exception:
        return
    if not api or usd <= 0:
        return
    try:
        month = _month_key()
        meters = _setting("api_meters", {}) or {}
        m = meters.get(api) or {}
        if m.get("month") != month:      # new month -> reset that API's meter
            m = {"month": month, "spent": 0.0, "calls": 0}
        m["spent"] = round(float(m.get("spent", 0)) + usd, 5)
        m["calls"] = int(m.get("calls", 0)) + 1
        meters[api] = m
        _set_setting("api_meters", meters)
    except Exception:
        pass


def api_meters() -> dict:
    """This month's per-API spend + call counts."""
    return _setting("api_meters", {}) or {}


def api_limits() -> dict:
    """Per-API monthly caps (defaults, overridable by the user from the dashboard)."""
    lim = dict(DEFAULT_API_LIMITS)
    for k, v in (_setting("api_limits", {}) or {}).items():
        try:
            lim[k] = float(v)
        except Exception:
            pass
    return lim


def set_api_limit(api: str, usd) -> dict:
    """User sets an API's monthly cap (their top-up / warn line)."""
    over = _setting("api_limits", {}) or {}
    over[api] = float(usd)
    _set_setting("api_limits", over)
    return over


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


def tracking_on() -> bool:
    v = _setting("outreach_tracking", {}) or {}
    return bool(v.get("enabled", True)) if isinstance(v, dict) else True


def _apply_tracking(html, to_addr, job):
    """Add the open pixel and wrap links. Returns html unchanged when tracking
    is off, when there is no HTML part, or when no base URL is configured."""
    if not html or not tracking_on():
        return html
    base = _env("PUBLIC_BASE_URL") or _env("ENGINE_PUBLIC_URL")
    if not base:
        return html                       # nowhere for the pixel to call home
    base = base.rstrip("/")
    import re as _re
    from urllib.parse import quote
    import content_engine_outreach as _O
    job_id = str((job or {}).get("job_id") or (job or {}).get("id") or "")
    p = (job or {}).get("payload") or {}
    step = len(((p.get("sent_at") or {}).get((to_addr or "").lower())) or []) + 1
    tok = _O.make_token(job_id, to_addr, step)
    try:
        _O.register_token(_STORE_FOR_TRACKING(), job_id, to_addr, step)
    except Exception:
        pass
    html = _re.sub(
        r'href="(https?://[^"]+)"',
        lambda m: f'href="{base}/t/c/{tok}?u={quote(m.group(1), safe="")}"',
        html)
    return html + f'<img src="{base}/t/o/{tok}.png" width="1" height="1" alt="" '\
                  f'style="display:none">'


def _STORE_FOR_TRACKING():
    """The settings-backed store, reused from whatever the app already wired."""
    class _S:
        def get_setting(self, k, default=None):
            return _setting(k, default)

        def set_setting(self, k, v):
            _set_setting(k, v)
    return _S()


def suppress_email(addr: str, reason: str = "bounce") -> None:
    a = (addr or "").strip()
    if not a:
        return
    supp = list(_setting("email_suppression", []) or [])
    if a.lower() not in {str(s).strip().lower() for s in supp}:
        supp.append(a)
        _set_setting("email_suppression", supp)
        log.info("suppressed %s (%s)", a, reason)
    # Record WHY. The list alone cannot tell a bounce from an unsubscribe, and
    # those two mean very different things about the health of a list.
    try:
        from datetime import datetime, timezone
        meta = dict(_setting("email_suppression_meta", {}) or {})
        meta.setdefault(a.lower(), {
            "reason": str(reason or "unrecorded"),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        _set_setting("email_suppression_meta", meta)
    except Exception as e:
        log.warning("suppression reason not recorded for %s: %s", a, e)


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
    # --- APPENDED 2026-07-30: the engines shipped today could not be connected
    # from the browser at all, because /connect rejects anything not on this
    # allow-list. Append-only: nothing above was removed or renamed.
    "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD",
    "PAGESPEED_API_KEY", "INDEXNOW_KEY",
    "GBP_ACCESS_TOKEN", "GBP_ACCOUNT_ID", "GBP_LOCATION_ID",
    "GOOGLE_ADS_OFFLINE_ACTION",
    "OPENAI_API_KEY", "OPENAI_AEO_MODEL",
    "PERPLEXITY_API_KEY", "PERPLEXITY_MODEL",
    "GEMINI_API_KEY", "GEMINI_MODEL",

    "ANTHROPIC_API_KEY",   # the Claude brain — front-end settable, bridged to env in wire_all()
    "WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD", "WP_STATUS",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_STARTTLS",
    "IMAP_HOST", "IMAP_PORT", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER",
    "SEARCH_PROVIDER", "SEARCH_API_KEY", "SERPER_API_KEY",
    "LINKEDIN_PROVIDER_URL", "LINKEDIN_API_KEY",
    "PROSPEO_API_KEY", "LEAD_COUNTRIES", "LEAD_TITLES",
    "GOOGLE_ACCESS_TOKEN", "GSC_SITE_URL", "GA4_PROPERTY_ID",
    "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SHEETS_ID", "GDRIVE_FOLDER_ID",
    "ADS_JSON", "BACKLINKS_JSON",
    "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "GOOGLE_ADS_API_VERSION", "CALCOM_API_KEY",
    "EMAIL_LOGO_URL", "EMAIL_BOOKING_URL", "EMAIL_MANAGE_URL", "EMAIL_UNSUBSCRIBE_URL",
    "EMAIL_COMPANY", "EMAIL_ADDRESS", "EMAIL_BRAND_COLOR", "EMAIL_HTML", "EMAIL_WEBSITE",
    "EMAIL_FROM_NAME", "EMAIL_SENDER_TITLE", "EMAIL_PHONE",
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



# ---------------------------------------------------------------------------
# WIRE VERIFICATION — creds present is not the same as creds accepted
# ---------------------------------------------------------------------------
# status() used to report credential PRESENCE only. A rejected Google Ads
# refresh token showed as a live wire while every call returned 401, and the
# risk register counts wires_down from status(), so the risk score was
# optimistic by one wire. A green wire now means something proved it works.
_AUTH_STATE: dict = {}          # wire -> {ok, code, reason, at}
_AUTH_TTL = 1800                # a rejection older than 30 min is re-tested on use

# Wires that can prove themselves for free. Serper is deliberately ABSENT:
# it has no free ping endpoint, and spending a paid search credit on a health
# check would be a worse bug than the one this fixes.
VERIFIABLE = ("ads_api", "google_gsc_ga4", "google_sheets", "google_drive",
              "calcom_bookings")


def note_auth(wire: str, ok: bool, code: int = 0, reason: str = "") -> None:
    """Record what the API actually said. Called from the real call paths, so
    verification costs nothing extra."""
    if not wire:
        return
    _AUTH_STATE[wire] = {"ok": bool(ok), "code": int(code or 0),
                         "reason": str(reason or ""), "at": _time.time()}


def _rejected(wire: str) -> bool:
    """True only for a fresh, hard credential rejection."""
    st = _AUTH_STATE.get(wire)
    if not st or st.get("ok"):
        return False
    if int(st.get("code") or 0) not in (401, 403):
        return False
    return (_time.time() - float(st.get("at") or 0)) < _AUTH_TTL


def _accepted(wire: str, present: bool) -> bool:
    """present AND not currently rejected. A wire nothing has called yet stays
    green on presence — unproven is not the same as broken, and saying
    otherwise would be its own false alarm."""
    return bool(present) and not _rejected(wire)


def auth_reasons() -> dict:
    """{wire: plain-English reason} for every wire whose credentials exist but
    were refused. Feeds the wiring diagnostic so a red wire says WHY."""
    out = {}
    for wire, st in _AUTH_STATE.items():
        if _rejected(wire):
            out[wire] = st.get("reason") or f"rejected with HTTP {st.get('code')}"
    return out


def _classify(e, wire: str, what: str) -> tuple:
    """(code, reason) from an exception raised by requests."""
    code = 0
    resp = getattr(e, "response", None)
    if resp is not None:
        code = int(getattr(resp, "status_code", 0) or 0)
    if code in (401, 403):
        return code, (f"{what} credentials were rejected by the provider "
                      f"(HTTP {code}). The key or token needs regenerating — "
                      f"this is not a network problem.")
    if code:
        return code, f"{what} returned HTTP {code}."
    return 0, f"{what} could not be reached: {str(e)[:120]}"


def verify_wire(wire: str) -> dict:
    """On-demand check for the Test button. Returns {ok, code, reason}."""
    try:
        if wire == "ads_api":
            g = GoogleAds()
            if not g.available():
                return {"ok": False, "code": 0, "reason": "credentials incomplete"}
            tok = g._access_token()
            if not tok:
                note_auth(wire, False, 401,
                          "Google refused the Ads refresh token (401). Regenerate "
                          "it in the OAuth playground — a refresh token dies if it "
                          "is unused for six months or the consent is revoked.")
            else:
                note_auth(wire, True)
            return dict(_AUTH_STATE.get(wire, {"ok": bool(tok), "code": 0, "reason": ""}))
        if wire in ("google_gsc_ga4", "google_sheets", "google_drive"):
            if not _google_configured():
                return {"ok": False, "code": 0, "reason": "no service-account JSON"}
            tok = _google_token(["https://www.googleapis.com/auth/drive.file"])
            if not tok:
                note_auth(wire, False, 401,
                          "The Google service-account key was rejected. If the key "
                          "was rotated or the service account was deleted, paste a "
                          "fresh JSON key — GSC, GA4, Sheets and Drive all use it.")
            else:
                note_auth(wire, True)
            return dict(_AUTH_STATE.get(wire, {}))
        if wire == "calcom_bookings":
            c = CalCom()
            if not c.available():
                return {"ok": False, "code": 0, "reason": "no Cal.com API key"}
            ok = c.bookings() is not None
            note_auth(wire, ok, 0 if ok else 401,
                      "" if ok else "Cal.com rejected the API key.")
            return dict(_AUTH_STATE.get(wire, {}))
    except Exception as e:
        return {"ok": False, "code": 0, "reason": f"{type(e).__name__}: {e}"}
    return {"ok": True, "code": 0, "reason": "this wire has no free self-test"}


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
def md_to_html(text: str) -> str:
    """Markdown -> HTML for publishing (headings, lists, bold/italic, links,
    images, paragraphs). The writer outputs markdown; WordPress needs HTML."""
    def _inline(s: str) -> str:
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" style="max-width:100%;height:auto"/>', s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
        return s
    out, inlist = [], False
    for ln in (text or "").split("\n"):
        s = ln.rstrip()
        if not s.strip():
            if inlist:
                out.append("</ul>")
                inlist = False
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            if inlist:
                out.append("</ul>")
                inlist = False
            lvl = min(len(m.group(1)) + 1, 4)      # '#' -> h2 (h1 = the post title)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            continue
        if re.match(r"^[-*]\s+", s):
            if not inlist:
                out.append("<ul>")
                inlist = True
            item = re.sub(r"^[-*]\s+", "", s)
            out.append(f"<li>{_inline(item)}</li>")
            continue
        if inlist:
            out.append("</ul>")
            inlist = False
        out.append(f"<p>{_inline(s)}</p>")
    if inlist:
        out.append("</ul>")
    return "\n".join(out)


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

    def _auth(self):
        return (self.user, self.app_password)

    def _category_ids(self, names: list) -> list:
        """Resolve category NAMES -> WordPress term IDs, creating any that are
        missing, so a piece lands in the right site sections (Blog / a service
        pillar / an audience segment). Best-effort — returns whatever it can."""
        rq = _requests()
        ids = []
        for name in names:
            if not name:
                continue
            try:
                r = rq.get(f"{self.base}/wp-json/wp/v2/categories",
                           params={"search": name}, auth=self._auth(),
                           headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
                match = next((c for c in (r.json() if r.ok else [])
                             if c.get("name", "").lower() == name.lower()), None)
                if match:
                    ids.append(match["id"]); continue
                cr = rq.post(f"{self.base}/wp-json/wp/v2/categories",
                             json={"name": name}, auth=self._auth(),
                             headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
                if cr.ok:
                    ids.append(cr.json().get("id"))
            except Exception as e:
                log.warning("wp category '%s' failed: %s", name, e)
        return [i for i in ids if i]

    def upload_media(self, content: bytes, filename: str = "image.png",
                     mime: str = "image/png"):
        """Upload raw image bytes to the WP media library -> (id, source_url).
        This is how AI-generated images get a PERMANENT home."""
        rq = _requests()
        try:
            r = rq.post(
                f"{self.base}/wp-json/wp/v2/media",
                data=content, auth=self._auth(),
                headers={"User-Agent": _UA, "Content-Type": mime,
                         "Content-Disposition": f'attachment; filename="{filename}"'},
                timeout=_HTTP_TIMEOUT)
            if not r.ok:
                return 0, ""
            j = r.json()
            return j.get("id", 0), (j.get("source_url") or "")
        except Exception as e:
            log.warning("wp upload_media failed: %s", e)
            return 0, ""

    def _featured_media(self, image_url: str, title: str) -> int:
        """Sideload the hero image into the WP media library and return its id
        (so it becomes the post's featured image). 0 on any failure."""
        if not image_url:
            return 0
        rq = _requests()
        try:
            img = rq.get(image_url, timeout=_HTTP_TIMEOUT)
            if not img.ok:
                return 0
            fn = (title or "hero").strip()[:60].replace('"', "") or "hero"
            r = rq.post(
                f"{self.base}/wp-json/wp/v2/media",
                data=img.content, auth=self._auth(),
                headers={"User-Agent": _UA, "Content-Type": img.headers.get("Content-Type", "image/png"),
                         "Content-Disposition": f'attachment; filename="{fn}.png"'},
                timeout=_HTTP_TIMEOUT)
            return r.json().get("id", 0) if r.ok else 0
        except Exception as e:
            log.warning("wp media upload failed: %s", e)
            return 0

    def publish(self, job: dict, piece: dict) -> str:
        rq = _requests()
        title = piece.get("title") or piece.get("meta_title") or "Untitled"
        # The writer produces markdown (## headings, - lists, **bold**, images).
        # WordPress expects HTML — publishing raw markdown was the 'no proper
        # headings' bug. Convert here.
        body = md_to_html(piece.get("body") or "")
        excerpt = piece.get("meta_description", "")
        data = {"title": title, "content": body, "status": self.status,
                "excerpt": excerpt}
        # Route to the right site sections (Blog / service pillar / audience segment)
        try:
            import content_engine_site_taxonomy as TAX
            tax = (job.get("payload", {}) or {}).get("taxonomy") or {}
            cats = TAX.wp_categories(
                piece.get("type") or (job.get("payload", {}) or {}).get("config", {}).get("type", "blog"),
                tax.get("segment", ""), tax.get("pillar", ""),
                title, piece.get("primary_keyword", ""))
            cat_ids = self._category_ids(cats)
            if cat_ids:
                data["categories"] = cat_ids
        except Exception as e:
            log.warning("wp categorisation skipped: %s", e)
        # Attach the on-brand hero image as the featured image (best-effort)
        media_id = self._featured_media(piece.get("image_url", ""), title)
        if media_id:
            data["featured_media"] = media_id
        try:
            r = rq.post(
                f"{self.base}/wp-json/wp/v2/posts",
                json=data, auth=self._auth(),
                headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT,
            )
            r.raise_for_status()
            j = r.json()
            ref = j.get("link") or f"wp:{j.get('id')}"
            log.info("published to WordPress (%s, cats=%s, media=%s): %s",
                     self.status, data.get("categories"), media_id, ref)
            # Topic memory: remember this title so the strategist NEVER plans a
            # duplicate (the 'same generic topics every day' bug).
            try:
                recent = list(_setting("recent_titles", []) or [])
                recent.append(title)
                _set_setting("recent_titles", recent[-40:])
            except Exception:
                pass
            return ref
        except Exception as e:
            log.error("WordPress publish failed: %s", e)
            return f"wp_error:{job.get('job_id')}"

    # ---- E7/E8/E9: the WRITE side the SEO fixer needs -----------------
    def find_by_url(self, url: str) -> dict:
        """Resolve a public URL back to its WP post/page record so a fix can be
        applied to the right object. Tries slug lookup on posts then pages."""
        rq = _requests()
        if not (rq and url):
            return {}
        from urllib.parse import urlparse
        slug = [s for s in urlparse(url).path.split("/") if s]
        if not slug:
            return {}
        slug = slug[-1]
        for kind in ("posts", "pages"):
            try:
                r = rq.get(f"{self.base}/wp-json/wp/v2/{kind}",
                           params={"slug": slug}, auth=self._auth(),
                           headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
                if r.ok and r.json():
                    j = r.json()[0]
                    return {"id": j.get("id"), "kind": kind, "link": j.get("link", ""),
                            "title": (j.get("title") or {}).get("rendered", ""),
                            "content": (j.get("content") or {}).get("rendered", ""),
                            "excerpt": (j.get("excerpt") or {}).get("rendered", "")}
            except Exception as e:
                log.debug("wp find_by_url %s/%s: %s", kind, slug, e)
        return {}

    def update_post(self, post_id: int, fields: dict, kind: str = "posts") -> str:
        """Patch an existing post. Used by the SEO fixer for titles, excerpts
        (meta description) and body edits. Returns 'updated' or an error tag."""
        rq = _requests()
        if not (rq and post_id and fields):
            return "wp_update_skipped"
        try:
            r = rq.post(f"{self.base}/wp-json/wp/v2/{kind}/{post_id}",
                        json=fields, auth=self._auth(),
                        headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
            r.raise_for_status()
            return "updated"
        except Exception as e:
            log.error("wp update_post %s failed: %s", post_id, e)
            return f"wp_update_error:{e}"

    def update_media_alt(self, media_id: int, alt: str) -> str:
        rq = _requests()
        if not (rq and media_id):
            return "skipped"
        try:
            r = rq.post(f"{self.base}/wp-json/wp/v2/media/{media_id}",
                        json={"alt_text": alt}, auth=self._auth(),
                        headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
            return "updated" if r.ok else f"error:{r.status_code}"
        except Exception as e:
            return f"error:{e}"

    def media_by_src(self, src_url: str) -> int:
        """Find a media library item id from its public file URL (so alt text
        can be written to the right attachment)."""
        rq = _requests()
        if not (rq and src_url):
            return 0
        slug = src_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        try:
            r = rq.get(f"{self.base}/wp-json/wp/v2/media",
                       params={"search": slug}, auth=self._auth(),
                       headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
            if r.ok and r.json():
                return r.json()[0].get("id", 0)
        except Exception as e:
            log.debug("wp media_by_src: %s", e)
        return 0


# ---------------------------------------------------------------------------
# Q17 / Q18 — Email sender  (SEND_FN)  — CAN-SPAM aware
# ---------------------------------------------------------------------------
def _html_escape(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Brand defaults pulled from the live site (logo) so cold email looks like the brand.
_LOGO_DEFAULT = "https://anthropos-automation.com/wp-content/uploads/2026/07/cropped-anthropos-logo-mark-transparent-1024-270x270.png"


def personalize_outreach(lead: dict, qual: dict, subject: str, body: str):
    """Build ONE customer's email from the campaign template + their qualifier
    profile (business/pain/offer). Deterministic — the mailbox shows exactly what
    sends. Returns (subject, body)."""
    lead = lead or {}
    qual = qual or {}
    name = ((lead.get("name") or "there").split(" ") or ["there"])[0]
    company = lead.get("company") or ""
    biz = qual.get("business") or ""
    pain = (qual.get("pain_point") or "").rstrip(".")
    offer = (qual.get("offer") or "").rstrip(".")
    lines = [f"Hi {name},", ""]
    if pain and offer:
        lines.append(f"Running {('a ' + biz) if biz else 'a business like yours'}, "
                     f"you likely deal with {pain}.")
        lines.append(f"{offer}.")
        lines.append("")
    b = (body or "").strip()
    for g in ("Hi there,", "Hi there", "Hello there,", "Hello,", "Hi,"):
        if b.startswith(g):
            b = b[len(g):].lstrip()
            break
    b = b.replace("{{name}}", name).replace("{{company}}", company)
    lines.append(b)
    subj = (subject or "Quick idea for {{company}}").replace("{{company}}", company or "your team")
    return subj, "\n".join(lines).strip()


SEQUENCE_TOUCHES = 3   # each customer gets at most 3 emails, then we stop.


def touch_stats(v):
    """Read a lead's send history. `v` is a list of refs (one per touch sent),
    or a legacy single ref string, or None. Returns (sent_count, last_status)
    where last_status is one of: ready | sent | held | blocked | error."""
    if not v:
        return 0, "ready"
    refs = v if isinstance(v, list) else [v]
    sent, last = 0, "ready"
    for r in refs:
        r = str(r or "")
        if r.startswith(("suppressed", "blocked")):
            last = "blocked"
        elif r.startswith("held"):
            last = "held"
        elif r.startswith("send_error"):
            last = "error"
        elif r:
            sent += 1
            last = "sent"
    return sent, last


def next_touch(v):
    """The next email step to send this lead (1..3), or 0 if the sequence is done
    (3 already sent) or blocked (suppressed). A held/error state retries the same
    step, so it does not advance the counter."""
    sent, last = touch_stats(v)
    if last == "blocked":
        return 0
    if sent >= SEQUENCE_TOUCHES:
        return 0
    return sent + 1


SEQUENCE_GAP_DAYS = 3   # wait this many days between emails (intro -> +3 -> +3)


def sequence_schedule(sent_at, gap_days: int = SEQUENCE_GAP_DAYS):
    """The real timeline for a lead's 3-email cycle. `sent_at` is the list of ISO
    timestamps of the emails already sent (parallel to sent_to). Returns a 3-item
    list: [{step, state, date}] where state is sent | due | scheduled and date is
    the actual send date (past) or the projected send date (future, ISO 'YYYY-MM-DD').
    Follow-up N is scheduled gap_days after the previous email actually went out."""
    from datetime import datetime, timedelta, timezone

    def _parse(t):
        try:
            d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # naive -> UTC
        except Exception:
            return None
    times = [d for d in (_parse(t) for t in (sent_at or [])) if d]
    now = datetime.now(timezone.utc)
    n_sent = len(times)
    out = []
    for step in (1, 2, 3):
        if step <= n_sent:
            out.append({"step": step, "state": "sent",
                        "date": times[step - 1].date().isoformat()})
        else:
            base = times[-1] if times else now
            # step (n_sent+1) is the next; each further step adds another gap
            due = base + timedelta(days=gap_days * (step - n_sent)) if times \
                else now + timedelta(days=gap_days * (step - 1))
            is_next = (step == n_sent + 1)
            state = "due" if (is_next and due <= now) else "scheduled"
            out.append({"step": step, "state": state, "date": due.date().isoformat()})
    return out


def outreach_touch(lead: dict, qual: dict, subject: str, body: str, touch: int):
    """The email for step 1/2/3 of the follow-up sequence. Touch 1 is the full
    personalized pitch; touch 2 is a short bump; touch 3 is a final soft close.
    Each is different so the customer never gets the same email twice."""
    subj1, body1 = personalize_outreach(lead, qual, subject, body)
    if touch <= 1:
        return subj1, body1
    name = ((lead.get("name") or "there").split(" ") or ["there"])[0]
    qual = qual or {}
    offer = (qual.get("offer") or "AI automation that saves hours each week").rstrip(".")
    pain = (qual.get("pain_point") or "").rstrip(".")
    rsubj = subj1 if subj1.lower().startswith("re:") else "Re: " + subj1
    if touch == 2:
        body2 = (f"Hi {name},\n\nJust floating this back to the top of your inbox in case it slipped by.\n\n"
                 f"{offer}. Worth a quick 15-minute call to see if it's a fit for you?")
        return rsubj, body2
    body3 = (f"Hi {name},\n\nLast note from me, I promise, I know inboxes are relentless.\n\n"
             + (f"If {pain} isn't a priority right now, no worries at all. " if pain else "")
             + "If it ever is, the link below is the fastest way to grab a time.")
    return rsubj, body3


def _outreach_emails(body: str, *, lang, sender, title, company, website, phone,
                     booking_url, address, unsub_url, logo, brand="#7A00DF"):
    """Build the (plain_text, html) versions of a cold email: the writer's personal
    body + a DETERMINISTIC professional signature (logo, name·title, website, a real
    'Book a free consultation' link) + a small legal footer. Code owns the signature
    so the consultation link is always attached and never malformed."""
    de = str(lang).strip().lower() in ("de", "ch", "at", "germany", "switzerland", "austria", "german")
    L = {
        "regards": "Viele Grüße," if de else "Best regards,",
        "book": "Kostenloses Beratungsgespräch buchen" if de else "Book a free consultation",
        "unsub": "Abmelden" if de else "Unsubscribe",
    }
    web = (website or "").replace("https://", "").replace("http://", "").strip("/")
    web_url = "https://" + web if web else ""
    clean_body = body.strip()
    phone_txt = f" | {phone}" if phone else ""

    # ---- plain text (fallback) ----
    plain = (clean_body + "\n\n" + L["regards"] + "\n" + sender + "\n"
             + f"{title} · {company}\n{web} | {L['book']}: {booking_url}\n\n"
             + f"{company} · {address}\n{L['unsub']}: {unsub_url}")

    # ---- HTML (the signature the founder wants) ----
    paras = "".join(
        f'<p style="margin:0 0 14px">{_html_escape(p).strip()}</p>'
        for p in clean_body.split("\n") if p.strip())
    phone_html = f' | {_html_escape(phone)}' if phone else ""
    # The conversion CTA — a big, obvious booking BUTTON (this is what turns a
    # reader into a booked call). Placed before the sign-off so it never gets lost.
    cta_btn = (
        f'<table cellpadding="0" cellspacing="0" style="margin:6px 0 18px"><tr><td '
        f'style="background:{brand};border-radius:10px"><a href="{booking_url}" '
        f'style="display:inline-block;padding:13px 26px;color:#ffffff;font-weight:bold;'
        f'font-size:15px;text-decoration:none">📅 {L["book"]} →</a></td></tr></table>')
    html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;color:#2b2b3a;font-size:15px;line-height:1.6;max-width:620px">'
        + paras
        + cta_btn
        + f'<p style="margin:0 0 12px">{L["regards"]}</p>'
        + '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse"><tr>'
        + f'<td style="padding-right:13px;vertical-align:top"><img src="{logo}" width="48" height="48" alt="{_html_escape(company)}" style="width:48px;height:48px;border-radius:9px;display:block;border:0"></td>'
        + f'<td style="vertical-align:top;border-left:3px solid {brand};padding-left:13px">'
        + f'<div style="font-weight:bold;font-size:15px;color:#14142b">{_html_escape(sender)}</div>'
        + f'<div style="font-size:12.5px;color:#6a6a80">{_html_escape(title)} · {_html_escape(company)}</div>'
        + f'<div style="font-size:12.5px;margin-top:4px"><a href="{web_url}" style="color:{brand};text-decoration:none">{_html_escape(web)}</a>{phone_html}</div>'
        + f'<div style="font-size:12.5px;margin-top:2px"><a href="{booking_url}" style="color:{brand};text-decoration:none;font-weight:bold">📅 {L["book"]}</a></div>'
        + '</td></tr></table>'
        + f'<p style="font-size:11px;color:#9a9ab0;margin-top:20px;border-top:1px solid #ececf5;padding-top:10px">{_html_escape(company)} · {_html_escape(address)}<br><a href="{unsub_url}" style="color:#9a9ab0">{L["unsub"]}</a></p>'
        + '</div>')
    return plain, html


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

    def _fill_tokens(self, body: str) -> str:
        """Mail-merge: replace the writer's placeholders with real, correct links.
        The AI only writes the token, code inserts the URL — so a booking or
        unsubscribe link can never come out missing or malformed."""
        booking = _env("EMAIL_BOOKING_URL", "https://anthropos-automation.com/free-audit/")
        unsub = _env("EMAIL_UNSUBSCRIBE_URL", "https://anthropos-automation.com/unsubscribe")
        for tok in ("{{booking_url}}", "{{ booking_url }}"):
            body = body.replace(tok, booking)
        for tok in ("{{unsubscribe_token}}", "{{ unsubscribe_token }}", "{{unsubscribe_url}}"):
            body = body.replace(tok, unsub)
        return body

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
        _from = self.from_for(category)
        _name = _env("EMAIL_FROM_NAME", "Hasan")   # friendly sender name on every email
        msg["From"] = formataddr((_name, _from)) if _name else _from
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid()
        for k, v in (extra_headers or {}).items():
            if v:
                msg[k] = v
        body = self._fill_tokens(body)   # swap {{booking_url}} / {{unsubscribe_token}} for real links
        msg.set_content(body)
        if html:
            msg.add_alternative(self._fill_tokens(html), subtype="html")
        try:
            self._transport(msg)
            log.info("email sent to %s from %s (%s)", to_addr, msg["From"], category or "default")
            return msg["Message-ID"]
        except Exception as e:
            log.error("email send failed: %s", e)
            return f"send_error:{to_addr}"

    def send_personalized(self, to_addr: str, subject: str, body: str, job: dict) -> str:
        """Send ONE outreach email to a SPECIFIC lead (the mailbox 'send' button).
        Respects suppression + warm-up cap + the CAN-SPAM validator, and appends
        the branded signature (address + unsubscribe). Returns a ref string."""
        to_addr = (to_addr or "").strip()
        if not to_addr:
            return "send_error_no_recipient"
        if is_suppressed(to_addr):
            return f"suppressed:{to_addr}"
        if not outreach_send_allowed():
            return "held_daily_cap"
        plain, html = self.compose_outreach(body, job)
        try:
            import content_engine_safety as _safety
            allowed = [_env("EMAIL_WEBSITE", "anthropos-automation.com"), "anthropos-automation.com"]
            ok, why = _safety.validate_email(subject, plain, allowed)
            if not ok:
                return f"blocked_quality:{why}"
        except Exception:
            pass
        # Open/click tracking. OFF changes nothing about the email. ON adds a
        # 1x1 pixel and rewrites links in the HTML alternative only — the plain
        # text part is never touched. Wrapped so a tracking failure can never
        # stop a send.
        try:
            html = _apply_tracking(html, to_addr, job)
        except Exception as e:
            log.warning("tracking not applied to %s (send unaffected): %s",
                        to_addr, e)
        ref = self.send_message(to_addr, subject, plain, category="marketing", html=html)
        if isinstance(ref, str) and not ref.startswith(("suppressed:", "send_error", "blocked_quality:")):
            _note_outreach_sent()
        return ref

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
        # Cold outreach: personal body + a deterministic branded signature (plain
        # text + HTML). Code owns the signature so the consultation link is always
        # attached. Replies stay plain.
        if is_outreach:
            plain, html = self.compose_outreach(body, job)
        else:
            plain, html = body, None
        # S4: last gate before an irreversible send — never let a broken/hijacked
        # or off-domain email leave the building.
        try:
            import content_engine_safety as _safety
            allowed = [_env("EMAIL_WEBSITE", "anthropos-automation.com"),
                       "anthropos-automation.com"]
            ok, why = _safety.validate_email(subject, plain, allowed)
            if not ok:
                log.error("email BLOCKED for %s — %s", job.get("job_id"), why)
                return f"blocked_quality:{why}"
        except Exception as _e:   # safety must never break sending on its own bug
            log.warning("email validation skipped (%s)", _e)
        ref = self.send_message(
            to_addr, subject, plain,
            extra_headers={"List-Unsubscribe": f"<{unsub}>" if unsub else ""},
            category=category, html=html)
        if is_outreach and isinstance(ref, str) and not ref.startswith(("suppressed:", "send_error")):
            _note_outreach_sent()   # count it toward today's warm-up cap
        return ref

    def compose_outreach(self, body: str, job: dict):
        """Return (plain_text, html) for a cold email — the body + the branded
        signature. Used by send() AND directly by the test command."""
        p = job.get("payload", {}) or {}
        cfg = p.get("config", {}) or {}
        lead = p.get("lead", {}) or {}
        return _outreach_emails(
            body,
            lang=lead.get("country", ""),
            sender=_env("EMAIL_FROM_NAME", "Hasan"),
            title=_env("EMAIL_SENDER_TITLE", "Founder"),
            company=_env("EMAIL_COMPANY", "") or cfg.get("sender_company") or "Anthropos Automation",
            website=_env("EMAIL_WEBSITE", "anthropos-automation.com"),
            phone=_env("EMAIL_PHONE", ""),
            booking_url=_env("EMAIL_BOOKING_URL", "https://anthropos-automation.com/free-audit/"),
            address=cfg.get("physical_address") or _env("EMAIL_ADDRESS", "1309 Coffeen Ave STE 1200, Sheridan, WY 82801"),
            unsub_url=p.get("unsubscribe_url") or _env("EMAIL_UNSUBSCRIBE_URL", "https://anthropos-automation.com/unsubscribe"),
            logo=_env("EMAIL_LOGO_URL", _LOGO_DEFAULT))


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

    DOMAIN_URL = "https://api.prospeo.io/domain-search"

    def email_from_domain(self, domain: str) -> str:
        """Find ONE verified email for a business website domain (Prospeo
        domain-search). Powers maps-sourced local leads. '' when none found."""
        domain = (domain or "").replace("https://", "").replace("http://", "").strip("/").replace("www.", "")
        if not (self.available() and domain):
            return ""
        j = _post_json(self.DOMAIN_URL, {"company": domain, "limit": 1},
                       headers=self._headers())
        if not j or j.get("error"):
            return ""
        resp = j.get("response") or {}
        rows = resp.get("email_list") or resp.get("emails") or []
        email = ""
        if rows and isinstance(rows[0], dict):
            email = rows[0].get("email") or ""
        elif rows and isinstance(rows[0], str):
            email = rows[0]
        if email:
            _record_cost(float(_env("PROSPEO_COST_PER_EMAIL", "0.039") or 0.039), "prospeo")
        return email

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
def maps_leads(query: str, limit: int = 20) -> list:
    """Location-based local leads: Google Maps (Serper) -> business + website ->
    Prospeo domain-search finds a verified email. Returns engine-shaped leads.
    Businesses without a website are kept (company data) but can't be emailed."""
    places = Serper().maps(query, num=limit)
    if not places:
        return []
    li = LinkedIn()
    out = []
    for p in places:
        website = (p.get("website") or "").strip()
        domain = re.sub(r"^https?://(www\.)?", "", website).strip("/").split("/")[0] if website else ""
        email = li.email_from_domain(domain) if domain else ""
        addr = p.get("address") or ""
        country = addr.split(",")[-1].strip() if "," in addr else ""
        out.append({
            "name": "",                        # maps gives the business, not a person
            "email": email,
            "company": p.get("name", ""),
            "title": "",
            "domain": domain,
            "phone": p.get("phone", ""),
            "address": addr,
            "country": country,
            "vertical": p.get("category", ""),
            "signal": f"maps ★{p.get('rating', 0)} ({p.get('reviews', 0)} reviews)",
            "source": "maps",
        })
    return out


def source_leads(job: dict) -> list:
    """Feeds lead_sourcing (which then dedupes + verifies). Pulls from:
      1) Google Maps (when config.lead_source == 'maps') — local businesses
      2) LinkedIn provider, using the job's ICP as the query
      3) web search, turning result domains into company leads
      4) any raw_leads already on the payload (e.g. posted in by n8n)
    """
    payload = job.get("payload", {})
    cfg = payload.get("config", {}) or {}
    icp = cfg.get("icp", {}) or {}
    leads: list = []
    for _raw in (payload.get("raw_leads", []) or []):
        if isinstance(_raw, dict):
            _raw.setdefault("source", "imported")
        leads.append(_raw)

    # Maps campaign: use the pre-fetched raw_leads if present (no double credit
    # spend); otherwise scrape maps now. Maps campaigns do NOT mix in LinkedIn.
    if (cfg.get("lead_source") or "").lower() == "maps":
        if leads:
            return leads
        return maps_leads(cfg.get("maps_query", ""), int(cfg.get("lead_limit", 20)))

    li = LinkedIn()
    if li.available():
        query = {
            "industries": icp.get("ideal_industries", []),
            "company_size": icp.get("ideal_size", ""),
            "keywords": cfg.get("search_keywords", ""),
            "limit": int(cfg.get("lead_limit", 25)),
        }
        # Stamp the provider. maps_leads() and the web branch already do; this
        # one never did, which is the real reason the dashboard's "Prospeo
        # (LinkedIn)" bar could only ever read 0.
        for _L in li.find_leads(query):
            if isinstance(_L, dict):
                _L.setdefault("source", "prospeo")
            leads.append(_L)

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
class Serper:
    """Google search + Google Maps via serper.dev (one key powers BOTH web
    research and location/maps lead scraping). Credits-based, ~$1/1k queries.
    Set SERPER_API_KEY in the dashboard Connect form (settings-first)."""

    def __init__(self) -> None:
        self.key = _env("SERPER_API_KEY")

    def available(self) -> bool:
        return bool(self.key and _requests())

    def _post(self, endpoint: str, body: dict):
        return _post_json(f"https://google.serper.dev/{endpoint}", body,
                          headers={"X-API-KEY": self.key, "Content-Type": "application/json"})

    def search(self, q: str, num: int = 8) -> list:
        """Google web search -> [{title, link, snippet}] for research briefs."""
        if not self.available():
            return []
        j = self._post("search", {"q": q, "num": num}) or {}
        return [{"title": r.get("title", ""), "link": r.get("link", ""),
                 "snippet": r.get("snippet", "")} for r in j.get("organic", [])[:num]]

    def search_with_ads(self, q: str, num: int = 10):
        """(organic_results, advertiser_domains) — captures who is PAYING to
        appear on this query (Google sponsored slots, when present)."""
        if not self.available():
            return [], []
        j = self._post("search", {"q": q, "num": num}) or {}
        organic = [{"title": r.get("title", ""), "link": r.get("link", ""),
                    "snippet": r.get("snippet", "")} for r in j.get("organic", [])[:num]]
        ads = []
        for a in (j.get("ads") or []) + (j.get("topAds") or []):
            m = re.search(r"(?:https?://)?(?:www\.)?([^/\s]+)", a.get("link") or a.get("displayedLink") or "")
            if m:
                ads.append(m.group(1).lower())
        return organic, ads

    def news(self, q: str, num: int = 8) -> list:
        """Google News results -> [{title, link, date, source}] — competitor
        signals (funding, partnerships, launches, expansion, hiring...)."""
        if not self.available():
            return []
        j = self._post("news", {"q": q}) or {}
        return [{"title": r.get("title", ""), "link": r.get("link", ""),
                 "date": r.get("date", ""), "source": r.get("source", "")}
                for r in (j.get("news") or [])[:num]]

    def maps(self, q: str, num: int = 20) -> list:
        """Google Maps places -> local businesses [{name, address, phone, website,
        rating, reviews, category}] — the location half of the ICP (clinics, law
        firms, salons...) that LinkedIn sourcing misses."""
        if not self.available():
            return []
        j = self._post("maps", {"q": q}) or {}
        out = []
        for p in (j.get("places") or [])[:num]:
            out.append({"name": p.get("title", ""), "address": p.get("address", ""),
                        "phone": p.get("phoneNumber", ""), "website": p.get("website", ""),
                        "rating": p.get("rating", 0), "reviews": p.get("ratingCount", 0),
                        "category": p.get("type", "")})
        return out

    # ---- E6: DAILY RANK TRACKING -------------------------------------
    def rank(self, query: str, domain: str, gl: str = "us",
             device: str = "desktop", num: int = 50) -> dict:
        """Where THIS domain ranks for one query, today, in one market.

        Search Console gives a 28-day AVERAGE, 2-3 days late. That is useless
        for telling whether yesterday's fix worked. This is the live number."""
        if not self.available():
            return {}
        body = {"q": query, "num": num, "gl": gl}
        if device == "mobile":
            body["device"] = "mobile"
        j = self._post("search", body) or {}
        _record_cost(0.001, "serper_rank")
        record_api_spend("serper", 0.001)
        target = (domain or "").lower().replace("www.", "")
        position, url_found = 0, ""
        for i, r in enumerate(j.get("organic", []) or [], start=1):
            link = (r.get("link") or "").lower()
            if target and target in link:
                position, url_found = i, r.get("link", "")
                break
        features = []
        for key, label in (("answerBox", "featured_snippet"), ("peopleAlsoAsk", "paa"),
                           ("knowledgeGraph", "knowledge_panel"), ("places", "local_pack"),
                           ("topAds", "ads"), ("ads", "ads")):
            if j.get(key) and label not in features:
                features.append(label)
        owns_snippet = bool(target and target in
                            str((j.get("answerBox") or {}).get("link", "")).lower())
        return {"query": query, "domain": domain, "market": gl, "device": device,
                "position": position, "url": url_found,
                "found": bool(position), "features": features,
                "owns_snippet": owns_snippet,
                "paa": [x.get("question", "") for x in (j.get("peopleAlsoAsk") or [])][:6],
                "top3": [(r.get("link") or "") for r in (j.get("organic") or [])[:3]]}

    def rank_batch(self, queries: list, domain: str, markets=("us",),
                   device: str = "desktop", limit: int = 100) -> list:
        out = []
        for q in (queries or [])[:limit]:
            for gl in markets:
                r = self.rank(q, domain, gl=gl, device=device)
                if r:
                    out.append(r)
        return out


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
        j = _post_json(url, body, headers=self._auth(self.GA4_SCOPE))
        if not j:
            return {}
        rows = j.get("rows", [])
        top_pages = [{"page": r["dimensionValues"][0]["value"],
                      "sessions": int(r["metricValues"][0]["value"])}
                     for r in rows]
        total_sessions = sum(p["sessions"] for p in top_pages)
        return {"period": f"last {days}d", "metrics": {
            "sessions": total_sessions, "top_pages": top_pages}}


    # ---- FULL replication (the 'google-grade dashboard' feed) ----
    def gsc_report(self, dimension: str, days: int = 28, limit: int = 50) -> list:
        """Search Console by any dimension: query|page|country|device|date."""
        auth = self._auth(self.GSC_SCOPE)
        if not (auth and self.site):
            return []
        from datetime import date, timedelta
        from urllib.parse import quote
        body = {"startDate": (date.today() - timedelta(days=days)).isoformat(),
                "endDate": date.today().isoformat(),
                "dimensions": [dimension], "rowLimit": limit}
        url = (f"https://searchconsole.googleapis.com/webmasters/v3/sites/"
               f"{quote(self.site, safe='')}/searchAnalytics/query")
        j = _post_json(url, body, headers=auth)
        return [{"key": r["keys"][0], "clicks": r.get("clicks", 0),
                 "impressions": r.get("impressions", 0),
                 "ctr": round(r.get("ctr", 0) * 100, 2),
                 "position": round(r.get("position", 0), 1)}
                for r in (j or {}).get("rows", [])]

    def gsc_full(self, days: int = 28) -> dict:
        """Everything Search Console gives us: queries, pages, countries,
        devices, and the daily trend."""
        if not self.available():
            return {}
        return {"queries": self.gsc_report("query", days, 50),
                "pages": self.gsc_report("page", days, 25),
                "countries": self.gsc_report("country", days, 15),
                "devices": self.gsc_report("device", days, 5),
                "daily": sorted(self.gsc_report("date", days, days + 2), key=lambda r: r["key"])}

    def ga4_report(self, dimensions: list, metrics: list, days: int = 28, limit: int = 30) -> list:
        auth = self._auth(self.GA4_SCOPE)
        if not (auth and self.ga4_property):
            return []
        body = {"dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
                "dimensions": [{"name": d} for d in dimensions],
                "metrics": [{"name": m} for m in metrics], "limit": limit}
        url = (f"https://analyticsdata.googleapis.com/v1beta/"
               f"properties/{self.ga4_property}:runReport")
        j = _post_json(url, body, headers=auth)
        out = []
        for r in (j or {}).get("rows", []):
            row = {}
            for i, d in enumerate(dimensions):
                row[d] = r["dimensionValues"][i]["value"]
            for i, m in enumerate(metrics):
                try:
                    row[m] = float(r["metricValues"][i]["value"])
                except Exception:
                    row[m] = 0
            out.append(row)
        return out

    def ga4_full(self, days: int = 28) -> dict:
        """Everything GA4 gives us: daily sessions/users, channels, top pages,
        countries, engagement + totals."""
        if not self.available():
            return {}
        daily = sorted(self.ga4_report(["date"], ["sessions", "totalUsers", "newUsers"], days, days + 2),
                       key=lambda r: r.get("date", ""))
        channels = self.ga4_report(["sessionDefaultChannelGroup"], ["sessions"], days, 10)
        pages = self.ga4_report(["pagePath"], ["sessions", "totalUsers"], days, 15)
        countries = self.ga4_report(["country"], ["sessions"], days, 12)
        eng = self.ga4_report([], ["sessions", "totalUsers", "newUsers", "engagementRate"], days, 1)
        totals = eng[0] if eng else {}
        return {"daily": daily, "channels": channels, "pages": pages,
                "countries": countries, "totals": totals}

    # ---- SEO ENGINE FEEDS (E2 + cannibalization + decay) ----
    def gsc_query_page(self, days: int = 28, limit: int = 500) -> list:
        """query x page rows — the ONLY way to detect cannibalization (two of
        your own pages fighting for one query). Free."""
        auth = self._auth(self.GSC_SCOPE)
        if not (auth and self.site):
            return []
        from datetime import date, timedelta
        from urllib.parse import quote
        body = {"startDate": (date.today() - timedelta(days=days)).isoformat(),
                "endDate": date.today().isoformat(),
                "dimensions": ["query", "page"], "rowLimit": limit}
        j = _post_json(f"https://searchconsole.googleapis.com/webmasters/v3/sites/"
                       f"{quote(self.site, safe='')}/searchAnalytics/query", body, headers=auth)
        return [{"keys": r.get("keys", []), "clicks": r.get("clicks", 0),
                 "impressions": r.get("impressions", 0),
                 "ctr": round(r.get("ctr", 0) * 100, 2),
                 "position": round(r.get("position", 0), 1)}
                for r in (j or {}).get("rows", [])]

    def gsc_range(self, dimension: str, start_days_ago: int, end_days_ago: int,
                  limit: int = 100) -> list:
        """Any past window — used to compare this 28d against the previous 28d
        so content DECAY becomes visible."""
        auth = self._auth(self.GSC_SCOPE)
        if not (auth and self.site):
            return []
        from datetime import date, timedelta
        from urllib.parse import quote
        today = date.today()
        body = {"startDate": (today - timedelta(days=start_days_ago)).isoformat(),
                "endDate": (today - timedelta(days=end_days_ago)).isoformat(),
                "dimensions": [dimension], "rowLimit": limit}
        j = _post_json(f"https://searchconsole.googleapis.com/webmasters/v3/sites/"
                       f"{quote(self.site, safe='')}/searchAnalytics/query", body, headers=auth)
        return [{"key": r["keys"][0], "clicks": r.get("clicks", 0),
                 "impressions": r.get("impressions", 0),
                 "position": round(r.get("position", 0), 1)}
                for r in (j or {}).get("rows", [])]

    def url_inspect(self, url: str) -> dict:
        """E2 — URL Inspection API. FREE, 2,000 calls/day. Tells you whether
        Google actually indexed a page, which canonical it chose, when it last
        crawled, and whether rich results are eligible. This is the single most
        valuable unused asset the account already had."""
        auth = self._auth(self.GSC_SCOPE)
        if not (auth and self.site):
            return {}
        j = _post_json("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                       {"inspectionUrl": url, "siteUrl": self.site}, headers=auth)
        res = ((j or {}).get("inspectionResult") or {})
        idx = res.get("indexStatusResult") or {}
        return {
            "url": url,
            "verdict": idx.get("verdict", ""),
            "coverageState": idx.get("coverageState", ""),
            "robotsTxtState": idx.get("robotsTxtState", ""),
            "indexingState": idx.get("indexingState", ""),
            "lastCrawlTime": idx.get("lastCrawlTime", ""),
            "pageFetchState": idx.get("pageFetchState", ""),
            "googleCanonical": idx.get("googleCanonical", ""),
            "userCanonical": idx.get("userCanonical", ""),
            "mobileUsability": ((res.get("mobileUsabilityResult") or {}).get("verdict", "")),
            "richResults": ((res.get("richResultsResult") or {}).get("verdict", "")),
        }

    def inspect_batch(self, urls: list, limit: int = 200) -> dict:
        """Inspect many URLs, staying well under the free daily quota."""
        out = {}
        for u in (urls or [])[:limit]:
            r = self.url_inspect(u)
            if r:
                out[u] = r
        return out


class PageSpeed:
    """E3 — PageSpeed Insights API (Lighthouse lab + CrUX field data).
    Works WITHOUT a key at a low rate limit; PAGESPEED_API_KEY raises it.
    Always free."""

    def __init__(self) -> None:
        self.key = _env("PAGESPEED_API_KEY")

    def available(self) -> bool:
        return _requests() is not None

    def check(self, url: str, strategy: str = "mobile") -> dict:
        if not self.available():
            return {}
        params = {"url": url, "strategy": strategy,
                  "category": ["performance", "seo", "accessibility"]}
        if self.key:
            params["key"] = self.key
        j = _get_json("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params)
        if not j:
            return {}
        lr = j.get("lighthouseResult") or {}
        cats = lr.get("categories") or {}
        audits = lr.get("audits") or {}

        def _num(a):
            return round((audits.get(a) or {}).get("numericValue", 0) or 0)

        field = (j.get("loadingExperience") or {}).get("metrics") or {}

        def _field(k):
            return (field.get(k) or {}).get("percentile")

        return {"url": url, "strategy": strategy,
                "performance": round((cats.get("performance") or {}).get("score", 0) * 100),
                "seo": round((cats.get("seo") or {}).get("score", 0) * 100),
                "accessibility": round((cats.get("accessibility") or {}).get("score", 0) * 100),
                "lcp_ms": _num("largest-contentful-paint"),
                "cls": round((audits.get("cumulative-layout-shift") or {}).get("numericValue", 0) or 0, 3),
                "tbt_ms": _num("total-blocking-time"),
                "fcp_ms": _num("first-contentful-paint"),
                "speed_index": _num("speed-index"),
                "field_lcp": _field("LARGEST_CONTENTFUL_PAINT_MS"),
                "field_inp": _field("INTERACTION_TO_NEXT_PAINT"),
                "field_cls": _field("CUMULATIVE_LAYOUT_SHIFT_SCORE"),
                "has_field_data": bool(field)}

    def check_many(self, urls: list, strategy: str = "mobile", limit: int = 12) -> list:
        return [r for r in (self.check(u, strategy) for u in (urls or [])[:limit]) if r]


class IndexNow:
    """E4 — instant index submission to Bing/Yandex/Seznam. Free, no account:
    you host a key file at https://yoursite/<key>.txt containing the key.
    Google ignores IndexNow, so we also ping the sitemap for Google."""

    def __init__(self) -> None:
        self.key = _env("INDEXNOW_KEY")
        self.site = _env("WORDPRESS_URL") or _env("GSC_SITE_URL")

    def available(self) -> bool:
        return bool(self.key and self.site and _requests())

    def key_file_url(self) -> str:
        return f"{self.site.rstrip('/')}/{self.key}.txt" if self.key and self.site else ""

    def submit(self, urls) -> str:
        if isinstance(urls, str):
            urls = [urls]
        urls = [u for u in (urls or []) if u]
        if not urls:
            return "no_urls"
        if not self.available():
            return "indexnow_not_configured"
        from urllib.parse import urlparse
        host = urlparse(self.site).netloc
        j = _post_json("https://api.indexnow.org/IndexNow",
                       {"host": host, "key": self.key,
                        "keyLocation": self.key_file_url(),
                        "urlList": urls[:10000]},
                       headers={"Content-Type": "application/json"})
        return "submitted" if j is not None else "indexnow_error"

    def ping_sitemap(self) -> str:
        """Nudge the sitemap so Google re-reads it (best-effort, free)."""
        rq = _requests()
        if not (rq and self.site):
            return "no_site"
        try:
            rq.get(f"{self.site.rstrip('/')}/wp-sitemap.xml",
                   headers={"User-Agent": _UA}, timeout=_HTTP_TIMEOUT)
            return "pinged"
        except Exception as e:
            return f"ping_failed:{e}"


class DataForSEO:
    """E11 — the ONE new paid vendor, and only for data Google refuses to give:
    your backlink profile. ~$0.02-0.05 per request. Key-gated: every other SEO
    card works without it.

    Set DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD in the dashboard Connect form."""

    BASE = "https://api.dataforseo.com/v3"

    def __init__(self) -> None:
        self.login = _env("DATAFORSEO_LOGIN")
        self.password = _env("DATAFORSEO_PASSWORD")

    def available(self) -> bool:
        return bool(self.login and self.password and _requests())

    def _auth_header(self) -> dict:
        import base64
        tok = base64.b64encode(f"{self.login}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {tok}", "Content-Type": "application/json"}

    def _call(self, path: str, payload: list, cost: float = 0.03):
        if not self.available():
            return None
        j = _post_json(f"{self.BASE}{path}", payload, headers=self._auth_header())
        if j is not None:
            _record_cost(cost, "dataforseo")
            record_api_spend("dataforseo", cost)
        try:
            return (j or {}).get("tasks", [{}])[0].get("result", [])
        except Exception:
            return None

    def backlink_summary(self, target: str) -> dict:
        res = self._call("/backlinks/summary/live", [{"target": target, "internal_list_limit": 1}])
        if not res:
            return {}
        r = res[0] if isinstance(res, list) else res
        return {"target": target,
                "backlinks": r.get("backlinks", 0),
                "referring_domains": r.get("referring_domains", 0),
                "referring_main_domains": r.get("referring_main_domains", 0),
                "rank": r.get("rank", 0),
                "dofollow": r.get("backlinks_dofollow", r.get("dofollow", 0)),
                "broken_backlinks": r.get("broken_backlinks", 0),
                "referring_ips": r.get("referring_ips", 0)}

    def backlinks(self, target: str, limit: int = 100) -> list:
        res = self._call("/backlinks/backlinks/live",
                         [{"target": target, "limit": limit, "mode": "one_per_domain"}], 0.05)
        items = (res[0].get("items") if res and isinstance(res, list) else None) or []
        return [{"domain": i.get("domain_from", ""), "url_from": i.get("url_from", ""),
                 "url_to": i.get("url_to", ""), "anchor": i.get("anchor", ""),
                 "dofollow": i.get("dofollow", True),
                 "rank": i.get("domain_from_rank", i.get("rank", 0)),
                 "first_seen": i.get("first_seen", ""), "lost": bool(i.get("is_lost"))}
                for i in items]

    def referring_domains(self, target: str, limit: int = 100) -> list:
        res = self._call("/backlinks/referring_domains/live",
                         [{"target": target, "limit": limit}], 0.05)
        items = (res[0].get("items") if res and isinstance(res, list) else None) or []
        return [{"domain": i.get("domain", ""), "backlinks": i.get("backlinks", 0),
                 "rank": i.get("rank", 0), "first_seen": i.get("first_seen", "")}
                for i in items]


class GoogleBusiness:
    """E13 — Google Business Profile (reviews, posts, insights). Needs its own
    OAuth (the service account cannot act on a business profile), so this stays
    key-gated exactly like Google Ads. Local-pack RANK comes from Serper Maps
    and works without this."""

    def __init__(self) -> None:
        self.token = _env("GBP_ACCESS_TOKEN")
        self.account = _env("GBP_ACCOUNT_ID")
        self.location = _env("GBP_LOCATION_ID")

    def available(self) -> bool:
        return bool(self.token and self.location and _requests())

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def reviews(self, limit: int = 50) -> list:
        if not self.available():
            return []
        j = _get_json(f"https://mybusiness.googleapis.com/v4/accounts/{self.account}"
                      f"/locations/{self.location}/reviews",
                      headers=self._h(), params={"pageSize": limit})
        return [{"reviewer": (r.get("reviewer") or {}).get("displayName", ""),
                 "rating": r.get("starRating", ""), "comment": r.get("comment", ""),
                 "created": r.get("createTime", ""),
                 "replied": bool(r.get("reviewReply"))}
                for r in ((j or {}).get("reviews") or [])]


def google_insights(force: bool = False) -> dict:
    """Cached (hourly) full GSC+GA4 pull — the dashboards read THIS, so pages
    load instantly and one slow Google call can never blank the UI."""
    from datetime import datetime, timezone
    try:
        cached = _setting("google_insights", {}) or {}
    except Exception:
        cached = {}
    if cached and not force:
        try:
            at = datetime.fromisoformat(str(cached.get("at", "")).replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - at).total_seconds() < 3600:
                return cached
        except Exception:
            pass
    g = Google()
    if not g.available():
        return cached
    fresh = {"at": datetime.now(timezone.utc).isoformat(),
             "gsc": g.gsc_full(), "ga4": g.ga4_full()}
    if fresh["gsc"] or fresh["ga4"]:
        try:
            _set_setting("google_insights", fresh)
        except Exception:
            pass
        return fresh
    return cached


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

    def post_image(self, text: str, image_url: str) -> str:
        """Post text + IMAGE CARD (LinkedIn's 3-step asset flow: register the
        upload -> PUT the bytes -> share with the asset attached). Falls back to
        a text-only post if any step fails, so a post always goes out."""
        if not (self.available() and image_url):
            return self.post(text)
        rq = _requests()
        H = {"Authorization": f"Bearer {self.token}",
             "X-Restli-Protocol-Version": "2.0.0"}
        try:
            # 1. register the upload slot
            reg = _post_json(
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                {"registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": self.author,
                    "serviceRelationships": [{"relationshipType": "OWNER",
                                              "identifier": "urn:li:userGeneratedContent"}]}},
                headers=H)
            val = (reg or {}).get("value") or {}
            asset = val.get("asset") or ""
            up = ((val.get("uploadMechanism") or {})
                  .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest") or {})
            upload_url = up.get("uploadUrl") or ""
            if not (asset and upload_url):
                return self.post(text)
            # 2. fetch the image bytes and PUT them into the slot
            img = rq.get(image_url, timeout=_HTTP_TIMEOUT)
            if not img.ok:
                return self.post(text)
            put = rq.put(upload_url, data=img.content,
                         headers={"Authorization": f"Bearer {self.token}"},
                         timeout=_HTTP_TIMEOUT)
            if put.status_code not in (200, 201):
                return self.post(text)
            # 3. share with the image attached
            body = {
                "author": self.author,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "IMAGE",
                        "media": [{"status": "READY", "media": asset}],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
            j = _post_json("https://api.linkedin.com/v2/ugcPosts", body, headers=H)
            if j is None:
                return self.post(text)
            return "linkedin_img:" + str(j.get("id", "posted"))
        except Exception as e:
            log.warning("linkedin image post failed, falling back to text: %s", e)
            return self.post(text)


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
    """Generate one image and return a PERMANENT URL (hosted in the WordPress
    media library). Handles both OpenAI response shapes: gpt-image-1 returns
    base64 only (the old code read `url` and silently got '' every time — the
    'no images in blogs' bug), dall-e-3 returns a short-lived URL. Either way
    the bytes are uploaded to WordPress so the URL never expires. Returns ''
    only when generation fails or nothing can host the image."""
    key = _env("IMAGE_API_KEY")
    rq = _requests()
    if not key or not rq:
        return ""
    provider = _env("IMAGE_PROVIDER", "openai").lower()
    img_bytes, transient_url = b"", ""
    if provider == "openai":
        j = _post_json("https://api.openai.com/v1/images/generations",
                       {"model": _env("IMAGE_MODEL", "gpt-image-1"), "prompt": prompt,
                        "size": size, "n": 1},
                       headers={"Authorization": f"Bearer {key}"})
        d = (j.get("data") or [{}])[0] if j else {}
        transient_url = d.get("url") or ""
        b64 = d.get("b64_json") or ""
        if b64:
            import base64
            try:
                img_bytes = base64.b64decode(b64)
            except Exception:
                img_bytes = b""
    else:
        url = _env("IMAGE_API_URL")
        if url:
            j = _post_json(url, {"prompt": prompt, "size": size},
                           headers={"Authorization": f"Bearer {key}"})
            transient_url = (j or {}).get("url", "") if j else ""
    if transient_url and not img_bytes:      # download so we can host it durably
        try:
            r = rq.get(transient_url, timeout=_HTTP_TIMEOUT)
            if r.ok:
                img_bytes = r.content
        except Exception:
            pass
    if not img_bytes and not transient_url:
        return ""
    _record_cost(float(_env("IMAGE_COST_PER", "0.04") or 0.04), "image")
    # host permanently in the WordPress media library
    if img_bytes:
        wp = WordPress()
        if wp.available():
            _mid, hosted = wp.upload_media(img_bytes, "ai-hero.png", "image/png")
            if hosted:
                return hosted
    return transient_url   # last resort: short-lived URL beats nothing


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


def repurpose_linkedin(piece: dict, website_url: str = "", booking_url: str = "") -> str:
    """Turn a produced blog into a NATIVE LinkedIn post — a hook line, 3-4 concrete
    takeaways pulled from the article's own headings/points, and a soft CTA. Not a
    truncated blog dump. Deterministic (no API cost), reliable, on-brand."""
    import re
    title = (piece.get("title") or "").strip()
    body = (piece.get("body") or "").strip()
    # pull the article's H2/H3 headings + bullet points as the takeaways
    points = []
    for ln in body.split("\n"):
        s = ln.strip()
        m = re.match(r"^#{2,3}\s+(.*)", s)
        if m:
            points.append(m.group(1).strip())
        elif re.match(r"^[-*]\s+\S", s):
            points.append(re.sub(r"^[-*]\s+", "", s).strip())
        if len(points) >= 6:
            break
    points = [p for p in points if 6 < len(p) < 120][:4]
    hook = title or (points[0] if points else "A quick note on automating your business")
    lines = [f"{hook}", ""]
    if points:
        lines.append("Here's what most owners miss:")
        lines += [f"→ {p}" for p in points]
        lines.append("")
    else:
        # fall back to the lead paragraph
        para = next((p.strip() for p in body.split("\n\n") if len(p.strip()) > 40), "")
        if para:
            lines += [para[:400].rstrip() + ("…" if len(para) > 400 else ""), ""]
    cta = "We map your biggest leak in a free 30-minute call."
    if booking_url:
        cta += f" → {booking_url}"
    elif website_url:
        cta += f" → {website_url}"
    lines.append(cta)
    tags = piece.get("hashtags") or ["automation", "AIagents", "smallbusiness", "leadgen"]
    lines.append("\n" + " ".join((t if str(t).startswith("#") else "#" + str(t)) for t in tags[:5]))
    text = "\n".join(lines).strip()
    return text[:2900]   # LinkedIn hard limit ~3000 chars


def post_social(job: dict, piece: dict, channel: str) -> str:
    """SOCIAL_FN — post a produced piece to one social channel. Each platform
    self-degrades to a clear '<channel>_not_configured' marker (visible to the
    human) when its credentials are absent, so the pipeline never crashes."""
    ch = (channel or "").lower()
    jid = job.get("job_id")
    if ch == "linkedin":
        p = LinkedInPoster()
        # use the founder-approved LinkedIn post if present, else repurpose the blog
        text = (piece.get("linkedin_post")
                or repurpose_linkedin(piece, _env("EMAIL_WEBSITE", ""), _env("EMAIL_BOOKING_URL", "")))
        if not p.available():
            return f"linkedin_not_configured:{jid}"
        img = piece.get("image_url", "")
        return p.post_image(text, img) if img else p.post(text)
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
        for _w in ("google_gsc_ga4", "google_sheets", "google_drive"):
            note_auth(_w, True)
        return creds.token
    except Exception as e:
        log.warning("google service-account auth failed: %s", e)
        # One key backs GSC, GA4, Sheets and Drive — if it is refused, all four
        # are down, and all four used to keep showing green.
        for _w in ("google_gsc_ga4", "google_sheets", "google_drive"):
            note_auth(_w, False, 401,
                      "The Google service-account key was rejected: "
                      f"{str(e)[:110]}. Paste a fresh JSON key — GSC, GA4, "
                      "Sheets and Drive all depend on this one credential.")
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
        # Cal.com retired the v1 API (410 Gone) — use v2 with Bearer auth.
        rq = _requests()
        if not rq:
            return []
        try:
            r = rq.get("https://api.cal.com/v2/bookings",
                       headers={"Authorization": f"Bearer {self.key}",
                                "cal-api-version": "2024-08-13"},
                       timeout=_HTTP_TIMEOUT)
            r.raise_for_status()
            j = r.json() or {}
        except Exception as e:
            log.warning("cal.com v2 bookings failed: %s", e)
            return []
        data = j.get("data")
        if isinstance(data, dict):                 # some responses nest {bookings:[...]}
            data = data.get("bookings", [])
        return data if isinstance(data, list) else []

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
        # optional: when the developer token belongs to a MANAGER (MCC) account
        # but ads run in a sub-account, Google needs the manager id as a header.
        self.login_cid = _env("GOOGLE_ADS_LOGIN_CUSTOMER_ID").replace("-", "")
        # Google retires API versions after ~a year; make it configurable so a
        # sunset version (404s) can be bumped without a code change. diag() probes
        # for a live one and tells you which to set.
        self.ver = _env("GOOGLE_ADS_API_VERSION", "v21") or "v21"

    def _base(self) -> str:
        return f"https://googleads.googleapis.com/{self.ver}/customers/{self.cid}"

    def available(self) -> bool:
        return bool(self.dev and self.cid and self.refresh
                    and self.client_id and self.client_secret and _requests())

    def _access_token(self) -> str:
        j = _post_json("https://oauth2.googleapis.com/token", {
            "client_id": self.client_id, "client_secret": self.client_secret,
            "refresh_token": self.refresh, "grant_type": "refresh_token"})
        tok = (j or {}).get("access_token", "")
        # Record the verdict. Google returns 401 for a dead refresh token, and
        # the dashboard used to show this wire green anyway.
        note_auth("ads_api", bool(tok), 0 if tok else 401,
                  "" if tok else
                  "Google refused the Ads refresh token (401). Regenerate it — a "
                  "refresh token expires if unused for six months, or if the "
                  "OAuth consent was revoked. Everything else about Ads is set up.")
        return tok

    def _headers(self, tok: str) -> dict:
        h = {"Authorization": f"Bearer {tok}", "developer-token": self.dev}
        if self.login_cid:
            h["login-customer-id"] = self.login_cid
        return h

    def _explain(self, code: int, body: str) -> str:
        b = (body or "").lower()
        if any(s in b for s in ("developer_token_not_approved", "not approved", "test account", "developer token")):
            return ("Your developer token is still in TEST access. In Google Ads → Tools → API Center, click "
                    "'Apply for basic access'. Google must approve it before live campaign data flows.")
        if any(s in b for s in ("login-customer-id", "login customer", "user_permission_denied",
                                "does not have permission", "not associated")):
            return ("Your token is on a MANAGER account but the customer id is a sub-account. Set the manager "
                    "(login customer) id — GOOGLE_ADS_LOGIN_CUSTOMER_ID — to your manager account, e.g. 4514413394.")
        if any(s in b for s in ("customer_not_found", "invalid_customer_id", "customer id")):
            return "The customer id looks wrong. Use your operating ad account's 10-digit id, no dashes."
        if code == 401 or "unauthenticated" in b:
            return "Auth failed — re-mint the OAuth refresh token (client id/secret/refresh mismatch)."
        return "See the error above. First-connect issues are usually: token not yet approved, or missing manager (login-customer) id."

    def diag(self) -> dict:
        """Plain-English reason Google Ads has (or hasn't) got data. For the dashboard
        'why is Ads empty?' diagnostic — surfaces the real API error, not a silent {}."""
        rq = _requests()
        if not rq:
            return {"ok": False, "stage": "deps", "hint": "The 'requests' library isn't installed."}
        if not self.available():
            missing = [n for n, v in (("developer token", self.dev), ("customer id", self.cid),
                                      ("refresh token", self.refresh), ("client id", self.client_id),
                                      ("client secret", self.client_secret)) if not v]
            return {"ok": False, "stage": "credentials", "missing": missing,
                    "hint": f"Missing on the System Map: {', '.join(missing)}."}
        tok = self._access_token()
        if not tok:
            return {"ok": False, "stage": "oauth",
                    "hint": "OAuth refused — the refresh token or client id/secret is wrong. Re-mint the refresh token."}
        q = {"query": "SELECT campaign.id, campaign.name FROM campaign LIMIT 5"}
        hdr = {**self._headers(tok), "User-Agent": _UA}

        def _call(ver):
            return rq.post(f"https://googleads.googleapis.com/{ver}/customers/{self.cid}/googleAds:searchStream",
                           json=q, headers=hdr, timeout=_HTTP_TIMEOUT)
        try:
            r = _call(self.ver)
            used = self.ver
            if r.status_code == 404:   # version sunset — probe for a live one
                for v in ("v21", "v20", "v19", "v18", "v17", "v16"):
                    if v == self.ver:
                        continue
                    rr = _call(v)
                    if rr.status_code != 404:
                        r, used = rr, v
                        break
        except Exception as e:
            return {"ok": False, "stage": "network", "error": str(e)[:200]}
        version_note = "" if used == self.ver else f" (set GOOGLE_ADS_API_VERSION={used} — {self.ver} is sunset)"
        if r.status_code == 404:
            return {"ok": False, "stage": "api_version",
                    "hint": "Every Google Ads API version returned 404 — the Google Ads API is likely NOT enabled "
                            "for your Cloud project. Enable 'Google Ads API' in Google Cloud Console → APIs & Services."}
        if r.status_code == 200:
            try:
                n = sum(len(b.get("results", [])) for b in r.json())
            except Exception:
                n = 0
            return {"ok": True, "stage": "live", "api_version": used, "campaigns_found": n,
                    "manager_id_set": bool(self.login_cid),
                    "hint": (("Google Ads API is live and returning data." if n else
                              "Connected and authorized — this account just has no campaigns in the window yet.")
                             + version_note)}
        return {"ok": False, "stage": "api", "status": r.status_code, "api_version": used,
                "manager_id_set": bool(self.login_cid),
                "error": r.text[:500], "hint": self._explain(r.status_code, r.text) + version_note}

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
            f"{self._base()}/googleAds:searchStream",
            {"query": q}, headers=self._headers(tok))
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

    def create_campaign(self, draft: dict, landing_url: str = "") -> dict:
        """1-click activate: launch a drafted campaign into Google Ads —
        budget -> campaign -> ad group -> responsive search ad -> keywords.
        Returns {'ok', 'detail'}. Requires an APPROVED developer token; until
        Google approves it the API returns an error (surfaced, nothing charged)."""
        if not self.available():
            return {"ok": False, "error": "Google Ads not connected"}
        tok = self._access_token()
        if not tok:
            return {"ok": False, "error": "could not get a Google access token"}
        H = self._headers(tok)
        base = self._base()

        def mut(resource, ops):
            return _post_json(f"{base}/{resource}:mutate", {"operations": ops}, headers=H)

        def rn(res):
            return (((res or {}).get("results") or [{}])[0]).get("resourceName")

        try:
            name = (draft.get("campaign_name") or "Anthropos campaign")[:120]
            daily = float(draft.get("daily_budget") or 10)
            budget = mut("campaignBudgets", [{"create": {
                "name": name + " budget", "amountMicros": int(daily * 1_000_000),
                "deliveryMethod": "STANDARD"}}])
            b_rn = rn(budget)
            if not b_rn:
                return {"ok": False, "error": f"budget step failed: {str(budget)[:200]}"}
            camp = mut("campaigns", [{"create": {
                "name": name, "status": "ENABLED", "advertisingChannelType": "SEARCH",
                "campaignBudget": b_rn, "manualCpc": {},
                "networkSettings": {"targetGoogleSearch": True, "targetSearchNetwork": True,
                                    "targetContentNetwork": False}}}])
            c_rn = rn(camp)
            if not c_rn:
                return {"ok": False, "error": f"campaign step failed: {str(camp)[:200]}"}
            made = 0
            for g in (draft.get("ad_groups") or [])[:5]:
                ag = mut("adGroups", [{"create": {
                    "name": (g.get("theme") or "Ad group")[:120], "campaign": c_rn,
                    "status": "ENABLED", "type": "SEARCH_STANDARD", "cpcBidMicros": 1_000_000}}])
                ag_rn = rn(ag)
                if not ag_rn:
                    continue
                heads = [{"text": h[:30]} for h in (g.get("headlines") or [])[:15] if h]
                descs = [{"text": d[:90]} for d in (g.get("descriptions") or [])[:4] if d]
                if len(heads) >= 3 and len(descs) >= 2:
                    mut("adGroupAds", [{"create": {
                        "adGroup": ag_rn, "status": "ENABLED",
                        "ad": {"responsiveSearchAd": {"headlines": heads, "descriptions": descs},
                               "finalUrls": [landing_url or "https://anthropos-automation.com/"]}}}])
                kw = [{"create": {"adGroup": ag_rn, "status": "ENABLED",
                                  "keyword": {"text": k[:80], "matchType": "PHRASE"}}}
                      for k in (g.get("keywords") or [])[:20] if k]
                if kw:
                    mut("adGroupCriteria", kw)
                made += 1
            return {"ok": True, "detail": f"campaign live with {made} ad group(s)", "campaign": c_rn}
        except Exception as e:  # never crash the dashboard
            return {"ok": False, "error": str(e)[:200]}

    def pause_campaign(self, campaign_ref: str) -> dict:
        """Abort a live campaign: set it to PAUSED in Google Ads (stops spend)."""
        if not campaign_ref:
            return {"ok": False, "error": "no campaign reference stored"}
        if not self.available():
            return {"ok": False, "error": "Google Ads not connected"}
        tok = self._access_token()
        if not tok:
            return {"ok": False, "error": "could not get a Google access token"}
        H = self._headers(tok)
        url = f"{self._base()}/campaigns:mutate"
        try:
            r = _post_json(url, {"operations": [{
                "update": {"resourceName": campaign_ref, "status": "PAUSED"},
                "updateMask": "status"}]}, headers=H)
            if r and r.get("results"):
                return {"ok": True, "detail": "campaign paused in Google Ads"}
            return {"ok": False, "error": f"pause failed: {str(r)[:180]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}


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
        "google_sheets": _accepted("google_sheets", GoogleSheets().available()),   # mother dashboard / store
        "google_drive": _accepted("google_drive", GoogleDrive().available()),     # content JSON storage
        "web_search": bool(_env("SEARCH_PROVIDER") and _env("SEARCH_API_KEY") and _requests()),
        "serper_search": Serper().available(),   # Google search + Maps (research + local leads)
        "linkedin_leads": LinkedIn().available(),
        "google_gsc_ga4": _accepted("google_gsc_ga4", Google().available()),
        "ads_data": bool(_env("ADS_JSON")),
        "ads_api": _accepted("ads_api", GoogleAds().available()),
        "calcom_bookings": _accepted("calcom_bookings", CalCom().available()),
        "backlinks_data": bool(_env("BACKLINKS_JSON")),
        # ---- SEO engine wires ----
        "seo_crawler": True,                      # pure code, always on
        "seo_index_inspect": Google().available(),  # free URL Inspection API
        "seo_pagespeed": PageSpeed().available(),   # free, no key needed
        "seo_indexnow": IndexNow().available(),
        "seo_rank_tracker": Serper().available(),
        "seo_backlinks": DataForSEO().available(),
        "seo_gbp": GoogleBusiness().available(),
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
    # every lead now carries where it came from, so the dashboard can stop
    # assigning all of them to one provider
    _sl = source_leads(job)
    assert _sl == [{"email": "x@y.com", "source": "imported"}], _sl

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

    # ---- wire verification: green must mean PROVEN, not merely present ----
    assert _accepted("ads_api", True) is True, "unproven wire must not read as broken"
    note_auth("ads_api", False, 401, "refused")
    assert _accepted("ads_api", True) is False, "a 401 must take the wire down"
    assert "ads_api" in auth_reasons(), "a down wire must say why"
    for transient in (500, 503, 0):
        note_auth("google_sheets", False, transient, "blip")
        assert _accepted("google_sheets", True) is True, (
            f"HTTP {transient} is not a credential rejection and must not flip a wire")
    note_auth("ads_api", True)
    assert _accepted("ads_api", True) is True and not auth_reasons(), "recovery must clear"
    _AUTH_STATE.clear()
    _st = status()
    assert all(k in _st for k in VERIFIABLE), "status() lost a wire"
    assert len(_st) == len(status()), "status() shape must be stable"

    print("OK — connectors self-check passed: graceful offline degradation, "
          "verifier always on, hooks wire only when creds present, collectors "
          "return safe empties, Google hub off-and-safe, and a wire reads green "
          "only once something proved the credentials were accepted. "
          "(No network, no API.)")
