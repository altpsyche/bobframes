"""Schema regression: every synthetic Parquet's column list matches schemas.expected_columns(stem)
exactly (catches alphabetization drift, dropped columns, dtype-name slips)."""
from __future__ import annotations

import os

import pyarrow.parquet as pq

from .. import schemas
from . import _render_util as u


def test_synthetic_parquet_schemas():
    checked = 0
    for dirpath, _dirs, files in os.walk(u.SYNTHETIC_DATA):
        for fn in files:
            if not fn.endswith(".parquet"):
                continue
            stem = fn[: -len(".parquet")]
            if stem.startswith("_"):  # _catalog, _global_entities — not per-table
                continue
            expected = schemas.expected_columns(stem)
            actual = tuple(pq.read_schema(os.path.join(dirpath, fn)).names)
            assert actual == expected, f"{fn}: symmetric diff {set(actual) ^ set(expected)}"
            checked += 1
    assert checked >= 27, f"expected to check >= 27 tables, checked {checked}"
