"""
content_engine_media_perf.py
============================================================================
PHASE 4: ROLLUPS, ATTRIBUTION, ANOMALIES, AND THE OPTIMISATION VERDICTS.

FIVE GRAINS, ONE ARITHMETIC
  The same numbers viewed by hour, day, week and month, plus the raw rows
  underneath. Every derived metric carries its denominator, and a metric
  over nothing comes back None with a sentence, never 0. Zero clicks on a
  thousand impressions is a measurement. Zero clicks on zero impressions
  is an absence, and printing 0.0% for both is how a founder ends up
  optimising against a number that was never there.

ATTRIBUTION LOOKS AT ONE TIMELINE
  A person does not have an email history and a separate paid history.
  They have a history. Attribution therefore walks the SHARED event layer
  the email OS already writes into, and paid clicks and paid conversions
  are event kinds in that same layer rather than a second store.

  Five models, and the reason all five exist is that they disagree. The
  screen shows the disagreement rather than picking a favourite and
  calling it truth.

RECONCILIATION REFUSES TO PICK A SIDE
  The platform claims conversions. The engine observed conversions. When
  they differ, reconcile() reports the gap and names both numbers. It does
  not quietly prefer one, because the platform counts view-through and the
  engine cannot see it, and neither of those is a lie.

ANOMALIES NEED A BASELINE THEY HAVE EARNED
  An alert computed against three days of history is a coin toss with a
  red badge on it. scan() refuses to judge a campaign whose baseline is
  thinner than MIN_BASELINE_DAYS and says so.

VERDICTS GO INTO THE QUEUE THAT ALREADY EXISTS
  propose() writes into content_engine_media_orders. Same codes, same
  evidence contract, same approval tier. There is no second queue, no
  new agent, and nothing here can spend money.
============================================================================
"""

from __future__ import annotations

import datetime as _dt
import logging

import content_engine_media_creative as MC
import content_engine_media_os as M
import content_engine_media_plan as MP
import content_engine_os_core as CORE
from content_engine_os_core import _D, now, rate, rid

log = logging.getLogger("content_engine.media_perf")

#: The grains. RAW is the rows as the platform gave them; the rest are
#: buckets over those rows. Declared once so the selector, the rollup and
#: the anomaly window cannot disagree about what a week is.
GRAINS = ("RAW", "HOURLY", "DAILY", "WEEKLY", "MONTHLY")

#: What the platforms actually report. Everything else is derived from
#: these, which is why there is no "ctr" column anywhere in the schema.
BASE_METRICS = ("impressions", "clicks", "spend", "conversions",
                "conversion_value")

#: name -> (numerator, denominator, multiplier, how to read it)
DERIVED = {
    "ctr":  ("clicks", "impressions", 100.0, "percent of impressions clicked"),
    "cpc":  ("spend", "clicks", 1.0, "cost per click"),
    "cpm":  ("spend", "impressions", 1000.0, "cost per thousand impressions"),
    "cvr":  ("conversions", "clicks", 100.0, "percent of clicks converting"),
    "cpa":  ("spend", "conversions", 1.0, "cost per conversion"),
    "roas": ("conversion_value", "spend", 1.0, "revenue per unit of spend"),
}

#: Paid touches live in the SAME event layer as email touches, IMPORTED
#: from the core's one vocabulary rather than retyped here. If these two
#: kinds are ever missing from EVENT_TYPES, record_event silently drops
#: them, so the import failing loudly at boot is the correct behaviour.
AD_EVENTS = tuple(k for k in CORE.EVENT_TYPES if k.startswith("AD_"))
assert AD_EVENTS == ("AD_CLICK", "AD_CONVERSION"), \
    "the core event vocabulary no longer carries the paid kinds"

#: What counts as a touch, and what counts as an outcome. Two lists, used
#: by every model, so no model can quietly redefine a conversion.
TOUCH_KINDS = ("EMAIL_CLICKED", "EMAIL_OPENED", "AD_CLICK")
CONVERSION_KINDS = ("EMAIL_CONVERTED", "AD_CONVERSION")

ATTRIBUTION_MODELS = ("last_touch", "first_touch", "linear",
                      "position_based", "time_decay")

#: Position-based gives the first and last touch most of the credit. These
#: three numbers are a CONVENTION, not a measurement, and the output says so.
POSITION_SPLIT = (0.40, 0.20, 0.40)

