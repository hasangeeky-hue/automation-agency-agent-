# -*- coding: utf-8 -*-
"""THE UI KIT: one design system for every OS section.

Why this module exists: the audit found six independent design systems.
e() was implemented six times, kpi() four times, empty() five times, and
40KB of CSS shipped six ways under six prefixes (ss- mc- cf- bi- sc-
ck-). Every future fix had to be made six times, which is the two-lists
bug wearing CSS. This is the ONE copy. A later gate fails any OS module
that re-implements a kit function locally.

WHAT THE KIT ENFORCES, BECAUSE THE ENGINES ALREADY DO
-----------------------------------------------------
  * Every chart names its SOURCE, or it renders a refusal instead of
    axes. A graph with no source is a picture.
  * A missing point is a GAP in the line, never a zero. Zero is a
    measurement; absence is not.
  * Status is icon plus word, never colour alone.
  * The lecture problem is solved structurally: note() renders one
    tooltip glyph, not a paragraph. The explanation survives; the wall
    of prose does not.
  * Freshness is a first-class stamp on charts and KPI rows, because
    the audit found two whole sections with zero freshness mentions.

All charts are server-rendered SVG: no chart library, no CDN, no
canvas, identical output in tests and in the browser.
"""
from __future__ import annotations

import html as _html
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ===========================================================================
# helpers (the one copy)
# ===========================================================================


def _s(x) -> str:
    return "" if x is None else str(x)


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def e(x) -> str:
    """The one HTML escaper."""
    return _html.escape(_s(x), quote=True)


def n(x, dash="not measured") -> str:
    """A number, or an honest word. Never a zero standing in for absence."""
    if x is None or x == "":
        return dash
    v = _f(x)
    if v is None:
        return e(x)
    return f"{int(v):,}" if abs(v - int(v)) < 1e-9 else f"{v:,.2f}"


def money(x, cur="EUR", dash="not measured") -> str:
    v = _f(x)
    if v is None:
        return dash
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(_s(cur).upper(), "")
    return sym + (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}")


def pct(x, dash="not measured") -> str:
    v = _f(x)
    return dash if v is None else f"{v * 100:,.1f}%"


# ===========================================================================
# tokens: ONE palette, ONE stylesheet
# ===========================================================================
TOKENS = {"bg": "#F7F8FA", "sf": "#FFFFFF", "sf2": "#F9FAFB",
          "bd": "#E5E7EB", "tx": "#111827", "tx2": "#4B5563",
          "mu": "#9CA3AF", "hu": "#2563EB", "ai": "#7C3AED",
          "ok": "#16A34A", "wa": "#D97706", "er": "#DC2626",
          "sys": "#0284C7", "pl": "#0F766E"}

#: Chart series order. Neutral first, meaning-colours only when a series
#: IS that meaning; platform colours never theme a chart.
SERIES = ("#2563EB", "#0F766E", "#7C3AED", "#0284C7", "#D97706",
          "#9CA3AF")

