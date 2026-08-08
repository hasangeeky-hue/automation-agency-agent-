"""
content_engine_os_schedule.py
============================================================================
WHEN AN EMAIL IS ALLOWED TO LEAVE: TIMEZONE, WINDOW, THROTTLE, RETRY.

FOUR SEPARATE QUESTIONS, ANSWERED SEPARATELY
  1. What time is it where this person is?   local_now()
  2. Is that inside the hours you send in?    in_window()
  3. Have you sent too many this hour?        throttle_room()
  4. Has this one failed, and when may it
     be tried again?                          backoff()

WHY LOCAL TIME IS NOT DECORATION
  Your five markets span nine hours. A batch released at 09:00 Munich
  reaches Vancouver at midnight, and a cold email that arrives at midnight
  is read at 08:00 under forty others. This is the difference between a
  campaign that lands and one that is technically delivered.

  Timezones are derived from the country when the profile does not carry
  one. That is an approximation for countries with several zones, and
  offset_for() says which ones are approximate rather than pretending.

RETRY IS NOT A LOOP
  A failed send waits, and waits longer each time: 5 minutes, 25, 125, then
  it stops and says why. Retrying a hard bounce forever is how a sending
  reputation dies quietly.

NO SENDING HAPPENS HERE. This module answers questions with numbers.
============================================================================
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from content_engine_os_core import _D, _L, parse_at

#: Standard offsets in hours. Deliberately winter time: a one hour error in
#: summer moves an email from 09:00 to 10:00, which is a worse outcome than
#: a table nobody maintains and everyone stops trusting.
COUNTRY_TZ = {
    "germany": ("Europe/Berlin", 1, False), "de": ("Europe/Berlin", 1, False),
    "austria": ("Europe/Vienna", 1, False),
    "switzerland": ("Europe/Zurich", 1, False),
    "ch": ("Europe/Zurich", 1, False),
    "france": ("Europe/Paris", 1, False),
    "netherlands": ("Europe/Amsterdam", 1, False),
    "uk": ("Europe/London", 0, False),
    "united kingdom": ("Europe/London", 0, False),
    "gb": ("Europe/London", 0, False),
    "ireland": ("Europe/Dublin", 0, False),
    "usa": ("America/New_York", -5, True),
    "united states": ("America/New_York", -5, True),
    "us": ("America/New_York", -5, True),
    "canada": ("America/Toronto", -5, True),
    "ca": ("America/Toronto", -5, True),
    "australia": ("Australia/Sydney", 11, True),
    "india": ("Asia/Kolkata", 5.5, False),
    "singapore": ("Asia/Singapore", 8, False),
    "uae": ("Asia/Dubai", 4, False),
}

#: The default sending window, in the RECIPIENT's local time. Business
#: hours, on business days.
DEFAULT_WINDOW = {"from_hour": 8, "to_hour": 17, "weekdays_only": True}

#: How many marketing emails may leave in one clock hour, engine wide. This
#: is separate from the daily warm-up cap: the daily cap protects the
#: domain's reputation, the hourly one stops a queue of four hundred
#: arriving as one visible burst.
DEFAULT_HOURLY = 40

WINDOW_KEY = "os_send_window"
HOURLY_KEY = "os_hourly_cap"
HOUR_COUNT_KEY = "os_sent_this_hour"

#: Retry ladder in minutes. Five attempts, then it stops.
BACKOFF_MINUTES = (5, 25, 125, 625)
MAX_ATTEMPTS = len(BACKOFF_MINUTES) + 1

#: Errors that must NEVER be retried. Trying a rejected address again is
#: how a domain earns a reputation for not listening.
PERMANENT = ("suppressed", "blocked_quality", "550", "551", "553", "554",
             "no such user", "mailbox unavailable", "does not exist",
             "invalid recipient", "unsubscribed")


def window(store) -> dict:
    try:
        w = store.get_setting(WINDOW_KEY, {}) or {}
    except Exception:
        w = {}
    out = dict(DEFAULT_WINDOW)
    out.update({k: v for k, v in _D(w).items() if k in DEFAULT_WINDOW})
    return out


def set_window(store, from_hour, to_hour, weekdays_only=True) -> dict:
    try:
        f, t = int(from_hour), int(to_hour)
    except Exception:
        return {"ok": False, "message": "the window needs two whole hours"}
    if not (0 <= f < t <= 24):
        return {"ok": False,
                "message": "the window must start before it ends, inside a "
                           "single day"}
    store.set_setting(WINDOW_KEY, {"from_hour": f, "to_hour": t,
                                   "weekdays_only": bool(weekdays_only)})
    return {"ok": True,
            "message": f"emails now leave between {f:02d}:00 and {t:02d}:00 "
                       f"in the RECIPIENT's local time"
                       + (", weekdays only" if weekdays_only else "")}


def hourly_cap(store) -> int:
    try:
        return max(1, int(store.get_setting(HOURLY_KEY, DEFAULT_HOURLY)
                          or DEFAULT_HOURLY))
    except Exception:
        return DEFAULT_HOURLY


def set_hourly_cap(store, n) -> dict:
    try:
        n = int(n)
    except Exception:
        return {"ok": False, "message": "that is not a number"}
    if not (1 <= n <= 1000):
        return {"ok": False, "message": "pick between 1 and 1000 an hour"}
    store.set_setting(HOURLY_KEY, n)
    return {"ok": True, "message": f"at most {n} email(s) leave in any hour"}


# ---------------------------------------------------------------------------
def offset_for(person) -> tuple:
    """(hours, zone_name, approximate). A profile's own timezone wins; the
    country is the fallback; UTC is the last resort and is reported as an
    approximation rather than a fact."""
    person = _D(person)
    tz = str(person.get("timezone") or "").strip()
    if tz:
        for _k, (name, off, approx) in COUNTRY_TZ.items():
            if name.lower() == tz.lower():
                return off, name, approx
    c = str(person.get("country") or "").strip().lower()
    hit = COUNTRY_TZ.get(c)
    if hit:
        return hit[1], hit[0], hit[2]
    return 0, "UTC", True


def local_now(person, at=None):
    off, name, approx = offset_for(person)
    base = at or datetime.now(timezone.utc)
    return base + timedelta(hours=off), name, approx


def in_window(person, win, at=None) -> tuple:
    """(bool, why). The why is shown on the queue row, because "held" with
    no reason is the same as broken."""
    local, name, approx = local_now(person, at)
    if win.get("weekdays_only") and local.weekday() >= 5:
        return False, (f"it is the weekend in {name}"
                       + (" (approximate)" if approx else ""))
    h = local.hour
    if not (int(win.get("from_hour", 8)) <= h < int(win.get("to_hour", 17))):
        return False, (f"it is {local:%H:%M} in {name}, outside "
                       f"{int(win.get('from_hour', 8)):02d}:00 to "
                       f"{int(win.get('to_hour', 17)):02d}:00"
                       + (" (approximate)" if approx else ""))
    return True, f"{local:%H:%M} in {name}"


def next_open(person, win, at=None) -> str:
    """When this person's window next opens, as an ISO stamp in UTC."""
    off, _n, _a = offset_for(person)
    base = at or datetime.now(timezone.utc)
    local = base + timedelta(hours=off)
    for _ in range(14):
        start = local.replace(hour=int(win.get("from_hour", 8)), minute=0,
                              second=0, microsecond=0)
        if start > local and not (win.get("weekdays_only")
                                  and start.weekday() >= 5):
            return (start - timedelta(hours=off)).isoformat(timespec="seconds")
        local = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0,
                                                    microsecond=0)
    return base.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
