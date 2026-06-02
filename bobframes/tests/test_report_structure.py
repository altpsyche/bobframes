"""c16c: golden-independent structural guards for the report restructure.

The full-page golden (test_parity) proves byte-identity; these asserts pin the STRUCTURE that c16c
introduced - section_card framing, sticky h2, rdc-copy-button on copyable IDs, table <caption> +
scope="col", dashboard small-multiples + cross-report nav, and the instancing fill-or-hide - so a
regression gives a focused failure independent of a golden refresh (ADR-23 / QUALITY_GATES).
"""
from __future__ import annotations

import os
import re

import pytest

from . import _render_util as u

_BANNED = re.compile(r'[—–…“”‘’→←↑↓×·✓✅]')

# tabled reports (pass_gpu uses bar-row divs, no <table>, so it is excluded from caption/scope).
_TABLED = ['overdraw', 'draws_by_class', 'shader_hotlist',
           'instancing_opportunities', 'trend_table']
_ALL_REPORTS = ['pass_gpu'] + _TABLED


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    dest = u.render_fresh(str(tmp_path_factory.mktemp('c16c') / 'root'))
    return {rel: open(os.path.join(dest, rel), encoding='utf-8').read()
            for rel in u.rendered_html_files(dest)}


def _report(pages, name):
    return pages[f'_reports/{name}.html']


def test_section_cards_and_sticky(rendered):
    for name in _ALL_REPORTS:
        html = _report(rendered, name)
        assert '<section class="card"' in html, name
        # every section card is wrapped for the in-view sticky highlight
        assert '<rdc-sticky-h2><section class="card"' in html, name
        # headings moved into the card header -> no bare raw <h2 id=...> anchors left
        assert '<h2 id=' not in html, name


def test_table_scope_and_caption(rendered):
    for name in _TABLED:
        html = _report(rendered, name)
        assert '<caption>' in html, name
        assert '<th>' not in html, f'{name}: bare <th> without scope'
        assert html.count('<th ') == html.count('scope="col"'), f'{name}: th/scope mismatch'


def test_copy_buttons_on_named_ids(rendered):
    # pass path (pass_gpu)
    assert 'data-label="copy pass path"' in _report(rendered, 'pass_gpu')
    # shader id + src path (shader_hotlist)
    sh = _report(rendered, 'shader_hotlist')
    assert 'data-label="copy shader id"' in sh
    assert 'data-label="copy src path"' in sh
    # mesh hash (instancing) - the FULL hash is copied, not the truncated last-4 display tag
    inst = _report(rendered, 'instancing_opportunities')
    m = re.search(r'<rdc-copy-button data-value="([^"]+)" data-label="copy mesh hash"', inst)
    assert m and len(m.group(1)) > 4, 'mesh-hash copy payload should be the full hash'


def test_instancing_fill_or_hide(rendered):
    # synthetic has no material-batching candidates -> the batching section must be HIDDEN,
    # not rendered as a bare heading over an empty-state (c16c fill-or-hide).
    inst = _report(rendered, 'instancing_opportunities')
    assert 'id="batching"' not in inst
    assert 'no material-batching candidates' not in inst


def test_dashboard_small_multiples_and_nav(rendered):
    idx = rendered['_reports/index.html']
    assert '<nav class="chip-cluster" aria-label="reports">' in idx     # cross-report nav
    assert idx.count('class="dash-card"') == 6
    assert idx.count('<p class="dash-sub">') == 6                        # insight subtitle per card
    assert idx.count('<figure class="chart">') == 6                     # a mini chart per card
    assert idx.count('<caption>') == 6
    assert '<th>' not in idx
    assert idx.count('<th ') == idx.count('scope="col"')


def test_dashboard_kpi_totals_paired_with_averages(rendered):
    """Raw totals read as alarming on their own; the dashboard pairs each with a per-frame / per-area
    average so the hero strip informs a budget decision instead of just scaring execs."""
    import re
    idx = rendered['_reports/index.html']
    labels = re.findall(r'class="kpi-label">([^<]*)<', idx)
    values = re.findall(r'class="kpi-value">([^<]*)<', idx)
    # per-area average is NOT a single headline number (one per area) -> it lives in the trend card
    assert labels == ['total gpu (s)', 'avg gpu / frame (s)', 'total draws',
                      'avg draws / frame', 'areas']
    kv = dict(zip(labels, values))
    to_num = lambda s: float(s.replace(',', ''))
    # the average must be a fraction of the total (n_frames > 1 in the synthetic: 2 drops x 5 frames)
    assert to_num(kv['avg draws / frame']) < to_num(kv['total draws'])
    assert to_num(kv['avg gpu / frame (s)']) < to_num(kv['total gpu (s)'])
    # per-area avg draws lives in the trend-table card, not the headline strip
    assert 'avg draws / frame' in idx and 'per-area GPU + draw load' in idx


def test_header_names_current_run(rendered):
    # c16e (ADR-35): each single-state report + the dashboard names the run it reports on, so the
    # reader is never unsure which run a "live" candidate / headline belongs to.
    single_state = ['pass_gpu', 'overdraw', 'draws_by_class', 'shader_hotlist',
                    'instancing_opportunities']
    for name in single_state + ['index']:
        rel = '_reports/index.html' if name == 'index' else f'_reports/{name}.html'
        html = rendered[rel]
        assert re.search(r'run <strong>\d+ of \d+</strong>:', html), name
    # trend_table is the across-run view; it has no single current run -> no run span.
    assert not re.search(r'run <strong>\d+ of \d+</strong>:',
                         _report(rendered, 'trend_table'))


