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


def test_no_banned_unicode(rendered):
    # whole-page (incl. inside-table data) ASCII guard - stricter than the orchestrator lint,
    # which only inspects text outside <table>/<script>/<style>.
    for rel, html in rendered.items():
        assert not _BANNED.search(html), rel