#: The floor the audit set: 11px minimum, muted grey only for metadata.
CSS = """<style>
.uk{--bg:#F7F8FA;--sf:#FFFFFF;--sf2:#F9FAFB;--bd:#E5E7EB;--tx:#111827;
--tx2:#4B5563;--mu:#9CA3AF;--hu:#2563EB;--ai:#7C3AED;--ok:#16A34A;
--wa:#D97706;--er:#DC2626;--sys:#0284C7;--pl:#0F766E;
color:var(--tx);font-family:Inter,system-ui,-apple-system,'Segoe UI',
sans-serif;font-size:14px;line-height:1.5}
.uk *{box-sizing:border-box}
.uk-h1{font-size:22px;font-weight:600;margin:0 0 8px}
.uk-h2{font-size:15px;font-weight:600;margin:16px 0 8px}
.uk-meta{font-size:11px;color:var(--mu)}
.uk-card{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:13px 15px;margin:0 0 10px}
.uk-kpis{display:grid;grid-template-columns:repeat(auto-fit,
minmax(140px,1fr));gap:10px;margin:0 0 12px}
.uk-kpi{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:11px 13px}
.uk-kpi>span{display:block;font-size:11px;color:var(--mu);
text-transform:uppercase;letter-spacing:.05em;margin:0 0 3px}
.uk-kpi>b{display:block;font-size:24px;font-weight:600;line-height:1.1;
font-variant-numeric:tabular-nums}
.uk-kpi>i{display:block;font-style:normal;font-size:11px;margin-top:3px}
.uk-pill{display:inline-block;font-size:11px;font-weight:500;
padding:2px 8px;border-radius:20px;border:1px solid var(--bd);
color:var(--tx2);background:var(--sf2)}
.uk-pill-ok{border-color:var(--ok);color:var(--ok)}
.uk-pill-wa{border-color:var(--wa);color:var(--wa)}
.uk-pill-er{border-color:var(--er);color:var(--er)}
.uk-pill-ai{border-color:var(--ai);color:var(--ai)}
.uk-pill-sys{border-color:var(--sys);color:var(--sys)}
.uk-ok{color:var(--ok)}.uk-wa{color:var(--wa)}.uk-er{color:var(--er)}
.uk-mu{color:var(--mu)}.uk-ai{color:var(--ai)}
.uk-i{display:inline-block;width:15px;height:15px;line-height:15px;
text-align:center;border-radius:50%;border:1px solid var(--bd);
color:var(--tx2);font-size:11px;font-style:normal;cursor:help;
margin-left:5px;vertical-align:middle}
.uk-btn{font:inherit;font-size:12px;font-weight:500;padding:6px 12px;
border-radius:8px;border:1px solid var(--bd);background:var(--sf);
color:var(--tx2);cursor:pointer;margin:0 5px 4px 0}
.uk-btn-hu{background:var(--hu);border-color:var(--hu);color:#fff}
.uk-btn-ai{background:var(--ai);border-color:var(--ai);color:#fff}
.uk-btn-er{background:var(--sf);border-color:var(--er);color:var(--er)}
.uk-tbl{width:100%;border-collapse:collapse;font-size:13px;
background:var(--sf)}
.uk-tbl th{text-align:left;font-size:11px;text-transform:uppercase;
letter-spacing:.05em;color:var(--mu);font-weight:600;padding:8px 10px;
border-bottom:1px solid var(--bd)}
.uk-tbl td{padding:8px 10px;border-bottom:1px solid var(--bd);
color:var(--tx2)}
.uk-tbl td.num{text-align:right;font-variant-numeric:tabular-nums;
color:var(--tx)}
.uk-tbl tr[data-drawer]{cursor:pointer}
.uk-tbl tr[data-drawer]:hover td{background:var(--sf2)}
.uk-scroll{overflow-x:auto;border:1px solid var(--bd);
border-radius:10px;margin:0 0 12px}
.uk-empty{border:1px dashed var(--bd);border-radius:10px;
padding:12px 14px;font-size:12px;color:var(--tx2);background:var(--sf)}
.uk-chart{background:var(--sf);border:1px solid var(--bd);
border-radius:10px;padding:12px 14px;margin:0 0 10px}
.uk-chart svg{display:block;width:100%;height:auto}
.uk-chart .uk-src{display:flex;gap:8px;justify-content:space-between;
margin-top:6px}
.uk-drawer{background:var(--sf);border:1px solid var(--hu);
border-radius:10px;padding:12px 14px;margin:8px 0;display:none}
.uk-drawer.on{display:block}
.uk-badge{display:inline-block;min-width:16px;text-align:center;
font-size:11px;padding:1px 5px;border-radius:9px;
background:rgba(148,163,184,.18);color:var(--tx2);margin-left:6px;
font-variant-numeric:tabular-nums}
</style>"""

JS = """<script>
window.OS = window.OS || {};
OS.drawer = function(id){var d=document.getElementById(id);
  if(d){d.classList.toggle('on');}};
</script>"""


# ===========================================================================
# components (the one copy)
# ===========================================================================
def note(text) -> str:
    """The lecture problem, solved: one glyph, hover for the reason."""
    return "<span class='uk-i' title='" + e(text) + "'>i</span>"


def pill(text, tone="") -> str:
    return ("<span class='uk-pill" + (" uk-pill-" + tone if tone else "")
            + "'>" + e(text) + "</span>")


_MARK = {"HEALTHY": ("● Healthy", "ok"), "DEGRADED": ("▲ Degraded", "wa"),
         "FAILED": ("● Failed", "er"), "RUNNING": ("◌ Running", "sys"),
         "STALLED": ("▲ Stalled", "wa"), "OFFLINE": ("● Offline", "er"),
         "DISABLED": ("○ Disabled", ""), "UNKNOWN": ("? Unknown", ""),
         "PASS": ("● Pass", "ok"), "WARNING": ("▲ Warning", "wa"),
         "FAIL": ("● Fail", "er"), "GOOD": ("● Good", "ok"),
         "BAD": ("● Bad", "er"), "OK": ("● OK", "ok")}


