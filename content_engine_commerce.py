# -*- coding: utf-8 -*-
"""THE CMS LAYER: what the site sells, and therefore what to write.

The founder's ask, in his words: "in sga section i can ad shopify,
wordpress and other cms my agent gonna [be connected] with the cms data
[and] search console data and work automatically, they know that they
should work for e commerce or service, they also know which type of
content need".

So three things, in order:
  CONNECT   read-only credentials per platform, saved through the same
            settings store every other wire uses
  READ      the catalogue (products) or the content inventory (pages),
            whichever that platform actually has
  DECIDE    ECOMMERCE or SERVICE, from EVIDENCE - products found, and
            what people already search to reach the site - never from a
            guess, and UNKNOWN stays UNKNOWN until something is read

The content policy hangs off that verdict, because a shop needs product
and category pages and a consultancy needs guides and proof.

NOTHING HERE WRITES TO A SHOP. Reading a catalogue is safe; changing a
price or publishing a product is not, and this module cannot do it.
"""
from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------------
#: What each platform needs before it can be read. These are ordinary
#: connector keys: they go through /connect like every other credential,
#: are stored in the same settings table, and are never read back out.
PLATFORMS: Dict[str, Dict[str, Any]] = {
    "shopify": {
        "label": "Shopify",
        "keys": ("SHOPIFY_SHOP_DOMAIN", "SHOPIFY_ADMIN_TOKEN"),
        "reads": "products, collections, and what each one costs",
        "where": ("Shopify admin, Settings, Apps and sales channels, "
                  "Develop apps, then a custom app with read_products"),
    },
    "woocommerce": {
        "label": "WooCommerce",
        "keys": ("WOO_SITE_URL", "WOO_CONSUMER_KEY", "WOO_CONSUMER_SECRET"),
        "reads": "products and categories over the REST API",
        "where": "WooCommerce, Settings, Advanced, REST API, read-only key",
    },
    "wordpress": {
        "label": "WordPress",
        "keys": ("WP_URL", "WP_USER", "WP_APP_PASSWORD"),
        "reads": "pages and posts already published",
        "where": "WordPress user profile, Application Passwords",
    },
}

#: Queries that betray a shop, and queries that betray a service.
#: Deliberately small and readable: a classifier nobody can audit is a
#: classifier nobody should trust.
_BUY_WORDS = ("buy", "price", "cheap", "shop", "order", "delivery",
              "shipping", "discount", "coupon", "in stock", "kaufen",
              "preis", "bestellen", "versand")
_HIRE_WORDS = ("agency", "consultant", "consulting", "service", "services",
               "hire", "freelance", "quote", "book a", "audit", "strategy",
               "beratung", "agentur", "dienstleistung")


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _s(x) -> str:
    return "" if x is None else str(x)


def _env(store, key: str) -> str:
    """Settings first, then environment: the resolver every wire uses."""
    try:
        v = store.get_setting(key, None)
        if v not in (None, ""):
            return _s(v).strip()
    except Exception:                                 # noqa: BLE001
        pass
    import os
    return _s(os.getenv(key, "")).strip()


# ==========================================================================
# CONNECT
# ==========================================================================
def status(store) -> Dict[str, Any]:
    """Which CMS platforms hold every key they need. Presence only."""
    out = {}
    for pid, spec in PLATFORMS.items():
        have = [k for k in spec["keys"] if _env(store, k)]
        out[pid] = {
            "label": spec["label"],
            "connected": len(have) == len(spec["keys"]),
            "have": len(have), "needs": len(spec["keys"]),
            "missing": [k for k in spec["keys"] if k not in have],
            "reads": spec["reads"], "where": spec["where"],
        }
    return out


def connector_keys() -> List[str]:
    """Every key this module accepts, for the allow-list on /connect."""
    out = []
    for spec in PLATFORMS.values():
        out.extend(spec["keys"])
    return out


