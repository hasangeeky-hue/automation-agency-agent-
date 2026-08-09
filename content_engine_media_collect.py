"""
content_engine_media_collect.py
============================================================================
THE DATA COLLECTION LAYER. Spec sections 2, 3, 4, 58, 59, 60.

ONE REPORTING COLLECTOR PER PLATFORM, and each one answers honestly for
every breakdown: it either returns rows or it returns UNSUPPORTED_CAPABILITY.
It never manufactures a breakdown the provider does not expose. The four
providers genuinely differ (Google reports through GAQL resources, metrics
and segments; Meta through metrics plus breakdowns; TikTok through
dimensions plus metrics; LinkedIn through account/campaign/creative
analytics with demographic pivots and privacy thresholds), and this file
records that difference rather than flattening it.

THE PIPELINE, in the spec's order:
  Scheduler -> Sync Job -> Adapter -> API request -> RAW STORAGE ->
  Normalization -> Validation -> Deduplication -> Fact rows

RAW IS NEVER DELETED. Every response lands in provider_raw_metrics with a
checksum and the api_version that produced it, because the day a number
disagrees with the platform's own UI, the original payload is the only
thing that settles the argument.

WHAT IS HONESTLY NOT HERE: Google is the only platform whose read socket
this engine can currently drive, so the other three collectors return
UNSUPPORTED_CAPABILITY per report type rather than pretending. That is a
stated limit, not a simulation.
============================================================================
"""

from __future__ import annotations

import hashlib
import json
import logging

import content_engine_media_manifest as MAN
import content_engine_media_os as M
from content_engine_os_core import _D, _L, now, rid

log = logging.getLogger("content_engine.media_collect")

#: The report types the spec names. A collector answers each one.
REPORT_TYPES = ("account", "campaign", "ad_group", "ad", "creative",
                "placement", "geo", "device", "audience", "conversion")

#: What each platform's REPORTING api actually exposes, per the manifest
#: research. UNKNOWN means the research did not verify it, and an unverified
#: capability is treated as unsupported rather than attempted blindly.
REPORT_SUPPORT = {
    "google":   {"account": True, "campaign": True, "ad_group": True,
                 "ad": True, "creative": False, "placement": True,
                 "geo": True, "device": True, "audience": True,
                 "conversion": True},
    "meta":     {"account": True, "campaign": True, "ad_group": True,
                 "ad": True, "creative": True, "placement": True,
                 "geo": True, "device": True, "audience": True,
                 "conversion": True},
    "tiktok":   {"account": True, "campaign": True, "ad_group": True,
                 "ad": True, "creative": True, "placement": False,
                 "geo": True, "device": True, "audience": True,
                 "conversion": True},
    "linkedin": {"account": True, "campaign": True, "ad_group": True,
                 "ad": True, "creative": True, "placement": False,
                 "geo": True, "device": False, "audience": True,
                 "conversion": True},
}

#: Which of those this ENGINE can currently drive. The gap between
#: REPORT_SUPPORT and DRIVEN is the honest work-remaining list.
DRIVEN = {"google": {"account", "campaign"}}

#: §60 Late conversions. How many trailing days are re-fetched and allowed
#: to CHANGE, per provider. Configurable, because platforms differ.
BACKFILL_DAYS = {"google": 7, "meta": 7, "tiktok": 3, "linkedin": 14}

#: §58 One reporting currency. Rows keep their own; conversion is recorded
#: with its rate and date or it does not happen.
REPORTING_CURRENCY = "EUR"


def unsupported(provider, report_type, why="") -> dict:
    return {"ok": False, "code": "UNSUPPORTED_CAPABILITY",
            "platform": provider, "report_type": report_type, "rows": [],
            "message": (why or
                        (f"{provider} exposes {report_type} reporting, but "
                         f"this engine has no collector wired for it yet"
                         if _D(REPORT_SUPPORT.get(provider)).get(report_type)
                         else f"{provider} does not expose {report_type} "
                              f"reporting; nothing is manufactured"))}


