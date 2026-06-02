"""Deterministic, dependency-free, server-side inline-SVG chart toolkit (c16b, ADR-33).

Extends the `delta.sparkline_svg` precedent to a full chart vocabulary: bar / stacked /
pct-stacked / donut / scatter (with bubble) / treemap / icicle-flame / histogram /
multi-series line. Every chart is a single `<svg role="img">` with `<title>`/`<desc>`, themed
from `design_tokens.toml` `[chart]` (sizes) + existing CSS `var(--...)` colors (light/dark aware).

Determinism is load-bearing (golden byte-parity + workflow resume): fixed-precision coords
(`f'{x:.2f}'`, mirroring sparkline_svg), NO `random` / `Date` / timestamps. Every emitted text
node is ASCII (the orchestrator lints each rendered page; `x` not `*`, `-` not em-dash). Empty or
all-zero input returns `''` (safe) so callers can drop a chart with no data.

The reports keep the detail table directly below each chart as the exact, accessible fallback
(chart = at-a-glance, table = source of truth). Re-exported through `reports/base.py`.
"""

from __future__ import annotations

import math

from . import _tokens
from .chrome import DRAW_CLASSES, class_color_var
# All emitted text/attrs route through safe_chrome_text (scrub banned chars + HTML-escape) so
# data-derived labels (pass / mesh / rt names) can never trip the page lint (ASCII-only contract).
from .formatters import safe_chrome_text as _h

# Designer-tunable sizes/palette from design_tokens.toml [chart] (c16b). Defaults keep charts
# working if the block is absent. Colors are CSS var() strings so they follow light-dark().
_CHART = _tokens.chart()

_DEF = {
    'width': 640, 'height': 220, 'donut': 180,
    'bar_h': 16, 'gap': 6, 'pad': 10,
    'series_color': 'var(--accent-data)',
    'axis_color': 'var(--border-2)', 'grid_color': 'var(--border-1)',
    'label_color': 'var(--text-2)',
    'threshold_warn': 'var(--status-warn)', 'threshold_alarm': 'var(--status-alarm)',
    'palette': ['var(--accent-data)', 'var(--c-opaque)', 'var(--c-prepass)',
                'var(--c-translucent)', 'var(--c-ui)', 'var(--c-postprocess)',
                'var(--c-additive)', 'var(--c-decal)', 'var(--c-shadow)', 'var(--c-other)'],
}

# Chart-internal geometry (px) that designers do not tune — kept module-local, not in tokens.
_AXIS_L = 44     # left margin for the y axis
_AXIS_B = 26     # bottom margin for the x axis
_AXIS_T = 12     # top margin
_AXIS_R = 12     # right margin


def _t(key):
    v = _CHART.get(key, _DEF.get(key))
    return v if v is not None else _DEF.get(key)


def _c(v: float) -> str:
    """Fixed-precision coordinate (mirror sparkline_svg)."""
    return f'{float(v):.2f}'


def _palette(i: int) -> str:
    pal = _t('palette') or _DEF['palette']
    return pal[i % len(pal)]


