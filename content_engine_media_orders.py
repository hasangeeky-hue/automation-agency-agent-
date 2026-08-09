"""
content_engine_media_orders.py
============================================================================
THE MEDIA WORK-ORDER SPINE. One code registry, one dispatch, evidence on
every verdict, and NOTHING that spends money moves without a human.

WHY A SECOND ORDER SYSTEM EXISTS AT ALL
  The SEO orders repair pages; these move money and tracking. The action
  classes are deliberately harsher: there is NO "fix now" class for spend.
  Every spend-touching code is DRAFT (a human approves each one), and the
  tracking codes publish through Tag Manager's own approval gate.

THE ONE-DISPATCH RULE
  run_media_batch is the only executor. The dashboard buttons, the agent and
  the scheduler all call it, so a button can never behave differently from
  the nightly run. Orders a platform cannot execute yet are HELD with the
  reason written down, never silently dropped.
============================================================================
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

log = logging.getLogger("media_orders")

SETTING_KEY = "media_workorders"
LEVEL_KEY = "media_auto_level"
LEVELS = ("off", "observe", "propose")

# ---------------------------------------------------------------------------
# THE CODES - one list. Screens, dispatch, rules and gates all import THIS.
# ---------------------------------------------------------------------------
CODES = {
    "pause_campaign":  ("spend",    "pause a campaign whose CPA broke its target"),
    "resume_campaign": ("spend",    "resume a paused campaign"),
    "budget_shift":    ("spend",    "move budget toward what converts"),
    "bid_change":      ("spend",    "change a bid or bid cap"),
    "negative_keyword": ("spend",   "stop paying for a term you already win free"),
    "creative_rotate": ("creative", "rotate a fatigued creative; drafts a new one"),
    "audience_exclude": ("spend",   "exclude an audience that spends and never converts"),
    "landing_fix":     ("handoff",  "the paid landing page converts too poorly to fund"),
    "utm_fix":         ("tracking", "a campaign carries broken or missing UTMs"),
    "tag_missing":     ("tracking", "a required tag is absent from the container"),
    "tag_paused":      ("tracking", "a required tag exists but is paused or unpublished"),
    "pixel_missing":   ("tracking", "a channel pixel is absent from the container"),
    "event_silent":    ("tracking", "a tag exists but its event has not fired in 7 days"),
    # The planner's one decision. It lives HERE rather than in a second queue
    # so a launch waits behind the same approval tier as every other spend.
    "launch_campaign": ("spend",    "create a planned campaign on its platform"),
    "budget_allocate": ("spend",    "move budget between platforms on marginal return"),
}

# Every code is DRAFT: approved by a click, executed by the dispatch. The
# split below only decides WHICH machinery executes an approved order.
EXEC_VIA = {
    "pause_campaign": "google_ads", "resume_campaign": "google_ads",
    "budget_shift": "google_ads", "bid_change": "google_ads",
    "negative_keyword": "google_ads", "audience_exclude": "google_ads",
    "creative_rotate": "content_engine",
    "landing_fix": "seo_queue",
    "utm_fix": "gtm", "tag_missing": "gtm", "tag_paused": "gtm",
    "pixel_missing": "gtm", "event_silent": "gtm",
    "launch_campaign": "media_os", "budget_allocate": "media_os",
}

# THE UTM LAW - one table. The campaign builder writes these; the tracking
# screen and the verifier read the SAME dict. Two hand-written copies of this
# vocabulary is the bug class that has bitten this engine five times.
UTM_LAW = {
    "google":    {"utm_source": "google",   "utm_medium": "cpc"},
    "facebook":  {"utm_source": "facebook", "utm_medium": "paid_social"},
    "instagram": {"utm_source": "instagram", "utm_medium": "paid_social"},
    "linkedin":  {"utm_source": "linkedin", "utm_medium": "paid_social"},
    "tiktok":    {"utm_source": "tiktok",   "utm_medium": "paid_social"},
}
CLICK_IDS = ("gclid", "fbclid", "ttclid", "li_fat_id")

def utm_url(url: str, platform: str, campaign: str) -> str:
    """Stamp the UTM law onto a landing URL. Idempotent: a URL already
    carrying utm_source is returned untouched, because overwriting a human's
    deliberate tagging silently is worse than trusting it."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    if not url or platform not in UTM_LAW:
        return url
    parts = urlsplit(url)
    q = parse_qsl(parts.query, keep_blank_values=True)
    if any(k == "utm_source" for k, _v in q):
        return url
    slug = "".join(c if c.isalnum() else "_" for c in
                   str(campaign or "engine").lower())[:60] or "engine"
    q += list(UTM_LAW[platform].items()) + [("utm_campaign", slug)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(q), parts.fragment))


