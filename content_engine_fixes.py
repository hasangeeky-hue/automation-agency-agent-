"""THE FIX REGISTRY — one place a card's problem becomes a card's action.

Measured before building this: 2,227 cards, 775 of them flagging a problem,
2,598 buttons - and ZERO that fix the card they sit on. The 314 buttons that
call act() post to seven global endpoints (/health, /selftest, /tick,
/evals/run, /schedule/run, /replies/refresh, /outreach/send_all). Every other
button navigates somewhere else, which is how a person loses their place.

WHAT THIS IS
    A registry mapping a fix id -> what it does, what it costs, whether it can
    be undone, and what it needs first. Plus one helper that renders the
    button, so board authors stop hand-writing HTML - which is why there are
    2,598 buttons in about forty shapes today.

WHY ONE REGISTRY
    The alternative is a handler per board. This codebase has five
    capabilities that were built and never wired: judge, evals, image_prompts,
    the outcome collector, seoAuto. A registry with an import-time assertion
    that every declared fix has a handler makes that specific failure
    impossible rather than merely unlikely.

THE THREE TIERS
    auto       free and reversible - an agent may run it unattended
    offered    costs money or cannot be undone - becomes a button you press
    escalated  needs a credential only you can supply - names the field

NEVER AUTO, whatever a caller passes: publishing, sending, spending without
confirmation, overwriting a credential, deleting content, changing a cap.

    python content_engine_fixes.py
"""
from __future__ import annotations

import html
import logging

log = logging.getLogger("content_engine.fixes")

_S = lambda v: str(v or "").strip()

# Fix ids that may NEVER be promoted to automatic, regardless of how they are
# registered or what a learning loop later concludes.
NEVER_AUTO = ("publish", "send", "spend", "credential", "delete", "cap")


class Fix:
    """One repairable problem: what to call it, what it costs, what it needs."""

    def __init__(self, fid, label, handler, *, cost=0.0, reversible=True,
                 requires=(), confirm=None, section=""):
        self.id = fid
        self.label = label
        self.handler = handler
        self.cost = float(cost or 0)
        self.reversible = bool(reversible)
        self.requires = tuple(requires or ())
        self.section = section
        self.confirm = confirm
        # A fix is auto-runnable only if it is free, reversible, and its id
        # does not touch a forbidden verb. The last clause is deliberately
        # crude: a fix called "publish_now" must never become automatic
        # because someone passed cost=0 by accident.
        self.auto = (self.cost == 0 and self.reversible
                     and not any(w in fid for w in NEVER_AUTO))

    def blocked_by(self, env_get) -> str:
        """The first credential this fix needs and does not have."""
        for name in self.requires:
            try:
                if not _S(env_get(name)):
                    return name
            except Exception:
                return name
        return ""


REGISTRY: dict[str, Fix] = {}


def register(fid, label, handler, **kw) -> Fix:
    if fid in REGISTRY:
        raise ValueError(f"fix id already registered: {fid}")
    f = Fix(fid, label, handler, **kw)
    REGISTRY[fid] = f
    return f


def fix_button(fid, *, arg="", env_get=None) -> str:
    """The button HTML for a card. Empty string when the fix is unknown.

    Board authors call THIS instead of writing markup, so every fix button on
    every board behaves identically and routes through one endpoint."""
    f = REGISTRY.get(fid)
    if f is None:
        return ""
    e = html.escape
    if env_get is not None:
        missing = f.blocked_by(env_get)
        if missing:
            # ESCALATED: focus the field, never navigate away.
            return (f"<button class='cbtn' onclick=\"focusKey('{e(missing)}')\">"
                    f"Needs {e(missing)}</button>")
    q = f"?arg={e(str(arg))}" if arg else ""
    cost = f" (&euro;{f.cost:.2f})" if f.cost else ""
    return (f"<button class='cta' onclick=\"act('/fix/{e(f.id)}{q}')\">"
            f"{e(f.label)}{cost}</button>")


LEDGER_KEY = "engine_fix_ledger"
LEDGER_MAX = 400


def _record(store, fid, arg, ok, message, auto) -> None:
    """THE LEDGER. Every fix leaves a trace: what was run, on what, whether it
    worked, and why not.

    This is what "learns day by day" actually rests on. Not a model that gets
    cleverer - a record of what worked. Three things become answerable once it
    has history, in ascending order of how much data they need:

      recurrence  the same check failing again days after a fix "worked" -
                  which means it was not a fix
      reliability this action fails most of the time, and here is the reason
      promotion   you have accepted this every time, should it run itself

    No thresholds are set here. They belong to the data, not to me."""
    if store is None or not hasattr(store, "set_setting"):
        return
    try:
        from datetime import datetime, timezone
        rows = list(store.get_setting(LEDGER_KEY, []) or [])
        rows.append({"fix": fid, "arg": _S(arg)[:60], "ok": bool(ok),
                     "message": _S(message)[:140], "auto": bool(auto),
                     "at": datetime.now(timezone.utc).isoformat()})
        store.set_setting(LEDGER_KEY, rows[-LEDGER_MAX:])
    except Exception as e:
        log.warning("could not record fix %s: %s", fid, e)


