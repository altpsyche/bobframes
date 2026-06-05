"""c16q: structural + reconciliation guards for the build-health one-pager (reports/summary.py).

test_parity proves byte-identity against the golden; these pin the STRUCTURE (verdict bar + scope +
Direction tag, four averaged KPIs, the baseline-gated Movement card, the By-area table) and the
RECONCILIATION (the averaged KPIs equal the dashboard's current-run totals / frame count), so a
regression fails focused, independent of a golden refresh (ADR-23 / QUALITY_GATES, the G-26 guard).
"""
from __future__ import annotations

import os
import re

import pytest

from . import _render_util as u
from .. import lint
from ..reports import base
from ..reports import dashboard as _dash

_BANNED = re.compile(r'[—–…“”‘’→←↑↓×·✓✅]')
_OLDER = '2026-05-27_r110565'        # the synthetic's older run (oldest -> no baseline)


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    dest = u.render_fresh(str(tmp_path_factory.mktemp('c16q') / 'root'))
    pages = {rel: open(os.path.join(dest, rel), encoding='utf-8').read()
             for rel in u.rendered_html_files(dest)}
    return dest, pages


def _summary(pages):
    return pages['_reports/summary.html']


def _kpi_value(html, label):
    m = re.search(re.escape(label) + r'</div><div class="kpi-value">([^<]*)', html)
    assert m, f'kpi {label!r} not found'
    return m.group(1)


def test_summary_in_page_set(rendered):
    _, pages = rendered
    assert '_reports/summary.html' in pages
    assert f'_reports/run/{_OLDER}/summary.html' in pages


def test_verdict_bar_and_scope(rendered):
    s = _summary(rendered[1])
    assert 'class="summary-bar' in s
    assert 'build health' in s
    assert re.search(r'\d+ of \d+ area', s)   # "1 of 1 area" / "7 of 7 areas"
    assert 'Action needed' in s          # synthetic overdraw 75% -> ALARM


def test_direction_tag(rendered):
    s = _summary(rendered[1])
    m = re.search(r'Direction: (improving|mixed|regressing|unknown)', s)
    assert m and m.group(1) == 'improving'   # synthetic: draws + gpu + shader all drop


def test_four_headline_kpis(rendered):
    s = _summary(rendered[1])
    for lbl in ['avg draws / frame', 'avg gpu / frame', 'worst overdraw', 'worst shader']:
        assert lbl in s
    assert s.count('class="kpi-chip') == 4
    assert 'delta-pill' in s                 # colored vs-prior deltas
    assert '<svg class="trendline' in s      # per-KPI area trend strip (c16x-5: chrome/delta component)
    assert 'trendline-fill' in s             # the filled area (not a bare polyline)
    assert 'kpi-note' in s                   # grey total / scale line


def test_movement_card_baseline_gated(rendered):
    _, pages = rendered
    s = pages['_reports/summary.html']
    assert 'id="movement"' in s
    assert 'Improvements' in s and 'Regressions' in s
    assert re.search(r'\d+ resolved / \d+ newly un-instanced', s)
    older = pages[f'_reports/run/{_OLDER}/summary.html']
    assert 'id="movement"' not in older      # oldest run -> no baseline -> hidden
    assert 'Direction: unknown' in older     # trajectory unknown (no false-green)


def test_by_area_table(rendered):
    s = _summary(rendered[1])
    assert 'id="by_area"' in s
    by = s[s.index('id="by_area"'):]
    assert '<caption>By area</caption>' in by
    assert '<th>' not in by                  # every th carries scope
    assert by.count('<th ') == by.count('scope="col"')
    body = by[by.index('<tbody>'):by.index('</tbody>')]
    assert body.count('<tr>') == 1           # one row per area (synthetic: 1 area)
    assert 'delta-pill' in body              # per-area vs-prior deltas
    assert 'Action needed' in body           # per-area status label


def test_lint_clean(rendered):
    dest, _ = rendered
    assert lint.lint_file(os.path.join(dest, '_reports', 'summary.html')) == []
    assert lint.lint_file(os.path.join(dest, '_reports', 'run', _OLDER, 'summary.html')) == []


def test_no_banned_unicode(rendered):
    _, pages = rendered
    for rel in ('_reports/summary.html', f'_reports/run/{_OLDER}/summary.html'):
        assert not _BANNED.search(pages[rel]), rel


def test_avg_kpis_reconcile_with_dashboard(rendered):
    dest, pages = rendered
    s, dash = pages['_reports/summary.html'], pages['_reports/index.html']
    # the one-pager's averaged KPIs equal the dashboard's current-run KPIs (same pooled total/frames)
    assert _kpi_value(s, 'avg draws / frame') == _kpi_value(dash, 'avg draws / frame')
    assert _kpi_value(s, 'avg gpu / frame') == _kpi_value(dash, 'avg gpu / frame (s)')
    # and against the raw current-run computation directly (capture-count-independent)
    rc = base.run_context(base.discover_drops(dest))
    _tg, td, nf = _dash._run_totals([rc.current])
    assert _kpi_value(s, 'avg draws / frame') == base.fmt_int(round(td / nf))


def test_total_line_matches_dashboard_totals(rendered):
    dest, pages = rendered
    s = pages['_reports/summary.html']
    rc = base.run_context(base.discover_drops(dest))
    tg, td, _nf = _dash._run_totals([rc.current])
    assert base.fmt_int(td) in s             # e.g. "4,417" draws total
    assert base.fmt_float(tg, 3) in s        # e.g. "0.177" s gpu total


def test_summary_deterministic(tmp_path):
    d1 = u.render_fresh(str(tmp_path / 'r1'))
    d2 = u.render_fresh(str(tmp_path / 'r2'))
    for rel in ('_reports/summary.html', f'_reports/run/{_OLDER}/summary.html'):
        a = u.normalize(open(os.path.join(d1, rel), encoding='utf-8').read())
        b = u.normalize(open(os.path.join(d2, rel), encoding='utf-8').read())
        assert a == b, rel
