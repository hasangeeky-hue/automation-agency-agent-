"""
content_engine_orchestrator.py
============================================================================
SKILL 15 — the Orchestrator (pure code). The state machine that moves a job
across the blackboard (see content-engine-prompt-engineering.md SECTION 2/3/9).

Responsibilities (SECTION 9):
  - poll jobs, dispatch the ONE step for the current status
  - route per SECTION 4 (engine -> fallback)
  - validate + retry ONCE + escalate to fallback + fail loud (SECTION 5 #9)
  - enforce per-job and per-day budget caps (SECTION 5 #10)
  - honor the human approval gate before publish / send (SECTION 1 rule 2)
  - idempotency: a step's result is written to payload; the STATUS ADVANCE is
    the commit. Re-processing a not-yet-advanced status re-runs the step.

Skills never call each other. The orchestrator is the only mover.

STORAGE: coded against a JobStore interface with an in-memory implementation
so this runs and self-tests with zero infra. Swap InMemoryJobStore for a
Postgres-backed store (same 5 methods) in production; keep the status/advance
logic identical.

DATA PLUMBING SEAM: prepare_input(skill, job) is where the "70% code" lives —
it shapes each skill's INPUT from prior step outputs. The stubs here pass
job["payload"] through; fill them per skill when you wire real data sources.
============================================================================
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Callable, Optional

from content_engine_providers import (build_prompt, call_provider,
                                      OutputTruncated)

# How much more room a truncated skill gets on its retry, and the hard stop.
# A ceiling is not a reservation - unused tokens cost nothing - so the only
# real limit is the model's own maximum.
_CEILING_GROWTH = 2.0
_CEILING_CAP = 16000


def _supervise(skill, data, job) -> dict:
    """Ask the supervisor whether the brief was met. Never blocks on its own
    failure — a broken checker must not stop a good piece."""
    try:
        import content_engine_supervisor as SUP
        return SUP.supervise(skill, data, job)
    except Exception as e:
        log.warning("supervisor unavailable for %s: %s", skill, e)
        return {"ok": True, "failed": [], "note": ""}


def _grow_ceiling(spec) -> bool:
    """Give a truncated skill more room for its retry. True if it grew.

    The retry loop used to re-send the identical request with the identical
    ceiling, which truncates identically. This is what makes the retry mean
    something."""
    try:
        now = int(getattr(spec, "max_tokens", 0) or 0)
    except Exception:
        return False
    if now <= 0 or now >= _CEILING_CAP:
        return False
    bigger = min(_CEILING_CAP, int(now * _CEILING_GROWTH))
    if bigger <= now:
        return False
    try:
        spec.max_tokens = bigger
    except Exception:
        return False                      # frozen spec: cannot grow, say so
    log.warning("%s truncated at %d tokens; retrying with %d",
                getattr(spec, "skill_name", "?"), now, bigger)
    return True
from content_engine_schemas import SCHEMAS
from content_engine_prep import prepare_input
from content_engine_learning import record_cycle

log = logging.getLogger("content_engine")


# ---------------------------------------------------------------------------
# SECTION 4 config (kept here — this is the control plane).
# ---------------------------------------------------------------------------
FRONTIER_MODEL = "claude-opus-4-8"
CHEAP_MODEL    = "claude-haiku-4-5"
# Claude-only fallback: on validation failure the pipeline escalates to a
# different (stronger) Claude model, using the same ANTHROPIC_API_KEY. No
# second provider, no OpenAI account. (Trade-off: no cross-provider outage
# cover; kept the escalation-tier benefit.)
FRONTIER_ALT   = "claude-sonnet-5"
CHEAP_ALT      = "claude-sonnet-5"

ROUTES = {
    "site_intelligence":  {"engine": "code", "narrate": CHEAP_MODEL},
    "authority_backlinks":{"engine": "code", "narrate": CHEAP_MODEL},
    "competitor_intel":   {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT},
    "content_strategist": {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT},
    "content_producer":   {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT,
                           "image_prompts": CHEAP_MODEL},
    "seo_optimizer":      {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},
    "qa_compliance":      {"engine": FRONTIER_MODEL, "fallback": None},   # NO fallback
    "publisher":          {"engine": "code"},
    "analytics_funnel":   {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},
    "optimizer":          {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT},
    "segmenter":          {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},  # labels only
    "lead_sourcing":      {"engine": "code"},
    "lead_qualifier":     {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},
    "outreach_copy":      {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},
    "ads_optimizer":      {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT},  # money = judgment
    "media_buyer":        {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT},  # drafts paid campaigns = judgment
    "media_chat":         {"engine": FRONTIER_MODEL, "fallback": FRONTIER_ALT},  # discuss + revise the draft
    "reply_responder":    {"engine": CHEAP_MODEL, "fallback": FRONTIER_ALT},  # customer-facing
    "judge":              {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},  # S1 evaluator — cheap on purpose
    "content_planner":    {"engine": FRONTIER_ALT, "fallback": CHEAP_MODEL},  # proposes a plan you approve
    # ---- SEO engine skills ----
    "seo_fixer":          {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},  # rewrites titles/metas/alt — cheap on purpose
    "link_pitch":         {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},  # link-building outreach copy
    "seo_analyst":        {"engine": CHEAP_MODEL, "fallback": CHEAP_ALT},  # narrates the qualitative cards
    "orchestrator":       {"engine": "code"},
}

# Budget caps (SECTION 5 #10). Tune per client tier. The monthly cap is the
# founder's hard ceiling ("$200/month, all activity included") — the engine
# pauses new LLM steps once it is reached rather than overspending.
# These stay as the ENV-level defaults. The live values are read through
# budget_caps() on every check so a change in the dashboard takes effect on the
# worker's next loop without a restart — the same settings-first path every
# credential uses.
PER_JOB_BUDGET_USD = float(os.getenv("PER_JOB_BUDGET_USD", "0.50"))
PER_DAY_BUDGET_USD = float(os.getenv("PER_DAY_BUDGET_USD", "50.00"))
PER_MONTH_BUDGET_USD = float(os.getenv("PER_MONTH_BUDGET_USD", "200.00"))
BUDGET_KEY = "engine_budget_caps"
BUDGET_LOG_KEY = "engine_budget_log"


def budget_caps(store=None) -> dict:
    """The caps in force RIGHT NOW: settings first, env second, default last.

    Never raises. If the store is unreachable the env values still apply, so a
    database blip can never remove the ceiling."""
    caps = {"per_job": PER_JOB_BUDGET_USD,
            "per_day": PER_DAY_BUDGET_USD,
            "per_month": PER_MONTH_BUDGET_USD}
    try:
        st = store or (_STORE_GET() if callable(globals().get("_STORE_GET")) else None)
        saved = st.get_setting(BUDGET_KEY, None) if st is not None else None
        if isinstance(saved, dict):
            for k in caps:
                v = saved.get(k)
                if v not in (None, "") and float(v) > 0:
                    caps[k] = float(v)
    except Exception:
        pass
    return caps


def set_budget_caps(store, per_job=None, per_day=None, per_month=None,
                    spent_this_month=0.0, note="") -> dict:
    """Save new caps. A cap below what is already spent this month is REFUSED —
    it would halt the engine the moment it took effect, with no warning."""
    from datetime import datetime, timezone
    cur = budget_caps(store)
    want = dict(cur)
    for key, val in (("per_job", per_job), ("per_day", per_day),
                     ("per_month", per_month)):
        if val in (None, ""):
            continue
        try:
            f = float(val)
        except Exception:
            return {"ok": False, "error": f"{key} must be a number"}
        if f <= 0:
            return {"ok": False, "error": f"{key} must be greater than zero"}
        want[key] = f
    spent = float(spent_this_month or 0.0)
    if want["per_month"] < spent:
        return {"ok": False,
                "error": (f"Refused: a monthly cap of EUR {want['per_month']:,.2f} "
                          f"is below the EUR {spent:,.2f} already spent this "
                          f"month. Saving it would halt the engine immediately. "
                          f"The lowest safe value is EUR {spent:,.2f}."),
                "floor": round(spent, 2), "current": cur}
    if want["per_day"] > want["per_month"]:
        return {"ok": False,
                "error": ("The daily cap cannot exceed the monthly cap.")}
    if want["per_job"] > want["per_day"]:
        return {"ok": False,
                "error": ("A single job cannot be allowed more than a whole day.")}
    try:
        store.set_setting(BUDGET_KEY, want)
        log = list(store.get_setting(BUDGET_LOG_KEY, []) or [])
        log.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "from": cur, "to": want, "note": str(note or "")[:120]})
        store.set_setting(BUDGET_LOG_KEY, log[-60:])
    except Exception as e:
        return {"ok": False, "error": f"could not save: {e}"}
    return {"ok": True, "caps": want, "previous": cur,
            "message": (f"Caps saved. Monthly EUR {want['per_month']:,.0f}, "
                        f"daily EUR {want['per_day']:,.0f}, per job EUR "
                        f"{want['per_job']:,.2f}. Live on the worker's next loop "
                        f"— no restart.")}


def budget_log(store) -> list:
    try:
        return list(store.get_setting(BUDGET_LOG_KEY, []) or [])[::-1]
    except Exception:
        return []

# How long a published piece / sent campaign collects real traffic BEFORE the
# measurement gate opens automatically. This makes "wait N days" a real elapsed
# time, independent of how often the cron/worker ticks.
MEASURE_AFTER_DAYS = float(os.getenv("MEASURE_AFTER_DAYS", "7"))
# ...but a page and an email do not answer on the same schedule. An email is
# opened within days; a page has to be indexed and start ranking before its
# numbers mean anything, so measuring content at 7 days mostly measures how
# fast Google crawled. Per-pipeline, still env-overridable.
MEASURE_AFTER_DAYS_CONTENT = float(
    os.getenv("MEASURE_AFTER_DAYS_CONTENT", "21"))
MEASURE_AFTER_DAYS_OUTREACH = float(
    os.getenv("MEASURE_AFTER_DAYS_OUTREACH", str(MEASURE_AFTER_DAYS)))


def measure_days_for(job: dict) -> float:
    return (MEASURE_AFTER_DAYS_OUTREACH if job.get("type") == "outreach_campaign"
            else MEASURE_AFTER_DAYS_CONTENT)

# Injectable clock so tests are deterministic.
_CLOCK: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def set_clock(fn: Callable[[], datetime]) -> None:
    global _CLOCK
    _CLOCK = fn


def _now() -> datetime:
    return _CLOCK()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class SkillFailed(Exception):
    pass


class BudgetExceeded(Exception):
    pass


# ---------------------------------------------------------------------------
# JobStore interface + in-memory implementation
# ---------------------------------------------------------------------------
def ensure_failure_reason(job: dict) -> None:
    """NO JOB DIES WITHOUT SAYING WHY - enforced at the save choke point.

    Nine real jobs sat in the database as failed with an empty halt_reason:
    unfixable, because the first question about any failure is unanswerable.
    Every failure site is SUPPOSED to stamp a reason, but 'supposed to' is a
    convention, and conventions drift. The store is the one door every job
    passes through, so the guarantee lives here: a failed job with no reason
    gets an explicit 'unknown failure' stamp naming the last thing it did -
    visible and searchable, never silent.

    Defined ONCE and called by BOTH stores (in-memory and Postgres), per the
    shared-vocabulary rule: two hand-written copies of a rule is how this
    engine breaks."""
    if job.get("status") == "failed" and not str(job.get("halt_reason") or "").strip():
        runs = job.get("_runs") or {}
        last = max(runs.items(), key=lambda kv: str((kv[1] or {}).get("at", "")),
                   default=(None, None))[0] if runs else None
        job["halt_reason"] = (
            "unknown failure - no reason was recorded at the failure site "
            + (f"(last completed step: {last})" if last
               else "(no step ever completed)")
            + ". Stamped by the store so this job is never silent.")
        job["needs_human"] = True


class JobStore:
    def get(self, job_id: str) -> dict: ...
    def save(self, job: dict) -> None: ...
    def claim_next(self) -> Optional[dict]: ...        # returns a runnable job or None
    def add_daily_cost(self, amount: float) -> None: ...
    def daily_cost(self) -> float: ...


class InMemoryJobStore(JobStore):
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._daily: dict[str, float] = {}
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key: str, value) -> None:
        self._settings[key] = value

    def put(self, job: dict) -> None:      # test/setup helper
        self._jobs[job["job_id"]] = job

    def get(self, job_id: str) -> dict:
        return self._jobs[job_id]

    def save(self, job: dict) -> None:
        ensure_failure_reason(job)
        self._jobs[job["job_id"]] = job

    def claim_next(self) -> Optional[dict]:
        for job in self._jobs.values():
            if is_runnable(job):
                return job
        return None

    def list_jobs(self, status: Optional[str] = None) -> list:
        return [j for j in self._jobs.values()
                if status is None or j.get("status") == status]

    def add_daily_cost(self, amount: float) -> None:
        k = date.today().isoformat()
        self._daily[k] = self._daily.get(k, 0.0) + amount

    def daily_cost(self) -> float:
        return self._daily.get(date.today().isoformat(), 0.0)

    def monthly_cost(self) -> float:
        prefix = date.today().isoformat()[:7]   # YYYY-MM
        return round(sum(v for k, v in self._daily.items()
                         if k.startswith(prefix)), 6)


# ---------------------------------------------------------------------------
# Step definitions. kind:
#   "llm"   -> run an LLM skill via the provider layer
#   "code"  -> run a pure-code handler (CODE_HANDLERS)
#   "gate"  -> pure status set, no work
#   "wait"  -> human approval gate; only proceeds when job["approved"] is True
# ---------------------------------------------------------------------------
@dataclass
class Step:
    kind: str
    skill: Optional[str]
    next_status: str
    verdict_routed: bool = False   # qa_compliance: route on data["verdict"]
    gate_flag: str = "approved"    # for kind=="wait": which job flag unblocks it
    time_gate: bool = False        # for kind=="wait": also opens once measure_at elapses


# PIPELINE A (Content): 1 -> 3 -> 4 -> 5 -> 6 -> 7 -> [GATE] -> 8 -> [WAIT days]
#                       -> 9 -> 10 -> LEARN
FLOW_CONTENT = {
    "created":            Step("llm",  "site_intelligence", "site_ready"),
    "site_ready":         Step("llm",  "competitor_intel",  "competitor_ready"),
    "competitor_ready":   Step("llm",  "content_strategist","planned"),
    "planned":            Step("llm",  "content_producer",  "produced"),
    "produced":           Step("llm",  "seo_optimizer",     "seo_checked"),
    "seo_checked":        Step("llm",  "qa_compliance",     "AWAITING_APPROVAL",
                               verdict_routed=True),
    "AWAITING_APPROVAL":  Step("wait", None,                "publishing",
                               gate_flag="approved"),
    "publishing":         Step("code", "publisher",         "published"),
    # Measurement is time-decoupled: a piece has no traffic at publish time.
    # An n8n cron flips job["ready_to_measure"] once enough days have passed.
    "published":          Step("wait", None,                "measuring",
                               gate_flag="ready_to_measure", time_gate=True),
    "measuring":          Step("llm",  "analytics_funnel",  "measured"),
    "measured":           Step("llm",  "optimizer",         "learned"),
    "learned":            Step("learn", None,               "optimized"),
    "optimized":          Step("gate", None,                "optimized"),   # terminal
}

# PIPELINE B (Outreach): 12 -> 13 -> 11 -> 14w -> 7 -> [GATE] -> 14s
#                        -> [WAIT days] -> 9 -> 10 -> LEARN
FLOW_OUTREACH = {
    "created":            Step("code", "lead_sourcing",     "sourced"),
    "sourced":            Step("llm",  "lead_qualifier",    "qualified"),
    "qualified":          Step("llm",  "segmenter",         "segmented"),
    "segmented":          Step("llm",  "outreach_copy",     "drafted"),
    "drafted":            Step("llm",  "qa_compliance",     "AWAITING_APPROVAL",
                               verdict_routed=True),
    "AWAITING_APPROVAL":  Step("wait", None,                "sending",
                               gate_flag="approved"),
    "sending":            Step("code", "outreach_send",     "sent"),
    "sent":               Step("wait", None,                "tracking",
                               gate_flag="ready_to_measure", time_gate=True),
    "tracking":           Step("llm",  "analytics_funnel",  "tracked"),
    "tracked":            Step("llm",  "optimizer",         "learned"),
    "learned":            Step("learn", None,               "optimized"),
    "optimized":          Step("gate", None,                "optimized"),   # terminal
}

FLOWS = {"content_piece": FLOW_CONTENT, "outreach_campaign": FLOW_OUTREACH}

# Terminal / halted statuses the poller must not pick up.
TERMINAL = {"optimized", "revision_needed", "halted_budget", "failed"}


def flow_for(job: dict) -> dict:
    try:
        return FLOWS[job["type"]]
    except KeyError:
        raise SkillFailed(f"no flow for job type '{job.get('type')}'")


def current_step(job: dict) -> Step:
    return flow_for(job)[job["status"]]


def _wait_open(job: dict, step: Step) -> bool:
    """A wait gate opens when its manual flag is set (human approval, or a forced
    measurement) OR, for a time gate, once the measurement window has elapsed."""
    if job.get(step.gate_flag, False):
        return True
    if step.time_gate:
        ma = job.get("measure_at")
        if ma:
            try:
                return _now() >= datetime.fromisoformat(ma)
            except ValueError:
                return False
    return False


def _maybe_stamp_measure(job: dict) -> None:
    """When a job arrives at a time-gated wait (published / sent), stamp when its
    measurement window opens, so the gate can open by elapsed time."""
    step = flow_for(job).get(job.get("status"))
    if (step and step.kind == "wait" and step.time_gate
            and not job.get("measure_at")):
        job["measure_at"] = (
            _now() + timedelta(days=measure_days_for(job))).isoformat()


PROPOSALS_KEY = "engine_rewrite_proposals"
MAX_PROPOSALS = 200


def _queue_proposal(store, proposal: dict) -> None:
    """Put a proposal in front of a person. It is a card, not an action — the
    engine has no path from here to spending or publishing without approval."""
    try:
        cur = list(store.get_setting(PROPOSALS_KEY, []) or [])
    except Exception:
        return
    jid = str(proposal.get("job_id", ""))
    if any(str(p.get("job_id", "")) == jid for p in cur if isinstance(p, dict)):
        return                                   # one proposal per piece, ever
    proposal["at"] = _now().isoformat()
    proposal["status"] = "pending"
    cur.append(proposal)
    try:
        store.set_setting(PROPOSALS_KEY, cur[-MAX_PROPOSALS:])
    except Exception:
        log.warning("could not persist the rewrite proposal for %s", jid)


def rewrite_proposals(store) -> list:
    """Pending proposals, newest first — read by the cockpit approval queue."""
    try:
        rows = list(store.get_setting(PROPOSALS_KEY, []) or [])
    except Exception:
        return []
    return [p for p in rows[::-1]
            if isinstance(p, dict) and p.get("status") == "pending"]


def resolve_proposal(store, job_id: str, accept: bool, note: str = "") -> dict:
    """A person accepted or declined. Either way it leaves the queue and the
    decision is recorded — declining with a reason is how the engine learns."""
    try:
        rows = list(store.get_setting(PROPOSALS_KEY, []) or [])
    except Exception:
        return {"ok": False, "error": "proposals are unreadable"}
    hit = None
    for p in rows:
        if isinstance(p, dict) and str(p.get("job_id", "")) == str(job_id) \
                and p.get("status") == "pending":
            p["status"] = "accepted" if accept else "declined"
            p["resolved_at"] = _now().isoformat()
            p["note"] = str(note or "")[:400]
            hit = p
            break
    if not hit:
        return {"ok": False, "error": "no pending proposal for that piece"}
    try:
        store.set_setting(PROPOSALS_KEY, rows)
    except Exception:
        return {"ok": False, "error": "could not save"}
    return {"ok": True, "message": ("Queued for rewrite." if accept
                                    else "Declined — recorded."), "proposal": hit}


def _collect_for(job: dict, skill: str, store=None) -> str:
    """Fetch the real-world outcome a reasoning step needs, just before it runs.

    Returns "" when the step may proceed, or a plain-English REASON when there
    is nothing real to reason about — in which case the caller skips the model
    instead of paying it to describe zeros.

    Only two skills consume outcomes; everything else passes straight through.
    Never raises: a collection failure degrades to 'unmeasured, because X',
    never to a crashed tick."""
    if skill not in ("analytics_funnel", "optimizer"):
        return ""
    try:
        import content_engine_collect as COL
    except Exception as e:                                    # pragma: no cover
        return f"the collector module is unavailable: {e}"
    payload = job.setdefault("payload", {})
    try:
        if skill == "analytics_funnel":
            a = COL.analytics_for(job, store)
            payload["analytics"] = a
            return "" if COL.is_measured(a) else str(
                a.get("unavailable") or "this outcome could not be measured")
        p = COL.performance_for(job, store)
        payload["performance"] = p
        return "" if p.get("measured") else str(
            p.get("unavailable") or "there is no measured performance to optimise")
    except Exception as e:                                    # pragma: no cover
        log.exception("collector failed for %s/%s", job.get("job_id"), skill)
        return f"collection failed ({type(e).__name__}): {str(e)[:160]}"


def is_runnable(job: dict) -> bool:
    """A job the poller can advance right now."""
    status = job["status"]
    if status in TERMINAL:
        return False
    step = flow_for(job).get(status)
    if step is None:
        return False
    if step.kind == "wait" and not _wait_open(job, step):
        return False   # blocked on a gate (human approval / measurement window)
    return True


# ---------------------------------------------------------------------------
# Pure-code skill handlers (SECTION 9) live in content_engine_code_skills and
# are idempotent (publish/send guard on an external ref). Swap their I/O hooks
# for real data sources there.
# ---------------------------------------------------------------------------
from content_engine_code_skills import CODE_HANDLERS  # noqa: E402


# ---------------------------------------------------------------------------
# Data-plumbing seam: prepare_input(skill, job) is imported from
# content_engine_prep (the "70% code"). It shapes each skill's INPUT from prior
# step outputs on the blackboard. See that module to add/adjust mappers.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Budget helpers
# ---------------------------------------------------------------------------
def over_budget(job: dict, store: JobStore) -> Optional[str]:
    _caps = budget_caps(store)
    if job.get("cost_so_far_usd", 0.0) >= _caps["per_job"]:
        return f"per-job cap ${_caps['per_job']} reached"
    if store.daily_cost() >= _caps["per_day"]:
        return f"per-day cap ${_caps['per_day']} reached"
    monthly = getattr(store, "monthly_cost", None)
    if callable(monthly) and monthly() >= _caps["per_month"]:
        return f"per-month cap ${_caps['per_month']} reached"
    return None


def log_cost(job: dict, model: str, cost: float, store: JobStore) -> None:
    job["cost_so_far_usd"] = round(job.get("cost_so_far_usd", 0.0) + cost, 6)
    job.setdefault("model_log", []).append({"model": model, "cost_usd": cost})
    store.add_daily_cost(cost)
    try:                                   # per-API meter: Claude/Anthropic spend
        import content_engine_connectors as _C
        _C.record_api_spend("anthropic", cost)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# LLM skill runner (SECTION 4 dispatch + SECTION 5 #9 retry policy).
# Returns (data, total_cost). Raises on unrecoverable failure.
# Overridable via _LLM_HOOK for tests.
# ---------------------------------------------------------------------------
import hashlib as _hashlib


def _prompt_version(skill: str) -> str:
    """Short, stable hash of a skill's prompt text — its version. A silent prompt
    edit changes this, so every job records exactly which prompt produced it."""
    try:
        from content_engine_prompts import SKILL_PROMPTS
        txt = SKILL_PROMPTS.get(skill, "") or ""
        return _hashlib.sha1(txt.encode("utf-8")).hexdigest()[:8] if txt else ""
    except Exception:
        return ""


def _stamp_run(job: dict, skill: str, model: str) -> None:
    """S7 versioning: pin which model + prompt version produced this step, so a
    silent prompt/model change on Tuesday isn't a debugging ghost on Wednesday."""
    try:
        runs = job.setdefault("_runs", {})
        runs[skill] = {"model": model, "prompt_version": _prompt_version(skill),
                       "at": _now().isoformat()}
    except Exception:
        pass


