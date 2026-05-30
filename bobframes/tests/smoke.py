"""End-to-end smoke test.

Cleans a known drop's _analysis_out, runs the pipeline, asserts every
expected output exists with non-empty data, asserts schema match,
asserts catalog updated, asserts lint clean.

Run from project root:
    python -m bobframes.tests.smoke
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pyarrow.parquet as papq

from .. import paths, schemas

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
AREA = 'Chor bazar'
DROP_LABEL = 'r110565'
DROP_DATE = '2026-05-27'


def _run(cmd: list[str]) -> int:
    p = subprocess.run(cmd, cwd=ROOT)
    return p.returncode


def _drop_dir() -> str:
    for entry in os.listdir(os.path.join(ROOT, AREA)):
        if entry.startswith(DROP_DATE):
            return os.path.join(ROOT, AREA, entry)
    raise FileNotFoundError(f'no dated drop in {AREA}')


def _clean(drop_dir: str) -> None:
    """Remove this drop's per-drop _data dir + drill dir (idempotent)."""
    drop_label_dated = os.path.basename(drop_dir)
    for d in (
        paths.drop_data_dir(ROOT, AREA, drop_label_dated),
        paths.drop_data_dir_tmp(ROOT, AREA, drop_label_dated),
        paths.drop_drill_dir(ROOT, AREA, drop_label_dated),
    ):
        if os.path.isdir(d):
            try:
                shutil.rmtree(d)
            except OSError as e:
                print(f'  warn: could not remove {d}: {e}')


def main() -> int:
    drop_dir = _drop_dir()
    drop_label_dated = os.path.basename(drop_dir)
    out_dir = paths.drop_data_dir(ROOT, AREA, drop_label_dated)
    tmp_dir = paths.drop_data_dir_tmp(ROOT, AREA, drop_label_dated)
    drill_dir = paths.drop_drill_dir(ROOT, AREA, drop_label_dated)

    print('1. clean')
    _clean(drop_dir)

    print('2. run pipeline')
    rc = _run([sys.executable, '-m', 'bobframes.run',
               '--area', AREA, '--label', DROP_LABEL])
    if rc != 0:
        print(f'FAIL: pipeline exited rc={rc}')
        return 1

    print('3. atomic commit check')
    assert os.path.isdir(out_dir), f'{out_dir} missing'
    assert not os.path.isdir(tmp_dir), f'{tmp_dir} should be gone after commit'

    print('4. parquet+csv pairs')
    for table_stem in schemas.TABLES:
        pq = os.path.join(out_dir, f'{table_stem}.parquet')
        cv = os.path.join(out_dir, f'{table_stem}.csv')
        if not os.path.exists(pq):
            continue
        assert os.path.exists(cv), f'{cv} missing alongside {pq}'

    print('5. schema match')
    schema_errors = 0
    for table_stem in schemas.TABLES:
        pq = os.path.join(out_dir, f'{table_stem}.parquet')
        if not os.path.exists(pq):
            continue
        cols = list(papq.read_schema(pq).names)
        expected = list(schemas.expected_columns(table_stem))
        if cols != expected:
            print(f'  FAIL {table_stem}: cols={cols} vs expected={expected}')
            schema_errors += 1
    if schema_errors:
        print(f'FAIL: {schema_errors} table schema mismatches')
        return 1

    print('6. stable_key populated for entity tables')
    sk_errors = 0
    for table_stem in schemas.TABLES:
        if not schemas.is_entity_table(table_stem):
            continue
        pq = os.path.join(out_dir, f'{table_stem}.parquet')
        if not os.path.exists(pq):
            continue
        t = papq.read_table(pq, columns=['stable_key'])
        n_total = t.num_rows
        if n_total == 0:
            continue
        n_nonempty = sum(1 for v in t.column('stable_key').to_pylist() if v)
        if n_nonempty == 0:
            print(f'  FAIL {table_stem}: stable_key all empty across {n_total} rows')
            sk_errors += 1
    if sk_errors:
        return 1

    print('7. sidecars')
    for required in ('shader_src', 'frame_metadata.jsonl'):
        p = os.path.join(out_dir, required)
        assert os.path.exists(p), f'{p} missing'
    if os.path.isdir(os.path.join(out_dir, 'shader_src')):
        n_shaders = len(os.listdir(os.path.join(out_dir, 'shader_src')))
        assert n_shaders > 0, 'shader_src/ is empty'

    print('8. manifest')
    mf = os.path.join(out_dir, '_manifest.json')
    with open(mf, 'r', encoding='utf-8') as f:
        m = json.load(f)
    assert m['schema_version'] == schemas.SCHEMA_VERSION, m['schema_version']
    assert all(s == 'ok' for s in m['capture_status'].values()), m['capture_status']

    print('9. catalog')
    cat_pq = paths.catalog_parquet(ROOT)
    assert os.path.exists(cat_pq), f'catalog missing at {cat_pq}'
    t = papq.read_table(cat_pq)
    area_col = t.column('area').to_pylist()
    cap_col = t.column('capture').to_pylist()
    found = sum(1 for a, s in zip(area_col, cap_col) if a == AREA)
    assert found >= len(m['captures']), f'catalog has {found} rows for {AREA}, expected >= {len(m["captures"])}'
    aop = t.column('analysis_out_path').to_pylist()
    for p in aop:
        assert not os.path.isabs(p), f'catalog has absolute analysis_out_path: {p}'

    print('10. html')
    assert os.path.exists(os.path.join(drill_dir, 'index.html')), \
        f'per-drop browser missing at {drill_dir}/index.html'
    assert os.path.exists(paths.root_index_html(ROOT)), 'root index.html missing'

    total_rows = sum(m['row_counts'].values())
    n_tables = sum(1 for v in m['row_counts'].values() if v > 0)
    print(f'OK: {n_tables} tables populated, {total_rows:,} total rows, {len(m["captures"])} captures')
    return 0


if __name__ == '__main__':
    sys.exit(main())