# ==========================================================================
# READ
# ==========================================================================
def _requests():
    try:
        import requests
        return requests
    except Exception:                                 # noqa: BLE001
        return None


def fetch_catalogue(store, platform: str = "", limit: int = 100
                    ) -> Dict[str, Any]:
    """Read products (or pages) from a connected CMS. READ ONLY.

    Returns {ok, platform, products, count, why}. Never raises into a
    render, and never reports zero products as "no shop": a call that
    failed and a shop that is empty are different facts."""
    st = status(store)
    plat = platform or next((p for p, v in st.items() if v["connected"]), "")
    if not plat:
        return {"ok": False, "products": [], "count": None,
                "why": "no CMS platform holds all of its keys yet"}
    if not st.get(plat, {}).get("connected"):
        return {"ok": False, "platform": plat, "products": [], "count": None,
                "why": (PLATFORMS[plat]["label"] + " is missing "
                        + ", ".join(st[plat]["missing"]))}
    rq = _requests()
    if rq is None:
        return {"ok": False, "platform": plat, "products": [], "count": None,
                "why": "the requests library is not installed in this image"}
    try:
        if plat == "shopify":
            dom = _env(store, "SHOPIFY_SHOP_DOMAIN").replace("https://", "")
            tok = _env(store, "SHOPIFY_ADMIN_TOKEN")
            r = rq.get(f"https://{dom}/admin/api/2024-10/products.json",
                       headers={"X-Shopify-Access-Token": tok},
                       params={"limit": min(int(limit), 250)}, timeout=25)
            if r.status_code >= 400:
                return {"ok": False, "platform": plat, "products": [],
                        "count": None,
                        "why": f"Shopify refused the read ({r.status_code}). "
                               "The admin token needs read_products."}
            rows = _l(_d(r.json()).get("products"))
            items = [{"id": _s(p.get("id")), "title": _s(p.get("title")),
                      "type": _s(p.get("product_type")),
                      "status": _s(p.get("status")),
                      "url": _s(p.get("handle"))} for p in map(_d, rows)]
        elif plat == "woocommerce":
            base = _env(store, "WOO_SITE_URL").rstrip("/")
            r = rq.get(base + "/wp-json/wc/v3/products",
                       auth=(_env(store, "WOO_CONSUMER_KEY"),
                             _env(store, "WOO_CONSUMER_SECRET")),
                       params={"per_page": min(int(limit), 100)}, timeout=25)
            if r.status_code >= 400:
                return {"ok": False, "platform": plat, "products": [],
                        "count": None,
                        "why": f"WooCommerce refused the read "
                               f"({r.status_code}). The key needs read "
                               f"scope and the site must allow REST."}
            items = [{"id": _s(p.get("id")), "title": _s(p.get("name")),
                      "type": _s(p.get("type")), "status": _s(p.get("status")),
                      "url": _s(p.get("permalink"))}
                     for p in map(_d, _l(r.json()))]
        else:  # wordpress: pages, not products
            base = _env(store, "WP_URL").rstrip("/")
            r = rq.get(base + "/wp-json/wp/v2/pages",
                       auth=(_env(store, "WP_USER"),
                             _env(store, "WP_APP_PASSWORD")),
                       params={"per_page": min(int(limit), 100)}, timeout=25)
            if r.status_code >= 400:
                return {"ok": False, "platform": plat, "products": [],
                        "count": None,
                        "why": f"WordPress refused the read "
                               f"({r.status_code})."}
            items = [{"id": _s(p.get("id")),
                      "title": _s(_d(p.get("title")).get("rendered")),
                      "type": "page", "status": _s(p.get("status")),
                      "url": _s(p.get("link"))}
                     for p in map(_d, _l(r.json()))]
    except Exception as exc:                          # noqa: BLE001
        return {"ok": False, "platform": plat, "products": [], "count": None,
                "why": f"the read failed: {type(exc).__name__}: "
                       f"{str(exc)[:120]}"}
    try:
        store.set_setting("cms_catalogue", {
            "platform": plat, "count": len(items),
            "items": items[:200], "at": _now()})
    except Exception:                                 # noqa: BLE001
        pass
    return {"ok": True, "platform": plat, "products": items,
            "count": len(items),
            "why": f"read {len(items)} item(s) from "
                   f"{PLATFORMS[plat]['label']}"}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ==========================================================================
