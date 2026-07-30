"""
content_engine_workorders.py
============================================================================
THE MISSING LOOP.

Before this module, SEO findings died as text on a dashboard card. Nothing
turned "this page has no schema" into work that actually got done.

A WorkOrder is one atomic, verifiable fix:
    {id, code, type, url, severity, impact, effort, priority, evidence,
     fix, auto, status, created_at, done_at, result}

  status:  open -> queued -> done | awaiting_approval | skipped | failed

Auto-fixable orders (schema, alt text, internal links, OG tags, indexnow) are
executed by content_engine_seo_fixer without asking. Everything that changes
words a human wrote (titles, metas, body copy) lands in awaiting_approval.

Persisted through the store's settings (key `seo_workorders`) so it survives
restarts and shows on the dashboard. Pure logic — no network.

Run offline self-check:  python content_engine_workorders.py
============================================================================
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

log = logging.getLogger("workorders")

SETTING_KEY = "seo_workorders"
MAX_ORDERS = 600          # keep the settings row sane

# Which finding codes the machine may fix WITHOUT human approval.
# Rule: it may add machine-readable markup and links; it may not rewrite prose.
AUTO_CODES = {
    "schema_missing", "img_alt_missing", "og_missing", "few_internal_links",
    "orphan_page", "canonical_missing", "indexnow_pending",
}

# Which codes must be approved (they change copy a human will read).
APPROVAL_CODES = {
    "title_long", "title_short", "title_missing", "title_duplicate",
    "meta_missing", "meta_short", "meta_long", "meta_duplicate",
    "thin_content", "ctr_gap", "decay_refresh", "cannibalization",
}

# Effort in "machine minutes" — used only to rank impact/effort.
EFFORT = {
    "schema_missing": 1, "img_alt_missing": 2, "og_missing": 1,
    "few_internal_links": 2, "orphan_page": 2, "canonical_missing": 1,
    "title_long": 2, "title_short": 2, "title_missing": 2, "title_duplicate": 3,
    "meta_missing": 2, "meta_short": 2, "meta_long": 1, "meta_duplicate": 3,
    "thin_content": 8, "decay_refresh": 8, "cannibalization": 6, "ctr_gap": 2,
    "broken_internal_link": 2, "not_found": 4, "server_error": 5,
    "redirect_chain": 2, "slow_page": 6, "noindex": 1, "not_indexed": 3,
    "canonical_override": 4, "canonical_mismatch": 3, "mobile_fail": 5,
    "heading_order": 2, "h1_missing": 2, "h1_multiple": 2, "unreachable": 5,
}

TYPE_OF = {
    "schema_missing": "schema", "img_alt_missing": "on_page", "og_missing": "on_page",
    "few_internal_links": "internal_links", "orphan_page": "internal_links",
    "title_long": "title", "title_short": "title", "title_missing": "title",
    "title_duplicate": "title", "ctr_gap": "title",
    "meta_missing": "meta", "meta_short": "meta", "meta_long": "meta",
    "meta_duplicate": "meta",
    "thin_content": "content", "decay_refresh": "content", "cannibalization": "content",
    "not_indexed": "indexing", "canonical_override": "indexing",
    "canonical_missing": "indexing", "canonical_mismatch": "indexing",
    "indexnow_pending": "indexing",
    "broken_internal_link": "technical", "not_found": "technical",
    "server_error": "technical", "redirect_chain": "technical",
    "slow_page": "technical", "noindex": "technical", "mobile_fail": "technical",
    "unreachable": "technical", "heading_order": "on_page",
    "h1_missing": "on_page", "h1_multiple": "on_page",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _oid(code: str, url: str) -> str:
    return "wo_" + hashlib.sha1(f"{code}|{url}".encode("utf-8")).hexdigest()[:12]


def make_order(code, url, *, severity="medium", detail="", fix="",
               impact=None, auto=None, extra=None) -> dict:
    weight = {"critical": 100, "high": 60, "medium": 30, "low": 10}.get(severity, 10)
    imp = weight if impact is None else impact
    eff = EFFORT.get(code, 3)
    is_auto = (code in AUTO_CODES) if auto is None else bool(auto)
    return {"id": _oid(code, url), "code": code, "type": TYPE_OF.get(code, "on_page"),
            "url": url, "severity": severity, "impact": round(imp, 1), "effort": eff,
            "priority": round(imp / max(eff, 1), 2), "evidence": detail, "fix": fix,
            "auto": is_auto, "status": "open", "created_at": _now(),
            "done_at": None, "result": "", "extra": extra or {}}


def from_audit(audit: dict, *, max_content_orders: int = 25) -> list:
    """Turn a content_engine_seo.full_audit() result into work orders."""
    orders = []
    for i in audit.get("issues", []) or []:
        orders.append(make_order(i["code"], i["url"], severity=i["severity"],
                                 detail=i.get("detail", ""), fix=i.get("fix", ""),
                                 auto=i.get("auto")))
    # opportunity-driven orders (not "broken", but money left on the table)
    for r in (audit.get("ctr_gaps") or [])[:max_content_orders]:
        orders.append(make_order(
            "ctr_gap", r["query"], severity="high",
            detail=(f"#{r['position']} with {r['impressions']} impressions but "
                    f"{r['ctr_actual']}% CTR (expected ~{r['ctr_expected']}%) — "
                    f"~{r['missed_clicks']} clicks missed"),
            fix="Rewrite the title/meta of the ranking page",
            impact=min(100, r["missed_clicks"] * 4), auto=False,
            extra={"query": r["query"]}))
    for r in (audit.get("decay") or [])[:max_content_orders]:
        orders.append(make_order(
            "decay_refresh", r["url"], severity="high",
            detail=f"Clicks fell {r['change_pct']}% ({r['clicks_before']} -> {r['clicks_now']})",
            fix="Refresh and republish this page", impact=min(100, r["lost_clicks"] * 3),
            auto=False))
    for r in (audit.get("cannibalization") or [])[:max_content_orders]:
        orders.append(make_order(
            "cannibalization", r["best"], severity="medium",
            detail=(f"{r['page_count']} pages compete for “{r['query']}” — "
                    f"{', '.join(p.split('/')[-1] or '/' for p in r['competing'][:3])}"),
            fix="Consolidate, or differentiate the intent of each page",
            impact=min(100, r["impressions"] / 5), auto=False,
            extra={"query": r["query"], "pages": r["pages"]}))
    return orders


def merge(existing: list, fresh: list) -> list:
    """Re-running a crawl must not duplicate or resurrect finished work.

    - an order already done stays done (unless the issue reappears later)
    - an open order keeps its original created_at
    - an order that no longer appears in the fresh set is marked `resolved`
    """
    by_id = {o["id"]: dict(o) for o in existing or []}
    fresh_ids = set()
    for f in fresh or []:
        fresh_ids.add(f["id"])
        old = by_id.get(f["id"])
        if not old:
            by_id[f["id"]] = f
            continue
        if old.get("status") in ("done", "skipped"):
            continue          # already handled; don't reopen on the same evidence
        old.update({"severity": f["severity"], "impact": f["impact"],
                    "priority": f["priority"], "evidence": f["evidence"],
                    "fix": f["fix"], "auto": f["auto"]})
        by_id[f["id"]] = old
    for oid, o in by_id.items():
        if oid not in fresh_ids and o.get("status") == "open":
            o["status"] = "resolved"
            o["done_at"] = _now()
            o["result"] = "No longer detected in the latest crawl"

    # LIVE work must never be evicted by history. A re-crawl that re-keys every
    # URL (the trailing-slash fix did exactly that) resolves the whole old set,
    # and a flat priority sort then let 314 resolved orders occupy half the cap
    # and truncate real, open work off the end.
    live = [o for o in by_id.values() if o["status"] not in ("resolved", "done", "skipped")]
    history = [o for o in by_id.values() if o["status"] in ("resolved", "done", "skipped")]
    live.sort(key=lambda o: (-o["priority"], o["code"]))
    history.sort(key=lambda o: (o.get("done_at") or "", o["code"]), reverse=True)
    return (live + history)[:MAX_ORDERS]


# ---------------------------------------------------------------- store
def load(store) -> list:
    try:
        return store.get_setting(SETTING_KEY, []) or []
    except Exception as e:
        log.warning("workorder load failed: %s", e)
        return []


def save(store, orders: list) -> None:
    try:
        store.set_setting(SETTING_KEY, orders[:MAX_ORDERS])
    except Exception as e:
        log.warning("workorder save failed: %s", e)


def refresh(store, audit: dict) -> dict:
    """Generate + merge + persist. Returns the queue stats."""
    orders = merge(load(store), from_audit(audit))
    save(store, orders)
    return stats(orders)


def stats(orders: list) -> dict:
    by_status, by_type = {}, {}
    for o in orders or []:
        by_status[o["status"]] = by_status.get(o["status"], 0) + 1
        by_type[o["type"]] = by_type.get(o["type"], 0) + 1
    open_orders = [o for o in orders or [] if o["status"] == "open"]
    return {"total": len(orders or []), "by_status": by_status, "by_type": by_type,
            "open": len(open_orders),
            "auto_ready": sum(1 for o in open_orders if o["auto"]),
            "needs_approval": sum(1 for o in open_orders if not o["auto"]),
            "done": by_status.get("done", 0),
            "resolved": by_status.get("resolved", 0)}


def next_batch(orders: list, *, auto_only=True, limit=20, types=None) -> list:
    """Highest-priority open orders the fixer should execute now."""
    out = [o for o in orders or [] if o["status"] == "open"
           and (o["auto"] if auto_only else True)
           and (o["type"] in types if types else True)]
    return sorted(out, key=lambda o: -o["priority"])[:limit]


def mark(store, order_id: str, status: str, result: str = "") -> bool:
    orders = load(store)
    hit = False
    for o in orders:
        if o["id"] == order_id:
            o["status"] = status
            o["result"] = result
            o["done_at"] = _now() if status in ("done", "skipped", "failed") else None
            hit = True
            break
    if hit:
        save(store, orders)
    return hit


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    audit = {
        "issues": [
            {"code": "schema_missing", "severity": "high", "url": "https://x.com/a",
             "detail": "No JSON-LD", "fix": "Inject schema", "auto": True},
            {"code": "title_long", "severity": "medium", "url": "https://x.com/a",
             "detail": "80 chars", "fix": "Rewrite", "auto": False},
            {"code": "not_found", "severity": "high", "url": "https://x.com/b",
             "detail": "404", "fix": "Redirect", "auto": False},
        ],
        "ctr_gaps": [{"query": "ai automation law firm", "position": 6.2, "impressions": 400,
                      "ctr_actual": 0.75, "ctr_expected": 5.0, "missed_clicks": 17.0}],
        "decay": [{"url": "https://x.com/c", "clicks_now": 4, "clicks_before": 40,
                   "change_pct": -90.0, "lost_clicks": 36}],
        "cannibalization": [{"query": "automation for lawyers", "best": "https://x.com/a",
                             "competing": ["https://x.com/d"], "page_count": 2,
                             "impressions": 160, "pages": []}],
    }
    orders = from_audit(audit)
    assert len(orders) == 6, len(orders)
    auto = [o for o in orders if o["auto"]]
    assert [o["code"] for o in auto] == ["schema_missing"], auto
    assert all(o["priority"] > 0 for o in orders)
    ctr = next(o for o in orders if o["code"] == "ctr_gap")
    assert ctr["type"] == "title" and not ctr["auto"], ctr
    assert next(o for o in orders if o["code"] == "decay_refresh")["type"] == "content"

    # ids are stable so re-crawls don't duplicate
    assert from_audit(audit)[0]["id"] == orders[0]["id"]

    class S:
        def __init__(self): self.d = {}
        def get_setting(self, k, default=None): return self.d.get(k, default)
        def set_setting(self, k, v): self.d[k] = v

    st = S()
    s1 = refresh(st, audit)
    assert s1["total"] == 6 and s1["auto_ready"] == 1, s1
    assert s1["needs_approval"] == 5, s1

    oid = auto[0]["id"]
    assert mark(st, oid, "done", "schema injected")
    assert stats(load(st))["done"] == 1

    # re-running must NOT reopen the finished order
    s2 = refresh(st, audit)
    assert s2["done"] == 1, s2
    assert s2["total"] == 6, s2

    # an issue that disappears gets resolved, not deleted
    shrunk = dict(audit, issues=[audit["issues"][0]], ctr_gaps=[], decay=[], cannibalization=[])
    refresh(st, shrunk)
    resolved = [o for o in load(st) if o["status"] == "resolved"]
    assert len(resolved) == 5, [o["code"] for o in resolved]

    batch = next_batch(load(st), auto_only=False, limit=5)
    assert all(o["status"] == "open" for o in batch)

    # ---- LIVE work must never be evicted by resolved history ----
    # Reproduces the re-crawl that re-keyed every URL: a full set of old orders
    # resolves at once, and a flat priority sort would truncate real open work.
    old = [make_order("title_long", f"https://x.com/old-{i}", severity="critical")
           for i in range(MAX_ORDERS)]
    for o in old:
        o["status"] = "resolved"
        o["done_at"] = "2026-07-30T09:00:00"
    fresh = [make_order("meta_missing", f"https://x.com/new-{i}/", severity="low")
             for i in range(40)]
    merged = merge(old, fresh)
    open_kept = [o for o in merged if o["status"] == "open"]
    assert len(open_kept) == 40, f"live work was evicted: only {len(open_kept)} of 40 kept"
    assert len(merged) == MAX_ORDERS, len(merged)
    assert merged[0]["status"] == "open", "open work must sort ahead of history"
    # ...and critical-but-resolved must NOT outrank low-priority-but-open
    assert all(o["status"] == "open" for o in merged[:40]), [o["status"] for o in merged[:45]]
    print("workorders self-check OK — generate, merge, persist, resolve, batch")
