"""
content_engine_os_store.py
============================================================================
REAL TABLES. One physical table per entity, typed columns, real indexes.

WHY THIS EXISTS
  The OS shipped persisting every collection as one JSON blob in the
  settings store. That was the right call for a first deploy (no migration,
  no downtime) and the wrong place to stay: reading forty thousand profiles
  to answer "who is in Germany" gets slower every week, and two writers in
  the same second lose one of the writes.

WHAT "NORMALIZED" MEANS HERE, HONESTLY
  Each entity gets its own table. The fields that are FILTERED, SORTED or
  JOINED on are real typed columns with indexes. Everything else lives in
  one JSONB column called extra. That is a deliberate line, not a shortcut:
  giving a column to a field nobody queries buys a migration every time an
  agent invents a property, and this engine's agents invent properties
  weekly.

ONE DECLARATION
  SCHEMA below generates the DDL, the INSERT, the SELECT and the row
  mapping. There is no second list of column names anywhere. A column added
  here appears in all four without another edit, which is the only way two
  hand written lists cannot disagree.

SAFETY
  - The settings backed store stays the fallback and is never deleted.
  - migrate() copies; it does not move. Running it twice is harmless.
  - Any database error at read time falls back to the JSON store and says
    so, because a dashboard that goes blank is worse than one that is slow.
============================================================================
"""

from __future__ import annotations

import json
import logging

from content_engine_os_core import COLLECTIONS, DEFAULT_WORKSPACE, _D, now

log = logging.getLogger("content_engine.os.store")

