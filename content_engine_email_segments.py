"""
content_engine_email_segments.py
============================================================================
SEGMENTS AND FLOWS. Two objects, one condition vocabulary.

A SEGMENT is a saved question about your people, answered live: "score >= 70
and country is Germany and they clicked in the last 30 days". It is not a
frozen list - it is re-evaluated every time it is read, so it can never go
stale without anyone noticing.

A FLOW is a sequence of steps against a segment: send, wait, and a condition
that branches on what the person did. Your existing three-touch cycle is the
default flow, expressed in exactly this vocabulary rather than hard-coded.

THE RULE THAT MATTERS
  THE FLOW RUNNER NEVER SENDS. It works out who is DUE and puts them in a
  queue. A human approves the queue. Automation that can post mail on its
  own is one bad condition away from mailing your whole list, and this
  engine has never let a send happen without a click.

ONE VOCABULARY
  FIELDS and OPS below are the only things a condition may be made of. The
  builder offers exactly these, the evaluator understands exactly these, and
  a gate imports both sides. Two hand-written vocabularies is the bug class
  that has bitten this engine five times.
============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("email_segments")

SEG_KEY = "email_segments"
FLOW_KEY = "email_flows"
QUEUE_KEY = "email_flow_queue"

# field -> (label, kind). kind decides which operators are offered.
FIELDS = {
    "score":      ("Lead score", "number"),
    "sends":      ("Emails received", "number"),
    "opens":      ("Opens", "number"),
    "clicks":     ("Clicks", "number"),
    "country":    ("Country", "text"),
    "vertical":   ("Vertical", "text"),
    "company":    ("Company", "text"),
    "title":      ("Job title", "text"),
    "email":      ("Email", "text"),
    "replied":    ("Has replied", "bool"),
    "days_since_send": ("Days since last email", "number"),
}

OPS = {
    "gte": (">=", "number"), "lte": ("<=", "number"),
    "eq": ("is", "any"), "neq": ("is not", "any"),
    "contains": ("contains", "text"), "in": ("is one of", "text"),
    "is_true": ("is true", "bool"), "is_false": ("is false", "bool"),
}

# which operators a field of each kind may use - the builder reads this, so
# it can never offer "contains" on a number
OPS_FOR = {
    "number": ("gte", "lte", "eq", "neq"),
    "text": ("eq", "neq", "contains", "in"),
    "bool": ("is_true", "is_false"),
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, list) else []


def ops_for(field: str) -> tuple:
    kind = FIELDS.get(field, ("", "text"))[1]
    return OPS_FOR.get(kind, ())


def valid_condition(c) -> str:
    """Returns '' when the condition is usable, or why it is not. A segment
    that silently drops a broken condition would quietly change who gets
    mail, which is the worst way for this to fail."""
    c = _D(c)
    f, op = c.get("field"), c.get("op")
    if f not in FIELDS:
        return f"'{f}' is not a field the engine knows"
    if op not in OPS:
        return f"'{op}' is not an operator"
    if op not in ops_for(f):
        return (f"{FIELDS[f][0]} is a {FIELDS[f][1]}, so it cannot use "
                f"'{OPS[op][0]}'")
    if op not in ("is_true", "is_false") and c.get("value") in (None, ""):
        return f"{FIELDS[f][0]} {OPS[op][0]} needs a value"
    return ""


def _match(person, c) -> bool:
    c = _D(c)
    f, op, want = c.get("field"), c.get("op"), c.get("value")
    got = _D(person).get(f)
    if f == "days_since_send":
        tl = [x for x in _L(_D(person).get("timeline"))
              if _D(x).get("kind") == "sent" and _D(x).get("at")]
        if not tl:
            return False
        try:
            last = datetime.fromisoformat(
                str(tl[-1]["at"]).replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            got = (datetime.now(timezone.utc) - last).days
        except Exception:
            return False
    if op == "is_true":
        return bool(got)
    if op == "is_false":
        return not bool(got)
    if got is None:
        return False
    if op in ("gte", "lte"):
        try:
            return (float(got) >= float(want) if op == "gte"
                    else float(got) <= float(want))
        except (TypeError, ValueError):
            return False
    g = str(got).strip().lower()
    w = str(want).strip().lower()
    if op == "eq":
        return g == w
    if op == "neq":
        return g != w
    if op == "contains":
        return w in g
    if op == "in":
        return g in {x.strip().lower() for x in w.split(",") if x.strip()}
    return False


def evaluate(people, conditions, match="all") -> list:
    """Who is in this segment, right now. Never cached."""
    conds = [c for c in _L(conditions) if not valid_condition(c)]
    if not conds:
        return list(_L(people))
    out = []
    for p in _L(people):
        hits = [_match(p, c) for c in conds]
        if (all(hits) if match != "any" else any(hits)):
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# SEGMENT STORAGE
# ---------------------------------------------------------------------------
def segments(store) -> list:
    try:
        return [s for s in _L(store.get_setting(SEG_KEY, [])) if _D(s)]
    except Exception:
        return []


def save_segment(store, name, conditions, match="all") -> dict:
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "a segment needs a name"}
    bad = [valid_condition(c) for c in _L(conditions)]
    bad = [b for b in bad if b]
    if bad:
        return {"ok": False, "error": bad[0]}
    if not _L(conditions):
        return {"ok": False, "error": "a segment with no condition is "
                                      "everyone; name a condition"}
    cur = segments(store)
    cur = [s for s in cur if s.get("name") != name]
    cur.append({"name": name, "conditions": _L(conditions),
                "match": ("any" if match == "any" else "all"),
                "created": _now()})
    store.set_setting(SEG_KEY, cur)
    return {"ok": True, "message": f"segment '{name}' saved",
            "count": len(cur)}


def delete_segment(store, name) -> dict:
    cur = [s for s in segments(store) if s.get("name") != name]
    store.set_setting(SEG_KEY, cur)
    return {"ok": True, "message": f"segment '{name}' removed",
            "count": len(cur)}


def describe(seg) -> str:
    """A segment in words, so nobody has to read JSON to know who gets mail."""
    seg = _D(seg)
    parts = []
    for c in _L(seg.get("conditions")):
        c = _D(c)
        f = FIELDS.get(c.get("field"), (c.get("field"), ""))[0]
        o = OPS.get(c.get("op"), (c.get("op"), ""))[0]
        v = "" if c.get("op") in ("is_true", "is_false") else f" {c.get('value')}"
        parts.append(f"{f} {o}{v}")
    join = " and " if seg.get("match") != "any" else " or "
    return join.join(parts) or "everyone"


# ---------------------------------------------------------------------------
# FLOWS
# ---------------------------------------------------------------------------
DEFAULT_FLOW = {
    "name": "Three-touch outreach",
    "segment": "",
    "steps": [
        {"kind": "send", "label": "First email"},
        {"kind": "wait", "days": 3},
        {"kind": "condition", "field": "opens", "op": "lte", "value": 0,
         "label": "did not open"},
        {"kind": "send", "label": "Second email"},
        {"kind": "wait", "days": 3},
        {"kind": "send", "label": "Third email"},
    ],
}


def flows(store) -> list:
    try:
        got = [f for f in _L(store.get_setting(FLOW_KEY, [])) if _D(f)]
    except Exception:
        got = []
    return got or [dict(DEFAULT_FLOW)]


def save_flow(store, flow) -> dict:
    flow = _D(flow)
    name = str(flow.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "a flow needs a name"}
    steps = _L(flow.get("steps"))
    if not steps:
        return {"ok": False, "error": "a flow with no steps does nothing"}
    for i, s in enumerate(steps, 1):
        s = _D(s)
        k = s.get("kind")
        if k not in ("send", "wait", "condition"):
            return {"ok": False,
                    "error": f"step {i}: '{k}' is not send, wait or condition"}
        if k == "wait" and not str(s.get("days") or "").strip():
            return {"ok": False, "error": f"step {i}: a wait needs days"}
        if k == "condition":
            why = valid_condition(s)
            if why:
                return {"ok": False, "error": f"step {i}: {why}"}
    cur = [f for f in flows(store) if f.get("name") != name]
    cur.append(dict(flow, name=name, saved=_now()))
    store.set_setting(FLOW_KEY, cur)
    return {"ok": True, "message": f"flow '{name}' saved"}


def run_flow(store, flow, people) -> dict:
    """Work out who is DUE at each send step and QUEUE them.

    THIS FUNCTION SENDS NOTHING. It writes a queue a human approves. That
    is deliberate and permanent: a flow that could mail on its own is one
    wrong condition away from mailing everybody."""
    flow = _D(flow)
    segs = {s.get("name"): s for s in segments(store)}
    pool = _L(people)
    sname = flow.get("segment")
    if sname and sname in segs:
        seg = segs[sname]
        pool = evaluate(pool, seg.get("conditions"), seg.get("match"))
    due, waiting, step_no = [], 0, 0
    gate = None
    for s in _L(flow.get("steps")):
        s = _D(s)
        k = s.get("kind")
        if k == "condition":
            gate = s
            continue
        if k == "wait":
            days = int(float(s.get("days") or 0))
            pool = [p for p in pool
                    if _match(p, {"field": "days_since_send", "op": "gte",
                                  "value": days})]
            waiting += 1
            continue
        step_no += 1
        eligible = pool
        if gate:
            eligible = [p for p in pool if _match(p, gate)]
            gate = None
        # a person who has already had this many touches is done with it
        eligible = [p for p in eligible
                    if int(_D(p).get("sends") or 0) < step_no]
        for p in eligible:
            due.append({"email": _D(p).get("email"),
                        "name": _D(p).get("name"),
                        "step": step_no, "label": s.get("label") or
                        f"Email {step_no}", "flow": flow.get("name")})
    seen, uniq = set(), []
    for d in due:
        k = (d["email"], d["step"])
        if d["email"] and k not in seen:
            seen.add(k)
            uniq.append(d)
    store.set_setting(QUEUE_KEY, uniq)
    return {"queued": len(uniq), "waits": waiting, "steps": step_no,
            "message": (f"{len(uniq)} person-step(s) queued for your "
                        f"approval. Nothing has been sent.")}


def flow_queue(store) -> list:
    try:
        return [q for q in _L(store.get_setting(QUEUE_KEY, [])) if _D(q)]
    except Exception:
        return []


def flow_stats(flow, people) -> list:
    """Per-step reality: how many reached this step, how many opened it."""
    out, reached = [], len(_L(people))
    n = 0
    for s in _L(_D(flow).get("steps")):
        s = _D(s)
        if s.get("kind") != "send":
            continue
        n += 1
        at_step = [p for p in _L(people) if int(_D(p).get("sends") or 0) >= n]
        opened = [p for p in at_step if int(_D(p).get("opens") or 0) > 0]
        out.append({"step": n, "label": s.get("label") or f"Email {n}",
                    "reached": len(at_step) or None,
                    "opened": len(opened) or None,
                    "of": f"{len(at_step)} of {reached}" if reached else "-"})
    return out


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = []

    def t(n, c):
        ok.append(bool(c))
        print(("  OK   " if c else "  FAIL ") + n)

    class _S:
        def __init__(self, d=None): self.d = dict(d or {})
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v

    people = [
        {"email": "a@x.de", "name": "Ann", "score": 80, "country": "Germany",
         "sends": 1, "opens": 2, "clicks": 1, "replied": False,
         "timeline": [{"kind": "sent", "at": "2020-01-01T10:00:00"}]},
        {"email": "b@y.us", "name": "Bo", "score": 40, "country": "USA",
         "sends": 0, "opens": 0, "clicks": 0, "replied": False,
         "timeline": []},
    ]
    t("every field has operators that fit it",
      all(ops_for(f) for f in FIELDS))
    t("a number field cannot use contains",
      valid_condition({"field": "score", "op": "contains", "value": "x"}))
    t("an unknown field is refused",
      valid_condition({"field": "nope", "op": "eq", "value": 1}))
    t("a valid condition passes",
      valid_condition({"field": "score", "op": "gte", "value": 70}) == "")
    got = evaluate(people, [{"field": "score", "op": "gte", "value": 70}])
    t("evaluate filters on real values", len(got) == 1
      and got[0]["email"] == "a@x.de")
    got2 = evaluate(people, [{"field": "country", "op": "in",
                              "value": "Germany, Switzerland"}])
    t("'is one of' works on a comma list", len(got2) == 1)
    got3 = evaluate(people, [{"field": "score", "op": "gte", "value": 70},
                             {"field": "clicks", "op": "gte", "value": 1}],
                    match="all")
    t("all-conditions narrows", len(got3) == 1)

    s = _S()
    t("a nameless segment is refused",
      save_segment(s, "", [{"field": "score", "op": "gte", "value": 1}])["ok"]
      is False)
    t("a segment with no condition is refused (it would be everyone)",
      save_segment(s, "All", [])["ok"] is False)
    t("a broken condition is refused with the reason",
      "cannot use" in save_segment(s, "Bad", [
          {"field": "score", "op": "contains", "value": "x"}])["error"])
    r = save_segment(s, "Hot DE", [{"field": "score", "op": "gte",
                                    "value": 70},
                                   {"field": "country", "op": "eq",
                                    "value": "Germany"}])
    t("a good segment saves", r["ok"] and len(segments(s)) == 1)
    t("a segment reads back in words",
      describe(segments(s)[0]) == "Lead score >= 70 and Country is Germany")
    t("saving the same name replaces, never duplicates",
      save_segment(s, "Hot DE", [{"field": "score", "op": "gte",
                                  "value": 90}])["ok"]
      and len(segments(s)) == 1)

    t("there is always a flow to show", len(flows(s)) == 1
      and flows(s)[0]["name"] == "Three-touch outreach")
    t("a flow with a bad step is refused",
      "not send, wait or condition" in
      save_flow(s, {"name": "X", "steps": [{"kind": "teleport"}]})["error"])
    t("a wait with no days is refused",
      "needs days" in save_flow(s, {"name": "X",
                                    "steps": [{"kind": "wait"}]})["error"])
    q = run_flow(s, DEFAULT_FLOW, people)
    t("the runner QUEUES and says it sent nothing",
      "Nothing has been sent" in q["message"])
    t("the queue holds real person-steps", len(flow_queue(s)) == q["queued"]
      and q["queued"] > 0)
    t("nobody is queued twice for the same step",
      len({(x["email"], x["step"]) for x in flow_queue(s)})
      == len(flow_queue(s)))
    st = flow_stats(DEFAULT_FLOW, people)
    t("per-step stats count who really reached it",
      st[0]["reached"] == 1 and st[0]["opened"] == 1)
    t("every step states its denominator", st[0]["of"] == "1 of 2")
    # THE RUNNER CANNOT SEND. Checked by PARSING the module's imports, not
    # by grepping the file - a substring check would match this very
    # assertion and pass for the wrong reason.
    import ast as _ast
    _tree = _ast.parse(open(__file__, encoding="utf-8").read())
    _imports = set()
    for _n in _ast.walk(_tree):
        if isinstance(_n, _ast.Import):
            _imports |= {x.name for x in _n.names}
        elif isinstance(_n, _ast.ImportFrom):
            _imports.add(_n.module or "")
    t("the runner imports no mailer, checked by parsing",
      not any("connector" in m or "outreach" in m for m in _imports))
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
