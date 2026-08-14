# -*- coding: utf-8 -*-
"""WHAT DID YOU DO TODAY: the answer, per employee.

Difference 4, the survival feature. An agent that cannot answer this
gets abandoned, not because it was dumb but because nobody could tell
what it did.

NO NEW TRACKING. Everything here is derived from what the engine
already records: the job store (what advanced, what died and why), the
approval queue (what waits on a human), and connector health (which
tool is refusing). If it were derived from a new event stream, the
report would be one more thing that can quietly stop.

ATTRIBUTION IS PER STEP. A content piece touches five employees, so a
finished job is credited to whoever owned the step that finished, not
to the lane it happened to sit in.
"""
from __future__ import annotations

from datetime import date as _date, datetime, timezone
from typing import Any, Dict, List

import content_engine_contracts as C
import content_engine_roster as R


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _s(x) -> str:
    return "" if x is None else str(x)


def _today() -> str:
    # One definition of the company's day (C.today). This used to be the
    # LOCAL date while the workers stamped UTC, so for part of every day
    # the report and the worker were looking at different dates.
    return C.today()


def _get(store, k, d=None):
    try:
        return store.get_setting(k, d)
    except Exception:                                 # noqa: BLE001
        return d


def _jobs(store) -> List[dict]:
    try:
        return [_d(j) for j in store.list_jobs(status=None)]
    except Exception:                                 # noqa: BLE001
        return []


def _touched_today(job: dict, day: str) -> bool:
    for k in ("updated_at", "created_at", "at"):
        if _s(job.get(k))[:10] == day:
            return True
    runs = _d(job.get("_runs"))
    return any(_s(v)[:10] == day for v in runs.values())


def _steps_done(job: dict) -> List[str]:
    """Which skills actually ran on this job. _runs is stamped per skill
    by the orchestrator, so this is a fact rather than an inference."""
    return sorted(_d(job.get("_runs")).keys())


def report_today(store, agent_id: str = "", day: str = "") -> Dict[str, Any]:
    """One employee's day: FINISHED / COULDN'T (with cause) / NEED YOU."""
    day = day or _today()
    who = _s(agent_id)
    finished, couldnt, needs = [], [], []

    for job in _jobs(store):
        if not _touched_today(job, day):
            continue
        jid = _s(job.get("job_id"))
        st = _s(job.get("status"))
        mine = [sk for sk in _steps_done(job)
                if not who or R.owner_of(sk) == who]
        if mine and st not in ("failed", "halted_budget"):
            finished.append({"what": ", ".join(mine[:3])
                             + (" +%d more" % (len(mine) - 3)
                                if len(mine) > 3 else ""),
                             "job_ids": [jid]})
        # A DEATH IS ATTRIBUTED TO THE STEP THAT DIED, and it always
        # carries its cause: halt_reason is guaranteed by the engine's
        # own no-reasonless-death rule.
        if st in ("failed", "halted_budget"):
            last = (_steps_done(job) or [""])[-1]
            if not who or R.owner_of(last) == who:
                couldnt.append({
                    "what": jid,
                    "cause": (_s(job.get("halt_reason"))
                              or "no reason recorded, which is itself a bug"),
                })
        if st == "AWAITING_APPROVAL" and job.get("approved") is not True:
            owner = R.owner_of("qa_compliance")
            if not who or owner == who:
                needs.append(C.need(
                    what="approve " + jid, kind="decision",
                    action="/jobs/" + jid + "/approve",
                    why="it is written and checked; nothing publishes "
                        "until you say so"))

    # A REFUSING TOOL IS BLOCKED, NEVER A PENDING APPROVAL. Merging them
    # hides an outage inside a to-do list (Section 2's rule).
    slots = [w for _t, w in _l(R.agent(who).get("slots"))] if who else []
    try:
        import content_engine_connectors as CN
        for h in CN.health():
            if h["status"] != "rejected":
                continue
            if who and h["wire"] not in slots:
                continue
            needs.append(C.need(
                what=h["wire"] + " is refusing", kind="blocked",
                action="/connect#" + h["wire"],
                why=h.get("reason") or "the provider refused this credential"))
    except Exception:                                 # noqa: BLE001
        pass

    # LANES THAT ARE NOT JOB PIPELINES still have to answer. The
    # Integrations Engineer runs on the cadence and produces no jobs, so
    # reading only the job table would print an empty day for an employee
    # that worked - which is precisely the silence this whole phase is
    # meant to end.
    lane_day = _d(_d(_get(store, "lane_log", {})).get(day))
    mine = _d(lane_day.get(who)) if who else {}
    if not who:
        for _aid, entry in sorted(lane_day.items()):
            e = _d(entry)
            finished += _l(e.get("finished"))
            couldnt += _l(e.get("couldnt"))
            needs += _l(e.get("needs"))
    else:
        finished += _l(mine.get("finished"))
        couldnt += _l(mine.get("couldnt"))
        needs += _l(mine.get("needs"))

    return C.daily_report(day, finished=finished, couldnt=couldnt,
                          needs=needs)


