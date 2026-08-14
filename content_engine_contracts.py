# -*- coding: utf-8 -*-
"""THE SYNC CONTRACT: one place both sides read, neither side invents.

Section 2 of the build script. Every new endpoint returns these shapes
and the kit renders only these. The wireframe's mock keys ({{ n.l }})
are illustration; this module is the truth for field names (10.1).

Nothing here fetches or computes. It defines the shape and the rules
for filling it, so a screen and an endpoint cannot drift apart the way
the boards drifted from their builders.
"""
from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------------
# STAFFING: what a desk is allowed to claim about itself
# --------------------------------------------------------------------------
#: Four states, no fifth. A badge changes ONLY when the code behind it
#: changes - never to make a screen look finished (0.3).
BADGES = ("live", "inspector", "architected", "notstaffed")

BADGE_LABEL = {
    "live": "LIVE LANE",
    "inspector": "INSPECTOR ONLY",
    "architected": "ARCHITECTED",
    "notstaffed": "NOT STAFFED",
}
BADGE_MARK = {"live": "●", "inspector": "◐", "architected": "○",
              "notstaffed": "▢"}

# --------------------------------------------------------------------------
# CONNECTOR HEALTH: the anti-false-green
# --------------------------------------------------------------------------
#: verified  a real call was accepted, and we hold the timestamp
#: present   credentials exist and NOTHING has ever verified them (amber)
#: rejected  a real call was refused, with the provider's reason
#: empty     no credential at all
CONNECTOR_STATES = ("verified", "present", "rejected", "empty")


def connector_health(wire: str, *, group: str = "", status: str = "empty",
                     last_verified=None, reason: str = "",
                     aliased_from=None, shadowed=None,
                     feeds: List[str] = None) -> Dict[str, Any]:
    """One connector row. GREEN REQUIRES A TIMESTAMP: a wire cannot be
    'verified' without last_verified, because "creds are present" is the
    exact lie this whole phase exists to kill."""
    st = str(status or "empty")
    if st not in CONNECTOR_STATES:
        raise ValueError(f"{st!r} is not a connector state")
    if st == "verified" and not last_verified:
        raise ValueError("verified without last_verified is false green: "
                         "use 'present' until a real call is accepted")
    return {"wire": str(wire), "group": str(group or ""), "status": st,
            "last_verified": last_verified, "reason": str(reason or ""),
            "aliased_from": aliased_from, "shadowed": shadowed,
            "feeds": list(feeds or [])}


# --------------------------------------------------------------------------
# THE DAILY REPORT: Difference 4, the survival feature
# --------------------------------------------------------------------------
#: A "need" is one of exactly two kinds. Merging them hides outages
#: behind approvals, so the cockpit can render them as two tabs.
NEED_KINDS = ("decision", "blocked")


def need(what: str, kind: str, action: str = "", why: str = "") -> dict:
    k = str(kind)
    if k not in NEED_KINDS:
        raise ValueError(f"{k!r} is not a need kind: a broken tool is "
                         f"'blocked', a waiting approval is 'decision', "
                         f"and counting one as the other hides an outage")
    return {"what": str(what), "kind": k, "action": str(action or ""),
            "why": str(why or "")}


def daily_report(date: str, finished=None, couldnt=None, needs=None) -> dict:
    """WHAT DID YOU DO TODAY: finished, couldn't (with cause), need you.

    A couldn't WITHOUT a cause is not allowed. "It didn't work" is what
    an abandoned agent says; an employee names the wire that refused."""
    cs = []
    for c in (couldnt or []):
        c = dict(c)
        if not str(c.get("cause") or "").strip():
            raise ValueError("a couldnt must carry its cause: an "
                             "unexplained failure is how trust dies")
        cs.append(c)
    return {"date": str(date), "finished": list(finished or []),
            "couldnt": cs, "needs": list(needs or [])}


def agent_card(id: str, name: str, module: str, badge: str, *,
               autonomy: str = "", slots=None, cap_usd=None, used_usd=None,
               report=None, learned=None, log=None) -> Dict[str, Any]:
    """The acv2 card. Every desk shows one; nothing on it is hardcoded."""
    b = str(badge)
    if b not in BADGES:
        raise ValueError(f"{b!r} is not a staffing badge")
    return {
        "id": str(id), "name": str(name), "module": str(module),
        "badge": b, "badge_label": BADGE_LABEL[b], "badge_mark": BADGE_MARK[b],
        "autonomy": str(autonomy or "Propose, I approve"),
        "slots": list(slots or []),
        "cap_usd": cap_usd, "used_usd": used_usd,
        "report": report or daily_report(""),
        # AN EMPTY PLAYBOOK IS NOT SILENCE. A new employee says which day
        # of its training it is on, so "nothing learned" reads as young
        # rather than broken.
        "learned": list(learned or []),
        "log": list(log or []),
    }


def staffing(module: str, badge: str, why: str) -> Dict[str, Any]:
    b = str(badge)
    if b not in BADGES:
        raise ValueError(f"{b!r} is not a staffing badge")
    if not str(why or "").strip():
        raise ValueError("a badge must carry its reason: a badge nobody "
                         "can justify is decoration")
    return {"module": str(module), "badge": b, "badge_label": BADGE_LABEL[b],
            "badge_mark": BADGE_MARK[b], "why": str(why)}


def company_today(finished_n: int, couldnt_n: int, need_n: int,
                  top_causes=None, agents_n: int = 0) -> Dict[str, Any]:
    return {"finished_n": int(finished_n), "couldnt_n": int(couldnt_n),
            "need_n": int(need_n), "agents_n": int(agents_n),
            "top_causes": list(top_causes or [])}


if __name__ == "__main__":
    ok = connector_health("gsc", status="verified",
                          last_verified="2026-08-15T09:12:00Z")
    assert ok["status"] == "verified"
    try:
        connector_health("x", status="verified")
        raise AssertionError("green without a timestamp must be refused")
    except ValueError:
        pass
    try:
        need("a", "approval")
        raise AssertionError("only decision|blocked are need kinds")
    except ValueError:
        pass
    try:
        daily_report("d", couldnt=[{"what": "x"}])
        raise AssertionError("a couldnt needs its cause")
    except ValueError:
        pass
    c = agent_card("seo.x", "X", "seo", "inspector")
    assert c["badge_mark"] == "◐" and c["report"]["finished"] == []
    try:
        staffing("m", "live", "")
        raise AssertionError("a badge must justify itself")
    except ValueError:
        pass
    print("OK - contracts: no green without a timestamp, no cause-less "
          "failure, no invented badge, decision and blocked stay apart")
