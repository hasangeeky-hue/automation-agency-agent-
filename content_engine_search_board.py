"""
content_engine_search_board.py
============================================================================
THE EXECUTION BOARD AND THE LOOP MONITOR. Spec sections 61, 62, 63, 70.

Two screens, one job: make it impossible to believe an optimisation
worked when nobody measured it.

  - The Execution board is the Kanban of states. EXECUTED sits in its own
    column and is labelled "not a result yet", because that is the column
    where every SEO tool in the world quietly declares victory.
  - The Loop Monitor is the table the spec asks for: initiative, stage,
    baseline, current signal, result. An initiative with no observation
    shows "not measured", never a zero and never a guess.
  - Every score is shown with its components (spec 70). There is no bare
    number anywhere on these screens.

This module RENDERS. It computes nothing: every fact comes from
content_engine_search_loop, so the board and the engine cannot disagree.
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_search_loop as SL
from content_engine_os_core import _D, _L

#: The Kanban columns, spec 61. One tuple, used by the board and the gates.
COLUMNS = (
    ("RECOMMENDED", "Proposed", "waiting to be planned"),
    ("APPROVAL_REQUIRED", "Approval", "needs your click"),
    ("EXECUTING", "Executing", "being applied"),
    ("EXECUTED", "Executed", "NOT a result yet"),
    ("TECHNICALLY_VERIFIED", "Verified", "the change is really live"),
    ("OBSERVING", "Observing", "waiting for search to answer"),
    ("SUCCESSFUL", "Success", "measured, not assumed"),
    ("UNSUCCESSFUL", "Failed", "measured, and it did not work"),
)

#: state -> semantic colour class, spec 8/9. Green is reserved for
#: VERIFIED SUCCESS only; executed is amber because it is unfinished.
TONE = {"SUCCESSFUL": "ok", "TECHNICALLY_VERIFIED": "ok",
        "REGRESSION": "bad", "UNSUCCESSFUL": "bad",
        "ESCALATED": "bad", "VERIFICATION_FAILED": "bad",
        "EXECUTED": "warn", "OBSERVING": "warn",
        "APPROVAL_REQUIRED": "warn"}


def e(v) -> str:
    return _html.escape(str("" if v is None else v), quote=True)


def _n(v, dash="not measured"):
    if v in (None, "", {}):
        return dash
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return e(v)


def execution_board(r) -> str:
    """Spec 61. The Kanban. EXECUTED is called out as unfinished."""
    items = r.all("search_initiatives")
    by = {}
    for it in items:
        by.setdefault(it.get("state"), []).append(it)
    cols = []
    for state, label, note in COLUMNS:
        rows = by.get(state, [])
        cards = "".join(
            "<div class='sl-card sl-" + TONE.get(state, "flat") + "'>"
            f"<b>{e(_D(x.get('recommendation')).get('action'))[:60]}</b>"
            f"<span>{e(x.get('target'))}</span>"
            f"<span>{e(x.get('agent'))} &middot; risk "
            f"{e(x.get('risk'))}</span>"
            + (f"<span class='sl-warn'>executed "
               f"{e(str(x.get('state_at'))[:10])}, not verified</span>"
               if state == "EXECUTED" else "")
            + "</div>" for x in rows[:6])
        cols.append(
            f"<div class='sl-col'><p class='sl-colh'>{e(label)}"
            f"<i>{len(rows)}</i></p>"
            f"<p class='sl-note'>{e(note)}</p>"
            + (cards or "<p class='sl-empty'>nothing here</p>")
            + "</div>")
    return "<div class='sl-board'>" + "".join(cols) + "</div>"


def loop_monitor(r) -> str:
    """Spec 62. Initiative, stage, baseline, current signal, result."""
    items = sorted(r.all("search_initiatives"),
                   key=lambda x: str(x.get("state_at") or ""), reverse=True)
    if not items:
        return ("<p class='sl-empty'>No optimisation initiative has been "
                "opened yet. This table fills when an opportunity is "
                "accepted; it stays empty rather than showing an example."
                "</p>")
    rows = []
    for it in items[:40]:
        obs = _L(it.get("observations"))
        base = _D(it.get("baseline"))
        latest = _D(obs[-1].get("metrics")) if obs else {}
        metric = _D(it.get("recommendation")).get("success_metric") or \
            "position"
        b, l = base.get(metric), latest.get(metric)
        if b in (None, "") or l in (None, ""):
            signal = "not measured"
        else:
            lower_better = metric in ("position", "cpa")
            delta = (float(b) - float(l)) if lower_better \
                else (float(l) - float(b))
            signal = (f"{_n(b)} to {_n(l)} "
                      + ("(better)" if delta > 0 else
                         "(worse)" if delta < 0 else "(flat)"))
        # the three results, never merged into one word
        res = " / ".join(
            f"{k.split('_')[0]}: {it.get(k) or 'not measured'}"
            for k in SL.RESULT_KINDS)
        rows.append(
            "<tr><td>"
            + e(_D(it.get("recommendation")).get("action"))[:48]
            + "</td><td>" + e(it.get("kind"))
            + "</td><td>" + e(it.get("target"))[:40]
            + "</td><td>" + e(it.get("agent"))
            + f"</td><td class='sl-{TONE.get(it.get('state'), 'flat')}'>"
            + e(it.get("state"))
            + "</td><td>" + e(str(it.get("state_at"))[:10])
            + "</td><td>" + (f"{len(obs)} obs" if obs else "none")
            + "</td><td>" + e(signal)
            + "</td><td>" + e(res) + "</td></tr>")
    return ("<div class='sl-scroll'><table class='sl-tbl'><thead><tr>"
            + "".join(f"<th>{e(h)}</th>" for h in
                      ("Initiative", "Type", "Target", "Agent", "Stage",
                       "Since", "Observations", "Signal",
                       "Results (impl / search / business)"))
            + "</tr></thead><tbody>" + "".join(rows)
            + "</tbody></table></div>"
            + "<p class='sl-note'>An initiative is complete only when it "
              "is executed, verified, observed AND judged. Anything short "
              "of that reads 'not measured' here rather than a number.</p>")


def timeline(r, initiative_id) -> str:
    """Spec 63. The action detail timeline, from recorded history only."""
    it = r.one("search_initiatives", initiative_id)
    if not it:
        return "<p class='sl-empty'>no such initiative</p>"
    steps = "".join(
        f"<div class='sl-step'><b>{e(str(h.get('at'))[:16])}</b>"
        f"<span class='sl-{TONE.get(h.get('state'), 'flat')}'>"
        f"{e(h.get('state'))}</span>"
        f"<span>{e(h.get('why'))}</span></div>"
        for h in _L(it.get("history")))
    obs = "".join(
        f"<div class='sl-step'><b>{e(str(o.get('at'))[:16])}</b>"
        f"<span>OBSERVED ({e(o.get('window'))}, day {o.get('day')})</span>"
        f"<span>{e(', '.join(f'{k} {v}' for k, v in _D(o.get('metrics')).items()))[:90]}</span>"
        "</div>" for o in _L(it.get("observations")))
    diff = _D(it.get("verification_diff"))
    dhtml = ("".join(
        f"<p class='sl-bad'>{e(k)}: wanted {e(_D(v).get('wanted'))}, "
        f"found {e(_D(v).get('found'))}</p>" for k, v in diff.items())
        if diff else "")
    return ("<div class='sl-timeline'>" + steps + obs + "</div>" + dhtml
            + f"<p class='sl-note'>outcome: "
              f"{e(it.get('outcome') or 'not judged yet')}</p>")


def health_breakdown(scores) -> str:
    """Spec 70. A score is never shown without its components."""
    d = _D(scores)
    if not d:
        return ("<p class='sl-empty'>no health components have been "
                "measured, so no score is shown. A bare number without "
                "its parts is not evidence.</p>")
    total = round(sum(float(v) for v in d.values()) / len(d))
    return ("<div class='sl-hs'><span class='sl-score'><b>" + str(total)
            + "</b>/100</span>"
            + "".join(f"<span>{e(k)} {_n(v)}</span>"
                      for k, v in sorted(d.items()))
            + "</div><p class='sl-note'>the score is the mean of the "
              "components beside it; each one is measured, not weighted "
              "by an invented constant.</p>")


def section(r) -> str:
    """The whole Search OS execution surface."""
    b = SL.board(r)
    learn = SL.learning(r)
    return (CSS
            + "<div class='sl-root'>"
            + "<p class='sl-h'>EXECUTION</p>"
            + f"<p class='sl-note'>{e(b['message'])}</p>"
            + execution_board(r)
            + "<p class='sl-h'>LOOP MONITOR</p>"
            + loop_monitor(r)
            + "<p class='sl-h'>WHAT HAS ACTUALLY WORKED</p>"
            + (("<div class='sl-scroll'><table class='sl-tbl'><thead><tr>"
                "<th>Type</th><th>Win</th><th>Neutral</th><th>Loss</th>"
                "<th>Insufficient</th></tr></thead><tbody>"
                + "".join(
                    f"<tr><td>{e(k)}</td><td>{v.get('WIN', 0)}</td>"
                    f"<td>{v.get('NEUTRAL', 0)}</td>"
                    f"<td>{v.get('LOSS', 0)}</td>"
                    f"<td>{v.get('INSUFFICIENT_DATA', 0)}</td></tr>"
                    for k, v in sorted(_D(learn.get("by_kind")).items()))
                + "</tbody></table></div>")
               if learn.get("by_kind") else
               f"<p class='sl-empty'>{e(learn['message'])}</p>")
            + "</div>")


CSS = """<style>
.sl-root{font-size:13px;color:#111827}
.sl-h{font-size:11px;letter-spacing:1.4px;color:#4B5563;
font-weight:700;margin:16px 0 6px}
.sl-note{color:#4B5563;font-size:11px;margin:5px 0}
.sl-empty{color:#4B5563;font-size:12px;margin:6px 0}
.sl-board{display:flex;gap:9px;overflow-x:auto;padding-bottom:6px}
.sl-col{min-width:165px;flex:1;border:1px solid #E5E7EB;
border-radius:10px;padding:9px 10px;background:#FFFFFF}
.sl-colh{margin:0;font-size:12px;font-weight:700;display:flex;
justify-content:space-between}
.sl-colh i{font-style:normal;color:#4B5563}
.sl-card{border:1px solid #E5E7EB;border-left-width:3px;
border-radius:8px;padding:7px 9px;margin:6px 0;display:flex;
flex-direction:column;gap:2px}
.sl-card b{font-size:12px}
.sl-card span{font-size:10px;color:#4B5563}
.sl-ok{border-left-color:#16A34A}.sl-warn{border-left-color:#D97706}
.sl-bad{border-left-color:#DC2626}.sl-flat{border-left-color:#4B5563}
td.sl-ok,span.sl-ok{color:#3FD98B}td.sl-warn,span.sl-warn{color:#F5B14C}
td.sl-bad,span.sl-bad,p.sl-bad{color:#FF6B93}
.sl-scroll{overflow-x:auto}
.sl-tbl{border-collapse:collapse;width:100%;font-size:12px}
.sl-tbl th{color:#4B5563;text-transform:uppercase;
font-size:10px;letter-spacing:.4px;text-align:left;padding:5px 8px;
border-bottom:1px solid #E5E7EB}
.sl-tbl td{padding:5px 8px;border-bottom:1px solid #E5E7EB;
font-variant-numeric:tabular-nums}
.sl-timeline{display:flex;flex-direction:column;gap:3px;margin:6px 0}
.sl-step{display:flex;gap:9px;align-items:baseline;font-size:11px}
.sl-step b{min-width:110px;color:#4B5563;font-weight:400}
.sl-hs{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:5px 0}
.sl-hs span{border:1px solid #E5E7EB;border-radius:7px;
padding:2px 9px;font-size:10px;color:#4B5563}
.sl-score b{font-size:18px;color:#111827}
</style>"""
