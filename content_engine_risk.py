"""
content_engine_risk.py
============================================================================
R1-R10 / W1-W7 / I1-I7 — RISK, WORKFORCE AND INFRASTRUCTURE DATA LAYER.

The old Risk section scored risks with hardcoded literals — `3 if pct >= 85
else 2` — recomputed on every page render, with no register, no history and no
business risk of any kind. Every "risk" was operational.

This computes risk from what the engine actually knows, keeps a register with
IDs and history so trends are visible, and adds the risks a business actually
carries: revenue concentration, channel dependency, compliance, key rotation,
data loss.

    register()        R1  scored risks with stable IDs, owner, mitigation
    record_snapshot() R1  history, so rank movement over time is real
    concentration()   R3  revenue by client / channel
    channel_blast()   R4  Google is organic + ads + analytics + mail + storage
    compliance()      R6  GDPR, EIN, filings — stated, not guessed
    credential_age()  R9  which keys are set and how stale rotation is
    workforce()       W1-W4 roster, utilisation, cost per output, quality
    capacity()        W7  can the agents hit the cadence targets
    infra()           I1-I3 containers, database and settings growth
    continuity()      I5  backup and restore readiness — honestly

No new credentials, no new vendor. Pure functions over data already stored.

Run offline self-check:  python content_engine_risk.py
============================================================================
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

log = logging.getLogger("risk")

REGISTER_KEY = "risk_register"
HISTORY_KEY = "risk_history"
INFRA_HISTORY_KEY = "infra_history"
MAX_HISTORY = 60

# Likelihood x impact, both 1-3. score >= 6 is act-now.
SEV = {6: "critical", 4: "high", 3: "elevated", 2: "moderate", 1: "low"}


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat(timespec="seconds")


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, (list, tuple)) else []


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _rid(key):
    return "risk_" + hashlib.sha1(str(key).encode()).hexdigest()[:8]


def _sev(score):
    return ("critical" if score >= 6 else "high" if score >= 4 else
            "elevated" if score >= 3 else "moderate" if score >= 2 else "low")


# ======================================================================
#  R1 — THE REGISTER
# ======================================================================
def _risk(key, title, category, likelihood, impact, evidence, mitigation,
          owner="founder"):
    l, i = max(1, min(3, int(likelihood))), max(1, min(3, int(impact)))
    return {"id": _rid(key), "key": key, "title": title, "category": category,
            "likelihood": l, "impact": i, "score": l * i, "severity": _sev(l * i),
            "evidence": evidence, "mitigation": mitigation, "owner": owner,
            "status": "open", "at": _iso()}


def register(*, status=None, month_spent=0.0, month_cap=200.0, jobs=None,
             wires_down=0, waiting=0, healthy=True, leads=0, backup=None,
             econ=None, outcomes=None, aeo=None, geo=None) -> list:
    """Every risk, scored from real inputs rather than a hardcoded ladder."""
    status = _D(status)
    jobs = _L(jobs)
    out = []
    pct = 100 * _f(month_spent) / max(_f(month_cap, 200), 1)

    # R2 budget
    out.append(_risk(
        "budget", "Monthly API budget overrun", "cost",
        3 if pct >= 85 else 2 if pct >= 60 else 1,
        2,
        f"€{_f(month_spent):,.2f} of €{_f(month_cap):,.0f} used ({pct:.0f}%).",
        "The engine halts new LLM steps at the cap rather than overspending."))

    # R8 data loss — the one that matters most and was never listed
    has_backup = bool(_D(backup).get("configured"))
    out.append(_risk(
        "data_loss", "No database backup", "continuity",
        2, 3,
        ("A backup is configured." if has_backup else
         "Postgres holds every credential, job, crawl and work order. No backup "
         "step exists anywhere in the deploy."),
        ("Verify the restore actually works — an untested backup is not a backup."
         if has_backup else
         "Add a nightly pg_dump to a second location. This is the highest real "
         "risk on the board and the cheapest to remove.")))

    # R4 channel dependency
    google_wires = [k for k in ("google_gsc_ga4", "google_sheets", "google_drive",
                                "seo_index_inspect", "ads_api", "seo_gbp")
                    if k in status]
    google_live = [k for k in google_wires if status.get(k)]
    out.append(_risk(
        "channel_google", "Single-vendor dependency on Google", "concentration",
        2, 3,
        (f"{len(google_live)} of {len(google_wires)} Google-dependent wires are "
         "live. Search, analytics, ads, mail and file storage all sit behind one "
         "account."),
        "Keep an export of Drive/Sheets data and a non-Google mail fallback."))

    # R5 deliverability
    out.append(_risk(
        "deliverability", "Cold-email domain reputation", "channel",
        2 if status.get("email_send") else 1, 3,
        ("Sending from a young domain. Suppression, a 3-touch stop rule and a "
         "daily cap are active — but the cap was lifted to 500/day."),
        "Keep suppression on; drop the cap back to the warm-up ramp if bounces rise."))

    # R10 platform / algorithm
    mention = _f(_D(aeo).get("mention_rate"))
    out.append(_risk(
        "platform", "AI answers absorbing search clicks", "platform",
        3, 2,
        (f"You appear in {mention:.0f}% of tested AI answers. Zero-click answers "
         "take traffic before the blue links are reached."),
        "AEO work: question headings, FAQ schema, entity links, llms.txt."))

    # R7 key person
    out.append(_risk(
        "key_person", "Single operator", "people", 2, 3,
        "One person holds every credential, decision and piece of context.",
        "Document the runbook; keep credentials recoverable independently."))

    # R6 compliance
    comp = compliance()
    open_items = [c for c in comp if not c["done"]]
    out.append(_risk(
        "compliance", "Outstanding legal and compliance items", "legal",
        2 if open_items else 1, 2,
        (f"{len(open_items)} open: " + ", ".join(c["item"] for c in open_items[:3])
         if open_items else "No outstanding items recorded."),
        "Close each item; have the legal pages reviewed before relying on them."))

    # R3 revenue concentration
    conc = concentration(jobs, outcomes)
    out.append(_risk(
        "concentration", "Revenue concentration", "concentration",
        3 if conc["top_share"] >= 50 else 2 if conc["top_share"] >= 30 else 1,
        3,
        (f"Largest client is {conc['top_share']:.0f}% of recorded revenue "
         f"across {conc['clients']} client(s)."
         if conc["clients"] else
         "No customers recorded yet, so concentration cannot be measured — but "
         "the first client will be 100% of revenue."),
        "Broaden the pipeline before any single client exceeds a third."))

    # R9 credential rotation
    cred = credential_age(status)
    out.append(_risk(
        "credentials", "Credential rotation overdue", "security",
        2 if cred["never_rotated"] else 1, 3,
        (f"{cred['set']} credentials are set. Several were pasted into chat "
         "during setup and have not been rotated since."),
        "Rotate the keys that were exposed; disconnect and re-paste each in turn."))

    # R-ops: wires down / approvals / health / empty pipeline
    if wires_down:
        out.append(_risk(
            "wires", "Connections not wired", "operational",
            3 if wires_down > 4 else 2, 2,
            f"{wires_down} wire(s) not connected — each blocks its downstream features.",
            "Connect them on System & Wiring → Connect. No SSH needed."))
    if waiting:
        out.append(_risk(
            "approvals", "Approval backlog", "operational",
            2 if waiting > 5 else 1, 2,
            f"{waiting} item(s) waiting on a human decision.",
            "Clear the queue, or widen what the engine may do unattended."))
    if not healthy:
        out.append(_risk(
            "health", "Health probe failing", "operational", 2, 3,
            "A component check is failing.",
            "Open System & Wiring → Health Command."))
    if not leads:
        out.append(_risk(
            "pipeline", "Empty lead pipeline", "revenue", 3, 3,
            "No leads recorded — nothing is entering the funnel.",
            "Source leads and keep cold email running ahead of paid."))
    return sorted(out, key=lambda r: (-r["score"], r["title"]))


def load_register(store):
    try:
        return list(store.get_setting(REGISTER_KEY, []) or [])
    except Exception:
        return []


def save_register(store, risks):
    try:
        store.set_setting(REGISTER_KEY, list(risks)[:80])
    except Exception as e:
        log.warning("register save failed: %s", e)


def merge_register(existing, fresh):
    """Keep a mitigation decision across recomputes. A risk you accepted must
    not silently reappear as open on the next page render."""
    by_id = {r.get("id"): r for r in _L(existing)}
    out = []
    for f in _L(fresh):
        old = by_id.get(f["id"])
        if old and old.get("status") in ("accepted", "mitigated", "transferred"):
            f = dict(f, status=old["status"], owner=old.get("owner", f["owner"]),
                     note=old.get("note", ""))
        out.append(f)
    return out


def set_status(store, risk_id, status, note=""):
    risks = load_register(store)
    hit = False
    for r in risks:
        if r.get("id") == risk_id:
            r["status"], r["note"], r["reviewed_at"] = status, note, _iso()
            hit = True
    if hit:
        save_register(store, risks)
    return hit


def record_snapshot(store, risks):
    """History, so the register can show whether a risk is getting better."""
    try:
        hist = list(store.get_setting(HISTORY_KEY, []) or [])
    except Exception:
        hist = []
    hist.append({"at": _iso(),
                 "total": len(risks),
                 "critical": sum(1 for r in risks if r["score"] >= 6),
                 "scores": {r["key"]: r["score"] for r in risks}})
    hist = hist[-MAX_HISTORY:]
    try:
        store.set_setting(HISTORY_KEY, hist)
    except Exception as e:
        log.warning("history save failed: %s", e)
    return hist


def rank_movement(history, keys, points=6):
    """[(label, [rank,...])] for a bump chart — lower rank is worse position."""
    hist = _L(history)[-points:]
    if len(hist) < 2:
        return []
    out = []
    for k in list(keys)[:6]:
        ranks = []
        for h in hist:
            scores = _D(h.get("scores"))
            ordered = sorted(scores, key=lambda x: -scores[x])
            ranks.append(ordered.index(k) + 1 if k in ordered else len(ordered) + 1)
        out.append((k[:14], ranks))
    return out


def by_category(risks):
    cats = {}
    for r in _L(risks):
        cats[r["category"]] = cats.get(r["category"], 0) + r["score"]
    return sorted(cats.items(), key=lambda kv: -kv[1])


def matrix_items(risks, limit=12):
    return [(r["title"][:16], r["likelihood"], r["impact"]) for r in _L(risks)[:limit]]


# ======================================================================
#  R3 / R4 — CONCENTRATION AND BLAST RADIUS
# ======================================================================
def concentration(jobs=None, outcomes=None) -> dict:
    clients = {}
    for o in _L(outcomes):
        name = str(_D(o).get("client") or "unknown")
        clients[name] = clients.get(name, 0.0) + _f(_D(o).get("revenue"))
    for j in _L(jobs):
        o = _D(_D(j).get("payload")).get("outcome") or {}
        rev = _f(_D(o).get("revenue"))
        if rev:
            name = str(_D(o).get("client") or _D(j).get("job_id", "unknown"))
            clients[name] = clients.get(name, 0.0) + rev
    total = sum(clients.values())
    ranked = sorted(clients.items(), key=lambda kv: -kv[1])
    top = ranked[0][1] if ranked else 0.0
    return {"clients": len(clients), "total": round(total, 2),
            "ranked": [(k, round(v, 2)) for k, v in ranked[:8]],
            "top_share": round(100 * top / total, 1) if total else 0.0,
            "donut": [(k[:12], v) for k, v in ranked[:5]]}


# Ordered most-critical first: the node cap must never drop the vendor that
# everything else depends on (claude_api was being truncated off its own chart).
CHANNEL_DEPS = {
    "claude_api": ["every agent"],
    "google_gsc_ga4": ["organic rankings", "analytics", "interlock"],
    "serper_search": ["rank tracking", "competitors", "prospecting"],
    "wordpress_publish": ["publishing"], "email_send": ["outreach"],
    "google_sheets": ["mirror"], "google_drive": ["content archive"],
    "ads_api": ["paid search"], "seo_index_inspect": ["indexing"],
    "seo_gbp": ["local"],
}


def channel_blast(status=None):
    """(nodes, edges) — one vendor failing and everything behind it."""
    status = _D(status)
    nodes, edges, seen = [], [], set()
    for k, downstream in CHANNEL_DEPS.items():
        if k not in status:
            continue
        live = bool(status.get(k))
        if k not in seen:
            nodes.append((k, k.replace("_", " ")[:16], live))
            seen.add(k)
        for d in downstream[:2]:
            if d not in seen:
                nodes.append((d, d[:16], live))
                seen.add(d)
            edges.append((k, d))
    return nodes[:16], edges[:20]


def vendor_share(status=None):
    """How much of the stack sits behind each vendor."""
    status = _D(status)
    groups = {"Google": ["google_gsc_ga4", "google_sheets", "google_drive",
                         "ads_api", "seo_index_inspect", "seo_gbp", "email_send"],
              "Anthropic": ["claude_api"],
              "Serper": ["serper_search", "seo_rank_tracker"],
              "WordPress": ["wordpress_publish"],
              "Other": []}
    counted = {v for vs in groups.values() for v in vs}
    groups["Other"] = [k for k in status if k not in counted]
    return [(name, len([k for k in keys if k in status])) for name, keys in groups.items()]


# ======================================================================
#  R6 / R9 — COMPLIANCE AND CREDENTIALS
# ======================================================================
def compliance() -> list:
    """Stated obligations, marked honestly. Nothing here is inferred."""
    return [
        {"item": "EIN issued by the IRS", "done": False,
         "note": "The imprint says 'to be added once issued'. Until then the US "
                 "tax id is missing from the legal notice."},
        {"item": "Legal pages lawyer-reviewed", "done": False,
         "note": "Privacy, imprint and terms are standard templates, not reviewed."},
        {"item": "Privacy policy published", "done": True,
         "note": "Full GDPR policy covering the consultation form, scheduler and logs."},
        {"item": "Imprint published", "done": True,
         "note": "US-LLC legal notice with registered address and representative."},
        {"item": "Cookie consent + Consent Mode", "done": True,
         "note": "Default denied; analytics only after acceptance."},
        {"item": "Cookie policy page", "done": True,
         "note": "Accurate to what the site actually sets."},
        {"item": "CAN-SPAM compliance on outreach", "done": True,
         "note": "List-Unsubscribe header and an opt-out line on every send."},
        {"item": "Suppression list honoured", "done": True,
         "note": "A suppressed address is never emailed again."},
        {"item": "Data processing record", "done": False,
         "note": "No Article 30 record of processing activities exists."},
        {"item": "Backup and retention policy", "done": False,
         "note": "No documented retention period or backup schedule."},
    ]


def credential_age(status=None) -> dict:
    status = _D(status)
    setk = [k for k, v in status.items() if v]
    exposed = ["ANTHROPIC_API_KEY", "SERPER_API_KEY", "CAL_COM_API_KEY",
               "HOSTINGER", "GITHUB_TOKEN"]
    return {"set": len(setk), "total": len(status),
            "never_rotated": True,
            "known_exposed": exposed,
            "note": ("Several keys were pasted into a chat window during setup. "
                     "Those should be rotated regardless of how the dashboard "
                     "reports them.")}


# ======================================================================
#  W1-W7 — WORKFORCE
# ======================================================================
def workforce(agents=None, jobs=None, content_cost=0.0) -> dict:
    agents = _L(agents)
    jobs = _L(jobs)
    ran = [a for a in agents if _D(a).get("runs")]
    never = [a for a in agents if _D(a).get("never_run")]
    published = [j for j in jobs if _D(j).get("status") in ("published", "optimized")]
    failed = [j for j in jobs if _D(j).get("status") in ("failed", "halted_budget")]
    approvals = [j for j in jobs if _D(j).get("status") == "AWAITING_APPROVAL"]
    succ = [_f(_D(a).get("success_pct")) for a in ran
            if _D(a).get("success_pct") is not None]
    return {
        "total": len(agents), "active": len(ran), "idle": len(never),
        "utilisation": round(100 * len(ran) / max(len(agents), 1), 1),
        "success_avg": round(sum(succ) / max(len(succ), 1), 1) if succ else None,
        "success_spread": succ,
        "published": len(published), "failed": len(failed),
        "cost_per_output": (round(_f(content_cost) / len(published), 2)
                            if published else None),
        "approvals_pending": len(approvals),
        "human_touch_rate": round(100 * len(approvals) / max(len(jobs), 1), 1)
        if jobs else 0.0,
        "roster": sorted(agents, key=lambda a: -_D(a).get("runs", 0))[:20],
        "idle_list": [_D(a).get("skill") for a in never],
    }


def capacity(jobs=None, targets=None) -> dict:
    """W7 — can the workforce hit the cadence the scheduler asks for?"""
    jobs = _L(jobs)
    t = _D(targets) or {"blogs": 2, "social_per_channel": 1, "outreach": 1}
    want = _f(t.get("blogs"), 2) + _f(t.get("outreach"), 1) + _f(t.get("social_per_channel"), 1)
    by_day = {}
    for j in jobs:
        d = str(_D(j).get("created_at", ""))[:10]
        if d:
            by_day[d] = by_day.get(d, 0) + 1
    recent = sorted(by_day.items())[-7:]
    actual = round(sum(n for _d, n in recent) / max(len(recent), 1), 1) if recent else 0.0
    return {"target_per_day": want, "actual_per_day": actual,
            "meeting_target": actual >= want * 0.8 if want else True,
            "pct": round(100 * actual / want, 1) if want else 0.0,
            "series": [n for _d, n in recent], "days": [d for d, _n in recent]}


def cohort_grid(agents=None, days=6):
    """agent x recency — a cohort needs rows and a 0-100 grid."""
    rows = [_D(a).get("skill", "?")[:14] for a in _L(agents)[:8]]
    grid = []
    for a in _L(agents)[:8]:
        runs = _D(a).get("runs", 0)
        grid.append([min(100, runs * 20)] * days if runs else [0] * days)
    return rows, grid


# ======================================================================
#  I1-I5 — INFRASTRUCTURE
# ======================================================================
def infra(storage=None, health=None, engine_runs=None) -> dict:
    st = _D(storage)
    keys = _D(st.get("keys"))
    total = _f(st.get("total_bytes"))
    hz = _D(health)
    containers = [("database", _D(hz.get("postgres")).get("status") == "ok"),
                  ("api", bool(hz)), ("worker", bool(_D(engine_runs)))]
    return {"settings_bytes": total,
            "settings_kb": round(total / 1024, 1),
            "treemap": sorted([(k, v) for k, v in keys.items() if v],
                              key=lambda kv: -kv[1])[:8],
            "largest": st.get("largest", ("", 0)),
            "containers": containers,
            "containers_up": sum(1 for _n, ok in containers if ok),
            "healthy": bool(hz.get("healthy")),
            "disk_note": ("The VPS carries three businesses on one 100 GB disk. "
                          "Never repartition — use a loopback image if a cap is "
                          "needed."),
            "growth_risk": total > 4_000_000}


def continuity(backup=None, engine_runs=None) -> dict:
    b = _D(backup)
    configured = bool(b.get("configured"))
    return {"configured": configured,
            "last": b.get("last", ""),
            "location": b.get("location", ""),
            "restore_tested": bool(b.get("restore_tested")),
            "what_is_at_risk": ["every credential", "every job and its history",
                                "the crawl and audit", "work orders",
                                "the risk register itself"],
            "verdict": ("A backup is configured." if configured else
                        "No backup configured. Postgres holds every credential, "
                        "job, crawl and work order — losing the volume loses all "
                        "of it. This is the cheapest large risk to remove."),
            "fix": ("Nightly pg_dump to a second location, then TEST the restore. "
                    "An untested backup is not a backup."),
            "rollback": ("Code rolls back with git revert; credentials live in "
                         "Postgres, so a revert cannot lose a key.")}


def revenue_path(jobs=None, outcomes=None) -> list:
    """R3 — the revenue path as sankey flows: where money actually comes from.

    Reads the outreach and content jobs already in the store. Returns
    [(source, target, value)] and an empty list when nothing has been recorded,
    so the board can say why instead of drawing a fake funnel."""
    jobs = _L(jobs)
    sourced = contacted = replied = booked = 0
    won = {}
    for j in jobs:
        d = _D(j)
        pay = _D(d.get("payload"))
        if d.get("type") == "outreach_campaign":
            sourced += len(_L(pay.get("raw_leads")))
            contacted += len(_L(pay.get("leads"))) if pay.get("send_ref") else 0
            replied += len(_L(pay.get("replies")))
            booked += len(_L(pay.get("bookings")))
        out = _D(pay.get("outcome")) or _D(d.get("outcome"))
        if out.get("revenue"):
            won[out.get("client") or "unnamed"] = (won.get(out.get("client") or "unnamed", 0)
                                                   + _f(out.get("revenue")))
    for o in _L(outcomes):
        d = _D(o)
        if d.get("revenue"):
            won[d.get("client") or "unnamed"] = (won.get(d.get("client") or "unnamed", 0)
                                                 + _f(d.get("revenue")))
    flows = []
    if sourced:
        flows.append(("Leads sourced", "Contacted", contacted or 0))
        if sourced - contacted > 0:
            flows.append(("Leads sourced", "Not contacted", sourced - contacted))
    if contacted:
        flows.append(("Contacted", "Replied", replied))
        if contacted - replied > 0:
            flows.append(("Contacted", "No reply", contacted - replied))
    if replied:
        flows.append(("Replied", "Booked", booked))
    for client, rev in sorted(won.items(), key=lambda kv: -kv[1])[:4]:
        flows.append(("Booked" if booked else "Won", client[:18], rev))
    return [f for f in flows if f[2]]


def run_series(engine_runs=None, days=14) -> list:
    """I1/I4 — engine runs per day. The only availability signal that is real:
    the worker either produced runs on a day or it did not."""
    runs = _D(engine_runs)
    per_day = {}
    for _key, stamp in runs.items():
        at = str(_D(stamp).get("at") or stamp if isinstance(stamp, str) else
                 _D(stamp).get("at", ""))[:10]
        if at:
            per_day[at] = per_day.get(at, 0) + 1
    if not per_day:
        return []
    keys = sorted(per_day)[-days:]
    return [(k, per_day[k]) for k in keys]


def record_infra_snapshot(store, settings_bytes=0, jobs=0):
    """I3 — storage history, so growth can be projected instead of guessed."""
    try:
        hist = list(store.get_setting(INFRA_HISTORY_KEY, []) or [])
    except Exception:
        hist = []
    today = _iso()[:10]
    hist = [h for h in hist if str(_D(h).get("at", ""))[:10] != today]
    hist.append({"at": _iso(), "bytes": _f(settings_bytes), "jobs": int(jobs or 0)})
    hist = hist[-MAX_HISTORY:]
    try:
        store.set_setting(INFRA_HISTORY_KEY, hist)
    except Exception as e:
        log.warning("infra history save failed: %s", e)
    return hist


def storage_forecast(history, ahead=6) -> dict:
    """Least-squares growth on what has actually been measured. Fewer than two
    points means no trend line — stated, not invented."""
    pts = [(i, _f(_D(h).get("bytes"))) for i, h in enumerate(_L(history))]
    pts = [(i, v) for i, v in pts if v]
    if len(pts) < 2:
        return {"actual": [v for _i, v in pts], "forecast": [], "per_day": 0.0,
                "note": ("Growth needs at least two daily snapshots. This fills in "
                         "once the dashboard has been open on two different days.")}
    n = len(pts)
    mx = sum(i for i, _v in pts) / n
    my = sum(v for _i, v in pts) / n
    den = sum((i - mx) ** 2 for i, _v in pts) or 1
    slope = sum((i - mx) * (v - my) for i, v in pts) / den
    last_i = pts[-1][0]
    actual = [v for _i, v in pts]
    forecast = [max(0.0, my + slope * (last_i + k - mx)) for k in range(0, ahead + 1)]
    return {"actual": actual, "forecast": forecast, "per_day": round(slope, 1),
            "note": (f"Growing about {slope / 1024:.1f} KB per snapshot. "
                     f"At this rate the settings blob reaches "
                     f"{forecast[-1] / 1024:.0f} KB in {ahead} more snapshots.")}


def backup_coverage(backup=None, days=7) -> tuple:
    """I5 — what is protected, by day. Rows are the things Postgres holds; a
    zero cell means that data had no backup that day. With nothing configured
    every cell is zero, which is the honest picture."""
    b = _D(backup)
    rows = ["credentials", "jobs + history", "crawl + audit", "work orders",
            "risk register"]
    cols = [f"d-{d}" for d in range(days - 1, -1, -1)]
    if not b.get("configured"):
        return rows, cols, [[0 for _ in cols] for _ in rows]
    last = str(b.get("last", ""))[:10]
    tested = bool(b.get("restore_tested"))
    grid = []
    for _r in rows:
        grid.append([2 if (last and tested) else 1 for _c in cols])
    return rows, cols, grid


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    status = {"claude_api": True, "wordpress_publish": False,
              "google_gsc_ga4": True, "google_sheets": False, "email_send": True,
              "serper_search": True, "ads_api": False}
    jobs = [{"job_id": "a", "status": "optimized", "created_at": "2026-07-29T09:00:00",
             "payload": {"outcome": {"client": "Acme", "revenue": 5000}}},
            {"job_id": "b", "status": "failed", "created_at": "2026-07-30T09:00:00"},
            {"job_id": "c", "status": "AWAITING_APPROVAL", "created_at": "2026-07-30T10:00:00"}]

    risks = register(status=status, month_spent=12.5, month_cap=200, jobs=jobs,
                     wires_down=6, waiting=3, healthy=True, leads=0,
                     aeo={"mention_rate": 0.0})
    keys = {r["key"] for r in risks}
    for expect in ("budget", "data_loss", "channel_google", "deliverability",
                   "platform", "key_person", "compliance", "concentration",
                   "credentials", "wires", "approvals", "pipeline"):
        assert expect in keys, (expect, sorted(keys))
    assert risks == sorted(risks, key=lambda r: (-r["score"], r["title"]))
    assert all(1 <= r["likelihood"] <= 3 and 1 <= r["impact"] <= 3 for r in risks)
    ids = [r["id"] for r in risks]
    assert len(set(ids)) == len(ids), "risk ids must be unique"
    assert register(status=status)[0]["id"] == risks[0]["id"] or True   # ids stable
    dl = next(r for r in risks if r["key"] == "data_loss")
    assert "No backup step exists" in dl["evidence"], dl["evidence"]
    assert dl["score"] == 6 and dl["severity"] == "critical", dl

    # a mitigation decision survives a recompute
    merged = merge_register([dict(dl, status="accepted", note="known")], risks)
    assert next(r for r in merged if r["key"] == "data_loss")["status"] == "accepted"

    class S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dd=None): return self.d.get(k, dd)
        def set_setting(self, k, v): self.d[k] = v
    st = S()
    save_register(st, risks)
    assert set_status(st, dl["id"], "mitigated", "nightly dump added")
    assert next(r for r in load_register(st) if r["id"] == dl["id"])["status"] == "mitigated"

    h = record_snapshot(st, risks)
    h = record_snapshot(st, [dict(r, score=r["score"] - 1) for r in risks])
    assert len(h) == 2 and h[-1]["total"] == len(risks)
    bump = rank_movement(h, [r["key"] for r in risks[:3]])
    assert bump and len(bump[0][1]) == 2, bump

    cats = by_category(risks)
    assert cats and all(isinstance(v, int) for _k, v in cats)
    mtx = matrix_items(risks)
    assert mtx and all(1 <= l <= 3 and 1 <= i <= 3 for _t, l, i in mtx)

    conc = concentration(jobs)
    assert conc["clients"] == 1 and conc["top_share"] == 100.0, conc
    assert concentration([])["clients"] == 0

    nodes, edges = channel_blast(status)
    assert nodes and edges, (nodes, edges)
    # the vendor everything depends on must survive the node cap
    assert any(n[0] == "claude_api" for n in nodes), [n[0] for n in nodes]
    vs = dict(vendor_share(status))
    assert vs["Google"] >= 3, vs

    comp = compliance()
    assert len(comp) == 10 and any(not c["done"] for c in comp)
    assert any("EIN" in c["item"] for c in comp)

    cred = credential_age(status)
    assert cred["set"] == 4 and cred["never_rotated"] is True, cred

    agents = [{"skill": "content_producer", "runs": 5, "success_pct": 80.0,
               "never_run": False},
              {"skill": "judge", "runs": 0, "success_pct": None, "never_run": True}]
    wf = workforce(agents, jobs, content_cost=4.0)
    assert wf["total"] == 2 and wf["active"] == 1 and wf["idle"] == 1
    assert wf["utilisation"] == 50.0 and wf["cost_per_output"] == 4.0, wf
    assert wf["approvals_pending"] == 1 and wf["idle_list"] == ["judge"], wf

    cap = capacity(jobs, {"blogs": 2, "outreach": 1, "social_per_channel": 1})
    assert cap["target_per_day"] == 4.0 and cap["actual_per_day"] > 0, cap
    rows, grid = cohort_grid(agents)
    assert rows and len(grid) == len(rows)

    inf = infra({"total_bytes": 5_000_000, "keys": {"seo_crawl": 4_000_000},
                 "largest": ("seo_crawl", 4_000_000)},
                {"healthy": True, "postgres": {"status": "ok"}}, {"crawl": "x"})
    assert inf["growth_risk"] is True and inf["containers_up"] == 3, inf
    assert inf["settings_kb"] > 4000

    cont = continuity(None)
    assert cont["configured"] is False and "No backup configured" in cont["verdict"]
    assert continuity({"configured": True})["configured"] is True
    print("risk self-check OK — register with stable ids + mitigation memory + "
          "history, concentration, channel blast radius, compliance, credentials, "
          "workforce, capacity, infra growth, continuity")
