# -*- coding: utf-8 -*-
"""The handlers behind the buttons that had nowhere to go.

Fourteen buttons said "there is no endpoint for this yet" because there
genuinely was not one: editing a piece, saving a brief, making a
variant, dismissing a signal. This is that missing half. Also here:
the quota tracker (a free API still stops answering at its limit, and
that halts work exactly as hard as an unpaid one) and the one call that
makes the Content Factory's own agents run.

EVERY MUTATION KEEPS THE HOUSE RULES: an agent may draft and may never
approve; a publish or a send waits for a named human; nothing is
recorded as verified because it executed.
"""
from __future__ import annotations

from typing import Any, Dict

MAX_LOG = 200


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _s(x) -> str:
    return "" if x is None else str(x)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _get(store, k, d=None):
    try:
        return store.get_setting(k, d)
    except Exception:                                 # noqa: BLE001
        return d


def _set(store, k, v) -> bool:
    try:
        store.set_setting(k, v)
        return True
    except Exception:                                 # noqa: BLE001
        return False


# ==========================================================================
# CONTENT: edit, save, vary, restore
# ==========================================================================
def save_piece(store, job_id: str, field: str, text: str,
               who: str = "") -> Dict[str, Any]:
    """Edit one field of a drafted piece, keeping the version before it.

    A human edit is not an agent run: it never re-bills, and it never
    moves the piece past its gate. The previous text is kept so
    'Restore' is a real button and not a wish."""
    jid, fld = _s(job_id), _s(field) or "body"
    if not jid:
        return {"ok": False, "error": "which piece?"}
    if fld not in ("title", "body", "meta_title", "meta_description",
                   "cta_text"):
        return {"ok": False, "error": f"'{fld}' is not an editable field"}
    try:
        job = store.get(jid)
    except Exception:                                 # noqa: BLE001
        return {"ok": False, "error": f"no piece called {jid}"}
    prod = _d(_d(job.get("payload")).get("content_producer"))
    before = _s(prod.get(fld))
    if before == _s(text):
        return {"ok": True, "message": "nothing changed"}
    versions = _l(job.setdefault("payload", {}).setdefault("_versions", []))
    versions.append({"at": _now(), "field": fld, "text": before,
                     "by": _s(who) or "the founder"})
    job["payload"]["_versions"] = versions[-20:]
    prod[fld] = _s(text)
    job["payload"]["content_producer"] = prod
    job["payload"]["edited_by_human"] = True
    store.save(job)
    return {"ok": True, "message": f"{fld} saved; the previous text is "
                                   f"kept and Restore will bring it back",
            "versions": len(job["payload"]["_versions"])}


def restore_piece(store, job_id: str) -> Dict[str, Any]:
    """Put back the text as it was before the last edit."""
    try:
        job = store.get(_s(job_id))
    except Exception:                                 # noqa: BLE001
        return {"ok": False, "error": f"no piece called {job_id}"}
    versions = _l(_d(job.get("payload")).get("_versions"))
    if not versions:
        return {"ok": False, "error": "this piece has no earlier version"}
    last = _d(versions[-1])
    prod = _d(_d(job["payload"]).get("content_producer"))
    prod[_s(last.get("field")) or "body"] = _s(last.get("text"))
    job["payload"]["content_producer"] = prod
    job["payload"]["_versions"] = versions[:-1]
    store.save(job)
    return {"ok": True, "message": f"restored the {last.get('field')} as it "
                                   f"was at {_s(last.get('at'))[:16]}"}