def ledger(store, limit=60) -> list:
    try:
        return list(store.get_setting(LEDGER_KEY, []) or [])[-limit:][::-1]
    except Exception:
        return []


def ledger_summary(store) -> dict:
    """What the record can honestly say today."""
    rows = []
    try:
        rows = list(store.get_setting(LEDGER_KEY, []) or [])
    except Exception:
        pass
    if not rows:
        return {"runs": 0, "note": "nothing recorded yet - the ledger starts "
                                   "empty and learns nothing until fixes run"}
    by = {}
    for r in rows:
        b = by.setdefault(r.get("fix", "?"), {"run": 0, "ok": 0})
        b["run"] += 1
        b["ok"] += 1 if r.get("ok") else 0
    unreliable = [f"{k} fails {b['run'] - b['ok']} of {b['run']}"
                  for k, b in by.items() if b["run"] >= 5 and b["ok"] * 2 < b["run"]]
    return {"runs": len(rows),
            "ok": len([r for r in rows if r.get("ok")]),
            "auto": len([r for r in rows if r.get("auto")]),
            "by_fix": by,
            "unreliable": unreliable,
            "note": ("enough history to judge reliability" if len(rows) >= 20
                     else f"{len(rows)} runs recorded - reliability needs about "
                          f"20 before it means anything")}


def run_fix(fid, store=None, arg="", auto=False) -> dict:
    """Execute a fix. Always returns {ok, message}; never raises."""
    f = REGISTRY.get(fid)
    if f is None:
        return {"ok": False, "message": f"no such fix: {fid}"}
    if auto and not f.auto:
        return {"ok": False,
                "message": f"{fid} costs money or cannot be undone - it needs "
                           f"a person to press it"}
    try:
        out = f.handler(store, arg) or {}
    except Exception as e:
        log.warning("fix %s raised: %s", fid, e)
        out = {"ok": False, "message": f"{type(e).__name__}: {str(e)[:160]}"}
    if not isinstance(out, dict):
        out = {"ok": True, "message": "done"}
    out.setdefault("ok", True)
    out.setdefault("message", "done" if out["ok"] else "that did not work")
    _record(store, fid, arg, out["ok"], out["message"], auto)
    return out


def auto_fixes() -> list:
    """Every fix an agent may run unattended."""
    return [f for f in REGISTRY.values() if f.auto]


def summary() -> dict:
    return {"total": len(REGISTRY),
            "auto": len(auto_fixes()),
            "offered": len([f for f in REGISTRY.values() if not f.auto]),
            "by_section": {s: len([f for f in REGISTRY.values()
                                   if f.section == s])
                           for s in sorted({f.section for f in REGISTRY.values()})}}


# ---------------------------------------------------------------------------
# THE FIXES THEMSELVES
# Each one is small on purpose: it does one thing and reports what happened.
# ---------------------------------------------------------------------------
def _f_retest_wires(store, arg):
    import content_engine_connectors as C
    st = C.status()
    live = len([k for k, v in st.items() if v])
    return {"ok": True, "message": f"{live} of {len(st)} wires answered"}


def _f_piece_image(store, arg):
    """Attach a hero image to a piece that has none."""
    import content_engine_api as API
    r = API.api_generate_piece_image(arg) if hasattr(
        API, "api_generate_piece_image") else None
    if isinstance(r, dict):
        return r
    return {"ok": False, "message": "the image endpoint is not available"}


def _f_backup(store, arg):
    import subprocess
    try:
        p = subprocess.run(["bash", "deploy/backup.sh"], capture_output=True,
                           text=True, timeout=240)
        ok = p.returncode == 0
        tail = (p.stdout or p.stderr or "").strip().splitlines()
        return {"ok": ok, "message": tail[-1][:150] if tail else
                ("backup written" if ok else "backup failed")}
    except FileNotFoundError:
        return {"ok": False, "message": "deploy/backup.sh is not in the image"}
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"[:150]}


def _f_clear_setting(store, arg):
    """Empty a stored credential that should not hold a value."""
    if not arg:
        return {"ok": False, "message": "no field named"}
    import content_engine_connectors as C
    if arg not in C.CONNECTOR_ENV_KEYS:
        return {"ok": False, "message": f"{arg} is not a field this engine reads"}
    if store is None or not hasattr(store, "set_setting"):
        return {"ok": False, "message": "this store cannot save settings"}
    store.set_setting(arg, "")
    return {"ok": True, "message": f"{arg} cleared"}


def _f_indexnow(store, arg):
    import content_engine_seo_ops as SEO
    if hasattr(SEO, "submit_indexnow"):
        r = SEO.submit_indexnow(store) or {}
        n = r.get("submitted", r.get("count", 0))
        return {"ok": True, "message": f"{n} URL(s) submitted to IndexNow"}
    return {"ok": False, "message": "IndexNow submission is not wired"}


