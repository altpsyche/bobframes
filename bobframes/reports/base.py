"""Shared chrome for Layer 2 reports.

This module is now a thin facade re-exporting from the topic modules below.
Existing reports keep `from . import base` working unchanged.

Topic modules:
- chrome: CSS tokens, page open/close, header, KPI strip, section card, legend, footer, ab_strip
- formatters: fmt_int/float/pct/bytes/id_short, mesh_hash_short, trunc_mid/left, safe_chrome_text
- delta: delta_cell, delta_pill, rank_pill, inline_bar, class_segments_bar, sparkline_svg
- discovery: DropRow, DropSet, discover_drops, resolve_drop_set, ok_capture_set
- cache: load_global_entities, load_labels, label_for, cache_dir, cache_path, build_per_drop_cache
- cli: run_report, ab_subdir, output_path, now_iso, _lint_or_raise, write_report, crumb_depth, rel_path_to_drop_index, rel_path_to_drop_file
"""

from __future__ import annotations

from .chrome import (
    DRAW_CLASSES,
    _FAVICON_HREF,
    ab_picker,
    ab_picker_for,
    ab_strip,
    callout,
    chrome_css,
    class_color_var,
    clip_attrs,
    clip_span,
    components_js,
    design_tokens_css,
    empty_state,
    h,
    header,
    heatmap_cell,
    icon,
    kpi_chip,
    kpi_strip,
    legend,
    link,
    page_close,
    page_open,
    provenance_strip,
    rdc_table_css,
    rdc_table_js,
    report_page,
    run_compare_banner,
    run_picker,
    run_picker_for,
    section_card,
    summary_bar,
)
from .formatters import (
    _BANNED_CHROME_CHARS,
    fmt_bytes,
    fmt_float,
    fmt_id_short,
    fmt_int,
    fmt_pct,
    mesh_hash_short,
    pass_short,
    pass_suffix,
    safe_chrome_text,
    trunc_left,
    trunc_mid,
)
from .delta import (
    class_segments_bar,
    delta_cell,
    delta_pill,
    inline_bar,
    rank_pill,
    sparkline_svg,
)
from .charts import (
    bar_chart,
    donut,
    figure,
    histogram,
    icicle,
    line_chart,
    pct_stacked_bar,
    scatter,
    stacked_bar,
    treemap,
)
from .discovery import (
    DropRow,
    DropSet,
    RunContext,
    baseline_run,
    current_run,
    discover_drops,
    ok_capture_set,
    prerendered_runs,
    resolve_drop_set,
    run_context,
)
from .cache import (
    _read_drop_parquet,
    _to_dict_of_lists,
    build_per_drop_cache,
    cache_dir,
    cache_path,
    label_for,
    load_cached,
    load_global_entities,
    load_labels,
    newest_drop_provenance,
)
from .cli import (
    _lint_or_raise,
    ab_subdir,
    crumb_depth,
    now_iso,
    output_path,
    rel_path_to_drop_file,
    rel_path_to_drop_index,
    run_report,
    run_subdir,
    write_report,
)


__all__ = [
    # chrome
    'DRAW_CLASSES', 'ab_picker', 'ab_picker_for', 'ab_strip', 'callout',
    'chrome_css', 'class_color_var', 'clip_attrs', 'clip_span',
    'components_js', 'design_tokens_css', 'empty_state', 'h', 'header', 'heatmap_cell',
    'icon', 'kpi_chip', 'kpi_strip', 'legend', 'link',
    'page_close', 'page_open', 'provenance_strip',
    'rdc_table_css', 'rdc_table_js',
    'report_page', 'run_compare_banner',
    'run_picker', 'run_picker_for', 'section_card', 'summary_bar',
    'newest_drop_provenance',
    # formatters
    'fmt_bytes', 'fmt_float', 'fmt_id_short', 'fmt_int', 'fmt_pct',
    'mesh_hash_short', 'pass_short', 'pass_suffix', 'safe_chrome_text',
    'trunc_left', 'trunc_mid',
    # delta
    'class_segments_bar', 'delta_cell', 'delta_pill', 'inline_bar',
    'rank_pill', 'sparkline_svg',
    # charts (c16b, ADR-33)
    'bar_chart', 'donut', 'figure', 'histogram', 'icicle', 'line_chart',
    'pct_stacked_bar', 'scatter', 'stacked_bar', 'treemap',
    # discovery
    'DropRow', 'DropSet', 'RunContext', 'baseline_run', 'current_run',
    'discover_drops', 'ok_capture_set', 'prerendered_runs', 'resolve_drop_set',
    'run_context',
    # cache
    'build_per_drop_cache', 'cache_dir', 'cache_path', 'label_for',
    'load_cached', 'load_global_entities', 'load_labels',
    # cli
    '_lint_or_raise', 'ab_subdir', 'crumb_depth', 'now_iso',
    'output_path', 'rel_path_to_drop_file', 'rel_path_to_drop_index',
    'run_report', 'run_subdir', 'write_report',
]
