# -*- coding: utf-8 -*-
"""THE MORNING BRIEFING: the report finally reaches the founder.

Difference 3 of the doctrine says an employee "works on a schedule and
messages you only when a human must decide". Difference 4 says it
reports what it finished, what it could not, and what it needs. This
engine has done the second since Phase 1 and never the first: the report
existed and the founder had to go and look for it.

A report nobody reads is the same as no report, and the lecture is blunt
about where that ends: nobody could tell you what it did, so you quietly
stopped trusting it. This module closes that.

WHEN IT WRITES TO YOU, AND WHEN IT STAYS QUIET
  It sends when something NEEDS A HUMAN: a decision waiting, or work
  that failed. On a day where everything ran and nothing is waiting, it
  sends nothing at all, because a daily "all fine" trains you to ignore
  the one that says otherwise. Silence is the signal that nothing needs
  you, and Monday carries a short week-in-review so silence is never
  indistinguishable from a broken cron.

THE ADDRESS IS NOT A PARAMETER
  This can only ever write to the founder's own address, read from the
  settings store. It takes no recipient from a caller, a payload or a
  URL. An engine that can email arbitrary people on a schedule is an
  outreach machine; this is a notification to the owner, and the
  difference is enforced here rather than promised in a comment.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_contracts as C

#: where the founder's address lives. Checked in this order.
ADDRESS_KEYS = ("FOUNDER_EMAIL", "OWNER_EMAIL", "DASHBOARD_EMAIL",
                "BRAND_CONTACT_EMAIL")

#: one briefing per day, whatever fires it
SENT_KEY = "briefing_sent"
#: the weekly review goes out on this weekday (0 = Monday)
REVIEW_WEEKDAY = 0


def _s(v) -> str:
    return "" if v is None else str(v)


def _d(v) -> dict:
    return dict(v) if isinstance(v, dict) else {}


def _l(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else []


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


def founder_address(store) -> str:
    """The ONE address this module may write to.

    Not a parameter anywhere in this file. A briefing that could be
    addressed by its caller is a send path, and this engine already has
    one of those with a gate on it."""
    for k in ADDRESS_KEYS:
        v = _s(_get(store, k, "")).strip()
        if "@" in v:
            return v
    return ""


# --------------------------------------------------------------------------
# WHAT TO SAY
# --------------------------------------------------------------------------
def gather(store) -> Dict[str, Any]:
    """Everything worth telling a human this morning, from the reports
    that already exist. Nothing is computed a second, different way."""
    out: Dict[str, Any] = {"decisions": [], "blocked": [], "couldnt": [],
                           "finished_n": 0, "by_agent": [], "errors": []}
    try:
        import content_engine_report as RP
        cards = RP.agent_cards(store)
    except Exception as exc:                              # noqa: BLE001
        out["errors"].append("report: %s" % type(exc).__name__)
        cards = []
    for c in cards:
        cd = _d(c)
        rep = _d(cd.get("report"))
        fin, cno = _l(rep.get("finished")), _l(rep.get("couldnt"))
        out["finished_n"] += len(fin)
        for f in cno:
            out["couldnt"].append({"who": _s(cd.get("name")),
                                   "what": _s(_d(f).get("what")),
                                   "cause": _s(_d(f).get("cause"))})
        for n in _l(rep.get("needs")):
            nd = _d(n)
            row = {"who": _s(cd.get("name")), "what": _s(nd.get("what")),
                   "why": _s(nd.get("why")), "action": _s(nd.get("action"))}
            (out["decisions"] if nd.get("kind") == "decision"
             else out["blocked"]).append(row)
        if fin or cno:
            out["by_agent"].append({"who": _s(cd.get("name")),
                                    "finished": len(fin), "couldnt": len(cno)})
    # PINK ITEMS ARE CALLED OUT SEPARATELY. A price change should not sit
    # in a list next to "approve a blog post" without being marked.
    try:
        import content_engine_pricing as PX
        for p in PX.proposals(store, "pending"):
            pd = _d(p)
            out["decisions"].append({
                "who": "📦 Commerce Analyst (pink)",
                "what": "price %s: %s to %s" % (_s(pd.get("title"))[:40],
                                                pd.get("price"),
                                                pd.get("new_price")),
                "why": _s(pd.get("why")), "action": "/commerce/prices"})
    except Exception:                                     # noqa: BLE001
        pass
    return out


def compose(store, data: Dict[str, Any], *, review: bool = False
            ) -> Dict[str, str]:
    """Subject and body. Plain text on purpose: this is a working note,
    it must be readable on a phone at 7am, and the numbers must be the
    same ones the dashboard shows."""
    d = _d(data)
    dec, blk, cno = _l(d.get("decisions")), _l(d.get("blocked")), _l(d.get("couldnt"))
    brand = _s(_get(store, "BRAND_NAME", "")) or "the engine"

    bits = []
    if dec:
        # Both branches of this were the empty string, so it always read
        # "1 need you". A subject line is the whole message for anyone
        # scanning a phone, so it is worth getting right.
        bits.append("%d %s you" % (len(dec),
                                   "needs" if len(dec) == 1 else "need"))
    if blk:
        bits.append("%d blocked" % len(blk))
    subject = "%s: %s" % (brand, ", ".join(bits) or "week in review")

    lines = ["Good morning.", ""]
    lines.append("Finished today: %d" % int(d.get("finished_n") or 0))
    lines.append("")

    if dec:
        lines.append("NEEDS YOUR DECISION (%d)" % len(dec))
        for x in dec[:10]:
            lines.append("  - %s" % _s(x.get("what")))
            if _s(x.get("why")):
                lines.append("      %s" % _s(x.get("why"))[:160])
            if _s(x.get("action")):
                lines.append("      %s" % _s(x.get("action")))
        lines.append("")
    if blk:
        # BLOCKED IS NOT AN APPROVAL LIST. Saying so in the email as well
        # as on the screen, because this is where it is easiest to
        # mistake one for the other and quietly ignore an outage.
        lines.append("BLOCKED, NOT YOURS TO APPROVE (%d)" % len(blk))
        # The first draft read "Approving nothing here will fix them",
        # which is a double negative that says the opposite. In the one
        # paragraph whose whole job is to stop an outage being mistaken
        # for a to-do, ambiguous wording is a defect.
        lines.append("  These are broken tools, not decisions.")
        lines.append("  Nothing you approve will fix them.")
        for x in blk[:10]:
            lines.append("  - %s" % _s(x.get("what")))
            if _s(x.get("why")):
                lines.append("      %s" % _s(x.get("why"))[:160])
        lines.append("")
    if cno:
        lines.append("COULD NOT (%d)" % len(cno))
        for x in cno[:10]:
            lines.append("  - %s: %s" % (_s(x.get("who")), _s(x.get("what"))))
            lines.append("      %s" % _s(x.get("cause"))[:160])
        lines.append("")
    if review:
        lines.append("WEEK IN REVIEW")
        for a in _l(d.get("by_agent"))[:20]:
            lines.append("  %-28s %d finished, %d couldn't"
                         % (_s(_d(a).get("who"))[:28], _d(a).get("finished"),
                            _d(a).get("couldnt")))
        lines.append("")
    lines.append("You are only reading this because something needs you.")
    lines.append("On a day when nothing does, nothing is sent.")
    return {"subject": subject, "body": "\n".join(lines)}


# --------------------------------------------------------------------------
# SENDING
# --------------------------------------------------------------------------
def should_send(data: Dict[str, Any], *, review: bool = False) -> bool:
    """Quiet unless a human is actually needed.

    A daily "all fine" is how a person learns to leave the message
    unread, and then misses the one that mattered."""
    d = _d(data)
    if review:
        return True
    return bool(_l(d.get("decisions")) or _l(d.get("blocked"))
                or _l(d.get("couldnt")))


def run(store, *, force: bool = False) -> Dict[str, Any]:
    """One morning. Idempotent per day: the internal cadence and an n8n
    cron may both fire it and it writes once."""
    from datetime import datetime, timezone
    day = C.today()
    sent = dict(_get(store, SENT_KEY, {}) or {})
    if not force and _s(sent.get(day)):
        return {"ok": True, "sent": False, "why": "already sent today"}

    review = datetime.now(timezone.utc).weekday() == REVIEW_WEEKDAY
    data = gather(store)
    if not should_send(data, review=review):
        # Record the quiet day too, so a silent morning cannot be
        # confused with a cron that did not run.
        sent[day] = "quiet"
        _set(store, SENT_KEY, dict(list(sent.items())[-60:]))
        return {"ok": True, "sent": False,
                "why": "nothing needed you today, so nothing was sent"}

    to = founder_address(store)
    if not to:
        return {"ok": False, "sent": False,
                "why": "no founder address is set. Add FOUNDER_EMAIL in "
                       "settings and the briefing starts arriving."}
    msg = compose(store, data, review=review)
    try:
        import content_engine_connectors as CN
        mailer = CN.Emailer()
        if not mailer.available():
            return {"ok": False, "sent": False,
                    "why": "SMTP is not configured, so the briefing cannot "
                           "be delivered. It is not lost: the same report is "
                           "on /company/today."}
        ref = mailer.send_message(to, msg["subject"], msg["body"],
                                  category="internal")
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "sent": False,
                "why": "the mail server refused: %s" % type(exc).__name__}
    sent[day] = _s(ref) or "sent"
    _set(store, SENT_KEY, dict(list(sent.items())[-60:]))
    return {"ok": True, "sent": True, "to": to, "subject": msg["subject"],
            "decisions": len(_l(data.get("decisions"))),
            "blocked": len(_l(data.get("blocked")))}


def check() -> Dict[str, Any]:
    """The rules that keep a notifier from becoming a send path."""
    import inspect
    problems = []
    for fn in (run, compose, gather):
        sig = inspect.signature(fn)
        for bad in ("to", "to_addr", "recipient", "email"):
            if bad in sig.parameters:
                problems.append("%s takes a recipient (%s); the briefing may "
                                "only ever write to the founder"
                                % (fn.__name__, bad))
    src = inspect.getsource(run)
    if "founder_address(store)" not in src:
        problems.append("run no longer resolves the address from settings")
    if "should_send" not in src:
        problems.append("run no longer checks whether anything needs a human")
    if "already sent today" not in src:
        problems.append("run is no longer idempotent per day")
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d = {"BRAND_NAME": "Anthropos", "FOUNDER_EMAIL": "a@b.com"}

        def get_setting(self, k, d=None):
            return self.d.get(k, d)

        def set_setting(self, k, v):
            self.d[k] = v

        def list_jobs(self, status=None):
            return []

        def daily_cost(self):
            return 0.0

    assert check()["ok"], check()["problems"]
    s = _S()
    print(run(s))
    data = {"finished_n": 3, "decisions": [
        {"who": "QA", "what": "approve piece 12", "why": "written and checked",
         "action": "/jobs/12/approve"}],
        "blocked": [{"who": "Publisher", "what": "gdrive is refusing",
                     "why": "403 API disabled"}], "couldnt": [], "by_agent": []}
    m = compose(s, data)
    print("\n" + m["subject"] + "\n")
    print(m["body"])
