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
    pages = {rel: open(os.path.join(dest, rel), encoding='utf-8').read()
             for rel in u.rendered_html_files(dest)}
    # c16j: also expose the externalized _pagedata/*.js companions (catalog/drill heavy data).
    pages.update({rel: open(os.path.join(dest, rel), encoding='utf-8').read()
                  for rel in u.rendered_page_data_files(dest)})
    return pages


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


def _pagedata_json(js_text):
    """Parse a ``_pagedata/<key>.js`` body (``window.__data_<key>={...};``) into its payload dict (c16j)."""
    import json
    body = js_text.split('=', 1)[1].rstrip()        # split only the assignment '='
    assert body.endswith(';'), 'page-data .js must end with ;'
    return json.loads(body[:-1])


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
    cat_cols = _pagedata_json(rendered['_pagedata/catalog.js'])['cols']  # c16j: data now external
    grouped = [c for g in groups for c in g['cols']]
    assert sorted(grouped) == sorted(cat_cols)             # exhaustive
    assert len(grouped) == len(set(grouped)) == len(cat_cols)  # no overlap
    # toggle UI is built client-side, so assert the _JS SOURCE: real <button> + aria-pressed state.
    assert "btn.type = 'button'" in idx
    assert "'col-group-toggle'" in idx
    assert "setAttribute('aria-pressed'" in idx


def test_c16i_reports_layer_untouched(rendered):
    # c16i was the template.py layer ONLY. Column groups are an OPT-IN report feature, declared per
    # report as its own index-keyed __colgroups_<key>: c16k brought them to shader_hotlist; c16l adds
    # overdraw (a wide per-drop-fanning table with a separable current/history split). Reports without
    # a separable wall stay clean, and the CATALOG global never leaks into any report.
    _COL_GROUP_REPORTS = {'shader_hotlist', 'overdraw'}
    for name in _ALL_REPORTS + ['index']:
        rel = '_reports/index.html' if name == 'index' else f'_reports/{name}.html'
        html = rendered[rel]
        if name not in _COL_GROUP_REPORTS:
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


# --- c16j: heavy VTable data decoupled into _pagedata/*.js (static, classic <script defer src>, ADR-37) ---
# The byte-golden (test_parity) proves the HTML shell + every .js companion; these asserts pin the
# STRUCTURE c16j introduced - data OUT of the HTML, referenced by a file://-safe classic defer script,
# the small globals kept inline, reports untouched, and the companions deterministic + offline.

def _drill_pagedata_rels(pages):
    return [r for r in pages if '/drill/' in r and '/_pagedata/' in r and r.endswith('.js')]


def test_c16j_catalog_data_externalized(rendered):
    idx = _root(rendered)
    # the heavy rows are gone from the HTML, referenced via a classic, file://-safe defer <script src>
    assert 'window.__data_catalog=' not in idx
    assert '<script defer src="_pagedata/catalog.js"></script>' in idx
    assert 'fetch(' not in idx and 'type="module"' not in idx     # offline: no fetch, no ES module
    # the small globals stay INLINE (only the heavy payload moves)
    assert 'window.__colgroups_catalog=' in idx
    assert 'window.__labels=' in idx
    # the companion exists, defines the global, and parses
    js = rendered['_pagedata/catalog.js']
    assert js.startswith('window.__data_catalog=')
    assert _pagedata_json(js)['cols']                              # non-empty cols


def test_c16j_drill_data_externalized(rendered):
    drill = _drill(rendered)
    # no inline per-table payload survives in the drill HTML
    assert 'window.__data_' not in drill
    # one classic defer <script src> per non-empty table, == the number of .js companions written
    n_refs = drill.count('<script defer src="_pagedata/')
    assert n_refs >= 1, 'drill should reference at least one _pagedata/*.js'
    assert len(_drill_pagedata_rels(rendered)) == n_refs
    # __labels stays inline; offline (no fetch / no module)
    assert 'window.__labels=' in drill
    assert 'fetch(' not in drill and 'type="module"' not in drill


