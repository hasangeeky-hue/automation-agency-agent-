"""
content_engine_gtm.py
============================================================================
GOOGLE TAG MANAGER, DRIVEN FROM THE DASHBOARD. Audit the container, draft
missing tags into a workspace, publish behind approval - so no channel loses
tracking silently and the founder never opens tagmanager.google.com.

WHAT IT NEEDS, STATED ONCE
  The same service account the engine already uses for GSC/GA4/Drive, added
  ONCE to the GTM container (or account) with edit + publish permission, and
  the setting GTM_CONTAINER_PATH ("accounts/<id>/containers/<id>"). Plus the
  GTM base snippet in the WordPress theme, once. Until both exist, every
  function here answers with the exact step that is missing - never a guess,
  never a fake green.

THE TAG REGISTRY - one vocabulary
  The required tag set per channel is THIS dict. The auditor, the drafter,
  the tracking screen and the gates all import it. A second hand-written
  copy of this list is the bug class that has bitten this engine five times.
============================================================================
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("gtm")

BASE = "https://tagmanager.googleapis.com/tagmanager/v2"
SCOPES = ["https://www.googleapis.com/auth/tagmanager.edit.containers",
          "https://www.googleapis.com/auth/tagmanager.publish"]
CONTAINER_KEY = "GTM_CONTAINER_PATH"   # accounts/<id>/containers/<id>

# tag-name -> (gtm tag type, the channel it serves, what it measures)
TAG_REGISTRY = {
    "GA4 - config":            ("gaawc",  "ga4",      "every pageview and session"),
    "GA4 - booking":           ("gaawe",  "ga4",      "the booking CTA firing"),
    "GA4 - form_submit":       ("gaawe",  "ga4",      "any form submitted"),
    "GA4 - phone_click":       ("gaawe",  "ga4",      "tel: links clicked"),
    "GA4 - email_click":       ("gaawe",  "ga4",      "mailto: links clicked"),
    "Google Ads - conversion": ("awct",   "google",   "paid conversions Google optimises on"),
    "Google Ads - remarketing": ("sp",    "google",   "audience building"),
    "Meta Pixel":              ("html",   "meta",     "FB+IG attribution"),
    "TikTok Pixel":            ("html",   "tiktok",   "TikTok attribution"),
    "LinkedIn Insight":        ("html",   "linkedin", "LinkedIn attribution"),
}

# which GA4 event each event-tag must fire, for the three-dots silence check
EVENT_OF = {"GA4 - booking": "booking", "GA4 - form_submit": "form_submit",
            "GA4 - phone_click": "phone_click",
            "GA4 - email_click": "email_click"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token():
    import content_engine_connectors as C
    fn = getattr(C, "_google_token", None)
    return fn(SCOPES) if fn else None


def _requests():
    import content_engine_connectors as C
    fn = getattr(C, "_requests", None)
    return fn() if fn else None


def readiness_steps() -> list:
    """The one-time steps, for screens rendering before any store exists."""
    return ["Add the engine's service account to GTM with Edit + Publish "
            "(Admin > User Management) - the same account that reads GSC/GA4.",
            "Save your container path on Connect as GTM_CONTAINER_PATH "
            "(accounts/<id>/containers/<id>, visible in the GTM URL).",
            "Paste the GTM base snippet into the WordPress theme header, "
            "once."]


def container_path(store) -> str:
    try:
        return str(store.get_setting(CONTAINER_KEY, "") or "").strip()
    except Exception:
        return ""


def readiness(store) -> dict:
    """What is missing before GTM can be driven, in the founder's language."""
    steps = []
    if not _token():
        steps.append("Add the engine's service account to Google Tag Manager "
                     "with Edit + Publish (Admin > User Management), the same "
                     "account that already reads your GSC and GA4.")
    if not container_path(store):
        steps.append("Save your container path on Connect as "
                     "GTM_CONTAINER_PATH, e.g. accounts/123/containers/456 "
                     "(visible in the GTM URL).")
    steps.append("The GTM base snippet must sit in the WordPress theme "
                 "header once; after that every tag is managed from here.")
    return {"ready": not steps[:-1], "steps": steps}


def _get(store, path):
    r = _requests()
    tok = _token()
    if not (r and tok):
        return None
    resp = r.get(f"{BASE}/{path}",
                 headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"GTM {path} -> {resp.status_code}: "
                           f"{resp.text[:160]}")
    return resp.json()


# ---------------------------------------------------------------------------
# AUDIT - the container against the registry, plus the silence check
# ---------------------------------------------------------------------------
def audit(store, *, insights=None) -> dict:
    """Compare the live container to the registry; check event silence in
    GA4. Persists to 'gtm_audit' so the boards and the agent read ONE result
    with its timestamp, not a cached green."""
    cp = container_path(store)
    if not cp or not _token():
        rep = {"at": _now(), "ready": False, **readiness(store),
               "missing": [], "paused": [], "silent": [], "present": []}
        store.set_setting("gtm_audit", rep)
        return rep
    ws = _get(store, f"{cp}/workspaces")
    wsid = (ws.get("workspace") or [{}])[0].get("path", "")
    tags = (_get(store, f"{wsid}/tags") or {}).get("tag", []) if wsid else []
    have = {t.get("name"): t for t in tags}
    missing, paused, present = [], [], []
    for name, (ttype, channel, why) in TAG_REGISTRY.items():
        t = have.get(name)
        if not t:
            missing.append({"tag": name, "channel": channel, "why": why})
        elif t.get("paused"):
            paused.append({"tag": name, "channel": channel})
        else:
            present.append({"tag": name, "channel": channel})
    # the silence check: a present tag whose GA4 event never fires is a
    # broken wire wearing a green dot
    silent = []
    events = {e.get("name"): int(e.get("count") or 0)
              for e in ((insights or {}).get("ga4") or {}).get("events", [])
              if isinstance(e, dict)}
    for name in (p["tag"] for p in present):
        ev = EVENT_OF.get(name)
        if ev and events and events.get(ev, 0) == 0:
            silent.append({"tag": name, "event": ev})
    rep = {"at": _now(), "ready": True, "workspace": wsid,
           "missing": missing, "paused": paused, "silent": silent,
           "present": present, "steps": []}
    store.set_setting("gtm_audit", rep)
    return rep


