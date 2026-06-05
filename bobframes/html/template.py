"""Per-drop data browser HTML + root cross-drop directory HTML.

Tables render via virtual scrolling: data ships as JSON in <script> blocks,
JS renders only the rows visible inside each scroll container, so the DOM
stays cheap regardless of dataset size. Sort/filter rebuild the visible
window in O(window-size).

Resource ID cells are enriched with labels from `_resource_labels.json`
(e.g. `tex_id=2184` displays as `2184  SceneDepthZ`).

CSS and JS are inlined for self-contained file:// browsing.
"""

from __future__ import annotations

import csv
import html as _html
import json
import os
from importlib.resources import files as _files
from typing import Iterable

import pyarrow.parquet as papq

from .. import paths as _paths
from .. import schemas
from ..reports import base as reports_base


def _read_asset(name: str) -> str:
    """Read a bundled CSS asset from reports/assets/ (c16x-1; see chrome._read_asset).

    The catalog/drill family's own CSS segment (_PER_DROP_CSS) lives as a real `.css` file alongside
    the report-family assets; it stays COMPOSED by this module's _compose_css (composition isolation,
    ADR-23) -- only its source moved out of a Python string literal.
    """
    return _files('bobframes.reports').joinpath('assets', name).read_text(encoding='utf-8')


# Category ASSIGNMENT now lives on schemas.TABLES[*].category (H-11). What stays here is the
# presentation-only WITHIN-category display order for the per-drop drill browser.
#
# D-9 (origin, recovered + recorded): this is a deliberate EDITORIAL "what a perf engineer reads
# first" ordering, NOT a derivable one - it matches neither the registry key order nor the catalog
# order (both effectively insertion/alpha), so it cannot be reconstructed from TABLES iteration.
# Within-category intent:
#   - aggregates: most-summary first (whole-pass timing -> class breakdown -> frame totals -> texture)
#   - entities:   most-inspected GPU resources first (shaders/textures), housekeeping last (fbos)
#   - actions:    the primary action (draws) first, then bindings/events/state, rare/derived last
#   - samples:    vertex-pipeline flow (vbo -> ibo -> post-VS -> textures -> pixel history)
# It is a relevance judgment, so there is no rule to derive. A NEW table absent from this tuple sorts
# to its category's TAIL (insert it at the relevance-appropriate spot to place it sooner). The order
# is gated by the HTML golden (drill page), so an accidental reshuffle fails parity.
_TABLE_DISPLAY_ORDER = (
    # aggregates
    'passes', 'pass_class_breakdown', 'frame_totals', 'texture_usage',
    # entities
    'shaders', 'textures', 'render_targets', 'programs', 'samplers', 'buffers', 'fbos',
    # actions
    'draws', 'draw_bindings', 'events', 'clears', 'dispatches', 'state_change_events',
    'vertex_inputs', 'indirect_args', 'descriptor_access', 'rt_event_timeline',
    'program_transitions', 'resource_creation', 'counters_per_event',
    # samples
    'vbo_samples', 'ibo_samples', 'post_vs_samples', 'texture_samples', 'pixel_history',
)
_DISPLAY_RANK = {name: i for i, name in enumerate(_TABLE_DISPLAY_ORDER)}
_CATEGORY_ORDER = ['aggregates', 'entities', 'actions', 'samples', 'sidecars']
_DEFAULT_OPEN = {'aggregates'}


# Collapsible column groups for the wide root catalog (c16i, G-21). The catalog is a flat ~37-col
# wall of identity columns + one `row_count_<table>` per registered table. Groups are derived
# deterministically from schemas.table_category (reuses H-11) so they auto-extend when a table is
# added - no hand-maintained column list to drift. Metadata = the non-row_count identity/build
# columns; each row_count_<table> buckets by its table's schema category. Default-open: Metadata +
# Workload (Resources + Samples collapse to break the wall). Drill tables are NOT grouped (they
# already collapse per-table via <details class="category">).
_CATALOG_GROUP_ORDER = ('Metadata', 'Workload', 'Resources', 'Samples')
_CATALOG_GROUP_OPEN = ('Metadata', 'Workload')
_CATEGORY_TO_CATALOG_GROUP = {
    'actions': 'Workload',
    'aggregates': 'Workload',
    'entities': 'Resources',
    'samples': 'Samples',
}


