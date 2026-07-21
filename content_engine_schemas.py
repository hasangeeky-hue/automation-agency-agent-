"""
content_engine_schemas.py
============================================================================
Output schemas for every LLM skill in the Content Engine (see
content-engine-prompt-engineering.md, SECTION 8).

Purpose: give the SECTION 4 dispatch wrapper something concrete to validate
against, so a malformed model response fails LOUD (retry once -> fallback ->
SkillFailed) instead of flowing garbage down the job blackboard.

Usage in the wrapper:
    from content_engine_schemas import SCHEMAS
    ok, errs = SCHEMAS[skill_name].validate(out)   # out = parsed JSON dict

Every skill's response may ALSO be the SECTION 6 escape object
    {"error": "reason", "partial": {...}}   (partial optional)
which .validate() treats as valid-but-failed: it returns ok=True so the
wrapper does not crash, but the object carries an "error" key the
orchestrator branches on. If you want the wrapper to RETRY on an error
object, check `out.get("error")` after a successful validate.

Pure-code skills (publisher, lead_sourcing, orchestrator, authority_backlinks)
have no schema here. authority_backlinks, when it narrates, reuses
"site_intelligence".

Dependency: jsonschema (pip install jsonschema). If it is not installed, a
lightweight built-in fallback validates required top-level keys + basic types
so the module still runs in dev.
============================================================================
"""

from __future__ import annotations

try:
    from jsonschema import Draft202012Validator  # type: ignore
    _HAVE_JSONSCHEMA = True
except Exception:  # pragma: no cover - dev fallback
    _HAVE_JSONSCHEMA = False


# ---------------------------------------------------------------------------
# The SECTION 6 escape object. Any skill may return this instead of its
# normal output. `partial` is optional and unconstrained.
# ---------------------------------------------------------------------------
ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {"type": "string"},
        "partial": {"type": "object"},
    },
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Reusable sub-schemas
# ---------------------------------------------------------------------------
_SEVERITY_ISSUE = {
    "type": "object",
    "required": ["issue", "severity", "fix", "why_it_matters"],
    "properties": {
        "issue": {"type": "string"},
        "severity": {"enum": ["critical", "high", "medium"]},
        "fix": {"type": "string"},
        "why_it_matters": {"type": "string"},
    },
    "additionalProperties": False,
}

_GSC_QUERY = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "position": {"type": "number"},
        "impressions": {"type": "number"},
        "clicks": {"type": "number"},
    },
    "additionalProperties": True,
}