def run_llm_skill(job: dict, skill: str, store: JobStore) -> tuple[dict, float]:
    route = ROUTES[skill]
    # Stage the skill-specific INPUT into the job payload the builder reads.
    staged = dict(job)
    staged["payload"] = prepare_input(skill, job)
    spec = build_prompt(skill, staged)
    schema = SCHEMAS.get(skill)

    total_cost = 0.0
    # "code+narrate" skills (site_intelligence, authority_backlinks) carry
    # engine="code" — the heavy work is in prepare_input; the LLM part runs on the
    # narrate/label model. Resolve that here (mirrors api_taste_skill) so the real
    # pipeline never hands "code" to the LLM provider.
    engine = route["engine"]
    if engine == "code":
        engine = route.get("narrate") or route.get("label") or CHEAP_MODEL
    models = [engine, route.get("fallback")]
    # WHY THIS LOOP LOOKS LIKE THIS NOW.
    #
    # OutputTruncated was raised by call_provider and caught by nobody, so it
    # flew straight past this retry machinery - the loop existed and truncation
    # never reached it. And a retry that re-sends the identical request with the
    # identical ceiling truncates identically, so catching it alone would have
    # changed nothing. A truncation is RECOVERABLE INFORMATION: it says exactly
    # what went wrong and exactly what to change. Grow the ceiling and go again.
    #
    # Raising max_tokens costs nothing unless the tokens are used - it is a
    # ceiling, not a reservation.
    last_why, attempts = [], 0
    for model in models:
        if not model:
            break
        for attempt in (1, 2):   # retry ONCE per model, then escalate
            reason = over_budget(job, store)
            if reason:
                raise BudgetExceeded(f"{job['job_id']}: {reason}")
            attempts += 1
            try:
                result = call_provider(model, spec)
            except (OutputTruncated, json.JSONDecodeError) as e:
                # CATCH THE CLASS, NOT THE CONFESSION. Truncation arrives two
                # ways: the provider admits it (OutputTruncated) or the torn
                # text hits a parser first (JSONDecodeError). Both mean "ran
                # out of room"; only one used to reach this recovery - the
                # other flew past to the catch-all and the piece was filed
                # dead. providers._parse_model_json now converts at the
                # source; this belt stays in case a future provider path
                # forgets, because 15 real pieces are why.
                last_why = [str(e)[:180]]
                if _grow_ceiling(spec):
                    continue          # same model, more room
                # at the cap: fail HONESTLY, with the reason, instead of the
                # bare re-raise that landed as "degraded (OutputTruncated)"
                raise SkillFailed(
                    f"{skill}: still truncated at the {spec.max_tokens}-token "
                    f"cap after growing. {str(e)[:200]}") from e
            total_cost += result.cost_usd
            ok, errs = schema.validate(result.data) if schema else (True, [])
            if ok and "error" not in result.data:
                # THE SUPERVISOR. The schema says the shape is right; this asks
                # whether the BRIEF was met — 4 sections, 4 image prompts, 650
                # words, a CTA, the keyword. Nine skills each handed their work
                # to the next one and nothing ever looked at it, so a blog with
                # no images and two sections reached the founder looking
                # finished. It counts; it never spends, publishes or sends.
                verdict = _supervise(skill, result.data, job)
                if verdict.get("ok"):
                    _stamp_run(job, skill, model)   # S7 version stamp
                    return result.data, total_cost
                # Feed the SPECIFIC misses back in. Re-rolling the same prompt
                # gets the same dice; telling the writer "1 of 4 sections" does
                # not. revision_note is the existing path prepare_input already
                # reads, so the correction reaches the prompt.
                last_why = [f"brief not met: {', '.join(verdict['failed'])} "
                            f"({'; '.join(verdict.get('detail', []))})"]
                job.setdefault("payload", {})["revision_note"] = verdict["note"]
                job["payload"]["supervisor_note"] = verdict["note"]
                job["payload"]["supervisor_failed"] = verdict["failed"]
                log.warning("%s: supervisor rejected attempt %d — %s",
                            skill, attempts, ", ".join(verdict["failed"]))
                try:                       # rebuild so the note reaches the prompt
                    spec = build_prompt(skill, job)
                except Exception:
                    pass
                continue
            # invalid shape or the {"error":...} escape -> retry/escalate.
            # KEEP the reason: this used to be , so every failure
            # reported "no model produced a valid result" and nothing else.
            last_why = [str(x)[:260] for x in (errs or [])][:3] or                 [str(result.data.get("error", ""))[:180]] or ["unknown"]
    raise SkillFailed(
        f"{skill}: no model produced a valid result after {attempts} "
        f"attempt(s) across {len([m for m in models if m])} model(s). "
        f"Last problem: {'; '.join(last_why) or 'not recorded'}")