def status(state) -> str:
    """Icon plus word, never colour alone."""
    st = _s(state).upper() or "UNKNOWN"
    label, tone = _MARK.get(st, ("? " + st.title(), ""))
    return pill(label, tone)


def kpi(label, value, *, delta=None, verdict="", freshness="",
        why="") -> str:
    """One scorecard. Delta coloured by VERDICT (the caller judges
    polarity; the kit never assumes higher is good)."""
    tone = {"GOOD": "uk-ok", "BAD": "uk-er",
            "NEUTRAL": "uk-mu"}.get(_s(verdict).upper(), "uk-mu")
    d = _f(delta)
    return ("<div class='uk-kpi'><span>" + e(label)
            + (note(why) if why else "") + "</span><b>" + value + "</b>"
            + ("<i class='" + tone + "'>"
               + ("+" if d > 0 else "") + n(d, "") + "%</i>"
               if d is not None else
               "<i class='uk-mu'>no comparison</i>")
            + ("<i class='uk-meta'>" + e(freshness) + "</i>"
               if freshness else "")
            + "</div>")


def empty(title, why, *, cta="", onclick="") -> str:
    """Compact: one line and a glyph, not a wall."""
    return ("<div class='uk-empty'><b>" + e(title) + "</b>" + note(why)
            + ((" <button class='uk-btn uk-btn-hu' onclick=\""
                + e(onclick) + "\">" + e(cta) + "</button>")
               if cta else "") + "</div>")


def button(label, kind="", *, onclick="") -> str:
    k = {"human": "uk-btn-hu", "ai": "uk-btn-ai",
         "danger": "uk-btn-er"}.get(_s(kind).lower(), "")
    mark = "✦ " if k == "uk-btn-ai" else ""
    return ("<button class='uk-btn " + k + "'"
            + (" onclick=\"" + e(onclick) + "\"" if onclick else "")
            + ">" + mark + e(label) + "</button>")


def badge(count) -> str:
    """The old dashboard's tab count badge, kept."""
    return "<span class='uk-badge'>" + n(count, "0") + "</span>"


def table(headers, rows, *, drawer_prefix="") -> str:
    """One table. A row given a drawer id becomes clickable."""
    h = "".join("<th>" + e(x) + "</th>" for x in headers)
    body = []
    for i, r in enumerate(rows):
        cells, did = r if isinstance(r, tuple) else (r, None)
        tds = "".join(
            "<td class='num'>" + c[1] + "</td>"
            if isinstance(c, tuple) else "<td>" + c + "</td>"
            for c in cells)
        attr = (" data-drawer onclick=\"OS.drawer('" + drawer_prefix
                + _s(did) + "')\"" if did else "")
        body.append("<tr" + attr + ">" + tds + "</tr>")
    return ("<div class='uk-scroll'><table class='uk-tbl'><thead><tr>"
            + h + "</tr></thead><tbody>" + "".join(body)
            + "</tbody></table></div>")


def drawer(did, inner) -> str:
    return ("<div class='uk-drawer' id='" + e(did) + "'>" + inner
            + "</div>")


def runbar(actions) -> str:
    """(label, kind, onclick) triples. The old wired-runbar pattern."""
    return ("<div style='display:flex;flex-wrap:wrap;gap:2px;"
            "margin:0 0 10px'>"
            + "".join(button(l, k, onclick=oc) for l, k, oc in actions)
            + "</div>")


# ===========================================================================
# charts: server SVG, honest by construction
# ===========================================================================
_W, _H, _PAD = 560, 150, 8


def _frame(inner, *, title, source, freshness, vb_h=_H,
           aria) -> str:
    """Every chart ships inside this: title, then the SVG, then the
    source and freshness line. No source, no chart; the refusal happens
    in each chart function before this is reached."""
    return ("<div class='uk-chart'>"
            + ("<p class='uk-h2' style='margin:0 0 8px'>" + e(title)
               + "</p>" if title else "")
            + "<svg viewBox='0 0 " + str(_W) + " " + str(vb_h)
            + "' role='img' aria-label='" + e(aria)
            + "' preserveAspectRatio='xMidYMid meet'>" + inner + "</svg>"
            + "<div class='uk-src'><span class='uk-meta'>Source: "
            + e(source) + "</span><span class='uk-meta'>"
            + e(freshness or "freshness not stated") + "</span></div>"
            + "</div>")


