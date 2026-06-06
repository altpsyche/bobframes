"""Comparison cells and visualization helpers."""

from __future__ import annotations

import html as _html

from .. import config
from . import _tokens
from .chrome import DRAW_CLASSES, Column, class_color_var, classes, h

# Sparkline default dimensions from design_tokens.toml [layout] (c08, H-20: was 60x14 inline).
_LAYOUT = _tokens.layout()


def rank_pill(n: int) -> str:
    cls = f'rank rank-{n}' if 1 <= n <= 3 else 'rank'
    return f'<span class="{cls}">{n}</span>'


def inline_bar(value, max_value, *, color_var: str | None = None) -> str:
    """Render a 80x6 inline progress bar. Renders empty if value/max invalid."""
    if max_value in (None, 0, 0.0):
        return ''
    try:
        v = float(value or 0)
        m = float(max_value)
    except (TypeError, ValueError):
        return ''
    if m <= 0:
        return ''
    pct = max(0.0, min(100.0, (v / m) * 100.0))
    style = f'width: {pct:.2f}%;'
    if color_var:
        style += f' background: {color_var};'
    return f'<div class="ibar"><div style="{style}"></div></div>'


def delta_parts(curr, prev, *, lower_is_better: bool | None = True,
                fmt: str | None = None,
                regression_threshold_pct: float | None = None) -> tuple[str, str]:
    """The shared (css_class, text) of a per-KPI delta -- the single source delta_cell / delta_pill /
    delta_column all consume (v0.2.6-4). ASCII signs only; the class (not the sign) encodes direction.

    Returns: ('flat', '') when both sides are None / unparseable; ('new', 'new') when there is no prior;
    ('flat', '0') for no change; else ('pos'|'neg'[' alarm'], '<signed value>'). 'alarm' flags a large
    REGRESSION only (cls == 'neg'); a big improvement must never wear the red regression accent (c16c).
    """
    if fmt is None:
        fmt = config.get_config().delta.fmt   # H-22
    if curr is None and prev is None:
        return 'flat', ''
    if prev is None:
        return 'new', 'new'
    if curr is None:
        curr = 0
    try:
        curr_f = float(curr)
        prev_f = float(prev)
    except (TypeError, ValueError):
        return 'flat', ''
    diff = curr_f - prev_f
    if diff == 0:
        return 'flat', '0'
    if lower_is_better is None:
        cls = 'flat'
    elif lower_is_better:
        cls = 'pos' if diff < 0 else 'neg'
    else:
        cls = 'pos' if diff > 0 else 'neg'
    if (cls == 'neg' and regression_threshold_pct is not None and prev_f != 0
            and abs(diff) / abs(prev_f) * 100.0 > regression_threshold_pct):
        cls = cls + ' alarm'
    text = fmt.format(diff).replace('−', '-')
    return cls, text


def delta_pill(curr, prev, *, lower_is_better: bool | None = True,
               fmt: str | None = None) -> str:
    """Same logic as delta_cell but renders <span class='delta-pill'> (no regression alarm)."""
    cls, text = delta_parts(curr, prev, lower_is_better=lower_is_better, fmt=fmt)
    return f'<span class="delta-pill {cls}">{_html.escape(text)}</span>'


def delta_cell(curr, prev, *,
               lower_is_better: bool | None = True,
               fmt: str | None = None,
               regression_threshold_pct: float | None = None) -> str:
    """Render <td> for a per-KPI delta. ASCII signs only. CSS class encodes direction.

    Retained for callers that emit a full <td> directly; the v0.2.6-4 tabled reports build delta columns
    via `delta_column` (the Column factory) instead, so this is now unused by the reports (kept as a
    valid standalone helper, still unit-tested)."""
    cls, text = delta_parts(curr, prev, lower_is_better=lower_is_better, fmt=fmt,
                            regression_threshold_pct=regression_threshold_pct)
    return f'<td class="delta {cls}">{_html.escape(text)}</td>'


def delta_column(key: str, header: str = 'delta', *,
                 latest: bool = False, latest_cell: bool = False, group: str | None = None) -> Column:
    """A `chrome.Column` for a per-KPI delta (v0.2.6-4). The cell VALUE at `row[key]` MUST be the
    `(css_class, text)` tuple produced by `delta_parts(...)` -- render reads the text, cell_class reads
    the direction, both off the PASSED value (no closure over a loop var). Reproduces today's split
    classes: `<th class="num[ delta-latest]">` + `<td class="delta[ delta-latest] {dir}">`. `latest`
    adds delta-latest to the th (all reports); `latest_cell` also to the td (trend's _kpi_matrix only).
    `group` names the collapsible col-group it joins (shader_hotlist's history wall)."""
    return Column(
        key, header, group=group,
        header_class=classes('num', 'delta-latest' if latest else ''),
        render=lambda value, row: h(value[1] if value else ''),
        cell_class=lambda value, row: classes('delta', 'delta-latest' if latest_cell else '',
                                              value[0] if value else 'flat'))


