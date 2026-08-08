"""
content_engine_media_os.py
============================================================================
THE MEDIA BUYING OS: CANONICAL MODEL, PROVIDER ADAPTER, STATE MACHINE.

WHAT THIS IS AND WHAT IT DELIBERATELY IS NOT
  This is the NORMALIZATION layer the specification asks for, and nothing
  more. It sits above adapters that already exist and below screens that
  do not exist yet. Everything it needs from lower down was already in
  this engine and is reused rather than rebuilt:

    content_engine_connectors     MetaAds, GoogleAds, TikTokAds,
                                  LinkedInAds and the _AdsSocket base
    content_engine_media_orders   the execution engine: order codes,
                                  approval tiers, rules_run, optimize
    content_engine_media_platforms  the capability map and is_connected
    content_engine_ads            economics, targets, judge_cpc, waste
    content_engine_os_core.Repo   tenancy, storage, audit, events
    content_engine_agents         the media agent, already registered

  Nothing above is duplicated here. The founder's rule was explicit: if
  the old OS has it, do not build a second one.

THE RULE THIS FILE EXISTS TO ENFORCE
  No Meta-specific, Google-specific or TikTok-specific logic may appear in
  a screen or in business logic. A caller asks the canonical model; the
  model asks an adapter; the adapter is the only code that knows what
  Meta calls an ad set.

WHAT NORMALIZATION MEANS HERE, HONESTLY
  Common fields are normalized. Provider differences are NOT flattened
  away: every object carries provider_config, and the objective mapper
  reports when a platform cannot do what you asked rather than silently
  substituting something close. Pretending Meta and Google are the same
  system is the mistake that makes these tools untrustworthy.

NOTHING HERE SPENDS MONEY. Every write goes through the existing order
engine, which already holds the approval tiers.
============================================================================
"""

from __future__ import annotations

import logging

import content_engine_os_core as CORE
from content_engine_os_core import _D, _L, now, rid

log = logging.getLogger("content_engine.media_os")

# ---------------------------------------------------------------------------
# THE VOCABULARY. One definition, imported everywhere, never re-typed.
# ---------------------------------------------------------------------------
PROVIDERS = ("meta", "google", "tiktok", "linkedin")

#: Canonical objectives. A provider that cannot do one says so.
OBJECTIVES = ("AWARENESS", "TRAFFIC", "ENGAGEMENT", "LEADS", "SALES",
              "APP_INSTALL", "CONVERSIONS")

#: The canonical hierarchy. Meta calls the middle level an ad set; Google
#: and TikTok call it an ad group. The engine calls it an ad group and the
#: adapter translates, so no screen ever learns the difference.
LEVELS = ("campaign", "ad_group", "ad")

CAMPAIGN_STATES = ("DRAFT", "VALIDATING", "READY", "SCHEDULED", "LAUNCHING",
                   "ACTIVE", "PAUSED", "COMPLETED",
                   "VALIDATION_FAILED", "LAUNCH_FAILED", "PROVIDER_REJECTED",
                   "SYNC_FAILED")

#: Legal moves. Anything absent is refused with the moves that ARE legal.
CAMPAIGN_MOVES = {
    "DRAFT": ("VALIDATING", "COMPLETED"),
    "VALIDATING": ("READY", "VALIDATION_FAILED"),
    "VALIDATION_FAILED": ("DRAFT",),
    "READY": ("SCHEDULED", "LAUNCHING", "DRAFT"),
    "SCHEDULED": ("LAUNCHING", "READY", "COMPLETED"),
    "LAUNCHING": ("ACTIVE", "LAUNCH_FAILED", "PROVIDER_REJECTED"),
    "LAUNCH_FAILED": ("DRAFT", "LAUNCHING"),
    "PROVIDER_REJECTED": ("DRAFT",),
    "ACTIVE": ("PAUSED", "COMPLETED", "SYNC_FAILED"),
    "PAUSED": ("ACTIVE", "COMPLETED"),
    "SYNC_FAILED": ("ACTIVE", "PAUSED"),
    "COMPLETED": (),
}

BUDGET_TYPES = ("DAILY", "LIFETIME")
BUYING_TYPES = ("AUCTION", "RESERVED")

#: What an agent may be permitted to do. The values are checked against
#: the existing media_orders approval tiers rather than a second system.
PERMISSIONS = ("READ_ANALYTICS", "CREATE_CAMPAIGN", "EDIT_BUDGET",
               "PAUSE_CAMPAIGN", "RESUME_CAMPAIGN", "CREATE_CREATIVE",
               "PUBLISH_CREATIVE", "CHANGE_TARGETING", "CHANGE_BID")