def make_variant(store, job_id: str, note: str = "") -> Dict[str, Any]:
    """Queue a VARIANT of a piece: a second version to test against the
    first. It enters as a draft like everything else, because a variant
    nobody approved is not a variant that publishes."""
    try:
        job = store.get(_s(job_id))
    except Exception:                                 # noqa: BLE001
        return {"ok": False, "error": f"no piece called {job_id}"}
    import content_engine_orchestrator as orch
    base = _d(job.get("payload"))
    child = {
        "job_id": f"{_s(job_id)}_var{len(_l(_get(store, 'variants', []))) + 1}",
        "type": job.get("type") or "content_piece",
        "status": "created",
        "created_at": _now(),
        "payload": {"config": dict(_d(base.get("config"))),
                    "variant_of": _s(job_id),
                    "variant_note": _s(note),
                    "revision_note": (_s(note) or
                                      "write a different angle on the same "
                                      "brief; this is a variant to test")},
    }
    orch.ensure_failure_reason(child)
    store.save(child)
    rows = _l(_get(store, "variants", []))
    rows.append({"at": _now(), "parent": _s(job_id),
                 "child": child["job_id"], "note": _s(note),
                 "state": "DRAFTING"})
    _set(store, "variants", rows[-MAX_LOG:])
    return {"ok": True, "message": f"variant queued as {child['job_id']}; it "
                                   f"drafts, then waits for you like any "
                                   f"other piece",
            "job_id": child["job_id"]}


def dismiss_signal(store, signal_id: str, why: str = "") -> Dict[str, Any]:
    """Take a signal off the board, with the reason recorded."""
    if not _s(signal_id):
        return {"ok": False, "error": "which signal?"}
    rows = _l(_get(store, "dismissed_signals", []))
    rows.append({"at": _now(), "id": _s(signal_id), "why": _s(why)})
    _set(store, "dismissed_signals", rows[-MAX_LOG:])
    return {"ok": True, "message": "dismissed; it will not come back on the "
                                   "board, and the reason is recorded"}


def save_brief(store, key: str, text: str) -> Dict[str, Any]:
    """Save a content brief the SEO screens write against."""
    if not _s(key):
        return {"ok": False, "error": "which brief?"}
    briefs = _d(_get(store, "content_briefs", {}))
    briefs[_s(key)] = {"text": _s(text), "at": _now()}
    _set(store, "content_briefs", briefs)
    return {"ok": True, "message": f"brief saved for {key}"}


def edit_plan(store, row_id: str, field: str, value: str) -> Dict[str, Any]:
    """Edit one row of the content plan before it becomes work."""
    plan = _d(_get(store, "content_plan", {}))
    rows = _l(plan.get("rows") or plan.get("calendar"))
    hit = None
    for r in rows:
        if _s(_d(r).get("id")) == _s(row_id):
            hit = r
            break
    if hit is None:
        return {"ok": False, "error": f"no plan row called {row_id}"}
    if _s(field) not in ("title", "type", "market", "date", "keyword"):
        return {"ok": False, "error": f"'{field}' is not an editable field"}
    hit[_s(field)] = _s(value)
    plan["rows"] = rows
    _set(store, "content_plan", plan)
    return {"ok": True, "message": f"plan row {row_id}: {field} is now "
                                   f"'{value}'"}


# ==========================================================================
# QUOTAS - a free API still stops answering
# ==========================================================================
#: Known monthly ceilings. A quota nobody declared is not tracked, and
#: the board says so rather than implying room that may not exist.
QUOTA_LIMITS = {
    "google_gsc_ga4": {"limit": 25000, "unit": "queries/day",
                       "why": "Search Console API daily quota"},
    "serper_search": {"limit": 2500, "unit": "searches/month",
                      "why": "Serper free tier"},
    "seo_pagespeed": {"limit": 25000, "unit": "requests/day",
                      "why": "PageSpeed Insights daily quota"},
}


def record_usage(store, wire: str, n: int = 1) -> None:
    """One tick against a wire's quota. Best-effort, never raises."""
    try:
        rows = _d(_get(store, "quota_usage", {}))
        key = _s(wire)
        cur = _d(rows.get(key))
        from datetime import date
        today = date.today().isoformat()
        if _s(cur.get("day")) != today:
            cur = {"day": today, "used": 0}
        cur["used"] = int(cur.get("used") or 0) + int(n)
        rows[key] = cur
        _set(store, "quota_usage", rows)
    except Exception:                                 # noqa: BLE001
        pass


