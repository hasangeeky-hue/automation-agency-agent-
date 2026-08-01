# -*- coding: utf-8 -*-
"""Is everything actually connected? One command, before trusting the map.

    python tools/system_map/check.py

Checks what can be checked FROM THIS LAPTOP. It deliberately does not guess at
VPS state — that needs audit_live.py in the container, and it says so rather
than reporting a green it cannot see.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
OUT = ROOT / "graphify-out"
FAILS, WARNS = [], []


def chk(ok, label, detail="", warn_only=False):
    mark = "  OK   " if ok else ("  WARN " if warn_only else "  FAIL ")
    print(mark + label + (f" — {detail}" if detail else ""))
    if not ok:
        (WARNS if warn_only else FAILS).append(label)


def git(args, cwd="."):
    try:
        r = subprocess.run(["git", "-C", cwd] + args, capture_output=True,
                           text=True, timeout=60)
        return r.stdout.strip()
    except Exception:
        return ""


print("=" * 62)
print("1. THE GRAPH")
print("=" * 62)
gp = OUT / "graph.json"
chk(gp.exists(), "graph.json exists")
if not gp.exists():
    sys.exit("no graph — run: python tools/system_map/build.py")
G = json.loads(gp.read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in G["nodes"]}
LINKS = G.get("links") or G.get("edges") or []
chk(len(NODES) > 2000, f"{len(NODES):,} nodes")
chk(len(LINKS) > 5000, f"{len(LINKS):,} edges")

# both codebases present
py = sum(1 for n in NODES.values()
         if str(n.get("source_file", "")).endswith(".py"))
php = sum(1 for n in NODES.values()
          if str(n.get("source_file", "")).endswith(".php"))
chk(py > 1500, f"engine code in the graph ({py:,} python nodes)")
chk(php > 50, f"website code in the graph ({php} php nodes)")

print()
print("=" * 62)
print("2. THE AUTHORED LAYERS  (wiped by the auto-rebuild; must be re-applied)")
print("=" * 62)
LAYERS = {
    "deployment topology": ["place_laptop", "place_vps", "place_wordpress",
                            "repo_engine", "repo_theme"],
    "VPS containers": ["vps_service_db", "vps_service_api", "vps_service_worker"],
    "engine<->website boundary": ["engine_website_http_boundary",
                                  "engine_website_ao_type_gap",
                                  "engine_website_measurement_loop"],
    "spec rationale": ["content_engine_prompt_engineering_rule_human_gate",
                       "content_engine_prompt_engineering_budget_caps"],
    "debug triage": ["debug_where_to_look"],
    "the rebuild trap": ["deploy_image_bakes_source"],
}
for layer, ids in LAYERS.items():
    miss = [i for i in ids if i not in NODES]
    chk(not miss, f"{layer} ({len(ids)} nodes)", f"missing {miss}" if miss else "")

ext = [i for i in NODES if i.startswith("ext_")]
chk(len(ext) >= 30, f"external systems mapped ({len(ext)})")

# every edge must land on a real node
dang = [(l.get("source"), l.get("target")) for l in LINKS
        if l.get("source") not in NODES or l.get("target") not in NODES]
chk(not dang, "every edge lands on a real node",
    f"{len(dang)} dangling, e.g. {dang[:2]}" if dang else "")

print()
print("=" * 62)
print("3. THE TWO REPOS")
print("=" * 62)
for label, path in (("engine", "."), ("theme", "anthropos-design")):
    url = git(["remote", "get-url", "origin"], path)
    chk(bool(url), f"{label}: remote configured", url.split("/")[-1] if url else "")
    dirty = git(["status", "--porcelain"], path)
    real = [l for l in dirty.splitlines()
            if l.strip() and "graphify-out" not in l]
    chk(not real, f"{label}: working tree clean",
        f"{len(real)} uncommitted" if real else "")
    git(["fetch", "origin", "--quiet"], path)
    counts = git(["rev-list", "--left-right", "--count", "origin/main...HEAD"], path)
    if counts and "\t" in counts:
        behind, ahead = counts.split("\t")
        chk(ahead == "0", f"{label}: pushed to GitHub",
            f"{ahead} commit(s) NOT pushed" if ahead != "0" else "up to date")
        chk(behind == "0", f"{label}: has the remote's work",
            f"{behind} commit(s) behind — pull first" if behind != "0" else "",
            warn_only=True)

# the theme version gate — Git Updater deploys on this and nothing warns you
css = ROOT / "anthropos-design" / "style.css"
if css.exists():
    ver = next((l.split(":", 1)[1].strip()
                for l in css.read_text(encoding="utf-8", errors="ignore").splitlines()[:20]
                if l.lower().startswith("version:")), "")
    last = git(["log", "-1", "--format=%s"], "anthropos-design")
    chk(bool(ver), f"theme version header present", ver)
    touched = git(["show", "--name-only", "--format=", "HEAD"], "anthropos-design")
    if "functions.php" in touched or "index.php" in touched:
        chk("style.css" in touched, "last theme commit bumped the version",
            "Git Updater deploys on the version header — without a bump the "
            "push reaches GitHub and never reaches the site", warn_only=True)

print()
print("=" * 62)
print("4. THE TOOLING")
print("=" * 62)
for f in ("build.py", "view.py", "layer_docs.py", "layer_boundary.py",
          "layer_topology.py", "layer_labels.py"):
    chk((ROOT / "tools" / "system_map" / f).exists(), f"tools/system_map/{f}")
chk((OUT / "SYSTEM_MAP.html").exists(), "SYSTEM_MAP.html generated")
chk((OUT / "graph.html").exists(), "graph.html generated")
for hook in ("post-commit", "post-checkout"):
    chk((ROOT / ".git" / "hooks" / hook).exists(), f"git {hook} hook installed")
settings = ROOT / ".claude" / "settings.json"
chk(settings.exists() and "hook-guard" in settings.read_text(encoding="utf-8"),
    "assistant is forced to query the graph before reading files")

print()
print("=" * 62)
print("5. THE ENGINE  (offline self-checks)")
print("=" * 62)
mods = sorted(p.name for p in ROOT.glob("content_engine_*.py"))
extra = [f for f in ("verify_loop.py", "verify_cadence.py", "verify_deploy.py",
                     "verify_contract.py")
         if (ROOT / f).exists()]
ok = bad = 0
failed = []
for f in mods + extra:
    r = subprocess.run([sys.executable, f], capture_output=True, text=True,
                       cwd=str(ROOT), timeout=180)
    if r.returncode == 0:
        ok += 1
    else:
        bad += 1
        failed.append(f)
chk(bad == 0, f"{ok} module self-checks pass",
    f"FAILING: {failed}" if failed else "")

print()
print("=" * 62)
print("6. WHAT THIS CANNOT SEE")
print("=" * 62)
print("   VPS state — which keys are live, whether the containers hold the")
print("   latest build, and whether jobs are running. Only this can tell you:")
print("     docker compose -f deploy/docker-compose.yml exec api python audit_live.py")
print("   WordPress — whether Git Updater has actually pulled the new version.")
print("     WP admin -> Dashboard -> Updates -> Check Again")

print()
if FAILS:
    print(f"{len(FAILS)} PROBLEM(S): {FAILS}")
    sys.exit(1)
if WARNS:
    print(f"CONNECTED, with {len(WARNS)} thing(s) to note: {WARNS}")
    sys.exit(0)
print("ALL CONNECTED — graph, both repos, tooling and engine.")
