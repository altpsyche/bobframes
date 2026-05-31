"""Unit tests for the schemas module helpers (c15, doc's `unit_schemas.py`).

Distinct from test_schemas.py (the parity-tier check that emitted Parquet matches the schema): this
pins the pure-Python contracts of schemas.py itself — expected_columns round-trips, the ID_COLS
prefix invariant, dtype inference totality, and no duplicate columns.

Named `test_schemas_unit` (not the c15 doc's `unit_schemas.py`) to avoid colliding with the existing
test_schemas.py and to satisfy default pytest discovery (no `python_files` override).
"""
from __future__ import annotations

import pytest

from .. import schemas


def test_schema_version_is_int():
    assert isinstance(schemas.SCHEMA_VERSION, int)


def test_expected_columns_roundtrips_every_stem():
    for stem, spec in schemas.TABLES.items():
        assert schemas.expected_columns(stem) == spec.cols
        assert schemas.is_entity_table(stem) is spec.is_entity
        assert schemas.size_class(stem) == spec.size_class
        assert spec.size_class in ('large', 'small')
        assert schemas.table_category(stem) == spec.category
        assert spec.api == 'core'  # c05: every base table is core; c33 adds gl/vk extensions


def test_every_table_starts_with_id_cols():
    for stem, cols in ((s, schemas.expected_columns(s)) for s in schemas.TABLES):
        assert cols[:len(schemas.ID_COLS)] == schemas.ID_COLS, stem


def test_no_duplicate_columns_within_a_table():
    for stem in schemas.TABLES:
        cols = schemas.expected_columns(stem)
        assert len(cols) == len(set(cols)), f'{stem} has duplicate columns'


def test_expected_columns_unknown_stem_raises():
    with pytest.raises(KeyError):
        schemas.expected_columns('does_not_exist')


def test_infer_dtype_total_and_spot_checks():
    # Every column across every table infers one of the four supported dtypes.
    for stem in schemas.TABLES:
        for col in schemas.expected_columns(stem):
            assert schemas.infer_dtype(col) in ('int', 'float', 'bool', 'str'), (stem, col)
    # Spot-checks across the inference buckets.
    assert schemas.infer_dtype('event_id') == 'int'
    assert schemas.infer_dtype('gpu_duration_s') == 'float'
    assert schemas.infer_dtype('is_rt') == 'bool'
    assert schemas.infer_dtype('format') == 'str'
    assert schemas.infer_dtype('totally_unknown_column') == 'str'  # default