def test_c16j_pagedata_deterministic_and_offline(rendered):
    # every companion is PURE DATA: ASCII, no banned unicode, no nondeterminism, no network.
    rels = [r for r in rendered if r.endswith('.js')]
    assert rels, 'no _pagedata/*.js found'
    for rel in rels:
        js = rendered[rel]
        assert js.isascii(), rel
        assert not _BANNED.search(js), rel
        for bad in ('Math.random', 'Date.now', 'new Date', 'fetch('):
            assert bad not in js, (rel, bad)
        assert js.startswith('window.__data_'), rel


def test_c16j_reports_have_no_pagedata(rendered):
    # the discovery family is catalog + drill ONLY - no report/dashboard contributes a companion.
    for rel in rendered:
        if rel.endswith('.js'):
            assert rel == '_pagedata/catalog.js' or '/drill/' in rel, rel


def test_c16j_loading_hint_catalog_drill_only(rendered):
    # CSS-only loading state (rides _PER_DROP_CSS) shows until the VTable injects rows; catalog+drill
    # only - a leak into the shared chrome CSS would churn the (frozen) reports goldens.
    for html in (_root(rendered), _drill(rendered)):
        assert '.table-scroll:empty::before' in html
        assert "content: 'loading...'" in html
    for name in _ALL_REPORTS + ['index']:
        rel = '_reports/index.html' if name == 'index' else f'_reports/{name}.html'
        assert '.table-scroll:empty::before' not in rendered[rel], name


# --- c16k: the unified rdc-table component (ADR-38). One engine, two data-delivery modes. ---
# virtual (catalog/drill): windowed, rows from _pagedata/*.js. static (a proof report): rows
# server-baked, JS enhances IN PLACE so JS-off/print/Ctrl-F keep every row. The byte-golden proves
# the emitted shell; these guards pin the STRUCTURE the merge introduced.

def test_c16k_virtual_hosts_on_catalog_and_drill(rendered):
    # catalog + drill render through <rdc-table data-mode="virtual"> (the old div.table-scroll host is
    # gone); the engine + data-delivery are unchanged (c16j externalization still holds, asserted above).
    for html in (_root(rendered), _drill(rendered)):
        assert '<rdc-table class="table-scroll" data-mode="virtual" data-table=' in html
        assert '<div class="table-scroll" data-table=' not in html   # host renamed div -> rdc-table
    # one engine string ships (class VTable + class StaticTable in the same IIFE), offline + det.
    for html in (_root(rendered), _drill(rendered)):
        assert 'class VTable' in html and 'class StaticTable' in html
        for bad in ('Math.random', 'Date.now', 'new Date', 'fetch('):
            assert bad not in html, bad


def test_c16k_static_proof_server_baked(rendered):
    # shader_hotlist is the static-mode proof (ADR-37 preserved): its main table is SERVER-BAKED into
    # the HTML (golden-visible, readable JS-off, printable, Ctrl-F-able), enhanced by
    # <rdc-table data-mode="static">. It is NOT virtual (no client data payload, no windowing spacers).
    import re
    import json as _json
    html = _report(rendered, 'shader_hotlist')
    assert '<rdc-table data-mode="static"' in html
    assert '<table class="data">' in html                    # consolidated table class
    assert 'window.__data_shader_hotlist' not in html         # not virtual: rows are baked, not streamed
    assert 'class="spacer"' not in html                       # not windowed: no virtual spacer rows
    # server-baked rows live in the HTML source: >=1 <tr> in the main table's tbody (the ranked rows).
    main_tbody = html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    assert main_tbody.count('<tr>') >= 1
    # the report's OWN column-groups spec, keyed by INDEX (per-drop header text repeats), distinct
    # from the catalog global; identity+cost groups present, empty toggle-bar container emitted.
    m = re.search(r'__colgroups_shader_hotlist=(\[.*?\]);</script>', html)
    assert m, 'colgroups spec script not found'
    groups = _json.loads(m.group(1))
    assert [g['name'] for g in groups][:2] == ['identity', 'cost']
    assert all(isinstance(c, int) for g in groups for c in g['cols'])
    assert '<div class="col-groups" role="group" aria-label="column groups">' in html


# --- c16l: the rollout. rdc-table (static) on every report surface; rdc-sortable-table DELETED. ---

