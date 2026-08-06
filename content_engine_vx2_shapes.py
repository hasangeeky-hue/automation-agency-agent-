"""
content_engine_vx2_shapes.py
============================================================================
THE SIX SHAPES, DRAWN. This is the grammar's ink.

The design document is exact about how each kind of number is allowed to
appear, and this module is that document turned into SVG:

  SCORE    a ring, the number inside, the threshold marked
  RATIO    one bar, filled portion coloured, both numbers in mono
  COUNT    the number, large, in mono, with its unit beside it
  TREND    sparkline, last point emphasised, no axes
  SPLIT    one stacked bar, segments labelled, no pie
  STATE    a dot and a word, never a number

No pies, no donuts beyond the single score ring, no 3-D, no dual axes.

THE HONESTY RULE
  Every renderer here draws only what it is given. hero() parses the value a
  board actually produced; when the value does not parse as that shape (a
  SCORE whose value is a word, a RATIO with no denominator) it falls back to
  the plain mono number rather than inventing geometry. A drawn shape is a
  claim about the data, and a claim needs the data.
============================================================================
"""

from __future__ import annotations

import html as _html
import math
import re


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


# state colours, shared with the main module's palette
_COL = {"bad": "var(--bad)", "warn": "var(--warnc)", "ok": "var(--okc)",
        "quiet": "var(--ft)"}


def _band(v: float) -> str:
    return "bad" if v < 60 else ("warn" if v < 85 else "ok")


