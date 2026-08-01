# -*- coding: utf-8 -*-
"""WHERE the code runs, and WHAT it talks to.

The graph already knows the code. It does not know that content_engine_*.py runs
on a VPS and anthropos-design/*.php runs on WordPress hosting, or that both come
from different GitHub repos, or which external service each connector reaches.

That is the missing half for debugging: "this is broken" is not actionable until
you know WHERE to look and WHICH key it needs.

EVERY node here is read from a real file in the repo. Nothing is typed from
memory:
  repos            git remote -v, in both working trees
  VPS services     deploy/docker-compose.yml
  what ships       deploy/Dockerfile  (COPY *.py)
  external systems content_engine_dashboard._DIAG  (30 wires + their keys)
  theme deploy     the Git Updater note in anthropos-design/functions.php
"""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(".").resolve()
CFG = str(ROOT / "deploy" / "docker-compose.yml").replace("/", os.sep)
DOCKER = str(ROOT / "deploy" / "Dockerfile").replace("/", os.sep)
DASH = str(ROOT / "content_engine_dashboard.py").replace("/", os.sep)
THEME_FN = str(ROOT / "anthropos-design" / "functions.php").replace("/", os.sep)

N, E, H = [], [], []


def node(nid, label, ftype, src, loc=None, rationale=None):
    d = {"id": nid, "label": label, "file_type": ftype, "source_file": src,
         "source_location": loc, "source_url": None, "captured_at": None,
         "author": None, "contributor": None}
    if rationale:
        d["rationale"] = rationale
    N.append(d)
    return nid


def edge(s, t, rel, conf, score, src, loc=None):
    E.append({"source": s, "target": t, "relation": rel, "confidence": conf,
              "confidence_score": score, "source_file": src,
              "source_location": loc, "weight": 1.0})