def _f_retry_job(store, arg):
    """Put a failed job back on the queue."""
    if not arg or store is None:
        return {"ok": False, "message": "no job named"}
    try:
        job = store.get(arg)
    except Exception:
        return {"ok": False, "message": f"no such job: {arg}"}
    prev = job.get("status")
    if prev not in ("failed", "revision_needed"):
        return {"ok": False, "message": f"job is '{prev}', not failed"}
    back = {"failed": "created", "revision_needed": "seo_checked"}
    job["status"] = back.get(prev, "created")
    job.pop("halt_reason", None)
    job["needs_human"] = False
    store.save(job)
    return {"ok": True, "message": f"{arg} requeued from {prev}"}


def _f_decline(store, arg):
    """Send a piece back with your correction attached.

    api_decline has existed the whole time and was reachable only from the
    Cockpit - so judging a piece and acting on it happened on two different
    screens. The note is the EDIT mechanism: prepare_input already reads
    revision_note, so what you write here reaches the writer's next prompt."""
    if not arg:
        return {"ok": False, "message": "no piece named"}
    jid, _, note = str(arg).partition("|")
    import content_engine_api as API
    r = API.api_decline(jid.strip(), note.strip()) or {}
    if r.get("error"):
        return {"ok": False, "message": str(r["error"])}
    return {"ok": True,
            "message": (f"sent back with your note" if note.strip()
                        else "declined - it will not publish")}


def _f_discard(store, arg):
    """Take a piece out of the queue for good. Never automatic: 'delete' is in
    NEVER_AUTO, so no agent can reach this however it is registered."""
    if not arg or store is None:
        return {"ok": False, "message": "no piece named"}
    try:
        job = store.get(str(arg).strip())
    except Exception:
        return {"ok": False, "message": f"no such job: {arg}"}
    if job.get("status") == "published":
        return {"ok": False,
                "message": "already published - discarding here would not "
                           "unpublish it, so this refuses rather than pretend"}
    job["status"] = "discarded"
    job["needs_human"] = False
    job["halt_reason"] = "discarded by you"
    store.save(job)
    return {"ok": True, "message": f"{arg} taken out of the queue"}


register("retest_wires", "Re-test every wire", _f_retest_wires,
         section="system")
register("run_backup", "Run a backup now", _f_backup, section="risk")
register("clear_setting", "Clear this field", _f_clear_setting,
         reversible=False, section="system")
register("submit_indexnow", "Submit to IndexNow", _f_indexnow, section="seo")
register("retry_job", "Retry this job", _f_retry_job, section="content")
register("piece_image", "Generate the image", _f_piece_image, cost=0.04,
         requires=("IMAGE_API_KEY",), section="content")
register("decline_piece", "Send back with a note", _f_decline,
         reversible=False, section="content")
register("delete_piece", "Discard this piece", _f_discard,
         reversible=False, section="content")


# EVERY REGISTERED FIX MUST HAVE A CALLABLE HANDLER. This assertion is the
# whole reason for a registry: five things in this codebase were built and
# never wired, and each was discovered by a person, weeks later.
for _fid, _f in REGISTRY.items():
    if not callable(_f.handler):
        raise AssertionError(f"fix '{_fid}' has no handler - this is the "
                             f"orphaned-capability bug, caught at import")


if __name__ == "__main__":
    s = summary()
    assert s["total"] == len(REGISTRY)
    assert REGISTRY["retest_wires"].auto, "free + reversible must be auto"
    assert not REGISTRY["piece_image"].auto, "a fix that spends is never auto"
    assert not REGISTRY["clear_setting"].auto, "irreversible is never auto"

    # a forbidden verb can never be auto even if registered as free+reversible
    register("publish_now", "Publish", lambda st, a: {"ok": True},
             section="test")
    assert not REGISTRY["publish_now"].auto, (
        "a fix whose id contains a forbidden verb must never be auto, "
        "however it was registered")
    del REGISTRY["publish_now"]

    got = {}
    assert fix_button("nope") == "", "an unknown fix renders nothing"
    b = fix_button("piece_image", env_get=lambda k: "")
    assert "Needs IMAGE_API_KEY" in b and "focusKey" in b, b
    b2 = fix_button("piece_image", env_get=lambda k: "sk-proj-x")
    assert "act(&#x27;/fix/piece_image&#x27;)" in b2 or "/fix/piece_image" in b2
    assert "0.04" in b2, "a fix that spends must show the cost on the button"

    r = run_fix("nope")
    assert r["ok"] is False and "no such fix" in r["message"]
    register("boom", "Boom", lambda st, a: 1 / 0, section="test")
    r = run_fix("boom")
    assert r["ok"] is False and "ZeroDivisionError" in r["message"], r
    del REGISTRY["boom"]

    r = run_fix("clear_setting", None, "")
    assert r["ok"] is False

    print(f"OK - fix registry self-check passed. {s['total']} fixes "
          f"registered, {s['auto']} of them safe for an agent to run "
          f"unattended, {s['offered']} that cost money or cannot be undone and "
          f"therefore stay behind a button. Every fix has a handler, an "
          f"unknown fix renders no button, a missing credential names the "
          f"field instead of navigating, and a handler that raises returns a "
          f"reason instead of a stack trace.")