# Indirection so tests can stub the LLM layer without touching providers.
_LLM_HOOK: Callable[[dict, str, JobStore], tuple[dict, float]] = run_llm_skill

# Optional hook to mirror a finished job to an external hub (Google Sheets +
# Drive). Best-effort; connectors.wire_all() sets it when Google is configured.
# Postgres remains the source of truth; a mirror failure never affects the job.
MIRROR_FN: Optional[Callable[[dict], None]] = None
_MIRROR_STATES = {"published", "sent", "optimized"}


# ---------------------------------------------------------------------------
# advance(): execute exactly ONE step for the job's current status.
# Returns the job's status AFTER the step (unchanged if it is waiting/terminal).
# ---------------------------------------------------------------------------
def advance(job: dict, store: JobStore) -> str:
    status = job["status"]
    if status in TERMINAL:
        return status
    step = flow_for(job).get(status)
    if step is None:
        raise SkillFailed(f"no step for status '{status}' in {job['type']}")

    try:
        if step.kind == "wait":
            if _wait_open(job, step):
                job["status"] = step.next_status
            # else: gate not open — DON'T early-return. Fall through to the save
            # below so updated_at is bumped and this parked job rotates to the
            # BACK of the claim queue. A time-gated 'published' job that keeps its
            # old updated_at pins the front of ORDER BY updated_at ASC and gets
            # re-claimed forever, busy-looping the worker and starving newer jobs.

        elif step.kind == "gate":
            job["status"] = step.next_status

        elif step.kind == "learn":
            # THE LEARNING EDGE (10 -> 4): fold the Optimizer's output into the
            # client's durable playbook so the next cycle is smarter.
            #
            # ...but ONLY if something was actually measured. Folding an
            # unmeasured cycle in would teach the playbook that whatever we
            # happened to do produced nothing, and every later decision would
            # inherit that. Silence is not evidence.
            _opt = job["payload"].get("optimizer", {}) or {}
            if job.get("unmeasured_reason") or _opt.get("measured") is False:
                job["learned_nothing"] = job.get("unmeasured_reason") or \
                    "nothing was measured for this cycle"
                log.info("job %s reached learn with nothing measured: %s",
                         job.get("job_id"), job["learned_nothing"])
            else:
                record_cycle(job.get("client_id", ""), _opt)
                # A MEASURED-poor piece earns a proposal in the approval queue.
                # Deliberately a proposal and not a rewrite: rewriting spends
                # money and republishes to a live site, and both stay behind the
                # human gate.
                try:
                    import content_engine_collect as _COL
                    prop = _COL.rewrite_proposal(job)
                    if prop and store is not None:
                        _queue_proposal(store, prop)
                        job["rewrite_proposed"] = True
                except Exception:
                    log.exception("could not queue a rewrite proposal for %s",
                                  job.get("job_id"))
            _maybe_spawn_next_cycle(job, store)
            job["status"] = step.next_status

        elif step.kind == "code":
            out = CODE_HANDLERS[step.skill](job)
            job["payload"][step.skill] = out
            _stamp_run(job, step.skill, "code")     # S7 version stamp
            job["status"] = step.next_status

        elif step.kind == "llm":
            # THE RETURN ARROW. Before a step that reasons about outcomes, go
            # and fetch the outcomes. Without this, analytics_funnel received
            # {sessions: 0, conv_rate: 0} for every piece ever published and the
            # playbook recorded conclusions drawn from those zeros.
            skip = _collect_for(job, step.skill, store)
            if skip:
                # Nothing to reason about, and reasoning costs money. Record why,
                # skip the model, advance. An unmeasured job is NOT a failed one
                # and must not be marked as one.
                job["payload"][step.skill] = {"measured": False,
                                              "unavailable": skip}
                job["unmeasured_reason"] = skip
                _stamp_run(job, step.skill, "skipped-unmeasured")
                job["status"] = step.next_status
            else:
                reason = over_budget(job, store)      # orchestrator-level gate
                if reason:
                    raise BudgetExceeded(f"{job['job_id']}: {reason}")
                data, cost = _LLM_HOOK(job, step.skill, store)
                log_cost(job, ROUTES[step.skill]["engine"], cost, store)
                job["payload"][step.skill] = data
                if step.verdict_routed:                # qa_compliance
                    if data.get("verdict") == "pass":
                        job["status"] = step.next_status      # -> AWAITING_APPROVAL
                    else:
                        job["status"] = "revision_needed"     # halt, needs a human
                        job["qa_verdict"] = data.get("verdict")
                else:
                    job["status"] = step.next_status
        else:
            raise SkillFailed(f"unknown step kind '{step.kind}'")

    except BudgetExceeded as e:
        job["status"] = "halted_budget"
        job["halt_reason"] = str(e)
    except SkillFailed as e:
        job["status"] = "failed"
        job["halt_reason"] = str(e)
        job["needs_human"] = True
    except Exception as e:
        # S7 DEGRADED MODE: a dead tool, a network drop, an unexpected bug in ANY
        # agent must never crash the tick and take the whole engine down. Narrow
        # this one job to a clean stop, hand it to a human, and let the loop go on.
        job["status"] = "failed"
        # 400 chars, not 200. Two API-refused jobs carried the request shape
        # AND the API's own explanation - and the old cap cut the reason off
        # exactly at "Original: Error cod". A diagnostic that truncates the
        # diagnosis is the disease it treats.
        job["halt_reason"] = f"degraded ({type(e).__name__}): {str(e)[:400]}"
        job["needs_human"] = True
        try:
            import logging as _lg
            _lg.getLogger("content_engine").exception(
                "degraded: step failed for job %s", job.get("job_id"))
        except Exception:
            pass

    _maybe_stamp_measure(job)      # open a measurement window on arrival at published/sent
    job["updated_at"] = _now().isoformat()
    store.save(job)

    # Mirror finished jobs to the Google hub (Sheets + Drive), once per state.
    if MIRROR_FN and job.get("status") in _MIRROR_STATES:
        _done = job.setdefault("_mirrored", [])
        if job["status"] not in _done:
            try:
                MIRROR_FN(job)
                _done.append(job["status"])
                store.save(job)
            except Exception:
                pass   # best-effort; Postgres is the source of truth

    return job["status"]


