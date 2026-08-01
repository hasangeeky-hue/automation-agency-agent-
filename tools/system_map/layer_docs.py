# -*- coding: utf-8 -*-
"""Semantic extraction for the 8 docs, done inline by the host agent.

The point of this pass is not to index prose. It is to connect the WHY that
lives in the spec and the deploy docs to the WHAT that lives in the code, so a
question like "why is the QA gate the only skill with no fallback" has an
answer in the graph instead of only in a markdown file nobody re-reads.
"""
import json
import os
from pathlib import Path

ROOT = Path(".").resolve()


def sf(rel):
    """Absolute path, verbatim in the form detect listed it."""
    return str(ROOT / rel).replace("/", os.sep)


SPEC = sf("content-engine-prompt-engineering.md")
DEPLOY = sf("deploy/DEPLOY.md")
HOST = sf("deploy/HOSTINGER-SETUP.md")
SIMPLE = sf("deploy/SIMPLE-START.md")
N8N = sf("n8n/README.md")
CLAUDEMD = sf("CLAUDE.md")
COMPOSE = sf("deploy/docker-compose.yml")
REQS = sf("deploy/requirements.txt")

N, E, H = [], [], []


def node(nid, label, ftype, src, loc=None, rationale=None):
    d = {"id": nid, "label": label, "file_type": ftype, "source_file": src,
         "source_location": loc, "source_url": None, "captured_at": None,
         "author": None, "contributor": None}
    if rationale:
        d["rationale"] = rationale
    N.append(d)
    return nid


def edge(s, t, rel, conf="EXTRACTED", score=1.0, src=SPEC, loc=None):
    E.append({"source": s, "target": t, "relation": rel, "confidence": conf,
              "confidence_score": score, "source_file": src,
              "source_location": loc, "weight": 1.0})


P = "content_engine_prompt_engineering"

# ---- SECTION 1-5: the rules and the reasoning behind them ----------------
r1 = node(f"{P}_rule_code_over_llm", "Rule: 70% code, 30% LLM", "rationale", SPEC,
          "SECTION 1",
          "Data-plumbing (fetch/parse/dedupe/store/send) must never be routed "
          "through a model. Only language and judgment go to an LLM. This is "
          "the engine's primary cost lever.")
r2 = node(f"{P}_rule_human_gate", "Rule: one human approval gate", "rationale",
          SPEC, "SECTION 1",
          "No skill publishes or sends outbound without a human-approved flag "
          "on the job. Stated as one of two rules that NEVER change.")
bb = node(f"{P}_blackboard_pattern", "Blackboard pattern", "concept", SPEC,
          "SECTION 2",
          "Skills NEVER call each other. They read and write a shared job "
          "record in Postgres, and the orchestrator moves the job by reading "
          "job.status. Chosen so any one skill can fail without breaking a "
          "call chain.")
jr = node(f"{P}_job_record", "The job record", "concept", SPEC, "SECTION 2",
          "Single source of truth: job_id, type, status, payload, approved, "
          "cost_so_far_usd, model_log.")
pa = node(f"{P}_pipeline_a", "Pipeline A - Content", "concept", SPEC, "SECTION 3",
          "1 -> 3 -> 4 -> 5 -> 6 -> 7 -> [HUMAN GATE] -> 8 -> 9 -> 10, "
          "looping back to 4.")
pb = node(f"{P}_pipeline_b", "Pipeline B - Outreach", "concept", SPEC, "SECTION 3",
          "12 -> 13 -> 11 -> 14(write) -> 7(CAN-SPAM) -> [HUMAN GATE] -> "
          "14(send) -> 9 -> 10.")
mr = node(f"{P}_model_routing", "Model routing", "concept", SPEC, "SECTION 4",
          "One config controls everything: FRONTIER for judgment, voice and "
          "compliance; CHEAP for classify, summarize and narrate.")
cache = node(f"{P}_prompt_caching", "Prompt caching prefix", "rationale", SPEC,
             "SECTION 5 #1",
             "SECTION 6 + 7 load as a cached prefix so only the small per-job "
             "payload is ever uncached.")