def _catalog_col_groups(cols: list[str]) -> list[dict]:
    """Deterministic group -> column map for the catalog VTable, in display order.

    `Metadata` holds every non-`row_count_` column; each `row_count_<table>` column is bucketed by
    `schemas.table_category(table)` (unknown tables fall back to Workload). Empty groups are
    dropped. Returned shape: ``[{'name', 'open', 'cols': [...]}, ...]`` - emitted as inline JSON
    and consumed by the VTable to build the toggle bar (catalog only).
    """
    buckets: dict[str, list[str]] = {name: [] for name in _CATALOG_GROUP_ORDER}
    for c in cols:
        if c.startswith('row_count_'):
            table = c[len('row_count_'):]
            try:
                cat = schemas.table_category(table)
            except KeyError:
                cat = 'actions'
            group = _CATEGORY_TO_CATALOG_GROUP.get(cat, 'Workload')
        else:
            group = 'Metadata'
        buckets[group].append(c)
    return [{'name': name, 'open': name in _CATALOG_GROUP_OPEN, 'cols': buckets[name]}
            for name in _CATALOG_GROUP_ORDER if buckets[name]]


# Map of (table_name, column_name) -> resource kind key in _resource_labels.json
_LABEL_COLS: dict[str, dict[str, str]] = {
    'draws': {
        'program_id': 'program',
        'vs_shader_id': 'shader',
        'fs_shader_id': 'shader',
        'depth_rt_id': 'texture',
        'color_rt_ids': 'texture_list',  # semicolon-joined
        'ibo_id': 'buffer',
    },
    'draw_bindings': {
        # resource_id meaning depends on slot_kind; resolved in JS
        'resource_id': 'auto_by_slot_kind',
        'sampler_id': 'sampler',
    },
    'passes': {
        'color_rt_id_first': 'texture',
        'depth_rt_id_first': 'texture',
    },
    'shaders': {
        # shader_id self-references; no need.
    },
    'render_targets': {
        # has its own label column already
    },
    'textures': {},
    'programs': {
        'vs_shader_id': 'shader',
        'fs_shader_id': 'shader',
        'cs_shader_id': 'shader',
    },
    'samplers': {},
    'fbos': {
        'resource_id': 'texture',
    },
    'events': {
        'output_color_rt_id': 'texture',
        'output_depth_rt_id': 'texture',
        'copy_source_id': 'texture',
        'copy_destination_id': 'texture',
    },
    'clears': {
        'fbo_id': 'fbo',
    },
    'dispatches': {
        'program_id': 'program',
        'cs_shader_id': 'shader',
    },
    'rt_event_timeline': {
        'rt_id': 'texture',
    },
    'descriptor_access': {
        'resource_id': 'auto_by_kind',
    },
    'pixel_history': {
        'rt_id': 'texture',
    },
    'texture_usage': {
        'tex_id': 'texture',
    },
    'pass_class_breakdown': {},
    'program_transitions': {
        'from_program_id': 'program',
        'to_program_id': 'program',
    },
    'state_change_events': {},
    'indirect_args': {
        'indirect_buffer_id': 'buffer',
    },
    'vertex_inputs': {
        'buffer_id': 'buffer',
    },
    'resource_creation': {},
    'counters_per_event': {},
    'frame_totals': {},
    'vbo_samples': {'buffer_id': 'buffer'},
    'ibo_samples': {'buffer_id': 'buffer'},
    'post_vs_samples': {},
    'texture_samples': {'tex_id': 'texture'},
}


# Drill/catalog-only chrome (c16k: the table.data engine CSS + col-groups + the table-var :root block
# moved to reports/chrome._RDC_TABLE_CSS so one class serves both modes; reports never load this
# remainder, so their goldens stay byte-stable). What stays here is catalog/drill page chrome: the
# wide-body width, the toc/controls, the .table-scroll virtual container + loading hint, the sidecar
# list, and the per-drop visual hierarchy (category label/rail + table-section cards).
_PER_DROP_CSS = _read_asset('per_drop.css')