def learned_lines(store, agent_id: str) -> List[str]:
    """Two or three lines from the playbook, or an honest 'day N of 30'.

    AN EMPTY PLAYBOOK IS NOT SILENCE. A new employee says which day of
    its training it is on, so nothing-learned reads as young instead of
    broken."""
    pb = {}
    try:
        import content_engine_learning as L
        import content_engine_roster as R
        # PHASE 2: this employee's OWN lane. Reading the shared playbook
        # made every card recite the writer's lessons, so an employee that
        # had learned nothing looked as experienced as one that had.
        pb = _d(L.get_playbook(_s(_get(store, "BRAND_NAME", "")) or "default",
                               R.lane_of(agent_id)))
    except Exception:                                 # noqa: BLE001
        pb = {}
    lines: List[str] = []
    for key, prefix in (("winning_topics", "winning: "),
                        ("double_down", "do more: "),
                        ("observations", "noted: "),
                        ("avoid", "avoid: ")):
        for v in _l(pb.get(key))[:2]:
            lines.append(prefix + _s(v)[:70])
    if lines:
        return lines[:3]
    started = _s(_d(_get(store, "roster_started", {})).get(_s(agent_id)))
    n = 1
    if started:
        try:
            n = max(1, (datetime.now(timezone.utc)
                        - datetime.fromisoformat(started)).days + 1)
        except Exception:                             # noqa: BLE001
            n = 1
    return ["still learning - day %d of 30" % n]


def agent_cards(store) -> List[Dict[str, Any]]:
    """Every employee, as the acv2 card. Nothing on it is hardcoded."""
    health = {}
    try:
        import content_engine_connectors as CN
        health = {h["wire"]: h for h in CN.health()}
    except Exception:                                 # noqa: BLE001
        health = {}
    caps = {}
    try:
        import content_engine_orchestrator as orch
        caps = _d(orch.budget_caps(store))
    except Exception:                                 # noqa: BLE001
        caps = {}
    spent_day = None
    try:
        spent_day = store.daily_cost()
    except Exception:                                 # noqa: BLE001
        spent_day = None

    out = []
    for r in R.roster():
        slots = []
        for tool, wire in _l(r.get("slots")):
            h = _d(health.get(wire))
            slots.append({"tool": tool, "wire": wire,
                          "status": h.get("status") or "empty",
                          "reason": h.get("reason") or ""})
        out.append(C.agent_card(
            r["id"], r["name"], r["module"], r["badge"],
            autonomy=("Propose, I approve"
                      if not _get(store, "autonomy", False)
                      else "Acts within its limits"),
            slots=slots,
            cap_usd=caps.get({"PER_DAY_BUDGET_USD": "per_day",
                              "PER_JOB_BUDGET_USD": "per_job",
                              "PER_MONTH_BUDGET_USD": "per_month"}
                             .get(r.get("cap_key"), "per_day")),
            used_usd=spent_day,
            report=report_today(store, r["id"]),
            learned=learned_lines(store, r["id"]),
            log=[]))
    return out