def _maybe_spawn_next_cycle(job: dict, store: JobStore) -> None:
    """Close the loop by queuing the next production cycle for the same client,
    carrying forward the code-collected inputs. The new job reads the freshly
    updated playbook via prepare_input, so it is smarter than this one. Bounded
    by config.max_cycles to prevent runaway. OFF unless config.auto_loop is set
    (recommended driver for 'day by day' is an n8n cron creating cycles)."""
    cfg = job.get("payload", {}).get("config", {}) or {}
    if not cfg.get("auto_loop"):
        return
    cycle = cfg.get("_cycle", 0) + 1
    if cycle > cfg.get("max_cycles", 3):
        return
    next_cfg = dict(cfg)
    next_cfg["_cycle"] = cycle
    next_cfg["produce_index"] = cfg.get("produce_index", 0) + 1  # next calendar row
    child = new_job(
        f"{job['job_id']}::cycle{cycle}", job["type"], job.get("brand", {}),
        {
            # carry forward the code-collected raw inputs; drop prior LLM results
            "config": next_cfg,
            "audit": job["payload"].get("audit", {}),
            "competitors": job["payload"].get("competitors", []),
            "analytics": {}, "performance": {},
        })
    store.save(child)


def revive(job: dict) -> dict:
    """THE ROAD OUT OF THE GRAVEYARD - a recovery edge, fired by a human click.

    The state machine had forward gears only: 'failed' and 'revision_needed'
    were TERMINAL, so 37 real pieces sat dead for nine days AFTER their
    underlying bugs were fixed, because resurrection was never a transition.
    Worse, revision_needed - QA literally saying "revise this" - was filed in
    the same bucket as dead.

    TERMINAL itself stays as the passive-loop guard: advance() raises on any
    status with no step (L693), so simply shrinking the set would make the
    worker crash-loop on revived states. The edge is this function instead,
    and it only ever fires on a click, because re-running spends money.

      revision_needed -> re-enters at the writing step, carrying QA's verdict
                         as revision_note (the field prepare_input already
                         feeds into the writer's next prompt)
      failed          -> resumes at the step AFTER the last one that completed
                         (from the _runs stamps), so finished work is not
                         re-bought

    Never raises; refuses anything not actually dead."""
    status = str(job.get("status") or "")
    payload = job.setdefault("payload", {})
    if status == "revision_needed":
        qa = (payload.get("qa_compliance") or {}) if isinstance(payload, dict) else {}
        issues = qa.get("issues") if isinstance(qa.get("issues"), list) else []
        notes = "; ".join(
            f"{(i.get('issue') or '').strip()} -> {(i.get('fix') or '').strip()}"
            for i in issues if isinstance(i, dict) and i.get("issue"))[:600]
        payload["revision_note"] = (notes or str(job.get("qa_verdict") or "")
                                    or "QA asked for a revision.")
        job["status"] = ("planned" if flow_for(job) is FLOW_CONTENT
                         else "segmented")   # re-enter at the writing step
    elif status == "failed":
        runs = job.get("_runs") or {}
        resume = "created"
        for st, step in flow_for(job).items():   # dicts keep pipeline order
            if step.skill and step.skill in runs:
                resume = step.next_status
        job["status"] = resume
    else:
        return {"ok": False,
                "message": f"{job.get('job_id')}: status is '{status}' - "
                           f"only failed or revision_needed pieces revive"}
    job["halt_reason"] = ""
    job["needs_human"] = False
    return {"ok": True, "job_id": str(job.get("job_id") or ""),
            "resumed_at": job["status"]}


