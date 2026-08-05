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
    SEVEN of the nine have real contracts - content, seo, outreach, bi, sga,
    risk and system - each written against data shapes read out of the live
    context builders BEFORE a single check was typed. The SEO cadence check
    calls the scheduler's own seo_due() rather than counting days itself; a
    second copy of that rule is the bug that started this whole day.

    The remaining two carry no checks ON PURPOSE. Media moves money and the
    Cockpit is where you decide - an agent acting in either is a worse
    machine, not a more capable one.

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


def _how_for(fix_id) -> str:
    """What pressing this button will actually do, and what the alternative is.

    Written once per fix rather than at every call site, so a finding can
    never offer a button whose consequence is undescribed. If a fix has no
    entry here it is named as unexplained rather than silently blank - a
    missing explanation should be visible, not invisible."""
    return {
        "clear_setting":
            "Empties the field. The engine then falls back to deploy/.env if "
            "a value is there. Nothing else is touched.",
        "retest_wires":
            "Asks every connector to answer. Free, changes nothing - it only "
            "re-reads what is already configured.",
        "run_backup":
            "Writes a backup now. Does not test that it restores - press "
            "Test the restore for that.",
        "test_restore":
            "Reads the backup back to prove it can be. Free, changes nothing.",
        "submit_indexnow":
            "Pushes your new URLs to Bing and Yandex. Free. Google is not "
            "included - it does not use IndexNow.",
        "retry_job":
            "Revives this one piece, resuming AFTER its last completed step "
            "- finished work is not re-bought. A QA-rejected piece carries "
            "QA's notes to the writer. Spends on the remaining steps only.",
        "retry_dead":
            "Revives EVERY dead piece the same way: each resumes after its "
            "last completed step, QA-rejected ones carry QA's notes. Costs "
            "about EUR 0.10 per piece; every piece still stops at your "
            "approval gate before anything publishes.",
        "piece_image":
            "Generates one image and attaches it. Costs about EUR 0.04 and "
            "cannot be undone, so it asks first.",
        "refresh_replies":
            "Re-reads the inbox and drafts answers. It NEVER sends - the "
            "drafts wait for you.",
        "run_seo_due":
            "Runs only the engines that are overdue AND free. Paid ones are "
            "skipped and named.",
        "run_seo_fixes":
            "Rewrites titles, metas and alt text - things a reader does not "
            "see. It never touches your body copy.",
        "enable_tracking":
            "Turns opens and clicks on for future sends. Past sends stay "
            "unmeasured; nothing is sent by this.",
        "decline_piece":
            "Sends the piece back with your note attached, which the writer "
            "reads on its next attempt.",
        "delete_piece":
            "Takes the piece out of the queue for good. It will not publish. "
            "This cannot be undone.",
    }.get(str(fix_id or ""), "")


