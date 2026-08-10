# -*- coding: utf-8 -*-
"""Switch the machine on, supervised. The wiring round's first command.

Run INSIDE the api container:
  docker compose -f deploy/docker-compose.yml exec -T api \
      python activate_wiring.py

What it sets, and why these values:
  media_auto_level = observe   the media agent judges daily and writes
                               verdicts; it drafts nothing and spends
                               nothing until you raise it to PROPOSE
  seo_autofix      = safe      the approved unattended set only: schema,
                               internal links, alt text, IndexNow -
                               never copy a visitor reads
  paused           = False     the worker's cadence gate opens
  cadence_on       = True      due engines fire, cheapest first
  autonomy         = False     EVERY piece waits for a named approval;
                               nothing publishes or sends on a timer
  WP_STATUS        = publish   a piece YOU approve goes live; an
                               unapproved piece cannot reach this path

It is idempotent: run it twice and the second run changes nothing.
It NEVER touches budget caps - those are yours to set from the BI
section's 'Set budget caps' button whenever you choose.
"""
from __future__ import annotations

import json


def main() -> int:
    from content_engine_api import get_store
    store = get_store()
    if not hasattr(store, "set_setting"):
        print("REFUSED: this store cannot save settings.")
        return 1

    def g(k, d=None):
        try:
            return store.get_setting(k, d)
        except Exception as exc:                      # noqa: BLE001
            return "unreadable: " + repr(exc)[:60]

    print("=" * 70)
    print("WIRING ROUND - SWITCH-ON, SUPERVISED")
    print("=" * 70)

    before = {k: g(k) for k in ("paused", "cadence_on", "autonomy",
                                "media_auto_level", "seo_autofix",
                                "WP_STATUS")}
    print("\nBEFORE:")
    for k, v in before.items():
        print(f"  {k:18} = {v!r}")

    # ---- the switches, in the safe order ---------------------------------
    store.set_setting("media_auto_level", "observe")
    store.set_setting("seo_autofix", "safe")
    store.set_setting("autonomy", False)
    store.set_setting("WP_STATUS", "publish")
    store.set_setting("cadence_on", True)
    store.set_setting("paused", False)

    print("\nAFTER:")
    for k in before:
        print(f"  {k:18} = {g(k)!r}")

    # ---- today's plan ----------------------------------------------------
    try:
        import content_engine_scheduler as sched
        planned = sched.plan_today(store, force=False)
        print("\nTODAY'S PLAN (drafts only; each waits for your approval):")
        print("  " + json.dumps(planned, default=str)[:600])
    except Exception as exc:                          # noqa: BLE001
        print("\nplan_today failed: " + repr(exc)[:200])

    # ---- which engines are due right now ---------------------------------
    try:
        due = sched.seo_due(store)
        print("\nENGINES DUE NOW (the worker fires one per loop, "
              "cheapest first):")
        print("  " + (", ".join(due) if due else "nothing due yet"))
    except Exception as exc:                          # noqa: BLE001
        print("\nseo_due failed: " + repr(exc)[:200])

    # ---- budget, stated but untouched ------------------------------------
    try:
        caps = {"per_month": g("PER_MONTH_BUDGET_USD"),
                "per_day": g("PER_DAY_BUDGET_USD"),
                "per_job": g("PER_JOB_BUDGET_USD")}
        print("\nBUDGET CAPS (untouched by this script - set them from "
              "the BI section):")
        print("  " + json.dumps(caps, default=str))
    except Exception:                                 # noqa: BLE001
        pass

    print("\nTHE CONTRACT THAT STILL HOLDS:")
    print("  - the scheduler force-disables reply auto-send every loop")
    print("  - no publish without a named human approval")
    print("  - no media spend at OBSERVE; drafts appear only at PROPOSE")
    print("  - paid engines wait for budget headroom")
    print("\nWatch it work:  docker compose -f deploy/docker-compose.yml "
          "logs -f worker")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