def _compose_css() -> str:
    return (reports_base.design_tokens_css()
            + reports_base.chrome_css()
            + reports_base.rdc_table_css()
            + _PER_DROP_CSS)


_CSS = _compose_css()


# The catalog/drill family's asset manifest + head-asset seam (c16r, ADR-41). Distinct from the report
# family's REPORT_ASSETS (chrome.py): catalog.css is `_CSS` served UN-minified (the c16i substring
# guards parse it raw) and the engine JS sits at body-end, not in `<head>`. The (filename -> content)
# pairing lives ONCE here; head_assets(REF) links from it and c16t writes the files from it.
CATALOG_ASSETS = (
    reports_base.AssetFile('catalog.css', 'css', lambda: _CSS),
    reports_base.AssetFile('catalog.js', 'js', reports_base.rdc_table_js),
)


def head_assets(sink: reports_base.AssetSink, depth: int = 0) -> reports_base.HeadAssets:
    """The catalog/drill family's head-asset markup for `sink` (c16r, ADR-41).

    INLINE reproduces today's exact bytes: `<style>{_CSS}</style>` in the head and the engine
    `<script>{rdc_table_js()}</script>` at body-end (so `head` + `body_js` are placed at their two
    distinct document positions by the caller). REF emits depth-relative `_assets/catalog.{css,js}`
    built from CATALOG_ASSETS (the css `<link>` in the head, the deferred js script at body-end).
    """
    if sink is reports_base.AssetSink.INLINE:
        return reports_base.HeadAssets(
            head=f'<style>{_CSS}</style>',
            body_js=f'<script>{reports_base.rdc_table_js()}</script>',
        )
    prefix = reports_base.assets_prefix(depth)
    css = next(a for a in CATALOG_ASSETS if a.kind == 'css')
    js = next(a for a in CATALOG_ASSETS if a.kind == 'js')
    return reports_base.HeadAssets(head=css.ref_link(prefix), body_js=js.ref_link(prefix))


# The virtual-scroll table engine moved to reports/chrome.py as the unified `rdc-table` (c16k,
# ADR-38): one bespoke engine serves BOTH the catalog/drill virtual mode (windowed, data from
# _pagedata/*.js) and the reports' static mode (server-baked rows, JS enhances in place). Catalog
# and drill now emit `<rdc-table data-mode="virtual">` hosts + `reports_base.rdc_table_js()`; the
# `table.data`/col-groups/type-split/heatmap CSS lives in `reports_base.rdc_table_css()`. ROW_H is
# single-sourced there (chrome._RDC_ROW_H). Drill-only chrome stays in _PER_DROP_CSS_REMAINDER below.


def _h(s) -> str:
    return _html.escape(str(s if s is not None else ''))


def _table_payload(table_name: str, out_dir: str) -> dict | None:
    pq = os.path.join(out_dir, f'{table_name}.parquet')
    if not os.path.exists(pq):
        return None
    t = papq.read_table(pq)
    if t.num_rows == 0:
        return None
    cols = t.column_names
    # Build rows as a list-of-lists. Pyarrow's to_pylist on a Table doesn't
    # exist; use per-column extraction.
    arrays = [t.column(c).to_pylist() for c in cols]
    n = t.num_rows
    rows = [[arrays[ci][ri] for ci in range(len(cols))] for ri in range(n)]
    label_cols = _LABEL_COLS.get(table_name, {})
    return {'cols': cols, 'rows': rows, 'labelCols': label_cols}


