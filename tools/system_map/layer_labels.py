# -*- coding: utf-8 -*-
"""Name every community from the FILE its members actually come from.

The first attempt keyed off the node-id prefix, which collapsed 25 distinct
theme communities into "Website Theme 2..25" — numbered placeholders wearing a
better word. source_file is the honest signal: it says single.php, main.js,
functions.php, and those are names a person can navigate by."""
import json
import re
from collections import Counter
from pathlib import Path

ENGINE = {
    "bi": "Business Intelligence", "bi_boards": "BI Boards", "api": "REST API",
    "outreach": "Leads & Outreach", "outreach_boards": "Outreach Boards",
    "seo_ops": "SEO Operations", "seo": "SEO Engine", "seo_boards": "SEO Boards",
    "seo_fixer": "SEO Auto-Fixer", "connectors": "External Connectors",
    "ads": "Ads & Media Buying", "media_boards": "Media Buying Boards",
    "sga": "Social, Growth & Ads", "sga_boards": "SGA Boards",
    "risk": "Risk Register", "risk_boards": "Risk Boards",
    "factory": "Content Factory", "factory_boards": "Content Factory Boards",
    "cockpit": "AI Cockpit", "cockpit_boards": "Cockpit Boards",
    "aeo": "AI Answer Engines", "geo": "Local & Geo SEO", "charts": "Chart Kit",
    "dashboard": "Dashboard Shell", "system": "System & Wiring",
    "system_boards": "System Boards", "providers": "Model Providers",
    "orchestrator": "Orchestrator", "scheduler": "Scheduler & Cadence",
    "prep": "Input Shaping", "schemas": "Output Schemas", "prompts": "Skill Prompts",
    "collect": "Outcome Collection", "learning": "Playbook & Learning",
    "store_pg": "Postgres Store", "crawler": "Site Crawler",
    "competitors": "Competitor Intel", "code_skills": "Pure-Code Skills",
    "reply_agent": "Reply Agent", "workorders": "Work Orders",
    "evals": "Evals & Needles", "judge": "Quality Judge", "safety": "Input Safety",
    "health": "Health Probes", "brand": "Brand & CI", "offpage": "Off-Page SEO",
    "crosschannel": "Cross-Channel Interlock", "site_taxonomy": "Site Taxonomy",
    "selftest": "Smoke Tests",
}
DOC = {
    "content-engine-prompt-engineering": "Engine Spec",
    "DEPLOY": "Deploy Guide", "HOSTINGER-SETUP": "Hostinger Setup",
    "SIMPLE-START": "Quickstart", "README": "Readme", "SETUP": "Theme Setup",
    "CLAUDE": "Assistant Rules", "docker-compose": "Compose Stack",
    "requirements": "Dependencies",
}

g = json.load(open("graphify-out/graph.json", encoding="utf-8"))
src = {}
for n in g["nodes"]:
    src[n["id"]] = (n.get("source_file") or "").replace("\\", "/")

a = json.loads(Path("graphify-out/.graphify_analysis.json").read_text(encoding="utf-8"))


def name_for(path: str) -> str:
    if not path:
        return "Cross-cutting"
    p = path.split("/")
    fname = p[-1]
    stem = fname.rsplit(".", 1)[0]
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if "anthropos-design" in path:
        # the theme: the file IS the meaningful unit (single.php, main.js)
        if ext == "php":
            return f"Theme: {fname}"
        if ext in ("js", "css"):
            return f"Theme asset: {fname}"
        if ext == "html":
            return f"Theme prototype: {fname}"
        return f"Theme: {fname}"
    if ext == "py":
        s = re.sub(r"^content_engine_", "", stem)
        return ENGINE.get(s, s.replace("_", " ").title())
    return DOC.get(stem, stem.replace("-", " ").replace("_", " ").title())


labels, counts = {}, Counter()
for cid, members in a["communities"].items():
    if not isinstance(members, list) or not members:
        labels[int(cid)] = "Cross-cutting"
        continue
    files = Counter(src.get(m, "") for m in members)
    top_path, n_top = files.most_common(1)[0]
    nm = name_for(top_path)
    if n_top / len(members) < 0.5:
        nm += " (mixed)"
    labels[int(cid)] = nm

final = {}
for cid, nm in sorted(labels.items()):
    counts[nm] += 1
    final[cid] = nm if counts[nm] == 1 else f"{nm} #{counts[nm]}"

Path("graphify-out/.graphify_labels.json").write_text(
    json.dumps({str(k): v for k, v in final.items()}, ensure_ascii=False),
    encoding="utf-8")
theme = sorted({v for v in final.values() if v.startswith("Theme")})
print(f"named {len(final)} communities")
print(f"theme communities ({len(theme)}):")
for t in theme[:20]:
    print("   ", t)
