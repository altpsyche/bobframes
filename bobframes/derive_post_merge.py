"""Post-merge derivations: augment existing parquets with derived columns.

Computes columns that the replay didn't fill (or filled in an older schema
version), purely from data already in the drop's Parquet files. Safe to
re-run idempotently.

Added in SCHEMA_VERSION 2:
  - draws.draw_class                  (from blend / depth_write / marker)
  - draws.parent_pass_path_norm       (strip 'Frame N/' prefix)
  - passes.marker_path_norm           (same)
  - events.parent_marker_path_norm    (same)

Run via: python -m bobframes.derive_post_merge <out_dir>
"""

from __future__ import annotations

import os
import re
import sys

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as papq

_RE_FRAME_PREFIX = re.compile(r'^Frame\s+\d+/?')


def _strip_frame(path: str) -> str:
    if not path:
        return ''
    return _RE_FRAME_PREFIX.sub('', path)


def _classify_draw(blend_enable: int, depth_write: int,
                   marker_path: str, blend_src_color: str, blend_dst_color: str) -> str:
    mp = (marker_path or '').lower()
    if 'shadow' in mp:
        return 'shadow'
    if 'prepass' in mp or 'depthonly' in mp:
        return 'prepass'
    if 'slate' in mp or '/ui' in mp or mp.endswith('ui'):
        return 'ui'
    if 'postprocess' in mp or 'tonemap' in mp or 'bloom' in mp or 'eyeadapt' in mp:
        return 'postprocess'
    if 'decal' in mp:
        return 'decal'
    if 'translucen' in mp:
        return 'translucent'
    if int(blend_enable or 0):
        bs = (blend_src_color or '').lower()
        bd = (blend_dst_color or '').lower()
        if bs == 'one' and bd == 'one':
            return 'additive'
        return 'translucent'
    # MobileBasePass / BasePass draws are scene opaques even when depth_write=0
    # (prepass already wrote depth with EarlyZPass=2).
    if 'basepass' in mp:
        return 'opaque'
    if int(depth_write or 0):
        return 'opaque'
    return 'other'


def _derive_draws(out_dir: str) -> bool:
    pq_path = os.path.join(out_dir, 'draws.parquet')
    csv_path = os.path.join(out_dir, 'draws.csv')
    if not os.path.exists(pq_path):
        return False
    t = papq.read_table(pq_path)
    cols = t.column_names

    parent = t.column('parent_pass_path').to_pylist() if 'parent_pass_path' in cols else []
    norm = [_strip_frame(p) for p in parent]

    blend_en = t.column('blend_enable').to_pylist() if 'blend_enable' in cols else [0] * t.num_rows
    depth_w = t.column('depth_write_enable').to_pylist() if 'depth_write_enable' in cols else [0] * t.num_rows
    bsc = t.column('blend_src_color').to_pylist() if 'blend_src_color' in cols else [''] * t.num_rows
    bdc = t.column('blend_dst_color').to_pylist() if 'blend_dst_color' in cols else [''] * t.num_rows
    classes = [_classify_draw(be, dw, p, sc, dc) for be, dw, p, sc, dc
               in zip(blend_en, depth_w, parent, bsc, bdc)]

    # Build new table in schema order
    from . import schemas
    target_cols = list(schemas.DRAWS_COLS)
    new_arrays: dict[str, pa.Array] = {}
    for c in target_cols:
        if c == 'parent_pass_path_norm':
            new_arrays[c] = pa.array(norm, type=pa.string())
        elif c == 'draw_class':
            new_arrays[c] = pa.array(classes, type=pa.string())
        elif c in cols:
            new_arrays[c] = t.column(c)
        else:
            # missing source column; emit empty
            dt = schemas.infer_dtype(c)
            default = 0 if dt in ('int', 'bool') else (0.0 if dt == 'float' else '')
            new_arrays[c] = pa.array([default] * t.num_rows)

    out_t = pa.table(new_arrays)
    papq.write_table(out_t, pq_path, compression='snappy')
    pacsv.write_csv(out_t, csv_path)
    return True