class ReportingCollector:
    """One per platform. Same interface, honest answers."""

    def __init__(self, provider):
        self.provider = str(provider or "").lower()
        self.adapter = M.Adapter(self.provider)

    def api_version(self) -> str:
        return self.adapter.api_version()

    def supports(self, report_type) -> bool:
        return bool(_D(REPORT_SUPPORT.get(self.provider)).get(report_type))

    def fetch(self, report_type, **kw) -> dict:
        """The one entry point; fetch_<type> names below are aliases so the
        spec's method list reads literally."""
        if report_type not in REPORT_TYPES:
            return {"ok": False, "code": "UNKNOWN_REPORT",
                    "message": f"{report_type!r} is not a report type. "
                               f"They are: " + ", ".join(REPORT_TYPES)}
        if report_type not in DRIVEN.get(self.provider, set()):
            return unsupported(self.provider, report_type)
        live, why = self.adapter.available()
        if not live:
            return {"ok": False, "code": "NOT_CONNECTED", "rows": [],
                    "message": why}
        try:
            if report_type == "account":
                raw = self.adapter.get_account()
                rows = [raw] if raw else []
            else:
                rows = _L(self.adapter.get_campaigns())
            return {"ok": True, "rows": rows, "raw": rows,
                    "api_version": self.api_version(),
                    "message": f"{len(rows)} raw row(s) from "
                               f"{self.provider} {report_type}"}
        except Exception as ex:
            err = M.normalize_error(self.provider, str(ex),
                                    operation=f"fetch_{report_type}")
            return {"ok": False, "code": err["category"], "rows": [],
                    "error": err, "message": err["provider_message"][:160]}

    # the spec's literal method names
    def fetch_account_metrics(self, **kw):
        return self.fetch("account", **kw)

    def fetch_campaign_metrics(self, **kw):
        return self.fetch("campaign", **kw)

    def fetch_ad_group_metrics(self, **kw):
        return self.fetch("ad_group", **kw)

    def fetch_ad_metrics(self, **kw):
        return self.fetch("ad", **kw)

    def fetch_creative_metrics(self, **kw):
        return self.fetch("creative", **kw)

    def fetch_placement_metrics(self, **kw):
        return self.fetch("placement", **kw)

    def fetch_geo_metrics(self, **kw):
        return self.fetch("geo", **kw)

    def fetch_device_metrics(self, **kw):
        return self.fetch("device", **kw)

    def fetch_audience_metrics(self, **kw):
        return self.fetch("audience", **kw)

    def fetch_conversion_metrics(self, **kw):
        return self.fetch("conversion", **kw)


def collectors() -> dict:
    return {p: ReportingCollector(p) for p in MAN.MANIFEST}


# ---------------------------------------------------------------------------
# RAW STORAGE (§4)
# ---------------------------------------------------------------------------
def store_raw(r, *, platform, account_id, object_type, object_id,
              report_date, api_version, payload) -> dict:
    body = json.dumps(payload, sort_keys=True, default=str)
    checksum = hashlib.sha256(body.encode()).hexdigest()[:32]
    rec = {"id": rid("raw", r.ws, platform, object_type, str(object_id),
                     str(report_date)),
           "platform": platform, "account_id": account_id,
           "provider_object_type": object_type,
           "provider_object_id": str(object_id),
           "report_date": str(report_date), "api_version": api_version,
           "retrieved_at": now(), "checksum": checksum, "payload": payload}
    r.put("provider_raw_metrics", rec)
    return {"ok": True, "id": rec["id"], "checksum": checksum}


# ---------------------------------------------------------------------------
# NORMALIZATION + VALIDATION + DEDUPLICATION (§3)
# ---------------------------------------------------------------------------
#: provider field -> canonical fact field. Declared per platform because
#: the providers genuinely name things differently.
FIELD_MAP = {
    "google": {"cost": "spend", "impressions": "impressions",
               "clicks": "clicks", "conversions": "conversions",
               "conv_value": "conversion_value"},
    "meta": {"spend": "spend", "impressions": "impressions",
             "reach": "reach", "frequency": "frequency",
             "clicks": "clicks", "inline_link_clicks": "link_clicks",
             "actions": "conversions"},
    "tiktok": {"spend": "spend", "impressions": "impressions",
               "clicks": "clicks", "conversion": "conversions",
               "total_purchase_value": "conversion_value"},
    "linkedin": {"costInLocalCurrency": "spend",
                 "impressions": "impressions", "clicks": "clicks",
                 "externalWebsiteConversions": "conversions"},
}

