"""Golden-independent guards for reports/charts.py (c16b, ADR-33).

Determinism (same input -> identical bytes), SVG structure (role/title/desc), token theming
(var() colors + [chart] sizes), empty-series -> safe '', and an ASCII-only guard (the page lint
bans decorative unicode; chart text rides outside <table> so it is linted).
"""

from __future__ import annotations

import re

from bobframes.reports import charts, _tokens


# A representative call per chart fn (kept here so determinism/ascii loops over all of them).
_BARS = [('opaque', 120.0), ('ui', 30.0), ('shadow', 5.0)]
_ROWS = [('District 01 / d1', {'opaque': 8, 'ui': 2}), ('District 01 / d2', {'opaque': 6, 'shadow': 4})]
_SEGS = [('opaque', 80, 'var(--c-opaque)'), ('ui', 20, 'var(--c-ui)')]
_PTS = [(10.0, 100.0, 4096, 'a'), (40.0, 900.0, 256, 'b')]
_TM = [('pass.a', 10, 'var(--c-opaque)'), ('pass.b', 4, 'var(--c-ui)')]
_LV = [[('root', 14, 'var(--accent-data)')], [('a', 10, 'var(--c-opaque)'), ('b', 4, 'var(--c-ui)')]]
_LN = [('District 01', [1.0, 2.0, None, 3.0], 'var(--accent-data)')]


def _all_charts():
    return {
        'bar': charts.bar_chart(_BARS, title='bars', desc='d'),
        'bar_threshold': charts.bar_chart(_BARS, title='b', desc='d',
                                          thresholds=[(50.0, 'var(--status-warn)', 'warn')]),
        'stacked': charts.stacked_bar(_ROWS, title='s', desc='d'),
        'pct_stacked': charts.pct_stacked_bar(_ROWS, title='p', desc='d'),
        'donut': charts.donut(_SEGS, center_label='100', title='do', desc='d'),
        'scatter': charts.scatter(_PTS, x_label='complexity', y_label='cost', bubble=True,
                                  title='sc', desc='d'),
        'histogram': charts.histogram([1, 2, 2, 3, 3, 3, 9], bins=6, title='h', desc='d'),
        'treemap': charts.treemap(_TM, title='tm', desc='d'),
        'icicle': charts.icicle(_LV, title='ic', desc='d'),
        'line': charts.line_chart(_LN, x_labels=['d1', 'd4'], title='ln', desc='d'),
    }


def test_determinism_same_input_same_bytes():
    a = _all_charts()
    b = _all_charts()
    for k in a:
        assert a[k] == b[k], f'{k} not deterministic'


def test_svg_structure_role_title_desc():
    for name, svg in _all_charts().items():
        assert svg, f'{name} empty'
        assert svg.startswith('<svg class="chart-svg"') and svg.endswith('</svg>'), name
        assert 'role="img"' in svg, name
        assert 'viewBox="0 0 ' in svg, name
        assert '<title>' in svg and '<desc>' in svg, name
        assert 'aria-label=' in svg, name


def test_element_counts():
    # N bars -> N <rect>; N points -> N <circle>; multi-seg donut -> N <path>.
    assert charts.bar_chart(_BARS, title='t').count('<rect') == len(_BARS)
    assert charts.scatter(_PTS, bubble=True, title='t').count('<circle') == len(_PTS)
    assert charts.donut(_SEGS, title='t').count('<path') == len(_SEGS)
    # single-segment donut -> two concentric circles, no path
    one = charts.donut([('opaque', 5, 'var(--c-opaque)')], title='t')
    assert one.count('<path') == 0 and one.count('<circle') == 2


def test_token_theming():
    # draw-class series -> --c-* vars; default single-series -> [chart].series_color.
    assert 'var(--c-opaque)' in charts.pct_stacked_bar(_ROWS, title='t')
    assert 'var(--accent-data)' in charts.bar_chart(_BARS, title='t')
    # [chart] sizes drive the viewBox width.
    w = int(_tokens.chart().get('width', 640))
    assert f'viewBox="0 0 {w} ' in charts.bar_chart(_BARS, title='t')


