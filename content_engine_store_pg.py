"""
content_engine_store_pg.py
============================================================================
Postgres-backed JobStore — a drop-in replacement for InMemoryJobStore with the
same interface the orchestrator uses (get / save / claim_next / add_daily_cost
/ daily_cost, plus put for seeding).

The full job record lives in a JSONB `data` column; status/type/approved/cost
are mirrored into typed columns for indexing and the claim query. The blackboard
(SECTION 2) is this table.

claim_next() uses `FOR UPDATE SKIP LOCKED` so many orchestrator workers can poll
the same table concurrently without grabbing the same job — the standard
Postgres work-queue pattern.

Requires psycopg (v3): `pip install "psycopg[binary]"`. Imported lazily so this
module loads even where psycopg isn't installed; it only errors when you
actually construct PgJobStore.

Usage:
    from content_engine_store_pg import PgJobStore, init_db
    store = PgJobStore(os.environ["DATABASE_URL"])
    init_db(store)                    # once; creates tables if absent
    store.put(new_job(...))           # enqueue
    # orchestrator.tick(store) ...
============================================================================
"""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

# Runnable statuses are computed in Python (is_runnable), but we prefilter in
# SQL to keep the claim query cheap: not terminal, and not a blocked gate.
_TERMINAL = ("optimized", "revision_needed", "halted_budget", "failed")
_GATE_STATUS = "AWAITING_APPROVAL"

DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL,
    approved        BOOLEAN NOT NULL DEFAULT FALSE,
    cost_so_far_usd NUMERIC NOT NULL DEFAULT 0,
    data            JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_claimable_idx
    ON jobs (status) WHERE status NOT IN
    ('optimized','revision_needed','halted_budget','failed');

CREATE TABLE IF NOT EXISTS daily_cost (
    day  DATE PRIMARY KEY,
    cost NUMERIC NOT NULL DEFAULT 0
);
"""

# Claim: oldest runnable job, skipping rows other workers hold.
_CLAIM_SQL = f"""
SELECT data FROM jobs
WHERE status <> ALL(%s)
  AND NOT (status = %s AND approved = FALSE)
ORDER BY updated_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1
"""

_UPSERT_SQL = """
INSERT INTO jobs (job_id, type, status, approved, cost_so_far_usd, data, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, now())
ON CONFLICT (job_id) DO UPDATE SET
    type = EXCLUDED.type,
    status = EXCLUDED.status,
    approved = EXCLUDED.approved,
    cost_so_far_usd = EXCLUDED.cost_so_far_usd,
    data = EXCLUDED.data,
    updated_at = now()
"""

_DAILY_UPSERT_SQL = """
INSERT INTO daily_cost (day, cost) VALUES (%s, %s)
ON CONFLICT (day) DO UPDATE SET cost = daily_cost.cost + EXCLUDED.cost
"""


def _connect(dsn: str):
    import psycopg  # lazy import
    return psycopg.connect(dsn, autocommit=False)


class PgJobStore:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn = _connect(dsn)

    # -- write ---------------------------------------------------------------
    def _upsert(self, cur, job: dict) -> None:
        cur.execute(_UPSERT_SQL, (
            job["job_id"], job["type"], job["status"],
            bool(job.get("approved", False)),
            job.get("cost_so_far_usd", 0.0),
            json.dumps(job),
        ))

    def put(self, job: dict) -> None:
        self.save(job)

    def save(self, job: dict) -> None:
        with self._conn.cursor() as cur:
            self._upsert(cur, job)
        self._conn.commit()

    # -- read ----------------------------------------------------------------
    def get(self, job_id: str) -> dict:
        with self._conn.cursor() as cur:
            cur.execute("SELECT data FROM jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
        if row is None:
            raise KeyError(job_id)
        return row[0]

    def claim_next(self) -> Optional[dict]:
        """Claim + return the oldest runnable job. The row lock is released when
        the caller next calls save() (which commits). If the worker crashes
        mid-step the transaction rolls back and the job is re-claimable."""
        cur = self._conn.cursor()
        cur.execute(_CLAIM_SQL, (list(_TERMINAL), _GATE_STATUS))
        row = cur.fetchone()
        if row is None:
            self._conn.rollback()   # release the (empty) transaction
            return None
        return row[0]

    def list_jobs(self, status: Optional[str] = None) -> list:
        with self._conn.cursor() as cur:
            if status is None:
                cur.execute("SELECT data FROM jobs ORDER BY updated_at DESC LIMIT 500")
            else:
                cur.execute("SELECT data FROM jobs WHERE status = %s "
                            "ORDER BY updated_at DESC LIMIT 500", (status,))
            rows = cur.fetchall()
        return [r[0] for r in rows]

    # -- budget --------------------------------------------------------------
    def add_daily_cost(self, amount: float) -> None:
        with self._conn.cursor() as cur:
            cur.execute(_DAILY_UPSERT_SQL, (date.today(), amount))
        self._conn.commit()

    def daily_cost(self) -> float:
        with self._conn.cursor() as cur:
            cur.execute("SELECT cost FROM daily_cost WHERE day = %s", (date.today(),))
            row = cur.fetchone()
        return float(row[0]) if row else 0.0

    def monthly_cost(self) -> float:
        """Sum of daily costs in the current calendar month — powers the hard
        PER_MONTH_BUDGET_USD ($200) cap on the live Postgres deployment."""
        first = date.today().replace(day=1)
        with self._conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(cost), 0) FROM daily_cost WHERE day >= %s",
                        (first,))
            row = cur.fetchone()
        return float(row[0]) if row else 0.0

    def close(self) -> None:
        self._conn.close()


def init_db(store: PgJobStore) -> None:
    with store._conn.cursor() as cur:
        cur.execute(DDL)
    store._conn.commit()


if __name__ == "__main__":
    # No live DB in this environment — verify the module imports, the SQL
    # constants are well-formed strings, and the interface matches JobStore.
    from content_engine_orchestrator import JobStore
    for m in ("get", "save", "claim_next", "add_daily_cost", "daily_cost"):
        assert hasattr(PgJobStore, m), f"PgJobStore missing {m}"
    assert "FOR UPDATE SKIP LOCKED" in _CLAIM_SQL
    assert "ON CONFLICT (job_id)" in _UPSERT_SQL
    assert "CREATE TABLE IF NOT EXISTS jobs" in DDL
    print("OK — PgJobStore interface + SQL verified (no live DB connection made).")