def _num(v) -> str:
    """Default value formatter: integer-valued -> grouped int, else 2 dp."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ''
    if f == int(f):
        return f'{int(f):,}'
    return f'{f:,.2f}'


def _open(w: int, h: int, aria: str, title: str, desc: str) -> str:
    """SVG opening tag + role/aria + title/desc. Text is escaped + assumed ASCII."""
    return (f'<svg class="chart-svg" role="img" viewBox="0 0 {int(w)} {int(h)}" '
            f'width="{int(w)}" height="{int(h)}" aria-label="{_h(aria or title)}">'
            f'<title>{_h(title)}</title><desc>{_h(desc)}</desc>')


def figure(svg: str, caption: str = '') -> str:
    """Wrap a chart SVG in <figure class="chart"> with an optional figcaption. '' -> ''."""
    if not svg:
        return ''
    cap = f'<figcaption>{_h(caption)}</figcaption>' if caption else ''
    return f'<figure class="chart">{cap}{svg}</figure>'


# --------------------------------------------------------------------------- bar_chart

def bar_chart(items, *, color: str | None = None, value_fmt=None, thresholds=None,
              max_value: float | None = None, width: int | None = None,
              title: str = '', desc: str = '', aria: str | None = None) -> str:
    """Horizontal bars. `items` = list of (label, value). Optional `thresholds` = list of
    (value, color, label) vertical rule-lines (e.g. config warn/alarm). Empty -> ''."""
    items = [(str(lbl), float(v or 0)) for lbl, v in (items or [])]
    if not items:
        return ''
    color = color or _t('series_color')
    value_fmt = value_fmt or _num
    W = int(width or _t('width'))
    bar_h, gap, pad = int(_t('bar_h')), int(_t('gap')), int(_t('pad'))
    n = len(items)
    H = pad * 2 + n * (bar_h + gap) - gap
    val_w = 64
    # Size the label column to the LONGEST actual label so the bar starts right after the text -
    # no fixed-fraction dead space (~6.6px/char at fs-small mono + 8px gap), capped at 60% of width
    # so bars never vanish. lbl_max is derived back from the (capped) column so a label can never
    # overrun the bar; hard-capped at 30 chars (c16c).
    _CHAR_W = 6.6
    longest = max((len(str(lbl)) for lbl, _ in items), default=0)
    label_w = max(pad + 8, min(int(W * 0.6), pad + int(longest * _CHAR_W) + 8))
    lbl_max = min(30, max(4, int((label_w - pad - 8) / _CHAR_W)))
    bar_x = label_w
    bar_w = max(1, W - label_w - pad - val_w)
    mx = float(max_value if max_value is not None else max((v for _, v in items), default=0.0))
    if mx <= 0:
        mx = 1.0

    top = items[0]
    aria = aria or title or 'bar chart'
    if not desc:
        desc = f'{n} bars; top {top[0]} at {value_fmt(top[1])}'
    out = [_open(W, H, aria, title, desc)]
    for i, (lbl, v) in enumerate(items):
        y = pad + i * (bar_h + gap)
        w = max(0.0, (v / mx) * bar_w)
        out.append(f'<text x="{_c(pad)}" y="{_c(y + bar_h * 0.74)}" '
                   f'fill="{_t("label_color")}">{_h(_clip(lbl, lbl_max))}</text>')
        out.append(f'<rect x="{_c(bar_x)}" y="{_c(y)}" width="{_c(w)}" height="{bar_h}" '
                   f'fill="{color}" rx="1"/>')
        out.append(f'<text x="{_c(bar_x + w + 4)}" y="{_c(y + bar_h * 0.74)}" '
                   f'fill="{_t("label_color")}">{_h(value_fmt(v))}</text>')
    for tv, tcolor, tlabel in (thresholds or []):
        tx = bar_x + min(1.0, float(tv) / mx) * bar_w
        out.append(f'<line x1="{_c(tx)}" y1="{_c(pad - 2)}" x2="{_c(tx)}" '
                   f'y2="{_c(H - pad + 2)}" stroke="{tcolor}" stroke-width="1" '
                   f'stroke-dasharray="3 2"/>')
        if tlabel:
            out.append(f'<text x="{_c(tx + 2)}" y="{_c(pad + 6)}" '
                       f'fill="{tcolor}">{_h(tlabel)}</text>')
    out.append('</svg>')
    return ''.join(out)


def _clip(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + '~'


# ------------------------------------------------------------------- stacked / pct_stacked

def _stacked(rows, classes, *, normalize, width, title, desc, aria):
    rows = [(str(lbl), dict(w or {})) for lbl, w in (rows or [])]
    rows = [(lbl, w) for lbl, w in rows if sum(float(x or 0) for x in w.values()) > 0]
    if not rows:
        return ''
    classes = classes or DRAW_CLASSES
    W = int(width or _t('width'))
    bar_h, gap, pad = int(_t('bar_h')), int(_t('gap')), int(_t('pad'))
    n = len(rows)
    H = pad * 2 + n * (bar_h + gap) - gap
    label_w = int(W * 0.30)
    bar_x = label_w
    bar_w = max(1, W - label_w - pad)
    global_max = max((sum(float(w.get(c, 0) or 0) for c in classes) for _, w in rows), default=1.0) or 1.0

    aria = aria or title or 'stacked bar chart'
    out = [_open(W, H, aria, title, desc or f'{n} rows by draw class')]
    for i, (lbl, w) in enumerate(rows):
        y = pad + i * (bar_h + gap)
        total = sum(float(w.get(c, 0) or 0) for c in classes) or 1.0
        denom = total if normalize else global_max
        out.append(f'<text x="{_c(pad)}" y="{_c(y + bar_h * 0.74)}" '
                   f'fill="{_t("label_color")}">{_h(_clip(lbl, 24))}</text>')
        cx = bar_x
        for c in classes:
            v = float(w.get(c, 0) or 0)
            if v <= 0:
                continue
            seg = (v / denom) * bar_w
            out.append(f'<rect x="{_c(cx)}" y="{_c(y)}" width="{_c(seg)}" height="{bar_h}" '
                       f'fill="{class_color_var(c)}"><title>{_h(c)}: {_h(_num(v))}</title></rect>')
            cx += seg
    out.append('</svg>')
    return ''.join(out)


def stacked_bar(rows, *, classes=None, width=None, title='', desc='', aria=None) -> str:
    """Absolute-width stacked bars (rows comparable against a shared max). `rows` = list of
    (label, {class: value}). Empty -> ''."""
    return _stacked(rows, classes, normalize=False, width=width,
                    title=title, desc=desc, aria=aria)


def pct_stacked_bar(rows, *, classes=None, width=None, title='', desc='', aria=None) -> str:
    """100%-normalized stacked bars (per-row share). `rows` = list of (label, {class: value})."""
    return _stacked(rows, classes, normalize=True, width=width,
                    title=title, desc=desc, aria=aria)


# --------------------------------------------------------------------------- donut

def _pt(cx, cy, r, a):
    return cx + r * math.cos(a), cy + r * math.sin(a)


def donut(segments, *, center_label: str = '', width: int | None = None,
          title: str = '', desc: str = '', aria: str | None = None) -> str:
    """Class-share ring. `segments` = list of (label, value, color). Empty -> ''."""
    segs = [(str(lbl), float(v or 0), col) for lbl, v, col in (segments or []) if float(v or 0) > 0]
    if not segs:
        return ''
    size = int(width or _t('donut'))
    cx = cy = size / 2.0
    r_out = size / 2.0 - 2
    r_in = r_out * 0.58
    total = sum(v for _, v, _ in segs) or 1.0

    shares = ', '.join(f'{lbl} {100.0 * v / total:.1f}%' for lbl, v, _ in segs[:6])
    aria = aria or title or 'donut chart'
    out = [_open(size, size, aria, title, desc or shares)]
    if len(segs) == 1:
        # Single full ring: two concentric circles (outer fill + hole punched with bg).
        lbl, v, col = segs[0]
        out.append(f'<circle cx="{_c(cx)}" cy="{_c(cy)}" r="{_c(r_out)}" fill="{col}">'
                   f'<title>{_h(lbl)}: 100.0%</title></circle>')
        out.append(f'<circle cx="{_c(cx)}" cy="{_c(cy)}" r="{_c(r_in)}" fill="var(--bg)"/>')
    else:
        a = -math.pi / 2.0
        for lbl, v, col in segs:
            sweep = 2.0 * math.pi * (v / total)
            a1 = a + sweep
            xo0, yo0 = _pt(cx, cy, r_out, a)
            xo1, yo1 = _pt(cx, cy, r_out, a1)
            xi1, yi1 = _pt(cx, cy, r_in, a1)
            xi0, yi0 = _pt(cx, cy, r_in, a)
            large = 1 if sweep > math.pi else 0
            out.append(
                f'<path d="M{_c(xo0)} {_c(yo0)} A{_c(r_out)} {_c(r_out)} 0 {large} 1 '
                f'{_c(xo1)} {_c(yo1)} L{_c(xi1)} {_c(yi1)} A{_c(r_in)} {_c(r_in)} 0 {large} 0 '
                f'{_c(xi0)} {_c(yi0)} Z" fill="{col}">'
                f'<title>{_h(lbl)}: {100.0 * v / total:.1f}%</title></path>')
            a = a1
    if center_label:
        out.append(f'<text x="{_c(cx)}" y="{_c(cy + 4)}" text-anchor="middle" '
                   f'fill="{_t("label_color")}">{_h(center_label)}</text>')
    out.append('</svg>')
    return ''.join(out)


# --------------------------------------------------------------------------- scatter

def scatter(points, *, x_label: str = '', y_label: str = '', bubble: bool = False,
            width: int | None = None, height: int | None = None,
            title: str = '', desc: str = '', aria: str | None = None) -> str:
    """x/y scatter. `points` = list of (x, y, size, label); `size` scales bubble radius when
    `bubble`, else ignored. Empty -> ''."""
    pts = []
    for p in (points or []):
        x, y = float(p[0] or 0), float(p[1] or 0)
        sz = float(p[2] or 0) if len(p) > 2 and p[2] is not None else 0.0
        lbl = str(p[3]) if len(p) > 3 else ''
        pts.append((x, y, sz, lbl))
    if not pts:
        return ''
    W = int(width or _t('width'))
    H = int(height or int(_t('width') * 0.5))
    x0, x1 = _AXIS_L, W - _AXIS_R
    y0, y1 = _AXIS_T, H - _AXIS_B
    xmin, xmax = 0.0, max((p[0] for p in pts), default=1.0) or 1.0
    ymin, ymax = 0.0, max((p[1] for p in pts), default=1.0) or 1.0
    smax = max((p[2] for p in pts), default=0.0)

    def px(x):
        return x0 + (x - xmin) / (xmax - xmin) * (x1 - x0) if xmax > xmin else x0
    def py(y):
        return y1 - (y - ymin) / (ymax - ymin) * (y1 - y0) if ymax > ymin else y1
    def radius(sz):
        if not bubble or smax <= 0:
            return 3.5
        return 3.0 + 11.0 * math.sqrt(max(0.0, sz) / smax)

    aria = aria or title or 'scatter chart'
    out = [_open(W, H, aria, title,
                 desc or f'{len(pts)} points; x={x_label or "x"}, y={y_label or "y"}')]
    # axes
    out.append(f'<line x1="{_c(x0)}" y1="{_c(y1)}" x2="{_c(x1)}" y2="{_c(y1)}" '
               f'stroke="{_t("axis_color")}"/>')
    out.append(f'<line x1="{_c(x0)}" y1="{_c(y0)}" x2="{_c(x0)}" y2="{_c(y1)}" '
               f'stroke="{_t("axis_color")}"/>')
    # tick labels (min/max)
    out.append(f'<text x="{_c(x1)}" y="{_c(H - 8)}" text-anchor="end" '
               f'fill="{_t("label_color")}">{_h(_num(xmax))}</text>')
    out.append(f'<text x="{_c(x0 + 2)}" y="{_c(y0 + 8)}" '
               f'fill="{_t("label_color")}">{_h(_num(ymax))}</text>')
    if x_label:
        out.append(f'<text x="{_c((x0 + x1) / 2)}" y="{_c(H - 8)}" text-anchor="middle" '
                   f'fill="{_t("label_color")}">{_h(x_label)}</text>')
    if y_label:
        out.append(f'<text x="{_c(10)}" y="{_c((y0 + y1) / 2)}" '
                   f'transform="rotate(-90 10 {_c((y0 + y1) / 2)})" text-anchor="middle" '
                   f'fill="{_t("label_color")}">{_h(y_label)}</text>')
    for x, y, sz, lbl in pts:
        out.append(f'<circle cx="{_c(px(x))}" cy="{_c(py(y))}" r="{_c(radius(sz))}" '
                   f'fill="{_t("series_color")}" fill-opacity="0.55" '
                   f'stroke="{_t("series_color")}">'
                   f'<title>{_h(lbl)}</title></circle>')
    out.append('</svg>')
    return ''.join(out)


# --------------------------------------------------------------------------- histogram

def histogram(values, *, bins: int = 10, color: str | None = None,
              width: int | None = None, height: int | None = None,
              title: str = '', desc: str = '', aria: str | None = None) -> str:
    """Vertical-bar histogram of `values`. Empty -> ''."""
    vals = [float(v) for v in (values or []) if v is not None]
    if not vals:
        return ''
    color = color or _t('series_color')
    W = int(width or _t('width'))
    H = int(height or int(_t('width') * 0.42))
    lo, hi = min(vals), max(vals)
    nb = max(1, int(bins))
    span = (hi - lo) or 1.0
    counts = [0] * nb
    for v in vals:
        b = int((v - lo) / span * nb)
        if b >= nb:
            b = nb - 1
        counts[b] += 1
    cmax = max(counts) or 1

    x0, x1 = _AXIS_L, W - _AXIS_R
    y0, y1 = _AXIS_T, H - _AXIS_B
    bw = (x1 - x0) / nb
    aria = aria or title or 'histogram'
    out = [_open(W, H, aria, title, desc or f'{len(vals)} values across {nb} bins')]
    out.append(f'<line x1="{_c(x0)}" y1="{_c(y1)}" x2="{_c(x1)}" y2="{_c(y1)}" '
               f'stroke="{_t("axis_color")}"/>')
    for i, ct in enumerate(counts):
        if ct <= 0:
            continue
        bh = (ct / cmax) * (y1 - y0)
        bx = x0 + i * bw
        out.append(f'<rect x="{_c(bx + 1)}" y="{_c(y1 - bh)}" width="{_c(bw - 2)}" '
                   f'height="{_c(bh)}" fill="{color}"><title>bin {i + 1}: {ct}</title></rect>')
    out.append(f'<text x="{_c(x0)}" y="{_c(H - 8)}" fill="{_t("label_color")}">{_h(_num(lo))}</text>')
    out.append(f'<text x="{_c(x1)}" y="{_c(H - 8)}" text-anchor="end" '
               f'fill="{_t("label_color")}">{_h(_num(hi))}</text>')
    out.append('</svg>')
    return ''.join(out)


# --------------------------------------------------------------------------- treemap

def _slice_dice(items, x, y, w, h, horizontal, out):
    if not items:
        return
    if len(items) == 1:
        lbl, v, col = items[0]
        out.append((x, y, w, h, lbl, v, col))
        return
    total = sum(v for _, v, _ in items) or 1.0
    acc = 0.0
    split = len(items) - 1
    for i, (_, v, _) in enumerate(items):
        acc += v
        if acc >= total / 2.0:
            split = i + 1
            break
    split = min(max(split, 1), len(items) - 1)
    a, b = items[:split], items[split:]
    sa = sum(v for _, v, _ in a) or 1.0
    if horizontal:
        wa = w * sa / total
        _slice_dice(a, x, y, wa, h, not horizontal, out)
        _slice_dice(b, x + wa, y, w - wa, h, not horizontal, out)
    else:
        ha = h * sa / total
        _slice_dice(a, x, y, w, ha, not horizontal, out)
        _slice_dice(b, x, y + ha, w, h - ha, not horizontal, out)


def treemap(items, *, width: int | None = None, height: int | None = None,
            title: str = '', desc: str = '', aria: str | None = None) -> str:
    """Slice-and-dice treemap. `items` = list of (label, value, color). Empty -> ''."""
    its = [(str(lbl), float(v or 0), col) for lbl, v, col in (items or []) if float(v or 0) > 0]
    if not its:
        return ''
    its = sorted(its, key=lambda t: (-t[1], t[0]))   # stable, deterministic
    W = int(width or _t('width'))
    H = int(height or int(_t('width') * 0.42))
    rects: list = []
    _slice_dice(its, 0.0, 0.0, float(W), float(H), True, rects)

    aria = aria or title or 'treemap'
    out = [_open(W, H, aria, title, desc or f'{len(its)} cells sized by value')]
    for x, y, w, h_, lbl, v, col in rects:
        out.append(f'<rect x="{_c(x)}" y="{_c(y)}" width="{_c(max(0, w - 1))}" '
                   f'height="{_c(max(0, h_ - 1))}" fill="{col}" stroke="var(--bg)">'
                   f'<title>{_h(lbl)}: {_h(_num(v))}</title></rect>')
        if w > 42 and h_ > 14:
            out.append(f'<text x="{_c(x + 3)}" y="{_c(y + 12)}" '
                       f'fill="var(--bg)">{_h(_clip(lbl, int(w / 7)))}</text>')
    out.append('</svg>')
    return ''.join(out)


# --------------------------------------------------------------------------- icicle (flame)

def icicle(levels, *, width: int | None = None, height: int | None = None,
           title: str = '', desc: str = '', aria: str | None = None) -> str:
    """Banded icicle/flame. `levels` = list of bands; each band = list of (label, value, color),
    partitioned left-to-right by value. Top band is the root. Empty -> ''."""
    bands = [[(str(lbl), float(v or 0), col) for lbl, v, col in (band or []) if float(v or 0) > 0]
             for band in (levels or [])]
    bands = [b for b in bands if b]
    if not bands:
        return ''
    W = int(width or _t('width'))
    H = int(height or int(_t('width') * 0.42))
    band_h = H / len(bands)
    aria = aria or title or 'icicle chart'
    out = [_open(W, H, aria, title, desc or f'{len(bands)} levels')]
    for li, band in enumerate(bands):
        total = sum(v for _, v, _ in band) or 1.0
        y = li * band_h
        cx = 0.0
        for lbl, v, col in band:
            w = W * v / total
            out.append(f'<rect x="{_c(cx)}" y="{_c(y)}" width="{_c(max(0, w - 1))}" '
                       f'height="{_c(band_h - 1)}" fill="{col}" stroke="var(--bg)">'
                       f'<title>{_h(lbl)}: {_h(_num(v))}</title></rect>')
            if w > 42:
                out.append(f'<text x="{_c(cx + 3)}" y="{_c(y + band_h * 0.6)}" '
                           f'fill="var(--bg)">{_h(_clip(lbl, int(w / 7)))}</text>')
            cx += w
    out.append('</svg>')
    return ''.join(out)


# --------------------------------------------------------------------------- line_chart

def line_chart(series, *, x_labels=None, width: int | None = None, height: int | None = None,
               title: str = '', desc: str = '', aria: str | None = None) -> str:
    """Multi-series line. `series` = list of (name, values, color); None values break the line
    (like sparkline_svg). Empty / all-None -> ''."""
    series = [(str(name), list(vals or []), col) for name, vals, col in (series or [])]
    finite = [float(v) for _, vals, _ in series for v in vals if v is not None]
    npts = max((len(vals) for _, vals, _ in series), default=0)
    if not finite or npts < 1:
        return ''
    W = int(width or _t('width'))
    H = int(height or int(_t('width') * 0.42))
    x0, x1 = _AXIS_L, W - _AXIS_R
    y0, y1 = _AXIS_T, H - _AXIS_B
    lo, hi = min(finite), max(finite)
    span = (hi - lo) or 1.0
    step = (x1 - x0) / (npts - 1) if npts > 1 else 0.0

    def py(v):
        return y1 - (float(v) - lo) / span * (y1 - y0)

    aria = aria or title or 'line chart'
    out = [_open(W, H, aria, title, desc or f'{len(series)} series over {npts} drops')]
    out.append(f'<line x1="{_c(x0)}" y1="{_c(y1)}" x2="{_c(x1)}" y2="{_c(y1)}" '
               f'stroke="{_t("axis_color")}"/>')
    out.append(f'<line x1="{_c(x0)}" y1="{_c(y0)}" x2="{_c(x0)}" y2="{_c(y1)}" '
               f'stroke="{_t("axis_color")}"/>')
    out.append(f'<text x="{_c(x0 + 2)}" y="{_c(y0 + 8)}" fill="{_t("label_color")}">{_h(_num(hi))}</text>')
    for si, (name, vals, col) in enumerate(series):
        col = col or _palette(si)
        seg: list = []
        segments: list = []
        for i, v in enumerate(vals):
            if v is None:
                if seg:
                    segments.append(seg)
                    seg = []
                continue
            seg.append((x0 + i * step, py(v)))
        if seg:
            segments.append(seg)
        for s in segments:
            if len(s) == 1:
                x, y = s[0]
                out.append(f'<circle cx="{_c(x)}" cy="{_c(y)}" r="2" fill="{col}"/>')
            else:
                pts = ' '.join(f'{_c(x)},{_c(y)}' for x, y in s)
                out.append(f'<polyline points="{pts}" stroke="{col}" stroke-width="1.5" '
                           f'fill="none"/>')
        # series label at its last point
        last = next((p for p in reversed([(x0 + i * step, v) for i, v in enumerate(vals)])
                     if p[1] is not None), None)
        if last is not None:
            out.append(f'<text x="{_c(min(last[0] + 3, x1))}" y="{_c(py(last[1]) - 2)}" '
                       f'fill="{col}">{_h(_clip(name, 14))}</text>')
    x_labels = x_labels or []
    if x_labels:
        out.append(f'<text x="{_c(x0)}" y="{_c(H - 6)}" '
                   f'fill="{_t("label_color")}">{_h(_clip(str(x_labels[0]), 16))}</text>')
        if len(x_labels) > 1:
            out.append(f'<text x="{_c(x1)}" y="{_c(H - 6)}" text-anchor="end" '
                       f'fill="{_t("label_color")}">{_h(_clip(str(x_labels[-1]), 16))}</text>')
    out.append('</svg>')
    return ''.join(out)
