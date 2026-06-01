"""Per-pass × draw_class aggregation.

Reads draws.parquet + counters_per_event.parquet, joins on event_id for
gpu_duration_s, groups by (area, drop_date, drop_label, capture,
parent_pass_path_norm, draw_class). Emits one row per group.
"""

from __future__ import annotations

import os
from collections import defaultdict

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as papq

from .. import schemas
from . import classifier


def build(out_dir: str) -> int:
    draws_path = os.path.join(out_dir, 'draws.parquet')
    counters_path = os.path.join(out_dir, 'counters_per_event.parquet')
    if not os.path.exists(draws_path):
        return 0

    draws = papq.read_table(draws_path, columns=[
        'area', 'drop_date', 'drop_label', 'capture',
        'event_id', 'parent_pass_path_norm', 'draw_class',
        'num_indices', 'num_instances',
    ])

    durations: dict[tuple, float] = {}
    if os.path.exists(counters_path):
        ct = papq.read_table(counters_path, columns=[
            'area', 'drop_date', 'drop_label', 'capture',
            'event_id', 'counter_name', 'value_double',
        ])
        ar = ct.column('area').to_pylist()
        dd = ct.column('drop_date').to_pylist()
        dl = ct.column('drop_label').to_pylist()
        cp = ct.column('capture').to_pylist()
        ev = ct.column('event_id').to_pylist()
        cn = ct.column('counter_name').to_pylist()
        vd = ct.column('value_double').to_pylist()
        gpu_aliases = set(classifier.gpu_duration_aliases())   # H-4 — was the literal 'GPU Duration'
        for i in range(ct.num_rows):
            if cn[i] in gpu_aliases:
                durations[(ar[i], dd[i], dl[i], cp[i], ev[i])] = float(vd[i] or 0.0)

    agg: dict[tuple, dict] = defaultdict(lambda: {
        'n_draws': 0, 'n_dispatches': 0,
        'sum_pre_vs_vertices': 0, 'sum_gpu_duration_s': 0.0,
    })
    d_ar = draws.column('area').to_pylist()
    d_dd = draws.column('drop_date').to_pylist()
    d_dl = draws.column('drop_label').to_pylist()
    d_cp = draws.column('capture').to_pylist()
    d_ev = draws.column('event_id').to_pylist()
    d_pp = draws.column('parent_pass_path_norm').to_pylist()
    d_cl = draws.column('draw_class').to_pylist()
    d_ni = draws.column('num_indices').to_pylist()
    d_ic = draws.column('num_instances').to_pylist()

    for i in range(draws.num_rows):
        key = (d_ar[i], d_dd[i], d_dl[i], d_cp[i], d_pp[i] or '', d_cl[i] or 'other')
        a = agg[key]
        a['n_draws'] += 1
        a['sum_pre_vs_vertices'] += int(d_ni[i] or 0) * max(int(d_ic[i] or 1), 1)
        dur = durations.get((d_ar[i], d_dd[i], d_dl[i], d_cp[i], d_ev[i]), 0.0)
        a['sum_gpu_duration_s'] += dur

    cols_target = list(schemas.PASS_CLASS_BREAKDOWN_COLS)
    out_rows = []
    for key, vals in sorted(agg.items()):
        out_rows.append({
            'area': key[0], 'drop_date': key[1], 'drop_label': key[2],
            'capture': key[3], 'marker_path_norm': key[4], 'draw_class': key[5],
            'n_draws': vals['n_draws'], 'n_dispatches': vals['n_dispatches'],
            'sum_pre_vs_vertices': vals['sum_pre_vs_vertices'],
            'sum_gpu_duration_s': vals['sum_gpu_duration_s'],
        })

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
    papq.write_table(table, os.path.join(out_dir, 'pass_class_breakdown.parquet'),
                     compression='snappy')
    pacsv.write_csv(table, os.path.join(out_dir, 'pass_class_breakdown.csv'))
    return table.num_rows


if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f'wrote {build(p)} rows')
