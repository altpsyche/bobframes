"""D-13 + H-41 (v027_1): the trend table's GPU regression is PER FRAME (capture-count-INDEPENDENT),
on the same basis the health verdict uses, and its thresholds are config-driven.

Before v027_1 the trend flagged a regression on a rise in raw cross-capture TOTAL GPU, so a run with
MORE captures than the prior at the SAME per-frame cost read a false +N% (the reason the real corpus
was hand-trimmed to a uniform capture count). These constructed two-drop trees prove the fix without a
golden dependency.
"""
from __future__ import annotations

import json
import os
import re

import pyarrow as pa
import pyarrow.parquet as papq
import pytest

from bobframes import catalog, config, paths, schemas
from bobframes.reports import trend_table
from bobframes.reports.cache import build_per_drop_cache
from bobframes.reports.discovery import discover_drops

AREA = 'AreaA'


def _write_drop(root: str, date: str, label: str, n_captures: int, gpu_per_frame: float) -> None:
    """One (area, drop) with `n_captures` frame_totals rows each at `gpu_per_frame` GPU seconds."""
    caps = [str(i) for i in range(1, n_captures + 1)]
    d = os.path.join(paths.data_root(root), AREA, paths.drop_dirname(date, label))
    os.makedirs(d, exist_ok=True)
    m = {'schema_version': schemas.SCHEMA_VERSION, 'build_timestamp': '2026-01-01T00:00:00+00:00',
         'area': AREA, 'drop_date': date, 'drop_label': label, 'captures': caps,
         'capture_status': {c: 'ok' for c in caps}, 'row_counts': {}, 'rotated_from': None}
    with open(os.path.join(d, paths.MANIFEST_NAME), 'w', encoding='utf-8') as f:
        json.dump(m, f)
    n = len(caps)
    papq.write_table(pa.table({
        'area': [AREA] * n, 'drop_date': [date] * n, 'drop_label': [label] * n, 'capture': caps,
        'n_events': [10] * n, 'n_draws': [100] * n, 'total_gpu_duration_s': [gpu_per_frame] * n,
    }), os.path.join(d, 'frame_totals.parquet'))
    # minimal entity tables (capture 1) so catalog + cache build a normal tree
    papq.write_table(pa.table({
        'area': [AREA], 'drop_date': [date], 'drop_label': [label], 'capture': ['1'],
        'mesh_hash': ['m1'], 'program_id': [1], 'vs_shader_id': [10], 'fs_shader_id': [20],
        'parent_pass_path_norm': ['Frame/basepass'], 'draw_class': ['opaque'],
        'num_indices': [100], 'num_instances': [1],
    }), os.path.join(d, 'draws.parquet'))
    papq.write_table(pa.table({
        'area': [AREA], 'drop_date': [date], 'drop_label': [label], 'capture': ['1'],
        'shader_id': [1], 'stable_key': ['s1'], 'shader_type': ['fragment'], 'src_len': [1],
        'complexity_score': [9.0], 'used_by_draw_count': [1], 'src_file_path': [''],
        'fb_fetch': [False], 'uses_cubemap': [False],
    }), os.path.join(d, 'shaders.parquet'))


def _render(root: str) -> str:
    config.load_config(root)              # pick up any <root>/.bobframes.toml override
    catalog.build_catalog(root)
    build_per_drop_cache(root)
    drops = discover_drops(root)
    return open(trend_table.build(root, drops=drops), encoding='utf-8').read()


def _regressions_kpi(html: str) -> int | None:
    m = re.search(r'regressions</div>\s*<div class="kpi-value">([\d,]+)</div>', html)
    return int(m.group(1).replace(',', '')) if m else None


@pytest.fixture(autouse=True)
def _clean_config():
    yield
    config._reset_for_tests()


def test_per_frame_regression_ignores_capture_count(tmp_path):
    """7-vs-5 captures at the SAME per-frame GPU -> 0 regressions (raw totals would read +40%)."""
    root = str(tmp_path / 'root')
    _write_drop(root, '2026-05-01', 'r1', n_captures=5, gpu_per_frame=0.10)
    _write_drop(root, '2026-05-08', 'r2', n_captures=7, gpu_per_frame=0.10)
    html = _render(root)
    # the matrix shows the per-frame mean (0.1000), not the raw totals (0.5 / 0.7)
    assert '0.1000' in html
    assert _regressions_kpi(html) == 0


def test_real_per_frame_rise_flags_regression(tmp_path):
    """A genuine per-frame rise (0.10 -> 0.13, +30%) flags under the default 10% threshold."""
    root = str(tmp_path / 'root')
    _write_drop(root, '2026-05-01', 'r1', n_captures=5, gpu_per_frame=0.10)
    _write_drop(root, '2026-05-08', 'r2', n_captures=5, gpu_per_frame=0.13)
    assert _regressions_kpi(_render(root)) >= 1


def test_config_threshold_moves_regression_count(tmp_path):
    """H-41: raising `gpu_regression_pct` in .bobframes.toml suppresses the +30% flag (the trend
    heatmap + hero count now read config, not the old baked KPIS literal)."""
    root = str(tmp_path / 'root')
    _write_drop(root, '2026-05-01', 'r1', n_captures=5, gpu_per_frame=0.10)
    _write_drop(root, '2026-05-08', 'r2', n_captures=5, gpu_per_frame=0.13)
    with open(os.path.join(root, '.bobframes.toml'), 'w', encoding='utf-8') as f:
        f.write('[report]\ngpu_regression_pct = 50.0\n')
    assert _regressions_kpi(_render(root)) == 0
