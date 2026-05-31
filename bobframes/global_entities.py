"""Emit <root>/_global_entities.parquet.

One row per (stable_key, kind, area, drop_date, drop_label, capture, local_id).
This is the canonical index for cross-drop entity joins. Layer 2 reports
join into draws/passes/events tables using stable_key directly:

    SELECT *
    FROM read_parquet('**/draws.parquet') d
    JOIN read_parquet('_global_entities.parquet') g
      ON g.area = d.area
     AND g.drop_date = d.drop_date
     AND g.drop_label = d.drop_label
     AND g.capture = d.capture
     AND g.local_id = d.fs_shader_id
     AND g.kind = 'shader'
    WHERE g.stable_key = 'abc123...';

The (kind, local_id) pair lets reports resolve any per-capture resource ID
back to its drop-spanning identity.
"""

from __future__ import annotations

import glob
import os

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as papq

from . import schemas


# Entity kind label: RTs are indexed as textures; everything else is the stem depluralized (H-9).
_KIND_OVERRIDE = {'render_targets': 'texture'}


def _entity_id_col(stem: str) -> str:
    """Per-capture resource-id column = the field right after stable_key (registry convention)."""
    cols = schemas.expected_columns(stem)
    return cols[cols.index('stable_key') + 1]


def _entity_kind(stem: str) -> str:
    return _KIND_OVERRIDE.get(stem, stem[:-1] if stem.endswith('s') else stem)


_OUT_COLS = ('stable_key', 'kind', 'area', 'drop_date', 'drop_label',
             'capture', 'local_id')


def build_global_entities(root: str) -> int:
    """Walk every entity parquet under <root>; emit _global_entities.parquet.

    Returns the row count written.
    """
    cols: dict[str, list] = {c: [] for c in _OUT_COLS}

    from . import paths as _paths
    data_root = _paths.data_root(root)
    for table in schemas.entity_tables():
        id_col = _entity_id_col(table)
        kind = _entity_kind(table)
        for path in sorted(glob.glob(os.path.join(data_root, '*', '*',
                                                  f'{table}.parquet'))):
            try:
                t = papq.read_table(path, columns=['stable_key', 'area', 'drop_date',
                                                   'drop_label', 'capture', id_col])
            except Exception:
                continue
            sk = t.column('stable_key').to_pylist()
            ar = t.column('area').to_pylist()
            dd = t.column('drop_date').to_pylist()
            dl = t.column('drop_label').to_pylist()
            cp = t.column('capture').to_pylist()
            lid = t.column(id_col).to_pylist()
            for i in range(len(sk)):
                if not sk[i]:
                    continue  # skip entities without a stable_key (best-effort only)
                cols['stable_key'].append(sk[i])
                cols['kind'].append(kind)
                cols['area'].append(ar[i])
                cols['drop_date'].append(dd[i])
                cols['drop_label'].append(dl[i])
                cols['capture'].append(cp[i])
                cols['local_id'].append(int(lid[i]) if lid[i] is not None else 0)

    arrays: dict[str, pa.Array] = {}
    for c in _OUT_COLS:
        if c == 'local_id':
            arrays[c] = pa.array(cols[c], type=pa.int64())
        else:
            arrays[c] = pa.array(cols[c], type=pa.string())
    table = pa.table(arrays)

    os.makedirs(_paths.data_root(root), exist_ok=True)
    papq.write_table(table, _paths.global_entities_parquet(root), compression='snappy')
    pacsv.write_csv(table, _paths.global_entities_csv(root))
    return table.num_rows


if __name__ == '__main__':
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    n = build_global_entities(root)
    print(f'wrote _global_entities.parquet: {n} rows')