def _write_page_data(pagedata_dir: str, key: str, payload: dict) -> str:
    """Externalize one VTable payload to ``<pagedata_dir>/<key>.js`` (c16j, ADR-37).

    The heavy ``window.__data_<key>={...}`` formerly inlined in the page is written here as its own
    classic, file://-safe script file, referenced by a ``<script defer src>``. Same compact
    ``json.dumps`` as the inline form -> identical bytes, just relocated; LF newline matches the golden.
    Returns the page-relative ``src`` (always one level down: ``_pagedata/<key>.js``).
    """
    os.makedirs(pagedata_dir, exist_ok=True)
    body = f'window.__data_{key}={json.dumps(payload, separators=(",", ":"))};\n'
    with open(os.path.join(pagedata_dir, f'{key}.js'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    return f'{_paths.PAGEDATA_DIR}/{key}.js'


def _inline_table_with_data(table_name: str, out_dir: str,
                             sidecar_rel: str = '.') -> tuple[str, str, dict] | None:
    """Returns (section_html, table_name, payload) or None if table empty.

    The heavy row payload is NOT inlined here (c16j); the caller writes it to a ``_pagedata/<table>.js``
    via ``_write_page_data`` and emits a ``<script defer src>`` ref, so the HTML shell paints first.

    sidecar_rel: relative path from rendered HTML to the data dir, used to
    construct CSV/parquet download links. Default '.' for legacy callers
    where HTML lives next to data.
    """
    payload = _table_payload(table_name, out_dir)
    if payload is None:
        return None
    n_total = len(payload['rows'])
    n_cols = len(payload['cols'])

    prefix = '' if sidecar_rel in ('.', '') else sidecar_rel.rstrip('/') + '/'

    section = []
    section.append(f'<section class="table-section" id="{table_name}">')
    section.append('<header class="table-header">')
    section.append(f'<h2>{_h(table_name)}</h2>')
    section.append(f'<span class="table-meta">{n_total:,} rows, {n_cols} cols</span>')
    section.append('</header>')
    section.append('<div class="controls">')
    section.append(f'<input type="search" aria-label="filter {table_name}" placeholder="filter {table_name}...">')
    section.append('<span class="ct visible-count"></span>')
    section.append(f'<a class="dl" href="{prefix}{table_name}.csv">CSV</a>')
    section.append(f'<a class="dl" href="{prefix}{table_name}.parquet">parquet</a>')
    section.append('</div>')
    section.append(f'<rdc-table class="table-scroll" data-mode="virtual" data-table="{table_name}"></rdc-table>')
    section.append('</section>')

    return '\n'.join(section), table_name, payload


def _categorize(table_specs: list[tuple[str, int, int]]) -> dict:
    """Return {category: [(name, n_rows, n_cols), ...]} in display order.

    Category membership comes from schemas.TABLES[*].category (a table unknown to the registry
    falls back to 'actions'); within a category, specs sort by _DISPLAY_RANK, with any unranked
    (newly registered) table tailing in TABLES order.
    """
    by_cat: dict[str, list] = {cat: [] for cat in _CATEGORY_ORDER if cat != 'sidecars'}
    for spec in table_specs:
        name = spec[0]
        try:
            cat = schemas.table_category(name)
        except KeyError:
            cat = 'actions'
        by_cat.setdefault(cat, []).append(spec)
    tail = len(_TABLE_DISPLAY_ORDER)
    for specs in by_cat.values():
        specs.sort(key=lambda s: _DISPLAY_RANK.get(s[0], tail))
    return by_cat


def _toc(by_cat: dict) -> str:
    """Category-aware TOC. Each category links to its <details> anchor."""
    parts = ['<nav class="toc">']
    for cat in _CATEGORY_ORDER:
        if cat == 'sidecars':
            parts.append(f'<a href="#cat-sidecars"><span>sidecars</span></a>')
            continue
        items = by_cat.get(cat, [])
        if not items:
            continue
        total_rows = sum(r for _, r, _ in items)
        parts.append(f'<a href="#cat-{_h(cat)}"><span>{_h(cat)}</span>'
                     f'<span class="ct">{len(items)}t, {total_rows:,}r</span></a>')
    parts.append('</nav>')
    return '\n'.join(parts)


def _category_block(cat: str, items: list, table_sections: dict,
                    is_open: bool) -> str:
    """Render <details class='category'> wrapping its table sections."""
    if not items:
        return ''
    total_rows = sum(r for _, r, _ in items)
    open_attr = ' open' if is_open else ''
    parts = [
        f'<details class="category" id="cat-{_h(cat)}"{open_attr}>',
        '<summary>',
        f'<span class="cat-name">{_h(cat)}</span>',
        f'<span class="cat-meta">{len(items)} tables, {total_rows:,} rows</span>',
        '</summary>',
        '<div class="cat-body">',
    ]
    for name, _, _ in items:
        sec_html = table_sections.get(name)
        if sec_html:
            parts.append(sec_html)
    parts.append('</div></details>')
    return '\n'.join(parts)


def _sidecar_category(out_dir: str, sidecar_rel: str = '.') -> str:
    """Render the sidecars category as <details class='category'>.

    sidecar_rel: relative path from rendered HTML to data dir, used to
    construct download links. Default '.' for legacy callers.
    """
    body_parts = []
    counts = []
    prefix = '' if sidecar_rel in ('.', '') else sidecar_rel.rstrip('/') + '/'

    src_dir = os.path.join(out_dir, 'shader_src')
    if os.path.isdir(src_dir):
        files = os.listdir(src_dir)
        files.sort(key=lambda f: int(f.split('.', 1)[0]) if f.split('.', 1)[0].isdigit() else 0)
        counts.append(f'shader_src {len(files)}')
        body_parts.append(f'<h3>shader_src ({len(files)} files)</h3>')
        body_parts.append('<ul class="sidecar-list">')
        for f in files:
            body_parts.append(f'<li><a href="{prefix}shader_src/{_h(f)}">{_h(f)}</a></li>')
        body_parts.append('</ul>')

    hist_dir = os.path.join(out_dir, 'histogram')
    if os.path.isdir(hist_dir):
        files = sorted(os.listdir(hist_dir))
        if files:
            counts.append(f'histogram {len(files)}')
            body_parts.append(f'<h3>histogram ({len(files)} files)</h3>')
            body_parts.append('<ul class="sidecar-list">')
            for f in files:
                body_parts.append(f'<li><a href="{prefix}histogram/{_h(f)}">{_h(f)}</a></li>')
            body_parts.append('</ul>')

    for jsonl in ('frame_metadata.jsonl', 'uniforms_per_pass.jsonl'):
        p = os.path.join(out_dir, jsonl)
        if os.path.exists(p):
            counts.append(jsonl)
            body_parts.append(f'<h3>{_h(jsonl)}</h3>')
            body_parts.append(f'<p><a href="{prefix}{_h(jsonl)}">download</a></p>')

    if not body_parts:
        return ''

    meta = ' / '.join(counts)
    return ('<details class="category" id="cat-sidecars">'
            '<summary>'
            '<span class="cat-name">sidecars</span>'
            f'<span class="cat-meta">{_h(meta)}</span>'
            '</summary>'
            '<div class="cat-body">'
            + '\n'.join(body_parts)
            + '</div></details>')


def _read_gl_renderer(out_dir: str) -> str:
    p = os.path.join(out_dir, 'frame_metadata.jsonl')
    if not os.path.exists(p):
        return ''
    try:
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                s = o.get('gl_renderer_string') or o.get('gl_renderer') or ''
                if s:
                    return s
    except OSError:
        pass
    return ''


def render_drop(drill_dir: str, *, data_dir: str,
                area: str, drop_date: str, drop_label: str,
                captures: list[str], schema_version: int, build_timestamp: str,
                row_counts: dict[str, int],
                sink: reports_base.AssetSink = reports_base.AssetSink.INLINE,
                depth: int = 0, redact: bool = False) -> str:
    """Render the per-drop browser HTML into drill_dir, reading data from data_dir.

    drill_dir: <root>/_reports/drill/<area>/<drop>/  (HTML output target)
    data_dir:  <root>/_data/<area>/<drop>/           (parquet + sidecars source)

    Returns path to drill_dir/index.html. Sidecar links (shader_src, histogram)
    point at data_dir via relative path.
    """
    total_rows = sum(row_counts.values())

    table_specs: list[tuple[str, int, int]] = []
    for table_name, n in sorted(row_counts.items()):
        if n <= 0:
            continue
        pq = os.path.join(data_dir, f'{table_name}.parquet')
        if not os.path.exists(pq):
            continue
        n_cols = len(papq.read_schema(pq).names)
        table_specs.append((table_name, n, n_cols))

    # Load labels sidecar (small JSON) from data_dir
    labels_path = os.path.join(data_dir, '_resource_labels.json')
    labels_json = '{}'
    if os.path.exists(labels_path):
        with open(labels_path, 'r', encoding='utf-8') as f:
            labels_json = f.read()

    drop_key = f'{drop_date}_{drop_label}' if drop_label else drop_date
    gl_renderer = _read_gl_renderer(data_dir)

    kpis = [
        {'label': 'rows total',  'value': reports_base.fmt_int(total_rows)},
        {'label': 'captures',    'value': reports_base.fmt_int(len(captures))},
        {'label': 'tables',      'value': reports_base.fmt_int(len(table_specs))},
    ]

    # Chrome CSS/JS routed through the c16r head_assets seam (ADR-41); INLINE is byte-identical to the
    # pre-c16r inline `<style>` (head) + body-end engine `<script>` (the two are spliced at their own
    # document positions: ha.head here, ha.body_js just before </body>).
    # c16t: sink=REF (depth-relative `_assets/`) is reachable for `package`; INLINE ignores depth.
    ha = head_assets(sink, depth)
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">']
    parts.append(f'<title>{_h(area)} {_h(drop_date)}</title>')
    parts.append(f'<link rel="icon" href="{reports_base._FAVICON_HREF}">')
    parts.append(f'{ha.head}</head>'
                 f'<body data-page-kind="drop-browser" style="--hdr-offset: 120px">')

    parts.append(f'<h1>{_h(area)} / {_h(drop_key)}</h1>')
    parts.append('<header class="strip">')
    parts.append(f'<span>area <strong>{_h(area)}</strong></span>')
    parts.append(f'<span>drop <strong>{_h(drop_key)}</strong></span>')
    parts.append(f'<span>rows <strong>{total_rows:,}</strong></span>')
    parts.append(f'<span>built <strong>{_h(build_timestamp)}</strong></span>')
    parts.append('</header>')
    # drill_dir = <root>/_reports/drill/<area>/<drop>/ → up 4 to reach <root>
    parts.append('<nav class="crumb">'
                 '<a href="../../../../index.html" data-link-kind="crumb">root catalog</a>'
                 '<a href="../../../index.html" data-link-kind="crumb">dashboard</a>'
                 '</nav>')

    # Summary bar: per-drop aggregates
    n_passes = row_counts.get('passes', 0)
    n_draws = row_counts.get('draws', 0)
    parts.append(reports_base.summary_bar(
        'this drop',
        f'{_h(area)} / {_h(drop_key)}',
        sub=f'{reports_base.fmt_int(n_draws)} draws; {reports_base.fmt_int(n_passes)} passes; {reports_base.fmt_int(len(captures))} captures',
        tone='neutral',
    ))

    if gl_renderer:
        # c16u: gl_renderer is device info -> scrub at the data seam under --redact (ADR-40).
        parts.append('<div class="device-strip">redacted</div>' if redact
                     else f'<div class="device-strip">{_h(gl_renderer)}</div>')

    parts.append(reports_base.kpi_strip(kpis))

    by_cat = _categorize(table_specs)
    parts.append(_toc(by_cat))

    # Compute relative path from drill_dir → data_dir for sidecar/shader_src links.
    data_rel = os.path.relpath(data_dir, drill_dir).replace('\\', '/')

    pagedata_dir = os.path.join(drill_dir, _paths.PAGEDATA_DIR)
    table_sections: dict[str, str] = {}
    data_refs: list[str] = []
    for name, _, _ in table_specs:
        result = _inline_table_with_data(name, data_dir, sidecar_rel=data_rel)
        if result is None:
            continue
        sec, key, payload = result
        table_sections[name] = sec
        src = _write_page_data(pagedata_dir, key, payload)
        data_refs.append(f'<script defer src="{src}"></script>')

    for cat in _CATEGORY_ORDER:
        if cat == 'sidecars':
            sidecar_html = _sidecar_category(data_dir, sidecar_rel=data_rel)
            if sidecar_html:
                parts.append(sidecar_html)
            continue
        block = _category_block(cat, by_cat.get(cat, []), table_sections,
                                 is_open=(cat in _DEFAULT_OPEN))
        if block:
            parts.append(block)

    parts.append(f'<script>window.__labels={labels_json};</script>')
    parts.extend(data_refs)
    parts.append(ha.body_js)
    parts.append('</body></html>')

    out_path = os.path.join(drill_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return out_path


def render_root(root: str, *, sink: reports_base.AssetSink = reports_base.AssetSink.INLINE) -> str:
    # c16t (ADR-41): ``sink=REF`` emits depth-relative ``_assets/`` links (the root page is at the
    # bundle root, depth 0); `package` shared mode re-renders the whole tree (root included) with REF
    # into a staging copy. INLINE (the default) is byte-identical to today.
    cat_pq = _paths.catalog_parquet(root)
    cat_json = _paths.catalog_json(root)
    root_index = _paths.root_index_html(root)
    if not os.path.exists(cat_pq):
        with open(root_index, 'w', encoding='utf-8') as f:
            f.write('<!doctype html><html><body>no catalog yet</body></html>')
        return root_index

    t = papq.read_table(cat_pq)
    summary = {}
    if os.path.exists(cat_json):
        with open(cat_json, 'r', encoding='utf-8') as f:
            summary = json.load(f)

    cols = t.column_names
    arrays = [t.column(c).to_pylist() for c in cols]
    n = t.num_rows
    rows = [[arrays[ci][ri] for ci in range(len(cols))] for ri in range(n)]

    # analysis_out_path column stored relative under _data/. Transform link
    # target to the per-drop browser at _reports/drill/<area>/<drop>/index.html.
    path_idx = cols.index('analysis_out_path') if 'analysis_out_path' in cols else -1
    if path_idx >= 0:
        for r in rows:
            v = str(r[path_idx])
            # Replace leading "_data/" with "_reports/drill/" and append index.html.
            if v.startswith(_paths.DATA_DIR + '/') or v.startswith(_paths.DATA_DIR + '\\'):
                drill_rel = (_paths.REPORTS_DIR + '/' + _paths.DRILL_DIR + '/'
                             + v[len(_paths.DATA_DIR) + 1:].replace('\\', '/'))
            elif os.path.isabs(v):
                drill_rel = os.path.relpath(
                    _paths.drop_dir_to_drill_dir(v), root).replace('\\', '/')
            else:
                drill_rel = v.replace('\\', '/')
            r[path_idx] = drill_rel.rstrip('/') + '/index.html'

    payload = {'cols': cols, 'rows': rows, 'labelCols': {}}

    # Chrome CSS/JS via the c16r head_assets seam (ADR-41); INLINE byte-identical (ha.head in the
    # head, ha.body_js at body-end before </body>).
    ha = head_assets(sink, 0)
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">']
    parts.append('<title>capture analysis catalog</title>')
    parts.append(f'<link rel="icon" href="{reports_base._FAVICON_HREF}">')
    parts.append(f'{ha.head}</head><body style="--hdr-offset: 120px">')
    parts.append('<header class="strip">')
    parts.append(f'<span>built <strong>{_h(summary.get("build_timestamp", ""))}</strong></span>')
    parts.append(f'<span>drops <strong>{summary.get("drop_count", 0)}</strong></span>')
    parts.append('</header>')

    # Summary bar: latest drop + area/capture counts
    area_idx = cols.index('area') if 'area' in cols else -1
    date_idx = cols.index('drop_date') if 'drop_date' in cols else -1
    label_idx = cols.index('drop_label') if 'drop_label' in cols else -1
    unique_areas: set = set()
    latest_date = ''
    latest_label = ''
    for r in rows:
        if area_idx >= 0 and r[area_idx]:
            unique_areas.add(str(r[area_idx]))
        if date_idx >= 0 and r[date_idx]:
            dval = str(r[date_idx])
            if dval > latest_date:
                latest_date = dval
                latest_label = str(r[label_idx]) if label_idx >= 0 else ''
    if latest_date:
        head_text = f'{latest_date}'
        if latest_label:
            head_text = f'{latest_date} / {latest_label}'
        parts.append(reports_base.summary_bar(
            'latest drop',
            head_text,
            sub=f'{len(unique_areas)} areas; {n} catalog rows',
            link_href=f'{_paths.REPORTS_DIR}/{_paths.INDEX_HTML}',
            link_text='dashboard',
            tone='neutral',
        ))

    # Reports section
    reports_dir = _paths.reports_dir(root)
    if os.path.isdir(reports_dir):
        dashboard = os.path.join(reports_dir, _paths.INDEX_HTML)
        if os.path.exists(dashboard):
            # c16q: promote the exec build-health one-pager (when present) ahead of the dashboard, and
            # EXCLUDE it from the auto-listed report grid below (mirrors the INDEX_HTML exclusion) so
            # the landing surfaces lead, not an alphabetised file row.
            chips = []
            if os.path.exists(os.path.join(reports_dir, 'summary.html')):
                chips.append(f'<a href="{_paths.REPORTS_DIR}/summary.html" '
                             'data-link-kind="primary">build health summary</a>')
            chips.append(f'<a href="{_paths.REPORTS_DIR}/{_paths.INDEX_HTML}" '
                         'data-link-kind="primary">cumulative reports dashboard</a>')
            parts.append('<section><h2 id="dashboard">dashboard</h2>'
                         '<div class="chip-cluster">' + ''.join(chips) + '</div></section>')

        report_files = sorted(
            f for f in os.listdir(reports_dir)
            if f.endswith('.html') and f not in (_paths.INDEX_HTML, 'summary.html')
        )
        if report_files:
            parts.append('<section><h2 id="reports">reports</h2>'
                         '<div class="catalog-grid">')
            for f in report_files:
                parts.append(f'<a href="{_paths.REPORTS_DIR}/{_h(f)}" data-link-kind="primary">'
                             f'{_h(f[:-5])}</a>')
            parts.append('</div></section>')

        ab_dir = os.path.join(reports_dir, _paths.AB_DIR)
        if os.path.isdir(ab_dir):
            pairs = sorted(
                d for d in os.listdir(ab_dir)
                if os.path.isdir(os.path.join(ab_dir, d))
            )
            if pairs:
                parts.append('<section><h2 id="ab">a/b comparisons</h2>'
                             '<div class="pair-list">')
                for pair in pairs:
                    pair_files = sorted(
                        f for f in os.listdir(os.path.join(ab_dir, pair))
                        if f.endswith('.html')
                    )
                    chips = ''.join(
                        f'<a href="{_paths.REPORTS_DIR}/{_paths.AB_DIR}/{_h(pair)}/{_h(f)}" data-link-kind="primary">'
                        f'{_h(f[:-5])}</a>'
                        for f in pair_files
                    )
                    parts.append(
                        f'<div class="pair-group">'
                        f'<h3>{_h(pair)}</h3>'
                        f'<div class="chip-cluster">{chips}</div>'
                        f'</div>'
                    )
                parts.append('</div></section>')

    parts.append('<section><h2>catalog</h2>')
    parts.append('<div class="controls">')
    parts.append('<input type="search" aria-label="filter catalog" placeholder="filter">')
    parts.append('<span class="ct visible-count"></span>')
    parts.append(f'<a class="dl" href="{_paths.DATA_DIR}/_catalog.csv" data-link-kind="inline">CSV</a>')
    parts.append(f'<a class="dl" href="{_paths.DATA_DIR}/_catalog.parquet" data-link-kind="inline">parquet</a>')
    parts.append('</div>')
    # Empty container for the column-group toggle bar; the buttons are built client-side from
    # window.__colgroups_catalog (c16i). Catalog only - drill pages emit neither.
    parts.append('<div class="col-groups" role="group" aria-label="column groups"></div>')
    parts.append(f'<rdc-table class="table-scroll" data-mode="virtual" data-table="catalog"></rdc-table>')
    parts.append('</section>')

    catalog_src = _write_page_data(os.path.join(root, _paths.PAGEDATA_DIR), 'catalog', payload)
    parts.append(f'<script defer src="{catalog_src}"></script>')
    parts.append('<script>window.__colgroups_catalog='
                 f'{json.dumps(_catalog_col_groups(cols), separators=(",", ":"))};</script>')
    parts.append(f'<script>window.__labels={{}};</script>')
    parts.append(ha.body_js)
    parts.append('</body></html>')

    out_path = root_index
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return out_path
