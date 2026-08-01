# -*- coding: utf-8 -*-
"""A READABLE system map — the 40-odd topology nodes, not the 2,294-node hairball.

    python tools/system_map/view.py     ->  graphify-out/SYSTEM_MAP.html

graph.html is the right tool for tracing one symbol through 2,294 nodes. It is
the wrong tool for "what runs where", because that answer is buried in a cloud
of dots. This reads the SAME graph.json and lays out only the deployment layer,
so the shape of the system is legible at a glance.

Everything rendered here is read from graph.json. If a node is not in the graph
it does not appear — there is no hardcoded fallback, because a system map that
quietly invents a service is worse than no map.
"""
import html
import json
from pathlib import Path

G = json.loads(Path("graphify-out/graph.json").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in G["nodes"]}


def get(nid):
    return NODES.get(nid)


def esc(s):
    return html.escape(str(s or ""))


def why(nid):
    n = get(nid) or {}
    return n.get("rationale") or n.get("note") or ""


places = [p for p in ("place_laptop", "place_vps", "place_wordpress") if get(p)]
repos = [r for r in ("repo_engine", "repo_theme") if get(r)]
services = sorted(i for i in NODES if i.startswith("vps_service_"))
externals = sorted(i for i in NODES if i.startswith("ext_") and i != "ext_social_channels")

missing = [x for x in ("place_laptop", "place_vps", "place_wordpress",
                       "repo_engine", "repo_theme", "debug_where_to_look")
           if not get(x)]

CSS = """
:root{--bg:#080B14;--s1:#0F1626;--s2:#0B111F;--line:#1B2640;--ink:#EDF1FB;
--mut:#8E9BBE;--dim:#59668A;--teal:#2FE3D2;--violet:#8B7CFF;--good:#3FD98B;
--warn:#F5B14C;--blue:#4C8DFF}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;padding:26px}
h1{font-size:21px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--mut);font-size:13px;margin:0 0 22px}
h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);
margin:26px 0 10px;font-weight:700}
.row{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.card{background:var(--s1);border:1px solid var(--line);border-radius:13px;padding:15px 16px}
.card.place{border-color:#26456f}
.card h3{margin:0 0 3px;font-size:14.5px}
.card .tag{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
color:var(--teal);font-weight:700}
.card p{margin:7px 0 0;color:var(--mut);font-size:12.5px}
.flow{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin:14px 0 4px}
.pill{background:var(--s2);border:1px solid var(--line);border-radius:9px;
padding:7px 12px;font-size:12.5px}
.pill b{color:var(--ink)}
.arrow{color:var(--violet);font-weight:700}
.ext{display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(255px,1fr))}
.e{background:var(--s2);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.e b{font-size:12.5px}
.e code{display:block;color:var(--dim);font-size:11px;margin-top:4px;
word-break:break-all;font-family:ui-monospace,Consolas,monospace}
.triage{background:linear-gradient(180deg,#141d33,#0F1626);
border:1px solid var(--violet);border-radius:13px;padding:16px 18px;margin-top:8px}
.triage p{color:var(--ink);font-size:13px;margin:0}
.trap{border-left:3px solid var(--warn);padding-left:12px;margin:12px 0;
color:var(--mut);font-size:12.5px}
.foot{color:var(--dim);font-size:11.5px;margin-top:28px;border-top:1px solid var(--line);
padding-top:12px}
@media(max-width:620px){body{padding:16px}.row{grid-template-columns:1fr}}
"""

parts = [f"<style>{CSS}</style>",
         "<h1>Anthropos — system map</h1>",
         f"<p class='sub'>Where every piece of code lives and runs. "
         f"Generated from graphify-out/graph.json "
         f"({len(NODES):,} nodes) — nothing here is hand-typed.</p>"]

if missing:
    parts.append("<div class='triage' style='border-color:#FF6B93'><p>"
                 "<b>Incomplete.</b> These topology nodes are not in the graph, "
                 "so the map below is missing part of the picture: "
                 + esc(", ".join(missing)) +
                 ". Run <code>python tools/system_map/build.py</code>.</p></div>")

parts.append("<h2>The three places</h2><div class='row'>")
for p in places:
    n = get(p)
    parts.append(f"<div class='card place'><div class='tag'>place</div>"
                 f"<h3>{esc(n['label'].replace('PLACE: ',''))}</h3>"
                 f"<p>{esc(why(p))}</p></div>")
parts.append("</div>")

parts.append("<h2>How code gets there</h2>")
for r, place in (("repo_engine", "the VPS"), ("repo_theme", "WordPress")):
    n = get(r)
    if not n:
        continue
    parts.append(f"<div class='flow'><span class='pill'><b>laptop</b></span>"
                 f"<span class='arrow'>&rarr; git push &rarr;</span>"
                 f"<span class='pill'><b>{esc(n['label'].replace('REPO: ',''))}</b></span>"
                 f"<span class='arrow'>&rarr;</span>"
                 f"<span class='pill'><b>{esc(place)}</b></span></div>"
                 f"<p class='sub' style='margin:0 0 10px'>{esc(why(r))}</p>")

bake = why("deploy_image_bakes_source")
if bake:
    parts.append(f"<div class='trap'><b>Trap:</b> {esc(bake)}</div>")

if services:
    parts.append("<h2>Running on the VPS</h2><div class='row'>")
    for s in services:
        n = get(s)
        parts.append(f"<div class='card'><div class='tag'>container</div>"
                     f"<h3>{esc(n['label'].replace('VPS service: ',''))}</h3>"
                     f"<p>{esc(why(s))}</p></div>")
    parts.append("</div>")

tri = why("debug_where_to_look")
if tri:
    parts.append("<h2>When something breaks</h2>"
                 f"<div class='triage'><p>{esc(tri)}</p></div>")

parts.append(f"<h2>External systems ({len(externals)})</h2><div class='ext'>")
for e in externals:
    n = get(e)
    lbl = n["label"].replace("EXTERNAL: ", "")
    r = why(e)
    needs = r.split("Without it:")[0].replace("Needs:", "").strip(" .") if r else ""
    parts.append(f"<div class='e'><b>{esc(lbl)}</b><code>{esc(needs or 'no credential')}</code></div>")
parts.append("</div>")

parts.append("<p class='foot'>Rebuild: <code>python tools/system_map/build.py</code> "
             "then <code>python tools/system_map/view.py</code>. "
             "The post-commit hook refreshes the code half automatically but "
             "does not re-apply the authored layers.</p>")

out = Path("graphify-out/SYSTEM_MAP.html")
out.write_text("\n".join(parts), encoding="utf-8")
print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")
print(f"  {len(places)} places · {len(repos)} repos · {len(services)} services "
      f"· {len(externals)} external systems")
if missing:
    print(f"  WARNING: missing topology nodes: {missing}")