def _refuse(title, why) -> str:
    return ("<div class='uk-chart'><p class='uk-h2' "
            "style='margin:0 0 6px'>" + e(title) + "</p>"
            + "<div class='uk-empty'>" + e(why) + "</div></div>")


def _scale(vals, lo=None, hi=None):
    known = [v for v in vals if v is not None]
    if not known:
        return 0.0, 1.0
    mn = min(known) if lo is None else lo
    mx = max(known) if hi is None else hi
    if mx == mn:
        mx = mn + 1
    return mn, mx


def _grid(y_count=3, h=_H) -> str:
    out = []
    for i in range(1, y_count + 1):
        y = _PAD + (h - 2 * _PAD) * i / (y_count + 1)
        out.append("<line x1='" + str(_PAD) + "' y1='" + f"{y:.1f}"
                   + "' x2='" + str(_W - _PAD) + "' y2='" + f"{y:.1f}"
                   + "' stroke='#E5E7EB' stroke-width='1'/>")
    return "".join(out)


def _poly(vals, mn, mx, colour, *, width=2, h=_H) -> str:
    """Polyline segments that BREAK at None. A gap is drawn as a gap."""
    span = max(len(vals) - 1, 1)
    segs, cur = [], []
    for i, v in enumerate(vals):
        if v is None:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
            continue
        x = _PAD + (_W - 2 * _PAD) * i / span
        y = h - _PAD - (h - 2 * _PAD) * ((v - mn) / (mx - mn))
        cur.append(f"{x:.1f},{y:.1f}")
    if len(cur) > 1:
        segs.append(cur)
    out = ["<polyline points='" + " ".join(s) + "' fill='none' stroke='"
           + colour + "' stroke-width='" + str(width)
           + "' stroke-linejoin='round'/>" for s in segs]
    # lone points still render as dots
    for i, v in enumerate(vals):
        if v is not None and (
                (i == 0 or vals[i - 1] is None)
                and (i == len(vals) - 1 or vals[i + 1] is None)):
            x = _PAD + (_W - 2 * _PAD) * i / span
            y = h - _PAD - (h - 2 * _PAD) * ((v - mn) / (mx - mn))
            out.append("<circle cx='" + f"{x:.1f}" + "' cy='"
                       + f"{y:.1f}" + "' r='2.5' fill='" + colour + "'/>")
    return "".join(out)


def sparkline(values, *, source, width=120, height=28) -> str:
    """Inline trend. Small, honest: gaps stay gaps."""
    vals = [_f(v) for v in list(values or [])]
    if not any(v is not None for v in vals):
        return "<span class='uk-meta'>no trend data</span>"
    mn, mx = _scale(vals)
    span = max(len(vals) - 1, 1)
    pts, segs, cur = [], [], []
    for i, v in enumerate(vals):
        if v is None:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
            continue
        x = 2 + (width - 4) * i / span
        y = height - 3 - (height - 6) * ((v - mn) / (mx - mn))
        cur.append(f"{x:.1f},{y:.1f}")
    if len(cur) > 1:
        segs.append(cur)
    body = "".join("<polyline points='" + " ".join(s)
                   + "' fill='none' stroke='#2563EB' "
                   "stroke-width='1.5'/>" for s in segs)
    return ("<svg width='" + str(width) + "' height='" + str(height)
            + "' viewBox='0 0 " + str(width) + " " + str(height)
            + "' role='img' aria-label='trend, source " + e(source)
            + "' style='vertical-align:middle'>" + body + "</svg>")


