# -*- coding: utf-8 -*-
"""TWO BUSINESSES, ONE ENGINE, AND THE WALL BETWEEN THEM.

The founder runs a service business (Anthropos, WordPress) and will
connect a product business (a shop). Before this module, every
credential resolved through ONE global settings pot and the engine held
ONE business_type verdict, so connecting the shop would have silently
merged two companies into one: the consultancy's blog written with a
checkout in mind, confidently, with no error anywhere.

AN ENTITY IS A WORKSPACE. The tenancy layer already has workspaces,
members, roles and require(); building a second scoping layer beside it
would be two lists that must agree, which is this project's oldest bug.
An entity here is nothing but a workspace id used as a credential and
verdict namespace.

RESOLUTION ORDER, the one rule of this module:

    entity_env(store, "shop", "SHOPIFY_ADMIN_TOKEN")
      1. setting  ws:shop:SHOPIFY_ADMIN_TOKEN     the entity's own key
      2. whatever _env() resolves globally         the founder's default

A key that is SCOPABLE identifies a business: its shop, its site, its
social channels, its analytics properties. A key that is NOT scopable is
shared plumbing (the Claude key, Serper, DataForSEO): scoping those
would mean two bills for one vendor, so scoping them is refused rather
than silently accepted.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Keys that may differ per business entity. DERIVED where possible
#: (commerce platform keys come from the commerce registry in check());
#: the rest are the identity and channel keys, typed once HERE and
#: checked against the connect allow-list so a typo cannot invent a key.
SCOPABLE_EXTRA = (
    # the site
    "WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD",
    "WP_URL", "WP_USER", "WP_APP_PASSWORD",
    # search + analytics identity
    "GSC_SITE_URL", "GA4_PROPERTY_ID",
    # social channel identity
    "LINKEDIN_POST_TOKEN", "LINKEDIN_AUTHOR_URN",
    "META_PAGE_ID", "META_PAGE_TOKEN", "IG_USER_ID",
    "TIKTOK_ACCESS_TOKEN", "TWITTER_BEARER_TOKEN",
    # bookings and brand
    "CALCOM_API_KEY", "CI_JSON", "EMAIL_FROM_NAME", "EMAIL_COMPANY",
    "EMAIL_WEBSITE",
)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _s(x) -> str:
    return str(x) if x is not None else ""


def scopable() -> tuple:
    """Every key an entity may hold its own value for."""
    keys = list(SCOPABLE_EXTRA)
    try:
        import content_engine_commerce as CM
        for spec in _d(getattr(CM, "PLATFORMS", {})).values():
            keys.extend(_d(spec).get("keys") or ())
    except Exception:                                     # noqa: BLE001
        pass
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return tuple(out)


def _ekey(entity_id: str, key: str) -> str:
    return "ws:%s:%s" % (_s(entity_id), _s(key))


# ==========================================================================
# READ
# ==========================================================================
def entities(store) -> List[Dict[str, Any]]:
    """The business entities: exactly the workspaces. The founder's home
    workspace is the default entity, so a single-business engine never
    has to know this module exists."""
    try:
        import content_engine_os_tenancy as TEN
        TEN.ensure_home(store)
        return [{"id": _s(w.get("id")), "name": _s(w.get("name"))}
                for w in _l(TEN.workspaces_for(store))]
    except Exception:                                     # noqa: BLE001
        return []


def default_entity() -> str:
    import content_engine_os_core as CORE
    return CORE.DEFAULT_WORKSPACE


def entity_env(store, entity_id: str, key: str, default: str = "") -> str:
    """The entity's own value first, the global resolution second.

    The fallback goes through connectors._env on purpose: that is where
    the alias map and the malformed-value shadow guard live, and a
    second resolution path that skipped them would reintroduce the
    IMAGE_API_KEY class of bug for entities only."""
    key = _s(key)
    if entity_id and entity_id != default_entity():
        try:
            v = store.get_setting(_ekey(entity_id, key), None)
        except Exception:                                 # noqa: BLE001
            v = None
        sv = (_s(v)).strip()
        if sv:
            return sv
    try:
        import content_engine_connectors as C
        return C._env(key, default)
    except Exception:                                     # noqa: BLE001
        return default


def set_entity_key(store, entity_id: str, key: str, value: str) -> Dict[str, Any]:
    """Save one entity-scoped credential. Refuses three ways, each named."""
    key, entity_id = _s(key), _s(entity_id)
    if key not in scopable():
        return {"ok": False,
                "why": ("%s is not entity-scopable. Shared plumbing (model "
                        "keys, search vendors) stays global so one vendor "
                        "means one bill." % key)}
    if not any(e["id"] == entity_id for e in entities(store)):
        return {"ok": False,
                "why": "no entity '%s' exists; create the workspace first"
                       % entity_id}
    try:
        import content_engine_connectors as C
        bad = C.credential_problem(key, _s(value))
        if bad:
            return {"ok": False, "why": "%s: %s" % (key, bad)}
    except Exception:                                     # noqa: BLE001
        pass
    store.set_setting(_ekey(entity_id, key), _s(value).strip())
    return {"ok": True, "key": key, "entity": entity_id}


# ==========================================================================
# WHICH ENTITY OWNS A PLATFORM (the router's first decision)
# ==========================================================================
def entity_of_platform(store, platform: str) -> Dict[str, Any]:
    """Which entity a platform's rows belong to.

    Deterministic, from who holds the keys:
      exactly one entity holds them scoped -> that entity
      nobody scoped, global keys exist     -> the default entity
      two entities hold the same platform  -> AMBIGUOUS, and the row is
                                              PARKED rather than guessed

    A wrong guess writes shop data into the consultancy, and nothing
    anywhere would flag it. Parking is the only honest answer."""
    platform = _s(platform).lower()
    try:
        import content_engine_commerce as CM
        spec = _d(_d(getattr(CM, "PLATFORMS", {})).get(platform))
        keys = tuple(spec.get("keys") or ())
    except Exception:                                     # noqa: BLE001
        keys = ()
    if not keys:
        # not a commerce platform (a social channel, a calendar): the
        # engine has one of each today, so they belong to the default
        # entity until someone scopes their identity keys.
        holders = []
        for e in entities(store):
            if e["id"] == default_entity():
                continue
            if any((_s(store.get_setting(_ekey(e["id"], k), "")) or "").strip()
                   for k in scopable()
                   if platform in k.lower()):
                holders.append(e["id"])
        if len(holders) == 1:
            return {"entity": holders[0], "how": "scoped identity key"}
        if len(holders) > 1:
            return {"entity": "", "how": "AMBIGUOUS: %s" % ", ".join(holders)}
        return {"entity": default_entity(), "how": "default workspace"}
    holders = []
    for e in entities(store):
        if e["id"] == default_entity():
            continue
        if all((_s(store.get_setting(_ekey(e["id"], k), "")) or "").strip()
               for k in keys):
            holders.append(e["id"])
    if len(holders) == 1:
        return {"entity": holders[0], "how": "holds all %d key(s)" % len(keys)}
    if len(holders) > 1:
        return {"entity": "",
                "how": "AMBIGUOUS: %s both hold %s" % (", ".join(holders),
                                                       platform)}
    return {"entity": default_entity(), "how": "global keys"}


# ==========================================================================
# PER-ENTITY BUSINESS TYPE
# ==========================================================================
def get_business_type(store, entity_id: str = "") -> Dict[str, Any]:
    """The entity's own verdict, falling back to the engine's global one
    for the default entity only. A non-default entity with no verdict is
    UNKNOWN, never inherited: a shop inheriting SERVICE would write
    service pages for a product catalogue."""
    eid = _s(entity_id) or default_entity()
    if eid != default_entity():
        v = _d(store.get_setting(_ekey(eid, "business_type"), None))
        return v or {"type": "UNKNOWN",
                     "why": "no CMS has been read for this entity yet"}
    return _d(store.get_setting("business_type", None)) or {
        "type": "UNKNOWN", "why": "nothing has been read from a CMS"}


def set_business_type(store, entity_id: str, verdict: dict) -> None:
    eid = _s(entity_id) or default_entity()
    if eid == default_entity():
        store.set_setting("business_type", _d(verdict))
    else:
        store.set_setting(_ekey(eid, "business_type"), _d(verdict))


# ==========================================================================
def check() -> Dict[str, Any]:
    """The wall must actually hold. Tested, not trusted."""
    problems: List[str] = []
    sc = scopable()

    # every scopable key must be one the connect endpoint accepts, or an
    # entity key could be saved that no global fallback could ever hold
    try:
        import content_engine_commerce as CM
        import content_engine_connectors as C
        allow = set(C.CONNECTOR_ENV_KEYS) | set(CM.connector_keys())
        rogue = [k for k in sc if k not in allow]
        if rogue:
            problems.append("scopable key(s) outside the allow-list: %s"
                            % ", ".join(rogue))
    except Exception as exc:                              # noqa: BLE001
        problems.append("could not read the allow-list: %s"
                        % type(exc).__name__)

    class _Stub:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, dflt=None):
            return self.d.get(k, dflt)

        def set_setting(self, k, v):
            self.d[k] = v

    st = _Stub()
    # resolution order: the entity's value wins over the global
    st.d["ws:shop:GSC_SITE_URL"] = "https://shop.example"
    got = entity_env(st, "shop", "GSC_SITE_URL")
    if got != "https://shop.example":
        problems.append("entity value did not win resolution: %r" % got)
    # THE WALL: entity A's key must never resolve for entity B
    if entity_env(st, "other", "GSC_SITE_URL", "") == "https://shop.example":
        problems.append("CROSS-ENTITY LEAK: one entity read another's key")
    # a non-default entity never inherits the global business verdict
    st.d["business_type"] = {"type": "SERVICE"}
    if get_business_type(st, "shop").get("type") == "SERVICE":
        problems.append("a shop entity inherited the service verdict")
    return {"ok": not problems, "problems": problems, "scopable": len(sc)}


if __name__ == "__main__":
    r = check()
    for p in r["problems"]:
        print("FAIL", p)
    print("entities: %d scopable key(s), wall %s"
          % (r["scopable"], "HOLDS" if r["ok"] else "BREACHED"))
    raise SystemExit(0 if r["ok"] else 1)
