"""
content_engine_os_audience.py
============================================================================
ENGINE 3 AND 4: LISTS (static) AND SEGMENTS (a dynamic query).

A LIST is a bag of people someone put there. A SEGMENT is a question asked
of every profile each time you look. They are different objects because
they fail differently: a list goes stale silently, a segment cannot.

THE RULE TREE
  A segment is stored as a nested group, never as hard-coded Python. That
  is the whole point: the founder can ask a question nobody wrote code for.

    {"operator": "AND", "conditions": [
        {"field": "country", "operator": "equals", "value": "Germany"},
        {"operator": "OR", "conditions": [...]}]}

  evaluate() walks it. Fourteen operators, nested AND/OR to any depth.

AUDIENCE RESOLUTION IS NOT SEGMENT EVALUATION
  resolve_audience() answers "who would actually receive this", which means
  the segment, then suppression, then consent, then a valid address. The
  difference between those two numbers is the most useful thing on the
  review screen, so it is returned rather than hidden.

READ-ONLY OVER THE REPO. Nothing here sends or queues.
============================================================================
"""

from __future__ import annotations

import content_engine_os_core as CORE
from content_engine_os_core import SEGMENT_OPS, _D, _L, norm_email, rid

# Fields a segment may ask about. A field not on this list is refused at
# save time, so a typo becomes an error message instead of a segment that
# silently matches nobody.
FIELDS = {
    "email":        {"kind": "string", "label": "Email"},
    "first_name":   {"kind": "string", "label": "First name"},
    "last_name":    {"kind": "string", "label": "Last name"},
    "company":      {"kind": "string", "label": "Company"},
    "job_title":    {"kind": "string", "label": "Job title"},
    "website":      {"kind": "string", "label": "Website"},
    "country":      {"kind": "string", "label": "Country"},
    "city":         {"kind": "string", "label": "City"},
    "language":     {"kind": "string", "label": "Language"},
    "source":       {"kind": "string", "label": "Source"},
    "consent":      {"kind": "enum", "label": "Subscription status",
                     "options": list(CORE.CONSENT_STATES)},
    "lead_stage":   {"kind": "enum", "label": "Lead stage",
                     "options": list(CORE.LEAD_STAGES)},
    "lead_score":   {"kind": "number", "label": "Lead score"},
    "emails_sent":  {"kind": "number", "label": "Emails sent"},
    "opens":        {"kind": "number", "label": "Opens"},
    "clicks":       {"kind": "number", "label": "Clicks"},
    "days_since_activity": {"kind": "number", "label": "Days since activity"},
    "sent_total":   {"kind": "number", "label": "Emails ever sent"},
    "is_scanner":   {"kind": "enum", "label": "Clicks are a scanner",
                     "options": ["yes", "no"]},
    "resting":      {"kind": "enum", "label": "Resting",
                     "options": ["yes", "no"]},
    "created_at":   {"kind": "date", "label": "Created"},
    "last_activity_at": {"kind": "date", "label": "Last activity"},
    "industry":     {"kind": "string", "label": "Industry (custom)"},
    "company_size": {"kind": "string", "label": "Company size (custom)"},
}

# Which operators make sense for which kind of field. Offering "greater
# than" on a country is how a builder teaches people it is untrustworthy.
OPS_FOR = {
    "string": ("equals", "not_equals", "contains", "not_contains",
               "exists", "not_exists", "in", "not_in"),
    "enum":   ("equals", "not_equals", "in", "not_in", "exists", "not_exists"),
    "number": ("equals", "not_equals", "greater_than", "less_than",
               "greater_or_equal", "less_or_equal", "exists", "not_exists"),
    "date":   ("before", "after", "exists", "not_exists"),
}

OP_WORDS = {
    "equals": "is", "not_equals": "is not", "contains": "contains",
    "not_contains": "does not contain", "greater_than": "is greater than",
    "less_than": "is less than", "greater_or_equal": "is at least",
    "less_or_equal": "is at most", "exists": "is set",
    "not_exists": "is not set", "in": "is one of", "not_in": "is not one of",
    "before": "is before", "after": "is after",
}


