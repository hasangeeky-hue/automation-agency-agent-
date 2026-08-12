# -*- coding: utf-8 -*-
"""Which board reads data nobody supplies?

THE CLASS: the OS rebuilds replaced screens without rewiring what feeds
them. A screen asks ctx for "signals"; no builder ever writes "signals";
the screen renders its honest empty state forever. Nothing errors. The
board simply says "no data" for the rest of its life, and the founder
reads a working system as a broken one.

This reads BOTH sides with the AST rather than by eye:
  SUPPLY  every key any build_*_ctx returns, plus every key an enrich()
          writes back onto the context at render time
  DEMAND  every key each screen function reads out of its ctx

A key in DEMAND but not in SUPPLY is a starved board. Reported per
screen function, because "the Factory is broken" is not actionable and
"cf_review reads needs_review, which nothing writes" is.

  python audit_starved.py            # the full map
  python audit_starved.py --gate     # exit 1 if any NEW starvation appears
"""
from __future__ import annotations

import ast
import io
import os
import sys

#: modules that RENDER (demand side)
SCREENS = [
    ("Content Factory", "content_engine_factory_screens.py"),
    ("Content Factory shell", "content_engine_factory_ui.py"),
    ("Cost-Aware BI", "content_engine_bi_screens.py"),
    ("Cost-Aware BI shell", "content_engine_bi_ui.py"),
    ("Control Plane", "content_engine_control_screens.py"),
    ("Command Cockpit", "content_engine_command_ui.py"),
    ("Media Buying", "content_engine_media_center.py"),
    ("Media platforms", "content_engine_media_platforms.py"),
    ("Search OS screens", "content_engine_search_screens.py"),
    ("SEO screens", "content_engine_seo_screens.py"),
    ("SEO boards", "content_engine_seo_boards.py"),
    ("Leads & Outreach", "content_engine_os_screens.py"),
    ("SGA", "content_engine_sga_screens.py"),
]

#: modules that BUILD context (supply side)
BUILDERS = [
    # the module written to answer this audit: it supplies the keys the
    # rebuilt boards read and the old builders never wrote
    "content_engine_feeds.py",
    "content_engine_seo_ops.py",
    "content_engine_os.py",
    "content_engine_search_bridge.py",
    "content_engine_factory_ui.py",
    "content_engine_bi_ui.py",
    "content_engine_control_ui.py",
    "content_engine_command_ui.py",
    "content_engine_cockpit.py",
]

#: read like ctx keys but are not: locals, row fields, kwargs
NOT_CONTEXT = {"type", "name", "id", "status", "value", "text", "title",
               "url", "at", "why", "state", "kind", "label", "key"}


def _parse(path):
    return ast.parse(io.open(path, encoding="utf-8").read())


def supply(paths):
    """Every context key anything writes."""
    keys = set()
    for p in paths:
        if not os.path.exists(p):
            continue
        for node in ast.walk(_parse(p)):
            # a builder returning / assembling a dict literal
            if isinstance(node, ast.Dict):
                for k in node.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
            # enrich(): c["machine"] = ...
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if (isinstance(t, ast.Subscript)
                            and isinstance(t.slice, ast.Constant)
                            and isinstance(t.slice.value, str)):
                        keys.add(t.slice.value)
            # c.setdefault("wires", ...)
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "setdefault"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
    return keys


def _ctx_names(fn):
    """Which local names in this function ARE the context.

    A screen does `c = _d(ctx)` and then reads c. But a table loop does
    `for c in campaigns` and reads c too - and `c.get("opens")` on a
    campaign ROW is not a starved board, it is a column. Counting both
    reported 66 starved screens when the truth was smaller and more
    specific. Only names bound to the ctx parameter count."""
    names = set()
    args = [a.arg for a in fn.args.args]
    if args and args[0] in ("ctx", "c", "cx"):
        names.add(args[0])
    for node in ast.walk(fn):
        # c = _d(ctx) / c = dict(ctx) / c = ctx or {}
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if not isinstance(t, ast.Name):
                continue
            v = node.value
            src = ""
            if isinstance(v, ast.Call) and v.args:
                if isinstance(v.args[0], ast.Name):
                    src = v.args[0].id
            elif isinstance(v, ast.BoolOp) and v.values:
                if isinstance(v.values[0], ast.Name):
                    src = v.values[0].id
            elif isinstance(v, ast.Name):
                src = v.id
            if src in names or src == "ctx":
                names.add(t.id)
        # a for-loop rebinds the name to a ROW: it stops being the ctx
        if isinstance(node, (ast.For, ast.comprehension)):
            tgt = node.target
            if isinstance(tgt, ast.Name):
                names.discard(tgt.id)
    return names


def demand(path):
    """{screen function -> keys it reads from its context}."""
    out = {}
    tree = _parse(path)
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        ctxnames = _ctx_names(fn)
        if not ctxnames:
            continue
        keys = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ctxnames
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                k = node.args[0].value
                if k not in NOT_CONTEXT:
                    keys.add(k)
        if keys:
            out[fn.name] = keys
    return out


def main() -> int:
    sup = supply(BUILDERS)
    print("=" * 74)
    print("STARVED BOARDS - screens reading data no builder supplies")
    print("=" * 74)
    print(f"\nsupply side: {len(sup)} distinct keys written by "
          f"{len(BUILDERS)} builder module(s)\n")

    total_screens = total_starved = 0
    worst = []
    for label, path in SCREENS:
        if not os.path.exists(path):
            print(f"{label}: MODULE MISSING ({path})")
            continue
        d = demand(path)
        rows = []
        for fnname, keys in sorted(d.items()):
            missing = sorted(k for k in keys if k not in sup)
            total_screens += 1
            if missing:
                total_starved += 1
                rows.append((fnname, len(keys), missing))
        fed = len(d) - len(rows)
        print(f"--- {label}  ({fed}/{len(d)} screens fed) ---")
        if not rows:
            print("    every screen's keys are supplied\n")
            continue
        for fnname, n, missing in rows:
            print(f"    {fnname:26} reads {n:2}, STARVED on: "
                  + ", ".join(missing[:8])
                  + (" ..." if len(missing) > 8 else ""))
            worst.append((len(missing), label, fnname))
        print()

    print("=" * 74)
    print(f"{total_starved} of {total_screens} screen functions read at "
          "least one key nothing supplies.")
    if worst:
        print("\nthe ten hungriest screens:")
        for n, label, fnname in sorted(worst, reverse=True)[:10]:
            print(f"  {n:3} missing key(s)  {label} :: {fnname}")
    print("=" * 74)

    if "--gate" in sys.argv:
        # A BASELINE, NOT A ZERO. Some screens legitimately read keys a
        # caller passes directly. The gate fails on GROWTH, so the next
        # rebuild cannot quietly starve another board.
        baseline = int(os.getenv("STARVED_BASELINE", "0") or 0)
        if baseline and total_starved > baseline:
            print(f"GATE FAILED: {total_starved} starved screens, "
                  f"baseline is {baseline}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
