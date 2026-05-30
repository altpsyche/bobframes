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
    chrome_css,
    class_color_var,
    components_js,
    design_tokens_css,
    footer_legend,
    h,
    header,
    icon,
    kpi_chip,
    kpi_strip,
    legend,
    link,
    page_close,
    page_open,
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
from .discovery import (
    DropRow,
    DropSet,
    discover_drops,
    ok_capture_set,
    resolve_drop_set,
)
from .cache import (
    _read_drop_parquet,
    build_per_drop_cache,
    cache_dir,
    cache_path,
    label_for,
    load_global_entities,
    load_labels,
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
    write_report,
)


__all__ = [
    # chrome
    'DRAW_CLASSES', 'ab_picker', 'ab_picker_for', 'ab_strip',
    'chrome_css', 'class_color_var',
    'components_js', 'design_tokens_css', 'footer_legend', 'h', 'header',
    'icon', 'kpi_chip', 'kpi_strip', 'legend', 'link',
    'page_close', 'page_open', 'section_card', 'summary_bar',
    # formatters
    'fmt_bytes', 'fmt_float', 'fmt_id_short', 'fmt_int', 'fmt_pct',
    'mesh_hash_short', 'pass_short', 'pass_suffix', 'safe_chrome_text',
    'trunc_left', 'trunc_mid',
    # delta
    'class_segments_bar', 'delta_cell', 'delta_pill', 'inline_bar',
    'rank_pill', 'sparkline_svg',
    # discovery
    'DropRow', 'DropSet', 'discover_drops', 'ok_capture_set', 'resolve_drop_set',
    # cache
    'build_per_drop_cache', 'cache_dir', 'cache_path', 'label_for',
    'load_global_entities', 'load_labels',
    # cli
    '_lint_or_raise', 'ab_subdir', 'crumb_depth', 'now_iso',
    'output_path', 'rel_path_to_drop_file', 'rel_path_to_drop_index',
    'run_report', 'write_report',
]
