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

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Callable, Optional

from content_engine_providers import build_prompt, call_provider
from content_engine_schemas import SCHEMAS
from content_engine_prep import prepare_input
from content_engine_learning import record_cycle


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
    "reply_responder":    {"engine": CHEAP_MODEL, "fallback": FRONTIER_ALT},  # customer-facing
    "orchestrator":       {"engine": "code"},
}

# Budget caps (SECTION 5 #10). Tune per client tier.
PER_JOB_BUDGET_USD = float(os.getenv("PER_JOB_BUDGET_USD", "0.50"))
PER_DAY_BUDGET_USD = float(os.getenv("PER_DAY_BUDGET_USD", "50.00"))

# How long a published piece / sent campaign collects real traffic BEFORE the
# measurement gate opens automatically. This makes "wait N days" a real elapsed
# time, independent of how often the cron/worker ticks.
MEASURE_AFTER_DAYS = float(os.getenv("MEASURE_AFTER_DAYS", "7"))

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

    def put(self, job: dict) -> None:      # test/setup helper
        self._jobs[job["job_id"]] = job

    def get(self, job_id: str) -> dict:
        return self._jobs[job_id]

    def save(self, job: dict) -> None:
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
        job["measure_at"] = (_now() + timedelta(days=MEASURE_AFTER_DAYS)).isoformat()


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
    if job.get("cost_so_far_usd", 0.0) >= PER_JOB_BUDGET_USD:
        return f"per-job cap ${PER_JOB_BUDGET_USD} reached"
    if store.daily_cost() >= PER_DAY_BUDGET_USD:
        return f"per-day cap ${PER_DAY_BUDGET_USD} reached"
    return None


def log_cost(job: dict, model: str, cost: float, store: JobStore) -> None:
    job["cost_so_far_usd"] = round(job.get("cost_so_far_usd", 0.0) + cost, 6)
    job.setdefault("model_log", []).append({"model": model, "cost_usd": cost})
    store.add_daily_cost(cost)


# ---------------------------------------------------------------------------
# LLM skill runner (SECTION 4 dispatch + SECTION 5 #9 retry policy).
# Returns (data, total_cost). Raises on unrecoverable failure.
# Overridable via _LLM_HOOK for tests.
# ---------------------------------------------------------------------------
def run_llm_skill(job: dict, skill: str, store: JobStore) -> tuple[dict, float]:
    route = ROUTES[skill]
    # Stage the skill-specific INPUT into the job payload the builder reads.
    staged = dict(job)
    staged["payload"] = prepare_input(skill, job)
    spec = build_prompt(skill, staged)
    schema = SCHEMAS.get(skill)

    total_cost = 0.0
    models = [route["engine"], route.get("fallback")]
    for model in models:
        if not model:
            break
        for attempt in (1, 2):   # retry ONCE per model, then escalate
            reason = over_budget(job, store)
            if reason:
                raise BudgetExceeded(f"{job['job_id']}: {reason}")
            result = call_provider(model, spec)
            total_cost += result.cost_usd
            ok, _ = schema.validate(result.data) if schema else (True, [])
            if ok and "error" not in result.data:
                return result.data, total_cost
            # invalid shape or model returned the {"error":...} escape -> retry/escalate
    raise SkillFailed(f"{skill}: no model produced a valid result")


# Indirection so tests can stub the LLM layer without touching providers.
_LLM_HOOK: Callable[[dict, str, JobStore], tuple[dict, float]] = run_llm_skill


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
            if not _wait_open(job, step):
                return status                      # blocked on a gate
            job["status"] = step.next_status

        elif step.kind == "gate":
            job["status"] = step.next_status

        elif step.kind == "learn":
            # THE LEARNING EDGE (10 -> 4): fold the Optimizer's output into the
            # client's durable playbook so the next cycle is smarter.
            record_cycle(job.get("client_id", ""),
                         job["payload"].get("optimizer", {}))
            _maybe_spawn_next_cycle(job, store)
            job["status"] = step.next_status

        elif step.kind == "code":
            out = CODE_HANDLERS[step.skill](job)
            job["payload"][step.skill] = out
            job["status"] = step.next_status

        elif step.kind == "llm":
            reason = over_budget(job, store)      # orchestrator-level gate
            if reason:
                raise BudgetExceeded(f"{job['job_id']}: {reason}")
            data, cost = _LLM_HOOK(job, step.skill, store)
            log_cost(job, ROUTES[step.skill]["engine"], cost, store)
            job["payload"][step.skill] = data
            if step.verdict_routed:                # qa_compliance
                if data.get("verdict") == "pass":
                    job["status"] = step.next_status          # -> AWAITING_APPROVAL
                else:
                    job["status"] = "revision_needed"          # halt, needs a human/rewrite
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

    _maybe_stamp_measure(job)      # open a measurement window on arrival at published/sent
    store.save(job)
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
    """One poll cycle: claim a runnable job and advance it to its next block."""
    job = store.claim_next()
    if job is None:
        return None
    return run_until_blocked(job, store)


def new_job(job_id: str, job_type: str, brand: dict, payload: dict) -> dict:
    return {
        "job_id": job_id, "type": job_type, "status": "created",
        "client_id": brand.get("brand_name", ""), "brand": brand,
        "payload": payload, "approved": False,
        "cost_so_far_usd": 0.0, "model_log": [],
    }


def approve(job_id: str, store: JobStore) -> None:
    """The single human approval action (SECTION 1 rule 2)."""
    job = store.get(job_id)
    job["approved"] = True
    store.save(job)


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
    set_clock(lambda: base + timedelta(days=float(MEASURE_AFTER_DAYS) + 1))
    assert is_runnable(job4), "window elapsed -> job should be runnable"
    status = run_until_blocked(job4, store4)
    assert status == "optimized", f"expected optimized after window, got {status}"
    set_clock(lambda: datetime.now(timezone.utc))  # restore clock

    _LLM_HOOK = run_llm_skill  # restore
    print("OK — orchestrator verified: human gate, completion, QA-block routing, "
          "budget halt, and time-based measurement gate. (LLM stubbed; no API.)")