#: A touch loses half its credit every this many days.
TIME_DECAY_HALFLIFE = 7.0

#: Anomaly detection.
BASELINE_DAYS = 14
MIN_BASELINE_DAYS = 7
ANOMALY_KINDS = {
    "DELIVERY_STOPPED": "an active campaign spent nothing",
    "SPEND_SPIKE": "spend jumped well past its own baseline",
    "SPEND_NO_RESULT": "money went out and nothing came back",
    "CPA_BREAK": "cost per conversion broke its baseline",
    "CVR_COLLAPSE": "the same clicks stopped converting",
    "CTR_COLLAPSE": "the same impressions stopped being clicked",
}
#: How far past baseline before it is worth a founder's attention.
WATCH_AT = 1.5
ACT_AT = 2.0


# ---------------------------------------------------------------------------
# ROLLUPS
# ---------------------------------------------------------------------------
def _bucket(row, grain) -> str:
    day = str(row.get("day") or "")[:10]
    hour = str(row.get("hour") or "").zfill(2)[:2] if row.get("hour") else ""
    if grain == "RAW":
        return f"{day} {hour}".strip() + "|" + str(row.get("ad_id")
                                                   or row.get("ad_group_id")
                                                   or row.get("campaign_id"))
    if grain == "HOURLY":
        return f"{day} {hour or '00'}:00"
    if grain == "DAILY":
        return day
    if not day:
        return ""
    try:
        d = _dt.date(int(day[:4]), int(day[5:7]), int(day[8:10]))
    except Exception:
        return day
    if grain == "WEEKLY":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    return day[:7]


def derive(totals) -> dict:
    """Every derived metric, each with the denominator it stands on.

    A metric over nothing is None and a sentence, never 0."""
    t = _D(totals)
    out = {}
    for name, (num, den, mult, how) in DERIVED.items():
        n, d = float(t.get(num) or 0), float(t.get(den) or 0)
        if d <= 0:
            out[name] = {"value": None, "of": f"no {den} yet", "how": how}
        else:
            out[name] = {"value": round(n / d * mult, 2),
                         "of": f"{n:,.0f} / {d:,.0f}", "how": how}
    return out


def rollup(r, *, grain="DAILY", level="campaign", provider="",
           campaign_id="", days=90) -> dict:
    """The same numbers at whichever grain the question needs."""
    if grain not in GRAINS:
        return {"ok": False, "rows": [],
                "message": f"{grain!r} is not a grain. They are: "
                           + ", ".join(GRAINS)}
    if level not in M.LEVELS:
        return {"ok": False, "rows": [],
                "message": f"{level!r} is not a level. They are: "
                           + ", ".join(M.LEVELS)}
    key_field = {"campaign": "campaign_id", "ad_group": "ad_group_id",
                 "ad": "ad_id"}[level]
    cutoff = _ago(days)
    buckets, seen_days = {}, set()
    for m in r.all("ad_metrics"):
        if provider and m.get("provider") != provider:
            continue
        if campaign_id and m.get("campaign_id") != campaign_id:
            continue
        day = str(m.get("day") or "")[:10]
        if cutoff and day and day < cutoff:
            continue
        if not m.get(key_field):
            continue
        b = _bucket(m, grain)
        k = (b, m.get(key_field))
        row = buckets.setdefault(k, {"bucket": b, "key": m.get(key_field),
                                     "level": level,
                                     "provider": m.get("provider"),
                                     **{x: 0.0 for x in BASE_METRICS}})
        for x in BASE_METRICS:
            try:
                row[x] += float(m.get(x) or 0)
            except Exception:
                pass
        if day:
            seen_days.add(day)
    names = _names(r, level)
    rows = []
    for row in buckets.values():
        row["name"] = names.get(row["key"], row["key"])
        row.update(derive(row))
        rows.append(row)
    rows.sort(key=lambda x: (str(x["bucket"]), -float(x["spend"] or 0)))
    tot = {x: sum(float(row[x] or 0) for row in rows) for x in BASE_METRICS}
    return {"ok": True, "grain": grain, "level": level, "rows": rows,
            "totals": {**tot, **derive(tot)},
            "days_with_data": len(seen_days),
            "message": (f"{len(rows)} {grain.lower()} row(s) over "
                        f"{len(seen_days)} day(s) with data"
                        if rows else
                        "nothing has been measured in this window yet. That "
                        "is an absence, not a zero.")}


