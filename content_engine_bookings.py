# -*- coding: utf-8 -*-
"""BOOKINGS: pipeline for a business that sells projects, not products.

Stage 2, second collector. The orders collector answers "what did the
shop sell". This one answers the question that actually applies to
Anthropos, which sells consulting: who booked time, and what came of it.

THE ONE RULE THIS MODULE EXISTS TO HOLD:

    A BOOKING IS NOT A SALE.

Cal.com knows a call was booked. It does not know whether the project
closed or what it was worth. The tempting move is to project bookings
into deals so the revenue screens light up, and it would be wrong twice
over: bi.revenue() coerces a missing value to 0.0, so every booking
would become a zero-value deal, inflating the deal count while dragging
avg_deal toward zero. The screens would look alive and read false.

So bookings stay pipeline until a human attaches a number. win() is that
step: it takes a value AND a named approver, and only then does a
booking become revenue. That is the same shape as every other write in
this engine, and for the same reason: the engine can observe, but only a
person can assert what a project was worth.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import content_engine_bi as BI

log = logging.getLogger("bookings")

BOOKINGS_KEY = "bookings_rows"
WON_KEY = "bookings_won"
COLLECT_KEY = "bookings_last_collect"
MAX_BOOKINGS = 1000

#: Cal.com's words for what happened to a booking. Grouped by what they
#: mean for pipeline, because "cancelled" and "pending" are both
#: not-accepted and are not remotely the same news.
ACCEPTED = ("accepted", "confirmed")
DEAD = ("cancelled", "rejected", "declined")


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _s(x) -> str:
    return "" if x is None else str(x)


def _money(x):
    """Missing stays missing. The whole point of this module."""
    if x in (None, ""):
        return None
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def _get(store, key, default):
    try:
        return store.get_setting(key, default)
    except Exception:                                     # noqa: BLE001
        return default


def _set(store, key, value):
    try:
        store.set_setting(key, value)
        return True
    except Exception as e:                                # noqa: BLE001
        log.warning("bookings: could not save %s: %s", key, e)
        return False


# ---------------------------------------------------------------- fetch
def fetch(store=None) -> Dict[str, Any]:
    """Read booked consultations from Cal.com. READ ONLY.

    count is None when the wire could not be read and an integer when it
    could, so an empty calendar never reads as a broken one."""
    try:
        import content_engine_connectors as CN
        c = CN.CalCom()
        if not c.available():
            return {"ok": False, "bookings": [], "count": None,
                    "why": ("CALCOM_API_KEY is not set, so no booking was "
                            "read. Cal.com, Settings, Developer, API keys.")}
        raw = c.bookings()
    except Exception as e:                                # noqa: BLE001
        log.warning("booking fetch failed: %s", e)
        return {"ok": False, "bookings": [], "count": None,
                "why": "Cal.com could not be reached: %s" % str(e)[:120]}
    rows = [normalise(b) for b in map(_d, _l(raw))]
    return {"ok": True, "bookings": rows, "count": len(rows),
            "why": ("Cal.com answered and there are no bookings yet"
                    if not rows else "")}


def normalise(raw: dict) -> Dict[str, Any]:
    """One Cal.com booking, in this engine's words."""
    raw = _d(raw)
    att = _d((_l(raw.get("attendees")) or [{}])[0])
    status = _s(raw.get("status")).lower()
    return {"id": _s(raw.get("uid") or raw.get("id")),
            "at": _s(raw.get("start") or raw.get("startTime"))[:10],
            "title": _s(raw.get("title")),
            "client": (_s(att.get("name")) or _s(att.get("email"))
                       or "unnamed")[:80],
            "email": _s(att.get("email")),
            "status": status,
            "accepted": status in ACCEPTED,
            "dead": status in DEAD}


# ---------------------------------------------------------------- store
def save(store, bookings) -> Dict[str, Any]:
    have = {_s(_d(b).get("id")): _d(b)
            for b in _l(_get(store, BOOKINGS_KEY, []))}
    added, updated = 0, 0
    for b in _l(bookings):
        bid = _s(_d(b).get("id"))
        if not bid:
            continue
        if bid in have:
            updated += 1
        else:
            added += 1
        have[bid] = _d(b)
    rows = sorted(have.values(), key=lambda b: _s(b.get("at")), reverse=True)
    rows = rows[:MAX_BOOKINGS]
    _set(store, BOOKINGS_KEY, rows)
    # the mutation ledger (16b), best-effort, only when something changed
    if added or updated:
        try:
            import content_engine_mutation as MU
            MU.route_and_record(
                store, platform="calcom", kind="booking_sync",
                what="%d booking(s) added, %d updated" % (added, updated))
        except Exception:                                 # noqa: BLE001
            pass
    return {"stored": len(rows), "added": added, "updated": updated}