#: Collections this module adds. They live in the same store, with the
#: same tenancy, as the engagement OS: one workspace, one Repo, one truth.
COLLECTIONS = ("ad_accounts", "media_campaigns", "ad_groups", "ads",
               "audiences", "creatives", "creative_versions",
               "media_plans", "ad_metrics", "sync_runs", "media_anomalies")

# ---------------------------------------------------------------------------
# THE CAPABILITY MAP. What each platform can actually be asked for.
# Built from the provider's own documented objective vocabulary; where a
# canonical objective has no equivalent the value is None and the caller
# is told, rather than being given the nearest thing without being asked.
# ---------------------------------------------------------------------------
OBJECTIVE_MAP = {
    "meta": {"AWARENESS": "OUTCOME_AWARENESS", "TRAFFIC": "OUTCOME_TRAFFIC",
             "ENGAGEMENT": "OUTCOME_ENGAGEMENT", "LEADS": "OUTCOME_LEADS",
             "SALES": "OUTCOME_SALES", "APP_INSTALL": "OUTCOME_APP_PROMOTION",
             "CONVERSIONS": "OUTCOME_SALES"},
    "google": {"AWARENESS": "DISPLAY", "TRAFFIC": "SEARCH",
               "ENGAGEMENT": "VIDEO", "LEADS": "SEARCH",
               "SALES": "PERFORMANCE_MAX", "APP_INSTALL": "APP",
               "CONVERSIONS": "SEARCH"},
    "tiktok": {"AWARENESS": "REACH", "TRAFFIC": "TRAFFIC",
               "ENGAGEMENT": "ENGAGEMENT", "LEADS": "LEAD_GENERATION",
               "SALES": "PRODUCT_SALES", "APP_INSTALL": "APP_PROMOTION",
               "CONVERSIONS": "WEB_CONVERSIONS"},
    "linkedin": {"AWARENESS": "BRAND_AWARENESS", "TRAFFIC": "WEBSITE_VISIT",
                 "ENGAGEMENT": "ENGAGEMENT", "LEADS": "LEAD_GENERATION",
                 "SALES": "WEBSITE_CONVERSION", "APP_INSTALL": None,
                 "CONVERSIONS": "WEBSITE_CONVERSION"},
}

#: What the middle level is called on each platform. Used only for the
#: sentence shown to a human; the code always says ad_group.
LEVEL_WORDS = {"meta": "ad set", "google": "ad group", "tiktok": "ad group",
               "linkedin": "campaign"}


def supports(provider, objective) -> dict:
    """Can this platform do what you asked. Three answers, never two."""
    p = str(provider or "").lower()
    if p not in OBJECTIVE_MAP:
        return {"ok": False, "provider_objective": None,
                "why": f"this engine has no adapter for {provider!r}"}
    if objective not in OBJECTIVES:
        return {"ok": False, "provider_objective": None,
                "why": f"{objective!r} is not an objective. They are: "
                       + ", ".join(OBJECTIVES)}
    mapped = OBJECTIVE_MAP[p].get(objective)
    if not mapped:
        return {"ok": False, "provider_objective": None,
                "why": f"{p} has no equivalent of {objective}. Choose a "
                       f"different objective for {p}, or leave {p} out of "
                       f"this campaign: substituting the nearest thing "
                       f"without telling you is how a budget ends up "
                       f"buying something you did not ask for."}
    return {"ok": True, "provider_objective": mapped,
            "why": f"{p} calls this {mapped}"}


def capability_table(objective=None) -> list:
    """Every platform against every objective. The Platforms step of the
    wizard draws this so a person sees the gaps before they plan around
    them."""
    out = []
    for p in PROVIDERS:
        row = {"provider": p, "level_word": LEVEL_WORDS.get(p, "ad group")}
        for obj in OBJECTIVES:
            row[obj] = OBJECTIVE_MAP[p].get(obj)
        row["missing"] = [o for o in OBJECTIVES if not OBJECTIVE_MAP[p].get(o)]
        if objective:
            row["asked"] = supports(p, objective)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# THE PROVIDER ADAPTER. One interface over the sockets that already exist.
