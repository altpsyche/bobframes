"""Coordinate cache build + per-report build + dashboard + root-index render."""

from __future__ import annotations

import time

from .. import lint
from ..html import template
from . import (
    _dashboard as report_dashboard,
    base as reports_base,
    draws_by_class as report_draws_by_class,
    instancing_opportunities as report_instancing,
    overdraw as report_overdraw,
    pass_gpu as report_pass_gpu,
    shader_hotlist as report_shader,
    trend_table as report_trend,
)

_REPORT_MODULES = (
    report_draws_by_class,
    report_trend,
    report_instancing,
    report_pass_gpu,
    report_shader,
    report_overdraw,
)


def render_all_reports(root: str, log) -> int:
    """Build cache, all 6 reports, dashboard, root index. Returns 0 on success."""
    t0 = time.monotonic()
    cache_out = reports_base.build_per_drop_cache(root)
    log(f'  built per-drop cache: {cache_out} ({time.monotonic()-t0:.1f}s)')

    for mod in _REPORT_MODULES:
        try:
            rep = mod.build(root)
            log(f'  built report: {rep}')
        except Exception as e:
            log(f'  {mod.__name__} FAILED: {e}')
            return 1

    try:
        dash = report_dashboard.build(root)
        log(f'  built dashboard: {dash}')
    except Exception as e:
        log(f'  dashboard FAILED: {e}')
        return 1

    log('rendering root index')
    root_idx = template.render_root(root)
    root_hits = lint.lint_file(root_idx)
    if root_hits:
        for lineno, label, snip in root_hits:
            log(f'  LINT FAIL {root_idx}:{lineno}: [{label}] {snip}')
        return 1
    log(f'  -> {root_idx}')
    return 0
