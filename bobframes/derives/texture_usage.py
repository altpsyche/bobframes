"""Per-texture usage heat.

Reads descriptor_access.parquet filtered to ReadOnlyResource (textures),
groups by (area, drop_date, drop_label, capture, resource_id), counts
unique events sampled + total accesses + first/last event. Joins into
textures.parquet to attach stable_key + label + format.

Lets reports answer: which texture is sampled the most? Which is bound but
never sampled? Memory-vs-usage ratio per texture?
"""

from __future__ import annotations

import os
from collections import defaultdict

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as papq

from .. import schemas


def build(out_dir: str) -> int:
    da_path = os.path.join(out_dir, 'descriptor_access.parquet')
    tx_path = os.path.join(out_dir, 'textures.parquet')
    if not os.path.exists(da_path):
        return 0

    da = papq.read_table(da_path, columns=[
        'area', 'drop_date', 'drop_label', 'capture',
        'event_id', 'descriptor_kind', 'resource_id',
    ])
    ar = da.column('area').to_pylist()
    dd = da.column('drop_date').to_pylist()
    dl = da.column('drop_label').to_pylist()
    cp = da.column('capture').to_pylist()
    ev = da.column('event_id').to_pylist()
    kn = da.column('descriptor_kind').to_pylist()
    rid = da.column('resource_id').to_pylist()

    agg: dict[tuple, dict] = defaultdict(lambda: {
        'events': set(), 'count': 0,
        'first_event_id': -1, 'last_event_id': -1,
    })
    # Arm RD's GLES backend uses 'ImageSampler' (sampled tex+sampler combo)
    # plus 'ReadOnlyResource' on other backends. Accept both.
    TEX_KINDS = {'ImageSampler', 'ReadOnlyResource'}
    for i in range(da.num_rows):
        if kn[i] not in TEX_KINDS:
            continue
        r = rid[i]
        if not r:
            continue
        key = (ar[i], dd[i], dl[i], cp[i], int(r))
        a = agg[key]
        e = int(ev[i] or 0)
        a['events'].add(e)
        a['count'] += 1
        if a['first_event_id'] < 0 or e < a['first_event_id']:
            a['first_event_id'] = e
        if e > a['last_event_id']:
            a['last_event_id'] = e

    # Build textures lookup: (area, drop_date, drop_label, capture, tex_id) -> {stable_key, label, format}
    tex_info: dict[tuple, dict] = {}
    if os.path.exists(tx_path):
        tx = papq.read_table(tx_path, columns=[
            'area', 'drop_date', 'drop_label', 'capture',
            'tex_id', 'stable_key', 'label', 'format',
        ])
        for i in range(tx.num_rows):
            tex_info[(
                tx.column('area')[i].as_py(),
                tx.column('drop_date')[i].as_py(),
                tx.column('drop_label')[i].as_py(),
                tx.column('capture')[i].as_py(),
                int(tx.column('tex_id')[i].as_py() or 0),
            )] = {
                'stable_key': tx.column('stable_key')[i].as_py() or '',
                'label': tx.column('label')[i].as_py() or '',
                'format': tx.column('format')[i].as_py() or '',
            }

    out_rows = []
    for key, vals in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3], -len(kv[1]['events']))):
        info = tex_info.get(key, {'stable_key': '', 'label': '', 'format': ''})
        out_rows.append({
            'area': key[0], 'drop_date': key[1], 'drop_label': key[2],
            'capture': key[3], 'tex_id': key[4],
            'stable_key': info['stable_key'],
            'label': info['label'],
            'format': info['format'],
            'n_unique_events_sampled': len(vals['events']),
            'n_descriptor_accesses': vals['count'],
            'first_event_id': vals['first_event_id'],
            'last_event_id': vals['last_event_id'],
        })

    cols_target = list(schemas.TEXTURE_USAGE_COLS)
    arrays: dict[str, pa.Array] = {}
    for c in cols_target:
        dt = schemas.infer_dtype(c)
        vs = [r.get(c) for r in out_rows]
        if dt == 'int':
            arrays[c] = pa.array([int(v or 0) for v in vs], type=pa.int64())
        elif dt == 'float':
            arrays[c] = pa.array([float(v or 0.0) for v in vs], type=pa.float64())
        else:
            arrays[c] = pa.array([str(v or '') for v in vs], type=pa.string())
    table = pa.table(arrays)
    papq.write_table(table, os.path.join(out_dir, 'texture_usage.parquet'),
                     compression='snappy')
    pacsv.write_csv(table, os.path.join(out_dir, 'texture_usage.csv'))
    return table.num_rows


if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f'wrote {build(p)} rows')
