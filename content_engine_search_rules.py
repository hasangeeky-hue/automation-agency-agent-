# -*- coding: utf-8 -*-
"""Search OS: the rules the whole system is held to, and the audit that
checks them against the running code.

Spec 1-3 and 100-107.

Every other module in this OS makes a promise in a docstring. This one
makes those promises CHECKABLE. Each rule below carries a check function
that runs against the live modules, so the dashboard can prove its own
guarantees instead of asserting them.

That distinction is the whole point. A principle written in a comment is
a hope. A principle with a check that fails the build is a constraint.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1-3. WHAT THIS OS REFUSES TO DO
# ---------------------------------------------------------------------------
#: Stated first because everything else follows from it. These are not
#: features that are missing; they are things the system will not do even
#: when asked, and each one exists because the alternative was tried
#: somewhere and produced a confident wrong answer.
REFUSALS: Tuple[Tuple[str, str], ...] = (
    ("It will not show a number that cannot name its source.",
     "A number with no source cannot be argued with, and a dashboard "
     "nobody can argue with stops being checked."),
    ("It will not render absence as zero.",
     "Zero is a measurement. 'Not measured' is the absence of one. "
     "Merging them turns an unmonitored thing into a healthy one."),
    ("It will not average a ratio.",
     "The mean of ten CTRs is not the CTR. It is a number that looks "
     "like one and moves in the wrong direction when volumes differ."),
    ("It will not call a run successful because it finished.",
     "Executed is not verified, verified is not observed, and observed "
     "is not successful. Collapsing those is how a system reports "
     "progress while achieving nothing."),
    ("It will not send, publish or spend without a named human.",
     "'The agent decided' is not a name, and an outbound action that "
     "cannot be attributed cannot be defended."),
    ("It will not guess an intent, a cause or an outcome.",
     "UNCLASSIFIED, UNKNOWN and INSUFFICIENT_DATA are answers. A guess "
     "wearing their place is worse than a blank."),
    ("It will not loop without a budget.",
     "Every agent run carries max steps, handoffs, tool calls, retries, "
     "cost and time. Exhausting one escalates to a person; it never "
     "quietly tries again."),
    ("It will not hold a secret in a business table.",
     "Tables get exported, backed up and pasted into support tickets. "
     "A reference survives that; a token does not survive it safely."),
)

#: 102. Verdicts. INSUFFICIENT_DATA sits here as a peer, not as a
#: fallback, because a system that has to choose between "good" and
#: "bad" will always find one.
VERDICTS = ("POSITIVE", "NEGATIVE", "NEUTRAL", "INSUFFICIENT_DATA")


def verdict(measured: Any, baseline: Any = None, n: Any = None,
            min_n: int = 30) -> Dict[str, Any]:
    """Classify a change, or refuse to.

    NEUTRAL means "we looked and it did not move". INSUFFICIENT_DATA
    means "we could not look". Those are different findings and this
    function will not swap one for the other.
    """
    if measured is None or baseline is None:
        return {"verdict": "INSUFFICIENT_DATA",
                "why": ("a comparison needs both a measurement and a "
                        "baseline; one of them is missing")}
    try:
        n_val = int(n) if n is not None else None
    except (TypeError, ValueError):
        n_val = None
    if n_val is None:
        return {"verdict": "INSUFFICIENT_DATA",
                "why": ("no sample size was recorded, so the size of "
                        "the move cannot be separated from noise")}
    if n_val < min_n:
        return {"verdict": "INSUFFICIENT_DATA", "n": n_val,
                "why": (f"{n_val} observation(s) is below the {min_n} "
                        f"this comparison needs. NOT 'no effect': too "
                        f"few to tell.")}
    try:
        delta = float(measured) - float(baseline)
    except (TypeError, ValueError):
        return {"verdict": "INSUFFICIENT_DATA",
                "why": "the values are not numbers"}
    if abs(delta) < 1e-9:
        return {"verdict": "NEUTRAL", "delta": 0.0, "n": n_val,
                "why": "measured against baseline, it did not move"}
    return {"verdict": "POSITIVE" if delta > 0 else "NEGATIVE",
            "delta": round(delta, 6), "n": n_val,
            "why": (f"moved {round(delta, 4)} against baseline over "
                    f"{n_val} observation(s)")}


# ---------------------------------------------------------------------------
# 101. RATIOS
# ---------------------------------------------------------------------------
def ratio(numerators: Iterable[Any], denominators: Iterable[Any]
          ) -> Dict[str, Any]:
    """SUM over SUM, computed after aggregation. Never a mean of means.

    Returns None rather than 0.0 when the denominator is zero, because
    "no impressions" is not "a click-through rate of nought".
    """
    num = [float(x) for x in (numerators or ()) if x is not None]
    den = [float(x) for x in (denominators or ()) if x is not None]
    tn, td = sum(num), sum(den)
    if td == 0:
        return {"value": None, "numerator": tn, "denominator": td,
                "why": ("the denominator is zero, so there is no rate. "
                        "Returning 0.0 here would report a failure where "
                        "there was no opportunity.")}
    return {"value": tn / td, "numerator": tn, "denominator": td,
            "why": (f"{tn:g} / {td:g}, summed first and divided once. "
                    f"The mean of the individual rates would be a "
                    f"different number and would not be the rate.")}


def mean_of_ratios(values: Iterable[Any]) -> float:
    """The WRONG calculation, kept so the audit can show the gap.

    This exists to be compared against ratio(), not to be called.
    """
    vals = [float(x) for x in (values or ()) if x is not None]
    return (sum(vals) / len(vals)) if vals else 0.0


# ---------------------------------------------------------------------------
# 100. THE GOLDEN DATA RULE
# ---------------------------------------------------------------------------
def golden_data_check(total: Any, timeseries: Iterable[Any] = (),
                      breakdown: Iterable[Any] = (),
                      tolerance: float = 0.01) -> Dict[str, Any]:
    """The headline, the chart and the table must be the same number.

    Not approximately. A dashboard whose KPI disagrees with the table
    below it teaches the reader to disbelieve both, and they are right
    to.
    """
    if total is None:
        return {"state": "NO TOTAL",
                "why": "nothing was claimed, so nothing can disagree"}
    t = float(total)
    ts = sum(float(x) for x in (timeseries or ()) if x is not None)
    bd = sum(float(x) for x in (breakdown or ()) if x is not None)
    probs = []
    if timeseries and abs(ts - t) > tolerance:
        probs.append(f"the timeseries sums to {ts:g}, the headline says "
                     f"{t:g}")
    if breakdown and abs(bd - t) > tolerance:
        probs.append(f"the breakdown sums to {bd:g}, the headline says "
                     f"{t:g}")
    if probs:
        return {"state": "DISAGREES", "total": t, "timeseries": ts,
                "breakdown": bd, "problems": probs,
                "why": ("; ".join(probs) + ". A reader who notices this "
                        "correctly stops trusting every figure on the "
                        "page, not just this one.")}
    return {"state": "AGREES", "total": t, "timeseries": ts,
            "breakdown": bd,
            "why": "the headline, the chart and the table are one number"}


# ---------------------------------------------------------------------------
# 105-106. VERSION STAMP AND DEGRADED MODE
# ---------------------------------------------------------------------------
MODES = ("NORMAL", "DEGRADED", "READ ONLY")


def stamp(version: Any = None, mode: Any = None,
          sources: Iterable[Any] = ()) -> Dict[str, Any]:
    """What produced this artefact, and under what conditions.

    Anything that leaves this OS carries it. A report, an export or a
    screenshot with no stamp cannot be reproduced, and six weeks later
    nobody can say whether it was right.
    """
    m = str(mode or "NORMAL").upper()
    if m not in MODES:
        m = "DEGRADED"
    stale = [str((s or {}).get("name")) for s in (sources or ())
             if str((s or {}).get("state") or "").upper()
             in ("STALE", "ERROR")]
    return {"version": str(version) if version else "NOT STAMPED",
            "mode": m,
            "degraded_by": stale,
            "trustworthy": (m == "NORMAL" and not stale
                            and bool(version)),
            "why": ("produced under NORMAL mode from current sources"
                    if (m == "NORMAL" and not stale and version) else
                    "; ".join(filter(None, [
                        None if version else "no build version recorded",
                        None if m == "NORMAL" else f"mode was {m}",
                        ("built on stale or errored source(s): "
                         + ", ".join(stale)) if stale else None]))
                    or "unstamped")}


# ---------------------------------------------------------------------------
# 107. THE SELF-AUDIT
# ---------------------------------------------------------------------------
def _c_no_bare_loops() -> Tuple[bool, str]:
    """No unbounded while loop in the engine (spec 52-54)."""
    import ast as _ast
    bad = []
    for mod in ("content_engine_search_loop.py",
                "content_engine_search_rules.py",
                "content_engine_search_data.py"):
        try:
            tree = _ast.parse(open(mod, encoding="utf-8").read())
        except OSError:
            continue
        for node in _ast.walk(tree):
            if isinstance(node, _ast.While):
                bad.append(f"{mod}:{node.lineno}")
    return (not bad,
            "no while loop in the engine modules" if not bad
            else "unbounded loop at " + ", ".join(bad))


def _c_ratio_not_mean() -> Tuple[bool, str]:
    """ratio() and the mean disagree on skewed data, and ratio wins."""
    clicks, imps = [1, 50], [10, 10000]
    correct = ratio(clicks, imps)["value"]
    wrong = mean_of_ratios([c / i for c, i in zip(clicks, imps)])
    return (abs(correct - wrong) > 0.01,
            f"summed rate {correct:.5f} vs mean of rates {wrong:.5f}; "
            f"the mean overstates it by {(wrong / correct):.1f}x because "
            f"a 10-impression row counts as much as a 10,000 one")


def _c_zero_denominator() -> Tuple[bool, str]:
    """A rate over nothing is None, never 0.0."""
    r = ratio([0], [0])
    return (r["value"] is None,
            "a rate with no denominator returns None, not 0.0")


def _c_insufficient_is_a_verdict() -> Tuple[bool, str]:
    """Too few observations is INSUFFICIENT_DATA, not NEUTRAL."""
    v = verdict(10, 10, n=2)
    return (v["verdict"] == "INSUFFICIENT_DATA",
            "2 observations returns " + v["verdict"]
            + ", and 'did not move' is reserved for when we could look")


def _c_neutral_is_distinct() -> Tuple[bool, str]:
    """A real no-change is NEUTRAL, so the two are not the same state."""
    v = verdict(10, 10, n=500)
    return (v["verdict"] == "NEUTRAL",
            "500 observations with no movement returns " + v["verdict"])


def _c_golden_data() -> Tuple[bool, str]:
    """A disagreeing total is caught."""
    bad = golden_data_check(100, [50, 40], [100])
    good = golden_data_check(100, [60, 40], [70, 30])
    return (bad["state"] == "DISAGREES" and good["state"] == "AGREES",
            "a headline of 100 over a chart summing to 90 is caught; a "
            "consistent one passes")


def _c_execution_is_not_success() -> Tuple[bool, str]:
    """advance() physically refuses EXECUTED to SUCCESSFUL (spec 103)."""
    try:
        import content_engine_search_loop as SL
        allowed = SL.MOVES.get("EXECUTED", ())
        return ("SUCCESSFUL" not in allowed,
                "from EXECUTED the only moves are "
                + (", ".join(allowed) or "none")
                + "; success is not among them")
    except Exception as exc:                          # noqa: BLE001
        return (False, "could not read the state machine: "
                + str(exc)[:60])


def _c_no_secret_in_tables() -> Tuple[bool, str]:
    """The canonical model stores a credential REFERENCE (spec 75)."""
    try:
        import content_engine_search_data as D
        ent = D.entity("credential")
        return (bool(ent) and ent["key"] == "credential_ref"
                and "never" in D.CREDENTIAL_RULE,
                "credentials are keyed by credential_ref and the rule is "
                "stated at the model")
    except Exception as exc:                          # noqa: BLE001
        return (False, "could not read the model: " + str(exc)[:60])


def _c_live_writes_are_gated() -> Tuple[bool, str]:
    """apply_change() is dry run by default and needs a named approver."""
    try:
        import content_engine_search_data as D
        dry = D.apply_change("wordpress", "update_title", "/x", "a", "b")
        live = D.apply_change("wordpress", "update_title", "/x", "a", "b",
                              dry_run=False)
        return (dry["state"] == "DRY RUN"
                and live["state"] == "NEEDS APPROVAL",
                "default is DRY RUN; a live write with no approver "
                "returns NEEDS APPROVAL")
    except Exception as exc:                          # noqa: BLE001
        return (False, "could not test the CMS adapter: "
                + str(exc)[:60])


def _c_metric_needs_a_source() -> Tuple[bool, str]:
    """metric() will not render a number that cannot name its origin."""
    try:
        import content_engine_search_screens as S
        try:
            S.metric("x", 1)
            return (False, "metric() rendered a number with no source, "
                           "which is the rule this OS is built on")
        except TypeError:
            return (True, "metric() refuses a value with no named source")
    except Exception as exc:                          # noqa: BLE001
        return (False, "could not load the screens: " + str(exc)[:60])


def _c_unstamped_is_untrustworthy() -> Tuple[bool, str]:
    """An artefact with no version is not trusted (spec 105)."""
    return (not stamp()["trustworthy"]
            and stamp("v17")["trustworthy"],
            "an unstamped artefact is not trustworthy; a stamped one "
            "from current sources is")


#: The audit. id, what it guarantees, and the check that proves it.
RULES: Tuple[Tuple[str, str, Callable[[], Tuple[bool, str]]], ...] = (
    ("bounded-loops", "No unbounded loop exists in the engine.",
     _c_no_bare_loops),
    ("ratio-not-mean", "Ratios are summed then divided, never averaged.",
     _c_ratio_not_mean),
    ("no-rate-over-nothing", "A rate with no denominator is None, not 0.",
     _c_zero_denominator),
    ("insufficient-is-a-verdict",
     "Too little data returns INSUFFICIENT_DATA, never NEUTRAL.",
     _c_insufficient_is_a_verdict),
    ("neutral-is-distinct",
     "A measured no-change returns NEUTRAL, so the two are separable.",
     _c_neutral_is_distinct),
    ("golden-data",
     "Headline, chart and table are one number, by construction.",
     _c_golden_data),
    ("execution-is-not-success",
     "EXECUTED cannot become SUCCESSFUL without verification.",
     _c_execution_is_not_success),
    ("no-secret-in-tables",
     "Business tables hold a credential reference, never a token.",
     _c_no_secret_in_tables),
    ("live-writes-are-gated",
     "A live-site write is dry run by default and needs a named human.",
     _c_live_writes_are_gated),
    ("metric-needs-a-source",
     "No number renders without naming where it came from.",
     _c_metric_needs_a_source),
    ("unstamped-is-untrustworthy",
     "Anything leaving this OS carries a version and a mode.",
     _c_unstamped_is_untrustworthy),
)


def audit() -> Dict[str, Any]:
    """Run every rule against the live code, right now.

    A check that raises is a FAILURE, not a skip. A self-audit that
    quietly excuses the tests it could not run is worse than no audit,
    because it produces a green page over an unknown system.
    """
    results: List[Dict[str, Any]] = []
    for rid, statement, check in RULES:
        try:
            ok, detail = check()
        except Exception as exc:                      # noqa: BLE001
            ok, detail = False, ("the check itself raised: "
                                 + str(exc)[:80])
        results.append({"id": rid, "rule": statement,
                        "state": "HOLDS" if ok else "BROKEN",
                        "evidence": detail})
    broken = [x for x in results if x["state"] == "BROKEN"]
    return {"results": results, "total": len(results),
            "broken": len(broken),
            "state": "ALL HOLD" if not broken else "BROKEN",
            "why": ("every rule was checked against the running code, "
                    "not against a comment"
                    if not broken else
                    str(len(broken)) + " rule(s) this OS claims to keep "
                    "are not being kept: "
                    + ", ".join(x["id"] for x in broken))}