# ---------------------------------------------------------------------------
class Adapter:
    """The whole surface the model is allowed to use.

    Every method is delegated to the connector class that already talks to
    that platform. This file adds no HTTP, no auth and no endpoint: doing
    so would be a second implementation of something that works, and the
    founder's instruction was not to build one."""

    def __init__(self, provider: str):
        self.provider = str(provider or "").lower()

    # -- the socket ---------------------------------------------------------
    def _socket(self):
        import content_engine_connectors as C
        return {"meta": C.MetaAds, "tiktok": C.TikTokAds,
                "linkedin": C.LinkedInAds, "google": C.GoogleAds}.get(
                    self.provider, lambda: None)()

    def available(self) -> tuple:
        """(bool, why). Asked, never remembered: adding a key must turn a
        platform on without a rebuild."""
        try:
            import content_engine_media_platforms as MP
            live = MP.effective_live(self.provider)
            return bool(live), (f"{self.provider} authorises right now"
                                if live else
                                f"{self.provider} is not connected; add its "
                                f"key on the Connect board and this turns on "
                                f"with no rebuild")
        except Exception as ex:
            return False, f"{self.provider} capability unknown: {ex}"

    # -- reads --------------------------------------------------------------
    def get_account(self) -> dict:
        ok, why = self.available()
        if not ok:
            return {"ok": False, "why": why}
        try:
            s = self._socket()
            fn = getattr(s, "account", None) or getattr(s, "get_account", None)
            return {"ok": True, "account": fn() if fn else {},
                    "why": f"{self.provider} answered"}
        except Exception as ex:
            return {"ok": False, "why": f"{self.provider} refused: {ex}"}

    def get_campaigns(self) -> list:
        """Raw campaigns from the platform, unnormalized. normalize()
        turns them into the canonical shape."""
        ok, _why = self.available()
        if not ok:
            return []
        try:
            s = self._socket()
            for name in ("campaigns", "list_campaigns", "get_campaigns"):
                fn = getattr(s, name, None)
                if fn:
                    got = fn()
                    return _L(got.get("campaigns") if isinstance(got, dict)
                              else got)
        except Exception as ex:
            log.warning("%s campaign read failed: %s", self.provider, ex)
        return []

    # -- writes. ALL of them go through the order engine ---------------------
    def can_write(self, action) -> dict:
        """Whether a write of this kind may happen at all right now.

        The answer comes from the EXISTING approval tier in
        content_engine_media_orders, not from a second policy system that
        could disagree with it."""
        try:
            import content_engine_api as A
            import content_engine_media_orders as MO
            level = MO.auto_level(A.get_store())
        except Exception:
            level = "propose"
        return {"level": level,
                "auto": level == "execute",
                "why": (f"the media approval tier is {level!r}; "
                        + ("actions execute automatically"
                           if level == "execute" else
                           "actions are proposed and wait for you"))}


# ---------------------------------------------------------------------------
# NORMALIZATION. Provider shape in, canonical shape out.
# ---------------------------------------------------------------------------
def normalize_campaign(provider, raw, account_id="") -> dict:
    """One platform's campaign as the canonical object.

    Common fields are mapped. EVERYTHING ELSE IS KEPT, under
    provider_config, because a field this engine does not understand today
    is not a field that should be thrown away."""
    raw = _D(raw)
    p = str(provider or "").lower()
    known = {"id", "name", "status", "objective", "daily_budget",
             "lifetime_budget", "budget", "currency", "start_time",
             "end_time", "buying_type"}
    status = str(raw.get("status") or "").upper()
    canon = {"ACTIVE": "ACTIVE", "ENABLED": "ACTIVE", "PAUSED": "PAUSED",
             "REMOVED": "COMPLETED", "DELETED": "COMPLETED",
             "ARCHIVED": "COMPLETED"}.get(status, "PAUSED")
    daily = raw.get("daily_budget")
    life = raw.get("lifetime_budget")
    return {
        "provider": p,
        "ad_account_id": account_id,
        "external_campaign_id": str(raw.get("id") or ""),
        "name": raw.get("name") or "(unnamed)",
        "state": canon,
        "provider_status": status,
        "objective": _canon_objective(p, raw.get("objective")),
        "provider_objective": raw.get("objective"),
        "buying_type": str(raw.get("buying_type") or "AUCTION").upper(),
        "budget_type": "DAILY" if daily else ("LIFETIME" if life else ""),
        "budget_amount": _money(daily or life or raw.get("budget")),
        "currency": raw.get("currency") or "EUR",
        "start_at": raw.get("start_time") or "",
        "end_at": raw.get("end_time") or "",
        # The bit most tools discard, and the reason they cannot round trip.
        "provider_config": {k: v for k, v in raw.items() if k not in known},
    }