def test_c16l_sortable_table_deleted(rendered):
    # c16l (ADR-38): the old rdc-sortable-table is GONE everywhere - the component def + its CSS + every
    # wrapper. The ONE rdc-table engine now serves every surface; table.report is retired for table.data.
    # G-23 fully resolved (no two code paths). Grep-clean over EVERY rendered page.
    for rel, html in rendered.items():
        if not rel.endswith('.html'):
            continue
        assert '<rdc-sortable-table' not in html, rel
        assert 'RdcSortableTable' not in html, rel
        assert "customElements.define('rdc-sortable-table'" not in html, rel
        assert 'class="report"' not in html, rel


def test_c16l_all_tabled_reports_on_static_rdc_table(rendered):
    # every tabled report renders through a STATIC rdc-table with SERVER-BAKED rows (ADR-37): readable
    # JS-off, printable, Ctrl-F-able. Not virtual (no client payload, no windowing spacers). The engine
    # (StaticTable + VTable) now ships in the always-on shared bundle, so it is inline on every page.
    for name in _TABLED:
        html = _report(rendered, name)
        assert '<rdc-table data-mode="static"' in html, name
        assert '<table class="data">' in html, name
        assert 'class="spacer"' not in html, name            # not windowed
        assert 'window.__data_' not in html, name             # static, not streamed
        assert '<tbody>' in html and '<tr>' in html, name     # server-baked rows in the HTML source
        assert 'class StaticTable' in html and 'class VTable' in html, name
    # pass_gpu is charts / bar-rows only - no table engine host
    assert '<rdc-table' not in _report(rendered, 'pass_gpu')
    # dashboard minis are bare table.data (deliberately NOT wrapped - a sortable header inside the
    # card-link <a> would both sort and navigate); the dashboard hosts no rdc-table.
    idx = rendered['_reports/index.html']
    assert '<rdc-table' not in idx
    assert '<table class="data">' in idx


def test_c16l_engine_in_shared_report_bundle():
    # c16l folds the engine into the ALWAYS-ON report bundle; the c16k opt-in (rdc_table_assets +
    # report_page(rdc_table=...)) is gone. template.py keeps rdc_table_css()/rdc_table_js() for the
    # catalog/drill bundle.
    from bobframes.reports import chrome
    css, js = chrome._compose_css(), chrome._compose_js()
    assert 'table.data' in css
    assert 'class StaticTable' in js and 'class VTable' in js
    assert "aria-sort" in js   # static-table sort state is announced (a11y parity with old rdc-sortable-table)
    assert not hasattr(chrome, 'rdc_table_assets')
    assert callable(chrome.rdc_table_css) and callable(chrome.rdc_table_js)
    import inspect
    assert 'rdc_table' not in inspect.signature(chrome.report_page).parameters
    assert 'rdc_table' not in inspect.signature(chrome.page_open).parameters


# --- c16m: controllable cell truncation + hover-reveal on the one rdc-table engine (ADR-38). ---

def test_c16m_clip_on_long_report_cells(rendered):
    # Known-long report cells truncate via an INNER .clip element (never the <td>), so the trailing
    # copy-button / file icon / rank pill ride OUTSIDE the clip and stay visible. The src-path column
    # gets the WIDE tier; areas / labels get the default tier. The clip is display-only CSS, so the
    # real DOM text stays the FULL value (Ctrl-F / selection-copy).
    sh = _report(rendered, 'shader_hotlist')
    assert '<span class="clip clip-wide">' in sh           # src path, wide tier, on an inner span
    inst = _report(rendered, 'instancing_opportunities')
    assert 'class="clip"' in inst                          # mesh label (on the <a>) + areas (span)
    assert 'class="clip clip-narrow"' in inst              # dominant pass, narrow tier
    over = _report(rendered, 'overdraw')
    assert 'class="clip"' in over and 'class="clip clip-narrow"' in over   # RT label + format
    assert 'class="clip"' in _report(rendered, 'trend_table')              # area column


def test_c16m_copy_and_link_payloads_keep_full_value(rendered):
    # The clipped DISPLAY never becomes the copyable/linked value (c16c contract). For the src-path
    # cell the inner clip span's text == the copy-button's data-value == the full path.
    sh = _report(rendered, 'shader_hotlist')
    # the first src cell: <a ...><span class="clip clip-wide">PATH</span>...icon...</a><rdc-copy-button data-value="PATH" ...>
    m = re.search(r'<span class="clip clip-wide">([^<]+)</span>.*?'
                  r'<rdc-copy-button data-value="([^"]+)" data-label="copy src path"', sh, re.S)
    assert m, 'src-path clip span + copy button not found'
    assert m.group(1) == m.group(2), 'clipped display must equal the full copied value'