def line(series, *, title, source, freshness="", labels=None,
         compare=None, compare_label="previous period") -> str:
    """The primary time-series. Compare renders muted behind current."""
    if not _s(source):
        return _refuse(title, "this chart has no source, so it does not "
                              "render. A graph with no source is a "
                              "picture.")
    vals = [_f(v) for v in list(series or [])]
    cmp_vals = [_f(v) for v in list(compare or [])]
    if not any(v is not None for v in vals):
        return _refuse(title, "no measured points in this window; the "
                              "axis is not drawn over nothing")
    mn, mx = _scale(vals + [v for v in cmp_vals if v is not None])
    gaps = sum(1 for v in vals if v is None)
    inner = _grid()
    if any(v is not None for v in cmp_vals):
        inner += _poly(cmp_vals, mn, mx, "#C7CDD6", width=1.5)
    inner += _poly(vals, mn, mx, "#2563EB", width=2)
    # endpoint emphasis + value
    last_i = max(i for i, v in enumerate(vals) if v is not None)
    span = max(len(vals) - 1, 1)
    lx = _PAD + (_W - 2 * _PAD) * last_i / span
    ly = _H - _PAD - (_H - 2 * _PAD) * ((vals[last_i] - mn) / (mx - mn))
    inner += ("<circle cx='" + f"{lx:.1f}" + "' cy='" + f"{ly:.1f}"
              + "' r='3.5' fill='#2563EB'/>"
              + "<text x='" + f"{min(lx, _W - 70):.1f}" + "' y='"
              + f"{max(ly - 7, 11):.1f}"
              + "' font-size='11' fill='#111827' "
              "font-family='inherit'>" + e(n(vals[last_i])) + "</text>")
    fresh = (freshness + (" · " + str(gaps) + " gap(s) shown as gaps, "
                          "not zeros" if gaps else "")
             ) if freshness else (str(gaps) + " gap(s) shown as gaps"
                                  if gaps else "")
    return _frame(inner, title=title, source=source, freshness=fresh,
                  aria=title + ", line chart, source " + source)


def hbar(items, *, title, source, freshness="", value_fmt=n) -> str:
    """Horizontal bars: (label, value) pairs, biggest first."""
    if not _s(source):
        return _refuse(title, "no source, no chart")
    rows = [(str(a), _f(b)) for a, b in list(items or [])]
    known = [r for r in rows if r[1] is not None]
    if not known:
        return _refuse(title, "nothing measured to compare")
    known.sort(key=lambda r: -r[1])
    mx = max(abs(v) for _l, v in known) or 1
    bh, gap = 20, 8
    h = _PAD * 2 + len(known) * (bh + gap)
    out = []
    for i, (label, v) in enumerate(known):
        y = _PAD + i * (bh + gap)
        w = (_W - 190) * abs(v) / mx
        out.append(
            "<text x='" + str(_PAD) + "' y='" + str(y + 14)
            + "' font-size='11' fill='#4B5563' "
            "font-family='inherit'>" + e(label[:24]) + "</text>"
            + "<rect x='150' y='" + str(y) + "' width='"
            + f"{max(w, 1):.1f}" + "' height='" + str(bh)
            + "' rx='4' fill='" + SERIES[0] + "'/>"
            + "<text x='" + f"{155 + w:.1f}" + "' y='" + str(y + 14)
            + "' font-size='11' fill='#111827' "
            "font-family='inherit'>" + e(value_fmt(v)) + "</text>")
    skipped = len(rows) - len(known)
    fr = freshness + (" · " + str(skipped) + " unmeasured row(s) "
                      "left out" if skipped else "")
    return _frame("".join(out), title=title, source=source,
                  freshness=fr, vb_h=h,
                  aria=title + ", bar chart, source " + source)


def stacked(labels, series, *, title, source, freshness="") -> str:
    """Stacked columns. series = [(name, [values...]), ...]."""
    if not _s(source):
        return _refuse(title, "no source, no chart")
    labs = [str(x) for x in list(labels or [])]
    ser = [(str(nm), [_f(v, 0) or 0 for v in vs]) for nm, vs in
           list(series or [])]
    if not labs or not ser:
        return _refuse(title, "nothing to stack")
    totals = [sum(vs[i] for _n2, vs in ser if i < len(vs))
              for i in range(len(labs))]
    mx = max(totals) or 1
    cw = (_W - 2 * _PAD) / len(labs)
    bw = min(cw * 0.6, 46)
    out = [_grid()]
    for i in range(len(labs)):
        x = _PAD + cw * i + (cw - bw) / 2
        y = _H - _PAD - 14
        for k, (_name, vs) in enumerate(ser):
            v = vs[i] if i < len(vs) else 0
            hh = (_H - 2 * _PAD - 14) * v / mx
            y -= hh
            out.append("<rect x='" + f"{x:.1f}" + "' y='" + f"{y:.1f}"
                       + "' width='" + f"{bw:.1f}" + "' height='"
                       + f"{max(hh, 0):.1f}" + "' fill='"
                       + SERIES[k % len(SERIES)] + "'/>")
        out.append("<text x='" + f"{x + bw / 2:.1f}" + "' y='"
                   + str(_H - 4) + "' font-size='10' fill='#9CA3AF' "
                   "text-anchor='middle' font-family='inherit'>"
                   + e(labs[i][:8]) + "</text>")
    legend = " ".join("<tspan fill='" + SERIES[k % len(SERIES)]
                      + "'>■</tspan> " + e(nm)
                      for k, (nm, _v) in enumerate(ser))
    out.append("<text x='" + str(_PAD) + "' y='11' font-size='10' "
               "fill='#4B5563' font-family='inherit'>" + legend
               + "</text>")
    return _frame("".join(out), title=title, source=source,
                  freshness=freshness,
                  aria=title + ", stacked bars, source " + source)