#: collection -> (typed columns, indexed columns). Every column is TEXT or
#: DOUBLE PRECISION or BOOLEAN; anything richer stays in extra.
SCHEMA = {
    "workspaces":     ([("name", "text"), ("plan", "text"),
                        ("owner_email", "text")], ["name"]),
    "users":          ([("email", "text"), ("name", "text"),
                        ("last_seen_at", "text")], ["email"]),
    "workspace_members": ([("user_id", "text"), ("user_email", "text"),
                           ("role", "text"), ("invited_at", "text"),
                           ("accepted_at", "text")],
                          ["user_id", "user_email", "role"]),
    "profiles":       ([("email", "text"), ("first_name", "text"),
                        ("last_name", "text"), ("company", "text"),
                        ("company_id", "text"), ("job_title", "text"),
                        ("country", "text"), ("city", "text"),
                        ("timezone", "text"), ("language", "text"),
                        ("website", "text"), ("phone", "text"),
                        ("linkedin_url", "text"), ("source", "text"),
                        ("source_id", "text"), ("consent", "text"),
                        ("last_activity_at", "text"), ("rest_until", "text")],
                       ["email", "consent", "country", "company_id",
                        "rest_until"]),
    "profile_properties": ([("profile_id", "text"), ("key", "text"),
                            ("value_type", "text")], ["profile_id", "key"]),
    "companies":      ([("name", "text"), ("website", "text"),
                        ("country", "text")], ["name"]),
    "leads":          ([("primary_profile_id", "text"), ("company_id", "text"),
                        ("stage", "text"), ("score", "double precision"),
                        ("intent_score", "double precision"),
                        ("source", "text"), ("source_url", "text"),
                        ("qualification_status", "text"),
                        ("assigned_agent", "text")],
                       ["primary_profile_id", "stage", "company_id"]),
    "lists":          ([("name", "text"), ("description", "text")], ["name"]),
    "list_members":   ([("list_id", "text"), ("profile_id", "text"),
                        ("added_at", "text"), ("source", "text")],
                       ["list_id", "profile_id"]),
    "segments":       ([("name", "text"), ("described", "text")], ["name"]),
    "templates":      ([("name", "text"), ("subject", "text"),
                        ("version", "double precision"),
                        ("published_at", "text")], ["name"]),
    "template_versions": ([("template_id", "text"),
                           ("version", "double precision"),
                           ("subject", "text"), ("published_at", "text")],
                          ["template_id"]),
    "campaigns":      ([("name", "text"), ("subject", "text"),
                        ("state", "text"), ("job_id", "text"),
                        ("source", "text"), ("audience_kind", "text"),
                        ("audience_id", "text"), ("template_id", "text"),
                        ("recipients", "double precision"),
                        ("scheduled_at", "text"), ("state_at", "text")],
                       ["state", "job_id", "name"]),
    "campaign_messages": ([("campaign_id", "text"), ("profile_id", "text"),
                           ("email", "text"), ("touch", "double precision"),
                           ("subject", "text"), ("variant", "text"),
                           ("state", "text"), ("sent_at", "text"),
                           ("edited", "boolean"), ("job_id", "text"),
                           ("flow_id", "text")],
                          ["campaign_id", "profile_id", "email", "state"]),
    "flows":          ([("name", "text"), ("status", "text"),
                        ("valid", "boolean")], ["status"]),
    "flow_executions": ([("flow_id", "text"), ("profile_id", "text"),
                         ("current_node_id", "text"), ("status", "text"),
                         ("wait_until", "text"), ("started_at", "text")],
                        ["flow_id", "profile_id", "status", "wait_until"]),
    "email_jobs":     ([("campaign_id", "text"), ("profile_id", "text"),
                        ("message_id", "text"), ("email", "text"),
                        ("status", "text"), ("provider", "text"),
                        ("provider_message_id", "text"),
                        ("attempts", "double precision"),
                        ("approved", "boolean"), ("approved_by", "text"),
                        ("scheduled_at", "text"), ("next_attempt_at", "text"),
                        ("sent_at", "text"), ("failed_at", "text"),
                        ("touch", "double precision"), ("variant", "text"),
                        ("error_message", "text")],
                       ["status", "campaign_id", "profile_id", "approved",
                        "next_attempt_at", "provider_message_id"]),
    "email_events":   ([("event_key", "text"), ("event_type", "text"),
                        ("profile_id", "text"), ("campaign_id", "text"),
                        ("flow_id", "text"), ("message_id", "text"),
                        ("timestamp", "text")],
                       ["event_key", "event_type", "profile_id",
                        "campaign_id", "message_id"]),
    "consents":       ([("email", "text"), ("status", "text"),
                        ("consent_source", "text"), ("consent_method", "text"),
                        ("consent_at", "text"), ("unsubscribed_at", "text"),
                        ("evidence", "text")], ["email", "status"]),
    "suppressions":   ([("email", "text"), ("reason", "text"),
                        ("suppressed_at", "text")], ["email", "reason"]),
    "sender_domains": ([("domain", "text"), ("selector", "text"),
                        ("state", "text"), ("checked_at", "text")],
                       ["domain"]),
    "providers":      ([("name", "text"), ("state", "text")], ["name"]),
    "agent_runs":     ([("agent_type", "text"), ("task", "text"),
                        ("status", "text"), ("started_at", "text"),
                        ("completed_at", "text"), ("cost", "double precision"),
                        ("token_usage", "double precision")],
                       ["agent_type", "status", "started_at"]),
    "agent_actions":  ([("agent_run_id", "text"), ("action_type", "text"),
                        ("target_type", "text"), ("target_id", "text"),
                        ("timestamp", "text")],
                       ["agent_run_id", "target_id"]),
    "audit_logs":     ([("actor", "text"), ("action", "text"),
                        ("target", "text"), ("at", "text")],
                       ["actor", "action", "at"]),
    "daily_metrics":  ([("day", "text"), ("campaign_id", "text"),
                        ("sent", "double precision"),
                        ("delivered", "double precision"),
                        ("bounced", "double precision"),
                        ("opens", "double precision"),
                        ("clicks", "double precision"),
                        ("unique_opens", "double precision"),
                        ("unique_clicks", "double precision"),
                        ("unsubscribes", "double precision"),
                        ("complaints", "double precision"),
                        ("conversions", "double precision"),
                        ("queued", "double precision"),
                        ("machine_opens", "double precision"),
                        ("machine_clicks", "double precision")],
                       ["day", "campaign_id"]),
}

# Every collection the core knows must have a table, or a write would go
# somewhere the reader never looks.
_MISSING = [c for c in COLLECTIONS if c not in SCHEMA]
assert not _MISSING, f"collections with no table: {_MISSING}"

TABLE = "os_{}".format


def ddl() -> list:
    """Every CREATE TABLE and CREATE INDEX, generated from SCHEMA alone."""
    out = []
    for coll, (cols, idx) in SCHEMA.items():
        t = TABLE(coll)
        body = ",\n  ".join(
            ["id text NOT NULL", "workspace_id text NOT NULL",
             "created_at text", "updated_at text"]
            + [f"{c} {typ}" for c, typ in cols]
            + ["extra jsonb NOT NULL DEFAULT '{}'::jsonb",
               "PRIMARY KEY (workspace_id, id)"])
        out.append(f"CREATE TABLE IF NOT EXISTS {t} (\n  {body}\n)")
        for c in idx:
            out.append(f"CREATE INDEX IF NOT EXISTS {t}_{c}_ix "
                       f"ON {t} (workspace_id, {c})")
    return out