def _names(r, level) -> dict:
    coll = {"campaign": "media_campaigns", "ad_group": "ad_groups",
            "ad": "ads"}[level]
    return {x.get("id"): x.get("name") for x in r.all(coll)}


def _ago(days) -> str:
    try:
        d = _dt.date.today() - _dt.timedelta(days=int(days or 0))
        return d.isoformat()
    except Exception:
        return ""


def compare(r, *, campaign_id="", provider="", window=7) -> dict:
    """This window against the one before it. Both denominators shown."""
    cur = rollup(r, grain="DAILY", campaign_id=campaign_id,
                 provider=provider, days=window)
    prev_all = rollup(r, grain="DAILY", campaign_id=campaign_id,
                      provider=provider, days=window * 2)
    cut = _ago(window)
    prev = {x: sum(float(row[x] or 0) for row in prev_all["rows"]
                   if str(row["bucket"]) < cut) for x in BASE_METRICS}
    out = {"window_days": window, "now": cur["totals"],
           "before": {**prev, **derive(prev)}, "moves": []}
    for name in DERIVED:
        a = _D(_D(out["before"]).get(name)).get("value")
        b = _D(_D(out["now"]).get(name)).get("value")
        if a in (None, 0) or b is None:
            out["moves"].append({"metric": name, "change": None,
                                 "why": (f"no {name} before this window, so "
                                         f"there is nothing to compare "
                                         f"against")})
        else:
            out["moves"].append({"metric": name, "before": a, "now": b,
                                 "change": round((b - a) / a * 100, 1),
                                 "why": f"{a} then, {b} now"})
    return out


# ---------------------------------------------------------------------------
# ATTRIBUTION, ACROSS ONE TIMELINE
# ---------------------------------------------------------------------------
def record_paid(r, kind, *, profile_id="", campaign_id="", at=None,
                value=0.0, metadata=None) -> dict:
    """One paid touch, into the ONE event layer, via the one recorder.

    Delegates to CORE.record_event so a paid click gets the same
    idempotency key and the same dedup as an email click. A second
    recorder here would eventually disagree with the first about what
    'the same event twice' means."""
    if kind not in AD_EVENTS:
        return {"ok": False,
                "message": f"{kind!r} is not a paid event. They are: "
                           + ", ".join(AD_EVENTS)}
    md = dict(_D(metadata))
    if value:
        md["value"] = float(value)
    got = CORE.record_event(r, kind, profile_id=profile_id,
                            campaign_id=campaign_id, at=at, metadata=md)
    return {"ok": bool(got), "id": _D(got).get("id"),
            "message": ("recorded" if got else
                        "already on record; a webhook delivered twice must "
                        "not double a conversion")}


def _touches(r, days=90) -> dict:
    """Every person's ordered history of touches and conversions.

    Reads email_events, the ONE event layer, with the field names it
    actually uses: event_type and timestamp. Reading a `kind` or an `at`
    off these rows returns None on every row and attribution silently
    reports zero converters, which is exactly the class of quiet lie this
    engine exists to not tell."""
    cutoff = _ago(days)
    people = {}
    for e in r.all("email_events"):
        kind = e.get("event_type")
        if kind not in TOUCH_KINDS and kind not in CONVERSION_KINDS:
            continue
        at = str(e.get("timestamp") or "")
        if cutoff and at[:10] < cutoff:
            continue
        pid = e.get("profile_id") or _D(e.get("metadata")).get("email") or ""
        if not pid:
            continue
        people.setdefault(pid, []).append(
            {"kind": kind, "at": at, "campaign_id": e.get("campaign_id") or "",
             "value": float(_D(e.get("metadata")).get("value") or 0)})
    for pid in people:
        people[pid].sort(key=lambda x: x["at"])
    return people


def _weights(touches, model) -> list:
    n = len(touches)
    if n == 0:
        return []
    if model == "last_touch":
        return [0.0] * (n - 1) + [1.0]
    if model == "first_touch":
        return [1.0] + [0.0] * (n - 1)
    if model == "linear":
        return [1.0 / n] * n
    if model == "position_based":
        first, mid, last = POSITION_SPLIT
        if n == 1:
            return [1.0]
        if n == 2:
            return [first + mid / 2, last + mid / 2]
        each = mid / (n - 2)
        return [first] + [each] * (n - 2) + [last]
    # time_decay: the touch nearest the conversion keeps most of the credit
    last_at = touches[-1]["at"]
    raw = []
    for t in touches:
        raw.append(0.5 ** (_days_between(t["at"], last_at) / TIME_DECAY_HALFLIFE))
    s = sum(raw) or 1.0
    return [x / s for x in raw]


