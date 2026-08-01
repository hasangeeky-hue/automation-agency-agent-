# -*- coding: utf-8 -*-
"""Rebuild the SYSTEM MAP: every repo, every place it runs, every service.

    python tools/system_map/build.py       (from the repo root)

WHY THIS FILE EXISTS
The graphify post-commit hook keeps the AST half of the map fresh automatically,
but it only re-parses code. The three authored layers below are invisible to any
parser and would be wiped on the next commit, so they live here and are
re-applied in one command:

    layer_docs.py      the spec and deploy docs -> the code they justify
    layer_boundary.py  the engine <-> WordPress REST boundary (no parser can
                       cross an HTTP call, so these edges are hand-authored and
                       marked INFERRED, never EXTRACTED)
    layer_topology.py  WHERE each repo runs: laptop / VPS / WordPress hosting,
                       the three containers, and all 30 external systems

Every authored node is derived from a real file — git remotes, docker-compose,
the Dockerfile, and _DIAG — so nothing here is typed from memory. The merge step
FAILS the build if any authored edge points at a node that does not exist.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
OUT = ROOT / "graphify-out"
PY = (OUT / ".graphify_python").read_text(encoding="utf-8").strip()
SCR = Path(sys.argv[0]).resolve().parent
ENV = dict(os.environ, PYTHONPATH=str(ROOT), GRAPHIFY_FORCE="1")


def run(code, label):
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                       cwd=str(ROOT), env=ENV, timeout=900)
    tail = (r.stdout or r.stderr).strip().splitlines()
    print(f"  {label}: {tail[-1][:100] if tail else 'ok'}")
    if r.returncode:
        raise SystemExit(f"FAILED at {label}\n{r.stderr[-1500:]}")


def script(path, label):
    r = subprocess.run([PY, str(SCR / path)], capture_output=True, text=True,
                       cwd=str(ROOT), env=ENV, timeout=900)
    tail = (r.stdout or r.stderr).strip().splitlines()
    print(f"  {label}: {tail[-1][:100] if tail else 'ok'}")
    if r.returncode:
        raise SystemExit(f"FAILED at {label}\n{r.stderr[-1500:]}")


print("1. detect + AST")
run("""
import json
from graphify.detect import detect
from graphify.extract import collect_files, extract
from pathlib import Path
for label, path, out in (('engine', '.', '.graphify'), ('theme', 'anthropos-design', '.theme')):
    d = detect(Path(path))
    Path(f'graphify-out/{out}_detect.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    files = []
    for f in d['files']['code']:
        p = Path(f); files.extend(collect_files(p) if p.is_dir() else [p])
    r = extract(files, cache_root=Path('.'))
    Path(f'graphify-out/{out}_ast.json').write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
    print(f'{label}: {len(r["nodes"])} nodes')
""", "AST both repos")

print("2. authored layers")
script("layer_docs.py", "docs")
script("layer_boundary.py", "engine<->website boundary")
script("layer_topology.py", "deployment topology")

print("3. merge")
run("""
import json
from pathlib import Path
P = Path('graphify-out')
files = ['.graphify_ast.json', '.theme_ast.json', '.graphify_semantic.json',
         '.boundary.json', '.topology.json']
nodes, seen, edges, hyper = [], set(), [], []
for f in files:
    d = json.loads((P / f).read_text(encoding='utf-8'))
    for n in d['nodes']:
        if n['id'] not in seen:
            seen.add(n['id']); nodes.append(n)
    edges += d['edges']; hyper += d.get('hyperedges', [])
authored = []
for f in files[2:]:
    authored += json.loads((P / f).read_text(encoding='utf-8'))['edges']
bad = [e for e in authored if e['source'] not in seen or e['target'] not in seen]
if bad:
    raise SystemExit(f'{len(bad)} AUTHORED edges dangle: {bad[:5]}')
(P / '.graphify_extract.json').write_text(json.dumps(
    {'nodes': nodes, 'edges': edges, 'hyperedges': hyper,
     'input_tokens': 0, 'output_tokens': 0}, ensure_ascii=False), encoding='utf-8')
print(f'{len(nodes)} nodes, {len(edges)} edges, 0 authored edges dangling')
""", "merge + integrity")

print("4. build + cluster")
run("""
import json
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.export import to_json
from pathlib import Path
ex = json.loads(Path('graphify-out/.graphify_extract.json').read_text(encoding='utf-8'))
G = build_from_json(ex, root='.', directed=False)
c = cluster(G)
Path('graphify-out/.graphify_analysis.json').write_text(json.dumps({
    'communities': {str(k): v for k, v in c.items()},
    'cohesion': {str(k): v for k, v in score_all(G, c).items()},
    'gods': god_nodes(G), 'surprises': surprising_connections(G, c),
    'questions': suggest_questions(G, c, {k: str(k) for k in c})},
    ensure_ascii=False), encoding='utf-8')
to_json(G, c, 'graphify-out/graph.json')
print(f'{G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(c)} communities')
""", "build")

print("5. name communities")
script("layer_labels.py", "labels")

print("6. report")
run("""
import json
from graphify.build import build_from_json
from graphify.analyze import suggest_questions
from graphify.report import generate
from pathlib import Path
P = Path('graphify-out')
ex = json.loads((P / '.graphify_extract.json').read_text(encoding='utf-8'))
de = json.loads((P / '.graphify_detect.json').read_text(encoding='utf-8'))
th = json.loads((P / '.theme_detect.json').read_text(encoding='utf-8'))
for k in ('code', 'document'):
    de['files'][k] = de['files'].get(k, []) + th['files'].get(k, [])
de['total_files'] = de.get('total_files', 0) + th.get('total_files', 0)
de['total_words'] = de.get('total_words', 0) + th.get('total_words', 0)
an = json.loads((P / '.graphify_analysis.json').read_text(encoding='utf-8'))
lb = json.loads((P / '.graphify_labels.json').read_text(encoding='utf-8'))
G = build_from_json(ex, root='.', directed=False)
c = {int(k): v for k, v in an['communities'].items()}
co = {int(k): v for k, v in an['cohesion'].items()}
la = {int(k): v for k, v in lb.items()}
(P / 'GRAPH_REPORT.md').write_text(generate(
    G, c, co, la, an['gods'], an['surprises'], de, {'input': 0, 'output': 0},
    '.', suggested_questions=suggest_questions(G, c, la)), encoding='utf-8')
print('report written')
""", "report")

print("7. html")
r = subprocess.run(["graphify", "export", "html"], capture_output=True,
                   text=True, cwd=str(ROOT), timeout=900)
print("  ", (r.stdout or r.stderr).strip().splitlines()[-1][:90])
for f in (".graphify_detect.json", ".theme_detect.json", ".graphify_ast.json",
          ".theme_ast.json", ".graphify_semantic.json", ".boundary.json",
          ".topology.json", ".graphify_extract.json", ".graphify_analysis.json"):
    (OUT / f).unlink(missing_ok=True)
print("\nDONE — graphify-out/graph.html")