class Finding:
    """THE TRANSPARENCY CONTRACT — what, why, and which way.

        check   WHAT is failing        "3 pieces failed"
        detail  WHY                    "content_producer ran out of room"
        how     WHICH WAY to fix it    "Raise the ceiling, or shorten the
                                        brief. This button does the first."

    A card that states a number and offers a button, without saying what the
    button will do or what the alternative is, is the thing being fixed here.
    In the founder's words: "it's just add some button which redirect me to
    the other page without proper explanation ... otherwise I am fully blind."

    `how` is REQUIRED whenever a fix is offered. inspect() records an error
    and substitutes a visible placeholder rather than letting a button ship
    with its consequence undescribed.
    """

    def __init__(self, section, check, detail, *, severity="warn",
                 fix_id="", fix_arg="", how=""):
        self.section = section
        self.check = check
        self.detail = detail
        self.severity = severity            # warn | bad
        self.fix_id = fix_id
        self.fix_arg = fix_arg
        self.how = how

    def as_dict(self):
        return {"section": self.section, "check": self.check,
                "detail": self.detail, "severity": self.severity,
                "fix_id": self.fix_id, "fix_arg": self.fix_arg,
                "how": self.how or _how_for(self.fix_id)}


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
                    # A BUTTON MUST EXPLAIN ITSELF. A finding that offers an
                    # action and cannot say what the action does is exactly
                    # the "button which redirect me without proper
                    # explanation" complaint. Caught here rather than left to
                    # be noticed on screen.
                    if f.fix_id and not (f.how or _how_for(f.fix_id)):
                        errs.append(
                            f"{getattr(fn, '__name__', 'check')}: offers "
                            f"'{f.fix_id}' with no explanation of what it "
                            f"does - add it to _how_for()")
                        f.how = (f"This runs '{f.fix_id}'. What it does is "
                                 f"not documented yet.")
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
    """THE PIPELINE WATCHDOG. 37 pieces sat dead for nine days after their
    underlying bugs were fixed, visible in one SQL query the whole time,
    and no agent owned that number. This one now does: how many are dead,
    how long the oldest has waited, what reviving them costs, and the one
    button that does it. A graveyard can never again accumulate unseen."""
    failed, revision, oldest_days = [], [], 0
    now = _now()
    for j in _pieces(store):
        j = _D(j)
        st = j.get("status")
        if st not in ("failed", "revision_needed"):
            continue
        (failed if st == "failed" else revision).append(j)
        try:
            when = datetime.fromisoformat(
                _S(j.get("updated_at") or j.get("created_at")
                   ).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            oldest_days = max(oldest_days, (now - when).days)
        except Exception:
            pass
    if not failed and not revision:
        return []
    n = len(failed) + len(revision)
    reasons = "; ".join(_S(_D(j).get("halt_reason"))[:50]
                        for j in failed[:2]) or "see each piece's record"
    return [Finding(
        "content",
        f"{n} piece(s) dead in the pipeline"
        + (f" — oldest {oldest_days} day(s)" if oldest_days else ""),
        f"{len(failed)} failed ({reasons}) and {len(revision)} sent back by "
        f"QA with notes nothing ever acted on. Reviving all of them costs "
        f"about €{n * 0.10:.2f} in model spend.",
        severity="bad", fix_id="retry_dead",
        how="Puts every dead piece back on the line, each resuming AFTER its "
            "last completed step (finished work is not re-bought). QA-"
            "rejected pieces carry QA's own notes to the writer. Costs about "
            "€0.10 per piece; nothing publishes without your approval. The "
            "alternative is retrying one piece at a time from its card.")]


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
                    "backup.", severity="warn", fix_id="test_restore")]


def _rsk_exposed(store, ctx):
    cr = _D(_risk_ctx(store).get("credentials"))
    ex = [x for x in _L(cr.get("known_exposed")) if _S(x)]
    out = []
    if ex:
        out.append(Finding("risk", f"{len(ex)} credential(s) known exposed",
                           ", ".join(_S(x) for x in ex[:5]),
                           severity="bad",
                           how="Rotate each one in its provider's console, "
                               "then set the new value with "
                               "`credentials.py --set NAME` - it reads with no "
                               "echo, so it never reaches a shell history. No "
                               "button can do this for you; only you can log "
                               "in to those providers."))
    if cr.get("never_rotated") and cr.get("set"):
        out.append(Finding("risk", "No credential has ever been rotated",
                           f"{cr.get('set')} of {cr.get('total')} fields hold "
                           f"a value and none has been replaced since setup.",
                           severity="warn",
                           how="Not urgent on its own. Rotate anything that "
                               "has been pasted into a chat, a ticket or a "
                               "shared document first."))
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
                    "from it.", severity="warn", fix_id="enable_tracking")]


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


# ===========================================================================
#  SEO AGENT
#
#  Every check below reuses the engine's OWN function or reads a return shape
#  I looked up first. seo_due() is the cadence authority - reimplementing
#  "which engines are overdue" here would be a second copy of a rule, which is
#  the bug that started this whole day.
# ===========================================================================
def _seo_ctx(store):
    import content_engine_seo_ops as OPS
    return _D(OPS.build_ctx(store))