def test_c16m_clip_helper_title_gating():
    # The full value is recoverable on hover via a server-set title= - but only on LONG cells (a
    # deterministic char-threshold proxy; short cells skip title= to avoid screen-reader double-read).
    # Tested directly on the helper (synthetic fixture paths are short, so the golden carries no
    # src-path title= - correct-for-data; we do NOT alter the threshold or the fixture to force one).
    from bobframes.reports import chrome
    long_path = '/Engine/Private/' + 'Deep/' * 20 + 'Material.usf'   # > wide threshold (64)
    wide = chrome.clip_span(long_path, tier='wide')
    assert 'class="clip clip-wide"' in wide and f'title="{long_path}"' in wide
    assert long_path in wide                                  # full value stays in the DOM text
    assert 'title=' not in chrome.clip_span('short', tier='')         # short -> no title noise
    assert 'title=' in chrome.clip_attrs('x' * 50)                    # long default-tier -> title
    assert 'title=' not in chrome.clip_attrs('x' * 50, tier='wide')   # 50 < wide threshold -> none


def test_c16m_dashboard_mini_hover_title(rendered):
    # Dashboard minis are bare (not engine-hosted), so they carry no inner .clip/JS title. The builder
    # sets a server-side title= on their text cells so a clipped value still reveals in full on hover
    # (and Ctrl-F matches the real inline text). Numeric cells (right-aligned, short) get no title.
    idx = rendered['_reports/index.html']
    assert '<td title="' in idx, 'dashboard mini text cells must carry a hover title='
    # headers clip too under table-layout:fixed (e.g. "avg draws / frame"), so they carry title= as well
    assert '<th class="num" scope="col" title="avg draws / frame">' in idx
    # the marker column is no longer builder-truncated (trunc_left) - the full value reaches the DOM,
    # the CSS clip handles the display, the title= reveals it. A trailing-ellipsis builder-trunc would
    # have put a literal "..." into the cell text; the unified path keeps the full value instead.
    assert '<td class="num" title=' not in idx, 'numeric mini cells should not carry a redundant title'


def test_c16m_expand_toggle_and_css_contract():
    # The global expand/wrap toggle is a real <button aria-pressed> built by the engine (both modes),
    # flipping data-expand on the host; the CSS releases the clip (single line both modes; static also
    # wraps). The c16l no-clip stopgap (static td max-width:none) is REPLACED by the controllable clip.
    from bobframes.reports import chrome
    css, js = chrome._RDC_TABLE_CSS, chrome._RDC_TABLE_JS
    # toggle: a real button with aria-pressed that flips data-expand
    assert "'rdc-expand-toggle'" in js or 'rdc-expand-toggle' in js
    assert 'aria-pressed' in js and 'dataset.expand' in js and 'Expand cells' in js
    # CSS contract: tiered caps, the inner .clip element, the data-expand release, print full-wrap
    assert '--clip-cap' in css and '--clip-cap-wide' in css and '--clip-cap-narrow' in css
    assert 'table.data .clip {' in css
    assert 'rdc-table[data-expand="true"] table.data .clip' in css
    # the DEFAULT td-clip (380px) protects the un-enhanced bare dashboard/preview minis; rdc-table cells
    # OPT OUT and truncate via the inner .clip element (so trailing copy-buttons/labels stay visible).
    assert 'max-width: 380px' in css
    assert 'rdc-table table.data tbody td { max-width: none' in css
    assert css.isascii()   # ellipsis via the CSS keyword, no literal U+2026


# --- c16n: truncation-coverage tail - draws_by_class clip + bare-mini print full-wrap (ADR-38 tail). ---

def test_c16n_draws_by_class_area_drop_clip(rendered):
    # draws_by_class was the only tabled report c16m's scope skipped; its raw per-(area,drop) table's
    # area + drop text cells now truncate via the inner .clip (default tier), so all 5 tabled reports
    # clip + hover-reveal consistently. A clean flip: the page had NO server-baked clip cell before
    # c16n (the engine JS applies clip via .className, never the literal class="clip").
    dbc = _report(rendered, 'draws_by_class')
    assert 'class="clip"' in dbc