# ---------------------------------------------------------------------------
# The evaluator
# ---------------------------------------------------------------------------
def _num(v):
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def _as_list(v) -> list:
    if isinstance(v, (list, tuple)):
        return [str(x).strip().lower() for x in v]
    return [x.strip().lower() for x in str(v or "").split(",") if x.strip()]


def compare(actual, op, expected) -> bool:
    """One comparison. Missing data is FALSE for every operator except
    not_exists and not_in, because "unknown" must never be read as a match."""
    if op == "exists":
        return actual not in (None, "", [], {})
    if op == "not_exists":
        return actual in (None, "", [], {})
    if op == "not_in":
        return str(actual or "").strip().lower() not in _as_list(expected)
    if actual in (None, "", [], {}):
        return False
    a_s = str(actual).strip().lower()
    e_s = str(expected or "").strip().lower()
    if op == "equals":
        return a_s == e_s
    if op == "not_equals":
        return a_s != e_s
    if op == "contains":
        return e_s in a_s
    if op == "not_contains":
        return e_s not in a_s
    if op == "in":
        return a_s in _as_list(expected)
    if op in ("greater_than", "less_than", "greater_or_equal",
              "less_or_equal"):
        a, b = _num(actual), _num(expected)
        if a is None or b is None:
            return False
        return {"greater_than": a > b, "less_than": a < b,
                "greater_or_equal": a >= b, "less_or_equal": a <= b}[op]
    if op in ("before", "after"):
        a, b = CORE.parse_at(actual), CORE.parse_at(expected)
        if a is None or b is None:
            return False
        return a < b if op == "before" else a > b
    return False


def evaluate(node, person) -> bool:
    """Walk the rule tree. A group has "conditions"; a leaf has "field"."""
    node = _D(node)
    if "conditions" in node:
        op = str(node.get("operator") or "AND").upper()
        kids = _L(node.get("conditions"))
        if not kids:
            return True                       # an empty group matches everyone
        results = [evaluate(k, person) for k in kids]
        return all(results) if op != "OR" else any(results)
    field = node.get("field")
    if field not in FIELDS:
        return False
    return compare(_D(person).get(field), node.get("operator"),
                   node.get("value"))


def describe(node, depth=0) -> str:
    """The rule in words. A builder people cannot read is a builder people
    do not trust, and an unreadable audience is how the wrong 400 people
    get an email."""
    node = _D(node)
    if "conditions" in node:
        joiner = f" {str(node.get('operator') or 'AND').upper()} "
        inner = joiner.join(describe(k, depth + 1)
                            for k in _L(node.get("conditions")))
        return f"({inner})" if depth and inner else inner or "everyone"
    label = _D(FIELDS.get(node.get("field"))).get("label") or node.get("field")
    word = OP_WORDS.get(node.get("operator"), node.get("operator"))
    if node.get("operator") in ("exists", "not_exists"):
        return f"{label} {word}"
    return f"{label} {word} {node.get('value')}"


def validate(node, _depth=0) -> tuple:
    """(ok, message). Refuses at save time rather than at send time."""
    node = _D(node)
    if _depth > 6:
        return False, "that rule is nested too deep to be understood"
    if "conditions" in node:
        if str(node.get("operator") or "AND").upper() not in ("AND", "OR"):
            return False, "a group must join its conditions with AND or OR"
        for k in _L(node.get("conditions")):
            ok, why = validate(k, _depth + 1)
            if not ok:
                return ok, why
        return True, ""
    f, op = node.get("field"), node.get("operator")
    if f not in FIELDS:
        return False, f"there is no field called {f!r} to filter on"
    if op not in SEGMENT_OPS:
        return False, f"{op!r} is not a comparison this engine makes"
    kind = _D(FIELDS[f]).get("kind", "string")
    if op not in OPS_FOR.get(kind, ()):
        return (False, f"{OP_WORDS.get(op, op)!r} does not apply to "
                       f"{_D(FIELDS[f]).get('label')}, which is a {kind}")
    if op not in ("exists", "not_exists") and str(node.get("value") or "") == "":
        return False, "that condition needs a value to compare against"
    return True, ""