_EVIDENCE_FIELDS = ("metric", "threshold", "window", "source")

#: THE LIFECYCLE, per the spec: PROPOSED -> VALIDATED -> APPROVED ->
#: EXECUTING -> EXECUTED -> VERIFIED, with HELD/FAILED/DISMISSED as exits.
#: Storage keeps the short statuses the whole engine already uses;
#: lifecycle_of() derives the spec's word from what actually happened, so
#: the two vocabularies cannot drift apart (they are one function).
LIFECYCLE = ("PROPOSED", "VALIDATED", "APPROVED", "EXECUTING", "EXECUTED",
             "VERIFIED", "HELD", "FAILED", "DISMISSED")


def lifecycle_of(order) -> str:
    o = order or {}
    st = o.get("status")
    if st == "open":
        # every order that exists passed the evidence gate, so an open
        # order is already VALIDATED; PROPOSED is the state make_order
        # refuses to leave incomplete.
        return "VALIDATED"
    if st == "approved":
        return "APPROVED"
    if st == "done":
        return "VERIFIED" if o.get("verified_at") else "EXECUTED"
    if st == "held":
        return "HELD"
    if st == "failed":
        return "FAILED"
    if st == "dismissed":
        return "DISMISSED"
    return "PROPOSED"


# ---------------------------------------------------------------------------
# THE POLICY ENGINE. Configurable autonomy thresholds, per the spec.
#
# EVERY DEFAULT IS "approval". The founder's standing rule is that nothing
# spends without his click, so autonomy here is something he RAISES on the
# policy card, never something this file assumes. A policy the code turned
# on by itself would be the engine spending his money on its own opinion.
# ---------------------------------------------------------------------------
POLICY_KEY = "media_policy"
DEFAULT_POLICY = {
    "budget_change_auto_pct": 0,        # 0 = never automatic
    "pause_auto_if_daily_spend_under": 0.0,
    "negative_keyword": "approval",     # approval | auto
    "new_campaign": "approval",         # approval only; launch is never auto
    "targeting_change": "approval",
    "creative": "approval",
    "delete": "human_only",
}


def get_policy(store) -> dict:
    try:
        return {**DEFAULT_POLICY, **(store.get_setting(POLICY_KEY, {}) or {})}
    except Exception:
        return dict(DEFAULT_POLICY)


def set_policy(store, **kw) -> dict:
    pol = get_policy(store)
    changed = []
    for k, v in kw.items():
        if k not in DEFAULT_POLICY or v in (None, ""):
            continue
        if isinstance(DEFAULT_POLICY[k], str):
            if str(v) not in ("approval", "auto", "human_only"):
                return {"ok": False,
                        "message": f"{k} must be approval, auto or "
                                   f"human_only, not {v!r}"}
            pol[k] = str(v)
        else:
            try:
                pol[k] = float(v)
            except Exception:
                return {"ok": False, "message": f"{k} must be a number"}
        changed.append(k)
    store.set_setting(POLICY_KEY, pol)
    return {"ok": True, "policy": pol,
            "message": (f"policy updated: {', '.join(changed)}"
                        if changed else "nothing changed")}