def _days_between(a, b) -> float:
    try:
        da = _dt.date(int(a[:4]), int(a[5:7]), int(a[8:10]))
        db = _dt.date(int(b[:4]), int(b[5:7]), int(b[8:10]))
        return abs((db - da).days)
    except Exception:
        return 0.0


def attribute(r, *, model="last_touch", days=90) -> dict:
    """Credit per campaign under one model, across email and paid together."""
    if model not in ATTRIBUTION_MODELS:
        return {"ok": False, "rows": [],
                "message": f"{model!r} is not a model. They are: "
                           + ", ".join(ATTRIBUTION_MODELS)}
    people = _touches(r, days)
    credit, converters, no_touch = {}, 0, 0
    for pid, hist in people.items():
        conv = [x for x in hist if x["kind"] in CONVERSION_KINDS]
        if not conv:
            continue
        converters += 1
        for c in conv:
            path = [x for x in hist
                    if x["kind"] in TOUCH_KINDS and x["at"] <= c["at"]
                    and x["campaign_id"]]
            if not path:
                no_touch += 1
                continue
            value = c["value"]
            for t, w in zip(path, _weights(path, model)):
                row = credit.setdefault(t["campaign_id"],
                                        {"campaign_id": t["campaign_id"],
                                         "conversions": 0.0, "value": 0.0,
                                         "touches": 0})
                row["conversions"] += w
                row["value"] += value * w
                row["touches"] += 1
    rows = []
    paid = {x.get("id"): x for x in r.all("media_campaigns")}
    email = {x.get("id"): x for x in r.all("campaigns")}
    for cid, row in credit.items():
        src = paid.get(cid) or email.get(cid) or {}
        rows.append({**row, "channel": "paid" if cid in paid else
                     ("email" if cid in email else "unknown"),
                     "name": src.get("name") or cid,
                     "provider": src.get("provider") or "",
                     "conversions": round(row["conversions"], 2),
                     "value": round(row["value"], 2)})
    rows.sort(key=lambda x: -x["conversions"])
    return {"ok": True, "model": model, "rows": rows,
            "converters": converters, "conversions_with_no_touch": no_touch,
            "convention": (
                f"position_based splits {POSITION_SPLIT[0]:.0%} first, "
                f"{POSITION_SPLIT[1]:.0%} middle, {POSITION_SPLIT[2]:.0%} "
                f"last, and time_decay halves credit every "
                f"{TIME_DECAY_HALFLIFE:.0f} days. Those are CONVENTIONS this "
                f"engine chose, not facts it measured."),
            "message": (
                f"{converters} converter(s) among {len(people)} person/people "
                f"on the shared timeline, credited by {model}."
                + (f" {no_touch} conversion(s) had no attributable touch at "
                   f"all and are counted nowhere, which is the honest place "
                   f"for them." if no_touch else ""))}


def model_spread(r, days=90) -> dict:
    """All five models side by side, because they disagree and that is
    the most useful thing about them."""
    runs = {m: attribute(r, model=m, days=days) for m in ATTRIBUTION_MODELS}
    ids = sorted({row["campaign_id"] for m in runs for row in runs[m]["rows"]})
    rows = []
    for cid in ids:
        vals = {}
        for m, res in runs.items():
            hit = next((x for x in res["rows"] if x["campaign_id"] == cid), None)
            vals[m] = hit["conversions"] if hit else 0.0
        lo, hi = min(vals.values()), max(vals.values())
        name = next((x["name"] for m in runs for x in runs[m]["rows"]
                     if x["campaign_id"] == cid), cid)
        rows.append({"campaign_id": cid, "name": name, **vals,
                     "spread": round(hi - lo, 2),
                     "why": (f"the models disagree by {hi - lo:.2f} "
                             f"conversion(s) on this campaign, so any single "
                             f"number you quote for it is a choice"
                             if hi - lo > 0.01 else
                             "every model agrees here, which usually means "
                             "there was only one touch to credit")})
    rows.sort(key=lambda x: -x["spread"])
    return {"ok": True, "rows": rows,
            "message": (f"{len(rows)} campaign(s) scored under all "
                        f"{len(ATTRIBUTION_MODELS)} models"
                        if rows else
                        "no conversion in the event layer has an attributable "
                        "touch yet, so there is nothing to model")}