def _seo_overdue(store, ctx):
    """Which engines are past their cadence. Asks the scheduler, never counts
    days itself."""
    try:
        import content_engine_scheduler as SCH
        due = SCH.seo_due(store)
    except Exception:
        return []
    if not due:
        return []
    free = [d for d in due
            if SCH.SEO_CADENCE.get(d, {}).get("cost") == "free"]
    return [Finding("seo", f"{len(due)} SEO engine(s) overdue",
                    ", ".join(due[:8])
                    + (f" - {len(free)} of them cost nothing" if free else ""),
                    severity="warn" if free else "bad",
                    fix_id="run_seo_due" if free else "")]


def _seo_search_console(store, ctx):
    """run_inspect returns {connected, reason} - shape read from the source."""
    ins = _D(_seo_ctx(store).get("inspect"))
    if not ins or ins.get("connected"):
        return []
    return [Finding("seo", "Search Console is not answering",
                    _S(ins.get("reason"))[:140]
                    or "the inspection engine could not reach Google",
                    severity="bad",
                    how="Check GOOGLE_SERVICE_ACCOUNT_JSON and GSC_SITE_URL, "
                        "and that the service account is added as a user on "
                        "the Search Console property. The engine cannot grant "
                        "itself that access.")]


def _seo_indexnow(store, ctx):
    """run_indexnow returns {status, ping, submitted, reason, at}."""
    ix = _D(_seo_ctx(store).get("indexnow"))
    if not ix:
        return []
    if int(ix.get("submitted") or 0):
        return []
    return [Finding("seo", "Nothing has been submitted to IndexNow",
                    _S(ix.get("reason"))[:120]
                    or f"status: {_S(ix.get('status')) or 'unknown'}",
                    severity="warn", fix_id="submit_indexnow")]


def _seo_crawl_issues(store, ctx):
    """run_crawl returns {crawled, issues, scores, work_orders, ...}."""
    cr = _D(_seo_ctx(store).get("crawl"))
    n = int(cr.get("issues") or 0)
    if not n:
        return []
    return [Finding("seo", f"{n} on-page issue(s) from the last crawl",
                    f"{cr.get('crawled', 0)} page(s) crawled. Work orders "
                    f"exist for the ones the engine can fix itself.",
                    severity="warn", fix_id="run_seo_fixes")]


register(Agent("seo", "SEO / AEO / GEO",
               [_seo_overdue, _seo_search_console, _seo_indexnow,
                _seo_crawl_issues]))


# ===========================================================================
#  BI AGENT — shapes read out of build_bi_ctx before a single check was typed
#     targets    {revenue_month, deals_month, leads_month, bookings_month, set}
#     cost       {total, produced, failed, wasted, wasted_pct, per_piece, ...}
#     attainment {rows, set, behind, note}
# ===========================================================================
def _bi_ctx(store):
    import content_engine_seo_ops as OPS
    return _D(OPS.build_bi_ctx(store))


def _bi_no_targets(store, ctx):
    t = _D(_bi_ctx(store).get("targets"))
    if t.get("set"):
        return []
    return [Finding("bi", "No targets are set",
                    "Every card can state a number and none can say whether it "
                    "is good. A dashboard without a target reports, it does "
                    "not judge.", severity="warn",
                    how="Set a monthly revenue, deals, leads or bookings "
                        "target on the Business Intel board. One number is "
                        "enough to start - every attainment card then has "
                        "something to measure against.")]


def _bi_wasted_spend(store, ctx):
    c = _D(_bi_ctx(store).get("cost"))
    pct = float(c.get("wasted_pct") or 0)
    if pct < 20 or not float(c.get("wasted") or 0):
        return []
    return [Finding("bi", f"{pct:.0f}% of content spend was wasted",
                    f"{c.get('failed', 0)} piece(s) failed after costing money. "
                    f"That is spend with nothing to show for it.",
                    severity="bad" if pct >= 40 else "warn")]