def policy_gate(order, policy) -> tuple:
    """(verdict, why). auto | approval | human_only.

    Auto only when the founder RAISED the threshold above its zero
    default and the order's magnitude sits inside it."""
    o, pol = order or {}, policy or DEFAULT_POLICY
    code = o.get("code")
    ev = o.get("evidence") or {}
    if code in ("launch_campaign",):
        return ("approval", "a new campaign is never automatic")
    if code == "budget_shift":
        cap = float(pol.get("budget_change_auto_pct") or 0)
        pct = ev.get("change_pct")
        if cap and pct is not None and abs(float(pct)) <= cap:
            return ("auto", f"budget change {pct}% is inside the "
                            f"{cap:g}% auto threshold you set")
        return ("approval",
                "budget changes above the auto threshold (or with no "
                "stated percentage) wait for you"
                if cap else "the auto threshold is 0, so every budget "
                            "change waits for you")
    if code == "pause_campaign":
        cap = float(pol.get("pause_auto_if_daily_spend_under") or 0)
        daily = ev.get("daily_spend")
        if cap and daily is not None and float(daily) <= cap:
            return ("auto", f"daily spend {daily} is under the {cap:g} "
                            f"auto-pause threshold you set")
        return ("approval", "pausing waits for you"
                if not cap else "daily spend is above your auto threshold")
    if code == "negative_keyword":
        return ((pol.get("negative_keyword") or "approval"),
                "per your negative-keyword policy")
    if code in ("creative_rotate",):
        return ((pol.get("creative") or "approval"),
                "per your creative policy")
    if code in ("audience_exclude", "bid_change"):
        return ((pol.get("targeting_change") or "approval"),
                "per your targeting policy")
    return ("approval", "no policy names this code, so it waits for you")


def apply_policy(store, *, limit=20) -> dict:
    """Auto-approve open orders the policy explicitly allows.

    With the default policy this approves NOTHING, and says so."""
    pol = get_policy(store)
    orders = load(store)
    approved = []
    for o in orders:
        if o.get("status") != "open":
            continue
        verdict, why = policy_gate(o, pol)
        if verdict == "auto" and len(approved) < limit:
            o["status"] = "approved"
            o["approved_by"] = "policy"
            o["policy_why"] = why
            approved.append(o["id"])
    if approved:
        save(store, orders)
    return {"ok": True, "auto_approved": len(approved), "ids": approved,
            "message": (f"{len(approved)} order(s) auto-approved inside the "
                        f"thresholds you set; they still execute only when "
                        f"the dispatch runs"
                        if approved else
                        "nothing auto-approved: every open order is outside "
                        "your policy thresholds (the default policy "
                        "approves nothing).")}


