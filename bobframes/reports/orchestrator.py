"""Coordinate cache build + per-report build + dashboard + root-index render."""

from __future__ import annotations

import time

from .. import lint
from ..config import get_config
from ..html import template
from . import (
    all_reports,
    dashboard as report_dashboard,
    base as reports_base,
    trend_table as report_trend_table,
)


def render_all_reports(root: str, log, *,
                       sink: reports_base.AssetSink = reports_base.AssetSink.INLINE,
                       build_ts: str | None = None, redact: bool = False) -> int:
    """Build cache, every registered report, dashboard, root index. Returns 0 on success.

    Top-level pages report the newest run (the run model default, ADR-35). c16f then pre-renders a
    page set per OLDER run under _reports/run/<key>/ (the run selector links to them), bounded by
    [report] max_prerendered_runs so history does not explode the page count.

    ``sink``/``build_ts`` (c16t, ADR-41): `package` re-renders the whole tree with ``sink=REF`` (the
    shared-asset form) into a staging copy and pins ``build_ts`` (the run date) so two packages are
    byte-identical. ``redact`` (c16u, ADR-40): `package --redact` re-emits every page's device/host
    provenance strip as ``redacted`` from the manifest. All three default to today's behavior -> the
    normal render path stays byte-identical.
    """
    t0 = time.monotonic()
    cache_out = reports_base.build_per_drop_cache(root)
    log(f'  built per-drop cache: {cache_out} ({time.monotonic()-t0:.1f}s)')

    for mod in all_reports():
        try:
            rep = mod.build(root, sink=sink, build_ts=build_ts, redact=redact)
            log(f'  built report: {rep}')
        except Exception as e:
            log(f'  {mod.__name__} FAILED: {e}')
            return 1

    try:
        dash = report_dashboard.build(root, sink=sink, build_ts=build_ts, redact=redact)
        log(f'  built dashboard: {dash}')
    except Exception as e:
        log(f'  dashboard FAILED: {e}')
        return 1

    # c16f: per-run page set for each OLDER run (newest is the top-level default above). trend_table is
    # excluded - it is the across-run matrix, not a single-run snapshot. Bounded + logged (ADR-23).
    drops = reports_base.discover_drops(root)
    if len(drops) > 1:
        cap = get_config().report.max_prerendered_runs
        newest_key = drops[-1].key
        older = [d for d in reports_base.prerendered_runs(drops, cap) if d.key != newest_key]
        skipped = (len(drops) - 1) - len(older)
        if skipped > 0:
            log(f'  per-run pages: capped at {cap} older runs; {skipped} older run(s) omitted '
                f'(reachable via trend_table)')
        per_run_mods = [m for m in all_reports() if m is not report_trend_table]
        for d in older:
            for mod in per_run_mods:
                try:
                    mod.build(root, run_label=d.label, run_date=d.date,
                              sink=sink, build_ts=build_ts, redact=redact)
                except Exception as e:
                    log(f'  {mod.__name__} (run {d.key}) FAILED: {e}')
                    return 1
            try:
                report_dashboard.build(root, run_label=d.label, run_date=d.date,
                                       sink=sink, build_ts=build_ts, redact=redact)
            except Exception as e:
                log(f'  dashboard (run {d.key}) FAILED: {e}')
                return 1
        if older:
            log(f'  built per-run pages for {len(older)} older run(s)')

    log('rendering root index')
    root_idx = template.render_root(root, sink=sink)
    root_hits = lint.lint_file(root_idx)
    if root_hits:
        for lineno, label, snip in root_hits:
            log(f'  LINT FAIL {root_idx}:{lineno}: [{label}] {snip}')
        return 1
    log(f'  -> {root_idx}')
    return 0
