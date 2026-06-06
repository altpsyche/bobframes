"""c16x-4: the table component family (chrome.Column / data_table / static_table; ADR-42).

The rdc-table ENGINE is single-source (c16k/c16l), but its HOST markup was hand-written per report with
inconsistent attribute order / per-report cells / inline col-groups, so a byte-identical migration is
impossible. This is the NORMALIZED component the reports adopt in v0.2.6 (the golden refresh there
absorbs the normalization). It builds through el(), so cells escape by construction. These pin the
normalized output shape (golden-independent); no production site is migrated yet, so test_parity stays
green (verified separately).
"""
from __future__ import annotations

from bobframes.reports import chrome
from bobframes.reports.chrome import (Column, colgroups_from, data_table, static_table, el, _Raw,
                                       table_controls, virtual_host, virtual_table_section)
from bobframes.reports.delta import delta_column, delta_parts


def test_static_table_bare_shape_and_escaping():
    cols = [Column('name', 'name'), Column('draws', 'draws', numeric=True)]
    rows = [{'name': 'opaque', 'draws': '1,820'}, {'name': 'ui & hud', 'draws': '120'}]
    out = static_table(cols, rows, caption='by area')
    assert isinstance(out, _Raw)
    assert out == (
        '<table class="data"><caption>by area</caption>'
        '<thead><tr><th scope="col">name</th><th class="num" scope="col">draws</th></tr></thead>'
        '<tbody>'
        '<tr><td>opaque</td><td class="num">1,820</td></tr>'
        '<tr><td>ui &amp; hud</td><td class="num">120</td></tr>'     # text escaped by construction
        '</tbody></table>')


def test_static_table_no_caption():
    out = static_table([Column('a', 'a')], [{'a': 'x'}])
    assert out == ('<table class="data"><thead><tr><th scope="col">a</th></tr></thead>'
                   '<tbody><tr><td>x</td></tr></tbody></table>')


def test_data_table_host_normalized_attr_order():
    cols = [Column('shader', 'shader'), Column('cost', 'cost proxy', numeric=True)]
    out = data_table(cols, [{'shader': 'vs_1', 'cost': '42'}], table_key='shader_hotlist',
                     default_sort='cost proxy', default_dir='desc', caption='shaders')
    assert out == (
        '<div class="table-wrap">'
        '<rdc-table data-mode="static" data-table="shader_hotlist" '
        'data-default-sort="cost proxy" data-default-dir="desc">'
        '<table class="data"><caption>shaders</caption>'
        '<thead><tr><th scope="col">shader</th><th class="num" scope="col">cost proxy</th></tr></thead>'
        '<tbody><tr><td>vs_1</td><td class="num">42</td></tr></tbody>'
        '</table></rdc-table></div>')


def test_data_table_omits_absent_host_attrs():
    """No default_sort/dir -> those attributes are omitted (el drops None); wrap=False drops the div."""
    out = data_table([Column('a', 'a')], [{'a': '1'}], table_key='t', wrap=False)
    assert out == ('<rdc-table data-mode="static" data-table="t">'
                   '<table class="data"><thead><tr><th scope="col">a</th></tr></thead>'
                   '<tbody><tr><td>1</td></tr></tbody></table></rdc-table>')


def test_column_render_and_clip_and_colgroups():
    cols = [Column('src', 'src', clip='wide'),
            Column('uses', 'uses', numeric=True, render=lambda v, r: el('b', None, v))]
    out = data_table(cols, [{'src': 'shader_src/0042.glsl', 'uses': '7'}], table_key='t',
                     colgroups=[{'name': 'g', 'open': True, 'cols': ['src']}])
    assert '<script>window.__colgroups_t=[{"name":"g","open":true,"cols":["src"]}];</script>' in out
    assert '<td class="num"><b>7</b></td>' in out          # render output spliced raw
    assert '<td><span class="clip clip-wide">shader_src/0042.glsl</span></td>' in out  # clip wrap


def test_mono_cell_class():
    out = static_table([Column('hash', 'hash', mono=True)], [{'hash': 'ab12'}])
    assert '<td class="mono">ab12</td>' in out


def test_cell_title_unconditional_and_single_escaped():
    """v0.2.6-3: Column.cell_title sets an always-on per-cell title= from the PLAIN value -- the
    dashboard-mini hover-reveal (a responsive fixed-layout mini can't length-gate like clip). Sourced from
    the plain value so el escapes it ONCE; a pre-escaped value would double-escape the title (R1)."""
    out = static_table([Column('area', 'area', cell_title=True)], [{'area': 'ui & hud'}])
    assert '<td title="ui &amp; hud">ui &amp; hud</td>' in out      # always-on, single-escaped
    assert '&amp;amp;' not in out                                   # NOT double-escaped (the R1 guard)
    # cell_title defaults False -> no title= (every summary / -4 report table site stays byte-unchanged)
    assert static_table([Column('a', 'a')], [{'a': 'x'}]) == (
        '<table class="data"><thead><tr><th scope="col">a</th></tr></thead>'
        '<tbody><tr><td>x</td></tr></tbody></table>')