def run_until_blocked(job: dict, store: JobStore, max_steps: int = 50) -> str:
    """Advance a job until it hits the human gate, a terminal, or a wait/halt."""
    for _ in range(max_steps):
        before = job["status"]
        after = advance(job, store)
        if after == before:            # wait gate or terminal — no progress
            return after
        if after in TERMINAL:
            return after
    raise SkillFailed(f"{job['job_id']}: exceeded max_steps (loop?)")


def tick(store: JobStore) -> Optional[str]:
    """One poll cycle: claim a runnable job and advance it to its next block.
    Honors the dashboard's global pause switch (get_setting('paused'))."""
    getset = getattr(store, "get_setting", None)
    if callable(getset) and getset("paused", False):
        return None
    job = store.claim_next()
    if job is None:
        return None
    before = job["status"]
    status = run_until_blocked(job, store)
    # If the job made NO forward progress and is parked on a time gate (an
    # already-'published' job re-touched while it waits days for its measurement
    # window), report idle so the worker sleeps instead of busy-spinning. It has
    # already rotated to the back of the queue, so active jobs get claimed first
    # next cycle. A job that genuinely advanced this tick (even ending at
    # 'published') still reports its real status.
    if status == before:
        step = flow_for(job).get(status)
        if step is not None and step.kind == "wait" and getattr(step, "time_gate", False) \
                and not _wait_open(job, step):
            return None
    return status