def scatter(points, *, title, source, freshness="", x_label="",
            y_label="") -> str:
    """(x, y, label) triples. The efficiency-quadrant chart."""
    if not _s(source):
        return _refuse(title, "no source, no chart")
    pts = [(_f(a), _f(b), str(c)) for a, b, c in list(points or [])]
    known = [p for p in pts if p[0] is not None and p[1] is not None]
    if not known:
        return _refuse(title, "no point has both coordinates measured")
    xmn, xmx = _scale([p[0] for p in known])
    ymn, ymx = _scale([p[1] for p in known])
    out = [_grid()]
    for x, y, lab in known:
        px = _PAD + 30 + (_W - 2 * _PAD - 40) * ((x - xmn) / (xmx - xmn))
        py = _H - _PAD - 14 - (_H - 2 * _PAD - 20) * (
            (y - ymn) / (ymx - ymn))
        out.append("<circle cx='" + f"{px:.1f}" + "' cy='"
                   + f"{py:.1f}" + "' r='4' fill='" + SERIES[0]
                   + "' fill-opacity='.75'/>"
                   + "<text x='" + f"{px + 6:.1f}" + "' y='"
                   + f"{py + 3:.1f}" + "' font-size='10' "
                   "fill='#4B5563' font-family='inherit'>"
                   + e(lab[:14]) + "</text>")
    out.append("<text x='" + str(_W - _PAD) + "' y='" + str(_H - 3)
               + "' font-size='10' fill='#9CA3AF' text-anchor='end' "
               "font-family='inherit'>" + e(x_label) + " →</text>"
               "<text x='10' y='11' font-size='10' fill='#9CA3AF' "
               "font-family='inherit'>↑ " + e(y_label) + "</text>")
    dropped = len(pts) - len(known)
    fr = freshness + (" · " + str(dropped) + " point(s) missing a "
                      "coordinate, left out" if dropped else "")
    return _frame("".join(out), title=title, source=source, freshness=fr,
                  aria=title + ", scatter, source " + source)


def donut(parts, *, title, source, freshness="", value_fmt=n) -> str:
    """Share of a whole: (label, value) pairs."""
    if not _s(source):
        return _refuse(title, "no source, no chart")
    rows = [(str(a), _f(b)) for a, b in list(parts or [])]
    known = [(a, v) for a, v in rows if v is not None and v > 0]
    if not known:
        return _refuse(title, "no measured parts")
    total = sum(v for _a, v in known)
    cx, cy, r, sw = 80, _H / 2, 48, 22
    import math
    circ = 2 * math.pi * r
    out, acc = [], 0.0
    for k, (label, v) in enumerate(sorted(known, key=lambda x: -x[1])):
        frac = v / total
        out.append("<circle cx='" + str(cx) + "' cy='" + f"{cy:.1f}"
                   + "' r='" + str(r) + "' fill='none' stroke='"
                   + SERIES[k % len(SERIES)] + "' stroke-width='"
                   + str(sw) + "' stroke-dasharray='"
                   + f"{frac * circ:.1f} {circ:.1f}"
                   + "' stroke-dashoffset='" + f"{-acc * circ:.1f}"
                   + "' transform='rotate(-90 " + str(cx) + " "
                   + f"{cy:.1f}" + ")'/>")
        acc += frac
    for k, (label, v) in enumerate(sorted(known, key=lambda x: -x[1])):
        y = 22 + k * 18
        if y > _H - 6:
            break
        out.append("<rect x='170' y='" + str(y - 9)
                   + "' width='9' height='9' rx='2' fill='"
                   + SERIES[k % len(SERIES)] + "'/>"
                   "<text x='185' y='" + str(y) + "' font-size='11' "
                   "fill='#4B5563' font-family='inherit'>"
                   + e(label[:20]) + "  " + e(value_fmt(v)) + " ("
                   + f"{v / total * 100:.0f}" + "%)</text>")
    return _frame("".join(out), title=title, source=source,
                  freshness=freshness,
                  aria=title + ", share chart, source " + source)


