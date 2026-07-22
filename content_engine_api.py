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

import hashlib
import os
from typing import Optional

import content_engine_orchestrator as orch
from content_engine_providers import build_prompt, call_provider
from content_engine_health import run_health

# The engine's job store. Swap to Postgres by setting STORE=pg + DATABASE_URL.
_STORE = None

# HTTP request models. Defined at MODULE LEVEL on purpose: this file uses
# `from __future__ import annotations`, so FastAPI sees the route hints as
# strings and resolves them against module globals — a class defined inside
# build_app() would not be found (FastAPI then mis-reads the body as a query
# param -> 422). Guarded so the module still imports without pydantic.
try:
    from pydantic import BaseModel

    class TasteBody(BaseModel):
        model_config = {"protected_namespaces": ()}
        input: dict
        brand: Optional[dict] = None
        model: Optional[str] = None

    class JobBody(BaseModel):
        type: str
        brand: dict = {}
        payload: dict = {}
        job_id: Optional[str] = None
except Exception:  # pydantic absent (core-only use, no HTTP)
    BaseModel = None  # type: ignore

# `Request` must live at MODULE level for the same reason as the models above:
# `from __future__ import annotations` turns `request: Request` into a string
# hint that FastAPI resolves against module globals. Imported inside build_app()
# it would be invisible -> FastAPI treats `request` as a query field -> 422.
try:
    from fastapi import Request  # noqa: E402
except Exception:
    Request = None  # type: ignore


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
    if chosen == "code":
        # code+narrate skills (site_intelligence, analytics_funnel, segmenter)
        # do their LLM work through a narrate/label model.
        chosen = route.get("narrate") or route.get("label")
    if not chosen:
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


def api_answer_replies(limit: int = 20, dry_run: bool = False) -> dict:
    """Trigger the inbound-reply agent (Q18b): read unread replies, draft
    answers, auto-send only the safe ones (respects REPLY_AUTO_SEND; complaints
    are always held for a human). Call from an n8n cron."""
    import content_engine_reply_agent as reply_agent
    return reply_agent.answer_replies(limit=limit, dry_run=dry_run)


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Dashboard login (Phase 1). A single password (DASHBOARD_PASSWORD) gates the
# control center. No password set = open (localhost/dev behind an SSH tunnel).
# ---------------------------------------------------------------------------
def _dash_password() -> str:
    return os.getenv("DASHBOARD_PASSWORD", "")


def _dash_token() -> str:
    pw = _dash_password()
    return hashlib.sha256(("aa-dash|" + pw).encode()).hexdigest() if pw else ""


def dash_authed(cookies: dict) -> bool:
    """True if the request may see the dashboard."""
    if not _dash_password():
        return True
    return (cookies or {}).get("aa_dash") == _dash_token()


_STATUS_COLOR = {"working": "#46E08B", "live": "#46E08B",
                 "partial": "#2FE3D2", "needs key": "#F5B14C"}


def _connectors_status() -> dict:
    try:
        import content_engine_connectors as C
        return C.status()
    except Exception:
        return {}


def _eighteen(st: dict) -> list:
    """The 18 capabilities + a live status derived from the connector map."""
    def L(k):
        return bool(st.get(k))
    social = L("social_linkedin") or L("social_twitter") or L("social_facebook")
    gsc = L("google_gsc_ga4")
    return [
        ("1 · Content agents", "working"),
        ("2 · Deploy content", "live" if L("wordpress_publish") else "needs key"),
        ("3 · Create content", "working"),
        ("4 · Social channels", "live" if social else "needs key"),
        ("5 · Deploy method", "live" if L("wordpress_publish") else "needs key"),
        ("6 · Store content (Drive)", "live" if L("google_drive") else "needs key"),
        ("7 · SEO technical", "live" if gsc else "partial"),
        ("8 · Keyword strategy", "working"),
        ("9 · Agent hub (Sheets)", "live" if L("google_sheets") else "partial"),
        ("10 · Web search", "live" if L("web_search") else "needs key"),
        ("11 · Tracking (GA4)", "live" if gsc else "needs key"),
        ("12 · Categorise", "working"),
        ("13 · Web scrape", "live" if L("web_search") else "needs key"),
        ("14 · LinkedIn leads", "live" if L("linkedin_leads") else "needs key"),
        ("15 · Lead scoring", "working"),
        ("16 · Customer groups", "working"),
        ("17 · Cold emails", "working"),
        ("18 · Send + reply email", "live" if L("email_send") else "needs key"),
    ]