def verify_orders(store) -> dict:
    """The VERIFIED step: check executed orders against the next platform
    read. An executed pause whose campaign still shows ENABLED on the next
    snapshot is a failure wearing a success flag."""
    snap = {}
    try:
        snap = store.get_setting("ads_snapshot", {}) or {}
    except Exception:
        pass
    camps = {str(c.get("id")): c
             for c in ((snap.get("ads") or {}).get("campaigns") or [])}
    at = str(snap.get("at") or "")
    orders = load(store)
    verified, unverifiable = 0, 0
    for o in orders:
        if o.get("status") != "done" or o.get("verified_at"):
            continue
        if o.get("done_at") and at and at <= str(o["done_at"]):
            unverifiable += 1
            o["verify_note"] = ("cannot verify yet: the last platform read "
                                "predates the execution. Pull platforms "
                                "again and re-run verify.")
            continue
        if o["code"] in ("pause_campaign", "resume_campaign"):
            c = camps.get(str((o.get("evidence") or {})
                              .get("campaign_ref") or o.get("key")))
            want = "PAUSED" if o["code"] == "pause_campaign" else "ENABLED"
            if c is None:
                unverifiable += 1
                o["verify_note"] = "the campaign is not in the snapshot"
            elif str(c.get("status")).upper() == want:
                o["verified_at"] = _now()
                o["after_state"] = {"status": c.get("status"),
                                    "read_at": at}
                verified += 1
            else:
                o["verify_note"] = (f"platform still says "
                                    f"{c.get('status')}; the write may not "
                                    f"have taken")
        else:
            unverifiable += 1
            o["verify_note"] = ("no read-back check exists for this code "
                                "yet; verified by eye is still verified "
                                "by someone")
    save(store, orders)
    return {"ok": True, "verified": verified, "unverifiable": unverifiable,
            "message": (f"{verified} order(s) verified against the platform "
                        f"read; {unverifiable} could not be checked and say "
                        f"why on the order.")}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _oid(code, key) -> str:
    return "mo_" + hashlib.sha1(f"{code}|{key}".encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------------------
def make_order(code, key, *, platform="", evidence=None, say="",
               confidence=None, confidence_basis="", expected_effect="",
               risk="") -> dict:
    """One decision the agent wants a human to make.

    REFUSES a verdict without full evidence. 'CPA too high' with no metric,
    threshold, window and source is an opinion, and the founder does not
    approve opinions.

    confidence is OPTIONAL and must arrive with its basis: a bare 0.87
    with no sentence about where it came from is the same opinion wearing
    decimals. Absent stays absent; it is never invented here."""
    if code not in CODES:
        raise ValueError(f"unknown media code {code!r}")
    ev = dict(evidence or {})
    missing = [f for f in _EVIDENCE_FIELDS if not ev.get(f)]
    if missing:
        raise ValueError(f"verdict {code} missing evidence fields: {missing}")
    if confidence is not None and not confidence_basis:
        raise ValueError("a confidence number needs its basis: say what "
                         "sample produced it")
    return {"id": _oid(code, key), "code": code, "kind": CODES[code][0],
            "key": str(key), "platform": platform, "evidence": ev,
            "say": say or CODES[code][1], "status": "open",
            "confidence": confidence, "confidence_basis": confidence_basis,
            "expected_effect": expected_effect,
            "risk": risk or ("MEDIUM" if CODES[code][0] == "spend" else "LOW"),
            "before_state": None, "after_state": None, "verified_at": None,
            "created_at": _now(), "result": "", "done_at": None}


def confidence_from_sample(n, floor) -> tuple:
    """(confidence, basis). Derived from evidence volume, never invented.

    Sits between 0.5 (barely at the floor) and 0.95, growing with how many
    times over the sample floor the evidence is."""
    try:
        n, floor = float(n or 0), float(floor or 1)
    except Exception:
        return None, ""
    if n < floor:
        return None, (f"below the sample floor ({n:g} of {floor:g}); no "
                      f"confidence is stated")
    import math as _math
    c = min(0.95, 0.5 + 0.1 * _math.log2(max(n / floor, 1.0)))
    return round(c, 2), (f"{n:g} observations against a floor of {floor:g}")


def load(store) -> list:
    try:
        return store.get_setting(SETTING_KEY, []) or []
    except Exception as e:
        log.warning("media order load failed: %s", e)
        return []


def save(store, orders) -> None:
    store.set_setting(SETTING_KEY, orders)


def upsert(store, new_orders) -> int:
    """Add verdicts that are not already queued. Re-running the rules must
    never duplicate a decision that is still waiting on the founder."""
    cur = load(store)
    seen = {o["id"] for o in cur}
    added = [o for o in new_orders if o["id"] not in seen]
    if added:
        save(store, cur + added)
    return len(added)


def mark(store, oid, status, result="") -> bool:
    orders = load(store)
    for o in orders:
        if o.get("id") == oid:
            o["status"] = status
            o["result"] = result
            if status in ("done", "held", "failed"):
                o["done_at"] = _now()
            save(store, orders)
            return True
    return False


def stats(orders) -> dict:
    open_ = [o for o in orders if o.get("status") == "open"]
    return {"total": len(orders), "open": len(open_),
            "by_kind": {k: sum(1 for o in open_ if o.get("kind") == k)
                        for k in ("spend", "tracking", "creative", "handoff")},
            "held": sum(1 for o in orders if o.get("status") == "held"),
            "done": sum(1 for o in orders if o.get("status") == "done")}


def auto_level(store) -> str:
    try:
        v = str(store.get_setting(LEVEL_KEY, "observe") or "observe").lower()
    except Exception:
        return "off"
    return v if v in LEVELS else "off"


def set_auto(store, level) -> dict:
    level = str(level or "").lower()
    if level not in LEVELS:
        return {"ok": False, "error": f"level must be one of {LEVELS}"}
    store.set_setting(LEVEL_KEY, level)
    return {"ok": True, "level": level, "message": {
        "off": "The media agent is OFF. Pulls still run; no verdicts.",
        "observe": "OBSERVE - the agent pulls and judges, and writes its "
                   "verdicts on the board, but drafts nothing.",
        "propose": "PROPOSE - verdicts become drafted orders in the queue. "
                   "Nothing spends until you approve each one.",
    }[level]}


# ---------------------------------------------------------------------------
# THE RULES - deterministic, evidence-first, honest about missing data
# ---------------------------------------------------------------------------
def rules_run(store, *, snap=None, inter=None, econ=None, insights=None,
              gtm_audit=None, **kwargs) -> dict:
    """Compute verdicts from what is REALLY there. A rule whose input is
    absent contributes a 'blind' note, never a guess."""
    verdicts, blind = [], []
    snap = snap or {}
    inter = inter or {}
    econ = econ or {}
    insights = insights or {}

    # R1 - CPA breach (needs a live ads pull AND a CPA target)
    ads = (snap.get("ads") or {})
    target = float((econ or {}).get("target_cpa") or 0)
    spend = float(ads.get("spend") or 0)
    conv = float(ads.get("conversions") or 0)
    if not ads or ads.get("reason"):
        blind.append("CPA rule: no ads pull on record (Google not connected)")
    elif not target:
        blind.append("CPA rule: no CPA target set in economics")
    elif conv and spend / conv > target * 1.5:
        verdicts.append(make_order(
            "pause_campaign", "account", platform="google",
            evidence={"metric": f"CPA {spend / conv:.2f}",
                      "threshold": f"target {target:.2f} x1.5",
                      "window": "7d", "source": "google_ads_pull"},
            say=f"CPA {spend / conv:.2f} is over 1.5x your {target:.2f} target"))

    # R2 - interlock: paid terms you already win organically (free, live)
    _bv = (inter.get("burn") or inter.get("overlap") or [])
    if isinstance(_bv, dict):
        _bv = list(_bv.values())
    for t in [x for x in _bv if isinstance(x, (dict, str))][:20]:
        term = t.get("term") if isinstance(t, dict) else str(t)
        verdicts.append(make_order(
            "negative_keyword", term, platform="google",
            evidence={"metric": f"organic position {t.get('position', '<=3') if isinstance(t, dict) else '<=3'}",
                      "threshold": "position <= 3", "window": "28d",
                      "source": "gsc_interlock"},
            say=f'you rank organically for "{term}" - stop paying for it'))
    if not inter:
        blind.append("interlock rule: no interlock snapshot yet")

    # R3 - paid landing pages that convert too poorly to fund (GA4, live)
    ga4 = (insights.get("ga4") or {})
    for p in (ga4.get("pages") or [])[:30]:
        try:
            sess = float(p.get("sessions") or 0)
            convs = float(p.get("conversions") or 0)
        except Exception:
            continue
        if sess >= 100 and convs / max(sess, 1) < 0.01:
            verdicts.append(make_order(
                "landing_fix", p.get("path") or p.get("page") or "?",
                evidence={"metric": f"{convs:.0f}/{sess:.0f} conversions",
                          "threshold": "< 1% with >= 100 sessions",
                          "window": "28d", "source": "ga4"},
                say="this page converts under 1%; fix it before funding it"))
    if not ga4:
        blind.append("landing rule: no GA4 insights on record")

    # R4 - tracking: the three-dots audit becomes orders (GTM, when granted)
    for miss in (gtm_audit or {}).get("missing") or []:
        verdicts.append(make_order(
            "tag_missing", miss.get("tag", "?"),
            evidence={"metric": "tag absent",
                      "threshold": "required by the tag registry",
                      "window": "now", "source": "gtm_audit"},
            say=f"required tag '{miss.get('tag')}' is not in the container"))
    for sil in (gtm_audit or {}).get("silent") or []:
        verdicts.append(make_order(
            "event_silent", sil.get("event", "?"),
            evidence={"metric": "0 events", "threshold": ">=1 in 7 days",
                      "window": "7d", "source": "ga4+gtm"},
            say=f"tag exists but event '{sil.get('event')}' fired 0 times in 7 days"))
    if gtm_audit is None:
        blind.append("tag rules: Tag Manager not granted yet")

    # R5 - monthly pacing: spend runs ahead of the cap's calendar share
    hist = kwargs.get("history") or []
    cap = float((econ or {}).get("monthly_budget") or 0)
    if not cap:
        blind.append("pacing rule: no monthly ad cap set in economics")
    elif not hist:
        blind.append("pacing rule: no spend history yet (fills daily)")
    else:
        from datetime import date as _d
        today = _d.today()
        month = today.isoformat()[:7]
        mtd = sum(float(h.get("spend") or 0) for h in hist
                  if str(h.get("date", "")).startswith(month))
        frac = today.day / 30.0
        if frac > 0 and cap and mtd > cap * frac * 1.3:
            verdicts.append(make_order(
                "budget_shift", f"pacing-{month}", platform="google",
                evidence={"metric": f"{mtd:.2f} spent by day {today.day}",
                          "threshold": f"130% of {cap * frac:.2f} pace",
                          "window": "month to date", "source": "ads_history"},
                say=f"spend {mtd:.2f} is running 30%+ ahead of the "
                    f"{cap:.0f}/month cap - cap or shift budget"))

    # R6 - creative fatigue: CTR last 7 days fell 30%+ vs the prior 7
    rows = [h for h in hist if h.get("clicks") is not None
            and h.get("impressions")]
    if len(rows) < 14:
        blind.append(f"creative-fatigue rule: needs 14 days of history, "
                     f"has {len(rows)}")
    else:
        def _ctr(seg):
            c = sum(float(h.get("clicks") or 0) for h in seg)
            im = sum(float(h.get("impressions") or 0) for h in seg)
            return (c / im) if im else 0.0
        last7, prior7 = _ctr(rows[-7:]), _ctr(rows[-14:-7])
        if prior7 > 0 and last7 < prior7 * 0.7:
            verdicts.append(make_order(
                "creative_rotate", "account-ctr", platform="google",
                evidence={"metric": f"CTR {last7:.3%} last 7d",
                          "threshold": f"30% under prior 7d {prior7:.3%}",
                          "window": "14d", "source": "ads_history"},
                say="click-through fell 30%+ week over week: the creative "
                    "is wearing out; rotate it"))

    return {"at": _now(), "verdicts": verdicts, "blind": blind}


def optimize(store, *, propose: bool) -> dict:
    """The agent's loop: gather real inputs, run the rules, and either just
    RECORD the verdicts (observe) or QUEUE them as drafts (propose)."""
    import content_engine_seo_ops as O
    import content_engine_ads as ADS
    snap = store.get_setting(O.K_ADS, {}) or {} if hasattr(store, "get_setting") else {}
    inter = store.get_setting(O.K_INTER, {}) or {} if hasattr(store, "get_setting") else {}
    econ = ADS.get_economics(store)
    insights = store.get_setting("google_insights", {}) or {}
    gtm_audit = store.get_setting("gtm_audit", None)
    hist = (store.get_setting("ads_history", []) or []
            if hasattr(store, "get_setting") else [])
    out = rules_run(store, snap=snap, inter=inter, econ=econ,
                    insights=insights, gtm_audit=gtm_audit, history=hist)
    store.set_setting("media_verdicts", {
        "at": out["at"], "blind": out["blind"],
        "verdicts": [{k: o[k] for k in ("id", "code", "key", "say",
                                        "evidence", "platform")}
                     for o in out["verdicts"]]})
    added = upsert(store, out["verdicts"]) if propose else 0
    return {"at": out["at"], "verdicts": len(out["verdicts"]),
            "drafted": added, "blind": out["blind"],
            "message": (f"{len(out['verdicts'])} verdict(s), "
                        + (f"{added} drafted for your approval"
                           if propose else "recorded only (observe)")
                        + (f"; blind on {len(out['blind'])} rule(s)"
                           if out["blind"] else ""))}


# ---------------------------------------------------------------------------
# THE DISPATCH - the only executor
# ---------------------------------------------------------------------------
def _stamp_before(store, o) -> None:
    """Record what the platform last said about this order's target."""
    try:
        if o.get("before_state") is not None:
            return
        snap = store.get_setting("ads_snapshot", {}) or {}
        camps = {str(c.get("id")): c
                 for c in ((snap.get("ads") or {}).get("campaigns") or [])}
        ref = str((o.get("evidence") or {}).get("campaign_ref")
                  or o.get("key"))
        c = camps.get(ref)
        orders = load(store)
        for x in orders:
            if x["id"] == o["id"]:
                x["before_state"] = (
                    {"status": c.get("status"), "budget": c.get("budget"),
                     "read_at": str(snap.get("at") or "")} if c else
                    {"note": "target not in the last platform read"})
        save(store, orders)
    except Exception as ex:
        log.warning("before_state stamp failed: %s", ex)


def _exec_launch(store, o) -> tuple:
    """Execute an APPROVED launch: create the campaign at the platform
    through the one adapter. Held in words when the platform is not
    connected or cannot express the campaign."""
    import content_engine_media_os as M
    r = M.repo(store)
    c = r.one("media_campaigns", o.get("key"))
    if not c:
        return ("failed", "the campaign behind this order no longer exists")
    ad = M.Adapter(c.get("provider") or "")
    live, why = ad.available()
    if not live:
        return ("held", f"{why}; the launch waits and executes the day the "
                        f"platform is connected")
    if c.get("state") == "SCHEDULED":
        M.move(r, c["id"], "LAUNCHING")
        c = r.one("media_campaigns", c["id"])
    try:
        got = ad.create_campaign(r, c)
    except Exception as ex:
        M.move(r, c["id"], "LAUNCH_FAILED",
               why=f"{type(ex).__name__}: {str(ex)[:100]}")
        return ("failed", f"{type(ex).__name__}: {str(ex)[:120]}")
    if (got or {}).get("hold"):
        return ("held", str(got.get("error"))[:160])
    if not (got or {}).get("ok"):
        M.move(r, c["id"], "PROVIDER_REJECTED",
               why=str((got or {}).get("error") or "")[:140])
        return ("failed", str((got or {}).get("error")
                              or "the platform rejected it")[:140])
    c["external_campaign_id"] = str((got or {}).get("campaign")
                                    or (got or {}).get("id") or "")
    r.put("media_campaigns", c)
    M.move(r, c["id"], "ACTIVE")
    return ("done", f"created on {c.get('provider')} as "
                    f"{c.get('external_campaign_id') or 'an unnamed id'}")


def run_media_batch(store, *, ids=None, limit: int = 20) -> dict:
    """Execute APPROVED orders. Executes what a connected platform allows,
    HOLDS the rest with the reason, hands off what belongs elsewhere."""
    orders = load(store)
    want = set(ids or ())
    batch = [o for o in orders if o.get("status") == "approved"
             and (not want or o["id"] in want)][:limit]
    rep = {"attempted": 0, "done": 0, "held": 0, "failed": 0, "details": []}
    for o in batch:
        rep["attempted"] += 1
        via = EXEC_VIA.get(o["code"], "none")
        try:
            if via == "google_ads":
                import content_engine_connectors as C
                ga = C.GoogleAds()
                if not ga.available():
                    out = ("held", "Google Ads is not connected; the order "
                                   "waits and executes the day it is")
                elif o["code"] == "pause_campaign":
                    r = ga.pause_campaign(o["key"])
                    out = (("done", r.get("detail", "paused")) if r.get("ok")
                           else ("failed", r.get("error", "")))
                elif o["code"] == "resume_campaign":
                    r = ga._mutate("campaigns", [{
                        "update": {"resourceName": o["key"],
                                   "status": "ENABLED"},
                        "updateMask": "status"}])
                    out = (("done", "resumed") if r.get("ok")
                           else ("failed", r.get("error", "")))
                elif o["code"] == "negative_keyword":
                    r = ga.add_negative_keyword(o["key"])
                    out = (("done", r.get("detail", "added")) if r.get("ok")
                           else ("failed", r.get("error", "")))
                elif o["code"] == "budget_shift":
                    amt = (o.get("evidence") or {}).get("new_daily_eur")
                    ref = (o.get("evidence") or {}).get("campaign_ref")
                    if amt and ref:
                        r = ga.set_campaign_budget(ref, float(amt))
                        out = (("done", r.get("detail", "budget set"))
                               if r.get("ok")
                               else ("failed", r.get("error", "")))
                    else:
                        out = ("held", "needs a campaign_ref and "
                                       "new_daily_eur on the order - set "
                                       "them when approving")
                elif o["code"] == "bid_change":
                    amt = (o.get("evidence") or {}).get("new_target_cpa_eur")
                    ref = (o.get("evidence") or {}).get("campaign_ref")
                    if amt and ref:
                        r = ga.set_target_cpa(ref, float(amt))
                        out = (("done", r.get("detail", "target set"))
                               if r.get("ok")
                               else ("failed", r.get("error", "")))
                    else:
                        out = ("held", "needs a campaign_ref and "
                                       "new_target_cpa_eur on the order")
                elif o["code"] == "audience_exclude":
                    ref = (o.get("evidence") or {}).get("campaign_ref")
                    ul = (o.get("evidence") or {}).get("user_list_ref")
                    if ref and ul:
                        r = ga.exclude_audience(ref, ul)
                        out = (("done", r.get("detail", "excluded"))
                               if r.get("ok")
                               else ("failed", r.get("error", "")))
                    else:
                        out = ("held", "needs campaign_ref and "
                                       "user_list_ref on the order")
                else:
                    out = ("held", f"{o['code']} has no Google write yet")
            elif via == "seo_queue":
                import content_engine_workorders as WO
                so = WO.make_order("thin_content", o["key"], severity="high",
                                   detail=o["say"])
                cur = WO.load(store)
                if so["id"] not in {x["id"] for x in cur}:
                    store.set_setting(WO.SETTING_KEY, cur + [so])
                out = ("done", "handed to the SEO page queue")
            elif via == "gtm":
                import content_engine_gtm as G
                out2 = G.execute_order(store, o)
                out = (out2.get("status", "held"), out2.get("result", ""))
            elif via == "content_engine":
                out = ("held", "creative drafting routes through the content "
                               "pipeline; press Draft on the creative board")
            elif via == "media_os":
                if o["code"] == "launch_campaign":
                    out = _exec_launch(store, o)
                else:
                    out = ("held", "budget allocation executes per campaign "
                                   "as budget_shift orders; approve those")
            else:
                out = ("held", "no executor for this code")
        except Exception as e:
            out = ("failed", f"{type(e).__name__}: {str(e)[:120]}")
        # before_state: what the last platform read said, recorded so the
        # audit can show before -> after instead of only "done".
        _stamp_before(store, o)
        mark(store, o["id"], out[0], out[1])
        rep[out[0]] = rep.get(out[0], 0) + 1
        rep["details"].append({"id": o["id"], "code": o["code"],
                               "status": out[0], "result": out[1]})
    return rep


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = []

    def t(name, cond):
        ok.append(bool(cond))
        print(("  OK   " if cond else "  FAIL ") + name)

    try:
        make_order("pause_campaign", "x", evidence={"metric": "1"})
        t("verdict without full evidence is refused", False)
    except ValueError:
        t("verdict without full evidence is refused", True)
    o = make_order("negative_keyword", "term", evidence={
        "metric": "pos 2", "threshold": "<=3", "window": "28d",
        "source": "gsc"})
    t("a full verdict builds", o["kind"] == "spend")
    t("every code has an executor route", set(CODES) == set(EXEC_VIA))
    t("UTM law covers all five platforms",
      set(UTM_LAW) == {"google", "facebook", "instagram", "linkedin", "tiktok"})

    class _S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v

    s = _S()
    t("upsert never duplicates a waiting decision",
      upsert(s, [o]) == 1 and upsert(s, [o]) == 0)
    r = rules_run(s)
    t("rules with no data are blind, not wrong",
      r["verdicts"] == [] and len(r["blind"]) >= 3)
    r2 = rules_run(s, inter={"burn": [{"term": "automation agency",
                                       "position": 2}]})
    t("the interlock rule fires on real data",
      len(r2["verdicts"]) == 1 and r2["verdicts"][0]["code"] == "negative_keyword")
    # dispatch: an approved google order with no connection is HELD, in words
    s2 = _S()
    o2 = dict(o, status="approved")
    save(s2, [o2])
    rep = run_media_batch(s2)
    t("an unexecutable approved order is held with the reason",
      rep["held"] == 1 and "not connected" in rep["details"][0]["result"])
    t("nothing ran that was not approved",
      run_media_batch(_S())["attempted"] == 0)
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