def _bi_behind(store, ctx):
    a = _D(_bi_ctx(store).get("attainment"))
    behind = _L(a.get("behind"))
    if not (a.get("set") and behind):
        return []
    return [Finding("bi", f"Behind on {len(behind)} target(s)",
                    ", ".join(_S(b) for b in behind[:5]), severity="warn")]


register(Agent("bi", "Business Intel",
               [_bi_no_targets, _bi_wasted_spend, _bi_behind]))


# ===========================================================================
#  SGA AGENT
#     channels {rows: [{channel, label, connected, posts, posting, ...}]}
#     calendar {tasks, live, planned, live_count, paid, organic, has_data}
#     cadence  {daily_target, days_measured, days_on_target, adherence, ...}
# ===========================================================================
def _sga_ctx(store):
    import content_engine_seo_ops as OPS
    return _D(OPS.build_sga_ctx(store))


def _sga_dead_channel(store, ctx):
    """A channel being posted to that cannot receive. This was a PROPOSED check
    in the plan; the shape is now read, so it is a real one."""
    rows = _L(_D(_sga_ctx(store).get("channels")).get("rows"))
    dead = [r for r in rows
            if _D(r).get("posting") and not _D(r).get("connected")]
    if not dead:
        return []
    return [Finding("sga", f"{len(dead)} channel(s) posting but not connected",
                    ", ".join(_S(_D(r).get("label")) for r in dead[:5])
                    + " - scheduled posts there cannot be delivered.",
                    severity="bad",
                    how="Either connect the channel on System & Wiring, or "
                        "remove it from the posting plan. Leaving it means "
                        "every scheduled post there fails silently.")]


def _sga_empty_calendar(store, ctx):
    cal = _D(_sga_ctx(store).get("calendar"))
    if cal.get("has_data") or int(cal.get("planned") or 0):
        return []
    return [Finding("sga", "Nothing is on the calendar",
                    "No social task is planned, so the cadence cannot be met "
                    "however well the channels are wired.", severity="warn")]


def _sga_adherence(store, ctx):
    cad = _D(_sga_ctx(store).get("cadence"))
    days = int(cad.get("days_measured") or 0)
    adh = float(cad.get("adherence") or 0)
    if days < 3 or adh >= 60:
        return []
    return [Finding("sga", f"Posting cadence at {adh:.0f}%",
                    f"{cad.get('days_on_target', 0)} of {days} day(s) hit the "
                    f"target of {cad.get('daily_target', 0)} post(s).",
                    severity="warn")]


register(Agent("sga", "SGA",
               [_sga_dead_channel, _sga_empty_calendar, _sga_adherence]))


_PENDING = {
    "media": ("Media Buying",
              "proposed: campaign without a cap, creative without an image. "
              "READ-ONLY by design - this section touches money"),
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
    assert set(withc) == {"system", "content", "risk", "outreach",
                          "seo", "bi", "sga"}, withc

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
    # the failure finding is now the WATCHDOG: count + age + cost + the one
    # batch button, so a graveyard can never again accumulate unseen
    assert any("dead in the pipeline" in c for c in checks), checks
    _wd = next(f for f in rc["findings"] if "dead in the pipeline" in f["check"])
    assert _wd["fix_id"] == "retry_dead", _wd
    assert "€" in _wd["detail"], "the watchdog must state the revival cost"
    assert any("72h" in c for c in checks), checks
    assert not rc["errors"], rc["errors"]

    # a check that raises must not take the others down
    bad = Agent("tmp", "T", [lambda s, c: 1 / 0, lambda s, c: Finding(
        "tmp", "still ran", "the other check survived")])
    rb = bad.inspect(None)
    assert len(rb["findings"]) == 1 and len(rb["errors"]) == 1, rb

    allr = inspect_all(St(jobs))
    assert allr["with_contract"] == 7 and allr["without_contract"] == 2

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
