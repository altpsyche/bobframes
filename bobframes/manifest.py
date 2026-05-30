"""Per-drop _manifest.json writer.

Records schema version, build timestamp, per-capture replay status, row
counts per table, and rotated-dir name (if a previous _analysis_out was
rotated during this run).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Any

from . import schemas


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def build_manifest(
    *,
    area: str,
    drop_date: str,
    drop_label: str,
    captures: list[str],
    capture_status: dict[str, str],
    row_counts: dict[str, int],
    rotated_from: str | None,
    build_timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        'schema_version': schemas.SCHEMA_VERSION,
        'build_timestamp': build_timestamp or utc_now_iso(),
        'area': area,
        'drop_date': drop_date,
        'drop_label': drop_label,
        'captures': sorted(captures, key=lambda s: (len(s), s)),
        'capture_status': dict(capture_status),
        'row_counts': dict(row_counts),
        'rotated_from': rotated_from,
    }


def write_manifest(out_dir: str, manifest: dict[str, Any]) -> str:
    path = os.path.join(out_dir, '_manifest.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write('\n')
    return path


def read_manifest(out_dir: str) -> dict[str, Any]:
    path = os.path.join(out_dir, '_manifest.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
