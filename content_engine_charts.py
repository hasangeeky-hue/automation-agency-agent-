"""
content_engine_charts.py
============================================================================
The Business Operating System visual language — hand-drawn inline SVG charts,
no libraries, works offline on the VPS. Each function returns an SVG string (or
"" when there's no data, so the caller can show an honest empty state).

Visual-by-data map (from the BOS brief):
  revenue trend -> confband/line   pipeline -> funnel      attribution -> sankey
  rankings -> heatmap              keyword move -> bump     clicks -> treemap
  risk -> matrix                   AI workflow -> digraph   infra -> statusgrid
  profit vs cost -> waterfall      retention -> cohort      workload -> gantt
============================================================================
"""
from __future__ import annotations

_INK = "#EDF1FB"
_MUT = "#8E9BBE"
_LINE = "#1B2640"
_PAL = ["#4C8DFF", "#2FE3D2", "#8B7CFF", "#F5B14C", "#3FD98B", "#FF6B93", "#5A7BE8"]


def _e(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _svg(w, h, inner, defs=""):
    return (f"<svg viewBox='0 0 {w} {h}' width='100%' style='max-width:{w}px;height:auto' "
            f"xmlns='http://www.w3.org/2000/svg'>{defs}{inner}</svg>")


_GLOW = ("<defs><filter id='cg' x='-60%' y='-60%' width='220%' height='220%'>"
         "<feGaussianBlur stdDeviation='3.2' result='b'/><feMerge>"
         "<feMergeNode in='b'/><feMergeNode in='SourceGraphic'/></feMerge></filter></defs>")


# --- Glowing "model" architecture (the rendered neural-net look) -------------
def neural(layers, labels=None):
    """A glowing multi-layer node network — the AGENT NETWORK rendered like the
    reference model diagram. layers=[node counts]; nodes glow, edges are faint,
    signal pulses travel across. Pure SVG (no libs)."""
    layers = [max(1, int(n)) for n in layers]
    if len(layers) < 2:
        return ""
    W, H, pad = 640, 400, 46
    nL = len(layers)
    colw = (W - 2 * pad) / (nL - 1)
    pos = []
    for li, cnt in enumerate(layers):
        x = pad + li * colw
        ys = [pad + (H - 2 * pad) * ((i + 0.5) / cnt) for i in range(cnt)]
        pos.append([(x, y) for y in ys])

    def lcol(li):
        return "#4C8DFF" if li == 0 else ("#3FD98B" if li == nL - 1 else "#2FE3D2")
    edges = ""
    pulses = ""
    for li in range(nL - 1):
        for a in pos[li]:
            for b in pos[li + 1]:
                edges += (f"<line x1='{a[0]:.0f}' y1='{a[1]:.0f}' x2='{b[0]:.0f}' y2='{b[1]:.0f}' "
                          f"stroke='{lcol(li)}' stroke-width='0.7' opacity='0.16'/>")
        # a couple of animated signal pulses per gap
        import_i = 0
        for k in range(min(2, len(pos[li]))):
            a = pos[li][k % len(pos[li])]
            b = pos[li + 1][k % len(pos[li + 1])]
            dur = 1.6 + (li + k) * 0.25
            pulses += (f"<circle r='2.6' fill='{lcol(li+1)}' filter='url(#cg)'>"
                       f"<animate attributeName='cx' from='{a[0]:.0f}' to='{b[0]:.0f}' dur='{dur:.2f}s' repeatCount='indefinite'/>"
                       f"<animate attributeName='cy' from='{a[1]:.0f}' to='{b[1]:.0f}' dur='{dur:.2f}s' repeatCount='indefinite'/>"
                       f"<animate attributeName='opacity' values='0;1;1;0' dur='{dur:.2f}s' repeatCount='indefinite'/></circle>")
    nodes = ""
    for li, layer in enumerate(pos):
        c = lcol(li)
        for (x, y) in layer:
            nodes += (f"<circle cx='{x:.0f}' cy='{y:.0f}' r='8' fill='#0B1220' stroke='{c}' stroke-width='2' filter='url(#cg)'/>"
                      f"<circle cx='{x:.0f}' cy='{y:.0f}' r='3.4' fill='{c}'/>")
    labs = ""
    if labels:
        for li, lab in enumerate(labels[:nL]):
            labs += (f"<text x='{pad + li*colw:.0f}' y='{H-14}' text-anchor='middle' fill='{_MUT}' "
                     f"font-size='10' font-weight='600'>{_e(lab)}</text>")
    return _svg(W, H, edges + nodes + pulses + labs, defs=_GLOW)


# --- Grouped vertical bars (Precision/Recall style) ------------------------
def vbars(groups, series):
    """groups=['A','B',...]; series=[(name,[values],color)]. Grouped columns."""
    if not groups or not series:
        return ""
    W, H, pad = 560, 300, 34
    ng, ns = len(groups), len(series)
    mx = max((max(v for v in s[1]) for s in series), default=1) or 1
    gw = (W - 2 * pad) / ng
    bw = gw * 0.7 / ns
    inner = f"<line x1='{pad}' y1='{H-pad}' x2='{W-pad}' y2='{H-pad}' stroke='{_LINE}'/>"
    for gi, g in enumerate(groups):
        gx = pad + gi * gw + gw * 0.15
        for si, (nm, vals, col) in enumerate(series):
            v = vals[gi] if gi < len(vals) else 0
            bh = (v / mx) * (H - 2 * pad)
            x = gx + si * bw
            inner += (f"<rect x='{x:.1f}' y='{H-pad-bh:.1f}' width='{bw*0.82:.1f}' height='{bh:.1f}' rx='3' fill='{col}'/>"
                      f"<text x='{x+bw*0.4:.1f}' y='{H-pad-bh-4:.1f}' text-anchor='middle' fill='{_MUT}' font-size='8'>{int(v)}</text>")
        inner += f"<text x='{gx+gw*0.35:.1f}' y='{H-pad+14:.0f}' text-anchor='middle' fill='{_MUT}' font-size='9'>{_e(g)[:8]}</text>"
    leg = " ".join(f"<span style='color:{c}'>● {_e(n)}</span>" for n, _v, c in series)
    return _svg(W, H, inner) + f"<div class='dim' style='font-size:11px;margin-top:4px'>{leg}</div>"


# --- Multi-segment donut ---------------------------------------------------
def ring(segments, center=""):
    """segments=[(label,value,color)]. Donut with a centre label."""
    segments = [(l, float(v), c) for l, v, c in segments if v]
    if not segments:
        return ""
    import math
    W = H = 220
    cx = cy = 110
    r = 78
    total = sum(v for _, v, _ in segments) or 1
    inner = f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='#141d31' stroke-width='20'/>"
    a0 = -90
    circ = 2 * math.pi * r
    off = 0
    for l, v, c in segments:
        frac = v / total
        dash = frac * circ
        inner += (f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='{c}' stroke-width='20' "
                  f"stroke-dasharray='{dash:.1f} {circ-dash:.1f}' stroke-dashoffset='{-off:.1f}' "
                  f"transform='rotate(-90 {cx} {cy})'/>")
        off += dash
    inner += (f"<text x='{cx}' y='{cy-2}' text-anchor='middle' fill='{_INK}' font-size='22' font-weight='800'>{_e(center)}</text>"
              f"<text x='{cx}' y='{cy+16}' text-anchor='middle' fill='{_MUT}' font-size='9'>total {int(total)}</text>")
    leg = " ".join(f"<span style='color:{c}'>● {_e(l)}</span>" for l, _v, c in segments)
    return _svg(W, H, inner) + f"<div class='dim' style='font-size:11px;margin-top:4px;text-align:center'>{leg}</div>"


# --- Multi-series line chart ------------------------------------------------
def lines(series, ymax=None):
    """series=[(name,[y...],color)]. Smooth-ish multi-line with legend + glow."""
    series = [(n, [float(x) for x in ys], c) for n, ys, c in series if ys]
    if not series:
        return ""
    W, H, pad = 560, 240, 26
    n = max(len(ys) for _, ys, _ in series)
    mx = ymax or max((max(ys) for _, ys, _ in series), default=1) or 1

    def X(i):
        return pad + i / max(n - 1, 1) * (W - 2 * pad)

    def Y(v):
        return pad + (1 - v / mx) * (H - 2 * pad)
    grid = "".join(f"<line x1='{pad}' y1='{pad + k*(H-2*pad)/4:.0f}' x2='{W-pad}' y2='{pad + k*(H-2*pad)/4:.0f}' stroke='{_LINE}' opacity='.5'/>" for k in range(5))
    paths = ""
    for nm, ys, col in series:
        d = " ".join(f"{'M' if i==0 else 'L'}{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(ys))
        paths += (f"<path d='{d}' fill='none' stroke='{col}' stroke-width='2.5' filter='url(#cg)'/>"
                  f"<circle cx='{X(len(ys)-1):.1f}' cy='{Y(ys[-1]):.1f}' r='3.5' fill='{col}'/>")
    leg = " ".join(f"<span style='color:{c}'>● {_e(n)}</span>" for n, _y, c in series)
    return _svg(W, H, grid + paths, defs=_GLOW) + f"<div class='dim' style='font-size:11px;margin-top:4px'>{leg}</div>"


# --- Infrastructure: status grid ------------------------------------------
def statusgrid(items):
    """items: [(label, ok_bool_or_None, detail)]. Green/amber/red tiles."""
    if not items:
        return ""
    cols = 3
    cw, ch, gap = 150, 52, 8
    rows = (len(items) + cols - 1) // cols
    w = cols * cw + (cols - 1) * gap
    h = rows * ch + (rows - 1) * gap
    cells = ""
    for i, (label, ok, detail) in enumerate(items):
        x = (i % cols) * (cw + gap)
        y = (i // cols) * (ch + gap)
        col = "#3FD98B" if ok else ("#F5B14C" if ok is None else "#FF6B93")
        cells += (f"<rect x='{x}' y='{y}' width='{cw}' height='{ch}' rx='9' fill='#0F1626' stroke='{col}' stroke-opacity='.6'/>"
                  f"<circle cx='{x+14}' cy='{y+18}' r='5' fill='{col}'/>"
                  f"<text x='{x+26}' y='{y+22}' fill='{_INK}' font-size='12' font-weight='600'>{_e(label)[:16]}</text>"
                  f"<text x='{x+12}' y='{y+40}' fill='{_MUT}' font-size='10'>{_e(detail)[:22]}</text>")
    return _svg(w, h, cells)


# --- Risk: 2x2 (likelihood x impact) matrix --------------------------------
def risk_matrix(items):
    """items: [(label, likelihood 1-3, impact 1-3)]."""
    if not items:
        return ""
    W = H = 300
    pad = 34
    cell = (W - pad) / 3
    inner = f"<rect x='{pad}' y='0' width='{W-pad}' height='{H-pad}' fill='none'/>"
    zone = [["#20351f", "#3a3a1e", "#4a2330"], ["#33331e", "#4a2330", "#5a2130"], ["#4a2330", "#5a2130", "#6a1a2f"]]
    for r in range(3):
        for c in range(3):
            x = pad + c * cell
            y = (2 - r) * cell
            inner += f"<rect x='{x}' y='{y}' width='{cell}' height='{cell}' fill='{zone[r][c]}' stroke='{_LINE}'/>"
    inner += (f"<text x='{pad-6}' y='{H-pad+16}' fill='{_MUT}' font-size='10' transform='rotate(-90 {pad-6} {H-pad})'>"
              f"Impact →</text>"
              f"<text x='{pad+4}' y='{H-12}' fill='{_MUT}' font-size='10'>Likelihood →</text>")
    for i, (label, lk, im) in enumerate(items[:8]):
        lk = max(1, min(3, int(lk))); im = max(1, min(3, int(im)))
        x = pad + (lk - 1) * cell + cell / 2
        y = (3 - im) * cell + cell / 2
        col = _PAL[i % len(_PAL)]
        inner += (f"<circle cx='{x}' cy='{y}' r='6' fill='{col}'/>"
                  f"<text x='{x+9}' y='{y+4}' fill='{_INK}' font-size='10'>{_e(label)[:14]}</text>")
    return _svg(W, H, inner)


# --- Finance: waterfall (profit vs cost) -----------------------------------
def waterfall(steps):
    """steps: [(label, delta)] — positives up, negatives down, running total."""
    steps = [(l, float(v)) for l, v in steps if l]
    if not steps:
        return ""
    W, H, pad = 460, 200, 26
    run = 0
    pts = []
    for l, d in steps:
        pts.append((l, run, run + d, d))
        run += d
    hi = max([max(a, b) for _, a, b, _ in pts] + [0]) or 1
    lo = min([min(a, b) for _, a, b, _ in pts] + [0])
    span = (hi - lo) or 1
    bw = (W - 2 * pad) / len(pts)

    def yy(v):
        return pad + (hi - v) / span * (H - 2 * pad)
    inner = f"<line x1='{pad}' y1='{yy(0)}' x2='{W-pad}' y2='{yy(0)}' stroke='{_LINE}'/>"
    for i, (l, a, b, d) in enumerate(pts):
        x = pad + i * bw + bw * 0.15
        col = "#3FD98B" if d >= 0 else "#FF6B93"
        y0, y1 = yy(max(a, b)), yy(min(a, b))
        inner += (f"<rect x='{x}' y='{y0}' width='{bw*0.7}' height='{max(2,y1-y0)}' rx='3' fill='{col}'/>"
                  f"<text x='{x+bw*0.35}' y='{H-8}' text-anchor='middle' fill='{_MUT}' font-size='9'>{_e(l)[:8]}</text>")
    return _svg(W, H, inner)


# --- Customer: retention cohort grid ---------------------------------------
def cohort(labels, grid):
    """labels: row names; grid: [[pct 0-100,...],...] left=recent."""
    if not grid:
        return ""
    W = 460
    rows = len(grid)
    cols = max(len(r) for r in grid)
    cw = (W - 90) / max(cols, 1)
    chh = 26
    H = rows * chh + 24
    inner = ""
    for c in range(cols):
        inner += f"<text x='{90 + c*cw + cw/2}' y='14' text-anchor='middle' fill='{_MUT}' font-size='9'>W{c}</text>"
    for r, row in enumerate(grid):
        y = 22 + r * chh
        inner += f"<text x='0' y='{y+16}' fill='{_INK}' font-size='10'>{_e(labels[r] if r < len(labels) else '')[:12]}</text>"
        for c, v in enumerate(row):
            x = 90 + c * cw
            a = max(0.06, min(1, (v or 0) / 100))
            inner += (f"<rect x='{x}' y='{y}' width='{cw-3}' height='{chh-4}' rx='4' fill='#2FE3D2' fill-opacity='{a:.2f}'/>"
                      f"<text x='{x+cw/2}' y='{y+16}' text-anchor='middle' fill='{_INK}' font-size='9'>{int(v)}</text>")
    return _svg(W, H, inner)


# --- SEO: rankings heatmap -------------------------------------------------
def heatmap(row_labels, col_labels, matrix):
    """matrix[r][c] = value 0-100 (e.g. visibility). Green good."""
    if not matrix:
        return ""
    W = 460
    cols = len(col_labels)
    cw = (W - 120) / max(cols, 1)
    chh = 24
    H = len(matrix) * chh + 26
    inner = ""
    for c, cl in enumerate(col_labels):
        inner += f"<text x='{120 + c*cw + cw/2}' y='14' text-anchor='middle' fill='{_MUT}' font-size='9'>{_e(cl)[:6]}</text>"
    for r, row in enumerate(matrix):
        y = 22 + r * chh
        inner += f"<text x='0' y='{y+15}' fill='{_INK}' font-size='10'>{_e(row_labels[r] if r < len(row_labels) else '')[:16]}</text>"
        for c, v in enumerate(row):
            x = 120 + c * cw
            a = max(0.08, min(1, (v or 0) / 100))
            inner += f"<rect x='{x}' y='{y}' width='{cw-3}' height='{chh-4}' rx='3' fill='#3FD98B' fill-opacity='{a:.2f}'/>"
    return _svg(W, H, inner)


# --- Marketing attribution: sankey (2 layers) ------------------------------
def sankey(flows):
    """flows: [(source, target, value)]. Curved ribbons L->R."""
    flows = [(s, t, float(v)) for s, t, v in flows if v]
    if not flows:
        return ""
    srcs, tgts = [], []
    for s, t, _ in flows:
        if s not in srcs:
            srcs.append(s)
        if t not in tgts:
            tgts.append(t)
    W, H, pad = 460, 240, 10
    stot = {s: sum(v for a, _, v in flows if a == s) for s in srcs}
    ttot = {t: sum(v for _, b, v in flows if b == t) for t in tgts}
    total = sum(stot.values()) or 1
    inner = ""

    def _stack(names, tot, x):
        pos, y = {}, pad
        for n in names:
            hgt = tot[n] / total * (H - 2 * pad)
            pos[n] = (y, hgt)
            y += hgt + 6
        return pos
    lp = _stack(srcs, stot, 0)
    rp = _stack(tgts, ttot, 0)
    for i, s in enumerate(srcs):
        y, h = lp[s]
        inner += (f"<rect x='6' y='{y}' width='12' height='{h}' rx='3' fill='{_PAL[i%len(_PAL)]}'/>"
                  f"<text x='22' y='{y+12}' fill='{_INK}' font-size='10'>{_e(s)[:16]}</text>")
    for i, t in enumerate(tgts):
        y, h = rp[t]
        inner += (f"<rect x='{W-18}' y='{y}' width='12' height='{h}' rx='3' fill='#2FE3D2'/>"
                  f"<text x='{W-24}' y='{y+12}' text-anchor='end' fill='{_INK}' font-size='10'>{_e(t)[:16]}</text>")
    soff = {s: lp[s][0] for s in srcs}
    toff = {t: rp[t][0] for t in tgts}
    for i, (s, t, v) in enumerate(flows):
        th = max(1.5, v / total * (H - 2 * pad))
        y0 = soff[s] + th / 2
        y1 = toff[t] + th / 2
        soff[s] += th
        toff[t] += th
        inner += (f"<path d='M18 {y0} C{W/2} {y0} {W/2} {y1} {W-18} {y1}' fill='none' "
                  f"stroke='{_PAL[i%len(_PAL)]}' stroke-opacity='.35' stroke-width='{th}'/>")
    return _svg(W, H, inner)


# --- Forecast: confidence-band line ----------------------------------------
def confband(points, band=0.15):
    """points: [y0,y1,...] actual+forecast; last ~third treated as forecast band."""
    pts = [float(p) for p in points if p is not None]
    if len(pts) < 2:
        return ""
    W, H, pad = 460, 160, 12
    hi = max(pts) or 1
    lo = min(pts)
    span = (hi - lo) or 1
    n = len(pts)

    def X(i):
        return pad + i / (n - 1) * (W - 2 * pad)

    def Y(v):
        return pad + (hi - v) / span * (H - 2 * pad)
    line = " ".join(f"{'M' if i==0 else 'L'}{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(pts))
    split = int(n * 0.66)
    up = " ".join(f"{'M' if i==0 else 'L'}{X(split+i):.1f} {Y(v*(1+band)):.1f}" for i, v in enumerate(pts[split:]))
    dn = " ".join(f"L{X(n-1-i):.1f} {Y(v*(1-band)):.1f}" for i, v in enumerate(reversed(pts[split:])))
    band_path = (up + " " + dn + " Z") if up else ""
    inner = (f"<path d='{band_path}' fill='#4C8DFF' fill-opacity='.14'/>" if band_path else "")
    inner += f"<path d='{line}' fill='none' stroke='#4C8DFF' stroke-width='2.5'/>"
    inner += f"<circle cx='{X(n-1):.1f}' cy='{Y(pts[-1]):.1f}' r='3.5' fill='#4C8DFF'/>"
    return _svg(W, H, inner)


# --- AI Workforce: directed graph (agent dependency) -----------------------
def digraph(nodes, edges):
    """nodes: [(id,label,ok)]; edges:[(from_id,to_id)]. Simple layered layout."""
    if not nodes:
        return ""
    W = 460
    per = 4
    rows = (len(nodes) + per - 1) // per
    H = rows * 74 + 20
    pos = {}
    for i, (nid, _l, _o) in enumerate(nodes):
        r, c = i // per, i % per
        x = 40 + c * ((W - 80) / max(per - 1, 1))
        y = 34 + r * 74
        pos[nid] = (x, y)
    inner = ""
    for a, b in edges:
        if a in pos and b in pos:
            (x0, y0), (x1, y1) = pos[a], pos[b]
            inner += f"<line x1='{x0}' y1='{y0}' x2='{x1}' y2='{y1}' stroke='{_LINE}' stroke-width='1.5'/>"
    for nid, label, ok in nodes:
        x, y = pos[nid]
        col = "#3FD98B" if ok else ("#F5B14C" if ok is None else "#FF6B93")
        inner += (f"<circle cx='{x}' cy='{y}' r='13' fill='#0F1626' stroke='{col}' stroke-width='2'/>"
                  f"<circle cx='{x}' cy='{y}' r='4' fill='{col}'/>"
                  f"<text x='{x}' y='{y+26}' text-anchor='middle' fill='{_INK}' font-size='9'>{_e(label)[:12]}</text>")
    return _svg(W, H, inner)


# --- Clicks: treemap -------------------------------------------------------
def treemap(items):
    """items: [(label, value)] — simple row-based squarified-ish layout."""
    items = [(l, float(v)) for l, v in items if v]
    if not items:
        return ""
    items.sort(key=lambda x: -x[1])
    items = items[:8]
    W, H = 460, 200
    total = sum(v for _, v in items) or 1
    inner = ""
    x = 0
    for i, (l, v) in enumerate(items):
        w = v / total * W
        col = _PAL[i % len(_PAL)]
        inner += (f"<rect x='{x}' y='0' width='{max(2,w-2)}' height='{H}' rx='6' fill='{col}' fill-opacity='.85'/>"
                  f"<text x='{x+6}' y='18' fill='#04121a' font-size='10' font-weight='700'>{_e(l)[:12]}</text>"
                  f"<text x='{x+6}' y='32' fill='#04121a' font-size='9'>{int(v)}</text>")
        x += w
    return _svg(W, H, inner)


# --- Keyword movement: bump chart ------------------------------------------
def bump(series):
    """series: [(label, [rank,...])] lower rank = better (drawn higher)."""
    series = [(l, [int(r) for r in rs]) for l, rs in series if rs]
    if not series:
        return ""
    W, H, pad = 460, 180, 20
    n = max(len(rs) for _, rs in series)
    mx = max(max(rs) for _, rs in series) or 1

    def X(i):
        return pad + i / max(n - 1, 1) * (W - 2 * pad)

    def Y(r):
        return pad + (r - 1) / max(mx - 1, 1) * (H - 2 * pad)
    inner = ""
    for i, (l, rs) in enumerate(series):
        col = _PAL[i % len(_PAL)]
        path = " ".join(f"{'M' if j==0 else 'L'}{X(j):.1f} {Y(r):.1f}" for j, r in enumerate(rs))
        inner += f"<path d='{path}' fill='none' stroke='{col}' stroke-width='2'/>"
        inner += f"<text x='{X(len(rs)-1)+4}' y='{Y(rs[-1])+3}' fill='{col}' font-size='9'>{_e(l)[:10]}</text>"
    return _svg(W, H, inner)


# --- Sales region: geographic distribution ---------------------------------
_FLAG = {"United States": "🇺🇸", "USA": "🇺🇸", "United Kingdom": "🇬🇧", "UK": "🇬🇧",
         "Germany": "🇩🇪", "Switzerland": "🇨🇭", "Canada": "🇨🇦", "Other": "🌍"}


def geo(items):
    """Regional distribution — items:[(country,value)]. Flag + proportional bar
    (a pragmatic geographic view that renders offline)."""
    items = [(l, float(v)) for l, v in items if l]
    if not items or not any(v for _, v in items):
        return ""
    W = 460
    rh = 30
    H = len(items) * rh + 8
    mx = max(v for _, v in items) or 1
    inner = ""
    for i, (l, v) in enumerate(items):
        y = i * rh + 6
        bw = (v / mx) * (W - 190)
        inner += (f"<text x='0' y='{y+15}' font-size='14'>{_FLAG.get(l,'🌍')}</text>"
                  f"<text x='22' y='{y+15}' fill='{_INK}' font-size='11'>{_e(l)[:18]}</text>"
                  f"<rect x='150' y='{y+3}' width='{max(3,bw)}' height='16' rx='4' fill='{_PAL[i%len(_PAL)]}'/>"
                  f"<text x='{150+max(3,bw)+6}' y='{y+15}' fill='{_MUT}' font-size='10'>{int(v)}</text>")
    return _svg(W, H, inner)


# --- Team/agent workload: gantt --------------------------------------------
def gantt(tasks, span=7):
    """tasks: [(label, start_day, length_days)] over `span` days."""
    tasks = [(l, int(s), int(ln)) for l, s, ln in tasks if l][:8]
    if not tasks:
        return ""
    W, H = 460, len(tasks) * 26 + 16
    lab = 110
    dw = (W - lab) / span
    inner = ""
    for d in range(span + 1):
        inner += f"<line x1='{lab + d*dw}' y1='0' x2='{lab + d*dw}' y2='{H-14}' stroke='{_LINE}'/>"
    for i, (l, s, ln) in enumerate(tasks):
        y = 6 + i * 26
        x = lab + s * dw
        inner += (f"<text x='0' y='{y+13}' fill='{_INK}' font-size='10'>{_e(l)[:16]}</text>"
                  f"<rect x='{x}' y='{y}' width='{max(4,ln*dw-3)}' height='18' rx='5' fill='{_PAL[i%len(_PAL)]}'/>")
    return _svg(W, H, inner)
