# -*- coding: utf-8 -*-
"""THE DATA MUTATION AGENT: a router and a ledger, and not a model.

Screen 16b has said since it was drawn: "who changed what, where, and
with whose approval." Until now nothing wrote that ledger, and the
screen said so honestly. This module is the writer.

WHY THIS IS CODE AND NOT AN LLM. Every decision it makes is already
known by the machinery that hands it the row: which credential answered
(entity), which platform answered (source), which collector ran (kind).
Paying a model to re-derive what the connector knows would be spend for
no judgment, and it would make routing non-reproducible: the same order
could land in a different business on a different day.

THE ROUTER NEVER GUESSES ENTITY. If two entities both hold a platform's
keys, the row is PARKED with the reason, loudly, exactly like every
other refusal in this engine. A wrong guess writes shop data into the
consultancy and nothing anywhere flags it; a parked row is a chip the
founder can decide in one click.

NO CREDENTIAL VALUE EVER ENTERS THE LEDGER. A credential_set row carries
the key NAME only. The record() call refuses anything that looks like a
secret in `what`, because an audit trail that leaks the values it audits
would be worse than no trail.
"""
from __future__ import annotations

from typing import Any, Dict, List

LEDGER_KEY = "mutation_ledger"
PARKED_KEY = "mutation_parked"
MAX_ROWS = 2000
MAX_PARKED = 300

#: every kind the ledger accepts, and the roster employee whose lane owns
#: rows of that kind. Checked against the real roster in check(), never
#: trusted: an unattributed kind is work nobody reports.
KIND_OWNER = {
    "order_sync": "commerce.analyst",
    "catalogue_sync": "commerce.analyst",
    "booking_sync": "bi.analyst",
    "social_snapshot": "sga.distributor",
    "price_change": "commerce.analyst",
    "credential_set": "system.integrations",
    "user_admin": "system.integrations",
    "rule_saved": "system.integrations",
}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _s(x) -> str:
    return str(x) if x is not None else ""


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _looks_secret(text: str) -> bool:
    t = _s(text)
    return ("sk-" in t or "Bearer " in t
            or any(len(w) > 40 and w.isalnum() for w in t.split()))


# ==========================================================================
# WRITE
# ==========================================================================
def record(store, *, source: str, kind: str, what: str, entity: str = "",
           actor: str = "engine", why: str = "",
           approved_by: str = "") -> Dict[str, Any]:
    """One ledger row. Refuses four ways, each named, because a ledger
    that accepts anything proves nothing."""
    if kind not in KIND_OWNER:
        return {"ok": False, "why": "unknown mutation kind %r; known: %s"
                % (kind, ", ".join(sorted(KIND_OWNER)))}
    if not _s(source).strip():
        return {"ok": False, "why": "a mutation with no source is a rumour"}
    if not _s(what).strip():
        return {"ok": False, "why": "a mutation that cannot say what "
                                    "changed records nothing"}
    if _looks_secret(what) or _looks_secret(why):
        return {"ok": False, "why": "refused: the text looks like it "
                                    "carries a credential value"}
    row = {"at": _now(), "source": _s(source), "kind": _s(kind),
           "entity": _s(entity), "actor": _s(actor),
           "what": _s(what)[:300], "why": _s(why)[:200],
           "approved_by": _s(approved_by), "owner": KIND_OWNER[kind]}
    rows = _l(store.get_setting(LEDGER_KEY, []))
    rows.append(row)
    store.set_setting(LEDGER_KEY, rows[-MAX_ROWS:])
    return {"ok": True, "row": row}


def park(store, *, source: str, kind: str, what: str, why: str) -> None:
    """A row the router refused to place. Loud, capped, dated."""
    rows = _l(store.get_setting(PARKED_KEY, []))
    rows.append({"at": _now(), "source": _s(source), "kind": _s(kind),
                 "what": _s(what)[:300], "why": _s(why)[:200]})
    store.set_setting(PARKED_KEY, rows[-MAX_PARKED:])


def route_and_record(store, *, platform: str, kind: str, what: str,
                     actor: str = "engine", why: str = "",
                     approved_by: str = "") -> Dict[str, Any]:
    """The agent's whole job in one call: decide the entity from who
    holds the platform's keys, then write the row, or park it."""
    try:
        import content_engine_entities as E
        got = E.entity_of_platform(store, platform)
    except Exception as exc:                              # noqa: BLE001
        got = {"entity": "", "how": "entity layer unreadable: %s"
               % type(exc).__name__}
    if not got.get("entity"):
        park(store, source=platform, kind=kind, what=what,
             why="entity could not be decided: %s" % got.get("how"))
        return {"ok": False, "parked": True, "why": got.get("how")}
    return record(store, source=platform, kind=kind, what=what,
                  entity=got["entity"], actor=actor, why=why,
                  approved_by=approved_by)


# ==========================================================================
# READ (what screen 16b renders)
# ==========================================================================
def ledger(store, limit: int = 60) -> List[dict]:
    return [_d(r) for r in _l(store.get_setting(LEDGER_KEY, []))][-limit:][::-1]


def parked(store) -> List[dict]:
    return [_d(r) for r in _l(store.get_setting(PARKED_KEY, []))][::-1]


def tallies(store) -> Dict[str, Any]:
    """Mutations by source, today: the rail his file drew with placeholder
    counts. These are the engine's own, counted from the ledger."""
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).date().isoformat()
    by_src: Dict[str, int] = {}
    total = 0
    for r in _l(store.get_setting(LEDGER_KEY, [])):
        r = _d(r)
        if _s(r.get("at"))[:10] == day:
            by_src[_s(r.get("source"))] = by_src.get(_s(r.get("source")), 0) + 1
            total += 1
    return {"day": day, "total": total,
            "by_source": sorted(by_src.items(), key=lambda kv: -kv[1])}


# ==========================================================================
def check() -> Dict[str, Any]:
    problems: List[str] = []
    # every kind's owner is a real roster employee
    try:
        import content_engine_roster as R
        for kind, owner in KIND_OWNER.items():
            if owner not in R.BY_ID:
                problems.append("kind %r owned by nobody on the roster (%r)"
                                % (kind, owner))
    except Exception as exc:                              # noqa: BLE001
        problems.append("could not read the roster: %s" % type(exc).__name__)

    class _Stub:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, dflt=None):
            return self.d.get(k, dflt)

        def set_setting(self, k, v):
            self.d[k] = v

    st = _Stub()
    # the four refusals actually refuse
    if record(st, source="", kind="order_sync", what="x").get("ok"):
        problems.append("a sourceless mutation was accepted")
    if record(st, source="shopify", kind="not_a_kind", what="x").get("ok"):
        problems.append("an unknown kind was accepted")
    if record(st, source="shopify", kind="credential_set",
              what="sk-abc123def456").get("ok"):
        problems.append("A CREDENTIAL VALUE REACHED THE LEDGER")
    # a good row lands and is counted today
    r = record(st, source="shopify", kind="order_sync",
               what="3 order(s) stored", entity="ws_anthropos")
    if not r.get("ok"):
        problems.append("a valid row was refused: %s" % r.get("why"))
    t = tallies(st)
    if t["total"] != 1 or t["by_source"][0][0] != "shopify":
        problems.append("tallies did not count the row just written")
    return {"ok": not problems, "problems": problems,
            "kinds": len(KIND_OWNER)}


if __name__ == "__main__":
    r = check()
    for p in r["problems"]:
        print("FAIL", p)
    print("mutation agent: %d kind(s), %s"
          % (r["kinds"], "OK" if r["ok"] else "FAILED"))
    raise SystemExit(0 if r["ok"] else 1)