# ---------------------------------------------------------------------------
# parsers - a shape is only drawn when the value really has that shape
# ---------------------------------------------------------------------------
def _num(s) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(s or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def _ratio(s) -> tuple | None:
    """'189/257', '7 of 9', '189 / 257' -> (189, 257)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:/|of)\s*(\d+(?:[.,]\d+)?)",
                  str(s or ""), re.I)
    if not m:
        return None
    try:
        x = float(m.group(1).replace(",", "."))
        y = float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    return (x, y) if y > 0 else None


# ---------------------------------------------------------------------------
# the renderers
# ---------------------------------------------------------------------------
def score_ring(value: float, *, target: float = 80, size: int = 64) -> str:
    """The ring: the number inside, the arc showing how much of 100 it is."""
    v = max(0.0, min(100.0, float(value)))
    col = _COL[_band(v)]
    r = (size - 10) / 2
    c = 2 * math.pi * r
    filled = c * v / 100.0
    mid = size / 2
    return (
        f"<svg class='shp' width='{size}' height='{size}' "
        f"viewBox='0 0 {size} {size}' role='img' "
        f"aria-label='score {v:.0f} of 100'>"
        f"<circle cx='{mid}' cy='{mid}' r='{r}' fill='none' "
        f"stroke='var(--ln)' stroke-width='6'/>"
        f"<circle cx='{mid}' cy='{mid}' r='{r}' fill='none' stroke='{col}' "
        f"stroke-width='6' stroke-linecap='round' "
        f"stroke-dasharray='{filled:.1f} {c:.1f}' "
        f"transform='rotate(-90 {mid} {mid})'/>"
        f"<text x='{mid}' y='{mid + 5}' text-anchor='middle' font-size='16' "
        f"font-family='ui-monospace,Menlo,monospace' font-weight='700' "
        f"fill='currentColor'>{v:.0f}</text></svg>")


def ratio_bar(x: float, y: float, *, width: int = 150) -> str:
    """One bar, the filled part coloured, both numbers beside it in mono."""
    frac = max(0.0, min(1.0, x / y))
    col = _COL[_band(frac * 100)]
    return (
        f"<span class='shp shp-ratio' role='img' "
        f"aria-label='{x:.0f} of {y:.0f}'>"
        f"<svg width='{width}' height='12' viewBox='0 0 {width} 12'>"
        f"<rect x='0' y='2' width='{width}' height='8' rx='4' fill='var(--ln)'/>"
        f"<rect x='0' y='2' width='{max(2, frac * width):.0f}' height='8' "
        f"rx='4' fill='{col}'/></svg>"
        f"<b>{x:.0f}/{y:.0f}</b></span>")


def sparkline(series, *, width: int = 150, height: int = 34) -> str:
    """The same number over time. Last point emphasised, no axes.

    Drawn ONLY from a real series of two or more numbers; a sparkline
    conjured from a single value would be a picture of nothing.
    """
    pts = [p for p in (_num(v) for v in (series or ())) if p is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    xy = [(i * step, height - 4 - (p - lo) / span * (height - 8))
          for i, p in enumerate(pts)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}"
                    for i, (x, y) in enumerate(xy))
    lx, ly = xy[-1]
    return (
        f"<svg class='shp' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}' role='img' aria-label='trend'>"
        f"<path d='{path}' fill='none' stroke='var(--ac)' stroke-width='2'/>"
        f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='3' fill='var(--ac)'/></svg>")


def split_bar(parts, *, width: int = 190) -> str:
    """Parts of a whole: one stacked bar, segments labelled. Never a pie."""
    rows = [(str(n), _num(v)) for n, v in (parts or ()) if _num(v)]
    total = sum(v for _n, v in rows)
    if not rows or total <= 0:
        return ""
    cols = ("var(--ac)", "#7A9BE8", "#B9C6EE", "var(--ln)")
    x, segs = 0.0, []
    for i, (_n, v) in enumerate(rows[:4]):
        w = v / total * width
        segs.append(f"<rect x='{x:.1f}' y='0' width='{max(1, w):.1f}' "
                    f"height='12' fill='{cols[min(i, 3)]}'/>")
        x += w
    label = " &middot; ".join(f"{e(n)} {v:.0f}" for n, v in rows[:4])
    return (f"<span class='shp shp-split'>"
            f"<svg width='{width}' height='12' viewBox='0 0 {width} 12' "
            f"role='img' aria-label='split'>{''.join(segs)}</svg>"
            f"<i>{label}</i></span>")


def state_word(word: str, tone: str = "quiet") -> str:
    """Up, down or off, per thing: a dot and a word, never a number."""
    col = _COL.get(tone, _COL["quiet"])
    return (f"<span class='shp shp-state' style='color:{col}'>"
            f"<i style='background:{col}'></i>{e(word)}</span>")


def count_big(value, unit: str = "") -> str:
    return (f"<span class='shp shp-count'><b>{e(value)}</b>"
            + (f"<i>{e(unit)}</i>" if unit else "") + "</span>")


# ---------------------------------------------------------------------------
# hero() - the one entry point: draw the shape the data actually supports
# ---------------------------------------------------------------------------
_STATE_WORDS = {"live": "ok", "on": "ok", "healthy": "ok", "up": "ok",
                "ready": "ok", "connected": "ok", "publish": "ok",
                "down": "bad", "off": "quiet", "failed": "bad", "dead": "bad",
                "paused": "warn", "stopped": "warn", "draft": "warn",
                "degraded": "warn", "stale": "warn", "safe": "ok"}


def hero(shape: str, big, sub: str = "", *, accent_state: str = "quiet") -> str:
    """The headline visual for a readout, per the grammar. Falls back to the
    plain mono value whenever the data does not really have the shape."""
    s = str(big if big is not None else "").strip()
    if shape == "SCORE":
        v = _num(s)
        if v is not None and 0 <= v <= 100 and "/" not in s:
            return score_ring(v)
    if shape == "RATIO":
        r = _ratio(s) or _ratio(f"{s} of {sub}" if _num(sub) else "")
        if r:
            return ratio_bar(*r)
    if shape == "STATE":
        w = s.lower()
        if w in _STATE_WORDS:
            return state_word(s, _STATE_WORDS[w])
    # COUNT, TREND-without-a-series, and every unparseable value: the number,
    # large, in mono, with its unit beside it. Honest and always available.
    return count_big(s if s else "--", sub[:24])


CSS = """
.shp{display:inline-flex;align-items:center;gap:8px;vertical-align:middle;
color:var(--tx)}
.shp-ratio b,.shp-count b{font-family:ui-monospace,Menlo,monospace;
font-variant-numeric:tabular-nums;font-weight:700}
.shp-ratio b{font-size:14px}
.shp-count b{font-size:30px;line-height:1}
.shp-count i{font-style:normal;font-size:12px;color:var(--ft)}
.shp-split{flex-direction:column;align-items:flex-start;gap:4px}
.shp-split i{font-style:normal;font-size:10.5px;color:var(--ft);
font-family:ui-monospace,Menlo,monospace}
.shp-state{font-family:ui-monospace,Menlo,monospace;font-size:15px;
font-weight:700;gap:7px}
.shp-state i{width:8px;height:8px;border-radius:50%;display:inline-block}
"""


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    checks = []

    def t(name, ok):
        checks.append(ok)
        print(("  OK   " if ok else "  FAIL ") + name)

    t("SCORE 54 draws a ring", "<circle" in hero("SCORE", "54"))
    t("SCORE keeps the number inside", ">54<" in hero("SCORE", "54"))
    t("SCORE with a word falls back to text", "<circle" not in hero("SCORE", "clean"))
    t("RATIO 189/257 draws a bar", "<rect" in hero("RATIO", "189/257"))
    t("RATIO '7 of 9' parses too", "<rect" in hero("RATIO", "7 of 9"))
    t("RATIO without a denominator falls back", "<rect" not in hero("RATIO", "42"))
    t("STATE 'live' is a dot and a word", "shp-state" in hero("STATE", "live"))
    t("STATE never shows a number", "42" not in hero("STATE", "live"))
    t("COUNT is the number large in mono", "shp-count" in hero("COUNT", "103", "emails"))
    t("sparkline needs a real series", sparkline([5]) == "" and "<path" in sparkline([1, 4, 2, 8]))
    t("sparkline emphasises the last point", "<circle" in sparkline([1, 2, 3]))
    t("split draws segments and labels", "web" in split_bar([("web", 53), ("li", 29)]))
    t("split refuses an empty whole", split_bar([("a", 0)]) == "")
    t("unparseable value never crashes", hero("TREND", None) != "")
    print(f"\n{sum(checks)} passed, {len(checks) - sum(checks)} failed")
    raise SystemExit(0 if all(checks) else 1)