def list_bookings(store) -> List[dict]:
    return [_d(b) for b in _l(_get(store, BOOKINGS_KEY, []))]


def won_index(store) -> Dict[str, dict]:
    """booking id -> the won record a human attached to it."""
    return {_s(k): _d(v) for k, v in _d(_get(store, WON_KEY, {})).items()}


# ------------------------------------------------------------- pipeline
def pipeline(bookings, won=None) -> Dict[str, Any]:
    """Where the booked work stands. Counts only, never money.

    `unconverted` is the number a founder should look at: calls that
    happened and were never marked won or lost. It is not a failure, it
    is a queue, and nothing else in the engine was counting it."""
    won = won or {}
    accepted, dead, pending, converted = 0, 0, 0, 0
    for b in map(_d, _l(bookings)):
        if _s(b.get("id")) in won:
            converted += 1
        elif b.get("dead"):
            dead += 1
        elif b.get("accepted"):
            accepted += 1
        else:
            pending += 1
    return {"total": len(_l(bookings)), "accepted": accepted,
            "cancelled": dead, "pending": pending, "converted": converted,
            "unconverted": accepted,
            # A conversion RATE needs a denominator. With no accepted
            # bookings it is None, never 0.0, because "none booked" and
            # "none of them converted" are different news.
            "conversion_rate": (round(100.0 * converted / (converted + accepted), 1)
                                if (converted + accepted) else None)}


# ------------------------------------------------------ the human step
def win(store, booking_id: str, value, *, approved_by: str = "",
        source: str = "direct") -> Dict[str, Any]:
    """Record that a booking became a paid project. NEEDS A NAMED HUMAN.

    This is the only path from booking to revenue, and it is deliberately
    manual. The engine can see that a call happened; only a person knows
    what was agreed. Inventing that number would put a figure on the
    revenue screen that nobody ever agreed to.
    """
    if not _s(approved_by).strip():
        return {"ok": False, "why": ("recording revenue needs a named human: "
                                     "the engine cannot know what a project "
                                     "was worth")}
    bid = _s(booking_id)
    book = next((b for b in list_bookings(store) if _s(b.get("id")) == bid), None)
    if not book:
        return {"ok": False, "why": "no such booking"}
    val = _money(value)
    if val is None or val <= 0:
        # A won deal with no value is not a won deal, it is a note. Let
        # it through and bi.revenue() would count a zero.
        return {"ok": False, "why": ("a won project needs a real value; "
                                     "'none' and 'zero' are not the same "
                                     "and neither belongs in revenue")}
    src = _s(source).lower()
    if src not in BI.SOURCES:
        # Same shared-vocabulary trap as the orders collector: BI coerces
        # an unknown source to "other" without raising.
        return {"ok": False, "why": ("'%s' is not a source BI knows. One of: "
                                     "%s" % (src, ", ".join(BI.SOURCES)))}
    won = won_index(store)
    if bid in won:
        return {"ok": False, "why": "this booking is already recorded as won"}
    from datetime import datetime, timezone
    won[bid] = {"value": val, "source": src, "approved_by": _s(approved_by),
                "at": _s(book.get("at")),
                "recorded_at": datetime.now(timezone.utc)
                .isoformat(timespec="seconds")}
    _set(store, WON_KEY, won)
    _sync_deals(store)
    return {"ok": True, "booking_id": bid, "value": val, "source": src,
            "approved_by": _s(approved_by),
            "note": "recorded as revenue and written to the BI deals feed"}


def to_deals(store) -> List[dict]:
    """Only WON bookings become deals. Pipeline never does."""
    won = won_index(store)
    books = {_s(b.get("id")): b for b in list_bookings(store)}
    out = []
    seen: Dict[str, int] = {}
    for bid, w in won.items():
        b = _d(books.get(bid))
        key = _s(b.get("email") or b.get("client")).lower()
        seen[key] = seen.get(key, 0) + 1
    for bid, w in won.items():
        b = _d(books.get(bid))
        key = _s(b.get("email") or b.get("client")).lower()
        out.append({"id": "book-" + bid,
                    "client": _s(b.get("client")) or "unnamed",
                    "value": _money(w.get("value")),
                    "at": _s(w.get("at") or b.get("at")),
                    "source": _s(w.get("source")) or "direct",
                    "recurring": seen.get(key, 0) > 1})
    return out


def _sync_deals(store) -> int:
    """Merge booking deals into the BI feed WITHOUT clobbering order deals.

    The orders collector also writes here. Whoever writes last must not
    erase the other, so each owner replaces only the rows carrying its
    own id prefix. Replacing the whole key, which is what a naive write
    would do, would make revenue swing depending on which collector ran
    most recently."""
    mine = to_deals(store)
    keep = [d for d in _l(_get(store, BI.DEALS_KEY, []))
            if not _s(_d(d).get("id")).startswith("book-")]
    merged = (keep + mine)[:BI.MAX_DEALS]
    _set(store, BI.DEALS_KEY, merged)
    return len(mine)


