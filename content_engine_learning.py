"""
content_engine_learning.py
============================================================================
THE LEARNING AGENT — what makes the system smarter day by day.

The gap it closes: without this, the Optimizer (Skill 10) produced insights that
died with the job. Nothing persisted, so every new job started from zero.

Now:
  - The Optimizer's output is folded into a durable, per-client PLAYBOOK
    (winning topics, subject style, platform focus, content mix, things to avoid).
  - Every generative agent (Strategist / Producer / Outreach) reads that playbook
    via prepare_input, so each new cycle is informed by accumulated evidence.
  - History is append-only for audit ("why did the strategy change?").

This is the feedback edge 10 -> 4 in the spec. Persistence is the mechanism;
whether the next cycle is spawned by auto_loop (orchestrator) or an n8n cron,
the smartness accrues in the playbook.

Two stores: InMemoryLearningStore (dev/tests) and PgLearningStore (production,
lazy psycopg). Swap via set_store(). prepare_input calls get_playbook();
the orchestrator calls record_cycle() after the Optimizer step.
============================================================================
"""

from __future__ import annotations

from typing import Optional


def _empty_playbook() -> dict:
    return {
        "content_mix": "",
        "winning_email_subject_style": "",
        "platform_focus": [],
        "winning_topics": [],   # topics/angles that performed
        "avoid": [],            # reduce_or_cut items
    }


def _empty_record(client_id: str) -> dict:
    return {"client_id": client_id, "playbook": _empty_playbook(),
            "history": [], "cycles": 0}


def _merge_list(existing: list, incoming, cap: int = 20) -> list:
    """Append new items (dedup, most-recent-last), capped."""
    out = list(existing)
    for item in (incoming or []):
        # incoming may be strings or {"what":...}/{"finding":...} objects
        val = item.get("what") or item.get("finding") if isinstance(item, dict) else item
        if val and val not in out:
            out.append(val)
    return out[-cap:]


def _apply_optimizer(record: dict, optimizer_output: dict, at: Optional[str]) -> dict:
    """Fold one Optimizer result into the playbook + history."""
    pb = record["playbook"]
    nxt = optimizer_output.get("next_cycle", {}) or {}

    if nxt.get("content_mix"):
        pb["content_mix"] = nxt["content_mix"]
    if nxt.get("winning_email_subject_style"):
        pb["winning_email_subject_style"] = nxt["winning_email_subject_style"]
    if nxt.get("platform_focus"):
        pb["platform_focus"] = list(nxt["platform_focus"])

    pb["winning_topics"] = _merge_list(
        pb["winning_topics"],
        list(nxt.get("topic_priorities", [])) + optimizer_output.get("double_down", []))
    pb["avoid"] = _merge_list(pb["avoid"], optimizer_output.get("reduce_or_cut", []))

    record["cycles"] += 1
    record["history"].append({
        "cycle": record["cycles"],
        "insights": optimizer_output.get("insights", []),
        "at": at,
    })
    # keep history bounded
    record["history"] = record["history"][-50:]
    return record


class InMemoryLearningStore:
    def __init__(self):
        self._d: dict[str, dict] = {}

    def get(self, client_id: str) -> dict:
        return self._d.setdefault(client_id, _empty_record(client_id))

    def snapshot(self, client_id: str) -> dict:
        """The playbook the generative agents read. Includes cycle count so
        callers can tell 'no learning yet' (cycles == 0) from a real playbook."""
        rec = self.get(client_id)
        pb = dict(rec["playbook"])
        pb["cycles"] = rec["cycles"]
        return pb

    def record_cycle(self, client_id: str, optimizer_output: dict,
                     at: Optional[str] = None) -> dict:
        rec = self.get(client_id)
        self._d[client_id] = _apply_optimizer(rec, optimizer_output, at)
        return self._d[client_id]


class PgLearningStore:
    """Postgres-backed learning store. Requires psycopg (lazy import)."""
    DDL = """
    CREATE TABLE IF NOT EXISTS learnings (
        client_id  TEXT PRIMARY KEY,
        playbook   JSONB NOT NULL,
        history    JSONB NOT NULL,
        cycles     INT   NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """

    def __init__(self, dsn: str):
        import psycopg  # lazy
        self._conn = psycopg.connect(dsn, autocommit=False)
        with self._conn.cursor() as cur:
            cur.execute(self.DDL)
        self._conn.commit()

    def get(self, client_id: str) -> dict:
        import json
        with self._conn.cursor() as cur:
            cur.execute("SELECT playbook, history, cycles FROM learnings WHERE client_id=%s",
                        (client_id,))
            row = cur.fetchone()
        if row is None:
            return _empty_record(client_id)
        pb, hist, cycles = row
        return {"client_id": client_id, "playbook": pb, "history": hist, "cycles": cycles}

    def snapshot(self, client_id: str) -> dict:
        rec = self.get(client_id)
        pb = dict(rec["playbook"])
        pb["cycles"] = rec["cycles"]
        return pb

    def record_cycle(self, client_id: str, optimizer_output: dict,
                     at: Optional[str] = None) -> dict:
        import json
        rec = _apply_optimizer(self.get(client_id), optimizer_output, at)
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO learnings (client_id, playbook, history, cycles, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (client_id) DO UPDATE SET
                    playbook=EXCLUDED.playbook, history=EXCLUDED.history,
                    cycles=EXCLUDED.cycles, updated_at=now()
            """, (client_id, json.dumps(rec["playbook"]),
                  json.dumps(rec["history"]), rec["cycles"]))
        self._conn.commit()
        return rec


# --- module singleton the rest of the engine talks to ----------------------
ACTIVE = InMemoryLearningStore()


def set_store(store) -> None:
    global ACTIVE
    ACTIVE = store


def get_playbook(client_id: str) -> dict:
    return ACTIVE.snapshot(client_id or "")


def record_cycle(client_id: str, optimizer_output: dict, at: Optional[str] = None) -> dict:
    return ACTIVE.record_cycle(client_id or "", optimizer_output, at)


if __name__ == "__main__":
    s = InMemoryLearningStore()
    set_store(s)
    # cycle 1
    record_cycle("acme", {
        "insights": [{"finding": "how-to posts convert", "evidence": "3x", "impact": "high"}],
        "double_down": [{"what": "how-to guides", "reason": "convert"}],
        "reduce_or_cut": [{"what": "listicles", "reason": "flat"}],
        "next_cycle": {"content_mix": "60% how-to", "topic_priorities": ["automation"],
                       "winning_email_subject_style": "question-led",
                       "platform_focus": ["linkedin"]}})
    pb = get_playbook("acme")
    assert pb["cycles"] == 1
    assert "how-to guides" in pb["winning_topics"] and "automation" in pb["winning_topics"]
    assert "listicles" in pb["avoid"]
    assert pb["content_mix"] == "60% how-to"
    assert pb["winning_email_subject_style"] == "question-led"
    # cycle 2 accumulates, no dupes
    record_cycle("acme", {"insights": [], "double_down": [{"what": "how-to guides"}],
                          "reduce_or_cut": [], "next_cycle": {"topic_priorities": ["ai agents"]}})
    pb = get_playbook("acme")
    assert pb["cycles"] == 2
    assert pb["winning_topics"].count("how-to guides") == 1, "should dedupe"
    assert "ai agents" in pb["winning_topics"]
    # a fresh client is empty
    assert get_playbook("new")["cycles"] == 0
    print("OK — learning agent verified: playbook accumulates across cycles, "
          "dedupes, and a new client starts empty.")