# ---------------------------------------------------------------------------
# The person view a segment is asked about
# ---------------------------------------------------------------------------
def _scanners_cached(repo):
    """Who is a machine. Imported lazily so this module keeps no dependency
    on analytics, which reads it back."""
    try:
        import content_engine_os_analytics as _AN
        return _AN.scanners(repo)
    except Exception:
        return {}



def people(repo) -> list:
    """Every profile flattened into the fields a segment can ask about,
    with its engagement counted from events. Built once per evaluation so a
    segment over 5,000 profiles does not walk the event list 5,000 times."""
    profs = repo.all("profiles")
    props = {}
    for r in repo.all("profile_properties"):
        props.setdefault(r.get("profile_id"), {})[r.get("key")] = r.get("value")
    leads = {l.get("primary_profile_id"): l for l in repo.all("leads")}
    scan = CORE._D(_scanners_cached(repo))
    sent, opens, clicks, last = {}, {}, {}, {}
    for e_ in repo.all("email_events"):
        pid, k = e_.get("profile_id"), e_.get("event_type")
        at = e_.get("timestamp")
        if at and str(at) > str(last.get(pid, "")):
            last[pid] = at
        if k == "EMAIL_SENT":
            sent[pid] = sent.get(pid, 0) + 1
        elif k == "EMAIL_OPENED":
            opens[pid] = opens.get(pid, 0) + 1
        elif k == "EMAIL_CLICKED":
            clicks[pid] = clicks.get(pid, 0) + 1
    out = []
    for p in profs:
        pid = p.get("id")
        lead = leads.get(pid) or {}
        pr = props.get(pid) or {}
        act = last.get(pid) or p.get("last_activity_at") or ""
        row = {k: p.get(k) for k in CORE.PROFILE_FIELDS}
        row.update({
            "id": pid, "email": p.get("email"),
            "first_name": p.get("first_name"), "last_name": p.get("last_name"),
            "consent": p.get("consent") or "NEVER_SUBSCRIBED",
            "created_at": p.get("created_at"),
            "lead_stage": lead.get("stage"), "lead_id": lead.get("id"),
            "lead_score": lead.get("score", pr.get("lead_score")),
            "emails_sent": sent.get(pid, 0), "sent_total": sent.get(pid, 0),
            "opens": opens.get(pid, 0), "clicks": clicks.get(pid, 0),
            "rest_until": p.get("rest_until", ""),
            "rest_reason": p.get("rest_reason", ""),
            "resting": "yes" if CORE.resting(p) else "no",
            "is_scanner": "yes" if pid in scan else "no",
            "scanner_why": scan.get(pid, ""),
            "last_activity_at": act,
            "days_since_activity": CORE.days_ago(act),
            "industry": pr.get("industry"), "company_size": pr.get("company_size"),
            "properties": pr,
        })
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------
def save_list(repo, name, description="") -> dict:
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "error": "a list needs a name"}
    rec = repo.put("lists", {"id": rid("lst", repo.ws, nm.lower()),
                             "name": nm, "description": description})
    return {"ok": True, "id": rec["id"], "message": f"list {nm!r} saved"}


def add_to_list(repo, list_id, profile_ids, source="manual") -> dict:
    n = 0
    for pid in _L(profile_ids):
        repo.put("list_members", {
            "id": rid("lm", repo.ws, list_id, pid),
            "list_id": list_id, "profile_id": pid,
            "added_at": CORE.now(), "source": source})
        n += 1
    return {"ok": True, "added": n}


def remove_from_list(repo, list_id, profile_ids) -> dict:
    n = 0
    for pid in _L(profile_ids):
        if repo.delete("list_members", rid("lm", repo.ws, list_id, pid)):
            n += 1
    return {"ok": True, "removed": n}