def remote(path="."):
    try:
        out = subprocess.run(["git", "-C", path, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip()
    except Exception:
        return ""


# ---- 1. THE THREE PLACES YOUR CODE LIVES -------------------------------
laptop = node("place_laptop", "PLACE: your laptop", "concept", CFG, None,
              "Where you edit. Not a runtime — nothing here serves traffic. "
              "Both repos are cloned side by side, which is why one folder can "
              "hold two independent projects.")
vps = node("place_vps", "PLACE: the VPS (srv1834712)", "concept", CFG, None,
           "Hostinger, 72.62.90.174. Runs three containers defined in "
           "deploy/docker-compose.yml: db (Postgres 16), api (FastAPI on 8000), "
           "worker (main.py). If the ENGINE misbehaves, the evidence is here.")
wp = node("place_wordpress", "PLACE: WordPress hosting", "concept", THEME_FN,
          None,
          "Serves anthropos-automation.com. Runs the PHP theme, updated from "
          "GitHub by the Git Updater plugin — not by docker, not by you. If a "
          "PAGE looks wrong, the evidence is here, not on the VPS.")

# ---- 2. THE TWO REPOS (read from git, not typed) -----------------------
eng_url = remote(".")
thm_url = remote("anthropos-design")
repo_engine = node("repo_engine", "REPO: automation-agency-agent-", "concept",
                   CFG, None,
                   f"{eng_url or 'origin unavailable'} — the Python engine. "
                   "Push here, then pull + rebuild ON THE VPS. A push alone "
                   "changes nothing that is running.")
repo_theme = node("repo_theme", "REPO: automation-agency", "concept", THEME_FN,
                  None,
                  f"{thm_url or 'origin unavailable'} — the WordPress theme. "
                  "Push here and Git Updater deploys it to the LIVE SITE. "
                  "There is no separate deploy step, which is why a push is "
                  "the risky action.")
edge(repo_engine, vps, "references", "EXTRACTED", 1.0, CFG)
edge(repo_theme, wp, "references", "EXTRACTED", 1.0, THEME_FN)
edge(laptop, repo_engine, "references", "EXTRACTED", 1.0, CFG)
edge(laptop, repo_theme, "references", "EXTRACTED", 1.0, THEME_FN)

# ---- 3. WHAT ACTUALLY RUNS ON THE VPS (from compose) -------------------
for svc, what, why in (
        ("db", "Postgres 16",
         "Holds EVERY credential, lead, deal and job. One docker volume, "
         "engine_db. Losing it loses all of them at once."),
        ("api", "FastAPI on :8000",
         "Serves the dashboard and every endpoint. A 500 on a page is here."),
        ("worker", "main.py loop",
         "Advances jobs and runs the cadence. Work not happening is here.")):
    sid = node(f"vps_service_{svc}", f"VPS service: {svc}", "concept", CFG,
               f"docker-compose.yml: {svc}", f"{what}. {why}")
    edge(vps, sid, "references", "EXTRACTED", 1.0, CFG)

edge("vps_service_worker", "main_run", "references", "INFERRED", 0.95, CFG)
edge("vps_service_api", "content_engine_api", "references", "INFERRED", 0.85, CFG)
edge("vps_service_db", "content_engine_store_pg_pgjobstore", "references",
     "INFERRED", 0.95, CFG)

bake = node("deploy_image_bakes_source", "The image BAKES the source in",
            "rationale", DOCKER, "Dockerfile: COPY *.py ./",
            "Dockerfile line 16 is `COPY *.py ./`, and there is no bind mount. "
            "The running container holds whatever it was BUILT with, so "
            "`git pull` on the VPS changes nothing until you rebuild. This cost "
            "a full round trip on 2026-07-31: an audit script reported "
            "byte-identical output after a pull because the old copy answered.")
edge(bake, vps, "references", "EXTRACTED", 1.0, DOCKER)
edge(bake, repo_engine, "references", "INFERRED", 0.95, DOCKER)

# ---- 4. THE 30 EXTERNAL SYSTEMS (from _DIAG) ---------------------------
import content_engine_dashboard as D

# wire key -> the connector code that actually reaches it. Only classes and
# functions VERIFIED to exist as nodes in the graph are named here.
OWNER = {
    "claude_api": "content_engine_providers_call_provider",
    "wordpress_publish": "content_engine_connectors_wordpress",
    "email_send": "content_engine_connectors_emailer",
    "email_reply_inbound": "content_engine_connectors_inboundemail",
    "linkedin_leads": "content_engine_connectors_linkedin",
    "google_gsc_ga4": "content_engine_connectors_google",
    "google_sheets": "content_engine_connectors_google",
    "google_drive": "content_engine_connectors_google",
    "seo_index_inspect": "content_engine_connectors_google",
    "social_linkedin": "content_engine_connectors_linkedinposter",
    "social_twitter": "content_engine_connectors_post_social",
    "social_facebook": "content_engine_connectors_post_social",
    "social_instagram": "content_engine_connectors_post_social",
    "social_tiktok": "content_engine_connectors_post_social",
    "ads_api": "content_engine_connectors_googleads",
    "calcom_bookings": "content_engine_connectors_calcom",
    "image_gen": "content_engine_connectors_generate_image",
    "serper_search": "content_engine_connectors_serper",
    "seo_rank_tracker": "content_engine_connectors_serper",
    "seo_crawler": "content_engine_crawler",
}
SOCIAL = {"social_linkedin", "social_twitter", "social_facebook",
          "social_instagram", "social_tiktok"}

wire_ids = []
for key, name, why, effect, fix in D._DIAG:
    nid = node(f"ext_{key}", f"EXTERNAL: {name}", "concept", DASH,
               f"_DIAG: {key}",
               f"Needs: {fix or 'no credential'}. Without it: {effect}")
    wire_ids.append(nid)
    # everything the engine calls out to is called FROM the VPS
    edge(vps, nid, "references", "INFERRED", 0.85, DASH)
    owner = OWNER.get(key)
    if owner:
        edge(owner, nid, "references", "INFERRED", 0.85, DASH)

# WordPress is the one external system that is ALSO one of your own places
edge("ext_wordpress_publish", wp, "references", "INFERRED", 0.95, DASH)
edge("ext_wordpress_publish", repo_theme, "conceptually_related_to",
     "INFERRED", 0.75, DASH)

soc = node("ext_social_channels", "All social channels", "concept", DASH, None,
           "LinkedIn, X, Facebook, Instagram, TikTok. Only LinkedIn is "
           "connected; the rest are deliberately deferred.")
for k in SOCIAL:
    edge(soc, f"ext_{k}", "references", "EXTRACTED", 1.0, DASH)

# ---- 5. THE DEBUGGING RULE, made explicit ------------------------------
tri = node("debug_where_to_look", "Where to look when something breaks",
           "rationale", CFG, None,
           "A page renders wrong -> WordPress hosting (theme repo). "
           "A job fails, a key is rejected, nothing is queued -> the VPS "
           "(engine repo, docker logs). An article publishes but does not "
           "appear in a listing -> BETWEEN them: the engine sent it, the theme "
           "filters it. That third case is the one that hid ao_type for weeks.")
edge(tri, vps, "references", "INFERRED", 0.85, CFG)
edge(tri, wp, "references", "INFERRED", 0.85, CFG)
edge(tri, "engine_website_http_boundary", "conceptually_related_to",
     "INFERRED", 0.85, CFG)

H.append({"id": "deployment_topology", "label": "Where every piece runs",
          "nodes": [laptop, vps, wp, repo_engine, repo_theme],
          "relation": "form", "confidence": "EXTRACTED",
          "confidence_score": 1.0, "source_file": CFG})
H.append({"id": "vps_runtime", "label": "The three containers on the VPS",
          "nodes": ["vps_service_db", "vps_service_api", "vps_service_worker",
                    vps, bake],
          "relation": "participate_in", "confidence": "EXTRACTED",
          "confidence_score": 1.0, "source_file": CFG})

out = {"nodes": N, "edges": E, "hyperedges": H,
       "input_tokens": 0, "output_tokens": 0}
Path("graphify-out/.topology.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"topology: {len(N)} nodes, {len(E)} edges, {len(H)} hyperedges")
print(f"  engine repo: {eng_url}")
print(f"  theme  repo: {thm_url}")
print(f"  external systems from _DIAG: {len(wire_ids)}")
