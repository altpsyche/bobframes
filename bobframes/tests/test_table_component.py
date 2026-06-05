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
from bobframes.reports.chrome import Column, data_table, static_table, el, _Raw


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