def _canon_objective(provider, provider_objective) -> str:
    """Provider objective back to the canonical one. Unknown stays unknown
    rather than being forced into the nearest bucket."""
    if not provider_objective:
        return ""
    table = OBJECTIVE_MAP.get(str(provider or "").lower(), {})
    for canon, theirs in table.items():
        if theirs and str(theirs).upper() == str(provider_objective).upper():
            return canon
    return ""


def _money(v):
    """Providers send money as micros, as cents, or as a decimal string.
    Guessing wrong by a factor of a million is a real way to misreport a
    budget, so the rule is explicit."""
    if v in (None, ""):
        return None
    try:
        f = float(v)
    except Exception:
        return None
    if f > 1_000_000:          # micros, as Google sends them
        return round(f / 1_000_000, 2)
    if f > 10_000:             # cents, as Meta sends them
        return round(f / 100, 2)
    return round(f, 2)


# ---------------------------------------------------------------------------
# THE CANONICAL MODEL
# ---------------------------------------------------------------------------
def repo(store, workspace_id=CORE.DEFAULT_WORKSPACE):
    """The SAME repository the engagement OS uses, so a lead, an email and
    an ad campaign share one tenancy and one store."""
    import content_engine_os_store as ST
    return ST.repo_for(store, workspace_id)


def save_account(r, provider, external_id, *, name="", currency="EUR",
                 timezone="Europe/Berlin") -> dict:
    """An advertising account. NO TOKEN IS STORED HERE.

    credentials_reference names where the credential lives (the settings
    store the Connect board already writes); the credential itself never
    enters a business table and never reaches a screen."""
    p = str(provider or "").lower()
    if p not in PROVIDERS:
        return {"ok": False, "message": f"no adapter for {provider!r}"}
    rec = r.put("ad_accounts", {
        "id": rid("adacc", r.ws, p, str(external_id)),
        "provider": p, "external_account_id": str(external_id or ""),
        "name": name or f"{p} account", "currency": currency,
        "timezone": timezone, "status": "CONNECTED",
        "credentials_reference": f"settings:{p.upper()}_CREDENTIALS"})
    CORE.audit(r, "founder", "ad_account_saved", rec["id"], p)
    return {"ok": True, "id": rec["id"],
            "message": f"{p} account {external_id} recorded. The credential "
                       f"itself stays where the Connect board put it."}


def accounts(r) -> list:
    """Every account, with whether its platform authorises right now."""
    out = []
    for a in r.all("ad_accounts"):
        ok, why = Adapter(a.get("provider")).available()
        out.append({**a, "live": ok, "why": why})
    for p in PROVIDERS:
        if not any(a.get("provider") == p for a in out):
            ok, why = Adapter(p).available()
            out.append({"id": "", "provider": p, "external_account_id": "",
                        "name": f"{p} (not recorded)", "live": ok,
                        "why": why, "status": "NOT_CONNECTED"})
    return out


def save_campaign(r, *, campaign_id="", name="", objective="LEADS",
                  provider="", ad_account_id="", budget_type="DAILY",
                  budget_amount=0.0, currency="EUR", start_at="", end_at="",
                  buying_type="AUCTION", provider_config=None,
                  attribution_model="last_touch") -> dict:
    """Create or edit a DRAFT. Past DRAFT the content is fixed, because a
    campaign already at the platform must not silently disagree with what
    this engine thinks it launched."""
    if objective not in OBJECTIVES:
        return {"ok": False,
                "message": f"{objective!r} is not an objective. They are: "
                           + ", ".join(OBJECTIVES)}
    if budget_type not in BUDGET_TYPES:
        return {"ok": False, "message": "budget must be DAILY or LIFETIME"}
    cid = campaign_id or rid("mcamp", r.ws, name or now())
    cur = r.one("media_campaigns", cid) or {"id": cid, "state": "DRAFT"}
    if cur.get("state") not in ("DRAFT", "VALIDATION_FAILED"):
        return {"ok": False,
                "message": f"this campaign is {cur.get('state')}; duplicate "
                           f"it to change anything"}
    cap = supports(provider, objective) if provider else {"ok": True}
    if provider and not cap["ok"]:
        return {"ok": False, "message": cap["why"]}
    cur.update({"name": name or cur.get("name") or "Untitled campaign",
                "objective": objective, "provider": str(provider or "").lower(),
                "provider_objective": cap.get("provider_objective"),
                "ad_account_id": ad_account_id, "budget_type": budget_type,
                "budget_amount": float(budget_amount or 0),
                "currency": currency, "start_at": start_at, "end_at": end_at,
                "buying_type": buying_type,
                "attribution_model": attribution_model,
                "provider_config": _D(provider_config)})
    rec = r.put("media_campaigns", cur)
    return {"ok": True, "id": rec["id"], "state": rec["state"],
            "message": f"{rec['name']!r} saved as a draft"
                       + (f". {cap.get('why')}" if provider else "")}


