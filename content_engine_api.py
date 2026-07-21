"""
content_engine_api.py
============================================================================
REST bridge so n8n (or anything) can drive and TEST the engine over HTTP.

Two layers:
  1. Core functions (api_*) — plain Python, no HTTP. Fully unit-tested offline.
  2. build_app() — wraps them in FastAPI routes (only if fastapi is installed).

Endpoints (what n8n calls):
  GET  /health                      -> preflight (every connection)
  GET  /skills                      -> list runnable skills
  POST /skills/{skill}/taste        -> run ONE agent on a literal INPUT and see
                                       its output. This is "taste every agent":
                                       test each skill in isolation before launch.
                                       body: {"input": {...}, "brand": {...}}
  POST /jobs                        -> create a job. body: {type, brand, payload}
  GET  /jobs/{id}                   -> status + payload
  POST /jobs/{id}/approve           -> flip the human gate
  POST /jobs/{id}/ready_to_measure  -> flip the measurement gate (n8n cron)
  POST /tick                        -> advance one runnable job (the worker beat)

Run the server (needs `pip install fastapi uvicorn`):
  uvicorn content_engine_api:app --host 0.0.0.0 --port 8000
Dev with zero API cost: USE_FIXTURES=1 (after RECORD_FIXTURES=1 capture).
============================================================================
"""

from __future__ import annotations

import os
from typing import Optional

import content_engine_orchestrator as orch
from content_engine_providers import build_prompt, call_provider
from content_engine_health import run_health

# The engine's job store. Swap to Postgres by setting STORE=pg + DATABASE_URL.
_STORE = None


def get_store():
    global _STORE
    if _STORE is None:
        if os.getenv("STORE", "memory").lower() == "pg":
            from content_engine_store_pg import PgJobStore, init_db
            _STORE = PgJobStore(os.environ["DATABASE_URL"])
            init_db(_STORE)
        else:
            _STORE = orch.InMemoryJobStore()
    return _STORE


# ---------------------------------------------------------------------------
# Core API functions (no HTTP)
# ---------------------------------------------------------------------------
_TASTEABLE = {
    "site_intelligence", "competitor_intel", "content_strategist",
    "content_producer", "content_producer_image", "seo_optimizer",
    "qa_compliance", "analytics_funnel", "optimizer", "segmenter",
    "lead_qualifier", "outreach_copy", "ads_optimizer",
}


def api_health() -> dict:
    return run_health()


def api_list_skills() -> dict:
    return {"skills": sorted(_TASTEABLE),
            "code_skills": sorted(orch.CODE_HANDLERS.keys()),
            "pipelines": {"content_piece": list(orch.FLOW_CONTENT.keys()),
                          "outreach_campaign": list(orch.FLOW_OUTREACH.keys())}}


def api_taste_skill(skill: str, skill_input: dict, brand: Optional[dict] = None,
                    model: Optional[str] = None) -> dict:
    """Run ONE skill on a LITERAL input (bypasses prepare_input) so you can test
    an agent in isolation. Uses the skill's routed model unless overridden."""
    if skill not in _TASTEABLE:
        return {"error": f"unknown or non-LLM skill '{skill}'",
                "tasteable": sorted(_TASTEABLE)}
    route = orch.ROUTES.get(skill, {})
    chosen = model or route.get("engine")
    if not chosen or chosen == "code":
        return {"error": f"skill '{skill}' has no LLM engine to taste"}
    spec = build_prompt(skill, {"payload": skill_input, "brand": brand or {}})
    result = call_provider(chosen, spec)
    return {"skill": skill, "model": chosen, "output": result.data,
            "usage": result.usage, "cost_usd": result.cost_usd,
            "warnings": result.warnings}


def api_create_job(job_type: str, brand: dict, payload: dict,
                   job_id: Optional[str] = None) -> dict:
    if job_type not in ("content_piece", "outreach_campaign"):
        return {"error": f"unknown job type '{job_type}'"}
    store = get_store()
    jid = job_id or f"job_{abs(hash((job_type, str(payload)))) % 10_000_000}"
    job = orch.new_job(jid, job_type, brand, payload)
    store.save(job)
    return {"job_id": jid, "status": job["status"]}


def api_list_jobs(status: Optional[str] = None) -> dict:
    """List jobs, optionally by status. Used by the n8n measurement cron to find
    jobs sitting in 'published' / 'sent' that are due for measurement."""
    store = get_store()
    if not hasattr(store, "list_jobs"):
        return {"jobs": [], "error": "store has no list_jobs"}
    jobs = store.list_jobs(status)
    return {"jobs": [{"job_id": j["job_id"], "type": j["type"],
                      "status": j["status"]} for j in jobs]}