_NUMERIC = ("spend", "impressions", "reach", "frequency", "clicks",
            "link_clicks", "landing_page_views", "engagements",
            "video_views", "video_25", "video_50", "video_75", "video_100",
            "leads", "add_to_cart", "checkout", "purchases", "conversions",
            "conversion_value")


def normalize_row(provider, raw, *, day, campaign_id="", currency="EUR",
                  is_estimated=False, freshness="") -> dict:
    """Provider shape in, canonical fact row out. Unmapped provider fields
    are KEPT under provider_native so nothing is thrown away (§8 of the
    omnichannel spec, and the reason raw is preserved at all)."""
    src = _D(raw)
    fmap = FIELD_MAP.get(provider, {})
    out = {"provider": provider, "day": str(day)[:10],
           "campaign_id": campaign_id, "currency": currency,
           "is_estimated": bool(is_estimated),
           "data_freshness": freshness or now(),
           "provider_native": {}}
    for k, v in src.items():
        canon = fmap.get(k)
        if canon:
            out[canon] = v
        elif k not in ("id", "name", "status"):
            out["provider_native"][k] = v
    # the platform's own conversion claim is kept SEPARATE from ours
    if "conversions" in out:
        out["provider_reported_conversions"] = out["conversions"]
    if "conversion_value" in out:
        out["provider_reported_conversion_value"] = out["conversion_value"]
    return out


def validate_row(row) -> tuple:
    """(ok, reason). A row that cannot be trusted is DROPPED and counted,
    never written half-true."""
    d = _D(row)
    if not d.get("provider"):
        return False, "no provider"
    if not str(d.get("day") or "")[:10]:
        return False, "no report date"
    for k in _NUMERIC:
        if k in d and d[k] is not None:
            try:
                v = float(d[k])
            except Exception:
                return False, f"{k} is not a number"
            if v < 0:
                return False, f"{k} is negative"
    return True, ""


def fact_id(r, row) -> str:
    """The deduplication key. Same platform + day + hour + object = one
    row, so re-fetching a day REPLACES rather than doubles it. This is also
    what makes late-conversion backfill safe (§60)."""
    d = _D(row)
    return rid("fact", r.ws, d.get("provider"), str(d.get("day"))[:10],
               str(d.get("hour") or ""), d.get("campaign_id") or "",
               d.get("ad_group_id") or "", d.get("ad_id") or "",
               d.get("creative_id") or "", d.get("device") or "",
               d.get("placement") or "", d.get("country") or "")


def convert_currency(row, *, rate=None, rate_date="") -> dict:
    """§58. No silent addition across currencies: either a rate is supplied
    and RECORDED with the row, or the row keeps its own currency and the
    quality layer flags the slice as mixed."""
    d = dict(_D(row))
    cur = str(d.get("currency") or REPORTING_CURRENCY)
    if cur == REPORTING_CURRENCY:
        d["exchange_rate"] = 1.0
        d["exchange_rate_date"] = ""
        return d
    if not rate:
        d["exchange_rate"] = None
        d["conversion_note"] = (f"{cur} was NOT converted to "
                                f"{REPORTING_CURRENCY}: no exchange rate "
                                f"was supplied, and inventing one would "
                                f"corrupt every total downstream")
        return d
    for k in ("spend", "conversion_value",
              "provider_reported_conversion_value"):
        if d.get(k) is not None:
            try:
                d[k] = round(float(d[k]) * float(rate), 4)
            except Exception:
                pass
    d.update({"currency": REPORTING_CURRENCY, "exchange_rate": float(rate),
              "exchange_rate_date": rate_date or now()[:10],
              "original_currency": cur})
    return d