def move(r, campaign_id, to_state, *, why="") -> dict:
    """The ONLY way a campaign changes state."""
    c = r.one("media_campaigns", campaign_id)
    if not c:
        return {"ok": False, "message": "no such campaign in this workspace"}
    if to_state not in CAMPAIGN_STATES:
        return {"ok": False, "message": f"{to_state} is not a campaign state"}
    frm = c.get("state") if c.get("state") in CAMPAIGN_STATES else "DRAFT"
    if to_state not in CAMPAIGN_MOVES.get(frm, ()):
        allowed = ", ".join(CAMPAIGN_MOVES.get(frm, ())) or "nothing"
        return {"ok": False,
                "message": f"a {frm} campaign can only move to: {allowed}"}
    c["state"] = to_state
    c["state_at"] = now()
    if why:
        c["state_why"] = why
    r.put("media_campaigns", c)
    CORE.audit(r, "founder", "media_campaign_state", campaign_id,
               f"{frm} -> {to_state}. {why}")
    return {"ok": True, "state": to_state,
            "message": f"{c.get('name')} is now {to_state.lower()}"}


def validate(r, campaign_id) -> dict:
    """The pre-flight. Returns VALID, WARNING or ERROR, and never launches
    past a blocking error."""
    c = r.one("media_campaigns", campaign_id)
    if not c:
        return {"ok": False, "level": "ERROR", "message": "no such campaign"}
    errors, warnings = [], []
    if not c.get("provider"):
        errors.append("no platform chosen")
    else:
        ok, why = Adapter(c["provider"]).available()
        (errors if not ok else warnings if False else []).append(why) if not ok \
            else None
        cap = supports(c["provider"], c.get("objective"))
        if not cap["ok"]:
            errors.append(cap["why"])
    if not c.get("ad_account_id"):
        warnings.append("no advertising account recorded for this campaign")
    if float(c.get("budget_amount") or 0) <= 0:
        errors.append("the budget is zero")
    if not c.get("start_at"):
        warnings.append("no start date, so it would begin immediately")
    if not r.find("ad_groups", campaign_id=campaign_id):
        errors.append("this campaign has no ad group, so it has nothing to "
                      "put a budget behind")
    level = "ERROR" if errors else ("WARNING" if warnings else "VALID")
    move(r, campaign_id, "VALIDATING")
    move(r, campaign_id, "VALIDATION_FAILED" if errors else "READY",
         why="; ".join(errors) if errors else "")
    return {"ok": not errors, "level": level, "errors": errors,
            "warnings": warnings,
            "message": ("ready to launch" if level == "VALID" else
                        f"{len(warnings)} thing(s) to look at" if not errors
                        else f"cannot launch: " + "; ".join(errors))}


def save_ad_group(r, campaign_id, *, group_id="", name="", audience_id="",
                  budget_amount=None, bid=None, provider_config=None) -> dict:
    """The middle level. Called an ad group here whatever the platform
    calls it; LEVEL_WORDS holds the word to show a human."""
    if not r.one("media_campaigns", campaign_id):
        return {"ok": False, "message": "no such campaign"}
    gid = group_id or rid("adgrp", r.ws, campaign_id, name or now())
    cur = r.one("ad_groups", gid) or {"id": gid, "campaign_id": campaign_id}
    cur.update({"name": name or cur.get("name") or "Untitled ad group",
                "audience_id": audience_id,
                "budget_amount": budget_amount, "bid": bid,
                "provider_config": _D(provider_config), "state": "DRAFT"})
    rec = r.put("ad_groups", cur)
    return {"ok": True, "id": rec["id"], "message": f"{rec['name']!r} saved"}


