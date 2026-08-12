"""
content_engine_providers.py
============================================================================
The provider layer for the Content Engine (see
content-engine-prompt-engineering.md, SECTION 4/5).

Gives the dispatch wrapper three things:
  1. build_prompt(skill_name, job) -> PromptSpec
       Stitches SECTION 6 (rules) + SECTION 7 (brand) + SECTION 8 (skill) as a
       CACHED system prefix, appends the tiny per-job payload as the uncached
       user turn, and computes max_tokens from the skill's TOKEN BUDGET.
  2. call_provider(model, spec) -> SkillResult
       Routes on the model id: "claude*" -> Anthropic, "gpt*" -> OpenAI.
       Honors USE_FIXTURES=1 (zero API cost in dev).
  3. SkillResult(data, usage, model, cost_usd)
       .data  = parsed JSON dict (validate this with content_engine_schemas)
       .usage = token counts   .cost_usd = computed spend for the budget cap

WHY NO THINKING: these are tight structured-JSON tasks with small max_tokens.
Extended/adaptive thinking would eat the output budget and truncate. We omit
it deliberately (Opus 4.8 runs without thinking when the field is absent).

Wrapper wiring (drop-in replacement for the SECTION 4 pseudocode):

    from content_engine_providers import build_prompt, call_provider
    from content_engine_schemas import SCHEMAS

    def run_skill(job, skill_name):
        route = ROUTES[skill_name]
        if route["engine"] == "code":
            return CODE_HANDLERS[skill_name](job)
        spec = build_prompt(skill_name, job)
        for model in [route["engine"], route.get("fallback")]:
            if not model:
                break
            if over_budget(job):
                raise BudgetExceeded(job["job_id"])
            result = call_provider(model, spec)          # SkillResult
            ok, errs = SCHEMAS[skill_name].validate(result.data)
            if ok and "error" not in result.data:
                log_cost(job, model, result)             # uses result.cost_usd
                return result.data
            # else: bad shape or model gave up -> try the fallback model
        raise SkillFailed(skill_name)

Dependencies: `anthropic` (required for Claude), `openai` (only if you use the
GPT fallback). Both optional at import time; a missing SDK only errors if you
actually call that provider.
============================================================================
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from content_engine_prompts import (
    SHARED_OUTPUT_RULES,
    BRAND_CONTEXT_TEMPLATE,
    BRAND_DEFAULTS,
    SKILL_PROMPTS,
)
from content_engine_schemas import SCHEMAS


# ---------------------------------------------------------------------------
# Pricing (USD per 1,000,000 tokens). Claude verified; GPT left None until you
# confirm from OpenAI docs. cost_usd falls back to 0.0 for a None price and
# stamps a warning so a fallback call is never silently "free".
# ---------------------------------------------------------------------------
# Claude-only. openai_call() below is kept for optionality but is not used by
# the default routing. If you re-enable a GPT fallback, add its price rows here.
PRICING = {
    "claude-opus-4-8":  {"in": 5.00, "out": 25.00},
    "claude-sonnet-5":  {"in": 2.00, "out": 10.00},   # intro pricing thru 2026-08-31
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00},
}
_CACHE_WRITE_MULT = 1.25   # 5-minute ephemeral cache write premium
_CACHE_READ_MULT = 0.10    # cache read discount


log = logging.getLogger("content_engine.providers")


# ---------------------------------------------------------------------------
# max_tokens per skill (from each SECTION 8 TOKEN BUDGET). Two skills are
# dynamic and handled in _max_tokens_for().
# ---------------------------------------------------------------------------
_MAX_TOKENS = {
    "site_intelligence": 1700,   # 5 issues x 4 prose fields + wins
    "authority_backlinks": 1700,  # shares the same narrate shape
    "competitor_intel": 3900,
    "content_strategist": 4000,
    "content_producer_image": 500,
    "seo_optimizer": 1650,
    "qa_compliance": 2400,
    "analytics_funnel": 650,
    "optimizer": 2450,
    "segmenter": 1100,
    "outreach_copy": 1150,   # per lead; room for a full email (incl. German)
    "media_buyer": 18550,    # a full campaign (ad groups + kw + headlines) must not truncate
    "media_chat": 18600,     # discuss + return the FULL revised campaign (same size)
    "reply_responder": 500,  # one inbound reply per call
    "judge": 500,            # S1 evaluator — compact verdict only
    "content_planner": 7350,  # a batch of proposed pieces (segment+pillar+channel+day) to approve
    "seo_fixer": 600,        # one page's title/meta/alt rewrite — compact by design
    "link_pitch": 500,       # one link-building email
    "seo_analyst": 2550,      # the qualitative reads across the SEO boards
}


def schema_token_estimate(schema: dict) -> int:
    """Worst-case output tokens this schema can produce.

    Sizing a budget by eye is how site_intelligence shipped with 500 tokens for
    an 805-token schema, and content_strategist with 900 for 1233 — each one
    discovered by a real job dying mid-pipeline, at real cost. This computes it
    from the schema instead: every array multiplied by its maxItems, every
    string charged at a prose-length allowance.

    Deliberately pessimistic. max_tokens is a CEILING, not a reservation — you
    are billed for tokens generated, not tokens permitted — so headroom is
    close to free and truncation is not."""
    # CALIBRATED AGAINST PRODUCTION, not guessed. content_strategist was sized
    # at 1233 tokens by the first version of this function, given a 1450 budget,
    # and still truncated in the field: it reached 3767 characters and was not
    # finished. Two constants were wrong and both are now measured:
    #   chars-per-token  3.2 -> 2.6   (3767 chars / 1450 tokens, observed)
    #   prose strings    90  -> 200   (a rationale or summary is a sentence or
    #                                  three, not a label)
    # Short fields keep a small allowance so a slug or a date is not charged as
    # an essay.
    PROSE = ("rationale", "why", "summary", "note", "insight", "description",
             "body", "headline", "fix", "suggestion", "answer", "reason",
             "recommendation", "finding", "read", "move", "cause", "focus",
             "opportunity", "angle", "weakness", "gap", "next", "advice")
    SHORT_CHARS = 90
    PROSE_CHARS = 200
    UNBOUNDED_ITEMS = 10     # only reachable if a cap was missed

    def walk(node, key="") -> int:
        if not isinstance(node, dict):
            return 0
        if "enum" in node:
            return max((len(str(x)) for x in node["enum"]), default=8) + 3
        t = node.get("type")
        if t == "string":
            k = key.lower()
            return PROSE_CHARS if any(w in k for w in PROSE) else SHORT_CHARS
        if t in ("number", "integer"):
            return 8
        if t == "boolean":
            return 5
        if t == "array":
            n = node.get("maxItems", UNBOUNDED_ITEMS)
            return 2 + n * (walk(node.get("items", {}), key) + 2)
        if t == "object" or "properties" in node:
            total = 2
            for k2, val in (node.get("properties") or {}).items():
                total += len(k2) + 4 + walk(val, k2)
            return total
        return 20

    return round(walk(schema) / 2.6)   # measured, not assumed


def _max_tokens_for(skill_name: str, payload: dict) -> int:
    # SIZE THE CEILING FROM THE BRIEF, not from a hand-written type check.
    #
    # This read `2600 if payload.get("type") == "blog" else 400` - a list of
    # one word. The day guide and service became long-form (4 sections, 650+
    # words, 4 image prompts) they kept getting FOUR HUNDRED tokens, which
    # cannot hold a title, so the piece died before writing a sentence. The
    # retry doubled 400 -> 800 -> 1600 and gave up, which is the
    # "1600-token ceiling after 0 characters" in production.
    #
    # The brief already states the length ("blog:1500-2000w"). Read the upper
    # bound from it and size to that, so a type added later is covered by
    # having a length rather than by being added here too.
    if skill_name in ("content_producer", "content_producer_copy"):
        import re as _re
        length = str(payload.get("length") or "")
        words = [int(x) for x in _re.findall(r"(\d{3,5})\s*w", length)] or \
                [int(x) for x in _re.findall(r"(\d{3,5})", length)]
        if words:
            # ~2.2 tokens per word of prose, plus room for the JSON envelope,
            # the meta fields and one image prompt per section.
            return min(16000, int(max(words) * 2.2) + 900)
        if payload.get("structure"):        # long-form but no parsable length
            return 6000
        return 2600 if payload.get("type") == "blog" else 900
    # Lead Qualifier: ~130 tokens per lead (now also business/pain/offer), 25-batch.
    if skill_name == "lead_qualifier":
        n = len(payload.get("leads", []) or [])
        return max(400, 140 * min(n, 25) + 150)  # room for the qualitative fields
    return _MAX_TOKENS.get(skill_name, 800)


# ---------------------------------------------------------------------------
# Schema key resolution (ROUTES key -> schema key). "content_producer" routes
# to the copy schema; the image sub-call uses "content_producer_image".
# ---------------------------------------------------------------------------
def _schema_for(skill_name: str):
    if skill_name in SCHEMAS:
        return SCHEMAS[skill_name].schema
    return None


# ---------------------------------------------------------------------------
# PromptSpec: the built request, provider-agnostic.
# ---------------------------------------------------------------------------
@dataclass
class PromptSpec:
    skill_name: str
    system_blocks: list          # list of {"type":"text","text":...,"cache_control"?}
    user_content: str            # JSON string of the per-job payload (uncached)
    max_tokens: int
    schema: Optional[dict]        # JSON schema for structured outputs (may be None)


@dataclass
class SkillResult:
    data: dict
    usage: dict
    model: str
    cost_usd: float
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------
def _render_brand(job: dict) -> str:
    brand = {**BRAND_DEFAULTS, **(job.get("brand") or {})}
    text = BRAND_CONTEXT_TEMPLATE.format(**brand)
    try:  # append the founder's CI / brand-identity guidance if configured
        import content_engine_brand as _brand
        ci = _brand.get_ci_block()
        if ci:
            text += "\n\n" + ci
    except Exception:
        pass
    # WHAT THIS BUSINESS ACTUALLY IS. The CMS layer decides ECOMMERCE or
    # SERVICE from evidence, and until now that verdict was computed,
    # displayed, and read by nobody: every writer still produced the same
    # generic post for a shop and a consultancy alike. This is the wire.
    # It is APPENDED to the brand block, so it reaches every content
    # skill at once and costs nothing extra - the block is cached.
    text += "\n\n" + _business_block(job)
    return text


def _business_block(job: dict) -> str:
    """The business type and its content policy, as prompt text.

    UNKNOWN is passed through as UNKNOWN. A writer told nothing is
    better than a writer told a guess: it will ask the brief instead of
    confidently writing product pages for a consultancy."""
    v = {}
    try:
        v = dict((job.get("business_type") or {}))
    except Exception:                                 # noqa: BLE001
        v = {}
    if not v:
        try:
            import content_engine_api as _A
            _st = _A.get_store()
            v = dict(_st.get_setting("business_type", {}) or {})
        except Exception:                             # noqa: BLE001
            v = {}
    btype = str((v or {}).get("type") or "UNKNOWN").upper()
    try:
        import content_engine_commerce as _CM
        pol = _CM.content_policy(verdict=v or {"type": btype})
    except Exception:                                 # noqa: BLE001
        pol = {"types": (), "avoid": (), "why": "", "cta": ""}
    if btype == "UNKNOWN" or not pol.get("types"):
        return ("THIS BUSINESS\n- Type: NOT ESTABLISHED. Nothing has been "
                "read from a CMS and search intent has not separated a "
                "shop from a service.\n- Therefore: follow the brief you "
                "were given and do NOT assume products exist. Do not "
                "invent a catalogue, a price or a checkout.")
    lines = [
        "THIS BUSINESS",
        "- Type: " + btype + " (confidence "
        + str(v.get("confidence") or "UNKNOWN") + ")",
        "- Decided because: " + str(v.get("why") or "")[:200],
        "- Content that fits: " + ", ".join(pol.get("types") or ()),
        "- The call to action is: " + str(pol.get("cta") or ""),
    ]
    if pol.get("avoid"):
        lines.append("- Do not write: " + ", ".join(pol.get("avoid")))
    lines.append("- Why this matters: " + str(pol.get("why") or ""))
    return "\n".join(lines)


# Anthropic silently IGNORES cache_control when the prefix is shorter than the
# model's minimum cacheable length. No error, no warning, no cache — the call
# just costs full price. This engine marked every prompt as cacheable and 20 of
# 23 skills were below the line, so SECTION 5's "cost lever #1" did nothing at
# all for most of the pipeline.
CACHE_MIN_TOKENS = {"haiku": 2048}      # everything else: 1024
CACHE_MIN_DEFAULT = 1024
_CHARS_PER_TOKEN = 3.6                  # prose prefix, not dense JSON


def cache_minimum(model: str) -> int:
    m = str(model or "").lower()
    for family, n in CACHE_MIN_TOKENS.items():
        if family in m:
            return n
    return CACHE_MIN_DEFAULT


def prefix_tokens(system_blocks: list) -> int:
    return round(sum(len(b.get("text", "")) for b in system_blocks) / _CHARS_PER_TOKEN)


def will_cache(system_blocks: list, model: str) -> bool:
    """Would this prefix ACTUALLY be cached by the provider?"""
    return prefix_tokens(system_blocks) >= cache_minimum(model)


def apply_cache_control(system_blocks: list, model: str) -> list:
    """Mark the prefix cacheable ONLY when the provider would honour it.

    Marking it regardless is not free-and-harmless: it reads as 'caching is on'
    in the code, in the self-check and in every cost conversation, while the
    bill says otherwise."""
    blocks = [dict(b) for b in system_blocks]
    for b in blocks:
        b.pop("cache_control", None)
    if blocks and will_cache(blocks, model):
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
    else:
        log.debug("prompt caching skipped: prefix ~%d tok < %d minimum for %s",
                  prefix_tokens(blocks), cache_minimum(model), model)
    return blocks


def _is_credit_exhaustion(msg: str) -> bool:
    """The API reports an empty wallet as a 400 invalid_request_error;
    the phrase is the contract this classifier keys on."""
    return "credit balance is too low" in str(msg).lower()


def build_prompt(skill_name: str, job: dict) -> PromptSpec:
    """Assemble the cached prefix + uncached payload for one skill call."""
    skill_prompt = SKILL_PROMPTS.get(skill_name)
    if not skill_prompt:
        raise KeyError(f"No prompt registered for skill '{skill_name}'")

    payload = job.get("payload", {}) or {}

    # Cached prefix = three stable text blocks. cache_control on the LAST one
    # caches all three together (render order: system before messages).
    system_blocks = [
        {"type": "text", "text": SHARED_OUTPUT_RULES},         # SECTION 6
        {"type": "text", "text": _render_brand(job)},          # SECTION 7 (per client)
        {"type": "text", "text": skill_prompt,                 # SECTION 8 (per skill)
         "cache_control": {"type": "ephemeral"}},
    ]

    # The API refuses a system block whose text is empty (400), and one
    # empty block kills the whole call. A block with nothing to say is
    # dropped; the skill block always survives (guarded non-empty above),
    # so the cache_control marker on it survives too.
    system_blocks = [b for b in system_blocks
                     if str(b.get("text") or "").strip()]

    # Uncached user turn = only the tiny per-job INPUT.
    user_content = "INPUT:\n" + json.dumps(payload, ensure_ascii=False)

    return PromptSpec(
        skill_name=skill_name,
        system_blocks=system_blocks,
        user_content=user_content,
        max_tokens=_max_tokens_for(skill_name, payload),
        schema=_schema_for(skill_name),
    )


# ---------------------------------------------------------------------------
# Structured-output schema hygiene: strip keywords the API's json_schema mode
# does not support, so a maxItems/minItems in our validation schema never 400s
# the structured-output request. We still validate the FULL schema afterward
# with content_engine_schemas (that is where maxItems etc. are enforced).
# ---------------------------------------------------------------------------
_UNSUPPORTED_SO_KEYS = {
    "minItems", "maxItems", "minLength", "maxLength",
    "minimum", "maximum", "multipleOf", "pattern",
}


def _strip_for_structured_outputs(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_for_structured_outputs(v)
                for k, v in schema.items() if k not in _UNSUPPORTED_SO_KEYS}
    if isinstance(schema, list):
        return [_strip_for_structured_outputs(v) for v in schema]
    return schema


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------
def _compute_cost(model: str, usage: dict) -> tuple[float, list]:
    price = PRICING.get(model)
    warns = []
    if not price or price.get("in") is None or price.get("out") is None:
        warns.append(f"no pricing for model '{model}' — cost logged as 0.0")
        return 0.0, warns
    pin = price["in"] / 1_000_000
    pout = price["out"] / 1_000_000
    cost = (
        usage.get("input_tokens", 0) * pin
        + usage.get("output_tokens", 0) * pout
        + usage.get("cache_creation_input_tokens", 0) * pin * _CACHE_WRITE_MULT
        + usage.get("cache_read_input_tokens", 0) * pin * _CACHE_READ_MULT
    )
    return round(cost, 6), warns


# ---------------------------------------------------------------------------
# Fixtures (USE_FIXTURES=1 -> read; RECORD_FIXTURES=1 -> write live responses)
# ---------------------------------------------------------------------------
_FIXTURE_DIR = Path(os.getenv("FIXTURE_DIR", "./fixtures"))


def _fixture_key(model: str, spec: PromptSpec) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(spec.skill_name.encode())
    h.update(spec.user_content.encode())
    return f"{spec.skill_name}__{model}__{h.hexdigest()[:12]}.json"


def load_fixture(model: str, spec: PromptSpec) -> SkillResult:
    path = _FIXTURE_DIR / _fixture_key(model, spec)
    if not path.exists():
        raise FileNotFoundError(
            f"USE_FIXTURES=1 but no fixture at {path}. "
            f"Run once with RECORD_FIXTURES=1 to capture it.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return SkillResult(data=data, usage={}, model=model, cost_usd=0.0,
                       warnings=["served from fixture (no API cost)"])


def _maybe_record(model: str, spec: PromptSpec, result: SkillResult) -> None:
    if os.getenv("RECORD_FIXTURES") != "1":
        return
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (_FIXTURE_DIR / _fixture_key(model, spec)).write_text(
        json.dumps(result.data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------
_anthropic_client = None


# No timeout was ever set, so every call inherited the SDK default of ten
# minutes. One stalled connection blocked the worker for that long with no
# output at all - indistinguishable from a crash, and the reason a probe run
# looks frozen. The orchestrator already retries once and falls back to a second
# model, so failing fast is strictly better than waiting.
LLM_TIMEOUT_S = float((os.getenv("LLM_TIMEOUT_S") or "").strip() or "240")


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic  # imported lazily so a missing SDK only errors on use
        _anthropic_client = anthropic.Anthropic(timeout=LLM_TIMEOUT_S,
                                                max_retries=1)
    return _anthropic_client


def web_research(topic: str, context: str = "", max_uses: int = 5) -> str:
    """Best-effort LIVE web research for a content piece. Uses the web_search
    server tool (free-form, no structured output) and returns a plain-text brief
    of real, current facts + sources the writer must ground the article in.
    Returns '' on ANY error, so the content pipeline never breaks if web search
    is unavailable on the account — it just falls back to un-researched writing."""
    topic = (topic or "").strip()
    if not topic:
        return ""
    model = os.getenv("FRONTIER_MODEL", "claude-opus-4-8")
    prompt = (
        "You are researching for a B2B blog article. Search the web and return a "
        "tight, factual brief the writer will ground the piece in.\n\n"
        f"TOPIC: {topic}\n" + (f"AUDIENCE / ANGLE: {context}\n" if context else "") +
        "\nReturn, using ONLY things you verified via search:\n"
        "- 5-7 specific, current facts or stats (include the year and the number)\n"
        "- 2-3 concrete real-world examples, named tools, or approaches\n"
        "- 2 credible sources as 'Name — URL'\n"
        "Be concrete and specific. No filler, no generic advice.")
    # Primary: Anthropic's server-side web_search tool. Fallback below: Serper.
    for tool_type in ("web_search_20260209", "web_search_20250305"):
        try:
            client = _get_anthropic()
            resp = client.messages.create(
                model=model, max_tokens=1300,
                tools=[{"type": tool_type, "name": "web_search", "max_uses": max_uses}],
                messages=[{"role": "user", "content": prompt}],
            )
            brief = "\n".join(b.text for b in resp.content
                              if getattr(b, "type", "") == "text" and getattr(b, "text", "")).strip()
            try:
                u = resp.usage
                usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                         "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                         "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0}
                cost, _ = _compute_cost(model, usage)
                if _WEB_RESEARCH_COST_SINK:
                    _WEB_RESEARCH_COST_SINK(cost, usage)
            except Exception:
                pass
            if brief:
                return brief
        except Exception:
            continue   # try the older tool type, then fall back to Serper
    # Fallback: Serper (Google search API) — deterministic brief from real results,
    # zero LLM cost. Activates when SERPER_API_KEY is connected.
    try:
        from content_engine_connectors import Serper
        rows = Serper().search(topic, num=8)
        if rows:
            lines = [f"- {r['title']}: {r['snippet']} (source: {r['link']})"
                     for r in rows if r.get("snippet")]
            if lines:
                return ("Live Google results for '" + topic + "' (via Serper):\n"
                        + "\n".join(lines[:8]))
    except Exception:
        pass
    return ""


def generate_briefing_text(metrics: str) -> str:
    """The AI brain's 'Good morning' narrative — a concise executive briefing written
    from REAL metrics only. Returns '' on any error (dashboard falls back to the
    rule-based briefing)."""
    metrics = (metrics or "").strip()
    if not metrics:
        return ""
    try:
        client = _get_anthropic()
        model = os.getenv("FRONTIER_MODEL", "claude-opus-4-8")
        prompt = (
            "You are the AI brain of a business operating system for an AI-automation consultancy. "
            "Write a concise executive 'Good morning' briefing (110-170 words) for the founder, using ONLY "
            "the real metrics below. Cover, in flowing prose (not bullet spam): overall health; what changed; "
            "the single biggest RISK; the single biggest OPPORTUNITY; and end with 3 concrete immediate actions. "
            "Be specific and honest. NEVER invent numbers, revenue, or clients not present in the metrics. "
            "If a figure is an estimate, say 'est.'.\n\nMETRICS:\n" + metrics)
        resp = client.messages.create(model=model, max_tokens=520,
                                      messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content
                       if getattr(b, "type", "") == "text" and getattr(b, "text", "")).strip()
        try:
            u = resp.usage
            usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                     "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                     "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0}
            cost, _ = _compute_cost(model, usage)
            if _WEB_RESEARCH_COST_SINK:
                _WEB_RESEARCH_COST_SINK(cost, usage)
        except Exception:
            pass
        return text
    except Exception:
        return ""


_WEB_RESEARCH_COST_SINK = None


def set_web_research_cost_sink(fn):
    """Register a callback(cost_usd, usage) so live-research spend hits the meters."""
    global _WEB_RESEARCH_COST_SINK
    _WEB_RESEARCH_COST_SINK = fn


class OutputTruncated(RuntimeError):
    """The model hit its token ceiling before it finished the JSON.

    Raised INSTEAD of letting json.loads fail, because the JSONDecodeError says
    'Unterminated string at char 2293' and this says which skill ran out of
    room, what its budget was, and what to change."""


def _truncated(stop_reason: str, spec: "PromptSpec", chars: int,
               blocks=None) -> None:
    if str(stop_reason) in ("max_tokens", "length"):
        if chars == 0:
            # Six pieces died saying "ran out of room after 0 characters" -
            # the whole budget was spent and NO text came back. Growing the
            # ceiling cannot fix what it cannot see; name where the tokens
            # actually went (thinking blocks, a refusal, an empty response)
            # so the fix targets the mechanism instead of the symptom.
            raise OutputTruncated(
                f"{spec.skill_name} spent its whole {spec.max_tokens}-token "
                f"budget and returned NO text at all. Blocks received: "
                f"{list(blocks) if blocks else '(none)'} - if these are "
                f"thinking blocks, the model is reasoning away the budget; "
                f"if empty, the response never started.")
        raise OutputTruncated(
            f"{spec.skill_name} ran out of room: it hit its {spec.max_tokens}-token "
            f"ceiling after {chars} characters, so the JSON was cut off mid-value. "
            f"Raise _MAX_TOKENS['{spec.skill_name}'] in content_engine_providers.py, "
            f"or cap the unbounded arrays in its schema.")


def _parse_model_json(text: str, spec: "PromptSpec", stop_reason: str,
                      blocks=None) -> dict:
    """THE ONLY WAY MODEL OUTPUT BECOMES DATA.

    The stop_reason guard above catches truncation only when the provider
    CONFESSES ("max_tokens"/"length"). Fifteen real jobs died because the
    confession never came: the response was cut, stop_reason said something
    else (or nothing), json.loads raised a raw JSONDecodeError two lines
    later, and the retry machinery - which knows exactly how to recover from
    truncation - never heard about it. The piece was filed as dead.

    Under a structured-output request the schema guarantees the SHAPE, so an
    unparseable response has exactly one realistic cause: the model was cut
    off before it finished. Classify it as what it is, whatever the provider
    claimed, so the recovery path always fires.

    Every *_call function must parse through here and nowhere else - a naked
    json.loads on model output fails the build (verify_loop's AST gate)."""
    _truncated(stop_reason, spec, len(text), blocks=blocks)
    try:
        return json.loads(text)
    except ValueError as e:   # JSONDecodeError subclasses ValueError
        raise OutputTruncated(
            f"{spec.skill_name} returned unparseable JSON under its "
            f"{spec.max_tokens}-token ceiling ({len(text)} characters, "
            f"stop_reason={str(stop_reason) or 'none'!r}; parser said: "
            f"{str(e)[:90]}). With a structured-output schema enforcing the "
            f"shape, this is a cut-off response - treating it as truncation "
            f"so the retry can grow the ceiling and go again.") from e


def anthropic_call(model: str, spec: PromptSpec) -> SkillResult:
    client = _get_anthropic()
    kwargs = dict(
        model=model,
        max_tokens=spec.max_tokens,
        # the marker is corrected HERE because only now do we know the model,
        # and the minimum cacheable length is per-model (haiku needs 2048)
        system=apply_cache_control(spec.system_blocks, model),
        messages=[{"role": "user", "content": spec.user_content}],
    )
    if spec.schema:
        kwargs["output_config"] = {
            "format": {"type": "json_schema",
                       "schema": _strip_for_structured_outputs(spec.schema)}
        }
    try:
        resp = client.messages.create(**kwargs)
    except Exception as e:
        # A 400 SAYS "Invalid request data" AND NOTHING ELSE. One revived
        # piece died on exactly that - a refusal with no named field is
        # undiagnosable from the error alone. Record the request's SHAPE
        # (never its content, never a key) so the next retry tells us what
        # the API disliked instead of repeating the mystery.
        if type(e).__name__ == "BadRequestError":
            # AN EMPTY WALLET IS NOT SIXTY BROKEN JOBS. The API reports an
            # exhausted credit balance as a 400, and one night of it turned
            # every queued piece into a separate needs-human corpse. It is
            # the daily-cap class: halted_budget, one revive when money
            # returns, nothing re-bought.
            if _is_credit_exhaustion(str(e)):
                from content_engine_orchestrator import BudgetExceeded
                raise BudgetExceeded(
                    f"{spec.skill_name}: the Anthropic account is out of "
                    "credits (the API refused with 'credit balance is too "
                    "low'). Top up at console.anthropic.com Plans & "
                    "Billing; revive resumes every halted piece from its "
                    "last completed step.") from e
            _blocks = kwargs.get("system") or []
            def _btext(b):
                return str((b.get("text") if isinstance(b, dict)
                            else getattr(b, "text", "")) or "")
            _msgs = kwargs.get("messages") or []
            _ulen = sum(len(str(m.get("content", ""))) for m in _msgs
                        if isinstance(m, dict))
            raise RuntimeError(
                f"the API refused the request (400) for {spec.skill_name}. "
                f"Request shape: model={model}, max_tokens="
                f"{kwargs.get('max_tokens')}, system_blocks={len(_blocks)}"
                f" (empty: {sum(1 for b in _blocks if not _btext(b).strip())}),"
                f" user_chars={_ulen}, structured_output="
                f"{'yes' if spec.schema else 'no'}. Original: "
                f"{str(e)[:180]}") from e
        raise

    text = next((b.text for b in resp.content if b.type == "text"), "")
    # A structured-output schema guarantees the SHAPE, not that the model was
    # given room to finish. When max_tokens cuts the response mid-string the
    # JSON is invalid no matter what the schema said, and json.loads raises an
    # opaque "Unterminated string at char 2293" that names neither the skill nor
    # the cause. Fifteen content jobs died on exactly that, all at step one,
    # for days. Say what actually happened instead.
    data = _parse_model_json(text, spec, getattr(resp, "stop_reason", ""),
                             blocks=[getattr(b, "type", "?")
                                     for b in resp.content])

    u = resp.usage
    usage = {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }
    cost, warns = _compute_cost(model, usage)
    result = SkillResult(data=data, usage=usage, model=model, cost_usd=cost,
                         warnings=warns)
    _maybe_record(model, spec, result)
    return result


# ---------------------------------------------------------------------------
# OpenAI adapter (cross-provider fallback). Uses Chat Completions + json_schema
# structured outputs — the stable shape across GPT-5.x. VERIFY against
# developers.openai.com/api/docs before relying on the fallback in production;
# newer models may prefer the Responses API and max_completion_tokens.
# OpenAI caches long identical prefixes automatically (no cache_control needed).
# ---------------------------------------------------------------------------
_openai_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        import openai
        _openai_client = openai.OpenAI()  # reads OPENAI_API_KEY
    return _openai_client


def openai_call(model: str, spec: PromptSpec) -> SkillResult:
    client = _get_openai()
    # Flatten the three cached system blocks into one system message.
    system_text = "\n\n".join(b["text"] for b in spec.system_blocks)
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": spec.user_content},
    ]
    kwargs: dict = {"model": model, "messages": messages}
    # GPT-5.x uses max_completion_tokens; older models use max_tokens.
    kwargs["max_completion_tokens"] = spec.max_tokens
    if spec.schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": spec.skill_name,
                "strict": True,
                "schema": _strip_for_structured_outputs(spec.schema),
            },
        }
    resp = client.chat.completions.create(**kwargs)

    _ch = resp.choices[0]
    _content = _ch.message.content or ""
    data = _parse_model_json(_content, spec, getattr(_ch, "finish_reason", ""))
    u = resp.usage
    usage = {
        "input_tokens": getattr(u, "prompt_tokens", 0),
        "output_tokens": getattr(u, "completion_tokens", 0),
        "cache_creation_input_tokens": 0,
        # OpenAI reports cached prompt tokens under prompt_tokens_details.cached_tokens
        "cache_read_input_tokens": getattr(
            getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0,
    }
    cost, warns = _compute_cost(model, usage)
    result = SkillResult(data=data, usage=usage, model=model, cost_usd=cost,
                         warnings=warns)
    _maybe_record(model, spec, result)
    return result


# ---------------------------------------------------------------------------
# call_provider — the router the wrapper calls.
# ---------------------------------------------------------------------------
def call_provider(model: str, spec: PromptSpec) -> SkillResult:
    if os.getenv("USE_FIXTURES") == "1":
        return load_fixture(model, spec)
    if model.startswith("claude"):
        return anthropic_call(model, spec)
    if model.startswith("gpt"):
        return openai_call(model, spec)
    raise ValueError(f"Unknown provider for model '{model}'")


# ---------------------------------------------------------------------------
# Offline self-check: build every prompt and confirm the prefix/payload split
# and max_tokens are correct. Runs no API calls.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_job = {
        "job_id": "job_test",
        "brand": {"brand_name": "Anthropos", "industry": "Automation"},
        "payload": {"type": "blog", "leads": [{"id": "1"}, {"id": "2"}]},
    }
    checks = {
        "site_intelligence": 1700,
        "content_producer": 2600,          # payload.type == blog
        "content_producer_image": 500,
        # Mirrors _max_tokens_for(): 140 tokens/lead + 150, floor 400. (This
        # assertion was left on the OLD 60/lead formula when the qualifier
        # gained its business/pain/offer fields — stale test, not a bug.)
        "lead_qualifier": max(400, 140 * 2 + 150),
        # Raised from 1500 on 2026-08-02: qa_compliance truncated in
        # production that morning. A ceiling is not a reservation — unused
        # tokens cost nothing — so the old number bought nothing and killed
        # three pieces.
        "qa_compliance": 2400,
        "outreach_copy": 1150,
    }
    for skill, expected in checks.items():
        spec = build_prompt(skill, sample_job)
        assert spec.max_tokens == expected, \
            f"{skill}: max_tokens {spec.max_tokens} != {expected}"
        assert len(spec.system_blocks) == 3, f"{skill}: expected 3 system blocks"
        assert "cache_control" in spec.system_blocks[-1], \
            f"{skill}: cache breakpoint missing on last system block"
        assert spec.user_content.startswith("INPUT:"), f"{skill}: payload not framed"
    # Cost math sanity (Opus 4.8, all cached read).
    c, _ = _compute_cost("claude-opus-4-8",
                         {"input_tokens": 200, "output_tokens": 500,
                          "cache_read_input_tokens": 4000})
    assert c > 0, "cost should be > 0"

    # ---- truncation must be NAMED, not left to json.loads ------------------
    class _Spec:
        skill_name, max_tokens = "site_intelligence", 1400
    for reason in ("max_tokens", "length"):
        try:
            _truncated(reason, _Spec(), 2293)
            raise AssertionError(f"{reason} must raise OutputTruncated")
        except OutputTruncated as e:
            assert "ran out of room" in str(e) and "site_intelligence" in str(e)
            assert "1400" in str(e), "the error must name the budget to change"
    _truncated("end_turn", _Spec(), 900)      # a normal finish must NOT raise

    # ---- the confession-less cut: stop_reason lies, JSON is torn -----------
    # Fifteen real jobs died as "degraded (JSONDecodeError)" because the
    # provider did NOT say max_tokens and the raw parse error flew past the
    # retry machinery. Any unparseable output must classify as truncation.
    for bad, why in (('{"title": "cut mid-str', "unterminated string"),
                     ('{"title": ', "value missing"),
                     ("", "empty response")):
        try:
            _parse_model_json(bad, _Spec(), "end_turn")
            raise AssertionError(f"{why}: must raise OutputTruncated")
        except OutputTruncated as e:
            assert "unparseable" in str(e) and "site_intelligence" in str(e), why
    assert _parse_model_json('{"ok": 1}', _Spec(), "end_turn") == {"ok": 1}

    # ---- EVERY budget must cover what its schema can emit --------------
    # This was discovered one dead job at a time, at real cost: site_intelligence
    # died at 500 tokens against an 805-token schema, and once that was fixed
    # content_strategist died at 900 against 1233. Both were sized by eye. The
    # schema already states exactly how much output it permits, so the budget is
    # now checked against it instead of guessed.
    #
    # max_tokens is a CEILING, not a reservation — billing is per token
    # GENERATED — so headroom costs nothing and truncation costs a whole job.
    import content_engine_schemas as _SC
    undersized, unbounded = [], []
    for _name, _obj in _SC.SCHEMAS.items():
        _sch = getattr(_obj, "schema", _obj)
        if not isinstance(_sch, dict):
            continue
        _budget = _MAX_TOKENS.get(_name)
        if _budget is None:
            continue                       # computed per job in _max_tokens_for
        _need = schema_token_estimate(_sch)
        if _need > _budget:
            undersized.append((_name, _budget, _need))
        _stack = [_sch.get("properties", {})]
        while _stack:
            _node = _stack.pop()
            if isinstance(_node, dict):
                if _node.get("type") == "array" and "maxItems" not in _node:
                    unbounded.append(_name)
                    break
                _stack.extend(_node.values())
            elif isinstance(_node, list):
                _stack.extend(_node)
    # A regression guard with the real numbers in it. content_strategist was
    # given 1450 by an estimate of 1233 and still truncated in production at
    # 3767 characters; if a future edit lowers these constants back, this fails
    # here rather than in a job three days later.
    _cs = _SC.SCHEMAS.get("content_strategist")
    if _cs is not None:
        _need = schema_token_estimate(getattr(_cs, "schema", _cs))
        assert _need >= 1800, (
            f"the estimator has drifted back to optimistic: content_strategist "
            f"needs {_need}, but production proved 1450 was not enough")
    assert not undersized, (
        "these token budgets are smaller than the output their own schema "
        "permits, so a full response truncates into invalid JSON "
        f"(skill, budget, needs): {sorted(undersized)}")
    assert not unbounded, (
        "these schemas contain an array with no maxItems, so their output "
        f"length is unbounded and no budget can be proven sufficient: "
        f"{sorted(set(unbounded))}")

    # ---- prompt caching: is it REAL? --------------------------------------
    # The self-check used to assert only that a cache breakpoint EXISTED. It
    # existed on all 23 skills and worked on 3, because a marker below the
    # provider's minimum is silently ignored. Assert the honest thing instead:
    # a marker is present ONLY where it will actually be honoured.
    import content_engine_orchestrator as _ORCH
    _real, _skipped = [], []
    for _sk in sorted(SKILL_PROMPTS):
        try:
            _sp = build_prompt(_sk, {"brand": {}, "payload": {}})
        except Exception:
            continue
        _model = str(_ORCH.ROUTES.get(_sk, {}).get("engine", "") or "")
        if _model == "code":
            _model = str(_ORCH.ROUTES.get(_sk, {}).get("narrate", "") or "")
        _blocks = apply_cache_control(_sp.system_blocks, _model)
        _marked = any("cache_control" in b for b in _blocks)
        (_real if _marked else _skipped).append(
            (_sk, prefix_tokens(_sp.system_blocks), cache_minimum(_model)))
        # the invariant: never claim a cache we will not get
        assert _marked == will_cache(_sp.system_blocks, _model), _sk

    assert not any(t >= m for _s, t, m in _skipped),         "a skill was skipped despite clearing the minimum"
    assert all(t >= m for _s, t, m in _real),         "a skill was marked cacheable below the minimum - that marker is a no-op"
    print(f"   prompt caching: {len(_real)} of {len(_real)+len(_skipped)} skills "
          f"actually cache; {len(_skipped)} are below the provider minimum and "
          f"are no longer marked as if they did")

    print(f"OK — build_prompt + routing + cost verified for {len(checks)} skills "
          f"(sample cost check ${c}); truncation is named, every array is "
          f"bounded, and all {len(_MAX_TOKENS)} budgets cover their schema.")