def test_resolved_since_separated_from_live(rendered):
    # c16e: where a "resolved since <baseline>" section exists it is a distinct section card,
    # never mixed into the live candidate list (top_meshes / shaders).
    for name in ['instancing_opportunities', 'shader_hotlist']:
        html = _report(rendered, name)
        if 'id="resolved"' in html:
            assert '<rdc-sticky-h2><section class="card" id="resolved"' in html, name


def test_no_banned_unicode(rendered):
    # whole-page (incl. inside-table data) ASCII guard - stricter than the orchestrator lint,
    # which only inspects text outside <table>/<script>/<style>.
    for rel, html in rendered.items():
        assert not _BANNED.search(html), rel


# --- c16i: catalog + drill readability (the html/template.py layer) ---
# The VTable <table>/cells are built CLIENT-SIDE, so the golden carries only <style> + _JS + the
# inline data/colgroups scripts + the empty col-groups div. These guards are substring/structural
# checks on that emitted source (pytest has no browser).

def _root(pages):
    return pages['index.html']


def _drill(pages):
    keys = [k for k in pages if '/drill/' in k and k.endswith('index.html')]
    assert keys, 'no drill page rendered'
    return pages[keys[0]]


def _script_json(html, varname):
    """Extract the JSON assigned to ``window.<varname>=...;</script>``. Each <script> is emitted on
    its own line, so a line scan beats brace-counting and avoids regex-vs-nested-braces fragility."""
    import json
    marker = f'window.{varname}='
    for line in html.splitlines():
        if marker in line and ';</script>' in line:
            payload = line.split(marker, 1)[1]
            return json.loads(payload[:payload.rindex(';</script>')])
    return None


def test_c16i_type_split(rendered):
    # Inter sans is the table.data DEFAULT; mono+tabular is re-asserted ONLY on numeric/.mono BODY
    # cells. Headers stay sans (the mono rule is scoped to tbody, never thead th.numeric).
    for html in (_root(rendered), _drill(rendered)):
        assert "font: var(--fs-body)/1.3 'Inter'" in html
        assert 'tbody td.numeric, table.data tbody td.mono' in html
        assert "ui-monospace, 'Cascadia Code', Consolas, monospace" in html
        assert 'thead th.numeric, table.data tbody td.mono' not in html  # headers NOT forced mono


def test_c16i_row_height_lockstep(rendered):
    # ROW_H (JS) is the sole virtual-scroll driver; the CSS cell padding is its coupled pair. Pin
    # both literals so neither drifts silently and overflows the row (which desyncs the scroll).
    for html in (_root(rendered), _drill(rendered)):
        assert 'const ROW_H = 32;' in html
        assert 'padding: 6px 8px;' in html


def test_c16i_heatmap_deterministic_and_offline(rendered):
    for html in (_root(rendered), _drill(rendered)):
        assert 'td.style.backgroundImage' in html         # bar via background-IMAGE...
        assert 'td.style.background =' not in html         # ...NOT the shorthand (would kill zebra/hover)
        assert 'var(--accent-data)' in html                # reuse the existing heatmap token
        assert '% of column max)' in html                  # aria-label -> colour is not the only signal
        for bad in ('Math.random', 'Date.now', 'new Date', 'fetch('):
            assert bad not in html, bad                    # offline + byte-deterministic


def test_c16i_column_groups_catalog_only(rendered):
    idx, drill = _root(rendered), _drill(rendered)
    # served chrome: exactly one toggle-bar container on the catalog, none on the drill
    assert idx.count('<div class="col-groups" role="group" aria-label="column groups">') == 1
    assert 'class="col-groups"' not in drill
    assert 'window.__colgroups_catalog=' not in drill
    # group -> column map: 4 category-derived groups, Metadata+Workload open, an EXACT partition of
    # the catalog columns (no orphaned or double-counted column).
    groups = _script_json(idx, '__colgroups_catalog')
    assert groups is not None, 'colgroups script not found'
    assert [g['name'] for g in groups] == ['Metadata', 'Workload', 'Resources', 'Samples']
    assert [g['name'] for g in groups if g['open']] == ['Metadata', 'Workload']
    cat_cols = _script_json(idx, '__data_catalog')['cols']
    grouped = [c for g in groups for c in g['cols']]
    assert sorted(grouped) == sorted(cat_cols)             # exhaustive
    assert len(grouped) == len(set(grouped)) == len(cat_cols)  # no overlap
    # toggle UI is built client-side, so assert the _JS SOURCE: real <button> + aria-pressed state.
    assert "btn.type = 'button'" in idx
    assert "'col-group-toggle'" in idx
    assert "setAttribute('aria-pressed'" in idx


def test_c16i_reports_layer_untouched(rendered):
    # c16i is the template.py layer ONLY. The reports/dashboard pages must carry none of the
    # catalog/drill VTable chrome - a leak here would mean shared CSS/JS bled into reports.
    for name in _ALL_REPORTS + ['index']:
        rel = '_reports/index.html' if name == 'index' else f'_reports/{name}.html'
        html = rendered[rel]
        assert 'class="col-groups"' not in html, name
        assert 'window.__colgroups_catalog=' not in html, name


def test_c16i_deterministic_render(tmp_path_factory):
    # same input -> identical catalog + drill output (no random/Date crept into the new JS). Compare
    # after u.normalize() since the catalog header carries the build timestamp (masked in the golden).
    a = u.render_fresh(str(tmp_path_factory.mktemp('c16i_a') / 'root'))
    b = u.render_fresh(str(tmp_path_factory.mktemp('c16i_b') / 'root'))
    rels = ['index.html'] + [k for k in u.rendered_html_files(a)
                             if '/drill/' in k and k.endswith('index.html')]
    for rel in rels:
        ta = u.normalize(open(os.path.join(a, rel), encoding='utf-8').read())
        tb = u.normalize(open(os.path.join(b, rel), encoding='utf-8').read())
        assert ta == tb, rel