def class_segments_bar(weights: dict, total: float | None = None) -> str:
    if total is None:
        total = sum(weights.values())
    try:
        total_f = float(total)
    except (TypeError, ValueError):
        total_f = 0.0
    if total_f <= 0:
        return '<div class="bar"></div>'
    min_pct = config.get_config().delta.bar_label_min_pct   # H-21
    parts = ['<div class="bar">']
    for cls in DRAW_CLASSES:
        n = weights.get(cls, 0)
        try:
            n_f = float(n)
        except (TypeError, ValueError):
            n_f = 0.0
        if n_f <= 0:
            continue
        pct = n_f * 100.0 / total_f
        label = ''
        if pct >= min_pct:
            if isinstance(n, float) and not n.is_integer():
                label = f'{n_f:,.2f}'
            else:
                label = f'{int(n_f):,}'
        parts.append(
            f'<div class="seg" style="width: {pct:.4f}%; background: {class_color_var(cls)};" '
            f'title="{h(cls)}: {label or n_f}">{h(label)}</div>'
        )
    parts.append('</div>')
    return ''.join(parts)


def sparkline_svg(values: list, w: int = _LAYOUT['sparkline_w'], h_: int = _LAYOUT['sparkline_h']) -> str:
    """Inline SVG polyline. None values render as segment breaks (multi-polyline)."""
    if not values or all(v is None for v in values):
        return ''
    finite = [float(v) for v in values if v is not None]
    if not finite:
        return ''
    lo = min(finite)
    hi = max(finite)
    span = hi - lo if hi != lo else 1.0
    n = len(values)
    if n < 2:
        return ''
    step = w / (n - 1)
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for i, v in enumerate(values):
        if v is None:
            if current:
                segments.append(current)
                current = []
            continue
        x = i * step
        y = h_ - ((float(v) - lo) / span) * (h_ - 2) - 1
        current.append((x, y))
    if current:
        segments.append(current)
    parts = [f'<svg class="spark" width="{w}" height="{h_}" viewBox="0 0 {w} {h_}">']
    for seg in segments:
        if len(seg) == 1:
            x, y = seg[0]
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.5" fill="currentColor"/>')
        else:
            pts = ' '.join(f'{x:.2f},{y:.2f}' for x, y in seg)
            parts.append(f'<polyline points="{pts}" stroke="currentColor" stroke-width="1.25" fill="none"/>')
    parts.append('</svg>')
    return ''.join(parts)


def trendline(values: list, *, tone: str = 'neutral', w: int = 240, h: int = 40,
              pad_x: int = 6, pad_y: int = 9) -> str:
    """Filled-area mini sparkline (polygon fill + polyline + endpoint dot), uniformly scaled to the chip
    width (viewBox + width:100%, height:auto - no distortion). Reads as a real trend strip even at 2
    points, where sparkline_svg's scratch line did not. None values are dropped; '' for < 2 points.

    c16x-5 (ADR-42): promoted verbatim from summary._trendline, with the classes renamed
    .bh-trend/.bh-line/.bh-fill/.bh-dot -> .trendline/.trendline-line/.trendline-fill/.trendline-dot so
    the styling lives in the owned component CSS instead of summary's inline <style>. Numeric-only
    output (no escaping needed); deterministic fixed-precision coords."""
    pts = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return ''
    n = len(values)
    ys = [v for _, v in pts]
    lo, hi = min(ys), max(ys)
    flat = hi == lo
    span = (hi - lo) or 1.0
    span_x = (n - 1) or 1

    def fx(i):
        return pad_x + (i / span_x) * (w - 2 * pad_x)

    def fy(v):
        if flat:                      # no movement -> a centered flat line, not one hugging the floor
            return h / 2
        return h - pad_y - ((v - lo) / span) * (h - 2 * pad_y)

    line = [(fx(i), fy(v)) for i, v in pts]
    poly = ' '.join(f'{x:.2f},{y:.2f}' for x, y in line)
    base_y = h - pad_y
    area = f'{line[0][0]:.2f},{base_y:.2f} {poly} {line[-1][0]:.2f},{base_y:.2f}'
    ex, ey = line[-1]
    return (f'<svg class="trendline tone-{tone}" viewBox="0 0 {w} {h}" role="img" aria-label="trend">'
            f'<polygon class="trendline-fill" points="{area}"/>'
            f'<polyline class="trendline-line" points="{poly}"/>'
            f'<circle class="trendline-dot" cx="{ex:.2f}" cy="{ey:.2f}" r="2.5"/></svg>')
