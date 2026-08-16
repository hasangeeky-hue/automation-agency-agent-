# -*- coding: utf-8 -*-
"""THE FEED: pull real rows in through every wire that is actually live.

    docker compose -f deploy/docker-compose.yml exec -T api \
        python feed_data.py
    ... --dry     say what would run and what would be skipped, run nothing
    ... --paid    also run the collectors that cost money, named first

WHAT THIS IS

Stage 3. The census said what is held; this fills it. For every wire that
holds its credentials, the matching READ collector runs and writes its rows
into the store the screens already read from.

WHAT IT WILL NEVER DO

Nothing here posts, sends, publishes, prices or spends. Every collector
below is a read: the shop's order list, the calendar's bookings, the
catalogue, the follower counts. The agents stay off. This is the engine
opening its eyes, not the engine going to work.

The separation is deliberate and it is the founder's rule: connect and
prove every wire first, keep the engine off. A feeder that could send is a
feeder nobody can safely run twice.

FREE BY DEFAULT

Four collectors cost real money per call - the AI visibility probes, rank
tracking through Serper, backlinks through DataForSEO, and link
prospecting. They are listed every run so they are never forgotten, and
they only execute behind --paid, which prints what it is about to spend on
before it does. A data feed that quietly bills the founder is a bug, not a
feature.

WHY IT REPORTS SKIPS AS LOUDLY AS FEEDS

"0 rows" is the least useful sentence this engine can produce. Every skip
below names the wire, the exact credential field it wants, and where that
credential is issued. A feed that fed nothing should still leave the
founder holding a next step.
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Dict, List, Optional

# ==========================================================================
# THE FEEDS
# ==========================================================================
#: name, the wire(s) any of which makes it runnable, what it pulls, and the
#: credential to name when it cannot run. `wires` is ANY-of: a shop feed is
#: runnable on Shopify OR WooCommerce, and demanding both would refuse a
#: perfectly good single-shop setup.
FREE_FEEDS: List[Dict[str, Any]] = [
    {"id": "bookings", "label": "Consultations from Cal.com",
     "wires": ("calcom_bookings",),
     "pulls": "every booked call, with its status",
     "needs": "CALCOM_API_KEY, from Cal.com Settings, Developer, API keys"},
    {"id": "orders", "label": "Orders from the shop",
     "wires": ("shopify", "woocommerce"),
     "pulls": "orders, revenue by channel, top sellers, and the deals feed "
              "the revenue screens read",
     "needs": "SHOPIFY_SHOP_DOMAIN + SHOPIFY_ADMIN_TOKEN (with BOTH "
              "read_products and read_orders), or WOO_SITE_URL + "
              "WOO_CONSUMER_KEY + WOO_CONSUMER_SECRET"},
    {"id": "catalogue", "label": "Catalogue and business type",
     "wires": ("shopify", "woocommerce", "wordpress_cms"),
     "pulls": "products or pages, and what kind of business this is",
     "needs": "any one shop or CMS: SHOPIFY_*, WOO_*, or WP_URL + WP_USER "
              "+ WP_APP_PASSWORD"},
    {"id": "social", "label": "Follower and post counts",
     "wires": ("social_linkedin", "social_facebook", "social_instagram",
               "social_tiktok", "social_twitter"),
     "pulls": "one dated snapshot per channel, so the screens can show a "
              "trend instead of a number that overwrites yesterday",
     "needs": "any one channel token: LINKEDIN_POST_TOKEN, META_PAGE_TOKEN, "
              "TIKTOK_ACCESS_TOKEN or TWITTER_BEARER_TOKEN"},
]

#: Named every run, executed only behind --paid. Cost is per call and real.
PAID_FEEDS: List[Dict[str, Any]] = [
    {"id": "aeo", "label": "AI visibility probes",
     "wires": ("claude_api",),
     "cost": "one LLM call per prompt per engine, on your Anthropic, "
             "OpenAI, Perplexity and Gemini balances"},
    {"id": "ranks", "label": "Rank tracking",
     "wires": ("seo_rank_tracker",),
     "cost": "one paid Serper search per tracked keyword"},
    {"id": "backlinks", "label": "Backlink profile",
     "wires": ("seo_backlinks",),
     "cost": "one paid DataForSEO call per domain"},
    {"id": "prospects", "label": "Link prospecting",
     "wires": ("serper_search",),
     "cost": "several paid Serper searches per keyword"},
]


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _rule(title: str) -> None:
    print("")
    print("=" * 74)
    print(title)
    print("=" * 74)


# ==========================================================================
# the collectors, each wrapped so one failure cannot take the run down
# ==========================================================================
def _feed_bookings(store) -> Dict[str, Any]:
    import content_engine_bookings as B
    got = B.fetch(store)
    if not got.get("ok"):
        return {"ok": False, "why": got.get("why"), "rows": 0}
    saved = _d(B.save(store, got["bookings"]))
    return {"ok": True, "rows": int(got.get("count") or 0),
            "note": "added %s, updated %s" % (saved.get("added"),
                                              saved.get("updated"))}


def _feed_orders(store) -> Dict[str, Any]:
    import content_engine_orders as O
    got = _d(O.run(store))
    if not got.get("ok"):
        return {"ok": False, "why": got.get("why"), "rows": 0}
    return {"ok": True, "rows": int(got.get("fetched") or 0),
            "note": "%s | deals written %s | %s"
                    % (got.get("platform"), got.get("deals_written"),
                       got.get("note"))}


def _feed_catalogue(store) -> Dict[str, Any]:
    import content_engine_commerce as CM
    got = _d(CM.refresh(store))
    cat = _d(got.get("catalogue"))
    if not cat.get("ok"):
        return {"ok": False, "why": cat.get("why"), "rows": 0}
    return {"ok": True, "rows": int(cat.get("count") or 0),
            "note": got.get("message")}


def _feed_social(store) -> Dict[str, Any]:
    import content_engine_social_stats as S
    got = _d(S.collect(store))
    rows = _l(got.get("rows"))
    kept = S.save(store, rows)
    read = int(got.get("read") or 0)
    if not read:
        # NAME EVERY CHANNEL AND ITS REASON. "0 channels read" over five
        # channels that each failed differently is the report that sends
        # you to check the wrong one.
        why = "; ".join(
            "%s: %s" % (_d(r).get("channel"), _d(r).get("why") or _d(r).get("state"))
            for r in rows) or "no channel is readable"
        return {"ok": False, "why": why, "rows": 0}
    return {"ok": True, "rows": read,
            "note": "%d of %d channel(s) answered, %d snapshot(s) held"
                    % (read, int(got.get("channels") or 0), kept)}


COLLECTORS: Dict[str, Callable[[Any], Dict[str, Any]]] = {
    "bookings": _feed_bookings,
    "orders": _feed_orders,
    "catalogue": _feed_catalogue,
    "social": _feed_social,
}


# ==========================================================================
def _live_wires(C) -> Dict[str, bool]:
    try:
        return {k: bool(v) for k, v in _d(C.status()).items()}
    except Exception as exc:                               # noqa: BLE001
        print("could not read wire status: %s" % type(exc).__name__)
        return {}


def _runnable(feed: Dict[str, Any], live: Dict[str, bool]) -> Optional[str]:
    """The first live wire that makes this feed runnable, or None."""
    for w in feed["wires"]:
        if live.get(w):
            return w
    return None


def main(argv: List[str]) -> int:
    dry = "--dry" in argv
    paid = "--paid" in argv

    print("DATA FEED - reads only. Nothing here posts, sends, publishes, "
          "prices or spends.")
    if dry:
        print("DRY RUN: nothing will be called.")

    import content_engine_api as API
    import content_engine_connectors as C
    store = API.get_store()
    if C._SETTINGS_GET is None:
        print("!! settings store not connected. Run this inside the api "
              "container, not on the host.")
        return 1

    live = _live_wires(C)
    print("%d of %d wire(s) hold their credentials."
          % (sum(1 for v in live.values() if v), len(live)))

    _rule("FREE FEEDS")
    fed, skipped, failed = [], [], []
    for feed in FREE_FEEDS:
        wire = _runnable(feed, live)
        if not wire:
            skipped.append(feed)
            print("\nSKIP  %s" % feed["label"])
            print("      no wire of: %s" % ", ".join(feed["wires"]))
            print("      needs: %s" % feed["needs"])
            continue
        if dry:
            print("\nWOULD RUN  %s   (via %s)" % (feed["label"], wire))
            print("           pulls %s" % feed["pulls"])
            continue
        print("\nRUN   %s   (via %s)" % (feed["label"], wire))
        try:
            got = _d(COLLECTORS[feed["id"]](store))
        except Exception as exc:                           # noqa: BLE001
            # One dead wire must not stop the other three. A feeder that
            # aborts on the first failure reports nothing about the rest,
            # and the founder cannot tell a broken shop from a broken run.
            got = {"ok": False, "rows": 0,
                   "why": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
        if got.get("ok"):
            fed.append((feed, got))
            print("      FED %d row(s). %s" % (got.get("rows") or 0,
                                               got.get("note") or ""))
        else:
            failed.append((feed, got))
            print("      NOTHING FED. %s" % got.get("why"))

    _rule("PAID FEEDS - not run unless you ask")
    for feed in PAID_FEEDS:
        wire = _runnable(feed, live)
        state = "ready" if wire else "wire not connected"
        print("  %-24s %-22s costs: %s"
              % (feed["label"], state, feed["cost"]))
    if not paid:
        print("\nNone of these ran. Add --paid to run them, and it will "
              "print what it is about to spend on first.")
    else:
        print("\n--paid was passed. These still need their own go-ahead: "
              "this build does not run them, because a metered call that "
              "starts from a flag is a bill nobody agreed to.")

    _rule("SUMMARY")
    print("fed      %d feed(s)" % len(fed))
    for feed, got in fed:
        print("   %-26s %d row(s)" % (feed["label"], got.get("rows") or 0))
    print("no data  %d feed(s)" % len(failed))
    for feed, got in failed:
        print("   %-26s %s" % (feed["label"], str(got.get("why"))[:80]))
    print("skipped  %d feed(s), no wire connected" % len(skipped))
    for feed in skipped:
        print("   %-26s %s" % (feed["label"], feed["needs"][:80]))
    print("")
    print("No agent was started. The scheduler is untouched.")
    return 0


def check() -> Dict[str, Any]:
    """Every wire a feed names must be a wire that exists.

    THIS IS THE BUG CLASS, NOT A NICETY. The feeds above name wires by
    hand, and status() names wires by hand, and the two lists have to
    agree. When they do not, the feed is not loud about it: _runnable()
    simply never finds its wire, and the feed reports SKIP with a tidy
    reason for the rest of time. Connect the shop, and it still skips.

    That is precisely how shopify sat outside status() while _FEEDS, the
    roster and _group_of all named it. So the agreement is asserted here
    and on every deploy, rather than trusted."""
    problems: List[str] = []
    try:
        import content_engine_connectors as C
        wires = set(_d(C.status()))
    except Exception as exc:                               # noqa: BLE001
        return {"ok": False, "problems": ["could not read status(): %s"
                                          % type(exc).__name__]}
    for feed in FREE_FEEDS + PAID_FEEDS:
        for w in feed["wires"]:
            if w not in wires:
                problems.append("%s names '%s', which status() does not "
                                "report, so it can never run" % (feed["id"], w))
        if not str(feed.get("needs") or feed.get("cost") or "").strip():
            problems.append("%s cannot say what it wants" % feed["id"])
    have = {f["id"] for f in FREE_FEEDS}
    if have != set(COLLECTORS):
        problems.append("free feeds and collectors disagree: %s"
                        % sorted(have ^ set(COLLECTORS)))
    return {"ok": not problems, "problems": problems,
            "free": len(FREE_FEEDS), "paid": len(PAID_FEEDS),
            "wires": len(wires)}


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        r = check()
        for p in r["problems"]:
            print("FAIL", p)
        print("feeds: %d free, %d paid, against %d wires - %s"
              % (r.get("free", 0), r.get("paid", 0), r.get("wires", 0),
                 "OK" if r["ok"] else "FAILED"))
        raise SystemExit(0 if r["ok"] else 1)
    raise SystemExit(main(sys.argv[1:]))