def company_today(store, day: str = "") -> Dict[str, Any]:
    """The cockpit rollup. It is the SUM of the cards, by construction:
    computing it separately is how a headline comes to disagree with the
    table under it."""
    cards = agent_cards(store)
    fin = sum(len(_l(_d(c.get("report")).get("finished"))) for c in cards)
    cno = sum(len(_l(_d(c.get("report")).get("couldnt"))) for c in cards)
    ned = sum(len(_l(_d(c.get("report")).get("needs"))) for c in cards)
    causes: Dict[str, int] = {}
    for c in cards:
        for x in _l(_d(c.get("report")).get("couldnt")):
            k = _s(_d(x).get("cause"))[:60]
            causes[k] = causes.get(k, 0) + 1
    top = [{"cause": k, "n": v} for k, v in
           sorted(causes.items(), key=lambda kv: -kv[1])[:3]]
    return C.company_today(fin, cno, ned, top_causes=top,
                           agents_n=len(cards))


def snapshot(store, day: str = "") -> Dict[str, Any]:
    """Write today's reports so "what did you do TUESDAY" also answers.

    IDEMPOTENT PER (agent, date) - 10.3. The scheduler has an internal
    cadence AND n8n crons hit the same routes; firing twice must write
    once, or the archive doubles every night."""
    day = day or _today()
    rows = _d(_get(store, "report_archive", {}))
    if _s(day) in rows:
        return {"ok": True, "day": day, "written": 0,
                "message": "already snapshotted today; nothing doubled"}
    rows[day] = {c["id"]: c["report"] for c in agent_cards(store)}
    keep = dict(sorted(rows.items())[-60:])
    try:
        store.set_setting("report_archive", keep)
    except Exception as exc:                          # noqa: BLE001
        return {"ok": False, "error": repr(exc)[:120]}
    return {"ok": True, "day": day, "written": len(rows[day]),
            "message": "snapshot written for %d employee(s)" % len(rows[day])}


def report_on(store, day: str, agent_id: str = "") -> Dict[str, Any]:
    """Yesterday's answer, from the archive."""
    rows = _d(_get(store, "report_archive", {}))
    d = _d(rows.get(_s(day)))
    if not d:
        return {"ok": False, "day": day,
                "error": "no snapshot exists for that day"}
    if agent_id:
        return {"ok": True, "day": day, "agent": agent_id,
                "report": _d(d.get(_s(agent_id)))}
    return {"ok": True, "day": day, "reports": d}


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d = {}
            self.j = []

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

        def list_jobs(self, status=None):
            return list(self.j)

        def daily_cost(self):
            return 1.25

    s = _S()
    today = _today()
    s.j = [
        {"job_id": "ok1", "status": "published", "updated_at": today,
         "_runs": {"content_producer": today}},
        {"job_id": "bad1", "status": "failed", "updated_at": today,
         "halt_reason": "gdrive rejected 403",
         "_runs": {"publisher": today}},
        {"job_id": "wait1", "status": "AWAITING_APPROVAL",
         "updated_at": today, "_runs": {"qa_compliance": today}},
    ]
    r = report_today(s, "mkt.producer")
    assert len(r["finished"]) == 1 and not r["couldnt"], r
    r2 = report_today(s, "mkt.distributor")
    assert len(r2["couldnt"]) == 1 and "403" in r2["couldnt"][0]["cause"]
    r3 = report_today(s, "mkt.creative_director")
    assert [n for n in r3["needs"] if n["kind"] == "decision"], r3
    ct = company_today(s)
    assert ct["finished_n"] >= 1 and ct["couldnt_n"] >= 1
    a = snapshot(s)
    b = snapshot(s)
    assert a["written"] > 0 and b["written"] == 0, (a, b)
    assert report_on(s, today)["ok"]
    ln = learned_lines(s, "mkt.producer")
    assert ln and ("still learning" in ln[0] or ":" in ln[0])
    print("OK - report: work is credited per STEP, a failure carries its "
          "cause, decisions and blockers stay apart, and a second "
          "snapshot writes nothing")
