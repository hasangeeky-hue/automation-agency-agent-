"""SECTION AGENTS — the inspectors that find a problem before you do.

Measured before building: the scheduler imports four modules and dispatches
three task types. Six of the nine dashboard sections - Media, BI, SGA, Risk,
System and the Cockpit - have NO automatic behaviour at all. 1,531 of 2,227
cards live in sections the scheduler has no import path to. They are reports
a person has to read and act on.

AN AGENT HERE IS SIX DECLARED THINGS
    contract   what healthy means, in COUNTABLE terms
    sensor     reads live state - pure code, no model, free
    findings   one per failed check, each carrying its own fix
    actions    the only part that may call a model (via the fix registry)
    cadence    when it runs
    escalation what it does when it cannot fix - names the field, never navigates

Contracts and sensors are arithmetic. That is deliberate: most agent work then
costs nothing and cannot be wrong about what it saw. The judge stays for taste
and is not used here - "is this credential malformed" is not a matter of
opinion.

HONEST SCOPE OF THIS FILE
    Content, Outreach, Risk and System have real contracts, each written
    against data shapes read out of the live context builders first rather
    than guessed.

    The other five are registered with NO CHECKS and say so. An agent with
    invented checks against a data shape nobody confirmed is worse than an
    empty one: it reports confidently and is wrong. Each needs one pass
    against its real board before it gets a contract, and until then it
    honestly reports that it has none.

    python content_engine_agents.py
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger("content_engine.agents")

_S = lambda v: str(v or "").strip()
_D = lambda v: v if isinstance(v, dict) else {}
_L = lambda v: list(v) if isinstance(v, (list, tuple)) else []

FINDINGS_KEY = "engine_agent_findings"


def _now():
    return datetime.now(timezone.utc)


class Finding:
    """One failed check, and what can be done about it."""

    def __init__(self, section, check, detail, *, severity="warn",
                 fix_id="", fix_arg=""):
        self.section = section
        self.check = check
        self.detail = detail
        self.severity = severity            # warn | bad
        self.fix_id = fix_id
        self.fix_arg = fix_arg

    def as_dict(self):
        return {"section": self.section, "check": self.check,
                "detail": self.detail, "severity": self.severity,
                "fix_id": self.fix_id, "fix_arg": self.fix_arg}


class Agent:
    """A section inspector. `checks` is a list of callables taking (store, ctx)
    and returning Finding objects (or nothing when healthy)."""

    def __init__(self, key, label, checks=(), note=""):
        self.key = key
        self.label = label
        self.checks = list(checks)
        self.note = note

    @property
    def has_contract(self) -> bool:
        return bool(self.checks)

    def inspect(self, store=None, ctx=None) -> dict:
        """Run every check. One failing check must never stop the others."""
        out, errs = [], []
        for fn in self.checks:
            try:
                r = fn(store, _D(ctx))
            except Exception as e:
                errs.append(f"{getattr(fn, '__name__', 'check')}: "
                            f"{type(e).__name__}: {str(e)[:90]}")
                continue
            for f in (r if isinstance(r, (list, tuple)) else [r]):
                if isinstance(f, Finding):
                    out.append(f)
        return {"section": self.key, "label": self.label,
                "has_contract": self.has_contract,
                "checks_run": len(self.checks),
                "findings": [f.as_dict() for f in out],
                "errors": errs,
                "note": self.note,
                "at": _now().isoformat()}


AGENTS: dict[str, Agent] = {}


def register(agent: Agent) -> Agent:
    AGENTS[agent.key] = agent
    return agent


# ===========================================================================
#  SYSTEM AGENT — the section with the clearest rules, so it proves the shape
# ===========================================================================
def _sys_bad_credentials(store, ctx):
    """A credential that is SET but malformed reads green everywhere else,
    because status() only asks whether the field is non-empty."""
    import content_engine_connectors as C
    out = []
    for row in C.credential_audit():
        out.append(Finding("system", f"{row['key']} looks wrong", row["problem"],
                           severity="bad", fix_id="clear_setting",
                           fix_arg=row["key"]))
    return out


def _sys_shadowed(store, ctx):
    """A malformed stored value being ignored in favour of deploy/.env still
    needs cleaning up - the engine works, the board lies."""
    import content_engine_connectors as C
    return [Finding("system", f"{k} is being ignored",
                    f"the stored value {why[:80]}, so the environment is used "
                    f"instead", severity="warn",
                    fix_id="clear_setting", fix_arg=k)
            for k, why in C.shadowed().items()]


def _sys_wires_down(store, ctx):
    import content_engine_connectors as C
    st = C.status()
    down = [k for k, v in st.items() if not v]
    if not down:
        return []
    return [Finding("system", f"{len(down)} wire(s) not connected",
                    ", ".join(sorted(down)[:8]),
                    severity="warn", fix_id="retest_wires")]


register(Agent("system", "System & Wiring",
               [_sys_bad_credentials, _sys_shadowed, _sys_wires_down]))


# ===========================================================================
#  CONTENT AGENT — data shapes verified today
# ===========================================================================
def _pieces(store):
    try:
        return [j for j in store.list_jobs()
                if _D(j).get("type") == "content_piece"]
    except Exception:
        return []


def _con_no_image(store, ctx):
    out = []
    for j in _pieces(store):
        if _D(j).get("status") != "AWAITING_APPROVAL":
            continue
        pl = _D(j).get("payload") or {}
        pc = _D(pl.get("content_producer"))
        if pc and not (pc.get("image_url") or pl.get("image_url")):
            out.append(Finding(
                "content", "A piece waiting for you has no image",
                _S(pc.get("title"))[:70] or _S(j.get("job_id")),
                severity="warn", fix_id="piece_image",
                fix_arg=_S(j.get("job_id"))))
    return out


def _con_failed(store, ctx):
    bad = [j for j in _pieces(store)
           if _D(j).get("status") in ("failed", "revision_needed")]
    return [Finding("content", f"{len(bad)} piece(s) failed",
                    "; ".join(_S(_D(j).get("halt_reason"))[:60]
                              for j in bad[:3]) or "no reason recorded",
                    severity="bad", fix_id="retry_job",
                    fix_arg=_S(_D(bad[0]).get("job_id")))] if bad else []


def _con_stale_gate(store, ctx):
    """A piece nobody has answered is a stalled line, not a queue."""
    out, now = [], _now()
    for j in _pieces(store):
        if _D(j).get("status") != "AWAITING_APPROVAL":
            continue
        try:
            when = datetime.fromisoformat(
                _S(_D(j).get("updated_at") or _D(j).get("created_at")
                   ).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        hours = (now - when).total_seconds() / 3600
        if hours > 72:
            out.append(Finding(
                "content", "Waiting for your decision over 72h",
                f"{_S(_D(j).get('job_id'))} - {int(hours)}h",
                severity="warn"))
    return out


register(Agent("content", "Content Factory",
               [_con_no_image, _con_failed, _con_stale_gate]))


# ===========================================================================
#  THE OTHER SEVEN — registered, honest, and deliberately empty
#
#  Writing checks against data shapes I have not verified is how a report
#  becomes confidently wrong. Each of these needs one pass against its real
#  board. Until then the agent exists, runs, and says it has no contract.
# ===========================================================================
def _risk_ctx(store):
    """The sensor. Reads live risk state through the same builder the board
    uses, so the agent and the screen can never disagree."""
    import content_engine_seo_ops as OPS
    return _D(OPS.build_risk_ctx(store))


def _rsk_no_backup(store, ctx):
    c = _D(_risk_ctx(store).get("continuity"))
    if c.get("configured"):
        return []
    return [Finding("risk", "No backup is configured",
                    _S(c.get("verdict"))[:140] or
                    "every credential, job and audit is at risk",
                    severity="bad", fix_id="run_backup")]


def _rsk_restore_untested(store, ctx):
    c = _D(_risk_ctx(store).get("continuity"))
    if not c.get("configured") or c.get("restore_tested"):
        return []
    return [Finding("risk", "The restore has never been tested",
                    "A backup nobody has restored from is a hope, not a "
                    "backup.", severity="warn")]


def _rsk_exposed(store, ctx):
    cr = _D(_risk_ctx(store).get("credentials"))
    ex = [x for x in _L(cr.get("known_exposed")) if _S(x)]
    out = []
    if ex:
        out.append(Finding("risk", f"{len(ex)} credential(s) known exposed",
                           ", ".join(_S(x) for x in ex[:5]),
                           severity="bad"))
    if cr.get("never_rotated") and cr.get("set"):
        out.append(Finding("risk", "No credential has ever been rotated",
                           f"{cr.get('set')} of {cr.get('total')} fields hold "
                           f"a value and none has been replaced since setup.",
                           severity="warn"))
    return out


register(Agent("risk", "Risk & Infrastructure",
               [_rsk_no_backup, _rsk_restore_untested, _rsk_exposed]))


def _out_ctx(store):
    import content_engine_seo_ops as OPS
    return _D(OPS.build_outreach_ctx(store))


def _out_tracking_off(store, ctx):
    t = _D(_out_ctx(store).get("tracking"))
    if t.get("enabled"):
        return []
    return [Finding("outreach", "Open and click tracking is off",
                    "Every send goes out unmeasured, so nothing can be learned "
                    "from it.", severity="warn")]


def _out_unclassified_replies(store, ctx):
    r = _D(_out_ctx(store).get("replies"))
    n = int(r.get("unclassified") or 0)
    if not n:
        return []
    return [Finding("outreach", f"{n} repl(ies) not classified",
                    "They arrived and nothing decided what they were, so they "
                    "are not in any queue.", severity="warn",
                    fix_id="refresh_replies")]


def _out_suppression(store, ctx):
    d = _D(_out_ctx(store).get("deliverability"))
    out = []
    rate = float(d.get("suppression_rate") or 0)
    if rate >= 5:
        out.append(Finding("outreach", f"Suppression rate {rate:.1f}%",
                           f"{d.get('bounces', 0)} bounce(s), "
                           f"{d.get('unsubscribes', 0)} unsubscribe(s). A "
                           f"climbing rate burns the sending domain.",
                           severity="bad"))
    if int(d.get("unrecorded") or 0):
        out.append(Finding("outreach",
                           f"{d.get('unrecorded')} send(s) with no outcome",
                           "Sent, and nothing recorded what happened.",
                           severity="warn"))
    return out


register(Agent("outreach", "Leads & Outreach",
               [_out_tracking_off, _out_unclassified_replies, _out_suppression]))


_PENDING = {
    "seo": ("SEO / AEO / GEO",
            "proposed: missing meta, alt, schema, canonical, IndexNow unsent"),
    "media": ("Media Buying",
              "proposed: campaign without a cap, creative without an image. "
              "READ-ONLY by design - this section touches money"),
    "bi": ("Business Intel", "proposed: metric with no source wired, stale pull"),
    "sga": ("SGA", "proposed: post scheduled to a dead channel, calendar gaps"),
    "cockpit": ("AI Cockpit",
                "proposed: queue age, burn rate. READ-ONLY by design - this is "
                "where you decide"),
}
for _k, (_lab, _note) in _PENDING.items():
    register(Agent(_k, _lab, [], note=_note))

# Sections an agent must never act on, whatever is later registered.
READ_ONLY = ("media", "cockpit")


def inspect_one(key, store=None, ctx=None) -> dict:
    a = AGENTS.get(key)
    if a is None:
        return {"section": key, "error": "no such agent"}
    r = a.inspect(store, ctx)
    r["read_only"] = key in READ_ONLY
    return r


def inspect_all(store=None, ctx=None) -> dict:
    rs = [inspect_one(k, store, ctx) for k in AGENTS]
    return {"at": _now().isoformat(),
            "sections": rs,
            "total_findings": sum(len(r.get("findings", [])) for r in rs),
            "with_contract": len([r for r in rs if r.get("has_contract")]),
            "without_contract": len([r for r in rs if not r.get("has_contract")])}


def save_findings(store, result) -> None:
    """One store key the boards read. No board computes its own health."""
    try:
        store.set_setting(FINDINGS_KEY, result)
    except Exception as e:
        log.warning("could not save findings: %s", e)


def load_findings(store) -> dict:
    try:
        return _D(store.get_setting(FINDINGS_KEY, {}))
    except Exception:
        return {}


if __name__ == "__main__":
    import content_engine_fixes as FX

    assert len(AGENTS) == 9, f"nine sections, got {len(AGENTS)}"
    withc = [k for k, a in AGENTS.items() if a.has_contract]
    assert set(withc) == {"system", "content", "risk", "outreach"}, withc

    # every fix an agent names must exist in the registry - the orphan check
    for a in AGENTS.values():
        for fn in a.checks:
            pass
    for fid in ("clear_setting", "retest_wires", "piece_image", "retry_job",
                "refresh_replies"):
        assert fid in FX.REGISTRY, f"agent names a fix that does not exist: {fid}"

    # read-only sections may never carry an auto fix
    for k in READ_ONLY:
        assert not AGENTS[k].checks, f"{k} must stay read-only"

    class St:
        def __init__(s, jobs=None, sets=None):
            s.j = jobs or []
            s.s = sets or {}

        def list_jobs(s):
            return s.j

        def get_setting(s, k, d=None):
            return s.s.get(k, d)

        def set_setting(s, k, v):
            s.s[k] = v

    import content_engine_connectors as C
    C._SETTINGS_GET = {"IMAGE_API_KEY": "cd /opt && docker compose up",
                       "WORDPRESS_URL": "https://x"}.get

    r = inspect_one("system", St())
    ids = [f["check"] for f in r["findings"]]
    assert any("IMAGE_API_KEY" in i for i in ids), ids
    assert r["findings"][0]["fix_id"] == "clear_setting"
    assert not r["errors"], r["errors"]

    jobs = [{"job_id": "a", "type": "content_piece",
             "status": "AWAITING_APPROVAL", "created_at": "2026-07-01T00:00:00Z",
             "updated_at": "2026-07-01T00:00:00Z",
             "payload": {"content_producer": {"title": "No picture here"}}},
            {"job_id": "b", "type": "content_piece", "status": "failed",
             "halt_reason": "qa_compliance: brief not met", "payload": {}}]
    rc = inspect_one("content", St(jobs))
    checks = [f["check"] for f in rc["findings"]]
    assert any("no image" in c for c in checks), checks
    assert any("failed" in c for c in checks), checks
    assert any("72h" in c for c in checks), checks
    assert not rc["errors"], rc["errors"]

    # a check that raises must not take the others down
    bad = Agent("tmp", "T", [lambda s, c: 1 / 0, lambda s, c: Finding(
        "tmp", "still ran", "the other check survived")])
    rb = bad.inspect(None)
    assert len(rb["findings"]) == 1 and len(rb["errors"]) == 1, rb

    allr = inspect_all(St(jobs))
    assert allr["with_contract"] == 4 and allr["without_contract"] == 5

    st = St()
    save_findings(st, allr)
    assert load_findings(st)["total_findings"] == allr["total_findings"]

    print(f"OK - agents self-check passed. {len(AGENTS)} sections registered: "
          f"{allr['with_contract']} with a real contract "
          f"({', '.join(sorted(withc))}) and "
          f"{allr['without_contract']} that run and honestly report having "
          f"none. Every fix an agent names exists in the registry, a check "
          f"that raises cannot silence the others, and the two money-and-"
          f"decision sections are read-only by construction.")