# ------------------------------------------------------------------ day
def run(store) -> Dict[str, Any]:
    """The collector's working day: read Cal.com, store, count pipeline."""
    from datetime import datetime, timezone
    got = fetch(store)
    if not got.get("ok"):
        return {"ok": False, "why": got.get("why"), "total": 0}
    saved = save(store, got["bookings"])
    books = list_bookings(store)
    pipe = pipeline(books, won_index(store))
    written = _sync_deals(store)
    _set(store, COLLECT_KEY,
         datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return {"ok": True, **saved, **pipe, "deals_written": written,
            "note": ("%d accepted booking(s) are not yet marked won or lost. "
                     "The engine cannot value them; that is your call."
                     % pipe["accepted"]) if pipe["accepted"] else
                    "no accepted booking is waiting on a decision"}


def context(store) -> Dict[str, Any]:
    """What the screens read. No calls, so it is free to render."""
    books = list_bookings(store)
    won = won_index(store)
    return {"connected": bool(books) or bool(_get(store, COLLECT_KEY, "")),
            "last_collect": _s(_get(store, COLLECT_KEY, "")),
            "bookings": books, "won": won,
            **pipeline(books, won)}


# ---------------------------------------------------------------- check
def check() -> Dict[str, Any]:
    out = []

    # THE RULE THIS MODULE EXISTS FOR.
    r = win(None, "x", 500, approved_by="")
    out.append(("revenue cannot be recorded without a named human",
                not r["ok"] and "named human" in r["why"], r.get("why")))

    out.append(("a missing value stays missing", _money(None) is None))

    # A booking with no money attached must never reach the deals feed,
    # because bi.revenue() would read it as a zero-value deal.
    out.append(("a booking is not a deal until a human values it",
                to_deals(_FakeStore({BOOKINGS_KEY: [{"id": "b1",
                                                     "client": "A"}],
                                     WON_KEY: {}})) == [], ""))

    # A rate with no denominator is None, not 0.
    out.append(("a conversion rate over no bookings is None, not 0.0",
                pipeline([])["conversion_rate"] is None, ""))

    # The shared vocabulary, again. BI silently coerces, so this refuses.
    st = _FakeStore({BOOKINGS_KEY: [{"id": "b1", "client": "A", "at": "2026-08-01"}],
                     WON_KEY: {}})
    bad = win(st, "b1", 500, approved_by="H", source="linkedin")
    out.append(("a source BI does not know is refused, not coerced",
                not bad["ok"] and "BI knows" in bad["why"], bad.get("why")))

    good = win(st, "b1", 500, approved_by="Founder", source="referral")
    out.append(("a valued, sourced, approved booking becomes revenue",
                good["ok"], good.get("why")))
    out.append(("and it cannot be recorded twice",
                not win(st, "b1", 500, approved_by="Founder")["ok"], ""))
    out.append(("a won project with no value is refused",
                not win(st, "b1", 0, approved_by="Founder")["ok"], ""))

    # THE COLLISION. Both collectors write BI.DEALS_KEY.
    st2 = _FakeStore({BI.DEALS_KEY: [{"id": "ord-1", "client": "Shop",
                                      "value": 10.0}],
                      BOOKINGS_KEY: [{"id": "b9", "client": "B",
                                      "at": "2026-08-02"}],
                      WON_KEY: {}})
    win(st2, "b9", 900, approved_by="Founder", source="referral")
    ids = [d["id"] for d in st2.data[BI.DEALS_KEY]]
    out.append(("BOOKINGS DO NOT ERASE THE ORDER DEALS SHARING THE FEED",
                "ord-1" in ids and "book-b9" in ids, ids))

    return {"ok": all(p for _n, p, *_x in out),
            "checks": [{"name": n, "pass": p,
                        "detail": (d[0] if d else "")}
                       for n, p, *d in out]}


class _FakeStore:
    """A settings store in memory, so check() can prove behaviour without
    a database. Tests that need infrastructure do not get run."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def get_setting(self, k, default=None):
        return self.data.get(k, default)

    def set_setting(self, k, v):
        self.data[k] = v


if __name__ == "__main__":
    r = check()
    for c in r["checks"]:
        print(("  OK   " if c["pass"] else "  FAIL ") + c["name"]
              + (("   " + str(c["detail"])[:120]) if c["detail"]
                 and not c["pass"] else ""))
    print("bookings self-check:", "OK" if r["ok"] else "FAILED")
    raise SystemExit(0 if r["ok"] else 1)
