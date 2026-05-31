"""Unit tests for discovery (c15, doc's `unit_discovery.py`).

Covers the area/dated-drop walking that drives ingest + smoke: latest-drop selection, the
area/label/capture filters, the capture sort order, skip rules, and parse_single_drop_arg
(the correct name — not the doc's earlier `_parse_drop_dirname`).

Named `test_*` for default pytest discovery (no `python_files` override).
"""
from __future__ import annotations

import os

import pytest

from .. import discovery
from .. import paths as _paths
from ..discovery import Drop


def _touch(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').close()


def _make_root(tmp_path) -> str:
    root = str(tmp_path / 'proj')
    # Town: two dated drops; the newer one has three captures with non-lexical numeric names.
    _touch(os.path.join(root, 'Town', '2026-05-27_old', '1.rdc'))
    for cap in ('1', '2', '10'):
        _touch(os.path.join(root, 'Town', '2026-05-28_new', f'{cap}.rdc'))
    # Bay: a single undated-label drop (label absent).
    _touch(os.path.join(root, 'Bay', '2026-01-01', 'cap.rdc'))
    # Noise that must be ignored: underscore (output) dir is not an area.
    _touch(os.path.join(root, _paths.DATA_DIR, 'District 01', '2026-05-28_new', 'x.parquet'))
    return root


def test_find_drops_picks_latest_per_area(tmp_path):
    drops = {d.area: d for d in discovery.find_drops(_make_root(tmp_path))}
    assert set(drops) == {'Town', 'Bay'}                  # '_data' skipped
    assert drops['Town'].drop_date == '2026-05-28'        # newest dated drop
    assert drops['Town'].drop_label == 'new'
    assert drops['Bay'].drop_label == ''                  # label optional


def test_latest_empty_drop_skips_area_no_fallback(tmp_path):
    # The newest dated dir has no .rdc; find_drops skips the whole area rather than falling
    # back to the older drop that does have captures.
    root = str(tmp_path / 'proj')
    _touch(os.path.join(root, 'Town', '2026-05-27_old', '1.rdc'))
    os.makedirs(os.path.join(root, 'Town', '2026-05-28_new'), exist_ok=True)
    assert discovery.find_drops(root) == []


def test_capture_sort_is_length_then_lexical(tmp_path):
    town = next(d for d in discovery.find_drops(_make_root(tmp_path)) if d.area == 'Town')
    assert town.captures == ('1', '2', '10')              # NOT lexical ('1','10','2')


def test_filters(tmp_path):
    root = _make_root(tmp_path)
    assert [d.area for d in discovery.find_drops(root, area_filter='Bay')] == ['Bay']
    assert discovery.find_drops(root, label_filter='nope') == []
    capped = discovery.find_drops(root, area_filter='Town', capture_filter='2')
    assert capped[0].captures == ('2',)
    # A capture filter that doesn't match the area's drop drops it entirely.
    assert discovery.find_drops(root, area_filter='Town', capture_filter='999') == []


def test_drop_without_rdc_is_skipped(tmp_path):
    root = str(tmp_path / 'proj')
    os.makedirs(os.path.join(root, 'Area', '2026-05-28_x'), exist_ok=True)
    assert discovery.find_drops(root) == []


def test_find_drops_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        discovery.find_drops(str(tmp_path / 'nope'))


def test_parse_single_drop_arg_ok(tmp_path):
    root = _make_root(tmp_path)
    d = discovery.parse_single_drop_arg('Town/2026-05-28_new', root)
    assert isinstance(d, Drop)
    assert (d.area, d.drop_date, d.drop_label) == ('Town', '2026-05-28', 'new')
    assert d.captures == ('1', '2', '10')
    # Trailing separators + backslashes normalize identically.
    assert discovery.parse_single_drop_arg('Town\\2026-05-28_new\\', root).drop_dir == d.drop_dir


def test_parse_single_drop_arg_errors(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ValueError):
        discovery.parse_single_drop_arg('justone', root)            # no <area>/<drop>
    with pytest.raises(ValueError):
        discovery.parse_single_drop_arg('Town/not-a-date', root)    # not a dated folder
    with pytest.raises(FileNotFoundError):
        discovery.parse_single_drop_arg('Town/2026-05-30_ghost', root)  # dir absent
