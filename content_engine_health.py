"""
content_engine_health.py
============================================================================
PREFLIGHT — "taste that everything is wired" before launch.

Checks every external dependency and returns a structured pass/fail report:
  - Anthropic API   (models.retrieve — a free GET, no tokens billed)
  - OpenAI API      (models.list)
  - Postgres        (SELECT 1 on DATABASE_URL)
  - REST endpoints  (GET each, expect < 500) from HEALTH_REST_URLS (comma-sep)
  - Python deps     (anthropic / openai / psycopg / fastapi presence)

Each check is best-effort and never raises: a missing key/DSN yields status
"skipped" (not "fail"), so you get a clear map of what is configured vs broken.

Run:
  python content_engine_health.py            # prints a table, exit 0 if healthy
  # or from n8n / the API: GET /health -> run_health()
============================================================================
"""

from __future__ import annotations

import os
from typing import Optional

OK, FAIL, SKIP = "ok", "fail", "skipped"


def _res(status: str, detail: str = "") -> dict:
    return {"status": status, "detail": detail}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
def check_dependency(mod: str) -> dict:
    try:
        __import__(mod)
        return _res(OK, f"{mod} importable")
    except Exception as e:
        return _res(SKIP, f"{mod} not installed ({e.__class__.__name__})")


def check_anthropic(model: str = "claude-haiku-4-5") -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _res(SKIP, "ANTHROPIC_API_KEY not set")
    try:
        import anthropic
        client = anthropic.Anthropic()
        m = client.models.retrieve(model)   # free GET; proves key + reachability
        return _res(OK, f"reachable; {model} available ({getattr(m, 'id', model)})")
    except Exception as e:
        return _res(FAIL, f"{e.__class__.__name__}: {e}")


def check_openai(model: str = "gpt-5.6-luna") -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        return _res(SKIP, "OPENAI_API_KEY not set (fallback path only)")
    try:
        import openai
        client = openai.OpenAI()
        client.models.list()
        return _res(OK, "reachable; models.list ok")
    except Exception as e:
        return _res(FAIL, f"{e.__class__.__name__}: {e}")


def check_postgres(dsn: Optional[str] = None) -> dict:
    dsn = dsn or os.getenv("DATABASE_URL")
    if not dsn:
        return _res(SKIP, "DATABASE_URL not set (using in-memory store)")
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return _res(OK, "connected; SELECT 1 ok")
    except Exception as e:
        return _res(FAIL, f"{e.__class__.__name__}: {e}")


def check_rest(urls: Optional[list] = None, timeout: float = 5.0) -> list:
    if urls is None:
        raw = os.getenv("HEALTH_REST_URLS", "")
        urls = [u.strip() for u in raw.split(",") if u.strip()]
    if not urls:
        return [{"url": "(none configured)", **_res(SKIP, "set HEALTH_REST_URLS")}]
    import urllib.request
    out = []
    for url in urls:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
            status = OK if code < 500 else FAIL
            out.append({"url": url, **_res(status, f"HTTP {code}")})
        except Exception as e:
            out.append({"url": url, **_res(FAIL, f"{e.__class__.__name__}: {e}")})
    return out


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
def run_health(dsn: Optional[str] = None, rest_urls: Optional[list] = None) -> dict:
    report = {
        "dependencies": {m: check_dependency(m)
                         for m in ("anthropic", "openai", "psycopg", "fastapi", "jsonschema")},
        "anthropic": check_anthropic(),
        "openai": check_openai(),
        "postgres": check_postgres(dsn),
        "rest": check_rest(rest_urls),
    }
    # healthy = nothing is in FAIL state (skips are acceptable)
    flat = [report["anthropic"], report["openai"], report["postgres"]]
    flat += list(report["dependencies"].values())
    flat += report["rest"]
    report["healthy"] = all(x["status"] != FAIL for x in flat)
    return report


def _print(report: dict) -> None:
    def line(name, r):
        mark = {"ok": "PASS", "fail": "FAIL", "skipped": "skip"}[r["status"]]
        print(f"  [{mark}] {name:<22} {r['detail']}")
    print("Content Engine — preflight health check")
    print("-" * 60)
    line("anthropic", report["anthropic"])
    line("openai", report["openai"])
    line("postgres", report["postgres"])
    for m, r in report["dependencies"].items():
        line(f"dep:{m}", r)
    for r in report["rest"]:
        line(f"rest:{r['url'][:16]}", r)
    print("-" * 60)
    print("HEALTHY" if report["healthy"] else "UNHEALTHY (fix FAIL rows above)")


if __name__ == "__main__":
    import sys
    rep = run_health()
    _print(rep)
    # Offline (no creds) => all skipped, healthy True. Live => real pass/fail.
    sys.exit(0 if rep["healthy"] else 1)
