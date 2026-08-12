# -*- coding: utf-8 -*-
"""Why is the dashboard not loading? Render it here and watch it fail.

curl on / returns the auth wall, so a broken page looks identical to a
locked one from outside. This builds the page INSIDE the container, the
same call the route makes, and prints the traceback with the section
that raised it - plus how long each stage took, because a page that
takes ninety seconds is "gone" to anyone waiting on it.

  docker compose -f deploy/docker-compose.yml exec -T api python - \
      < probe_dashboard.py
"""
from __future__ import annotations

import time
import traceback


def main() -> int:
    print("=" * 70)
    print("DASHBOARD PROBE")
    print("=" * 70)

    t0 = time.time()
    try:
        import content_engine_api as A
        print("api module imported            %.2fs" % (time.time() - t0))
    except Exception:
        print("THE API MODULE ITSELF WILL NOT IMPORT:")
        traceback.print_exc()
        return 1

    # each stage separately, so a slow one is named rather than guessed
    t = time.time()
    try:
        kw = A._dashboard_kwargs()
        print("context assembled             %.2fs  (%d keys)"
              % (time.time() - t, len(kw)))
    except Exception:
        print("CONTEXT ASSEMBLY FAILED after %.2fs:" % (time.time() - t))
        traceback.print_exc()
        return 1

    # which context did each section get, and did any carry an error?
    for name in sorted(k for k in kw if k.endswith("_ctx")):
        v = kw.get(name)
        if isinstance(v, dict) and v.get("_ctx_error"):
            print(f"  !! {name}: {v['_ctx_error'][:120]}")

    t = time.time()
    try:
        html = A.api_dashboard_html()
        dt = time.time() - t
        print("page rendered                 %.2fs  (%d chars)"
              % (dt, len(html)))
        if dt > 10:
            print("  SLOW: anything past ~10s reads as 'the dashboard is "
                  "gone' to a person waiting on it.")
    except Exception:
        print("RENDER FAILED after %.2fs:" % (time.time() - t))
        traceback.print_exc()
        return 1

    # the two boards changed most recently, rendered alone
    for label, fn in (("factory", "content_engine_factory_boards"),
                      ("seo", "content_engine_seo_boards")):
        t = time.time()
        try:
            mod = __import__(fn)
            ctx = kw.get(label + "_ctx") or kw.get("seo_ctx") or {}
            if label == "factory":
                out = mod.factory_section(ctx)
            else:
                out = mod.seo_section(ctx, legacy_html="")
            print("%-8s section rendered      %.2fs  (%d chars)"
                  % (label, time.time() - t, len(out)))
        except Exception:
            print("%s SECTION FAILED after %.2fs:"
                  % (label, time.time() - t))
            traceback.print_exc()

    print("\nthe page builds. If the browser still shows nothing, the "
          "problem is between you and the container: hard-refresh "
          "(Ctrl+Shift+R), then check the api log.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