cap = node(f"{P}_budget_caps", "Budget caps", "rationale", SPEC, "SECTION 5 #10",
           "Per-job and per-day ceilings; on breach the engine stops and "
           "alerts rather than overspending.")
maxtok = node(f"{P}_cap_output_tokens", "Cap output tokens", "rationale", SPEC,
              "SECTION 5 #5",
              "Set max_tokens to the SMALLEST that fits the schema. Read too "
              "literally this is exactly what truncated site_intelligence at "
              "500 tokens against an 805-token schema and killed 15 content "
              "jobs: the budget must FIT the schema, not merely be small.")
retry = node(f"{P}_validate_retry_once", "Validate + retry once", "rationale",
             SPEC, "SECTION 5 #9",
             "Never loop: retry once, escalate to the fallback model, then "
             "fail loud.")
gate7 = node(f"{P}_qa_no_fallback", "QA gate has no fallback", "rationale", SPEC,
             "SECTION 4",
             "qa_compliance is the only skill with fallback=None: a compliance "
             "check must never be silently downgraded to a cheaper model.")
fixtures = node(f"{P}_dev_on_fixtures", "Develop on fixtures", "rationale", SPEC,
                "SECTION 5 #8",
                "USE_FIXTURES=1 reads saved responses, so development costs "
                "nothing in API spend.")

# ---- spec -> the code that implements it --------------------------------
edge(r2, "content_engine_orchestrator_advance", "rationale_for", "EXTRACTED", 1.0)
edge(r2, "content_engine_api_api_start", "rationale_for", "INFERRED", 0.95)
edge(r2, "content_engine_orchestrator_auto_approve_stale", "rationale_for",
     "INFERRED", 0.95)
edge(bb, "content_engine_orchestrator_tick", "implements", "EXTRACTED", 1.0)
edge(bb, "content_engine_orchestrator_run_until_blocked", "implements",
     "INFERRED", 0.95)
edge(jr, "content_engine_orchestrator_new_job", "implements", "EXTRACTED", 1.0)
edge(pa, "content_engine_orchestrator_flow_for", "references", "INFERRED", 0.85)
edge(pb, "content_engine_orchestrator_flow_for", "references", "INFERRED", 0.85)
edge(mr, "content_engine_providers_call_provider", "implements", "EXTRACTED", 1.0)
edge(mr, "content_engine_providers_build_prompt", "implements", "INFERRED", 0.95)
edge(cap, "content_engine_orchestrator_budget_caps", "rationale_for",
     "EXTRACTED", 1.0)
edge(cap, "content_engine_orchestrator_over_budget", "rationale_for",
     "EXTRACTED", 1.0)
edge(cap, "content_engine_orchestrator_set_budget_caps", "rationale_for",
     "INFERRED", 0.95)
edge(maxtok, "content_engine_providers_max_tokens_for", "rationale_for",
     "EXTRACTED", 1.0)
edge(maxtok, "content_engine_providers_schema_token_estimate", "rationale_for",
     "INFERRED", 0.95)
edge(maxtok, "content_engine_providers_truncated", "rationale_for",
     "INFERRED", 0.85)
edge(retry, "content_engine_orchestrator_run_llm_skill", "rationale_for",
     "INFERRED", 0.85)
edge(gate7, "content_engine_prep_in_qa_compliance", "rationale_for",
     "INFERRED", 0.85)
edge(cache, "content_engine_providers_build_prompt", "rationale_for",
     "INFERRED", 0.85)
edge(r1, bb, "conceptually_related_to", "INFERRED", 0.85)
edge(r1, mr, "conceptually_related_to", "INFERRED", 0.85)
edge(fixtures, "content_engine_selftest_run_smoke", "rationale_for",
     "INFERRED", 0.75)

# ---- deployment and operations docs -------------------------------------
dep = node("deploy_deploy_vps_deployment", "VPS deployment procedure", "document",
           DEPLOY, None,
           "Clone, configure secrets, docker compose build, health-check every "
           "connection, then wire n8n.")
upd = node("deploy_deploy_update_after_change", "Updating after a code change",
           "rationale", DEPLOY, None,
           "The image bakes the source in via COPY *.py, so a git pull alone "
           "changes nothing that is running - the container must be rebuilt.")
