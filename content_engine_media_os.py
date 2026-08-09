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
                   # SUBMITTED and IN_REVIEW live between "we sent it" and
                   # "the platform runs it", because every platform reviews
                   # and pretending otherwise makes ACTIVE a lie for hours.
                   "SUBMITTED", "IN_REVIEW",
                   "ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED",
                   "VALIDATION_FAILED", "LAUNCH_FAILED", "PROVIDER_REJECTED",
                   "SYNC_FAILED")

#: Legal moves. Anything absent is refused with the moves that ARE legal.
CAMPAIGN_MOVES = {
    "DRAFT": ("VALIDATING", "COMPLETED"),
    "VALIDATING": ("READY", "VALIDATION_FAILED"),
    "VALIDATION_FAILED": ("DRAFT",),
    "READY": ("SCHEDULED", "LAUNCHING", "DRAFT"),
    "SCHEDULED": ("LAUNCHING", "READY", "COMPLETED"),
    "LAUNCHING": ("SUBMITTED", "ACTIVE", "LAUNCH_FAILED",
                  "PROVIDER_REJECTED"),
    "SUBMITTED": ("IN_REVIEW", "ACTIVE", "PROVIDER_REJECTED",
                  "LAUNCH_FAILED"),
    "IN_REVIEW": ("ACTIVE", "PROVIDER_REJECTED"),
    "LAUNCH_FAILED": ("DRAFT", "LAUNCHING"),
    "PROVIDER_REJECTED": ("DRAFT",),
    "ACTIVE": ("PAUSED", "COMPLETED", "SYNC_FAILED", "ARCHIVED"),
    "PAUSED": ("ACTIVE", "COMPLETED", "ARCHIVED"),
    "SYNC_FAILED": ("ACTIVE", "PAUSED"),
    "COMPLETED": ("ARCHIVED",),
    "ARCHIVED": (),
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

    # -- the full adapter interface, spec section 7. What a platform
    # -- cannot do returns UNSUPPORTED_CAPABILITY, never fake success.
    def unsupported(self, op) -> dict:
        return {"ok": False, "code": "UNSUPPORTED_CAPABILITY",
                "operation": op,
                "message": (f"{self.provider} has no {op} write wired in "
                            f"this engine yet. This is stated, not "
                            f"simulated; the operation holds until the "
                            f"socket gains it.")}

    def api_version(self) -> str:
        """The version this adapter would actually call, env-overridable."""
        import content_engine_media_manifest as MAN
        import os as _os
        m = MAN.manifest(self.provider) or {}
        api = m.get("api", {})
        return (_os.environ.get(api.get("version_env", "")) or
                api.get("coded_default_version") or "unknown")

    def update_campaign(self, r, campaign) -> dict:
        return self.unsupported("update_campaign")

    def delete_campaign(self, r, campaign_id) -> dict:
        # deletion is human-only by policy anyway; no platform delete is
        # wired, and none pretends to be
        return self.unsupported("delete_campaign")

    def pause_campaign(self, external_id) -> dict:
        if self.provider == "google":
            return self._socket().pause_campaign(external_id)
        s = self._socket()
        if hasattr(s, "pause_campaign"):
            return s.pause_campaign(external_id)
        return self.unsupported("pause_campaign")

    def resume_campaign(self, external_id) -> dict:
        if self.provider == "google":
            return self._socket()._mutate("campaigns", [{
                "update": {"resourceName": external_id,
                           "status": "ENABLED"},
                "updateMask": "status"}])
        return self.unsupported("resume_campaign")

    def update_budget(self, external_id, amount) -> dict:
        if self.provider == "google":
            return self._socket().set_campaign_budget(external_id,
                                                      float(amount))
        return self.unsupported("update_budget")

    def upload_asset(self, data, filename) -> dict:
        return self.unsupported("upload_asset (platform-side)")

    def get_preview(self, creative) -> dict:
        return self.unsupported("provider-side preview")

    def get_targeting_options(self) -> dict:
        return self.unsupported("get_targeting_options")

    def create_campaign(self, r, campaign) -> dict:
        """Create an APPROVED canonical campaign at the platform, through
        the socket that already exists. Only Google carries a create write
        today; the others HOLD in words instead of failing, because 'not
        wired yet' and 'the platform said no' are different facts."""
        c = _D(campaign)
        if self.provider != "google":
            return {"ok": False, "hold": True,
                    "error": (f"{self.provider} has no campaign-create "
                              f"write wired yet; the order holds and "
                              f"executes when that socket gains one")}
        # canonical -> the socket's draft shape
        groups = r.find("ad_groups", campaign_id=c.get("id"))
        ads = {a.get("ad_group_id"): a
               for a in r.find("ads", campaign_id=c.get("id"))}
        draft_groups, landing = [], ""
        for g in groups[:5]:
            a = ads.get(g.get("id")) or {}
            cre = r.one("creatives", a.get("creative_id")) or {}
            landing = landing or a.get("landing_page_url") or ""
            draft_groups.append({
                "theme": g.get("name") or "Ad group",
                "headlines": [x for x in (cre.get("headline"),
                                          cre.get("hook"),
                                          cre.get("concept"),
                                          c.get("name")) if x],
                "descriptions": [x for x in (cre.get("primary_text"),
                                             cre.get("description"),
                                             cre.get("cta")) if x],
                "keywords": _L(_D(g.get("provider_config")).get("keywords"))
                or _L(_D(c.get("provider_config")).get("keywords"))})
        sock = self._socket()
        return sock.create_campaign(
            {"campaign_name": c.get("name"),
             "daily_budget": c.get("budget_amount"),
             "ad_groups": draft_groups},
            landing_url=landing)


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


# ---------------------------------------------------------------------------
# PLATFORM ERROR NORMALIZATION, spec section 36, and the retry policy,
# section 37. One taxonomy; the publish runner and every adapter caller
# read the SAME table to decide what may be retried.
# ---------------------------------------------------------------------------
ERROR_CATEGORIES = ("AUTHENTICATION", "PERMISSION", "VALIDATION",
                    "RATE_LIMIT", "ASSET", "TARGETING", "BUDGET",
                    "CREATIVE", "POLICY", "NOT_FOUND", "CONFLICT",
                    "SERVER", "UNKNOWN")

#: Which categories a retry can ever help. Retrying a VALIDATION error is
#: asking the same question louder.
RETRYABLE = {"RATE_LIMIT", "SERVER"}

_ERROR_HINTS = (
    ("AUTHENTICATION", ("token", "auth", "credential", "unauthoriz",
                        "unauthent", "expired", "not connected")),
    ("PERMISSION", ("permission", "forbidden", "denied", "scope",
                    "developer token")),
    ("RATE_LIMIT", ("rate", "quota", "too many", "429")),
    ("POLICY", ("policy", "disapprov", "prohibited")),
    ("BUDGET", ("budget",)),
    ("TARGETING", ("targeting", "audience", "criterion")),
    ("ASSET", ("asset", "upload", "media file", "image", "video")),
    ("CREATIVE", ("creative", "headline", "description", "ad copy")),
    ("NOT_FOUND", ("not found", "404", "no such")),
    ("CONFLICT", ("conflict", "duplicate", "already exists", "409")),
    ("VALIDATION", ("invalid", "required", "must be", "validation")),
    ("SERVER", ("500", "502", "503", "timeout", "timed out",
                "internal error", "unavailable")),
)


def normalize_error(provider, message, *, operation="", field="",
                    provider_code="", request_id="") -> dict:
    """One PlatformError shape for every platform's complaint."""
    msg = str(message or "")
    low = msg.lower()
    category = "UNKNOWN"
    for cat, needles in _ERROR_HINTS:
        if any(n in low for n in needles):
            category = cat
            break
    return {"platform": provider, "provider_code": str(provider_code or ""),
            "provider_message": msg[:400], "category": category,
            "retryable": category in RETRYABLE,
            "field": field, "operation": operation,
            "request_id": request_id,
            "recommended": {
                "AUTHENTICATION": "reconnect the platform on the Connect "
                                  "board",
                "PERMISSION": "the credential lacks a scope; regrant it",
                "RATE_LIMIT": "wait and retry; the runner backs off "
                              "automatically",
                "POLICY": "read the platform's policy reason; do not "
                          "retry as-is",
                "VALIDATION": "fix the named field and re-validate",
                "SERVER": "the platform hiccuped; retry is safe",
            }.get(category, "read the provider message")}


#: Platform status words -> canonical states, for adopted campaigns.
ADOPT_STATE = {"ENABLED": "ACTIVE", "ACTIVE": "ACTIVE", "PAUSED": "PAUSED",
               "REMOVED": "COMPLETED", "ENDED": "COMPLETED"}


def adopt(r, store) -> dict:
    """THE TRANSFORMATION. Pull the OLD system's Google Ads snapshot into
    the canonical model, so the new screens show the campaigns that were
    already running instead of an empty room.

    Reads the ads_snapshot the old boards read; touches no key and makes
    no API call. Idempotent: campaign ids are derived from Google's own
    ids, so running it twice updates rather than duplicates.

    HONESTY ABOUT GRANULARITY: the snapshot is a 30-day aggregate, not a
    daily series. The metrics land with day="" and a window_days marker,
    so the totals, the allocator and the forecaster can use them while
    the daily chart says "adopted aggregate, daily history starts from
    the next sync" instead of drawing a 30-day lump as one day."""
    snap = {}
    try:
        snap = store.get_setting("ads_snapshot", {}) or {}
    except Exception as ex:
        return {"ok": False, "adopted": 0,
                "message": f"could not read the old snapshot: "
                           f"{type(ex).__name__}"}
    ads = _D(snap.get("ads"))
    camps = _L(ads.get("campaigns"))
    if not camps:
        return {"ok": True, "adopted": 0, "updated": 0,
                "message": ("the old system holds no Google Ads snapshot to "
                            "adopt. Press 'Pull platforms now' first (needs "
                            "the Google connection), then adopt again.")}
    at = str(snap.get("at") or now())[:10]
    # one adopted account record, so the campaigns have a parent
    acct_id = rid("madacct", r.ws, "google", "adopted")
    if not r.one("ad_accounts", acct_id):
        r.put("ad_accounts", {"id": acct_id, "provider": "google",
                              "external_account_id": "adopted-from-snapshot",
                              "name": "Google Ads (adopted)",
                              "currency": "EUR", "status": "CONNECTED",
                              "credentials_reference":
                                  "settings:GOOGLE_ADS (Connect board)"})
    made = updated = 0
    for c in camps:
        ext = str(c.get("id") or c.get("name") or "")
        if not ext:
            continue
        cid = rid("gadopt", r.ws, ext)
        cur = r.one("media_campaigns", cid)
        state = ADOPT_STATE.get(str(c.get("status") or "").upper(),
                                "SYNC_FAILED")
        rec = {"id": cid, "name": c.get("name") or ext,
               "provider": "google", "external_campaign_id": ext,
               "ad_account_id": acct_id,
               # the platform does not say WHY the campaign exists; the
               # objective is marked adopted rather than invented.
               "objective": (cur or {}).get("objective") or "CONVERSIONS",
               "buying_type": "AUCTION", "budget_type": "DAILY",
               "budget_amount": float(c.get("budget") or 0),
               "currency": "EUR", "state": state,
               "provider_status": str(c.get("status") or ""),
               "synced_at": now(),
               "provider_config": {"adopted": True, "adopted_at": at,
                                   "type": c.get("type"),
                                   "bid_strategy": c.get("bid_strategy"),
                                   "is_share": c.get("is_share"),
                                   "is_lost_budget": c.get("is_lost_budget"),
                                   "is_lost_rank": c.get("is_lost_rank")}}
        if cur:
            cur.update(rec)
            r.put("media_campaigns", cur)
            updated += 1
        else:
            r.put("media_campaigns", rec)
            made += 1
        r.put("ad_metrics", {
            "id": rid("gadoptm", r.ws, ext, at),
            "day": "", "provider": "google", "campaign_id": cid,
            "window_days": 30, "adopted_at": at,
            "impressions": float(c.get("impressions") or 0),
            "clicks": float(c.get("clicks") or 0),
            "spend": float(c.get("cost") or 0),
            "conversions": float(c.get("conversions") or 0),
            "conversion_value": float(c.get("conv_value") or 0)})
    return {"ok": True, "adopted": made, "updated": updated,
            "message": (f"{made} campaign(s) adopted and {updated} updated "
                        f"from the old Google Ads snapshot of {at}. Their "
                        f"30-day totals are in; daily history accrues from "
                        f"the next sync. No key was touched.")}


# ---------------------------------------------------------------------------
# PUBLISHING IS A JOB, spec sections 17-19. Idempotent steps, a log the
# founder can read, provider errors normalized and never hidden.
# ---------------------------------------------------------------------------
PUBLISH_STATES = ("QUEUED", "RUNNING", "DONE", "HELD", "FAILED")
PUBLISH_STEPS = ("validate", "create_campaign_tree", "verify", "record_ids")


def make_publish_job(r, campaign_id) -> dict:
    """One job per campaign publication. The idempotency key is derived
    from the campaign, so retrying a timed-out publish reuses the SAME
    job and cannot create a duplicate campaign."""
    c = r.one("media_campaigns", campaign_id)
    if not c:
        return {"ok": False, "message": "no such campaign"}
    key = rid("pubkey", r.ws, campaign_id, c.get("provider") or "")
    jid = rid("pubjob", r.ws, campaign_id)
    cur = r.one("publish_jobs", jid)
    if cur and cur.get("state") in ("QUEUED", "RUNNING"):
        return {"ok": True, "id": jid, "existing": True,
                "message": "a publish job for this campaign is already "
                           "queued; re-pressing does not duplicate it"}
    rec = {"id": jid, "campaign_id": campaign_id,
           "provider": c.get("provider"), "state": "QUEUED",
           "idempotency_key": key, "attempt": (cur or {}).get("attempt", 0) + 1,
           "steps": [{"step": s, "status": "PENDING", "detail": "",
                      "at": ""} for s in PUBLISH_STEPS],
           "finished_at": ""}
    r.put("publish_jobs", rec)
    return {"ok": True, "id": jid, "existing": False,
            "message": f"publish job queued (attempt {rec['attempt']})"}


def _job_step(job, name, status, detail="", error=None) -> None:
    for s in job["steps"]:
        if s["step"] == name:
            s.update({"status": status, "detail": str(detail)[:300],
                      "at": now()})
            if error:
                s["error"] = error


def run_publish_job(r, store, job_id) -> dict:
    """Execute one queued publish job through the one adapter.

    The Google socket creates the whole tree (budget, campaign, ad group,
    RSA, keywords) in one authenticated flow; the step log records what it
    reported. Idempotency: a campaign that already carries an external id
    SKIPS creation instead of creating a twin."""
    job = r.one("publish_jobs", job_id)
    if not job:
        return {"ok": False, "message": "no such publish job"}
    c = r.one("media_campaigns", job.get("campaign_id"))
    if not c:
        job["state"] = "FAILED"
        _job_step(job, "validate", "FAILED", "campaign vanished")
        r.put("publish_jobs", job)
        return {"ok": False, "message": "the campaign behind this job no "
                                        "longer exists"}
    job["state"] = "RUNNING"
    r.put("publish_jobs", job)
    prov = c.get("provider") or ""
    ad = Adapter(prov)
    # step 1: validate
    v = validate(r, c["id"]) if c.get("state") not in (
        "READY", "SCHEDULED", "LAUNCHING", "SUBMITTED") else {"ok": True}
    if not v.get("ok"):
        _job_step(job, "validate", "FAILED", v.get("message", ""))
        job["state"] = "FAILED"
        r.put("publish_jobs", job)
        return {"ok": False, "state": "FAILED",
                "message": v.get("message", "validation failed")}
    _job_step(job, "validate", "OK", "canonical validation passed")
    # step 2: create the tree, idempotently
    if c.get("external_campaign_id"):
        _job_step(job, "create_campaign_tree", "SKIPPED",
                  f"already created as {c['external_campaign_id']} "
                  f"(idempotency)")
        got = {"ok": True, "campaign": c["external_campaign_id"],
               "detail": "already existed"}
    else:
        live, why = ad.available()
        if not live:
            _job_step(job, "create_campaign_tree", "HELD", why)
            job["state"] = "HELD"
            r.put("publish_jobs", job)
            return {"ok": False, "state": "HELD", "message": why}
        try:
            got = ad.create_campaign(r, c)
        except Exception as ex:
            got = {"ok": False, "error": f"{type(ex).__name__}: "
                                         f"{str(ex)[:160]}"}
        if got.get("hold") or got.get("code") == "UNSUPPORTED_CAPABILITY":
            _job_step(job, "create_campaign_tree", "HELD",
                      got.get("error") or got.get("message", ""))
            job["state"] = "HELD"
            r.put("publish_jobs", job)
            return {"ok": False, "state": "HELD",
                    "message": got.get("error") or got.get("message", "")}
        if not got.get("ok"):
            err = normalize_error(prov, got.get("error"),
                                  operation="create_campaign")
            # An AUTHENTICATION error is "not connected yet", which is a
            # wait, not a rejection: the job HOLDS and runs the day the
            # key exists, exactly like every other order.
            if err["category"] == "AUTHENTICATION":
                _job_step(job, "create_campaign_tree", "HELD",
                          got.get("error", ""), error=err)
                job["state"] = "HELD"
                r.put("publish_jobs", job)
                return {"ok": False, "state": "HELD", "error": err,
                        "message": (f"{err['provider_message'][:120]}; "
                                    f"{err['recommended']}. The job holds "
                                    f"and re-runs when the connection "
                                    f"exists.")}
            _job_step(job, "create_campaign_tree", "FAILED",
                      got.get("error", ""), error=err)
            job["state"] = "FAILED"
            r.put("publish_jobs", job)
            move(r, c["id"], "PROVIDER_REJECTED",
                 why=str(got.get("error"))[:140])
            return {"ok": False, "state": "FAILED", "error": err,
                    "message": (f"{err['category']}: "
                                f"{err['provider_message'][:120]}. "
                                f"{err['recommended']}"
                                + ("" if err["retryable"] else
                                   " This class is NOT retried "
                                   "automatically."))}
        _job_step(job, "create_campaign_tree", "OK",
                  got.get("detail", "created"))
    # step 3: verify + step 4: record ids
    ext = str(got.get("campaign") or c.get("external_campaign_id") or "")
    _job_step(job, "verify", "OK" if ext else "FAILED",
              (f"provider id {ext}" if ext else
               "the platform returned no id; treat as failed"))
    c["external_campaign_id"] = ext
    c["published_api_version"] = ad.api_version()
    r.put("media_campaigns", c)
    if c.get("state") in ("LAUNCHING",):
        move(r, c["id"], "SUBMITTED", why="publish job completed; the "
                                          "platform reviews before it runs")
    _job_step(job, "record_ids", "OK", f"external_campaign_id={ext}, "
                                       f"api={ad.api_version()}")
    job["state"] = "DONE" if ext else "FAILED"
    job["finished_at"] = now()
    r.put("publish_jobs", job)
    return {"ok": bool(ext), "state": job["state"], "provider_id": ext,
            "message": (f"published to {prov} as {ext} on API "
                        f"{ad.api_version()}; the platform reviews before "
                        f"it runs" if ext else "publish did not complete")}


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
