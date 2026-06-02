"""Comparison cells and visualization helpers."""

from __future__ import annotations

import html as _html

from .. import config
from . import _tokens
from .chrome import DRAW_CLASSES, class_color_var, h

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


def delta_pill(curr, prev, *, lower_is_better: bool | None = True,
               fmt: str | None = None) -> str:
    """Same logic as delta_cell but renders <span class='delta-pill'>."""
    if fmt is None:
        fmt = config.get_config().delta.fmt   # H-22
    if curr is None and prev is None:
        return '<span class="delta-pill flat"></span>'
    if prev is None:
        return '<span class="delta-pill new">new</span>'
    if curr is None:
        curr = 0
    try:
        curr_f = float(curr)
        prev_f = float(prev)
    except (TypeError, ValueError):
        return '<span class="delta-pill flat"></span>'
    diff = curr_f - prev_f
    if diff == 0:
        return '<span class="delta-pill flat">0</span>'
    if lower_is_better is None:
        cls = 'flat'
    elif lower_is_better:
        cls = 'pos' if diff < 0 else 'neg'
    else:
        cls = 'pos' if diff > 0 else 'neg'
    text = fmt.format(diff).replace('−', '-')
    return f'<span class="delta-pill {cls}">{_html.escape(text)}</span>'


def delta_cell(curr, prev, *,
               lower_is_better: bool | None = True,
               fmt: str | None = None,
               regression_threshold_pct: float | None = None) -> str:
    """Render <td> for a per-KPI delta. ASCII signs only. CSS class encodes direction."""
    if fmt is None:
        fmt = config.get_config().delta.fmt   # H-22
    if curr is None and prev is None:
        return '<td class="delta flat"></td>'
    if prev is None:
        return '<td class="delta new">new</td>'
    if curr is None:
        curr = 0
    try:
        curr_f = float(curr)
        prev_f = float(prev)
    except (TypeError, ValueError):
        return '<td class="delta flat"></td>'

    diff = curr_f - prev_f
    if diff == 0:
        return '<td class="delta flat">0</td>'

    if lower_is_better is None:
        cls = 'flat'
    elif lower_is_better:
        cls = 'pos' if diff < 0 else 'neg'
    else:
        cls = 'pos' if diff > 0 else 'neg'

    # 'alarm' flags a large REGRESSION only (cls == 'neg'); a big improvement must never wear the
    # red regression accent (c16c - was magnitude-only, which painted red bars on -100% wins).
    alarm = ''
    if cls == 'neg' and regression_threshold_pct is not None and prev_f != 0:
        pct = abs(diff) / abs(prev_f) * 100.0
        if pct > regression_threshold_pct:
            alarm = ' alarm'

    text = fmt.format(diff).replace('−', '-')
    return f'<td class="delta {cls}{alarm}">{_html.escape(text)}</td>'


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