def new_job(job_id: str, job_type: str, brand: dict, payload: dict) -> dict:
    now = _now().isoformat()
    return {
        "job_id": job_id, "type": job_type, "status": "created",
        "client_id": brand.get("brand_name", ""), "brand": brand,
        "payload": payload, "approved": False,
        "cost_so_far_usd": 0.0, "model_log": [],
        "created_at": now, "updated_at": now,   # power trends / calendar / projection
    }


def approve(job_id: str, store: JobStore) -> None:
    """The single human approval action (SECTION 1 rule 2)."""
    job = store.get(job_id)
    job["approved"] = True
    store.save(job)


# How long a piece waits for a human before autonomy releases it (Phase 2:
# "if I don't respond, the agent runs the plan on its own").
AUTONOMY_GRACE_HOURS = float(os.getenv("AUTONOMY_GRACE_HOURS", "24"))


def auto_approve_stale(store: JobStore) -> int:
    """When the dashboard's Autonomy switch is ON, auto-approve pieces that have
    waited at the human gate longer than AUTONOMY_GRACE_HOURS — so the machine
    keeps moving if the founder doesn't respond. Off by default (autonomy=False).
    Returns how many were released."""
    getset = getattr(store, "get_setting", None)
    if not (callable(getset) and getset("autonomy", False)):
        return 0
    if not hasattr(store, "list_jobs"):
        return 0
    cutoff = _now() - timedelta(hours=AUTONOMY_GRACE_HOURS)
    released = 0
    for j in store.list_jobs("AWAITING_APPROVAL"):
        if j.get("approved"):
            continue   # already released; a tick will advance it
        ua = j.get("updated_at")
        try:
            stale = bool(ua) and datetime.fromisoformat(ua) <= cutoff
        except ValueError:
            stale = False
        if stale:
            j["approved"] = True
            j["auto_approved"] = True
            store.save(j)
            released += 1
    return released


