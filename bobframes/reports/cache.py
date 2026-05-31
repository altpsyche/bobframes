"""Per-drop cache + labels + global-entities loaders."""

from __future__ import annotations

import functools
import json
import os

import pyarrow as pa
import pyarrow.parquet as papq

from .. import paths as _paths
from .discovery import DropSet, discover_drops


@functools.lru_cache(maxsize=64)
def load_global_entities(root: str):
    p = os.path.join(root, '_global_entities.parquet')
    if not os.path.exists(p):
        return None
    try:
        return papq.read_table(p)
    except Exception:
        return None


@functools.lru_cache(maxsize=64)
def load_labels(drop_dir: str) -> dict:
    """Read <drop_dir>/_resource_labels.json. Returns empty dict on miss."""
    p = os.path.join(drop_dir, '_resource_labels.json')
    if not os.path.exists(p):
        return {}
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def label_for(drop_dir: str, capture, kind: str, rid) -> str:
    if not rid or rid == 0 or rid == '0':
        return ''
    data = load_labels(drop_dir)
    by_cap = data.get('by_capture', {})
    bucket = by_cap.get(str(capture), {}).get(kind, {})
    return bucket.get(str(rid), '')


def cache_dir(root: str) -> str:
    d = _paths.reports_cache_dir(root)
    os.makedirs(d, exist_ok=True)
    return d


def cache_path(root: str, table: str) -> str:
    return os.path.join(cache_dir(root), f'{table}_per_drop.parquet')


def _read_drop_parquet(drop: DropSet, table: str, cols: list[str]):
    """Read one parquet table across all areas of a drop. Returns pyarrow Table or None.

    drop.rows[i].drop_dir is the per-drop data dir (_data/<area>/<drop>/); parquet
    files sit directly under it.
    """
    tables = []
    for r in drop.rows:
        p = os.path.join(r.drop_dir, f'{table}.parquet')
        if not os.path.exists(p):
            continue
        try:
            schema_cols = set(papq.read_schema(p).names)
            want = [c for c in cols if c in schema_cols]
            if not want:
                continue
            t = papq.read_table(p, columns=want)
            tables.append(t)
        except Exception:
            continue
    if not tables:
        return None
    try:
        return pa.concat_tables(tables, promote_options='default')
    except TypeError:
        return pa.concat_tables(tables)


def build_per_drop_cache(root: str) -> dict:
    """Compute heavy per-drop aggregations once.

    Writes:
      _reports/_cache/draws_summary_per_drop.parquet
      _reports/_cache/shader_summary_per_drop.parquet
    """
    drops = discover_drops(root)
    out: dict[str, int] = {}

    draws_rows: list[dict] = []
    for d in drops:
        t = _read_drop_parquet(d, 'draws',
            ['area', 'drop_date', 'drop_label', 'capture', 'mesh_hash',
             'program_id', 'vs_shader_id', 'fs_shader_id',
             'parent_pass_path_norm', 'draw_class', 'num_indices', 'num_instances'])
        if t is None or t.num_rows == 0:
            continue
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        n = t.num_rows
        for i in range(n):
            draws_rows.append({
                'drop_date': d.date,
                'drop_label': d.label,
                'area': cols['area'][i],
                'capture': cols['capture'][i],
                'mesh_hash': cols.get('mesh_hash', [''])[i] if 'mesh_hash' in cols else '',
                'program_id': cols.get('program_id', [0])[i] if 'program_id' in cols else 0,
                'vs_shader_id': cols.get('vs_shader_id', [0])[i] if 'vs_shader_id' in cols else 0,
                'fs_shader_id': cols.get('fs_shader_id', [0])[i] if 'fs_shader_id' in cols else 0,
                'parent_pass_path_norm': cols.get('parent_pass_path_norm', [''])[i] if 'parent_pass_path_norm' in cols else '',
                'draw_class': cols.get('draw_class', [''])[i] if 'draw_class' in cols else '',
                'num_indices': cols.get('num_indices', [0])[i] if 'num_indices' in cols else 0,
                'num_instances': cols.get('num_instances', [1])[i] if 'num_instances' in cols else 1,
            })
    if draws_rows:
        tbl = pa.Table.from_pylist(draws_rows)
        papq.write_table(tbl, cache_path(root, 'draws_summary'), compression='snappy')
        out['draws_summary'] = len(draws_rows)

    shader_rows: list[dict] = []
    for d in drops:
        t = _read_drop_parquet(d, 'shaders',
            ['area', 'drop_date', 'drop_label', 'capture', 'shader_id', 'stable_key',
             'shader_type', 'src_len', 'complexity_score', 'total_branches',
             'total_loops', 'total_discards', 'total_dfdx_dfdy',
             'total_texture_samples', 'used_by_draw_count', 'src_file_path',
             'fb_fetch', 'uses_cubemap'])
        if t is None or t.num_rows == 0:
            continue
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        n = t.num_rows
        for i in range(n):
            shader_rows.append({k: cols[k][i] for k in cols})
            shader_rows[-1]['drop_date'] = d.date
            shader_rows[-1]['drop_label'] = d.label
    if shader_rows:
        tbl = pa.Table.from_pylist(shader_rows)
        papq.write_table(tbl, cache_path(root, 'shader_summary'), compression='snappy')
        out['shader_summary'] = len(shader_rows)

    return out
