"""Build <root>/_data/_catalog.parquet and _catalog.json.

One row per (area, drop_date, drop_label, capture). Per-capture row counts
are computed by reading each drop's parquets and grouping by the `capture`
column — that way the catalog reflects what actually landed for each
capture, not just drop-level totals.

Also tracks schema version, build timestamp, replay status, and the relative
path to the drop's data dir (`_data/<area>/<drop>`). Path is RELATIVE for
portability across machines.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from collections import defaultdict

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as papq

from . import manifest as _manifest, paths as _paths, schemas


# Derived from the single registry (H-10). schemas.TABLES key order IS the catalog order, so the
# row_count_* column order baked into the golden root index.html stays byte-identical.
_CATALOG_TABLE_KEYS = tuple(schemas.TABLES.keys())


def _find_manifests(root: str) -> list[tuple[str, str, dict]]:
    """Walk _data/<area>/<drop>/_manifest.json. Returns [(data_dir, rel_path, manifest)]."""
    out = []
    data_root = _paths.data_root(root)
    if not os.path.isdir(data_root):
        return out
    for area_entry in sorted(os.listdir(data_root)):
        if area_entry.startswith(('_', '.')):
            continue
        area_dir = os.path.join(data_root, area_entry)
        if not os.path.isdir(area_dir):
            continue
        for drop_entry in sorted(os.listdir(area_dir)):
            drop_dir = os.path.join(area_dir, drop_entry)
            if not os.path.isdir(drop_dir):
                continue
            mf = os.path.join(drop_dir, _paths.MANIFEST_NAME)
            if not os.path.exists(mf):
                continue
            try:
                with open(mf, 'r', encoding='utf-8') as f:
                    m = json.load(f)
            except Exception:
                continue
            # R-18: skip non-canonical drop dirs. A `--force` run rotates the live drop to a SIBLING
            # backup `<drop>.<ts>` (R-16) that still carries the ORIGINAL manifest, so its dir name no
            # longer equals `<drop_date>_<drop_label>`; counting it would emit a DUPLICATE capture row.
            # `.stage`/`.tmp` staging dirs are excluded the same way. Reconstructing from the manifest
            # (not a `'.' in name` test) keeps legit labels that contain a dot.
            if drop_entry != _paths.drop_dirname(m.get('drop_date', ''), m.get('drop_label') or ''):
                continue
            rel = _paths.drop_dir_rel(area_entry, drop_entry)
            out.append((drop_dir, rel, m))
    return out


def _per_capture_row_counts(data_dir: str, captures: list[str]) -> dict[str, dict[str, int]]:
    """Walk all parquets in data_dir; return {capture: {table: row_count}}."""
    result: dict[str, dict[str, int]] = {c: defaultdict(int) for c in captures}
    for table in _CATALOG_TABLE_KEYS:
        pq = os.path.join(data_dir, f'{table}.parquet')
        if not os.path.exists(pq):
            continue
        try:
            t = papq.read_table(pq, columns=['capture'])
            caps = t.column('capture').to_pylist()
        except Exception:
            continue
        for c in caps:
            if c in result:
                result[c][table] += 1
    return {c: dict(d) for c, d in result.items()}


def _capture_rows(data_dir: str, rel_path: str, manifest: dict) -> list[dict]:
    captures = manifest.get('captures') or manifest.get('stems') or []
    cap_status = manifest.get('capture_status') or manifest.get('stem_status') or {}

    per_cap = _per_capture_row_counts(data_dir, captures) if captures else {}

    rows: list[dict] = []
    for cap in captures:
        counts = per_cap.get(cap, {})
        rows.append({
            'area': manifest['area'],
            'drop_date': manifest['drop_date'],
            'drop_label': manifest.get('drop_label', '') or '',
            'capture': cap,
            'schema_version': int(manifest.get('schema_version', 0)),
            'build_timestamp': manifest.get('build_timestamp', ''),
            'replay_status': cap_status.get(cap, 'unknown'),
            **{f'row_count_{k}': int(counts.get(k, 0)) for k in _CATALOG_TABLE_KEYS},
            'analysis_out_path': rel_path,
        })
    return rows


def build_catalog(root: str) -> dict:
    manifests = _find_manifests(root)
    all_rows: list[dict] = []
    for data_dir, rel_path, m in manifests:
        # D-7: refuse to (re)build over a drop written under a different SCHEMA_VERSION. This is the
        # shared chokepoint for `render` (which rebuilds the catalog first) and `catalog`.
        _manifest.check_schema_version(m, source=rel_path)
        all_rows.extend(_capture_rows(data_dir, rel_path, m))

    cols = [
        'area', 'drop_date', 'drop_label', 'capture',
        'schema_version', 'build_timestamp', 'replay_status',
    ] + [f'row_count_{k}' for k in _CATALOG_TABLE_KEYS] + ['analysis_out_path']

    arrays: dict[str, pa.Array] = {}
    for c in cols:
        vs = [r.get(c, '' if not c.startswith('row_count_') and c != 'schema_version' else 0)
              for r in all_rows]
        if c.startswith('row_count_') or c == 'schema_version':
            arrays[c] = pa.array(vs, type=pa.int64())
        else:
            arrays[c] = pa.array([str(v) for v in vs], type=pa.string())
    table = pa.table(arrays)

    os.makedirs(_paths.data_root(root), exist_ok=True)
    papq.write_table(table, _paths.catalog_parquet(root), compression='snappy')
    pacsv.write_csv(table, _paths.catalog_csv(root))

    summary = {
        'schema_version': max((r['schema_version'] for r in all_rows), default=0),
        'build_timestamp': _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        'drop_count': len({(r['area'], r['drop_date'], r['drop_label']) for r in all_rows}),
        'capture_count': len(all_rows),
        'areas': sorted({r['area'] for r in all_rows}),
    }
    with open(_paths.catalog_json(root), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == '__main__':
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    s = build_catalog(root)
    print(json.dumps(s, indent=2))
