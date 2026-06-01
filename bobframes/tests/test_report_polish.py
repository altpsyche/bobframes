"""c16 report-quality polish: chrome builder units + an end-to-end empty-state render.

Golden-independent guards (the populated golden is covered by test_parity). Covers the provenance
strip (G-6/G-7), the insight callout (A7), the empty-state card (A9), the heatmap cell (A8), and that
a sparse drop renders friendly empty-state messages instead of blank tables.
"""
from __future__ import annotations

import os
import shutil

import pyarrow.parquet as papq

from bobframes.reports import chrome
from bobframes.tests import _render_util as u


# --- chrome builder units ----------------------------------------------------

def test_provenance_strip_renders_fields_and_omits_bobframes():
    s = chrome.provenance_strip(
        {'gpu': 'GpuX', 'gpu_driver': 'Drv', 'cpu': 'CpuY', 'os': 'OsZ', 'bobframes': '9.9.9'},
        {'renderdoccmd': 'rc-1', 'qrenderdoc': 'qrd-1'})
    assert 'device-strip' in s
    for token in ('GpuX', 'Drv', 'CpuY', 'OsZ', 'rc-1', 'qrd-1'):
        assert token in s
    assert '9.9.9' not in s          # bobframes version deliberately excluded (no golden churn)


def test_provenance_strip_empty_when_no_data():
    assert chrome.provenance_strip({}, {}) == ''
    assert chrome.provenance_strip(None, None) == ''


def test_callout_alarm_wraps_and_tones():
    c = chrome.callout('alarm', 'Title', 'Detail', href='#x', link_text='go')
    assert 'callout sev-alarm' in c
    assert 'rdc-alarm-banner' in c and 'data-severity="high"' in c
    assert 'Title' in c and 'Detail' in c and 'href="#x"' in c


def test_callout_info_has_no_alarm_banner():
    c = chrome.callout('info', 'T')
    assert 'sev-info' in c and 'rdc-alarm-banner' not in c


def test_empty_state_has_icon_and_message():
    s = chrome.empty_state('nothing to show')
    assert 'empty-state' in s and 'nothing to show' in s and '<svg' in s


def test_heatmap_cell_emits_data_attrs():
    cell = chrome.heatmap_cell(7, 0, 10, text='7')
    assert cell.startswith('<rdc-heatmap-cell')
    assert 'data-value="7"' in cell and 'data-min="0"' in cell and 'data-max="10"' in cell
    assert 'data-direction="hot"' in cell and '>7<' in cell


# --- end-to-end: a sparse drop renders empty-state, not blank tables ---------

def _build_sparse_data(src_data: str, out_data: str) -> None:
    """Copy the synthetic _data tree but slice every parquet to 0 rows (manifests/sidecars kept)."""
    for dirpath, _dirs, files in os.walk(src_data):
        rel = os.path.relpath(dirpath, src_data)
        dst_dir = os.path.join(out_data, rel)
        os.makedirs(dst_dir, exist_ok=True)
        for fn in files:
            s = os.path.join(dirpath, fn)
            d = os.path.join(dst_dir, fn)
            if fn.endswith('.parquet'):
                papq.write_table(papq.read_table(s).slice(0, 0), d, compression='snappy')
            else:
                shutil.copy2(s, d)


def test_sparse_drop_renders_empty_state(tmp_path):
    sparse_data = str(tmp_path / 'sparse_data')
    _build_sparse_data(u.SYNTHETIC_DATA, sparse_data)
    dest = u.render_fresh(str(tmp_path / 'root'), data_src=sparse_data)

    # shader_hotlist + instancing both gate their tables behind an empty-state on no rows.
    for rel in ('_reports/shader_hotlist.html', '_reports/instancing_opportunities.html',
                '_reports/draws_by_class.html'):
        html = open(os.path.join(dest, rel), encoding='utf-8').read()
        assert 'empty-state' in html, f'{rel} should show a friendly empty-state on a sparse drop'
