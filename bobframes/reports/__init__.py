"""Report registry — the single source of the report list (H-8 / D-1).

`orchestrator` and `ab` both build from `all_reports()` instead of each keeping its own module list
(the old `_REPORT_MODULES` / `_MODULES` duplicate). The list is runtime-augmentable via
`register_report()` so v0.6 plugins (M-1) and the new v0.4 reports (c28/c31) can join without editing
this module. Base modules are imported lazily inside `all_reports()` to keep `bobframes version`/`check`
free of pyarrow and to avoid an import cycle (report modules import `.base`).
"""

from __future__ import annotations

_EXTRA_REPORTS: list = []


def register_report(module) -> None:
    """Register an extra report module (must expose a `build(root, ...)`). Idempotent."""
    if module not in _EXTRA_REPORTS:
        _EXTRA_REPORTS.append(module)


def all_reports() -> tuple:
    """Canonical render order: the 6 base reports + any runtime-registered extras."""
    from . import (
        draws_by_class,
        trend_table,
        instancing_opportunities,
        pass_gpu,
        shader_hotlist,
        overdraw,
    )
    base = (
        draws_by_class,
        trend_table,
        instancing_opportunities,
        pass_gpu,
        shader_hotlist,
        overdraw,
    )
    extras = tuple(m for m in _EXTRA_REPORTS if m not in base)
    return base + extras