def reconcile(r, days=30) -> dict:
    """What the platform claims against what this engine observed.

    Names both numbers and the gap. Does NOT declare a winner: the platform
    counts view-through conversions this engine cannot see, and this engine
    counts conversions that never reach the platform's pixel."""
    claimed = {}
    for row in rollup(r, grain="DAILY", days=days)["rows"]:
        c = claimed.setdefault(row["key"], {"conversions": 0.0, "spend": 0.0})
        c["conversions"] += float(row["conversions"] or 0)
        c["spend"] += float(row["spend"] or 0)
    observed = {x["campaign_id"]: x["conversions"]
                for x in attribute(r, model="last_touch", days=days)["rows"]}
    names = _names(r, "campaign")
    rows = []
    for cid, c in claimed.items():
        obs = float(observed.get(cid) or 0)
        cl = c["conversions"]
        gap = obs - cl
        rows.append({
            "campaign_id": cid, "name": names.get(cid, cid),
            "platform_claims": round(cl, 2), "engine_observed": round(obs, 2),
            "gap": round(gap, 2), "spend": round(c["spend"], 2),
            "agreement": rate(min(cl, obs), max(cl, obs))[0],
            "why": ("the two agree" if abs(gap) < 0.51 else
                    (f"the platform claims {cl:,.0f} and this engine can see "
                     f"{obs:,.0f}. The platform counts view-through, which "
                     f"this engine cannot observe, so neither number is "
                     f"wrong and neither is the whole truth."
                     if gap < 0 else
                     f"this engine sees {obs:,.0f} against the platform's "
                     f"{cl:,.0f}. Conversions that never reached the pixel "
                     f"look like this."))})
    rows.sort(key=lambda x: -abs(x["gap"]))
    return {"ok": True, "rows": rows,
            "message": (f"{len(rows)} campaign(s) reconciled over {days} "
                        f"day(s). Where the numbers differ, both are shown "
                        f"and neither is corrected into the other."
                        if rows else
                        "nothing to reconcile: no campaign has both platform "
                        "metrics and an attributable conversion yet")}


# ---------------------------------------------------------------------------
# ANOMALIES
# ---------------------------------------------------------------------------
def scan(r, *, window=3, save=True) -> dict:
    """Judge each campaign's recent days against its OWN baseline.

    Refuses on a baseline it has not earned, and says so rather than
    printing a red badge computed from three days of data."""
    found, blind = [], []
    campaigns = {c["id"]: c for c in r.all("media_campaigns")}
    by_camp = {}
    for m in r.all("ad_metrics"):
        cid = m.get("campaign_id")
        if not cid:
            continue
        by_camp.setdefault(cid, []).append(m)
    for cid, rows in by_camp.items():
        c = campaigns.get(cid) or {}
        rows.sort(key=lambda x: str(x.get("day") or ""))
        days = sorted({str(x.get("day") or "")[:10] for x in rows if x.get("day")})
        recent_days = set(days[-window:])
        base_days = [d for d in days[:-window]][-BASELINE_DAYS:]
        if len(base_days) < MIN_BASELINE_DAYS:
            blind.append({
                "campaign_id": cid, "name": c.get("name") or cid,
                "why": (f"{len(base_days)} day(s) of baseline against a "
                        f"minimum of {MIN_BASELINE_DAYS}. Judging this now "
                        f"would be a coin toss with a red badge on it.")})
            continue
        base = _sum(rows, set(base_days))
        cur = _sum(rows, recent_days)
        nb, nc = len(base_days), len(recent_days) or 1
        for kind, hit in _tests(base, cur, nb, nc, c):
            sev = "act" if hit["ratio"] and hit["ratio"] >= ACT_AT else "watch"
            # "type", not "kind": that is the column the anomalies table
            # declares and indexes, and a second word for the same thing is
            # the vocabulary bug this engine has already paid for five times.
            rec = {"id": rid("manom", r.ws, cid, kind, days[-1]),
                   "campaign_id": cid, "name": c.get("name") or cid,
                   "provider": c.get("provider"), "type": kind,
                   "severity": sev, "status": "open", "detected_at": now(),
                   "metric": f"{hit.get('current')} vs baseline "
                             f"{hit.get('baseline')}",
                   "day": days[-1], "baseline_days": nb,
                   "window_days": nc, **hit,
                   "means": ANOMALY_KINDS[kind]}
            found.append(rec)
            if save:
                r.put("media_anomalies", rec)
    found.sort(key=lambda x: (x["severity"] != "act", -(x.get("ratio") or 0)))
    return {"ok": True, "anomalies": found, "not_judged": blind,
            "message": (f"{len(found)} anomaly/anomalies across "
                        f"{len(by_camp) - len(blind)} campaign(s) with a "
                        f"baseline of at least {MIN_BASELINE_DAYS} days."
                        + (f" {len(blind)} campaign(s) were NOT judged for "
                           f"lack of history, which is listed rather than "
                           f"hidden." if blind else ""))}