def _derive_path_norm(out_dir: str, table: str, src_col: str, dst_col: str) -> bool:
    pq_path = os.path.join(out_dir, f'{table}.parquet')
    csv_path = os.path.join(out_dir, f'{table}.csv')
    if not os.path.exists(pq_path):
        return False
    t = papq.read_table(pq_path)
    cols = t.column_names
    if src_col not in cols:
        return False

    norm = [_strip_frame(p) for p in t.column(src_col).to_pylist()]

    from . import schemas
    schema_attr = {
        'passes': schemas.PASSES_COLS,
        'events': schemas.EVENTS_COLS,
    }[table]
    target_cols = list(schema_attr)
    new_arrays: dict[str, pa.Array] = {}
    for c in target_cols:
        if c == dst_col:
            new_arrays[c] = pa.array(norm, type=pa.string())
        elif c in cols:
            new_arrays[c] = t.column(c)
        else:
            dt = schemas.infer_dtype(c)
            default = 0 if dt in ('int', 'bool') else (0.0 if dt == 'float' else '')
            new_arrays[c] = pa.array([default] * t.num_rows)

    out_t = pa.table(new_arrays)
    papq.write_table(out_t, pq_path, compression='snappy')
    pacsv.write_csv(out_t, csv_path)
    return True


# --- Texture estimated bytes ------------------------------------------------

# Bytes per pixel by RD-style format Name(). Falls back to 4 on unknown.
_BYTES_PER_PIXEL = {
    'R8G8B8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4, 'R8G8B8A8_SNORM': 4,
    'R8G8B8_UNORM': 3, 'R8G8B8_SRGB': 3,
    'B8G8R8A8_UNORM': 4, 'B8G8R8A8_SRGB': 4,
    'R8G8_UNORM': 2, 'R8G8_SNORM': 2,
    'R8_UNORM': 1, 'R8_SNORM': 1,
    'R16G16B16A16_FLOAT': 8, 'R16G16B16A16_UNORM': 8,
    'R16G16_FLOAT': 4, 'R16_FLOAT': 2,
    'R32G32B32A32_FLOAT': 16, 'R32_FLOAT': 4,
    'R11G11B10_FLOAT': 4, 'R10G10B10A2_UNORM': 4,
    'R5G6B5_UNORM': 2, 'R5G5B5A1_UNORM': 2,
    'D24_UNORM_S8_UINT': 4, 'D32_FLOAT_S8_UINT': 8,
    'D16_UNORM': 2, 'D32_FLOAT': 4, 'D24_UNORM': 3,
    # Compressed: 0.5 bpp (4-bit) for BC1/ETC1; 1 bpp for BC3/ETC2_RGBA/ASTC_4x4
    'BC1_UNORM': 0.5, 'BC1_SRGB': 0.5,
    'BC3_UNORM': 1.0, 'BC3_SRGB': 1.0,
    'BC4_UNORM': 0.5, 'BC5_UNORM': 1.0,
    'BC7_UNORM': 1.0, 'BC7_SRGB': 1.0,
    'ETC1_RGB8': 0.5, 'ETC2_RGB8': 0.5, 'ETC2_RGB8_SRGB': 0.5,
    'ETC2_RGB8A1': 0.5, 'ETC2_RGBA8': 1.0, 'ETC2_RGBA8_SRGB': 1.0,
    'EAC_R11_UNORM': 0.5, 'EAC_RG11_UNORM': 1.0,
    'ASTC_4x4_UNORM': 1.0, 'ASTC_4x4_SRGB': 1.0,
    'ASTC_5x4_UNORM': 0.8, 'ASTC_5x5_UNORM': 0.64,
    'ASTC_6x5_UNORM': 0.533, 'ASTC_6x6_UNORM': 0.444,
    'ASTC_8x5_UNORM': 0.4, 'ASTC_8x6_UNORM': 0.333,
    'ASTC_8x8_UNORM': 0.25, 'ASTC_10x10_UNORM': 0.16,
    'ASTC_12x12_UNORM': 0.111,
}


def _est_bytes_for_texture(format_str: str, width: int, height: int,
                            depth: int, mip_levels: int, sample_count: int,
                            kind: str) -> int:
    if width <= 0 or height <= 0:
        return 0
    bpp = _BYTES_PER_PIXEL.get(format_str, 4)
    base = width * height * max(depth, 1) * bpp
    if mip_levels and mip_levels > 1:
        base *= 4.0 / 3.0
    samples = max(sample_count, 1)
    base *= samples
    if kind and 'cube' in kind.lower():
        base *= 6
    return int(round(base))