# --- v0.2.6-4: the extensions the 5 tabled detail reports need (header_class / cell_class / colgroups
# div + emit_colgroups_script / colgroups_from / the delta_column factory). ----------------------------

def test_header_class_and_cell_class():
    """header_class adds to the th class; cell_class(value,row) adds a PER-ROW td class (delta direction).
    The th/td classes legitimately differ -- the reason both knobs exist."""
    col = Column('d', 'delta', header_class='num delta-latest',
                 cell_class=lambda value, row: 'delta ' + value[0],
                 render=lambda value, row: value[1])
    out = static_table([col], [{'d': ('pos', '-5')}, {'d': ('neg alarm', '+9')}])
    assert '<th class="num delta-latest" scope="col">delta</th>' in out
    assert '<td class="delta pos">-5</td>' in out
    assert '<td class="delta neg alarm">+9</td>' in out          # per-row class, not the header's


def test_colgroups_from_positions_and_order():
    """colgroups_from derives index lists from each Column.group BY POSITION (no hand counter); groups
    are ordered by the `opens` dict and empty groups are dropped."""
    cols = [Column('a', group='identity'), Column('b', group='cost'),
            Column('c', group='cost'), Column('d', group='identity')]
    spec = colgroups_from(cols, {'identity': True, 'cost': True, 'history': False})
    assert spec == [{'name': 'identity', 'open': True, 'cols': [0, 3]},
                    {'name': 'cost', 'open': True, 'cols': [1, 2]}]   # history empty -> dropped
    assert all(isinstance(c, int) for g in spec for c in g['cols'])


def test_data_table_colgroups_div_and_script_toggle():
    """colgroups => the empty .col-groups toggle-bar div (sibling BEFORE table-wrap) + the inline spec
    script. emit_colgroups_script=False keeps the div but drops the script (overdraw's shared-spec path)."""
    cols = [Column('a', 'a', group='g')]
    spec = [{'name': 'g', 'open': True, 'cols': [0]}]
    full = data_table(cols, [{'a': '1'}], table_key='t', colgroups=spec)
    assert full.startswith('<div class="col-groups" role="group" aria-label="column groups"></div>'
                           '<div class="table-wrap">')
    assert '<script>window.__colgroups_t=[{"name":"g","open":true,"cols":[0]}];</script>' in full
    div_only = data_table(cols, [{'a': '1'}], table_key='t', colgroups=spec,
                          emit_colgroups_script=False)
    assert '<div class="col-groups" role="group" aria-label="column groups"></div>' in div_only
    assert '<script>window.__colgroups_t' not in div_only          # script suppressed, div kept
    # no colgroups -> neither div nor script
    assert 'col-groups' not in data_table(cols, [{'a': '1'}], table_key='t')


def test_delta_parts_shape():
    assert delta_parts(None, None) == ('flat', '')
    assert delta_parts(5, None, fmt='{:+,.0f}') == ('new', 'new')
    assert delta_parts(5, 5, fmt='{:+,.0f}') == ('flat', '0')
    assert delta_parts(5, 10, lower_is_better=True, fmt='{:+,.0f}') == ('pos', '-5')   # lower is better
    assert delta_parts(50, 10, lower_is_better=True, fmt='{:+,.0f}',
                       regression_threshold_pct=20.0) == ('neg alarm', '+40')          # big regression


def test_delta_column_classes_and_per_row_independence():
    """delta_column reproduces the split classes; latest -> th, latest_cell -> td. Each row gets its OWN
    direction (the closure-bug guard: render/cell_class read the PASSED value, not a captured loop var)."""
    th_only = delta_column('d', latest=True)
    out = static_table([th_only], [{'d': ('pos', '-5')}, {'d': ('neg', '+9')}])
    assert '<th class="num delta-latest" scope="col">delta</th>' in out
    assert '<td class="delta pos">-5</td>' in out and '<td class="delta neg">+9</td>' in out  # per row
    assert 'delta-latest' not in out.split('</thead>')[1]          # th only, NOT on the td (overdraw etc)
    # latest_cell -> td also carries delta-latest (trend _kpi_matrix), in the delta delta-latest {dir} order
    both = delta_column('d', latest=True, latest_cell=True)
    body = static_table([both], [{'d': ('neg alarm', '+40')}]).split('</thead>')[1]
    assert '<td class="delta delta-latest neg alarm">+40</td>' in body