def _sum(rows, days) -> dict:
    out = {x: 0.0 for x in BASE_METRICS}
    for m in rows:
        if str(m.get("day") or "")[:10] in days:
            for x in BASE_METRICS:
                try:
                    out[x] += float(m.get(x) or 0)
                except Exception:
                    pass
    return out


def _tests(base, cur, nb, nc, campaign):
    """Each test returns the numbers it fired on, never a bare verdict."""
    out = []
    bd = lambda k: base[k] / nb          # noqa: E731  baseline per day
    cd = lambda k: cur[k] / nc           # noqa: E731  current per day
    state = str(campaign.get("state") or "")

    if state == "ACTIVE" and bd("spend") > 0 and cd("spend") == 0:
        out.append(("DELIVERY_STOPPED",
                    {"ratio": ACT_AT, "baseline": round(bd("spend"), 2),
                     "current": 0.0,
                     "evidence": (f"this campaign is ACTIVE and averaged "
                                  f"{bd('spend'):,.2f} a day over {nb} days, "
                                  f"then spent nothing for {nc} day(s)")}))
    if bd("spend") > 0 and cd("spend") / bd("spend") >= WATCH_AT:
        rt = cd("spend") / bd("spend")
        out.append(("SPEND_SPIKE",
                    {"ratio": round(rt, 2), "baseline": round(bd("spend"), 2),
                     "current": round(cd("spend"), 2),
                     "evidence": (f"{cd('spend'):,.2f} a day against a "
                                  f"{nb}-day baseline of {bd('spend'):,.2f}, "
                                  f"which is {rt:.1f}x")}))
    if cur["spend"] > 0 and cur["conversions"] == 0 and base["conversions"] > 0:
        out.append(("SPEND_NO_RESULT",
                    {"ratio": ACT_AT, "baseline": round(base["conversions"], 2),
                     "current": 0.0,
                     "evidence": (f"{cur['spend']:,.2f} spent over {nc} day(s) "
                                  f"with no conversion, against {base['conversions']:,.0f} "
                                  f"in the {nb} days before")}))
    bcpa = (base["spend"] / base["conversions"]) if base["conversions"] else None
    ccpa = (cur["spend"] / cur["conversions"]) if cur["conversions"] else None
    if bcpa and ccpa and ccpa / bcpa >= WATCH_AT:
        rt = ccpa / bcpa
        out.append(("CPA_BREAK",
                    {"ratio": round(rt, 2), "baseline": round(bcpa, 2),
                     "current": round(ccpa, 2),
                     "evidence": (f"CPA {ccpa:,.2f} against a baseline of "
                                  f"{bcpa:,.2f} over {nb} days, which is "
                                  f"{rt:.1f}x")}))
    for kind, num, den in (("CVR_COLLAPSE", "conversions", "clicks"),
                           ("CTR_COLLAPSE", "clicks", "impressions")):
        if base[den] <= 0 or cur[den] <= 0 or base[num] <= 0:
            continue
        b = base[num] / base[den]
        c = cur[num] / cur[den]
        if c > 0 and b / c >= WATCH_AT:
            rt = b / c
            out.append((kind,
                        {"ratio": round(rt, 2), "baseline": round(b * 100, 2),
                         "current": round(c * 100, 2),
                         "evidence": (f"{c * 100:.2f}% against a baseline of "
                                      f"{b * 100:.2f}% on {cur[den]:,.0f} "
                                      f"{den}, which is {rt:.1f}x worse")}))
    return out