def _derive_est_bytes(out_dir: str, table: str) -> bool:
    pq_path = os.path.join(out_dir, f'{table}.parquet')
    csv_path = os.path.join(out_dir, f'{table}.csv')
    if not os.path.exists(pq_path):
        return False
    t = papq.read_table(pq_path)
    cols = t.column_names
    if 'est_bytes' not in cols or 'format' not in cols:
        return False
    fmts = t.column('format').to_pylist()
    widths = t.column('width').to_pylist() if 'width' in cols else [0] * t.num_rows
    heights = t.column('height').to_pylist() if 'height' in cols else [0] * t.num_rows
    depths = t.column('depth').to_pylist() if 'depth' in cols else [0] * t.num_rows
    mips = t.column('mip_levels').to_pylist() if 'mip_levels' in cols else [1] * t.num_rows
    samps = t.column('sample_count').to_pylist() if 'sample_count' in cols else [1] * t.num_rows
    kinds = t.column('kind').to_pylist() if 'kind' in cols else [''] * t.num_rows

    new_eb = [_est_bytes_for_texture(fmts[i] or '', int(widths[i] or 0),
                                     int(heights[i] or 0), int(depths[i] or 0),
                                     int(mips[i] or 1), int(samps[i] or 1),
                                     kinds[i] or '')
              for i in range(t.num_rows)]

    from . import schemas
    target_cols = list(schemas.TEXTURES_COLS if table == 'textures' else schemas.RENDER_TARGETS_COLS)
    new_arrays: dict[str, pa.Array] = {}
    for c in target_cols:
        if c == 'est_bytes':
            new_arrays[c] = pa.array(new_eb, type=pa.int64())
        elif c in cols:
            new_arrays[c] = t.column(c)
        else:
            dt = schemas.infer_dtype(c)
            default = 0 if dt in ('int', 'bool') else (0.0 if dt == 'float' else '')
            new_arrays[c] = pa.array([default] * t.num_rows)

    out_t = pa.table(new_arrays)
    papq.write_table(out_t, pq_path, compression='snappy')
    pacsv.write_csv(out_t, csv_path)
    return True


# --- Shader complexity_score -------------------------------------------------

def _derive_complexity_score(out_dir: str) -> bool:
    pq_path = os.path.join(out_dir, 'shaders.parquet')
    csv_path = os.path.join(out_dir, 'shaders.csv')
    if not os.path.exists(pq_path):
        return False
    t = papq.read_table(pq_path)
    cols = t.column_names
    def _col(name):
        return t.column(name).to_pylist() if name in cols else [0] * t.num_rows
    ts = _col('total_texture_samples')
    br = _col('total_branches')
    lo = _col('total_loops')
    di = _col('total_discards')
    df = _col('total_dfdx_dfdy')
    m4 = _col('total_mat4_constructors')
    sl = _col('src_len')
    from . import config
    w = config.get_config().scoring.complexity   # H-17 / Q-3
    scores = [
        float(ts[i] or 0) * w.w_texture_samples
        + float(br[i] or 0) * w.w_branches
        + float(lo[i] or 0) * w.w_loops
        + float(di[i] or 0) * w.w_discards
        + float(df[i] or 0) * w.w_dfdx_dfdy
        + float(m4[i] or 0) * w.w_mat4
        + min(float(sl[i] or 0) / w.src_len_divisor, w.src_len_cap)
        for i in range(t.num_rows)
    ]

    from . import schemas
    target_cols = list(schemas.SHADERS_COLS)
    new_arrays: dict[str, pa.Array] = {}
    for c in target_cols:
        if c == 'complexity_score':
            new_arrays[c] = pa.array(scores, type=pa.float64())
        elif c in cols:
            new_arrays[c] = t.column(c)
        else:
            dt = schemas.infer_dtype(c)
            default = 0 if dt in ('int', 'bool') else (0.0 if dt == 'float' else '')
            new_arrays[c] = pa.array([default] * t.num_rows)

    out_t = pa.table(new_arrays)
    papq.write_table(out_t, pq_path, compression='snappy')
    pacsv.write_csv(out_t, csv_path)
    return True


