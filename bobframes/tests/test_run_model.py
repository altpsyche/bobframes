"""c16e: the run model (ADR-35) - per-run truth, not the cumulative union of all runs.

The full-page golden (test_parity) proves byte-identity; these asserts pin the MODEL so a
regression gives a focused failure independent of a golden refresh (ADR-23 / QUALITY_GATES):
- the resolver primitives (current_run / baseline_run / RunContext);
- the dashboard headline reports ONE run's draws, not run1+run2 summed;
- instancing's LIVE candidate set is a subset of the current run's meshes (the invariant that the
  cumulative-union flaw violated) - so a mesh removed in the newer run can never linger as live;
- every single-state report + the dashboard name their current run in the header.
"""
from __future__ import annotations

import os
import re

import pyarrow.parquet as papq
import pytest

from . import _render_util as u
from ..reports import base


@pytest.fixture(scope='module')
def root(tmp_path_factory):
    return u.render_fresh(str(tmp_path_factory.mktemp('c16e') / 'root'))


@pytest.fixture(scope='module')
def pages(root):
    return {rel: open(os.path.join(root, rel), encoding='utf-8').read()
            for rel in u.rendered_html_files(root)}


def _drops(root):
    return base.discover_drops(root)


def _slice_section(html: str, section_id: str) -> str:
    """The single `<section class="card" id="<id>">...</section>` (sections do not nest)."""
    start = html.find(f'id="{section_id}"')
    assert start != -1, f'section {section_id!r} not found'
    end = html.find('</section>', start)
    return html[start:end if end != -1 else None]


def _valid_meshes(drop) -> set:
    """Valid mesh-hash set drawn in `drop` (num_indices>0 and program_id!=0), from the fixture."""
    meshes: set = set()
    for r in drop.rows:
        p = os.path.join(r.drop_dir, 'draws.parquet')
        if not os.path.exists(p):
            continue
        t = papq.read_table(p, columns=['mesh_hash', 'num_indices', 'program_id'])
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        for i in range(t.num_rows):
            mh = cols['mesh_hash'][i]
            if mh and (cols['num_indices'][i] or 0) > 0 and (cols['program_id'][i] or 0) != 0:
                meshes.add(mh)
    return meshes


# --- resolver primitives -----------------------------------------------------

def test_current_run_defaults_newest(root):
    drops = _drops(root)
    assert len(drops) == 2
    assert base.current_run(drops) is drops[-1]
    assert base.current_run([]) is None
    # explicit override picks the named run
    assert base.current_run(drops, run_label=drops[0].label) is drops[0]


def test_baseline_run_immediately_prior(root):
    drops = _drops(root)
    cur = base.current_run(drops)
    assert base.baseline_run(drops, cur) is drops[-2]
    # single run / oldest / empty -> no baseline
    assert base.baseline_run(drops[:1], drops[0]) is None
    assert base.baseline_run([], None) is None


def test_run_context_props(root):
    drops = _drops(root)
    rc = base.run_context(drops)
    assert rc.n_runs == 2
    assert rc.current is drops[-1] and rc.baseline is drops[-2]
    assert rc.ordinal == '2 of 2'
    assert rc.is_newest is True
    assert rc.run_label == drops[-1].key
    # single run
    rc1 = base.run_context(drops[:1])
    assert rc1.ordinal == '1 of 1' and rc1.is_newest and rc1.baseline is None
    # empty
    rc0 = base.run_context([])
    assert rc0.current is None and rc0.ordinal == '' and rc0.run_label == '' \
        and not rc0.is_newest


# --- per-run truth -----------------------------------------------------------

def test_dashboard_total_draws_is_current_run_only(root, pages):
    drops = _drops(root)
    cur = base.current_run(drops)
    cur_sum = 0
    both_sum = 0
    for d in drops:
        for r in d.rows:
            t = papq.read_table(os.path.join(r.drop_dir, 'frame_totals.parquet'),
                                columns=['n_draws'])
            s = sum(v for v in t.column('n_draws').to_pylist() if v is not None)
            both_sum += s
            if d.key == cur.key:
                cur_sum += s
    idx = pages['_reports/index.html']
    labels = re.findall(r'class="kpi-label">([^<]*)<', idx)
    values = re.findall(r'class="kpi-value">([^<]*)<', idx)
    kv = dict(zip(labels, values))
    rendered = int(kv['total draws over captures'].replace(',', ''))
    assert rendered == cur_sum, f'dashboard total draws {rendered} != current run {cur_sum}'
    assert rendered < both_sum, 'dashboard total draws must NOT be the cross-run sum'


def test_instancing_live_candidates_subset_of_current_run(root, pages):
    """The run-model invariant: every LIVE instancing candidate is a mesh drawn in the current run.

    This is what the cumulative-union flaw violated (a run1-only mesh showed as live). It holds
    regardless of fixture content - it is the model, not an incidental property.
    """
    cur = base.current_run(_drops(root))
    cur_meshes = _valid_meshes(cur)
    top = _slice_section(pages['_reports/instancing_opportunities.html'], 'top_meshes')
    live_hashes = set(re.findall(
        r'data-value="([^"]+)" data-label="copy mesh hash"', top))
    assert live_hashes, 'expected some live mesh candidates'
    assert live_hashes <= cur_meshes, \
        f'live candidates not drawn in the current run: {live_hashes - cur_meshes}'


