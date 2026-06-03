"""R-18: a `--force` rotation backup must not be counted as a duplicate drop.

`--force` rotates the live drop `<drop>` to a SIBLING backup `<drop>.<ts>` (R-16) that keeps the
ORIGINAL manifest + Parquet (clean `drop_label`). Both walkers that scan `_data/<area>/<drop>/`
- `catalog._find_manifests` and `global_entities.build_global_entities` - used to include the backup,
double-counting capture rows + entity rows until the backups were cleaned. The fix skips any drop dir
whose basename != `<drop_date>_<drop_label>` (reconstructed from the manifest/Parquet content).
"""
from __future__ import annotations

import json
import os

import pyarrow as pa
import pyarrow.parquet as papq

from bobframes import catalog, global_entities, paths, schemas


def test_drop_dirname_helper():
    assert paths.drop_dirname('2026-01-01', 'r1') == '2026-01-01_r1'
    assert paths.drop_dirname('2026-01-01', '') == '2026-01-01'      # labelless drop
    assert paths.drop_dirname('2026-01-01', 'r1.2') == '2026-01-01_r1.2'  # dotted label preserved


def _write_drop(area_dir: str, dirname: str) -> None:
    """Write a minimal canonical-content drop (manifest + one shaders entity) into <area>/<dirname>.

    The CONTENT always names the live drop (drop_label='r1'); only the dir NAME varies, so a backup
    dir name (`2026-01-01_r1.<ts>`) diverges from `<drop_date>_<drop_label>` exactly as in the wild.
    """
    d = os.path.join(area_dir, dirname)
    os.makedirs(d, exist_ok=True)
    m = {
        'schema_version': schemas.SCHEMA_VERSION,
        'build_timestamp': '2026-01-01T00:00:00+00:00',
        'area': 'Area', 'drop_date': '2026-01-01', 'drop_label': 'r1',
        'captures': ['1'], 'capture_status': {'1': 'ok'},
        'row_counts': {}, 'rotated_from': None,
    }
    with open(os.path.join(d, paths.MANIFEST_NAME), 'w', encoding='utf-8') as f:
        json.dump(m, f)
    table = schemas.entity_tables()[0]                       # 'shaders'
    id_col = global_entities._entity_id_col(table)           # 'shader_id'
    t = pa.table({
        'stable_key': ['sk-1'], 'area': ['Area'], 'drop_date': ['2026-01-01'],
        'drop_label': ['r1'], 'capture': ['1'], id_col: [7],
    })
    papq.write_table(t, os.path.join(d, f'{table}.parquet'))


def _root_with_live_and_backup(tmp_path) -> str:
    root = str(tmp_path)
    area_dir = os.path.join(paths.data_root(root), 'Area')
    _write_drop(area_dir, '2026-01-01_r1')                   # live drop
    _write_drop(area_dir, '2026-01-01_r1.20260101T000000')   # --force rotation backup (R-16)
    return root


def test_build_catalog_ignores_rotation_backup(tmp_path):
    root = _root_with_live_and_backup(tmp_path)
    summary = catalog.build_catalog(root)
    assert summary['capture_count'] == 1, 'backup dir double-counted as a duplicate capture (R-18)'
    assert summary['drop_count'] == 1


def test_global_entities_ignores_rotation_backup(tmp_path):
    root = _root_with_live_and_backup(tmp_path)
    n = global_entities.build_global_entities(root)
    assert n == 1, 'backup dir double-counted the entity (R-18)'