# ---------------------------------------------------------------------------
# 8.1  SITE INTELLIGENCE  (also used by authority_backlinks narrate)
# ---------------------------------------------------------------------------
SITE_INTELLIGENCE = {
    "type": "object",
    "required": ["health_score", "top_issues", "quick_wins",
                 "content_opportunities", "summary"],
    "properties": {
        "health_score": {"type": "number"},
        "top_issues": {"type": "array", "maxItems": 5, "items": _SEVERITY_ISSUE},
        "quick_wins": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
        "content_opportunities": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.2  COMPETITOR INTEL
# ---------------------------------------------------------------------------
COMPETITOR_INTEL = {
    "type": "object",
    "required": ["competitors", "market_gap", "differentiation_angles"],
    "properties": {
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "content_types", "topics_they_own",
                             "topics_they_miss", "weakness"],
                "properties": {
                    "name": {"type": "string"},
                    "content_types": {"type": "array", "items": {"type": "string"}},
                    "topics_they_own": {"type": "array", "items": {"type": "string"}},
                    "topics_they_miss": {"type": "array", "items": {"type": "string"}},
                    "weakness": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "market_gap": {
            "type": "object",
            "required": ["opportunity", "why_open"],
            "properties": {
                "opportunity": {"type": "string"},
                "why_open": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "differentiation_angles": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["angle", "how", "example_title"],
                "properties": {
                    "angle": {"type": "string"},
                    "how": {"type": "string"},
                    "example_title": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.3  CONTENT STRATEGIST
# ---------------------------------------------------------------------------
CONTENT_STRATEGIST = {
    "type": "object",
    "required": ["week_of", "calendar", "notes"],
    "properties": {
        "week_of": {"type": "string"},
        "calendar": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["date", "type", "working_title", "primary_keyword",
                             "target_segment", "business_goal", "priority",
                             "rationale"],
                "properties": {
                    "date": {"type": "string"},
                    "type": {"enum": ["blog", "social_carousel", "reel", "email"]},
                    "working_title": {"type": "string"},
                    "primary_keyword": {"type": "string"},
                    "target_segment": {"enum": ["champions", "active",
                                                "window_shoppers", "at_risk", "all"]},
                    "business_goal": {"enum": ["sales", "awareness", "retention"]},
                    "priority": {"enum": ["high", "medium", "low"]},
                    "rationale": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.4  CONTENT PRODUCER  (two sub-calls -> two schemas)
# ---------------------------------------------------------------------------
CONTENT_PRODUCER_COPY = {
    "type": "object",
    "required": ["title", "body", "cta_text"],
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "meta_title": {"type": "string"},        # blog only
        "meta_description": {"type": "string"},   # blog only
        "cta_text": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},  # social only
    },
    "additionalProperties": False,
}

CONTENT_PRODUCER_IMAGE = {
    "type": "object",
    "required": ["image_prompts"],
    "properties": {
        "image_prompts": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": ["platform", "prompt", "dimensions", "notes"],
                "properties": {
                    "platform": {"type": "string"},
                    "prompt": {"type": "string"},
                    "dimensions": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.5  SEO OPTIMIZER
# ---------------------------------------------------------------------------
SEO_OPTIMIZER = {
    "type": "object",
    "required": ["seo_ready", "checks", "fixes"],
    "properties": {
        "seo_ready": {"type": "boolean"},
        "checks": {
            "type": "object",
            "required": ["keyword_in_title", "keyword_in_first_100_words",
                         "keyword_density_pct", "word_count", "readability_grade",
                         "internal_link_suggestions", "meta_title",
                         "meta_description"],
            "properties": {
                "keyword_in_title": {"type": "boolean"},
                "keyword_in_first_100_words": {"type": "boolean"},
                "keyword_density_pct": {"type": "number"},
                "word_count": {"type": "number"},
                "readability_grade": {"type": "number"},
                "internal_link_suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["anchor", "target_hint", "placement"],
                        "properties": {
                            "anchor": {"type": "string"},
                            "target_hint": {"type": "string"},
                            "placement": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "meta_title": {"type": "string"},
                "meta_description": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "fixes": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.6  QA & COMPLIANCE GATE
# ---------------------------------------------------------------------------
QA_COMPLIANCE = {
    "type": "object",
    "required": ["verdict", "brand_voice_match", "issues", "claims_check",
                 "compliance"],
    "properties": {
        "verdict": {"enum": ["pass", "revise", "block"]},
        "brand_voice_match": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["issue", "location", "severity", "fix"],
                "properties": {
                    "issue": {"type": "string"},
                    "location": {"type": "string"},
                    "severity": {"enum": ["block", "high", "low"]},
                    "fix": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "claims_check": {
            "type": "object",
            "required": ["all_defensible", "flagged_claims"],
            "properties": {
                "all_defensible": {"type": "boolean"},
                "flagged_claims": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        "compliance": {
            "type": "object",
            "required": ["can_spam_ok", "has_unsubscribe", "has_physical_address",
                         "non_deceptive_subject", "disclaimers_present"],
            "properties": {
                "can_spam_ok": {"type": "boolean"},
                "has_unsubscribe": {"type": "boolean"},
                "has_physical_address": {"type": "boolean"},
                "non_deceptive_subject": {"type": "boolean"},
                "disclaimers_present": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.7  ANALYTICS NARRATIVE
# ---------------------------------------------------------------------------
ANALYTICS_FUNNEL = {
    "type": "object",
    "required": ["headline", "what_worked", "what_dropped", "biggest_leak",
                 "recommended_focus_next"],
    "properties": {
        "headline": {"type": "string"},
        "what_worked": {"type": "array", "maxItems": 2, "items": {"type": "string"}},
        "what_dropped": {"type": "array", "maxItems": 2, "items": {"type": "string"}},
        "biggest_leak": {
            "type": "object",
            "required": ["stage", "users_lost", "likely_cause", "suggested_fix"],
            "properties": {
                "stage": {"type": "string"},
                "users_lost": {"type": "number"},
                "likely_cause": {"type": "string"},
                "suggested_fix": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "recommended_focus_next": {"type": "string"},
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.8  OPTIMIZER (learning loop)
# ---------------------------------------------------------------------------
OPTIMIZER = {
    "type": "object",
    "required": ["insights", "double_down", "reduce_or_cut", "next_cycle"],
    "properties": {
        "insights": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["finding", "evidence", "impact"],
                "properties": {
                    "finding": {"type": "string"},
                    "evidence": {"type": "string"},
                    "impact": {"enum": ["high", "medium", "low"]},
                },
                "additionalProperties": False,
            },
        },
        "double_down": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["what", "reason"],
                "properties": {"what": {"type": "string"},
                               "reason": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "reduce_or_cut": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["what", "reason"],
                "properties": {"what": {"type": "string"},
                               "reason": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "next_cycle": {
            "type": "object",
            "required": ["content_mix", "topic_priorities",
                         "winning_email_subject_style", "platform_focus"],
            "properties": {
                "content_mix": {"type": "string"},
                "topic_priorities": {"type": "array", "items": {"type": "string"}},
                "winning_email_subject_style": {"type": "string"},
                "platform_focus": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.9  SEGMENTER (labels)
# ---------------------------------------------------------------------------
SEGMENTER = {
    "type": "object",
    "required": ["segments"],
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["bucket_id", "label", "one_line_profile",
                             "recommended_action", "email_tone", "content_frequency"],
                "properties": {
                    "bucket_id": {"type": "number"},
                    "label": {"enum": ["champions", "active",
                                       "window_shoppers", "at_risk"]},
                    "one_line_profile": {"type": "string"},
                    "recommended_action": {"type": "string"},
                    "email_tone": {"enum": ["exclusive", "helpful",
                                            "urgency", "winback"]},
                    "content_frequency": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.10  LEAD QUALIFIER (batched)
# ---------------------------------------------------------------------------
LEAD_QUALIFIER = {
    "type": "object",
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "category", "fit_score", "priority", "reason",
                             "disqualify_reason"],
                "properties": {
                    "id": {"type": "string"},
                    "category": {"enum": ["ecommerce", "saas", "agency",
                                          "other", "disqualified"]},
                    "fit_score": {"type": ["number", "null"]},
                    "priority": {"enum": ["urgent", "high", "medium", "low"]},
                    "reason": {"type": "string"},
                    "disqualify_reason": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 8.11  OUTREACH COPY
# ---------------------------------------------------------------------------
OUTREACH_COPY = {
    "type": "object",
    "required": ["subject_variants", "body", "cta", "personalization_used"],
    "properties": {
        "subject_variants": {"type": "array", "minItems": 2, "maxItems": 2,
                             "items": {"type": "string"}},
        "body": {"type": "string"},
        "cta": {"type": "string"},
        "personalization_used": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# ADS OPTIMIZER (Skill 16) - optimize ads using performance + SEO signals
# ---------------------------------------------------------------------------
ADS_OPTIMIZER = {
    "type": "object",
    "required": ["summary", "campaign_actions", "keyword_actions",
                 "seo_alignment", "budget_reallocation", "expected_impact"],
    "properties": {
        "summary": {"type": "string"},
        "campaign_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["campaign", "action", "change_pct", "reason", "evidence"],
                "properties": {
                    "campaign": {"type": "string"},
                    "action": {"enum": ["increase_budget", "decrease_budget",
                                        "pause", "maintain"]},
                    "change_pct": {"type": "number"},
                    "reason": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "keyword_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["keyword", "action", "reason", "source"],
                "properties": {
                    "keyword": {"type": "string"},
                    "action": {"enum": ["raise_bid", "lower_bid", "pause",
                                        "add_negative", "add_from_seo"]},
                    "reason": {"type": "string"},
                    "source": {"enum": ["performance", "seo"]},
                },
                "additionalProperties": False,
            },
        },
        "seo_alignment": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["insight", "action"],
                "properties": {"insight": {"type": "string"},
                               "action": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "budget_reallocation": {
            "type": "object",
            "required": ["from", "to", "amount_pct", "reason"],
            "properties": {
                "from": {"type": "string"},
                "to": {"type": "string"},
                "amount_pct": {"type": "number"},
                "reason": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "expected_impact": {"type": "string"},
    },
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Validator wrapper: .validate(obj) -> (ok: bool, errors: list[str])
# Accepts either the skill schema OR the SECTION 6 error object.
# ---------------------------------------------------------------------------
class Schema:
    def __init__(self, name: str, schema: dict):
        self.name = name
        self.schema = schema
        if _HAVE_JSONSCHEMA:
            self._v = Draft202012Validator(schema)
            self._err = Draft202012Validator(ERROR_SCHEMA)

    def validate(self, obj):
        """Return (ok, errors). ok=True also for a valid error object."""
        if not isinstance(obj, dict):
            return False, [f"{self.name}: output is not a JSON object"]

        if _HAVE_JSONSCHEMA:
            errs = sorted(self._v.iter_errors(obj), key=lambda e: list(e.path))
            if not errs:
                return True, []
            # Try the escape object before failing.
            if not list(self._err.iter_errors(obj)):
                return True, []  # valid {"error": ...} — wrapper branches on it
            return False, [f"{self.name}: {e.message} at /{'/'.join(map(str, e.path))}"
                           for e in errs]

        # ---- lightweight fallback (no jsonschema installed) ----
        if "error" in obj and isinstance(obj["error"], str):
            return True, []
        missing = [k for k in self.schema.get("required", []) if k not in obj]
        if missing:
            return False, [f"{self.name}: missing required key '{k}'" for k in missing]
        return True, []


# ---------------------------------------------------------------------------
# Registry — keys match ROUTES in SECTION 4.
# content_producer has two sub-calls; register both explicitly and alias the
# ROUTES key "content_producer" to the copy schema (sub-call A).
# ---------------------------------------------------------------------------
SCHEMAS = {
    "site_intelligence":       Schema("site_intelligence", SITE_INTELLIGENCE),
    "authority_backlinks":     Schema("authority_backlinks", SITE_INTELLIGENCE),  # reuses narrate
    "competitor_intel":        Schema("competitor_intel", COMPETITOR_INTEL),
    "content_strategist":      Schema("content_strategist", CONTENT_STRATEGIST),
    "content_producer":        Schema("content_producer", CONTENT_PRODUCER_COPY),      # sub-call A
    "content_producer_copy":   Schema("content_producer_copy", CONTENT_PRODUCER_COPY),
    "content_producer_image":  Schema("content_producer_image", CONTENT_PRODUCER_IMAGE),  # sub-call B
    "seo_optimizer":           Schema("seo_optimizer", SEO_OPTIMIZER),
    "qa_compliance":           Schema("qa_compliance", QA_COMPLIANCE),
    "analytics_funnel":        Schema("analytics_funnel", ANALYTICS_FUNNEL),
    "optimizer":               Schema("optimizer", OPTIMIZER),
    "segmenter":               Schema("segmenter", SEGMENTER),
    "lead_qualifier":          Schema("lead_qualifier", LEAD_QUALIFIER),
    "outreach_copy":           Schema("outreach_copy", OUTREACH_COPY),
    "ads_optimizer":           Schema("ads_optimizer", ADS_OPTIMIZER),
}

# Pure-code skills have no output schema:
#   publisher, lead_sourcing, orchestrator
# authority_backlinks only needs a schema when it narrates (reuses site_intelligence).


if __name__ == "__main__":
    # Smoke test: every registered schema validates a minimal error object,
    # and rejects a plainly wrong shape.
    for name, s in SCHEMAS.items():
        ok, _ = s.validate({"error": "insufficient input"})
        assert ok, f"{name} should accept the error escape object"
        bad_ok, _ = s.validate({"totally": "wrong"})
        assert not bad_ok, f"{name} should reject a wrong-shaped object"
    print(f"OK — {len(SCHEMAS)} schemas registered and self-checked "
          f"(jsonschema={'on' if _HAVE_JSONSCHEMA else 'fallback'}).")