# ---------------------------------------------------------------------------
# DRAFT + PUBLISH - create in a workspace, publish only behind approval
# ---------------------------------------------------------------------------
def _tag_body(name: str, store) -> dict:
    ttype = TAG_REGISTRY[name][0]
    ga4_id = ""
    try:
        ga4_id = str(store.get_setting("GA4_MEASUREMENT_ID", "") or "")
    except Exception:
        pass
    body = {"name": name, "type": ttype}
    if ttype == "gaawc":
        body["parameter"] = [{"type": "template", "key": "measurementIdOverride",
                              "value": ga4_id or "G-UNSET"}]
    elif ttype == "gaawe":
        body["parameter"] = [{"type": "template", "key": "eventName",
                              "value": EVENT_OF.get(name, "event")}]
    return body


def draft_tag(store, name: str) -> dict:
    """Create ONE registry tag in the workspace. A workspace is a draft by
    nature - nothing reaches the site until publish, and publish is gated."""
    if name not in TAG_REGISTRY:
        return {"status": "failed", "result": f"'{name}' is not in the tag "
                                              f"registry; nothing was created"}
    cp = container_path(store)
    if not cp or not _token():
        return {"status": "held",
                "result": " ".join(readiness(store)["steps"][:1]) or
                          "Tag Manager is not granted yet"}
    r = _requests()
    ws = _get(store, f"{cp}/workspaces")
    wsid = (ws.get("workspace") or [{}])[0].get("path", "")
    resp = r.post(f"{BASE}/{wsid}/tags",
                  headers={"Authorization": f"Bearer {_token()}",
                           "Content-Type": "application/json"},
                  data=json.dumps(_tag_body(name, store)), timeout=30)
    if resp.status_code != 200:
        return {"status": "failed",
                "result": f"GTM refused: {resp.status_code} "
                          f"{resp.text[:140]}"}
    return {"status": "done",
            "result": f"'{name}' created in the workspace as a draft. It is "
                      f"NOT live; approve the publish order to make it so."}


def publish(store) -> dict:
    """Version + publish the workspace. Called ONLY from an approved order."""
    cp = container_path(store)
    if not cp or not _token():
        return {"status": "held", "result": "Tag Manager is not granted yet"}
    r = _requests()
    ws = _get(store, f"{cp}/workspaces")
    wsid = (ws.get("workspace") or [{}])[0].get("path", "")
    resp = r.post(f"{BASE}/{wsid}:create_version",
                  headers={"Authorization": f"Bearer {_token()}",
                           "Content-Type": "application/json"},
                  data=json.dumps({"name": f"engine {_now()}"}), timeout=30)
    if resp.status_code != 200:
        return {"status": "failed",
                "result": f"version refused: {resp.status_code}"}
    vid = (resp.json().get("containerVersion") or {}).get("path", "")
    resp2 = r.post(f"{BASE}/{vid}:publish",
                   headers={"Authorization": f"Bearer {_token()}"}, timeout=30)
    if resp2.status_code != 200:
        return {"status": "failed",
                "result": f"publish refused: {resp2.status_code}"}
    return {"status": "done", "result": "version published; the audit will "
                                        "confirm on its next pass"}


def execute_order(store, order: dict) -> dict:
    """The dispatch's entry point for tracking orders."""
    code = order.get("code")
    if code in ("tag_missing", "pixel_missing"):
        return draft_tag(store, order.get("key", ""))
    if code == "tag_paused":
        return {"status": "held", "result": "unpausing is a publish; approve "
                                            "the publish order instead"}
    if code in ("event_silent", "utm_fix"):
        return {"status": "held",
                "result": "needs eyes: the tag exists, so the break is in "
                          "the trigger or the page. The audit's detail names "
                          "which."}
    return {"status": "held", "result": f"no GTM path for {code}"}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = []

    def t(n, c):
        ok.append(bool(c))
        print(("  OK   " if c else "  FAIL ") + n)

    class _S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v

    s = _S()
    r = readiness(s)
    t("readiness names the exact missing steps", len(r["steps"]) >= 2
      and "service account" in r["steps"][0])
    a = audit(s)
    t("an ungranted audit is honest, not green",
      a["ready"] is False and a["missing"] == [] and s.d.get("gtm_audit"))
    d = draft_tag(s, "GA4 - booking")
    t("drafting without the grant is held with the step",
      d["status"] == "held")
    t("drafting an unregistered tag is refused",
      draft_tag(s, "Random Tag")["status"] == "failed")
    t("every event tag maps to a GA4 event",
      set(EVENT_OF) == {k for k, v in TAG_REGISTRY.items() if v[0] == "gaawe"})
    t("registry covers all five channels",
      {v[1] for v in TAG_REGISTRY.values()} >= {"ga4", "google", "meta",
                                                "tiktok", "linkedin"})
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