def test_removed_mesh_not_listed_as_live(root, pages):
    """A mesh present in the baseline run but gone in the current run must not be a live candidate.

    The synthetic's two drops derive from different source areas, so removal is exercised; skip with
    a clear message if the fixture ever changes so the drops share all meshes (the fixture parquet
    cannot be edited without refreshing the forbidden digests, so the skip-guard is the right path).
    """
    drops = _drops(root)
    cur = base.current_run(drops)
    bl = base.baseline_run(drops, cur)
    removed = _valid_meshes(bl) - _valid_meshes(cur)
    if not removed:
        pytest.skip('fixture drops share all meshes; removed-mesh path not exercised')
    top = _slice_section(pages['_reports/instancing_opportunities.html'], 'top_meshes')
    live_hashes = set(re.findall(
        r'data-value="([^"]+)" data-label="copy mesh hash"', top))
    assert not (removed & live_hashes), \
        'a mesh removed in the current run is listed as a LIVE instancing candidate'


# --- header + resolved-since framing -----------------------------------------

_SINGLE_STATE = ['instancing_opportunities', 'draws_by_class', 'shader_hotlist',
                 'pass_gpu', 'overdraw']


def test_each_report_names_current_run(root, pages):
    cur = base.current_run(_drops(root))
    rels = ['_reports/index.html'] + [f'_reports/{n}.html' for n in _SINGLE_STATE]
    for rel in rels:
        html = pages[rel]
        assert re.search(r'run <strong>\d+ of \d+</strong>:', html), rel
        assert cur.key in html, rel


def test_resolved_since_is_a_separate_card(pages):
    # resolved-since (where present) is a distinct section card, never nested in the live list.
    for name in ['instancing_opportunities', 'shader_hotlist']:
        html = pages[f'_reports/{name}.html']
        if 'id="resolved"' in html:
            assert '<rdc-sticky-h2><section class="card" id="resolved"' in html, name


# --- c16f: run-selector UX ---------------------------------------------------

_OLDER_RUN = '2026-05-27_r110565'   # the synthetic's older run (newest is 2026-05-28_r110600)


def test_per_run_pages_emitted(pages):
    # each OLDER run gets a self-contained page set under run/<key>/ (newest stays the top-level
    # default); trend_table is the across-run view and is NOT pre-rendered per run.
    for name in _SINGLE_STATE + ['index']:
        assert f'_reports/run/{_OLDER_RUN}/{name}.html' in pages, name
    assert f'_reports/run/{_OLDER_RUN}/trend_table.html' not in pages


def test_run_picker_lists_runs_marks_current(root, pages):
    keys = [d.key for d in _drops(root)]
    top = pages['_reports/index.html']
    assert 'id="rdc-run-select"' in top
    for k in keys:
        assert f': {k}' in top                      # every run is an option
    # newest is the selected option on the top-level page; links resolve from _reports/
    assert re.search(r'<option value="index.html" selected>run \d+/\d+: ' + re.escape(keys[-1]), top)
    assert f'<option value="run/{_OLDER_RUN}/index.html">' in top
    # on the older run's page the older run is selected; links are depth-prefixed (../../)
    per = pages[f'_reports/run/{_OLDER_RUN}/index.html']
    assert f'<option value="../../run/{_OLDER_RUN}/index.html" selected>' in per
    assert '<option value="../../index.html">' in per


def test_older_run_cue_only_on_nonnewest(pages):
    assert 'viewing an older run' not in pages['_reports/index.html']
    per = pages[f'_reports/run/{_OLDER_RUN}/index.html']
    assert 'viewing an older run' in per
    assert 'href="../../index.html"' in per          # cue links back up to the newest page


def test_baseline_banner(root, pages):
    drops = _drops(root)
    top = pages['_reports/index.html']
    assert f'current: {drops[-1].key} | baseline: <span class="dim">{drops[-2].key}' in top
    # the oldest run has no prior -> no banner
    assert 'baseline: <span class="dim">' not in pages[f'_reports/run/{_OLDER_RUN}/index.html']


def test_nav_persists_within_run_dir(pages):
    per = pages[f'_reports/run/{_OLDER_RUN}/index.html']
    # the 5 per-run reports are bare siblings -> selecting a run persists into that run's dir
    assert 'href="instancing_opportunities.html"' in per
    # trend_table is not per-run -> its link points up to the top level
    assert 'href="../../trend_table.html"' in per


def test_ab_page_suppresses_run_picker(root):
    # an A/B page is a fixed pair; the run selector + "current vs baseline" banner must not appear
    # on it (ab is not None). Pure-function check - no A/B pages in the default render.
    drops = _drops(root)
    rc = base.run_context(drops)
    html = base.report_page('x', ['<p>body</p>'], crumb_depth=3, ab=(drops[0], drops[1]),
                            root=root, report_key='pass_gpu', run=rc)
    assert 'id="rdc-run-select"' not in html
    assert 'class="ab-strip">current:' not in html
