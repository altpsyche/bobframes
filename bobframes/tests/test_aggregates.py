"""G-26: `aggregates` is the single source of the mesh repeat-count + shader uses/cost atoms and the
per-(drop, area) frame count. A constructed multi-capture tree (no golden dependency) pins the atoms
and proves the dashboard helpers now read them. Seeds the c16v per-frame test (test_multicapture_normalize).
"""
from __future__ import annotations

import json
import os

import pyarrow as pa
import pyarrow.parquet as papq
import pytest

from bobframes import aggregates as agg, catalog, paths, schemas
from bobframes.reports import cache
from bobframes.reports.discovery import discover_drops


def _write_tree(root: str, *, area: str, date: str, label: str, captures: list,
                draws: dict, shaders: dict) -> None:
    """Write one drop (manifest + draws.parquet + shaders.parquet) under <root>/_data/<area>/<dir>."""
    d = os.path.join(paths.data_root(root), area, paths.drop_dirname(date, label))
    os.makedirs(d, exist_ok=True)
    m = {
        'schema_version': schemas.SCHEMA_VERSION,
        'build_timestamp': '2026-01-01T00:00:00+00:00',
        'area': area, 'drop_date': date, 'drop_label': label,
        'captures': captures, 'capture_status': {c: 'ok' for c in captures},
        'row_counts': {}, 'rotated_from': None,
    }
    with open(os.path.join(d, paths.MANIFEST_NAME), 'w', encoding='utf-8') as f:
        json.dump(m, f)
    papq.write_table(pa.table(draws), os.path.join(d, 'draws.parquet'))
    papq.write_table(pa.table(shaders), os.path.join(d, 'shaders.parquet'))


def _draws(area, date, label, mesh_caps: list) -> dict:
    """One draw row per (mesh_hash, capture) entry in `mesh_caps` = [(mesh_hash, capture), ...]."""
    n = len(mesh_caps)
    return {
        'area': [area] * n, 'drop_date': [date] * n, 'drop_label': [label] * n,
        'capture': [c for _, c in mesh_caps],
        'mesh_hash': [mh for mh, _ in mesh_caps],
        'program_id': [1] * n, 'vs_shader_id': [10] * n, 'fs_shader_id': [20] * n,
        'parent_pass_path_norm': ['Frame/basepass'] * n, 'draw_class': ['opaque'] * n,
        'num_indices': [100] * n, 'num_instances': [1] * n,
    }


def _shaders(area, date, label, rows: list) -> dict:
    """rows = [(stable_key, shader_type, capture, complexity, used_by_draw_count), ...]."""
    n = len(rows)
    return {
        'area': [area] * n, 'drop_date': [date] * n, 'drop_label': [label] * n,
        'capture': [c for _, _, c, _, _ in rows],
        'shader_id': list(range(1, n + 1)),
        'stable_key': [sk for sk, _, _, _, _ in rows],
        'shader_type': [st for _, st, _, _, _ in rows],
        'src_len': [123] * n,
        'complexity_score': [cx for _, _, _, cx, _ in rows],
        'used_by_draw_count': [u for _, _, _, _, u in rows],
        'src_file_path': [''] * n, 'fb_fetch': [False] * n, 'uses_cubemap': [False] * n,
    }


@pytest.fixture(scope='module')
def tree(tmp_path_factory):
    """One area, one drop, 3 ok captures. m1 drawn once/capture (3 rows); m2 twice in capture 1.
    fragment s1 used twice/capture (3 rows); vertex s2 once (filtered out by stage)."""
    root = str(tmp_path_factory.mktemp('agg') / 'root')
    os.makedirs(root, exist_ok=True)
    date, label, area = '2026-05-30', 'r1', 'AreaA'
    _write_tree(
        root, area=area, date=date, label=label, captures=['1', '2', '3'],
        draws=_draws(area, date, label,
                     [('m1', '1'), ('m1', '2'), ('m1', '3'), ('m2', '1'), ('m2', '1')]),
        shaders=_shaders(area, date, label,
                         [('s1', 'fragment', '1', 30.0, 2), ('s1', 'fragment', '2', 30.0, 2),
                          ('s1', 'fragment', '3', 30.0, 2), ('s2', 'vertex', '1', 5.0, 1)]),
    )
    catalog.build_catalog(root)
    cache.build_per_drop_cache(root)
    drops = discover_drops(root)
    return root, drops, f'{date}_{label}', area


def test_ok_captures_is_three(tree):
    _root, drops, _dk, area = tree
    assert drops[0].n_captures == 3
    assert drops[0].rows[0].ok_captures == 3


def test_draw_aggregates_atoms(tree):
    root, drops, dk, area = tree
    da = agg.draw_aggregates(root, drops)
    assert da.count[(dk, area, 'm1')] == 3      # drawn once per captured frame
    assert da.count[(dk, area, 'm2')] == 2      # twice, all in capture 1
    assert da.frames(dk, area) == 3             # distinct captures present in draws


def test_shader_aggregates_atoms(tree):
    root, drops, dk, area = tree
    sa = agg.shader_aggregates(root, drops, stage='fragment')
    assert sa.uses[(dk, area, 's1')] == 6       # 2 uses x 3 frames
    assert sa.cplx[(dk, area, 's1')] == 30.0
    assert sa.cost_sum[(dk, area, 's1')] == 180.0  # 30 x 2 x 3
    assert sa.frames(dk, area) == 3
    assert (dk, area, 's2') not in sa.uses      # vertex excluded by stage