def waterfall(start_label, start_value, steps, *, title, source,
              freshness="", end_label="Result") -> str:
    """The margin bridge: start, minus named steps, to the result.
    Refuses a missing start; a missing STEP is listed as not supplied
    rather than drawn as zero."""
    if not _s(source):
        return _refuse(title, "no source, no chart")
    sv = _f(start_value)
    if sv is None:
        return _refuse(title, "the starting value is not measured")
    rows = [(str(a), _f(b)) for a, b in list(steps or [])]
    known = [(a, v) for a, v in rows if v is not None]
    missing = [a for a, v in rows if v is None]
    end = sv - sum(v for _a, v in known)
    bars = [(start_label, sv, sv, "start")]
    run = sv
    for a, v in known:
        bars.append((a, v, run - v, "step"))
        run -= v
    bars.append((end_label, end, end, "end"))
    mx = max(sv, end, 1)
    cw = (_W - 2 * _PAD) / len(bars)
    bw = min(cw * 0.62, 58)
    out = [_grid()]
    for i, (label, v, top, kind) in enumerate(bars):
        x = _PAD + cw * i + (cw - bw) / 2
        if kind == "start" or kind == "end":
            hh = (_H - 2 * _PAD - 16) * max(v, 0) / mx
            y = _H - _PAD - 14 - hh
            col = SERIES[0] if kind == "start" else TOKENS["ok"]
        else:
            hh = (_H - 2 * _PAD - 16) * abs(v) / mx
            y = _H - _PAD - 14 - (_H - 2 * _PAD - 16) * (
                (top + v) / mx) if False else \
                _H - _PAD - 14 - (_H - 2 * _PAD - 16) * ((top + v) / mx)
            col = TOKENS["er"]
        out.append("<rect x='" + f"{x:.1f}" + "' y='" + f"{y:.1f}"
                   + "' width='" + f"{bw:.1f}" + "' height='"
                   + f"{max(hh, 1):.1f}" + "' rx='3' fill='" + col
                   + "' fill-opacity='" + ("1" if kind != "step"
                                           else ".8") + "'/>"
                   # The value, on the chart. A bridge whose numbers
                   # cannot be read is a decoration; the gate caught
                   # this missing entirely in the first version.
                   + "<text x='" + f"{x + bw / 2:.1f}" + "' y='"
                   + f"{max(y - 4, 10):.1f}"
                   + "' font-size='10' fill='#111827' "
                   "text-anchor='middle' font-family='inherit'>"
                   + e(n(v)) + "</text>"
                   + "<text x='" + f"{x + bw / 2:.1f}" + "' y='"
                   + str(_H - 3) + "' font-size='10' fill='#9CA3AF' "
                   "text-anchor='middle' font-family='inherit'>"
                   + e(label[:9]) + "</text>")
    fr = freshness + ((" · not supplied and not deducted: "
                       + ", ".join(missing)) if missing else "")
    return _frame("".join(out), title=title, source=source, freshness=fr,
                  aria=title + ", waterfall, source " + source)


# ===========================================================================
# the subsection template (Data-Studio pattern)
# ===========================================================================
def subsection(title, *, kpis="", chart="", breakdown="",
               table_html="", freshness="") -> str:
    """scorecards -> primary chart -> breakdown -> table. The one shape
    every subsection converts to in Round 2."""
    return ("<div class='uk'><p class='uk-h2'>" + e(title)
            + ("<span class='uk-meta' style='float:right'>"
               + e(freshness) + "</span>" if freshness else "")
            + "</p>"
            + ("<div class='uk-kpis'>" + kpis + "</div>" if kpis else "")
            + chart + breakdown + table_html + "</div>")


#: Everything an OS module may NOT re-implement once adopted. The
#: verify suite greps for local defs of these names outside this file.
KIT_EXPORTS = ("e", "n", "money", "pct", "kpi", "pill", "status",
               "empty", "button", "badge", "table", "drawer", "runbar",
               "note", "sparkline", "line", "hbar", "stacked", "scatter",
               "donut", "waterfall", "subsection")