# ---------------------------------------------------------------------------
# Self-check: drive a content job through the full state machine with the LLM
# layer stubbed (no API, no cost surprises). Verifies:
#   - it stops at the human gate and will not publish unapproved
#   - approval lets it finish
#   - qa "block" routes to revision_needed
#   - budget cap halts the job
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # NOTE: assign the module global directly. Do NOT `import
    # content_engine_orchestrator as O` here — running as a script makes that a
    # second module object, and advance()/tick() (living in __main__) would
    # still read __main__._LLM_HOOK, not the patched copy.

    # Stub the LLM layer: return schema-shaped-enough data + a small cost.
    def fake_llm(job, skill, store):
        if skill == "qa_compliance":
            return {"verdict": "pass"}, 0.01
        return {"ok": True}, 0.01
    _LLM_HOOK = fake_llm

    store = InMemoryJobStore()

    # 1) Happy path halts at the gate, then completes on approval.
    job = new_job("job_A", "content_piece",
                  {"brand_name": "Anthropos"}, {"type": "blog"})
    store.put(job)
    status = tick(store)
    assert status == "AWAITING_APPROVAL", f"expected gate, got {status}"
    assert job["payload"].get("published_ref") is None, "published before approval!"
    approve("job_A", store)
    status = tick(store)
    assert status == "published", f"expected publish then measure-wait, got {status}"
    assert job["payload"]["publisher"]["published_ref"] == "pub_job_A"
    # measurement gate: no traffic yet — an n8n cron flips this after N days.
    job["ready_to_measure"] = True
    store.save(job)
    status = tick(store)
    assert status == "optimized", f"expected optimized, got {status}"

    # 2) QA block routes to revision_needed (never reaches the gate).
    def fake_block(job, skill, store):
        if skill == "qa_compliance":
            return {"verdict": "block"}, 0.01
        return {"ok": True}, 0.01
    _LLM_HOOK = fake_block
    job2 = new_job("job_B", "content_piece", {"brand_name": "X"}, {"type": "blog"})
    store.put(job2)
    status = run_until_blocked(job2, store)
    assert status == "revision_needed", f"expected revision_needed, got {status}"

    # 3) Budget cap halts the job.
    _LLM_HOOK = lambda job, skill, store: ({"ok": True}, 999.0)
    job3 = new_job("job_C", "content_piece", {"brand_name": "Y"}, {"type": "blog"})
    store.put(job3)
    status = run_until_blocked(job3, store)
    assert status == "halted_budget", f"expected halted_budget, got {status}"

    # 4) Time-based measurement gate: opens by ELAPSED TIME, no manual flag,
    #    independent of how often we tick. Fresh store (test 3 spent the daily cap).
    _LLM_HOOK = fake_llm
    store4 = InMemoryJobStore()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    set_clock(lambda: base)
    job4 = new_job("job_T", "content_piece", {"brand_name": "Z"}, {"type": "blog"})
    job4["approved"] = True                      # pre-approve so it flies to publish
    store4.put(job4)
    status = run_until_blocked(job4, store4)
    assert status == "published", f"expected published, got {status}"
    assert job4.get("measure_at"), "measure_at was not stamped on publish"
    assert not is_runnable(job4), "should be blocked until the window elapses"
    # A page and an email do not answer on the same schedule: content waits 21
    # days so the measurement reflects ranking rather than crawl speed.
    _days = measure_days_for(job4)
    assert _days == MEASURE_AFTER_DAYS_CONTENT == 21.0, _days
    assert measure_days_for({"type": "outreach_campaign"}) ==         MEASURE_AFTER_DAYS_OUTREACH, "outreach must keep the short window"
    set_clock(lambda: base + timedelta(days=float(MEASURE_AFTER_DAYS) + 1))
    assert not is_runnable(job4), "8 days must NOT open a 21-day content window"
    set_clock(lambda: base + timedelta(days=_days + 1))
    assert is_runnable(job4), "window elapsed -> job should be runnable"
    status = run_until_blocked(job4, store4)
    assert status == "optimized", f"expected optimized after window, got {status}"

    # ---- THE RETURN ARROW: an unmeasurable outcome must report WHY and must
    # NOT be handed to the model as zeros, must NOT be recorded as a failure,
    # and must NOT teach the playbook anything.
    assert job4.get("unmeasured_reason"), (
        "GA4 is not connected in a test env, so this job MUST carry a stated "
        "reason rather than silently measuring zero")
    _an = job4["payload"].get("analytics", {})
    assert _an.get("measured") is False and _an.get("metrics") == {}, (
        f"an unmeasured job must carry NO numbers, got {_an}")
    assert job4.get("learned_nothing"), (
        "an unmeasured cycle must not be folded into the playbook")
    assert job4["status"] == "optimized", "unmeasured is not failed"
    set_clock(lambda: datetime.now(timezone.utc))  # restore clock

    # 5) A MEASURED-poor piece earns a PROPOSAL that still waits for a person.
    import content_engine_collect as _COL
    store5 = InMemoryJobStore()
    _poor = {"job_id": "quiet", "type": "content_piece", "payload": {
        "content_producer": {"title": "A quiet piece"},
        "analytics": {"measured": True, "period": "last 21d", "page": "/quiet",
                      "metrics": {"sessions": 2, "conv_rate": 0.0}}}}
    _queue_proposal(store5, _COL.rewrite_proposal(_poor))
    _q = rewrite_proposals(store5)
    assert len(_q) == 1 and _q[0]["requires_approval"] is True, _q
    _queue_proposal(store5, _COL.rewrite_proposal(_poor))
    assert len(rewrite_proposals(store5)) == 1, "one proposal per piece, ever"
    assert resolve_proposal(store5, "quiet", False, "wrong keyword")["ok"]
    assert rewrite_proposals(store5) == [], "resolved proposals leave the queue"
    assert resolve_proposal(store5, "quiet", True)["ok"] is False, "no double-resolve"

    _LLM_HOOK = run_llm_skill  # restore
    print("OK — orchestrator verified: human gate, completion, QA-block "
          "routing, budget halt, per-pipeline measurement windows, and THE "
          "RETURN ARROW: an unmeasurable outcome states why, skips the "
          "model, is not a failure, and teaches the playbook nothing. "
          "(LLM stubbed; no API.)")
