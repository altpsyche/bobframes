"""Merge per-capture CSV fragments into drop-level CSV + Parquet pairs.

For each table in schemas.TABLES:
  1. Read every _stage/<capture>/<table>.csv that exists.
  2. Verify the CSV header equals schemas.<TABLE>_COLS exactly (no drift).
  3. Concatenate (preserving capture order).
  4. Compute stable_key for entity tables.
  5. Coerce dtypes via schemas.infer_dtype.
  6. Write _analysis_out.tmp/<table>.parquet (snappy) and <table>.csv.

Also copies non-tabular sidecars (shader_src/, histogram/, jsonl) from the
stage tree into _analysis_out.tmp/.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
from typing import Iterable

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as papq

from . import paths, schemas, stable_keys

_LOG = logging.getLogger('bobframes')


def _list_stage_dirs(stage_root: str) -> list[str]:
    if not os.path.isdir(stage_root):
        return []
    names = []
    for entry in os.listdir(stage_root):
        full = os.path.join(stage_root, entry)
        if os.path.isdir(full):
            names.append(entry)
    names.sort(key=lambda s: (len(s), s))
    return names


def _read_csv_compat(path: str, expected_cols: tuple[str, ...]) -> tuple[list[list[str]], list[int | None]]:
    """Read CSV, return rows ordered into the expected_cols positions.

    Any expected column missing from the CSV header is filled with empty
    strings (post-merge derives populate them later). Extra columns in the
    CSV are ignored. Reorders columns as needed to match expected order.

    Returns (rows, position_map) where rows[i][j] is the value for
    expected_cols[j]. position_map records which CSV column index maps to
    each expected column (None if not present).
    """
    with open(path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return [], []
        idx_for = {c: i for i, c in enumerate(header)}
        pos_map: list[int | None] = [idx_for.get(c) for c in expected_cols]

        out_rows: list[list[str]] = []
        for raw in reader:
            row: list[str] = []
            for p in pos_map:
                if p is None or p >= len(raw):
                    row.append('')
                else:
                    row.append(raw[p])
            out_rows.append(row)
        return out_rows, pos_map


def _cast_value(v: str, dtype: str, fails: dict | None = None):
    """Coerce a CSV string cell to `dtype`. An empty/None cell is a legit default (0/0.0/False/'')
    and is NOT a failure; a value that fails to coerce is defaulted too, but (Q-2) when `fails` is
    given the per-dtype failure count is incremented so the caller can log an aggregate summary
    instead of swallowing genuine data loss silently."""
    if v == '' or v is None:
        if dtype == 'int':   return 0
        if dtype == 'float': return 0.0
        if dtype == 'bool':  return False
        return ''
    try:
        if dtype == 'int':
            try: return int(v)
            except (ValueError, TypeError): return int(float(v))
        if dtype == 'float': return float(v)
        if dtype == 'bool':  return v not in ('0', '', 'False', 'false')
    except (ValueError, TypeError):
        if fails is not None:
            fails[dtype] = fails.get(dtype, 0) + 1
        if dtype == 'int':   return 0
        if dtype == 'float': return 0.0
        if dtype == 'bool':  return False
    return v


def _as_int(v) -> int:
    try:
        return int(v) if v not in ('', None) else 0
    except (ValueError, TypeError):
        return 0


def _shaders_key(g) -> str:
    return g('src_hash')


def _texture_key(g) -> str:
    return stable_keys.texture_key(
        g('label'), g('format'), _as_int(g('width')), _as_int(g('height')),
        _as_int(g('depth')), _as_int(g('mip_levels')), _as_int(g('sample_count')))


def _sampler_key(g) -> str:
    return stable_keys.sampler_key(
        g('min_filter'), g('mag_filter'), g('wrap_s'), g('wrap_t'), g('wrap_r'),
        _as_int(g('max_anisotropy')), g('compare_mode'), g('compare_func'))


def _buffer_key(g) -> str:
    tgts = g('target_history')
    return stable_keys.buffer_key(
        g('usage_hint'), _as_int(g('allocated_size_bytes')),
        tgts.split(';')[0] if tgts else '')


def _program_key(g) -> str:
    ids = g('attached_shader_ids')
    id_list = [x for x in ids.split(';') if x] if ids else []
    return stable_keys.program_key(id_list) if id_list else ''


def _fbo_key(g) -> str:
    rid = g('resource_id')
    return stable_keys.fbo_key([rid]) if rid and rid != '0' else ''


# Q-1: per-entity-table stable-key builders, one row-function each (was a 60-line if/elif chain).
# Each builder takes a `get(col) -> str` accessor (missing/None/'' -> ''); textures + render_targets
# share the texture key. Byte-identical to the old chain - locked by test_stable_keys' oracle battery.
_KEY_BUILDERS = {
    'shaders': _shaders_key,
    'textures': _texture_key,
    'render_targets': _texture_key,
    'samplers': _sampler_key,
    'buffers': _buffer_key,
    'programs': _program_key,
    'fbos': _fbo_key,
}


def _apply_stable_key(table_stem: str, columns: dict[str, list]) -> None:
    """For entity tables, fill the stable_key column from row content (Q-1).

    Called BEFORE dtype coercion; all column values are still strings here. Numeric inputs are cast
    via _as_int. A per-row `get(col)` reads the i-th value, defaulting a missing/None/empty cell to ''
    (the CSV merge never produces None, so this matches the old per-branch `... or ''`).
    """
    if 'stable_key' not in columns:
        return
    n = len(next(iter(columns.values())))
    builder = _KEY_BUILDERS.get(table_stem)
    if builder is None:
        columns['stable_key'] = ['' for _ in range(n)]
        return

    def _get_at(i):
        return lambda col: ((columns.get(col) or [''] * n)[i] or '')

    columns['stable_key'] = [builder(_get_at(i)) for i in range(n)]


def _build_table(table_stem: str, stage_root: str) -> tuple[pa.Table | None, int]:
    """Return (pa.Table or None, row_count). None if no fragments existed."""
    expected_cols = schemas.expected_columns(table_stem)
    captures = _list_stage_dirs(stage_root)

    columns: dict[str, list] = {c: [] for c in expected_cols}

    found_any = False
    for capture in captures:
        path = os.path.join(stage_root, capture, f'{table_stem}.csv')
        if not os.path.exists(path):
            continue
        found_any = True
        rows, _pos = _read_csv_compat(path, expected_cols)
        for row in rows:
            for i, col in enumerate(expected_cols):
                columns[col].append(row[i])

    if not found_any:
        return None, 0

    n_rows = len(columns[expected_cols[0]])

    if schemas.is_entity_table(table_stem):
        _apply_stable_key(table_stem, columns)

    arrays: dict[str, pa.Array] = {}
    fails: dict[str, int] = {}   # Q-2: per-dtype coercion-failure tally (defaulted values, not silent)
    for col in expected_cols:
        dtype = schemas.infer_dtype(col)
        raw = columns[col]
        if dtype == 'int':
            arrays[col] = pa.array([_cast_value(v, 'int', fails) for v in raw], type=pa.int64())
        elif dtype == 'float':
            arrays[col] = pa.array([_cast_value(v, 'float', fails) for v in raw], type=pa.float64())
        elif dtype == 'bool':
            arrays[col] = pa.array([_cast_value(v, 'bool', fails) for v in raw], type=pa.bool_())
        else:
            arrays[col] = pa.array(raw, type=pa.string())

    if fails:
        _LOG.warning('parquetize %s: %d cell(s) failed dtype coercion and were defaulted (%s)',
                     table_stem, sum(fails.values()),
                     ', '.join(f'{k}x{v}' for k, v in sorted(fails.items())))

    return pa.table(arrays), n_rows


def _write_pair(table: pa.Table, out_dir: str, name: str) -> None:
    """Stage Parquet+CSV to .tmp, then atomically rename both. If either write
    fails, roll back both tmps so a half-written pair is never committed (R-2)."""
    pq_path = os.path.join(out_dir, f'{name}.parquet')
    csv_path = os.path.join(out_dir, f'{name}.csv')
    pq_tmp = pq_path + paths.TMP_SUFFIX
    csv_tmp = csv_path + paths.TMP_SUFFIX
    try:
        papq.write_table(table, pq_tmp, compression='snappy')
        pacsv.write_csv(table, csv_tmp)
    except BaseException:
        for t in (pq_tmp, csv_tmp):
            try:
                os.remove(t)
            except OSError:
                pass
        raise
    os.replace(pq_tmp, pq_path)
    os.replace(csv_tmp, csv_path)


def _copy_sidecars(stage_root: str, out_dir: str) -> None:
    """Copy shader_src/, histogram/ and jsonl sidecars from stage to out."""
    captures = _list_stage_dirs(stage_root)
    shader_src_dst = os.path.join(out_dir, 'shader_src')
    histogram_dst = os.path.join(out_dir, 'histogram')
    os.makedirs(shader_src_dst, exist_ok=True)
    os.makedirs(histogram_dst, exist_ok=True)

    # jsonl merging across captures
    fm_path = os.path.join(out_dir, 'frame_metadata.jsonl')
    up_path = os.path.join(out_dir, 'uniforms_per_pass.jsonl')
    fm_lines: list[str] = []
    up_lines: list[str] = []

    for capture in captures:
        cap_dir = os.path.join(stage_root, capture)

        src = os.path.join(cap_dir, 'shader_src')
        if os.path.isdir(src):
            for f in os.listdir(src):
                shutil.copy2(os.path.join(src, f), os.path.join(shader_src_dst, f))

        hist = os.path.join(cap_dir, 'histogram')
        if os.path.isdir(hist):
            for f in os.listdir(hist):
                shutil.copy2(os.path.join(hist, f), os.path.join(histogram_dst, f))

        fm = os.path.join(cap_dir, 'frame_metadata.json')
        if os.path.exists(fm):
            with open(fm, 'r', encoding='utf-8') as f:
                obj = json.load(f)
            fm_lines.append(json.dumps(obj))

        up = os.path.join(cap_dir, 'uniforms_per_pass.jsonl')
        if os.path.exists(up):
            with open(up, 'r', encoding='utf-8') as f:
                up_lines.append(f.read().rstrip('\n'))

    if fm_lines:
        with open(fm_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(fm_lines) + '\n')
    if up_lines:
        with open(up_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(up_lines) + '\n')


def merge_drop(stage_root: str, out_dir: str) -> dict[str, int]:
    """Merge all stage CSVs into out_dir as Parquet+CSV pairs. Returns row counts."""
    os.makedirs(out_dir, exist_ok=True)
    row_counts: dict[str, int] = {}
    for table_stem in schemas.TABLES:
        tbl, n_rows = _build_table(table_stem, stage_root)
        if tbl is None:
            row_counts[table_stem] = 0
            continue
        _write_pair(tbl, out_dir, table_stem)
        row_counts[table_stem] = n_rows
    _copy_sidecars(stage_root, out_dir)
    return row_counts
