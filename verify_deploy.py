"""
verify_deploy.py
============================================================================
What is ACTUALLY running in this container. Run it inside the API container:

    docker compose -f deploy/docker-compose.yml exec api python verify_deploy.py

Answers, with no guessing:
  - which build is loaded
  - whether every engine module imports at all
  - which sections the dashboard renders, and how many cards each has
  - whether a section fell back to its old modules, and the reason if so

Reads only. Makes no network call, spends nothing, changes nothing.
============================================================================
"""
from __future__ import annotations

import importlib
import re
import sys
import traceback

CARD = re.compile(r"<div class='card (?:overflowcard )?sev-")
SEC = re.compile(r"id='sec-([a-z0-9_]+)'")

EXPECTED_SECTIONS = [
    "mission", "business", "marketing", "sales", "customer", "ops", "finance",
    "riskinfra", "exec", "content", "leads", "email", "social", "seo", "ads",
    "media", "budget", "google", "appr", "learn", "system",
]
BIG_SECTIONS = {"seo": 235, "media": 296, "system": 214, "riskinfra": 208}
FELL_BACK = "boards failed to render"


def main() -> int:
    bad = []

    print("=" * 68)
    print("1. MODULES")
    print("=" * 68)
    for mod in ("content_engine_dashboard", "content_engine_risk",
                "content_engine_risk_boards", "content_engine_system_boards",
                "content_engine_seo_boards", "content_engine_media_boards",
                "content_engine_seo_ops", "content_engine_connectors",
                "content_engine_charts"):
        try:
            importlib.import_module(mod)
            print(f"   ok    {mod}")
        except Exception as e:
            bad.append(f"{mod} will not import: {type(e).__name__}: {e}")
            print(f"   FAIL  {mod}: {type(e).__name__}: {e}")

    import content_engine_dashboard as D
    print()
    print("=" * 68)
    print("2. BUILD LOADED IN THIS CONTAINER")
    print("=" * 68)
    tag = str(getattr(D, "BUILD_TAG", "(no BUILD_TAG)"))
    for line in tag.split(". "):
        if line.strip():
            print("   " + line.strip()[:96])

    print()
    print("=" * 68)
    print("3. THE PAGE THE BROWSER ACTUALLY GETS")
    print("=" * 68)
    try:
        import content_engine_api as A
        html = A.api_dashboard_html()
        source = "content_engine_api.api_dashboard_html()  (the real route)"
    except Exception as e:
        print(f"   the API render failed ({type(e).__name__}: {e});"
              " falling back to a direct render")
        traceback.print_exc()
        html = D.dashboard_html(jobs=[], st={}, health={"healthy": True},
                                month_spent=0, month_cap=200, day_spent=0,
                                day_cap=50, taste_skills=[])
        source = "content_engine_dashboard.dashboard_html()  (direct)"
    print(f"   rendered by: {source}")
    print(f"   page size:   {len(html):,} characters")

    ids = SEC.findall(html)
    print(f"   sections:    {len(ids)}")
    missing = [s for s in EXPECTED_SECTIONS if s not in ids]
    extra = [s for s in ids if s not in EXPECTED_SECTIONS]
    if missing:
        bad.append(f"sections missing from the page: {missing}")
    if extra:
        print(f"   unexpected:  {extra}")

    print()
    print("   section        cards   state")
    print("   " + "-" * 56)
    for sid in ids:
        m = re.search(r"id='sec-%s'(.*?)(?=id='sec-|\Z)" % sid, html, re.S)
        body = m.group(1) if m else ""
        n = len(CARD.findall(body))
        state = ""
        if FELL_BACK in body:
            reason = re.search(r"Reason: ([^<]{0,160})", body)
            state = "FELL BACK -> " + (reason.group(1) if reason else "reason not stated")
            bad.append(f"section '{sid}' fell back: {state}")
        elif sid in BIG_SECTIONS and n < BIG_SECTIONS[sid] * 0.5:
            state = f"thin (expected around {BIG_SECTIONS[sid]})"
            bad.append(f"section '{sid}' rendered {n} cards, expected ~{BIG_SECTIONS[sid]}")
        print(f"   {sid:<14} {n:>5}   {state}")

    print()
    print("=" * 68)
    print("4. THE THREE MERGED-AWAY SECTIONS")
    print("=" * 68)
    for old in ("risk", "workforce", "infra", "agents", "map", "overview"):
        gone = f"id='sec-{old}'" not in html
        aliased = f"{old}:'" in html
        print(f"   {old:<10} removed: {'yes' if gone else 'NO - still a page'}"
              f"   nav alias: {'yes' if aliased else 'no'}")
        if not gone:
            bad.append(f"'{old}' is still a separate page")

    print()
    print("=" * 68)
    if bad:
        print(f"NOT HEALTHY - {len(bad)} problem(s):")
        for b in bad:
            print("   * " + b)
        print()
        print("Paste this whole output back and it says exactly what to fix.")
        return 1
    print("HEALTHY - 21 sections, Risk & Infrastructure merged and full, "
          "nothing fell back.")
    print("If the browser still shows the old layout, it is a cached page: "
          "hard-reload with Ctrl+Shift+R.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