def test_default_tier_clip():
    """clip='default' wraps in the default (320px) .clip tier (the area/drop/label cells); the field's
    '' still means NO clip (every prior call site unchanged)."""
    assert '<td><span class="clip">ui &amp; hud</span></td>' in static_table(
        [Column('area', 'area', clip='default')], [{'area': 'ui & hud'}])
    assert '<span class="clip">' not in static_table([Column('a', 'a')], [{'a': 'x'}])


# --- virtual rdc-table host (v0.2.6-5): catalog/drill route through these instead of hand-concat -----

def test_virtual_table_section_drill_shape():
    """The DRILL per-table host: section.table-section[id] + header(h2 + .table-meta) + controls (no dl
    data-link-kind) + the row-less <rdc-table data-mode="virtual"> -- no col-groups div on drill."""
    out = virtual_table_section('draws', title='draws', meta='1,820 rows, 12 cols',
                                csv_href='_data/draws.csv', parquet_href='_data/draws.parquet',
                                filter_label='filter draws', placeholder='filter draws...')
    assert isinstance(out, _Raw)
    assert out == (
        '<section class="table-section" id="draws">'
        '<header class="table-header"><h2>draws</h2>'
        '<span class="table-meta">1,820 rows, 12 cols</span></header>'
        '<div class="controls">'
        '<input type="search" aria-label="filter draws" placeholder="filter draws...">'
        '<span class="ct visible-count"></span>'
        '<a class="dl" href="_data/draws.csv">CSV</a>'
        '<a class="dl" href="_data/draws.parquet">parquet</a></div>'
        '<rdc-table class="table-scroll" data-mode="virtual" data-table="draws"></rdc-table>'
        '</section>')
    assert 'class="col-groups"' not in out                     # col-groups is catalog-only


def test_virtual_host_col_groups_catalog_only():
    """virtual_host(col_groups=True) emits EXACTLY the empty .col-groups toggle bar (the engine fills it)
    BEFORE the host (catalog); col_groups=False (drill) is the bare host. Attr order matches the c16i/k
    substring guards (class, data-mode, data-table) + (class, role, aria-label)."""
    cat = virtual_host('catalog', col_groups=True)
    assert cat == ('<div class="col-groups" role="group" aria-label="column groups"></div>'
                   '<rdc-table class="table-scroll" data-mode="virtual" data-table="catalog"></rdc-table>')
    assert cat.count('class="col-groups"') == 1
    drill = virtual_host('draws')
    assert drill == '<rdc-table class="table-scroll" data-mode="virtual" data-table="draws"></rdc-table>'
    assert 'col-groups' not in drill


def test_table_controls_link_kind_catalog_vs_drill():
    """dl_link_kind='inline' (catalog) emits data-link-kind on the dl <a>s; None (drill) omits it. The
    search input keeps its aria-label (a placeholder is NOT a label, c16o)."""
    catalog = table_controls('_data/_catalog.csv', '_data/_catalog.parquet',
                             filter_label='filter catalog', placeholder='filter', dl_link_kind='inline')
    assert catalog == (
        '<div class="controls">'
        '<input type="search" aria-label="filter catalog" placeholder="filter">'
        '<span class="ct visible-count"></span>'
        '<a class="dl" href="_data/_catalog.csv" data-link-kind="inline">CSV</a>'
        '<a class="dl" href="_data/_catalog.parquet" data-link-kind="inline">parquet</a></div>')
    drill = table_controls('draws.csv', 'draws.parquet',
                           filter_label='filter draws', placeholder='filter draws...')
    assert '<a class="dl" href="draws.csv">CSV</a>' in drill        # no data-link-kind on drill
    assert 'data-link-kind' not in drill


def test_virtual_host_escapes_table_key_by_construction():
    """The escape-by-construction property the el migration buys: a table_key with &/\" can't break out of
    the data-table= attr (or, via virtual_table_section, the id= / aria-label=)."""
    assert virtual_host('a&b"c') == (
        '<rdc-table class="table-scroll" data-mode="virtual" data-table="a&amp;b&quot;c"></rdc-table>')
    sec = virtual_table_section('a&b', title='a&b', meta='0 rows, 0 cols',
                                csv_href='a&b.csv', parquet_href='a&b.parquet',
                                filter_label='filter a&b', placeholder='filter a&b...')
    assert '<section class="table-section" id="a&amp;b">' in sec
    assert 'aria-label="filter a&amp;b"' in sec and 'data-table="a&amp;b"' in sec