# DECIDE
# ==========================================================================
def detect_business_type(store, *, catalogue=None, queries=None
                         ) -> Dict[str, Any]:
    """ECOMMERCE, SERVICE, or UNKNOWN - with the evidence that decided it.

    Two independent witnesses: what the CMS holds, and what people
    already type to arrive. They can disagree (a consultancy with three
    downloadable products), so the verdict names both and says which
    weighed more. UNKNOWN is a real answer and stays until something is
    actually read: guessing here would send every agent in the machine
    down the wrong road at once."""
    cat = _d(catalogue if catalogue is not None
             else _d(store.get_setting("cms_catalogue", {}) or {}))
    items = _l(cat.get("items"))
    n_products = len([i for i in map(_d, items)
                      if _s(i.get("type")) != "page"])
    n_pages = len([i for i in map(_d, items)
                   if _s(i.get("type")) == "page"])

    qs = _l(queries)
    if not qs:
        ins = _d(store.get_setting("google_insights", {}) or {})
        qs = [_s(_d(r).get("keys") or _d(r).get("query"))
              for r in _l(_d(ins.get("gsc")).get("queries"))]
    ql = [q.lower() for q in qs if q]
    buy = sum(1 for q in ql if any(w in q for w in _BUY_WORDS))
    hire = sum(1 for q in ql if any(w in q for w in _HIRE_WORDS))

    ev = {"products_found": n_products, "pages_found": n_pages,
          "queries_read": len(ql), "buying_intent_queries": buy,
          "hiring_intent_queries": hire,
          "catalogue_at": _s(cat.get("at")),
          "platform": _s(cat.get("platform"))}

    if not items and not ql:
        return {"type": "UNKNOWN", "confidence": "NONE",
                "why": ("nothing has been read yet: no CMS catalogue and "
                        "no search queries. Connect a CMS or wait for the "
                        "next Search Console pull. A guess here would "
                        "point every content agent at the wrong business."),
                "evidence": ev, "at": _now()}

    if n_products >= 3:
        conf = "HIGH" if (n_products >= 10 or buy >= hire) else "MEDIUM"
        return {"type": "ECOMMERCE", "confidence": conf,
                "why": (f"{n_products} product(s) in the "
                        f"{_s(cat.get('platform')) or 'CMS'} catalogue"
                        + (f", and {buy} of {len(ql)} search queries carry "
                           f"buying intent" if ql else "")),
                "evidence": ev, "at": _now()}

    if ql and buy > hire and buy >= 3:
        return {"type": "ECOMMERCE", "confidence": "MEDIUM",
                "why": (f"no catalogue read yet, but {buy} of {len(ql)} "
                        f"queries carry buying intent against {hire} "
                        f"hiring intent"),
                "evidence": ev, "at": _now()}

    if (n_pages or ql) and hire >= buy:
        conf = "HIGH" if hire >= 3 else "LOW"
        return {"type": "SERVICE", "confidence": conf,
                "why": (f"no products in the catalogue"
                        + (f", {n_pages} page(s) published" if n_pages else "")
                        + (f", and {hire} of {len(ql)} queries ask for "
                           f"someone to hire" if ql else "")),
                "evidence": ev, "at": _now()}

    return {"type": "UNKNOWN", "confidence": "LOW",
            "why": ("what was read does not separate a shop from a "
                    "service: too few products and too little search "
                    "intent either way"),
            "evidence": ev, "at": _now()}