def api_list_measurable() -> dict:
    """Jobs whose measurement window has already opened (published/sent with an
    elapsed measure_at). For monitoring; the engine opens the gate by time on
    its own, so a plain /tick advances them without an explicit flip."""
    store = get_store()
    if not hasattr(store, "list_jobs"):
        return {"jobs": []}
    out = []
    for status in ("published", "sent"):
        for j in store.list_jobs(status):
            step = orch.flow_for(j).get(j["status"])
            if step and orch._wait_open(j, step):
                out.append({"job_id": j["job_id"], "type": j["type"],
                            "status": j["status"], "measure_at": j.get("measure_at")})
    return {"jobs": out}


def api_get_job(job_id: str) -> dict:
    try:
        job = get_store().get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    return {"job_id": job_id, "type": job["type"], "status": job["status"],
            "approved": job.get("approved", False),
            "ready_to_measure": job.get("ready_to_measure", False),
            "cost_so_far_usd": job.get("cost_so_far_usd", 0.0),
            "payload": job.get("payload", {})}


def _set_flag(job_id: str, flag: str) -> dict:
    store = get_store()
    try:
        job = store.get(job_id)
    except KeyError:
        return {"error": "not found", "job_id": job_id}
    job[flag] = True
    store.save(job)
    return {"job_id": job_id, flag: True, "status": job["status"]}


def api_approve(job_id: str) -> dict:
    return _set_flag(job_id, "approved")


def api_ready_to_measure(job_id: str) -> dict:
    return _set_flag(job_id, "ready_to_measure")


def api_tick() -> dict:
    status = orch.tick(get_store())
    return {"advanced": status is not None, "status": status}


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def api_dashboard_html() -> str:
    """A single self-contained HTML page: the job list + statuses + cost. This
    is the 'show me the list' view — open http://<host>:8000/ in a browser."""
    store = get_store()
    jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
    # newest-ish first isn't guaranteed by in-memory; sort by status grouping
    gate = {"AWAITING_APPROVAL"}
    term = {"optimized", "failed", "revision_needed", "halted_budget"}
    total_cost = sum(float(j.get("cost_so_far_usd", 0)) for j in jobs)
    rows = []
    for j in jobs:
        st = j.get("status", "")
        color = "#FF5C8A" if st in gate else ("#46E08B" if st == "optimized"
                 else ("#9AA6C6" if st in term else "#2FE3D2"))
        rows.append(
            f"<tr><td class='mono'>{_esc(j.get('job_id'))}</td>"
            f"<td>{_esc(j.get('type'))}</td>"
            f"<td><span class='pill' style='color:{color};border-color:{color}'>{_esc(st)}</span></td>"
            f"<td>{'yes' if j.get('approved') else ''}</td>"
            f"<td class='mono'>${float(j.get('cost_so_far_usd', 0)):.4f}</td></tr>")
    body = "".join(rows) or "<tr><td colspan='5' style='color:#8891B8'>No jobs yet. Create one via POST /jobs or the intake webhook.</td></tr>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Content Engine</title><style>
