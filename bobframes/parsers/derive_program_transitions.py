"""Derive program_transitions.parquet from draws.parquet.

Walk draws in event_id order; emit (from_program_id, to_program_id, count)
aggregated across the whole drop. Per (area, drop_date, drop_label, capture).
"""

from __future__ import annotations

import os
from collections import Counter

import pyarrow as pa
import pyarrow.parquet as papq
import pyarrow.csv as pacsv

from .. import schemas


def derive(out_dir: str) -> int:
    draws_pq = os.path.join(out_dir, 'draws.parquet')
    if not os.path.exists(draws_pq):
        return 0

    t = papq.read_table(draws_pq, columns=list(schemas.ID_COLS) + ['event_id', 'program_id'])
    n = t.num_rows
    if n == 0:
        return 0

    # Group by (area, drop_date, drop_label, capture) and walk in event_id order.
    cols = {c: t.column(c).to_pylist() for c in t.column_names}
    groups: dict[tuple, list[tuple[int, int]]] = {}
    for i in range(n):
        key = (cols['area'][i], cols['drop_date'][i], cols['drop_label'][i], cols['capture'][i])
        groups.setdefault(key, []).append((cols['event_id'][i], cols['program_id'][i]))

    out_rows: dict[tuple, dict] = {}
    for key, draws_for_capture in groups.items():
        draws_for_capture.sort(key=lambda x: x[0])
        prev = 0
        counter: Counter = Counter()
        for ev, pid in draws_for_capture:
            if prev and pid and prev != pid:
                counter[(prev, pid)] += 1
            prev = pid
        for (a, b), c in counter.items():
            out_rows[(key, a, b)] = {
                'area': key[0], 'drop_date': key[1], 'drop_label': key[2], 'capture': key[3],
                'from_program_id': a, 'to_program_id': b, 'count': c,
            }

    cols_out = list(schemas.PROG_TRANS_COLS)
    arrays: dict[str, pa.Array] = {}
    for c in cols_out:
        vs = [r[c] for r in out_rows.values()]
        dt = schemas.infer_dtype(c)
        if dt == 'int':
            arrays[c] = pa.array(vs, type=pa.int64())
        else:
            arrays[c] = pa.array(vs, type=pa.string())

    table = pa.table(arrays)
    papq.write_table(table, os.path.join(out_dir, 'program_transitions.parquet'),
                     compression='snappy')
    pacsv.write_csv(table, os.path.join(out_dir, 'program_transitions.csv'))
    return table.num_rows


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print('usage: derive_program_transitions.py <out_dir>', file=sys.stderr)
        sys.exit(2)
    print(f'wrote {derive(sys.argv[1])} program_transitions rows')