def _blueprint_svg(st: dict) -> str:
    """A simple 'circuit board' wiring map. Destination nodes turn green when
    their connector is live, amber when the key is still missing."""
    def col(k):
        return "#46E08B" if st.get(k) else "#F5B14C"

    def node(x, y, w, label, color, sub=""):
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="9" '
            f'fill="#0F1626" stroke="{color}" stroke-width="1.6"/>'
            f'<text x="{x + w/2}" y="{y + (20 if sub else 28)}" fill="#EAF0FF" '
            f'font-size="12" font-weight="600" text-anchor="middle">{label}</text>'
            + (f'<text x="{x + w/2}" y="{y + 35}" fill="{color}" font-size="10" '
               f'text-anchor="middle">{sub}</text>' if sub else ""))

    def wire(x1, y1, x2, y2):
        return (f'<path d="M{x1} {y1} C {(x1+x2)/2} {y1}, {(x1+x2)/2} {y2}, {x2} {y2}" '
                f'stroke="#2FE3D2" stroke-width="1.4" fill="none" opacity="0.55"/>')

    parts = ['<svg viewBox="0 0 900 470" width="100%" xmlns="http://www.w3.org/2000/svg" '
             'style="max-width:100%;height:auto">']
    # sources (left)
    parts.append(node(20, 40, 150, "Web / Search", col("web_search"), "search + scrape"))
    parts.append(node(20, 120, 150, "LinkedIn", col("linkedin_leads"), "leads"))
    parts.append(node(20, 350, 150, "n8n", "#8B7CFF", "triggers / cron"))
    # center: VPS
    parts.append('<rect x="330" y="150" width="240" height="150" rx="14" fill="#0C1120" '
                 'stroke="#2FE3D2" stroke-width="2"/>')
    parts.append('<text x="450" y="185" fill="#2FE3D2" font-size="14" font-weight="700" '
                 'text-anchor="middle">VPS — Agents + Engine</text>')
    parts.append('<text x="450" y="210" fill="#9AA6C6" font-size="11" '
                 'text-anchor="middle">orchestrator · blackboard · dashboard</text>')
    parts.append('<text x="450" y="232" fill="#9AA6C6" font-size="11" '
                 'text-anchor="middle">Postgres (source of truth)</text>')
    parts.append('<text x="450" y="270" fill="#46E08B" font-size="11" '
                 'text-anchor="middle">Claude (Opus / Haiku)</text>')
    # Google hub (right top)
    ghue = "#46E08B" if (st.get("google_sheets") or st.get("google_drive")) else "#F5B14C"
    parts.append('<rect x="700" y="30" width="180" height="120" rx="12" fill="#0F1626" '
                 f'stroke="{ghue}" stroke-width="1.8"/>')
    parts.append('<text x="790" y="55" fill="#EAF0FF" font-size="12" font-weight="700" '
                 'text-anchor="middle">Google Workspace</text>')
    parts.append(f'<text x="790" y="78" fill="{col("google_sheets")}" font-size="11" '
                 'text-anchor="middle">Sheets · dashboard</text>')
    parts.append(f'<text x="790" y="98" fill="{col("google_drive")}" font-size="11" '
                 'text-anchor="middle">Drive · content JSON</text>')
    parts.append(f'<text x="790" y="118" fill="{col("email_send")}" font-size="11" '
                 'text-anchor="middle">Gmail · sending</text>')
    # destinations (right)
    parts.append(node(700, 190, 180, "WordPress", col("wordpress_publish"), "publish"))
    social_live = st.get("social_linkedin") or st.get("social_twitter") or st.get("social_facebook")
    parts.append(node(700, 260, 180, "Social channels",
                      "#46E08B" if social_live else "#F5B14C", "LI · X · FB · IG · TT"))
    parts.append(node(700, 330, 180, "Email out + replies", col("email_send"), "Gmail / IMAP"))
    # wires
    parts.append(wire(170, 63, 330, 200))
    parts.append(wire(170, 143, 330, 220))
    parts.append(wire(170, 373, 330, 260))
    parts.append(wire(570, 200, 700, 90))     # VPS <-> Google
    parts.append(wire(570, 230, 700, 215))    # -> WordPress
    parts.append(wire(570, 250, 700, 290))    # -> Social
    parts.append(wire(570, 270, 700, 355))    # -> Email
    parts.append("</svg>")
    return "".join(parts)