def _hour_key(at=None) -> str:
    return (at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H")


def throttle_room(store) -> tuple:
    """(room_left, why). Counted per clock hour, reset by the key changing
    rather than by a timer nobody can see."""
    cap = hourly_cap(store)
    try:
        rec = store.get_setting(HOUR_COUNT_KEY, {}) or {}
    except Exception:
        rec = {}
    used = int(_D(rec).get("n", 0)) if _D(rec).get("hour") == _hour_key() else 0
    return max(0, cap - used), f"{used} of {cap} sent this hour"


def note_sent(store, n=1) -> None:
    try:
        rec = store.get_setting(HOUR_COUNT_KEY, {}) or {}
    except Exception:
        rec = {}
    k = _hour_key()
    used = int(_D(rec).get("n", 0)) if _D(rec).get("hour") == k else 0
    store.set_setting(HOUR_COUNT_KEY, {"hour": k, "n": used + int(n)})


# ---------------------------------------------------------------------------
def is_permanent(error) -> bool:
    e = str(error or "").lower()
    return any(p in e for p in PERMANENT)


def backoff(attempts, error="") -> dict:
    """{retry, next_attempt_at, why}. The only place the ladder exists."""
    n = int(attempts or 0)
    if is_permanent(error):
        return {"retry": False, "next_attempt_at": "",
                "why": "that address refused permanently, so it will not be "
                       "tried again"}
    if n >= MAX_ATTEMPTS:
        return {"retry": False, "next_attempt_at": "",
                "why": f"{n} attempts have failed; this one stops here rather "
                       f"than retrying forever"}
    mins = BACKOFF_MINUTES[min(n - 1, len(BACKOFF_MINUTES) - 1)] if n else 5
    when = datetime.now(timezone.utc) + timedelta(minutes=mins)
    return {"retry": True,
            "next_attempt_at": when.isoformat(timespec="seconds"),
            "why": f"attempt {n} failed; the next one is in {mins} minute(s)"}


def due(job, at=None) -> bool:
    """Is this queued row allowed to be picked up yet."""
    nxt = parse_at(_D(job).get("next_attempt_at"))
    sched = parse_at(_D(job).get("scheduled_at"))
    base = at or datetime.now(timezone.utc)
    if nxt and nxt > base:
        return False
    if sched and sched > base:
        return False
    return True


def describe(store) -> dict:
    """What the Sending settings screen draws."""
    w = window(store)
    room, why = throttle_room(store)
    return {"window": w, "hourly_cap": hourly_cap(store), "room": room,
            "why": why,
            "zones": sorted({v[0] for v in COUNTRY_TZ.values()}),
            "ladder": ", ".join(f"{m}m" for m in BACKOFF_MINUTES),
            "max_attempts": MAX_ATTEMPTS}