def _derive_frame_totals_bytes(out_dir: str) -> bool:
    """After textures.est_bytes is filled, update frame_totals byte aggregates."""
    ft_path = os.path.join(out_dir, 'frame_totals.parquet')
    ft_csv = os.path.join(out_dir, 'frame_totals.csv')
    tx_path = os.path.join(out_dir, 'textures.parquet')
    bf_path = os.path.join(out_dir, 'buffers.parquet')
    if not os.path.exists(ft_path):
        return False

    ft = papq.read_table(ft_path)
    cols = ft.column_names

    # Per-capture aggregates
    tex_by_cap: dict[str, int] = {}
    if os.path.exists(tx_path):
        tx = papq.read_table(tx_path, columns=['capture', 'est_bytes'])
        cap = tx.column('capture').to_pylist()
        eb = tx.column('est_bytes').to_pylist()
        for c, b in zip(cap, eb):
            tex_by_cap[c] = tex_by_cap.get(c, 0) + int(b or 0)

    vbo_by_cap: dict[str, int] = {}
    ibo_by_cap: dict[str, int] = {}
    ubo_by_cap: dict[str, int] = {}
    if os.path.exists(bf_path):
        bf = papq.read_table(bf_path, columns=['capture', 'allocated_size_bytes',
                                                'used_as_vbo', 'used_as_ibo', 'used_as_ubo'])
        cap = bf.column('capture').to_pylist()
        sz = bf.column('allocated_size_bytes').to_pylist()
        v = bf.column('used_as_vbo').to_pylist()
        i = bf.column('used_as_ibo').to_pylist()
        u = bf.column('used_as_ubo').to_pylist()
        for ci, s, vi, ii, ui in zip(cap, sz, v, i, u):
            if vi: vbo_by_cap[ci] = vbo_by_cap.get(ci, 0) + int(s or 0)
            if ii: ibo_by_cap[ci] = ibo_by_cap.get(ci, 0) + int(s or 0)
            if ui: ubo_by_cap[ci] = ubo_by_cap.get(ci, 0) + int(s or 0)

    cap_col = ft.column('capture').to_pylist()
    new_tex = [tex_by_cap.get(c, 0) for c in cap_col]
    new_vbo = [vbo_by_cap.get(c, 0) for c in cap_col]
    new_ibo = [ibo_by_cap.get(c, 0) for c in cap_col]
    new_ubo = [ubo_by_cap.get(c, 0) for c in cap_col]

    from . import schemas
    target = list(schemas.FRAME_TOTALS_COLS)
    new_arrays: dict[str, pa.Array] = {}
    for c in target:
        if c == 'total_texture_bytes_allocated':
            new_arrays[c] = pa.array(new_tex, type=pa.int64())
        elif c == 'total_vbo_bytes_uploaded':
            new_arrays[c] = pa.array(new_vbo, type=pa.int64())
        elif c == 'total_ibo_bytes_uploaded':
            new_arrays[c] = pa.array(new_ibo, type=pa.int64())
        elif c == 'total_ubo_bytes_uploaded':
            new_arrays[c] = pa.array(new_ubo, type=pa.int64())
        elif c in cols:
            new_arrays[c] = ft.column(c)
        else:
            dt = schemas.infer_dtype(c)
            default = 0 if dt in ('int', 'bool') else (0.0 if dt == 'float' else '')
            new_arrays[c] = pa.array([default] * ft.num_rows)

    out_t = pa.table(new_arrays)
    papq.write_table(out_t, ft_path, compression='snappy')
    pacsv.write_csv(out_t, ft_csv)
    return True


def derive(out_dir: str) -> dict[str, bool]:
    """Run all post-merge derivations on an _analysis_out directory."""
    results = {}
    results['draws'] = _derive_draws(out_dir)
    results['passes'] = _derive_path_norm(out_dir, 'passes', 'marker_path', 'marker_path_norm')
    results['events'] = _derive_path_norm(out_dir, 'events', 'parent_marker_path', 'parent_marker_path_norm')
    results['textures_est_bytes'] = _derive_est_bytes(out_dir, 'textures')
    results['render_targets_est_bytes'] = _derive_est_bytes(out_dir, 'render_targets')
    results['shaders_complexity'] = _derive_complexity_score(out_dir)
    results['frame_totals_bytes'] = _derive_frame_totals_bytes(out_dir)
    return results


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('usage: derive_post_merge.py <out_dir>', file=sys.stderr)
        sys.exit(2)
    print(derive(sys.argv[1]))