# ---------------------------------------------------------------------------
# THE SYNC JOB (§3)
# ---------------------------------------------------------------------------
def run_sync_job(r, *, platform, report_type="campaign", date_from="",
                 date_to="", fx=None) -> dict:
    """One accounted collection run: received, written, failed, all named."""
    started = now()
    col = ReportingCollector(platform)
    jid = rid("syncjob", r.ws, platform, report_type, started)
    job = {"id": jid, "platform": platform, "report_type": report_type,
           "date_from": date_from, "date_to": date_to,
           "started_at": started, "status": "RUNNING",
           "api_version": col.api_version(),
           "records_received": 0, "records_written": 0,
           "records_failed": 0, "error": "",
           "freshness_timestamp": ""}
    r.put("sync_jobs", job)
    got = col.fetch(report_type)
    if not got.get("ok"):
        job.update({"status": ("UNSUPPORTED"
                               if got.get("code") == "UNSUPPORTED_CAPABILITY"
                               else "HELD" if got.get("code") == "NOT_CONNECTED"
                               else "FAILED"),
                    "completed_at": now(), "error": got.get("message", "")})
        r.put("sync_jobs", job)
        return {"ok": False, "job_id": jid, "status": job["status"],
                "message": got.get("message", "")}
    rows = _L(got.get("rows"))
    job["records_received"] = len(rows)
    day = (date_to or now())[:10]
    written = failed = 0
    reasons = []
    for raw in rows:
        store_raw(r, platform=platform, account_id="",
                  object_type=report_type,
                  object_id=_D(raw).get("id") or _D(raw).get("name") or "?",
                  report_date=day, api_version=col.api_version(),
                  payload=raw)
        row = normalize_row(platform, raw, day=day,
                            campaign_id=str(_D(raw).get("id") or ""),
                            freshness=now())
        row = convert_currency(row, rate=_D(fx).get(row.get("currency")),
                               rate_date=_D(fx).get("date", ""))
        ok, why = validate_row(row)
        if not ok:
            failed += 1
            reasons.append(why)
            continue
        row["id"] = fact_id(r, row)
        r.put("ad_metrics", row)
        written += 1
    job.update({"records_written": written, "records_failed": failed,
                "status": "OK" if not failed else "PARTIAL",
                "completed_at": now(), "freshness_timestamp": now(),
                "error": "; ".join(sorted(set(reasons))[:3])})
    r.put("sync_jobs", job)
    return {"ok": True, "job_id": jid, "received": len(rows),
            "written": written, "failed": failed,
            "message": (f"{platform} {report_type}: {len(rows)} received, "
                        f"{written} written, {failed} dropped"
                        + (f" ({job['error']})" if failed else "")
                        + ". Raw responses kept for every one.")}


def backfill_window(provider) -> dict:
    """§60. Which trailing days are still allowed to change."""
    days = BACKFILL_DAYS.get(provider, 7)
    return {"provider": provider, "days": days,
            "message": (f"the last {days} day(s) of {provider} are re-fetched "
                        f"and may still change; older days are treated as "
                        f"settled. Late conversions land through the same "
                        f"dedup key, so a re-fetch updates rather than "
                        f"doubles.")}


def collection_status(r) -> dict:
    """What the Data Health screen reads about COLLECTION specifically."""
    jobs = sorted(r.all("sync_jobs"),
                  key=lambda j: str(j.get("started_at") or ""), reverse=True)
    per = {}
    for j in jobs:
        p = j.get("platform")
        if p and p not in per:
            per[p] = {"status": j.get("status"),
                      "at": j.get("completed_at") or j.get("started_at"),
                      "received": j.get("records_received"),
                      "written": j.get("records_written"),
                      "failed": j.get("records_failed"),
                      "api_version": j.get("api_version"),
                      "error": j.get("error")}
    gaps = []
    for p, sup in REPORT_SUPPORT.items():
        for rt, yes in sup.items():
            if yes and rt not in DRIVEN.get(p, set()):
                gaps.append(f"{p}.{rt}")
    return {"per_platform": per, "raw_rows": len(r.all("provider_raw_metrics")),
            "jobs": len(jobs), "undriven_report_types": sorted(gaps),
            "message": (f"{len(jobs)} sync job(s) on record, "
                        f"{len(r.all('provider_raw_metrics'))} raw response(s) "
                        f"kept. {len(gaps)} provider report type(s) are "
                        f"supported by the platform but NOT yet driven by "
                        f"this engine; they are listed rather than hidden.")}