hs = node("deploy_hostinger_setup_accounts", "Accounts to connect", "document",
          HOST, "PART 1",
          "Tiered A-E: CORE to run at all, then content, optional, outreach, "
          "notifications.")
minlive = node("deploy_hostinger_setup_minimum_live",
               "Minimum to go live with content", "concept", HOST, None,
               "The smallest set of connected accounts that can produce and "
               "publish web content.")
n8nw = node("n8n_readme_workflows", "n8n workflows", "document", N8N, None,
            "Three workflow definitions: intake, approve, measure-cron. "
            "Superseded by the engine's own cadence in the worker, so n8n is "
            "no longer required for scheduling.")
simple = node("deploy_simple_start_quickstart", "Simple start quickstart",
              "document", SIMPLE, None,
              "The shortest path from nothing to a running engine on Hostinger.")
comp = node("deploy_docker_compose_services", "Compose services: db, api, worker",
            "concept", COMPOSE, None,
            "Postgres with a healthcheck, the FastAPI service, and the worker "
            "running main.py.")
vol = node("deploy_docker_compose_engine_db_volume", "engine_db volume", "concept",
           COMPOSE, None,
           "A single docker volume holding all settings, leads, deals and job "
           "history - the reason an off-box backup matters.")
reqs = node("deploy_requirements_dependencies", "Python dependencies", "document",
            REQS, None, "The pinned runtime dependency set installed into the image.")
cmd = node("claude_graphify_rules", "Graphify project rules", "document",
           CLAUDEMD, None,
           "Instructs the assistant to query the knowledge graph before reading "
           "raw source, and to run graphify update after code changes.")

edge(dep, comp, "references", "EXTRACTED", 1.0, DEPLOY)
edge(comp, vol, "shares_data_with", "EXTRACTED", 1.0, COMPOSE)
edge(upd, comp, "references", "INFERRED", 0.95, DEPLOY)
edge(hs, minlive, "references", "EXTRACTED", 1.0, HOST)
edge(simple, dep, "semantically_similar_to", "INFERRED", 0.85, SIMPLE)
edge(n8nw, "content_engine_scheduler_run_due_work", "semantically_similar_to",
     "INFERRED", 0.85, N8N)
edge(vol, "content_engine_store_pg_pgjobstore", "references",
     "INFERRED", 0.85, COMPOSE)
edge(comp, "main_run", "references", "INFERRED", 0.85, COMPOSE)
edge(hs, "content_engine_connectors_status", "references", "INFERRED", 0.75, HOST)
edge(minlive, "content_engine_connectors_wire_all", "references", "INFERRED",
     0.75, HOST)
edge(cmd, "content_engine_dashboard_dashboard_html", "references", "INFERRED",
     0.65, CLAUDEMD)

# ---- hyperedges: groups that only make sense together -------------------
H.append({"id": "content_pipeline_a_flow", "label": "Pipeline A: the content flow",
          "nodes": [pa, "content_engine_orchestrator_advance",
                    "content_engine_code_skills_publisher",
                    "content_engine_collect_analytics_for", r2],
          "relation": "participate_in", "confidence": "INFERRED",
          "confidence_score": 0.85, "source_file": SPEC})
H.append({"id": "cost_control_mechanism",
          "label": "How spend is actually held down",
          "nodes": [cap, maxtok, "content_engine_orchestrator_budget_caps",
                    "content_engine_providers_schema_token_estimate", cache],
          "relation": "form", "confidence": "INFERRED",
          "confidence_score": 0.85, "source_file": SPEC})
H.append({"id": "deployment_chain", "label": "What it takes to run this on a VPS",
          "nodes": [dep, comp, vol, hs, upd],
          "relation": "participate_in", "confidence": "EXTRACTED",
          "confidence_score": 1.0, "source_file": DEPLOY})

out = {"nodes": N, "edges": E, "hyperedges": H,
       "input_tokens": 0, "output_tokens": 0}
Path("graphify-out/.graphify_semantic.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"semantic: {len(N)} nodes, {len(E)} edges, {len(H)} hyperedges")