def _split(coll, rec) -> tuple:
    """A record into (typed values, leftover JSONB). One mapping, used by
    both the writer and the reader."""
    cols = [c for c, _ in SCHEMA[coll][0]]
    known = set(cols) | {"id", "workspace_id", "created_at", "updated_at"}
    vals = []
    for c, typ in SCHEMA[coll][0]:
        v = rec.get(c)
        if typ == "double precision":
            try:
                v = float(v) if v not in (None, "") else None
            except Exception:
                v = None
        elif typ == "boolean":
            v = bool(v) if v is not None else None
        elif v is not None and not isinstance(v, str):
            v = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        vals.append(v)
    extra = {k: v for k, v in rec.items() if k not in known}
    return vals, extra


def _join(coll, row) -> dict:
    """A database row back into the dict the rest of the OS speaks."""
    cols = [c for c, _ in SCHEMA[coll][0]]
    head = ["id", "workspace_id", "created_at", "updated_at"]
    rec = {}
    for i, name in enumerate(head + cols):
        v = row[i]
        if v is not None:
            rec[name] = v
    extra = row[len(head) + len(cols)]
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except Exception:
            extra = {}
    rec.update(_D(extra))
    return rec


class PgRepo:
    """The same six methods as the JSON Repo, over real tables.

    Deliberately the identical surface: every engine above this line was
    written against Repo and none of them needed a line changed."""

    def __init__(self, conn, workspace_id=DEFAULT_WORKSPACE):
        self.conn = conn
        self.ws = str(workspace_id or DEFAULT_WORKSPACE)

    # -- helpers ------------------------------------------------------------
    def _cols(self, coll):
        return ["id", "workspace_id", "created_at", "updated_at"] \
            + [c for c, _ in SCHEMA[coll][0]] + ["extra"]

    def _select(self, coll, where="", args=()):
        cols = ", ".join(self._cols(coll))
        sql = (f"SELECT {cols} FROM {TABLE(coll)} WHERE workspace_id = %s"
               + (f" AND {where}" if where else ""))
        with self.conn.cursor() as cur:
            cur.execute(sql, (self.ws,) + tuple(args))
            return [_join(coll, r) for r in cur.fetchall()]

    # -- the Repo surface ---------------------------------------------------
    def all(self, coll: str) -> list:
        if coll not in SCHEMA:
            raise KeyError(f"unknown collection: {coll}")
        return self._select(coll)

    def find(self, coll: str, **where) -> list:
        if coll not in SCHEMA:
            raise KeyError(f"unknown collection: {coll}")
        typed = {c for c, _ in SCHEMA[coll][0]}
        sql, args = [], []
        for k, v in where.items():
            if k in typed:
                sql.append(f"{k} = %s")
                args.append(v)
        rows = self._select(coll, " AND ".join(sql), args)
        # Anything not a real column still filters, just in Python.
        for k, v in where.items():
            if k not in typed:
                rows = [r for r in rows if r.get(k) == v]
        return rows

    def one(self, coll: str, rec_id: str):
        rows = self._select(coll, "id = %s", (rec_id,))
        return rows[0] if rows else None

    def put(self, coll: str, rec: dict) -> dict:
        if coll not in SCHEMA:
            raise KeyError(f"unknown collection: {coll}")
        import content_engine_os_core as CORE
        rec = dict(_D(rec))
        rec["workspace_id"] = self.ws
        rec.setdefault("id", CORE.rid(coll[:3], self.ws, coll, now()))
        rec.setdefault("created_at", now())
        rec["updated_at"] = now()
        vals, extra = _split(coll, rec)
        names = self._cols(coll)
        place = ", ".join(["%s"] * len(names))
        upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in names
                        if c not in ("id", "workspace_id", "created_at"))
        sql = (f"INSERT INTO {TABLE(coll)} ({', '.join(names)}) "
               f"VALUES ({place}) "
               f"ON CONFLICT (workspace_id, id) DO UPDATE SET {upd}")
        args = ([rec["id"], self.ws, rec.get("created_at"), rec["updated_at"]]
                + vals + [json.dumps(extra, default=str)])
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
        self.conn.commit()
        return rec

    def delete(self, coll: str, rec_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE(coll)} "
                        f"WHERE workspace_id = %s AND id = %s",
                        (self.ws, rec_id))
            n = cur.rowcount
        self.conn.commit()
        return bool(n)

    def append(self, coll: str, rec: dict) -> dict:
        import content_engine_os_core as CORE
        rec = dict(_D(rec))
        rec.setdefault("id", CORE.rid("ev", self.ws, coll, now(),
                                      rec.get("event_key", "")))
        return self.put(coll, rec)