:root{{color-scheme:dark}}
body{{margin:0;background:#080B14;color:#EAF0FF;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:28px 20px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#9AA6C6;font-size:13px;margin-bottom:20px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
.card{{background:#0F1626;border:1px solid #1b2540;border-radius:12px;padding:14px 18px;min-width:120px}}
.card b{{font-size:22px;display:block}} .card span{{color:#9AA6C6;font-size:12px}}
table{{width:100%;border-collapse:collapse;background:#0C1120;border:1px solid #1b2540;border-radius:12px;overflow:hidden}}
th,td{{text-align:left;padding:10px 14px;border-bottom:1px solid #141d33;font-size:13px}}
th{{color:#9AA6C6;font-weight:600;font-size:11px;letter-spacing:.05em;text-transform:uppercase}}
.mono{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#9AA6C6}}
.pill{{border:1px solid;border-radius:99px;padding:2px 9px;font-size:11px;font-family:ui-monospace,monospace}}
a{{color:#2FE3D2;text-decoration:none}} .links{{margin-top:18px;font-size:13px;color:#9AA6C6}}
</style></head><body><div class="wrap">
<h1>Content Engine</h1><div class="sub">job list · statuses · spend</div>
<div class="cards">
  <div class="card"><b>{len(jobs)}</b><span>jobs</span></div>
  <div class="card"><b>{sum(1 for j in jobs if j.get('status') in gate)}</b><span>awaiting approval</span></div>
  <div class="card"><b>{sum(1 for j in jobs if j.get('status')=='optimized')}</b><span>completed</span></div>
  <div class="card"><b>${total_cost:.2f}</b><span>total spend</span></div>
</div>
<table><thead><tr><th>Job</th><th>Type</th><th>Status</th><th>Approved</th><th>Cost</th></tr></thead>
<tbody>{body}</tbody></table>
<div class="links"><a href="/health">/health</a> &nbsp;·&nbsp; <a href="/skills">/skills</a> &nbsp;·&nbsp; <a href="/jobs">/jobs (json)</a></div>
</div></body></html>"""


# ---------------------------------------------------------------------------
# FastAPI wiring (optional — only if fastapi is installed)
# ---------------------------------------------------------------------------
def build_app():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel

    app = FastAPI(title="Content Engine", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return api_dashboard_html()

    class TasteBody(BaseModel):
        input: dict
        brand: Optional[dict] = None
        model: Optional[str] = None

    class JobBody(BaseModel):
        type: str
        brand: dict = {}
        payload: dict = {}
        job_id: Optional[str] = None

    @app.get("/health")
    def health():
        return api_health()

    @app.get("/skills")
    def skills():
        return api_list_skills()

    @app.get("/jobs")
    def list_jobs(status: Optional[str] = None):
        return api_list_jobs(status)

    @app.get("/jobs/measurable")
    def measurable():
        return api_list_measurable()

    @app.post("/skills/{skill}/taste")
    def taste(skill: str, body: TasteBody):
        return api_taste_skill(skill, body.input, body.brand, body.model)

    @app.post("/jobs")
    def create(body: JobBody):
        return api_create_job(body.type, body.brand, body.payload, body.job_id)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        return api_get_job(job_id)

    @app.post("/jobs/{job_id}/approve")
    def approve(job_id: str):
        return api_approve(job_id)

    @app.post("/jobs/{job_id}/ready_to_measure")
    def ready(job_id: str):
        return api_ready_to_measure(job_id)

    @app.post("/tick")
    def tick():
        return api_tick()

    return app


# Module-level `app` for `uvicorn content_engine_api:app` (guarded so the module
# still imports where fastapi isn't installed).
try:
    app = build_app()
except Exception:  # fastapi not installed
    app = None


if __name__ == "__main__":
    # Offline self-check: exercise the core API functions end-to-end with the
    # LLM layer stubbed. No HTTP server, no fastapi needed, no API calls.
    from content_engine_prep import prepare_input

    def stub_llm(job, skill, store):
        canned = {
            "site_intelligence": {"health_score": 90, "top_issues": [], "quick_wins": [],
                                  "content_opportunities": ["x"], "summary": "s"},
            "competitor_intel": {"competitors": [], "market_gap": {"opportunity": "g",
                                 "why_open": "w"}, "differentiation_angles": []},
            "content_strategist": {"week_of": "2026-07-20", "notes": "", "calendar": [{
                "date": "2026-07-21", "type": "blog", "working_title": "T",
                "primary_keyword": "k", "target_segment": "all",
                "business_goal": "awareness", "priority": "high", "rationale": "r"}]},
            "content_producer": {"title": "T", "body": "b", "meta_title": "m",
                                 "meta_description": "d", "cta_text": "c", "hashtags": []},
            "seo_optimizer": {"seo_ready": True, "checks": {}, "fixes": []},
            "qa_compliance": {"verdict": "pass", "brand_voice_match": True, "issues": [],
                              "claims_check": {}, "compliance": {}},
            "analytics_funnel": {"headline": "", "what_worked": [], "what_dropped": [],
                                 "biggest_leak": {}, "recommended_focus_next": ""},
            "optimizer": {"insights": [], "double_down": [{"what": "how-to"}],
                          "reduce_or_cut": [], "next_cycle": {"content_mix": "60% how-to"}},
        }.get(skill, {"ok": True})
        return canned, 0.002
    orch._LLM_HOOK = stub_llm

    # health
    h = api_health()
    assert "healthy" in h and "anthropic" in h

    # skills list
    sk = api_list_skills()
    assert "content_strategist" in sk["skills"]

    # list jobs (empty at first)
    assert api_list_jobs()["jobs"] == []

    # ads optimizer is a tasteable agent
    assert "ads_optimizer" in api_list_skills()["skills"]

    # dashboard renders HTML
    dash = api_dashboard_html()
    assert dash.startswith("<!doctype html>") and "Content Engine" in dash

    # create -> tick to gate -> approve -> measure gate -> finish
    r = api_create_job("content_piece", {"brand_name": "Acme"},
                       {"config": {"produce_index": 0}, "audit": {}, "competitors": []},
                       job_id="api_job")
    assert r["status"] == "created"
    for _ in range(20):
        t = api_tick()
        if not t["advanced"]:
            break
    assert api_get_job("api_job")["status"] == "AWAITING_APPROVAL"
    api_approve("api_job")
    for _ in range(5):
        if not api_tick()["advanced"]:
            break
    assert api_get_job("api_job")["status"] == "published"
    # the measurement cron finds it via the list endpoint
    assert any(j["job_id"] == "api_job" for j in api_list_jobs("published")["jobs"])
    api_ready_to_measure("api_job")
    for _ in range(5):
        if not api_tick()["advanced"]:
            break
    assert api_get_job("api_job")["status"] == "optimized"

    # learning closed the loop: the Optimizer's content_mix is now in the playbook
    from content_engine_learning import get_playbook
    assert get_playbook("Acme")["content_mix"] == "60% how-to", "loop did not learn"

    orch._LLM_HOOK = orch.run_llm_skill
    print("OK — REST API core verified: health, skills, create/tick/approve/"
          "measure/finish, and the learning loop persisted the playbook. "
          "(LLM stubbed; no server, no API calls.)")