def save_ad(r, ad_group_id, *, ad_id="", name="", creative_id="",
            landing_page_url="", provider_config=None) -> dict:
    g = r.one("ad_groups", ad_group_id)
    if not g:
        return {"ok": False, "message": "no such ad group"}
    aid = ad_id or rid("mad", r.ws, ad_group_id, name or now())
    cur = r.one("ads", aid) or {"id": aid, "ad_group_id": ad_group_id,
                                "campaign_id": g.get("campaign_id")}
    cur.update({"name": name or cur.get("name") or "Untitled ad",
                "creative_id": creative_id,
                "landing_page_url": landing_page_url,
                "provider_config": _D(provider_config), "state": "DRAFT"})
    rec = r.put("ads", cur)
    return {"ok": True, "id": rec["id"], "message": f"{rec['name']!r} saved"}


# ---------------------------------------------------------------------------
# SYNCHRONIZATION. The engine must never say ACTIVE while Meta says PAUSED.
# ---------------------------------------------------------------------------
def sync(r, provider=None) -> dict:
    """Reconcile this engine against the platforms.

    Read only. A difference is RECORDED and the internal state follows the
    platform, because the platform is the one actually spending the money.
    A tool that insists it is right and the platform is wrong is a tool
    that will eventually report a campaign as running for a week after it
    stopped."""
    started = now()
    providers = [provider] if provider else list(PROVIDERS)
    seen, changed, errors = 0, [], []
    for p in providers:
        ad = Adapter(p)
        ok, why = ad.available()
        if not ok:
            errors.append(f"{p}: {why}")
            continue
        for raw in ad.get_campaigns():
            seen += 1
            canon = normalize_campaign(p, raw)
            cid = rid("mcamp", r.ws, p, canon["external_campaign_id"])
            cur = r.one("media_campaigns", cid) or {"id": cid, "state": "DRAFT",
                                                    "source": "synced"}
            before = cur.get("state")
            cur.update(canon)
            cur["state"] = canon["state"]
            cur["synced_at"] = now()
            r.put("media_campaigns", cur)
            if before and before != canon["state"]:
                changed.append({"campaign": canon["name"], "provider": p,
                                "was": before, "now": canon["state"]})
    run = r.put("sync_runs", {
        "id": rid("syncrun", r.ws, started), "provider": provider or "all",
        "started_at": started, "completed_at": now(),
        "status": "OK" if not errors else "PARTIAL",
        "objects_synced": seen, "errors": errors, "changed": changed})
    return {"ok": True, "seen": seen, "changed": changed, "errors": errors,
            "run_id": run["id"],
            "message": (f"{seen} campaign(s) read"
                        + (f", {len(changed)} had changed at the platform"
                           if changed else ", none had drifted")
                        + (f". {len(errors)} platform(s) unreachable"
                           if errors else ""))}


def drift(r) -> list:
    """Where this engine and a platform currently disagree. The Campaign
    screen shows this at the top: a disagreement is the most important
    thing on a media screen and most tools hide it."""
    out = []
    for c in r.all("media_campaigns"):
        if not c.get("external_campaign_id"):
            continue
        internal = c.get("state")
        theirs = c.get("provider_status")
        if theirs and internal in ("ACTIVE", "PAUSED"):
            expect = "ACTIVE" if theirs in ("ACTIVE", "ENABLED") else "PAUSED"
            if expect != internal:
                out.append({"campaign": c.get("name"),
                            "provider": c.get("provider"),
                            "engine_says": internal, "platform_says": theirs,
                            "since": c.get("synced_at", "")})
    return out


def summary(r) -> dict:
    """What the Media command centre reads. Counts only; the money comes
    from content_engine_ads, which already computes it."""
    camps = r.all("media_campaigns")
    by_state = {}
    for c in camps:
        by_state[c.get("state")] = by_state.get(c.get("state"), 0) + 1
    runs = sorted(r.all("sync_runs"), key=lambda x: str(x.get("started_at")),
                  reverse=True)
    return {"campaigns": len(camps), "ad_groups": len(r.all("ad_groups")),
            "ads": len(r.all("ads")),
            "accounts": len([a for a in accounts(r) if a.get("live")]),
            "by_state": by_state, "drift": drift(r),
            "last_sync": (runs[0].get("completed_at") if runs else None),
            "platforms": [{"provider": p, **dict(zip(("live", "why"),
                                                     Adapter(p).available()))}
                          for p in PROVIDERS]}
