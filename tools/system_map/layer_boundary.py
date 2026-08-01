# -*- coding: utf-8 -*-
"""The engine <-> website boundary, authored deliberately.

AST cannot find these. The engine talks to WordPress over HTTP
(POST /wp-json/wp/v2/posts) — there is no import, no call, no shared symbol
between the Python and the PHP. Left alone, a combined graph would be two
islands sitting in one file.

So every edge here is hand-authored and marked INFERRED with the reason stated,
never EXTRACTED. An edge that says EXTRACTED should mean a parser found it.
"""
import json
import os
from pathlib import Path

ROOT = Path(".").resolve()
CONTRACT = str(ROOT / "content-engine-prompt-engineering.md").replace("/", os.sep)
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


# ---- the boundary itself, as a first-class concept ----------------------
http = node("engine_website_http_boundary",
            "Engine to website: the REST boundary", "concept", CONTRACT, None,
            "The engine publishes by POSTing to /wp-json/wp/v2/posts. There is "
            "no code-level link between the Python engine and the PHP theme, so "
            "no parser can see this edge — it is a runtime contract. Everything "
            "below is INFERRED for that reason, not because the coupling is "
            "uncertain.")

# what the engine sends
edge(http, "content_engine_connectors_wordpress_publish", "references",
     "INFERRED", 0.95, CONTRACT)
edge(http, "content_engine_code_skills_publisher", "references",
     "INFERRED", 0.95, CONTRACT)

# what renders it on the other side
for tpl, why in (("anthropos_design_single", "renders a published post"),
                 ("anthropos_design_page", "renders a published page"),
                 ("anthropos_design_index", "the archive listing")):
    edge("content_engine_connectors_wordpress_publish", tpl, "shares_data_with",
         "INFERRED", 0.85, CONTRACT)

# the markdown -> HTML contract: the engine converts, the theme styles
edge("content_engine_connectors_md_to_html", "anthropos_design_single",
     "shares_data_with", "INFERRED", 0.85, CONTRACT)
mdc = node("engine_website_markup_contract",
           "Markup contract: h2/h3, lists, bold", "concept", CONTRACT, None,
           "The engine converts markdown to HTML before publishing because "
           "WordPress stores HTML. The theme styles whatever tags arrive, so a "
           "change to the converter changes how every published page LOOKS "
           "without touching a line of CSS.")
edge(mdc, "content_engine_connectors_md_to_html", "rationale_for",
     "INFERRED", 0.95, CONTRACT)
edge(mdc, "anthropos_design_single", "shares_data_with", "INFERRED", 0.75, CONTRACT)

# the featured image path
edge("content_engine_connectors_wordpress_upload_media", "anthropos_design_single",
     "shares_data_with", "INFERRED", 0.75, CONTRACT)

# ---- the GAP found while wiring this up --------------------------------
gap = node("engine_website_ao_type_gap",
           "Gap: ao_type is never populated", "rationale", THEME_FN,
           "functions.php:76",
           "The theme registers a custom taxonomy 'ao_type' (Content Type) on "
           "posts. The engine's wp_categories() only ever returns core WordPress "
           "CATEGORY names (Blog/Guides/Services + pillar + segment) and the "
           "publisher sets only data['categories']. Nothing in the engine ever "
           "writes ao_type — so every post the engine publishes has an empty "
           "Content Type. Either the engine should set it or the theme should "
           "stop registering it.")
edge(gap, "anthropos_design_functions_anthropos_register_taxonomy",
     "references", "INFERRED", 0.95, THEME_FN)
edge(gap, "content_engine_site_taxonomy_wp_categories", "references",
     "INFERRED", 0.95, THEME_FN)
edge(gap, "content_engine_code_skills_publisher", "references",
     "AMBIGUOUS", 0.3, THEME_FN)

# ---- measurement closes back onto the website --------------------------
meas = node("engine_website_measurement_loop",
            "Measurement reads the website back", "concept", CONTRACT, None,
            "GA4 is queried for the exact page path the publisher returned, so "
            "the website is not just the output of the engine — it is the "
            "instrument the engine measures itself with.")
edge(meas, "content_engine_collect_content_analytics", "rationale_for",
     "INFERRED", 0.95, CONTRACT)
edge(meas, "anthropos_design_single", "references", "INFERRED", 0.75, CONTRACT)
edge(meas, http, "conceptually_related_to", "INFERRED", 0.85, CONTRACT)

H.append({"id": "publish_to_render_chain",
          "label": "From engine to a live page",
          "nodes": ["content_engine_code_skills_publisher",
                    "content_engine_connectors_wordpress_publish",
                    "content_engine_connectors_md_to_html",
                    "anthropos_design_single", http],
          "relation": "participate_in", "confidence": "INFERRED",
          "confidence_score": 0.85, "source_file": CONTRACT})

out = {"nodes": N, "edges": E, "hyperedges": H,
       "input_tokens": 0, "output_tokens": 0}
Path("graphify-out/.boundary.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"boundary: {len(N)} nodes, {len(E)} edges, {len(H)} hyperedges")