def list_rows(repo) -> list:
    members = {}
    for m in repo.all("list_members"):
        members[m.get("list_id")] = members.get(m.get("list_id"), 0) + 1
    return [{"id": l.get("id"), "name": l.get("name"),
             "description": l.get("description", ""),
             "members": members.get(l.get("id"), 0),
             "created_at": l.get("created_at")}
            for l in repo.all("lists")]


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------
def save_segment(repo, name, tree) -> dict:
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "error": "a segment needs a name"}
    ok, why = validate(tree)
    if not ok:
        return {"ok": False, "error": why, "message": "not saved: " + why}
    rec = repo.put("segments", {"id": rid("seg", repo.ws, nm.lower()),
                                "name": nm, "tree": tree,
                                "described": describe(tree)})
    n = len(members(repo, rec))
    return {"ok": True, "id": rec["id"], "size": n,
            "message": f"{nm!r} saved: {describe(tree)}. "
                       f"{n} people match right now."}


def delete_segment(repo, seg_id) -> dict:
    return {"ok": repo.delete("segments", seg_id),
            "message": "segment removed"}


def members(repo, segment, _people=None) -> list:
    rows = _people if _people is not None else people(repo)
    return [p for p in rows if evaluate(_D(segment).get("tree"), p)]


def segment_rows(repo) -> list:
    rows = people(repo)
    return [{"id": s.get("id"), "name": s.get("name"),
             "described": s.get("described") or describe(s.get("tree")),
             "tree": s.get("tree"),
             "size": len(members(repo, s, rows)),
             "created_at": s.get("created_at")}
            for s in repo.all("segments")]


# ---------------------------------------------------------------------------
# AUDIENCE RESOLUTION. Who would really receive this.
# ---------------------------------------------------------------------------
def resolve_audience(repo, kind, ref="", tree=None) -> dict:
    """Returns the eligible people AND the reason every excluded person was
    excluded. The review screen shows both, because "8,420 recipients" with
    183 silently dropped is the number that gets a founder in trouble.

    kind: "all" | "list" | "segment" | "filter" | "job"
    """
    rows = people(repo)
    supp = CORE.suppression_index(repo)
    if kind == "list":
        ids = {m.get("profile_id") for m in repo.find("list_members",
                                                      list_id=ref)}
        pool = [p for p in rows if p.get("id") in ids]
        label = "list"
    elif kind == "segment":
        seg = repo.one("segments", ref) or {}
        pool = members(repo, seg, rows)
        label = seg.get("name") or "segment"
    elif kind == "filter":
        pool = [p for p in rows if evaluate(tree, p)]
        label = describe(tree)
    elif kind == "job":
        ids = {m.get("profile_id") for m in repo.find("campaign_messages",
                                                      job_id=ref)}
        pool = [p for p in rows if p.get("id") in ids] or rows
        label = "campaign leads"
    else:
        pool, label = rows, "everyone"

    eligible, dropped = [], {"suppressed": [], "unsubscribed": [],
                             "not_confirmed": [], "resting": [],
                             "invalid_address": []}
    for p in pool:
        em = norm_email(p.get("email"))
        if not CORE.valid_email(em):
            dropped["invalid_address"].append(em or "(blank)")
            continue
        if em in supp:
            dropped["suppressed"].append(em)
            continue
        if p.get("consent") == "UNSUBSCRIBED":
            dropped["unsubscribed"].append(em)
            continue
        if p.get("resting") == "yes":
            dropped["resting"].append(em)
            continue
        if p.get("consent") == "PENDING":
            # PENDING IS NOT A SUBSCRIBER. Somebody filled in the form and
            # never clicked the confirmation, which is a no. Treating it as
            # a yes would make double opt-in a decoration and would be the
            # single worst thing on this screen for a founder sending into
            # Germany.
            dropped["not_confirmed"].append(em)
            continue
        eligible.append(p)
    return {"label": label, "pool": len(pool), "eligible": eligible,
            "deliverable": len(eligible),
            "dropped": {k: len(v) for k, v in dropped.items()},
            "dropped_detail": dropped,
            "suppressed": len(dropped["suppressed"])}
