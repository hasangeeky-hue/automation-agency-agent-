# -*- coding: utf-8 -*-
"""LANE 3a - THE INTEGRATIONS ENGINEER (system.integrations).

Phase 0 gave the engine honest connector health. Health is a READING;
nobody was employed to act on it. This module is the employee: it looks
at the wires every day, remembers which ones misbehave, and puts a named
fix in front of a person.

The six rungs, in order (Section 4.1):

  CONTEXT     connector health rows + the alias and shadow maps, re-read
              on every run. It never caches a verdict between runs.
  MEMORY      the 'system' learning lane. Which wires flap, and which
              fix actually cleared one.
  LANE        find configuration faults: newly rejected, stale green,
              shadowed keys, half-configured groups.
  TOOLS       the health store and the settings reader. Nothing else.
  SCHEDULE    daily, on the cadence.
  GUARDRAILS  it proposes. It never writes a credential, never re-auths,
              never calls a paid endpoint.
  REPORT      it answers "what did you do today" like everyone else.

THE LINE THIS LANE WILL NOT CROSS
---------------------------------
A free self-test cannot prove a remote credential works; only a real
call can, and real calls cost money and are the other lanes' job. So
this employee is allowed to find faults and is NOT allowed to mark
anything verified. If it could, Phase 0's whole guarantee would be
undone by the very worker built to protect it: a green light would once
again mean "we looked at our own config" rather than "they accepted us".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import content_engine_contracts as C

AGENT_ID = "system.integrations"
LANE = "system"

#: a wire verified longer ago than this is not trusted as current
STALE_DAYS = 14

#: where its own day is written, so the daily report can read it back
LANE_LOG_KEY = "lane_log"

#: its proposals. Separate from the content rewrite queue on purpose: a
#: credential fix is not a piece of writing and must not sit in a list
#: the founder skims for editorial approval.
PROPOSALS_KEY = "integration_proposals"

#: wires that only work as a set. Half a group configured is the fault
#: that looks like a working integration right up until it runs.
#: These names were READ from health(), not guessed. The first draft of
#: this table said ("gsc", "ga4") - wires that do not exist - and would
#: have reported nothing forever while looking like a working check.
GROUPS_ALL_OR_NOTHING = {
    "the email round trip": ("email_send", "email_reply_inbound"),
    "google ads": ("ads_api", "ads_data"),
}


def check() -> Dict[str, Any]:
    """Every wire this module names must be a wire that exists. A check
    that watches a misspelled wire reports 'all clear' forever."""
    problems = []
    try:
        import content_engine_connectors as CN
        known = {r["wire"] for r in CN.health()}
        for group, members in GROUPS_ALL_OR_NOTHING.items():
            for m in members:
                if m not in known:
                    problems.append("%s: '%s' is not a real wire" % (group, m))
    except Exception as exc:                              # noqa: BLE001
        problems.append("could not read the wires: %s" % type(exc).__name__)
    return {"ok": not problems, "problems": problems}

_SEEN_KEY = "integration_last_seen"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _s(v) -> str:
    return "" if v is None else str(v)


def _get(store, k, d=None):
    try:
        return store.get_setting(k, d)
    except Exception:                                     # noqa: BLE001
        return d


def _set(store, k, v) -> bool:
    try:
        store.set_setting(k, v)
        return True
    except Exception:                                     # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# RUNG 1 - CONTEXT: what it reads, every single run
# --------------------------------------------------------------------------
def context(store=None) -> Dict[str, Any]:
    """The desk it sits at. Named as a function so the context is a fact
    that can be inspected and tested, not an assumption buried in a loop."""
    rows, alias, shadow = [], {}, {}
    try:
        import content_engine_connectors as CN
        rows = [dict(r) for r in CN.health()]
        alias = dict(CN.aliased() or {})
        shadow = dict(CN.shadowed() or {})
    except Exception:                                     # noqa: BLE001
        pass
    return {"health": rows, "aliased": alias, "shadowed": shadow,
            "read_at": _now().isoformat()}


# --------------------------------------------------------------------------
# RUNG 3 - THE LANE: four free checks, each of which can only find a fault
# --------------------------------------------------------------------------
def _newly_rejected(ctx: Dict[str, Any], last: Dict[str, str]) -> List[dict]:
    """A wire that was fine yesterday and is refusing today. This is the
    finding that matters most, because it is the one nobody notices: the
    engine keeps running and one lane quietly stops producing."""
    out = []
    for r in ctx["health"]:
        if r.get("status") != "rejected":
            continue
        was = last.get(r["wire"])
        if was and was != "rejected":
            out.append({
                "wire": r["wire"], "kind": "newly_rejected",
                "what": "%s started refusing (it was %s)" % (r["wire"], was),
                "cause": _s(r.get("reason")) or "the provider refused",
                "fix": "re-authorise %s in Connections" % r["wire"],
            })
    return out


def _stale_green(ctx: Dict[str, Any], at: datetime) -> List[dict]:
    """Verified, but so long ago that the word has stopped meaning
    anything. Reported as a fault to look at, never downgraded silently:
    changing a state the founder can see, without saying so, is how a
    board loses its credibility."""
    out = []
    cutoff = at - timedelta(days=STALE_DAYS)
    for r in ctx["health"]:
        if r.get("status") != "verified":
            continue
        stamp = _s(r.get("last_verified"))
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except Exception:                                 # noqa: BLE001
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when < cutoff:
            days = max(0, (at - when).days)
            out.append({
                "wire": r["wire"], "kind": "stale",
                "what": "%s has not been exercised in %d days" % (r["wire"], days),
                "cause": "last accepted call was %s" % stamp[:10],
                "fix": "no action needed unless its lane is idle; the next "
                       "real call re-stamps it",
            })
    return out


def _shadowed_keys(ctx: Dict[str, Any]) -> List[dict]:
    """The cruellest class: the founder edits a key, saves it, sees it
    saved, and the engine keeps using a different value. Nothing looks
    broken from either end."""
    out = []
    for field, why in sorted(ctx["shadowed"].items()):
        out.append({
            "wire": field, "kind": "shadowed",
            "what": "%s is saved but NOT the value being used" % field,
            "cause": _s(why) or "a stored value was ignored in favour of "
                                "the environment",
            "fix": "fix the saved value in Connections, or remove the "
                   "environment copy; the edit you make now has no effect",
        })
    for field, twin in sorted(ctx["aliased"].items()):
        out.append({
            "wire": field, "kind": "aliased",
            "what": "%s is running on %s, not on its own key" % (field, twin),
            "cause": "resolved from a differently-named twin",
            "fix": "harmless, but %s will not do what you expect if you "
                   "change it" % field,
        })
    return out


def _half_configured(ctx: Dict[str, Any]) -> List[dict]:
    """Groups that only work whole."""
    by_wire = {r["wire"]: r for r in ctx["health"]}
    out = []
    for group, members in sorted(GROUPS_ALL_OR_NOTHING.items()):
        have = [m for m in members
                if _s(by_wire.get(m, {}).get("status")) in ("verified", "present")]
        if have and len(have) != len(members):
            miss = [m for m in members if m not in have]
            out.append({
                "wire": group, "kind": "half_configured",
                "what": "%s is half configured: %s set, %s missing"
                        % (group, ", ".join(have), ", ".join(miss)),
                "cause": "the group only works as a set",
                "fix": "add %s, or the wires you did configure earn nothing"
                       % ", ".join(miss),
            })
    return out


def self_tests(store, at: datetime = None) -> Dict[str, Any]:
    """The whole free battery. Returns findings; writes nothing."""
    at = at or _now()
    ctx = context(store)
    last = dict(_get(store, _SEEN_KEY, {}) or {})
    findings = (_newly_rejected(ctx, last)
                + _shadowed_keys(ctx)
                + _half_configured(ctx)
                + _stale_green(ctx, at))
    return {"at": at.isoformat(), "checked": len(ctx["health"]),
            "findings": findings,
            "state": {r["wire"]: _s(r.get("status")) for r in ctx["health"]}}


# --------------------------------------------------------------------------
# RUNG 6 - GUARDRAILS: it proposes, a person decides
# --------------------------------------------------------------------------
def _propose(store, findings: List[dict], at: datetime) -> List[dict]:
    """One open proposal per (wire, kind). Resolved ones are dropped, so a
    wire that breaks again next month gets asked about again - the content
    queue's one-ever rule would silence exactly the repeat offender this
    lane exists to catch."""
    live = {(f["wire"], f["kind"]) for f in findings
            if f["kind"] in ("newly_rejected", "shadowed", "half_configured")}
    keep, seen = [], set()
    for p in list(_get(store, PROPOSALS_KEY, []) or []):
        if not isinstance(p, dict):
            continue
        key = (_s(p.get("wire")), _s(p.get("kind")))
        if key in live and key not in seen:
            seen.add(key)
            keep.append(p)                    # still true: leave it standing
    for f in findings:
        key = (f["wire"], f["kind"])
        if key not in live or key in seen:
            continue
        seen.add(key)
        keep.append({"wire": f["wire"], "kind": f["kind"], "what": f["what"],
                     "cause": f["cause"], "fix": f["fix"],
                     "at": at.isoformat(), "status": "pending",
                     "action": "/connect#" + f["wire"]})
    _set(store, PROPOSALS_KEY, keep[-50:])
    return keep


def proposals(store) -> List[dict]:
    return [p for p in (_get(store, PROPOSALS_KEY, []) or [])
            if isinstance(p, dict)]


# --------------------------------------------------------------------------
# RUNG 7 - THE REPORT: it answers the question every employee answers
# --------------------------------------------------------------------------
def _log_day(store, day: str, finished: List[dict], couldnt: List[dict],
             needs: List[dict]) -> None:
    log = dict(_get(store, LANE_LOG_KEY, {}) or {})
    per_day = dict(log.get(day) or {})
    per_day[AGENT_ID] = {"finished": finished, "couldnt": couldnt,
                         "needs": needs}
    log[day] = per_day
    for old in sorted(log)[:-14]:                 # a fortnight is plenty
        log.pop(old, None)
    _set(store, LANE_LOG_KEY, log)


def run(store, at: datetime = None) -> Dict[str, Any]:
    """One working day for the Integrations Engineer."""
    at = at or _now()
    day = C.today()          # the company's day, not this process's clock
    # yesterday's picture, read BEFORE this run overwrites it: without it
    # "which fix actually worked" is unanswerable, and that memory is the
    # only reason this lane is an employee rather than a status page.
    prev = dict(_get(store, _SEEN_KEY, {}) or {})
    res = self_tests(store, at)
    findings = res["findings"]
    props = _propose(store, findings, at)

    finished = [{"what": "checked %d wires, found %d fault(s)"
                         % (res["checked"], len(findings)),
                 "job_ids": []}]
    couldnt: List[dict] = []
    if not res["checked"]:
        couldnt = [{"what": "the daily wire check",
                    "cause": "the connector health store returned nothing, so "
                             "this run proved nothing"}]
        finished = []

    # A wire the founder must re-authorise is a DECISION. A wire that is
    # simply refusing is BLOCKED. Phase 1's rule, applied to its own lane.
    needs = [C.need(what=p["what"], kind="decision", action=p["action"],
                    why=p["fix"]) for p in props]
    _log_day(store, day, finished, couldnt, needs)
    _set(store, _SEEN_KEY, res["state"])

    # RUNG 2 - MEMORY. Only real observations are recorded; a quiet day
    # teaches nothing and must not be counted as a cycle.
    learned = ["%s: %s" % (f["kind"], f["what"]) for f in findings[:5]]
    cleared = [w for w, st in res["state"].items()
               if st == "verified" and _s(prev.get(w)) == "rejected"]
    if cleared:
        learned.append("cleared after a fix: " + ", ".join(sorted(cleared)[:3]))
    if learned:
        try:
            import content_engine_learning as L
            L.record_lane_cycle(_s(_get(store, "BRAND_NAME", "")) or "default",
                                LANE, learned=learned, at=at.isoformat())
        except Exception:                                 # noqa: BLE001
            pass

    return {"agent": AGENT_ID, "day": day, "checked": res["checked"],
            "findings": findings, "proposals": props,
            "report": C.daily_report(day, finished=finished, couldnt=couldnt,
                                     needs=needs)}


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, d=None):
            return self.d.get(k, d)

        def set_setting(self, k, v):
            self.d[k] = v

    s = _S()
    out = run(s)
    print("checked", out["checked"], "findings", len(out["findings"]))
    for f in out["findings"][:5]:
        print(" -", f["kind"], "|", f["what"])