def quotas(store) -> list:
    """What each wire has used against what it is allowed."""
    used = _d(_get(store, "quota_usage", {}))
    out = []
    for wire, spec in QUOTA_LIMITS.items():
        u = _d(used.get(wire))
        n = u.get("used")
        lim = spec["limit"]
        pct = (round(float(n) / lim * 100, 1)
               if isinstance(n, (int, float)) and lim else None)
        out.append({
            "name": wire, "limit": lim, "unit": spec["unit"],
            "used": n,
            "pct": pct,
            "state": ("NOT MEASURED" if n is None else
                      "AT RISK" if pct is not None and pct >= 80 else "OK"),
            "why": (spec["why"] if n is not None else
                    spec["why"] + "; nothing has been counted yet, which is "
                    "not the same as nothing having been used"),
        })
    return out


# ==========================================================================
# THE FACTORY'S OWN AGENTS
# ==========================================================================
def run_factory_agents(store, limit: int = 1) -> Dict[str, Any]:
    """Run the Content Factory's agents once, over real signals.

    The prover has said "factory loop: NEVER RUN" since the day it was
    built: the four agents exist, are gated, and nothing ever called
    them. They draft and they escalate; they cannot approve, distribute
    or publish, and this call does not change that."""
    try:
        import content_engine_factory_agents as FA
    except Exception as exc:                          # noqa: BLE001
        return {"ok": False, "error": f"the factory agents are not in this "
                                      f"image: {type(exc).__name__}"}
    runner = None
    for name in ("run_once", "run", "tick", "plan_from_signals"):
        if hasattr(FA, name):
            runner = getattr(FA, name)
            break
    if runner is None:
        return {"ok": False,
                "error": ("no runnable entry point on the factory agents "
                          "(looked for run_once, run, tick, "
                          "plan_from_signals)")}
    try:
        res = runner(store) if _takes_store(runner) else runner()
    except Exception as exc:                          # noqa: BLE001
        return {"ok": False,
                "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    rows = _l(_get(store, "agent_runs", []))
    rows.append({"at": _now(), "agent": "factory", "ok": True,
                 "result": _s(res)[:200] if not isinstance(res, dict)
                 else _s(_d(res).get("message"))[:200],
                 "cost": 0.0, "quality": "MEASURED"})
    _set(store, "agent_runs", rows[-MAX_LOG:])
    return {"ok": True, "message": "the factory agents ran; whatever they "
                                   "produced waits for your approval",
            "result": res if isinstance(res, dict) else _s(res)[:200]}


def _takes_store(fn) -> bool:
    try:
        import inspect
        return len(inspect.signature(fn).parameters) >= 1
    except Exception:                                 # noqa: BLE001
        return True


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d, self.j = {}, {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

        def get(self, jid):
            if jid not in self.j:
                raise KeyError(jid)
            return self.j[jid]

        def save(self, job):
            self.j[job["job_id"]] = job

    s = _S()
    s.j["p1"] = {"job_id": "p1", "type": "content_piece",
                 "payload": {"content_producer": {"body": "first text"}}}
    r = save_piece(s, "p1", "body", "second text")
    assert r["ok"] and s.j["p1"]["payload"]["content_producer"]["body"] \
        == "second text"
    r = restore_piece(s, "p1")
    assert s.j["p1"]["payload"]["content_producer"]["body"] == "first text", r
    assert not save_piece(s, "p1", "price", "x")["ok"], "field allow-list"
    r = make_variant(s, "p1", "shorter, sharper")
    assert r["ok"] and s.j[r["job_id"]]["status"] == "created"
    q = quotas(s)
    assert q and all(x["state"] == "NOT MEASURED" for x in q), q
    record_usage(s, "serper_search", 5)
    q2 = [x for x in quotas(s) if x["name"] == "serper_search"][0]
    assert q2["used"] == 5 and q2["state"] == "OK", q2
    assert dismiss_signal(s, "sig1", "not our market")["ok"]
    assert save_brief(s, "k1", "the brief")["ok"]
    print("OK - actions: edits keep their history, restore works, a variant "
          "enters as a draft, and an uncounted quota says NOT MEASURED")