def test_empty_series_safe():
    assert charts.bar_chart([]) == ''
    assert charts.stacked_bar([]) == '' and charts.pct_stacked_bar([]) == ''
    assert charts.donut([]) == '' and charts.donut([('a', 0, 'x')]) == ''
    assert charts.scatter([]) == '' and charts.histogram([]) == ''
    assert charts.treemap([]) == '' and charts.icicle([]) == ''
    assert charts.line_chart([]) == ''
    assert charts.line_chart([('a', [None, None], 'x')]) == ''
    assert charts.figure('', 'cap') == ''


def test_figure_wrap():
    fig = charts.figure(charts.bar_chart(_BARS, title='t'), 'caption')
    assert fig.startswith('<figure class="chart">')
    assert '<figcaption>caption</figcaption>' in fig
    assert '<svg class="chart-svg"' in fig


_BANNED = re.compile(r'[—–…“”‘’→←↑↓×·✓✅]')


def test_ascii_only_output():
    # Even with banned chars in labels, output is scrubbed (safe_chrome_text) -> lint-safe.
    dirty = charts.bar_chart([('a × b', 5), ('c — d', 3)], title='t → x')
    assert dirty and not _BANNED.search(dirty)
    for name, svg in _all_charts().items():
        assert not _BANNED.search(svg), f'{name} has banned char'


# --- c16d-c: gradient fills + per-datum <title> + dimmed axes -----------------

def test_gradients_present_and_referenced():
    bar = charts.bar_chart(_BARS, title='t', chart_id='b1')
    assert '<linearGradient id="g-b1-bar"' in bar and 'fill="url(#g-b1-bar)"' in bar
    hist = charts.histogram([1, 2, 2, 3, 3, 3], bins=4, title='t', chart_id='h1')
    assert '<linearGradient id="g-h1-bin"' in hist and 'fill="url(#g-h1-bin)"' in hist
    sc = charts.scatter(_PTS, bubble=True, title='t', chart_id='s1')
    assert '<radialGradient id="g-s1-dot"' in sc and 'fill="url(#g-s1-dot)"' in sc
    # gradient stops keep the CSS var() colour so light-dark() theming survives
    assert 'stop-color="var(--accent-data)"' in bar


def test_gradient_ids_unique_across_charts_on_page():
    # two charts share one HTML page (dashboard) -> ids must not collide
    a = charts.bar_chart(_BARS, title='t', chart_id='dash-tt')
    b = charts.bar_chart(_BARS, title='t', chart_id='dash-im')
    assert 'id="g-dash-tt-bar"' in a and 'id="g-dash-im-bar"' in b
    assert 'g-dash-tt-bar' not in b and 'g-dash-im-bar' not in a


def test_gradient_id_deterministic_and_sanitized():
    # no hash()/counter: same chart_id -> identical bytes; ids forced to ascii [a-z0-9-]
    assert charts.bar_chart(_BARS, title='t', chart_id='x') == charts.bar_chart(_BARS, title='t', chart_id='x')
    dirty = charts.bar_chart(_BARS, title='t', chart_id='Pass A/B #1')
    assert 'id="g-pass-a-b--1-bar"' in dirty and not _BANNED.search(dirty)


def test_per_datum_titles():
    bar = charts.bar_chart(_BARS, title='t', chart_id='b')
    assert bar.count('<title>') == len(_BARS) + 1     # one per bar + the chart-level title
    assert '<title>opaque: 120</title>' in bar
    ln = charts.line_chart(_LN, x_labels=['d1', 'd4'], title='ln', chart_id='l')
    assert ln.count('<title>') >= 2                   # chart-level + at least one per-series


def test_axis_dimmed_to_lightest_border():
    # c16d dims axes from --border-2 (strong) to --border-1 (lightest) so data pops
    sc = charts.scatter(_PTS, title='t', chart_id='s')
    assert 'stroke="var(--border-1)"' in sc
    assert 'stroke="var(--border-2)"' not in sc