def _login_html(error: str = "") -> str:
    import content_engine_dashboard as D
    return D.login_html(error)


def api_dashboard_html() -> str:
    """Gather live engine data and render the Business Control Center."""
    store = get_store()
    jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
    st = _connectors_status()
    try:
        health = run_health()
    except Exception as e:  # never let a health hiccup 500 the dashboard
        health = {"healthy": False, "anthropic": {"status": "fail", "detail": str(e)}}
    month_cap = getattr(orch, "PER_MONTH_BUDGET_USD", 200.0)
    day_cap = getattr(orch, "PER_DAY_BUDGET_USD", 50.0)
    month_spent = store.monthly_cost() if hasattr(store, "monthly_cost") else         sum(float(j.get("cost_so_far_usd", 0)) for j in jobs)
    day_spent = store.daily_cost() if hasattr(store, "daily_cost") else 0.0
    import content_engine_dashboard as D
    return D.dashboard_html(
        jobs=jobs, st=st, health=health, month_spent=month_spent, month_cap=month_cap,
        day_spent=day_spent, day_cap=day_cap, taste_skills=sorted(_TASTEABLE),
        has_password=bool(_dash_password()))


# ---------------------------------------------------------------------------
# FastAPI wiring (optional — only if fastapi is installed)
# ---------------------------------------------------------------------------
def build_app():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, RedirectResponse

    app = FastAPI(title="Content Engine", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        if not dash_authed(request.cookies):
            return HTMLResponse(_login_html())
        return HTMLResponse(api_dashboard_html())

    @app.post("/login")
    async def login(request: Request):
        # Parse the urlencoded form by hand so we don't need python-multipart.
        from urllib.parse import parse_qs
        raw = (await request.body()).decode("utf-8", "ignore")
        password = parse_qs(raw).get("password", [""])[0]
        if _dash_password() and password == _dash_password():
            resp = RedirectResponse(url="/", status_code=303)
            resp.set_cookie("aa_dash", _dash_token(), httponly=True,
                            samesite="lax", max_age=60 * 60 * 24 * 14)
            return resp
        return HTMLResponse(_login_html("Wrong password"), status_code=401)

    @app.get("/logout")
    def logout():
        resp = RedirectResponse(url="/", status_code=303)
        resp.delete_cookie("aa_dash")
        return resp

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

    @app.post("/replies/answer")
    def answer_replies(limit: int = 20, dry_run: bool = False):
        return api_answer_replies(limit=limit, dry_run=dry_run)

    return app


# Module-level `app` for `uvicorn content_engine_api:app` (guarded so the module
# still imports where fastapi isn't installed).
try:
    app = build_app()
except ImportError:  # fastapi/starlette not installed (core-only offline use)
    app = None
    # Any OTHER build error is intentionally NOT swallowed here: letting it
    # propagate makes uvicorn fail loudly with the real traceback instead of
    # silently serving app=None (which 500s every request).


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