def save_business_type(store, verdict: dict) -> dict:
    """Persist the verdict so every agent reads the same one."""
    try:
        store.set_setting("business_type", verdict)
    except Exception:                                 # noqa: BLE001
        pass
    return verdict


# ==========================================================================
# THE CONTENT POLICY that hangs off the verdict
# ==========================================================================
#: What to write, per business type. A shop and a consultancy do not
#: need the same pages, and this is the table the planner reads instead
#: of writing blog posts at everyone forever.
CONTENT_POLICY = {
    "ECOMMERCE": {
        "types": ("product page", "category page", "buying guide",
                  "comparison", "how-to using the product",
                  "review round-up"),
        "avoid": ("thought leadership with no product on the page",),
        "why": ("a shop is found by people comparing and buying, so the "
                "pages that earn the click name the product, the price "
                "and the alternative"),
        "cta": "add to cart or view the product",
    },
    "SERVICE": {
        "types": ("guide", "case study", "method explainer", "pricing page",
                  "comparison of approaches", "FAQ"),
        "avoid": ("product listings for things you do not sell",),
        "why": ("a service is bought on proof and trust, so the pages "
                "that earn the enquiry show the method and the result"),
        "cta": "book a call or request an audit",
    },
    "UNKNOWN": {
        "types": (),
        "avoid": (),
        "why": ("the business type is not established, so no content "
                "type is recommended. Anything written now would be a "
                "guess wearing a plan."),
        "cta": "",
    },
}


def content_policy(store=None, verdict=None) -> Dict[str, Any]:
    """The content types this business should be making, and why."""
    v = _d(verdict if verdict is not None
           else (_d(store.get_setting("business_type", {}) or {})
                 if store is not None else {}))
    t = _s(v.get("type")).upper() or "UNKNOWN"
    pol = dict(CONTENT_POLICY.get(t, CONTENT_POLICY["UNKNOWN"]))
    pol["business_type"] = t
    pol["confidence"] = _s(v.get("confidence")) or "NONE"
    pol["basis"] = _s(v.get("why"))
    return pol


def refresh(store) -> Dict[str, Any]:
    """Read the CMS, decide the business type, save it. One call, so the
    scheduler and the dashboard button do exactly the same thing."""
    cat = fetch_catalogue(store)
    verdict = detect_business_type(store)
    save_business_type(store, verdict)
    return {"ok": True, "catalogue": {"ok": cat.get("ok"),
                                      "count": cat.get("count"),
                                      "why": cat.get("why")},
            "business_type": verdict["type"],
            "confidence": verdict["confidence"],
            "why": verdict["why"],
            "message": (f"{verdict['type']} ({verdict['confidence']} "
                        f"confidence): {verdict['why']}")}


if __name__ == "__main__":
    class _S:
        def __init__(self, d=None):
            self.d = d or {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    s = _S()
    v = detect_business_type(s)
    assert v["type"] == "UNKNOWN" and v["confidence"] == "NONE", v
    s.d["cms_catalogue"] = {"platform": "shopify", "at": "x", "items": [
        {"id": "1", "title": "A", "type": "shirt"},
        {"id": "2", "title": "B", "type": "shirt"},
        {"id": "3", "title": "C", "type": "shirt"}]}
    v = detect_business_type(s)
    assert v["type"] == "ECOMMERCE", v
    assert content_policy(verdict=v)["cta"].startswith("add to cart")
    v2 = detect_business_type(_S(), queries=["seo agency munich",
                                             "hire a consultant",
                                             "marketing strategy audit"])
    assert v2["type"] == "SERVICE", v2
    assert "guide" in content_policy(verdict=v2)["types"]
    assert content_policy(verdict={"type": "UNKNOWN"})["types"] == ()
    print("OK - commerce: unknown stays unknown, a catalogue makes a shop, "
          "hiring queries make a service, and the policy follows")