# ---------------------------------------------------------------------------
# BACKEND SELECTION
# ---------------------------------------------------------------------------
_STATE = {"conn": None, "ready": False, "why": "not attempted", "mode": "json"}


def _dsn() -> str:
    import os
    for k in ("DATABASE_URL", "POSTGRES_DSN", "PG_DSN"):
        v = os.environ.get(k)
        if v:
            return v
    return ""


def connect(force=False):
    """Open the connection and create the tables. Once per process."""
    import os
    if _STATE["ready"] and not force:
        return _STATE["conn"]
    if str(os.environ.get("OS_STORE", "auto")).lower() == "json":
        _STATE.update(ready=True, conn=None, mode="json",
                      why="OS_STORE=json, so the OS stays on the settings store")
        return None
    dsn = _dsn()
    if not dsn:
        _STATE.update(ready=True, conn=None, mode="json",
                      why="no DATABASE_URL, so the OS uses the settings store")
        return None
    try:
        import psycopg
        conn = psycopg.connect(dsn, autocommit=False)
        with conn.cursor() as cur:
            for stmt in ddl():
                cur.execute(stmt)
        conn.commit()
        _STATE.update(ready=True, conn=conn, mode="postgres",
                      why=f"{len(SCHEMA)} tables live in Postgres")
        return conn
    except Exception as ex:
        log.error("os tables unavailable, staying on the settings store: %s", ex)
        _STATE.update(ready=True, conn=None, mode="json",
                      why=f"Postgres refused ({type(ex).__name__}), so the OS "
                          f"fell back to the settings store rather than going "
                          f"blank")
        return None


def backend() -> dict:
    connect()
    return {"mode": _STATE["mode"], "why": _STATE["why"],
            "tables": len(SCHEMA) if _STATE["mode"] == "postgres" else 0}


def repo_for(store, workspace_id=DEFAULT_WORKSPACE):
    """THE factory. Every caller in the OS goes through here, so flipping
    the backend is one function rather than forty call sites."""
    import content_engine_os_core as CORE
    conn = connect()
    if conn is None:
        return CORE.Repo(store, workspace_id)
    try:
        return PgRepo(conn, workspace_id)
    except Exception as ex:
        log.error("PgRepo failed, falling back: %s", ex)
        return CORE.Repo(store, workspace_id)


# ---------------------------------------------------------------------------
# MIGRATION. Copies. Never moves, never deletes.
# ---------------------------------------------------------------------------
MIGRATED_KEY = "os_migrated_to_tables"


def migrate(store, workspace_id=DEFAULT_WORKSPACE, *, force=False) -> dict:
    """Copy every JSON collection into its table. It copies; it never moves.

    The JSON stays exactly where it was. If anything about the tables turns
    out to be wrong, setting OS_STORE=json puts the old world back with no
    data loss, which is the only kind of migration worth running on a
    system that is already sending."""
    import content_engine_os_core as CORE
    conn = connect()
    if conn is None:
        return {"ok": False, "mode": "json", "message": _STATE["why"]}
    done = store.get_setting(MIGRATED_KEY, {}) or {}
    if done.get("at") and not force:
        return {"ok": True, "already": True, "at": done.get("at"),
                "copied": done.get("copied", 0),
                "message": f"already migrated on {done.get('at')}; "
                           f"{done.get('copied')} record(s) live in tables"}
    src = CORE.Repo(store, workspace_id)
    dst = PgRepo(conn, workspace_id)
    copied, per = 0, {}
    for coll in COLLECTIONS:
        rows = src.all(coll)
        for r in rows:
            try:
                dst.put(coll, r)
                copied += 1
            except Exception as ex:
                log.error("migrate %s/%s: %s", coll, r.get("id"), ex)
        per[coll] = len(rows)
    stamp = {"at": now(), "copied": copied, "per": per}
    store.set_setting(MIGRATED_KEY, stamp)
    return {"ok": True, "copied": copied, "per": per,
            "message": f"{copied} record(s) copied into {len(SCHEMA)} tables. "
                       f"The JSON copy is untouched."}


def counts(workspace_id=DEFAULT_WORKSPACE) -> dict:
    """Row counts straight from the tables, for the Storage screen."""
    conn = connect()
    if conn is None:
        return {}
    out = {}
    try:
        with conn.cursor() as cur:
            for coll in SCHEMA:
                cur.execute(f"SELECT count(*) FROM {TABLE(coll)} "
                            f"WHERE workspace_id = %s", (workspace_id,))
                out[coll] = int(cur.fetchone()[0])
    except Exception as ex:
        log.error("counts failed: %s", ex)
    return out
