"""
content_engine_brand.py
============================================================================
CI / brand-identity feeding (Phase 2). The founder builds a corporate brand
identity (voice, tone, do/don't, positioning, proof points, colors) and drops it
in as a file; every content agent then writes on-brand.

Load order (first that exists wins):
  1. env CI_JSON      — the whole identity as inline JSON
  2. env CI_FILE      — a path to a .json or .md/.txt identity file
  3. nothing          — agents fall back to the built-in brand defaults

get_ci()        -> dict (or {} if none)
get_ci_block()  -> a compact text block appended to every prompt's brand context
                   (content_engine_providers._render_brand calls this)

Recognised JSON fields (all optional): brand_name, tagline, voice, tone,
positioning, offer, proof_points (list), audience, do (list), dont (list),
banned_words (list), colors (list), links (dict). A .md/.txt file is used as-is
as the voice/guidance block.
============================================================================
"""

from __future__ import annotations

import json
import os

_CACHE = None  # parsed once per process


def _load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    ci: dict = {}
    raw = os.getenv("CI_JSON", "").strip()
    path = os.getenv("CI_FILE", "").strip()
    try:
        if raw:
            ci = json.loads(raw)
        elif path and os.path.exists(path):
            text = open(path, encoding="utf-8").read()
            if path.lower().endswith(".json"):
                ci = json.loads(text)
            else:
                ci = {"_freeform": text.strip()}
    except Exception:
        ci = {}
    _CACHE = ci if isinstance(ci, dict) else {}
    return _CACHE


def reset_cache() -> None:
    """For tests / hot-reload after the founder updates the CI file."""
    global _CACHE
    _CACHE = None


def get_ci() -> dict:
    return dict(_load())


def _lines(label, val) -> str:
    if not val:
        return ""
    if isinstance(val, (list, tuple)):
        val = "; ".join(str(v) for v in val if v)
    return f"{label}: {val}\n"


def get_ci_block() -> str:
    """Compact brand-identity guidance appended to the cached prompt prefix.
    Empty string when no CI is configured (agents then use built-in defaults)."""
    ci = _load()
    if not ci:
        return ""
    if ci.get("_freeform"):
        return "BRAND IDENTITY (follow this voice exactly):\n" + ci["_freeform"]
    out = ["BRAND IDENTITY (follow this exactly):"]
    out.append(_lines("Brand", ci.get("brand_name")))
    out.append(_lines("Tagline", ci.get("tagline")))
    out.append(_lines("Voice", ci.get("voice")))
    out.append(_lines("Tone", ci.get("tone")))
    out.append(_lines("Positioning", ci.get("positioning")))
    out.append(_lines("What we sell", ci.get("offer")))
    out.append(_lines("Audience", ci.get("audience")))
    out.append(_lines("Proof points (cite only these)", ci.get("proof_points")))
    out.append(_lines("Always do", ci.get("do")))
    out.append(_lines("Never do", ci.get("dont")))
    out.append(_lines("Never use these words", ci.get("banned_words")))
    return "".join(p for p in out if p).strip()


if __name__ == "__main__":
    # No CI configured -> empty, agents use defaults.
    reset_cache()
    os.environ.pop("CI_JSON", None)
    os.environ.pop("CI_FILE", None)
    assert get_ci() == {} and get_ci_block() == ""

    # Inline JSON identity.
    os.environ["CI_JSON"] = json.dumps({
        "brand_name": "Anthropos Automation",
        "voice": "plain, confident, no hype",
        "positioning": "pure programmatic automation, not generic chatbots",
        "proof_points": ["runs on n8n", "one dashboard"],
        "dont": ["invent client results", "use jargon"],
    })
    reset_cache()
    b = get_ci_block()
    assert "Anthropos Automation" in b and "Never do: invent client results" in b
    assert "not generic chatbots" in b
    os.environ.pop("CI_JSON", None)
    reset_cache()
    print("OK — CI/brand feeding: empty->defaults, JSON identity -> guidance block. No network.")