# ---------------------------------------------------------------------------
# THE VERDICTS. Same queue, same tier, same evidence contract.
# ---------------------------------------------------------------------------
#: anomaly kind -> the order code that answers it. One table, so a new
#: anomaly cannot silently produce no verdict at all.
ANSWER = {
    "DELIVERY_STOPPED": "resume_campaign",
    "SPEND_SPIKE": "budget_shift",
    "SPEND_NO_RESULT": "pause_campaign",
    "CPA_BREAK": "pause_campaign",
    "CVR_COLLAPSE": "landing_fix",
    "CTR_COLLAPSE": "creative_rotate",
}


def propose(r, store=None, *, window=3, queue=True) -> dict:
    """Turn measured anomalies into verdicts a human approves.

    Every verdict carries metric, threshold, window and source, because
    the order engine refuses an opinion and it is right to."""
    import content_engine_media_orders as MO
    found = scan(r, window=window, save=False)
    orders, skipped = [], []
    for a in found["anomalies"]:
        code = ANSWER.get(a["type"])
        if not code:
            skipped.append(a["type"])
            continue
        orders.append(MO.make_order(
            code, a["campaign_id"], platform=a.get("provider") or "",
            evidence={"metric": f"{a['type']} at {a['current']}",
                      "threshold": f"baseline {a['baseline']} "
                                   f"({a['ratio']}x)",
                      "window": f"{a['window_days']}d against "
                                f"{a['baseline_days']}d",
                      "source": "ad_metrics rollup"},
            say=f"{a['name']}: {a['evidence']}"))
    # Allocation is its own verdict, and it only fires when the allocator
    # actually has history to allocate on.
    alloc = MP.allocate(r, _live_budget(r))
    if alloc.get("ok") and alloc.get("basis") == "marginal return" \
            and len(alloc["rows"]) > 1:
        top = alloc["rows"][0]
        orders.append(MO.make_order(
            "budget_allocate", "portfolio", platform=top["provider"],
            evidence={"metric": f"marginal ROAS {top['marginal_roas']}",
                      "threshold": f"average {top['average_roas']}",
                      "window": "90d",
                      "source": "marginal allocation over ad_metrics"},
            say=(f"move budget toward {top['provider']} "
                 f"({top['amount']:,.0f}); {alloc['message']}")))
    added = 0
    if queue and store is not None and orders:
        added = MO.upsert(store, orders)
    tier = MO.auto_level(store) if store is not None else "unknown"
    return {"ok": True, "proposed": len(orders), "queued": added,
            "tier": tier, "not_judged": found["not_judged"],
            "no_answer_for": sorted(set(skipped)),
            "orders": [{"code": o["code"], "say": o["say"],
                        "evidence": o["evidence"]} for o in orders],
            "message": (f"{len(orders)} verdict(s), {added} newly queued. "
                        f"The approval tier is {tier!r}, so "
                        + ("they go out on the next pass"
                           if tier == "execute" else
                           "they wait for you on the Media board") + "."
                        + (f" {len(found['not_judged'])} campaign(s) were not "
                           f"judged for lack of baseline."
                           if found["not_judged"] else "")
                        if orders else
                        "nothing to propose: no campaign broke its own "
                        "baseline in this window."
                        + (f" {len(found['not_judged'])} campaign(s) do not "
                           f"have enough history to judge yet."
                           if found["not_judged"] else ""))}


def _live_budget(r) -> float:
    return sum(float(c.get("budget_amount") or 0) for c in
               r.all("media_campaigns")
               if c.get("state") in ("ACTIVE", "SCHEDULED", "LAUNCHING")) or 0.0


def summary(r, days=30) -> dict:
    """The one screen a founder reads first. Decision before detail."""
    roll = rollup(r, grain="DAILY", days=days)
    anom = scan(r, save=False)
    spread = model_spread(r, days=days)
    tot = roll["totals"]
    return {
        "spend": tot.get("spend"), "conversions": tot.get("conversions"),
        "cpa": tot.get("cpa"), "roas": tot.get("roas"),
        "days_with_data": roll["days_with_data"],
        "needs_action": [a for a in anom["anomalies"] if a["severity"] == "act"],
        "watching": [a for a in anom["anomalies"] if a["severity"] == "watch"],
        "not_judged": anom["not_judged"],
        "most_disputed": spread["rows"][:3],
        "message": (roll["message"] + " " + anom["message"]),
    }
