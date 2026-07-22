"""
main.py — Content Engine runner (SECTION 15 in motion)
============================================================================
Long-running poll loop: claim a runnable job, advance it to its next block
(human gate / terminal), repeat. One process = one worker; run several against
the same Postgres store for horizontal scale (claim_next uses SKIP LOCKED).

Env:
  STORE           memory | pg           (default: memory)
  DATABASE_URL    postgres DSN          (required when STORE=pg)
  POLL_IDLE_SECS  sleep when no work    (default: 2.0)
  POLL_BUSY_SECS  sleep between jobs    (default: 0.1)
  RUN_ONCE        1 -> drain the queue once and exit (for cron / CI)
  USE_FIXTURES    1 -> no API calls (dev); RECORD_FIXTURES=1 to capture
  PER_JOB_BUDGET_USD / PER_DAY_BUDGET_USD   budget caps

Run:
  python main.py                 # continuous worker (Ctrl-C to stop cleanly)
  RUN_ONCE=1 python main.py      # drain once and exit
  STORE=pg DATABASE_URL=... python main.py

Graceful shutdown: SIGINT/SIGTERM finish the current job's step (advance is
atomic per step and commits via save), then exit. A job mid-pipeline simply
resumes on the next tick — no work is lost because status is the commit point.
============================================================================
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

import content_engine_orchestrator as orch

log = logging.getLogger("content_engine")

_stop = False


def _handle_signal(signum, _frame):
    global _stop
    log.info("signal %s received — finishing current step, then stopping", signum)
    _stop = True


def make_store():
    kind = os.getenv("STORE", "memory").lower()
    if kind == "pg":
        from content_engine_store_pg import PgJobStore, init_db
        dsn = os.environ["DATABASE_URL"]  # required
        store = PgJobStore(dsn)
        init_db(store)
        log.info("using Postgres store")
        return store
    log.info("using in-memory store (jobs are not durable)")
    return orch.InMemoryJobStore()


def run(store) -> None:
    idle = float(os.getenv("POLL_IDLE_SECS", "2.0"))
    busy = float(os.getenv("POLL_BUSY_SECS", "0.1"))
    run_once = os.getenv("RUN_ONCE") == "1"

    loops = 0
    while not _stop:
        loops += 1
        if loops % 15 == 1:   # pick up credentials added from the dashboard live
            try:
                import content_engine_connectors as _c
                _c.wire_all()
            except Exception:
                pass
        try:
            orch.auto_approve_stale(store)   # autonomy: release stale gates if ON
            status = orch.tick(store)        # claim + advance one job, or None
        except Exception:                    # never let one bad job kill the worker
            log.exception("tick failed; continuing")
            time.sleep(busy)
            continue

        if status is None:
            if run_once:
                log.info("queue drained — exiting (RUN_ONCE)")
                return
            time.sleep(idle)
        else:
            log.info("advanced a job -> %s", status)
            time.sleep(busy)

    log.info("stopped cleanly")


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    store = make_store()
    # Let connectors read credentials the founder saved from the dashboard's
    # Connect form (settings store), then install hooks. run() re-wires each
    # loop so keys added later take effect within seconds — no restart needed.
    try:
        import content_engine_connectors as connectors
        connectors.set_settings_provider(store.get_setting)
        connectors.wire_all()
    except Exception:
        log.exception("connector wiring failed; continuing with offline defaults")
    log.info("worker starting (STORE=%s, USE_FIXTURES=%s, RUN_ONCE=%s)",
             os.getenv("STORE", "memory"),
             os.getenv("USE_FIXTURES", "0"),
             os.getenv("RUN_ONCE", "0"))
    run(store)
    if hasattr(store, "close"):
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
